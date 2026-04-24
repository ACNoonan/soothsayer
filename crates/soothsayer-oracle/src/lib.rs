//! Soothsayer Oracle — Rust serving layer.
//!
//! Loads the Python-produced calibration artifacts (`v1b_bounds.parquet`,
//! `v1b_calibration_surface.csv`, `v1b_calibration_surface_pooled.csv`) and
//! serves calibrated price bands via the hybrid per-regime forecaster +
//! empirical-buffer inversion.
//!
//! **Reference implementation:** `src/soothsayer/oracle.py`. This crate's
//! [`Oracle::fair_value`] must produce byte-for-byte identical output to the
//! Python `Oracle.fair_value` when given the same inputs and the same on-disk
//! artifacts.
//!
//! Architecture (v1b, 2026-04-24):
//!
//! 1. **Raw forecasters** (F1_emp_regime, F0_stale) produce bounds at a fine
//!    claimed-coverage grid. Both already live in the bounds table.
//! 2. **Calibration surface** maps (symbol, regime, forecaster, claimed) →
//!    empirical realized coverage. Built by the Python backtest.
//! 3. **Hybrid per-regime forecaster selection** — `REGIME_FORECASTER` picks
//!    F1 in normal/long_weekend, F0 in high_vol where F1 stretches and F0's
//!    already-wide Gaussian is efficient.
//! 4. **Empirical calibration buffer** — the consumer-requested target is
//!    bumped by 2.5pp before surface inversion to close the ~3pp OOS gap
//!    measured in `reports/v1b_hybrid_validation.md`.

pub mod config;
pub mod error;
pub mod oracle;
pub mod surface;
pub mod types;

pub use config::{default_regime_forecaster, CALIBRATION_BUFFER_PCT, DEFAULT_FORECASTER, MAX_SERVED_TARGET};
pub use error::{OracleError, OracleResult};
pub use oracle::Oracle;
pub use surface::{CalibrationSurface, PooledSurface};
pub use types::{CalibrationDiag, PricePoint, Regime};
