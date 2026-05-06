//! Soothsayer consumer SDK.
//!
//! A minimal, dependency-light decoder for the Soothsayer `PriceUpdate`
//! account layout. Downstream consumers (Kamino fork, Jupiter Lend, any
//! Solana lending / perp protocol) link this instead of pulling the full
//! Anchor program crate with its BPF-targeted dependencies.
//!
//! The decoder mirrors `programs/soothsayer-oracle-program/src/state.rs`
//! byte-for-byte — update both in lockstep on any schema bump.

#![no_std]

use core::mem;
use thiserror::Error;

/// Anchor's 8-byte discriminator prefix on every account.
pub const ACCOUNT_DISCRIMINATOR_SIZE: usize = 8;

/// Regime codes — keep in sync with program state.rs.
pub const REGIME_NORMAL: u8 = 0;
pub const REGIME_LONG_WEEKEND: u8 = 1;
pub const REGIME_HIGH_VOL: u8 = 2;
pub const REGIME_SHOCK_FLAGGED: u8 = 3;

/// Typed pre-publish regime. Numeric codes above are the on-chain wire
/// representation; this enum is the ergonomic Rust-consumer view.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Regime {
    Normal,
    LongWeekend,
    HighVol,
    /// Reserved — not used by the current Oracle, but a v1b-era forecaster
    /// could populate it. Consumers should treat this identically to HighVol
    /// for safety (widen everything).
    ShockFlagged,
}

impl Regime {
    pub fn from_code(code: u8) -> Option<Self> {
        match code {
            REGIME_NORMAL => Some(Self::Normal),
            REGIME_LONG_WEEKEND => Some(Self::LongWeekend),
            REGIME_HIGH_VOL => Some(Self::HighVol),
            REGIME_SHOCK_FLAGGED => Some(Self::ShockFlagged),
            _ => None,
        }
    }

    pub fn to_code(self) -> u8 {
        match self {
            Self::Normal => REGIME_NORMAL,
            Self::LongWeekend => REGIME_LONG_WEEKEND,
            Self::HighVol => REGIME_HIGH_VOL,
            Self::ShockFlagged => REGIME_SHOCK_FLAGGED,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Normal => "normal",
            Self::LongWeekend => "long_weekend",
            Self::HighVol => "high_vol",
            Self::ShockFlagged => "shock_flagged",
        }
    }
}

/// Forecaster codes — keep in sync with `programs/soothsayer-oracle-program/src/state.rs`.
///
/// Codes 0 and 1 are retained for receipts emitted by Soothsayer-v0
/// (paper 1 §2.1 hybrid forecaster). From M5 onward the live on-chain
/// code is `FORECASTER_MONDRIAN` (= 2); from M6 onward (paper 1 §4
/// deployed) the wire-format slot for the locally-weighted variant is
/// `FORECASTER_LWC` (= 3). Older codes are still recognised here so
/// historical PriceUpdate accounts decode cleanly.
pub const FORECASTER_F1_EMP_REGIME: u8 = 0;
pub const FORECASTER_F0_STALE: u8 = 1;
pub const FORECASTER_MONDRIAN: u8 = 2;
pub const FORECASTER_LWC: u8 = 3;

/// Typed forecaster view over the wire `forecaster_code` byte. Mirror of
/// `Forecaster` in `crates/soothsayer-oracle/src/types.rs`, plus the legacy
/// Soothsayer-v0 variants that may appear in pre-M5 in-flight accounts.
///
/// Consumer responsibility: assert `band.forecaster()` matches the
/// integration spec. New M5 / M6 integrations should accept Mondrian and/or
/// Lwc and reject the legacy variants.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Forecaster {
    /// Soothsayer-v0 F1 empirical-regime forecaster (pre-M5 receipts).
    F1EmpRegime,
    /// Soothsayer-v0 F0 stale-hold fallback (pre-M5 receipts).
    F0Stale,
    /// M5 per-regime split-conformal Mondrian (live on-chain).
    Mondrian,
    /// M6 locally-weighted Mondrian split-conformal (deployed; on-chain
    /// slot reserved pending Rust-port-driven publish enablement).
    Lwc,
}

impl Forecaster {
    pub fn from_code(code: u8) -> Option<Self> {
        match code {
            FORECASTER_F1_EMP_REGIME => Some(Self::F1EmpRegime),
            FORECASTER_F0_STALE => Some(Self::F0Stale),
            FORECASTER_MONDRIAN => Some(Self::Mondrian),
            FORECASTER_LWC => Some(Self::Lwc),
            _ => None,
        }
    }

    pub fn to_code(self) -> u8 {
        match self {
            Self::F1EmpRegime => FORECASTER_F1_EMP_REGIME,
            Self::F0Stale => FORECASTER_F0_STALE,
            Self::Mondrian => FORECASTER_MONDRIAN,
            Self::Lwc => FORECASTER_LWC,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::F1EmpRegime => "F1_emp_regime",
            Self::F0Stale => "F0_stale",
            Self::Mondrian => "mondrian",
            Self::Lwc => "lwc",
        }
    }
}

/// Serving-profile codes (reports/active/m6_refactor.md A4). Code 0 is reserved for
/// pre-A4 in-flight `PriceUpdate` accounts whose `_pad0` byte 0 was zero.
/// New publishes set 1 (lending) or 2 (amm).
pub const PROFILE_LEGACY: u8 = 0;
pub const PROFILE_LENDING: u8 = 1;
pub const PROFILE_AMM: u8 = 2;

/// Typed serving-profile view. Mirror of `Profile` in
/// `crates/soothsayer-oracle/src/types.rs`, plus the `Legacy` variant
/// for pre-A4 receipts.
///
/// Consumer responsibility: assert `band.profile()` matches the integration
/// spec (e.g. a Kamino lending market should refuse a Profile::Amm read).
/// Treating `Profile::Legacy` as a Lending receipt is acceptable on the
/// historical pre-A4 deployment slot, but new integrations should reject it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Profile {
    /// Pre-A4 single-profile receipt; semantically equivalent to a
    /// pre-M6b2 M5 read.
    Legacy,
    /// M6b2 per-symbol_class Mondrian (Lending track).
    Lending,
    /// M5 per-regime Mondrian (AMM track interim).
    Amm,
}

impl Profile {
    pub fn from_code(code: u8) -> Option<Self> {
        match code {
            PROFILE_LEGACY => Some(Self::Legacy),
            PROFILE_LENDING => Some(Self::Lending),
            PROFILE_AMM => Some(Self::Amm),
            _ => None,
        }
    }

    pub fn to_code(self) -> u8 {
        match self {
            Self::Legacy => PROFILE_LEGACY,
            Self::Lending => PROFILE_LENDING,
            Self::Amm => PROFILE_AMM,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Legacy => "legacy",
            Self::Lending => "lending",
            Self::Amm => "amm",
        }
    }
}

pub const PRICE_UPDATE_VERSION: u8 = 1;

/// Typed view over the `PriceUpdate` account data. All fields are primitives
/// so downstream consumers can treat this as a plain old data struct.
#[derive(Clone, Debug, PartialEq)]
pub struct PriceBand {
    pub version: u8,
    pub regime_code: u8,
    pub forecaster_code: u8,
    pub exponent: i8,
    /// Serving profile (0 = legacy/pre-A4, 1 = lending, 2 = amm). Use
    /// [`Profile::from_code`] for the typed view.
    pub profile_code: u8,
    pub target_coverage_bps: u16,
    pub claimed_served_bps: u16,
    pub buffer_applied_bps: u16,
    pub symbol: [u8; 16],
    pub point: i64,
    pub lower: i64,
    pub upper: i64,
    pub fri_close: i64,
    pub fri_ts: i64,
    pub publish_ts: i64,
    pub publish_slot: u64,
    pub signer: [u8; 32],
    pub signer_epoch: u64,
}

impl PriceBand {
    /// Scale factor (10^exponent) for converting fixed-point prices to f64.
    pub fn scale(&self) -> f64 {
        libm_pow(10.0, self.exponent as i32)
    }

    pub fn point_f64(&self) -> f64 {
        self.point as f64 * self.scale()
    }
    pub fn lower_f64(&self) -> f64 {
        self.lower as f64 * self.scale()
    }
    pub fn upper_f64(&self) -> f64 {
        self.upper as f64 * self.scale()
    }
    pub fn fri_close_f64(&self) -> f64 {
        self.fri_close as f64 * self.scale()
    }

    pub fn half_width_bps(&self) -> f64 {
        let p = self.point_f64();
        if p == 0.0 {
            0.0
        } else {
            (self.upper_f64() - self.lower_f64()) / 2.0 / p * 1e4
        }
    }

    /// Symbol as a trimmed string slice (stops at the first null byte).
    pub fn symbol_str(&self) -> &str {
        let end = self.symbol.iter().position(|&b| b == 0).unwrap_or(self.symbol.len());
        core::str::from_utf8(&self.symbol[..end]).unwrap_or("")
    }

    /// Typed serving profile. Returns `None` if the on-chain `profile_code`
    /// is not a value this SDK version recognises (forward-compat: a future
    /// program upgrade could add code 3 etc.).
    pub fn profile(&self) -> Option<Profile> {
        Profile::from_code(self.profile_code)
    }

    /// Typed serving forecaster. Returns `None` if the on-chain
    /// `forecaster_code` is not a value this SDK version recognises.
    /// Pre-M5 receipts decode as `F1EmpRegime` / `F0Stale`; M5 receipts as
    /// `Mondrian`; M6 receipts as `Lwc`.
    pub fn forecaster(&self) -> Option<Forecaster> {
        Forecaster::from_code(self.forecaster_code)
    }

    /// Check the core band invariant: lower ≤ point ≤ upper.
    pub fn validate_invariants(&self) -> Result<(), DecodeError> {
        if self.version != PRICE_UPDATE_VERSION {
            return Err(DecodeError::VersionMismatch {
                expected: PRICE_UPDATE_VERSION,
                found: self.version,
            });
        }
        if !(self.lower <= self.point && self.point <= self.upper) {
            return Err(DecodeError::InvariantViolated);
        }
        if self.target_coverage_bps > 10_000
            || self.claimed_served_bps > 10_000
            || self.buffer_applied_bps > 10_000
        {
            return Err(DecodeError::CoverageOutOfRange);
        }
        Ok(())
    }
}

#[derive(Debug, Error, Clone, Copy, PartialEq)]
pub enum DecodeError {
    #[error("account data too short: {0} bytes")]
    TooShort(usize),

    #[error("wrong anchor discriminator (expected PriceUpdate)")]
    WrongDiscriminator,

    #[error("price update version mismatch: expected {expected}, found {found}")]
    VersionMismatch { expected: u8, found: u8 },

    #[error("band invariant violated (need lower ≤ point ≤ upper)")]
    InvariantViolated,

    #[error("coverage or buffer basis points out of range (must be ≤ 10000)")]
    CoverageOutOfRange,
}

/// Anchor discriminator for the `PriceUpdate` account — first 8 bytes of
/// `sha256("account:PriceUpdate")`. Exposed as a constant so consumer protocols
/// can verify before decoding.
///
/// Anchor computes this as `sha256("account:<TypeName>")[..8]`. Computed offline
/// and embedded here to keep this crate no_std.
///
/// Verified against the live `HfMaU9Qa54fp1V3uh11Qec81RgKUgzT6mxvFkmZ6V3LH`
/// SPY PriceUpdate PDA on devnet (program `AgXLLTmUJEVh9EsJnznU1yJaUeE9Ufe7ZotupmDqa7f6`).
/// The pre-2026-05-02 constant `[149, 40, 25, 155, 47, 226, 14, 198]` was
/// internally consistent (synth tests round-tripped) but wrong on chain — the
/// BandAMM swap path failed `BandRejected` until this was fixed.
pub const PRICE_UPDATE_DISCRIMINATOR: [u8; 8] = [105, 54, 115, 246, 58, 216, 66, 178];

/// Decode an on-chain `PriceUpdate` account's raw bytes into a typed [`PriceBand`].
///
/// Expected input shape: 8-byte Anchor discriminator + serialized struct.
/// This is a straight memcpy-style decoder — fields are read little-endian
/// in the exact order and padding the on-chain struct uses.
pub fn decode_price_update(data: &[u8]) -> Result<PriceBand, DecodeError> {
    let expected_size = ACCOUNT_DISCRIMINATOR_SIZE + PRICE_UPDATE_DATA_SIZE;
    if data.len() < expected_size {
        return Err(DecodeError::TooShort(data.len()));
    }
    let disc = &data[..ACCOUNT_DISCRIMINATOR_SIZE];
    if disc != PRICE_UPDATE_DISCRIMINATOR {
        return Err(DecodeError::WrongDiscriminator);
    }
    let body = &data[ACCOUNT_DISCRIMINATOR_SIZE..];

    // Field offsets mirror state.rs exactly; padding bytes are skipped but
    // present on-chain so accounts are aligned.
    let mut o = 0;
    let version = body[o]; o += 1;
    let regime_code = body[o]; o += 1;
    let forecaster_code = body[o]; o += 1;
    let exponent = body[o] as i8; o += 1;
    // reports/active/m6_refactor.md A4: byte 4 was formerly `_pad0[0]` (always zero on
    // pre-A4 publishes). New publishes write the profile_code there.
    // Old in-flight accounts naturally decode as profile_code = 0
    // (Profile::Legacy).
    let profile_code = body[o]; o += 1;
    o += 3; // _pad0[1..4]
    let target_coverage_bps = u16::from_le_bytes([body[o], body[o+1]]); o += 2;
    let claimed_served_bps = u16::from_le_bytes([body[o], body[o+1]]); o += 2;
    let buffer_applied_bps = u16::from_le_bytes([body[o], body[o+1]]); o += 2;
    o += 2; // _pad1
    let mut symbol = [0u8; 16];
    symbol.copy_from_slice(&body[o..o+16]); o += 16;
    let point = i64::from_le_bytes(body[o..o+8].try_into().unwrap()); o += 8;
    let lower = i64::from_le_bytes(body[o..o+8].try_into().unwrap()); o += 8;
    let upper = i64::from_le_bytes(body[o..o+8].try_into().unwrap()); o += 8;
    let fri_close = i64::from_le_bytes(body[o..o+8].try_into().unwrap()); o += 8;
    let fri_ts = i64::from_le_bytes(body[o..o+8].try_into().unwrap()); o += 8;
    let publish_ts = i64::from_le_bytes(body[o..o+8].try_into().unwrap()); o += 8;
    let publish_slot = u64::from_le_bytes(body[o..o+8].try_into().unwrap()); o += 8;
    let mut signer = [0u8; 32];
    signer.copy_from_slice(&body[o..o+32]); o += 32;
    let signer_epoch = u64::from_le_bytes(body[o..o+8].try_into().unwrap());

    Ok(PriceBand {
        version, regime_code, forecaster_code, exponent, profile_code,
        target_coverage_bps, claimed_served_bps, buffer_applied_bps,
        symbol,
        point, lower, upper, fri_close,
        fri_ts, publish_ts, publish_slot,
        signer, signer_epoch,
    })
}

/// Raw byte size of the PriceUpdate struct (excluding 8-byte discriminator).
/// Hand-computed to match state.rs; if the struct changes, bump here.
/// Sum: 8 + 8 + 16 + 32 + 24 + 32 + 8 = 128.
pub const PRICE_UPDATE_DATA_SIZE: usize =
      (1 + 1 + 1 + 1 + 4)       // version, regime, forecaster, exponent, _pad0   = 8
    + (2 + 2 + 2 + 2)           // target_bps, served_bps, buffer_bps, _pad1      = 8
    + 16                        // symbol                                         = 16
    + (8 + 8 + 8 + 8)           // point, lower, upper, fri_close                 = 32
    + (8 + 8 + 8)               // fri_ts, publish_ts, publish_slot               = 24
    + 32                        // signer                                         = 32
    + 8;                        // signer_epoch                                   = 8

/// Minimal `pow` for no_std — only needs integer exponents.
fn libm_pow(base: f64, exp: i32) -> f64 {
    let mut result = 1.0f64;
    let mut e = exp;
    if e < 0 {
        while e < 0 {
            result /= base;
            e += 1;
        }
        return result;
    }
    while e > 0 {
        result *= base;
        e -= 1;
    }
    result
}

// Avoid unused import warning when mem isn't needed.
const _: fn() = || {
    let _ = mem::size_of::<PriceBand>();
};

#[cfg(test)]
extern crate alloc;

#[cfg(test)]
mod tests {
    use super::*;
    use alloc::vec::Vec;

    #[test]
    fn data_size_matches_hand_calc() {
        assert_eq!(PRICE_UPDATE_DATA_SIZE, 128);
    }

    #[test]
    fn too_short_rejected() {
        let data = [0u8; 10];
        assert_eq!(
            decode_price_update(&data),
            Err(DecodeError::TooShort(10))
        );
    }

    #[test]
    fn symbol_str_trims_null_padding() {
        let mut band = PriceBand {
            version: 1, regime_code: 0, forecaster_code: 0, exponent: -8,
            profile_code: PROFILE_LENDING,
            target_coverage_bps: 9500, claimed_served_bps: 9750, buffer_applied_bps: 250,
            symbol: [0; 16],
            // At exponent=-8, each integer unit is 10^-8; $700 = 700 * 10^8 = 70_000_000_000
            point: 70_000_000_000, lower: 69_000_000_000, upper: 71_000_000_000,
            fri_close: 71_000_000_000, fri_ts: 0, publish_ts: 0, publish_slot: 0,
            signer: [0; 32], signer_epoch: 0,
        };
        band.symbol[..3].copy_from_slice(b"SPY");
        assert_eq!(band.symbol_str(), "SPY");
        // point = 700 * 10^8 at exponent -8  ⇒  $700.00
        assert!((band.point_f64() - 700.0).abs() < 1e-9);
    }

    #[test]
    fn invariant_check_passes_good() {
        let band = PriceBand {
            version: 1, regime_code: 0, forecaster_code: 0, exponent: -8,
            profile_code: PROFILE_LENDING,
            target_coverage_bps: 9500, claimed_served_bps: 9750, buffer_applied_bps: 250,
            symbol: [0; 16],
            point: 700, lower: 680, upper: 720,
            fri_close: 710, fri_ts: 0, publish_ts: 0, publish_slot: 0,
            signer: [0; 32], signer_epoch: 0,
        };
        assert!(band.validate_invariants().is_ok());
    }

    #[test]
    fn invariant_check_rejects_inverted_band() {
        let band = PriceBand {
            version: 1, regime_code: 0, forecaster_code: 0, exponent: -8,
            profile_code: PROFILE_LENDING,
            target_coverage_bps: 9500, claimed_served_bps: 9750, buffer_applied_bps: 250,
            symbol: [0; 16],
            point: 700, lower: 720, upper: 680,  // inverted — should be caught
            fri_close: 710, fri_ts: 0, publish_ts: 0, publish_slot: 0,
            signer: [0; 32], signer_epoch: 0,
        };
        assert_eq!(band.validate_invariants(), Err(DecodeError::InvariantViolated));
    }

    /// Synthesize a full on-wire `PriceUpdate` account body (8-byte
    /// discriminator + 128-byte struct). Defaults to forecaster_code =
    /// FORECASTER_MONDRIAN; use `synth_account_bytes_with_forecaster` to
    /// override (e.g. to test LWC decode). The `profile_code` byte goes
    /// into the repurposed `_pad0[0]` slot.
    fn synth_account_bytes(profile_code: u8) -> Vec<u8> {
        synth_account_bytes_with_forecaster(profile_code, FORECASTER_MONDRIAN)
    }

    fn synth_account_bytes_with_forecaster(profile_code: u8, forecaster_code: u8) -> Vec<u8> {
        let mut data = Vec::with_capacity(8 + PRICE_UPDATE_DATA_SIZE);
        data.extend_from_slice(&PRICE_UPDATE_DISCRIMINATOR);
        data.push(1);                  // version
        data.push(REGIME_NORMAL);      // regime_code
        data.push(forecaster_code);    // forecaster_code
        data.push((-8i8) as u8);       // exponent
        data.push(profile_code);       // _pad0[0] → profile_code
        data.extend_from_slice(&[0u8; 3]); // _pad0[1..4]
        data.extend_from_slice(&9500u16.to_le_bytes()); // target_coverage_bps
        data.extend_from_slice(&9500u16.to_le_bytes()); // claimed_served_bps
        data.extend_from_slice(&0u16.to_le_bytes());    // buffer_applied_bps
        data.extend_from_slice(&[0u8; 2]);             // _pad1
        let mut symbol = [0u8; 16];
        symbol[..3].copy_from_slice(b"SPY");
        data.extend_from_slice(&symbol);
        data.extend_from_slice(&70_000_000_000i64.to_le_bytes()); // point
        data.extend_from_slice(&69_000_000_000i64.to_le_bytes()); // lower
        data.extend_from_slice(&71_000_000_000i64.to_le_bytes()); // upper
        data.extend_from_slice(&71_000_000_000i64.to_le_bytes()); // fri_close
        data.extend_from_slice(&0i64.to_le_bytes()); // fri_ts
        data.extend_from_slice(&0i64.to_le_bytes()); // publish_ts
        data.extend_from_slice(&0u64.to_le_bytes()); // publish_slot
        data.extend_from_slice(&[0u8; 32]);          // signer
        data.extend_from_slice(&0u64.to_le_bytes()); // signer_epoch
        assert_eq!(data.len(), 8 + PRICE_UPDATE_DATA_SIZE);
        data
    }

    #[test]
    fn decode_legacy_account_yields_profile_zero() {
        // Pre-A4 in-flight account: byte 4 was the first byte of `_pad0`,
        // always zero. New consumer must decode it as PROFILE_LEGACY.
        let bytes = synth_account_bytes(PROFILE_LEGACY);
        let band = decode_price_update(&bytes).expect("decode ok");
        assert_eq!(band.profile_code, PROFILE_LEGACY);
        assert_eq!(band.profile(), Some(Profile::Legacy));
    }

    #[test]
    fn decode_lending_account_yields_profile_lending() {
        let bytes = synth_account_bytes(PROFILE_LENDING);
        let band = decode_price_update(&bytes).expect("decode ok");
        assert_eq!(band.profile_code, PROFILE_LENDING);
        assert_eq!(band.profile(), Some(Profile::Lending));
    }

    #[test]
    fn decode_amm_account_yields_profile_amm() {
        let bytes = synth_account_bytes(PROFILE_AMM);
        let band = decode_price_update(&bytes).expect("decode ok");
        assert_eq!(band.profile_code, PROFILE_AMM);
        assert_eq!(band.profile(), Some(Profile::Amm));
    }

    #[test]
    fn unknown_future_profile_code_decodes_but_typed_view_is_none() {
        // Forward-compat: a hypothetical profile_code = 9 from a future
        // publish should not crash the decoder. The byte field round-trips,
        // and the typed view returns None — the consumer can decide what
        // to do.
        let bytes = synth_account_bytes(9);
        let band = decode_price_update(&bytes).expect("decode ok");
        assert_eq!(band.profile_code, 9);
        assert_eq!(band.profile(), None);
    }

    #[test]
    fn decode_lwc_account_yields_forecaster_lwc() {
        // M6 publish path: forecaster_code = 3 (FORECASTER_LWC) + the
        // standard profile_code = PROFILE_AMM (M5 and M6 both use
        // point-relative bands; the legacy Lending profile is no longer
        // produced by new publishes). Wire layout unchanged from M5 — only
        // the forecaster_code byte differs.
        let bytes = synth_account_bytes_with_forecaster(PROFILE_AMM, FORECASTER_LWC);
        let band = decode_price_update(&bytes).expect("decode ok");
        assert_eq!(band.forecaster_code, FORECASTER_LWC);
        assert_eq!(band.forecaster_code, 3);
        assert_eq!(band.forecaster(), Some(Forecaster::Lwc));
        // Profile axis is the standard AMM (point-relative bands).
        assert_eq!(band.profile(), Some(Profile::Amm));
        // Band invariants still hold.
        assert!(band.validate_invariants().is_ok());
    }

    #[test]
    fn decode_mondrian_account_yields_forecaster_mondrian() {
        let bytes = synth_account_bytes_with_forecaster(PROFILE_AMM, FORECASTER_MONDRIAN);
        let band = decode_price_update(&bytes).expect("decode ok");
        assert_eq!(band.forecaster_code, FORECASTER_MONDRIAN);
        assert_eq!(band.forecaster(), Some(Forecaster::Mondrian));
    }

    #[test]
    fn unknown_future_forecaster_code_decodes_but_typed_view_is_none() {
        let bytes = synth_account_bytes_with_forecaster(PROFILE_AMM, 99);
        let band = decode_price_update(&bytes).expect("decode ok");
        assert_eq!(band.forecaster_code, 99);
        assert_eq!(band.forecaster(), None);
    }
}
