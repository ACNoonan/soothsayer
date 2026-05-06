# Paper 1 — methodology revisions work doc

**Started:** 2026-05-06. **Status:** in flight, parallel to wording-revision agent.

Working tracker for the methodology tweaks raised in the 2026-05-06 review pass. Forward-tape items (path-coverage N≥300, forward-tape N≥13) are excluded — collection is in progress and not blocking this list.

Each item lists: **goal / why / scope / status / result**. Result rows are filled in as we land them; everything below `Status: pending` is forward-looking spec.

---

## Tier A — highest leverage for defensibility

### A1. Cross-sectional common-mode partial-out, run on M6 LWC + Berkowitz/DQ

**Goal.** Test whether subtracting the within-weekend median (or factor-weighted) residual *before* the M6 LWC conformity score materially reduces ρ̂_cross and improves Berkowitz/DQ. Either result is publishable: a positive result tightens the band at matched coverage; a null result closes the §9.4 disclosure properly as a negative result.

**Why this is different from the existing M6a script.** `scripts/run_m6a_common_mode_partial_out.py` uses regression-fitted β on the *raw M5 baseline* score and is sold as a forward-looking diagnostic upper bound (β·r̄_w uses Monday data). What we need now: (a) the partial-out applied on the *deployed M6 LWC* score, (b) median (not regression β) within weekend so the operation is non-parametric, (c) Berkowitz / DQ / per-symbol Kupiec on the PITs, not just width and ρ.

**Scope.**
- New script `scripts/run_paper1_a1_common_mode_partial_out_m6.py` (don't overwrite the M6a script — it's referenced from §10).
- Two variants: (i) leave-one-out weekend median; (ii) factor-weighted within-weekend mean.
- Apply partial-out *to the signed residual* before computing |·| / (fri_close · σ̂_sym). Re-fit per-regime conformal quantile and c(τ) bump on TRAIN only.
- Evaluate on OOS 2023+: Kupiec, Christoffersen, Berkowitz, Engle-Manganelli DQ, ρ̂_cross, mean half-width at τ ∈ {0.68, 0.85, 0.95, 0.99}.
- Output table: `reports/tables/paper1_a1_common_mode_partial_out_m6.csv` + writeup.

**Status:** ✅ complete 2026-05-06. **Verdict: clean negative result — partial-out reduces the disclosed ρ̂_cross sharply but destroys the per-symbol Kupiec 10/10 headline and worsens DQ at lower τ. §9.4 closure: the disclosed residual is not removable by a simple non-parametric residual operation.**

**Implementation.** `scripts/run_paper1_a1_common_mode_partial_out_m6.py`. Three variants on the deployed M6 LWC pipeline (σ̂ EWMA HL=8, Mondrian by `regime_pub`, split = 2023-01-01):
- `baseline_no_po` — current §6 headline (no partial-out)
- `partial_out_loo_median` — r_i^{po} = r_i − median_{j≠i in weekend w}(r_j)
- `partial_out_loo_mean`   — r_i^{po} = r_i − mean_{j≠i in weekend w}(r_j)

Each variant: per-regime CP quantile on TRAIN (4,186 rows), c(τ) bump on OOS (1,730 rows × 173 weekends), full-distribution Berkowitz on dense-grid PITs, DQ at each τ, per-symbol Kupiec at τ=0.95.

**Result tables.**
- `reports/tables/paper1_a1_common_mode_partial_out_m6.csv` — pooled by τ × variant
- `reports/tables/paper1_a1_common_mode_partial_out_m6_summary.csv` — Berkowitz / ρ̂_cross
- `reports/tables/paper1_a1_common_mode_partial_out_m6_per_symbol.csv` — per-symbol Kupiec

**Headline numbers:**

| variant | ρ̂_cross | τ=0.95 cov | τ=0.95 hw bps | per-sym Kupiec | DQ p (0.85) |
|---|---|---|---|---|---|
| baseline | **0.4147** | 0.950 | 370.6 | **10/10** | 0.975 |
| LOO median partial-out | **0.1234** | 0.950 | 363.8 (−1.8 %) | 7/10 | 0.000 |
| LOO mean partial-out   | **0.0568** | 0.950 | 413.7 (+11.6 %) | 5/10 | 0.000 |

(Baseline ρ̂_cross is 0.4147 on the OOS slice with the deployed σ̂ rule — slightly above the 0.354 quoted in §6.3.6 because that number was computed on the v1 panel ordering convention; both numbers reflect the same residual.)

**Per-symbol Kupiec failure pattern.** Median variant fails GLD (viol-rate 14.5 %), QQQ (0.6 %), TLT (9.2 %). Mean variant additionally fails HOOD, NVDA at τ=0.95. Mechanism: the within-weekend median is dominated by the equity cluster (AAPL, GOOGL, MSTR, NVDA, QQQ, SPY, TSLA = 7/10 symbols). Subtracting the equity common-mode from GLD/TLT — which are *negatively* correlated with the equity factor over weekend horizons — pushes their residuals to the wrong side of the band on equity-rally weekends and toward the centre on equity-selloff weekends; the directional distortion translates directly into bilateral coverage failure.

**Why Berkowitz LR doesn't improve.** Pooled Berkowitz LR is ≈10⁴ in all three variants. The LR is dominated by `var(z) ≪ 1` (z-scores compressed near zero by the PIT-from-quantile-grid construction with min anchor τ=0.05); the lag-1 ρ on z under (fri_ts, symbol) ordering is small (−0.03 to −0.07) for all variants. ρ̂_cross is on the *signed residual*, not on Φ⁻¹(PIT) — Berkowitz isn't sensitive to the same channel. Reading: the §6.3 framing that "Berkowitz/DQ both detect cross-sectional common-mode" is correct that the residual is non-zero, but the partial-out-vs-Berkowitz comparison is structurally weaker than the partial-out-vs-ρ̂_cross comparison.

**Why DQ *worsens* at lower τ.** Partial-out shifts which symbols violate within a weekend: rows whose signed residual aligns with the within-weekend common-mode see |r^{po}| shrink (no violation), rows whose residual disagrees see |r^{po}| grow (violation). Under (fri_ts, symbol) panel ordering, this concentrates violations on the 1–3 symbols per weekend that move against the cluster — creating fresh AR(1)-equivalent autocorrelation in the violation series that DQ catches. The procedure removes the channel ρ̂_cross detects but installs a different one that DQ detects.

**Implication for paper §9.4.** The disclosure that the residual is "orthogonal to per-symbol scale and addressable only by an architecture that consumes a within-weekend common-mode signal" stands and is now empirically demonstrated, not asserted. A simple naive partial-out is *not* the missing handle: it trades ρ̂_cross for joint-tail conditional miscalibration and per-symbol coverage. A working fix would need to (i) treat the equity / safe-haven clusters separately, (ii) be Friday-observable (the existing W8 prototype's OOS R² < 0.4 made this hard), or (iii) sit at the AMM layer (Paper 4). All three are documented as deferred-with-gates.

**Framing for paper (the negative result is a positive contribution).** Don't write A1 up as "we tried and failed." Write it up as "we empirically characterised the residual." §9.4 currently positions the cross-sectional common-mode as something that "would require Paper 4 territory to fully resolve" — vague. After A1 the paper can say something stronger and standalone:

> *The residual is a within-weekend cluster structure separating equities (7 symbols, positively correlated with the weekend equity factor) from safe-haven assets (GLD, TLT, negatively correlated). A naive non-parametric partial-out using either the within-weekend median or mean reduces ρ̂_cross from 0.41 to {0.12, 0.06} but breaks per-symbol Kupiec on the safe-haven cluster (GLD violation rate 14.5 %, TLT 9.2 % under the median variant; 5/10 per-symbol pass under the mean variant) and rejects DQ at τ ∈ {0.68, 0.85}. The mechanism is structural: subtracting an equity-dominated weekend median from a negatively-correlated asset creates fresh violations on equity-rally weekends and pulls residuals toward the band centre on selloff weekends. Any operation that treats the panel as exchangeable inherits this failure mode; a working architecture-level fix must respect the cluster topology.*

That tells the reader **what kind of structure the residual has and why three different naive fixes won't work**. It also makes the §10 deferral (path-fitted score, AMM-layer treatment) concretely motivated. Not "we'll get to it" — "here's why simple things don't work."

**Cross-reference to A3 (added once A3 lands).** A3's t-copula homogeneous correlation slightly over-disperses the empirical k_w distribution (emp/t variance 0.63 at τ=0.95). The over-dispersion of the *homogeneous* t-copula and the cluster failure of the *naive* partial-out are two views of the same equity-vs-safe-haven structure: a single R̂ averages high equity-equity correlations against negative equity-safe-haven correlations; a single weekend median centres on the equity cluster's mean. Either rendering of the panel as homogeneous misses the same topology.

**Numbers / tables.** All reproducible from `reports/tables/paper1_a1_common_mode_partial_out_m6.csv` and `..._per_symbol.csv`.

---

### A2. Nested temporal × symbol holdout for c(τ) bump

**Goal.** Make the headline 0.95 number properly held-out at the *time* level. Today: c(τ) is fit on the OOS 2023+ slice and evaluated on the same slice. LOSO holds out a symbol but not time. Refit c(τ) using **only 2023** as the OOS-tuning anchor, then evaluate on **2024–26** as the true holdout.

**Why.** Current §6.3 headline is fit-on-evaluate at the time level. A 2023-fit / 2024–26-eval split is the cleanest possible defence and is what a referee will demand.

**Scope.**
- New script `scripts/run_paper1_a2_nested_holdout_c_tau.py`.
- Train q_cell^LWC(τ) on pre-2023 (unchanged).
- Fit c(τ) bump on 2023 only (≈ 51 weekends × 10 symbols ≈ 510 rows).
- Evaluate on 2024-01-01 → most-recent-closed weekend (2024 + 2025 + 2026-YTD).
- Compare to the current §6.3 headline: realised coverage, half-width, Kupiec, Christoffersen at τ ∈ {0.68, 0.85, 0.95, 0.99}.
- If headline degrades materially, document and decide whether to retrain c(τ) on the full OOS slice but evaluate-on-holdout-only (the symmetric, more conservative read).

**Status:** ✅ complete 2026-05-06. **Verdict: clean WIN. Headline τ=0.95 is properly held-out at the time level. The fit-on-evaluate concern at the headline operating point is empirically null.**

**Implementation.** `scripts/run_paper1_a2_nested_holdout_c_tau.py`. Three-way temporal split:
- TRAIN = pre-2023-01-01 (4,186 rows × 458 weekends) — per-regime CP quantile, unchanged
- TUNE  = 2023-01-01 → 2023-12-29 (520 rows × 52 weekends) — c(τ) fit slice
- EVAL  = 2024-01-05 → 2026-04-24 (1,210 rows × 121 weekends) — true holdout

Three reporting modes:
- `M_full_fit_on_eval`: q on TRAIN; c on TUNE ∪ EVAL; eval on TUNE ∪ EVAL — current paper convention
- `M_evalsub_full_cb`: q on TRAIN; c on TUNE ∪ EVAL; eval on EVAL only — strips eval-period change
- `M_a2_proper_holdout`: q on TRAIN; c on TUNE only; eval on EVAL — true held-out at time level

**Result tables.** `reports/tables/paper1_a2_nested_holdout_c_tau.csv` (pooled by τ × mode), `_per_symbol.csv` (per-symbol Kupiec at τ=0.95).

**Headline τ=0.95:**

| mode | realised | c(0.95) | Kupiec p | Christoffersen p | hw bps | per-sym Kupiec |
|---|---|---|---|---|---|---|
| M_full (current paper) | 0.9504 | 1.079 | 0.956 | 0.720 | 370.6 | 10/10 |
| M_evalsub (held-out eval, full cb) | 0.9504 | 1.079 | 0.947 | 0.989 | 420.8 | 10/10 |
| **M_a2 (true holdout)** | **0.9504** | **1.079** | **0.947** | **0.989** | **420.8** | **10/10** |

The bump c(τ=0.95) = 1.079 fit on 2023-only is identical to the bump fit on the full 2023+ slice — the τ=0.95 number is *not* fit-on-evaluate sensitive. M_evalsub and M_a2 are identical at τ=0.95: M_a2's c(τ=0.95) coincides with M_full's c(τ=0.95) at three decimal places, and Christoffersen p actually *improves* in held-out mode (0.989 vs 0.720) because the 2024+ slice has cleaner violation independence than the full 2023+ slice. The half-width difference (370.6 vs 420.8 bps) is entirely an eval-slice effect: 2024+ contains a higher-vol mix (2024-08-05 BoJ, 2025-04 tariff weekend) that widens σ̂.

**Lower τ — over-coverage rejection in held-out mode.** At τ=0.68, M_a2 realises 0.712 (Kupiec p=0.015 reject); at τ=0.85, realises 0.870 (Kupiec p=0.044 reject borderline). Both rejections are toward *over-coverage* — c(0.68) and c(0.85) fit on TUNE-only are 1.028 / 1.026 (both > 1.0 from TUNE_∪_EVAL fit), inflated because TUNE (2023) included the March banking-crisis weekend. The over-coverage on EVAL is a sharpness deficit, not a coverage-contract failure. M_full's c(0.68) = c(0.85) = 1.0 reflects the full OOS slice averaging that out.

**Implication for paper §6.3 / §3.4.** The τ=0.95 headline can be reported as "held-out at the time level": realised coverage 0.9504, Kupiec p=0.947, Christoffersen p=0.989, per-symbol Kupiec 10/10 — c(τ=0.95) fit on 2023 alone, evaluated on a 2024-01-05 → 2026-04-24 holdout never seen by either q or c. This converts the headline from fit-on-evaluate to properly held-out at no cost to the result.

At τ ∈ {0.68, 0.85} the held-out reading is over-coverage rather than nominal — a sharpness disclosure that should accompany the headline. The mechanism (TUNE-only c(τ) inheriting 2023 banking-crisis tilt) is identifiable and the over-coverage is a one-sided contract-favourable failure.

**Framing for paper — three things to flag.**

**(1) Headline restructure: held-out at *both* time *and* symbol.** The combined picture is now τ=0.95 holds out on two orthogonal axes:
- **Temporal holdout (A2):** c fit on 2023 alone, evaluated on 2024-01-05 → 2026-04-24 — realised 0.9504, Kupiec 0.947, Christoffersen 0.989, **per-symbol Kupiec 10/10**.
- **Symbol holdout (existing LOSO):** realised 0.9497 ± 0.0128 across held-out symbols (5.7× tighter than M5).

These are orthogonal holdouts. Reporting them together makes the headline genuinely held-out, not held-out by construction. **§9.3's OOS-fit provenance disclosure shrinks dramatically** — it now only needs to cover the lower-τ over-coverage in held-out mode, which is a different (and milder) kind of disclosure.

**(2) The half-width shift (370.6 → 420.8 bps) is an *eval-slice composition* effect, not a c-fit effect.** Make this explicit in §6.3 or expect a reviewer comment about "your bands got 14% wider when you held out, what gives?" The right framing:

> *c(0.95) is identical at three decimals across `M_full` (fit on 2023+) and `M_a2` (fit on 2023-only): both 1.079. The half-width difference between modes is entirely an eval-slice effect — the 2024+ holdout contains the 2024-08-05 BoJ unwind and the 2025-04 tariff weekend, both of which inflate σ̂_sym; the 2023 sub-slice was relatively calm in σ̂ terms. Coverage is unchanged (0.9504); the σ̂-conditional band response widened the half-width as it should.*

**(3) Lower-τ over-coverage disclosure — accept it.** A2 over-covers at τ ∈ {0.68, 0.85} (realised 0.712 / 0.870, Kupiec p=0.015 / 0.044). Three options were considered:
- (a) **Accept it.** Report held-out τ ∈ {0.68, 0.85} as 0.712 / 0.870, note that this is a sharpness deficit (one-sided contract-favourable), document the mechanism (TUNE = 2023 inherits banking-crisis volatility, calibrating c(0.68)/c(0.85) higher than the full-OOS average warrants).
- (b) Refit c(τ) per anchor on the most-recent-N-weekends rolling window. More principled but introduces another knob and risks looking ad hoc.
- (c) Report both `M_full` and `M_a2` at all anchors. `M_full` at τ ∈ {0.68, 0.85} hits nominal cleanly; `M_a2` at τ=0.95 is the held-out headline. Lets you have it both ways without overclaiming.

**Decision: option (a).** The over-coverage is honest disclosure, the mechanism is interpretable, and it doesn't undermine the τ=0.95 result. Adding a knob to fix something that isn't broken is worse.

**Verification still owed before locking A2 in.** With ~5 expected violations in 52 TUNE weekends, c(τ=0.99) on TUNE-only could be noisy. The current writeup confirms c(0.95) matches at three decimals between TUNE-only and full-OOS but doesn't show c(0.99). If c(0.99) drifts substantially, that's a separate disclosure to add. Tracked under **A2.5** (Tier A v2) below.

**Numbers / tables.** All reproducible from `reports/tables/paper1_a2_nested_holdout_c_tau.csv` and `..._per_symbol.csv`.

---

### A3. DCC-GARCH or t-copula joint baseline (vs Binom(10, 0.05))

**Goal.** Replace the Binom(10, τ_violation) "independence strawman" comparator for the joint-tail k_w distribution with a properly specified joint-volatility / joint-tail baseline. Whether the empirical k_w lives closer to the joint baseline than to independence is the actual claim a quant risk team would care about.

**Why.** Independence as the only baseline is exactly what the user expects a hostile referee to weaponise. Moving k_w=10/10 from "vs strawman" to "vs properly specified joint model" is the single most-likely-demanded revision.

**Approach.** Two candidate baselines, ordered by implementation cost:
1. **t-copula on per-symbol GARCH-t marginals** — use the Phase 8 per-symbol GARCH-t fits already in `reports/active/phase_8.md`. Estimate empirical Kendall's τ between standardised residuals to pin the t-copula df + correlation matrix; sample 10,000 weekends; compute simulated k_w distribution at each served τ. Implementation: `scipy.stats.t` + Cholesky on the empirical correlation matrix; ~half-day.
2. **DCC-GARCH on the 10-symbol panel** — `arch` package supports DCC. Higher implementation cost; closer to what a CCAR-style risk team would actually run.

Start with the t-copula. Add DCC only if the t-copula result is not decisive against independence.

**Scope.**
- New script `scripts/run_paper1_a3_joint_baseline_kw.py`.
- Inputs: per-symbol GARCH-t fits from Phase 8 (or refit if not persisted), 2023+ standardised residuals.
- Output: empirical k_w distribution + t-copula simulated k_w + Binom(10, τ̄_violation) for τ ∈ {0.68, 0.85, 0.95, 0.99}; KS distance and Wasserstein-1 distance between empirical and each baseline.
- Update §6.3.4 / §6.3.5 narrative based on result (paper edit handed off to wording agent with explicit hand-off note).

**Status:** ✅ complete 2026-05-06. **Verdict: clean WIN. The empirical k_w distribution sits inside the joint-baseline envelope — Binom strawman understates k_w variance by 2.34× (essentially the paper's existing 2.32) but a t-copula on Student-t marginals slightly over-disperses (emp / t variance ratio 0.63). The 2024-08-05 BoJ k_w=10 weekend had P=0.21% under the t-copula vs P=0.0001% under Binom; properly specified, that event is expected once every ~475 weekends, not a freak.**

**Implementation.** `scripts/run_paper1_a3_joint_baseline_kw.py`.

Construction:
- z_i,t = (mon_open − point) / (fri_close · σ̂_sym) — standardised conformity residual under deployed M6 LWC (σ̂ EWMA HL=8). For most symbols σ̂ already absorbs per-symbol volatility, so a per-symbol GARCH-t fit on z is redundant; z's per-symbol marginal is approximately Student-t with ν̂_i, fit by MLE.
- Marginals: per-symbol Student-t with ν̂_i ∈ [4.80, 28.32], median ν̂ = 6.04.
- Copula correlation R̂: empirical Pearson on z, 10 × 10. Mean off-diagonal correlation **0.359** — substantial joint exposure even after σ̂_sym standardisation.
- Three baselines:
  - **Binom(10, τ̄_violation)** — independence strawman the paper currently uses.
  - **Gaussian copula** with R̂ on z.
  - **Student-t copula** with R̂ and df ν̂_copula = 6.04 (median of marginals).
- Simulation: 50,000 synthetic weekends per baseline, regime drawn from empirical OOS regime mix (`normal` 67%, `high_vol` 22%, `long_weekend` 11%); standardised threshold T_r(τ) = q_r(τ)·c(τ) from the deployed M6 fit (q from TRAIN, c from full OOS).

**Result tables.** `reports/tables/paper1_a3_joint_baseline_kw_distribution.csv` (PMF table, k=0..10 per τ × baseline), `paper1_a3_joint_baseline_kw_summary.csv` (tail probabilities + distance metrics).

**Headline τ=0.95:**

| baseline | τ̄_viol | P(k_w ≥ 3) | P(k_w ≥ 5) | P(k_w = 10) | WS-1 vs emp | var ratio (emp / model) |
|---|---|---|---|---|---|---|
| empirical | 0.0497 | **0.0462** | **0.0058** | 0.0000 | — | — |
| Binom(10, τ̄) | — | 0.0114 | 0.0000 | 0.0000 | 0.200 | **2.34** |
| Gaussian copula | — | 0.0669 | 0.0186 | 0.0000 | 0.134 | — |
| t-copula (ν=6.04) | — | 0.0815 | 0.0315 | 0.0001 | 0.180 | **0.63** |

**Pattern across τ.** Variance-overdispersion ratio emp/Binom is **2.34, 2.31, 2.34, 2.35** at τ ∈ {0.68, 0.85, 0.95, 0.99} — independence robustly understates k_w variance by ~2.3× at every served anchor. Versus the t-copula, emp/t is **0.83, 0.54, 0.63, 0.73** — at deep-tail τ ∈ {0.95, 0.99} the t-copula slightly over-disperses; the empirical sits comfortably inside the joint-baseline envelope.

At τ=0.85 (the BoJ-weekend anchor): P(k_w = 10) under empirical = 0.0058 (1/173 weekends), under Binom = 0.0001, under t-copula = **0.0021**. The 2024-08-05 weekend is a ~1-in-475-weekends event under a properly specified joint baseline, not the ~1-in-10,000-weekends event the independence strawman implies. The current §6.3.5 vignette gains a much stronger framing.

**Paper narrative implication.** The current §6.3.4 / §9.4 storyline ("empirical k_w overdisperses 2.32× vs Binomial; the residual is cross-sectional common-mode that requires Paper 4 territory to fully resolve") is *correct* on the variance overdispersion vs independence. What we now have additionally:

1. **Independence is robustly misspecified** at every served τ by the same factor (~2.3×). This is a stronger claim than "the Binom variance is 2.32× too small at τ=0.95"; it's "the Binom variance is uniformly 2.3× too small across the served τ range, indicating a systematic joint-tail dependence rather than a τ-specific calibration anomaly".
2. **A t-copula on Student-t marginals brackets the empirical from above** — the empirical k_w distribution is *less* extreme than what a properly specified joint volatility model would predict. The protocol-design implication: an oracle calibrated against the empirical k_w (the §6.3.4 reserve-guidance threshold k* = 3) is *more* conservative than one calibrated against a t-copula DGP.
3. **The Gaussian copula sits closest in Wasserstein-1 at τ=0.95** (0.134 vs 0.180 t-copula vs 0.200 Binom). At deeper tails (τ=0.99) the copulas pull ahead of Binom by 2× (WS-1 0.027 ≈ 0.025 ≈ 0.060). The pattern: the deeper into the joint tail, the more independence misses; copulas are roughly equivalent to each other in the tail.

**Framing for paper — the substantive shift is bigger than the result tables suggest.** The story moves from "we overdisperse vs a strawman" to four claims:

1. **The joint dependence is real** — mean off-diagonal R̂ = 0.36 in standardised residuals. Worth quoting independently as a panel-level fact.
2. **It has parametric structure** — t-copula at ν̂ ≈ 6 brackets the empirical from above.
3. **Independence is misspecified by ~2.3× variance uniformly across τ ∈ {0.68, 0.85, 0.95, 0.99}** — this is a *systematic-dependence* claim, not a τ-specific anomaly.
4. **The reserve-guidance threshold k* = 3 is conservative against a properly specified joint baseline**, not just against independence.

**Lead operationally with claim (4).** A protocol consuming Soothsayer with k*=3 isn't using a number calibrated against an obvious strawman; it's using a number that holds up against the kind of joint-volatility model a CCAR-style risk team would actually run. That's the defensibility leap.

**§6.3.5 BoJ vignette — quote both numbers explicitly.**

> *Under a Student-t copula with ν̂ = 6.04 and empirical correlation R̂ (mean off-diagonal 0.36), P(k_w = 10) at τ = 0.85 is 0.21 % — i.e., the BoJ weekend is a ~1-in-475-weekends event under a properly specified joint baseline, not a freak. The independence baseline puts the same event at ~1-in-10,000 weekends; the residual structure §6.3.4 / §9.4 documents is exactly the gap between these two figures.*

The contrast (1-in-475 vs 1-in-10,000) is rhetorically powerful. The residual has a *name* and a *parametric envelope*, not just a Berkowitz LR.

**§6.3.4 — three-baseline table replaces "vs binomial 1.15%":**

| τ | P(k_w ≥ 3) emp | Binom (independence) | Gaussian copula | t-copula (ν=6.04) |
|---|---|---|---|---|
| 0.85 | 22.5 % | 16.8 % | 36.2 % | 36.2 % |
| 0.95 |  4.6 % |  1.1 % |  6.7 % |  8.2 % |
| 0.99 |  0.6 % |  0.0 % |  0.9 % |  1.3 % |

**Footnote on copula homogeneity (§10 connection).** The slight over-dispersion of the t-copula vs empirical (emp/t variance 0.63 at τ=0.95) likely reflects that R̂ averages over heterogeneous correlations — equity-equity correlations are higher than equity-safe-haven correlations (which are negative). A block-correlation or two-factor t-copula would fit better. For Paper 1 the single-R̂ t-copula is the right level of complexity; mention block-correlation as a §10 next step.

**Cross-reference to A1 (key tightening).** The over-dispersion of the homogeneous t-copula (A3) and the cluster failure of the naive partial-out (A1) are **two views of the same equity-vs-safe-haven structure**:
- A1: a single weekend median centres on the equity cluster's mean → fails GLD/TLT (negatively correlated with equities) bilaterally.
- A3: a single Pearson R̂ averages high equity-equity against negative equity-safe-haven correlations → over-disperses k_w.

Either rendering of the panel as homogeneous misses the same topology. Quoting this cross-reference in §9.4 (or §6.3.6) tightens the diagnostics narrative considerably — it's the same finding visible through two different aggregations, exactly as the §6.3 framing already pulls Berkowitz/DQ and the k_w distribution together.

**§9.4 framing tweak.** The residual is now positioned as "documented joint dependence with structure consistent with a Student-t copula at ν ≈ 6 with empirical correlation R̂ averaging cluster-heterogeneous components", not as "a residual the architecture cannot characterise". This is a defensibility upgrade — the residual has a *name*, a *parametric envelope*, and a *cluster-topology mechanism*, all empirically grounded.

**Numbers / tables.** All reproducible from `reports/tables/paper1_a3_joint_baseline_kw_distribution.csv` and `..._summary.csv`.

---

## Tier A v2 — follow-ups raised by Tier A results

### A1.5. Cluster-internal partial-out (equity-only / safe-haven-only)

**Goal.** Test whether the failure of A1's naive partial-out is genuinely a cluster-topology problem, or something deeper. Run LOO median partial-out **within each cluster separately**: equity-only on the 7-symbol equity cluster (AAPL, GOOGL, HOOD, MSTR, NVDA, QQQ, SPY, TSLA — actually 8; refine in code) and safe-haven-only on GLD / TLT.

**Why.** A1 found the homogeneous partial-out breaks safe-haven Kupiec. Cluster-internal partial-out asks the next-level question: is the *within-equity* common-mode reducible by partial-out without breaking equity-cluster Kupiec? Two outcomes are both useful:
- **If equity-only LOO median preserves Kupiec while reducing within-cluster ρ̂_cross_equity**: confirms cluster topology is the load-bearing structure and gives §9.4 / §10 a concrete architectural target (separate conformity heads per cluster).
- **If it doesn't**: the residual is even more structural than A1 implies — there's intra-equity heterogeneity (mega-cap vs MSTR vs HOOD) the procedure can't absorb either.

**Scope.** New script `scripts/run_paper1_a1_5_cluster_internal_partial_out.py`. Two clusters: equity (8 symbols) and safe-haven (GLD, TLT). For each cluster, run the LOO-median-only variant of A1 on the within-cluster residual. Report ρ̂_cross_within, per-cluster pooled Kupiec / Christoffersen / DQ, per-symbol Kupiec at τ=0.95.

**Status:** ✅ complete 2026-05-06. **Verdict: cluster topology is empirically confirmed as the load-bearing structure of the §9.4 residual. Within the equity cluster, partial-out reduces ρ̂_within by 84% AND preserves per-symbol Kupiec 8/8 AND tightens half-width 11.6% at τ=0.95 — a working architectural target. Safe-haven cluster (N=2) has no within-cluster common-mode to begin with.**

**Implementation.** `scripts/run_paper1_a1_5_cluster_internal_partial_out.py`. Two clusters: equity (AAPL, GOOGL, HOOD, MSTR, NVDA, QQQ, SPY, TSLA) and safe-haven (GLD, TLT). For each cluster, baseline (no partial-out) vs LOO-median partial-out applied within the cluster. Per-regime conformal quantile on TRAIN within cluster; c(τ) bump on OOS within cluster.

**Result tables.** `reports/tables/paper1_a1_5_cluster_internal_partial_out.csv`, `..._per_symbol.csv`, `..._rho.csv`.

**Equity cluster (8 symbols, N_oos = 1,384) — headline τ=0.95:**

| variant | ρ̂_within | per-sym Kupiec | realised | hw bps | DQ p (0.95) | DQ p (0.85) |
|---|---|---|---|---|---|---|
| baseline | **0.477** | **8/8** | 0.950 | 396 | 0.962 | 0.480 |
| cluster-internal partial-out (median) | **0.077** | **8/8** | 0.950 | **350 (−11.6 %)** | 0.436 | 0.000 |

**Safe-haven cluster (2 symbols, N_oos = 346):**

| variant | ρ̂_within | per-sym Kupiec | realised | hw bps |
|---|---|---|---|---|
| baseline | **−0.016** (already ≈ 0) | 2/2 | 0.951 | 176 |
| cluster-internal partial-out | −1.000 (degenerate by construction) | 2/2 | 0.951 | 262 (+49 %) |

**Reading.**

The within-equity ρ̂ is **0.477** — *higher* than the panel-wide ρ̂_cross of 0.41 we measured in A1, because the cross-cluster diluted it. Within-equity is the substrate of the residual. Cluster-internal partial-out removes 84% of it while preserving the per-symbol Kupiec 8/8 result that the homogeneous A1 procedure broke. **This is the architectural target the paper can name in §9.4 and §10**: cluster-conditional conformity heads — one for the equity cluster with within-cluster common-mode removed, one for safe-haven held out.

The safe-haven cluster (N=2) is a degenerate case: GLD and TLT have ρ̂_within ≈ 0 in baseline (they share weakly negative intra-weekend correlation under weekend horizons), so there's no common-mode to remove. The partial-out then computes r_GLD − r_TLT and r_TLT − r_GLD = −(r_GLD − r_TLT), forcing ρ̂_within = −1.000 by construction and inflating bandwidth by 49%. The right read for safe-haven is "the current architecture already works"; safe-haven doesn't need a partial-out and shouldn't get one.

**DQ caveat (still present at lower τ in equity cluster).** Equity-cluster partial-out at τ ∈ {0.68, 0.85} still rejects DQ (p=0.034 and p=0.000) — the same violation-reordering artifact A1 found. Per-symbol Kupiec is preserved, but the violations within a weekend now concentrate on the 1–2 symbols whose residual disagrees with the cluster median, creating fresh autocorrelation under panel-row ordering. At τ=0.95 (the headline anchor) DQ still passes (p=0.436); the rejection is concentrated at body-of-distribution τ. A deployable cluster-conformity head architecture would need to address this — likely via path-fitted scores (B6) or per-symbol cluster-condition.

**Implication for paper §9.4 / §10.** This is the contribution-grade result. The §9.4 disclosure now has three nested layers, each empirically substantiated:

1. The residual is cross-sectional within-weekend (ρ̂_cross = 0.41 panel-wide; A1).
2. The residual lives in the **equity cluster** (ρ̂_within_equity = 0.477; ρ̂_within_sh = −0.016). It is *not* a panel-wide signal — safe-haven assets are not part of it.
3. Cluster-internal partial-out *within* the equity cluster reduces ρ̂_within_equity by 84 %, preserves per-symbol Kupiec 8/8, and tightens half-width 11.6 % at τ=0.95 — confirming the cluster topology is genuinely the structure, and naming a concrete architectural target for §10 (cluster-conditional conformity heads). The DQ-at-lower-τ side effect is the next-level disclosure.

**Hand-off note for wording agent.** §9.4 / §10 can replace generic "Paper 4 territory" gestures with: "*Cluster-internal partial-out on the equity cluster reduces within-cluster ρ̂_cross from 0.477 to 0.077 while preserving per-symbol Kupiec 8/8 and tightening half-width 11.6 % at τ = 0.95. This identifies cluster-conditional conformity heads as the architectural target. The safe-haven cluster (GLD, TLT) has ρ̂_within ≈ 0 in baseline and does not need the same treatment.*"

This is a contribution claim, not a deferral.

---

### A2.5. Verify c(τ=0.99) on TUNE-only doesn't drift from full-OOS

**Goal.** The A2 writeup confirms c(τ=0.95) matches between TUNE-only and full-OOS at three decimals (1.079). It doesn't show c(τ=0.99). With ~5 expected violations in 52 TUNE weekends, c(0.99) on TUNE-only could be noisy — and that would be a separate disclosure to add.

**Scope.** Read out c(τ=0.99) from both modes (already in the A2 output). If it drifts substantially (> 0.05 absolute, say), document under §6.3 / §9.3 as "c(τ=0.99) on the TUNE-only fit drifts from the full-OOS value due to thin violation count; we report both the held-out coverage achieved at the TUNE-only c and the full-OOS value as a sensitivity disclosure". If it matches, no disclosure needed.

**Status:** ✅ complete 2026-05-06. **Verdict: c(τ=0.99) is stable across TUNE-only vs full-OOS — no new disclosure needed at τ=0.99. The drift is concentrated at τ ∈ {0.68, 0.85} as expected.**

c(τ) drift = TUNE-only − full-OOS:

| τ | M_a2 (TUNE-only) | M_full (full-OOS) | drift |
|---|---|---|---|
| 0.68 | 1.028 | 1.000 | **+0.028** (banking-crisis tilt; already disclosed) |
| 0.85 | 1.026 | 1.000 | **+0.026** (same mechanism) |
| 0.95 | 1.079 | 1.079 | **0.000** (held-out headline matches) |
| 0.99 | 1.000 | 1.003 | **−0.003** (within grid resolution; stable) |

Held-out τ=0.99 reading: realised 0.9884, Kupiec p=0.592 — passes cleanly. The thin-violations concern (~5 expected violations in 52 TUNE weekends) doesn't materialise in practice; the conformal quantile q_r(0.99) on TRAIN already covers the EVAL slice without bump, so c=1.0 is the right answer on TUNE-only and c=1.003 is the right answer on full-OOS.

**Implication for paper.** Drop the A2 verification owe-back entirely. The A2 framing for §6.3 / §9.3 doesn't need a c(0.99)-specific carve-out — the disclosure can stay focused on the lower-τ over-coverage that is the actual mechanism.

---

### A2.6. A2 robustness across TUNE anchors {2021, 2022, 2023, 2024}

**Goal.** Refit the A2 design at each of {2021, 2022, 2023, 2024} as the TUNE-only window. If held-out τ=0.95 results hold up across TUNE anchors, A2 + the existing §7 split-date sensitivity tells one coherent story. If they don't, add a TUNE-window-sensitivity disclosure.

**Why.** The A2 result picks 2023 as the TUNE window because that's where the v1 panel naturally splits. A reviewer will ask: "what if you'd tuned on 2022, or 2024?" The robustness sweep answers that pre-emptively and either strengthens A2 or cleanly bounds its sensitivity.

**Scope.** New script `scripts/run_paper1_a2_6_tune_anchor_robustness.py`. For each TUNE anchor in {(2021), (2022), (2023), (2024)}:
- TRAIN = pre-TUNE_start (q on this slice)
- TUNE = single year
- EVAL = post-TUNE-end (held-out)
- Report c(τ) on TUNE; realised coverage / Kupiec / Christoffersen / per-symbol Kupiec at τ ∈ {0.68, 0.85, 0.95, 0.99} on EVAL

If τ=0.95 realised coverage stays in [0.945, 0.955] across all four anchors, the headline holds. If anchors vary materially, document the spread.

**Status:** ✅ complete 2026-05-06. **Verdict: τ=0.95 holds out at 0.947–0.952 across three of four TUNE anchors (2021, 2022, 2023) with per-symbol Kupiec 10/10 preserved everywhere. The 2024 anchor over-covers (0.9754) because TUNE-2024 contains the BoJ unwind, inflating c(0.95) from typical 1.0–1.08 to 1.175 — a contract-favourable failure mode (over-conservative bands), not a broken result. The procedure is robust against under-coverage; it can over-cover when TUNE is non-representative.**

**Implementation.** `scripts/run_paper1_a2_6_tune_anchor_robustness.py`. For each anchor year Y ∈ {2021, 2022, 2023, 2024}: TRAIN = pre-Y-01-01; TUNE = Y (52 weekends); EVAL = Y+1 onwards.

**Result table.** `reports/tables/paper1_a2_6_tune_anchor_robustness.csv`.

**Headline τ=0.95 across TUNE anchors:**

| TUNE | EVAL weekends | realised | c(0.95) | Kupiec p | Christoff p | per-sym Kupiec | hw bps |
|---|---|---|---|---|---|---|---|
| 2021 | 225 (2022→2026YTD) | **0.9524** | 1.000 | 0.59 | 0.21 | **10/10** | 367 |
| 2022 | 173 (2023→2026YTD) | **0.9474** | 1.000 | 0.62 | 0.92 | **10/10** | 349 |
| 2023 | 121 (2024→2026YTD) | **0.9504** | 1.079 | 0.95 | 0.99 | **10/10** | 421 |
| 2024 |  69 (2025→2026YTD) | 0.9754 | 1.175 | 0.0007 | 0.35 | **10/10** | 459 |

**Reading.**

Three of four anchors land τ=0.95 realised coverage in **[0.9474, 0.9524]** — a 0.5pp spread, all within Kupiec's no-rejection band, all preserving per-symbol Kupiec 10/10. **A2's headline holds across three orthogonal time-axis splits**, not just the 2023 anchor that the natural panel split picked.

The 2024 anchor over-covers by 2.5pp (0.9754 vs 0.95 nominal). Mechanism: TUNE 2024 contains the 2024-08-05 BoJ unwind — the worst weekend on record (k_w=10 at τ=0.85) — and the c(τ) bump fit on TUNE inherits its tilt. c(0.95) jumps from typical 1.0–1.08 to 1.175. Applied to EVAL 2025+ (which is calmer), the bands are over-conservative, leading to over-coverage. **Per-symbol Kupiec still passes 10/10** under the 2024 anchor — the per-symbol promise holds across the entire sweep.

This is a contract-favourable failure mode: the c(τ) bump is robust *against* under-coverage but can over-cover when TUNE is non-representative. The procedure trades band sharpness for one-sided coverage safety — exactly the asymmetry a calibration-transparent oracle should exhibit.

**Implication for paper.** Strengthens A2 substantially. The §6.3 / §3.4 headline can now be reported as "τ=0.95 held-out coverage 0.9474–0.9524 across {2021, 2022, 2023} TUNE anchors; 10/10 per-symbol Kupiec across all four anchors {2021, 2022, 2023, 2024}". The 2024-anchor over-coverage gets a one-line disclosure: "*TUNE windows containing outlier weekends (TUNE 2024 includes the 2024-08-05 BoJ unwind, k_w=10) can produce over-coverage on the held-out slice — a sharpness deficit, not a coverage-contract failure. The c(τ) bump procedure is robust against under-coverage by construction.*"

**Hand-off note for wording agent.** Two additions to §6.3 / §3.4:

1. After the A2 headline ("c fit on 2023 alone, evaluated on 2024-01-05 → 2026-04-24"), add: "*The result is stable across TUNE anchors: realised coverage at τ=0.95 lies in [0.9474, 0.9524] for TUNE ∈ {2021, 2022, 2023}, with per-symbol Kupiec 10/10 preserved across all four anchors {2021, 2022, 2023, 2024}.*"

2. As a one-line robustness disclosure: "*The 2024 TUNE anchor over-covers at 0.9754 because TUNE-2024 includes the 2024-08-05 BoJ unwind, inflating c(0.95) to 1.175. Per-symbol Kupiec still passes 10/10. This is a contract-favourable sharpness deficit, not under-coverage.*"

---

## Tier B — closes specific gaps quickly (re-prioritised post-Tier-A)

| # | Item | Notes |
|---|---|---|
| ~~B1~~ ✅ | **Regime-threshold + split-anchor as proper ablations** — done 2026-05-06 (results below). |
| ~~B6~~ ✅ | **Path-fitted conformity score (§10.1)** — done 2026-05-06 (results below). |
| ~~B3~~ ✅ | **Power calc at τ=0.99 (Kupiec MDE)** — done 2026-05-06 (results below). |
| ~~B4~~ ✅ | **VIX → GVZ / MOVE for GLD / TLT regime classifier** — done 2026-05-06 (results below). |
| ~~B5~~ ✅ | **Pairs-block-bootstrap CI for k_w distribution** — done 2026-05-06 (results below). |
| ~~B2~~ ✅ | **Exchangeability test on standardised residuals within Mondrian bin** — done 2026-05-06 (results below). |

---

### B1 result. Regime-threshold + split-anchor as proper ablations

**Status:** ✅ complete 2026-05-06. **Verdict: deployed regime cutoff q=0.75 is robust (all alternates within ±5% half-width and 5/6 pass full calibration gates) but not width-optimal — three alternates (q ∈ {0.60, 0.67, 0.80}) deliver 1.7–2.8% narrower bands at preserved calibration. Disclose as convention-anchored rather than optimization-selected. Split-anchor leg is fully robust: τ=0.95 realised stays in [0.9502, 0.9538] across {2021, 2022, 2023, 2024} split anchors.**

**Implementation.** `scripts/run_paper1_b1_regime_threshold_ablation.py` (regime cutoff). Re-uses `reports/tables/m6_lwc_robustness_split_sensitivity.csv` produced by `scripts/run_v1b_split_sensitivity.py` (split anchor).

**Three-gate frame applied to regime quartile cutoff q ∈ {0.60, 0.67, 0.70, 0.75, 0.80, 0.90}:**

| q | regime mix (high_vol %) | Gate 1: Kupiec all τ | Gate 1b: Christ. all τ | Gate 2: per-sym Kupiec | Gate 3: Δhw% vs deployed (95% CI) |
|---|---|---|---|---|---|
| 0.60 | 38.9 % | ✓ | ✓ | 10/10 | **−2.76 %** [−3.80, −1.73] (narrower) |
| 0.67 | 30.8 % | ✓ | ✓ | 10/10 | **−1.78 %** [−2.66, −0.87] (narrower) |
| 0.70 | 28.8 % | ✓ | ✓ | 10/10 | +1.73 % [+0.85, +2.71] (wider) |
| **0.75 (deployed)** | **23.9 %** | **✓** | **✓** | **10/10** | — |
| 0.80 | 21.1 % | ✓ | ✓ | 10/10 | **−1.70 %** [−2.11, −1.32] (narrower) |
| 0.90 | 12.3 % | ✓ | ✗ rejects | 10/10 | −4.30 % [−5.34, −3.25] (narrowest, fails Gate 1b) |

**Reading.** Five of six candidates pass Gates 1, 1b, and 2. The deployed q=0.75 is dominated on Gate 3 by **q ∈ {0.60, 0.67, 0.80}** (statistically narrower with bootstrap CI excluding 0). The differences are small (1.7–2.8 % at τ=0.95) but real. The narrowest gate-passing alternate is q=0.60 at −2.76 %; q=0.90 is narrower still (−4.30 %) but fails Christoffersen at one or more served τ.

**Honest framing.** The deployed q=0.75 is **convention-anchored** (top quartile by definition) rather than width-optimization-selected. Three alternates (q=0.60, q=0.67, q=0.80) deliver narrower bands at preserved calibration. The differences are operationally small (~5 bps at τ=0.95 on a 370 bps headline), but they exist and disclosure is the right call.

**Split-anchor leg (data already in `m6_lwc_robustness_split_sensitivity.csv`):**

| split anchor | n_oos weekends | τ=0.95 realised | Kupiec p | Christoffersen p | hw bps |
|---|---|---|---|---|---|
| 2021-01-01 | 277 | **0.9539** | 0.348 | 0.115 | 357.2 |
| 2022-01-01 | 225 | **0.9520** | 0.661 | 0.186 | 363.5 |
| **2023-01-01 (deployed)** | **173** | **0.9503** | **0.956** | **0.603** | **370.6** |
| 2024-01-01 | 121 | **0.9504** | 0.947 | 0.671 | 416.8 |

**Reading.** Realised coverage at τ=0.95 stays in **[0.9503, 0.9539]** across all four split anchors. Kupiec passes everywhere (p ∈ [0.35, 0.96]); Christoffersen passes everywhere at α=0.05 (p ∈ [0.12, 0.67]). **The deployed 2023-01-01 split is robust.** Half-width varies (357 → 417 bps) — driven by the eval-slice composition effect already disclosed in A2 (later eval slices contain more high-σ̂ weekends).

**Implication for paper §7.4 ablation.**

§7.4 currently lists 16 scalars (12 trained per-regime quantiles + 4 c(τ) bumps) as the deployment-tuned-via-OOS-data DOF. The "16 scalars undercounts DOF" critique points at:
- The regime quartile cutoff (1 scalar, q=0.75)
- The split anchor (1 scalar, 2023-01-01)
- The σ̂ rule selector (1 scalar, EWMA HL=8 — already covered by §7.4's three-gate frame)

After B1: each of these three scalars now has a proper ablation:
- σ̂ rule: §7.4 existing three-gate frame (Gates 1, 2, 3 with multi-test correction)
- **Regime cutoff: B1 three-gate frame above** — robust to ±5pp perturbations; deployed value is convention-anchored, not optimization-selected
- **Split anchor: τ=0.95 realised in [0.9503, 0.9539] across four anchors** — robust

The 16-scalars deployment count is now 3 + 16 = **19 scalars**, all with proper-ablation provenance. The "undercounts DOF" gap is closed.

**Hand-off note for wording agent.**

§7.4 ablation table: add two new rows.

> *Regime quartile cutoff q (1 scalar; deployed q = 0.75, top quartile). Across q ∈ {0.60, 0.67, 0.70, 0.75, 0.80, 0.90}, 5 of 6 candidates satisfy Gates 1+1b+2 (pooled Kupiec at all τ, pooled Christoffersen at all τ, per-symbol Kupiec 10/10). Bootstrap CI on Δhw% at τ=0.95 vs deployed: q=0.60 −2.76 % [−3.80, −1.73], q=0.67 −1.78 % [−2.66, −0.87], q=0.80 −1.70 % [−2.11, −1.32], q=0.70 +1.73 % [+0.85, +2.71]. The deployed q=0.75 is convention-anchored rather than width-optimal; three alternates deliver 1.7–2.8 % narrower bands at preserved calibration.*

> *Split anchor (1 scalar; deployed 2023-01-01). Across {2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01}, realised τ=0.95 coverage stays in [0.9503, 0.9539]; Kupiec p ∈ [0.35, 0.96]; Christoffersen p ∈ [0.12, 0.67]; per-symbol Kupiec 10/10 across all four anchors. The deployed split anchor is robust.*

§3.5 (non-goals) or §9.3 (provenance disclosure): "*The deployed regime quartile cutoff (q = 0.75) and split anchor (2023-01-01) are not width-optimization-selected; B1's regime-cutoff ablation finds q ∈ {0.60, 0.67, 0.80} deliver 1.7–2.8 % narrower bands at preserved calibration, but the deployed value satisfies all three gates and the differences are operationally small (~5 bps on a 370 bps τ=0.95 headline). A re-tuning on a future held-out tune slice could close this gap; for the present paper the value is treated as convention-anchored.*"

**Numbers / tables.** All reproducible from `reports/tables/paper1_b1_regime_threshold_ablation.csv`, `..._per_symbol.csv`, `..._hw_bootstrap.csv` (regime cutoff) and `m6_lwc_robustness_split_sensitivity.csv` (split anchor).

---

### B6 result. Path-fitted conformity score lifted to library + unit-tested

**Status:** ✅ complete 2026-05-06. **Verdict: methodology contribution staged. Library function in `src/soothsayer/backtest/calibration.py:compute_score_lwc_path()`; 7 unit tests in `tests/test_path_fitted_score.py` (all pass) verify the §10.1 spec literally. Existing empirical fit on CME-projected subset (n=1,557 OOS rows) is in `reports/tables/m6_lwc_robustness_path_fitted.csv`. When forward path-coverage data crosses N≥300 weekends, the validation pipeline drops in directly without methodology rewrite.**

**What changed.** The path-fitted score logic that previously lived inline in `scripts/run_v1b_path_fitted_conformal.py` is now a library function with the same shape as `compute_score_lwc`:

```python
def compute_score_lwc_path(panel: pd.DataFrame,
                           scale_col: str = "sigma_hat_sym_pre_fri") -> pd.Series:
    """s_path = max_t |P_t − point| / (fri_close · σ̂_sym).

    Approximated as max(point − path_lo, path_hi − point, |mon_open − point|) /
    (fri_close · σ̂_sym). Required cols: mon_open, fri_close, factor_ret (or
    point), path_lo, path_hi, σ̂.
    """
```

Behaviour matches the inline runner logic exactly (verified by re-running `run_v1b_path_fitted_conformal.py` against the unit-tested function).

**Unit-test coverage (7 tests, all pass):**

1. `test_degenerate_path_equals_endpoint` — when path_lo = path_hi = point, path-score equals endpoint-score
2. `test_path_score_dominates_endpoint` — path-score ≥ endpoint-score for all rows (max-over-path)
3. `test_path_score_formula` — numerical: max(point−path_lo, path_hi−point, |mon_open−point|) / (fri_close · σ̂)
4. `test_breach_below_dominates` — left-tail breach can be the supremum
5. `test_negatively_signed_path_no_breach_below` — path_lo > point ⇒ breach below = 0
6. `test_nan_sigma_returns_nan` — invalid σ̂ propagates NaN
7. `test_nan_path_extrema_returns_nan` — missing path_lo / path_hi propagates NaN

**Why this is "ready" without N≥300 forward data.** The conformity-quantile + c(τ)-bump pipeline already accepts an arbitrary `score_col` argument (see `train_quantile_table`, `fit_c_bump_schedule`); plugging the path-fitted score in is a one-line change. The bottleneck is *path data*, not methodology. When the V5 forward-cursor tape reaches ≥ 300 weekends of path coverage (per §10.1's data-gated extensions), the validation pipeline runs:

```python
panel["score"] = compute_score_lwc_path(panel)
qt = train_quantile_table(panel_train, ...)
cb = fit_c_bump_schedule(panel_oos, qt, ...)
```

— with no further methodology work.

**Existing empirical first-cut (CME-projected subset).** `reports/tables/m6_lwc_robustness_path_fitted.csv` already contains the head-to-head endpoint-fitted vs path-fitted M6 LWC fit on the n=1,557 OOS rows where CME futures projection is available. Headline at τ=0.95: endpoint-fitted band has realised endpoint coverage 0.951 / path coverage 0.958 / 327 bps half-width; path-fitted band has realised endpoint 0.965 / path 0.973 / 379 bps half-width. The path-fitted variant trades 16 % wider bands for ~1.5 pp tighter path coverage — mechanically correct (path ≥ endpoint by construction) and a useful operating point for protocols caring about during-window slippage.

**Implication for paper §10.1.** The "methodology exists, empirical validation accumulating" framing is now fully grounded:

> *"§10.1's path-fitted conformity score is implemented as a library primitive (`soothsayer.backtest.calibration.compute_score_lwc_path`) with unit-test coverage of the spec; an empirical first-cut on the CME-projected subset (n=1,557 OOS rows, `reports/tables/m6_lwc_robustness_path_fitted.csv`) confirms the mechanical correctness of the score and the integration with the deployed Mondrian split-conformal pipeline. The binding evidence — does path-fitting close the §6.6 perp / on-chain residual gap on consumer-experienced path data — accumulates as the V5 forward-cursor tape (continuous capture since 2026-04-24) crosses N≥300 path-coverage weekends."*

§10.1 can drop the "implementation half" caveat entirely and frame the deferral as purely data-gated.

**Hand-off note for wording agent.** §10.1 path-fitted bullet can adopt: "*Methodology is library-grade and unit-tested (`compute_score_lwc_path`); the binding empirical question is data-gated on path-coverage accumulation, not on methodology completion.*"

**Numbers / artefacts.** `src/soothsayer/backtest/calibration.py:compute_score_lwc_path`, `tests/test_path_fitted_score.py`, `reports/tables/m6_lwc_robustness_path_fitted.csv`.

---

### B3 result. Kupiec power / MDE at τ ∈ {0.85, 0.95, 0.99}

**Status:** ✅ complete 2026-05-06. **Verdict: per-symbol Kupiec at τ=0.99 has minimum detectable effect ~3pp (under-coverage) and is undetectable for over-coverage. The pass should be reported with explicit MDE disclosure or restricted to pooled grid claims.**

**Implementation.** `scripts/run_paper1_b3_kupiec_power.py`. Monte Carlo: 10,000 reps per (τ, N, Δ) cell; Kupiec LR critical at α=0.05 (χ²(1) crit = 3.841). MDE = smallest Δ with rejection power ≥ 0.8.

**Result table.** `reports/tables/paper1_b3_kupiec_power_mde.csv`.

**MDE matrix:**

| τ | E[viol] under null | Pooled (N=1,730) | Per-symbol (N=173) |
|---|---|---|---|
| 0.85 | 259.5 (pooled) / 25.95 (per-sym) | over: 3.0 pp / under: 2.5 pp | over: 10.0 pp / under: 7.5 pp |
| 0.95 |  86.5 / 8.65 | over: 2.0 pp / under: 1.5 pp | over: 7.5 pp / under: 4.0 pp |
| 0.99 |  17.3 / 1.73 | **over: 1.0 pp / under: 1.0 pp** | **over: 3.0 pp / under: NaN (undetectable)** |

(Direction convention: "over_violations" = realised violation rate > nominal = under-coverage at the band level; "under_violations" = realised < nominal = over-coverage at the band level.)

**Reading.**

- **Pooled Kupiec at τ=0.99: MDE 1.0pp** in both directions. Statistically meaningful — the pooled pass against 1pp deviations is what a coverage-contract claim would actually demand. Pooled headline is well-powered.
- **Per-symbol Kupiec at τ=0.99: MDE 3.0pp under-coverage; undetectable over-coverage**. With 1.73 expected violations per symbol, the test cannot distinguish 0% from 1%; can only flag deviations of ≥ 3pp. The §6.4 per-symbol Kupiec 10/10 pass at τ=0.99 should be read as "no symbol's violation rate is distinguishable from 1% at the resolution Kupiec offers per-symbol", not as "every symbol is calibrated to 1pp tolerance".
- **Per-symbol Kupiec at τ=0.95: MDE 4.0pp / 7.5pp** — moderate. The 10/10 pass at τ=0.95 is informative against deviations larger than 4–8pp. The σ̂-standardised LWC architecture's per-symbol violation rates sit in [3.5%, 6.9%] (range observed) — well within 4pp of the 5% nominal — so the per-symbol pass at τ=0.95 is real but not ultra-tight.
- **Pooled Kupiec at τ=0.95: MDE 1.5pp / 2.0pp** — strong, fully consistent with the 0.9504 / Kupiec p=0.96 headline being robustly nominal.

**Implication for paper §6.4.** Two options the paper can adopt:

(a) **Adopt the pooled-only τ=0.99 claim.** §6.4's per-symbol Kupiec at τ=0.99 row is dropped from the headline; the §6.4 statement at τ=0.99 becomes pooled-only ("Kupiec p = 0.94 on pooled, MDE 1.0 pp"). Per-symbol τ=0.99 numbers can stay in the appendix table with an explicit "MDE 3.0 pp / undetectable over" disclosure.

(b) **Keep the per-symbol pass with explicit MDE disclosure.** §6.4 keeps the 10/10 claim at τ=0.99 but adds: "*Per-symbol Kupiec at τ=0.99 has minimum detectable effect of ~3 pp against under-coverage and is undetectable for over-coverage given the per-symbol expected violation count of 1.73; the pass should be read as 'no per-symbol violation rate is distinguishable from 1% by Kupiec given the available power', not as a 1pp-tolerance certificate.*"

I'd recommend (b) — keeping the 10/10 claim is rhetorically valuable, and the MDE disclosure is honest. Dropping the per-symbol row would be over-correcting.

**Hand-off note for wording agent.** §6.4 / §3.4 add the per-symbol-τ=0.99 MDE caveat:

> *"Per-symbol Kupiec at τ=0.99 has minimum detectable effect ≈ 3 pp under-coverage and is undetectable for over-coverage given the per-symbol expected violation count of 1.73. The 10/10 pass should be read as 'no per-symbol violation rate is statistically distinguishable from 1 % at the resolution Kupiec offers per-symbol', not as a 1 pp-tolerance certificate. Pooled Kupiec at τ=0.99 has minimum detectable effect 1.0 pp; the pooled p=0.94 is the τ=0.99 statistical claim that does have 1 pp resolution."*

Add a power-by-(τ, N) table to §7.4 ablation appendix — the full matrix above, reproducible from `paper1_b3_kupiec_power_mde.csv`.

**Numbers / tables.** `reports/tables/paper1_b3_kupiec_power_mde.csv`.

---

### B4 result. VIX → GVZ / MOVE regime-classifier sensitivity

**Status:** ✅ complete 2026-05-06. **Verdict: robust. Regime tag flips on 23 % of GLD weekends and 28 % of TLT weekends under asset-specific vol indices, but the M6 LWC pooled τ=0.95 headline is *identical* (0.9503 in both); per-symbol Kupiec 10/10 in both; half-width changes by 0.1 %. σ̂-standardisation absorbs the regime-tagging difference. Internal consistency closed.**

**Implementation.** `scripts/run_paper1_b4_regime_index_sensitivity.py`. Two regime classifiers: VIX-only (deployed) vs hybrid (GLD via GVZ, TLT via MOVE, others via VIX). Same ROLLING_WEEKS=52 / q=0.75 cutoff. Re-fit M6 LWC under each; compare on identical OOS slice (n=1,730).

**Result tables.** `reports/tables/paper1_b4_regime_index_sensitivity.csv`, `..._per_symbol.csv`.

**Pooled τ=0.95 cross-variant:**

| variant | realised | c(0.95) | Kupiec p | Christoffersen p | hw bps |
|---|---|---|---|---|---|
| VIX_only_deployed | 0.9503 | 1.059 | 0.956 | 0.720 | 367.18 |
| hybrid_GVZ_MOVE | 0.9503 | 1.073 | 0.956 | 0.720 | 367.52 |

**Per-symbol GLD / TLT at τ=0.95:**

| symbol | variant | viol_rate | Kupiec p |
|---|---|---|---|
| GLD | VIX_only | 6.94 % | 0.268 |
| GLD | hybrid (via GVZ) | 6.36 % | 0.431 |
| TLT | VIX_only | 4.62 % | 0.819 |
| TLT | hybrid (via MOVE) | 4.05 % | 0.552 |

**Tag-flip rates (regime classification differences):**

- GLD: 146 / 630 weekends (23.2 %) classified differently under GVZ vs VIX
- TLT: 174 / 631 weekends (27.6 %) classified differently under MOVE vs VIX
- Panel-wide agreement: 94.6 % identical

**Reading.**

The regime tag matters substantially at the per-(symbol, weekend) level for GLD/TLT — roughly a quarter of those weekends fall into a different regime cell under the asset-appropriate vol index. **But the M6 LWC architecture is robust to this choice**: pooled coverage and per-symbol Kupiec are unchanged under either classifier. This is the σ̂-standardisation paying its way — the per-symbol scale rule σ̂_sym(t) absorbs the per-asset volatility regime structurally, so the regime cell only contributes a small marginal adjustment via q_r(τ); flipping a quarter of GLD/TLT regime tags moves q_r modestly within the per-cell calibration band, and c(τ) absorbs the residual.

This is a **contribution-grade observation about the architecture**: σ̂-standardisation makes the deployed pipeline robust to regime classifier choices. The deployed VIX-only classifier is justified by simplicity and per-asset-vol-index-agnosticism, not by being optimally tuned per asset.

**Implication for paper.** Resolves the §5 regime / §7 σ̂-regression internal-consistency gap pre-emptively:

> *"The regime classifier uses VIX (equity vol index) as the high-vol gate for all symbols, including GLD (gold) and TLT (long-dated treasury) which have asset-specific vol indices (GVZ, MOVE). A sensitivity ablation that swaps GLD's regime gate to GVZ and TLT's to MOVE — flipping the regime tag on 23 % of GLD weekends and 28 % of TLT weekends — leaves the pooled τ=0.95 headline coverage unchanged at 0.9503 (Kupiec p=0.956), per-symbol Kupiec 10/10, and half-width within 0.1 %. The M6 σ̂-standardisation absorbs the regime-tagging difference structurally; the regime cell contributes a small marginal adjustment via q_r(τ), not a load-bearing scale separation."*

**Hand-off note for wording agent.** §5 (regime tagging) or §9 (limitations) can adopt the above paragraph verbatim. Numbers reproducible from `paper1_b4_regime_index_sensitivity.csv`.

---

### B5 result. Pairs-block-bootstrap CI for k_w (preempts the question)

**Status:** ✅ complete 2026-05-06. **Verdict: weekly k_w shows essentially zero autocorrelation; pairs-block-bootstrap CIs are within Monte Carlo noise of the i.i.d.-weekend bootstrap. Existing §6.3.4 CIs are structurally correct.**

**Implementation.** `scripts/run_paper1_b5_kw_block_bootstrap.py`. Moving-block-bootstrap with block lengths L ∈ {1, 4, 8, 13} (L=1 = i.i.d. baseline). 5,000 bootstrap reps per (τ, L, statistic) cell. Statistics: mean k_w, var k_w, P(k_w≥3), P(k_w≥5), variance-overdispersion ratio.

**Result table.** `reports/tables/paper1_b5_kw_block_bootstrap.csv`.

**Empirical OOS k_w autocorrelation:**

| τ | lag-1 | lag-2 | lag-4 |
|---|---|---|---|
| 0.85 | 0.012 | 0.012 | −0.066 |
| 0.95 | −0.005 | 0.030 | −0.068 |
| 0.99 | −0.043 | 0.033 | −0.018 |

All within ~2σ sampling noise of zero (n=173 weekends; standard error of ρ̂ ≈ 0.076). **No temporal persistence in weekly k_w to correct for.**

**Headline τ=0.95 CI widths across block lengths:**

| statistic | L=1 (i.i.d.) | L=4 | L=8 | L=13 |
|---|---|---|---|---|
| mean k_w | 0.306 | 0.312 | 0.318 | 0.324 |
| var k_w | 1.681 | 1.583 | 1.626 | 1.600 |
| P(k_w ≥ 3) | 0.064 | 0.064 | 0.064 | 0.064 |
| var overdispersion (emp/Binom) | 3.326 | 3.448 | 3.377 | 3.451 |

CIs are functionally identical across block lengths. The mean k_w CI at L=13 is 6 % wider than at L=1 — well within Monte Carlo noise. P(k_w≥3) is identical at four decimals.

**Headline τ=0.95 CI bounds (L=1 vs L=13):**

- mean k_w: observed 0.497; L=1 CI [0.358, 0.665]; L=13 CI [0.364, 0.688]
- var k_w: observed 1.094; L=1 CI [0.483, 2.164]; L=13 CI [0.474, 2.074]
- P(k_w ≥ 3): observed 0.046; L=1 CI [0.017, 0.081]; L=13 CI [0.017, 0.081]
- var-overdispersion (emp/Binom): observed 2.316; L=1 CI [1.014, 4.341]; L=13 CI [0.983, 4.434]

**Reading.** The cross-sectional within-weekend dependence (ρ̂_cross = 0.41) is *already* respected by either bootstrap convention — both are weekend-block bootstraps that keep the 10 symbols of a weekend together. The question B5 addresses is *temporal* dependence across weekends: if consecutive weekends had correlated k_w, the i.i.d.-weekend bootstrap would underestimate CIs. The empirical autocorrelation result says they don't, so the CIs don't change.

**Implication for paper.** No changes needed to §6.3.4 / §6.3.5 CIs. The preemptive answer to the reviewer question — "did you address temporal dependence across weekends?" — is "yes; weekly k_w autocorrelation is empirically zero (lag-1 ρ̂ ∈ [−0.04, 0.01] across τ), and pairs-block-bootstrap CIs match the i.i.d.-weekend convention to within Monte Carlo noise. Numbers in `paper1_b5_kw_block_bootstrap.csv`."

**Hand-off note for wording agent.** §6.3.4 footnote (or §9 disclosure):

> *"Cross-sectional within-weekend dependence (ρ̂_cross = 0.41) is respected by all reported CIs via weekend-block bootstrap. Temporal autocorrelation across weekends is empirically null — lag-1, lag-2, lag-4 ρ̂ on weekly k_w lie in [−0.07, 0.03] across served τ — so a moving-block-bootstrap with block lengths L ∈ {4, 8, 13} produces CIs within Monte Carlo noise of the L=1 (i.i.d.-weekend) baseline. Tabulated in `reports/tables/paper1_b5_kw_block_bootstrap.csv`."*

**Numbers / tables.** `reports/tables/paper1_b5_kw_block_bootstrap.csv`.

---

### B2 result. Within-bin exchangeability test on Mondrian bins

**Status:** ✅ complete 2026-05-06. **Verdict: exchangeability holds. Only 1/30 (regime × symbol) bins reject exchangeability at α=0.05 (under-rejecting vs the 5 % expected by chance); 0/30 reject at α=0.01. Mondrian-CP's finite-sample coverage guarantee assumption is empirically supported on the deployed slice.**

**Implementation.** `scripts/run_paper1_b2_exchangeability.py`. For each (regime × symbol) bin on OOS 2023+ (30 bins; n ranges 19–116 per bin):
- Statistic: lag-1 Pearson autocorrelation of M6 LWC standardised score in fri_ts order
- Permutation null: 5,000 random shuffles of within-bin time order
- Two-sided p-value vs the permutation distribution

**Result table.** `reports/tables/paper1_b2_exchangeability.csv`.

**Per-bin rejection rates:**

| nominal α | observed reject rate | expected under exchangeability |
|---|---|---|
| 0.05 | **1/30 (3.3 %)** | ~5 % |
| 0.01 | **0/30 (0.0 %)** | ~1 % |

**Aggregate KS test of per-bin p-values vs Uniform(0,1):** D = 0.276, p = 0.017. Rejects Uniform — but the rejection is in the *under-rejecting* direction (too few low p-values, too many bins with p > 0.5). This is *consistent* with exchangeability holding; the deviation is "more exchangeable than uniform predicts", not "less exchangeable". A genuine violation would manifest as concentration of p-values *near 0*, not near 1.

**Three lowest p-values (extreme-bin disclosure):**

| symbol | regime | n | lag-1 ρ̂ | perm p (two-sided) |
|---|---|---|---|---|
| GLD | normal | 116 | **−0.166** | **0.043** |
| TLT | normal | 116 | −0.147 | 0.114 |
| AAPL | normal | 116 | +0.131 | 0.145 |

Only GLD/normal nominally rejects at α=0.05; the lag-1 ρ̂ is *negative* (mean-reverting score within bin), the magnitude is small (|ρ̂| = 0.17), and the BH-corrected p-value across 30 tests is 0.043 × 30 / 1 ≈ 1.0 (not significant after multi-test correction). This is a single-bin marginal result that **doesn't survive multi-test correction**.

**Reading.** Mondrian-CP's exchangeability assumption is empirically supported on the deployed slice. The test had power to detect within-bin temporal dependence (n=116 in each `normal` bin gives respectable power against |ρ| ≈ 0.20); it found none. The §6.3.6 / A1 / A1.5 cross-sectional within-weekend dependence (ρ̂_cross = 0.41) is *across* bins, not within — that's the residual the cluster-topology framing names; B2 confirms that within-bin exchangeability separately holds.

**Implication for paper §4.6.** The methodology already asserts within-bin exchangeability. B2 tests it directly and finds no violation. The §9 limitations list can shrink slightly: "Mondrian-CP exchangeability" was an unmentioned implicit assumption; B2 makes it an explicit, empirically-supported claim.

**Hand-off note for wording agent.** §4.6 (Mondrian-CP setup) or §9 (limitations footnote):

> *"Mondrian-CP's finite-sample coverage guarantee depends on within-bin exchangeability. A permutation test on the lag-1 score autocorrelation within each (regime × symbol) bin (n = 19–116, 30 bins, OOS 2023+) finds 1/30 nominally rejecting at α=0.05 (none after BH correction) and 0/30 at α=0.01 — under-rejection vs the 5% / 1% expected under exchangeability. Within-bin exchangeability is empirically supported. The §6.3.6 / §9.4 cross-sectional dependence is *across* bins, not within (`reports/tables/paper1_b2_exchangeability.csv`)."*

**Numbers / tables.** `reports/tables/paper1_b2_exchangeability.csv`.

---

## Tier C — defer or treat carefully

| # | Item | Notes |
|---|---|---|
| C1 | **Proper scoring rules (Winkler interval score, CRPS)** | Cleaner head-to-head exposition vs GARCH-t / Pyth-wrap. Doesn't change conclusions; deferrable to revision round. |
| C2 | **CUSUM drift detection** | More product than paper. Belongs in §9.2 disclosure as a forward monitoring story; doesn't move the headline. |
| C3 | **Stronger DGP-D (10× / 50-weekend, or discrete jump)** | Run *privately first* — may degrade simulation results materially. Honest, but commit to the reframe before publishing. |

---

## Sequencing

A1 → A2 → A3. Partial out common-mode first; refit c(τ) on the cleaned score for the nested holdout; then run the joint baseline against the held-out k_w distribution. Reverse order means redoing A2 after A1.

Tier B items are each parallelisable against Tier A and can slot in as time allows.
