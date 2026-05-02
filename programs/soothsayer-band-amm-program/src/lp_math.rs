//! Pure LP accounting math, host-runnable for unit tests. Mirror of Uniswap V2:
//!
//! - **First deposit**: `lp_minted = isqrt(amount_base · amount_quote)`. Sets
//!   the pool's price ratio.
//! - **Subsequent deposit**: `lp_minted = min(amount_base · supply / r_base,
//!   amount_quote · supply / r_quote)`. The contract takes only the prorata
//!   amounts and returns the leftover to the depositor implicitly (the
//!   handler only transfers `base_used` + `quote_used` from the user).
//! - **Withdraw**: `(base_out, quote_out) = (lp · r_base / supply, lp · r_quote
//!   / supply)`. Rounds *down* — never gives the user more than their prorata
//!   share. The discarded fractional atoms stay in the pool, accruing to
//!   remaining LPs (Uniswap-V2-equivalent behaviour).
//!
//! All intermediate arithmetic is u128. Returns are u64 to fit SPL.

#[derive(Debug, PartialEq, Eq)]
pub enum LpMathError {
    ZeroAmount,
    ZeroLpSupplyWithReserves,
    Overflow,
    InsufficientReserves,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DepositPlan {
    pub lp_minted: u64,
    /// Atoms of base that should be transferred from depositor to pool.
    pub base_used: u64,
    /// Atoms of quote that should be transferred from depositor to pool.
    pub quote_used: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct WithdrawPlan {
    pub base_out: u64,
    pub quote_out: u64,
}

/// First-ever deposit into a pool. Sets the initial LP supply.
///
/// Both amounts must be > 0. The caller's chosen ratio becomes the pool's
/// price ratio — there is no oracle anchor at first deposit. Subsequent
/// arbitrage corrects toward the band.
pub fn lp_for_first_deposit(amount_base: u64, amount_quote: u64) -> Result<u64, LpMathError> {
    if amount_base == 0 || amount_quote == 0 {
        return Err(LpMathError::ZeroAmount);
    }
    let prod = (amount_base as u128)
        .checked_mul(amount_quote as u128)
        .ok_or(LpMathError::Overflow)?;
    Ok(isqrt_u128(prod) as u64)
}

/// Subsequent deposit. Returns the prorata `lp_minted` plus the actual
/// `base_used` / `quote_used` to transfer.
///
/// The depositor passes a *max* `(amount_base, amount_quote)`. We pick the
/// side that mints the smaller LP and use that side's amount in full; the
/// other side is scaled prorata. Leftover stays with the user.
pub fn lp_for_subsequent_deposit(
    amount_base: u64,
    amount_quote: u64,
    reserves_base: u64,
    reserves_quote: u64,
    lp_supply: u64,
) -> Result<DepositPlan, LpMathError> {
    if amount_base == 0 || amount_quote == 0 {
        return Err(LpMathError::ZeroAmount);
    }
    if reserves_base == 0 || reserves_quote == 0 {
        return Err(LpMathError::InsufficientReserves);
    }
    if lp_supply == 0 {
        return Err(LpMathError::ZeroLpSupplyWithReserves);
    }

    let lp_from_base = (amount_base as u128)
        .checked_mul(lp_supply as u128)
        .ok_or(LpMathError::Overflow)?
        / reserves_base as u128;
    let lp_from_quote = (amount_quote as u128)
        .checked_mul(lp_supply as u128)
        .ok_or(LpMathError::Overflow)?
        / reserves_quote as u128;

    let lp_minted_u128 = lp_from_base.min(lp_from_quote);
    if lp_minted_u128 == 0 {
        return Err(LpMathError::ZeroAmount);
    }
    let lp_minted = lp_minted_u128 as u64;

    let base_used = lp_minted_u128
        .checked_mul(reserves_base as u128)
        .ok_or(LpMathError::Overflow)?
        / lp_supply as u128;
    let quote_used = lp_minted_u128
        .checked_mul(reserves_quote as u128)
        .ok_or(LpMathError::Overflow)?
        / lp_supply as u128;

    Ok(DepositPlan {
        lp_minted,
        base_used: base_used as u64,
        quote_used: quote_used as u64,
    })
}

/// Withdraw a prorata share of the pool. Rounds DOWN (user disadvantage by
/// 0–1 atom; never advantage). Caller is responsible for the LP burn IX.
pub fn redeem_lp(
    lp_amount: u64,
    reserves_base: u64,
    reserves_quote: u64,
    lp_supply: u64,
) -> Result<WithdrawPlan, LpMathError> {
    if lp_amount == 0 {
        return Err(LpMathError::ZeroAmount);
    }
    if lp_supply == 0 {
        return Err(LpMathError::ZeroLpSupplyWithReserves);
    }
    if lp_amount > lp_supply {
        return Err(LpMathError::Overflow);
    }
    let base_out = (lp_amount as u128)
        .checked_mul(reserves_base as u128)
        .ok_or(LpMathError::Overflow)?
        / lp_supply as u128;
    let quote_out = (lp_amount as u128)
        .checked_mul(reserves_quote as u128)
        .ok_or(LpMathError::Overflow)?
        / lp_supply as u128;
    Ok(WithdrawPlan {
        base_out: base_out as u64,
        quote_out: quote_out as u64,
    })
}

/// Integer square root via Newton's method. u128 → u128.
pub fn isqrt_u128(n: u128) -> u128 {
    if n == 0 {
        return 0;
    }
    let mut x = n;
    let mut y = (x + 1) / 2;
    while y < x {
        x = y;
        y = (x + n / x) / 2;
    }
    x
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn isqrt_basic() {
        assert_eq!(isqrt_u128(0), 0);
        assert_eq!(isqrt_u128(1), 1);
        assert_eq!(isqrt_u128(4), 2);
        assert_eq!(isqrt_u128(99), 9);
        assert_eq!(isqrt_u128(100), 10);
        assert_eq!(isqrt_u128(101), 10);
        assert_eq!(isqrt_u128(10_000), 100);
    }

    #[test]
    fn first_deposit_uses_geometric_mean() {
        // 1000 * 4000 = 4_000_000; sqrt = 2000.
        let lp = lp_for_first_deposit(1_000, 4_000).unwrap();
        assert_eq!(lp, 2_000);
    }

    #[test]
    fn first_deposit_rejects_zero() {
        assert_eq!(
            lp_for_first_deposit(0, 1_000),
            Err(LpMathError::ZeroAmount)
        );
        assert_eq!(
            lp_for_first_deposit(1_000, 0),
            Err(LpMathError::ZeroAmount)
        );
    }

    #[test]
    fn subsequent_deposit_picks_smaller_side() {
        // Pool: 1000 base / 4000 quote / 2000 lp_supply.
        // User offers 100 base + 500 quote. Ratio implied:
        //   lp_from_base  = 100 * 2000 / 1000 = 200
        //   lp_from_quote = 500 * 2000 / 4000 = 250
        // Min = 200. base_used = 200 * 1000 / 2000 = 100; quote_used = 200 * 4000 / 2000 = 400.
        let plan = lp_for_subsequent_deposit(100, 500, 1_000, 4_000, 2_000).unwrap();
        assert_eq!(plan.lp_minted, 200);
        assert_eq!(plan.base_used, 100);
        assert_eq!(plan.quote_used, 400);
    }

    #[test]
    fn subsequent_deposit_exact_ratio_uses_full_amounts() {
        // Pool: 1000/4000/2000. User offers 200+800 (exact ratio).
        // Both sides: lp = 200 * 2000 / 1000 = 400; lp = 800 * 2000 / 4000 = 400.
        let plan = lp_for_subsequent_deposit(200, 800, 1_000, 4_000, 2_000).unwrap();
        assert_eq!(plan.lp_minted, 400);
        assert_eq!(plan.base_used, 200);
        assert_eq!(plan.quote_used, 800);
    }

    #[test]
    fn redeem_lp_returns_prorata() {
        // Pool: 1000/4000/2000. Withdraw 500 LP.
        // base_out = 500 * 1000 / 2000 = 250; quote_out = 500 * 4000 / 2000 = 1000.
        let plan = redeem_lp(500, 1_000, 4_000, 2_000).unwrap();
        assert_eq!(plan.base_out, 250);
        assert_eq!(plan.quote_out, 1_000);
    }

    #[test]
    fn redeem_lp_rounds_down() {
        // Pool: 1001/4003/2000. Withdraw 1 LP.
        // base_out = 1 * 1001 / 2000 = 0 (rounded down). quote_out = 4003 / 2000 = 2.
        let plan = redeem_lp(1, 1_001, 4_003, 2_000).unwrap();
        assert_eq!(plan.base_out, 0);
        assert_eq!(plan.quote_out, 2);
    }

    #[test]
    fn redeem_lp_rejects_over_supply() {
        assert_eq!(
            redeem_lp(2_001, 1_000, 4_000, 2_000),
            Err(LpMathError::Overflow)
        );
    }

    #[test]
    fn deposit_then_withdraw_returns_close_to_input() {
        // First deposit: 1000 / 4000 → lp = 2000.
        // Withdraw all: should return ~exactly 1000 / 4000.
        let lp = lp_for_first_deposit(1_000, 4_000).unwrap();
        let plan = redeem_lp(lp, 1_000, 4_000, lp).unwrap();
        assert_eq!(plan.base_out, 1_000);
        assert_eq!(plan.quote_out, 4_000);
    }
}
