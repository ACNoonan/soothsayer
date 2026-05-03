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
}
