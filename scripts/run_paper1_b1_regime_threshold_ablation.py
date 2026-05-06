"""Paper 1 — Tier B item B1.

Regime-quartile threshold + split-anchor as proper ablations in the §7.4
three-gate frame.

The deployed regime classifier flags a weekend `high_vol` if VIX_fri_close
is above the 75th percentile of its trailing 52-weekend (≈ 252 trading-day)
window. The 75th percentile is a free parameter — a quartile by convention
but not by derivation. This ablation enumerates alternates and confirms
robustness.

Candidate VIX percentile cutoffs:
  q ∈ {0.60, 0.67, 0.70, 0.75, 0.80, 0.90}
  q = 0.75 is deployed (top quartile).

Three-gate frame (§7.4 σ̂-selection criterion, applied to regime cutoff):
  Gate 1: pooled Kupiec / Christoffersen at every served τ ∈ {0.68, 0.85,
          0.95, 0.99} — calibration must hold.
  Gate 2: per-symbol Kupiec at τ = 0.95 — 10/10 pass preserved.
  Gate 3: bootstrap CI on pooled half-width at τ = 0.95 — deployed value
          must not be statistically wider than the best-performing
          alternate (the deployed value need not be the *narrowest*; it
          must not be *worse* than the narrowest at preserved calibration).

For the split-anchor ablation we re-use the existing
`reports/tables/m6_lwc_robustness_split_sensitivity.csv` produced by
`scripts/run_v1b_split_sensitivity.py`. This script focuses on the
regime-cutoff leg.

Output:
  reports/tables/paper1_b1_regime_threshold_ablation.csv
  reports/tables/paper1_b1_regime_threshold_ablation_per_symbol.csv
  reports/tables/paper1_b1_regime_threshold_ablation_hw_bootstrap.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
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
VIX_QUARTILE_CANDIDATES = (0.60, 0.67, 0.70, 0.75, 0.80, 0.90)
DEPLOYED_QUARTILE = 0.75
N_BOOTSTRAP = 2_000
RNG = np.random.default_rng(20260506)


def retag_regime_at_quantile(panel: pd.DataFrame, q: float) -> pd.Series:
    """Re-compute `regime_pub` using a configurable VIX percentile cutoff.

    Mirrors `soothsayer.backtest.regimes._high_vol_flag` but with a
    parametric q instead of the hard-coded 0.75.
    """
    vix = panel[["fri_ts", "vix_fri_close"]].drop_duplicates().sort_values("fri_ts")
    rolling = vix["vix_fri_close"].rolling(52, min_periods=20).quantile(q)
    lookup = pd.Series(rolling.values, index=vix["fri_ts"].values)
    high_vol = panel["fri_ts"].map(lookup).lt(panel["vix_fri_close"]).fillna(False)
    regime = pd.Series("normal", index=panel.index, dtype=object)
    regime.loc[panel["gap_days"] >= 4] = "long_weekend"
    regime.loc[high_vol.values] = "high_vol"
    return regime


def evaluate_at_taus(panel_oos: pd.DataFrame,
                     qt: dict, cb: dict,
                     taus: tuple[float, ...]) -> pd.DataFrame:
    rows = []
    cells = panel_oos["regime_pub"].astype(str).to_numpy()
    sigma = panel_oos["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    score = panel_oos["score_lwc"].astype(float).to_numpy()
    base_valid = np.isfinite(score) & np.isfinite(sigma) & (sigma > 0)
    for tau in taus:
        c = cb[tau]
        b_per_row = np.array(
            [qt.get(cells[i], {}).get(tau, np.nan)
             for i in range(len(panel_oos))],
            dtype=float,
        )
        valid = base_valid & np.isfinite(b_per_row)
        s = score[valid]
        b_eff = b_per_row[valid] * c
        inside = (s <= b_eff).astype(int)
        viol = (1 - inside).astype(int)
        lr_uc, p_uc = met._lr_kupiec(viol, tau)
        lr_ind, p_ind = met._lr_christoffersen_independence(viol)
        sigma_v = sigma[valid]
        hw_bps = b_eff * sigma_v * 1e4
        rows.append({
            "target": tau, "bump_c": float(c),
            "n_oos": int(valid.sum()),
            "realised": float(inside.mean()),
            "kupiec_p": float(p_uc),
            "christoffersen_p": float(p_ind),
            "half_width_bps_mean": float(hw_bps.mean()),
            "half_width_bps_median": float(np.median(hw_bps)),
            # Store per-row hw for bootstrap
            "_hw_bps_arr": hw_bps,
        })
    return pd.DataFrame(rows)


def per_symbol_pass(panel_oos: pd.DataFrame, qt: dict, cb: dict,
                    tau: float = 0.95) -> tuple[int, int, list[dict]]:
    cells = panel_oos["regime_pub"].astype(str).to_numpy()
    score = panel_oos["score_lwc"].astype(float).to_numpy()
    sigma = panel_oos["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    c = cb[tau]
    b_per_row = np.array(
        [qt.get(cells[i], {}).get(tau, np.nan) for i in range(len(panel_oos))],
        dtype=float,
    )
    valid = np.isfinite(score) & np.isfinite(b_per_row) & np.isfinite(sigma) & (sigma > 0)
    sub = panel_oos[valid].copy()
    sub["score"] = score[valid]
    sub["b_eff"] = b_per_row[valid] * c
    sub["viol"] = (sub["score"] > sub["b_eff"]).astype(int)
    rows = []
    n_pass = 0
    n_total = 0
    for sym, g in sub.groupby("symbol"):
        v = g["viol"].to_numpy()
        if len(v) < 5:
            continue
        n_total += 1
        _, p = met._lr_kupiec(v, tau)
        if p >= 0.05:
            n_pass += 1
        rows.append({"symbol": str(sym), "n": int(len(v)),
                     "viol_rate": float(v.mean()), "kupiec_p": float(p)})
    return n_pass, n_total, rows


def bootstrap_hw_diff(hw_a: np.ndarray, hw_b: np.ndarray,
                      n_boot: int = N_BOOTSTRAP) -> dict:
    """Paired-bootstrap CI on (mean(hw_b) − mean(hw_a)) / mean(hw_a) (%)."""
    if len(hw_a) != len(hw_b):
        # If the row counts differ (different regime tags drop different rows),
        # use unpaired difference of means
        diffs = np.empty(n_boot)
        for i in range(n_boot):
            sa = RNG.choice(hw_a, size=len(hw_a), replace=True)
            sb = RNG.choice(hw_b, size=len(hw_b), replace=True)
            diffs[i] = (sb.mean() - sa.mean()) / sa.mean()
    else:
        diffs = np.empty(n_boot)
        idx = np.arange(len(hw_a))
        for i in range(n_boot):
            ix = RNG.choice(idx, size=len(idx), replace=True)
            diffs[i] = (hw_b[ix].mean() - hw_a[ix].mean()) / hw_a[ix].mean()
    return {
        "mean_diff_pct": float(diffs.mean()),
        "ci_lo_pct": float(np.quantile(diffs, 0.025)),
        "ci_hi_pct": float(np.quantile(diffs, 0.975)),
    }


def main() -> None:
    panel_raw = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel_raw["fri_ts"] = pd.to_datetime(panel_raw["fri_ts"]).dt.date
    panel_raw = panel_raw.dropna(
        subset=["mon_open", "fri_close", "factor_ret", "vix_fri_close",
                "gap_days"]
    ).reset_index(drop=True)

    pooled_rows = []
    persym_rows = []
    hw_arrays = {}  # quartile_q → hw_bps array at τ=0.95
    persym_pass_by_q = {}

    for q in VIX_QUARTILE_CANDIDATES:
        print(f"\n=== regime quartile cut q = {q} ===", flush=True)
        panel = panel_raw.copy()
        panel["regime_pub"] = retag_regime_at_quantile(panel, q).astype(str)
        # Sanity: regime mix
        mix = panel["regime_pub"].value_counts(normalize=True)
        print(f"  regime mix:")
        for r, v in mix.items():
            print(f"    {r}: {v*100:.1f}%")

        # Re-compute LWC σ̂ + score under new regime tagging
        # (σ̂ doesn't depend on regime, but we want a clean per-q panel)
        panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HAT_HL_WEEKENDS)
        sigma_col = f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HAT_HL_WEEKENDS}"
        panel["sigma_hat_sym_pre_fri"] = panel[sigma_col]
        panel["score_lwc"] = compute_score_lwc(panel, scale_col="sigma_hat_sym_pre_fri")
        panel = panel[panel["score_lwc"].notna()].reset_index(drop=True)

        train = panel[panel["fri_ts"] <  SPLIT_DATE].reset_index(drop=True)
        oos   = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

        qt = train_quantile_table(train, cell_col="regime_pub",
                                   taus=HEADLINE_TAUS, score_col="score_lwc")
        cb = fit_c_bump_schedule(oos, qt, cell_col="regime_pub",
                                  taus=HEADLINE_TAUS, score_col="score_lwc")
        print(f"  c(τ): " + ", ".join(f"τ={t:.2f}→{cb[t]:.3f}" for t in HEADLINE_TAUS))
        print(f"  q_r per regime ({len(qt)} cells):")
        for r, row in qt.items():
            print(f"    {r}: " + ", ".join(f"τ={t}→{v:.3f}" for t, v in sorted(row.items())))

        df = evaluate_at_taus(oos, qt, cb, HEADLINE_TAUS)
        n_pass, n_total, persym_at_q = per_symbol_pass(oos, qt, cb, tau=0.95)
        print(f"  per-symbol Kupiec at τ=0.95: {n_pass}/{n_total} pass")
        persym_pass_by_q[q] = (n_pass, n_total)

        for r in df.to_dict("records"):
            r2 = {k: v for k, v in r.items() if not k.startswith("_")}
            r2["quartile_q"] = q
            r2["n_high_vol_weekends"] = int((panel["regime_pub"] == "high_vol").sum())
            pooled_rows.append(r2)
        for psr in persym_at_q:
            persym_rows.append({"quartile_q": q, **psr})

        # Capture hw array at τ=0.95 for bootstrap
        hw_at_95 = df[df["target"] == 0.95]["_hw_bps_arr"].iloc[0]
        hw_arrays[q] = np.asarray(hw_at_95)

    out_pool = REPORTS / "tables" / "paper1_b1_regime_threshold_ablation.csv"
    out_per  = REPORTS / "tables" / "paper1_b1_regime_threshold_ablation_per_symbol.csv"
    pd.DataFrame(pooled_rows).to_csv(out_pool, index=False)
    pd.DataFrame(persym_rows).to_csv(out_per, index=False)
    print(f"\nwrote {out_pool}\nwrote {out_per}")

    # Gate 3: bootstrap CI on Δhw% at τ=0.95 vs deployed q=0.75
    print("\n=== Gate 3: bootstrap CI on Δhw% at τ=0.95 vs deployed q=0.75 ===")
    boot_rows = []
    deployed_hw = hw_arrays[DEPLOYED_QUARTILE]
    for q in VIX_QUARTILE_CANDIDATES:
        if q == DEPLOYED_QUARTILE:
            boot_rows.append({"quartile_q": q,
                              "mean_diff_pct_vs_deployed": 0.0,
                              "ci_lo_pct": 0.0, "ci_hi_pct": 0.0,
                              "n_a_deployed": int(len(deployed_hw)),
                              "n_b": int(len(deployed_hw)),
                              "deployed_q": DEPLOYED_QUARTILE})
            continue
        b = bootstrap_hw_diff(deployed_hw, hw_arrays[q])
        boot_rows.append({"quartile_q": q,
                           "mean_diff_pct_vs_deployed": b["mean_diff_pct"],
                           "ci_lo_pct": b["ci_lo_pct"],
                           "ci_hi_pct": b["ci_hi_pct"],
                           "n_a_deployed": int(len(deployed_hw)),
                           "n_b": int(len(hw_arrays[q])),
                           "deployed_q": DEPLOYED_QUARTILE})
        print(f"  q={q}: Δhw%/deployed = {b['mean_diff_pct']*100:+.2f}% "
              f"(95% CI [{b['ci_lo_pct']*100:+.2f}%, {b['ci_hi_pct']*100:+.2f}%])")

    out_boot = REPORTS / "tables" / "paper1_b1_regime_threshold_ablation_hw_bootstrap.csv"
    pd.DataFrame(boot_rows).to_csv(out_boot, index=False)
    print(f"\nwrote {out_boot}")

    # Three-gate summary
    print("\n=== three-gate summary across q ===")
    gate_summary = []
    for q in VIX_QUARTILE_CANDIDATES:
        sub = pd.DataFrame([r for r in pooled_rows if r["quartile_q"] == q])
        # Gate 1: pooled Kupiec p ≥ 0.05 at every τ
        g1 = bool((sub["kupiec_p"] >= 0.05).all())
        # Gate 1b: pooled Christoffersen p ≥ 0.05 at every τ
        g1b = bool((sub["christoffersen_p"] >= 0.05).all())
        # Gate 2: per-symbol 10/10
        n_pass, n_total = persym_pass_by_q[q]
        g2 = (n_pass == n_total)
        # Gate 3: hw not statistically wider than deployed (CI lo ≥ -∞ trivial; meaningful: hw not narrower than deployed at level α — use: deployed is *not significantly* wider than q if CI on Δhw% includes 0 OR is negative)
        boot = next(r for r in boot_rows if r["quartile_q"] == q)
        # The deployed value should not be wider than alternate at preserved cal:
        # diff is (q's hw - deployed hw) / deployed hw. If q is wider, diff > 0.
        # So deployed is "not wider" when diff_q ≥ 0 OR CI includes 0.
        # Gate 3 here simply: deployed value must not be statistically wider than this alternate.
        # If alternate q gives narrower hw with CI excluding 0 from above, that's a problem.
        is_alt_significantly_narrower = (boot["ci_hi_pct"] < 0) and (q != DEPLOYED_QUARTILE)
        g3 = not is_alt_significantly_narrower
        gate_summary.append({
            "quartile_q": q,
            "deployed": q == DEPLOYED_QUARTILE,
            "gate1_kupiec_all_tau": g1,
            "gate1b_christoffersen_all_tau": g1b,
            "gate2_per_symbol_kupiec": f"{n_pass}/{n_total}",
            "gate2_pass": g2,
            "gate3_hw_diff_pct_mean": boot["mean_diff_pct_vs_deployed"],
            "gate3_hw_ci_lo_pct": boot["ci_lo_pct"],
            "gate3_hw_ci_hi_pct": boot["ci_hi_pct"],
            "gate3_alt_significantly_narrower": is_alt_significantly_narrower,
        })
    print(pd.DataFrame(gate_summary).to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
