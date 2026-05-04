# §6 — Results

This section reports the primary calibration evidence. Sharpness and per-component effects are deferred to §7; system-level implementation and audit reproducibility are in §8.

## 6.1 Evaluation protocol

The backtest panel comprises $N = 5{,}996$ weekend prediction windows: ten symbols × $639$ weekends, 2014-01-17 through 2026-04-24. Monday open is the target; Friday close and contemporaneous factor / vol-index readings compose $\mathcal{F}_t(s)$. We report (i) an *in-sample machinery check* (quantile fit and served on the full panel; realised coverage matches $\tau$ by construction), and (ii) the *out-of-sample validation* (quantile fit on $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$; Oracle served on the 1{,}730-row $\mathcal{T}_\text{test}$ slice). All $p$-values are two-sided Kupiec POF and Christoffersen independence tests. The base point estimator is unbiased (median residual $-0.5$ bps; MAE $90.0$; RMSE $163.3$) but a raw $\pm k\sigma$ wrap mis-calibrates at every $\tau$; the product is the per-regime conformal quantile + OOS-fit bump + walk-forward $\delta$ shift.

## 6.2 Served-band calibration — in-sample machinery check

Full panel ($N = 5{,}996$):

| Regime ($n$)          | $\tau = 0.68$: realised / width (bps) | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---|---|---|---|
| normal (3,924)        | 0.687 / 90.9  | 0.851 / 163.5 | 0.946 / 279.9 | 0.987 / 534.4 |
| long_weekend (630)    | 0.685 / 99.6  | 0.851 / 207.3 | 0.946 / 403.4 | 0.989 / 766.4 |
| high_vol (1,442)      | 0.683 / 174.2 | 0.853 / 312.2 | 0.951 / 557.8 | 0.992 /1{,}069.7 |
| **pooled (5,996)**    | **0.685 / 110.2** | **0.851 / 201.0** | **0.948 / 354.5** | **0.989 / 677.5** |

Pooled realised coverage matches the consumer's request to within $0.2$pp by construction.

## 6.3 Served-band calibration — out-of-sample (2023+)

Quantile fit on pre-2023 weekends; Oracle served on the 2023+ slice (1{,}730 rows × 173 weekends). The 12 trained quantiles are held-out; the 4+4 schedules ($c(\tau)$, $\delta(\tau)$) are deployment-tuned on this same slice, matching the prior hybrid Oracle's `BUFFER_BY_TARGET` budget. **The strongest defensible characterisation is *deployment-calibrated and walk-forward-stable*, not purely held-out end-to-end.** §9.3 carries the wider provenance disclosure; this concession is referenced — not re-stated — through the rest of the paper.

| Regime ($n$)       | $\tau = 0.68$: realised / width | $\tau = 0.85$ | $\tau = 0.95$ | $\tau = 0.99$ |
|---|---|---|---|---|
| normal (1,160)     | 0.660 / 90.9  | 0.829 / 163.5 | 0.939 / 279.9 | 0.988 / 534.4 |
| long_weekend (190) | 0.663 / 99.6  | 0.879 / 207.3 | 0.984 / 403.4 | 1.000 / 766.4 |
| high_vol (380)     | 0.750 / 174.2 | 0.900 / 312.2 | 0.968 / 557.8 | 0.992 /1{,}069.7 |
| **pooled (1,730)** | **0.680 / 110.2** | **0.850 / 201.0** | **0.950 / 354.5** | **0.990 / 677.5** |

### Conditional-coverage tests (pooled OOS)

| $\tau$ | Violations | Rate | Kupiec LR | $p_\text{uc}$ | Christoffersen LR | $p_\text{ind}$ |
|---:|---:|---:|---:|---:|---:|---:|
| 0.680 | 553 | 0.320 | 0.001 | **0.975** | 20.50 | 0.025 |
| 0.850 | 259 | 0.150 | 0.001 | **0.973** | 9.17 | **0.516** |
| **0.950** | **86** | **0.050** | **0.003** | **0.956** | **3.33** | **0.912** |
| **0.990** | **17** | **0.010** | **0.005** | **0.942** | **4.49** | **0.344** |

**The $\tau = 0.95$ row is the primary oracle-validation operating result.** Realised coverage is exactly $0.950$ (Kupiec $p_{uc} = 0.956$, Christoffersen $p_{ind} = 0.912$); at $\tau = 0.99$, M5 hits $0.990$, closing the prior baseline's tail ceiling at $0.972$. Mean half-width at $\tau = 0.95$ is **354.5 bps** — 20% narrower than the prior baseline's 443.5 (CI $-23.9\%$ to $-15.6\%$); per-regime $279.9 / 403.4 / 557.8$ bps. Christoffersen rejects only at $\tau = 0.68$ ($p_{ind} = 0.025$); §6.4.1 localises the residual to a *bimodal* per-symbol calibration error rather than a temporal-clustering story.

**Realised-move tertile decomposition at $\tau = 0.95$.** Stratifying the OOS slice by post-hoc realised-move $|z|$-score tertile (`reports/tables/v1b_prework_tertile.csv`) closes the loop between the §6.3 pooled headline and the §9.1 shock-tertile ceiling:

| tertile ($n$)     | realised | half-width (bps) | Kupiec $p$ |
|---|---:|---:|---:|
| calm   (497)      | 1.0000   | 340.2 | $0$ (over-covers) |
| normal (601)      | 0.9917   | 351.5 | $0$ (over-covers) |
| **shock** (632)   | **0.8718** | 368.9 | $0$ (under-covers) |
| **pooled** (1{,}730) | **0.9503** | **354.6** | **0.956** |

Half-width is approximately flat across tertiles (340–369 bps), so the band does not widen in shock periods — it just misses more often. The shock-tertile floor is the §9.1 disclosure made empirical: $87.2\%$ realised coverage on $n = 632$ shock-tertile weekends at nominal $\tau = 0.95$, materially below nominal but $\sim 7$pp above the conservative $80\%$ ceiling §9.1 prior reported. Calm- and normal-tertile over-coverage averages out the shock-tertile shortfall to deliver pooled $0.950$.

![Calibration curves on the 1{,}730-row 2023+ OOS slice. M5 (this paper, blue) tracks the $45^\circ$ diagonal across the served range $\tau \in [0.68, 0.99]$; the constant-buffer baseline (F0\_stale, vermilion) over-covers throughout (over-conservative Gaussian wrap on $\sigma_{20d}$); the prior hybrid (orange) follows M5 closely until $\tau \approx 0.97$ where it caps at $0.972$ — the prior baseline's finite-sample tail ceiling that M5 closes. Star marks the headline $\tau = 0.95$ result.\label{fig:calibration}](figures/fig2_calibration.pdf)

**Walk-forward stability.** Re-running conformal + bump + shift selection on six expanding-window splits (fractions 0.2–0.7) with the deployed $\delta$ schedule: walk-forward coverage matches nominal at every anchor (Kupiec $p$ = 0.43, 0.37, 0.36, 0.32 at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$); per-split mean half-width 124 / 215 / 357 / 746 bps tracks the full-OOS-fit 110 / 201 / 354 / 677 to within +13% / +7% / +1% / +10%. The schedule is not idiosyncratic to the 2023+ slice but does not upgrade the result to purely held-out end-to-end (§10.1 (the rolling artefact rebuild) is the upgrade path).

**Split-date sensitivity.** Repeating the M5 fit (quantile table re-trained, $c(\tau)$ re-fit per split, $\delta$ schedule held at the deployed walk-forward-fit values) at four OOS-split anchors {2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01} delivers realised $\tau = 0.95$ coverage of $\{0.9507,\ 0.9502,\ 0.9503,\ 0.9504\}$ — Kupiec $p \in \{0.864, 0.961, 0.956, 0.947\}$ and Christoffersen $p \in \{0.293, 0.666, 0.921, 0.887\}$ all pass; mean half-width $\{397.3, 371.4, 354.6, 388.9\}$ bps varies $\pm 5\%$ around the deployed value. The four-decimal-place agreement on realised coverage is what the $c(\tau)$ refit is *for* — pooled OOS Kupiec is the fit's selection criterion — so the diagnostic content is the half-width range and the per-split Christoffersen pass, not the realised-coverage tightness. With $\delta$ held fixed across split anchors, this is a sensitivity of the $c(\tau)$ component alone; the LOSO read below is the more informative provenance check (`reports/tables/v1b_robustness_split_sensitivity.csv`).

**Leave-one-symbol-out CV.** Hardens the schedule provenance more than the 6-split walk-forward. Holding out each of the ten symbols' rows from train + OOS fits and evaluating $\tau = 0.95$ on the held-out symbol's post-2023 slice: 8 of 10 LOSO bands are within $\pm 5$pp of nominal; mean realised $0.943$, std $0.076$. The schedule shows moderate fragility to held-out heavy-tail tickers (MSTR $0.786$, HOOD $0.856$, TSLA $0.879$) — symptom of the per-symbol bimodality §6.4 reports — and over-covers the well-behaved tail (SPY $1.000$, TLT $1.000$, GLD $0.994$). A single-multiplier compromise that the M6b2 lending profile rejects on principle (`reports/tables/v1b_robustness_loso.csv`).

![Walk-forward and split-date stability of the deployed schedule. **(a)** Six-split expanding-window walk-forward at four $\tau$ anchors: realised coverage on each test fold (markers) tracks nominal (dotted lines) at every anchor; bars are 95% binomial CIs. **(b)** Split-date sensitivity at four OOS-anchors {2021, 2022, 2023, 2024} with the quantile table re-trained and $c(\tau)$ re-fit per split: realised $\tau = 0.95$ coverage holds at $\{0.951, 0.950, 0.950, 0.950\}$ across anchors; the deployed split (yellow band) is not idiosyncratic.\label{fig:stability}](figures/fig3_stability.pdf)

This validates the oracle's coverage contract at $\tau = 0.95$. It does *not* prove $\tau = 0.95$ is the welfare-optimal operating point; that is Paper 3.

### 6.3.1 Extended diagnostics — Berkowitz and DQ

**Berkowitz (2001) joint LR on continuous PITs.** PITs reconstructed by inverting each served band against the realised Monday open through the per-regime conformal CDF. Rejects ($\text{LR} = 173.1$, $\hat\rho = 0.31$). **Engle-Manganelli (2004) DQ at $\tau = 0.95$.** Stat $= 32.1$, $p = 5.7 \times 10^{-6}$, violation rate $4.97\%$ over 86 weekends — rejection driven by clustering rather than a level miss; Christoffersen at $\tau = 0.95$ does not reject. Bands are *per-anchor calibrated*, not full-distribution calibrated.

**Localising the rejection.** Decomposing the lag-1 alternative under panel-row order: the AR(1) signal lives in the *cross-sectional within-weekend* ordering ($\hat\rho_{\text{cross}} = 0.354$, $p < 10^{-100}$, $n = 1{,}557$) — not the temporal-within-symbol ordering ($\hat\rho_{\text{time}} = -0.032$, $p = 0.18$, $n = 1{,}720$). A vol-tertile sub-split of `normal` regime (5 cells: `normal_calm` / `normal_mid` / `normal_heavy` / `long_weekend` / `high_vol`) leaves Berkowitz LR essentially unchanged ($173.0 \to 175.0$) while widening $\tau = 0.95$ band by $9\%$ — finer regime granularity is not the lever (`reports/tables/v1b_robustness_vol_tertile.csv`, `reports/tables/v1b_density_rejection_lag1_decomposition.csv`). The residual is common-mode within a weekend that the $\rho \times s$ factor switchboard does not fully partial out; §10 names the §10 candidate architectures that target it. Per-symbol DQ rejection concentrates on heavy-tail tickers (HOOD, MSTR, TSLA); per-symbol Berkowitz rejection is *bimodal*, see §6.4.1.

## 6.4 Per-symbol generalisation and point accuracy

M5 pools the conformity score across symbols within each regime; the M3 ablation (§7.2.2) confirmed adding a per-symbol stratum thins bins to $N \approx 50$–$300$ and degrades Christoffersen. 95th-percentile residual scores cluster around 0.04–0.07 for SPY/QQQ/TLT/GLD and 0.10–0.15 for HOOD/MSTR/NVDA/TSLA. Point-estimate MAE $90.0$ bps, RMSE $163.3$, median bias $-5.2$ bps. Bias does not propagate to coverage: the conformity score uses absolute residuals, so a non-zero median within a regime simply shifts $q_r(\tau)$ upward.

### 6.4.1 Per-symbol diagnostics — bimodal calibration error

Per-symbol Kupiec at $\tau = 0.95$ on the deployed band, paired with the per-symbol Berkowitz LR from M5 OOS PITs (`reports/tables/v1b_robustness_per_symbol.csv`); Figure \ref{fig:per-symbol} visualises the bimodality.

![Per-symbol bimodality on the 2023+ OOS slice. Each ticker appears at its M5-PIT variance $\hat\sigma^2_z$ (x) and per-symbol Kupiec $p$-value at $\tau = 0.95$ (y, log scale). Two failure modes appear: SPY/QQQ/GLD/TLT/AAPL reject from variance compression ($\hat\sigma^2_z \ll 1$, bands too wide, near-zero violation rate, orange down-triangles); TSLA/HOOD/MSTR reject from variance expansion ($\hat\sigma^2_z > 1.5$, bands too narrow, $11$–$16\%$ violation rate, blue up-triangles). NVDA and GOOGL pass both at the deployed schedule. The pattern is the canonical "common multiplier on heterogeneous tails" failure of a single-cell-multiplier conformal at this granularity.\label{fig:per-symbol}](figures/fig4_per_symbol.pdf)

| Symbol | $n_\text{oos}$ | viol. rate | Kupiec $p$ | Berkowitz LR | $\hat{\sigma}^2_z$ |
|---|---:|---:|---:|---:|---:|
| SPY  | 173 | 0.000 | 0.000 | $85.83$ | $0.30$ |
| QQQ  | 173 | 0.006 | 0.001 | $45.41$ | $0.44$ |
| TLT  | 173 | 0.000 | 0.000 | $51.01$ | $0.43$ |
| GLD  | 173 | 0.006 | 0.001 | $45.06$ | $0.44$ |
| AAPL | 173 | 0.006 | 0.001 | $13.56$ | $0.67$ |
| GOOGL| 173 | 0.029 | 0.168 | $7.14$  | $0.77$ |
| NVDA | 173 | 0.041 | 0.552 | $4.02$  | $1.19$ |
| TSLA | 173 | 0.116 | 0.001 | $34.06$ | $1.74$ |
| HOOD | 173 | 0.139 | 0.000 | $30.47$ | $1.67$ |
| MSTR | 173 | 0.156 | 0.000 | $64.78$ | $2.10$ |

The pattern is *bimodal*: large-cap equities and the RWA anchors (SPY, QQQ, GLD, TLT) reject from variance compression ($\hat{\sigma}^2_z \ll 1$, bands too wide, near-zero violation rate); heavy-tail tickers (TSLA, HOOD, MSTR) reject from variance expansion ($\hat{\sigma}^2_z > 1.5$, bands too narrow, $11$–$16\%$ violation rate). NVDA and GOOGL pass both. The mechanism is a single $(r, \tau)$-keyed multiplier mis-calibrating symbols whose residual scale deviates from the regime average in opposing directions — the canonical "common multiplier on heterogeneous tails" failure. HOOD per-symbol Kupiec specifically: fails at $\tau \in \{0.68, 0.85, 0.95\}$, *passes* at $\tau = 0.99$ (violation rate $2.3\%$, Kupiec $p = 0.138$); the deployed $\tau = 0.99$ tail is wide enough for HOOD's residual. M5 carries this disclosure; §10.4 names the §10 candidate architectures that target it.

**MSTR-removed panel sensitivity.** A 9-symbol re-fit excluding MSTR (the heaviest-tail ticker, $\hat{\sigma}^2_z = 2.10$) leaves pooled $\tau = 0.95$ realised coverage essentially unchanged ($0.9503 \to 0.9505$, $\Delta = +0.03$pp) while shrinking mean half-width by $10.0\%$ ($354.6 \to 319.1$ bps; `reports/tables/v1b_prework_mstr_sensitivity.csv`). The reading is the same bimodality at panel level: MSTR's residual scale anchors the fitted $c(0.95) = 1.300$ bump, so removing the symbol releases $\sim 10\%$ of the deployed band's width with no coverage cost on the remaining nine symbols. The 2020-08-01 factor pivot for MSTR (§5.4) is therefore not a load-bearing modeling choice for the headline, but the symbol's heavy tail is doing visible work on the deployed schedule.

### 6.4.2 GARCH(1,1) baseline

The textbook econometric default for a time-varying interval at $\tau$ is per-symbol GARCH(1,1) on log Friday-to-Monday returns with Gaussian innovations, fit on the pre-2023 train and recursive $\hat\sigma_t$ over OOS (`reports/tables/v1b_robustness_garch_baseline.csv`). Head-to-head on the 1{,}730-row OOS slice:

| $\tau$ | GARCH(1,1) realised / hw (bps) / Kupiec $p$ | M5 realised / hw / Kupiec $p$ |
|---:|---|---|
| 0.68 | $0.7393$ / $163.4$ / $0.000$ | $0.7353$ / $137.5$ / $0.000$ |
| 0.85 | $0.8514$ / $236.6$ / $0.866$ | $0.8867$ / $235.1$ / $0.000$ |
| 0.95 | $\mathbf{0.9254}$ / $322.2$ / $\mathbf{0.000}$ | $\mathbf{0.9503}$ / $354.6$ / $\mathbf{0.956}$ |
| 0.99 | $\mathbf{0.9630}$ / $423.7$ / $\mathbf{0.000}$ | $\mathbf{0.9902}$ / $677.7$ / $\mathbf{0.942}$ |

A nominal-anchor comparison at $\tau = 0.95$ would read GARCH at $322.2$ bps and M5 at $354.6$ bps and infer GARCH is ~9% sharper. That comparison is unfair: GARCH realises $0.9254$ at the same nominal claim while M5 realises $0.9503$, so the two are at different points on the coverage–width curve. **At matched 95% realised coverage** (GARCH re-served at the smallest $\tau_\text{nominal}$ delivering OOS realised $\ge 0.95$, found at $\tau_\text{nominal} = 0.981$ on the same OOS slice; `reports/tables/v1b_prework_garch_matched.csv`), GARCH's mean half-width is $385.7$ bps — **8.8% wider than M5's $354.6$ bps at the same realised coverage.** GARCH also fails Kupiec at $\tau \in \{0.68, 0.95, 0.99\}$ on the nominal grid (the textbook tail-mis-coverage failure of Gaussian innovations); the matched-coverage exercise establishes that the calibration failure does not buy bandwidth, it costs bandwidth.

### 6.4.3 Per-asset-class deviation

Pooled OOS coverage stratified by asset class shows the per-symbol bimodality of §6.4.1 expressed at the class level: equities (8 syms, 1{,}384 obs) under-cover at $\tau = 0.95$ by ~1pp (realised 0.9386, Kupiec $p = 0.060$), while GLD and TLT each over-cover by ~5pp (realised 0.9942 and 1.0000, Kupiec rejecting in the *too-wide* direction). Same root cause as §6.4.1 — single multiplier on heterogeneous residual scales — expressed across rather than within classes. Full table at `reports/tables/v1b_robustness_per_class.csv`.

## 6.5 Comparison to incumbent oracle surfaces

We measure what consumers receive from deployed alternatives across three reconstructions: a regular-Pyth Hermes-derived band (265 obs, 2024+), a Chainlink Data Streams v10/v11 reconstruction (87 obs, frozen 2026-02-06 → 2026-04-17), and a forward-cursor RedStone Live tape ($n = 12$, 2026-04-26+); Pyth Pro / Blue Ocean is excluded on access and window grounds. Caveats: sample CIs are wide; composition is skewed toward large-cap normal-regime weekends (compare to Soothsayer's 279.9 bps normal-regime half-width); wrap multipliers are *consumer-supplied* — none of the three incumbents publishes a calibration claim a consumer can read directly.

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

The naive textbook 95% wrap returns 10.2% — under-calibrated by ≈10× as a consumer-supplied band. The smallest $k$ delivering ≥ 95% is $k \approx 50$ (279.5 bps); on the regime-matched M5 comparator (279.9 bps) Pyth+50× is *width-equivalent at matched coverage*. Per-symbol availability is uneven (SPY 69%, QQQ 65%, TLT 59%, TSLA 25%; AAPL/GOOGL/HOOD/NVDA 0% — Pyth's RH equity feeds did not publish before 2024). The Soothsayer differentiator on this panel is the calibration receipt, not the bandwidth.

![Coverage versus mean half-width across methods at the four served $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ (vertical dotted lines). M5 (blue stars) and the prior hybrid (orange circles) are at full panel ($n = 1{,}730$); GARCH(1,1) baseline (vermilion squares) is the textbook econometric default; Pyth $\pm k\!\cdot\!\mathrm{conf}$ (green diamonds, $n = 265$) is the consumer-supplied wrap that achieves the claimed coverage at the smallest $k$ on the available subset; Chainlink Streams (purple, $n = 87$) is the manual mid$\,\pm\,k\%$ wrap on the marker-aware-decoded sample. M5 sits on the calibration-vs-sharpness Pareto frontier at every served $\tau$; GARCH undercovers at $\tau \in \{0.95, 0.99\}$ despite slightly tighter bands; Pyth and Chainlink subsets cover comparable widths but on small, heterogeneous samples (§6.5 caveats).\label{fig:pareto}](figures/fig5_pareto.pdf)

**Chainlink Data Streams v10 / v11.** v10 (Tokenized Asset, `0x000a`) carries no `bid`/`ask`/confidence on the wire — band-less by construction [chainlink-v10]. v11 (RWA Advanced, `0x000b`) adds `bid`, `ask`, `mid`. Marker-aware classifier on a 26-report weekend scan:

| Symbol (n) | Pattern | Wire `bid` | Wire `ask` | Implied spread |
|---|---|---:|---:|---:|
| SPYx (6) | PURE_PLACEHOLDER | 21.01 | 715.01 | ~18,858 bps |
| QQQx (6) | BID_SYNTHETIC | 656.01 | — | 117–329 bps |
| TSLAx (7) | BID_SYNTHETIC | 372.01 | — | 117–329 bps |
| NVDAx (1) | REAL | 208.07 | 208.14 | ~3.4 bps |

The v11 weekend `bid` carries a synthetic `.01` suffix at 100% incidence on three of four mapped xStocks — a generated bookend, not a venue quote. To get a usable band a v11 consumer must replace wire `bid`/`ask` with a manual `mid ± k%` wrap; an earlier 87-obs panel found $k \approx 3.2\%$ delivers ≥ 95% — ~14% wider than the regime-matched M5. Neither v10 nor v11 publishes a coverage band a consumer can read directly.

## 6.6 Path coverage — endpoint vs intra-weekend

The §6.3 result is *endpoint coverage*: realised Monday open lies inside the served band. A DeFi consumer holding an xStock as collateral is exposed at every block over the weekend; a Saturday liquidation when the on-chain xStock briefly trades outside the band is a real loss event even if Monday open returns inside. We measure path coverage on $[\text{Fri 16:00 ET},\, \text{Mon 09:30 ET}]$ against 24/7 stock-perp 1m bars from `cex_stock_perp/ohlcv/the prior hybrid Oracle` (Kraken Futures `PF_<sym>XUSD`, xStock-backed). Sample: 19 weekends × 9 symbols (TLT excluded — no perp listing), $n = 118$ (symbol, weekend) pairs per anchor, 2025-12-19 → 2026-04-24:

| $\tau$ | $n$ | endpoint | path | gap (pp) |
|---:|---:|---:|---:|---:|
| 0.68 | 118 | 0.771 | 0.509 | $+26.3$ |
| 0.85 | 118 | 0.915 | 0.729 | $+18.6$ |
| **0.95** | **118** | **0.983** | **0.839** | $+\mathbf{14.4}$ |
| 0.99 | 118 | 1.000 | 0.966 | $+3.4$ |

At $\tau = 0.95$ the raw perp path stays inside the band for $0.839$ of weekends — a $14.4$pp gap concentrated in `normal` weekends ($+18.2$pp, $n = 66$) rather than `high_vol` ($+8.9$pp, $n = 45$), consistent with `high_vol`'s wider band absorbing path noise. The gap collapses to $+3.4$pp at $\tau = 0.99$ — stepping up one anchor approximately closes it. Sample is small (binomial CI on the $\tau = 0.95$ pooled gap is $\pm 6$pp); the test is directional. Continued capture is tracked under scryer item 51 and §10.1 (the path-fitted conformity score).

![Path coverage gap on the 24/7 stock-perp reference. **(a)** Endpoint coverage (blue) tracks nominal across $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ (and over-covers at low $\tau$); path coverage (vermilion) — the fraction of weekends where the perp 1m bar high/low stay inside the served band over the full $[\text{Fri 16:00, Mon 09:30}]$ window — runs $26.3$/$18.6$/$14.4$/$3.4$pp behind. The gap collapses at $\tau = 0.99$. **(b)** At $\tau = 0.95$ the gap concentrates in `normal` weekends ($+18.2$pp, $n = 66$) rather than `high_vol` ($+8.9$pp, $n = 45$). Sample is small ($n = 118$ symbol-weekends across 19 calendar weekends, 2025-12 to 2026-04); the read is directional and §10.1 (the path-fitted conformity score) path-fitted variant is the methodology fix.\label{fig:path-coverage}](figures/fig6_path_coverage.pdf)

### 6.6.1 Robustness of the perp-path gap

Three confounds inherent in the perp tape (`reports/v1b_path_coverage_robustness.md`), each checked independently at $\tau = 0.95$:

| Variant | gap (pp) | Note |
|---|---:|---|
| **Headline (raw)** | **14.4** | $n = 118$ |
| (A) Basis-normalized to Fri 16:00 ET | $10.2$ | mean $|\text{basis}|$ at anchor $= 106$ bps |
| (B) Volume floor `volume_base > 1.0` | $14.3$ | $n = 63$ ($4.4\%$ of bars survive) |
| (B) Volume floor `volume_base > 10.0` | $7.1$ | $n = 42$ ($2.1\%$) |
| (C) Sustained crossing, 5m / 15m rolling median | $12.7$ | violations not single-print noise |

Roughly $4$pp of the headline is start-of-window perp-spot basis; ${\sim}95\%$ of perp bars carry near-zero `volume_base`, and the heaviest-volume subsample (volume floor $> 10.0$, $n = 42$ — the lower bound of the cited range) reads $7.1$pp at the cost of small sample size. The residual after all three is approximately **$7$–$10$pp of genuine intra-weekend path-coverage shortfall**, with the lower bound supported by $n = 42$ and the upper bound by $n = 63$ (volume floor $> 1.0$). The structural component — running-max stochastically dominates endpoint, so endpoint-fit conformity scores cannot deliver path coverage at the same $\tau$ — accounts for some unknown share; the remainder is method-correctable in next-generation via a path-fitted conformity score (§10.1 (the path-fitted conformity score)). At $\tau = 0.99$ every variant's gap is $\le 3.4$pp.

### 6.6.2 Other references and takeaway

The on-chain xStock swap leg (`dex_xstock/swaps/the prior hybrid Oracle`) is the consumer-experienced object directly; the cache currently begins after the panel's last Monday and there is no overlap, picked up at the next artefact rebuild. A factor-projected path from CME 1m futures on the full 2018+ panel ($n = 3{,}861$ symbol-weekends, $95.1\%$ observable) at $\tau = 0.95$ gives endpoint $0.964$, path $0.992$ — a *negative* gap of $-2.8$pp, by construction (band centre is the factor-implied projection); a smoothness check on the point estimator, not a consumer-experienced measure. Full tables: `reports/v1b_path_coverage{,_robustness}.md`, `reports/tables/path_coverage_{perp,cme}*.csv`.

The endpoint contract stands. A consumer requiring path coverage at level $\tau$ should step up one anchor (empirically closes the gap on this slice at $\tau = 0.99$), absorb the residual through downstream policy (Paper 3), or — for continuous-consumption products that cannot use the step-up lever (band-aware AMMs the canonical case) — adopt the path-fitted conformity-score variant on the next-generation roadmap.

## 6.7 Summary

At $\tau = 0.95$ on the 2023+ held-out slice: realised **95.0%**, both Kupiec and Christoffersen pass, mean half-width **354.5 bps**, six-split walk-forward passes Kupiec at every anchor, **20% narrower than the prior hybrid Oracle** at indistinguishable coverage through $\tau \le 0.95$. A naive regular-Pyth $k = 1.96$ wrap realises 10.2%; v10 is band-less; v11's wire `bid` carries a synthetic `.01`-suffix on three of four mapped xStocks. Berkowitz and DQ both reject — bands are *per-anchor calibrated*, not full-distribution calibrated. Supports P2 (§3.4); P1 evidenced by §8; P3 by §7.
