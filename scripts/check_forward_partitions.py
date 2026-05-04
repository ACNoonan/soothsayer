"""
Forward-weekend partition presence pre-flight for the M6 LWC harness.

The SLA check (`check_scryer_freshness.py`) verifies that scryer's
runners completed *some* recent run within an SLA window. It does NOT
prove that the specific Friday-and-Monday partitions the forward
weekend needs have actually landed yet — those are written by per-day
runners on their own cadence, and on 2026-05-04 a 4-minute lag between
the harness fire and CME's `day=01.parquet` write caused the panel
build to silently drop the only forward weekend.

This script is the missing belt. It:

  1. Reads the frozen-artefact training cutoff (max `fri_ts` in
     `lwc_artefact_v1_frozen_*.parquet`).
  2. Derives the target `(fri_ts, mon_ts)` pair from SPY data: the
     latest gap-≥3 trading-day pair where `fri_ts > cutoff` and
     `mon_ts ≤ today`. SPY is the canonical anchor — if SPY itself
     hasn't closed the pair yet, no other equity will have either,
     and we should not even attempt a build.
  3. For that pair, verifies that every upstream `panel.build()`
     reads against has rows for the dates it joins on:
       * yahoo equities (CORE_XSTOCKS underlyings + RWA_ANCHORS):
         both fri_ts and mon_ts.
       * CME-or-yahoo blended futures (ES=F, NQ=F, GC=F, ZN=F): both
         fri_ts and mon_ts (panel joins fri_close + mon_open).
       * CBOE-or-yahoo blended VIX: fri_ts only (panel joins
         vix_fri_close).
       * yahoo BTC-USD: both fri_ts and mon_ts (used for MSTR factor
         post-2020-08).
       * yahoo ^GVZ, MOVE: fri_ts only (used for GLD/TLT vol_idx;
         falls back to VIX, so warn-only).
  4. If anything is missing, polls every `--poll-seconds` (default 30)
     up to `--max-wait-seconds` (default 900 = 15 min) for it to
     land. Most race conditions today are ≤ 5 minutes; 15 min covers
     the long tail of an upstream runner that's running late.

Exit codes:
  0 — all required partitions present, OR no forward weekend reachable
      yet (today's pair hasn't closed in SPY data — e.g., we're firing
      between Mon market open and Mon equity-daily upload). The
      collector handles a no-forward-weekend tape gracefully.
  1 — required partitions still missing after the wait budget. The
      wrapper script halts so we don't waste cycles building a panel
      we already know will drop the forward weekend; the next launchd
      fire will re-check.

Run
---
  uv run python scripts/check_forward_partitions.py
  uv run python scripts/check_forward_partitions.py --max-wait-seconds 1200
  uv run python scripts/check_forward_partitions.py --no-wait    # one-shot
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from soothsayer.backtest.panel import (
    BTC,
    FUTURES,
    GVZ,
    MOVE,
    RWA_ANCHORS,
    VIX,
    _load_one_symbol,
)
from soothsayer.config import DATA_PROCESSED
from soothsayer.universe import CORE_XSTOCKS


def _latest_frozen_cutoff() -> tuple[date, Path]:
    candidates = sorted(DATA_PROCESSED.glob("lwc_artefact_v1_frozen_*.parquet"))
    if not candidates:
        raise FileNotFoundError(
            "No frozen artefact found under "
            f"{DATA_PROCESSED}. Run scripts/freeze_lwc_artefact.py first."
        )
    frozen = candidates[-1]
    df = pd.read_parquet(frozen)
    cutoff = pd.to_datetime(df["fri_ts"]).dt.date.max()
    return cutoff, frozen


def _candidate_pair(cutoff: date, today: date) -> tuple[date, date] | None:
    """Latest (fri_ts, mon_ts) trading-day pair from SPY where
    `fri_ts > cutoff` and `mon_ts ≤ today`. Returns ``None`` if no such
    pair has closed yet — that's a legitimate "no forward weekend
    reachable yet" state and the wrapper should continue without
    failing."""
    df = _load_one_symbol("SPY", cutoff - timedelta(days=10), today)
    if df.empty:
        return None
    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"]).dt.date
    df = df.sort_values("ts").reset_index(drop=True)
    pairs: list[tuple[date, date]] = []
    for i in range(1, len(df)):
        prev_ts = df.at[i - 1, "ts"]
        cur_ts = df.at[i, "ts"]
        gap = (cur_ts - prev_ts).days
        if gap >= 3 and prev_ts > cutoff and cur_ts <= today:
            pairs.append((prev_ts, cur_ts))
    return pairs[-1] if pairs else None


def _equity_universe() -> list[str]:
    return [x.underlying for x in CORE_XSTOCKS] + list(RWA_ANCHORS)


def _missing_for_pair(fri: date, mon: date) -> tuple[list[str], list[str]]:
    """Return (hard_missing, soft_missing). A row in `hard_missing`
    blocks the harness — `panel.build()`'s dropna will cut the forward
    weekend without it. A row in `soft_missing` is a warn-only
    fallback path (vol-index series with a VIX fallback)."""
    hard: list[str] = []
    soft: list[str] = []

    # Wide-enough window so the loader's date-range filter doesn't trim
    # boundary rows.
    win_start = fri - timedelta(days=4)
    win_end = mon + timedelta(days=4)

    def have_rows(sym: str) -> set[date]:
        df = _load_one_symbol(sym, win_start, win_end)
        if df.empty:
            return set()
        return set(pd.to_datetime(df["ts"]).dt.date)

    # 1) Equities (yahoo only): fri AND mon
    for sym in _equity_universe():
        have = have_rows(sym)
        if fri not in have:
            hard.append(f"{sym}: missing fri={fri}")
        if mon not in have:
            hard.append(f"{sym}: missing mon={mon}")

    # 2) Futures (yahoo blended with CME): fri AND mon
    for sym in FUTURES:
        have = have_rows(sym)
        if fri not in have:
            hard.append(f"{sym}: missing fri={fri}")
        if mon not in have:
            hard.append(f"{sym}: missing mon={mon}")

    # 3) VIX (CBOE blended with yahoo): fri only
    have = have_rows(VIX)
    if fri not in have:
        hard.append(f"{VIX}: missing fri={fri}")

    # 4) BTC-USD (yahoo only): fri AND mon (used for MSTR post-2020 factor)
    have = have_rows(BTC)
    if fri not in have:
        hard.append(f"{BTC}: missing fri={fri}")
    if mon not in have:
        hard.append(f"{BTC}: missing mon={mon}")

    # 5) GVZ / MOVE (yahoo only): fri only, falls back to VIX → soft
    for sym in (GVZ, MOVE):
        have = have_rows(sym)
        if fri not in have:
            soft.append(f"{sym}: missing fri={fri} (vol-index; falls back to VIX)")

    return hard, soft


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-wait-seconds", type=int, default=900,
        help="Max time to wait for missing partitions to land "
             "(default 900 = 15 min).",
    )
    parser.add_argument(
        "--poll-seconds", type=int, default=30,
        help="Seconds between presence checks (default 30).",
    )
    parser.add_argument(
        "--no-wait", action="store_true",
        help="One-shot: do not poll, fail immediately if anything is missing.",
    )
    args = parser.parse_args()

    cutoff, frozen = _latest_frozen_cutoff()
    today = date.today()
    print(f"Frozen artefact: {frozen.name}")
    print(f"  training cutoff: {cutoff}")
    print(f"  today (local):   {today}")

    pair = _candidate_pair(cutoff, today)
    if pair is None:
        print(
            "No forward weekend reachable yet — SPY has no Fri/Mon pair "
            f"with fri > {cutoff} and mon ≤ {today}. The collector will "
            "produce a context-only tape; the next harness fire will "
            "re-check."
        )
        return 0

    fri, mon = pair
    print(f"Target forward weekend: fri={fri}  mon={mon}")

    deadline = time.monotonic() + (0 if args.no_wait else args.max_wait_seconds)
    iteration = 0
    while True:
        iteration += 1
        hard, soft = _missing_for_pair(fri, mon)

        if soft:
            for s in soft:
                print(f"  WARN: {s}")

        if not hard:
            print(f"All required partitions present (iter={iteration}).")
            return 0

        remaining = deadline - time.monotonic()
        if args.no_wait or remaining <= 0:
            print(
                f"FAIL: required partitions still missing"
                f"{'' if args.no_wait else f' after {args.max_wait_seconds}s'}:"
            )
            for h in hard:
                print(f"  - {h}")
            print(
                "Halting before the build to avoid silently dropping the "
                "forward weekend. The next harness fire will re-check."
            )
            return 1

        print(
            f"Iter {iteration}: {len(hard)} hard partition(s) missing; "
            f"sleeping {args.poll_seconds}s "
            f"(remaining budget: {int(remaining)}s)",
            flush=True,
        )
        for h in hard:
            print(f"  - {h}")
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
