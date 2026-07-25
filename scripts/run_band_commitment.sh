#!/usr/bin/env bash
# Pre-open commitment launchd entrypoint.
#
# Modes (first argument):
#   friday   Weekend commitment — σ̂/regime/half-widths per symbol per τ,
#            appended to data/band_archive/commitments_v1.csv. Fired
#            Saturday 19:30 ET (after the ~18:30 cboe-indices run lands
#            Friday's VIX close; CBOE publishes T+1) with a Sunday
#            10:00 ET retry. Both precede Globex reopen Sunday 18:00 ET;
#            the emitter's own guard refuses late writes.
#   monday   Pre-open publication — point from the factor instrument's
#            Monday bar, band = point ± committed half-width, appended
#            to bands_v1.csv with provenance=published_pre_open. Fired
#            Monday 07:30 ET with an 09:05 ET retry; the emitter refuses
#            to write after 09:25 ET.
#
# Both emissions are idempotent (dedup on weekend/symbol/tau/sha), so
# the retry fire is a no-op when the primary succeeded.
#
# Timestamping: if SOOTHSAYER_ARCHIVE_PUSH=1, the archive delta is
# committed and pushed immediately — the public git history is the
# commitment clock. This is the ONE sanctioned exception to the
# "harness never commits" convention, because the push IS the product
# here. Only data/band_archive is ever staged (explicit pathspec), so
# unrelated working-tree changes are never swept in.

set -uo pipefail

MODE="${1:-}"
if [ "$MODE" != "friday" ] && [ "$MODE" != "monday" ]; then
    echo "usage: $0 {friday|monday}" >&2
    exit 2
fi

REPO_DIR="${REPO_DIR:-/Users/adamnoonan/Documents/soothsayer}"
LOG_FILE="${LOG_FILE:-${HOME}/Library/Logs/soothsayer-band-commitment.log}"

mkdir -p "$(dirname "$LOG_FILE")"
cd "$REPO_DIR" || {
    echo "[$(date -u +%FT%TZ)] ERROR: cannot cd to ${REPO_DIR}" >> "$LOG_FILE"
    exit 1
}

# launchd does not load shell rc files; find uv ourselves.
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

{
    echo
    echo "============================================================"
    echo "[$(date -u +%FT%TZ)] band-commitment fire — mode=${MODE}"
    echo "============================================================"

    uv run python scripts/emit_band_commitments.py "$MODE"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "ERROR: emit_band_commitments.py ${MODE} exited ${rc}."
        echo "       Emission is idempotent — the retry fire (or a manual"
        echo "       run) can recover; the retro path covers a full miss."
        exit "$rc"
    fi

    if [ "${SOOTHSAYER_ARCHIVE_PUSH:-0}" = "1" ]; then
        echo "-- timestamping: commit + push data/band_archive --"
        if git diff --quiet -- data/band_archive && \
           [ -z "$(git ls-files --others --exclude-standard data/band_archive)" ]; then
            echo "archive unchanged (dedup no-op) — nothing to timestamp."
        else
            git add data/band_archive
            git commit -m "archive: ${MODE} band-commitment emission $(date -u +%F)" \
                -- data/band_archive
            git pull --rebase --autostash origin main || {
                echo "WARN: pull --rebase failed; local commit retained, push skipped."
                exit 0
            }
            git push origin main || {
                echo "WARN: push failed; local commit retained (timestamp is the"
                echo "      commit; push will carry it on the next successful fire)."
            }
        fi
    else
        echo "SOOTHSAYER_ARCHIVE_PUSH != 1 — rows written locally, not pushed."
        echo "Adam commits/pushes manually (the push is the public timestamp)."
    fi

    echo "[$(date -u +%FT%TZ)] band-commitment fire complete"
} >> "$LOG_FILE" 2>&1
