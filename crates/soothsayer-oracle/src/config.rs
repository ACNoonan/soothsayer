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

/// Empirical calibration buffer. Shifts consumer-requested target upward by
/// this amount before surface inversion, to close the measured OOS gap. 0.025
/// is the median OOS gap across target levels from the hybrid validation
/// (`reports/v1b_hybrid_validation.md`).
///
/// A production deployment would re-measure this on each surface rebuild.
pub const CALIBRATION_BUFFER_PCT: f64 = 0.025;

/// The maximum claimed coverage at which the bounds table has data. We cannot
/// buffer past this because the fine grid stops at 0.995.
pub const MAX_SERVED_TARGET: f64 = 0.995;

/// Minimum observations required in a per-symbol surface bucket before we use
/// it; below this we fall back to the pooled surface.
pub const MIN_OBS: u32 = 30;
