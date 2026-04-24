"""
Build the empirical calibration surface from backtest output.

The calibration surface is the product's trust primitive: for each (symbol,
regime_pub, claimed_coverage) bucket, we publish the empirically-realized
coverage rate over a rolling historical window. Consumers who want a target
realized coverage level (e.g. 'I want a 95% CI that really is 95%') look up
which claimed quantile delivers it and receive that specific band.

No forecasting happens here. This module only consumes:
  - a fine-grid bounds table (claimed → lower/upper, per row)
  - the realised Monday opens from the panel
and emits a DataFrame of (symbol, regime, claimed, realized, n_obs) rows.

The inverse mapping (target_realized → claimed) is done by interpolation at
serve time — see `oracle.py`.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


DEFAULT_CLAIMED_GRID: tuple[float, ...] = (
    0.50, 0.60, 0.68, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95, 0.975, 0.99, 0.995
)


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


def compute_calibration_surface(bounds: pd.DataFrame) -> pd.DataFrame:
    """For each (symbol, regime_pub, forecaster, claimed) bucket, compute realized coverage.

    Output columns: symbol, regime_pub, forecaster, claimed, realized, n_obs, mean_half_width_bps.
    `realized` is the fraction of rows where mon_open ∈ [lower, upper].

    If `forecaster` is not in the bounds frame (single-forecaster backwards
    compat), the grouping falls back to (symbol, regime_pub, claimed).
    """
    base_cols = ["symbol", "regime_pub", "claimed", "realized", "n_obs", "mean_half_width_bps"]
    if bounds.empty:
        cols = (["forecaster"] + base_cols) if "forecaster" in bounds.columns else base_cols
        return pd.DataFrame(columns=cols)
    b = bounds.copy()
    b["inside"] = (b["mon_open"] >= b["lower"]) & (b["mon_open"] <= b["upper"])
    b["half_width_bps"] = (b["upper"] - b["lower"]) / 2 / b["fri_close"] * 1e4

    group_cols = ["symbol", "regime_pub", "claimed"]
    if "forecaster" in b.columns:
        group_cols.append("forecaster")

    grp = b.groupby(group_cols, observed=True)
    surface = grp.agg(
        realized=("inside", "mean"),
        n_obs=("inside", "count"),
        mean_half_width_bps=("half_width_bps", "mean"),
    ).reset_index()
    return surface.sort_values(group_cols).reset_index(drop=True)


def pooled_surface(bounds: pd.DataFrame, by: Iterable[str] = ("regime_pub", "forecaster", "claimed")) -> pd.DataFrame:
    """Same schema as compute_calibration_surface but pooled across symbols.

    Fallback for consumers querying a symbol with sparse data — a regime's
    pooled calibration is more stable than any single symbol's. `by` defaults
    to (regime_pub, forecaster, claimed) so the pooled surface retains the
    forecaster dimension needed for hybrid regime selection."""
    if bounds.empty:
        return pd.DataFrame()
    b = bounds.copy()
    b["inside"] = (b["mon_open"] >= b["lower"]) & (b["mon_open"] <= b["upper"])
    b["half_width_bps"] = (b["upper"] - b["lower"]) / 2 / b["fri_close"] * 1e4
    by_list = [c for c in by if c != "forecaster" or "forecaster" in b.columns]
    grp = b.groupby(by_list, observed=True)
    surface = grp.agg(
        realized=("inside", "mean"),
        n_obs=("inside", "count"),
        mean_half_width_bps=("half_width_bps", "mean"),
    ).reset_index()
    surface["symbol"] = "__pooled__"
    return surface.sort_values(by_list).reset_index(drop=True)


def invert(
    surface: pd.DataFrame,
    symbol: str,
    regime: str,
    target_realized: float,
    min_obs: int = 30,
    forecaster: str | None = None,
) -> tuple[float, dict]:
    """Find the `claimed` quantile whose historical realized coverage equals
    `target_realized` for (symbol, regime[, forecaster]). Linear-interpolates
    between grid points.

    If `forecaster` is supplied and the surface has a `forecaster` column,
    the search is restricted to that forecaster's rows — the hybrid regime-
    selection path uses this to serve F0_stale in high_vol and F1_emp_regime
    in normal/long_weekend.

    Returns (claimed_quantile, diagnostics). `claimed_quantile` may be outside
    the fitted grid — callers should clip to what their bounds table supplies.
    If the (symbol, regime) bucket has fewer than `min_obs` observations at
    any claimed level, diagnostics['fallback'] = 'pooled' signals the caller
    should query the pooled surface instead.
    """
    sym_df = surface[(surface["symbol"] == symbol) & (surface["regime_pub"] == regime)]
    if forecaster is not None and "forecaster" in surface.columns:
        sym_df = sym_df[sym_df["forecaster"] == forecaster]
    if sym_df.empty or sym_df["n_obs"].max() < min_obs:
        return (target_realized, {"fallback": "pooled", "symbol_n": int(sym_df["n_obs"].max() if not sym_df.empty else 0)})

    # Sort by realized to interpolate claimed from realized
    s = sym_df.sort_values("realized").reset_index(drop=True)
    realized = s["realized"].values
    claimed = s["claimed"].values

    if target_realized <= realized.min():
        return (float(claimed[0]), {"clipped": "below", "realized_min": float(realized.min())})
    if target_realized >= realized.max():
        return (float(claimed[-1]), {"clipped": "above", "realized_max": float(realized.max())})

    # Find bracketing indices
    for i in range(len(realized) - 1):
        if realized[i] <= target_realized <= realized[i + 1]:
            r0, r1 = realized[i], realized[i + 1]
            c0, c1 = claimed[i], claimed[i + 1]
            if r1 == r0:
                return (float(c0), {"exact_tie": True})
            frac = (target_realized - r0) / (r1 - r0)
            interp_claimed = c0 + frac * (c1 - c0)
            return (float(interp_claimed), {"bracketed": (float(c0), float(c1))})
    return (float(claimed[-1]), {"fallback": "edge"})
