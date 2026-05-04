#!/usr/bin/env bash
# M6 forward-tape harness — Phase 4.4 launchd entrypoint.
#
# Runs once per launchd fire (Tuesday 09:30 local time per the plist):
#   1. Confirm scryer's upstream runners are within their freshness SLA
#      (`internal.scryer/workflow_run/v2`).
#   2. Verify the specific Fri/Mon partitions the forward weekend needs
#      have actually landed (poll-and-wait pre-flight). The SLA check
#      proves "scryer's runners ran recently"; this proves "the rows
#      panel.build() will join on are physically on disk." Without it,
#      a partition-write that lags the harness fire by even a few
#      minutes silently drops the forward weekend (root cause of the
#      2026-05-04 22:15 UTC fire's empty tape).
#   3. Collect the forward tape (re-builds the panel over a 400-day
#      context window, filters to `is_forward = True`).
#   4. Evaluate the frozen LWC artefact on the forward rows.
#   5. Score all 5 σ̂ variants (Phase 5 ladder) on the same forward rows
#      from the frozen variant bundle. §13.6 of m6_sigma_ewma.md — held-
#      out re-validation of the EWMA HL=8 selection. Additive, fails-
#      open: a missing bundle or evaluator error does not affect the
#      canonical step-4 report.
#
# All stdout / stderr is appended to `~/Library/Logs/soothsayer-forward-tape.log`.
# The script does NOT git commit — Adam reviews the produced reports
# manually and decides when to commit (per his "phase-commit" preference).

set -uo pipefail

REPO_DIR="${REPO_DIR:-/Users/adamnoonan/Documents/soothsayer}"
LOG_FILE="${LOG_FILE:-${HOME}/Library/Logs/soothsayer-forward-tape.log}"

mkdir -p "$(dirname "$LOG_FILE")"

cd "$REPO_DIR" || {
    echo "[$(date -u +%FT%TZ)] ERROR: cannot cd to ${REPO_DIR}" >> "$LOG_FILE"
    exit 1
}

# Source ~/.zshrc-equivalent so `uv` is on $PATH under launchd. launchd
# does NOT load shell rc files; we have to find uv ourselves.
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

{
    echo
    echo "============================================================"
    echo "[$(date -u +%FT%TZ)] forward-tape harness fire"
    echo "REPO_DIR=${REPO_DIR}"
    echo "============================================================"

    echo
    echo "[1/4] SLA check on scryer workflow_run.v2 …"
    if ! uv run python scripts/check_scryer_freshness.py; then
        echo "WARN: SLA check failed — continuing anyway. Forward tape may "
        echo "      be incomplete; the evaluator's graceful empty-tape "
        echo "      handling will print 'insufficient data' if so."
    fi

    echo
    echo "[2/4] forward-partition presence pre-flight …"
    uv run python scripts/check_forward_partitions.py
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "ERROR: required partitions not present after wait budget; halting"
        echo "       before build to avoid silently dropping the forward weekend."
        echo "       Next launchd fire will re-check."
        exit "$rc"
    fi

    echo
    echo "[3/4] collect_forward_tape.py …"
    uv run python scripts/collect_forward_tape.py
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "ERROR: collect_forward_tape.py exited $rc"
        exit "$rc"
    fi

    echo
    echo "[4/5] run_forward_tape_evaluation.py …"
    uv run python scripts/run_forward_tape_evaluation.py
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "ERROR: run_forward_tape_evaluation.py exited $rc"
        exit "$rc"
    fi

    echo
    echo "[5/5] run_forward_tape_variant_comparison.py …"
    # Additive — failure here does NOT abort the harness; the canonical
    # step-4 report is the deployment-load-bearing one. The variant
    # comparison is a transparency layer for the §13.6 selection-procedure
    # disclosure and can re-run by hand if it fails.
    uv run python scripts/run_forward_tape_variant_comparison.py
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "WARN: run_forward_tape_variant_comparison.py exited $rc — "
        echo "      canonical step-4 report still landed; rerun by hand."
    fi

    echo
    echo "[$(date -u +%FT%TZ)] harness fire complete"
} >> "$LOG_FILE" 2>&1
