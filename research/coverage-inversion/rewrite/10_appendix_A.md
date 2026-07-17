# Appendix A — Reproducibility

<!-- Assembled 2026-07-16 per internal/paper1_process/DISPOSITION.md Appendix A rows. Base: 12_appendix_reproducibility.md
     (excluding old A.9 → Appendix B) + command blocks from 04_methodology.md / 05_data_and_regimes.md /
     08_serving_layer.md consolidated into A.5 + forward-tape ops from 06_results.md §6.6 and
     reports/m6_forward_tape_11weekends.md. A.6 rebuilt for the H1–H5 / S1–S2 figure set. -->

This appendix consolidates everything needed to reproduce the §6 empirical results, the §7 ablation, and the Appendix B / Appendix D robustness diagnostics from the publicly-available source data plus the Soothsayer repo. The deployment is a five-line lookup against sixteen pre-fit scalars; reproducibility is determined by the panel construction, the schedule fits, and the serving formula — all of which are deterministic given the panel.

## A.1 Algorithm boxes

We give pseudocode for three procedures: the M6 fit (deployment-artefact build), the M6 serve (runtime band lookup), and the strictly-pre-Friday per-symbol σ̂ EWMA construction. §4 cites Algorithms 1–2 as the recipe; nothing there is duplicated here beyond the pseudocode itself. Implementations: Python at `src/soothsayer/{backtest/calibration.py,oracle.py}`, Rust port at `crates/soothsayer-oracle/src/{config,oracle,types}.rs` (currently mirrors the M5 reference path; M6 wire-format slot reserved as `forecaster_code = 3`).

**Algorithm 1 — M6 fit** (one-shot, produces the 16 deployment scalars; `scripts/build_lwc_artefact.py`).

```
Input:  panel D = {(s, t, p_Fri, mon_open, r_F, r) : i = 1, ..., N}
        split date d_split = 2023-01-01
        anchor τ-grid T = {0.68, 0.85, 0.95, 0.99}
        c-grid C = {1.000, 1.001, ..., 5.000}
        EWMA half-life HL = 8 weekends
        warm-up minimum past_obs_min = 8

Output: sigma_hat_table  sigma_hat_s(t)         per-(symbol, fri_ts) parquet column
        quantile_table   q_r(τ)         dim 3 × 4 = 12 scalars
        c_bump_schedule  c(τ)           dim 4 scalars
        delta_shift_schedule  δ(τ)      dim 4 scalars (identically zero under M6)

1.  for each row i ∈ D:
        p_hat_i ← p_Fri,i · (1 + r_F,i)             # factor-adjusted point
        rrel_i ← (mon_open_i − p_hat_i) / p_Fri,i   # signed relative residual
2.  for each (symbol s, weekend t) ∈ D:
        prior ← {rrel_{i'} : symbol(i') = s, t' < t}    # strictly pre-Friday
        if |prior| < past_obs_min:
            mark row as warmup_drop and skip
        else:
            sigma_hat_s(t) ← EWMA(prior, half_life = HL)        # weekend half-life decay
3.  D_train ← {i ∈ D : t_i < d_split, not warmup_drop}
    D_oos   ← {i ∈ D : t_i ≥ d_split, not warmup_drop}
4.  for each row i in D_train ∪ D_oos:
        score_i ← |mon_open_i − p_hat_i| / (p_Fri,i · sigma_hat_{s_i}(t_i))  # std.
5.  for each (regime r, target τ) ∈ {normal, long_weekend, high_vol} × T:
        S_r ← {score_i : i ∈ D_train, r_i = r}
        k ← ⌈τ · (|S_r| + 1)⌉                   # finite-sample CP rank
        q_r(τ) ← sort(S_r)[k]              # trained standardised quantile
6.  for each τ ∈ T:
        c(τ) ← smallest c∈C with mean_{D_oos} 1{score_i ≤ q_{r_i}(τ)·c} ≥ τ
7.  δ(τ) ← 0 at every anchor under M6 (walk-forward sweep; per-symbol sigma_hat
            tightens cross-split coverage variance, so no shift is needed)
8.  return (sigma_hat_s(t), q_r(τ), c(τ), δ(τ))
```

**Algorithm 2 — M6 serve** (runtime band; `Oracle.fair_value_lwc` in `src/soothsayer/oracle.py`).

```
Input:  symbol s, as-of date t, target coverage τ ∈ [0.68, 0.99]
        lookup row (p_Fri, regime r, sigma_hat_s(t)) from per-Friday parquet at (s, t)
        deployment scalars (q_r(τ), c(τ), δ(τ) ≡ 0) from Algorithm 1

Output: PricePoint{ τ, δ(τ), p_hat, lower, upper, r, c, q_eff, q_r, sigma_hat }

1.  c_eff ← interpolate c on the τ-grid at τ
2.  q_eff ← c_eff · q_r(τ)              # standardised quantile (sigma_hat below)
3.  p_hat ← p_Fri · (1 + r_F)              # factor-adjusted point (centre)
4.  half ← q_eff · sigma_hat_s(t) · p_Fri      # price-unit half-width
5.  lower ← p_hat − half;   upper ← p_hat + half
6.  return PricePoint(τ, δ(τ) = 0, p_hat, lower, upper, r,
                     diagnostics{c_eff, q_eff, q_r(τ), sigma_hat_s(t)})
```

**Algorithm 3 — Per-symbol σ̂ EWMA construction** (`scripts/build_lwc_artefact.py` step 2; soft constants `SIGMA_HAT_HL_WEEKENDS = 8`, `SIGMA_HAT_MIN = 8`).

```
Input:  panel D, EWMA half-life HL = 8 weekends, past_obs_min = 8

Output: per-(symbol, fri_ts) sigma_hat_s(t) column on the artefact parquet

1.  λ ← 0.5 ** (1.0 / HL)        # ≈ 0.917 per past Friday
2.  for each symbol s in D:
        rows_s ← rows of D with symbol = s, sorted by fri_ts
        for each row i in rows_s:
            prior ← {rrel_j : j∈rows_s, fri_ts(j) < fri_ts(i)}  # pre-Fri
            if |prior| < past_obs_min:
                sigma_hat_s(fri_ts(i)) ← undefined  (row marked warmup_drop)
            else:
                weights ← [λ ** (|prior| − k − 1) for k in 0..|prior|]
                sigma_hat_s(fri_ts(i)) ← weighted_std(prior, weights)
3.  return sigma_hat column
```

The σ̂ rule itself was selected from a five-variant ladder under the pre-registered three-gate criterion of §7 (full procedure and tables in Appendix D); alternative variants remain buildable for archival reproduction via `scripts/build_lwc_artefact.py --variant {baseline_k26, ewma_hl6, ewma_hl12, blend_k26_ewma_hl8}`.

## A.2 Hyperparameter specification

The M6 deployment artefact is fully specified by the 16 scalars below plus four "soft" pipeline constants and the σ̂ rule constants. All values are recorded in `data/processed/lwc_artefact_v1.json` (the audit-trail sidecar) and loaded at module import into `src/soothsayer/oracle.py:LWC_REGIME_QUANTILE_TABLE` (with the schedule constants hard-coded alongside); the Rust unit test `lwc_constants_match_sidecar` enforces ≤ 2 ULP agreement between the hard-coded constants and the sidecar on every refit (A.8).

**Trained per-regime quantiles** $q_r(\tau)$ on standardised residuals (12 scalars, fit on the 4{,}186-row pre-2023 train set after the 80-row σ̂ warm-up drop):

| regime ($n$) | $\tau = 0.68$ | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---:|---:|---:|---:|
| normal       | 0.7767 | 1.2195 | 1.9682 | 3.3280 |
| long_weekend | 0.8638 | 1.3649 | 2.2208 | 4.0152 |
| high_vol     | 1.1086 | 1.9433 | 3.0971 | 6.4563 |

Note these are *standardised* quantiles (dimensionless; multiplied at serve time by $\hat\sigma_s(t)$ to yield a relative-residual quantile in basis points). The high_vol $\tau = 0.99$ value of $6.46$ — a $6.46$-σ shock at the panel-relative scale — is the headline-tail shape M6 is calibrated to absorb.

**OOS-fit $c(\tau)$ multiplicative bumps** (4 scalars, fit on the 1,730-row 2023+ OOS via Algorithm 1 step 6):

| $\tau$ | 0.68  | 0.85  | 0.95  | 0.99  |
|---|---:|---:|---:|---:|
| $c(\tau)$ | 1.000 | 1.000 | 1.079 | 1.003 |

Three of four near-identity; only $c(0.95) = 1.079$ carries meaningful OOS information. §8 carries the provenance disclosure for that one scalar; B.7 carries the detail.

**Walk-forward $\delta(\tau)$ shifts** (4 scalars; identically zero under M6 — per-symbol σ̂ standardisation tightens cross-split realised-coverage variance enough that no shift is required):

| $\tau$ | 0.68 | 0.85 | 0.95 | 0.99 |
|---|---:|---:|---:|---:|
| $\delta(\tau)$ | 0.000 | 0.000 | 0.000 | 0.000 |

The $\delta$ schedule is retained as a 4-zero vector in the artefact JSON for shape-compatibility with the receipt schema.

**Soft constants** (pipeline shape; not OOS-tuned):

| Constant | Value | Source |
|---|---|---|
| Train/OOS split anchor | 2023-01-01 | §5.6; split-date sensitivity in B.6 |
| Conformity score | $\lvert y - \hat p \rvert / (p_{\mathrm{Fri}} \cdot \hat\sigma_s)$ | §4.4 (standardised) |
| Point estimator | $p_{\mathrm{Fri}} \cdot (1 + r_t^F)$ | §4.2 / §5.4 (factor switchboard) |
| Factor switchboard | per-symbol $\rho(s, t)$ | §5.4, MSTR pivot 2020-08-01 |
| Regime classifier | 3-bin $\rho \in \{\text{normal}, \text{lw}, \text{hv}\}$ | §5.5 |
| `c-grid` resolution | $\Delta c = 0.001$ | Algorithm 1 step 6 |
| Off-grid $\tau$ interpolation | linear on the four anchors | §4.6 |
| σ̂ EWMA half-life | 8 weekends | §4.3; `SIGMA_HAT_HL_WEEKENDS` |
| σ̂ warm-up minimum past obs | 8 | §4.3; `SIGMA_HAT_MIN` |

## A.3 Data and code availability

**Data.** All upstream data is publicly available (Yahoo Finance daily bars, CME 1m futures, VIX/GVZ/MOVE, BTC-USD, Yahoo earnings calendar, Kraken Futures perp tape, Pyth Hermes archive, Chainlink Data Streams archive). Soothsayer consumes pre-fetched parquet from the sibling `scryer` repo at `SCRYER_DATASET_ROOT`. The decade-scale weekend panel `data/processed/v1b_panel.parquet` (5,996 rows × 35 columns, 2014-01-17 → 2026-04-24) is built by `scripts/run_calibration.py` calling `soothsayer.backtest.panel.build()`; the overnight panel `data/processed/overnight_panel.parquet` (22,624 rows, 2014-01-16 → 2026-04-23) is built by `scripts/build_overnight_panel.py` calling the same `build()` with `gap_mode="overnight"` plus `yahoo/earnings/v2` session timing and the `yahoo/corp_actions/v1` ex-dividend adjustment (§5.2). All `_fetched_at` cutoffs are preserved in the parquet metadata.

**Panel row schema.** Each row is a single $(s, t)$ prediction window carrying: `fri_close`, `mon_open`, `gap_days`, `fri_vol_20d` (rolling 20-trading-day std of daily log-returns at the closing print), `factor_ret` (closed-window return of the per-symbol conditioning factor), `vol_idx_fri_close`, `earnings_next_week` (Yahoo `earnings_dates` flag; session-timed per gap on the overnight panel), and `is_long_weekend` (`gap_days` $\ge 4$). §5.2 carries the panel counts; §5.5 the regime shares.

**Repository.** Code at `https://github.com/ACNoonan/soothsayer`. Results were produced from the `main` branch as of 2026-05-05; the camera-ready snapshot is tagged to the commit covering the corrected overnight battery (2026-06-25) and the $N = 11$ forward tape (2026-07-14). License: see repository LICENSE file.

**Layout.**

\footnotesize

| Layer | Path | Purpose |
|:-----------|:--------------------|:-----------|
| Panel build | `src/soothsayer/backtest/panel.py` | weekend-pair assembly, regime tag, factor join |
| Calibration helpers | `src/soothsayer/backtest/calibration.py` | `compute_score`, `train_quantile_table`, `fit_c_bump_schedule`, `serve_bands`, `fit_split_conformal_forecaster` |
| Metrics | `src/soothsayer/backtest/metrics.py` | Kupiec, Christoffersen, Berkowitz, DQ, CRPS, PIT |
| Python serve | `src/soothsayer/oracle.py` | `Oracle.fair_value_lwc` (M6 path); `Oracle.fair_value` (M5 reference) |
| Rust serve (parity) | `crates/soothsayer-oracle/` | byte-for-byte both forecasters (`Forecaster::Mondrian`, `Forecaster::Lwc`); 180/180 parity vs Python |
| On-chain publisher | `programs/soothsayer-oracle-program/` | Anchor program, `PriceUpdate` Borsh wire |
| M6 artefact build | `scripts/build_lwc_artefact.py` | Algorithm 1 |
| M6 freeze | `scripts/freeze_lwc_artefact.py` | content-addressed freeze for forward-tape eval |
| M5 artefact build (reference) | `scripts/build_mondrian_artefact.py` | Appendix D ablation rung |
| Cross-verification | `scripts/verify_rust_oracle.py` | 180-case Python ↔ Rust parity probe (90 M5 + 90 M6 LWC) |
| Robustness battery | `scripts/run_v1b_*.py`, `scripts/run_*.py` | per-symbol diagnostics, vol-tertile, GARCH-N + GARCH-$t$, split sensitivity, LOSO, per-class, path-fitted |
| Paper-strengthening runners | `scripts/run_portfolio_clustering.py`, `scripts/run_subperiod_robustness.py`, `scripts/run_v1b_garch_baseline.py --dist t`, `scripts/run_per_symbol_kupiec_all_methods.py`, `scripts/run_kw_threshold_stability.py` | joint-tail clustering (§8 / B.8), sub-period stability (B.6), GARCH-$t$ baseline (B.12), 4-method per-symbol grid (§6.2), $k_w$ threshold stability (B.8) |

\normalsize
| Forward tape | `scripts/collect_forward_tape.py`, `scripts/run_forward_tape_evaluation.py` | weekly held-out evaluation against the frozen artefact (A.9) |
| Figures | `scripts/build_paper1_figures.py` (appendix figures), `scripts/build_fig_h{1,2,3,4,5}.py`, `scripts/build_fig_s{1,2}.py` (main-text figures) | per-figure provenance in A.6 |

## A.4 Compute environment

| Component | Version | Notes |
|---|---|---|
| Python | 3.12.13 | enforced via `pyproject.toml` `requires-python = ">=3.12,<3.13"` |
| Environment manager | `uv` | lockfile `uv.lock` checked in |
| Key deps (Python) | numpy ≥ 1.26, pandas ≥ 2.2, scipy ≥ 1.13, polars ≥ 0.20, pyarrow ≥ 16.0, statsmodels ≥ 0.14, arch (for the B.12 GARCH baselines) | full list in `pyproject.toml` |
| Rust | stable (1.81+) | matches Solana toolchain |
| Anchor | 0.30.x | for the on-chain publisher |
| OS | macOS Darwin 25.4 (development); deployment is platform-agnostic | |

## A.5 Reproducing the paper's numerical content

This is the single consolidated command listing; §4.8, §5.7, and Appendix E refer here rather than repeating commands. The end-to-end pipeline from raw panel to all paper artefacts:

```
# 0. Environment.
uv sync

# 1. Build the weekend panel from scryer parquet (one-time, ~3 min;
#    end-to-end backtest: under 15 min cold, under 1 min warm).
uv run python scripts/run_calibration.py

# 2. Fit M6, write the artefact (Algorithm 1) + sidecar; freeze; smoke-test.
uv run python scripts/build_lwc_artefact.py    # artefact + JSON sidecar
uv run python scripts/freeze_lwc_artefact.py   # content-addressed freeze
uv run python scripts/smoke_oracle.py --forecaster lwc   # cross-regime API demo

# 3. Verify Python <-> Rust parity (A.8); build the Rust serving CLI.
PYTHONUNBUFFERED=1 uv run python scripts/verify_rust_oracle.py
uv run python scripts/build_mondrian_artefact.py    # M5 reference (App D rung)
cargo build --release -p soothsayer-publisher
soothsayer fair-value --symbol SPY --as-of 2026-04-24 --target 0.85
./scripts/deploy_devnet.sh                     # devnet publish (App E)

# 4. Path-coverage diagnostic (B.14) + excursion-inflation λ.
uv run python scripts/run_path_coverage.py
uv run python scripts/proto_excursion_inflation.py

# 4b. Off-hours: overnight panel + calibration battery (§6.4, B.15).
uv run python scripts/build_overnight_panel.py   # overnight panel (§5.2)
uv run python scripts/build_overnight_artefact.py   # overnight artefact + battery

# 5. §6 / §7 / Appendix B / Appendix D robustness battery.
uv run python scripts/run_v1b_per_symbol_diagnostics.py
uv run python scripts/run_v1b_vol_tertile.py
uv run python scripts/run_v1b_garch_baseline.py          # GARCH-Gaussian
uv run python scripts/run_v1b_garch_baseline.py --dist t # GARCH-t (B.12)
uv run python scripts/run_v1b_split_sensitivity.py
uv run python scripts/run_v1b_loso.py
uv run python scripts/run_v1b_per_class.py
uv run python scripts/run_v1b_path_fitted_conformal.py
uv run python scripts/run_v1b_tokenised_tracking_baseline.py  # §6.2, App D

# 6. Joint-tail / stability runners (§8, B.6, B.8).
uv run python scripts/run_portfolio_clustering.py     # joint-tail dist.
uv run python scripts/run_subperiod_robustness.py     # sub-period stability
uv run python scripts/run_per_symbol_kupiec_all_methods.py  # 4-method grid
uv run python scripts/run_kw_threshold_stability.py   # reserve threshold

# 7. Build the paper figures (A.6).
uv run python scripts/build_paper1_figures.py
uv run python scripts/build_fig_h1.py
uv run python scripts/build_fig_h2.py
uv run python scripts/build_fig_h3.py
uv run python scripts/build_fig_h4.py
uv run python scripts/build_fig_h5.py
uv run python scripts/build_fig_s1.py
uv run python scripts/build_fig_s2.py

# 8. Compile this paper.
cd research/coverage-inversion/build && uv run python build.py --pdf
```

`run_calibration.py` materialises `data/processed/v1b_bounds.parquet`, the per-symbol and pooled calibration surfaces, and refreshes the OOS-evaluation tables; the two overnight scripts materialise the overnight panel and its calibration battery. Forward-tape harness commands are in A.9.

## A.6 Per-figure data provenance

Rebuilt for the H1–H5 / S1–S2 figure plan. H1–H3 are new builds; H4, H5, S1, and S2 are redesigns of earlier exhibits (fig11, fig10, fig4, and fig8 respectively); the remaining appendix figures carry their original provenance.

Status (new build / redesign of a prior exhibit / existing) is given in the paragraph above; the table below records each figure's builder and data source. Paths under `data/processed/` and `reports/tables/` are shown without their directory prefix; the `figN_*()` builders are functions in `scripts/build_paper1_figures.py`.

\footnotesize

| Figure (placement) | Script | Source data (parquet / CSV) |
|:-------------------|:------------------|:------------------------|
| H1a week timeline (§1); H1b gap distributions (§1.1) | `build_fig_h1.py` | `v1b_panel`, `overnight_panel` |
| H2 anatomy of a read (§3) | `build_fig_h2.py` | `lwc_artefact_v1` (exemplar; else diagrammatic) |
| H3 promised-vs-delivered coverage (§6.2) | `build_fig_h3.py` | `m6_pooled_oos`, `m6_lwc_robustness_garch_t_baseline` |
| H4 earnings event-time band (§6.5) | `build_fig_h4.py` | `overnight_panel`, `overnight_artefact_v1` |
| H5 joint-tail $k_w$ counts (§8) | `build_fig_h5.py` | `paper1_a3_joint_baseline_kw_distribution` |
| Fig. 1 serving pipeline (§4) | `fig1_pipeline()` | diagrammatic |
| S1 per-symbol promise audit (§6.2) | `build_fig_s1.py` | `m6_lwc_robustness_per_symbol`, `m6_per_symbol_kupiec_4methods` |
| S2 overnight promise audit (§6.4) | `build_fig_s2.py` | overnight panel + artefact (§5.2, B.15) |
| fig6 path coverage (B.14) | `fig6_path_coverage()` | `path_coverage_perp_per_row` + artefact bands |
| fig7b per-symbol ablation (App D) | `fig7b_oos_ablation()` | `paper1_fig7b_per_symbol_ablation` (per split anchor) |
| fig9 BoJ band anatomy (B.9) | `fig9_boj_anatomy()` | `lwc_artefact_v1`, `v1b_panel` |
| simulation figure (App C) | `run_simulation_study.py` | `sim_per_symbol_kupiec` |

\normalsize

Former fig0, fig2, and fig5 are superseded (fig0 upgraded into H1; fig2 + fig5 merged into H3) and are no longer emitted into the build.

## A.7 Determinism and randomness

The M6 fit and serve paths are deterministic given the panel: no random initialisation, no Monte Carlo, no bootstrap inside the fit. The 4-split powered walk-forward (B.6, Appendix D) uses fixed split fractions {0.4, 0.5, 0.6, 0.7} (the 0.2 / 0.3 fractions are excluded as under-powered for the 4-scalar $c(\tau)$ fit; Appendix D); the four split-date sensitivity anchors (B.6) are fixed at {2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01}; LOSO (§6.1) iterates the ten symbols in lexicographic order. The block-bootstrap CIs reported in §8, B.8, and Appendix D use NumPy's default RNG with seed 0 over 1,000 weekend-block resamples. The simulation study (Appendix C) uses NumPy's default RNG with seed 0 over 100 replications per DGP.

The GARCH(1,1) baselines (B.12) are fit per-symbol via `arch_model(..., dist={"normal", "t"}).fit(disp="off")`; the optimisation is deterministic up to BFGS tolerance (default `tol=1e-8`). Under GARCH-$t$, NVDA's $t$-MLE hits the optimizer lower bound $\hat\nu = 2.50$ (adjacent to the $\nu \le 2$ variance-undefined region) and falls back to Gaussian; the fallback is recorded in the `dist_used` column of the output CSV and is deterministic across reruns.

## A.8 Independent verification (Python ↔ Rust ↔ on-chain)

The deployed serving stack has three independent implementations of both forecasters that must agree byte-for-byte:

1. **Python reference.** `src/soothsayer/oracle.py::Oracle.fair_value_lwc` (M6 deployed path); `Oracle.fair_value` (M5 reference path). Reads `data/processed/lwc_artefact_v1.parquet` (M6) or `data/processed/mondrian_artefact_v2.parquet` (M5) for the per-Friday `(symbol, fri_close, point, regime_pub, sigma_hat_sym_pre_fri)` tuple; the M6 16 scalars (M5 20 scalars) are hard-coded module constants.
2. **Rust serving crate.** `crates/soothsayer-oracle/src/oracle.rs::Oracle::fair_value` exposes both forecasters via `Oracle::load_with_forecaster(&path, Forecaster::{Mondrian, Lwc})`. The 16 LWC scalars and 20 Mondrian scalars are hard-coded in `config.rs`; the unit test `lwc_constants_match_sidecar` enforces ≤ 2 ULP agreement with `lwc_artefact_v1.json` on every refit.
3. **On-chain publisher.** `programs/soothsayer-oracle-program/`. The Rust crate is consumed by an Anchor program that emits `PriceUpdate` PDAs whose Borsh layout is preserved across the M5 → M6 migration. The wire `forecaster_code` byte distinguishes paths: code 2 = `FORECASTER_MONDRIAN` (M5; live on-chain); code 3 = `FORECASTER_LWC` (M6; live in the Rust publisher as of the Appendix E parity milestone, on-chain enablement gated on the next publisher release). The `soothsayer-consumer` no_std crate decodes the PDA into a typed `Forecaster::{Mondrian, Lwc}` view; consumers branching on `forecaster_code` need only add code-2 and code-3 cases.

`scripts/verify_rust_oracle.py` runs a dual-forecaster probe across 30 (symbol, fri_ts) cases × 3 target-coverage anchors per forecaster (90 cases per side, 180 total) and asserts byte-exact agreement on `(point, lower, upper, sharpness_bps, half_width_bps, claimed_served)` between Python and Rust on every case. **Submission status:** **180/180 pass** (90/90 M5 + 90/90 M6) for the Python↔Rust parity. The Anchor program (`programs/soothsayer-oracle-program/tests/`) carries a scaffolded integration test that decodes the on-chain PDA after a publish call on the live M5 path; extending it to the M6 path is gated on the on-chain M6 enablement above.

A reviewer reproducing the paper end-to-end thus has three independent implementations of each forecaster that must agree on every (symbol, fri_ts, target_coverage) read.

## A.9 Forward-tape harness operations

The forward-tape harness closes the $c(\tau)$ OOS-tuning loop on truly held-out data (the provenance disclosure is in §8, with detail in B.7): a content-addressed frozen artefact (`data/processed/lwc_artefact_v1_frozen_20260504.json`, SHA-256 `7b86d17a7691…`, freeze date 2026-05-04) is evaluated weekly against forward weekends as they accumulate. The frozen artefact's σ̂ schedule, $q_r$ table, and $c(\tau)$ are read-only; only the per-symbol $\hat\sigma_s(t)$ updates as new past-Fridays arrive.

**Operations.** The harness fires Tuesday mornings via launchd (`launchd/com.adamnoonan.soothsayer.forward-tape.plist`); each run executes a 26h-SLA pre-check on the upstream scryer feeds, runs `scripts/collect_forward_tape.py`, and writes `reports/m6_forward_tape_{N}weekends.md` with a "preliminary" banner when $N < 4$. The harness is silent about deployment; an out-of-band freeze re-roll is required to advance the artefact — after a planned methodology refresh, re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.

```
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

**Status at submission** (`reports/m6_forward_tape_11weekends.md`, generated 2026-07-14): $N = 11$ forward weekends, 2026-05-01 → 2026-07-10, $n = 110$ symbol-rows.

| $\tau$ | $n$ | realised | half-width (bps) | Kupiec $p$ | Christoffersen $p$ |
|---|---:|---:|---:|---:|---:|
| 0.68 | 110 | 0.7455 | 112.3 | 0.1330 | 0.7908 |
| 0.85 | 110 | 0.8455 | 179.2 | 0.8942 | 0.4758 |
| 0.95 | 110 | 0.9636 | 312.2 | 0.4912 | 0.3640 |
| 0.99 | 110 | 1.0000 | 515.6 | 0.1370 | — (no violations) |

Pooled Kupiec passes at all four anchors with no under-coverage; pooled Christoffersen passes at the three anchors with observed violations. Per-symbol Kupiec at $\tau = 0.95$ passes 10/10 on the forward tape, but at $n = 11$ per symbol the test is powerless: two symbols (HOOD and MSTR) each realise a 18.2% violation rate (2 of 11), which Kupiec cannot reject at that $n$ (the M5 in-sample baseline was 2/10). $N = 11$ clears the harness's own preliminary banner ($N \ge 4$) and remains just under the $N \ge 13$ threshold for cumulative pooled Christoffersen power. The submission's held-out backbone is §6.1's leave-one-symbol-out CV plus the nested temporal holdout, per-symbol Kupiec, split-date sensitivity, and four-year calendar sub-period stability (B.6); the forward-tape harness becomes load-bearing as $N$ accumulates.

A sibling script (`scripts/run_forward_tape_variant_comparison.py`) carries an alternative-σ̂ check on the same forward slice — never used to re-select, only to flag if a different σ̂ rule looks dramatically cleaner on held-out data (§7, Appendix D).
