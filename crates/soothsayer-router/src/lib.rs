//! Unified-feed router types.
//!
//! This crate implements the `unified_feed_receipt.v1` schema locked in the
//! 2026-04-28 (morning) entry of `reports/methodology_history.md`, plus
//! supporting enums and validation primitives for the Layer 0 multi-upstream
//! aggregator (locked 2026-04-28 (afternoon) + (midday) entries).
//!
//! The receipt is the soothsayer-router product's *trust primitive*: every
//! consumer integration is built against the [`UnifiedFeedReceipt`] tuple,
//! and breaking changes require a v2 program PDA per the methodology lock.
//!
//! Phase 1 step 1 of the router build sequence — types only. Filters,
//! regime detection, and the on-chain CPI logic land in subsequent steps.

pub mod receipt;

pub use receipt::{
    AggregateMethod, ClosedMarketRegime, DeviationHit, ExclusionReason, Forecaster, QualityFlag,
    Regime, UnifiedFeedReceipt, UpstreamKind, UpstreamReceipt, ValidationError, SCHEMA_VERSION,
};
