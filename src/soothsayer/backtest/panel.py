"""
Assemble the weekend panel for the decade-scale calibration backtest.

For each (symbol, weekend) produce a row with:
  fri_ts, fri_close, fri_vol_20d        -- publish-time state, underlying
  mon_ts, mon_open                      -- ground truth target
  gap_days                              -- 3 for normal weekend, 4+ for holiday
  es_fri_close, es_mon_open             -- futures weekend return signal
  nq_fri_close, nq_mon_open
  vix_fri_close                         -- regime context

Only uses information available at Friday 16:00 ET. Monday values are the
ground truth, never inputs to forecasters.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..sources.scryer import (
    load_cboe_index_daily,
    load_cme_daily_from_intraday,
    load_yahoo_bars,
    load_yahoo_earnings,
)
from ..universe import CORE_XSTOCKS

# Symbols whose forward-going coverage moved from `yahoo/equities_daily/v1`
# to a non-yahoo scryer source (G1.b shipped 2026-05-04). For each, we
# read both sources and concat — yahoo provides the historical depth,
# the new source extends forward. Where both have a date, the new
# source wins.
CBOE_INDEX_SYMBOLS: dict[str, str] = {
    "^VIX": "VIX",  # panel-side canonical name → CBOE on-disk index name
}
CME_FUTURES_SYMBOLS: tuple[str, ...] = ("ES=F", "NQ=F", "GC=F", "ZN=F")

# Extra underlyings to support the RWA-generalization narrative (closed-market
# assets that aren't equities: gold, long treasuries). TLT and GLD trade NYSE
# hours so they share the weekend-gap problem with xStocks.
RWA_ANCHORS = ("GLD", "TLT")

FUTURES = ("ES=F", "NQ=F", "GC=F", "ZN=F")
VIX = "^VIX"
GVZ = "^GVZ"   # Gold VIX (gold implied vol index)
MOVE = "^MOVE"  # ICE BofA MOVE index (treasury implied vol)
BTC = "BTC-USD"
VOL_INDICES = (VIX, GVZ, MOVE)

# Per-symbol conditioning factor. Equities → broad-market futures; gold →
# gold futures; long rates → treasury futures. MSTR switches to BTC-USD from
# 2020-08 onward (company started accumulating BTC Aug 2020 and its price
# behaviour pivoted accordingly); pre-2020 MSTR uses ES=F like other equities.
FACTOR_BY_SYMBOL: dict[str, str] = {
    "SPY":   "ES=F",
    "QQQ":   "ES=F",
    "AAPL":  "ES=F",
    "GOOGL": "ES=F",
    "NVDA":  "ES=F",
    "TSLA":  "ES=F",
    "MSTR":  "ES=F",   # overridden to BTC-USD post-2020-08 in build()
    "HOOD":  "ES=F",
    "GLD":   "GC=F",
    "TLT":   "ZN=F",
}

MSTR_BTC_PIVOT: date = date(2020, 8, 1)

# Per-symbol vol-index selection. VIX works for equities but not for non-equity
# RWAs; fitted log-log β values in the first V1b pass showed GLD β≈0.55 and
# TLT β≈0.94, both well below equity β≈1.5, confirming VIX is a weak vol proxy
# for gold and treasuries. GVZ (gold VIX) and MOVE (treasury vol) are the
# asset-class-appropriate proxies.
VOL_INDEX_BY_SYMBOL: dict[str, str] = {
    "SPY":   VIX,
    "QQQ":   VIX,
    "AAPL":  VIX,
    "GOOGL": VIX,
    "NVDA":  VIX,
    "TSLA":  VIX,
    "MSTR":  VIX,
    "HOOD":  VIX,
    "GLD":   GVZ,
    "TLT":   MOVE,
}


@dataclass(frozen=True)
class PanelSpec:
    start: date
    end: date
    min_gap_days: int = 3
    vol_lookback: int = 20  # trading days for realized vol used in F0 CI


def _universe() -> list[str]:
    eq = [x.underlying for x in CORE_XSTOCKS]
    return eq + list(RWA_ANCHORS)


def _vol_20d(close: pd.Series, window: int = 20) -> pd.Series:
    """Rolling daily-return std over `window` trading days, as a fraction."""
    r = np.log(close / close.shift(1))
    return r.rolling(window, min_periods=window // 2).std()


def _weekend_pairs_with_vol(daily: pd.DataFrame, spec: PanelSpec) -> pd.DataFrame:
    """Per-symbol: for each Fri→Mon pair, attach fri_close, mon_open, gap_days,
    and fri_vol_{vol_lookback}d computed from Fri-including history only."""
    out: list[dict] = []
    for sym, grp in daily.sort_values("ts").groupby("symbol", sort=False):
        g = grp.reset_index(drop=True).copy()
        g["ts"] = pd.to_datetime(g["ts"])
        g["vol"] = _vol_20d(g["close"], spec.vol_lookback)
        gaps = g["ts"].diff().dt.days
        for i in range(1, len(g)):
            gap = gaps.iloc[i]
            if pd.isna(gap) or gap < spec.min_gap_days:
                continue
            fri_vol = g.at[i - 1, "vol"]
            if pd.isna(fri_vol):
                continue
            out.append(
                {
                    "symbol": sym,
                    "fri_ts": g.at[i - 1, "ts"].date(),
                    "mon_ts": g.at[i, "ts"].date(),
                    "gap_days": int(gap),
                    "fri_close": float(g.at[i - 1, "close"]),
                    "mon_open": float(g.at[i, "open"]),
                    "fri_vol_20d": float(fri_vol),
                }
            )
    if not out:
        return pd.DataFrame(
            columns=[
                "symbol", "fri_ts", "mon_ts", "gap_days", "fri_close",
                "mon_open", "fri_vol_20d",
            ]
        )
    return pd.DataFrame(out)


def _load_one_symbol(sym: str, start: date, end: date) -> pd.DataFrame:
    """Per-symbol loader with source dispatch. Returns a frame with at
    least ``symbol, ts, open, close`` columns (``ts`` as datetime.date).

    Dispatch:
      * VIX (key ``^VIX`` in panel) → blend CBOE (forward) with yahoo
        legacy (historical). CBOE goes back to 1990 for VIX, but we still
        keep yahoo legacy for byte-identical reads on the frozen
        artefact's training window. Where both have a date, CBOE wins.
      * ES=F / NQ=F / GC=F / ZN=F → blend CME-1m-resampled (forward)
        with yahoo legacy (historical). Yahoo wins on overlapping dates
        (its convention is what the frozen artefact was trained on).
      * Everything else → yahoo only.
    """
    if sym in CBOE_INDEX_SYMBOLS:
        cboe_idx = CBOE_INDEX_SYMBOLS[sym]
        cboe = load_cboe_index_daily(cboe_idx, start, end)
        if not cboe.empty:
            cboe = cboe[["symbol", "ts", "open", "close"]].copy()
            cboe["symbol"] = sym  # restore the panel-side ^VIX key
        yahoo = load_yahoo_bars(sym, start, end)
        if not yahoo.empty:
            yahoo = yahoo[["symbol", "ts", "open", "close"]].copy()
        # CBOE wins on overlap.
        if cboe.empty:
            return yahoo
        if yahoo.empty:
            return cboe
        covered = set(cboe["ts"])
        gap = yahoo[~yahoo["ts"].isin(covered)]
        return pd.concat([cboe, gap], ignore_index=True).sort_values("ts").reset_index(drop=True)

    if sym in CME_FUTURES_SYMBOLS:
        yahoo = load_yahoo_bars(sym, start, end)
        if not yahoo.empty:
            yahoo = yahoo[["symbol", "ts", "open", "close"]].copy()
        cme = load_cme_daily_from_intraday(sym, start, end)
        if not cme.empty:
            cme = cme[["symbol", "ts", "open", "close"]].copy()
        # Yahoo wins on overlap (frozen-artefact training convention).
        if cme.empty:
            return yahoo
        if yahoo.empty:
            return cme
        covered = set(yahoo["ts"])
        gap = cme[~cme["ts"].isin(covered)]
        return pd.concat([yahoo, gap], ignore_index=True).sort_values("ts").reset_index(drop=True)

    # Default path: yahoo only.
    df = load_yahoo_bars(sym, start, end)
    if df.empty:
        return pd.DataFrame(columns=["symbol", "ts", "open", "close"])
    return df[["symbol", "ts", "open", "close"]].copy()


def _load_daily_window(symbols: list[str], start: date, end: date) -> pd.DataFrame:
    """Load one daily-bar window for a list of symbols, dispatching each
    symbol to the appropriate scryer source (yahoo, CBOE, CME)."""
    frames: list[pd.DataFrame] = []
    for sym in symbols:
        df = _load_one_symbol(sym, start, end)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["symbol", "ts", "open", "close"])
    return pd.concat(frames, ignore_index=True)


def _join_exog(panel: pd.DataFrame, exog: pd.DataFrame, exog_symbol: str, prefix: str) -> pd.DataFrame:
    """Attach Friday close and Monday open of an exogenous daily series to the panel.

    Exog rows are indexed by ts. Monday-open of a futures contract is a proxy for
    the Sunday-to-Monday-morning cumulative return; it's not the Sunday 20:00 level
    but it's the cleanest daily signal available without intraday data."""
    e = exog[exog["symbol"] == exog_symbol][["ts", "close", "open"]].copy()
    e["ts"] = pd.to_datetime(e["ts"]).dt.date
    fri = e.rename(columns={"ts": "fri_ts", "close": f"{prefix}_fri_close"})[
        ["fri_ts", f"{prefix}_fri_close"]
    ]
    mon = e.rename(columns={"ts": "mon_ts", "open": f"{prefix}_mon_open"})[
        ["mon_ts", f"{prefix}_mon_open"]
    ]
    out = panel.merge(fri, on="fri_ts", how="left").merge(mon, on="mon_ts", how="left")
    return out


def _join_vix(panel: pd.DataFrame, vix: pd.DataFrame) -> pd.DataFrame:
    v = vix[vix["symbol"] == VIX][["ts", "close"]].copy()
    v["ts"] = pd.to_datetime(v["ts"]).dt.date
    v = v.rename(columns={"ts": "fri_ts", "close": "vix_fri_close"})
    return panel.merge(v, on="fri_ts", how="left")


def _join_vol_index(panel: pd.DataFrame, vol_idx_daily: pd.DataFrame, symbol: str, prefix: str) -> pd.DataFrame:
    v = vol_idx_daily[vol_idx_daily["symbol"] == symbol][["ts", "close"]].copy()
    if v.empty:
        panel[f"{prefix}_fri_close"] = np.nan
        return panel
    v["ts"] = pd.to_datetime(v["ts"]).dt.date
    v = v.rename(columns={"ts": "fri_ts", "close": f"{prefix}_fri_close"})
    return panel.merge(v, on="fri_ts", how="left")


def _earnings_flags(spec: PanelSpec) -> pd.DataFrame:
    """For each (symbol, weekend), emit earnings_next_week boolean: True if the
    ticker has an earnings release scheduled in the upcoming Mon–Fri window.

    Reads scryer ``yahoo/earnings/v1`` parquet. The historical depth is still
    bounded by the imported earnings calendar, so earlier years naturally land
    as False rather than "known no earnings".
    """
    symbols = [x.underlying for x in CORE_XSTOCKS]
    rows: list[pd.DataFrame] = []
    for sym in symbols:
        try:
            df = load_yahoo_earnings(sym, spec.start, spec.end + timedelta(days=4))
        except Exception as exc:
            warnings.warn(f"earnings loader failed for {sym}: {exc}")
            continue
        if not df.empty:
            rows.append(df[["symbol", "earnings_date"]].copy())
    if not rows:
        return pd.DataFrame(columns=["symbol", "earnings_date"])
    return pd.concat(rows, ignore_index=True).drop_duplicates(
        subset=["symbol", "earnings_date"]
    )


def _attach_earnings_flag(panel: pd.DataFrame, earnings: pd.DataFrame) -> pd.DataFrame:
    """earnings_next_week = True if earnings_date is in [mon_ts, mon_ts + 4 trading days]
    for the row's symbol. We approximate the trading-week window as mon_ts + 4 calendar days,
    which catches all weekday earnings after Monday open."""
    out = panel.copy()
    out["earnings_next_week"] = False
    if earnings.empty:
        return out
    e = earnings.copy()
    e["earnings_date"] = pd.to_datetime(e["earnings_date"]).dt.date
    for sym in out["symbol"].unique():
        sym_earnings = set(e.loc[e["symbol"] == sym, "earnings_date"].tolist())
        if not sym_earnings:
            continue
        mask = out["symbol"] == sym
        for_idx = out.loc[mask].index
        for idx in for_idx:
            mon = out.at[idx, "mon_ts"]
            # check if any earnings date falls within [mon, mon + 4 days]
            in_window = any(
                (ed >= mon) and (ed <= mon + timedelta(days=4))
                for ed in sym_earnings
            )
            if in_window:
                out.at[idx, "earnings_next_week"] = True
    return out


def build(spec: PanelSpec) -> pd.DataFrame:
    """Return the fully-assembled weekend panel.

    Columns:
      symbol, fri_ts, mon_ts, gap_days,
      fri_close, mon_open, fri_vol_20d,
      es_fri_close, es_mon_open, nq_fri_close, nq_mon_open,
      gc_fri_close, gc_mon_open, zn_fri_close, zn_mon_open,
      bt_fri_close, bt_mon_open,        -- BTC-USD daily closes and Mon-open proxy
      vix_fri_close, gvz_fri_close, move_fri_close,
      factor, factor_ret,               -- per-symbol conditioning factor
      vol_idx, vol_idx_fri_close,       -- per-symbol vol index
      earnings_next_week,               -- boolean regime flag
      fut_ret                           -- alias for es_ret (legacy F2 path)
    """
    equities = _universe()
    eq_daily = _load_daily_window(equities, spec.start, spec.end)
    fut_daily = _load_daily_window(list(FUTURES), spec.start, spec.end)
    vix_daily = _load_daily_window([VIX], spec.start, spec.end)
    gvz_daily = _load_daily_window([GVZ], spec.start, spec.end)
    move_daily = _load_daily_window([MOVE], spec.start, spec.end)
    btc_daily = _load_daily_window([BTC], spec.start, spec.end)

    panel = _weekend_pairs_with_vol(eq_daily, spec)

    panel = _join_exog(panel, fut_daily, "ES=F", "es")
    panel = _join_exog(panel, fut_daily, "NQ=F", "nq")
    panel = _join_exog(panel, fut_daily, "GC=F", "gc")
    panel = _join_exog(panel, fut_daily, "ZN=F", "zn")
    panel = _join_exog(panel, btc_daily, BTC, "bt")
    panel = _join_vix(panel, vix_daily)
    panel = _join_vol_index(panel, gvz_daily, GVZ, "gvz")
    panel = _join_vol_index(panel, move_daily, MOVE, "move")

    essential_core = ["es_fri_close", "es_mon_open", "nq_fri_close", "nq_mon_open", "vix_fri_close"]
    before = len(panel)
    panel = panel.dropna(subset=essential_core).reset_index(drop=True)
    dropped_core = before - len(panel)

    panel["es_ret"] = panel["es_mon_open"] / panel["es_fri_close"] - 1.0
    panel["nq_ret"] = panel["nq_mon_open"] / panel["nq_fri_close"] - 1.0
    panel["gc_ret"] = panel["gc_mon_open"] / panel["gc_fri_close"] - 1.0
    panel["zn_ret"] = panel["zn_mon_open"] / panel["zn_fri_close"] - 1.0
    panel["bt_ret"] = panel["bt_mon_open"] / panel["bt_fri_close"] - 1.0

    # Build per-symbol factor series, with MSTR overridden to BTC from MSTR_BTC_PIVOT
    def _select_factor_ret(row: pd.Series) -> float:
        sym = row["symbol"]
        factor = FACTOR_BY_SYMBOL.get(sym, "ES=F")
        if sym == "MSTR" and row["fri_ts"] >= MSTR_BTC_PIVOT:
            factor = BTC
            return row["bt_ret"]
        code = factor.replace("=F", "").lower().replace("-usd", "")
        return row.get(f"{code}_ret", np.nan)

    def _select_factor_label(row: pd.Series) -> str:
        sym = row["symbol"]
        if sym == "MSTR" and row["fri_ts"] >= MSTR_BTC_PIVOT:
            return BTC
        return FACTOR_BY_SYMBOL.get(sym, "ES=F")

    panel["factor"] = panel.apply(_select_factor_label, axis=1)
    panel["factor_ret"] = panel.apply(_select_factor_ret, axis=1)

    # Per-symbol vol index
    panel["vol_idx"] = panel["symbol"].map(VOL_INDEX_BY_SYMBOL).fillna(VIX)
    vol_idx_close = pd.Series(index=panel.index, dtype=float)
    for idx_name, col_prefix in [(VIX, "vix"), (GVZ, "gvz"), (MOVE, "move")]:
        mask = panel["vol_idx"] == idx_name
        vol_idx_close.loc[mask] = panel.loc[mask, f"{col_prefix}_fri_close"].values
    # Fallback to VIX where the preferred index is missing (early GVZ/MOVE history gaps)
    vol_idx_close = vol_idx_close.fillna(panel["vix_fri_close"])
    panel["vol_idx_fri_close"] = vol_idx_close

    before2 = len(panel)
    panel = panel.dropna(subset=["factor_ret", "vol_idx_fri_close"]).reset_index(drop=True)
    dropped_factor = before2 - len(panel)

    # Earnings flag — not blocking if absent for some tickers
    try:
        earnings = _earnings_flags(spec)
        panel = _attach_earnings_flag(panel, earnings)
    except Exception as exc:
        warnings.warn(f"earnings flag step failed, defaulting all False: {exc}")
        panel["earnings_next_week"] = False

    # Legacy alias for F2 / old code paths
    panel["fut_ret"] = panel["es_ret"]

    panel.attrs["spec"] = spec
    panel.attrs["dropped_for_missing_exog"] = dropped_core + dropped_factor
    return panel
