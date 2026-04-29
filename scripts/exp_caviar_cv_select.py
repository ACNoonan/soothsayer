"""
Family A continuation — defensible per-symbol CAViaR selection via 3-fold
rolling time-series cross-validation on the pre-2023 calibration set.

Per methodology log entry 2026-04-28 (very late evening, Family A result
block). The oracle hybrid (SAV-for-SPY + AS-for-AAPL + baseline-for-rest)
passed all four scorecard thresholds at 1/10 reject — but that selection
used OOS-observed DQ patterns (data-snooping). Single-split calibration
DQ-based selection failed (6/10 reject). This script implements a
cleaner defensible scheme: 3-fold rolling time-series CV on the
calibration set; aggregate per-(symbol, method) DQ p-value across the
held-out folds; pick per-symbol method that minimizes median rejection
probability; apply selected methods to the FULL 2023+ OOS slice.

Folds (rolling expanding-window):
  Fold 1: fit on 2014-2018 cal (~260 wkends); eval on 2019 (~52 wkends)
  Fold 2: fit on 2014-2019 cal (~310 wkends); eval on 2020 (~52 wkends; COVID stress)
  Fold 3: fit on 2014-2020 cal (~370 wkends); eval on 2021-2022 (~104 wkends)

The 2023+ OOS slice is UNTOUCHED by the selection process.

Decision rule (per methodology log):
  PASS if per-symbol DQ reject-count ≤ 3/10 at τ=0.99 on OOS, AND HOOD
  is the only invariant.
  v1.5 deployment candidate if ≤ 2/10.
  Headline Paper-1 update if ≤ 1/10.
"""

from __future__ import annotations

import time
import warnings
from datetime import date

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import chi2 as _chi2

from soothsayer.backtest import forecasters as fc
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS

warnings.filterwarnings("ignore")

SPLIT_DATE = date(2023, 1, 1)
FOLD_BOUNDARIES = [
    (date(2014, 1, 1), date(2019, 1, 1), date(2020, 1, 1)),     # train_start, train_end, eval_end
    (date(2014, 1, 1), date(2020, 1, 1), date(2021, 1, 1)),
    (date(2014, 1, 1), date(2021, 1, 1), date(2023, 1, 1)),
]
WINDOW = 156
MIN_OBS = 50
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
TAIL_TAUS = (0.95, 0.99)
EXTRA_REGRESSORS = ("earnings_next_week_f", "is_long_weekend", "log_fri_vol_20d")
VOL_COL_BY_SYMBOL = {
    "SPY": "vix_fri_close", "QQQ": "vix_fri_close",
    "AAPL": "vix_fri_close", "GOOGL": "vix_fri_close",
    "NVDA": "vix_fri_close", "TSLA": "vix_fri_close",
    "HOOD": "vix_fri_close", "MSTR": "vix_fri_close",
    "GLD": "gvz_fri_close", "TLT": "move_fri_close",
}


def pinball_loss(quantile, observed, alpha):
    err = observed - quantile
    return float(np.where(err >= 0, alpha * err, (alpha - 1) * err).sum())


def caviar_sav_quantiles(params, residuals, q_init):
    b0, b1, b2 = params
    n = len(residuals)
    q = np.zeros(n)
    q[0] = q_init
    for t in range(1, n):
        q[t] = b0 + b1 * q[t - 1] + b2 * abs(residuals[t - 1])
    return q


def caviar_as_quantiles(params, residuals, q_init):
    b0, b1, b2, b3 = params
    n = len(residuals)
    q = np.zeros(n)
    q[0] = q_init
    for t in range(1, n):
        y_prev = residuals[t - 1]
        q[t] = b0 + b1 * q[t - 1] + b2 * max(y_prev, 0) + b3 * max(-y_prev, 0)
    return q


def caviar_sav_obj(params, residuals, alpha, q_init):
    b0, b1, b2 = params
    if not all(np.isfinite([b0, b1, b2])): return 1e10
    if abs(b1) > 0.999: return 1e10
    q = caviar_sav_quantiles(params, residuals, q_init)
    if not np.all(np.isfinite(q)): return 1e10
    return pinball_loss(q, residuals, alpha)


def caviar_as_obj(params, residuals, alpha, q_init):
    b0, b1, b2, b3 = params
    if not all(np.isfinite([b0, b1, b2, b3])): return 1e10
    if abs(b1) > 0.999: return 1e10
    q = caviar_as_quantiles(params, residuals, q_init)
    if not np.all(np.isfinite(q)): return 1e10
    return pinball_loss(q, residuals, alpha)


def fit_sav(residuals, alpha):
    if len(residuals) < 30:
        return (0.0, 0.0, 0.0)
    q_init = float(np.quantile(residuals, alpha))
    init = np.array([q_init * 0.15, 0.85, 0.05 if alpha < 0.5 else -0.05])
    try:
        result = minimize(caviar_sav_obj, init, args=(residuals, alpha, q_init),
                          method="Nelder-Mead", options={"maxiter": 500, "xatol": 1e-5, "fatol": 1e-6})
        return tuple(result.x)
    except Exception:
        return (0.0, 0.0, 0.0)


def fit_as(residuals, alpha):
    if len(residuals) < 30:
        return (0.0, 0.0, 0.0, 0.0)
    q_init = float(np.quantile(residuals, alpha))
    init = np.array([q_init * 0.15, 0.85,
                     0.05 if alpha < 0.5 else -0.05,
                     0.05 if alpha < 0.5 else -0.05])
    try:
        result = minimize(caviar_as_obj, init, args=(residuals, alpha, q_init),
                          method="Nelder-Mead", options={"maxiter": 800, "xatol": 1e-5, "fatol": 1e-6})
        return tuple(result.x)
    except Exception:
        return (0.0, 0.0, 0.0, 0.0)


def collect_residuals_per_symbol(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """For each symbol, produce a DataFrame with (fri_ts, resid_log)."""
    point_fa = fc.point_futures_adjusted(panel)
    out = {}
    for sym, idx in panel.groupby("symbol").groups.items():
        g = panel.loc[idx].sort_values("fri_ts")
        g_pfa = point_fa.loc[g.index]
        resid = np.log(g["mon_open"].astype(float).values / g_pfa.values)
        out[sym] = pd.DataFrame({
            "fri_ts": g["fri_ts"].values,
            "resid_log": resid,
        })
    return out


def replay_with_pooled_tail_baseline(panel: pd.DataFrame) -> pd.DataFrame:
    """Trial 3 + Trial 6 baseline (pooled-tail at τ ≥ 0.95, with state-augmented
    F1 σ regression). Returns the bound table for the full panel.
    """
    point_fa = fc.point_futures_adjusted(panel)
    extra_cols = list(EXTRA_REGRESSORS)
    cell_rows = []
    for sym, idx in panel.groupby("symbol").groups.items():
        g = panel.loc[idx].sort_values("fri_ts")
        g_pfa = point_fa.loc[g.index]
        vol_col = VOL_COL_BY_SYMBOL.get(sym, "vix_fri_close")
        vol = g[vol_col].astype(float).values
        resid_log = np.log(g["mon_open"].astype(float).values / g_pfa.values)
        extras = {col: g[col].astype(float).values if col in g.columns else np.zeros(len(g))
                  for col in extra_cols}
        fri_ts_arr = g["fri_ts"].values
        regime_arr = g["regime_pub"].values
        mon_open_arr = g["mon_open"].astype(float).values
        fri_close_arr = g["fri_close"].astype(float).values

        for i in range(len(g)):
            pfa_i = float(g_pfa.iloc[i]); vol_i = vol[i]
            if not np.isfinite(vol_i) or vol_i <= 0 or not np.isfinite(pfa_i):
                continue
            start = max(0, i - WINDOW)
            past_r = resid_log[start:i]; past_v = vol[start:i]
            past_extras = {col: arr[start:i] for col, arr in extras.items()}
            now_extras = {col: arr[i] for col, arr in extras.items()}
            valid = (np.isfinite(past_r) & np.isfinite(past_v) & (past_v > 0) & (np.abs(past_r) > 1e-10))
            for arr in past_extras.values(): valid &= np.isfinite(arr)
            if valid.sum() < MIN_OBS: continue
            r_v = past_r[valid]; v_v = past_v[valid]
            design = [np.ones(valid.sum()), np.log(v_v)]; kept = []
            for col in extra_cols:
                x_col = past_extras[col][valid]
                if np.nanstd(x_col) > 0:
                    design.append(x_col); kept.append(col)
            X = np.column_stack(design); y = np.log(np.abs(r_v))
            try:
                beta_hat, *_ = np.linalg.lstsq(X, y, rcond=None)
            except np.linalg.LinAlgError:
                continue
            alpha_p = beta_hat[0]; b = beta_hat[1]
            gammas = dict(zip(kept, beta_hat[2:]))
            sigma_hist_log = alpha_p + b * np.log(v_v)
            for col in kept:
                sigma_hist_log = sigma_hist_log + gammas[col] * past_extras[col][valid]
            sigma_hist = np.exp(sigma_hist_log)
            sigma_now_log = alpha_p + b * np.log(vol_i)
            for col in kept:
                v_now = now_extras[col]
                if not np.isfinite(v_now): v_now = float(np.nanmean(past_extras[col][valid]))
                sigma_now_log += gammas[col] * v_now
            sigma_now = float(np.exp(sigma_now_log))
            if sigma_now <= 0 or not np.isfinite(sigma_now): continue
            z_hist = r_v / sigma_hist
            cell_rows.append({
                "symbol": sym, "fri_ts": fri_ts_arr[i], "regime_pub": regime_arr[i],
                "pfa": pfa_i, "sigma_now": sigma_now,
                "mon_open": mon_open_arr[i], "fri_close": fri_close_arr[i],
                "z_hist": z_hist,
            })

    cells = pd.DataFrame(cell_rows)
    pooled_by_key = {}
    for (regime, fri_ts), g in cells.groupby(["regime_pub", "fri_ts"]):
        pooled_by_key[(regime, fri_ts)] = np.concatenate(g["z_hist"].values)

    out_rows = []
    for _, c in cells.iterrows():
        z_hist_pool = pooled_by_key[(c["regime_pub"], c["fri_ts"])]
        for tau in HEADLINE_TAUS:
            tail = (1 - tau) / 2
            if tau in TAIL_TAUS:
                z_lo = float(np.quantile(z_hist_pool, tail))
                z_hi = float(np.quantile(z_hist_pool, 1 - tail))
            else:
                z_lo = float(np.quantile(c["z_hist"], tail))
                z_hi = float(np.quantile(c["z_hist"], 1 - tail))
            lo = c["pfa"] * np.exp(z_lo * c["sigma_now"])
            hi = c["pfa"] * np.exp(z_hi * c["sigma_now"])
            out_rows.append({
                "symbol": c["symbol"], "fri_ts": c["fri_ts"], "regime_pub": c["regime_pub"],
                "target": tau, "mon_open": c["mon_open"], "fri_close": c["fri_close"],
                "lo_baseline": lo, "hi_baseline": hi,
                "pfa": c["pfa"], "sigma_now": c["sigma_now"],
            })
    return pd.DataFrame(out_rows)


def per_symbol_dq_at_tau99(bounds_subset: pd.DataFrame, lo_col: str, hi_col: str) -> pd.Series:
    """Compute per-symbol DQ p-value at τ=0.99 on a bounds subset. Returns Series indexed by symbol."""
    sub = bounds_subset[bounds_subset["target"] == 0.99].copy()
    sub["inside"] = ((sub["mon_open"] >= sub[lo_col]) & (sub["mon_open"] <= sub[hi_col])).astype(int)
    out = {}
    for sym, gg in sub.groupby("symbol"):
        v_g = (1 - gg["inside"].astype(int)).values
        if len(v_g) < 10:
            out[sym] = np.nan; continue
        res = met.dynamic_quantile_test(v_g, 0.99, n_lags=4)
        out[sym] = float(res["p_value"]) if np.isfinite(res["dq"]) else np.nan
    return pd.Series(out, name="p_value")


def add_caviar_bounds(bounds: pd.DataFrame, resid_by_sym: dict[str, pd.DataFrame],
                       fit_window_end: date, label: str) -> pd.DataFrame:
    """Add CAViaR-SAV and CAViaR-AS bounds to the bounds table. CAViaR fits use
    only data with fri_ts < fit_window_end (no leakage past the fold boundary).
    """
    caviar_q = {}
    for sym, rdf in resid_by_sym.items():
        cal = rdf[rdf["fri_ts"] < fit_window_end]["resid_log"].values
        cal = cal[np.isfinite(cal) & (np.abs(cal) > 1e-10)]
        if len(cal) < 100:
            caviar_q[sym] = None; continue
        sav_lo_p = fit_sav(cal, 0.005); sav_hi_p = fit_sav(cal, 0.995)
        as_lo_p = fit_as(cal, 0.005);  as_hi_p = fit_as(cal, 0.995)
        # Initialize from cal-set empirical quantiles
        q_init_lo = float(np.quantile(cal, 0.005))
        q_init_hi = float(np.quantile(cal, 0.995))
        # Compute on the FULL panel (not just cal) — use the residuals from rdf
        residuals = rdf["resid_log"].values
        r_clean = np.where(np.isfinite(residuals) & (np.abs(residuals) > 1e-10), residuals, 0.0)
        sav_lo_seq = caviar_sav_quantiles(sav_lo_p, r_clean, q_init_lo)
        sav_hi_seq = caviar_sav_quantiles(sav_hi_p, r_clean, q_init_hi)
        as_lo_seq = caviar_as_quantiles(as_lo_p, r_clean, q_init_lo)
        as_hi_seq = caviar_as_quantiles(as_hi_p, r_clean, q_init_hi)
        caviar_q[sym] = {
            "fri_ts": rdf["fri_ts"].values,
            "sav_lo": sav_lo_seq, "sav_hi": sav_hi_seq,
            "as_lo": as_lo_seq, "as_hi": as_hi_seq,
        }

    # Map to bounds rows
    sav_lo_col = []; sav_hi_col = []; as_lo_col = []; as_hi_col = []
    for r in bounds.itertuples():
        if caviar_q.get(r.symbol) is None:
            sav_lo_col.append(np.nan); sav_hi_col.append(np.nan)
            as_lo_col.append(np.nan); as_hi_col.append(np.nan)
            continue
        ts_match = (caviar_q[r.symbol]["fri_ts"] == r.fri_ts)
        if not ts_match.any():
            sav_lo_col.append(np.nan); sav_hi_col.append(np.nan)
            as_lo_col.append(np.nan); as_hi_col.append(np.nan)
            continue
        j = int(np.argmax(ts_match))
        sav_lo = caviar_q[r.symbol]["sav_lo"][j]
        sav_hi = caviar_q[r.symbol]["sav_hi"][j]
        as_lo = caviar_q[r.symbol]["as_lo"][j]
        as_hi = caviar_q[r.symbol]["as_hi"][j]
        # Convert q (log-space) → bound (price-space) using r.pfa
        sav_lo_col.append(r.pfa * np.exp(sav_lo) if np.isfinite(sav_lo) else np.nan)
        sav_hi_col.append(r.pfa * np.exp(sav_hi) if np.isfinite(sav_hi) else np.nan)
        as_lo_col.append(r.pfa * np.exp(as_lo) if np.isfinite(as_lo) else np.nan)
        as_hi_col.append(r.pfa * np.exp(as_hi) if np.isfinite(as_hi) else np.nan)
    out = bounds.copy()
    out[f"lo_sav_{label}"] = sav_lo_col
    out[f"hi_sav_{label}"] = sav_hi_col
    out[f"lo_as_{label}"] = as_lo_col
    out[f"hi_as_{label}"] = as_hi_col
    return out


def run_diag_battery(served: pd.DataFrame, bound_cols: tuple[str, str], label: str) -> dict:
    lo_col, hi_col = bound_cols
    rows = []
    per_symbol_rows = []
    for tau in HEADLINE_TAUS:
        sub = served[served["target"] == tau].copy()
        sub["inside"] = ((sub["mon_open"] >= sub[lo_col]) & (sub["mon_open"] <= sub[hi_col])).astype(int)
        sub["half_width_bps"] = ((sub[hi_col] - sub[lo_col]) / 2.0 / sub["fri_close"] * 1e4)
        sub = sub.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)
        v_pooled = (1 - sub["inside"].values).astype(int)
        kup_lr, kup_p = met._lr_kupiec(v_pooled, tau)
        chr_lr, chr_p = met._lr_christoffersen_independence(v_pooled)
        dq_total, dq_df_total = 0.0, 0
        per_sym_p = []
        for sym, gg in sub.groupby("symbol"):
            v_g = (1 - gg["inside"].astype(int)).values
            if len(v_g) < 10: continue
            res = met.dynamic_quantile_test(v_g, tau, n_lags=4)
            if np.isfinite(res["dq"]):
                dq_total += res["dq"]; dq_df_total += res["df"]
                per_sym_p.append(float(res["p_value"]))
                per_symbol_rows.append({"label": label, "target": tau, "symbol": sym,
                                        "n": int(res["n"]), "dq": float(res["dq"]),
                                        "p_value": float(res["p_value"])})
        p_dq_pooled = (float(1.0 - _chi2.cdf(max(dq_total, 0.0), df=max(dq_df_total, 1)))
                       if dq_df_total > 0 else float("nan"))
        arr = np.array(per_sym_p) if per_sym_p else np.array([float("nan")])
        n_reject_05 = int((arr < 0.05).sum()) if per_sym_p else 0
        rows.append({
            "label": label, "target": tau, "n": int(len(sub)),
            "realised": float(sub["inside"].mean()),
            "n_violations": int((1 - sub["inside"]).sum()),
            "mean_hw_bps": float(sub["half_width_bps"].mean()),
            "kupiec_p": float(kup_p), "christoffersen_p": float(chr_p),
            "p_dq_pooled": p_dq_pooled, "n_symbols_reject_05": n_reject_05,
        })
    return {"summary": pd.DataFrame(rows), "per_symbol": pd.DataFrame(per_symbol_rows)}


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    panel["log_fri_vol_20d"] = np.log(panel["fri_vol_20d"].astype(float).clip(lower=1e-6))
    print(f"Full panel: {len(panel):,} rows", flush=True)

    print("\n--- Computing pooled-tail+state-aug baseline (Trial 3 + 6) ---", flush=True)
    t0 = time.time()
    bounds = replay_with_pooled_tail_baseline(panel)
    print(f"  Done in {time.time()-t0:.1f}s; {len(bounds):,} rows", flush=True)

    resid_by_sym = collect_residuals_per_symbol(panel)

    # --- Cross-validation: 3 folds, per-(symbol, method) DQ on each held-out fold ---
    print("\n--- Cross-validation: per-fold per-symbol per-method DQ ---", flush=True)
    cv_results = []  # list of dicts: {fold, symbol, method, p_value}
    for fi, (train_start, train_end, eval_end) in enumerate(FOLD_BOUNDARIES):
        print(f"  Fold {fi+1}: fit on [{train_start}, {train_end}); eval on [{train_end}, {eval_end})", flush=True)
        # Add CAViaR bounds fit on data < train_end
        bounds_fold = add_caviar_bounds(bounds, resid_by_sym, train_end, label=f"fold{fi+1}")
        # Restrict to eval-fold rows
        eval_mask = (bounds_fold["fri_ts"] >= train_end) & (bounds_fold["fri_ts"] < eval_end)
        eval_bounds = bounds_fold[eval_mask].reset_index(drop=True)

        # Per-symbol DQ on each method
        for method, lo_col, hi_col in [
            ("baseline", "lo_baseline", "hi_baseline"),
            ("sav", f"lo_sav_fold{fi+1}", f"hi_sav_fold{fi+1}"),
            ("as", f"lo_as_fold{fi+1}", f"hi_as_fold{fi+1}"),
        ]:
            p_by_sym = per_symbol_dq_at_tau99(eval_bounds, lo_col, hi_col)
            for sym, pv in p_by_sym.items():
                cv_results.append({"fold": fi+1, "symbol": sym, "method": method, "p_value": pv})

    cv_df = pd.DataFrame(cv_results)
    print(f"\nCV results: {len(cv_df):,} (fold, symbol, method) cells", flush=True)

    # Aggregate per-(symbol, method) median p-value across folds
    agg = (cv_df.groupby(["symbol", "method"])["p_value"]
           .agg([("median_p", lambda s: float(np.nanmedian(s))),
                 ("min_p", lambda s: float(np.nanmin(s))),
                 ("n_folds_present", lambda s: int(s.notna().sum())),
                 ("n_folds_reject_05", lambda s: int((s < 0.05).sum()))])
           .reset_index())
    print("\n=== CV-aggregated per-symbol per-method (median p across folds) ===", flush=True)
    pivot = agg.pivot(index="symbol", columns="method", values="median_p")
    pivot.columns = [f"med_p_{c}" for c in pivot.columns]
    print(pivot.round(4).to_string())
    print()
    pivot_rej = agg.pivot(index="symbol", columns="method", values="n_folds_reject_05")
    pivot_rej.columns = [f"n_rej_{c}" for c in pivot_rej.columns]
    print(pivot_rej.to_string())

    # Selection rule: pick method with highest median p-value across folds.
    # Default to baseline if all methods all-NaN (e.g. HOOD insufficient calibration).
    def _select_per_symbol(group):
        finite = group.dropna(subset=["median_p"])
        if finite.empty:
            return group[group["method"] == "baseline"].iloc[0]
        return finite.loc[finite["median_p"].idxmax()]
    sel = agg.groupby("symbol", as_index=False).apply(_select_per_symbol)[["symbol", "method", "median_p", "n_folds_reject_05"]]
    sel = sel.set_index("symbol")
    print(f"\n=== Defensible per-symbol selection (highest CV-median p, baseline fallback) ===", flush=True)
    print(sel.to_string())

    # --- Refit CAViaR on FULL pre-2023 calibration; apply to OOS using selected per-symbol method ---
    print("\n--- Refitting CAViaR on full pre-2023; applying selection to OOS ---", flush=True)
    bounds_final = add_caviar_bounds(bounds, resid_by_sym, SPLIT_DATE, label="full")
    bounds_oos = bounds_final[bounds_final["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    # Build defensible bounds: per-symbol method from sel
    bounds_oos["lo_def"] = bounds_oos["lo_baseline"]
    bounds_oos["hi_def"] = bounds_oos["hi_baseline"]
    for sym, row in sel.iterrows():
        method = row["method"]
        if method == "baseline":
            continue
        mask = (bounds_oos["symbol"] == sym) & (bounds_oos["target"] == 0.99)
        if method == "sav":
            bounds_oos.loc[mask, "lo_def"] = bounds_oos.loc[mask, "lo_sav_full"]
            bounds_oos.loc[mask, "hi_def"] = bounds_oos.loc[mask, "hi_sav_full"]
        elif method == "as":
            bounds_oos.loc[mask, "lo_def"] = bounds_oos.loc[mask, "lo_as_full"]
            bounds_oos.loc[mask, "hi_def"] = bounds_oos.loc[mask, "hi_as_full"]

    # Diagnostic battery on the defensible bounds + baseline + oracle for comparison
    # Build oracle bounds (SAV-for-SPY, AS-for-AAPL, baseline-rest)
    bounds_oos["lo_oracle"] = bounds_oos["lo_baseline"]
    bounds_oos["hi_oracle"] = bounds_oos["hi_baseline"]
    mask_spy = (bounds_oos["symbol"] == "SPY") & (bounds_oos["target"] == 0.99)
    mask_aapl = (bounds_oos["symbol"] == "AAPL") & (bounds_oos["target"] == 0.99)
    bounds_oos.loc[mask_spy, "lo_oracle"] = bounds_oos.loc[mask_spy, "lo_sav_full"]
    bounds_oos.loc[mask_spy, "hi_oracle"] = bounds_oos.loc[mask_spy, "hi_sav_full"]
    bounds_oos.loc[mask_aapl, "lo_oracle"] = bounds_oos.loc[mask_aapl, "lo_as_full"]
    bounds_oos.loc[mask_aapl, "hi_oracle"] = bounds_oos.loc[mask_aapl, "hi_as_full"]

    print("\n=== Baseline (Trial 3 + Trial 6) ===", flush=True)
    res_base = run_diag_battery(bounds_oos, ("lo_baseline", "hi_baseline"), label="baseline")
    print(res_base["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Defensible (CV-selected per-symbol) ===", flush=True)
    res_def = run_diag_battery(bounds_oos, ("lo_def", "hi_def"), label="defensible")
    print(res_def["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Oracle (OOS-DQ-selected, upper bound) ===", flush=True)
    res_oracle = run_diag_battery(bounds_oos, ("lo_oracle", "hi_oracle"), label="oracle")
    print(res_oracle["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Per-symbol DQ at τ=0.99 — Baseline vs Defensible vs Oracle ===", flush=True)
    bp = res_base["per_symbol"][res_base["per_symbol"]["target"] == 0.99].set_index("symbol")[["p_value"]].rename(columns={"p_value": "p_base"})
    dp = res_def["per_symbol"][res_def["per_symbol"]["target"] == 0.99].set_index("symbol")[["p_value"]].rename(columns={"p_value": "p_def"})
    op = res_oracle["per_symbol"][res_oracle["per_symbol"]["target"] == 0.99].set_index("symbol")[["p_value"]].rename(columns={"p_value": "p_oracle"})
    cmp = bp.join(dp).join(op).join(sel[["method"]]).sort_index()
    cmp["base_R"] = cmp["p_base"] < 0.05
    cmp["def_R"] = cmp["p_def"] < 0.05
    cmp["orc_R"] = cmp["p_oracle"] < 0.05
    print(cmp.to_string(float_format=lambda x: f"{x:.4f}"))

    # Persist
    out_dir = REPORTS / "tables"
    summary = pd.concat([res_base["summary"], res_def["summary"], res_oracle["summary"]], ignore_index=True)
    per_sym = pd.concat([res_base["per_symbol"], res_def["per_symbol"], res_oracle["per_symbol"]], ignore_index=True)
    summary.to_csv(out_dir / "v1b_oos_caviar_cv_summary.csv", index=False)
    per_sym.to_csv(out_dir / "v1b_oos_dq_per_symbol_caviar_cv.csv", index=False)
    cv_df.to_csv(out_dir / "v1b_caviar_cv_per_fold.csv", index=False)
    sel.to_csv(out_dir / "v1b_caviar_cv_selection.csv")

    print("\n" + "=" * 80)
    print("DECISION SCORECARD — Family A continuation (defensible CV selection) at τ = 0.99")
    print("=" * 80)
    base_99 = res_base["summary"][res_base["summary"]["target"] == 0.99].iloc[0]
    def_99 = res_def["summary"][res_def["summary"]["target"] == 0.99].iloc[0]
    orc_99 = res_oracle["summary"][res_oracle["summary"]["target"] == 0.99].iloc[0]
    cap = 1.5 * base_99["mean_hw_bps"]
    print(f"  Per-symbol DQ rejects ≤ 3/10:   base {int(base_99['n_symbols_reject_05'])}/10  "
          f"|  defensible {int(def_99['n_symbols_reject_05'])}/10  "
          f"|  oracle {int(orc_99['n_symbols_reject_05'])}/10")
    print(f"  Realised (target 0.99):          base {base_99['realised']:.3f}  "
          f"|  defensible {def_99['realised']:.3f}  |  oracle {orc_99['realised']:.3f}")
    print(f"  Christoffersen p_ind > 0.05:     base {base_99['christoffersen_p']:.3f}  "
          f"|  defensible {def_99['christoffersen_p']:.3f}  |  oracle {orc_99['christoffersen_p']:.3f}")
    print(f"  Bandwidth (cap {cap:.0f} bps):        base {base_99['mean_hw_bps']:.0f}  "
          f"|  defensible {def_99['mean_hw_bps']:.0f}  |  oracle {orc_99['mean_hw_bps']:.0f}")
    print(f"\n  DEFENSIBLE scorecard:")
    print(f"    Threshold 1 (DQ ≤ 3/10):    PASS: {def_99['n_symbols_reject_05'] <= 3}")
    print(f"    Threshold 2 (realised ±2pp): PASS: {abs(def_99['realised'] - 0.99) <= 0.02}")
    print(f"    Threshold 3 (Chr p > 0.05):  PASS: {def_99['christoffersen_p'] > 0.05}")
    print(f"    Threshold 4 (BW ≤ 1.5×):    PASS: {def_99['mean_hw_bps'] <= cap}")


if __name__ == "__main__":
    main()
