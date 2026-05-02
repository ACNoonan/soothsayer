//! Pure swap math, host-runnable for fast unit tests. No Anchor / Solana
//! types, no I/O — just integers in, integers out. Pulled into the BPF
//! program by `lib.rs::swap`; run on the host by `cargo test --lib`.
//!
//! # Conventions
//!
//! - Token amounts are `u64` (SPL convention) at IX boundaries; intermediate
//!   arithmetic widens to `u128` to keep checked-mul on a normalized basis.
//! - Band prices are `i64` at the band's published `exponent`. The pool stores
//!   `base_decimals` + `quote_decimals` (mint decimals). The "atom-ratio"
//!   `reserves_quote / reserves_base` is compared against
//!   `band_value · 10^k` where `k = quote_decimals − base_decimals + exponent`.
//!   Cross-products avoid any division.
//! - Fees are `u16` basis points, checked.
//!
//! # Fee branch
//!
//! 1. Quote with `fee_bps_in`. Compute post-swap reserves and post-price.
//! 2. If post-price ∈ `[lower, upper]` (in normalized space): tier = `InBand`;
//!    return `f_in` quote.
//! 3. Else compute `d = max(lo·b_norm − q_norm, q_norm − hi·b_norm)` (always ≥ 0
//!    in this branch) and `w = (hi − lo) · b_norm`. Surcharge ramp:
//!    `surcharge_bps = α_out · clamp(d·10_000 / w, 0, w_max) / 10_000`.
//!    Re-quote with `effective_fee = f_in + surcharge`. Tier = `OutOfBand`.
//!
//! Single re-quote, deliberately. The *intent* distance (the post-price under
//! `f_in`) is the surcharge basis. The actual post-price under `f_out` will
//! land closer to the band but we charge based on intent. This is documented
//! and matches the brief's §3.1 spec; iterating to a fixed point is brittle
//! and not worth the BPF compute cost for the hackathon.

use core::cmp::{max, Ordering};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Side {
    /// Caller pays base, receives quote. Pushes pool price toward `lower`.
    BaseIn,
    /// Caller pays quote, receives base. Pushes pool price toward `upper`.
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
    NegativeBandValue,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SwapQuote {
    pub amount_out: u64,
    /// Fee paid in input-token atoms.
    pub fee_paid: u64,
    pub fee_tier: FeeTier,
    /// Effective fee charged in basis points. For `InBand`: == `fee_bps_in`.
    /// For `OutOfBand`: == `fee_bps_in + surcharge`.
    pub effective_fee_bps: u32,
    /// Post-swap reserves after this swap is applied. Caller writes these
    /// back to the pool. Always returned consistent with `amount_out`.
    pub reserves_base_post: u64,
    pub reserves_quote_post: u64,
}

#[allow(clippy::too_many_arguments)]
pub fn quote_swap(
    reserves_base: u64,
    reserves_quote: u64,
    amount_in: u64,
    side: Side,
    band_lower: i64,
    band_upper: i64,
    band_exponent: i8,
    base_decimals: u8,
    quote_decimals: u8,
    fee_bps_in: u16,
    fee_alpha_out_bps: u16,
    fee_w_max_bps: u16,
) -> Result<SwapQuote, SwapMathError> {
    if amount_in == 0 {
        return Err(SwapMathError::ZeroAmountIn);
    }
    match band_lower.cmp(&band_upper) {
        Ordering::Greater => return Err(SwapMathError::InvertedBand),
        _ => {}
    }
    if band_lower < 0 {
        return Err(SwapMathError::NegativeBandValue);
    }

    // ── 1. First-pass quote with f_in.
    let (out_in_band, reserves_b_post_inb, reserves_q_post_inb, _) =
        cpmm_quote(reserves_base, reserves_quote, amount_in, side, fee_bps_in)?;

    // ── 2. Is the post-price in band?
    let in_band = post_price_in_band(
        reserves_b_post_inb,
        reserves_q_post_inb,
        band_lower as u128,
        band_upper as u128,
        band_exponent,
        base_decimals,
        quote_decimals,
    )?;

    if in_band {
        let fee_paid = compute_fee_paid(amount_in, fee_bps_in)?;
        return Ok(SwapQuote {
            amount_out: out_in_band,
            fee_paid,
            fee_tier: FeeTier::InBand,
            effective_fee_bps: fee_bps_in as u32,
            reserves_base_post: reserves_b_post_inb,
            reserves_quote_post: reserves_q_post_inb,
        });
    }

    // ── 3. Out-of-band: compute surcharge from intent distance.
    let surcharge_bps = surcharge_from_distance(
        reserves_b_post_inb,
        reserves_q_post_inb,
        band_lower as u128,
        band_upper as u128,
        band_exponent,
        base_decimals,
        quote_decimals,
        fee_alpha_out_bps,
        fee_w_max_bps,
    )?;

    // Cap effective fee at 9_999 bps so the user always receives at least one
    // atom (avoids accidental zero-output divides in extreme tail).
    let effective_fee_bps = (fee_bps_in as u32 + surcharge_bps).min(9_999);

    // ── 4. Re-quote with f_out.
    let (out_out_band, reserves_b_post_out, reserves_q_post_out, _) = cpmm_quote(
        reserves_base,
        reserves_quote,
        amount_in,
        side,
        effective_fee_bps as u16,
    )?;

    let fee_paid = compute_fee_paid(amount_in, effective_fee_bps as u16)?;

    Ok(SwapQuote {
        amount_out: out_out_band,
        fee_paid,
        fee_tier: FeeTier::OutOfBand,
        effective_fee_bps,
        reserves_base_post: reserves_b_post_out,
        reserves_quote_post: reserves_q_post_out,
    })
}

/// CPMM quote with fee-on-input. Returns `(amount_out, reserves_base_post,
/// reserves_quote_post, amount_in_after_fee)`. Standard Uniswap V2 math:
///
/// ```text
/// Δin_after_fee = Δin · (10_000 − fee_bps) / 10_000
/// Δout = reserves_out · Δin_after_fee / (reserves_in + Δin_after_fee)
/// reserves_in_post  = reserves_in  + Δin           (full Δin retained — fees stay in pool)
/// reserves_out_post = reserves_out − Δout
/// ```
fn cpmm_quote(
    reserves_base: u64,
    reserves_quote: u64,
    amount_in: u64,
    side: Side,
    fee_bps: u16,
) -> Result<(u64, u64, u64, u64), SwapMathError> {
    if fee_bps > 10_000 {
        return Err(SwapMathError::Overflow);
    }
    let (reserve_in, reserve_out) = match side {
        Side::BaseIn => (reserves_base, reserves_quote),
        Side::QuoteIn => (reserves_quote, reserves_base),
    };
    if reserve_in == 0 || reserve_out == 0 {
        return Err(SwapMathError::InsufficientReserves);
    }

    let amount_in_u128 = amount_in as u128;
    let amount_in_after_fee = amount_in_u128
        .checked_mul(10_000u128 - fee_bps as u128)
        .ok_or(SwapMathError::Overflow)?
        / 10_000u128;

    let numerator = (reserve_out as u128)
        .checked_mul(amount_in_after_fee)
        .ok_or(SwapMathError::Overflow)?;
    let denominator = (reserve_in as u128)
        .checked_add(amount_in_after_fee)
        .ok_or(SwapMathError::Overflow)?;
    if denominator == 0 {
        return Err(SwapMathError::InsufficientReserves);
    }
    let amount_out_u128 = numerator / denominator;
    if amount_out_u128 >= reserve_out as u128 {
        // Output cannot drain the pool (CPMM ensures this in the limit, but
        // pathological rounding could).
        return Err(SwapMathError::InsufficientReserves);
    }
    let amount_out = amount_out_u128 as u64;

    let reserve_in_post = reserve_in
        .checked_add(amount_in)
        .ok_or(SwapMathError::Overflow)?;
    let reserve_out_post = reserve_out - amount_out; // checked above

    let (reserves_base_post, reserves_quote_post) = match side {
        Side::BaseIn => (reserve_in_post, reserve_out_post),
        Side::QuoteIn => (reserve_out_post, reserve_in_post),
    };

    Ok((
        amount_out,
        reserves_base_post,
        reserves_quote_post,
        amount_in_after_fee as u64,
    ))
}

/// Compute the fee paid (in input-token atoms) for a given `amount_in` and
/// fee bps. Defined so the unit tests can assert on the exact fee, and so the
/// receipt event in `lib.rs` can report it.
fn compute_fee_paid(amount_in: u64, fee_bps: u16) -> Result<u64, SwapMathError> {
    if fee_bps > 10_000 {
        return Err(SwapMathError::Overflow);
    }
    let amount_in_u128 = amount_in as u128;
    let after_fee = amount_in_u128
        .checked_mul(10_000u128 - fee_bps as u128)
        .ok_or(SwapMathError::Overflow)?
        / 10_000u128;
    Ok(amount_in_u128.saturating_sub(after_fee) as u64)
}

/// Cross-product comparison: is `reserves_quote / reserves_base ∈
/// [lower, upper] · 10^k`, where `k = quote_decimals − base_decimals + exponent`?
///
/// Normalization:
/// - `q_norm = reserves_quote · 10^max(0, −k)`
/// - `b_norm = reserves_base  · 10^max(0,  k)`
/// - Compare `lower · b_norm ≤ q_norm ≤ upper · b_norm`.
fn post_price_in_band(
    reserves_base_post: u64,
    reserves_quote_post: u64,
    band_lower: u128,
    band_upper: u128,
    band_exponent: i8,
    base_decimals: u8,
    quote_decimals: u8,
) -> Result<bool, SwapMathError> {
    let (q_norm, b_norm) =
        normalize_post_reserves(reserves_base_post, reserves_quote_post, band_exponent, base_decimals, quote_decimals)?;
    let lo_x_b = band_lower
        .checked_mul(b_norm)
        .ok_or(SwapMathError::Overflow)?;
    let hi_x_b = band_upper
        .checked_mul(b_norm)
        .ok_or(SwapMathError::Overflow)?;
    Ok(lo_x_b <= q_norm && q_norm <= hi_x_b)
}

/// Compute the surcharge in basis points from the intent post-price's signed
/// distance from the band, as a fraction of band width, slope `α`, saturated
/// at `w_max`. Returned value is `surcharge_bps`, *not* the effective fee.
#[allow(clippy::too_many_arguments)]
fn surcharge_from_distance(
    reserves_base_post: u64,
    reserves_quote_post: u64,
    band_lower: u128,
    band_upper: u128,
    band_exponent: i8,
    base_decimals: u8,
    quote_decimals: u8,
    alpha_out_bps: u16,
    w_max_bps: u16,
) -> Result<u32, SwapMathError> {
    let (q_norm, b_norm) =
        normalize_post_reserves(reserves_base_post, reserves_quote_post, band_exponent, base_decimals, quote_decimals)?;
    let lo_x_b = band_lower
        .checked_mul(b_norm)
        .ok_or(SwapMathError::Overflow)?;
    let hi_x_b = band_upper
        .checked_mul(b_norm)
        .ok_or(SwapMathError::Overflow)?;

    let d_below = lo_x_b.saturating_sub(q_norm);
    let d_above = q_norm.saturating_sub(hi_x_b);
    let d = max(d_below, d_above);

    let width_x_b = band_upper
        .saturating_sub(band_lower)
        .checked_mul(b_norm)
        .ok_or(SwapMathError::Overflow)?;

    let clamped_bps: u128 = if width_x_b == 0 {
        // Degenerate band (lower == upper, and post != lower): saturate.
        w_max_bps as u128
    } else {
        // d/w in bps, clamped to w_max. Use checked_mul; on overflow saturate.
        match d.checked_mul(10_000u128) {
            Some(num) => (num / width_x_b).min(w_max_bps as u128),
            None => w_max_bps as u128, // d so large it overflows — saturate.
        }
    };

    // surcharge_bps = α · clamped / 10_000  (slope · clamped fraction).
    let surcharge = (alpha_out_bps as u128)
        .checked_mul(clamped_bps)
        .ok_or(SwapMathError::Overflow)?
        / 10_000u128;
    Ok(surcharge as u32)
}

/// Compute `(q_norm, b_norm)` such that `q_norm / b_norm` corresponds 1:1 to
/// the band-fixed-point price (no scale).
fn normalize_post_reserves(
    reserves_base_post: u64,
    reserves_quote_post: u64,
    band_exponent: i8,
    base_decimals: u8,
    quote_decimals: u8,
) -> Result<(u128, u128), SwapMathError> {
    if reserves_base_post == 0 {
        return Err(SwapMathError::InsufficientReserves);
    }
    let k: i32 = quote_decimals as i32 - base_decimals as i32 + band_exponent as i32;
    let (q_pow, b_pow) = if k >= 0 { (0u32, k as u32) } else { ((-k) as u32, 0u32) };
    if q_pow > 30 || b_pow > 30 {
        // 10^31 already exceeds u128/2; abort before lossy multiply.
        return Err(SwapMathError::Overflow);
    }
    let q_norm = (reserves_quote_post as u128)
        .checked_mul(pow10_u128(q_pow))
        .ok_or(SwapMathError::Overflow)?;
    let b_norm = (reserves_base_post as u128)
        .checked_mul(pow10_u128(b_pow))
        .ok_or(SwapMathError::Overflow)?;
    Ok((q_norm, b_norm))
}

fn pow10_u128(p: u32) -> u128 {
    let mut x: u128 = 1;
    for _ in 0..p {
        x = x.saturating_mul(10);
    }
    x
}

// ─────────────────────────────────── tests ───────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Helper: SPYx-USDC-shaped pool. base=8 decimals, quote=6 decimals,
    /// band exponent=−8. So `k = 6 − 8 + (−8) = −10`.
    /// Band point=70_000_000_000 (= $700.00). Reserves chosen so
    /// pool-implied price ≈ $700: 1000 SPYx atoms = 10^11; quote atoms
    /// for 700 USDC × 1000 SPYx? Not 1000; let's use 10 SPYx and 7000 USDC:
    /// reserves_base = 10·10^8 = 10^9. reserves_quote = 7000·10^6 = 7·10^9.
    /// q_norm = 7·10^9 · 10^10 = 7·10^19. b_norm = 10^9.
    /// q_norm / b_norm = 7·10^10 == band point. ✓
    fn spyx_pool_inputs() -> (u64, u64, i8, u8, u8) {
        (1_000_000_000, 7_000_000_000, -8i8, 8u8, 6u8)
    }

    #[test]
    fn day1_legacy_invariants_still_apply() {
        // Inverted band still rejected.
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let r = quote_swap(rb, rq, 1_000, Side::BaseIn, 71_000_000_000, 69_000_000_000, exp, b_dec, q_dec, 5, 30, 10_000);
        assert_eq!(r, Err(SwapMathError::InvertedBand));
    }

    #[test]
    fn zero_amount_in_rejected() {
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let r = quote_swap(rb, rq, 0, Side::BaseIn, 69_000_000_000, 71_000_000_000, exp, b_dec, q_dec, 5, 30, 10_000);
        assert_eq!(r, Err(SwapMathError::ZeroAmountIn));
    }

    #[test]
    fn swap_inside_band_charges_f_in() {
        // Tight band well around $700, tiny swap → post-price barely moves → in band.
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let q = quote_swap(rb, rq, 1_000_000, Side::BaseIn, 69_000_000_000, 71_000_000_000, exp, b_dec, q_dec, 5, 30, 10_000).unwrap();
        assert_eq!(q.fee_tier, FeeTier::InBand);
        assert_eq!(q.effective_fee_bps, 5);
        // Output must be positive and less than constant-product no-fee bound.
        assert!(q.amount_out > 0);
        assert!(q.amount_out < (rq as u128 * 1_000_000u128 / (rb as u128 + 1_000_000u128)) as u64);
    }

    #[test]
    fn swap_exits_band_charges_f_out() {
        // Swap a large fraction of base reserves; post-price should drop hard
        // and exit the lower band.
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let big = rb / 10; // 10% of base reserves
        // tight band — pre-swap $700; ±2% band.
        let lower = 686_000_000_00; // $686 = 686·1e8
        let upper = 714_000_000_00; // $714
        let q = quote_swap(rb, rq, big, Side::BaseIn, lower, upper, exp, b_dec, q_dec, 5, 100, 10_000).unwrap();
        assert_eq!(q.fee_tier, FeeTier::OutOfBand);
        assert!(q.effective_fee_bps > 5);
        assert!(q.effective_fee_bps <= 5 + 100); // capped at f_in + α
    }

    #[test]
    fn swap_already_outside_band_charges_f_out_from_byte_one() {
        // Pre-swap pool price $700; band is well above ($800–$820). Pre-swap
        // already out-of-band on the lower side. Even a tiny swap stays out.
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let lower = 800_000_000_00;
        let upper = 820_000_000_00;
        let q = quote_swap(rb, rq, 1_000_000, Side::BaseIn, lower, upper, exp, b_dec, q_dec, 5, 50, 10_000).unwrap();
        assert_eq!(q.fee_tier, FeeTier::OutOfBand);
    }

    #[test]
    fn fee_alpha_zero_collapses_to_flat_fee() {
        // α=0: surcharge is identically 0 regardless of d/w.
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let big = rb / 10;
        let lower = 686_000_000_00;
        let upper = 714_000_000_00;
        let q = quote_swap(rb, rq, big, Side::BaseIn, lower, upper, exp, b_dec, q_dec, 5, 0, 10_000).unwrap();
        assert_eq!(q.fee_tier, FeeTier::OutOfBand);
        assert_eq!(q.effective_fee_bps, 5); // f_in + 0 = 5
    }

    #[test]
    fn surcharge_saturates_at_w_max() {
        // Ridiculously narrow band, big swap — d/w >> w_max, so surcharge
        // saturates at α · w_max / 10_000.
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let big = rb / 5;
        let lower = 699_990_000_00;
        let upper = 700_010_000_00;
        let q = quote_swap(rb, rq, big, Side::BaseIn, lower, upper, exp, b_dec, q_dec, 5, 200, 5_000).unwrap();
        // saturated: surcharge = 200 · 5_000 / 10_000 = 100. Effective = 5 + 100 = 105.
        assert_eq!(q.effective_fee_bps, 5 + 100);
    }

    #[test]
    fn swap_quote_in_pushes_price_up_and_can_exit_upper() {
        // Symmetry test: quote → base swap pushes price toward upper edge.
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let big_q = rq / 10;
        let lower = 686_000_000_00;
        let upper = 714_000_000_00;
        let q = quote_swap(rb, rq, big_q, Side::QuoteIn, lower, upper, exp, b_dec, q_dec, 5, 100, 10_000).unwrap();
        assert_eq!(q.fee_tier, FeeTier::OutOfBand);
        // Post-quote-reserves should have INCREASED quote, DECREASED base.
        assert!(q.reserves_quote_post > rq);
        assert!(q.reserves_base_post < rb);
    }

    #[test]
    fn reserves_post_consistent_with_amount_out() {
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let amt_in = 5_000_000;
        let q = quote_swap(rb, rq, amt_in, Side::BaseIn, 600_000_000_00, 800_000_000_00, exp, b_dec, q_dec, 5, 30, 10_000).unwrap();
        // base_in=full amt_in; quote_out=amount_out.
        assert_eq!(q.reserves_base_post, rb + amt_in);
        assert_eq!(q.reserves_quote_post, rq - q.amount_out);
    }

    #[test]
    fn cpmm_invariant_grows_after_fee() {
        // k = reserves_base · reserves_quote should never DECREASE after a
        // swap with non-zero fee.
        let (rb, rq, exp, b_dec, q_dec) = spyx_pool_inputs();
        let amt_in = 2_000_000;
        let q = quote_swap(rb, rq, amt_in, Side::BaseIn, 600_000_000_00, 800_000_000_00, exp, b_dec, q_dec, 30, 30, 10_000).unwrap();
        let k_pre = rb as u128 * rq as u128;
        let k_post = q.reserves_base_post as u128 * q.reserves_quote_post as u128;
        assert!(k_post >= k_pre, "k_post={} should be ≥ k_pre={}", k_post, k_pre);
    }

    #[test]
    fn pow10_u128_works() {
        assert_eq!(pow10_u128(0), 1);
        assert_eq!(pow10_u128(1), 10);
        assert_eq!(pow10_u128(10), 10_000_000_000);
    }
}
