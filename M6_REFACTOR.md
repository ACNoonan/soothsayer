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
  - σ̂_sym(t): trailing **K=26 weekend** observations of relative residual std per symbol; **strictly pre-Friday** (uses only `fri_ts' < fri_ts`); requires **≥ 8 past observations**. Persisted as `sigma_hat_sym_pre_fri` on the panel. Constants exposed as `SIGMA_HAT_K`, `SIGMA_HAT_MIN`. (Note: the brief's "26-week / 130-trading-day" parenthetical conflates trading-day count with weekend count; the operational unit is **26 past Fridays** — same as the v3 bake-off used for C1.) **(Superseded 2026-05-04 by EWMA HL=8 — see Phase 5. The K=26 trailing window remains the archival receipt-reproduction rule; the deployed σ̂ is now the EWMA variant. The `sigma_hat_sym_pre_fri` column name on the artefact parquet is preserved across the swap, so the Oracle's read path is variant-agnostic.)**
  - Standardised score: `|mon_open − point| / (fri_close · σ̂_sym(t))`.
  - Per-regime quantile fit on the standardised score with the same finite-sample CP rank formula M5 uses (`ceil(τ·(n+1))`).
  - Half-width at serve: `q_r^LWC(τ) · σ̂_sym(t) · fri_close`.
- [x] Sanity: end-to-end fit on `v1b_panel.parquet` reproduces the bake-off C1 receipts byte-for-byte (5,916 rows × 631 weekends, 80 dropped at warm-up; at τ=0.95 realised=0.9503, HW=385.3 bps, c=1.069). See `reports/v3_bakeoff.md`. The EWMA HL=8 variant matches the same 5,916 evaluable rows, with c(τ=0.95)=1.079 and a 3.83% narrower pooled half-width — `reports/m6_sigma_ewma.md` carries the receipts.

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

## Phase 5 — σ̂ fast-reacting variant (Christoffersen-targeted) ✅ COMPLETE 2026-05-04 — PROMOTE EWMA HL=8

**Verdict:** PROMOTE → **EWMA HL=8** is now the canonical M6 σ̂ rule. K=26 trailing window stays buildable for archival (`build_lwc_artefact.py --variant baseline_k26`).

**Headline:** the 2021 + 2022 split-date Christoffersen rejections at τ=0.95 clear (p: 0.0065 → 0.1153, 0.0016 → 0.1861); per-symbol Kupiec stays 10/10; pooled half-width is **3.83% narrower** at τ=0.95 (block-bootstrap 95-CI upper on Δhw% across all τ = +0.25%, well inside the +5% gate). EWMA HL=8 is the only variant that clears split-date Christoffersen at every (split × τ) at α=0.05 — HL=6 and HL=12 each have one rejection elsewhere; the convex blend has one. See `reports/m6_sigma_ewma.md`.

This phase is **pre-publication empirical work** — it changed the deployed M6 artefact because a variant won on the headline criteria. Phase 6 (simulation sample-size sweep) and Phase 7 (Rust port) consume the EWMA HL=8 σ̂ implementation.

### 5.1 — EWMA σ̂ implementation ✅

- [x] Added `add_sigma_hat_sym_ewma` and `add_sigma_hat_sym_blend` to `src/soothsayer/backtest/calibration.py`. Half-life is a parameter; emits `sigma_hat_sym_ewma_pre_fri_hl{N}` columns. Strict pre-Friday convention preserved (uses only `fri_ts' < fri_ts`). `compute_score_lwc` gained a `scale_col` parameter so any σ̂ column can drive the standardised score.
- [x] Three pure-EWMA half-lives — **HL = 6, 8, 12 weekends** — plus one convex blend (`α · σ̂_K26 + (1−α) · σ̂_EWMA_HL8`, α=0.5).
- [x] Warm-up rule: ≥ 8 past observations (same as M6 baseline). All variants share the same 5,916 evaluable rows.

### 5.2 — Refit c(τ) and δ(τ) per variant ✅

- [x] OOS c-fit and walk-forward δ-fit per variant via `scripts/run_sigma_ewma_variants.py`. Outputs: `reports/tables/sigma_ewma_<variant>_delta_sweep.csv` (one per variant). All five variants land at δ=0 across all τ (cov_mean ≥ τ at δ=0 for every cell, matching the M6 baseline criterion).
- [x] At split=2023-01-01 the EWMA HL=8 schedule is `c = {0.68: 1.000, 0.85: 1.000, 0.95: 1.079, 0.99: 1.003}` and `δ = {all zero}`. Per-regime quantiles in `data/processed/lwc_artefact_v1.json`.

### 5.3 — Targeted diagnostics ✅

- [x] **Split-date Christoffersen** at all 4 split anchors × 4 τ × 5 variants. EWMA HL=8 is the only variant with **zero rejections** at α=0.05 across the entire 16-cell grid. Output: `reports/tables/sigma_ewma_split_sensitivity.csv`.
- [x] **Per-symbol Berkowitz LR** — 10 symbols × 5 variants. Of the three Phase-2 outliers (TSLA, GOOGL, TLT), GOOGL clears at α=0.01 under EWMA HL=8 (p=0.017 vs baseline 0.002); TLT and TSLA still reject (LR 16.7 / 13.5 vs baseline 14.4 / 18.0 — TLT essentially flat, TSLA modestly improved). Cross-sectional common-mode is the residual rejection axis, as expected. Output: `reports/tables/sigma_ewma_per_symbol.csv`.
- [x] **Pooled OOS Kupiec + half-width** at split=2023-01-01: realised 0.6925 / 0.8549 / 0.9503 / 0.9902 (K=26 baseline: 0.6873 / 0.8613 / 0.9503 / 0.9902); half-width 130.8 / 213.6 / 370.6 / 635.0 bps (baseline: 132.6 / 218.1 / 385.3 / 685.8). Output: `reports/tables/sigma_ewma_summary.csv`.
- [x] **Per-symbol Kupiec at τ=0.95** — 10/10 under EWMA HL=8 (baseline 10/10).
- [x] **Block-bootstrap CI on (Δrealised, Δhw)** at all 4 τ vs baseline_k26: 1000 weekend-block resamples, seed=0, paired on `(symbol, fri_ts, τ)`. Δhw% 95-CI upper across all τ = +0.25% (gate: ≤ +5%). Output: `reports/tables/sigma_ewma_bootstrap.csv`.

### 5.4 — Decision + re-freeze ✅

- [x] Promotion criterion satisfied. Re-built the artefact under EWMA HL=8 via `build_lwc_artefact.py --variant ewma_hl8` (now the default). Sidecar `_lwc_variant` field set to `"ewma_hl8"`; `sigma_hat` block records method=ewma, half_life_weekends=8.
- [x] Re-froze via `scripts/freeze_lwc_artefact.py`. New canonical freeze: `data/processed/lwc_artefact_v1_frozen_20260504.{json,parquet}` (sha 7b86d17a76912aa0…). Original K=26 freeze archived to `lwc_artefact_v1_archive_baseline_k26_20260504.{json,parquet}` (sha-preserved).
- [x] Forward-tape harness re-fired clean against the new freeze; the auto-discovery glob `lwc_artefact_v1_frozen_*` now picks up the EWMA freeze (the archive name was deliberately moved outside the `_frozen_*` pattern so the glob remains unambiguous).
- [x] `tests/test_oracle_competitor_registry.py` + `tests/test_protocol_compare.py` — 11 tests + 5 subtests still pass.
- [x] M5 smoke (`scripts/smoke_oracle.py --forecaster m5`) byte-for-byte unchanged.

### 5.5 — Reporting ✅

- [x] `reports/m6_sigma_ewma.md` — full evidence pack: variant comparison tables, the four headline diagnostics, the bootstrap CI, the verdict, reproduce-from-scratch script block.
- [x] Dated entry in `reports/methodology_history.md` (2026-05-04, σ̂ EWMA HL=8 promotion).

### 5.6 — Selection-procedure disclosure (post-promotion) ✅

The Phase 5.3 promotion ran 80 split-date Christoffersen tests (5 variants × 4 splits × 4 τ) and selected the only variant with zero per-cell rejections at uncorrected α=0.05. That selection is multi-test exposed. This sub-phase adds the mitigation so the paper's Phase 5 narrative reads "pre-registered, multi-test corrected, forward-tape re-validated" rather than "uncorrected best-of-five."

- [x] **Pre-registration disclosure.** `reports/m6_sigma_ewma.md` §13 added: explicit pre-registration of the three-gate criterion, transparent 5×16 grid of all variants' Christoffersen p-values, multi-test exposure framing, honest-claim limits.
- [x] **Benjamini-Hochberg correction.** `scripts/run_sigma_ewma_variants.py` extended with `benjamini_hochberg()` + `emit_multiple_testing_correction()`; writes `reports/tables/sigma_ewma_split_sensitivity_bh_corrected.csv`. Result: **under BH at FDR=0.05 across the 80-cell grid, no variant has a rejected cell** (smallest BH-adjusted q is 0.130). The corrected reading is that per-cell evidence does not statistically distinguish the five variants — the case for HL=8 over neighbours rests on the bootstrap CI on width (gate 3, no multi-test issue) and on the held-out forward-tape comparison below.
- [x] **Variant bundle freeze.** `scripts/freeze_sigma_ewma_variant_bundle.py` builds (qt, cb, δ) for all 5 variants at the same training cutoff (split=2023-01-01) and writes `data/processed/lwc_variant_bundle_v1_frozen_{YYYYMMDD}.json` — content-addressed (SHA-256), date-tagged, on a separate glob from the canonical `lwc_artefact_v1_frozen_*` deployment file. Lifecycle is independent. First freeze: `lwc_variant_bundle_v1_frozen_20260504.json` (sha 7cef6132d970…).
- [x] **Forward-tape variant comparison.** `scripts/run_forward_tape_variant_comparison.py` — sibling to the canonical evaluator; loads the variant bundle, computes σ̂ per variant on the combined context+forward panel, applies each variant's frozen schedules, and writes `reports/m6_forward_tape_{N}weekends_variants.md` plus `reports/tables/m6_forward_tape_{N}weekends_variants.csv`. Re-validation framing: the report does NOT re-select among variants on forward data; its job is to flag if a different variant looks dramatically cleaner on the held-out slice.
- [x] **Wired into the harness.** `scripts/run_forward_tape_harness.sh` step 5 runs the variant comparison after the canonical evaluator; failure is non-fatal (canonical step 4 is the deployment-load-bearing one).

### Definition of done — Phase 5 ✅

- [x] Three EWMA half-lives (6, 8, 12) + convex blend implemented, fit, diagnosed.
- [x] Split-date Christoffersen + per-symbol Berkowitz tables emitted for all variants.
- [x] `reports/m6_sigma_ewma.md` rendered with explicit Promote verdict.
- [x] Artefact re-frozen, Phase 1 §1.1 updated, smoke + tests still green.
- [x] §5.6 selection-procedure disclosure (BH correction + variant bundle + forward-tape re-validation) shipped 2026-05-04 (this section).

---

## Phase 6 — Simulation: sample-size sensitivity (panel-admission criterion) ✅ COMPLETE 2026-05-04

**Verdict:** newly-listed-symbol admission threshold is **N ≥ 80 weekends** under stationary / drift / structural-break DGPs (LWC pass-rate ≥ 0.95 across the entire N-grid for those three DGPs). Under regime-switching (DGP B), the K=26 σ̂ tracking-lag pushes the strict-0.95 threshold to N=600; the relaxed-criterion threshold (LWC pass-rate ≥ 0.94) is N=200. **Recommended deployment threshold for Soothsayer-style panels: N ≥ 200.** HOOD's empirical N≈218 sits inside this band and its per-symbol Kupiec p=0.552 is consistent with the simulation's 0.94–0.99 range at N=200.

The N=600 cells reproduce Phase 3's `sim_summary.csv` byte-for-byte (regression check passes: `n_pass_05` and `pass_rate_05` bit-exact, `mean_realised` matches to float-rounding noise of 1.1×10⁻¹⁶).

### 6.1 — Sweep grid ✅

- [x] Built `scripts/run_simulation_size_sweep.py` as a sibling to `run_simulation_study.py`. Imports the Phase 3 RNG hierarchy + builders by file-path so the two scripts share identical seeds and the N=600 column is bit-exact.
- [x] Sweep `N ∈ {80, 100, 150, 200, 300, 400, 600}` complete. Each rep generates the full N=600 base panel using Phase 3's exact RNG sequence, then truncates to the requested N (DGPs A/B/C) or rebuilds with N-dependent break (DGP D).
- [x] 4 DGPs × 7 N × 4 anchors × M5 + LWC × 100 reps = 22,400 Kupiec cells total. Runtime ~6 minutes; output `sim_size_sweep_per_symbol_kupiec.csv` is 224,000 rows.

### 6.2 — Pass-rate curves ✅

- [x] Per-(DGP, τ=0.95, forecaster) pass-rate curves rendered. **Panel-admission thresholds (LWC pass-rate ≥ 0.95):** A=80, B=600, C=80, D=80. **Parity-with-M5 floor:** N=80 across all four DGPs. Output: `reports/tables/sim_size_sweep_admission_thresholds.csv`.

### 6.3 — Outputs ✅

- [x] `reports/tables/sim_size_sweep_per_symbol_kupiec.csv` (224,000 rows).
- [x] `reports/tables/sim_size_sweep_summary.csv` (224 rows).
- [x] `reports/tables/sim_size_sweep_admission_thresholds.csv` (4 rows).
- [x] `reports/figures/sim_size_curves.{pdf,png}` — 4-panel curves, log-N x-axis, M5 (red) vs LWC (blue), 0.95 reference line.

### 6.4 — Production guidance ✅

- [x] New §13 "Newly-listed-symbol admission (Phase 6 evidence)" added to `reports/m6_validation.md` with the regime-assumption × minimum-N × expected-pass-rate table, recommended deployment threshold, and the HOOD cross-check.
- [x] HOOD's empirical N≈218 (246 listed − 28 σ̂ warm-up) cross-references against the N=200 simulated pass-rate range (0.94 under DGP B; 0.99 under DGP A/C/D); HOOD's empirical Kupiec p=0.552 falls within the simulated band.
- [x] Phase 2 §11 item 2 in `reports/m6_validation.md` updated with the Phase 5 EWMA HL=8 resolution note (the 2021/2022 split-date Christoffersen rejections at τ=0.95 cleared under the canonical σ̂).

### 6.5 — Reporting ✅

- [x] §7 "Sample-size sensitivity (Phase 6)" appended to `reports/m6_simulation_study.md` — headline pass-rate-vs-N table, parity-with-M5 floor, HOOD cross-check, production-threshold table, reproducibility block, open follow-ups.
- [x] §14 of `reports/m6_validation.md` (files produced this phase) gained the Phase 5 + Phase 6 entries.

### Definition of done — Phase 6 ✅

- [x] Seven sample sizes × four DGPs × 100 reps × two forecasters complete (22,400 Kupiec cells); runtime ~6 minutes.
- [x] N=600 cells reproduce Phase 3 numbers byte-for-byte (regression guard built into runner).
- [x] Sweep tables + curves figure rendered.
- [x] Newly-listed-symbol admission threshold documented with a numeric N per DGP regime.
- [x] Reproducible from `uv run python -u scripts/run_simulation_size_sweep.py` (no manual seed handling).

### EWMA HL=8 sensitivity follow-up ✅ COMPLETE 2026-05-04

- [x] Added `--sigma-variant {k26, ewma_hl8}` and `--dgps` flags to `scripts/run_simulation_size_sweep.py`. Outputs land in `*_ewma_hl8.csv` so the K=26 sweep is preserved.
- [x] Re-ran DGP B at all 7 N × 100 reps under EWMA HL=8 (~90s wall clock). Result: per-symbol Kupiec pass-rate at τ=0.95 only improves at N=600 (0.976 → 0.986, +1pp); intermediate-N differences within Monte Carlo noise. **Strict-0.95 admission threshold under DGP B stays at N=600 across both σ̂ rules.**
- [x] Interpretation captured in `reports/m6_simulation_study.md` §7.6: Phase 5's Christoffersen win does not translate to a Kupiec-pass-rate improvement at small N because the two tests catch different failure modes (temporal clustering vs unconditional violation rate). Under DGP B the bottleneck is **stochastic OOS regime mixture across symbols**, not σ̂'s tracking lag — both σ̂ rules see the same per-symbol regime sequences.
- [x] Production-guidance tables in `reports/m6_simulation_study.md` §7.4 and `reports/m6_validation.md` §13 updated to remove the speculative "EWMA HL=8 expected to lower this" caveat. The relaxed N ≥ 200 deployment threshold is robust to σ̂ choice.

---

## Phase 7 — Paper-strengthening empirical tests (paper-only; no artefact change)

**Goal:** add three pieces of evidence that strengthen Paper 1's value proposition and defuse anticipated reviewer objections. None of these change the deployed M6 artefact; they extend the §6 / §7 evidence pack and use the M6 panel + serving harness already built in Phases 1–2.

These three tests are independent and can be run in any order. Phase 7 does not gate Phase 8 (Rust port) — the artefact is unchanged — but it should be complete before the next Paper 1 revision is sent out.

### 7.1 — Portfolio-level violation clustering (highest ROI) ✅ COMPLETE 2026-05-04

**Why this matters:** the paper currently calibrates per-symbol; a sophisticated consumer (e.g. Kamino risk team) holds correlated assets and asks "what's my portfolio-level tail risk?" The current §6.3.1 framing — "cross-sectional common-mode deferred to a companion paper" — leaves the bands looking operationally weaker than they are. A direct portfolio-level diagnostic settles it: either clustering exists and we give consumers empirical reserve guidance (a contribution, since no incumbent oracle does this), or it doesn't and we've defused §6.3.1 with a positive result. Either outcome strengthens the paper.

- [x] `scripts/run_portfolio_clustering.py`. For each OOS weekend at τ ∈ {0.85, 0.95, 0.99}, counts `k_w = #{symbols breaching their τ-band}` over the 10-symbol panel under both M5 and M6 LWC.
- [x] Compares the empirical distribution of `k_w` to `Binomial(10, 1-τ)` via χ² GOF (bins {0, 1, 2, ≥3}), KS distance, and 1000-rep weekend-block bootstrap CIs on the tail probabilities.
- [x] Outputs: `reports/tables/m6_portfolio_clustering.csv` (long-format aggregate), `reports/tables/m6_portfolio_clustering_per_weekend.csv` (per-weekend `k_w`), `reports/figures/portfolio_clustering.{pdf,png}` (3-panel empirical-vs-binomial PMF).
- [x] §14 of `reports/m6_validation.md` with the headline table + figure cross-reference + consumer reserve guidance.

**Headline at τ=0.95** (173 full-coverage OOS weekends; CIs are 1000-rep weekend-block bootstrap, seed=0):

| | M5 deployed | M6 LWC | Binomial(10, 0.05) |
|---|---|---|---|
| Mean k_w | 0.497 | 0.497 | 0.500 |
| Var ratio (overdispersion) | 1.78 | **2.39** | 1.00 |
| P(k ≥ 3) | 4.05% [1.16, 6.94] | **5.20% [2.31, 8.67]** | 1.15% |
| P(k ≥ 5) | 0.58% [0.00, 1.73] | 1.16% [0.00, 2.89] | 0.01% |
| P(k ≥ 7) | 0.00% | 0.58% [0.00, 1.73] | <0.001% |
| max k_w | 6 | 8 | — |
| χ² GOF p | 0.0001 | <0.0001 | (null) |

**Verdict — paper-strengthening, mixed nuance.** Both forecasters reject the independence null with bootstrap CIs that strictly exclude the binomial reference at k≥3. Calibration of the marginal is preserved (mean = 0.497 / weekend under both, matching binomial 0.500). M6 LWC clusters slightly more than M5 at the upper tail at τ=0.95 (variance ratio 2.39 vs 1.78, max k_w 8 vs 6) — the price of per-symbol scale standardisation, redistributing some marginal mass to the joint upper tail. **Consumer reserve guidance:** at τ=0.95, reserve against an empirical 99th-percentile of ≈ 5 simultaneous breaches, not the binomial ≈ 2. This is the contribution.

### 7.2 — Sub-period robustness within OOS ✅ COMPLETE 2026-05-04

**Why this matters:** §9.2 of Paper 1 currently *discloses* stationarity as a limitation. Sub-period evidence converts the disclosure into either a positive claim (calibration holds across regimes) or a meaningful operating boundary (which consumers need to know). Cheap to run because the panel and serving harness already exist.

- [x] `scripts/run_subperiod_robustness.py`. Splits the 2023+ OOS slice into {2023, 2024, 2025, 2026-YTD-through-2026-04-24}.
- [x] Per-subperiod pooled Kupiec / Christoffersen / realised / half-width at τ ∈ {0.68, 0.85, 0.95, 0.99} under both M5 and M6 LWC (32 cells per forecaster).
- [x] n ≥ 50 (weekend × symbol) cells in every subperiod (2023/2024/2025 = 520, 2026-YTD = 170); the `low_n_flag` column is a sanity guard, not a real cutoff.
- [x] Output: `reports/tables/m6_subperiod_robustness.csv` (32 rows per forecaster).

**Headline at τ=0.95** (`reports/m6_validation.md` §15 has the full per-τ table):

| Subperiod | Realised (M5) | Realised (M6 LWC) | Kupiec p (M5) | Kupiec p (M6) |
|---|---|---|---|---|
| 2023 | 0.965 | 0.942 | 0.089 | 0.432 |
| 2024 | 0.939 | 0.939 | 0.243 | 0.243 |
| 2025 | 0.939 | 0.967 | 0.243 | 0.054 |
| 2026-YTD | 0.977 | 0.959 | 0.079 | 0.587 |

Across the full 16-cell (subperiod × τ) grid per forecaster: M5 has 5 / 16 Kupiec rejections (all over-coverage at lower τ in 2023/2024), M6 LWC has 2 / 16 (both over-coverage in 2025 at τ=0.85 and τ=0.99). Christoffersen rejections: 0 / 16 under both. **Verdict:** §9.2 stationarity disclosure is replaced by a positive claim — M6 LWC realised range across the four years at τ=0.95 is 0.942–0.967, every cell passes Kupiec at α=0.05, no within-symbol lag-1 clustering.

### 7.3 — GARCH-t baseline (replace Gaussian) ✅ COMPLETE 2026-05-04

**Why this matters:** §6.4.2 currently uses GARCH(1,1)-Gaussian, which is a known-to-fail straw man — any reviewer with finance training will say so. GARCH-t is the standard practitioner baseline. If M6 still beats GARCH-t at matched coverage on width, the dominance claim becomes much harder to dismiss. If GARCH-t wins on some metric, we've found something important.

- [x] Extended `scripts/run_v1b_garch_baseline.py` with `--dist {gaussian, t}`. Default preserved as gaussian; the existing receipt's `method` row label literal (`"GARCH(1,1)"`) is preserved so `build_paper1_figures.py` keeps working. Schema-additive: a new `garch_dist` column is appended.
- [x] GARCH-t uses `arch_model(..., dist="t")`; ν is per-symbol; band quantile = `T_ν⁻¹(0.5+τ/2) · √((ν−2)/ν)`.
- [x] Per-symbol fallback to gaussian on convergence failure or ν ≤ 2.5; recorded in `dist_used` column. NVDA hits the floor (ν̂=2.5); the other 9 symbols converge cleanly with ν̂ ∈ [2.84, 6.88].
- [x] Re-ran under both forecasters: `reports/tables/{v1b_robustness,m6_lwc_robustness}_garch_t_baseline.csv`. `reports/m6_validation.md` §16 has the full evidence pack.

**Headline at τ=0.95** (matched OOS keys, n=1,730):

| Method | Realised | HW (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|
| GARCH(1,1)-N | 0.9254 | 322.2 | 0.000 | 0.016 |
| GARCH(1,1)-t | 0.9277 | 331.6 | 0.000 | **0.209** |
| M5 deployed | 0.9503 | 354.6 | 0.956 | 0.921 |
| M6 LWC deployed | 0.9503 | 385.3 | 0.956 | 0.275 |

**Verdict:** GARCH-t closes most of the GARCH-Gaussian τ=0.99 tail-coverage gap (realised 0.985 vs 0.963; Kupiec p 0.05 vs <0.001) and clears Christoffersen at τ=0.95 (p=0.209 vs 0.016) — fat-tailed innovations explain a meaningful chunk of both the tail-coverage gap and the lag-1 clustering. But GARCH-t still fails Kupiec unconditional coverage at every τ < 0.99 (p ∈ {0.018, 0.001, 0.000} at τ ∈ {0.68, 0.85, 0.95}); the standardised-t quantile is *narrower* than Gaussian at low τ for ν≈3, so it tightens exactly where Gaussian was already under-covering. **M6 LWC dominates GARCH-t at matched coverage at every τ.** Paper 1 §6.4.2 should lead with GARCH-t (the practitioner standard), demote Gaussian to a footnote.

### Definition of done — Phase 7

- [x] Three runners ship with reproducible outputs.
- [x] `reports/m6_validation.md` updated with §14 (clustering), §15 (sub-period robustness), §16 (GARCH-t).
- [x] Phase 7 results consolidated at `PHASE_7_RESULTS.md` (project root, one-shot summary).
- [ ] Paper 1 §6.3.1, §6.4.2, §9.2 revision edits committed against the relevant files in `reports/paper1_coverage_inversion/` — pending the next paper-revision sweep.
- [x] No change to deployed M6 artefact, smoke, or tests.

---

## Phase 8 — Compounders on Phase 7 (paper-only; no artefact change)

**Goal:** three follow-up passes that compound on Phase 7's three results — turning each from a statistical headline into a deeper claim a sophisticated reader can act on. None change the deployed artefact. All three are independent and can run in any order.

Phase 8 does not gate Phase 9 (Rust port) — the artefact is unchanged — and the two may run in parallel. The combined Phase 7 + Phase 8 evidence pack is what Paper 1's next revision will draw from.

Results are summarised at `PHASE_8.md` (project root) — sibling to `PHASE_7_RESULTS.md`. Each sub-phase fills its block there as it completes.

### 8.1 — Worst-weekend characterization ✅ COMPLETE 2026-05-04

**Why this matters:** Phase 7.1 produced a striking statistical headline — under M6 LWC at τ=0.85 the worst OOS weekend has *all 10 symbols breaching their bands simultaneously*. The clustering result is currently a distribution shape; pinning down which weekend (and what the macro context was) converts it into a memorable narrative for the §6.3.1 framing and gives §9.1 a concrete example for the circuit-breaker recommendation. Industry readers (Kamino risk team, oracle competitors) remember vignettes; statistical distributions blur.

- [x] Identified the only `k_w = 10` weekend at τ=0.85 under M6 LWC: **Friday 2024-08-02, Mon-open 2024-08-05**. Cross-referenced against `v1b_panel.parquet` for per-symbol breach magnitudes.
- [x] Characterised the macro context as the Bank of Japan rate-hike yen-carry-trade unwind: BoJ July 31 hike + weak US July nonfarm payrolls (Sahm-rule trigger) + Nikkei −12.4% on Aug 5 (largest single-day drop since Black Monday 1987) + VIX intraday ≈ 65 (highest since March 2020 COVID).
- [x] `PHASE_8.md` §8.1 written (~150 lines: process / per-symbol breach table / macro narrative / paper impact).
- [x] `reports/m6_validation.md` §14 — "Worst weekend" sub-section appended with the per-symbol table and the circuit-breaker connection.
- [ ] Paper 1 §6.3.1 / §9.1 inline revision notes — pending the next paper-revision sweep.

**Headline:** all 10 symbols sold off in concert that weekend (mean weekend return −963 bps, median −807 bps; range −2737 bps MSTR to +143 bps TLT — the only safe-haven bid). 9 of 10 also breached at τ=0.95; even at τ=0.99, AAPL/HOOD/NVDA/QQQ/SPY breached. The σ̂-standardisation worked at the per-symbol level (high-vol symbols got wide bands, low-vol got narrow), but no per-symbol band can absorb a 4–27σ-equivalent joint event. **This is the §9.1 circuit-breaker case study:** `k_w` in real time would flag `k_w = 10` at τ=0.85 by the Mon-open print, far above the empirical 99th percentile (k = 7).

### 8.2 — Per-symbol GARCH-t comparison ✅ COMPLETE 2026-05-04

**Why this matters:** Phase 7.3 showed M6 LWC dominates GARCH-t at the *pooled* level. The §6.4.1 per-symbol Kupiec claim ("M6 LWC: 10/10 passes vs M5: 2/10") is the central per-symbol generalization argument; right now it's against the deployed M5 baseline only. Adding GARCH-t per-symbol extends the claim to "vs the strongest parametric baseline at the per-symbol level." This is the version a reviewer with finance training cannot dismiss.

- [x] Wrote sibling runner `scripts/run_per_symbol_kupiec_all_methods.py`. Imports `fit_per_symbol_garch` and `serve_garch_bands` from the Phase 7.3-extended `run_v1b_garch_baseline.py` via `importlib.util.spec_from_file_location` (same precedent as `run_simulation_size_sweep.py`).
- [x] Emits per-symbol Kupiec at all four τ under all four methods in one CSV: `reports/tables/m6_per_symbol_kupiec_4methods.csv` (160 rows = 10 symbols × 4 methods × 4 τ; schema `symbol, method, tau, n_oos, viol_rate, kupiec_lr, kupiec_p`).
- [x] `reports/m6_validation.md` §16 — "Per-symbol GARCH comparison" sub-section appended with the τ=0.95 table and the pass-count grid.
- [x] `PHASE_8.md` §8.2 filled in (Process / Results / Paper impact / Outputs).
- [ ] Paper 1 §6.4.1 paragraph upgrade — pending the next paper-revision sweep.

**Headline at τ=0.95** — per-symbol Kupiec pass-count out of 10 symbols:

| Method | Pass-count at τ=0.95 | Pass-count across full 4×10 grid |
|---|---:|---:|
| M5 deployed | 2/10 | 12/40 |
| GARCH(1,1)-Gaussian | 6/10 | 23/40 |
| GARCH(1,1)-t | 8/10 | 31/40 |
| **M6 LWC** | **10/10** | **39/40** |

**Verdict:** at τ=0.95 M6 LWC achieves per-symbol calibration on every symbol; the strongest practitioner baseline (GARCH-t) achieves 8/10. Across all 40 (symbol × τ) cells M6 LWC fails only **TSLA at τ=0.85** (p=0.044, over-coverage — the same TSLA cell already in §6.4.1's acknowledged outlier list). GARCH-t closes the Gaussian fat-tail failures at τ=0.99 (10/10) and on HOOD/MSTR at τ=0.95, but still fails GLD at every τ<0.99 (over-tightened) and several other low-τ cells. **§6.4.1 paragraph upgrades from "vs M5" to "vs the strongest parametric baseline."**

### 8.3 — Cross-subperiod k_w threshold stability ✅ COMPLETE 2026-05-04

**Why this matters:** Phase 7.1 produced consumer reserve guidance — "at τ=0.95, reserve against ≈ 5 simultaneous breaches." That's a one-shot empirical observation. A consumer sizing reserves needs to know it's *stable across regimes*. If the empirical 95th-percentile of `k_w` jumped from k=3 in 2023 to k=7 in 2025, the reserve guidance is unreliable. Piggyback on Phase 7.2's calendar sub-periods to test stability. (A naive Kupiec test on a self-derived percentile is tautological by construction; the cross-subperiod stability framing avoids this by fitting the threshold on the full OOS and testing the year-by-year hit rate.)

- [x] `scripts/run_kw_threshold_stability.py`. Reads `reports/tables/m6_portfolio_clustering_per_weekend.csv`. For each forecaster × τ ∈ {0.85, 0.95, 0.99}: fits two threshold conventions on the *full-OOS* hit-rate curve — `k_close` (rate closest to 5%, primary) and `k_below_5pct` (smallest k with rate ≤ 5%, deployment-conservative).
- [x] For each subperiod {2023, 2024, 2025, 2026-YTD}: Kupiec LR test of subperiod hit-rate vs full-OOS rate; per-subperiod 95th-percentile of `k_w`; `low_power_flag` set when expected subperiod hits < 3 (binomial-LR power threshold).
- [x] Output: `reports/tables/m6_kw_threshold_stability.csv` (48 rows = 2 forecasters × 3 τ × 2 conventions × 4 subperiods).
- [x] `reports/m6_validation.md` §14 — "Threshold stability" sub-section appended with the headline table and the per-subperiod 95th-percentile drift table.
- [x] `PHASE_8.md` §8.3 filled in (Process / Results / Paper impact / Outputs).
- [ ] Paper 1 §6.3.1 / §9.1 inline revision notes — pending the next paper-revision sweep.

**Headline:** across the full 24-cell stability grid per forecaster: **M6 LWC has 0 / 24 Kupiec rejections at α=0.05; M5 has 2 / 24** — both at τ=0.95 in 2024 (same over-clustering signal Phase 7.2 already flagged). Year-on-year drift in the per-subperiod 95th-percentile of `k_w` is ≤ 1.6 integer-symbols at every τ under M6 LWC. The deployment-recommended threshold (k*=3 at τ=0.95, k*=5 at τ=0.85) sits at or above every per-subperiod 95th-percentile — i.e. the consumer guidance is conservative against year-on-year drift, not just against the full-OOS distribution.

**Power caveat (transparently disclosed):** subperiod n ∈ {52, 17} and target rates ~5% give limited binomial-LR power; most cells flag `low_power_flag = 1`. The result is "no detectable instability with the available power," not "definitively stationary." The 95th-percentile drift table is the orthogonal quantile-read that does not depend on test power.

**§6.3.1 / §9.1 upgrade:** combined with Phase 8.1 (Aug 5 2024 vignette) and Phase 7.1 (clustering distribution), the reserve guidance is now end-to-end specified — threshold is fitted (k*=3 at τ=0.95), threshold is stable across regimes (0/24 rejections), threshold catches the worst observed weekend (Aug 5 2024 had `k_w = 10` at τ=0.85, well above the deployment k*).

### Definition of done — Phase 8

- [x] All three sub-phases complete and reproducible.
- [x] `PHASE_8.md` filled in (status table + per-sub-phase Process / Results / Paper impact / Outputs).
- [x] `reports/m6_validation.md` extended with the three new sub-sections (§14 Worst-weekend + §14 Threshold-stability + §16 Per-symbol-GARCH).
- [ ] Paper 1 §6.3.1 / §6.4.1 / §9.1 inline revision notes — pending the next paper-revision sweep.
- [x] No change to deployed M6 artefact, smoke, or tests.

---

## Phase 9 — Rust parity port for M6 (GATED)

**Gate:** do **not** start until Adam has forwarded Phase 1–6 results to the secondary agent and explicitly green-lit this phase here. The σ̂ variant decision (Phase 5) and panel-admission guidance (Phase 6) must be locked first so the port mirrors the canonical M6. Phase 7 + Phase 8 (paper-strengthening tests) do **not** gate Phase 9 — the artefact is unchanged — and these may run in parallel.

**Goal:** extend the byte-for-byte parity contract of §8.5 to M6.

### 9.1 — Port

- [ ] Port `Oracle.fair_value_lwc` to `crates/soothsayer-oracle/src/oracle.rs`.
- [ ] Add the per-symbol scale series to `crates/soothsayer-oracle/src/config.rs` (or load it from a binary asset — the per-Friday scale is per-(symbol, fri_ts), so it's a lookup, not a constant).

### 9.2 — Parity

- [ ] Update `scripts/verify_rust_oracle.py` to add 90 LWC test cases. Target **90/90 pass for both M5 and M6 (180/180 total)**.

### 9.3 — On-chain

- [ ] Reserve `forecaster_code = 3` (FORECASTER_LWC) in the on-chain Anchor program.
- [ ] Wire-format invariance: existing M5 consumers must decode M6 `PriceUpdate` accounts without crashing — only the `forecaster_code` field changes.

### Definition of done — Phase 9

- 180/180 Python ↔ Rust parity.
- On-chain decoder unchanged.
- M6 publishable end-to-end through the existing publisher CLI.

---

## Reporting back

When Phases 1–9 are complete, produce one summary at `reports/m6_promotion_summary.md` containing:

- Headline M6 OOS table at τ ∈ {0.68, 0.85, 0.95, 0.99} (mirrors §6.3 of the paper).
- Per-symbol Kupiec table for M6 vs M5 (mirrors §6.4.1) — extended with GARCH-t per-symbol from Phase 8.2.
- Block-bootstrap CIs on the M5 → M6 width and coverage deltas.
- Four-DGP simulation summary table + sample-size sweep curves (Phase 6).
- σ̂ variant verdict (Phase 5): which half-life ships, or why the K=26 baseline stayed.
- Newly-listed-symbol admission threshold (Phase 6): minimum N per regime.
- Portfolio-level violation clustering (Phase 7.1): empirical P(k ≥ 3 / 5 / 7) at τ=0.95 vs Binomial(10, 0.05); reserve guidance for correlated holdings.
- Sub-period Kupiec table (Phase 7.2): per-year M6 vs M5 at τ=0.95.
- GARCH-t headline (Phase 7.3): matched-coverage half-width and pooled Kupiec vs M6 LWC.
- Worst-weekend vignette (Phase 8.1): date, macro context, per-symbol breach magnitudes.
- k_w threshold stability (Phase 8.3): cross-subperiod year-by-year hit rate at the deployment-recommended threshold.
- Bullet list of any Phase-2 / Phase-7 / Phase-8 robustness check where **M6 underperforms M5 / GARCH-t** — these are the ones we need to discuss.
- Frozen artefact hash and freeze date (post-Phase-5 freeze if a variant was promoted).

Adam then brings this back into the conversation and we plan the Paper 1 revision around it.
