//! Soothsayer Lending-track on-chain publisher daemon (M6_REFACTOR Phase A5
//! step 2).
//!
//! Each fire = one batch publish across the 10-symbol Lending universe.
//! Composes two existing pieces:
//!
//!   1. The in-workspace `soothsayer prepare-publish` binary, which computes
//!      the band via `Oracle::fair_value` and emits a JSON envelope containing
//!      the borsh-serialized 67-byte `PublishPayload` as `bytes_hex`.
//!   2. This crate, which prepends the Anchor `global:publish` discriminator,
//!      derives the per-symbol `PriceUpdate` PDA, signs with the hot key, and
//!      submits via `solana_client::RpcClient`.
//!
//! No payload re-encoding — `bytes_hex` is the on-the-wire body verbatim.
//!
//! Cadence is owned by macOS launchd (per the user's global preference for
//! launchd over in-process schedulers). One `publish-batch` invocation =
//! one publish per symbol = one launchd fire. The plist template lives at
//! `ops/launchd/com.soothsayer.lending-publisher.plist`.
//!
//! Standalone manifest, excluded from the workspace, mirrors the band-amm-cli
//! pattern. See its `Cargo.toml` for the rationale.

use anyhow::{anyhow, bail, Context, Result};
use chrono::{Datelike, NaiveDate, Utc, Weekday};
use clap::{Parser, Subcommand};
use serde::Deserialize;
use solana_client::rpc_client::RpcClient;
use solana_sdk::{
    commitment_config::CommitmentConfig,
    instruction::{AccountMeta, Instruction},
    pubkey::Pubkey,
    signature::{read_keypair_file, Keypair, Signature, Signer},
    system_program,
    transaction::Transaction,
};
use std::{path::PathBuf, process::Command};

mod anchor;
use anchor::ix_discriminator;

/// Devnet program ID. Mainnet bumps in soothsayer Phase A8 production-readiness.
const ORACLE_PROGRAM_ID: Pubkey =
    solana_sdk::pubkey!("AgXLLTmUJEVh9EsJnznU1yJaUeE9Ufe7ZotupmDqa7f6");

/// The 10-symbol Lending universe (matches `SYMBOL_CLASS_MAP` in
/// `crates/soothsayer-oracle/src/config.rs`). Order is the canonical
/// publish order — kept stable so log diffs across runs are readable.
const LENDING_UNIVERSE: &[&str] = &[
    "SPY", "QQQ", "AAPL", "GOOGL", "NVDA", "TSLA", "MSTR", "HOOD", "GLD", "TLT",
];

/// Default publisher binary path relative to the repo root. The
/// `soothsayer prepare-publish` invocation produces the borsh wire bytes
/// the publish IX consumes.
const DEFAULT_PUBLISHER_BIN: &str = "target/release/soothsayer";

#[derive(Parser)]
#[command(
    name = "soothsayer-lending-publisher",
    version,
    about = "Lending-track on-chain publisher (M6_REFACTOR Phase A5 step 2)"
)]
struct Cli {
    /// Solana RPC endpoint. Defaults to public devnet.
    #[arg(long, global = true, default_value = "https://api.devnet.solana.com")]
    rpc_url: String,

    /// Path to the operator hot-key keypair (must match `signer_set.root`
    /// on the deployed soothsayer-oracle program).
    #[arg(long, global = true, default_value = "~/.config/solana/id.json")]
    keypair: String,

    /// Path to the in-workspace soothsayer publisher binary that computes
    /// the band and emits borsh wire bytes via `prepare-publish`.
    #[arg(long, global = true, default_value = DEFAULT_PUBLISHER_BIN)]
    publisher_bin: PathBuf,

    /// Repo root (used to resolve `--publisher-bin` when relative).
    #[arg(long, global = true)]
    repo_root: Option<PathBuf>,

    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Publish a single symbol. Useful for ad-hoc re-publish or smoke tests.
    Publish {
        #[arg(long)]
        symbol: String,
        /// Friday close anchor date (YYYY-MM-DD). Defaults to the most
        /// recent Friday relative to today's UTC date.
        #[arg(long)]
        as_of: Option<NaiveDate>,
        /// Target coverage τ. Default 0.95 — the Lending headline anchor.
        #[arg(long, default_value_t = 0.95)]
        target: f64,
        /// Skip the actual on-chain submit. Logs the IX details + payload
        /// hex so a smoke test can verify everything except the network call.
        #[arg(long)]
        dry_run: bool,
    },

    /// Publish the full 10-symbol Lending universe in one fire. This is
    /// the launchd-driven entrypoint.
    PublishBatch {
        /// Friday close anchor date. Default = most-recent-Friday from today.
        #[arg(long)]
        as_of: Option<NaiveDate>,
        /// Target coverage τ. Default 0.95.
        #[arg(long, default_value_t = 0.95)]
        target: f64,
        /// Skip submission. Useful for smoke-testing the whole loop without
        /// burning devnet rent.
        #[arg(long)]
        dry_run: bool,
        /// Stop the batch on the first error. Default behaviour is to log
        /// and continue — a single bad symbol shouldn't drop nine others.
        #[arg(long)]
        fail_fast: bool,
    },
}

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "soothsayer_lending_publisher=info".into()),
        )
        .with_writer(std::io::stderr)
        .init();

    let cli = Cli::parse();
    let rpc = RpcClient::new_with_commitment(cli.rpc_url.clone(), CommitmentConfig::confirmed());
    let publisher_bin = resolve_publisher_bin(&cli.publisher_bin, cli.repo_root.as_deref())?;

    // Keypair is only required for non-dry-run submits. For dry-run, use an
    // ephemeral in-memory keypair so the IX accounts list is well-formed
    // (the IX is built but never sent).
    let load_wallet = || -> Result<Keypair> {
        read_keypair_file(expand_tilde(&cli.keypair))
            .map_err(|e| anyhow!("read keypair {}: {e}", cli.keypair))
    };

    match cli.cmd {
        Cmd::Publish { symbol, as_of, target, dry_run } => {
            let as_of = as_of.unwrap_or_else(most_recent_friday);
            let wallet = if dry_run { Keypair::new() } else { load_wallet()? };
            let result = publish_one(&rpc, &wallet, &publisher_bin, &symbol, as_of, target, dry_run)?;
            tracing::info!(?result, "single-symbol publish done");
        }
        Cmd::PublishBatch { as_of, target, dry_run, fail_fast } => {
            let as_of = as_of.unwrap_or_else(most_recent_friday);
            let wallet = if dry_run { Keypair::new() } else { load_wallet()? };
            let mut ok = 0usize;
            let mut errs: Vec<(String, String)> = Vec::new();
            for symbol in LENDING_UNIVERSE {
                match publish_one(&rpc, &wallet, &publisher_bin, symbol, as_of, target, dry_run) {
                    Ok(r) => {
                        tracing::info!(symbol = %symbol, sig = %r.txid_or_dry_run, "ok");
                        ok += 1;
                    }
                    Err(e) => {
                        tracing::error!(symbol = %symbol, err = %e, "publish failed");
                        errs.push((symbol.to_string(), e.to_string()));
                        if fail_fast {
                            break;
                        }
                    }
                }
            }
            tracing::info!(
                ok, fail = errs.len(),
                "batch done (as_of={as_of}, target={target}, dry_run={dry_run})"
            );
            if !errs.is_empty() {
                for (sym, err) in &errs {
                    eprintln!("FAILED {sym}: {err}");
                }
                bail!("batch had {} failures", errs.len());
            }
        }
    }
    Ok(())
}

#[derive(Debug)]
struct PublishOutcome {
    symbol: String,
    price_update_pda: Pubkey,
    txid_or_dry_run: String,
}

fn publish_one(
    rpc: &RpcClient,
    wallet: &Keypair,
    publisher_bin: &PathBuf,
    symbol: &str,
    as_of: NaiveDate,
    target: f64,
    dry_run: bool,
) -> Result<PublishOutcome> {
    let envelope = run_prepare_publish(publisher_bin, symbol, as_of, target)?;
    let payload_bytes = hex::decode(&envelope.bytes_hex)
        .with_context(|| format!("decode bytes_hex for {symbol}"))?;
    if envelope.bytes_len != payload_bytes.len() {
        bail!(
            "bytes_len mismatch for {symbol}: declared {}, decoded {}",
            envelope.bytes_len,
            payload_bytes.len()
        );
    }
    if envelope.payload.profile_code != 1 {
        bail!(
            "expected profile_code = 1 (lending) from prepare-publish, got {}",
            envelope.payload.profile_code
        );
    }

    let symbol_padded = pad_symbol(symbol);
    let (price_update_pda, _) =
        Pubkey::find_program_address(&[b"price", symbol_padded.as_ref()], &ORACLE_PROGRAM_ID);
    let (config_pda, _) = Pubkey::find_program_address(&[b"config"], &ORACLE_PROGRAM_ID);
    let (signer_set_pda, _) =
        Pubkey::find_program_address(&[b"signer_set"], &ORACLE_PROGRAM_ID);

    // IX accounts mirror the `Publish<'info>` struct in
    // programs/soothsayer-oracle-program/src/lib.rs:
    //   signer (mut, Signer), config (RO), signer_set (RO), price_update (mut, init_if_needed),
    //   system_program (RO).
    let accounts = vec![
        AccountMeta::new(wallet.pubkey(), true),
        AccountMeta::new_readonly(config_pda, false),
        AccountMeta::new_readonly(signer_set_pda, false),
        AccountMeta::new(price_update_pda, false),
        AccountMeta::new_readonly(system_program::ID, false),
    ];
    let mut ix_data = Vec::with_capacity(8 + payload_bytes.len());
    ix_data.extend_from_slice(&ix_discriminator("publish"));
    ix_data.extend_from_slice(&payload_bytes);

    let ix = Instruction {
        program_id: ORACLE_PROGRAM_ID,
        accounts,
        data: ix_data,
    };

    if dry_run {
        tracing::info!(
            symbol,
            price_update_pda = %price_update_pda,
            payload_bytes = envelope.bytes_len,
            point = envelope.source_pricepoint.point,
            lower = envelope.source_pricepoint.lower,
            upper = envelope.source_pricepoint.upper,
            "DRY-RUN — not submitting"
        );
        return Ok(PublishOutcome {
            symbol: symbol.to_string(),
            price_update_pda,
            txid_or_dry_run: format!("dry-run({})", envelope.source_pricepoint.profile),
        });
    }

    let sig = send_and_confirm(rpc, wallet, &[ix], symbol)?;
    Ok(PublishOutcome {
        symbol: symbol.to_string(),
        price_update_pda,
        txid_or_dry_run: sig.to_string(),
    })
}

fn send_and_confirm(
    rpc: &RpcClient,
    payer: &Keypair,
    ixs: &[Instruction],
    label: &str,
) -> Result<Signature> {
    let blockhash = rpc.get_latest_blockhash().context("get blockhash")?;
    let tx = Transaction::new_signed_with_payer(
        ixs,
        Some(&payer.pubkey()),
        &[payer],
        blockhash,
    );
    let sig = rpc
        .send_and_confirm_transaction(&tx)
        .with_context(|| format!("send {label}"))?;
    rpc.confirm_transaction_with_commitment(&sig, CommitmentConfig::confirmed())
        .with_context(|| format!("confirm {label}"))?;
    Ok(sig)
}

// ── prepare-publish JSON contract ────────────────────────────────────────────

#[derive(Deserialize, Debug)]
struct PrepareEnvelope {
    payload: PreparePayload,
    bytes_hex: String,
    bytes_len: usize,
    source_pricepoint: SourcePricePoint,
}

#[derive(Deserialize, Debug)]
struct PreparePayload {
    profile_code: u8,
    // The other fields exist but the IX needs only bytes_hex; we just
    // read profile_code to assert the publisher CLI is in lending mode.
}

#[derive(Deserialize, Debug)]
struct SourcePricePoint {
    point: f64,
    lower: f64,
    upper: f64,
    profile: String,
}

fn run_prepare_publish(
    bin: &PathBuf,
    symbol: &str,
    as_of: NaiveDate,
    target: f64,
) -> Result<PrepareEnvelope> {
    let out = Command::new(bin)
        .args([
            "--profile",
            "lending",
            "prepare-publish",
            "--symbol",
            symbol,
            "--as-of",
            &as_of.to_string(),
            "--target",
            &target.to_string(),
        ])
        .output()
        .with_context(|| format!("invoke {} prepare-publish", bin.display()))?;
    if !out.status.success() {
        let stderr = String::from_utf8_lossy(&out.stderr);
        bail!("prepare-publish failed for {symbol}: {stderr}");
    }
    serde_json::from_slice(&out.stdout)
        .with_context(|| format!("parse prepare-publish JSON for {symbol}"))
}

// ── small utilities ──────────────────────────────────────────────────────────

fn pad_symbol(s: &str) -> [u8; 16] {
    let mut out = [0u8; 16];
    let bytes = s.as_bytes();
    let n = bytes.len().min(16);
    out[..n].copy_from_slice(&bytes[..n]);
    out
}

fn most_recent_friday() -> NaiveDate {
    let today = Utc::now().date_naive();
    let weekday = today.weekday();
    let back = match weekday {
        Weekday::Fri => 0,
        Weekday::Sat => 1,
        Weekday::Sun => 2,
        Weekday::Mon => 3,
        Weekday::Tue => 4,
        Weekday::Wed => 5,
        Weekday::Thu => 6,
    };
    today - chrono::Duration::days(back)
}

fn expand_tilde(p: &str) -> PathBuf {
    if let Some(rest) = p.strip_prefix("~/") {
        if let Ok(home) = std::env::var("HOME") {
            return PathBuf::from(home).join(rest);
        }
    }
    PathBuf::from(p)
}

fn resolve_publisher_bin(
    bin: &PathBuf,
    repo_root: Option<&std::path::Path>,
) -> Result<PathBuf> {
    if bin.is_absolute() {
        return Ok(bin.clone());
    }
    let root = repo_root
        .map(|p| p.to_path_buf())
        .or_else(|| std::env::current_dir().ok())
        .ok_or_else(|| anyhow!("can't resolve repo_root"))?;
    let resolved = root.join(bin);
    if !resolved.exists() {
        // Best-effort: tell the operator to build the in-workspace publisher first.
        tracing::warn!(
            path = %resolved.display(),
            "publisher binary not found; build with `cargo build --release -p soothsayer-publisher`"
        );
    }
    Ok(resolved)
}

