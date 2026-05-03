//! Wire-format builders for the soothsayer-oracle-program `publish` IX.
//!
//! Layout mirrors `programs/soothsayer-oracle-program/src/state.rs::PublishPayload`
//! and the `Publish` accounts struct in lib.rs. Discriminator is computed by
//! `anchor::ix_discriminator("publish")`.

use borsh::BorshSerialize;
use serde::{Deserialize, Serialize};
use solana_sdk::{
    instruction::{AccountMeta, Instruction},
    pubkey::Pubkey,
    sysvar,
};

use crate::{anchor::ix_discriminator, ORACLE_PROGRAM_ID};

#[derive(BorshSerialize, Clone, Debug)]
pub struct PublishPayload {
    pub version: u8,
    pub regime_code: u8,
    pub forecaster_code: u8,
    pub exponent: i8,
    pub target_coverage_bps: u16,
    pub claimed_served_bps: u16,
    pub buffer_applied_bps: u16,
    pub symbol: [u8; 16],
    pub point: i64,
    pub lower: i64,
    pub upper: i64,
    pub fri_close: i64,
    pub fri_ts: i64,
}

pub fn find_config_pda() -> (Pubkey, u8) {
    Pubkey::find_program_address(&[b"config"], &ORACLE_PROGRAM_ID)
}
pub fn find_signer_set_pda() -> (Pubkey, u8) {
    Pubkey::find_program_address(&[b"signer_set"], &ORACLE_PROGRAM_ID)
}
pub fn find_price_update_pda(symbol_padded: &[u8; 16]) -> (Pubkey, u8) {
    Pubkey::find_program_address(&[b"price", symbol_padded.as_ref()], &ORACLE_PROGRAM_ID)
}

pub fn publish_ix(signer: &Pubkey, price_update: &Pubkey, payload: &PublishPayload) -> Instruction {
    let (config, _) = find_config_pda();
    let (signer_set, _) = find_signer_set_pda();

    // Anchor IX accounts order matches the order fields appear in the
    // `Publish<'info>` struct: signer, config, signer_set, price_update,
    // system_program. is_signer / is_writable mirror the `#[account(...)]`
    // attributes in lib.rs.
    let accounts = vec![
        AccountMeta::new(*signer, true),
        AccountMeta::new_readonly(config, false),
        AccountMeta::new_readonly(signer_set, false),
        AccountMeta::new(*price_update, false),
        AccountMeta::new_readonly(solana_sdk::system_program::ID, false),
    ];
    let _ = sysvar::rent::ID; // silence unused-import warning if rent ever sneaks in

    let mut data = Vec::with_capacity(8 + 64);
    data.extend_from_slice(&ix_discriminator("publish"));
    payload.serialize(&mut data).expect("borsh serialize");
    Instruction {
        program_id: ORACLE_PROGRAM_ID,
        accounts,
        data,
    }
}

/// Lightweight artefact-record form of a published band. Stored in the JSON
/// ledger so future runs can reuse it without re-decoding.
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BandRecord {
    pub symbol: String,
    pub price_update: String,
    pub point: f64,
    pub lower: f64,
    pub upper: f64,
    pub target_coverage_bps: u16,
    pub claimed_served_bps: u16,
    pub regime_code: u8,
}
