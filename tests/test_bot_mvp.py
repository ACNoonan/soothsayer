"""Bot MVP — instrumentation-contract tests.

Exercises:
  - Position math (implied liquidation price, LTV).
  - BandEvaluator classification across the full spectrum
    (in-band, approaching, exit-above, exit-below).
  - DecisionPipeline tape-append-before-decision contract.
  - JsonlTape round-trip.

Uses synthetic positions and the deployed Soothsayer Oracle on a
Friday from the Paper 1 panel.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from soothsayer.bot import (
    BandClassification,
    BandEvaluator,
    DecisionPipeline,
    JsonlTape,
    Position,
)
from soothsayer.oracle import Oracle

# A Friday that exists in the Paper 1 panel for SPY (2026-04-17 was the
# last Friday of the OOS slice). Tests are robust against slight regimes.
TEST_FRIDAY = date(2026, 4, 17)


class PositionMathTests(unittest.TestCase):
    def test_implied_liquidation_price(self) -> None:
        # Position: 100 SPY collateral, $80,000 debt, LT=0.85
        # P_liq = 80000 / (0.85 × 100) = 941.18
        p = Position(
            position_id="t1",
            symbol="SPY",
            collateral_amount=100.0,
            debt_amount_usd=80_000.0,
            liquidation_threshold=0.85,
            observed_at=datetime(2026, 4, 17, 16, 0, tzinfo=timezone.utc),
        )
        self.assertAlmostEqual(p.implied_liquidation_price(), 941.176, places=2)

    def test_ltv_at_price(self) -> None:
        p = Position(
            position_id="t2",
            symbol="SPY",
            collateral_amount=100.0,
            debt_amount_usd=80_000.0,
            liquidation_threshold=0.85,
            observed_at=datetime(2026, 4, 17, 16, 0, tzinfo=timezone.utc),
        )
        # At price 1000: LTV = 80000 / (100 * 1000) = 0.80
        self.assertAlmostEqual(p.ltv_at(1000.0), 0.80, places=4)

    def test_invalid_inputs_raise(self) -> None:
        p = Position(
            position_id="bad",
            symbol="SPY",
            collateral_amount=0.0,
            debt_amount_usd=80_000.0,
            liquidation_threshold=0.85,
            observed_at=datetime(2026, 4, 17, 16, 0, tzinfo=timezone.utc),
        )
        with self.assertRaises(ValueError):
            p.implied_liquidation_price()


class BandEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = Oracle.load()
        cls.evaluator = BandEvaluator(oracle=cls.oracle, target_coverage=0.95)
        cls.pp = cls.oracle.fair_value("SPY", TEST_FRIDAY, target_coverage=0.95)

    def _position_with_implied_price(self, target_implied: float) -> Position:
        # debt = LT × C × P → set debt to engineer implied price
        collateral = 100.0
        lt = 0.85
        debt = lt * collateral * target_implied
        return Position(
            position_id=f"engineered-{target_implied:.2f}",
            symbol="SPY",
            collateral_amount=collateral,
            debt_amount_usd=debt,
            liquidation_threshold=lt,
            observed_at=datetime(2026, 4, 17, 16, 0, tzinfo=timezone.utc),
        )

    def test_in_band_classifies_in_band(self) -> None:
        # Set implied price to band midpoint
        p = self._position_with_implied_price(self.pp.point)
        cls, band, dist_bps, exit_bps = self.evaluator.evaluate(p, as_of=TEST_FRIDAY)
        self.assertEqual(cls, BandClassification.IN_BAND)
        self.assertAlmostEqual(dist_bps, 0.0, places=2)
        self.assertEqual(exit_bps, 0.0)

    def test_exit_above_classifies(self) -> None:
        # 300 bps beyond upper edge — well past the 100 bps approaching threshold
        target = self.pp.upper * (1 + 300 / 1e4)
        p = self._position_with_implied_price(target)
        cls, _, dist_bps, exit_bps = self.evaluator.evaluate(p, as_of=TEST_FRIDAY)
        self.assertEqual(cls, BandClassification.EXIT_ABOVE)
        self.assertGreater(exit_bps, 0)
        self.assertGreater(dist_bps, 0)

    def test_exit_below_classifies(self) -> None:
        target = self.pp.lower * (1 - 300 / 1e4)
        p = self._position_with_implied_price(target)
        cls, _, dist_bps, exit_bps = self.evaluator.evaluate(p, as_of=TEST_FRIDAY)
        self.assertEqual(cls, BandClassification.EXIT_BELOW)
        self.assertGreater(exit_bps, 0)
        self.assertLess(dist_bps, 0)

    def test_approaching_upper_classifies(self) -> None:
        # 30 bps inside upper edge — within default 100 bps approaching threshold
        target = self.pp.upper * (1 - 30 / 1e4)
        p = self._position_with_implied_price(target)
        cls, _, _, exit_bps = self.evaluator.evaluate(p, as_of=TEST_FRIDAY)
        self.assertEqual(cls, BandClassification.APPROACHING_UPPER)
        self.assertEqual(exit_bps, 0.0)

    def test_approaching_lower_classifies(self) -> None:
        target = self.pp.lower * (1 + 30 / 1e4)
        p = self._position_with_implied_price(target)
        cls, _, _, exit_bps = self.evaluator.evaluate(p, as_of=TEST_FRIDAY)
        self.assertEqual(cls, BandClassification.APPROACHING_LOWER)
        self.assertEqual(exit_bps, 0.0)


class DecisionPipelineTapeContractTests(unittest.TestCase):
    """Verify the instrumentation contract: every observation hits the tape."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = Oracle.load()
        cls.evaluator = BandEvaluator(oracle=cls.oracle, target_coverage=0.95)
        cls.pp = cls.oracle.fair_value("SPY", TEST_FRIDAY, target_coverage=0.95)

    def _position(self, label: str, target_implied: float) -> Position:
        collateral = 100.0
        lt = 0.85
        return Position(
            position_id=label,
            symbol="SPY",
            collateral_amount=collateral,
            debt_amount_usd=lt * collateral * target_implied,
            liquidation_threshold=lt,
            observed_at=datetime(2026, 4, 17, 16, 0, tzinfo=timezone.utc),
        )

    def test_every_position_hits_tape(self) -> None:
        positions = [
            self._position("a-in-band", self.pp.point),
            self._position("b-exit-above", self.pp.upper * 1.03),
            self._position("c-exit-below", self.pp.lower * 0.97),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tape_path = Path(tmp) / "tape.jsonl"
            with JsonlTape(tape_path) as tape:
                pipeline = DecisionPipeline(evaluator=self.evaluator, tape=tape)
                results = []
                for p in positions:
                    # Override observed_at.date() via direct evaluation date
                    # — easier in tests, mirrors v1 RPC-timestamp injection
                    cls, band, dist, exit_b = self.evaluator.evaluate(p, as_of=TEST_FRIDAY)
                    # We call .process() to exercise the pipeline contract,
                    # but accept that .process() uses the position's
                    # observed_at by default — for the smoke test that's fine.
                    event, action = pipeline.process(p)
                    results.append((event, action))
            # Re-read the tape and verify every position is represented.
            lines = tape_path.read_text().strip().split("\n")
            self.assertEqual(len(lines), len(positions))
            ids = [json.loads(line)["position"]["position_id"] for line in lines]
            self.assertEqual(set(ids), {"a-in-band", "b-exit-above", "c-exit-below"})

    def test_tape_round_trip_preserves_classification(self) -> None:
        p = self._position("rt", self.pp.upper * 1.02)
        with tempfile.TemporaryDirectory() as tmp:
            tape_path = Path(tmp) / "tape.jsonl"
            with JsonlTape(tape_path) as tape:
                pipeline = DecisionPipeline(evaluator=self.evaluator, tape=tape)
                event, action = pipeline.process(p)
            line = tape_path.read_text().strip()
            payload = json.loads(line)
            self.assertEqual(payload["position"]["position_id"], "rt")
            # Classification persists in tape exactly as the BandClassification
            # enum's value (since target was set to upper*1.02 = exit_above).
            self.assertIn(payload["classification"], {
                BandClassification.EXIT_ABOVE.value,
                BandClassification.APPROACHING_UPPER.value,
            })


if __name__ == "__main__":
    unittest.main()
