"""
Family B — Two-tailed Peaks-Over-Threshold Hawkes (2T-POT Hawkes) for τ=0.99
quantile estimation, applied to all 10 symbols.

Per methodology log entry 2026-04-28 (very late evening, +5). The Family A
CV-defensible result closed 2 of 3 structural rejectors (AAPL via CAViaR-AS,
SPY via CAViaR-SAV) and isolated HOOD as the sole remaining residual.
Family B targets the SELF-EXCITING tail-clustering mechanism — empirically:
post-shock weekends carry elevated tail risk because past tail events
trigger future ones (earnings cycles, post-event recovery, meme-stock
contagion).

Hawkes-POT decomposes tail behaviour into two layers:

  1. INTENSITY (when does the next exceedance occur?):
     λ(t) = μ + Σ_{t_i < t} α · exp(-β(t - t_i))
     Self-excitation: each past exceedance lifts the intensity by α,
     decaying at rate β. Fit by MLE on per-symbol exceedance times above
     the 90th-percentile threshold.

  2. MAGNITUDE (how big when it does?):
     GPD(ξ, σ) on the per-symbol exceedance magnitudes |r_t - u|.

Conditional VaR at level α:
  VaR_t(α) = u + GPD-quantile(α_eff)
  where α_eff = α · (μ_uncond / λ(t))  -- when intensity is HIGH, effective
  tail probability inflates → need a smaller α_eff → wider quantile.

Hypothesis (per methodology log):
  H1: For HOOD specifically, the post-IPO + meme-stock-era event clustering
      generates Hawkes self-excitation (α/β) that the cross-sectional pooled
      methodology cannot capture. Hawkes-POT should fix HOOD's τ=0.99 reject.
  H2: For other symbols where CAViaR + baseline already pass, Hawkes-POT
      should at minimum not regress.

Decision threshold: same four-threshold scorecard. Headline goal: HOOD
flips from reject → pass at τ=0.99.

Implementation: standalone, parallel-style to exp_caviar_*.py. Fits Hawkes
once-per-symbol on pre-2023 calibration data; applies forward to OOS.
"""

from __future__ import annotations

import time
import warnings
from datetime import date

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import chi2 as _chi2
from scipy.stats import genpareto

from soothsayer.backtest import forecasters as fc
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS

warnings.filterwarnings("ignore")

SPLIT_DATE = date(2023, 1, 1)
WINDOW = 156
MIN_OBS = 50
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
TAIL_TAUS = (0.95, 0.99)
EXTRA_REGRESSORS = ("earnings_next_week_f", "is_long_weekend", "log_fri_vol_20d")
HAWKES_THRESHOLD_Q = 0.90   # tested 0.80 also; both fail the scorecard
HAWKES_MIN_EXCESS = 8
VOL_COL_BY_SYMBOL = {
    "SPY": "vix_fri_close", "QQQ": "vix_fri_close",
    "AAPL": "vix_fri_close", "GOOGL": "vix_fri_close",
    "NVDA": "vix_fri_close", "TSLA": "vix_fri_close",
    "HOOD": "vix_fri_close", "MSTR": "vix_fri_close",
    "GLD": "gvz_fri_close", "TLT": "move_fri_close",
}


# --- Hawkes (exponential kernel) ---


def hawkes_intensity_at(t: float, mu: float, alpha: float, beta: float,
                         past_events: np.ndarray) -> float:
    """λ(t) = μ + Σ_{t_i < t} α exp(-β (t-t_i))."""
    if len(past_events) == 0:
        return mu
    contrib = alpha * np.exp(-beta * (t - past_events))
    return float(mu + contrib.sum())


def hawkes_neg_log_likelihood(params: np.ndarray, event_times: np.ndarray,
                                T_total: float) -> float:
    """Negative log-likelihood of a univariate Hawkes process with
    exponential kernel, given observed event times in [0, T_total].
    """
    mu, alpha, beta = params
    # Stability constraints: μ > 0, α ≥ 0, β > 0, branching ratio α/β < 1
    if mu <= 0 or alpha < 0 or beta <= 0 or (alpha / beta) >= 0.999:
        return 1e10

    n = len(event_times)
    if n == 0:
        return mu * T_total  # no events → just integral term

    log_lik = 0.0
    A = 0.0  # recursive accumulator: A_i = Σ_{j<i} α exp(-β (t_i - t_j))
    log_lik += np.log(mu + A) if (mu + A) > 0 else -1e10
    for i in range(1, n):
        delta = event_times[i] - event_times[i - 1]
        A = A * np.exp(-beta * delta) + alpha * np.exp(-beta * delta)
        intensity = mu + A
        if intensity > 0:
            log_lik += np.log(intensity)
        else:
            return 1e10

    integral = mu * T_total
    integral += (alpha / beta) * np.sum(1.0 - np.exp(-beta * (T_total - event_times)))

    return float(-(log_lik - integral))


def fit_hawkes_mle(event_times: np.ndarray, T_total: float,
                    init: tuple = None) -> tuple:
    """Fit Hawkes(μ, α, β) by MLE. Returns (μ, α, β); NaNs on failure."""
    n = len(event_times)
    if n < 5:
        return (float("nan"), float("nan"), float("nan"))
    if init is None:
        # Reasonable default initialization
        baseline_rate = n / T_total
        init = (baseline_rate * 0.7, baseline_rate * 0.2, 1.0)
    try:
        result = minimize(
            hawkes_neg_log_likelihood, np.array(init),
            args=(event_times, T_total),
            method="Nelder-Mead",
            options={"maxiter": 1500, "xatol": 1e-6, "fatol": 1e-7},
        )
    except Exception:
        return (float("nan"), float("nan"), float("nan"))
    mu, alpha, beta = result.x
    if not all(np.isfinite([mu, alpha, beta])) or mu <= 0 or beta <= 0:
        return (float("nan"), float("nan"), float("nan"))
    return float(mu), float(alpha), float(beta)


def fit_gpd_excess(excess: np.ndarray) -> tuple:
    """Fit GPD on positive excesses. Returns (xi, sigma)."""
    if len(excess) < HAWKES_MIN_EXCESS:
        return (float("nan"), float("nan"))
    try:
        xi, _, sigma = genpareto.fit(excess, floc=0)
    except Exception:
        return (float("nan"), float("nan"))
    if not all(np.isfinite([xi, sigma])) or sigma <= 0:
        return (float("nan"), float("nan"))
    return float(xi), float(sigma)


def gpd_quantile(p_tail: float, xi: float, sigma: float, threshold_zeta: float) -> float:
    """Compute the GPD-extrapolated quantile beyond threshold u.

    p_tail: target tail probability in the FULL distribution
    threshold_zeta: empirical Pr(X > u) on the calibration set
    Returns the magnitude beyond u, or NaN.
    """
    if not all(np.isfinite([xi, sigma])) or sigma <= 0 or threshold_zeta <= 0:
        return float("nan")
    p_cond = max(p_tail / threshold_zeta, 1e-10)
    if p_cond > 1:
        return float("nan")
    if abs(xi) < 1e-6:
        excess_q = -sigma * np.log(p_cond)
    else:
        excess_q = (sigma / xi) * (p_cond ** (-xi) - 1)
    return float(excess_q) if np.isfinite(excess_q) else float("nan")


# --- Symbol-level Hawkes-POT ---


def fit_symbol_hawkes_pot(returns: np.ndarray, weekend_index: np.ndarray) -> dict:
    """Fit two-tailed Hawkes-POT on a per-symbol return series.

    Returns dict with upper-tail and lower-tail Hawkes parameters + GPD parameters
    and the threshold values.
    """
    n = len(returns)
    if n < 50:
        return None
    # Threshold values
    u_upper = float(np.quantile(returns, HAWKES_THRESHOLD_Q))
    u_lower = float(np.quantile(returns, 1 - HAWKES_THRESHOLD_Q))

    # Upper-tail exceedances
    upper_mask = returns > u_upper
    upper_excess = returns[upper_mask] - u_upper
    upper_event_times = weekend_index[upper_mask].astype(float)
    upper_zeta = float(upper_mask.mean())

    # Lower-tail exceedances (symmetric setup)
    lower_mask = returns < u_lower
    lower_excess = u_lower - returns[lower_mask]
    lower_event_times = weekend_index[lower_mask].astype(float)
    lower_zeta = float(lower_mask.mean())

    T_total = float(weekend_index[-1] - weekend_index[0]) if n > 1 else 1.0

    # Fit
    mu_u, alpha_u, beta_u = fit_hawkes_mle(upper_event_times, T_total)
    mu_l, alpha_l, beta_l = fit_hawkes_mle(lower_event_times, T_total)
    xi_u, sigma_u = fit_gpd_excess(upper_excess)
    xi_l, sigma_l = fit_gpd_excess(lower_excess)

    return {
        "u_upper": u_upper, "u_lower": u_lower,
        "upper_zeta": upper_zeta, "lower_zeta": lower_zeta,
        "upper_event_times": upper_event_times,
        "lower_event_times": lower_event_times,
        "mu_u": mu_u, "alpha_u": alpha_u, "beta_u": beta_u,
        "mu_l": mu_l, "alpha_l": alpha_l, "beta_l": beta_l,
        "xi_u": xi_u, "sigma_u": sigma_u,
        "xi_l": xi_l, "sigma_l": sigma_l,
        "n_upper": int(upper_mask.sum()), "n_lower": int(lower_mask.sum()),
    }


def hawkes_pot_quantile(t: float, p_tail: float, params: dict, side: str) -> float:
    """Compute the conditional VaR magnitude at time t for tail probability p_tail.

    The Hawkes self-excitation inflates the conditional rate of exceedance
    at time t relative to the long-run baseline. We adjust the GPD's effective
    tail probability by the ratio λ(t) / μ_uncond, where μ_uncond is the
    baseline intensity (the un-self-excited rate). When λ(t) >> μ, the effective
    p_eff = p_tail · (μ_uncond / λ(t)) is smaller → the GPD-quantile is larger
    → bound widens.
    """
    if params is None:
        return float("nan")
    if side == "upper":
        mu, alpha, beta = params["mu_u"], params["alpha_u"], params["beta_u"]
        past = params["upper_event_times"]
        zeta = params["upper_zeta"]
        xi, sigma = params["xi_u"], params["sigma_u"]
        u = params["u_upper"]
        sign = +1
    else:
        mu, alpha, beta = params["mu_l"], params["alpha_l"], params["beta_l"]
        past = params["lower_event_times"]
        zeta = params["lower_zeta"]
        xi, sigma = params["xi_l"], params["sigma_l"]
        u = params["u_lower"]
        sign = -1

    if not all(np.isfinite([mu, alpha, beta, xi, sigma])):
        return float("nan")

    # Compute Hawkes intensity at time t given prior exceedances
    past_before_t = past[past < t]
    lam_t = hawkes_intensity_at(t, mu, alpha, beta, past_before_t)
    # Long-run baseline intensity (un-conditional): for stationary Hawkes
    # μ_uncond = μ / (1 - α/β)
    mu_uncond = mu / max(1 - alpha / beta, 1e-3)
    # Inflation factor
    inflation = lam_t / max(mu_uncond, 1e-6)
    # Effective tail prob
    p_eff = max(p_tail / inflation, 1e-10) if inflation > 0 else p_tail
    # GPD-extrapolated quantile beyond u
    excess_q = gpd_quantile(p_eff, xi, sigma, zeta)
    if not np.isfinite(excess_q):
        return float("nan")
    return float(u + sign * excess_q)


# --- Trial 3 + Trial 6 baseline ---


def replay_with_pooled_tail_baseline(panel: pd.DataFrame) -> pd.DataFrame:
    """Same baseline replay as in exp_caviar_cv_select.py — Trial 3 + Trial 6.
    Returns the bound table for the full panel.
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


def collect_per_symbol_returns(panel: pd.DataFrame) -> dict:
    """For each symbol, extract weekly log-returns (Mon_open / Fri_close)
    and weekend index (sequence). These are the inputs to the Hawkes-POT
    fit — not the F1 residuals (Hawkes models the raw return tails).
    """
    out = {}
    for sym, idx in panel.groupby("symbol").groups.items():
        g = panel.loc[idx].sort_values("fri_ts")
        rets = np.log(g["mon_open"].astype(float).values / g["fri_close"].astype(float).values)
        ts = g["fri_ts"].values
        n = len(rets)
        out[sym] = {
            "rets": rets, "fri_ts": ts,
            "weekend_index": np.arange(n, dtype=float),
        }
    return out


def run_diag_battery(served: pd.DataFrame, bound_cols: tuple, label: str) -> dict:
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

    # --- Fit Hawkes-POT per symbol on pre-2023 calibration ---
    print("\n--- Fitting Hawkes-POT (2T) per symbol on pre-2023 ---", flush=True)
    sym_data = collect_per_symbol_returns(panel)
    hawkes_params = {}
    for sym, d in sym_data.items():
        cal_mask = d["fri_ts"] < SPLIT_DATE
        cal_rets = d["rets"][cal_mask]
        cal_idx = d["weekend_index"][cal_mask]
        # Drop NaN rets
        valid = np.isfinite(cal_rets)
        if valid.sum() < 50:
            print(f"  {sym}: insufficient cal data ({valid.sum()})")
            hawkes_params[sym] = None; continue
        params = fit_symbol_hawkes_pot(cal_rets[valid], cal_idx[valid])
        hawkes_params[sym] = params
        if params:
            print(f"  {sym}: n_upper={params['n_upper']}, n_lower={params['n_lower']}, "
                  f"u=({params['u_lower']:.4f}, {params['u_upper']:.4f}), "
                  f"upper Hawkes (μ,α,β)=({params['mu_u']:.4f}, {params['alpha_u']:.4f}, {params['beta_u']:.4f}), "
                  f"upper GPD (ξ,σ)=({params['xi_u']:.3f}, {params['sigma_u']:.4f})")

    # --- Compute Hawkes-POT bounds for each OOS row ---
    print("\n--- Computing Hawkes-POT bounds for each row ---", flush=True)
    bounds_with_hawkes = bounds.copy()
    bounds_with_hawkes["lo_hawkes"] = bounds_with_hawkes["lo_baseline"]
    bounds_with_hawkes["hi_hawkes"] = bounds_with_hawkes["hi_baseline"]

    for sym, d in sym_data.items():
        if hawkes_params[sym] is None:
            continue
        # Map each fri_ts → weekend_index (lookup table)
        ts_to_idx = dict(zip(d["fri_ts"], d["weekend_index"]))
        sym_mask = (bounds_with_hawkes["symbol"] == sym) & (bounds_with_hawkes["target"] == 0.99)
        for ridx in bounds_with_hawkes[sym_mask].index:
            row = bounds_with_hawkes.loc[ridx]
            ts = row["fri_ts"]
            t_idx = ts_to_idx.get(ts, None)
            if t_idx is None:
                continue
            # Compute Hawkes-POT bounds at this t
            p_tail = (1 - 0.99) / 2  # 0.005 per side
            q_lo_excess = hawkes_pot_quantile(t_idx, p_tail, hawkes_params[sym], side="lower")
            q_hi_excess = hawkes_pot_quantile(t_idx, p_tail, hawkes_params[sym], side="upper")
            if np.isfinite(q_lo_excess) and np.isfinite(q_hi_excess):
                bounds_with_hawkes.at[ridx, "lo_hawkes"] = row["fri_close"] * np.exp(q_lo_excess)
                bounds_with_hawkes.at[ridx, "hi_hawkes"] = row["fri_close"] * np.exp(q_hi_excess)

    bounds_oos = bounds_with_hawkes[bounds_with_hawkes["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    print("\n=== Baseline (Trial 3 + Trial 6) ===", flush=True)
    res_base = run_diag_battery(bounds_oos, ("lo_baseline", "hi_baseline"), label="baseline")
    print(res_base["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Family B (Hawkes-POT) ===", flush=True)
    res_haw = run_diag_battery(bounds_oos, ("lo_hawkes", "hi_hawkes"), label="hawkes_pot")
    print(res_haw["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Per-symbol DQ at τ=0.99 — Baseline vs Hawkes-POT ===", flush=True)
    bp = res_base["per_symbol"][res_base["per_symbol"]["target"] == 0.99].set_index("symbol")[["p_value"]].rename(columns={"p_value": "p_base"})
    hp = res_haw["per_symbol"][res_haw["per_symbol"]["target"] == 0.99].set_index("symbol")[["p_value"]].rename(columns={"p_value": "p_haw"})
    cmp = bp.join(hp).sort_index()
    cmp["base_R"] = cmp["p_base"] < 0.05
    cmp["haw_R"] = cmp["p_haw"] < 0.05
    print(cmp.to_string(float_format=lambda x: f"{x:.4f}"))

    out_dir = REPORTS / "tables"
    summary = pd.concat([res_base["summary"], res_haw["summary"]], ignore_index=True)
    per_sym = pd.concat([res_base["per_symbol"], res_haw["per_symbol"]], ignore_index=True)
    summary.to_csv(out_dir / "v1b_oos_hawkes_summary.csv", index=False)
    per_sym.to_csv(out_dir / "v1b_oos_dq_per_symbol_hawkes.csv", index=False)

    print("\n" + "=" * 80)
    print("DECISION SCORECARD — Family B (Hawkes-POT) at τ = 0.99")
    print("=" * 80)
    base_99 = res_base["summary"][res_base["summary"]["target"] == 0.99].iloc[0]
    haw_99 = res_haw["summary"][res_haw["summary"]["target"] == 0.99].iloc[0]
    cap = 1.5 * base_99["mean_hw_bps"]
    print(f"  Per-symbol DQ rejects ≤ 3/10:   base {int(base_99['n_symbols_reject_05'])}/10  "
          f"|  hawkes {int(haw_99['n_symbols_reject_05'])}/10")
    print(f"  Realised (target 0.99):          base {base_99['realised']:.3f}  "
          f"|  hawkes {haw_99['realised']:.3f}")
    print(f"  Christoffersen p_ind > 0.05:     base {base_99['christoffersen_p']:.3f}  "
          f"|  hawkes {haw_99['christoffersen_p']:.3f}")
    print(f"  Bandwidth (cap {cap:.0f} bps):        base {base_99['mean_hw_bps']:.0f}  "
          f"|  hawkes {haw_99['mean_hw_bps']:.0f}")
    print()
    print(f"  HAWKES scorecard:")
    print(f"    Threshold 1 (DQ ≤ 3/10):    PASS: {haw_99['n_symbols_reject_05'] <= 3}")
    print(f"    Threshold 2 (realised ±2pp): PASS: {abs(haw_99['realised'] - 0.99) <= 0.02}")
    print(f"    Threshold 3 (Chr p > 0.05):  PASS: {haw_99['christoffersen_p'] > 0.05}")
    print(f"    Threshold 4 (BW ≤ 1.5×):    PASS: {haw_99['mean_hw_bps'] <= cap}")
    print()
    print(f"  HOOD-specific (the structural residual):")
    if "HOOD" in cmp.index:
        print(f"    base p={cmp.loc['HOOD', 'p_base']:.4f} ({'reject' if cmp.loc['HOOD', 'base_R'] else 'pass'})")
        print(f"    hawkes p={cmp.loc['HOOD', 'p_haw']:.4f} ({'reject' if cmp.loc['HOOD', 'haw_R'] else 'pass'})")


if __name__ == "__main__":
    main()
