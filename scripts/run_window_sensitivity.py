"""
Window-size sensitivity sweep for F1_emp_regime.

Question. The deployed log-log residual model uses a rolling 156-weekend
(≈ 3-year) window. Why 156? It was the value carried over from initial
methodology with no optimization sweep. A reviewer can reasonably ask: is
156 the elbow of a U-curve, or arbitrary?

Method. For each window in {52, 78, 104, 156, 208, 260, 312} weekends:
  1. Recompute F1_emp_regime bounds at the deployed 14-level claimed grid
     (only the rolling-window arg changes; everything else identical).
  2. F0_stale bounds are window-independent — recomputed once.
  3. Build the calibration surface on pre-2023 bounds + serve OOS 2023+
     using the deployed `BUFFER_BY_TARGET` schedule. This tests whether
     the deployed schedule is robust to a window change, not the
     window's intrinsic best achievable.
  4. Compute pooled realised coverage, mean half-width, Kupiec p_uc at
     τ ∈ {0.68, 0.85, 0.95}.

A "window-robust" methodology has flat realised coverage and gracefully
varying sharpness across windows. A window-fragile methodology has either
coverage degradation (bad — needs tuning per window) or large sharpness
swings (less bad but disclosed).

Outputs:
  reports/tables/v1b_window_sensitivity.csv
  reports/v1b_window_sensitivity.md
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import forecasters as fc
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


WINDOWS: tuple[int, ...] = (52, 78, 104, 156, 208, 260, 312)
EXTENDED_GRID: tuple[float, ...] = (
    0.50, 0.60, 0.68, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95, 0.975, 0.99, 0.995, 0.997, 0.999,
)
SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95)


def _tables_dir() -> Path:
    p = REPORTS / "tables"; p.mkdir(parents=True, exist_ok=True); return p


def _serve_oos(bounds_oos, panel_oos, surface, surface_pooled, target):
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)
    rows = []
    for _, w in panel_oos.iterrows():
        try:
            pp = oracle.fair_value(w["symbol"], w["fri_ts"], target_coverage=target)
        except ValueError:
            continue
        inside = (w["mon_open"] >= pp.lower) and (w["mon_open"] <= pp.upper)
        rows.append({
            "symbol": w["symbol"], "fri_ts": w["fri_ts"], "regime_pub": w["regime_pub"],
            "inside": int(inside), "half_width_bps": float(pp.half_width_bps),
            "buffer_applied": float(pp.calibration_buffer_applied),
        })
    return pd.DataFrame(rows)


def _stats(served, target):
    n = int(len(served))
    if n == 0:
        return {"n": 0, "realized": float("nan"), "mean_half_width_bps": float("nan"),
                "p_uc": float("nan"), "p_ind": float("nan")}
    realized = float(served["inside"].mean())
    hw = float(served["half_width_bps"].mean())
    v = (~served["inside"].astype(bool)).astype(int).values
    _, p_uc = met._lr_kupiec(v, target)
    lr_ind_total, n_groups = 0.0, 0
    for sym, g in served.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
        lr_ind, _ = met._lr_christoffersen_independence(
            (~g["inside"].astype(bool)).astype(int).values)
        if not np.isnan(lr_ind):
            lr_ind_total += lr_ind
            n_groups += 1
    p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
    return {"n": n, "realized": realized, "mean_half_width_bps": hw,
            "p_uc": float(p_uc), "p_ind": p_ind}


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    if "is_long_weekend" not in panel.columns:
        panel["is_long_weekend"] = (panel["gap_days"] >= 4).astype(float)
    if "earnings_next_week_f" not in panel.columns:
        panel["earnings_next_week_f"] = panel["earnings_next_week"].astype(float)
    print(f"Panel: {len(panel):,} rows; sweeping windows {WINDOWS}", flush=True)

    # F0_stale is window-independent — compute once
    print("\nComputing F0_stale (window-independent)...", flush=True)
    f0_forecast = fc.forecast_f0(panel)
    f0_bounds_dict = fc.gaussian_bounds(f0_forecast, coverage_levels=EXTENDED_GRID)
    bt_f0 = cal.build_bounds_table(panel, f0_bounds_dict, forecaster="F0_stale")

    rows = []
    sweep_start = time.time()
    for window in WINDOWS:
        t0 = time.time()
        print(f"\n=== window={window} ===", flush=True)
        f1_bounds, _ = fc.empirical_quantiles_f1_loglog(
            panel,
            coverage_levels=EXTENDED_GRID,
            window=window,
            vol_col="vol_idx_fri_close",
            extra_regressors=("earnings_next_week_f", "is_long_weekend"),
        )
        bt_f1 = cal.build_bounds_table(panel, f1_bounds, forecaster="F1_emp_regime")
        bt = pd.concat([bt_f1, bt_f0], ignore_index=True)
        bt.attrs.clear()

        bt["fri_ts"] = pd.to_datetime(bt["fri_ts"]).dt.date
        bt["mon_ts"] = pd.to_datetime(bt["mon_ts"]).dt.date
        train = bt[bt["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
        test = bt[bt["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
        panel_oos = bt[bt["fri_ts"] >= SPLIT_DATE][
            ["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]
        ].drop_duplicates(["symbol", "fri_ts"]).reset_index(drop=True)

        surface = cal.compute_calibration_surface(train)
        pooled = cal.pooled_surface(train)

        for target in TARGETS:
            served = _serve_oos(test, panel_oos, surface, pooled, target)
            s = _stats(served, target)
            row = {"window": window, "target": target, **s,
                   "buffer_applied": float(served["buffer_applied"].iloc[0]) if not served.empty else float("nan")}
            rows.append(row)
            print(f"  τ={target:.2f}: n={s['n']:,}  realized={s['realized']:.3f}  "
                  f"hw={s['mean_half_width_bps']:.0f}bps  p_uc={s['p_uc']:.3f}  p_ind={s['p_ind']:.3f}",
                  flush=True)
        print(f"  window total time: {time.time()-t0:.1f}s", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(_tables_dir() / "v1b_window_sensitivity.csv", index=False)

    # Diff against deployed window=156
    print()
    print("=" * 80)
    print("WINDOW SENSITIVITY — pivoted")
    print("=" * 80)
    for t in TARGETS:
        sub = df[df["target"] == t].sort_values("window").reset_index(drop=True)
        baseline = sub[sub["window"] == 156].iloc[0]
        sub["Δ_realized_vs_156"] = sub["realized"] - baseline["realized"]
        sub["Δ_hw_pct_vs_156"] = (sub["mean_half_width_bps"] - baseline["mean_half_width_bps"]) / baseline["mean_half_width_bps"] * 100
        print(f"\n--- τ={t:.2f} ---")
        print(sub[["window", "n", "realized", "mean_half_width_bps", "p_uc",
                   "Δ_realized_vs_156", "Δ_hw_pct_vs_156"]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # Best-window analysis
    print()
    print("=" * 80)
    print("BEST WINDOW PER τ")
    print("=" * 80)
    for t in TARGETS:
        sub = df[df["target"] == t]
        # Best = smallest |realized - target| with a tiebreaker on sharpness
        sub = sub.copy()
        sub["abs_dev"] = (sub["realized"] - t).abs()
        ranked = sub.sort_values(["abs_dev", "mean_half_width_bps"]).reset_index(drop=True)
        best = ranked.iloc[0]
        deployed = sub[sub["window"] == 156].iloc[0]
        print(f"\nτ={t:.2f}: best window = {int(best['window'])} (realized={best['realized']:.3f}, "
              f"hw={best['mean_half_width_bps']:.0f}bps)")
        print(f"         deployed window = 156 (realized={deployed['realized']:.3f}, "
              f"hw={deployed['mean_half_width_bps']:.0f}bps)")

    elapsed = time.time() - sweep_start
    print(f"\nSweep total: {elapsed:.1f}s")

    # Writeup
    md = [
        "# V1b — Window-size sensitivity",
        "",
        f"**Question.** The deployed log-log residual model uses a rolling 156-weekend (≈ 3-year) window. Is 156 on a sensitivity elbow, or arbitrary? A reviewer can reasonably ask whether the choice was optimized.",
        "",
        f"**Method.** For each window $\\in \\{{{', '.join(map(str, WINDOWS))}\\}}$, recompute F1_emp_regime bounds at the deployed claimed grid; F0_stale bounds are window-independent (recomputed once). Build the calibration surface on pre-2023 bounds + serve OOS 2023+ using the deployed `BUFFER_BY_TARGET` schedule. Compute pooled realised coverage, mean half-width, Kupiec $p_{{uc}}$ at τ ∈ {{0.68, 0.85, 0.95}}.",
        "",
        "## Results",
        "",
    ]
    for t in TARGETS:
        sub = df[df["target"] == t].sort_values("window").reset_index(drop=True)
        baseline = sub[sub["window"] == 156].iloc[0]
        sub["Δ_realized_vs_156"] = sub["realized"] - baseline["realized"]
        sub["Δ_hw_pct_vs_156"] = (sub["mean_half_width_bps"] - baseline["mean_half_width_bps"]) / baseline["mean_half_width_bps"] * 100
        md.append(f"### τ = {t:.2f}")
        md.append("")
        md.append(sub[["window", "n", "realized", "mean_half_width_bps", "p_uc",
                       "Δ_realized_vs_156", "Δ_hw_pct_vs_156"]].to_markdown(index=False, floatfmt=".3f"))
        md.append("")

    md.extend([
        "## Reading",
        "",
        "**Window-robustness** is the property we want — realised coverage flat across windows, sharpness varies gracefully. Specifically:",
        "",
        "- A flat realised-coverage column across windows means the deployed `BUFFER_BY_TARGET` schedule (tuned at window=156) generalises — the methodology doesn't degrade if you happened to pick a slightly different window.",
        "- A monotonic sharpness curve (narrower bands as window grows, then plateaus) is the expected shape under the bias–variance tradeoff: small windows are noisy; large windows over-smooth.",
        "- A U-shape in coverage (best at window=156) would suggest 156 was lucky, not robust.",
        "",
        "**For the paper:** if the table shows realised coverage Δ ≤ 1pp across windows in [104, 260], cite this as window-robustness in §9 and disclose 156 as a defensible choice within a stable region. If a different window dominates on both coverage and sharpness, retune deployment.",
        "",
        "Raw artefacts: `reports/tables/v1b_window_sensitivity.csv`. Reproducible via `scripts/run_window_sensitivity.py`.",
    ])
    out = REPORTS / "v1b_window_sensitivity.md"
    out.write_text("\n".join(md))
    print(f"\nWrote {out}")
    print(f"Wrote {_tables_dir() / 'v1b_window_sensitivity.csv'}")


if __name__ == "__main__":
    main()
