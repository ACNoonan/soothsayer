# earnings_night flag coverage has decayed — live defect

**Found 2026-07-25** while verifying the adaptive band-archive emitter. Not caused by that work; surfaced by it.

## Symptom

The overnight panel carries **zero** `earnings_night` rows after **2025-05-28**, despite running to 2026-04-23. Ten symbols reporting quarterly (six of which have earnings — SPY/QQQ/GLD/TLT are ETFs) should produce roughly 24 flagged nights a year. Observed counts: 2023 → 24, 2024 → 24, **2025 → 12, 2026 → 0**.

## Root cause — upstream, not in the panel logic

`panel._attach_earnings_flag` deliberately excludes rows with `session_confirmed == False`, on the stated rationale that forward-estimated rows "carry the near-duplicate ±1-day source-disagreement the scryer team flagged, **and lie beyond the historical panel anyway**". That second clause was true when written. It is no longer: the panel has caught up to and passed that boundary.

scryer `yahoo/earnings/v2` has the dates — 542 rows for the panel symbols, running to 2026-07-30. What it has lost is *confirmation*:

| year | confirmed | unconfirmed |
|---|---:|---:|
| 2023 | 24 | 0 |
| 2024 | 24 | 0 |
| 2025 | 12 | 6 |
| 2026 | 5 | 14 |

Per the scryer wishlist, `earnings.v2` has two upstreams: a Yahoo one-shot backfill that derives confirmed BMO/AMC sessions from deep history, and a Finnhub forward runner whose free tier has no history. The forward runner keeps the *dates* current; only the backfill confirms *sessions*. The backfill has not been re-run since roughly mid-2025, so recent quarters are forward-only and get excluded.

The panel is behaving exactly as specified. The specification's assumption expired.

## Why this matters — three consequences, in order of severity

**1. Live serving is wrong today.** Any earnings night served now is classified `normal` and receives a ≈3% band where the calibrated earnings band is ≈25%. That is precisely the failure W12 measured: without the partition, `earnings_night` coverage is **0.333 against a claimed 0.95**. The regime cell exists to prevent this and is currently not firing.

**2. The paper's `earnings_night` sample is smaller than it should be.** OOS n = 60 is the number every power caveat in W14/W16/W17 is written around. Restoring confirmation for 2025-06 → 2026-04 adds roughly 14 nights — a ~23% increase on the thinnest, most-cited cell in the evidence pack.

**3. It fails silently and in the safe-looking direction.** A missing `earnings_night` row is not an error; it is a `normal` row. Nothing warns, and pooled coverage barely moves because the cell is ~1% of the panel. This is the third silent-failure-in-the-conservative-direction found in this programme, after the σ̂ contamination and the triple-witching hole.

## Fix

**Upstream, in scryer**: re-run the Yahoo earnings backfill to confirm sessions through the present, then rebuild the overnight panel. This is an operator action, not a code change — the runner and schema already exist (scryer wishlist, `earnings.v2 session timing`, phase 126).

**Then, in soothsayer**: add a build-time assertion that the panel's most recent `earnings_night` row is within one quarter of the panel end. The defect's whole character is that it is silent; a loud check is the durable fix, and it belongs next to the existing σ̂ warm-up guard.

## Not done here

Neither fix is applied. The backfill is a scryer operator run (CLAUDE.md rules #1/#2 — data work lands upstream first), and the panel rebuild depends on it. Filed as a carry-forward note on the scryer `earnings.v2` wishlist entry.
