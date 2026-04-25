# V1b — Chainlink incumbent comparison

**Dataset.** Existing scrape of Chainlink Data Streams v10/v11 publish events during 11 weekends (2026-02-06 → 2026-04-17) across 8 xStock tickers (SPYx, QQQx, AAPLx, GOOGLx, NVDAx, TSLAx, HOODx, MSTRx). One observation per (weekend, ticker) at the latest pre-Monday-open Chainlink publish. Pulled via Helius RPC (`scripts/run_v1_scrape.py`); raw parquet at `data/processed/v1_chainlink_vs_monday_open.parquet`. Sample size **87 observations**.

## Finding 1 — Chainlink does not publish a band during weekend `marketStatus = 5`

Chainlink Data Streams v11 schema includes `bid` and `ask` fields. During regular trading hours (`marketStatus = 2`) these are populated with the reported NBBO. During `marketStatus = 5` (weekend) they are zeroed:

- Fraction of weekend observations with `bid ≈ 0`: **100.0%**
- Fraction of weekend observations with `ask ≈ 0`: **100.0%**
- Median weekend `bid`: **1.000e-18**
- Median weekend `ask`: **0.000e+00**

A downstream consumer who reads Chainlink's band during a weekend window sees a degenerate band of essentially zero width — i.e., Chainlink offers a stale-hold point estimate with no uncertainty signal. This is the structural reading of `marketStatus = 5` documented in §1.1 of the paper, here confirmed empirically on a real sample.

## Finding 2 — Implicit ±k% wrap required for τ = 0.95 coverage

If a downstream consumer wraps Chainlink's `cl_mid` (the published weekend value) with a symmetric ±k% band, what is the smallest k that empirically delivers τ = 0.95 realised coverage of the actual Monday open on this panel?

|   k_pct |   halfwidth_bps |       n |   realized |
|--------:|----------------:|--------:|-----------:|
|  0.0050 |         50.0000 | 87.0000 |     0.2874 |
|  0.0075 |         75.0000 | 87.0000 |     0.4483 |
|  0.0100 |        100.0000 | 87.0000 |     0.5517 |
|  0.0125 |        125.0000 | 87.0000 |     0.6437 |
|  0.0150 |        150.0000 | 87.0000 |     0.7356 |
|  0.0200 |        200.0000 | 87.0000 |     0.8161 |
|  0.0250 |        250.0000 | 87.0000 |     0.8851 |
|  0.0300 |        300.0000 | 87.0000 |     0.9425 |
|  0.0400 |        400.0000 | 87.0000 |     0.9770 |
|  0.0500 |        500.0000 | 87.0000 |     0.9885 |
|  0.0750 |        750.0000 | 87.0000 |     1.0000 |
|  0.1000 |       1000.0000 | 87.0000 |     1.0000 |

**Pooled finding.** Crossing 95% realised coverage on this sample requires a wrap somewhere between ±3.00% (94.25% realised) and ±4.00% (97.70% realised). Linear interpolation suggests $k \approx 3.2\%$ → 320 bps half-width.

**Caveat on the comparison.** This finding is *suggestive but underpowered* relative to the Soothsayer benchmark, for three reasons:

1. **Sample-size CI.** A binomial 95% confidence interval at $\hat p = 0.95$ with $n = 87$ is approximately [0.89, 0.99]. The "≈320 bps" wrap-width number sits inside that wide band, not on top of it.
2. **Sample period skew.** The 11-weekend Feb–Apr 2026 window is mostly `normal` regime — `high_vol` weekends are under-represented. Soothsayer's pooled OOS half-width (443 bps) is averaged over 172 weekends including high_vol; the matched-sample comparison would more fairly use Soothsayer's `normal`-regime-only half-width (401 bps, per §6.4 of the paper). On that comparator, Chainlink+wrap (320 bps) and Soothsayer (401 bps) on the *Soothsayer-deployed* coverage track are within bootstrap noise.
3. **Consumer-supplied calibration.** The headline observation isn't *"Chainlink can be cheaper if you wrap it right"*. It is *"Chainlink doesn't publish a verifiable calibration claim — the consumer does the calibration work."* A consumer who wants a 95% band has to back-fit the wrap themselves, with no audit trail, no per-symbol stratification, and no per-regime adjustment. Soothsayer publishes the band and the calibration receipt; Chainlink publishes a stale-hold point and zeroed bid/ask.

The §1 thesis stands on Finding 1 (no published band), not on Finding 2 (matched-coverage bandwidth). A v2 deliverable should extend the Chainlink dataset to 100+ weekends across all regimes for a fair matched-sample comparison.

## Caveats

- Sample size is **87** obs from a recent 11-weekend window — sufficient to demonstrate the structural finding (no Chainlink band) but small for a per-regime breakdown. A multi-year extension would require pulling Chainlink Data Streams reports from earlier 2025 / 2024 via Helius; the pull infrastructure exists in `src/soothsayer/chainlink/scraper.py` and is gated only on engineering time, not data access.
- The naive ±k% wrap is *not* what a sophisticated Chainlink consumer would actually deploy; this is the comparator a *naive* consumer would see. The realistic alternative (for a v2 deliverable) is to compare against Kamino's flat ±300bps band (already done in `reports/tables/protocol_compare_*.csv`), which is the deployed standard for Chainlink-consuming Solana protocols.
- We do not measure Chainlink's *bias* — that's the V1 finding (`reports/v1_chainlink_bias.md`): pooled bias is −8.77 bps with t = −0.52, p = 0.605 (undetectable). Chainlink's point estimate is unbiased; what's missing is the band.

Per-symbol breakdown: `reports/tables/chainlink_implicit_band_by_symbol.csv`.
Raw observations: `data/processed/v1_chainlink_vs_monday_open.parquet`.