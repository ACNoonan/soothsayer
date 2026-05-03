# Validation Backlog — Defensibility Workstreams Beyond M5

**Status:** Living working doc. Created 2026-05-02 after M5 Mondrian validation entry landed.

**Delete this file when:** every workstream below is either (a) executed and folded into `reports/methodology_history.md` as a dated entry with linked artefact, or (b) explicitly rejected with a rationale recorded in the methodology log.

**Source of truth for everything that *sticks*:** `reports/methodology_history.md`. This file is scratch-space for *candidates* to that ledger.

**Source of truth for current state:** `reports/methodology_history.md` §0.

**Sibling working doc:** `M5_REFACTOR.md` (M5 deployment migration; orthogonal to this backlog).

---

## Why this exists

After the 2026-05-02 M5 Mondrian win, the question was: *what other tests should we run to make sure the system is the strongest possible relative to incumbent oracles?* This backlog enumerates those candidates with prioritization, expected effort, gate condition, and a result line that gets filled in as each completes. Each item ends in one of three terminal states:

- **Adopt** — material finding, append a methodology log entry, propagate to papers/code, then strike from this doc.
- **Disclose-not-deploy** — informative result, footnote in Paper 1, no methodology change.
- **Reject** — null/uninformative, log a one-line "considered and dropped" entry in the methodology log so it does not get re-suggested.

---

## Priority ranking (2026-05-02)

1. **W1 — Incumbent oracle band coverage head-to-head.** Highest ROI; data already on disk; directly addresses "compared to incumbents" framing for Colosseum + Paper 1 reviewers. **In flight.**
2. **W2 — Berkowitz / DQ rejection localization.** Both v1 and M5 reject density tests; finding the source could drive a v3 forecaster.
3. **W3 — Regime classifier audit.** M5 makes `regime_pub` load-bearing; classifier robustness now a methodology question, not a feature-engineering choice.
4. **W4 — Asymmetric / one-sided coverage.** Direct empirical input to Paper 3 (P-conf vs P+conf).
5. **W5 — Live forward-tape realized coverage.** Reviewer-immune. Grows over time; cheap to set up.
6. **W6 — Halt-window subset coverage.** Direct numerical complement to Paper 3 §Structural.
7. **W7 — Cross-class Mondrian (class × regime).** Possible M5+ rung; cheap.

---

## W1 — Incumbent oracle band coverage head-to-head

**Status:** In flight (started 2026-05-02). Pyth + Chainlink prior art exists; RedStone + Kamino Scope and the unified head-to-head are the actual gap.

**Question.** What realized coverage τ does each incumbent oracle's *published implicit band* deliver on xStock-relevant symbols during weekend close-to-Monday-open? At what width? How does that compare to Soothsayer v1 (deployed) and M5 (v2 candidate)?

**Prior art (already on disk, do not redo).**

- **Pyth (DONE).** `scripts/pyth_benchmark_comparison.py` reads scryer `pyth/oracle_tape/v1` for 2024+ OOS weekends. Output: `data/processed/pyth_benchmark_oos.parquet`, `reports/tables/pyth_coverage_by_k.csv`, `reports/v1b_pyth_comparison.md`. Headline: 265-obs available subset (SPY/QQQ/TLT/TSLA-heavy), naive `±1.96·conf` realises **0.102** coverage; consumer must scale to `±50·conf` to hit 0.951 at 280 bps mean half-width.
- **Chainlink (DONE).** `scripts/chainlink_implicit_band_analysis.py` works from the frozen 87-obs panel `data/processed/v1_chainlink_vs_monday_open.parquet` (2026-02-06 → 2026-04-17). Output: `reports/tables/chainlink_implicit_band.csv`, `reports/v1b_chainlink_comparison.md`. Headline: bid/ask zeroed during `marketStatus=5` weekends; symmetric `±300 bps` wrap on the stale mid hits 0.943 coverage.

**Sample-window inventory (2026-05-02).**

| Tape | Date range | Symbols | Weekend events available | Implicit band |
|---|---|---|---|---|
| `pyth/oracle_tape/v1` | 2024+ via prior-art runner | 8 underliers | 265 (symbol × weekend) | `pyth_price ± k·pyth_conf` |
| `chainlink/data_streams/v1` (live) | 2026-05-02 → 2026-05-03 | xStock feed_ids | 0 (need more capture) | `[bid, ask]` (zeroed during weekend `marketStatus=5`) |
| `redstone/oracle_tape/v1` | 2026-04-26 → 2026-05-03 | 3 (SPY, QQQ, MSTR) | **2 weekends × 3 = 6** | point-only |
| `kamino_scope/oracle_tape/v1` | 2026-04-26 → 2026-05-03 | 8 (xStocks) | **2 weekends × 8 = 16** | point-only |

The forward-tape sample for RedStone + Kamino Scope is small *and grows over time*. Treat as a baseline that re-runs weekly.

**Protocol (the gap pieces).**

1. **RedStone coverage runner.** New script `scripts/redstone_benchmark_comparison.py`, mirroring the Pyth runner's structure exactly: read scryer `redstone/oracle_tape/v1`, find last pre-Friday-close row per (symbol, fri_ts), sweep `k_pct ∈ {0.5%, 0.75%, 1%, 1.25%, 1.5%, 2%, 2.5%, 3%, 4%, 5%, 7.5%, 10%}` symmetric wrap, compute realized coverage on Yahoo Monday open. Outputs: `data/processed/redstone_benchmark_oos.parquet`, `reports/tables/redstone_coverage_by_k_pct.csv`, `reports/v1b_redstone_comparison.md`.
2. **Kamino Scope coverage runner.** New script `scripts/kamino_scope_benchmark_comparison.py`, same pattern, with xStock→underlier symbol mapping (strip the `x` suffix) so the truth column joins cleanly to Yahoo `equities_daily`. Outputs: parallel naming.
3. **Unified head-to-head.** New script `scripts/run_incumbent_oracle_unified_report.py` reads the four per-oracle CSVs and `data/processed/v1b_bounds.parquet`, builds one head-to-head table at matched coverage τ ∈ {0.68, 0.85, 0.95}: width per oracle, restricted to the intersection panel where each oracle has data. Outputs: `reports/tables/incumbent_oracle_unified_summary.csv`, `reports/v1b_incumbent_oracle_comparison.md`.
4. **Sample-size disclosure.** Every output explicitly states n per oracle and notes that RedStone + Kamino Scope numbers are forward-tape baselines that should be re-run as the tape grows.

**Headline question.** *Is there an incumbent oracle that delivers ≥0.85 realized coverage at narrower-than-Soothsayer width on the matched-panel intersection? Does Soothsayer's calibrated band beat point-only oracles across the τ grid?*

If yes → finding the Colosseum pitch + Paper 1 must address head-on. If no (expected) → the asymmetric width chart is the killer comparison artefact: "incumbents either don't publish a band, under-cover at any reasonable width, or require consumer-supplied calibration that costs more than reading Soothsayer's."

**Deliverables.**

- [x] Pyth: prior art (`pyth_benchmark_comparison.py`, `pyth_coverage_by_k.csv`, `v1b_pyth_comparison.md`)
- [x] Chainlink: prior art (`chainlink_implicit_band_analysis.py`, `chainlink_implicit_band.csv`, `v1b_chainlink_comparison.md`)
- [x] RedStone: `scripts/redstone_benchmark_comparison.py`, `data/processed/redstone_benchmark_oos.parquet`, `reports/tables/redstone_coverage_by_k_pct.csv`, `reports/v1b_redstone_comparison.md` (n=12, 4 weekends × 3 symbols; smallest k_pct hitting τ=0.95 is 2.5% / 250 bps with 1.000 realised — over-covered on a small/gentle sample; re-run weekly)
- [x] Kamino Scope: `scripts/kamino_scope_benchmark_comparison.py`, `data/processed/kamino_scope_benchmark_oos.parquet` (n=0 evaluable as of 2026-05-02; tape starts 2026-04-26 Sunday so the only candidate Friday in panel range is pre-tape; first evaluable weekend = Friday 2026-05-01 → Monday 2026-05-04, will populate after Yahoo Monday-open lands ~2026-05-05 14:00 UTC)
- [x] Unified report: `scripts/run_incumbent_oracle_unified_report.py`, `reports/tables/incumbent_oracle_unified_summary.csv`, `reports/v1b_incumbent_oracle_comparison.md`
- [ ] Methodology log entry referencing the unified table — pending decision on whether the finding is material enough to log (recommend: yes; one short entry adopting the unified report as a recurring artefact, *not* a methodology change).
- [ ] Paper 1 §7.9 rung citing the four-oracle comparison + Soothsayer (v1, M5).

**Result (fill in on completion):**

W1 complete on 2026-05-02. Headline (`reports/v1b_incumbent_oracle_comparison.md`):

| τ | Soothsayer v1 (deployed) | Soothsayer M5 (v2 cand.) | Pyth+50·conf | Chainlink ±k_pct on stale mid | RedStone ±k_pct on point |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 136 bps (n=1730) | 110 bps (n=1730) | 140 bps at k=25 (n=265) | 150 bps at 1.5% (n=87) | 100 bps at 1.0% (n=12) |
| 0.85 | 251 bps (n=1730) | 201 bps (n=1730) | 279 bps at k=50 (n=265) | 250 bps at 2.5% (n=87) | 250 bps at 2.5% (n=12) |
| 0.95 | 443 bps (n=1730) | 355 bps (n=1730) | 279 bps at k=50 (n=265) | 400 bps at 4.0% (n=87) | 250 bps at 2.5% (n=12) |

Three findings:

1. **Only Soothsayer publishes a calibration claim.** Every incumbent row's `halfwidth_bps_at_tau` is the smallest consumer-supplied k or k_pct in the sweep that crosses τ realised. The "narrower" appearance of some incumbents requires the consumer to do their own calibration backtest on their own historical sample — Soothsayer publishes the claim as a first-class field.
2. **Sample sizes are not commensurate.** Soothsayer rows are on 1,730 OOS observations; Pyth on a 265-obs subset (SPY/QQQ/TLT/TSLA-heavy, low-vol composition); Chainlink on an 87-obs frozen panel; RedStone on 12 forward-tape obs. The Pyth-vs-Soothsayer matched-subset comparison (already in `v1b_pyth_comparison.md`) puts Soothsayer's `normal`-regime large-cap half-width at ≈401 bps vs Pyth+50× at 280 bps — the 443 bps headline averages over high-vol weekends Pyth's eligible subset doesn't see.
3. **Forward-tape over-coverage is sample-driven.** RedStone hits 1.000 realised at 250 bps on n=12, but the 95% binomial CI on that estimate is ≈±40pp; this is a baseline that re-runs weekly and is expected to widen.

**Decision (Adopt / Disclose-not-deploy / Reject):** **Adopt as recurring artefact.** The unified table is the single highest-value chart for the Colosseum pitch + Paper 1 §7 reviewer-defensibility — it makes the calibration-claim asymmetry between Soothsayer and incumbents quantitative on data already on disk. **No methodology change**; this is a comparator artefact. Recurring re-run schedule: every Tuesday after Yahoo Monday-open lands. To stay honest, re-run the unified report after the M5 deployment (post-2026-05-10) to swap M5 numbers from "v2 candidate" framing to "v1.5 deployed."

---

## W2 — Berkowitz / DQ rejection localization

**Status:** Complete 2026-05-02.

**Question.** Both v1 and M5 reject Berkowitz on the OOS 2023+ panel. Where do the rejections live? Can a partition flip from rejecting to non-rejecting, and if so, what does that partition tell us about the next forecaster rung?

**Deliverables.**

- [x] `scripts/run_density_rejection_diagnostics.py`
- [x] `reports/v1b_density_rejection_localization.md`
- [x] `reports/tables/v1b_density_rejection_per_partition.csv` (Berkowitz + DQ in 27 partitions × 2 methodologies)
- [x] `reports/tables/v1b_density_rejection_lag1_decomposition.csv` (cross-sectional vs temporal lag-1)
- [x] `reports/tables/v1b_density_rejection_berkowitz_decomposed.csv` (LR_full → mean / var / AR(1) shares)
- [x] `reports/tables/v1b_density_rejection_pit_m5.csv` (per-row M5 PITs for downstream use)

**Result:**

Four findings:

1. **v1 and M5 fail Berkowitz for different surface reasons.** v1's pooled LR=37.6 decomposes as 68% variance compression (var_z=0.84), 27% mean shift (mean_z=0.07), 5% AR(1). M5's LR=173 is 99.6% AR(1) (rho=0.31), <1% variance/mean. v1's bands plus the deployed 0.020 buffer are slightly too wide (PITs cluster near 0.5); M5's per-row magnitude is correctly calibrated but consecutive-row PITs are correlated.
2. **The cross-sectional autocorrelation is a data property, not a methodology artefact.** Re-ordering both v1 and M5 PITs by `(fri_ts, symbol)` and computing within-weekend lag-1 gives **ρ ≈ 0.354 for both methodologies**. Within-symbol temporal lag-1 is ≈ 0 for both. Neither methodology absorbs the common-mode weekend residual after their factor-adjusted points. v1's lower pooled LR is only because `run_reviewer_diagnostics.py` orders v1 by `(symbol, fri_ts)` (temporal-first) while `density_tests_m5` orders M5 by `(fri_ts, symbol)` (cross-sectional-first) — the underlying structure is identical.
3. **Per-symbol M5 reveals heterogeneous variance.** Single-symbol Berkowitz on M5 (where AR(1) is near zero per finding 2) shows wildly different `var_z`: SPY (0.30), QQQ (0.44), GLD (0.44), TLT (0.43) all have *compressed* PITs (M5 bands too wide); MSTR (2.10), TSLA (1.74), HOOD (1.67) have *inflated* PITs (M5 bands too narrow). Per-regime Mondrian pools across symbols within a regime; per-symbol residual scale is not uniform within a regime. NVDA (var_z=1.19, p=0.26) and GOOGL (var_z=0.77, p=0.07) are the only single-symbol partitions that pass.
4. **Non-rejecting partitions exist.** With Berkowitz p ≥ 0.05 and n ≥ 50: M5/NVDA, M5/GOOGL, M5/with_earnings (n=82); v1/AAPL, v1/GOOGL, v1/SPY, v1/QQQ, v1/GLD, v1/vix_low, v1/with_earnings. v1's per-symbol calibration is locally uniform across most of the universe (no AR(1) within-symbol; mean and variance close to Gaussian). The pooled rejection is fully attributable to the cross-sectional dimension for both methodologies.

**Decision: Adopt as v3 forecaster leads + Paper 1 §9 disclosure upgrade.** Two clean v3 candidates fall out:

- **v3 lead 1: common-mode residual partial-out.** After the factor-adjusted point and before per-regime conformal quantile, regress residuals on the cross-sectional weekend mean residual; refit conformal on the doubly-residualised score. Expected to remove ρ ≈ 0.35 and tighten the band ~10–15%.
- **v3 lead 2: per-symbol Mondrian.** Move from `Mondrian(regime)` to `Mondrian(regime × {symbol-class})`. Re-allocates width across the universe — tightens SPY/QQQ/TLT/GLD, widens MSTR/TSLA/HOOD — rather than reducing total width.

**Disclosure upgrade for Paper 1 §6/§9.** Replace "per-anchor calibration only, not full-distribution" with: *per-anchor calibration is uniform within-symbol across the panel; the pooled Berkowitz rejection is fully attributable to (a) cross-sectional common-mode residual autocorrelation (ρ ≈ 0.35) and (b) heterogeneous per-symbol residual variance under M5's per-regime quantile pooling. Both are isolated v3 leads.*

**Not a methodology change for v1 or M5.** Pre-2026-05-10 Colosseum delivery still ships under v1; M5 still ships post-Colosseum without modification.

---

## W2-followup — v3 forecaster leads quantified (M6a, M6b, M6c)

**Status:** Complete 2026-05-02. Spawned directly by W2's findings.

**Question.** W2 identified two clean v3 leads. How much width gain does each deliver, and do they stack?

**Deliverables.**

- [x] `scripts/run_m6a_common_mode_partial_out.py`, `reports/v1b_m6a_common_mode_partial_out.md`, `reports/tables/v1b_m6a_common_mode_oos.csv`, `reports/tables/v1b_m6a_common_mode_fit.csv`
- [x] `scripts/run_m6b_per_symbol_class_mondrian.py`, `reports/v1b_m6b_per_symbol_class_mondrian.md`, `reports/tables/v1b_m6b_per_symbol_class_oos.csv`, `reports/tables/v1b_m6b_per_cell_quantiles.csv`
- [x] `scripts/run_m6c_combined.py`, `reports/v1b_m6c_combined.md`, `reports/tables/v1b_m6c_combined_oos.csv`

**Result.** Half-width (bps) at matched OOS realised coverage on the §6/§7 OOS 2023+ panel (n=1,730 weekends × symbols).

| τ | v1 (deployed) | M5 (v2 cand.) | M6a (upper bound) | M6b1 (per-symbol) | M6b2 (per-class) | **M6c (M6a+M6b2)** |
|---:|---:|---:|---:|---:|---:|---:|
| 0.68 | 136 | 110 | 103 (-7%) | 118 (+7%) | 116 (+5%) | **105 (-5%)** |
| 0.85 | 251 | 201 | 178 (-11%) | 185 (-8%) | 185 (-8%) | **168 (-16%)** |
| 0.95 | 443 | 355 | 309 (-13%) | **299 (-16%)** | 304 (-14%) | **271 (-24%)** |
| 0.99 | 609⁺ | 677 | 596 (-12%) | 718 (+6%) | 664 (-2%) | **643 (-5%)** |

⁺ v1 hits the bounds-grid ceiling at τ=0.99; numbers comparable across the table only at τ ≤ 0.95.

Realised coverage matches τ-target across all variants at all anchors (sample-size CIs ~±2pp).

**Findings.**

1. **M6a (common-mode partial-out, upper bound).** β̂=0.811, R²=0.278 (train), R²=0.255 (OOS). The leave-one-out weekend mean residual explains ≈28% of per-row residual variance. Cross-sectional within-weekend ρ on the signed residual drops 0.41 → 0.07 after partial-out — confirms the diagnosis. Width gain at τ=0.95: **-13%** (355 → 309 bps). **Caveat: r̄_w^(−i) is Monday-derived; M6a is an *upper-bound* until a Friday-observable proxy is built.** Deployable gain scales with the forward predictor's R²(r̄_w | Friday-state); a predictor with R²=0.5 would deliver ≈ -7% at τ=0.95.
2. **M6b (per-symbol / per-class Mondrian, deployable).** Re-allocates width across symbols rather than reducing total width uniformly. **M6b2 (per-class, 6 cells) is the deployment-ready candidate**: -14% at τ=0.95 with 24 trained scalars (vs M5's 12), τ=0.99 width essentially unchanged. M6b1 (per-symbol, 10 cells) gives a slightly bigger gain at τ=0.95 (-16%) but pays a +6% width penalty at τ=0.99 driven by HOOD's thin tail in OOS — preferable only if HOOD-class noise is acceptable. M6b3 (class × regime, 18 cells with regime-fallback) underperforms M6b2 cleanly — the cross-cell sample dilution outweighs the partition gain.
3. **M6c stacks (efficiency ≈ 0.87 at τ ∈ {0.85, 0.95}).** Gains are mostly additive: M6a -13% + M6b2 -14% combine to M6c -24% at τ=0.95 (vs additive prediction of -27%). Two structurally different residual-variance sources captured. **Vs the deployed v1 baseline of 443 bps at τ=0.95, M6c is 271 bps — a 39% narrower band.**

**Decision (Adopt / Disclose-not-deploy / Reject):**

- **M6b2 — Adopt as v3 deployment candidate (post-M5 deployment, post-Colosseum).** -14% at τ=0.95 vs M5, deployable today, modest parameter increase. Becomes a Paper 1 v3 future-work paragraph immediately and a methodology-history candidate when prioritised.
- **M6a — Adopt as a v3-research workstream gated on a forward predictor of r̄_w.** Build a Friday-observable proxy: candidates are CME ES/NQ Sunday-Globex implied gap, VIX/skew change, sector-rotation indicators. If a predictor with R²(forward) ≥ 0.4 against r̄_w is achievable, deployable M6a delivers ≈ -5 to -8% at τ=0.95 standalone, and stacks with M6b2 to ~-19 to -22%. Gate: prototype a forward predictor (1–2 weeks of work) before committing to deployment.
- **M6c — Headline v3 ceiling.** 271 bps at τ=0.95 = 39% narrower than deployed v1, 24% narrower than M5. This is the best evidence that the methodology has serious headroom beyond M5. Honest framing: "M5 closes 32% vs v1; v3 family closes another 24% over M5 with deployment caveats."

**Paper 1 / Colosseum impact.**

- Colosseum 2026-05-10 ships under v1 unchanged. No methodology change.
- Paper 1 §10 future-work upgrades from "conformal alternatives" to a structured M6 family with quantified ceilings.
- Paper 4 (post-grant AMM) inherits the v3-ceiling argument as a deployment headroom claim — the band primitive has multi-year width-tightening trajectory ahead.

---

## W3 — Regime classifier audit

**Status:** Not started.

**Question.** M5 makes `regime_pub` load-bearing: per-regime conformal quantile is what does the work. How robust is the classifier itself?

**Audit checklist.**
1. **Count-per-regime in OOS.** If `high_vol` has <50 weekends in OOS, the per-regime conformal quantile is finite-sample noisy; compute bootstrap CI on `q_high_vol(0.95)` to size the uncertainty.
2. **Boundary sensitivity.** What fraction of (symbol-weekend) cells sit within ε of a regime threshold (where ε is some natural scale, e.g. 0.5 vol-index points for the high_vol cutoff)? Coverage of these boundary cells vs interior cells.
3. **Leave-one-year-out classifier consistency.** Re-fit the classifier excluding 2024, then 2023, then 2022; how often does the regime label flip on the held-out year?
4. **Concept drift.** Plot fraction-in-each-regime by year. Has the regime mix changed monotonically over 2015–2026?
5. **Adversarial regimes.** Spot-check regime labels for known-stress periods (Aug 2024 yen carry, Oct 2022 BoE, Mar 2023 SVB, Apr 2025 tariff spike, Nov 2025 xStock cluster). Does each get classified plausibly?

**Deliverables.**
- [ ] `scripts/run_regime_classifier_audit.py`
- [ ] `reports/v1b_regime_classifier_audit.md`

**Result:** _pending_

**Decision:** _pending_

---

## W4 — Asymmetric / one-sided coverage

**Status:** Not started.

**Question.** Bands are symmetric `±hw`, but xStock weekend returns are likely skewed (left-tail heavier on equities; right-tail heavier on MSTR/TSLA). If realized coverage at τ=0.95 nominal is 0.95 *pooled* but, say, 0.91 left-tail / 0.99 right-tail, the protocol implication is concrete: P-conf and P+conf should not be equal.

**Protocol.**
1. Decompose realized coverage at each τ into `cov_left = P(truth ≥ point − hw)` and `cov_right = P(truth ≤ point + hw)`.
2. Test `H0: cov_left = cov_right` per τ.
3. If rejected, compute the implied asymmetric quantile pair `(q_low(τ), q_high(τ))` from the empirical residual distribution per regime.
4. Quantify the width premium over a symmetric band at matched two-sided coverage.

**Why this matters.** Direct input to Paper 3 §Structural — MarginFi semantics already are asymmetric (P-conf, P+conf). If our band is symmetric while the residual distribution isn't, the Paper 3 worked example is partly misspecified.

**Deliverables.**
- [ ] `scripts/run_asymmetric_coverage.py`
- [ ] `reports/v1b_asymmetric_coverage.md`

**Result:** _pending_

**Decision:** _pending_

---

## W5 — Live forward-tape realized coverage

**Status:** Not started; data accruing since 2026-04-26.

**Question.** What's realized coverage on the *forward* slice — weekends that happened entirely after the last calibration cutoff?

**Protocol.**
1. Define `forward_panel` = weekends with `_fetched_at` ≥ 2026-04-26 on Yahoo bars (or wherever the last calibration data ended).
2. Build the same coverage table as §6 of Paper 1, computed only over `forward_panel`.
3. Re-compute weekly as forward panel grows.

**Why this matters.** Reviewer-immune — there is no plausible "you tuned on this" critique. For Colosseum, "live since 2026-04-26, realized 0.94 vs τ=0.95" beats a backtest table for video / pitch comprehensibility.

**Deliverables.**
- [ ] `scripts/run_forward_coverage.py` (idempotent; safe to re-run weekly)
- [ ] `reports/v1b_forward_coverage.md` (auto-updated)

**Caveat.** Sample is tiny right now (~1–2 weekends). This deliverable's value compounds; do once, make it cheap to re-run.

**Result:** _pending_

**Decision:** _pending_

---

## W6 — Halt-window subset coverage

**Status:** Not started.

**Question.** During NASDAQ halts (`nasdaq/halts` dataset), what's realized coverage of (a) Soothsayer's band and (b) incumbent oracles' published bands? Halts are exactly where Kamino's PriceHeuristic / staleness gates fail (Paper 3 §Structural argument), so empirical coverage in those windows is the direct numerical complement.

**Protocol.**
1. Join `nasdaq/halts` rows with oracle tapes (per-symbol, per-time-window).
2. For each halt event, compute the band's coverage of the *first post-resume cash print*.
3. Compare across oracles.

**Deliverables.**
- [ ] `scripts/run_halt_coverage.py`
- [ ] `reports/v1b_halt_coverage.md`

**Cross-link.** This is the empirical complement to `reports/paper3_liquidation_policy/protocol_semantics.md`.

**Result:** _pending_

**Decision:** _pending_

---

## W7 — Cross-class Mondrian (class × regime)

**Status:** Not started.

**Question.** Mondrian by `regime` pools equities, GLD, TLT, BTC. They have very different residual distributions. Does Mondrian by `(class, regime)` tighten further?

**Protocol.**
1. Define class buckets: `equity_high_beta` (NVDA, TSLA, MSTR, HOOD), `equity_index` (SPY, QQQ), `single_stock_meta` (AAPL, GOOGL), `gold` (GLD), `bond` (TLT), `crypto` (BTC?). Verify against `src/soothsayer/universe.py`.
2. Re-run M5 on the `(class, regime)` partition; report width and coverage per cell.
3. Compare to current M5 (regime-only).

**Why this matters.** If it tightens, that's an M5+ rung for v2 deployment. If it doesn't, that's a strong "pooling justified" footnote that pre-empts the obvious reviewer critique.

**Deliverables.**
- [ ] `scripts/run_mondrian_class_x_regime.py`
- [ ] `reports/tables/v1b_mondrian_class_x_regime.csv`

**Result:** _pending_

**Decision:** _pending_

---

## Cleanup (when this doc is empty)

- [ ] Every workstream above has a terminal decision recorded.
- [ ] Findings that warranted methodology changes have entries in `reports/methodology_history.md`.
- [ ] Findings that didn't warrant changes have a one-line "considered and dropped" entry in the methodology log.
- [ ] **Delete this file (`VALIDATION_BACKLOG.md`).**
