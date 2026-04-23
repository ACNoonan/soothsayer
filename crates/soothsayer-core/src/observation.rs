//! The `Observation` record — the one normalized datum that flows through the
//! ingest → filter → publisher pipeline. Per the Phase 1 plan:
//!
//! > Normalize to `Observation { asset, signal_type, value, ts, source_σ² }`.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::asset::{AssetSymbol, SignalKind, Source};

/// A single normalized observation.
///
/// `variance` is the source's estimate of observation noise (σ²) on the raw
/// `value`. Sources that don't publish a confidence estimate should set it to
/// `0.0`; the filter layer will then fall back to a rolling-vol prior.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Observation {
    pub asset: AssetSymbol,
    pub kind: SignalKind,
    pub source: Source,
    pub value: f64,
    pub variance: f64,
    pub ts: DateTime<Utc>,
}

impl Observation {
    pub fn new(
        asset: AssetSymbol,
        kind: SignalKind,
        source: Source,
        value: f64,
        variance: f64,
        ts: DateTime<Utc>,
    ) -> Self {
        Self { asset, kind, source, value, variance, ts }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn observation_roundtrips_through_json() {
        let obs = Observation::new(
            AssetSymbol::new("SPYx").unwrap(),
            SignalKind::Mid,
            Source::Chainlink,
            707.83,
            0.0,
            Utc.with_ymd_and_hms(2026, 4, 20, 13, 29, 13).unwrap(),
        );
        let s = serde_json::to_string(&obs).unwrap();
        let rt: Observation = serde_json::from_str(&s).unwrap();
        assert_eq!(obs, rt);
    }
}
