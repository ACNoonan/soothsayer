//! Calibration surface — the empirical (symbol, regime, forecaster, claimed)
//! → realized coverage map. Two surfaces are maintained: per-symbol and
//! pooled-across-symbols (fallback for thin buckets).
//!
//! Each surface is a flat vector of rows loaded once at Oracle::load time.
//! Inversion (`invert_target_to_claimed`) does linear interpolation in
//! (realized, claimed) space to find the claimed quantile that empirically
//! delivers the requested target realized coverage.

use polars::prelude::*;
use std::path::Path;

use crate::config::MIN_OBS;
use crate::error::{OracleError, OracleResult};

/// A single surface row: (symbol, regime_pub, forecaster, claimed, realized,
/// n_obs, mean_half_width_bps).
#[derive(Clone, Debug)]
pub struct SurfaceRow {
    pub symbol: String,
    pub regime_pub: String,
    pub forecaster: String,
    pub claimed: f64,
    pub realized: f64,
    pub n_obs: u32,
    pub mean_half_width_bps: f64,
}

/// Per-symbol calibration surface. Keyed by (symbol, regime, forecaster);
/// each key maps to a list of (claimed, realized, n_obs) sorted by claimed.
pub struct CalibrationSurface {
    rows: Vec<SurfaceRow>,
}

impl CalibrationSurface {
    pub fn load_csv(path: &Path) -> OracleResult<Self> {
        let df = CsvReadOptions::default()
            .with_has_header(true)
            .with_parse_options(CsvParseOptions::default().with_try_parse_dates(false))
            .try_into_reader_with_file_path(Some(path.to_path_buf()))?
            .finish()?;
        let rows = parse_surface_df(&df)?;
        Ok(Self { rows })
    }

    /// Return rows filtered to (symbol, regime, forecaster).
    pub fn rows_for(
        &self,
        symbol: &str,
        regime: &str,
        forecaster: &str,
    ) -> Vec<&SurfaceRow> {
        self.rows
            .iter()
            .filter(|r| r.symbol == symbol && r.regime_pub == regime && r.forecaster == forecaster)
            .collect()
    }
}

/// Pooled-across-symbols calibration surface. `symbol` column is populated as
/// "__pooled__" by the Python builder; we use the same convention here.
pub struct PooledSurface {
    rows: Vec<SurfaceRow>,
}

impl PooledSurface {
    pub fn load_csv(path: &Path) -> OracleResult<Self> {
        let df = CsvReadOptions::default()
            .with_has_header(true)
            .with_parse_options(CsvParseOptions::default().with_try_parse_dates(false))
            .try_into_reader_with_file_path(Some(path.to_path_buf()))?
            .finish()?;
        let rows = parse_surface_df(&df)?;
        Ok(Self { rows })
    }

    pub fn rows_for(&self, regime: &str, forecaster: &str) -> Vec<&SurfaceRow> {
        self.rows
            .iter()
            .filter(|r| r.regime_pub == regime && r.forecaster == forecaster)
            .collect()
    }
}

fn parse_surface_df(df: &DataFrame) -> OracleResult<Vec<SurfaceRow>> {
    let n = df.height();
    let sym_col = df.column("symbol").map_err(|_| OracleError::MissingColumn {
        column: "symbol".into(),
        artifact: "surface".into(),
    })?;
    let reg_col = df.column("regime_pub").map_err(|_| OracleError::MissingColumn {
        column: "regime_pub".into(),
        artifact: "surface".into(),
    })?;
    let fc_col = df.column("forecaster").map_err(|_| OracleError::MissingColumn {
        column: "forecaster".into(),
        artifact: "surface".into(),
    })?;
    let claimed_col = df.column("claimed").map_err(|_| OracleError::MissingColumn {
        column: "claimed".into(),
        artifact: "surface".into(),
    })?;
    let realized_col = df.column("realized").map_err(|_| OracleError::MissingColumn {
        column: "realized".into(),
        artifact: "surface".into(),
    })?;
    let n_obs_col = df.column("n_obs").map_err(|_| OracleError::MissingColumn {
        column: "n_obs".into(),
        artifact: "surface".into(),
    })?;
    let hw_col = df.column("mean_half_width_bps").map_err(|_| OracleError::MissingColumn {
        column: "mean_half_width_bps".into(),
        artifact: "surface".into(),
    })?;

    let sym = sym_col.str()?;
    let reg = reg_col.str()?;
    let fc = fc_col.str()?;
    let claimed = claimed_col.f64()?;
    let realized = realized_col.f64()?;
    let n_obs = n_obs_col.cast(&DataType::UInt32)?;
    let n_obs = n_obs.u32()?;
    let hw = hw_col.f64()?;

    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        out.push(SurfaceRow {
            symbol: sym.get(i).unwrap_or("").to_string(),
            regime_pub: reg.get(i).unwrap_or("").to_string(),
            forecaster: fc.get(i).unwrap_or("").to_string(),
            claimed: claimed.get(i).unwrap_or(f64::NAN),
            realized: realized.get(i).unwrap_or(f64::NAN),
            n_obs: n_obs.get(i).unwrap_or(0),
            mean_half_width_bps: hw.get(i).unwrap_or(f64::NAN),
        });
    }
    Ok(out)
}

/// Result of an inversion: the claimed quantile + lightweight diagnostics.
#[derive(Clone, Debug)]
pub struct InvertResult {
    pub claimed: f64,
    /// Which path was used: "per_symbol" or "pooled".
    pub calibration: String,
    pub bracketed: Option<(f64, f64)>,
    pub clipped: Option<String>,
    pub symbol_n: Option<u32>,
    pub realized_min: Option<f64>,
    pub realized_max: Option<f64>,
}

/// Inverts target_realized → claimed on a slice of surface rows. Mirrors the
/// Python `cal.invert` function.
///
/// Sorts the rows by realized ascending; if target is outside the grid,
/// clips to the nearest edge. Otherwise linear-interpolates between the two
/// bracketing grid points.
fn invert_rows(
    rows: &[&SurfaceRow],
    target_realized: f64,
) -> Option<InvertResult> {
    if rows.is_empty() {
        return None;
    }
    let max_n = rows.iter().map(|r| r.n_obs).max().unwrap_or(0);
    if max_n < MIN_OBS {
        return None; // caller should fall back to pooled
    }
    // Sort by realized ascending
    let mut sorted: Vec<&&SurfaceRow> = rows.iter().collect();
    sorted.sort_by(|a, b| a.realized.partial_cmp(&b.realized).unwrap_or(std::cmp::Ordering::Equal));

    let realized_vals: Vec<f64> = sorted.iter().map(|r| r.realized).collect();
    let claimed_vals: Vec<f64> = sorted.iter().map(|r| r.claimed).collect();
    let r_min = *realized_vals.first().unwrap();
    let r_max = *realized_vals.last().unwrap();

    if target_realized <= r_min {
        return Some(InvertResult {
            claimed: claimed_vals[0],
            calibration: String::new(), // caller fills in
            bracketed: None,
            clipped: Some("below".into()),
            symbol_n: Some(max_n),
            realized_min: Some(r_min),
            realized_max: None,
        });
    }
    if target_realized >= r_max {
        return Some(InvertResult {
            claimed: *claimed_vals.last().unwrap(),
            calibration: String::new(),
            bracketed: None,
            clipped: Some("above".into()),
            symbol_n: Some(max_n),
            realized_min: None,
            realized_max: Some(r_max),
        });
    }

    for i in 0..(realized_vals.len() - 1) {
        let r0 = realized_vals[i];
        let r1 = realized_vals[i + 1];
        if r0 <= target_realized && target_realized <= r1 {
            let c0 = claimed_vals[i];
            let c1 = claimed_vals[i + 1];
            let claimed = if (r1 - r0).abs() < f64::EPSILON {
                c0
            } else {
                let frac = (target_realized - r0) / (r1 - r0);
                c0 + frac * (c1 - c0)
            };
            return Some(InvertResult {
                claimed,
                calibration: String::new(),
                bracketed: Some((c0, c1)),
                clipped: None,
                symbol_n: Some(max_n),
                realized_min: None,
                realized_max: None,
            });
        }
    }

    // Fallback: return the max claimed (shouldn't happen given clip checks above)
    Some(InvertResult {
        claimed: *claimed_vals.last().unwrap(),
        calibration: String::new(),
        bracketed: None,
        clipped: None,
        symbol_n: Some(max_n),
        realized_min: None,
        realized_max: None,
    })
}

/// Invert using the per-symbol surface, falling back to pooled if the
/// (symbol, regime, forecaster) bucket is thin. Mirrors the Python
/// `Oracle._invert_to_claimed` path.
pub fn invert_with_fallback(
    per_symbol: &CalibrationSurface,
    pooled: &PooledSurface,
    symbol: &str,
    regime: &str,
    forecaster: &str,
    target_realized: f64,
) -> InvertResult {
    let sym_rows = per_symbol.rows_for(symbol, regime, forecaster);
    if let Some(mut res) = invert_rows(&sym_rows, target_realized) {
        res.calibration = "per_symbol".into();
        return res;
    }

    let pooled_rows = pooled.rows_for(regime, forecaster);
    if let Some(mut res) = invert_rows(&pooled_rows, target_realized) {
        res.calibration = "pooled".into();
        return res;
    }

    // Last resort: return the target as-is; caller will clip to grid
    InvertResult {
        claimed: target_realized,
        calibration: "degenerate".into(),
        bracketed: None,
        clipped: None,
        symbol_n: None,
        realized_min: None,
        realized_max: None,
    }
}
