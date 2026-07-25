//! The `commitment` command: audit the pre-open publication chain.
//!
//! A weekend's band decomposes as width (committed Friday-close, in
//! `commitments_v1.csv`, before any weekend information existed) plus
//! center (published Monday pre-open into `bands_v1.csv` with
//! `provenance=published_pre_open`). This command checks the chain:
//!
//!   1. every published_pre_open band row is BACKED by a commitment
//!      with the same (weekend, symbol, τ, artefact sha);
//!   2. the band's realised half-width equals the committed
//!      `half_width_abs` (a commitment is binding — verbatim reuse);
//!   3. the band is symmetric about its point;
//!   4. commitments whose target open has passed WITHOUT a pre-open
//!      band row are reported as lapsed-to-retro (disclosure — the
//!      Tuesday retro path fills them; a standing known case is MSTR,
//!      whose BTC factor bar is not in scryer Monday morning).
//!
//! What this does NOT yet verify: that the point equals
//! fri_close × (1 + factor return) recomputed from public futures data
//! — the T3-lite replay leg, deferred; the implied factor return is
//! printed for inspection instead.
//!
//! Exit codes: 0 = chain consistent; 1 = unbacked row or width/center
//! mismatch; 2 = data error.

use std::collections::BTreeMap;

use crate::archive;

const REL_TOL: f64 = 1e-6;

pub fn run(commitments_src: &str, bands_src: &str, json: bool) -> i32 {
    let commitments = match archive::load_commitments(commitments_src) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("error: {e}");
            return 2;
        }
    };
    let bands = match archive::load(bands_src) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: {e}");
            return 2;
        }
    };

    let key = |w: &str, s: &str, tau: f64, sha: &str| {
        format!("{w}|{s}|{}|{sha}", (tau * 10_000.0).round() as i64)
    };
    let com_by_key: BTreeMap<String, &archive::CommitmentRow> = commitments
        .iter()
        .map(|c| (key(&c.weekend_date, &c.symbol, c.tau, &c.artefact_sha256), c))
        .collect();

    let mut unbacked: Vec<String> = Vec::new();
    let mut width_mismatch: Vec<String> = Vec::new();
    let mut asym: Vec<String> = Vec::new();
    let mut implied_factor: BTreeMap<String, f64> = BTreeMap::new();
    let mut checked = 0usize;

    for b in bands.iter().filter(|b| b.provenance == "published_pre_open") {
        checked += 1;
        let k = key(&b.weekend_date, &b.symbol, b.tau, &b.artefact_sha256);
        let Some(c) = com_by_key.get(&k) else {
            unbacked.push(k);
            continue;
        };
        let half_band = (b.upper - b.lower) / 2.0;
        if (half_band - c.half_width_abs).abs() > REL_TOL * c.half_width_abs.abs().max(1e-12) {
            width_mismatch.push(format!(
                "{k}: band half {half_band} vs committed {}",
                c.half_width_abs
            ));
        }
        let mid = (b.upper + b.lower) / 2.0;
        if (mid - b.point).abs() > REL_TOL * b.point.abs().max(1e-12) {
            asym.push(format!("{k}: midpoint {mid} vs point {}", b.point));
        }
        implied_factor
            .entry(format!("{}|{}", b.weekend_date, b.symbol))
            .or_insert(b.point / c.fri_close - 1.0);
    }

    // Lapsed commitments: target open passed, no pre-open band row.
    let today = {
        let days = (std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs()
            / 86_400) as i64;
        let (y, m, d) = crate::truth::civil_from_days(days);
        format!("{y:04}-{m:02}-{d:02}")
    };
    let band_keys: std::collections::BTreeSet<String> = bands
        .iter()
        .filter(|b| b.provenance == "published_pre_open")
        .map(|b| key(&b.weekend_date, &b.symbol, b.tau, &b.artefact_sha256))
        .collect();
    let lapsed: Vec<&&archive::CommitmentRow> = com_by_key
        .iter()
        .filter(|(k, c)| c.mon_date.as_str() < today.as_str() && !band_keys.contains(*k))
        .map(|(_, c)| c)
        .collect();
    let lapsed_pretty: Vec<String> = {
        let mut set: Vec<String> = lapsed
            .iter()
            .map(|c| format!("{} {}", c.weekend_date, c.symbol))
            .collect();
        set.dedup();
        set
    };

    let failed = !unbacked.is_empty() || !width_mismatch.is_empty() || !asym.is_empty();

    if json {
        let out = serde_json::json!({
            "pre_open_rows_checked": checked,
            "commitment_rows": commitments.len(),
            "unbacked": unbacked,
            "width_mismatches": width_mismatch,
            "asymmetric": asym,
            "lapsed_to_retro": lapsed_pretty,
            "implied_factor_return": implied_factor,
            "consistent": !failed,
        });
        println!("{}", serde_json::to_string_pretty(&out).unwrap());
    } else {
        println!("soothsayer-verify commitment — pre-open publication chain audit");
        println!();
        println!(
            "Checked {checked} published_pre_open band rows against {} commitment rows.",
            commitments.len()
        );
        if unbacked.is_empty() && width_mismatch.is_empty() && asym.is_empty() {
            println!("Width chain: every pre-open band uses its committed half-width verbatim.");
        }
        for u in &unbacked {
            println!("UNBACKED pre-open row (no matching commitment): {u}");
        }
        for w in &width_mismatch {
            println!("WIDTH MISMATCH: {w}");
        }
        for a in &asym {
            println!("ASYMMETRIC BAND: {a}");
        }
        if !lapsed_pretty.is_empty() {
            println!(
                "Lapsed to retro path (committed, open passed, no pre-open row): {}",
                lapsed_pretty.join(", ")
            );
        }
        if !implied_factor.is_empty() {
            println!();
            println!("Implied factor returns (point / committed fri_close − 1; replay");
            println!("from public futures data is the deferred T3-lite leg):");
            for (k, fr) in &implied_factor {
                println!("  {k}: {:+.4}%", fr * 100.0);
            }
        }
        println!();
        println!(
            "Note: this audits the width chain and band geometry. Coverage of these \
             rows is `soothsayer-verify coverage`; point construction replay is not \
             yet verified."
        );
    }
    i32::from(failed)
}
