//! The `coverage` command: fetch the band archive, fetch truth
//! independently, recompute the coverage statistics, and compare
//! realised coverage against the claimed τ.
//!
//! Exit codes: 0 = claims consistent; 1 = a pooled Kupiec test rejects
//! a coverage claim at the 5% level; 2 = data/integrity error.

use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;

use crate::archive::{self, BandRow};
use crate::stats;
use crate::truth::Truth;

pub struct Args {
    pub archive: String,
    pub tau: Option<f64>,
    pub symbol: Option<String>,
    pub since: Option<String>,
    pub json: bool,
}

struct TauReport {
    tau: f64,
    n: usize,
    violations: usize,
    realised: f64,
    mean_half_width_bps: f64,
    kupiec_lr: f64,
    kupiec_p: f64,
    christ_lr: f64,
    christ_df: u32,
    christ_p: f64,
}

impl TauReport {
    fn rejected(&self) -> bool {
        self.kupiec_p.is_finite() && self.kupiec_p < 0.05
    }
    fn verdict(&self) -> &'static str {
        if self.rejected() {
            "REJECTED (Kupiec p < 0.05)"
        } else {
            "consistent"
        }
    }
}

fn tau_key(tau: f64) -> i64 {
    (tau * 10_000.0).round() as i64
}

pub fn run(args: &Args) -> i32 {
    match run_inner(args) {
        Ok(code) => code,
        Err(e) => {
            eprintln!("error: {e}");
            2
        }
    }
}

fn run_inner(args: &Args) -> Result<i32, Box<dyn Error>> {
    let mut rows = archive::load(&args.archive)?;
    let total_rows = rows.len();
    if let Some(sym) = &args.symbol {
        rows.retain(|r| r.symbol.eq_ignore_ascii_case(sym));
    }
    if let Some(since) = &args.since {
        rows.retain(|r| r.weekend_date.as_str() >= since.as_str());
    }
    if let Some(tau) = args.tau {
        rows.retain(|r| tau_key(r.tau) == tau_key(tau));
    }
    if rows.is_empty() {
        return Err(format!(
            "no archive rows left after filters ({total_rows} rows in archive)"
        )
        .into());
    }
    // Deterministic order: (symbol, weekend) — the per-symbol
    // independence test needs time order within symbol.
    rows.sort_by(|a, b| {
        (a.symbol.as_str(), a.weekend_date.as_str(), tau_key(a.tau)).cmp(&(
            b.symbol.as_str(),
            b.weekend_date.as_str(),
            tau_key(b.tau),
        ))
    });

    let symbols: BTreeSet<String> = rows.iter().map(|r| r.symbol.clone()).collect();
    let weekends: BTreeSet<&str> = rows.iter().map(|r| r.weekend_date.as_str()).collect();
    let artefacts: BTreeSet<&str> = rows.iter().map(|r| r.artefact_sha256.as_str()).collect();
    let min_mon = rows.iter().map(|r| r.mon_date.as_str()).min().unwrap();

    eprintln!(
        "archive: {} rows / {} weekends / {} symbols ({} → {})",
        rows.len(),
        weekends.len(),
        symbols.len(),
        weekends.iter().next().unwrap(),
        weekends.iter().last().unwrap(),
    );
    eprintln!("fetching truth from Yahoo v8 chart for {} symbols …", symbols.len());
    let truth = Truth::fetch(&symbols, min_mon)?;

    // Resolve truth per row; collect misses and split disclosures.
    // A missing bar whose target open hasn't happened yet is PENDING
    // (published_pre_open rows exist before their outcome by design);
    // a missing bar for a past open is a hard error.
    let today = {
        let days = (std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_secs()
            / 86_400) as i64;
        let (y, m, d) = crate::truth::civil_from_days(days);
        format!("{y:04}-{m:02}-{d:02}")
    };
    let mut missing: BTreeSet<(String, String)> = BTreeSet::new();
    let mut pending = 0usize;
    let mut split_notes: BTreeSet<String> = BTreeSet::new();
    let mut resolved: Vec<(&BandRow, f64)> = Vec::with_capacity(rows.len());
    for row in &rows {
        match truth.open(&row.symbol, &row.mon_date) {
            Some(open) => {
                if open.split_factor != 1.0 {
                    split_notes.insert(format!(
                        "{} {}: Yahoo open renormalised ×{:.6} for post-dated split(s)",
                        row.symbol, row.mon_date, open.split_factor
                    ));
                }
                resolved.push((row, open.value));
            }
            None if row.mon_date >= today => pending += 1,
            None => {
                missing.insert((row.symbol.clone(), row.mon_date.clone()));
            }
        }
    }
    if !missing.is_empty() {
        for (sym, date) in &missing {
            eprintln!("missing truth bar: {sym} {date}");
        }
        return Err(format!(
            "{} (symbol, date) truth bars missing from Yahoo — cannot verify",
            missing.len()
        )
        .into());
    }
    if pending > 0 {
        eprintln!(
            "{pending} rows target an open on/after {today} — pending, excluded from coverage."
        );
    }
    if resolved.is_empty() {
        return Err("every selected row is pending — nothing to verify yet".into());
    }

    // Per-τ statistics; per-symbol independence needs grouped vectors.
    let mut by_tau: BTreeMap<i64, Vec<(&BandRow, f64)>> = BTreeMap::new();
    for (row, open) in resolved {
        by_tau.entry(tau_key(row.tau)).or_default().push((row, open));
    }

    let mut reports: Vec<TauReport> = Vec::new();
    let mut per_symbol_detail: Vec<(String, usize, f64, f64)> = Vec::new();
    let detail_tau = args.tau.map(tau_key).unwrap_or(9_500);

    for (key, entries) in &by_tau {
        let tau = *key as f64 / 10_000.0;
        let mut groups: Vec<Vec<u8>> = Vec::new();
        let mut all: Vec<u8> = Vec::with_capacity(entries.len());
        let mut half_width_sum = 0.0;
        for sym in &symbols {
            // entries are (symbol, weekend)-sorted already.
            let v: Vec<u8> = entries
                .iter()
                .filter(|(r, _)| &r.symbol == sym)
                .map(|(r, open)| u8::from(!(*open >= r.lower && *open <= r.upper)))
                .collect();
            if v.is_empty() {
                continue;
            }
            all.extend_from_slice(&v);
            if *key == detail_tau {
                let (_, p) = stats::kupiec(&v, tau);
                let viol_rate = v.iter().map(|&x| x as f64).sum::<f64>() / v.len() as f64;
                per_symbol_detail.push((sym.clone(), v.len(), viol_rate, p));
            }
            groups.push(v);
        }
        for (r, _) in entries {
            half_width_sum += r.half_width_bps;
        }
        let violations = all.iter().map(|&x| x as usize).sum::<usize>();
        let (kupiec_lr, kupiec_p) = stats::kupiec(&all, tau);
        let (christ_lr, christ_df, christ_p) = stats::pooled_independence(&groups);
        reports.push(TauReport {
            tau,
            n: all.len(),
            violations,
            realised: 1.0 - violations as f64 / all.len() as f64,
            mean_half_width_bps: half_width_sum / entries.len() as f64,
            kupiec_lr,
            kupiec_p,
            christ_lr,
            christ_df,
            christ_p,
        });
    }

    let retro = rows.iter().filter(|r| r.provenance == "retro_frozen").count();
    let pre_open = rows
        .iter()
        .filter(|r| r.provenance == "published_pre_open")
        .count();
    let any_rejected = reports.iter().any(TauReport::rejected);

    if args.json {
        print_json(
            &reports, &per_symbol_detail, &rows, &artefacts, retro, pre_open, pending,
            &split_notes,
        );
    } else {
        print_human(
            &reports,
            &per_symbol_detail,
            detail_tau,
            &weekends,
            &artefacts,
            retro,
            pre_open,
            pending,
            rows.len(),
            &split_notes,
        );
    }
    Ok(i32::from(any_rejected))
}

fn fmt_p(p: f64) -> String {
    if p.is_finite() {
        format!("{p:.4}")
    } else {
        "n/a".to_string()
    }
}

#[allow(clippy::too_many_arguments)]
fn print_human(
    reports: &[TauReport],
    per_symbol: &[(String, usize, f64, f64)],
    detail_tau: i64,
    weekends: &BTreeSet<&str>,
    artefacts: &BTreeSet<&str>,
    retro: usize,
    pre_open: usize,
    pending: usize,
    n_rows: usize,
    split_notes: &BTreeSet<String>,
) {
    println!("soothsayer-verify — independent audit of published band coverage");
    println!();
    println!(
        "Verified {} rows over {} weekends ({} → {}).",
        n_rows,
        weekends.len(),
        weekends.iter().next().unwrap(),
        weekends.iter().last().unwrap()
    );
    for sha in artefacts {
        println!("Frozen artefact SHA-256: {sha}");
    }
    println!("Truth: Yahoo v8 chart daily opens, fetched independently at run time.");
    if split_notes.is_empty() {
        println!("Split renormalisation: none required.");
    } else {
        for note in split_notes {
            println!("Split renormalisation: {note}");
        }
    }
    println!();
    println!("  τ      n   viol  realised  half-width(bps)  Kupiec p  Christoffersen p  verdict");
    for r in reports {
        println!(
            "  {:.2} {:>4}  {:>4}    {:.4}         {:>7.1}    {:>6}          {:>6}    {}",
            r.tau,
            r.n,
            r.violations,
            r.realised,
            r.mean_half_width_bps,
            fmt_p(r.kupiec_p),
            fmt_p(r.christ_p),
            r.verdict()
        );
    }
    if !per_symbol.is_empty() {
        println!();
        println!("Per-symbol at τ = {:.2}:", detail_tau as f64 / 10_000.0);
        println!("  symbol   n   viol-rate  Kupiec p");
        for (sym, n, viol, p) in per_symbol {
            println!("  {sym:<7} {n:>3}     {viol:.4}    {}", fmt_p(*p));
        }
    }
    println!();
    println!(
        "Provenance: retro_frozen {retro}, published_pre_open {pre_open}{}",
        if pending > 0 {
            format!(" ({pending} pre-open rows pending their target open — excluded)")
        } else {
            String::new()
        }
    );
    println!();
    println!("Caveats (read before citing):");
    if retro > 0 {
        println!(
            "  - {retro}/{n_rows} rows are provenance=retro_frozen: computed after the \
             weekend outcome, from an artefact frozen BEFORE it (SHA above)."
        );
    }
    if pre_open > 0 {
        println!(
            "  - published_pre_open rows were emitted before their target open; \
             audit their width commitments with `soothsayer-verify commitment`."
        );
    }
    println!(
        "  - Per-symbol n is small; per-symbol Kupiec has low power at these sizes."
    );
    println!(
        "  - τ=0.99 sits near the finite-sample tail ceiling (out of v1 scope per Paper 1);"
    );
    println!(
        "    a Christoffersen 'n/a' means zero violations left nothing to test."
    );
    println!(
        "  - This audits coverage of the recorded bands (T1). It does not re-derive the"
    );
    println!(
        "    bands from market data (T3) or attest on-chain publication timing."
    );
}

#[allow(clippy::too_many_arguments)]
fn print_json(
    reports: &[TauReport],
    per_symbol: &[(String, usize, f64, f64)],
    rows: &[BandRow],
    artefacts: &BTreeSet<&str>,
    retro: usize,
    pre_open: usize,
    pending: usize,
    split_notes: &BTreeSet<String>,
) {
    let nan_null = |x: f64| {
        if x.is_finite() {
            serde_json::json!(x)
        } else {
            serde_json::Value::Null
        }
    };
    let out = serde_json::json!({
        "n_rows": rows.len(),
        "artefact_sha256": artefacts.iter().collect::<Vec<_>>(),
        "provenance_retro_frozen": retro,
        "provenance_published_pre_open": pre_open,
        "pending_rows_excluded": pending,
        "split_renormalisations": split_notes.iter().collect::<Vec<_>>(),
        "per_tau": reports.iter().map(|r| serde_json::json!({
            "tau": r.tau,
            "n": r.n,
            "violations": r.violations,
            "realised": r.realised,
            "mean_half_width_bps": r.mean_half_width_bps,
            "kupiec_lr": nan_null(r.kupiec_lr),
            "kupiec_p": nan_null(r.kupiec_p),
            "christoffersen_lr": nan_null(r.christ_lr),
            "christoffersen_df": r.christ_df,
            "christoffersen_p": nan_null(r.christ_p),
            "rejected": r.rejected(),
        })).collect::<Vec<_>>(),
        "per_symbol": per_symbol.iter().map(|(s, n, v, p)| serde_json::json!({
            "symbol": s, "n": n, "violation_rate": v, "kupiec_p": nan_null(*p),
        })).collect::<Vec<_>>(),
    });
    println!("{}", serde_json::to_string_pretty(&out).unwrap());
}
