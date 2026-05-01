//! Per-upstream account decoding.
//!
//! Phase 1 step 2 scaffold: function signatures + dispatcher only. Each
//! `read_*` function returns `Err(RouterError::UpstreamDecoderNotImplemented)`
//! today; step 2b implements the real decoders against the upstream account
//! layouts:
//!
//! - **Pyth** — read aggregate `price` + `confidence` + `pub_slot` via
//!   `pyth-solana-receiver-sdk` (or direct PDA decode).
//! - **Chainlink v11** — decode the Verifier program's report PDA per the
//!   v11 schema (schema id `0x000b`) — the same logic the soothsayer-side
//!   Python decoders implement at `src/soothsayer/chainlink/v11.py`.
//! - **Switchboard On-Demand** — `PullFeedAccountData` decode for the
//!   underlier's feed PDA.
//! - **RedStone Live** — currently REST-only on the public gateway; the
//!   on-chain path requires the RedStone PDA layout when/if it lists.
//!   Stubbed permanently until that becomes available.
//! - **Mango v4 post-guard** — Mango v4 `PerpMarket` / `Bank` account
//!   decode for crypto-correlated assets only.

use anchor_lang::prelude::*;

use crate::errors::RouterError;
use crate::filters::RawUpstreamRead;
use crate::state::{
    UPSTREAM_CHAINLINK_STREAMS_RELAY, UPSTREAM_PYTH_AGGREGATE, UPSTREAM_REDSTONE_LIVE,
    UPSTREAM_SWITCHBOARD_ONDEMAND,
};

/// Dispatch on `kind` to the appropriate decoder. Returns
/// `RouterError::UnsupportedUpstreamKind` for unknown discriminants. Code 4
/// (formerly `UPSTREAM_MANGO_V4_POST_GUARD`) is permanently reserved and
/// rejected as unsupported per the 2026-04-29 methodology entry.
pub fn read_upstream(
    kind: u8,
    pda: Pubkey,
    account_data: &[u8],
    snapshot_exponent: i8,
) -> Result<RawUpstreamRead> {
    match kind {
        UPSTREAM_PYTH_AGGREGATE => read_pyth_aggregate(pda, account_data, snapshot_exponent),
        UPSTREAM_CHAINLINK_STREAMS_RELAY => {
            read_chainlink_streams_relay(pda, account_data, snapshot_exponent)
        }
        UPSTREAM_SWITCHBOARD_ONDEMAND => {
            read_switchboard_ondemand(pda, account_data, snapshot_exponent)
        }
        UPSTREAM_REDSTONE_LIVE => read_redstone_live(pda, account_data, snapshot_exponent),
        _ => Err(error!(RouterError::UnsupportedUpstreamKind)),
    }
}

// ──────────────────────── Phase 1 step 2b stubs ────────────────────────────

/// Decode a Pyth `PriceUpdateV2` from `account_data` and project it into
/// the router's `RawUpstreamRead` shape.
///
/// Verification: this commit accepts both `Full` and `Partial` Wormhole
/// verification levels. A future commit will add a `min_verification_level`
/// knob to `AssetConfig` so production assets can require `Full`. Tracked
/// alongside open methodology question O5.
///
/// Feed-id binding: this commit trusts the upstream PDA to correspond to the
/// expected feed (the AssetConfig `pda` field is the binding). A future
/// commit will store the expected `feed_id` in `AssetConfig` and assert
/// `price_message.feed_id == expected_feed_id` here, closing a per-asset
/// integrity check.
pub fn read_pyth_aggregate(
    pda: Pubkey,
    account_data: &[u8],
    snapshot_exponent: i8,
) -> Result<RawUpstreamRead> {
    use pyth_solana_receiver_sdk::price_update::PriceUpdateV2;

    // Try-deserialize via Anchor's standard path; checks the 8-byte
    // discriminator matches `PriceUpdateV2`'s and returns the inner struct.
    let mut buf = account_data;
    let price_update = PriceUpdateV2::try_deserialize(&mut buf)
        .map_err(|_| error!(RouterError::UpstreamDecoderNotImplemented))?;

    let msg = &price_update.price_message;
    if msg.price <= 0 {
        // Negative or zero price = upstream is unhealthy or misconfigured.
        return Err(error!(RouterError::UpstreamDecoderNotImplemented));
    }

    let raw_price = rescale_to_i64(msg.price as i128, msg.exponent, snapshot_exponent as i32)
        .ok_or_else(|| error!(RouterError::ExponentOutOfRange))?;

    // Confidence may not always rescale cleanly; if it overflows, omit it
    // rather than fail the whole read. The confidence filter then passes
    // this upstream through unchecked, which is the safe direction.
    let raw_confidence =
        rescale_to_i64(msg.conf as i128, msg.exponent, snapshot_exponent as i32);

    Ok(RawUpstreamRead {
        kind: crate::state::UPSTREAM_PYTH_AGGREGATE,
        pda: pda.to_bytes(),
        raw_price,
        raw_confidence,
        last_update_slot: price_update.posted_slot,
        last_update_unix_ts: msg.publish_time,
        exponent: snapshot_exponent,
    })
}

/// Rescale an i128 fixed-point value from `from_exp` to `to_exp`. Returns
/// `None` if the result overflows i64 or if the exponent gap exceeds 38
/// (the safe range for i128 arithmetic with 10^N constants).
fn rescale_to_i64(raw: i128, from_exp: i32, to_exp: i32) -> Option<i64> {
    let exp_diff = to_exp.checked_sub(from_exp)?;
    let scaled: i128 = if exp_diff > 0 {
        if exp_diff > 38 {
            return None;
        }
        let divisor = 10_i128.checked_pow(exp_diff as u32)?;
        raw.checked_div(divisor)?
    } else if exp_diff < 0 {
        if -exp_diff > 38 {
            return None;
        }
        let multiplier = 10_i128.checked_pow((-exp_diff) as u32)?;
        raw.checked_mul(multiplier)?
    } else {
        raw
    };
    scaled.try_into().ok()
}

/// Decode a `streams_relay_update.v1` PDA written by the soothsayer-controlled
/// Chainlink Streams Relay program (see scryer wishlist item 42 + the
/// 2026-04-29 (afternoon) entry in `reports/methodology_history.md`).
///
/// Wire format (mirror of `streams_relay_update.v1`):
///   - 8-byte Anchor discriminator
///   - version u8, market_status u8, schema_decoded_from u8,
///     signature_verified u8, _pad0 [u8; 4]
///   - feed_id [u8; 32], underlier_symbol [u8; 16]
///   - price i64, confidence i64, bid i64, ask i64, last_traded_price i64
///   - chainlink_observations_ts i64, chainlink_last_seen_ts_ns i64,
///     relay_post_ts i64, relay_post_slot u64
///   - exponent i8, _pad1 [u8; 7]
///
/// **Phase 1 step 2c stub.** The relay program (scryer wishlist item 42) does
/// not yet exist; once it lands and posts at least one `streams_relay_update`
/// PDA on devnet, this decoder will be implemented to parse the wire format
/// described above. Until then, `read_chainlink_streams_relay` returns
/// `UpstreamDecoderNotImplemented` so any AssetConfig wiring this upstream
/// kind fails cleanly at refresh — surfacing the missing infrastructure in
/// the call path rather than silently returning zero / stale data.
#[allow(unused_variables)]
pub fn read_chainlink_streams_relay(
    pda: Pubkey,
    account_data: &[u8],
    snapshot_exponent: i8,
) -> Result<RawUpstreamRead> {
    // Step 2c: implement once `soothsayer-streams-relay-program::post_relay_update`
    // is writing PDAs we can read. Decoder reads the relay PDA's `price` /
    // `confidence` / `relay_post_ts` / `relay_post_slot` / `exponent` and
    // projects into RawUpstreamRead. The Chainlink wire-format decoder
    // (`chainlink_v11.rs` in this crate) is reference-only for the relay
    // daemon's off-chain work and is not called from this code path.
    Err(error!(RouterError::UpstreamDecoderNotImplemented))
}

/// Decode a Switchboard On-Demand `PullFeedAccountData` and project it into
/// the router's `RawUpstreamRead` shape.
///
/// Reads `result.value` (the post-aggregation median across oracle
/// submissions, at 18-decimal precision) as the price, and `result.std_dev`
/// (also at 18-decimal precision) as the confidence interval. The slot is
/// `result.slot` (when the result was signed) and the unix timestamp is
/// `last_update_timestamp` from the account header.
///
/// Layout note: Switchboard's `PullFeedAccountData` is `#[repr(C)]` + Pod,
/// so bytemuck reinterprets the raw bytes after the 8-byte discriminator.
/// This avoids the SDK's `parse` Ref-of-Ref API which doesn't fit our
/// `&[u8]` decoder signature.
pub fn read_switchboard_ondemand(
    pda: Pubkey,
    account_data: &[u8],
    snapshot_exponent: i8,
) -> Result<RawUpstreamRead> {
    use switchboard_on_demand::on_demand::accounts::pull_feed::PullFeedAccountData;
    use switchboard_on_demand::Discriminator;

    // Switchboard precision: real_value = raw × 10^-18.
    const SWITCHBOARD_FROM_EXP: i32 = -18;

    if account_data.len() < 8 {
        return Err(error!(RouterError::UpstreamDecoderNotImplemented));
    }
    if &account_data[..8] != PullFeedAccountData::DISCRIMINATOR {
        return Err(error!(RouterError::UpstreamDecoderNotImplemented));
    }

    let body = &account_data[8..];
    let need = core::mem::size_of::<PullFeedAccountData>();
    if body.len() < need {
        return Err(error!(RouterError::UpstreamDecoderNotImplemented));
    }

    // `pod_read_unaligned` copies the bytes into an owned struct, so the
    // alignment of the source slice doesn't matter. Anchor account data may
    // not be aligned for `i128` after the 8-byte discriminator prefix.
    let feed: PullFeedAccountData = bytemuck::pod_read_unaligned(&body[..need]);

    // `result.slot == 0` means the feed has never been resolved — treat as
    // unavailable rather than a zero-price read.
    if feed.result.slot == 0 || feed.result.value <= 0 {
        return Err(error!(RouterError::UpstreamDecoderNotImplemented));
    }

    let raw_price = rescale_to_i64(
        feed.result.value,
        SWITCHBOARD_FROM_EXP,
        snapshot_exponent as i32,
    )
    .ok_or_else(|| error!(RouterError::ExponentOutOfRange))?;

    // std_dev is at the same precision as value. Soft-fail on overflow.
    let raw_confidence = if feed.result.std_dev > 0 {
        rescale_to_i64(
            feed.result.std_dev,
            SWITCHBOARD_FROM_EXP,
            snapshot_exponent as i32,
        )
    } else {
        None
    };

    Ok(RawUpstreamRead {
        kind: crate::state::UPSTREAM_SWITCHBOARD_ONDEMAND,
        pda: pda.to_bytes(),
        raw_price,
        raw_confidence,
        last_update_slot: feed.result.slot,
        last_update_unix_ts: feed.last_update_timestamp,
        exponent: snapshot_exponent,
    })
}

#[allow(unused_variables)]
pub fn read_redstone_live(
    pda: Pubkey,
    account_data: &[u8],
    snapshot_exponent: i8,
) -> Result<RawUpstreamRead> {
    // RedStone's public path is REST-only as of 2026-04-28. On-chain support
    // depends on RedStone publishing a Solana PDA layout; stub remains until
    // they do. AssetConfig should keep `active = 0` for this slot until then.
    Err(error!(RouterError::UpstreamDecoderNotImplemented))
}

// Note: `read_mango_v4_post_guard` was removed per the 2026-04-29 methodology
// entry. Mango v4's `PerpMarket` does not persist a post-guard `oracle_price`
// field; the deviation guard runs ephemerally during Mango's own instructions
// and the result is never written to account state. Mango contributes
// deviation-guard methodology only (already adopted as the Layer 0 filter
// per the 2026-04-28 (midday) entry, retracting that entry's "post-guard
// price as a fifth upstream" claim via in-line AMENDMENT). Code 4 in the
// `UPSTREAM_*` numbering remains reserved.

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dispatcher_rejects_unknown_kind() {
        let r = read_upstream(99, Pubkey::default(), &[], -8);
        assert!(r.is_err());
    }

    #[test]
    fn unimplemented_kinds_still_stubbed_pending_follow_up() {
        // RedStone is currently REST-only on the public gateway; on-chain
        // support depends on RedStone publishing a Solana PDA layout.
        // ChainlinkStreamsRelay is stubbed pending the relay program +
        // daemon (scryer wishlist items 42 + 43; soothsayer methodology
        // log 2026-04-29 (afternoon)).
        // Pyth and Switchboard On-Demand are real and covered by their
        // dedicated test functions.
        for kind in [UPSTREAM_REDSTONE_LIVE, UPSTREAM_CHAINLINK_STREAMS_RELAY] {
            let r = read_upstream(kind, Pubkey::default(), &[], -8);
            assert!(
                r.is_err(),
                "kind {kind} should error pending follow-up implementation",
            );
        }
    }

    #[test]
    fn reserved_mango_v4_code_4_is_rejected() {
        // Code 4 was previously `UPSTREAM_MANGO_V4_POST_GUARD`. Per the
        // 2026-04-29 (morning) methodology entry, Mango v4 was reclassified
        // as methodology-only (deviation-guard adopted as Layer 0 filter);
        // the "post-guard price as fifth upstream" premise was retracted.
        // Code 4 remains reserved and the dispatcher rejects it cleanly.
        let r = read_upstream(4, Pubkey::default(), &[], -8);
        assert!(r.is_err(), "kind 4 should be rejected as unsupported");
    }

    #[test]
    fn read_chainlink_streams_relay_returns_not_implemented_until_relay_ships() {
        // Per the 2026-04-29 (afternoon) entry, the relay program (scryer
        // wishlist item 42) doesn't yet exist. The decoder is stubbed to
        // surface that gap loudly when refresh_feed is called against an
        // AssetConfig that wires this upstream kind. When the relay program
        // is deployed and posts at least one PDA, this stub is replaced
        // with the real `streams_relay_update.v1` decoder.
        let r = read_chainlink_streams_relay(Pubkey::default(), &[0u8; 144], -8);
        assert!(r.is_err());
    }

    // ───── Pyth aggregate end-to-end test ─────

    fn build_pyth_price_update_v2(
        price: i64,
        conf: u64,
        exponent: i32,
        publish_time: i64,
        posted_slot: u64,
    ) -> Vec<u8> {
        use anchor_lang::Discriminator;
        use pyth_solana_receiver_sdk::price_update::{
            PriceFeedMessage, PriceUpdateV2, VerificationLevel,
        };

        let update = PriceUpdateV2 {
            write_authority: Pubkey::default(),
            verification_level: VerificationLevel::Full,
            price_message: PriceFeedMessage {
                feed_id: [42; 32],
                price,
                conf,
                exponent,
                publish_time,
                prev_publish_time: publish_time - 1,
                ema_price: price,
                ema_conf: conf,
            },
            posted_slot,
        };

        // Build the on-chain wire form: 8-byte discriminator + borsh body.
        let mut buf = Vec::new();
        buf.extend_from_slice(&PriceUpdateV2::DISCRIMINATOR);
        update.serialize(&mut buf).unwrap();
        buf
    }

    #[test]
    fn read_pyth_aggregate_extracts_price_and_confidence() {
        // SPY at $528.42, Pyth exponent -8 → price = 52_842_000_000.
        // Snapshot exponent also -8 → no rescale needed.
        let data = build_pyth_price_update_v2(
            52_842_000_000,
            5_000_000, // 0.05 conf
            -8,
            1_761_700_000,
            312_500_000,
        );
        let r = read_pyth_aggregate(Pubkey::default(), &data, -8).unwrap();
        assert_eq!(r.kind, UPSTREAM_PYTH_AGGREGATE);
        assert_eq!(r.raw_price, 52_842_000_000);
        assert_eq!(r.raw_confidence, Some(5_000_000));
        assert_eq!(r.last_update_unix_ts, 1_761_700_000);
        assert_eq!(r.last_update_slot, 312_500_000);
        assert_eq!(r.exponent, -8);
    }

    #[test]
    fn read_pyth_aggregate_rescales_across_exponents() {
        // Pyth publishes at -5 (5 decimals); we want -8 (8 decimals).
        // Pyth value 52_842_000 at exp=-5 represents 528.42; at exp=-8 it's
        // 52_842_000_000 (multiply by 10^3).
        let data = build_pyth_price_update_v2(52_842_000, 1_000, -5, 1_761_700_000, 1);
        let r = read_pyth_aggregate(Pubkey::default(), &data, -8).unwrap();
        assert_eq!(r.raw_price, 52_842_000_000);
        assert_eq!(r.raw_confidence, Some(1_000_000));
    }

    #[test]
    fn read_pyth_aggregate_errors_on_zero_or_negative_price() {
        let data = build_pyth_price_update_v2(0, 0, -8, 1_761_700_000, 1);
        assert!(read_pyth_aggregate(Pubkey::default(), &data, -8).is_err());

        let data_neg = build_pyth_price_update_v2(-1, 0, -8, 1_761_700_000, 1);
        assert!(read_pyth_aggregate(Pubkey::default(), &data_neg, -8).is_err());
    }

    #[test]
    fn read_pyth_aggregate_errors_on_corrupt_data() {
        let mostly_zeros = vec![0u8; 32];
        let r = read_pyth_aggregate(Pubkey::default(), &mostly_zeros, -8);
        assert!(r.is_err());
    }

    #[test]
    fn rescale_to_i64_handles_zero_diff() {
        assert_eq!(rescale_to_i64(12345, -8, -8), Some(12345));
    }

    #[test]
    fn rescale_to_i64_divides_when_target_has_fewer_decimals() {
        // 12345 at exp=-3 (= 12.345) → at exp=-1 (= 12.3) — divide by 100.
        assert_eq!(rescale_to_i64(12345, -3, -1), Some(123));
    }

    #[test]
    fn rescale_to_i64_multiplies_when_target_has_more_decimals() {
        // 123 at exp=-1 (= 12.3) → at exp=-3 (= 12.300) — multiply by 100.
        assert_eq!(rescale_to_i64(123, -1, -3), Some(12300));
    }

    #[test]
    fn rescale_to_i64_returns_none_on_i64_overflow() {
        // i128::MAX at exp=-18 to exp=-8 would still be huge — overflow i64.
        assert_eq!(rescale_to_i64(i128::MAX, -18, -8), None);
    }

    #[test]
    fn rescale_to_i64_returns_none_on_extreme_exponent_gap() {
        // exp_diff > 38 not supported (10^39 overflows i128).
        assert_eq!(rescale_to_i64(1, -50, 0), None);
    }

    // ───── Switchboard On-Demand end-to-end tests ─────

    fn build_switchboard_pull_feed(
        value_18d: i128,
        std_dev_18d: i128,
        result_slot: u64,
        last_update_ts: i64,
    ) -> Vec<u8> {
        use bytemuck::Zeroable;
        use switchboard_on_demand::on_demand::accounts::pull_feed::PullFeedAccountData;
        use switchboard_on_demand::Discriminator;

        // Construct an aligned, zeroed struct on the stack. We only populate
        // the fields read_switchboard_ondemand consumes; everything else
        // stays zero (matches uninitialized-feed semantics for those fields).
        let mut feed = PullFeedAccountData::zeroed();
        feed.result.value = value_18d;
        feed.result.std_dev = std_dev_18d;
        feed.result.slot = result_slot;
        feed.result.num_samples = 5;
        feed.last_update_timestamp = last_update_ts;

        // Wire form: 8-byte discriminator + bytes of the struct.
        let body_bytes = bytemuck::bytes_of(&feed);
        let mut buf = Vec::with_capacity(8 + body_bytes.len());
        buf.extend_from_slice(PullFeedAccountData::DISCRIMINATOR);
        buf.extend_from_slice(body_bytes);
        buf
    }

    #[test]
    fn read_switchboard_extracts_value_and_std_dev() {
        // SPY at $528.42 in 18-decimal: 528.42 × 10^18 = 528_420_000_000_000_000_000
        // Snapshot exp -8 → 52_842_000_000.
        let value: i128 = 528_420_000_000_000_000_000;
        let std_dev: i128 = 50_000_000_000_000_000; // 0.05 in 18-decimal
        let data = build_switchboard_pull_feed(value, std_dev, 312_500_000, 1_761_700_000);
        let r = read_switchboard_ondemand(Pubkey::default(), &data, -8).unwrap();
        assert_eq!(r.kind, UPSTREAM_SWITCHBOARD_ONDEMAND);
        assert_eq!(r.raw_price, 52_842_000_000);
        assert_eq!(r.raw_confidence, Some(5_000_000));
        assert_eq!(r.last_update_slot, 312_500_000);
        assert_eq!(r.last_update_unix_ts, 1_761_700_000);
        assert_eq!(r.exponent, -8);
    }

    #[test]
    fn read_switchboard_omits_confidence_when_std_dev_zero() {
        let value: i128 = 100_000_000_000_000_000_000;
        let data = build_switchboard_pull_feed(value, 0, 1, 1_761_700_000);
        let r = read_switchboard_ondemand(Pubkey::default(), &data, -8).unwrap();
        assert!(r.raw_confidence.is_none());
    }

    #[test]
    fn read_switchboard_errors_on_unresolved_feed() {
        // result.slot == 0 → feed has never been resolved.
        let value: i128 = 100_000_000_000_000_000_000;
        let data = build_switchboard_pull_feed(value, 0, 0, 1_761_700_000);
        assert!(read_switchboard_ondemand(Pubkey::default(), &data, -8).is_err());
    }

    #[test]
    fn read_switchboard_errors_on_zero_or_negative_value() {
        let data_zero = build_switchboard_pull_feed(0, 0, 1, 1_761_700_000);
        assert!(read_switchboard_ondemand(Pubkey::default(), &data_zero, -8).is_err());

        let data_neg = build_switchboard_pull_feed(-1, 0, 1, 1_761_700_000);
        assert!(read_switchboard_ondemand(Pubkey::default(), &data_neg, -8).is_err());
    }

    #[test]
    fn read_switchboard_errors_on_bad_discriminator() {
        use switchboard_on_demand::on_demand::accounts::pull_feed::PullFeedAccountData;
        let mut data =
            vec![0u8; 8 + core::mem::size_of::<PullFeedAccountData>()];
        // Discriminator stays zero — not a real PullFeedAccountData.
        assert!(read_switchboard_ondemand(Pubkey::default(), &data, -8).is_err());

        // Now flip a single byte in the discriminator and verify still rejected.
        data[0] = 1;
        assert!(read_switchboard_ondemand(Pubkey::default(), &data, -8).is_err());
    }

    #[test]
    fn read_switchboard_errors_on_truncated_data() {
        // Only the discriminator + a few bytes of body — too short.
        let truncated = vec![0u8; 50];
        assert!(read_switchboard_ondemand(Pubkey::default(), &truncated, -8).is_err());
    }
}
