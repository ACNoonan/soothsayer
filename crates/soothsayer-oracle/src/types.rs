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

/// The Soothsayer oracle read. Stable fields are what protocols integrate
/// against; `diagnostics` is human-consumable metadata.
///
/// Field semantics under M5 (Mondrian split-conformal by regime, paper 1 §7.7):
///   - `target_coverage`: what the consumer asked for (τ).
///   - `calibration_buffer_applied`: δ(τ) — the OOS-fit τ-shift, the
///     structural successor to v1's `BUFFER_BY_TARGET` schedule.
///   - `claimed_coverage_served`: τ + δ(τ), the served band's claim.
///   - `forecaster_used`: always "mondrian" under M5 (legacy field; on the
///     wire this maps to FORECASTER_MONDRIAN = 2).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PricePoint {
    pub symbol: String,
    pub as_of: NaiveDate,
    pub target_coverage: f64,
    pub calibration_buffer_applied: f64,
    pub claimed_coverage_served: f64,
    pub point: f64,
    pub lower: f64,
    pub upper: f64,
    pub regime: Regime,
    pub forecaster_used: String,
    pub sharpness_bps: f64,
    pub half_width_bps: f64,
    pub diagnostics: PricePointDiagnostics,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PricePointDiagnostics {
    pub fri_close: f64,
    /// τ + δ(τ); the τ' that the conformal lookup actually used.
    pub served_target: f64,
    /// `c(τ')`, the multiplicative OOS-fit bump applied to the trained quantile.
    pub c_bump: f64,
    /// `q_r(τ')`, the per-regime trained conformal quantile.
    pub q_regime: f64,
    /// `c(τ') · q_r(τ')`, the effective relative half-width in residual units.
    pub q_eff: f64,
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
