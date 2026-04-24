//! Program error codes. Ordered for stability — new errors get appended, never
//! inserted in the middle, so clients can cache error-code→reason mappings.

use anchor_lang::prelude::*;

#[error_code]
pub enum SoothsayerError {
    #[msg("publishing is currently paused by the authority")]
    PublishingPaused, // 0

    #[msg("transaction signer is not the current signer set")]
    SignerNotInSet, // 1

    #[msg("publish rejected: below minimum interval since last publish")]
    CadenceTooFast, // 2

    #[msg("price bounds violate invariants (lower <= point <= upper)")]
    BandInvariantViolated, // 3

    #[msg("coverage / buffer basis points out of range")]
    CoverageOutOfRange, // 4

    #[msg("exponent out of supported range (-12..=0)")]
    ExponentOutOfRange, // 5

    #[msg("symbol payload does not match PriceUpdate PDA seeds")]
    SymbolMismatch, // 6

    #[msg("unsupported payload version")]
    UnsupportedVersion, // 7
}
