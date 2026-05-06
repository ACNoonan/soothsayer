"""
M6 Locally-Weighted Conformal — δ-shift walk-forward sweep.

Mirrors `scripts/v1_archive/run_mondrian_delta_sweep.py` for the LWC build
(M6) instead of the per-regime score (M5). 4-split expanding-window
walk-forward protocol; same δ grid; same per-τ summary shape. The output
informs the LWC_DELTA_SHIFT_SCHEDULE constant in
`scripts/build_lwc_artefact.py`.

Procedure
---------
For each split fraction f ∈ {0.40, 0.50, 0.60, 0.70} of the OOS
weekend index:
  train: pre-2023 panel (fixed) → per-regime per-τ quantile q_r^LWC(τ) on
         standardised score |y - p̂| / (fri_close · σ̂_sym(t))
  tune:  first f% of OOS weekends → fit c(τ) such that pooled tune coverage
         with q_r^LWC(τ)·c(τ)·σ̂·fri_close bands ≥ τ + δ(τ)
  test:  remaining (1-f)% of OOS weekends → realised coverage

Sweeps δ ∈ {0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07} per τ. Reports
cross-split test-realised mean / std / Kupiec-margin per (τ, δ) so the
deployer can pick the smallest δ that aligns walk-forward realised
coverage with nominal at each anchor (the M5 selection criterion).

Output
------
  reports/tables/v1b_lwc_delta_sweep.csv     per-split rows for every (τ, δ)

The σ̂_sym(t) construction is *not refit per split* — σ̂ at row t depends
only on rows with fri_ts' < fri_ts[t], so it is naturally walk-forward by
construction.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    add_sigma_hat_sym_ewma,
    SIGMA_HAT_MIN,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
TARGETS = DEFAULT_TAUS
DELTA_GRID = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07)
WALKFORWARD_FRACTIONS = (0.40, 0.50, 0.60, 0.70)
# The 0.20 (n_tune = 35) and 0.30 (n_tune = 52) splits are excluded as
# under-powered: at those tune sizes the 4-scalar c(τ) fit collapses to
# identity at one or more anchors (the 0.20 split at τ ≥ 0.95; the 0.30
# split at τ = 0.99 where 52 tune weekends cannot reliably estimate the
# 99th percentile). The 0.40 split (n_tune = 69) is the smallest fraction
# whose c(τ) fit is non-identity at every served anchor under EWMA HL=8.
OUTPUT_CSV = REPORTS / "tables" / "v1b_lwc_delta_sweep.csv"


def _kupiec(n: int, x: int, claimed: float) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p_obs = x / n
    p_exp = 1.0 - claimed
    if p_obs in (0.0, 1.0):
        lr = 2.0 * n * (
            p_obs * np.log(max(p_obs, 1e-12) / max(p_exp, 1e-12))
            + (1 - p_obs) * np.log(max(1 - p_obs, 1e-12) / max(1 - p_exp, 1e-12))
        )
    else:
        lr = 2.0 * (
            x * np.log(p_obs / p_exp)
            + (n - x) * np.log((1 - p_obs) / (1 - p_exp))
        )
    return float(lr), float(1.0 - chi2.cdf(lr, df=1))


def _train_quantile_per_regime(
    panel_train: pd.DataFrame,
    score_col: str,
    targets: tuple[float, ...],
) -> pd.DataFrame:
    """Long-form per-regime CP quantile of score_col at every τ."""
    rows = []
    for regime, g in panel_train.groupby("regime_pub"):
        scores = g[score_col].dropna().to_numpy(float)
        n = scores.size
        if n == 0:
            continue
        sorted_scores = np.sort(scores)
        for tau in targets:
            k = int(np.ceil(tau * (n + 1)))
            k = min(max(k, 1), n)
            rows.append(
                {
                    "regime_pub": regime,
                    "target": tau,
                    "b": float(sorted_scores[k - 1]),
                    "n_train": n,
                }
            )
    return pd.DataFrame(rows)


def _fit_c(
    panel_tune: pd.DataFrame,
    base_quantiles: pd.DataFrame,
    score_col: str,
    target: float,
    coverage_target: float,
) -> float:
    """Smallest c on the standard 1.0..5.0 grid with mean(score ≤ b·c) ≥
    coverage_target on the tune slice. Mirrors `_fit_c_bump` in
    `build_mondrian_artefact.py`."""
    sub = base_quantiles[base_quantiles["target"] == target][["regime_pub", "b"]]
    merged = panel_tune.merge(sub, on="regime_pub", how="left").dropna(
        subset=[score_col, "b"]
    )
    scores = merged[score_col].to_numpy(float)
    b_arr = merged["b"].to_numpy(float)
    grid = np.arange(1.0, 5.0001, 0.001)
    for c in grid:
        if float(np.mean(scores <= b_arr * c)) >= coverage_target:
            return float(c)
    return float(grid[-1])


def walk_forward_lwc(
    panel_train: pd.DataFrame,
    panel_oos: pd.DataFrame,
    delta: float,
    score_col: str = "score_lwc",
    scale_col: str = "sigma_hat_sym_pre_fri",
) -> pd.DataFrame:
    """6-split expanding-window walk-forward of LWC, fitting c(τ) such that
    tune coverage ≥ τ+δ. Returns one row per (split_fraction, target).

    Mirrors `walk_forward_m5` in
    `scripts/v1_archive/run_mondrian_walkforward_pit.py` but with the
    standardised conformity score and σ̂-rescaled half-width."""
    base = _train_quantile_per_regime(panel_train, score_col, TARGETS)
    weekends = sorted(panel_oos["fri_ts"].unique())
    rows = []
    for f in WALKFORWARD_FRACTIONS:
        n_tune = max(int(round(len(weekends) * f)), 8)
        tune_ws = set(weekends[:n_tune])
        test_ws = set(weekends[n_tune:])
        panel_tune = panel_oos[panel_oos["fri_ts"].isin(tune_ws)].copy()
        panel_test = panel_oos[panel_oos["fri_ts"].isin(test_ws)].copy()
        for tau in TARGETS:
            cov_target = min(tau + delta, 0.999)
            c = _fit_c(panel_tune, base, score_col, target=tau,
                       coverage_target=cov_target)
            sub = base[base["target"] == tau][["regime_pub", "b"]]
            test = panel_test.merge(sub, on="regime_pub", how="left").dropna(
                subset=[score_col, "b"]
            )
            test["b_eff"] = test["b"] * c
            inside = (test[score_col] <= test["b_eff"]).astype(int)
            # Half-width in bps for reporting: q · σ̂ · 1e4 (relative to fri_close).
            hw_bps = test["b_eff"] * test[scale_col] * 1e4
            rows.append(
                {
                    "split_fraction": f,
                    "n_tune_weekends": n_tune,
                    "n_test_weekends": len(test_ws),
                    "target": tau,
                    "delta": delta,
                    "bump_c": c,
                    "n_test": int(inside.size),
                    "test_realised": float(inside.mean()) if len(inside) else float("nan"),
                    "test_half_width_bps_mean": float(hw_bps.mean()) if len(test) else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    # Deployed M6 σ̂ rule (matches `lwc_artefact_v1.json` → EWMA HL=8). Alias
    # the EWMA column to `sigma_hat_sym_pre_fri` for downstream compatibility.
    panel = add_sigma_hat_sym_ewma(panel, half_life=8, min_obs=SIGMA_HAT_MIN)
    panel["sigma_hat_sym_pre_fri"] = panel["sigma_hat_sym_ewma_pre_fri_hl8"]
    panel["score_lwc"] = compute_score_lwc(panel)
    mask = panel["score_lwc"].notna() & panel["sigma_hat_sym_pre_fri"].notna()
    work = panel[mask].copy()
    print(
        f"Panel after σ̂_sym filter: {len(work):,} rows × "
        f"{work['fri_ts'].nunique()} weekends "
        f"(dropped {len(panel) - len(work):,} warm-up rows)",
        flush=True,
    )

    panel_train = work[work["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = work[work["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(
        f"  train: {len(panel_train):,}  oos: {len(panel_oos):,}",
        flush=True,
    )
    print()

    all_rows = []
    print(
        f"{'tau':>5} {'delta':>5} {'c_mean':>7} {'c_std':>6} "
        f"{'cov_mean':>9} {'cov_std':>8} {'def_mean_pp':>11} "
        f"{'def_max_pp':>11} {'kup_p_mean':>10} {'hw_mean':>8}"
    )
    print("-" * 100)
    for delta in DELTA_GRID:
        wf = walk_forward_lwc(panel_train, panel_oos, delta=float(delta))
        all_rows.append(wf)
        for tau, g in wf.groupby("target"):
            c_mean = float(g["bump_c"].mean())
            c_std = float(g["bump_c"].std(ddof=1))
            cov_mean = float(g["test_realised"].mean())
            cov_std = float(g["test_realised"].std(ddof=1))
            deficit_mean = (cov_mean - tau) * 100
            deficit_max = (g["test_realised"].min() - tau) * 100
            kup_ps = []
            for _, row in g.iterrows():
                n = int(row["n_test"])
                x_in = int(round(row["test_realised"] * n))
                _, p = _kupiec(n, n - x_in, tau)
                kup_ps.append(p)
            kup_p_mean = float(np.nanmean(kup_ps))
            hw_mean = float(g["test_half_width_bps_mean"].mean())
            print(
                f"{tau:>5.2f} {delta:>5.3f} {c_mean:>7.3f} {c_std:>6.3f} "
                f"{cov_mean:>9.4f} {cov_std:>8.4f} {deficit_mean:>+11.2f} "
                f"{deficit_max:>+11.2f} {kup_p_mean:>10.3f} {hw_mean:>8.1f}"
            )
        print()

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(all_rows, ignore_index=True).to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
