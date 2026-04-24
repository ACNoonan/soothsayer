"""
Soothsayer Oracle — serving-time API.

Consumers call `Oracle.fair_value(symbol, as_of, target_coverage)` and receive
a principled price band: a point estimate and lower/upper bounds whose
empirical coverage matches the target. The calibration surface driving the
inversion is produced by the backtest (see `backtest/calibration.py`) and
persisted to `data/processed/v1b_bounds.parquet`.

**Hybrid regime forecaster (2026-04-24).** The Oracle consults
`REGIME_FORECASTER` to decide which forecaster's calibration surface to
invert against for a given regime. v1b evidence at matched realized coverage:

  normal regime       (65% of weekends) → F1_emp_regime  (27% tighter than F0)
  long_weekend regime (10%)             → F1_emp_regime  (43% tighter)
  high_vol regime     (24%)             → F0_stale       (~10% tighter; F1 stretches)

The `forecaster_used` field on the PricePoint is the receipt for which
forecaster's band the consumer received.

Two modes:
  historical mode (used by the smoke test and demo): `as_of` must match a
    Friday present in the backtest panel; bounds are looked up directly.
  live mode (for production): not yet implemented — would fetch current
    Friday data and run the model online. Out of scope for Phase 0.

The explicit product promise: the `claimed_coverage_served` field tells the
consumer exactly which quantile level was used to deliver their
`target_coverage` — an honest calibration receipt, not a guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .backtest import calibration as cal
from .config import DATA_PROCESSED, REPORTS


BOUNDS_PATH = DATA_PROCESSED / "v1b_bounds.parquet"
SURFACE_PATH = REPORTS / "tables" / "v1b_calibration_surface.csv"
SURFACE_POOLED_PATH = REPORTS / "tables" / "v1b_calibration_surface_pooled.csv"


# Per-regime forecaster selection. Evidence-driven per v1b: F1_emp_regime
# is calibration-surface-tighter than F0 on normal and long_weekend, but F0
# is tighter in high_vol (F1 stretches to cover, F0's already-wide Gaussian
# is efficient there). See reports/v1b_decision.md.
REGIME_FORECASTER: dict[str, str] = {
    "normal": "F1_emp_regime",
    "long_weekend": "F1_emp_regime",
    "high_vol": "F0_stale",
}
DEFAULT_FORECASTER = "F1_emp_regime"


# Empirical calibration buffer. The v1b hybrid OOS validation (see
# reports/v1b_hybrid_validation.md) found a ~3pp undercoverage gap: a consumer
# asking for target=0.95 received realized=0.92 on held-out post-2023 data.
# The gap is a calibration-surface aging effect: the surface fits the period
# it was trained on tighter than future periods. Until split-conformal
# prediction lands in Phase 2 (see 08 - Project Plan.md), we close the gap
# with a simple empirical buffer: add `CALIBRATION_BUFFER_PCT` to the target
# before inversion. Disclosed in every PricePoint via `calibration_buffer_applied`.
#
# The default 0.025 is the median of measured OOS gaps across target levels
# (0.035 at 0.68, 0.030 at 0.95, 0.019 at 0.99). A production deployment would
# rebuild this buffer from a rolling OOS backtest on each surface rebuild.
CALIBRATION_BUFFER_PCT: float = 0.025
MAX_SERVED_TARGET: float = 0.995  # top of the fine grid; can't buffer past this


@dataclass(frozen=True)
class PricePoint:
    """The Soothsayer oracle read. Stable fields are what protocols integrate
    against; `diagnostics` is human-consumable metadata."""
    symbol: str
    as_of: date
    target_coverage: float       # what the consumer asked for
    calibration_buffer_applied: float  # OOS buffer added to target before inversion
    claimed_coverage_served: float  # which claimed quantile we actually used
    point: float
    lower: float
    upper: float
    regime: str
    forecaster_used: str         # which forecaster's band we served (hybrid receipt)
    sharpness_bps: float
    diagnostics: dict = field(default_factory=dict)

    @property
    def half_width_bps(self) -> float:
        if self.point == 0:
            return 0.0
        return (self.upper - self.lower) / 2 / self.point * 1e4

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of": str(self.as_of),
            "target_coverage": self.target_coverage,
            "calibration_buffer_applied": self.calibration_buffer_applied,
            "claimed_coverage_served": self.claimed_coverage_served,
            "point": self.point,
            "lower": self.lower,
            "upper": self.upper,
            "regime": self.regime,
            "forecaster_used": self.forecaster_used,
            "sharpness_bps": self.sharpness_bps,
            "half_width_bps": self.half_width_bps,
            "diagnostics": self.diagnostics,
        }


class Oracle:
    """Serving-time Oracle with per-regime forecaster selection."""

    def __init__(
        self,
        bounds: pd.DataFrame,
        surface: pd.DataFrame,
        surface_pooled: pd.DataFrame,
        regime_forecaster: dict[str, str] | None = None,
        calibration_buffer_pct: float = CALIBRATION_BUFFER_PCT,
    ):
        self._bounds = bounds
        self._surface = surface
        self._surface_pooled = surface_pooled
        self._regime_forecaster = regime_forecaster or REGIME_FORECASTER
        self._buffer_pct = float(calibration_buffer_pct)

    @classmethod
    def load(
        cls,
        bounds_path: Path | str = BOUNDS_PATH,
        surface_path: Path | str = SURFACE_PATH,
        surface_pooled_path: Path | str = SURFACE_POOLED_PATH,
        regime_forecaster: dict[str, str] | None = None,
        calibration_buffer_pct: float = CALIBRATION_BUFFER_PCT,
    ) -> "Oracle":
        bounds = pd.read_parquet(bounds_path)
        surface = pd.read_csv(surface_path)
        surface_pooled = pd.read_csv(surface_pooled_path)
        return cls(
            bounds=bounds,
            surface=surface,
            surface_pooled=surface_pooled,
            regime_forecaster=regime_forecaster,
            calibration_buffer_pct=calibration_buffer_pct,
        )

    def list_available(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """Fridays for which historical-mode serving is possible."""
        b = self._bounds[["symbol", "fri_ts", "regime_pub"]].drop_duplicates()
        if symbol is not None:
            b = b[b["symbol"] == symbol]
        return b.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)

    def _pick_forecaster(self, regime: str) -> str:
        return self._regime_forecaster.get(regime, DEFAULT_FORECASTER)

    def _invert_to_claimed(
        self, symbol: str, regime: str, target_coverage: float, forecaster: str,
    ) -> tuple[float, dict]:
        # Try per-symbol surface first, restricted to the chosen forecaster
        claimed_sym, diag_sym = cal.invert(
            self._surface, symbol, regime, target_coverage, forecaster=forecaster,
        )
        if diag_sym.get("fallback") != "pooled":
            return claimed_sym, {"calibration": "per_symbol", **diag_sym}
        # Fallback to pooled
        claimed_p, diag_p = cal.invert(
            self._surface_pooled, "__pooled__", regime, target_coverage,
            forecaster=forecaster,
        )
        return claimed_p, {"calibration": "pooled", **diag_p}

    def fair_value(
        self,
        symbol: str,
        as_of: date | str,
        target_coverage: float = 0.95,
        forecaster_override: str | None = None,
        buffer_override: float | None = None,
    ) -> PricePoint:
        """Serve a calibrated price band.

        `forecaster_override` forces a specific forecaster ("F1_emp_regime" or
        "F0_stale" etc.) regardless of regime — useful for A/B diagnostics.
        When None (default), uses the per-regime selection from
        `REGIME_FORECASTER`.

        `buffer_override` overrides the empirical calibration buffer (the OOS
        gap correction, default `CALIBRATION_BUFFER_PCT`). Pass 0.0 to disable
        entirely for diagnostics against the raw surface inversion.
        """
        if isinstance(as_of, str):
            as_of = pd.to_datetime(as_of).date()

        # Look up every forecaster's rows at this (symbol, fri_ts)
        rows = self._bounds[
            (self._bounds["symbol"] == symbol) & (self._bounds["fri_ts"] == as_of)
        ]
        if rows.empty:
            raise ValueError(
                f"No bounds available for symbol={symbol} as_of={as_of}. "
                "Call list_available() to see what's supported."
            )

        regime = str(rows["regime_pub"].iloc[0])
        fri_close = float(rows["fri_close"].iloc[0])

        forecaster_used = forecaster_override or self._pick_forecaster(regime)
        forecaster_rows = rows[rows["forecaster"] == forecaster_used] if "forecaster" in rows.columns else rows
        if forecaster_rows.empty:
            forecaster_used = rows["forecaster"].iloc[0] if "forecaster" in rows.columns else DEFAULT_FORECASTER
            forecaster_rows = rows[rows["forecaster"] == forecaster_used] if "forecaster" in rows.columns else rows

        # Apply empirical calibration buffer to target before inversion.
        # Rationale: OOS realized coverage runs ~3pp below naive target; bumping
        # the target up by the measured buffer recovers calibration on the
        # held-out slice. See reports/v1b_hybrid_validation.md.
        buffer_pct = float(buffer_override) if buffer_override is not None else self._buffer_pct
        effective_target = min(target_coverage + buffer_pct, MAX_SERVED_TARGET)

        # Invert calibration using the chosen forecaster's surface, at the
        # buffered target.
        claimed_served, diag_inv = self._invert_to_claimed(
            symbol, regime, effective_target, forecaster_used,
        )

        grid = sorted(forecaster_rows["claimed"].unique())
        nearest_claimed = min(grid, key=lambda c: abs(c - claimed_served))
        chosen = forecaster_rows[forecaster_rows["claimed"] == nearest_claimed].iloc[0]

        lower = float(chosen["lower"])
        upper = float(chosen["upper"])
        point = (lower + upper) / 2.0
        sharpness_bps = (upper - lower) / 2 / fri_close * 1e4

        return PricePoint(
            symbol=symbol,
            as_of=as_of,
            target_coverage=target_coverage,
            calibration_buffer_applied=buffer_pct,
            claimed_coverage_served=float(nearest_claimed),
            point=point,
            lower=lower,
            upper=upper,
            regime=regime,
            forecaster_used=forecaster_used,
            sharpness_bps=sharpness_bps,
            diagnostics={
                "fri_close": fri_close,
                "nearest_grid": nearest_claimed,
                "buffered_target": effective_target,
                "requested_claimed_pre_clip": claimed_served,
                "regime_forecaster_policy": self._regime_forecaster,
                **diag_inv,
            },
        )
