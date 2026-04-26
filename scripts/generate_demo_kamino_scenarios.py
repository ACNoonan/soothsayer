"""Generate the Kamino-fork demo scenario panel from the deployed Oracle.

Phase 1 Week 3 artifact. Runs ``Oracle.fair_value()`` for ~15 weekends
covering all three regimes (normal / long_weekend / high_vol), pairs each
band with a synthetic borrow position sized to sit near the threshold
boundary, and serialises the panel to ``data/processed/demo_kamino_scenarios.json``.

The Rust binary at ``crates/soothsayer-demo-kamino/src/bin/run_demo.rs``
deserialises this file and emits the side-by-side legacy-flat-baseline-vs-
Soothsayer decision comparison. The numbers in the resulting panel are real outputs
from the deployed methodology — the same surface that produces the on-chain
PriceUpdate accounts.

Selection logic (deterministic):

- For each of the three regimes, pick one weekend per symbol from the OOS
  2023+ slice, prioritising **recent** weekends so the panel reflects current
  market structure. Cap to 5 symbols per regime to keep the panel at ~15.
- For each scenario, attach a Position sized so that LTV-against-point is
  near the boundary between Caution (0.75) and Liquidate (0.85). This is
  where small differences in band lower-bound width flip the decision —
  exactly the pitch contrast we want.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from soothsayer.oracle import Oracle


SCENARIO_TARGETS_BY_REGIME = {
    "normal": 0.85,
    "long_weekend": 0.85,
    "high_vol": 0.95,
}

# Five symbols per regime, prioritising the highest-stakes pitch tickers.
PITCH_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSTR", "NVDA"]

OOS_CUTOFF = date(2023, 1, 1)

OUTPUT = Path("data/processed/demo_kamino_scenarios.json")


def position_for(point_price: float, target_ltv: float, collateral_qty: float) -> dict:
    """Size a synthetic borrow so LTV-against-point ≈ target_ltv.

    Kamino-style positions are USDC-denominated debt against a collateral
    quantity of the underlying. We hold collateral_qty fixed and size debt
    to land near the threshold.
    """
    debt = target_ltv * point_price * collateral_qty
    return {"debt_usdc": round(debt, 2), "collateral_qty": collateral_qty}


def main() -> None:
    oracle = Oracle.load()
    available = oracle.list_available()
    available = available[available["fri_ts"] >= OOS_CUTOFF]
    available["regime"] = available["regime_pub"]

    scenarios: list[dict] = []
    pos_size = 100.0  # 100 units of underlying held as collateral per scenario.

    for regime in ("normal", "long_weekend", "high_vol"):
        target = SCENARIO_TARGETS_BY_REGIME[regime]
        regime_rows = available[available["regime"] == regime]
        for sym in PITCH_SYMBOLS:
            sym_rows = regime_rows[regime_rows["symbol"] == sym]
            if sym_rows.empty:
                continue
            # Pick most-recent weekend in (regime, symbol).
            row = sym_rows.iloc[-1]
            as_of: date = row["fri_ts"]
            try:
                pp = oracle.fair_value(symbol=sym, as_of=as_of, target_coverage=target)
            except Exception as e:  # noqa: BLE001 — surface and skip gracefully
                print(f"  skip {sym} {as_of} ({regime}): {e}")
                continue

            # Three target-LTV variants per scenario to populate Safe / Caution / Liquidate.
            for target_ltv, label in ((0.65, "safe"), (0.80, "caution_zone"), (0.90, "liquidate_zone")):
                scenarios.append({
                    "scenario_id": f"{sym}_{as_of}_{regime}_{label}",
                    "label": label,
                    "regime_label": regime,
                    "target_ltv": target_ltv,
                    "band": pp.to_dict(),
                    "position": position_for(pp.point, target_ltv, pos_size),
                    # Legacy flat-band baseline retained for continuity with the
                    # original Kamino comparison scaffold.
                    "kamino_deviation_bps": 300,
                })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w") as f:
        json.dump(scenarios, f, indent=2, default=str)
    print(f"Wrote {len(scenarios)} scenarios → {OUTPUT}")

    # Quick summary so a reviewer can sanity-check the panel composition.
    counts = pd.Series([s["regime_label"] for s in scenarios]).value_counts()
    print("Regime distribution:")
    for regime, n in counts.items():
        print(f"  {regime}: {n}")


if __name__ == "__main__":
    main()
