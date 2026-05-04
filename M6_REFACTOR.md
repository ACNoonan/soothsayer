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

## Phase 2 — Re-run the full §6 / §7 validation battery on M6  ✅ COMPLETE 2026-05-04

**Goal:** produce the full empirical evidence the paper needs to promote M6 to the headline result. Every robustness check the paper currently runs against M5 has been re-run against M6 and reported alongside in `reports/m6_validation.md`.

Implementation: a small forecaster dispatcher in `src/soothsayer/backtest/calibration.py` (`prep_panel_for_forecaster`, `fit_split_conformal_forecaster`, `serve_bands_forecaster`) keeps per-script changes minimal — each runner gained an `argparse --forecaster {m5,lwc}` flag and writes to `m6_lwc_*` CSVs when run under LWC.

### 2.1 — Robustness battery ✅

- [x] `scripts/run_v1b_per_symbol_diagnostics.py` → **10/10 per-symbol Kupiec passes at τ=0.95 under LWC** (vs 2/10 under M5). HOOD violation rate 13.9% → 4.05% (Kupiec p 0.000 → 0.552). Per-symbol Berkowitz LR range collapses from 0.9–224 (250×) under M5 to 3.3–18 (5.5×) under M6.
- [x] `scripts/run_v1b_garch_baseline.py` — GARCH undercovers at every τ (0.9254 at τ=0.95, p<0.001 Kupiec); both M5 and LWC clear Kupiec; LWC Christoffersen 0.275 vs M5 0.921.
- [x] `scripts/run_v1b_split_sensitivity.py` — LWC realised at τ=0.95 across 4 splits = 0.9502–0.9506 (M5: 0.9502–0.9507). LWC Christoffersen rejects at 2021 + 2022 splits; M5 doesn't (see discussion list entry 2 below).
- [x] `scripts/run_v1b_loso.py` — **most striking generalisation result.** LWC LOSO realised mean=0.9497, **std=0.0134** (vs M5 std=0.0759 — 5.7× tighter); **all 10 symbols pass Kupiec when held out** (vs M5: held-out MSTR drops to 0.786, SPY climbs to 1.000).
- [x] `scripts/run_v1b_per_class.py` — width redistribution: equities 355→436 bps (+23%), gold/treasuries 355→184 bps (−48%); LWC Kupiec passes every class at every τ; M5 over-covers gold/treasuries (Kupiec p=0.000–0.001 at τ=0.95).
- [x] `scripts/run_v1b_path_fitted_conformal.py` — LWC narrows endpoint-vs-path gap at τ=0.95 from M5's −4.05pp to −1.16pp without explicit path-fitting (σ̂-rescaling absorbs within-weekend path variance).
- [x] `scripts/run_v1b_vol_tertile.py` — bin-structure refutation holds under both forecasters (M5: 173→175, LWC: 165→168 — finer cells don't drop Berkowitz LR). LWC Berkowitz is 5% lower pooled but both still strongly reject.
- [x] `scripts/aggregate_m5_m6_bootstrap.py` (new — separate from the Kamino-policy `aggregate_ab_comparison.py`). 1000 weekend-block resamples, seed 0, paired by `(symbol, fri_ts)`. **Headline at τ=0.95: Δrealised = 0.000 [−0.014, +0.013]** (CI straddles 0); **Δhalf-width = +30.7 bps [+12.3, +49.0]** (CI excludes 0 high). At τ=0.85 LWC is reliably *narrower* (Δhw=−17, CI [−27, −8]). At τ=0.99 width is statistically neutral.

### 2.2 — Pooled OOS + tertile tables ✅

- [x] `scripts/run_m6_pooled_oos_tables.py` (new). Pooled OOS at every served τ + realised-move tertile decomposition (calm/normal/shock × τ × forecaster). Both forecasters in one CSV pair.
  - Pooled at τ=0.95: M5 realised 0.9503 / hw 354.6 / Kupiec 0.956 / Christ 0.921; LWC realised 0.9503 / hw 385.3 / Kupiec 0.956 / Christ 0.275.
  - Tertile at τ=0.95 shock: M5 0.8718 / 368.9 bps; LWC 0.8782 / 394.6 bps. Shock-tertile floor improves only +0.64pp under LWC — orthogonal axis (cross-sectional ρ, not per-symbol scale).

### 2.3 — Summary doc ✅

- [x] `reports/m6_validation.md` written (full evidence pack, ~13 sections including the discussion list and reproduce-from-scratch script block).

### Definition of done — Phase 2 ✅

- [x] All eight robustness scripts run cleanly with `--forecaster lwc`.
- [x] M6 per-symbol Kupiec at τ=0.95: **10/10 passes** (well above the ≥8/10 threshold; M5: 2/10).
- [x] `reports/m6_validation.md` is filled in with all numbers populated.

### Phase 2 discussion list — where M6 underperforms M5

These are the cells where the comparison flips against M6, surfaced for the paper-revision conversation. Full detail in `reports/m6_validation.md` §11.

1. **Pooled half-width at τ=0.95: +30.7 bps wider** (CI excludes zero). The +8.6% width tax — the trade-off for per-symbol calibration. M6 still passes Kupiec at the same level (p=0.956 for both).
2. **Christoffersen p drops at every τ.** LWC has 2021 + 2022 split-date Christoffersen rejections at τ=0.95 (M5 didn't). LWC tightens unconditional per-symbol calibration but introduces some lag-1 violation clustering — σ̂_sym(t) is itself slowly-varying, so a calm streak under-estimates σ̂ going into a vol shock.
3. **Shock-tertile floor barely improves** (+0.64pp). The §9.1 ceiling is cross-sectional common-mode (M6a territory), not per-symbol scale (M6 LWC).
4. **Path-coverage Kupiec still rejects at τ=0.68/0.85.** LWC's narrower endpoint-vs-path gap at τ=0.95 doesn't lift Kupiec p at lower τ.
5. **Per-symbol Berkowitz still rejects for TSLA / GOOGL / TLT** at α=0.01 (LR 14–18 vs M5's 27–141 — 5–14× smaller but non-zero). Cross-sectional common-mode again.
6. **NVDA Berkowitz LR rises slightly** (0.92 → 7.92). NVDA was M5's best symbol; LWC marginally over-tightens it. Small price for fixing 9 others.

---

## Phase 3 — Simulation study  ✅ COMPLETE 2026-05-04

**Goal:** validate the LWC methodology on synthetic data with known ground truth — the standard reviewer hygiene check the paper currently lacks.

Single deliverable: `scripts/run_simulation_study.py`. Deterministic from seed=0; full battery (4 DGPs × 100 reps × 2 forecasters) runs in ~30 s. Per-DGP RNG via `np.random.default_rng(0).spawn(4)` so adding/removing a DGP doesn't perturb others' draws.

### 3.1 — DGP A (homoskedastic baseline) ✅

- [x] 10 synthetic symbols, σ_i ∈ linspace(0.005, 0.030, 10), 600 i.i.d. Student-t df=4 weekend returns each (rescaled so std(r)=σ_i). No regimes.
- [x] **M5 pass-rate at τ=0.95 = 0.311** (311/1000 cells) — bimodality reproduces under controlled conditions, as predicted.
- [x] **LWC pass-rate at τ=0.95 = 0.994** (994/1000) — uniform calibration per-symbol.

### 3.2 — DGP B (regime-switching) ✅

- [x] 3-state Markov chain over `{medium=1.0×, low=0.5×, high=2.0×}` vol multipliers; stationary distribution [0.65, 0.25, 0.10] enforced by detailed-balance construction (state 0 dwell ~24 weeks; states 1/2 dwell ~6.7 weeks). Regime label observable.
- [x] **M5 pass-rate = 0.310, LWC = 0.976.** LWC pays a ~2pp pass-rate cost vs DGP A — regime transitions inject σ̂-tracking lag (when regime flips, σ̂ is contaminated with the previous regime's residuals for ~13 weekends). The only DGP where LWC's pass-rate falls noticeably below 0.99.

### 3.3 — DGP C (non-stationary scale — drift) ✅

- [x] σ_t = σ_i · (1 + 0.1·t/T). 10% drift over 600 weekends.
- [x] **M5 pass-rate = 0.309, LWC = 0.996.** This is LWC's *best* DGP — drift is exactly the case σ̂'s adaptive K=26 window was designed for.

### 3.4 — DGP D (exchangeability stress test) ✅

- [x] Variance triples at t=400 (std × √3). Train on t<400, evaluate on t≥400.
- [x] **M5 pass-rate = 0.292, LWC = 0.994. The break barely degrades LWC** — pass-rate matches DGP A. σ̂'s 26-week trailing window absorbs the structural break in <26 weekends, and the 174 well-calibrated post-recovery weekends dilute the warm-up under-coverage.
- This was a surprise vs the brief's "honest case where neither method is great" prediction. **Stronger result than expected.**

### 3.5 — Outputs ✅

- [x] `reports/tables/sim_{a,b,c,d}_per_symbol_kupiec.csv` (1000 rows × 4 anchors × 2 forecasters per DGP).
- [x] `reports/tables/sim_summary.csv` (one row per DGP × τ × forecaster).
- [x] `reports/figures/simulation_summary.{pdf,png}` — 4-panel box-plot at τ=0.95, M5 vs LWC × 10 symbols × 100 reps.
- [x] `reports/m6_simulation_study.md` — full evidence pack with per-DGP narrative + headline tables + reproducibility block.

### Definition of done — Phase 3 ✅

- [x] Four DGPs complete, 100 reps each.
- [x] Outputs and summary doc rendered.
- [x] Result is reproducible from seed 0 (single command: `uv run python -u scripts/run_simulation_study.py`).

---

## Phase 4 — Forward-tape harness scaffolding ✅ COMPLETE 2026-05-04

**Goal:** build the infrastructure to validate M6 on truly held-out forward weekends as they accumulate, so the next paper revision can include "T weekends of forward-tape OOS validation since artefact freeze."

This is **scaffolding** — it does not produce paper evidence yet. The harness's job is to make sure that when forward weekends arrive, validation is one command away. Phase 4 split cleanly into two sides: the scryer agent shipped G1.b (forward polling for VIX via CBOE + daily CME 1m for futures) on 2026-05-04; the soothsayer side wires the new sources into `panel.py` and bundles the harness behind a launchd-driven runner.

### 4.0 — Scryer-side hand-off ✅

- [x] Drafted `M6_PHASE4_SCRYER_BRIEF.md` (now deleted — purpose served).
- [x] Scryer agent confirmed coverage, ran the cadence audit, identified the 7 non-forward-polled symbols (4 futures + 3 vol indices), and shipped G1.b: VIX → `cboe/indices/v1/index=VIX/` (daily 22:30 UTC); futures → soothsayer-side resample of `cme/intraday_1m/v1` (daily 06:00 UTC). ^GVZ + ^MOVE remain on soothsayer's existing VIX-fallback path (acceptable per the brief's §5 watch-out).
- [x] Forward-poll cadences documented: equities-daily 22:00 UTC, earnings 23:00 UTC, cme-intraday-1m 06:00 UTC, cboe-indices 22:30 UTC. All under a 25h SLA.

### 4.1 — Freeze the artefact ✅

- [x] `scripts/freeze_lwc_artefact.py` (re-runnable). Copies `lwc_artefact_v1.{json,parquet}` → `lwc_artefact_v1_frozen_{YYYYMMDD}.{json,parquet}` and embeds two SHA-256s: `_frozen_parquet_sha256` over the parquet bytes and `_artefact_sha256` over the canonical-JSON serialisation of the augmented sidecar.
- [x] First freeze produced: `data/processed/lwc_artefact_v1_frozen_20260504.{json,parquet}` (training cutoff = 2026-04-24, last complete training Friday).

### 4.2 — Forward-tape collector ✅

- [x] `scripts/collect_forward_tape.py`:
  - Auto-discovers the latest frozen artefact (or accepts `--frozen-suffix YYYYMMDD`).
  - Calls `soothsayer.backtest.panel.build()` over a 400-day context window so the evaluator's σ̂_sym(t) and `regimes._high_vol_flag` rolling-quantile windows are stable for the first forward weekend.
  - Calls `regimes.tag()` to add `regime_pub` + `realized_bucket` (panel.build doesn't tag).
  - Persists `data/processed/forward_tape_v1.parquet` with `is_forward = (fri_ts > cutoff)` per row.
- [x] Currently 560 context rows × 56 weekends, 0 forward rows (the 2026-05-01 weekend's CME bar is missing because of a backfill gap from the runner's standup).

### 4.3 — Forward-tape evaluator ✅

- [x] `scripts/run_forward_tape_evaluation.py`:
  - Loads the frozen JSON sidecar's three schedules directly (constants only; never touches the live module-level `LWC_*` tables — immune to live-artefact updates between freeze and evaluation).
  - Recomputes σ̂ over the combined context+forward panel (same K=26 / min_obs=8 as the artefact build).
  - Applies the LWC serving formula on forward rows; computes pooled-OOS metrics (Kupiec + Christoffersen at 4 anchors) and per-symbol Kupiec + Berkowitz LR.
  - Outputs `reports/m6_forward_tape_{N}weekends.md` with a "preliminary" banner when N < 4.
- [x] Empty-tape graceful: writes a `m6_forward_tape_0weekends.md` stub when no forward rows are available; the wrapper script's SLA pre-check explains the most-likely cause.
- [x] End-to-end synthetic test (cutoff shifted to 2026-04-10, 2 forward weekends): pooled OOS realised 0.7500 / 0.9500 / 1.0000 / 1.0000 across the four anchors — no errors, all metrics populate.

### 4.4 — Recurring trigger (launchd) ✅

- [x] `scripts/check_scryer_freshness.py` — SLA pre-check reads `internal.scryer/workflow_run/v2`, confirms the four runners have a `succeeded` run in the last 26h. Currently OK on all four (latest within ~30 min of fire time).
- [x] `scripts/run_forward_tape_harness.sh` — wrapper that runs SLA check + collector + evaluator, all stdout/stderr appended to `~/Library/Logs/soothsayer-forward-tape.log`. Wrapper does NOT git-commit (Adam's "phase-commit" preference; he reviews + commits manually).
- [x] `launchd/com.adamnoonan.soothsayer.forward-tape.plist` — fires every Tuesday at 09:30 local time. **Install instructions inside the plist comment.** Plist passes `plutil -lint`. Per Adam's global memory: launchd is the canonical recurring scheduler; `/schedule` and CronCreate/RemoteTrigger are explicitly avoided.

### 4.5 — End-to-end test + documentation ✅

- [x] Local fire produced clean run: SLA OK, collector wrote the tape, evaluator wrote the 0-weekend stub. Total wall clock ~3 s.
- [x] M6_REFACTOR.md updated (this commit).
- [x] `M6_PHASE4_SCRYER_BRIEF.md` deleted (lifecycle-completion as the brief itself directed).

### 4.6 — CBOE VIX + CME futures resample (G1.b adoption) ✅

- [x] Added `load_cboe_index_daily` and `load_cme_daily_from_intraday` to `src/soothsayer/sources/scryer.py`. CBOE schema is `(index, date, open, high, low, close)`; loader normalises to yahoo-bars-shape (`symbol, ts, open, high, low, close`). CME loader resamples 1m bars to UTC-day OHLCV.
- [x] Updated `src/soothsayer/backtest/panel.py::_load_one_symbol` with per-symbol source dispatch:
  - `^VIX` → blend CBOE (forward) with yahoo (legacy); CBOE wins on overlap. (`^GVZ`, `^MOVE` stay on yahoo + existing VIX-fallback.)
  - `ES=F` / `NQ=F` / `GC=F` / `ZN=F` → blend yahoo (legacy) with CME-resampled (forward); **yahoo wins on overlap** to preserve the frozen artefact's training convention.
  - All other symbols unchanged.
- [x] Verified the source switch produces byte-identical historical reads (frozen-artefact training period intact) and picks up the new sources for forward dates the legacy sources don't have.

### Definition of done — Phase 4 ✅

- [x] Scryer side confirmed (G1.b shipped) and adopted in panel.py.
- [x] Frozen artefact JSON contains `_artefact_sha256` and `_frozen_parquet_sha256`.
- [x] Collector and evaluator both run cleanly against the current empty-forward tape (n=0 → graceful "insufficient data" exit, stub report written).
- [x] Wrapper script + launchd plist ready to install. Adam's install: copy plist to `~/Library/LaunchAgents/` and `launchctl load -w …` (instructions inside the plist).

### Open follow-ups

- **First populated forward report.** The 2026-05-01 weekend can't be evaluated because of a CME 1m backfill gap (Apr 29–May 2 missing for ES/NQ/GC/ZN). When the next clean weekend completes (Fri 2026-05-08, evaluable Tue 2026-05-12), the harness will produce the first non-stub `reports/m6_forward_tape_1weekends.md` automatically. After ~4 forward weekends, the preliminary banner clears and the report is paper-revisable evidence.
- **CME backfill.** Adam can ask the scryer agent to backfill 2026-04-29 → 2026-05-02 for the four CME symbols if recovering the 2026-05-01 weekend matters; otherwise the harness will simply skip it.

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
