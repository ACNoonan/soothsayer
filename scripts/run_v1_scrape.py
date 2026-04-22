"""
Driver for V1 data collection.

Pulls, for each market-closure window >=3 calendar days since Chainlink's xStock
equity launch (Jan 20 2026):

  - Yahoo daily OHLC for 8 xStock underlyings -> Friday close, Monday open
  - Chainlink `last Sunday` v10 observation per xStock via on-chain scrape

Writes a joined table to data/processed/v1_chainlink_vs_monday_open.parquet
with one row per (weekend, symbol).

Run: uv run python scripts/run_v1_scrape.py
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from soothsayer.chainlink.feeds import XSTOCK_FEEDS
from soothsayer.chainlink.scraper import fetch_latest_per_xstock
from soothsayer.config import DATA_PROCESSED
from soothsayer.sources.yahoo import fetch_daily, weekend_pairs
from soothsayer.universe import CORE_XSTOCKS

# Chainlink launched 24/5 equity Data Streams Jan 20 2026 (per CoinDesk), but on-chain
# probing shows xStock v10 traffic first appears on Solana around Feb 2-9. Use Feb 9 as
# the first Monday with confirmed coverage — probe yielded 13 xStock obs in 100 sigs.
CHAINLINK_LAUNCH = date(2026, 2, 9)
ET = ZoneInfo("America/New_York")


def monday_open_utc_ts(monday_date: date) -> int:
    """NYSE open on `monday_date` as a unix timestamp. Handles DST by delegating to zoneinfo."""
    dt_et = datetime.combine(monday_date, datetime.min.time(), tzinfo=ET).replace(
        hour=9, minute=30
    )
    return int(dt_et.astimezone(UTC).timestamp())


def main() -> None:
    syms = [x.underlying for x in CORE_XSTOCKS]  # SPY, QQQ, GOOGL, AAPL, NVDA, TSLA, MSTR, HOOD
    underlying_to_xstock = {x.underlying: x.symbol for x in CORE_XSTOCKS}
    print(f"universe: {syms}")

    print("\n-- pulling yfinance daily bars for 8 underlyings --")
    daily = fetch_daily(syms, start=date(2026, 1, 15), end=date.today())
    print(f"rows: {len(daily)}, symbols: {sorted(daily['symbol'].unique())}")

    # Build weekend pair list using SPY (same trading calendar for all 8)
    spy = daily[daily["symbol"] == "SPY"].sort_values("ts").reset_index(drop=True)
    pairs = weekend_pairs(spy)
    pairs = pairs[pairs["mon_ts"] >= CHAINLINK_LAUNCH].reset_index(drop=True)
    print(f"\n-- {len(pairs)} weekend pairs since Chainlink launch ({CHAINLINK_LAUNCH}) --")
    print(pairs[["fri_ts", "mon_ts", "gap_days"]].to_string(index=False))

    # Pivot daily into {symbol: date: (close, open)} for fast lookup
    daily["ts"] = pd.to_datetime(daily["ts"]).dt.date
    fri_close = daily.set_index(["symbol", "ts"])["close"].to_dict()
    mon_open = daily.set_index(["symbol", "ts"])["open"].to_dict()

    # Scrape Chainlink Sun-last per xStock per weekend
    import os
    use_rpc = os.environ.get("SCRAPE_MODE", "rpc").lower() == "rpc"
    print(f"scrape mode: {'RPC' if use_rpc else 'Enhanced API'}", flush=True)

    xstock_to_underlying = {s: u for u, s in underlying_to_xstock.items()}
    results: list[dict] = []
    t_start = time.monotonic()
    for i, row in pairs.iterrows():
        mon_date = row["mon_ts"]
        fri_date = row["fri_ts"]
        end_ts = monday_open_utc_ts(mon_date)
        print(
            f"\n[{i+1}/{len(pairs)}] fri={fri_date} mon={mon_date} gap={row['gap_days']}d "
            f"| mon_open_ts={end_ts}",
            flush=True,
        )
        try:
            latest = fetch_latest_per_xstock(
                end_ts, lookback_hours=36, use_rpc=use_rpc, verbose=True
            )
        except Exception as e:
            print(f"  weekend {mon_date} failed: {type(e).__name__}: {e}", flush=True)
            latest = {}
        for xsym, obs in latest.items():
            underlying = xstock_to_underlying[xsym]
            results.append(
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
        print(f"  found {len(latest)}/8 xStocks this weekend", flush=True)

    df = pd.DataFrame(results)
    print(f"\n-- {len(df)} (weekend, xStock) rows collected in {time.monotonic()-t_start:.1f}s --")
    print(f"per-symbol coverage: {df.groupby('symbol').size().to_dict()}")

    out = DATA_PROCESSED / "v1_chainlink_vs_monday_open.parquet"
    df.to_parquet(out)
    print(f"wrote -> {out}")


if __name__ == "__main__":
    main()
