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

/// Serving forecaster — selects the architecture used to compute the band.
///
/// Both `Mondrian` (the M5 per-regime split-conformal reference path) and
/// `Lwc` (the M6 deployed locally-weighted Mondrian conformal path) share
/// the band formula `[point * (1 ± q_eff), ...]` and the on-chain wire
/// format. They differ in how `q_eff` is constructed:
///
/// - Mondrian:   `q_eff = c(τ) · q_r(τ)`                      (per-regime quantile on raw residuals)
/// - Lwc (M6):   `q_eff = c(τ) · q_r(τ) · σ̂_s(t)`             (per-regime quantile on standardised residuals, rescaled by per-symbol pre-Friday σ̂)
///
/// On-chain wire `forecaster_code`: Mondrian = 2, Lwc = 3.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Forecaster {
    Mondrian = 2,
    Lwc = 3,
}

impl Forecaster {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Mondrian => "mondrian",
            Self::Lwc => "lwc",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "mondrian" => Some(Self::Mondrian),
            "lwc" => Some(Self::Lwc),
            _ => None,
        }
    }

    /// Borsh-codable wire byte. Matches `soothsayer_consumer::FORECASTER_*`.
    pub fn code(&self) -> u8 {
        *self as u8
    }
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
/// Field semantics:
///   - `target_coverage`: what the consumer asked for (τ).
///   - `calibration_buffer_applied`: δ(τ) — the walk-forward τ-shift. Under
///     M6 (LWC) this is identically zero; under M5 (Mondrian) it carries
///     the legacy `BUFFER_BY_TARGET` schedule.
///   - `claimed_coverage_served`: τ + δ(τ); the served band's claim.
///   - `forecaster_used`: "mondrian" (M5) or "lwc" (M6). On the wire this
///     maps to `forecaster_code = 2` (Mondrian; live on-chain) or `= 3`
///     (Lwc; on-chain slot reserved pending Rust port + publish enablement).
///     Wire-format invariance: existing consumers must decode an Lwc
///     PriceUpdate account without crashing — only the `forecaster_code`
///     byte changes; `point`, `lower`, `upper` semantics are unchanged.
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
    pub forecaster: Forecaster,
    pub diagnostics: PricePointDiagnostics,
}

/// Per-Friday diagnostics. Common fields (fri_close, served_target, c_bump,
/// q_eff) are populated under both forecasters; per-forecaster cell fields
/// are populated only under the matching forecaster so the JSON shape
/// mirrors Python's `Oracle.fair_value` (M5) / `Oracle.fair_value_lwc`
/// (M6) diagnostics dict on each side.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PricePointDiagnostics {
    pub fri_close: f64,
    /// τ + δ(τ); the τ' that the conformal lookup actually used.
    pub served_target: f64,
    /// `c(τ')`, the multiplicative OOS-fit bump applied to the trained quantile.
    pub c_bump: f64,
    /// `c(τ') · q_r(τ')` — the unitless effective quantile. Under M6 the
    /// half-width adds a factor of σ̂_s(t) (`half = q_eff · σ̂ · fri_close`,
    /// fri_close-relative band); under M5 it's `half = q_eff · point`
    /// (point-relative band). The same diagnostic field carries both.
    pub q_eff: f64,
    /// M5 / Mondrian only: `q_r(τ')`, per-regime trained conformal quantile
    /// on raw relative residuals. `None` for M6 reads.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub q_regime: Option<f64>,
    /// M6 / LWC only: `q_r^LWC(τ')`, per-regime trained conformal quantile
    /// on standardised residuals. `None` for M5 reads. Field name matches
    /// Python's `q_regime_lwc` diagnostic key.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub q_regime_lwc: Option<f64>,
    /// M6 / LWC only: per-symbol pre-Friday EWMA σ̂_s(t) read from the
    /// artefact parquet's `sigma_hat_sym_pre_fri` column. `None` for M5.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sigma_hat_sym_pre_fri: Option<f64>,
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
