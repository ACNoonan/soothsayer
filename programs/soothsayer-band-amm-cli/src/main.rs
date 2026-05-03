//! BandAMM devnet seed + demo CLI.
//!
//! Hackathon Day-4 deliverable. Drives the full devnet bring-up:
//! republish the SPY oracle band, first-publish the QQQ band, create test
//! mints (SPYx_test, QQQx_test, USDC_test), initialize two pools, deposit
//! liquidity, and run a demo swap whose receipt event reconciles against the
//! on-chain band PDA.
//!
//! Anchor instructions are wire-encoded by hand (8-byte discriminator =
//! `sha256("global:<snake_case_ix_name>")[..8]` + borsh-serialized args), so
//! this crate has no program-crate path dependency.

mod anchor;
mod artefact;
mod oracle_ix;
mod pool_ix;

use std::path::PathBuf;

use anyhow::{anyhow, bail, Context, Result};
use clap::{Parser, Subcommand};
use solana_client::rpc_client::RpcClient;
use solana_sdk::{
    commitment_config::CommitmentConfig,
    instruction::Instruction,
    program_pack::Pack,
    pubkey::Pubkey,
    signature::Signature,
    signer::{keypair::{read_keypair_file, Keypair}, Signer},
    system_instruction,
    transaction::Transaction,
};
use spl_associated_token_account::{
    get_associated_token_address, instruction as ata_ix,
};

use crate::artefact::{Artefact, PoolRecord};

// ─────────────────────────────────────── consts ──────────────────────────────

/// BandAMM program ID (matches `declare_id!` in soothsayer-band-amm-program).
const BAND_AMM_PROGRAM_ID: Pubkey =
    solana_sdk::pubkey!("7vjG4nuVcpotSBDHPQeonrzuvxbwgDddKzibeLASaqw8");

/// Soothsayer oracle program ID (matches `declare_id!` in
/// soothsayer-oracle-program).
const ORACLE_PROGRAM_ID: Pubkey =
    solana_sdk::pubkey!("AgXLLTmUJEVh9EsJnznU1yJaUeE9Ufe7ZotupmDqa7f6");

const SPYX_DECIMALS: u8 = 8;
const QQQX_DECIMALS: u8 = 8;
const USDC_DECIMALS: u8 = 6;

const BAND_EXPONENT: i8 = -8;
const PRICE_UPDATE_VERSION: u8 = 1;

const DEFAULT_HELIUS_DEVNET: &str = "https://api.devnet.solana.com";

// ─────────────────────────────────────── CLI ─────────────────────────────────

#[derive(Parser)]
#[command(
    name = "soothsayer-band-amm",
    about = "Devnet seed + demo CLI for the Soothsayer BandAMM",
    version
)]
struct Cli {
    /// Solana RPC URL (devnet). Defaults to `RPC_URL` env, then public devnet.
    /// Pass a Helius / Triton URL with API key for higher rate limits.
    #[arg(long, global = true)]
    rpc_url: Option<String>,

    /// Path to the wallet keypair (must match the on-chain oracle program's
    /// configured `signer_set.root` for `republish-band` to succeed).
    #[arg(long, global = true, default_value = "~/.config/solana/id.json")]
    wallet: String,

    /// Path to the JSON artefact ledger written and updated by every
    /// subcommand. Defaults to `reports/paper4_oracle_conditioned_amm/devnet_artefacts.json`.
    #[arg(long, global = true)]
    artefact: Option<PathBuf>,

    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Create the three test SPL mints (SPYx_test 8 dec, QQQx_test 8 dec,
    /// USDC_test 6 dec) with the wallet as mint authority. Writes pubkeys to
    /// the artefact ledger. Idempotent: reuses any mint already in the ledger.
    SeedMints,

    /// Mint test tokens to the wallet's ATAs. Defaults: 1000 SPYx, 1000 QQQx,
    /// 1_000_000 USDC.
    MintToWallet {
        #[arg(long, default_value_t = 1_000)]
        spyx: u64,
        #[arg(long, default_value_t = 1_000)]
        qqqx: u64,
        #[arg(long, default_value_t = 1_000_000)]
        usdc: u64,
    },

    /// Republish (or first-publish) a band via the oracle program. Hand-rolled
    /// for the hackathon: the band values come from `--point` + `--lower` +
    /// `--upper` (in dollars; converted to fixed-point at exp=-8).
    PublishBand {
        #[arg(long)]
        symbol: String,
        #[arg(long)]
        point: f64,
        #[arg(long)]
        lower: f64,
        #[arg(long)]
        upper: f64,
        #[arg(long, default_value_t = 9500)]
        target_coverage_bps: u16,
        #[arg(long, default_value_t = 9750)]
        claimed_served_bps: u16,
        #[arg(long, default_value_t = 250)]
        buffer_applied_bps: u16,
        #[arg(long, default_value_t = 0)]
        regime_code: u8,
        #[arg(long, default_value_t = 0)]
        forecaster_code: u8,
    },

    /// Initialize a BandAMM pool. The pool PDA is derived from
    /// `[b"band_amm_pool", base_mint, quote_mint]`. The `--symbol` flag picks
    /// which oracle PriceUpdate PDA the pool reads (binding is locked at init).
    InitPool {
        #[arg(long)]
        base_mint: Pubkey,
        #[arg(long)]
        quote_mint: Pubkey,
        /// 16-byte symbol used to derive the oracle `PriceUpdate` PDA seed:
        /// `[b"price", symbol_padded_to_16]`.
        #[arg(long)]
        symbol: String,
        /// In-band fee in bps (default = program default = 5).
        #[arg(long)]
        fee_bps_in: Option<u16>,
        /// Outside-band staleness limit in seconds (default = program default = 60).
        #[arg(long)]
        max_band_staleness_secs: Option<u32>,
        /// Friendly label written to the artefact ledger ("SPYx-USDC").
        #[arg(long)]
        label: String,
    },

    /// Deposit liquidity into a pool. `--base` and `--quote` are in human
    /// units (8 dec for SPYx/QQQx, 6 dec for USDC) — the CLI scales to atoms.
    Deposit {
        #[arg(long)]
        label: String,
        #[arg(long)]
        base: f64,
        #[arg(long)]
        quote: f64,
        #[arg(long, default_value_t = 0.0)]
        min_lp_out: f64,
    },

    /// Execute a swap. `--side base` means base-in/quote-out.
    Swap {
        #[arg(long)]
        label: String,
        #[arg(long)]
        amount_in: f64,
        #[arg(long, default_value_t = 0.0)]
        min_amount_out: f64,
        /// "base" = swap base in for quote out; "quote" = quote in for base out.
        #[arg(long, default_value = "base")]
        side: String,
    },

    /// One-shot pipeline: SeedMints → MintToWallet → PublishBand (SPY+QQQ) →
    /// InitPool (×2) → Deposit (×2) → Swap (×2). Used for the Day-4 capture.
    SeedAll {
        /// Skip mint creation if the artefact ledger already records them.
        #[arg(long, default_value_t = true)]
        idempotent: bool,
    },
}

// ─────────────────────────────────── main ────────────────────────────────────

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "soothsayer_band_amm=info".into()),
        )
        .with_writer(std::io::stderr)
        .init();

    let cli = Cli::parse();

    let rpc_url = cli
        .rpc_url
        .clone()
        .or_else(|| std::env::var("RPC_URL").ok())
        .unwrap_or_else(|| DEFAULT_HELIUS_DEVNET.to_string());
    let wallet_path = expand_tilde(&cli.wallet);
    let wallet = read_keypair_file(&wallet_path)
        .map_err(|e| anyhow!("read wallet keypair {}: {e}", wallet_path.display()))?;
    let artefact_path = cli
        .artefact
        .clone()
        .unwrap_or_else(default_artefact_path);

    tracing::info!(rpc = %rpc_url, wallet = %wallet.pubkey(), "wallet ready");

    let rpc = RpcClient::new_with_commitment(rpc_url.clone(), CommitmentConfig::confirmed());
    let mut state = Artefact::load_or_init(&artefact_path)?;
    state.rpc_url = Some(rpc_url);
    state.wallet = Some(wallet.pubkey().to_string());
    state.band_amm_program = Some(BAND_AMM_PROGRAM_ID.to_string());
    state.oracle_program = Some(ORACLE_PROGRAM_ID.to_string());

    match cli.cmd {
        Cmd::SeedMints => {
            run_seed_mints(&rpc, &wallet, &mut state)?;
        }
        Cmd::MintToWallet { spyx, qqqx, usdc } => {
            run_mint_to_wallet(&rpc, &wallet, &state, spyx, qqqx, usdc)?;
        }
        Cmd::PublishBand {
            symbol,
            point,
            lower,
            upper,
            target_coverage_bps,
            claimed_served_bps,
            buffer_applied_bps,
            regime_code,
            forecaster_code,
        } => {
            run_publish_band(
                &rpc,
                &wallet,
                &mut state,
                &symbol,
                point,
                lower,
                upper,
                target_coverage_bps,
                claimed_served_bps,
                buffer_applied_bps,
                regime_code,
                forecaster_code,
            )?;
        }
        Cmd::InitPool {
            base_mint,
            quote_mint,
            symbol,
            fee_bps_in,
            max_band_staleness_secs,
            label,
        } => {
            run_init_pool(
                &rpc,
                &wallet,
                &mut state,
                base_mint,
                quote_mint,
                &symbol,
                fee_bps_in,
                max_band_staleness_secs,
                &label,
            )?;
        }
        Cmd::Deposit {
            label,
            base,
            quote,
            min_lp_out,
        } => {
            run_deposit(&rpc, &wallet, &mut state, &label, base, quote, min_lp_out)?;
        }
        Cmd::Swap {
            label,
            amount_in,
            min_amount_out,
            side,
        } => {
            run_swap(
                &rpc,
                &wallet,
                &mut state,
                &label,
                amount_in,
                min_amount_out,
                &side,
            )?;
        }
        Cmd::SeedAll { idempotent } => {
            run_seed_all(&rpc, &wallet, &mut state, idempotent)?;
        }
    }

    state.save(&artefact_path)?;
    Ok(())
}

// ─────────────────────────────────── helpers ─────────────────────────────────

fn expand_tilde(p: &str) -> PathBuf {
    if let Some(stripped) = p.strip_prefix("~/") {
        if let Ok(home) = std::env::var("HOME") {
            return PathBuf::from(home).join(stripped);
        }
    }
    PathBuf::from(p)
}

fn default_artefact_path() -> PathBuf {
    PathBuf::from("reports/paper4_oracle_conditioned_amm/devnet_artefacts.json")
}

fn pad_symbol(s: &str) -> [u8; 16] {
    let mut out = [0u8; 16];
    let bytes = s.as_bytes();
    let n = bytes.len().min(16);
    out[..n].copy_from_slice(&bytes[..n]);
    out
}

fn fp_dollars_to_atoms(price: f64, exp: i8) -> Result<i64> {
    let scale = 10f64.powi(-exp as i32);
    let v = (price * scale).round();
    if !v.is_finite() {
        bail!("non-finite fixed-point conversion for {price}");
    }
    if v.abs() > i64::MAX as f64 {
        bail!("fixed-point value {price}*{scale} exceeds i64::MAX");
    }
    Ok(v as i64)
}

fn human_to_atoms(human: f64, decimals: u8) -> u64 {
    (human * 10f64.powi(decimals as i32)).round() as u64
}

fn confirm_and_log(rpc: &RpcClient, sig: &Signature, label: &str) -> Result<()> {
    rpc.confirm_transaction_with_commitment(sig, CommitmentConfig::confirmed())
        .with_context(|| format!("confirm {label}"))?;
    let url = format!(
        "https://explorer.solana.com/tx/{sig}?cluster=devnet"
    );
    tracing::info!(%sig, %url, "{label} confirmed");
    Ok(())
}

fn send_and_confirm(
    rpc: &RpcClient,
    payer: &Keypair,
    signers: &[&Keypair],
    ixs: &[Instruction],
    label: &str,
) -> Result<Signature> {
    let blockhash = rpc.get_latest_blockhash().context("get blockhash")?;
    let mut all_signers: Vec<&Keypair> = vec![payer];
    for s in signers {
        if s.pubkey() != payer.pubkey() {
            all_signers.push(s);
        }
    }
    let tx = Transaction::new_signed_with_payer(
        ixs,
        Some(&payer.pubkey()),
        &all_signers,
        blockhash,
    );
    let sig = rpc
        .send_and_confirm_transaction(&tx)
        .with_context(|| format!("send {label}"))?;
    confirm_and_log(rpc, &sig, label)?;
    Ok(sig)
}

// ─────────────────────────────────── runners ─────────────────────────────────

fn run_seed_mints(
    rpc: &RpcClient,
    wallet: &Keypair,
    state: &mut Artefact,
) -> Result<()> {
    let entries = [
        ("spyx_test", SPYX_DECIMALS, "SPYx_test"),
        ("qqqx_test", QQQX_DECIMALS, "QQQx_test"),
        ("usdc_test", USDC_DECIMALS, "USDC_test"),
    ];
    for (key, decimals, label) in entries {
        if state.mint_pubkey(key).is_some() {
            tracing::info!(key, "mint already in artefact ledger; skipping");
            continue;
        }
        let mint = Keypair::new();
        let rent = rpc
            .get_minimum_balance_for_rent_exemption(spl_token::state::Mint::LEN)
            .context("rent for mint")?;
        let create = system_instruction::create_account(
            &wallet.pubkey(),
            &mint.pubkey(),
            rent,
            spl_token::state::Mint::LEN as u64,
            &spl_token::ID,
        );
        let init = spl_token::instruction::initialize_mint(
            &spl_token::ID,
            &mint.pubkey(),
            &wallet.pubkey(),
            None,
            decimals,
        )
        .context("initialize_mint ix")?;
        send_and_confirm(
            rpc,
            wallet,
            &[&mint],
            &[create, init],
            &format!("create_mint {label}"),
        )?;
        state.set_mint(key, label, &mint.pubkey(), decimals);
        tracing::info!(key, mint = %mint.pubkey(), "minted");
    }
    Ok(())
}

fn run_mint_to_wallet(
    rpc: &RpcClient,
    wallet: &Keypair,
    state: &Artefact,
    spyx: u64,
    qqqx: u64,
    usdc: u64,
) -> Result<()> {
    let entries = [("spyx_test", spyx), ("qqqx_test", qqqx), ("usdc_test", usdc)];
    for (key, human_amount) in entries {
        if human_amount == 0 {
            continue;
        }
        let mint_record = state
            .mint(key)
            .with_context(|| format!("mint {key} not in ledger; run seed-mints first"))?;
        let mint_pk: Pubkey = mint_record.pubkey.parse().context("parse mint pubkey")?;
        let ata = get_associated_token_address(&wallet.pubkey(), &mint_pk);
        let mut ixs: Vec<Instruction> = vec![];
        if rpc
            .get_account(&ata)
            .map(|a| a.lamports > 0)
            .unwrap_or(false)
        {
            // ATA exists.
        } else {
            ixs.push(ata_ix::create_associated_token_account(
                &wallet.pubkey(),
                &wallet.pubkey(),
                &mint_pk,
                &spl_token::ID,
            ));
        }
        let amount = human_to_atoms(human_amount as f64, mint_record.decimals);
        ixs.push(
            spl_token::instruction::mint_to(
                &spl_token::ID,
                &mint_pk,
                &ata,
                &wallet.pubkey(),
                &[],
                amount,
            )
            .context("mint_to ix")?,
        );
        send_and_confirm(rpc, wallet, &[], &ixs, &format!("mint_to {key}"))?;
        tracing::info!(key, %ata, atoms = amount, "minted to wallet ATA");
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn run_publish_band(
    rpc: &RpcClient,
    wallet: &Keypair,
    state: &mut Artefact,
    symbol: &str,
    point: f64,
    lower: f64,
    upper: f64,
    target_coverage_bps: u16,
    claimed_served_bps: u16,
    buffer_applied_bps: u16,
    regime_code: u8,
    forecaster_code: u8,
) -> Result<()> {
    let symbol_padded = pad_symbol(symbol);
    let payload = oracle_ix::PublishPayload {
        version: PRICE_UPDATE_VERSION,
        regime_code,
        forecaster_code,
        exponent: BAND_EXPONENT,
        target_coverage_bps,
        claimed_served_bps,
        buffer_applied_bps,
        symbol: symbol_padded,
        point: fp_dollars_to_atoms(point, BAND_EXPONENT)?,
        lower: fp_dollars_to_atoms(lower, BAND_EXPONENT)?,
        upper: fp_dollars_to_atoms(upper, BAND_EXPONENT)?,
        fri_close: fp_dollars_to_atoms(point, BAND_EXPONENT)?,
        fri_ts: chrono::Utc::now().timestamp() - 86_400,
    };
    let (price_pda, _) = oracle_ix::find_price_update_pda(&symbol_padded);
    let ix = oracle_ix::publish_ix(&wallet.pubkey(), &price_pda, &payload);
    send_and_confirm(rpc, wallet, &[], &[ix], &format!("publish {symbol}"))?;

    state.set_band(
        symbol,
        oracle_ix::BandRecord {
            symbol: symbol.to_string(),
            price_update: price_pda.to_string(),
            point,
            lower,
            upper,
            target_coverage_bps,
            claimed_served_bps,
            regime_code,
        },
    );
    tracing::info!(symbol, price_update = %price_pda, "band published");
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn run_init_pool(
    rpc: &RpcClient,
    wallet: &Keypair,
    state: &mut Artefact,
    base_mint: Pubkey,
    quote_mint: Pubkey,
    symbol: &str,
    fee_bps_in: Option<u16>,
    max_band_staleness_secs: Option<u32>,
    label: &str,
) -> Result<()> {
    let symbol_padded = pad_symbol(symbol);
    let (price_pda, _) = oracle_ix::find_price_update_pda(&symbol_padded);
    let (pool_pda, _) = pool_ix::find_pool_pda(&base_mint, &quote_mint);
    let (lp_mint, _) = pool_ix::find_lp_mint_pda(&pool_pda);
    let (base_vault, _) = pool_ix::find_vault_pda(&pool_pda, &base_mint);
    let (quote_vault, _) = pool_ix::find_vault_pda(&pool_pda, &quote_mint);

    let ix = pool_ix::initialize_pool_ix(
        &wallet.pubkey(),
        &base_mint,
        &quote_mint,
        &pool_pda,
        &lp_mint,
        &base_vault,
        &quote_vault,
        &price_pda,
        pool_ix::InitializePoolParams {
            authority: wallet.pubkey(),
            fee_bps_in,
            fee_alpha_out_bps: None,
            fee_w_max_bps: None,
            max_band_staleness_secs,
        },
    );
    send_and_confirm(rpc, wallet, &[], &[ix], &format!("init_pool {label}"))?;
    state.upsert_pool(
        label,
        PoolRecord {
            label: label.to_string(),
            symbol: symbol.to_string(),
            base_mint: base_mint.to_string(),
            quote_mint: quote_mint.to_string(),
            pool: pool_pda.to_string(),
            lp_mint: lp_mint.to_string(),
            base_vault: base_vault.to_string(),
            quote_vault: quote_vault.to_string(),
            price_update: price_pda.to_string(),
            deposited: false,
        },
    );
    tracing::info!(label, %pool_pda, "pool initialized");
    Ok(())
}

fn run_deposit(
    rpc: &RpcClient,
    wallet: &Keypair,
    state: &Artefact,
    label: &str,
    base: f64,
    quote: f64,
    min_lp_out: f64,
) -> Result<()> {
    let pool = state
        .pool(label)
        .with_context(|| format!("pool {label} not in ledger; run init-pool first"))?;
    let pool_pk: Pubkey = pool.pool.parse().context("parse pool pubkey")?;
    let lp_mint: Pubkey = pool.lp_mint.parse()?;
    let base_vault: Pubkey = pool.base_vault.parse()?;
    let quote_vault: Pubkey = pool.quote_vault.parse()?;
    let base_mint: Pubkey = pool.base_mint.parse()?;
    let quote_mint: Pubkey = pool.quote_mint.parse()?;

    let user_base = get_associated_token_address(&wallet.pubkey(), &base_mint);
    let user_quote = get_associated_token_address(&wallet.pubkey(), &quote_mint);
    let user_lp = get_associated_token_address(&wallet.pubkey(), &lp_mint);

    let mut ixs: Vec<Instruction> = vec![];
    if rpc.get_account(&user_lp).map(|a| a.lamports > 0).unwrap_or(false) {
        // LP ATA exists.
    } else {
        ixs.push(ata_ix::create_associated_token_account(
            &wallet.pubkey(),
            &wallet.pubkey(),
            &lp_mint,
            &spl_token::ID,
        ));
    }

    let base_decimals = state
        .mint_for_pubkey(&pool.base_mint)
        .map(|m| m.decimals)
        .unwrap_or(SPYX_DECIMALS);
    let quote_decimals = state
        .mint_for_pubkey(&pool.quote_mint)
        .map(|m| m.decimals)
        .unwrap_or(USDC_DECIMALS);

    let amount_base = human_to_atoms(base, base_decimals);
    let amount_quote = human_to_atoms(quote, quote_decimals);
    let min_lp_out = human_to_atoms(min_lp_out, 6); // LP mint decimals = 6

    let ix = pool_ix::deposit_ix(
        &wallet.pubkey(),
        &pool_pk,
        &lp_mint,
        &base_vault,
        &quote_vault,
        &user_base,
        &user_quote,
        &user_lp,
        amount_base,
        amount_quote,
        min_lp_out,
    );
    ixs.push(ix);
    send_and_confirm(rpc, wallet, &[], &ixs, &format!("deposit {label}"))?;
    tracing::info!(label, atoms_base = amount_base, atoms_quote = amount_quote, "deposit confirmed");
    Ok(())
}

fn run_swap(
    rpc: &RpcClient,
    wallet: &Keypair,
    state: &mut Artefact,
    label: &str,
    amount_in: f64,
    min_amount_out: f64,
    side: &str,
) -> Result<()> {
    let pool = state
        .pool(label)
        .with_context(|| format!("pool {label} not in ledger; run init-pool first"))?
        .clone();
    let pool_pk: Pubkey = pool.pool.parse()?;
    let base_vault: Pubkey = pool.base_vault.parse()?;
    let quote_vault: Pubkey = pool.quote_vault.parse()?;
    let base_mint: Pubkey = pool.base_mint.parse()?;
    let quote_mint: Pubkey = pool.quote_mint.parse()?;
    let price_update: Pubkey = pool.price_update.parse()?;

    let user_base = get_associated_token_address(&wallet.pubkey(), &base_mint);
    let user_quote = get_associated_token_address(&wallet.pubkey(), &quote_mint);

    let side_base_in = match side {
        "base" => true,
        "quote" => false,
        _ => bail!("--side must be `base` or `quote`"),
    };

    let base_decimals = state
        .mint_for_pubkey(&pool.base_mint)
        .map(|m| m.decimals)
        .unwrap_or(SPYX_DECIMALS);
    let quote_decimals = state
        .mint_for_pubkey(&pool.quote_mint)
        .map(|m| m.decimals)
        .unwrap_or(USDC_DECIMALS);
    let in_dec = if side_base_in { base_decimals } else { quote_decimals };
    let out_dec = if side_base_in { quote_decimals } else { base_decimals };

    let amount_in = human_to_atoms(amount_in, in_dec);
    let min_amount_out = human_to_atoms(min_amount_out, out_dec);

    let ix = pool_ix::swap_ix(
        &wallet.pubkey(),
        &pool_pk,
        &base_vault,
        &quote_vault,
        &user_base,
        &user_quote,
        &price_update,
        amount_in,
        min_amount_out,
        side_base_in,
    );
    let sig = send_and_confirm(rpc, wallet, &[], &[ix], &format!("swap {label}"))?;
    state.append_swap(label, &sig.to_string(), amount_in, side_base_in);
    Ok(())
}

fn run_seed_all(
    rpc: &RpcClient,
    wallet: &Keypair,
    state: &mut Artefact,
    idempotent: bool,
) -> Result<()> {
    let _ = idempotent; // seed-mints + ata-create are already idempotent
    run_seed_mints(rpc, wallet, state)?;
    run_mint_to_wallet(rpc, wallet, state, 1_000, 1_000, 1_000_000)?;

    // Hand-picked SPY/QQQ bands centered around late-April 2026 reference
    // levels. Day-4 demo only — replace with publisher output in production.
    run_publish_band(
        rpc, wallet, state, "SPY",
        700.00, 689.50, 710.50,
        9500, 9750, 250, 0, 0,
    )?;
    run_publish_band(
        rpc, wallet, state, "QQQ",
        480.00, 472.50, 487.50,
        9500, 9750, 250, 0, 0,
    )?;

    let spyx = state.mint_pubkey("spyx_test").context("spyx mint")?;
    let qqqx = state.mint_pubkey("qqqx_test").context("qqqx mint")?;
    let usdc = state.mint_pubkey("usdc_test").context("usdc mint")?;

    if state.pool("SPYx-USDC").is_none() {
        run_init_pool(rpc, wallet, state, spyx, usdc, "SPY", None, None, "SPYx-USDC")?;
    } else {
        tracing::info!("pool SPYx-USDC already in ledger; skipping init");
    }
    if state.pool("QQQx-USDC").is_none() {
        run_init_pool(rpc, wallet, state, qqqx, usdc, "QQQ", None, None, "QQQx-USDC")?;
    } else {
        tracing::info!("pool QQQx-USDC already in ledger; skipping init");
    }

    // ~10 SPYx and ~7,000 USDC ⇒ implied price 700, matches band point.
    if state.pool("SPYx-USDC").map(|p| p.deposited).unwrap_or(false).not() {
        run_deposit(rpc, wallet, state, "SPYx-USDC", 10.0, 7_000.0, 0.0)?;
        state.mark_deposited("SPYx-USDC", true);
    }
    if state.pool("QQQx-USDC").map(|p| p.deposited).unwrap_or(false).not() {
        run_deposit(rpc, wallet, state, "QQQx-USDC", 10.0, 4_800.0, 0.0)?;
        state.mark_deposited("QQQx-USDC", true);
    }

    // Demo swaps: 0.01 SPYx → USDC, 0.01 QQQx → USDC. In-band by construction
    // (band centered on the deposit ratio).
    run_swap(rpc, wallet, state, "SPYx-USDC", 0.01, 0.0, "base")?;
    run_swap(rpc, wallet, state, "QQQx-USDC", 0.01, 0.0, "base")?;
    Ok(())
}

// `Option<bool>::not()` shim for the deposit guard above.
trait BoolNot {
    fn not(self) -> bool;
}
impl BoolNot for bool {
    fn not(self) -> bool {
        !self
    }
}
