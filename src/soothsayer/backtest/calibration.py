"""
Bounds-table builder retained for archived v1 diagnostic scripts.

Under v2 (Mondrian split-conformal by regime, paper 1 §7.7), the calibration
surface S^f(s, r, q) and its inversion are no longer the serving primitive —
the deployed Oracle reads `data/processed/mondrian_artefact_v2.parquet` and
serves a band via per-regime conformal quantile + δ-shifted c(τ) bump. The
v1 calibration-surface API (`compute_calibration_surface`, `pooled_surface`,
`invert`) was removed in the M5 refactor. This module retains only
`build_bounds_table`, used by archived diagnostic scripts under
`scripts/v1_archive/` to materialise per-Friday bounds tables for legacy
ablations and historical reproductions.
"""

from __future__ import annotations

import pandas as pd


def build_bounds_table(
    panel: pd.DataFrame,
    bounds_by_coverage: dict[float, pd.DataFrame],
    forecaster: str,
) -> pd.DataFrame:
    """Flatten {coverage: DataFrame(lower, upper)} into a long-form bounds table.

    Output columns: symbol, fri_ts, mon_ts, regime_pub, claimed, lower, upper,
                    mon_open, fri_close, forecaster.
    """
    rows = []
    for cov, band in bounds_by_coverage.items():
        m = band["lower"].notna() & band["upper"].notna()
        sub = panel.loc[m, ["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]].copy()
        sub["claimed"] = float(cov)
        sub["lower"] = band.loc[m, "lower"].values
        sub["upper"] = band.loc[m, "upper"].values
        sub["forecaster"] = forecaster
        rows.append(sub)
    if not rows:
        return pd.DataFrame(
            columns=["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open",
                     "fri_close", "claimed", "lower", "upper", "forecaster"]
        )
    out = pd.concat(rows, ignore_index=True)
    out.attrs.clear()  # avoid non-JSON-serializable .attrs on parquet write
    return out
