# §7 — Ablation Study

This section answers Q3 of §3.6: which components are load-bearing for the calibration claim? §7.1 stress-tests the deployable simpler baseline that strips regime structure entirely (a global constant buffer); §7.2 extends the Mondrian-by-regime ladder from the legacy comparator (Soothsayer-v0) through v1 (the predecessor architecture without per-symbol scale) to the deployed v2 (locally-weighted Mondrian under EWMA HL=8 σ̂); §7.3 documents the σ̂ selection procedure that promoted v2's deployed σ̂ rule, including the multiple-testing exposure and the held-out forward-tape re-validation; §7.4 decomposes where the Soothsayer-v0 premium went under v1 and how σ̂ standardisation in v2 redistributes width across symbols. Soothsayer-v0 is the legacy hybrid forecaster ladder (factor switchboard, log-log VIX standardisation, per-symbol vol index, earnings flag, long-weekend flag) wrapped in a per-(symbol, regime, claimed-quantile) calibration surface plus a 4-scalar `BUFFER_BY_TARGET` schedule, fully documented in `reports/methodology_history.md`.

All deltas carry block-bootstrap 95% CIs by weekend (1000 resamples, seed=0, paired by `(symbol, fri_ts)`). Raw tables: `reports/tables/v1b_constant_buffer_*.csv`, `reports/tables/v1b_mondrian_*.csv`, `reports/tables/m5_vs_m6_bootstrap.csv`, `reports/tables/sigma_ewma_*.csv`.

## 7.1 Constant-buffer baseline (width-at-coverage)

This is the deployable *external* baseline most likely to be used by a protocol team unwilling to absorb modelling complexity: the Pyth/Chainlink Friday close held forward, with a single global symmetric buffer $b(\tau)$ per claimed quantile. One parameter per $\tau$. No factor switchboard, no empirical residual quantile, no regime model.

$$\big[\;p_{\text{Fri}}\,(1 - b(\tau)),\;p_{\text{Fri}}\,(1 + b(\tau))\;\big],\qquad b(\tau)\;\text{calibrated globally on the training panel}.$$

### 7.1.1 Trained-buffer fit on OOS

Each $b(\tau)$ is the empirical $\tau$-quantile of $|p_{\text{Mon}} - p_{\text{Fri}}|/p_{\text{Fri}}$ on the calibration set. Carrying the trained $b(\tau)$ to the 2023+ panel:

| $\tau$ | method | realised | half-width (bps) | $p_{uc}$ | $p_{ind}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | constant buffer (train-fit) | 0.538 | 76.0 | 0.000 | 0.001 |
| 0.68 | v2 deployed | 0.693 | 130.8 | 0.264 | 0.244 |
| 0.85 | constant buffer (train-fit) | 0.731 | 140.0 | 0.000 | 0.000 |
| 0.85 | v2 deployed | 0.855 | 213.6 | 0.565 | 0.403 |
| 0.95 | constant buffer (train-fit) | 0.897 | 272.0 | 0.000 | 0.013 |
| 0.95 | v2 deployed | 0.950 | 370.6 | 0.956 | 0.603 |
| 0.99 | constant buffer (train-fit) | 0.984 | 695.0 | 0.018 | 0.927 |
| 0.99 | v2 deployed | 0.990 | 635.0 | 0.942 | $\approx 1.0$ |

The training-fit constant buffer **catastrophically undercovers** at every $\tau \leq 0.95$ (deficits $-14.2 / -12.0 / -5.4$pp, all rejecting Kupiec at $p_{uc} < 10^{-6}$) — non-stationarity: $b(\tau)$ is calibrated on a 2014–2022 window calmer than the 2023+ holdout. **The deployable constant-buffer baseline does not deliver coverage on the holdout; v2 does.** This is the *adaptivity-to-distribution-shift* contribution of the regime model + per-symbol σ̂.

### 7.1.2 Coverage-matched comparison

To answer the width-at-coverage question, we re-fit $b(\tau)$ post-hoc on the OOS slice (oracle-fit, non-deployable, but gives the constant buffer the most generous trade-off):

| $\tau$ | matched $b$ | matched-CB hw (bps) | v2 hw (bps) | $\Delta$ width (v2 − CB) |
|---:|---:|---:|---:|---|
| 0.68 | 1.21% | 120.9 | 130.8 | **+8.2% [+3.7, +13.0]** |
| 0.85 | 2.26% | 226.4 | 213.6 | **−5.7% [−10.6, −0.5]** |
| 0.95 | 3.96% | 395.6 | 370.6 | **−6.3% [−12.1, −0.4]** |
| 0.99 | 5.46% | 545.8 | 635.0 | $+16.3\%$ [$+9.6$, $+23.6$] |

**v2 is narrower than a coverage-matched (oracle-fit) constant buffer at $\tau \in \{0.85, 0.95\}$.** This is a stronger result than v1's "11–12% wider than oracle-fit CB at $\tau \le 0.95$" — the σ̂ standardisation that redistributes width across symbols (§6.4.3) reaches sufficient sharpness on the equity-heavy panel that v2 outperforms even the oracle-fit constant buffer at the headline anchor. v2 is wider only at $\tau \in \{0.68, 0.99\}$, where the cell-conditional regime structure carries genuine information. The regime model + σ̂ buy *both* coverage on a non-stationary distribution *and* mean-width sharpness at $\tau \in \{0.85, 0.95\}$ against the strongest non-modeled comparator.

### 7.1.3 Per-regime decomposition

The pooled half-width at $\tau = 0.95$ hides a regime-conditional structure. v2 pooled: $370.6$ bps; per-regime $300.1 / 334.7 / 603.7$ bps (normal / long_weekend / high_vol). The matched-CB at $\tau = 0.95$ delivers $395.6$ bps in *every* regime by construction (one global multiplier). The regime model concentrates width in `high_vol` ($+52\%$ vs CB at $603.7$ vs $395.6$) where it earns $-1.1$pp coverage; releases width in `normal` ($-24\%$ vs CB at $300.1$ vs $395.6$) without losing coverage. The constant buffer's pooled coverage is "average right but worst where it matters most": violations concentrate in high-vol weekends — exactly where a downstream lending protocol incurs the largest mark-to-market gap. The regime model's contribution is **(i) calibration through distribution shift** and **(ii) tail-protection in `high_vol` weekends** at sharper *normal*-regime widths than the constant buffer.

## 7.2 Mondrian-by-regime ladder — through v1 to v2

§7.1 ruled out a deployable baseline stripping regime structure. The natural follow-up: which architectural ingredients of v1 → v2 are load-bearing? The answer separates into (a) the v1 contribution (the per-regime conformal quantile + OOS-fit $c(\tau)$ replacing Soothsayer-v0's hybrid ladder), and (b) the v2 contribution (per-symbol σ̂ standardisation closing v1's bimodal per-symbol failure).

### 7.2.1 The ladder

Each variant fits a per-regime conformal quantile and serves a band; the rungs add components left-to-right:

- **M1.** Stale point + per-regime quantile (no factor adjustment).
- **M2.** Factor-adjusted point + per-regime quantile.
- **M3.** Factor-adjusted point + per-(symbol, regime) quantile (cells too thin; fails Christoffersen).
- **M4.** M2 with quantile re-fit *post-hoc on OOS itself* (oracle-fit, non-deployable).
- **v1.** M2 + per-target multiplicative bump $c(\tau)$ tuned on OOS + walk-forward $\delta(\tau)$ shift schedule. **The Mondrian-without-σ̂ deployment.** Twelve trained scalars + 4 OOS-fit + 4 walk-forward-fit = 20 deployment scalars.
- **v2-K26.** v1 + per-symbol pre-Friday σ̂ on a 26-weekend trailing window (the LWC architecture before σ̂ promotion).
- **v2.** v2-K26 with σ̂ rule swapped to EWMA HL=8 (the §7.3 selection-validated variant). **The deployed architecture.** Twelve trained scalars + 4 OOS-fit $c(\tau)$ + 0 walk-forward (collapses) = 16 deployment scalars.

The σ̂ rule for v2 is itself a soft constant (half-life 8 weekends, ≥8-past-obs warm-up); it is not an additional fit-against-OOS scalar.

### 7.2.2 OOS pooled results

| $\tau$ | method | realised | hw (bps) | $p_{uc}$ | $p_{ind}$ | per-symbol Kupiec pass |
|---:|---|---:|---:|---:|---:|---:|
| 0.68 | Soothsayer-v0 | 0.680 | 136.1 | 0.984 | 0.645 | — |
| 0.68 | M2 fa + regime-CP | 0.547 | 73.5 | 0.000 | 0.776 | — |
| 0.68 | v1 deployed | 0.735 | 137.5 | 0.000 | 0.339 | (v1 fails 8/10) |
| 0.68 | v2-K26 | 0.687 | 132.6 | 0.515 | 0.102 | — |
| 0.68 | v2 deployed | 0.693 | 130.8 | 0.264 | 0.244 | 10/10 |
| 0.85 | Soothsayer-v0 | 0.856 | 251.4 | 0.477 | 0.182 | — |
| 0.85 | v1 deployed | 0.887 | 235.1 | 0.000 | 0.424 | — |
| 0.85 | v2 deployed | 0.855 | 213.6 | 0.565 | 0.403 | — |
| **0.95** | Soothsayer-v0 | 0.950 | 443.5 | 0.956 | 0.483 | — |
| **0.95** | M2 | 0.910 | 272.7 | $8.2{\times}10^{-12}$ | 0.396 | — |
| **0.95** | **v1 deployed** | **0.950** | **354.6** | **0.956** | **0.921** | **2/10** |
| **0.95** | **v2-K26** | **0.950** | **385.3** | **0.956** | **0.275** | **10/10** |
| **0.95** | **v2 deployed** | **0.950** | **370.6** | **0.956** | **0.603** | **10/10** |
| 0.99 | Soothsayer-v0 | 0.972 | 522.8 | 0.000 | 0.897 | — |
| 0.99 | v1 deployed | 0.990 | 677.7 | 0.942 | 0.344 | — |
| 0.99 | v2 deployed | 0.990 | 635.0 | 0.942 | $\approx 1.0$ | — |

**The two structural moves are visible.** v1 over Soothsayer-v0: **20% narrower** at $\tau = 0.95$ (354.6 vs 443.5 bps; CI $-23.9\%$ to $-15.6\%$) at indistinguishable pooled coverage, and closes Soothsayer-v0's tail ceiling at $\tau = 0.99$. v2 over v1: **per-symbol Kupiec pass-rate 2/10 → 10/10** at indistinguishable pooled coverage, with a $+4.5\%$ pooled half-width tax (CI on Δhw at $\tau = 0.95$ from `m5_vs_m6_bootstrap.csv` is $[+12.3, +49.0]$ bps for v1→v2-K26; the v1→v2 EWMA HL=8 delta is the v1→v2-K26 delta minus the K=26→EWMA HL=8 narrowing of $-14.8$ bps, giving v1→v2 ≈ $+16$ bps or $+4.5\%$). The Christoffersen $p$ at $\tau = 0.95$ on the 2023 split passes for all three (v1: 0.921; v2-K26: 0.275; v2: 0.603) — but the K=26 baseline of v2 introduced split-date Christoffersen rejections at the 2021/2022 split anchors that v1 didn't have, motivating the §7.3 σ̂ selection. **§7.4 documents how the σ̂ standardisation redistributes the per-symbol width that v1 was leaving on the table.**

### 7.2.3 Walk-forward δ-shift schedule — collapses under v2

Under v1, a plain $c(\tau)$ fit to the pooled OOS slice produced per-split realised coverage that scattered around nominal — passed Kupiec on the pooled fit by construction, but undercovered in roughly half the splits. v1 added a four-scalar walk-forward $\delta(\tau) = \{0.05,\, 0.02,\, 0.00,\, 0.00\}$ to push every split above nominal. Under v2 the same walk-forward sweep over $\delta \in \{0.00, \dots, 0.07\}$ selects $\delta(\tau) \equiv 0$ — per-symbol scale standardisation tightens cross-split realised-coverage variance enough that the structural-conservatism shim is no longer load-bearing. v1 vs v2 at the deployed (post-walk-forward) schedule:

| $\tau$ | v1 deployed (with δ) | v2 deployed (δ=0) | v2 advantage |
|---:|---|---|---|
| 0.68 | $0.735$ / $137.5$ bps / $p=0.000$ | $0.693$ / $130.8$ bps / $p=0.264$ | Kupiec passes; +6% narrower |
| 0.85 | $0.887$ / $235.1$ bps / $p=0.000$ | $0.855$ / $213.6$ bps / $p=0.565$ | Kupiec passes; $-9\%$ narrower |
| 0.95 | $0.950$ / $354.6$ bps / $p=0.956$ | $0.950$ / $370.6$ bps / $p=0.956$ | $+4.5\%$ wider, per-symbol Kupiec 2/10→10/10 |
| 0.99 | $0.990$ / $677.7$ bps / $p=0.942$ | $0.990$ / $635.0$ bps / $p=0.942$ | $-6\%$ narrower |

At three of four anchors v2 is *narrower* than v1 with a stricter per-symbol calibration constraint. At $\tau = 0.95$ — the headline anchor — v2 is $+4.5\%$ wider and trades that for the per-symbol fix. The v1 over-conservatism at $\tau \in \{0.68, 0.85\}$ (Kupiec rejecting because $\delta$-shift pushed coverage above nominal) is what σ̂ standardisation removes.

### 7.2.4 The per-symbol-bimodality fix (v1 → v2)

The ablation isolates σ̂ standardisation as the load-bearing component for per-symbol calibration. Side-by-side at $\tau = 0.95$ (full table at §6.4.1):

| metric | v1 | v2 |
|---|---:|---:|
| pooled realised | 0.9503 | 0.9503 |
| pooled half-width (bps) | 354.6 | 370.6 |
| per-symbol Kupiec pass-rate | 2 / 10 | **10 / 10** |
| per-symbol Berkowitz LR range | 0.9 – 224 (250×) | **3.2 – 16.7 (5.3×)** |
| LOSO realised std at $\tau = 0.95$ | 0.0759 | **0.0134 (5.7× tighter)** |
| LOSO Kupiec pass-rate (held-out) | 8 / 10 | **10 / 10** |

The v2 architectural change isolates exactly: same point estimator, same regime classifier, same Mondrian split-conformal, same finite-sample CP rank formula, same training set, same OOS slice. Only the σ̂ standardisation of the conformity score is added. The per-symbol Kupiec pass-rate, Berkowitz LR range, and LOSO calibration std all improve simultaneously by mechanism — no other component of v1 is touched. The $+4.5\%$ pooled width tax is the price for the per-symbol calibration; the §6.Y simulation evidence on synthetic data with known DGP confirms this is the correct architectural trade.

## 7.3 σ̂ selection procedure and multiple-testing disclosure

The per-symbol scale rule $\hat\sigma_s(t)$ is the only deployment constant of v2 that does not have a closed-form derivation from its specification. v1 and v2-K26 use a 26-weekend trailing window; v2 deployed swaps to EWMA HL=8. This section documents the selection procedure, its multiple-testing exposure, and the held-out forward-tape re-validation that backs the deployment decision.

### 7.3.1 Pre-registered three-gate criterion

Before running the σ̂ comparison we registered three gates the deployed σ̂ rule must satisfy:

1. **Gate 1 — split-date Christoffersen.** No (split × $\tau$) cell rejecting at uncorrected $\alpha = 0.05$ across the four split anchors {2021, 2022, 2023, 2024} × four $\tau$ anchors. Motivation: the K=26 baseline introduced 2021/2022 split-date Christoffersen rejections at $\tau = 0.95$ that v1 did not have; we want a σ̂ rule that closes those without re-introducing them elsewhere.
2. **Gate 2 — per-symbol Kupiec.** Pass-rate 10/10 at $\tau = 0.95$. Motivation: the v2 architecture exists to fix the v1 per-symbol bimodality; any σ̂ rule that loses this property is rejected.
3. **Gate 3 — bootstrap CI on pooled half-width.** The 95% bootstrap CI upper bound on $\Delta$hw% (vs the K=26 baseline) must lie within $+5\%$ at every $\tau$. Motivation: any σ̂ rule that materially widens the deployed band relative to baseline must be justified on calibration grounds; we cap the calibration-for-width trade at $+5\%$ a priori.

Gate 3 has no multiple-testing exposure: a single bootstrap CI per $\tau$ (no per-cell tests), the threshold is pre-registered. Gates 1 and 2 are per-cell tests that — at uncorrected $\alpha$ — accumulate multi-test risk. Gate 1 is the most exposed (16 cells per variant × 5 variants = 80 cells); we report that exposure and apply Benjamini-Hochberg correction below.

### 7.3.2 The five-variant ladder

Five σ̂ rules were considered:

- **K=26 baseline.** Trailing 26-weekend window, equal-weight (the LWC v2-K26 from §7.2).
- **EWMA HL=6.** Exponentially-weighted moving average of past relative residuals, weekend half-life 6.
- **EWMA HL=8.** Same, half-life 8.
- **EWMA HL=12.** Same, half-life 12.
- **Convex blend.** $0.5 \cdot$ K=26 $+\, 0.5 \cdot$ EWMA HL=8.

All five share the ≥8-past-observation warm-up rule and the strict pre-Friday convention; all five build $\hat\sigma_s$ over the same evaluable panel ($n = 5,916$). Per-variant artefacts (regime quantile table + $c(\tau)$ + $\delta(\tau)$ schedules) were re-fit at the same training cutoff (2023-01-01); δ collapsed to zero across all five variants. Outputs in `reports/tables/sigma_ewma_*.csv`.

### 7.3.3 Gate 1 — split-date Christoffersen across all 80 cells

Per-cell Christoffersen $p$-values across the 5 variants × 4 split anchors × 4 $\tau$ = 80-cell grid (`reports/tables/sigma_ewma_split_sensitivity.csv`). Counting cells with $p < 0.05$ (uncorrected):

| variant | cells rejecting at uncorrected α=0.05 | rejecting (split, τ) cells |
|---|---:|---|
| K=26 baseline | **4** | (2021, 0.68); (2021, 0.85); (2021, 0.95); (2022, 0.95) |
| EWMA HL=6 | **3** | (2021, 0.68); (2023, 0.68); (2024, 0.68) |
| **EWMA HL=8** | **0** | **none** |
| EWMA HL=12 | 1 | (2021, 0.85) |
| Convex blend | 1 | (2021, 0.68) |

EWMA HL=8 is the only variant with zero per-cell rejections at uncorrected $\alpha = 0.05$ across the 16-cell grid for that variant. **At face value, Gate 1 selects EWMA HL=8 uniquely.**

**Multiple-testing correction.** The Gate-1 ranking above is multi-test exposed. We apply Benjamini-Hochberg correction at FDR $= 0.05$ across the full 80-cell grid (5 variants × 16 cells each); output `reports/tables/sigma_ewma_split_sensitivity_bh_corrected.csv`. **Under BH correction, no variant has any rejected cell.** The two K=26 cells that drove the uncorrected count at $\tau = 0.95$ — 2022 split ($p = 0.0016$) and 2021 split ($p = 0.0065$) — carry BH-adjusted $q$-values of $0.130$ and $0.259$ respectively, both well above the $0.05$ threshold; $0.130$ is the smallest $q$ in the entire 80-cell grid. The honest reading: per-cell Christoffersen evidence after multi-test correction does not statistically distinguish the five σ̂ variants. **The deployment decision cannot rest on Gate 1 alone**, even though EWMA HL=8 is the only variant clearing the gate at uncorrected $\alpha = 0.05$.

**Qualitative pattern across the $\tau = 0.95$ column** (supporting context, not statistical evidence). Even though BH correction wipes out the formal rejections, the uncorrected $p$-values across the four split anchors at $\tau = 0.95$ are systematically lower for K=26 than for any EWMA variant:

| variant | $p_{\text{Christ}}(\tau=0.95)$ across {2021, 2022, 2023, 2024} splits |
|---|---|
| K=26 baseline | $\{0.006,\ 0.002,\ 0.274,\ 0.525\}$ — two visible problem cells |
| EWMA HL=6 | $\{0.210,\ 0.321,\ 0.675,\ 0.784\}$ |
| **EWMA HL=8** | $\{0.115,\ 0.186,\ 0.603,\ 0.671\}$ — strictly higher than K=26 at every anchor |
| EWMA HL=12 | $\{0.318,\ 0.529,\ 0.680,\ 0.586\}$ |
| Convex blend (50/50) | $\{0.094,\ 0.162,\ 0.724,\ 0.791\}$ |

EWMA HL=8 produces uncorrected $p$-values that are higher than the K=26 baseline at every one of the four split anchors at $\tau = 0.95$ ($0.115$ vs $0.006$; $0.186$ vs $0.002$; $0.603$ vs $0.274$; $0.671$ vs $0.525$); the column-wise minimum rises from $0.002$ under K=26 to $0.115$ under HL=8. We treat this consistent column-wise lift as *qualitative supporting context* — it is the pattern in the raw $p$-values that originally motivated the σ̂ work — but we do not claim it as statistical evidence: under BH correction, none of these per-cell differences are formally significant. The statistical weight for the deployment decision is carried by Gate 3 (§7.3.5), which is a single-quantity bootstrap CI with no multi-test exposure.

### 7.3.4 Gate 2 — per-symbol Kupiec at $\tau = 0.95$

Per-symbol Kupiec at $\tau = 0.95$ on the 2023+ OOS slice across the 5 σ̂ variants × 10 symbols (`reports/tables/sigma_ewma_per_symbol.csv`):

| variant | per-symbol Kupiec pass-rate at $\tau = 0.95$ |
|---|---:|
| K=26 baseline | 10 / 10 |
| EWMA HL=6 | 10 / 10 |
| **EWMA HL=8** | **10 / 10** |
| EWMA HL=12 | 10 / 10 |
| Convex blend | 10 / 10 |

All five variants pass Gate 2. Per-symbol calibration is a property of the architecture (per-symbol σ̂ standardisation), not the σ̂ rule — once σ̂ is per-symbol and pre-Friday, the rule's half-life affects pooled width and split-date temporal independence but not per-symbol Kupiec at $\tau = 0.95$ on this panel. **Gate 2 does not discriminate among the variants.**

### 7.3.5 Gate 3 — bootstrap CI on pooled half-width

Per-variant Δhw% versus the K=26 baseline at each $\tau$, with 95% block-bootstrap CIs (1000 weekend-block resamples, seed=0; `reports/tables/sigma_ewma_bootstrap.csv`). The deployed σ̂ rule must have a 95% CI upper on Δhw% within +5% at every $\tau$:

| $\tau$ | EWMA HL=8 Δhw% (vs K=26) | 95% CI on Δhw% | within +5% gate? |
|---:|---:|---:|:---:|
| 0.68 | $-1.34\%$ | $[-3.02,\ +0.25]$ | ✓ |
| 0.85 | $-2.07\%$ | $[-3.75,\ -0.45]$ | ✓ (also significantly narrower) |
| 0.95 | $-3.83\%$ | $[-6.15,\ -1.88]$ | ✓ (also significantly narrower) |
| 0.99 | $-7.41\%$ | $[-9.33,\ -5.65]$ | ✓ (also significantly narrower) |

EWMA HL=8 satisfies Gate 3 with the upper-bound CI at $+0.25\%$ across all $\tau$ — well inside the $+5\%$ pre-registered cap. EWMA HL=8 is *narrower* than the K=26 baseline at every $\tau$ in the bootstrap point estimate; the 95% CI excludes zero on the narrow side (i.e. **statistically significantly narrower**) at $\tau \in \{0.85, 0.95, 0.99\}$, and is neutral at $\tau = 0.68$ (CI straddles zero). At no $\tau$ is EWMA HL=8 statistically significantly *wider* than baseline — the comparison is one-sided. Realised-coverage deltas at $\tau \in \{0.95, 0.99\}$ are exactly zero by construction (per-symbol Kupiec is preserved and the pooled count is unchanged on this finite panel); at $\tau \in \{0.68, 0.85\}$ the paired Δ-realised CIs straddle zero. Calibration is preserved at the deployed anchors; sharpness improves. Gate 3 is the load-bearing gate for the deployment decision: it has no multi-test exposure (one CI per $\tau$, threshold pre-registered), and EWMA HL=8 is the variant that delivers the largest narrowing relative to baseline while satisfying the gate.

### 7.3.6 Held-out forward-tape variant comparison

To re-validate the σ̂ selection on data not used in any of the three gates, the forward-tape harness (§6.7) carries a sibling variant-comparison runner (`scripts/run_forward_tape_variant_comparison.py`). The runner loads a content-addressed *variant bundle* (`data/processed/lwc_variant_bundle_v1_frozen_20260504.json`, SHA-256 `7cef6132d970…`) with $(q_r^{\text{LWC}},\,c(\tau),\,\delta(\tau))$ schedules for all five variants at the same 2023-01-01 training cutoff, and applies each variant's frozen schedules to the forward-tape rows. The comparison **never re-selects** among variants — its function is to flag if a different σ̂ rule looks dramatically cleaner on the held-out slice; if so, that's a finding that motivates a re-fit with disclosure, not an automatic re-deploy. Output: `reports/m6_forward_tape_{N}weekends_variants.{md,csv}`.

**Status at submission:** $N = $ [N TBD; the forward-tape variant-comparison report is the load-bearing held-out re-validation evidence and **must be regenerated immediately before submission**, alongside §6.7]. With $N \geq 4$ the variant-comparison report is interpretable; with $N \geq 13$ it has moderate power to detect a meaningful per-variant gap on forward data.

### 7.3.7 Honest framing of the σ̂ deployment claim

The selection procedure is what it is: a 5-variant ladder × 16-cell grid × 3 gates, with the three gates pre-registered and the multiple-testing exposure of Gate 1 disclosed and corrected. Under BH at FDR=0.05, Gate 1 alone does not statistically distinguish the five variants — the formal selection signal that Gate 1 carried at uncorrected $\alpha$ is washed out by the multi-test correction, exactly as one would expect with 80 tests against a correct null. Gates 2 and 3 — both unambiguously satisfied by EWMA HL=8 — are the deployment-load-bearing tests. The forward-tape variant-comparison harness (§7.3.6) is the held-out re-validation.

**We claim that EWMA HL=8 satisfies the pre-registered three-gate criterion under uncorrected per-cell $\alpha = 0.05$; that under BH multi-test correction the per-cell Christoffersen evidence does not statistically distinguish the five variants; that the qualitative pattern in the uncorrected $\tau = 0.95$ column ($p$-values strictly higher under HL=8 than baseline at every split anchor) is consistent with the deployment choice but is supporting context, not statistical evidence; and that the deployment decision rests on Gate 3 (the bootstrap CI on width, no multi-test issue, statistically significantly narrower at $\tau \in \{0.85, 0.95, 0.99\}$ with calibration preserved) plus the held-out forward-tape re-validation. We do not claim the σ̂ rule is optimal among all locally-weighted variants** (§3.5 non-goal). A future paper may sweep finer half-life grids, alternative weight kernels, or hybrid rules; that work is gated on accumulating forward-tape evidence to re-validate any new selection on truly held-out data.

## 7.4 Where the Soothsayer-v0 premium goes — and how σ̂ standardisation redistributes it

§7.1.3 attributed the constant-buffer premium to `high_vol`; §7.2 attributed the v1-over-Soothsayer-v0 narrowing to the per-regime conformal lookup replacing Soothsayer-v0's hybrid forecaster ladder; §7.4 attributes the v1→v2 width redistribution to per-symbol σ̂.

**v1 vs Soothsayer-v0 per-regime decomposition at $\tau = 0.95$.** Soothsayer-v0 earns its OOS calibration **primarily by overwidening normal-regime weekends** (the 67% of the panel) at $+43.9\%$ wider for $+0.7$pp coverage (table at `reports/tables/v1b_oracle_v_prior.csv`) — the Soothsayer-v0 forecaster ladder is cosmetic on top of `regime_pub`.

**v1 vs v2 per-class decomposition at $\tau = 0.95$.** Where v1 paid its $+4.5\%$ pooled width tax over Soothsayer-v0, v2 redistributes that width *across symbols within a regime* via σ̂:

| class | $n$ | v1 hw at $\tau=0.95$ | v2 hw at $\tau=0.95$ | Δ |
|---|---:|---:|---:|---|
| equities (8 symbols) | 1,384 | 355 bps | 436 bps | **+23%** (carries the per-symbol heavy-tail fix) |
| GLD + TLT (2 symbols) | 346 | 355 bps | 184 bps | **−48%** (releases over-conservative defensive bands) |

Under v1, every symbol within a regime received the same $c(\tau) \cdot q_r(\tau) \cdot p_{\text{Fri}}$ width — the "common multiplier on heterogeneous tails" failure of §6.4.1. Under v2, the σ̂ multiplier is per-symbol, so heavy-tail equities (HOOD, MSTR, TSLA) receive bands that match their relative residual scale, and the over-covered defensive class (GLD, TLT) receives narrower bands without losing coverage. **The v1 → v2 transition is a width-redistribution at neutral pooled coverage**, not a free-lunch claim and not a mean-width improvement on the panel-aggregate scale.

The wire format (`PriceUpdate` Borsh) is preserved across the migration v1 → v2: the swap reserves a new `forecaster_code` (v1: 2 = Mondrian; v2: 3 = LWC) but the decoder, the field schema, and the §3.4 property contract are unchanged. v2 is the deployable architecture this paper validates; the §10 candidate architectures (cross-sectional common-mode partial-out, full-distribution conformal, sub-regime granularity) target the residual rejections (§6.3.1 cross-sectional within-weekend correlation; §9.4 per-symbol Berkowitz on TSLA/TLT) that σ̂ standardisation does not reach.
