"""Bot MVP smoke run with synthetic positions.

Generates a small panel of synthetic Kamino-style positions across the
full classification spectrum (in-band / approaching / exit), runs them
through the DecisionPipeline, and writes the resulting events to a
JSONL tape at `data/bot_tape/mvp_synthetic.jsonl`.

This is the v0 instrumentation-contract validation: every event hits
the tape; no Solana RPC, no Pyth Express Relay, no Jito bundles. v1
will replace synthetic position generation with `accountSubscribe`
against the Kamino lending program.
"""
from __future__ import annotations

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

REPO = Path(__file__).resolve().parents[1]
TAPE_PATH = REPO / "data" / "bot_tape" / "mvp_synthetic.jsonl"

# Pick a Friday from the Paper 1 panel — guaranteed served bands.
EVAL_DATE = date(2026, 4, 17)
TARGET_COVERAGE = 0.95
LIQUIDATION_THRESHOLD = 0.85
COLLATERAL_AMOUNT = 100.0  # 100 units of the underlying asset

# Set of synthetic positions per symbol, parameterised by where we want the
# position-implied liquidation price to fall relative to the served band.
SYNTHETIC_PROBES = {
    "midpoint": 0.0,            # exactly at point — deep in-band
    "approaching-upper": 0.997, # 30 bps inside upper edge
    "exit-above-modest": 1.005, # ~50 bps beyond upper
    "exit-above-large": 1.04,   # ~400 bps beyond upper — tail event
    "approaching-lower": 1.003, # 30 bps inside lower edge (factor inverted below)
    "exit-below-modest": 0.995, # ~50 bps beyond lower
    "exit-below-large": 0.96,   # ~400 bps beyond lower
}

# Symbols to probe — broad coverage of the deployed Soothsayer panel.
SYMBOLS = ["SPY", "QQQ", "TSLA", "NVDA", "AAPL", "GOOGL", "MSTR", "GLD"]


def synthesize_positions(
    oracle: Oracle, eval_date: date, tau: float
) -> list[Position]:
    """Generate a panel of synthetic positions across the classification spectrum."""
    positions: list[Position] = []
    obs_at = datetime(eval_date.year, eval_date.month, eval_date.day, 16, 0, tzinfo=timezone.utc)

    for symbol in SYMBOLS:
        try:
            pp = oracle.fair_value(symbol, eval_date, target_coverage=tau)
        except ValueError:
            continue  # symbol not in panel for this date

        for label, factor in SYNTHETIC_PROBES.items():
            if label == "midpoint":
                target_implied = pp.point
            elif label.startswith("approaching-upper") or label.startswith("exit-above"):
                target_implied = pp.upper * factor
            else:
                target_implied = pp.lower * factor

            debt = LIQUIDATION_THRESHOLD * COLLATERAL_AMOUNT * target_implied
            positions.append(
                Position(
                    position_id=f"{symbol}-{label}",
                    symbol=symbol,
                    collateral_amount=COLLATERAL_AMOUNT,
                    debt_amount_usd=debt,
                    liquidation_threshold=LIQUIDATION_THRESHOLD,
                    observed_at=obs_at,
                )
            )
    return positions


def main() -> None:
    oracle = Oracle.load()
    print(f"Oracle loaded; eval date {EVAL_DATE}, τ={TARGET_COVERAGE}", flush=True)

    positions = synthesize_positions(oracle, EVAL_DATE, TARGET_COVERAGE)
    print(f"Synthesised {len(positions)} positions across {len(SYMBOLS)} symbols", flush=True)

    evaluator = BandEvaluator(oracle=oracle, target_coverage=TARGET_COVERAGE)
    print(f"Tape sink: {TAPE_PATH}", flush=True)

    classification_counts: dict[str, int] = {c.value: 0 for c in BandClassification}
    action_counts: dict[str, int] = {}

    with JsonlTape(TAPE_PATH) as tape:
        pipeline = DecisionPipeline(evaluator=evaluator, tape=tape)
        for position in positions:
            event, action = pipeline.process(position)
            classification_counts[event.classification.value] += 1
            action_counts[action] = action_counts.get(action, 0) + 1

    print()
    print("Classifications observed:")
    for cls, count in sorted(classification_counts.items()):
        if count:
            print(f"  {cls:25s} {count:3d}")

    print()
    print("Recommended actions:")
    for action, count in sorted(action_counts.items()):
        print(f"  {action:25s} {count:3d}")

    # Sanity: tape line count == positions
    n_lines = sum(1 for _ in TAPE_PATH.open("r", encoding="utf-8"))
    print()
    print(f"Tape line count: {n_lines} (expected {len(positions)})")
    assert n_lines == len(positions), "instrumentation contract violated"
    print("Instrumentation contract: OK (every position hit the tape).")


if __name__ == "__main__":
    main()
