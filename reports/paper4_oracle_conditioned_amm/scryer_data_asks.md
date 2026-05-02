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

## Proposed recurring Scryer analytics job (new ask)

This is the operational follow-up to the one-shot Soothsayer analytics script
(`scripts/compute_competitor_oracle_analytics.py`): move the same metrics into
a scheduled Scryer job so comparator analytics are continuously recomputed from
fresh parquet and available to all downstream consumers.

### Job contract

- **Job name:** `competitor_oracle_analytics_rollup.v1`
- **Owner:** Scryer (scheduled analysis/rollup, no new upstream fetchers)
- **Run cadence:** hourly at `:07` (UTC), plus one daily close rollup at
  `00:17` UTC.
- **Input datasets:**
  - `soothsayer_v5/tape/v1`
  - `pyth/oracle_tape/v1`
  - `redstone/oracle_tape/v1`
  - Chainlink stream tape with path fallback:
    - preferred `chainlink_data_streams/report_tape/v1`
    - fallback `chainlink/data_streams/v1` (current local layout)
- **Output dataset (derived):**
  - `soothsayer_v6/competitor_oracle_analytics/v1/year=YYYY/month=MM/day=DD.parquet`
  - schema version: `soothsayer_competitor_oracle_analytics.v1`

### Output schema (tall format, append-friendly)

Minimum columns:

- `as_of_ts` (UTC timestamp; rollup run time)
- `window` (`1d`, `7d`, `30d`, `all_available`)
- `provider` (`chainlink_v11`, `chainlink_v10_v5`, `pyth_regular`, `redstone_live`)
- `session_bucket` (`weekday`, `weekend`, `regular`, `pre`, `post`, `on`, `unknown`)
- `symbol` (nullable string; empty for provider-level aggregate rows)
- `metric` (string)
- `value` (float64)
- `n_obs` (int64)
- `source_start_ts` (UTC timestamp)
- `source_end_ts` (UTC timestamp)
- `_schema_version`, `_fetched_at`, `_source`, `_dedup_key`

### Required metrics

Per provider/window/session (and by symbol where available):

1. **Coverage counters**
   - `rows_total`
   - `symbols_covered`
   - `coverage_hours`
2. **Variance/dispersion proxies**
   - `abs_return_bps_median`
   - `abs_return_bps_p90`
3. **Provider-specific integrity metrics**
   - **Pyth:** `conf_bps_median`, `conf_bps_p90`
   - **RedStone:** `minutes_age_median`, `poll_cadence_s_median`, `poll_cadence_s_p90`
   - **Chainlink v11:** `spread_bps_median`, `spread_bps_p90`, `market_status_share_*`,
     `bid_marker_01_rate`, `ask_marker_01_rate`
     *Note:* `spread_bps_*` is **misleading during `market_status = 5` (weekend)** windows
     for SPYx, QQQx, and TSLAx because the wire `bid` / `ask` carry synthetic `.01`-suffix
     placeholder values (canonical [`docs/sources/oracles/chainlink_v11.md`](../../docs/sources/oracles/chainlink_v11.md)
     §3, "Spread is misleading on weekends" reconciliation row). The `bid_marker_01_rate`
     and `ask_marker_01_rate` metrics above are the load-bearing weekend signal; consumers
     should stratify spread metrics by `market_status` and treat synthetic-marker-positive
     rows as a separate cohort rather than averaging through them.
   - **v5 joined comparator:** `basis_abs_bps_median`, `basis_abs_bps_p90`
4. **Data-health metrics**
   - `null_rate_<core_field>`
   - `duplicate_rate_dedup_key`

### Quality/freshness gates

- Emit a row-level `data_quality_flag` derived from:
  - freshness lag > 2 * expected cadence,
  - symbol coverage drop > 30% vs prior 7-day baseline,
  - chainlink v11 window too short for trend claim (`coverage_hours < 72`).
- Do not suppress rows when quality is degraded; publish with flags so
  dashboards/reports can disclose uncertainty rather than silently dropping data.

### Soothsayer-side consumption

- Registry and paper/dashboard consumers should read this derived dataset first;
  one-off scripts become audit tools, not the production path.
- `docs/sources/oracles/competitor_oracle_registry.md` should reference this
  dataset as the canonical analytics feed once the job is live.
