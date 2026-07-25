//! The `artefact` command: verify a frozen artefact sidecar's
//! self-hash and (optionally) confirm the band archive's rows actually
//! name that hash — the link between "the scalars that were frozen"
//! and "the bands that were served".
//!
//! The freeze script (`scripts/freeze_lwc_artefact.py`) stamps
//! `_artefact_sha256` = SHA-256 of the **canonical JSON** of the
//! sidecar (Python `json.dumps(obj, sort_keys=True,
//! separators=(",", ":"))`, the self-hash field excluded) — not of the
//! file bytes. [`canonical_json`] reproduces that byte stream exactly:
//! BTree-ordered keys (= Python's `sort_keys` for UTF-8 strings, whose
//! byte order preserves code-point order) and Python's default
//! `ensure_ascii=True` escaping (`\uXXXX` for every non-ASCII char,
//! surrogate pairs above the BMP). Known limitation: floats that
//! Python renders in exponent notation (|x| < 1e-4 or ≥ 1e16) can
//! format differently under Rust's shortest-round-trip printer
//! (`1e-05` vs `1e-5`); no such value appears in current artefacts.
//! The sidecar also names the frozen parquet's file hash, checked when
//! the sibling file exists.
//!
//! Exit codes: 0 = all present hashes verify; 1 = any mismatch;
//! 2 = I/O error.

use std::path::Path;

use serde_json::Value;
use sha2::{Digest, Sha256};

/// Serialise a JSON value byte-identically to Python's
/// `json.dumps(obj, sort_keys=True, separators=(",", ":"))` with the
/// default `ensure_ascii=True`.
pub fn canonical_json(v: &Value, out: &mut String) {
    match v {
        Value::Null => out.push_str("null"),
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Value::Number(n) => out.push_str(&n.to_string()),
        Value::String(s) => escape_python(s, out),
        Value::Array(a) => {
            out.push('[');
            for (i, x) in a.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                canonical_json(x, out);
            }
            out.push(']');
        }
        // serde_json's default Map is a BTreeMap → keys already sorted.
        Value::Object(m) => {
            out.push('{');
            for (i, (k, x)) in m.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                escape_python(k, out);
                out.push(':');
                canonical_json(x, out);
            }
            out.push('}');
        }
    }
}

/// Python `json` string escaping with `ensure_ascii=True`: short
/// escapes for the usual controls, `\uXXXX` (lowercase hex) for other
/// controls and for every char above 0x7E, surrogate pairs above the
/// BMP.
fn escape_python(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 || (c as u32) > 0x7e => {
                let cp = c as u32;
                if cp > 0xFFFF {
                    let v = cp - 0x10000;
                    out.push_str(&format!(
                        "\\u{:04x}\\u{:04x}",
                        0xD800 + (v >> 10),
                        0xDC00 + (v & 0x3FF)
                    ));
                } else {
                    out.push_str(&format!("\\u{cp:04x}"));
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

struct Report {
    file_sha: String,
    /// (recomputed canonical self-hash, stamped `_artefact_sha256`).
    self_hash: Option<(String, String)>,
    /// (parquet name, stamped sha, recomputed sha) — recomputed empty
    /// when the sibling file is absent.
    parquet: Option<(String, String, Option<String>)>,
}

pub fn run(file: &str, expect_sha: Option<&str>, archive: Option<&str>, json: bool) -> i32 {
    let bytes = match std::fs::read(file) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("error: cannot read {file}: {e}");
            return 2;
        }
    };
    let mut report = Report {
        file_sha: hex::encode(Sha256::digest(&bytes)),
        self_hash: None,
        parquet: None,
    };

    if let Ok(Value::Object(mut map)) = serde_json::from_slice::<Value>(&bytes) {
        if let Some(Value::String(stamped)) = map.remove("_artefact_sha256") {
            let mut canon = String::new();
            canonical_json(&Value::Object(map.clone()), &mut canon);
            let recomputed = hex::encode(Sha256::digest(canon.as_bytes()));
            report.self_hash = Some((recomputed, stamped));
        }
        if let (Some(Value::String(pname)), Some(Value::String(psha))) = (
            map.get("_frozen_parquet_path"),
            map.get("_frozen_parquet_sha256"),
        ) {
            let sibling = Path::new(file)
                .parent()
                .unwrap_or_else(|| Path::new("."))
                .join(pname);
            let recomputed = std::fs::read(&sibling)
                .ok()
                .map(|b| hex::encode(Sha256::digest(&b)));
            report.parquet = Some((pname.clone(), psha.clone(), recomputed));
        }
    }

    // The identity a verifier should quote/compare is the canonical
    // self-hash when present (that is what archive rows and reports
    // name), else the plain file hash.
    let effective = report
        .self_hash
        .as_ref()
        .map(|(recomputed, _)| recomputed.clone())
        .unwrap_or_else(|| report.file_sha.clone());

    let mut archive_rows_with_sha: Option<usize> = None;
    if let Some(src) = archive {
        match crate::archive::load(src) {
            Ok(rows) => {
                archive_rows_with_sha =
                    Some(rows.iter().filter(|r| r.artefact_sha256 == effective).count());
            }
            Err(e) => {
                eprintln!("error: cannot load archive {src}: {e}");
                return 2;
            }
        }
    }

    let self_ok = report
        .self_hash
        .as_ref()
        .map(|(recomputed, stamped)| recomputed.eq_ignore_ascii_case(stamped));
    let parquet_ok = report
        .parquet
        .as_ref()
        .and_then(|(_, stamped, recomputed)| {
            recomputed.as_ref().map(|r| r.eq_ignore_ascii_case(stamped))
        });
    let expect_ok = expect_sha.map(|e| e.eq_ignore_ascii_case(&effective));

    if json {
        println!(
            "{}",
            serde_json::to_string_pretty(&serde_json::json!({
                "file": file,
                "file_sha256": report.file_sha,
                "canonical_self_sha256": report.self_hash.as_ref().map(|(r, _)| r),
                "stamped_artefact_sha256": report.self_hash.as_ref().map(|(_, s)| s),
                "self_hash_verified": self_ok,
                "frozen_parquet": report.parquet.as_ref().map(|(name, stamped, recomputed)| {
                    serde_json::json!({
                        "name": name, "stamped_sha256": stamped,
                        "recomputed_sha256": recomputed, "verified": parquet_ok,
                    })
                }),
                "matches_expected": expect_ok,
                "archive_rows_with_sha": archive_rows_with_sha,
            }))
            .unwrap()
        );
    } else {
        println!("{file}");
        println!("  file sha256               {}", report.file_sha);
        match &report.self_hash {
            Some((recomputed, stamped)) => {
                println!("  canonical self-hash       {recomputed}");
                println!("  stamped _artefact_sha256  {stamped}");
                println!(
                    "  self-hash                 {}",
                    if self_ok == Some(true) { "VERIFIED (canonical JSON reproduces the stamp)" } else { "MISMATCH" }
                );
            }
            None => println!("  (no _artefact_sha256 field — plain file, file sha256 is the identity)"),
        }
        if let Some((name, stamped, recomputed)) = &report.parquet {
            match recomputed {
                Some(r) if parquet_ok == Some(true) => {
                    println!("  frozen parquet {name}  sha256 {r}  VERIFIED")
                }
                Some(r) => println!(
                    "  frozen parquet {name}  sha256 {r}  MISMATCH (stamped {stamped})"
                ),
                None => println!(
                    "  frozen parquet {name}  not found next to sidecar — stamped {stamped} unchecked"
                ),
            }
        }
        match expect_ok {
            Some(true) => println!("  expectation               MATCH"),
            Some(false) => {
                println!("  expectation               MISMATCH (expected {})", expect_sha.unwrap())
            }
            None => {}
        }
        if let Some(n) = archive_rows_with_sha {
            println!("  archive rows naming this artefact: {n}");
        }
    }
    let failed = self_ok == Some(false) || parquet_ok == Some(false) || expect_ok == Some(false);
    i32::from(failed)
}
