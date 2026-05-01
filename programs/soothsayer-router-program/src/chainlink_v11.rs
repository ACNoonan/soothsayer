//! Chainlink Data Streams v11 report decoder.
//!
//! **Reference-only as of 2026-04-29 (afternoon).** Per the methodology entry
//! that date, Chainlink Data Streams on Solana doesn't publish passive PDAs
//! and the equity-feed schema on Solana is V8 (RWA), not v11. The router
//! consumes Chainlink via a soothsayer-controlled relay program (Option C);
//! the relay daemon does the off-chain decoding work. This module is
//! retained here as a near-template implementation for the relay daemon's
//! V8 decoder (similar word-aligned ABI structure with different field
//! count) and to preserve the wire-format research investment. It is not
//! called from any production code path; see `upstreams.rs::read_chainlink_streams_relay`
//! for the live decoder, which reads a soothsayer-controlled relay PDA.
//!
//! Pure-Rust port of `src/soothsayer/chainlink/v11.py`. ABI-encoded report:
//! 14 fields, one 32-byte word each, total 448 bytes. Integer fields are
//! big-endian and right-aligned; i192 fields are sign-extended across the
//! full 32-byte word, so an i192 that fits in i128 has the upper 16 bytes as
//! sign-extension fill (0x00 for non-negative, 0xff for negative).
//!
//! Schema reference (matches the upstream SDK):
//!   smartcontractkit/data-streams-sdk/rust/crates/report/src/report/v11.rs
//!
//! No external deps: this file is BPF/SBF-friendly and runs on-chain.
//!
//! Word layout:
//! ```text
//!   0: feed_id                bytes32
//!   1: valid_from_timestamp   u32     (in low 4 bytes of word)
//!   2: observations_timestamp u32
//!   3: native_fee             u192    (discarded — fee plumbing)
//!   4: link_fee               u192    (discarded)
//!   5: expires_at             u32
//!   6: mid                    i192    ← DON-consensus benchmark price
//!   7: last_seen_timestamp_ns u64
//!   8: bid                    i192
//!   9: bid_volume             i192    (discarded)
//!  10: ask                    i192
//!  11: ask_volume             i192    (discarded)
//!  12: last_traded_price      i192
//!  13: market_status          u32     (0..5)
//! ```

const WORD: usize = 32;
pub const REPORT_LEN: usize = 14 * WORD; // 448 bytes

/// market_status discriminants (matches the Python `MARKET_STATUS` map).
pub const STATUS_UNKNOWN: u32 = 0;
pub const STATUS_PRE_MARKET: u32 = 1;
pub const STATUS_REGULAR: u32 = 2;
pub const STATUS_POST_MARKET: u32 = 3;
pub const STATUS_OVERNIGHT: u32 = 4;
pub const STATUS_CLOSED: u32 = 5;

/// Decoded subset of the v11 report carrying every field soothsayer's router
/// uses. The volume fields and fee fields are intentionally discarded — the
/// router does not consume them and dropping them halves the snapshot size.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct V11Report {
    pub feed_id: [u8; 32],
    pub valid_from_timestamp: u32,
    pub observations_timestamp: u32,
    pub expires_at: u32,
    /// 18-decimal fixed-point. Convert via `to_fixed_point(target_exponent)`.
    pub mid_raw: i128,
    pub last_seen_timestamp_ns: u64,
    pub bid_raw: i128,
    pub ask_raw: i128,
    pub last_traded_price_raw: i128,
    pub market_status: u32,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DecodeError {
    /// Account data shorter than `REPORT_LEN`.
    TooShort { got: usize, need: usize },
    /// An i192 field's upper 16 bytes are not sign-extension of its lower 16,
    /// meaning the value doesn't fit in i128. In practice this never happens
    /// for USD prices ≤ $10^20.
    PriceOverflowsI128,
    /// A u32/u64 field has non-zero high bytes — corrupt or unexpected layout.
    HighByteOverflow,
    /// The exponent gap between v11's 18-decimal and the target snapshot
    /// exponent is too large to convert without overflow.
    ExponentOutOfRange,
}

/// Decode a 448-byte v11 raw report payload. Returns `DecodeError::TooShort`
/// if the input is shorter than `REPORT_LEN`; bytes beyond `REPORT_LEN` are
/// silently ignored (caller's responsibility to slice if needed).
pub fn decode(report: &[u8]) -> Result<V11Report, DecodeError> {
    if report.len() < REPORT_LEN {
        return Err(DecodeError::TooShort {
            got: report.len(),
            need: REPORT_LEN,
        });
    }

    let feed_id: [u8; 32] = read_word(report, 0).try_into().expect("32-byte word");
    let valid_from_timestamp = read_u32_low(report, 1)?;
    let observations_timestamp = read_u32_low(report, 2)?;
    // word 3 = native_fee (u192) — discarded
    // word 4 = link_fee   (u192) — discarded
    let expires_at = read_u32_low(report, 5)?;
    let mid_raw = read_i192_as_i128(report, 6)?;
    let last_seen_timestamp_ns = read_u64_low(report, 7)?;
    let bid_raw = read_i192_as_i128(report, 8)?;
    // word 9 = bid_volume — discarded
    let ask_raw = read_i192_as_i128(report, 10)?;
    // word 11 = ask_volume — discarded
    let last_traded_price_raw = read_i192_as_i128(report, 12)?;
    let market_status = read_u32_low(report, 13)?;

    Ok(V11Report {
        feed_id,
        valid_from_timestamp,
        observations_timestamp,
        expires_at,
        mid_raw,
        last_seen_timestamp_ns,
        bid_raw,
        ask_raw,
        last_traded_price_raw,
        market_status,
    })
}

/// Convert an 18-decimal raw value to the requested target exponent.
/// `target_exponent` follows the Pyth/soothsayer convention: -8 means
/// "8 decimal places" (real_value = raw × 10^target_exponent). Returns
/// `ExponentOutOfRange` if the conversion would overflow i64.
pub fn to_fixed_point_i64(raw_18d: i128, target_exponent: i8) -> Result<i64, DecodeError> {
    // v11 prices are at exponent -18; convert to target_exponent.
    let from_exp: i32 = -18;
    let to_exp: i32 = target_exponent as i32;
    let exp_diff: i32 = to_exp - from_exp;

    let scaled: i128 = if exp_diff > 0 {
        // target has fewer decimals → divide
        if exp_diff > 38 {
            return Err(DecodeError::ExponentOutOfRange);
        }
        let divisor = 10_i128
            .checked_pow(exp_diff as u32)
            .ok_or(DecodeError::ExponentOutOfRange)?;
        raw_18d / divisor
    } else if exp_diff < 0 {
        if -exp_diff > 38 {
            return Err(DecodeError::ExponentOutOfRange);
        }
        let multiplier = 10_i128
            .checked_pow((-exp_diff) as u32)
            .ok_or(DecodeError::ExponentOutOfRange)?;
        raw_18d
            .checked_mul(multiplier)
            .ok_or(DecodeError::ExponentOutOfRange)?
    } else {
        raw_18d
    };

    scaled
        .try_into()
        .map_err(|_| DecodeError::ExponentOutOfRange)
}

fn read_word(report: &[u8], idx: usize) -> &[u8] {
    &report[idx * WORD..(idx + 1) * WORD]
}

fn read_u32_low(report: &[u8], idx: usize) -> Result<u32, DecodeError> {
    let w = read_word(report, idx);
    // First 28 bytes must be zero — u32 lives in the low 4 bytes.
    if w[..28].iter().any(|&b| b != 0) {
        return Err(DecodeError::HighByteOverflow);
    }
    Ok(u32::from_be_bytes([w[28], w[29], w[30], w[31]]))
}

fn read_u64_low(report: &[u8], idx: usize) -> Result<u64, DecodeError> {
    let w = read_word(report, idx);
    if w[..24].iter().any(|&b| b != 0) {
        return Err(DecodeError::HighByteOverflow);
    }
    let mut bytes = [0u8; 8];
    bytes.copy_from_slice(&w[24..32]);
    Ok(u64::from_be_bytes(bytes))
}

/// Read an i192 stored as a 32-byte sign-extended word and return as i128.
/// Errors if the upper 16 bytes are not the proper sign-extension of the
/// lower 16 — meaning the value doesn't fit in i128.
fn read_i192_as_i128(report: &[u8], idx: usize) -> Result<i128, DecodeError> {
    let w = read_word(report, idx);
    let mut lower = [0u8; 16];
    lower.copy_from_slice(&w[16..32]);
    let val_i128 = i128::from_be_bytes(lower);

    // For an i128-fitting value, the upper 16 bytes (positions 0..15) must
    // all equal the sign-extension fill of the i128.
    let expected_fill: u8 = if val_i128 < 0 { 0xff } else { 0x00 };
    if w[..16].iter().any(|&b| b != expected_fill) {
        return Err(DecodeError::PriceOverflowsI128);
    }
    Ok(val_i128)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn put_u32_low(buf: &mut [u8], val: u32) {
        // buf is the 32-byte word slice; writes into bytes 28..32.
        buf[28..32].copy_from_slice(&val.to_be_bytes());
    }

    fn put_i192_from_i128(buf: &mut [u8], val: i128) {
        let fill: u8 = if val < 0 { 0xff } else { 0x00 };
        for b in &mut buf[..16] {
            *b = fill;
        }
        buf[16..32].copy_from_slice(&val.to_be_bytes());
    }

    fn build_report(
        mid: i128,
        bid: i128,
        ask: i128,
        last_traded: i128,
        market_status: u32,
        observations_ts: u32,
    ) -> Vec<u8> {
        let mut bytes = vec![0u8; REPORT_LEN];
        // word 0: feed_id (any 32 bytes)
        for byte in bytes.iter_mut().take(32) {
            *byte = 1;
        }
        // word 1: valid_from_timestamp
        put_u32_low(&mut bytes[32..64], observations_ts.saturating_sub(5));
        // word 2: observations_timestamp
        put_u32_low(&mut bytes[64..96], observations_ts);
        // word 5: expires_at
        put_u32_low(&mut bytes[160..192], observations_ts.saturating_add(60));
        // word 6: mid
        put_i192_from_i128(&mut bytes[192..224], mid);
        // word 8: bid
        put_i192_from_i128(&mut bytes[256..288], bid);
        // word 10: ask
        put_i192_from_i128(&mut bytes[320..352], ask);
        // word 12: last_traded_price
        put_i192_from_i128(&mut bytes[384..416], last_traded);
        // word 13: market_status
        put_u32_low(&mut bytes[416..448], market_status);
        bytes
    }

    #[test]
    fn decodes_synthetic_report() {
        // SPY at $528.42, 18-decimal: 528.42 × 10^18 = 528_420_000_000_000_000_000
        let mid: i128 = 528_420_000_000_000_000_000;
        let bid: i128 = 528_400_000_000_000_000_000;
        let ask: i128 = 528_440_000_000_000_000_000;
        let ltp: i128 = 528_420_000_000_000_000_000;
        let report = build_report(mid, bid, ask, ltp, STATUS_REGULAR, 1_761_700_000);
        let r = decode(&report).unwrap();
        assert_eq!(r.mid_raw, mid);
        assert_eq!(r.bid_raw, bid);
        assert_eq!(r.ask_raw, ask);
        assert_eq!(r.last_traded_price_raw, ltp);
        assert_eq!(r.market_status, STATUS_REGULAR);
        assert_eq!(r.observations_timestamp, 1_761_700_000);
    }

    #[test]
    fn decodes_negative_value_with_sign_extension() {
        let report =
            build_report(-100_000_000_000_000_000_000, 0, 0, 0, STATUS_REGULAR, 1_700_000_000);
        let r = decode(&report).unwrap();
        assert!(r.mid_raw < 0);
    }

    #[test]
    fn decodes_closed_status() {
        let report =
            build_report(528_420_000_000_000_000_000, 0, 0, 0, STATUS_CLOSED, 1_700_000_000);
        let r = decode(&report).unwrap();
        assert_eq!(r.market_status, STATUS_CLOSED);
    }

    #[test]
    fn rejects_short_report() {
        let too_short = vec![0u8; 100];
        assert!(matches!(
            decode(&too_short),
            Err(DecodeError::TooShort { .. })
        ));
    }

    #[test]
    fn detects_i192_value_that_overflows_i128() {
        let mut bytes = vec![0u8; REPORT_LEN];
        // Word 6 (mid) — set bytes 0..15 to non-sign-extension; bytes 16..31 stay zero.
        // val_i128 will be 0 (positive); expected_fill = 0x00; our 0x80 byte fails.
        bytes[192] = 0x80;
        // (Other words can stay zero — decode hits word 6 first via the order
        // of field reads, but the timestamp words are read before mid.
        // Make sure those are valid: word 1, 2, 5 = 0 is fine.)
        let err = decode(&bytes).unwrap_err();
        assert_eq!(err, DecodeError::PriceOverflowsI128);
    }

    #[test]
    fn detects_corrupt_high_bytes_in_u32_field() {
        let mut bytes = vec![0u8; REPORT_LEN];
        // Word 1 (valid_from_timestamp) — set byte 0 to non-zero.
        bytes[32] = 0xff;
        let err = decode(&bytes).unwrap_err();
        assert_eq!(err, DecodeError::HighByteOverflow);
    }

    #[test]
    fn fixed_point_conversion_18d_to_minus8() {
        // 528.42 in 18-decimal → 52_842_000_000 in 8-decimal
        let raw_18d: i128 = 528_420_000_000_000_000_000;
        let got = to_fixed_point_i64(raw_18d, -8).unwrap();
        assert_eq!(got, 52_842_000_000);
    }

    #[test]
    fn fixed_point_conversion_18d_to_minus6() {
        // 528.42 in 18-decimal → 528_420_000 in 6-decimal
        let raw_18d: i128 = 528_420_000_000_000_000_000;
        let got = to_fixed_point_i64(raw_18d, -6).unwrap();
        assert_eq!(got, 528_420_000);
    }

    #[test]
    fn fixed_point_conversion_negative_value() {
        let raw_18d: i128 = -528_420_000_000_000_000_000;
        let got = to_fixed_point_i64(raw_18d, -8).unwrap();
        assert_eq!(got, -52_842_000_000);
    }

    #[test]
    fn fixed_point_conversion_zero() {
        assert_eq!(to_fixed_point_i64(0, -8).unwrap(), 0);
    }

    #[test]
    fn fixed_point_conversion_overflow_errors() {
        // i128::MAX in 18-decimal cannot fit in i64 at -8 exponent
        let huge: i128 = i128::MAX;
        assert!(to_fixed_point_i64(huge, -8).is_err());
    }
}
