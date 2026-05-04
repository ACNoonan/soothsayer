"""
SLA pre-check for the M6 forward-tape harness — Phase 4.4 belt-and-braces.

Reads `internal.scryer/workflow_run/v2` and confirms each runner the
forward-tape harness depends on has a *recent* `succeeded` run. Prints a
short summary and exits 0 if all good, 1 if any runner is stale or
failing. The launchd plist's wrapper script invokes this before
`collect_forward_tape.py` so an obviously-broken upstream is caught
before the collector silently produces an empty tape.

Manifests we care about (mapping to the panel symbols they refresh):
  equities-daily      — yahoo daily bars for 11 forward-polled symbols
  earnings            — yahoo earnings calendar for 6 single-name tickers
  cme-intraday-1m     — CME 1m bars for ES=F, NQ=F, GC=F, ZN=F
  cboe-indices        — CBOE daily indices for VIX (and friends)

SLA: default 26h since last `succeeded` run. The agent's 25h freshness
SLAs sit one hour shy of this so the harness alerts on borderline-late
runs.

Run
---
  uv run python scripts/check_scryer_freshness.py
  uv run python scripts/check_scryer_freshness.py --sla-hours 48

Exit code 0 = all good; 1 = at least one runner stale or failing.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


SCRYER_ROOT = Path(os.path.expanduser(
    "~/Library/Application Support/scryer/dataset"
))
WORKFLOW_RUN_DIR = SCRYER_ROOT / "internal.scryer" / "workflow_run" / "v2"
RELEVANT_MANIFESTS = (
    "equities-daily",
    "earnings",
    "cme-intraday-1m",
    "cboe-indices",
)
DEFAULT_SLA_HOURS = 26


def _recent_workflow_run_files(now: datetime, days: int = 5) -> list[Path]:
    """Return the last `days` daily partition files of workflow_run/v2,
    skipping ones that don't exist."""
    out: list[Path] = []
    for i in range(days):
        d = (now - timedelta(days=i)).date()
        p = (WORKFLOW_RUN_DIR /
             f"year={d.year:04d}" / f"month={d.month:02d}" /
             f"day={d.day:02d}.parquet")
        if p.exists():
            out.append(p)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sla-hours", type=int, default=DEFAULT_SLA_HOURS,
                        help="SLA window in hours since last succeeded run "
                             "(default 26).")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress success summary; only print on failure.")
    args = parser.parse_args()

    if not WORKFLOW_RUN_DIR.exists():
        print(f"WARN  workflow_run table not found at {WORKFLOW_RUN_DIR}; "
              "skipping SLA check.", file=sys.stderr)
        sys.exit(0)

    now = datetime.now(timezone.utc)
    files = _recent_workflow_run_files(now)
    if not files:
        print(f"WARN  no recent workflow_run partitions found under "
              f"{WORKFLOW_RUN_DIR}; cannot verify SLA.", file=sys.stderr)
        sys.exit(0)

    df = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    df = df[df["manifest_id"].isin(RELEVANT_MANIFESTS)].copy()
    if df.empty:
        print(f"WARN  no rows for the relevant manifests "
              f"({list(RELEVANT_MANIFESTS)}) in the last 5 days. "
              "scryer may not be running these runners on this host.",
              file=sys.stderr)
        sys.exit(1)

    sla_cutoff_unix = int((now - timedelta(hours=args.sla_hours)).timestamp())

    failures: list[str] = []
    rows: list[dict] = []
    for manifest in RELEVANT_MANIFESTS:
        sub = df[df["manifest_id"] == manifest]
        if sub.empty:
            failures.append(f"{manifest}: no runs in the last 5 days")
            rows.append({"manifest": manifest, "status": "MISSING",
                         "last_succeeded": "—", "age_hours": float("inf")})
            continue
        succeeded = sub[sub["status"] == "succeeded"]
        if succeeded.empty:
            failures.append(f"{manifest}: no SUCCEEDED runs in the last 5 days")
            rows.append({"manifest": manifest, "status": "ALL FAILED",
                         "last_succeeded": "—", "age_hours": float("inf")})
            continue
        last_unix = int(succeeded["finished_at_unix_secs"].max())
        last_dt = datetime.fromtimestamp(last_unix, tz=timezone.utc)
        age_hours = (now - last_dt).total_seconds() / 3600
        if last_unix < sla_cutoff_unix:
            failures.append(
                f"{manifest}: last succeeded run was "
                f"{last_dt.isoformat()} ({age_hours:.1f}h ago > "
                f"{args.sla_hours}h SLA)"
            )
            status = "STALE"
        else:
            status = "OK"
        rows.append({"manifest": manifest, "status": status,
                     "last_succeeded": last_dt.strftime("%Y-%m-%d %H:%M UTC"),
                     "age_hours": round(age_hours, 2)})

    summary = pd.DataFrame(rows)
    if failures:
        print("SLA check FAILED:", file=sys.stderr)
        print(summary.to_string(index=False), file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"SLA check OK (SLA = {args.sla_hours}h)")
        print(summary.to_string(index=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
