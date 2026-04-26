"""BandEvaluator — wraps Soothsayer Oracle, classifies positions.

Given a Position and (optionally) a date to read the band as-of, returns
a BandClassification + a BandSnapshot + the per-event distance / exit
bps the tape needs.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from soothsayer.bot.types import (
    BandClassification,
    BandSnapshot,
    Position,
)
from soothsayer.oracle import Oracle, PricePoint

EVALUATOR_VERSION = "0.1.0-mvp"

DEFAULT_APPROACHING_BPS = 100.0  # within X bps of band edge → approaching, not in_band


class BandEvaluator:
    """Classify a Position relative to the Soothsayer-served band at a τ."""

    def __init__(
        self,
        oracle: Optional[Oracle] = None,
        target_coverage: float = 0.95,
        approaching_bps: float = DEFAULT_APPROACHING_BPS,
    ):
        self.oracle = oracle if oracle is not None else Oracle.load()
        self.target_coverage = float(target_coverage)
        self.approaching_bps = float(approaching_bps)

    def evaluate(
        self,
        position: Position,
        as_of: Optional[date] = None,
    ) -> tuple[BandClassification, BandSnapshot, float, float]:
        """Run the full band evaluation pipeline for one position.

        Returns (classification, band_snapshot, distance_bps, exit_bps).
        """
        evaluation_date = as_of if as_of is not None else position.observed_at.date()
        pp = self.oracle.fair_value(
            position.symbol,
            evaluation_date,
            target_coverage=self.target_coverage,
        )
        band = self._snapshot(position.symbol, evaluation_date, pp)
        implied_price = position.implied_liquidation_price()
        classification, exit_bps = self._classify(implied_price, band)
        # Signed distance to band midpoint, normalised to bps of point.
        distance_bps = (implied_price - band.point) / band.point * 1e4
        return classification, band, distance_bps, exit_bps

    @staticmethod
    def _snapshot(symbol: str, as_of: date, pp: PricePoint) -> BandSnapshot:
        return BandSnapshot(
            symbol=symbol,
            as_of=as_of,
            target_coverage=float(pp.target_coverage),
            point=float(pp.point),
            lower=float(pp.lower),
            upper=float(pp.upper),
            q_served=float(pp.claimed_coverage_served),
            regime=str(pp.regime),
            forecaster_used=str(pp.forecaster_used),
            sharpness_bps=float(pp.sharpness_bps),
            calibration_buffer_applied=float(pp.calibration_buffer_applied),
        )

    def _classify(
        self,
        implied_price: float,
        band: BandSnapshot,
    ) -> tuple[BandClassification, float]:
        # Outside the band: exit classification + bps beyond the nearer edge.
        if implied_price > band.upper:
            exit_bps = (implied_price - band.upper) / band.point * 1e4
            return BandClassification.EXIT_ABOVE, exit_bps
        if implied_price < band.lower:
            exit_bps = (band.lower - implied_price) / band.point * 1e4
            return BandClassification.EXIT_BELOW, exit_bps

        # Inside the band: check approaching-edge buffer.
        upper_dist_bps = (band.upper - implied_price) / band.point * 1e4
        lower_dist_bps = (implied_price - band.lower) / band.point * 1e4
        if upper_dist_bps < self.approaching_bps:
            return BandClassification.APPROACHING_UPPER, 0.0
        if lower_dist_bps < self.approaching_bps:
            return BandClassification.APPROACHING_LOWER, 0.0
        return BandClassification.IN_BAND, 0.0
