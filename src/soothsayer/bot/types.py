"""Core types for the Soothsayer liquidator bot.

All types are intentionally Python-side only for MVP. The V5 tape format
(JSONL on disk, eventually Parquet for analysis) is the wire format that
the Solana / Pyth / Jito reconstructors will populate at v1+.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from enum import Enum


class BandClassification(str, Enum):
    """How a position's implied liquidation price relates to the served band."""

    IN_BAND = "in_band"
    APPROACHING_UPPER = "approaching_upper"
    APPROACHING_LOWER = "approaching_lower"
    EXIT_ABOVE = "exit_above"
    EXIT_BELOW = "exit_below"


@dataclass(frozen=True)
class Position:
    """A Kamino-style lending position.

    For MVP/devnet, these are synthetic. For v1 mainnet observe-only,
    these are populated from `accountSubscribe` over WebSocket against
    the Kamino lending program. The dataclass is intentionally thin —
    only the fields needed for band evaluation.
    """

    position_id: str
    symbol: str  # collateral asset symbol (e.g., "SPY", "TSLA"; xStocks → underlying)
    collateral_amount: float  # units of collateral asset
    debt_amount_usd: float  # USD-denominated debt
    liquidation_threshold: float  # e.g., 0.85 — LTV at which the position becomes liquidatable
    observed_at: datetime  # when we observed this state

    def implied_liquidation_price(self) -> float:
        """Price at which this position becomes liquidatable.

        At liquidation_threshold, debt = LT × collateral_value = LT × C × P,
        so P_liq = debt / (LT × C).
        """
        if self.collateral_amount <= 0 or self.liquidation_threshold <= 0:
            raise ValueError("collateral_amount and liquidation_threshold must be > 0")
        return self.debt_amount_usd / (self.liquidation_threshold * self.collateral_amount)

    def ltv_at(self, price: float) -> float:
        if self.collateral_amount <= 0 or price <= 0:
            return float("inf")
        return self.debt_amount_usd / (self.collateral_amount * price)


@dataclass(frozen=True)
class BandSnapshot:
    """Frozen view of the served Soothsayer band at evaluation time."""

    symbol: str
    as_of: date
    target_coverage: float
    point: float
    lower: float
    upper: float
    q_served: float
    regime: str
    forecaster_used: str
    sharpness_bps: float
    calibration_buffer_applied: float


@dataclass(frozen=True)
class TapeEvent:
    """One observation in the V5 forward-cursor research tape.

    Instrumentation contract: every position-band evaluation produces a
    TapeEvent, regardless of whether the bot bids, wins, or sees the
    event resolve. The tape is the primary deliverable.
    """

    event_id: str
    timestamp: datetime
    position: Position
    band: BandSnapshot
    classification: BandClassification
    implied_liquidation_price: float
    distance_bps: float  # signed distance from implied to band point, in bps
    exit_bps: float  # absolute distance beyond the band edge; 0 if in-band
    evaluator_version: str

    def to_jsonl_dict(self) -> dict:
        """Serialisable form for the JSONL tape."""
        d = asdict(self)
        # datetimes / dates → ISO strings for JSON
        d["timestamp"] = self.timestamp.isoformat()
        d["position"]["observed_at"] = self.position.observed_at.isoformat()
        d["band"]["as_of"] = self.band.as_of.isoformat()
        d["classification"] = self.classification.value
        return d
