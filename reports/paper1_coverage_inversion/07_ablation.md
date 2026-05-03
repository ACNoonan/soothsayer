# §7 — Ablation Study

This section answers Q3 of §3.6: which components of the band-construction architecture are load-bearing for the calibration claim, and which are disclosed for auditability but contribute no measurable signal at our sample size? The ablation runs in three layers, in the order of increasing scope:

1. *The v1 forecaster ladder* (§7.1–§7.5). A nine-step ladder on the full panel + a seven-cell serving-layer matrix on the held-out 2023+ slice + a load-bearing-vs-cosmetic taxonomy. This was the architecture-design ablation that produced the v1 hybrid Oracle (F1_emp_regime + per-target buffer + per-regime forecaster choice). It is retained here as the *historical record* of why we ended up with the regime classifier $\rho$ as the load-bearing piece — the §7.5 taxonomy was the bridge from "complex forecaster ladder" to "regime classifier + something simple on top."

2. *The deployable simpler-baseline stress test* (§7.6). A constant-buffer width-at-coverage baseline tests whether the regime model's complexity buys pooled width-at-coverage relative to a single global symmetric buffer. It does not — the regime model's contribution is calibration through distribution shift and tail-protection in `high_vol`, not pooled sharpness — but the baseline does not deliver coverage at all on the OOS slice, so the regime classifier survives the stress test as load-bearing.

3. *The Mondrian split-conformal-by-regime ablation that produced the deployed M5 / v2 architecture* (§7.7). A five-rung Mondrian ladder identifies the *deployable* simpler architecture that delivers coverage *and* materially narrower bands than the v1 hybrid Oracle: per-regime conformal quantile + factor-adjusted point + δ-shifted $c(\tau)$ bump. This is the deployed architecture (§4); §7.1–§7.5 is the v1 ladder it superseded; §7.6 is the constant-buffer stress test it survived.

All deltas carry block-bootstrap 95% confidence intervals; the bootstrap unit is the weekend (`fri_ts`), with all symbol-rows sharing a weekend resampled together so cross-sectional correlation is preserved (1000 resamples). Raw tables: `reports/tables/v1b_ablation_*.csv` (v1 ladder) and `reports/tables/v1b_mondrian_*.csv` + `reports/tables/v1b_constant_buffer_*.csv` (M5 ablation + stress test).

> The §7.1–§7.5 ladder was conducted under the v1 architecture (calibration surface $S^f(s, r, q)$ + per-target additive buffer + per-regime forecaster selection). The §7.7 Mondrian ablation showed that the F1_emp_regime forecaster machinery on top of $\rho$ — log-log VIX, per-symbol vol indices, earnings flag, long-weekend flag — is over-engineering relative to a per-regime conformal quantile lookup. Read §7.1–§7.5 as documenting *why we know the regime classifier is load-bearing*; the F1 internals are mostly cosmetic at our sample size.

## 7.1 Ladder design

Each ladder rung adds exactly one knob to the previous rung; the ablation isolates the marginal contribution of each design choice. Variants are scored on the full 5,996-weekend panel (2014-01-17 → 2026-04-24) at the nominal claimed quantile $q = 0.95$ — the *raw-forecaster* coverage, prior to the calibration-surface inversion of §4.2–§4.3. The A0_VIX rung — the forward-curve-implied Gaussian baseline that a reviewer is likely to ask for in lieu of A0's realised-vol baseline — is scored on the equity subset of the panel (8 of 10 tickers; GLD/TLT use GVZ/MOVE in F1, and constructing an analogous standalone index-implied-vol baseline for them would require per-class unit conversions outside this rung's scope; we treat that as a v2 baseline candidate, see §10).

| Variant | Description | Realised | Mean half-width (bps) | Point MAE (bps) |
|---|---|---:|---:|---:|
| A0 | F0_stale: Friday close + 20-day realised Gaussian band | 0.976 | 401.9 | 94.7 |
| A0_VIX | F0_VIX: Friday close + VIX-implied Gaussian (equity-only, $n=4{,}755$) | 0.900 | 233.5 | 94.7 |
| A1 | + factor-adjusted point + empirical residual quantile | 0.914 | 244.6 | 90.0 |
| A2 | + VIX-scaled residual standardisation | 0.921 | 240.0 | 90.0 |
| A3 | + log-log VIX regression on $\log\|\varepsilon\|$ | 0.923 | 252.8 | 90.0 |
| A4 | + per-symbol vol index (VIX / GVZ / MOVE) | 0.924 | 253.6 | 90.0 |
| A5 | + earnings-next-week regressor (only) | 0.924 | 254.0 | 90.0 |
| A6 | + is_long_weekend regressor (only) | 0.924 | 253.6 | 90.0 |
| A7 | full $\texttt{F1\_emp\_regime}$ (both regressors) | 0.924 | 253.9 | 90.0 |
| B0 | A7's CI width centred on stale point | 0.920 | 253.9 | 94.7 |

Every variant's *raw-forecaster* Kupiec test rejects at the nominal 0.95 claim — this is by design. The 0.95 figure here is the un-buffered, un-inverted quantile-grid output; the served-band coverage of §6.4 is produced by the calibration-surface inversion + per-target buffer that wraps any of these variants. The ablation isolates *which underlying components* drive the sharpness and coverage of the inversion's input, not the inversion's output.

## 7.2 Pooled effect — which knob delivers the sharpness?

| A → B | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) |
|---|---|---|
| **A0 → A0_VIX** (swap σ source: 20d realised → VIX-implied; equity-only $n=4{,}719$) | **−7.86 [−8.75, −6.99]** | **−49.3 [−50.6, −48.1]** |
| **A0_VIX → A1** (factor pt + emp Q on top of VIX-Gaussian; $n=4{,}503$) | **+1.51 [+0.11, +2.90]** | **+17.5 [+13.3, +21.9]** |
| **A0 → A1** (factor pt + emp Q) | **−6.2 [−7.4, −5.0]** | **−39.3 [−41.3, −37.3]** |
| A1 → A2 (VIX-scale residuals) | +0.7 [−0.1, +1.4] | −1.9 [−4.6, +1.0] |
| A2 → A3 (log-log VIX regression) | +0.3 [−0.3, +0.9] | **+3.9 [+1.6, +6.4]** |
| A3 → A4 (per-symbol vol index) | +0.1 [−0.1, +0.4] | **+0.3 [+0.1, +0.5]** |
| A4 → A5 (earnings regressor) | 0.0 [−0.1, +0.1] | +0.1 [−0.2, +0.5] |
| A4 → A6 (long-weekend flag) | 0.0 [−0.3, +0.3] | 0.0 [−0.4, +0.5] |
| A4 → A7 (both regressors) | −0.1 [−0.4, +0.2] | +0.1 [−0.5, +0.7] |
| A7 → B0 (strip factor pt; hold CI fixed) | −0.4 [−1.2, +0.4] | 0.0 (by construction) |

Negative $\Delta$ sharpness means tighter bands. Bold rows are those whose 95% CI excludes zero.

**The factor-switchboard point + empirical residual quantile (A0 → A1) deliver essentially all of the pooled sharpness gain: bands are 39.3% tighter (CI [37.3%, 41.3%]) at the cost of 6.2pp lower raw-forecaster coverage.** Every subsequent rung's pooled sharpness effect is either flat or a small widening. The earnings regressor (A4 → A5) and the long-weekend flag (A4 → A6) have no statistically detectable pooled effect — both confidence intervals span zero on coverage and sharpness.

**The forward-curve-implied baseline (A0 → A0_VIX) delivers a *larger* sharpness gain than F1 — 49.3% tighter against A0's realised-vol Gaussian — but undercovers by 7.9pp at $q = 0.95$.** The mechanism is the structural mismatch between an *index-level* implied-vol input (VIX) and a *single-stock* weekend tail: VIX prices the SPX 30-day forward variance, which is systematically below per-name single-stock variance for the high-beta universe (NVDA, TSLA, MSTR especially). The miscalibration is uniform across regimes — the equity-matched per-regime A0 → A0_VIX deltas are:

| Regime | $n$ | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) |
|---|---:|---|---|
| normal | 3,095 | **−8.14 [−9.29, −7.02]** | **−51.3 [−52.6, −50.0]** |
| long_weekend | 496 | **−6.65 [−9.04, −4.61]** | **−53.4 [−56.7, −50.3]** |
| high_vol | 1,128 | **−7.62 [−9.79, −5.60]** | **−43.5 [−46.2, −40.5]** |

Every regime's coverage CI excludes zero in the negative direction; the gap is not a shock-tertile artefact. The headline is that the most natural reviewer-asked baseline — "just use the market's price for uncertainty" — is *not* a competitive alternative to F1's per-stock empirical residual machinery; it is a sharp-but-miscalibrated band. Adding F1's factor-switchboard point and empirical-quantile band on top of A0_VIX (A0_VIX → A1) recovers +1.5pp of coverage [CI +0.1, +2.9] while *widening* the band by +17.5% [CI +13.3, +21.9]; the gap closes faster in `normal` (+5.3pp coverage / +42.4% wider) than in `high_vol`, where A0_VIX is *over*-conservative on this sample (Δcov −8.5pp). The §7.4 serving-layer evidence shows that the full deployed Oracle (per-stock vol indexing + log-log regression + empirical-quantile inversion + per-target buffer) closes the residual gap entirely; the A0_VIX rung therefore frames F1's per-stock machinery as the load-bearing path from the natural baseline to a calibrated served band, not as a marginal refinement of an already-defensible default.

The B0 variant strips the factor-adjusted point while holding A7's empirical CI width *constant* and centring on the stale point estimate. Pooled $\Delta$ coverage is −0.4pp (CI [−1.2, +0.4]) — not statistically distinguishable from A7. The MAE rises 4.8 bps (94.8 vs 90.0). The factor-switchboard point's contribution is therefore concentrated in *point accuracy*, not in served-band coverage; at $n = 5{,}996$ the coverage contribution of the point shift is below detection.

## 7.3 Per-regime effect — where the regime-specific knobs earn their keep

The pooled view obscures three regime-specific findings.

| A → B | regime | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) |
|---|---|---|---|
| A0 → A1 (factor pt + emp Q) | normal | **−3.0 [−3.9, −2.2]** | **−29.9 [−32.3, −27.5]** |
|  | long_weekend | **−6.0 [−8.6, −3.9]** | **−50.7 [−55.0, −46.1]** |
|  | high_vol | **−14.5 [−18.3, −11.0]** | **−52.1 [−55.3, −49.0]** |
| A1 → A2 (VIX-scale) | normal | **−1.5 [−2.2, −0.8]** | **−15.1 [−17.1, −13.3]** |
|  | long_weekend | −1.9 [−3.6, 0.0] | **−16.6 [−21.6, −11.2]** |
|  | high_vol | **+7.2 [+5.3, +9.6]** | **+41.1 [+34.2, +48.7]** |
| A2 → A3 (log-log) | normal | **−0.7 [−1.2, −0.2]** | **−2.2 [−3.1, −1.2]** |
|  | long_weekend | −0.5 [−2.3, +1.1] | −1.7 [−4.3, +0.8] |
|  | high_vol | **+3.2 [+1.4, +5.1]** | **+15.6 [+9.6, +22.0]** |
| A4 → A6 (long-weekend flag) | normal | −0.1 [−0.4, +0.1] | **−1.8 [−2.1, −1.5]** |
|  | long_weekend | +1.1 [−0.3, +2.4] | **+10.6 [+8.5, +12.9]** |
|  | high_vol | −0.1 [−0.6, +0.4] | +0.1 [−0.6, +0.9] |

Three observations.

1. **The log-log VIX regression (A1 → A3 cumulatively) exists for the `high_vol` regime.** It lifts high-vol coverage by 10.4pp (cumulative across A2 + A3) at the cost of 65% wider bands — the insurance trade a consumer wants in elevated-volatility weekends. In `normal` regime the same transition *costs* coverage by 2.2pp at no sharpness gain, which is why the §4.4 hybrid policy assigns `high_vol` to F0_stale rather than to A7.
2. **The long-weekend flag is a localised effect.** It widens bands by +10.6% **only in its own regime** (`long_weekend`), with statistically-flat effects in `normal` and `high_vol`. The flag costs nothing outside its regime and earns its keep inside it.
3. **The earnings regressor is not detectable in any regime.** Every cell of A4 → A5 has a 95% CI containing zero on both coverage and sharpness. A weekend-ahead binary flag is too coarse to carry signal through the empirical-quantile band-construction at $n = 5{,}996$. We retain it for *auditability* — every PricePoint receipt records whether the flag was active — but not for performance, and we flag it as a v2 candidate for replacement with a finer event-granularity dataset (scheduled datetime + implied-move).

## 7.4 Serving-layer matrix — hybrid policy and calibration buffer

The forecaster ladder of §7.1–§7.3 measures the *raw-forecaster* contribution of each knob. The serving layer adds two additional design choices: the per-regime forecaster selection (§4.4) and the per-target empirical buffer (§4.3). We isolate these by re-serving the same OOS 2023+ panel (1,730 rows × 173 weekends) at the §6 headline target $\tau = 0.95$ across five deployed-comparator cells (C0–C4) plus two F0_VIX challenger cells (B1, B2; equity-only, 1,384 rows × 173 weekends). The calibration surface is fit on the pre-2023 calibration set and held fixed; the deployed buffer at $\tau = 0.95$ is $0.020$ per `BUFFER_BY_TARGET` (§4.3).

| Cell | Forecaster policy | Buffer | Realised | Half-width (bps) | Kupiec $p_{uc}$ | Christoffersen $p_{ind}$ |
|---|---|---:|---:|---:|---:|---:|
| C0 | F1 everywhere | 0.000 | 0.922 | 360.1 | 0.000 | 0.146 |
| C1 | F0 everywhere | 0.000 | 0.921 | 292.9 | 0.000 | 0.470 |
| C2 | hybrid (F1 normal/LW, F0 high_vol) | 0.000 | 0.921 | 351.6 | 0.000 | 0.381 |
| C3 | F1 everywhere | 0.020 | 0.949 | 454.1 | 0.869 | 0.220 |
| C4 | **hybrid (deployed Oracle)** | **0.020** | **0.950** | **443.5** | **0.956** | **0.483** |
| B1 | F0_VIX everywhere (equity-only) | 0.000 | 0.860 | 238.1 | 0.000 | 0.129 |
| B2 | F0_VIX everywhere (equity-only) | 0.020 | 0.876 | 266.4 | 0.000 | 0.059 |

| Comparison | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) | Interpretation |
|---|---|---|---|
| C0 → C2 (hybrid effect, no buffer) | −0.1 [−0.7, +0.5] | −2.4 [−5.6, +1.1] | Hybrid alone doesn't change realised coverage; saves ~2% bandwidth |
| **C0 → C3 (buffer effect, no hybrid)** | **+2.7 [+1.9, +3.6]** | **+26.1 [+24.8, +27.4]** | Buffer closes OOS coverage gap at ~26% wider bands |
| **C2 → C4 (buffer effect, with hybrid)** | **+2.9 [+2.1, +3.9]** | **+26.1 [+24.7, +27.6]** | Buffer effect is approximately independent of hybrid |
| **C0 → C4 (total serving layer)** | **+2.8 [+2.0, +3.8]** | **+23.2 [+19.3, +27.6]** | Full Oracle delivers target coverage; pays ~23% sharpness vs raw F1 |
| **B1 → B2 (F0_VIX buffer effect)** | **+1.7 [+0.9, +2.5]** | **+11.9 [+10.8, +12.9]** | Deployed buffer recovers <2pp of F0_VIX's 9pp coverage gap |
| **B2 → C4 (F0_VIX buffered vs deployed Oracle)** | **+6.7 [+4.3, +9.1]** | **+88.5 [+79.9, +96.3]** | C4 covers 6.7pp more than F0_VIX-buffered, on equity-matched rows; C4 bands ~88% wider |
| **B2 → C3 (F0_VIX buffered vs F1-everywhere buffered)** | **+6.7 [+4.2, +9.2]** | **+93.7 [+87.5, +100.4]** | F1-everywhere covers 6.7pp more than F0_VIX-buffered, ~94% wider |

Negative $\Delta$ sharpness means tighter bands; CIs are 95% block-bootstrap by weekend over 1,000 resamples (`reports/tables/v1b_serving_ablation_bootstrap.csv`).

**Four findings.**

1. **The per-target buffer is the load-bearing serving-layer knob for coverage.** $+2.7$ to $+2.9$pp of the OOS gap is closed by the buffer at $\tau = 0.95$; the hybrid regime policy alone closes essentially none of it. Without the buffer, surface inversion delivers $0.92$ realised against a $0.95$ target and Kupiec rejects at every cell.

2. **The hybrid regime policy is the empirically preferred deployment choice on the evaluated sample, not a binary necessity.** At the deployed buffer, both F1-everywhere (C3) and the hybrid (C4) pass Kupiec and Christoffersen at $\alpha = 0.05$. The hybrid is *weakly dominant* over F1-everywhere on both evaluation axes: bands tighten from $454.1 \to 443.5$ bps ($-2.3\%$), Kupiec margin tightens from $p_{uc} = 0.869$ to $p_{uc} = 0.956$, and Christoffersen margin tightens from $p_{ind} = 0.220$ to $p_{ind} = 0.483$, with no observed trade-off between the two criteria. This is the empirical content of property P3 of §3.4 — *per-regime serving efficiency* defined as empirical dominance on the evaluated sample under (i) mean bandwidth at matched realised coverage and (ii) the Christoffersen independence $p$-value as a violation-clustering diagnostic (not as a decision-theoretic optimisation target). The hybrid is the preferred deployment choice under the paper's evaluation objective.

3. **The buffer effect is approximately additive to the hybrid effect.** The buffer-vs-no-buffer delta is $+2.7$pp without hybrid (C0 → C3) and $+2.9$pp with hybrid (C2 → C4) — bracketing CIs overlap, so we cannot reject buffer-hybrid additivity at $n = 173$ OOS weekends. Practically: deciding hybrid-vs-no-hybrid does not affect the buffer-tuning decision, and vice versa, which simplifies the schedule re-fitting required by any V2.2 rolling rebuild (§10.1).

4. **The forward-curve-implied baseline (F0_VIX) is structurally miscalibrated through the deployed serving stack and cannot be repaired by the deployed buffer.** F0_VIX served with no buffer (B1) realises $0.860$ — a 9pp gap to target. The deployed $0.020$ buffer (B2) lifts realised coverage to $0.876$ but Kupiec still rejects at $p_{uc} \approx 0$; Christoffersen sits at $p_{ind} = 0.059$, marginal. The bootstrap delta against the deployed Oracle (B2 → C4) shows the gap is $+6.7$pp coverage [CI $+4.3, +9.1$] at $+88\%$ width [CI $+80\%, +96\%$], on the equity-matched intersection. Closing F0_VIX's calibration gap to the C4 level on this serving stack would require either (a) a buffer schedule large enough to wipe out the implied-vol baseline's headline width advantage — i.e., to ask for an $\tilde\tau \approx 0.99$ to deliver realised $0.95$, blowing F0_VIX's bands well past F1's — or (b) per-symbol implied vol from OPRA / Cboe options chains, the natural v2 baseline (§10). The empirical content of finding 4 is that the most-natural reviewer-asked baseline — "use the market's price for uncertainty" — is sharper than F1 on its raw bands but cannot meet a calibrated coverage target through the deployed serving layer; F1's per-symbol vol indexing + log-log regression + empirical-quantile inversion is what closes that gap on freely-available data.

The historical record of the v1 development sequence — including an earlier scalar 0.025 buffer that produced cleanly-different numbers, in particular a Christoffersen rejection at the F1-everywhere cell — is preserved in `reports/v1b_ablation.md` and the methodology evolution log at `reports/methodology_history.md`.

## 7.5 Load-bearing-vs-cosmetic taxonomy (v1 architecture)

Synthesising §7.2–§7.4 *under the v1 architecture* (calibration surface + per-target buffer + per-regime forecaster choice). The ladder this taxonomy summarises is what produced the v1 deployment numbers in `reports/v1b_calibration.md` and was the architecture that shipped before the §7.7 Mondrian ablation. The deployed M5 architecture inherits some pieces (factor-switchboard point, regime classifier $\rho$, per-target OOS-fit schedule) and removes others (per-symbol vol index inside the conditional sigma fit, earnings flag, long-weekend flag, calibration surface, hybrid forecaster policy):

| Component | Role under v1 | Status under M5 (§7.7) | Evidence |
|---|---|---|---|
| Factor-switchboard point (A0 → A1) | **Load-bearing for sharpness.** Pooled 39.3% tighter at $n = 5{,}996$. | **Inherited.** M5's $\hat P_{\text{Mon},r}$ is the same factor-adjusted point. | §7.2, §4.1 |
| Empirical residual quantile (A1) | **Load-bearing for sharpness** in conjunction with the factor point. | **Inherited but restructured.** M5 takes the residual quantile per-regime instead of per-(symbol, regime, claimed) — same family of estimator, simpler stratification. | §7.2, §4.2 |
| VIX-scaled residual standardisation + log-log VIX regression (A1 → A3) | **Load-bearing for `high_vol` coverage** under v1. Cumulative +10.4pp coverage in `high_vol` at the cost of 65% wider bands. | **Cosmetic under M5.** §7.7 shows the regime classifier $\rho$ alone (without VIX-scaling inside the conditional sigma) recovers the same coverage at narrower width via Mondrian conformal. | §7.3, §7.7.2 |
| Per-symbol vol index (VIX / GVZ / MOVE) | **Load-bearing for non-equity RWA generalisation** under v1's log-log conditional sigma fit. | **Cosmetic under M5.** The Mondrian quantile is taken over the panel residual distribution stratified only by regime; per-symbol vol indices were absorbed into the v1 conditional-sigma layer that M5 removes. | §5.4, §7.2, §7.7 |
| Regime classifier $\rho$ | **Load-bearing for distribution-shift calibration and `high_vol` tail protection.** Train-fit constant buffer undercovers OOS by 5–14pp at $\tau \leq 0.95$ (Kupiec $p_{uc} < 10^{-6}$); the regime classifier delivers calibration on the OOS slice that the constant-buffer baseline cannot. | **Inherited and now the dominant load-bearing piece.** M5 makes the regime classifier the *only* feature inside the conformal lookup; everything else collapses around it. | §7.6, §7.7, §4.2 |
| Long-weekend flag | **Load-bearing inside `long_weekend` regime, neutral outside** under v1's conditional-sigma fit. | **Cosmetic under M5.** Long-weekend conditioning is now absorbed entirely into $q_\text{long\_weekend}(\tau)$ — the trained quantile for the regime — without a separate flag inside conditional sigma. | §7.3 |
| Earnings-next-week flag | **Disclosed for auditability under v1; no detectable performance contribution at our sample size.** | **Removed under M5.** | §7.3 |
| Empirical calibration buffer (per-target schedule) | **Load-bearing for OOS coverage** under v1. +2.7 to +2.9pp coverage closes the OOS gap; without it, surface inversion alone delivers raw realised 0.92 at $\tau = 0.95$. | **Restructured into M5's $c(\tau)$ multiplicative bump.** Same 4-scalar parameter budget, same OOS-fit role, multiplicative on the conformal quantile rather than additive on the target. | §7.4, §4.3 |
| Hybrid regime-to-forecaster policy | **Empirically preferred deployment choice under v1.** Weakly dominant over F1-everywhere on (sharpness, Christoffersen margin). | **Removed under M5.** A single conformal lookup keyed on $\rho$ replaces the per-regime forecaster choice; M5 does not need an "F0_stale in high_vol" branch because the per-regime quantile $q_\text{high\_vol}(\tau)$ absorbs the high-vol widening. | §7.4, §7.7 |
| Forward-curve-implied Gaussian baseline (A0_VIX) | **Disclosed challenger under v1, not deployed.** | **Subsumed under M5.** Forward-curve-implied conditioning enters the M5 fit through the regime classifier (high-vol weekends are flagged off VIX), not as a separate forecaster rung. | §7.2, §7.4 |
| Per-target $\delta(\tau)$ shift on the served quantile | n/a (v1 had no $\delta$-shift) | **New under M5.** Walk-forward-fit conservative overshoot, the M5 analogue of v1's BUFFER_BY_TARGET conservative-tuning. 4 scalars; deployed $\{0.05, 0.02, 0.00, 0.00\}$. | §7.7.4, §4.3 |

The taxonomy reads top-to-bottom as the chronological narrowing of the v1 architecture: factor switchboard and regime classifier survive as load-bearing; the conditional-sigma machinery on top of them (VIX log-log, per-symbol vol indices, earnings flag, long-weekend flag) and the calibration-surface inversion are dropped under M5; the per-target tuning schedule is restructured (additive buffer → multiplicative bump + walk-forward shift) but kept at the same 4-scalar OOS budget. §7.6 and §7.7 are the bridging stress tests that justified the simplification: §7.6 rules out the deployable baseline that strips regime structure entirely; §7.7 isolates the deployable baseline that keeps regime structure and removes the rest.

## 7.6 Constant-buffer baseline (width-at-coverage)

§7.1–§7.5 strips knobs from inside $\texttt{F1\_emp\_regime}$ and the serving layer; §7.4's A0_VIX cell tests the natural alternative-data baseline. This subsection compares the deployed Oracle against the *external* baseline most likely to be deployed by a protocol team unwilling to absorb the modelling complexity: the Pyth/Chainlink Friday close held forward, with a single global symmetric buffer $b(\tau)$ per claimed quantile. One parameter per $\tau$. No factor switchboard, no empirical residual quantile, no regime model, no per-symbol tuning, no calibration surface. The mechanic is

$$\big[\;p_{\text{Fri}}\,(1 - b(\tau)),\;p_{\text{Fri}}\,(1 + b(\tau))\;\big],\qquad b(\tau)\;\text{calibrated globally on the training panel}.$$

Sample-size argument for taking it seriously. Pooled across 10 symbols and 466 training weekends, the constant-buffer fit has $N = 4{,}266$ observations supporting one scalar — a coverage CI on the holdout of roughly $\pm 2$pp at $\tau = 0.95$ — versus the per-(symbol, regime) fit windows of the deployed Oracle that ride at $N \approx 50$–$250$ for the rolling residual-quantile estimate ($\pm 5$–$15$pp). If the regime model only delivers a small width reduction at matched realised coverage, the modelling complexity isn't earning its keep. We test against three measures: realised coverage at the consumer's $\tau$, mean half-width at matched coverage, and per-regime decomposition. Raw tables: `reports/tables/v1b_constant_buffer_*.csv`. Script: `scripts/run_constant_buffer_baseline.py`.

### 7.6.1 Trained-buffer fit

Each $b(\tau)$ is the smallest multiplicative buffer such that the pooled training panel's empirical coverage of $[p_{\text{Fri}}(1 - b), p_{\text{Fri}}(1 + b)]$ is $\geq \tau$ — equivalently, the empirical $\tau$-quantile of $|p_{\text{Mon}} - p_{\text{Fri}}|/p_{\text{Fri}}$ on the pre-2023 calibration set ($N = 4{,}266$, 466 weekends, 2014-01-17 → 2022-12-30):

| $\tau$ | $b(\tau)$ | training realised | half-width (bps) |
|---:|---:|---:|---:|
| 0.68 | 0.76% | 0.682 | 76.0 |
| 0.85 | 1.40% | 0.850 | 140.0 |
| 0.95 | 2.72% | 0.950 | 272.0 |
| 0.99 | 6.95% | 0.990 | 695.0 |

These buffers reproduce the $\tau$-quantile in-sample by construction.

### 7.6.2 Train-fit baseline on the OOS slice

We carry the trained $b(\tau)$ to the same 2023+ panel that §7.4 evaluates the Oracle on (1,730 rows × 173 weekends), apply the symmetric band, and report pooled diagnostics alongside the deployed Oracle (cell C4 of §7.4, the hybrid regime-policy with the per-target buffer schedule):

| $\tau$ | method | realised | half-width (bps) | $p_{uc}$ | $p_{ind}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | constant buffer (train-fit) | 0.538 | 76.0 | 0.000 | 0.001 |
| 0.68 | deployed Oracle | 0.680 | 136.1 | 0.984 | 0.645 |
| 0.85 | constant buffer (train-fit) | 0.731 | 140.0 | 0.000 | 0.000 |
| 0.85 | deployed Oracle | 0.856 | 251.4 | 0.477 | 0.182 |
| 0.95 | constant buffer (train-fit) | 0.897 | 272.0 | 0.000 | 0.013 |
| 0.95 | deployed Oracle | 0.950 | 443.5 | 0.956 | 0.483 |
| 0.99 | constant buffer (train-fit) | 0.984 | 695.0 | 0.018 | 0.927 |
| 0.99 | deployed Oracle | 0.972 | 522.8 | 0.000 | 0.897 |

The training-fit constant buffer **catastrophically undercovers** at every $\tau \leq 0.95$: the OOS deficit is $-14.2$pp at $\tau = 0.68$, $-12.0$pp at $\tau = 0.85$, $-5.4$pp at $\tau = 0.95$, all rejecting Kupiec at $p_{uc} < 10^{-6}$. The mechanism is non-stationarity: $b(\tau)$ is calibrated on a 2014–2022 window whose pooled weekend-volatility distribution is calmer than the 2023+ holdout (post-COVID, post-rate-hikes, plus the 2024–2026 single-stock vol regime including MSTR, NVDA, TSLA, HOOD names with distributional shift relative to their 2014–2022 history). At $\tau = 0.99$ the trained buffer overcovers (0.984) and Kupiec rejects from the other side. The Oracle delivers calibrated coverage at $\tau \in \{0.68, 0.85, 0.95\}$ on the same slice and hits the disclosed finite-sample tail ceiling at $\tau = 0.99$ (§9.1).

The fair conclusion of §7.6.2 alone is therefore: **the deployable constant-buffer baseline does not deliver coverage on the holdout. The Oracle does.** This is the *adaptivity-to-distribution-shift* contribution of the regime model and the deployment-tuned buffer schedule. But it is not yet a width-at-coverage claim — the Oracle is also wider, and width comparisons across miscalibrated cells aren't meaningful.

### 7.6.3 Coverage-matched comparison (the headline metric)

To answer the width-at-coverage question — at the same realised coverage on the same OOS slice, how much narrower is the regime model than a constant buffer? — we re-fit $b(\tau)$ post-hoc on the OOS slice itself, choosing the smallest $b$ such that pooled OOS coverage matches the Oracle's realised coverage at that $\tau$. This is an *oracle-fit* baseline that uses the holdout to set $b$; it is not deployable, but it gives the constant buffer the most generous possible width-at-coverage trade-off and removes the train/holdout distribution-shift confound:

| $\tau$ | matched $b$ | matched-CB realised | matched-CB hw (bps) | Oracle realised | Oracle hw (bps) | $\Delta$ width (Oracle − CB) |
|---:|---:|---:|---:|---:|---:|---|
| 0.68 | 1.21% | 0.680 | 120.9 | 0.680 | 136.1 | **+12.4% [+7.2, +18.5]** |
| 0.85 | 2.26% | 0.857 | 226.4 | 0.856 | 251.4 | **+11.1% [+6.1, +16.4]** |
| 0.95 | 3.96% | 0.951 | 395.6 | 0.950 | 443.5 | **+12.2% [+6.4, +18.8]** |
| 0.99 | 5.46% | 0.972 | 545.8 | 0.972 | 522.8 | $-4.3\%$ [−9.8, +1.6] |

Bootstrap CIs are 95% block-bootstrap by weekend over 1,000 resamples (`v1b_constant_buffer_bootstrap.csv`); deltas in bold have CIs that exclude zero.

**The Oracle is 11–12% wider than a coverage-matched constant buffer at every $\tau \leq 0.95$.** The CI excludes zero in all three cases. Phrased against the test the constant-buffer challenge sets — "the regime model has earned its place if it produces a $\tau = 0.95$ band on average 200 bps narrower than the constant-buffer baseline at the same realised coverage" — the regime model is **47.9 bps wider**, not narrower, than the matched constant buffer at $\tau = 0.95$. Only at $\tau = 0.99$ does the regime model match (and marginally beat) the constant buffer in pooled width-at-coverage, with a CI that straddles zero.

The regime model's modelling complexity therefore does **not** buy pooled width-at-coverage on the OOS slice; it buys *coverage at all* on a non-stationary distribution where the deployable constant buffer fails by 5–14pp. This is a smaller and more honest claim than implied by a face-value reading of §6: the headline 27% sharpness premium of the deployed Oracle over its no-buffer ablation cell (C0 → C4 of §7.4) is not a sharpness premium over a deployable simpler baseline — against the simpler baseline, the buffer-equipped Oracle pays a sharpness penalty for buying calibration through the distribution shift.

### 7.6.4 Per-regime decomposition — where the regime model actually earns its keep

The pooled $+12\%$ width premium of §7.6.3 obscures a sharply regime-conditional structure. Decomposing the $\tau = 0.95$ cell:

| regime | $n$ | matched-CB realised | matched-CB hw (bps) | Oracle realised | Oracle hw (bps) | Oracle premium |
|---|---:|---:|---:|---:|---:|---|
| normal | 1,160 | 0.965 | 395.6 | 0.946 | 402.7 | $+1.8\%$ wider, $-1.9$pp coverage |
| long_weekend | 190 | 0.968 | 395.6 | 0.953 | 396.5 | $+0.2\%$ wider, $-1.6$pp coverage |
| high_vol | 380 | 0.900 | 395.6 | 0.963 | 591.6 | **$+49.5\%$ wider, $+6.3$pp coverage** |

In `normal` and `long_weekend`, the regime model is **statistically indistinguishable from a constant buffer** at matched pooled coverage on the OOS slice — the band widths bracket each other within $\pm 2\%$ and the regime model in fact *overshoots in width* by a hair while *undershooting in coverage* by 1.6–1.9pp. In `high_vol`, the regime model widens sharply ($+49.5\%$) and gains 6.3pp of coverage (96.3% vs 90.0%). The constant buffer's pooled coverage is "average right but worst where it matters most": its violations concentrate in high-vol weekends — exactly the weekends where a downstream lending protocol incurs the largest mark-to-market gap if the band fails. The matched-CB Christoffersen test reflects this directly: $p_{ind} = 0.024$ on the pooled $\tau = 0.95$ cell, *rejecting* independence at $\alpha = 0.05$, while the Oracle's $p_{ind} = 0.483$ does not. At $\tau = 0.68$ the gap is starker still — matched-CB $p_{ind} = 7.7 \times 10^{-7}$ vs Oracle 0.645.

The honest claim. The regime model's contribution is **(i) calibration through distribution shift** (training-fit constant buffer fails Kupiec by 5–14pp; Oracle passes) and **(ii) tail-protection in `high_vol` weekends** ($+49.5\%$ width premium, $+6.3$pp coverage at $\tau = 0.95$, with Christoffersen-independent violations at every $\tau \leq 0.95$). The implicit pooled-width-at-coverage claim — that the regime model produces tighter bands than a simple constant buffer at matched realised coverage — does **not survive this baseline** at any $\tau \leq 0.95$. Reviewers of §6's headline should read it conditional on the calibration property (the actual product) rather than as an unconditional sharpness improvement.

## 7.7 Mondrian conformal-by-regime baseline (the v2 candidate)

§7.6 showed that a deployable simpler baseline that strips regime structure entirely (one global symmetric buffer per $\tau$) fails to deliver coverage on the 2023+ OOS slice — the regime classifier is doing real work. The natural follow-up tightens the question: the §7.5 taxonomy isolated `regime_pub` as the load-bearing piece of the deployed Oracle, and the F1_emp_regime forecaster machinery (factor switchboard, log-log VIX, per-symbol vol index, earnings flag, long-weekend flag) plus the per-target buffer schedule as the rest of the architecture. Does that machinery *on top of* `regime_pub` earn its place against a Mondrian split-conformal quantile fit per regime? We test a five-rung Mondrian ladder, all on the same calibration set + 2023+ OOS panel + per-target tuning budget the deployed Oracle uses. Raw tables: `reports/tables/v1b_mondrian_*.csv`, `reports/tables/v1b_oracle_walkforward*.csv`. Scripts: `scripts/run_mondrian_regime_baseline.py` (M1–M5 OOS), `scripts/run_mondrian_walkforward_pit.py` (6-split walk-forward + density tests), `scripts/run_mondrian_delta_sweep.py` (δ-shift schedule sweep).

### 7.7.1 Mondrian ladder design

Each variant fits a per-regime conformal quantile $q_r(\tau)$ — the empirical $\tau$-quantile of the absolute relative residual $|p_{\text{Mon}} - \hat p_{\text{Mon},r}| / p_{\text{Mon}}$ on the calibration set within regime $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ — and serves $[\hat p_{\text{Mon},r}(1 - q_r(\tau)),\;\hat p_{\text{Mon},r}(1 + q_r(\tau))]$. The ladder strips and then re-introduces knobs:

- **M1.** Stale point ($\hat p_{\text{Mon},r} = p_{\text{Fri}}$) + per-regime quantile, no further tuning.
- **M2.** Factor-adjusted point ($\hat p_{\text{Mon},r} = p_{\text{Fri}} \cdot R_f$ from the §7.4 factor switchboard) + per-regime quantile.
- **M3.** Factor-adjusted point + per-(symbol, regime) quantile (Mondrian on regime × symbol; tests whether per-symbol residual-quantile bins add anything over per-regime pooled bins, given $N \approx 50$–$300$ per cell).
- **M4.** Factor-adjusted point + per-regime quantile re-fit *post-hoc on the OOS slice itself* (oracle-fit, non-deployable; gives the upper bound of what per-regime conformal can achieve on this panel).
- **M5.** Factor-adjusted point + per-regime quantile fit on the train panel + a per-target multiplicative bump $c(\tau)$ tuned on the OOS slice — twelve trained scalars (3 regimes × 4 anchors) plus four OOS scalars, exactly matching the deployed Oracle's per-target buffer schedule parameter budget.

M5 is the deployable variant. The $c(\tau)$ bump is the structural analogue of the deployed Oracle's `BUFFER_BY_TARGET` schedule: both are 4 OOS-tuned scalars, both push pooled OOS realised coverage to the nominal $\tau$.

### 7.7.2 OOS pooled results

Carrying each variant to the same 2023+ panel that §7.4 evaluates the Oracle on (1,730 rows × 173 weekends, 10 symbols):

| $\tau$ | method | realised | hw (bps) | $p_{uc}$ | $p_{ind}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | deployed Oracle | 0.680 | 136.1 | 0.984 | 0.645 |
| 0.68 | M1 stale + regime-CP | 0.530 | 76.2 | 0.000 | 0.068 |
| 0.68 | M2 fa + regime-CP | 0.547 | 73.5 | 0.000 | 0.776 |
| 0.68 | M3 fa + (symbol,regime)-CP | 0.572 | 92.2 | 0.000 | $2.1{\times}10^{-4}$ |
| 0.68 | M4 fa + regime-CP (oracle-fit) | 0.682 | 109.5 | 0.893 | 0.105 |
| 0.68 | M5 fa + regime-CP + $c(\tau)$ | 0.680 | 110.2 | 0.975 | 0.025 |
| 0.85 | deployed Oracle | 0.856 | 251.4 | 0.477 | 0.182 |
| 0.85 | M1 | 0.714 | 136.0 | 0.000 | $5.3{\times}10^{-5}$ |
| 0.85 | M2 | 0.738 | 138.1 | 0.000 | 0.248 |
| 0.85 | M3 | 0.764 | 158.3 | 0.000 | $5.8{\times}10^{-4}$ |
| 0.85 | M4 oracle-fit | 0.851 | 196.7 | 0.866 | 0.623 |
| 0.85 | M5 deployable | 0.850 | 201.0 | 0.973 | 0.516 |
| 0.95 | deployed Oracle | 0.950 | 443.5 | 0.956 | 0.483 |
| 0.95 | M1 | 0.890 | 269.1 | 0.000 | 0.217 |
| 0.95 | M2 | 0.910 | 272.7 | $8.2{\times}10^{-12}$ | 0.396 |
| 0.95 | M3 | 0.916 | 293.6 | $1.9{\times}10^{-9}$ | 0.002 |
| 0.95 | M4 oracle-fit | 0.951 | 345.0 | 0.782 | 0.760 |
| 0.95 | M5 deployable | 0.950 | 354.5 | 0.956 | 0.912 |
| 0.99 | deployed Oracle | 0.972 | 522.8 | 0.000 | 0.897 |
| 0.99 | M1 | 0.978 | 650.7 | $1.6{\times}10^{-5}$ | 0.854 |
| 0.99 | M2 | 0.986 | 629.6 | 0.081 | 0.794 |
| 0.99 | M3 | 0.973 | 605.1 | $3.2{\times}10^{-9}$ | 0.126 |
| 0.99 | M4 oracle-fit | 0.991 | 684.7 | 0.570 | 0.415 |
| 0.99 | M5 deployable | 0.990 | 677.5 | 0.942 | 0.344 |

Read M1 → M5 as a ladder. M1 (stale + per-regime quantile) and M2 (factor-adjusted + per-regime quantile) reproduce §7.6's finding from the other side: a deployable per-regime conformal lookup, with no further tuning, undercovers the 2023+ slice by 6–14pp at every $\tau \leq 0.95$ — the regime classifier alone is not enough; the calibration set is non-stationary in the same way the constant-buffer baseline of §7.6 hits. M3 (per-symbol Mondrian) does worse on Christoffersen because the per-(symbol, regime) bins thin out to $N \approx 50$–$300$, and the rolling residual-quantile estimator gets noisy. M4 (oracle-fit) shows the headroom — per-regime conformal at coverage matched to the Oracle delivers 110/197/345/685 bps versus the Oracle's 136/251/444/523 bps. M5 closes essentially all the M4 gap with the same 4-scalar parameter budget the Oracle uses, and matches the Oracle's pooled OOS realised coverage to within 0.2pp at every $\tau$.

Block-bootstrap CIs by weekend (1,000 resamples; `v1b_mondrian_bootstrap.csv`) on the M5 − Oracle deltas:

| $\tau$ | $\Delta$ coverage (pp) | $\Delta$ width (%) |
|---:|---:|---:|
| 0.68 | $+0.02$ [$-2.60$, $+2.72$] | $-19.1\%$ [$-22.6$, $-15.7$] |
| 0.85 | $-0.56$ [$-2.66$, $+1.45$] | $-20.0\%$ [$-24.0$, $-15.9$] |
| 0.95 | $-0.05$ [$-1.45$, $+1.33$] | $-20.0\%$ [$-23.9$, $-15.6$] |
| 0.99 | $+1.82$ [$+0.92$, $+2.89$] | $+29.6\%$ [$+23.2$, $+36.2$] |

Coverage CIs straddle zero at every $\tau \leq 0.95$. **At $\tau \leq 0.95$, M5 is 19–20% narrower than the deployed Oracle at indistinguishable realised coverage on the OOS slice; at $\tau = 0.99$, M5 widens to hit the nominal target where the deployed Oracle hits its bounds-grid ceiling.** §7.6 showed the deployable baseline that strips regime structure entirely fails to deliver coverage at all; §7.7's M5 shows the deployable baseline that *keeps* the regime classifier and replaces the F1 forecaster machinery with a per-regime conformal quantile recovers calibration *and* delivers it at materially narrower width than F1.

### 7.7.3 Walk-forward (the OOS-fit confound check)

The pooled OOS comparison is contaminated for both methods in the same direction: both $c(\tau)$ and `BUFFER_BY_TARGET` are 4 scalars tuned on the same 2023+ slice they're then evaluated on. To put both methods on the same OOS-fit footing, we re-run each on a 6-split expanding-window walk-forward over the 2023+ slice (split fractions 0.2, 0.3, 0.4, 0.5, 0.6, 0.7; tune the 4 scalars on the early fraction, evaluate on the rest), pooling test-fold realised coverage and mean half-width across symbols within each split:

| $\tau$ | M5 realised (mean ± σ) | M5 hw (bps) | Oracle realised (mean ± σ) | Oracle hw (bps) |
|---:|---:|---:|---:|---:|
| 0.68 | $0.614 \pm 0.014$ | 104 | $0.735 \pm 0.010$ | 186 |
| 0.85 | $0.814 \pm 0.013$ | 196 | $0.878 \pm 0.012$ | 287 |
| 0.95 | $0.943 \pm 0.009$ | 357 | $0.971 \pm 0.017$ | 526 |
| 0.99 | $0.991 \pm 0.005$ | 745 | $0.979 \pm 0.008$ | 609 |

Bare M5 ($\delta = 0$) is *anti-conservative* on walk-forward at $\tau \leq 0.85$: deficits are $-6.6$pp, $-3.6$pp, $-0.7$pp, $+0.1$pp at $\tau = 0.68, 0.85, 0.95, 0.99$. The deployed Oracle is *conservative* on walk-forward at the same anchors: deficits $+5.5$pp, $+2.8$pp, $+2.1$pp, $-1.1$pp. The asymmetry is a property of how each method's 4-scalar OOS schedule generalises across splits, not of the conformal-vs-empirical-quantile distinction itself: the Oracle's `BUFFER_BY_TARGET` is post-hoc-tuned to push pooled OOS realised coverage *above* nominal (a deployment-quality conservative tuning); bare M5 $c(\tau)$ is post-hoc-tuned to *match* nominal, so per-split coverage scatters around the target. The fix is to push M5 to the same conservative side the Oracle sits on by serving it at $c(\tau + \delta(\tau))$ for a small per-anchor $\delta$ — the M5 analogue of the `BUFFER_BY_TARGET` overshoot.

### 7.7.4 δ-shift schedule

A δ-shift sweep over $\delta \in \{0.00, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07\}$ per anchor (`v1b_mondrian_delta_sweep.csv`) selects the smallest schedule that aligns walk-forward realised coverage with nominal at each anchor: $\delta = \{0.68\!:\!0.05,\;0.85\!:\!0.02,\;0.95\!:\!0.00,\;0.99\!:\!0.00\}$. Final M5 walk-forward result with $\delta$ schedule applied, alongside the deployed Oracle on the same splits:

| $\tau$ | M5 (with δ) realised | M5 hw (bps) | Oracle realised | Oracle hw (bps) | M5 width advantage |
|---:|---:|---:|---:|---:|---|
| 0.68 | 0.672 (Kupiec $p=0.43$) | 124 | 0.735 | 186 | $-33\%$ |
| 0.85 | 0.832 ($p=0.37$) | 215 | 0.878 | 287 | $-25\%$ |
| 0.95 | 0.943 ($p=0.36$) | 357 | 0.971 | 526 | $-32\%$ |
| 0.99 | 0.991 ($p=0.32$) | 746 | 0.979 | 609 | $+22\%$, **target hit** |

**M5 with the δ-shift schedule passes Kupiec at every anchor on walk-forward at 25–33% narrower mean half-width than the deployed Oracle through $\tau \leq 0.95$.** At $\tau = 0.99$, M5 trades width for target attainment — it hits the nominal 0.99 where the deployed Oracle hits the structural finite-sample ceiling at 0.979 (cf. §9.1). The $\delta$ schedule is itself part of the M5 deployment recipe; it is the load-bearing OOS-fit complement to the trained per-regime quantile table, structurally parallel to (but smaller than) the Oracle's `BUFFER_BY_TARGET` schedule.

### 7.7.5 Density tests on M5

Berkowitz on M5's walk-forward PIT residuals: $\mathrm{LR} = 173.1$, $\hat\rho = 0.31$, $\mu_z = 0.018$, $\sigma_z^2 = 0.990$ (`v1b_mondrian_density_tests.csv`). DQ at $\tau = 0.95$: stat $= 32.1$, $p = 5.7 \times 10^{-6}$, violation rate $4.97\%$ over 86 violating weekends, with the rejection driven by clustering of violations. **M5 has the same per-anchor-only calibration profile as the deployed Oracle (cf. §6 abstract; §9.5).** Per-anchor Kupiec passes at every walk-forward target; Berkowitz and DQ both reject. The shared diagnosis is structural rather than method-specific: the regime classifier $\rho$ is a coarse three-bin index over the joint distribution of weekend conditioning information, and the residuals retain unexplained autocorrelation through high-vol weekend clusters. M5 does not fix the density-test rejection. It does not make it worse either. Full-distribution conformal calibration remains the v3 research target identified in §10.

### 7.7.6 Per-regime decomposition at $\tau = 0.95$

Decomposing the same M5-vs-Oracle $\tau = 0.95$ cell that §7.6.4 decomposed for the constant-buffer baseline:

| regime | $n$ | M5 realised | M5 hw (bps) | Oracle realised | Oracle hw (bps) | Oracle premium |
|---|---:|---:|---:|---:|---:|---|
| normal | 1,160 | 0.939 | 279.9 | 0.946 | 402.7 | $+43.9\%$ wider, $+0.7$pp coverage |
| long_weekend | 190 | 0.984 | 403.4 | 0.953 | 396.5 | $-1.7\%$ wider, $-3.1$pp coverage |
| high_vol | 380 | 0.968 | 557.8 | 0.963 | 591.6 | $+6.1\%$ wider, $-0.5$pp coverage |

§7.6.4's decomposition put the Oracle's pooled width premium in `high_vol` (constant buffer pooled-coverage right but worst where it matters). §7.7.6's decomposition puts the Oracle's pooled width premium in `normal` — the 67% of weekends — at $+43.9\%$ wider for $+0.7$pp coverage. In `long_weekend` and `high_vol` the two methods bracket each other within $\pm 6\%$ of width. The diagnosis: F1_emp_regime + the per-target buffer schedule earns its OOS calibration *primarily by overwidening normal-regime weekends* relative to what a per-regime conformal quantile delivers. That is the operational expression of the §7.5 finding that the F1 forecaster ladder is cosmetic on top of `regime_pub`: the cosmetic layer's contribution at the deployment target ($\tau = 0.95$) is to widen the 67% of weekends where per-regime conformal would already hit nominal coverage with a tighter band.

### 7.7.7 Verdict

§7.6 ruled out the deployable baseline that strips regime structure entirely. §7.7 isolates the deployable baseline that keeps `regime_pub` and replaces the F1 forecaster machinery with a Mondrian split-conformal quantile: factor-adjusted point + per-regime conformal quantile + δ-shifted $c(\tau)$, twelve trained scalars + four OOS scalars. On the OOS slice it is 19–20% narrower than the deployed Oracle at indistinguishable realised coverage at every $\tau \leq 0.95$ (block-bootstrap CIs exclude zero on width; coverage CIs straddle zero); on the 6-split walk-forward it passes Kupiec at every anchor at 25–33% narrower mean half-width through $\tau \leq 0.95$ and hits the nominal target at $\tau = 0.99$ where the deployed Oracle hits its finite-sample ceiling; on density tests it shares the deployed Oracle's per-anchor-only calibration profile.

This identifies M5 as the **v2 deployment methodology candidate** (`reports/methodology_history.md`, 2026-05-02 entry). It is not deployed in the v1 numbers reported in §6 because the deployment migration window collides with the 2026-05-10 Colosseum hackathon submission, where the consumer-facing bands are integrated end-to-end into the Paper-4 AMM demo. The wire format (the `PriceUpdate` Borsh layout in `crates/soothsayer-consumer`) is preserved across the migration: the swap changes only the published *values* — not the on-chain decoder, not Paper 4's AMM consumer, not the property contract $P_1/P_2/P_3$ of §1. Migration tracking is at `M5_REFACTOR.md` (root); deletion of that working doc on completion is the deployment receipt.
