//! Band-archive loading. The archive (`data/band_archive/bands_v1.csv`
//! in the public repo) is the record of claims being audited — see
//! `data/band_archive/README.md` for column semantics. It carries no
//! realised prices; truth comes from `crate::truth`.

use std::error::Error;

use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct BandRow {
    pub weekend_date: String,
    pub mon_date: String,
    pub symbol: String,
    pub tau: f64,
    pub lower: f64,
    pub upper: f64,
    pub point: f64,
    pub half_width_bps: f64,
    pub regime_code: String,
    pub forecaster_code: u8,
    pub profile_code: u8,
    pub artefact_sha256: String,
    pub provenance: String,
    pub computed_ts: String,
}

/// Load archive rows from a local path or an `http(s)://` URL.
pub fn load(source: &str) -> Result<Vec<BandRow>, Box<dyn Error>> {
    let text = if source.starts_with("http://") || source.starts_with("https://") {
        crate::http::get_text(source)?
    } else {
        std::fs::read_to_string(source)
            .map_err(|e| format!("cannot read archive {source}: {e}"))?
    };
    let mut rdr = csv::Reader::from_reader(text.as_bytes());
    let mut rows: Vec<BandRow> = Vec::new();
    for rec in rdr.deserialize() {
        rows.push(rec?);
    }
    if rows.is_empty() {
        return Err(format!("archive {source} contains no rows").into());
    }
    Ok(rows)
}
