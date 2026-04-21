"""
Yahoo Finance source for NYSE EOD and 1-minute intraday bars.

Used by:
  - V1 (Chainlink bias): daily bars → Friday close / Monday open per weekend
  - V2 (MS half-life):   1-min RTH bars, last ~60 days
  - V3 (funding signal): daily bars for underlyings + weekend-BTC + Friday sector ETFs
                         plus intraday for ES/NQ Sunday-evening return

yfinance limits, as-of April 2026:
  - 1-min bars: rolling 60-day window, max 7 days per request → chunked here
  - daily bars: no practical limit for our horizon
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import yfinance as yf

from ..cache import parquet_cached

_CORE_COLS = ["open", "high", "low", "close", "adj_close", "volume"]


def _download(
    tickers: Sequence[str],
    *,
    start: date | datetime,
    end: date | datetime,
    interval: str,
) -> pd.DataFrame:
    """Raw yfinance pull. End is exclusive in yfinance, so caller should pass the stop they want."""
    df = yf.download(
        tickers=list(tickers),
        start=start,
        end=end,
        interval=interval,
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if df.empty:
        raise RuntimeError(f"yfinance returned empty frame for tickers={list(tickers)} "
                           f"start={start} end={end} interval={interval}")
    return df


def _reshape(raw: pd.DataFrame, tickers: Sequence[str]) -> pd.DataFrame:
    """Normalise yfinance output (MultiIndex cols with single or multi ticker) to long-form."""
    if not isinstance(raw.columns, pd.MultiIndex):
        # Single-ticker case: yfinance returns flat cols.
        raw = raw.copy()
        raw.columns = pd.MultiIndex.from_product([[tickers[0]], raw.columns])

    rows: list[pd.DataFrame] = []
    top_level = set(raw.columns.get_level_values(0))
    for t in tickers:
        if t not in top_level:
            continue
        sub = raw[t].reset_index()
        sub.columns = [str(c).lower().replace(" ", "_") for c in sub.columns]
        sub = sub.rename(columns={"date": "ts", "datetime": "ts"})
        sub["symbol"] = t
        rows.append(sub)

    if not rows:
        raise RuntimeError(f"no rows after reshape: requested {list(tickers)}, got {sorted(top_level)}")

    out = pd.concat(rows, ignore_index=True)
    keep = ["symbol", "ts"] + [c for c in _CORE_COLS if c in out.columns]
    return out[keep].dropna(subset=["open", "close"]).reset_index(drop=True)


def fetch_daily(tickers: Sequence[str], start: date, end: date) -> pd.DataFrame:
    """Daily OHLCV, long-form: symbol, ts (date), open, high, low, close, adj_close, volume.

    `end` is inclusive from the caller's perspective — we add 1 day for yfinance's exclusive end.
    """
    key = {"tickers": sorted(tickers), "start": str(start), "end": str(end), "kind": "daily"}

    def _go() -> pd.DataFrame:
        raw = _download(tickers, start=start, end=end + timedelta(days=1), interval="1d")
        df = _reshape(raw, tickers)
        df["ts"] = pd.to_datetime(df["ts"]).dt.date
        return df

    return parquet_cached("yahoo", key, _go)


def fetch_minutes(tickers: Sequence[str], *, days: int = 60) -> pd.DataFrame:
    """1-minute bars for the last `days` calendar days. Chunks 7 days per request (yfinance limit)."""
    end = datetime.now(UTC).replace(tzinfo=None)
    start = end - timedelta(days=days)
    key = {"tickers": sorted(tickers), "days": days, "end": end.strftime("%Y-%m-%d")}

    def _go() -> pd.DataFrame:
        chunks: list[pd.DataFrame] = []
        cursor = start
        step = timedelta(days=7)
        while cursor < end:
            stop = min(cursor + step, end)
            raw = _download(tickers, start=cursor, end=stop, interval="1m")
            chunks.append(_reshape(raw, tickers))
            cursor = stop
        df = pd.concat(chunks, ignore_index=True).drop_duplicates(["symbol", "ts"])
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df.sort_values(["symbol", "ts"]).reset_index(drop=True)

    return parquet_cached("yahoo", key, _go)


def weekend_pairs(daily: pd.DataFrame, min_gap_days: int = 3) -> pd.DataFrame:
    """For each symbol, consecutive trading-day pairs separated by >= `min_gap_days` calendar days.

    `min_gap_days=3` captures Fri→Mon (standard weekend). Setting to 3 also catches Fri→Tue long
    weekends naturally. Output columns: symbol, fri_ts, fri_close, mon_ts, mon_open, gap_days.
    """
    rows: list[dict] = []
    for sym, grp in daily.sort_values("ts").groupby("symbol", sort=False):
        g = grp.reset_index(drop=True)
        ts = pd.to_datetime(g["ts"])
        gaps = ts.diff().dt.days
        for i in range(1, len(g)):
            gap = gaps.iloc[i]
            if pd.isna(gap) or gap < min_gap_days:
                continue
            rows.append(
                {
                    "symbol": sym,
                    "fri_ts": g.at[i - 1, "ts"],
                    "fri_close": float(g.at[i - 1, "close"]),
                    "mon_ts": g.at[i, "ts"],
                    "mon_open": float(g.at[i, "open"]),
                    "gap_days": int(gap),
                }
            )
    return pd.DataFrame(rows)
