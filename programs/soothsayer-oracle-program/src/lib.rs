//! Soothsayer oracle — on-chain program.
//!
//! Four instructions:
//!
//! - `initialize` — one-time setup: creates `PublisherConfig` + `SignerSet` PDAs
//!   with the provided authority + initial signer.
//! - `publish` — validates signer, rate-limits, writes a `PriceUpdate` PDA per
//!   symbol. Consumers read these PDAs to get the current calibrated band + receipt.
//! - `pause` — authority-only emergency stop.
//! - `rotate_signer_set` — authority-only signer rotation. Phase 1: single signer;
//!   Phase 3: replace with Merkle-root multi-replicator.
//!
//! Every instruction emits structured Anchor events so off-chain indexers can
//! trace publish history without re-reading every account.

use anchor_lang::prelude::*;

pub mod errors;
pub mod state;

use errors::SoothsayerError;
use state::{
    PriceUpdate, PublishPayload, PublisherConfig, SignerSet, PRICE_UPDATE_VERSION,
    PUBLISHER_CONFIG_VERSION, SIGNER_SET_VERSION,
};

// Valid placeholder program ID until deploy tooling rewrites it.
declare_id!("11111111111111111111111111111111");

#[program]
pub mod soothsayer_oracle_program {
    use super::*;

    /// One-time initialization. Creates `PublisherConfig` and `SignerSet` PDAs.
    pub fn initialize(
        ctx: Context<Initialize>,
        authority: Pubkey,
        initial_signer: Pubkey,
        min_publish_interval_secs: u32,
    ) -> Result<()> {
        require!(
            min_publish_interval_secs <= 24 * 3600,
            SoothsayerError::CadenceTooFast
        );

        let config = &mut ctx.accounts.config;
        config.version = PUBLISHER_CONFIG_VERSION;
        config.paused = 0;
        config._pad0 = [0; 6];
        config.min_publish_interval_secs = min_publish_interval_secs;
        config._pad1 = 0;
        config.authority = authority;

        let signer_set = &mut ctx.accounts.signer_set;
        signer_set.version = SIGNER_SET_VERSION;
        signer_set.signer_count = 1;
        signer_set._pad0 = [0; 6];
        signer_set.epoch = 1;
        signer_set.updated_ts = Clock::get()?.unix_timestamp;
        signer_set.root = initial_signer.to_bytes();

        emit!(Initialized {
            authority,
            initial_signer,
            min_publish_interval_secs,
            ts: signer_set.updated_ts,
        });
        Ok(())
    }

    /// Publish a PriceUpdate for a symbol. The PDA is derived from the symbol
    /// bytes; first publish for a symbol creates the account (init_if_needed),
    /// subsequent publishes overwrite in place.
    pub fn publish(ctx: Context<Publish>, payload: PublishPayload) -> Result<()> {
        let config = &ctx.accounts.config;
        require!(config.paused == 0, SoothsayerError::PublishingPaused);

        require!(
            payload.version == PRICE_UPDATE_VERSION,
            SoothsayerError::UnsupportedVersion
        );

        // Phase 1 single-signer: the signer_set.root IS the signer's pubkey.
        // Phase 3 will replace with Merkle-proof verification.
        let signer_set = &ctx.accounts.signer_set;
        let signer_key_bytes = ctx.accounts.signer.key().to_bytes();
        require!(
            signer_set.root == signer_key_bytes,
            SoothsayerError::SignerNotInSet
        );

        // Invariants on the payload.
        require!(
            payload.lower <= payload.point && payload.point <= payload.upper,
            SoothsayerError::BandInvariantViolated
        );
        require!(
            payload.target_coverage_bps <= 10_000
                && payload.claimed_served_bps <= 10_000
                && payload.buffer_applied_bps <= 10_000,
            SoothsayerError::CoverageOutOfRange
        );
        require!(
            (-12..=0).contains(&payload.exponent),
            SoothsayerError::ExponentOutOfRange
        );

        // The symbol field on the payload must match the seed used for the PDA.
        // Anchor has already verified the PDA matches the accounts; we just
        // cross-check the payload symbol matches the account's symbol bytes.
        // For new accounts, this is the first write — we set it from the payload.
        let pu = &mut ctx.accounts.price_update;
        let is_new = pu.version == 0;

        // Cadence check: if not a new account, require enough time has elapsed.
        let now_ts = Clock::get()?.unix_timestamp;
        if !is_new {
            let elapsed = now_ts.saturating_sub(pu.publish_ts);
            require!(
                elapsed >= config.min_publish_interval_secs as i64,
                SoothsayerError::CadenceTooFast
            );
            require!(
                pu.symbol == payload.symbol,
                SoothsayerError::SymbolMismatch
            );
        }

        // Write all PriceUpdate fields from payload + context.
        pu.version = PRICE_UPDATE_VERSION;
        pu.regime_code = payload.regime_code;
        pu.forecaster_code = payload.forecaster_code;
        pu.exponent = payload.exponent;
        pu._pad0 = [0; 4];
        pu.target_coverage_bps = payload.target_coverage_bps;
        pu.claimed_served_bps = payload.claimed_served_bps;
        pu.buffer_applied_bps = payload.buffer_applied_bps;
        pu._pad1 = [0; 2];
        pu.symbol = payload.symbol;
        pu.point = payload.point;
        pu.lower = payload.lower;
        pu.upper = payload.upper;
        pu.fri_close = payload.fri_close;
        pu.fri_ts = payload.fri_ts;
        pu.publish_ts = now_ts;
        pu.publish_slot = Clock::get()?.slot;
        pu.signer = ctx.accounts.signer.key();
        pu.signer_epoch = signer_set.epoch;

        emit!(Published {
            symbol: payload.symbol,
            signer: pu.signer,
            publish_ts: pu.publish_ts,
            publish_slot: pu.publish_slot,
            point: pu.point,
            lower: pu.lower,
            upper: pu.upper,
            target_coverage_bps: pu.target_coverage_bps,
            claimed_served_bps: pu.claimed_served_bps,
            regime_code: pu.regime_code,
            forecaster_code: pu.forecaster_code,
        });
        Ok(())
    }

    /// Authority-only emergency pause / unpause.
    pub fn set_paused(ctx: Context<AuthorityOnly>, paused: bool) -> Result<()> {
        let config = &mut ctx.accounts.config;
        config.paused = if paused { 1 } else { 0 };
        emit!(PauseToggled {
            paused: config.paused == 1,
            authority: ctx.accounts.authority.key(),
            ts: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    /// Authority-only signer rotation. In Phase 1 this replaces the sole
    /// signer. In Phase 3 this will take a Merkle root + list of new members.
    pub fn rotate_signer_set(
        ctx: Context<AuthorityOnlySigners>,
        new_root: [u8; 32],
        new_count: u8,
    ) -> Result<()> {
        let signer_set = &mut ctx.accounts.signer_set;
        signer_set.epoch = signer_set.epoch.saturating_add(1);
        signer_set.root = new_root;
        signer_set.signer_count = new_count;
        signer_set.updated_ts = Clock::get()?.unix_timestamp;
        emit!(SignerSetRotated {
            epoch: signer_set.epoch,
            new_root,
            signer_count: new_count,
            authority: ctx.accounts.authority.key(),
            ts: signer_set.updated_ts,
        });
        Ok(())
    }
}

// ─────────────────────────────── Account constraint contexts ──────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    /// The account paying for initialization. Typically the future authority.
    #[account(mut)]
    pub payer: Signer<'info>,

    #[account(
        init,
        payer = payer,
        space = 8 + PublisherConfig::INIT_SPACE,
        seeds = [b"config"],
        bump,
    )]
    pub config: Account<'info, PublisherConfig>,

    #[account(
        init,
        payer = payer,
        space = 8 + SignerSet::INIT_SPACE,
        seeds = [b"signer_set"],
        bump,
    )]
    pub signer_set: Account<'info, SignerSet>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(payload: PublishPayload)]
pub struct Publish<'info> {
    /// The publisher; must match `signer_set.root` (Phase 1) or satisfy a
    /// Merkle proof (Phase 3). Pays for init_if_needed on first publish per symbol.
    #[account(mut)]
    pub signer: Signer<'info>,

    #[account(seeds = [b"config"], bump)]
    pub config: Account<'info, PublisherConfig>,

    #[account(seeds = [b"signer_set"], bump)]
    pub signer_set: Account<'info, SignerSet>,

    /// Per-symbol PriceUpdate PDA. Created on first publish for that symbol.
    #[account(
        init_if_needed,
        payer = signer,
        space = 8 + PriceUpdate::INIT_SPACE,
        seeds = [b"price", payload.symbol.as_ref()],
        bump,
    )]
    pub price_update: Account<'info, PriceUpdate>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct AuthorityOnly<'info> {
    pub authority: Signer<'info>,

    #[account(
        mut,
        seeds = [b"config"],
        bump,
        has_one = authority @ SoothsayerError::SignerNotInSet,
    )]
    pub config: Account<'info, PublisherConfig>,
}

#[derive(Accounts)]
pub struct AuthorityOnlySigners<'info> {
    pub authority: Signer<'info>,

    #[account(
        seeds = [b"config"],
        bump,
        has_one = authority @ SoothsayerError::SignerNotInSet,
    )]
    pub config: Account<'info, PublisherConfig>,

    #[account(mut, seeds = [b"signer_set"], bump)]
    pub signer_set: Account<'info, SignerSet>,
}

// ─────────────────────────────────────── Events ───────────────────────────────

#[event]
pub struct Initialized {
    pub authority: Pubkey,
    pub initial_signer: Pubkey,
    pub min_publish_interval_secs: u32,
    pub ts: i64,
}

#[event]
pub struct Published {
    pub symbol: [u8; 16],
    pub signer: Pubkey,
    pub publish_ts: i64,
    pub publish_slot: u64,
    pub point: i64,
    pub lower: i64,
    pub upper: i64,
    pub target_coverage_bps: u16,
    pub claimed_served_bps: u16,
    pub regime_code: u8,
    pub forecaster_code: u8,
}

#[event]
pub struct PauseToggled {
    pub paused: bool,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct SignerSetRotated {
    pub epoch: u64,
    pub new_root: [u8; 32],
    pub signer_count: u8,
    pub authority: Pubkey,
    pub ts: i64,
}
