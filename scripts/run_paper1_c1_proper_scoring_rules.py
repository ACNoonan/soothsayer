"""Paper 1 — Tier C item C1.

Proper scoring rules (Winkler interval score + CRPS) head-to-head across
M6 LWC (deployed), M5 (Mondrian-only baseline), and GARCH(1,1)-t.

Single-number per method ↔ "did head-to-head comparisons without reading
off four anchor rows".

Winkler interval score for a (1−α) interval [L, U] given realised y:
  S(α; L, U; y) = (U − L) + (2/α) · max(0, L − y) + (2/α) · max(0, y − U)

Lower is better. Combines width (narrow = good) and miss penalty
(realised outside band = bad with weight 2/α). CRPS via the symmetric-
band τ-grid construction:

  Coverage c ∈ {0.05, 0.10, …, 0.95, 0.99} maps to a pair of CDF anchors
  (cdf_low, cdf_hi) = ((1−c)/2, (1+c)/2). For each row, build the
  ascending-τ quantile vector across the union of all (c, c-pair) anchors
  and compute the trapezoid-integrated CRPS via
  `metrics.crps_from_quantiles`.

Output:
  reports/tables/paper1_c1_proper_scoring_rules.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    SIGMA_HAT_HL_WEEKENDS,
    add_sigma_hat_sym_ewma,
    train_quantile_table,
    fit_c_bump_schedule,
    compute_score,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

# Re-use GARCH-t fit pipeline from the existing baseline script.
import sys
sys.path.insert(0, str((REPORTS.parent / "scripts").resolve()))
from run_v1b_garch_baseline import (  # type: ignore
    fit_per_symbol_garch, _quantile as garch_quantile,
)

SPLIT_DATE = date(2023, 1, 1)
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
DENSE_COVERAGE_GRID = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.68,
                        0.70, 0.80, 0.85, 0.90, 0.93, 0.95, 0.97, 0.99)


def _winkler_interval_score(lower: np.ndarray, upper: np.ndarray,
                            y: np.ndarray, tau: float) -> np.ndarray:
    alpha = 1.0 - tau
    width = upper - lower
    pen_lo = (2.0 / alpha) * np.maximum(0.0, lower - y)
    pen_hi = (2.0 / alpha) * np.maximum(0.0, y - upper)
    return width + pen_lo + pen_hi


def _interp_table(table: dict, x: float) -> float:
    keys = sorted(float(k) for k in table.keys())
    if x <= keys[0]:
        return float(table[keys[0]])
    if x >= keys[-1]:
        return float(table[keys[-1]])
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= x <= hi:
            frac = (x - lo) / (hi - lo)
            return float(table[lo] + frac * (table[hi] - table[lo]))
    return float(table[keys[-1]])


def lwc_bounds_at_coverage(panel: pd.DataFrame, qt: dict, cb: dict,
                           coverage: float) -> tuple[np.ndarray, np.ndarray]:
    cells = panel["regime_pub"].astype(str).to_numpy()
    sigma = panel["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    fri_close = panel["fri_close"].astype(float).to_numpy()
    point = (panel["fri_close"].astype(float)
             * (1.0 + panel["factor_ret"].astype(float))).to_numpy()
    c = _interp_table(cb, coverage)
    q_per_row = np.array(
        [_interp_table(qt.get(cells[i], {}), coverage)
         if cells[i] in qt else np.nan
         for i in range(len(panel))],
        dtype=float,
    )
    half = q_per_row * c * sigma * fri_close
    return point - half, point + half


def m5_bounds_at_coverage(panel: pd.DataFrame, qt: dict, cb: dict,
                          coverage: float) -> tuple[np.ndarray, np.ndarray]:
    cells = panel["regime_pub"].astype(str).to_numpy()
    fri_close = panel["fri_close"].astype(float).to_numpy()
    point = (panel["fri_close"].astype(float)
             * (1.0 + panel["factor_ret"].astype(float))).to_numpy()
    c = _interp_table(cb, coverage)
    q_per_row = np.array(
        [_interp_table(qt.get(cells[i], {}), coverage)
         if cells[i] in qt else np.nan
         for i in range(len(panel))],
        dtype=float,
    )
    half = q_per_row * c * point
    return point - half, point + half


def garch_bounds_at_coverage(forecasts: pd.DataFrame,
                             coverage: float) -> tuple[np.ndarray, np.ndarray]:
    fri_close = forecasts["fri_close"].astype(float).to_numpy()
    mu = forecasts["mu_hat"].to_numpy(float)
    sig = forecasts["sigma_hat"].to_numpy(float)
    dist_used = forecasts["dist_used"].to_numpy()
    nu = forecasts["nu_hat"].to_numpy(float)
    n = len(forecasts)
    q_per_row = np.empty(n)
    cache: dict[tuple[str, float], float] = {}
    for i in range(n):
        key = (str(dist_used[i]),
               float(nu[i]) if np.isfinite(nu[i]) else float("nan"))
        if key not in cache:
            cache[key] = garch_quantile(coverage, key[0], key[1])
        q_per_row[i] = cache[key]
    lower = fri_close * np.exp(mu - q_per_row * sig)
    upper = fri_close * np.exp(mu + q_per_row * sig)
    return lower, upper


def crps_grid(panel_lower: list[np.ndarray], panel_upper: list[np.ndarray],
              y: np.ndarray, coverage_grid: tuple[float, ...]) -> np.ndarray:
    """For each row, build a (cdf_levels, quantile) pair across the
    coverage grid (yields 2K + 1 anchors per row; the +1 is the median at
    cdf=0.5, taken as the row's `point` predictor). Calls
    `crps_from_quantiles` per row.

    Inputs panel_lower[i], panel_upper[i] is the (lower, upper) array at
    coverage grid index i."""
    n_rows = len(y)
    crps = np.full(n_rows, np.nan)
    cov_arr = np.array(coverage_grid)
    cdf_lo = (1.0 - cov_arr) / 2.0
    cdf_hi = (1.0 + cov_arr) / 2.0
    for r in range(n_rows):
        q_vals = []
        cdf_levels = []
        for k, c in enumerate(coverage_grid):
            ll = panel_lower[k][r]
            uu = panel_upper[k][r]
            if not (np.isfinite(ll) and np.isfinite(uu)):
                continue
            q_vals.extend([ll, uu])
            cdf_levels.extend([cdf_lo[k], cdf_hi[k]])
        if len(q_vals) < 4:
            continue
        # Add the median anchor (cdf=0.5) at the average of the deepest band
        # midpoints — i.e., the implied point predictor. Use coverage→0
        # extrapolation: at very narrow coverage the band collapses to point.
        mid = 0.5 * (panel_lower[0][r] + panel_upper[0][r])
        q_vals.append(mid)
        cdf_levels.append(0.5)
        order = np.argsort(cdf_levels)
        cdf_arr = np.asarray(cdf_levels)[order]
        q_arr = np.asarray(q_vals)[order]
        # Drop duplicate cdf levels (numerical near-ties)
        keep = np.concatenate(([True], np.diff(cdf_arr) > 1e-9))
        cdf_arr = cdf_arr[keep]
        q_arr = q_arr[keep]
        crps[r] = met.crps_from_quantiles(float(y[r]), cdf_arr, q_arr)
    return crps


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HAT_HL_WEEKENDS)
    sigma_col = f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HAT_HL_WEEKENDS}"
    panel["sigma_hat_sym_pre_fri"] = panel[sigma_col]

    panel_m5 = panel.copy()
    panel_m5["score"] = compute_score(panel_m5)
    panel_m5 = panel_m5.dropna(subset=["score"]).reset_index(drop=True)

    panel_lwc = panel.copy()
    panel_lwc["score"] = compute_score_lwc(panel_lwc, scale_col="sigma_hat_sym_pre_fri")
    panel_lwc = panel_lwc.dropna(subset=["score"]).reset_index(drop=True)

    print(f"M5 panel: {len(panel_m5):,} rows; LWC panel: {len(panel_lwc):,} rows",
          flush=True)

    # Fits on dense τ grid for both M5 and LWC
    dense_taus = tuple(sorted(set(DENSE_COVERAGE_GRID) | set(HEADLINE_TAUS)))
    train_m5 = panel_m5[panel_m5["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    oos_m5 = panel_m5[panel_m5["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    train_lwc = panel_lwc[panel_lwc["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    oos_lwc = panel_lwc[panel_lwc["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    qt_m5 = train_quantile_table(train_m5, cell_col="regime_pub", taus=dense_taus,
                                  score_col="score")
    cb_m5 = fit_c_bump_schedule(oos_m5, qt_m5, cell_col="regime_pub",
                                 taus=dense_taus, score_col="score")
    qt_lwc = train_quantile_table(train_lwc, cell_col="regime_pub",
                                   taus=dense_taus, score_col="score")
    cb_lwc = fit_c_bump_schedule(oos_lwc, qt_lwc, cell_col="regime_pub",
                                  taus=dense_taus, score_col="score")
    print(f"M5 c-bumps headline: {[(t, cb_m5[t]) for t in HEADLINE_TAUS]}",
          flush=True)
    print(f"LWC c-bumps headline: {[(t, cb_lwc[t]) for t in HEADLINE_TAUS]}",
          flush=True)

    # GARCH-t fits per symbol; recursive σ̂; OOS rows
    print("\nFitting GARCH(1,1)-t per symbol …", flush=True)
    garch_forecasts = fit_per_symbol_garch(panel, dist="t")
    garch_forecasts["fri_ts"] = pd.to_datetime(garch_forecasts["fri_ts"]).dt.date
    g_oos = (garch_forecasts[garch_forecasts["fri_ts"] >= SPLIT_DATE]
             .dropna(subset=["sigma_hat"]).reset_index(drop=True))
    print(f"GARCH-t OOS rows: {len(g_oos):,}", flush=True)

    # Align all three methods on the same OOS keys (intersection)
    keys_m5 = oos_m5[["symbol", "fri_ts"]].astype({"symbol": str})
    keys_lwc = oos_lwc[["symbol", "fri_ts"]].astype({"symbol": str})
    keys_g = g_oos[["symbol", "fri_ts"]].astype({"symbol": str})
    keys = keys_m5.merge(keys_lwc, on=["symbol", "fri_ts"]).merge(
        keys_g, on=["symbol", "fri_ts"]
    )
    print(f"Aligned OOS keys (intersection): {len(keys):,}", flush=True)

    panel_m5_a = oos_m5.merge(keys, on=["symbol", "fri_ts"]).sort_values(["symbol", "fri_ts"]).reset_index(drop=True)
    panel_lwc_a = oos_lwc.merge(keys, on=["symbol", "fri_ts"]).sort_values(["symbol", "fri_ts"]).reset_index(drop=True)
    panel_g_a = g_oos.merge(keys, on=["symbol", "fri_ts"]).sort_values(["symbol", "fri_ts"]).reset_index(drop=True)

    # Sanity: realized y is mon_open
    y = panel_lwc_a["mon_open"].astype(float).to_numpy()

    # Headline-τ Winkler
    rows = []
    for tau in HEADLINE_TAUS:
        # M5
        ll_m5, uu_m5 = m5_bounds_at_coverage(panel_m5_a, qt_m5, cb_m5, tau)
        ws_m5 = _winkler_interval_score(ll_m5, uu_m5, y, tau)
        # LWC
        ll_l, uu_l = lwc_bounds_at_coverage(panel_lwc_a, qt_lwc, cb_lwc, tau)
        ws_l = _winkler_interval_score(ll_l, uu_l, y, tau)
        # GARCH-t
        ll_g, uu_g = garch_bounds_at_coverage(panel_g_a, tau)
        ws_g = _winkler_interval_score(ll_g, uu_g, y, tau)

        # Normalise to bps of fri_close to make comparable at different τ
        fri_close = panel_lwc_a["fri_close"].astype(float).to_numpy()
        rows.append({
            "tau": tau,
            "n": int(len(y)),
            "winkler_M5_bps":     float(np.mean(ws_m5 / fri_close * 1e4)),
            "winkler_LWC_bps":    float(np.mean(ws_l / fri_close * 1e4)),
            "winkler_GARCH_t_bps": float(np.mean(ws_g / fri_close * 1e4)),
            "width_M5_bps":       float(np.mean((uu_m5 - ll_m5) / fri_close * 1e4)),
            "width_LWC_bps":      float(np.mean((uu_l - ll_l) / fri_close * 1e4)),
            "width_GARCH_t_bps":  float(np.mean((uu_g - ll_g) / fri_close * 1e4)),
        })
    df_w = pd.DataFrame(rows)
    print("\n=== Winkler interval score (bps of fri_close, lower better) ===")
    print(df_w.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # CRPS via dense coverage grid
    print("\nComputing CRPS via dense coverage grid …", flush=True)
    lwc_bands = [lwc_bounds_at_coverage(panel_lwc_a, qt_lwc, cb_lwc, c)
                 for c in DENSE_COVERAGE_GRID]
    lwc_lows = [b[0] for b in lwc_bands]
    lwc_his = [b[1] for b in lwc_bands]
    crps_l = crps_grid(lwc_lows, lwc_his, y, DENSE_COVERAGE_GRID)

    m5_bands = [m5_bounds_at_coverage(panel_m5_a, qt_m5, cb_m5, c)
                for c in DENSE_COVERAGE_GRID]
    m5_lows = [b[0] for b in m5_bands]
    m5_his = [b[1] for b in m5_bands]
    crps_m5 = crps_grid(m5_lows, m5_his, y, DENSE_COVERAGE_GRID)

    g_bands = [garch_bounds_at_coverage(panel_g_a, c) for c in DENSE_COVERAGE_GRID]
    g_lows = [b[0] for b in g_bands]
    g_his = [b[1] for b in g_bands]
    crps_g = crps_grid(g_lows, g_his, y, DENSE_COVERAGE_GRID)

    fri_close = panel_lwc_a["fri_close"].astype(float).to_numpy()
    crps_summary = {
        "method": ["M5_Mondrian", "M6_LWC_deployed", "GARCH(1,1)-t"],
        "crps_mean_price_units": [
            float(np.nanmean(crps_m5)),
            float(np.nanmean(crps_l)),
            float(np.nanmean(crps_g)),
        ],
        "crps_mean_bps_of_fri_close": [
            float(np.nanmean(crps_m5 / fri_close * 1e4)),
            float(np.nanmean(crps_l / fri_close * 1e4)),
            float(np.nanmean(crps_g / fri_close * 1e4)),
        ],
    }
    df_c = pd.DataFrame(crps_summary)
    print("\n=== CRPS (bps of fri_close, lower better) ===")
    print(df_c.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # Save
    out_w = REPORTS / "tables" / "paper1_c1_winkler_interval_score.csv"
    out_c = REPORTS / "tables" / "paper1_c1_crps.csv"
    df_w.to_csv(out_w, index=False)
    df_c.to_csv(out_c, index=False)
    print(f"\nwrote {out_w}\nwrote {out_c}", flush=True)


if __name__ == "__main__":
    main()
