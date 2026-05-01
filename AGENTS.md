# AGENTS.md — soothsayer

This file is the canonical agent-instruction surface for non-Claude
tools (Codex, Cursor, Aider, etc.). Claude Code reads `CLAUDE.md` for
the long form; both files restate the same hard rules.

If you are an agent working in this repo, read `CLAUDE.md` first — it
has the project context, methodology pointers, and the canonical read
pattern. The five hard rules are reproduced verbatim below so they
fail the "I didn't see them" excuse.

---

## Hard rules

1. **All data fetching goes via scryer.** Soothsayer does not pull
   data from the network. No `requests.get`, no `httpx`, no
   `yfinance.download`, no `solana-py` / Helius / Jupiter / Kraken
   HTTP calls, no Web3 RPC. Data lives at
   `/Users/adamnoonan/Library/Application Support/scryer/dataset/{venue}/{data_type}/v{N}/...`
   (the canonical live root, also exposed as `soothsayer.config.SCRYER_DATASET_ROOT`).
   The sibling checkout `../scryer/dataset/...` is for offline replay only.

2. **New data sources go in scryer first.** Add a methodology entry
   to `scryer/methodology_log.md` (per scryer's hard rule #1),
   implement the fetcher + schema in scryer, then consume the parquet
   here. Queue lives in `scryer/wishlist.md`. Do not write a one-off
   fetcher in soothsayer.

3. **Analysis reads scryer parquet, not raw API output.** Use
   `polars.read_parquet` / `pd.read_parquet` against
   `dataset/{venue}/{data_type}/v{N}/...`. Don't materialise
   JSON→DataFrame in soothsayer.

4. **Preserve `_schema_version` / `_fetched_at` / `_source` on read.**
   Don't drop scryer's metadata columns. Record `_fetched_at` cutoffs
   in calibration runs so re-runs are reproducible. Use
   `_schema_version` to guard against silent schema upgrades.

5. **Soothsayer-side derived datasets use experiment-versioned
   venues.** Venue = `soothsayer_v{N}`, data_type = artefact name,
   schema version independent. See the 2026-04-27 lock in
   `scryer/methodology_log.md`. Old data stays at the old venue
   forever.

If a request would break any of these, name the rule, cite the
methodology section, and ask whether this is a deliberate exception
or whether the plan needs to change.

## Operational path notes

- **Trust the live dataset layout, not an inferred schema nickname.**
  Some storage paths differ from the older shorthand used in docs:
  `yahoo.v1` daily bars live under `yahoo/equities_daily/v1/...`
  (not `yahoo/bars/v1/...`), and `nasdaq_halts.v1` lives under
  `nasdaq/halts/v1/...` (not `nasdaq_halts/live/...`).
- **Prefer `SCRYER_DATASET_ROOT` or `soothsayer.sources.scryer` loaders.**
  Hardcoding `../scryer/dataset` or reconstructing paths from memory is a
  common failure mode. Read `docs/scryer_consumer_guide.md` first if the
  exact `venue/data_type` path matters.
- **When verifying migration status, check the real filesystem.**
  If docs and disk disagree, prefer the actual live dataset under
  `SCRYER_DATASET_ROOT` and update the docs/rules to match it.

## Read pattern (canonical)

```python
import polars as pl
from pathlib import Path

SCRYER_ROOT = Path("/Users/adamnoonan/Library/Application Support/scryer/dataset")

spy_bars = pl.read_parquet(
    SCRYER_ROOT / "yahoo" / "equities_daily" / "v1" / "symbol=SPY" / "year=*.parquet"
)
assert spy_bars.select(pl.col("_schema_version").unique()).item() == "yahoo.v1"

nasdaq_halts = pl.read_parquet(
    SCRYER_ROOT / "nasdaq" / "halts" / "v1" / "year=2026.parquet"
)
assert nasdaq_halts.select(pl.col("_schema_version").unique()).item() == "nasdaq_halts.v1"
```

Full guide: `docs/scryer_consumer_guide.md`. Available datasets table:
`CLAUDE.md` § Available scryer data.

## What was deleted in the April 2026 cutover

`crates/soothsayer-ingest/`, `src/soothsayer/sources/`,
`src/soothsayer/cache.py`, `src/soothsayer/chainlink/scraper.py`,
and 22 fetcher scripts under `scripts/`. The corresponding scryer
schemas / fetchers are listed in `CLAUDE.md` § Available scryer data
and `scryer/wishlist.md`. If you find a script that imports from a
deleted module, the fix is *always* to read scryer parquet, never to
restore the deleted fetcher.
