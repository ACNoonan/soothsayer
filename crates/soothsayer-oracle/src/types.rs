//! Public types for the Oracle serving layer.

use chrono::NaiveDate;
use serde::{Deserialize, Serialize};

/// Pre-publish regime, derived from gap_days + VIX at Friday close.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Regime {
    Normal,
    LongWeekend,
    HighVol,
}

impl Regime {
    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "normal" => Some(Self::Normal),
            "long_weekend" => Some(Self::LongWeekend),
            "high_vol" => Some(Self::HighVol),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Normal => "normal",
            Self::LongWeekend => "long_weekend",
            Self::HighVol => "high_vol",
        }
    }
}

/// Diagnostics returned alongside a calibration surface inversion.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CalibrationDiag {
    /// Which surface was consulted: "per_symbol" or "pooled".
    pub calibration: String,
    /// Bracketing claim levels used for the interpolation, if applicable.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bracketed: Option<(f64, f64)>,
    /// Clip direction if the target was outside the grid ("above" or "below").
    #[serde(skip_serializing_if = "Option::is_none")]
    pub clipped: Option<String>,
    /// Symbol's n_obs (when per_symbol fell back to pooled).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub symbol_n: Option<u32>,
}

/// The Soothsayer oracle read. Stable fields are what protocols integrate
/// against; `diagnostics` is human-consumable metadata.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PricePoint {
    pub symbol: String,
    pub as_of: NaiveDate,
    /// What the consumer asked for.
    pub target_coverage: f64,
    /// The OOS buffer added to target before inversion.
    pub calibration_buffer_applied: f64,
    /// The claimed quantile we actually served.
    pub claimed_coverage_served: f64,
    pub point: f64,
    pub lower: f64,
    pub upper: f64,
    pub regime: Regime,
    /// Which forecaster's band we served — hybrid selection receipt.
    pub forecaster_used: String,
    pub sharpness_bps: f64,
    pub half_width_bps: f64,
    pub diagnostics: PricePointDiagnostics,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PricePointDiagnostics {
    pub fri_close: f64,
    pub nearest_grid: f64,
    pub buffered_target: f64,
    pub requested_claimed_pre_clip: f64,
    /// The regime→forecaster policy in effect at serve time.
    pub regime_forecaster_policy: std::collections::BTreeMap<String, String>,
    pub calibration: String, // "per_symbol" | "pooled"
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bracketed: Option<(f64, f64)>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub clipped: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub realized_min: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub realized_max: Option<f64>,
}

impl PricePoint {
    pub fn compute_half_width_bps(point: f64, lower: f64, upper: f64) -> f64 {
        if point == 0.0 {
            0.0
        } else {
            (upper - lower) / 2.0 / point * 1e4
        }
    }
}
