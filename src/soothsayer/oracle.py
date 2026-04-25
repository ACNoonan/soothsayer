"""
Soothsayer Oracle — serving-time API.

Consumers call `Oracle.fair_value(symbol, as_of, target_coverage)` and receive
a principled price band: a point estimate and lower/upper bounds whose
empirical coverage matches the target. The calibration surface driving the
inversion is produced by the backtest (see `backtest/calibration.py`) and
persisted to `data/processed/v1b_bounds.parquet`.

**Default target_coverage = 0.85 (2026-04-25).** The shipping default moved
from 0.95 to 0.85 after the OOS protocol-comparison bootstrap
(`reports/tables/protocol_compare_*.csv`) showed t=0.85 yields a statistically
significant expected-loss improvement vs a Kamino-style flat ±300bps band on
the held-out 2023+ slice. Under the per-target buffer schedule and the default
4:1 miss:FP cost matrix: t=0.85 ΔEL = −0.0107 with bootstrap CI [−0.014,
−0.008] (~15% EL reduction; t=0.80 reaches ~27% but at higher miss rate);
t=0.95 ΔEL = +0.0245 (~35% worse than Kamino) because the buffered band
over-fires false-positive liquidations. The choice between t=0.80 and t=0.85
as the welfare-optimal default is paper-2 territory; t=0.85 ships as a
moderately conservative Schelling point. Customer-selects-coverage (Option C)
means consumers with extreme bad-debt aversion can still ask for 0.95 or 0.99;
we just don't default there.

**Per-target buffer schedule (2026-04-25).** A scalar 2.5pp buffer was
sufficient at the original τ=0.95 default. After the default moved to
τ=0.85, the same scalar under-corrected (Kupiec p_uc=0.014 reject) and a
proper conformal alternative under-corrected further (see
`reports/v1b_conformal_comparison.md`). The fix is per-target tuning of the
heuristic itself; `BUFFER_BY_TARGET` now persists buffers calibrated against
each anchor point on the OOS 2023+ slice, with linear interpolation for
off-grid targets. See `reports/v1b_buffer_tune.md` for the sweep evidence.

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
# is calibration-surface-tighter than F0 on normal and long_weekend. In
# high_vol, F0 is tighter in-sample and OOS; the hybrid's OOS defense
# primarily rests on Christoffersen independence (hybrid + buffer passes,
# F1 + buffer does not). See reports/v1b_decision.md and
# reports/v1b_ablation.md for the bootstrap intervals.
REGIME_FORECASTER: dict[str, str] = {
    "normal": "F1_emp_regime",
    "long_weekend": "F1_emp_regime",
    "high_vol": "F0_stale",
}
DEFAULT_FORECASTER = "F1_emp_regime"


# Empirical calibration buffer — per-target tuning (2026-04-25).
#
# The v1b hybrid OOS validation found a calibration-surface aging effect: at
# τ=0.95, the surface inversion delivers realized ~0.92 on held-out 2023+ data.
# We close the gap with an empirical buffer added to the consumer's target
# before surface inversion. Disclosed in every PricePoint via
# `calibration_buffer_applied`.
#
# An earlier scalar default (0.025) was tuned for τ=0.95 only. After the
# default operating point moved to τ=0.85 (per the protocol-compare EL
# analysis), the τ=0.95-tuned scalar under-corrected at τ=0.85 and Kupiec
# rejected at p_uc=0.014. The split-conformal comparison
# (`reports/v1b_conformal_comparison.md`) confirmed no off-the-shelf conformal
# alternative outperformed the heuristic, so the fix is per-target tuning of
# the heuristic itself.
#
# Buffers below are the smallest values satisfying realized ≥ τ − 0.005,
# Kupiec p_uc > 0.10, Christoffersen p_ind > 0.05 on the OOS 2023+ slice
# (`reports/v1b_buffer_tune.md`, `reports/tables/v1b_buffer_recommended.csv`).
# Off-grid targets are linearly interpolated between adjacent anchors;
# targets at or above 0.99 hit the structural finite-sample tail ceiling
# (§9.1) regardless of buffer because the bounds grid stops at 0.995.
#
# A production deployment would rebuild this dict on each surface rebuild
# from a rolling OOS backtest. Treat the values as a fixed snapshot of the
# 2026-04-25 calibration; the methodology is the load-bearing artifact, not
# the specific numbers.
BUFFER_BY_TARGET: dict[float, float] = {
    0.68: 0.045,
    0.85: 0.045,
    0.95: 0.020,
    0.99: 0.005,
}

# Scalar fallback retained for callers that pass a single number (e.g., the
# ablation tooling that A/Bs against a fixed buffer). In serving-time use,
# the per-target dict is the primary mechanism.
CALIBRATION_BUFFER_PCT: float = 0.025
MAX_SERVED_TARGET: float = 0.995  # top of the fine grid; can't buffer past this


def buffer_for_target(target: float, schedule: dict[float, float] = None) -> float:
    """Linear-interpolate the per-target buffer schedule for a consumer's
    requested target. Targets below the smallest anchor use the smallest
    anchor's buffer; targets above the largest use the largest anchor's
    buffer. Schedule defaults to the module-level BUFFER_BY_TARGET."""
    if schedule is None:
        schedule = BUFFER_BY_TARGET
    anchors = sorted(schedule.keys())
    if target <= anchors[0]:
        return float(schedule[anchors[0]])
    if target >= anchors[-1]:
        return float(schedule[anchors[-1]])
    for i in range(len(anchors) - 1):
        lo, hi = anchors[i], anchors[i + 1]
        if lo <= target <= hi:
            frac = (target - lo) / (hi - lo)
            return float(schedule[lo] + frac * (schedule[hi] - schedule[lo]))
    return float(schedule[anchors[-1]])  # unreachable; satisfies type checker


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
        calibration_buffer_pct: float | None = None,
        buffer_by_target: dict[float, float] | None = None,
    ):
        self._bounds = bounds
        self._surface = surface
        self._surface_pooled = surface_pooled
        self._regime_forecaster = regime_forecaster or REGIME_FORECASTER
        # If a scalar buffer is supplied, it broadcasts to every target (legacy
        # behaviour and ablation A/B). Otherwise use the per-target schedule.
        self._buffer_scalar = float(calibration_buffer_pct) if calibration_buffer_pct is not None else None
        self._buffer_schedule = dict(buffer_by_target) if buffer_by_target is not None else dict(BUFFER_BY_TARGET)

    @classmethod
    def load(
        cls,
        bounds_path: Path | str = BOUNDS_PATH,
        surface_path: Path | str = SURFACE_PATH,
        surface_pooled_path: Path | str = SURFACE_POOLED_PATH,
        regime_forecaster: dict[str, str] | None = None,
        calibration_buffer_pct: float | None = None,
        buffer_by_target: dict[float, float] | None = None,
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
            buffer_by_target=buffer_by_target,
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
        target_coverage: float = 0.85,
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
        # Resolution order:
        #   1. `buffer_override` (caller-supplied scalar) — A/B and diagnostic.
        #   2. Oracle-level scalar (legacy single-buffer construction) if set.
        #   3. Per-target schedule via `buffer_for_target` interpolation.
        # See reports/v1b_buffer_tune.md for the per-target tuning evidence.
        if buffer_override is not None:
            buffer_pct = float(buffer_override)
        elif self._buffer_scalar is not None:
            buffer_pct = self._buffer_scalar
        else:
            buffer_pct = buffer_for_target(target_coverage, self._buffer_schedule)
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
