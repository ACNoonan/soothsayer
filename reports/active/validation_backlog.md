# Validation Backlog — Defensibility Workstreams Beyond M5

**Status:** Living working doc. Created 2026-05-02 after M5 Mondrian validation entry landed.

**Delete this file when:** every workstream below is either (a) executed and folded into `reports/methodology_history.md` as a dated entry with linked artefact, or (b) explicitly rejected with a rationale recorded in the methodology log.

**Source of truth for everything that *sticks*:** `reports/methodology_history.md`. This file is scratch-space for *candidates* to that ledger.

**Source of truth for current state:** `reports/methodology_history.md` §0.

**Sibling working doc:** `reports/active/m6_refactor.md` (post-M5 dual-profile rollout — Lending-track M6b2 + AMM-track M6a). `M5_REFACTOR.md` was deleted on completion 2026-05-XX (see `reports/methodology_history.md` deployment receipt).

---

## Why this exists

After the 2026-05-02 M5 Mondrian win, the question was: *what other tests should we run to make sure the system is the strongest possible relative to incumbent oracles?* This backlog enumerates those candidates with prioritization, expected effort, gate condition, and a result line that gets filled in as each completes. Each item ends in one of three terminal states:

- **Adopt** — material finding, append a methodology log entry, propagate to papers/code, then strike from this doc.
- **Disclose-not-deploy** — informative result, footnote in Paper 1, no methodology change.
- **Reject** — null/uninformative, log a one-line "considered and dropped" entry in the methodology log so it does not get re-suggested.

---

## Priority ranking (2026-05-03 — post-W8-decision)

1. ~~**W1 — Incumbent oracle band coverage head-to-head.**~~ Complete 2026-05-02. Adopt as recurring artefact.
2. ~~**W2 — Berkowitz / DQ rejection localization.**~~ Complete 2026-05-02. Adopt as v3 forecaster leads + Paper 1 §9 disclosure upgrade.
3. ~~**W2-followup — v3 leads quantified (M6a, M6b, M6c).**~~ Complete 2026-05-02. Adopt M6b2 as Lending-track; adopt M6a-deployable as AMM-track conditionally on W8.
4. ~~**W8 — r̄_w forward predictor prototype.**~~ Complete 2026-05-03. Reject at Friday-close-only feature set; AMM-track shipping deferred indefinitely until Sunday-Globex republish architecture (W8b, engineering-gated) or V3.1 F_tok data accumulation (W8c, data-gated).
5. ~~**W4 — Asymmetric / one-sided coverage.**~~ Complete 2026-05-03. Q1 (two-sided asymmetric on wire) Disclose-not-deploy; Q2 (auxiliary one-sided per-class table) Adopt — handed off to other agent's Phase A1 artefact builder + ~hour of consumer SDK work. Direct Paper 3 §Structural narrative upgrade.
6. **W3 — Regime classifier audit.** M5 makes `regime_pub` load-bearing on AMM-track (Lending-track uses `symbol_class`); classifier robustness is now an AMM-track-specific methodology question, deferred alongside AMM-track shipping.
7. **W5 — Live forward-tape realized coverage.** Reviewer-immune. Grows over time; cheap to set up.
8. **W6 — Halt-window subset coverage.** Direct numerical complement to Paper 3 §Structural.
9. **W7 — Cross-class Mondrian (class × regime).** Subsumed by M6b3 in W2-followup; tested and rejected (sample dilution beats partition gain). Strike.
10. **W8b — Sunday-Globex republish predictor (deferred).** Re-evaluate W8 with ES/NQ Sunday 18:00 ET reopen returns added to the feature set. Requires a scryer fetcher for Sunday-evening futures snapshots first. ~3–4 weeks total once scryer item lands.
11. **W8c — V3.1 F_tok-based predictor (deferred).** Re-evaluate W8 with the on-chain xStock cross-section as the predictor's primary feature. Data-gated on V3.1 F_tok tape accumulation (≥150 weekends; ETA Q3–Q4 2026).
12. ~~**W9 — v3 per-symbol-calibration bake-off (C1 / C2 / C4 vs M5).**~~ Complete 2026-05-03. **Decision: freeze M5 as Paper 1.** C1 (LWC + regime) lead candidate for v3 per-symbol calibration, deferred until V3.2 rolling-rebuild + paper-grade walk-forward; C2 (M6b2) → Paper 3 lending track (already deployed for Lending profile); C4 (stacked) Pareto-dominated, **rejected**.

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

## W4 — Asymmetric / one-sided coverage (Lending-track sub-axis)

**Status:** Complete 2026-05-03. **Decision: Q1 Disclose-not-deploy (two-sided asymmetric pair); Q2 Adopt as auxiliary (one-sided per-class quantile table).** Redirects `reports/active/m6_refactor.md` Phase A7 from "asymmetric two-sided wire-format pair" to "auxiliary one-sided lending-consumer table in the artefact JSON sidecar."

**Question.** Bands are symmetric `±hw`, but xStock weekend returns are likely skewed (left-tail heavier on equities; right-tail heavier on MSTR/TSLA). If realized coverage at τ=0.95 nominal is 0.95 *pooled* but, say, 0.91 left-tail / 0.99 right-tail, the protocol implication is concrete: MarginFi's P-conf and P+conf should not be equal, and band-perp's long vs short liquidation buffers should not be equal.

**Why Lending-track only.** The asymmetric pair `(q_low(τ), q_high(τ))` matters specifically for products that take *different* positions on the upper vs lower bound. Lending: assets use the lower bound, liabilities use the upper. Band-perp: long liquidation tied to lower, short liquidation tied to upper. Single-underlier options inherit the asymmetry from the underlying. The AMM-track (LP region sizing across the universe) doesn't see asymmetry as load-bearing — pooled width drives LP economics, and the AMM-track's M6a partial-out is a symmetric correction. The asymmetric pair is therefore a clean Lending-track sub-axis and not a separate methodology family.

**Protocol.**
1. Decompose realized coverage at each τ into `cov_left = P(truth ≥ point − hw)` and `cov_right = P(truth ≤ point + hw)`, both pooled and per `symbol_class`.
2. Test `H0: cov_left = cov_right` per (τ, symbol_class).
3. Where rejected, compute the asymmetric quantile pair `(q_low(τ), q_high(τ))` from per-class signed residual distribution (uses the same pre-2023 calibration set as the M6b2 b's).
4. Quantify the width-premium over a symmetric band at matched two-sided coverage; quantify the asymmetric-aware width gain at matched one-sided τ.
5. Wire format: no change. The `lower` and `upper` fields in `PriceUpdate` already carry the two sides independently — W4 just changes how they're computed in the artefact build.

**Deliverables.**
- [x] `scripts/run_asymmetric_coverage.py` — analysis runner; reports per-(τ, symbol_class) cov_left vs cov_right + the implied asymmetric pair + the one-sided lending-consumer view.
- [x] `reports/v1b_w4_asymmetric_coverage_lending.md` — paper-ready writeup with two-question decision split.
- [x] `reports/tables/v1b_w4_asymmetric_per_class_tau.csv`, `v1b_w4_asymmetric_one_sided.csv`, `v1b_w4_skewness_train.csv`.
- [ ] **Q2 deliverable (handoff to other agent's Phase A1 work):** extend `scripts/build_m6b2_lending_artefact.py` to emit `LENDING_QUANTILE_ONE_SIDED_LOW` and `LENDING_QUANTILE_ONE_SIDED_HIGH` keyed by `(symbol_class, tau_one)` in the artefact JSON sidecar. 24 additional scalars (6 classes × 2 anchors × 2 sides; `equity_recent` τ=0.95-only per cell-size gate). Wire format: no change.
- [ ] Consumer SDK accessor in `crates/soothsayer-consumer`: `one_sided_quantile(symbol_class, tau, side)` reading from the auxiliary table.
- [ ] Paper 3 §Structural worked example: regenerate at one-sided q_low / q_high widths.

**Result.** Two questions, two answers:

**Q1 — Replace symmetric `b_sym(class, τ)` with asymmetric `(q_low, q_high)` at two-sided τ?** **No.** Materially-asymmetric cells: 2/21 (10%, below the 25% adoption threshold). Pooled `width_delta_pct` at τ=0.95 = +2% (asymmetric is *wider* at matched two-sided coverage). Equal-tail asymmetric reallocates between tails but doesn't shrink total band. Only `bond` shows clearly asymmetric tail violations on OOS (left 6.4% vs right 2.3% at τ=0.95). Per-class skewness is real on TRAIN — `equity_meta` skew = −1.80, `gold` = −2.32, `equity_index` = −0.90 — but doesn't translate to a tighter two-sided band.

**Q2 — Publish auxiliary per-class one-sided quantiles for lending consumers?** **Yes.** Headline at τ_one = 0.95 (the lending-consumer-facing target):

| symbol_class | sym `b_two`(0.95) bps | one-sided q_low bps | asset Δ | one-sided q_high bps | liability Δ |
|---|---:|---:|---:|---:|---:|
| equity_index | 169 | 102 | **−39%** | 135 | **−20%** |
| equity_meta | 232 | 150 | **−35%** | 169 | **−27%** |
| equity_highbeta | 451 | 275 | **−39%** | 313 | **−31%** |
| equity_recent | 463 | 408 | **−12%** | 227 | **−51%** |
| gold | 145 | 127 | **−12%** | 95 | **−35%** |
| bond | 132 | 113 | **−14%** | 95 | **−28%** |

Reading: a MarginFi asset Bank holding equity_highbeta collateral that targets 95% downside confidence currently reads the symmetric `b_sym(0.95) = 451 bps`, which is actually a 97.5% one-sided guarantee. With the auxiliary table, the Bank reads `q_low_one(equity_highbeta, 0.95) = 275 bps` and gets exactly the 95% one-sided contract it specified — **39% narrower buffer at the same statistical guarantee**. OOS realised lower coverage validates: 0.92 (within sample-size CI of the 0.95 target), vs the symmetric band's 0.97 over-cover.

**Decision: Disclose-not-deploy (Q1) + Adopt as auxiliary (Q2).**

- **Q1 strike from `reports/active/m6_refactor.md` Phase A7's original scope.** The published `lower` / `upper` continue to be the symmetric `point ± b_sym(class, τ)·fri_close`. No wire-format change. No two-sided asymmetric publish.
- **Q2 redirects Phase A7 to the auxiliary one-sided table.** Implementation: ~half-day on the artefact builder + ~hour on the consumer SDK accessor + the Paper 3 worked-example refresh.
- **Paper 3 §Structural narrative upgrade:** the auxiliary table replaces ad-hoc Kamino reserve-buffer set-up with calibrated per-(symbol_class, τ_one, side) receipts. MarginFi assets-vs-liabilities maps cleanly to `q_low_one` / `q_high_one`. This is the strongest empirical Paper 3 lever from the W2-W4 chain.

---

## W5 — Live forward-tape realized coverage

**Status:** Soothsayer-side cron (analysis); scryer-side SLA dependency on `yahoo/equities_daily` Monday cron reliability. Data accruing since 2026-04-26.

**Question.** What's realized coverage on the *forward* slice — weekends that happened entirely after the last calibration cutoff?

**Protocol.**
1. Define `forward_panel` = weekends with `mon_ts > 2026-04-24` (the last fri_ts in `data/processed/v1b_panel.parquet`'s held-out OOS slice).
2. Build the same coverage table as §6 of Paper 1, computed only over `forward_panel`.
3. Re-compute weekly as forward panel grows.

**Why this matters.** Reviewer-immune — there is no plausible "you tuned on this" critique. For pitch / paper purposes, "live since 2026-04-26, realised 0.94 vs τ=0.95" beats a backtest table for comprehensibility.

**Scryer-side dependency (operational SLA, not new development).**

- Confirm `yahoo/equities_daily/v1` forward cron lands Monday-open data reliably by 14:30 UTC each Monday (NYSE open + 1h buffer). Today the cron exists but cadence is unclear from Soothsayer's vantage.
- This becomes scryer-handoff item #1 in the prompt below.

**Soothsayer-side deliverables (do after scryer SLA confirmed).**
- [x] `scripts/run_forward_coverage.py` (idempotent; safe to re-run weekly; Path 2 self-contained — re-derives the panel from scryer over a forward-extended window, applies the deployed M5 serve formula via `soothsayer.oracle` constants, and cross-checks 3 historical rows against the frozen `v1b_panel.parquet` before reporting forward numbers)
- [x] `reports/v1b_forward_coverage.md` (auto-updated; first run 2026-05-03 with n=0 forward weekends — fri 2026-05-01 → mon 2026-05-04 not yet evaluable until Yahoo Monday cron lands ~14:30 UTC Tue)
- [ ] Optional: a tiny launchd plist on Adam's machine to fire the runner Tuesday 09:00 local time.

**Caveat.** Sample is small right now (~1 evaluable weekend). This deliverable's value compounds; do once, make it cheap to re-run.

**Result:** _pending forward-tape accumulation_ (runner stood up 2026-05-03; first evaluable weekend = fri 2026-05-01 → mon 2026-05-04, populates on the 2026-05-05 Tuesday-morning re-run)

**Decision:** _pending_

---

## W6 — Halt-window subset coverage

**Status:** Gated on a new scryer dataset (intraday NBBO around halt events). Coarse-grained variant (using next daily close as the post-resume proxy) is Soothsayer-side and unblocked, but the precise per-halt analysis needs the new fetcher.

**Question.** During NASDAQ halts (`nasdaq/halts` dataset), what's realised coverage of (a) Soothsayer's band and (b) incumbent oracles' published bands? Halts are exactly where Kamino's PriceHeuristic / staleness gates fail (Paper 3 §Structural argument), so empirical coverage in those windows is the direct numerical complement.

**Why scryer-side.** Today's `nasdaq/halts` gives halt timestamps but no intraday cash prints. To compute "band's coverage of the first post-resume cash print" precisely, we need 1-min OHLCV bars for the affected symbol covering the halt window (e.g., −5min before halt to +30min after resume). This is a new scryer dataset, not analysis-side work.

**Scryer-side deliverable (new wishlist item).**

Proposed scryer wishlist item #53: `nasdaq/halts_intraday/v1` or similar. 1-minute OHLCV around each halt event in `nasdaq/halts/v1`. Source recommendation: Yahoo intraday 1-min bars (free, ~60-day backfill window — adequate for going-forward halt coverage; older halts won't backfill). Alternative: Polygon free tier, if API key is available.

This becomes scryer-handoff item #2 in the prompt below.

**Soothsayer-side deliverables (do after scryer dataset lands).**
- [ ] `scripts/run_halt_coverage.py` — joins `nasdaq/halts/v1` with `nasdaq/halts_intraday/v1` and the four oracle tapes; computes per-halt coverage and per-oracle width comparison.
- [ ] `reports/v1b_halt_coverage.md` — paper-ready writeup; cross-links to Paper 3 §Structural.

**Coarse-grained interim (Soothsayer-side, unblocked).** A Soothsayer-only variant using `yahoo/equities_daily` next-daily-close as the post-resume proxy is implementable today. Less precise than the intraday version (a halt at 14:30 ET resumes by 16:00 ET, but daily close is also at 16:00 ET — the proxy collapses for late-day halts). Could be a "v0 coarse" report while the scryer dataset is being built.

**Cross-link.** This is the empirical complement to `reports/paper3_liquidation_policy/protocol_semantics.md`.

**Result:** _pending_ (scryer dataset, then Soothsayer analysis runner)

**Decision:** _pending_

---

## W7 — Cross-class Mondrian (class × regime)

**Status:** Subsumed by W2-followup M6b3 variant; tested and rejected 2026-05-02. Strike from active list.

**Result.** `scripts/run_m6b_per_symbol_class_mondrian.py` evaluated M6b3 (`Mondrian(symbol_class × regime)`, 18 cells with regime-fallback for n<30 cells) on the OOS 2023+ panel. At τ=0.95: half-width 320 bps vs M6b2's 304 bps — M6b3 is **wider** than M6b2 despite the finer partition. Sample-dilution beats partition-gain at the available train sample size. M6b2 (`Mondrian(symbol_class)`, 6 cells) is the correct choice.

**Decision: Reject.** No methodology log entry needed beyond the W2-followup record. M6b3 is documented as a tested-and-dropped variant in `reports/v1b_m6b_per_symbol_class_mondrian.md`.

---

## W8 — r̄_w forward predictor prototype (AMM-track shipping gate)

**Status:** Complete 2026-05-03. **Decision: REJECT** at the Friday-close-only feature set; AMM-track shipping deferred until Sunday-Globex republish architecture or V3.1 F_tok data accumulates.

**Question.** M6a's upper-bound width gain (-13% at τ=0.95) uses the leave-one-out weekend-mean residual r̄_w^(−i), which is Monday-derived. To deploy AMM-track, we need a Friday-observable predictor of r̄_w with R²(forward) ≥ 0.4 against the realized r̄_w on a TRAIN/OOS split. Below that threshold, the deployable M6a width gain is too small to justify the engineering cost; above it, AMM-track ships and unlocks Layer 1 (Band-AMM) + Layer 4 AMM-licensee tier.

**Hypotheses for the predictor (cheap to test).**

1. **CME ES/NQ Sunday-Globex implied weekend gap.** Friday close → Sunday 18:00 ET futures reopen → Monday cash open. The futures track the index move continuously over the weekend; by Monday cash open the futures-implied gap is a strong signal. Soothsayer publishes at *Friday* close, so the relevant question is: how much of `r̄_w` is predictable from *Friday-close* futures state alone (without Sunday Globex peeking)? Likely some — futures already trade Friday late; the Friday-close ES quote already reflects forward-looking information. Cong et al. and the M6a `factor_ret` precedent suggest yes.
2. **VIX/skew change Friday close vs prior week.** Common-mode dispersion correlates with vol-regime change. Test ΔVIX, ΔGVZ, ΔMOVE as features.
3. **Sector rotation indicators.** XLK/XLF/XLE relative-strength change Friday close vs prior week. If sector dispersion is accelerating, common-mode `r̄_w` is more predictable.
4. **Macro release calendar.** Fed minutes, CPI, NFP, FOMC adjacent weekends have wider expected `r̄_w`. Categorical feature.
5. **Soothsayer-v5 tape signal (post-V3.1).** Once on-chain xStock prices have ≥150 weekends of coverage (V3.1 F_tok gate), the cross-sectional mean of weekend xStock drift is a near-perfect proxy for `r̄_w`. Today's sample (≈30 weekends) is too small.

**Protocol.**

1. Feature-engineering pass on the v1b_panel: assemble candidate Friday-observable features (ES/NQ ret, GC/ZN/BTC ret, VIX/GVZ/MOVE level + change, fri_vol_20d index, sector spreads if available in scryer).
2. OLS regression of `r̄_w` on the feature set on the TRAIN slice (pre-2023). Report R²(train), R²(OOS) on the 2023+ slice. Stepwise feature selection to maximize OOS R².
3. Cross-validate with regularization (Ridge) to handle multicollinearity in the macro-vol features.
4. Gate: `R²(OOS) ≥ 0.4` against `r̄_w`. Stretch: `R²(OOS) ≥ 0.6` (would deliver ≥80% of M6a's upper-bound gain).
5. Sanity-check: Berkowitz on M6a-deployable PITs (using `r̄_w_hat` instead of `r̄_w^(−i)`) — cross-sectional ρ should drop materially below 0.41. Expected: ρ ≈ 0.41 × (1 − R²(OOS)) under linear partial-out.

**Why this matters.** Direct gate on AMM-track deployment. Below R²=0.4, M6a is "interesting upper bound" only and `reports/active/m6_refactor.md` Phase B defers indefinitely (or reframes as "wait for V3.1 F_tok signal accumulation"). Above R²=0.4, AMM-track ships under `reports/active/m6_refactor.md` Phase B and Layer 1 / Layer 4 AMM-licensee tier go live.

**Deliverables.**

- [x] `scripts/run_r_bar_forward_predictor.py` — feature engineering + OLS/Ridge fit + R²(train/OOS) reporting + cross-sectional-ρ sanity check. Outputs predictor coefficients to `data/processed/r_bar_predictor_v1.json`.
- [x] `reports/v1b_r_bar_forward_predictor.md` — paper-ready writeup with the gate decision.
- [x] Negative-result log entry in `reports/methodology_history.md` (extended 2026-05-03 entry).

**Result.** Sample: 458 train weekends + 173 OOS weekends, dependent variable r̄_w with std ≈ 0.010 train / 0.011 OOS. Six model variants tested:

| ID | Features | R²(train) | R²(OOS) |
|---|---|---:|---:|
| M0_ar1 | r_bar_lag1 | 0.003 | **0.005** |
| M1_vol_ols | macro vol level + Δ (6 features) | 0.079 | −0.060 |
| M1_vol_ridge1 | M1 + α=1 | 0.079 | −0.060 |
| M2_full_ols | M0 ∪ M1 ∪ panel/calendar/regime (13 features) | 0.112 | −0.057 |
| M2_full_ridge1 | M2 + α=1 | 0.112 | −0.058 |
| M2_full_ridge10 | M2 + α=10 | 0.111 | −0.050 |

All non-trivial models (M1, M2) have negative OOS R² — they overfit on TRAIN and predict worse than the train mean on OOS. The autoregressive baseline (M0_ar1) has R²(OOS) = 0.005, effectively zero. Cross-sectional within-weekend ρ on OOS PITs barely moves: raw ρ = 0.4147 → after partial-out ρ = 0.4134 (the predictor brings essentially no information beyond what factor_ret already absorbs).

Three diagnostic findings:

1. **r̄_w has no autoregressive structure week-over-week.** R²(M0_ar1) ≈ 0.005 means the prior-weekend common-mode residual carries effectively no signal about the next weekend's. This is consistent with a martingale residual that the factor_ret point already partials out at the per-row level.
2. **Friday-close macro vol features overfit.** R²(train) is non-trivial (~0.08–0.11) for the vol family but R²(OOS) is negative across all regularisation strengths. The vol features predict TRAIN noise, not OOS signal.
3. **The factor-adjusted point is doing more work than expected.** factor_ret (futures-implied weekend gap) absorbs nearly all of what Friday-close macro state can predict about r̄_w. What remains in r̄_w is approximately unpredictable from currently-observable Friday state.

**Decision: REJECT at the current data surface.** AMM-track is not deployable from Friday-close-only state with the v1b_panel feature set.

**Architectural implication for `reports/active/m6_refactor.md` Phase B.** Phase B is **deferred indefinitely** under current data. Two roadmap paths forward, neither blocked on each other:

- **Path 1 — Sunday-Globex republish architecture.** ES/NQ Sunday 18:00 ET reopen. By Sunday evening the futures-implied Monday gap is a strong predictor of r̄_w (likely R²(OOS) > 0.5 ex-ante). Requires: (a) a scryer fetcher for Sunday-evening futures snapshots, (b) a Soothsayer publisher daemon that re-publishes the band Sunday at Globex reopen with the AMM-track applied, (c) consumer documentation that AMM-track has a "Friday-close + Sunday-republish" cadence, distinct from Lending-track's Friday-close-only cadence. This is the cleanest path; engineering-gated, ~3–4 weeks of work including scryer items.
- **Path 2 — V3.1 F_tok signal accumulation.** On-chain xStock cross-section on `soothsayer_v5/tape` is a near-perfect proxy for r̄_w by construction (the cross-sectional mean of weekend xStock drift is ≈ r̄_w). Today (~30 weekends since launch) is too small for the predictor to fit reliably. ETA Q3–Q4 2026 once ≥ 150 weekends accumulate. Data-gated, no engineering required until the gate fires.

**Headline reframe.** The M6c "ceiling" of 271 bps at τ=0.95 (39% narrower than v1) is now correctly framed as a *data-accumulation-gated* future state, not a near-term deployment target. M6b2 (Lending-track, ships next per `reports/active/m6_refactor.md` Phase A) delivers ~50% of M6c's gain over M5 with no data dependency.

**Decision: REJECT (Friday-close only); reopen as W8b (Sunday-Globex variant) or W8c (V3.1 F_tok variant) when the respective data surfaces are ready.**

---

## W9 — v3 per-symbol-calibration bake-off (C1 / C2 / C4 vs M5)

**Status:** Complete 2026-05-03. Decision: **freeze M5 as Paper 1**; route candidates as roadmap evidence.

**Trigger.** §10 robustness pass surfaced a bimodal per-symbol Kupiec failure on M5 (SPY/QQQ/GLD/TLT/AAPL bands too wide; TSLA/HOOD/MSTR too narrow; HOOD fails Kupiec at τ ∈ {0.68, 0.85, 0.95}). Hypothesis: (A) per-symbol scale heterogeneity is the dominant disease; (B) cross-sectional within-weekend common-mode is the orthogonal residual. Three candidate methodologies attack (A); none attack (B) directly.

**Method.** Same panel, same train/OOS split (2023-01-01), same four served τ. δ-shift held at zero; c(τ) refit per variant. σ̂_sym(t) = trailing-26-week relative-residual std per symbol, strictly pre-Friday. Symbol-class mapping from the deployed M6b2 lending sidecar.

**Result (pooled τ=0.95, 1,730 OOS rows):**

| Variant | Realised | HW (bps) | Δ vs M5 | n_pass per-symbol Kupiec |
|---|---:|---:|---:|---:|
| M5 baseline | 0.9503 | 354.9 | — | 2/10 |
| C1 LWC + regime | 0.9503 | 385.3 | +8.6% | **10/10** |
| C2 M6b2 class | 0.9503 | **302.6** | **−14.7%** | 8/10 |
| C4 stacked | 0.9555 | 379.6 | +7.0% | 9/10 |

ρ_cross unchanged across all variants (0.249–0.280) — none of these address (B).

**Decisions:**

- **C1 LWC + regime — DEFER (lead future candidate, not adopted).** Best per-symbol calibration; pays 8.6% on width. Promote to Paper 1 §10.4 as v3 per-symbol-calibration lead candidate. Re-evaluate as a candidate v3 primitive after V3.2 rolling-rebuild pipeline + paper-grade walk-forward.
- **C2 M6b2 class — HAND OFF (Paper 3 lending-track).** Already deployed for Lending profile. The −14.7% sharpness story belongs in Paper 3's per-class collateral-buffer narrative (Kamino/MarginFi reserve evaluation), not in Paper 1 main body. Paper 1 §10.4 mentions briefly.
- **C4 stacked — REJECT.** Double-counts per-symbol scale (LWC standardises score; class cells already partition by scale). c(τ) degenerates to 1.000 at every τ. Pareto-dominated by both C1 and C2.
- **M6a common-mode partial-out — already on hold (W8 rejected).** Independent gate on Friday-observable r̄_w predictor; Paper 1 §10.4 cross-references W8's deferral.

**Decision rationale.** The bake-off ran *after* Paper 1's validation loop closed. Promoting C1 or C2 into the main paper methodology would invite a "how many variants did you try before selecting this?" review question. M5 is the validated calibration-transparent endpoint-band primitive; the bake-off is roadmap evidence informing v3 specialisation, not a retroactive paper revision.

**Evidence.** `reports/v3_bakeoff.md`, `reports/tables/v3_bakeoff_{pooled,per_symbol,mechanism}.csv`, `scripts/run_v3_bakeoff.py`.

---

## Cleanup (when this doc is empty)

- [ ] Every workstream above has a terminal decision recorded.
- [ ] Findings that warranted methodology changes have entries in `reports/methodology_history.md`.
- [ ] Findings that didn't warrant changes have a one-line "considered and dropped" entry in the methodology log.
- [ ] **Delete this file (`reports/active/validation_backlog.md`).**
