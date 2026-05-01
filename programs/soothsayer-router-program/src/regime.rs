//! Regime gate: open / closed / halted / unknown.
//!
//! Reads two independent signals:
//! 1. The `marketStatus` byte from the configured `market_status_source` PDA
//!    (Chainlink v11 report PDA for equity assets).
//! 2. A calendar-based detection embedded in the program (NYSE / CME GLOBEX
//!    schedules, hard-coded for v0).
//!
//! When the two agree, the regime is determinate. When they disagree, the
//! gate emits [`RegimeDecision::Unknown`] and the consumer chooses whether
//! to trust the read (the caller stamps `quality_flag = regime_ambiguous`).
//!
//! Phase 1 step 2 scaffold: signature + invariants + a placeholder
//! [`RegimeDecision::from_signals`] resolver. The Chainlink v11 byte parser
//! and the embedded calendar land in step 2b together with the upstream
//! decoders.

use crate::state::{REGIME_CLOSED, REGIME_HALTED, REGIME_OPEN, REGIME_UNKNOWN};

/// Calendar-based market-status signal independent of any oracle. v0 ships
/// with NYSE + CME GLOBEX hard-coded; new asset classes add a calendar via
/// methodology entry per open question O7 (2026-04-28 (afternoon) entry).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CalendarSignal {
    Open,
    Closed,
    /// Calendar unknown for the asset's venue (e.g., a non-NYSE/CME asset).
    NotApplicable,
}

/// Oracle-reported market-status signal extracted from `market_status_source`.
/// For Chainlink v11 these map to the published `marketStatus` byte.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OracleSignal {
    /// Regular trading session.
    Open,
    /// Pre-market or after-hours; treated as `Open` for routing purposes
    /// (consumer reads see real prices, not a stale-hold).
    Extended,
    /// Weekend close.
    Closed,
    /// Mid-session halt.
    Halted,
    /// Source did not report or report was unparseable.
    Unknown,
}

/// Final regime decision derived from the two signals. Mirrors `Regime` in
/// the host-side `crates/soothsayer-router::receipt`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RegimeDecision {
    Open,
    Closed,
    Halted,
    Unknown,
}

impl RegimeDecision {
    pub fn code(&self) -> u8 {
        match self {
            RegimeDecision::Open => REGIME_OPEN,
            RegimeDecision::Closed => REGIME_CLOSED,
            RegimeDecision::Halted => REGIME_HALTED,
            RegimeDecision::Unknown => REGIME_UNKNOWN,
        }
    }

    /// Resolve the regime from two independent signals.
    ///
    /// - Both Open → Open.
    /// - Both Closed → Closed.
    /// - Oracle Halted (regardless of calendar) → Halted (the venue is
    ///   authoritative on intra-session halts).
    /// - Oracle disagrees with calendar (e.g., calendar Open + oracle Closed) → Unknown.
    /// - Oracle Unknown + calendar known → fall back to calendar.
    /// - Both Unknown / NotApplicable → Unknown.
    pub fn from_signals(oracle: OracleSignal, calendar: CalendarSignal) -> Self {
        match (oracle, calendar) {
            (OracleSignal::Halted, _) => RegimeDecision::Halted,
            (OracleSignal::Open | OracleSignal::Extended, CalendarSignal::Open) => {
                RegimeDecision::Open
            }
            (OracleSignal::Closed, CalendarSignal::Closed) => RegimeDecision::Closed,

            // Disagreement → Unknown.
            (OracleSignal::Open | OracleSignal::Extended, CalendarSignal::Closed) => {
                RegimeDecision::Unknown
            }
            (OracleSignal::Closed, CalendarSignal::Open) => RegimeDecision::Unknown,

            // Oracle Unknown — fall back to calendar where possible.
            (OracleSignal::Unknown, CalendarSignal::Open) => RegimeDecision::Open,
            (OracleSignal::Unknown, CalendarSignal::Closed) => RegimeDecision::Closed,

            // Calendar NotApplicable — trust oracle.
            (OracleSignal::Open | OracleSignal::Extended, CalendarSignal::NotApplicable) => {
                RegimeDecision::Open
            }
            (OracleSignal::Closed, CalendarSignal::NotApplicable) => RegimeDecision::Closed,

            // Everything else → Unknown.
            (OracleSignal::Unknown, CalendarSignal::NotApplicable) => RegimeDecision::Unknown,
        }
    }
}

/// Parse the `market_status_code` byte from a soothsayer-controlled
/// `streams_relay_update.v1` PDA written by the Chainlink Streams Relay
/// program. The relay daemon decodes the upstream Chainlink V8 report
/// off-chain (or via Verifier CPI inside the relay program) and projects
/// the `marketStatus` field into the relay PDA's `market_status_code` byte
/// using the same vocabulary (0 = unknown, 1 = pre-market, 2 = regular,
/// 3 = post-market, 4 = overnight, 5 = closed).
///
/// **Phase 1 step 2c stub.** The relay program (scryer wishlist item 42)
/// doesn't yet exist; until it ships, this parser returns
/// `OracleSignal::Unknown` so the regime gate falls back cleanly to the
/// calendar signal.
///
/// When the relay PDA is live, this function will read offset 1 of the
/// account body (after the 8-byte discriminator + 1-byte version) to
/// extract `market_status_code`, and project into `OracleSignal` via the
/// same mapping used by the retracted v11 parser.
#[allow(unused_variables)]
pub fn parse_chainlink_streams_relay_market_status(account_data: &[u8]) -> OracleSignal {
    // Step 2c: read the relay PDA's `market_status_code` and map:
    //   1 = pre_market | 3 = post_market | 4 = overnight  → Extended
    //   2 = regular                                        → Open
    //   5 = closed                                         → Closed
    //   0 = unknown / anything else                        → Unknown
    OracleSignal::Unknown
}

/// Holiday-aware DST-correct NYSE calendar detection. Locked 2026-04-29
/// (late evening). Coverage 2024-01-01 through 2027-12-31 — see
/// [`NYSE_HOLIDAYS`] for the source citations and open question O8 for the
/// refresh-cadence policy. Closes the v0 limitations disclosed in the
/// 2026-04-28 (afternoon) entry: holidays now return `Closed`, DST is
/// honoured via the post-2007 rule, and early-close days return `Closed`
/// after 13:00 ET.
pub fn nyse_calendar_signal(unix_ts: i64) -> CalendarSignal {
    let (y, m, d, dow) = civil_from_unix(unix_ts);
    if dow == 0 || dow == 6 {
        return CalendarSignal::Closed;
    }
    let kind = holiday_lookup(y, m, d);
    if matches!(kind, Some(HolidayKind::FullClose)) {
        return CalendarSignal::Closed;
    }
    let (open_secs, close_secs) =
        market_hours_utc(is_us_dst(y, m, d), matches!(kind, Some(HolidayKind::EarlyClose)));
    let secs_into_day = unix_ts.rem_euclid(86_400);
    if (open_secs..close_secs).contains(&secs_into_day) {
        CalendarSignal::Open
    } else {
        CalendarSignal::Closed
    }
}

/// Open/close window in UTC seconds-of-day for sessions whose underlying
/// Eastern hours are 09:30-16:00 (regular) or 09:30-13:00 (early). Right
/// edge is exclusive — 16:00 ET sharp returns `Closed`.
const fn market_hours_utc(dst: bool, early: bool) -> (i64, i64) {
    match (dst, early) {
        (true, false) => (48_600, 72_000),  // 13:30-20:00 UTC = 09:30-16:00 EDT
        (true, true) => (48_600, 61_200),   // 13:30-17:00 UTC = 09:30-13:00 EDT
        (false, false) => (52_200, 75_600), // 14:30-21:00 UTC = 09:30-16:00 EST
        (false, true) => (52_200, 64_800),  // 14:30-18:00 UTC = 09:30-13:00 EST
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum HolidayKind {
    FullClose,
    EarlyClose,
}

/// NYSE holiday table, sorted ascending by (year, month, day) — binary-search
/// keyed. Coverage 2024-01-01 through 2027-12-31. Sources locked in the
/// 2026-04-29 (late evening) methodology entry:
/// - ICE PR "NYSE Group Announces 2024, 2025 and 2026 Holiday and Early
///   Closings Calendar" (issued 2023; covers 2024-2026).
/// - ICE PR "NYSE Group Announces 2025, 2026 and 2027 Holiday and Early
///   Closings Calendar" (issued 2024; covers 2025-2027).
/// - SEC Release No. 34-101993 (Carter day of mourning, 2025-01-09).
const NYSE_HOLIDAYS: &[(u16, u8, u8, HolidayKind)] = &[
    // 2024 — included for backtest parity.
    (2024, 1, 1, HolidayKind::FullClose),   // New Year's Day (Mon)
    (2024, 1, 15, HolidayKind::FullClose),  // MLK Jr. Day
    (2024, 2, 19, HolidayKind::FullClose),  // Presidents' Day
    (2024, 3, 29, HolidayKind::FullClose),  // Good Friday
    (2024, 5, 27, HolidayKind::FullClose),  // Memorial Day
    (2024, 6, 19, HolidayKind::FullClose),  // Juneteenth (Wed)
    (2024, 7, 3, HolidayKind::EarlyClose),  // pre-Independence Day
    (2024, 7, 4, HolidayKind::FullClose),   // Independence Day (Thu)
    (2024, 9, 2, HolidayKind::FullClose),   // Labor Day
    (2024, 11, 28, HolidayKind::FullClose), // Thanksgiving (Thu)
    (2024, 11, 29, HolidayKind::EarlyClose), // post-Thanksgiving (Fri)
    (2024, 12, 24, HolidayKind::EarlyClose), // Christmas Eve (Tue)
    (2024, 12, 25, HolidayKind::FullClose), // Christmas (Wed)
    // 2025
    (2025, 1, 1, HolidayKind::FullClose),   // New Year's Day (Wed)
    (2025, 1, 9, HolidayKind::FullClose),   // Carter day of mourning (SEC 34-101993)
    (2025, 1, 20, HolidayKind::FullClose),  // MLK Jr. Day
    (2025, 2, 17, HolidayKind::FullClose),  // Presidents' Day
    (2025, 4, 18, HolidayKind::FullClose),  // Good Friday
    (2025, 5, 26, HolidayKind::FullClose),  // Memorial Day
    (2025, 6, 19, HolidayKind::FullClose),  // Juneteenth (Thu)
    (2025, 7, 3, HolidayKind::EarlyClose),  // pre-Independence Day (Thu)
    (2025, 7, 4, HolidayKind::FullClose),   // Independence Day (Fri)
    (2025, 9, 1, HolidayKind::FullClose),   // Labor Day
    (2025, 11, 27, HolidayKind::FullClose), // Thanksgiving (Thu)
    (2025, 11, 28, HolidayKind::EarlyClose), // post-Thanksgiving (Fri)
    (2025, 12, 24, HolidayKind::EarlyClose), // Christmas Eve (Wed)
    (2025, 12, 25, HolidayKind::FullClose), // Christmas (Thu)
    // 2026
    (2026, 1, 1, HolidayKind::FullClose),   // New Year's Day (Thu)
    (2026, 1, 19, HolidayKind::FullClose),  // MLK Jr. Day
    (2026, 2, 16, HolidayKind::FullClose),  // Presidents' Day
    (2026, 4, 3, HolidayKind::FullClose),   // Good Friday (during EDT)
    (2026, 5, 25, HolidayKind::FullClose),  // Memorial Day
    (2026, 6, 19, HolidayKind::FullClose),  // Juneteenth (Fri)
    (2026, 7, 3, HolidayKind::FullClose),   // Independence Day observed (Fri); 7/4 = Sat
    (2026, 9, 7, HolidayKind::FullClose),   // Labor Day
    (2026, 11, 26, HolidayKind::FullClose), // Thanksgiving (Thu)
    (2026, 11, 27, HolidayKind::EarlyClose), // post-Thanksgiving (Fri)
    (2026, 12, 24, HolidayKind::EarlyClose), // Christmas Eve (Thu)
    (2026, 12, 25, HolidayKind::FullClose), // Christmas (Fri)
    // 2027
    (2027, 1, 1, HolidayKind::FullClose),   // New Year's Day (Fri)
    (2027, 1, 18, HolidayKind::FullClose),  // MLK Jr. Day
    (2027, 2, 15, HolidayKind::FullClose),  // Presidents' Day
    (2027, 3, 26, HolidayKind::FullClose),  // Good Friday
    (2027, 5, 31, HolidayKind::FullClose),  // Memorial Day
    (2027, 6, 18, HolidayKind::FullClose),  // Juneteenth observed (Fri); 6/19 = Sat
    (2027, 7, 5, HolidayKind::FullClose),   // Independence Day observed (Mon); 7/4 = Sun
    (2027, 9, 6, HolidayKind::FullClose),   // Labor Day
    (2027, 11, 25, HolidayKind::FullClose), // Thanksgiving (Thu)
    (2027, 11, 26, HolidayKind::EarlyClose), // post-Thanksgiving (Fri)
    (2027, 12, 24, HolidayKind::FullClose), // Christmas observed (Fri); 12/25 = Sat
];

fn holiday_lookup(y: i32, m: u8, d: u8) -> Option<HolidayKind> {
    if !(2024..=2027).contains(&y) {
        return None;
    }
    let key = (y as u16, m, d);
    NYSE_HOLIDAYS
        .binary_search_by_key(&key, |&(yy, mm, dd, _)| (yy, mm, dd))
        .ok()
        .map(|i| NYSE_HOLIDAYS[i].3)
}

/// Convert `unix_ts` to (year, month, day, day-of-week). dow: 0 = Sunday,
/// ..., 6 = Saturday. Howard Hinnant's `civil_from_days` algorithm; pure
/// integer arithmetic, BPF-safe, no `chrono` dependency.
fn civil_from_unix(unix_ts: i64) -> (i32, u8, u8, u8) {
    let days = unix_ts.div_euclid(86_400);
    // 1970-01-01 (unix 0) was a Thursday → days 0 ↔ dow 4.
    let dow = ((days + 4).rem_euclid(7)) as u8;

    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097) as u32;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let mut y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u8;
    let m = (if mp < 10 { mp + 3 } else { mp - 9 }) as u8;
    if m <= 2 {
        y += 1;
    }
    (y as i32, m, d, dow)
}

/// Days since 1970-01-01 for the given civil date (Howard Hinnant's
/// `days_from_civil`).
fn days_from_civil(y: i32, m: u8, d: u8) -> i64 {
    let y = (if m <= 2 { y - 1 } else { y }) as i64;
    let m = m as i64;
    let d = d as i64;
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let mp = if m > 2 { m - 3 } else { m + 9 };
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe - 719_468
}

/// `n`-th occurrence of `target_dow` in `(year, month)`. 1-indexed (n = 1
/// → first). `target_dow`: 0 = Sunday, ..., 6 = Saturday.
fn nth_dow_of_month(year: i32, month: u8, target_dow: u8, n: u8) -> u8 {
    let first_day = days_from_civil(year, month, 1);
    let first_dow = ((first_day + 4).rem_euclid(7)) as u8;
    let offset = (target_dow + 7 - first_dow) % 7;
    1 + offset + (n - 1) * 7
}

/// US daylight-saving-time window, post-2007 rule: 02:00 ET on the second
/// Sunday of March → 02:00 ET on the first Sunday of November. Resolution
/// is date-only (sufficient because NYSE trading hours are post-09:30 ET,
/// well after the 02:00 transition; the transition Sunday is treated as
/// post-transition for date-comparison purposes — irrelevant in practice
/// since markets are closed Sunday).
fn is_us_dst(y: i32, m: u8, d: u8) -> bool {
    if m < 3 || m > 11 {
        return false;
    }
    if m > 3 && m < 11 {
        return true;
    }
    if m == 3 {
        d >= nth_dow_of_month(y, 3, 0, 2)
    } else {
        d < nth_dow_of_month(y, 11, 0, 1)
    }
}

/// CME GLOBEX runs ~23 hours/day Mon–Fri with a 1-hour maintenance window
/// (17:00–18:00 ET = 22:00–23:00 UTC EST / 21:00–22:00 UTC EDT) plus a
/// weekend close from Friday 17:00 ET to Sunday 18:00 ET. This function is
/// scheduled for step 2c implementation alongside the holiday-aware NYSE
/// calendar; for v0 it returns `NotApplicable`, deferring the regime
/// decision entirely to whatever oracle source is configured for the asset.
pub fn cme_globex_calendar_signal(_unix_ts: i64) -> CalendarSignal {
    CalendarSignal::NotApplicable
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn agreement_resolves_cleanly() {
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Open, CalendarSignal::Open),
            RegimeDecision::Open
        );
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Closed, CalendarSignal::Closed),
            RegimeDecision::Closed
        );
    }

    #[test]
    fn halted_dominates_calendar() {
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Halted, CalendarSignal::Open),
            RegimeDecision::Halted
        );
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Halted, CalendarSignal::Closed),
            RegimeDecision::Halted
        );
    }

    #[test]
    fn extended_session_routes_as_open() {
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Extended, CalendarSignal::Open),
            RegimeDecision::Open
        );
    }

    #[test]
    fn disagreement_resolves_unknown() {
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Open, CalendarSignal::Closed),
            RegimeDecision::Unknown
        );
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Closed, CalendarSignal::Open),
            RegimeDecision::Unknown
        );
    }

    #[test]
    fn unknown_oracle_falls_back_to_calendar() {
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Unknown, CalendarSignal::Open),
            RegimeDecision::Open
        );
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Unknown, CalendarSignal::Closed),
            RegimeDecision::Closed
        );
        assert_eq!(
            RegimeDecision::from_signals(
                OracleSignal::Unknown,
                CalendarSignal::NotApplicable
            ),
            RegimeDecision::Unknown
        );
    }

    #[test]
    fn calendar_not_applicable_trusts_oracle() {
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Open, CalendarSignal::NotApplicable),
            RegimeDecision::Open
        );
        assert_eq!(
            RegimeDecision::from_signals(OracleSignal::Closed, CalendarSignal::NotApplicable),
            RegimeDecision::Closed
        );
    }

    // ───── NYSE calendar tests ─────
    // Reference timestamps, verified against the day-of-week formula
    // `dow = ((unix_ts / 86400) + 4) % 7` where 0 = Sunday. 2026-04-27 is
    // a Monday during EDT (DST starts 2026-03-08, ends 2026-11-01):
    //   2026-04-25 (Sat) 18:00 UTC = 1_777_140_000
    //   2026-04-26 (Sun) 18:00 UTC = 1_777_226_400
    //   2026-04-27 (Mon) 13:00 UTC = 1_777_294_800  (09:00 EDT, pre-market)
    //   2026-04-27 (Mon) 14:30 UTC = 1_777_300_200  (10:30 EDT, mid-session)
    //   2026-04-27 (Mon) 19:00 UTC = 1_777_316_400  (15:00 EDT, mid-session)
    //   2026-04-27 (Mon) 21:30 UTC = 1_777_325_400  (17:30 EDT, after-hours)

    fn ts(y: i32, m: u8, d: u8, hh: u32, mm: u32) -> i64 {
        days_from_civil(y, m, d) * 86_400 + (hh as i64) * 3600 + (mm as i64) * 60
    }

    #[test]
    fn nyse_calendar_recognises_weekend_as_closed() {
        let saturday_18_utc: i64 = 1_777_140_000;
        let sunday_18_utc: i64 = 1_777_226_400;
        assert_eq!(nyse_calendar_signal(saturday_18_utc), CalendarSignal::Closed);
        assert_eq!(nyse_calendar_signal(sunday_18_utc), CalendarSignal::Closed);
    }

    #[test]
    fn nyse_calendar_recognises_weekday_market_hours_as_open() {
        let monday_mid_session_a: i64 = 1_777_300_200; // 14:30 UTC = 10:30 EDT
        let monday_mid_session_b: i64 = 1_777_316_400; // 19:00 UTC = 15:00 EDT
        assert_eq!(
            nyse_calendar_signal(monday_mid_session_a),
            CalendarSignal::Open
        );
        assert_eq!(
            nyse_calendar_signal(monday_mid_session_b),
            CalendarSignal::Open
        );
    }

    #[test]
    fn nyse_calendar_recognises_after_hours_as_closed() {
        let monday_after_hours: i64 = 1_777_325_400; // 21:30 UTC = 17:30 EDT
        assert_eq!(
            nyse_calendar_signal(monday_after_hours),
            CalendarSignal::Closed
        );
    }

    #[test]
    fn nyse_calendar_recognises_pre_market_as_closed() {
        // Monday 13:00 UTC = 09:00 EDT, before 09:30 market open.
        let monday_pre: i64 = 1_777_294_800;
        assert_eq!(nyse_calendar_signal(monday_pre), CalendarSignal::Closed);
    }

    // ───── civil_from_unix / days_from_civil round-trip ─────

    #[test]
    fn civil_from_unix_handles_known_dates() {
        assert_eq!(civil_from_unix(0), (1970, 1, 1, 4)); // Thursday
        assert_eq!(civil_from_unix(86_400), (1970, 1, 2, 5)); // Friday
        assert_eq!(civil_from_unix(ts(2024, 2, 29, 0, 0)), (2024, 2, 29, 4)); // leap-day Thu
        assert_eq!(civil_from_unix(ts(2025, 12, 25, 17, 0)), (2025, 12, 25, 4)); // Christmas Thu
        assert_eq!(civil_from_unix(ts(2026, 4, 27, 14, 30)), (2026, 4, 27, 1)); // Mon
    }

    #[test]
    fn days_from_civil_round_trips() {
        for (y, m, d) in [
            (1970, 1, 1),
            (1999, 12, 31),
            (2000, 1, 1),
            (2024, 2, 29),
            (2025, 7, 4),
            (2027, 12, 31),
        ] {
            let days = days_from_civil(y, m, d);
            let (y2, m2, d2, _) = civil_from_unix(days * 86_400);
            assert_eq!((y, m, d), (y2, m2, d2));
        }
    }

    // ───── DST detection ─────

    #[test]
    fn is_us_dst_matches_post_2007_rule() {
        // 2026 transitions: spring forward 2026-03-08, fall back 2026-11-01.
        assert!(!is_us_dst(2026, 3, 7)); // Saturday before spring forward
        assert!(is_us_dst(2026, 3, 8)); // spring-forward Sunday — post-transition
        assert!(is_us_dst(2026, 3, 9)); // first EDT Monday
        assert!(is_us_dst(2026, 7, 15)); // mid-summer
        assert!(is_us_dst(2026, 10, 31)); // last EDT Saturday
        assert!(!is_us_dst(2026, 11, 1)); // fall-back Sunday — post-transition
        assert!(!is_us_dst(2026, 11, 2)); // first EST Monday
        assert!(!is_us_dst(2026, 1, 15)); // January, EST
        assert!(!is_us_dst(2026, 12, 15)); // December, EST

        // 2027 transitions: spring forward 2027-03-14, fall back 2027-11-07.
        assert!(!is_us_dst(2027, 3, 13));
        assert!(is_us_dst(2027, 3, 14));
        assert!(is_us_dst(2027, 11, 6));
        assert!(!is_us_dst(2027, 11, 7));
    }

    // ───── DST corner cases that the v0 stub got wrong ─────

    #[test]
    fn nyse_calendar_open_at_first_edt_trading_hour() {
        // 2026-04-27 (Mon, EDT) 13:30 UTC = 09:30 EDT. The v0 stub used a
        // fixed 14:30 UTC open, returning Closed; with DST honoured, this
        // is now the first second of trading and returns Open.
        assert_eq!(
            nyse_calendar_signal(ts(2026, 4, 27, 13, 30)),
            CalendarSignal::Open
        );
    }

    #[test]
    fn nyse_calendar_closed_at_last_edt_trading_hour() {
        // 2026-04-27 (Mon, EDT) 20:30 UTC = 16:30 EDT, after the 16:00 ET
        // close. v0 stub used a fixed 21:00 UTC close, returning Open; now
        // returns Closed.
        assert_eq!(
            nyse_calendar_signal(ts(2026, 4, 27, 20, 30)),
            CalendarSignal::Closed
        );
    }

    #[test]
    fn nyse_calendar_closes_exactly_at_16_eastern() {
        // Right edge is exclusive — 16:00 ET sharp is Closed.
        assert_eq!(
            nyse_calendar_signal(ts(2026, 4, 27, 20, 0)), // 16:00 EDT exactly
            CalendarSignal::Closed
        );
        // EST equivalent: 2026-12-15 (Tue, EST) 21:00 UTC = 16:00 EST sharp.
        assert_eq!(
            nyse_calendar_signal(ts(2026, 12, 15, 21, 0)),
            CalendarSignal::Closed
        );
    }

    // ───── Holiday closures (full-day) ─────

    #[test]
    fn nyse_calendar_holidays_return_closed_during_market_hours() {
        // All sampled at mid-session UTC times, accounting for DST per date.
        // Christmas 2025 (Thu) — would be Open without holiday handling.
        assert_eq!(
            nyse_calendar_signal(ts(2025, 12, 25, 15, 0)),
            CalendarSignal::Closed
        );
        // MLK Jr. Day 2026 (Mon, EST).
        assert_eq!(
            nyse_calendar_signal(ts(2026, 1, 19, 15, 0)),
            CalendarSignal::Closed
        );
        // Presidents' Day 2026 (Mon, EST).
        assert_eq!(
            nyse_calendar_signal(ts(2026, 2, 16, 15, 0)),
            CalendarSignal::Closed
        );
        // Good Friday 2026 (during EDT).
        assert_eq!(
            nyse_calendar_signal(ts(2026, 4, 3, 14, 30)),
            CalendarSignal::Closed
        );
        // Memorial Day 2026 (Mon, EDT).
        assert_eq!(
            nyse_calendar_signal(ts(2026, 5, 25, 14, 30)),
            CalendarSignal::Closed
        );
        // Juneteenth 2026 (Fri, EDT).
        assert_eq!(
            nyse_calendar_signal(ts(2026, 6, 19, 14, 30)),
            CalendarSignal::Closed
        );
        // Independence Day observed 2026-07-03 (Fri); 7/4 falls on Sat.
        assert_eq!(
            nyse_calendar_signal(ts(2026, 7, 3, 14, 30)),
            CalendarSignal::Closed
        );
        // Labor Day 2026 (Mon, EDT).
        assert_eq!(
            nyse_calendar_signal(ts(2026, 9, 7, 14, 30)),
            CalendarSignal::Closed
        );
        // Thanksgiving 2026 (Thu, EST — fall-back has happened).
        assert_eq!(
            nyse_calendar_signal(ts(2026, 11, 26, 15, 0)),
            CalendarSignal::Closed
        );
        // Carter day of mourning 2025-01-09 (Thu, EST) — ad-hoc closure.
        assert_eq!(
            nyse_calendar_signal(ts(2025, 1, 9, 15, 0)),
            CalendarSignal::Closed
        );
    }

    // ───── Early-close days ─────

    #[test]
    fn nyse_calendar_early_close_open_before_1pm_eastern() {
        // 2025-11-28 (Fri, post-Thanksgiving, EST) 17:30 UTC = 12:30 EST.
        assert_eq!(
            nyse_calendar_signal(ts(2025, 11, 28, 17, 30)),
            CalendarSignal::Open
        );
        // 2025-12-24 (Wed, Christmas Eve, EST) 17:30 UTC = 12:30 EST.
        assert_eq!(
            nyse_calendar_signal(ts(2025, 12, 24, 17, 30)),
            CalendarSignal::Open
        );
    }

    #[test]
    fn nyse_calendar_early_close_closed_after_1pm_eastern() {
        // 2025-11-28 (Fri, EST) 18:30 UTC = 13:30 EST — after early close.
        assert_eq!(
            nyse_calendar_signal(ts(2025, 11, 28, 18, 30)),
            CalendarSignal::Closed
        );
        // 2025-11-28 (Fri, EST) 18:00 UTC = 13:00 EST sharp — right edge exclusive.
        assert_eq!(
            nyse_calendar_signal(ts(2025, 11, 28, 18, 0)),
            CalendarSignal::Closed
        );
        // 2024-07-03 (Wed, EDT) 17:30 UTC = 13:30 EDT — pre-Independence-Day early.
        assert_eq!(
            nyse_calendar_signal(ts(2024, 7, 3, 17, 30)),
            CalendarSignal::Closed
        );
        // 2024-07-03 (Wed, EDT) 16:30 UTC = 12:30 EDT — still open.
        assert_eq!(
            nyse_calendar_signal(ts(2024, 7, 3, 16, 30)),
            CalendarSignal::Open
        );
    }

    // ───── Out-of-window dates: no holiday data, falls back to weekday/hours ─────

    #[test]
    fn nyse_calendar_unknown_year_falls_back_to_weekday_hours() {
        // 2030-12-25 (Wed) — outside table coverage. Without holiday data
        // we fall back to weekday + market-hour logic only. EST window
        // applies (December). 15:00 UTC = 10:00 EST = Open.
        assert_eq!(
            nyse_calendar_signal(ts(2030, 12, 25, 15, 0)),
            CalendarSignal::Open,
            "out-of-coverage dates fall back to weekday/hours; the regime \
             gate's oracle-disagreement safety net catches missed holidays"
        );
    }

    // ───── parse_chainlink_streams_relay_market_status tests ─────

    #[test]
    fn parse_chainlink_streams_relay_returns_unknown_until_relay_ships() {
        // Per the 2026-04-29 (afternoon) entry, the parser is stubbed
        // until the soothsayer-streams-relay-program is deployed and
        // posts at least one `streams_relay_update` PDA. Until then, the
        // regime gate composes Unknown + (calendar signal) and behaves
        // sensibly (calendar Open → Open, calendar Closed → Closed).
        for size in [0, 32, 100, 144, 448] {
            let data = vec![0u8; size];
            assert_eq!(
                parse_chainlink_streams_relay_market_status(&data),
                OracleSignal::Unknown,
                "stub should return Unknown for any input shape (size={size})",
            );
        }
    }
}
