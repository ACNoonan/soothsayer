# CLAUDE.md — soothsayer

Calibration-transparent fair-value oracle for tokenized RWAs on Solana.

This is the startup context for agents. Keep it short. Detailed reasoning belongs in linked artefacts, especially `reports/methodology_history.md`.

## Read First

- `STATUS.md` — single-page current-state pointer page (read first; updated when methodology / workstream / artefact changes).
- `reports/methodology_history.md` — append-only dated decision log. §0 = current state, §1 = chronological entries.
- `reports/INDEX.md` — classifies every report under `reports/` as current / paper-evidence / historical / operational.
- `docs/ROADMAP.md` — phase sequencing and active publication/deployment gates.
- `docs/scryer_consumer_guide.md` — sanctioned data-read pattern from scryer parquet.
- `README.md` — public product shape and evidence snapshot.

When citing methodology, cite the dated entry or linked artefact rather than pasting long rationale.

## Hard Rules

1. **All upstream data fetching goes through scryer.** Soothsayer does not call external APIs for upstream data: no `requests.get`, `httpx`, `yfinance.download`, Solana RPC/Helius/Jupiter/Kraken/Web3 fetches, etc. The canonical live root is `SCRYER_DATASET_ROOT`, defaulting on this machine to `/Users/adamnoonan/Library/Application Support/scryer/dataset`.

2. **New data sources land in scryer first.** Add the methodology row / wishlist item in `../scryer`, implement fetcher + schema there, then consume parquet here. Do not write a one-off Soothsayer fetcher to unblock analysis.

3. **Analysis reads parquet, not raw API output.** Use `polars.read_parquet`, `pd.read_parquet`, or helpers in `soothsayer.sources.scryer` against `dataset/{venue}/{data_type}/v{N}/...`.

4. **Preserve metadata.** Keep `_schema_version`, `_fetched_at`, `_source`, and `_dedup_key` where present. Calibration and paper artefacts must record `_fetched_at` cutoffs for reproducibility.

5. **Soothsayer-derived datasets use experiment-versioned venues.** Venue is `soothsayer_v{N}`, data_type is the artefact (`tape`, `bounds`, `panel`, etc.), schema version is independent. Old data stays at the old venue.

6. **Do not restore deleted ingest code.** The April 2026 cutover removed Soothsayer-side fetching. If code imports deleted source modules, migrate it to scryer parquet.

If a user request would break these rules, name the rule and ask whether it is a deliberate exception.

## Current State

For deployed methodology, active workstreams, headline metrics, deployment artefact paths, and a per-task "if you're working on X, read Y" routing table: read [`STATUS.md`](STATUS.md). It is updated on every methodology / workstream / artefact change. Don't duplicate that content here.

For dated narrative on *why* the current state looks the way it does, read `reports/methodology_history.md`.

## Repo Map

```
src/soothsayer/
  oracle.py                  Python serving reference
  config.py                  paths/env, including SCRYER_DATASET_ROOT
  universe.py                xStock universe + mint registry
  sources/scryer.py          canonical parquet loaders
  backtest/                  panel assembly, calibration, metrics, protocol comparison
  chainlink/                 decoders only, no fetching
  bot/                       devnet-bot tape + decision logic

scripts/                     analysis/reporting runners; no upstream fetchers

crates/
  soothsayer-oracle          Rust port of oracle.py
  soothsayer-publisher       publish-path CLI
  soothsayer-consumer        no_std downstream decoder
  soothsayer-demo-kamino     Kamino integration demo

programs/                    Anchor programs for router / publish paths

reports/
  INDEX.md                   classifies every report as current / paper-evidence / historical / operational
  methodology_history.md     compact methodology ledger
  active/                    in-flight working docs (M6 refactor, Phase 7/8 results, validation backlog)
  paper1_coverage_inversion/
  paper3_liquidation_policy/
  paper4_oracle_conditioned_amm/

docs/
  ROADMAP.md
  scryer_consumer_guide.md
  methodology_scope.md
  sources/
```

## Canonical Read Pattern

```python
import polars as pl
from soothsayer.config import SCRYER_DATASET_ROOT

df = pl.read_parquet(
    SCRYER_DATASET_ROOT / "yahoo" / "equities_daily" / "v1" /
    "symbol=SPY" / "year=*.parquet"
)

assert df.select(pl.col("_schema_version").unique()).item() == "yahoo.v1"
```

Prefer `soothsayer.sources.scryer` helpers for common oracle tapes and windows.

## Available Data Pointers

Important live scryer surfaces include:

- `yahoo/equities_daily`, `yahoo/earnings`, `yahoo/corp_actions`
- `nasdaq/halts`, `backed/corp_actions`, `backed/nav_strikes`, `cme/intraday_1m`
- `pyth/oracle_tape`, `chainlink_data_streams/report_tape`, `redstone/oracle_tape`, `kamino_scope/oracle_tape`
- `soothsayer_v5/tape`
- `geckoterminal/trades`, `kraken/funding`, `solana_dex/xstock_swaps`
- `kamino/liquidations`, `marginfi/reserves`

If the path matters, verify against disk or `docs/scryer_consumer_guide.md`; do not rely on older shorthand.
