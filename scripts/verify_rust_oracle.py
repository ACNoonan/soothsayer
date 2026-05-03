"""
Rust ↔ Python Oracle parity check (Mondrian / M5 deployment).

For a random sample of (symbol, fri_ts) tuples from the M5 artefact, call
both the Python `Oracle.fair_value` and the Rust `soothsayer fair-value` CLI
and diff the key fields. The expectation is byte-exact agreement on the
numeric output (point, lower, upper, sharpness_bps, claimed_served) and
exact agreement on the string fields (regime, forecaster_used).

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
ARTEFACT_PATH = REPO_ROOT / "data" / "processed" / "mondrian_artefact_v2.parquet"

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
DIAGNOSTIC_NUMERIC = [
    "fri_close",
    "served_target",
    "c_bump",
    "q_regime",
    "q_eff",
]
DIAGNOSTIC_STRING: list[str] = []


def rust_bin() -> Path:
    if RUST_BIN_RELEASE.exists():
        return RUST_BIN_RELEASE
    return RUST_BIN_DEBUG


def run_rust(symbol: str, as_of: str, target: float) -> dict:
    out = subprocess.run(
        [str(rust_bin()), "fair-value",
         "--symbol", symbol, "--as-of", as_of, "--target", str(target)],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def run_python(oracle: Oracle, symbol: str, as_of: str, target: float) -> dict:
    pp = oracle.fair_value(symbol, as_of, target_coverage=target)
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


def compare(py: dict, rs: dict) -> list[str]:
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
    for f in DIAGNOSTIC_NUMERIC:
        mismatches += diff_fields(f"diag.{f}", py_d.get(f), rs_d.get(f), tol=NUMERIC_TOL)
    for f in DIAGNOSTIC_STRING:
        mismatches += diff_fields(f"diag.{f}", py_d.get(f), rs_d.get(f))

    return mismatches


def main() -> int:
    if not rust_bin().exists():
        print(f"Rust binary not found at {rust_bin()}")
        print("Run: cargo build -p soothsayer-publisher")
        return 2

    artefact = pd.read_parquet(ARTEFACT_PATH)
    unique = artefact[["symbol", "fri_ts"]].drop_duplicates().reset_index(drop=True)
    print(f"Artefact rows: {len(artefact):,} total, {len(unique):,} unique (symbol, fri_ts)")
    print(f"Rust binary: {rust_bin()}")
    print()

    oracle = Oracle.load()

    # Deterministic sample: 10 across various regimes, times, symbols
    random.seed(42)
    n_cases = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    sample = unique.sample(n=n_cases, random_state=42).reset_index(drop=True)

    # Test a few edge cases deterministically too
    edge_cases = []
    for symbol in ["SPY", "GLD", "TLT", "MSTR", "HOOD"]:
        sub = unique[unique["symbol"] == symbol]
        if not sub.empty:
            # Recent Friday (likely high-vol or normal)
            edge_cases.append((symbol, sub["fri_ts"].sort_values().iloc[-1]))

    all_cases = [(row["symbol"], str(row["fri_ts"])) for _, row in sample.iterrows()]
    all_cases += [(s, str(d)) for s, d in edge_cases]

    target_coverages = [0.68, 0.95, 0.99]
    total = len(all_cases) * len(target_coverages)
    print(f"Testing {len(all_cases)} (symbol, fri_ts) pairs × {len(target_coverages)} targets = {total} cases")
    print()

    total_mismatches = 0
    cases_with_mismatch = 0

    for i, (symbol, as_of) in enumerate(all_cases):
        for tc in target_coverages:
            try:
                py = run_python(oracle, symbol, as_of, tc)
                rs = run_rust(symbol, as_of, tc)
            except Exception as e:
                print(f"  {symbol:<6} {as_of} target={tc}  ERROR: {e}")
                total_mismatches += 1
                continue
            m = compare(py, rs)
            if m:
                cases_with_mismatch += 1
                total_mismatches += len(m)
                print(f"  {symbol:<6} {as_of} target={tc:.2f}  MISMATCH ({len(m)}):")
                for line in m:
                    print(line)
            else:
                # success — print concise OK line
                if (i * len(target_coverages)) % 10 == 0 and tc == target_coverages[0]:
                    py_hw = py["half_width_bps"]
                    print(f"  {symbol:<6} {as_of} regime={py['regime']:<12} fc={py['forecaster_used']:<15}  target={tc:.2f}→claim={py['claimed_coverage_served']:.3f} hw={py_hw:5.0f}bps  ✓")

    print()
    print("=" * 60)
    if total_mismatches == 0:
        print(f"PASS: all {total} cases match byte-for-byte ✓")
        return 0
    else:
        print(f"FAIL: {cases_with_mismatch}/{total} cases had mismatches, {total_mismatches} total field differences")
        return 1


if __name__ == "__main__":
    sys.exit(main())
