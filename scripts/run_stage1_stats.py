"""
Stage-1 statistics: serving-layer ablation (hybrid / buffer) + block-bootstrap
95% CIs on every pairwise effect size in the ablation ladder.

Reads per-row ablation outputs from scripts/run_ablation.py and simulates the
serving-time Oracle with toggled hybrid-regime and calibration-buffer knobs on
the held-out 2023+ slice.

Bootstrap units: unique weekends (fri_ts). Weekends are resampled with
replacement; all symbol-rows sharing a weekend are kept together, preserving
cross-sectional correlation. 1000 resamples → 2.5/97.5 quantiles for 95% CI.

Outputs:
  reports/tables/v1b_ablation_bootstrap.csv  pairwise deltas with 95% CI
  reports/tables/v1b_ablation_serving.csv    hybrid / buffer cell table
  reports/tables/v1b_ablation_serving_bootstrap.csv  OOS serving-layer deltas
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


RNG_SEED = 0xBEEF_C0FFEE
N_BOOT = 1000
SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.95, 0.99)


def _tables_dir() -> Path:
    p = REPORTS / "tables"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Block bootstrap on the A-ladder
# ---------------------------------------------------------------------------

def _metrics(df: pd.DataFrame) -> dict:
    """Pooled coverage + sharpness on a variant-filtered frame with columns:
    inside (0/1), half_width_bps, mon_open, lower, upper."""
    if len(df) == 0:
        return {"cov": np.nan, "sharp": np.nan, "n": 0}
    return {
        "cov": float(df["inside"].mean()),
        "sharp": float(df["half_width_bps"].mean()),
        "n": int(len(df)),
    }


def _bootstrap_deltas(rows: pd.DataFrame, variant_a: str, variant_b: str,
                      n_boot: int = N_BOOT, seed: int = RNG_SEED,
                      regime: str | None = None) -> dict:
    """Block bootstrap on weekend unit. Returns dict with point estimate +
    2.5/97.5 percentiles for (delta_cov, delta_sharp_bps, delta_sharp_pct).

    Positive delta = variant_b has higher coverage / wider bands than variant_a.
    """
    if regime is not None:
        rows = rows[rows["regime_pub"] == regime]
    ra = rows[rows["variant"] == variant_a].set_index(["symbol", "fri_ts"])
    rb = rows[rows["variant"] == variant_b].set_index(["symbol", "fri_ts"])
    # Align on common (symbol, fri_ts) so each pair is matched
    common = ra.index.intersection(rb.index)
    ra = ra.loc[common].reset_index()
    rb = rb.loc[common].reset_index()

    # Weekend (fri_ts) is the block unit
    weekends = pd.unique(ra["fri_ts"].values)
    rng = np.random.default_rng(seed)

    # Point estimates on full sample
    pt_cov_a = float(ra["inside"].mean())
    pt_cov_b = float(rb["inside"].mean())
    pt_sh_a = float(ra["half_width_bps"].mean())
    pt_sh_b = float(rb["half_width_bps"].mean())
    pt_dcov = pt_cov_b - pt_cov_a
    pt_dsh = pt_sh_b - pt_sh_a
    pt_dsh_pct = (pt_sh_b / pt_sh_a - 1.0) if pt_sh_a > 0 else np.nan

    # Precompute weekend-indexed groups for O(1) resample
    ra_by_wk = {w: grp for w, grp in ra.groupby("fri_ts")}
    rb_by_wk = {w: grp for w, grp in rb.groupby("fri_ts")}

    dcovs = np.empty(n_boot)
    dshs = np.empty(n_boot)
    dsh_pcts = np.empty(n_boot)

    n_wk = len(weekends)
    for i in range(n_boot):
        draw = rng.integers(0, n_wk, size=n_wk)
        sampled_wks = weekends[draw]
        a_frames = [ra_by_wk[w] for w in sampled_wks]
        b_frames = [rb_by_wk[w] for w in sampled_wks]
        a_cat = pd.concat(a_frames, ignore_index=True)
        b_cat = pd.concat(b_frames, ignore_index=True)
        cov_a = a_cat["inside"].mean()
        cov_b = b_cat["inside"].mean()
        sh_a = a_cat["half_width_bps"].mean()
        sh_b = b_cat["half_width_bps"].mean()
        dcovs[i] = cov_b - cov_a
        dshs[i] = sh_b - sh_a
        dsh_pcts[i] = (sh_b / sh_a - 1.0) if sh_a > 0 else np.nan

    return {
        "variant_a": variant_a,
        "variant_b": variant_b,
        "regime": regime or "pooled",
        "n_weekends": n_wk,
        "n_rows": int(len(ra)),
        "delta_cov": pt_dcov,
        "delta_cov_ci_lo": float(np.quantile(dcovs, 0.025)),
        "delta_cov_ci_hi": float(np.quantile(dcovs, 0.975)),
        "delta_sharp_bps": pt_dsh,
        "delta_sharp_bps_ci_lo": float(np.quantile(dshs, 0.025)),
        "delta_sharp_bps_ci_hi": float(np.quantile(dshs, 0.975)),
        "delta_sharp_pct": pt_dsh_pct,
        "delta_sharp_pct_ci_lo": float(np.nanquantile(dsh_pcts, 0.025)),
        "delta_sharp_pct_ci_hi": float(np.nanquantile(dsh_pcts, 0.975)),
    }


def run_a_ladder_bootstrap() -> pd.DataFrame:
    rows = pd.read_parquet(DATA_PROCESSED / "v1b_ablation_rows.parquet")
    # Pairs exercise one knob at a time along the ladder, plus one B0 comparison.
    pairs = [
        ("A0_f0_stale",      "A0_VIX_f0_vix"),      # swap σ source: 20d realised → VIX-implied
        ("A0_VIX_f0_vix",    "A1_f1_emp"),          # factor-adj + empirical Q on top of VIX-Gaussian
        ("A0_f0_stale",      "A1_f1_emp"),          # factor-adj point + empirical quantiles
        ("A1_f1_emp",        "A2_f1_emp_vol"),      # VIX-scaled residuals
        ("A2_f1_emp_vol",    "A3_f1_ll_vix"),       # log-log VIX regression
        ("A3_f1_ll_vix",     "A4_f1_ll_volidx"),    # per-symbol vol index
        ("A4_f1_ll_volidx",  "A5_f1_ll_vi_earn"),   # + earnings regressor
        ("A4_f1_ll_volidx",  "A6_f1_ll_vi_lw"),     # + long_weekend regressor
        ("A4_f1_ll_volidx",  "A7_f1_emp_regime"),   # + both regressors (full model)
        ("A7_f1_emp_regime", "B0_stale_pt_regime_ci"),  # strip factor-switchboard point
    ]
    regimes = [None, "normal", "long_weekend", "high_vol"]
    results = []
    for a, b in pairs:
        for rg in regimes:
            t0 = time.time()
            rec = _bootstrap_deltas(rows, a, b, regime=rg)
            results.append(rec)
            print(f"  {a} → {b} ({rg or 'pooled'}): "
                  f"Δcov={rec['delta_cov']:+.3f} [{rec['delta_cov_ci_lo']:+.3f}, {rec['delta_cov_ci_hi']:+.3f}]  "
                  f"Δsharp={rec['delta_sharp_pct']:+.1%} "
                  f"[{rec['delta_sharp_pct_ci_lo']:+.1%}, {rec['delta_sharp_pct_ci_hi']:+.1%}]  "
                  f"({time.time()-t0:.1f}s)", flush=True)
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Serving-layer ablation: hybrid × buffer on OOS 2023+
# ---------------------------------------------------------------------------

def _serve_oos(oracle_kwargs: dict, bounds_oos: pd.DataFrame, panel_oos: pd.DataFrame,
               train_surface: pd.DataFrame, train_pooled: pd.DataFrame,
               forecaster_override: str | None = None,
               buffer_override: float | None = None) -> pd.DataFrame:
    oracle = Oracle(bounds=bounds_oos, surface=train_surface, surface_pooled=train_pooled,
                    **oracle_kwargs)
    rows = []
    for _, row in panel_oos.iterrows():
        for t in TARGETS:
            try:
                pp = oracle.fair_value(row["symbol"], row["fri_ts"], target_coverage=t,
                                       forecaster_override=forecaster_override,
                                       buffer_override=buffer_override)
            except ValueError:
                continue
            inside = (row["mon_open"] >= pp.lower) and (row["mon_open"] <= pp.upper)
            rows.append({
                "symbol": row["symbol"],
                "fri_ts": row["fri_ts"],
                "regime_pub": row["regime_pub"],
                "target": t,
                "inside": int(inside),
                "half_width_bps": pp.half_width_bps,
                "claim_served": pp.claimed_coverage_served,
                "forecaster_used": pp.forecaster_used,
                "buffer_applied": pp.calibration_buffer_applied,
            })
    return pd.DataFrame(rows)


def _kupiec_per_target(served: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t, grp in served.groupby("target"):
        v = (~grp["inside"].astype(bool)).astype(int).values
        lr_uc, p_uc = met._lr_kupiec(v, t)
        lr_ind, p_ind = met._lr_christoffersen_independence(v)
        rows.append({
            "target": t, "n": len(grp),
            "realized": float(grp["inside"].mean()),
            "mean_half_width_bps": float(grp["half_width_bps"].mean()),
            "violations": int(v.sum()),
            "violation_rate": float(v.mean()),
            "lr_uc": lr_uc, "p_uc": p_uc,
            "lr_ind": lr_ind, "p_ind": p_ind,
        })
    return pd.DataFrame(rows)


def run_serving_ablation() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds["mon_ts"] = pd.to_datetime(bounds["mon_ts"]).dt.date

    panel_full = bounds[["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]].drop_duplicates(
        subset=["symbol", "fri_ts"]).reset_index(drop=True)
    panel_oos = panel_full[panel_full["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)

    train_surface = cal.compute_calibration_surface(bounds_train)
    train_pooled = cal.pooled_surface(bounds_train)
    print(f"OOS panel: {len(panel_oos):,} rows in {panel_oos['fri_ts'].nunique()} weekends", flush=True)

    # Five cells: (C0) raw F1, (C1) raw F0, (C2) hybrid no buffer,
    # (C3) F1 + buffer, (C4) full Oracle (hybrid + buffer).
    cells = [
        ("C0_raw_f1",        {"forecaster_override": "F1_emp_regime", "buffer_override": 0.0}),
        ("C1_raw_f0",        {"forecaster_override": "F0_stale",       "buffer_override": 0.0}),
        ("C2_hybrid_nobuf",  {"forecaster_override": None,             "buffer_override": 0.0}),
        ("C3_f1_buffered",   {"forecaster_override": "F1_emp_regime",  "buffer_override": 0.025}),
        ("C4_full_oracle",   {"forecaster_override": None,             "buffer_override": 0.025}),
    ]

    per_cell_served: dict[str, pd.DataFrame] = {}
    summary_rows = []
    for name, cfg in cells:
        t0 = time.time()
        served = _serve_oos({}, bounds_oos, panel_oos, train_surface, train_pooled,
                            forecaster_override=cfg["forecaster_override"],
                            buffer_override=cfg["buffer_override"])
        per_cell_served[name] = served
        k = _kupiec_per_target(served)
        k["cell"] = name
        summary_rows.append(k)
        print(f"[{name}] served {len(served):,} rows in {time.time()-t0:.1f}s; "
              f"95% realized = {served[served['target']==0.95]['inside'].mean():.3f}", flush=True)

    summary = pd.concat(summary_rows, ignore_index=True)[
        ["cell", "target", "n", "realized", "mean_half_width_bps",
         "violations", "violation_rate", "lr_uc", "p_uc", "lr_ind", "p_ind"]
    ]
    return summary, panel_oos, per_cell_served


def bootstrap_serving_deltas(per_cell: dict[str, pd.DataFrame], target: float = 0.95) -> pd.DataFrame:
    """Block-bootstrap 95% CIs on OOS coverage deltas between serving cells."""
    pairs = [
        ("C0_raw_f1",       "C2_hybrid_nobuf"),  # effect of hybrid
        ("C0_raw_f1",       "C3_f1_buffered"),   # effect of buffer (no hybrid)
        ("C2_hybrid_nobuf", "C4_full_oracle"),   # effect of buffer (with hybrid)
        ("C0_raw_f1",       "C4_full_oracle"),   # total effect
    ]
    rng = np.random.default_rng(RNG_SEED)
    results = []
    for a, b in pairs:
        sa = per_cell[a][per_cell[a]["target"] == target].copy()
        sb = per_cell[b][per_cell[b]["target"] == target].copy()
        sa = sa.set_index(["symbol", "fri_ts"])
        sb = sb.set_index(["symbol", "fri_ts"])
        common = sa.index.intersection(sb.index)
        sa = sa.loc[common].reset_index()
        sb = sb.loc[common].reset_index()
        weekends = pd.unique(sa["fri_ts"].values)
        n_wk = len(weekends)
        sa_by_wk = {w: grp for w, grp in sa.groupby("fri_ts")}
        sb_by_wk = {w: grp for w, grp in sb.groupby("fri_ts")}
        pt_dcov = sb["inside"].mean() - sa["inside"].mean()
        pt_dsh_pct = sb["half_width_bps"].mean() / sa["half_width_bps"].mean() - 1.0

        dcovs = np.empty(N_BOOT)
        dshs = np.empty(N_BOOT)
        for i in range(N_BOOT):
            draw = rng.integers(0, n_wk, size=n_wk)
            sampled = weekends[draw]
            a_cat = pd.concat([sa_by_wk[w] for w in sampled], ignore_index=True)
            b_cat = pd.concat([sb_by_wk[w] for w in sampled], ignore_index=True)
            dcovs[i] = b_cat["inside"].mean() - a_cat["inside"].mean()
            dshs[i] = b_cat["half_width_bps"].mean() / a_cat["half_width_bps"].mean() - 1.0
        results.append({
            "cell_a": a, "cell_b": b, "target": target,
            "n_weekends": n_wk, "n_rows": int(len(sa)),
            "delta_cov": float(pt_dcov),
            "delta_cov_ci_lo": float(np.quantile(dcovs, 0.025)),
            "delta_cov_ci_hi": float(np.quantile(dcovs, 0.975)),
            "delta_sharp_pct": float(pt_dsh_pct),
            "delta_sharp_pct_ci_lo": float(np.quantile(dshs, 0.025)),
            "delta_sharp_pct_ci_hi": float(np.quantile(dshs, 0.975)),
        })
        r = results[-1]
        print(f"  {a} → {b}: Δcov={r['delta_cov']:+.3f} "
              f"[{r['delta_cov_ci_lo']:+.3f}, {r['delta_cov_ci_hi']:+.3f}]  "
              f"Δsharp={r['delta_sharp_pct']:+.1%} "
              f"[{r['delta_sharp_pct_ci_lo']:+.1%}, {r['delta_sharp_pct_ci_hi']:+.1%}]", flush=True)
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 80)
    print("A-LADDER BOOTSTRAP — pairwise 95% CIs on coverage / sharpness deltas")
    print("=" * 80)
    boot = run_a_ladder_bootstrap()
    boot.to_csv(_tables_dir() / "v1b_ablation_bootstrap.csv", index=False)

    print()
    print("=" * 80)
    print("SERVING-LAYER ABLATION — hybrid × buffer on OOS 2023+")
    print("=" * 80)
    serving_summary, panel_oos, per_cell = run_serving_ablation()
    serving_summary.to_csv(_tables_dir() / "v1b_ablation_serving.csv", index=False)
    print()
    print(serving_summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print()
    print("=" * 80)
    print("SERVING-LAYER BOOTSTRAP (95% target)")
    print("=" * 80)
    serving_boot = bootstrap_serving_deltas(per_cell, target=0.95)
    serving_boot.to_csv(_tables_dir() / "v1b_ablation_serving_bootstrap.csv", index=False)

    print()
    print("Wrote:")
    print(f"  {_tables_dir() / 'v1b_ablation_bootstrap.csv'}")
    print(f"  {_tables_dir() / 'v1b_ablation_serving.csv'}")
    print(f"  {_tables_dir() / 'v1b_ablation_serving_bootstrap.csv'}")


if __name__ == "__main__":
    main()
