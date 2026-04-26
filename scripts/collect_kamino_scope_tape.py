"""Forward-running Kamino-Scope tape — observe the price each xStock reserve
is actually consuming, every minute.

Phase 1 Week 3 / Step 2 of the real-data Kamino comparator. The V5 tape
daemon (``scripts/run_v5_tape.py``, running since 2026-04-24) already
captures Chainlink ``tokenizedPrice`` + Jupiter on-chain DEX quotes per
xStock per minute. This script adds the missing third leg: Kamino's
**Scope-served price**, i.e. the value Klend's `Reserve.tokenInfo` actually
reads when it computes LTV at any timestamp.

Free-tier observation paths the spec asked for that turned out NOT to work:

- Kraken xStock spot: Kraken does NOT list xStocks on spot (only perps,
  via the existing ``src/soothsayer/sources/kraken_perp.py``). Their public
  asset-pair list returns only HMSTR for our search terms.
- Bybit: geo-blocked from the US (CloudFront 403). Cannot poll without a
  non-US proxy or VPS, which is outside the free-tier constraint.

Free-tier paths that DO work (and are already captured by V5 tape):

- Jupiter on-chain DEX quote (the actual on-chain market for SPYx etc.)
- Chainlink Data Streams v10 ``tokenizedPrice`` (24/7 CEX-aggregated mark)
- Chainlink Data Streams v10 ``price`` (frozen Friday close — stale)

This daemon adds:

- Scope-served price per xStock from Kamino's actual oracle wiring,
  decoded from the on-chain ``OraclePrices`` PDA at chain indices read
  from the latest snapshot (``data/processed/kamino_xstocks_snapshot_*.json``).

All 8 xStocks share one Scope ``priceFeed`` PDA
(``3t4JZcueEzTbVP6kLxXrL3VpWx45jDer4eqysweBchNH``); differentiated only by
chain index. So we make exactly one ``getAccountInfo`` call per tick,
slice locally for all 8 prices.

Run modes:

- ``uv run python scripts/collect_kamino_scope_tape.py --once``
  — snapshot once and exit. Cron-friendly.
- ``PYTHONUNBUFFERED=1 nohup uv run python -u scripts/collect_kamino_scope_tape.py
  > /tmp/scope_tape.log 2>&1 &``
  — long-running daemon, 60s cadence, daily parquet rollover.

Output: ``data/raw/kamino_scope_tape_YYYYMMDD.parquet`` (daily partitions).
Schema: poll_ts, symbol, scope_value_raw, scope_exp, scope_price,
scope_unix_ts, scope_slot, scope_age_s, feed_pda, chain_id.
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from soothsayer.config import DATA_PROCESSED, DATA_RAW
from soothsayer.sources.helius import rpc

# Layout offsets in the OraclePrices account (after the 8-byte Anchor disc):
#   [0..8]    discriminator
#   [8..40]   oracleMappings: Pubkey (32 bytes)
#   [40..]    prices: [DatedPrice; 512]
#
# Each DatedPrice is 56 bytes:
#   [0..8]    price.value: u64
#   [8..16]   price.exp:   u64
#   [16..24]  lastUpdatedSlot: u64
#   [24..32]  unixTimestamp:   u64
#   [32..56]  genericData: [u8; 24]
ORACLE_PRICES_HEADER = 8 + 32  # 40 bytes
DATED_PRICE_SIZE = 56

POLL_INTERVAL_SECS_DEFAULT = 60
FLUSH_INTERVAL_SECS = 600


def latest_snapshot() -> dict:
    """Find the most recent kamino_xstocks_snapshot_*.json under data/processed/.
    Returns the parsed snapshot dict.
    """
    candidates = sorted(DATA_PROCESSED.glob("kamino_xstocks_snapshot_*.json"))
    if not candidates:
        raise SystemExit(
            "No Kamino snapshot found under data/processed/. Run:\n"
            "  uv run python scripts/snapshot_kamino_xstocks.py"
        )
    snapshot = json.loads(candidates[-1].read_text())
    print(f"Loaded snapshot {candidates[-1].name} "
          f"({snapshot['n_reserves']} reserves, taken {snapshot['snapshot_date']})")
    return snapshot


def build_chain_map(snapshot: dict) -> tuple[str, dict[str, int]]:
    """Return (shared price-feed PDA, {symbol: chain_id}). Asserts that all
    xStocks share one feed PDA (the snapshot from 2026-04-26 confirms this;
    if Kamino governance ever migrates to multiple feeds, this guard will
    fire and we extend to multi-feed reads).
    """
    feeds = {r["token_info"]["scope"]["price_feed"] for r in snapshot["reserves"]
             if r["token_info"]["scope"]["active"]}
    if len(feeds) != 1:
        raise SystemExit(
            f"Expected one Scope feed PDA across xStocks; found {len(feeds)}: {feeds}. "
            "Extend the daemon to fetch multiple OraclePrices accounts."
        )
    feed = feeds.pop()
    chain_map = {
        r["symbol"]: r["token_info"]["scope"]["price_chain"][0]
        for r in snapshot["reserves"]
        if r["token_info"]["scope"]["active"]
    }
    return feed, chain_map


def fetch_oracle_prices(feed_pda: str) -> bytes:
    """Single getAccountInfo for the shared OraclePrices PDA. Returns raw bytes."""
    res = rpc("getAccountInfo", [feed_pda, {"encoding": "base64"}])
    if not res or not res.get("value"):
        raise RuntimeError(f"empty getAccountInfo for {feed_pda}")
    return base64.b64decode(res["value"]["data"][0])


def decode_chain_slot(raw: bytes, chain_id: int) -> dict:
    """Decode the 56-byte DatedPrice at the given chain index."""
    start = ORACLE_PRICES_HEADER + chain_id * DATED_PRICE_SIZE
    end = start + DATED_PRICE_SIZE
    if end > len(raw):
        raise IndexError(f"chain_id {chain_id} OOB; account is {len(raw)} bytes")
    blob = raw[start:end]
    value, exp, slot, ts = struct.unpack_from("<QQQQ", blob, 0)
    # Real price is value / 10**exp.
    price = float(value) / (10 ** exp) if exp > 0 else float(value)
    return {
        "scope_value_raw": int(value),
        "scope_exp": int(exp),
        "scope_price": price,
        "scope_slot": int(slot),
        "scope_unix_ts": int(ts),
    }


def tick(feed_pda: str, chain_map: dict[str, int]) -> list[dict]:
    """Single observation across all xStocks. Returns one row per symbol."""
    poll_ts = datetime.now(timezone.utc).isoformat()
    poll_unix = int(time.time())
    raw = fetch_oracle_prices(feed_pda)
    rows: list[dict] = []
    for sym, chain in chain_map.items():
        try:
            slot = decode_chain_slot(raw, chain)
        except Exception as e:  # noqa: BLE001
            rows.append({
                "poll_ts": poll_ts, "symbol": sym, "feed_pda": feed_pda,
                "chain_id": chain, "scope_err": str(e),
            })
            continue
        slot["scope_age_s"] = poll_unix - slot["scope_unix_ts"] if slot["scope_unix_ts"] else None
        rows.append({
            "poll_ts": poll_ts,
            "symbol": sym,
            "feed_pda": feed_pda,
            "chain_id": chain,
            **slot,
            "scope_err": None,
        })
    return rows


def parquet_path_for(now: datetime) -> Path:
    """Daily-partitioned parquet file under data/raw/."""
    return DATA_RAW / f"kamino_scope_tape_{now.strftime('%Y%m%d')}.parquet"


def append_rows(buf: list[dict]) -> int:
    """Flush buffered rows to today's parquet file (read-modify-write to keep
    free-tier engineering simple; for high-cadence daemons this'd be a Parquet
    append writer, but at 1-min cadence the overhead is negligible)."""
    if not buf:
        return 0
    now = datetime.now(timezone.utc)
    target = parquet_path_for(now)
    target.parent.mkdir(parents=True, exist_ok=True)
    new_df = pd.DataFrame(buf)
    if target.exists():
        existing = pd.read_parquet(target)
        out = pd.concat([existing, new_df], ignore_index=True)
    else:
        out = new_df
    out.to_parquet(target, index=False)
    return len(new_df)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true",
                    help="snapshot once and exit (cron-friendly)")
    ap.add_argument("--interval", type=int, default=POLL_INTERVAL_SECS_DEFAULT,
                    help=f"poll interval seconds (default: {POLL_INTERVAL_SECS_DEFAULT})")
    args = ap.parse_args()

    snapshot = latest_snapshot()
    feed_pda, chain_map = build_chain_map(snapshot)
    print(f"Polling shared Scope feed: {feed_pda}")
    print(f"Chain ID map: {chain_map}")
    print(f"Mode: {'one-shot' if args.once else f'daemon @ {args.interval}s'}")

    if args.once:
        rows = tick(feed_pda, chain_map)
        n = append_rows(rows)
        for r in rows:
            print(f"  {r['symbol']:7s} ${r.get('scope_price', 'ERR'):>10}  "
                  f"age={r.get('scope_age_s', 'NA')}s  slot={r.get('scope_slot', 'NA')}")
        print(f"Wrote {n} rows to {parquet_path_for(datetime.now(timezone.utc))}")
        return

    # Daemon loop.
    buf: list[dict] = []
    last_flush = time.time()
    print(f"Daemon started; flushing every {FLUSH_INTERVAL_SECS}s. Ctrl-C to stop.")
    while True:
        try:
            rows = tick(feed_pda, chain_map)
            buf.extend(rows)
            print(f"  [{datetime.now(timezone.utc).isoformat()}] "
                  f"buffered +{len(rows)} (total {len(buf)})")
            now_t = time.time()
            if now_t - last_flush >= FLUSH_INTERVAL_SECS:
                n = append_rows(buf)
                print(f"  ⇒ flushed {n} rows to "
                      f"{parquet_path_for(datetime.now(timezone.utc)).name}")
                buf.clear()
                last_flush = now_t
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nInterrupted; flushing buffer before exit...")
            n = append_rows(buf)
            print(f"  flushed {n} rows; exiting.")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  [tick error] {e}; backing off 30s")
            time.sleep(30)


if __name__ == "__main__":
    main()
