"""
M6 Phase 7.1 — Portfolio-level violation clustering.

For each OOS weekend at served τ ∈ {0.85, 0.95, 0.99}, count the number of
symbols (out of the 10-symbol panel) whose realised Mon-open breached its
served LWC band. Compare the empirical distribution of weekend-level
breach counts `k_w` to the independence prediction `Binomial(n_w, 1-τ)`.

Either outcome is paper-strengthening:
  • If breaches cluster, give consumers the empirical tail (reserve against
    P(k_w ≥ k) at the empirical, not the binomial — no incumbent oracle
    publishes this).
  • If breaches do not cluster, the §6.3.1 cross-sectional concern is
    defused with a positive result.

Run under both forecasters (M5 deployed Mondrian + M6 LWC) so the paper
can claim "M6 doesn't worsen clustering" alongside the headline.

Outputs
-------
  reports/tables/m6_portfolio_clustering.csv
      Long-format aggregate statistics: forecaster × tau × statistic.
  reports/tables/m6_portfolio_clustering_per_weekend.csv
      Per-weekend breach counts: forecaster × fri_ts × tau × n_w × k_w.
  reports/figures/portfolio_clustering.{pdf,png}
      3-panel empirical-vs-binomial PMF (one panel per τ).

Run
---
  uv run python -u scripts/run_portfolio_clustering.py
"""

from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binom, chisquare

from soothsayer.backtest.calibration import (
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
FORECASTERS = ("m5", "lwc")
TAUS = (0.85, 0.95, 0.99)
TAIL_K = (3, 5, 7)
N_PANEL = 10  # canonical xStock universe size used by the LWC artefact
BOOT_REPS = 1000
BOOT_SEED = 0

OUT_TABLES = REPORTS / "tables"
OUT_FIGURES = REPORTS / "figures"


# --------------------------------------------------------- panel + serving


def serve_oos(forecaster: str) -> tuple[pd.DataFrame, dict[float, pd.DataFrame]]:
    """Same recipe used by `run_m6_pooled_oos_tables.py`. Returns
    (oos_panel, bounds_at_taus_dict)."""
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = prep_panel_for_forecaster(panel, forecaster)

    qt, cb, _ = fit_split_conformal_forecaster(
        panel, SPLIT_DATE, forecaster, cell_col="regime_pub",
    )
    oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
           .dropna(subset=["score"])
           .sort_values(["fri_ts", "symbol"])
           .reset_index(drop=True))
    bounds = serve_bands_forecaster(
        oos, qt, cb, forecaster, cell_col="regime_pub", taus=TAUS,
    )
    return oos, bounds


def per_weekend_breaches(
    oos: pd.DataFrame, bounds: dict[float, pd.DataFrame], tau: float,
) -> pd.DataFrame:
    """One row per OOS weekend: (fri_ts, n_w, k_w)."""
    band = bounds[tau]
    breach = ((oos["mon_open"] < band["lower"]) |
              (oos["mon_open"] > band["upper"])).astype(int)
    df = pd.DataFrame({"fri_ts": oos["fri_ts"].to_numpy(),
                       "breach": breach.to_numpy()})
    grp = df.groupby("fri_ts", as_index=False).agg(
        n_w=("breach", "size"), k_w=("breach", "sum")
    )
    return grp.sort_values("fri_ts").reset_index(drop=True)


# --------------------------------------------------------- statistics


def empirical_pmf(k: np.ndarray, n: int) -> np.ndarray:
    """Empirical PMF over support 0..n."""
    counts = np.bincount(k, minlength=n + 1)[: n + 1].astype(float)
    return counts / counts.sum() if counts.sum() > 0 else counts


def ks_distance(emp_cdf: np.ndarray, ref_cdf: np.ndarray) -> float:
    return float(np.max(np.abs(emp_cdf - ref_cdf)))


def block_bootstrap_tail_ci(
    weekly: pd.DataFrame, tau: float, n_panel: int, k_min: int,
    *, reps: int = BOOT_REPS, seed: int = BOOT_SEED,
) -> tuple[float, float, float]:
    """Bootstrap 95% CI on empirical P(k_w ≥ k_min) by weekend resample.

    Resampling unit = whole weekends (preserves cross-symbol structure)."""
    full = weekly[weekly["n_w"] == n_panel]["k_w"].to_numpy()
    if len(full) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    point = float((full >= k_min).mean())
    draws = np.empty(reps, dtype=float)
    n = len(full)
    for r in range(reps):
        idx = rng.integers(0, n, size=n)
        draws[r] = (full[idx] >= k_min).mean()
    lo, hi = np.quantile(draws, (0.025, 0.975))
    return point, float(lo), float(hi)


def aggregate_statistics(
    weekly: pd.DataFrame, tau: float, forecaster: str, n_panel: int = N_PANEL,
) -> pd.DataFrame:
    """Long-format rows for the aggregate CSV.

    The Binomial(n_panel, 1-τ) reference is the only well-defined common-mode
    null when weekends with partial symbol coverage are excluded. We restrict
    the comparison to weekends with `n_w == n_panel` and report `n_dropped`
    transparently."""
    full = weekly[weekly["n_w"] == n_panel]["k_w"].to_numpy()
    n_dropped = int((weekly["n_w"] != n_panel).sum())

    p = 1.0 - tau
    binom_pmf = binom.pmf(np.arange(n_panel + 1), n_panel, p)
    binom_cdf = np.cumsum(binom_pmf)
    binom_mean = n_panel * p
    binom_var = n_panel * p * (1.0 - p)

    rows: list[dict] = [
        {"forecaster": forecaster, "tau": float(tau),
         "statistic": "n_weekends_full", "value": float(len(full))},
        {"forecaster": forecaster, "tau": float(tau),
         "statistic": "n_weekends_dropped", "value": float(n_dropped)},
        {"forecaster": forecaster, "tau": float(tau),
         "statistic": "binomial_mean", "value": float(binom_mean)},
        {"forecaster": forecaster, "tau": float(tau),
         "statistic": "binomial_var", "value": float(binom_var)},
    ]

    if len(full) == 0:
        return pd.DataFrame(rows)

    emp_pmf = empirical_pmf(full, n_panel)
    emp_cdf = np.cumsum(emp_pmf)
    emp_mean = float(full.mean())
    emp_var = float(full.var(ddof=1)) if len(full) > 1 else float("nan")

    rows.extend([
        {"forecaster": forecaster, "tau": float(tau),
         "statistic": "empirical_mean", "value": emp_mean},
        {"forecaster": forecaster, "tau": float(tau),
         "statistic": "empirical_var", "value": emp_var},
        {"forecaster": forecaster, "tau": float(tau),
         "statistic": "var_ratio_emp_over_binom",
         "value": float(emp_var / binom_var) if binom_var > 0 else float("nan")},
        {"forecaster": forecaster, "tau": float(tau),
         "statistic": "ks_distance", "value": ks_distance(emp_cdf, binom_cdf)},
    ])

    # Chi-square GOF, bins {0, 1, 2, ≥3}. The lower bins typically dominate
    # at τ=0.95 (binomial mean = 0.5 breaches/weekend). Pooling the upper
    # tail keeps min expected count above the standard ≥5 rule of thumb.
    bins = [0, 1, 2]
    obs = np.array([float((full == b).sum()) for b in bins] +
                   [float((full >= 3).sum())])
    exp = np.array([binom.pmf(b, n_panel, p) * len(full) for b in bins] +
                   [(1.0 - binom.cdf(2, n_panel, p)) * len(full)])
    # Drop bins where expected count < 1 (chi-square unreliable below this).
    mask = exp >= 1.0
    if mask.sum() >= 2:
        # Renormalise so observed and expected sum to the same total.
        obs_m, exp_m = obs[mask], exp[mask]
        exp_m = exp_m * (obs_m.sum() / exp_m.sum())
        chi_stat, chi_p = chisquare(obs_m, exp_m)
        rows.append({"forecaster": forecaster, "tau": float(tau),
                     "statistic": "chi2_stat", "value": float(chi_stat)})
        rows.append({"forecaster": forecaster, "tau": float(tau),
                     "statistic": "chi2_p", "value": float(chi_p)})

    # Tail probabilities at k_min ∈ {3, 5, 7}.
    for k_min in TAIL_K:
        emp_p = float((full >= k_min).mean())
        bin_p = float(1.0 - binom.cdf(k_min - 1, n_panel, p))
        _, lo, hi = block_bootstrap_tail_ci(weekly, tau, n_panel, k_min)
        rows.extend([
            {"forecaster": forecaster, "tau": float(tau),
             "statistic": f"emp_p_ge_{k_min}", "value": emp_p},
            {"forecaster": forecaster, "tau": float(tau),
             "statistic": f"emp_p_ge_{k_min}_ci_lo", "value": lo},
            {"forecaster": forecaster, "tau": float(tau),
             "statistic": f"emp_p_ge_{k_min}_ci_hi", "value": hi},
            {"forecaster": forecaster, "tau": float(tau),
             "statistic": f"binom_p_ge_{k_min}", "value": bin_p},
            {"forecaster": forecaster, "tau": float(tau),
             "statistic": f"ratio_emp_over_binom_ge_{k_min}",
             "value": float(emp_p / bin_p) if bin_p > 0 else float("nan")},
        ])

    return pd.DataFrame(rows)


# --------------------------------------------------------- figure


def render_figure(
    pmfs: dict[tuple[str, float], np.ndarray], out_dir,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.5), sharey=False)
    colors = {"m5": "#d62728", "lwc": "#1f77b4"}
    width = 0.38
    for ax, tau in zip(axes, TAUS):
        p = 1.0 - tau
        x = np.arange(N_PANEL + 1)
        binom_pmf = binom.pmf(x, N_PANEL, p)
        # Trim x-axis to the maximum support that has visible mass.
        max_k = int(max(
            np.where(pmfs[("lwc", tau)] > 1e-6)[0].max() if pmfs[("lwc", tau)].any() else 0,
            np.where(pmfs[("m5", tau)] > 1e-6)[0].max() if pmfs[("m5", tau)].any() else 0,
            np.where(binom_pmf > 1e-4)[0].max(),
        ))
        max_k = min(max(max_k + 1, 4), N_PANEL)
        ax.bar(x[: max_k + 1] - width / 2, pmfs[("m5", tau)][: max_k + 1],
               width=width, color=colors["m5"], alpha=0.85,
               edgecolor="black", linewidth=0.4, label="M5 empirical")
        ax.bar(x[: max_k + 1] + width / 2, pmfs[("lwc", tau)][: max_k + 1],
               width=width, color=colors["lwc"], alpha=0.85,
               edgecolor="black", linewidth=0.4, label="M6 LWC empirical")
        ax.plot(x[: max_k + 1], binom_pmf[: max_k + 1],
                marker="D", color="black", linewidth=1.0, markersize=5,
                label=f"Binomial(10, {p:.2f}) reference")
        ax.set_xticks(x[: max_k + 1])
        ax.set_xlabel("k = simultaneous breaches in a weekend")
        ax.set_ylabel("P(k_w = k)")
        ax.set_title(f"τ = {tau:.2f}")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(axis="y", linewidth=0.3, alpha=0.5)
    fig.suptitle("Phase 7.1 — Portfolio-level violation clustering "
                 "(2023+ OOS, n=10 symbols)", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    pdf_path = out_dir / "portfolio_clustering.pdf"
    png_path = out_dir / "portfolio_clustering.png"
    fig.savefig(pdf_path)
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    print(f"\nWrote {pdf_path}", flush=True)
    print(f"Wrote {png_path}", flush=True)


# --------------------------------------------------------- main


def main() -> None:
    OUT_TABLES.mkdir(parents=True, exist_ok=True)
    OUT_FIGURES.mkdir(parents=True, exist_ok=True)

    agg_rows: list[pd.DataFrame] = []
    week_rows: list[pd.DataFrame] = []
    pmfs: dict[tuple[str, float], np.ndarray] = {}

    for fc in FORECASTERS:
        print(f"\n=== {fc.upper()} ===", flush=True)
        oos, bounds = serve_oos(fc)
        n_oos_rows, n_weekends = len(oos), oos["fri_ts"].nunique()
        print(f"OOS: {n_oos_rows:,} rows × {n_weekends} weekends", flush=True)
        for tau in TAUS:
            weekly = per_weekend_breaches(oos, bounds, tau)
            weekly = weekly.assign(forecaster=fc, tau=float(tau))
            week_rows.append(weekly)
            agg_rows.append(aggregate_statistics(weekly, tau, fc))
            full = weekly[weekly["n_w"] == N_PANEL]["k_w"].to_numpy()
            pmfs[(fc, tau)] = (empirical_pmf(full, N_PANEL) if len(full)
                               else np.zeros(N_PANEL + 1))
            print(f"  τ={tau:.2f}  n_full={len(full)}  "
                  f"mean k_w={full.mean():.3f}  max k_w={int(full.max())}",
                  flush=True)

    agg = pd.concat(agg_rows, ignore_index=True)
    week = pd.concat(week_rows, ignore_index=True)[
        ["forecaster", "tau", "fri_ts", "n_w", "k_w"]
    ]
    out_agg = OUT_TABLES / "m6_portfolio_clustering.csv"
    out_week = OUT_TABLES / "m6_portfolio_clustering_per_weekend.csv"
    agg.to_csv(out_agg, index=False)
    week.to_csv(out_week, index=False)
    print(f"\nWrote {out_agg}", flush=True)
    print(f"Wrote {out_week}", flush=True)

    render_figure(pmfs, OUT_FIGURES)

    # ------------------- console summary
    print("\n" + "=" * 96)
    print("HEADLINE — empirical P(k_w ≥ k) vs Binomial(10, 1-τ)  "
          "[full-coverage weekends only]")
    print("=" * 96)
    pivot = agg.pivot_table(
        index=["forecaster", "tau"], columns="statistic", values="value",
    )
    show_cols: list[str] = []
    for k in TAIL_K:
        show_cols.extend([f"emp_p_ge_{k}", f"binom_p_ge_{k}"])
    show_cols.extend(["var_ratio_emp_over_binom", "ks_distance", "chi2_p"])
    show_cols = [c for c in show_cols if c in pivot.columns]
    print(pivot[show_cols].to_string(float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
