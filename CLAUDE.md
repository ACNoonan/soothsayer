# CLAUDE.md — soothsayer

Calibration-transparent fair-value oracle for tokenized RWAs on Solana.

This is the startup context for agents. Keep it short. Detailed reasoning belongs in linked artefacts, especially `reports/methodology_history.md`.

## Read First

- `reports/methodology_history.md` — compact operational source of truth: current decisions, recent locks, open gates.
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

Phase 0 validation is complete. Phase 1 is active: devnet / publish-path work, Paper 1 completion, Paper 3 draft, and forward data capture for Paper 4/Product-stack evidence.

Current methodology:

- Product: calibrated band primitive with receipts; downstream policy work consumes the band.
- Default deployment target: `τ = 0.85`.
- Paper 1 headline target: `τ = 0.95`.
- Served range with strongest evidence: `τ ∈ [0.52, 0.98]`; `τ = 0.99` is a disclosed finite-sample tail ceiling.
- Hybrid forecaster: `normal` + `long_weekend` use `F1_emp_regime`; `high_vol` uses `F0_stale`.
- Buffer schedule: `{0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.010}`.

Paper 3 current framing:

- Three claims: Geometric, Structural, Empirical.
- Kamino-xStocks is the xStock empirical panel (`kamino/liquidations/v1`, 102 events over 2025-08 to 2026-04).
- MarginFi is the cleanest general-lending deployment-substrate argument; it has zero direct xStock Banks in the current scan.
- Active next work: Kamino 2025-11 cluster analysis, dynamic-bonus / `D_repaid` fit, class-disaggregated reserve-buffer evaluation, path-aware truth.

Paper 4 / product-stack current framing:

- Post-grant AMM arc, but forward capture must start now.
- Scryer item 51 owns `jito_bundle_tape`, `validator_client`, `clmm_pool_state`, `dlmm_pool_state`, and `dex_xstock_swaps` promotion.
- Soothsayer later builds consumers: pool-state reconstructor, path-aware truth labeller, bundle-attribution labels, counterfactual replay.

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
  methodology_history.md     compact methodology ledger
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
