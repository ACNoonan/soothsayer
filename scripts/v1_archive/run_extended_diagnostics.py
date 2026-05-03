"""
Extended diagnostics — Tier-1 follow-up:

  D5  Inter-anchor τ validation. The deployed `BUFFER_BY_TARGET` schedule has
      anchors at {0.68, 0.85, 0.95, 0.99} with linear interpolation off-grid.
      A consumer querying τ = 0.92 receives an interpolated buffer between
      0.85 and 0.95. Has the served band's realised coverage actually been
      validated at non-anchor targets, or is the interpolation a faith claim?

      Sweep τ at fine grid (0.50 → 0.99 step 0.01) on the OOS 2023+ panel,
      serve every row at every τ, compute pooled realised coverage + Kupiec
      p_uc per τ. A well-calibrated Oracle delivers realised ≈ τ at *every*
      grid point, not only the four anchors.

  D6  Served-band PIT uniformity. The earlier D3 diagnostic tested the raw
      forecaster's PIT (which is non-uniform by construction — that's why
      the calibration surface exists). The product claim, however, is that
      the *served band* (after surface inversion + per-target buffer)
      delivers calibration across the *full* (0,1) interval, not only at
      four anchor τ values.

      For each OOS row, the served-band PIT is τ_PIT = min{τ : mon_open ∈
      [L(τ), U(τ)]}. We find this by sweeping τ at the same fine grid as D5
      and recording, for each row, the smallest τ at which the served band
      covers mon_open (or 1.0 if uncovered at every τ in the grid). The
      Diebold-Gunther-Tay framework requires PIT ~ U(0,1); we KS-test.

Single script, single sweep of Oracle.fair_value calls, both diagnostics.

Outputs:
  reports/tables/v1b_diag_inter_anchor_tau.csv     per-τ pooled coverage
  reports/tables/v1b_diag_pit_served.csv           per-row served-band PIT
  reports/figures/v1b_diag_pit_served.png          PIT histogram + KS overlay
  reports/v1b_diagnostics_extended.md              writeup
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2, kstest

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


SPLIT_DATE = date(2023, 1, 1)
# Fine grid for both diagnostics. Below 0.50 is omitted because (a) protocols
# don't deploy at < 50% confidence and (b) below the lowest BUFFER_BY_TARGET
# anchor (0.68) the interpolation flat-extrapolates to 0.045 anyway.
TAU_GRID: tuple[float, ...] = tuple(round(0.50 + 0.01 * i, 2) for i in range(50))  # 0.50..0.99 step 0.01


def _tables_dir() -> Path:
    p = REPORTS / "tables"; p.mkdir(parents=True, exist_ok=True); return p


def _figures_dir() -> Path:
    p = REPORTS / "figures"; p.mkdir(parents=True, exist_ok=True); return p


def main() -> None:
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds["mon_ts"] = pd.to_datetime(bounds["mon_ts"]).dt.date
    panel_full = bounds[
        ["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]
    ].drop_duplicates(["symbol", "fri_ts"]).reset_index(drop=True)
    panel_oos = panel_full[panel_full["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)

    surface = cal.compute_calibration_surface(bounds_train)
    surface_pooled = cal.pooled_surface(bounds_train)
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)

    print(f"OOS panel: {len(panel_oos):,} rows; sweeping τ ∈ "
          f"[{TAU_GRID[0]}, {TAU_GRID[-1]}] step 0.01 ({len(TAU_GRID)} levels)…",
          flush=True)

    # Single sweep — for each (row, τ) record inside flag and band width.
    rows = []
    t0 = time.time()
    for i, w in panel_oos.iterrows():
        sym = w["symbol"]; fri = w["fri_ts"]; reg = w["regime_pub"]
        mon = float(w["mon_open"]); fri_c = float(w["fri_close"])
        first_cover_tau = None
        for tau in TAU_GRID:
            try:
                pp = oracle.fair_value(sym, fri, target_coverage=tau)
            except ValueError:
                continue
            inside = (mon >= pp.lower) and (mon <= pp.upper)
            rows.append({
                "symbol": sym, "fri_ts": fri, "regime_pub": reg,
                "tau": tau, "inside": int(inside),
                "half_width_bps": float(pp.half_width_bps),
                "claim_served": float(pp.claimed_coverage_served),
                "buffer_applied": float(pp.calibration_buffer_applied),
            })
            if first_cover_tau is None and inside:
                first_cover_tau = tau
        if (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            print(f"  [{i+1}/{len(panel_oos)}] elapsed={elapsed:.0f}s  "
                  f"rate={(i+1)/elapsed:.1f} rows/s", flush=True)
    full = pd.DataFrame(rows)
    print(f"\nServe complete in {time.time()-t0:.1f}s; {len(full):,} (row × τ) cells", flush=True)

    # ---------------------------------------------------------------
    # D5: inter-anchor τ validation (per-τ pooled coverage)
    # ---------------------------------------------------------------
    inter = []
    for tau in TAU_GRID:
        sub = full[full["tau"] == tau]
        if sub.empty:
            continue
        v = (~sub["inside"].astype(bool)).astype(int).values
        lr_uc, p_uc = met._lr_kupiec(v, tau)
        lr_ind_total, n_groups = 0.0, 0
        for sym, g in sub.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
            lr_ind, _ = met._lr_christoffersen_independence(
                (~g["inside"].astype(bool)).astype(int).values)
            if not np.isnan(lr_ind):
                lr_ind_total += lr_ind
                n_groups += 1
        p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
        inter.append({
            "tau": tau, "n": int(len(sub)),
            "realized": float(sub["inside"].mean()),
            "mean_half_width_bps": float(sub["half_width_bps"].mean()),
            "buffer_applied": float(sub["buffer_applied"].mean()),
            "lr_uc": float(lr_uc), "p_uc": float(p_uc),
            "lr_ind": float(lr_ind_total), "p_ind": p_ind,
            "is_anchor": tau in {0.68, 0.85, 0.95, 0.99},
        })
    inter_df = pd.DataFrame(inter)
    inter_df.to_csv(_tables_dir() / "v1b_diag_inter_anchor_tau.csv", index=False)

    # Largest deviation realised - τ across the grid
    inter_df["delta_realized_minus_target"] = inter_df["realized"] - inter_df["tau"]
    max_abs_dev = inter_df["delta_realized_minus_target"].abs().max()
    worst_tau_row = inter_df.iloc[inter_df["delta_realized_minus_target"].abs().idxmax()]
    n_kupiec_pass = int((inter_df["p_uc"] > 0.05).sum())
    n_kupiec_pass_strict = int((inter_df["p_uc"] > 0.10).sum())

    print()
    print("=" * 80)
    print("D5 — Inter-anchor τ validation")
    print("=" * 80)
    print(f"  Targets evaluated: {len(inter_df)}  (anchors flagged is_anchor=True)")
    print(f"  Kupiec p_uc > 0.05 at: {n_kupiec_pass}/{len(inter_df)} targets")
    print(f"  Kupiec p_uc > 0.10 at: {n_kupiec_pass_strict}/{len(inter_df)} targets")
    print(f"  Max |realised − τ|:    {max_abs_dev:.3f} (at τ = {worst_tau_row['tau']:.2f}, "
          f"realised = {worst_tau_row['realized']:.3f}, p_uc = {worst_tau_row['p_uc']:.3f})")
    print()
    # Print summary at every 5th target plus all anchors
    show = inter_df[(inter_df["is_anchor"]) | (inter_df["tau"].isin([0.55, 0.60, 0.70, 0.75, 0.80, 0.875, 0.90, 0.925, 0.96, 0.97, 0.98]))]
    print(show[["tau", "n", "realized", "mean_half_width_bps", "buffer_applied",
                "p_uc", "p_ind", "is_anchor"]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # ---------------------------------------------------------------
    # D6: served-band PIT
    # ---------------------------------------------------------------
    # For each row, find smallest τ at which inside=1; if never, PIT = 1.0
    pit_rows = []
    for (sym, fri), g in full.groupby(["symbol", "fri_ts"]):
        g_sorted = g.sort_values("tau")
        covered = g_sorted[g_sorted["inside"] == 1]
        if covered.empty:
            pit = 1.0
            cov_class = "uncovered_at_max_tau"
        else:
            pit = float(covered["tau"].min())
            cov_class = "covered"
        pit_rows.append({
            "symbol": sym, "fri_ts": fri,
            "regime_pub": g_sorted["regime_pub"].iloc[0],
            "pit": pit, "cov_class": cov_class,
        })
    pit_df = pd.DataFrame(pit_rows)
    pit_df.to_csv(_tables_dir() / "v1b_diag_pit_served.csv", index=False)

    # KS test against U(0,1). Cap at 0.999 for PIT=1.0 (uncovered tails) so the
    # KS doesn't reject solely because PITs pile up at exactly 1.0.
    pit_for_ks = pit_df["pit"].clip(0.001, 0.999)
    ks_stat, ks_p = kstest(pit_for_ks, "uniform")

    n_uncov = int((pit_df["cov_class"] == "uncovered_at_max_tau").sum())
    print()
    print("=" * 80)
    print("D6 — Served-band PIT uniformity")
    print("=" * 80)
    print(f"  n PIT values: {len(pit_df):,}")
    print(f"  n uncovered at max τ ({TAU_GRID[-1]}): {n_uncov} ({n_uncov/len(pit_df)*100:.1f}%)")
    print(f"  KS statistic vs U(0,1): {ks_stat:.4f}")
    print(f"  KS p-value:             {ks_p:.4f}")
    print(f"  → {'NOT rejected' if ks_p > 0.05 else 'REJECTED'} at α=0.05")

    # PIT histogram
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].hist(pit_df["pit"], bins=20, edgecolor="black", alpha=0.7)
    axes[0].axhline(len(pit_df) / 20, color="red", linestyle="--", label="uniform expectation")
    axes[0].set_xlabel("Served-band PIT (smallest τ at which served band covers mon_open)")
    axes[0].set_ylabel("Count")
    axes[0].set_title(f"D6 — Served-band PIT histogram\nKS = {ks_stat:.3f}, p = {ks_p:.3f} "
                       f"({'pass' if ks_p > 0.05 else 'reject'} α=0.05); n_uncov = {n_uncov}")
    axes[0].legend()

    # Inter-anchor calibration plot
    axes[1].plot([0, 1], [0, 1], "k--", alpha=0.5, label="perfect")
    anchors_sub = inter_df[inter_df["is_anchor"]]
    inter_sub = inter_df[~inter_df["is_anchor"]]
    axes[1].plot(inter_sub["tau"], inter_sub["realized"], "o-", color="C0",
                 markersize=4, alpha=0.7, label="inter-anchor τ")
    axes[1].plot(anchors_sub["tau"], anchors_sub["realized"], "s", color="C3",
                 markersize=10, label="anchor τ", zorder=5)
    axes[1].set_xlabel("Consumer target τ")
    axes[1].set_ylabel("Realised coverage on OOS")
    axes[1].set_title(f"D5 — Inter-anchor τ validation\n"
                       f"Kupiec pass at {n_kupiec_pass}/{len(inter_df)} targets (α=0.05); "
                       f"max |realised − τ| = {max_abs_dev:.3f}")
    axes[1].set_xlim(0.5, 1.0); axes[1].set_ylim(0.5, 1.0)
    axes[1].grid(True, alpha=0.3); axes[1].legend()
    fig.tight_layout()
    fig.savefig(_figures_dir() / "v1b_diag_pit_served.png", dpi=140)
    plt.close(fig)

    # Writeup
    md = [
        "# V1b — Extended diagnostics (D5, D6)",
        "",
        "Two follow-up diagnostics that close paper-side gaps identified in the bibliography review.",
        "",
        "## D5 — Inter-anchor τ validation",
        "",
        f"**Question.** The deployed `BUFFER_BY_TARGET` has anchors at $\\{{0.68, 0.85, 0.95, 0.99\\}}$ with linear interpolation off-grid. A consumer requesting $\\tau = 0.92$ receives an interpolated buffer between the 0.85 and 0.95 anchors. Is the resulting served band actually calibrated at non-anchor τ, or is the interpolation a faith claim?",
        "",
        f"**Method.** Sweep $\\tau \\in \\{{0.50, 0.51, \\ldots, 0.99\\}}$ ({len(TAU_GRID)} levels) on the OOS 2023+ panel ({len(panel_oos):,} rows × {len(TAU_GRID)} τ levels = {len(full):,} cells). At each target, compute pooled realised coverage and the Kupiec $p_{{uc}}$ test against the target rate.",
        "",
        f"**Result.** Kupiec $p_{{uc}} > 0.05$ at **{n_kupiec_pass}/{len(inter_df)}** targets and $p_{{uc}} > 0.10$ at **{n_kupiec_pass_strict}/{len(inter_df)}** targets. The maximum absolute deviation $|\\text{{realised}} - \\tau|$ across the grid is **{max_abs_dev:.3f}** (at $\\tau = {worst_tau_row['tau']:.2f}$, realised = {worst_tau_row['realized']:.3f}, $p_{{uc}}$ = {worst_tau_row['p_uc']:.3f}).",
        "",
        "Per-τ summary (anchors **bold**, every 5th interpolation point shown):",
        "",
        show[["tau", "n", "realized", "mean_half_width_bps", "buffer_applied", "p_uc", "p_ind", "is_anchor"]]
            .to_markdown(index=False, floatfmt=".3f"),
        "",
        "**Reading.** If realised coverage tracks $\\tau$ closely and $p_{uc}$ remains > 0.05 at the inter-anchor targets, the linear-interpolation deployment of `BUFFER_BY_TARGET` is empirically validated. If specific inter-anchor regions show systematic over- or under-coverage, the schedule should be densified (more anchors) or the interpolation function changed (spline, isotonic).",
        "",
        "## D6 — Served-band PIT uniformity",
        "",
        "**Question.** D3 (in `reports/v1b_diagnostics.md`) tested the raw forecaster's PIT and found it non-uniform by KS — that's expected, the raw forecaster is not calibrated, which is why the surface exists. The product claim is that the **served band** (after surface inversion + per-target buffer) delivers calibration *across the full $(0,1)$ interval*, not only at the four anchor τ.",
        "",
        f"**Method.** For each OOS row, the served-band PIT is $\\tau_\\text{{PIT}} = \\min\\{{\\tau : \\text{{mon\\_open}} \\in [L(\\tau), U(\\tau)]\\}}$. We find this by reusing the τ-sweep above and recording, for each row, the smallest τ at which the served band covers `mon_open`. Rows uncovered at the maximum τ (= 0.99) get $\\tau_\\text{{PIT}} = 1.0$.",
        "",
        f"**Result.** $n = {len(pit_df):,}$ PIT values; $n_\\text{{uncov}} = {n_uncov}$ ({n_uncov/len(pit_df)*100:.1f}%) rows uncovered at $\\tau \\le 0.99$. KS test against $U(0,1)$ (clipping uncovered to 0.999 to avoid trivial rejection from the point mass at 1.0):",
        "",
        f"- KS statistic: **{ks_stat:.4f}**",
        f"- KS p-value: **{ks_p:.4f}** → {'**not rejected**' if ks_p > 0.05 else '**rejected**'} at $\\alpha = 0.05$",
        "",
        ("Served-band PIT distribution is statistically consistent with uniform on $(0,1)$. The full-distribution calibration claim — not only the per-anchor claim — is empirically supported." if ks_p > 0.05 else
         "Served-band PIT distribution deviates from uniform; the served-band is calibrated at the four anchors but the full-distribution calibration claim does not hold. Disclose accordingly in §6 — the calibration claim is target-specific, not distribution-wide."),
        "",
        f"PIT histogram + inter-anchor calibration plot: `reports/figures/v1b_diag_pit_served.png`.",
        "",
        "## Use",
        "",
        "1. **Paper §6.4:** if D5 passes, add a one-sentence validation that consumer-target τ is honoured at *every* point on the deployed grid, not only at the four buffer anchors. If D6 passes, the calibration claim upgrades from per-anchor to full-distribution.",
        "2. **Methodology log §0:** record the inter-anchor max deviation and the served-band KS as additional empirical claims alongside the per-anchor Kupiec results.",
        "3. **§9.4 of paper:** if D5 reveals systematic inter-anchor mis-calibration, the schedule should be either densified or its interpolation function reconsidered (spline, isotonic). The current 4-anchor linear interpolation is a heuristic; D5 measures whether it's an *acceptable* heuristic.",
        "",
        "Raw artefacts: `reports/tables/v1b_diag_inter_anchor_tau.csv`, `reports/tables/v1b_diag_pit_served.csv`. Reproducible via `scripts/run_extended_diagnostics.py`.",
    ]
    out = REPORTS / "v1b_diagnostics_extended.md"
    out.write_text("\n".join(md))
    print()
    print(f"Wrote {out}")
    print(f"Wrote {_tables_dir() / 'v1b_diag_inter_anchor_tau.csv'}")
    print(f"Wrote {_tables_dir() / 'v1b_diag_pit_served.csv'}")
    print(f"Wrote {_figures_dir() / 'v1b_diag_pit_served.png'}")


if __name__ == "__main__":
    main()
