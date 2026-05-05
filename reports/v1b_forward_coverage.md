# v1b — Live forward-tape realised coverage (W5)

_Last run: 2026-05-05 13:00 UTC_

Reviewer-immune coverage check on weekends with `fri_ts > 2026-04-24` — the last Friday in the frozen calibration panel. The deployed M5 (AMM-profile) band is applied exactly as the live oracle would serve it; realised coverage is computed against Yahoo Monday open. Sample is small at first and grows by ≈10 observations (universe size) per evaluable weekend.

## Inputs (re-derived from scryer)

- Panel-build window: 2024-01-01 → 2026-05-05
- Frozen-panel cutoff: 2026-04-24
- M5 serving constants: `soothsayer.oracle` (`REGIME_QUANTILE_TABLE`, `C_BUMP_SCHEDULE`, `DELTA_SHIFT_SCHEDULE`).

## Historical cross-check

- Rows checked: 3 (latest historical overlap with `data/processed/v1b_panel.parquet`)
- Columns checked per row: `fri_close, mon_open, factor_ret, regime_pub, point`
- **All re-derived columns match the frozen panel exactly.**

## Forward sample

- Forward weekends evaluable: 1 (2026-05-01)
- Symbol-weekend rows per τ: 10

## Realised coverage by τ

| τ (target) | served τ' | n | hits | realised | 95% Wilson CI | mean half-width (bps) |
|---:|---:|---:|---:|---:|---|---:|
| 0.68 | 0.73 | 10 | 8 | 0.800 | [0.490, 0.943] | 113.0 |
| 0.85 | 0.87 | 10 | 10 | 1.000 | [0.722, 1.000] | 189.7 |
| 0.95 | 0.95 | 10 | 10 | 1.000 | [0.722, 1.000] | 280.5 |
| 0.99 | 0.99 | 10 | 10 | 1.000 | [0.722, 1.000] | 535.5 |

_τ' = τ + δ(τ) is the served claim after the walk-forward δ-shift; consumer-facing target is τ. Realised coverage should sit at or above τ on average (the schedule is conservative by construction); with this small a sample the Wilson CI is wide and a single miss can drop the headline materially._

## Per-regime composition (informational)

| τ | normal | long_weekend | high_vol |
|---:|---:|---:|---:|
| 0.68 | 10 | 0 | 0 |
| 0.85 | 10 | 0 | 0 |
| 0.95 | 10 | 0 | 0 |
| 0.99 | 10 | 0 | 0 |

## Per-(symbol, τ) detail

| symbol | fri_ts | regime | τ | mon_open | point | hw bps | hit |
|---|---|---|---:|---:|---:|---:|:---:|
| AAPL | 2026-05-01 | normal | 0.68 | 279.6550 | 280.6811 | 112.9 | ✓ |
| AAPL | 2026-05-01 | normal | 0.85 | 279.6550 | 280.6811 | 189.7 | ✓ |
| AAPL | 2026-05-01 | normal | 0.95 | 279.6550 | 280.6811 | 280.4 | ✓ |
| AAPL | 2026-05-01 | normal | 0.99 | 279.6550 | 280.6811 | 535.4 | ✓ |
| GLD | 2026-05-01 | normal | 0.68 | 418.8000 | 423.1068 | 112.7 | ✓ |
| GLD | 2026-05-01 | normal | 0.85 | 418.8000 | 423.1068 | 189.3 | ✓ |
| GLD | 2026-05-01 | normal | 0.95 | 418.8000 | 423.1068 | 279.8 | ✓ |
| GLD | 2026-05-01 | normal | 0.99 | 418.8000 | 423.1068 | 534.3 | ✓ |
| GOOGL | 2026-05-01 | normal | 0.68 | 385.6300 | 386.4350 | 112.9 | ✓ |
| GOOGL | 2026-05-01 | normal | 0.85 | 385.6300 | 386.4350 | 189.7 | ✓ |
| GOOGL | 2026-05-01 | normal | 0.95 | 385.6300 | 386.4350 | 280.4 | ✓ |
| GOOGL | 2026-05-01 | normal | 0.99 | 385.6300 | 386.4350 | 535.4 | ✓ |
| HOOD | 2026-05-01 | normal | 0.68 | 74.7000 | 73.8023 | 112.9 | ✗ |
| HOOD | 2026-05-01 | normal | 0.85 | 74.7000 | 73.8023 | 189.7 | ✓ |
| HOOD | 2026-05-01 | normal | 0.95 | 74.7000 | 73.8023 | 280.4 | ✓ |
| HOOD | 2026-05-01 | normal | 0.99 | 74.7000 | 73.8023 | 535.4 | ✓ |
| MSTR | 2026-05-01 | normal | 0.68 | 180.9000 | 178.3027 | 113.5 | ✗ |
| MSTR | 2026-05-01 | normal | 0.85 | 180.9000 | 178.3027 | 190.5 | ✓ |
| MSTR | 2026-05-01 | normal | 0.95 | 180.9000 | 178.3027 | 281.7 | ✓ |
| MSTR | 2026-05-01 | normal | 0.99 | 180.9000 | 178.3027 | 537.8 | ✓ |
| NVDA | 2026-05-01 | normal | 0.68 | 199.5000 | 198.8333 | 112.9 | ✓ |
| NVDA | 2026-05-01 | normal | 0.85 | 199.5000 | 198.8333 | 189.7 | ✓ |
| NVDA | 2026-05-01 | normal | 0.95 | 199.5000 | 198.8333 | 280.4 | ✓ |
| NVDA | 2026-05-01 | normal | 0.99 | 199.5000 | 198.8333 | 535.4 | ✓ |
| QQQ | 2026-05-01 | normal | 0.68 | 674.6600 | 675.4522 | 112.9 | ✓ |
| QQQ | 2026-05-01 | normal | 0.85 | 674.6600 | 675.4522 | 189.7 | ✓ |
| QQQ | 2026-05-01 | normal | 0.95 | 674.6600 | 675.4522 | 280.4 | ✓ |
| QQQ | 2026-05-01 | normal | 0.99 | 674.6600 | 675.4522 | 535.4 | ✓ |
| SPY | 2026-05-01 | normal | 0.68 | 720.0700 | 722.0420 | 112.9 | ✓ |
| SPY | 2026-05-01 | normal | 0.85 | 720.0700 | 722.0420 | 189.7 | ✓ |
| SPY | 2026-05-01 | normal | 0.95 | 720.0700 | 722.0420 | 280.4 | ✓ |
| SPY | 2026-05-01 | normal | 0.99 | 720.0700 | 722.0420 | 535.4 | ✓ |
| TLT | 2026-05-01 | normal | 0.68 | 85.3500 | 85.6463 | 112.8 | ✓ |
| TLT | 2026-05-01 | normal | 0.85 | 85.3500 | 85.6463 | 189.4 | ✓ |
| TLT | 2026-05-01 | normal | 0.95 | 85.3500 | 85.6463 | 280.0 | ✓ |
| TLT | 2026-05-01 | normal | 0.99 | 85.3500 | 85.6463 | 534.6 | ✓ |
| TSLA | 2026-05-01 | normal | 0.68 | 390.2300 | 391.5749 | 112.9 | ✓ |
| TSLA | 2026-05-01 | normal | 0.85 | 390.2300 | 391.5749 | 189.7 | ✓ |
| TSLA | 2026-05-01 | normal | 0.95 | 390.2300 | 391.5749 | 280.4 | ✓ |
| TSLA | 2026-05-01 | normal | 0.99 | 390.2300 | 391.5749 | 535.4 | ✓ |

## Re-run

```
uv run python scripts/run_forward_coverage.py
```

Idempotent. Safe to re-run weekly (Tuesday after Yahoo's Monday-open cron lands). Each new evaluable weekend adds ≈10 observations across the universe.

