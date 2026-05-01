//! On-chain account types for soothsayer-streams-relay-program.
//!
//! Three account types:
//!
//! - [`RelayConfig`] — global PDA. Authority + emergency-pause flag +
//!   active writer-set list. One per program instance.
//! - [`FeedRegistry`] — per-feed config PDA. Holds the feed_id, underlier
//!   symbol, exponent, and feed-specific operational flags. PDA seed:
//!   `[b"feed", feed_id]`.
//! - [`StreamsRelayUpdate`] — per-feed price PDA. Mirrors the
//!   `streams_relay_update.v1` schema locked in the soothsayer methodology
//!   log 2026-04-29 (afternoon). PDA seed: `[b"streams_relay", feed_id]`.
//!   Updated on every successful `post_relay_update` call by an authorised
//!   writer.
//!
//! Layout principles match `soothsayer-router-program::state` for consistency:
//! prices stored as absolute fixed-point i64; one shared exponent across price
//! / confidence / bid / ask / last_traded_price; integer enum codes (no
//! floats); explicit padding for deterministic on-chain layout.

use anchor_lang::prelude::*;

// ─────────────────────────────── schema versions ────────────────────────────

pub const RELAY_CONFIG_VERSION: u8 = 1;
pub const FEED_REGISTRY_VERSION: u8 = 1;
pub const STREAMS_RELAY_UPDATE_VERSION: u8 = 1;

/// Off-chain relay-PDA schema id. Kept in sync with the soothsayer-router
/// host crate's expectations; consumers reading the relay PDA decode against
/// this version. Locked 2026-04-29 (afternoon).
pub const RELAY_SCHEMA_ID: &str = "streams_relay_update.v1";

/// Maximum number of writer keypairs in the active writer set. v0 starts at 1
/// (single-key); the constant allows pre-allocation for future multi-writer
/// rotation per O10 in the soothsayer methodology log §2.
pub const MAX_WRITERS: usize = 5;

/// Maximum number of feeds tracked in the global registry index. Per-feed
/// `FeedRegistry` PDAs exist independently; this constant is informational
/// only (no fixed-size array uses it on-chain currently).
pub const SUGGESTED_FEED_LIMIT: usize = 32;

// ──────────────────── Chainlink schema discriminants ───────────────────────

/// Schema 8 (V8) — Chainlink Data Streams RWA report shape (used for
/// US equities on Solana).
pub const CHAINLINK_SCHEMA_V8: u8 = 8;
/// Schema 11 (V11) — Chainlink Data Streams V11 (EVM-side; reserved here
/// for forward compatibility if equity feeds migrate).
pub const CHAINLINK_SCHEMA_V11: u8 = 11;

// ────────── market_status discriminants (mirror Chainlink's vocabulary) ────

pub const MARKET_STATUS_UNKNOWN: u8 = 0;
pub const MARKET_STATUS_PRE_MARKET: u8 = 1;
pub const MARKET_STATUS_REGULAR: u8 = 2;
pub const MARKET_STATUS_POST_MARKET: u8 = 3;
pub const MARKET_STATUS_OVERNIGHT: u8 = 4;
pub const MARKET_STATUS_CLOSED: u8 = 5;

// ────────────────── signature_verified discriminants ───────────────────────

/// Off-chain validation only (development / trust mode). v0 production
/// (per O11 in the soothsayer methodology log §2) ships always-CPI on
/// devnet, so production receipts always carry SIGNATURE_VERIFIED_CPI.
pub const SIGNATURE_VERIFIED_OFFCHAIN_ONLY: u8 = 0;
/// Verifier CPI succeeded — the signed report was validated by Chainlink's
/// on-chain Verifier program before this PDA was written.
pub const SIGNATURE_VERIFIED_CPI: u8 = 1;

// ─────────────────────────────── account types ──────────────────────────────

/// Global program configuration. PDA seeded with `[b"relay_config"]`.
#[account]
#[derive(InitSpace)]
pub struct RelayConfig {
    pub version: u8,
    /// 1 if the relay is paused (authority-triggered emergency stop).
    pub paused: u8,
    /// Active writers in the set; remaining slots are zero pubkeys.
    pub n_writers: u8,
    /// 1 if Verifier CPI is required for `post_relay_update` (mainnet
    /// production default). 0 enables the off-chain validation path
    /// (devnet-only, pre-Verifier-SDK integration). Per the 2026-04-29
    /// (evening) entry, v0 ships always-CPI on devnet; this field exists
    /// for the methodology-locked transition policy.
    pub verifier_cpi_required: u8,
    pub _pad0: [u8; 4],

    pub authority: Pubkey,
    pub writer_set: [Pubkey; MAX_WRITERS],

    pub created_ts: i64,
    pub updated_ts: i64,
}

/// Per-feed configuration. PDA seeded with `[b"feed", feed_id]`.
#[account]
#[derive(InitSpace)]
pub struct FeedRegistry {
    pub version: u8,
    /// 1 if posts to this feed are paused while leaving the rest of the relay live.
    pub paused: u8,
    /// Default exponent for the relay PDA's fixed-point fields. Soothsayer
    /// convention: -8 for equities (mirrors the router's
    /// DEFAULT_SNAPSHOT_EXPONENT).
    pub exponent: i8,
    /// Last successful Chainlink schema decoded for this feed (CHAINLINK_SCHEMA_*).
    /// 0 if the feed has never been posted to.
    pub last_schema_decoded_from: u8,
    pub _pad0: [u8; 4],

    /// Chainlink Data Streams feed_id (32 bytes, raw).
    pub feed_id: [u8; 32],
    /// ASCII null-padded underlier symbol (e.g., b"SPY\0\0\0...").
    pub underlier_symbol: [u8; 16],

    pub created_ts: i64,
    pub last_post_ts: i64,
}

/// Per-feed price PDA. Mirrors the `streams_relay_update.v1` wire format
/// locked in the soothsayer methodology log 2026-04-29 (afternoon).
/// PDA seeded with `[b"streams_relay", feed_id]`.
#[account]
#[derive(InitSpace)]
pub struct StreamsRelayUpdate {
    pub version: u8,
    /// MARKET_STATUS_* discriminant (0..5).
    pub market_status_code: u8,
    /// CHAINLINK_SCHEMA_* discriminant (audit trail: which Chainlink
    /// wire format was decoded into this PDA).
    pub schema_decoded_from: u8,
    /// SIGNATURE_VERIFIED_* discriminant.
    pub signature_verified: u8,
    pub _pad0: [u8; 4],

    pub feed_id: [u8; 32],
    pub underlier_symbol: [u8; 16],

    /// Fixed-point at `exponent`. Defaults to mid; falls back to
    /// last_traded_price when mid is a Chainlink placeholder per paper-1
    /// §1.1 observation. Soothsayer's relay daemon does the price-selection
    /// logic off-chain before submitting.
    pub price: i64,
    /// Fixed-point at `exponent`. Sentinel `i64::MIN` if no CI is derivable
    /// (the relay daemon decides; v0 derivation: (ask - bid) / 2 when both
    /// are real, sentinel otherwise).
    pub confidence: i64,
    pub bid: i64,
    pub ask: i64,
    pub last_traded_price: i64,

    /// Unix seconds; from the Chainlink report's `observations_timestamp`.
    pub chainlink_observations_ts: i64,
    /// Nanoseconds; from `last_seen_timestamp_ns` in the Chainlink report.
    pub chainlink_last_seen_ts_ns: i64,
    /// Unix seconds when the relay daemon called `post_relay_update`.
    pub relay_post_ts: i64,
    /// Solana slot of the relay write.
    pub relay_post_slot: u64,

    pub exponent: i8,
    pub _pad1: [u8; 7],
}

// ─────────────────────────── instruction payloads ──────────────────────────

/// Wire payload for `add_feed`.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Debug)]
pub struct AddFeedPayload {
    pub feed_id: [u8; 32],
    pub underlier_symbol: [u8; 16],
    pub exponent: i8,
}

/// Wire payload for `post_relay_update`. The `signed_report_blob` is the
/// full DON-signed report bytes the daemon fetched from Chainlink Streams;
/// the relay program forwards it to the Verifier program via CPI (Phase 42b).
/// `decoded_fields` carries the off-chain-decoded projection that becomes
/// the relay PDA contents on success.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Debug)]
pub struct PostRelayUpdatePayload {
    pub feed_id: [u8; 32],
    /// Soothsayer schema version this post claims to follow.
    pub version: u8,
    /// CHAINLINK_SCHEMA_* discriminant. Records which Chainlink schema
    /// was decoded (V8 for equities; V11 reserved for future migration).
    pub schema_decoded_from: u8,
    /// MARKET_STATUS_* discriminant (0..5).
    pub market_status_code: u8,
    pub _pad0: [u8; 5],

    pub price: i64,
    pub confidence: i64,
    pub bid: i64,
    pub ask: i64,
    pub last_traded_price: i64,
    pub chainlink_observations_ts: i64,
    pub chainlink_last_seen_ts_ns: i64,

    /// The raw DON-signed report blob the daemon fetched from Chainlink
    /// Streams. Phase 42b forwards this to the Verifier program via CPI
    /// for cryptographic validation; Phase 42a stubs the CPI and the
    /// validation path errors `VerifierCpiNotImplemented` (per O11 in
    /// the soothsayer methodology log §2; v0 ships always-CPI on devnet).
    pub signed_report_blob: Vec<u8>,
}

/// Wire payload for `rotate_writer_set`. Replaces the active writer
/// keypair list. Slots beyond `n_writers` must be `Pubkey::default()`.
#[derive(AnchorSerialize, AnchorDeserialize, Clone, Debug)]
pub struct RotateWriterSetPayload {
    pub n_writers: u8,
    pub writers: [Pubkey; MAX_WRITERS],
}
