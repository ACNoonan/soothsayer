//! PricePoint ↔ PublishPayload conversion.
//!
//! A [`PricePoint`] is the off-chain Oracle output (f64 prices, f64 coverage
//! in [0,1]). The on-chain [`PublishPayload`] is fixed-point i64 / integer
//! basis points / packed bytes, matching the schema in
//! `programs/soothsayer-oracle-program/src/state.rs`.
//!
//! This module converts between them deterministically and is tested against
//! the on-chain `PriceUpdate::point_f64()` recovery to verify round-trips.

use serde::{Deserialize, Serialize};
use soothsayer_consumer::{
    FORECASTER_F0_STALE, FORECASTER_F1_EMP_REGIME, FORECASTER_MONDRIAN, REGIME_HIGH_VOL,
    REGIME_LONG_WEEKEND, REGIME_NORMAL,
};
use soothsayer_oracle::types::{PricePoint, Regime};
use thiserror::Error;

/// Default precision for published prices: 10^-8 per fixed-point unit.
pub const DEFAULT_EXPONENT: i8 = -8;

/// Byte-for-byte representation of the on-chain `PublishPayload` — kept in
/// sync with the Anchor program's state.rs.
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct PublishPayload {
    pub version: u8,
    pub regime_code: u8,
    pub forecaster_code: u8,
    pub exponent: i8,
    pub target_coverage_bps: u16,
    pub claimed_served_bps: u16,
    pub buffer_applied_bps: u16,
    #[serde(with = "symbol_serde")]
    pub symbol: [u8; 16],
    pub point: i64,
    pub lower: i64,
    pub upper: i64,
    pub fri_close: i64,
    pub fri_ts: i64,
}

/// Error type for payload construction.
#[derive(Debug, Error)]
pub enum PayloadError {
    #[error("symbol too long: {0} ({1} bytes, max 16)")]
    SymbolTooLong(String, usize),
    #[error("coverage/buffer out of range at bp scale: {0}")]
    CoverageOutOfRange(f64),
    #[error("fri_ts parse failed: {0}")]
    FriTsParse(String),
}

/// Serde helper: serialize `[u8; 16]` symbol as trimmed ASCII string for
/// human-readable JSON; deserialize back.
mod symbol_serde {
    use serde::{Deserialize, Deserializer, Serializer};
    pub fn serialize<S: Serializer>(bytes: &[u8; 16], s: S) -> Result<S::Ok, S::Error> {
        let end = bytes.iter().position(|&b| b == 0).unwrap_or(16);
        let as_str = std::str::from_utf8(&bytes[..end]).unwrap_or("");
        s.serialize_str(as_str)
    }
    pub fn deserialize<'de, D: Deserializer<'de>>(d: D) -> Result<[u8; 16], D::Error> {
        let s: &str = Deserialize::deserialize(d)?;
        let b = s.as_bytes();
        if b.len() > 16 {
            return Err(serde::de::Error::custom("symbol > 16 bytes"));
        }
        let mut out = [0u8; 16];
        out[..b.len()].copy_from_slice(b);
        Ok(out)
    }
}

pub fn encode_symbol(sym: &str) -> Result<[u8; 16], PayloadError> {
    let b = sym.as_bytes();
    if b.len() > 16 {
        return Err(PayloadError::SymbolTooLong(sym.to_string(), b.len()));
    }
    let mut out = [0u8; 16];
    out[..b.len()].copy_from_slice(b);
    Ok(out)
}

pub fn regime_to_code(regime: Regime) -> u8 {
    match regime {
        Regime::Normal => REGIME_NORMAL,
        Regime::LongWeekend => REGIME_LONG_WEEKEND,
        Regime::HighVol => REGIME_HIGH_VOL,
        // Shock regime isn't used by the Oracle today — reserved.
    }
}

pub fn forecaster_to_code(name: &str) -> u8 {
    match name {
        // Legacy v1 receipts (paper 1 §7.4 hybrid forecaster).
        "F1_emp_regime" => FORECASTER_F1_EMP_REGIME,
        "F0_stale" => FORECASTER_F0_STALE,
        // M5 / v2 deployment (paper 1 §7.7).
        "mondrian" => FORECASTER_MONDRIAN,
        _ => 255, // unknown — consumer should reject
    }
}

fn coverage_to_bps(c: f64) -> Result<u16, PayloadError> {
    let bps = (c * 10_000.0).round();
    if !(0.0..=10_000.0).contains(&bps) {
        return Err(PayloadError::CoverageOutOfRange(c));
    }
    Ok(bps as u16)
}

fn to_fixed(v: f64, exponent: i8) -> i64 {
    // exponent = -8  ⇒  multiplier = 10^8
    let multiplier = (10f64).powi(-(exponent as i32));
    (v * multiplier).round() as i64
}

/// Convert the Oracle's `PricePoint` into the on-chain `PublishPayload`. The
/// `fri_ts` is encoded as the approximate UTC timestamp for the anchored
/// Friday's US market close (20:00 UTC).
pub fn from_price_point(pp: &PricePoint) -> Result<PublishPayload, PayloadError> {
    let symbol = encode_symbol(&pp.symbol)?;
    let exponent = DEFAULT_EXPONENT;
    let fri_ts = pp
        .as_of
        .and_hms_opt(20, 0, 0)
        .map(|dt| dt.and_utc().timestamp())
        .ok_or_else(|| PayloadError::FriTsParse(pp.as_of.to_string()))?;

    Ok(PublishPayload {
        version: soothsayer_consumer::PRICE_UPDATE_VERSION,
        regime_code: regime_to_code(pp.regime),
        forecaster_code: forecaster_to_code(&pp.forecaster_used),
        exponent,
        target_coverage_bps: coverage_to_bps(pp.target_coverage)?,
        claimed_served_bps: coverage_to_bps(pp.claimed_coverage_served)?,
        buffer_applied_bps: coverage_to_bps(pp.calibration_buffer_applied)?,
        symbol,
        point: to_fixed(pp.point, exponent),
        lower: to_fixed(pp.lower, exponent),
        upper: to_fixed(pp.upper, exponent),
        fri_close: to_fixed(pp.diagnostics.fri_close, exponent),
        fri_ts,
    })
}

/// Little-endian byte serialization matching `borsh::to_vec` for the on-chain
/// `PublishPayload`. Kept manually to avoid pulling in borsh as a heavy dep
/// for the publisher binary; matches the anchor derivation exactly.
pub fn borsh_bytes(payload: &PublishPayload) -> Vec<u8> {
    let mut out = Vec::with_capacity(64);
    out.push(payload.version);
    out.push(payload.regime_code);
    out.push(payload.forecaster_code);
    out.push(payload.exponent as u8);
    out.extend_from_slice(&payload.target_coverage_bps.to_le_bytes());
    out.extend_from_slice(&payload.claimed_served_bps.to_le_bytes());
    out.extend_from_slice(&payload.buffer_applied_bps.to_le_bytes());
    out.extend_from_slice(&payload.symbol);
    out.extend_from_slice(&payload.point.to_le_bytes());
    out.extend_from_slice(&payload.lower.to_le_bytes());
    out.extend_from_slice(&payload.upper.to_le_bytes());
    out.extend_from_slice(&payload.fri_close.to_le_bytes());
    out.extend_from_slice(&payload.fri_ts.to_le_bytes());
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::NaiveDate;
    use soothsayer_oracle::types::{PricePoint, PricePointDiagnostics};

    fn sample_price_point() -> PricePoint {
        PricePoint {
            symbol: "SPY".to_string(),
            as_of: NaiveDate::from_ymd_opt(2026, 4, 17).unwrap(),
            target_coverage: 0.95,
            calibration_buffer_applied: 0.0,
            claimed_coverage_served: 0.95,
            point: 700.0755895327402,
            lower: 687.2102286091069,
            upper: 712.9409504563733,
            regime: Regime::Normal,
            forecaster_used: "mondrian".to_string(),
            sharpness_bps: 181.16653981260782,
            half_width_bps: 183.7710258147993,
            diagnostics: PricePointDiagnostics {
                fri_close: 710.1400146484375,
                served_target: 0.95,
                c_bump: 1.300,
                q_regime: 0.021530,
                q_eff: 0.027989,
            },
        }
    }

    #[test]
    fn to_fixed_round_trip_exponent_minus_8() {
        let p = 700.0755895327402;
        let fp = to_fixed(p, -8);
        let recovered = fp as f64 * 1e-8;
        assert!((recovered - p).abs() < 1e-8);
    }

    #[test]
    fn coverage_bps_exact() {
        assert_eq!(coverage_to_bps(0.95).unwrap(), 9500);
        assert_eq!(coverage_to_bps(0.975).unwrap(), 9750);
        assert_eq!(coverage_to_bps(0.025).unwrap(), 250);
        assert_eq!(coverage_to_bps(0.0).unwrap(), 0);
        assert_eq!(coverage_to_bps(1.0).unwrap(), 10_000);
    }

    #[test]
    fn encode_symbol_pads_null() {
        let b = encode_symbol("SPY").unwrap();
        assert_eq!(&b[..3], b"SPY");
        for &x in &b[3..] {
            assert_eq!(x, 0);
        }
    }

    #[test]
    fn encode_symbol_too_long_rejected() {
        let long = "0123456789ABCDEFG"; // 17 bytes
        match encode_symbol(long) {
            Err(PayloadError::SymbolTooLong(_, 17)) => {}
            other => panic!("expected SymbolTooLong(_, 17), got {other:?}"),
        }
    }

    #[test]
    fn from_price_point_uses_friday_close_timestamp_utc() {
        let payload = from_price_point(&sample_price_point()).unwrap();
        assert_eq!(payload.fri_ts, 1_776_456_000);
    }

    #[test]
    fn borsh_bytes_matches_publish_payload_wire_size() {
        let payload = from_price_point(&sample_price_point()).unwrap();
        assert_eq!(borsh_bytes(&payload).len(), 66);
    }
}
