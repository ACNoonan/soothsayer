"""Soothsayer xStocks-on-Kamino weekend-reopen observe-first instrument.

MVP / devnet scope: position monitor + band evaluator + tape logger.
No bidding. Synthetic positions. Validates the observe-first
instrumentation contract for Kamino-style reserve-buffer monitoring.

The primary deliverable is the V5 forward-cursor *tape* — a research-grade
record of every observed event under real Kamino reserve semantics. Net
liquidation revenue, if any, is secondary; instrumentation comes first.
"""
from soothsayer.bot.types import (
    BandClassification,
    BandSnapshot,
    Position,
    TapeEvent,
)
from soothsayer.bot.band_evaluator import BandEvaluator, EVALUATOR_VERSION
from soothsayer.bot.tape import JsonlTape
from soothsayer.bot.decision import DecisionPipeline

__all__ = [
    "BandClassification",
    "BandSnapshot",
    "Position",
    "TapeEvent",
    "BandEvaluator",
    "EVALUATOR_VERSION",
    "JsonlTape",
    "DecisionPipeline",
]
