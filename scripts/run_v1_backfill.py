"""
Backfill failed weekends for V1.

After the main scrape, run this to retry weekends that failed on 429s. Reads the
existing parquet, identifies weekends with <8 rows, re-scrapes them with the new
retry logic (429 support), and rewrites the parquet.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from soothsayer.chainlink.scraper import fetch_latest_per_xstock
from soothsayer.config import DATA_PROCESSED
from soothsayer.sources.yahoo import fetch_daily, weekend_pairs
from soothsayer.universe import CORE_XSTOCKS

ET = ZoneInfo("America/New_York")
CHAINLINK_LAUNCH = date(2026, 2, 9)
PAUSE_BETWEEN_WEEKENDS = 10  # seconds — ease up on the rate limiter


def mon_open_ts(mon_date: date) -> int:
    dt_et = datetime.combine(mon_date, datetime.min.time(), tzinfo=ET).replace(hour=9, minute=30)
    return int(dt_et.astimezone(UTC).timestamp())


def main() -> None:
    parquet_path = DATA_PROCESSED / "v1_chainlink_vs_monday_open.parquet"
    existing = pd.read_parquet(parquet_path)
    print(f"existing rows: {len(existing)}, weekends: {sorted(existing['weekend_mon'].unique())}", flush=True)

    # Find which weekends are missing or incomplete
    syms = [x.underlying for x in CORE_XSTOCKS]
    underlying_to_xstock = {x.underlying: x.symbol for x in CORE_XSTOCKS}
    xstock_to_underlying = {s: u for u, s in underlying_to_xstock.items()}

    daily = fetch_daily(syms, start=date(2026, 1, 15), end=date.today())
    spy = daily[daily["symbol"] == "SPY"].sort_values("ts").reset_index(drop=True)
    pairs = weekend_pairs(spy)
    pairs = pairs[pairs["mon_ts"] >= CHAINLINK_LAUNCH].reset_index(drop=True)

    # count existing per weekend
    counts = existing.groupby("weekend_mon").size().to_dict() if len(existing) else {}
    todo = []
    for _, row in pairs.iterrows():
        n = counts.get(row["mon_ts"], 0)
        if n < 8:
            todo.append(row)
    print(f"weekends needing backfill: {len(todo)}", flush=True)
    for row in todo:
        print(f"  fri={row['fri_ts']} mon={row['mon_ts']} gap={row['gap_days']}d current={counts.get(row['mon_ts'], 0)}/8", flush=True)

    daily["ts"] = pd.to_datetime(daily["ts"]).dt.date
    fri_close = daily.set_index(["symbol", "ts"])["close"].to_dict()
    mon_open = daily.set_index(["symbol", "ts"])["open"].to_dict()

    new_rows: list[dict] = []
    for i, row in enumerate(todo):
        mon_date = row["mon_ts"]
        fri_date = row["fri_ts"]
        end_ts = mon_open_ts(mon_date)
        print(f"\n[{i+1}/{len(todo)}] fri={fri_date} mon={mon_date} gap={row['gap_days']}d", flush=True)
        try:
            latest = fetch_latest_per_xstock(
                end_ts, lookback_hours=36, use_rpc=True, verbose=True
            )
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}", flush=True)
            latest = {}
        for xsym, obs in latest.items():
            underlying = xstock_to_underlying[xsym]
            new_rows.append(
                {
                    "weekend_mon": mon_date,
                    "fri_ts": fri_date,
                    "gap_days": int(row["gap_days"]),
                    "symbol": xsym,
                    "underlying": underlying,
                    "fri_close": fri_close.get((underlying, fri_date)),
                    "mon_open": mon_open.get((underlying, mon_date)),
                    "cl_mid": obs["mid"],
                    "cl_last_traded": obs["last_traded"],
                    "cl_bid": obs["bid"],
                    "cl_ask": obs["ask"],
                    "cl_obs_ts": obs["obs_ts"],
                    "cl_minutes_before_open": (end_ts - obs["obs_ts"]) / 60,
                    "cl_signature": obs["signature"],
                }
            )
        print(f"  added {len(latest)}/8 xStocks", flush=True)
        if i < len(todo) - 1:
            print(f"  sleeping {PAUSE_BETWEEN_WEEKENDS}s before next weekend", flush=True)
            time.sleep(PAUSE_BETWEEN_WEEKENDS)

    # merge — replace any existing rows for weekends we re-scraped
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        touched_weekends = set(new_df["weekend_mon"])
        kept = existing[~existing["weekend_mon"].isin(touched_weekends)]
        combined = pd.concat([kept, new_df], ignore_index=True)
        combined = combined.sort_values(["weekend_mon", "symbol"]).reset_index(drop=True)
        combined.to_parquet(parquet_path)
        print(f"\nwrote {len(combined)} rows -> {parquet_path}", flush=True)
        print(f"per-symbol coverage: {combined.groupby('symbol').size().to_dict()}", flush=True)
    else:
        print("\nno new rows to merge", flush=True)


if __name__ == "__main__":
    main()
