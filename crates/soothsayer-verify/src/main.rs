use clap::{Parser, Subcommand};

use soothsayer_verify::{artefact, commitment, coverage, receipt};

/// Default to the public archive so a third party needs zero setup;
/// pass --archive for a local checkout.
const DEFAULT_ARCHIVE: &str =
    "https://raw.githubusercontent.com/ACNoonan/soothsayer/main/data/band_archive/bands_v1.csv";
const DEFAULT_COMMITMENTS: &str =
    "https://raw.githubusercontent.com/ACNoonan/soothsayer/main/data/band_archive/commitments_v1.csv";

#[derive(Parser)]
#[command(
    name = "soothsayer-verify",
    version,
    about = "Independent audit of Soothsayer's published band coverage claims",
    long_about = "Fetches the public band archive (claims only), fetches realised \
                  opens independently from Yahoo, and recomputes the coverage \
                  statistics. Exit code 0 = claims consistent, 1 = a claim is \
                  rejected / an invariant fails, 2 = data or network error."
)]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Recompute coverage (Kupiec + Christoffersen) of archived bands
    /// against independently fetched Monday opens.
    Coverage {
        /// Band archive: local CSV path or http(s) URL.
        #[arg(long, default_value = DEFAULT_ARCHIVE)]
        archive: String,
        /// Restrict to one target coverage level (e.g. 0.95).
        #[arg(long)]
        tau: Option<f64>,
        /// Restrict to one underlying symbol (e.g. SPY).
        #[arg(long)]
        symbol: Option<String>,
        /// Restrict to weekends on/after this date (YYYY-MM-DD).
        #[arg(long)]
        since: Option<String>,
        /// Emit machine-readable JSON instead of the human report.
        #[arg(long)]
        json: bool,
    },
    /// Audit the pre-open publication chain: every published_pre_open
    /// band must reuse its Friday-close committed width verbatim.
    Commitment {
        /// Commitments CSV: local path or http(s) URL.
        #[arg(long, default_value = DEFAULT_COMMITMENTS)]
        commitments: String,
        /// Band archive: local path or http(s) URL.
        #[arg(long, default_value = DEFAULT_ARCHIVE)]
        archive: String,
        #[arg(long)]
        json: bool,
    },
    /// Decode a live on-chain PriceUpdate account and check its invariants.
    Receipt {
        /// Account pubkey (base58) of the PriceUpdate PDA.
        #[arg(long)]
        account: String,
        /// RPC endpoint: "devnet", "mainnet", or a full URL.
        #[arg(long, default_value = "devnet")]
        url: String,
        #[arg(long)]
        json: bool,
    },
    /// Recompute a frozen artefact's SHA-256 and cross-check the archive.
    Artefact {
        /// Path to the frozen artefact JSON sidecar.
        #[arg(long)]
        file: String,
        /// Expected SHA-256 (e.g. from a report or archive row).
        #[arg(long)]
        expect_sha: Option<String>,
        /// Band archive to cross-check (path or URL).
        #[arg(long)]
        archive: Option<String>,
        #[arg(long)]
        json: bool,
    },
}

fn main() {
    let cli = Cli::parse();
    let code = match cli.cmd {
        Cmd::Coverage {
            archive,
            tau,
            symbol,
            since,
            json,
        } => coverage::run(&coverage::Args {
            archive,
            tau,
            symbol,
            since,
            json,
        }),
        Cmd::Commitment {
            commitments,
            archive,
            json,
        } => commitment::run(&commitments, &archive, json),
        Cmd::Receipt { account, url, json } => receipt::run(&account, &url, json),
        Cmd::Artefact {
            file,
            expect_sha,
            archive,
            json,
        } => artefact::run(&file, expect_sha.as_deref(), archive.as_deref(), json),
    };
    std::process::exit(code);
}
