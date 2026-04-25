//! Soothsayer publisher CLI.
//!
//! Usage:
//!
//!     soothsayer fair-value --symbol SPY --as-of 2026-04-17 --target 0.85
//!     soothsayer list-available --symbol SPY
//!
//! Artifacts default to the repo-root paths:
//!     data/processed/v1b_bounds.parquet
//!     reports/tables/v1b_calibration_surface.csv
//!     reports/tables/v1b_calibration_surface_pooled.csv
//!
//! This binary is the Phase 1 Week 1 deliverable: the Rust equivalent of the
//! Python `Oracle.fair_value` (ref: `src/soothsayer/oracle.py`). Output JSON
//! should match the Python to within floating-point identity on the same
//! inputs + same artifacts.

use chrono::NaiveDate;
use clap::{Parser, Subcommand};
use std::path::PathBuf;

use soothsayer_oracle::Oracle;

mod payload;
use payload::{borsh_bytes, from_price_point, PublishPayload};

#[derive(Parser)]
#[command(name = "soothsayer", version, about = "Soothsayer oracle publisher")]
struct Cli {
    /// Path to the bounds parquet (default: data/processed/v1b_bounds.parquet).
    #[arg(long, global = true)]
    bounds: Option<PathBuf>,

    /// Path to the per-symbol calibration surface CSV (default: reports/tables/v1b_calibration_surface.csv).
    #[arg(long, global = true)]
    surface: Option<PathBuf>,

    /// Path to the pooled calibration surface CSV (default: reports/tables/v1b_calibration_surface_pooled.csv).
    #[arg(long, global = true)]
    pooled: Option<PathBuf>,

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
        /// Override the hybrid regime-selected forecaster (A/B diagnostic).
        #[arg(long)]
        forecaster: Option<String>,
        /// Override the empirical calibration buffer (0.0 disables).
        #[arg(long)]
        buffer: Option<f64>,
    },
    /// List every (symbol, fri_ts, regime) triple available in the bounds table.
    ListAvailable {
        #[arg(long)]
        symbol: Option<String>,
        /// Only print the last N rows.
        #[arg(long, default_value_t = 20)]
        tail: usize,
    },
    /// Print summary stats for the loaded artifacts (sanity check).
    Info,
    /// Convert a PricePoint into the on-chain `PublishPayload` wire format.
    /// Offline-only — does not submit to a Solana cluster. Output: JSON summary
    /// + hex-encoded borsh bytes ready for an Anchor `publish` instruction.
    ///
    /// The full `publish` subcommand (which signs and submits via RPC) lands in
    /// Week 2.5 once the Solana toolchain is installed locally. See
    /// `scripts/deploy_devnet.sh` for the full deploy + publish flow.
    PreparePublish {
        #[arg(long)]
        symbol: String,
        #[arg(long)]
        as_of: NaiveDate,
        #[arg(long, default_value_t = 0.85)]
        target: f64,
        #[arg(long)]
        forecaster: Option<String>,
        #[arg(long)]
        buffer: Option<f64>,
        /// Emit only the hex bytes (for piping into a signing tool).
        #[arg(long)]
        bytes_only: bool,
    },
}

fn default_paths() -> (PathBuf, PathBuf, PathBuf) {
    (
        PathBuf::from("data/processed/v1b_bounds.parquet"),
        PathBuf::from("reports/tables/v1b_calibration_surface.csv"),
        PathBuf::from("reports/tables/v1b_calibration_surface_pooled.csv"),
    )
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
    let (def_bounds, def_surface, def_pooled) = default_paths();
    let bounds_path = cli.bounds.unwrap_or(def_bounds);
    let surface_path = cli.surface.unwrap_or(def_surface);
    let pooled_path = cli.pooled.unwrap_or(def_pooled);

    let oracle = Oracle::load(&bounds_path, &surface_path, &pooled_path)?;

    match cli.cmd {
        Command::FairValue { symbol, as_of, target, forecaster, buffer } => {
            let pp = oracle.fair_value(
                &symbol,
                as_of,
                target,
                forecaster.as_deref(),
                buffer,
            )?;
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
            println!("bounds rows (unique symbol×fri_ts): {}", rows.len());
            if let (Some(first), Some(last)) = (rows.first(), rows.last()) {
                println!("  span: {} → {}", first.1, last.1);
            }
        }
        Command::PreparePublish {
            symbol,
            as_of,
            target,
            forecaster,
            buffer,
            bytes_only,
        } => {
            let pp = oracle.fair_value(
                &symbol,
                as_of,
                target,
                forecaster.as_deref(),
                buffer,
            )?;
            let payload: PublishPayload = from_price_point(&pp)?;
            let bytes = borsh_bytes(&payload);
            if bytes_only {
                // One line of hex — suitable for `xxd -r -p` or piping to a signer.
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
