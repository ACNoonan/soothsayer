//! Soothsayer Oracle — Rust serving layer (Mondrian / M5 deployment).
//!
//! Loads the Python-produced Mondrian artefact
//! (`data/processed/mondrian_artefact_v2.parquet`) and serves calibrated
//! price bands via per-regime conformal quantile + δ-shifted c(τ) bump.
//!
//! **Reference implementation:** `src/soothsayer/oracle.py`. This crate's
//! [`Oracle::fair_value`] must produce byte-for-byte identical output to the
//! Python `Oracle.fair_value` when given the same inputs and the same
//! artefact. Twenty deployment scalars (12 trained per-regime quantiles,
//! 4 OOS-fit `c(τ)` bumps, 4 walk-forward-fit `δ(τ)` shifts) live in
//! [`config`].
//!
//! See paper 1 §7.7 and `reports/methodology_history.md` (M5 entry) for the
//! methodology validation that established these constants.

pub mod config;
pub mod error;
pub mod oracle;
pub mod types;

pub use config::{
    c_bump_for_target, delta_shift_for_target, lending_c_bump_for, lending_class_quantile_for,
    lending_delta_shift_for, regime_quantile_for, symbol_class_for, C_BUMP_SCHEDULE,
    DEFAULT_TARGET_COVERAGE, DELTA_SHIFT_SCHEDULE, LENDING_CLASSES, LENDING_C_BUMP_SCHEDULE,
    LENDING_DELTA_SHIFT_SCHEDULE, LENDING_FORECASTER, LENDING_QUANTILE_TABLE, MAX_SERVED_TARGET,
    MIN_SERVED_TARGET, MONDRIAN_FORECASTER, REGIMES, REGIME_QUANTILE_TABLE, SYMBOL_CLASS_MAP,
    TARGET_ANCHORS,
};
pub use error::{Error, Result};
pub use oracle::{Oracle, DEFAULT_PROFILE};
pub use types::{PricePoint, PricePointDiagnostics, Profile, Regime};
