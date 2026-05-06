"""Paper 1 — Tier A item A3.

Replace the Binom(10, τ̄_violation) "independence strawman" comparator for the
joint-tail k_w distribution with a properly specified joint-volatility / joint-
tail baseline.

Two parametric joint baselines on the deployed M6 LWC standardised residuals:

  z_i,t = (mon_open_i,t − point_i,t) / (fri_close_i,t · σ̂_sym_i,t)
        ≈ standardised conformity residual under the deployed σ̂ EWMA HL=8

  Marginals: per-symbol Student-t (df ν̂_i fit by MLE on z_i,t over EVAL slice)
  Copula:    (1) Gaussian copula with empirical Pearson R̂(z)
             (2) Student-t  copula with same R̂ and df ν̂_copula via kurtosis MoM

Simulation: 50,000 synthetic weekends per baseline. For each weekend:
  - Sample regime r ∼ Empirical(regime_pub on EVAL)
  - Get standardised threshold T_r(τ) = q_r(τ) · c(τ) from the deployed M6 fit
  - Sample u ∼ Copula(R̂, [ν̂_copula])
  - z_sim_i = F_i^{-1}(u_i; ν̂_i)
  - V_i = 1{|z_sim_i| > T_r(τ)}
  - k_w = Σ_i V_i

Compare the simulated k_w distributions and the empirical k_w distribution
to the strawman Binom(10, τ̄_violation) at each served τ. Headline metrics:
KS distance, Wasserstein-1, P(k_w ≥ 3), P(k_w ≥ 5), P(k_w = 10).

Output:
  reports/tables/paper1_a3_joint_baseline_kw_distribution.csv
  reports/tables/paper1_a3_joint_baseline_kw_summary.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import t as student_t, norm, kstest, wasserstein_distance, binom

from soothsayer.backtest.calibration import (
    add_sigma_hat_sym_ewma,
    SIGMA_HAT_HL_WEEKENDS,
    train_quantile_table,
    fit_c_bump_schedule,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
N_SIM = 50_000
RNG = np.random.default_rng(20260506)


def fit_t_df_mle(x: np.ndarray) -> float:
    """MLE Student-t df on a centered, ~unit-scale standardised series.

    Uses scipy's t.fit with floc=0, fscale=1 fixed (since z is already
    standardised). Falls back to method-of-moments kurtosis if MLE returns
    a degenerate value.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 30:
        return float("nan")
    try:
        nu, _, _ = student_t.fit(x, floc=0.0, fscale=1.0)
        if 2.5 <= nu <= 60:
            return float(nu)
    except Exception:
        pass
    # Method of moments via excess kurtosis: ν = 4 + 6 / k_excess (k > 0)
    k = float(((x ** 4).mean()) - 3.0)
    if k <= 0:
        return 30.0
    nu_mom = 4.0 + 6.0 / k
    return float(np.clip(nu_mom, 2.5, 60.0))


def kurtosis_to_copula_df(z_panel: np.ndarray) -> float:
    """Average per-marginal kurtosis-implied df, used as the t-copula df.

    Pragmatic estimator: fit per-symbol t-df, take their median. The t-copula
    df controls joint-tail dependence; using the median per-symbol df keeps
    the joint heaviness consistent with the marginal heaviness.
    """
    nus = [fit_t_df_mle(z_panel[:, j]) for j in range(z_panel.shape[1])]
    nus = [n for n in nus if np.isfinite(n)]
    if not nus:
        return 30.0
    return float(np.median(nus))


def gaussian_copula_sample(R: np.ndarray, n: int, rng) -> np.ndarray:
    """Sample n × d uniforms from a Gaussian copula with correlation R."""
    L = np.linalg.cholesky(R + 1e-9 * np.eye(R.shape[0]))
    z = rng.standard_normal(size=(n, R.shape[0]))
    g = z @ L.T
    return norm.cdf(g)


def t_copula_sample(R: np.ndarray, nu: float, n: int, rng) -> np.ndarray:
    """Sample n × d uniforms from a Student-t copula with corr R and df nu.

    Construction:
      g ∼ N(0, R)   → joint normal with correlation R
      w ∼ χ²(nu)/nu independently
      x = g / sqrt(w)   has marginal Student-t(nu) and t-copula dependence
      u = T_nu(x)        with the same marginal CDF
    """
    L = np.linalg.cholesky(R + 1e-9 * np.eye(R.shape[0]))
    z = rng.standard_normal(size=(n, R.shape[0]))
    g = z @ L.T
    w = rng.chisquare(df=nu, size=n) / nu
    x = g / np.sqrt(w)[:, None]
    return student_t.cdf(x, df=nu)


def compute_kw_distribution(simulated_z: np.ndarray,
                            regime_idx: np.ndarray,
                            thresholds_by_regime: dict[str, float],
                            regime_labels: list[str]) -> np.ndarray:
    """Given simulated z (n × 10), regime per row, regime → standardised
    threshold T_r(τ), return k_w per simulated weekend."""
    thr_arr = np.array([thresholds_by_regime[regime_labels[i]] for i in regime_idx],
                       dtype=float)
    V = (np.abs(simulated_z) > thr_arr[:, None]).astype(int)
    return V.sum(axis=1)


def kw_distribution_summary(kw: np.ndarray) -> dict:
    """Convert a 1D array of k_w into a {k → P(K=k)} dict."""
    out = {k: float((kw == k).mean()) for k in range(11)}
    return out


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
    panel["score_lwc"] = compute_score_lwc(panel, scale_col="sigma_hat_sym_pre_fri")

    # Standardised signed residual z = (mon_open - point) / (fri_close · σ̂)
    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    panel["z_signed"] = (
        (panel["mon_open"].astype(float) - point)
        / (panel["fri_close"].astype(float) * panel["sigma_hat_sym_pre_fri"].astype(float))
    )

    panel = panel[panel["score_lwc"].notna() & panel["z_signed"].notna()].reset_index(
        drop=True
    )

    train = panel[panel["fri_ts"] <  SPLIT_DATE].reset_index(drop=True)
    oos   = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    qt = train_quantile_table(train, cell_col="regime_pub",
                              taus=HEADLINE_TAUS, score_col="score_lwc")
    cb = fit_c_bump_schedule(oos, qt, cell_col="regime_pub",
                              taus=HEADLINE_TAUS, score_col="score_lwc")
    print(f"deployed M6 c-bumps: {cb}", flush=True)
    print(f"deployed q_r(τ) per regime:")
    for r, row in qt.items():
        print(f"  {r}: " + ", ".join(f"τ={t:.2f}→{v:.3f}" for t, v in sorted(row.items())))

    # Standardised threshold T_r(τ) = q_r(τ) · c(τ)
    regimes = sorted(qt.keys())
    threshold_by_tau_regime = {
        tau: {r: float(qt[r][tau] * cb[tau]) for r in regimes}
        for tau in HEADLINE_TAUS
    }

    # Pivot z to (weekend × symbol) on OOS
    oos = oos.sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    Zw = oos.pivot_table(index="fri_ts", columns="symbol", values="z_signed",
                          aggfunc="first")
    regime_w = oos.groupby("fri_ts")["regime_pub"].first().reindex(Zw.index)

    n_full = Zw.dropna(axis=0, how="any").shape[0]
    print(f"\nOOS panel: {Zw.shape[0]} weekends × {Zw.shape[1]} symbols",
          flush=True)
    print(f"  with no missing symbol: {n_full} weekends", flush=True)

    Z_full_w = Zw.dropna(axis=0, how="any")
    regime_full_w = regime_w.loc[Z_full_w.index]
    Z_arr = Z_full_w.to_numpy()  # (W, 10)
    sym_order = list(Z_full_w.columns)
    print(f"  symbols (in z column order): {sym_order}", flush=True)

    # === Per-symbol marginals (Student-t df) ===
    nus_marginal = np.array([fit_t_df_mle(Z_arr[:, j]) for j in range(Z_arr.shape[1])])
    print(f"\nper-symbol marginal t-df (MLE):")
    for s, nu in zip(sym_order, nus_marginal):
        print(f"  {s}: ν̂ = {nu:.2f}")

    # === Copula correlation R̂ on z ===
    R = np.corrcoef(Z_arr.T)
    print(f"\nempirical correlation matrix R̂ on z (shape {R.shape}); "
          f"mean off-diag corr = {(R - np.eye(len(R))).sum() / (R.size - len(R)):.3f}",
          flush=True)
    nu_copula = float(np.median(nus_marginal))
    print(f"t-copula df (median of marginals): {nu_copula:.2f}", flush=True)

    # === Simulation ===
    # Empirical regime distribution on OOS
    regime_emp_freq = regime_full_w.value_counts(normalize=True)
    regime_labels = list(regime_emp_freq.index)
    regime_probs  = regime_emp_freq.values
    print(f"\nempirical OOS regime mix (full-coverage weekends):")
    print(regime_emp_freq.to_string())

    # Sample regimes for N_SIM weekends
    regime_idx_sim = RNG.choice(len(regime_labels), size=N_SIM, p=regime_probs)

    # Gaussian copula simulation
    U_g = gaussian_copula_sample(R, N_SIM, RNG)
    Z_g = np.column_stack([
        student_t.ppf(U_g[:, j], df=nus_marginal[j])
        for j in range(Z_arr.shape[1])
    ])
    # t-copula simulation
    U_t = t_copula_sample(R, nu_copula, N_SIM, RNG)
    Z_t = np.column_stack([
        student_t.ppf(U_t[:, j], df=nus_marginal[j])
        for j in range(Z_arr.shape[1])
    ])

    # Empirical k_w on full-coverage weekends
    rows_pool = []
    rows_summary = []
    for tau in HEADLINE_TAUS:
        thr_by_r = threshold_by_tau_regime[tau]
        # Empirical
        thr_full = np.array([thr_by_r[r] for r in regime_full_w], dtype=float)
        V_emp = (np.abs(Z_arr) > thr_full[:, None]).astype(int)
        kw_emp = V_emp.sum(axis=1)
        emp_dist = kw_distribution_summary(kw_emp)

        # Per-symbol violation rates τ̄ for the Binom strawman
        # (use the same regime-conditional thresholds; per symbol over weekends)
        per_sym_viol = (np.abs(Z_arr) > thr_full[:, None]).mean(axis=0)
        tau_bar = float(per_sym_viol.mean())

        # Binom(10, tau_bar) strawman
        kw_binom = RNG.binomial(n=10, p=tau_bar, size=N_SIM)
        binom_dist = kw_distribution_summary(kw_binom)

        # Gaussian copula
        kw_g = compute_kw_distribution(Z_g, regime_idx_sim, thr_by_r, regime_labels)
        g_dist = kw_distribution_summary(kw_g)

        # t-copula
        kw_t = compute_kw_distribution(Z_t, regime_idx_sim, thr_by_r, regime_labels)
        t_dist = kw_distribution_summary(kw_t)

        # Distance metrics: Wasserstein-1 on integer support 0..10, KS via PMF→CDF
        def ws1(a, b):
            return float(wasserstein_distance(a, b))
        def ks_int(a, b):
            xs = np.arange(0, 11)
            ca = np.array([(a <= x).mean() for x in xs])
            cb = np.array([(b <= x).mean() for x in xs])
            return float(np.max(np.abs(ca - cb)))

        rows_summary.append({
            "target": tau,
            "tau_bar_violation_rate": tau_bar,
            "n_eval_weekends": int(len(kw_emp)),
            # P-tail metrics
            "P_kw_ge_3_emp": float((kw_emp >= 3).mean()),
            "P_kw_ge_3_binom": float((kw_binom >= 3).mean()),
            "P_kw_ge_3_gauss": float((kw_g >= 3).mean()),
            "P_kw_ge_3_t":     float((kw_t >= 3).mean()),
            "P_kw_ge_5_emp":   float((kw_emp >= 5).mean()),
            "P_kw_ge_5_binom": float((kw_binom >= 5).mean()),
            "P_kw_ge_5_gauss": float((kw_g >= 5).mean()),
            "P_kw_ge_5_t":     float((kw_t >= 5).mean()),
            "P_kw_eq_10_emp":  float((kw_emp == 10).mean()),
            "P_kw_eq_10_binom": float((kw_binom == 10).mean()),
            "P_kw_eq_10_gauss": float((kw_g == 10).mean()),
            "P_kw_eq_10_t":    float((kw_t == 10).mean()),
            # Distance to empirical
            "ws1_binom_vs_emp": ws1(kw_binom, kw_emp),
            "ws1_gauss_vs_emp": ws1(kw_g, kw_emp),
            "ws1_t_vs_emp":     ws1(kw_t, kw_emp),
            "ks_binom_vs_emp":  ks_int(kw_binom, kw_emp),
            "ks_gauss_vs_emp":  ks_int(kw_g, kw_emp),
            "ks_t_vs_emp":      ks_int(kw_t, kw_emp),
            # Mean / variance
            "mean_emp":   float(kw_emp.mean()),
            "var_emp":    float(kw_emp.var()),
            "mean_binom": float(kw_binom.mean()),
            "var_binom":  float(kw_binom.var()),
            "mean_gauss": float(kw_g.mean()),
            "var_gauss":  float(kw_g.var()),
            "mean_t":     float(kw_t.mean()),
            "var_t":      float(kw_t.var()),
            "var_overdispersion_emp_over_binom": (
                float(kw_emp.var()) / float(kw_binom.var()) if kw_binom.var() > 0 else float("nan")
            ),
            "var_overdispersion_emp_over_gauss": (
                float(kw_emp.var()) / float(kw_g.var()) if kw_g.var() > 0 else float("nan")
            ),
            "var_overdispersion_emp_over_t": (
                float(kw_emp.var()) / float(kw_t.var()) if kw_t.var() > 0 else float("nan")
            ),
        })

        for k in range(11):
            rows_pool.append({
                "target": tau, "k": k,
                "P_emp": emp_dist[k],
                "P_binom": binom_dist[k],
                "P_gauss_copula": g_dist[k],
                "P_t_copula": t_dist[k],
            })

    summary_df = pd.DataFrame(rows_summary)
    pmf_df = pd.DataFrame(rows_pool)

    out_pmf = REPORTS / "tables" / "paper1_a3_joint_baseline_kw_distribution.csv"
    out_sum = REPORTS / "tables" / "paper1_a3_joint_baseline_kw_summary.csv"
    pmf_df.to_csv(out_pmf, index=False)
    summary_df.to_csv(out_sum, index=False)
    print(f"\nwrote {out_pmf}\nwrote {out_sum}", flush=True)

    print("\n=== headline τ comparison: empirical vs Binom vs Gaussian-copula vs t-copula ===")
    cols = ["target", "tau_bar_violation_rate",
            "P_kw_ge_3_emp", "P_kw_ge_3_binom", "P_kw_ge_3_gauss", "P_kw_ge_3_t",
            "P_kw_ge_5_emp", "P_kw_ge_5_binom", "P_kw_ge_5_gauss", "P_kw_ge_5_t",
            "P_kw_eq_10_emp", "P_kw_eq_10_t",
            "ws1_binom_vs_emp", "ws1_gauss_vs_emp", "ws1_t_vs_emp",
            "var_overdispersion_emp_over_binom", "var_overdispersion_emp_over_t"]
    print(summary_df[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
