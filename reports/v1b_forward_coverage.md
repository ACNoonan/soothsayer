# v1b — Live forward-tape realised coverage (W5)

_Last run: 2026-05-03 21:40 UTC_

Reviewer-immune coverage check on weekends with `fri_ts > 2026-04-24` — the last Friday in the frozen calibration panel. The deployed M5 (AMM-profile) band is applied exactly as the live oracle would serve it; realised coverage is computed against Yahoo Monday open. Sample is small at first and grows by ≈10 observations (universe size) per evaluable weekend.

## Inputs (re-derived from scryer)

- Panel-build window: 2024-01-01 → 2026-05-03
- Frozen-panel cutoff: 2026-04-24
- M5 serving constants: `soothsayer.oracle` (`REGIME_QUANTILE_TABLE`, `C_BUMP_SCHEDULE`, `DELTA_SHIFT_SCHEDULE`).

## Historical cross-check

- Rows checked: 3 (latest historical overlap with `data/processed/v1b_panel.parquet`)
- Columns checked per row: `fri_close, mon_open, factor_ret, regime_pub, point`
- **All re-derived columns match the frozen panel exactly.**

## Forward sample

**No forward weekends evaluable yet.** The next Monday open (2026-05-04) lands in scryer ~14:30 UTC Tuesday; re-run this script once Yahoo's `equities_daily/v1` Monday cron completes.

Result table will populate from that run forward.
