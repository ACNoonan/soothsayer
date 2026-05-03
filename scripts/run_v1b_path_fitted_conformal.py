"""
Path-fitted conformity score — first cut on the CME-projected path subset.

§6.6.3 / §10.1's V3.3 promises a path-fitted variant of the conformity
score: rather than calibrating on the endpoint residual

    s_endpoint = |mon_open - point| / fri_close,

calibrate on the supremum of the residual over the weekend window:

    s_path = max_{t in [Fri 16:00, Mon 09:30]} |P_t - point| / fri_close.

This script runs that fit on the n=3,861 CME-projected subset (the same
panel `scripts/run_path_coverage.py` uses) and reports head-to-head:

  - Endpoint-fitted M5  (the deployed schedule)  — row-aligned to subset
  - Path-fitted M5      (s_path replaces s_endpoint in train + OOS)
  - Both evaluated by *path coverage* on the same OOS rows.

Bands will be wider but path-calibrated by construction. The point is to
deliver a first read on the trade-off the paper currently defers.

Output:
  reports/tables/v1b_robustness_path_fitted.csv
"""

from __future__ import annotations

from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    fit_c_bump_schedule,
    serve_bands,
    train_quantile_table,
)
from soothsayer.config import DATA_PROCESSED, REPORTS, SCRYER_DATASET_ROOT

SPLIT_DATE = date(2023, 1, 1)
NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
WINDOW_START = dtime(16, 0)
WINDOW_END = dtime(9, 30)

FACTOR_FOR_PATH: dict[str, str] = {
    "SPY":   "ES=F",
    "QQQ":   "ES=F",
    "AAPL":  "ES=F",
    "GOOGL": "ES=F",
    "NVDA":  "ES=F",
    "TSLA":  "ES=F",
    "HOOD":  "ES=F",
    "MSTR":  "ES=F",
    "GLD":   "GC=F",
    "TLT":   "ZN=F",
}
MSTR_BTC_PIVOT = date(2020, 8, 1)


def load_cme_factor(factor: str) -> pd.DataFrame:
    root = SCRYER_DATASET_ROOT / "cme" / "intraday_1m" / "v1" / f"symbol={factor}"
    files = [str(p) for p in sorted(root.rglob("*.parquet"))]
    d = ds.dataset(files, format="parquet")
    tbl = d.to_table(columns=["ts", "high", "low", "close"])
    df = tbl.to_pandas()
    df["ts"] = pd.to_numeric(df["ts"], downcast="integer")
    return df.sort_values("ts").reset_index(drop=True)


def weekend_window_utc(fri_ts: date, mon_ts: date) -> tuple[int, int]:
    start = datetime.combine(fri_ts, WINDOW_START, tzinfo=NY).astimezone(UTC)
    end = datetime.combine(mon_ts, WINDOW_END, tzinfo=NY).astimezone(UTC)
    return int(start.timestamp()), int(end.timestamp())


def cme_path_extrema(factor_bars: pd.DataFrame, fri_ts: date,
                     mon_ts: date) -> tuple[float | None, float | None,
                                            float | None, int]:
    start_utc, end_utc = weekend_window_utc(fri_ts, mon_ts)
    win = factor_bars[(factor_bars["ts"] >= start_utc) &
                      (factor_bars["ts"] <= end_utc)]
    if win.empty:
        return None, None, None, 0
    pre = factor_bars[factor_bars["ts"] <= start_utc + 60]
    if pre.empty:
        anchor = float(win["close"].iloc[0])
    else:
        anchor = float(pre["close"].iloc[-1])
    return (anchor, float(win["low"].min()), float(win["high"].max()),
            int(len(win)))


def compute_path_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """For each (symbol, weekend), compute path_lo and path_hi via CME 1m
    bars scaled by `fri_close / F_anchor`. Drops rows where the factor is
    not loadable (e.g., MSTR post-2020-08, BTC tape absent)."""
    base = panel[panel["symbol"].isin(FACTOR_FOR_PATH)].copy()
    base = base[~((base["symbol"] == "MSTR") &
                  (base["fri_ts"] >= MSTR_BTC_PIVOT))]
    base["factor_used"] = base["symbol"].map(FACTOR_FOR_PATH)

    factor_cache: dict[str, pd.DataFrame] = {}
    rows = []
    for _, row in base.iterrows():
        f = row["factor_used"]
        if f not in factor_cache:
            factor_cache[f] = load_cme_factor(f)
        anchor, lo, hi, n_bars = cme_path_extrema(
            factor_cache[f], row["fri_ts"], row["mon_ts"]
        )
        if anchor is None or anchor <= 0 or n_bars == 0:
            continue
        scale = float(row["fri_close"]) / anchor
        rows.append({
            "symbol": row["symbol"],
            "fri_ts": row["fri_ts"],
            "mon_ts": row["mon_ts"],
            "regime_pub": row["regime_pub"],
            "fri_close": float(row["fri_close"]),
            "mon_open": float(row["mon_open"]),
            "factor_ret": float(row["factor_ret"]),
            "factor_used": f,
            "n_bars": int(n_bars),
            "path_lo": lo * scale,
            "path_hi": hi * scale,
        })
    return pd.DataFrame(rows)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    print("[1/4] Loading CME 1m bars and computing per-row path extrema …",
          flush=True)
    pp = compute_path_panel(panel)
    print(f"      {len(pp):,} rows  ({pp['symbol'].nunique()} symbols, "
          f"{pp['fri_ts'].nunique()} weekends)", flush=True)

    pp["point"] = pp["fri_close"] * (1.0 + pp["factor_ret"])
    pp["score_endpoint"] = (
        (pp["mon_open"] - pp["point"]).abs() / pp["fri_close"]
    )
    # Path score: max breach over the full path, including the Monday-open
    # endpoint (mon_open ∈ [path_lo, path_hi] is not guaranteed, so we
    # take the worst of {endpoint, low, high}).
    breach_lo = (pp["point"] - pp["path_lo"]).clip(lower=0.0)
    breach_hi = (pp["path_hi"] - pp["point"]).clip(lower=0.0)
    breach_end = (pp["mon_open"] - pp["point"]).abs()
    pp["score_path"] = (np.maximum.reduce([breach_lo, breach_hi, breach_end])
                        / pp["fri_close"])

    train = pp[pp["fri_ts"] < SPLIT_DATE]
    oos = (pp[pp["fri_ts"] >= SPLIT_DATE]
           .sort_values(["symbol", "fri_ts"])
           .reset_index(drop=True))
    print(f"      train={len(train):,}  oos={len(oos):,}", flush=True)

    print("[2/4] Endpoint-fitted M5 (subset-restricted re-fit) …",
          flush=True)
    qt_e = train_quantile_table(train.assign(score=train["score_endpoint"]),
                                cell_col="regime_pub", taus=DEFAULT_TAUS,
                                score_col="score")
    cb_e = fit_c_bump_schedule(oos.assign(score=oos["score_endpoint"]),
                               qt_e, cell_col="regime_pub",
                               taus=DEFAULT_TAUS, score_col="score")
    bounds_e = serve_bands(oos, qt_e, cb_e, cell_col="regime_pub",
                           taus=DEFAULT_TAUS)

    print("[3/4] Path-fitted M5 (score = max breach over weekend) …",
          flush=True)
    qt_p = train_quantile_table(train.assign(score=train["score_path"]),
                                cell_col="regime_pub", taus=DEFAULT_TAUS,
                                score_col="score")
    cb_p = fit_c_bump_schedule(oos.assign(score=oos["score_path"]),
                               qt_p, cell_col="regime_pub",
                               taus=DEFAULT_TAUS, score_col="score")
    bounds_p = serve_bands(oos, qt_p, cb_p, cell_col="regime_pub",
                           taus=DEFAULT_TAUS)

    print("[4/4] Coverage on path AND endpoint criteria …", flush=True)
    rows = []
    for variant_name, bounds in [("endpoint_fitted", bounds_e),
                                 ("path_fitted", bounds_p)]:
        for tau in DEFAULT_TAUS:
            b = bounds[tau]
            endpoint_in = ((oos["mon_open"] >= b["lower"]) &
                           (oos["mon_open"] <= b["upper"]))
            path_in = ((oos["path_lo"] >= b["lower"]) &
                       (oos["path_hi"] <= b["upper"]))
            v_endp = (~endpoint_in).astype(int).to_numpy()
            v_path = (~path_in).astype(int).to_numpy()
            kup_e_lr, kup_e_p = met._lr_kupiec(v_endp, tau)
            kup_p_lr, kup_p_p = met._lr_kupiec(v_path, tau)
            rows.append({
                "variant": variant_name, "tau": tau,
                "n": int(len(oos)),
                "endpoint_realised": float(endpoint_in.mean()),
                "path_realised": float(path_in.mean()),
                "gap_pp": float((endpoint_in.mean() - path_in.mean()) * 100),
                "half_width_bps": float(((b["upper"] - b["lower"]) / 2 /
                                         oos["fri_close"] * 1e4).mean()),
                "kupiec_p_endpoint": float(kup_e_p),
                "kupiec_p_path": float(kup_p_p),
                "c_bump": float(cb_p[tau] if variant_name == "path_fitted"
                                else cb_e[tau]),
            })
    out = pd.DataFrame(rows)
    out_path = REPORTS / "tables" / "v1b_robustness_path_fitted.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}\n", flush=True)
    print("=" * 100)
    print("PATH-FITTED vs ENDPOINT-FITTED M5 (CME-projected subset, OOS)")
    print("=" * 100)
    print(out.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
