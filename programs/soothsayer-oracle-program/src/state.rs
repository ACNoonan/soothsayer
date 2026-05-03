//! On-chain account types for the Soothsayer oracle program.
//!
//! Three account types:
//!
//! - `PublisherConfig` — global PDA carrying authority + emergency-pause flag +
//!   cadence policy. One per program instance.
//! - `SignerSet` — global PDA carrying the Merkle root of currently-valid
//!   publisher pubkeys. For Phase 1 single-publisher the "root" is just the
//!   signer's pubkey stored directly. Multi-replicator Merkle verification
//!   lands in Phase 3.
//! - `PriceUpdate` — per-symbol PDA carrying the latest band + receipt. One
//!   per symbol in the universe; the symbol's PDA address is derived from
//!   the symbol bytes.
//!
//! Layout principles (informed by Pyth's Sep-2021 BTC flash-crash RCA — see
//! `reports/v1b_decision.md` and `07.1 - Deep Research Output v2` Topic 5):
//!
//! - Prices stored as **absolute fixed-point i64**, never as deltas. A consumer
//!   should never have to compute `point + lower_delta` to derive a band edge.
//! - Single `exponent: i8` applies to point/lower/upper/fri_close so they all
//!   share precision. No unit-mismatch footgun.
//! - Coverage / buffer values stored as integer **basis points** (u16), never
//!   as floats. 9500 = 95%. Eliminates any float-parse / float-compare drift
//!   between Rust, Anchor IDL, TS clients, and downstream consumers.
//! - Fields explicitly padded to 8-byte alignment for deterministic layout.

use anchor_lang::prelude::*;

/// Global program configuration. PDA seeded with [b"config"].
#[account]
#[derive(InitSpace)]
pub struct PublisherConfig {
    /// Schema version. Bumps on any layout change. Current: 1.
    pub version: u8,
    /// 1 if publishing is paused (authority-triggered emergency stop).
    pub paused: u8,
    /// Reserved for alignment; always 0.
    pub _pad0: [u8; 6],
    /// Minimum seconds between two publishes for the same symbol. Enforced
    /// on-chain to prevent accidental spam or a hot key getting stuck in a
    /// loop. Default: 30 seconds.
    pub min_publish_interval_secs: u32,
    /// Reserved.
    pub _pad1: u32,
    /// Authority for pause / rotate / upgrade. Typically a multisig in
    /// production; a single pubkey during the hackathon.
    pub authority: Pubkey,
}

/// Current signer set. PDA seeded with [b"signer_set"].
#[account]
#[derive(InitSpace)]
pub struct SignerSet {
    /// Schema version. Current: 1.
    pub version: u8,
    /// Number of active signers. For Phase 1: always 1. Multi-replicator path
    /// (Phase 3) grows this and replaces `root` with a Merkle root.
    pub signer_count: u8,
    pub _pad0: [u8; 6],
    /// Epoch of the current signer set. Increments on every rotation — both
    /// for audit trail and to let clients detect stale cached state.
    pub epoch: u64,
    /// Timestamp the set was last rotated.
    pub updated_ts: i64,
    /// Phase 1: directly the current publisher's pubkey bytes (single signer).
    /// Phase 3: Merkle root of the multi-replicator set. A consumer verifies
    /// a publish by proving `tx.signer ∈ signer_set` via the stored root.
    pub root: [u8; 32],
}

/// Per-symbol latest price. PDA seeded with [b"price", symbol_bytes].
///
/// Wire shape consumers integrate against. Anchor's discriminator (8 bytes)
/// prefixes the account data on-chain.
#[account]
#[derive(InitSpace)]
pub struct PriceUpdate {
    /// Schema version. Current: 1.
    pub version: u8,
    /// Regime code: 0=normal, 1=long_weekend, 2=high_vol, 3=shock_flagged.
    pub regime_code: u8,
    /// Forecaster used for this band: 0=F1_emp_regime (v1, legacy receipts),
    /// 1=F0_stale (v1, legacy receipts), 2=mondrian (M5 / v2 deployment).
    /// Receipt field.
    pub forecaster_code: u8,
    /// Shared exponent for the fixed-point prices: real_price = value * 10^exponent.
    /// For USDC-like 6-decimal precision: exponent = -6. For asset prices
    /// scaled to 8 decimals: exponent = -8. Publisher chooses per its own
    /// precision target; -8 is the Soothsayer default.
    pub exponent: i8,
    pub _pad0: [u8; 4],
    /// What the consumer asked for, in basis points (9500 = 95%).
    pub target_coverage_bps: u16,
    /// What we actually served, in basis points (e.g. 9750 = 97.5%). This is
    /// the `claimed_served` receipt that matches the Python `claimed_coverage_served`.
    pub claimed_served_bps: u16,
    /// Empirical calibration buffer applied to the target before surface
    /// inversion, in basis points (250 = 2.5%).
    pub buffer_applied_bps: u16,
    pub _pad1: [u8; 2],
    /// Symbol this price is for, ASCII, null-padded. e.g. b"SPY\0\0\0\0\0\0\0\0\0\0\0\0\0".
    pub symbol: [u8; 16],
    /// Absolute fixed-point price at scale `exponent`.
    pub point: i64,
    /// Absolute fixed-point lower-bound price. NOT a delta from point.
    pub lower: i64,
    /// Absolute fixed-point upper-bound price. NOT a delta.
    pub upper: i64,
    /// Friday-close price the band was anchored on (same scale).
    pub fri_close: i64,
    /// Unix-timestamp seconds of the Friday the band anchors to.
    pub fri_ts: i64,
    /// Unix-timestamp seconds when this update was published.
    pub publish_ts: i64,
    /// Solana slot of publication.
    pub publish_slot: u64,
    /// Which signer pubkey performed this publish.
    pub signer: Pubkey,
    /// Signer-set epoch at publish time. Lets consumers detect rotations.
    pub signer_epoch: u64,
}

impl PriceUpdate {
    /// Scale factor applied to a fixed-point i64 to recover the real price.
    pub fn scale(&self) -> f64 {
        (10f64).powi(self.exponent as i32)
    }

    pub fn point_f64(&self) -> f64 {
        self.point as f64 * self.scale()
    }
    pub fn lower_f64(&self) -> f64 {
        self.lower as f64 * self.scale()
    }
    pub fn upper_f64(&self) -> f64 {
        self.upper as f64 * self.scale()
    }
    pub fn fri_close_f64(&self) -> f64 {
        self.fri_close as f64 * self.scale()
    }
}

/// Wire payload for a `publish` instruction. Mirrors PriceUpdate layout for
/// the fields that the publisher provides; the rest (signer, publish_ts,
/// publish_slot, signer_epoch) are set by the program from tx context.
///
/// Kept as a single AnchorSerialize struct so TS clients + Rust publisher
/// share one schema.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Debug)]
pub struct PublishPayload {
    pub version: u8,
    pub regime_code: u8,
    pub forecaster_code: u8,
    pub exponent: i8,
    pub target_coverage_bps: u16,
    pub claimed_served_bps: u16,
    pub buffer_applied_bps: u16,
    pub symbol: [u8; 16],
    pub point: i64,
    pub lower: i64,
    pub upper: i64,
    pub fri_close: i64,
    pub fri_ts: i64,
}

/// Regime codes mirrored from `Regime` in `crates/soothsayer-oracle/src/types.rs`.
/// Keep in sync.
pub const REGIME_NORMAL: u8 = 0;
pub const REGIME_LONG_WEEKEND: u8 = 1;
pub const REGIME_HIGH_VOL: u8 = 2;
pub const REGIME_SHOCK_FLAGGED: u8 = 3;

/// Forecaster codes mirrored from Python/Rust `forecaster_used`.
///
/// Codes 0 and 1 are v1 receipts (F1_emp_regime + F0_stale, the hybrid
/// per-regime forecaster); code 2 is the M5 / v2 deployment (Mondrian
/// split-conformal by regime; paper 1 §7.7). Code 3 is reserved.
pub const FORECASTER_F1_EMP_REGIME: u8 = 0;
pub const FORECASTER_F0_STALE: u8 = 1;
pub const FORECASTER_MONDRIAN: u8 = 2;
pub const FORECASTER_RESERVED_3: u8 = 3;

/// Current schema version. Bump on any on-wire layout change.
pub const PRICE_UPDATE_VERSION: u8 = 1;
pub const PUBLISHER_CONFIG_VERSION: u8 = 1;
pub const SIGNER_SET_VERSION: u8 = 1;
