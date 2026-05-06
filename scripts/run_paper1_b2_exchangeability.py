"""Paper 1 — Tier B item B2.

Exchangeability test on M6 LWC standardised conformity scores within each
Mondrian bin (regime × symbol).

Mondrian-CP's finite-sample coverage guarantee is exchangeability-based:
within each Mondrian bin (here, regime × symbol on the v1 panel), the
calibration scores must be exchangeable for the per-bin conformal
quantile to deliver finite-sample coverage. The §4.6 methodology asserts
this; we never tested it.

Test design — within each (regime × symbol) bin on the OOS slice:
  Statistic: lag-1 Pearson autocorrelation of the score in fri_ts order
  Null:      score is exchangeable within bin
  Permutation distribution: shuffle the time order N_PERM = 5,000 times,
                             recompute the statistic on each shuffle.
  Two-sided p-value: 2 · min(P(stat_obs ≤ stat_perm), P(stat_obs ≥ stat_perm))

Aggregate diagnostic: under exchangeability, the 30 per-bin p-values
should be Uniform(0, 1). We report:
  - The 30 per-bin p-values (visible to the wording agent).
  - The empirical rejection rate at α=0.05 (expected ~5 % under H0).
  - KS test of the 30 p-values vs Uniform(0, 1).
  - The single largest LR on bin-level autocorrelation (extreme-bin disclosure).

Output:
  reports/tables/paper1_b2_exchangeability.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import kstest

from soothsayer.backtest.calibration import (
    add_sigma_hat_sym_ewma,
    SIGMA_HAT_HL_WEEKENDS,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
N_PERM = 5_000
RNG = np.random.default_rng(20260506)


def lag1_corr(x: np.ndarray) -> float:
    if len(x) < 5:
        return float("nan")
    a = x[:-1]
    b = x[1:]
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def perm_test_lag1(values: np.ndarray, n_perm: int) -> tuple[float, float]:
    obs = lag1_corr(values)
    if not np.isfinite(obs):
        return obs, float("nan")
    n = len(values)
    perm_stats = np.empty(n_perm)
    for i in range(n_perm):
        idx = RNG.permutation(n)
        perm_stats[i] = lag1_corr(values[idx])
    perm_stats = perm_stats[np.isfinite(perm_stats)]
    if len(perm_stats) < 100:
        return obs, float("nan")
    p_le = float((perm_stats <= obs).mean())
    p_ge = float((perm_stats >= obs).mean())
    p_two = min(2.0 * min(p_le, p_ge), 1.0)
    return obs, p_two


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
    panel = panel[panel["score_lwc"].notna()].reset_index(drop=True)
    oos = panel[panel["fri_ts"] >= SPLIT_DATE].sort_values(["fri_ts", "symbol"]).reset_index(drop=True)

    rows = []
    for (regime, symbol), g in oos.groupby(["regime_pub", "symbol"]):
        g = g.sort_values("fri_ts")
        x = g["score_lwc"].to_numpy(float)
        n = len(x)
        if n < 10:
            rows.append({
                "regime": regime, "symbol": symbol, "n": int(n),
                "lag1_rho_obs": float("nan"), "perm_p_two_sided": float("nan"),
                "skip_reason": "n<10",
            })
            continue
        rho_obs, p_two = perm_test_lag1(x, N_PERM)
        rows.append({
            "regime": str(regime), "symbol": str(symbol), "n": int(n),
            "lag1_rho_obs": float(rho_obs),
            "perm_p_two_sided": float(p_two),
            "skip_reason": "",
        })

    df = pd.DataFrame(rows)
    out = REPORTS / "tables" / "paper1_b2_exchangeability.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out}")

    valid = df[df["perm_p_two_sided"].notna()].copy()
    print(f"\n{len(valid)} bins with valid permutation test (n ≥ 10):")
    print(valid.sort_values("perm_p_two_sided").to_string(index=False,
            float_format=lambda x: f"{x:.4f}"))

    # Aggregate diagnostics
    print("\n=== aggregate exchangeability diagnostic ===")
    p_arr = valid["perm_p_two_sided"].to_numpy(float)
    n_reject_05 = int((p_arr < 0.05).sum())
    n_reject_01 = int((p_arr < 0.01).sum())
    print(f"  rejection rate at α=0.05: {n_reject_05}/{len(p_arr)} "
          f"({100*n_reject_05/len(p_arr):.1f}%) — expected ~5% under exchangeability")
    print(f"  rejection rate at α=0.01: {n_reject_01}/{len(p_arr)} "
          f"({100*n_reject_01/len(p_arr):.1f}%) — expected ~1% under exchangeability")

    # KS test of p-values vs Uniform(0,1)
    ks_stat, ks_p = kstest(p_arr, "uniform")
    print(f"  KS test: per-bin p-values vs Uniform(0,1): "
          f"D={ks_stat:.4f}  p={ks_p:.4f}")

    # Extreme-bin disclosure
    extreme = valid.sort_values("perm_p_two_sided").head(3)
    print(f"\n  three smallest perm p-values:")
    for _, r in extreme.iterrows():
        print(f"    {r['symbol']:6s}  {r['regime']:14s}  n={int(r['n']):3d}  "
              f"ρ̂_lag1={r['lag1_rho_obs']:+.4f}  p={r['perm_p_two_sided']:.4f}")


if __name__ == "__main__":
    main()
