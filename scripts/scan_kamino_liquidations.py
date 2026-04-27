"""Scan Kamino-Klend liquidation events on the xStocks lending market.

Phase 1 publication-risk gate: Paper 2 §C4 + Paper 3 cost-anchor inputs. Until
this script existed, every claim about xStocks-on-Kamino OEV concentration or
liquidation-event severity rested on retrospective underlier proxies. This
emits the actual on-chain event panel, reconstructed from RPC primitives only:

  signature → slot → block_time → liquidator → obligation
            → repay_reserve  (+ symbol)  → repay_amount (lamports)
            → withdraw_reserve (+ symbol) → liquidity-side accounts
            → liquidation IX version (V1 / V2)
            → min_acceptable_received_liquidity_amount, max_allowed_ltv_override_pct

How it works:

1. Walks ``getSignaturesForAddress`` on the xStocks lending market PDA
   (``5wJeMrUYECGq41fxRESKALVcHnNX26TAWy4W98yULsua``). Every Klend IX touching
   this market — including liquidations — appears in this signature stream.
2. For each batch of signatures, parallel-fetches ``getTransaction`` via the
   existing ``rpc_batch`` helper (provider rate-limited).
3. Walks both top-level and inner instructions. Filters to ``programId ==
   KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD`` and matches the leading 8
   bytes of the IX data against the two liquidation discriminators:
       liquidate_obligation_and_redeem_reserve_collateral     (V1)
       liquidate_obligation_and_redeem_reserve_collateral_v2  (V2)
4. Decodes the args (three little-endian u64s after the 8-byte disc) and
   resolves the account references against the IX's ``accounts`` list
   (``jsonParsed`` encoding inlines pubkey strings directly).
5. Filters out events whose ``lending_market`` is not the xStocks market
   (defensive — should be redundant given the address filter, but a Klend
   instruction could in principle CPI through the same tx for a different
   market).
6. Maps repay/withdraw reserve PDAs back to xStock symbols using the latest
   reserve snapshot, so the event panel is self-describing.

What this does NOT do (deferred to follow-up):
- Reconstruct the pre/post oracle update price around the liquidation slot
  (requires ``getAccountInfo`` at slot vs. continuous Scope tape — the
  forward-running tape is the cleanest path; backfill from RPC is possible
  but expensive).
- Reconstruct realized liquidator profit (requires resolving collateral
  amount actually withdrawn, not just the IX-arg ``liquidity_amount`` repaid).
- Attach Jito bundle / searcher metadata. Possible via Jito's bundle API
  (free), but out of scope for v1 of the panel.

Output: ``data/processed/kamino_liquidations_YYYYMMDD.parquet`` (one row per
liquidation event) + a JSON summary with cross-event aggregates.

Run:
    uv run python scripts/scan_kamino_liquidations.py --days-back 30
    uv run python scripts/scan_kamino_liquidations.py --days-back 365 --max-pages 50

Free-tier RPC only. Helius free tier supports ``getSignaturesForAddress`` and
``getTransaction`` without batch JSON-RPC; ``rpc_batch`` issues concurrent
serial POSTs bounded by the provider's rate limiter.
"""
from __future__ import annotations

import argparse
import base64
import json
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

import base58
import pandas as pd

from soothsayer.config import DATA_PROCESSED
from soothsayer.sources.helius import (
    get_signatures_for_address,
    get_transaction,
    paginate_signatures,
    rpc,
    rpc_batch,
)

KLEND_PROGRAM = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD"
# The xStocks lending market PDA from the reserve snapshot. Defensive — if a
# future snapshot adds reserves in a second market, the loader below catches
# it and aborts rather than silently scanning the wrong market.
XSTOCKS_MARKET = "5wJeMrUYECGq41fxRESKALVcHnNX26TAWy4W98yULsua"

# Anchor instruction discriminators (sha256("global:<ix_name>")[:8], hex).
# Regenerate with:
#   python -c "import hashlib; print(hashlib.sha256(b'global:liquidate_obligation_and_redeem_reserve_collateral').hexdigest()[:16])"
LIQUIDATE_V1_DISC = bytes.fromhex("b1479abce2854a37")
LIQUIDATE_V2_DISC = bytes.fromhex("a2a1238f1ebbb967")

# Account ordering inside the inner ``liquidationAccounts`` substructure of
# both V1 and V2 IXs (V2 wraps V1's flat list and appends two farms account
# groups; the first 20 entries are identical). We only need a few:
ACC_LIQUIDATOR = 0
ACC_OBLIGATION = 1
ACC_LENDING_MARKET = 2
ACC_REPAY_RESERVE = 4
ACC_WITHDRAW_RESERVE = 7

# Persistent on-disk paths. Single-file events (JSONL append) + single-file
# checkpoint, both keyed by the lending-market PDA so two-market scans can't
# collide. The final parquet is rebuilt from the JSONL at end-of-run.
EVENTS_JSONL = DATA_PROCESSED / "kamino_liquidations_events.jsonl"
CHECKPOINT = DATA_PROCESSED / "kamino_liquidations_checkpoint.json"
EVENTS_PARQUET = DATA_PROCESSED / "kamino_liquidations.parquet"
SUMMARY_JSON = DATA_PROCESSED / "kamino_liquidations.summary.json"


def rpc_batch_dual(
    calls: list[tuple[str, list]],
    *,
    max_concurrent: int = 48,
    soft_fail: bool = True,
) -> tuple[list, list[int]]:
    """Fan out RPC calls across BOTH Helius and RPC Fast for ~2× throughput.

    Each call is round-robin assigned to a provider; ``rpc()``'s per-provider
    ``_RateLimiter`` independently throttles each bucket. Net per-second cap
    is therefore ~9 (Helius) + ~14 (RPC Fast) = ~23 calls/sec, vs. ~9 with
    single-provider ``rpc_batch``.

    ``soft_fail=True`` (default) returns ``None`` for any individual call
    that fails after retries, so a single transient 429 doesn't abort a
    multi-hour run. Failed-call indices are returned so the caller can log /
    re-issue them. Set ``soft_fail=False`` to mirror ``rpc_batch``'s
    all-or-nothing semantics.
    """
    if not calls:
        return [], []
    results: list = [None] * len(calls)
    failed: list[int] = []
    workers = min(max_concurrent, len(calls))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = []
        for i, (method, params) in enumerate(calls):
            provider = "helius" if i % 2 == 0 else "rpcfast"
            futures.append((i, ex.submit(rpc, method, params, provider=provider)))
        for i, fut in futures:
            try:
                results[i] = fut.result()
            except Exception as e:
                failed.append(i)
                if not soft_fail:
                    raise RuntimeError(
                        f"concurrent dual-RPC error id={i} method={calls[i][0]}: {e}"
                    ) from e
    return results, failed


def _read_checkpoint() -> dict:
    """Return the current checkpoint, or an empty dict if no checkpoint file
    exists. Schema: {"market": <pda>, "last_processed_sig": <sig>,
    "last_processed_block_time": <ts>, "n_events": N, "updated_at": iso}."""
    if not CHECKPOINT.exists():
        return {}
    try:
        return json.loads(CHECKPOINT.read_text())
    except Exception:
        return {}


def _write_checkpoint(market: str, last_sig: str, last_block_time: Optional[int],
                      n_events: int) -> None:
    CHECKPOINT.write_text(json.dumps({
        "market": market,
        "last_processed_sig": last_sig,
        "last_processed_block_time": last_block_time,
        "n_events": n_events,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }, indent=2))


def _append_events_jsonl(events: list[dict]) -> None:
    """Append-flush events into the JSONL panel. One JSON object per line so
    a downstream reader can stream row-by-row and a partial run is always
    consistent — the worst-case loss on SIGKILL is one in-flight batch."""
    if not events:
        return
    with EVENTS_JSONL.open("a") as f:
        for ev in events:
            f.write(json.dumps(ev, default=str) + "\n")


def _load_events_from_jsonl() -> list[dict]:
    """Read all events from the JSONL panel (idempotent, safe on partial)."""
    if not EVENTS_JSONL.exists():
        return []
    rows: list[dict] = []
    with EVENTS_JSONL.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _load_reserve_map() -> tuple[str, dict[str, dict]]:
    """Return (xstocks_market_pda, {reserve_pda: {symbol, decimals, ltv, liq}})
    from the latest reserve snapshot. Aborts if the snapshot disagrees with
    the hard-coded market constant.
    """
    candidates = sorted(DATA_PROCESSED.glob("kamino_xstocks_snapshot_*.json"), reverse=True)
    if not candidates:
        raise SystemExit(
            "No reserve snapshot found. Run scripts/snapshot_kamino_xstocks.py first."
        )
    snap = json.loads(candidates[0].read_text())
    market_pdas = {r["lending_market"] for r in snap["reserves"]}
    if len(market_pdas) != 1:
        raise SystemExit(
            f"Reserve snapshot spans {len(market_pdas)} markets; need single-market: {market_pdas}"
        )
    market_pda = next(iter(market_pdas))
    if market_pda != XSTOCKS_MARKET:
        raise SystemExit(
            f"Snapshot market {market_pda} != hard-coded XSTOCKS_MARKET {XSTOCKS_MARKET}"
        )
    reserve_map = {
        r["reserve_pda"]: {
            "symbol": r["symbol"],
            "decimals": r["liquidity_mint_decimals"],
            "ltv": r["config"]["loan_to_value_pct"],
            "liq": r["config"]["liquidation_threshold_pct"],
        }
        for r in snap["reserves"]
    }
    return market_pda, reserve_map


def _decode_klend_ix(ix: dict) -> Optional[dict]:
    """Inspect one parsed instruction; return decoded liquidation args or None.

    Expects jsonParsed encoding for non-Anchor-recognized programs:
      {"programId": "<pubkey>", "accounts": ["<pubkey>", ...], "data": "<b58>"}
    """
    if ix.get("programId") != KLEND_PROGRAM:
        return None
    data_b58 = ix.get("data")
    if not data_b58:
        return None
    try:
        raw = base58.b58decode(data_b58)
    except Exception:
        return None
    if len(raw) < 8 + 24:
        return None
    disc = raw[:8]
    if disc == LIQUIDATE_V1_DISC:
        version = "v1"
    elif disc == LIQUIDATE_V2_DISC:
        version = "v2"
    else:
        return None
    liquidity_amount = int.from_bytes(raw[8:16], "little")
    min_received = int.from_bytes(raw[16:24], "little")
    max_ltv_override = int.from_bytes(raw[24:32], "little")

    accs = ix.get("accounts") or []
    if len(accs) <= ACC_WITHDRAW_RESERVE:
        return None
    return {
        "ix_version": version,
        "liquidator": accs[ACC_LIQUIDATOR],
        "obligation": accs[ACC_OBLIGATION],
        "lending_market": accs[ACC_LENDING_MARKET],
        "repay_reserve": accs[ACC_REPAY_RESERVE],
        "withdraw_reserve": accs[ACC_WITHDRAW_RESERVE],
        "liquidity_amount_lamports": liquidity_amount,
        "min_acceptable_received_liquidity_amount": min_received,
        "max_allowed_ltv_override_pct": max_ltv_override,
    }


def _walk_instructions(tx: dict) -> Iterable[dict]:
    """Yield every (top-level + inner) instruction in a jsonParsed tx."""
    if not tx:
        return
    msg = (tx.get("transaction") or {}).get("message") or {}
    for ix in msg.get("instructions") or []:
        yield ix
    for inner in (tx.get("meta") or {}).get("innerInstructions") or []:
        for ix in inner.get("instructions") or []:
            yield ix


def _collect_signatures(
    market_pda: str,
    min_block_time: Optional[int],
    max_pages: int,
    page_size: int,
    verbose: bool,
    before_sig: Optional[str] = None,
) -> list[dict]:
    """Page through getSignaturesForAddress and return raw sig records,
    bounded by ``min_block_time`` (Unix seconds) and ``max_pages``.

    ``before_sig`` (when set) starts pagination *immediately before* the
    given signature — i.e., resumes a previously-interrupted scan from the
    checkpoint without re-walking the already-processed prefix. The cursor
    advances explicitly here (rather than via ``paginate_signatures``) so
    the per-page-size budget can be enforced before the first page returns.
    Failed sigs (``err`` set) are dropped — they can't contain a successful
    liquidation IX.
    """
    sigs: list[dict] = []
    page = 0
    cursor: Optional[str] = before_sig
    while True:
        batch = get_signatures_for_address(
            market_pda, before=cursor, limit=page_size
        )
        if not batch:
            break
        # Apply min_block_time cutoff before logging; sigs older than the
        # floor terminate the walk.
        stop = False
        for sig in batch:
            if sig.get("err") is not None:
                continue
            if min_block_time is not None and sig.get("blockTime") is not None:
                if sig["blockTime"] < min_block_time:
                    stop = True
                    break
            sigs.append(sig)
        page += 1
        if verbose:
            bt = batch[-1].get("blockTime")
            stamp = (
                datetime.fromtimestamp(bt, tz=timezone.utc).isoformat() if bt else "?"
            )
            print(f"  page {page}: {len(sigs)} sigs collected (last blockTime {stamp})",
                  flush=True)
        if stop:
            break
        if len(batch) < page_size:
            break
        if page >= max_pages:
            if verbose:
                print(f"  hit --max-pages {max_pages}; stopping pagination", flush=True)
            break
        cursor = batch[-1]["signature"]
    return sigs


def _decode_one_tx(s: dict, tx: Optional[dict], reserve_map: dict[str, dict],
                   market_pda: str) -> list[dict]:
    """Pure decoder: given a (sig record, tx) pair, return zero or more
    liquidation event rows. Extracted from the scan loop so retry/replay
    paths share one implementation."""
    if not tx:
        return []
    if (tx.get("meta") or {}).get("err") is not None:
        return []
    out: list[dict] = []
    for ix in _walk_instructions(tx):
        event = _decode_klend_ix(ix)
        if event is None:
            continue
        if event["lending_market"] != market_pda:
            continue
        repay_meta = reserve_map.get(event["repay_reserve"], {})
        withdraw_meta = reserve_map.get(event["withdraw_reserve"], {})
        repay_decimals = repay_meta.get("decimals")
        liquidity_amount_human = (
            event["liquidity_amount_lamports"] / (10 ** repay_decimals)
            if repay_decimals is not None
            else None
        )
        out.append({
            "signature": s["signature"],
            "slot": s.get("slot"),
            "block_time": s.get("blockTime"),
            "block_time_iso": (
                datetime.fromtimestamp(s["blockTime"], tz=timezone.utc).isoformat()
                if s.get("blockTime")
                else None
            ),
            "ix_version": event["ix_version"],
            "liquidator": event["liquidator"],
            "obligation": event["obligation"],
            "repay_reserve": event["repay_reserve"],
            "repay_symbol": repay_meta.get("symbol", "?"),
            "repay_decimals": repay_decimals,
            "withdraw_reserve": event["withdraw_reserve"],
            "withdraw_symbol": withdraw_meta.get("symbol", "?"),
            "withdraw_decimals": withdraw_meta.get("decimals"),
            "liquidity_amount_lamports": event["liquidity_amount_lamports"],
            "liquidity_amount_human": liquidity_amount_human,
            "min_acceptable_received_liquidity_amount": event[
                "min_acceptable_received_liquidity_amount"
            ],
            "max_allowed_ltv_override_pct": event["max_allowed_ltv_override_pct"],
        })
    return out


def _fetch_and_decode(
    sigs: list[dict],
    reserve_map: dict[str, dict],
    market_pda: str,
    batch_size: int,
    verbose: bool,
    use_dual_provider: bool,
    n_existing_events: int,
) -> list[dict]:
    """Resolve each sig to a transaction, decode liquidation IXs, and return
    enriched event rows.

    Incremental write contract:
      - Every batch's events are appended to ``EVENTS_JSONL`` *before*
        returning, so a SIGKILL between batches loses at most one in-flight
        batch's tx fetches (no decoded events).
      - The checkpoint is updated to the LAST sig in the just-completed
        batch (i.e., the oldest sig of the batch in pagination order).
        Resuming with ``before=<checkpoint_sig>`` reissues from there.

    Provider routing:
      - ``use_dual_provider=True`` round-robins each call across Helius and
        RPC Fast for ~2× net throughput.
      - ``False`` uses the single-provider ``rpc_batch`` (default
        ``PRIMARY_RPC``).
    """
    tx_opts = {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
    events: list[dict] = []
    n_inspected = 0
    n_failed_total = 0
    t_batch_start = time.time()
    n_total_events = n_existing_events
    for chunk_start in range(0, len(sigs), batch_size):
        chunk = sigs[chunk_start : chunk_start + batch_size]
        calls = [("getTransaction", [s["signature"], tx_opts]) for s in chunk]

        if use_dual_provider:
            txs, failed_idxs = rpc_batch_dual(calls, soft_fail=True)
        else:
            try:
                txs = rpc_batch(calls)
                failed_idxs = []
            except Exception as e:
                if verbose:
                    print(f"  rpc_batch failed ({type(e).__name__}: {e}); falling back per-tx",
                          flush=True)
                txs, failed_idxs = [], []
                for s in chunk:
                    try:
                        txs.append(get_transaction(s["signature"]))
                    except Exception:
                        txs.append(None)
                        failed_idxs.append(len(txs) - 1)

        if failed_idxs:
            n_failed_total += len(failed_idxs)
            if verbose:
                print(f"  batch {chunk_start//batch_size}: {len(failed_idxs)} failed calls "
                      f"(soft-fail, total failures so far: {n_failed_total})",
                      flush=True)

        batch_events: list[dict] = []
        for s, tx in zip(chunk, txs):
            n_inspected += 1
            batch_events.extend(_decode_one_tx(s, tx, reserve_map, market_pda))

        # Append THIS batch's events to JSONL atomically (one write call) and
        # update the checkpoint. Both happen before we move to the next
        # batch so a kill between batches is recoverable.
        if batch_events:
            _append_events_jsonl(batch_events)
            events.extend(batch_events)
            n_total_events += len(batch_events)
        # Always advance the checkpoint, even on a 0-event batch — pagination
        # progress is what we care about. last sig in chunk = oldest in
        # pagination order = the cursor a resume should continue from.
        last_sig = chunk[-1]["signature"]
        last_bt = chunk[-1].get("blockTime")
        _write_checkpoint(market_pda, last_sig, last_bt, n_total_events)

        if verbose and (chunk_start // batch_size) % 4 == 0:
            elapsed = time.time() - t_batch_start
            rate = n_inspected / elapsed if elapsed > 0 else 0
            eta_secs = (len(sigs) - n_inspected) / rate if rate > 0 else 0
            print(f"  inspected {n_inspected}/{len(sigs)} txs at {rate:.1f} req/s "
                  f"(eta {eta_secs/60:.1f} min); events this run: {len(events)}, "
                  f"total panel: {n_total_events}",
                  flush=True)
    return events


def _summarize(events: list[dict]) -> dict:
    """Cross-event aggregates Paper 3 cares about."""
    if not events:
        return {
            "n_events": 0,
            "n_unique_obligations": 0,
            "n_unique_liquidators": 0,
            "by_collateral_symbol": {},
            "by_debt_symbol": {},
            "by_ix_version": {},
            "by_weekend": {},
            "earliest_block_time": None,
            "latest_block_time": None,
        }
    obligations = {e["obligation"] for e in events}
    liquidators = {e["liquidator"] for e in events}
    by_collateral = Counter(e["withdraw_symbol"] for e in events)
    by_debt = Counter(e["repay_symbol"] for e in events)
    by_version = Counter(e["ix_version"] for e in events)

    # weekend bucket: Friday 20:00 UTC → Monday 13:30 UTC. Anything else is
    # "weekday". Stylized but matches the V5-tape window definition.
    def _is_weekend(ts: Optional[int]) -> bool:
        if ts is None:
            return False
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        # Monday=0..Sunday=6. Saturday=5, Sunday=6 always weekend.
        if dt.weekday() in (5, 6):
            return True
        # Friday after 20:00 UTC → weekend regime (US market closed).
        if dt.weekday() == 4 and dt.hour >= 20:
            return True
        # Monday before 13:30 UTC → weekend regime (US market not yet open).
        if dt.weekday() == 0 and (dt.hour, dt.minute) < (13, 30):
            return True
        return False

    weekend_count = sum(1 for e in events if _is_weekend(e.get("block_time")))
    block_times = [e["block_time"] for e in events if e.get("block_time") is not None]
    return {
        "n_events": len(events),
        "n_unique_obligations": len(obligations),
        "n_unique_liquidators": len(liquidators),
        "by_collateral_symbol": dict(by_collateral),
        "by_debt_symbol": dict(by_debt),
        "by_ix_version": dict(by_version),
        "by_weekend": {
            "n_weekend": weekend_count,
            "n_weekday": len(events) - weekend_count,
            "weekend_share": weekend_count / len(events) if events else 0.0,
        },
        "earliest_block_time": min(block_times) if block_times else None,
        "latest_block_time": max(block_times) if block_times else None,
    }


def _print_human_summary(summary: dict, scan_meta: dict) -> None:
    n_sigs = scan_meta.get("n_sigs_this_run", scan_meta.get("n_sigs", 0))
    print(f"\nScan window: last {scan_meta['days_back']} days "
          f"(min_block_time={scan_meta['min_block_time']})  "
          f"sigs this run: {n_sigs}, "
          f"events on disk: {summary['n_events']}")
    if summary["n_events"] == 0:
        return
    print(f"  unique obligations liquidated: {summary['n_unique_obligations']}")
    print(f"  unique liquidator addresses:   {summary['n_unique_liquidators']}")
    if summary["earliest_block_time"]:
        ear = datetime.fromtimestamp(summary["earliest_block_time"], tz=timezone.utc).isoformat()
        lat = datetime.fromtimestamp(summary["latest_block_time"], tz=timezone.utc).isoformat()
        print(f"  block_time range: {ear} → {lat}")
    print(f"  ix versions: {summary['by_ix_version']}")
    print(f"  weekend share: {summary['by_weekend']['n_weekend']}/{summary['n_events']} "
          f"({summary['by_weekend']['weekend_share']:.1%})")
    print(f"  by collateral seized (withdraw_reserve symbol):")
    for sym, n in sorted(summary["by_collateral_symbol"].items(), key=lambda kv: -kv[1]):
        print(f"    {sym:>7}: {n}")
    print(f"  by debt repaid (repay_reserve symbol):")
    for sym, n in sorted(summary["by_debt_symbol"].items(), key=lambda kv: -kv[1]):
        print(f"    {sym:>7}: {n}")


def _consolidate_jsonl_to_parquet() -> int:
    """Read every event ever appended to the JSONL panel, dedupe by
    signature (a single liquidation tx contains exactly one matching IX in
    practice; multi-IX edge cases keep distinct signatures), and write the
    final parquet. Returns the row count.
    """
    rows = _load_events_from_jsonl()
    if not rows:
        return 0
    df = pd.DataFrame(rows)
    # De-dup by signature in case an interrupted scan re-decoded a sig that
    # was already in the JSONL. Keep the first occurrence (chronologically
    # earliest write).
    df = df.drop_duplicates(subset=["signature"], keep="first")
    df = df.sort_values("block_time", na_position="last")
    df.to_parquet(EVENTS_PARQUET, index=False)
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days-back",
        type=int,
        default=30,
        help="Lower bound (days from now) on signature blockTime. Default 30.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Hard cap on signature pages to walk (each page = page-size sigs). Default 50.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=1000,
        help="getSignaturesForAddress page size (max 1000 per Helius docs).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=80,
        help="getTransaction calls per wave. Default 80 — empirically the "
             "best (batch_size, max_concurrent=48) cell on the dual-provider "
             "throughput sweep with HTTP keep-alive enabled (~8 sigs/s).",
    )
    parser.add_argument(
        "--single-provider",
        action="store_true",
        help="Disable dual-provider routing; use only PRIMARY_RPC at ~9 req/s. "
             "Default uses both Helius + RPC Fast for ~2× throughput.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the checkpoint at data/processed/kamino_liquidations_checkpoint.json. "
             "Pagination starts immediately before the checkpointed signature; "
             "the JSONL panel is appended to in-place.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="DELETE the existing JSONL panel + checkpoint before scanning. "
             "Use to start a clean scan from scratch.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    market_pda, reserve_map = _load_reserve_map()
    print(f"xStocks market: {market_pda}")
    print(f"Reserves in market: {len(reserve_map)} ({', '.join(sorted({m['symbol'] for m in reserve_map.values()}))})")

    if args.reset:
        for p in (EVENTS_JSONL, CHECKPOINT, EVENTS_PARQUET, SUMMARY_JSON):
            if p.exists():
                p.unlink()
                print(f"  reset: removed {p}")

    # Resume cursor: when --resume is set, paginate strictly before the
    # checkpointed sig so we don't re-walk completed pages. The min_block_time
    # floor still applies on top, so a resume can be combined with a tighter
    # --days-back to do a "fill the next slice" scan.
    before_sig: Optional[str] = None
    n_existing_events = 0
    if args.resume:
        ck = _read_checkpoint()
        if not ck:
            print("--resume requested but no checkpoint found; starting fresh.")
        elif ck.get("market") != market_pda:
            raise SystemExit(
                f"Checkpoint market {ck.get('market')} != target market {market_pda}; "
                "refusing to resume into the wrong market. Use --reset to clear."
            )
        else:
            before_sig = ck["last_processed_sig"]
            n_existing_events = ck.get("n_events", 0)
            print(f"Resuming from checkpoint: before_sig={before_sig[:16]}…, "
                  f"prior events on disk: {n_existing_events}")

    min_block_time = (
        int((datetime.now(tz=timezone.utc) - timedelta(days=args.days_back)).timestamp())
        if args.days_back > 0
        else None
    )
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    print(f"Walking signatures (days_back={args.days_back}, "
          f"max_pages={args.max_pages}, page_size={args.page_size}, "
          f"before={before_sig[:16]+'…' if before_sig else 'now'})…")
    t0 = time.time()
    sigs = _collect_signatures(
        market_pda=market_pda,
        min_block_time=min_block_time,
        max_pages=args.max_pages,
        page_size=args.page_size,
        verbose=args.verbose,
        before_sig=before_sig,
    )
    print(f"Collected {len(sigs)} signatures in {time.time()-t0:.1f}s")

    if not sigs:
        print("No signatures in window — nothing to do.")
        return

    use_dual = not args.single_provider
    print(f"Decoding {len(sigs)} transactions, batch_size={args.batch_size}, "
          f"providers={'helius+rpcfast' if use_dual else 'single'}…")
    t1 = time.time()
    events = _fetch_and_decode(
        sigs=sigs,
        reserve_map=reserve_map,
        market_pda=market_pda,
        batch_size=args.batch_size,
        verbose=args.verbose,
        use_dual_provider=use_dual,
        n_existing_events=n_existing_events,
    )
    elapsed = time.time() - t1
    rate = len(sigs) / elapsed if elapsed > 0 else 0
    print(f"Decoded {len(events)} new liquidation events from {len(sigs)} sigs "
          f"in {elapsed:.1f}s ({rate:.1f} sigs/s)")

    # Consolidate JSONL → parquet (includes any prior events on disk).
    n_total = _consolidate_jsonl_to_parquet()
    print(f"Consolidated panel → {EVENTS_PARQUET} ({n_total} total events on disk)")

    # Summarise the FULL panel (not just this run's new events), so the
    # summary reflects the cumulative state.
    all_events = _load_events_from_jsonl()
    summary = _summarize(all_events)
    scan_meta = {
        "scanned_at": datetime.now(tz=timezone.utc).isoformat(),
        "days_back": args.days_back,
        "max_pages": args.max_pages,
        "page_size": args.page_size,
        "batch_size": args.batch_size,
        "use_dual_provider": use_dual,
        "min_block_time": min_block_time,
        "n_sigs_this_run": len(sigs),
        "n_new_events_this_run": len(events),
        "n_total_events_on_disk": n_total,
        "klend_program": KLEND_PROGRAM,
        "lending_market": market_pda,
    }
    _print_human_summary(summary, scan_meta)

    SUMMARY_JSON.write_text(json.dumps({"scan": scan_meta, "summary": summary}, indent=2, default=str))
    print(f"\nWrote summary → {SUMMARY_JSON}")
    print(f"Events JSONL: {EVENTS_JSONL}  (append-only panel; safe to re-run with --resume)")


if __name__ == "__main__":
    main()
