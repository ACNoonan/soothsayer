//! Wire-format builders for the BandAMM IXs.
//!
//! Discriminators come from `anchor::ix_discriminator(<snake_name>)`. Account
//! ordering and writability mirror the `#[derive(Accounts)]` blocks in
//! `programs/soothsayer-band-amm-program/src/lib.rs`.

use borsh::BorshSerialize;
use solana_sdk::{
    instruction::{AccountMeta, Instruction},
    pubkey::Pubkey,
    sysvar,
};

use crate::{anchor::ix_discriminator, BAND_AMM_PROGRAM_ID};

#[derive(BorshSerialize, Clone, Debug)]
pub struct InitializePoolParams {
    pub authority: Pubkey,
    pub fee_bps_in: Option<u16>,
    pub fee_alpha_out_bps: Option<u16>,
    pub fee_w_max_bps: Option<u16>,
    pub max_band_staleness_secs: Option<u32>,
}

pub fn find_pool_pda(base_mint: &Pubkey, quote_mint: &Pubkey) -> (Pubkey, u8) {
    Pubkey::find_program_address(
        &[b"band_amm_pool", base_mint.as_ref(), quote_mint.as_ref()],
        &BAND_AMM_PROGRAM_ID,
    )
}
pub fn find_lp_mint_pda(pool: &Pubkey) -> (Pubkey, u8) {
    Pubkey::find_program_address(&[b"lp_mint", pool.as_ref()], &BAND_AMM_PROGRAM_ID)
}
pub fn find_vault_pda(pool: &Pubkey, mint: &Pubkey) -> (Pubkey, u8) {
    Pubkey::find_program_address(
        &[b"vault", pool.as_ref(), mint.as_ref()],
        &BAND_AMM_PROGRAM_ID,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn initialize_pool_ix(
    payer: &Pubkey,
    base_mint: &Pubkey,
    quote_mint: &Pubkey,
    pool: &Pubkey,
    lp_mint: &Pubkey,
    base_vault: &Pubkey,
    quote_vault: &Pubkey,
    price_update: &Pubkey,
    params: InitializePoolParams,
) -> Instruction {
    let accounts = vec![
        AccountMeta::new(*payer, true),
        AccountMeta::new_readonly(*base_mint, false),
        AccountMeta::new_readonly(*quote_mint, false),
        AccountMeta::new(*pool, false),
        AccountMeta::new(*lp_mint, false),
        AccountMeta::new(*base_vault, false),
        AccountMeta::new(*quote_vault, false),
        AccountMeta::new_readonly(*price_update, false),
        AccountMeta::new_readonly(solana_sdk::system_program::ID, false),
        AccountMeta::new_readonly(spl_token::ID, false),
        AccountMeta::new_readonly(sysvar::rent::ID, false),
    ];
    let mut data = Vec::with_capacity(8 + 64);
    data.extend_from_slice(&ix_discriminator("initialize_pool"));
    params.serialize(&mut data).expect("borsh serialize params");
    Instruction {
        program_id: BAND_AMM_PROGRAM_ID,
        accounts,
        data,
    }
}

#[allow(clippy::too_many_arguments)]
pub fn deposit_ix(
    user: &Pubkey,
    pool: &Pubkey,
    lp_mint: &Pubkey,
    base_vault: &Pubkey,
    quote_vault: &Pubkey,
    user_base: &Pubkey,
    user_quote: &Pubkey,
    user_lp: &Pubkey,
    amount_base: u64,
    amount_quote: u64,
    min_lp_out: u64,
) -> Instruction {
    let accounts = vec![
        AccountMeta::new_readonly(*user, true),
        AccountMeta::new(*pool, false),
        AccountMeta::new(*lp_mint, false),
        AccountMeta::new(*base_vault, false),
        AccountMeta::new(*quote_vault, false),
        AccountMeta::new(*user_base, false),
        AccountMeta::new(*user_quote, false),
        AccountMeta::new(*user_lp, false),
        AccountMeta::new_readonly(spl_token::ID, false),
    ];
    let mut data = Vec::with_capacity(8 + 24);
    data.extend_from_slice(&ix_discriminator("deposit"));
    amount_base.serialize(&mut data).unwrap();
    amount_quote.serialize(&mut data).unwrap();
    min_lp_out.serialize(&mut data).unwrap();
    Instruction {
        program_id: BAND_AMM_PROGRAM_ID,
        accounts,
        data,
    }
}

#[allow(clippy::too_many_arguments)]
pub fn swap_ix(
    user: &Pubkey,
    pool: &Pubkey,
    base_vault: &Pubkey,
    quote_vault: &Pubkey,
    user_base: &Pubkey,
    user_quote: &Pubkey,
    price_update: &Pubkey,
    amount_in: u64,
    min_amount_out: u64,
    side_base_in: bool,
) -> Instruction {
    let accounts = vec![
        AccountMeta::new_readonly(*user, true),
        AccountMeta::new(*pool, false),
        AccountMeta::new(*base_vault, false),
        AccountMeta::new(*quote_vault, false),
        AccountMeta::new(*user_base, false),
        AccountMeta::new(*user_quote, false),
        AccountMeta::new_readonly(*price_update, false),
        AccountMeta::new_readonly(spl_token::ID, false),
    ];
    let mut data = Vec::with_capacity(8 + 17);
    data.extend_from_slice(&ix_discriminator("swap"));
    amount_in.serialize(&mut data).unwrap();
    min_amount_out.serialize(&mut data).unwrap();
    side_base_in.serialize(&mut data).unwrap();
    Instruction {
        program_id: BAND_AMM_PROGRAM_ID,
        accounts,
        data,
    }
}
