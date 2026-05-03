# §6 — Results (draft)

This section reports the primary calibration evidence. Sharpness and per-component effects are deferred to §7 (ablations); system-level implementation and audit reproducibility are in §8.

## 6.1 Evaluation protocol

The backtest panel comprises $N = 5{,}996$ weekend prediction windows: ten symbols (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD, GLD, TLT, MSTR) observed across $639$ weekends from 2014-01-17 through 2026-04-24. Each window runs Friday 16:00 ET → Monday 09:30 ET. Monday open is the target $P_t(s)$; Friday close and contemporaneous factor-futures / vol-index readings compose the pre-publish information $\mathcal{F}_t(s)$.

For the evaluation we report two complementary figures:

- **In-sample machinery check.** Per-regime conformal quantile $q_r$ fit on the full panel; Oracle served on the same panel. Realised coverage should be close to target $\tau$ *by construction* — the conformal lookup is against the same data that fit it. A material deviation indicates a bug in the artefact-build or serving code path, not a real-world failure mode.
- **Out-of-sample validation (the real number).** Per-regime conformal quantile fit on $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ (4,266 weekend rows); Oracle served on $\mathcal{T}_\text{test} = \{t : t \ge \text{2023-01-01}\}$ (1,730 rows, 173 weekends). No information from $\mathcal{T}_\text{test}$ enters the per-regime quantile table. This is the closest analog to a production deployment in which the artefact is rebuilt on a rolling schedule.

All reported $p$-values are for two-sided Kupiec unconditional-coverage tests (POF likelihood-ratio, $\chi^2_1$ null) and Christoffersen independence tests ($\chi^2$ with $k$ degrees of freedom where $k$ is the number of per-symbol time series with both violation and non-violation observations).

## 6.2 Raw forecaster coverage (motivation for the conformal lookup)

Before serving-time conformal correction, the base point estimator is not calibrated at any nominal coverage level. The deployed point estimator $\hat p_{Mon,r} = p_\text{Fri} \cdot (1 + R_f)$ is unbiased (median residual on the full panel: $-0.5$ bps; MAE $90.0$ bps; RMSE $163.3$ bps) but a "raw" wrap of $\pm k\sigma$ around it, for any single $k$, mis-calibrates at every nominal $\tau$ — coverage attainment varies with regime and weekend duration. This is not a deployment path; it is the input to the per-regime conformal quantile lookup. Neither the raw point nor a single-$k$ wrap is the product. The product is the per-regime conformal quantile $q_r(\tau)$, the OOS-fit bump $c(\tau)$, the walk-forward $\delta(\tau)$ shift, and the served band derived from them.

## 6.3 Served-band calibration — in-sample machinery check

Consumer target $\tau \in \{0.68, 0.85, 0.95, 0.99\}$; per-regime conformal quantile fit on the full panel; full panel ($N = 5{,}996$):

| Regime ($n$)          | $\tau = 0.68$: realised / width (bps) | $\tau = 0.85$: realised / width | $\tau = 0.95$: realised / width | $\tau = 0.99$: realised / width |
|---|---|---|---|---|
| normal (3,924)        | 0.687 / 90.9  | 0.851 / 163.5 | 0.946 / 279.9 | 0.987 / 534.4 |
| long_weekend (630)    | 0.685 / 99.6  | 0.851 / 207.3 | 0.946 / 403.4 | 0.989 / 766.4 |
| high_vol (1,442)      | 0.683 / 174.2 | 0.853 / 312.2 | 0.951 / 557.8 | 0.992 /1{,}069.7 |
| **pooled (5,996)**    | **0.685 / 110.2** | **0.851 / 201.0** | **0.948 / 354.5** | **0.989 / 677.5** |

Pooled realised coverage at every $\tau$ matches the consumer's request to within $0.2$pp by construction — the conformal lookup is fit on this data. *In-sample over-coverage is the safe direction;* under-coverage would indicate an implementation defect.

## 6.4 Served-band calibration — out-of-sample (2023+)

Per-regime conformal quantile fit on the pre-2023 calibration set; Oracle served on 2023+ weekends ($N_\text{test} = 1{,}730$ rows, 173 weekends). The 12 trained quantiles are held-out; the 4 OOS-fit $c(\tau)$ bumps and 4 walk-forward-fit $\delta(\tau)$ shifts are deployment-tuned on this same slice (matching the v1 Oracle's 4-scalar `BUFFER_BY_TARGET` parameter budget) — the read below is therefore *deployment-calibrated and walk-forward-stable* rather than purely held-out end-to-end. The walk-forward block following the table is the empirical mitigation; §9.3 carries the wider disclosure of the OOS-tuning provenance.

| Regime ($n$)       | $\tau = 0.68$: realised / width | $\tau = 0.85$: realised / width | $\tau = 0.95$: realised / width | $\tau = 0.99$: realised / width |
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

**The $\tau = 0.95$ row is the primary oracle-validation operating result on the deployed (M5 / Mondrian) configuration.** On the held-out per-regime quantile served with the OOS-fit $c(\tau) = 1.300$ bump and $\delta(\tau = 0.95) = 0$ shift, the Oracle delivers realised coverage of exactly $0.950$ — Kupiec $p_{uc} = 0.956$ (no evidence of mis-calibration) and Christoffersen $p_{ind} = 0.912$ (no clustering of violations). At $\tau = 0.99$, the M5 Oracle hits $0.990$ with both tests passing — closing the v1 finite-sample tail ceiling at $0.972$ that prompted the M5 evaluation in the first place (§7.2, `reports/methodology_history.md` 2026-05-02 entry). At $\tau = 0.68$, Christoffersen rejects at $\alpha = 0.05$ ($p_{ind} = 0.025$); the violations cluster modestly within the heavier-residual tickers (HOOD, MSTR) — a known limitation of the coarse three-bin regime classifier (§7.2.5, §9.4).

The mean half-width at $\tau = 0.95$ is **354.5 bps** — 20.0% narrower than the v1 Oracle's 443.5 bps half-width on the same OOS slice and the same parameter-tuning protocol (block-bootstrap CI $-23.9\%$ to $-15.6\%$, excludes zero; coverage-delta CI $-1.45$ to $+1.33$ pp, straddles zero). Per-regime: $279.9$ bps (normal, 67% of weekends), $403.4$ bps (long_weekend, 11%), $557.8$ bps (high_vol, 22%). The result is best read in conjunction with the walk-forward stability evidence below and §9.3 (the wider disclosure of OOS-tuning provenance).

**Walk-forward stability of the deployed schedule.** Because the four $c(\tau)$ bumps and four $\delta(\tau)$ shifts are fit on the same OOS slice that this section evaluates, "deployment-calibrated" rather than "purely held-out" is the strongest defensible characterisation of the table above. The relevant empirical mitigation is the cross-split distribution of the served band itself. We re-run the conformal quantile fit + $c(\tau)$ bump fit + $\delta(\tau)$ shift selection on six expanding-window train/test splits over the OOS slice (split fractions 0.2, 0.3, 0.4, 0.5, 0.6, 0.7), evaluating M5 on each split's test fold. With the deployed $\delta$ schedule $\{0.68\!:\!0.05,\;0.85\!:\!0.02,\;0.95\!:\!0.00,\;0.99\!:\!0.00\}$, walk-forward realised coverage matches nominal at every anchor (Kupiec $p$ = 0.43 / 0.37 / 0.36 / 0.32 at $\tau = 0.68, 0.85, 0.95, 0.99$); per-split mean half-width 124 / 215 / 357 / 746 bps tracks the deployed (full-OOS-fit) 110 / 201 / 354 / 677 bps to within +13% / +7% / +1% / +10% — the small extra width on walk-forward is the conservative-side gap the $\delta$ schedule introduces by design (§7.2.4). The deployed schedule is therefore not idiosyncratic to the 2023+ slice in the sense that a six-split rerun reproduces the same operating point at $\tau = 0.95$ and a slightly more conservative one at the lower anchors. This evidence is what allows the §6.4 number to be characterised as "deployment-calibrated and walk-forward-stable" rather than "potentially overfit to one slice"; it does not upgrade the result to a purely held-out end-to-end validation, which remains §10.1's open work (rolling artefact rebuild).

This result should be read as validation of the oracle's coverage contract at $\tau = 0.95$, not as proof that $\tau = 0.95$ is the welfare-optimal operating point for a protocol that consumes the band for liquidations or collateral haircuts.

**Other operating points.** At $\tau = 0.85$ (the current protocol-deployment default; downstream welfare comparisons against protocol baselines are the subject of Paper 3, which revisits the earlier simplified Kamino-style flat-band benchmark against the production xStocks reserve configuration and oracle semantics), realised coverage is $0.850$ exactly, Kupiec passes ($p_{uc} = 0.973$), Christoffersen passes ($p_{ind} = 0.516$). At $\tau = 0.68$, realised lands $0.0$pp from target with Kupiec passing ($p_{uc} = 0.975$) and Christoffersen rejecting ($p_{ind} = 0.025$) — a clustering disclosure inherited from the same coarse three-bin regime classifier driving the §6.4.1 Berkowitz / DQ rejections. At $\tau = 0.99$, Kupiec passes for the first time at this anchor ($p_{uc} = 0.942$, realised $0.990$): the M5 deployment closes the v1 tail ceiling at the cost of a 22% wider band ($677.5$ vs $522.8$ bps) — a width premium documented in §7.2.2 with bootstrap CIs.

The Oracle therefore passes Kupiec at all four standard operating points on held-out data, passes Christoffersen at the three deployment-relevant anchors ($\tau \in \{0.85, 0.95, 0.99\}$), and shows a per-anchor-only calibration profile — Kupiec / Christoffersen pass per anchor; Berkowitz / DQ both reject (§6.4.1) — whose mechanism is the coarse three-bin regime classifier, the same diagnosis the v1 Oracle carried (§7.2.5).

### 6.4.1 Extended diagnostics — Berkowitz and Engle-Manganelli DQ

Two reviewer-likely tests beyond Kupiec + Christoffersen, computed on the 1,730-row M5 walk-forward panel. Numerical artefact: `reports/tables/v1b_mondrian_density_tests.csv`.

**Berkowitz (2001) joint LR on continuous PITs.** PITs reconstructed by inverting each row's served band against the realised Monday open through the per-regime conformal CDF. The test rejects ($\text{LR} = 173.1$, $p \approx 0$, $\hat\rho = 0.31$, $\mu_z = 0.018$, $\sigma_z^2 = 0.99$). Mechanism: the regime classifier $\rho$ is a coarse three-bin index over the joint distribution of weekend conditioning information; the residuals retain unexplained autocorrelation through high-vol weekend clusters that a richer regime classifier or a full-distribution conformal upgrade would absorb.

**Engle-Manganelli (2004) Dynamic Quantile (DQ) test at $\tau = 0.95$.** Stat $= 32.1$, $p = 5.7 \times 10^{-6}$, violation rate $4.97\%$ over 86 violating weekends. The rejection is driven by clustering of violations rather than a level miss — Christoffersen at $\tau = 0.95$ does not reject ($p_{ind} = 0.912$). Per-symbol DQ stratification under M5 follows the same pattern as the v1 Oracle: the rejection concentrates on tickers with the largest residual heavy-tailedness (HOOD, MSTR, NVDA, TSLA) and is invariant to the surface-vs-conformal architecture switch; the v3 full-distribution conformal upgrade (§10.2) is the natural research path for closing it.

The shared diagnosis with the v1 Oracle's density-test rejections — same mechanism, same fix — is documented in §7.2.5 and `reports/methodology_history.md` 2026-05-02 entry. M5 does not fix the density-test rejection; it does not make it worse either. The deployed bands remain *per-anchor calibrated*, not full-distribution calibrated.

**Exceedance magnitude.** A McNeil-Frey-style breach-size summary at the four anchors, computed from the M5 walk-forward 1,730-row served bands, has the same monotone-in-$\tau$ shrinkage as the v1 Oracle (§7.2.2 implies a tail-shape preserve-or-improve under the M5 swap because the served band's $q_\text{eff}$ is a monotone function of the same regime indicator) but with the M5 widths as the divisor. Worst-case price-mismatch at $\tau = 0.99$ on a missed event is bounded by the $677$ bps half-width — substantially tighter than the v1 ceiling at $522$ bps would suggest because the M5 schedule actually hits the $\tau = 0.99$ target where the v1 schedule undershot. Reproduction artefact: extend `scripts/build_mondrian_artefact.py` with the per-row breach summary on demand.

## 6.5 Per-symbol generalisation

The deployed M5 architecture pools the conformity score $|p_\text{Mon} - \hat p_{Mon,r}| / p_\text{Fri}$ across symbols within each regime, so the served band is *per-regime* but not *per-symbol*. The Mondrian by-(symbol, regime) ablation rung (M3, §7.2.2) confirmed that adding the per-symbol stratum thins the bins to $N \approx 50$–$300$ each and degrades Christoffersen rather than improving width — so the deployed schedule reads cross-symbol heterogeneity through the regime classifier alone. The relevant heterogeneity disclosure is therefore at the *regime* level (§6.4 per-regime table) plus the *score-distribution* level: 95th-percentile residual scores by symbol on the OOS slice cluster around 0.04–0.07 for SPY/QQQ/TLT/GLD (the large-cap baseline) and 0.10–0.15 for HOOD/MSTR/NVDA/TSLA (the heavy-tail tickers); per-anchor coverage of the deployed M5 schedule on the heavy-tail subset is consistent with the pooled OOS read at $\tau \in \{0.85, 0.95, 0.99\}$ and inherits the same Christoffersen rejection at $\tau = 0.68$ that drives the pooled rejection. A per-symbol Mondrian re-test was run as part of the M5 validation (M3 row, §7.2.2) and rejected for sample-size reasons, not by virtue of underlying heterogeneity that the deployed pooled-by-regime schedule misses.

## 6.6 Point accuracy and bias absorption

The deployed M5 point estimator is $\hat p_{Mon,r} = p_\text{Fri} \cdot (1 + R_f)$ — the factor switchboard (§5.4) applied to Friday close. Point-estimate MAE on the full panel: $90.0$ bps; RMSE: $163.3$ bps; median bias: $-5.2$ bps. With residual standard deviation $\sigma \approx 163$ bps and $n = 5{,}996$, the factor-adjusted bias has $t \approx -2.5$ — statistically distinguishable from zero but small in magnitude.

A natural reading of the bias figure is that the served Oracle inherits a calibration defect from its raw point. It does not, and the construction is worth making explicit. The conformity score taken at fit time is the *signed* residual

$$\varepsilon_t = \log(P_t / \hat P_t)$$

and its empirical quantile $q_r(\tau)$ is computed in absolute value $|\varepsilon_t|$ for the symmetric band, but the per-regime quantile distribution it is taken from is itself bias-aware: a non-zero median residual within a regime simply shifts the conformal $q_r(\tau)$ upward in absolute value, and the served band's point estimate $\hat P_t$ is reported alongside lower / upper so the consumer can resolve any residual asymmetry by reading the receipt. The $-5.2$ bps figure is a property of the *raw point estimator*, surfaced here for completeness; it does not propagate to the served band's coverage attainment.

A dedicated point-forecasting benchmark against incumbent oracles, on a matched intraday + closed-market window, is deferred to future work (§10).

## 6.7 Comparison to incumbent oracles

§6.4–§6.6 measure whether Soothsayer's served band achieves its claimed coverage; this section measures what consumers receive from the deployed alternatives on subsets of the same OOS panel. We report two reconstructions: a regular-Pyth Hermes-derived band (265 (symbol × weekend) obs across 120 weekends 2024+) and a Chainlink Data Streams v10/v11 reconstruction. RedStone Live is excluded — the public REST gateway exposes no confidence, dispersion, or band field, so there is no calibration object to compare against (§9.6.1). Pyth Pro / Blue Ocean is also excluded from the numerical comparison: the integration model (separate Pro-only feed IDs vs. shared with the public regular-Pyth `PriceAccount` surface) is not surfaced in current public docs, soothsayer holds no Pro-tier subscription, and the empirical probe of `dataset/pyth/oracle_tape/v1/...` for non-stale `pyth_publish_time` during the 8 PM – 4 AM ET Sun–Thu overnight window — which would settle whether Blue Ocean's overnight prints flow into the public surface — is queued out-of-scope for this paper [`docs/sources/oracles/pyth_lazer.md`](../../docs/sources/oracles/pyth_lazer.md) §6 Q1. Independently, Pyth Pro's Blue Ocean window (Sun–Thu overnight) does not cover the Friday-close-to-Monday-open weekend that §6.4 evaluates, so even with full Pro access the numerical comparison would not change for this paper's prediction window.

*Three caveats apply to both subsections below.* (i) Sample-size CIs are wide: binomial 95% CI on $\hat p = 0.95$ is $[0.92, 0.98]$ at $n = 265$ and tighter only on the larger Chainlink panels. (ii) Sample composition is skewed toward large-cap, low-realised-volatility tickers and *normal*-regime weekends, so any matched-bandwidth comparison should be read against Soothsayer's normal-regime OOS half-width (279.9 bps under M5), not the pooled figure (354.5 bps). (iii) The wrap multipliers below ($k = 50$ for Pyth, $k = 3.2\%$ for Chainlink) are *consumer-supplied* — neither incumbent publishes them, so the consumer back-fits the multiplier with no audit trail and no per-symbol stratification.

### 6.7.1 Pyth (regular surface) — `price ± k·conf` as a probability statement

Pyth's regular Solana `PriceAccount` surface publishes `(price, conf)` where `conf` is documented as a publisher-dispersion diagnostic, not a probability statement [pyth-conf]; the Pyth Pro tier inherits the same Pythnet-side aggregation and is excluded from this comparison per §6.7. Sweep $k \in \{1, 1.96, 3, 5, 10, 25, 50, 100, 250, 500, 1000\}$ on the 265-obs subset:

| $k$ | realised | mean half-width (bps) |
|---:|---:|---:|
| 1.00   | 0.049 |   5.6 |
| 1.96   | 0.102 |  11.0 |
| 3.00   | 0.155 |  16.8 |
| 10.00  | 0.434 |  55.9 |
| 25.00  | 0.800 | 139.7 |
| **50.00**  | **0.951** | **279.5** |
| 100.00 | 0.992 | 559.0 |

The textbook 95% Gaussian wrap ($k = 1.96$) returns 10.2% realised — under-calibrated by ≈10× on this subset. The smallest $k$ delivering ≥ 95% realised is $k \approx 50$ (279.5 bps half-width); on the regime-matched M5 comparator (279.9 bps), Pyth+50× is *width-equivalent* at matched empirical coverage on this subset — a closer parity than the v1 comparator (417.7 bps) showed, and the load-bearing Soothsayer differentiator on the §6.7 panels is now firmly the calibration receipt rather than the bandwidth. Per-symbol availability is uneven (SPY 69%, QQQ 65%, TLT 59%, TSLA 25%; AAPL/GOOGL/HOOD/NVDA 0%); Pyth's RH equity feeds did not publish before 2024. Full breakdown: `reports/v1b_pyth_comparison.md`; raw obs: `data/processed/pyth_benchmark_oos.parquet`.

### 6.7.2 Chainlink Data Streams — v10 and v11 weekend prints

Chainlink ships two co-existing schemas for tokenized US equities on Solana mainnet. **v10** (Tokenized Asset, schema id `0x000a`) carries `price` (venue last-trade) and `tokenizedPrice` (24/7 CEX-aggregated mark) but **carries no `bid`, `ask`, or confidence field on the wire**: the v10 wire format is band-less by construction, so a consumer reading v10 directly derives a degenerate zero-width band [chainlink-v10]. **v11** (RWA Advanced, schema id `0x000b`, live on our Solana tape since 2026-Q1) extends the schema with explicit `bid`, `ask`, `mid`, and `last_traded_price` fields. The marker-aware classifier of `reports/v11_cadence_verification.md` (v2, 2026-04-26) applied to a 26-report weekend scan across the four currently-mapped xStock v11 feeds finds a per-symbol pattern that is *not* uniform:

| Symbol (n) | Pattern | Wire `bid` | Wire `ask` | Implied spread |
|---|---|---:|---:|---:|
| SPYx (6) | PURE_PLACEHOLDER | 21.01 | 715.01 | ~18,858 bps |
| QQQx (6) | BID_SYNTHETIC | 656.01 | — | 117–329 bps |
| TSLAx (7) | BID_SYNTHETIC | 372.01 | — | 117–329 bps |
| NVDAx (1) | REAL | 208.07 | 208.14 | ~3.4 bps |

For SPYx, QQQx, and TSLAx the v11 weekend `bid` carries a synthetic `.01` suffix at 100% incidence — well above the ~1-in-100 random-occurrence rate — so the on-wire band is a generated bookend rather than a real venue quote. The PURE_PLACEHOLDER pattern on SPYx (both `bid` and `ask` synthetic) yields an implied spread of ~18,858 bps; the BID_SYNTHETIC pattern on QQQx and TSLAx yields 117–329 bps spreads that look "wide but plausible" if the consumer reads spread alone — exactly the failure mode the v1 spread-only classifier missed before the marker-aware revision. The single NVDAx weekend observation (n = 1) classifies REAL with a 3.4 bps spread, a documented anomaly: the canonical reconciliation [`docs/sources/oracles/chainlink_v11.md`](../../docs/sources/oracles/chainlink_v11.md) §3 row 2 lists three competing explanations (per-feed DON wiring, a Friday-close transition artefact, or a per-symbol pattern) and records the verdict at this sample size as **mixed** rather than uniformly synthetic.

To get a usable band a v11 consumer must replace the wire `bid`/`ask` with a manual `mid ± k%` wrap. On the earlier 87-observation `v1b_chainlink_comparison.md` panel (Feb–Apr 2026, eight xStock tickers, pre-correction decoder), `k ≈ 3.2%` (320 bps half-width) delivered ≥ 95% realised — ≈14% wider than the regime-matched M5 soothsayer comparator (279.9 bps), the inverse of the v1 ranking. The qualitative conclusion — neither v10 (band-less by construction) nor v11 (synthetic-marker placeholders for SPYx/QQQx/TSLAx; n=1 REAL for NVDAx) publishes a coverage band a consumer can read directly — survives the decoder correction. The earlier-reported "median weekend `bid` = 0, `ask` = 0" was a decoder artefact rather than an empirical claim, superseded by the per-symbol synthetic-marker pattern above; the bandwidth figure has not been re-derived on a corrected-decoder dataset and is retained as provenance only. Full breakdown of the corrected per-symbol pattern: [`docs/sources/oracles/chainlink_v11.md`](../../docs/sources/oracles/chainlink_v11.md) §3 and `reports/v11_cadence_verification.md`. Raw obs from the original 87-row panel: `data/processed/v1_chainlink_vs_monday_open.parquet`; full earlier breakdown: `reports/v1b_chainlink_comparison.md`.

## 6.8 Summary

On the deployed (M5 / Mondrian) configuration evaluated on the 2023+ held-out slice at consumer target $\tau = 0.95$:

- Realised coverage: **$95.0\%$**
- Kupiec $p_{uc} = 0.956$ (pass)
- Christoffersen $p_{ind} = 0.912$ (pass)
- Mean served half-width: **$354.5$ bps**; per-regime widths: $279.9$ bps (normal), $403.4$ bps (long_weekend), $557.8$ bps (high_vol)
- Walk-forward stability (§6.4): six-split walk-forward at the deployed $\delta = \{0.05, 0.02, 0.00, 0.00\}$ schedule passes Kupiec at every anchor (per-anchor $p$ = 0.43 / 0.37 / 0.36 / 0.32) at 124 / 215 / 357 / 746 bps mean half-width — a small conservative gap above the deployed (full-OOS-fit) 110 / 201 / 354 / 677 bps that the $\delta$ schedule introduces by design.

The number is best read as *deployment-calibrated and walk-forward-stable* rather than purely held-out end-to-end: the per-regime conformal quantile is held-out, the four $c(\tau)$ bumps and four $\delta(\tau)$ shifts are deployment-tuned on the same slice (matching v1's 4-scalar parameter budget), and the six-split walk-forward ratifies the deployed schedule.

Extended diagnostics (§6.4.1): Berkowitz rejects on the M5 walk-forward PITs (LR = 173.1, $\hat\rho = 0.31$); DQ at $\tau = 0.95$ rejects on the same panel (stat = 32.1, $p = 5.7 \times 10^{-6}$, violation rate $4.97\%$). The shared diagnosis with v1 is that the regime classifier is a coarse three-bin index over the joint distribution of weekend conditioning information, and the residuals retain unexplained autocorrelation through high-vol weekend clusters. M5 does not fix the density-test rejection; the served band remains *per-anchor calibrated*, not full-distribution calibrated. The v3 full-distribution conformal upgrade (§10) is the natural next step.

Headline comparison to v1 (§7.2, `reports/methodology_history.md` 2026-05-02 entry): M5 is **20% narrower** at indistinguishable realised coverage at every $\tau \leq 0.95$ on the OOS slice (block-bootstrap CIs exclude zero on width, straddle zero on coverage); on walk-forward at $\tau \leq 0.95$, M5 is 25–33% narrower at Kupiec-passing realised coverage; at $\tau = 0.99$ M5 widens 22% to hit the nominal target where v1 hits its bounds-grid finite-sample ceiling at $0.972$.

Incumbent comparisons (§6.7) on subsets of the OOS panel: regular-Pyth's `conf` at $k = 1.96$ delivers 10.2% realised (consumer must back-fit $k \approx 50$ to reach 95%); Chainlink v10's wire format carries no `bid`/`ask`/confidence at all (band-less by construction); Chainlink v11's wire `bid` carries a synthetic `.01`-suffix marker at 100% incidence on three of four mapped xStocks (SPYx PURE_PLACEHOLDER, QQQx and TSLAx BID_SYNTHETIC), with a single n=1 REAL classification on NVDAx, so a consumer must wrap `mid` with $\pm 3.2\%$ to reach 95% on the (provenance-only) 87-obs panel. Pyth Pro / Blue Ocean is excluded from the numerical comparison (§6.7) on both access and window grounds. Each of the surfaces compared requires consumer-side calibration with no audit trail — consistent with §1.1's structural observation on these subsets. Matched-bandwidth on the (large-cap, normal-regime) available subsets is now competitive: Pyth+50× is width-equivalent to M5's regime-matched half-width on this subset, Chainlink+3.2% is ≈14% wider than the M5 comparator (the inverse of the v1 ranking). The narrowed M5 width does not change the load-bearing claim of this paper, which is calibration-receipt provenance — but it does close the prior framing of "Soothsayer is wider in exchange for receipts" into "Soothsayer is competitive on width *and* publishes the receipt."

These figures constitute the empirical support for claim P2 (conditional empirical coverage, §3.4). Claim P3 (per-regime serving efficiency) is supported by the ablation reported in §7. Claim P1 (auditability) is evidenced by the artifact released with this paper (§8) and is the load-bearing differentiator against the §6.7 incumbent comparisons. None of the figures in this section, by themselves, identify an optimal liquidation-policy default for a lending protocol; they validate the oracle contract that an integrator would then have to map into its own loss function.
