<p align="center">
  <img src="landing/favicon.svg" width="64" height="64" alt="Soothsayer logo — point inside a band" />
</p>

# soothsayer

> **Real-world assets don't sleep on the weekend.**

The promise of tokenized equities is real 24/7, permissionless markets. The missing infrastructure is a defensible closed-market price. Soothsayer publishes a **calibration-transparent fair-value band** for tokenized RWAs on Solana — built for the weekend, overnight, and halt windows where Chainlink Data Streams holds stale fields, Pyth + Blue Ocean still hand back the weekend, and RedStone Live runs on undisclosed methodology.

The product shape is different from every other oracle on Solana: **consumers specify the realised coverage level they need, and Soothsayer returns the band that empirically delivers it** — with per-(symbol, regime) audit receipts backed by 12 years of public data. The same receipt then supports two layers of output across the repo: the calibrated band primitive itself and downstream protocol-policy analysis. It is designed to be read **alongside** a primary price oracle, not to replace one. The moat is *calibration transparency*, not "our math is better."

**Hard facts.** Held-out 2023+ slice (1,720 rows × 172 weekends × 10 tickers, temporally disjoint from the calibration window) delivers Kupiec + Christoffersen passes at three operating points:

| τ | Realised | Half-width (bps) | Kupiec $p_{uc}$ | Christoffersen $p_{ind}$ |
|---:|---:|---:|---:|---:|
| 0.68 | **0.678** | 135.9 | 0.893 | 0.647 |
| 0.85 | **0.855** | 251.1 | 0.541 | 0.185 |
| 0.95 | **0.950** | 456.0 | 1.000 | 0.485 |

τ=0.99 hits a structural finite-sample tail ceiling and is disclosed as out-of-scope for v1. Full receipt: [`reports/v1b_calibration.md`](reports/v1b_calibration.md). Living methodology log: [`reports/methodology_history.md`](reports/methodology_history.md).

> **Status (2026-04-29):** Phase 0 validation complete; **full PASS**. Phase 1 is now focused on three things in parallel: devnet deploy, Paper 1 to arXiv, and Paper 3's reserve-buffer / liquidation-policy track. Paper drafts: [`reports/paper1_coverage_inversion/`](reports/paper1_coverage_inversion/) (in flight) and [`reports/paper3_liquidation_policy/`](reports/paper3_liquidation_policy/) (planning). See also [`reports/v1b_decision.md`](reports/v1b_decision.md), [`docs/product-spec.md`](docs/product-spec.md), and [`reports/methodology_history.md`](reports/methodology_history.md).

## Why this exists

Tokenized equities trade continuously on-chain while their underlyings do not. That leaves weekends, overnights, and halts as the highest-risk windows for lending protocols, liquidators, and risk teams: the reference market is closed, on-chain liquidity keeps moving, and existing oracle surfaces mostly give you a number without an auditable uncertainty contract.

In practice, the market falls back to one of three weak patterns:

- **Stale hold-forward**: last trade held into the weekend with no explicit uncertainty.
- **Publisher-dispersion diagnostics**: confidence-like intervals that are not aggregate coverage claims.
- **Undisclosed off-hours pricing**: continuous marks with no public calibration evidence.

Soothsayer's claim is narrower and more useful: **publish a band whose realised coverage can be checked against public data**.

## What consumers get

For any `(symbol, as_of, target_coverage)` request, the oracle returns:

```python
fv = oracle.fair_value("SPY", "2026-04-17", target_coverage=0.85)

fv.point                       # factor-adjusted fair value (band midpoint, bias-aware by construction)
fv.lower, fv.upper             # band edges at the served claimed quantile
fv.target_coverage             # 0.85 — what the consumer asked for
fv.calibration_buffer_applied  # 0.045 — empirical buffer added to target before surface inversion
fv.claimed_coverage_served     # which claimed quantile the surface actually delivered
fv.regime                      # "normal" | "long_weekend" | "high_vol"
fv.forecaster_used             # "F1_emp_regime" | "F0_stale" — hybrid receipt
fv.sharpness_bps               # band half-width in bps
fv.diagnostics                 # full auditable receipt
```

Those fields are the product. They let a consumer say: *"I asked for 85% realised coverage, you buffered that request by 4.5pp, served a specific quantile from a specific forecaster in a specific regime, and I can audit that decision against historical evidence."* The calibration surface and receipts are documented in [`reports/v1b_calibration.md`](reports/v1b_calibration.md) and `data/processed/v1b_bounds.parquet`.

The deployment default is **τ = 0.85**, chosen on protocol-policy grounds in the current Paper 3 work. Any τ ∈ (0, 1) is valid; **τ = 0.95** is the headline oracle-validation target in Paper 1.

## How it works

The product is the **served band**, not the raw forecaster. The methodology has three layers.

**Layer 1: raw forecasters.** Two base forecasters generate candidate bands across a claimed-coverage grid:

- `F1_emp_regime` — point estimate is Friday close × per-symbol factor return; conditional sigma is fit by a log-log regression on a per-symbol volatility index plus calendar regressors:
  ```
  log|resid| = α + β·log(vol_idx) + γ_earn·earnings_next_week + γ_long·is_long_weekend
  ```
  Residuals are standardised by predicted σ; empirical quantiles are taken on the standardised residual, then re-scaled by current predicted σ. No Gaussian assumption, no parametric vol model.
- `F0_stale` — Friday close held forward + 20-day Gaussian band. Uninformative but robust; serves as the high-volatility hybrid fallback.

Factor switchboard:
- Equities (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD) → ES=F (E-mini S&P futures)
- MSTR → BTC-USD from 2020-08-01 onward; ES=F prior (BTC-proxy pivot)
- GLD → GC=F (gold futures)
- TLT → ZN=F (10-year treasury note futures)

Per-symbol vol indices: VIX for equities, GVZ for gold, MOVE for treasuries.

**Layer 2: empirical calibration surface.** For each `(symbol, regime, forecaster, claimed_quantile)` cell, Soothsayer measures realised coverage on rolling history and persists the result. At serve time, a request `(s, r, τ)` is mapped to the claimed quantile that historically delivered the buffered target on that bucket.

**Layer 3: serving policy.**
- `REGIME_FORECASTER = {normal: F1_emp_regime, long_weekend: F1_emp_regime, high_vol: F0_stale}`. Evidence: at matched realised coverage, F1 is 27–43% tighter than F0 on `normal`/`long_weekend`. In `high_vol`, F0 is what prevents the OOS Christoffersen-independence rejection that pure-F1 produces (clustered violations).
- `BUFFER_BY_TARGET = {0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.010}`, linearly interpolated off-grid. Per-target tuned on the OOS 2023+ slice as the smallest buffer satisfying realised-within-0.5pp + Kupiec $p_{uc} > 0.10$ + Christoffersen $p_{ind} > 0.05$. The buffer is **load-bearing for the OOS Kupiec pass** at every τ ≤ 0.95; without it, surface inversion alone delivers 92.2% realised at τ=0.95 and Kupiec rejects.

Much more complex stacks were tried and rejected. The current methodology won because it hit the calibration target first and stayed auditable. The full decision trail lives in [`reports/methodology_history.md`](reports/methodology_history.md).

## Evidence snapshot

Held-out 2023+ slice (1,720 rows × 172 weekends), Oracle served end-to-end through all three methodology layers:

| τ | n | Realised | Half-width (bps) | Kupiec $p_{uc}$ | Christoffersen $p_{ind}$ |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 1,720 | 0.678 | 135.9 | **0.893** | **0.647** |
| 0.85 | 1,720 | 0.855 | 251.1 | **0.541** | **0.185** |
| **0.95** | **1,720** | **0.950** | **456.0** | **1.000** | **0.485** |
| 0.99 | 1,720 | 0.977 | 580.8 | 0.000 | 0.956 |

Per-regime breakdown at **τ = 0.95** on the OOS slice:

| Regime | n | Realised | Half-width (bps) | Forecaster served |
|---|---:|---:|---:|---|
| normal | 1,150 | 0.945 | 417.7 | F1_emp_regime |
| long_weekend | 190 | 0.953 | 416.6 | F1_emp_regime |
| high_vol | 380 | 0.963 | 591.6 | F0_stale |

Interpretation:

- **τ = 0.95** is the headline oracle-validation target.
- **τ = 0.85** is the current deployment default for policy work.
- **τ = 0.99** remains out of scope for v1 because the finite-sample tail is too thin to support a clean 1% claim.

Full surface, per-symbol breakdown, calibration curves: [`reports/v1b_calibration.md`](reports/v1b_calibration.md), [`reports/paper1_coverage_inversion/06_results.md`](reports/paper1_coverage_inversion/06_results.md). Ablation with bootstrap CIs: [`reports/v1b_ablation.md`](reports/v1b_ablation.md). Reproducible end-to-end via `uv run python scripts/run_calibration.py` and `uv run python scripts/smoke_oracle.py`.

## Quick start

```bash
uv sync
cp .env.example .env           # optional — only needed if you're running live Helius workloads
uv run python scripts/run_calibration.py     # builds the calibration surface from 12 yrs of data
uv run python scripts/smoke_oracle.py        # demo the Oracle serving API
```

All upstream data now comes from Scryer parquet under `SCRYER_DATASET_ROOT`. Start with [`docs/scryer_consumer_guide.md`](docs/scryer_consumer_guide.md) for the read pattern and [`docs/data-sources.md`](docs/data-sources.md) for the provider catalog.

## Repo map

```
src/soothsayer/
  backtest/                 v1b calibration backtest — produces the empirical surface
    panel.py                weekend panel assembly (10 tickers × 12 years)
    forecasters.py          F0 through F1_emp_regime + F2_har_rv (broken, kept for diagnostic)
    metrics.py              coverage, sharpness, calibration-curve helpers
    regimes.py              pre-publish regime tagging (high_vol, long_weekend, normal)
    calibration.py          builds the per-(symbol, regime, claimed) empirical surface
  oracle.py                 serving-time Oracle.fair_value() API
  chainlink/                v10/v11 decoder + Verifier parser (decoders only;
                            historical scraper.py removed in the April 2026 cutover)
  universe.py, config.py    xStock universe + mint registry, env/paths

scripts/
  run_calibration.py        full backtest + produces product artifacts
  smoke_oracle.py           end-to-end Oracle demo
  (analysis runners only — fetcher / scraper scripts were removed
   in the April 2026 scryer cutover; see CLAUDE.md hard rule #1
   and docs/scryer_consumer_guide.md for the new read pattern.)

docs/
  product-spec.md           customer-selects-coverage product spec
  ROADMAP.md                phase sequencer (product / research / methodology tracks)
  methodology_scope.md      four-question filter for which RWA classes apply
  scryer_consumer_guide.md  canonical data-read pattern (scryer parquet)

reports/
  methodology_history.md    append-only source-of-truth log of methodology decisions
  v1b_decision.md           go/no-go writeup (2026-04-24 frozen snapshot)
  v1b_calibration.md        full results + per-symbol + per-regime tables
  v1b_ablation.md           ablation across forecaster variants + bootstrap CIs
  v1b_buffer_tune.md        per-target buffer sweep
  paper1_coverage_inversion/         Paper 1 drafts (§1, §2, §3, §6, §9 + references)
  paper3_liquidation_policy/         Paper 3 plan + working bibliography (band → action)
  figures/, tables/         persisted charts and tables

notebooks/                  V1-V4 historical notebooks (superseded by v1b — see reports/)
data/
  raw/                      retained for in-flight Phase 1 papers; new code
                            reads from `SCRYER_DATASET_ROOT` instead
                            (canonical: `/Users/adamnoonan/Library/Application
                            Support/scryer/dataset/`).
  processed/                v1b_bounds.parquet + soothsayer-side derived artefacts

`SCRYER_DATASET_ROOT`       `/Users/adamnoonan/Library/Application Support/scryer/dataset/`
                            — the canonical scryer dataset root, written
                            by scryer's launchd-managed daemons. The only
                            sanctioned data path; all upstream fetching,
                            retry, dedup, and parquet schemas live in
                            scryer. Loaders in
                            `src/soothsayer/sources/scryer.py`. See
                            CLAUDE.md and docs/scryer_consumer_guide.md.

crates/                     Rust — production parity port of oracle.py
                            (75/75 byte-for-byte tests vs Python reference;
                             on-chain publish path lives here too).
                            Note: soothsayer-ingest was removed in the
                            April 2026 cutover; on-chain ingest now lives
                            in scryer-fetch-solana.
```

## Current focus

- **Paper 1:** finish the calibration-transparent oracle paper and post it.
- **Paper 3:** turn the calibrated band into a defensible liquidation-policy layer.
- **Devnet:** ship the on-chain router / publish path that serves the same receipt contract in production.

`docs/ROADMAP.md` is the detailed sequencer. `reports/methodology_history.md` is the methodology source of truth.

## Contributing

Methodology critiques, new RWA-class factor proposals, and integration-partner conversations are especially welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache-2.0](LICENSE).
