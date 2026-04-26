"""Soothsayer xStocks-on-Kamino weekend-reopen liquidator bot.

MVP / devnet scope: position monitor + band evaluator + tape logger.
No bidding. Synthetic positions. Validates the instrumentation contract
documented in `docs/bot_kamino_xstocks_liquidator.md`.

The bot's primary deliverable is the V5 forward-cursor *tape* — a research-
grade record of every band-classified observation. Net liquidation revenue
is secondary; instrumentation comes first.
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
