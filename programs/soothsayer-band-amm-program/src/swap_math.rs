//! Pure swap math, host-runnable for fast unit tests. No Anchor / Solana
//! types, no I/O — just integers in, integers out. Day 2 will fill in the
//! body; Day 1 keeps stubs that compile + a single sanity test.
//!
//! Conventions:
//! - All token amounts are `u64` (SPL convention).
//! - All band prices are `i64` at the band's published `exponent` — caller is
//!   responsible for matching exponents across the pool's two legs (base price
//!   in quote terms is implied by the band exponent + USDC's 6-decimal mint).
//! - Fees are `u16` basis points; arithmetic is checked.

use core::cmp::Ordering;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Side {
    /// Caller pays base, receives quote.
    BaseIn,
    /// Caller pays quote, receives base.
    QuoteIn,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FeeTier {
    InBand,
    OutOfBand,
}

#[derive(Debug, PartialEq, Eq)]
pub enum SwapMathError {
    ZeroAmountIn,
    InsufficientReserves,
    Overflow,
    InvertedBand,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SwapQuote {
    pub amount_out: u64,
    pub fee_paid: u64,
    pub fee_tier: FeeTier,
    pub effective_fee_bps: u32,
}

/// Day-1 stub: real implementation lands Day 2. Kept here so `lib.rs` can
/// import without conditional compilation, and the unit-test module already
/// has a target to expand.
#[allow(clippy::too_many_arguments)]
pub fn quote_swap(
    _reserves_base: u64,
    _reserves_quote: u64,
    _amount_in: u64,
    _side: Side,
    _band_lower: i64,
    _band_upper: i64,
    _fee_bps_in: u16,
    _fee_alpha_out_bps: u16,
    _fee_w_max_bps: u16,
) -> Result<SwapQuote, SwapMathError> {
    Err(SwapMathError::Overflow) // Day-2 placeholder.
}

/// Order an inverted band as a precondition check. Pure helper.
pub fn band_orientation(lower: i64, upper: i64) -> Ordering {
    lower.cmp(&upper)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn day1_stub_returns_overflow() {
        // Day-1 placeholder behaviour. Replaced Day 2 with real math + tests.
        let r = quote_swap(1_000, 1_000, 100, Side::BaseIn, 95, 105, 5, 30, 10_000);
        assert_eq!(r, Err(SwapMathError::Overflow));
    }

    #[test]
    fn band_orientation_detects_inversion() {
        assert_eq!(band_orientation(10, 20), Ordering::Less);
        assert_eq!(band_orientation(20, 10), Ordering::Greater);
        assert_eq!(band_orientation(15, 15), Ordering::Equal);
    }
}
