"""
M5 deployable Mondrian — δ-shift walk-forward sweep.

The base M5 walk-forward (`run_mondrian_walkforward_pit.py`) showed that
fitting c(τ) on tune-slice to hit target τ exactly produces test-slice
undercoverage of −0.7pp (τ=0.95) to −6.6pp (τ=0.68) under expanding-window
splits — the OOS test slice is more volatile than the tune slice, so c(τ)
fit-to-hit-τ exactly under-delivers on the more volatile tail end.

The fix: fit c(τ) to hit τ+δ(τ) on the tune slice, where δ(τ) is a scalar
margin per target chosen to hit τ on the test slice. δ becomes the
deployment artifact — 4 scalars total, same parameter budget as the
deployed Oracle's BUFFER_BY_TARGET.

This script sweeps δ ∈ {0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07} for each τ,
runs the 6-split walk-forward at each (τ, δ) cell, and reports cross-split
test-realised mean / std / Kupiec-margin so the user can pick δ(τ).

Output: reports/tables/v1b_mondrian_delta_sweep.csv
"""

from __future__ import annotations

from datetime import date
import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.config import DATA_PROCESSED, REPORTS

import sys
sys.path.insert(0, str((REPORTS / ".." / "scripts").resolve()))
from run_mondrian_walkforward_pit import walk_forward_m5, TARGETS, SPLIT_DATE


DELTA_GRID = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07)


def _kupiec(n: int, x: int, claimed: float) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p_obs = x / n; p_exp = 1.0 - claimed
    if p_obs in (0.0, 1.0):
        lr = 2.0 * n * (p_obs * np.log(max(p_obs, 1e-12) / max(p_exp, 1e-12))
                        + (1 - p_obs) * np.log(max(1 - p_obs, 1e-12) / max(1 - p_exp, 1e-12)))
    else:
        lr = 2.0 * (x * np.log(p_obs / p_exp) + (n - x) * np.log((1 - p_obs) / (1 - p_exp)))
    return float(lr), float(1.0 - chi2.cdf(lr, df=1))


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(subset=["mon_open", "fri_close", "regime_pub"]).reset_index(drop=True)
    panel["point_fa"] = panel["fri_close"].astype(float) * (1.0 + panel["factor_ret"].astype(float))
    panel_train = panel[panel["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    all_rows = []
    print(f"{'tau':>5} {'delta':>5} {'c_mean':>7} {'c_std':>6} {'cov_mean':>9} "
          f"{'cov_std':>8} {'def_mean_pp':>11} {'def_max_pp':>11} {'kup_p_mean':>10} {'hw_mean':>8}")
    print("-" * 100)
    for delta in DELTA_GRID:
        wf = walk_forward_m5(panel_train, panel_oos, point_col="point_fa", delta=float(delta))
        all_rows.append(wf)
        for tau, g in wf.groupby("target"):
            c_mean = float(g["bump_c"].mean()); c_std = float(g["bump_c"].std(ddof=1))
            cov_mean = float(g["test_realised"].mean()); cov_std = float(g["test_realised"].std(ddof=1))
            deficit_mean = (cov_mean - tau) * 100
            deficit_max = (g["test_realised"].min() - tau) * 100  # worst split
            # Avg per-split Kupiec p-value
            kup_ps = []
            for _, row in g.iterrows():
                n = int(row["n_test"]); x_in = int(round(row["test_realised"] * n))
                _, p = _kupiec(n, n - x_in, tau)  # x_in = inside count, violations = n - x_in
                kup_ps.append(p)
            kup_p_mean = float(np.nanmean(kup_ps))
            hw_mean = float(g["test_half_width_bps_mean"].mean())
            print(f"{tau:>5.2f} {delta:>5.3f} {c_mean:>7.3f} {c_std:>6.3f} {cov_mean:>9.4f} "
                  f"{cov_std:>8.4f} {deficit_mean:>+11.2f} {deficit_max:>+11.2f} {kup_p_mean:>10.3f} {hw_mean:>8.1f}")
        print()

    out = REPORTS / "tables"
    out.mkdir(parents=True, exist_ok=True)
    pd.concat(all_rows, ignore_index=True).to_csv(out / "v1b_mondrian_delta_sweep.csv", index=False)
    print(f"Wrote {out / 'v1b_mondrian_delta_sweep.csv'}")


if __name__ == "__main__":
    main()
