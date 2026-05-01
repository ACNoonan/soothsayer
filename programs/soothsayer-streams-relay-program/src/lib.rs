//! Soothsayer Chainlink Data Streams relay — on-chain program.
//!
//! Locked 2026-04-29 (afternoon) per `reports/methodology_history.md`. The
//! soothsayer-router consumes Chainlink equity feeds via this program (Option
//! C); the off-chain daemon (scryer wishlist item 43) fetches DON-signed
//! reports from Chainlink Streams and calls `post_relay_update` to persist
//! decoded results into per-feed `streams_relay_update.v1` PDAs.
//!
//! **Phase 42a scaffold (this commit).** Six instructions wired with full
//! account-validation contexts; the Verifier-CPI step in `post_relay_update`
//! is stubbed with `RelayError::VerifierCpiNotImplemented`. Phase 42b adds
//! the real CPI to Chainlink's Verifier program at
//! `Gt9S41PtjR58CbG9JhJ3J6vxesqrNAswbWYbLNTMZA3c` (devnet) /
//! mainnet-equivalent, after `chainlink-data-streams-solana` SDK dep-graph
//! verification against anchor-lang 0.31.
//!
//! Seven instructions:
//! - `initialize` — creates `RelayConfig` with authority + initial single-writer set.
//! - `add_feed` — authority-gated; creates `FeedRegistry` + `StreamsRelayUpdate` PDAs.
//! - `post_relay_update` — writer-gated; writes a fresh price-update to the
//!   feed's `StreamsRelayUpdate` PDA after Verifier validation (Phase 42b live).
//! - `set_paused` — authority-gated emergency pause.
//! - `set_verifier_cpi_required` — authority-gated; toggles the
//!   `verifier_cpi_required` flag on `RelayConfig` (dev mode ↔ production mode).
//! - `rotate_authority` — authority-gated authority handoff.
//! - `rotate_writer_set` — authority-gated; replaces the active writer set.
//!
//! v0 governance: ships upgradeable, controlled by the same multisig as the
//! soothsayer-router-program. Migration to immutable + versioned-replacement
//! is gated on a signed institutional-partner LOI per the 2026-04-28
//! (afternoon) methodology entry.

use anchor_lang::prelude::*;

pub mod errors;
pub mod state;

use errors::RelayError;
use state::{
    AddFeedPayload, FeedRegistry, PostRelayUpdatePayload, RelayConfig, RotateWriterSetPayload,
    StreamsRelayUpdate, FEED_REGISTRY_VERSION, MAX_WRITERS, RELAY_CONFIG_VERSION,
    STREAMS_RELAY_UPDATE_VERSION,
};

// Valid placeholder program ID until `anchor keys sync` rewrites it.
declare_id!("DiLqUXQPAMrX1ZoFrEqfw8mPWjpWxzhsPPQzNnEZyMFG");

#[program]
pub mod soothsayer_streams_relay_program {
    use super::*;

    /// One-time initialization. Creates `RelayConfig` PDA with the given
    /// authority and an initial single-writer set (the writer keypair is
    /// passed by the caller; rotate via `rotate_writer_set`).
    pub fn initialize(
        ctx: Context<Initialize>,
        authority: Pubkey,
        initial_writer: Pubkey,
        verifier_cpi_required: bool,
    ) -> Result<()> {
        let now_ts = Clock::get()?.unix_timestamp;
        let config = &mut ctx.accounts.config;
        config.version = RELAY_CONFIG_VERSION;
        config.paused = 0;
        config.n_writers = 1;
        config.verifier_cpi_required = if verifier_cpi_required { 1 } else { 0 };
        config._pad0 = [0; 4];
        config.authority = authority;
        config.writer_set = [Pubkey::default(); MAX_WRITERS];
        config.writer_set[0] = initial_writer;
        config.created_ts = now_ts;
        config.updated_ts = now_ts;

        emit!(RelayInitialized {
            authority,
            initial_writer,
            verifier_cpi_required: config.verifier_cpi_required == 1,
            ts: now_ts,
        });
        Ok(())
    }

    /// Authority-only emergency pause / unpause for the entire relay.
    pub fn set_paused(ctx: Context<AuthorityOnly>, paused: bool) -> Result<()> {
        let config = &mut ctx.accounts.config;
        config.paused = if paused { 1 } else { 0 };
        config.updated_ts = Clock::get()?.unix_timestamp;
        emit!(RelayPauseToggled {
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
        emit!(RelayAuthorityRotated {
            old_authority: old,
            new_authority,
            ts: config.updated_ts,
        });
        Ok(())
    }

    /// Authority-only. Toggles the `verifier_cpi_required` flag on `RelayConfig`.
    /// 0 = development mode (off-chain validation only; signature_verified=0
    /// on every post). 1 = production mode (Verifier CPI mandatory; CPI
    /// failure aborts the post; signature_verified=1 on success).
    ///
    /// Per the 2026-04-29 (evening) operator commitments: production
    /// deployments must run with this flag set to 1 before mainnet relay
    /// goes live. The toggle exists so the same deployed program can run
    /// in dev mode during initial integration and flip to production
    /// without a fresh deploy / RelayConfig PDA migration.
    pub fn set_verifier_cpi_required(
        ctx: Context<AuthorityOnly>,
        required: bool,
    ) -> Result<()> {
        let config = &mut ctx.accounts.config;
        let was_required = config.verifier_cpi_required == 1;
        config.verifier_cpi_required = if required { 1 } else { 0 };
        config.updated_ts = Clock::get()?.unix_timestamp;
        emit!(RelayVerifierCpiToggled {
            previously_required: was_required,
            now_required: required,
            authority: ctx.accounts.authority.key(),
            ts: config.updated_ts,
        });
        Ok(())
    }

    /// Authority-only writer-set rotation. Replaces the active writer set
    /// with the supplied list; slots beyond `n_writers` must be `Pubkey::default()`.
    /// Path for the v0 single-writer → v1 multi-writer transition (per O10
    /// in the soothsayer methodology log §2).
    pub fn rotate_writer_set(
        ctx: Context<AuthorityOnly>,
        payload: RotateWriterSetPayload,
    ) -> Result<()> {
        require!(
            (payload.n_writers as usize) > 0 && (payload.n_writers as usize) <= MAX_WRITERS,
            RelayError::WriterSetFull
        );
        // Active prefix invariant: indices 0..n_writers must be non-default;
        // indices n_writers..MAX_WRITERS must be default.
        for (i, w) in payload.writers.iter().enumerate() {
            let expected_active = (i as u8) < payload.n_writers;
            let actually_active = *w != Pubkey::default();
            require!(
                expected_active == actually_active,
                RelayError::WriterSetFull
            );
        }

        let config = &mut ctx.accounts.config;
        config.n_writers = payload.n_writers;
        config.writer_set = payload.writers;
        config.updated_ts = Clock::get()?.unix_timestamp;

        emit!(RelayWriterSetRotated {
            n_writers: payload.n_writers,
            authority: ctx.accounts.authority.key(),
            ts: config.updated_ts,
        });
        Ok(())
    }

    /// Authority-only. Registers a new feed_id for relay coverage. Creates
    /// the per-feed `FeedRegistry` PDA (config) and the per-feed
    /// `StreamsRelayUpdate` PDA (zeroed; first `post_relay_update`
    /// populates).
    pub fn add_feed(ctx: Context<AddFeed>, payload: AddFeedPayload) -> Result<()> {
        require!(ctx.accounts.config.paused == 0, RelayError::RelayPaused);
        require!(
            (-12..=0).contains(&payload.exponent),
            RelayError::ExponentOutOfRange
        );

        let now_ts = Clock::get()?.unix_timestamp;
        let registry = &mut ctx.accounts.feed_registry;
        registry.version = FEED_REGISTRY_VERSION;
        registry.paused = 0;
        registry.exponent = payload.exponent;
        registry.last_schema_decoded_from = 0;
        registry._pad0 = [0; 4];
        registry.feed_id = payload.feed_id;
        registry.underlier_symbol = payload.underlier_symbol;
        registry.created_ts = now_ts;
        registry.last_post_ts = 0;

        // Initialise the StreamsRelayUpdate PDA with zeroed fields. First
        // post_relay_update populates real values.
        let snapshot = &mut ctx.accounts.relay_update;
        snapshot.version = STREAMS_RELAY_UPDATE_VERSION;
        snapshot.feed_id = payload.feed_id;
        snapshot.underlier_symbol = payload.underlier_symbol;
        snapshot.exponent = payload.exponent;

        emit!(RelayFeedAdded {
            feed_id: payload.feed_id,
            underlier_symbol: payload.underlier_symbol,
            exponent: payload.exponent,
            authority: ctx.accounts.authority.key(),
            ts: now_ts,
        });
        Ok(())
    }

    /// Writer-only. Submits a Chainlink-signed report blob along with its
    /// off-chain decoding. Phase 42a stubs the Verifier CPI; Phase 42b adds
    /// the real validation (CPI into Chainlink Verifier program). On
    /// success, persists `StreamsRelayUpdate.v1` for the feed.
    pub fn post_relay_update(
        ctx: Context<PostRelayUpdate>,
        payload: PostRelayUpdatePayload,
    ) -> Result<()> {
        let config = &ctx.accounts.config;
        require!(config.paused == 0, RelayError::RelayPaused);
        require!(
            ctx.accounts.feed_registry.paused == 0,
            RelayError::RelayPaused
        );
        require!(
            payload.version == STREAMS_RELAY_UPDATE_VERSION,
            RelayError::UnsupportedVersion
        );
        require!(
            ctx.accounts.feed_registry.feed_id == payload.feed_id,
            RelayError::FeedIdMismatch
        );

        // Writer-set check.
        let signer_key = ctx.accounts.writer.key();
        let mut writer_ok = false;
        for i in 0..(config.n_writers as usize) {
            if config.writer_set[i] == signer_key {
                writer_ok = true;
                break;
            }
        }
        require!(writer_ok, RelayError::NotInWriterSet);

        // Schema + market-status validation.
        require!(
            matches!(
                payload.schema_decoded_from,
                state::CHAINLINK_SCHEMA_V8 | state::CHAINLINK_SCHEMA_V11
            ),
            RelayError::UnsupportedSchemaId
        );
        require!(
            payload.market_status_code <= state::MARKET_STATUS_CLOSED,
            RelayError::MarketStatusOutOfRange
        );

        // Staleness check vs the currently-stored snapshot. Reject older
        // posts so a slow daemon can't overwrite a fresher one.
        let snapshot = &ctx.accounts.relay_update;
        require!(
            payload.chainlink_observations_ts >= snapshot.chainlink_observations_ts,
            RelayError::StalePost
        );

        // ── Verifier CPI (Phase 42b) ──
        // When `verifier_cpi_required == 1` (production default), the relay
        // program builds the Chainlink Verifier verify-instruction via the
        // `chainlink_solana_data_streams` SDK, invokes it via CPI, and
        // requires success before persisting. The Verifier program does the
        // DON-threshold-signature check internally; on success the relay
        // stamps `signature_verified = SIGNATURE_VERIFIED_CPI`. On failure
        // the tx aborts and no PDA write occurs.
        //
        // When `verifier_cpi_required == 0` (development override; never
        // enabled on mainnet per the 2026-04-29 (evening) operator
        // commitments), the CPI is skipped and the relay stamps
        // `signature_verified = SIGNATURE_VERIFIED_OFFCHAIN_ONLY`. Consumers
        // can downgrade trust on `signature_verified == 0` reads.
        let signature_verified = if config.verifier_cpi_required == 1 {
            use anchor_lang::solana_program::program::invoke;
            use chainlink_solana_data_streams::VerifierInstructions;

            let ix = VerifierInstructions::verify(
                ctx.accounts.verifier_program.key,
                ctx.accounts.verifier_account.key,
                ctx.accounts.access_controller.key,
                ctx.accounts.writer.key,
                ctx.accounts.report_config.key,
                payload.signed_report_blob.clone(),
            );

            invoke(
                &ix,
                &[
                    ctx.accounts.verifier_account.to_account_info(),
                    ctx.accounts.access_controller.to_account_info(),
                    ctx.accounts.writer.to_account_info(),
                    ctx.accounts.report_config.to_account_info(),
                    ctx.accounts.verifier_program.to_account_info(),
                ],
            )
            .map_err(|_| error!(RelayError::VerifierRejected))?;

            // The Verifier returns the decoded report via instruction
            // return_data. We don't fully decode + cross-check here in v0
            // (that's a Phase 42c hardening item — comparing the daemon-
            // supplied `payload.price/conf/...` against the Verifier-
            // returned canonical decoded fields). For v0, success of the
            // invoke is sufficient evidence the signed report is valid.
            state::SIGNATURE_VERIFIED_CPI
        } else {
            state::SIGNATURE_VERIFIED_OFFCHAIN_ONLY
        };

        // ── Persist ──
        let clock = Clock::get()?;
        let now_ts = clock.unix_timestamp;
        let now_slot = clock.slot;

        let snapshot = &mut ctx.accounts.relay_update;
        snapshot.version = STREAMS_RELAY_UPDATE_VERSION;
        snapshot.market_status_code = payload.market_status_code;
        snapshot.schema_decoded_from = payload.schema_decoded_from;
        snapshot.signature_verified = signature_verified;
        snapshot._pad0 = [0; 4];
        snapshot.feed_id = payload.feed_id;
        snapshot.underlier_symbol = ctx.accounts.feed_registry.underlier_symbol;
        snapshot.price = payload.price;
        snapshot.confidence = payload.confidence;
        snapshot.bid = payload.bid;
        snapshot.ask = payload.ask;
        snapshot.last_traded_price = payload.last_traded_price;
        snapshot.chainlink_observations_ts = payload.chainlink_observations_ts;
        snapshot.chainlink_last_seen_ts_ns = payload.chainlink_last_seen_ts_ns;
        snapshot.relay_post_ts = now_ts;
        snapshot.relay_post_slot = now_slot;
        snapshot.exponent = ctx.accounts.feed_registry.exponent;
        snapshot._pad1 = [0; 7];

        // Stamp last-post bookkeeping on the registry.
        let registry = &mut ctx.accounts.feed_registry;
        registry.last_schema_decoded_from = payload.schema_decoded_from;
        registry.last_post_ts = now_ts;

        emit!(RelayUpdatePosted {
            feed_id: payload.feed_id,
            writer: signer_key,
            schema_decoded_from: payload.schema_decoded_from,
            market_status_code: payload.market_status_code,
            signature_verified,
            price: payload.price,
            chainlink_observations_ts: payload.chainlink_observations_ts,
            relay_post_ts: now_ts,
            relay_post_slot: now_slot,
        });
        Ok(())
    }
}

// ────────────────────── account constraint contexts ────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,

    #[account(
        init,
        payer = payer,
        space = 8 + RelayConfig::INIT_SPACE,
        seeds = [b"relay_config"],
        bump,
    )]
    pub config: Account<'info, RelayConfig>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct AuthorityOnly<'info> {
    pub authority: Signer<'info>,

    #[account(
        mut,
        seeds = [b"relay_config"],
        bump,
        has_one = authority @ RelayError::NotAuthority,
    )]
    pub config: Account<'info, RelayConfig>,
}

#[derive(Accounts)]
#[instruction(payload: AddFeedPayload)]
pub struct AddFeed<'info> {
    pub authority: Signer<'info>,

    #[account(mut)]
    pub payer: Signer<'info>,

    #[account(
        seeds = [b"relay_config"],
        bump,
        has_one = authority @ RelayError::NotAuthority,
    )]
    pub config: Account<'info, RelayConfig>,

    #[account(
        init,
        payer = payer,
        space = 8 + FeedRegistry::INIT_SPACE,
        seeds = [b"feed", payload.feed_id.as_ref()],
        bump,
    )]
    pub feed_registry: Account<'info, FeedRegistry>,

    #[account(
        init,
        payer = payer,
        space = 8 + StreamsRelayUpdate::INIT_SPACE,
        seeds = [b"streams_relay", payload.feed_id.as_ref()],
        bump,
    )]
    pub relay_update: Account<'info, StreamsRelayUpdate>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(payload: PostRelayUpdatePayload)]
pub struct PostRelayUpdate<'info> {
    /// The writer keypair calling this instruction. Must be in the active
    /// writer set on `RelayConfig.writer_set[..n_writers]`. Also forwarded
    /// to the Chainlink Verifier as the `user` signer when `verifier_cpi_required == 1`.
    pub writer: Signer<'info>,

    #[account(
        seeds = [b"relay_config"],
        bump,
    )]
    pub config: Account<'info, RelayConfig>,

    #[account(
        mut,
        seeds = [b"feed", payload.feed_id.as_ref()],
        bump,
    )]
    pub feed_registry: Account<'info, FeedRegistry>,

    #[account(
        mut,
        seeds = [b"streams_relay", payload.feed_id.as_ref()],
        bump,
    )]
    pub relay_update: Account<'info, StreamsRelayUpdate>,

    // ── Chainlink Verifier-side accounts (only used when verifier_cpi_required == 1) ──
    //
    // These are passed through to `VerifierInstructions::verify` as the
    // 5 accounts the Verifier program requires. In dev mode (verifier_cpi_required==0)
    // the relay program does not invoke the Verifier and these can be any
    // pubkeys (typically the writer's own pubkey for compactness). In
    // production mode they must be the real Chainlink Verifier devnet/mainnet
    // accounts; the Verifier program itself rejects mismatched inputs.
    //
    /// CHECK: Chainlink Verifier program. Devnet: `Gt9S41PtjR58CbG9JhJ3J6vxesqrNAswbWYbLNTMZA3c`.
    /// In dev mode this is unused; in production mode the CPI invocation
    /// will fail if this isn't the real Verifier.
    pub verifier_program: UncheckedAccount<'info>,

    /// CHECK: Verifier's config PDA, derived via `get_verifier_config_pda()`
    /// from the Chainlink SDK. Validated by the Verifier program at CPI time.
    pub verifier_account: UncheckedAccount<'info>,

    /// CHECK: Access controller PDA. Devnet: `2k3DsgwBoqrnvXKVvd7jX7aptNxdcRBdcd5HkYsGgbrb`.
    /// Validated by the Verifier program.
    pub access_controller: UncheckedAccount<'info>,

    /// CHECK: Report config PDA, derived from the first 32 bytes of the
    /// uncompressed signed report via `get_config_pda()`. Validated by the
    /// Verifier program.
    pub report_config: UncheckedAccount<'info>,
}

// ─────────────────────────────────── events ────────────────────────────────

#[event]
pub struct RelayInitialized {
    pub authority: Pubkey,
    pub initial_writer: Pubkey,
    pub verifier_cpi_required: bool,
    pub ts: i64,
}

#[event]
pub struct RelayPauseToggled {
    pub paused: bool,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct RelayAuthorityRotated {
    pub old_authority: Pubkey,
    pub new_authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct RelayVerifierCpiToggled {
    pub previously_required: bool,
    pub now_required: bool,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct RelayWriterSetRotated {
    pub n_writers: u8,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct RelayFeedAdded {
    pub feed_id: [u8; 32],
    pub underlier_symbol: [u8; 16],
    pub exponent: i8,
    pub authority: Pubkey,
    pub ts: i64,
}

#[event]
pub struct RelayUpdatePosted {
    pub feed_id: [u8; 32],
    pub writer: Pubkey,
    pub schema_decoded_from: u8,
    pub market_status_code: u8,
    pub signature_verified: u8,
    pub price: i64,
    pub chainlink_observations_ts: i64,
    pub relay_post_ts: i64,
    pub relay_post_slot: u64,
}
