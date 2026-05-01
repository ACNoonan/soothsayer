//! `unified_feed_receipt.v1` — the locked router product surface.
//!
//! Schema and field-population semantics are fixed by the 2026-04-28 (morning)
//! methodology entry. Field-name renames, type narrowings, and semantic
//! redefinitions are breaking changes that require a v2 program PDA, not a
//! v1 amendment. Additive non-breaking changes (new optional field, new enum
//! variant with documented semantics) are permitted within v1.
//!
//! Field-population pattern: regime-conditional. Always-populated fields
//! define the consumer-facing minimum; regime-conditional fields populate
//! only when their methodology is load-bearing for the read.
//! [`UnifiedFeedReceipt::validate_regime_invariants`] enforces this.

use serde::{Deserialize, Serialize};

/// Schema-version identifier emitted on every receipt.
pub const SCHEMA_VERSION: &str = "unified_feed_receipt.v1";

/// Methodology identifier for the open-regime aggregator under Layer 0 v0.
pub const ROUTER_METHODOLOGY_V0_1: &str = "router.v0.1";

/// Methodology identifier for the closed-regime band primitive (paper 1 v1b).
pub const SOOTHSAYER_METHODOLOGY_V1B: &str = "v1b";

/// The market-status regime the router observed at read time.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Regime {
    /// Underlying venue is open; Layer 0 multi-upstream aggregator serves.
    Open,
    /// Underlying venue is closed (weekend or after-hours); soothsayer band serves.
    Closed,
    /// Underlying venue is mid-session-halted; soothsayer band serves with a halted flag.
    Halted,
    /// Regime detection sources disagreed; consumer decides whether to trust the read.
    Unknown,
}

/// Advisory disclosure flag the router is required to emit when its underlying
/// conditions are met. Suppressing a non-`Ok` flag is a methodology violation.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QualityFlag {
    /// Read is healthy on every tracked invariant.
    Ok,
    /// Post-filter quorum dropped below the configured `min_quorum`.
    LowQuorum,
    /// Every tracked upstream was stale at read time; served the most-recent surviving read.
    AllStale,
    /// Closed-regime read could not load the soothsayer band PDA.
    SoothsayerBandUnavailable,
    /// Regime-detection sources disagreed (e.g., Chainlink v11 marketStatus vs calendar).
    RegimeAmbiguous,
}

/// The aggregation method applied during open-regime reads. v0 always serves
/// `RobustMedianV1`; `CalibrationWeightedV1` is a forward reference to Layer 1
/// (gated on ~3 months of upstream forward tape per scryer wishlist 21-23).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AggregateMethod {
    RobustMedianV1,
    CalibrationWeightedV1,
}

/// The closed-regime forecaster that produced the served band.
///
/// Wire-format values match the Python codebase ([`F1_emp_regime`, `F0_stale`])
/// and the 2026-04-28 (morning) schema lock. Explicit `rename` overrides
/// `rename_all = "snake_case"` to preserve the capital `F`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Forecaster {
    /// Factor-switchboard point + log-log vol regression + empirical-quantile residual band.
    #[serde(rename = "F1_emp_regime")]
    F1EmpRegime,
    /// Friday-close held forward + 20-day Gaussian band; serves in `high_vol`.
    #[serde(rename = "F0_stale")]
    F0Stale,
}

/// The closed-market regime label assigned by the pre-publish regime labeler.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ClosedMarketRegime {
    Normal,
    LongWeekend,
    HighVol,
}

/// The kind of upstream feed contributing to a Layer 0 aggregate. Fixed
/// vocabulary per the 2026-04-28 (morning) schema lock; adding a variant is
/// non-breaking provided the `serde` rename matches the methodology entry.
///
/// Mango v4 is intentionally absent: per the 2026-04-29 (morning) entry,
/// Mango does not persist a readable post-guard price field, and the
/// strategic decision was to reclassify Mango's contribution as
/// deviation-guard methodology only (adopted as the Layer 0 filter in the
/// 2026-04-28 (midday) entry).
///
/// `ChainlinkStreamsRelay` was renamed from `ChainlinkV11` per the 2026-04-29
/// (afternoon) entry: Chainlink Data Streams on Solana doesn't publish
/// passive PDAs, so the router consumes via a soothsayer-controlled relay
/// program (Option C) rather than reading raw Chainlink reports. The
/// upstream still attributes to Chainlink in receipts; only the internal
/// data path differs from the original v11-direct-read assumption.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum UpstreamKind {
    PythAggregate,
    /// Wire format `chainlink_streams_relay`. The router reads a
    /// soothsayer-controlled `streams_relay_update.v1` PDA written by
    /// the Chainlink Streams Relay program; the relay daemon validates
    /// signed Chainlink reports off-chain (or via Verifier CPI inside
    /// the relay program) before posting.
    ChainlinkStreamsRelay,
    /// Wire format `switchboard_ondemand` (no inner underscore) per the locked
    /// schema and matching the scryer venue `switchboard_ondemand_tape.v1`.
    #[serde(rename = "switchboard_ondemand")]
    SwitchboardOnDemand,
    RedstoneLive,
}

/// Why a particular upstream's read was excluded from the aggregate.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExclusionReason {
    Stale,
    LowConfidence,
    DeviationOutlier,
}

/// Per-upstream contribution captured in the `upstream_contributions` array
/// during open-regime reads.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct UpstreamReceipt {
    pub kind: UpstreamKind,
    /// Base58-encoded PDA of the upstream feed.
    pub pda: String,
    pub raw_price: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raw_confidence: Option<f64>,
    pub last_update_slot: u64,
    pub included_in_aggregate: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exclusion_reason: Option<ExclusionReason>,
}

/// Per-upstream deviation magnitude captured in `deviation_guard_hits` when a
/// Mango-style guard clamped the read.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct DeviationHit {
    pub upstream: UpstreamKind,
    pub deviation_bps_from_median: f64,
}

/// The full unified-feed receipt. See the 2026-04-28 (morning) methodology
/// entry for the locked field semantics.
///
/// Fields are partitioned into three groups:
///   - **Always populated** — `schema_version`, `asset_id`, `slot`, `unix_ts`,
///     `regime`, `point`, `lower`, `upper`, `soothsayer_methodology`,
///     `quality_flag`. These define the consumer-facing minimum surface.
///   - **Open-regime fields** — populated when `regime == Open`, `None` otherwise:
///     `aggregate_method`, `upstream_contributions`, `deviation_guard_hits`,
///     `quorum_size`, `quorum_required`.
///   - **Closed-regime fields** — populated when `regime in {Closed, Halted}`,
///     `None` otherwise: `tau`, `q_served`, `forecaster`, `closed_market_regime`,
///     `buffer_applied`, `calibration_basis`.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct UnifiedFeedReceipt {
    pub schema_version: String,
    pub asset_id: String,
    pub slot: u64,
    pub unix_ts: i64,
    pub regime: Regime,

    pub point: f64,
    pub lower: f64,
    pub upper: f64,
    pub soothsayer_methodology: String,
    pub quality_flag: QualityFlag,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub aggregate_method: Option<AggregateMethod>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub upstream_contributions: Option<Vec<UpstreamReceipt>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deviation_guard_hits: Option<Vec<DeviationHit>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub quorum_size: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub quorum_required: Option<u8>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub tau: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub q_served: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub forecaster: Option<Forecaster>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub closed_market_regime: Option<ClosedMarketRegime>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub buffer_applied: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub calibration_basis: Option<String>,
}

impl UnifiedFeedReceipt {
    /// Validate that field population matches the regime per the methodology lock.
    /// Returns `Ok(())` if the receipt is consistent, otherwise the first violation.
    ///
    /// Open-regime reads must populate all five open-regime fields and leave the
    /// six closed-regime fields `None`. Closed/halted reads must populate all six
    /// closed-regime fields and leave the five open-regime fields `None` (except
    /// `deviation_guard_hits`, which is allowed to be `None` in either regime —
    /// it's an open-regime field but is populated only when a guard actually fired).
    /// Unknown-regime reads must carry `quality_flag == RegimeAmbiguous`.
    pub fn validate_regime_invariants(&self) -> Result<(), ValidationError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ValidationError::SchemaVersionMismatch(
                self.schema_version.clone(),
            ));
        }

        match self.regime {
            Regime::Open => {
                if self.aggregate_method.is_none() {
                    return Err(ValidationError::MissingOpenRegimeField("aggregate_method"));
                }
                if self.upstream_contributions.is_none() {
                    return Err(ValidationError::MissingOpenRegimeField(
                        "upstream_contributions",
                    ));
                }
                if self.quorum_size.is_none() {
                    return Err(ValidationError::MissingOpenRegimeField("quorum_size"));
                }
                if self.quorum_required.is_none() {
                    return Err(ValidationError::MissingOpenRegimeField("quorum_required"));
                }
                if self.tau.is_some()
                    || self.q_served.is_some()
                    || self.forecaster.is_some()
                    || self.closed_market_regime.is_some()
                    || self.buffer_applied.is_some()
                    || self.calibration_basis.is_some()
                {
                    return Err(ValidationError::ClosedRegimeFieldInOpenRegime);
                }
            }
            Regime::Closed | Regime::Halted => {
                if self.tau.is_none() {
                    return Err(ValidationError::MissingClosedRegimeField("tau"));
                }
                if self.q_served.is_none() {
                    return Err(ValidationError::MissingClosedRegimeField("q_served"));
                }
                if self.forecaster.is_none() {
                    return Err(ValidationError::MissingClosedRegimeField("forecaster"));
                }
                if self.closed_market_regime.is_none() {
                    return Err(ValidationError::MissingClosedRegimeField(
                        "closed_market_regime",
                    ));
                }
                if self.buffer_applied.is_none() {
                    return Err(ValidationError::MissingClosedRegimeField("buffer_applied"));
                }
                if self.calibration_basis.is_none() {
                    return Err(ValidationError::MissingClosedRegimeField("calibration_basis"));
                }
                if self.aggregate_method.is_some()
                    || self.upstream_contributions.is_some()
                    || self.deviation_guard_hits.is_some()
                    || self.quorum_size.is_some()
                    || self.quorum_required.is_some()
                {
                    return Err(ValidationError::OpenRegimeFieldInClosedRegime);
                }
            }
            Regime::Unknown => {
                if self.quality_flag != QualityFlag::RegimeAmbiguous {
                    return Err(ValidationError::UnknownRegimeRequiresAmbiguousFlag);
                }
            }
        }

        Ok(())
    }

    /// Build a Layer 0 v0 open-regime receipt with the required fields populated
    /// and all closed-regime fields cleared. The methodology identifier is
    /// pinned to [`ROUTER_METHODOLOGY_V0_1`]; aggregate method is fixed to
    /// `RobustMedianV1` for v0.
    #[allow(clippy::too_many_arguments)]
    pub fn new_open_layer0(
        asset_id: impl Into<String>,
        slot: u64,
        unix_ts: i64,
        point: f64,
        lower: f64,
        upper: f64,
        upstream_contributions: Vec<UpstreamReceipt>,
        deviation_guard_hits: Vec<DeviationHit>,
        quorum_size: u8,
        quorum_required: u8,
        quality_flag: QualityFlag,
    ) -> Self {
        let deviation_guard_hits = if deviation_guard_hits.is_empty() {
            None
        } else {
            Some(deviation_guard_hits)
        };
        Self {
            schema_version: SCHEMA_VERSION.to_string(),
            asset_id: asset_id.into(),
            slot,
            unix_ts,
            regime: Regime::Open,
            point,
            lower,
            upper,
            soothsayer_methodology: ROUTER_METHODOLOGY_V0_1.to_string(),
            quality_flag,
            aggregate_method: Some(AggregateMethod::RobustMedianV1),
            upstream_contributions: Some(upstream_contributions),
            deviation_guard_hits,
            quorum_size: Some(quorum_size),
            quorum_required: Some(quorum_required),
            tau: None,
            q_served: None,
            forecaster: None,
            closed_market_regime: None,
            buffer_applied: None,
            calibration_basis: None,
        }
    }

    /// Build a closed-regime receipt sourced from the soothsayer band primitive.
    /// `regime` must be `Closed` or `Halted`; `Open` and `Unknown` panic in debug.
    #[allow(clippy::too_many_arguments)]
    pub fn new_closed(
        asset_id: impl Into<String>,
        slot: u64,
        unix_ts: i64,
        regime: Regime,
        point: f64,
        lower: f64,
        upper: f64,
        tau: f64,
        q_served: f64,
        forecaster: Forecaster,
        closed_market_regime: ClosedMarketRegime,
        buffer_applied: f64,
        calibration_basis: impl Into<String>,
        quality_flag: QualityFlag,
    ) -> Self {
        debug_assert!(
            matches!(regime, Regime::Closed | Regime::Halted),
            "new_closed requires regime in {{Closed, Halted}}, got {regime:?}",
        );
        Self {
            schema_version: SCHEMA_VERSION.to_string(),
            asset_id: asset_id.into(),
            slot,
            unix_ts,
            regime,
            point,
            lower,
            upper,
            soothsayer_methodology: SOOTHSAYER_METHODOLOGY_V1B.to_string(),
            quality_flag,
            aggregate_method: None,
            upstream_contributions: None,
            deviation_guard_hits: None,
            quorum_size: None,
            quorum_required: None,
            tau: Some(tau),
            q_served: Some(q_served),
            forecaster: Some(forecaster),
            closed_market_regime: Some(closed_market_regime),
            buffer_applied: Some(buffer_applied),
            calibration_basis: Some(calibration_basis.into()),
        }
    }
}

/// Errors raised by [`UnifiedFeedReceipt::validate_regime_invariants`].
#[derive(thiserror::Error, Debug, PartialEq, Eq)]
pub enum ValidationError {
    #[error("open-regime read missing required field: {0}")]
    MissingOpenRegimeField(&'static str),
    #[error("closed-regime read missing required field: {0}")]
    MissingClosedRegimeField(&'static str),
    #[error("closed-regime field populated in an open-regime read")]
    ClosedRegimeFieldInOpenRegime,
    #[error("open-regime field populated in a closed-regime read")]
    OpenRegimeFieldInClosedRegime,
    #[error("regime=unknown requires quality_flag=regime_ambiguous")]
    UnknownRegimeRequiresAmbiguousFlag,
    #[error("schema_version does not match locked v1: got {0:?}")]
    SchemaVersionMismatch(String),
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_upstreams() -> Vec<UpstreamReceipt> {
        vec![
            UpstreamReceipt {
                kind: UpstreamKind::PythAggregate,
                pda: "PythSPYxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx".to_string(),
                raw_price: 528.42,
                raw_confidence: Some(0.04),
                last_update_slot: 312_500_000,
                included_in_aggregate: true,
                exclusion_reason: None,
            },
            UpstreamReceipt {
                kind: UpstreamKind::ChainlinkStreamsRelay,
                pda: "ChainlinkSPYxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx".to_string(),
                raw_price: 528.41,
                raw_confidence: None,
                last_update_slot: 312_499_998,
                included_in_aggregate: true,
                exclusion_reason: None,
            },
        ]
    }

    fn sample_open_receipt() -> UnifiedFeedReceipt {
        UnifiedFeedReceipt::new_open_layer0(
            "SPY",
            312_500_000,
            1_761_700_000,
            528.41,
            528.10,
            528.72,
            sample_upstreams(),
            vec![],
            2,
            2,
            QualityFlag::Ok,
        )
    }

    fn sample_closed_receipt() -> UnifiedFeedReceipt {
        UnifiedFeedReceipt::new_closed(
            "SPY",
            312_500_000,
            1_761_700_000,
            Regime::Closed,
            528.41,
            515.10,
            541.72,
            0.95,
            0.97,
            Forecaster::F1EmpRegime,
            ClosedMarketRegime::Normal,
            0.020,
            "soothsayer_v1b",
            QualityFlag::Ok,
        )
    }

    #[test]
    fn open_receipt_roundtrips_through_json() {
        let r = sample_open_receipt();
        let s = serde_json::to_string(&r).unwrap();
        let r2: UnifiedFeedReceipt = serde_json::from_str(&s).unwrap();
        assert_eq!(r, r2);
    }

    #[test]
    fn closed_receipt_roundtrips_through_json() {
        let r = sample_closed_receipt();
        let s = serde_json::to_string(&r).unwrap();
        let r2: UnifiedFeedReceipt = serde_json::from_str(&s).unwrap();
        assert_eq!(r, r2);
    }

    #[test]
    fn enum_variants_serialize_to_documented_strings() {
        // Spot-check that the rename_all = "snake_case" produces the strings the
        // methodology entry fixed. If any of these change the schema lock breaks.
        assert_eq!(
            serde_json::to_string(&Regime::Open).unwrap(),
            "\"open\""
        );
        assert_eq!(
            serde_json::to_string(&QualityFlag::SoothsayerBandUnavailable).unwrap(),
            "\"soothsayer_band_unavailable\""
        );
        assert_eq!(
            serde_json::to_string(&AggregateMethod::RobustMedianV1).unwrap(),
            "\"robust_median_v1\""
        );
        assert_eq!(
            serde_json::to_string(&AggregateMethod::CalibrationWeightedV1).unwrap(),
            "\"calibration_weighted_v1\""
        );
        assert_eq!(
            serde_json::to_string(&Forecaster::F1EmpRegime).unwrap(),
            "\"F1_emp_regime\""
        );
        assert_eq!(
            serde_json::to_string(&Forecaster::F0Stale).unwrap(),
            "\"F0_stale\""
        );
        assert_eq!(
            serde_json::to_string(&ClosedMarketRegime::LongWeekend).unwrap(),
            "\"long_weekend\""
        );
        assert_eq!(
            serde_json::to_string(&UpstreamKind::PythAggregate).unwrap(),
            "\"pyth_aggregate\""
        );
        assert_eq!(
            serde_json::to_string(&UpstreamKind::ChainlinkStreamsRelay).unwrap(),
            "\"chainlink_streams_relay\""
        );
        assert_eq!(
            serde_json::to_string(&UpstreamKind::SwitchboardOnDemand).unwrap(),
            "\"switchboard_ondemand\""
        );
        assert_eq!(
            serde_json::to_string(&UpstreamKind::RedstoneLive).unwrap(),
            "\"redstone_live\""
        );
        assert_eq!(
            serde_json::to_string(&ExclusionReason::DeviationOutlier).unwrap(),
            "\"deviation_outlier\""
        );
    }

    #[test]
    fn schema_version_constant_matches_methodology_lock() {
        assert_eq!(SCHEMA_VERSION, "unified_feed_receipt.v1");
        let r = sample_open_receipt();
        assert_eq!(r.schema_version, SCHEMA_VERSION);
    }

    #[test]
    fn well_formed_open_receipt_validates() {
        sample_open_receipt().validate_regime_invariants().unwrap();
    }

    #[test]
    fn well_formed_closed_receipt_validates() {
        sample_closed_receipt()
            .validate_regime_invariants()
            .unwrap();
    }

    #[test]
    fn open_receipt_with_closed_field_set_fails() {
        let mut r = sample_open_receipt();
        r.tau = Some(0.95);
        let err = r.validate_regime_invariants().unwrap_err();
        assert_eq!(err, ValidationError::ClosedRegimeFieldInOpenRegime);
    }

    #[test]
    fn closed_receipt_with_open_field_set_fails() {
        let mut r = sample_closed_receipt();
        r.aggregate_method = Some(AggregateMethod::RobustMedianV1);
        let err = r.validate_regime_invariants().unwrap_err();
        assert_eq!(err, ValidationError::OpenRegimeFieldInClosedRegime);
    }

    #[test]
    fn open_receipt_missing_aggregate_method_fails() {
        let mut r = sample_open_receipt();
        r.aggregate_method = None;
        let err = r.validate_regime_invariants().unwrap_err();
        assert_eq!(
            err,
            ValidationError::MissingOpenRegimeField("aggregate_method")
        );
    }

    #[test]
    fn closed_receipt_missing_tau_fails() {
        let mut r = sample_closed_receipt();
        r.tau = None;
        let err = r.validate_regime_invariants().unwrap_err();
        assert_eq!(err, ValidationError::MissingClosedRegimeField("tau"));
    }

    #[test]
    fn unknown_regime_without_ambiguous_flag_fails() {
        let mut r = sample_open_receipt();
        r.regime = Regime::Unknown;
        // quality_flag is still Ok from the open-regime constructor — should fail.
        let err = r.validate_regime_invariants().unwrap_err();
        assert_eq!(err, ValidationError::UnknownRegimeRequiresAmbiguousFlag);
    }

    #[test]
    fn unknown_regime_with_ambiguous_flag_validates() {
        let mut r = sample_open_receipt();
        r.regime = Regime::Unknown;
        r.quality_flag = QualityFlag::RegimeAmbiguous;
        // Unknown is permissive on field population — the consumer decides.
        r.validate_regime_invariants().unwrap();
    }

    #[test]
    fn schema_version_mismatch_fails() {
        let mut r = sample_open_receipt();
        r.schema_version = "unified_feed_receipt.v2".to_string();
        let err = r.validate_regime_invariants().unwrap_err();
        assert!(matches!(err, ValidationError::SchemaVersionMismatch(_)));
    }

    #[test]
    fn deviation_guard_hits_omitted_when_empty() {
        // An empty list of guard hits should round-trip as None / omitted, not as []
        // — keeps receipts compact when nothing fired.
        let r = sample_open_receipt();
        assert!(r.deviation_guard_hits.is_none());
        let s = serde_json::to_string(&r).unwrap();
        assert!(!s.contains("deviation_guard_hits"));
    }

    #[test]
    fn deviation_guard_hits_populated_when_nonempty() {
        let r = UnifiedFeedReceipt::new_open_layer0(
            "SPY",
            1,
            1,
            100.0,
            99.0,
            101.0,
            sample_upstreams(),
            vec![DeviationHit {
                upstream: UpstreamKind::RedstoneLive,
                deviation_bps_from_median: 92.5,
            }],
            2,
            2,
            QualityFlag::LowQuorum,
        );
        let hits = r.deviation_guard_hits.as_ref().unwrap();
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].upstream, UpstreamKind::RedstoneLive);
    }

    #[test]
    fn upstream_receipt_omits_optional_fields_when_none() {
        let u = UpstreamReceipt {
            kind: UpstreamKind::ChainlinkStreamsRelay,
            pda: "P".to_string(),
            raw_price: 1.0,
            raw_confidence: None,
            last_update_slot: 0,
            included_in_aggregate: true,
            exclusion_reason: None,
        };
        let s = serde_json::to_string(&u).unwrap();
        assert!(!s.contains("raw_confidence"));
        assert!(!s.contains("exclusion_reason"));
    }
}
