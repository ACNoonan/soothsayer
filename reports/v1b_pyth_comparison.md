# V1b — Pyth Hermes incumbent comparison

**Question.** If a downstream protocol naively reads Pyth's published `price ± k·conf` as a probability statement, what realised coverage do they receive on the same OOS panel where Soothsayer delivers τ = 0.95 at Kupiec $p_{uc}$ = 1.000?

**Method.** For each (symbol, fri_ts) in the 2024+ subset of the OOS panel (1,200 (symbol × weekend) pairs across 120 weekends), pull Pyth's (price, conf) via the Hermes Benchmarks API at the nearest publish to Friday 15:55 ET. Retry up to 2 hours back if the queried timestamp falls outside Pyth's publish cadence. For $k \in \{1,\, 1.96,\, 3,\, 5,\, 10,\, 25,\, 50,\, 100,\, 250,\, 500,\, 1000\}$, define Pyth's implicit band $[\text{price} - k\cdot\text{conf},\, \text{price} + k\cdot\text{conf}]$ and check whether the realised Monday open lies inside. Aggregate to pooled and per-symbol realised coverage.

The panel is restricted to 2024+ because Pyth's regular-hours US-equity feeds did not exist before then; queries against 2023 timestamps return empty consistently across all tested tickers. We also note up-front that Pyth's documentation describes `conf` as a publisher-dispersion diagnostic, not a probability-of-coverage claim, so the multiplier $k$ found here is a *consumer-supplied calibration*, not a Pyth-published one.

## Per-symbol availability

| symbol | Pyth available rate |
|:---|---:|
| SPY   | 0.692 |
| QQQ   | 0.650 |
| TLT   | 0.592 |
| TSLA  | 0.250 |
| MSTR  | 0.017 |
| GLD   | 0.008 |
| AAPL  | 0.000 |
| GOOGL | 0.000 |
| HOOD  | 0.000 |
| NVDA  | 0.000 |

Pooled availability across 2024+ is **22.1%** (265 of 1,200 attempts had Pyth data within ±2h of Friday close). Coverage analysis below uses the 265-obs subset; on this subset, the symbol mix is **SPY-, QQQ-, TLT- and TSLA-heavy** — large-cap, low-realised-volatility names by composition, which biases the comparison toward easier weekends than Soothsayer's pooled OOS slice.

## Pooled realised coverage at increasing k

| $k$ | $n$ | realised | mean half-width (bps) |
|---:|---:|---:|---:|
| 1.00   | 265 | 0.049 |    5.6 |
| 1.96   | 265 | 0.102 |   11.0 |
| 3.00   | 265 | 0.155 |   16.8 |
| 5.00   | 265 | 0.242 |   27.9 |
| 10.00  | 265 | 0.434 |   55.9 |
| 25.00  | 265 | 0.800 |  139.7 |
| **50.00**  | **265** | **0.951** |  **279.5** |
| 100.00 | 265 | 0.992 |  559.0 |
| 250.00 | 265 | 1.000 | 1397.4 |
| 500.00 | 265 | 1.000 | 2794.9 |
| 1000.00| 265 | 1.000 | 5589.7 |

**Naive Pyth at $k = 1.96$ (the textbook 95% Gaussian wrap) delivers 10.2% realised coverage**. The Pyth conf field is so tight relative to weekend-gap dispersion that even tripling it (k = 3) recovers only 15.5%. Reading Pyth's published CI as a probability statement at face value mis-calibrates by a factor of 9–10 in the under-cover direction.

To get the *implied* probability statement to match 95% realised, the consumer would need to scale Pyth's conf by approximately **50×** — at which point the published number is no longer Pyth's calibration claim, it is the consumer's.

## Comparison to Soothsayer at τ = 0.95

|  | n | realised | mean half-width (bps) |
|:---|---:|---:|---:|
| Soothsayer (deployed, OOS pooled) | 1,720 | 0.950 |  442.7 |
| Pyth + naive $\pm 1.96\cdot\text{conf}$ | 265 | 0.102 |   11.0 |
| Pyth + consumer-fit $\pm 50\cdot\text{conf}$ | 265 | 0.951 |  279.5 |

On the *available subset* (265 obs, biased toward SPY/QQQ/TLT/TSLA), Pyth+50× is approximately 37% narrower than Soothsayer's *full-panel* deployed band at matched coverage. Three reasons this is not a Soothsayer-loses finding:

1. **Sample composition.** The 265-obs Pyth subset is dominated by SPY, QQQ, TLT — Soothsayer's `normal`-regime large-cap weekends. Soothsayer's `normal`-regime-only OOS half-width at τ = 0.95 is **401 bps** (per §6.4 of the paper), not 443. The Pyth-eligible subset doesn't include any of the high-volatility weekends Soothsayer's pooled number averages over.
2. **Sample size.** A binomial 95% CI on $\hat p = 0.951$ with $n = 265$ is approximately $[0.92, 0.98]$. The "match" between Pyth+50× and Soothsayer's calibration target is wider than the comparison suggests.
3. **Consumer-supplied calibration.** Pyth does not publish $k = 50$ as the right scaling; Pyth publishes $k = 1$ (raw `conf`) and the consumer must back-fit the multiplier on their own historical sample, with no audit trail and no per-symbol stratification. The price you see in the comparison table costs the consumer a separate calibration backtest. Soothsayer publishes the inversion as a first-class API parameter and exposes the receipt.

## Reading

The §1 thesis is supported, not weakened, by this comparison: Pyth's published CI is documented as an aggregation diagnostic, and our backtest confirms empirically that the published value, read at face as a probability statement, mis-calibrates by an order of magnitude. To match Soothsayer's calibration claim, a Pyth consumer must do the calibration work themselves — at which point they have left Pyth's published claim behind. This is exactly the verifiable-calibration-claim gap that the coverage-inversion primitive fills.

The "Pyth+50× is narrower" observation on the matched subset is empirically interesting and deserves disclosure: when a consumer is willing to accept a low-volatility ticker subset and a 30-month calibration sample, naive scaling on Pyth's already-tight conf can produce a competitive band. But that consumer is no longer reading Pyth's calibration claim; they are constructing their own.

## Caveats

- **2024+ restriction.** Pyth's RH equity feeds did not publish before 2024; the comparison covers 120 of the 172 OOS weekends in our headline sample.
- **Per-symbol availability is uneven.** AAPL, GOOGL, HOOD, NVDA have 0% Pyth coverage at our query times despite valid feed IDs — Pyth may publish these tickers only during specific market hours that don't include our 15:55 ET probe target, or the feeds may have launched after the OOS window opens.
- **Single-feed restriction.** The benchmark uses Pyth's regular-hours feeds (`Equity.US.{TICKER}/USD`). Pyth also publishes overnight (`.ON`) and pre/post-market (`.PRE` / `.POST`) feeds; an extension comparing those is v2 work.
- **No bootstrap CIs on Pyth.** Soothsayer's coverage claims carry weekend-block bootstrap CIs (`reports/v1b_walkforward.md`); the Pyth comparison numbers here are point estimates on a 265-obs sample. A v2 deliverable should include matched-sample bootstrap.

Raw observations: `data/processed/pyth_benchmark_oos.parquet`. Per-(k, scope) breakdown: `reports/tables/pyth_coverage_by_k.csv`. Reproducible via `scripts/pyth_benchmark_comparison.py`.
