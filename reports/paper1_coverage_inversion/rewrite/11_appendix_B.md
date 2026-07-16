# Appendix B — Full validation battery

<!-- Assembled 2026-07-16 per DISPOSITION.md Appendix B rows (Slices C/D/E/G/H).
     Sources: 06_results.md (corrected 2026-07-16), 05_data_and_regimes.md §5.5,
     09_limitations.md §9.2/§9.3/§9.5.1, 12_appendix_reproducibility.md A.9,
     case_study_boj_m6.md (M6 re-run; the v1-era case study is cited nowhere).
     Tables and numbers verbatim from source; connective prose updated to the
     §1–§9 / App A–F / H1–H5, S1–S2 numbering. -->

This appendix carries the complete validation battery behind §6 and §8. The main text states the claims and the numbers that support them; this appendix walks the protocol, the full tables, and the diagnostics they are drawn from. Every table is emitted by a runner listed in A.3/A.5 and is reproducible from public data.

## B.1 Evaluation protocol detail

The primary backtest panel comprises $N = 5{,}996$ weekend prediction windows: ten symbols × $639$ weekends, 2014-01-17 through 2026-04-24 (the overnight panel of §6.4 / B.15 — $22{,}624$ rows on the same symbols — is constructed identically bar the gap selector; §5.2). Monday open is the target; Friday close and contemporaneous factor / vol-index readings compose $\mathcal{F}_t(s)$. The σ̂ warm-up rule (≥8 past observations per symbol) drops 80 rows at panel start to leave $5{,}916$ evaluable rows.

Four evaluation modes are reported: (i) an *in-sample machinery check* (quantile fit and served on the full evaluable panel; realised coverage matches $\tau$ by construction — B.2), (ii) the *out-of-sample validation* (quantile fit on $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ — 4,186 rows; served on the 1,730-row $\mathcal{T}_\text{test}$ slice — B.3 onward), (iii) the held-out *forward-tape* evaluation against a content-addressed frozen artefact (§5.8, A.9), and (iv) a *simulation study* on synthetic panels with known ground truth (Appendix C). All $p$-values are two-sided Kupiec POF (proportion-of-failures) and Christoffersen independence tests. The base point estimator is unbiased (median residual $-0.5$ bps; MAE $90.0$; RMSE $163.3$); the product is the per-symbol-σ̂-rescaled per-regime conformal quantile with the OOS-fit $c(\tau)$ bump.

## B.2 In-sample machinery check

Full evaluable panel ($N = 5{,}916$):

| Regime ($n$)          | $\tau = 0.68$: realised / width (bps) | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---|---|---|---|
| normal (3,883)        | 0.685 / 91.0  | 0.851 / 142.7 | 0.951 / 247.7 | 0.987 / 424.8 |
| long_weekend (619)    | 0.683 / 109.4 | 0.852 / 171.7 | 0.948 / 297.7 | 0.989 / 511.1 |
| high_vol (1,414)      | 0.682 / 175.7 | 0.853 / 275.5 | 0.950 / 478.5 | 0.992 / 821.0 |
| **pooled (5,916)**    | **0.684 / 109.4** | **0.852 / 175.0** | **0.951 / 303.4** | **0.989 / 521.6** |

Pooled realised coverage matches the target $\tau$ to within $0.2$pp by construction. The narrower in-sample widths (vs the OOS table in B.3) reflect σ̂'s tighter estimate over the full panel; the OOS table's wider bands reflect the OOS-fit $c(\tau) = 1.079$ at $\tau = 0.95$.

## B.3 Out-of-sample per-regime coverage (2023+)

Quantile fit on pre-2023 weekends ($n = 4{,}186$); served on the 2023+ slice (1,730 rows × 173 weekends). The 12 trained per-regime quantiles $q_r(\tau)$ are held-out. The 4-scalar $c(\tau)$ schedule is OOS-fit, but the $\tau = 0.95$ headline is held out on two orthogonal axes — temporally via the nested TUNE/EVAL split and on symbol via leave-one-symbol-out CV (§6.1; detail in B.6) — both of which evaluate $c(0.95)$ on data its fit never touched. The walk-forward $\delta(\tau)$ schedule is identically zero (§4.5). B.7 carries the residual provenance disclosure.

| Regime ($n$)       | $\tau = 0.68$: realised / width | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---|---|---|---|
| normal (1,160)     | 0.687 / 109.7 | 0.847 / 172.3 | 0.947 / 300.1 | 0.990 / 471.6 |
| long_weekend (190) | 0.626 / 120.6 | 0.842 / 190.6 | 0.958 / 334.7 | 1.000 / 562.5 |
| high_vol (380)     | 0.742 / 200.3 | 0.887 / 351.1 | 0.955 / 603.7 | 0.987 /1{,}169.9 |
| **pooled (1,730)** | **0.693 / 130.8** | **0.855 / 213.6** | **0.950 / 370.6** | **0.990 / 635.0** |

`high_vol` carries the widest bands, `normal` the narrowest, and every regime lands within $\pm 1$pp of nominal at $\tau = 0.95$.

## B.4 Conditional-coverage tests (pooled OOS)

| $\tau$ | Violations | Rate | Kupiec $p_\text{uc}$ | Christoffersen $p_\text{ind}$ | $c(\tau)$ |
|---:|---:|---:|---:|---:|---:|
| 0.68  | 532 | 0.308 | 0.264 | 0.244 | 1.000 |
| 0.85  | 251 | 0.145 | 0.565 | 0.403 | 1.000 |
| **0.95** | **86** | **0.050** | **0.956** | **0.603** | **1.079** |
| 0.99  | 17 | 0.010 | 0.942 | $\approx 1.0$ | 1.003 |

The $\tau = 0.95$ row is the headline pooled operating result. Realised coverage is exactly $0.9503$ (Kupiec $p_{uc} = 0.956$); Christoffersen $p_{ind} = 0.603$ passes. Kupiec and Christoffersen pass at every served anchor on the deployed-fit OOS slice. Mean half-width at $\tau = 0.95$ is 370.6 bps — narrower than the K=26 σ̂ comparator (385.3 bps; bootstrap 95% CI on $\Delta$hw% upper bound is $-1.88\%$, see §7 / Appendix D). The held-out claim against this pooled baseline is the leave-one-symbol-out CV of §6.1 ($0.9497 \pm 0.0128$). The residual Berkowitz / DQ rejection localises to per-symbol Berkowitz on TLT and TSLA (B.11) and to cross-sectional within-weekend common-mode (§8, B.8) — where the contract fails is §8's subject.

## B.5 Realised-move tertile decomposition at $\tau = 0.95$

A post-hoc tertile labeler tags each weekend by realised-move z-score (calm / normal / shock); this `realized_bucket` is *not* a regime in the §3 sense — it depends on the realised target — and is used only for diagnostic stratification, including the shock-tertile ceiling reported in §8. Stratifying the OOS slice by realised-move $|z|$-score tertile (`reports/tables/m6_realised_move_tertile.csv`):

| tertile ($n$)     | realised | half-width (bps) | Kupiec $p$ |
|---|---:|---:|---:|
| calm   (497)      | 0.9920   | 359.5 | $< 10^{-6}$ (over-covers) |
| normal (601)      | 0.9933   | 379.6 | $< 10^{-6}$ (over-covers) |
| **shock** (632)   | **0.8766** | **370.7** | $< 10^{-6}$ (under-covers) |
| **pooled** (1{,}730) | **0.9503** | **370.6** | **0.956** |

Half-width is approximately flat across tertiles (365–380 bps), so the band does not widen in shock periods — it just misses more often. The shock-tertile residual is cross-sectional common-mode within a weekend (§8), not per-symbol scale; pooled $\tau = 0.95 = 0.950$ is achieved through compensating tertile-level biases (calm 1.000, normal 0.993, shock 0.878). A $|z|$-conditional conformal upgrade (characterised in Appendix F) would tighten calm bands and widen shock bands at the same pooled $\tau$.

## B.6 Stability detail — nested holdout, TUNE anchors, split dates, walk-forward, calendar sub-periods

The headline stability results are stated in §6.1; this section carries the mode tables and mechanisms.

**Nested temporal holdout — $c(\tau)$ fit on 2023, evaluated on 2024–26.** TRAIN = pre-2023-01-01 (the unchanged 4,186-row per-regime quantile fit); TUNE = 2023-01-01 → 2023-12-29 (52 weekends, $c(\tau)$ fit slice); EVAL = 2024-01-05 → 2026-04-24 (1,210 rows × 121 weekends, true holdout). At $\tau = 0.95$:

| mode | realised | $c(0.95)$ | Kupiec $p$ | Christoffersen $p$ | hw bps | per-sym Kupiec |
|---|---:|---:|---:|---:|---:|---:|
| $M_\text{full}$ (full-OOS $c$ fit; B.4 baseline) | 0.9504 | 1.079 | 0.956 | 0.720 | 370.6 | 10/10 |
| **$M_\text{a2}$ (true temporal holdout)** | **0.9504** | **1.079** | **0.947** | **0.989** | **420.8** | **10/10** |

(The $M_\text{full}$ row re-evaluates the B.4 deployed fit inside the nested-holdout runner; its Christoffersen statistic ($0.720$) differs from B.4's ($0.603$) because the lag-1 independence test is sensitive to the violation-series concatenation order — B.10 documents exactly this ordering sensitivity — and both pass at $\alpha = 0.05$. The reported Christoffersen figures use a fixed canonical ordering, weekend-major then symbol-lexicographic; the independence conclusion rests on no exact $p$-value, being corroborated order-robustly by the DQ and within-bin permutation tests, B.10 and B.16.) $c(\tau = 0.95)$ on TUNE-only matches the full-OOS fit at three decimals — the headline $\tau = 0.95$ number is *not* fit-on-evaluate sensitive. Christoffersen $p$ improves in held-out mode ($0.989$ vs $0.720$) because the 2024+ slice exhibits cleaner violation independence than the full 2023+ slice. The half-width difference (370.6 vs 420.8 bps) is entirely an eval-slice composition effect: the 2024+ holdout contains the 2024-08-05 BoJ unwind and the 2025-04 tariff weekend, both of which inflate $\hat\sigma_s$; coverage is unchanged because the $\hat\sigma_s$-conditional bands widened with the underlying realised volatility.

**TUNE-anchor sensitivity.** The result is stable across TUNE anchors $\{2021, 2022, 2023\}$: realised coverage at $\tau = 0.95$ lies in $[0.9474,\ 0.9524]$ with per-symbol Kupiec 10/10 preserved across all four anchors $\{2021, 2022, 2023, 2024\}$ (split-anchor robustness tables in Appendix D). The 2024 TUNE anchor over-covers at $0.9754$ because TUNE-2024 includes the 2024-08-05 BoJ unwind, inflating $c(0.95)$ to $1.175$; per-symbol Kupiec still passes 10/10. This is over-wide, not under-covering — the contract-favourable side of the asymmetry §8 frames.

**Lower-$\tau$ over-coverage disclosure.** At $\tau = 0.68$ and $\tau = 0.85$, $M_\text{a2}$ realises $0.712$ and $0.870$ respectively (Kupiec $p = 0.015$ and $p = 0.044$, both rejecting toward over-coverage). Mechanism: $c(0.68)$ and $c(0.85)$ fit on TUNE-only inherit the elevated banking-crisis-weekend volatility of 2023 (March SVB/CS), inflating $c$ to $1.028$ and $1.026$ respectively; $M_\text{full}$'s schedule on the full OOS slice averages this out at the floor ($c = 1.000$) and is the deployed mitigation. Source: `reports/tables/paper1_a2_nested_holdout_c_tau.csv`, `paper1_a2_6_tune_anchor_robustness.csv`.

**Split-date sensitivity (stability-of-fit on the deployed slice).** Repeating the fit (quantile table re-trained, $c(\tau)$ re-fit per split, $\delta \equiv 0$ held) at four OOS-split anchors $\{2021\text{-}01\text{-}01, 2022\text{-}01\text{-}01, 2023\text{-}01\text{-}01, 2024\text{-}01\text{-}01\}$ delivers realised $\tau = 0.95$ coverage of $\{0.9539,\ 0.9520,\ 0.9503,\ 0.9504\}$ — Kupiec $p \in \{0.348,\ 0.661,\ 0.956,\ 0.947\}$ and Christoffersen $p \in \{0.115,\ 0.186,\ 0.603,\ 0.671\}$ — every (split × $\tau$) cell passes at $\alpha = 0.05$. Mean half-width $\{357.2,\ 363.5,\ 370.6,\ 416.8\}$ bps varies $\pm 8\%$ around the deployed value.

**Walk-forward stability.** Re-running the schedule selection on the four powered expanding-window splits (fractions $f \in \{0.40, 0.50, 0.60, 0.70\}$ — the 0.20 and 0.30 splits are excluded as under-powered for the 4-scalar $c(\tau)$ fit; Appendix D) with $\delta = 0$: walk-forward realised $\tau = 0.95$ coverage is $\geq 0.95$ on every powered split (range 0.954–0.975) — the criterion that selected $\delta = 0$ (§4.5). Per-split mean half-width at $\tau = 0.95$ tracks the full-OOS-fit value within $\pm 8\%$.

**Calendar sub-period stability.** Bucketing the OOS slice into four calendar sub-periods {2023, 2024, 2025, 2026-YTD} (`reports/tables/m6_subperiod_robustness.csv`):

| Sub-period ($n$ weekends) | Realised at $\tau = 0.95$ | Half-width (bps) | Kupiec $p$ | Christoffersen $p$ |
|---|---:|---:|---:|---:|
| 2023 (52)          | 0.950 | 253.6 | 1.000 | 0.888 |
| 2024 (52)          | 0.931 | 420.4 | 0.057 | 0.841 |
| 2025 (52)          | 0.971 | 444.4 | 0.017 | 0.793 |
| 2026-YTD (17)      | 0.947 | 350.0 | 0.862 | 0.908 |
| **Pooled OOS (173)** | **0.950** | **370.6** | **0.956** | **0.603** |

Pooled OOS calibration at $\tau = 0.95$ holds across each of the four years that span SVB / banking-stress 2023, the 2024 rate-cut transition, the 2025 tokenisation-launch year, and 2026-YTD (realised range $0.931$–$0.971$). The 2025 cell rejects Kupiec at $\alpha = 0.05$ ($p = 0.017$, over-coverage); 2024 sits just above the threshold ($p = 0.057$); 2023 and 2026-YTD pass cleanly. Across the full 16-cell (sub-period × $\tau$) grid the architecture carries 3 Kupiec rejections — all toward over-coverage (one 2024 cell at $\tau = 0.99$ and the 2025 cells at $\tau \in \{0.95, 0.99\}$; §8 frames the asymmetry); Christoffersen lag-1 independence is not rejected in any of the 16 cells.

**Stationarity read.** The $P_2$ guarantee (§3) assumes the standardised score's conditional distribution is approximately stationary; the sub-period grid is the direct empirical evidence, and it is positive: four years of structurally different market regimes, three rejections, all on the over-coverage side — not the under-coverage failure mode that warrants a deployment alarm. The EWMA $\hat\sigma_s(t)$ provides partial adaptive scaling per symbol (the Appendix C simulation shows σ̂ tracks drift and structural-break DGPs with a half-life-bounded lag), but conditional-distribution stationarity of the *standardised* score is still assumed; §8 lists the three violations no backtest grid can pre-empt.

## B.7 OOS-tuned $c(\tau)$ provenance

Of the four OOS-fit $c(\tau)$ scalars, three are essentially identity ($c \in \{1.000,\,1.000,\,1.003\}$ at $\tau \in \{0.68,\,0.85,\,0.99\}$); **only $c(0.95) = 1.079$ carries meaningful OOS information** (a 7.9% widening at the headline anchor). The nested temporal holdout (B.6) fits $c(0.95)$ on 2023 alone and evaluates it on a 2024-01-05 → 2026-04-24 slice that neither the per-regime quantile nor the bump has seen — realised coverage $0.9504$, Kupiec $p = 0.947$, Christoffersen $p = 0.989$, per-symbol Kupiec 10/10; $c(0.95)$ on TUNE-only matches the full-OOS fit at three decimals. **The headline $c(0.95) = 1.079$ is empirically held-out at the time level.** The residual provenance disclosure is restricted to the lower-$\tau$ over-coverage in held-out mode (B.6), which the deployed full-OOS schedule mitigates at the floor. The forward-tape harness (A.9) closes the residual contamination by carrying the frozen deployment artefact onto truly held-out weekends as they accumulate: at submission $N = 11$ forward weekends show pooled Kupiec passing at all four anchors with no under-coverage and per-symbol Kupiec 10/10 at $\tau = 0.95$ — just under the $N \ge 13$ gate at which the disclosure upgrades to "OOS-fit + held-out forward-tape re-validation."

## B.8 Joint-tail empirical distribution — fitting detail and stability

§8 states the joint-tail result and carries Figure H5; this section documents the baseline construction and the full statistics. For each OOS weekend $w$ with full 10-symbol coverage, $k_w = |\{s : s \text{ breaches its } \tau\text{-band on } w\}|$ is compared against three properly specified baselines: $\mathrm{Binom}(10, 1-\tau)$ (independence), a Gaussian copula on the empirical correlation matrix $\hat R$ (mean off-diagonal $0.36$ on standardised residuals), and a Student-$t$ copula on per-symbol Student-$t$ marginals with $\hat\nu \in [4.80, 28.32]$, copula degrees-of-freedom $\hat\nu_\text{copula} = 6.04$ (median across symbols) (`reports/tables/paper1_a3_joint_baseline_kw_distribution.csv`, `..._summary.csv`; 50,000 simulated weekends per baseline; CIs are 1000-rep weekend-block bootstrap, seed = 0):

| Statistic at $\tau = 0.95$ ($n_\text{weekends} = 173$) | empirical | $\mathrm{Binom}(10, 0.05)$ | Gaussian copula | t-copula ($\nu = 6.04$) |
|---|---:|---:|---:|---:|
| Mean $k_w$ / weekend | 0.497 | 0.500 | 0.501 | 0.501 |
| Variance ratio (emp / model) | — | **2.34** | 0.83 | **0.63** |
| $P(k_w \ge 3)$ | **4.62% [1.73, 7.51]** | 1.15% | 6.69% | 8.15% |
| $P(k_w \ge 5)$ | **0.58% [0.00, 1.73]** | 0.01% | 1.86% | 3.15% |
| max $k_w$ (worst weekend) | 9 | — | — | — |

**Variance overdispersion.** Empirical $k_w$ over-disperses by a uniform $\sim 2.3\times$ vs Binom independence at every served $\tau$ (emp/Binom variance ratio $\{2.34, 2.31, 2.34, 2.35\}$ at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$) and sits inside a properly-specified t-copula envelope from above (emp/t variance ratio $\{0.83, 0.54, 0.63, 0.73\}$; Wasserstein-1 distance to the t-copula $\le 0.180$ at every $\tau$, less than half the distance to Binom independence). Marginal calibration is preserved — mean $k_w$ matches every reference to $0.003$. Independence is misspecified, the joint dependence is real ($\hat R = 0.36$ mean off-diagonal), and the structure brackets-bound: empirical between Binom independence and a homogeneous t-copula at $\hat\nu \approx 6$. The mean intra-weekend pairwise breach correlation ($\bar\rho_\text{intra} = 0.41$ — the average pairwise dependence across the ten symbols within a weekend, distinct from the lag-1 cross-sectional AR coefficient $\hat\rho_\text{cross} = 0.354$ of B.10) is respected by all reported CIs via weekend-block bootstrap; temporal autocorrelation across weekends is empirically null (lag-1, lag-2, lag-4 $\hat\rho$ on weekly $k_w$ in $[-0.07, 0.03]$), so $L \in \{4, 8, 13\}$ moving-block-bootstrap CIs are within Monte Carlo noise of the $L = 1$ baseline (`reports/tables/paper1_b5_kw_block_bootstrap.csv`).

**Reserve-guidance threshold stability.** $k^\ast$ at each $\tau$ — smallest $k$ whose empirical hit-rate is closest to $5\%$ — is $k^\ast = 5$ at $\tau = 0.85$ (rate $5.78\%$), $k^\ast = 3$ at $\tau = 0.95$ ($4.62\%$), and $k^\ast = 1$ at $\tau = 0.99$ ($6.36\%$). Across the 24-cell grid (3 $\tau$ × 2 threshold conventions × 4 sub-periods) the architecture carries **0/24 Kupiec stability rejections** at $\alpha = 0.05$ (`reports/tables/m6_kw_threshold_stability.csv`); at $k^\ast = 3$ for $\tau = 0.95$, per-sub-period hit-rates are $\{3.85, 7.69, 1.92, 5.88\}\%$ across {2023, 2024, 2025, 2026-YTD} with Kupiec $p \in \{0.78, 0.33, 0.30, 0.81\}$. The per-sub-period 95th percentile of $k_w$ at $\tau = 0.95$ stays in $[1.0, 3.0]$ across the four years. With sub-period $n \approx 52$ and target rates $\sim 5\%$, the binomial-stability test has limited power against drift below the year-on-year p95 spread (≤ 1.6 integer-symbols); the result is "no detectable instability with the available power." At $\tau = 0.85$ the empirical 99th percentile of $k_w$ is $\approx 7$ vs binomial $\approx 4$; §8 carries the consumer guidance.

## B.9 Worst-observed weekend — 2024-08-05 BoJ yen-carry unwind

The single OOS weekend with all 10 symbols breaching the $\tau = 0.85$ band simultaneously is **Friday 2024-08-02 → Monday 2024-08-05** — the Bank of Japan rate-hike yen-carry-trade unwind, one of the largest single-weekend global risk-off events of the post-2020 period. The same weekend has $k_w = 9$ at $\tau = 0.95$ (only TLT inside that band — consistent with the B.8 worst-weekend maximum) and $k_w = 5$ at $\tau = 0.99$. §8 carries the one-paragraph summary; the per-symbol anatomy follows. The deployed served band, computed directly from the deployment artefact (per-Friday parquet row + sidecar schedules, EWMA HL=8 σ̂) on the 2024-08-02 row:

| Symbol | Weekend return | HW @ $\tau=0.85$ | Breach @ $\tau=0.85$ | @ $\tau=0.95$ |
|---|---:|---:|---:|---|
| MSTR  | $-27.4\%$ | 663 bps  | $-1537$ bps | breach ($-1060$) |
| HOOD  | $-17.8\%$ | 357 bps  | $-1336$ bps | breach ($-1079$) |
| NVDA  | $-14.2\%$ | 332 bps  | $-1000$ bps | breach ($-762$) |
| TSLA  | $-10.8\%$ | 499 bps  | $-496$ bps  | breach ($-137$) |
| AAPL  | $-9.4\%$  | 201 bps  | $-659$ bps  | breach ($-514$) |
| GOOGL | $-6.7\%$  | 194 bps  | $-390$ bps  | breach ($-250$) |
| QQQ   | $-5.4\%$  | 120 bps  | $-330$ bps  | breach ($-243$) |
| SPY   | $-4.0\%$  | 85 bps   | $-228$ bps  | breach ($-167$) |
| GLD   | $-2.1\%$  | 108 bps  | $-171$ bps  | breach ($-94$) |
| TLT   | $+1.4\%$  | 131 bps  | $+10$ (just past) | inside |

![Anatomy of the served band on the worst observed weekend (2024-08-02 → 2024-08-05, BoJ yen-carry unwind). For each symbol: nested served bands at $\tau \in \{0.85, 0.95, 0.99\}$ (blue, darkest = 0.85), the factor-adjusted point $\hat p$ (black tick), and the realised Monday open (filled vermilion = breach at $\tau = 0.95$; open = inside), in weekend-return space relative to Friday close. Bands are computed from the deployment artefact, byte-aligned with what a consumer read. Per-symbol $\hat\sigma_s$ width differentiation is visible directly — MSTR's $\tau = 0.85$ half-width (663 bps) is $\approx 8\times$ SPY's (85 bps) — and so is the cross-sectional common-mode failure: nine realised opens march left past their bands in concert, which no per-symbol band, however well calibrated, can absorb. The $k_w$ distribution of §8 / B.8 is the operational handle for exactly this event class.\label{fig:boj-anatomy}](figures/fig9_boj_anatomy.pdf)

Cross-section: 9 of 10 symbols sold off in concert (mean weekend return $-963$ bps, median $-807$ bps); only TLT delivered the classic flight-to-quality bid. Macro context: the 2024-08-02 US July nonfarm-payrolls print landed at 114k vs ~175k consensus with the Sahm-rule recession indicator triggering; the 2024-07-31 BoJ rate hike combined with hawkish Powell/Yellen language drove an accelerating yen-carry unwind through Asian time zones over the weekend; the Monday 2024-08-05 Nikkei fell 12.4% (largest single-day drop since Black Monday 1987) and intraday VIX spiked to ~65, the highest reading since the COVID-19 March 2020 panic.

The σ̂-standardisation held at the per-symbol level — high-vol symbols (MSTR, TSLA) got wide bands, low-vol symbols (SPY, QQQ, GLD) narrow ones, and breach magnitudes scale with the cross-sectional shock divided by σ̂. What broke is *cross-sectional common-mode*: when nearly every symbol moves the same direction at the same time by 4–27 standard-deviation-scale weekend returns, no per-symbol band — however well calibrated — can absorb the joint event. A consumer monitoring $k_w$ in real time would have seen $k_w = 10$ at $\tau = 0.85$ by the Monday-open print, well in excess of the deployment-time-fitted $k^\ast = 5$ (or the empirical 99th percentile of $7$); the empirical $k_w$ distribution is the right operational signal precisely because it captures the cross-sectional common-mode that per-symbol coverage cannot.

**Joint-baseline framing of the BoJ probability.** Under a Student-$t$ copula with $\hat\nu = 6.04$ and empirical correlation $\hat R$ (mean off-diagonal $0.36$), $P(k_w = 10)$ at $\tau = 0.85$ is $0.21\%$ — i.e., the 2024-08-05 BoJ unwind is a $\sim 1\text{-in-}475\text{-weekends}$ event under a properly specified joint baseline. The independence baseline puts the same event at $\sim 1\text{-in-}10{,}000\text{-weekends}$; the residual structure §8 documents is exactly the gap between these two figures. The residual has a *name* (cluster topology, §8), a *parametric envelope* (t-copula at $\nu \approx 6$ with empirical $\hat R$), and a *structural mechanism* (equity vs safe-haven cluster topology) — not "a residual the architecture cannot characterise."

### B.9.1 Case study — the M6 served bands against hypothetical consumer configurations

A per-method coverage grid on the same weekend makes the §8 claim concrete: no method on the grid attains its nominal coverage at $\tau \le 0.95$ on this weekend. Generated by the self-checking runner `scripts/build_case_study_boj_m6.py` (band logic mirrors `build_paper1_figures.py::fig9_boj_anatomy`; sanity-gated against B.9's $k_w = 10/9/5$; input hashes recorded in the report header). Bands are read from the deployment artefact, not refit — byte-aligned with what a consumer read on 2024-08-02; the 2024-08-02 row sits in the OOS slice.

The comparators are **hypothetical consumer configurations, not incumbent products**: "Pyth+k%" wraps a Pyth-style point price in a fixed symmetric k% buffer; "VIX-scaled" and "Const-buffer" are this project's v1-era calibrated baselines (pre-2023 train, centred on Friday close), whose half-widths are retained for comparability. Coverage = Monday 09:30 ET open inside the band. Regime classification for 2024-08-02 = `high_vol` for all 10 symbols. Realised moves: max $|$Mon−Fri$|$/Fri = 2,737 bps (MSTR); mean $|$move$|$ = 992 bps; 7 of 10 symbols exceed 500 bps.

| Symbol | Realised (bps) | Pyth+2% | Pyth+5% | Pyth+10% | Pyth+20% | VIX-scaled τ=0.68 | VIX-scaled τ=0.85 | VIX-scaled τ=0.95 | VIX-scaled τ=0.99 | Const-buffer τ=0.68 | Const-buffer τ=0.85 | Const-buffer τ=0.95 | Const-buffer τ=0.99 | M6 τ=0.68 | M6 τ=0.85 | M6 τ=0.95 | M6 τ=0.99 |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **AAPL** | -945 | ✗ / 200 bps | ✗ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 114 bps | ✗ / 201 bps | ✗ / 345 bps | ✗ / 668 bps |
| **GLD** | -212 | ✗ / 200 bps | ✓ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✓ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✓ / 272 bps | ✓ / 694 bps | ✗ / 62 bps | ✗ / 108 bps | ✗ / 185 bps | ✓ / 359 bps |
| **GOOGL** | -670 | ✗ / 200 bps | ✗ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✓ / 694 bps | ✗ / 111 bps | ✗ / 194 bps | ✗ / 334 bps | ✓ / 647 bps |
| **HOOD** | -1779 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 204 bps | ✗ / 357 bps | ✗ / 614 bps | ✗ / 1190 bps |
| **MSTR** | -2737 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✗ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 378 bps | ✗ / 663 bps | ✗ / 1139 bps | ✓ / 2208 bps |
| **NVDA** | -1418 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 189 bps | ✗ / 332 bps | ✗ / 571 bps | ✗ / 1106 bps |
| **QQQ** | -536 | ✗ / 200 bps | ✗ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✓ / 694 bps | ✗ / 69 bps | ✗ / 120 bps | ✗ / 207 bps | ✗ / 402 bps |
| **SPY** | -399 | ✗ / 200 bps | ✓ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✓ / 694 bps | ✗ / 49 bps | ✗ / 85 bps | ✗ / 146 bps | ✗ / 283 bps |
| **TLT** | +143 | ✓ / 200 bps | ✓ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✓ / 173 bps | ✓ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✓ / 272 bps | ✓ / 694 bps | ✗ / 75 bps | ✗ / 131 bps | ✓ / 225 bps | ✓ / 435 bps |
| **TSLA** | -1081 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 285 bps | ✗ / 499 bps | ✗ / 859 bps | ✓ / 1664 bps |

Aggregate coverage on this weekend (✓ count / total):

| Method | Covered | Mean half-width (bps) |
|---|---|---:|
| Pyth+2% | 1/10 | 200 |
| Pyth+5% | 3/10 | 500 |
| Pyth+10% | 6/10 | 1000 |
| Pyth+20% | 9/10 | 2000 |
| VIX-scaled τ=0.68 | 0/10 | 103 |
| VIX-scaled τ=0.85 | 1/10 | 173 |
| VIX-scaled τ=0.95 | 2/10 | 329 |
| VIX-scaled τ=0.99 | 5/10 | 700 |
| Const-buffer τ=0.68 | 0/10 | 75 |
| Const-buffer τ=0.85 | 0/10 | 139 |
| Const-buffer τ=0.95 | 2/10 | 272 |
| Const-buffer τ=0.99 | 5/10 | 694 |
| M6 τ=0.68 | 0/10 | 153 |
| M6 τ=0.85 | 0/10 | 269 |
| M6 τ=0.95 | 1/10 | 463 |
| M6 τ=0.99 | 5/10 | 896 |

Reading the grid:

- **M6 at $\tau = 0.68$ and $\tau = 0.85$ covers 0/10.** All ten symbols breach the $\tau = 0.85$ band simultaneously; this weekend is the single $k_w = 10$ event at $\tau = 0.85$ in the OOS record (§8, B.8).
- **M6 at $\tau = 0.95$ covers 1/10** (TLT only; $k_w = 9$, the OOS maximum at that anchor). The σ̂ standardisation works at the per-symbol level — MSTR's $\tau = 0.85$ half-width (663 bps) is ≈ 8× SPY's (85 bps) — but nine symbols moving the same direction by 4–27 σ̂-scale weekend returns is a cross-sectional common-mode event that no per-symbol band absorbs. The joint-breach distribution ($k^\ast = 3$ reserve-guidance threshold at $\tau = 0.95$; §8) is the operational handle for this event class.
- **M6 at $\tau = 0.99$ covers 5/10** (GLD, GOOGL, MSTR, TLT, TSLA; mean half-width 896 bps). Coverage at this anchor comes from per-symbol width differentiation plus the factor-adjusted centre: MSTR's served band is 2,208 bps wide and centred −538 bps below Friday close, so its −2,737 bps realised move lands inside; SPY's 283 bps band does not reach its −399 bps move.
- **Fixed-buffer comparators:** Pyth+5% covers 3/10; Pyth+10% covers 6/10 and Pyth+20% covers 9/10, at uniform 1,000 / 2,000 bps half-widths on every symbol in every week regardless of regime. The v1-era calibrated comparators (VIX-scaled, const-buffer; pre-2023 train) cover at most 2/10 at $\tau \le 0.95$ and 5/10 at $\tau = 0.99$.
- **No method on this grid attains its nominal coverage at $\tau \le 0.95$ on this weekend.** The best $\tau \le 0.95$ cell is 2/10. The tail-coverage story on this event sits at $\tau = 0.99$, where M6 matches the best comparator count (5/10) with regime- and symbol-conditional widths rather than a flat buffer.

One weekend is one observation. The aggregate OOS calibration evidence for the deployed architecture is §6 and B.3–B.8; this case study is the qualitative counterpart on the worst observed weekend.

## B.10 Extended diagnostics — DQ and Berkowitz specification

**Engle-Manganelli (2004) DQ is the finer test on the violation series.** Kupiec checks marginal counts and Christoffersen's two-state Markov independence checks the lag-1 hit transition; neither has power against conditional miscalibration patterns that yield correct marginal counts and uncorrelated lag-1 hits but encode systematic dependence on lagged hits or the served quantile [engle-manganelli-2004]. DQ regresses the centred hit indicator on a constant + $K$ lagged hits and tests joint significance under $\chi^2_{K+1}$. We use $K = 4$ throughout (the lag-only specification of Engle–Manganelli's CAViaR — conditional autoregressive value-at-risk — Table 1, block 1), no contemporaneous covariate — the lag-only specification is symmetric across the five methods compared in §6.2, so cross-method DQ p-values are directly comparable. **Pooled DQ at $\tau = 0.95$ rejects on the deployed fit** — the cross-sectional within-weekend common-mode (orthogonal to σ̂ standardisation) is what DQ is sensitive to here. Per-(symbol × τ × method) DQ p-values are reported in the §6.2 master grid alongside Kupiec and Christoffersen. **Bands are *per-anchor calibrated*, not full-distribution calibrated** — the joint-tail empirical distribution (§8, B.8) turns this disclosure into a measurable, reportable shape.

**Berkowitz (2001) joint LR on continuous PITs.** PITs reconstructed by inverting each served band against the realised Monday open through the per-regime conformal CDF. The pooled Berkowitz LR on the deployed PITs is non-zero, viewing the same residual through the PIT lens. The Berkowitz/DQ rejection and the B.8 joint-tail overdispersion are not two independent residuals: both are the cross-sectional within-weekend common-mode ($\hat\rho_\text{cross} = 0.354$) viewed through different aggregations — Berkowitz/DQ on the pooled PIT/violation series detects it as serial-cluster-equivalent dependence; the $k_w$ distribution on the same panel detects it as upper-tail overdispersion in joint-breach counts. The methodology fix targets the same channel; the consumer-facing handle is the reserve-guidance threshold (§8).

**Localising the residual.** Decomposing the lag-1 alternative under panel-row order: the AR(1) signal lives in the *cross-sectional within-weekend* ordering ($\hat\rho_{\text{cross}} = 0.354$, $p < 10^{-100}$, $n = 1{,}557$) — not the temporal-within-symbol ordering ($\hat\rho_{\text{time}} = -0.032$, $p = 0.18$, $n = 1{,}720$). σ̂ standardisation operates *within* a symbol's history, not *across* symbols within a weekend, so it cannot reach this residual. A vol-tertile sub-split of `normal` regime (5 cells) leaves Berkowitz LR essentially unchanged ($170 \to 172$) while widening the $\tau = 0.95$ band by $9\%$ — finer regime granularity is not the lever (`reports/tables/m6_lwc_robustness_vol_tertile.csv`). The candidate architectures that target cross-sectional common-mode (cluster-conditional partial-out, Appendix F) are deferred-with-gates.

## B.11 Per-symbol Kupiec at $\tau = 0.95$, Berkowitz LR, and test power

Per-symbol Kupiec on the 2023+ OOS slice (`reports/tables/m6_per_symbol_kupiec_4methods.csv`, regenerated 2026-05-05):

| Symbol | Violation rate | Kupiec $p$ | Berkowitz LR |
|---|---:|---:|---:|
| AAPL  | 0.069 | 0.268 |  6.7 |
| GLD   | 0.069 | 0.268 |  3.2 |
| GOOGL | 0.052 | 0.903 | 10.2 |
| HOOD  | 0.035 | 0.329 |  6.4 |
| MSTR  | 0.046 | 0.818 |  7.1 |
| NVDA  | 0.052 | 0.903 | 10.0 |
| QQQ   | 0.040 | 0.552 |  5.1 |
| SPY   | 0.046 | 0.818 |  9.6 |
| TLT   | 0.046 | 0.818 | 16.7 |
| TSLA  | 0.040 | 0.552 | 13.5 |
| **pass-rate at $\alpha = 0.05$** | | **10 / 10** | |
| **Berkowitz LR range** | | | **3.2 – 16.7** (5.2$\times$) |

All 10 symbols pass Kupiec at $\tau = 0.95$ with violation rates inside $[3.5\%, 6.9\%]$. Within the per-symbol Berkowitz LR range $[3.2, 16.7]$ (a 5.2$\times$ spread), only TLT (LR 16.7) and TSLA (LR 13.5) reject Berkowitz at $\alpha = 0.01$, and those rejections trace to cross-sectional common-mode rather than per-symbol scale (B.10).

**Power caveat at $\tau = 0.99$.** Per-symbol Kupiec at $\tau = 0.99$ has minimum detectable effect $\approx 3$ pp under-coverage and is undetectable for over-coverage given the per-symbol expected violation count of $1.73$ (Monte Carlo: 10,000 reps per cell, Kupiec LR critical at $\alpha = 0.05$; `reports/tables/paper1_b3_kupiec_power_mde.csv`). The 10/10 pass should be read as "no per-symbol violation rate is statistically distinguishable from $1\%$ at the resolution Kupiec offers per-symbol", **not** as a 1 pp tolerance certificate. Pooled Kupiec at $\tau = 0.99$ has minimum detectable effect $1.0$ pp; the pooled $p = 0.94$ is the $\tau = 0.99$ statistical claim that does have 1 pp resolution. Per-symbol Kupiec at $\tau = 0.95$ has MDE $4.0$ pp under-coverage / $7.5$ pp over-coverage on $N = 173$ — the deployed per-symbol violation rates in $[3.5\%, 6.9\%]$ sit well within the 4 pp window of nominal $5\%$, so the 10/10 pass at $\tau = 0.95$ is informative against deviations larger than 4–8 pp.

## B.12 GARCH baselines — pooled tables, matched-coverage width, proper scoring

The textbook econometric default for a time-varying interval at $\tau$ is per-symbol GARCH(1,1) on log Friday-to-Monday returns. The practitioner choice of innovation distribution is Student-$t$: Gaussian innovations under-fit equity weekend tails, where the fitted $\hat\nu \approx 3$ across the panel (`reports/tables/m6_lwc_robustness_garch_t_baseline.csv`):

| $\tau$ | Method | Realised | HW (bps) | Kupiec $p$ | Christoffersen $p$ |
|---:|---|---:|---:|---:|---:|
| 0.95 | GARCH-Gaussian | 0.9254 | 322.2 | $0.000$ | 0.016 |
| 0.95 | GARCH-$t$       | 0.9277 | 331.6 | $0.000$ | **0.209** |
| 0.95 | **this paper**  | $\mathbf{0.9503}$ | $\mathbf{370.6}$ | $\mathbf{0.956}$ | **0.603** |
| 0.99 | GARCH-Gaussian | 0.9630 | 423.7 | $0.000$ | 0.866 |
| 0.99 | GARCH-$t$       | 0.9850 | 569.3 | 0.050  | $1.000$ |
| 0.99 | **this paper**  | $\mathbf{0.9902}$ | $\mathbf{635.0}$ | $\mathbf{0.942}$ | $1.000$ |

GARCH-$t$ closes two failures GARCH-Gaussian leaves on the table: the $\tau = 0.99$ tail capture (realised improves from $0.963$ to $0.985$; Kupiec $p$ moves from $< 0.001$ to a borderline $0.050$) and the Christoffersen rejection at $\tau = 0.95$ ($p$ moves from $0.016$ to $0.209$). What it does *not* fix is the **Kupiec under-coverage at every $\tau < 0.99$** — the standardised-$t$ 95th percentile at $\nu \approx 3$ is $\sim 1.83$ vs Gaussian $1.96$, so the bands tighten precisely where Gaussian was already under-covering. T-innovations fix the wrong end of the distribution.

**At matched 95% realised coverage**, widening GARCH-$t$ to its claimed $\tau = 0.95$ requires roughly $+14\%$ on width, giving a matched-coverage HW $\approx 378$ bps — comparable to the deployed architecture's $370.6$ bps (we report the two half-widths rather than a paired width test; the claim rests on the coverage difference, not a width difference). The distinction that matters is provenance: the deployed $370.6$ bps is served with its coverage stated in advance, while GARCH-$t$'s $\approx 378$ bps is the width that reproduces the target coverage only in hindsight. At $\tau = 0.99$ the deployed architecture dominates GARCH-$t$ on coverage and width-at-matched-coverage simultaneously. The conformal route fixes both Kupiec and Christoffersen because it is calibrated to the data, not to a fitted parametric distribution; the NVDA fallback (t-MLE pushes $\hat\nu$ to the optimizer lower bound $\hat\nu = 2.50$, adjacent to the $\nu \le 2$ variance-undefined region) is the parametric-tail risk the deployed architecture avoids.

**Proper-scoring-rule head-to-head.** Under proper scoring rules — Winkler (1972) interval score and CRPS (continuous ranked probability score) — the deployed architecture dominates GARCH(1,1)-$t$ at every served $\tau$. Winkler interval score (bps of fri_close, lower is better) at $\tau = 0.95$: deployed $992$ vs GARCH-$t$ $1{,}139$ ($-12.9\%$); at $\tau = 0.99$: deployed $1{,}566$ vs GARCH-$t$ $1{,}904$ ($-17.8\%$). The advantage grows with $\tau$ — the σ̂-standardisation pays most where parametric-tail mis-specification hurts most. Pooled CRPS over the served coverage range $\{0.05, 0.10, \dots, 0.99\}$: deployed $80.7$ vs GARCH-$t$ $92.6$ ($-12.8\%$). Both rules are computed on the aligned 1,730-row OOS slice; method aggregation is by row, not by $\tau$, so a single number summarises the practitioner-baseline comparison without anchor-row cherry-picking. Source: `reports/tables/paper1_c1_winkler_interval_score.csv`, `..._crps.csv`. The Winkler comparison against the *tokenised-tracking* baseline archetype — the competitor motivated by Cong et al.'s conditional-mean result, distinct from the GARCH-family parametric baselines compared here — is carried in §6.3 with construction detail in Appendix D.

## B.13 Per-asset-class deviation

Pooled OOS coverage stratified by asset class under the deployed EWMA HL=8 σ̂ (`reports/tables/m6_lwc_robustness_per_class.csv`). Equities (8 syms, 1,384 obs): realised $0.952$ at $\tau = 0.95$ with hw $417.8$ bps; GLD ($n = 173$): realised $0.931$, hw $180.9$ bps; TLT ($n = 173$): realised $0.954$, hw $182.3$ bps. Row-weighted reconciliation: $(1384 \cdot 417.8 + 173 \cdot 180.9 + 173 \cdot 182.3) / 1730 = 370.6$ bps, matching the B.4 panel-pooled HW. The per-symbol $\hat\sigma_s$ multiplier delivers heavy-tail equities wider bands matched to their relative-residual scale and the defensive class (GLD, TLT) narrower bands matched to theirs; the deployed architecture's Kupiec passes every class at every $\tau$. The width allocation across asset classes is the operational manifestation of $P_3$ (per-regime serving efficiency): width is concentrated where calibration demands it.

## B.14 Path coverage — endpoint vs intra-weekend

The §6 result is *endpoint coverage*: realised Monday open lies inside the served band. A DeFi consumer holding an xStock as collateral is exposed at every block over the weekend; a Saturday liquidation when the on-chain xStock briefly trades outside the band is a real loss event even if Monday open returns inside. We measure path coverage on $[\text{Fri 16:00 ET},\, \text{Mon 09:30 ET}]$ against 24/7 stock-perp 1m bars from `cex_stock_perp/ohlcv` (Kraken Futures `PF_<sym>XUSD`, xStock-backed). Sample: 19 weekends × 9 symbols (TLT excluded — no perp listing), $n = 118$ (symbol, weekend) pairs per anchor, 2025-12-19 → 2026-04-24 (`reports/tables/path_coverage_perp.csv`):

| $\tau$ | $n$ | Endpoint coverage | Path coverage | Gap (pp) |
|---:|---:|---:|---:|---:|
| 0.68 | 118 | 0.644 | 0.348 | $+29.7$ |
| 0.85 | 118 | 0.864 | 0.568 | $+29.7$ |
| **0.95** | **118** | $\mathbf{0.949}$ | $\mathbf{0.788}$ | $+\mathbf{16.1}$ |
| 0.99 | 118 | 0.992 | 0.915 | $+7.6$  |

The deployed architecture calibrates the perp-listed sample to nominal endpoint coverage (0.949 at $\tau = 0.95$ vs nominal $0.95$) on a sample whose composition is predominantly large-cap equities (SPY/QQQ/AAPL/GOOGL/NVDA/MSTR/TSLA/HOOD plus GLD; TLT excluded — no perp listing). The path-coverage gap is $+16.1$ pp at $\tau = 0.95$: an honestly-calibrated endpoint band exhibits a structural shortfall on a sample whose intra-weekend variance is larger than its endpoint variance. Sample is small (binomial CI on the $\tau = 0.95$ pooled gap is $\pm 6$ pp); the test is directional. After three confound checks documented in `reports/v1b_path_coverage_robustness.md` — perp-spot basis normalisation closes the gap to $11.0$ pp, a volume-floor filter at $\geq 1$ contract closes it to $9.5$ pp ($n=63$), and a 15-minute rolling-median sustained-crossing definition leaves it at $14.4$ pp — the residual genuine-shortfall band is $\sim 9$–$15$ pp at $\tau = 0.95$, with most of the magnitude attributable to sustained drift rather than transient thin-liquidity prints. The gap collapses meaningfully only at $\tau = 0.99$ ($+7.6$ pp); continued capture is tracked under scryer item 51, and the path-fitted conformity score is the methodology variant (Appendix F).

![Path coverage gap on the 24/7 stock-perp reference. Endpoint coverage (blue) tracks nominal across $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ on the perp-listed subset; path coverage (vermilion) — the fraction of weekends where the perp 1m bar high/low stay inside the served band over the full $[\text{Fri 16:00, Mon 09:30}]$ window — runs $29.7$/$29.7$/$16.1$/$7.6$ pp behind. The gap collapses meaningfully only at $\tau = 0.99$. Sample is small ($n = 118$ symbol-weekends across 19 calendar weekends, 2025-12 to 2026-04); the read is directional and the path-fitted conformity score (Appendix F) is the methodology fix.\label{fig:path-coverage}](figures/fig6_path_coverage.pdf)

**Decomposing the gap: fair-value path vs venue microstructure.** An excursion-inflation diagnostic separates the two sources of the perp gap. Define $\lambda(\tau)$ as the multiplier on the endpoint band half-width required to reach $\tau$ *path* coverage. On the CME factor-projected path — the projectable weekend trajectory of the per-symbol factor scaled to underlier units, 435 weekends — $\lambda(\tau) \approx 1.0$ at every anchor: the endpoint-sized band already contains the factor's intra-weekend round-trips (`reports/active/proto_excursion_inflation.md`). The larger perp $\lambda$ ($\approx 1.6$–$2.4$, and non-monotone in $\tau$ at this $n$) therefore reflects predominantly *venue basis and microstructure* on a thin-liquidity perp — not fair-value excursion the forecaster fails to capture, consistent with the thin-print confounds above. The contract implication: the deployed band is an **endpoint** contract that, on the projectable fair-value path, also delivers $\approx \tau$ path coverage; the residual a continuous-consumption consumer experiences is a property of their settlement venue, and closing it on a real venue is a microstructure layer (the oracle-conditioned-AMM setting), not a forecaster deficiency.

The endpoint contract stands. A consumer requiring path coverage at level $\tau$ should step up one anchor (empirically closes the gap on this slice at $\tau = 0.99$), absorb the residual through their own downstream risk policy, or — for continuous-consumption AMM use cases that cannot use the step-up lever — adopt the path-fitted conformity-score variant (Appendix F).

## B.15 Overnight generalisation — full battery

§6.4 states the overnight result; this section carries the tables and the cadence-specific data treatments. Pooled OOS conditional coverage (overnight; TRAIN < 2023-01-01, 16,093 rows; OOS ≥ 2023-01-01, 6,450 rows × 645 nights; post-dividend-adjustment run, `reports/active/overnight_calibration_firstread.md` @ 2026-06-25):

| $\tau$ | Violations | Rate | Kupiec $p_\text{uc}$ | Christoffersen $p_\text{ind}$ | $c(\tau)$ |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 2,064 | 0.320 | 1.000 | 0.537 | 1.019 |
| 0.85 |   963 | 0.149 | 0.875 | 0.212 | 1.000 |
| **0.95** | **316** | **0.049** | **0.710** | **0.158** | **1.000** |
| 0.99 |    53 | 0.008 | 0.138 | 1.000 | 1.000 |

Kupiec and Christoffersen pass at every served anchor — the same headline property as the weekend panel (B.4), reproduced on a different and ≈3.8× larger panel, with the OOS-fit $c(\tau)$ collapsing to ≈1.0 (the overnight bands need essentially no post-hoc widening to calibrate).

**Robustness to consecutive-night autocorrelation.** Overnight gaps, unlike weekends, are temporally adjacent, straining the i.i.d. assumption behind Christoffersen. A moving-block-bootstrap on the OOS violation series (block lengths $L \in \{1, 5, 10\}$, 2,000 reps) places the nominal violation rate $1-\tau$ inside the 95% CI at every $\tau$ and every block length, and the CIs barely widen from $L=1$ to $L=10$ (e.g. $\tau = 0.95$: $[0.044, 0.054]$ at $L=1$, $[0.044, 0.055]$ at $L=10$) — the consecutive-night dependence does not invalidate the coverage claim.

**Per-regime.** `normal` and `high_vol` are near-nominal at every anchor (`normal` 0.691 / 0.853 / 0.951 / 0.992, $n = 4{,}985$; `high_vol` 0.636 / 0.836 / 0.949 / 0.992, $n = 1{,}405$). `earnings_night` (OOS $n \approx 60$ nights) realises 0.767 / 0.967 / 0.983 / 1.000 — over-coverage on the small-$n$ earnings cell, the contract-favourable side of the §8 asymmetry, which tightens as the panel accumulates (§6.5).

**Ex-dividend adjustment.** Because the index factor does not drop for a single name's distribution, the ex-dividend-morning open is reconstructed to its cum-dividend level (`mon_open += dividend`) from scryer `yahoo/corp_actions/v1` on the 241 affected mornings. This removes the deterministic ex-div down-gap — the mean signed standardised residual on those mornings moves from $-0.39$ (a clear downward skew against a dividend-blind factor point) to $+0.12$, in line with the $+0.08$ panel mean — with pooled coverage unchanged. Earnings timing is session-assigned: an after-close (`amc`) release dated $t_0$ or a before-open (`bmo`) release dated $t_1$ fires inside the close$(t_0)$→open$(t_1)$ gap, using the `session` field of scryer `yahoo/earnings/v2`; session timing is complete for reported earnings from 2015 onward, covering the held-out window (a date-only flag that brackets both adjacent nights dilutes the regime with normal nights and is strictly dominated).

## B.16 Within-bin exchangeability — permutation test

Mondrian-CP's finite-sample coverage guarantee depends on within-bin exchangeability of the conformity score. A permutation test on the lag-1 Pearson autocorrelation of the standardised score within each (regime × symbol) bin ($n = 19$–$116$ per bin, 30 bins, OOS 2023+; statistic computed in `fri_ts` order, null distribution from 5,000 within-bin shuffles per bin) finds $1/30$ bins nominally rejecting at $\alpha = 0.05$ and $0/30$ at $\alpha = 0.01$ — *under-rejecting* relative to the $5\%$ / $1\%$ expected under exchangeability. Aggregate KS test of per-bin $p$-values vs Uniform(0,1) is $D = 0.276$, $p = 0.017$, but the deviation is in the under-rejecting direction (too few low $p$-values, too many bins with $p > 0.5$) — consistent with exchangeability holding, not violating. The single nominally-rejecting bin (GLD/normal, lag-1 $\hat\rho = -0.166$) does not survive Benjamini-Hochberg correction across the 30-test grid. The cross-sectional dependence of B.10 / §8 is *across* bins, not within. Source: `reports/tables/paper1_b2_exchangeability.csv`.

## B.17 τ-stratified CUSUM drift bank

Beyond passive forward-tape observation (A.9), the deployed system carries a two-sided Page CUSUM drift monitor at each served $\tau$. With control statistic $X_t = k_w / 10$ (weekend violation rate), reference $\mu_0 = 1 - \tau$, and slack $k = \mu_0 / 2$ tuned to detect a 2× violation-rate shift, calibrated thresholds $h \in \{0.40, 0.40, 0.30\}$ for $\tau \in \{0.85, 0.95, 0.99\}$ produce mean in-control run length $\approx 225$ weekends (one expected false alarm per $\sim 4.3$ years; calibration via 20,000 Monte-Carlo traces × 500 weekends). Detection power against an operationally relevant 2× violation-rate drift: $\sim 83\%$ with median latency 5 / 11 / 28 weekends at $\tau \in \{0.85, 0.95, 0.99\}$; against 3× drift: 2 / 5 / 14 weekends (5,000 traces × 200 weekends; `reports/tables/paper1_c2_cusum_drift.csv`, `paper1_c2_cusum_calibration.csv`).

On the 173-week OOS slice, the $\tau = 0.85$ CUSUM fires $S^+$ alarms at both **2023-03-10** (SVB collapse, $k_w = 7$) and **2024-08-02** (BoJ unwind, $k_w = 10$) — the two canonical stress weekends in the OOS window — with the post-BoJ $S^-$ (over-coverage) alarm at **2024-09-27** catching the over-conservative recovery period documented under the split-anchor robustness battery (Appendix D). CUSUM banks at $\tau \in \{0.95, 0.99\}$ fire on different weekends: pairwise alarm coincidence with $\tau = 0.85$ is **2 of 7 alarms**; pairwise coincidence between $\tau = 0.95$ and $\tau = 0.99$ is **0 of 7 alarms**. Each anchor's monitor surfaces a structurally distinct aspect of drift — body-of-distribution shift at $\tau = 0.85$, near-tail at $\tau = 0.95$, deep-tail mass at $\tau = 0.99$ — confirming the $\tau$-stratified CUSUM bank is a multi-resolution detector rather than a redundant signal. A complementary location-shift CUSUM on the standardised residual mean composes with this bank (Appendix C). Source: `reports/tables/paper1_f1_cusum_alarm_timing.csv`, `paper1_f1_cusum_alarm_proximity.csv`, `paper1_f1_cusum_alarm_coincidence.csv`. The CUSUM bank is operational concurrently with the forward-tape harness and re-uses its weekly ingest path.
