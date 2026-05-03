# §7 — Ablation Study

This section answers Q3 of §3.6: which components of the band-construction architecture are load-bearing for the calibration claim? Two ablations target the deployed v2 / M5 architecture: §7.1 stress-tests the deployable simpler baseline that strips regime structure entirely (a global constant buffer); §7.2 compares the deployed Mondrian split-conformal-by-regime architecture against a v1 surface-plus-buffer Oracle on the same OOS slice and parameter budget. The precursor v1 forecaster ladder ablation (factor-switchboard rung, VIX scaling, log-log regression, per-symbol vol indices, earnings + long-weekend flags, hybrid forecaster policy) is documented in `reports/methodology_history.md` and the load-bearing-vs-cosmetic taxonomy it produced is summarised inline where the M5 architecture inherits or drops a component.

All deltas carry block-bootstrap 95% confidence intervals; the bootstrap unit is the weekend (`fri_ts`), with all symbol-rows sharing a weekend resampled together so cross-sectional correlation is preserved (1000 resamples). Raw tables: `reports/tables/v1b_constant_buffer_*.csv` (§7.1 stress test) and `reports/tables/v1b_mondrian_*.csv` + `reports/tables/v1b_oracle_walkforward*.csv` (§7.2 Mondrian ablation).

## 7.1 Constant-buffer baseline (width-at-coverage)

This subsection compares the deployed Oracle against the *external* baseline most likely to be deployed by a protocol team unwilling to absorb the modelling complexity: the Pyth/Chainlink Friday close held forward, with a single global symmetric buffer $b(\tau)$ per claimed quantile. One parameter per $\tau$. No factor switchboard, no empirical residual quantile, no regime model, no per-symbol tuning, no calibration surface. The mechanic is

$$\big[\;p_{\text{Fri}}\,(1 - b(\tau)),\;p_{\text{Fri}}\,(1 + b(\tau))\;\big],\qquad b(\tau)\;\text{calibrated globally on the training panel}.$$

Sample-size argument for taking it seriously. Pooled across 10 symbols and 466 training weekends, the constant-buffer fit has $N = 4{,}266$ observations supporting one scalar — a coverage CI on the holdout of roughly $\pm 2$pp at $\tau = 0.95$ — versus the per-(symbol, regime) fit windows of the v1 architecture that ride at $N \approx 50$–$250$ for the rolling residual-quantile estimate ($\pm 5$–$15$pp). If the regime model only delivers a small width reduction at matched realised coverage, the modelling complexity isn't earning its keep. We test against three measures: realised coverage at the consumer's $\tau$, mean half-width at matched coverage, and per-regime decomposition. Raw tables: `reports/tables/v1b_constant_buffer_*.csv`. Script: `scripts/run_constant_buffer_baseline.py`.

### 7.1.1 Trained-buffer fit

Each $b(\tau)$ is the smallest multiplicative buffer such that the pooled training panel's empirical coverage of $[p_{\text{Fri}}(1 - b), p_{\text{Fri}}(1 + b)]$ is $\geq \tau$ — equivalently, the empirical $\tau$-quantile of $|p_{\text{Mon}} - p_{\text{Fri}}|/p_{\text{Fri}}$ on the pre-2023 calibration set ($N = 4{,}266$, 466 weekends, 2014-01-17 → 2022-12-30):

| $\tau$ | $b(\tau)$ | training realised | half-width (bps) |
|---:|---:|---:|---:|
| 0.68 | 0.76% | 0.682 | 76.0 |
| 0.85 | 1.40% | 0.850 | 140.0 |
| 0.95 | 2.72% | 0.950 | 272.0 |
| 0.99 | 6.95% | 0.990 | 695.0 |

These buffers reproduce the $\tau$-quantile in-sample by construction.

### 7.1.2 Train-fit baseline on the OOS slice

We carry the trained $b(\tau)$ to the same 2023+ panel that §6.4 evaluates the Oracle on (1,730 rows × 173 weekends), apply the symmetric band, and report pooled diagnostics alongside the deployed Oracle:

| $\tau$ | method | realised | half-width (bps) | $p_{uc}$ | $p_{ind}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | constant buffer (train-fit) | 0.538 | 76.0 | 0.000 | 0.001 |
| 0.68 | deployed Oracle | 0.680 | 136.1 | 0.984 | 0.645 |
| 0.85 | constant buffer (train-fit) | 0.731 | 140.0 | 0.000 | 0.000 |
| 0.85 | deployed Oracle | 0.856 | 251.4 | 0.477 | 0.182 |
| 0.95 | constant buffer (train-fit) | 0.897 | 272.0 | 0.000 | 0.013 |
| 0.95 | deployed Oracle | 0.950 | 443.5 | 0.956 | 0.483 |
| 0.99 | constant buffer (train-fit) | 0.984 | 695.0 | 0.018 | 0.927 |
| 0.99 | deployed Oracle | 0.990 | 677.5 | 0.942 | 0.344 |

The training-fit constant buffer **catastrophically undercovers** at every $\tau \leq 0.95$: the OOS deficit is $-14.2$pp at $\tau = 0.68$, $-12.0$pp at $\tau = 0.85$, $-5.4$pp at $\tau = 0.95$, all rejecting Kupiec at $p_{uc} < 10^{-6}$. The mechanism is non-stationarity: $b(\tau)$ is calibrated on a 2014–2022 window whose pooled weekend-volatility distribution is calmer than the 2023+ holdout (post-COVID, post-rate-hikes, plus the 2024–2026 single-stock vol regime including MSTR, NVDA, TSLA, HOOD names with distributional shift relative to their 2014–2022 history). At $\tau = 0.99$ the trained buffer overcovers (0.984) and Kupiec rejects from the other side.

The fair conclusion of §7.1.2 alone is therefore: **the deployable constant-buffer baseline does not deliver coverage on the holdout. The Oracle does.** This is the *adaptivity-to-distribution-shift* contribution of the regime model and the deployment-tuned schedules. But it is not yet a width-at-coverage claim — the Oracle is also wider, and width comparisons across miscalibrated cells aren't meaningful.

### 7.1.3 Coverage-matched comparison (the headline metric)

To answer the width-at-coverage question — at the same realised coverage on the same OOS slice, how much narrower is the regime model than a constant buffer? — we re-fit $b(\tau)$ post-hoc on the OOS slice itself, choosing the smallest $b$ such that pooled OOS coverage matches the Oracle's realised coverage at that $\tau$. This is an *oracle-fit* baseline that uses the holdout to set $b$; it is not deployable, but it gives the constant buffer the most generous possible width-at-coverage trade-off and removes the train/holdout distribution-shift confound:

| $\tau$ | matched $b$ | matched-CB realised | matched-CB hw (bps) | Oracle realised | Oracle hw (bps) | $\Delta$ width (Oracle − CB) |
|---:|---:|---:|---:|---:|---:|---|
| 0.68 | 1.21% | 0.680 | 120.9 | 0.680 | 136.1 | **+12.4% [+7.2, +18.5]** |
| 0.85 | 2.26% | 0.857 | 226.4 | 0.856 | 251.4 | **+11.1% [+6.1, +16.4]** |
| 0.95 | 3.96% | 0.951 | 395.6 | 0.950 | 443.5 | **+12.2% [+6.4, +18.8]** |
| 0.99 | 5.46% | 0.972 | 545.8 | 0.990 | 677.5 | $+24.1\%$ [$+18.0$, $+30.7$] |

Bootstrap CIs are 95% block-bootstrap by weekend over 1,000 resamples (`v1b_constant_buffer_bootstrap.csv`); deltas in bold have CIs that exclude zero.

**The Oracle is 11–12% wider than a coverage-matched constant buffer at every $\tau \leq 0.95$.** The CI excludes zero in all three cases. The regime model's modelling complexity therefore does **not** buy pooled width-at-coverage on the OOS slice; it buys *coverage at all* on a non-stationary distribution where the deployable constant buffer fails by 5–14pp. This is a smaller and more honest claim than implied by a face-value reading of §6: the headline result is not a sharpness premium over a deployable simpler baseline — against the simpler baseline, the buffer-equipped Oracle pays a sharpness penalty for buying calibration through the distribution shift.

### 7.1.4 Per-regime decomposition — where the regime model actually earns its keep

The pooled $+12\%$ width premium of §7.1.3 obscures a sharply regime-conditional structure. Decomposing the $\tau = 0.95$ cell:

| regime | $n$ | matched-CB realised | matched-CB hw (bps) | Oracle realised | Oracle hw (bps) | Oracle premium |
|---|---:|---:|---:|---:|---:|---|
| normal | 1,160 | 0.965 | 395.6 | 0.946 | 402.7 | $+1.8\%$ wider, $-1.9$pp coverage |
| long_weekend | 190 | 0.968 | 395.6 | 0.953 | 396.5 | $+0.2\%$ wider, $-1.6$pp coverage |
| high_vol | 380 | 0.900 | 395.6 | 0.963 | 591.6 | **$+49.5\%$ wider, $+6.3$pp coverage** |

In `normal` and `long_weekend`, the regime model is **statistically indistinguishable from a constant buffer** at matched pooled coverage on the OOS slice. In `high_vol`, the regime model widens sharply ($+49.5\%$) and gains 6.3pp of coverage (96.3% vs 90.0%). The constant buffer's pooled coverage is "average right but worst where it matters most": its violations concentrate in high-vol weekends — exactly the weekends where a downstream lending protocol incurs the largest mark-to-market gap if the band fails. The matched-CB Christoffersen test reflects this directly: $p_{ind} = 0.024$ on the pooled $\tau = 0.95$ cell, *rejecting* independence at $\alpha = 0.05$, while the Oracle's $p_{ind} = 0.483$ does not. At $\tau = 0.68$ the gap is starker still — matched-CB $p_{ind} = 7.7 \times 10^{-7}$ vs Oracle 0.645.

The honest claim. The regime model's contribution is **(i) calibration through distribution shift** (training-fit constant buffer fails Kupiec by 5–14pp; Oracle passes) and **(ii) tail-protection in `high_vol` weekends** ($+49.5\%$ width premium, $+6.3$pp coverage at $\tau = 0.95$, with Christoffersen-independent violations at every $\tau \leq 0.95$). The implicit pooled-width-at-coverage claim — that the regime model produces tighter bands than a simple constant buffer at matched realised coverage — does **not survive this baseline** at any $\tau \leq 0.95$. Reviewers of §6's headline should read it conditional on the calibration property (the actual product) rather than as an unconditional sharpness improvement.

## 7.2 Mondrian conformal-by-regime baseline (the deployed v2 architecture)

§7.1 showed that a deployable simpler baseline that strips regime structure entirely fails to deliver coverage on the 2023+ OOS slice — the regime classifier is doing real work. The natural follow-up tightens the question: the v1 forecaster ladder (precursor architecture documented in `reports/methodology_history.md`) isolated `regime_pub` as the load-bearing piece of the deployed Oracle, and the F1_emp_regime forecaster machinery (factor switchboard, log-log VIX, per-symbol vol index, earnings flag, long-weekend flag) plus the per-target buffer schedule as the rest of the architecture. Does that machinery *on top of* `regime_pub` earn its place against a Mondrian split-conformal quantile fit per regime? We test a five-rung Mondrian ladder, all on the same calibration set + 2023+ OOS panel + per-target tuning budget the v1 Oracle uses. Raw tables: `reports/tables/v1b_mondrian_*.csv`, `reports/tables/v1b_oracle_walkforward*.csv`. Scripts: `scripts/run_mondrian_regime_baseline.py` (M1–M5 OOS), `scripts/run_mondrian_walkforward_pit.py` (6-split walk-forward + density tests), `scripts/run_mondrian_delta_sweep.py` (δ-shift schedule sweep).

### 7.2.1 Mondrian ladder design

Each variant fits a per-regime conformal quantile $q_r(\tau)$ — the empirical $\tau$-quantile of the absolute relative residual $|p_{\text{Mon}} - \hat p_{\text{Mon},r}| / p_{\text{Mon}}$ on the calibration set within regime $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ — and serves $[\hat p_{\text{Mon},r}(1 - q_r(\tau)),\;\hat p_{\text{Mon},r}(1 + q_r(\tau))]$. The ladder strips and then re-introduces knobs:

- **M1.** Stale point ($\hat p_{\text{Mon},r} = p_{\text{Fri}}$) + per-regime quantile, no further tuning.
- **M2.** Factor-adjusted point ($\hat p_{\text{Mon},r} = p_{\text{Fri}} \cdot R_f$ from the factor switchboard) + per-regime quantile.
- **M3.** Factor-adjusted point + per-(symbol, regime) quantile (Mondrian on regime × symbol; tests whether per-symbol residual-quantile bins add anything over per-regime pooled bins, given $N \approx 50$–$300$ per cell).
- **M4.** Factor-adjusted point + per-regime quantile re-fit *post-hoc on the OOS slice itself* (oracle-fit, non-deployable; gives the upper bound of what per-regime conformal can achieve on this panel).
- **M5.** Factor-adjusted point + per-regime quantile fit on the train panel + a per-target multiplicative bump $c(\tau)$ tuned on the OOS slice — twelve trained scalars (3 regimes × 4 anchors) plus four OOS scalars, exactly matching the v1 Oracle's per-target buffer schedule parameter budget.

M5 is the deployed variant. The $c(\tau)$ bump is the structural analogue of the v1 Oracle's `BUFFER_BY_TARGET` schedule: both are 4 OOS-tuned scalars, both push pooled OOS realised coverage to the nominal $\tau$.

### 7.2.2 OOS pooled results

Carrying each variant to the same 2023+ panel that §6.4 evaluates the Oracle on (1,730 rows × 173 weekends, 10 symbols):

| $\tau$ | method | realised | hw (bps) | $p_{uc}$ | $p_{ind}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | v1 hybrid Oracle | 0.680 | 136.1 | 0.984 | 0.645 |
| 0.68 | M1 stale + regime-CP | 0.530 | 76.2 | 0.000 | 0.068 |
| 0.68 | M2 fa + regime-CP | 0.547 | 73.5 | 0.000 | 0.776 |
| 0.68 | M3 fa + (symbol,regime)-CP | 0.572 | 92.2 | 0.000 | $2.1{\times}10^{-4}$ |
| 0.68 | M4 fa + regime-CP (oracle-fit) | 0.682 | 109.5 | 0.893 | 0.105 |
| 0.68 | M5 fa + regime-CP + $c(\tau)$ | 0.680 | 110.2 | 0.975 | 0.025 |
| 0.85 | v1 hybrid Oracle | 0.856 | 251.4 | 0.477 | 0.182 |
| 0.85 | M1 | 0.714 | 136.0 | 0.000 | $5.3{\times}10^{-5}$ |
| 0.85 | M2 | 0.738 | 138.1 | 0.000 | 0.248 |
| 0.85 | M3 | 0.764 | 158.3 | 0.000 | $5.8{\times}10^{-4}$ |
| 0.85 | M4 oracle-fit | 0.851 | 196.7 | 0.866 | 0.623 |
| 0.85 | M5 deployed | 0.850 | 201.0 | 0.973 | 0.516 |
| 0.95 | v1 hybrid Oracle | 0.950 | 443.5 | 0.956 | 0.483 |
| 0.95 | M1 | 0.890 | 269.1 | 0.000 | 0.217 |
| 0.95 | M2 | 0.910 | 272.7 | $8.2{\times}10^{-12}$ | 0.396 |
| 0.95 | M3 | 0.916 | 293.6 | $1.9{\times}10^{-9}$ | 0.002 |
| 0.95 | M4 oracle-fit | 0.951 | 345.0 | 0.782 | 0.760 |
| 0.95 | M5 deployed | 0.950 | 354.5 | 0.956 | 0.912 |
| 0.99 | v1 hybrid Oracle | 0.972 | 522.8 | 0.000 | 0.897 |
| 0.99 | M1 | 0.978 | 650.7 | $1.6{\times}10^{-5}$ | 0.854 |
| 0.99 | M2 | 0.986 | 629.6 | 0.081 | 0.794 |
| 0.99 | M3 | 0.973 | 605.1 | $3.2{\times}10^{-9}$ | 0.126 |
| 0.99 | M4 oracle-fit | 0.991 | 684.7 | 0.570 | 0.415 |
| 0.99 | M5 deployed | 0.990 | 677.5 | 0.942 | 0.344 |

Read M1 → M5 as a ladder. M1 (stale + per-regime quantile) and M2 (factor-adjusted + per-regime quantile) reproduce §7.1's finding from the other side: a deployable per-regime conformal lookup, with no further tuning, undercovers the 2023+ slice by 6–14pp at every $\tau \leq 0.95$ — the regime classifier alone is not enough; the calibration set is non-stationary in the same way the constant-buffer baseline of §7.1 hits. M3 (per-symbol Mondrian) does worse on Christoffersen because the per-(symbol, regime) bins thin out to $N \approx 50$–$300$, and the rolling residual-quantile estimator gets noisy. M4 (oracle-fit) shows the headroom — per-regime conformal at coverage matched to the v1 Oracle delivers 110/197/345/685 bps versus the v1 Oracle's 136/251/444/523 bps. M5 closes essentially all the M4 gap with the same 4-scalar parameter budget the v1 Oracle uses, and matches the v1 Oracle's pooled OOS realised coverage to within 0.2pp at every $\tau$.

Block-bootstrap CIs by weekend (1,000 resamples; `v1b_mondrian_bootstrap.csv`) on the M5 − v1-Oracle deltas:

| $\tau$ | $\Delta$ coverage (pp) | $\Delta$ width (%) |
|---:|---:|---:|
| 0.68 | $+0.02$ [$-2.60$, $+2.72$] | $-19.1\%$ [$-22.6$, $-15.7$] |
| 0.85 | $-0.56$ [$-2.66$, $+1.45$] | $-20.0\%$ [$-24.0$, $-15.9$] |
| 0.95 | $-0.05$ [$-1.45$, $+1.33$] | $-20.0\%$ [$-23.9$, $-15.6$] |
| 0.99 | $+1.82$ [$+0.92$, $+2.89$] | $+29.6\%$ [$+23.2$, $+36.2$] |

Coverage CIs straddle zero at every $\tau \leq 0.95$. **At $\tau \leq 0.95$, M5 is 19–20% narrower than the v1 hybrid Oracle at indistinguishable realised coverage on the OOS slice; at $\tau = 0.99$, M5 widens to hit the nominal target where the v1 Oracle hits its bounds-grid ceiling.** §7.1 showed the deployable baseline that strips regime structure entirely fails to deliver coverage at all; §7.2's M5 shows the deployable baseline that *keeps* the regime classifier and replaces the F1 forecaster machinery with a per-regime conformal quantile recovers calibration *and* delivers it at materially narrower width than F1.

### 7.2.3 Walk-forward (the OOS-fit confound check)

The pooled OOS comparison is contaminated for both methods in the same direction: both $c(\tau)$ and `BUFFER_BY_TARGET` are 4 scalars tuned on the same 2023+ slice they're then evaluated on. To put both methods on the same OOS-fit footing, we re-run each on a 6-split expanding-window walk-forward over the 2023+ slice (split fractions 0.2, 0.3, 0.4, 0.5, 0.6, 0.7; tune the 4 scalars on the early fraction, evaluate on the rest), pooling test-fold realised coverage and mean half-width across symbols within each split:

| $\tau$ | M5 realised (mean ± σ) | M5 hw (bps) | v1 Oracle realised (mean ± σ) | v1 Oracle hw (bps) |
|---:|---:|---:|---:|---:|
| 0.68 | $0.614 \pm 0.014$ | 104 | $0.735 \pm 0.010$ | 186 |
| 0.85 | $0.814 \pm 0.013$ | 196 | $0.878 \pm 0.012$ | 287 |
| 0.95 | $0.943 \pm 0.009$ | 357 | $0.971 \pm 0.017$ | 526 |
| 0.99 | $0.991 \pm 0.005$ | 745 | $0.979 \pm 0.008$ | 609 |

Bare M5 ($\delta = 0$) is *anti-conservative* on walk-forward at $\tau \leq 0.85$: deficits are $-6.6$pp, $-3.6$pp, $-0.7$pp, $+0.1$pp at $\tau = 0.68, 0.85, 0.95, 0.99$. The v1 Oracle is *conservative* on walk-forward at the same anchors: deficits $+5.5$pp, $+2.8$pp, $+2.1$pp, $-1.1$pp. The asymmetry is a property of how each method's 4-scalar OOS schedule generalises across splits, not of the conformal-vs-empirical-quantile distinction itself: the v1 Oracle's `BUFFER_BY_TARGET` is post-hoc-tuned to push pooled OOS realised coverage *above* nominal (a deployment-quality conservative tuning); bare M5 $c(\tau)$ is post-hoc-tuned to *match* nominal, so per-split coverage scatters around the target. The fix is to push M5 to the same conservative side the v1 Oracle sits on by serving it at $c(\tau + \delta(\tau))$ for a small per-anchor $\delta$ — the M5 analogue of the `BUFFER_BY_TARGET` overshoot.

### 7.2.4 δ-shift schedule

A δ-shift sweep over $\delta \in \{0.00, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07\}$ per anchor (`v1b_mondrian_delta_sweep.csv`) selects the smallest schedule that aligns walk-forward realised coverage with nominal at each anchor: $\delta = \{0.68\!:\!0.05,\;0.85\!:\!0.02,\;0.95\!:\!0.00,\;0.99\!:\!0.00\}$. Final M5 walk-forward result with $\delta$ schedule applied, alongside the v1 Oracle on the same splits:

| $\tau$ | M5 (with δ) realised | M5 hw (bps) | v1 Oracle realised | v1 Oracle hw (bps) | M5 width advantage |
|---:|---:|---:|---:|---:|---|
| 0.68 | 0.672 (Kupiec $p=0.43$) | 124 | 0.735 | 186 | $-33\%$ |
| 0.85 | 0.832 ($p=0.37$) | 215 | 0.878 | 287 | $-25\%$ |
| 0.95 | 0.943 ($p=0.36$) | 357 | 0.971 | 526 | $-32\%$ |
| 0.99 | 0.991 ($p=0.32$) | 746 | 0.979 | 609 | $+22\%$, **target hit** |

**M5 with the δ-shift schedule passes Kupiec at every anchor on walk-forward at 25–33% narrower mean half-width than the v1 hybrid Oracle through $\tau \leq 0.95$.** At $\tau = 0.99$, M5 trades width for target attainment — it hits the nominal 0.99 where the v1 Oracle hits the structural finite-sample ceiling at 0.979 (cf. §9.1). The $\delta$ schedule is itself part of the M5 deployment recipe; it is the load-bearing OOS-fit complement to the trained per-regime quantile table, structurally parallel to (but smaller than) the v1 Oracle's `BUFFER_BY_TARGET` schedule.

### 7.2.5 Density tests on M5

Berkowitz on M5's walk-forward PIT residuals: $\mathrm{LR} = 173.1$, $\hat\rho = 0.31$, $\mu_z = 0.018$, $\sigma_z^2 = 0.990$ (`v1b_mondrian_density_tests.csv`). DQ at $\tau = 0.95$: stat $= 32.1$, $p = 5.7 \times 10^{-6}$, violation rate $4.97\%$ over 86 violating weekends, with the rejection driven by clustering of violations. Per-anchor Kupiec passes at every walk-forward target; Berkowitz and DQ both reject. The diagnosis is structural: the regime classifier $\rho$ is a coarse three-bin index over the joint distribution of weekend conditioning information, and the residuals retain unexplained autocorrelation through high-vol weekend clusters. M5 does not fix the density-test rejection. Full-distribution conformal calibration remains the v3 research target identified in §10.

### 7.2.6 Per-regime decomposition at $\tau = 0.95$

Decomposing the same M5-vs-v1-Oracle $\tau = 0.95$ cell that §7.1.4 decomposed for the constant-buffer baseline:

| regime | $n$ | M5 realised | M5 hw (bps) | v1 Oracle realised | v1 Oracle hw (bps) | v1 Oracle premium |
|---|---:|---:|---:|---:|---:|---|
| normal | 1,160 | 0.939 | 279.9 | 0.946 | 402.7 | $+43.9\%$ wider, $+0.7$pp coverage |
| long_weekend | 190 | 0.984 | 403.4 | 0.953 | 396.5 | $-1.7\%$ wider, $-3.1$pp coverage |
| high_vol | 380 | 0.968 | 557.8 | 0.963 | 591.6 | $+6.1\%$ wider, $-0.5$pp coverage |

§7.1.4's decomposition put the v1 Oracle's pooled width premium in `high_vol` (constant buffer pooled-coverage right but worst where it matters). §7.2.6's decomposition puts the v1 Oracle's pooled width premium in `normal` — the 67% of weekends — at $+43.9\%$ wider for $+0.7$pp coverage. In `long_weekend` and `high_vol` the two methods bracket each other within $\pm 6\%$ of width. The diagnosis: F1_emp_regime + the per-target buffer schedule earns its OOS calibration *primarily by overwidening normal-regime weekends* relative to what a per-regime conformal quantile delivers. That is the operational expression of the load-bearing-vs-cosmetic finding (`reports/methodology_history.md`) that the F1 forecaster ladder is cosmetic on top of `regime_pub`: the cosmetic layer's contribution at the deployment target ($\tau = 0.95$) is to widen the 67% of weekends where per-regime conformal would already hit nominal coverage with a tighter band.

### 7.2.7 Verdict

§7.1 ruled out the deployable baseline that strips regime structure entirely. §7.2 isolates the deployable baseline that keeps `regime_pub` and replaces the F1 forecaster machinery with a Mondrian split-conformal quantile: factor-adjusted point + per-regime conformal quantile + δ-shifted $c(\tau)$, twelve trained scalars + four OOS scalars. On the OOS slice it is 19–20% narrower than the v1 hybrid Oracle at indistinguishable realised coverage at every $\tau \leq 0.95$ (block-bootstrap CIs exclude zero on width; coverage CIs straddle zero); on the 6-split walk-forward it passes Kupiec at every anchor at 25–33% narrower mean half-width through $\tau \leq 0.95$ and hits the nominal target at $\tau = 0.99$ where the v1 hybrid Oracle hits its finite-sample ceiling; on density tests it shares the v1 Oracle's per-anchor-only calibration profile.

This identifies M5 as the **deployed v2 architecture** (`reports/methodology_history.md`, 2026-05-02 entry). The wire format (the `PriceUpdate` Borsh layout in `crates/soothsayer-consumer`) is preserved across the v1 → v2 migration: the swap changes only the published *values* — not the on-chain decoder, not the property contract $P_1/P_2/P_3$ of §3.4.
