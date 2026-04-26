#!/usr/bin/env bash
# Soothsayer — Kamino xStocks weekly rollup (launchd entry point)
#
# Runs every Monday at 10:30 local time via
# ~/Library/LaunchAgents/com.soothsayer.kamino-weekly-rollup.plist.
# Replaces the cloud routine (trig_01DCnXffiXhbed8W8aYqi3rt) which lacked
# access to local V5/Scope tape data and had to fall back to the public
# Solana RPC. Running locally we get full-fidelity tape data and the
# repo's .env-loaded Helius/RPC Fast keys.
#
# Pipeline (idempotent, safe to re-run):
#   1. git pull --rebase origin main
#   2. snapshot_kamino_xstocks.py        → data/processed/kamino_xstocks_snapshot_YYYYMMDD.json
#   3. score_weekend_comparison.py       → data/processed/weekend_comparison_YYYYMMDD.json
#   4. render_weekend_report.py          → reports/.../weekend_YYYYMMDD.md + landing/.html
#   5. stage outputs (idl + reports + landing fragment; never data/processed/*)
#   6. conditional commit (skip if no staged changes)
#   7. git push origin main
#
# All output is tee'd to /tmp/kamino_rollup.log for after-the-fact triage.
# launchd captures stdout / stderr separately to /tmp/kamino_rollup.{stdout,stderr}.log.

set -euo pipefail

REPO_ROOT="/Users/adamnoonan/Documents/soothsayer"
LOG="/tmp/kamino_rollup.log"

cd "$REPO_ROOT"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }

log "=== Kamino xStocks weekly rollup starting ==="
log "  cwd: $(pwd)"
log "  uv:  $(command -v uv) ($(uv --version 2>&1))"
log "  git: $(command -v git) ($(git --version))"

# --- 1. Sync with origin -----------------------------------------------------
log "[1/7] git pull --rebase origin main"
git pull --rebase origin main 2>&1 | tee -a "$LOG"

# --- 2. Refresh on-chain Kamino reserve snapshot -----------------------------
log "[2/7] snapshot Kamino xStock reserves"
uv run python scripts/snapshot_kamino_xstocks.py 2>&1 | tee -a "$LOG"

# --- 3. Score the most-recent-completed weekend ------------------------------
log "[3/7] score weekend (auto-picks latest Friday whose Monday is in the past)"
uv run python scripts/score_weekend_comparison.py 2>&1 | tee -a "$LOG"

# --- 4. Render the report ----------------------------------------------------
log "[4/7] render markdown + HTML report"
uv run python scripts/render_weekend_report.py 2>&1 | tee -a "$LOG"

# --- 5. Stage outputs (intentionally NOT data/processed/* — gitignored) ------
log "[5/7] stage outputs"
git add reports/kamino_xstocks_weekend_*.md \
        landing/kamino_xstocks_weekend_fragment.html \
        idl/kamino/klend.json \
        idl/kamino/scope.json 2>&1 | tee -a "$LOG"

# --- 6. Conditional commit ---------------------------------------------------
if git diff --cached --quiet; then
    log "[6/7] no staged changes — skipping commit + push"
    log "=== rollup done (no-op) ==="
    exit 0
fi

LATEST_JSON=$(ls -t data/processed/weekend_comparison_*.json | head -1)
log "[6/7] committing — message body sourced from $LATEST_JSON"

# Build the commit message body via a Python helper that reads the scored JSON.
COMMIT_MSG=$(uv run python scripts/_compose_kamino_rollup_message.py "$LATEST_JSON")
git commit -m "$COMMIT_MSG" 2>&1 | tee -a "$LOG"

# --- 7. Push to origin -------------------------------------------------------
log "[7/7] git push origin main"
if git push origin main 2>&1 | tee -a "$LOG"; then
    log "=== rollup done ==="
else
    log "PUSH FAILED — local commit preserved; investigate, then re-run \`git push\`"
    exit 1
fi
