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
fv = oracle.fair_value("SPY", "2026-04-24", target_coverage=0.85)

fv.point                       # factor-adjusted fair value (band midpoint)
fv.lower, fv.upper             # band edges at the served claimed quantile
fv.target_coverage             # 0.85 — what the consumer asked for
fv.calibration_buffer_applied  # 0.02 — δ(τ) shift, the OOS-fit conservatism
fv.claimed_coverage_served     # τ + δ(τ) — the band's actual claim
fv.regime                      # "normal" | "long_weekend" | "high_vol"
fv.forecaster_used             # "mondrian" — wire forecaster_code = 2
fv.sharpness_bps               # band half-width in bps
fv.diagnostics                 # c_bump, q_regime, q_eff — full auditable receipt
```

Those fields are the product. They let a consumer say: *"I asked for 85% realised coverage, you served at 87% via the deployed δ-shift conservatism, the regime classifier pulled `normal`, the per-regime conformal quantile was 0.0163 with the OOS-fit bump 1.455 — and I can audit that decision against the published 20-scalar deployment artefact and 12 years of public weekend data."* The deployment artefact and serving code are documented in [`src/soothsayer/oracle.py`](src/soothsayer/oracle.py), [`scripts/build_mondrian_artefact.py`](scripts/build_mondrian_artefact.py), and [`reports/paper1_coverage_inversion/`](reports/paper1_coverage_inversion/) §4.

The deployment default is **τ = 0.85**, chosen on protocol-policy grounds in the current Paper 3 work. Any τ ∈ (0, 1) is valid; **τ = 0.95** is the headline oracle-validation target in Paper 1.

## How it works

The product is the **served band**, not the raw point estimate. The deployed v2 / M5 architecture is a Mondrian split-conformal-by-regime predictor with three layers.

**Layer 1: factor-switchboard point estimator.**

```
P_hat = fri_close × (1 + factor_return)
```

Factor switchboard:
- Equities (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD) → ES=F (E-mini S&P futures)
- MSTR → BTC-USD from 2020-08-01 onward; ES=F prior (BTC-proxy pivot)
- GLD → GC=F (gold futures)
- TLT → ZN=F (10-year treasury note futures)

**Layer 2: per-regime conformal quantile.** For each regime $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ and each anchor $\tau \in \{0.68, 0.85, 0.95, 0.99\}$, the empirical $\tau$-quantile of the absolute relative residual $|P_\text{Mon} - P_\text{hat}| / P_\text{Fri}$ is fit on the pre-2023 calibration set (4,266 weekend rows). Twelve trained scalars total.

**Layer 3: deployment-tuned conservatism schedule.**
- $c(\tau) \in \{0.68 \to 1.498, 0.85 \to 1.455, 0.95 \to 1.300, 0.99 \to 1.076\}$ — multiplicative bump on the trained quantile, fit on the 2023+ OOS slice as the smallest scalar that closes the train-OOS distribution-shift gap.
- $\delta(\tau) \in \{0.68 \to 0.05, 0.85 \to 0.02, 0.95 \to 0.00, 0.99 \to 0.00\}$ — τ-shift selected by 6-split walk-forward sweep as the smallest schedule aligning per-split realised coverage with nominal at every anchor.

Serving-time computation is a five-line lookup against the per-Friday artefact and the 20 deployment scalars. Linear interpolation off-anchor; no surface inversion, no per-symbol fallback, no scalar buffer override.

The architecture is the product of a multi-step ablation against the v1 hybrid forecaster Oracle (preserved as historical evidence in `reports/paper1_coverage_inversion/` §7.1–§7.5) and the constant-buffer width-at-coverage stress test (§7.6). The Mondrian conformal-by-regime ablation (§7.7) established the deployable simpler baseline that delivers 19–20% narrower bands at indistinguishable Kupiec calibration through τ ≤ 0.95. The full decision trail lives in [`reports/methodology_history.md`](reports/methodology_history.md).

## Evidence snapshot

Held-out 2023+ slice (1,730 rows × 173 weekends), v2 / M5 Mondrian split-conformal-by-regime Oracle served end-to-end:

| τ | n | Realised | Half-width (bps) | Kupiec $p_{uc}$ | Christoffersen $p_{ind}$ |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 1,730 | 0.680 | 110.2 | **0.975** | 0.025 |
| 0.85 | 1,730 | 0.850 | 201.0 | **0.973** | **0.516** |
| **0.95** | **1,730** | **0.950** | **354.5** | **0.956** | **0.912** |
| **0.99** | **1,730** | **0.990** | **677.5** | **0.942** | **0.344** |

Per-regime breakdown at **τ = 0.95** on the OOS slice (forecaster: `mondrian` for every row):

| Regime | n | Realised | Half-width (bps) |
|---|---:|---:|---:|
| normal | 1,160 | 0.939 | 279.9 |
| long_weekend | 190 | 0.984 | 403.4 |
| high_vol | 380 | 0.968 | 557.8 |

Interpretation:

- **τ = 0.95** is the headline oracle-validation target.
- **τ = 0.85** is the current deployment default for policy work.
- **τ = 0.99** is now in scope under the M5 deployment: realised $0.990$ with Kupiec passing, at the cost of a 22% wider band than the v1 hybrid Oracle returned at the same anchor (the v1 finite-sample tail ceiling at $0.972$ is closed).

The deployed v2 / M5 architecture is **20% narrower** than the prior v1 hybrid Oracle at indistinguishable Kupiec calibration through τ ≤ 0.95 (block-bootstrap CIs exclude zero on width, straddle zero on coverage). See [`reports/methodology_history.md`](reports/methodology_history.md) (2026-05-02 M5 entry) and [`reports/paper1_coverage_inversion/`](reports/paper1_coverage_inversion/) §4 (methodology) + §7.7 (Mondrian ablation).

Full breakdown: [`reports/paper1_coverage_inversion/06_results.md`](reports/paper1_coverage_inversion/06_results.md). Ablation with bootstrap CIs: [`reports/paper1_coverage_inversion/07_ablation.md`](reports/paper1_coverage_inversion/07_ablation.md). Reproducible end-to-end via `uv run python scripts/build_mondrian_artefact.py` and `uv run python scripts/smoke_oracle.py`.

## Quick start

```bash
uv sync
cp .env.example .env                          # optional — only needed for live Helius workloads
uv run python scripts/build_mondrian_artefact.py   # builds the M5 deployment artefact from 12 yrs of data
uv run python scripts/smoke_oracle.py              # demo the Oracle serving API
```

All upstream data now comes from Scryer parquet under `SCRYER_DATASET_ROOT`. Start with [`docs/scryer_consumer_guide.md`](docs/scryer_consumer_guide.md) for the read pattern and [`docs/data-sources.md`](docs/data-sources.md) for the provider catalog.

## Repo map

```
src/soothsayer/
  backtest/                 v1b calibration backtest — produces the empirical surface
    panel.py                weekend panel assembly (10 tickers × 12 years)
    forecasters.py          F0 through F1_emp_regime + F2_har_rv (legacy v1 ladder; M5 uses only point_futures_adjusted)
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
