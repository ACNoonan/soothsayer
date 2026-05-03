//! Dual-profile (M5 + M6b2) Oracle implementation — Rust port of
//! `src/soothsayer/oracle.py`.

use chrono::NaiveDate;
use polars::prelude::*;
use std::path::Path;

use crate::config::{
    c_bump_for_target, delta_shift_for_target, lending_c_bump_for,
    lending_class_quantile_for, lending_delta_shift_for, regime_quantile_for, symbol_class_for,
    MAX_SERVED_TARGET, MIN_SERVED_TARGET, MONDRIAN_FORECASTER,
};
use crate::error::{Error, Result};
use crate::types::{PricePoint, PricePointDiagnostics, Profile, Regime};

/// Default serving profile. Matches the Python `DEFAULT_PROFILE` in
/// `src/soothsayer/oracle.py` — Lending is the deployable v3 winner.
pub const DEFAULT_PROFILE: Profile = Profile::Lending;

/// One row of the Mondrian artefact for a given (symbol, fri_ts).
#[derive(Clone, Debug)]
struct ArtefactRow {
    symbol: String,
    fri_ts: NaiveDate,
    regime_pub: String,
    fri_close: f64,
    point: f64,
}

/// The Soothsayer Oracle — dual-profile Mondrian split-conformal.
///
/// Construct via [`Oracle::load`], then call [`Oracle::fair_value`]. The
/// served band depends on the profile selected at load time:
///
/// ```text
///   τ' = τ + δ(τ)         (profile-specific δ schedule)
///   q  = c(τ') · b_cell(τ')   (cell axis: regime for AMM, symbol_class for Lending)
///
///   AMM (legacy M5):     lower = point · (1 - q),     upper = point · (1 + q)
///   Lending (M6b2):      lower = point - q · fri_close,
///                        upper = point + q · fri_close
/// ```
///
/// where `point = fri_close · (1 + factor_ret)` is the §7.4 factor-
/// adjusted Friday close (precomputed at artefact-build time). Schedules
/// `b_cell(·)`, `c(·)`, `δ(·)` are the per-profile constants in
/// [`crate::config`].
pub struct Oracle {
    rows: Vec<ArtefactRow>,
    profile: Profile,
}

impl Oracle {
    /// Load the Mondrian artefact under the default profile (Lending).
    pub fn load(artefact_path: &Path) -> Result<Self> {
        Self::load_with_profile(artefact_path, DEFAULT_PROFILE)
    }

    /// Load the Mondrian artefact (`data/processed/mondrian_artefact_v2.parquet`
    /// or whatever path is supplied) under the given profile.
    pub fn load_with_profile(artefact_path: &Path, profile: Profile) -> Result<Self> {
        let rows = load_artefact(artefact_path)?;
        Ok(Self { rows, profile })
    }

    pub fn profile(&self) -> Profile {
        self.profile
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

        let (delta, served_target, c_bump, q_eff, lower, upper, diagnostics) = match self.profile {
            Profile::Lending => {
                let delta = lending_delta_shift_for(tau_clipped);
                let served_target = (tau_clipped + delta).min(MAX_SERVED_TARGET);
                let c_bump = lending_c_bump_for(served_target);
                let cls = symbol_class_for(symbol)
                    .ok_or_else(|| Error::UnknownSymbolClass(symbol.to_string()))?;
                let b = lending_class_quantile_for(cls, served_target)
                    .ok_or_else(|| Error::UnknownSymbolClass(cls.to_string()))?;
                let q_eff = c_bump * b;
                // Band relative to fri_close — exact match to the conformity
                // score |mon_open - point| / fri_close used to fit b.
                let lower = row.point - q_eff * row.fri_close;
                let upper = row.point + q_eff * row.fri_close;
                let diag = PricePointDiagnostics {
                    fri_close: row.fri_close,
                    served_target,
                    c_bump,
                    q_eff,
                    q_regime: None,
                    symbol_class: Some(cls.to_string()),
                    b_class: Some(b),
                };
                (delta, served_target, c_bump, q_eff, lower, upper, diag)
            }
            Profile::Amm => {
                let delta = delta_shift_for_target(tau_clipped);
                let served_target = (tau_clipped + delta).min(MAX_SERVED_TARGET);
                let c_bump = c_bump_for_target(served_target);
                let q_regime = regime_quantile_for(&row.regime_pub, served_target);
                let q_eff = c_bump * q_regime;
                // Legacy M5 formula — band relative to point. Kept for
                // byte-for-byte parity with deployed M5 receipts.
                let lower = row.point * (1.0 - q_eff);
                let upper = row.point * (1.0 + q_eff);
                let diag = PricePointDiagnostics {
                    fri_close: row.fri_close,
                    served_target,
                    c_bump,
                    q_eff,
                    q_regime: Some(q_regime),
                    symbol_class: None,
                    b_class: None,
                };
                (delta, served_target, c_bump, q_eff, lower, upper, diag)
            }
        };
        let _ = (served_target, c_bump, q_eff); // already captured into PricePoint via diag

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
            claimed_coverage_served: diagnostics.served_target,
            point: row.point,
            lower,
            upper,
            regime,
            forecaster_used: MONDRIAN_FORECASTER.to_string(),
            sharpness_bps,
            half_width_bps,
            profile: self.profile,
            diagnostics,
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

fn load_artefact(path: &Path) -> Result<Vec<ArtefactRow>> {
    let mut file = std::fs::File::open(path)?;
    let df = ParquetReader::new(&mut file).finish()?;

    let required = ["symbol", "fri_ts", "regime_pub", "fri_close", "point"];
    for col in &required {
        df.column(col).map_err(|_| Error::MissingColumn {
            column: (*col).into(),
            artifact: "mondrian_artefact_v2".into(),
        })?;
    }

    let sym_col = df.column("symbol")?.str()?;
    let reg_col = df.column("regime_pub")?.str()?;
    let fri_close_col = df.column("fri_close")?.f64()?;
    let point_col = df.column("point")?.f64()?;

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
        out.push(ArtefactRow {
            symbol: sym_col.get(i).unwrap_or("").to_string(),
            fri_ts,
            regime_pub: reg_col.get(i).unwrap_or("").to_string(),
            fri_close: fri_close_col.get(i).unwrap_or(f64::NAN),
            point: point_col.get(i).unwrap_or(f64::NAN),
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
