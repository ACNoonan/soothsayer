"""
Smoke test for the Soothsayer Oracle serving API.

Two modes, controlled by `--forecaster`:

  --forecaster m5          (default; dual-profile M5 + M6b2 visual diff)
                           Phase A2 deliverable: instantiate both profiles
                           on a sample Friday, print both bands across the
                           universe, and visually diff against
                           `reports/v1b_m6b_per_symbol_class_mondrian.md`'s
                           per-class table:
                             - Lending tightens wide-PIT classes (equity_index,
                               gold, bond at τ=0.95).
                             - Lending widens narrow-PIT classes (equity_highbeta,
                               equity_recent at τ=0.95).
                             - AMM bands match deployed M5 receipts byte-for-byte.

  --forecaster lwc         (M6 LWC Phase 1.5 deliverable)
                           Verify the LWC serving path returns valid
                           PricePoints for SPY, MSTR, HOOD across all four
                           anchors (τ ∈ {0.68, 0.85, 0.95, 0.99}) and all
                           three regimes (normal, long_weekend, high_vol).
                           Picks a sample Friday for each (symbol, regime)
                           combination from the LWC artefact.

Loads the artefact produced by `scripts/build_mondrian_artefact.py` plus
the Lending sidecar (`scripts/build_m6b2_lending_artefact.py`) and the LWC
artefact (`scripts/build_lwc_artefact.py`).
"""

from __future__ import annotations

import argparse
import json

from soothsayer.oracle import (
    C_BUMP_SCHEDULE,
    DELTA_SHIFT_SCHEDULE,
    LENDING_C_BUMP_SCHEDULE,
    LENDING_DELTA_SHIFT_SCHEDULE,
    LENDING_METADATA,
    LENDING_QUANTILE_TABLE,
    LWC_C_BUMP_SCHEDULE,
    LWC_DELTA_SHIFT_SCHEDULE,
    LWC_METADATA,
    LWC_REGIME_QUANTILE_TABLE,
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


def _print_lwc_constants() -> None:
    print(f"M6 (LWC) constants  [{LWC_METADATA.get('methodology_version')}]:")
    print(f"  σ̂_sym window: K={LWC_METADATA.get('sigma_hat', {}).get('K_weekends')} "
          f"weekends, min_past={LWC_METADATA.get('sigma_hat', {}).get('min_past_obs')} obs")
    print(f"  n_train={LWC_METADATA.get('n_train')}  n_oos={LWC_METADATA.get('n_oos')}  "
          f"warmup_dropped={LWC_METADATA.get('n_dropped_warmup')}")
    print("  LWC_REGIME_QUANTILE_TABLE [unitless]:")
    for r, row in LWC_REGIME_QUANTILE_TABLE.items():
        cells = "  ".join(f"τ={t:.2f}: {q:.4f}" for t, q in row.items())
        print(f"    {r:>14}  {cells}")
    print(f"  LWC_C_BUMP_SCHEDULE:      {LWC_C_BUMP_SCHEDULE}")
    print(f"  LWC_DELTA_SHIFT_SCHEDULE: {LWC_DELTA_SHIFT_SCHEDULE}")
    print()


def _smoke_lwc(oracle: Oracle) -> None:
    """Verify fair_value_lwc() returns a valid PricePoint for SPY, MSTR, HOOD
    at every (anchor τ × regime) cell. Picks the most recent artefact row
    per (symbol, regime) so each regime is exercised at least once per
    symbol if available."""
    if not oracle.has_lwc:
        raise RuntimeError(
            "Oracle was loaded without the LWC artefact. Re-run "
            "`Oracle.load(lwc_artefact_path=LWC_ARTEFACT_PATH)` after "
            "`uv run python scripts/build_lwc_artefact.py`."
        )
    lwc = oracle._lwc_artefact  # type: ignore[attr-defined]  -- internal smoke access
    targets = (0.68, 0.85, 0.95, 0.99)
    regimes = ("normal", "long_weekend", "high_vol")
    symbols = ("SPY", "MSTR", "HOOD")

    for symbol in symbols:
        sym_rows = lwc[lwc["symbol"] == symbol]
        if sym_rows.empty:
            print(f"--- {symbol}  (no LWC artefact rows; skipping)\n")
            continue

        # Pick one Friday per regime (latest available) so we exercise each
        # of the three cells that LWC's quantile table covers.
        regime_fridays: dict[str, object] = {}
        for r in regimes:
            sub = sym_rows[sym_rows["regime_pub"] == r]
            if not sub.empty:
                regime_fridays[r] = sub["fri_ts"].iloc[-1]

        print(f"--- {symbol} (class={SYMBOL_CLASS_MAP.get(symbol, '?')})")
        print(f"     {'regime':>14}  {'fri_ts':>12}  {'σ̂':>8}  {'τ':>5}  "
              f"{'point':>10}  {'lower':>10}  {'upper':>10}  {'hw_bps':>8}  {'forecaster':>10}")
        for r in regimes:
            friday = regime_fridays.get(r)
            if friday is None:
                print(f"     {r:>14}  {'(none)':>12}  ──── no artefact rows for this regime ────")
                continue
            for tau in targets:
                pp = oracle.fair_value_lwc(symbol, friday, target_coverage=tau)
                sigma = pp.diagnostics["sigma_hat_sym_pre_fri"]
                print(
                    f"     {r:>14}  {str(friday):>12}  {sigma:>8.5f}  "
                    f"τ={tau:.2f}  {pp.point:>10.4f}  {pp.lower:>10.4f}  "
                    f"{pp.upper:>10.4f}  {pp.half_width_bps:>8.2f}  "
                    f"{pp.forecaster_used:>10}"
                )
        print()

    # Print a sample receipt JSON for the first available (SPY, normal) row
    # so the diagnostics shape is visible.
    spy_normal = lwc[(lwc["symbol"] == "SPY") & (lwc["regime_pub"] == "normal")]
    if not spy_normal.empty:
        friday = spy_normal["fri_ts"].iloc[-1]
        pp = oracle.fair_value_lwc("SPY", friday, target_coverage=0.95)
        print(f"Receipt JSON (LWC, τ=0.95, SPY @ {friday}):")
        print(json.dumps(pp.to_dict(), indent=2, default=str))


def _smoke_dual_profile() -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forecaster",
        choices=("m5", "lwc"),
        default="m5",
        help="m5 = dual-profile (lending + amm) visual diff (default); "
             "lwc = M6 LWC smoke across SPY/MSTR/HOOD × 4 τ × 3 regimes.",
    )
    args = parser.parse_args()

    if args.forecaster == "lwc":
        oracle = Oracle.load(profile="amm")  # profile irrelevant for LWC path
        if not oracle.has_lwc:
            raise SystemExit(
                "LWC artefact not found. Run "
                "`uv run python scripts/build_lwc_artefact.py` first."
            )
        _print_lwc_constants()
        _smoke_lwc(oracle)
    else:
        _smoke_dual_profile()


if __name__ == "__main__":
    main()
