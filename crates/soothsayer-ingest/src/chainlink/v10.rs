//! Chainlink Data Streams v10 report decoder.
//!
//! Schema v10 (feed-ID prefix `0x000a`): 13 ABI-encoded 32-byte words, total
//! 416 bytes. Integer fields are big-endian and right-aligned within their
//! word; i192 fields are sign-extended across the full 32 bytes so signed
//! 256-bit interpretation is correct.
//!
//! Field layout (word index → field):
//!
//! | # | Field                     | Rust type        |
//! |---|---------------------------|------------------|
//! | 0 | `feed_id`                 | `[u8; 32]`       |
//! | 1 | `valid_from_timestamp`    | `u32`            |
//! | 2 | `observations_timestamp`  | `u32`            |
//! | 3 | `native_fee`              | `u128` (trunc)   |
//! | 4 | `link_fee`                | `u128` (trunc)   |
//! | 5 | `expires_at`              | `u32`            |
//! | 6 | `last_seen_timestamp_ns`  | `u64`            |
//! | 7 | `mid` (raw 1e18-scaled)   | `i128` (trunc)   |
//! | 8 | `bid`                     | `i128` (trunc)   |
//! | 9 | `bid_volume`              | `i128` (trunc)   |
//! |10 | `ask`                     | `i128` (trunc)   |
//! |11 | `ask_volume`              | `i128` (trunc)   |
//! |12 | `last_traded_price`       | `i128` (trunc)   |
//!
//! The u192/i192 fields are truncated to u128/i128 for ergonomics. All fields
//! we actually use (prices and fees) fit comfortably inside 128 bits — decoded
//! mid is `price * 1e18`, so for a $100,000 asset the value is `1e23`, well
//! below `i128::MAX ≈ 1.7e38`. The decoder validates that the upper 16 bytes
//! are sign-extension; if not, it returns `OutOfRange`.

use chrono::{DateTime, TimeZone, Utc};
use soothsayer_core::{Error, Result};

pub const WORD: usize = 32;
pub const REPORT_LEN: usize = 13 * WORD;
pub const PRICE_SCALE: i128 = 1_000_000_000_000_000_000; // 1e18
pub const EQUITY_SCHEMA_V10: u16 = 0x000a;

/// A decoded v10 Chainlink Data Streams report. `*_raw` fields are 1e18-scaled
/// fixed-point. Use the helper accessors ([`mid`], [`bid`], ...) to get floats.
#[derive(Clone, Debug, PartialEq)]
pub struct V10Report {
    pub feed_id: [u8; 32],
    pub valid_from_timestamp: u32,
    pub observations_timestamp: u32,
    pub native_fee: u128,
    pub link_fee: u128,
    pub expires_at: u32,
    pub last_seen_timestamp_ns: u64,
    pub mid_raw: i128,
    pub bid_raw: i128,
    pub bid_volume_raw: i128,
    pub ask_raw: i128,
    pub ask_volume_raw: i128,
    pub last_traded_price_raw: i128,
}

impl V10Report {
    /// First two bytes of the feed ID — identifies the report schema.
    pub fn schema(&self) -> u16 {
        u16::from_be_bytes([self.feed_id[0], self.feed_id[1]])
    }

    pub fn feed_id_hex(&self) -> String {
        hex::encode(self.feed_id)
    }

    pub fn mid(&self) -> f64 {
        self.mid_raw as f64 / PRICE_SCALE as f64
    }

    pub fn bid(&self) -> f64 {
        self.bid_raw as f64 / PRICE_SCALE as f64
    }

    pub fn ask(&self) -> f64 {
        self.ask_raw as f64 / PRICE_SCALE as f64
    }

    pub fn last_traded_price(&self) -> f64 {
        self.last_traded_price_raw as f64 / PRICE_SCALE as f64
    }

    pub fn observations_at(&self) -> DateTime<Utc> {
        Utc.timestamp_opt(self.observations_timestamp as i64, 0)
            .single()
            .unwrap_or_else(|| Utc.timestamp_opt(0, 0).unwrap())
    }
}

fn word(bytes: &[u8], idx: usize) -> &[u8; WORD] {
    let start = idx * WORD;
    let slice = &bytes[start..start + WORD];
    slice.try_into().expect("word is exactly 32 bytes by construction")
}

/// Read a word as a `u128`. Upper 16 bytes must be zero.
fn read_u128(bytes: &[u8], idx: usize) -> Result<u128> {
    let w = word(bytes, idx);
    if w[..16].iter().any(|&b| b != 0) {
        return Err(Error::OutOfRange(format!("u128 overflow at word {idx}")));
    }
    Ok(u128::from_be_bytes(w[16..].try_into().unwrap()))
}

/// Read a word as a `u32`. All but the last 4 bytes must be zero.
fn read_u32(bytes: &[u8], idx: usize) -> Result<u32> {
    let w = word(bytes, idx);
    if w[..28].iter().any(|&b| b != 0) {
        return Err(Error::OutOfRange(format!("u32 overflow at word {idx}")));
    }
    Ok(u32::from_be_bytes(w[28..].try_into().unwrap()))
}

/// Read a word as a `u64`. All but the last 8 bytes must be zero.
fn read_u64(bytes: &[u8], idx: usize) -> Result<u64> {
    let w = word(bytes, idx);
    if w[..24].iter().any(|&b| b != 0) {
        return Err(Error::OutOfRange(format!("u64 overflow at word {idx}")));
    }
    Ok(u64::from_be_bytes(w[24..].try_into().unwrap()))
}

/// Read a word as an `i128`. Upper 16 bytes must be sign-extension of the lower 16.
fn read_i128(bytes: &[u8], idx: usize) -> Result<i128> {
    let w = word(bytes, idx);
    let is_negative = (w[0] & 0x80) != 0;
    let fill = if is_negative { 0xff } else { 0x00 };
    if w[..16].iter().any(|&b| b != fill) {
        return Err(Error::OutOfRange(format!("i128 overflow at word {idx}")));
    }
    Ok(i128::from_be_bytes(w[16..].try_into().unwrap()))
}

/// Decode a 416-byte v10 report payload.
pub fn decode(report: &[u8]) -> Result<V10Report> {
    if report.len() < REPORT_LEN {
        return Err(Error::Decode(format!(
            "report too short: {} bytes, need >= {REPORT_LEN}",
            report.len()
        )));
    }
    let feed_id: [u8; 32] = report[..WORD].try_into().unwrap();
    Ok(V10Report {
        feed_id,
        valid_from_timestamp: read_u32(report, 1)?,
        observations_timestamp: read_u32(report, 2)?,
        native_fee: read_u128(report, 3)?,
        link_fee: read_u128(report, 4)?,
        expires_at: read_u32(report, 5)?,
        last_seen_timestamp_ns: read_u64(report, 6)?,
        mid_raw: read_i128(report, 7)?,
        bid_raw: read_i128(report, 8)?,
        bid_volume_raw: read_i128(report, 9)?,
        ask_raw: read_i128(report, 10)?,
        ask_volume_raw: read_i128(report, 11)?,
        last_traded_price_raw: read_i128(report, 12)?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a synthetic v10 payload by encoding each field into its 32-byte slot.
    #[allow(clippy::too_many_arguments)]
    fn pack(
        feed_id: [u8; 32],
        valid_from: u32,
        observations: u32,
        native_fee: u128,
        link_fee: u128,
        expires: u32,
        last_seen_ns: u64,
        mid: i128,
        bid: i128,
        bid_vol: i128,
        ask: i128,
        ask_vol: i128,
        last_traded: i128,
    ) -> Vec<u8> {
        let mut out = Vec::with_capacity(REPORT_LEN);
        out.extend_from_slice(&feed_id);
        out.extend_from_slice(&left_pad_u32(valid_from));
        out.extend_from_slice(&left_pad_u32(observations));
        out.extend_from_slice(&left_pad_u128(native_fee));
        out.extend_from_slice(&left_pad_u128(link_fee));
        out.extend_from_slice(&left_pad_u32(expires));
        out.extend_from_slice(&left_pad_u64(last_seen_ns));
        out.extend_from_slice(&sign_extend_i128(mid));
        out.extend_from_slice(&sign_extend_i128(bid));
        out.extend_from_slice(&sign_extend_i128(bid_vol));
        out.extend_from_slice(&sign_extend_i128(ask));
        out.extend_from_slice(&sign_extend_i128(ask_vol));
        out.extend_from_slice(&sign_extend_i128(last_traded));
        out
    }

    fn left_pad_u32(v: u32) -> [u8; 32] {
        let mut w = [0u8; 32];
        w[28..].copy_from_slice(&v.to_be_bytes());
        w
    }
    fn left_pad_u64(v: u64) -> [u8; 32] {
        let mut w = [0u8; 32];
        w[24..].copy_from_slice(&v.to_be_bytes());
        w
    }
    fn left_pad_u128(v: u128) -> [u8; 32] {
        let mut w = [0u8; 32];
        w[16..].copy_from_slice(&v.to_be_bytes());
        w
    }
    fn sign_extend_i128(v: i128) -> [u8; 32] {
        let mut w = [0u8; 32];
        if v < 0 {
            w[..16].fill(0xff);
        }
        w[16..].copy_from_slice(&v.to_be_bytes());
        w
    }

    #[test]
    fn decode_synthetic_tslax_payload() {
        // Mirror a real TSLAx report captured from the live scraper:
        //   mid = $389.87, last_traded = $389.94, obs_ts = 2026-04-21 15:09:31 UTC.
        let mut feed_id = [0u8; 32];
        // TSLAx feedId prefix (schema 0x000a + real 30-byte remainder)
        hex::decode_to_slice(
            "000a80c655069b61d168b887d5e7f4231fe288c6ccb84b1854c9ccead20f3398",
            &mut feed_id,
        )
        .unwrap();

        let mid = (389.87_f64 * 1e18) as i128;
        let last_traded = (389.94_f64 * 1e18) as i128;
        let payload = pack(
            feed_id,
            1_776_755_371,
            1_776_755_371,
            0,
            0,
            1_776_841_771,
            1_776_755_371_000_000_000,
            mid,
            mid - 1,
            0,
            mid + 1,
            0,
            last_traded,
        );
        assert_eq!(payload.len(), REPORT_LEN);

        let r = decode(&payload).unwrap();
        assert_eq!(r.schema(), EQUITY_SCHEMA_V10);
        assert_eq!(r.feed_id, feed_id);
        assert_eq!(r.observations_timestamp, 1_776_755_371);
        assert!((r.mid() - 389.87).abs() < 1e-3);
        assert!((r.last_traded_price() - 389.94).abs() < 1e-3);
    }

    #[test]
    fn rejects_short_payload() {
        let err = decode(&[0u8; 100]).unwrap_err();
        assert!(matches!(err, Error::Decode(_)));
    }

    #[test]
    fn decode_negative_value_roundtrip() {
        let feed_id = [0x00, 0x0a, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0, 0, 0, 0, 0, 0, 0, 0,
                       0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        let payload = pack(feed_id, 1, 2, 0, 0, 3, 4, -42 * PRICE_SCALE, 0, 0, 0, 0, 0);
        let r = decode(&payload).unwrap();
        assert_eq!(r.mid_raw, -42 * PRICE_SCALE);
        assert!((r.mid() - -42.0).abs() < 1e-9);
    }
}
