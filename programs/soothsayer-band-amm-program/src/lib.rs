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
use anchor_spl::token::{Mint, Token, TokenAccount};

pub mod errors;
pub mod state;
pub mod swap_math;

use errors::BandAmmError;
use state::{
    BandAmmPool, BAND_AMM_POOL_VERSION, DEFAULT_FEE_ALPHA_OUT_BPS, DEFAULT_FEE_BPS_IN,
    DEFAULT_FEE_W_MAX_BPS, DEFAULT_MAX_BAND_STALENESS_SECS,
};

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
        pool._pad0 = [0; 2];

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

    /// Deposit liquidity. Day 1 stub — Day 2 wires SPL transfers + LP mint.
    pub fn deposit(
        _ctx: Context<Deposit>,
        _amount_base: u64,
        _amount_quote: u64,
        _min_lp_out: u64,
    ) -> Result<()> {
        // Day-2 implementation; placeholder so the IDL emits the IX shape.
        Ok(())
    }

    /// Withdraw liquidity. Day 1 stub — Day 2 wires LP burn + SPL transfers.
    pub fn withdraw(
        _ctx: Context<Withdraw>,
        _lp_amount: u64,
        _min_base_out: u64,
        _min_quote_out: u64,
    ) -> Result<()> {
        // Day-2 implementation; placeholder so the IDL emits the IX shape.
        Ok(())
    }

    /// Swap. Day 1 stub — Day 2 wires the in/out fee branch + SPL transfers,
    /// Day 3 wires receipt event + staleness guard.
    pub fn swap(
        _ctx: Context<Swap>,
        _amount_in: u64,
        _min_amount_out: u64,
        _side_base_in: bool,
    ) -> Result<()> {
        // Day-2 implementation; placeholder so the IDL emits the IX shape.
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
