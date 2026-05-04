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

/// Serving profile. Both profiles share the M5 Mondrian architecture and
/// wire format; they differ only in the conformal cell axis (per-class
/// for Lending, per-regime for AMM) and the band formula (fri_close-
/// relative for Lending, point-relative for AMM-legacy).
///
/// Discriminant values match the on-chain `profile_code` byte that A4
/// adds to `PriceUpdate`: `Lending = 1`, `Amm = 2`. `0` is reserved for
/// "legacy M5 single-profile receipt" — not produced by this crate.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Profile {
    Lending = 1,
    Amm = 2,
}

impl Profile {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Lending => "lending",
            Self::Amm => "amm",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "lending" => Some(Self::Lending),
            "amm" => Some(Self::Amm),
            _ => None,
        }
    }

    /// Borsh-codable byte. Phase A4 wires this into `PriceUpdate.profile_code`.
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
/// Field semantics under the dual-profile architecture (M5 + M6b2):
///   - `target_coverage`: what the consumer asked for (τ).
///   - `calibration_buffer_applied`: δ(τ) — the walk-forward τ-shift, the
///     structural successor to v1's `BUFFER_BY_TARGET` schedule.
///   - `claimed_coverage_served`: τ + δ(τ), the served band's claim.
///   - `forecaster_used`: "mondrian" under both M5 / M6b2 profiles (legacy
///     field; on the wire this maps to FORECASTER_MONDRIAN = 2).
///     Code 3 is reserved for FORECASTER_LWC (the M6 Locally-Weighted
///     Conformal serving path). The Python sibling `Oracle.fair_value_lwc()`
///     ships ahead of the Rust port; the Rust LWC implementation lands in
///     Phase 5 of `M6_REFACTOR.md` (gated on Adam's hand-off). Wire-format
///     invariance: existing M5 consumers must decode an LWC PriceUpdate
///     account without crashing — only the `forecaster_code` byte changes.
///   - `profile`: which conformal cell axis was used. Lending → per-class,
///     AMM → per-regime. Wire-encoded as the `profile_code` byte (A4).
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
    pub profile: Profile,
    pub diagnostics: PricePointDiagnostics,
}

/// Per-Friday diagnostics. Common fields (fri_close, served_target, c_bump,
/// q_eff) are populated under both profiles; the cell-specific fields below
/// are populated only under the matching profile so the JSON shape mirrors
/// `src/soothsayer/oracle.py`'s diagnostics dict on each side.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PricePointDiagnostics {
    pub fri_close: f64,
    /// τ + δ(τ); the τ' that the conformal lookup actually used.
    pub served_target: f64,
    /// `c(τ')`, the multiplicative OOS-fit bump applied to the trained quantile.
    pub c_bump: f64,
    /// `c(τ') · b(cell, τ')`, the effective relative half-width in residual units.
    pub q_eff: f64,
    /// AMM profile only: `q_r(τ')`, the per-regime trained conformal quantile.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub q_regime: Option<f64>,
    /// Lending profile only: the symbol's class label (e.g. "equity_index").
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub symbol_class: Option<String>,
    /// Lending profile only: `b(class, τ')`, the per-class trained quantile.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub b_class: Option<f64>,
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
