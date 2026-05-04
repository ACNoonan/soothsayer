#!/usr/bin/env bash
# M6 forward-tape harness — Phase 4.4 launchd entrypoint.
#
# Runs once per launchd fire (Tuesday 09:30 local time per the plist):
#   1. Confirm scryer's upstream runners are within their freshness SLA
#      (`internal.scryer/workflow_run/v2`).
#   2. Collect the forward tape (re-builds the panel over a 400-day
#      context window, filters to `is_forward = True`).
#   3. Evaluate the frozen LWC artefact on the forward rows.
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
    echo "[1/3] SLA check on scryer workflow_run.v2 …"
    if ! uv run python scripts/check_scryer_freshness.py; then
        echo "WARN: SLA check failed — continuing anyway. Forward tape may "
        echo "      be incomplete; the evaluator's graceful empty-tape "
        echo "      handling will print 'insufficient data' if so."
    fi

    echo
    echo "[2/3] collect_forward_tape.py …"
    uv run python scripts/collect_forward_tape.py
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "ERROR: collect_forward_tape.py exited $rc"
        exit "$rc"
    fi

    echo
    echo "[3/3] run_forward_tape_evaluation.py …"
    uv run python scripts/run_forward_tape_evaluation.py
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "ERROR: run_forward_tape_evaluation.py exited $rc"
        exit "$rc"
    fi

    echo
    echo "[$(date -u +%FT%TZ)] harness fire complete"
} >> "$LOG_FILE" 2>&1
