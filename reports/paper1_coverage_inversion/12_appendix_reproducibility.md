# §A — Reproducibility appendix

This appendix consolidates everything needed to reproduce the §6 empirical results, the §7 ablation, and the §6.3 / §6.4 / §6.6 robustness diagnostics from the publicly-available source data plus the Soothsayer repo. The deployment is a five-line lookup against sixteen pre-fit scalars; reproducibility is determined by the panel construction, the schedule fits, and the serving formula — all of which are deterministic given the panel.

## A.1 Algorithm boxes

We give pseudocode for three procedures: the M6 fit (deployment-artefact build), the M6 serve (runtime band lookup), and the strictly-pre-Friday per-symbol σ̂ EWMA construction. Implementations: Python at `src/soothsayer/{backtest/calibration.py,oracle.py}`, Rust port at `crates/soothsayer-oracle/src/{config,oracle,types}.rs` (currently mirrors the M5 reference path; M6 wire-format slot reserved as `forecaster_code = 3`).

**Algorithm 1 — M6 fit** (one-shot, produces the 16 deployment scalars; `scripts/build_lwc_artefact.py`).

```
Input:  panel D = {(s, t, p_Fri, mon_open, r_F, r) : i = 1, ..., N}
        split date d_split = 2023-01-01
        anchor τ-grid T = {0.68, 0.85, 0.95, 0.99}
        c-grid C = {1.000, 1.001, ..., 5.000}
        EWMA half-life HL = 8 weekends
        warm-up minimum past_obs_min = 8

Output: sigma_hat_table  σ̂_s(t)         per-(symbol, fri_ts) parquet column
        quantile_table   q_r(τ)         dim 3 × 4 = 12 scalars
        c_bump_schedule  c(τ)           dim 4 scalars
        delta_shift_schedule  δ(τ)      dim 4 scalars (identically zero under M6)

1.  for each row i ∈ D:
        p̂_i ← p_Fri,i · (1 + r_F,i)             # factor-adjusted point
        rrel_i ← (mon_open_i − p̂_i) / p_Fri,i   # signed relative residual
2.  for each (symbol s, weekend t) ∈ D:
        prior ← {rrel_{i'} : symbol(i') = s, t' < t}    # strictly pre-Friday
        if |prior| < past_obs_min:
            mark row as warmup_drop and skip
        else:
            σ̂_s(t) ← EWMA(prior, half_life = HL)        # weekend half-life decay
3.  D_train ← {i ∈ D : t_i < d_split, not warmup_drop}
    D_oos   ← {i ∈ D : t_i ≥ d_split, not warmup_drop}
4.  for each row i in D_train ∪ D_oos:
        score_i ← |mon_open_i − p̂_i| / (p_Fri,i · σ̂_{s_i}(t_i))   # standardised
5.  for each (regime r, target τ) ∈ {normal, long_weekend, high_vol} × T:
        S_r ← {score_i : i ∈ D_train, r_i = r}
        k ← ⌈τ · (|S_r| + 1)⌉                   # finite-sample CP rank
        q_r(τ) ← sort(S_r)[k]                    # the trained standardised quantile
6.  for each τ ∈ T:
        c(τ) ← argmin_{c ∈ C} {c : (1/|D_oos|) · Σ_{i ∈ D_oos} 1{score_i ≤ q_{r_i}(τ) · c} ≥ τ}
7.  δ(τ) ← walk-forward sweep selects 0 at every anchor under M6 (per-symbol σ̂ tightens
            cross-split realised-coverage variance enough that no shift is required)
8.  return (σ̂_s(t), q_r(τ), c(τ), δ(τ))
```

**Algorithm 2 — M6 serve** (runtime band; `Oracle.fair_value_lwc` in `src/soothsayer/oracle.py`).

```
Input:  symbol s, as-of date t, target coverage τ ∈ [0.68, 0.99]
        lookup row (p_Fri, regime r, σ̂_s(t)) from per-Friday parquet at (s, t)
        deployment scalars (q_r(τ), c(τ), δ(τ) ≡ 0) from Algorithm 1

Output: PricePoint{ τ, δ(τ), p̂, lower, upper, r, c, q_eff, q_r, σ̂ }

1.  c_eff ← interpolate c on the τ-grid at τ
2.  q_eff ← c_eff · q_r(τ) · σ̂_s(t)         # standardised quantile rescaled by per-symbol σ̂
3.  p̂ ← p_Fri · (1 + r_F)                    # factor-adjusted point
4.  lower ← p̂ · (1 − q_eff);   upper ← p̂ · (1 + q_eff)
5.  return PricePoint(τ, δ(τ) = 0, p̂, lower, upper, r,
                     diagnostics{c_eff, q_eff, q_r(τ), σ̂_s(t)})
```

**Algorithm 3 — Per-symbol σ̂ EWMA construction** (`scripts/build_lwc_artefact.py` step 2; soft constants `SIGMA_HAT_HL_WEEKENDS = 8`, `SIGMA_HAT_MIN = 8`).

```
Input:  panel D, EWMA half-life HL = 8 weekends, past_obs_min = 8

Output: per-(symbol, fri_ts) σ̂_s(t) column on the artefact parquet

1.  λ ← 0.5 ** (1.0 / HL)        # ≈ 0.917 per past Friday
2.  for each symbol s in D:
        rows_s ← rows of D with symbol = s, sorted by fri_ts
        for each row i in rows_s:
            prior ← {rrel_{j} : j ∈ rows_s, fri_ts(j) < fri_ts(i)}     # strictly pre-Friday
            if |prior| < past_obs_min:
                σ̂_s(fri_ts(i)) ← undefined  (row marked warmup_drop)
            else:
                weights ← [λ ** (|prior| − k − 1) for k in 0..|prior|]
                σ̂_s(fri_ts(i)) ← weighted_std(prior, weights)
3.  return σ̂ column
```

The σ̂ rule itself was selected from a five-variant ladder under §7.3's pre-registered three-gate criterion; alternative variants remain buildable for archival reproduction via `scripts/build_lwc_artefact.py --variant {baseline_k26, ewma_hl6, ewma_hl12, blend_k26_ewma_hl8}`.

## A.2 Hyperparameter specification

The M6 deployment artefact is fully specified by the 16 scalars below plus four "soft" pipeline constants and the σ̂ rule constants. All values are in `data/processed/lwc_artefact_v1.json` (the audit-trail sidecar) and hard-coded in `src/soothsayer/oracle.py`.

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

Three of four near-identity; only $c(0.95) = 1.079$ carries meaningful OOS information. §9.3 carries the full provenance disclosure for that one scalar.

**Walk-forward $\delta(\tau)$ shifts** (4 scalars; identically zero under M6 — per-symbol σ̂ standardisation tightens cross-split realised-coverage variance enough that no shift is required):

| $\tau$ | 0.68 | 0.85 | 0.95 | 0.99 |
|---|---:|---:|---:|---:|
| $\delta(\tau)$ | 0.000 | 0.000 | 0.000 | 0.000 |

The $\delta$ schedule is retained as a 4-zero vector in the artefact JSON for shape-compatibility with the receipt schema.

**Soft constants** (pipeline shape; not OOS-tuned):

| Constant | Value | Source |
|---|---|---|
| Train/OOS split anchor | 2023-01-01 | §6.1, sensitivity in §6.3.3 |
| Conformity score | $\lvert y - \hat p \rvert / (p_{\mathrm{Fri}} \cdot \hat\sigma_s)$ | §4.3 (standardised) |
| Point estimator | $p_{\mathrm{Fri}} \cdot (1 + r_t^F)$ | §4.1 / §5.4 (factor switchboard) |
| Factor switchboard | per-symbol $\rho(s, t)$ | §5.4, MSTR pivot 2020-08-01 |
| Regime classifier | 3-bin $\rho \in \{\text{normal}, \text{lw}, \text{hv}\}$ | §5.5 |
| `c-grid` resolution | $\Delta c = 0.001$ | Algorithm 1 step 6 |
| Off-grid $\tau$ interpolation | linear on the four anchors | §4.6 |
| σ̂ EWMA half-life | 8 weekends | §4.2; `SIGMA_HAT_HL_WEEKENDS` |
| σ̂ warm-up minimum past obs | 8 | §4.2; `SIGMA_HAT_MIN` |

## A.3 Data and code availability

**Data.** All upstream data is publicly available (Yahoo Finance daily bars, CME 1m futures, VIX/GVZ/MOVE, BTC-USD, Yahoo earnings calendar, Kraken Futures perp tape, Pyth Hermes archive, Chainlink Data Streams archive). Soothsayer consumes pre-fetched parquet from the sibling `scryer` repo at `SCRYER_DATASET_ROOT`. The decade-scale weekend panel `data/processed/v1b_panel.parquet` (5,996 rows × 35 columns, 2014-01-17 → 2026-04-24) is built by `scripts/run_calibration.py` calling `soothsayer.backtest.panel.build()`. All `_fetched_at` cutoffs are preserved in the parquet metadata.

**Repository.** Code at `https://github.com/ACNoonan/soothsayer`. Tag the experimental snapshot at submission time; this paper's results were produced from the `main` branch as of 2026-05-05. License: see repository LICENSE file.

**Layout.**

| Layer | Path | Purpose |
|---|---|---|
| Panel build | `src/soothsayer/backtest/panel.py` | weekend-pair assembly, regime tag, factor join |
| Calibration helpers | `src/soothsayer/backtest/calibration.py` | `compute_score`, `train_quantile_table`, `fit_c_bump_schedule`, `serve_bands`, `fit_split_conformal_forecaster` |
| Metrics | `src/soothsayer/backtest/metrics.py` | Kupiec, Christoffersen, Berkowitz, DQ, CRPS, PIT |
| Python serve | `src/soothsayer/oracle.py` | `Oracle.fair_value_lwc` (M6 path); `Oracle.fair_value` (M5 reference) |
| Rust serve (parity) | `crates/soothsayer-oracle/` | byte-for-byte both forecasters (`Forecaster::Mondrian`, `Forecaster::Lwc`); 180/180 parity vs Python |
| On-chain publisher | `programs/soothsayer-oracle-program/` | Anchor program, `PriceUpdate` Borsh wire |
| M6 artefact build | `scripts/build_lwc_artefact.py` | Algorithm 1 |
| M6 freeze | `scripts/freeze_lwc_artefact.py` | content-addressed freeze for forward-tape eval |
| M5 artefact build (reference) | `scripts/build_mondrian_artefact.py` | §7.2 ablation rung |
| Cross-verification | `scripts/verify_rust_oracle.py` | 180-case Python ↔ Rust parity probe (90 M5 + 90 M6 LWC) |
| Robustness battery | `scripts/run_v1b_*.py`, `scripts/run_*.py` | per-symbol diagnostics, vol-tertile, GARCH-N + GARCH-$t$, split sensitivity, LOSO, per-class, path-fitted |
| Phase 7 / 8 runners | `scripts/run_portfolio_clustering.py`, `scripts/run_subperiod_robustness.py`, `scripts/run_v1b_garch_baseline.py --dist t`, `scripts/run_per_symbol_kupiec_all_methods.py`, `scripts/run_kw_threshold_stability.py` | joint-tail clustering, sub-period stability, GARCH-$t$ baseline, 4-method per-symbol grid, $k_w$ threshold stability |
| Figures | `scripts/build_paper1_figures.py` | produces all 6 paper figures |

## A.4 Compute environment

| Component | Version | Notes |
|---|---|---|
| Python | 3.12.13 | enforced via `pyproject.toml` `requires-python = ">=3.12,<3.13"` |
| Environment manager | `uv` | lockfile `uv.lock` checked in |
| Key deps (Python) | numpy ≥ 1.26, pandas ≥ 2.2, scipy ≥ 1.13, polars ≥ 0.20, pyarrow ≥ 16.0, statsmodels ≥ 0.14, arch (for §6.4.3 GARCH baselines) | full list in `pyproject.toml` |
| Rust | stable (1.81+) | matches Solana toolchain |
| Anchor | 0.30.x | for the on-chain publisher |
| OS | macOS Darwin 25.4 (development); deployment is platform-agnostic | |

## A.5 Reproducing the paper's numerical content

The end-to-end pipeline from raw panel to all paper artefacts:

```
# 1. Build the weekend panel from scryer parquet (one-time, ~3 min).
uv run python scripts/run_calibration.py

# 2. Fit M6 and write the deployment artefact (Algorithm 1).
uv run python scripts/build_lwc_artefact.py
uv run python scripts/freeze_lwc_artefact.py        # content-addressed freeze for forward-tape

# 3. Verify Python ↔ Rust serving parity on the M5 reference path (90/90 cases).
uv run python scripts/verify_rust_oracle.py

# 4. §6.6 path-coverage diagnostic (CME + perp + on-chain).
uv run python scripts/run_path_coverage.py

# 5. §6 / §7 robustness battery.
uv run python scripts/run_v1b_per_symbol_diagnostics.py
uv run python scripts/run_v1b_vol_tertile.py
uv run python scripts/run_v1b_garch_baseline.py                 # GARCH-Gaussian baseline
uv run python scripts/run_v1b_garch_baseline.py --dist t        # GARCH-t baseline (§6.4.3)
uv run python scripts/run_v1b_split_sensitivity.py
uv run python scripts/run_v1b_loso.py
uv run python scripts/run_v1b_per_class.py
uv run python scripts/run_v1b_path_fitted_conformal.py

# 6. Phase 7 / 8 paper-strengthening runners.
uv run python scripts/run_portfolio_clustering.py               # §6.3.4 joint-tail empirical distribution
uv run python scripts/run_subperiod_robustness.py               # §6.3.3 calendar sub-period stability
uv run python scripts/run_per_symbol_kupiec_all_methods.py      # §6.4.2 4-method per-symbol grid
uv run python scripts/run_kw_threshold_stability.py             # §6.3.4 reserve-guidance threshold stability

# 7. Build all six figures.
uv run python scripts/build_paper1_figures.py

# 8. Compile this paper.
cd reports/paper1_coverage_inversion/build && uv run python build.py --pdf
```

## A.6 Per-figure data provenance

| Figure | Script | Source CSVs / parquet |
|---|---|---|
| Fig. 1 (pipeline) | `build_paper1_figures.py::fig1_pipeline` | none — diagrammatic |
| Fig. 2 (calibration) | `build_paper1_figures.py::fig2_calibration` | `data/processed/{v1b_panel.parquet, lwc_artefact_v1.parquet}` |
| Fig. 3 (stability) | `build_paper1_figures.py::fig3_stability` | `reports/tables/{m6_lwc_walkforward.csv, m6_lwc_robustness_split_sensitivity.csv}` |
| Fig. 4 (per-symbol) | `build_paper1_figures.py::fig4_per_symbol` | `reports/tables/m6_per_symbol_kupiec_4methods.csv` |
| Fig. 5 (Pareto) | `build_paper1_figures.py::fig5_pareto` | `reports/tables/{incumbent_oracle_unified_summary.csv, m6_lwc_robustness_garch_t_baseline.csv}` |
| Fig. 6 (path) | `build_paper1_figures.py::fig6_path_coverage` | `reports/tables/{path_coverage_perp.csv, path_coverage_perp_by_regime.csv}` |
| Simulation appendix figure | `scripts/run_simulation_study.py` | `reports/tables/sim_per_symbol_kupiec.csv` |

## A.7 Determinism and randomness

The M6 fit and serve paths are deterministic given the panel: no random initialisation, no Monte Carlo, no bootstrap inside the fit. The 4-split powered walk-forward (§6.3.3, §7.2.3) uses fixed split fractions {0.4, 0.5, 0.6, 0.7} (the 0.2 / 0.3 fractions are excluded as under-powered for the 4-scalar $c(\tau)$ fit; see §4.5); the four split-date sensitivity anchors (§6.3.3) are fixed at {2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01}; LOSO (§6.3.3) iterates the ten symbols in lexicographic order. The block-bootstrap CIs reported in §6.3.4, §7.1.2, §7.3.5 use NumPy's default RNG with seed 0 over 1,000 weekend-block resamples. The simulation study (§6.8) uses NumPy's default RNG with seed 0 over 100 replications per DGP.

The GARCH(1,1) baselines (§6.4.3) are fit per-symbol via `arch_model(..., dist={"normal", "t"}).fit(disp="off")`; the optimisation is deterministic up to BFGS tolerance (default `tol=1e-8`). Under GARCH-$t$, NVDA hits the variance-undefined boundary at $\hat\nu = 2.50$ and falls back to Gaussian; the fallback is recorded in the `dist_used` column of the output CSV and is deterministic across reruns.

## A.8 Independent verification (Python ↔ Rust ↔ on-chain)

The deployed serving stack has three independent implementations of both forecasters that must agree byte-for-byte:

1. **Python reference.** `src/soothsayer/oracle.py::Oracle.fair_value_lwc` (M6 deployed path); `Oracle.fair_value` (M5 reference path). Reads `data/processed/lwc_artefact_v1.parquet` (M6) or `data/processed/mondrian_artefact_v2.parquet` (M5) for the per-Friday `(symbol, fri_close, point, regime_pub, sigma_hat_sym_pre_fri)` tuple; the M6 16 scalars (M5 20 scalars) are hard-coded module constants.
2. **Rust serving crate.** `crates/soothsayer-oracle/src/oracle.rs::Oracle::fair_value` exposes both forecasters via `Oracle::load_with_forecaster(&path, Forecaster::{Mondrian, Lwc})`. The 16 LWC scalars and 20 Mondrian scalars are hard-coded in `config.rs`; the unit test `lwc_constants_match_sidecar` enforces ≤ 2 ULP agreement with `lwc_artefact_v1.json` on every refit.
3. **On-chain publisher.** `programs/soothsayer-oracle-program/`. The Rust crate is consumed by an Anchor program that emits `PriceUpdate` PDAs whose Borsh layout is preserved across the M5 → M6 migration. The wire `forecaster_code` byte distinguishes paths: code 2 = `FORECASTER_MONDRIAN` (M5; live on-chain); code 3 = `FORECASTER_LWC` (M6; live in the Rust publisher as of the §8.5 parity milestone, on-chain enablement gated on the next publisher release). The `soothsayer-consumer` no_std crate decodes the PDA into a typed `Forecaster::{Mondrian, Lwc}` view; consumers branching on `forecaster_code` need only add code-2 and code-3 cases.

`scripts/verify_rust_oracle.py` runs a dual-forecaster probe across 30 (symbol, fri_ts) cases × 3 target-coverage anchors per forecaster (90 cases per side, 180 total) and asserts byte-exact agreement on `(point, lower, upper, sharpness_bps, half_width_bps, claimed_served)` between Python and Rust on every case. **Submission status:** **180/180 pass** (90/90 M5 + 90/90 M6). The Anchor integration test (`programs/soothsayer-oracle-program/tests/`) extends the parity check to path 3 by decoding the on-chain PDA after a publish call.

A reviewer reproducing the paper end-to-end thus has three independent implementations of each forecaster that must agree on every (symbol, fri_ts, target_coverage) read.
