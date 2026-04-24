# V1b — Ablation study

**Question:** which components of the `F1_emp_regime` forecaster + hybrid serving layer are load-bearing for the coverage-transparency claim, and which are cosmetic?

**Method.** Eight-level ladder in which each variant differs from its predecessor by exactly one knob. Each variant re-computes bounds on the same 5,986-weekend panel (2014-01-17 → 2026-04-17, 10 tickers) and is scored pooled, per-regime, and per-pair. A ninth variant (B0) strips the factor-switchboard point while holding the CI width fixed, isolating the point-estimator's contribution.

Block-bootstrap 95% CIs are reported on all pairwise deltas. Bootstrap unit is the weekend (`fri_ts`): all symbol-rows sharing a weekend are resampled together, preserving cross-sectional correlation. 1000 resamples.

A separate OOS block (§3) simulates the serving-time Oracle at five (hybrid × calibration-buffer) cells on 2023+ weekends using a calibration surface fit on pre-2023 data only (1,720 rows, 172 weekends).

## 1. Ablation ladder — pooled at 95% claim

| Variant | Description | Realized | Sharp (bps) | MAE (bps) |
|---|---|---:|---:|---:|
| A0 | F0 stale-hold + Gaussian CI | 0.976 | 401.8 | 94.8 |
| A1 | + factor-adjusted point + empirical residual quantile | 0.914 | 244.4 | 90.0 |
| A2 | + VIX-scaled residual standardisation | 0.921 | 239.8 | 90.0 |
| A3 | + log-log VIX regression on \|residual\| | 0.923 | 252.6 | 90.0 |
| A4 | + per-symbol vol index (VIX / GVZ / MOVE) | 0.924 | 253.5 | 90.0 |
| A5 | + earnings-next-week regressor (only) | 0.924 | 253.8 | 90.0 |
| A6 | + is_long_weekend regressor (only) | 0.924 | 253.5 | 90.0 |
| A7 | **full `F1_emp_regime`** (both regressors) | 0.923 | 253.7 | 90.0 |
| B0 | A7's CI width centred on stale point | 0.919 | 253.7 | 94.8 |

Every variant's pooled Kupiec test rejects at the nominal 0.95 claim. This is expected — the 0.95 figure here is raw-model coverage, not serving-time output; the calibration surface transforms it into the served quantile (§3).

## 2. Pairwise bootstrap — which knob does the work?

All deltas are $\Delta(\text{row}_b) - \Delta(\text{row}_a)$. Negative $\Delta\text{sharp}\%$ means tighter bands; 95% CI in brackets. Rows in **bold** are where the CI excludes zero.

### 2.1 Pooled

| A → B | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) |
|---|---|---|
| **A0 → A1 (factor pt + emp. Q)** | **-6.2 [-7.4, -5.0]** | **-39.3 [-41.3, -37.3]** |
| A1 → A2 (VIX-scale residuals) | +0.7 [-0.1, +1.4] | -1.9 [-4.6, +1.0] |
| A2 → A3 (log-log VIX regression) | +0.3 [-0.3, +0.9] | **+3.9 [+1.6, +6.4]** |
| **A3 → A4 (per-symbol vol idx)** | +0.1 [-0.1, +0.4] | **+0.3 [+0.1, +0.5]** |
| A4 → A5 (earnings regressor) | 0.0 [-0.1, +0.1] | +0.1 [-0.2, +0.5] |
| A4 → A6 (long-weekend flag) | 0.0 [-0.3, +0.3] | 0.0 [-0.4, +0.5] |
| A4 → A7 (both regressors) | -0.1 [-0.4, +0.2] | +0.1 [-0.5, +0.7] |
| A7 → B0 (strip factor pt) | -0.4 [-1.2, +0.4] | 0.0 (by construction) |

**Pooled reading.** The factor-adjusted point + empirical residual quantile (A0 → A1) delivers essentially all of the sharpness contribution: 39% tighter bands with statistically-significant CI. Every other knob's pooled effect is either flat or a small widening. **The earnings regressor and long-weekend flag have no detectable pooled effect** — their CIs span zero on both coverage and sharpness.

### 2.2 By regime (where the regime-specific knobs earn their keep)

| A → B | regime | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) |
|---|---|---|---|
| A0 → A1 | normal       | **-3.0 [-3.9, -2.2]** | **-29.9 [-32.3, -27.5]** |
|         | long_weekend | **-6.0 [-8.6, -3.9]** | **-50.7 [-55.0, -46.1]** |
|         | high_vol     | **-14.5 [-18.3, -11.0]** | **-52.1 [-55.3, -49.0]** |
| A1 → A2 (VIX-scale) | normal | **-1.5 [-2.2, -0.8]** | **-15.1 [-17.1, -13.3]** |
|         | long_weekend | -1.9 [-3.6, 0.0] | **-16.6 [-21.6, -11.2]** |
|         | high_vol     | **+7.2 [+5.3, +9.6]** | **+41.1 [+34.2, +48.7]** |
| A2 → A3 (log-log) | normal | **-0.7 [-1.2, -0.2]** | **-2.2 [-3.1, -1.2]** |
|         | long_weekend | -0.5 [-2.3, +1.1] | -1.7 [-4.3, +0.8] |
|         | high_vol     | **+3.2 [+1.4, +5.1]** | **+15.6 [+9.6, +22.0]** |
| A4 → A6 (long-weekend flag) | normal | -0.1 [-0.4, +0.1] | **-1.8 [-2.1, -1.5]** |
|         | long_weekend | +1.1 [-0.3, +2.4] | **+10.6 [+8.5, +12.9]** |
|         | high_vol | -0.1 [-0.6, +0.4] | +0.1 [-0.6, +0.9] |

**Regime reading.**

1. **The log-log vol regression (A1 → A3) exists for `high_vol`.** It lifts high-vol coverage by 10.4pp cumulatively (A1 → A3) at the cost of 65% wider bands — which is exactly the insurance policy a consumer wants in elevated-vol regimes. In `normal` regime, the same transition *costs* coverage, which is why the hybrid policy uses F0 in high_vol, not A7.
2. **The long-weekend flag is a localised effect.** It widens bands by +10.6% **only in its own regime** (`long_weekend`), with statistically-flat effects in `normal` and `high_vol`. Cheap to keep.
3. **The earnings regressor is not detectable in any regime.** A4 → A5 has CI-overlaps-zero in every cell. This is a candidate for removal in a future release — the current weekend-ahead earnings flag is too coarse to carry signal through empirical quantiles.
4. **B0 (stale point + regime CI widths):** strips the factor-adjusted point while holding the CI identical. Pooled $\Delta$cov = −0.4pp (CI [−1.2, +0.4]), and MAE rises 4.8 bps. The factor-switchboard point's value is concentrated in point accuracy; its coverage contribution is small and not statistically resolved at n=5,986.

## 3. Serving-layer ablation — OOS 2023+ at target τ = 0.95

Surface fit on pre-2023 bounds (4,266 weekend-rows); Oracle served on 2023+ weekends (1,720 rows, 172 weekends) at consumer target 0.95. Five cells isolate hybrid regime selection and empirical calibration buffer.

| Cell | Forecaster policy | Buffer | Realized | Half-width (bps) | Kupiec $p_{uc}$ | Christoffersen $p_{ind}$ |
|---|---|---|---:|---:|---:|---:|
| C0 | F1 everywhere                   | 0.000 | 0.922 | 360 | 0.000 | 0.647 |
| C1 | F0 everywhere                   | 0.000 | 0.921 | 293 | 0.000 | 0.102 |
| C2 | hybrid (F1 normal/LW, F0 high_vol) | 0.000 | 0.920 | 351 | 0.000 | 0.726 |
| C3 | F1 everywhere                   | 0.025 | 0.959 | 464 | 0.087 | 0.033 |
| C4 | **hybrid (full Oracle)**        | **0.025** | **0.959** | **456** | **0.068** | **0.086** |

**Pairwise OOS bootstrap (all at target 0.95):**

| Comparison | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) | Interpretation |
|---|---|---|---|
| C0 → C2  (hybrid effect, no buffer) | −0.1 [−0.7, +0.4] | −2.4 [−5.8, +0.7] | Hybrid alone doesn't change realized coverage; saves a modest ~2% on bandwidth |
| C0 → C3  (buffer effect, no hybrid) | **+3.7 [+2.7, +4.7]** | **+29.1 [+27.8, +30.4]** | Buffer closes the OOS coverage gap, at cost of ~29% wider bands |
| C2 → C4  (buffer effect, with hybrid) | **+3.9 [+2.8, +4.9]** | **+30.0 [+28.4, +31.5]** | Buffer effect is independent of hybrid |
| **C0 → C4  (total serving-layer)** | **+3.8 [+2.8, +4.9]** | **+26.9 [+22.3, +31.4]** | Full Oracle delivers target coverage; pays ~27% sharpness vs raw F1 |

**Serving-layer reading.**

- **The empirical calibration buffer is the load-bearing serving-layer knob.** +3.7–3.9pp of the coverage gap is closed by the 2.5pp buffer; the hybrid regime policy alone closes essentially none of it.
- **The hybrid policy contributes efficiency, not calibration.** Hybrid + buffer (C4) narrows bands 1.7% vs F1 + buffer (C3: 464 → 456 bps). Not huge, but a free improvement since the surface is built for both forecasters anyway.
- **Only C4 passes both conditional-coverage tests at 0.05.** C3 (F1 + buffer) passes Kupiec but fails Christoffersen independence (violations cluster, $p_\text{ind}=0.033$); C4 is not rejected by either ($p_{uc}=0.068$, $p_{ind}=0.086$). The hybrid policy — swapping F0 into high_vol — reduces violation clustering, even though it barely moves the mean.

## 4. Implications for the paper

**§7 (Ablations) storyline:**

1. Two components are clearly load-bearing: (a) the factor-switchboard point + empirical residual quantile (A0 → A1: 39.3% ± 2% sharper bands pooled), and (b) the empirical calibration buffer on the serving path (+3.8pp OOS coverage, confidence interval excludes zero).
2. Two components earn their keep in one specific regime: log-log vol regression (+10.4pp coverage cumulatively in `high_vol` at 65% wider bands — the insurance trade) and the long-weekend flag (+10.6% wider bands *only in* `long_weekend`).
3. Two components are cosmetic at the n=5,986 sample size: per-symbol vol index vs single VIX (A3 → A4: statistically significant but a 0.3% band-width effect) and the earnings regressor (A4 → A5: no detectable effect). These are disclosed as negligible and retained in the receipt for auditability, not performance.
4. The hybrid regime policy is defended on Christoffersen independence, not on mean coverage. This is a cleaner reviewer-facing claim than "hybrid is sharper" — it is sharper by ~2%, but the real justification is de-clustering of violations in `high_vol`.

**§9 (Limitations) additions:**

- The earnings-regressor finding motivates a Phase 2 replacement with a finer event-granularity dataset (scheduled datetime + implied-move).
- The 2.5pp buffer is a heuristic; a conformalised version (Vovk / Barber et al.) would upgrade this to a finite-sample guarantee under exchangeability, and is flagged as future work.

Raw tables: `reports/tables/v1b_ablation.csv`, `v1b_ablation_by_regime.csv`, `v1b_ablation_bootstrap.csv`, `v1b_ablation_serving.csv`, `v1b_ablation_serving_bootstrap.csv`. Per-row variant output for any downstream analysis: `data/processed/v1b_ablation_rows.parquet`.
