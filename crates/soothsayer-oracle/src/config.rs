//! Oracle-serving configuration constants — Mondrian (M5) deployment.
//!
//! These values MUST match `src/soothsayer/oracle.py` exactly — the Rust
//! Oracle is a byte-for-byte port of the Python reference. The deployment
//! surface is twenty scalars: 12 trained per-regime quantiles, 4 OOS-fit
//! `c(τ)` bumps, and 4 walk-forward-fit `δ(τ)` shifts. See paper 1 §7.7
//! and `reports/methodology_history.md` (M5 entry).

/// Anchor τ values shared across the three schedules. Values supplied by
/// each schedule below are aligned to these positions.
pub const TARGET_ANCHORS: [f64; 4] = [0.68, 0.85, 0.95, 0.99];

/// Trained per-regime conformal quantile q_r(τ). Rows are aligned with
/// [`REGIMES`]; columns are aligned with [`TARGET_ANCHORS`]. Mirrors
/// `src/soothsayer/oracle.py::REGIME_QUANTILE_TABLE`.
pub const REGIMES: [&str; 3] = ["normal", "long_weekend", "high_vol"];
pub const REGIME_QUANTILE_TABLE: [[f64; 4]; 3] = [
    // normal
    [0.006070, 0.011236, 0.021530, 0.049663],
    // long_weekend
    [0.006648, 0.014248, 0.031032, 0.071228],
    // high_vol
    [0.011628, 0.021460, 0.042911, 0.099418],
];

/// Multiplicative OOS-fit bump c(τ), aligned with [`TARGET_ANCHORS`].
pub const C_BUMP_SCHEDULE: [f64; 4] = [1.498, 1.455, 1.300, 1.076];

/// Walk-forward-fit τ-shift δ(τ), aligned with [`TARGET_ANCHORS`].
pub const DELTA_SHIFT_SCHEDULE: [f64; 4] = [0.05, 0.02, 0.00, 0.00];

/// Mondrian receipt label exposed in PricePoint.forecaster_used.
pub const MONDRIAN_FORECASTER: &str = "mondrian";

/// Default consumer target.
pub const DEFAULT_TARGET_COVERAGE: f64 = 0.85;

/// Top of the τ schedule. Above this we clip to the τ=0.99 row.
pub const MAX_SERVED_TARGET: f64 = 0.99;

/// Bottom of the τ schedule. Below this we clip to the τ=0.68 row.
pub const MIN_SERVED_TARGET: f64 = 0.68;

/// Linearly interpolate a τ-keyed schedule represented as four anchor values
/// aligned with [`TARGET_ANCHORS`]. Targets at or below the smallest anchor
/// return the smallest anchor's value; targets at or above the largest anchor
/// return the largest anchor's value.
pub fn interp_schedule(tau: f64, schedule: &[f64; 4]) -> f64 {
    if tau <= TARGET_ANCHORS[0] {
        return schedule[0];
    }
    if tau >= TARGET_ANCHORS[TARGET_ANCHORS.len() - 1] {
        return schedule[TARGET_ANCHORS.len() - 1];
    }
    for i in 0..(TARGET_ANCHORS.len() - 1) {
        let lo = TARGET_ANCHORS[i];
        let hi = TARGET_ANCHORS[i + 1];
        if lo <= tau && tau <= hi {
            let frac = (tau - lo) / (hi - lo);
            return schedule[i] + frac * (schedule[i + 1] - schedule[i]);
        }
    }
    schedule[TARGET_ANCHORS.len() - 1]
}

pub fn delta_shift_for_target(tau: f64) -> f64 {
    interp_schedule(tau, &DELTA_SHIFT_SCHEDULE)
}

pub fn c_bump_for_target(tau: f64) -> f64 {
    interp_schedule(tau, &C_BUMP_SCHEDULE)
}

/// Per-regime conformal quantile lookup. Unknown regimes fall back to
/// `high_vol` (the conservative widest row).
pub fn regime_quantile_for(regime: &str, tau: f64) -> f64 {
    let idx = REGIMES
        .iter()
        .position(|&r| r == regime)
        .unwrap_or(REGIMES.len() - 1);
    interp_schedule(tau, &REGIME_QUANTILE_TABLE[idx])
}

// === Lending profile (M6b2) constants =====================================
// Mirrors `src/soothsayer/oracle.py`'s LENDING_*, hardcoded here so the
// Rust serving path is self-contained (no parquet/JSON read on the hot
// path). Single source of truth = the audit-trail JSON sidecar at
// `data/processed/m6b2_lending_artefact_v1.json` produced by
// `scripts/build_m6b2_lending_artefact.py`. The unit test
// `lending_constants_match_sidecar` enforces bit-for-bit agreement.
//
// Cells: 6 symbol_classes × 4 τ-anchors = 24 trained quantiles. Plus 4
// OOS-fit c(τ) bumps and 4 walk-forward δ(τ) shifts → 32 deployment
// scalars (vs M5's 20).

/// Lending receipt label exposed in PricePoint.forecaster_used. The
/// distinction from MONDRIAN_FORECASTER on the wire is carried by the
/// `profile_code` byte (Phase A4), not the forecaster_code byte; this
/// label is for display + log parity with M5.
pub const LENDING_FORECASTER: &str = "mondrian";

/// Symbol classes, aligned with [`LENDING_QUANTILE_TABLE`] rows. Order
/// matches `scripts/build_m6b2_lending_artefact.py::CLASSES`.
pub const LENDING_CLASSES: [&str; 6] = [
    "equity_index",
    "equity_meta",
    "equity_highbeta",
    "equity_recent",
    "gold",
    "bond",
];

/// Trained per-(symbol_class, τ) conformal quantile b. Columns aligned
/// with [`TARGET_ANCHORS`]; rows aligned with [`LENDING_CLASSES`]. Values
/// taken bit-for-bit from `m6b2_lending_artefact_v1.json` —
/// `class_quantile_table`. Each literal is the shortest decimal that
/// round-trips to the f64 produced by the Python builder.
pub const LENDING_QUANTILE_TABLE: [[f64; 4]; 6] = [
    // equity_index
    [0.004929947574806843, 0.009255912125044752, 0.016869564748457338, 0.04093702745769363],
    // equity_meta
    [0.007108313040523537, 0.012158507131789693, 0.02317347346475547, 0.053866039467961334],
    // equity_highbeta
    [0.012061294867197299, 0.02289074693494606, 0.04514018281176891, 0.10350537606959213],
    // equity_recent
    [0.016651414900959633, 0.024357263874478712, 0.046296149527498345, 0.05805541746614789],
    // gold
    [0.005351615987301906, 0.009109742914256964, 0.014529936260002976, 0.02415652508648394],
    // bond
    [0.005400631470408542, 0.008565085562056382, 0.013199358216759648, 0.021241256355786425],
];

/// Multiplicative OOS-fit bump c(τ), aligned with [`TARGET_ANCHORS`].
/// Values from `m6b2_lending_artefact_v1.json::c_bump_schedule` — the
/// short-decimal reprs reproduce the np.arange grid noise bit-for-bit.
pub const LENDING_C_BUMP_SCHEDULE: [f64; 4] = [
    1.3239999999999643,
    1.2069999999999772,
    1.0489999999999946,
    1.099999999999989,
];

/// Walk-forward-fit δ(τ) shift, aligned with [`TARGET_ANCHORS`].
/// Identical to the M5 schedule today; kept as an independent constant
/// so a future Lending δ-tune doesn't accidentally bleed into AMM.
pub const LENDING_DELTA_SHIFT_SCHEDULE: [f64; 4] = [0.05, 0.02, 0.0, 0.0];

/// Symbol → symbol_class mapping. Order matches the artefact JSON's
/// `symbol_class_mapping`. Underlying tickers (SPY) map directly;
/// xStock forms (SPYx) are normalised by [`symbol_class_for`].
pub const SYMBOL_CLASS_MAP: &[(&str, &str)] = &[
    ("SPY", "equity_index"),
    ("QQQ", "equity_index"),
    ("AAPL", "equity_meta"),
    ("GOOGL", "equity_meta"),
    ("NVDA", "equity_highbeta"),
    ("TSLA", "equity_highbeta"),
    ("MSTR", "equity_highbeta"),
    ("HOOD", "equity_recent"),
    ("GLD", "gold"),
    ("TLT", "bond"),
];

pub fn lending_delta_shift_for(tau: f64) -> f64 {
    interp_schedule(tau, &LENDING_DELTA_SHIFT_SCHEDULE)
}

pub fn lending_c_bump_for(tau: f64) -> f64 {
    interp_schedule(tau, &LENDING_C_BUMP_SCHEDULE)
}

/// Per-class conformal quantile lookup. Unlike `regime_quantile_for`,
/// there is no implicit fallback — an unknown class is a programmer
/// error (the symbol passed validation in `symbol_class_for`) and
/// returns None.
pub fn lending_class_quantile_for(symbol_class: &str, tau: f64) -> Option<f64> {
    let idx = LENDING_CLASSES.iter().position(|&c| c == symbol_class)?;
    Some(interp_schedule(tau, &LENDING_QUANTILE_TABLE[idx]))
}

/// Resolve symbol → symbol_class. Accepts either an underlying ticker
/// ("SPY") or its xStock form ("SPYx"). Matches the Python helper in
/// `src/soothsayer/universe.py`.
pub fn symbol_class_for(symbol: &str) -> Option<&'static str> {
    for (sym, cls) in SYMBOL_CLASS_MAP {
        if *sym == symbol {
            return Some(*cls);
        }
    }
    if let Some(stripped) = symbol.strip_suffix('x') {
        for (sym, cls) in SYMBOL_CLASS_MAP {
            if *sym == stripped {
                return Some(*cls);
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn anchor_lookup_matches_table() {
        assert!((regime_quantile_for("normal", 0.68) - 0.006070).abs() < 1e-12);
        assert!((regime_quantile_for("high_vol", 0.95) - 0.042911).abs() < 1e-12);
    }

    #[test]
    fn off_grid_interp_is_linear() {
        // Halfway between τ=0.85 (q=0.011236) and τ=0.95 (q=0.021530)
        // should interpolate to (0.011236 + 0.021530) / 2 = 0.016383.
        let q = regime_quantile_for("normal", 0.90);
        assert!((q - 0.016383).abs() < 1e-12);
    }

    #[test]
    fn unknown_regime_falls_back_to_high_vol() {
        assert!(
            (regime_quantile_for("alien", 0.95) - regime_quantile_for("high_vol", 0.95)).abs()
                < 1e-12
        );
    }

    #[test]
    fn bump_clamps_to_endpoints() {
        assert!((c_bump_for_target(0.0) - C_BUMP_SCHEDULE[0]).abs() < 1e-12);
        assert!((c_bump_for_target(1.0) - C_BUMP_SCHEDULE[3]).abs() < 1e-12);
    }

    #[test]
    fn lending_class_lookup_matches_table() {
        // equity_index row, τ=0.95 anchor.
        let q = lending_class_quantile_for("equity_index", 0.95).unwrap();
        assert!((q - 0.016869564748457338).abs() < 1e-15);
        // bond row, τ=0.99 anchor.
        let q = lending_class_quantile_for("bond", 0.99).unwrap();
        assert!((q - 0.021241256355786425).abs() < 1e-15);
    }

    #[test]
    fn lending_unknown_class_returns_none() {
        assert!(lending_class_quantile_for("alien", 0.95).is_none());
    }

    #[test]
    fn lending_off_grid_interp_is_linear() {
        // Halfway between τ=0.85 (b=0.009255912125044752) and τ=0.95
        // (b=0.016869564748457338) for equity_index should land at the mean.
        let q = lending_class_quantile_for("equity_index", 0.90).unwrap();
        let expected = (0.009255912125044752 + 0.016869564748457338) / 2.0;
        assert!((q - expected).abs() < 1e-15);
    }

    #[test]
    fn symbol_class_for_handles_xstock_suffix() {
        assert_eq!(symbol_class_for("SPY"), Some("equity_index"));
        assert_eq!(symbol_class_for("SPYx"), Some("equity_index"));
        assert_eq!(symbol_class_for("HOOD"), Some("equity_recent"));
        assert_eq!(symbol_class_for("HOODx"), Some("equity_recent"));
        assert_eq!(symbol_class_for("FAKE"), None);
    }

    /// SSOT cross-check: the hardcoded LENDING_* constants must agree
    /// with the JSON sidecar at `data/processed/m6b2_lending_artefact_v1.json`
    /// up to ≤ 2 ULP. We can't require bit-exact equality through serde_json
    /// because its decimal-parser disagrees with Python's (and Rust's
    /// f64-literal parser) by ≤ 1 ULP on a handful of values — those are
    /// "round-half-to-even" edge cases where serde_json's path differs.
    /// Runtime serving uses our hardcoded literal, which matches Python's
    /// `json.loads` bit-for-bit (verified via `verify_rust_oracle.py`); the
    /// test tolerance is just for the JSON re-parse path.
    ///
    /// Real drift (a regenerated artefact with different values) shifts
    /// numbers by orders of magnitude more than 2 ULP and fails this test
    /// loudly. Skips silently if the sidecar isn't materialised.
    #[test]
    fn lending_constants_match_sidecar() {
        use std::path::PathBuf;
        let sidecar_path: PathBuf = ["..", "..", "data", "processed", "m6b2_lending_artefact_v1.json"]
            .iter()
            .collect();
        let Ok(text) = std::fs::read_to_string(&sidecar_path) else {
            eprintln!("skip: {sidecar_path:?} not present");
            return;
        };
        let v: serde_json::Value = serde_json::from_str(&text).expect("valid JSON");

        fn ulp_close(a: f64, b: f64) -> bool {
            // ≤ 2 ULP at the value's magnitude.
            let mag = a.abs().max(b.abs()).max(f64::MIN_POSITIVE);
            (a - b).abs() <= 2.0 * mag * f64::EPSILON
        }

        // Quantile table
        let qt = &v["class_quantile_table"];
        for (row_idx, cls) in LENDING_CLASSES.iter().enumerate() {
            for (col_idx, tau) in TARGET_ANCHORS.iter().enumerate() {
                let key = format!("{tau:.2}");
                let want = qt[cls][&key].as_f64().expect("number");
                let got = LENDING_QUANTILE_TABLE[row_idx][col_idx];
                assert!(ulp_close(want, got),
                    "quantile drift at class={cls} tau={tau}: want={want} got={got}");
            }
        }

        // c-bump schedule
        for (i, tau) in TARGET_ANCHORS.iter().enumerate() {
            let key = format!("{tau:.2}");
            let want = v["c_bump_schedule"][&key].as_f64().expect("number");
            let got = LENDING_C_BUMP_SCHEDULE[i];
            assert!(ulp_close(want, got),
                "c_bump drift at tau={tau}: want={want} got={got}");
        }

        // delta-shift schedule
        for (i, tau) in TARGET_ANCHORS.iter().enumerate() {
            let key = format!("{tau:.2}");
            let want = v["delta_shift_schedule"][&key].as_f64().expect("number");
            let got = LENDING_DELTA_SHIFT_SCHEDULE[i];
            assert!(ulp_close(want, got),
                "delta_shift drift at tau={tau}: want={want} got={got}");
        }

        // symbol_class mapping
        let sym_map = v["symbol_class_mapping"].as_object().expect("object");
        for (k, v_) in sym_map {
            let want = v_.as_str().expect("string");
            assert_eq!(symbol_class_for(k), Some(want),
                "symbol_class mismatch for {k}");
        }
    }
}
