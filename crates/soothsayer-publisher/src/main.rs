//! Soothsayer publisher CLI (M5 reference + M6 LWC deployed).
//!
//! Usage:
//!
//!     soothsayer fair-value --symbol SPY --as-of 2026-04-17 --target 0.85
//!     soothsayer --forecaster mondrian fair-value --symbol SPY --as-of 2026-04-17 --target 0.85
//!     soothsayer list-available --symbol SPY
//!
//! Artefact defaults to the deployed M6 LWC parquet:
//!     data/processed/lwc_artefact_v1.parquet
//!
//! For the M5 reference path (`--forecaster mondrian`) the default is
//! `data/processed/mondrian_artefact_v2.parquet`. Override with
//! `--artefact <PATH>`.
//!
//! This binary is the Rust equivalent of the Python `Oracle.fair_value_lwc`
//! (under M6) or `Oracle.fair_value` (under M5) — see `src/soothsayer/oracle.py`.
//! Output JSON should match the Python to within floating-point identity on
//! the same inputs + same artefact.

use chrono::NaiveDate;
use clap::{Parser, Subcommand, ValueEnum};
use std::path::PathBuf;

use soothsayer_oracle::{Forecaster, Oracle};

mod payload;
use payload::{borsh_bytes, from_price_point, PublishPayload};

/// Mirror of `soothsayer_oracle::Forecaster` shaped for clap's ValueEnum.
#[derive(Copy, Clone, Debug, ValueEnum)]
enum CliForecaster {
    /// M5 reference path (per-regime split-conformal on raw residuals).
    Mondrian,
    /// M6 deployed path (locally-weighted Mondrian split-conformal).
    Lwc,
}

impl From<CliForecaster> for Forecaster {
    fn from(f: CliForecaster) -> Self {
        match f {
            CliForecaster::Mondrian => Forecaster::Mondrian,
            CliForecaster::Lwc => Forecaster::Lwc,
        }
    }
}

#[derive(Parser)]
#[command(name = "soothsayer", version, about = "Soothsayer oracle publisher")]
struct Cli {
    /// Path to the per-Friday artefact parquet. Default depends on
    /// `--forecaster`: `lwc_artefact_v1.parquet` for LWC (deployed),
    /// `mondrian_artefact_v2.parquet` for Mondrian (M5 reference).
    #[arg(long, global = true)]
    artefact: Option<PathBuf>,

    /// Serving forecaster. Default = `lwc` (M6, deployed). `mondrian` is
    /// the M5 reference path retained for parity refresh and the on-chain
    /// publish surface that pre-dates the M6 Rust port.
    #[arg(long, global = true, value_enum, default_value_t = CliForecaster::Lwc)]
    forecaster: CliForecaster,

    #[command(subcommand)]
    cmd: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Serve a single fair_value read for a (symbol, as_of) at the requested target coverage.
    FairValue {
        #[arg(long)]
        symbol: String,
        #[arg(long)]
        as_of: NaiveDate,
        #[arg(long, default_value_t = 0.85)]
        target: f64,
    },
    /// List every (symbol, fri_ts, regime) triple available in the artefact.
    ListAvailable {
        #[arg(long)]
        symbol: Option<String>,
        /// Only print the last N rows.
        #[arg(long, default_value_t = 20)]
        tail: usize,
    },
    /// Print summary stats for the loaded artefact (sanity check).
    Info,
    /// Convert a PricePoint into the on-chain `PublishPayload` wire format.
    /// Offline-only — does not submit to a Solana cluster. Output: JSON summary
    /// + hex-encoded borsh bytes ready for an Anchor `publish` instruction.
    PreparePublish {
        #[arg(long)]
        symbol: String,
        #[arg(long)]
        as_of: NaiveDate,
        #[arg(long, default_value_t = 0.85)]
        target: f64,
        /// Emit only the hex bytes (for piping into a signing tool).
        #[arg(long)]
        bytes_only: bool,
    },
}

fn default_artefact(forecaster: Forecaster) -> PathBuf {
    match forecaster {
        Forecaster::Mondrian => PathBuf::from("data/processed/mondrian_artefact_v2.parquet"),
        Forecaster::Lwc => PathBuf::from("data/processed/lwc_artefact_v1.parquet"),
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "soothsayer=info".into()),
        )
        .with_writer(std::io::stderr)
        .init();

    let cli = Cli::parse();
    let forecaster: Forecaster = cli.forecaster.into();
    let artefact_path = cli.artefact.unwrap_or_else(|| default_artefact(forecaster));

    let oracle = Oracle::load_with_forecaster(&artefact_path, forecaster)?;

    match cli.cmd {
        Command::FairValue { symbol, as_of, target } => {
            let pp = oracle.fair_value(&symbol, as_of, target)?;
            println!("{}", serde_json::to_string_pretty(&pp)?);
        }
        Command::ListAvailable { symbol, tail } => {
            let rows = oracle.list_available(symbol.as_deref());
            let start = rows.len().saturating_sub(tail);
            for (sym, fri_ts, regime) in &rows[start..] {
                println!("{sym:<8} {fri_ts}  {regime}");
            }
            eprintln!("({} of {} total rows shown)", rows.len() - start, rows.len());
        }
        Command::Info => {
            let rows = oracle.list_available(None);
            println!("artefact rows (unique symbol×fri_ts): {}", rows.len());
            if let (Some(first), Some(last)) = (rows.first(), rows.last()) {
                println!("  span: {} → {}", first.1, last.1);
            }
        }
        Command::PreparePublish { symbol, as_of, target, bytes_only } => {
            let pp = oracle.fair_value(&symbol, as_of, target)?;
            let payload: PublishPayload = from_price_point(&pp)?;
            let bytes = borsh_bytes(&payload);
            if bytes_only {
                for b in &bytes {
                    print!("{:02x}", b);
                }
                println!();
            } else {
                let out = serde_json::json!({
                    "payload": payload,
                    "bytes_hex": bytes.iter().map(|b| format!("{:02x}", b)).collect::<String>(),
                    "bytes_len": bytes.len(),
                    "source_pricepoint": pp,
                });
                println!("{}", serde_json::to_string_pretty(&out)?);
            }
        }
    }

    Ok(())
}
