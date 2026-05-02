#!/usr/bin/env python3
"""Regime decomposition probe (2026-05-01).

Tests the qualitative claim that off-hours oracle behavior decomposes
into three structurally distinct regimes — fully-closed weekend,
weeknight overnight (US closed but Asia/Europe live), and TRTH extended
hours — at the single-oracle level, against currently available scryer
tape.

The probe is intentionally lightweight; it produces a long-format
summary parquet under data/processed/ for follow-up. When the deeper
operator-side backfills (wishlist items 49a-d) land, re-run this same
script against the deeper tape — the regime split is the analysis
primitive, not the dataset.
"""
from __future__ import annotations

from datetime import time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from soothsayer.config import SCRYER_DATASET_ROOT

ET = ZoneInfo("America/New_York")
PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"
SUMMARY_OUT = PROCESSED / "regime_decomposition_probe_summary.parquet"
LEGACY_REDSTONE = PROCESSED / "redstone_live_tape.parquet"

WINDOW_ORDER = ["rth", "premarket", "afterhours", "overnight", "weekend"]

XSTOCK_TO_UNDERLIER = {
    "AAPLx": "AAPL", "GOOGLx": "GOOGL", "HOODx": "HOOD", "MSTRx": "MSTR",
    "NVDAx": "NVDA", "QQQx": "QQQ", "SPYx": "SPY", "TSLAx": "TSLA",
}


def classify_window(t: dtime, weekday0: int) -> str:
    if weekday0 >= 5:
        return "weekend"
    if dtime(9, 30) <= t < dtime(16, 0):
        return "rth"
    if dtime(4, 0) <= t < dtime(9, 30):
        return "premarket"
    if dtime(16, 0) <= t < dtime(20, 0):
        return "afterhours"
    return "overnight"


def to_utc(s: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(s):
        if s.dt.tz is None:
            return s.dt.tz_localize("UTC")
        return s.dt.tz_convert("UTC")
    if pd.api.types.is_integer_dtype(s):
        sample = int(s.dropna().iloc[0])
        unit = "ns" if sample > 1e16 else "us" if sample > 1e13 else "ms" if sample > 1e11 else "s"
        return pd.to_datetime(s, unit=unit, utc=True, errors="coerce")
    return pd.to_datetime(s, utc=True, errors="coerce")


def add_window(df: pd.DataFrame, ts_col: str) -> pd.DataFrame:
    ts_utc = to_utc(df[ts_col])
    et = ts_utc.dt.tz_convert(ET)
    df = df.copy()
    df["_ts_utc"] = ts_utc
    df["_window"] = [classify_window(t, w) for t, w in zip(et.dt.time, et.dt.weekday)]
    return df.dropna(subset=["_ts_utc"])


def canonicalize_symbol(s: pd.Series) -> pd.Series:
    return s.replace(XSTOCK_TO_UNDERLIER)


def load_concat(glob_dir: Path) -> pd.DataFrame:
    files = sorted(glob_dir.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def normalize_pyth() -> pd.DataFrame:
    base = SCRYER_DATASET_ROOT / "pyth/oracle_tape/v1"
    frames = []
    for d in sorted(base.glob("year=*/month=*")):
        df = load_concat(d)
        if df.empty:
            continue
        df = add_window(df, "poll_unix")
        df = df[["_ts_utc", "_window", "symbol", "pyth_price", "pyth_conf",
                 "pyth_half_width_bps"]].copy()
        df["oracle"] = "pyth"
        df["symbol"] = canonicalize_symbol(df["symbol"])
        df = df.rename(columns={"pyth_price": "value"})
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize_kamino_scope() -> pd.DataFrame:
    base = SCRYER_DATASET_ROOT / "kamino_scope/oracle_tape/v1"
    frames = []
    for d in sorted(base.glob("year=*/month=*")):
        df = load_concat(d)
        if df.empty:
            continue
        df = add_window(df, "poll_ts")
        df = df[["_ts_utc", "_window", "symbol", "scope_price"]].copy()
        df["oracle"] = "kamino_scope"
        df["symbol"] = canonicalize_symbol(df["symbol"])
        df = df.rename(columns={"scope_price": "value"})
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize_redstone_forward() -> pd.DataFrame:
    base = SCRYER_DATASET_ROOT / "redstone/oracle_tape/v1"
    frames = []
    for d in sorted(base.glob("year=*/month=*")):
        df = load_concat(d)
        if df.empty:
            continue
        df = add_window(df, "redstone_ts")
        df = df[["_ts_utc", "_window", "symbol", "value", "minutes_age"]].copy()
        df["oracle"] = "redstone_forward"
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize_redstone_legacy() -> pd.DataFrame:
    if not LEGACY_REDSTONE.exists():
        return pd.DataFrame()
    df = pd.read_parquet(LEGACY_REDSTONE)
    df = add_window(df, "redstone_ts")
    df = df[["_ts_utc", "_window", "symbol", "value", "minutes_age"]].copy()
    df["oracle"] = "redstone_legacy30d"
    return df


def normalize_chainlink_v5_join() -> pd.DataFrame:
    """Chainlink-via-v5: cl_tokenized_px (v10 tokenizedPrice).

    Used as a proxy until chainlink/data_streams parquet lands (item 49d).
    """
    base = SCRYER_DATASET_ROOT / "soothsayer_v5/tape/v1"
    frames = []
    for d in sorted(base.glob("year=*/month=*")):
        df = load_concat(d)
        if df.empty:
            continue
        df = add_window(df, "poll_ts")
        df = df[["_ts_utc", "_window", "symbol", "cl_tokenized_px",
                 "cl_market_status"]].copy()
        df["oracle"] = "chainlink_v10_tokenized"
        df["symbol"] = canonicalize_symbol(df["symbol"])
        df = df.rename(columns={"cl_tokenized_px": "value"})
        df = df.dropna(subset=["value"])
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize_jupiter_v5_join() -> pd.DataFrame:
    """Jupiter mid via v5_tape — the consumer-side execution proxy."""
    base = SCRYER_DATASET_ROOT / "soothsayer_v5/tape/v1"
    frames = []
    for d in sorted(base.glob("year=*/month=*")):
        df = load_concat(d)
        if df.empty:
            continue
        df = add_window(df, "poll_ts")
        df = df[["_ts_utc", "_window", "symbol", "jup_mid", "spread_bp"]].copy()
        df["oracle"] = "jupiter_mid"
        df["symbol"] = canonicalize_symbol(df["symbol"])
        df = df.rename(columns={"jup_mid": "value"})
        df = df.dropna(subset=["value"])
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def per_window_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Stats per (oracle, window, symbol)."""
    if df.empty:
        return pd.DataFrame()
    out = []
    for (oracle, window, symbol), grp in df.groupby(["oracle", "_window", "symbol"], observed=True):
        grp = grp.sort_values("_ts_utc")
        v = grp["value"].astype(float).values
        ts = grp["_ts_utc"].values
        n = len(v)
        n_unique = len(set(v))
        if n >= 2:
            dts = np.diff(ts.astype("datetime64[s]").astype(np.int64))
            median_dt_s = float(np.median(dts))
            ret = np.diff(np.log(np.where(v > 0, v, np.nan)))
            ret = ret[np.isfinite(ret)]
            std_logret_bp = float(np.std(ret) * 1e4) if len(ret) else np.nan
            stale_rate = float((np.diff(v) == 0).mean())
        else:
            median_dt_s = np.nan
            std_logret_bp = np.nan
            stale_rate = np.nan
        out.append(dict(
            oracle=oracle, window=window, symbol=symbol,
            n=n, n_unique=n_unique,
            median_dt_s=median_dt_s,
            std_logret_bp=std_logret_bp,
            stale_rate=stale_rate,
        ))
    return pd.DataFrame(out)


def per_window_pooled(stats: pd.DataFrame) -> pd.DataFrame:
    """Pool across symbols per (oracle, window) for an at-a-glance table."""
    if stats.empty:
        return stats
    pooled = stats.groupby(["oracle", "window"], observed=True).agg(
        n_rows=("n", "sum"),
        symbols=("symbol", "nunique"),
        median_dt_s=("median_dt_s", "median"),
        std_logret_bp=("std_logret_bp", "median"),
        stale_rate=("stale_rate", "mean"),
        n_unique_med=("n_unique", "median"),
    ).reset_index()
    pooled["window"] = pd.Categorical(pooled["window"], categories=WINDOW_ORDER, ordered=True)
    return pooled.sort_values(["oracle", "window"])


def main() -> None:
    print("Loading tapes…")
    tapes = {
        "pyth": normalize_pyth(),
        "kamino_scope": normalize_kamino_scope(),
        "redstone_forward": normalize_redstone_forward(),
        "redstone_legacy30d": normalize_redstone_legacy(),
        "chainlink_v10_tokenized": normalize_chainlink_v5_join(),
        "jupiter_mid": normalize_jupiter_v5_join(),
    }
    for name, df in tapes.items():
        print(f"  {name:30s}  rows={len(df):>9,}  span="
              f"{df._ts_utc.min() if len(df) else '—'} → "
              f"{df._ts_utc.max() if len(df) else '—'}")

    long_df = pd.concat([df for df in tapes.values() if not df.empty], ignore_index=True)
    if long_df.empty:
        print("No data — exiting.")
        return

    stats = per_window_stats(long_df)
    pooled = per_window_pooled(stats)

    print("\n=== Per-(oracle, window) pooled summary ===")
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.width", 200)
    print(pooled.to_string(index=False, float_format=lambda x: f"{x:>10.2f}"))

    PROCESSED.mkdir(parents=True, exist_ok=True)
    pooled.to_parquet(SUMMARY_OUT, index=False)
    print(f"\nWrote {SUMMARY_OUT}")

    detail_out = PROCESSED / "regime_decomposition_probe_per_symbol.parquet"
    stats.to_parquet(detail_out, index=False)
    print(f"Wrote {detail_out}")


if __name__ == "__main__":
    main()
