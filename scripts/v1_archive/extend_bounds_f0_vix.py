"""Append F0_VIX bounds to the deployed v1b_bounds.parquet and refresh surfaces.

F0_VIX is the forward-curve-implied Gaussian baseline rung introduced in
Paper 1 §7.1 (the VIX-scaled equity baseline that a reviewer will ask for).
It shares the F0 forecaster shape with F0_stale; only the σ source differs
(VIX-implied 2-day vol instead of realised 20-day vol). Equity-only.

This script extends the existing bounds parquet without re-running the F1
calibration — the F0_stale and F1_emp_regime rows are left untouched, so
all §6 / §7.4 deployed numbers remain reproducible.

Outputs:
  data/processed/v1b_bounds.parquet      (in-place: adds F0_VIX rows)
  reports/tables/v1b_calibration_surface.csv
  reports/tables/v1b_calibration_surface_pooled.csv
"""

from __future__ import annotations

import pandas as pd

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import forecasters as fc
from soothsayer.config import DATA_PROCESSED, REPORTS

F0_VIX_NAME = "F0_VIX"


def _tables_dir():
    p = REPORTS / "tables"
    p.mkdir(parents=True, exist_ok=True)
    return p


def main() -> None:
    bounds_path = DATA_PROCESSED / "v1b_bounds.parquet"
    panel_path = DATA_PROCESSED / "v1b_panel.parquet"

    bounds = pd.read_parquet(bounds_path)
    panel = pd.read_parquet(panel_path)

    grid = tuple(sorted(float(c) for c in bounds["claimed"].unique()))
    print(f"Existing bounds: {len(bounds):,} rows, forecasters={sorted(bounds['forecaster'].unique())}")
    print(f"Claimed grid: {grid}")

    # Drop any prior F0_VIX rows so the script is idempotent
    bounds = bounds[bounds["forecaster"] != F0_VIX_NAME].reset_index(drop=True)

    forecast = fc.forecast_f0_vix(panel)
    f0_vix_bounds = fc.gaussian_bounds(forecast, grid)
    bounds_f0_vix = cal.build_bounds_table(panel, f0_vix_bounds, forecaster=F0_VIX_NAME)
    print(f"F0_VIX bounds: {len(bounds_f0_vix):,} rows ({bounds_f0_vix['symbol'].nunique()} symbols)")

    merged = pd.concat([bounds, bounds_f0_vix], ignore_index=True)
    merged.attrs.clear()
    merged.to_parquet(bounds_path)
    print(f"Wrote {bounds_path} ({len(merged):,} rows total)")

    surface = cal.compute_calibration_surface(merged)
    surface_pooled = cal.pooled_surface(merged)
    surface.to_csv(_tables_dir() / "v1b_calibration_surface.csv", index=False)
    surface_pooled.to_csv(_tables_dir() / "v1b_calibration_surface_pooled.csv", index=False)
    print(f"Wrote surface CSVs ({len(surface):,} rows per-symbol, {len(surface_pooled):,} pooled)")


if __name__ == "__main__":
    main()
