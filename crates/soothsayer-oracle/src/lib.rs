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
    c_bump_for_target, delta_shift_for_target, regime_quantile_for, C_BUMP_SCHEDULE,
    DEFAULT_TARGET_COVERAGE, DELTA_SHIFT_SCHEDULE, MAX_SERVED_TARGET, MIN_SERVED_TARGET,
    MONDRIAN_FORECASTER, REGIMES, REGIME_QUANTILE_TABLE, TARGET_ANCHORS,
};
pub use error::{Error, Result};
pub use oracle::Oracle;
pub use types::{PricePoint, PricePointDiagnostics, Regime};
