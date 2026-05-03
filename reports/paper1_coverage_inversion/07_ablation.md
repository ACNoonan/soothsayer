# §7 — Ablation Study

This section answers Q3 of §3.6: which components are load-bearing for the calibration claim? §7.1 stress-tests the deployable simpler baseline that strips regime structure entirely (a global constant buffer); §7.2 compares M5 against a v1 surface-plus-buffer Oracle on the same OOS slice and parameter budget. The precursor v1 forecaster ladder is documented in `reports/methodology_history.md`.

All deltas carry block-bootstrap 95% CIs by weekend (1000 resamples). Raw tables: `reports/tables/v1b_constant_buffer_*.csv`, `reports/tables/v1b_mondrian_*.csv`, `reports/tables/v1b_oracle_walkforward*.csv`.

## 7.1 Constant-buffer baseline (width-at-coverage)

This is the deployable *external* baseline most likely to be used by a protocol team unwilling to absorb modelling complexity: the Pyth/Chainlink Friday close held forward, with a single global symmetric buffer $b(\tau)$ per claimed quantile. One parameter per $\tau$. No factor switchboard, no empirical residual quantile, no regime model.

$$\big[\;p_{\text{Fri}}\,(1 - b(\tau)),\;p_{\text{Fri}}\,(1 + b(\tau))\;\big],\qquad b(\tau)\;\text{calibrated globally on the training panel}.$$

### 7.1.1 Trained-buffer fit on OOS

Each $b(\tau)$ is the empirical $\tau$-quantile of $|p_{\text{Mon}} - p_{\text{Fri}}|/p_{\text{Fri}}$ on the calibration set. Carrying the trained $b(\tau)$ to the 2023+ panel:

| $\tau$ | method | realised | half-width (bps) | $p_{uc}$ | $p_{ind}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | constant buffer (train-fit) | 0.538 | 76.0 | 0.000 | 0.001 |
| 0.68 | deployed Oracle | 0.680 | 136.1 | 0.984 | 0.645 |
| 0.85 | constant buffer (train-fit) | 0.731 | 140.0 | 0.000 | 0.000 |
| 0.85 | deployed Oracle | 0.856 | 251.4 | 0.477 | 0.182 |
| 0.95 | constant buffer (train-fit) | 0.897 | 272.0 | 0.000 | 0.013 |
| 0.95 | deployed Oracle | 0.950 | 443.5 | 0.956 | 0.483 |
| 0.99 | constant buffer (train-fit) | 0.984 | 695.0 | 0.018 | 0.927 |
| 0.99 | deployed Oracle | 0.990 | 677.5 | 0.942 | 0.344 |

The training-fit constant buffer **catastrophically undercovers** at every $\tau \leq 0.95$ (deficits $-14.2 / -12.0 / -5.4$pp, all rejecting Kupiec at $p_{uc} < 10^{-6}$) — non-stationarity: $b(\tau)$ is calibrated on a 2014–2022 window calmer than the 2023+ holdout. **The deployable constant-buffer baseline does not deliver coverage on the holdout; the Oracle does.** This is the *adaptivity-to-distribution-shift* contribution of the regime model.

### 7.1.2 Coverage-matched comparison

To answer the width-at-coverage question, we re-fit $b(\tau)$ post-hoc on the OOS slice (oracle-fit, non-deployable, but gives the constant buffer the most generous trade-off):

| $\tau$ | matched $b$ | matched-CB hw (bps) | Oracle hw (bps) | $\Delta$ width (Oracle − CB) |
|---:|---:|---:|---:|---|
| 0.68 | 1.21% | 120.9 | 136.1 | **+12.4% [+7.2, +18.5]** |
| 0.85 | 2.26% | 226.4 | 251.4 | **+11.1% [+6.1, +16.4]** |
| 0.95 | 3.96% | 395.6 | 443.5 | **+12.2% [+6.4, +18.8]** |
| 0.99 | 5.46% | 545.8 | 677.5 | $+24.1\%$ [$+18.0$, $+30.7$] |

**The Oracle is 11–12% wider than a coverage-matched constant buffer at every $\tau \leq 0.95$.** The regime model does **not** buy pooled width-at-coverage on OOS; it buys *coverage at all* on a non-stationary distribution where the deployable constant buffer fails by 5–14pp.

### 7.1.3 Per-regime decomposition

The pooled premium hides a regime-conditional structure. At $\tau = 0.95$:

| regime | $n$ | matched-CB realised | matched-CB hw | Oracle realised | Oracle hw |
|---|---:|---:|---:|---:|---:|
| normal | 1,160 | 0.965 | 395.6 | 0.946 | 402.7 |
| long_weekend | 190 | 0.968 | 395.6 | 0.953 | 396.5 |
| high_vol | 380 | 0.900 | 395.6 | 0.963 | 591.6 |

In `normal` and `long_weekend` the regime model is statistically indistinguishable from a constant buffer. In `high_vol` it widens sharply (+49.5%) and gains 6.3pp of coverage. The constant buffer's pooled coverage is "average right but worst where it matters most": violations concentrate in high-vol weekends — exactly where a downstream lending protocol incurs the largest mark-to-market gap. Matched-CB Christoffersen at pooled $\tau = 0.95$: $p_{ind} = 0.024$ (rejects); Oracle: $p_{ind} = 0.483$ (does not). At $\tau = 0.68$ the gap is starker: $7.7 \times 10^{-7}$ vs 0.645. The regime model's contribution is **(i) calibration through distribution shift** and **(ii) tail-protection in `high_vol` weekends**; the implicit pooled-width-at-coverage claim does not survive this baseline at $\tau \leq 0.95$.

## 7.2 Mondrian conformal-by-regime (the deployed v2 architecture)

§7.1 ruled out a deployable baseline stripping regime structure. The natural follow-up: does v1's hybrid forecaster machinery (factor switchboard, log-log VIX, per-symbol vol index, earnings flag, long-weekend flag) plus the per-target buffer schedule earn its place against a Mondrian split-conformal quantile fit per regime?

### 7.2.1 Mondrian ladder

Each variant fits a per-regime conformal quantile $q_r(\tau)$ and serves $[\hat p_{\text{Mon},r}(1 \pm q_r(\tau))]$:

- **M1.** Stale point + per-regime quantile.
- **M2.** Factor-adjusted point + per-regime quantile.
- **M3.** Factor-adjusted point + per-(symbol, regime) quantile.
- **M4.** M2 with quantile re-fit *post-hoc on OOS itself* (oracle-fit, non-deployable).
- **M5.** M2 + per-target multiplicative bump $c(\tau)$ tuned on OOS — twelve trained scalars + four OOS, matching v1's parameter budget. **The deployed variant.**

### 7.2.2 OOS pooled results

| $\tau$ | method | realised | hw (bps) | $p_{uc}$ | $p_{ind}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | v1 hybrid Oracle | 0.680 | 136.1 | 0.984 | 0.645 |
| 0.68 | M2 fa + regime-CP | 0.547 | 73.5 | 0.000 | 0.776 |
| 0.68 | M3 (symbol,regime)-CP | 0.572 | 92.2 | 0.000 | $2.1{\times}10^{-4}$ |
| 0.68 | M4 oracle-fit | 0.682 | 109.5 | 0.893 | 0.105 |
| 0.68 | M5 deployed | 0.680 | 110.2 | 0.975 | 0.025 |
| 0.85 | v1 hybrid Oracle | 0.856 | 251.4 | 0.477 | 0.182 |
| 0.85 | M5 deployed | 0.850 | 201.0 | 0.973 | 0.516 |
| 0.95 | v1 hybrid Oracle | 0.950 | 443.5 | 0.956 | 0.483 |
| 0.95 | M2 | 0.910 | 272.7 | $8.2{\times}10^{-12}$ | 0.396 |
| 0.95 | M5 deployed | 0.950 | 354.5 | 0.956 | 0.912 |
| 0.99 | v1 hybrid Oracle | 0.972 | 522.8 | 0.000 | 0.897 |
| 0.99 | M5 deployed | 0.990 | 677.5 | 0.942 | 0.344 |

M1 / M2 reproduce §7.1's finding from the other side: a deployable per-regime conformal lookup with no further tuning undercovers by 6–14pp at $\tau \leq 0.95$. M3 (per-symbol Mondrian) does worse on Christoffersen because per-(symbol, regime) bins thin to $N \approx 50$–$300$. M4 (oracle-fit) shows the headroom; M5 closes essentially all of it with the same 4-scalar budget v1 uses.

Block-bootstrap CIs on M5 − v1 deltas:

| $\tau$ | $\Delta$ coverage (pp) | $\Delta$ width (%) |
|---:|---:|---:|
| 0.68 | $+0.02$ [$-2.60$, $+2.72$] | $-19.1\%$ [$-22.6$, $-15.7$] |
| 0.85 | $-0.56$ [$-2.66$, $+1.45$] | $-20.0\%$ [$-24.0$, $-15.9$] |
| 0.95 | $-0.05$ [$-1.45$, $+1.33$] | $-20.0\%$ [$-23.9$, $-15.6$] |
| 0.99 | $+1.82$ [$+0.92$, $+2.89$] | $+29.6\%$ [$+23.2$, $+36.2$] |

**At $\tau \leq 0.95$, M5 is 19–20% narrower than v1 at indistinguishable realised coverage; at $\tau = 0.99$, M5 widens to hit nominal where v1 ceilings.**

### 7.2.3 Walk-forward δ-shift schedule

The pooled OOS comparison is contaminated for both methods (both 4-scalar schedules are tuned on the same slice). On a 6-split expanding-window walk-forward, bare M5 ($\delta = 0$) is *anti-conservative* at $\tau \leq 0.85$ while v1's `BUFFER_BY_TARGET` is *conservative* — an OOS-tuning-protocol asymmetry, not a conformal-vs-empirical-quantile distinction. The fix pushes M5 to the same conservative side via a $\delta$-shift, serving $c(\tau + \delta(\tau)) \cdot q_r(\tau + \delta(\tau))$. A sweep over $\delta \in \{0.00, \dots, 0.07\}$ selects $\delta = \{0.68\!:\!0.05,\;0.85\!:\!0.02,\;0.95\!:\!0.00,\;0.99\!:\!0.00\}$ as the smallest schedule aligning walk-forward coverage with nominal at every anchor.

| $\tau$ | M5 (with δ) realised | M5 hw (bps) | v1 realised | v1 hw (bps) | M5 advantage |
|---:|---:|---:|---:|---:|---|
| 0.68 | 0.672 ($p=0.43$) | 124 | 0.735 | 186 | $-33\%$ |
| 0.85 | 0.832 ($p=0.37$) | 215 | 0.878 | 287 | $-25\%$ |
| 0.95 | 0.943 ($p=0.36$) | 357 | 0.971 | 526 | $-32\%$ |
| 0.99 | 0.991 ($p=0.32$) | 746 | 0.979 | 609 | $+22\%$, **target hit** |

**M5 with the δ-shift schedule passes Kupiec at every anchor on walk-forward at 25–33% narrower mean half-width than v1 through $\tau \leq 0.95$.** At $\tau = 0.99$, M5 trades width for target attainment.

### 7.2.4 Where the v1 premium goes

§7.1.3 attributed the constant-buffer premium to `high_vol`; §7.2 shifts the question. M5-vs-v1 $\tau = 0.95$ decomposition:

| regime | $n$ | M5 hw | v1 hw | v1 premium |
|---|---:|---:|---:|---|
| normal | 1,160 | 279.9 | 402.7 | $+43.9\%$ wider, $+0.7$pp coverage |
| long_weekend | 190 | 403.4 | 396.5 | $-1.7\%$ wider, $-3.1$pp coverage |
| high_vol | 380 | 557.8 | 591.6 | $+6.1\%$ wider, $-0.5$pp coverage |

v1 earns its OOS calibration **primarily by overwidening normal-regime weekends** (the 67% of the panel) at $+43.9\%$ wider for $+0.7$pp coverage — the v1 forecaster ladder is cosmetic on top of `regime_pub`. Berkowitz and DQ on M5's walk-forward PITs reject ($\text{LR} = 173.1$; DQ at $\tau = 0.95$, $p = 5.7 \times 10^{-6}$) — same diagnosis as §6.3.1, full-distribution conformal remains the v3 target.

§7.1 ruled out a deployable baseline that strips regime structure. §7.2 isolates the deployable baseline that keeps `regime_pub` and replaces v1's forecaster machinery: 19–20% narrower than v1 at indistinguishable coverage on OOS at $\tau \leq 0.95$; 25–33% narrower on walk-forward; hits nominal $\tau = 0.99$ where v1 ceilings; shares v1's per-anchor-only profile on density tests. The wire format (`PriceUpdate` Borsh) is preserved across v1 → v2: the swap changes only the published *values*, not the decoder or the §3.4 property contract.
