# §7 — Ablation Study

This section answers Q3 of §3.6: which components are load-bearing for the calibration claim? The deployed architecture has three load-bearing components, isolated below by descriptive comparator rather than by code tag:

- **§7.1 — Regime stratification.** A symmetric global buffer applied to a held-forward Friday close (the *constant-buffer baseline* — the deployable comparator most likely to be reached for by a protocol team unwilling to absorb modelling complexity) under-covers materially on the 2023+ holdout. Per-regime conformal stratification supplies adaptivity to distribution shift and tail-protection in `high_vol` weekends.
- **§7.2 — Per-symbol σ̂ standardisation.** An *unweighted Mondrian comparator* — the same per-regime conformal architecture without per-symbol scale standardisation — pools to nominal coverage but exhibits a per-symbol bimodality that fails Kupiec on 8 of 10 symbols at $\tau = 0.95$. Standardising the conformity score by a per-symbol pre-Friday $\hat\sigma_s(t)$, with no other architectural change, takes per-symbol Kupiec from 2/10 to 10/10.
- **§7.3 — Near-identity OOS $c(\tau)$ bump.** A 4-scalar multiplicative correction $c(\tau)$ closes any residual train-OOS distribution-shift gap. Three of the four scalars are essentially identity ($c \in \{1.000, 1.000, 1.003\}$ at $\tau \in \{0.68, 0.85, 0.99\}$); only $c(0.95) = 1.079$ carries meaningful OOS information.

§7.4 documents the σ̂ selection procedure (multi-test correction and the held-out forward-tape re-validation harness), and §7.5 decomposes how σ̂ standardisation redistributes width across symbols.

All deltas carry block-bootstrap 95% CIs by weekend (1000 resamples, seed=0, paired by `(symbol, fri_ts)`). Raw tables: `reports/tables/v1b_constant_buffer_*.csv`, `reports/tables/v1b_mondrian_*.csv`, `reports/tables/m5_vs_m6_bootstrap.csv`, `reports/tables/sigma_ewma_*.csv`.

## 7.1 Regime stratification — vs constant-buffer baseline

The *constant-buffer baseline* is the deployable external comparator most likely to be used by a protocol team unwilling to absorb modelling complexity: the Pyth/Chainlink Friday close held forward, with a single global symmetric buffer $b(\tau)$ per claimed quantile. One parameter per $\tau$. No factor switchboard, no empirical residual quantile, no regime model.

$$\big[\;p_{\text{Fri}}\,(1 - b(\tau)),\;p_{\text{Fri}}\,(1 + b(\tau))\;\big],\qquad b(\tau)\;\text{calibrated globally on the training panel}.$$

### 7.1.1 Trained-buffer fit on OOS

Each $b(\tau)$ is the empirical $\tau$-quantile of $|p_{\text{Mon}} - p_{\text{Fri}}|/p_{\text{Fri}}$ on the calibration set. Carrying the trained $b(\tau)$ to the 2023+ panel:

| $\tau$ | method | realised | half-width (bps) | $p_{uc}$ | $p_{ind}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | constant buffer (train-fit) | 0.538 | 76.0 | 0.000 | 0.001 |
| 0.68 | deployed | 0.693 | 130.8 | 0.264 | 0.244 |
| 0.85 | constant buffer (train-fit) | 0.731 | 140.0 | 0.000 | 0.000 |
| 0.85 | deployed | 0.855 | 213.6 | 0.565 | 0.403 |
| 0.95 | constant buffer (train-fit) | 0.897 | 272.0 | 0.000 | 0.013 |
| 0.95 | deployed | 0.950 | 370.6 | 0.956 | 0.603 |
| 0.99 | constant buffer (train-fit) | 0.984 | 695.0 | 0.018 | 0.927 |
| 0.99 | deployed | 0.990 | 635.0 | 0.942 | $\approx 1.0$ |

The training-fit constant buffer **catastrophically undercovers** at every $\tau \leq 0.95$ (deficits $-14.2 / -12.0 / -5.4$pp, all rejecting Kupiec at $p_{uc} < 10^{-6}$) — non-stationarity: $b(\tau)$ is calibrated on a 2014–2022 window calmer than the 2023+ holdout. The deployable constant-buffer baseline does not deliver coverage on the holdout; the regime-stratified architecture does. This is the *adaptivity-to-distribution-shift* contribution of the regime model + per-symbol σ̂.

### 7.1.2 Coverage-matched comparison

To answer the width-at-coverage question, we re-fit $b(\tau)$ post-hoc on the OOS slice (oracle-fit, non-deployable, but gives the constant buffer the most generous trade-off):

| $\tau$ | matched $b$ | matched-CB hw (bps) | deployed hw (bps) | $\Delta$ width (deployed − CB) |
|---:|---:|---:|---:|---|
| 0.68 | 1.21% | 120.9 | 130.8 | **+8.2% [+3.7, +13.0]** |
| 0.85 | 2.26% | 226.4 | 213.6 | **−5.7% [−10.6, −0.5]** |
| 0.95 | 3.96% | 395.6 | 370.6 | **−6.3% [−12.1, −0.4]** |
| 0.99 | 5.46% | 545.8 | 635.0 | $+16.3\%$ [$+9.6$, $+23.6$] |

The deployed architecture is narrower than a coverage-matched (oracle-fit) constant buffer at $\tau \in \{0.85, 0.95\}$. The σ̂ standardisation that redistributes width across symbols (§6.4.4) reaches sufficient sharpness on the equity-heavy panel that the deployment outperforms even the oracle-fit constant buffer at the headline anchor; the architecture is wider only at $\tau \in \{0.68, 0.99\}$, where the cell-conditional regime structure carries genuine information. The regime model + σ̂ buy *both* coverage on a non-stationary distribution *and* mean-width sharpness at $\tau \in \{0.85, 0.95\}$ against the strongest non-modelled comparator.

### 7.1.3 Per-regime decomposition

The pooled half-width at $\tau = 0.95$ hides a regime-conditional structure. Deployed pooled: $370.6$ bps; per-regime $300.1 / 334.7 / 603.7$ bps (normal / long_weekend / high_vol). The matched-CB at $\tau = 0.95$ delivers $395.6$ bps in *every* regime by construction (one global multiplier). The regime model concentrates width in `high_vol` ($+52\%$ vs CB at $603.7$ vs $395.6$) where it earns $-1.1$pp coverage; releases width in `normal` ($-24\%$ vs CB at $300.1$ vs $395.6$) without losing coverage. The constant buffer's pooled coverage is "average right but worst where it matters most": violations concentrate in high-vol weekends — exactly where a downstream lending protocol incurs the largest mark-to-market gap. The regime model's contribution is **(i) calibration through distribution shift** and **(ii) tail-protection in `high_vol` weekends** at sharper *normal*-regime widths than the constant buffer.

## 7.2 Per-symbol σ̂ standardisation — vs unweighted Mondrian

The *unweighted Mondrian comparator* shares the regime structure of §7.1 but omits the per-symbol scale standardisation: a single per-(regime, $\tau$) conformal quantile is fit on the *un-standardised* relative residual $|P_{\text{Mon}} - \hat P_{\text{Mon}}| / P_{\text{Fri}}$, and the served band uses that quantile directly as a fraction of $P_{\text{Fri}}$. Same training set, same OOS slice, same point estimator, same regime classifier, same finite-sample CP rank formula. Only the σ̂ standardisation of the conformity score is added by the deployed architecture.

### 7.2.1 OOS pooled results

| $\tau$ | method | realised | hw (bps) | $p_{uc}$ | $p_{ind}$ | per-symbol Kupiec pass |
|---:|---|---:|---:|---:|---:|---:|
| 0.68 | unweighted Mondrian | 0.735 | 137.5 | 0.000 | 0.339 | (1/10) |
| 0.68 | deployed | 0.693 | 130.8 | 0.264 | 0.244 | 10/10 |
| 0.85 | unweighted Mondrian | 0.887 | 235.1 | 0.000 | 0.424 | (1/10) |
| 0.85 | deployed | 0.855 | 213.6 | 0.565 | 0.403 | 10/10 |
| **0.95** | **unweighted Mondrian** | **0.950** | **354.6** | **0.956** | **0.921** | **2/10** |
| **0.95** | **deployed** | **0.950** | **370.6** | **0.956** | **0.603** | **10/10** |
| 0.99 | unweighted Mondrian | 0.990 | 677.7 | 0.942 | 0.344 | (8/10) |
| 0.99 | deployed | 0.990 | 635.0 | 0.942 | $\approx 1.0$ | 10/10 |

Both methods pool to nominal at $\tau = 0.95$ (both $0.950$, both Kupiec $p = 0.956$). The split is on per-symbol calibration: the unweighted Mondrian comparator passes 2 of 10 per-symbol Kupiec cells at $\tau = 0.95$; the deployed architecture passes 10 of 10. The unweighted comparator pools to nominal *through compensating per-symbol biases* — heavy-tail tickers under-cover, low-vol tickers over-cover, and the cross-sectional average lands at $\tau$ by accident. The σ̂ standardisation factors out the per-symbol scale before the conformal fit, so the regime quantile carries only the *shape* of the standardised residual distribution and per-symbol calibration is recovered by the per-symbol $\hat\sigma_s(t)$ at serve time.

The pooled half-width tax at $\tau = 0.95$ is **$+4.5\%$** (370.6 vs 354.6 bps; $+15.93$ bps with 95% block-bootstrap CI $[+1.05,\,+30.73]$ from `m5_vs_m6_bootstrap.csv`). The per-symbol calibration is bought at exactly that price; §7.5 documents how the +4.5% pooled figure resolves into a +17.8% widening on heavy-tail equities and a −48.8% narrowing on the defensive class.

### 7.2.2 Side-by-side at $\tau = 0.95$

The σ̂-standardisation isolation: same point estimator, same regime classifier, same Mondrian split-conformal, same finite-sample CP rank formula, same training set, same OOS slice. Only the σ̂ standardisation of the conformity score is added.

| metric | unweighted Mondrian | deployed (σ̂-standardised) |
|---|---:|---:|
| pooled realised | 0.9503 | 0.9503 |
| pooled half-width (bps) | 354.6 | 370.6 |
| per-symbol Kupiec pass-rate | 2 / 10 | **10 / 10** |
| per-symbol Berkowitz LR range | 0.9 – 224 (250×) | **3.2 – 16.7 (5.2×)** |
| LOSO realised std at $\tau = 0.95$ | 0.0759 | **0.0128 (5.9× tighter)** |
| LOSO Kupiec pass-rate (held-out) | 8 / 10 | **10 / 10** |

The per-symbol Kupiec pass-rate, Berkowitz LR range, and LOSO calibration std all improve simultaneously by mechanism — no other component of the architecture is touched. The §6.8 simulation evidence on synthetic data with known DGP confirms this is the correct architectural trade — under four DGPs spanning homoskedastic, regime-switching, drift, and structural-break specifications, the unweighted Mondrian comparator's per-symbol Kupiec pass-rate at $\tau = 0.95$ collapses to $29$–$31\%$ while σ̂ standardisation closes the bimodality on every DGP at $98.6$–$99.9\%$.

### 7.2.3 Walk-forward $\delta$-shift schedule — collapses

Under an unweighted Mondrian fit, a plain $c(\tau)$ correction to the pooled OOS slice produces per-split realised coverage that scatters around nominal — passes Kupiec on the pooled fit by construction, but undercovers in roughly half the splits, motivating the addition of a per-anchor structural-conservatism shift $\delta(\tau)$. Under the σ̂-standardised architecture the same walk-forward sweep over $\delta \in \{0.00, \dots, 0.07\}$ on the four powered tune fractions $f \in \{0.40, 0.50, 0.60, 0.70\}$ selects $\delta(\tau) \equiv 0$: per-symbol scale standardisation tightens cross-split realised-coverage variance enough that the structural-conservatism shim is no longer load-bearing. The schedule is retained as a four-zero-vector in the artefact JSON for shape-compatibility with the receipt schema, but the deployment carries zero walk-forward-tuned scalars.

## 7.3 Near-identity OOS $c(\tau)$ bump

The deployed $c(\tau)$ schedule is

$$c(\tau) = \{0.68\!:\!1.000,\;0.85\!:\!1.000,\;0.95\!:\!1.079,\;0.99\!:\!1.003\}.$$

This is a 4-scalar multiplicative correction fit on the 2023+ OOS slice as the smallest $c \in [1, 5]$ such that pooled realised coverage with effective quantile $c \cdot q_r(\tau)$ matches $\tau$. Three of the four are essentially identity: under the deployed σ̂ rule and the 2023-01-01 split, the trained per-regime quantile already lands within 0.3 pp of nominal at $\tau \in \{0.68, 0.85, 0.99\}$, so $c(\tau)$ at those anchors collapses to $\{1.000, 1.000, 1.003\}$. Only $\tau = 0.95$ has a meaningful train-OOS distribution-shift gap; the 7.9% widening at that anchor is what closes the pooled $0.946 \to 0.950$ correction.

The architectural significance is that $c(\tau)$ carries one scalar of meaningful OOS information (3 of 16 deployment scalars under the disclosure of §9.3) — not four. A reviewer-relevant alternative is to drop the $c(\tau)$ correction entirely and serve at the trained-quantile coverage; on this slice that costs ~0.4 pp at $\tau = 0.95$ (0.946 vs the deployment-tuned 0.950) and is statistically indistinguishable from nominal under Kupiec. The deployment opts to close the residual gap because the published receipt names a specific $\tau$ and a 0.4 pp deficit on a held-out slice would translate into a small but persistent under-coverage in the served claim. The provenance trade — one scalar of OOS information for closure to the published target — is documented in §9.3 and re-validated under leave-one-symbol-out CV in §6.3.3 (each held-out symbol's $c(\tau)$ is fit on the other nine, never sees the held-out symbol's data).

## 7.4 σ̂ selection procedure and multiple-testing disclosure

The per-symbol scale rule $\hat\sigma_s(t)$ is the only deployment constant of the architecture that does not have a closed-form derivation from its specification. A pre-registered three-gate selection compared five σ̂ rules; **the deployment decision rests on Gate 3 — a single bootstrap CI per $\tau$ on pooled half-width with no multi-test exposure — which selects EWMA HL=8 as statistically significantly narrower than the K=26 baseline at $\tau \in \{0.85, 0.95, 0.99\}$ at preserved calibration. Gate 1 (per-cell split-date Christoffersen) is qualitative supporting context once Benjamini-Hochberg correction is applied across the 80-cell grid.** The full procedure follows.

### 7.4.1 Pre-registered three-gate criterion

Before running the σ̂ comparison we registered three gates the deployed σ̂ rule must satisfy:

1. **Gate 1 — split-date Christoffersen.** No (split × $\tau$) cell rejecting at uncorrected $\alpha = 0.05$ across the four split anchors {2021, 2022, 2023, 2024} × four $\tau$ anchors. Motivation: the K=26 baseline introduced 2021/2022 split-date Christoffersen rejections at $\tau = 0.95$ that earlier ablation rungs did not have; we want a σ̂ rule that closes those without re-introducing them elsewhere.
2. **Gate 2 — per-symbol Kupiec.** Pass-rate 10/10 at $\tau = 0.95$. Motivation: the σ̂-standardisation architecture exists to fix the per-symbol bimodality of an unweighted Mondrian fit; any σ̂ rule that loses this property is rejected.
3. **Gate 3 — bootstrap CI on pooled half-width.** The 95% bootstrap CI upper bound on $\Delta$hw% (vs the K=26 baseline) must lie within $+5\%$ at every $\tau$. Motivation: any σ̂ rule that materially widens the deployed band relative to baseline must be justified on calibration grounds; we cap the calibration-for-width trade at $+5\%$ a priori.

Gate 3 has no multiple-testing exposure: a single bootstrap CI per $\tau$ (no per-cell tests), the threshold is pre-registered. Gates 1 and 2 are per-cell tests that — at uncorrected $\alpha$ — accumulate multi-test risk. Gate 1 is the most exposed (16 cells per variant × 5 variants = 80 cells); we report that exposure and apply Benjamini-Hochberg correction below.

### 7.4.2 The five-variant ladder

Five σ̂ rules were considered:

- **K=26 baseline.** Trailing 26-weekend window, equal-weight.
- **EWMA HL=6.** Exponentially-weighted moving average of past relative residuals, weekend half-life 6.
- **EWMA HL=8.** Same, half-life 8.
- **EWMA HL=12.** Same, half-life 12.
- **Convex blend.** $0.5 \cdot$ K=26 $+\, 0.5 \cdot$ EWMA HL=8.

All five share the ≥8-past-observation warm-up rule and the strict pre-Friday convention; all five build $\hat\sigma_s$ over the same evaluable panel ($n = 5{,}916$). Per-variant artefacts (regime quantile table + $c(\tau)$ + $\delta(\tau)$ schedules) were re-fit at the same training cutoff (2023-01-01); δ collapsed to zero across all five variants. Outputs in `reports/tables/sigma_ewma_*.csv`.

### 7.4.3 Gate 1 — split-date Christoffersen across all 80 cells

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

EWMA HL=8 produces uncorrected $p$-values that are higher than the K=26 baseline at every one of the four split anchors at $\tau = 0.95$ ($0.115$ vs $0.006$; $0.186$ vs $0.002$; $0.603$ vs $0.274$; $0.671$ vs $0.525$); the column-wise minimum rises from $0.002$ under K=26 to $0.115$ under HL=8. We treat this consistent column-wise lift as *qualitative supporting context* — it is the pattern in the raw $p$-values that originally motivated the σ̂ work — but we do not claim it as statistical evidence: under BH correction, none of these per-cell differences are formally significant. The statistical weight for the deployment decision is carried by Gate 3 (§7.4.5), which is a single-quantity bootstrap CI with no multi-test exposure.

### 7.4.4 Gate 2 — per-symbol Kupiec at $\tau = 0.95$

Per-symbol Kupiec at $\tau = 0.95$ on the 2023+ OOS slice across the 5 σ̂ variants × 10 symbols (`reports/tables/sigma_ewma_per_symbol.csv`):

| variant | per-symbol Kupiec pass-rate at $\tau = 0.95$ |
|---|---:|
| K=26 baseline | 10 / 10 |
| EWMA HL=6 | 10 / 10 |
| **EWMA HL=8** | **10 / 10** |
| EWMA HL=12 | 10 / 10 |
| Convex blend | 10 / 10 |

All five variants pass Gate 2. Per-symbol calibration is a property of the architecture (per-symbol σ̂ standardisation), not the σ̂ rule — once σ̂ is per-symbol and pre-Friday, the rule's half-life affects pooled width and split-date temporal independence but not per-symbol Kupiec at $\tau = 0.95$ on this panel. **Gate 2 does not discriminate among the variants.**

### 7.4.5 Gate 3 — bootstrap CI on pooled half-width

Per-variant Δhw% versus the K=26 baseline at each $\tau$, with 95% block-bootstrap CIs (1000 weekend-block resamples, seed=0; `reports/tables/sigma_ewma_bootstrap.csv`). The deployed σ̂ rule must have a 95% CI upper on Δhw% within +5% at every $\tau$:

| $\tau$ | EWMA HL=8 Δhw% (vs K=26) | 95% CI on Δhw% | within +5% gate? |
|---:|---:|---:|:---:|
| 0.68 | $-1.34\%$ | $[-3.02,\ +0.25]$ | ✓ |
| 0.85 | $-2.07\%$ | $[-3.75,\ -0.45]$ | ✓ (also significantly narrower) |
| 0.95 | $-3.83\%$ | $[-6.15,\ -1.88]$ | ✓ (also significantly narrower) |
| 0.99 | $-7.41\%$ | $[-9.33,\ -5.65]$ | ✓ (also significantly narrower) |

EWMA HL=8 satisfies Gate 3 with the upper-bound CI at $+0.25\%$ across all $\tau$ — well inside the $+5\%$ pre-registered cap. EWMA HL=8 is *narrower* than the K=26 baseline at every $\tau$ in the bootstrap point estimate; the 95% CI excludes zero on the narrow side (i.e. **statistically significantly narrower**) at $\tau \in \{0.85, 0.95, 0.99\}$, and is neutral at $\tau = 0.68$ (CI straddles zero). At no $\tau$ is EWMA HL=8 statistically significantly *wider* than baseline — the comparison is one-sided. Realised-coverage deltas at $\tau \in \{0.95, 0.99\}$ are exactly zero by construction (per-symbol Kupiec is preserved and the pooled count is unchanged on this finite panel); at $\tau \in \{0.68, 0.85\}$ the paired Δ-realised CIs straddle zero. Calibration is preserved at the deployed anchors; sharpness improves. Gate 3 is the load-bearing gate for the deployment decision: it has no multi-test exposure (one CI per $\tau$, threshold pre-registered), and EWMA HL=8 is the variant that delivers the largest narrowing relative to baseline while satisfying the gate.

### 7.4.6 Held-out forward-tape variant comparison

To re-validate the σ̂ selection on data not used in any of the three gates, the forward-tape harness (§6.7) carries a sibling variant-comparison runner (`scripts/run_forward_tape_variant_comparison.py`). The runner loads a content-addressed *variant bundle* (`data/processed/lwc_variant_bundle_v1_frozen_20260504.json`, SHA-256 `7cef6132d970…`) with $(q_r,\,c(\tau),\,\delta(\tau))$ schedules for all five variants at the same 2023-01-01 training cutoff, and applies each variant's frozen schedules to the forward-tape rows. The comparison **never re-selects** among variants — its function is to flag if a different σ̂ rule looks dramatically cleaner on the held-out slice; if so, that's a finding that motivates a re-fit with disclosure, not an automatic re-deploy. Output: `reports/m6_forward_tape_{N}weekends_variants.{md,csv}`.

**Status at submission:** $N = 1$ forward weekend (`reports/m6_forward_tape_1weekends_variants.md`, 2026-05-01). The variant comparison is uninterpretable at $N = 1$ — its function is to flag a held-out σ̂-rule discrepancy after the preliminary banner clears at $N \geq 4$, with moderate power against a meaningful per-variant gap requiring $N \geq 13$. The σ̂ deployment claim therefore rests on Gates 2 and 3 of §7.4.1–§7.4.5; the forward-tape variant comparison is operational and accumulating, not yet held-out evidence the deployment leans on.

### 7.4.7 Honest framing of the σ̂ deployment claim

The selection procedure is what it is: a 5-variant ladder × 16-cell grid × 3 gates, with the three gates pre-registered and the multiple-testing exposure of Gate 1 disclosed and corrected. Under BH at FDR=0.05, Gate 1 alone does not statistically distinguish the five variants — the formal selection signal that Gate 1 carried at uncorrected $\alpha$ is washed out by the multi-test correction, exactly as one would expect with 80 tests against a correct null. Gates 2 and 3 — both unambiguously satisfied by EWMA HL=8 — are the deployment-load-bearing tests. The forward-tape variant-comparison harness (§7.4.6) is the held-out re-validation.

**We claim that EWMA HL=8 satisfies the pre-registered three-gate criterion under uncorrected per-cell $\alpha = 0.05$; that under BH multi-test correction the per-cell Christoffersen evidence does not statistically distinguish the five variants; that the qualitative pattern in the uncorrected $\tau = 0.95$ column ($p$-values strictly higher under HL=8 than baseline at every split anchor) is consistent with the deployment choice but is supporting context, not statistical evidence; and that the deployment decision rests on Gate 3 (the bootstrap CI on width, no multi-test issue, statistically significantly narrower at $\tau \in \{0.85, 0.95, 0.99\}$ with calibration preserved) plus the held-out forward-tape re-validation. We do not claim the σ̂ rule is optimal among all locally-weighted variants** (§3.5 non-goal). A future paper may sweep finer half-life grids, alternative weight kernels, or hybrid rules; that work is gated on accumulating forward-tape evidence to re-validate any new selection on truly held-out data.

### 7.4.8 Regime quartile cutoff $q$ — ablation under the three-gate frame

The deployed `high_vol` regime gate (§5.5) is "VIX at Friday close in the top quartile of its trailing 252-trading-day window" — a single scalar $q = 0.75$. Ablating $q \in \{0.60, 0.67, 0.70, 0.75, 0.80, 0.90\}$ under the three-gate frame of §7.4.1 (`reports/tables/paper1_b1_regime_threshold_ablation.csv`, `..._hw_bootstrap.csv`):

| $q$ | high_vol mix (%) | Gate 1: pooled Kupiec all $\tau$ | Gate 1b: pooled Christoffersen all $\tau$ | Gate 2: per-symbol Kupiec | $\Delta$hw% at $\tau = 0.95$ vs deployed (95% CI) |
|---|---:|:---:|:---:|---:|---:|
| 0.60 | 38.9 | ✓ | ✓ | 10/10 | $-2.76\%\ [-3.80, -1.73]$ |
| 0.67 | 30.8 | ✓ | ✓ | 10/10 | $-1.78\%\ [-2.66, -0.87]$ |
| 0.70 | 28.8 | ✓ | ✓ | 10/10 | $+1.73\%\ [+0.85, +2.71]$ |
| **0.75 (deployed)** | **23.9** | **✓** | **✓** | **10/10** | — |
| 0.80 | 21.1 | ✓ | ✓ | 10/10 | $-1.70\%\ [-2.11, -1.32]$ |
| 0.90 | 12.3 | ✓ | ✗ rejects | 10/10 | $-4.30\%\ [-5.34, -3.25]$ |

5 of 6 candidates satisfy Gates 1, 1b, and 2. Three alternates ($q \in \{0.60, 0.67, 0.80\}$) deliver $1.7$–$2.8\%$ narrower bands at preserved calibration with bootstrap CIs excluding zero. The deployed $q = 0.75$ is **convention-anchored** (top quartile by definition) rather than width-optimization-selected. The differences are operationally small ($\sim 5$ bps on a 370 bps $\tau = 0.95$ headline) but real; a future re-tuning on a held-out tune slice could close this gap.

### 7.4.9 Split anchor — robustness across {2021, 2022, 2023, 2024}

The deployed train/test split anchor is 2023-01-01 (1 scalar). Ablating across $\{2021, 2022, 2023, 2024\}$-01-01 (re-fit per anchor; `reports/tables/m6_lwc_robustness_split_sensitivity.csv`):

| split anchor | $n_\text{OOS}$ weekends | $\tau = 0.95$ realised | Kupiec $p$ | Christoffersen $p$ | hw bps | per-sym Kupiec |
|---|---:|---:|---:|---:|---:|---:|
| 2021-01-01 | 277 | $0.9539$ | 0.348 | 0.115 | 357.2 | 10/10 |
| 2022-01-01 | 225 | $0.9520$ | 0.661 | 0.186 | 363.5 | 10/10 |
| **2023-01-01 (deployed)** | **173** | **$\mathbf{0.9503}$** | **0.956** | **0.603** | **370.6** | **10/10** |
| 2024-01-01 | 121 | $0.9504$ | 0.947 | 0.671 | 416.8 | 10/10 |

Realised $\tau = 0.95$ coverage stays in $[0.9503, 0.9539]$; Kupiec $p \in [0.35, 0.96]$; Christoffersen $p \in [0.12, 0.67]$; per-symbol Kupiec 10/10 across all four anchors. The deployed split anchor is robust. Half-width varies (357 → 417 bps) — driven by the eval-slice composition effect documented in §6.3.3.1 (later eval slices contain more high-σ̂ weekends, including the 2024-08-05 BoJ unwind).

### 7.4.10 Disclosure-DOF accounting

After §7.4.8 and §7.4.9 the deployment-DOF count rises from 16 to **19 scalars** with proper-ablation provenance: 12 trained per-regime quantiles + 4 OOS-fit $c(\tau)$ + 0 walk-forward $\delta$ + 1 σ̂ rule selector (EWMA HL=8, §7.4.1–7) + 1 regime quartile cutoff ($q = 0.75$, §7.4.8) + 1 split anchor (2023-01-01, §7.4.9). All three appended scalars satisfy the three-gate criterion under their respective ablation tables. The "16 scalars undercounts DOF" critique closes.

## 7.5 How σ̂ standardisation redistributes width across symbols

§7.1.3 attributed the constant-buffer premium to `high_vol`; §7.2 attributed the per-symbol Kupiec fix to σ̂ standardisation; this section attributes the +4.5% pooled half-width tax to a width *redistribution* across symbols within a regime.

**Per-class decomposition at $\tau = 0.95$.** Where the unweighted Mondrian comparator pays a uniform width within a regime, the deployed architecture redistributes that width across symbols within a regime via the per-symbol $\hat\sigma_s$ multiplier:

| class | $n$ | unweighted Mondrian hw at $\tau=0.95$ | deployed hw at $\tau=0.95$ | Δ |
|---|---:|---:|---:|---|
| equities (8 symbols) | 1,384 | 354.6 bps | 417.8 bps | **+17.8%** (carries the per-symbol heavy-tail fix) |
| GLD + TLT (2 symbols) | 346  | 354.6 bps | 181.6 bps | **−48.8%** (releases over-conservative defensive bands) |

Row-weighted reconciliation against the §6.3 panel pooled: $(1384 \cdot 417.8 + 346 \cdot 181.6) / 1730 = 370.6$ bps, matching the §6.3.1 panel-pooled HW at $\tau = 0.95$.

Under the unweighted comparator, every symbol within a regime received the same $c(\tau) \cdot q_r(\tau) \cdot p_{\text{Fri}}$ width — the "common multiplier on heterogeneous tails" failure of §6.4.1; the per-class mean HW is identical across classes because the regime mix is identical across symbols (regime is global, §5.5) and width within a regime carries no per-symbol axis. Under the deployed architecture, the σ̂ multiplier is per-symbol, so heavy-tail equities (HOOD, MSTR, TSLA) receive bands that match their relative residual scale, and the over-covered defensive class (GLD, TLT) receives narrower bands without losing coverage.

The +4.5% pooled width tax of §7.2.1 is the *equity-weighted* read on a panel that is 80% equity rows ($1{,}384 / 1{,}730$). Under the deployed architecture the average equity-class symbol receives a +17.8% wider band than under an unweighted Mondrian fit ($417.8$ vs $354.6$ bps); a defensive-class symbol (GLD, TLT) receives a −48.8% narrower one ($181.6$ vs $354.6$). The redistribution is *toward heavy-tail equities*, where the per-symbol calibration evidence demands it (§6.4.1: TSLA, MSTR, HOOD all in the $0.052$–$0.058$ violation-rate band that the unweighted comparator could not deliver), and *away from defensive collateral*, where the previous regime-pooled multiplier was over-conservative. A protocol whose collateral mix is dominated by equity xStocks should expect the deployed mean served band to be materially wider than the unweighted comparator's; a protocol whose collateral mix is dominated by GLD/TLT will see materially narrower bands. The pooled +4.5% figure is the right summary of the trade only at the deployed panel composition; downstream consumers should re-weight by their own collateral mix.

The §10 candidate architectures (cross-sectional common-mode partial-out, full-distribution conformal, sub-regime granularity) target the residual rejections (§6.3.6 cross-sectional within-weekend correlation; §9.4 per-symbol Berkowitz on TSLA/TLT) that σ̂ standardisation does not reach.
