"""
Historical xStock Chainlink scraper (Solana mainnet, Verifier program).

Use case: for each market-closed window (weekend / long weekend / holiday bridge),
find the last Chainlink v10 observation per xStock before the NYSE Monday open.

Strategy:
  1. Seed a starting signature near the window end_ts via the RPC signature
     enumeration endpoint (cheap: 1k sigs / call, 1 RPC credit).
  2. Walk backward through Verifier transactions via the Helius Enhanced API
     (100 parsed txs / call, 1 DAS credit).
  3. For each returned tx, locate the inner Verifier `verify` ix, decode via
     the snappy-decompress + envelope-parse path (meta.returnData isn't
     exposed by the Enhanced API), keep v10 reports whose feedId is in our
     xStock mapping.
  4. Stop when the oldest tx's block_time falls below start_ts.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Iterator

import pandas as pd

from ..sources.helius import (
    enhanced_address_transactions,
    get_signatures_for_address,
    get_transaction,
    rpc,
    rpc_batch,
)
from .feeds import feed_id_to_xstock
from .v10 import decode as v10_decode
from .verifier import VERIFIER_PROGRAM_ID, parse_verify, parse_verify_return_data


def _slots_per_second() -> float:
    """Measure live slot rate from two points 100k slots apart (~11h).

    Shorter lookback than feels natural because RPC Fast Start-tier nodes prune
    ~850k slots back; Helius retains deeper. 100k is within any provider's
    retention window and still gives a stable slot-rate estimate.
    """
    cur_slot = rpc("getSlot")
    cur_ts = rpc("getBlockTime", [cur_slot])
    ref_slot = max(0, cur_slot - 100_000)
    ref_ts = rpc("getBlockTime", [ref_slot])
    if ref_ts is None or cur_ts is None or cur_ts == ref_ts:
        return 2.5
    return (cur_slot - ref_slot) / (cur_ts - ref_ts)


def _seed_verifier_sig_near_ts(target_ts: int, search_radius: int = 200) -> str | None:
    """Return a Verifier signature near `target_ts` using slot estimation.

    Walks blocks outward from the estimated slot until finding one with any tx;
    uses any tx in that block as a `before=` anchor into `getSignaturesForAddress`
    (which returns addr-specific Verifier sigs regardless of the anchor's program).
    """
    rate = _slots_per_second()
    cur_slot = rpc("getSlot")
    cur_ts = rpc("getBlockTime", [cur_slot])
    est_slot = cur_slot - int((cur_ts - target_ts) * rate)

    # Walk outward from est_slot to find a non-skipped block
    for delta in range(search_radius):
        for slot in (est_slot + delta, est_slot - delta):
            try:
                block = rpc(
                    "getBlock",
                    [slot, {
                        "transactionDetails": "signatures",
                        "rewards": False,
                        "maxSupportedTransactionVersion": 0,
                    }],
                )
            except Exception:
                continue
            if not block:
                continue
            sigs = block.get("signatures") or []
            if not sigs:
                continue
            # Anchor into Verifier's sig stream via any block-local sig
            anchor = sigs[0]
            verifier_sigs = get_signatures_for_address(
                VERIFIER_PROGRAM_ID, before=anchor, limit=1000
            )
            if verifier_sigs:
                # Walk into the batch to find the first sig <= target_ts
                for vs in verifier_sigs:
                    bt = vs.get("blockTime")
                    if bt is not None and bt <= target_ts:
                        return vs["signature"]
                # Otherwise use the last (oldest) in the batch as a stepping stone
                return verifier_sigs[-1]["signature"]
    return None


def iter_xstock_reports(
    start_ts: int,
    end_ts: int,
    *,
    before_signature: str | None = None,
    verbose: bool = False,
) -> Iterator[dict]:
    """Walk Verifier txs in (start_ts, end_ts], yielding one dict per xStock v10 obs.

    `before_signature` optionally seeds pagination at a known sig to avoid the
    initial getSignaturesForAddress probe; use _find_sig_before() for a generic case.
    """
    if before_signature is None:
        before_signature = _seed_verifier_sig_near_ts(end_ts + 120)
    if before_signature is None:
        if verbose:
            print(f"  no seed signature found for end_ts={end_ts}", flush=True)
        return

    pages = 0
    n_txs = 0
    n_verify_ix = 0
    n_v10 = 0
    n_xstock = 0
    t_start = time.monotonic()

    # Local paginator (need to seed `before` ourselves; can't use the module helper)
    cursor_before: str | None = before_signature
    while True:
        batch = enhanced_address_transactions(
            VERIFIER_PROGRAM_ID, before=cursor_before, limit=100
        )
        if not batch:
            break
        pages += 1
        batch_min_ts = min((t.get("timestamp") or 0) for t in batch)
        for tx in batch:
            ts = tx.get("timestamp")
            if ts is None:
                continue
            if ts > end_ts:
                continue  # newer than our window — skip (shouldn't happen after seed)
            if ts <= start_ts:
                continue  # older than window — will bail after this batch
            n_txs += 1
            # Collect every inner-instruction call to the Verifier
            for outer in tx.get("instructions", []):
                for inner in outer.get("innerInstructions", []) or []:
                    if inner.get("programId") != VERIFIER_PROGRAM_ID:
                        continue
                    n_verify_ix += 1
                    try:
                        p = parse_verify(inner["data"])
                    except Exception:
                        continue
                    if p.schema != 0x000a:
                        continue
                    n_v10 += 1
                    sym = feed_id_to_xstock(p.raw_report[:32])
                    if sym is None:
                        continue
                    n_xstock += 1
                    r = v10_decode(p.raw_report)
                    yield {
                        "symbol": sym,
                        "feed_id": r.feed_id_hex,
                        "obs_ts": r.observations_timestamp,
                        "mid": float(r.mid),
                        "bid": float(r.bid),
                        "ask": float(r.ask),
                        "last_traded": float(r.last_traded_price),
                        "tx_block_time": ts,
                        "signature": tx["signature"],
                    }
        # Stop when the batch is entirely below the floor
        if batch_min_ts <= start_ts:
            break
        if len(batch) < 100:
            break  # no more pages
        cursor_before = batch[-1]["signature"]

    if verbose:
        dt = time.monotonic() - t_start
        print(
            f"  window [{datetime.fromtimestamp(start_ts, UTC):%Y-%m-%d %H:%M}, "
            f"{datetime.fromtimestamp(end_ts, UTC):%Y-%m-%d %H:%M}] "
            f"pages={pages} txs={n_txs} verify_ix={n_verify_ix} v10={n_v10} xstock={n_xstock} "
            f"in {dt:.1f}s",
            flush=True,
        )


def iter_xstock_reports_rpc(
    start_ts: int,
    end_ts: int,
    *,
    before_signature: str | None = None,
    verbose: bool = False,
) -> Iterator[dict]:
    """RPC-path equivalent of iter_xstock_reports — uses getSignaturesForAddress +
    getTransaction instead of the Helius Enhanced API. Slower per tx but more reliable
    for historical data (Enhanced API sometimes 504s on distant queries).

    Decodes via meta.returnData (base64-decode, no snappy/envelope parse needed)."""
    if before_signature is None:
        before_signature = _seed_verifier_sig_near_ts(end_ts + 120)
    if before_signature is None:
        if verbose:
            print(f"  no seed for end_ts={end_ts}", flush=True)
        return

    pages = 0
    n_txs = 0
    n_xstock = 0
    t_start = time.monotonic()
    cursor: str | None = before_signature

    while True:
        sigs = get_signatures_for_address(VERIFIER_PROGRAM_ID, before=cursor, limit=1000)
        if not sigs:
            break
        pages += 1
        batch_min_ts = min((s.get("blockTime") or 0) for s in sigs)
        batch_max_ts = max((s.get("blockTime") or 0) for s in sigs)
        in_window = [s for s in sigs
                     if s.get("blockTime") is not None
                     and start_ts < s["blockTime"] <= end_ts
                     and s.get("err") is None]
        if verbose:
            print(
                f"    page {pages}: {len(sigs)} sigs "
                f"[{datetime.fromtimestamp(batch_min_ts, UTC):%m-%d %H:%M}..{datetime.fromtimestamp(batch_max_ts, UTC):%m-%d %H:%M}] "
                f"{len(in_window)} in window, n_xstock_so_far={n_xstock}",
                flush=True,
            )
        # Fetch transactions via rpc_batch — concurrent serial POSTs, bounded by
        # the provider's rate limiter. BATCH sizes the wave; 25 is a round figure
        # that saturates Helius's 9 req/s cap in ~3s and RPC Fast's 14 req/s in ~2s.
        BATCH = 25
        tx_opts = {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
        for chunk_start in range(0, len(in_window), BATCH):
            chunk = in_window[chunk_start:chunk_start + BATCH]
            calls = [("getTransaction", [s["signature"], tx_opts]) for s in chunk]
            try:
                txs = rpc_batch(calls)
            except Exception:
                # Fall back to per-tx fetch so one bad sig doesn't waste the whole batch
                txs = []
                for s in chunk:
                    try:
                        txs.append(get_transaction(s["signature"]))
                    except Exception:
                        txs.append(None)
            for s, tx in zip(chunk, txs):
                n_txs += 1
                if not tx:
                    continue
                rd = parse_verify_return_data((tx.get("meta") or {}).get("returnData"))
                if rd is None or rd.schema != 0x000a:
                    continue
                sym = feed_id_to_xstock(rd.raw_report[:32])
                if sym is None:
                    continue
                n_xstock += 1
                r = v10_decode(rd.raw_report)
                yield {
                    "symbol": sym,
                    "feed_id": r.feed_id_hex,
                    "obs_ts": r.observations_timestamp,
                    "mid": float(r.mid),
                    "bid": float(r.bid),
                    "ask": float(r.ask),
                    "last_traded": float(r.last_traded_price),
                    "tx_block_time": s["blockTime"],
                    "signature": s["signature"],
                }
        if batch_min_ts <= start_ts or len(sigs) < 1000:
            break
        cursor = sigs[-1]["signature"]

    if verbose:
        dt = time.monotonic() - t_start
        print(
            f"  [rpc] window [{datetime.fromtimestamp(start_ts, UTC):%Y-%m-%d %H:%M}, "
            f"{datetime.fromtimestamp(end_ts, UTC):%Y-%m-%d %H:%M}] "
            f"pages={pages} txs_fetched={n_txs} xstock={n_xstock} in {dt:.1f}s",
            flush=True,
        )


def fetch_latest_per_xstock(
    end_ts: int,
    *,
    lookback_hours: int = 24,
    target_symbols: set[str] | None = None,
    use_rpc: bool = False,
    max_in_window_yields: int = 3000,
    verbose: bool = False,
) -> dict[str, dict]:
    """Walk backward from `end_ts`, return the latest v10 observation per xStock.

    Stops when either:
      - every symbol in `target_symbols` has been seen (fast path — ~1 min), OR
      - `max_in_window_yields` xStock observations have been yielded without covering
        all symbols (bounded fallback — prevents infinite spin if one feedId is
        inactive for this window, e.g. due to feedId rotation or a sparse update
        schedule). Returns whatever was found.

    Observations are yielded newest-first, so first-seen = latest.
    """
    if target_symbols is None:
        from .feeds import XSTOCK_FEEDS
        target_symbols = set(XSTOCK_FEEDS.values())

    start_ts = end_ts - lookback_hours * 3600
    latest: dict[str, dict] = {}
    iterator = (
        iter_xstock_reports_rpc(start_ts, end_ts, verbose=verbose)
        if use_rpc
        else iter_xstock_reports(start_ts, end_ts, verbose=verbose)
    )
    n_yields = 0
    for obs in iterator:
        n_yields += 1
        sym = obs["symbol"]
        if sym in target_symbols and sym not in latest:
            latest[sym] = obs
            if set(latest.keys()) >= target_symbols:
                break
        if n_yields >= max_in_window_yields:
            missing = sorted(target_symbols - set(latest.keys()))
            if verbose:
                print(
                    f"  max_in_window_yields={max_in_window_yields} hit; "
                    f"found {len(latest)}/{len(target_symbols)}, missing={missing}",
                    flush=True,
                )
            break
    return latest


def fetch_xstock_reports(start_ts: int, end_ts: int, *, verbose: bool = False) -> pd.DataFrame:
    """Materialise all xStock v10 observations in a closed window as a DataFrame."""
    rows = list(iter_xstock_reports(start_ts, end_ts, verbose=verbose))
    if not rows:
        return pd.DataFrame(
            columns=["symbol", "feed_id", "obs_ts", "mid", "bid", "ask", "last_traded",
                     "tx_block_time", "signature"]
        )
    df = pd.DataFrame(rows)
    df["obs_at"] = pd.to_datetime(df["obs_ts"], unit="s", utc=True)
    return df.sort_values(["symbol", "obs_ts"]).reset_index(drop=True)
