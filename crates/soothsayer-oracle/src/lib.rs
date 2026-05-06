//! Soothsayer Oracle — Rust serving layer (M5 reference + M6 LWC deployed).
//!
//! Loads the Python-produced artefacts and serves calibrated price bands
//! via per-regime conformal quantile lookup. Two forecasters share the
//! crate:
//!
//!   - **M5 / Mondrian** — the reference path live on-chain
//!     (`forecaster_code = 2`). Per-regime split-conformal on raw relative
//!     residuals + OOS-fit `c(τ)` + walk-forward `δ(τ)`. 20 deployment
//!     scalars. Reads `data/processed/mondrian_artefact_v2.parquet`.
//!
//!   - **M6 / LWC (deployed)** — locally-weighted Mondrian split-conformal
//!     on standardised residuals (rescaled by per-symbol pre-Friday EWMA
//!     σ̂, half-life 8 weekends) + near-identity OOS-fit `c(τ)` + zero
//!     walk-forward shift. 16 deployment scalars + the σ̂ rule. Reads
//!     `data/processed/lwc_artefact_v1.parquet`. On-chain wire-format
//!     slot reserved as `forecaster_code = 3`.
//!
//! **Reference implementation:** `src/soothsayer/oracle.py`. This crate's
//! [`Oracle::fair_value`] must produce byte-for-byte identical output to
//! the Python `Oracle.fair_value` (M5) and `Oracle.fair_value_lwc` (M6)
//! when given the same inputs and the same artefact. See paper 1 §4 / §7
//! and `reports/methodology_history.md`.

pub mod config;
pub mod error;
pub mod oracle;
pub mod types;

pub use config::{
    c_bump_for_target, delta_shift_for_target, lwc_c_bump_for, lwc_delta_shift_for,
    lwc_regime_quantile_for, regime_quantile_for, C_BUMP_SCHEDULE, DEFAULT_TARGET_COVERAGE,
    DELTA_SHIFT_SCHEDULE, LWC_C_BUMP_SCHEDULE, LWC_DELTA_SHIFT_SCHEDULE, LWC_FORECASTER,
    LWC_REGIME_QUANTILE_TABLE, MAX_SERVED_TARGET, MIN_SERVED_TARGET, MONDRIAN_FORECASTER, REGIMES,
    REGIME_QUANTILE_TABLE, SIGMA_HAT_HL_WEEKENDS, SIGMA_HAT_MIN, TARGET_ANCHORS,
};
pub use error::{Error, Result};
pub use oracle::{Oracle, DEFAULT_FORECASTER};
pub use types::{Forecaster, PricePoint, PricePointDiagnostics, Regime};
