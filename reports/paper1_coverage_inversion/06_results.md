# §6 — Results

This section reports the primary calibration evidence for **M6** (the deployed locally-weighted Mondrian split-conformal architecture under EWMA HL=8 σ̂; §4) on real and synthetic data, plus the forward-tape harness operational against a content-addressed frozen artefact. Sharpness, per-component effects, and the σ̂ selection procedure are deferred to §7; system-level implementation and audit reproducibility are in §8. The headline is per-anchor calibration with all 10 symbols passing per-symbol Kupiec at $\tau = 0.95$, calendar sub-period stability across four years, and a measurable joint-tail empirical distribution that turns the residual *per-anchor calibrated, not full-distribution calibrated* disclosure into operational reserve guidance.

## 6.1 Evaluation protocol

The backtest panel comprises $N = 5{,}996$ weekend prediction windows: ten symbols × $639$ weekends, 2014-01-17 through 2026-04-24. Monday open is the target; Friday close and contemporaneous factor / vol-index readings compose $\mathcal{F}_t(s)$. The σ̂ warm-up rule (≥8 past observations per symbol) drops 80 weekends at panel start to leave $5{,}916$ evaluable rows. We report (i) an *in-sample machinery check* (quantile fit and served on the full evaluable panel; realised coverage matches $\tau$ by construction), (ii) the *out-of-sample validation* (quantile fit on $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ — 4,186 rows; M6 served on the 1,730-row $\mathcal{T}_\text{test}$ slice), (iii) the held-out *forward-tape* evaluation against a content-addressed frozen artefact (§6.7), and (iv) a *simulation study* on synthetic panels with known ground truth (§6.8). All $p$-values are two-sided Kupiec POF and Christoffersen independence tests. The base point estimator is unbiased (median residual $-0.5$ bps; MAE $90.0$; RMSE $163.3$); the product is the per-symbol-σ̂-rescaled per-regime conformal quantile with the OOS-fit $c(\tau)$ bump.

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

Quantile fit on pre-2023 weekends ($n = 4{,}186$); M6 served on the 2023+ slice (1,730 rows × 173 weekends). The 12 trained per-regime quantiles $q_r(\tau)$ are held-out; the 4-scalar $c(\tau)$ schedule is OOS-fit on this same slice. The walk-forward $\delta(\tau)$ schedule is identically zero — per-symbol scale standardisation tightens cross-split realised-coverage variance enough that no structural-conservatism shift is required (§4.5). **The strongest defensible characterisation is *deployment-calibrated and walk-forward-stable*; the 4-scalar OOS-fit $c(\tau) = \{1.000,\,1.000,\,1.079,\,1.003\}$ is near-identity at three of four anchors and only widens by 7.9% at $\tau = 0.95$.** §9.3 carries the full provenance disclosure.

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

**The $\tau = 0.95$ row is the primary oracle-validation operating result.** Realised coverage is exactly $0.9503$ (Kupiec $p_{uc} = 0.956$); Christoffersen $p_{ind} = 0.603$ passes. **Kupiec and Christoffersen pass at every served anchor.** Mean half-width at $\tau = 0.95$ is **370.6 bps** — narrower than the K=26 σ̂ comparator (385.3 bps; bootstrap 95% CI on $\Delta$hw% upper bound is $-1.88\%$, see §7.3). The §6.3.5 residual Berkowitz / DQ rejection localises to per-symbol Berkowitz on TLT and TSLA (§6.4.1) and to cross-sectional within-weekend common-mode (§6.3.4) — neither curable with a different σ̂ rule.

### 6.3.2 Realised-move tertile decomposition at $\tau = 0.95$

Stratifying the OOS slice by post-hoc realised-move $|z|$-score tertile (`reports/tables/m6_realised_move_tertile.csv`) closes the loop between the §6.3 pooled headline and the §9.1 shock-tertile ceiling:

| tertile ($n$)     | realised | half-width (bps) | Kupiec $p$ |
|---|---:|---:|---:|
| calm   (497)      | 1.0000   | 379.7 | $0$ (over-covers) |
| normal (601)      | 0.9933   | 371.6 | $0$ (over-covers) |
| **shock** (632)   | **0.8782** | 364.6 | $0$ (under-covers) |
| **pooled** (1{,}730) | **0.9503** | **370.6** | **0.956** |

Half-width is approximately flat across tertiles (365–380 bps), so the band does not widen in shock periods — it just misses more often. The shock-tertile residual is cross-sectional common-mode within a weekend (§9.1), not per-symbol scale.

![Calibration curves on the 1{,}730-row 2023+ OOS slice. M6 (this paper, blue) tracks the $45^\circ$ diagonal across the served range $\tau \in [0.68, 0.99]$; the constant-buffer baseline (F0\_stale, vermilion) over-covers throughout (over-conservative Gaussian wrap on $\sigma_{20d}$); the legacy Soothsayer-v0 forecaster ladder (orange) tracks until $\tau \approx 0.97$ where it caps at $0.972$ — Soothsayer-v0's finite-sample tail ceiling that M6 closes. Star marks the headline $\tau = 0.95$ result.\label{fig:calibration}](figures/fig2_calibration.pdf)

### 6.3.3 Stability — walk-forward, split-date, LOSO, calendar sub-period

**Walk-forward stability.** Re-running the M6 schedule selection on the four powered expanding-window splits (fractions $f \in \{0.40, 0.50, 0.60, 0.70\}$ — see §4.5 for why the 0.20 and 0.30 splits are excluded as under-powered for the 4-scalar $c(\tau)$ fit) with $\delta = 0$: walk-forward realised $\tau = 0.95$ coverage is $\geq 0.95$ on every powered split (range 0.954–0.975) — the criterion that selected $\delta = 0$ in §4.5. Per-split mean half-width at $\tau = 0.95$ tracks the full-OOS-fit value within $\pm 8\%$.

**Split-date sensitivity.** Repeating the M6 fit (quantile table re-trained, $c(\tau)$ re-fit per split, $\delta \equiv 0$ held) at four OOS-split anchors {2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01} delivers realised $\tau = 0.95$ coverage of $\{0.9539,\ 0.9520,\ 0.9503,\ 0.9504\}$ — Kupiec $p \in \{0.348,\ 0.661,\ 0.956,\ 0.947\}$ and **Christoffersen $p \in \{0.115,\ 0.186,\ 0.603,\ 0.671\}$ — every (split × $\tau$) cell passes at $\alpha = 0.05$.** Mean half-width $\{357.2,\ 363.5,\ 370.6,\ 416.8\}$ bps varies $\pm 8\%$ around the deployed value.

**Leave-one-symbol-out CV.** Holding out each of the ten symbols' rows from train + OOS fits and evaluating $\tau = 0.95$ on the held-out symbol's post-2023 slice: **all 10 LOSO bands pass Kupiec when held out**; mean realised $0.9497$, std $0.0134$ across the held-out symbol distribution (`reports/tables/m6_lwc_robustness_loso.csv`). Heavy-tail tickers (MSTR, HOOD, TSLA) and low-vol tickers (SPY, GLD) all sit in a uniform 0.93–0.97 band when held out — the per-symbol $\hat\sigma_s(t)$ on the held-out symbol carries its own scale, so cross-symbol calibration is not load-bearing on heavy-tail inclusion.

**Calendar sub-period stability.** Bucketing the OOS slice into four calendar sub-periods {2023, 2024, 2025, 2026-YTD} (`reports/tables/m6_subperiod_robustness.csv`):

| Sub-period ($n$ weekends) | Realised at $\tau = 0.95$ | Half-width (bps) | Kupiec $p$ | Christoffersen $p$ |
|---|---:|---:|---:|---:|
| 2023 (52)          | 0.942 | 249.7 | 0.432 | 0.105 |
| 2024 (52)          | 0.939 | 444.5 | 0.243 | 0.878 |
| 2025 (52)          | 0.967 | 471.2 | 0.054 | 0.969 |
| 2026-YTD (17)      | 0.959 | 356.2 | 0.587 | 0.908 |
| **Pooled OOS (173)** | **0.950** | **370.6** | **0.956** | **0.603** |

Pooled OOS calibration at $\tau = 0.95$ holds across each of the four years that span SVB / banking-stress 2023, the 2024 rate-cut transition, the 2025 tokenisation-launch year, and 2026-YTD (Kupiec $p \ge 0.054$ in every cell; realised range $0.942$–$0.967$). Across the full 16-cell (sub-period × $\tau$) grid M6 has 2 Kupiec rejections (2025 at $\tau = 0.85$ and $\tau = 0.99$, both *over-coverage*). Christoffersen lag-1 independence is not rejected in any of the 16 cells. The sub-period evidence converts the §9.2 stationarity disclosure into a positive temporal-stability claim.

![Walk-forward and split-date stability of the deployed M6 schedule. **(a)** Six-split expanding-window walk-forward at four $\tau$ anchors: realised coverage on each test fold (markers) tracks nominal (dotted lines) at every anchor; bars are 95% binomial CIs. **(b)** Split-date sensitivity at four OOS-anchors {2021, 2022, 2023, 2024}: realised $\tau = 0.95$ coverage holds at $\{0.954, 0.952, 0.950, 0.950\}$ across anchors; Christoffersen passes every cell at $\alpha = 0.05$.\label{fig:stability}](figures/fig3_stability.pdf)

This validates the oracle's coverage contract at $\tau = 0.95$. It does *not* prove $\tau = 0.95$ is the welfare-optimal operating point; that is Paper 3.

### 6.3.4 Joint-tail empirical distribution and reserve-guidance threshold

A consumer holding a portfolio of correlated RWAs needs to know not only the per-symbol calibration but the *joint* distribution of simultaneous breaches. We compute, for each OOS weekend $w$ with full 10-symbol coverage, the count $k_w = |\{s : s \text{ breaches its } \tau\text{-band on } w\}|$, and compare its empirical distribution to the binomial-independence reference $\mathrm{Binom}(10, 1-\tau)$ (`reports/tables/m6_portfolio_clustering.csv`; CIs are 1000-rep weekend-block bootstrap, seed = 0):

| Statistic at $\tau = 0.95$ ($n_\text{weekends} = 173$) | M6 | $\mathrm{Binom}(10, 0.05)$ |
|---|---:|---:|
| Mean $k_w$ / weekend | 0.497 | 0.500 |
| $\mathrm{Var}(k_w)$ | 1.135 | 0.475 |
| Variance ratio (overdispersion) | **2.39** | 1.00 |
| $P(k_w \ge 3)$ | **5.20% [2.31, 8.67]** | 1.15% |
| $P(k_w \ge 5)$ | **1.16% [0.00, 2.89]** | 0.01% |
| $P(k_w \ge 7)$ | **0.58% [0.00, 1.73]** | $< 0.001\%$ |
| max $k_w$ (worst weekend) | 8 | — |
| $\chi^2$ goodness-of-fit $p$ | $< 0.0001$ | (null) |

Marginal calibration is preserved (mean $k_w$ matches the binomial reference to $0.003$); the clustering shows up only in the *variance* and the *upper tail*. The bootstrap CI on $P(k_w \ge 3)$ ($[2.31\%,\,8.67\%]$) strictly excludes the binomial reference ($1.15\%$) — joint upper-tail mass is materially heavier than independence and the result is robust to weekend-resampling. The same overdispersion is more visible at $\tau = 0.85$ where absolute counts are larger: M6 overdispersion is $2.22$, $P(k_w \ge 5) = 5.78\%$ vs binomial $0.99\%$, and the worst-observed weekend has all 10 symbols breaching simultaneously.

**Reserve-guidance threshold.** The deployment-recommended threshold $k^\ast$ at each $\tau$ — the smallest $k$ whose empirical hit-rate on the full OOS slice is closest to $5\%$ — is $k^\ast = 5$ at $\tau = 0.85$ (full-OOS rate $5.78\%$), $k^\ast = 3$ at $\tau = 0.95$ (full-OOS rate $5.20\%$), and $k^\ast = 1$ at $\tau = 0.99$ (full-OOS rate $5.78\%$). **Stability across calendar sub-periods** (`reports/tables/m6_kw_threshold_stability.csv`): at $k^\ast = 3$ for $\tau = 0.95$, the per-sub-period hit-rate is $\{7.69\%, 5.77\%, 3.85\%, 0.00\%\}$ across {2023, 2024, 2025, 2026-YTD} with Kupiec $p \in \{0.449, 0.856, 0.645, 0.178\}$ — every cell is statistically consistent with the full-OOS rate. Across the full 24-cell grid (3 $\tau$ × 2 threshold conventions × 4 sub-periods), M6 carries **0/24 Kupiec stability rejections** on the per-sub-period $k_w \ge k^\ast$ hit-rate at $\alpha = 0.05$. The per-sub-period empirical 95th percentile of $k_w$ at $\tau = 0.95$ stays in $[1.4, 3.0]$ across the four years (range 1.6 integer-symbols), so the deployment threshold is conservative against year-on-year drift.

**Power caveat.** With sub-period $n \approx 52$ and target rates $\sim 5\%$, the binomial-stability test has limited power to detect drift smaller than the year-on-year p95 spread (≤ 1.6 integer-symbols). The result is "no detectable instability with the available power" rather than "proven stationary"; the orthogonal quantile-read (year-on-year p95 spread) is what compensates.

**Operational consumer guidance** (the contribution this measurement enables). A 10-symbol xStock-style portfolio at $\tau = 0.95$ should reserve against an empirical 99th-percentile of $\approx 5$ simultaneous breaches, not the binomial $\approx 2$; at $\tau = 0.85$ the empirical 99th percentile is $\approx 7$ vs binomial $\approx 4$. **No incumbent oracle (Pyth, Chainlink Data Streams, RedStone, Kamino Scope) publishes this distribution**; this is the joint-tail measurement layer that calibration-transparency makes possible.

### 6.3.5 Worst-observed weekend — 2024-08-05 BoJ yen-carry-unwind

The single OOS weekend with all 10 symbols breaching the $\tau = 0.85$ band simultaneously is **Friday 2024-08-02 → Monday 2024-08-05** — the Bank of Japan rate-hike yen-carry-trade unwind, one of the largest single-weekend global risk-off events of the post-2020 period. The same weekend has $k_w = 8$ at $\tau = 0.95$ (only TSLA and TLT inside that band) and $k_w = 5$ at $\tau = 0.99$. M6 served band re-evaluated on the 2024-08-02 row at the deployed $\text{split} = \text{2023-01-01}$:

| Symbol | Weekend return | M6 HW @ $\tau=0.85$ | Breach @ $\tau=0.85$ | @ $\tau=0.95$ |
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

### 6.3.6 Extended diagnostics — Berkowitz and DQ

**Berkowitz (2001) joint LR on continuous PITs.** PITs reconstructed by inverting each served band against the realised Monday open through the per-regime conformal CDF. The pooled Berkowitz LR on M6's PITs is non-zero (the residual is the cross-sectional within-weekend common-mode of §6.3.4). **Engle-Manganelli (2004) DQ at $\tau = 0.95$** also rejects on the pooled fit — the same temporal-clustering signal, again because the cross-sectional within-weekend common-mode (which is what DQ is sensitive to here) is orthogonal to the σ̂ standardisation. **Bands are *per-anchor calibrated*, not full-distribution calibrated** — the §6.3.4 joint-tail empirical distribution turns this disclosure into a measurable, reportable shape.

**Localising the residual.** Decomposing the lag-1 alternative under panel-row order: the AR(1) signal lives in the *cross-sectional within-weekend* ordering ($\hat\rho_{\text{cross}} = 0.354$, $p < 10^{-100}$, $n = 1{,}557$) — not the temporal-within-symbol ordering ($\hat\rho_{\text{time}} = -0.032$, $p = 0.18$, $n = 1{,}720$). σ̂ standardisation operates *within* a symbol's history, not *across* symbols within a weekend, so it cannot reach this residual. A vol-tertile sub-split of `normal` regime (5 cells) leaves Berkowitz LR essentially unchanged ($170 \to 172$) while widening $\tau = 0.95$ band by $9\%$ — finer regime granularity is not the lever (`reports/tables/m6_lwc_robustness_vol_tertile.csv`). The §10 candidate architectures that target cross-sectional common-mode (the cross-sectional partial-out track in `reports/active/m6_refactor.md`, gated on a Friday-observable $\bar r_w$ predictor) are deferred-with-gates.

## 6.4 Per-symbol generalisation

The §6.3 OOS pooled coverage at $\tau = 0.95$ matches nominal; the per-symbol question is whether each ticker's individual cell is also calibrated. Under M6, **all 10 symbols pass Kupiec at $\tau = 0.95$** with violation rates in $[2.9\%,\,6.9\%]$ and per-symbol PIT variance $\hat\sigma^2_z \in [0.62,\,0.83]$ — all close to the calibrated $1.0$ from below. Figure \ref{fig:per-symbol} visualises the per-symbol calibration distribution.

![Per-symbol calibration at $\tau = 0.95$ on the 2023+ OOS slice. Each symbol's violation rate (markers) sits within the binomial 95% confidence band around the nominal $0.05$ rate (shaded). Symbols are ordered by their realised PIT variance $\hat\sigma^2_z$. The distribution is unimodal and centred near nominal — heavy-tail tickers (TSLA, HOOD, MSTR), low-vol tickers (SPY, QQQ, GLD, TLT), and the equity middle (AAPL, GOOGL, NVDA) all sit in the same cluster. The single outlier in the broader (symbol × $\tau$) grid is TSLA at $\tau = 0.85$ (Kupiec $p = 0.044$, over-coverage), discussed in §6.4.2.\label{fig:per-symbol}](figures/fig4_per_symbol.pdf)

### 6.4.1 Per-symbol Kupiec at $\tau = 0.95$ and Berkowitz LR

Per-symbol Kupiec on the 2023+ OOS slice (`reports/tables/m6_per_symbol_kupiec_4methods.csv`, regenerated 2026-05-05):

| Symbol | Violation rate | Kupiec $p$ | Berkowitz LR |
|---|---:|---:|---:|
| AAPL  | 0.069 | 0.268 |  6.7 |
| GLD   | 0.058 | 0.645 |  3.2 |
| GOOGL | 0.046 | 0.818 | 10.2 |
| HOOD  | 0.040 | 0.552 |  6.4 |
| MSTR  | 0.052 | 0.903 |  7.1 |
| NVDA  | 0.058 | 0.645 | 10.0 |
| QQQ   | 0.029 | 0.168 |  5.1 |
| SPY   | 0.046 | 0.818 |  9.6 |
| TLT   | 0.046 | 0.818 | 16.7 |
| TSLA  | 0.052 | 0.903 | 13.5 |
| **pass-rate at $\alpha = 0.05$** | | **10 / 10** | |
| **Berkowitz LR range** | | | **3.2 – 16.7** (5.3$\times$) |

**All 10 symbols pass Kupiec at $\tau = 0.95$** with violation rates inside $[2.9\%, 6.9\%]$. The per-symbol Berkowitz LR range $[3.2, 16.7]$ (a 5.3$\times$ spread) is one of the strongest per-symbol calibration claims a Mondrian-conformal architecture can make on this panel — only TLT (LR 16.7) and TSLA (LR 13.5) reject Berkowitz at $\alpha = 0.01$, and those rejections trace to cross-sectional common-mode rather than per-symbol scale (§6.3.6).

### 6.4.2 Per-symbol Kupiec across parametric baselines

The per-symbol claim extends to a 40-cell (symbol × $\tau$) grid against three parametric / non-parametric baselines: GARCH(1,1)-Gaussian, GARCH(1,1)-$t$ (Student-$t$ innovations, the practitioner default for fat-tailed returns), and the M5 unweighted Mondrian comparator (`reports/tables/m6_per_symbol_kupiec_4methods.csv`, 160 rows).

Pass-counts at each $\tau$ (per-symbol Kupiec $p \ge 0.05$; out of 10 symbols at each anchor; out of 40 across the grid):

| $\tau$ | GARCH-N | GARCH-$t$ | M5 (unweighted Mondrian) | **M6** |
|---:|---:|---:|---:|---:|
| 0.68 | 5/10 | 6/10 | 1/10 | **10/10** |
| 0.85 | 8/10 | 7/10 | 1/10 | 9/10 |
| 0.95 | 6/10 | 8/10 | 2/10 | **10/10** |
| 0.99 | 4/10 | 10/10 | 8/10 | **10/10** |
| **Total (40 cells)** | **23/40** | **31/40** | **12/40** | **39/40** |

**M6's lone failure across the 40-cell grid is TSLA at $\tau = 0.85$** (Kupiec $p = 0.044$, violation rate $0.098$ vs target $0.150$ — *over-coverage*), the same TSLA cell that anchors §6.4.1's per-symbol Berkowitz disclosure. Versus the strongest practitioner baseline GARCH-$t$ (which carries 31/40 passes), M6 leads by 8 cells, dominates at $\tau = 0.95$ (10/10 vs 8/10), and ties at $\tau = 0.99$ (10/10 each — the only methods to clear that anchor on every symbol; GARCH-Gaussian's Gaussian-tail mis-specification is visible on the $\tau = 0.99$ row, 4/10).

### 6.4.3 GARCH-$t$ pooled baseline (and GARCH-Gaussian)

The textbook econometric default for a time-varying interval at $\tau$ is per-symbol GARCH(1,1) on log Friday-to-Monday returns. The practitioner choice of innovation distribution is Student-$t$ — Gaussian innovations are a known straw-man on equity weekend returns where fitted $\hat\nu \approx 3$ across the panel (`reports/tables/m6_lwc_robustness_garch_t_baseline.csv`):

| $\tau$ | Method | Realised | HW (bps) | Kupiec $p$ | Christoffersen $p$ |
|---:|---|---:|---:|---:|---:|
| 0.95 | GARCH-Gaussian | 0.9254 | 322.2 | $0.000$ | 0.016 |
| 0.95 | GARCH-$t$       | 0.9277 | 331.6 | $0.000$ | **0.209** |
| 0.95 | **M6**          | $\mathbf{0.9503}$ | $\mathbf{370.6}$ | $\mathbf{0.956}$ | **0.603** |
| 0.99 | GARCH-Gaussian | 0.9630 | 423.7 | $0.000$ | 0.866 |
| 0.99 | GARCH-$t$       | 0.9850 | 569.3 | 0.050  | $1.000$ |
| 0.99 | **M6**          | $\mathbf{0.9902}$ | $\mathbf{635.0}$ | $\mathbf{0.942}$ | $1.000$ |

GARCH-$t$ closes two failures GARCH-Gaussian leaves on the table: the $\tau = 0.99$ tail capture (realised improves from $0.963$ to $0.985$; Kupiec $p$ moves from $< 0.001$ to a borderline $0.050$) and the Christoffersen rejection at $\tau = 0.95$ ($p$ moves from $0.016$ to $0.209$). What it does *not* fix is the **Kupiec under-coverage at every $\tau < 0.99$** — the standardised-$t$ 95th percentile at $\nu \approx 3$ is $\sim 1.83$ vs Gaussian $1.96$, so the bands tighten precisely where Gaussian was already under-covering. T-innovations fix the wrong end of the distribution.

**At matched 95% realised coverage**, widening GARCH-$t$ to its claimed $\tau = 0.95$ requires roughly $+14\%$ on width, giving a matched-coverage HW $\approx 378$ bps — statistically tied with M6's $370.6$ bps. At $\tau = 0.99$ M6 dominates GARCH-$t$ on coverage and width-at-matched-coverage simultaneously. The conformal LWC route fixes both Kupiec and Christoffersen because it is calibrated to the data, not to a fitted parametric distribution; one further parametric-tail risk M6 avoids is the NVDA fallback observable here, where the t-MLE pushes $\hat\nu$ to the variance-undefined boundary at $2.50$ and the runner falls back to Gaussian. GARCH-Gaussian is retained in the table for completeness and is not the practitioner standard.

### 6.4.4 Per-asset-class deviation

Pooled OOS coverage stratified by asset class (`reports/tables/m6_lwc_robustness_per_class.csv`). Equities (8 syms, 1,384 obs): realised $0.9466$ at $\tau = 0.95$ with hw $436$ bps; GLD + TLT (2 syms, 346 obs): realised $0.954$ with hw $184$ bps. The per-symbol $\hat\sigma_s$ multiplier delivers heavy-tail equities wider bands matched to their relative-residual scale and the defensive class (GLD, TLT) narrower bands matched to theirs; M6 Kupiec passes every class at every $\tau$. The width allocation across asset classes is the operational manifestation of $P_3$ (per-regime serving efficiency): width is concentrated where calibration demands it.

## 6.5 Comparison to incumbent oracle surfaces

We measure what consumers receive from deployed alternatives across three reconstructions: a regular-Pyth Hermes-derived band (265 obs, 2024+), a Chainlink Data Streams v10/v11 reconstruction (87 obs, frozen 2026-02-06 → 2026-04-17), and a forward-cursor RedStone Live tape ($n = 12$, 2026-04-26+); Pyth Pro / Blue Ocean is excluded on access and window grounds. Caveats: sample CIs are wide; composition is skewed toward large-cap normal-regime weekends (compare to M6's 300.1 bps normal-regime half-width); wrap multipliers are *consumer-supplied* — none of the three incumbents publishes a calibration claim a consumer can read directly.

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

The naive textbook 95% wrap returns 10.2% — under-calibrated by ≈10× as a consumer-supplied band. The smallest $k$ delivering ≥ 95% is $k \approx 50$ (279.5 bps); on the Pyth-available subsample (composed predominantly of large-cap equities) M6's regime-matched normal half-width at $\tau = 0.95$ is 300.1 bps — width-comparable at matched coverage. The Soothsayer differentiator on this panel is the calibration receipt and its cross-symbol generalisation, not the bandwidth on a SPY-heavy subsample.

![Coverage versus mean half-width across methods at the four served $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ (vertical dotted lines). M6 (blue stars) at full panel ($n = 1{,}730$); Soothsayer-v0 legacy ladder (orange circles) for context; GARCH-$t$ (vermilion squares) is the practitioner econometric baseline; Pyth $\pm k \!\cdot\! \mathrm{conf}$ (green diamonds, $n = 265$) is the consumer-supplied wrap that achieves the claimed coverage at the smallest $k$ on the available subset; Chainlink Streams (purple, $n = 87$) is the manual mid $\pm k\%$ wrap on the marker-aware-decoded sample. M6 sits on the calibration-vs-sharpness Pareto frontier at every served $\tau$; GARCH-$t$ undercovers Kupiec at $\tau \in \{0.68, 0.85, 0.95\}$ despite slightly tighter bands; Pyth and Chainlink subsets cover comparable widths but on small, heterogeneous samples (§6.5 caveats).\label{fig:pareto}](figures/fig5_pareto.pdf)

**Chainlink Data Streams v10 / v11.** v10 (Tokenized Asset, `0x000a`) carries no `bid`/`ask`/confidence on the wire — band-less by construction [chainlink-v10]. v11 (RWA Advanced, `0x000b`) adds `bid`, `ask`, `mid`. Marker-aware classifier on a 26-report weekend scan:

| Symbol (n) | Pattern | Wire `bid` | Wire `ask` | Implied spread |
|---|---|---:|---:|---:|
| SPYx (6) | PURE_PLACEHOLDER | 21.01 | 715.01 | ~18,858 bps |
| QQQx (6) | BID_SYNTHETIC | 656.01 | — | 117–329 bps |
| TSLAx (7) | BID_SYNTHETIC | 372.01 | — | 117–329 bps |
| NVDAx (1) | REAL | 208.07 | 208.14 | ~3.4 bps |

The v11 weekend `bid` carries a synthetic `.01` suffix at 100% incidence on three of four mapped xStocks — a generated bookend, not a venue quote. To get a usable band a v11 consumer must replace wire `bid`/`ask` with a manual `mid ± k%` wrap; an earlier 87-obs panel found $k \approx 3.2\%$ delivers ≥ 95% — ~10% wider than M6's regime-matched normal half-width. Neither v10 nor v11 publishes a coverage band a consumer can read directly.

## 6.6 Path coverage — endpoint vs intra-weekend

The §6.3 result is *endpoint coverage*: realised Monday open lies inside the served band. A DeFi consumer holding an xStock as collateral is exposed at every block over the weekend; a Saturday liquidation when the on-chain xStock briefly trades outside the band is a real loss event even if Monday open returns inside. We measure path coverage on $[\text{Fri 16:00 ET},\, \text{Mon 09:30 ET}]$ against 24/7 stock-perp 1m bars from `cex_stock_perp/ohlcv` (Kraken Futures `PF_<sym>XUSD`, xStock-backed). Sample: 19 weekends × 9 symbols (TLT excluded — no perp listing), $n = 118$ (symbol, weekend) pairs per anchor, 2025-12-19 → 2026-04-24 (`reports/tables/path_coverage_perp.csv`):

| $\tau$ | $n$ | Endpoint coverage | Path coverage | Gap (pp) |
|---:|---:|---:|---:|---:|
| 0.68 | 118 | 0.644 | 0.348 | $+29.7$ |
| 0.85 | 118 | 0.864 | 0.568 | $+29.7$ |
| **0.95** | **118** | $\mathbf{0.949}$ | $\mathbf{0.788}$ | $+\mathbf{16.1}$ |
| 0.99 | 118 | 0.992 | 0.915 | $+7.6$  |

**M6 calibrates the perp-listed sample to nominal endpoint coverage** (0.949 at $\tau = 0.95$ vs nominal $0.95$) on a sample whose composition is predominantly large-cap equities (SPY/QQQ/AAPL/GOOGL/NVDA/MSTR/TSLA/HOOD plus GLD; TLT excluded — no perp listing). The path-coverage gap is $+16.1$ pp at $\tau = 0.95$: an honestly-calibrated endpoint band exhibits a structural shortfall on a sample whose intra-weekend variance is larger than its endpoint variance. Sample is small (binomial CI on the $\tau = 0.95$ pooled gap is $\pm 6$ pp); the test is directional. After three confound checks documented in `reports/v1b_path_coverage_robustness.md` — perp-spot basis normalisation closes the gap to $11.0$ pp, a volume-floor filter at $\geq 1$ contract closes it to $9.5$ pp ($n=63$), and a 15-minute rolling-median sustained-crossing definition leaves it at $14.4$ pp — the residual genuine-shortfall band is $\sim 9$–$15$ pp at $\tau = 0.95$, with most of the magnitude attributable to sustained drift rather than transient thin-liquidity prints. The gap collapses meaningfully only at $\tau = 0.99$ ($+7.6$ pp); continued capture is tracked under scryer item 51 and §10.1 (the path-fitted conformity score).

![Path coverage gap on the 24/7 stock-perp reference. M6 endpoint coverage (blue) tracks nominal across $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ on the perp-listed subset; M6 path coverage (vermilion) — the fraction of weekends where the perp 1m bar high/low stay inside the served band over the full $[\text{Fri 16:00, Mon 09:30}]$ window — runs $29.7$/$29.7$/$16.1$/$7.6$ pp behind. The gap collapses meaningfully only at $\tau = 0.99$. Sample is small ($n = 118$ symbol-weekends across 19 calendar weekends, 2025-12 to 2026-04); the read is directional and §10.1 (the path-fitted conformity score) is the methodology fix.\label{fig:path-coverage}](figures/fig6_path_coverage.pdf)

The endpoint contract stands. A consumer requiring path coverage at level $\tau$ should step up one anchor (empirically closes the gap on this slice at $\tau = 0.99$), absorb the residual through downstream policy (Paper 3), or — for continuous-consumption products that cannot use the step-up lever (band-aware AMMs the canonical case) — adopt the path-fitted conformity-score variant on the next-generation roadmap.

## 6.7 Forward-tape held-out validation

The 4-scalar OOS-fit $c(\tau)$ schedule is fit on the 2023+ slice; the resulting deployment artefact carries a residual contamination disclosure (§9.3). The forward-tape harness closes that loop on truly held-out data: a content-addressed frozen artefact (`data/processed/lwc_artefact_v1_frozen_20260504.json`, SHA-256 `7b86d17a7691…`, freeze date 2026-05-04) is evaluated weekly against forward weekends as they accumulate. The frozen artefact's σ̂ schedule, $q_r$ table, and $c(\tau)$ are read-only; only the per-symbol $\hat\sigma_s(t)$ updates as new past-Fridays arrive.

The harness fires Tuesday mornings via launchd (`launchd/com.adamnoonan.soothsayer.forward-tape.plist`); each run executes a 26h-SLA pre-check on the upstream scryer feeds, runs `scripts/collect_forward_tape.py`, and writes `reports/m6_forward_tape_{N}weekends.md` with a "preliminary" banner when $N < 4$. The harness is silent about deployment; an out-of-band freeze re-roll is required to advance the artefact (`scripts/freeze_lwc_artefact.py`).

**Status at submission:** $N = $ [N TBD as forward weekends accumulate; first non-stub report ETA 2026-05-12; the §6.7 numbers are the load-bearing post-freeze evidence and **must be regenerated immediately before submission**]. Latest report: `reports/m6_forward_tape_{N}weekends.md`. With $N \geq 4$ the preliminary banner clears; with $N \geq 6$ the per-symbol Kupiec read becomes informative; with $N \geq 13$ the cumulative pooled Christoffersen on forward data has moderate power.

The forward-tape evidence is the cleanest possible held-out coverage statement on the deployed artefact. The harness's σ̂ variant comparison sibling (`scripts/run_forward_tape_variant_comparison.py`, output `reports/m6_forward_tape_{N}weekends_variants.md`) carries an alternative-σ̂ check on the same forward slice — never used to re-select, only to flag if a different σ̂ rule looks dramatically cleaner on the held-out data (§7.3).

## 6.8 Simulation study — predicted-and-validated per-symbol fix

The §6.4 per-symbol calibration result raises a methodological question: is the per-symbol bimodality that an unweighted Mondrian comparator exhibits a property of the deployed comparator on this real-data panel, or a structural property of the architecture? We answer the second question with a four-DGP simulation study under known ground truth. **Across stationary, regime-switching, drift, and structural-break specifications, the unweighted-Mondrian comparator's per-symbol Kupiec pass-rate at $\tau = 0.95$ is 29–31% while M6's is 97.6–99.6% — the bimodality is structural, predicted by the architecture, and reproducible in synthetic data.**

Source: `scripts/run_simulation_study.py` (~30 s end-to-end). Each DGP uses 10 synthetic symbols × 600 weekend returns, $\sigma_i \in \mathrm{linspace}(0.005, 0.030, 10)$ — spanning the empirical real-panel range. Train/OOS split at $t = 400$. Returns drawn from Student-$t$ df=4 rescaled to $\mathrm{std}(r) = \sigma_i$ (or $\sigma_i \cdot m_t$ under DGP B/C/D's vol modifications). 100 Monte Carlo replications per DGP, seed $= 0$.

| DGP | Unweighted-Mondrian pass-rate at $\tau = 0.95$ | M6 pass-rate | Mechanism |
|---|---:|---:|---|
| A — homoskedastic baseline | $0.311$ | $\mathbf{0.994}$ | Per-symbol scale heterogeneity is the entire failure mode |
| B — regime-switching vol multiplier | $0.310$ | $\mathbf{0.976}$ | M6 σ̂ tracks regime transitions with a half-life lag |
| C — non-stationary scale (drift) | $0.309$ | $\mathbf{0.996}$ | M6's adaptive σ̂ is built for this DGP |
| D — exchangeability stress (variance ×3 at $t = 400$) | $0.292$ | $\mathbf{0.994}$ | σ̂ recovers in $\leq 26$ weekends; warm-up under-coverage diluted |

Both methods pool to mean realised $\approx 0.95$ across all four DGPs (within $0.005$ of nominal). The split is on the *per-symbol* failure rate. The unweighted comparator passes $\sim 30\%$ of (symbol, replicate) cells — the bimodal failure mode reproduces under controlled conditions exactly as the architecture predicts (a single $(r, \tau)$-keyed multiplier mis-calibrates symbols whose residual scale deviates from the regime average in opposing directions). M6 passes $97.6$–$99.6\%$ of cells, with the only material gap from DGP A appearing under DGP B's regime-switching (σ̂'s ~13-weekend tracking lag at regime flips). DGP D was the surprise — the prediction was that an exchangeability break would degrade both methods; the result is that M6's adaptive σ̂ recovers in under 26 weekends and the under-covered warm-up is diluted by the well-calibrated post-recovery slice.

A sample-size sweep (`scripts/run_simulation_size_sweep.py`; 7 N-values × 4 DGPs × 100 reps × 2 forecasters = 22,400 cells) establishes the newly-listed-symbol admission threshold for M6: $N \geq 80$ weekends under stationary / drift / structural-break DGPs, $N \geq 200$ under regime-switching (the production threshold). HOOD's empirical $N \approx 218$ (246 listed − 28 σ̂ warm-up) sits inside this band; HOOD's empirical Kupiec $p = 0.552$ at $\tau = 0.95$ is consistent with the simulation's pass-rate range at $N = 200$ (0.94 under DGP B, 0.99 under DGP A/C/D). See `reports/m6_simulation_study.md` and `reports/tables/sim_size_sweep_admission_thresholds.csv`.

![Per-symbol Kupiec $p$ at $\tau = 0.95$ across 100 reps × 4 DGPs (figure 7). Each panel shows side-by-side box-plots: the unweighted-Mondrian comparator (red) and M6 (blue), one box per synthetic symbol sorted by $\sigma_i$ (S00 lowest, S09 highest). The unweighted comparator's red boxes cluster near $p \approx 0$ for low- and high-$\sigma$ symbols (variance compression and expansion failures of the single-multiplier conformal); M6's blue boxes sit centred around $p = 0.5$ across every symbol, every DGP — uniform calibration as predicted by exchangeability under per-symbol standardisation.\label{fig:simulation}](figures/simulation_summary.pdf)

## 6.9 Summary

At $\tau = 0.95$ on the 2023+ held-out slice: realised **95.0%**, both Kupiec ($p = 0.956$) and Christoffersen ($p = 0.603$) pass, mean half-width **370.6 bps**. **All 10 symbols pass per-symbol Kupiec** with violation rates in $[2.9\%, 6.9\%]$; per-symbol Berkowitz LR sits in $[3.2, 16.7]$. Across the 40-cell (symbol × $\tau$) grid M6 carries 39/40 Kupiec passes, leading the strongest practitioner baseline GARCH-$t$ (31/40). Calendar sub-period calibration holds across {2023, 2024, 2025, 2026-YTD} (Kupiec $p \ge 0.054$ in every cell; 2/16 over-coverage rejections, 0/16 Christoffersen rejections). Joint-tail behaviour is empirically characterised: $P(k_w \ge 3) = 5.20\%$ at $\tau = 0.95$ vs the binomial $1.15\%$, with $k^\ast = 3$ stable across the 24-cell grid (0/24 sub-period rejections); the worst-observed weekend (2024-08-05 BoJ unwind) sat at $k_w = 10$ at $\tau = 0.85$. A four-DGP simulation predicts the per-symbol fix from architecture before the real-data confirmation; a forward-tape harness against a content-addressed frozen artefact carries the held-out evidence forward weekly. Berkowitz and DQ still reject pooled — bands remain *per-anchor calibrated*, not full-distribution calibrated — and the residual rejection localises to cross-sectional within-weekend common-mode (orthogonal to σ̂; §10 / Paper 4 territory). Supports $P_2$ (§3.4); $P_1$ evidenced by §8; $P_3$ by §7.
