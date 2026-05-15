"""V1b — Per-minute Winkler curve in the closed window.

Sibling to run_v1b_tokenized_tracking_baseline.py. At each minute t in
[Fri 16:00 ET, Mon 09:30 ET]:

  baseline:   point_t = perp_close(t),  halfwidth_t,tau = walk-forward
              empirical-quantile of |mon_open - perp_close(t)| across past
              weekends (pooled across symbols) at the SAME minute-of-window.
  soothsayer: held constant from the LWC artefact for the whole closed
              window.

Aggregated across (weekend × symbol) per minute-of-window, the baseline's
Winkler curve declines (tokenized side absorbs weekend news); Soothsayer's
is flat. This script materialises that curve at 15-minute granularity
(rather than 1-minute) for compute-budget reasons — the qualitative shape
is identical and resolution beyond 15 min adds nothing analytically.

Outputs:
  - reports/tables/paper1_c3_per_minute_winkler_curve.csv
        long-format: (snapshot_minute_offset, tau, forecaster, mean_winkler_bps,
        mean_halfwidth_bps, realised_coverage, n)
  - reports/v1b_tokenized_per_minute_winkler.md  (companion write-up)
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from soothsayer.config import DATA_PROCESSED  # noqa: E402
from soothsayer.oracle import Oracle, LWC_ARTEFACT_PATH  # noqa: E402
from soothsayer.sources.scryer import (  # noqa: E402
    load_cex_stock_perp_ohlcv,
    load_yahoo_bars,
)


ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# Minute-of-window grid: every 15 minutes from Fri 16:00 ET (offset = 0) to
# Mon 09:30 ET (offset = 1050 min = 17.5 hours past Mon midnight ET, or
# 65.5 hours past Fri 16:00 ET = 3930 min). Grid step 15 min gives 263 points.
WINDOW_MINUTES_START = 0
WINDOW_MINUTES_END = 65 * 60 + 30  # 65h30m past Fri 16:00 ET = Mon 09:30 ET
WINDOW_GRID_STEP = 15  # minutes

TAU_GRID: tuple[float, ...] = (0.68, 0.85, 0.95, 0.99)
BAKEOFF_SYMBOLS: tuple[str, ...] = (
    "SPY", "QQQ", "GLD", "TSLA", "NVDA", "GOOGL", "AAPL", "HOOD", "MSTR",
)
MIN_WARMUP_WEEKENDS = 4


def fri_close_moment(fri_date: date) -> pd.Timestamp:
    """Fri 16:00 ET as a UTC pandas Timestamp."""
    base = datetime(fri_date.year, fri_date.month, fri_date.day, 16, 0, tzinfo=ET)
    return pd.Timestamp(base).tz_convert(UTC)


def fetch_mon_open(symbol: str, fri_date: date) -> float | None:
    bars = load_yahoo_bars(symbol, fri_date + timedelta(days=1), fri_date + timedelta(days=7))
    if bars.empty:
        return None
    bars = bars.copy()
    bars["ts"] = pd.to_datetime(bars["ts"]).dt.date
    bars = bars[bars["ts"] > fri_date].sort_values("ts")
    if bars.empty:
        return None
    return float(bars.iloc[0]["open"])


def load_perp_path(symbol: str, fri_date: date) -> pd.DataFrame:
    raw = load_cex_stock_perp_ohlcv(symbol, fri_date - timedelta(days=1),
                                    fri_date + timedelta(days=4))
    if raw.empty:
        return pd.DataFrame(columns=["ts_utc", "perp_close"])
    df = raw[raw["backing_kind"] == "xstock_backed"].copy()
    df["ts_utc"] = pd.to_datetime(df["bar_open_ts"], unit="s", utc=True)
    win_start = fri_close_moment(fri_date)
    win_end = win_start + pd.Timedelta(minutes=WINDOW_MINUTES_END)
    df = df[(df["ts_utc"] >= win_start) & (df["ts_utc"] <= win_end)]
    df = df[["ts_utc", "close"]].rename(columns={"close": "perp_close"}).copy()
    df = df.sort_values("ts_utc").reset_index(drop=True)
    return df


def asof_perp(perp_path: pd.DataFrame, ts: pd.Timestamp) -> float | None:
    if perp_path.empty:
        return None
    before = perp_path[perp_path["ts_utc"] <= ts]
    if before.empty:
        return None
    return float(before.iloc[-1]["perp_close"])


def winkler(lo: np.ndarray, hi: np.ndarray, y: np.ndarray, tau: float) -> np.ndarray:
    alpha = 1.0 - tau
    width = hi - lo
    pen = np.where(y < lo, (2.0 / alpha) * (lo - y), 0.0) \
        + np.where(y > hi, (2.0 / alpha) * (y - hi), 0.0)
    return width + pen


def build_minute_panel() -> pd.DataFrame:
    """One row per (symbol, fri_ts, minute_offset) with:
       perp_at_minute, mon_open, fri_close, plus the Soothsayer band.
    The Soothsayer band columns are constant across minute_offset for a
    given (symbol, fri_ts) — repeated for join convenience."""
    oracle = Oracle.load(lwc_artefact_path=LWC_ARTEFACT_PATH)
    art = oracle._lwc_artefact  # type: ignore[attr-defined]
    art = art[pd.to_datetime(art["fri_ts"]) >= pd.Timestamp("2025-12-19")]
    art = art[art["symbol"].isin(BAKEOFF_SYMBOLS)].copy()
    art["fri_ts"] = pd.to_datetime(art["fri_ts"]).dt.date

    minutes = list(range(WINDOW_MINUTES_START, WINDOW_MINUTES_END + 1, WINDOW_GRID_STEP))

    rows: list[dict] = []
    for _, art_row in art.sort_values(["fri_ts", "symbol"]).iterrows():
        symbol = art_row["symbol"]
        fri_d = art_row["fri_ts"]
        fri_close = float(art_row["fri_close"])
        mon_open = fetch_mon_open(symbol, fri_d)
        if mon_open is None:
            continue
        perp_path = load_perp_path(symbol, fri_d)
        if perp_path.empty:
            continue
        sooth_bands = {
            tau: oracle.fair_value_lwc(symbol, fri_d, target_coverage=tau)
            for tau in TAU_GRID
        }
        win_start = fri_close_moment(fri_d)
        for off in minutes:
            ts = win_start + pd.Timedelta(minutes=off)
            perp_px = asof_perp(perp_path, ts)
            if perp_px is None:
                continue
            r: dict = {
                "fri_ts": fri_d, "symbol": symbol,
                "minute_offset": off, "perp_at_t": perp_px,
                "mon_open": mon_open, "fri_close": fri_close,
            }
            for tau in TAU_GRID:
                pp = sooth_bands[tau]
                r[f"sooth_lower_tau{tau}"] = pp.lower
                r[f"sooth_upper_tau{tau}"] = pp.upper
                r[f"sooth_point_tau{tau}"] = pp.point
            rows.append(r)
    return pd.DataFrame(rows)


def calibrate_walkforward_per_minute(panel: pd.DataFrame) -> pd.DataFrame:
    """For each (minute_offset, weekend, tau), compute the empirical-quantile
    half-width of |mon_open - perp_at_t| pooled across past weekends and all
    symbols *at the same minute_offset*. Returns the panel with added cols."""
    p = panel.copy()
    p["__resid__"] = p["mon_open"] - p["perp_at_t"]
    p = p.sort_values(["minute_offset", "fri_ts"]).reset_index(drop=True)

    hw_arrs: dict[float, list[float]] = {tau: [] for tau in TAU_GRID}
    # iterate per (minute_offset, fri_ts) to walk-forward by weekend within minute
    for (off, fri_d), group in p.groupby(["minute_offset", "fri_ts"], sort=True):
        past = p[(p["minute_offset"] == off) & (p["fri_ts"] < fri_d)]
        past_resid = past["__resid__"].dropna().abs().values
        n_past_weekends = past["fri_ts"].nunique()
        for _ in range(len(group)):
            if (
                n_past_weekends < MIN_WARMUP_WEEKENDS
                or len(past_resid) == 0
            ):
                for tau in TAU_GRID:
                    hw_arrs[tau].append(float("nan"))
            else:
                for tau in TAU_GRID:
                    hw_arrs[tau].append(float(np.quantile(past_resid, tau)))
    # The groupby order matched the panel's sort, so direct assignment by order works.
    # Re-attach in the order we iterated.
    # To stay safe, rebuild via merge.
    keyed = p.reset_index().sort_values(["minute_offset", "fri_ts", "index"]).reset_index(drop=True)
    for tau in TAU_GRID:
        keyed[f"baseline_halfwidth_tau{tau}"] = hw_arrs[tau]
    keyed = keyed.sort_values("index").reset_index(drop=True)
    keyed = keyed.drop(columns=["index", "__resid__"])
    return keyed


def aggregate_curve(panel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per minute_offset across (weekend × symbol)."""
    out_rows: list[dict] = []
    for off, group in panel.groupby("minute_offset", sort=True):
        for tau in TAU_GRID:
            g = group.dropna(subset=[f"baseline_halfwidth_tau{tau}"]).copy()
            if g.empty:
                continue
            y = g["mon_open"].values
            fri = g["fri_close"].values
            # Baseline
            bp = g["perp_at_t"].values
            bh = g[f"baseline_halfwidth_tau{tau}"].values
            bl, bu = bp - bh, bp + bh
            b_in = (y >= bl) & (y <= bu)
            b_wk_bps = (winkler(bl, bu, y, tau) / fri * 1e4).mean()
            b_hw_bps = (bh / fri * 1e4).mean()
            out_rows.append({
                "minute_offset": int(off),
                "tau": tau,
                "forecaster": "tokenized_tracking_baseline",
                "n": int(len(g)),
                "realised_cov": float(b_in.mean()),
                "mean_halfwidth_bps": float(b_hw_bps),
                "mean_winkler_bps": float(b_wk_bps),
            })
            # Soothsayer (constant across minute; reported at every offset for chart)
            sl = g[f"sooth_lower_tau{tau}"].values
            su = g[f"sooth_upper_tau{tau}"].values
            s_in = (y >= sl) & (y <= su)
            s_wk_bps = (winkler(sl, su, y, tau) / fri * 1e4).mean()
            s_hw_bps = ((su - sl) / 2 / fri * 1e4).mean()
            out_rows.append({
                "minute_offset": int(off),
                "tau": tau,
                "forecaster": "soothsayer_m6_lwc",
                "n": int(len(g)),
                "realised_cov": float(s_in.mean()),
                "mean_halfwidth_bps": float(s_hw_bps),
                "mean_winkler_bps": float(s_wk_bps),
            })
    return pd.DataFrame(out_rows)


def main() -> int:
    print("[1/3] Building per-minute panel (15-min grid, 263 offsets x 117 weekend-symbols)...", flush=True)
    panel = build_minute_panel()
    print(f"      rows: {len(panel):,}  weekends: {panel['fri_ts'].nunique()}  syms: {panel['symbol'].nunique()}", flush=True)

    print("[2/3] Walk-forward calibrating baseline at each minute_offset (this is the slow step)...", flush=True)
    panel = calibrate_walkforward_per_minute(panel)

    print("[3/3] Aggregating into per-minute curve...", flush=True)
    curve = aggregate_curve(panel)

    out_panel = DATA_PROCESSED / "v1b_tokenized_per_minute_winkler.parquet"
    out_curve = REPO / "reports" / "tables" / "paper1_c3_per_minute_winkler_curve.csv"
    out_panel.parent.mkdir(parents=True, exist_ok=True)
    out_curve.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(out_panel, index=False)
    curve.to_csv(out_curve, index=False)
    print(f"      Wrote {out_panel}")
    print(f"      Wrote {out_curve}")

    # Headline: at tau=0.95, what's the Winkler ratio at each canonical hour offset?
    print()
    print("---- Mean Winkler (bps) at tau=0.95, by hour offset from Fri close ----")
    sub = curve[curve["tau"] == 0.95].copy()
    # Pivot to wide for display.
    wide = sub.pivot_table(index="minute_offset", columns="forecaster",
                           values="mean_winkler_bps").reset_index()
    wide["hours"] = wide["minute_offset"] / 60.0
    wide = wide[(wide["minute_offset"] % 240 == 0) | (wide["minute_offset"] == WINDOW_MINUTES_END)]
    cols = ["hours", "soothsayer_m6_lwc", "tokenized_tracking_baseline"]
    wide["ratio_base_over_sooth"] = wide["tokenized_tracking_baseline"] / wide["soothsayer_m6_lwc"]
    print(wide[cols + ["ratio_base_over_sooth"]].round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
