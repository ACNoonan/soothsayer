//! On-chain account types for the soothsayer-router program.
//!
//! Three account types:
//!
//! - [`RouterConfig`] — global PDA. Authority + emergency-pause flag +
//!   creation/update timestamps. One per program instance.
//! - [`AssetConfig`] — per-asset PDA. Filter parameters (max_staleness /
//!   max_confidence / max_deviation), `min_quorum`, the upstream PDA list,
//!   the market-status source PDA, and the soothsayer band PDA.
//! - [`UnifiedFeedSnapshot`] — per-asset PDA. Mirrors `unified_feed_receipt.v1`
//!   in BPF-friendly fixed-point i64 + integer enum codes. Updated on every
//!   `refresh_feed` instruction.
//!
//! The wire format mapping is one-to-one with the host-side
//! `crates/soothsayer-router::receipt::UnifiedFeedReceipt` and is enforced
//! by the 2026-04-28 (morning) methodology lock. Off-chain decoders convert
//! the on-chain snapshot into the host-side receipt for SDK consumers.
//!
//! Layout principles (mirrored from `soothsayer-oracle-program`):
//!
//! - Prices stored as **absolute fixed-point i64**, never as deltas.
//! - One `exponent: i8` shared across all price fields in a snapshot.
//! - Coverage / buffer / filter values stored as integer **basis points** (u16),
//!   never floats.
//! - Explicit `_pad` fields for deterministic on-chain layout.

use anchor_lang::prelude::*;

// ─────────────────────────────── schema versions ────────────────────────────

pub const ROUTER_CONFIG_VERSION: u8 = 1;
pub const ASSET_CONFIG_VERSION: u8 = 1;
pub const UNIFIED_FEED_SNAPSHOT_VERSION: u8 = 1;

/// Off-chain receipt schema id. The on-chain snapshot is the BPF-friendly
/// projection; decoders rehydrate to this string when emitting the host-side
/// `unified_feed_receipt.v1` tuple. Locked 2026-04-28 (morning).
pub const RECEIPT_SCHEMA_ID: &str = "unified_feed_receipt.v1";

/// Maximum number of upstream feeds per asset. Pyth + Chainlink v11 +
/// Switchboard On-Demand + RedStone Live = 4. (Mango v4 was reclassified
/// methodology-only per the 2026-04-29 entry; see `docs/methodology_history.md`.)
/// The constant stays at 5 to preserve account layout if a future variant is
/// added; the empty 5th slot has `active = 0` and is otherwise zeroed.
pub const MAX_UPSTREAMS: usize = 5;

// ─────────────── enum codes (mirror `crates/soothsayer-router::receipt`) ────

// Regime
pub const REGIME_OPEN: u8 = 0;
pub const REGIME_CLOSED: u8 = 1;
pub const REGIME_HALTED: u8 = 2;
pub const REGIME_UNKNOWN: u8 = 3;

// QualityFlag
pub const QUALITY_OK: u8 = 0;
pub const QUALITY_LOW_QUORUM: u8 = 1;
pub const QUALITY_ALL_STALE: u8 = 2;
pub const QUALITY_SOOTHSAYER_BAND_UNAVAILABLE: u8 = 3;
pub const QUALITY_REGIME_AMBIGUOUS: u8 = 4;

// AggregateMethod
pub const AGGREGATE_ROBUST_MEDIAN_V1: u8 = 0;
/// Forward reference to Layer 1; not used in Layer 0 v0.
pub const AGGREGATE_CALIBRATION_WEIGHTED_V1: u8 = 1;

// UpstreamKind (must match scryer venue strings + host-side enum).
//
// Code 1 was renamed `UPSTREAM_CHAINLINK_V11` → `UPSTREAM_CHAINLINK_STREAMS_RELAY`
// per the 2026-04-29 (afternoon) entry: Chainlink Data Streams on Solana doesn't
// publish passive PDAs (per-tx report-submission product), so the router consumes
// via a soothsayer-controlled relay program (Option C). Discriminant value
// unchanged at 1; only the name + decoder behaviour changed. The receipt-side
// wire format is `chainlink_streams_relay` (renamed from `chainlink_v11`).
//
// Code 4 was previously `UPSTREAM_MANGO_V4_POST_GUARD`; reclassified to
// methodology-only per the 2026-04-29 (morning) entry. Code 4 is reserved
// (not reused) so any historical receipt that hex-dumps an upstream
// contribution with kind=4 is recognisable as belonging to the retracted variant.
pub const UPSTREAM_PYTH_AGGREGATE: u8 = 0;
pub const UPSTREAM_CHAINLINK_STREAMS_RELAY: u8 = 1;
pub const UPSTREAM_SWITCHBOARD_ONDEMAND: u8 = 2;
pub const UPSTREAM_REDSTONE_LIVE: u8 = 3;

// ExclusionReason — 0 means "included in the aggregate" (no exclusion).
pub const EXCLUSION_NONE: u8 = 0;
pub const EXCLUSION_STALE: u8 = 1;
pub const EXCLUSION_LOW_CONFIDENCE: u8 = 2;
pub const EXCLUSION_DEVIATION_OUTLIER: u8 = 3;

// Forecaster (closed-regime; mirror of the soothsayer-oracle-program codes)
pub const FORECASTER_F1_EMP_REGIME: u8 = 0;
pub const FORECASTER_F0_STALE: u8 = 1;

// ClosedMarketRegime (closed-regime label)
pub const CLOSED_MARKET_REGIME_NORMAL: u8 = 0;
pub const CLOSED_MARKET_REGIME_LONG_WEEKEND: u8 = 1;
pub const CLOSED_MARKET_REGIME_HIGH_VOL: u8 = 2;

// ─────────────────────────────── account types ──────────────────────────────

/// Global program configuration. PDA seeded with `[b"router_config"]`.
#[account]
#[derive(InitSpace)]
pub struct RouterConfig {
    pub version: u8,
    /// 1 if the entire router is paused (authority-triggered emergency stop).
    pub paused: u8,
    pub _pad0: [u8; 6],
    pub authority: Pubkey,
    pub created_ts: i64,
    pub updated_ts: i64,
}

/// One slot of an asset's upstream-feed list. Used inside [`AssetConfig`].
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, Debug, Default, InitSpace)]
pub struct UpstreamSlot {
    /// `UPSTREAM_*` discriminant.
    pub kind: u8,
    /// 1 if this slot is populated; 0 means the slot is empty (skip).
    pub active: u8,
    pub _pad0: [u8; 6],
    pub pda: Pubkey,
    /// Per-upstream weight in basis points. Layer 0 v0 uses uniform weights
    /// (set to 10000 / n_active_upstreams at config time). Layer 1 (future)
    /// will use historical-fit weights derived from the upstream forward
    /// tape (scryer wishlist items 21-23).
    pub initial_weight_bps: u16,
    pub _pad1: [u8; 6],
}

/// Per-asset configuration. PDA seeded with `[b"asset", asset_id]`
/// where `asset_id` is the 16-byte ASCII-padded ticker
/// (matches `soothsayer-oracle-program::PriceUpdate.symbol`).
#[account]
#[derive(InitSpace)]
pub struct AssetConfig {
    pub version: u8,
    /// 1 if this asset's feed is paused while leaving the rest of the
    /// router live.
    pub paused: u8,
    /// Number of populated upstream slots (`<= MAX_UPSTREAMS`).
    pub n_upstreams: u8,
    /// Required post-filter surviving upstreams.  The Layer 0 v0 default is
    /// asset-specific and recorded in the methodology log.  See open
    /// methodology question O5 (2026-04-28 (afternoon) entry).
    pub min_quorum: u8,
    pub _pad0: [u8; 4],

    /// 16-byte ASCII-padded ticker. Must match the AssetConfig PDA seed.
    pub asset_id: [u8; 16],

    /// Filter parameters (Mango-style staleness / confidence / deviation).
    /// v0 defaults locked 2026-04-28 (midday): 60s / 200 bps / 75 bps for
    /// equities; 60s / 200 bps / 50 bps for crypto-correlated tokens.
    pub max_staleness_secs: u32,
    pub max_confidence_bps: u16,
    pub max_deviation_bps: u16,

    /// PDA whose state is read to determine `marketStatus` for the regime
    /// gate. v0 default for equities: Chainlink v11 report PDA.
    pub market_status_source: Pubkey,

    /// PDA of the closed-regime soothsayer band primitive (a `PriceUpdate`
    /// from `soothsayer-oracle-program`).
    pub soothsayer_band_pda: Pubkey,

    /// Configured upstream feeds. Inactive slots have `active = 0`.
    pub upstreams: [UpstreamSlot; MAX_UPSTREAMS],

    pub created_ts: i64,
    pub updated_ts: i64,
}

/// One slot of the snapshot's per-upstream contribution log. Mirrors the
/// host-side `UpstreamReceipt` field-for-field with fixed-point ints.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, Debug, Default, InitSpace)]
pub struct UpstreamReadSlot {
    pub kind: u8,
    /// 1 if this read survived all filters and was included in the aggregate.
    pub included: u8,
    pub exclusion_reason_code: u8,
    pub _pad0: [u8; 5],

    pub pda: Pubkey,
    /// Fixed-point at the snapshot's `exponent`.
    pub raw_price: i64,
    /// Fixed-point at the snapshot's `exponent`. Sentinel `i64::MIN` means
    /// the upstream did not publish a confidence interval.
    pub raw_confidence: i64,
    pub last_update_slot: u64,
    /// Signed deviation in basis points from the post-filter median. Valid
    /// when `included == 0 && exclusion_reason_code == EXCLUSION_DEVIATION_OUTLIER`.
    pub deviation_bps_from_median: i32,
    pub _pad1: [u8; 4],
}

/// Per-asset latest unified-feed snapshot. PDA seeded with
/// `[b"snapshot", asset_id]`. Mirrors `unified_feed_receipt.v1` in
/// fixed-point + integer codes.
///
/// Field-population semantics are regime-conditional and match the host-side
/// receipt. `validate_regime_invariants` lives off-chain (in
/// `crates/soothsayer-router`); on-chain we trust `refresh_feed` to set the
/// invariants correctly and emit a `FeedRefreshed` event for indexers.
#[account]
#[derive(InitSpace)]
pub struct UnifiedFeedSnapshot {
    pub version: u8,
    pub regime_code: u8,
    pub quality_flag_code: u8,
    /// Set during open-regime; unspecified otherwise. Layer 0 v0: always
    /// `AGGREGATE_ROBUST_MEDIAN_V1`. Layer 1 will use
    /// `AGGREGATE_CALIBRATION_WEIGHTED_V1` without an account-version bump.
    pub aggregate_method_code: u8,
    /// Set during closed/halted regime; unspecified otherwise.
    pub forecaster_code: u8,
    /// Set during closed/halted regime; unspecified otherwise.
    pub closed_market_regime_code: u8,
    /// Set during open regime; unspecified otherwise.
    pub quorum_size: u8,
    /// Set during open regime; mirrors `AssetConfig.min_quorum` at read time.
    pub quorum_required: u8,

    pub exponent: i8,
    pub _pad0: [u8; 7],

    pub asset_id: [u8; 16],
    pub point: i64,
    pub lower: i64,
    pub upper: i64,

    /// Closed-regime: target coverage the consumer requested (basis points,
    /// 9500 = 95%). Unspecified during open regime.
    pub target_coverage_bps: u16,
    /// Closed-regime: claimed quantile actually served (basis points).
    pub claimed_served_bps: u16,
    /// Closed-regime: empirical buffer applied at the serving layer.
    pub buffer_applied_bps: u16,
    pub _pad1: [u8; 2],

    /// Unix-timestamp seconds of the last successful refresh.
    pub publish_ts: i64,
    /// Solana slot of the last successful refresh.
    pub publish_slot: u64,

    /// Open-regime contribution log. Up to `MAX_UPSTREAMS` rows, populated
    /// from index 0 to `n_upstream_reads`. Inactive slots are zeroed.
    pub upstream_reads: [UpstreamReadSlot; MAX_UPSTREAMS],
    pub n_upstream_reads: u8,
    pub _pad2: [u8; 7],
}

impl UnifiedFeedSnapshot {
    pub fn scale(&self) -> f64 {
        (10f64).powi(self.exponent as i32)
    }
}

// ─────────────────────────── instruction payload ───────────────────────────

/// Wire payload for `add_asset` and `update_asset_config`. Excludes seed-
/// derived fields (the asset-id seed); the program asserts the seed matches.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Debug)]
pub struct AssetConfigPayload {
    pub version: u8,
    pub paused: u8,
    pub min_quorum: u8,
    pub asset_id: [u8; 16],
    pub max_staleness_secs: u32,
    pub max_confidence_bps: u16,
    pub max_deviation_bps: u16,
    pub market_status_source: Pubkey,
    pub soothsayer_band_pda: Pubkey,
    /// Number of populated entries; remaining slots are zero/inactive.
    pub n_upstreams: u8,
    pub upstreams: [UpstreamSlot; MAX_UPSTREAMS],
}
