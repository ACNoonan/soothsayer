//! BandAMM integration tests via `solana-program-test` in native (processor!)
//! mode. Covers the surface in `colosseum_test_plan.md` §5.
//!
//! Native execution means we bypass the BPF .so artefact and run the
//! program against an in-process BanksClient. Faster than localnet,
//! supports clock manipulation, and lets us synthesise the soothsayer
//! `PriceUpdate` PDA byte-perfect via `ProgramTestContext::set_account` —
//! the path the test plan §5 explicitly contemplates.
//!
//! Run with: `cargo test --test integration` from the program crate root.

#![allow(clippy::too_many_arguments)]

use anchor_lang::{AnchorDeserialize, Discriminator, InstructionData, ToAccountMetas};
use solana_program_test::{ProgramTest, ProgramTestContext};
use solana_sdk::{
    account::Account as SdkAccount,
    instruction::Instruction,
    program_pack::Pack,
    pubkey::Pubkey,
    rent::Rent,
    signature::{Keypair, Signer},
    system_instruction,
    transaction::Transaction,
};

use soothsayer_band_amm_program::{
    accounts as ix_accts, instruction as ix_data, InitializePoolParams, Swapped,
};
use soothsayer_consumer::{
    PriceBand, PRICE_UPDATE_DISCRIMINATOR, PRICE_UPDATE_VERSION, PROFILE_AMM,
};
use spl_token::state::{Account as TokenAccountState, Mint as MintState};

// ─────────────────────────────────── constants ───────────────────────────────

const SPYX_DECIMALS: u8 = 8;
const USDC_DECIMALS: u8 = 6;
const BAND_EXPONENT: i8 = -8;

const INITIAL_BASE_DEPOSIT: u64 = 10 * 10u64.pow(SPYX_DECIMALS as u32);
const INITIAL_QUOTE_DEPOSIT: u64 = 7_000 * 10u64.pow(USDC_DECIMALS as u32);

const DEFAULT_BAND_LOWER: i64 = 689_500_000_00; // $689.50 at exp=-8
const DEFAULT_BAND_POINT: i64 = 700_000_000_00;
const DEFAULT_BAND_UPPER: i64 = 710_500_000_00;

const DEFAULT_FEE_BPS_IN: u16 = 5;
const DEFAULT_FEE_ALPHA_OUT_BPS: u16 = 100;
const DEFAULT_FEE_W_MAX_BPS: u16 = 10_000;
const DEFAULT_MAX_STALENESS_SECS: u32 = 60;

// ─────────────────────────────────── fixtures ────────────────────────────────

struct PoolFixture {
    payer: Keypair,
    authority: Keypair,
    base_mint: Pubkey,
    quote_mint: Pubkey,
    pool: Pubkey,
    lp_mint: Pubkey,
    base_vault: Pubkey,
    quote_vault: Pubkey,
    price_update: Pubkey,

    /// Payer-side ATAs from setup. Payer holds all LP from the initial deposit.
    payer_base: Pubkey,
    payer_quote: Pubkey,
    payer_lp: Pubkey,

    /// Test-time anchor timestamp — captured at setup, used as the "now" for
    /// synthesised band publish_ts values.
    setup_unix_ts: i64,
}

async fn setup_funded_pool() -> (ProgramTestContext, PoolFixture) {
    // BPF mode: load the .so from `tests/fixtures/` or `$SBF_OUT_DIR`. The
    // anchor-0.31 + solana-program-test-2.3 lifetime mismatch makes native
    // (processor!) execution non-trivial; a `.so` round-trip is fine for
    // the hackathon and is what eventually runs on devnet anyway.
    let mut pt = ProgramTest::new(
        "soothsayer_band_amm_program",
        soothsayer_band_amm_program::ID,
        None,
    );
    pt.prefer_bpf(true);
    // spl-token is preloaded by solana-program-test's default genesis.

    let mut ctx = pt.start_with_context().await;
    let payer = clone_keypair(&ctx.payer);
    let authority = Keypair::new();

    let setup_unix_ts = current_unix_ts(&mut ctx).await;

    airdrop(&mut ctx, &authority.pubkey(), 1_000_000_000).await;

    let base_mint = create_mint(&mut ctx, &payer, SPYX_DECIMALS, &payer.pubkey()).await;
    let quote_mint = create_mint(&mut ctx, &payer, USDC_DECIMALS, &payer.pubkey()).await;

    let (pool, _pool_bump) = Pubkey::find_program_address(
        &[b"band_amm_pool", base_mint.as_ref(), quote_mint.as_ref()],
        &soothsayer_band_amm_program::ID,
    );
    let (lp_mint, _) = Pubkey::find_program_address(
        &[b"lp_mint", pool.as_ref()],
        &soothsayer_band_amm_program::ID,
    );
    let (base_vault, _) = Pubkey::find_program_address(
        &[b"vault", pool.as_ref(), base_mint.as_ref()],
        &soothsayer_band_amm_program::ID,
    );
    let (quote_vault, _) = Pubkey::find_program_address(
        &[b"vault", pool.as_ref(), quote_mint.as_ref()],
        &soothsayer_band_amm_program::ID,
    );

    let price_update = Pubkey::new_unique();
    write_band_account(&mut ctx, &price_update, default_band(setup_unix_ts)).await;

    init_pool(&mut ctx, &payer, &authority, &base_mint, &quote_mint, &price_update).await;

    let payer_base = create_ata_with_balance(
        &mut ctx,
        &payer,
        &payer.pubkey(),
        &base_mint,
        100 * 10u64.pow(SPYX_DECIMALS as u32),
    )
    .await;
    let payer_quote = create_ata_with_balance(
        &mut ctx,
        &payer,
        &payer.pubkey(),
        &quote_mint,
        70_000 * 10u64.pow(USDC_DECIMALS as u32),
    )
    .await;
    let payer_lp = create_ata(&mut ctx, &payer, &payer.pubkey(), &lp_mint).await;

    deposit_ix(
        &mut ctx,
        &payer,
        &PoolAccts {
            pool,
            lp_mint,
            base_vault,
            quote_vault,
            base_mint,
            quote_mint,
        },
        &payer_base,
        &payer_quote,
        &payer_lp,
        INITIAL_BASE_DEPOSIT,
        INITIAL_QUOTE_DEPOSIT,
        0,
    )
    .await
    .expect("initial deposit");

    (
        ctx,
        PoolFixture {
            payer,
            authority,
            base_mint,
            quote_mint,
            pool,
            lp_mint,
            base_vault,
            quote_vault,
            price_update,
            payer_base,
            payer_quote,
            payer_lp,
            setup_unix_ts,
        },
    )
}

// ─────────────────────────────────── helpers ─────────────────────────────────

fn clone_keypair(kp: &Keypair) -> Keypair {
    Keypair::from_bytes(&kp.to_bytes()).unwrap()
}

async fn current_unix_ts(ctx: &mut ProgramTestContext) -> i64 {
    let clock_account = ctx
        .banks_client
        .get_account(solana_sdk::sysvar::clock::ID)
        .await
        .ok()
        .flatten()
        .expect("clock sysvar present");
    let clock: solana_sdk::clock::Clock = bincode::deserialize(&clock_account.data).unwrap();
    clock.unix_timestamp
}

async fn airdrop(ctx: &mut ProgramTestContext, to: &Pubkey, lamports: u64) {
    let payer = clone_keypair(&ctx.payer);
    let ix = system_instruction::transfer(&payer.pubkey(), to, lamports);
    let blockhash = refresh_blockhash(ctx).await;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&payer.pubkey()),
        &[&payer],
        blockhash,
    );
    ctx.banks_client.process_transaction(tx).await.unwrap();
}

async fn create_mint(
    ctx: &mut ProgramTestContext,
    payer: &Keypair,
    decimals: u8,
    authority: &Pubkey,
) -> Pubkey {
    let mint = Keypair::new();
    let rent = Rent::default().minimum_balance(MintState::LEN);
    let create = system_instruction::create_account(
        &payer.pubkey(),
        &mint.pubkey(),
        rent,
        MintState::LEN as u64,
        &spl_token::ID,
    );
    let init = spl_token::instruction::initialize_mint(
        &spl_token::ID,
        &mint.pubkey(),
        authority,
        None,
        decimals,
    )
    .unwrap();
    let blockhash = refresh_blockhash(ctx).await;
    let tx = Transaction::new_signed_with_payer(
        &[create, init],
        Some(&payer.pubkey()),
        &[payer, &mint],
        blockhash,
    );
    ctx.banks_client.process_transaction(tx).await.unwrap();
    mint.pubkey()
}

async fn create_ata(
    ctx: &mut ProgramTestContext,
    payer: &Keypair,
    owner: &Pubkey,
    mint: &Pubkey,
) -> Pubkey {
    let ata = Keypair::new();
    let rent = Rent::default().minimum_balance(TokenAccountState::LEN);
    let create = system_instruction::create_account(
        &payer.pubkey(),
        &ata.pubkey(),
        rent,
        TokenAccountState::LEN as u64,
        &spl_token::ID,
    );
    let init = spl_token::instruction::initialize_account(&spl_token::ID, &ata.pubkey(), mint, owner)
        .unwrap();
    let blockhash = refresh_blockhash(ctx).await;
    let tx = Transaction::new_signed_with_payer(
        &[create, init],
        Some(&payer.pubkey()),
        &[payer, &ata],
        blockhash,
    );
    ctx.banks_client.process_transaction(tx).await.unwrap();
    ata.pubkey()
}

async fn create_ata_with_balance(
    ctx: &mut ProgramTestContext,
    payer: &Keypair,
    owner: &Pubkey,
    mint: &Pubkey,
    amount: u64,
) -> Pubkey {
    let ata = create_ata(ctx, payer, owner, mint).await;
    let mint_ix =
        spl_token::instruction::mint_to(&spl_token::ID, mint, &ata, &payer.pubkey(), &[], amount)
            .unwrap();
    let blockhash = refresh_blockhash(ctx).await;
    let tx = Transaction::new_signed_with_payer(
        &[mint_ix],
        Some(&payer.pubkey()),
        &[payer],
        blockhash,
    );
    ctx.banks_client.process_transaction(tx).await.unwrap();
    ata
}

async fn refresh_blockhash(ctx: &mut ProgramTestContext) -> solana_sdk::hash::Hash {
    ctx.banks_client.get_latest_blockhash().await.unwrap()
}

/// Synthesize the on-wire bytes of a `PriceUpdate` account: 8-byte Anchor
/// discriminator + 128-byte body. Layout matches
/// `programs/soothsayer-oracle-program/src/state.rs` exactly.
fn synth_price_update_data(b: &PriceBand) -> Vec<u8> {
    let mut data = Vec::with_capacity(8 + 128);
    data.extend_from_slice(&PRICE_UPDATE_DISCRIMINATOR);
    data.push(b.version);
    data.push(b.regime_code);
    data.push(b.forecaster_code);
    data.push(b.exponent as u8);
    data.push(b.profile_code);             // reports/active/m6_refactor.md A4: was _pad0[0]
    data.extend_from_slice(&[0u8; 3]);     // remaining _pad0[1..4]
    data.extend_from_slice(&b.target_coverage_bps.to_le_bytes());
    data.extend_from_slice(&b.claimed_served_bps.to_le_bytes());
    data.extend_from_slice(&b.buffer_applied_bps.to_le_bytes());
    data.extend_from_slice(&[0u8; 2]); // _pad1
    data.extend_from_slice(&b.symbol);
    data.extend_from_slice(&b.point.to_le_bytes());
    data.extend_from_slice(&b.lower.to_le_bytes());
    data.extend_from_slice(&b.upper.to_le_bytes());
    data.extend_from_slice(&b.fri_close.to_le_bytes());
    data.extend_from_slice(&b.fri_ts.to_le_bytes());
    data.extend_from_slice(&b.publish_ts.to_le_bytes());
    data.extend_from_slice(&b.publish_slot.to_le_bytes());
    data.extend_from_slice(&b.signer);
    data.extend_from_slice(&b.signer_epoch.to_le_bytes());
    assert_eq!(data.len(), 8 + 128);
    data
}

fn default_band(now_ts: i64) -> PriceBand {
    PriceBand {
        version: PRICE_UPDATE_VERSION,
        regime_code: 0,
        forecaster_code: 0,
        exponent: BAND_EXPONENT,
        profile_code: PROFILE_AMM,
        target_coverage_bps: 9500,
        claimed_served_bps: 9750,
        buffer_applied_bps: 250,
        symbol: pad_symbol(b"SPY"),
        point: DEFAULT_BAND_POINT,
        lower: DEFAULT_BAND_LOWER,
        upper: DEFAULT_BAND_UPPER,
        fri_close: DEFAULT_BAND_POINT,
        fri_ts: now_ts - 86_400,
        publish_ts: now_ts,
        publish_slot: 0,
        signer: [0u8; 32],
        signer_epoch: 1,
    }
}

fn pad_symbol(s: &[u8]) -> [u8; 16] {
    let mut out = [0u8; 16];
    out[..s.len()].copy_from_slice(s);
    out
}

async fn write_band_account(ctx: &mut ProgramTestContext, pubkey: &Pubkey, band: PriceBand) {
    let data = synth_price_update_data(&band);
    let rent = Rent::default().minimum_balance(data.len()).max(1);
    let account = SdkAccount {
        lamports: rent,
        data,
        owner: soothsayer_oracle_program_id(),
        executable: false,
        rent_epoch: 0,
    };
    ctx.set_account(pubkey, &account.into());
}

fn soothsayer_oracle_program_id() -> Pubkey {
    "AgXLLTmUJEVh9EsJnznU1yJaUeE9Ufe7ZotupmDqa7f6"
        .parse()
        .unwrap()
}

// ─────────────────────────────── IX builders ────────────────────────────────

struct PoolAccts {
    pool: Pubkey,
    lp_mint: Pubkey,
    base_vault: Pubkey,
    quote_vault: Pubkey,
    base_mint: Pubkey,
    quote_mint: Pubkey,
}

async fn init_pool(
    ctx: &mut ProgramTestContext,
    payer: &Keypair,
    authority: &Keypair,
    base_mint: &Pubkey,
    quote_mint: &Pubkey,
    price_update: &Pubkey,
) {
    let (pool, _) = Pubkey::find_program_address(
        &[b"band_amm_pool", base_mint.as_ref(), quote_mint.as_ref()],
        &soothsayer_band_amm_program::ID,
    );
    let (lp_mint, _) = Pubkey::find_program_address(
        &[b"lp_mint", pool.as_ref()],
        &soothsayer_band_amm_program::ID,
    );
    let (base_vault, _) = Pubkey::find_program_address(
        &[b"vault", pool.as_ref(), base_mint.as_ref()],
        &soothsayer_band_amm_program::ID,
    );
    let (quote_vault, _) = Pubkey::find_program_address(
        &[b"vault", pool.as_ref(), quote_mint.as_ref()],
        &soothsayer_band_amm_program::ID,
    );

    let accts = ix_accts::InitializePool {
        payer: payer.pubkey(),
        base_mint: *base_mint,
        quote_mint: *quote_mint,
        pool,
        lp_mint,
        base_vault,
        quote_vault,
        price_update: *price_update,
        system_program: solana_sdk::system_program::ID,
        token_program: spl_token::ID,
        rent: solana_sdk::sysvar::rent::ID,
    };
    let data = ix_data::InitializePool {
        params: InitializePoolParams {
            authority: authority.pubkey(),
            fee_bps_in: Some(DEFAULT_FEE_BPS_IN),
            fee_alpha_out_bps: Some(DEFAULT_FEE_ALPHA_OUT_BPS),
            fee_w_max_bps: Some(DEFAULT_FEE_W_MAX_BPS),
            max_band_staleness_secs: Some(DEFAULT_MAX_STALENESS_SECS),
        },
    }
    .data();

    let ix = Instruction {
        program_id: soothsayer_band_amm_program::ID,
        accounts: accts.to_account_metas(None),
        data,
    };
    let blockhash = refresh_blockhash(ctx).await;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&payer.pubkey()),
        &[payer],
        blockhash,
    );
    ctx.banks_client
        .process_transaction(tx)
        .await
        .expect("init_pool");
}

async fn deposit_ix(
    ctx: &mut ProgramTestContext,
    user: &Keypair,
    pool: &PoolAccts,
    user_base: &Pubkey,
    user_quote: &Pubkey,
    user_lp: &Pubkey,
    amount_base: u64,
    amount_quote: u64,
    min_lp_out: u64,
) -> Result<(), solana_program_test::BanksClientError> {
    let accts = ix_accts::Deposit {
        user: user.pubkey(),
        pool: pool.pool,
        lp_mint: pool.lp_mint,
        base_vault: pool.base_vault,
        quote_vault: pool.quote_vault,
        user_base: *user_base,
        user_quote: *user_quote,
        user_lp: *user_lp,
        token_program: spl_token::ID,
    };
    let data = ix_data::Deposit {
        amount_base,
        amount_quote,
        min_lp_out,
    }
    .data();
    let ix = Instruction {
        program_id: soothsayer_band_amm_program::ID,
        accounts: accts.to_account_metas(None),
        data,
    };
    let blockhash = refresh_blockhash(ctx).await;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&user.pubkey()),
        &[user],
        blockhash,
    );
    ctx.banks_client.process_transaction(tx).await
}

async fn withdraw_ix(
    ctx: &mut ProgramTestContext,
    user: &Keypair,
    pool: &PoolAccts,
    user_base: &Pubkey,
    user_quote: &Pubkey,
    user_lp: &Pubkey,
    lp_amount: u64,
    min_base_out: u64,
    min_quote_out: u64,
) -> Result<(), solana_program_test::BanksClientError> {
    let accts = ix_accts::Withdraw {
        user: user.pubkey(),
        pool: pool.pool,
        lp_mint: pool.lp_mint,
        base_vault: pool.base_vault,
        quote_vault: pool.quote_vault,
        user_base: *user_base,
        user_quote: *user_quote,
        user_lp: *user_lp,
        token_program: spl_token::ID,
    };
    let data = ix_data::Withdraw {
        lp_amount,
        min_base_out,
        min_quote_out,
    }
    .data();
    let ix = Instruction {
        program_id: soothsayer_band_amm_program::ID,
        accounts: accts.to_account_metas(None),
        data,
    };
    let blockhash = refresh_blockhash(ctx).await;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&user.pubkey()),
        &[user],
        blockhash,
    );
    ctx.banks_client.process_transaction(tx).await
}

async fn swap_ix(
    ctx: &mut ProgramTestContext,
    user: &Keypair,
    pool: &PoolAccts,
    price_update: &Pubkey,
    user_base: &Pubkey,
    user_quote: &Pubkey,
    amount_in: u64,
    min_amount_out: u64,
    side_base_in: bool,
) -> Result<Vec<u8>, solana_program_test::BanksClientError> {
    let accts = ix_accts::Swap {
        user: user.pubkey(),
        pool: pool.pool,
        base_vault: pool.base_vault,
        quote_vault: pool.quote_vault,
        user_base: *user_base,
        user_quote: *user_quote,
        price_update: *price_update,
        token_program: spl_token::ID,
    };
    let data = ix_data::Swap {
        amount_in,
        min_amount_out,
        side_base_in,
    }
    .data();
    let ix = Instruction {
        program_id: soothsayer_band_amm_program::ID,
        accounts: accts.to_account_metas(None),
        data,
    };
    let blockhash = refresh_blockhash(ctx).await;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&user.pubkey()),
        &[user],
        blockhash,
    );
    let meta = ctx
        .banks_client
        .process_transaction_with_metadata(tx)
        .await?;
    meta.result?;
    let logs = meta
        .metadata
        .map(|m| m.log_messages)
        .unwrap_or_default();
    Ok(extract_swapped_event(&logs))
}

async fn set_paused_ix(
    ctx: &mut ProgramTestContext,
    authority: &Keypair,
    pool: &PoolAccts,
    paused: bool,
) -> Result<(), solana_program_test::BanksClientError> {
    let accts = ix_accts::AuthorityOnly {
        authority: authority.pubkey(),
        pool: pool.pool,
    };
    let data = ix_data::SetPaused { paused }.data();
    let ix = Instruction {
        program_id: soothsayer_band_amm_program::ID,
        accounts: accts.to_account_metas(None),
        data,
    };
    let blockhash = refresh_blockhash(ctx).await;
    let tx = Transaction::new_signed_with_payer(
        &[ix],
        Some(&authority.pubkey()),
        &[authority],
        blockhash,
    );
    ctx.banks_client.process_transaction(tx).await
}

/// Find the `Swapped` event bytes in transaction logs by scanning for the
/// Anchor event discriminator. Returns the body bytes (post-discriminator)
/// for `Swapped::try_from_slice`.
fn extract_swapped_event(logs: &[String]) -> Vec<u8> {
    use base64::Engine;
    let disc = Swapped::DISCRIMINATOR;
    for line in logs {
        if let Some(rest) = line.strip_prefix("Program data: ") {
            let bytes = base64::engine::general_purpose::STANDARD
                .decode(rest)
                .unwrap_or_default();
            if bytes.len() >= 8 && bytes[..8] == *disc {
                return bytes[8..].to_vec();
            }
        }
    }
    Vec::new()
}

async fn token_balance(ctx: &mut ProgramTestContext, ata: &Pubkey) -> u64 {
    let acc = ctx.banks_client.get_account(*ata).await.unwrap().unwrap();
    let parsed = TokenAccountState::unpack(&acc.data).unwrap();
    parsed.amount
}

fn pool_accts(fix: &PoolFixture) -> PoolAccts {
    PoolAccts {
        pool: fix.pool,
        lp_mint: fix.lp_mint,
        base_vault: fix.base_vault,
        quote_vault: fix.quote_vault,
        base_mint: fix.base_mint,
        quote_mint: fix.quote_mint,
    }
}

async fn fund_user(
    ctx: &mut ProgramTestContext,
    fix: &PoolFixture,
) -> (Keypair, Pubkey, Pubkey) {
    let user = Keypair::new();
    airdrop(ctx, &user.pubkey(), 1_000_000_000).await;
    let user_base = create_ata_with_balance(
        ctx,
        &fix.payer,
        &user.pubkey(),
        &fix.base_mint,
        10 * 10u64.pow(SPYX_DECIMALS as u32),
    )
    .await;
    let user_quote = create_ata_with_balance(
        ctx,
        &fix.payer,
        &user.pubkey(),
        &fix.quote_mint,
        10_000 * 10u64.pow(USDC_DECIMALS as u32),
    )
    .await;
    (user, user_base, user_quote)
}

fn assert_contains(haystack: &str, needle: &str) {
    assert!(
        haystack.contains(needle),
        "expected `{}` in error: {}",
        needle,
        haystack
    );
}

/// Anchor error codes are offset by `ERROR_CODE_OFFSET = 6000`. Resolve a
/// `BandAmmError` enum discriminant to the on-wire `Custom(N)` value the
/// transaction error reports.
fn anchor_err_code(idx: u32) -> u32 {
    anchor_lang::error::ERROR_CODE_OFFSET + idx
}

#[allow(dead_code)]
const ERR_POOL_PAUSED: u32 = 0;
#[allow(dead_code)]
const ERR_BAND_REJECTED: u32 = 1;
#[allow(dead_code)]
const ERR_BAND_STALE: u32 = 2;
#[allow(dead_code)]
const ERR_WRONG_PRICE_UPDATE: u32 = 3;

fn assert_anchor_error(
    err: &solana_program_test::BanksClientError,
    expected_idx: u32,
) {
    let msg = format!("{err:?}");
    let expected = format!("Custom({})", anchor_err_code(expected_idx));
    assert!(
        msg.contains(&expected),
        "expected error code {expected}, got: {msg}"
    );
}

// ─────────────────────────────────── tests ───────────────────────────────────

// §5.1 happy path: deposit-side already exercised in setup. This adds a swap
// that lands in-band, asserts the receipt event and SPL balances reconcile.
#[tokio::test]
async fn swap_inband_credits_user_and_emits_inband_receipt() {
    let (mut ctx, fix) = setup_funded_pool().await;
    let pool_accts = pool_accts(&fix);

    let (user, user_base, user_quote) = fund_user(&mut ctx, &fix).await;
    let user_quote_pre = token_balance(&mut ctx, &user_quote).await;

    let one_cent = 10u64.pow(SPYX_DECIMALS as u32) / 100;
    let event_bytes = swap_ix(
        &mut ctx,
        &user,
        &pool_accts,
        &fix.price_update,
        &user_base,
        &user_quote,
        one_cent,
        1,
        true,
    )
    .await
    .expect("inband swap");
    let ev = Swapped::try_from_slice(&event_bytes).expect("parse Swapped");
    assert!(!ev.fee_tier_out_of_band, "must be in-band tier");
    assert_eq!(ev.effective_fee_bps, DEFAULT_FEE_BPS_IN as u32);
    assert_eq!(ev.amount_in, one_cent);
    assert!(ev.amount_out > 0, "swap must produce non-zero output");

    let user_quote_post = token_balance(&mut ctx, &user_quote).await;
    assert_eq!(user_quote_post - user_quote_pre, ev.amount_out);
}

// §5.3 audit-chain receipt invariant.
#[tokio::test]
async fn swap_event_matches_band_pda_at_publish_slot() {
    let (mut ctx, fix) = setup_funded_pool().await;
    let pool_accts = pool_accts(&fix);

    let custom = PriceBand {
        version: PRICE_UPDATE_VERSION,
        regime_code: 1,
        forecaster_code: 0,
        exponent: BAND_EXPONENT,
        profile_code: PROFILE_AMM,
        target_coverage_bps: 9500,
        claimed_served_bps: 9612,
        buffer_applied_bps: 250,
        symbol: pad_symbol(b"SPY"),
        point: 705_000_000_00,
        lower: 697_000_000_00,
        upper: 713_000_000_00,
        fri_close: 705_000_000_00,
        fri_ts: fix.setup_unix_ts - 86_400,
        publish_ts: fix.setup_unix_ts,
        publish_slot: 12_345,
        signer: [7u8; 32],
        signer_epoch: 9,
    };
    write_band_account(&mut ctx, &fix.price_update, custom.clone()).await;

    let (user, user_base, user_quote) = fund_user(&mut ctx, &fix).await;
    let one_cent = 10u64.pow(SPYX_DECIMALS as u32) / 100;
    let event_bytes = swap_ix(
        &mut ctx,
        &user,
        &pool_accts,
        &fix.price_update,
        &user_base,
        &user_quote,
        one_cent,
        1,
        true,
    )
    .await
    .expect("swap with custom band");
    let ev = Swapped::try_from_slice(&event_bytes).unwrap();

    assert_eq!(ev.band_lower, custom.lower);
    assert_eq!(ev.band_upper, custom.upper);
    assert_eq!(ev.band_exponent, custom.exponent);
    assert_eq!(ev.band_publish_ts, custom.publish_ts);
    assert_eq!(ev.band_publish_slot, custom.publish_slot);
    assert_eq!(ev.claimed_served_bps, custom.claimed_served_bps);
    assert_eq!(ev.regime_code, custom.regime_code);
}

// §5.2 stale-band guard.
#[tokio::test]
async fn swap_with_stale_band_rejected_then_unblocked_after_refresh() {
    let (mut ctx, fix) = setup_funded_pool().await;
    let pool_accts = pool_accts(&fix);

    let mut stale = default_band(fix.setup_unix_ts);
    stale.publish_ts = fix.setup_unix_ts - (DEFAULT_MAX_STALENESS_SECS as i64) * 2;
    write_band_account(&mut ctx, &fix.price_update, stale).await;

    let (user, user_base, user_quote) = fund_user(&mut ctx, &fix).await;
    let result = swap_ix(
        &mut ctx,
        &user,
        &pool_accts,
        &fix.price_update,
        &user_base,
        &user_quote,
        10_000,
        1,
        true,
    )
    .await;
    let err = result.expect_err("stale band must be rejected");
    assert_anchor_error(&err, ERR_BAND_STALE);

    // Republish a fresh band; same swap now succeeds. Use a different
    // amount_in so the tx doesn't collide with the rejected pre-refresh one.
    let fresh_now = current_unix_ts(&mut ctx).await;
    write_band_account(&mut ctx, &fix.price_update, default_band(fresh_now)).await;
    swap_ix(
        &mut ctx,
        &user,
        &pool_accts,
        &fix.price_update,
        &user_base,
        &user_quote,
        10_001,
        1,
        true,
    )
    .await
    .expect("after refresh, swap succeeds");
}

// §5.2 attacker-supplied PriceUpdate rejected by the address constraint.
#[tokio::test]
async fn swap_with_attacker_supplied_fake_price_pda_rejected() {
    let (mut ctx, fix) = setup_funded_pool().await;
    let pool_accts = pool_accts(&fix);

    let fake = Pubkey::new_unique();
    write_band_account(&mut ctx, &fake, default_band(fix.setup_unix_ts)).await;

    let (user, user_base, user_quote) = fund_user(&mut ctx, &fix).await;
    let result = swap_ix(
        &mut ctx,
        &user,
        &pool_accts,
        &fake,
        &user_base,
        &user_quote,
        10_000,
        1,
        true,
    )
    .await;
    let err = result.expect_err("fake price_update must be rejected");
    assert_anchor_error(&err, ERR_WRONG_PRICE_UPDATE);
}

// §5.2 paused pool refuses swap.
#[tokio::test]
async fn paused_pool_refuses_swap_then_unpause_restores() {
    let (mut ctx, fix) = setup_funded_pool().await;
    let pool_accts = pool_accts(&fix);

    set_paused_ix(&mut ctx, &fix.authority, &pool_accts, true)
        .await
        .expect("pause");

    let (user, user_base, user_quote) = fund_user(&mut ctx, &fix).await;
    let result = swap_ix(
        &mut ctx,
        &user,
        &pool_accts,
        &fix.price_update,
        &user_base,
        &user_quote,
        10_000,
        1,
        true,
    )
    .await;
    let err = result.expect_err("paused pool must refuse swaps");
    assert_anchor_error(&err, ERR_POOL_PAUSED);

    set_paused_ix(&mut ctx, &fix.authority, &pool_accts, false)
        .await
        .expect("unpause");
    // Tweak amount so the second tx differs from the rejected pre-pause one
    // (BanksClient tracks both processed and rejected tx bytes as "seen").
    swap_ix(
        &mut ctx,
        &user,
        &pool_accts,
        &fix.price_update,
        &user_base,
        &user_quote,
        10_001,
        1,
        true,
    )
    .await
    .expect("after unpause, swap succeeds");
}

// §3.4 policy: paused pool *allows* withdraw (LPs can always exit).
#[tokio::test]
async fn paused_pool_allows_withdraw() {
    let (mut ctx, fix) = setup_funded_pool().await;
    let pool_accts = pool_accts(&fix);

    set_paused_ix(&mut ctx, &fix.authority, &pool_accts, true)
        .await
        .expect("pause");

    // Payer holds all LP from the initial deposit. Withdraw 10%.
    let payer_lp_balance = token_balance(&mut ctx, &fix.payer_lp).await;
    assert!(payer_lp_balance > 0);

    let to_burn = payer_lp_balance / 10;
    withdraw_ix(
        &mut ctx,
        &fix.payer,
        &pool_accts,
        &fix.payer_base,
        &fix.payer_quote,
        &fix.payer_lp,
        to_burn,
        1,
        1,
    )
    .await
    .expect("withdraw on paused pool must succeed");

    // LP balance dropped by exactly the burned amount.
    assert_eq!(
        token_balance(&mut ctx, &fix.payer_lp).await,
        payer_lp_balance - to_burn
    );
}

// §5.1 deposit→swap→withdraw round trip across two LPs proves prorata fee accrual.
#[tokio::test]
async fn two_lps_then_swaps_then_both_withdraw_share_fees_prorata() {
    let (mut ctx, fix) = setup_funded_pool().await;
    let pool_accts = pool_accts(&fix);

    // Second LP with the same notional as the first (gives 50/50 LP supply
    // after their deposit).
    let lp2 = Keypair::new();
    airdrop(&mut ctx, &lp2.pubkey(), 1_000_000_000).await;
    let lp2_base = create_ata_with_balance(
        &mut ctx,
        &fix.payer,
        &lp2.pubkey(),
        &fix.base_mint,
        20 * 10u64.pow(SPYX_DECIMALS as u32),
    )
    .await;
    let lp2_quote = create_ata_with_balance(
        &mut ctx,
        &fix.payer,
        &lp2.pubkey(),
        &fix.quote_mint,
        20_000 * 10u64.pow(USDC_DECIMALS as u32),
    )
    .await;
    let lp2_lp = create_ata(&mut ctx, &fix.payer, &lp2.pubkey(), &fix.lp_mint).await;

    deposit_ix(
        &mut ctx,
        &lp2,
        &pool_accts,
        &lp2_base,
        &lp2_quote,
        &lp2_lp,
        INITIAL_BASE_DEPOSIT,
        INITIAL_QUOTE_DEPOSIT,
        0,
    )
    .await
    .expect("LP2 deposit");

    // A few in-band swaps to accrue fees. Varying amount_in per iteration
    // keeps each tx's instruction-bytes distinct (otherwise BanksClient
    // returns AlreadyProcessed for identical signed messages).
    let (user, user_base, user_quote) = fund_user(&mut ctx, &fix).await;
    let one_cent = 10u64.pow(SPYX_DECIMALS as u32) / 100;
    for i in 0..5u64 {
        swap_ix(
            &mut ctx,
            &user,
            &pool_accts,
            &fix.price_update,
            &user_base,
            &user_quote,
            one_cent + i,
            1,
            true,
        )
        .await
        .expect("swap");
    }

    // Both LPs withdraw all. Fees stay in the pool reserves; prorata redemption
    // means each LP gets their share. We assert: payer_lp and lp2_lp balances
    // post-withdraw are zero, and base+quote received are equal across them
    // (they minted equal LP).
    let payer_lp_supply = token_balance(&mut ctx, &fix.payer_lp).await;
    let lp2_lp_supply = token_balance(&mut ctx, &lp2_lp).await;
    assert_eq!(payer_lp_supply, lp2_lp_supply, "both LPs minted equal LP");

    let payer_base_pre = token_balance(&mut ctx, &fix.payer_base).await;
    let payer_quote_pre = token_balance(&mut ctx, &fix.payer_quote).await;
    let lp2_base_pre = token_balance(&mut ctx, &lp2_base).await;
    let lp2_quote_pre = token_balance(&mut ctx, &lp2_quote).await;

    withdraw_ix(
        &mut ctx,
        &fix.payer,
        &pool_accts,
        &fix.payer_base,
        &fix.payer_quote,
        &fix.payer_lp,
        payer_lp_supply,
        1,
        1,
    )
    .await
    .expect("payer withdraw");
    withdraw_ix(
        &mut ctx,
        &lp2,
        &pool_accts,
        &lp2_base,
        &lp2_quote,
        &lp2_lp,
        lp2_lp_supply,
        1,
        1,
    )
    .await
    .expect("lp2 withdraw");

    let payer_base_delta = token_balance(&mut ctx, &fix.payer_base).await - payer_base_pre;
    let payer_quote_delta = token_balance(&mut ctx, &fix.payer_quote).await - payer_quote_pre;
    let lp2_base_delta = token_balance(&mut ctx, &lp2_base).await - lp2_base_pre;
    let lp2_quote_delta = token_balance(&mut ctx, &lp2_quote).await - lp2_quote_pre;

    // Within 1 atom (prorata rounding). Equal supply ⇒ equal-or-1-off receipts.
    assert!(
        (payer_base_delta as i128 - lp2_base_delta as i128).abs() <= 1,
        "base deltas should match within 1 atom: {} vs {}",
        payer_base_delta,
        lp2_base_delta
    );
    assert!(
        (payer_quote_delta as i128 - lp2_quote_delta as i128).abs() <= 1,
        "quote deltas should match within 1 atom: {} vs {}",
        payer_quote_delta,
        lp2_quote_delta
    );
}
