"""
Smoke test for the Soothsayer Oracle serving API — dual-profile (M5 + M6b2).

Phase A2 deliverable: instantiate both profiles on a sample Friday, print
both bands across the universe, and visually diff against
`reports/v1b_m6b_per_symbol_class_mondrian.md`'s per-class table:

  - Lending should tighten the wide-PIT classes the M5 per-regime quantile
    over-allocated to (equity_index, gold, bond at τ=0.95).
  - Lending should widen the narrow-PIT classes M5 under-allocated to
    (equity_highbeta, equity_recent at τ=0.95).
  - AMM bands match the deployed M5 receipts byte-for-byte.

Loads the artefact produced by `scripts/build_mondrian_artefact.py` plus
the Lending sidecar produced by `scripts/build_m6b2_lending_artefact.py`.
"""

from __future__ import annotations

import json

from soothsayer.oracle import (
    C_BUMP_SCHEDULE,
    DELTA_SHIFT_SCHEDULE,
    LENDING_C_BUMP_SCHEDULE,
    LENDING_DELTA_SHIFT_SCHEDULE,
    LENDING_METADATA,
    LENDING_QUANTILE_TABLE,
    REGIME_QUANTILE_TABLE,
    Oracle,
)
from soothsayer.universe import SYMBOL_CLASS_MAP


def _print_constants() -> None:
    print("M5 (AMM profile) constants:")
    print("  REGIME_QUANTILE_TABLE:")
    for r, row in REGIME_QUANTILE_TABLE.items():
        cells = "  ".join(f"τ={t:.2f}: {q:.4f}" for t, q in row.items())
        print(f"    {r:>14}  {cells}")
    print(f"  C_BUMP_SCHEDULE:      {C_BUMP_SCHEDULE}")
    print(f"  DELTA_SHIFT_SCHEDULE: {DELTA_SHIFT_SCHEDULE}")
    print()
    print(f"M6b2 (Lending profile) constants  [{LENDING_METADATA.get('methodology_version')}]:")
    print("  LENDING_QUANTILE_TABLE:")
    for cls, row in LENDING_QUANTILE_TABLE.items():
        cells = "  ".join(f"τ={t:.2f}: {b:.4f}" for t, b in row.items())
        print(f"    {cls:>16}  {cells}")
    print(f"  LENDING_C_BUMP_SCHEDULE:      {LENDING_C_BUMP_SCHEDULE}")
    print(f"  LENDING_DELTA_SHIFT_SCHEDULE: {LENDING_DELTA_SHIFT_SCHEDULE}")
    print()


def _sample_friday(oracle: Oracle) -> tuple[str, object]:
    available = oracle.list_available(symbol="SPY")
    return ("SPY", available["fri_ts"].iloc[-1])


def _print_dual_band(symbol: str, friday, lending: Oracle, amm: Oracle) -> None:
    print(f"--- {symbol} ({SYMBOL_CLASS_MAP.get(symbol, '?')})  fri_ts={friday}")
    header = f"     {'τ':>5}  {'profile':>9}  {'point':>10}  {'lower':>10}  {'upper':>10}  {'hw_bps':>8}"
    print(header)
    for tau in (0.68, 0.85, 0.95, 0.99):
        for profile, oracle in [("lending", lending), ("amm", amm)]:
            try:
                pp = oracle.fair_value(symbol, friday, target_coverage=tau)
            except ValueError as e:
                print(f"     τ={tau:.2f}  {profile:>9}  {'(unavailable)':>30}  {e}")
                continue
            print(
                f"     τ={tau:.2f}  {profile:>9}  "
                f"{pp.point:>10.4f}  {pp.lower:>10.4f}  {pp.upper:>10.4f}  "
                f"{pp.half_width_bps:>8.2f}"
            )
    print()


def _per_class_table(lending: Oracle, amm: Oracle, friday) -> None:
    """Reproduces the visual shape of the per-class breakdown table at τ=0.95
    in `reports/v1b_m6b_per_symbol_class_mondrian.md`. Each row is the half-
    width served by the two profiles on `friday` for one symbol — the per-
    class re-allocation should be visible at a glance."""
    tau = 0.95
    print(f"Per-symbol band-half-width comparison at τ={tau:.2f}, fri_ts={friday}:")
    print(f"  {'symbol':>7}  {'class':>16}  {'lending_bps':>11}  {'amm_bps':>9}  {'Δ%':>7}")
    for symbol in sorted(SYMBOL_CLASS_MAP.keys()):
        try:
            pp_l = lending.fair_value(symbol, friday, target_coverage=tau)
            pp_a = amm.fair_value(symbol, friday, target_coverage=tau)
        except ValueError:
            print(f"  {symbol:>7}  {SYMBOL_CLASS_MAP[symbol]:>16}  (no row this Friday)")
            continue
        delta_pct = (pp_l.half_width_bps - pp_a.half_width_bps) / pp_a.half_width_bps * 100
        print(
            f"  {symbol:>7}  {SYMBOL_CLASS_MAP[symbol]:>16}  "
            f"{pp_l.half_width_bps:>11.2f}  {pp_a.half_width_bps:>9.2f}  "
            f"{delta_pct:>+7.1f}"
        )
    print()


def main() -> None:
    lending = Oracle.load(profile="lending")
    amm = Oracle.load(profile="amm")
    print(f"Profiles loaded: lending (default) + amm (M5)")
    print()

    _print_constants()

    symbol, friday = _sample_friday(lending)
    _print_dual_band(symbol, friday, lending, amm)
    _per_class_table(lending, amm, friday)

    pp = lending.fair_value(symbol, friday, target_coverage=0.95)
    print("Receipt JSON (Lending profile, τ=0.95, latest SPY Friday):")
    print(json.dumps(pp.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()
