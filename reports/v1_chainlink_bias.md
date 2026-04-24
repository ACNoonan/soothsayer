# V1 — Chainlink Weekend Bias

**Hypothesis** ([H8](../docs/hypotheses.md)): the Chainlink Data Streams weekend price (last observation before NYSE open) systematically deviates from the realized Monday-open price.

**Sample:** 11 weekend/long-weekend windows from 2026-02-09 through 2026-04-20, 8 xStocks (SPYx, QQQx, GOOGLx, AAPLx, NVDAx, TSLAx, MSTRx, HOODx) = **87 (weekend, ticker) pairs**.

**Method:** for each (weekend, ticker):
- `g_T = ln(P^NYSE_Mon_open / P^NYSE_Fri_close)` — realized Monday gap
- `ĝ_CL = ln(P^CL_Sun-last / P^NYSE_Fri_close)` — Chainlink-implied gap forecast
- `e_T = g_T - ĝ_CL` — residual (positive ⇒ Chainlink underestimated the real move)

**Gate:** pooled `E[e_T]` significant at 5% **and** |mean| > 10 bp ⇒ green-light Phase 1.

## Pooled

| n | mean (bp) | sd (bp) | t | p |
|---|---|---|---|---|
| 87 | -8.77 | 157.35 | -0.52 | 0.6045 |

## Per-ticker

| symbol   |   n |   mean_bp |   sd_bp |      t |     p |   ci_half_bp |
|:---------|----:|----------:|--------:|-------:|------:|-------------:|
| HOODx    |  11 |   -33.762 | 194.141 | -0.577 | 0.577 |      114.73  |
| GOOGLx   |  10 |   -24.149 | 120.628 | -0.633 | 0.542 |       74.766 |
| TSLAx    |  11 |   -19.592 | 138.368 | -0.47  | 0.649 |       81.77  |
| MSTRx    |  11 |   -18.374 | 323.049 | -0.189 | 0.854 |      190.91  |
| QQQx     |  11 |    -4.345 |  86.568 | -0.166 | 0.871 |       51.159 |
| SPYx     |  11 |     1.435 |  78.009 |  0.061 | 0.953 |       46.1   |
| NVDAx    |  11 |     2.106 | 120.234 |  0.058 | 0.955 |       71.054 |
| AAPLx    |  11 |    25.133 |  88.966 |  0.937 | 0.371 |       52.576 |

## Decision

**RETHINK** — Chainlink's weekend bias is not detectable above the 10 bp / 5% gate at this sample size. Reconsider positioning — possibly pivot to a different axis of improvement (e.g. CI calibration, anomaly/fallback alarms).

![per-ticker residuals](figures/v1_chainlink_bias.png)