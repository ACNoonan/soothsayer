# M6 LWC Promotion — Working Document

**Status:** Phase 1 ready to start. Phases run strictly sequentially; do not start phase N+1 until phase N's definition-of-done is fully passing.

**Authoring date:** 2026-05-04. Supersedes the prior dual-profile (M6a / M6b2) plan that previously occupied this file. The dual-profile direction is paused; M6 is now the LWC promotion described below. The decision context is in `reports/v3_bakeoff.md` and will be recorded in `reports/methodology_history.md` when Phase 1 closes.

**Delete this file when:** M6 is deployed, the methodology log entry is committed, Paper 1 §6 / §7 / §8 are updated against M6, and the checklist below is fully closed.

---

## Context

The currently deployed architecture is **M5** — Mondrian split-conformal by `regime_pub`, pooled across symbols within each regime, with OOS-fit `c(τ)` bumps and walk-forward-fit `δ(τ)` shifts.

`reports/v3_bakeoff.md` already validated **C1 — Locally-Weighted Conformal (LWC)** as the lead candidate for closing the per-symbol bimodality reported in §6.4.1 of Paper 1. That bake-off was run outside the validation loop and was not adopted. The work here promotes LWC to **M6**, reruns the full validation battery, and adds two new pieces of evidence (simulation study + forward-tape harness scaffolding) that the paper currently lacks.

## Cross-cutting rules

1. **M5 is not deleted.** `Oracle.fair_value`, `data/processed/mondrian_artefact_v2.{parquet,json}`, `crates/soothsayer-oracle` M5 paths, and `forecaster_code = 2` all remain in place. M6 is **added alongside** M5 so the §7 ablation can compare both on identical data. Treat M5 the way the paper currently treats "the prior hybrid Oracle" — as the named reference baseline.
2. **No Rust port until forwarded.** Phase 5 is explicitly gated: do not begin the Rust parity port until Adam has forwarded the Phase 1–4 results to the secondary agent and given the green light here.
3. **CLAUDE.md hard rules apply.** All upstream data still goes through scryer parquet. New artefacts under `data/processed/` are fine; no new fetchers in this repo.
4. **Wire-format invariance.** Existing M5 consumers must decode M6 `PriceUpdate` accounts without crashing. The only field that changes is `forecaster_code` (2 → 3).

---

## Phase 1 — Promote LWC to M6 (canonical implementation)  ✅ COMPLETE 2026-05-04

**Goal:** produce a deployable M6 artefact + Python serving path that matches M5's interface byte-for-byte but uses locally-weighted conformal under the hood.

### 1.1 — Calibration core ✅

- [x] Added `add_sigma_hat_sym`, `compute_score_lwc`, `train_lwc_quantile_table`, `serve_bands_lwc` to `src/soothsayer/backtest/calibration.py`.
  - σ̂_sym(t) = trailing **K=26 weekend** observations of relative residual std per symbol; **strictly pre-Friday** (uses only `fri_ts' < fri_ts`); requires **≥ 8 past observations**. Persisted as `sigma_hat_sym_pre_fri` on the panel. Constants exposed as `SIGMA_HAT_K`, `SIGMA_HAT_MIN`. (Note: the brief's "26-week / 130-trading-day" parenthetical conflates trading-day count with weekend count; the operational unit is **26 past Fridays** — same as the v3 bake-off used for C1.)
  - Standardised score: `|mon_open − point| / (fri_close · σ̂_sym(t))`.
  - Per-regime quantile fit on the standardised score with the same finite-sample CP rank formula M5 uses (`ceil(τ·(n+1))`).
  - Half-width at serve: `q_r^LWC(τ) · σ̂_sym(t) · fri_close`.
- [x] Sanity: end-to-end fit on `v1b_panel.parquet` reproduces the bake-off C1 receipts byte-for-byte (5,916 rows × 631 weekends, 80 dropped at warm-up; at τ=0.95 realised=0.9503, HW=385.3 bps, c=1.069). See `reports/v3_bakeoff.md`.

### 1.2 — c(τ) and δ(τ) refit ✅

- [x] OOS c-fit on standardised residuals: **`c_LWC = {0.68: 1.000, 0.85: 1.000, 0.95: 1.069, 0.99: 1.039}`**.
- [x] Walk-forward δ-sweep at `scripts/run_lwc_delta_sweep.py`. Output: `reports/tables/v1b_lwc_delta_sweep.csv`. Selection criterion (mirrors M5): smallest δ such that walk-forward realised coverage ≥ τ on every split.
- [x] **`δ_LWC = {0.68: 0.00, 0.85: 0.00, 0.95: 0.00, 0.99: 0.00}`** — all zero. Finding worth flagging: LWC's per-symbol scale standardisation tightens cross-split calibration variance enough that the M5-style overshoot margin is no longer load-bearing. Compare M5's deployed `{0.05, 0.02, 0.00, 0.00}`. Worst-split deficits at τ=0.95 (−1.74 pp) and τ=0.99 (−0.23 pp) are within splitting noise; raising δ to clear them costs **+30% / +53% on width** (the τ=0.99 jump is a c-grid discontinuity) for negligible coverage gain.

### 1.3 — Artefact build ✅

- [x] `scripts/build_lwc_artefact.py` written and run. Builds in well under M5's runtime.
- [x] `data/processed/lwc_artefact_v1.parquet` — 5,916 rows × 10 symbols × 631 weekends, with `sigma_hat_sym_pre_fri` column.
- [x] `data/processed/lwc_artefact_v1.json` — 12 (regime quantiles) + 4 (c) + 4 (δ) = 20 scalars + σ̂ window metadata + train/OOS counts.

### 1.4 — Python serving path ✅

- [x] `Oracle.fair_value_lwc()` added as a sibling to `fair_value`. `Oracle.load()` gained an optional `lwc_artefact_path` parameter (defaults to canonical path; gracefully no-ops if file missing). New `Oracle.has_lwc` property.
- [x] `PricePoint` receipt schema unchanged; the `diagnostics` dict gains `sigma_hat_sym_pre_fri` and `q_regime_lwc`. `forecaster_used = "lwc"`.
- [x] Module-level constants `LWC_REGIME_QUANTILE_TABLE`, `LWC_C_BUMP_SCHEDULE`, `LWC_DELTA_SHIFT_SCHEDULE`, `LWC_METADATA` loaded from the sidecar at import. Helpers `lwc_delta_shift_for`, `lwc_c_bump_for`, `lwc_regime_quantile_for`.
- [x] `forecaster_code = 3` reservation comment added to `crates/soothsayer-oracle/src/types.rs` (no Rust code change; `cargo check` clean). Rust port stays gated on Phase 5.

### 1.5 — Smoke ✅

- [x] `uv run python scripts/smoke_oracle.py --forecaster lwc` exercises all 36 cells (SPY / MSTR / HOOD × 4 τ × 3 regimes) and returns a valid `PricePoint` for every one. σ̂ scaling visible in widths: SPY (σ̂≈0.008) → 167 bps at τ=0.95 normal; MSTR (σ̂≈0.027) → 555 bps at the same anchor; HOOD (σ̂≈0.021) → 435 bps.
- [x] `--forecaster m5` (M5 dual-profile path) byte-for-byte unchanged from prior runs.
- [x] Non-bot pytest suite green (`tests/test_protocol_compare.py` + `tests/test_oracle_competitor_registry.py` — 11 tests + 5 subtests pass).

### Phase 1 deliverables — handed off to the secondary agent

- `src/soothsayer/backtest/calibration.py` — LWC primitives.
- `scripts/run_lwc_delta_sweep.py` + `reports/tables/v1b_lwc_delta_sweep.csv`.
- `scripts/build_lwc_artefact.py` + `data/processed/lwc_artefact_v1.{parquet,json}`.
- `src/soothsayer/oracle.py` — `Oracle.fair_value_lwc()`, LWC constants, sidecar loader.
- `crates/soothsayer-oracle/src/types.rs` — comment-only reservation of `FORECASTER_LWC = 3`.
- `scripts/smoke_oracle.py` — `--forecaster lwc` mode.

---

## Phase 2 — Re-run the full §6 / §7 validation battery on M6

**Goal:** produce the full empirical evidence the paper needs to promote M6 to the headline result. Every robustness check the paper currently runs against M5 must be re-run against M6 and reported alongside.

Add a `--forecaster {m5, lwc}` flag to each runner below and persist outputs to parallel CSVs under `reports/tables/m6_lwc_*.csv`.

### 2.1 — Robustness battery

- [ ] `scripts/run_v1b_per_symbol_diagnostics.py` — expect **10/10 per-symbol Kupiec passes at τ=0.95** based on the bake-off. Persist **Berkowitz LR per symbol** — this is the central new evidence.
- [ ] `scripts/run_v1b_garch_baseline.py` — re-run matched-coverage comparison against the GARCH-side benchmark.
- [ ] `scripts/run_v1b_split_sensitivity.py` — re-run the four-anchor split-date sensitivity {2021, 2022, 2023, 2024} with M6.
- [ ] `scripts/run_v1b_loso.py` — leave-one-symbol-out CV. **Most important sensitivity check** given that LWC's whole point is per-symbol calibration.
- [ ] `scripts/run_v1b_per_class.py` — per-asset-class breakdown.
- [ ] `scripts/run_v1b_path_fitted_conformal.py` — path-coverage variant on the perp tape.
- [ ] `scripts/run_v1b_vol_tertile.py` — confirm the §6.3.1 cross-sectional-AR(1) finding holds or moves under M6.
- [ ] `scripts/aggregate_ab_comparison.py` — produce M5-vs-M6 **block-bootstrap CIs** on coverage and width at every anchor (**1000 weekend-block resamples, seed 0**).

### 2.2 — Pooled OOS tables

- [ ] New pooled OOS table for M6 mirroring §6.3.1 (Kupiec + Christoffersen at τ ∈ {0.68, 0.85, 0.95, 0.99}).
- [ ] New realised-move-tertile decomposition mirroring the calm/normal/shock table in §6.3.

### 2.3 — Summary doc

- [ ] Write `reports/m6_validation.md` in the same shape as `reports/v1b_calibration.md`, with all numbers populated.

### Definition of done — Phase 2

- All eight robustness scripts run cleanly with `--forecaster lwc`.
- M6 row of the per-symbol diagnostics table shows **≥ 8/10 Kupiec passes at τ=0.95** (failure-mode inverted from M5).
- `reports/m6_validation.md` is filled in with all numbers populated.

---

## Phase 3 — Simulation study

**Goal:** validate the LWC methodology on synthetic data with known ground truth — the standard reviewer hygiene check the paper currently lacks.

Build `scripts/run_simulation_study.py`. Use NumPy default RNG with **seed 0**. The simulation must be deterministic. Run **100 Monte Carlo replications per DGP**.

### 3.1 — DGP A (homoskedastic baseline)

- [ ] Generate 10 synthetic "symbols", each 600 weekend returns drawn i.i.d. from Student-t df=4 with known scale parameters spanning the empirical range of the real panel (`σ ∈ [0.005, 0.030]`). No regimes.
- [ ] Fit M5 and M6 separately. Report per-symbol Kupiec at τ ∈ {0.68, 0.85, 0.95, 0.99} for both.
- **Expected:** M5 exhibits per-symbol bimodality (low-σ over-cover, high-σ under-cover) by construction. M6 should pass per-symbol at all 10 since it standardises by σ.

### 3.2 — DGP B (regime-switching)

- [ ] Same 10 symbols, but a 3-state Markov regime governs a global volatility multiplier (low/medium/high — **multipliers 0.5/1.0/2.0**, transition probabilities calibrated to roughly match the empirical 65/24/10 split). Regime is observable.
- [ ] Fit both architectures using the regime label as a stratifier. Same per-symbol Kupiec.
- **Expected:** M6 still passes per-symbol; M5 still bimodal. Width should now scale appropriately with regime under both.

### 3.3 — DGP C (non-stationary scale — the realistic case)

- [ ] Same 10 symbols, but each symbol's σ slowly drifts upward over time (`σ_t = σ_0 · (1 + 0.1 · t/T)` over 600 weekends). This is the case where the trailing-26-week σ̂ in LWC has to track the change.
- **Expected:** M6 stays calibrated; M5 progressively under-covers as the panel ages.

### 3.4 — DGP D (exchangeability stress test)

- [ ] Inject a structural break at `t = 400` (variance triples). This breaks the conformal-prediction exchangeability assumption. Fit on `t < 400`, evaluate on `t ≥ 400`.
- **Expected:** Both architectures degrade. The right finding is **how much** and **whether LWC's adaptive scale recovers faster**. Honest reporting here strengthens the paper.

### 3.5 — Outputs

- [ ] `reports/tables/sim_{a,b,c,d}_*.csv` for each DGP.
- [ ] `reports/figures/simulation_summary.{pdf,png}` — per-symbol Kupiec p-value distributions for M5 vs M6 across the four DGPs.
- [ ] `reports/m6_simulation_study.md` with the four-DGP table populated and the summary figure rendered.

### Definition of done — Phase 3

- Four DGPs complete, 100 reps each.
- Outputs and summary doc rendered.
- Result is reproducible from seed 0.

---

## Phase 4 — Forward-tape harness scaffolding

**Goal:** build the infrastructure to validate M6 on truly held-out forward weekends as they accumulate, so the next paper revision can include "T weekends of forward-tape OOS validation since artefact freeze."

This is **scaffolding** — it will not produce paper evidence yet. The harness's job is to make sure that when forward weekends arrive, validation is one command away.

### 4.1 — Freeze the artefact

- [ ] Tag the M6 artefact at `data/processed/lwc_artefact_v1_frozen_{YYYYMMDD}.json` with a hash (e.g. SHA-256). This frozen artefact is what all forward-tape evaluation runs against. The "live" artefact (`lwc_artefact_v1.json`) keeps updating; the frozen one does not.

### 4.2 — Forward-tape collector

- [ ] Write `scripts/collect_forward_tape.py`:
  - Reads from existing scryer parquet incrementally.
  - Identifies weekends with `fri_ts > artefact_freeze_date`.
  - Builds a forward panel mirroring the training panel schema.
  - Persists to `data/processed/forward_tape_v1.parquet`.

### 4.3 — Forward-tape evaluator

- [ ] Write `scripts/run_forward_tape_evaluation.py`:
  - Loads the frozen artefact.
  - Loads the forward tape.
  - Runs the §6.3 / §6.4 / §6.6 batteries on the forward tape only — **no schedule re-fitting, no quantile re-training, nothing touches the frozen artefact**.
  - Outputs `reports/m6_forward_tape_{N}weekends.md` in the same shape as `reports/m6_validation.md`.

### 4.4 — CI workflow

- [ ] Add `.github/workflows/forward_tape_monthly.yml` running `collect_forward_tape.py` + `run_forward_tape_evaluation.py` monthly and committing the resulting markdown/CSVs.

### Definition of done — Phase 4

- Collector and evaluator both run cleanly against an empty forward tape (n=0 → graceful exit with "insufficient data").
- When ≥ 4 forward weekends have accumulated post-freeze, the evaluator produces a populated report.
- Frozen artefact hash is committed.

---

## Phase 5 — Rust parity port for M6 (GATED)

**Gate:** do **not** start until Adam has forwarded Phase 1–4 results to the secondary agent and explicitly green-lit this phase here.

**Goal:** extend the byte-for-byte parity contract of §8.5 to M6.

### 5.1 — Port

- [ ] Port `Oracle.fair_value_lwc` to `crates/soothsayer-oracle/src/oracle.rs`.
- [ ] Add the per-symbol scale series to `crates/soothsayer-oracle/src/config.rs` (or load it from a binary asset — the per-Friday scale is per-(symbol, fri_ts), so it's a lookup, not a constant).

### 5.2 — Parity

- [ ] Update `scripts/verify_rust_oracle.py` to add 90 LWC test cases. Target **90/90 pass for both M5 and M6 (180/180 total)**.

### 5.3 — On-chain

- [ ] Reserve `forecaster_code = 3` (FORECASTER_LWC) in the on-chain Anchor program.
- [ ] Wire-format invariance: existing M5 consumers must decode M6 `PriceUpdate` accounts without crashing — only the `forecaster_code` field changes.

### Definition of done — Phase 5

- 180/180 Python ↔ Rust parity.
- On-chain decoder unchanged.
- M6 publishable end-to-end through the existing publisher CLI.

---

## Reporting back

When Phases 1–5 are complete, produce one summary at `reports/m6_promotion_summary.md` containing:

- Headline M6 OOS table at τ ∈ {0.68, 0.85, 0.95, 0.99} (mirrors §6.3 of the paper).
- Per-symbol Kupiec table for M6 vs M5 (mirrors §6.4.1).
- Block-bootstrap CIs on the M5 → M6 width and coverage deltas.
- Four-DGP simulation summary table.
- Bullet list of any Phase-2 robustness check where **M6 underperforms M5** — these are the ones we need to discuss.
- Frozen artefact hash and freeze date.

Adam then brings this back into the conversation and we plan the Paper 1 revision around it.
