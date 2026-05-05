//! Read-side mirror of `soothsayer-oracle-program::PriceUpdate`.
//!
//! The router needs to load a closed-regime band from the soothsayer-oracle
//! program's `PriceUpdate` PDA without taking a cross-program Cargo dep
//! (which would entangle two BPF builds and double the audit surface).
//! Instead we mirror the borsh layout here; a canary parity test (added in
//! step 2c) will assert byte-for-byte equality between this duplicate and
//! the canonical struct in `programs/soothsayer-oracle-program/src/state.rs`.
//!
//! WARNING: Keep this in sync with the canonical `PriceUpdate`. Any field
//! addition / type change there must be mirrored here in the same commit.

use anchor_lang::prelude::*;

/// Mirror of `soothsayer_oracle_program::state::PriceUpdate`. Layout-stable
/// borsh; the 8-byte Anchor account discriminator is stripped by the caller
/// before passing the slice to `deserialize`.
#[derive(AnchorDeserialize, Clone, Debug)]
pub struct PriceUpdateLayout {
    pub version: u8,
    /// Soothsayer's closed-market regime label: 0=normal, 1=long_weekend,
    /// 2=high_vol, 3=shock_flagged. Maps to our `closed_market_regime_code`.
    pub regime_code: u8,
    /// 0=F1_emp_regime, 1=F0_stale, 2=mondrian.
    pub forecaster_code: u8,
    /// Fixed-point exponent applied to `point` / `lower` / `upper` / `fri_close`.
    pub exponent: i8,
    /// Serving profile (reports/active/m6_refactor.md A4): 0=legacy, 1=lending, 2=amm.
    /// Repurposed first byte of the prior `_pad0: [u8;4]` slot.
    pub profile_code: u8,
    pub _pad0: [u8; 3],
    pub target_coverage_bps: u16,
    pub claimed_served_bps: u16,
    pub buffer_applied_bps: u16,
    pub _pad1: [u8; 2],
    pub symbol: [u8; 16],
    pub point: i64,
    pub lower: i64,
    pub upper: i64,
    pub fri_close: i64,
    pub fri_ts: i64,
    pub publish_ts: i64,
    pub publish_slot: u64,
    pub signer: Pubkey,
    pub signer_epoch: u64,
}

/// Anchor account discriminator length.
pub const DISCRIMINATOR_LEN: usize = 8;

/// Try to deserialize a `PriceUpdate` from the account data slice. The
/// caller must strip the 8-byte discriminator before calling.
pub fn deserialize_price_update(data_after_disc: &[u8]) -> Result<PriceUpdateLayout> {
    let mut cursor = data_after_disc;
    PriceUpdateLayout::deserialize(&mut cursor)
        .map_err(|_| error!(crate::errors::RouterError::SoothsayerBandUnavailable))
}

#[cfg(test)]
mod parity_canary {
    //! Byte-for-byte parity canary against the canonical `PriceUpdate` in
    //! `programs/soothsayer-oracle-program/src/state.rs`.
    //!
    //! `CanonicalPriceUpdate` below is a deliberate hand-mirror of the
    //! canonical struct — same fields, same order, same types, same padding.
    //! When the canonical struct changes, this mirror MUST be updated in the
    //! same commit; the round-trip test will fail loudly if borsh layout
    //! drifts between the canonical struct and `PriceUpdateLayout`.
    //!
    //! UPDATE PROTOCOL: any edit to `soothsayer_oracle_program::state::PriceUpdate`
    //! requires three coordinated edits:
    //!   1. The canonical struct itself.
    //!   2. `PriceUpdateLayout` in this file.
    //!   3. `CanonicalPriceUpdate` below + the assertion list in
    //!      `parity_canary_round_trip`.
    //! Failing to update (3) causes the canary test to fail; failing to update
    //! (2) causes `populate_closed_or_halted_regime` to mis-deserialize at runtime.

    use super::*;

    #[derive(AnchorSerialize, AnchorDeserialize, Clone, Debug, PartialEq)]
    struct CanonicalPriceUpdate {
        version: u8,
        regime_code: u8,
        forecaster_code: u8,
        exponent: i8,
        profile_code: u8,
        _pad0: [u8; 3],
        target_coverage_bps: u16,
        claimed_served_bps: u16,
        buffer_applied_bps: u16,
        _pad1: [u8; 2],
        symbol: [u8; 16],
        point: i64,
        lower: i64,
        upper: i64,
        fri_close: i64,
        fri_ts: i64,
        publish_ts: i64,
        publish_slot: u64,
        signer: Pubkey,
        signer_epoch: u64,
    }

    fn sample_canonical() -> CanonicalPriceUpdate {
        let mut symbol = [0u8; 16];
        symbol[..3].copy_from_slice(b"SPY");
        CanonicalPriceUpdate {
            version: 1,
            regime_code: 0, // normal
            forecaster_code: 2, // mondrian (M5 / M6b2)
            exponent: -8,
            profile_code: 1, // lending
            _pad0: [0; 3],
            target_coverage_bps: 9500,
            claimed_served_bps: 9700,
            buffer_applied_bps: 200,
            _pad1: [0; 2],
            symbol,
            point: 528_42000000,
            lower: 515_10000000,
            upper: 541_72000000,
            fri_close: 528_00000000,
            fri_ts: 1_761_700_000,
            publish_ts: 1_761_700_005,
            publish_slot: 312_500_000,
            signer: Pubkey::default(),
            signer_epoch: 1,
        }
    }

    #[test]
    fn parity_canary_round_trip() {
        let canonical = sample_canonical();
        let mut buf = Vec::new();
        canonical.serialize(&mut buf).unwrap();

        // Round-trip through PriceUpdateLayout — if any field offset / type
        // differs, this deserialize will read the wrong bytes for one or
        // more fields and the assertion list below will catch the mismatch.
        let mirror = deserialize_price_update(&buf).unwrap();

        assert_eq!(canonical.version, mirror.version);
        assert_eq!(canonical.regime_code, mirror.regime_code);
        assert_eq!(canonical.forecaster_code, mirror.forecaster_code);
        assert_eq!(canonical.exponent, mirror.exponent);
        assert_eq!(canonical.profile_code, mirror.profile_code);
        assert_eq!(canonical._pad0, mirror._pad0);
        assert_eq!(canonical.target_coverage_bps, mirror.target_coverage_bps);
        assert_eq!(canonical.claimed_served_bps, mirror.claimed_served_bps);
        assert_eq!(canonical.buffer_applied_bps, mirror.buffer_applied_bps);
        assert_eq!(canonical._pad1, mirror._pad1);
        assert_eq!(canonical.symbol, mirror.symbol);
        assert_eq!(canonical.point, mirror.point);
        assert_eq!(canonical.lower, mirror.lower);
        assert_eq!(canonical.upper, mirror.upper);
        assert_eq!(canonical.fri_close, mirror.fri_close);
        assert_eq!(canonical.fri_ts, mirror.fri_ts);
        assert_eq!(canonical.publish_ts, mirror.publish_ts);
        assert_eq!(canonical.publish_slot, mirror.publish_slot);
        assert_eq!(canonical.signer, mirror.signer);
        assert_eq!(canonical.signer_epoch, mirror.signer_epoch);
    }

    #[test]
    fn parity_canary_serialized_size_matches() {
        // Borsh-serialized size = sum of field byte sizes.
        //   version       u8    1
        //   regime_code   u8    1
        //   forecaster    u8    1
        //   exponent      i8    1   ← 4
        //   profile_code  u8    1   ← 5
        //   _pad0       [u8;3]  3   ← 8
        //   target_cov   u16    2
        //   claimed     u16    2
        //   buffer       u16    2   ← 14
        //   _pad1       [u8;2]  2   ← 16
        //   symbol     [u8;16] 16   ← 32
        //   point         i64   8   ← 40
        //   lower         i64   8   ← 48
        //   upper         i64   8   ← 56
        //   fri_close     i64   8   ← 64
        //   fri_ts        i64   8   ← 72
        //   publish_ts    i64   8   ← 80
        //   publish_slot  u64   8   ← 88
        //   signer     Pubkey  32   ← 120
        //   signer_epoch  u64   8   ← 128
        // Total = 128, unchanged across the A4 wire-format upgrade
        // (profile_code repurposes the first byte of the prior _pad0).
        let canonical = sample_canonical();
        let mut buf = Vec::new();
        canonical.serialize(&mut buf).unwrap();
        assert_eq!(
            buf.len(),
            128,
            "canonical PriceUpdate borsh-serialized size drifted from 128 — \
             check that PriceUpdateLayout still mirrors it"
        );
    }

    #[test]
    fn deserialize_rejects_truncated_buffer() {
        let canonical = sample_canonical();
        let mut buf = Vec::new();
        canonical.serialize(&mut buf).unwrap();
        // Truncate to half the size.
        let half = &buf[..buf.len() / 2];
        let r = deserialize_price_update(half);
        assert!(r.is_err(), "truncated buffer should fail to deserialize");
    }
}
