# §6 — Results

This section reports the primary calibration evidence. Sharpness and per-component effects are deferred to §7; system-level implementation and audit reproducibility are in §8.

## 6.1 Evaluation protocol

The backtest panel comprises $N = 5{,}996$ weekend prediction windows: ten symbols across $639$ weekends from 2014-01-17 through 2026-04-24. Monday open is the target; Friday close and contemporaneous factor / vol-index readings compose $\mathcal{F}_t(s)$. We report two figures: (i) an *in-sample machinery check* (quantile fit and served on the full panel; realised coverage should match $\tau$ by construction), and (ii) the *out-of-sample validation* (quantile fit on $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$, Oracle served on the 1,730-row $\mathcal{T}_\text{test}$ slice). All $p$-values are two-sided Kupiec POF and Christoffersen independence tests.

The base point estimator is unbiased (median residual $-0.5$ bps; MAE $90.0$; RMSE $163.3$) but a raw $\pm k\sigma$ wrap mis-calibrates at every $\tau$. The product is the per-regime conformal quantile, the OOS-fit bump, the walk-forward $\delta$ shift, and the served band derived from them.

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

Quantile fit on pre-2023 weekends; Oracle served on the 2023+ slice (1{,}730 rows, 173 weekends). The 12 trained quantiles are held-out; the 4+4 schedules are deployment-tuned on this same slice (matching v1's `BUFFER_BY_TARGET` budget). The read is therefore *deployment-calibrated and walk-forward-stable*; §9.3 carries the wider disclosure.

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

**The $\tau = 0.95$ row is the primary oracle-validation operating result.** On the held-out quantile served with $c(0.95) = 1.300$, realised coverage is exactly $0.950$ — Kupiec $p_{uc} = 0.956$, Christoffersen $p_{ind} = 0.912$. At $\tau = 0.99$, M5 hits $0.990$ with both tests passing — closing the v1 tail ceiling at $0.972$. At $\tau = 0.68$ Christoffersen rejects ($p_{ind} = 0.025$); violations cluster modestly in heavier-residual tickers (HOOD, MSTR) — the coarse three-bin regime classifier limitation. Mean half-width at $\tau = 0.95$ is **354.5 bps** — 20% narrower than v1's 443.5 on the same slice (CI $-23.9\%$ to $-15.6\%$); per-regime $279.9$ / $403.4$ / $557.8$ bps.

**Walk-forward stability.** Because the 4+4 schedules are fit on the same OOS slice, "deployment-calibrated" is the strongest defensible characterisation. Re-running the conformal + bump + shift selection on six expanding-window splits (fractions 0.2–0.7) and evaluating M5 on each test fold: with the deployed $\delta$ schedule, walk-forward coverage matches nominal at every anchor (Kupiec $p$ = 0.43 / 0.37 / 0.36 / 0.32); per-split mean half-width 124 / 215 / 357 / 746 bps tracks the full-OOS-fit 110 / 201 / 354 / 677 to within +13% / +7% / +1% / +10%. The schedule is not idiosyncratic to the 2023+ slice but does not upgrade the result to purely held-out end-to-end (§10.1's open work).

This validates the oracle's coverage contract at $\tau = 0.95$. It does *not* prove $\tau = 0.95$ is the welfare-optimal operating point; that is Paper 3.

### 6.3.1 Extended diagnostics — Berkowitz and DQ

**Berkowitz (2001) joint LR on continuous PITs.** PITs reconstructed by inverting each served band against the realised Monday open through the per-regime conformal CDF. Rejects ($\text{LR} = 173.1$, $\hat\rho = 0.31$). The regime classifier is a coarse three-bin index; residuals retain unexplained autocorrelation through high-vol weekend clusters.

**Engle-Manganelli (2004) DQ at $\tau = 0.95$.** Stat $= 32.1$, $p = 5.7 \times 10^{-6}$, violation rate $4.97\%$ over 86 weekends. Rejection driven by clustering rather than a level miss — Christoffersen at $\tau = 0.95$ does not reject. Per-symbol DQ concentrates on heavy-tail tickers (HOOD, MSTR, NVDA, TSLA). Bands remain *per-anchor calibrated*, not full-distribution calibrated.

## 6.4 Per-symbol generalisation and point accuracy

M5 pools the conformity score across symbols within each regime; the M3 ablation confirmed adding a per-symbol stratum thins bins to $N \approx 50$–$300$ and degrades Christoffersen. 95th-percentile residual scores cluster around 0.04–0.07 for SPY/QQQ/TLT/GLD and 0.10–0.15 for HOOD/MSTR/NVDA/TSLA; coverage on the heavy-tail subset is consistent with pooled OOS at $\tau \in \{0.85, 0.95, 0.99\}$ and inherits the same $\tau = 0.68$ rejection.

Point-estimate MAE $90.0$ bps; RMSE $163.3$; median bias $-5.2$ bps. The bias does not propagate to coverage: the conformity score uses absolute residuals, so a non-zero median within a regime simply shifts $q_r(\tau)$ upward, and the receipt exposes lower/upper alongside $\hat P_t$.

## 6.5 Comparison to incumbent oracle surfaces

This section measures what consumers receive from deployed alternatives. We report two reconstructions: a regular-Pyth Hermes-derived band (265 obs, 2024+) and a Chainlink Data Streams v10/v11 reconstruction. RedStone Live is excluded (no confidence/dispersion field on the public REST gateway, §9.6.1); Pyth Pro / Blue Ocean is excluded on access and window grounds.

Three caveats: (i) sample-size CIs are wide; (ii) composition is skewed toward large-cap normal-regime weekends, so any matched-bandwidth comparison should be read against Soothsayer's normal-regime half-width (279.9 bps); (iii) the wrap multipliers below are *consumer-supplied* — neither incumbent publishes them.

### 6.5.1 Pyth (regular surface) — consumer wrap `price ± k·conf`

Pyth's `(price, conf)` is documented as a publisher-dispersion diagnostic, not a probability statement [pyth-conf]; Pyth Pro inherits the same aggregation. Sweep on 265-obs subset:

| $k$ | realised | mean half-width (bps) |
|---:|---:|---:|
| 1.96 (textbook 95% Gaussian) | 0.102 | 11.0 |
| 25.00 | 0.800 | 139.7 |
| **50.00** | **0.951** | **279.5** |
| 100.00 | 0.992 | 559.0 |

The naive textbook 95% wrap returns 10.2% realised — under-calibrated by ≈10× as a consumer-supplied band, not as a Pyth claim. The smallest $k$ delivering ≥ 95% is $k \approx 50$ (279.5 bps); on the regime-matched M5 comparator (279.9 bps) Pyth+50× is *width-equivalent* at matched coverage. Per-symbol availability is uneven (SPY 69%, QQQ 65%, TLT 59%, TSLA 25%; AAPL/GOOGL/HOOD/NVDA 0% — Pyth's RH equity feeds did not publish before 2024). The Soothsayer differentiator on this panel is the calibration receipt, not the bandwidth.

### 6.5.2 Chainlink Data Streams — v10 and v11

**v10** (Tokenized Asset, `0x000a`) carries `price` and `tokenizedPrice` but **no `bid`, `ask`, or confidence on the wire** — band-less by construction [chainlink-v10]. **v11** (RWA Advanced, `0x000b`) adds `bid`, `ask`, `mid`. The marker-aware classifier on a 26-report weekend scan:

| Symbol (n) | Pattern | Wire `bid` | Wire `ask` | Implied spread |
|---|---|---:|---:|---:|
| SPYx (6) | PURE_PLACEHOLDER | 21.01 | 715.01 | ~18,858 bps |
| QQQx (6) | BID_SYNTHETIC | 656.01 | — | 117–329 bps |
| TSLAx (7) | BID_SYNTHETIC | 372.01 | — | 117–329 bps |
| NVDAx (1) | REAL | 208.07 | 208.14 | ~3.4 bps |

For SPYx, QQQx, TSLAx the v11 weekend `bid` carries a synthetic `.01` suffix at 100% incidence — the on-wire band is a generated bookend, not a real venue quote. To get a usable band a v11 consumer must replace wire `bid`/`ask` with a manual `mid ± k%` wrap; on an earlier 87-observation panel `k ≈ 3.2%` (320 bps) delivered ≥ 95% — ≈14% wider than the regime-matched M5 comparator. Neither v10 nor v11 publishes a coverage band a consumer can read directly.

## 6.6 Summary

On the deployed M5 configuration at $\tau = 0.95$ on the 2023+ held-out slice: realised coverage **95.0%**; Kupiec $p_{uc} = 0.956$, Christoffersen $p_{ind} = 0.912$ (both pass); mean half-width **354.5 bps**; six-split walk-forward passes Kupiec at every anchor; **20% narrower than v1** at indistinguishable coverage through $\tau \le 0.95$. vs incumbent surfaces: a naive regular-Pyth $k = 1.96$ consumer wrap realises 10.2%; Chainlink v10 is band-less; v11's wire `bid` carries a synthetic `.01`-suffix on three of four mapped xStocks; none publishes a calibration receipt. Berkowitz and DQ both reject — bands are *per-anchor calibrated*, not full-distribution calibrated. Supports P2 (§3.4); P1 evidenced by §8; P3 by §7.
