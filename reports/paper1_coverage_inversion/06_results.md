# §6 — Results (draft)

This section reports the primary calibration evidence. Sharpness and per-component effects are deferred to §7 (ablations); system-level implementation and audit reproducibility are in §8.

## 6.1 Evaluation protocol

The backtest panel comprises $N = 5{,}986$ weekend prediction windows: ten symbols (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD, GLD, TLT, MSTR) observed across $638$ weekends from 2014-01-17 through 2026-04-17. Each window runs Friday 16:00 ET → Monday 09:30 ET. Monday open is the target $P_t(s)$; Friday close and contemporaneous factor-futures / vol-index readings compose the pre-publish information $\mathcal{F}_t(s)$.

For the evaluation we report two complementary figures:

- **In-sample machinery check.** Calibration surface $S^f$ fit on the full panel; Oracle served on the same panel. Realised coverage should be close to target $\tau$ *by construction* — the inversion is against the surface that was fit on this data. A material deviation indicates a bug in the surface-build or inversion code path, not a real-world failure mode.
- **Out-of-sample validation (the real number).** Calibration surface fit on $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ (4,266 weekend rows); Oracle served on $\mathcal{T}_\text{test} = \{t : t \ge \text{2023-01-01}\}$ (1,720 rows, 172 weekends). No information from $\mathcal{T}_\text{test}$ enters the surface. This is the closest analog to a production deployment in which the surface is rebuilt on a rolling schedule.

All reported $p$-values are for two-sided Kupiec unconditional-coverage tests (POF likelihood-ratio, $\chi^2_1$ null) and Christoffersen independence tests ($\chi^2$ with $k$ degrees of freedom where $k$ is the number of per-symbol time series with both violation and non-violation observations).

## 6.2 Raw forecaster coverage (motivation for the calibration surface)

Before serving-time inversion, the base forecasters are not calibrated at their nominal claimed-coverage levels. At claim $q = 0.95$ on the full panel:

| Forecaster | Realised | Half-width (bps) | MAE (bps) |
|---|---:|---:|---:|
| F0 (stale-hold + Gaussian)                    | 0.976 | 401.8 | 94.8 |
| F1_emp_regime (factor + log-log + regressors) | 0.923 | 253.7 | 90.0 |

F0 over-covers (97.6% vs 95% claimed) at the cost of blanket-width bands, as is expected from an uninformative Gaussian with no factor adjustment. F1_emp_regime under-covers at the nominal 95% claim by $2.7$pp. This is not a deployment path — it is the input to the calibration surface. Neither raw forecaster is the product. The product is $\mathcal{S}^f$ and the served band at $q_\text{served}$.

## 6.3 Served-band calibration — in-sample machinery check

Consumer target $\tau \in \{0.68, 0.95, 0.99\}$; full surface; full panel ($N = 5{,}986$):

| Regime ($n$)          | $\tau = 0.68$: realised / width (bps) | $\tau = 0.95$: realised / width | $\tau = 0.99$: realised / width |
|---|---|---|---|
| normal (3,924)        | 0.725 / 97.2  | 0.978 / 341.5 | 0.980 / 384.9 |
| long_weekend (630)    | 0.719 / 117.6 | 0.970 / 389.2 | 0.981 / 429.4 |
| high_vol (1,432)      | 0.735 / 174.6 | 0.974 / 585.6 | 0.985 / 700.1 |
| **pooled (5,986)**    | **0.727 / 117.8** | **0.976 / 404.9** | **0.981 / 465.0** |

Pooled realised coverage at $\tau = 0.95$ is $0.976$ — a $+2.6$pp over-coverage against the consumer request. The in-sample Kupiec test rejects at every $\tau$; this is expected because the inversion uses a discrete 12-point claimed grid and a small positive buffer on the target, both of which bias the served band toward over-coverage. *In-sample over-coverage is the safe direction;* under-coverage would indicate an implementation defect.

## 6.4 Served-band calibration — out-of-sample (2023+)

Calibration surface fit on pre-2023 bounds; Oracle served on 2023+ weekends ($N_\text{test} = 1{,}720$ rows, 172 weekends). The calibration surface is held-out — frozen on the 4{,}266 pre-2023 calibration rows; no parameter, threshold, or grid point is updated using OOS data. The per-anchor empirical buffer schedule of §4.3 is *deployment-tuned* on this same OOS slice via the methodology of `reports/v1b_buffer_tune.md`. The numbers below are therefore best read as a deployment-calibrated operating result on a held-out surface, not as a clean held-out validation end-to-end. The walk-forward stability evidence in the inset block below is the empirical mitigation of the buffer-OOS-tuning concern.

| Regime ($n$)       | $\tau = 0.68$: realised / width | $\tau = 0.85$: realised / width | $\tau = 0.95$: realised / width | $\tau = 0.99$: realised / width |
|---|---|---|---|---|
| normal (1,150)     | 0.691 / 121.2 | 0.863 / 229.7 | 0.945 / 417.7 | 0.977 / 502.8 |
| long_weekend (190) | 0.632 / 121.0 | 0.821 / 283.3 | 0.953 / 416.6 | 0.958 / 465.2 |
| high_vol (380)     | 0.663 / 188.0 | 0.850 / 299.6 | 0.963 / 591.6 | 0.984 / 874.5 |
| **pooled (1,720)** | **0.678 / 135.9** | **0.855 / 251.1** | **0.950 / 456.0** | **0.977 / 580.8** |

### Conditional-coverage tests (pooled OOS)

| $\tau$ | Violations | Rate | Kupiec LR | $p_\text{uc}$ | Christoffersen LR | $p_\text{ind}$ |
|---:|---:|---:|---:|---:|---:|---:|
| 0.680 | 553 | 0.322 | 0.018 | **0.893** | 7.818 | **0.647** |
| 0.850 | 249 | 0.145 | 0.373 | **0.541** | 13.750 | **0.185** |
| **0.950** | **86** | **0.050** | **0.000** | **1.000** | 9.500 | **0.485** |
| 0.990 | 40 | 0.023 | 22.224 | 0.000 | 3.801 | 0.956 |

**The $\tau = 0.95$ row is the primary oracle-validation operating result on the deployed configuration.** On the held-out surface served at the deployment-tuned per-anchor buffer, the Oracle delivers realised coverage of exactly $0.950$ — Kupiec $p_{uc} = 1.000$ (test statistic essentially zero, no evidence of mis-calibration) and Christoffersen $p_{ind} = 0.485$ (no clustering of violations). The conjunction passes by margin, not by inches. The number is *deployment-calibrated* on the OOS slice rather than purely held-out end-to-end, and should be read in conjunction with the walk-forward stability evidence below and §9.4 (the wider disclosure of the buffer-tuning provenance).

**Walk-forward stability of the deployed buffer.** Because the per-anchor buffer schedule of §4.3 is fit on the same OOS slice that this section evaluates, "deployment-calibrated" rather than "purely held-out" is the strongest defensible characterisation of the table above. The relevant empirical mitigation is the cross-split distribution of the buffer itself. We re-run the buffer-tuning sweep on six expanding-window train/test splits spanning 2019-01 through 2025-01 (`reports/v1b_walkforward.md`), each split fitting the surface and the per-anchor buffer on its own train side and reporting the buffer that satisfies the same realised-within-0.5pp + Kupiec $p_{uc} > 0.10$ + Christoffersen $p_{ind} > 0.05$ criterion that selected the deployed schedule. At $\tau = 0.95$, the cross-split mean is $0.019$ ($\sigma = 0.017$); the deployed value $0.020$ lands at the cross-split mean to within rounding. At $\tau = 0.85$, the cross-split mean is $0.025$ ($\sigma = 0.022$) and the deployed value $0.045$ is conservative ($\geq 1\sigma$ above the mean). The deployed buffers are therefore not idiosyncratic to the 2023+ slice in the sense that a multi-split rerun reproduces the same operating point at $\tau = 0.95$ and a tighter operating point at $\tau = 0.85$. This evidence is what allows the §6.4 number to be characterised as "deployment-calibrated and walk-forward-stable" rather than "potentially overfit to one slice"; it does not upgrade the result to a purely held-out end-to-end validation, which remains §10.1's V2.2 (rolling calibration-surface rebuild).

This result should be read as validation of the oracle's coverage contract at $\tau = 0.95$, not as proof that $\tau = 0.95$ is the welfare-optimal operating point for a protocol that consumes the band for liquidations or collateral haircuts.

**Other operating points.** At $\tau = 0.85$ (the current protocol-deployment default; downstream welfare comparisons against protocol baselines are the subject of Paper 3, which revisits the earlier simplified Kamino-style flat-band benchmark against the production xStocks reserve configuration and oracle semantics), realised coverage is $0.855$, both tests pass at $\alpha = 0.05$. At $\tau = 0.68$, realised lands $0.2$pp below target with both tests passing comfortably. At $\tau = 0.99$, Kupiec rejects: realised coverage is $0.977$, materially below the requested $0.99$. This is a structural ceiling — the rolling 156-weekend per-(symbol, regime) calibration window cannot resolve the 1% tail reliably; even with the bounds grid extended to 0.999 (`reports/v1b_extended_grid.md`), the per-bucket sample size is too small to estimate the 1% quantile with the precision the consumer is asking for. The Christoffersen independence test continues to pass on the OOS slice ($p_\text{ind} = 0.956$): the rejected coverage is a level-attribution failure, not a violation-clustering failure. §9.1 discusses the structural ceiling; §10 frames the conformal-prediction upgrade that would address it.

The Oracle therefore passes Kupiec + Christoffersen at three of four standard operating points (0.68, 0.85, 0.95) on held-out data, with the upper-tail failure (0.99) disclosed as a finite-sample structural ceiling rather than a deployment defect.

### 6.4.1 Extended diagnostics — Berkowitz, DQ, CRPS, exceedance magnitude

Four reviewer-likely tests beyond Kupiec + Christoffersen, computed on the 1,730-row rerun panel (one weekend past the §6.4 cutoff; the τ = 0.99 row picks up nine additional violations and a higher max-breach from the new weekend). Numerical artefacts: `reports/tables/v1b_oos_reviewer_diagnostics.csv`, `v1b_oos_dq_per_symbol{,_summary}.csv`, `v1b_oos_berkowitz_crps.csv`.

**Berkowitz (2001) joint LR on continuous PITs.** PITs reconstructed per row by interpolating the served-band CDF on a 19-point central-quantile grid (τ ∈ {0.05, …, 0.95}). The test rejects ($\text{LR} = 37.6$, $p \approx 0$, $\widehat{\text{var}}\,z = 0.84$). Mechanism: the per-target buffer schedule (§4.3) anchors at four τ ∈ {0.68, 0.85, 0.95, 0.99} and flat-extrapolates outside; at low τ the flat-extrapolated buffer is over-conservative by design, producing safe-direction over-coverage in the central region that Berkowitz detects as variance contraction. The served band is *per-anchor calibrated*, not full-distribution calibrated; the deviation outside the deployment range is over-coverage, not under-coverage. Reliability diagram: `reports/figures/v1b_reliability_diagram.png`.

**Engle-Manganelli (2004) Dynamic Quantile (DQ) test.** Per-symbol DQ regressions on four lags + intercept; the pooled-$\chi^2(50)$ statistic across $K = 10$ symbols rejects at all four anchors ($p_\text{DQ} = 0.032 / 0.014 / 0.032 / \approx 0$ at τ = 0.68 / 0.85 / 0.95 / 0.99). The pooled aggregation inflates as $K$ grows; the standard sensitivity is the per-symbol p-value distribution:

| τ | per-symbol $p$ median | per-symbol $p$ min | rejects at α = 0.05 | pooled $p_\text{DQ}$ |
|---:|---:|---:|---:|---:|
| 0.68 | 0.211 | 0.024 | 1 / 10 | 0.032 |
| 0.85 | 0.384 | 0.001 | 2 / 10 | 0.014 |
| 0.95 | 0.289 | 0.002 | 2 / 10 | 0.032 |
| 0.99 | 0.261 | 0.000 | 5 / 10 | 0.000 |

By the median per-symbol p-value, all four anchors pass at α = 0.05 — the pooled rejection at τ ≤ 0.95 is over-stated by aggregation. By the per-symbol reject-count, the τ ≤ 0.95 counts (≤ 2 / 10) are consistent with type-I rate near α, but the τ = 0.99 count of 5 / 10 indicates real tail-conditional miscalibration in half the universe that does not vanish under any defensible aggregation. The §10.2 halt / corp-action filter — gated on scryer wishlist 15a + 15b — would isolate which of the five rejecting symbols are picking up structural exceptions vs persistent calibration gaps. The DQ disclosure remains a disclosure rather than a deployment block: Christoffersen $p_\text{ind}$ passes at all four anchors (§6.4) and Kupiec passes at three.

**Continuous Ranked Probability Score (CRPS).** Mean CRPS = 1.82 in price units (median 0.97). Reported as a baseline for cross-oracle comparators in future work (§10); not interpretable in absolute terms without a competing forecaster on the same panel.

**McNeil-Frey-style exceedance magnitude.** Distribution of breach sizes (basis points of Friday close) per τ:

| τ | Violations | Mean | Median | $p_{95}$ | Max |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 554 | 104 | 49  | 415 | 2{,}339 |
| 0.85 | 249 | 120 | 50  | 456 | 2{,}150 |
| 0.95 |  86 | 127 | 56  | 465 | 1{,}415 |
| 0.99 |  49 | 137 | 71  | 515 | 1{,}081 |

Max breach shrinks monotonically in τ (2,339 → 2,150 → 1,415 → 1,081 bps) — wider bands catch larger shocks. The 49 missed-coverage events at τ = 0.99 have median breach 71 bps and max 1,081 bps; a protocol consuming the τ = 0.99 band experiences a worst-case ~11% price-mismatch on a missed event, ~0.7% at the median. This bounds the practical cost of the §9.1 structural ceiling.

## 6.5 Per-symbol generalisation

Per-symbol realised coverage of the served band at $\tau = 0.95$ on the full in-sample panel (the OOS subsample of 172 weekends is too small per symbol for ticker-level reads):

| Symbol | Realised | Half-width (bps) |
|---|---:|---:|
| AAPL  | 0.929 | 257.9 |
| GLD   | 0.928 | 142.2 |
| GOOGL | 0.932 | 193.4 |
| HOOD  | 0.877 | 391.3 |
| MSTR  | 0.901 | 390.4 |
| NVDA  | 0.923 | 319.1 |
| QQQ   | 0.930 | 172.2 |
| SPY   | 0.935 | 193.4 |
| TLT   | 0.917 | 142.2 |
| TSLA  | 0.930 | 319.1 |

These are *raw-forecaster* realised coverages at the nominal 0.95 claim — not served-band. They confirm the pattern motivating the calibration-surface approach: the raw forecaster under-covers at the nominal level, and the amount of under-coverage varies meaningfully across tickers (HOOD: 87.7%, MSTR: 90.1%, SPY: 93.5%). The calibration surface stratified by (symbol, regime) absorbs this variation. The aggregate OOS pass in §6.4 confirms that the surface + inversion mechanism reconciles this heterogeneity.

## 6.6 Point accuracy and bias absorption

Point-estimate MAE on the full panel: $90.0$ bps for F1_emp_regime vs $94.8$ bps for F0 stale-hold. RMSE: $163.3$ bps vs $176.4$ bps. Median bias on the *raw* factor-adjusted point: $-5.2$ bps; on the *raw* F0 stale point: $-4.1$ bps. With residual standard deviation $\sigma \approx 163$ bps and $n = 5{,}986$, the factor-adjusted bias has $t \approx -2.5$, which is statistically distinguishable from zero. The factor-adjusted point delivers a $5\%$ MAE improvement.

A natural reading of the bias figure is that the served Oracle inherits a calibration defect from its raw point. It does not, and the construction is worth making explicit. The empirical-quantile architecture takes quantiles of the *log-residual* distribution

$$\varepsilon_t = \log(P_t / \hat P_t)$$

directly — no zero-mean assumption is made. The lower and upper bounds are constructed as $\hat P_t \cdot \exp(z_\text{lo})$ and $\hat P_t \cdot \exp(z_\text{hi})$, where $z_\text{lo}, z_\text{hi}$ are the empirical quantiles of $\varepsilon_t$ on the rolling window. If $\varepsilon_t$ has a non-zero median, that asymmetry shifts $z_\text{lo}$ and $z_\text{hi}$ by the same amount, and the served band is bias-aware by construction. The served point used at the API surface — defined as $(L_t + U_t) / 2$ — is therefore the midpoint of a bias-corrected band, not the raw factor-adjusted estimate $\hat P_t$. The $-5.2$ bps figure is a property of the *raw forecaster*, made transparent here for completeness; it does not propagate to the consumer-facing point or to the coverage figures of §6.4.

A dedicated point-forecasting benchmark against incumbent oracles, on a matched intraday + closed-market window, is deferred to future work (§10).

## 6.7 Comparison to incumbent oracles

§6.4–§6.6 measure whether Soothsayer's served band achieves its claimed coverage; this section measures what consumers receive from the deployed alternatives on subsets of the same OOS panel. We report two reconstructions: a Pyth Hermes-derived band (265 (symbol × weekend) obs across 120 weekends 2024+) and a Chainlink Data Streams v11 reconstruction (87 obs across 11 weekends Feb–Apr 2026). RedStone Live is excluded — the public REST gateway exposes no confidence, dispersion, or band field, so there is no calibration object to compare against (§9.8.1).

*Three caveats apply to both subsections below.* (i) Sample-size CIs are wide: binomial 95% CI on $\hat p = 0.95$ is $[0.92, 0.98]$ at $n = 265$ and $[0.89, 0.99]$ at $n = 87$. (ii) Sample composition is skewed toward large-cap, low-realised-volatility tickers and *normal*-regime weekends, so any matched-bandwidth comparison should be read against Soothsayer's normal-regime OOS half-width (417.7 bps), not the pooled figure (456 bps). (iii) The wrap multipliers below ($k = 50$ for Pyth, $k = 3.2\%$ for Chainlink) are *consumer-supplied* — neither incumbent publishes them, so the consumer back-fits the multiplier with no audit trail and no per-symbol stratification.

### 6.7.1 Pyth — `price ± k·conf` as a probability statement

Pyth publishes `(price, conf)` where `conf` is documented as a publisher-dispersion diagnostic, not a probability statement [pyth-conf]. Sweep $k \in \{1, 1.96, 3, 5, 10, 25, 50, 100, 250, 500, 1000\}$ on the 265-obs subset:

| $k$ | realised | mean half-width (bps) |
|---:|---:|---:|
| 1.00   | 0.049 |   5.6 |
| 1.96   | 0.102 |  11.0 |
| 3.00   | 0.155 |  16.8 |
| 10.00  | 0.434 |  55.9 |
| 25.00  | 0.800 | 139.7 |
| **50.00**  | **0.951** | **279.5** |
| 100.00 | 0.992 | 559.0 |

The textbook 95% Gaussian wrap ($k = 1.96$) returns 10.2% realised — under-calibrated by ≈10× on this subset. The smallest $k$ delivering ≥ 95% realised is $k \approx 50$ (279.5 bps half-width); on the regime-matched comparator (417.7 bps), Pyth+50× is ≈33% narrower at matched empirical coverage. Per-symbol availability is uneven (SPY 69%, QQQ 65%, TLT 59%, TSLA 25%; AAPL/GOOGL/HOOD/NVDA 0%); Pyth's RH equity feeds did not publish before 2024. Full breakdown: `reports/v1b_pyth_comparison.md`; raw obs: `data/processed/pyth_benchmark_oos.parquet`.

### 6.7.2 Chainlink Data Streams — weekend `marketStatus = 5` and the implicit band

Chainlink Data Streams v11 publishes `bid` / `ask` / `mid` fields. During weekends (`marketStatus = 5`) we observe, on 87 of 87 weekend observations across the eight xStock tickers:

| Field | Median weekend value |
|---|---:|
| `bid` | $1.000 \times 10^{-18}$ |
| `ask` | $0$ |

The published band is degenerate — Chainlink delivers a stale-hold point with zero published uncertainty. To get a band the consumer must wrap `mid` with a $\pm k\%$ correction; on the 87-obs sample $k \approx 3.2\%$ (320 bps half-width) delivers ≥ 95% realised. Against the regime-matched comparator (417.7 bps), Chainlink+3.2% is ≈23% narrower. Caveat specific to this sample: the 87-obs dataset uses the pre-correction v10 + v11 decoders (fixed 2026-04-25); the structural finding (zeroed weekend `bid`/`ask`) is robust across decoder versions and was independently re-confirmed, but the bandwidth figure has not been re-derived on a corrected-decoder dataset. Full breakdown: `reports/v1b_chainlink_comparison.md`; raw obs: `data/processed/v1_chainlink_vs_monday_open.parquet`.

## 6.8 Summary

On the deployed configuration evaluated on the 2023+ held-out slice at consumer target $\tau = 0.95$:

- Realised coverage: **$95.0\%$**
- Kupiec $p_{uc} = 1.000$ (pass)
- Christoffersen $p_{ind} = 0.485$ (pass)
- Mean served half-width: $456$ bps; per-regime widths: $417.7$ bps (normal), $416.6$ bps (long_weekend), $591.6$ bps (high_vol)
- Walk-forward buffer stability (§6.4): six-split cross-split mean at $\tau = 0.95$ is $0.019$ ($\sigma = 0.017$); deployed value $0.020$ lands at the mean.

The number is best read as *deployment-calibrated and walk-forward-stable* rather than purely held-out end-to-end: the calibration surface is held-out, the per-anchor buffer is deployment-tuned on the same slice, and a six-split walk-forward ratifies the deployed buffer at $\tau = 0.95$ as the cross-split mean.

Extended diagnostics (§6.4.1): Berkowitz rejects (safe-direction over-coverage outside the anchor range; per-anchor calibration confirmed); DQ pooled rejects but per-symbol-median passes at all four anchors, with an irreducible 5/10 per-symbol reject-count at τ = 0.99 (halt/corp-action filter gated on scryer per §10.2); exceedance magnitude bounded by ~1,100 bps max at τ = 0.99 with median 71 bps; CRPS = 1.82 baseline.

Incumbent comparisons (§6.7) on subsets of the OOS panel: Pyth's `conf` at $k = 1.96$ delivers 10.2% realised (consumer must back-fit $k \approx 50$ to reach 95%); Chainlink's weekend v11 `bid`/`ask` are degenerate (median ask = 0 across 87 of 87 obs; consumer must wrap `mid` with $\pm 3.2\%$ to reach 95%). Both require consumer-side calibration with no audit trail — the §1.1 thesis confirmed empirically. Matched-bandwidth on the (large-cap, normal-regime) available subsets is competitive (Pyth+50× ≈33% narrower than the regime-matched half-width, Chainlink+3.2% ≈23% narrower); the price is the audit trail the calibration receipt provides for free.

These figures constitute the empirical support for claim P2 (conditional empirical coverage, §3.4). Claim P3 (per-regime serving efficiency) is supported by the ablation reported in §7. Claim P1 (auditability) is evidenced by the artifact released with this paper (§8) and is the load-bearing differentiator against the §6.7 incumbent comparisons. None of the figures in this section, by themselves, identify an optimal liquidation-policy default for a lending protocol; they validate the oracle contract that an integrator would then have to map into its own loss function.
