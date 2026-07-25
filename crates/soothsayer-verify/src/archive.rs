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

/// A Friday-close commitment row (`commitments_v1.csv`): the width
/// half of the band, emitted before the weekend's outcome information
/// existed. The Monday pre-open band must use these values verbatim.
#[derive(Debug, Clone, Deserialize)]
pub struct CommitmentRow {
    pub weekend_date: String,
    pub mon_date: String,
    pub symbol: String,
    pub tau: f64,
    pub fri_close: f64,
    pub sigma_hat: f64,
    pub regime_code: String,
    pub half_width_bps: f64,
    pub half_width_abs: f64,
    pub forecaster_code: u8,
    pub profile_code: u8,
    pub artefact_sha256: String,
    pub computed_ts: String,
}

fn read_source(source: &str) -> Result<String, Box<dyn Error>> {
    if source.starts_with("http://") || source.starts_with("https://") {
        crate::http::get_text(source)
    } else {
        std::fs::read_to_string(source)
            .map_err(|e| format!("cannot read {source}: {e}").into())
    }
}

fn load_csv<T: serde::de::DeserializeOwned>(source: &str) -> Result<Vec<T>, Box<dyn Error>> {
    let text = read_source(source)?;
    let mut rdr = csv::Reader::from_reader(text.as_bytes());
    let mut rows: Vec<T> = Vec::new();
    for rec in rdr.deserialize() {
        rows.push(rec?);
    }
    if rows.is_empty() {
        return Err(format!("{source} contains no rows").into());
    }
    Ok(rows)
}

/// Load band rows from a local path or an `http(s)://` URL.
pub fn load(source: &str) -> Result<Vec<BandRow>, Box<dyn Error>> {
    load_csv::<BandRow>(source)
}

/// Load commitment rows from a local path or an `http(s)://` URL.
pub fn load_commitments(source: &str) -> Result<Vec<CommitmentRow>, Box<dyn Error>> {
    load_csv::<CommitmentRow>(source)
}
