# Paper 4 Phase A — scryer data asks

**Status:** compacted 2026-05-02. This file is now the short handoff. The reconciled operational plan is `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md`; use that as the source of truth.

## Why This Exists

Paper 4 needs 6-9 months of slot-resolution xStock AMM data. Several inputs are forward-only or retention-limited, so the operational priority is to start capture now, not when Paper 4 writing begins.

## Current Scryer State

Already live / usable for the Paper 4 foundation:

- `pyth/oracle_tape`
- `chainlink_data_streams/report_tape`
- `redstone/oracle_tape`
- `kamino_scope/oracle_tape`
- `soothsayer_v5/tape`
- `geckoterminal/trades`
- `kraken/funding`
- `cme/intraday_1m`
- `nasdaq/halts`
- `backed/corp_actions`, `backed/nav_strikes`
- `yahoo/equities_daily`, `yahoo/earnings`, `yahoo/corp_actions`
- `solana_dex/xstock_swaps` code path / promotion path

Already locked in scryer for item 51:

- `jito_bundle_tape.v1`
- `validator_client.v1`
- `clmm_pool_state.v1`
- `dlmm_pool_state.v1`
- `dex_xstock_swaps.v1` backfill + forward-poll promotion

## Operational Asks

Start these first because every day deferred loses panel time:

1. **51a — Jito bundle tape forward poll.** Highest urgency because bundle history has finite retention.
2. **51b — validator-client labels.** Forward-only past public labeller horizons.
3. **49a-49d operator triggers.** Backfill Pyth, Kamino Scope, RedStone, and Chainlink 90d tapes in parallel.
4. **51c/51d — CLMM + DLMM pool-state capture.** Geyser provider choice lands in the per-fetcher scryer methodology row.
5. **51e — `dex_xstock_swaps` historical backfill + forward poll.** Backfill from 2025-07-14 to forward cursor.

Cross-paper item:

- **Item 47 — `marginfi_liquidation.v1`.** Priority 0 for Paper 3; also useful for Paper 4 cross-protocol OEV joins.

## Mint Universe

Use the current 8 xStocks from `src/soothsayer/universe.py`: SPYx, QQQx, AAPLx, GOOGLx, NVDAx, TSLAx, HOODx, MSTRx.

GLDx/TLTx are allowed only if Backed lists them during the panel; that requires a follow-up methodology amendment.

## Still-Open Questions

- Geyser provider for pool-state capture: Helius vs Triton vs Yellowstone vs operator-run node.
- `getVersion` vs community-labeller disagreement rate for validator-client labels.
- Cross-DEX CLMM field normalization in Soothsayer consumer code once rows exist.

## Out of Scope for Scryer

These are Soothsayer-side consumers after parquet rows exist:

- path-aware next-venue-open truth labeller
- pool-state reconstructor
- bundle-attribution to RWA-pool LVR labels
- BAM Plugin reference implementation
- B0/B1/B2/B3 counterfactual replay engine
