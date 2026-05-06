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

## Tier B — closes specific gaps quickly

| # | Item | Notes |
|---|---|---|
| B1 | **Regime-threshold + split-anchor as proper ablations** | Extend §7.3's three-gate frame to (a) the regime quartile cut and (b) the 2023-01-01 split anchor. Closes "16 scalars undercounts DOF". 1-day extension. |
| B2 | **Exchangeability test on standardised residuals within Mondrian bin** | Permutation test: shuffle time order within each (regime × symbol) bin, recompute Berkowitz LR or Kupiec rejection rate, check whether observed deviates. Mondrian-CP's finite-sample guarantee depends on this. |
| B3 | **Power calc at τ=0.99 (Kupiec MDE)** | With 17 expected violations, compute minimum detectable effect against 1pp deviations. Either report the MDE or restrict per-symbol claims at τ=0.99 to pooled grid. |
| B4 | **VIX → GVZ / MOVE for GLD / TLT regime classifier** | Either swap or run a sensitivity ablation showing it doesn't matter. As written, the regime classifier is internally inconsistent with the σ-regression story. |
| B5 | **Pairs-block-bootstrap CI for k_w distribution** | The current weekend-block bootstrap assumes weekends are independent — the cross-sectional structure violates that. Reporting both methods preempts the question. |
| B6 | **Path-fitted conformity score (§10.1)** — implementation only | Implementation half is *not* blocked on N≥300 path-coverage data. Build, unit-test, and stage so when forward data lands we can validate immediately. Decouples methodology contribution from data wait. |

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
