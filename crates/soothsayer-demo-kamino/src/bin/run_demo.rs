//! Kamino-fork demo runner.
//!
//! Reads `data/processed/demo_kamino_scenarios.json` (produced by
//! `scripts/generate_demo_kamino_scenarios.py` from the deployed Oracle),
//! runs each scenario through both the Soothsayer-band evaluator and a
//! legacy flat-band evaluator, and emits:
//!
//! - a stdout summary table,
//! - a markdown comparison at `reports/demo_kamino_comparison.md`,
//! - an HTML fragment at `landing/demo_kamino_fragment.html`.
//!
//! All three contain the same numbers — the Soothsayer bands are real outputs
//! from the deployed methodology; the borrower positions and flat-band
//! comparator are synthetic teaching artifacts.
//!
//! Run:
//!     cargo run --release -p soothsayer-demo-kamino --bin run_demo

use serde::Deserialize;
use soothsayer_consumer::{
    PriceBand, FORECASTER_F0_STALE, FORECASTER_F1_EMP_REGIME, PROFILE_LENDING, REGIME_HIGH_VOL,
    REGIME_LONG_WEEKEND,
    REGIME_NORMAL, REGIME_SHOCK_FLAGGED,
};
use soothsayer_demo_kamino::{
    evaluate, evaluate_with_flat_band, Evaluation, LendingDecision, LendingParams, Position,
};
use std::fs;
use std::path::Path;

const SCENARIOS_PATH: &str = "data/processed/demo_kamino_scenarios.json";
const MARKDOWN_PATH: &str = "reports/demo_kamino_comparison.md";
const HTML_PATH: &str = "landing/demo_kamino_fragment.html";
const FIXED_POINT_EXPONENT: i8 = -8;

#[derive(Debug, Deserialize)]
struct Scenario {
    scenario_id: String,
    label: String,
    regime_label: String,
    target_ltv: f64,
    band: BandJson,
    position: PositionJson,
    kamino_deviation_bps: u16,
}

#[derive(Debug, Deserialize)]
struct BandJson {
    symbol: String,
    as_of: String,
    target_coverage: f64,
    calibration_buffer_applied: f64,
    claimed_coverage_served: f64,
    point: f64,
    lower: f64,
    upper: f64,
    regime: String,
    forecaster_used: String,
    half_width_bps: f64,
}

#[derive(Debug, Deserialize)]
struct PositionJson {
    debt_usdc: f64,
    collateral_qty: f64,
}

fn regime_code(label: &str) -> u8 {
    match label {
        "normal" => REGIME_NORMAL,
        "long_weekend" => REGIME_LONG_WEEKEND,
        "high_vol" => REGIME_HIGH_VOL,
        "shock_flagged" => REGIME_SHOCK_FLAGGED,
        _ => REGIME_NORMAL,
    }
}

fn forecaster_code(label: &str) -> u8 {
    match label {
        "F0_stale" => FORECASTER_F0_STALE,
        "F1_emp_regime" => FORECASTER_F1_EMP_REGIME,
        _ => FORECASTER_F1_EMP_REGIME,
    }
}

fn encode_symbol(s: &str) -> [u8; 16] {
    let mut out = [0u8; 16];
    let bytes = s.as_bytes();
    let n = bytes.len().min(16);
    out[..n].copy_from_slice(&bytes[..n]);
    out
}

fn to_fixed(v: f64) -> i64 {
    (v * 1e8).round() as i64
}

fn build_band(b: &BandJson) -> PriceBand {
    PriceBand {
        version: 1,
        regime_code: regime_code(&b.regime),
        forecaster_code: forecaster_code(&b.forecaster_used),
        exponent: FIXED_POINT_EXPONENT,
        // Demo runs the Kamino lending integration; tag receipts as Lending.
        profile_code: PROFILE_LENDING,
        target_coverage_bps: (b.target_coverage * 10_000.0).round() as u16,
        claimed_served_bps: (b.claimed_coverage_served * 10_000.0).round() as u16,
        buffer_applied_bps: (b.calibration_buffer_applied * 10_000.0).round() as u16,
        symbol: encode_symbol(&b.symbol),
        point: to_fixed(b.point),
        lower: to_fixed(b.lower),
        upper: to_fixed(b.upper),
        fri_close: to_fixed(b.point),
        fri_ts: 0,
        publish_ts: 0,
        publish_slot: 0,
        signer: [0; 32],
        signer_epoch: 1,
    }
}

fn decision_str(d: LendingDecision) -> &'static str {
    match d {
        LendingDecision::Safe => "Safe",
        LendingDecision::Caution => "Caution",
        LendingDecision::Liquidate => "Liquidate",
    }
}

#[derive(Debug)]
struct Row {
    scenario_id: String,
    symbol: String,
    as_of: String,
    regime: String,
    target_ltv: f64,
    soothsayer_half_width_bps: f64,
    kamino_half_width_bps: f64,
    soothsayer_lower: f64,
    kamino_lower: f64,
    soothsayer_eval: Evaluation,
    kamino_eval: Evaluation,
    decision_diverges: bool,
}

fn run_scenario(s: &Scenario, params: &LendingParams) -> Row {
    let band = build_band(&s.band);
    let position = Position {
        debt_usdc: s.position.debt_usdc,
        collateral_qty: s.position.collateral_qty,
    };
    let soothsayer_eval =
        evaluate(&band, &position, params).expect("scenarios should be well-formed");
    let kamino_eval =
        evaluate_with_flat_band(s.band.point, s.kamino_deviation_bps, &position, params)
            .expect("scenarios should be well-formed");

    let kamino_lower = s.band.point * (1.0 - s.kamino_deviation_bps as f64 / 10_000.0);
    let decision_diverges = soothsayer_eval.decision != kamino_eval.decision;

    Row {
        scenario_id: s.scenario_id.clone(),
        symbol: s.band.symbol.clone(),
        as_of: s.band.as_of.clone(),
        regime: s.regime_label.clone(),
        target_ltv: s.target_ltv,
        soothsayer_half_width_bps: s.band.half_width_bps,
        kamino_half_width_bps: s.kamino_deviation_bps as f64,
        soothsayer_lower: s.band.lower,
        kamino_lower,
        soothsayer_eval,
        kamino_eval,
        decision_diverges,
    }
}

fn write_stdout(rows: &[Row]) {
    println!(
        "\n{:<32} {:<6} {:<12} {:<12} {:>4} {:>9} {:>8} {:>10} {:>10} {:>10} {:>10}",
        "scenario_id",
        "sym",
        "as_of",
        "regime",
        "ltv",
        "S_HW(bps)",
        "K_HW(bps)",
        "S_decision",
        "K_decision",
        "S_LTV",
        "K_LTV",
    );
    println!("{}", "-".repeat(140));
    for r in rows {
        let mark = if r.decision_diverges { "  ◂" } else { "" };
        println!(
            "{:<32} {:<6} {:<12} {:<12} {:>4.2} {:>9.1} {:>8} {:>10} {:>10} {:>10.3} {:>10.3}{}",
            r.scenario_id,
            r.symbol,
            r.as_of,
            r.regime,
            r.target_ltv,
            r.soothsayer_half_width_bps,
            r.kamino_half_width_bps as i64,
            decision_str(r.soothsayer_eval.decision),
            decision_str(r.kamino_eval.decision),
            r.soothsayer_eval.current_ltv,
            r.kamino_eval.current_ltv,
            mark,
        );
    }

    let n_diverge = rows.iter().filter(|r| r.decision_diverges).count();
    let n_total = rows.len();
    println!("\nDecision divergence: {}/{} scenarios", n_diverge, n_total);

    let band_widths: Vec<(String, f64, f64, f64)> = rows
        .iter()
        .map(|r| {
            (
                r.regime.clone(),
                r.soothsayer_half_width_bps,
                r.kamino_half_width_bps,
                r.soothsayer_half_width_bps - r.kamino_half_width_bps,
            )
        })
        .collect();
    for regime in ["normal", "long_weekend", "high_vol"] {
        let regime_rows: Vec<&(String, f64, f64, f64)> = band_widths
            .iter()
            .filter(|(r, _, _, _)| r == regime)
            .collect();
        if regime_rows.is_empty() {
            continue;
        }
        let n = regime_rows.len() as f64;
        let mean_s: f64 = regime_rows.iter().map(|(_, s, _, _)| s).sum::<f64>() / n;
        let mean_k: f64 = regime_rows.iter().map(|(_, _, k, _)| k).sum::<f64>() / n;
        println!(
            "  {:<14} mean half-width — Soothsayer: {:.1} bps, Kamino: {:.1} bps (delta {:+.1})",
            regime,
            mean_s,
            mean_k,
            mean_s - mean_k,
        );
    }
}

fn write_markdown(rows: &[Row], path: &str) -> std::io::Result<()> {
    let mut md = String::new();
    md.push_str("# Kamino-fork demo: Soothsayer band vs legacy flat ±300 bps baseline\n\n");
    md.push_str(
        "*Generated by `cargo run -p soothsayer-demo-kamino --bin run_demo`. \
         Scenario panel is `data/processed/demo_kamino_scenarios.json`, \
         produced from the deployed Python Oracle. The Soothsayer bands below \
         are real outputs from the methodology in Paper 1; the borrower book \
         and flat ±300 bps comparator are synthetic teaching artifacts.*\n\n",
    );
    md.push_str(
        "> **Stylized demo, not the production comparator.** The live \
         Kamino-xStocks comparator runs against on-chain reserve config and \
         lives in the rolling weekly rollups (e.g. \
         `reports/kamino_xstocks_weekend_20260417.md`). Use that for any \
         claim about the deployed Kamino comparison; this file exists for \
         pedagogy and legacy-baseline continuity only.\n\n",
    );
    md.push_str(
        "**Setup.** Each row is one (symbol, weekend, target-LTV) scenario. \
         The same `LendingParams` (max-LTV-at-origination 0.75, liquidation \
         threshold 0.85, regime multipliers all 1.0) are applied to both \
         evaluators. Collateral quantity is 100 units of the underlying; debt \
         is sized so that LTV-against-the-point-price equals the target-LTV \
         column.\n\n",
    );
    md.push_str("## Per-scenario decisions\n\n");
    md.push_str("| Scenario | Symbol | As-of | Regime | tgt LTV | Soothsayer half-width (bps) | Kamino half-width (bps) | Soothsayer decision | Kamino decision | Soothsayer LTV | Kamino LTV |\n");
    md.push_str("|---|---|---|---|---:|---:|---:|---|---|---:|---:|\n");
    for r in rows {
        let s_dec = if r.decision_diverges {
            format!("**{}**", decision_str(r.soothsayer_eval.decision))
        } else {
            decision_str(r.soothsayer_eval.decision).to_string()
        };
        let k_dec = if r.decision_diverges {
            format!("**{}**", decision_str(r.kamino_eval.decision))
        } else {
            decision_str(r.kamino_eval.decision).to_string()
        };
        md.push_str(&format!(
            "| `{}` | {} | {} | {} | {:.2} | {:.1} | {} | {} | {} | {:.3} | {:.3} |\n",
            r.scenario_id,
            r.symbol,
            r.as_of,
            r.regime,
            r.target_ltv,
            r.soothsayer_half_width_bps,
            r.kamino_half_width_bps as i64,
            s_dec,
            k_dec,
            r.soothsayer_eval.current_ltv,
            r.kamino_eval.current_ltv,
        ));
    }
    md.push('\n');

    md.push_str("## Per-regime band-width summary\n\n");
    md.push_str("| Regime | n | Soothsayer mean half-width (bps) | Kamino mean half-width (bps) | Delta |\n");
    md.push_str("|---|---:|---:|---:|---:|\n");
    for regime in ["normal", "long_weekend", "high_vol"] {
        let regime_rows: Vec<&Row> = rows.iter().filter(|r| r.regime == regime).collect();
        if regime_rows.is_empty() {
            continue;
        }
        let n = regime_rows.len() as f64;
        let mean_s: f64 = regime_rows.iter().map(|r| r.soothsayer_half_width_bps).sum::<f64>() / n;
        let mean_k: f64 = regime_rows.iter().map(|r| r.kamino_half_width_bps).sum::<f64>() / n;
        md.push_str(&format!(
            "| {} | {} | {:.1} | {:.1} | {:+.1} |\n",
            regime,
            regime_rows.len(),
            mean_s,
            mean_k,
            mean_s - mean_k,
        ));
    }
    md.push('\n');

    let n_diverge = rows.iter().filter(|r| r.decision_diverges).count();
    md.push_str(&format!(
        "## Decision divergence\n\n**{} of {} scenarios reach a different liquidation decision** under \
         the Soothsayer band than under the legacy flat ±300 bps baseline, holding the \
         lending parameters constant. This is a stylized comparison artifact rather than \
         a literal read of Kamino's live xStocks reserve configuration; the current \
         production comparison in Paper 3 is framed around reserve-buffer exhaustion \
         under observed on-chain Kamino semantics.\n\n",
        n_diverge,
        rows.len(),
    ));

    md.push_str("## Pitch one-liner\n\n");
    md.push_str(
        "*The live reserve buffer is narrow; Soothsayer makes the weekend uncertainty \
         around that buffer explicit.* The two evaluators often agree on benign \
         positions; they diverge when the stylized flat baseline fails to reflect the \
         same regime-aware downside protection that the calibrated band encodes.\n",
    );

    if let Some(parent) = Path::new(path).parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, md)?;
    Ok(())
}

fn write_html(rows: &[Row], path: &str) -> std::io::Result<()> {
    let mut html = String::new();
    html.push_str("<!-- Generated by soothsayer-demo-kamino/run_demo. Drop this fragment into landing/index.html. -->\n");
    html.push_str("<section class=\"demo-kamino\">\n");
    html.push_str("  <h2>Kamino-fork demo: Soothsayer vs legacy flat ±300 bps baseline</h2>\n");
    html.push_str("  <p class=\"demo-kamino__caption\">Real Soothsayer bands from the deployed methodology evaluated against a synthetic borrower book and a legacy flat-band baseline retained for continuity with the original comparator scaffold.</p>\n");
    html.push_str("  <table class=\"demo-kamino__table\">\n");
    html.push_str("    <thead><tr>\n");
    html.push_str("      <th>Scenario</th><th>Sym</th><th>As-of</th><th>Regime</th><th>tgt LTV</th>\n");
    html.push_str("      <th>Soothsayer hw (bps)</th><th>Kamino hw (bps)</th>\n");
    html.push_str("      <th>Soothsayer</th><th>Kamino</th>\n");
    html.push_str("      <th>Soothsayer LTV</th><th>Kamino LTV</th>\n");
    html.push_str("    </tr></thead>\n    <tbody>\n");
    for r in rows {
        let row_class = if r.decision_diverges {
            " class=\"demo-kamino__diverge\""
        } else {
            ""
        };
        html.push_str(&format!(
            "      <tr{}><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td><td>{:.2}</td><td>{:.1}</td><td>{}</td><td>{}</td><td>{}</td><td>{:.3}</td><td>{:.3}</td></tr>\n",
            row_class,
            r.scenario_id,
            r.symbol,
            r.as_of,
            r.regime,
            r.target_ltv,
            r.soothsayer_half_width_bps,
            r.kamino_half_width_bps as i64,
            decision_str(r.soothsayer_eval.decision),
            decision_str(r.kamino_eval.decision),
            r.soothsayer_eval.current_ltv,
            r.kamino_eval.current_ltv,
        ));
    }
    html.push_str("    </tbody>\n  </table>\n");

    let n_diverge = rows.iter().filter(|r| r.decision_diverges).count();
    html.push_str(&format!(
        "  <p class=\"demo-kamino__summary\"><strong>{} of {} scenarios</strong> reach a different liquidation decision under Soothsayer than under the legacy flat ±300 bps baseline. This artifact is retained as a stylized teaching comparison; the live Kamino xStocks framing now centers on reserve-buffer exhaustion under observed on-chain semantics.</p>\n",
        n_diverge,
        rows.len(),
    ));
    html.push_str("</section>\n");

    if let Some(parent) = Path::new(path).parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, html)?;
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let raw = fs::read_to_string(SCENARIOS_PATH).map_err(|e| {
        format!(
            "failed to read {} — run `uv run python scripts/generate_demo_kamino_scenarios.py` first ({})",
            SCENARIOS_PATH, e
        )
    })?;
    let scenarios: Vec<Scenario> = serde_json::from_str(&raw)?;
    let params = LendingParams::default();

    let rows: Vec<Row> = scenarios
        .iter()
        .map(|s| run_scenario(s, &params))
        .collect();

    write_stdout(&rows);
    write_markdown(&rows, MARKDOWN_PATH)?;
    write_html(&rows, HTML_PATH)?;

    println!("\nWrote {}", MARKDOWN_PATH);
    println!("Wrote {}", HTML_PATH);
    Ok(())
}
