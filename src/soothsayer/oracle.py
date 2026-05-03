"""
Soothsayer Oracle — serving-time API (v2 / M5 Mondrian).

Consumers call `Oracle.fair_value(symbol, as_of, target_coverage)` and receive
a calibrated price band: a point estimate and lower/upper bounds whose
empirical coverage matches the target. The band is computed via Mondrian
split-conformal-by-regime (paper 1 §7.7, deployed 2026-MM-DD per
`reports/methodology_history.md`):

  p_hat = fri_close * (1 + factor_ret)                  # §7.4 factor switchboard
  tau'  = tau + DELTA_SHIFT_SCHEDULE(tau)               # OOS-fit conservatism
  q     = C_BUMP_SCHEDULE(tau') * REGIME_QUANTILE_TABLE(regime, tau')
  lower = p_hat * (1 - q),  upper = p_hat * (1 + q),  point = p_hat

Twenty deployment scalars total:
  - `REGIME_QUANTILE_TABLE`  3 regimes × 4 τ-anchors = 12 train-fit quantiles
  - `C_BUMP_SCHEDULE`        4 τ-anchors                = 4 OOS-fit scalars
  - `DELTA_SHIFT_SCHEDULE`   4 τ-anchors                = 4 walk-forward-fit shifts

This matches the v1 deployment's parameter budget (4 OOS scalars in
`BUFFER_BY_TARGET`) plus the 12 trained quantiles and 4 δ shifts. The 12+4
trained-vs-tuned split mirrors the v1 surface (trained) + buffer (tuned)
architecture, with the surface collapsed to a 12-row regime quantile table
and the buffer applied as a multiplicative bump rather than an additive shift
in target-quantile space.

Per-Friday lookup parquet: `data/processed/mondrian_artefact_v2.parquet`
(produced by `scripts/build_mondrian_artefact.py`). Audit-trail sidecar
duplicating the 20 deployment scalars lives at
`data/processed/mondrian_artefact_v2.json`.

Reference: paper 1 §7.7, `reports/methodology_history.md` (M5 entry),
`reports/tables/v1b_mondrian_*.csv`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import DATA_PROCESSED


ARTEFACT_PATH = DATA_PROCESSED / "mondrian_artefact_v2.parquet"

# Mondrian receipt label exposed in PricePoint.forecaster_used and the on-chain
# PriceUpdate.forecaster_code (FORECASTER_MONDRIAN = 2 in the consumer SDK).
MONDRIAN_FORECASTER = "mondrian"


# Per-(regime, τ) trained quantile from the pre-2023 calibration set
# (split date 2023-01-01). See `scripts/build_mondrian_artefact.py` step 1
# for the fit; values match `reports/tables/v1b_mondrian_calibration.csv`
# (method=M2_mondrian_fa, since M5 reuses the M2 fit and adds the OOS bump).
REGIME_QUANTILE_TABLE: dict[str, dict[float, float]] = {
    "normal": {
        0.68: 0.006070,
        0.85: 0.011236,
        0.95: 0.021530,
        0.99: 0.049663,
    },
    "long_weekend": {
        0.68: 0.006648,
        0.85: 0.014248,
        0.95: 0.031032,
        0.99: 0.071228,
    },
    "high_vol": {
        0.68: 0.011628,
        0.85: 0.021460,
        0.95: 0.042911,
        0.99: 0.099418,
    },
}

# OOS-fit multiplicative bump on the trained quantile (the M5 analogue of v1's
# BUFFER_BY_TARGET). One scalar per τ-anchor; off-grid τ linearly interpolated.
# See `reports/tables/v1b_mondrian_calibration.csv` (M5_mondrian_deployable
# rows, bump_c column).
C_BUMP_SCHEDULE: dict[float, float] = {
    0.68: 1.498,
    0.85: 1.455,
    0.95: 1.300,
    0.99: 1.076,
}

# Walk-forward-fit τ-shift schedule. Serves c(τ + δ) · q_r(τ + δ) instead of
# c(τ) · q_r(τ); pushes per-split realised coverage above nominal so the
# deployed schedule is conservative, not centred (see §7.7.4 / sweep table
# `reports/tables/v1b_mondrian_delta_sweep.csv`).
DELTA_SHIFT_SCHEDULE: dict[float, float] = {
    0.68: 0.05,
    0.85: 0.02,
    0.95: 0.00,
    0.99: 0.00,
}

# Default consumer target. Held over from v1 — protocol-policy work consumes
# τ=0.85 as a moderately conservative Schelling point (see paper 3 plan §13).
DEFAULT_TARGET_COVERAGE: float = 0.85
# Top of the τ schedule. Serving requests above this clip to the τ=0.99 row
# of the schedule; finite-sample tail discussion in §9.1.
MAX_SERVED_TARGET: float = 0.99
# Bottom of the τ schedule. Below this we clip to the τ=0.68 row.
MIN_SERVED_TARGET: float = 0.68


def _interp_schedule(tau: float, schedule: dict[float, float]) -> float:
    """Linearly interpolate a τ-keyed schedule. Targets at or below the
    smallest anchor return the smallest anchor's value; targets at or above
    the largest anchor return the largest anchor's value."""
    anchors = sorted(schedule.keys())
    if tau <= anchors[0]:
        return float(schedule[anchors[0]])
    if tau >= anchors[-1]:
        return float(schedule[anchors[-1]])
    for i in range(len(anchors) - 1):
        lo, hi = anchors[i], anchors[i + 1]
        if lo <= tau <= hi:
            frac = (tau - lo) / (hi - lo)
            return float(schedule[lo] + frac * (schedule[hi] - schedule[lo]))
    return float(schedule[anchors[-1]])


def delta_shift_for_target(tau: float) -> float:
    return _interp_schedule(tau, DELTA_SHIFT_SCHEDULE)


def c_bump_for_target(tau: float) -> float:
    return _interp_schedule(tau, C_BUMP_SCHEDULE)


def regime_quantile_for(regime: str, tau: float) -> float:
    """Linearly interpolate the per-regime quantile row at τ. Unknown regimes
    fall back to `high_vol` (the conservative widest-quantile row)."""
    row = REGIME_QUANTILE_TABLE.get(regime, REGIME_QUANTILE_TABLE["high_vol"])
    return _interp_schedule(tau, row)


@dataclass(frozen=True)
class PricePoint:
    """The Soothsayer oracle read. Stable fields are what protocols integrate
    against; `diagnostics` is human-consumable metadata.

    Field semantics under M5:
      - `target_coverage`: what the consumer asked for (τ).
      - `calibration_buffer_applied`: δ(τ) — the OOS-fit τ-shift, the
        structural successor to v1's `BUFFER_BY_TARGET` schedule.
      - `claimed_coverage_served`: τ + δ(τ), the served band's claim.
      - `forecaster_used`: always "mondrian" under M5 (legacy field; on the
        wire this maps to FORECASTER_MONDRIAN = 2).
    """

    symbol: str
    as_of: date
    target_coverage: float
    calibration_buffer_applied: float  # δ(τ) — OOS-fit shift on serving target
    claimed_coverage_served: float  # τ + δ(τ)
    point: float
    lower: float
    upper: float
    regime: str
    forecaster_used: str
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
    """Serving-time Oracle — Mondrian split-conformal by regime."""

    def __init__(self, artefact: pd.DataFrame):
        self._artefact = artefact

    @classmethod
    def load(cls, artefact_path: Path | str = ARTEFACT_PATH) -> "Oracle":
        artefact = pd.read_parquet(artefact_path)
        # Normalise fri_ts to datetime.date so equality checks against
        # consumer-supplied dates work regardless of upstream pandas dtype.
        artefact["fri_ts"] = pd.to_datetime(artefact["fri_ts"]).dt.date
        return cls(artefact=artefact)

    def list_available(self, symbol: Optional[str] = None) -> pd.DataFrame:
        cols = ["symbol", "fri_ts", "regime_pub"]
        df = self._artefact[cols].drop_duplicates()
        if symbol is not None:
            df = df[df["symbol"] == symbol]
        return df.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)

    def fair_value(
        self,
        symbol: str,
        as_of: date | str,
        target_coverage: float = DEFAULT_TARGET_COVERAGE,
    ) -> PricePoint:
        """Serve a calibrated price band.

        At consumer τ, looks up the per-Friday point and regime, applies
        the δ-shift schedule + c(τ) bump + per-regime quantile, returns
        symmetric bounds around the factor-adjusted point.
        """
        if isinstance(as_of, str):
            as_of = pd.to_datetime(as_of).date()

        rows = self._artefact[
            (self._artefact["symbol"] == symbol)
            & (self._artefact["fri_ts"] == as_of)
        ]
        if rows.empty:
            raise ValueError(
                f"No artefact row for symbol={symbol} as_of={as_of}. "
                "Call list_available() to see what's supported."
            )

        row = rows.iloc[0]
        regime = str(row["regime_pub"])
        fri_close = float(row["fri_close"])
        point = float(row["point"])

        tau_clipped = max(min(target_coverage, MAX_SERVED_TARGET), MIN_SERVED_TARGET)
        delta = delta_shift_for_target(tau_clipped)
        served_target = min(tau_clipped + delta, MAX_SERVED_TARGET)
        c_bump = c_bump_for_target(served_target)
        q_regime = regime_quantile_for(regime, served_target)
        q_eff = c_bump * q_regime

        lower = point * (1.0 - q_eff)
        upper = point * (1.0 + q_eff)
        sharpness_bps = (upper - lower) / 2 / fri_close * 1e4 if fri_close else 0.0

        return PricePoint(
            symbol=symbol,
            as_of=as_of,
            target_coverage=float(target_coverage),
            calibration_buffer_applied=float(delta),
            claimed_coverage_served=float(served_target),
            point=point,
            lower=lower,
            upper=upper,
            regime=regime,
            forecaster_used=MONDRIAN_FORECASTER,
            sharpness_bps=sharpness_bps,
            diagnostics={
                "fri_close": fri_close,
                "served_target": served_target,
                "c_bump": c_bump,
                "q_regime": q_regime,
                "q_eff": q_eff,
                "regime_quantile_table_anchors": list(C_BUMP_SCHEDULE.keys()),
            },
        )
