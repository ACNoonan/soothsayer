//! Layer 0 filter primitives: staleness + confidence + Mango-style deviation
//! guard. Adopted as soothsayer methodology per the 2026-04-28 (midday)
//! entry of `reports/methodology_history.md`.
//!
//! These functions operate on already-decoded `RawUpstreamRead` records;
//! per-upstream account decoding (Pyth / Chainlink v11 / Switchboard / RedStone /
//! Mango v4) is the responsibility of `upstreams.rs` and lands in step 2b.
//!
//! Filter pipeline (locked v0):
//! 1. [`apply_staleness_filter`] — drop reads where `now - last_update > max_staleness_secs`.
//! 2. [`apply_confidence_filter`] — drop reads where `confidence > max_confidence_bps`.
//! 3. [`apply_deviation_guard`] — Mango-style: drop reads `> max_deviation_bps` from the
//!    provisional median, then recompute the median over surviving reads.
//!
//! All filter ops are pure (no I/O) and BPF-friendly (`no_std` would also work
//! if we ever need it on a tighter target).

use crate::state::{
    EXCLUSION_DEVIATION_OUTLIER, EXCLUSION_LOW_CONFIDENCE, EXCLUSION_NONE, EXCLUSION_STALE,
};

/// One upstream read after on-chain account decoding, before any filters.
/// `raw_confidence == None` means the upstream did not publish a CI.
#[derive(Clone, Copy, Debug)]
pub struct RawUpstreamRead {
    pub kind: u8,
    pub pda: [u8; 32],
    pub raw_price: i64,
    pub raw_confidence: Option<i64>,
    pub last_update_slot: u64,
    pub last_update_unix_ts: i64,
    pub exponent: i8,
}

/// Per-read filter status accumulated across the pipeline.
#[derive(Clone, Copy, Debug)]
pub struct FilteredUpstream {
    pub read: RawUpstreamRead,
    pub included: bool,
    pub exclusion_reason_code: u8, // EXCLUSION_*
    /// Signed deviation (basis points) from the post-filter median. Only valid
    /// when `exclusion_reason_code == EXCLUSION_DEVIATION_OUTLIER` or
    /// `included == true && a guard fired on a sibling`.
    pub deviation_bps_from_median: i32,
}

impl FilteredUpstream {
    pub fn new(read: RawUpstreamRead) -> Self {
        Self {
            read,
            included: true,
            exclusion_reason_code: EXCLUSION_NONE,
            deviation_bps_from_median: 0,
        }
    }

    fn exclude(&mut self, reason: u8) {
        self.included = false;
        self.exclusion_reason_code = reason;
    }
}

/// Drop reads whose `last_update_unix_ts` is older than `max_staleness_secs`
/// from `now_unix_ts`. Only mutates entries currently `included`.
pub fn apply_staleness_filter(
    reads: &mut [FilteredUpstream],
    now_unix_ts: i64,
    max_staleness_secs: u32,
) {
    let max = max_staleness_secs as i64;
    for r in reads.iter_mut() {
        if !r.included {
            continue;
        }
        let age = now_unix_ts.saturating_sub(r.read.last_update_unix_ts);
        if age > max {
            r.exclude(EXCLUSION_STALE);
        }
    }
}

/// Drop reads whose published confidence interval exceeds `max_confidence_bps`
/// of the published price. Reads with no confidence interval are passed through
/// (we cannot evaluate the filter; trust the upstream's own discipline).
pub fn apply_confidence_filter(reads: &mut [FilteredUpstream], max_confidence_bps: u16) {
    for r in reads.iter_mut() {
        if !r.included {
            continue;
        }
        let Some(conf) = r.read.raw_confidence else {
            continue;
        };
        let price = r.read.raw_price;
        if price <= 0 {
            continue;
        }
        let conf_abs = conf.unsigned_abs() as u128;
        let price_abs = price.unsigned_abs() as u128;
        // bps = conf / price * 10_000
        let conf_bps = (conf_abs.saturating_mul(10_000)) / price_abs.max(1);
        if conf_bps > max_confidence_bps as u128 {
            r.exclude(EXCLUSION_LOW_CONFIDENCE);
        }
    }
}

/// Mango-style deviation guard. Compute the provisional median over the
/// currently-`included` reads; drop any read whose price differs from the
/// provisional median by more than `max_deviation_bps`; recompute the median
/// over the post-filter survivors and stamp the deviation magnitude on every
/// read for the receipt's `deviation_guard_hits` log.
///
/// Returns the final post-filter median if at least one read survives.
/// Returns `None` if every read was rejected (caller should emit `LowQuorum`
/// or `AllStale` per upstream context).
pub fn apply_deviation_guard(
    reads: &mut [FilteredUpstream],
    max_deviation_bps: u16,
) -> Option<i64> {
    // Provisional median over currently-included reads.
    let provisional = median_of_included(reads)?;
    let max_dev = max_deviation_bps as i128;

    for r in reads.iter_mut() {
        if !r.included {
            continue;
        }
        let dev = signed_deviation_bps(r.read.raw_price, provisional);
        r.deviation_bps_from_median = dev;
        if (dev as i128).abs() > max_dev {
            r.exclude(EXCLUSION_DEVIATION_OUTLIER);
        }
    }

    median_of_included(reads)
}

/// Compute the integer median of `included` prices. Returns `None` if zero
/// reads are included. For an even survivor count, returns the lower of the
/// two midpoints (deterministic + integer-arithmetic-friendly; equivalent to
/// `floor` rounding).
fn median_of_included(reads: &[FilteredUpstream]) -> Option<i64> {
    // Stack-allocated; bounded by MAX_UPSTREAMS = 5.
    let mut prices: [i64; crate::state::MAX_UPSTREAMS] = [0; crate::state::MAX_UPSTREAMS];
    let mut n = 0usize;
    for r in reads {
        if r.included && n < prices.len() {
            prices[n] = r.read.raw_price;
            n += 1;
        }
    }
    if n == 0 {
        return None;
    }
    // Insertion sort over the populated prefix.
    for i in 1..n {
        let mut j = i;
        while j > 0 && prices[j - 1] > prices[j] {
            prices.swap(j - 1, j);
            j -= 1;
        }
    }
    Some(prices[(n - 1) / 2])
}

/// Signed deviation of `price` from `median` in basis points. Positive when
/// `price > median`. Returns 0 if `median == 0` (defensive; in practice prices
/// are always > 0 for the assets in scope).
fn signed_deviation_bps(price: i64, median: i64) -> i32 {
    if median == 0 {
        return 0;
    }
    // (price - median) / median * 10_000, with i128 intermediate to avoid overflow
    let num = (price as i128 - median as i128).saturating_mul(10_000);
    let den = median as i128;
    let bps = num / den;
    if bps > i32::MAX as i128 {
        i32::MAX
    } else if bps < i32::MIN as i128 {
        i32::MIN
    } else {
        bps as i32
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{
        UPSTREAM_CHAINLINK_STREAMS_RELAY, UPSTREAM_PYTH_AGGREGATE, UPSTREAM_REDSTONE_LIVE,
        UPSTREAM_SWITCHBOARD_ONDEMAND,
    };

    fn read(kind: u8, price: i64, conf: Option<i64>, age_secs: i64) -> FilteredUpstream {
        FilteredUpstream::new(RawUpstreamRead {
            kind,
            pda: [0; 32],
            raw_price: price,
            raw_confidence: conf,
            last_update_slot: 0,
            last_update_unix_ts: 1_000_000 - age_secs,
            exponent: -8,
        })
    }

    #[test]
    fn staleness_drops_old_reads() {
        let mut reads = [
            read(UPSTREAM_PYTH_AGGREGATE, 100_00000000, None, 10),
            read(UPSTREAM_CHAINLINK_STREAMS_RELAY, 100_00000000, None, 120),
        ];
        apply_staleness_filter(&mut reads, 1_000_000, 60);
        assert!(reads[0].included);
        assert!(!reads[1].included);
        assert_eq!(reads[1].exclusion_reason_code, EXCLUSION_STALE);
    }

    #[test]
    fn confidence_drops_wide_ci() {
        // price 100.0 (fixed-point at -8), conf 5.0 = 500 bps > 200 bps cap
        let mut reads = [
            read(UPSTREAM_PYTH_AGGREGATE, 100_00000000, Some(5_00000000), 0),
            read(UPSTREAM_CHAINLINK_STREAMS_RELAY, 100_00000000, Some(0_50000000), 0),
        ];
        apply_confidence_filter(&mut reads, 200);
        assert!(!reads[0].included);
        assert_eq!(reads[0].exclusion_reason_code, EXCLUSION_LOW_CONFIDENCE);
        assert!(reads[1].included);
    }

    #[test]
    fn deviation_guard_rejects_outlier_and_returns_clean_median() {
        // Three reads near 100.00, one at 102.00 (200 bps off). Cap = 75 bps.
        let mut reads = [
            read(UPSTREAM_PYTH_AGGREGATE, 100_00000000, None, 0),
            read(UPSTREAM_CHAINLINK_STREAMS_RELAY, 100_05000000, None, 0),
            read(UPSTREAM_SWITCHBOARD_ONDEMAND, 99_95000000, None, 0),
            read(UPSTREAM_REDSTONE_LIVE, 102_00000000, None, 0),
        ];
        let m = apply_deviation_guard(&mut reads, 75).unwrap();
        // Median over the three remaining (~100.00, 100.05, 99.95) sorts to
        // 99.95, 100.00, 100.05; index (3-1)/2 = 1 → 100.00.
        assert_eq!(m, 100_00000000);
        assert!(!reads[3].included);
        assert_eq!(reads[3].exclusion_reason_code, EXCLUSION_DEVIATION_OUTLIER);
        // Outlier deviation stamped on the receipt; ~+200 bps.
        assert!(reads[3].deviation_bps_from_median.abs() >= 199);
    }

    #[test]
    fn deviation_guard_with_no_outliers_includes_all() {
        let mut reads = [
            read(UPSTREAM_PYTH_AGGREGATE, 100_00000000, None, 0),
            read(UPSTREAM_CHAINLINK_STREAMS_RELAY, 100_05000000, None, 0),
            read(UPSTREAM_SWITCHBOARD_ONDEMAND, 100_10000000, None, 0),
        ];
        apply_deviation_guard(&mut reads, 75).unwrap();
        assert!(reads.iter().all(|r| r.included));
    }

    #[test]
    fn deviation_guard_returns_none_when_all_excluded() {
        let mut reads = [read(UPSTREAM_PYTH_AGGREGATE, 100_00000000, None, 0)];
        reads[0].exclude(EXCLUSION_STALE);
        assert!(apply_deviation_guard(&mut reads, 75).is_none());
    }

    #[test]
    fn signed_deviation_bps_directionality() {
        assert_eq!(signed_deviation_bps(101_00000000, 100_00000000), 100);
        assert_eq!(signed_deviation_bps(99_00000000, 100_00000000), -100);
        assert_eq!(signed_deviation_bps(100_00000000, 100_00000000), 0);
    }

    #[test]
    fn median_of_included_handles_even_count_deterministically() {
        let mut reads = [
            read(UPSTREAM_PYTH_AGGREGATE, 100_00000000, None, 0),
            read(UPSTREAM_CHAINLINK_STREAMS_RELAY, 110_00000000, None, 0),
            read(UPSTREAM_SWITCHBOARD_ONDEMAND, 105_00000000, None, 0),
            read(UPSTREAM_REDSTONE_LIVE, 95_00000000, None, 0),
        ];
        // Sorted: 95, 100, 105, 110 — n=4, idx=(4-1)/2=1 → 100.
        let m = median_of_included(&reads).unwrap();
        assert_eq!(m, 100_00000000);
        // Mark one excluded; sorted survivors 95, 105, 110 → idx 1 → 105.
        reads[0].exclude(EXCLUSION_STALE);
        assert_eq!(median_of_included(&reads).unwrap(), 105_00000000);
    }
}
