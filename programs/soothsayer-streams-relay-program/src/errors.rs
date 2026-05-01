//! Program error codes for soothsayer-streams-relay-program. Append-only —
//! new errors get added at the end so clients can cache code → reason
//! mappings across upgrades.

use anchor_lang::prelude::*;

#[error_code]
pub enum RelayError {
    #[msg("relay is currently paused by the authority")]
    RelayPaused, // 0

    #[msg("transaction signer is not the configured authority")]
    NotAuthority, // 1

    #[msg("transaction signer is not in the active writer set")]
    NotInWriterSet, // 2

    #[msg("feed_id payload does not match the relay PDA seed")]
    FeedIdMismatch, // 3

    #[msg("feed has not been registered with add_feed")]
    UnknownFeed, // 4

    #[msg("feed registration limit reached")]
    TooManyFeeds, // 5

    #[msg("writer set is full; rotate_writer_set to evict before adding")]
    WriterSetFull, // 6

    #[msg("schema_decoded_from value is not a recognised Chainlink schema id")]
    UnsupportedSchemaId, // 7

    #[msg("market_status_code is out of range")]
    MarketStatusOutOfRange, // 8

    #[msg("Verifier CPI is required but the verification result was not provided")]
    VerifierResultMissing, // 9

    #[msg("Verifier CPI failed: signed-report validation rejected the payload")]
    VerifierRejected, // 10

    #[msg("submitted post is older than the currently-stored post for this feed")]
    StalePost, // 11

    #[msg("relay schema version is not supported by this program")]
    UnsupportedVersion, // 12

    #[msg("exponent out of supported range (-12..=0)")]
    ExponentOutOfRange, // 13

    /// Reserved for backward compatibility — Phase 42a used this for the
    /// stubbed CPI path. Phase 42b replaced the stub with the real Chainlink
    /// Verifier CPI; failures now surface as `VerifierRejected` (code 10).
    /// Discriminant retained at 14 so historical client error-code mappings
    /// continue to resolve cleanly.
    #[msg("Verifier CPI is not implemented (legacy Phase 42a stub; superseded by VerifierRejected)")]
    VerifierCpiNotImplemented, // 14
}
