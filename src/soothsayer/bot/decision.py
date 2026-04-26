"""DecisionPipeline — orchestrator for the bot's per-position evaluation.

Instrumentation-first: tape append happens *before* any bidding decision.
For MVP, no bidding — the pipeline only produces a classification +
recommended action, and writes the event to the tape.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional

from soothsayer.bot.band_evaluator import BandEvaluator, EVALUATOR_VERSION
from soothsayer.bot.tape import JsonlTape
from soothsayer.bot.types import (
    BandClassification,
    Position,
    TapeEvent,
)


# Recommended-action mapping from BandClassification — MVP only logs;
# v2 will use this to gate Pyth Express Relay bid submission.
RECOMMENDED_ACTION = {
    BandClassification.IN_BAND: "monitor",
    BandClassification.APPROACHING_UPPER: "prewarm",
    BandClassification.APPROACHING_LOWER: "prewarm",
    BandClassification.EXIT_ABOVE: "bid",
    BandClassification.EXIT_BELOW: "bid",
}


class DecisionPipeline:
    """Run a Position through the band evaluator and append to the tape.

    Returns the TapeEvent for caller introspection (tests, dashboards,
    eventually the bid path). The action recommended by the classification
    is reported alongside but not executed in MVP.
    """

    def __init__(
        self,
        evaluator: BandEvaluator,
        tape: JsonlTape,
    ):
        self.evaluator = evaluator
        self.tape = tape

    def process(self, position: Position) -> tuple[TapeEvent, str]:
        classification, band, distance_bps, exit_bps = self.evaluator.evaluate(position)
        event = TapeEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(tz=timezone.utc),
            position=position,
            band=band,
            classification=classification,
            implied_liquidation_price=position.implied_liquidation_price(),
            distance_bps=distance_bps,
            exit_bps=exit_bps,
            evaluator_version=EVALUATOR_VERSION,
        )
        # Tape append happens FIRST — before any action recommendation is logged.
        self.tape.append(event)
        action = RECOMMENDED_ACTION[classification]
        return event, action

    def process_many(self, positions: Iterable[Position]) -> list[tuple[TapeEvent, str]]:
        return [self.process(p) for p in positions]
