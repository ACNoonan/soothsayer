<p align="center">
  <img src="landing/favicon.svg" width="64" height="64" alt="Soothsayer logo — point inside a band" />
</p>

# soothsayer

> **Real-world assets don't sleep on the weekend.**

The promise of tokenized equities is real 24/7, permissionless markets. The missing infrastructure is a defensible closed-market price. Soothsayer publishes a **calibration-transparent fair-value band** for tokenized RWAs on Solana — built for the weekend, overnight, and halt windows where Chainlink Data Streams holds stale fields, Pyth + Blue Ocean still hand back the weekend, and RedStone Live runs on undisclosed methodology.

The product shape is different from every other oracle on Solana: **Soothsayer publishes a calibrated band per symbol — point plus bounds plus a receipt — whose realised coverage rate can be checked against 12 years of public weekend data**. It consumes upstream oracle and market signals (Pyth, Chainlink, RedStone, Kamino-Scope, Yahoo, Kraken) and republishes them as a band whose coverage claim is empirically falsifiable, with per-(symbol, regime) audit receipts naming the exact scalars used. The same receipt then supports two layers of output across the repo: the calibrated band primitive itself and downstream protocol-policy analysis. Other oracles publish a number. Soothsayer publishes a number, a band, and a coverage claim — and stakes the product on that coverage claim being verifiable from public data.

**Hard facts.** Held-out 2023+ slice (1,730 rows × 173 weekends × 10 tickers, temporally disjoint from the calibration window) delivers Kupiec + Christoffersen passes at all four operating points under the deployed M6 LWC (σ̂ EWMA HL=8) Oracle:

| τ | Realised | Half-width (bps) | Kupiec $p_{uc}$ | Christoffersen $p_{ind}$ |
|---:|---:|---:|---:|---:|
| 0.68 | **0.693** | 130.8 | 0.264 | 0.244 |
| 0.85 | **0.855** | 213.6 | 0.565 | 0.403 |
| 0.95 | **0.950** | 370.6 | 0.956 | 0.603 |
| 0.99 | **0.990** | 635.0 | 0.942 | 1.000 |

The headline new evidence under M6: **per-symbol Kupiec at τ=0.95 passes for 10/10 symbols** (vs 2/10 under the prior M5 deployment), and held-out-symbol (LOSO) realised-coverage std collapses 5.7× (0.0759 → 0.0134). Full receipt: [`reports/m6_validation.md`](reports/m6_validation.md). σ̂ promotion evidence: [`reports/m6_sigma_ewma.md`](reports/m6_sigma_ewma.md). Living methodology log: [`reports/methodology_history.md`](reports/methodology_history.md).

> **Status (2026-05-04):** Phase 0 validation complete; **full PASS**. M6 (LWC + σ̂ EWMA HL=8) is the deployed forecaster as of 2026-05-04 — Phases 1–6 of the M6 promotion are closed (Python serving + full robustness battery + 4-DGP simulation study + sample-size sweep + EWMA σ̂ promotion + forward-tape harness on launchd). Phase 7 (Rust parity port for M6) is gated. Phase 1 product work continues in parallel: devnet deploy, Paper 1 revision against M6, and Paper 3's reserve-buffer / liquidation-policy track. Paper drafts: [`reports/paper1_coverage_inversion/`](reports/paper1_coverage_inversion/) and [`reports/paper3_liquidation_policy/`](reports/paper3_liquidation_policy/). See [`STATUS.md`](STATUS.md) for the agent-facing current-state page, [`reports/active/m6_refactor.md`](reports/active/m6_refactor.md) (in-flight working doc), [`docs/product-spec.md`](docs/product-spec.md), and [`reports/methodology_history.md`](reports/methodology_history.md).

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
fv = oracle.fair_value_lwc("SPY", "2026-04-24", target_coverage=0.85)

fv.point                       # factor-adjusted fair value (band midpoint)
fv.lower, fv.upper             # band edges at the served claimed quantile
fv.target_coverage             # 0.85 — what the consumer asked for
fv.calibration_buffer_applied  # 0.00 — δ(τ) shift; M6 deploys δ=0 at every τ
fv.claimed_coverage_served     # τ + δ(τ) — the band's actual claim
fv.regime                      # "normal" | "long_weekend" | "high_vol"
fv.forecaster_used             # "lwc" — wire forecaster_code = 3
fv.sharpness_bps               # band half-width in bps
fv.diagnostics                 # sigma_hat_sym_pre_fri, q_regime_lwc, c_bump — full auditable receipt
```

Those fields are the product. They let a consumer say: *"I asked for 85% realised coverage, you served exactly that via the deployed schedule, the regime classifier pulled `normal`, the per-regime LWC quantile was 1.219 standardised units, my pre-Friday EWMA-HL=8 σ̂ for SPY was 0.008, the OOS-fit c-bump was 1.000 — and I can audit that decision against the published 20-scalar deployment artefact and 12 years of public weekend data."* The deployment artefact and serving code are documented in [`src/soothsayer/oracle.py`](src/soothsayer/oracle.py), [`scripts/build_lwc_artefact.py`](scripts/build_lwc_artefact.py), and [`reports/paper1_coverage_inversion/`](reports/paper1_coverage_inversion/) §4. The M5 path (`Oracle.fair_value`, `forecaster_code = 2`) remains in place as the named reference baseline for the §7 ablation.

The deployment default is **τ = 0.85**, chosen on protocol-policy grounds in the current Paper 3 work. Any τ ∈ (0, 1) is valid; **τ = 0.95** is the headline oracle-validation target in Paper 1.

## How it works

The product is the **served band**, not the raw point estimate. The deployed M6 architecture is a **Locally-Weighted Conformal (LWC)** predictor with per-symbol scale standardisation, fit Mondrian-style by `regime_pub`. Three layers.

**Layer 1: factor-switchboard point estimator.** (Unchanged from M5.)

```
P_hat = fri_close × (1 + factor_return)
```

Factor switchboard:
- Equities (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD) → ES=F (E-mini S&P futures)
- MSTR → BTC-USD from 2020-08-01 onward; ES=F prior (BTC-proxy pivot)
- GLD → GC=F (gold futures)
- TLT → ZN=F (10-year treasury note futures)

**Layer 2: per-symbol scale standardisation.** A pre-Friday EWMA estimator of the per-symbol relative-residual std,

$$\hat{\sigma}_\text{sym}(t) = \text{EWMA}_{\text{HL}=8}\big(|P_\text{Mon} - P_\text{hat}| / P_\text{Fri}\big)\big|_{t' < t}$$

with weekend half-life 8 (decay $\lambda = 0.5^{1/8} \approx 0.917$), strictly pre-Friday, ≥ 8 past observations required. This is the single lever that distinguishes M6 from the prior M5 deployment; it absorbs cross-symbol scale heterogeneity that M5 pooled away.

**Layer 3: per-regime conformal quantile on the standardised score, plus deployment-tuned conservatism.** For each regime $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ and each anchor $\tau \in \{0.68, 0.85, 0.95, 0.99\}$, the empirical $\tau$-quantile of the standardised score $|P_\text{Mon} - P_\text{hat}| / (P_\text{Fri} \cdot \hat{\sigma}_\text{sym}(t))$ is fit on the pre-2023 calibration set (4,186 weekend rows). Twelve trained scalars; the served half-width at $(\text{symbol}, t, r, \tau)$ is $q^{LWC}_r(\tau) \cdot \hat{\sigma}_\text{sym}(t) \cdot P_\text{Fri} \cdot c(\tau)$, with:

- $c(\tau) \in \{0.68 \to 1.000, 0.85 \to 1.000, 0.95 \to 1.079, 0.99 \to 1.003\}$ — OOS-fit multiplicative bump (M6 fits two of four anchors at 1.000; standardisation already closes most of the train-OOS gap).
- $\delta(\tau) = \{0.68 \to 0.00, 0.85 \to 0.00, 0.95 \to 0.00, 0.99 \to 0.00\}$ — walk-forward δ-shift collapses to zero at every anchor under LWC, because per-symbol standardisation tightens cross-split calibration variance enough that the M5-style overshoot margin is no longer load-bearing.

Twenty deployment scalars total (12 regime quantiles + 4 c-bumps + 4 δ-shifts), audit-trailed in the artefact sidecar. Serving-time computation is a five-line lookup. Linear interpolation off-anchor; no surface inversion, no per-symbol fallback, no scalar buffer override.

The architecture is the product of (a) a multi-step ablation against the v1 hybrid forecaster Oracle and the constant-buffer width-at-coverage stress test (preserved as historical evidence in `reports/paper1_coverage_inversion/` §7.1–§7.6); (b) the M5 Mondrian conformal-by-regime ablation (§7.7) that established the simpler M5 baseline; (c) the M6 LWC promotion (`reports/m6_validation.md`) that re-ran the full robustness battery and closed the per-symbol Kupiec bimodality reported in §6.4.1; and (d) the σ̂ EWMA HL=8 promotion (`reports/m6_sigma_ewma.md`) that picked up an additional 3.83% pooled-width tightening at τ=0.95 while clearing the 2021/2022 split-date Christoffersen rejections that the K=26 trailing window left open. The full decision trail lives in [`reports/methodology_history.md`](reports/methodology_history.md).

## Evidence snapshot

Held-out 2023+ slice (1,730 rows × 173 weekends), M6 LWC + σ̂ EWMA HL=8 Oracle served end-to-end (5,916 evaluable rows after the 80-row σ̂ warm-up; train n=4,186, OOS n=1,730):

| τ | n | Realised | Half-width (bps) | Kupiec $p_{uc}$ | Christoffersen $p_{ind}$ |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 1,730 | 0.693 | 130.8 | 0.264 | 0.244 |
| 0.85 | 1,730 | 0.855 | 213.6 | **0.565** | **0.403** |
| **0.95** | **1,730** | **0.950** | **370.6** | **0.956** | **0.603** |
| **0.99** | **1,730** | **0.990** | **635.0** | **0.942** | **1.000** |

**Per-symbol Kupiec at τ = 0.95 — the headline M6 win.** Under the prior M5 deployment, only 2/10 symbols passed per-symbol Kupiec at α=0.05 (the failure mode was bimodal — SPY/QQQ/GLD/TLT/AAPL over-covered, MSTR/HOOD/TSLA under-covered). Under M6, **10/10 symbols pass**, with every per-symbol violation rate landing in [0.029, 0.069] of the nominal 0.05. Per-symbol Berkowitz LR range collapses from 0.9–224 (250×) to 3.3–18 (5.5×). Held-out-symbol (LOSO) realised-coverage std collapses from 0.0759 to 0.0134 (5.7× tighter); every LOSO held-out symbol passes Kupiec under M6.

Per-asset-class breakdown at **τ = 0.95** on the OOS slice:

| Asset class | n | Realised | Half-width (bps) | Kupiec p |
|---|---:|---:|---:|---:|
| Equities (8 symbols) | 1,384 | 0.951 | 435.6 | 0.882 |
| Gold (GLD) | 173 | 0.942 | 184.4 | 0.646 |
| Treasuries (TLT) | 173 | 0.954 | 184.3 | 0.819 |

The width redistribution is the point: M5 served a flat ~355 bps half-width to every asset class (per-regime quantile is symbol-agnostic), which over-covered gold and treasuries severely (Kupiec p ≤ 0.001) and under-covered the high-σ equity tail. M6's per-symbol scale standardisation widens equities by +23%, tightens gold and treasuries by −48%, and clears Kupiec everywhere.

Interpretation:

- **τ = 0.95** is the headline oracle-validation target.
- **τ = 0.85** is the current deployment default for policy work.
- **τ = 0.99** is in scope under both M5 and M6: realised $0.990$ with Kupiec passing.
- The pooled-width trade-off vs M5 at τ=0.95 is +4.5% (370.6 vs 354.5 bps) under M6 EWMA HL=8 — bought entirely by per-symbol calibration uniformity. Block-bootstrap 95-CI on Δrealised straddles zero at every anchor.
- The σ̂ EWMA HL=8 promotion ([`reports/m6_sigma_ewma.md`](reports/m6_sigma_ewma.md)) further tightens pooled half-width by 3.83% at τ=0.95 vs the K=26 LWC baseline and is the only σ̂ variant that clears split-date Christoffersen at every (split × τ) cell at α=0.05.

In addition to the historical OOS slice, M6 evidence now includes a 4-DGP simulation study ([`reports/m6_simulation_study.md`](reports/m6_simulation_study.md)) showing per-symbol Kupiec pass-rate ≥ 0.99 under stationary / drift / structural-break DGPs (M5 sits at ~0.31), a sample-size sweep that pins the newly-listed-symbol admission threshold at N ≥ 200 weekends, and a forward-tape harness on launchd that re-validates the frozen artefact on each new closed weekend ([`reports/m6_forward_tape_*weekends.md`](reports/)).

Full breakdown: [`reports/m6_validation.md`](reports/m6_validation.md). σ̂ promotion evidence: [`reports/m6_sigma_ewma.md`](reports/m6_sigma_ewma.md). Reproducible end-to-end via `uv run python scripts/build_lwc_artefact.py` and `uv run python scripts/smoke_oracle.py --forecaster lwc`.

## Quick start

```bash
uv sync
cp .env.example .env                                  # optional — only needed for live Helius workloads
uv run python scripts/build_lwc_artefact.py          # builds the M6 LWC deployment artefact from 12 yrs of data
uv run python scripts/smoke_oracle.py --forecaster lwc  # demo the M6 Oracle serving API (`--forecaster m5` for the M5 reference baseline)
```

All upstream data now comes from Scryer parquet under `SCRYER_DATASET_ROOT`. Start with [`docs/scryer_consumer_guide.md`](docs/scryer_consumer_guide.md) for the read pattern and [`docs/data-sources.md`](docs/data-sources.md) for the provider catalog.

## Repo map

```
src/soothsayer/
  backtest/                 calibration backtest — produces the empirical surface
    panel.py                weekend panel assembly (10 tickers × 12 years)
    forecasters.py          F0 through F1_emp_regime + F2_har_rv (legacy ladder; M5/M6 use only point_futures_adjusted)
    metrics.py              coverage, sharpness, calibration-curve helpers
    regimes.py              pre-publish regime tagging (high_vol, long_weekend, normal)
    calibration.py          M5 + M6 LWC primitives (σ̂ K=26 + EWMA variants, regime-quantile fit, dispatcher)
  oracle.py                 serving-time API: `Oracle.fair_value` (M5) + `Oracle.fair_value_lwc` (M6)
  chainlink/                v10/v11 decoder + Verifier parser (decoders only;
                            historical scraper.py removed in the April 2026 cutover)
  sources/scryer.py         canonical scryer-parquet loaders (yahoo bars + CBOE indices + CME-resampled futures)
  universe.py, config.py    xStock universe + mint registry, env/paths

scripts/
  build_mondrian_artefact.py   builds the M5 deployment artefact (reference baseline)
  build_lwc_artefact.py        builds the M6 LWC deployment artefact (canonical)
  freeze_lwc_artefact.py       SHA-256-stamped frozen freeze for forward-tape evaluation
  collect_forward_tape.py      pulls forward weekends past the freeze cutoff
  run_forward_tape_evaluation.py
                               re-runs the M6 evaluator on accumulated forward weekends
  run_forward_tape_harness.sh  launchd-driven wrapper (SLA pre-check + collector + evaluator)
  run_simulation_study.py      4-DGP simulation study (Phase 3 evidence)
  run_simulation_size_sweep.py sample-size sweep for newly-listed-symbol admission (Phase 6)
  run_sigma_ewma_variants.py   σ̂ variant comparison + Phase 5 promotion artefact
  aggregate_m5_m6_bootstrap.py paired weekend-block bootstrap on (Δrealised, Δhw)
  smoke_oracle.py              end-to-end Oracle demo (`--forecaster {m5, lwc}`)
  (analysis runners only — no upstream fetchers; see CLAUDE.md hard rule #1
   and docs/scryer_consumer_guide.md for the read pattern.)

launchd/
  com.adamnoonan.soothsayer.forward-tape.plist
                               weekly Tuesday harness fire (forward-tape re-validation)

docs/
  product-spec.md           customer-selects-coverage product spec
  ROADMAP.md                phase sequencer (product / research / methodology tracks)
  methodology_scope.md      four-question filter for which RWA classes apply
  scryer_consumer_guide.md  canonical data-read pattern (scryer parquet)

reports/
  methodology_history.md    append-only source-of-truth log of methodology decisions
  m6_validation.md          full M6 LWC robustness battery (per-symbol Kupiec, LOSO, GARCH, etc.)
  m6_sigma_ewma.md          Phase 5 σ̂ EWMA HL=8 promotion evidence pack
  m6_simulation_study.md    Phase 3 simulation study + Phase 6 sample-size sweep
  m6_forward_tape_*.md      forward-tape evaluator outputs (auto-rolling N-weekends report)
  v1b_calibration.md, v1b_ablation.md, v1b_buffer_tune.md, v1b_decision.md
                            historical v1b receipts (M5 baseline)
  paper1_coverage_inversion/   Paper 1 drafts (revising against M6)
  paper3_liquidation_policy/   Paper 3 plan + working bibliography (band → action)
  figures/, tables/         persisted charts and tables

notebooks/                  V1-V4 historical notebooks (superseded by v1b — see reports/)
data/
  raw/                      retained for in-flight Phase 1 papers; new code
                            reads from `SCRYER_DATASET_ROOT` instead
                            (canonical: `/Users/adamnoonan/Library/Application
                            Support/scryer/dataset/`).
  processed/                M5 + M6 deployment artefacts and frozen-for-forward-tape freezes:
                              mondrian_artefact_v2.{parquet,json}              — M5 reference baseline
                              lwc_artefact_v1.{parquet,json}                   — M6 canonical (live)
                              lwc_artefact_v1_frozen_YYYYMMDD.{parquet,json}   — SHA-256-stamped freeze for forward-tape
                              lwc_artefact_v1_archive_baseline_k26_*.{...}     — archival K=26 σ̂ variant
                              forward_tape_v1.parquet                          — accumulated forward weekends
                              lwc_variant_bundle_v1_frozen_*.json              — Phase 5.6 variant-bundle freeze

`SCRYER_DATASET_ROOT`       `/Users/adamnoonan/Library/Application Support/scryer/dataset/`
                            — the canonical scryer dataset root, written
                            by scryer's launchd-managed daemons. The only
                            sanctioned data path; all upstream fetching,
                            retry, dedup, and parquet schemas live in
                            scryer. Loaders in
                            `src/soothsayer/sources/scryer.py`. See
                            CLAUDE.md and docs/scryer_consumer_guide.md.

crates/                     Rust — production parity port of oracle.py.
                            M5 path: 75/75 byte-for-byte tests vs Python
                            reference; on-chain publish path lives here too.
                            M6 LWC parity port (`forecaster_code = 3`) is
                            Phase 7 of the M6 promotion — gated; not yet
                            started. M5 wire format remains the production
                            contract until Phase 7 closes.
                            Note: soothsayer-ingest was removed in the
                            April 2026 cutover; on-chain ingest now lives
                            in scryer-fetch-solana.
```

## Current focus

- **Paper 1:** revise against M6 (per-symbol Kupiec 10/10 + LOSO 5.7× tighter + 4-DGP simulation study) and post.
- **Paper 3:** turn the calibrated band into a defensible liquidation-policy layer.
- **Devnet:** ship the on-chain router / publish path that serves the same receipt contract in production.
- **M6 Phase 7 (gated):** Rust parity port for the LWC forecaster (`forecaster_code = 3`) — starts after the §5/§6 results are forwarded.

`docs/ROADMAP.md` is the detailed sequencer. `reports/methodology_history.md` is the methodology source of truth.

## Contributing

Methodology critiques, new RWA-class factor proposals, and integration-partner conversations are especially welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache-2.0](LICENSE).
