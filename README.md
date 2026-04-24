# soothsayer

**A calibration-transparent fair-value oracle for tokenized RWAs on Solana.**

Soothsayer publishes a fair-value estimate plus an **auditable empirical confidence band** for tokenized equities (xStocks) and other closed-market RWAs during weekend, overnight, and halt windows — the hours when Chainlink Data Streams carries stale values, Pyth's Blue Ocean coverage drops off, and RedStone Live relies on undisclosed methodology.

The product shape is different from every other oracle on Solana: **consumers specify the realized coverage level they need, and Soothsayer returns the band that empirically delivers it — with per-(symbol, regime) receipts backed by 12 years of public data.**

It is designed to be read **alongside** a primary price oracle, not to replace one. The moat is *calibration transparency*, not "our math is better."

> **Status (2026-04-24):** Phase 0 validation complete. PASS-LITE verdict: factor-adjusted fair value with empirical-quantile CI is calibrated at 95.0% realized coverage on normal weekends with 28% tighter bands than stale-hold, across 5,986 weekends × 10 tickers × 12 years. Phase 1 MVP underway. See [`reports/v1b_decision.md`](reports/v1b_decision.md), [`reports/v1b_calibration.md`](reports/v1b_calibration.md), and [`reports/option_c_spec.md`](reports/option_c_spec.md).

## Why this exists

Tokenized equities trade 24/7 on-chain while their underlyings are open only ~32% of wall-clock hours. The other 68% — weekends, overnights, halts — is when on-chain liquidity diverges from fundamental price, when bad liquidations happen, and when every existing oracle falls back to one of:

- **Stale last-trade held forward** (Chainlink `marketStatus=5`, no uncertainty signal)
- **An aggregate median of currently-submitting publishers** (Pyth, CI derived from quote dispersion, not drift/vol)
- **Undisclosed methodology** (RedStone Live, marketed as 24/7 equity coverage)

None publish a calibration claim that a protocol integrator can verify against public data. Soothsayer does.

## What we publish

For any `(symbol, as_of, target_coverage)` request, the oracle returns:

```python
fv = oracle.fair_value("SPY", "2026-04-17", target_coverage=0.95)

fv.point                      # 699.95 — factor-adjusted fair value
fv.lower                      # 688.35
fv.upper                      # 711.54
fv.claimed_coverage_served    # 0.975 — which claimed quantile we used
fv.regime                     # "normal"
fv.sharpness_bps              # 163 bps half-width
fv.diagnostics                # auditable receipt
```

The `claimed_coverage_served` field is the trust primitive. It says: *"to deliver your requested 95% realized coverage on a (SPY, normal) bucket, we looked up our empirical calibration table and served you the 97.5% claimed quantile, because that's what historically covers 95% of Mondays."* Any consumer can verify that mapping on `reports/v1b_calibration.md`.

## The methodology (one screen)

**Point estimate.** Friday close × per-symbol factor return over the weekend:
- Equities (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD) → ES=F (E-mini S&P futures)
- MSTR → BTC-USD from 2020-08-01 onward; ES=F prior (MSTR pivoted to BTC-proxy)
- GLD → GC=F (gold futures)
- TLT → ZN=F (10-year treasury note futures)

**Confidence band.** Walk-forward data-driven regime model:

```
log|resid| = α + β·log(vol_idx) + γ_earn·earnings_next_week + γ_long·is_long_weekend
```

with per-symbol `vol_idx`: VIX for equities, GVZ for gold, MOVE for treasuries. Residuals are standardised by the predicted σ, empirical quantiles are taken on the standardised residual, then re-scaled by the current predicted σ. No Gaussian assumption, no parametric vol model, no econometric black box.

That's the entire method stack. The Madhavan-Sobczyk / VECM / HAR-RV / Hawkes stack originally researched was tested and found unnecessary — simpler methodology was sufficient to calibrate.

## Evidence

| Regime | N weekends | Realized at 95% claim | CI half-width |
|---|---|---|---|
| normal (65%) | 3,924 | **95.0%** | 252 bps |
| long_weekend (10%) | 630 | 93.8% | 275 bps |
| high_vol (24%) | 1,432 | 91% | 401 bps |
| F0 stale-hold (for comparison) | 5,986 | 97.6% | 402 bps (blunt blanket) |

Full tables, per-symbol breakdown, calibration curves: [`reports/v1b_calibration.md`](reports/v1b_calibration.md). Reproducible end-to-end via `uv run python scripts/run_calibration.py` and `uv run python scripts/smoke_oracle.py`.

## Setup

```bash
uv sync
cp .env.example .env           # optional — only needed if you're running live Helius workloads
uv run python scripts/run_calibration.py     # builds the calibration surface from 12 yrs of data
uv run python scripts/smoke_oracle.py        # demo the Oracle serving API
```

Phase 0 runs on free data only: yfinance (equities + futures + vol indices + BTC + earnings_dates) + Helius free tier (reserved for Phase 1 on-chain work). See [`docs/data-sources.md`](docs/data-sources.md) for the full provider catalog.

## Repo layout

```
src/soothsayer/
  backtest/                 v1b calibration backtest — produces the empirical surface
    panel.py                weekend panel assembly (10 tickers × 12 years)
    forecasters.py          F0 through F1_emp_regime + F2_har_rv (broken, kept for diagnostic)
    metrics.py              coverage, sharpness, calibration-curve helpers
    regimes.py              pre-publish regime tagging (high_vol, long_weekend, normal)
    calibration.py          builds the per-(symbol, regime, claimed) empirical surface
  oracle.py                 serving-time Oracle.fair_value() API
  sources/                  data source modules (yfinance, kraken_perp, jupiter, helius)
  chainlink/                v10/v11 decoder + Verifier parser (Phase 1 consumer lookup)
  universe.py, config.py, cache.py

scripts/
  run_calibration.py        full backtest + produces product artifacts
  smoke_oracle.py           end-to-end Oracle demo
  ...                       (legacy V1-V3 scrape scripts)

reports/
  v1b_decision.md           go/no-go writeup
  v1b_calibration.md        full results + per-symbol + per-regime tables
  option_c_spec.md          product spec (customer-selects-coverage)
  figures/, tables/         plots and persisted CSVs

notebooks/                  V1-V4 historical notebooks (superseded by v1b — see reports/)
data/
  raw/                      cached source pulls (gitignored)
  processed/                v1b_bounds.parquet (product artifact)

crates/                     Rust — Phase 1 on-chain publish path (scaffold)
```

## Roadmap

- **Phase 0 — done.** V1b decade-scale backtest → PASS-LITE → Option C product shape locked.
- **Phase 1 (now, 4 weeks).** Live-mode Oracle serving + on-chain publish path (Switchboard or Anchor per 1-day prototype) + xStock-specific calibration overlay once V5 tape has ≥ 1 month of data + Kamino-fork consumer demo + x402-gated premium endpoint.
- **Phase 2 (weeks 5–6).** Public comparator dashboard (Soothsayer vs Chainlink vs Pyth across every weekend of 2025–2026) + methodology writeup + hackathon submission.
- **Phase 3 (post-hackathon).** Adviser-driven VC intros, Kamino BD deepening, first B2B data-license conversation, third-party publisher replication path.

## Contributing

Methodology critiques, new RWA-class factor proposals, and integration-partner conversations are especially welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache-2.0](LICENSE).
