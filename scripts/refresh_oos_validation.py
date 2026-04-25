"""
Refresh the OOS-validation tables under the deployed BUFFER_BY_TARGET schedule.

The headline §6.4 numbers in the paper draft were computed under a scalar
0.025 buffer. After the per-target tuning landed (`reports/v1b_buffer_tune.md`),
those numbers are slightly stale at τ=0.95 (buffer is now 0.020) and at τ=0.85
(buffer is now 0.045 — wasn't reported at all before).

This script re-serves the OOS panel with the deployed Oracle (no buffer
override → uses BUFFER_BY_TARGET) and produces a fresh per-(τ, regime) table
for §6.4 plus pooled Kupiec/Christoffersen for the headline.

Outputs:
  reports/tables/v1b_oos_validation_pertarget.csv  per-(τ, regime) coverage + half-width
  reports/tables/v1b_oos_kupiec_pertarget.csv      pooled Kupiec/Christoffersen at each τ
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95, 0.99)


def main() -> None:
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds["mon_ts"] = pd.to_datetime(bounds["mon_ts"]).dt.date

    panel = bounds[["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]].drop_duplicates(
        ["symbol", "fri_ts"]
    ).reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)

    surface = cal.compute_calibration_surface(bounds_train)
    surface_pooled = cal.pooled_surface(bounds_train)

    # Default Oracle pulls BUFFER_BY_TARGET via buffer_for_target() at serve time.
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)
    print(f"OOS panel: {len(panel_oos):,} rows in {panel_oos['fri_ts'].nunique()} weekends",
          flush=True)

    rows = []
    for _, w in panel_oos.iterrows():
        for t in TARGETS:
            try:
                pp = oracle.fair_value(w["symbol"], w["fri_ts"], target_coverage=t)
            except ValueError:
                continue
            inside = (w["mon_open"] >= pp.lower) and (w["mon_open"] <= pp.upper)
            rows.append({
                "symbol": w["symbol"], "fri_ts": w["fri_ts"], "regime_pub": w["regime_pub"],
                "target": t, "inside": int(inside),
                "half_width_bps": pp.half_width_bps,
                "buffer_applied": pp.calibration_buffer_applied,
            })
    served = pd.DataFrame(rows)

    # Per-(target, regime) summary
    per_regime = served.groupby(["target", "regime_pub"], observed=True).agg(
        n=("inside", "count"),
        realized=("inside", "mean"),
        mean_half_width_bps=("half_width_bps", "mean"),
        buffer=("buffer_applied", "first"),
    ).reset_index()
    pooled = served.groupby("target", observed=True).agg(
        n=("inside", "count"),
        realized=("inside", "mean"),
        mean_half_width_bps=("half_width_bps", "mean"),
        buffer=("buffer_applied", "first"),
    ).reset_index()
    pooled["regime_pub"] = "pooled"
    per_regime = pd.concat([per_regime, pooled], ignore_index=True)
    per_regime = per_regime.sort_values(["target", "regime_pub"]).reset_index(drop=True)

    # Kupiec + Christoffersen pooled per target
    kr_rows = []
    for t in TARGETS:
        sub = served[served["target"] == t].sort_values(["symbol", "fri_ts"])
        v = (~sub["inside"].astype(bool)).astype(int).values
        lr_uc, p_uc = met._lr_kupiec(v, t)
        lr_ind_total, n_groups = 0.0, 0
        for sym, g in sub.groupby("symbol"):
            lr_ind, _ = met._lr_christoffersen_independence(
                (~g["inside"].astype(bool)).astype(int).values
            )
            if not np.isnan(lr_ind):
                lr_ind_total += lr_ind
                n_groups += 1
        p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
        kr_rows.append({
            "target": t, "n": int(len(sub)),
            "realized": float(sub["inside"].mean()),
            "violations": int(v.sum()),
            "violation_rate": float(v.mean()),
            "lr_uc": float(lr_uc), "p_uc": float(p_uc),
            "lr_ind": float(lr_ind_total), "p_ind": p_ind,
        })
    kupiec = pd.DataFrame(kr_rows)

    out_dir = REPORTS / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    per_regime.to_csv(out_dir / "v1b_oos_validation_pertarget.csv", index=False)
    kupiec.to_csv(out_dir / "v1b_oos_kupiec_pertarget.csv", index=False)

    print()
    print("Per-(target, regime) under deployed BUFFER_BY_TARGET")
    print("=" * 80)
    print(per_regime.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print("Pooled Kupiec / Christoffersen")
    print("=" * 80)
    print(kupiec.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print(f"Wrote {out_dir / 'v1b_oos_validation_pertarget.csv'}")
    print(f"Wrote {out_dir / 'v1b_oos_kupiec_pertarget.csv'}")


if __name__ == "__main__":
    main()
