//! Oracle-serving configuration constants — Mondrian (M5) reference path
//! and Locally-Weighted Conformal (M6 LWC, deployed) path.
//!
//! Both forecasters share the same on-chain wire format (`PriceUpdate`
//! Borsh layout), the same regime taxonomy (3 cells), the same τ-anchor
//! grid, and the same band formula `point * (1 ± q_eff)`. They differ
//! only in how `q_eff` is constructed:
//!
//!   - **M5 / Mondrian**:  `q_eff = c(τ) · q_r(τ)`
//!     12 trained per-regime conformal quantiles on raw relative residuals
//!     + 4 OOS-fit `c(τ)` bumps + 4 walk-forward `δ(τ)` shifts = 20 scalars.
//!     Live on-chain (`forecaster_code = 2`).
//!
//!   - **M6 / LWC**:       `q_eff = c(τ) · q_r(τ) · σ̂_s(t)`
//!     12 trained per-regime conformal quantiles on standardised residuals
//!     + 4 OOS-fit `c(τ)` bumps + 0 walk-forward shifts (collapses under
//!     per-symbol σ̂ standardisation) = 16 scalars. Plus a per-symbol pre-
//!     Friday EWMA σ̂ rule (half-life 8 weekends, ≥ 8 past obs warm-up)
//!     read from the artefact parquet's `sigma_hat_sym_pre_fri` column.
//!     On-chain wire-format slot reserved as `forecaster_code = 3`.
//!
//! Constants in this file MUST match the Python reference
//! (`src/soothsayer/oracle.py`) bit-for-bit. The unit tests
//! `mondrian_constants_match_sidecar` and `lwc_constants_match_sidecar`
//! enforce parity against the JSON sidecars at
//! `data/processed/mondrian_artefact_v2.json` and
//! `data/processed/lwc_artefact_v1.json` respectively. See paper 1
//! §4 / §7 and `reports/methodology_history.md`.

/// Anchor τ values shared across the schedules of both forecasters. Values
/// supplied by each schedule below are aligned to these positions.
pub const TARGET_ANCHORS: [f64; 4] = [0.68, 0.85, 0.95, 0.99];

/// Regime taxonomy shared across both forecasters.
pub const REGIMES: [&str; 3] = ["normal", "long_weekend", "high_vol"];

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

// =========================================================================
// === M5 / Mondrian constants =============================================
// =========================================================================

/// Trained per-regime conformal quantile q_r(τ) on raw relative residuals.
/// Rows aligned with [`REGIMES`]; columns aligned with [`TARGET_ANCHORS`].
/// Mirrors `src/soothsayer/oracle.py::REGIME_QUANTILE_TABLE`.
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

pub fn delta_shift_for_target(tau: f64) -> f64 {
    interp_schedule(tau, &DELTA_SHIFT_SCHEDULE)
}

pub fn c_bump_for_target(tau: f64) -> f64 {
    interp_schedule(tau, &C_BUMP_SCHEDULE)
}

/// Per-regime conformal quantile lookup (M5). Unknown regimes fall back to
/// `high_vol` (the conservative widest row).
pub fn regime_quantile_for(regime: &str, tau: f64) -> f64 {
    let idx = REGIMES
        .iter()
        .position(|&r| r == regime)
        .unwrap_or(REGIMES.len() - 1);
    interp_schedule(tau, &REGIME_QUANTILE_TABLE[idx])
}

// =========================================================================
// === M6 / LWC (deployed) constants =======================================
// =========================================================================

/// LWC receipt label exposed in PricePoint.forecaster_used. Wire-encoded
/// as `forecaster_code = 3` (`FORECASTER_LWC` in the consumer crate).
pub const LWC_FORECASTER: &str = "lwc";

/// Per-symbol pre-Friday EWMA σ̂ half-life, in weekends. Decay rate
/// λ = 0.5 ** (1 / HL) ≈ 0.917 per past Friday at HL = 8.
pub const SIGMA_HAT_HL_WEEKENDS: u32 = 8;

/// Minimum past relative-residual observations required before σ̂_s(t) is
/// defined; weekends with fewer past Fridays per symbol are dropped at
/// warm-up. Matches Python's `SIGMA_HAT_MIN`.
pub const SIGMA_HAT_MIN: u32 = 8;

/// Trained per-regime conformal quantile q_r(τ) on STANDARDISED residuals.
/// Rows aligned with [`REGIMES`]; columns aligned with [`TARGET_ANCHORS`].
/// Bit-for-bit from `data/processed/lwc_artefact_v1.json::regime_quantile_table`.
/// Each literal is the shortest decimal that round-trips to the f64 produced
/// by the Python builder.
pub const LWC_REGIME_QUANTILE_TABLE: [[f64; 4]; 3] = [
    // normal
    [0.7767272317989513, 1.2194990647624138, 1.9681608719699637, 3.3279604103068388],
    // long_weekend
    [0.8637555272733264, 1.3648606059791455, 2.2208333798923596, 4.015199635992656],
    // high_vol
    [1.1086378907121812, 1.9432779938106572, 3.097125105461176, 6.456344506221736],
];

/// LWC OOS-fit multiplicative bump c(τ), aligned with [`TARGET_ANCHORS`].
/// Three of four near-identity; only c(0.95) carries meaningful OOS info.
pub const LWC_C_BUMP_SCHEDULE: [f64; 4] = [
    1.0,
    1.0,
    1.0789999999999913,
    1.0029999999999997,
];

/// LWC walk-forward δ(τ) shift — identically zero. Per-symbol σ̂
/// standardisation tightens cross-split realised-coverage variance enough
/// that no structural-conservatism shift is required. Retained as a
/// 4-zero vector for shape-compatibility with the receipt schema.
pub const LWC_DELTA_SHIFT_SCHEDULE: [f64; 4] = [0.0, 0.0, 0.0, 0.0];

pub fn lwc_delta_shift_for(tau: f64) -> f64 {
    interp_schedule(tau, &LWC_DELTA_SHIFT_SCHEDULE)
}

pub fn lwc_c_bump_for(tau: f64) -> f64 {
    interp_schedule(tau, &LWC_C_BUMP_SCHEDULE)
}

/// Per-regime LWC standardised quantile lookup. Unknown regimes fall back
/// to `high_vol` (the conservative widest row), mirroring M5 semantics.
pub fn lwc_regime_quantile_for(regime: &str, tau: f64) -> f64 {
    let idx = REGIMES
        .iter()
        .position(|&r| r == regime)
        .unwrap_or(REGIMES.len() - 1);
    interp_schedule(tau, &LWC_REGIME_QUANTILE_TABLE[idx])
}

#[cfg(test)]
mod tests {
    use super::*;

    // ---- M5 / Mondrian tests ---------------------------------------------

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

    // ---- M6 / LWC tests --------------------------------------------------

    #[test]
    fn lwc_anchor_lookup_matches_table() {
        // normal regime, τ=0.95 standardised quantile from the JSON sidecar.
        let q = lwc_regime_quantile_for("normal", 0.95);
        assert!((q - 1.9681608719699637).abs() < 1e-15);
        // high_vol regime, τ=0.99.
        let q = lwc_regime_quantile_for("high_vol", 0.99);
        assert!((q - 6.456344506221736).abs() < 1e-15);
    }

    #[test]
    fn lwc_off_grid_interp_is_linear() {
        // Halfway between τ=0.85 (q=1.2194990647624138) and τ=0.95
        // (q=1.9681608719699637) for normal should land at the mean.
        let q = lwc_regime_quantile_for("normal", 0.90);
        let expected = (1.2194990647624138 + 1.9681608719699637) / 2.0;
        assert!((q - expected).abs() < 1e-15);
    }

    #[test]
    fn lwc_bump_clamps_to_endpoints() {
        assert!((lwc_c_bump_for(0.0) - LWC_C_BUMP_SCHEDULE[0]).abs() < 1e-12);
        assert!((lwc_c_bump_for(1.0) - LWC_C_BUMP_SCHEDULE[3]).abs() < 1e-12);
    }

    #[test]
    fn lwc_delta_is_identically_zero() {
        for &tau in &[0.68, 0.85, 0.95, 0.99] {
            assert_eq!(lwc_delta_shift_for(tau), 0.0);
        }
    }

    #[test]
    fn lwc_unknown_regime_falls_back_to_high_vol() {
        assert!(
            (lwc_regime_quantile_for("alien", 0.95)
                - lwc_regime_quantile_for("high_vol", 0.95))
                .abs()
                < 1e-15
        );
    }

    /// SSOT cross-check: the hardcoded LWC_* constants must agree with the
    /// JSON sidecar at `data/processed/lwc_artefact_v1.json` up to ≤ 2 ULP.
    /// We can't require bit-exact equality through serde_json because its
    /// decimal-parser disagrees with Python's (and Rust's f64-literal parser)
    /// by ≤ 1 ULP on a handful of values — those are "round-half-to-even"
    /// edge cases where serde_json's path differs. Runtime serving uses our
    /// hardcoded literal, which matches Python's `json.loads` bit-for-bit
    /// (verified via `verify_rust_oracle.py`); the test tolerance is just
    /// for the JSON re-parse path.
    ///
    /// Real drift (a regenerated artefact with different values) shifts
    /// numbers by orders of magnitude more than 2 ULP and fails this test
    /// loudly. Skips silently if the sidecar isn't materialised.
    #[test]
    fn lwc_constants_match_sidecar() {
        use std::path::PathBuf;
        let sidecar_path: PathBuf = ["..", "..", "data", "processed", "lwc_artefact_v1.json"]
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

        // Methodology version sanity check.
        assert_eq!(
            v["methodology_version"].as_str(),
            Some("M6_LWC"),
            "expected methodology_version=M6_LWC; sidecar reports {:?}",
            v["methodology_version"]
        );
        assert_eq!(v["_lwc_variant"].as_str(), Some("ewma_hl8"));

        // σ̂ rule constants.
        assert_eq!(v["sigma_hat"]["half_life_weekends"].as_u64(), Some(SIGMA_HAT_HL_WEEKENDS as u64));
        assert_eq!(v["sigma_hat"]["min_past_obs"].as_u64(), Some(SIGMA_HAT_MIN as u64));

        // Quantile table — standardised residuals.
        let qt = &v["regime_quantile_table"];
        for (row_idx, regime) in REGIMES.iter().enumerate() {
            for (col_idx, tau) in TARGET_ANCHORS.iter().enumerate() {
                let key = format!("{tau:.2}");
                let want = qt[regime][&key].as_f64().expect("number");
                let got = LWC_REGIME_QUANTILE_TABLE[row_idx][col_idx];
                assert!(ulp_close(want, got),
                    "LWC quantile drift at regime={regime} tau={tau}: want={want} got={got}");
            }
        }

        // c-bump schedule.
        for (i, tau) in TARGET_ANCHORS.iter().enumerate() {
            let key = format!("{tau:.2}");
            let want = v["c_bump_schedule"][&key].as_f64().expect("number");
            let got = LWC_C_BUMP_SCHEDULE[i];
            assert!(ulp_close(want, got),
                "LWC c_bump drift at tau={tau}: want={want} got={got}");
        }

        // δ schedule (identically zero — hard-assert exact).
        for (i, tau) in TARGET_ANCHORS.iter().enumerate() {
            let key = format!("{tau:.2}");
            let want = v["delta_shift_schedule"][&key].as_f64().expect("number");
            let got = LWC_DELTA_SHIFT_SCHEDULE[i];
            assert_eq!(want, 0.0, "LWC δ in sidecar is non-zero at tau={tau}: {want}");
            assert_eq!(got, 0.0);
        }
    }
}
