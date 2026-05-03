"""
Smoke test for the Soothsayer Oracle serving API — Mondrian (M5) edition.

Demonstrates the v2 product claims:

  1. Customer-selects-coverage: consumer asks for realised coverage τ, the
     served band reports the actually-served quantile (τ + δ(τ)) and the
     audit receipt for the per-regime conformal lookup.

  2. Mondrian split-conformal-by-regime (paper 1 §7.7): the regime classifier
     `regime_pub` is the load-bearing piece; the per-regime trained quantile
     plus the OOS-fit c(τ) bump and walk-forward δ-shift schedule deliver
     20–33% narrower bands at indistinguishable Kupiec calibration through
     τ ≤ 0.95 vs the v1 deployed Oracle.

Loads the artefact produced by `scripts/build_mondrian_artefact.py`.
"""

from __future__ import annotations

import json

from soothsayer.oracle import (
    C_BUMP_SCHEDULE,
    DELTA_SHIFT_SCHEDULE,
    REGIME_QUANTILE_TABLE,
    Oracle,
)


def main() -> None:
    oracle = Oracle.load()

    available = oracle.list_available(symbol="SPY")
    print(f"SPY available weekends in M5 artefact: {len(available):,}")
    print(f"  range: {available['fri_ts'].min()} → {available['fri_ts'].max()}")
    print()
    print("M5 deployment constants (paper 1 §7.7):")
    print("  REGIME_QUANTILE_TABLE:")
    for r, row in REGIME_QUANTILE_TABLE.items():
        cells = "  ".join(f"τ={t:.2f}: {q:.4f}" for t, q in row.items())
        print(f"    {r:>14}  {cells}")
    print(f"  C_BUMP_SCHEDULE:    {C_BUMP_SCHEDULE}")
    print(f"  DELTA_SHIFT_SCHEDULE: {DELTA_SHIFT_SCHEDULE}")
    print()

    sample_fridays = []
    for regime in ("normal", "long_weekend", "high_vol"):
        sub = available[available["regime_pub"] == regime]
        if not sub.empty:
            sample_fridays.append((regime, sub["fri_ts"].iloc[-1]))

    for regime, friday in sample_fridays:
        print(f"=== regime={regime}  fri_ts={friday} ===")
        for tau in (0.68, 0.85, 0.95, 0.99):
            pp = oracle.fair_value("SPY", friday, target_coverage=tau)
            print(f"  τ={tau:.2f}: served={pp.claimed_coverage_served:.3f}, "
                  f"point=${pp.point:.2f}, "
                  f"hw={pp.half_width_bps:.0f}bps, "
                  f"forecaster={pp.forecaster_used}")
        print()

    pp = oracle.fair_value("SPY", available["fri_ts"].iloc[-1], target_coverage=0.95)
    print("Receipt JSON (τ=0.95, latest SPY Friday):")
    print(json.dumps(pp.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()
