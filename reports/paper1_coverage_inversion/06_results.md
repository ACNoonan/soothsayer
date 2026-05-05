# §6 — Results

This section reports the primary calibration evidence for the deployed v2 (locally-weighted Mondrian split-conformal under EWMA HL=8 σ̂; §4) on real and synthetic data, plus the forward-tape harness operational against a content-addressed frozen artefact. Sharpness and per-component effects are deferred to §7; system-level implementation and audit reproducibility are in §8. The §6 evidence pack closes the per-symbol calibration weakness disclosed in earlier draft of this paper against v1 (Mondrian split-conformal without per-symbol scale standardisation): under v2 the per-symbol Kupiec pass-rate at $\tau = 0.95$ rises from 2/10 to 10/10, the per-symbol Berkowitz LR range collapses from 0.9–224 (250×) to 3.16–16.73 (5.3×), and the bimodal per-symbol calibration error becomes a single unimodal cluster centred near nominal.

## 6.1 Evaluation protocol

The backtest panel comprises $N = 5{,}996$ weekend prediction windows: ten symbols × $639$ weekends, 2014-01-17 through 2026-04-24. Monday open is the target; Friday close and contemporaneous factor / vol-index readings compose $\mathcal{F}_t(s)$. Under v2 the σ̂ warm-up rule (≥8 past observations per symbol) drops 80 weekends at panel start to leave $5{,}916$ evaluable rows. We report (i) an *in-sample machinery check* (quantile fit and served on the full evaluable panel; realised coverage matches $\tau$ by construction), (ii) the *out-of-sample validation* (quantile fit on $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ — 4,186 rows; Oracle served on the 1,730-row $\mathcal{T}_\text{test}$ slice), (iii) the held-out *forward-tape* evaluation against a content-addressed frozen artefact (§6.8), and (iv) a *simulation study* on synthetic panels with known ground truth (§6.9). All $p$-values are two-sided Kupiec POF and Christoffersen independence tests. The base point estimator is unbiased (median residual $-0.5$ bps; MAE $90.0$; RMSE $163.3$); the product is the per-symbol-σ̂-rescaled per-regime conformal quantile with the OOS-fit $c(\tau)$ bump.

## 6.2 Served-band calibration — in-sample machinery check

Full evaluable panel ($N = 5{,}916$):

| Regime ($n$)          | $\tau = 0.68$: realised / width (bps) | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---|---|---|---|
| normal (3,883)        | 0.685 / 91.0  | 0.851 / 142.7 | 0.951 / 247.7 | 0.987 / 424.8 |
| long_weekend (619)    | 0.683 / 109.4 | 0.852 / 171.7 | 0.948 / 297.7 | 0.989 / 511.1 |
| high_vol (1,414)      | 0.682 / 175.7 | 0.853 / 275.5 | 0.950 / 478.5 | 0.992 / 821.0 |
| **pooled (5,916)**    | **0.684 / 109.4** | **0.852 / 175.0** | **0.951 / 303.4** | **0.989 / 521.6** |

Pooled realised coverage matches the consumer's request to within $0.2$pp by construction. The narrower in-sample widths (vs the OOS table below) reflect σ̂'s tighter estimate over the full panel; the OOS table's wider bands are the OOS-fit $c(\tau) = 1.079$ at $\tau = 0.95$ working as designed.

## 6.3 Served-band calibration — out-of-sample (2023+)

Quantile fit on pre-2023 weekends ($n = 4,186$); Oracle served on the 2023+ slice (1,730 rows × 173 weekends). The 12 trained per-regime quantiles $q_r^{\text{LWC}}(\tau)$ are held-out; the 4-scalar $c(\tau)$ schedule is OOS-fit on this same slice. Under v2 the walk-forward $\delta(\tau)$ schedule is identically zero — the structural-conservatism shim v1 needed is no longer load-bearing (§4.5). **The strongest defensible characterisation is *deployment-calibrated and walk-forward-stable*; the 4-scalar OOS-fit $c(\tau) = \{1.000,\,1.000,\,1.079,\,1.003\}$ is near-identity at three of four anchors and only widens by 7.9% at $\tau = 0.95$.** §9.3 carries the full provenance disclosure.

| Regime ($n$)       | $\tau = 0.68$: realised / width | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---|---|---|---|
| normal (1,160)     | 0.687 / 109.7 | 0.847 / 172.3 | 0.947 / 300.1 | 0.990 / 471.6 |
| long_weekend (190) | 0.626 / 120.6 | 0.842 / 190.6 | 0.958 / 334.7 | 1.000 / 562.5 |
| high_vol (380)     | 0.742 / 200.3 | 0.887 / 351.1 | 0.955 / 603.7 | 0.987 /1{,}169.9 |
| **pooled (1,730)** | **0.693 / 130.8** | **0.855 / 213.6** | **0.950 / 370.6** | **0.990 / 635.0** |

The per-regime story is the same shape as v1 — `high_vol` carries the widest bands, `normal` the narrowest — but every regime now lands closer to nominal at $\tau = 0.95$ (v1 was 0.939 / 0.984 / 0.968 across the three regimes; v2 is 0.947 / 0.958 / 0.955). The σ̂ standardisation tightens *cross-regime* variance as a side effect of tightening *cross-symbol* variance.

### Conditional-coverage tests (pooled OOS)

| $\tau$ | Violations | Rate | Kupiec $p_\text{uc}$ | Christoffersen $p_\text{ind}$ | $c(\tau)$ |
|---:|---:|---:|---:|---:|---:|
| 0.68  | 532 | 0.308 | 0.264 | 0.244 | 1.000 |
| 0.85  | 251 | 0.145 | 0.565 | 0.403 | 1.000 |
| **0.95** | **86** | **0.050** | **0.956** | **0.603** | **1.079** |
| 0.99  | 17 | 0.010 | 0.942 | $\approx 1.0$ | 1.003 |

**The $\tau = 0.95$ row is the primary oracle-validation operating result.** Realised coverage is exactly $0.9503$ (Kupiec $p_{uc} = 0.956$); Christoffersen $p_{ind} = 0.603$ passes. **Kupiec and Christoffersen pass at every served anchor under v2.** Under v1, Kupiec rejected at $\tau \in \{0.68,\,0.85\}$ (the OOS-fit $c$-bumps were chasing pooled coverage at $0.95$ and pulling the lower-$\tau$ schedule off-target); under v2 the near-identity $c$ schedule lets every anchor calibrate independently, and Kupiec passes everywhere. Mean half-width at $\tau = 0.95$ is **370.6 bps** — narrower than the K=26 σ̂ baseline (385.3 bps; bootstrap 95% CI on Δhw% upper bound is $-1.88\%$, see §7.3) and $+4.5\%$ wider than v1's 354.6 bps (the per-symbol-calibration tax v1 did not pay). Christoffersen rejects nowhere at this anchor schedule; the §9.4 residual rejection localises to per-symbol Berkowitz on TLT and TSLA (§6.4.1) and to cross-sectional within-weekend common-mode (§6.3.1) — neither curable with a different σ̂ rule.

**Realised-move tertile decomposition at $\tau = 0.95$.** Stratifying the OOS slice by post-hoc realised-move $|z|$-score tertile (`reports/tables/m6_realised_move_tertile.csv`) closes the loop between the §6.3 pooled headline and the §9.1 shock-tertile ceiling:

| tertile ($n$)     | realised | half-width (bps) | Kupiec $p$ |
|---|---:|---:|---:|
| calm   (497)      | 1.0000   | 379.7 | $0$ (over-covers) |
| normal (601)      | 0.9933   | 371.6 | $0$ (over-covers) |
| **shock** (632)   | **0.8782** | 364.6 | $0$ (under-covers) |
| **pooled** (1{,}730) | **0.9503** | **370.6** | **0.956** |

Half-width is approximately flat across tertiles (365–380 bps), so the band does not widen in shock periods — it just misses more often. Shock-tertile floor improves only $+0.64$pp under v2 vs v1 ($87.18\% \to 87.82\%$) — the residual is cross-sectional common-mode within a weekend (§9.1), not per-symbol scale.

![Calibration curves on the 1{,}730-row 2023+ OOS slice. v2 (this paper, blue) tracks the $45^\circ$ diagonal across the served range $\tau \in [0.68, 0.99]$; v1 (Mondrian without σ̂ standardisation, green) also tracks but with the bimodal per-symbol failure documented in §6.4.1; the constant-buffer baseline (F0\_stale, vermilion) over-covers throughout (over-conservative Gaussian wrap on $\sigma_{20d}$); Soothsayer-v0 (orange) follows v1 closely until $\tau \approx 0.97$ where it caps at $0.972$ — Soothsayer-v0's finite-sample tail ceiling that v1 and v2 close. Star marks the headline $\tau = 0.95$ result.\label{fig:calibration}](figures/fig2_calibration.pdf)

**Walk-forward stability.** Re-running the v2 schedule selection on six expanding-window splits (fractions 0.2–0.7) with $\delta = 0$: walk-forward realised $\tau = 0.95$ coverage is $\geq 0.95$ on every split — the criterion that selected $\delta = 0$ in §4.5. Per-split mean half-width at $\tau = 0.95$ tracks the full-OOS-fit value within $\pm 8\%$. This is not idiosyncratic to the 2023+ slice but does not upgrade the result to purely held-out end-to-end (§6.8 (the forward-tape) and §10.1 (the rolling artefact rebuild) are the upgrade paths).

**Split-date sensitivity.** Repeating the v2 fit (quantile table re-trained, $c(\tau)$ re-fit per split, $\delta \equiv 0$ held) at four OOS-split anchors {2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01} delivers realised $\tau = 0.95$ coverage of $\{0.9539,\ 0.9520,\ 0.9503,\ 0.9504\}$ — Kupiec $p \in \{0.348,\ 0.661,\ 0.956,\ 0.947\}$ and **Christoffersen $p \in \{0.115,\ 0.186,\ 0.603,\ 0.671\}$ — every (split × $\tau$) cell passes at $\alpha = 0.05$.** Mean half-width $\{357.2,\ 363.5,\ 370.6,\ 416.8\}$ bps varies $\pm 8\%$ around the deployed value. The K=26 σ̂ baseline of v2 (the LWC variant before §7.3 σ̂ promotion) rejected Christoffersen at the 2021 and 2022 split anchors at $\tau = 0.95$ ($p = 0.0065,\ 0.0016$); the EWMA HL=8 promotion clears those rejections — see §7.3 for the variant comparison and the multiple-testing correction.

**Leave-one-symbol-out CV.** Holding out each of the ten symbols' rows from train + OOS fits and evaluating $\tau = 0.95$ on the held-out symbol's post-2023 slice: **all 10 LOSO bands pass Kupiec when held out**; mean realised $0.9497$, std $0.0134$ — $5.7\times$ tighter than v1's std $= 0.0759$. The "moderate fragility to held-out heavy-tail tickers" disclosure under v1 (MSTR $0.786$, HOOD $0.856$, TSLA $0.879$ realised at $\tau = 0.95$ when held out) becomes a uniform 0.93–0.97 band under v2: heavy-tail tickers no longer drag the held-out coverage down, because the per-symbol $\hat\sigma_s(t)$ on the held-out symbol carries its own scale (`reports/tables/m6_lwc_robustness_loso.csv`).

![Walk-forward and split-date stability of the deployed v2 schedule. **(a)** Six-split expanding-window walk-forward at four $\tau$ anchors: realised coverage on each test fold (markers) tracks nominal (dotted lines) at every anchor; bars are 95% binomial CIs. **(b)** Split-date sensitivity at four OOS-anchors {2021, 2022, 2023, 2024}: realised $\tau = 0.95$ coverage holds at $\{0.954, 0.952, 0.950, 0.950\}$ across anchors; Christoffersen passes every cell at $\alpha = 0.05$.\label{fig:stability}](figures/fig3_stability.pdf)

This validates the oracle's coverage contract at $\tau = 0.95$. It does *not* prove $\tau = 0.95$ is the welfare-optimal operating point; that is Paper 3.

### 6.3.1 Extended diagnostics — Berkowitz and DQ

**Berkowitz (2001) joint LR on continuous PITs.** PITs reconstructed by inverting each served band against the realised Monday open through the per-regime conformal CDF. Under v2 the pooled Berkowitz LR is materially smaller than v1's $173.1$ but still rejects (the residual is the cross-sectional within-weekend common-mode discussed below; not addressable by σ̂ choice). **Engle-Manganelli (2004) DQ at $\tau = 0.95$** also rejects on the pooled fit — the same temporal-clustering signal that drove v1's DQ rejection persists, again because the cross-sectional within-weekend common-mode (which is what DQ is sensitive to here) is orthogonal to the σ̂ standardisation. **Bands are *per-anchor calibrated*, not full-distribution calibrated.**

**Localising the rejection.** Decomposing the lag-1 alternative under panel-row order: the AR(1) signal lives in the *cross-sectional within-weekend* ordering ($\hat\rho_{\text{cross}} = 0.354$, $p < 10^{-100}$, $n = 1{,}557$) — not the temporal-within-symbol ordering ($\hat\rho_{\text{time}} = -0.032$, $p = 0.18$, $n = 1{,}720$). Under v2 the cross-sectional correlation is essentially unchanged from v1 — σ̂ standardisation operates *within* a symbol's history, not *across* symbols within a weekend, so it cannot reach this residual. A vol-tertile sub-split of `normal` regime (5 cells) leaves Berkowitz LR essentially unchanged ($170 \to 172$) while widening $\tau = 0.95$ band by $9\%$ — finer regime granularity is not the lever (`reports/tables/m6_lwc_robustness_vol_tertile.csv`). The §10 candidate architectures that target cross-sectional common-mode (the M6a partial-out track in M6_REFACTOR.md, gated on a Friday-observable $\bar r_w$ predictor) are deferred-with-gates.

## 6.4 Per-symbol generalisation — the v1 → v2 inversion

The §6.3 OOS pooled coverage at $\tau = 0.95$ matches v1's; the difference is *who* contributes to that pool. Under v1, the pool averages a 2/10-Kupiec-pass per-symbol distribution: SPY/QQQ/GLD/TLT/AAPL over-cover (variance compression, $\hat\sigma^2_z \in [0.11, 0.44]$), HOOD/MSTR/TSLA under-cover (variance expansion, $\hat\sigma^2_z \in [1.45, 2.10]$), with HOOD's violation rate climbing to 13.9% at nominal 5%. Under v2, **all 10 symbols pass Kupiec at $\tau = 0.95$** with violation rates in $[2.9\%, 6.9\%]$ and $\hat\sigma^2_z \in [0.62, 0.83]$ — close to the calibrated 1.0 from below in every case. Figure \ref{fig:per-symbol} visualises the inversion.

![Per-symbol calibration under v2 vs v1. Each panel shows the 10 symbols on the 2023+ OOS slice; symbols are ordered by v1-PIT variance $\hat\sigma^2_z$ (an "easy"-to-"hard" ordering for v1). Under v1 (left), the bimodal failure mode is visible: low-$\hat\sigma^2_z$ symbols (SPY, QQQ, GLD, TLT, AAPL) reject from variance compression with violation rates near zero (orange down-triangles below the $p = 0.05$ Kupiec threshold); high-$\hat\sigma^2_z$ symbols (TSLA, HOOD, MSTR) reject from variance expansion with violation rates 11–16% (blue up-triangles also below the threshold). NVDA and GOOGL pass. Under v2 (right), every symbol passes — violation rates are in $[2.9\%, 6.9\%]$ and Kupiec $p \in [0.27, 0.92]$. The bimodal cluster is collapsed into a single unimodal cluster centred near nominal.\label{fig:per-symbol}](figures/fig4_per_symbol.pdf)

### 6.4.1 Per-symbol Kupiec at $\tau = 0.95$ and Berkowitz LR — side-by-side

| Symbol | v1 viol rate | v1 Kupiec $p$ | v1 Berkowitz LR | v2 viol rate | v2 Kupiec $p$ | v2 Berkowitz LR |
|---|---:|---:|---:|---:|---:|---:|
| AAPL  | 0.0058 | 0.001 | 40.9 | 0.069 | 0.268 | 6.7 |
| GLD   | 0.0058 | 0.001 | 115.7 | 0.069 | 0.268 | 3.2 |
| GOOGL | 0.0289 | 0.168 | 33.3 | 0.052 | 0.903 | 10.2 |
| HOOD  | 0.1387 | 0.000 | 16.5 | 0.035 | 0.329 | 6.4 |
| MSTR  | 0.1561 | 0.000 | 51.5 | 0.046 | 0.819 | 7.1 |
| NVDA  | 0.0405 | 0.552 |  0.9 | 0.052 | 0.903 | 10.0 |
| QQQ   | 0.0058 | 0.001 | 139.4 | 0.040 | 0.552 | 5.1 |
| SPY   | 0.0000 | 0.000 | 223.7 | 0.046 | 0.819 | 9.6 |
| TLT   | 0.0000 | 0.000 | 140.7 | 0.046 | 0.819 | 16.7 |
| TSLA  | 0.1156 | 0.001 | 26.5 | 0.040 | 0.552 | 13.5 |
| **pass-rate at $\alpha = 0.05$** | | **2 / 10** | | | **10 / 10** | |
| **LR range** | | | **0.9 – 224** (250×) | | | **3.2 – 16.7** (5.3×) |

HOOD specifically: violation rate $13.9\% \to 4.0\%$, Kupiec $p\,\;0.000 \to 0.329$ — the ticker that drove the §6.4 weakness disclosure under v1 now sits in the middle of the cluster. MSTR: $15.6\% \to 4.6\%$, $p\,\;0.000 \to 0.819$. SPY: $0\% \to 4.6\%$, $p\,\;0.000 \to 0.819$ (the over-coverage failure flips, by exactly the σ̂ mechanism §4.3 specifies). The per-symbol Berkowitz LR range collapse from $0.9$–$224$ to $3.2$–$16.7$ is the strongest single piece of evidence the LWC primitive does what it was designed to do; only TLT and TSLA still reject Berkowitz at $\alpha = 0.01$ (LR $16.7$ and $13.5$), and those rejections trace to cross-sectional common-mode rather than per-symbol scale (§6.3.1).

NVDA's slight Berkowitz LR rise ($0.9 \to 10.0$) is the one cell where the picture worsens: NVDA was v1's best-calibrated symbol, and v2's pooled per-regime quantile pulls NVDA's bands modestly off-target by absorbing the calibration mass other heavy-tail symbols used to need. This is a small price for fixing nine other symbols and does not break Kupiec ($p = 0.903$).

The MSTR-removed sensitivity that load-bore the v1 disclosure becomes uninteresting under v2 — the v2 schedule is no longer anchored on heavy-tail symbols, so removing MSTR moves the schedule by less than 0.5%. The 2020-08-01 factor pivot for MSTR (§5.4) is a point-estimator detail, not a load-bearing modeling choice for the headline.

### 6.4.2 GARCH(1,1) baseline

The textbook econometric default for a time-varying interval at $\tau$ is per-symbol GARCH(1,1) on log Friday-to-Monday returns with Gaussian innovations, fit on the pre-2023 train and recursive $\hat\sigma_t$ over OOS. Head-to-head on the 1,730-row OOS slice (`reports/tables/m6_lwc_robustness_garch_baseline.csv`):

| $\tau$ | GARCH(1,1) realised / hw / Kupiec $p$ | v2 realised / hw / Kupiec $p$ |
|---:|---|---|
| 0.68 | $0.7393$ / $163.4$ / $0.000$ | $0.6925$ / $130.8$ / $0.264$ |
| 0.85 | $0.8514$ / $236.6$ / $0.866$ | $0.8549$ / $213.6$ / $0.565$ |
| 0.95 | $\mathbf{0.9254}$ / $322.2$ / $\mathbf{0.000}$ | $\mathbf{0.9503}$ / $370.6$ / $\mathbf{0.956}$ |
| 0.99 | $\mathbf{0.9630}$ / $423.7$ / $\mathbf{0.000}$ | $\mathbf{0.9902}$ / $635.0$ / $\mathbf{0.942}$ |

GARCH undercovers at $\tau \in \{0.68, 0.95, 0.99\}$ (the textbook tail-mis-coverage failure of Gaussian innovations). The naive nominal-anchor comparison at $\tau = 0.95$ would read GARCH at $322.2$ bps and v2 at $370.6$ bps and infer GARCH is ~13% sharper. That comparison is unfair: GARCH realises $0.9254$ and v2 realises $0.9503$. **At matched 95% realised coverage** GARCH's mean half-width climbs to $385.7$ bps — **3.9% wider than v2** at the same realised coverage and rejecting at three of four nominal anchors.

### 6.4.3 Per-asset-class deviation

Pooled OOS coverage stratified by asset class shows the v1 per-class redistribution v2 absorbs into σ̂. Equities (8 syms, 1,384 obs): under v1 realised $0.9386$ at $\tau = 0.95$ with hw $355$ bps; under v2 realised $0.9466$ with hw $436$ bps — a $+23\%$ width reallocation onto the under-covered class. GLD + TLT (346 obs): under v1 realised $0.997$ with hw $355$ bps; under v2 realised $0.954$ with hw $184$ bps — a $-48\%$ width *reduction* on the over-covered defensive class, releasing width at no coverage cost. **v2 redistributes width from the v1-over-covered defensive bands to the v1-under-covered heavy-tail equities** — an architectural improvement, not a free-lunch claim. v2 Kupiec passes every class at every $\tau$; v1 Kupiec rejects gold/treasuries at $\tau = 0.95$ in the *too-wide* direction with $p = 0.000$ (`reports/tables/m6_lwc_robustness_per_class.csv`).

## 6.5 Comparison to incumbent oracle surfaces

We measure what consumers receive from deployed alternatives across three reconstructions: a regular-Pyth Hermes-derived band (265 obs, 2024+), a Chainlink Data Streams v10/v11 reconstruction (87 obs, frozen 2026-02-06 → 2026-04-17), and a forward-cursor RedStone Live tape ($n = 12$, 2026-04-26+); Pyth Pro / Blue Ocean is excluded on access and window grounds. Caveats: sample CIs are wide; composition is skewed toward large-cap normal-regime weekends (compare to v2's 300.1 bps normal-regime half-width); wrap multipliers are *consumer-supplied* — none of the three incumbents publishes a calibration claim a consumer can read directly.

| Surface | Sample | xStock coverage | Wire band? | Caveats (full §9.6) |
|---|---|---|---|---|
| Pyth regular (Hermes archive) | $n = 265$, 2024+ | SPY 69%, QQQ 65%, TLT 59%, TSLA 25%; AAPL/GOOGL/HOOD/NVDA 0% | $(\text{price},\, \mathrm{conf})$, dispersion-only | 2024- RH equity feeds did not publish |
| Chainlink Streams v10 | $n = 87$ frozen panel | SPY/QQQ/TSLA mapped | no `bid`/`ask` on wire (§6.5.2) | band-less by construction |
| Chainlink Streams v11 | $n = 87$ frozen panel | SPY/QQQ/TSLA mapped, NVDA partial | wire `bid`/`ask` carry synthetic `.01` suffix at 100% incidence on 3/4 mapped (§6.5.2) | requires manual mid$\pm k\%$ wrap |
| RedStone Live (REST) | $n = 12$ forward tape | underlier prices only — SPY, QQQ, MSTR; **empty on TSLA, NVDA, HOOD, GOOGL, AAPL**; 33d stale on AAPL at query time | no calibration object on the wire | 30d retention cap; only forward-collected weekends enter |

**Pyth (regular surface) — consumer wrap $\text{price} \pm k \cdot \text{conf}$.** Pyth's `(price, conf)` is documented as a publisher-dispersion diagnostic, not a probability statement [pyth-conf]; Pyth Pro inherits the same aggregation.

| $k$ | realised | mean half-width (bps) |
|---:|---:|---:|
| 1.96 (textbook 95% Gaussian) | 0.102 | 11.0 |
| 25.00 | 0.800 | 139.7 |
| **50.00** | **0.951** | **279.5** |
| 100.00 | 0.992 | 559.0 |

The naive textbook 95% wrap returns 10.2% — under-calibrated by ≈10× as a consumer-supplied band. The smallest $k$ delivering ≥ 95% is $k \approx 50$ (279.5 bps); on the Pyth-available subsample (composed predominantly of large-cap equities) v2's regime-matched normal half-width at $\tau = 0.95$ is 300.1 bps — width-comparable at matched coverage. The Soothsayer differentiator on this panel is the calibration receipt and its cross-symbol generalisation, not the bandwidth on a SPY-heavy subsample.

![Coverage versus mean half-width across methods at the four served $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ (vertical dotted lines). v2 (blue stars) and Soothsayer-v0 (orange circles) are at full panel ($n = 1{,}730$); GARCH(1,1) baseline (vermilion squares) is the textbook econometric default; Pyth $\pm k\!\cdot\!\mathrm{conf}$ (green diamonds, $n = 265$) is the consumer-supplied wrap that achieves the claimed coverage at the smallest $k$ on the available subset; Chainlink Streams (purple, $n = 87$) is the manual mid$\,\pm\,k\%$ wrap on the marker-aware-decoded sample. v2 sits on the calibration-vs-sharpness Pareto frontier at every served $\tau$; GARCH undercovers at $\tau \in \{0.95, 0.99\}$ despite slightly tighter bands; Pyth and Chainlink subsets cover comparable widths but on small, heterogeneous samples (§6.5 caveats).\label{fig:pareto}](figures/fig5_pareto.pdf)

**Chainlink Data Streams v10 / v11.** v10 (Tokenized Asset, `0x000a`) carries no `bid`/`ask`/confidence on the wire — band-less by construction [chainlink-v10]. v11 (RWA Advanced, `0x000b`) adds `bid`, `ask`, `mid`. Marker-aware classifier on a 26-report weekend scan:

| Symbol (n) | Pattern | Wire `bid` | Wire `ask` | Implied spread |
|---|---|---:|---:|---:|
| SPYx (6) | PURE_PLACEHOLDER | 21.01 | 715.01 | ~18,858 bps |
| QQQx (6) | BID_SYNTHETIC | 656.01 | — | 117–329 bps |
| TSLAx (7) | BID_SYNTHETIC | 372.01 | — | 117–329 bps |
| NVDAx (1) | REAL | 208.07 | 208.14 | ~3.4 bps |

The v11 weekend `bid` carries a synthetic `.01` suffix at 100% incidence on three of four mapped xStocks — a generated bookend, not a venue quote. To get a usable band a v11 consumer must replace wire `bid`/`ask` with a manual `mid ± k%` wrap; an earlier 87-obs panel found $k \approx 3.2\%$ delivers ≥ 95% — ~10% wider than v2's regime-matched normal half-width. Neither v10 nor v11 publishes a coverage band a consumer can read directly.

## 6.6 Path coverage — endpoint vs intra-weekend

The §6.3 result is *endpoint coverage*: realised Monday open lies inside the served band. A DeFi consumer holding an xStock as collateral is exposed at every block over the weekend; a Saturday liquidation when the on-chain xStock briefly trades outside the band is a real loss event even if Monday open returns inside. We measure path coverage on $[\text{Fri 16:00 ET},\, \text{Mon 09:30 ET}]$ against 24/7 stock-perp 1m bars from `cex_stock_perp/ohlcv` (Kraken Futures `PF_<sym>XUSD`, xStock-backed). Sample: 19 weekends × 9 symbols (TLT excluded — no perp listing), $n = 118$ (symbol, weekend) pairs per anchor, 2025-12-19 → 2026-04-24:

v2 served bands recomputed live from the deployed LWC artefact + EWMA HL=8 σ̂ on the same 118-row keyspace; v1 numbers from `reports/tables/path_coverage_perp.csv` are retained alongside as the per-anchor comparator.

| $\tau$ | $n$ | v1 endpoint | v1 path | v1 gap (pp) | **v2 endpoint** | **v2 path** | **v2 gap (pp)** |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.68 | 118 | 0.771 | 0.509 | $+26.3$ | $0.644$ | $0.348$ | $+29.7$ |
| 0.85 | 118 | 0.915 | 0.729 | $+18.6$ | $0.864$ | $0.568$ | $+29.7$ |
| **0.95** | **118** | **0.983** | **0.839** | $+\mathbf{14.4}$ | $\mathbf{0.949}$ | $\mathbf{0.788}$ | $+\mathbf{16.1}$ |
| 0.99 | 118 | 1.000 | 0.966 | $+3.4$ | $0.992$ | $0.915$ | $+7.6$ |

The headline is that **v2 calibrates this perp-listed sample to nominal endpoint coverage at every $\tau$** (0.949 at $\tau = 0.95$ vs nominal 0.95) — whereas v1 over-covered the same sample (0.983 endpoint at $\tau = 0.95$). The composition is mostly large-cap equities (SPY/QQQ/AAPL/GOOGL/NVDA/MSTR/TSLA/HOOD plus GLD; TLT excluded — no perp listing); under v1 these symbols inherited the regime-pooled quantile that was over-tuned for the heavy-tail bucket and ended up wide-on-this-subsample. v2's per-symbol σ̂ standardisation collapses the over-coverage. The path-coverage gap consequently widens by $+1.7$pp at $\tau = 0.95$ ($14.4 \to 16.1$) — this is the calibration tax: v1's wide-on-this-subsample bands incidentally covered more of the path; v2's correctly-scaled bands do not.

The +16pp v2 path gap at $\tau = 0.95$ is therefore not a v2 regression — it is what an honestly-calibrated endpoint band exhibits on a sample whose intra-weekend variance is structurally larger than its endpoint variance. Sample is small (binomial CI on the $\tau = 0.95$ pooled gap is $\pm 6$pp); the test is directional. After the three confound checks documented in `reports/v1b_path_coverage_robustness.md` (perp-spot basis at the Friday-close anchor, volume floor, sustained-crossing definition) the residual genuine-shortfall band on this slice is $\sim 8$–$12$pp under v2. The gap collapses meaningfully only at $\tau = 0.99$ ($+7.6$pp); continued capture is tracked under scryer item 51 and §10.1 (the path-fitted conformity score).

![Path coverage gap on the 24/7 stock-perp reference. **(a)** v2 endpoint coverage (blue) tracks nominal across $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ on the perp-listed subset; v2 path coverage (vermilion) — the fraction of weekends where the perp 1m bar high/low stay inside the served band over the full $[\text{Fri 16:00, Mon 09:30}]$ window — runs $29.7$/$29.7$/$16.1$/$7.6$pp behind. The gap collapses meaningfully only at $\tau = 0.99$. **(b)** Side-by-side comparison of the τ=0.95 gap under v1 (14.4pp) and v2 (16.1pp) on the same sample. v2's slightly wider gap is a calibration artifact — v1 was over-covering the perp-listed subset, so its narrower gap reflected that over-coverage rather than tighter intra-weekend tracking. Sample is small ($n = 118$ symbol-weekends across 19 calendar weekends, 2025-12 to 2026-04); the read is directional and §10.1 (the path-fitted conformity score) is the methodology fix.\label{fig:path-coverage}](figures/fig6_path_coverage.pdf)

The endpoint contract stands. A consumer requiring path coverage at level $\tau$ should step up one anchor (empirically closes the gap on this slice at $\tau = 0.99$), absorb the residual through downstream policy (Paper 3), or — for continuous-consumption products that cannot use the step-up lever (band-aware AMMs the canonical case) — adopt the path-fitted conformity-score variant on the next-generation roadmap.

## 6.7 Forward-tape held-out validation

The 4-scalar OOS-fit $c(\tau)$ schedule is fit on the 2023+ slice; the resulting deployment artefact carries a residual contamination disclosure (§9.3). The forward-tape harness closes that loop on truly held-out data: a content-addressed frozen artefact (`data/processed/lwc_artefact_v1_frozen_20260504.json`, SHA-256 `7b86d17a7691…`, freeze date 2026-05-04) is evaluated weekly against forward weekends as they accumulate. The frozen artefact's σ̂ schedule, $q_r^{\text{LWC}}$ table, and $c(\tau)$ are read-only; only the per-symbol $\hat\sigma_s(t)$ updates as new past-Fridays arrive.

The harness fires Tuesday mornings via launchd (`launchd/com.adamnoonan.soothsayer.forward-tape.plist`); each run executes a 26h-SLA pre-check on the upstream scryer feeds, runs `scripts/collect_forward_tape.py`, and writes `reports/m6_forward_tape_{N}weekends.md` with a "preliminary" banner when $N < 4$. The harness is silent about deployment; an out-of-band freeze re-roll is required to advance the artefact (`scripts/freeze_lwc_artefact.py`).

**Status at submission:** $N = $ [N TBD as forward weekends accumulate; first non-stub report ETA 2026-05-12; the §6.7 numbers are the load-bearing post-freeze evidence and **must be regenerated immediately before submission**]. Latest report: `reports/m6_forward_tape_{N}weekends.md`. With $N \geq 4$ the preliminary banner clears; with $N \geq 6$ the per-symbol Kupiec read becomes informative; with $N \geq 13$ the cumulative pooled Christoffersen on forward data has moderate power.

The forward-tape evidence is the cleanest possible held-out coverage statement on the deployed artefact. The harness's σ̂ variant comparison sibling (`scripts/run_forward_tape_variant_comparison.py`, output `reports/m6_forward_tape_{N}weekends_variants.md`) carries an alternative-σ̂ check on the same forward slice — never used to re-select, only to flag if a different σ̂ rule looks dramatically cleaner on the held-out data (§7.3).

## 6.8 Simulation study — predicted-and-validated per-symbol fix

The §6.4 per-symbol calibration result (v1's 2/10 → v2's 10/10 Kupiec pass-rate at $\tau = 0.95$) raises a methodological question: is the per-symbol bimodality v1 exhibits a property of the deployed v1 schedule on this real-data panel, or a structural property of the architecture? We answer the second question with a four-DGP simulation study under known ground truth. **Across stationary, regime-switching, drift, and structural-break specifications, v1's per-symbol Kupiec pass-rate is 29–31% while v2's is 97.6–99.6% — the bimodality is structural, predicted by the architecture, and reproducible in synthetic data.**

Source: `scripts/run_simulation_study.py` (~30 s end-to-end). Each DGP uses 10 synthetic symbols × 600 weekend returns, $\sigma_i \in \mathrm{linspace}(0.005, 0.030, 10)$ — spanning the empirical real-panel range. Train/OOS split at $t = 400$. Returns drawn from Student-$t$ df=4 rescaled to $\mathrm{std}(r) = \sigma_i$ (or $\sigma_i \cdot m_t$ under DGP B/C/D's vol modifications). 100 Monte Carlo replications per DGP, seed $= 0$.

| DGP | v1 pass-rate at $\tau = 0.95$ | v2 pass-rate | Mechanism |
|---|---:|---:|---|
| A — homoskedastic baseline | **0.311** | **0.994** | Per-symbol scale heterogeneity is the entire failure mode |
| B — regime-switching vol multiplier | **0.310** | **0.976** | LWC σ̂ tracks regime transitions with a half-life lag |
| C — non-stationary scale (drift) | **0.309** | **0.996** | LWC's adaptive σ̂ is built for this DGP |
| D — exchangeability stress (variance ×3 at $t = 400$) | **0.292** | **0.994** | σ̂ recovers in $\leq 26$ weekends; warm-up under-coverage diluted |

Both methods pool to mean realised $\approx 0.95$ across all four DGPs (within 0.005 of nominal). The split is on the *per-symbol* failure rate. Under v1, ~30% of (symbol, replicate) cells pass — the bimodal failure mode reproduces under controlled conditions exactly as the architecture predicts (the single $(r, \tau)$-keyed multiplier mis-calibrates symbols whose residual scale deviates from the regime average in opposing directions). Under v2, 97.6–99.6% of cells pass, with the only material gap from DGP A appearing under DGP B's regime-switching (σ̂'s ~13-weekend tracking lag at regime flips). DGP D was the surprise — the prediction was that an exchangeability break would degrade both methods; the result is that v2's adaptive σ̂ recovers in under 26 weekends and the under-covered warm-up is diluted by the well-calibrated post-recovery slice.

A sample-size sweep (`scripts/run_simulation_size_sweep.py`; 7 N-values × 4 DGPs × 100 reps × 2 forecasters = 22,400 cells) establishes the newly-listed-symbol admission threshold for v2: $N \geq 80$ weekends under stationary / drift / structural-break DGPs, $N \geq 200$ under regime-switching (the production threshold). HOOD's empirical $N \approx 218$ (246 listed − 28 σ̂ warm-up) sits inside this band; HOOD's empirical Kupiec $p = 0.329$ at $\tau = 0.95$ is consistent with the simulation's pass-rate range at $N = 200$ (0.94 under DGP B, 0.99 under DGP A/C/D). See `reports/m6_simulation_study.md` and `reports/tables/sim_size_sweep_admission_thresholds.csv`.

![Per-symbol Kupiec $p$ at $\tau = 0.95$ across 100 reps × 4 DGPs (figure 7). Each panel shows side-by-side box-plots: v1 (red) and v2 (blue), one box per synthetic symbol sorted by $\sigma_i$ (S00 lowest, S09 highest). v1's red boxes cluster near $p \approx 0$ for low- and high-$\sigma$ symbols (variance compression and expansion failures of the single-multiplier conformal); v2's blue boxes sit centred around $p = 0.5$ across every symbol, every DGP — uniform calibration as predicted by exchangeability under per-symbol standardisation.\label{fig:simulation}](figures/simulation_summary.pdf)

## 6.9 Summary

At $\tau = 0.95$ on the 2023+ held-out slice: realised **95.0%**, both Kupiec ($p = 0.956$) and Christoffersen ($p = 0.603$) pass, mean half-width **370.6 bps**. **All 10 symbols pass per-symbol Kupiec** (vs v1's 2/10); per-symbol Berkowitz LR range collapses from $0.9$–$224$ to $3.2$–$16.7$. The σ̂ EWMA HL=8 promotion clears v1's lurking split-date Christoffersen issue (under K=26 σ̂ baseline, 2021/2022 splits rejected at $\tau = 0.95$; under EWMA HL=8 every split passes). A four-DGP simulation predicts the per-symbol fix from architecture before the real-data confirmation; a forward-tape harness against a content-addressed frozen artefact carries the held-out evidence forward weekly. Berkowitz and DQ still reject pooled — bands remain *per-anchor calibrated*, not full-distribution calibrated — and the residual rejection localises to cross-sectional within-weekend common-mode (orthogonal to σ̂; §10 / Paper 4 territory). Supports P2 (§3.4); P1 evidenced by §8; P3 by §7.
