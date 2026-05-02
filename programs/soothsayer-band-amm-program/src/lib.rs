//! Soothsayer BandAMM — on-chain program (Day 1 scaffold).
//!
//! Single-active-range AMM whose quoted range tracks the calibrated band
//! published by `soothsayer-oracle-program`. Inside-band swaps charge
//! `fee_bps_in`; outside-band swaps incur a width-scaled surcharge that
//! accrues to LPs.
//!
//! Day-1 deliverable: program compiles, IDL emits, all five instructions wired
//! with correct account constraints. Bodies are stubbed (`Ok(())` after
//! validation) — Day 2 fills in `swap` math + SPL transfers, Day 3 wires the
//! receipt event + staleness guard.
//!
//! Cross-program data flow (intentional): the AMM does NOT CPI the oracle
//! program. It reads the `PriceUpdate` PDA as a regular account and decodes
//! via `soothsayer_consumer::decode_price_update`. Zero new dependencies on
//! the oracle program crate.

use anchor_lang::prelude::*;
use anchor_spl::token::{self, Burn, Mint, MintTo, Token, TokenAccount, Transfer};

pub mod errors;
pub mod lp_math;
pub mod state;
pub mod swap_math;

use errors::BandAmmError;
use lp_math::{lp_for_first_deposit, lp_for_subsequent_deposit, redeem_lp, LpMathError};
use state::{
    BandAmmPool, BAND_AMM_POOL_VERSION, DEFAULT_FEE_ALPHA_OUT_BPS, DEFAULT_FEE_BPS_IN,
    DEFAULT_FEE_W_MAX_BPS, DEFAULT_MAX_BAND_STALENESS_SECS,
};
use swap_math::{quote_swap, FeeTier, Side, SwapMathError};

declare_id!("7vjG4nuVcpotSBDHPQeonrzuvxbwgDddKzibeLASaqw8");

#[program]
pub mod soothsayer_band_amm_program {
    use super::*;

    /// Create the pool, LP mint, and base/quote vaults. Reads the oracle
    /// `PriceUpdate` account once at init only to lock the binding — the AMM
    /// does NOT require a fresh band at init. Fee params default to the
    /// constants in `state.rs`; rotate via `set_fee_params`.
    pub fn initialize_pool(
        ctx: Context<InitializePool>,
        params: InitializePoolParams,
    ) -> Result<()> {
        require!(
            ctx.accounts.base_mint.key() != ctx.accounts.quote_mint.key(),
            BandAmmError::DuplicateMint
        );

        let fee_bps_in = params.fee_bps_in.unwrap_or(DEFAULT_FEE_BPS_IN);
        let fee_alpha_out_bps = params
            .fee_alpha_out_bps
            .unwrap_or(DEFAULT_FEE_ALPHA_OUT_BPS);
        let fee_w_max_bps = params.fee_w_max_bps.unwrap_or(DEFAULT_FEE_W_MAX_BPS);
        let max_band_staleness_secs = params
            .max_band_staleness_secs
            .unwrap_or(DEFAULT_MAX_BAND_STALENESS_SECS);

        require!(
            fee_bps_in <= 10_000 && fee_w_max_bps <= 10_000,
            BandAmmError::FeeParamOutOfRange
        );
        require!(
            max_band_staleness_secs > 0 && max_band_staleness_secs <= 86_400,
            BandAmmError::StalenessParamOutOfRange
        );

        let pool = &mut ctx.accounts.pool;
        pool.version = BAND_AMM_POOL_VERSION;
        pool.paused = 0;
        pool.pool_bump = ctx.bumps.pool;
        pool.lp_mint_bump = ctx.bumps.lp_mint;
        pool.base_vault_bump = ctx.bumps.base_vault;
        pool.quote_vault_bump = ctx.bumps.quote_vault;
        pool.base_decimals = ctx.accounts.base_mint.decimals;
        pool.quote_decimals = ctx.accounts.quote_mint.decimals;

        pool.authority = params.authority;
        pool.base_mint = ctx.accounts.base_mint.key();
        pool.quote_mint = ctx.accounts.quote_mint.key();
        pool.base_vault = ctx.accounts.base_vault.key();
        pool.quote_vault = ctx.accounts.quote_vault.key();
        pool.lp_mint = ctx.accounts.lp_mint.key();
        pool.price_update = ctx.accounts.price_update.key();

        pool.fee_bps_in = fee_bps_in;
        pool.fee_alpha_out_bps = fee_alpha_out_bps;
        pool.fee_w_max_bps = fee_w_max_bps;
        pool.max_band_staleness_secs = max_band_staleness_secs;
        pool._pad1 = [0; 2];

        pool.cumulative_fees_base = 0;
        pool.cumulative_fees_quote = 0;
        pool.cumulative_swaps = 0;
        pool._pad2 = [0; 16];

        emit!(PoolInitialized {
            pool: pool.key(),
            base_mint: pool.base_mint,
            quote_mint: pool.quote_mint,
            price_update: pool.price_update,
            authority: pool.authority,
            ts: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    /// Deposit liquidity. First deposit (LP supply == 0) sets the initial
    /// pool ratio; subsequent deposits are prorata against current reserves.
    /// Caller passes max amounts; the pool takes the prorata portion that
    /// matches the smaller side and refunds the other implicitly (only
    /// `base_used`/`quote_used` are pulled from the user).
    pub fn deposit(
        ctx: Context<Deposit>,
        amount_base: u64,
        amount_quote: u64,
        min_lp_out: u64,
    ) -> Result<()> {
        require!(ctx.accounts.pool.paused == 0, BandAmmError::PoolPaused);
        require!(
            amount_base > 0 && amount_quote > 0,
            BandAmmError::ZeroAmountIn
        );

        let lp_supply = ctx.accounts.lp_mint.supply;
        let r_base = ctx.accounts.base_vault.amount;
        let r_quote = ctx.accounts.quote_vault.amount;

        let (lp_minted, base_used, quote_used) = if lp_supply == 0 {
            let lp = lp_for_first_deposit(amount_base, amount_quote).map_err(map_lp_err)?;
            (lp, amount_base, amount_quote)
        } else {
            let plan = lp_for_subsequent_deposit(
                amount_base, amount_quote, r_base, r_quote, lp_supply,
            )
            .map_err(map_lp_err)?;
            (plan.lp_minted, plan.base_used, plan.quote_used)
        };

        require!(lp_minted >= min_lp_out, BandAmmError::SlippageExceeded);

        // ── Pull base + quote from user into vaults.
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.user_base.to_account_info(),
                    to: ctx.accounts.base_vault.to_account_info(),
                    authority: ctx.accounts.user.to_account_info(),
                },
            ),
            base_used,
        )?;
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.user_quote.to_account_info(),
                    to: ctx.accounts.quote_vault.to_account_info(),
                    authority: ctx.accounts.user.to_account_info(),
                },
            ),
            quote_used,
        )?;

        // ── Mint LP to user (pool PDA is mint authority).
        let pool_key = ctx.accounts.pool.key();
        let base_mint_key = ctx.accounts.pool.base_mint;
        let quote_mint_key = ctx.accounts.pool.quote_mint;
        let pool_bump = ctx.accounts.pool.pool_bump;
        let _ = pool_key; // for signer-seed clarity; pool is signer.
        let signer_seeds: &[&[&[u8]]] = &[&[
            b"band_amm_pool",
            base_mint_key.as_ref(),
            quote_mint_key.as_ref(),
            &[pool_bump],
        ]];
        token::mint_to(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                MintTo {
                    mint: ctx.accounts.lp_mint.to_account_info(),
                    to: ctx.accounts.user_lp.to_account_info(),
                    authority: ctx.accounts.pool.to_account_info(),
                },
                signer_seeds,
            ),
            lp_minted,
        )?;

        emit!(Deposited {
            pool: pool_key,
            user: ctx.accounts.user.key(),
            base_used,
            quote_used,
            lp_minted,
            ts: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    /// Withdraw a prorata share of the pool reserves. Burns the caller's LP
    /// and transfers `(lp · r / supply)` rounded down for each leg.
    /// Withdrawals are allowed even when the pool is paused — LPs can always
    /// exit their position (matches Test Plan §3.4 policy choice).
    pub fn withdraw(
        ctx: Context<Withdraw>,
        lp_amount: u64,
        min_base_out: u64,
        min_quote_out: u64,
    ) -> Result<()> {
        require!(lp_amount > 0, BandAmmError::ZeroAmountIn);

        let lp_supply = ctx.accounts.lp_mint.supply;
        let r_base = ctx.accounts.base_vault.amount;
        let r_quote = ctx.accounts.quote_vault.amount;

        let plan = redeem_lp(lp_amount, r_base, r_quote, lp_supply).map_err(map_lp_err)?;

        require!(
            plan.base_out >= min_base_out && plan.quote_out >= min_quote_out,
            BandAmmError::SlippageExceeded
        );

        // ── Burn the user's LP first (defence against re-entrancy of any kind).
        token::burn(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Burn {
                    mint: ctx.accounts.lp_mint.to_account_info(),
                    from: ctx.accounts.user_lp.to_account_info(),
                    authority: ctx.accounts.user.to_account_info(),
                },
            ),
            lp_amount,
        )?;

        // ── Transfer base + quote out (pool PDA signs).
        let pool_key = ctx.accounts.pool.key();
        let base_mint_key = ctx.accounts.pool.base_mint;
        let quote_mint_key = ctx.accounts.pool.quote_mint;
        let pool_bump = ctx.accounts.pool.pool_bump;
        let signer_seeds: &[&[&[u8]]] = &[&[
            b"band_amm_pool",
            base_mint_key.as_ref(),
            quote_mint_key.as_ref(),
            &[pool_bump],
        ]];

        if plan.base_out > 0 {
            token::transfer(
                CpiContext::new_with_signer(
                    ctx.accounts.token_program.to_account_info(),
                    Transfer {
                        from: ctx.accounts.base_vault.to_account_info(),
                        to: ctx.accounts.user_base.to_account_info(),
                        authority: ctx.accounts.pool.to_account_info(),
                    },
                    signer_seeds,
                ),
                plan.base_out,
            )?;
        }
        if plan.quote_out > 0 {
            token::transfer(
                CpiContext::new_with_signer(
                    ctx.accounts.token_program.to_account_info(),
                    Transfer {
                        from: ctx.accounts.quote_vault.to_account_info(),
                        to: ctx.accounts.user_quote.to_account_info(),
                        authority: ctx.accounts.pool.to_account_info(),
                    },
                    signer_seeds,
                ),
                plan.quote_out,
            )?;
        }

        emit!(Withdrawn {
            pool: pool_key,
            user: ctx.accounts.user.key(),
            lp_burned: lp_amount,
            base_out: plan.base_out,
            quote_out: plan.quote_out,
            ts: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    /// Swap. Reads the soothsayer `PriceUpdate` PDA, decodes via
    /// `soothsayer-consumer`, validates invariants + staleness, quotes the
    /// trade through `swap_math::quote_swap`, applies SPL transfers, and
    /// emits a receipt event.
    pub fn swap(
        ctx: Context<Swap>,
        amount_in: u64,
        min_amount_out: u64,
        side_base_in: bool,
    ) -> Result<()> {
        require!(ctx.accounts.pool.paused == 0, BandAmmError::PoolPaused);
        require!(amount_in > 0, BandAmmError::ZeroAmountIn);

        // ── Decode the band PDA. `address = pool.price_update` is enforced
        // by the account constraint; here we decode + validate.
        let band = {
            let data = ctx
                .accounts
                .price_update
                .try_borrow_data()
                .map_err(|_| error!(BandAmmError::BandRejected))?;
            let band = soothsayer_consumer::decode_price_update(&data)
                .map_err(|_| error!(BandAmmError::BandRejected))?;
            band.validate_invariants()
                .map_err(|_| error!(BandAmmError::BandRejected))?;
            band
        };

        // ── Staleness guard. Day-2 wires this here; Day-3 adds explicit test
        // coverage in integration tests.
        let now_ts = Clock::get()?.unix_timestamp;
        let age = now_ts.saturating_sub(band.publish_ts);
        require!(
            age <= ctx.accounts.pool.max_band_staleness_secs as i64,
            BandAmmError::BandStale
        );

        // ── Quote the swap.
        let r_base = ctx.accounts.base_vault.amount;
        let r_quote = ctx.accounts.quote_vault.amount;
        let side = if side_base_in { Side::BaseIn } else { Side::QuoteIn };

        let pool_ref = &ctx.accounts.pool;
        let q = quote_swap(
            r_base,
            r_quote,
            amount_in,
            side,
            band.lower,
            band.upper,
            band.exponent,
            pool_ref.base_decimals,
            pool_ref.quote_decimals,
            pool_ref.fee_bps_in,
            pool_ref.fee_alpha_out_bps,
            pool_ref.fee_w_max_bps,
        )
        .map_err(map_swap_err)?;

        require!(
            q.amount_out >= min_amount_out,
            BandAmmError::SlippageExceeded
        );

        // ── Execute transfers. Direction governs which vault pays out; the
        // pool PDA always signs the outflow leg.
        let pool_key = pool_ref.key();
        let base_mint_key = pool_ref.base_mint;
        let quote_mint_key = pool_ref.quote_mint;
        let pool_bump = pool_ref.pool_bump;
        let signer_seeds: &[&[&[u8]]] = &[&[
            b"band_amm_pool",
            base_mint_key.as_ref(),
            quote_mint_key.as_ref(),
            &[pool_bump],
        ]];

        match side {
            Side::BaseIn => {
                // user → vault: base in
                token::transfer(
                    CpiContext::new(
                        ctx.accounts.token_program.to_account_info(),
                        Transfer {
                            from: ctx.accounts.user_base.to_account_info(),
                            to: ctx.accounts.base_vault.to_account_info(),
                            authority: ctx.accounts.user.to_account_info(),
                        },
                    ),
                    amount_in,
                )?;
                // vault → user: quote out
                token::transfer(
                    CpiContext::new_with_signer(
                        ctx.accounts.token_program.to_account_info(),
                        Transfer {
                            from: ctx.accounts.quote_vault.to_account_info(),
                            to: ctx.accounts.user_quote.to_account_info(),
                            authority: ctx.accounts.pool.to_account_info(),
                        },
                        signer_seeds,
                    ),
                    q.amount_out,
                )?;
            }
            Side::QuoteIn => {
                token::transfer(
                    CpiContext::new(
                        ctx.accounts.token_program.to_account_info(),
                        Transfer {
                            from: ctx.accounts.user_quote.to_account_info(),
                            to: ctx.accounts.quote_vault.to_account_info(),
                            authority: ctx.accounts.user.to_account_info(),
                        },
                    ),
                    amount_in,
                )?;
                token::transfer(
                    CpiContext::new_with_signer(
                        ctx.accounts.token_program.to_account_info(),
                        Transfer {
                            from: ctx.accounts.base_vault.to_account_info(),
                            to: ctx.accounts.user_base.to_account_info(),
                            authority: ctx.accounts.pool.to_account_info(),
                        },
                        signer_seeds,
                    ),
                    q.amount_out,
                )?;
            }
        }

        // ── Update cumulative counters. Fee accrues to the input-token leg.
        let pool = &mut ctx.accounts.pool;
        match side {
            Side::BaseIn => {
                pool.cumulative_fees_base = pool
                    .cumulative_fees_base
                    .saturating_add(q.fee_paid);
            }
            Side::QuoteIn => {
                pool.cumulative_fees_quote = pool
                    .cumulative_fees_quote
                    .saturating_add(q.fee_paid);
            }
        }
        pool.cumulative_swaps = pool.cumulative_swaps.saturating_add(1);

        // ── Receipt event. Day 3 expands to the full PriceBand mirror.
        emit!(Swapped {
            pool: pool_key,
            user: ctx.accounts.user.key(),
            side_base_in,
            amount_in,
            amount_out: q.amount_out,
            fee_paid: q.fee_paid,
            effective_fee_bps: q.effective_fee_bps,
            fee_tier_out_of_band: q.fee_tier == FeeTier::OutOfBand,
            band_lower: band.lower,
            band_upper: band.upper,
            band_exponent: band.exponent,
            band_publish_ts: band.publish_ts,
            band_publish_slot: band.publish_slot,
            claimed_served_bps: band.claimed_served_bps,
            regime_code: band.regime_code,
            ts: now_ts,
        });
        Ok(())
    }

    /// Authority-only pause / unpause toggle.
    pub fn set_paused(ctx: Context<AuthorityOnly>, paused: bool) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        pool.paused = u8::from(paused);
        emit!(PauseToggled {
            pool: pool.key(),
            paused,
            authority: ctx.accounts.authority.key(),
            ts: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    /// Authority-only fee parameter update. Bands of validity match
    /// `initialize_pool`.
    pub fn set_fee_params(
        ctx: Context<AuthorityOnly>,
        fee_bps_in: u16,
        fee_alpha_out_bps: u16,
        fee_w_max_bps: u16,
        max_band_staleness_secs: u32,
    ) -> Result<()> {
        require!(
            fee_bps_in <= 10_000 && fee_w_max_bps <= 10_000,
            BandAmmError::FeeParamOutOfRange
        );
        require!(
            max_band_staleness_secs > 0 && max_band_staleness_secs <= 86_400,
            BandAmmError::StalenessParamOutOfRange
        );

        let pool = &mut ctx.accounts.pool;
        pool.fee_bps_in = fee_bps_in;
        pool.fee_alpha_out_bps = fee_alpha_out_bps;
        pool.fee_w_max_bps = fee_w_max_bps;
        pool.max_band_staleness_secs = max_band_staleness_secs;

        emit!(FeeParamsUpdated {
            pool: pool.key(),
            fee_bps_in,
            fee_alpha_out_bps,
            fee_w_max_bps,
            max_band_staleness_secs,
            authority: ctx.accounts.authority.key(),
            ts: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }
}

// ─────────────────────────────── Instruction params ──────────────────────────

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Debug)]
pub struct InitializePoolParams {
    pub authority: Pubkey,
    /// Optional overrides; `None` falls back to the `state::DEFAULT_*` constants.
    pub fee_bps_in: Option<u16>,
    pub fee_alpha_out_bps: Option<u16>,
    pub fee_w_max_bps: Option<u16>,
    pub max_band_staleness_secs: Option<u32>,
}

// ─────────────────────────────── Account contexts ────────────────────────────

#[derive(Accounts)]
pub struct InitializePool<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,

    pub base_mint: Box<Account<'info, Mint>>,
    pub quote_mint: Box<Account<'info, Mint>>,

    #[account(
        init,
        payer = payer,
        space = 8 + BandAmmPool::INIT_SPACE,
        seeds = [b"band_amm_pool", base_mint.key().as_ref(), quote_mint.key().as_ref()],
        bump,
    )]
    pub pool: Box<Account<'info, BandAmmPool>>,

    #[account(
        init,
        payer = payer,
        seeds = [b"lp_mint", pool.key().as_ref()],
        bump,
        mint::decimals = 6,
        mint::authority = pool,
    )]
    pub lp_mint: Box<Account<'info, Mint>>,

    #[account(
        init,
        payer = payer,
        seeds = [b"vault", pool.key().as_ref(), base_mint.key().as_ref()],
        bump,
        token::mint = base_mint,
        token::authority = pool,
    )]
    pub base_vault: Box<Account<'info, TokenAccount>>,

    #[account(
        init,
        payer = payer,
        seeds = [b"vault", pool.key().as_ref(), quote_mint.key().as_ref()],
        bump,
        token::mint = quote_mint,
        token::authority = pool,
    )]
    pub quote_vault: Box<Account<'info, TokenAccount>>,

    /// CHECK: validated only as the configured `price_update` pubkey at init
    /// time. The AMM decodes its data on each swap via
    /// `soothsayer_consumer::decode_price_update` — full discriminator + version
    /// + invariant checks happen there. No account-deserialize at init avoids
    /// pulling in the oracle program's account types.
    pub price_update: UncheckedAccount<'info>,

    pub system_program: Program<'info, System>,
    pub token_program: Program<'info, Token>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct Deposit<'info> {
    pub user: Signer<'info>,

    #[account(
        mut,
        seeds = [b"band_amm_pool", pool.base_mint.as_ref(), pool.quote_mint.as_ref()],
        bump = pool.pool_bump,
    )]
    pub pool: Box<Account<'info, BandAmmPool>>,

    #[account(mut, address = pool.lp_mint)]
    pub lp_mint: Box<Account<'info, Mint>>,

    #[account(mut, address = pool.base_vault)]
    pub base_vault: Box<Account<'info, TokenAccount>>,

    #[account(mut, address = pool.quote_vault)]
    pub quote_vault: Box<Account<'info, TokenAccount>>,

    #[account(mut, token::mint = pool.base_mint, token::authority = user)]
    pub user_base: Box<Account<'info, TokenAccount>>,

    #[account(mut, token::mint = pool.quote_mint, token::authority = user)]
    pub user_quote: Box<Account<'info, TokenAccount>>,

    #[account(mut, token::mint = pool.lp_mint, token::authority = user)]
    pub user_lp: Box<Account<'info, TokenAccount>>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Withdraw<'info> {
    pub user: Signer<'info>,

    #[account(
        mut,
        seeds = [b"band_amm_pool", pool.base_mint.as_ref(), pool.quote_mint.as_ref()],
        bump = pool.pool_bump,
    )]
    pub pool: Box<Account<'info, BandAmmPool>>,

    #[account(mut, address = pool.lp_mint)]
    pub lp_mint: Box<Account<'info, Mint>>,

    #[account(mut, address = pool.base_vault)]
    pub base_vault: Box<Account<'info, TokenAccount>>,

    #[account(mut, address = pool.quote_vault)]
    pub quote_vault: Box<Account<'info, TokenAccount>>,

    #[account(mut, token::mint = pool.base_mint, token::authority = user)]
    pub user_base: Box<Account<'info, TokenAccount>>,

    #[account(mut, token::mint = pool.quote_mint, token::authority = user)]
    pub user_quote: Box<Account<'info, TokenAccount>>,

    #[account(mut, token::mint = pool.lp_mint, token::authority = user)]
    pub user_lp: Box<Account<'info, TokenAccount>>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct Swap<'info> {
    pub user: Signer<'info>,

    #[account(
        mut,
        seeds = [b"band_amm_pool", pool.base_mint.as_ref(), pool.quote_mint.as_ref()],
        bump = pool.pool_bump,
    )]
    pub pool: Box<Account<'info, BandAmmPool>>,

    #[account(mut, address = pool.base_vault)]
    pub base_vault: Box<Account<'info, TokenAccount>>,

    #[account(mut, address = pool.quote_vault)]
    pub quote_vault: Box<Account<'info, TokenAccount>>,

    #[account(mut, token::mint = pool.base_mint, token::authority = user)]
    pub user_base: Box<Account<'info, TokenAccount>>,

    #[account(mut, token::mint = pool.quote_mint, token::authority = user)]
    pub user_quote: Box<Account<'info, TokenAccount>>,

    /// CHECK: address-locked to `pool.price_update`; data is decoded via
    /// soothsayer-consumer on each swap (Day 2/3).
    #[account(address = pool.price_update @ BandAmmError::WrongPriceUpdate)]
    pub price_update: UncheckedAccount<'info>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct AuthorityOnly<'info> {
    pub authority: Signer<'info>,

    #[account(
        mut,
        seeds = [b"band_amm_pool", pool.base_mint.as_ref(), pool.quote_mint.as_ref()],
        bump = pool.pool_bump,
        has_one = authority @ BandAmmError::Unauthorized,
    )]
    pub pool: Box<Account<'info, BandAmmPool>>,
}

// ──────────────────────────────────── Events ─────────────────────────────────

#[event]
pub struct PoolInitialized {
    pub pool: Pubkey,
    pub base_mint: Pubkey,
    pub quote_mint: Pubkey,
    pub price_update: Pubkey,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct PauseToggled {
    pub pool: Pubkey,
    pub paused: bool,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct FeeParamsUpdated {
    pub pool: Pubkey,
    pub fee_bps_in: u16,
    pub fee_alpha_out_bps: u16,
    pub fee_w_max_bps: u16,
    pub max_band_staleness_secs: u32,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct Deposited {
    pub pool: Pubkey,
    pub user: Pubkey,
    pub base_used: u64,
    pub quote_used: u64,
    pub lp_minted: u64,
    pub ts: i64,
}

#[event]
pub struct Withdrawn {
    pub pool: Pubkey,
    pub user: Pubkey,
    pub lp_burned: u64,
    pub base_out: u64,
    pub quote_out: u64,
    pub ts: i64,
}

/// Swap receipt — the on-chain analogue of Paper 1's calibration receipt,
/// applied to AMM execution. Reconcilable against the on-chain `PriceUpdate`
/// PDA at `band_publish_slot` for the audit-chain test (test plan §5.3).
#[event]
pub struct Swapped {
    pub pool: Pubkey,
    pub user: Pubkey,
    pub side_base_in: bool,
    pub amount_in: u64,
    pub amount_out: u64,
    pub fee_paid: u64,
    pub effective_fee_bps: u32,
    pub fee_tier_out_of_band: bool,
    pub band_lower: i64,
    pub band_upper: i64,
    pub band_exponent: i8,
    pub band_publish_ts: i64,
    pub band_publish_slot: u64,
    pub claimed_served_bps: u16,
    pub regime_code: u8,
    pub ts: i64,
}

// ─────────────────────────────── Error mappers ───────────────────────────────

fn map_lp_err(e: LpMathError) -> Error {
    match e {
        LpMathError::ZeroAmount => error!(BandAmmError::ZeroAmountIn),
        LpMathError::ZeroLpSupplyWithReserves => error!(BandAmmError::InsufficientReserves),
        LpMathError::Overflow => error!(BandAmmError::MathOverflow),
        LpMathError::InsufficientReserves => error!(BandAmmError::InsufficientReserves),
    }
}

fn map_swap_err(e: SwapMathError) -> Error {
    match e {
        SwapMathError::ZeroAmountIn => error!(BandAmmError::ZeroAmountIn),
        SwapMathError::InsufficientReserves => error!(BandAmmError::InsufficientReserves),
        SwapMathError::Overflow => error!(BandAmmError::MathOverflow),
        SwapMathError::InvertedBand => error!(BandAmmError::BandRejected),
        SwapMathError::NegativeBandValue => error!(BandAmmError::BandRejected),
    }
}
