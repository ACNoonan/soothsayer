//! Mock Chainlink Verifier program — devnet-only test fixture.
//!
//! Mimics the public `verify` instruction signature of Chainlink's real
//! Verifier program (devnet `Gt9S41PtjR58CbG9JhJ3J6vxesqrNAswbWYbLNTMZA3c`)
//! so the soothsayer-streams-relay-program's Phase 42b CPI shape can be
//! validated end-to-end on devnet without a Chainlink Streams subscription.
//!
//! Why this matters: the relay program's `post_relay_update` instruction
//! (when `verifier_cpi_required=1`) builds an Instruction via
//! `chainlink_solana_data_streams::VerifierInstructions::verify(...)` and
//! invokes it. The Instruction's program_id is whatever account is passed
//! as `verifier_program` — pointing it at this mock instead of Chainlink's
//! real Verifier lets the CPI succeed unconditionally, so we can prove
//! the relay's signature_verified=1 path persists correctly.
//!
//! Discriminator parity: this program defines a function literally named
//! `verify`. Anchor derives the 8-byte discriminator as
//! `sha256("global:verify")[..8]`, which matches what Chainlink's SDK
//! hardcodes as `discriminator::VERIFY = [133, 161, 141, 48, 120, 198, 88, 150]`
//! (verified against the SDK source at v1.1.0). Same discriminator ⇒ same
//! wire-format ⇒ the CPI Instruction routes correctly to whichever program
//! ID we point at.
//!
//! Account context parity: matches Chainlink's Verifier — 4 accounts
//! (verifier_account, access_controller, user signer, report_config) — so
//! Anchor's account validation accepts the SDK-built Instruction shape.
//!
//! **Production note:** never deploy this to mainnet. The real Verifier
//! does threshold-signature validation; this mock accepts anything. Production
//! AssetConfigs must point at Chainlink's real Verifier program.

use anchor_lang::prelude::*;

// Placeholder ID rewritten by `anchor keys sync` after first build.
declare_id!("G1FNffdhk83kejVjWXcHNbrX9y84nhx8EfzWu86EaKxL");

#[program]
pub mod mock_chainlink_verifier_program {
    use super::*;

    /// Mock verify: matches the real Verifier's instruction signature
    /// (`fn verify(ctx, signed_report: Vec<u8>) -> Result<()>`) so an
    /// Instruction built by `chainlink_solana_data_streams::VerifierInstructions::verify`
    /// routes here unchanged. Always returns Ok regardless of payload.
    ///
    /// Emits a `MockVerifyCalled` event with the report length so off-chain
    /// observers can confirm the CPI reached this program.
    pub fn verify(ctx: Context<Verify>, signed_report: Vec<u8>) -> Result<()> {
        emit!(MockVerifyCalled {
            user: ctx.accounts.user.key(),
            verifier_account: ctx.accounts.verifier_account.key(),
            report_len: signed_report.len() as u32,
        });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Verify<'info> {
    /// CHECK: matches Chainlink Verifier's `verifier_account` slot. Mock
    /// accepts any pubkey; the real Verifier validates this against its
    /// internal config PDA.
    pub verifier_account: UncheckedAccount<'info>,

    /// CHECK: matches Chainlink Verifier's `access_controller` slot. Mock
    /// accepts any pubkey; the real Verifier validates DON access lists.
    pub access_controller: UncheckedAccount<'info>,

    /// The signer of the verify call. In the relay-program path this is
    /// the writer keypair making the post.
    pub user: Signer<'info>,

    /// CHECK: matches Chainlink Verifier's `report_config` slot. Mock
    /// accepts any pubkey; the real Verifier validates the report's
    /// feed-id-derived config PDA.
    pub report_config: UncheckedAccount<'info>,
}

#[event]
pub struct MockVerifyCalled {
    pub user: Pubkey,
    pub verifier_account: Pubkey,
    pub report_len: u32,
}
