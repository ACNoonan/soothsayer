"""
Collect forward-tape rows for the M6 LWC harness — Phase 4.2.

Reads the frozen LWC artefact, identifies its training cutoff (the max
`fri_ts` baked into the frozen parquet), and rebuilds the v1b panel
over a window that spans `[cutoff - σ̂-context, today]` via
`soothsayer.backtest.panel.build()`. Persists every row with an
`is_forward` flag (True if `fri_ts > cutoff`); downstream evaluators
filter on the flag.

Why we persist context rows alongside the forward rows: σ̂_sym(F) for
a forward weekend F is the trailing-26-weekend std of relative
residuals for that symbol — its window includes ~26 *training-period*
weekends from before the cutoff. The frozen artefact only stores σ̂
values; recomputing for forward rows requires the underlying rel_resids
(which need `mon_open`, `fri_close`, `factor_ret` from the panel). So
the collector pulls a context window of ≥ 220 days so the evaluator
can recompute σ̂ correctly on forward rows.

Per CLAUDE.md hard rule #1, this script does not fetch upstream data —
`panel.build()` reads `yahoo/equities_daily/v1`, `yahoo/earnings/v1`,
and the auxiliary scryer surfaces it always reads. The forward-tape
harness's progress is therefore bounded by scryer's refresh cadence.

Behaviour
---------
- Empty forward set (no `is_forward = True` rows): the file is still
  written with the context-only rows so the evaluator's parquet
  contract is stable; the evaluator detects 0 forward rows and exits
  with "insufficient data".
- Per-row dropna in `panel.build()` excludes weekends with missing
  exogenous data (futures, vol indices). Until scryer's G1.b ships
  forward polling for those symbols, post-cutoff weekends are silently
  filtered out and the harness fires no-op week after week.

Outputs
-------
  data/processed/forward_tape_v1.parquet   (written every run)
  prints a small summary to stdout

Run
---
  uv run python scripts/collect_forward_tape.py
  uv run python scripts/collect_forward_tape.py --frozen-suffix 20260504
  uv run python scripts/collect_forward_tape.py --context-days 240
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from soothsayer.backtest import regimes
from soothsayer.backtest.panel import PanelSpec, build as build_panel
from soothsayer.config import DATA_PROCESSED


FORWARD_TAPE_PATH = DATA_PROCESSED / "forward_tape_v1.parquet"
SCHEMA_VERSION = "forward_tape.v1"
# 400 days ≈ 57 weekends. Safely larger than two windows that the
# downstream evaluator needs:
#   1. σ̂_sym(t) trailing K=26 weekends (~ 182 days)
#   2. regimes._high_vol_flag rolling 52-week VIX 75th percentile (~ 365 days)
# A 400-day context keeps both stable for the first forward weekend.
DEFAULT_CONTEXT_DAYS = 400


def _find_frozen_artefact(suffix: str | None) -> tuple[Path, Path, dict]:
    """Locate the frozen LWC artefact JSON + parquet pair. If `suffix` is
    None, picks the most recent `lwc_artefact_v1_frozen_*.json`."""
    if suffix is not None:
        json_path = DATA_PROCESSED / f"lwc_artefact_v1_frozen_{suffix}.json"
        parquet_path = DATA_PROCESSED / f"lwc_artefact_v1_frozen_{suffix}.parquet"
        if not json_path.exists():
            raise FileNotFoundError(f"Frozen artefact not found: {json_path}")
    else:
        candidates = sorted(DATA_PROCESSED.glob("lwc_artefact_v1_frozen_*.json"))
        if not candidates:
            raise FileNotFoundError(
                "No frozen artefact found. Run "
                "`uv run python scripts/freeze_lwc_artefact.py` first."
            )
        json_path = candidates[-1]
        # Match the parquet by stripping the JSON suffix.
        parquet_path = json_path.with_suffix(".parquet")
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Frozen parquet missing for {json_path.name}: {parquet_path}"
        )
    sidecar = json.loads(json_path.read_text())
    return json_path, parquet_path, sidecar


def _training_cutoff(frozen_parquet: Path) -> date:
    """Max fri_ts across all symbols in the frozen parquet. Anything strictly
    after this is a forward weekend."""
    df = pd.read_parquet(frozen_parquet)
    fri_ts = pd.to_datetime(df["fri_ts"]).dt.date
    return fri_ts.max()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frozen-suffix",
        default=None,
        help="YYYYMMDD suffix of the frozen artefact (defaults to latest).",
    )
    parser.add_argument(
        "--context-days",
        type=int,
        default=DEFAULT_CONTEXT_DAYS,
        help=("Days of context (training-period) history to include before "
              "the cutoff. Must exceed the σ̂_sym K=26 weekend window "
              "(~182 days)."),
    )
    args = parser.parse_args()

    frozen_json, frozen_parquet, sidecar = _find_frozen_artefact(args.frozen_suffix)
    cutoff = _training_cutoff(frozen_parquet)
    today = date.today()
    start = cutoff - timedelta(days=args.context_days)

    print(f"[1/3] Frozen artefact: {frozen_json.name}")
    print(f"      training cutoff (max fri_ts in frozen): {cutoff}")
    print(f"      sha256: {sidecar.get('_artefact_sha256', '<unknown>')}")
    print(f"      panel build window: {start} → {today}  "
          f"(context={args.context_days} days)", flush=True)

    print(f"[2/3] Building panel via soothsayer.backtest.panel.build()…",
          flush=True)
    spec = PanelSpec(start=start, end=today)
    panel = build_panel(spec)

    # `panel.build()` doesn't tag regimes — that's a separate
    # `regimes.tag()` call. The training panel (`v1b_panel.parquet`)
    # was tagged the same way, so applying it here keeps the cell
    # axis consistent with the frozen artefact.
    panel = regimes.tag(panel)

    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    panel["is_forward"] = panel["fri_ts"] > cutoff
    n_forward = int(panel["is_forward"].sum())
    n_context = int((~panel["is_forward"]).sum())

    print(f"      panel built: {len(panel):,} rows × "
          f"{panel['fri_ts'].nunique()} weekends "
          f"({panel['fri_ts'].min()} → {panel['fri_ts'].max()})", flush=True)
    print(f"      context rows (fri_ts ≤ {cutoff}): {n_context:,}",
          flush=True)
    print(f"      forward rows (fri_ts > {cutoff}): {n_forward:,} "
          f"({panel.loc[panel['is_forward'], 'fri_ts'].nunique()} weekends, "
          f"{panel.loc[panel['is_forward'], 'symbol'].nunique() if n_forward else 0} symbols)",
          flush=True)

    panel["_schema_version"] = SCHEMA_VERSION
    panel["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    panel["_source"] = "scripts/collect_forward_tape.py"
    panel["_freeze_cutoff"] = cutoff.isoformat()
    panel["_frozen_artefact"] = frozen_json.name
    panel = panel.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)
    # `panel.build()` stuffs a non-JSON-serialisable PanelSpec into
    # `panel.attrs`; pyarrow tries to JSON-encode it on write. Clear.
    panel.attrs.clear()
    panel.to_parquet(FORWARD_TAPE_PATH, index=False)

    print(f"[3/3] Wrote {FORWARD_TAPE_PATH}", flush=True)
    if n_forward == 0:
        print("      (no forward rows — context-only tape; harness's evaluator "
              "exits 'insufficient data' and the launchd cadence picks up "
              "rows when scryer's G1.b lands forward polling for futures + "
              "vol indices)", flush=True)
    else:
        print("      forward weekends present:")
        forward_only = panel[panel["is_forward"]]
        for fri, n in (forward_only.groupby("fri_ts").size()
                       .sort_index().items()):
            print(f"        {fri}: {n} symbols")


if __name__ == "__main__":
    main()
