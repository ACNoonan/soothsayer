# Appendix D — Ablation detail and the σ̂ ladder

§7 carries the effect sizes for the three load-bearing components; this appendix carries the full tables and equations, the walk-forward δ(τ) finding, the c(τ) schedule analysis, the σ̂ selection ladder and its supporting robustness battery, the vol-index switchboard selection evidence, the width-redistribution decomposition, and the tokenized-tracking baseline — whose deployment headline (−45% half-width, −46% Winkler at matched coverage; 7 of 9 symbols) appears in §6.2, with the construction, full grid, and the matched-calibration-history decomposition (D.7.7, which shows about half that edge is the 12-year calibration record rather than the architecture) here.

All deltas carry block-bootstrap 95% CIs by weekend (1,000 resamples, seed=0, paired by `(symbol, fri_ts)`). Raw tables: `reports/tables/v1b_constant_buffer_*.csv`, `reports/tables/v1b_mondrian_*.csv`, `reports/tables/m5_vs_m6_bootstrap.csv`, `reports/tables/sigma_ewma_*.csv`, `reports/tables/paper1_c2_tokenised_tracking_baseline*.csv`.

## D.1 Regime stratification — vs constant-buffer baseline

The constant-buffer baseline is the Pyth/Chainlink Friday close held forward, with a single global symmetric buffer $b(\tau)$ per claimed quantile — one parameter per $\tau$, no factor switchboard, no residual quantile, no regime model:

$$\big[\;p_{\text{Fri}}\,(1 - b(\tau)),\;p_{\text{Fri}}\,(1 + b(\tau))\;\big],\qquad b(\tau)\;\text{calibrated globally on the training panel}.$$

### D.1.1 Trained-buffer fit on OOS

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

The training-fit constant buffer under-covers at every $\tau \leq 0.95$ (deficits $-14.2 / -12.0 / -5.4$pp, all rejecting Kupiec at $p_{uc} < 10^{-6}$). The mechanism is non-stationarity: $b(\tau)$ is calibrated on a 2014–2022 window calmer than the 2023+ holdout, and a single global scalar has no channel through which to adapt. The deployable constant-buffer baseline does not deliver coverage on the holdout; the regime-stratified architecture does.

### D.1.2 Coverage-matched comparison

To answer the width-at-coverage question, we re-fit $b(\tau)$ post-hoc on the OOS slice (oracle-fit, non-deployable, but gives the constant buffer the most generous trade-off):

| $\tau$ | matched $b$ | matched-CB hw (bps) | deployed hw (bps) | $\Delta$ width (deployed − CB) |
|---:|---:|---:|---:|---|
| 0.68 | 1.21% | 120.9 | 130.8 | **+8.2% [+3.7, +13.0]** |
| 0.85 | 2.26% | 226.4 | 213.6 | **−5.7% [−10.6, −0.5]** |
| 0.95 | 3.96% | 395.6 | 370.6 | **−6.3% [−12.1, −0.4]** |
| 0.99 | 5.46% | 545.8 | 635.0 | $+16.3\%$ [$+9.6$, $+23.6$] |

The deployed architecture is narrower than a coverage-matched (oracle-fit) constant buffer at $\tau \in \{0.85, 0.95\}$. The σ̂ standardisation that redistributes width across symbols (§D.6) reaches sufficient sharpness on the equity-heavy panel that the deployment outperforms even the oracle-fit constant buffer at the headline anchor; the architecture is wider only at $\tau \in \{0.68, 0.99\}$, where the cell-conditional regime structure carries genuine information. The regime model + σ̂ buy *both* coverage on a non-stationary distribution *and* mean-width sharpness at $\tau \in \{0.85, 0.95\}$ against the strongest non-modelled comparator.

### D.1.3 Per-regime decomposition

The pooled half-width at $\tau = 0.95$ hides a regime-conditional structure. Deployed pooled: $370.6$ bps; per-regime $300.1 / 334.7 / 603.7$ bps (normal / long_weekend / high_vol). The matched-CB at $\tau = 0.95$ delivers $395.6$ bps in *every* regime by construction (one global multiplier). The regime model concentrates width in `high_vol` ($+52\%$ vs CB at $603.7$ vs $395.6$) where it earns $-1.1$pp coverage; releases width in `normal` ($-24\%$ vs CB at $300.1$ vs $395.6$) without losing coverage. The constant buffer's pooled coverage is average-right but worst where it matters most: violations concentrate in high-vol weekends — exactly where a downstream lending protocol incurs the largest mark-to-market gap. The regime model's contribution is **(i) calibration through distribution shift** and **(ii) tail-protection in `high_vol` weekends** at sharper *normal*-regime widths than the constant buffer.

## D.2 Per-symbol σ̂ standardisation — vs unweighted Mondrian

The *unweighted Mondrian comparator* shares the regime structure of D.1 but omits the per-symbol scale standardisation: a single per-(regime, $\tau$) conformal quantile is fit on the *un-standardised* relative residual $|P_{\text{Mon}} - \hat P_{\text{Mon}}| / P_{\text{Fri}}$, and the served band uses that quantile directly as a fraction of $P_{\text{Fri}}$. Same training set, same OOS slice, same point estimator, same regime classifier, same finite-sample CP rank formula. Only the σ̂ standardisation of the conformity score is added by the deployed architecture.

### D.2.1 OOS pooled results

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

The pooled half-width tax at $\tau = 0.95$ is **$+4.5\%$** (370.6 vs 354.6 bps; $+15.93$ bps with 95% block-bootstrap CI $[+1.05,\,+30.73]$ from `m5_vs_m6_bootstrap.csv`). The per-symbol calibration is bought at exactly that price; §D.6 documents how the +4.5% pooled figure resolves into a +17.8% widening on heavy-tail equities and a −48.8% narrowing on the defensive class.

### D.2.2 Side-by-side at $\tau = 0.95$

The σ̂-standardisation isolation: same point estimator, same regime classifier, same Mondrian split-conformal, same finite-sample CP rank formula, same training set, same OOS slice. Only the σ̂ standardisation of the conformity score is added.

| metric | unweighted Mondrian | deployed (σ̂-standardised) |
|---|---:|---:|
| pooled realised | 0.9503 | 0.9503 |
| pooled half-width (bps) | 354.6 | 370.6 |
| per-symbol Kupiec pass-rate | 2 / 10 | **10 / 10** |
| per-symbol Berkowitz LR range | 0.9 – 224 (250×) | **3.2 – 16.7 (5.2×)** |
| LOSO realised std at $\tau = 0.95$ | 0.0759 | **0.0128 (5.9× tighter)** |
| LOSO Kupiec pass-rate (held-out) | 8 / 10 | **10 / 10** |

The per-symbol Kupiec pass-rate, Berkowitz LR range, and LOSO calibration std all improve simultaneously by mechanism — no other component of the architecture is touched. The Appendix C simulation evidence on synthetic data with known DGP (data-generating process) confirms the same trade under ground truth — under four DGPs spanning homoskedastic, regime-switching, drift, and structural-break specifications, the unweighted Mondrian comparator's per-symbol Kupiec pass-rate at $\tau = 0.95$ collapses to $31$–$38\%$ while σ̂ standardisation closes the bimodality on every DGP at $98.6$–$99.9\%$.

![Per-symbol ablation at $\tau = 0.95$ on real data, in the visual idiom of [romano-cqr-2019] (their Fig. 4) adapted to the per-symbol Mondrian setting. Three method rows — constant-buffer (oracle-fit on the OOS slice; the most generous comparator D.1.2 considers), unweighted Mondrian (M5; same architecture as deployed without σ̂ standardisation), and the deployed σ̂-standardised architecture (M6; bold). Each box is the per-(symbol, split-anchor) cell distribution: 10 symbols $\times$ 4 split anchors $\{2021, 2022, 2023, 2024\}$-01-01 = 40 cells per row. Median pills annotate the leftmost edge. Left panel: mean half-width (bps). Right panel: realised coverage; dotted vertical marks $\tau = 0.95$. The deployed-σ̂ row collapses per-symbol coverage onto nominal (cross-cell std $0.0092$) while CB-matched and M5 disperse from $\sim 0.78$ to $1.00$ ($0.071$ and $0.062$ respectively) — pooled-coverage parity through compensating per-symbol biases. The half-width panel is the dual: M6 widths span $\sim 150$–$830$ bps within each split anchor (per-symbol $\hat\sigma_s$ redistribution; §D.6), while CB and M5 are uniform across symbols by construction. Source table: `reports/tables/paper1_fig7b_per_symbol_ablation.csv`.\label{fig:fig7b-oos-ablation}](figures/fig7b_oos_ablation.pdf)

### D.2.3 Walk-forward $\delta(\tau)$ selection — collapses to zero

Under an unweighted Mondrian fit, a plain $c(\tau)$ correction to the pooled OOS slice produces per-split realised coverage that scatters around nominal — it passes Kupiec on the pooled fit by construction but under-covers in roughly half the splits, and stabilising it requires a per-anchor structural-conservatism shift $\delta(\tau)$. Under the σ̂-standardised architecture the same walk-forward sweep over $\delta \in \{0.00, \dots, 0.07\}$ on the four powered tune fractions $f \in \{0.40, 0.50, 0.60, 0.70\}$ selects $\delta(\tau) \equiv 0$: per-symbol scale standardisation tightens cross-split realised-coverage variance enough that the shift is not load-bearing. The $\delta$ schedule an unweighted comparator requires thus collapses to identity once σ̂ is per-symbol. The schedule is retained as a four-zero vector in the artefact JSON for shape-compatibility with the receipt schema, and the deployment carries zero walk-forward-tuned scalars (§4.5).

## D.3 Near-identity OOS $c(\tau)$ bump

The deployed $c(\tau)$ schedule is

$$c(\tau) = \{0.68\!:\!1.000,\;0.85\!:\!1.000,\;0.95\!:\!1.079,\;0.99\!:\!1.003\}.$$

This is a 4-scalar multiplicative correction fit on the 2023+ OOS slice as the smallest $c \in [1, 5]$ such that pooled realised coverage with effective quantile $c \cdot q_r(\tau)$ matches $\tau$. Three of the four are essentially identity: under the deployed σ̂ rule and the 2023-01-01 split, the trained per-regime quantile already lands within 0.3 pp of nominal at $\tau \in \{0.68, 0.85, 0.99\}$, so $c(\tau)$ at those anchors collapses to $\{1.000, 1.000, 1.003\}$. Only $\tau = 0.95$ has a meaningful train-OOS distribution-shift gap; the 7.9% widening at that anchor is what closes the pooled $0.946 \to 0.950$ correction.

$c(\tau)$ thus carries one scalar of meaningful OOS information, not four. Dropping the $c(\tau)$ correction and serving at the trained-quantile coverage costs ~0.4 pp at $\tau = 0.95$ on this slice (0.946 vs the deployment-tuned 0.950) — statistically indistinguishable from nominal under Kupiec, but a persistent deficit on the served claim. §8 carries the provenance disclosure for $c(0.95)$; §6.1's LOSO cross-validation re-validates it on held-out symbol data.

## D.4 σ̂ selection procedure and multiple-testing disclosure

The per-symbol scale rule $\hat\sigma_s(t)$ is the only deployment constant of the architecture without a closed-form derivation. The comparison set is a five-variant ladder on the 2023+ OOS slice — K=26 trailing window (baseline), EWMA HL=$\{6, 8, 12\}$, and a 50/50 K=26 / EWMA-HL-8 convex blend — under the pre-registered three-gate criterion stated in §7: **Gate 1**, no per-cell rejection at uncorrected $\alpha = 0.05$ on the 16-cell split-date Christoffersen grid; **Gate 2**, per-symbol Kupiec 10/10 at $\tau = 0.95$; **Gate 3**, 95% bootstrap CI upper bound on $\Delta$hw% (vs K=26) within $+5\%$ at every $\tau$. All five variants share the ≥8-past-observation warm-up and pre-Friday convention; per-variant artefacts ($q_r$, $c(\tau)$, $\delta(\tau)$) were re-fit at the same 2023-01-01 cutoff with $\delta$ collapsing to zero on every variant.

**Gate 1 (multi-test corrected) does not discriminate.** At uncorrected $\alpha$, EWMA HL=8 is the only variant with zero per-cell rejections; K=26 carries 4. Under Benjamini–Hochberg (false-discovery-rate) correction at FDR=0.05 across the full 80-cell grid (5 variants × 16 cells), no variant has any rejected cell — the smallest $q$-value in the grid is $0.130$ (K=26, 2022 split, $\tau = 0.95$). After multi-test correction, per-cell Christoffersen evidence does not statistically distinguish the five variants. **Gate 2 (per-symbol Kupiec) also does not discriminate** — all five pass 10/10 at $\tau = 0.95$, which the D.2 ablation already established as a property of per-symbol σ̂ standardisation rather than of the rule's half-life.

**Gate 3 (bootstrap CI on width) is load-bearing** (`reports/tables/sigma_ewma_bootstrap.csv`):

| $\tau$ | EWMA HL=8 Δhw% (vs K=26) | 95% CI on Δhw% | within +5% gate? |
|---:|---:|---:|:---:|
| 0.68 | $-1.34\%$ | $[-3.02,\ +0.25]$ | ✓ |
| 0.85 | $-2.07\%$ | $[-3.75,\ -0.45]$ | ✓ (also significantly narrower) |
| 0.95 | $-3.83\%$ | $[-6.15,\ -1.88]$ | ✓ (also significantly narrower) |
| 0.99 | $-7.41\%$ | $[-9.33,\ -5.65]$ | ✓ (also significantly narrower) |

EWMA HL=8 is narrower than K=26 at every $\tau$ in point estimate and statistically significantly narrower at $\tau \in \{0.85, 0.95, 0.99\}$; calibration is preserved (paired Δ-realised CIs straddle zero, per-symbol Kupiec 10/10 holds). Gate 3 has no multi-test exposure: one bootstrap CI per $\tau$, threshold pre-registered. EWMA HL=8 satisfies all three gates and delivers the largest narrowing relative to baseline.

**Held-out re-validation.** The forward-tape harness (§5.8) carries a sibling variant-comparison runner (`scripts/run_forward_tape_variant_comparison.py`) that loads a content-addressed *variant bundle* with frozen $(q_r,\,c(\tau),\,\delta(\tau))$ schedules for all five variants and applies them to forward weekends as they accumulate. The runner *never re-selects* — its function is to flag if a different σ̂ rule looks dramatically cleaner on truly held-out data. Status at submission: $N = 11$ forward weekends (`reports/m6_forward_tape_11weekends_variants.md`, 2026-05-01 → 2026-07-10); $N$ has cleared the harness's own preliminary banner ($N \ge 4$) though moderate per-variant power still requires $N \ge 13$. On the forward slice the five variants are near-indistinguishable — pooled half-widths at $\tau = 0.95$ span $293.6$–$321.5$ bps with identical realised coverage ($0.964$), and no variant looks dramatically cleaner than canonical EWMA HL=8, so the re-validation raises no flag to revisit the selection. The σ̂ deployment claim therefore rests on Gate 3 plus the (accumulating) forward-tape re-validation. We do not claim the σ̂ rule is optimal among all locally-weighted variants (§3.5 non-goal).

### D.4.1 Regime quartile cutoff $q$ — ablation under the three-gate frame

The deployed `high_vol` regime gate (§5.5) is "VIX at Friday close in the top quartile of its trailing 252-trading-day window" — a single scalar $q = 0.75$. Ablating $q \in \{0.60, 0.67, 0.70, 0.75, 0.80, 0.90\}$ under the three-gate frame of D.4 (`reports/tables/paper1_b1_regime_threshold_ablation.csv`, `..._hw_bootstrap.csv`):

| $q$ | high_vol mix (%) | Gate 1: pooled Kupiec all $\tau$ | Gate 1b: pooled Christoffersen all $\tau$ | Gate 2: per-symbol Kupiec | $\Delta$hw% at $\tau = 0.95$ vs deployed (95% CI) |
|---|---:|:---:|:---:|---:|---:|
| 0.60 | 38.9 | ✓ | ✓ | 10/10 | $-2.76\%\ [-3.80, -1.73]$ |
| 0.67 | 30.8 | ✓ | ✓ | 10/10 | $-1.78\%\ [-2.66, -0.87]$ |
| 0.70 | 28.8 | ✓ | ✓ | 10/10 | $+1.73\%\ [+0.85, +2.71]$ |
| **0.75 (deployed)** | **23.9** | **✓** | **✓** | **10/10** | — |
| 0.80 | 21.1 | ✓ | ✓ | 10/10 | $-1.70\%\ [-2.11, -1.32]$ |
| 0.90 | 12.3 | ✓ | ✗ rejects | 10/10 | $-4.30\%\ [-5.34, -3.25]$ |

5 of 6 candidates satisfy Gates 1, 1b, and 2. Three alternates ($q \in \{0.60, 0.67, 0.80\}$) deliver $1.7$–$2.8\%$ narrower bands at preserved calibration with bootstrap CIs excluding zero. The deployed $q = 0.75$ is **convention-anchored** (top quartile by definition) rather than width-optimization-selected. The differences are operationally small ($\sim 5$ bps on a 370 bps $\tau = 0.95$ headline) but real; a re-tuning on a held-out tune slice could close this gap.

### D.4.2 Split anchor — robustness across {2021, 2022, 2023, 2024}

The deployed train/test split anchor is 2023-01-01 (1 scalar). Ablating across $\{2021, 2022, 2023, 2024\}$-01-01 (re-fit per anchor; `reports/tables/m6_lwc_robustness_split_sensitivity.csv`):

| split anchor | $n_\text{OOS}$ weekends | $\tau = 0.95$ realised | Kupiec $p$ | Christoffersen $p$ | hw bps | per-sym Kupiec |
|---|---:|---:|---:|---:|---:|---:|
| 2021-01-01 | 277 | $0.9539$ | 0.348 | 0.115 | 357.2 | 10/10 |
| 2022-01-01 | 225 | $0.9520$ | 0.661 | 0.186 | 363.5 | 10/10 |
| **2023-01-01 (deployed)** | **173** | **$\mathbf{0.9503}$** | **0.956** | **0.603** | **370.6** | **10/10** |
| 2024-01-01 | 121 | $0.9504$ | 0.947 | 0.671 | 416.8 | 10/10 |

Realised $\tau = 0.95$ coverage stays in $[0.9503, 0.9539]$; Kupiec $p \in [0.35, 0.96]$; Christoffersen $p \in [0.12, 0.67]$; per-symbol Kupiec 10/10 across all four anchors. The deployed split anchor is robust. Half-width varies (357 → 417 bps) — driven by an eval-slice composition effect: later eval slices contain more high-σ̂ weekends, including the 2024-08-05 BoJ unwind (§8).

### D.4.3 Cross-asset regime-index sensitivity

The classifier uses VIX as the high-vol gate for *all* symbols, including GLD (gold) and TLT (long-dated treasury) which have asset-specific vol indices (GVZ, MOVE) used in the σ̂ regression (§5.4). A sensitivity ablation that swaps GLD's regime gate to GVZ and TLT's to MOVE — flipping the regime tag on $23\%$ of GLD weekends and $28\%$ of TLT weekends — leaves the pooled $\tau = 0.95$ headline coverage unchanged at $0.9503$ (Kupiec $p = 0.956$), per-symbol Kupiec 10/10, and half-width within $0.1\%$. The σ̂-standardisation absorbs the regime-tagging difference structurally; the regime cell contributes a small marginal adjustment via $q_r(\tau)$, not a load-bearing scale separation. Source: `reports/tables/paper1_b4_regime_index_sensitivity.csv`, `..._per_symbol.csv`. The deployed VIX-only classifier is justified by simplicity and per-asset-vol-index-agnosticism, not by being optimally tuned per asset.

## D.5 Vol-index switchboard selection evidence

The per-symbol vol-index assignments of §5.4 (GVZ for GLD, MOVE for TLT, VIX elsewhere) are evidence-driven rather than conventional. In the V1b validation pass, fitting the log-log sigma regression with VIX as the vol index yielded $\hat\beta \approx 0.55$ for GLD and $\hat\beta \approx 0.94$ for TLT, well below the equity-class mean ($\hat\beta \approx 1.5$) — the VIX level carries materially less information about defensive-class weekend residual scale than about equity scale. Substituting GVZ and MOVE lifted $\hat\beta$ into the equity range and improved coverage at matched bandwidth. Note the asymmetry with D.4.3: the asset-native indices are load-bearing in the *scale* pathway but not in the *regime-gate* pathway, where σ̂ standardisation absorbs the tagging difference.

## D.6 How σ̂ standardisation redistributes width across symbols

D.1.3 attributed the constant-buffer premium to `high_vol`; D.2 attributed the per-symbol Kupiec fix to σ̂ standardisation; this section attributes the +4.5% pooled half-width tax to a width *redistribution* across symbols within a regime.

**Per-class decomposition at $\tau = 0.95$.** Where the unweighted Mondrian comparator pays a uniform width within a regime, the deployed architecture redistributes that width across symbols within a regime via the per-symbol $\hat\sigma_s$ multiplier:

| class | $n$ | unweighted Mondrian hw at $\tau=0.95$ | deployed hw at $\tau=0.95$ | Δ |
|---|---:|---:|---:|---|
| equities (8 symbols) | 1,384 | 354.6 bps | 417.8 bps | **+17.8%** (carries the per-symbol heavy-tail fix) |
| GLD + TLT (2 symbols) | 346  | 354.6 bps | 181.6 bps | **−48.8%** (releases over-conservative defensive bands) |

Row-weighted reconciliation against the §6.1 panel pooled: $(1384 \cdot 417.8 + 346 \cdot 181.6) / 1730 = 370.6$ bps, matching the §6.1 panel-pooled half-width at $\tau = 0.95$.

Under the unweighted comparator, every symbol within a regime received the same $c(\tau) \cdot q_r(\tau) \cdot p_{\text{Fri}}$ width — the common-multiplier-on-heterogeneous-tails failure visible in Fig. S1 (§6.2); the per-class mean HW is identical across classes because the regime mix is identical across symbols (regime is global, §5.5) and width within a regime carries no per-symbol axis. Under the deployed architecture, the σ̂ multiplier is per-symbol, so heavy-tail equities (HOOD, MSTR, TSLA) receive bands that match their relative residual scale, and the over-covered defensive class (GLD, TLT) receives narrower bands without losing coverage.

The +4.5% pooled width tax of D.2.1 is the *equity-weighted* read on a panel that is 80% equity rows ($1{,}384 / 1{,}730$). Under the deployed architecture the average equity-class symbol receives a +17.8% wider band than under an unweighted Mondrian fit ($417.8$ vs $354.6$ bps); a defensive-class symbol (GLD, TLT) receives a −48.8% narrower one ($181.6$ vs $354.6$). The redistribution is *toward heavy-tail equities*, where the per-symbol calibration evidence demands it (§6.2 / Fig. S1: TSLA, MSTR, HOOD all in the $0.035$–$0.046$ violation-rate band that the unweighted comparator could not deliver), and *away from defensive collateral*, where the regime-pooled multiplier was over-conservative. A protocol whose collateral mix is dominated by equity xStocks should expect the deployed mean served band to be materially wider than the unweighted comparator's; a protocol whose collateral mix is dominated by GLD/TLT will see materially narrower bands. The pooled +4.5% figure is the right summary of the trade only at the deployed panel composition; downstream consumers should re-weight by their own collateral mix.

The residual these components do not reach — within-weekend cross-sectional common-mode, and the per-symbol Berkowitz rejections on TSLA/TLT — is §8's subject; a characterised (not deployed) cluster-conditional variant is in Appendix F.

## D.7 Tokenized-tracking baseline (post-Cong)

*§6.3 carries the headline of this comparison; this section carries the construction, the full snapshot and per-symbol grids, and the power caveat.*

The D.1 constant-buffer baseline is the *underlying-frozen* competitor archetype — what a consumer reading the Pyth or Chainlink `price` field gets during the closed window. The complementary archetype, motivated empirically by Cong et al. [cong-tokenized-2025] (Table 10, p. 40), is the *tokenised-tracking* baseline: an oracle that publishes $\text{point}_t = \text{tokenised-side price at } t$ throughout the closed window. Cong et al. report a Hasbrouck-style passthrough $\lambda = 0.903$ with adjusted $R^2 = 0.839$ from off-hour tokenised returns to the close-to-open underlying return — i.e., reading the live tokenised perp during closed hours already explains 84% of the variance in where the underlying reopens. The tokenised-tracking critique therefore has empirical bite on the conditional mean and must be addressed on the conditional quantile. It is a *constructed proxy* for the continuous-tracking archetype, not any vendor's product, and is distinct from D.1's underlying-frozen archetype and from §6.2 / D.2's internal-architecture comparators.

### D.7.1 Baseline construction

For each canonical snapshot $t$ in the closed window:

$$\text{point}_t = \text{perp\_close}_{\text{kraken\_futures}}(t),\qquad \text{halfwidth}_{t,\tau} = \mathrm{quantile}_\tau\Big(\big|\text{mon\_open} - \text{perp\_close}(t)\big|\,;\;\text{past weekends pooled across symbols}\Big).$$

Walk-forward expanding-window calibration over weekends (warm-up = 4 past weekends before the first evaluable observation). The empirical-quantile residual specification is intentional: it places the baseline in the same non-parametric quantile family as the deployed architecture, eliminating the objection that the baseline is handicapped by an imposed Gaussian — the objection §6.2's GARCH baselines invite.

**Snapshot grid.** Six canonical evaluation moments in $[\text{Fri\ 16{:}00\ ET}, \text{Mon\ 09{:}30\ ET}]$: `fri_close` (Fri 16:00 ET), `sat_noon` (Sat 12:00 ET), `sun_noon` (Sun 12:00 ET), `sun_globex` (Sun 20:00 ET CME Globex reopen), `mon_premkt` (Mon 04:00 ET pre-market start), `mon_open` (Mon 09:00 ET just before NMS — national market system / regular-session — reopen). The deployed M6 LWC band is published once at Friday close and held constant; the baseline updates at every snapshot. The baseline's `mon_open` snapshot is its most-informed configuration — the tokenised side has absorbed the entire closed-window news flow by then.

### D.7.2 Panel

The post-launch slice of the LWC artefact ($\text{fri\_ts} \ge 2025\text{-}12\text{-}19$) intersected with the `cex_stock_perp/ohlcv/v1` kraken_futures xstock-backed perp tape: $n = 117$ weekend-symbol observations pre-warmup, $n = 105$ after warm-up. Nine symbols (SPY, QQQ, GLD: 19 weekends each; TSLA, NVDA, GOOGL, AAPL, HOOD, MSTR: $\approx 10$ each). **TLT is excluded** — no xstock-backed perp exists for it. This is materially smaller than the $n = 1{,}730$ panel that backs §6 and D.1–D.6, and §6.2's grid backtests are the powered baselines; D.7 is a head-to-head on a powered-only-for-paired-Winkler post-launch sub-slice. See `reports/v1b_tokenised_tracking_baseline.md` for the full panel description.

### D.7.3 Head-to-head — pooled

The deployed M6 LWC band (one $(point, halfwidth)$ per weekend, held across the closed window) on the bake-off panel; tokenised-tracking baseline at its $\text{mon\_open}$ snapshot (the most-informed configuration). Cong et al.'s λ = 0.903 channels through this row. Winkler is the interval score glossed in §6.3 — width plus a penalty for misses:

| $\tau$ | method | realised | hw (bps) | Winkler (bps) | Kupiec $p_{uc}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | tokenised-tracking (mon_open) | 0.724 | 205 | 661 | 0.330 |
| 0.68 | **this paper (M6 LWC)** | **0.641** | **124** | **426** | **0.371** |
| 0.85 | tokenised-tracking (mon_open) | 0.867 | 372 | 1{,}031 | 0.627 |
| 0.85 | **this paper (M6 LWC)** | **0.863** | **207** | **588** | **0.684** |
| 0.95 | tokenised-tracking (mon_open) | 0.943 | 656 | 1{,}619 | 0.742 |
| 0.95 | **this paper (M6 LWC)** | **0.949** | **358** | **879** | **0.949** |
| 0.99 | tokenised-tracking (mon_open) | 0.981 | 904 | 2{,}572 | 0.407 |
| 0.99 | **this paper (M6 LWC)** | **0.991** | **636** | **1{,}516** | **0.871** |

At $\tau = 0.95$ the deployed architecture matches the baseline's coverage rate ($0.949$ vs $0.943$, both Kupiec-passing) at **$45\%$ narrower half-width** (358 vs 656 bps) and **$46\%$ lower Winkler interval score** (879 vs 1,619 bps). At $\tau = 0.99$ the Winkler gap widens to $-41\%$ — the tail regime where the baseline's empirical-quantile fattens dramatically. Across all six snapshots and four served $\tau$ ($24$ baseline cells), the deployed architecture's mean Winkler is lower on $24$ of $24$.

### D.7.4 Snapshot evolution across the closed window

The strongest configuration a tokenised-tracking competitor can claim is its latest snapshot — by Monday pre-open the tokenised perp has absorbed the weekend news flow. The snapshot evolution at $\tau = 0.95$ measures how much that helps:

| snapshot | baseline hw (bps) | baseline Winkler (bps) | Winkler ratio vs M6 LWC |
|---|---:|---:|---:|
| `fri_close`  | 730 | 1{,}685 | 1.92× worse |
| `sat_noon`   | 733 | 1{,}702 | 1.94× worse |
| `sun_noon`   | 735 | 1{,}698 | 1.93× worse |
| `sun_globex` | 736 | 1{,}696 | 1.93× worse |
| `mon_premkt` | 691 | 1{,}688 | 1.92× worse |
| `mon_open`   | **656** | **1{,}619** | **1.84× worse** |

The baseline tightens by $\sim 10\%$ (730 → 656 bps) across the closed window, but never closes more than half the gap to the deployed architecture's flat 358 bps. Cong et al.'s λ = 0.903 transports the conditional mean; it does not transport the residual distribution, which is what consumes width.

A 15-minute-resolution per-minute Winkler curve (`reports/tables/paper1_c3_per_minute_winkler_curve.csv`; runner `scripts/run_v1b_tokenised_per_minute_winkler.py`) sharpens the finding: at $\tau = 0.95$ the baseline's Winkler is **worst** during Saturday night through Sunday afternoon (hour offsets 32–44 past Fri 16:00 ET, mean Winkler $\approx 2{,}023$ bps; ratio $2.14\times$ the deployed flat $\approx 945$ bps). Waiting until Sunday night for the perp to absorb weekend news does not help — Sunday afternoon is the *worst*-scoring time on the perp, consistent with crypto-native weekend flow drifting the perp price while no underlying-market arbitrage operates to correct it. The Winkler ratio is monotone in neither direction across the closed window; the baseline never closes more than $\sim$half the gap at any minute.

### D.7.5 Per-symbol robustness — where the baseline is competitive

The pooled comparison is honest about where the result is and is not unanimous. Per-symbol Winkler ratio (baseline / M6 LWC at $\tau = 0.95$, `mon_open` snapshot; $> 1$ means M6 LWC wins):

| symbol | $n$ | M6 LWC hw (bps) | baseline hw (bps) | Winkler ratio |
|---|---:|---:|---:|---:|
| HOOD  | 10 |   635 | 2{,}109 | **3.32** |
| GOOGL | 10 |   348 |   509 | **2.91** |
| NVDA  | 10 |   399 |   858 | **2.15** |
| MSTR  | 10 |   735 | 1{,}153 | **1.57** |
| GLD   | 15 |   361 |   345 | **1.46** |
| AAPL  | 10 |   297 |   608 | **1.36** |
| QQQ   | 15 |   214 |   253 | **1.02** |
| SPY   | 15 |   178 |   226 | **0.89** |
| TSLA  | 10 |   468 |   414 | **0.89** |

The deployed architecture wins on Winkler in **7 of 9 symbols**. The two exceptions are SPY and TSLA — the two deepest xstock-backed perp markets, and the symbols where the Cong et al. R² = 0.839 has the most empirical bite. For these names the tokenised perp tracks the NMS open competitively, and a non-parametric empirical-quantile residual band on the perp is sufficient. The deployed architecture's edge widens as perp liquidity thins: for the long tail (HOOD, GOOGL, NVDA, MSTR, GLD, AAPL) the Winkler ratio is $1.36$–$3.32\times$.

The pattern localises the advantage where the consumer's risk-management need is largest — on the thin-liquidity collateral that dominates the named lending-collateral universe (TSLAx aside, every other Kamino-onboarded xStock falls in the long tail above), not on the two deepest perps, where a simpler oracle is genuinely competitive. The defensible claim is: under a non-parametric tokenised-tracking baseline at its most-informed closed-window snapshot, the deployed architecture is the materially-tighter choice on $7$ of $9$ symbols and tied-to-modestly-behind on the other two. The architecture's separation of concerns admits a point-estimate swap — a tokenised-side conditional-mean import — without changing the conformal band scaffolding (Appendix F); the SPY/TSLA gap is a forecaster-swap surface, not a band-architecture failure.

### D.7.6 Sample-size caveat and what is and is not powered

The bake-off panel is $n = 117$ weekend-symbol observations — about $7\%$ of the $n = 1{,}730$ panel that backs §6 and D.1–D.6. At this sample size, the Kupiec / Christoffersen tests have limited power; under both the deployed architecture and the baseline, Kupiec $p_{uc}$ at $\tau = 0.95$ accepts a wide band of realised-coverage values around nominal. **The powered signal in this comparison is the paired Winkler score** — a per-observation diagnostic that is much more powerful at small $n$ than the binomial coverage tests. The pooled coverage results (Kupiec $p_{uc} = 0.949$ for M6 LWC, $0.742$ for the baseline) are consistent with both methods being well-calibrated on this slice; they do not by themselves discriminate between architectures. The width-and-Winkler results do. We treat the §6 / D.1–D.6 panel as the powered backtest of the calibration claim itself, and D.7 as a (smaller-$n$) head-to-head against the tokenised-tracking competitor archetype that complements the D.1 (underlying-frozen) and §6.2 (GARCH-$t$) baselines on a different competitor axis.

Source script: `scripts/run_v1b_tokenised_tracking_baseline.py`; full panel artefact: `data/processed/v1b_tokenised_tracking_baseline.parquet`; tables: `reports/tables/paper1_c2_tokenised_tracking_baseline_summary.csv`, `reports/tables/paper1_c2_tokenised_tracking_baseline_per_symbol.csv`; full write-up: `reports/v1b_tokenised_tracking_baseline.md`.

### D.7.7 Matched calibration history — isolating architecture from history length

The D.7.3 head-to-head gives the deployed band a decisive structural advantage the reader should see named: it is calibrated on the full 2014–2026 artefact, while the tokenised baseline can only calibrate over the post-2025-12 live perp tape ($\le 19$ weekends per symbol). To separate the architecture from calibration-history length, we re-run both methods walk-forward on the *same* post-2025-12 window — refitting the deployed architecture (regime → per-symbol σ̂ → per-regime conformal quantile → σ̂·`fri_close` band) on only the calibration data available up to each evaluation weekend, exactly as the baseline does, on the common $n = 90$ cells (`scripts/run_v1b_tokenized_matched_history.py`; tables `reports/tables/v1b_tokenized_matched_history_{summary,deltas,per_symbol,regime_floor}.csv`). Two concessions keep the comparison apples-to-apples and are themselves findings: the OOS $c(\tau)$ / $\delta(\tau)$ conservatism layer is dropped (it needs a train/OOS split the short window cannot afford, and the baseline has no such layer), and the σ̂ warm-up is relaxed from $\ge 8$ to $\ge 4$ past observations (at $\ge 8$ the short window strands $24/117$ cells).

Deployed-vs-baseline deltas at $\tau = 0.95$ (`mon_open` snapshot, block-bootstrap 95% CI):

| calibration history | width reduction | Winkler improvement [95% CI] |
|---|---:|---:|
| frozen M6 (12 yr, re-scored on common $n=90$) | $43\%$ | $37.5\%\ [16.3, 51.8]$ |
| matched M6, regime ($\approx 4$ mo) | $26.7\%\ [14.9, 36.4]$ | $19.9\%\ [-1.5, 35.6]$ |
| matched M6, pooled ($\approx 4$ mo) | $29.6\%\ [18.4, 38.7]$ | $20.4\%\ [-2.0, 37.1]$ |

When calibration history is equalised, the width edge roughly halves ($43 \to 27$–$30\%$) and the **Winkler edge collapses from $\approx 38$–$46\%$ to $\approx 20\%$ with a 95% CI that spans zero** — Winkler is the coverage-fair arbiter, and it no longer distinguishes the architectures. The matched refit buys its remaining narrowness partly with lost coverage: it under-covers at $0.91$ vs frozen-M6's $0.96$ and the baseline's $0.94$. At $\tau = 0.99$ the edge *reverses* (matched-regime Winkler $-18\%$): the per-regime conformal quantile is $100\%$ saturated at every walk-forward step in all three regimes (it needs $\ge 99$ obs/cell; the largest cell reaches $63$), so the tail band is systematically too narrow and the tail claim is simply not identifiable on the equalised window. Per-symbol, the deployment "wins seven of nine" falls to **four of nine**: matched-M6 beats the baseline only on the thin/volatile perps — GOOGL ($2.7\times$), HOOD ($3.1\times$), NVDA ($1.5\times$), MSTR ($1.1\times$) — and loses on the deep-liquid core — SPY ($0.54\times$), QQQ ($0.61\times$), GLD ($0.68\times$), TSLA ($0.88\times$), AAPL ($0.95\times$) — where the perp tracks so tightly that a few-months-calibrated conformal band is wider than the baseline's empirical quantile.

**Verdict for §6.2.** The architecture advantage is real but much smaller than the deployment figure and confounded by coverage: roughly half to two-thirds of the $\tau = 0.95$ edge is the 12-year calibration record, not the architecture. The surviving architectural edge lives in the thin/volatile names — exactly where a lending consumer's closed-market risk concentrates — while the naive tracker is competitive-to-better on the liquid core. This is the empirical basis for the token-anchored hybrid named as future work (§9), and for the "data-hungry by construction" limitation (§8).

### D.7.8 Jupiter-mid (v5/tape) cross-check — directional confirmation on the Solana-DEX surface

The kraken_futures xstock-backed perp is the deepest tokenised-equity surface but is not the on-chain SPL token a Solana-DEX consumer actually reads. The `soothsayer_v5/tape` jup_mid series (Jupiter's quoted mid for eight Backed xStocks) is the directly Solana-DEX-relevant signal; overlap with the deployed LWC artefact is one weekend (2026-04-24), extended two weekends forward via a forward-tape-extended σ̂ lookup that re-uses the sidecar constants without re-fitting. Sample: 3 weekends × 8 symbols = $n = 24$. The baseline halfwidth is **borrowed verbatim** from the primary mon_open snapshot (no re-fit on the cross-check sample). The directional Winkler result reproduces — ratios baseline / M6 LWC at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ are $\{1.65, 2.09, 2.41, 2.11\}\times$. The ratio at $\tau = 0.95$ ($2.41\times$) is *wider* than the primary kraken_futures panel ($1.84\times$), consistent with Jupiter mid on Solana DEXs having a thinner, more dispersion-prone book than the deeper kraken_futures perp. Kupiec / Christoffersen are degenerate at $n = 24$ and we report only the Winkler / halfwidth axis. The cross-check is *confirmatory*, not powered. Source: `scripts/run_v1b_tokenised_tracking_v5_xcheck.py`; table `reports/tables/paper1_c2_tokenised_tracking_v5_xcheck.csv`.
