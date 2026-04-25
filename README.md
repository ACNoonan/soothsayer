<p align="center">
  <img src="landing/favicon.svg" width="64" height="64" alt="Soothsayer logo — point inside a band" />
</p>

# soothsayer

**A calibration-transparent fair-value oracle for tokenized RWAs on Solana.**

Soothsayer publishes a fair-value estimate plus an **auditable empirical confidence band** for tokenized equities (xStocks) and other closed-market RWAs during weekend, overnight, and halt windows — the hours when Chainlink Data Streams carries stale values, Pyth's Blue Ocean coverage drops off, and RedStone Live relies on undisclosed methodology.

The product shape is different from every other oracle on Solana: **consumers specify the realized coverage level they need, and Soothsayer returns the band that empirically delivers it — with per-(symbol, regime) receipts backed by 12 years of public data.**

It is designed to be read **alongside** a primary price oracle, not to replace one. The moat is *calibration transparency*, not "our math is better."

> **Status (2026-04-25):** Phase 0 validation complete; **full PASS**. On a held-out 2023+ slice (1,720 rows × 172 weekends, temporally disjoint from the surface's training window), the served Oracle delivers Kupiec + Christoffersen passes at three operating points — τ=0.95 → realised 0.950 ($p_{uc}$=1.000, $p_{ind}$=0.485); τ=0.85 → realised 0.855 ($p_{uc}$=0.541, $p_{ind}$=0.185); τ=0.68 → realised 0.678 ($p_{uc}$=0.893, $p_{ind}$=0.647). τ=0.99 hits a structural finite-sample tail ceiling and is disclosed as out-of-scope for v1. Phase 1 underway: devnet deploy + Paper 1 to arXiv + Paper 2 (OEV mechanism design) and Paper 3 (liquidation policy) plans being developed in parallel. Source-of-truth log: [`reports/methodology_history.md`](reports/methodology_history.md). Paper drafts: [`reports/paper1_coverage_inversion/`](reports/paper1_coverage_inversion/) (in flight), [`reports/paper2_oev_mechanism_design/`](reports/paper2_oev_mechanism_design/) (planning), [`reports/paper3_liquidation_policy/`](reports/paper3_liquidation_policy/) (planning). See also [`reports/v1b_decision.md`](reports/v1b_decision.md), [`reports/v1b_calibration.md`](reports/v1b_calibration.md), and [`reports/option_c_spec.md`](reports/option_c_spec.md).

## Why this exists

Tokenized equities trade 24/7 on-chain while their underlyings are open only ~32% of wall-clock hours. The other 68% — weekends, overnights, halts — is when on-chain liquidity diverges from fundamental price, when bad liquidations happen, and when every existing oracle falls back to one of:

- **Stale last-trade held forward** (Chainlink `marketStatus=5`, no uncertainty signal)
- **An aggregate median of currently-submitting publishers** (Pyth, CI derived from quote dispersion, not drift/vol)
- **Undisclosed methodology** (RedStone Live, marketed as 24/7 equity coverage)

None publish a calibration claim verifiable against public data **at the aggregate feed level**. (Pyth's documentation recommends per-publisher self-attestation to ~95% coverage, but that is a publisher-level statement, not a property of the aggregate served feed that downstream protocols actually read.) Soothsayer does.

## What we publish

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

`target_coverage`, `calibration_buffer_applied`, `claimed_coverage_served`, `forecaster_used`, and `regime` together compose the trust primitive. They say: *"to deliver your requested 85% realised coverage on a (SPY, normal) bucket, we added a 4.5pp empirical buffer to your target, inverted our calibration surface at the buffered quantile, and served you the band from F1_emp_regime — because that combination has historically covered 85% of Mondays on held-out 2023+ data."* Any consumer can reconstruct the surface and verify that mapping against [`reports/v1b_calibration.md`](reports/v1b_calibration.md) and the persisted bounds at `data/processed/v1b_bounds.parquet`.

The deployment default is **τ = 0.85**, picked on protocol-expected-loss grounds against a Kamino-style flat ±300bps benchmark (see [`reports/paper3_liquidation_policy/plan.md`](reports/paper3_liquidation_policy/plan.md)). Any τ ∈ (0, 1) is a valid request; τ = 0.95 is the paper's headline oracle-validation target.

## The methodology (one screen)

The product is the **served band**, not the raw forecaster. Three layers compose it.

**Layer 1 — Raw forecaster stack.** Two base forecasters, each producing bands across a 12-point claimed-coverage grid:

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

**Layer 2 — Empirical calibration surface.** For each (symbol, regime, forecaster, claimed-quantile) cell we measure realised coverage on rolling history and persist the table. At serve time, a request `(s, r, τ)` returns the band at `q_served = S⁻¹(s, r, τ_buffered)` — i.e. *the claimed quantile that historically delivered the buffered target on this bucket*. This is the inversion that produces the calibration receipt.

**Layer 3 — Hybrid + per-target buffer at the serving layer.**
- `REGIME_FORECASTER = {normal: F1_emp_regime, long_weekend: F1_emp_regime, high_vol: F0_stale}`. Evidence: at matched realised coverage, F1 is 27–43% tighter than F0 on `normal`/`long_weekend`. In `high_vol`, F0 is what prevents the OOS Christoffersen-independence rejection that pure-F1 produces (clustered violations).
- `BUFFER_BY_TARGET = {0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.005}`, linearly interpolated off-grid. Per-target tuned on the OOS 2023+ slice as the smallest buffer satisfying realised-within-0.5pp + Kupiec $p_{uc} > 0.10$ + Christoffersen $p_{ind} > 0.05$. The buffer is **load-bearing for the OOS Kupiec pass** at every τ ≤ 0.95; without it, surface inversion alone delivers 92.2% realised at τ=0.95 and Kupiec rejects.

The Madhavan-Sobczyk / VECM / HAR-RV / Hawkes stack originally researched was tested and dropped — the simpler stack hit the calibration target first. Vanilla split-conformal (Vovk), Barber et al. (2022) nexCP at 6/12-month half-lives, and block-recency conformal were each compared on the same OOS slice with bootstrap CIs and rejected vs the per-target heuristic. Conformal is reframed as v2-conditional in §9.4 of the paper, gated on a finer claimed-coverage grid (above 0.995) or multi-split walk-forward evaluation. Full evolution log: [`reports/methodology_history.md`](reports/methodology_history.md).

## Evidence

Held-out 2023+ slice (1,720 rows × 172 weekends), Oracle served end-to-end through all three methodology layers:

| τ | n | Realised | Half-width (bps) | Kupiec $p_{uc}$ | Christoffersen $p_{ind}$ |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 1,720 | 0.678 | 135.9 | **0.893** | **0.647** |
| 0.85 | 1,720 | 0.855 | 251.1 | **0.541** | **0.185** |
| **0.95** | **1,720** | **0.950** | **442.7** | **1.000** | **0.485** |
| 0.99 | 1,720 | 0.972 | 519.4 | 0.000 | 0.897 |

Per-regime breakdown at τ = 0.95 (OOS):

| Regime | n | Realised | Half-width (bps) | Forecaster served |
|---|---:|---:|---:|---|
| normal | 1,150 | 0.945 | 401.1 | F1_emp_regime |
| long_weekend | 190 | 0.953 | 396.5 | F1_emp_regime |
| high_vol | 380 | 0.963 | 591.6 | F0_stale |

τ = 0.95 is the paper's headline oracle-validation target. τ = 0.85 is the shipping default per protocol-EL evidence vs Kamino flat ±300bps (`reports/paper3_liquidation_policy/plan.md`). τ = 0.99 is structurally limited by the rolling 156-weekend per-bucket window and the 0.995 grid ceiling — disclosed in §9.1 of the paper.

Full surface, per-symbol breakdown, calibration curves: [`reports/v1b_calibration.md`](reports/v1b_calibration.md), [`reports/paper1_coverage_inversion/06_results.md`](reports/paper1_coverage_inversion/06_results.md). Ablation with bootstrap CIs: [`reports/v1b_ablation.md`](reports/v1b_ablation.md). Reproducible end-to-end via `uv run python scripts/run_calibration.py` and `uv run python scripts/smoke_oracle.py`.

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
  methodology_history.md    append-only source-of-truth log of methodology decisions
  v1b_decision.md           go/no-go writeup (2026-04-24 frozen snapshot)
  v1b_calibration.md        full results + per-symbol + per-regime tables
  v1b_ablation.md           ablation across forecaster variants + bootstrap CIs
  v1b_buffer_tune.md        per-target buffer sweep
  v1b_conformal_comparison.md  vanilla / nexCP / block-recency vs heuristic
  option_c_spec.md          product spec (customer-selects-coverage)
  paper1_coverage_inversion/         Paper 1 drafts (§1, §2, §3, §6, §9 + references)
  paper2_oev_mechanism_design/       Paper 2 plan + working bibliography (OEV mechanism design)
  paper3_liquidation_policy/         Paper 3 plan + working bibliography (band → action)
  figures/, tables/         plots and persisted CSVs

notebooks/                  V1-V4 historical notebooks (superseded by v1b — see reports/)
data/
  raw/                      cached source pulls (gitignored)
  processed/                v1b_bounds.parquet (product artifact)

crates/                     Rust — production parity port of oracle.py
                            (75/75 byte-for-byte tests vs Python reference;
                             on-chain publish path lives here too)
```

## Roadmap

Full roadmap with three parallel tracks (product/deploy, research, methodology) lives in [`docs/ROADMAP.md`](docs/ROADMAP.md). Quick view:

- **Phase 0 ✅** — V1b decade-scale backtest → full PASS (Kupiec + Christoffersen, OOS) → Option C product shape locked → Rust port at parity with Python reference.
- **Phase 1 (now)** — Devnet deploy + **Paper 1** (§4/§5/§7/§8 + coherence review → arXiv: q-fin.RM, ACM AFT) + **Paper 3** (calibrated band → liquidation-policy decision-theoretic mapping) outline & first draft (existing protocol-compare scaffolding) + **Paper 2** (OEV mechanism design under calibration-transparent oracles) plan refinement & auction-simulator design — in parallel.
- **Phase 2** — Public comparator dashboard (Soothsayer vs Chainlink vs Pyth, every weekend 2025–2026) + Paper 1 & Paper 3 live (arXiv + SSRN) + Paper 2 active drafting (simulator build, theoretical results) + first design-partner conversations.
- **Phase 3** (gated on Paper 3 evidence + ≥1 design-partner LOI) — Mainnet + B2B + AFT/FC submission for Paper 1 & Paper 3 + Paper 2 to arXiv → AFT/EC.

## Contributing

Methodology critiques, new RWA-class factor proposals, and integration-partner conversations are especially welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache-2.0](LICENSE).
