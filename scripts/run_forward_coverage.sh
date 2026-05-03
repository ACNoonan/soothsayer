#!/usr/bin/env bash
# Soothsayer — W5 live forward-tape coverage (launchd entry point).
#
# Runs every Tuesday at 09:00 local time via
# ~/Library/LaunchAgents/com.soothsayer.forward-coverage.plist. By that time
# Yahoo's `equities_daily/v1` Monday-open cron has landed (SLA ~14:30 UTC,
# i.e. ~07:30 PDT), so the most-recent weekend (last fri → last mon) is
# evaluable.
#
# Pipeline (idempotent, safe to re-run):
#   1. log uv / git versions
#   2. uv run python scripts/run_forward_coverage.py
#        - rebuilds panel from scryer for 2024-01-01 → today
#        - cross-checks 3 historical rows against frozen v1b_panel.parquet
#        - emits data/processed/v1b_forward_coverage.parquet (if n>0)
#        - emits reports/v1b_forward_coverage.md (always)
#
# Intentionally does NOT auto-commit. Forward sample is small at first; a
# single miss can swing the τ=0.95 headline by tens of percentage points, so
# Adam reviews + commits manually after each weekly run.
#
# Logs:
#   /tmp/soothsayer_forward_coverage.log         tee'd from this wrapper
#   /tmp/soothsayer_forward_coverage.stdout.log  launchd-captured stdout
#   /tmp/soothsayer_forward_coverage.stderr.log  launchd-captured stderr

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="/tmp/soothsayer_forward_coverage.log"

cd "$REPO_ROOT"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }

log "=== Soothsayer forward-coverage runner starting ==="
log "  cwd: $(pwd)"
log "  uv:  $(command -v uv) ($(uv --version 2>&1))"
log "  git: $(command -v git) ($(git --version))"

log "[1/1] uv run python scripts/run_forward_coverage.py"
uv run python scripts/run_forward_coverage.py 2>&1 | tee -a "$LOG"

log "=== forward-coverage runner done ==="
