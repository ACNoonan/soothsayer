//! Main Oracle implementation.

use chrono::NaiveDate;
use polars::prelude::*;
use std::collections::HashMap;
use std::path::Path;

use crate::config::{
    buffer_for_target, default_buffer_by_target, default_regime_forecaster, DEFAULT_FORECASTER,
    MAX_SERVED_TARGET,
};
use crate::error::{OracleError, OracleResult};
use crate::surface::{invert_with_fallback, CalibrationSurface, PooledSurface};
use crate::types::{PricePoint, PricePointDiagnostics, Regime};

/// One row of the bounds table for a given (symbol, fri_ts, forecaster, claimed).
#[derive(Clone, Debug)]
struct BoundsRow {
    symbol: String,
    fri_ts: NaiveDate,
    regime_pub: String,
    forecaster: String,
    claimed: f64,
    lower: f64,
    upper: f64,
    fri_close: f64,
}

/// The Soothsayer Oracle — Rust port of `src/soothsayer/oracle.py`.
///
/// Construct via [`Oracle::load`], then call [`Oracle::fair_value`].
pub struct Oracle {
    bounds: Vec<BoundsRow>,
    surface: CalibrationSurface,
    surface_pooled: PooledSurface,
    regime_forecaster: HashMap<String, String>,
    /// If `Some(x)`, scalar buffer broadcasts to every target (legacy /
    /// ablation A/B path). If `None`, the per-target schedule is the
    /// primary mechanism.
    buffer_scalar: Option<f64>,
    /// Per-target buffer schedule, sorted by target ascending. See
    /// `config::default_buffer_by_target` for the deployed values and
    /// `reports/v1b_buffer_tune.md` for tuning evidence.
    buffer_schedule: Vec<(f64, f64)>,
}

impl Oracle {
    /// Load from the Python-produced artifacts.
    pub fn load(
        bounds_path: &Path,
        surface_path: &Path,
        surface_pooled_path: &Path,
    ) -> OracleResult<Self> {
        let bounds = load_bounds_table(bounds_path)?;
        let surface = CalibrationSurface::load_csv(surface_path)?;
        let surface_pooled = PooledSurface::load_csv(surface_pooled_path)?;
        let regime_forecaster = default_regime_forecaster()
            .into_iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        Ok(Self {
            bounds,
            surface,
            surface_pooled,
            regime_forecaster,
            buffer_scalar: None,
            buffer_schedule: default_buffer_by_target(),
        })
    }

    /// Override the hybrid regime→forecaster map (for diagnostics / A/B).
    pub fn with_regime_forecaster(mut self, map: HashMap<String, String>) -> Self {
        self.regime_forecaster = map;
        self
    }

    /// Override with a single scalar buffer applied to every target. Sets the
    /// legacy single-buffer path; `0.0` disables the buffer entirely.
    pub fn with_buffer_pct(mut self, buffer: f64) -> Self {
        self.buffer_scalar = Some(buffer);
        self
    }

    /// Replace the per-target buffer schedule. Pairs must be `(target, buffer)`
    /// sorted by target ascending; off-grid targets are linearly interpolated.
    pub fn with_buffer_schedule(mut self, schedule: Vec<(f64, f64)>) -> Self {
        self.buffer_schedule = schedule;
        self.buffer_scalar = None;
        self
    }

    fn pick_forecaster(&self, regime: &str) -> &str {
        self.regime_forecaster
            .get(regime)
            .map(|s| s.as_str())
            .unwrap_or(DEFAULT_FORECASTER)
    }

    /// Serve a calibrated band.
    ///
    /// `forecaster_override` forces a specific forecaster regardless of regime
    /// (useful for A/B tests). `buffer_override` overrides the empirical
    /// calibration buffer; pass `Some(0.0)` to disable entirely.
    pub fn fair_value(
        &self,
        symbol: &str,
        as_of: NaiveDate,
        target_coverage: f64,
        forecaster_override: Option<&str>,
        buffer_override: Option<f64>,
    ) -> OracleResult<PricePoint> {
        // 1. Look up every forecaster's rows at this (symbol, fri_ts)
        let rows: Vec<&BoundsRow> = self
            .bounds
            .iter()
            .filter(|r| r.symbol == symbol && r.fri_ts == as_of)
            .collect();
        if rows.is_empty() {
            return Err(OracleError::NoBounds {
                symbol: symbol.to_string(),
                as_of,
            });
        }

        let regime_str = rows[0].regime_pub.clone();
        let fri_close = rows[0].fri_close;
        let regime = Regime::from_str(&regime_str)
            .ok_or_else(|| OracleError::UnknownRegime(regime_str.clone()))?;

        // 2. Pick forecaster (hybrid per-regime by default)
        let forecaster_used: String = match forecaster_override {
            Some(f) => f.to_string(),
            None => self.pick_forecaster(&regime_str).to_string(),
        };

        // Filter rows to the chosen forecaster; fall back to any available if absent
        let mut fc_rows: Vec<&BoundsRow> =
            rows.iter().copied().filter(|r| r.forecaster == forecaster_used).collect();
        let forecaster_used_final = if fc_rows.is_empty() {
            let fallback = rows[0].forecaster.clone();
            fc_rows = rows.iter().copied().filter(|r| r.forecaster == fallback).collect();
            fallback
        } else {
            forecaster_used
        };

        // 3. Apply buffer to target. Resolution order:
        //    1. caller-supplied `buffer_override` (scalar) — A/B / diagnostic.
        //    2. Oracle-level scalar (legacy `with_buffer_pct`).
        //    3. Per-target schedule via `buffer_for_target` interpolation.
        let buffer_pct = match buffer_override {
            Some(b) => b,
            None => match self.buffer_scalar {
                Some(b) => b,
                None => buffer_for_target(target_coverage, &self.buffer_schedule),
            },
        };
        let effective_target = (target_coverage + buffer_pct).min(MAX_SERVED_TARGET);

        // 4. Invert calibration surface
        let invert_res = invert_with_fallback(
            &self.surface,
            &self.surface_pooled,
            symbol,
            &regime_str,
            &forecaster_used_final,
            effective_target,
        );
        let claimed_served = invert_res.claimed;

        // 5. Clip to nearest grid point
        let grid: Vec<f64> = {
            let mut g: Vec<f64> = fc_rows.iter().map(|r| r.claimed).collect();
            g.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
            g.dedup();
            g
        };
        let nearest_claimed = grid
            .iter()
            .copied()
            .min_by(|a, b| {
                (a - claimed_served)
                    .abs()
                    .partial_cmp(&(b - claimed_served).abs())
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .ok_or_else(|| OracleError::Integrity("empty claimed grid".into()))?;

        let chosen = fc_rows
            .iter()
            .find(|r| (r.claimed - nearest_claimed).abs() < 1e-12)
            .ok_or_else(|| OracleError::Integrity(
                format!("no bounds row at claimed={}", nearest_claimed),
            ))?;

        // 6. Build PricePoint
        let lower = chosen.lower;
        let upper = chosen.upper;
        let point = (lower + upper) / 2.0;
        let sharpness_bps = (upper - lower) / 2.0 / fri_close * 1e4;
        let half_width_bps = PricePoint::compute_half_width_bps(point, lower, upper);

        // Policy snapshot for the receipt (BTreeMap keeps key order deterministic).
        let policy: std::collections::BTreeMap<String, String> = self
            .regime_forecaster
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();

        Ok(PricePoint {
            symbol: symbol.to_string(),
            as_of,
            target_coverage,
            calibration_buffer_applied: buffer_pct,
            claimed_coverage_served: nearest_claimed,
            point,
            lower,
            upper,
            regime,
            forecaster_used: forecaster_used_final,
            sharpness_bps,
            half_width_bps,
            diagnostics: PricePointDiagnostics {
                fri_close,
                nearest_grid: nearest_claimed,
                buffered_target: effective_target,
                requested_claimed_pre_clip: claimed_served,
                regime_forecaster_policy: policy,
                calibration: invert_res.calibration,
                bracketed: invert_res.bracketed,
                clipped: invert_res.clipped,
                realized_min: invert_res.realized_min,
                realized_max: invert_res.realized_max,
            },
        })
    }

    /// List every (symbol, fri_ts, regime) triple available in the bounds table.
    pub fn list_available(&self, symbol: Option<&str>) -> Vec<(String, NaiveDate, String)> {
        use std::collections::HashSet;
        let mut seen: HashSet<(String, NaiveDate)> = HashSet::new();
        let mut out = Vec::new();
        for r in &self.bounds {
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

fn load_bounds_table(path: &Path) -> OracleResult<Vec<BoundsRow>> {
    let mut file = std::fs::File::open(path)?;
    let df = ParquetReader::new(&mut file).finish()?;

    let required = [
        "symbol",
        "fri_ts",
        "regime_pub",
        "forecaster",
        "claimed",
        "lower",
        "upper",
        "fri_close",
    ];
    for col in &required {
        df.column(col).map_err(|_| OracleError::MissingColumn {
            column: (*col).into(),
            artifact: "bounds".into(),
        })?;
    }

    let sym_col = df.column("symbol")?.str()?;
    let reg_col = df.column("regime_pub")?.str()?;
    let fc_col = df.column("forecaster")?.str()?;
    let claimed_col = df.column("claimed")?.f64()?;
    let lower_col = df.column("lower")?.f64()?;
    let upper_col = df.column("upper")?.f64()?;
    let fri_close_col = df.column("fri_close")?.f64()?;

    // fri_ts may be stored as Date32 (Arrow) or as a string; handle both.
    let fri_ts_col = df.column("fri_ts")?;
    let fri_ts_dates: Vec<Option<NaiveDate>> = if matches!(fri_ts_col.dtype(), DataType::Date) {
        fri_ts_col
            .date()?
            .into_iter()
            .map(|d| d.map(date32_to_naive_date))
            .collect()
    } else {
        // Fallback: parse as ISO date string
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
            None => continue, // skip rows with unparseable date
        };
        out.push(BoundsRow {
            symbol: sym_col.get(i).unwrap_or("").to_string(),
            fri_ts,
            regime_pub: reg_col.get(i).unwrap_or("").to_string(),
            forecaster: fc_col.get(i).unwrap_or("").to_string(),
            claimed: claimed_col.get(i).unwrap_or(f64::NAN),
            lower: lower_col.get(i).unwrap_or(f64::NAN),
            upper: upper_col.get(i).unwrap_or(f64::NAN),
            fri_close: fri_close_col.get(i).unwrap_or(f64::NAN),
        });
    }
    Ok(out)
}

fn date32_to_naive_date(days: i32) -> NaiveDate {
    // Arrow Date32 = days since Unix epoch 1970-01-01
    NaiveDate::from_ymd_opt(1970, 1, 1)
        .unwrap()
        .checked_add_days(chrono::Days::new(days as u64))
        .unwrap_or_else(|| NaiveDate::from_ymd_opt(1970, 1, 1).unwrap())
}
