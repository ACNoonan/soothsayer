# V1b — RedStone incumbent comparison

**Question.** RedStone publishes a point price with no calibration claim or confidence band. If a downstream protocol wraps RedStone's point with a symmetric ±k% band, what k_pct does it take to deliver τ-coverage on the same Friday-close → Monday-open weekend gap that Soothsayer is calibrated against?

**Sample.** Forward-tape baseline. RedStone scryer tape: 2026-03-27 → 2026-05-02. Symbols on tape: ['SPY', 'QQQ', 'MSTR'] (underlier tickers, not xStocks). **n = 12 (symbol × weekend) observations** across 4 weekend(s). Re-run weekly as the panel grows.

**Method.** For each (symbol, fri_ts) where Yahoo has both fri_close and the next-trading-day open, find the latest RedStone tape row with redstone_ts ≤ Friday 15:55 ET (2h lookback). Sweep k_pct ∈ {0.5%, 0.75%, 1%, ..., 20%} symmetric wrap on the RedStone point and ask whether mon_open is inside.

## Pooled — RedStone realised coverage at increasing k_pct

|   k_pct |   halfwidth_bps | scope   |   n |   realized |
|--------:|----------------:|:--------|----:|-----------:|
|  0.0050 |         50.0000 | pooled  |  12 |     0.5833 |
|  0.0075 |         75.0000 | pooled  |  12 |     0.5833 |
|  0.0100 |        100.0000 | pooled  |  12 |     0.7500 |
|  0.0125 |        125.0000 | pooled  |  12 |     0.7500 |
|  0.0150 |        150.0000 | pooled  |  12 |     0.7500 |
|  0.0200 |        200.0000 | pooled  |  12 |     0.8333 |
|  0.0250 |        250.0000 | pooled  |  12 |     1.0000 |
|  0.0300 |        300.0000 | pooled  |  12 |     1.0000 |
|  0.0400 |        400.0000 | pooled  |  12 |     1.0000 |
|  0.0500 |        500.0000 | pooled  |  12 |     1.0000 |
|  0.0750 |        750.0000 | pooled  |  12 |     1.0000 |
|  0.1000 |       1000.0000 | pooled  |  12 |     1.0000 |
|  0.1500 |       1500.0000 | pooled  |  12 |     1.0000 |
|  0.2000 |       2000.0000 | pooled  |  12 |     1.0000 |

## Smallest k_pct delivering τ-coverage

| τ | k_pct | half-width (bps) | realized |
|---:|---:|---:|---:|
| 0.68 | 0.0100 | 100 | 0.750 |
| 0.85 | 0.0250 | 250 | 1.000 |
| 0.95 | 0.0250 | 250 | 1.000 |

## Reading

RedStone does not publish a calibration claim, so the comparator k_pct is *consumer-supplied* — the consumer must back-fit the multiplier on their own historical sample. Soothsayer publishes the calibrated band as a first-class value with an audit-able receipt (regime, forecaster, buffer, target_coverage_bps). On forward-tape data, even a small RedStone wrap (1–3%) tends to over-cover the τ=0.95 target *given the sample's gentle weekend gaps*; this is a sample-window feature, not a generalisation.

## Caveats

- **Tape recency.** RedStone scryer capture began 2026-03-27; the comparison window grows over time.
- **Symbol coverage.** Tape carries SPY, QQQ, MSTR only. xStock-native symbols (SPYx etc.) are not on the public RedStone gateway feed used here (see `reference_redstone_gateway.md`).
- **Sample-size CIs.** With `n = 12` weekend observations a binomial 95% CI on realised coverage is roughly ±40pp; treat this report as a baseline that re-runs as more weekends accrue.

Raw observations: `data/processed/redstone_benchmark_oos.parquet`. Per-(k_pct, scope) breakdown: `reports/tables/redstone_coverage_by_k_pct.csv`. Reproducible via `scripts/redstone_benchmark_comparison.py`.