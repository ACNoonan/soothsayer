"""
Trial 1 — EVT/POT (Generalized Pareto Distribution) for τ ≥ 0.95 anchors.

Standalone experiment per methodology log entry 2026-04-28 (late evening).
Replicates the F1 log-log fit pipeline; for each (symbol, fri_ts) it
computes the τ=0.99 (and τ=0.95) quantile of the standardized residuals
two ways:

  * empirical:  np.quantile(z_hist, 1 - tail)   ← current production
  * gpd:        Pickands-Balkema-de Haan extrapolation from a GPD
                fit on threshold exceedances above the 95th percentile.

Outputs the side-by-side bounds, then runs the same per-symbol DQ +
Kupiec + Christoffersen + exceedance-magnitude battery as
run_reviewer_diagnostics.py on the GPD-modified bounds.

Decision threshold (per methodology log):
  1. Per-symbol DQ reject-count at α=0.05 ≤ 3/10  (baseline 5/10)
  2. Pooled realised at τ=0.99 within ±2pp        (baseline 0.977)
  3. Pooled Christoffersen p_ind > 0.05            (baseline 0.956)
  4. Mean half-width at τ=0.99 ≤ 1.5× empirical    (baseline 580.8 bps)
"""

from __future__ import annotations

import time
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import chi2 as _chi2
from scipy.stats import genpareto

from soothsayer.backtest import forecasters as fc
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
WINDOW = 156
MIN_OBS = 50
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
GPD_THRESHOLD_Q = 0.90   # fit GPD on residuals above the 90th percentile (McNeil-Frey default; n=156 → ~15 exceedances per fit)
TAIL_TAUS = (0.95, 0.99)  # GPD path applies only at τ ≥ 0.95
MIN_EXCEEDANCES = 8      # minimum exceedances for GPD fit
EXTRA_REGRESSORS = ("earnings_next_week_f", "is_long_weekend")
VOL_COL_BY_SYMBOL = {  # mirrors panel.build VOL_INDEX_BY_SYMBOL
    "SPY": "vix_fri_close", "QQQ": "vix_fri_close",
    "AAPL": "vix_fri_close", "GOOGL": "vix_fri_close",
    "NVDA": "vix_fri_close", "TSLA": "vix_fri_close",
    "HOOD": "vix_fri_close", "MSTR": "vix_fri_close",
    "GLD": "gvz_fri_close", "TLT": "move_fri_close",
}


def gpd_tail_quantile(z_hist: np.ndarray, target_q: float, side: str = "upper") -> tuple[float, float, float, int]:
    """Estimate the target_q quantile of z_hist using a GPD fit on threshold
    exceedances. side='upper' for q > 0.5; side='lower' for q < 0.5.

    Returns (quantile, xi, sigma, n_excess). NaNs if fit fails.
    """
    if side == "upper":
        u = float(np.quantile(z_hist, GPD_THRESHOLD_Q))
        excess = z_hist[z_hist > u] - u
        # Conditional tail prob: Pr(X > x | X > u) = (1 - target_q) / (1 - GPD_THRESHOLD_Q)
        p_cond = (1.0 - target_q) / (1.0 - GPD_THRESHOLD_Q)
    else:
        u = float(np.quantile(z_hist, 1.0 - GPD_THRESHOLD_Q))
        excess = u - z_hist[z_hist < u]
        # Pr(X < x | X < u) = target_q / (1 - GPD_THRESHOLD_Q) for the symmetric setup
        p_cond = target_q / (1.0 - GPD_THRESHOLD_Q)

    n_excess = int(len(excess))
    if n_excess < MIN_EXCEEDANCES:
        return float("nan"), float("nan"), float("nan"), n_excess
    # GPD fit with location fixed at 0 (excesses already shifted)
    try:
        xi, _, sigma = genpareto.fit(excess, floc=0)
    except Exception:
        return float("nan"), float("nan"), float("nan"), n_excess
    if not (np.isfinite(xi) and np.isfinite(sigma) and sigma > 0):
        return float("nan"), float(xi), float(sigma), n_excess

    # Quantile inversion. p_cond is the conditional tail prob beyond u.
    # The magnitude of the excess at that prob is computed from the GPD CDF inversion.
    if abs(xi) < 1e-6:
        excess_q = -sigma * np.log(max(p_cond, 1e-12))
    else:
        excess_q = (sigma / xi) * (max(p_cond, 1e-12)**(-xi) - 1.0)
    if not np.isfinite(excess_q):
        return float("nan"), float(xi), float(sigma), n_excess

    if side == "upper":
        return u + excess_q, float(xi), float(sigma), n_excess
    else:
        return u - excess_q, float(xi), float(sigma), n_excess


def replay_f1_fit_with_gpd(panel: pd.DataFrame) -> pd.DataFrame:
    """Replay the per-(symbol, fri_ts) F1 log-log fit, capturing z_hist and
    computing both empirical and GPD quantiles at τ ∈ HEADLINE_TAUS for τ ≥ 0.95.
    Returns a long-form DataFrame with one row per (symbol, fri_ts, target).
    """
    point_fa = fc.point_futures_adjusted(panel)
    out_rows: list[dict] = []
    extra_cols = list(EXTRA_REGRESSORS)

    for sym, idx in panel.groupby("symbol").groups.items():
        g = panel.loc[idx].sort_values("fri_ts")
        g_pfa = point_fa.loc[g.index]
        vol_col = VOL_COL_BY_SYMBOL.get(sym, "vix_fri_close")
        vol = g[vol_col].astype(float).values
        resid_log = np.log(g["mon_open"].astype(float).values / g_pfa.values)
        extras = {col: g[col].astype(float).values if col in g.columns else np.zeros(len(g))
                  for col in extra_cols}
        fri_ts_arr = g["fri_ts"].values
        regime_arr = g["regime_pub"].values if "regime_pub" in g.columns else np.array([""] * len(g))
        mon_open_arr = g["mon_open"].astype(float).values
        fri_close_arr = g["fri_close"].astype(float).values

        for i in range(len(g)):
            pfa_i = float(g_pfa.iloc[i])
            vol_i = vol[i]
            if not np.isfinite(vol_i) or vol_i <= 0 or not np.isfinite(pfa_i):
                continue
            start = max(0, i - WINDOW)
            past_r = resid_log[start:i]
            past_v = vol[start:i]
            past_extras = {col: arr[start:i] for col, arr in extras.items()}
            now_extras = {col: arr[i] for col, arr in extras.items()}

            valid = (np.isfinite(past_r) & np.isfinite(past_v) & (past_v > 0)
                     & (np.abs(past_r) > 1e-10))
            for arr in past_extras.values():
                valid &= np.isfinite(arr)
            if valid.sum() < MIN_OBS:
                continue

            r_v = past_r[valid]
            v_v = past_v[valid]
            design = [np.ones(valid.sum()), np.log(v_v)]
            kept = []
            for col in extra_cols:
                x_col = past_extras[col][valid]
                if np.nanstd(x_col) > 0:
                    design.append(x_col)
                    kept.append(col)
            X = np.column_stack(design)
            y = np.log(np.abs(r_v))
            try:
                beta_hat, *_ = np.linalg.lstsq(X, y, rcond=None)
            except np.linalg.LinAlgError:
                continue
            alpha = beta_hat[0]
            b = beta_hat[1]
            gammas = dict(zip(kept, beta_hat[2:]))

            sigma_hist_log = alpha + b * np.log(v_v)
            for col in kept:
                sigma_hist_log = sigma_hist_log + gammas[col] * past_extras[col][valid]
            sigma_hist = np.exp(sigma_hist_log)
            sigma_now_log = alpha + b * np.log(vol_i)
            for col in kept:
                sigma_now_log += gammas[col] * now_extras[col]
            sigma_now = float(np.exp(sigma_now_log))
            if sigma_now <= 0 or not np.isfinite(sigma_now):
                continue
            z_hist = r_v / sigma_hist

            for tau in HEADLINE_TAUS:
                tail = (1 - tau) / 2
                # Empirical (current production)
                z_lo_emp = float(np.quantile(z_hist, tail))
                z_hi_emp = float(np.quantile(z_hist, 1 - tail))
                lo_emp = pfa_i * np.exp(z_lo_emp * sigma_now)
                hi_emp = pfa_i * np.exp(z_hi_emp * sigma_now)

                # GPD only for τ ≥ 0.95 (lower tau uses the empirical bounds)
                if tau in TAIL_TAUS:
                    z_hi_gpd, xi_u, sig_u, nex_u = gpd_tail_quantile(z_hist, 1 - tail, side="upper")
                    z_lo_gpd, xi_l, sig_l, nex_l = gpd_tail_quantile(z_hist, tail, side="lower")
                    if np.isfinite(z_hi_gpd) and np.isfinite(z_lo_gpd):
                        lo_gpd = pfa_i * np.exp(z_lo_gpd * sigma_now)
                        hi_gpd = pfa_i * np.exp(z_hi_gpd * sigma_now)
                    else:
                        lo_gpd = float("nan"); hi_gpd = float("nan")
                else:
                    lo_gpd = lo_emp; hi_gpd = hi_emp
                    xi_u = sig_u = nex_u = xi_l = sig_l = nex_l = float("nan")

                out_rows.append({
                    "symbol": sym, "fri_ts": fri_ts_arr[i], "regime_pub": regime_arr[i],
                    "target": tau,
                    "mon_open": mon_open_arr[i], "fri_close": fri_close_arr[i],
                    "lo_emp": lo_emp, "hi_emp": hi_emp,
                    "lo_gpd": lo_gpd, "hi_gpd": hi_gpd,
                    "n_window": int(valid.sum()),
                    "xi_upper": xi_u, "sigma_upper": sig_u, "n_excess_upper": nex_u,
                    "xi_lower": xi_l, "sigma_lower": sig_l, "n_excess_lower": nex_l,
                })

    return pd.DataFrame(out_rows)


def run_diag_battery(served: pd.DataFrame, bound_cols: tuple[str, str], label: str) -> dict:
    """Run per-τ DQ + per-symbol DQ + Kupiec + Christoffersen + exceedance magnitude
    on the served panel, using bound_cols (lower, upper) at each row. Returns a dict
    with one entry per (target, statistic).
    """
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
        realised = float(sub["inside"].mean())
        n_violations = int((1 - sub["inside"]).sum())
        mean_hw = float(sub["half_width_bps"].mean())

        # DQ pooled (sum of per-symbol χ² as in run_reviewer_diagnostics.py)
        dq_total, dq_df_total = 0.0, 0
        per_sym_p = []
        for sym, gg in sub.groupby("symbol"):
            v_g = (1 - gg["inside"].astype(int)).values
            if len(v_g) < 10:
                continue
            res = met.dynamic_quantile_test(v_g, tau, n_lags=4)
            if np.isfinite(res["dq"]):
                dq_total += res["dq"]; dq_df_total += res["df"]
                per_sym_p.append(float(res["p_value"]))
                per_symbol_rows.append({
                    "label": label, "target": tau, "symbol": sym,
                    "n": int(res["n"]), "dq": float(res["dq"]),
                    "p_value": float(res["p_value"]),
                })
        p_dq_pooled = (float(1.0 - _chi2.cdf(max(dq_total, 0.0), df=max(dq_df_total, 1)))
                       if dq_df_total > 0 else float("nan"))
        per_sym_arr = np.array(per_sym_p) if per_sym_p else np.array([float("nan")])
        median_p = float(np.median(per_sym_arr)) if per_sym_p else float("nan")
        n_reject_05 = int((per_sym_arr < 0.05).sum()) if per_sym_p else 0

        # Exceedance magnitude
        breach = []
        for _, r in sub[sub["inside"] == 0].iterrows():
            if r["mon_open"] < r[lo_col]:
                breach.append((r[lo_col] - r["mon_open"]) / r["fri_close"] * 1e4)
            elif r["mon_open"] > r[hi_col]:
                breach.append((r["mon_open"] - r[hi_col]) / r["fri_close"] * 1e4)
        breach = np.array(breach) if breach else np.array([0.0])

        rows.append({
            "label": label, "target": tau, "n": int(len(sub)),
            "realised": realised, "n_violations": n_violations,
            "mean_hw_bps": mean_hw,
            "kupiec_lr": float(kup_lr), "kupiec_p": float(kup_p),
            "christoffersen_lr": float(chr_lr), "christoffersen_p": float(chr_p),
            "dq_pooled": dq_total, "dq_df": dq_df_total, "p_dq_pooled": p_dq_pooled,
            "p_dq_per_symbol_median": median_p,
            "n_symbols_reject_05": n_reject_05,
            "n_breach": int((1 - sub["inside"]).sum()),
            "breach_mean_bps": float(np.mean(breach)) if len(breach) else float("nan"),
            "breach_max_bps": float(np.max(breach)) if len(breach) else float("nan"),
            "breach_p95_bps": float(np.percentile(breach, 95)) if len(breach) else float("nan"),
        })
    return {"summary": pd.DataFrame(rows), "per_symbol": pd.DataFrame(per_symbol_rows)}


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    print(f"Full panel: {len(panel):,} rows", flush=True)

    t0 = time.time()
    bounds_long = replay_f1_fit_with_gpd(panel)
    print(f"\nF1+GPD fit complete in {time.time()-t0:.1f}s; "
          f"{len(bounds_long):,} (symbol, fri_ts, target) rows", flush=True)

    # OOS slice
    bounds_oos = bounds_long[bounds_long["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"OOS slice: {len(bounds_oos):,} rows in {bounds_oos['fri_ts'].nunique()} weekends", flush=True)

    # Diagnostic battery — empirical baseline vs GPD swap
    print("\n=== Empirical (baseline replay) ===", flush=True)
    res_emp = run_diag_battery(bounds_oos, ("lo_emp", "hi_emp"), label="empirical")
    print(res_emp["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== GPD (Trial 1) ===", flush=True)
    res_gpd = run_diag_battery(bounds_oos, ("lo_gpd", "hi_gpd"), label="gpd")
    print(res_gpd["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Per-symbol DQ — GPD ===", flush=True)
    print(res_gpd["per_symbol"].sort_values(["target", "symbol"]).to_string(
        index=False, float_format=lambda x: f"{x:.4f}"))

    # Persist
    out_dir = REPORTS / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.concat([res_emp["summary"], res_gpd["summary"]], ignore_index=True)
    per_symbol = pd.concat([res_emp["per_symbol"], res_gpd["per_symbol"]], ignore_index=True)
    bounds_oos.to_parquet(DATA_PROCESSED / "exp_evt_pot_bounds.parquet", index=False)
    summary.to_csv(out_dir / "v1b_oos_evt_pot_summary.csv", index=False)
    per_symbol.to_csv(out_dir / "v1b_oos_dq_per_symbol_evt.csv", index=False)
    print(f"\nWrote {out_dir / 'v1b_oos_evt_pot_summary.csv'}")
    print(f"Wrote {out_dir / 'v1b_oos_dq_per_symbol_evt.csv'}")
    print(f"Wrote {DATA_PROCESSED / 'exp_evt_pot_bounds.parquet'}")

    # === Decision scorecard ===
    print("\n" + "=" * 80)
    print("DECISION SCORECARD — Trial 1 (EVT/POT) at τ = 0.99")
    print("=" * 80)
    emp_99 = res_emp["summary"][res_emp["summary"]["target"] == 0.99].iloc[0]
    gpd_99 = res_gpd["summary"][res_gpd["summary"]["target"] == 0.99].iloc[0]
    cap_hw = 1.5 * emp_99["mean_hw_bps"]
    print(f"  Threshold 1: per-symbol DQ reject-count ≤ 3/10")
    print(f"    empirical: {int(emp_99['n_symbols_reject_05'])}/10   "
          f"gpd: {int(gpd_99['n_symbols_reject_05'])}/10   "
          f"PASS: {gpd_99['n_symbols_reject_05'] <= 3}")
    print(f"  Threshold 2: pooled realised within ±2pp of 0.99")
    print(f"    empirical: {emp_99['realised']:.3f}   gpd: {gpd_99['realised']:.3f}   "
          f"PASS: {abs(gpd_99['realised'] - 0.99) <= 0.02}")
    print(f"  Threshold 3: Christoffersen p_ind > 0.05")
    print(f"    empirical: {emp_99['christoffersen_p']:.3f}   gpd: {gpd_99['christoffersen_p']:.3f}   "
          f"PASS: {gpd_99['christoffersen_p'] > 0.05}")
    print(f"  Threshold 4: mean half-width ≤ 1.5× empirical (cap = {cap_hw:.0f} bps)")
    print(f"    empirical: {emp_99['mean_hw_bps']:.0f} bps   gpd: {gpd_99['mean_hw_bps']:.0f} bps   "
          f"PASS: {gpd_99['mean_hw_bps'] <= cap_hw}")


if __name__ == "__main__":
    main()
