"""
Rust ↔ Python Oracle parity check — dual-forecaster (M5 Mondrian + M6 LWC).

For a deterministic sample of (symbol, fri_ts) tuples from each forecaster's
artefact, call both the Python `Oracle.fair_value` (M5) / `Oracle.fair_value_lwc`
(M6) and the Rust `soothsayer fair-value` CLI under each forecaster, and diff
the key fields. The expectation is byte-exact agreement on the consumer-facing
numeric output (point, lower, upper, sharpness_bps, claimed_served) and exact
agreement on string fields (regime, forecaster_used).

Target: **180/180 pass** (90 M5 + 90 M6, each = 30 (symbol, fri_ts) cases × 3
target-coverage anchors).

Run:
    cargo build --release -p soothsayer-publisher
    PYTHONUNBUFFERED=1 uv run python scripts/verify_rust_oracle.py
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
from soothsayer.oracle import Oracle  # noqa: E402


RUST_BIN_DEBUG = REPO_ROOT / "target" / "debug" / "soothsayer"
RUST_BIN_RELEASE = REPO_ROOT / "target" / "release" / "soothsayer"

ARTEFACT_PATHS = {
    "mondrian": REPO_ROOT / "data" / "processed" / "mondrian_artefact_v2.parquet",
    "lwc":      REPO_ROOT / "data" / "processed" / "lwc_artefact_v1.parquet",
}

# Fields we require to match exactly (numeric = bit-level; string = exact).
NUMERIC_FIELDS = [
    "target_coverage",
    "calibration_buffer_applied",
    "claimed_coverage_served",
    "point",
    "lower",
    "upper",
    "sharpness_bps",
    "half_width_bps",
]
STRING_FIELDS = [
    "symbol",
    "forecaster_used",
    # regime is serialised as snake_case by both
]
DIAGNOSTIC_NUMERIC_COMMON = [
    "fri_close",
    "served_target",
    "c_bump",
    "q_eff",
]
DIAGNOSTIC_NUMERIC_BY_FORECASTER = {
    "mondrian": ["q_regime"],
    "lwc": ["q_regime_lwc", "sigma_hat_sym_pre_fri"],
}


def rust_bin() -> Path:
    if RUST_BIN_RELEASE.exists():
        return RUST_BIN_RELEASE
    return RUST_BIN_DEBUG


def run_rust(symbol: str, as_of: str, target: float, forecaster: str) -> dict:
    out = subprocess.run(
        [str(rust_bin()), "--forecaster", forecaster, "fair-value",
         "--symbol", symbol, "--as-of", as_of, "--target", str(target)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def run_python(oracle: Oracle, symbol: str, as_of: str, target: float,
               forecaster: str) -> dict:
    if forecaster == "mondrian":
        pp = oracle.fair_value(symbol, as_of, target_coverage=target)
    elif forecaster == "lwc":
        pp = oracle.fair_value_lwc(symbol, as_of, target_coverage=target)
    else:
        raise ValueError(f"unknown forecaster: {forecaster!r}")
    return pp.to_dict()


def _normalize(v):
    """Normalize for comparison: tuples ↔ lists, nested recursion."""
    if isinstance(v, tuple):
        return [_normalize(x) for x in v]
    if isinstance(v, list):
        return [_normalize(x) for x in v]
    return v


# Numeric tolerance. Equal algorithm on different compilers / orderings can
# differ by ≤1 ULP (~2e-16 for f64). Use a safe 1e-12 margin.
NUMERIC_TOL = 1e-12


def diff_fields(label: str, py_val, rs_val, tol: float | None = NUMERIC_TOL) -> list[str]:
    py_val = _normalize(py_val)
    rs_val = _normalize(rs_val)

    # Element-wise tolerance for lists of numbers
    if isinstance(py_val, list) and isinstance(rs_val, list) and len(py_val) == len(rs_val):
        if all(
            isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= (tol or 0)
            for a, b in zip(py_val, rs_val)
        ):
            return []

    if tol is not None and isinstance(py_val, (int, float)) and isinstance(rs_val, (int, float)):
        if abs(py_val - rs_val) <= tol:
            return []
        return [f"    {label}: py={py_val!r} rs={rs_val!r} Δ={py_val - rs_val:+.3e}"]
    if py_val != rs_val:
        return [f"    {label}: py={py_val!r} rs={rs_val!r}"]
    return []


def compare(py: dict, rs: dict, forecaster: str) -> list[str]:
    mismatches = []

    # Consumer-facing numeric fields must match bit-for-bit (tol=0).
    for f in NUMERIC_FIELDS:
        mismatches += diff_fields(f, py.get(f), rs.get(f), tol=0.0)
    for f in STRING_FIELDS:
        mismatches += diff_fields(f, py.get(f), rs.get(f))
    mismatches += diff_fields("regime", py.get("regime"), rs.get("regime"))
    mismatches += diff_fields("as_of", py.get("as_of"), rs.get("as_of"))

    # Diagnostic numeric fields: allow ≤1e-12 (ULP noise from op ordering).
    py_d = py.get("diagnostics", {})
    rs_d = rs.get("diagnostics", {})
    for f in DIAGNOSTIC_NUMERIC_COMMON + DIAGNOSTIC_NUMERIC_BY_FORECASTER[forecaster]:
        mismatches += diff_fields(f"diag.{f}", py_d.get(f), rs_d.get(f), tol=NUMERIC_TOL)

    return mismatches


def _build_case_list(unique: pd.DataFrame, n_random: int) -> list[tuple[str, str]]:
    """Deterministic random sample + per-symbol latest-Friday edge cases."""
    random.seed(42)
    sample = unique.sample(n=n_random, random_state=42).reset_index(drop=True)
    edge_cases = []
    for symbol in ["SPY", "GLD", "TLT", "MSTR", "HOOD"]:
        sub = unique[unique["symbol"] == symbol]
        if not sub.empty:
            edge_cases.append((symbol, sub["fri_ts"].sort_values().iloc[-1]))
    cases = [(row["symbol"], str(row["fri_ts"])) for _, row in sample.iterrows()]
    cases += [(s, str(d)) for s, d in edge_cases]
    return cases


def _run_forecaster(forecaster: str, n_random: int,
                    target_coverages: list[float]) -> tuple[int, int, int]:
    """Run parity for one forecaster. Returns (cases_total, cases_with_mismatch,
    total_field_diffs)."""
    print(f"=== forecaster={forecaster} ===")

    artefact_path = ARTEFACT_PATHS[forecaster]
    if not artefact_path.exists():
        print(f"  SKIP: artefact {artefact_path} not present "
              f"(run scripts/build_{'lwc' if forecaster == 'lwc' else 'mondrian'}_artefact.py)")
        return 0, 0, 0

    artefact = pd.read_parquet(artefact_path)
    unique = artefact[["symbol", "fri_ts"]].drop_duplicates().reset_index(drop=True)
    print(f"  artefact rows: {len(artefact):,} total, {len(unique):,} unique (symbol, fri_ts)")

    all_cases = _build_case_list(unique, n_random)
    print(f"  testing {len(all_cases)} cases × {len(target_coverages)} targets = "
          f"{len(all_cases) * len(target_coverages)} combinations")

    # Python oracle: load with the M5 per-regime "amm" profile for the
    # Mondrian parity probe (Python's default profile is "lending" /
    # M6b2 per-class, which Rust no longer exposes — Option A drops the
    # M6b2 Lending profile from the Rust path). For LWC the profile arg
    # is moot — fair_value_lwc bypasses the M5/M6b2 dispatch entirely
    # and reads the LWC artefact via the auto-loaded slot.
    oracle = Oracle.load(profile="amm" if forecaster == "mondrian" else "lending")

    total = len(all_cases) * len(target_coverages)
    total_mismatches = 0
    cases_with_mismatch = 0
    for i, (symbol, as_of) in enumerate(all_cases):
        for tc in target_coverages:
            try:
                py = run_python(oracle, symbol, as_of, tc, forecaster)
                rs = run_rust(symbol, as_of, tc, forecaster)
            except Exception as e:
                print(f"    {symbol:<6} {as_of} target={tc}  ERROR: {e}")
                total_mismatches += 1
                continue
            m = compare(py, rs, forecaster)
            if m:
                cases_with_mismatch += 1
                total_mismatches += len(m)
                print(f"    {symbol:<6} {as_of} target={tc:.2f}  MISMATCH ({len(m)}):")
                for line in m:
                    print(line)
            else:
                if (i * len(target_coverages)) % 30 == 0 and tc == target_coverages[0]:
                    py_hw = py["half_width_bps"]
                    print(f"    {symbol:<6} {as_of} regime={py['regime']:<14} "
                          f"target={tc:.2f}→claim={py['claimed_coverage_served']:.3f} "
                          f"hw={py_hw:5.0f}bps  ✓")
    return total, cases_with_mismatch, total_mismatches


def main() -> int:
    if not rust_bin().exists():
        print(f"Rust binary not found at {rust_bin()}")
        print("Run: cargo build --release -p soothsayer-publisher")
        return 2

    n_random = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    target_coverages = [0.68, 0.95, 0.99]
    print(f"Rust binary: {rust_bin()}")
    print(f"Cases per forecaster: {n_random + 5} unique (symbol, fri_ts) × "
          f"{len(target_coverages)} targets = {(n_random + 5) * len(target_coverages)}")
    print()

    summary = {}
    for forecaster in ("mondrian", "lwc"):
        total, cases_with_mm, field_diffs = _run_forecaster(
            forecaster, n_random, target_coverages
        )
        summary[forecaster] = (total, cases_with_mm, field_diffs)
        print()

    print("=" * 60)
    grand_pass = True
    grand_total = 0
    grand_passed = 0
    for forecaster, (total, cases_with_mm, field_diffs) in summary.items():
        passed = total - cases_with_mm
        status = "PASS" if field_diffs == 0 and total > 0 else \
                 "SKIP" if total == 0 else "FAIL"
        if field_diffs:
            grand_pass = False
        grand_total += total
        grand_passed += passed
        print(f"  forecaster={forecaster:<10}  {passed}/{total}  ({status})")
    print(f"  {'GRAND TOTAL':<23}  {grand_passed}/{grand_total}")
    print("=" * 60)
    return 0 if grand_pass else 1


if __name__ == "__main__":
    sys.exit(main())
