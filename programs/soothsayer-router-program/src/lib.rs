//! Soothsayer unified-feed router — on-chain program.
//!
//! Regime-routes between an open-hours multi-upstream aggregator and the
//! closed-hours soothsayer band primitive. Locked 2026-04-28 (afternoon)
//! per `reports/methodology_history.md`.
//!
//! Phase 1 build status: structural shell + filter primitives + regime gate
//! shipped. Pyth and Switchboard On-Demand decoders are real and tested.
//! Chainlink consumption is via the soothsayer-controlled streams-relay
//! program (Option C, locked 2026-04-29 (afternoon)) — relay program +
//! daemon are separate work tracked in scryer wishlist items 42 + 43; the
//! `read_chainlink_streams_relay` decoder stub errors `UpstreamDecoderNotImplemented`
//! until the relay PDA shape is live. RedStone is stubbed pending a Solana
//! PDA layout. Mango v4 was reclassified methodology-only per the
//! 2026-04-29 (morning) entry.
//!
//! Six instructions:
//! - `initialize` — one-time setup; creates `RouterConfig`.
//! - `add_asset` — authority-gated; creates `AssetConfig` + `UnifiedFeedSnapshot` PDAs.
//! - `update_asset_config` — authority-gated; updates filter params + upstream list.
//! - `refresh_feed` — anyone-pays; reads upstreams, applies filters, writes snapshot.
//! - `set_paused` — authority-gated emergency pause.
//! - `rotate_authority` — authority-gated authority handoff.
//!
//! v0 governance: ships upgradeable, controlled by a 2-of-3 multisig held off-chain
//! (the program enforces single-authority signing; the multisig is the authority pubkey).
//! Migration to immutable + versioned-replacement is gated on a signed institutional-
//! partner LOI per the 2026-04-28 (afternoon) methodology entry.

use anchor_lang::prelude::*;

pub mod chainlink_v11;
pub mod errors;
pub mod filters;
pub mod regime;
pub mod soothsayer_band;
pub mod state;
pub mod upstreams;

use errors::RouterError;
use state::{
    AssetConfig, AssetConfigPayload, RouterConfig, UnifiedFeedSnapshot, UpstreamReadSlot,
    UpstreamSlot, ASSET_CONFIG_VERSION, MAX_UPSTREAMS, ROUTER_CONFIG_VERSION,
    UNIFIED_FEED_SNAPSHOT_VERSION,
};

/// Default fixed-point exponent for snapshot prices. Matches the soothsayer
/// oracle program's convention: real_price = stored_value × 10^-8. Future
/// per-asset exponent overrides are tracked via methodology entry.
const DEFAULT_SNAPSHOT_EXPONENT: i8 = -8;

// Valid placeholder program ID until deploy tooling rewrites it.
declare_id!("AZE8HixpkLpqmuuZbCku5NbjWqoQLWhPRTHp8aMY9xNU");

#[program]
pub mod soothsayer_router_program {
    use super::*;

    /// One-time initialization. Creates `RouterConfig` PDA.
    pub fn initialize(ctx: Context<Initialize>, authority: Pubkey) -> Result<()> {
        let now_ts = Clock::get()?.unix_timestamp;
        let config = &mut ctx.accounts.config;
        config.version = ROUTER_CONFIG_VERSION;
        config.paused = 0;
        config._pad0 = [0; 6];
        config.authority = authority;
        config.created_ts = now_ts;
        config.updated_ts = now_ts;

        emit!(RouterInitialized {
            authority,
            ts: now_ts,
        });
        Ok(())
    }

    /// Authority-only emergency pause / unpause for the entire router.
    pub fn set_paused(ctx: Context<AuthorityOnly>, paused: bool) -> Result<()> {
        let config = &mut ctx.accounts.config;
        config.paused = if paused { 1 } else { 0 };
        config.updated_ts = Clock::get()?.unix_timestamp;
        emit!(RouterPauseToggled {
            paused: config.paused == 1,
            authority: ctx.accounts.authority.key(),
            ts: config.updated_ts,
        });
        Ok(())
    }

    /// Authority-only authority rotation. v0: simple swap. Eventually replaced
    /// by a partner-witnessed change-process per the 2026-04-28 (afternoon)
    /// methodology entry.
    pub fn rotate_authority(
        ctx: Context<AuthorityOnly>,
        new_authority: Pubkey,
    ) -> Result<()> {
        let config = &mut ctx.accounts.config;
        let old = config.authority;
        config.authority = new_authority;
        config.updated_ts = Clock::get()?.unix_timestamp;
        emit!(AuthorityRotated {
            old_authority: old,
            new_authority,
            ts: config.updated_ts,
        });
        Ok(())
    }

    /// Authority-gated. Creates `AssetConfig` + `UnifiedFeedSnapshot` PDAs
    /// for an asset.
    pub fn add_asset(ctx: Context<AddAsset>, payload: AssetConfigPayload) -> Result<()> {
        require!(ctx.accounts.config.paused == 0, RouterError::RouterPaused);
        require!(
            payload.version == ASSET_CONFIG_VERSION,
            RouterError::UnsupportedVersion
        );
        validate_asset_config_payload(&payload)?;

        let now_ts = Clock::get()?.unix_timestamp;
        let asset_config = &mut ctx.accounts.asset_config;
        asset_config.version = ASSET_CONFIG_VERSION;
        asset_config.paused = payload.paused;
        asset_config.n_upstreams = payload.n_upstreams;
        asset_config.min_quorum = payload.min_quorum;
        asset_config._pad0 = [0; 4];
        asset_config.asset_id = payload.asset_id;
        asset_config.max_staleness_secs = payload.max_staleness_secs;
        asset_config.max_confidence_bps = payload.max_confidence_bps;
        asset_config.max_deviation_bps = payload.max_deviation_bps;
        asset_config.market_status_source = payload.market_status_source;
        asset_config.soothsayer_band_pda = payload.soothsayer_band_pda;
        asset_config.upstreams = payload.upstreams;
        asset_config.created_ts = now_ts;
        asset_config.updated_ts = now_ts;

        // Initialize the snapshot PDA with zeroed fields. First refresh_feed
        // populates real values.
        let snapshot = &mut ctx.accounts.snapshot;
        snapshot.version = UNIFIED_FEED_SNAPSHOT_VERSION;
        snapshot.asset_id = payload.asset_id;

        emit!(AssetAdded {
            asset_id: payload.asset_id,
            n_upstreams: payload.n_upstreams,
            min_quorum: payload.min_quorum,
            authority: ctx.accounts.authority.key(),
            ts: now_ts,
        });
        Ok(())
    }

    /// Authority-gated. Replaces the AssetConfig in place with the provided
    /// payload. Every parameter change is recorded as a methodology-log
    /// entry off-chain per the 2026-04-28 (afternoon) governance commitment.
    pub fn update_asset_config(
        ctx: Context<UpdateAssetConfig>,
        payload: AssetConfigPayload,
    ) -> Result<()> {
        require!(ctx.accounts.config.paused == 0, RouterError::RouterPaused);
        require!(
            payload.version == ASSET_CONFIG_VERSION,
            RouterError::UnsupportedVersion
        );
        validate_asset_config_payload(&payload)?;

        let asset_config = &mut ctx.accounts.asset_config;
        require!(
            asset_config.asset_id == payload.asset_id,
            RouterError::AssetIdMismatch
        );

        asset_config.paused = payload.paused;
        asset_config.n_upstreams = payload.n_upstreams;
        asset_config.min_quorum = payload.min_quorum;
        asset_config.max_staleness_secs = payload.max_staleness_secs;
        asset_config.max_confidence_bps = payload.max_confidence_bps;
        asset_config.max_deviation_bps = payload.max_deviation_bps;
        asset_config.market_status_source = payload.market_status_source;
        asset_config.soothsayer_band_pda = payload.soothsayer_band_pda;
        asset_config.upstreams = payload.upstreams;
        asset_config.updated_ts = Clock::get()?.unix_timestamp;

        emit!(AssetConfigUpdated {
            asset_id: payload.asset_id,
            n_upstreams: payload.n_upstreams,
            min_quorum: payload.min_quorum,
            max_staleness_secs: payload.max_staleness_secs,
            max_confidence_bps: payload.max_confidence_bps,
            max_deviation_bps: payload.max_deviation_bps,
            authority: ctx.accounts.authority.key(),
            ts: asset_config.updated_ts,
        });
        Ok(())
    }

    /// Anyone-pays. Reads upstreams, applies filters, writes the snapshot.
    ///
    /// **End-to-end for Chainlink-only assets** (this commit). For assets
    /// configured with Pyth / Switchboard / RedStone / Mango v4 upstreams,
    /// the corresponding decoders return
    /// [`RouterError::UpstreamDecoderNotImplemented`] until follow-up step 2b
    /// commits add the SDK dependencies and decoders. Closed-regime + halted
    /// reads work end-to-end via the soothsayer-band PDA path.
    pub fn refresh_feed(ctx: Context<RefreshFeed>) -> Result<()> {
        require!(ctx.accounts.config.paused == 0, RouterError::RouterPaused);
        require!(
            ctx.accounts.asset_config.paused == 0,
            RouterError::AssetPaused
        );

        let clock = Clock::get()?;
        let now_ts = clock.unix_timestamp;
        let now_slot = clock.slot;

        // Step 1 — regime detection.
        require!(
            ctx.accounts.market_status_source.key()
                == ctx.accounts.asset_config.market_status_source,
            RouterError::AssetIdMismatch
        );
        let oracle_signal = {
            let data = ctx.accounts.market_status_source.try_borrow_data()?;
            regime::parse_chainlink_streams_relay_market_status(&data)
        };
        let calendar_signal = regime::nyse_calendar_signal(now_ts);
        let decision = regime::RegimeDecision::from_signals(oracle_signal, calendar_signal);

        // Step 2 — gather upstream reads (open regime only).
        let snapshot_exponent = DEFAULT_SNAPSHOT_EXPONENT;
        let asset_config = ctx.accounts.asset_config.clone();
        let n_upstreams = asset_config.n_upstreams as usize;

        let mut filtered: [filters::FilteredUpstream; MAX_UPSTREAMS] =
            [PLACEHOLDER_FILTERED; MAX_UPSTREAMS];
        if matches!(decision, regime::RegimeDecision::Open) {
            require!(
                ctx.remaining_accounts.len() >= n_upstreams,
                RouterError::TooManyUpstreams
            );
            for i in 0..n_upstreams {
                let slot = &asset_config.upstreams[i];
                require!(slot.active == 1, RouterError::TooManyUpstreams);
                let acct = &ctx.remaining_accounts[i];
                require!(*acct.key == slot.pda, RouterError::AssetIdMismatch);
                let raw = {
                    let data = acct.try_borrow_data()?;
                    upstreams::read_upstream(slot.kind, *acct.key, &data, snapshot_exponent)?
                };
                filtered[i] = filters::FilteredUpstream::new(raw);
            }
        }

        // Step 3 — apply filters (open) or load band (closed/halted), then
        // populate the snapshot.
        let snapshot = &mut ctx.accounts.snapshot;
        snapshot.version = UNIFIED_FEED_SNAPSHOT_VERSION;
        snapshot.asset_id = asset_config.asset_id;
        snapshot.regime_code = decision.code();
        snapshot.exponent = snapshot_exponent;
        snapshot.publish_ts = now_ts;
        snapshot.publish_slot = now_slot;
        // Default-zero everything; per-regime population follows.
        zero_open_regime_fields(snapshot);
        zero_closed_regime_fields(snapshot);

        match decision {
            regime::RegimeDecision::Open => {
                populate_open_regime(snapshot, &asset_config, &mut filtered, n_upstreams, now_ts);
            }
            regime::RegimeDecision::Closed | regime::RegimeDecision::Halted => {
                populate_closed_or_halted_regime(
                    snapshot,
                    &asset_config,
                    &ctx.accounts.soothsayer_band,
                )?;
            }
            regime::RegimeDecision::Unknown => {
                snapshot.quality_flag_code = state::QUALITY_REGIME_AMBIGUOUS;
            }
        }

        emit!(FeedRefreshed {
            asset_id: snapshot.asset_id,
            regime_code: snapshot.regime_code,
            quality_flag_code: snapshot.quality_flag_code,
            quorum_size: snapshot.quorum_size,
            quorum_required: snapshot.quorum_required,
            point: snapshot.point,
            lower: snapshot.lower,
            upper: snapshot.upper,
            publish_ts: snapshot.publish_ts,
            publish_slot: snapshot.publish_slot,
        });
        Ok(())
    }
}

// ──────────────────────── refresh_feed helpers ─────────────────────────────

const PLACEHOLDER_FILTERED: filters::FilteredUpstream = filters::FilteredUpstream {
    read: filters::RawUpstreamRead {
        kind: 0,
        pda: [0; 32],
        raw_price: 0,
        raw_confidence: None,
        last_update_slot: 0,
        last_update_unix_ts: 0,
        exponent: 0,
    },
    included: false,
    exclusion_reason_code: state::EXCLUSION_NONE,
    deviation_bps_from_median: 0,
};

fn populate_open_regime(
    snapshot: &mut UnifiedFeedSnapshot,
    asset_config: &AssetConfig,
    filtered: &mut [filters::FilteredUpstream; MAX_UPSTREAMS],
    n_upstreams: usize,
    now_ts: i64,
) {
    snapshot.aggregate_method_code = state::AGGREGATE_ROBUST_MEDIAN_V1;
    snapshot.quorum_required = asset_config.min_quorum;

    let working = &mut filtered[..n_upstreams];
    filters::apply_staleness_filter(working, now_ts, asset_config.max_staleness_secs);
    filters::apply_confidence_filter(working, asset_config.max_confidence_bps);
    let median = filters::apply_deviation_guard(working, asset_config.max_deviation_bps);

    let quorum_size = working.iter().filter(|f| f.included).count() as u8;
    snapshot.quorum_size = quorum_size;

    snapshot.quality_flag_code = if quorum_size == 0 {
        state::QUALITY_ALL_STALE
    } else if quorum_size < asset_config.min_quorum {
        state::QUALITY_LOW_QUORUM
    } else {
        state::QUALITY_OK
    };

    if let Some(med) = median {
        snapshot.point = med;
        let (low, high) = layer0_band_edges(working, med);
        snapshot.lower = low;
        snapshot.upper = high;
    } else {
        snapshot.point = 0;
        snapshot.lower = 0;
        snapshot.upper = 0;
    }

    // Populate the upstream_reads array with the post-filter contribution log.
    snapshot.n_upstream_reads = n_upstreams as u8;
    for (i, f) in working.iter().enumerate() {
        snapshot.upstream_reads[i] = UpstreamReadSlot {
            kind: f.read.kind,
            included: u8::from(f.included),
            exclusion_reason_code: f.exclusion_reason_code,
            _pad0: [0; 5],
            pda: Pubkey::new_from_array(f.read.pda),
            raw_price: f.read.raw_price,
            raw_confidence: f.read.raw_confidence.unwrap_or(i64::MIN),
            last_update_slot: f.read.last_update_slot,
            deviation_bps_from_median: f.deviation_bps_from_median,
            _pad1: [0; 4],
        };
    }
    for i in n_upstreams..MAX_UPSTREAMS {
        snapshot.upstream_reads[i] = UpstreamReadSlot::default();
    }
}

/// Layer 0 v0: dispersion-based band — `[min, max]` of included upstream reads.
/// Layer 1 (future) replaces with a calibration-weighted band.
fn layer0_band_edges(reads: &[filters::FilteredUpstream], median: i64) -> (i64, i64) {
    let mut min = i64::MAX;
    let mut max = i64::MIN;
    let mut any = false;
    for r in reads {
        if !r.included {
            continue;
        }
        any = true;
        if r.read.raw_price < min {
            min = r.read.raw_price;
        }
        if r.read.raw_price > max {
            max = r.read.raw_price;
        }
    }
    if !any {
        (median, median)
    } else {
        (min, max)
    }
}

fn populate_closed_or_halted_regime(
    snapshot: &mut UnifiedFeedSnapshot,
    asset_config: &AssetConfig,
    soothsayer_band_account: &UncheckedAccount,
) -> Result<()> {
    require!(
        soothsayer_band_account.key() == asset_config.soothsayer_band_pda,
        RouterError::SoothsayerBandUnavailable
    );

    let data = soothsayer_band_account.try_borrow_data()?;
    if data.len() < soothsayer_band::DISCRIMINATOR_LEN {
        snapshot.quality_flag_code = state::QUALITY_SOOTHSAYER_BAND_UNAVAILABLE;
        return Ok(());
    }
    let layout = match soothsayer_band::deserialize_price_update(
        &data[soothsayer_band::DISCRIMINATOR_LEN..],
    ) {
        Ok(l) => l,
        Err(_) => {
            snapshot.quality_flag_code = state::QUALITY_SOOTHSAYER_BAND_UNAVAILABLE;
            return Ok(());
        }
    };
    drop(data);

    snapshot.exponent = layout.exponent;
    snapshot.point = layout.point;
    snapshot.lower = layout.lower;
    snapshot.upper = layout.upper;
    snapshot.target_coverage_bps = layout.target_coverage_bps;
    snapshot.claimed_served_bps = layout.claimed_served_bps;
    snapshot.buffer_applied_bps = layout.buffer_applied_bps;
    snapshot.forecaster_code = layout.forecaster_code;
    snapshot.closed_market_regime_code = layout.regime_code;
    snapshot.quality_flag_code = state::QUALITY_OK;
    Ok(())
}

fn zero_open_regime_fields(snapshot: &mut UnifiedFeedSnapshot) {
    snapshot.aggregate_method_code = 0;
    snapshot.quorum_size = 0;
    snapshot.quorum_required = 0;
    snapshot.n_upstream_reads = 0;
    for i in 0..MAX_UPSTREAMS {
        snapshot.upstream_reads[i] = UpstreamReadSlot::default();
    }
}

fn zero_closed_regime_fields(snapshot: &mut UnifiedFeedSnapshot) {
    snapshot.forecaster_code = 0;
    snapshot.closed_market_regime_code = 0;
    snapshot.target_coverage_bps = 0;
    snapshot.claimed_served_bps = 0;
    snapshot.buffer_applied_bps = 0;
}

// ─────────────────────────────── helpers ────────────────────────────────────

fn validate_asset_config_payload(payload: &AssetConfigPayload) -> Result<()> {
    require!(
        (payload.n_upstreams as usize) <= MAX_UPSTREAMS,
        RouterError::TooManyUpstreams
    );
    require!(
        payload.min_quorum <= payload.n_upstreams,
        RouterError::QuorumExceedsUpstreamCount
    );
    require!(
        payload.max_confidence_bps <= 10_000,
        RouterError::FilterParameterOutOfRange
    );
    require!(
        payload.max_deviation_bps <= 10_000,
        RouterError::FilterParameterOutOfRange
    );
    // Active-slot prefix invariant: indices 0..n_upstreams must all be active;
    // indices n_upstreams..MAX_UPSTREAMS must all be inactive.
    for (i, slot) in payload.upstreams.iter().enumerate() {
        let expected_active = (i as u8) < payload.n_upstreams;
        let actually_active = slot.active == 1;
        require!(
            expected_active == actually_active,
            RouterError::TooManyUpstreams
        );
        if actually_active {
            // Code 4 (`UPSTREAM_MANGO_V4_POST_GUARD`) is reserved per the
            // 2026-04-29 entry; AssetConfig cannot wire it.
            require!(
                matches!(
                    slot.kind,
                    state::UPSTREAM_PYTH_AGGREGATE
                        | state::UPSTREAM_CHAINLINK_STREAMS_RELAY
                        | state::UPSTREAM_SWITCHBOARD_ONDEMAND
                        | state::UPSTREAM_REDSTONE_LIVE
                ),
                RouterError::UnsupportedUpstreamKind
            );
        }
    }
    Ok(())
}

// ────────────────────── account constraint contexts ────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,

    #[account(
        init,
        payer = payer,
        space = 8 + RouterConfig::INIT_SPACE,
        seeds = [b"router_config"],
        bump,
    )]
    pub config: Account<'info, RouterConfig>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct AuthorityOnly<'info> {
    pub authority: Signer<'info>,

    #[account(
        mut,
        seeds = [b"router_config"],
        bump,
        has_one = authority @ RouterError::NotAuthority,
    )]
    pub config: Account<'info, RouterConfig>,
}

#[derive(Accounts)]
#[instruction(payload: AssetConfigPayload)]
pub struct AddAsset<'info> {
    pub authority: Signer<'info>,

    #[account(mut)]
    pub payer: Signer<'info>,

    #[account(
        seeds = [b"router_config"],
        bump,
        has_one = authority @ RouterError::NotAuthority,
    )]
    pub config: Account<'info, RouterConfig>,

    #[account(
        init,
        payer = payer,
        space = 8 + AssetConfig::INIT_SPACE,
        seeds = [b"asset", payload.asset_id.as_ref()],
        bump,
    )]
    pub asset_config: Account<'info, AssetConfig>,

    #[account(
        init,
        payer = payer,
        space = 8 + UnifiedFeedSnapshot::INIT_SPACE,
        seeds = [b"snapshot", payload.asset_id.as_ref()],
        bump,
    )]
    pub snapshot: Account<'info, UnifiedFeedSnapshot>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(payload: AssetConfigPayload)]
pub struct UpdateAssetConfig<'info> {
    pub authority: Signer<'info>,

    #[account(
        seeds = [b"router_config"],
        bump,
        has_one = authority @ RouterError::NotAuthority,
    )]
    pub config: Account<'info, RouterConfig>,

    #[account(
        mut,
        seeds = [b"asset", payload.asset_id.as_ref()],
        bump,
    )]
    pub asset_config: Account<'info, AssetConfig>,
}

/// Account context for `refresh_feed`. The full per-upstream account list is
/// passed via `remaining_accounts` so the same instruction shape works whether
/// an asset has 4 or 5 upstreams configured. Step 2b parses + validates them
/// against `asset_config.upstreams`.
#[derive(Accounts)]
pub struct RefreshFeed<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,

    #[account(
        seeds = [b"router_config"],
        bump,
    )]
    pub config: Account<'info, RouterConfig>,

    pub asset_config: Account<'info, AssetConfig>,

    #[account(
        mut,
        seeds = [b"snapshot", asset_config.asset_id.as_ref()],
        bump,
    )]
    pub snapshot: Account<'info, UnifiedFeedSnapshot>,

    /// CHECK: the soothsayer band PDA referenced by `asset_config.soothsayer_band_pda`.
    /// Validated in step 2b against the AssetConfig field; loaded only for closed-regime.
    pub soothsayer_band: UncheckedAccount<'info>,

    /// CHECK: the market-status source PDA (Chainlink v11 report PDA for equities).
    /// Validated in step 2b against `asset_config.market_status_source`.
    pub market_status_source: UncheckedAccount<'info>,
    // Per-upstream accounts arrive in `ctx.remaining_accounts` in the same
    // order as `asset_config.upstreams` (active slots first). Step 2b validates
    // count + PDA equality.
}

// ─────────────────────────────────── events ────────────────────────────────

#[event]
pub struct RouterInitialized {
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct RouterPauseToggled {
    pub paused: bool,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct AuthorityRotated {
    pub old_authority: Pubkey,
    pub new_authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct AssetAdded {
    pub asset_id: [u8; 16],
    pub n_upstreams: u8,
    pub min_quorum: u8,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct AssetConfigUpdated {
    pub asset_id: [u8; 16],
    pub n_upstreams: u8,
    pub min_quorum: u8,
    pub max_staleness_secs: u32,
    pub max_confidence_bps: u16,
    pub max_deviation_bps: u16,
    pub authority: Pubkey,
    pub ts: i64,
}

/// Emitted on every successful `refresh_feed`. Off-chain indexers join this
/// with the snapshot PDA's slot to reconstruct the receipt history without
/// re-reading every snapshot account.
#[event]
pub struct FeedRefreshed {
    pub asset_id: [u8; 16],
    pub regime_code: u8,
    pub quality_flag_code: u8,
    pub quorum_size: u8,
    pub quorum_required: u8,
    pub point: i64,
    pub lower: i64,
    pub upper: i64,
    pub publish_ts: i64,
    pub publish_slot: u64,
}

// Suppress unused-import warnings on the helper modules until step 2b wires them.
#[allow(dead_code)]
fn _scaffold_keepalive(slot: UpstreamSlot, _read: UpstreamReadSlot) {
    let _ = slot;
}
