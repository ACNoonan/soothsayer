"""
V5 tape daemon — continuous Chainlink xStock mid vs Jupiter DEX mid.

Polls at POLL_INTERVAL_S cadence (default 60 s) and writes daily parquet
partitions to data/raw/v5_tape_YYYYMMDD.parquet. Buffered in memory and
flushed every FLUSH_INTERVAL_S (default 600 s) to keep I/O sane; also
flushed at day rollover and at SIGINT.

Feeds the Phase 1 Week 3 xStock-specific residual overlay (per
`docs/v5-tape.md` axes 3 and 4) and the V2.1 F_tok forecaster
(`docs/v2.md`). Need ≥ ~1 month of tape before the overlay calibration
fits anything stable — so start this early, let it run.

Run with unbuffered stdout so the monitor can follow progress:

    PYTHONUNBUFFERED=1 uv run python scripts/run_v5_tape.py

Or in the background:

    nohup uv run python -u scripts/run_v5_tape.py > /tmp/v5_tape.log 2>&1 &
"""

from __future__ import annotations

import math
import signal
import sys
import time
from datetime import UTC, datetime, timezone
from pathlib import Path

import pandas as pd

from soothsayer.chainlink.scraper import fetch_latest_per_xstock
from soothsayer.config import DATA_RAW
from soothsayer.sources import jupiter


POLL_INTERVAL_S = 60                  # one tick per minute
FLUSH_INTERVAL_S = 600                # flush buffered rows every 10 minutes
CL_LOOKBACK_HOURS = 0.25              # 15 min — small enough to be cheap, big enough for gaps
JUP_SLIPPAGE_BPS = 50
JUP_SHARES = 1.0
TAPE_DIR = DATA_RAW


def _partition_path(ts: float) -> Path:
    d = datetime.fromtimestamp(ts, UTC).strftime("%Y%m%d")
    return TAPE_DIR / f"v5_tape_{d}.parquet"


def _poll_once(symbols: list[str], verbose: bool) -> list[dict]:
    """Run one poll tick for every symbol. Returns rows (one per symbol, errors included)."""
    poll_ts = int(time.time())

    # --- Chainlink: single batched call, latest-per-xStock in the lookback window.
    cl_err = ""
    try:
        cl_latest = fetch_latest_per_xstock(
            end_ts=poll_ts,
            lookback_hours=CL_LOOKBACK_HOURS,
            target_symbols=set(symbols),
            verbose=False,
        )
    except Exception as e:
        cl_err = f"{type(e).__name__}: {e}"
        cl_latest = {}

    rows: list[dict] = []
    for sym in symbols:
        cl_obs = cl_latest.get(sym)
        row: dict = {
            "poll_ts": poll_ts,
            "symbol": sym,
            "cl_obs_ts": cl_obs["obs_ts"] if cl_obs else None,
            "cl_age_s": (poll_ts - cl_obs["obs_ts"]) if cl_obs else None,
            "cl_tokenized_px": float(cl_obs["tokenized_price"]) if cl_obs else None,
            "cl_venue_px": float(cl_obs["price"]) if cl_obs else None,
            "cl_market_status": int(cl_obs["market_status"]) if cl_obs else None,
            "cl_err": cl_err if cl_obs is None else "",
        }

        # --- Jupiter: two-sided mid for this symbol.
        try:
            bid, ask, mid = jupiter.xstock_two_sided_mid_usdc(sym, shares=JUP_SHARES)
            row["jup_bid"] = float(bid)
            row["jup_ask"] = float(ask)
            row["jup_mid"] = float(mid)
            row["spread_bp"] = float((math.log(ask) - math.log(bid)) * 1e4) if bid > 0 else None
            row["jup_err"] = ""
        except Exception as e:
            row["jup_bid"] = None
            row["jup_ask"] = None
            row["jup_mid"] = None
            row["spread_bp"] = None
            row["jup_err"] = f"{type(e).__name__}: {e}"

        # Basis only if both sides present.
        if row["cl_tokenized_px"] and row["jup_mid"]:
            row["basis_bp"] = float((math.log(row["jup_mid"]) - math.log(row["cl_tokenized_px"])) * 1e4)
        else:
            row["basis_bp"] = None

        rows.append(row)

        if verbose:
            basis = f"{row['basis_bp']:+7.1f}bp" if row["basis_bp"] is not None else "    NaN "
            cl_mark = f"{row['cl_tokenized_px']:8.3f}" if row["cl_tokenized_px"] else "      -- "
            jup_mid = f"{row['jup_mid']:8.3f}" if row["jup_mid"] else "      -- "
            age = f"{row['cl_age_s']:3d}s" if row["cl_age_s"] is not None else "  -- "
            err_flag = ""
            if row["cl_err"] and row["jup_err"]:
                err_flag = " [BOTH ERR]"
            elif row["cl_err"]:
                err_flag = f" [CL: {row['cl_err'][:40]}]"
            elif row["jup_err"]:
                err_flag = f" [JUP: {row['jup_err'][:40]}]"
            ts_str = datetime.fromtimestamp(poll_ts, UTC).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  {ts_str} {sym:<6} cl={cl_mark} jup={jup_mid} basis={basis} age={age}{err_flag}")

    return rows


def _flush(buffer: list[dict], verbose: bool) -> list[dict]:
    """Write buffered rows to daily parquet partitions. Returns empty list (new buffer)."""
    if not buffer:
        return []
    TAPE_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(buffer)
    # Partition by day-of-poll_ts; a single flush may span a day boundary.
    df["_day"] = pd.to_datetime(df["poll_ts"], unit="s", utc=True).dt.strftime("%Y%m%d")
    for day, sub in df.groupby("_day"):
        path = TAPE_DIR / f"v5_tape_{day}.parquet"
        sub_out = sub.drop(columns=["_day"]).reset_index(drop=True)
        if path.exists():
            # Append: read existing, concat, rewrite. Daily files stay small enough
            # (~300-500k rows max at 60s cadence × 8 symbols × 24h = 11.5k rows/day).
            existing = pd.read_parquet(path)
            final = pd.concat([existing, sub_out], ignore_index=True)
        else:
            final = sub_out
        final.to_parquet(path, index=False)
        if verbose:
            print(f"  [flush] appended {len(sub_out):,} rows → {path.name} (total {len(final):,})")
    return []


def main() -> int:
    symbols = sorted(jupiter.XSTOCK_MINTS.keys())
    print(f"V5 tape daemon starting.")
    print(f"  symbols:          {symbols}")
    print(f"  poll interval:    {POLL_INTERVAL_S}s")
    print(f"  flush interval:   {FLUSH_INTERVAL_S}s")
    print(f"  CL lookback:      {CL_LOOKBACK_HOURS}h")
    print(f"  output:           {TAPE_DIR}/v5_tape_YYYYMMDD.parquet")
    print()

    buffer: list[dict] = []
    last_flush = time.monotonic()
    stop_requested = False

    def _handle_sigint(signum, frame):
        nonlocal stop_requested
        stop_requested = True
        print("\n  [sigint] will flush and exit after current tick finishes")

    signal.signal(signal.SIGINT, _handle_sigint)

    tick = 0
    while not stop_requested:
        t0 = time.monotonic()
        try:
            rows = _poll_once(symbols, verbose=True)
            buffer.extend(rows)
        except Exception as e:
            print(f"  [tick error] {type(e).__name__}: {e}")

        now = time.monotonic()
        if (now - last_flush) >= FLUSH_INTERVAL_S:
            try:
                buffer = _flush(buffer, verbose=True)
                last_flush = now
            except Exception as e:
                print(f"  [flush error] {type(e).__name__}: {e}")

        tick += 1
        elapsed = time.monotonic() - t0
        sleep_for = max(0.0, POLL_INTERVAL_S - elapsed)
        if not stop_requested:
            time.sleep(sleep_for)

    # Final flush on exit.
    try:
        _flush(buffer, verbose=True)
    except Exception as e:
        print(f"  [final flush error] {type(e).__name__}: {e}")
    print(f"V5 tape daemon stopped after {tick} ticks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
