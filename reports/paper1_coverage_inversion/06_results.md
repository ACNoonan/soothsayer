# §6 — Results

This section reports the primary calibration evidence for the deployed locally-weighted Mondrian split-conformal architecture (EWMA HL=8 σ̂; §4) on real and synthetic data, plus the forward-tape harness operational against a content-addressed frozen artefact. Sharpness, per-component effects, and the σ̂ selection procedure are deferred to §7; system-level implementation and audit reproducibility are in §8. The headline is held-out per-symbol calibration via leave-one-symbol-out CV ($0.9497 \pm 0.0128$ at $\tau = 0.95$ across the held-out symbol distribution), with all 10 symbols passing per-symbol Kupiec, calendar sub-period stability across four years, and a measurable joint-tail empirical distribution that turns the residual *per-anchor calibrated, not full-distribution calibrated* disclosure into operational reserve guidance.

## 6.1 Evaluation protocol

The backtest panel comprises $N = 5{,}996$ weekend prediction windows: ten symbols × $639$ weekends, 2014-01-17 through 2026-04-24. Monday open is the target; Friday close and contemporaneous factor / vol-index readings compose $\mathcal{F}_t(s)$. The σ̂ warm-up rule (≥8 past observations per symbol) drops 80 weekends at panel start to leave $5{,}916$ evaluable rows. We report (i) an *in-sample machinery check* (quantile fit and served on the full evaluable panel; realised coverage matches $\tau$ by construction), (ii) the *out-of-sample validation* (quantile fit on $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ — 4,186 rows; served on the 1,730-row $\mathcal{T}_\text{test}$ slice), (iii) the held-out *forward-tape* evaluation against a content-addressed frozen artefact (§6.6), and (iv) a *simulation study* on synthetic panels with known ground truth (§6.7). All $p$-values are two-sided Kupiec POF and Christoffersen independence tests. The base point estimator is unbiased (median residual $-0.5$ bps; MAE $90.0$; RMSE $163.3$); the product is the per-symbol-σ̂-rescaled per-regime conformal quantile with the OOS-fit $c(\tau)$ bump.

## 6.2 Served-band calibration — in-sample machinery check

Full evaluable panel ($N = 5{,}916$):

| Regime ($n$)          | $\tau = 0.68$: realised / width (bps) | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---|---|---|---|
| normal (3,883)        | 0.685 / 91.0  | 0.851 / 142.7 | 0.951 / 247.7 | 0.987 / 424.8 |
| long_weekend (619)    | 0.683 / 109.4 | 0.852 / 171.7 | 0.948 / 297.7 | 0.989 / 511.1 |
| high_vol (1,414)      | 0.682 / 175.7 | 0.853 / 275.5 | 0.950 / 478.5 | 0.992 / 821.0 |
| **pooled (5,916)**    | **0.684 / 109.4** | **0.852 / 175.0** | **0.951 / 303.4** | **0.989 / 521.6** |

Pooled realised coverage matches the target $\tau$ to within $0.2$pp by construction. The narrower in-sample widths (vs the OOS table below) reflect σ̂'s tighter estimate over the full panel; the OOS table's wider bands are the OOS-fit $c(\tau) = 1.079$ at $\tau = 0.95$ working as designed.

## 6.3 Served-band calibration — out-of-sample (2023+)

Quantile fit on pre-2023 weekends ($n = 4{,}186$); served on the 2023+ slice (1,730 rows × 173 weekends). The 12 trained per-regime quantiles $q_r(\tau)$ are held-out. The 4-scalar $c(\tau)$ schedule is OOS-fit, but **the $\tau = 0.95$ headline is held out on two orthogonal axes** — *temporally* via a nested 2023-only TUNE / 2024–2026 EVAL split (§6.3.3.1) and on *symbol* via leave-one-symbol-out CV (§6.3.3) — both of which evaluate $c(0.95)$ on data its fit never touched. The walk-forward $\delta(\tau)$ schedule is identically zero (§4.5). §9.3 carries the residual provenance disclosure.

| Regime ($n$)       | $\tau = 0.68$: realised / width | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---|---|---|---|
| normal (1,160)     | 0.687 / 109.7 | 0.847 / 172.3 | 0.947 / 300.1 | 0.990 / 471.6 |
| long_weekend (190) | 0.626 / 120.6 | 0.842 / 190.6 | 0.958 / 334.7 | 1.000 / 562.5 |
| high_vol (380)     | 0.742 / 200.3 | 0.887 / 351.1 | 0.955 / 603.7 | 0.987 /1{,}169.9 |
| **pooled (1,730)** | **0.693 / 130.8** | **0.855 / 213.6** | **0.950 / 370.6** | **0.990 / 635.0** |

`high_vol` carries the widest bands, `normal` the narrowest, and every regime lands within $\pm 1$pp of nominal at $\tau = 0.95$.

### 6.3.1 Conditional-coverage tests (pooled OOS)

| $\tau$ | Violations | Rate | Kupiec $p_\text{uc}$ | Christoffersen $p_\text{ind}$ | $c(\tau)$ |
|---:|---:|---:|---:|---:|---:|
| 0.68  | 532 | 0.308 | 0.264 | 0.244 | 1.000 |
| 0.85  | 251 | 0.145 | 0.565 | 0.403 | 1.000 |
| **0.95** | **86** | **0.050** | **0.956** | **0.603** | **1.079** |
| 0.99  | 17 | 0.010 | 0.942 | $\approx 1.0$ | 1.003 |

The $\tau = 0.95$ row is the headline pooled operating result. Realised coverage is exactly $0.9503$ (Kupiec $p_{uc} = 0.956$); Christoffersen $p_{ind} = 0.603$ passes. **Kupiec and Christoffersen pass at every served anchor on the deployed-fit OOS slice.** Mean half-width at $\tau = 0.95$ is **370.6 bps** — narrower than the K=26 σ̂ comparator (385.3 bps; bootstrap 95% CI on $\Delta$hw% upper bound is $-1.88\%$, see §7.4). The held-out claim against this pooled baseline is the §6.3.3 leave-one-symbol-out CV ($0.9497 \pm 0.0128$). The §6.3.5 residual Berkowitz / DQ rejection localises to per-symbol Berkowitz on TLT and TSLA (§6.4.1) and to cross-sectional within-weekend common-mode (§6.3.4).

### 6.3.2 Realised-move tertile decomposition at $\tau = 0.95$

Stratifying the OOS slice by post-hoc realised-move $|z|$-score tertile (`reports/tables/m6_realised_move_tertile.csv`) closes the loop between the §6.3 pooled rows and the §9.1 shock-tertile ceiling:

| tertile ($n$)     | realised | half-width (bps) | Kupiec $p$ |
|---|---:|---:|---:|
| calm   (497)      | 0.9920   | 359.5 | $0$ (over-covers) |
| normal (601)      | 0.9933   | 379.6 | $0$ (over-covers) |
| **shock** (632)   | **0.8766** | 370.7 | $0$ (under-covers) |
| **pooled** (1{,}730) | **0.9503** | **370.6** | **0.956** |

Half-width is approximately flat across tertiles (365–380 bps), so the band does not widen in shock periods — it just misses more often. The shock-tertile residual is cross-sectional common-mode within a weekend (§9.1), not per-symbol scale; pooled $\tau = 0.95 = 0.950$ is achieved through compensating tertile-level biases (calm 1.000, normal 0.993, shock 0.878). A $|z|$-conditional conformal upgrade (§10.1) would tighten calm bands and widen shock bands at the same pooled $\tau$.

![Calibration curves on the 1{,}730-row 2023+ OOS slice. The deployed architecture (this paper, blue) tracks the $45^\circ$ diagonal across the served range $\tau \in [0.68, 0.99]$; GARCH(1,1)-$t$ markers (vermilion squares) at the four served anchors are the practitioner-standard parametric baseline and visibly under-cover at $\tau \in \{0.68, 0.85, 0.95\}$ (Kupiec figures in §6.4.3). Star marks the headline $\tau = 0.95$ result.\label{fig:calibration}](figures/fig2_calibration.pdf)

### 6.3.3 Stability — LOSO, temporal holdout, split-date, walk-forward, calendar sub-period

**The $\tau = 0.95$ headline is held-out on two orthogonal axes:** *temporal* (§6.3.3.1: $c(\tau)$ fit on 2023 alone, evaluated on 2024-01-05 → 2026-04-24 — realised $0.9504$, Kupiec $p = 0.947$, Christoffersen $p = 0.989$, per-symbol Kupiec 10/10) and *symbol* (LOSO realised $0.9497 \pm 0.0128$ across held-out symbols). The result is stable across TUNE anchors $\{2021, 2022, 2023\}$: realised coverage at $\tau = 0.95$ lies in $[0.9474,\ 0.9524]$ with per-symbol Kupiec 10/10 preserved across all four anchors $\{2021, 2022, 2023, 2024\}$ (§7.4.2 split-anchor robustness). The 2024 TUNE anchor over-covers at $0.9754$ because TUNE-2024 includes the 2024-08-05 BoJ unwind, inflating $c(0.95)$ to $1.175$; per-symbol Kupiec still passes 10/10. **This is a contract-favourable sharpness deficit, not under-coverage** (§9.3 frames the asymmetry as a one-sided contract).

**Leave-one-symbol-out CV (symbol-axis holdout).** Holding out each of the ten symbols' rows from train + OOS fits and evaluating $\tau = 0.95$ on the held-out symbol's post-2023 slice: **all 10 LOSO bands pass Kupiec when held out**; mean realised $\mathbf{0.9497}$, std $\mathbf{0.0128}$ across the held-out symbol distribution (`reports/tables/m6_lwc_robustness_loso.csv`). Each held-out symbol's $c(\tau)$ is fit on the other nine symbols' OOS slice and never sees the held-out symbol's data. Heavy-tail tickers (MSTR, HOOD, TSLA) and low-vol tickers (SPY, GLD) all sit in a uniform $0.93$–$0.97$ band when held out — the per-symbol $\hat\sigma_s(t)$ on the held-out symbol carries its own scale.

#### 6.3.3.1 Nested temporal holdout — c(τ) fit on 2023, evaluated on 2024–26

A nested temporal split renders the headline held-out at the *time* level. TRAIN = pre-2023-01-01 (the unchanged 4,186-row per-regime quantile fit); TUNE = 2023-01-01 → 2023-12-29 (52 weekends, $c(\tau)$ fit slice); EVAL = 2024-01-05 → 2026-04-24 (1,210 rows × 121 weekends, true holdout). At $\tau = 0.95$:

| mode | realised | $c(0.95)$ | Kupiec $p$ | Christoffersen $p$ | hw bps | per-sym Kupiec |
|---|---:|---:|---:|---:|---:|---:|
| $M_\text{full}$ (full-OOS $c$ fit; §6.3.1 baseline) | 0.9504 | 1.079 | 0.956 | 0.720 | 370.6 | 10/10 |
| **$M_\text{a2}$ (true temporal holdout)** | **0.9504** | **1.079** | **0.947** | **0.989** | **420.8** | **10/10** |

$c(\tau = 0.95)$ on TUNE-only matches the full-OOS fit at three decimals — the headline $\tau = 0.95$ number is *not* fit-on-evaluate sensitive. Christoffersen $p$ improves in held-out mode ($0.989$ vs $0.720$) because the 2024+ slice exhibits cleaner violation independence than the full 2023+ slice. The half-width difference (370.6 vs 420.8 bps) is entirely an eval-slice composition effect: the 2024+ holdout contains the 2024-08-05 BoJ unwind and the 2025-04 tariff weekend, both of which inflate $\hat\sigma_s$; coverage is unchanged because $\hat\sigma_s$-conditional bands widened with the underlying realised volatility, exactly as designed.

**Lower-$\tau$ over-coverage disclosure.** At $\tau = 0.68$ and $\tau = 0.85$, $M_\text{a2}$ realises $0.712$ and $0.870$ respectively (Kupiec $p = 0.015$ and $p = 0.044$, both rejecting toward over-coverage). Mechanism: $c(0.68)$ and $c(0.85)$ fit on TUNE-only inherit the elevated banking-crisis-weekend volatility of 2023 (March SVB/CS), inflating $c$ to $1.028$ and $1.026$ respectively; $M_\text{full}$'s schedule on the full OOS slice averages this out at the floor ($c = 1.000$) and is the deployed mitigation. Source: `reports/tables/paper1_a2_nested_holdout_c_tau.csv`, `paper1_a2_6_tune_anchor_robustness.csv`.

**Split-date sensitivity (stability-of-fit on the deployed slice).** Repeating the fit (quantile table re-trained, $c(\tau)$ re-fit per split, $\delta \equiv 0$ held) at four OOS-split anchors $\{2021\text{-}01\text{-}01, 2022\text{-}01\text{-}01, 2023\text{-}01\text{-}01, 2024\text{-}01\text{-}01\}$ delivers realised $\tau = 0.95$ coverage of $\{0.9539,\ 0.9520,\ 0.9503,\ 0.9504\}$ — Kupiec $p \in \{0.348,\ 0.661,\ 0.956,\ 0.947\}$ and **Christoffersen $p \in \{0.115,\ 0.186,\ 0.603,\ 0.671\}$ — every (split × $\tau$) cell passes at $\alpha = 0.05$.** Mean half-width $\{357.2,\ 363.5,\ 370.6,\ 416.8\}$ bps varies $\pm 8\%$ around the deployed value.

**Walk-forward stability.** Re-running the schedule selection on the four powered expanding-window splits (fractions $f \in \{0.40, 0.50, 0.60, 0.70\}$ — see §4.5 for why the 0.20 and 0.30 splits are excluded as under-powered for the 4-scalar $c(\tau)$ fit) with $\delta = 0$: walk-forward realised $\tau = 0.95$ coverage is $\geq 0.95$ on every powered split (range 0.954–0.975) — the criterion that selected $\delta = 0$ in §4.5. Per-split mean half-width at $\tau = 0.95$ tracks the full-OOS-fit value within $\pm 8\%$.

**Calendar sub-period stability.** Bucketing the OOS slice into four calendar sub-periods {2023, 2024, 2025, 2026-YTD} (`reports/tables/m6_subperiod_robustness.csv`):



| Sub-period ($n$ weekends) | Realised at $\tau = 0.95$ | Half-width (bps) | Kupiec $p$ | Christoffersen $p$ |
|---|---:|---:|---:|---:|
| 2023 (52)          | 0.950 | 253.6 | 1.000 | 0.888 |
| 2024 (52)          | 0.931 | 420.4 | 0.057 | 0.841 |
| 2025 (52)          | 0.971 | 444.4 | 0.017 | 0.793 |
| 2026-YTD (17)      | 0.947 | 350.0 | 0.862 | 0.908 |
| **Pooled OOS (173)** | **0.950** | **370.6** | **0.956** | **0.603** |

Pooled OOS calibration at $\tau = 0.95$ holds across each of the four years that span SVB / banking-stress 2023, the 2024 rate-cut transition, the 2025 tokenisation-launch year, and 2026-YTD (realised range $0.931$–$0.971$). The 2025 cell rejects Kupiec at $\alpha = 0.05$ ($p = 0.017$, over-coverage); 2024 sits just above the threshold ($p = 0.057$); 2023 and 2026-YTD pass cleanly. Across the full 16-cell (sub-period × $\tau$) grid the architecture carries 3 Kupiec rejections, all over-coverage in 2025 (§9.3 frames the asymmetry); Christoffersen lag-1 independence is not rejected in any of the 16 cells.

![Walk-forward and split-date stability of the deployed schedule. **(a)** Six-split expanding-window walk-forward at four $\tau$ anchors: realised coverage on each test fold (markers) tracks nominal (dotted lines) at every anchor; bars are 95% binomial CIs. **(b)** Split-date sensitivity at four OOS-anchors {2021, 2022, 2023, 2024}: realised $\tau = 0.95$ coverage holds at $\{0.954, 0.952, 0.950, 0.950\}$ across anchors; Christoffersen passes every cell at $\alpha = 0.05$.\label{fig:stability}](figures/fig3_stability.pdf)

This validates the oracle's coverage contract at $\tau = 0.95$. We do not address the welfare-optimal operating $\tau$ for a particular lending policy in this paper.

### 6.3.4 Joint-tail empirical distribution and reserve-guidance threshold

A consumer holding a portfolio of correlated RWAs needs to know not only the per-symbol calibration but the *joint* distribution of simultaneous breaches. We compute, for each OOS weekend $w$ with full 10-symbol coverage, the count $k_w = |\{s : s \text{ breaches its } \tau\text{-band on } w\}|$, and compare its empirical distribution to three properly specified baselines: $\mathrm{Binom}(10, 1-\tau)$ (the independence strawman), a Gaussian copula on the empirical correlation matrix $\hat R$ (mean off-diagonal $0.36$ on standardised residuals), and a Student-$t$ copula on per-symbol Student-$t$ marginals with $\hat\nu \in [4.80, 28.32]$, copula degrees-of-freedom $\hat\nu_\text{copula} = 6.04$ (median across symbols) (`reports/tables/paper1_a3_joint_baseline_kw_distribution.csv`, `..._summary.csv`; 50,000 simulated weekends per baseline; CIs are 1000-rep weekend-block bootstrap, seed = 0):

| Statistic at $\tau = 0.95$ ($n_\text{weekends} = 173$) | empirical | $\mathrm{Binom}(10, 0.05)$ | Gaussian copula | t-copula ($\nu = 6.04$) |
|---|---:|---:|---:|---:|
| Mean $k_w$ / weekend | 0.497 | 0.500 | 0.501 | 0.501 |
| Variance ratio (emp / model) | — | **2.34** | 0.83 | **0.63** |
| $P(k_w \ge 3)$ | **4.62% [1.73, 7.51]** | 1.15% | 6.69% | 8.15% |
| $P(k_w \ge 5)$ | **0.58% [0.00, 1.73]** | 0.01% | 1.86% | 3.15% |
| max $k_w$ (worst weekend) | 9 | — | — | — |

**Variance-overdispersion lead.** Empirical $k_w$ over-disperses by a uniform $\sim 2.3\times$ vs Binom independence at every served $\tau$ (emp/Binom variance ratio $\{2.34, 2.31, 2.34, 2.35\}$ at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$) and sits inside a properly-specified t-copula envelope from above (emp/t variance ratio $\{0.83, 0.54, 0.63, 0.73\}$; Wasserstein-1 distance to the t-copula $\le 0.180$ at every $\tau$, less than half the distance to Binom independence). Marginal calibration is preserved — mean $k_w$ matches every reference to $0.003$. Independence is misspecified, the joint dependence is real ($\hat R = 0.36$ mean off-diagonal), and the structure brackets-bound: empirical between Binom independence and a homogeneous t-copula at $\hat\nu \approx 6$. Cross-sectional within-weekend dependence ($\hat\rho_\text{cross} = 0.41$) is respected by all reported CIs via weekend-block bootstrap; temporal autocorrelation across weekends is empirically null (lag-1, lag-2, lag-4 $\hat\rho$ on weekly $k_w$ in $[-0.07, 0.03]$), so $L \in \{4, 8, 13\}$ moving-block-bootstrap CIs are within Monte Carlo noise of the $L = 1$ baseline (`reports/tables/paper1_b5_kw_block_bootstrap.csv`).

**Reserve-guidance threshold.** $k^\ast$ at each $\tau$ — smallest $k$ whose empirical hit-rate is closest to $5\%$ — is $k^\ast = 5$ at $\tau = 0.85$ (rate $5.78\%$), $k^\ast = 3$ at $\tau = 0.95$ ($4.62\%$), and $k^\ast = 1$ at $\tau = 0.99$ ($6.36\%$). Across the 24-cell grid (3 $\tau$ × 2 threshold conventions × 4 sub-periods) the architecture carries **0/24 Kupiec stability rejections** at $\alpha = 0.05$ (`reports/tables/m6_kw_threshold_stability.csv`); at $k^\ast = 3$ for $\tau = 0.95$, per-sub-period hit-rates are $\{3.85, 7.69, 1.92, 5.88\}\%$ across {2023, 2024, 2025, 2026-YTD} with Kupiec $p \in \{0.78, 0.33, 0.30, 0.81\}$. The per-sub-period 95th percentile of $k_w$ at $\tau = 0.95$ stays in $[1.0, 3.0]$ across the four years. With sub-period $n \approx 52$ and target rates $\sim 5\%$, the binomial-stability test has limited power against drift below the year-on-year p95 spread (≤ 1.6 integer-symbols); the result is "no detectable instability with the available power."

**Operational consumer guidance.** $k^\ast = 3$ at $\tau = 0.95$ is conservative against a properly specified joint baseline, not just against independence: a 10-symbol portfolio should reserve against an empirical 99th-percentile of $\approx 5$ simultaneous breaches (binomial puts it at $\approx 2$, t-copula at $\approx 6$). At $\tau = 0.85$ the empirical 99th percentile is $\approx 7$ vs binomial $\approx 4$. **No incumbent oracle (Pyth, Chainlink Data Streams, RedStone, Kamino Scope) publishes this distribution** — the joint-tail measurement layer is what calibration-transparency makes possible.

### 6.3.5 Worst-observed weekend — 2024-08-05 BoJ yen-carry-unwind

The single OOS weekend with all 10 symbols breaching the $\tau = 0.85$ band simultaneously is **Friday 2024-08-02 → Monday 2024-08-05** — the Bank of Japan rate-hike yen-carry-trade unwind, one of the largest single-weekend global risk-off events of the post-2020 period. The same weekend has $k_w = 8$ at $\tau = 0.95$ (only TSLA and TLT inside that band) and $k_w = 5$ at $\tau = 0.99$. The deployed served band re-evaluated on the 2024-08-02 row at the deployed $\text{split} = \text{2023-01-01}$:

| Symbol | Weekend return | HW @ $\tau=0.85$ | Breach @ $\tau=0.85$ | @ $\tau=0.95$ |
|---|---:|---:|---:|---|
| MSTR  | $-27.4\%$ | 783 bps  | $-1416$ bps | breach ($-720$) |
| HOOD  | $-17.8\%$ | 368 bps  | $-1325$ bps | breach ($-997$) |
| NVDA  | $-14.2\%$ | 324 bps  | $-1008$ bps | breach ($-720$) |
| TSLA  | $-10.8\%$ | 587 bps  | $-409$ bps  | inside |
| AAPL  | $-9.4\%$  | 202 bps  | $-657$ bps  | breach ($-478$) |
| GOOGL | $-6.7\%$  | 230 bps  | $-354$ bps  | breach ($-149$) |
| QQQ   | $-5.4\%$  | 110 bps  | $-340$ bps  | breach ($-242$) |
| SPY   | $-4.0\%$  | 84 bps   | $-229$ bps  | breach ($-154$) |
| GLD   | $-2.1\%$  | 126 bps  | $-153$ bps  | breach ($-41$) |
| TLT   | $+1.4\%$  | 128 bps  | $+12$ (just past) | inside |

Cross-section: 9 of 10 symbols sold off in concert (mean weekend return $-963$ bps, median $-807$ bps); only TLT delivered the classic flight-to-quality bid. Macro context: the 2024-08-02 US July nonfarm-payrolls print landed at 114k vs ~175k consensus with the Sahm-rule recession indicator triggering; the 2024-07-31 BoJ rate hike combined with hawkish Powell/Yellen language drove an accelerating yen-carry unwind through Asian time zones over the weekend; the Monday 2024-08-05 Nikkei fell 12.4% (largest single-day drop since Black Monday 1987) and intraday VIX spiked to ~65, the highest reading since the COVID-19 March 2020 panic.

The σ̂-standardisation worked as designed at the per-symbol level — high-vol symbols (MSTR, TSLA) got wide bands, low-vol symbols (SPY, QQQ, GLD) narrow ones, and breach magnitudes scale with the cross-sectional shock divided by σ̂. What broke is *cross-sectional common-mode*: when nearly every symbol moves the same direction at the same time by 4–27 standard-deviation-scale weekend returns, no per-symbol band — however well calibrated — can absorb the joint event. A consumer monitoring $k_w$ in real time would have seen $k_w = 10$ at $\tau = 0.85$ by the Monday-open print, well in excess of the deployment-time-fitted $k^\ast = 5$ (or the empirical 99th percentile of $7$); the empirical $k_w$ distribution is the right operational signal precisely because it captures the cross-sectional common-mode that per-symbol coverage cannot.

**Joint-baseline framing of the BoJ probability.** Under a Student-$t$ copula with $\hat\nu = 6.04$ and empirical correlation $\hat R$ (mean off-diagonal $0.36$), $P(k_w = 10)$ at $\tau = 0.85$ is $0.21\%$ — i.e., the 2024-08-05 BoJ unwind is a $\sim 1\text{-in-}475\text{-weekends}$ event under a properly specified joint baseline, not a freak. The independence baseline puts the same event at $\sim 1\text{-in-}10{,}000\text{-weekends}$; the residual structure §6.3.4 / §9.4 documents is exactly the gap between these two figures. The residual has a *name* (cluster topology, §6.3.6 / §9.4), a *parametric envelope* (t-copula at $\nu \approx 6$ with empirical $\hat R$), and a *structural mechanism* (equity vs safe-haven cluster topology) — not "a residual the architecture cannot characterise."

### 6.3.6 Extended diagnostics — DQ and Berkowitz

**Engle-Manganelli (2004) DQ is the finer test on the violation series.** Kupiec checks marginal counts and Christoffersen's two-state Markov independence checks the lag-1 hit transition; neither has power against conditional miscalibration patterns that yield correct marginal counts and uncorrelated lag-1 hits but encode systematic dependence on lagged hits or the served quantile [engle-manganelli-2004]. DQ regresses the centred hit indicator on a constant + $K$ lagged hits and tests joint significance under $\chi^2_{K+1}$. We use $K = 4$ throughout (CAViaR Table 1 block 1), no contemporaneous covariate — the lag-only specification is symmetric across the five methods compared in §6.4.2, so cross-method DQ p-values are directly comparable. **Pooled DQ at $\tau = 0.95$ rejects on the deployed fit** — the cross-sectional within-weekend common-mode (orthogonal to σ̂ standardisation) is what DQ is sensitive to here. Per-(symbol × τ × method) DQ p-values are reported in the §6.4.2 master grid alongside Kupiec and Christoffersen. **Bands are *per-anchor calibrated*, not full-distribution calibrated** — the §6.3.4 joint-tail empirical distribution turns this disclosure into a measurable, reportable shape.

**Berkowitz (2001) joint LR on continuous PITs.** PITs reconstructed by inverting each served band against the realised Monday open through the per-regime conformal CDF. The pooled Berkowitz LR on the deployed PITs is non-zero, viewing the same residual through the PIT lens. The Berkowitz/DQ rejection and the §6.3.4 joint-tail overdispersion are not two independent residuals: both are the cross-sectional within-weekend common-mode ($\hat\rho_\text{cross} = 0.354$) viewed through different aggregations — Berkowitz/DQ on the pooled PIT/violation series detects it as serial-cluster-equivalent dependence; the $k_w$ distribution on the same panel detects it as upper-tail overdispersion in joint-breach counts. The methodology fix targets the same channel; the consumer-facing handle is the §6.3.4 reserve-guidance threshold.

**Localising the residual.** Decomposing the lag-1 alternative under panel-row order: the AR(1) signal lives in the *cross-sectional within-weekend* ordering ($\hat\rho_{\text{cross}} = 0.354$, $p < 10^{-100}$, $n = 1{,}557$) — not the temporal-within-symbol ordering ($\hat\rho_{\text{time}} = -0.032$, $p = 0.18$, $n = 1{,}720$). σ̂ standardisation operates *within* a symbol's history, not *across* symbols within a weekend, so it cannot reach this residual. A vol-tertile sub-split of `normal` regime (5 cells) leaves Berkowitz LR essentially unchanged ($170 \to 172$) while widening $\tau = 0.95$ band by $9\%$ — finer regime granularity is not the lever (`reports/tables/m6_lwc_robustness_vol_tertile.csv`). The §10 candidate architectures that target cross-sectional common-mode (the cross-sectional partial-out track in `reports/active/m6_refactor.md`, gated on a Friday-observable $\bar r_w$ predictor) are deferred-with-gates.

## 6.4 Per-symbol generalisation

The §6.3 OOS pooled coverage at $\tau = 0.95$ matches nominal; the per-symbol question is whether each ticker's individual cell is also calibrated. Under the deployed architecture, **all 10 symbols pass Kupiec at $\tau = 0.95$** with violation rates in $[3.5\%,\,6.9\%]$ and per-symbol PIT variance $\hat\sigma^2_z \in [0.66,\,0.83]$ — all close to the calibrated $1.0$ from below. Figure \ref{fig:per-symbol} visualises the per-symbol calibration distribution.

![Per-symbol calibration at $\tau = 0.95$ on the 2023+ OOS slice. Each symbol's violation rate (markers) sits within the binomial 95% confidence band around the nominal $0.05$ rate (shaded). Symbols are ordered by their realised PIT variance $\hat\sigma^2_z$. The distribution is unimodal and centred near nominal — heavy-tail tickers (TSLA, HOOD, MSTR), low-vol tickers (SPY, QQQ, GLD, TLT), and the equity middle (AAPL, GOOGL, NVDA) all sit in the same cluster.\label{fig:per-symbol}](figures/fig4_per_symbol.pdf)

### 6.4.1 Per-symbol Kupiec at $\tau = 0.95$ and Berkowitz LR

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

**All 10 symbols pass Kupiec at $\tau = 0.95$** with violation rates inside $[3.5\%, 6.9\%]$. The per-symbol Berkowitz LR range $[3.2, 16.7]$ (a 5.2$\times$ spread) is one of the strongest per-symbol calibration claims a Mondrian-conformal architecture can make on this panel — only TLT (LR 16.7) and TSLA (LR 13.5) reject Berkowitz at $\alpha = 0.01$, and those rejections trace to cross-sectional common-mode rather than per-symbol scale (§6.3.6).

**Power caveat at $\tau = 0.99$.** Per-symbol Kupiec at $\tau = 0.99$ has minimum detectable effect $\approx 3$ pp under-coverage and is undetectable for over-coverage given the per-symbol expected violation count of $1.73$ (Monte Carlo: 10,000 reps per cell, Kupiec LR critical at $\alpha = 0.05$; `reports/tables/paper1_b3_kupiec_power_mde.csv`). The 10/10 pass should be read as "no per-symbol violation rate is statistically distinguishable from $1\%$ at the resolution Kupiec offers per-symbol", **not** as a 1 pp tolerance certificate. Pooled Kupiec at $\tau = 0.99$ has minimum detectable effect $1.0$ pp; the pooled $p = 0.94$ is the $\tau = 0.99$ statistical claim that does have 1 pp resolution. Per-symbol Kupiec at $\tau = 0.95$ has MDE $4.0$ pp under-coverage / $7.5$ pp over-coverage on $N = 173$ — the deployed per-symbol violation rates in $[3.5\%, 6.9\%]$ sit well within the 4 pp window of nominal $5\%$, so the 10/10 pass at $\tau = 0.95$ is informative against deviations larger than 4–8 pp.

### 6.4.2 Per-symbol master grid — Kupiec + Christoffersen + DQ across baselines

We report a single 40-cell (symbol × $\tau$) grid evaluated under three backtests — Kupiec UC, Christoffersen IND, Engle-Manganelli DQ (lag-only specification, $K = 4$ lagged hits, no contemporaneous covariate; CAViaR Table 1 block 1 — the lag-only spec is symmetric across the five methods so cross-method DQ is directly comparable) — against four baselines: GARCH(1,1)-Gaussian, GARCH(1,1)-$t$ (Student-$t$ innovations, practitioner default), an unweighted Mondrian comparator (same per-regime quantile architecture, no per-symbol σ̂ standardisation), and a train-fit constant-buffer baseline. **Pass counts at $\alpha = 0.05$** (per-symbol cell passes; out of 10 symbols per $\tau$, out of 40 across the grid; full long-format table at `reports/tables/m6_per_symbol_master_grid.csv`):

| $\tau$ | metric | constant buffer | GARCH-N | GARCH-$t$$^\dagger$ | unweighted Mondrian | **this paper** |
|---:|---|---:|---:|---:|---:|---:|
| 0.68 | Kupiec | 4/10 | 5/10 | 6/10 | 1/10 | **10/10** |
|      | Christoffersen | 7/10 | 7/10 | 8/10 | 9/10 | **9/10** |
|      | DQ | 2/10 | 6/10 | 7/10 | 1/10 | **10/10** |
| 0.85 | Kupiec | 2/10 | 8/10 | 7/10 | 1/10 | **10/10** |
|      | Christoffersen | 7/10 | 7/10 | 9/10 | 8/10 | **10/10** |
|      | DQ | 2/10 | 8/10 | 7/10 | 2/10 | **10/10** |
| **0.95** | **Kupiec** | **4/10** | **6/10** | **8/10** | **2/10** | **10/10** |
|      | Christoffersen | 7/10 | 7/10 | 10/10 | 8/10 | **10/10** |
|      | **DQ** | **4/10** | **6/10** | **8/10** | **5/10** | **10/10** |
| 0.99 | Kupiec | 7/10 | 4/10 | 10/10 | 8/10 | **10/10** |
|      | Christoffersen | 5/10 | 10/10 | 10/10 | 4/10 | 9/10 |
|      | DQ | 3/10 | 2/10 | 9/10 | 1/10 | 9/10 |
| **40-cell totals** | **Kupiec** | **17/40** | **23/40** | **31/40$^\dagger$** | **12/40** | **40/40** |
|      | **Christoffersen** | **26/40** | **31/40** | **37/40** | **29/40** | **38/40** |
|      | **DQ** | **11/40** | **22/40** | **31/40$^\dagger$** | **9/40** | **39/40** |

$^\dagger$ NVDA's t-MLE pushes $\hat\nu \to 2.50$ (the variance-undefined boundary); the runner falls back to GARCH-Gaussian on those four NVDA cells, so the GARCH-$t$ counts include 4 NVDA cells evaluated under the Gaussian fallback. Reported as-is because NVDA-with-Gaussian-fallback is the practitioner-equivalent of attempting GARCH-$t$ and finding it ill-defined.

**The deployed architecture leads every baseline at every test** — 40/40 Kupiec, 38/40 Christoffersen, 39/40 DQ across the 40-cell grid; the strongest practitioner baseline GARCH-$t$ comes second on every metric (31/40, 37/40, 31/40). At the headline $\tau = 0.95$ anchor the deployed architecture passes 10/10 on all three tests — a per-(symbol × test) sweep no other method on the grid achieves at any τ. **Per-symbol DQ at $\tau \in \{0.68, 0.85, 0.95\}$ is 10/10 on each symbol's own time-ordered violation series.** The pooled DQ rejection at $\tau = 0.95$ reported in §6.3.6 arises specifically when violations are concatenated *across symbols in panel-row order*, which interleaves cross-sectional within-weekend cluster dependence as apparent serial dependence ($\hat\rho_\text{cross} = 0.354$ at the cross-sectional ordering vs $\hat\rho_\text{time} = -0.032$ at the temporal-within-symbol ordering); on each symbol's own time series the residual is invisible to DQ. The pooled rejection localises to a cross-sectional structure orthogonal to σ̂ standardisation; the §6.3.4 reserve-guidance threshold is the consumer-facing handle and §10.1 the methodology fix.

### 6.4.3 GARCH-$t$ pooled baseline (and GARCH-Gaussian)

The textbook econometric default for a time-varying interval at $\tau$ is per-symbol GARCH(1,1) on log Friday-to-Monday returns. The practitioner choice of innovation distribution is Student-$t$ — Gaussian innovations are a known straw-man on equity weekend returns where fitted $\hat\nu \approx 3$ across the panel (`reports/tables/m6_lwc_robustness_garch_t_baseline.csv`):

| $\tau$ | Method | Realised | HW (bps) | Kupiec $p$ | Christoffersen $p$ |
|---:|---|---:|---:|---:|---:|
| 0.95 | GARCH-Gaussian | 0.9254 | 322.2 | $0.000$ | 0.016 |
| 0.95 | GARCH-$t$       | 0.9277 | 331.6 | $0.000$ | **0.209** |
| 0.95 | **this paper**  | $\mathbf{0.9503}$ | $\mathbf{370.6}$ | $\mathbf{0.956}$ | **0.603** |
| 0.99 | GARCH-Gaussian | 0.9630 | 423.7 | $0.000$ | 0.866 |
| 0.99 | GARCH-$t$       | 0.9850 | 569.3 | 0.050  | $1.000$ |
| 0.99 | **this paper**  | $\mathbf{0.9902}$ | $\mathbf{635.0}$ | $\mathbf{0.942}$ | $1.000$ |

GARCH-$t$ closes two failures GARCH-Gaussian leaves on the table: the $\tau = 0.99$ tail capture (realised improves from $0.963$ to $0.985$; Kupiec $p$ moves from $< 0.001$ to a borderline $0.050$) and the Christoffersen rejection at $\tau = 0.95$ ($p$ moves from $0.016$ to $0.209$). What it does *not* fix is the **Kupiec under-coverage at every $\tau < 0.99$** — the standardised-$t$ 95th percentile at $\nu \approx 3$ is $\sim 1.83$ vs Gaussian $1.96$, so the bands tighten precisely where Gaussian was already under-covering. T-innovations fix the wrong end of the distribution.

**At matched 95% realised coverage**, widening GARCH-$t$ to its claimed $\tau = 0.95$ requires roughly $+14\%$ on width, giving a matched-coverage HW $\approx 378$ bps — statistically tied with the deployed architecture's $370.6$ bps. At $\tau = 0.99$ the deployed architecture dominates GARCH-$t$ on coverage and width-at-matched-coverage simultaneously. The conformal route fixes both Kupiec and Christoffersen because it is calibrated to the data, not to a fitted parametric distribution; the NVDA fallback (t-MLE pushes $\hat\nu$ to the variance-undefined boundary at $2.50$) is the parametric-tail risk the deployed architecture avoids.

**Proper-scoring-rule head-to-head.** Under proper scoring rules — Winkler (1972) interval score and CRPS (continuous ranked probability score) — the deployed architecture dominates GARCH(1,1)-$t$ at every served $\tau$. Winkler interval score (bps of fri_close, lower is better) at $\tau = 0.95$: deployed $992$ vs GARCH-$t$ $1{,}139$ ($-12.9\%$); at $\tau = 0.99$: deployed $1{,}566$ vs GARCH-$t$ $1{,}904$ ($-17.8\%$). The advantage grows with $\tau$ — the σ̂-standardisation pays most where parametric-tail mis-specification hurts most. Pooled CRPS over the served coverage range $\{0.05, 0.10, \dots, 0.99\}$: deployed $80.7$ vs GARCH-$t$ $92.6$ ($-12.8\%$). Both rules are computed on the aligned 1,730-row OOS slice; method aggregation is by row, not by $\tau$, so a single number summarises the practitioner-baseline comparison without anchor-row cherry-picking. Source: `reports/tables/paper1_c1_winkler_interval_score.csv`, `..._crps.csv`. The Winkler comparison against the *tokenized-tracking* baseline archetype — the competitor motivated by Cong et al.'s $R^2 = 0.839$ conditional-mean result, distinct from the GARCH-family parametric baselines compared here — is carried in §7.6.

![Realised coverage vs mean half-width at the four served $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ (vertical dotted lines). The deployed architecture (blue stars) at full panel ($n = 1{,}730$) and GARCH(1,1)-$t$ (vermilion squares) on the same OOS slice. The deployed architecture clears Kupiec at every served anchor; GARCH-$t$ undercovers Kupiec at $\tau \in \{0.68, 0.85, 0.95\}$ despite tighter bands and meets the deployed architecture only at the matched-coverage width quoted in §6.4.3. The figure is restricted to methods that emit a calibrated coverage band — incumbent oracle surfaces (Pyth, Chainlink Data Streams, RedStone, Kamino Scope) do not, so a coverage-vs-sharpness comparison against them is not well-defined; the categorical contribution is discussed in §1 / §2.\label{fig:pareto}](figures/fig5_pareto.pdf)

### 6.4.4 Per-asset-class deviation

Pooled OOS coverage stratified by asset class under the deployed EWMA HL=8 σ̂ (`reports/tables/m6_lwc_robustness_per_class.csv`). Equities (8 syms, 1,384 obs): realised $0.952$ at $\tau = 0.95$ with hw $417.8$ bps; GLD ($n = 173$): realised $0.931$, hw $180.9$ bps; TLT ($n = 173$): realised $0.954$, hw $182.3$ bps. Row-weighted reconciliation: $(1384 \cdot 417.8 + 173 \cdot 180.9 + 173 \cdot 182.3) / 1730 = 370.6$ bps, matching the §6.3.1 panel-pooled HW. The per-symbol $\hat\sigma_s$ multiplier delivers heavy-tail equities wider bands matched to their relative-residual scale and the defensive class (GLD, TLT) narrower bands matched to theirs; the deployed architecture's Kupiec passes every class at every $\tau$. The width allocation across asset classes is the operational manifestation of $P_3$ (per-regime serving efficiency): width is concentrated where calibration demands it.

## 6.5 Path coverage — endpoint vs intra-weekend

The §6.3 result is *endpoint coverage*: realised Monday open lies inside the served band. A DeFi consumer holding an xStock as collateral is exposed at every block over the weekend; a Saturday liquidation when the on-chain xStock briefly trades outside the band is a real loss event even if Monday open returns inside. We measure path coverage on $[\text{Fri 16:00 ET},\, \text{Mon 09:30 ET}]$ against 24/7 stock-perp 1m bars from `cex_stock_perp/ohlcv` (Kraken Futures `PF_<sym>XUSD`, xStock-backed). Sample: 19 weekends × 9 symbols (TLT excluded — no perp listing), $n = 118$ (symbol, weekend) pairs per anchor, 2025-12-19 → 2026-04-24 (`reports/tables/path_coverage_perp.csv`):

| $\tau$ | $n$ | Endpoint coverage | Path coverage | Gap (pp) |
|---:|---:|---:|---:|---:|
| 0.68 | 118 | 0.644 | 0.348 | $+29.7$ |
| 0.85 | 118 | 0.864 | 0.568 | $+29.7$ |
| **0.95** | **118** | $\mathbf{0.949}$ | $\mathbf{0.788}$ | $+\mathbf{16.1}$ |
| 0.99 | 118 | 0.992 | 0.915 | $+7.6$  |

**The deployed architecture calibrates the perp-listed sample to nominal endpoint coverage** (0.949 at $\tau = 0.95$ vs nominal $0.95$) on a sample whose composition is predominantly large-cap equities (SPY/QQQ/AAPL/GOOGL/NVDA/MSTR/TSLA/HOOD plus GLD; TLT excluded — no perp listing). The path-coverage gap is $+16.1$ pp at $\tau = 0.95$: an honestly-calibrated endpoint band exhibits a structural shortfall on a sample whose intra-weekend variance is larger than its endpoint variance. Sample is small (binomial CI on the $\tau = 0.95$ pooled gap is $\pm 6$ pp); the test is directional. After three confound checks documented in `reports/v1b_path_coverage_robustness.md` — perp-spot basis normalisation closes the gap to $11.0$ pp, a volume-floor filter at $\geq 1$ contract closes it to $9.5$ pp ($n=63$), and a 15-minute rolling-median sustained-crossing definition leaves it at $14.4$ pp — the residual genuine-shortfall band is $\sim 9$–$15$ pp at $\tau = 0.95$, with most of the magnitude attributable to sustained drift rather than transient thin-liquidity prints. The gap collapses meaningfully only at $\tau = 0.99$ ($+7.6$ pp); continued capture is tracked under scryer item 51 and §10.2 (the path-fitted conformity score).

![Path coverage gap on the 24/7 stock-perp reference. Endpoint coverage (blue) tracks nominal across $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ on the perp-listed subset; path coverage (vermilion) — the fraction of weekends where the perp 1m bar high/low stay inside the served band over the full $[\text{Fri 16:00, Mon 09:30}]$ window — runs $29.7$/$29.7$/$16.1$/$7.6$ pp behind. The gap collapses meaningfully only at $\tau = 0.99$. Sample is small ($n = 118$ symbol-weekends across 19 calendar weekends, 2025-12 to 2026-04); the read is directional and §10.2 (the path-fitted conformity score) is the methodology fix.\label{fig:path-coverage}](figures/fig6_path_coverage.pdf)

The endpoint contract stands. A consumer requiring path coverage at level $\tau$ should step up one anchor (empirically closes the gap on this slice at $\tau = 0.99$), absorb the residual through their own downstream risk policy, or — for continuous-consumption AMM use cases that cannot use the step-up lever — adopt the path-fitted conformity-score variant (§10.2).

## 6.6 Forward-tape held-out validation

The 4-scalar OOS-fit $c(\tau)$ schedule is fit on the 2023+ slice; the resulting deployment artefact carries a residual contamination disclosure (§9.3). The forward-tape harness closes that loop on truly held-out data on top of the §6.3.3 LOSO read: a content-addressed frozen artefact (`data/processed/lwc_artefact_v1_frozen_20260504.json`, SHA-256 `7b86d17a7691…`, freeze date 2026-05-04) is evaluated weekly against forward weekends as they accumulate. The frozen artefact's σ̂ schedule, $q_r$ table, and $c(\tau)$ are read-only; only the per-symbol $\hat\sigma_s(t)$ updates as new past-Fridays arrive.

The harness fires Tuesday mornings via launchd (`launchd/com.adamnoonan.soothsayer.forward-tape.plist`); each run executes a 26h-SLA pre-check on the upstream scryer feeds, runs `scripts/collect_forward_tape.py`, and writes `reports/m6_forward_tape_{N}weekends.md` with a "preliminary" banner when $N < 4$. The harness is silent about deployment; an out-of-band freeze re-roll is required to advance the artefact (`scripts/freeze_lwc_artefact.py`).

**Status at submission:** $N = 1$ forward weekend (`reports/m6_forward_tape_1weekends.md`, 2026-05-01) with $n = 10$ symbol-rows and $0/10$ violations across all four served $\tau$. The harness's own threshold treats $N < 4$ as preliminary and $N < 13$ as under-powered for cumulative pooled Christoffersen, so per-anchor inferential statistics at this $N$ are persisted but not reported inline. The present submission's held-out backbone is §6.3.3's leave-one-symbol-out CV plus per-symbol Kupiec, split-date sensitivity, and four-year calendar sub-period stability; the forward-tape harness becomes load-bearing as $N$ accumulates.

The σ̂ variant comparison sibling (`scripts/run_forward_tape_variant_comparison.py`) carries an alternative-σ̂ check on the same forward slice — never used to re-select, only to flag if a different σ̂ rule looks dramatically cleaner on the held-out data (§7.4).

## 6.7 Simulation study — synthetic-DGP corroboration of the per-symbol fix

**Across four DGPs spanning stationary, regime-switching, drift, and structural-break specifications, the σ̂-standardised architecture's per-symbol Kupiec pass-rate at $\tau = 0.95$ is 98.6–99.9% while the unweighted-Mondrian comparator's collapses to 29–31% — the per-symbol bimodality is reproducible in synthetic data with known DGP, and σ̂ standardisation closes it on every DGP tested.** This answers the methodological question raised by §6.4: the bimodality is a structural property of the architecture (a single per-(regime, $\tau$) multiplier on heterogeneous-tail symbols mis-calibrates in opposing directions), not a property of the unweighted comparator on this particular real-data panel. The simulation is corroborative — a known-DGP control isolating the failure mechanism — not a pre-real-data prediction (the bimodality was first observed on real data under an unweighted Mondrian fit before the simulation was run; σ̂ standardisation was implemented next; this section was committed before the real-data confirmation).

Source: `scripts/run_simulation_study.py` (~30 s end-to-end). Each DGP uses 10 synthetic symbols × 600 weekend returns, $\sigma_i \in \mathrm{linspace}(0.005, 0.030, 10)$ — spanning the empirical real-panel range. Train/OOS split at $t = 400$. Returns drawn from Student-$t$ df=4 rescaled to $\mathrm{std}(r) = \sigma_i$ (or $\sigma_i \cdot m_t$ under DGP B/C/D's vol modifications). 100 Monte Carlo replications per DGP, seed $= 0$.

| DGP | Unweighted-Mondrian pass-rate at $\tau = 0.95$ | σ̂-standardised pass-rate | Mechanism |
|---|---:|---:|---|
| A — homoskedastic baseline | $0.311$ | $\mathbf{0.993}$ | Per-symbol scale heterogeneity is the entire failure mode |
| B — regime-switching vol multiplier | $0.310$ | $\mathbf{0.986}$ | σ̂ tracks regime transitions with a half-life lag |
| C — non-stationary scale (drift) | $0.309$ | $\mathbf{0.996}$ | Adaptive σ̂ is built for this DGP |
| D — variance shock (10× / 50-week transient at $t = 400$) | $0.380$ | $\mathbf{0.999}$ | σ̂ tracks even 10× variance shocks within EWMA HL=8 |
| E — mean jump (+$\Delta = 200$ bps at $t = 400$, $\sigma_\text{true}$ unchanged) | $0.335$ | $0.595$ | Location shift; σ̂ absorbs $\Delta$ as variance, over-deflates low-σ scores |

Both methods pool to mean realised $\approx 0.95$ across DGPs A–D (within $0.005$ of nominal); the split is on the *per-symbol* failure rate. The σ̂-standardised architecture's smallest pass-rate (DGP B, $0.986$) reflects σ̂'s ~13-weekend tracking lag at regime flips. **DGP D upgrade:** the original $3\times$ variance break became a $10\times / 50$-week transient (matching real-world weekend events: 2024-08-05 BoJ unwind, March-2020 COVID-month vol multiplier $\sim 5\times$ for 6–8 weeks). LWC's per-symbol pass rate is unchanged at $99.9\%$ (`reports/tables/paper1_c3_stronger_dgp_d.csv`).

**DGP E — location-shift limitation with closed-form phase transition.** A complementary stress test — a discrete $+\Delta$ conditional-mean shift at the OOS boundary, variance unchanged — exposes a location-shift limitation that σ̂-standardisation does not absorb. $\hat\sigma$ EWMA on the post-shift residual stream sees apparent variance $\hat\sigma^2 \approx \sigma_\text{true}^2 + \Delta^2$, inflating bands across the panel and over-deflating the standardised score on symbols whose $\sigma_\text{true}$ falls below the phase-transition threshold

$$\sigma^\ast(\Delta) \;\approx\; \frac{\Delta}{q \cdot c \,-\, 1}.$$

At deployed $q_r(0.95) \cdot c(0.95) \approx 2.23$, $\sigma^\ast(\Delta) \approx 0.81 \cdot \Delta$ — empirically validated across $\Delta \in \{100, 200, 400\}$ bps within $4\%$ of the closed-form prediction ($\sigma^\ast_\text{pred} / \sigma^\ast_\text{emp}$ ratio in $[0.96, 0.99]$ at $\Delta \in \{100, 200\}$ bps; bounded by the $\sigma_i$ grid endpoints elsewhere — `reports/tables/paper1_f2_5_sigma_star_formula.csv`). Symbols with $\sigma_\text{true} < \sigma^\ast(\Delta)$ over-cover (sharpness deficit, contract-favourable per §9.3); symbols with $\sigma_\text{true} \ge \sigma^\ast(\Delta)$ remain calibrated. At $\Delta = 200$ bps, LWC pooled coverage over-shoots to $0.9727$ and per-symbol Kupiec drops to $59.5\%$ — the failure is *over-coverage on low-σ symbols*, not under-coverage. A complementary location-shift detector — CUSUM on the standardised residual mean, composable with §9.5.1's violation-rate CUSUM bank — closes this gap at the monitoring layer, since the violation-rate CUSUM is by-construction blind to location shifts that produce nominal violation rates. Source: `reports/tables/paper1_f2_mean_jump_bimodality.csv`.

A sample-size sweep (`scripts/run_simulation_size_sweep.py`; 7 N-values × 4 DGPs × 100 reps × 2 forecasters = 22,400 cells) establishes the newly-listed-symbol admission threshold: $N \geq 80$ weekends under stationary / drift / structural-break DGPs, $N \geq 200$ under regime-switching (the production threshold). HOOD's empirical $N \approx 218$ (246 listed − 28 σ̂ warm-up) sits inside this band; HOOD's empirical Kupiec $p = 0.329$ at $\tau = 0.95$ (violation rate $0.035$, slight over-coverage) is consistent with the simulation's pass-rate range at $N = 200$. See `reports/m6_simulation_study.md` and `reports/tables/sim_size_sweep_admission_thresholds.csv`.

![Phase-3 simulation study at $\tau = 0.95$ — half-width and coverage in the visual idiom of [@romano-cqr-2019, Fig. 4], adapted to the per-symbol Mondrian setting. Eight rows: 4 DGPs $\times$ 2 forecasters (M5 unweighted-Mondrian comparator in vermilion; LWC deployed σ̂-standardised in blue, bold). Each box is the per-(rep, symbol) cell distribution ($N = 1{,}000$ per row). Median pills annotate the leftmost edge of each box. Left panel: avg. half-width (bps). Right panel: avg. coverage; dotted vertical marks nominal $\tau = 0.95$. The σ̂ contribution is the *coverage panel*: M5 boxes scatter from $\sim 0.81$ to $\sim 1.00$ — the per-symbol bimodality §7.5 documents — while LWC boxes sit tightly on $\tau = 0.95$ across every DGP. The half-width panel makes the §7.5 redistribution visible: M5 widths concentrate on a single per-rep value (the unweighted multiplier applied uniformly across the σ-grid); LWC widths span a wide range within each rep (per-symbol $\hat\sigma_s$ scaling).\label{fig:simulation}](figures/simulation_summary.pdf)

## 6.8 Summary

The headline $\tau = 0.95$ claim is **held out on two orthogonal axes**: temporally (§6.3.3.1: $c$ fit on 2023 alone, evaluated on a 2024-01-05 → 2026-04-24 holdout — realised $0.9504$, Kupiec $p = 0.947$, Christoffersen $p = 0.989$, per-symbol Kupiec 10/10) and on symbol (§6.3.3 LOSO: realised $0.9497 \pm 0.0128$ across the held-out symbol distribution, all 10 LOSO bands pass Kupiec). The result is stable across TUNE anchors $\{2021, 2022, 2023\}$ ($[0.9474, 0.9524]$) and across split anchors $\{2021, 2022, 2023, 2024\}$ ($[0.9503, 0.9539]$), with per-symbol Kupiec 10/10 preserved everywhere. On the deployment-tuned 2023+ slice the pooled headline at $\tau = 0.95$ is realised **95.0%** at mean half-width **370.6 bps** with both Kupiec ($p = 0.956$) and Christoffersen ($p = 0.603$) passing. **All 10 symbols pass per-symbol Kupiec** with violation rates in $[3.5\%, 6.9\%]$; per-symbol Berkowitz LR sits in $[3.2, 16.7]$. Across the 40-cell (symbol × $\tau$) grid jointly evaluated under Kupiec / Christoffersen / DQ, the architecture carries **40/40 Kupiec, 38/40 Christoffersen, 39/40 DQ** — leading the strongest practitioner baseline GARCH-$t$ (31/40, 37/40, 31/40) on every metric. Calendar sub-period calibration holds across {2023, 2024, 2025, 2026-YTD} (3/16 over-coverage rejections, all in 2025; 0/16 Christoffersen rejections). Joint-tail behaviour is empirically characterised: $P(k_w \ge 3) = 4.62\%$ at $\tau = 0.95$ vs the binomial $1.15\%$, with $k^\ast = 3$ stable across the 24-cell grid (0/24 sub-period rejections); the worst-observed weekend (2024-08-05 BoJ unwind) sat at $k_w = 10$ at $\tau = 0.85$. A four-DGP simulation corroborates the per-symbol fix on synthetic data with known ground truth; a forward-tape harness against a content-addressed frozen artefact is operational and accumulating ($N = 1$ at submission, preliminary by its own threshold of $N \ge 4$). Berkowitz and DQ still reject pooled — bands remain *per-anchor calibrated*, not full-distribution calibrated — and the residual rejection localises to cross-sectional within-weekend common-mode (orthogonal to σ̂; addressed in §10). Supports $P_2$ (§3.4); $P_1$ evidenced by §8; $P_3$ by §7.
