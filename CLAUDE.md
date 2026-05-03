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

Current methodology (v2 / M5 — deployed):

- Product: calibrated band primitive with receipts; downstream policy work consumes the band.
- Default deployment target: `τ = 0.85`.
- Paper 1 headline target: `τ = 0.95`.
- Served range: `τ ∈ [0.68, 0.99]`; M5 closes the v1 finite-sample tail ceiling at τ=0.99 at the cost of a 22% wider band.
- Architecture: Mondrian split-conformal by `regime_pub` + factor-adjusted point + δ-shifted `c(τ)`. Twenty deployment scalars: 12 trained per-regime quantiles, 4 OOS-fit `c(τ)` bumps, 4 walk-forward-fit `δ(τ)` shifts. See `src/soothsayer/oracle.py` and `crates/soothsayer-oracle/src/config.rs`.
- Deployment artefact: `data/processed/mondrian_artefact_v2.parquet` (per-Friday rows) + `data/processed/mondrian_artefact_v2.json` (audit-trail sidecar with the 20 scalars). Built by `scripts/build_mondrian_artefact.py`.
- Wire format: `PriceUpdate` Borsh layout preserved across the v1 → M5 migration; `forecaster_code = 2` (FORECASTER_MONDRIAN) signals an M5 read.
- Empirical headline: at τ=0.95 on the 2023+ OOS slice, realised $0.950$ with Kupiec $p = 0.956$, Christoffersen $p = 0.912$, mean half-width $354.5$ bps (20% narrower than the v1 hybrid Oracle at the same anchor and parameter budget). See `reports/methodology_history.md` (2026-05-02 M5 entry) and `reports/paper1_coverage_inversion/` §4 + §7.7.

Post-M5 direction (2026-05-03, architecturally locked, not yet deployed): dual-profile methodology family. Lending-track (M6b2 per-class Mondrian) ships next; AMM-track (M6a-deployable common-mode partial-out) gated on a Friday-observable r̄_w forward predictor. Both profiles share this M5 architecture and wire format; they differ only in (a) score residualisation and (b) conformal cell partition. Working doc: `M6_REFACTOR.md` (root). Architecture: `docs/product-stack.md` "Dual-profile methodology family" section + per-layer track assignment table. Decision record: `reports/methodology_history.md` (2026-05-03 entry).

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
