//! Program error codes for the BandAMM. Append-only — clients cache code→reason
//! mappings. Never insert in the middle of the enum.

use anchor_lang::prelude::*;

#[error_code]
pub enum BandAmmError {
    #[msg("pool is paused by authority")]
    PoolPaused, // 0

    #[msg("oracle band PDA failed discriminator / version / invariant check")]
    BandRejected, // 1

    #[msg("oracle band is stale (publish_ts older than max_band_staleness_secs)")]
    BandStale, // 2

    #[msg("oracle band PDA does not match the pool's configured price_update")]
    WrongPriceUpdate, // 3

    #[msg("zero amount in")]
    ZeroAmountIn, // 4

    #[msg("amount in exceeds pool reserves of input token")]
    InsufficientReserves, // 5

    #[msg("output below caller's min_amount_out")]
    SlippageExceeded, // 6

    #[msg("deposit amounts do not match the pool's current reserve ratio")]
    DepositRatioMismatch, // 7

    #[msg("withdraw amount exceeds caller's LP balance")]
    InsufficientLp, // 8

    #[msg("checked arithmetic overflow")]
    MathOverflow, // 9

    #[msg("fee parameter out of range (bps must be ≤ 10000; alpha ≤ 65535)")]
    FeeParamOutOfRange, // 10

    #[msg("max staleness must be in (0, 86400] seconds")]
    StalenessParamOutOfRange, // 11

    #[msg("base mint and quote mint must differ")]
    DuplicateMint, // 12

    #[msg("non-authority caller for authority-gated instruction")]
    Unauthorized, // 13
}
