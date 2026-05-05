"""
Rust ↔ Python Oracle parity check — dual-profile (M5 + M6b2 Lending).

For a random sample of (symbol, fri_ts) tuples from the Mondrian artefact,
call both the Python `Oracle.fair_value` and the Rust `soothsayer fair-value`
CLI under each profile (`lending`, `amm`) and diff the key fields. The
expectation is byte-exact agreement on the consumer-facing numeric output
(point, lower, upper, sharpness_bps, claimed_served) and exact agreement on
the string fields (regime, forecaster_used, profile).

Phase A3 target (reports/active/m6_refactor.md): 90/90 per profile.

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
DIAGNOSTIC_NUMERIC_COMMON = [
    "fri_close",
    "served_target",
    "c_bump",
    "q_eff",
]
DIAGNOSTIC_NUMERIC_BY_PROFILE = {
    "amm": ["q_regime"],
    "lending": ["b_class"],
}
DIAGNOSTIC_STRING_BY_PROFILE = {
    "amm": [],
    "lending": ["symbol_class"],
}


def rust_bin() -> Path:
    if RUST_BIN_RELEASE.exists():
        return RUST_BIN_RELEASE
    return RUST_BIN_DEBUG


def run_rust(symbol: str, as_of: str, target: float, profile: str) -> dict:
    out = subprocess.run(
        [str(rust_bin()), "--profile", profile, "fair-value",
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


def compare(py: dict, rs: dict, profile: str) -> list[str]:
    mismatches = []

    # Consumer-facing numeric fields must match bit-for-bit (tol=0).
    for f in NUMERIC_FIELDS:
        mismatches += diff_fields(f, py.get(f), rs.get(f), tol=0.0)
    for f in STRING_FIELDS:
        mismatches += diff_fields(f, py.get(f), rs.get(f))
    mismatches += diff_fields("regime", py.get("regime"), rs.get("regime"))
    mismatches += diff_fields("as_of", py.get("as_of"), rs.get("as_of"))
    mismatches += diff_fields("profile", py.get("profile"), rs.get("profile"))

    # Diagnostic numeric fields: allow ≤1e-12 (ULP noise from op ordering).
    py_d = py.get("diagnostics", {})
    rs_d = rs.get("diagnostics", {})
    for f in DIAGNOSTIC_NUMERIC_COMMON + DIAGNOSTIC_NUMERIC_BY_PROFILE[profile]:
        mismatches += diff_fields(f"diag.{f}", py_d.get(f), rs_d.get(f), tol=NUMERIC_TOL)
    for f in DIAGNOSTIC_STRING_BY_PROFILE[profile]:
        mismatches += diff_fields(f"diag.{f}", py_d.get(f), rs_d.get(f))

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


def _run_profile(profile: str, all_cases: list[tuple[str, str]],
                 target_coverages: list[float]) -> tuple[int, int, int]:
    """Run parity for one profile. Returns (cases_total, cases_with_mismatch,
    total_field_diffs)."""
    print(f"=== profile={profile} ===")
    oracle = Oracle.load(profile=profile)
    total = len(all_cases) * len(target_coverages)
    total_mismatches = 0
    cases_with_mismatch = 0
    for i, (symbol, as_of) in enumerate(all_cases):
        for tc in target_coverages:
            try:
                py = run_python(oracle, symbol, as_of, tc)
                rs = run_rust(symbol, as_of, tc, profile)
            except Exception as e:
                print(f"  {symbol:<6} {as_of} target={tc}  ERROR: {e}")
                total_mismatches += 1
                continue
            m = compare(py, rs, profile)
            if m:
                cases_with_mismatch += 1
                total_mismatches += len(m)
                print(f"  {symbol:<6} {as_of} target={tc:.2f}  MISMATCH ({len(m)}):")
                for line in m:
                    print(line)
            else:
                if (i * len(target_coverages)) % 30 == 0 and tc == target_coverages[0]:
                    py_hw = py["half_width_bps"]
                    cell = py["diagnostics"].get("symbol_class") or py["regime"]
                    print(f"  {symbol:<6} {as_of} cell={cell:<14} target={tc:.2f}"
                          f"→claim={py['claimed_coverage_served']:.3f} hw={py_hw:5.0f}bps  ✓")
    return total, cases_with_mismatch, total_mismatches


def main() -> int:
    if not rust_bin().exists():
        print(f"Rust binary not found at {rust_bin()}")
        print("Run: cargo build --release -p soothsayer-publisher")
        return 2

    artefact = pd.read_parquet(ARTEFACT_PATH)
    unique = artefact[["symbol", "fri_ts"]].drop_duplicates().reset_index(drop=True)
    print(f"Artefact rows: {len(artefact):,} total, {len(unique):,} unique (symbol, fri_ts)")
    print(f"Rust binary: {rust_bin()}")
    print()

    # Phase A3 target: 90/90 per profile. 30 cases × 3 anchors = 90.
    n_random = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    all_cases = _build_case_list(unique, n_random)
    target_coverages = [0.68, 0.95, 0.99]
    print(f"Testing {len(all_cases)} (symbol, fri_ts) pairs × "
          f"{len(target_coverages)} targets = {len(all_cases)*len(target_coverages)} "
          f"cases per profile")
    print()

    summary = {}
    for profile in ("amm", "lending"):
        total, cases_with_mm, field_diffs = _run_profile(profile, all_cases, target_coverages)
        summary[profile] = (total, cases_with_mm, field_diffs)
        print()

    print("=" * 60)
    grand_pass = True
    for profile, (total, cases_with_mm, field_diffs) in summary.items():
        passed = total - cases_with_mm
        status = "PASS" if field_diffs == 0 else "FAIL"
        if field_diffs:
            grand_pass = False
        print(f"  profile={profile:<8}  {passed}/{total}  ({status})")
    print("=" * 60)
    return 0 if grand_pass else 1


if __name__ == "__main__":
    sys.exit(main())
