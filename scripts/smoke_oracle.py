"""
Smoke test for the Soothsayer Oracle serving API — hybrid regime edition.

Demonstrates the core product claims:

  1. Customer-selects-coverage: consumer asks for realized coverage, we
     return an audit-receipt showing which claimed quantile delivered it.

  2. Hybrid forecaster selection per regime (v1b evidence at matched
     realized coverage): F1_emp_regime on normal/long_weekend, F0_stale in
     high_vol where F1 stretches and F0's already-wide Gaussian is more
     efficient. The receipt tells the consumer which forecaster was used.

Loads artifacts produced by `scripts/run_calibration.py`.
"""

from __future__ import annotations

import json
from datetime import date

from soothsayer.oracle import Oracle, REGIME_FORECASTER


def main() -> None:
    oracle = Oracle.load()

    available = oracle.list_available(symbol="SPY")
    print(f"SPY available weekends in bounds table: {len(available):,}")
    print(f"  range: {available['fri_ts'].min()} → {available['fri_ts'].max()}")
    print()
    print(f"Hybrid regime policy: {REGIME_FORECASTER}")
    print()

    # Pick the most recent Friday in each regime (if the regime exists in SPY's history)
    sample_fridays = [
        ("normal",
         available[available["regime_pub"] == "normal"]["fri_ts"].sort_values().iloc[-1]
         if not available[available["regime_pub"] == "normal"].empty else None),
        ("high_vol",
         available[available["regime_pub"] == "high_vol"]["fri_ts"].sort_values().iloc[-1]
         if not available[available["regime_pub"] == "high_vol"].empty else None),
        ("long_weekend",
         available[available["regime_pub"] == "long_weekend"]["fri_ts"].sort_values().iloc[-1]
         if not available[available["regime_pub"] == "long_weekend"].empty else None),
    ]

    target_coverages = (0.68, 0.95, 0.99)

    for regime_name, fri in sample_fridays:
        if fri is None:
            continue
        print(f"─── SPY @ {fri}  (regime: {regime_name}) ───────────────")
        for tc in target_coverages:
            fv = oracle.fair_value("SPY", fri, target_coverage=tc)
            print(
                f"  target={tc:>5.2f}  "
                f"forecaster={fv.forecaster_used:<15}  "
                f"claim_served={fv.claimed_coverage_served:>5.3f}  "
                f"point=${fv.point:>8.2f}  "
                f"band=[{fv.lower:>7.2f}, {fv.upper:>7.2f}]  "
                f"half-width={fv.half_width_bps:>6.1f}bps"
            )
        print()

    # A/B comparison on the same high_vol Friday: hybrid (F0) vs. forced F1_emp_regime
    print("─── High-vol regime: hybrid F0 vs. forced F1_emp_regime ────")
    hv_fri = sample_fridays[1][1]
    if hv_fri is not None:
        fv_hybrid = oracle.fair_value("SPY", hv_fri, target_coverage=0.95)
        fv_f1 = oracle.fair_value("SPY", hv_fri, target_coverage=0.95,
                                   forecaster_override="F1_emp_regime")
        print(
            f"  hybrid (F0)   half-width={fv_hybrid.half_width_bps:>6.1f}bps "
            f"claim_served={fv_hybrid.claimed_coverage_served:.3f}"
        )
        print(
            f"  forced F1     half-width={fv_f1.half_width_bps:>6.1f}bps "
            f"claim_served={fv_f1.claimed_coverage_served:.3f}"
        )
        delta = fv_hybrid.half_width_bps - fv_f1.half_width_bps
        if fv_hybrid.half_width_bps < fv_f1.half_width_bps:
            pct = abs(delta) / fv_f1.half_width_bps * 100
            winner = f"hybrid (F0) is {pct:.1f}% tighter than forced F1 at matched target={fv_hybrid.target_coverage}"
        else:
            pct = delta / fv_f1.half_width_bps * 100
            winner = f"hybrid (F0) is {pct:.1f}% wider than forced F1"
        print(f"  → {winner} — F1's claim stretched to {fv_f1.claimed_coverage_served:.3f} vs hybrid's {fv_hybrid.claimed_coverage_served:.3f}")
        print()

    # Cross-symbol sample (target_coverage=0.95)
    print("─── Cross-symbol sample (target_coverage=0.95) ────────────")
    symbols = ("SPY", "QQQ", "NVDA", "TSLA", "MSTR", "HOOD", "GLD", "TLT")
    for sym in symbols:
        av = oracle.list_available(symbol=sym)
        if av.empty:
            continue
        recent = av["fri_ts"].sort_values().iloc[-1]
        try:
            fv = oracle.fair_value(sym, recent, target_coverage=0.95)
            print(
                f"  {sym:<6} @ {fv.as_of}  "
                f"regime={fv.regime:<12}  "
                f"forecaster={fv.forecaster_used:<15}  "
                f"half-width={fv.half_width_bps:>6.1f}bps  "
                f"(claim={fv.claimed_coverage_served:.3f})"
            )
        except Exception as exc:
            print(f"  {sym:<6} @ {recent}  ERROR: {exc}")

    # Dump a sample PricePoint as JSON — what a protocol integrator receives
    print()
    print("─── Sample response payload (JSON) ──────────────────────")
    last_spy = available["fri_ts"].sort_values().iloc[-1]
    fv = oracle.fair_value("SPY", last_spy, target_coverage=0.95)
    print(json.dumps(fv.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()
