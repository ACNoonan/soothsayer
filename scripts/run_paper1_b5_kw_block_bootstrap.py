"""Paper 1 — Tier B item B5.

Pairs-block-bootstrap CI for the k_w distribution at τ=0.95.

The current §6.3.4 bootstrap on k_w summary statistics assumes
i.i.d.-weekend draws — weekend-block-bootstrap respects within-weekend
dependence (the 10 symbols stay together) but treats weekends as
exchangeable across time. If weekly k_w shows temporal persistence (e.g.,
clustered high-k_w weekends in a regime cluster), the i.i.d.-weekend
bootstrap underestimates the CI width.

This script:
  1. Computes the OOS k_w time series at τ ∈ {0.85, 0.95, 0.99}.
  2. Tests it for autocorrelation (lag-1, lag-2, lag-4 Pearson ρ).
  3. Runs three bootstraps:
       - I.I.D. weekend-bootstrap (deployed convention; L=1)
       - Moving-block-bootstrap with block lengths L ∈ {4, 8, 13}
  4. Reports CIs on key statistics and compares widths.

Key statistics on the OOS k_w distribution:
  - mean k_w
  - var  k_w
  - P(k_w ≥ 3)
  - var-overdispersion ratio (var_empirical / Binom(10, τ̄)_var)

Output:
  reports/tables/paper1_b5_kw_block_bootstrap.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    add_sigma_hat_sym_ewma,
    SIGMA_HAT_HL_WEEKENDS,
    train_quantile_table,
    fit_c_bump_schedule,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
HEADLINE_TAUS = (0.85, 0.95, 0.99)
N_BOOTSTRAP = 5_000
BLOCK_LENGTHS = (1, 4, 8, 13)
RNG = np.random.default_rng(20260506)


def block_bootstrap(values: np.ndarray, block_len: int, n_boot: int,
                    statistic_fn) -> np.ndarray:
    """Moving-block-bootstrap. `values` is 1D ordered (chronologically here).

    For each bootstrap rep:
      - Concatenate ⌈n / block_len⌉ blocks of length `block_len`, each block
        starting at a uniform-random index in [0, n - block_len].
      - Trim to length n.
      - Compute statistic.

    Block_len = 1 reduces to ordinary i.i.d. bootstrap.
    """
    n = len(values)
    if block_len < 1 or block_len > n:
        raise ValueError(f"block_len {block_len} out of range")
    n_blocks = int(np.ceil(n / block_len))
    out = np.empty(n_boot)
    for i in range(n_boot):
        starts = RNG.integers(0, n - block_len + 1, size=n_blocks)
        sample = np.concatenate([values[s:s + block_len] for s in starts])[:n]
        out[i] = statistic_fn(sample)
    return out


def autocorr(x: np.ndarray, lag: int) -> float:
    if lag <= 0 or lag >= len(x):
        return float("nan")
    a = x[:-lag]
    b = x[lag:]
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


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

    train = panel[panel["fri_ts"] <  SPLIT_DATE].reset_index(drop=True)
    oos   = panel[panel["fri_ts"] >= SPLIT_DATE].sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    qt = train_quantile_table(train, cell_col="regime_pub",
                               taus=HEADLINE_TAUS, score_col="score_lwc")
    cb = fit_c_bump_schedule(oos, qt, cell_col="regime_pub",
                              taus=HEADLINE_TAUS, score_col="score_lwc")

    rows_summary = []
    for tau in HEADLINE_TAUS:
        c = cb[tau]
        cells = oos["regime_pub"].astype(str).to_numpy()
        sigma = oos["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
        score = oos["score_lwc"].astype(float).to_numpy()
        b_per_row = np.array(
            [qt.get(cells[i], {}).get(tau, np.nan) for i in range(len(oos))],
            dtype=float,
        )
        valid = np.isfinite(score) & np.isfinite(b_per_row) & np.isfinite(sigma) & (sigma > 0)
        sub = oos[valid].copy()
        sub["score"] = score[valid]
        sub["b_eff"] = b_per_row[valid] * c
        sub["viol"] = (sub["score"] > sub["b_eff"]).astype(int)
        kw_per_weekend = sub.groupby("fri_ts")["viol"].sum().to_numpy()
        viol_rate_per_sym = sub.groupby("symbol")["viol"].mean().to_numpy()
        tau_bar = float(viol_rate_per_sym.mean())

        # Autocorrelation
        ac1 = autocorr(kw_per_weekend.astype(float), 1)
        ac2 = autocorr(kw_per_weekend.astype(float), 2)
        ac4 = autocorr(kw_per_weekend.astype(float), 4)
        print(f"\n=== τ = {tau} ===")
        print(f"  empirical OOS k_w autocorrelation: lag1={ac1:.4f}  "
              f"lag2={ac2:.4f}  lag4={ac4:.4f}")
        print(f"  τ̄ violation rate (mean of per-sym): {tau_bar:.4f}")

        # Statistics to CI
        def stat_mean(x):    return float(np.mean(x))
        def stat_var(x):     return float(np.var(x))
        def stat_pge3(x):    return float((x >= 3).mean())
        def stat_pge5(x):    return float((x >= 5).mean())
        def stat_overdisp(x):
            v = np.var(x)
            v_binom = 10 * tau_bar * (1.0 - tau_bar)
            return float(v / v_binom) if v_binom > 0 else float("nan")

        statistics = [
            ("mean_kw", stat_mean),
            ("var_kw", stat_var),
            ("P_kw_ge_3", stat_pge3),
            ("P_kw_ge_5", stat_pge5),
            ("var_overdispersion", stat_overdisp),
        ]

        for L in BLOCK_LENGTHS:
            for stat_name, fn in statistics:
                samples = block_bootstrap(kw_per_weekend.astype(float), L,
                                           N_BOOTSTRAP, fn)
                stat_obs = fn(kw_per_weekend.astype(float))
                lo = float(np.quantile(samples, 0.025))
                hi = float(np.quantile(samples, 0.975))
                rows_summary.append({
                    "tau": tau,
                    "block_length": L,
                    "block_label": "iid_weekend" if L == 1 else f"L={L}",
                    "statistic": stat_name,
                    "observed": stat_obs,
                    "ci_lo": lo,
                    "ci_hi": hi,
                    "ci_width": hi - lo,
                    "ac1_kw": ac1,
                    "ac2_kw": ac2,
                    "ac4_kw": ac4,
                    "n_weekends": int(len(kw_per_weekend)),
                })

    df = pd.DataFrame(rows_summary)
    out = REPORTS / "tables" / "paper1_b5_kw_block_bootstrap.csv"
    df.to_csv(out, index=False)
    print(f"\nwrote {out}")

    print("\n=== headline τ=0.95 CI widths across block lengths ===")
    sub = df[df["tau"] == 0.95]
    pivot = sub.pivot_table(index="statistic", columns="block_length",
                              values="ci_width")
    print(pivot.to_string(float_format=lambda x: f"{x:.4f}"))

    print("\n=== headline τ=0.95 CI bounds (L=1 vs L=8 vs L=13) ===")
    for stat in ("mean_kw", "var_kw", "P_kw_ge_3", "var_overdispersion"):
        rows = sub[sub["statistic"] == stat]
        for L in (1, 8, 13):
            r = rows[rows["block_length"] == L].iloc[0]
            print(f"  {stat:22s} L={L:2d}: obs={r['observed']:.4f}  "
                  f"CI=[{r['ci_lo']:.4f}, {r['ci_hi']:.4f}]")


if __name__ == "__main__":
    main()
