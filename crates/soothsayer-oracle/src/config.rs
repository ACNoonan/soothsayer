//! Oracle-serving configuration constants.
//!
//! These values MUST match `src/soothsayer/oracle.py` exactly — the Rust
//! Oracle is a byte-for-byte port of the Python reference.

use std::collections::HashMap;

/// Per-regime forecaster selection. Evidence-driven per v1b:
/// - normal, long_weekend → F1_emp_regime (tighter via the empirical-quantile
///   + log-log regime model)
/// - high_vol → F0_stale (Gaussian band is more efficient at matched realized
///   coverage because F1 stretches to cover)
///
/// See `reports/v1b_decision.md` §"Per-regime OOS breakdown" for evidence.
pub const DEFAULT_FORECASTER: &str = "F1_emp_regime";

pub fn default_regime_forecaster() -> HashMap<&'static str, &'static str> {
    HashMap::from([
        ("normal", "F1_emp_regime"),
        ("long_weekend", "F1_emp_regime"),
        ("high_vol", "F0_stale"),
    ])
}

/// Empirical calibration buffer (per-target schedule, 2026-04-25).
///
/// An earlier scalar default (0.025) was tuned for τ=0.95 only. After the
/// default operating point moved to τ=0.85 (per the protocol-compare EL
/// analysis), the τ=0.95-tuned scalar under-corrected at τ=0.85
/// (Kupiec p_uc=0.014 reject). The conformal-comparison study
/// (`reports/v1b_conformal_comparison.md`) confirmed no off-the-shelf
/// conformal alternative outperformed the heuristic, so the fix is
/// per-target tuning of the heuristic itself.
///
/// Buffers below are the smallest values satisfying realized ≥ τ − 0.005,
/// Kupiec p_uc > 0.10, Christoffersen p_ind > 0.05 on the OOS 2023+ slice
/// (`reports/v1b_buffer_tune.md`). Off-grid targets linearly interpolate
/// between adjacent anchors.
pub fn default_buffer_by_target() -> Vec<(f64, f64)> {
    vec![
        (0.68, 0.045),
        (0.85, 0.045),
        (0.95, 0.020),
        (0.99, 0.005),
    ]
}

/// Linear-interpolate the per-target buffer schedule for a consumer's
/// requested target. Targets below the smallest anchor use the smallest
/// anchor's buffer; targets above the largest anchor use the largest's.
/// Schedule is assumed sorted by target ascending.
pub fn buffer_for_target(target: f64, schedule: &[(f64, f64)]) -> f64 {
    if schedule.is_empty() {
        return CALIBRATION_BUFFER_PCT;
    }
    if target <= schedule[0].0 {
        return schedule[0].1;
    }
    if target >= schedule[schedule.len() - 1].0 {
        return schedule[schedule.len() - 1].1;
    }
    for w in schedule.windows(2) {
        let (lo_t, lo_b) = w[0];
        let (hi_t, hi_b) = w[1];
        if lo_t <= target && target <= hi_t {
            let frac = (target - lo_t) / (hi_t - lo_t);
            return lo_b + frac * (hi_b - lo_b);
        }
    }
    schedule[schedule.len() - 1].1
}

/// Scalar fallback retained for callers that pass a single number (legacy
/// API and ablation A/B). In serving-time use, the per-target schedule
/// above is the primary mechanism.
pub const CALIBRATION_BUFFER_PCT: f64 = 0.025;

/// The maximum claimed coverage at which the bounds table has data. We cannot
/// buffer past this because the fine grid stops at 0.995.
pub const MAX_SERVED_TARGET: f64 = 0.995;

/// Minimum observations required in a per-symbol surface bucket before we use
/// it; below this we fall back to the pooled surface.
pub const MIN_OBS: u32 = 30;
