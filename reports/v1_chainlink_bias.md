# V1 — Chainlink Weekend Bias

**Hypothesis** ([H8](../docs/hypotheses.md)): the Chainlink Data Streams weekend price (last observation before NYSE open) systematically deviates from the realized Monday-open price.

**Sample:** 6 weekend/long-weekend windows from 2026-02-09 through 2026-04-20, 8 xStocks (SPYx, QQQx, GOOGLx, AAPLx, NVDAx, TSLAx, MSTRx, HOODx) = **48 (weekend, ticker) pairs**.

**Method:** for each (weekend, ticker):
- `g_T = ln(P^NYSE_Mon_open / P^NYSE_Fri_close)` — realized Monday gap
- `ĝ_CL = ln(P^CL_Sun-last / P^NYSE_Fri_close)` — Chainlink-implied gap forecast
- `e_T = g_T - ĝ_CL` — residual (positive ⇒ Chainlink underestimated the real move)

**Gate:** pooled `E[e_T]` significant at 5% **and** |mean| > 10 bp ⇒ green-light Phase 1.

## Pooled

| n | mean (bp) | sd (bp) | t | p |
|---|---|---|---|---|
| 48 | -48.30 | 142.66 | -2.35 | 0.02326 |

## Per-ticker

| symbol   |   n |   mean_bp |   sd_bp |      t |     p |   ci_half_bp |
|:---------|----:|----------:|--------:|-------:|------:|-------------:|
| MSTRx    |   6 |  -202.197 | 315.916 | -1.568 | 0.178 |      252.785 |
| HOODx    |   6 |   -64.563 | 176.904 | -0.894 | 0.412 |      141.552 |
| NVDAx    |   6 |   -43.859 |  73.387 | -1.464 | 0.203 |       58.722 |
| GOOGLx   |   6 |   -23.909 |  97.604 | -0.6   | 0.575 |       78.099 |
| QQQx     |   6 |   -23.468 |  26.807 | -2.144 | 0.085 |       21.45  |
| TSLAx    |   6 |   -19.35  |  79.273 | -0.598 | 0.576 |       63.431 |
| SPYx     |   6 |   -17.863 |   9.713 | -4.505 | 0.006 |        7.772 |
| AAPLx    |   6 |     8.809 |  44.104 |  0.489 | 0.645 |       35.291 |

## Decision

**GREEN-LIGHT** — Chainlink's weekend aggregation exhibits detectable bias. Proceed to Phase 1 build.

![per-ticker residuals](figures/v1_chainlink_bias.png)