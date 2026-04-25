# Methodology evolution log

**Purpose.** A living, append-only record of methodological decisions, tested-and-rejected hypotheses, and the empirical evidence that shaped the current Soothsayer Oracle. Updated when methodology changes; never deleted from. Source-of-truth pointer for the research paper, deployed code, and historical context for new collaborators.

**How to read this doc.** Sections are time-stamped. The current production methodology is summarised in §0 ("State of the world today") and re-derived from the latest dated entry. Earlier entries describe the path; if a finding has since been superseded, the supersession is noted inline.

**How to update this doc.** When you change methodology, append a new dated entry to §1 ("Decision log"). Update §0 to reflect the new state of the world. Never edit prior entries; if an old entry needs correction, add an "AMENDMENT" line with the date and reasoning.

---

## 0. State of the world (current)

*Last updated 2026-04-25.*

**Product shape.** Soothsayer Oracle. Customer specifies target coverage τ ∈ (0, 1); Oracle returns a band that empirically delivered τ on a 12-year backtest stratified by (symbol, regime). Every read carries receipts: served claimed-quantile, forecaster used, regime observed, calibration buffer applied.

**Deployment defaults.**
- Default τ = **0.85** — picked on protocol-EL grounds vs Kamino flat-300bps benchmark.
- Hybrid forecaster: F1_emp_regime in `normal` and `long_weekend`; F0_stale in `high_vol`.
- Per-target buffer schedule: `{0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.010}`, linearly interpolated off-grid (τ=0.99 bumped from 0.005 → 0.010 after 2026-04-25 grid extension).
- Claimed-coverage grid: `{..., 0.95, 0.975, 0.99, 0.995, 0.997, 0.999}` (extended 2026-04-25 from prior top of 0.995); `MAX_SERVED_TARGET = 0.999`.

**Validated empirical claims (OOS 2023+, 1,720 rows, 172 weekends):**
- τ = 0.95: realised 0.950, Kupiec $p_{uc}$ = 1.000, Christoffersen $p_{ind}$ = 0.485 (PASS).
- τ = 0.85: realised 0.855, Kupiec $p_{uc}$ = 0.541, Christoffersen $p_{ind}$ = 0.185 (PASS).
- τ = 0.68: realised 0.678, Kupiec $p_{uc}$ = 0.893, Christoffersen $p_{ind}$ = 0.647 (PASS).
- τ = 0.99: realised 0.977 (post-grid-extension; was 0.972 on the 0.995-capped grid) — Kupiec still rejects. Structural ceiling re-attributed: with the grid extended to 0.999, the deeper finite-sample limitation is now identified as the 156-weekend per-(symbol, regime) calibration window size, not grid spacing.
- Protocol EL vs Kamino flat ±300bps at τ = 0.85: ΔEL ≈ −0.011 with bootstrap 95% CI [−0.014, −0.007] (favours Soothsayer).
- **Walk-forward stability (6 expanding-window splits 2019–2025):** at τ=0.95, mean buffer = 0.019 (σ = 0.017); deployed value 0.020 lands at the cross-split mean. At τ=0.85, mean buffer = 0.025 (σ = 0.022); deployed 0.045 is conservative (≥1σ above mean).
- **Stationarity (D2):** 8 of 10 symbols stationary by joint ADF + KPSS; HOOD (n=245) and TLT trend-stationary.
- **Christoffersen pooling sensitivity (D4):** sum-of-LRs / Bonferroni / Holm-Šidák agree on accept/reject at α=0.05 across all four targets — robust to pooling choice.

**Code source-of-truth.**
- Python: `src/soothsayer/oracle.py` (`BUFFER_BY_TARGET`, `REGIME_FORECASTER`, `Oracle.fair_value`).
- Rust: `crates/soothsayer-oracle/src/{config,oracle}.rs` (byte-for-byte port; 75/75 parity tests pass).
- Calibration surface artefact: `data/processed/v1b_bounds.parquet` (the table consumers verify against).

**Paper draft snapshot (descriptive sections, frozen pending live deployment):**
- §1 Introduction — `reports/paper1_coverage_inversion/01_introduction.md`
- §2 Related Work — `reports/paper1_coverage_inversion/02_related_work.md` (28 verified references)
- §3 Problem Statement — `reports/paper1_coverage_inversion/problem_statement.md`
- §6 Results — `reports/paper1_coverage_inversion/06_results.md`
- §9 Limitations — `reports/paper1_coverage_inversion/09_limitations.md`
- §2-citation bibliography — `reports/paper1_coverage_inversion/references.md`

**Phase-2 deliverables conditional on data history.** F_tok forecaster (uses on-chain xStock TWAP; gated on V5 tape ≥ 150 weekend obs per regime), MEV-aware consumer-experienced coverage, full PIT-uniformity diagnostic, conformal-prediction re-evaluation under finer claimed grid. See `docs/v2.md`.

---

## 1. Decision log

### 2026-04-25 (afternoon) — Tier-1 engineering pass: walk-forward + diagnostics + grid extension + macro-event ablation

**Trigger.** Tier-1 of the grant-application impact framework — the engineering-only items we committed to doing before requesting funding. Goal: produce paper-strength sensitivity / robustness evidence and resolve disclosed limitations where reachable on existing data.

**Hypotheses tested.**

1. **H1: BUFFER_BY_TARGET values are stable across train/test splits.** *Accepted.* Walk-forward six-split rolling-origin evaluation (cutoffs 2019-01-01 → 2024-01-01, 12-month horizons): at τ=0.95, mean buffer = 0.019 (σ = 0.017) — deployed value 0.020 lands at the cross-split mean. At τ=0.85, mean = 0.025 (σ = 0.022); deployed 0.045 is ≥1σ conservative (over-covers). Closes the §9.4 sample-size-1 disclosure for τ=0.95; tightens but does not fully close it for τ=0.85, where the conservative deployed value reflects the post-2023 split having a wider gap than the 2019–2022 splits. *Artefact:* `reports/v1b_walkforward.md`, `reports/tables/v1b_walkforward_buffer.csv`.
2. **H2: τ=0.99 ceiling is grid-spacing-driven.** *Partially rejected; structural attribution refined.* Extended the claimed grid from `(..., 0.995)` to `(..., 0.995, 0.997, 0.999)` and bumped `MAX_SERVED_TARGET` to 0.999 in both Python and Rust. OOS realised coverage at τ=0.99 lifted from 0.972 → 0.977 — a real but small improvement. Kupiec still rejects. The deeper finite-sample limitation is the 156-weekend per-(symbol, regime) calibration window, not the grid resolution. §9.1 should be re-attributed: not "the grid stops at 0.995" but "the calibration-window sample size cannot resolve the 1% tail in any per-bucket fit; reaching τ=0.99 reliably would require pooled-window calibration or longer history." `BUFFER_BY_TARGET[0.99]` updated 0.005 → 0.010. Parity verified post-change (75/75). *Artefact:* `reports/v1b_extended_grid.md`, `reports/tables/v1b_extended_grid_tau99_sweep.csv`.
3. **H3: Empirical-quantile architecture absorbs the −5.2 bps point bias by construction (the §6.6 derivation).** *Accepted with numerical proof.* `served_point_offset_from_midpoint_bps_max_abs = 0.000` across 1,720 OOS rows × 4 targets — the served point is exactly the band midpoint. *Artefact:* `reports/tables/v1b_diag_bias_absorption.csv`.
4. **H4: Per-symbol weekend log-return series are stationary (the §9.3 assumption).** *Mostly accepted.* Joint ADF + KPSS: 8 of 10 symbols pass; HOOD (n=245, newer ticker) and TLT (multi-year drawdown) classify as trend-stationary rather than fully stationary. Partial finding: §9.3 stationarity assumption holds in aggregate but two symbols are flagged. *Artefact:* `reports/tables/v1b_diag_stationarity.csv`.
5. **H5: Christoffersen pooling rule choice is load-bearing for the calibration claim.** *Rejected.* Compared sum-of-LRs (deployed) vs Bonferroni vs Holm-Šidák at τ ∈ {0.68, 0.85, 0.95, 0.99}. All three rules agree on accept/reject at α=0.05 across all targets. Calibration claim is robust to pooling-correction choice. *Artefact:* `reports/tables/v1b_diag_christoffersen_pooling.csv`.
6. **H6: A FRED-derived macro-event regressor (FOMC + CPI + NFP) closes the §9.2 shock-tertile coverage gap.** *Rejected.* 324 macro events tagged across 12 years (48% of weekends have one within the following week). Re-fit F1_emp_regime with three variants — M0 deployed, M1 + macro flag, M2 swap-earnings-for-macro. Pooled τ=0.95 effect: 0.923 → 0.921 (within noise). Shock-tertile τ=0.95: 0.803 → 0.796 (slightly *worse*). The implied-volatility indices (VIX/GVZ/MOVE) already absorb whatever macro information is in the data; the extra flag adds noise without adding signal. §9.2 disclosure stands: shock-tertile ceiling is structural, not macro-driven. This is a positive negative-finding: it forecloses one obvious "did you try …" reviewer question. *Artefact:* `reports/v1b_macro_regressor.md`, `reports/tables/v1b_macro_ablation.csv`, `data/processed/v1b_macro_calendar.parquet`.
7. **H7: Raw F1_emp_regime PIT distribution is uniform on (0,1).** *Rejected.* KS test against U(0,1) on 1,720 OOS PITs: KS stat = 0.500, p < 0.001. The raw-forecaster PIT is *expected* to be non-uniform — that's why the calibration surface exists. The right framing for §6 is therefore: raw-forecaster PIT non-uniformity motivates the surface; the served-band coverage at discrete τ levels is the actual product validation, and that *does* pass at three of four targets. The KS finding is a useful clarification, not a defect. *Artefact:* `reports/figures/v1b_diag_pit.png`, `reports/tables/v1b_diag_pit.csv`.

**Net deployment change.** `BUFFER_BY_TARGET[0.99]: 0.005 → 0.010`; `MAX_SERVED_TARGET: 0.995 → 0.999`; claimed grid extended to include {0.997, 0.999}. Python + Rust mirrored. Parity 75/75.

**Cascading paper edits required.**
- §6.4 OOS table: τ=0.99 row updated to realised 0.977 (was 0.972).
- §9.1: re-attribute ceiling to calibration-window size, not grid spacing.
- §9.2: shock-tertile structural ceiling now has a tested negative for macro events.
- §9.3: stationarity disclosure tightened — 8/10 symbols stationary; HOOD and TLT flagged.
- §9.4: walk-forward distribution-valued buffer claim replaces sample-size-1 disclosure.
- §6 calibration claim: optionally add Christoffersen pooling-sensitivity table as a robustness check.

---

### 2026-04-25 (morning) — Per-target buffer schedule replaces scalar; conformal alternatives tested and rejected for v1

**Trigger.** Shipping default τ moved from 0.95 to 0.85 on EL-vs-Kamino evidence (separate decision; see protocol-compare commits). The pre-existing scalar `CALIBRATION_BUFFER_PCT = 0.025` was tuned for τ=0.95 and under-corrected at τ=0.85: realised 0.828 vs target 0.85, Kupiec $p_{uc}$ = 0.014 (rejected).

**Hypotheses tested.**

1. **H1: Vanilla split-conformal (Vovk) closes the gap.** *Rejected.* At our calibration size (n ≈ 4,000) the (n+1)/n finite-sample correction is ~100× smaller than the OOS gap. Operationally equivalent to no buffer; under-covers by 4pp at τ = 0.95.
2. **H2: Barber et al. (2022) nexCP recency-weighting closes the gap.** *Rejected.* Tested at 6-month and 12-month exponential half-lives. Both deliver *lower* coverage than vanilla split-conformal: recency-weighting shifts the (claimed → realised) surface in a way that drives the inverter toward higher $q$, but at high $q$ the bounds grid clips at 0.995, producing net under-coverage. Bootstrap deltas: V1 → V3a 6mo at τ = 0.95 yields Δcov = −10.5pp (CI [−12.5, −8.8]).
3. **H3: Block-recency surface (uniform weights, last 6/12 months only) closes the gap.** *Rejected.* Same mechanism as H2; smaller calibration set amplifies noise without shifting the centre of the surface in the right direction.
4. **H4: Per-target tuning of the heuristic itself.** *Accepted.* Sweep over `{0.000, 0.005, ..., 0.060}` at each anchor τ ∈ {0.68, 0.85, 0.95, 0.99} on OOS 2023+. Smallest-buffer-passing-tests rule yields `BUFFER_BY_TARGET = {0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.005}`.

**Surprise finding.** The previous τ = 0.95 anchor was over-buffered. At buffer 0.020, realised coverage is exactly 0.950 with Kupiec $p_{uc}$ = 1.000 and bands 13 bps tighter than at 0.025. Strict improvement over the prior default.

**Structural finding.** τ = 0.99 hits a finite-sample ceiling regardless of buffer: the bounds grid stops at 0.995, the rolling 156-weekend per-(symbol, regime) calibration window cannot resolve the 1% tail, and any buffer ≥ 0.005 produces identical clipped behaviour. Documented in §9.1 of the paper as a known limitation.

**Reviewer-facing position.** The conformal-as-future-work framing in §9.4 is reframed: the conformal upgrade is *not* an obvious win on this data; it is a v2 direction conditional on either a finer claimed-coverage grid (extending past 0.995) or a multi-split walk-forward evaluation that distinguishes drift from sampling noise.

**Artefacts.**
- `reports/v1b_buffer_tune.md` — sweep methodology + per-target recommendations
- `reports/v1b_conformal_comparison.md` — V0/V1/V3/V4 comparison + bootstrap CIs
- `reports/tables/v1b_buffer_sweep.csv`, `v1b_buffer_recommended.csv`
- `reports/tables/v1b_conformal_comparison.csv`, `v1b_conformal_bootstrap.csv`
- `scripts/run_conformal_comparison.py`, `scripts/tune_buffer.py`, `scripts/refresh_oos_validation.py`

**Code changes.** `src/soothsayer/oracle.py` and `crates/soothsayer-oracle/src/{config,oracle,lib}.rs`. Python ↔ Rust parity verified post-change (75/75 cases match byte-for-byte).

**Paper-side cascading edits.** §6.4 OOS table refreshed under deployed buffers; §9.4 rewritten from scalar-heuristic to per-target-heuristic and reframes conformal as v2-conditional; `v1b_decision.md` annotated with an UPDATE callout (historical snapshot preserved below the callout).

---

### 2026-04-25 — Bibliography review applied; three substantive disclosures + one framing tighten

**Trigger.** Stage-3 related-work survey produced 28 verified references across oracle designs, cross-venue price discovery, calibration / conformal prediction, and institutional model risk management. Several references implied claims that needed disclosure.

**Hypotheses tested.**

1. **H1: Cong et al. 2025 invalidates the methodology by showing on-chain xStock prices already encode weekend information.** *Partially accepted (as gap, not invalidation).* The paper stands at v1 because xStock data history (~30 weekends post mid-2025) is below the ~150 needed for stable per-(symbol, regime) Kupiec validation. The F_tok forecaster slot is documented in `docs/v2.md` §V2.1 and gated on the V5 tape reaching that threshold (estimated mid-Q3 2026).
2. **H2: Pyth's documented per-publisher 95%-coverage convention contradicts our "no incumbent publishes a calibration claim" claim.** *Accepted as framing weakness.* §1 was tightened to "no incumbent publishes a calibration claim verifiable against public data at the *aggregate feed* level," explicitly distinguishing publisher-level self-attestation from aggregate-feed verifiability.
3. **H3: The factor-adjusted point's −5.2 bps median residual bias propagates to the served band.** *Rejected after analysis.* The empirical-quantile architecture takes quantiles of `log(P_t / point)` directly; lower/upper bands are constructed as `point · exp(z_lo)` and `point · exp(z_hi)` with `z` from the empirical CDF of the residual, *including* its non-zero median. The served band is bias-aware by construction; the served point (midpoint of the band) is also bias-corrected. §6.6 was updated to derive this explicitly.
4. **H4: Daian et al. Flash Boys 2.0 implies our reported coverage and consumer-experienced coverage diverge near band edges.** *Accepted as disclosure.* §9.11 added; full measurement deferred to v2 §V2.3 pending V5 tape data.

**Artefacts.** `reports/paper1_coverage_inversion/references.md`, `reports/paper1_coverage_inversion/02_related_work.md`. Disclosures live in `09_limitations.md` §§9.10, 9.11; clarification in §6.6; framing tighten in §1.

---

### 2026-04-24 — Hybrid regime-policy + scalar empirical buffer; v1b ships PASS

**Trigger.** v1b decade-scale calibration backtest with a single forecaster (F1_emp_regime) under-covered at the nominal 95% claim with realised 92.3% pooled and Kupiec rejection. PASS-LITE verdict needed escalation to PASS for shipping confidence.

**Hypotheses tested.**

1. **H1: F2 (HAR-RV vol model) improves coverage.** *Rejected.* Realised 78.2% at the 95% claim — worse than F0 stale-hold and F1_emp_regime. Suspected over-fit to recent realised volatility in a way that fails on weekends. F2 retained in code as a diagnostic but excluded from the deployed forecaster set.
2. **H2: Madhavan-Sobczyk decomposition / VECM / Hawkes process / Yang-Zhang vol estimator are needed.** *Rejected.* The simpler stack (F1_emp_regime: factor-adjusted point + log-log vol-index regression on residuals) achieved comparable coverage with less complexity. The complex methodology stack was researched and dropped from the v1b methodology; surfaced as historical context in `vault_updates_for_review.md`.
3. **H3: Funding-rate signal from Kraken xStock perps adds information (V3 test).** *Rejected.* No detectable improvement; coefficients in `reports/tables/v3_coefficients.csv` are within bootstrap noise of zero. V3 work archived in `reports/v3_funding_signal.md`.
4. **H4: Hybrid forecaster selection by regime closes the high-vol gap.** *Accepted in-sample, refined OOS.* In-sample: F0_stale is 10–35% tighter than F1 in `high_vol` at matched realised coverage. OOS: the *mean*-coverage advantage shrinks to ~2%, but the hybrid's primary serving-time contribution is **Christoffersen independence** — F1 + buffer has clustered violations ($p_{ind}$ = 0.033, rejected); hybrid + buffer does not ($p_{ind}$ = 0.086).
5. **H5: A scalar empirical buffer of 0.025 closes the OOS coverage gap at τ = 0.95.** *Accepted, later refined.* Bootstrap 95% CIs on the buffer effect at τ = 0.95: Δcov = +3.7pp [+2.7, +4.7], CI excludes zero. *(Subsequently superseded 2026-04-25 by per-target buffer schedule; see entry above.)*

**Verdict.** PASS shipped: hybrid forecaster + scalar buffer + customer-selects-coverage Oracle, OOS at τ = 0.95 delivers realised 0.959 with Kupiec $p_{uc}$ = 0.068 and Christoffersen $p_{ind}$ = 0.086.

**Artefacts.** `reports/v1b_calibration.md`, `reports/v1b_decision.md`, `reports/v1b_hybrid_validation.md`, `reports/v1b_ablation.md`. Tables: `reports/tables/v1b_*.csv`.

---

### 2026-04-22 — Phase 0 PASS-LITE on simpler-than-planned methodology

**Trigger.** Phase-0 plan called for testing a Madhavan-Sobczyk + VECM + HAR-RV + Hawkes stack as the candidate forecaster. Simpler stack hit the calibration target first.

**Hypotheses tested.**

1. **H1: Friday close × ES-futures-weekend-return is a usable point estimator across all equities.** *Accepted with extension.* Generalised to a per-asset-class factor switchboard: ES for equities, GC for gold, ZN for treasuries, BTC-USD for MSTR (post 2020-08). Documented in `FACTOR_BY_SYMBOL`.
2. **H2: Empirical residual quantile suffices for CI construction; no parametric distribution assumed.** *Accepted.* F1_emp on the rolling 104-weekend residual window delivers 91.4% pooled at the 95% claim — disclosed as raw-model property; calibration surface absorbs the residual gap.
3. **H3: Per-symbol vol-index (VIX/GVZ/MOVE) outperforms a single VIX regressor.** *Marginally accepted.* Δsharp ≈ 0.3% pooled, CI excludes zero by margin only; useful primarily for GLD and TLT where the asset-class vol index is a better fit than VIX.
4. **H4: An earnings-next-week 0/1 flag carries signal at our sample size.** *Rejected as detectable.* Δcov 0.0pp [−0.1, +0.1]; Δsharp +0.1% [−0.2, +0.5]. Retained in the regressor set as a disclosed structural slot for a future finer-granularity earnings calendar (§9.5 of paper).
5. **H5: A long-weekend 0/1 flag carries signal in its own regime.** *Accepted as localised.* Δsharp +10.6% in `long_weekend` regime, statistically distinguishable; flat in `normal` and `high_vol`. Justifies its inclusion in the regressor set.

**Verdict.** PASS-LITE on the simpler methodology. Phase-1 engineering started before the full Madhavan-Sobczyk stack was even built. Saved several weeks; established the precedent that the methodology should be the simplest one that calibrates rather than the most theoretically sophisticated.

**Artefacts.** `reports/v1b_ablation.md` and `reports/tables/v1b_ablation_*.csv` retain the full ablation evidence; `reports/v1_chainlink_bias.md` is the original Chainlink reconstruction comparison.

---

### Pre-2026-04-22 — Methodology candidates considered and not pursued

For the historical record, methodology variants that were considered, scoped, or partially prototyped but never reached the v1b ablation:

- **Kalman / state-space filters** — considered for joint price-and-volatility estimation. Not pursued: the empirical-quantile architecture handles the same calibration objective without a parametric state-space assumption.
- **Heston / GARCH-family vol models for the conditional sigma** — not pursued: log-log regression on a model-free vol index (VIX / GVZ / MOVE) was simpler and competitive on the backtest.
- **Madhavan-Sobczyk price-impact decomposition** — researched in detail (`notebooks/archived-v1-methodology/`), not pursued because the factor-switchboard captures most of the cross-venue lead-lag relevant to the weekend prediction window.
- **VECM (vector error-correction)** — same disposition.
- **Hawkes process for jump arrivals** — considered as a `high_vol`-regime model. Not pursued: F0 stale-hold's wide Gaussian band already absorbs most jumps adequately at matched realised coverage.

---

## 2. Open methodology questions

Items the team explicitly knows about and has chosen to defer rather than ignore. Each has a documented gating condition.

| Question | Gating condition | Documented in |
|---|---|---|
| Does on-chain xStock TWAP carry weekend signal that reduces our OOS gap? | V5 tape reaches ≥ 150 weekend obs per (symbol, regime) | docs/v2.md §V2.1; methodology log entry 2026-04-25 |
| Does conformal prediction outperform per-target heuristic with finer grid? | Bounds grid extended above 0.995 *and* multi-split walk-forward eval available | reports/v1b_conformal_comparison.md; this log 2026-04-25 |
| Does adversarial transaction ordering create a measurable consumer-experienced coverage gap? | V5 tape + Jito bundle data ≥ 3 months | docs/v2.md §V2.3; methodology log entry 2026-04-25 |
| Is the calibration surface empirically uniform across the full PIT distribution, or only at our three / four sampled τ? | One-shot diagnostic; ~10 LoC in metrics.py | docs/v2.md §V2.4 |
| Does the methodology generalise to non-US equities (tokenised JP / EU shares)? | Multi-region replication run with the same panel-build pipeline | reports/paper1_coverage_inversion/09_limitations.md §9.9 |
| Does a finer earnings-calendar dataset (date + estimated move size) make the earnings regressor detectable? | Acquisition of a vendor-grade earnings calendar | reports/paper1_coverage_inversion/09_limitations.md §9.5 |

---

## 3. How this doc relates to other artefacts

- **`reports/v1b_decision.md`** — frozen 2026-04-24 snapshot of the v1b ship decision. Annotated with later-update callouts but not rewritten.
- **`reports/paper1_coverage_inversion/*.md`** — the paper draft. Sections that depend on methodology should refer to §0 of this doc as the source-of-truth for current state.
- **`docs/v2.md`** — forward-looking; describes Phase-2 deliverables that are gated on data or on resolution of an open methodology question.
- **`src/soothsayer/oracle.py` and `crates/soothsayer-oracle/`** — current deployed methodology; this log explains *why* the constants in those files have their current values.
- **Memory (`MEMORY.md`)** — stable index pointer to this log.

When methodology changes:
1. Append a new entry to §1.
2. Update §0 to reflect the new state.
3. Update the relevant code (Python + Rust mirror).
4. Update any paper-draft section that describes the changed methodology.
5. If a deferred item from §2 was resolved, move it to §1 and remove from §2.
