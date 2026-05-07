# Paper 1 — paper-change recommendations for the wording agent

**Started:** 2026-05-06. **Source:** the methodology work documented in `reports/active/paper1_methodology_revisions.md`. This doc aggregates only the *paper-text* recommendations — section-keyed, with specific replacement / addition text. Reproducibility numbers and full mechanism explanations live in the methodology work doc; this one is the editing brief.

**Convention.**
- "Current method" = M6 LWC (deployed). The paper headline should centre on it and proper external baselines (GARCH(1,1)-t, Binom(10, τ̄) independence, Student-t copula) — *not* on M5 vs M6 framings. M5 stays in §7 ablation as the named architectural-ablation reference; do not pull M5 into §6.5 / §6.6 head-to-head paragraphs that aren't already there.
- All numbers are reproducible from `reports/tables/paper1_*.csv` artefacts cited per item.

---

## Highest-leverage structural addition

### NEW subsection §6.x or §11 — "Asymmetric failure modes"

**This is the single most important addition.** Five separate findings (§6.6 mean-jump, §7.4 split anchor + regime cutoff, §9.2 CUSUM alarms, §10.1 path-fitted at lower τ) all point the same direction — toward over-coverage / over-conservatism. Naming the asymmetry as a coherent architectural property converts five scattered disclosures into one contribution.

**Recommended location:** between §9 (limitations) and §10 (future work) as a "characterisation of limits" bridge. Or §6.x as a results-side claim.

**Text to insert (single paragraph):**

> *"Across the empirical results above, every documented M6 LWC failure mode points the same direction — toward over-coverage rather than under-coverage. (i) TUNE windows containing outlier weekends inflate c(τ) (§7.4): the 2024 TUNE anchor over-covers at τ=0.95 to 0.9754 because c(0.95) inherits the BoJ-inflated tail. (ii) The deployed VIX quartile cutoff q=0.75 (§7.4) is convention-anchored; three alternates {q=0.60, 0.67, 0.80} deliver 1.7–2.8 % narrower bands at preserved calibration — the deployed value over-pays in width. (iii) Under a +Δ conditional-mean shift (§6.6), σ̂ EWMA absorbs the bias as variance and over-deflates standardised scores on low-σ symbols, producing over-coverage with phase transition σ*(Δ) ≈ Δ/(q·c − 1). (iv) The §9.2 τ-stratified CUSUM bank fires an S− (over-coverage) alarm at 2024-09-27, two months after BoJ — c(τ=0.85) inherits the BoJ-inflated tail and over-covers in the calm recovery. (v) Path-fitted scoring at lower τ ∈ {0.68, 0.85} introduces over-coverage that DQ catches as violation clustering (§10.1). The mechanism is structural: σ̂ EWMA reads unexplained residual energy as scale and inflates bands; the `fit_c_bump_schedule` grid searches the smallest bump achieving nominal coverage but cannot shrink; the regime cutoff is set by convention rather than width-optimisation. The deployed architecture's asymmetry — failing toward sharpness deficit rather than coverage-contract violation — is a design property, not an accident, and the kind of asymmetry a calibration-transparent oracle servicing collateral protocols should exhibit by construction."*

---

## §3.4 / §6.3 — headline restructure (held-out at *both* time and symbol)

The τ=0.95 headline can now be reported as held-out on two orthogonal axes. Replace any existing fit-on-evaluate language at this anchor with:

> *"At τ=0.95 the headline is held-out on two orthogonal axes: temporal (c fit on 2023 alone, evaluated on 2024-01-05 → 2026-04-24 — realised 0.9504, Kupiec p=0.947, Christoffersen p=0.989, per-symbol Kupiec 10/10) and symbol (LOSO realised coverage 0.9497 ± 0.0128 across held-out symbols). The result is stable across TUNE anchors {2021, 2022, 2023}: realised coverage at τ=0.95 lies in [0.9474, 0.9524] with per-symbol Kupiec 10/10 preserved across all four anchors {2021, 2022, 2023, 2024}."*

**Robustness sub-disclosure** (one line):

> *"The 2024 TUNE anchor over-covers at 0.9754 because TUNE-2024 includes the 2024-08-05 BoJ unwind, inflating c(0.95) to 1.175. Per-symbol Kupiec still passes 10/10. This is a contract-favourable sharpness deficit, not under-coverage."*

**Lower-τ disclosure** (one line, replacing the §9.3 OOS-fit-provenance text):

> *"c(τ ∈ {0.68, 0.85}) fit on 2023-only inherits the slice's elevated banking-crisis-weekend volatility, producing over-coverage on the 2024+ eval slice (realised 0.712 / 0.870 vs nominal). The over-coverage is a sharpness deficit, not a coverage-contract failure; the deployed c(τ) on full OOS averages this out."*

§9.3 OOS-fit-provenance disclosure can shrink dramatically — only the lower-τ over-coverage remains. (Source: A2 + A2.6, `reports/tables/paper1_a2_nested_holdout_c_tau.csv`, `paper1_a2_6_tune_anchor_robustness.csv`.)

---

## §6.3.4 / §6.3.5 — joint-tail baseline upgrade (Binom → t-copula)

Replace "vs binomial 1.15%" with a three-baseline table:

| τ | P(k_w ≥ 3) emp | Binom (independence) | Gaussian copula | t-copula (ν=6.04) |
|---|---|---|---|---|
| 0.85 | 22.5 % | 16.8 % | 36.2 % | 36.2 % |
| 0.95 |  4.6 % |  1.1 % |  6.7 % |  8.2 % |
| 0.99 |  0.6 % |  0.0 % |  0.9 % |  1.3 % |

**Variance-overdispersion lead** (replace the τ=0.95-specific "2.32×" framing):

> *"Empirical k_w over-disperses 2.34× vs Binom independence and 0.63× vs a Student-t copula at every served τ ∈ {0.68, 0.85, 0.95, 0.99}. The independence baseline is robustly misspecified by a uniform factor across the τ range, indicating systematic joint-tail dependence rather than a τ-specific calibration anomaly. The empirical k_w distribution sits inside a properly specified joint-baseline envelope."*

**§6.3.5 BoJ vignette upgrade** (quote both numbers):

> *"Under a Student-t copula with ν̂ = 6.04 and empirical correlation R̂ (mean off-diagonal 0.36), P(k_w = 10) at τ = 0.85 is 0.21 % — i.e., the 2024-08-05 BoJ unwind is a ~1-in-475-weekends event under a properly specified joint baseline, not a freak. The independence baseline puts the same event at ~1-in-10,000 weekends; the residual structure §6.3.4 / §9.4 documents is exactly the gap between these two figures."*

(Source: A3, `reports/tables/paper1_a3_joint_baseline_kw_distribution.csv`, `..._summary.csv`.)

**§9.4 framing tweak.** Reposition the residual as "documented joint dependence with structure consistent with a Student-t copula at ν ≈ 6 with empirical correlation R̂ averaging cluster-heterogeneous components" — *not* as "a residual the architecture cannot characterise". The residual now has a *name* (cluster topology), a *parametric envelope* (t-copula at ν≈6), and a *structural mechanism* (equity vs safe-haven cluster topology) — see §9.4 / §10 below.

---

## §9.4 / §10 — cluster topology of the residual + cluster-conditional architecture

A1 + A1.5 + F3 together name the residual structure precisely. §9.4 should adopt:

> *"The residual is a within-weekend cluster structure separating equities (8 symbols, positively correlated with the weekend equity factor) from safe-haven assets (GLD, TLT, with negative or near-zero correlation to the equity factor). A naive non-parametric partial-out using either the within-weekend median or mean reduces ρ̂_cross from 0.41 to {0.12, 0.06} but breaks per-symbol Kupiec on the safe-haven cluster (GLD violation rate 14.5 %, TLT 9.2 % under the median variant; 5/10 per-symbol pass under the mean variant) and rejects DQ at τ ∈ {0.68, 0.85}. The mechanism is structural: subtracting an equity-dominated weekend median from a negatively-correlated asset creates fresh violations on equity-rally weekends and pulls residuals toward the band centre on selloff weekends. Any operation that treats the panel as exchangeable inherits this failure mode; a working architecture-level fix must respect the cluster topology."*

**Cross-reference to A3 (clean tightening):**

> *"The over-dispersion of the homogeneous t-copula in §6.3.4 (emp/t variance 0.63 at τ=0.95) and the cluster failure of the naive partial-out are two views of the same equity-vs-safe-haven structure: a single Pearson R̂ averages high equity-equity correlations against negative equity-safe-haven correlations; a single weekend median centres on the equity cluster's mean. Either rendering of the panel as homogeneous misses the same topology."*

**§10 architectural recommendation — collapsed from three pointers into one paragraph (replaces scattered cross-sectional partial-out / path-fitted bullets):**

> *"The cluster-internal partial-out (within the equity cluster reduces ρ̂_within from 0.477 to 0.077, per-symbol Kupiec preserved 8/8, half-width −11.6 % at τ=0.95) and the path-fitted conformity score (library-grade, unit-tested per `compute_score_lwc_path`) compose into a τ-conditional architectural recommendation: at τ ≥ 0.95, cluster-conditional + path-fitted is empirically calibrated (DQ p=0.912 at τ=0.95 on the equity cluster) and provides path coverage as an operational primitive; at τ < 0.95, endpoint scoring on the unpartialled residual remains the dominant test (path extrema introduce within-symbol temporal autocorrelation in the violation series that DQ catches at body-of-distribution τ; baseline_path rejects DQ p=0.000 at τ ∈ {0.68, 0.85} even without partial-out). The architectural recommendation is τ-conditional and bounded, not blanket."*

(Sources: A1, A1.5, B6, F3 — `paper1_a1_*.csv`, `paper1_a1_5_*.csv`, `paper1_f3_*.csv`.)

---

## §6.5 — head-to-head against external practitioner baseline (GARCH-t)

**Single-number summary** (replaces or extends the existing four-anchor-row read-off):

> *"Under proper scoring rules, the deployed M6 LWC architecture dominates the GARCH(1,1)-t practitioner baseline at every served τ. Winkler interval score (bps of fri_close, lower = better) at τ=0.95: LWC 992 vs GARCH-t 1,139 (−12.9 %). The advantage grows with τ — at τ=0.99 LWC is 18 % below GARCH-t. Pooled CRPS over the served coverage range: LWC 80.7 vs GARCH-t 92.6 (−12.8 %)."*

(Do not pull M5 into this paragraph; M5's role is the architectural-ablation reference under §7, not the practitioner-baseline comparator. M5 vs LWC under Winkler/CRPS can land in the existing §7 ablation table without restructuring the §6.5 headline.)

(Source: C1, `reports/tables/paper1_c1_winkler_interval_score.csv`, `..._crps.csv`.)

---

## §6.6 — DGP-D upgrade + new mean-jump DGP-E disclosure

**(a) Replace 3× variance break with 10×/50-week transient.** The paper's §6.6 DGP-D narrative tightens and matches real-world stress (COVID-month vol multiplier was ~5× for 6–8 weeks). Per-symbol Kupiec pass rate stays 99.9 % at the upgraded stress; the §6.6 narrative becomes:

> *"M6 LWC's adaptive σ̂ tracks even 10× variance shocks for 50 weekends within the EWMA half-life of 8 weekends; the synthetic stress matches real-world weekend events (2024-08-05 BoJ unwind, March-2020 COVID weekends) and the architecture absorbs them with no per-symbol Kupiec degradation."*

**(b) Add new DGP-E mean-jump disclosure with closed-form phase-transition formula:**

> *"A complementary stress test — a discrete +Δ conditional-mean shift at the OOS boundary, variance unchanged — exposes a location-shift limitation that the σ̂-standardisation does not absorb. σ̂ EWMA on the post-shift residual stream sees apparent variance σ̂² ≈ σ_true² + Δ², inflating bands across the panel and over-deflating the standardised score on symbols whose σ_true falls below the phase-transition threshold:*
>
> *σ*(Δ) ≈ Δ / (q·c − 1)*
>
> *At deployed q_r(0.95)·c(0.95) ≈ 2.23, σ*(Δ) ≈ 0.81·Δ — empirically validated across Δ ∈ {100, 200, 400} bps within 4 % of the closed-form prediction. Symbols with σ_true < σ*(Δ) over-cover (sharpness deficit, contract-favourable); symbols with σ_true ≥ σ*(Δ) remain calibrated. A complementary location-shift detector — CUSUM on the standardised residual mean, composable with §9.2's violation-rate CUSUM bank — closes this gap at the monitoring layer."*

(Sources: C3, F2, F2.5 — `paper1_c3_stronger_dgp_d.csv`, `paper1_f2_mean_jump_bimodality.csv`, `paper1_f2_5_sigma_star_formula.csv`.)

---

## §7.4 — ablation table + 3-gate frame extensions

§7.4's ablation framework already has the σ̂-rule three-gate criterion. Add two new rows for the regime cutoff and split anchor:

**(a) Regime quartile cutoff q (1 scalar; deployed q = 0.75).**

> *"Across q ∈ {0.60, 0.67, 0.70, 0.75, 0.80, 0.90}, 5 of 6 candidates satisfy Gates 1+1b+2 (pooled Kupiec at all τ, pooled Christoffersen at all τ, per-symbol Kupiec 10/10). Bootstrap CI on Δhw% at τ=0.95 vs deployed: q=0.60 −2.76 % [−3.80, −1.73], q=0.67 −1.78 % [−2.66, −0.87], q=0.80 −1.70 % [−2.11, −1.32], q=0.70 +1.73 % [+0.85, +2.71]. The deployed q=0.75 is convention-anchored rather than width-optimal; three alternates deliver 1.7–2.8 % narrower bands at preserved calibration. The differences are operationally small (~5 bps on a 370 bps τ=0.95 headline)."*

**(b) Split anchor (1 scalar; deployed 2023-01-01).**

> *"Across {2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01}, realised τ=0.95 coverage stays in [0.9503, 0.9539]; Kupiec p ∈ [0.35, 0.96]; Christoffersen p ∈ [0.12, 0.67]; per-symbol Kupiec 10/10 across all four anchors. The deployed split anchor is robust."*

After these two rows, the §7.4 disclosure-DOF count goes from 16 to **19 scalars**, all with proper-ablation provenance. The "16 scalars undercounts DOF" critique closes.

(Sources: B1, `reports/tables/paper1_b1_regime_threshold_ablation.csv`, `..._hw_bootstrap.csv`, `m6_lwc_robustness_split_sensitivity.csv`.)

---

## §6.4 / §3.4 — per-symbol Kupiec at τ=0.99 power disclosure

Add an MDE caveat to the per-symbol τ=0.99 row:

> *"Per-symbol Kupiec at τ=0.99 has minimum detectable effect ≈ 3 pp under-coverage and is undetectable for over-coverage given the per-symbol expected violation count of 1.73. The 10/10 pass should be read as 'no per-symbol violation rate is statistically distinguishable from 1 % at the resolution Kupiec offers per-symbol', not as a 1 pp-tolerance certificate. Pooled Kupiec at τ=0.99 has minimum detectable effect 1.0 pp; the pooled p=0.94 is the τ=0.99 statistical claim that does have 1 pp resolution."*

(Source: B3, `reports/tables/paper1_b3_kupiec_power_mde.csv`.)

---

## §5 — regime classifier internal-consistency disclosure

Add one paragraph to §5 (or §9 limitations) on VIX vs GVZ/MOVE robustness:

> *"The regime classifier uses VIX (equity vol index) as the high-vol gate for all symbols, including GLD (gold) and TLT (long-dated treasury) which have asset-specific vol indices (GVZ, MOVE). A sensitivity ablation that swaps GLD's regime gate to GVZ and TLT's to MOVE — flipping the regime tag on 23 % of GLD weekends and 28 % of TLT weekends — leaves the pooled τ=0.95 headline coverage unchanged at 0.9503 (Kupiec p=0.956), per-symbol Kupiec 10/10, and half-width within 0.1 %. The M6 σ̂-standardisation absorbs the regime-tagging difference structurally; the regime cell contributes a small marginal adjustment via q_r(τ), not a load-bearing scale separation."*

(Source: B4, `reports/tables/paper1_b4_regime_index_sensitivity.csv`.)

---

## §4.6 — Mondrian-CP exchangeability empirically supported

Replace the implicit-assumption framing with empirical support:

> *"Mondrian-CP's finite-sample coverage guarantee depends on within-bin exchangeability. A permutation test on the lag-1 score autocorrelation within each (regime × symbol) bin (n = 19–116, 30 bins, OOS 2023+) finds 1/30 nominally rejecting at α=0.05 (none after BH correction) and 0/30 at α=0.01 — under-rejection vs the 5 % / 1 % expected under exchangeability. Within-bin exchangeability is empirically supported. The §6.3.6 / §9.4 cross-sectional dependence is *across* bins, not within."*

(Source: B2, `reports/tables/paper1_b2_exchangeability.csv`.)

---

## §6.3.4 footnote — pairs-block-bootstrap CI preempt

Add a one-line footnote to §6.3.4:

> *"Cross-sectional within-weekend dependence (ρ̂_cross = 0.41) is respected by all reported CIs via weekend-block bootstrap. Temporal autocorrelation across weekends is empirically null — lag-1, lag-2, lag-4 ρ̂ on weekly k_w lie in [−0.07, 0.03] across served τ — so a moving-block-bootstrap with block lengths L ∈ {4, 8, 13} produces CIs within Monte Carlo noise of the L=1 (i.i.d.-weekend) baseline."*

(Source: B5, `reports/tables/paper1_b5_kw_block_bootstrap.csv`.)

---

## §9.2 — τ-stratified CUSUM bank (replaces "passive forward-tape observation")

Replace generic forward-tape language with the calibrated CUSUM bank:

> *"Beyond passive forward-tape observation, the deployed system carries a two-sided Page CUSUM drift monitor at each served τ. Calibrated thresholds h ∈ {0.40, 0.40, 0.30} for τ ∈ {0.85, 0.95, 0.99} produce mean in-control run length ≈ 225 weekends (one expected false alarm per ~4.3 years). Detection power against an operationally relevant 2× violation-rate drift: ~83 % with median latency 5 / 11 / 28 weekends at τ ∈ {0.85, 0.95, 0.99}; against 3× drift: 2 / 5 / 14 weekends.*
>
> *On the 173-week OOS slice, the τ=0.85 CUSUM fires S+ alarms at both 2023-03-10 (SVB collapse, k_w=7) and 2024-08-02 (BoJ unwind, k_w=10) — the two canonical stress weekends in the OOS window — with the post-BoJ S− alarm at 2024-09-27 catching the over-conservative recovery period documented under §7.4 split-anchor robustness. CUSUM banks at τ ∈ {0.95, 0.99} fire on different weekends: pairwise coincidence with τ=0.85 = 2 of 7 alarms; pairwise coincidence between τ=0.95 and τ=0.99 = **0 of 7 alarms**. Each anchor's monitor surfaces a structurally distinct aspect of drift — body-of-distribution shift at τ=0.85, near-tail at τ=0.95, deep-tail mass at τ=0.99 — confirming the τ-stratified CUSUM bank is a multi-resolution detector rather than a redundant signal."*

(Sources: C2, F1, `reports/tables/paper1_c2_cusum_drift.csv`, `paper1_f1_cusum_alarm_*.csv`.)

---

## §10.1 — path-fitted conformity score (now library-grade + τ-conditional)

§10.1's path-fitted bullet upgrades:

> *"Methodology is library-grade and unit-tested (`soothsayer.backtest.calibration.compute_score_lwc_path`). An empirical first-cut on the CME-projected subset (n=1,557 OOS rows) confirms mechanical correctness. The architectural recommendation is **τ-conditional**: path-fitted scoring at τ ≥ 0.95, where path coverage is the operational concern and the cluster-conditional + path-fitted combination is empirically calibrated (DQ p=0.912 on the equity cluster + CME-projected subset); endpoint scoring at lower τ ∈ {0.68, 0.85}, where path extrema introduce within-symbol temporal autocorrelation in the violation series that DQ rejects (path-fitted baseline alone rejects DQ p=0.000 at τ ∈ {0.68, 0.85} regardless of partial-out). The binding empirical question — does path-fitting close the §6.6 perp / on-chain residual gap on consumer-experienced path data — accumulates as the V5 forward-cursor tape (continuous capture since 2026-04-24) crosses N≥300 path-coverage weekends."*

(Sources: B6, F3 — `tests/test_path_fitted_score.py`, `m6_lwc_robustness_path_fitted.csv`, `paper1_f3_*.csv`.)

---

## What NOT to add

These items have explicit "do not push to paper" guidance:

- **M5 vs LWC head-to-head paragraphs in §6.5 / §6.6.** M5's role is the §7 architectural-ablation reference. Existing §7 already includes M5; do not pull M5 into §6.5 / §6.6 head-to-head paragraphs (those should centre on M6 LWC + GARCH-t / Binom independence / t-copula proper baselines).
- **Block-correlation / two-factor copula refinement of §6.3.4.** The cluster topology from §9.4 + the homogeneous t-copula bracket from §6.3.4 are sufficient for paper 1. A copula that respects cluster structure is a §10 mention at most.
- **F1 alarm timing on a longer OOS window.** Forward-tape accumulation is the natural way to grow this; do not speculate beyond the 7-alarm sample at each τ.
- **F3 endpoint-score behaviour at τ ≥ 0.95.** Already handled by existing §6 endpoint results; F3's τ-conditional split doesn't require revisiting endpoint behaviour.
- **Speculation about hypothetical future stress events.** F1's "monitor catches stress" claim should anchor on the two empirically observed events (SVB, BoJ); avoid framing as "would catch any future event" or similar.

---

## Editing order suggestion

1. Add the **§6.x / §11 asymmetric-failure-modes subsection** first — it sets the architectural framing the rest of the additions slot into.
2. **§6.3 / §3.4 headline restructure** + **§6.3.4 / §6.3.5 joint-tail upgrade** — these are the most-cited results; the rest reference back to them.
3. **§9.4 / §10 cluster topology + τ-conditional architecture** — replaces multiple scattered bullets with a coherent paragraph.
4. **§9.2 CUSUM bank section + §10.1 path-fitted upgrade** — adds the operational story.
5. **§7.4 ablation rows + §6.4 power disclosure + §5 regime sensitivity + §4.6 exchangeability + §6.3.4 footnote** — these are smaller per-section additions, slot in last.
6. **§6.5 GARCH-t head-to-head + §6.6 DGP upgrade** — single-paragraph additions.

Total: ~10 paragraph additions + 2 new subsections, no full-section rewrites. Numbers all in `reports/tables/paper1_*.csv` artefacts; mechanism explanations live in `reports/active/paper1_methodology_revisions.md` if a hand-off question comes up.
