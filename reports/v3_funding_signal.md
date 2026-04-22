# V3 — Kraken Perp Funding Rate as a Weekend-Gap Signal

**Hypothesis (H9):** Kraken xStock perp funding rate at Sunday evening predicts the Monday-open gap for the underlying, beyond what weekend BTC / ES / sector-ETF returns alone predict.

**Gate:** δ significant at 5% **and** ΔR² > 2 pp vs baseline.

**Specification:**
- baseline:   `g_T = α + β_BTC * r_BTC_weekend + β_ES * r_ES_weekend + β_XLK * r_XLK_Fri + ticker FE`
- augmented:  baseline + `δ * f_Sun20UTC`

**Sample:** 102 (weekend, ticker) rows across 8 xStock underlyings; earliest Kraken listing Dec 17 2025 (SPY/QQQ/GLD) and Feb 6 2026 (others).

## Pooled result (ticker-FE OLS)

| sample | n | R² | adj-R² |
|---|---|---|---|
| baseline (same-sample) | 102 | 0.0928 | -0.0069 |
| augmented | 102 | 0.0951 | -0.0155 |

**δ (funding coefficient)** = +0.01257  (SE 0.02624, t +0.479, p 0.6331)
  
**ΔR²** = +0.23 percentage points

## Per-ticker

| ticker   |   n |    delta |        se |      p |    dR2 |
|:---------|----:|---------:|----------:|-------:|-------:|
| SPY      |  18 |  0.02337 | 0.0238179 | 0.3443 | 0.0608 |
| QQQ      |  18 |  0.02217 | 0.0213641 | 0.3184 | 0.0668 |
| GOOGL    |  11 |  0.10064 | 0.33033   | 0.7709 | 0.015  |
| AAPL     |  11 |  0.20312 | 0.145813  | 0.213  | 0.2277 |
| NVDA     |  11 |  0.69664 | 0.39451   | 0.1279 | 0.2669 |
| TSLA     |  11 |  0.16652 | 0.461937  | 0.7308 | 0.0203 |
| MSTR     |  11 | -0.22597 | 0.447342  | 0.6315 | 0.0097 |
| HOOD     |  11 | -0.75239 | 0.757087  | 0.3587 | 0.1264 |

## Decision

**FAIL** — funding is not adding meaningful signal (δ p=0.633, ΔR²=+0.23 pp). Keep as backup input only.

![V3 per-ticker funding coefficient](figures/v3_funding_signal.png)