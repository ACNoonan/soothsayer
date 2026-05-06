//! Dual-forecaster Oracle implementation — Rust port of
//! `src/soothsayer/oracle.py`.
//!
//! Supports two architectures:
//!
//!   - [`Forecaster::Mondrian`] (M5; reference path) — per-regime split-
//!     conformal on raw relative residuals + OOS-fit `c(τ)` + walk-forward
//!     `δ(τ)` shift. Reads `data/processed/mondrian_artefact_v2.parquet`
//!     for the per-Friday `(symbol, fri_ts, fri_close, point, regime_pub)`
//!     tuple. Live on-chain (`forecaster_code = 2`).
//!
//!   - [`Forecaster::Lwc`] (M6; deployed) — per-regime split-conformal on
//!     standardised residuals (rescaled by per-symbol pre-Friday EWMA σ̂)
//!     + near-identity OOS-fit `c(τ)` + zero walk-forward shift. Reads
//!     `data/processed/lwc_artefact_v1.parquet` which adds a
//!     `sigma_hat_sym_pre_fri` column to the same per-Friday schema.
//!     On-chain wire-format slot reserved as `forecaster_code = 3`.

use chrono::NaiveDate;
use polars::prelude::*;
use std::path::Path;

use crate::config::{
    c_bump_for_target, delta_shift_for_target, lwc_c_bump_for, lwc_delta_shift_for,
    lwc_regime_quantile_for, regime_quantile_for, LWC_FORECASTER, MAX_SERVED_TARGET,
    MIN_SERVED_TARGET, MONDRIAN_FORECASTER,
};
use crate::error::{Error, Result};
use crate::types::{Forecaster, PricePoint, PricePointDiagnostics, Regime};

/// Default forecaster. Matches the Python `DEFAULT_PROFILE` in
/// `src/soothsayer/oracle.py` — the M6 LWC path is deployed.
pub const DEFAULT_FORECASTER: Forecaster = Forecaster::Lwc;

/// One row of the per-Friday artefact for a given (symbol, fri_ts). The
/// `sigma_hat_sym_pre_fri` column is `Some` for LWC artefacts and `None`
/// for Mondrian (the M5 reference path doesn't need it).
#[derive(Clone, Debug)]
struct ArtefactRow {
    symbol: String,
    fri_ts: NaiveDate,
    regime_pub: String,
    fri_close: f64,
    point: f64,
    sigma_hat_sym_pre_fri: Option<f64>,
}

/// The Soothsayer Oracle — dual-forecaster split-conformal serving layer.
///
/// Construct via [`Oracle::load`] (default = LWC) or
/// [`Oracle::load_with_forecaster`], then call [`Oracle::fair_value`]. The
/// served band depends on the forecaster selected at load time:
///
/// ```text
///   τ' = τ + δ(τ)            (δ ≡ 0 under LWC; M5 carries a non-zero schedule)
///   q_eff = c(τ') · q_r(τ')         under Mondrian
///   q_eff = c(τ') · q_r(τ') · σ̂_s(t)  under LWC
///
///   lower = point · (1 - q_eff),     upper = point · (1 + q_eff)
/// ```
///
/// where `point = fri_close · (1 + factor_ret)` is the §4.1 factor-adjusted
/// Friday close (precomputed at artefact-build time). Schedules `q_r(·)`,
/// `c(·)`, `δ(·)` are the per-forecaster constants in [`crate::config`].
pub struct Oracle {
    rows: Vec<ArtefactRow>,
    forecaster: Forecaster,
}

impl Oracle {
    /// Load the deployed M6 LWC artefact at the standard path.
    pub fn load(artefact_path: &Path) -> Result<Self> {
        Self::load_with_forecaster(artefact_path, DEFAULT_FORECASTER)
    }

    /// Load the artefact at `artefact_path` under the given forecaster.
    /// For [`Forecaster::Mondrian`] pass the M5 reference parquet
    /// (`data/processed/mondrian_artefact_v2.parquet`); for
    /// [`Forecaster::Lwc`] pass the deployed M6 parquet
    /// (`data/processed/lwc_artefact_v1.parquet`).
    pub fn load_with_forecaster(artefact_path: &Path, forecaster: Forecaster) -> Result<Self> {
        let rows = load_artefact(artefact_path, forecaster)?;
        Ok(Self { rows, forecaster })
    }

    pub fn forecaster(&self) -> Forecaster {
        self.forecaster
    }

    /// Serve a calibrated band.
    pub fn fair_value(
        &self,
        symbol: &str,
        as_of: NaiveDate,
        target_coverage: f64,
    ) -> Result<PricePoint> {
        let row = self
            .rows
            .iter()
            .find(|r| r.symbol == symbol && r.fri_ts == as_of)
            .ok_or_else(|| Error::NoBounds {
                symbol: symbol.to_string(),
                as_of,
            })?;

        let regime = Regime::from_str(&row.regime_pub)
            .ok_or_else(|| Error::UnknownRegime(row.regime_pub.clone()))?;

        let tau_clipped = target_coverage.clamp(MIN_SERVED_TARGET, MAX_SERVED_TARGET);

        // Per-forecaster outputs: (delta, served_target, c_bump, q_eff,
        // lower, upper, q_regime_mondrian, q_regime_lwc, sigma_hat,
        // forecaster_str).
        let (
            delta, served_target, c_bump, q_eff, lower, upper,
            q_regime_mondrian, q_regime_lwc, sigma_hat, forecaster_str,
        ) = match self.forecaster {
            Forecaster::Mondrian => {
                // M5: point-relative band, conformity score |mon - point| / fri_close
                // q_eff is the unitless c · q_r; half = q_eff · point.
                let delta = delta_shift_for_target(tau_clipped);
                let served_target = (tau_clipped + delta).min(MAX_SERVED_TARGET);
                let c_bump = c_bump_for_target(served_target);
                let q_regime = regime_quantile_for(&row.regime_pub, served_target);
                let q_eff = c_bump * q_regime;
                let lower = row.point * (1.0 - q_eff);
                let upper = row.point * (1.0 + q_eff);
                (
                    delta, served_target, c_bump, q_eff, lower, upper,
                    Some(q_regime), None, None, MONDRIAN_FORECASTER,
                )
            }
            Forecaster::Lwc => {
                // M6: fri_close-relative band, conformity score
                // |mon - point| / (fri_close · σ̂). q_eff is the unitless
                // c · q_r^LWC (no σ̂ inside); half = q_eff · σ̂ · fri_close.
                // Matches Python `Oracle.fair_value_lwc` in
                // `src/soothsayer/oracle.py` byte-for-byte.
                let delta = lwc_delta_shift_for(tau_clipped);
                let served_target = (tau_clipped + delta).min(MAX_SERVED_TARGET);
                let c_bump = lwc_c_bump_for(served_target);
                let q_regime = lwc_regime_quantile_for(&row.regime_pub, served_target);
                let sigma_hat = row.sigma_hat_sym_pre_fri.ok_or_else(|| {
                    Error::Integrity(format!(
                        "LWC fair_value requires sigma_hat_sym_pre_fri on the artefact \
                         row for symbol={symbol} fri_ts={as_of}; got None"
                    ))
                })?;
                if !(sigma_hat > 0.0 && sigma_hat.is_finite()) {
                    return Err(Error::Integrity(format!(
                        "LWC artefact row has non-positive sigma_hat_sym_pre_fri ({sigma_hat}) \
                         for symbol={symbol} as_of={as_of}; warm-up filter should have excluded \
                         this row — check the build step"
                    )));
                }
                let q_eff = c_bump * q_regime;
                let half = q_eff * sigma_hat * row.fri_close;
                let lower = row.point - half;
                let upper = row.point + half;
                (
                    delta, served_target, c_bump, q_eff, lower, upper,
                    None, Some(q_regime), Some(sigma_hat), LWC_FORECASTER,
                )
            }
        };

        let sharpness_bps = if row.fri_close == 0.0 {
            0.0
        } else {
            (upper - lower) / 2.0 / row.fri_close * 1e4
        };
        let half_width_bps = PricePoint::compute_half_width_bps(row.point, lower, upper);

        Ok(PricePoint {
            symbol: symbol.to_string(),
            as_of,
            target_coverage,
            calibration_buffer_applied: delta,
            claimed_coverage_served: served_target,
            point: row.point,
            lower,
            upper,
            regime,
            forecaster_used: forecaster_str.to_string(),
            sharpness_bps,
            half_width_bps,
            forecaster: self.forecaster,
            diagnostics: PricePointDiagnostics {
                fri_close: row.fri_close,
                served_target,
                c_bump,
                q_eff,
                q_regime: q_regime_mondrian,
                q_regime_lwc,
                sigma_hat_sym_pre_fri: sigma_hat,
            },
        })
    }

    /// List every (symbol, fri_ts, regime) triple in the artefact.
    pub fn list_available(&self, symbol: Option<&str>) -> Vec<(String, NaiveDate, String)> {
        use std::collections::HashSet;
        let mut seen: HashSet<(String, NaiveDate)> = HashSet::new();
        let mut out = Vec::new();
        for r in &self.rows {
            if let Some(s) = symbol {
                if r.symbol != s {
                    continue;
                }
            }
            let key = (r.symbol.clone(), r.fri_ts);
            if seen.insert(key) {
                out.push((r.symbol.clone(), r.fri_ts, r.regime_pub.clone()));
            }
        }
        out.sort_by(|a, b| a.1.cmp(&b.1).then(a.0.cmp(&b.0)));
        out
    }
}

fn load_artefact(path: &Path, forecaster: Forecaster) -> Result<Vec<ArtefactRow>> {
    let mut file = std::fs::File::open(path)?;
    let df = ParquetReader::new(&mut file).finish()?;

    let artefact_label = match forecaster {
        Forecaster::Mondrian => "mondrian_artefact_v2",
        Forecaster::Lwc => "lwc_artefact_v1",
    };

    let required = ["symbol", "fri_ts", "regime_pub", "fri_close", "point"];
    for col in &required {
        df.column(col).map_err(|_| Error::MissingColumn {
            column: (*col).into(),
            artifact: artefact_label.into(),
        })?;
    }

    // sigma_hat_sym_pre_fri is required for LWC artefacts; absent on Mondrian.
    if matches!(forecaster, Forecaster::Lwc) {
        df.column("sigma_hat_sym_pre_fri")
            .map_err(|_| Error::MissingColumn {
                column: "sigma_hat_sym_pre_fri".into(),
                artifact: artefact_label.into(),
            })?;
    }

    let sym_col = df.column("symbol")?.str()?;
    let reg_col = df.column("regime_pub")?.str()?;
    let fri_close_col = df.column("fri_close")?.f64()?;
    let point_col = df.column("point")?.f64()?;
    let sigma_col = if matches!(forecaster, Forecaster::Lwc) {
        Some(df.column("sigma_hat_sym_pre_fri")?.f64()?.clone())
    } else {
        None
    };

    let fri_ts_col = df.column("fri_ts")?;
    let fri_ts_dates: Vec<Option<NaiveDate>> = if matches!(fri_ts_col.dtype(), DataType::Date) {
        fri_ts_col
            .date()?
            .into_iter()
            .map(|d| d.map(date32_to_naive_date))
            .collect()
    } else {
        fri_ts_col
            .str()?
            .into_iter()
            .map(|s| s.and_then(|x| NaiveDate::parse_from_str(x, "%Y-%m-%d").ok()))
            .collect()
    };

    let n = df.height();
    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        let fri_ts = match fri_ts_dates[i] {
            Some(d) => d,
            None => continue,
        };
        let sigma_hat_sym_pre_fri = sigma_col.as_ref().and_then(|c| c.get(i));
        out.push(ArtefactRow {
            symbol: sym_col.get(i).unwrap_or("").to_string(),
            fri_ts,
            regime_pub: reg_col.get(i).unwrap_or("").to_string(),
            fri_close: fri_close_col.get(i).unwrap_or(f64::NAN),
            point: point_col.get(i).unwrap_or(f64::NAN),
            sigma_hat_sym_pre_fri,
        });
    }
    Ok(out)
}

fn date32_to_naive_date(days: i32) -> NaiveDate {
    NaiveDate::from_ymd_opt(1970, 1, 1)
        .unwrap()
        .checked_add_days(chrono::Days::new(days as u64))
        .unwrap_or_else(|| NaiveDate::from_ymd_opt(1970, 1, 1).unwrap())
}
