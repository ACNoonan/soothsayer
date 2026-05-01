//! Program error codes. Append-only — new errors get added at the end so
//! clients can cache error-code → reason mappings across upgrades.

use anchor_lang::prelude::*;

#[error_code]
pub enum RouterError {
    #[msg("router is currently paused by the authority")]
    RouterPaused, // 0

    #[msg("per-asset feed is currently paused")]
    AssetPaused, // 1

    #[msg("transaction signer is not the configured authority")]
    NotAuthority, // 2

    #[msg("asset is not registered in this router instance")]
    UnknownAsset, // 3

    #[msg("asset_id payload does not match the AssetConfig PDA seed")]
    AssetIdMismatch, // 4

    #[msg("upstream slot count exceeds MAX_UPSTREAMS")]
    TooManyUpstreams, // 5

    #[msg("min_quorum exceeds the number of configured upstreams")]
    QuorumExceedsUpstreamCount, // 6

    #[msg("filter parameter out of permitted range")]
    FilterParameterOutOfRange, // 7

    #[msg("unsupported upstream kind code")]
    UnsupportedUpstreamKind, // 8

    #[msg("regime detection sources disagreed and the asset has no documented fallback")]
    RegimeUndetermined, // 9

    #[msg("upstream account decoding is not implemented yet (Phase 1 step 2b)")]
    UpstreamDecoderNotImplemented, // 10

    #[msg("post-filter quorum dropped below configured min_quorum")]
    QuorumNotMet, // 11

    #[msg("soothsayer band PDA could not be loaded")]
    SoothsayerBandUnavailable, // 12

    #[msg("unsupported snapshot or config schema version")]
    UnsupportedVersion, // 13

    #[msg("band invariants violated: lower <= point <= upper required")]
    BandInvariantViolated, // 14

    #[msg("exponent out of supported range (-12..=0)")]
    ExponentOutOfRange, // 15
}
