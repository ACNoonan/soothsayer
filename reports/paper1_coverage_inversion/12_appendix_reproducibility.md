# §A — Reproducibility appendix

This appendix consolidates everything needed to reproduce the §6 empirical results, the §7 ablation, and the §6.4 / §6.6 robustness diagnostics from the publicly-available source data plus the Soothsayer repo. The deployment is a five-line lookup against twenty pre-fit scalars; reproducibility is determined by the panel construction, the schedule fits, and the serving formula — all of which are deterministic given the panel.

## A.1 Algorithm boxes

We give pseudocode for three procedures: the v1 fit (deployment-artefact build), the v1 serve (runtime band lookup), and the walk-forward stability protocol. Implementations: Python at `src/soothsayer/{backtest/calibration.py,oracle.py}`, Rust at `crates/soothsayer-oracle/src/{config,oracle,types}.rs`. The Rust path is byte-for-byte verified against Python on a 90-case probe (`scripts/verify_rust_oracle.py`, 90/90 pass).

**Algorithm 1 — v1 fit** (one-shot, produces the 20 deployment scalars; `scripts/build_mondrian_artefact.py`).

```
Input:  panel D = {(s, t, p_Fri, mon_open, r_F, r) : i = 1, ..., N}
        split date d_split = 2023-01-01
        anchor τ-grid T = {0.68, 0.85, 0.95, 0.99}
        c-grid C = {1.000, 1.001, ..., 5.000}
        δ-schedule selection from `run_mondrian_delta_sweep.py` (Algorithm 3)

Output: quantile_table  q_r(τ)         dim 3 × 4 = 12 scalars
        c_bump_schedule  c(τ)          dim 4 scalars
        delta_shift_schedule  δ(τ)     dim 4 scalars

1.  D_train ← {i ∈ D : t_i < d_split};   D_oos ← {i ∈ D : t_i ≥ d_split}
2.  for each row i ∈ D:
        p̂_i ← p_Fri,i · (1 + r_F,i)             # factor-adjusted point
        score_i ← |mon_open_i − p̂_i| / p_Fri,i  # relative absolute residual
3.  for each (regime r, target τ) ∈ {normal, long_weekend, high_vol} × T:
        S_r ← {score_i : i ∈ D_train,  r_i = r}
        k ← ⌈τ · (|S_r| + 1)⌉                   # finite-sample CP rank
        q_r(τ) ← sort(S_r)[k]                    # the trained quantile
4.  for each τ ∈ T:
        c(τ) ← argmin_{c ∈ C} {c : (1/|D_oos|) · Σ_{i ∈ D_oos} 1{score_i ≤ q_{r_i}(τ) · c} ≥ τ}
5.  δ(τ) ← from Algorithm 3 (walk-forward sweep, deployed at {0.05, 0.02, 0.00, 0.00})
6.  return (q_r(τ), c(τ), δ(τ))
```

**Algorithm 2 — v1 serve** (runtime band; `Oracle.fair_value` in `src/soothsayer/oracle.py`).

```
Input:  symbol s, as-of date t, target coverage τ ∈ [0.68, 0.99]
        lookup row (p_Fri, regime r) from per-Friday parquet at (s, t)
        deployment scalars (q_r(τ), c(τ), δ(τ)) from Algorithm 1

Output: PricePoint{ τ, δ(τ), τ', p̂, lower, upper, r, c, q_eff, q_r }

1.  τ' ← min(τ + δ(τ), 0.99)                 # δ-shift, clipped to served range
2.  c_eff ← interpolate c on the τ-grid at τ'
3.  q_eff ← c_eff · q_r(τ')
4.  p̂ ← p_Fri · (1 + r_F)                    # factor-adjusted point
5.  lower ← p̂ · (1 − q_eff);   upper ← p̂ · (1 + q_eff)
6.  return PricePoint(τ, δ(τ), τ', p̂, lower, upper, r,
                     diagnostics{c_eff, q_eff, q_r(τ')})
```

**Algorithm 3 — Walk-forward δ-shift selection** (`scripts/run_mondrian_delta_sweep.py`; produces the 4 δ scalars from a 6-split expanding-window backtest).

```
Input:  panel D, split fractions F = {0.2, 0.3, 0.4, 0.5, 0.6, 0.7}
        anchor τ-grid T, δ-grid Δ = {0.00, 0.01, ..., 0.10}
        per-split deficit threshold ε

Output: δ(τ) for each τ ∈ T

1.  for each (f, τ) ∈ F × T:
        D_tune ← first ⌈f · |D|⌉ rows of D, sorted by t
        D_test ← rows of D with t ∈ [next f-fraction window]
        for each δ ∈ Δ:
            (q, c) ← Algorithm 1 on D_tune, evaluated at τ' = τ + δ
            realised(f, τ, δ) ← coverage of D_test against the served band
2.  for each τ ∈ T:
        δ(τ) ← smallest δ ∈ Δ such that median_f realised(f, τ, δ) ≥ τ AND
                                       max_f deficit(f, τ, δ) ≤ ε
3.  return δ(τ)
```

## A.2 Hyperparameter specification

The deployment artefact is fully specified by the 20 scalars below plus four "soft" pipeline constants. All values are in `data/processed/mondrian_artefact_v2.json` and hard-coded in `src/soothsayer/oracle.py` and `crates/soothsayer-oracle/src/config.rs`.

**Trained per-regime quantiles** $q_r(\tau)$ (12 scalars, fit on the 4{,}266-row pre-2023 train set):

| regime ($n$) | $\tau = 0.68$ | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---:|---:|---:|---:|
| normal       (3{,}934) | 0.006070 | 0.011236 | 0.021530 | 0.049663 |
| long_weekend ( 630)    | 0.006648 | 0.014248 | 0.031032 | 0.071228 |
| high_vol     (1{,}432) | 0.011628 | 0.021460 | 0.042911 | 0.099418 |

**OOS-fit $c(\tau)$ multiplicative bumps** (4 scalars, fit on the 1{,}730-row 2023+ OOS via Algorithm 1 step 4):

| $\tau$ | 0.68  | 0.85  | 0.95  | 0.99  |
|---|---:|---:|---:|---:|
| $c(\tau)$ | 1.498 | 1.455 | 1.300 | 1.076 |

**Walk-forward $\delta(\tau)$ shifts** (4 scalars, fit via Algorithm 3 across 6 expanding-window splits at fractions {0.2, ..., 0.7}):

| $\tau$ | 0.68 | 0.85 | 0.95 | 0.99 |
|---|---:|---:|---:|---:|
| $\delta(\tau)$ | 0.05 | 0.02 | 0.00 | 0.00 |

**Soft constants** (pipeline shape; not OOS-tuned):

| Constant | Value | Source |
|---|---|---|
| Train/OOS split anchor | 2023-01-01 | §6.1, sensitivity in §6.3 |
| Conformity score | $\lvert y - \hat p \rvert \,/\, p_{\mathrm{Fri}}$ | §4.2 |
| Point estimator | $p_{\mathrm{Fri}} \cdot (1 + r_t^F)$ | §5.4 (factor switchboard) |
| Factor switchboard | per-symbol $\rho(s, t)$ | §5.4, MSTR pivot 2020-08-01 |
| Regime classifier | 3-bin $\rho \in \{\text{normal}, \text{lw}, \text{hv}\}$ | §5.5 |
| `c-grid` resolution | $\Delta c = 0.001$ | Algorithm 1 step 4 |
| Off-grid $\tau$ interpolation | linear on the four anchors | §4.5 |

## A.3 Data and code availability

**Data.** All upstream data is publicly available (Yahoo Finance daily bars, CME 1m futures, VIX/GVZ/MOVE, BTC-USD, Yahoo earnings calendar, Kraken Futures perp tape, Pyth Hermes archive, Chainlink Data Streams archive). Soothsayer consumes pre-fetched parquet from the sibling `scryer` repo at `SCRYER_DATASET_ROOT`. The decade-scale weekend panel `data/processed/v1b_panel.parquet` (5{,}996 rows × 35 columns, 2014-01-17 → 2026-04-24) is built by `scripts/run_calibration.py` calling `soothsayer.backtest.panel.build()`. All `_fetched_at` cutoffs are preserved in the parquet metadata.

**Repository.** Code at `https://github.com/ACNoonan/soothsayer`. Tag the experimental snapshot at submission time; this paper's results were produced from the `main` branch as of 2026-05-03. License: see repository LICENSE file.

**Layout.**

| Layer | Path | Purpose |
|---|---|---|
| Panel build | `src/soothsayer/backtest/panel.py` | weekend-pair assembly, regime tag, factor join |
| Calibration helpers | `src/soothsayer/backtest/calibration.py` | `compute_score`, `train_quantile_table`, `fit_c_bump_schedule`, `serve_bands`, `fit_split_conformal` |
| Metrics | `src/soothsayer/backtest/metrics.py` | Kupiec, Christoffersen, Berkowitz, DQ, CRPS, PIT |
| Python serve | `src/soothsayer/oracle.py` | `Oracle.fair_value()` |
| Rust serve (parity) | `crates/soothsayer-oracle/` | byte-for-byte equivalent |
| On-chain publisher | `programs/soothsayer-oracle-program/` | Anchor program, `PriceUpdate` Borsh wire |
| Artefact build | `scripts/build_mondrian_artefact.py` | Algorithm 1 |
| Cross-verification | `scripts/verify_rust_oracle.py` | 90-case Python ↔ Rust parity probe |
| Robustness battery | `scripts/run_v1b_*.py` (7 runners) | per-symbol diagnostics, vol-tertile, GARCH, split sensitivity, LOSO, per-class, path-fitted |
| Figures | `scripts/build_paper1_figures.py` | produces all 6 paper figures |

## A.4 Compute environment

| Component | Version | Notes |
|---|---|---|
| Python | 3.12.13 | enforced via `pyproject.toml` `requires-python = ">=3.12,<3.13"` |
| Environment manager | `uv` | lockfile `uv.lock` checked in |
| Key deps (Python) | numpy ≥ 1.26, pandas ≥ 2.2, scipy ≥ 1.13, polars ≥ 0.20, pyarrow ≥ 16.0, statsmodels ≥ 0.14, arch (for §6.4.2 GARCH baseline only) | full list in `pyproject.toml` |
| Rust | stable (1.81+) | matches Solana toolchain |
| Anchor | 0.30.x | for the on-chain publisher |
| OS | macOS Darwin 25.4 (development); deployment is platform-agnostic | |

## A.5 Reproducing the paper's numerical content

The end-to-end pipeline from raw panel to all paper artefacts:

```
# 1. Build the weekend panel from scryer parquet (one-time, ~3 min).
uv run python scripts/run_calibration.py

# 2. Fit v1 and write the deployment artefact (Algorithm 1).
uv run python scripts/build_mondrian_artefact.py

# 3. Verify Python ↔ Rust serving parity (90/90 cases).
uv run python scripts/verify_rust_oracle.py

# 4. §6.6 path-coverage diagnostic (CME + perp + on-chain).
uv run python scripts/run_path_coverage.py

# 5. §6.3 / §6.4 / §10.4 robustness battery (eight checks; ~10 min total).
uv run python scripts/run_v1b_per_symbol_diagnostics.py
uv run python scripts/run_v1b_vol_tertile.py
uv run python scripts/run_v1b_garch_baseline.py
uv run python scripts/run_v1b_split_sensitivity.py
uv run python scripts/run_v1b_loso.py
uv run python scripts/run_v1b_per_class.py
uv run python scripts/run_v1b_path_fitted_conformal.py

# 6. §10.4 next-generation candidate bake-off.
uv run python scripts/run_v3_bakeoff.py

# 7. Build all six figures.
uv run python scripts/build_paper1_figures.py

# 8. Compile this paper.
cd reports/paper1_coverage_inversion/build && uv run python build.py --pdf
```

## A.6 Per-figure data provenance

| Figure | Script | Source CSVs / parquet |
|---|---|---|
| Fig. 1 (pipeline) | `build_paper1_figures.py::fig1_pipeline` | none — diagrammatic |
| Fig. 2 (calibration) | `build_paper1_figures.py::fig2_calibration` | `data/processed/{v1b_panel.parquet, v1b_bounds.parquet}` |
| Fig. 3 (stability) | `build_paper1_figures.py::fig3_stability` | `reports/tables/{v1b_mondrian_walkforward.csv, v1b_robustness_split_sensitivity.csv}` |
| Fig. 4 (per-symbol) | `build_paper1_figures.py::fig4_per_symbol` | `reports/tables/v1b_robustness_per_symbol.csv` |
| Fig. 5 (Pareto) | `build_paper1_figures.py::fig5_pareto` | `reports/tables/{incumbent_oracle_unified_summary.csv, v1b_robustness_garch_baseline.csv}` |
| Fig. 6 (path) | `build_paper1_figures.py::fig6_path_coverage` | `reports/tables/{path_coverage_perp.csv, path_coverage_perp_by_regime.csv}` |

## A.7 Determinism and randomness

The v1 fit and serve paths are deterministic given the panel: no random initialisation, no Monte Carlo, no bootstrap inside the fit. The 6-split walk-forward (§6.3, §7.2.3) uses fixed split fractions {0.2, 0.3, 0.4, 0.5, 0.6, 0.7}; the four split-date sensitivity anchors (§6.3) are fixed at {2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01}; LOSO (§6.3) iterates the ten symbols in lexicographic order. The block-bootstrap CIs reported in §6.3 use NumPy's default RNG with seed 0 over 1{,}000 weekend-block resamples (`scripts/aggregate_ab_comparison.py`).

The GARCH(1,1) baseline (§6.4.2) is fit per-symbol via `arch_model(..., dist="normal").fit(disp="off")`; the optimisation is deterministic up to BFGS tolerance (default `tol=1e-8`).

## A.8 Independent verification (Python ↔ Rust ↔ on-chain)

The deployed serving stack has three independent implementations of the v1 lookup that must agree byte-for-byte:

1. **Python reference.** `src/soothsayer/oracle.py::Oracle.fair_value`. Reads `data/processed/mondrian_artefact_v2.parquet` for the per-Friday `(symbol, fri_close, point, regime_pub)` tuple; the 20 scalars are hard-coded module constants.
2. **Rust serving crate.** `crates/soothsayer-oracle/src/oracle.rs::Oracle::fair_value`. Same parquet, same 20 hard-coded scalars (in `config.rs`); independent implementation of the interpolation and serving formula.
3. **On-chain publisher.** `programs/soothsayer-oracle-program/`. The Rust crate is consumed by an Anchor program that emits `PriceUpdate` PDAs whose Borsh layout was preserved across the migration from Soothsayer-v0 to v1 (`forecaster_code = 2` signals a Mondrian read); a downstream `soothsayer-consumer` no_std crate decodes the PDA and reconstructs `(point, lower, upper, claimed_coverage_served)` from the wire bytes.

`scripts/verify_rust_oracle.py` runs a 90-case probe across (10 symbols × 9 weekends) and asserts identical `(point, lower, upper)` between paths 1 and 2 to within float precision (max abs diff < 1e-10 on a normalised band). The Anchor integration test (`programs/soothsayer-oracle-program/tests/`) extends the parity check to path 3 by decoding the on-chain PDA after a publish call.

A reviewer reproducing the paper end-to-end thus has three independent implementations of the same lookup that must agree on every (symbol, fri_ts, target_coverage) read — a stronger reproducibility guarantee than a single-language reference would provide.
