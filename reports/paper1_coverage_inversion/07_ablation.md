# §7 — Ablation Study (draft)

This section answers Q3 of §3.6: which components of $\texttt{F1\_emp\_regime}$ and the serving layer are load-bearing for the calibration claim, and which are disclosed for auditability but contribute no measurable signal at our sample size? We report two ablation studies — a nine-step *forecaster ladder* on the full panel (§7.1–§7.3) and a seven-cell *serving-layer matrix* on the held-out 2023+ slice (§7.4) — and conclude with a load-bearing-vs-cosmetic taxonomy (§7.5). All deltas carry block-bootstrap 95% confidence intervals; the bootstrap unit is the weekend (`fri_ts`), with all symbol-rows sharing a weekend resampled together so cross-sectional correlation is preserved (1000 resamples). Raw tables: `reports/tables/v1b_ablation_*.csv`. Tables in this section reflect the 2026-05-02 ablation regeneration that added the forward-curve-implied F0_VIX rung; minor row-count differences against §6 (5,996 vs 5,986) reflect a one-week panel extension to 2026-04-24.

## 7.1 Ladder design

Each ladder rung adds exactly one knob to the previous rung; the ablation isolates the marginal contribution of each design choice. Variants are scored on the full 5,996-weekend panel (2014-01-17 → 2026-04-24) at the nominal claimed quantile $q = 0.95$ — the *raw-forecaster* coverage, prior to the calibration-surface inversion of §4.2–§4.3. The A0_VIX rung — the forward-curve-implied Gaussian baseline that a reviewer is likely to ask for in lieu of A0's realised-vol baseline — is scored on the equity subset of the panel (8 of 10 tickers; GLD/TLT use GVZ/MOVE in F1, and constructing an analogous standalone index-implied-vol baseline for them would require per-class unit conversions outside this rung's scope; we treat that as a v2 baseline candidate, see §10).

| Variant | Description | Realised | Mean half-width (bps) | Point MAE (bps) |
|---|---|---:|---:|---:|
| A0 | F0_stale: Friday close + 20-day realised Gaussian band | 0.976 | 401.9 | 94.7 |
| A0_VIX | F0_VIX: Friday close + VIX-implied Gaussian (equity-only, $n=4{,}755$) | 0.900 | 233.5 | 94.7 |
| A1 | + factor-adjusted point + empirical residual quantile | 0.914 | 244.6 | 90.0 |
| A2 | + VIX-scaled residual standardisation | 0.921 | 240.0 | 90.0 |
| A3 | + log-log VIX regression on $\log\|\varepsilon\|$ | 0.923 | 252.8 | 90.0 |
| A4 | + per-symbol vol index (VIX / GVZ / MOVE) | 0.924 | 253.6 | 90.0 |
| A5 | + earnings-next-week regressor (only) | 0.924 | 254.0 | 90.0 |
| A6 | + is_long_weekend regressor (only) | 0.924 | 253.6 | 90.0 |
| A7 | full $\texttt{F1\_emp\_regime}$ (both regressors) | 0.924 | 253.9 | 90.0 |
| B0 | A7's CI width centred on stale point | 0.920 | 253.9 | 94.7 |

Every variant's *raw-forecaster* Kupiec test rejects at the nominal 0.95 claim — this is by design. The 0.95 figure here is the un-buffered, un-inverted quantile-grid output; the served-band coverage of §6.4 is produced by the calibration-surface inversion + per-target buffer that wraps any of these variants. The ablation isolates *which underlying components* drive the sharpness and coverage of the inversion's input, not the inversion's output.

## 7.2 Pooled effect — which knob delivers the sharpness?

| A → B | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) |
|---|---|---|
| **A0 → A0_VIX** (swap σ source: 20d realised → VIX-implied; equity-only $n=4{,}719$) | **−7.86 [−8.75, −6.99]** | **−49.3 [−50.6, −48.1]** |
| **A0_VIX → A1** (factor pt + emp Q on top of VIX-Gaussian; $n=4{,}503$) | **+1.51 [+0.11, +2.90]** | **+17.5 [+13.3, +21.9]** |
| **A0 → A1** (factor pt + emp Q) | **−6.2 [−7.4, −5.0]** | **−39.3 [−41.3, −37.3]** |
| A1 → A2 (VIX-scale residuals) | +0.7 [−0.1, +1.4] | −1.9 [−4.6, +1.0] |
| A2 → A3 (log-log VIX regression) | +0.3 [−0.3, +0.9] | **+3.9 [+1.6, +6.4]** |
| A3 → A4 (per-symbol vol index) | +0.1 [−0.1, +0.4] | **+0.3 [+0.1, +0.5]** |
| A4 → A5 (earnings regressor) | 0.0 [−0.1, +0.1] | +0.1 [−0.2, +0.5] |
| A4 → A6 (long-weekend flag) | 0.0 [−0.3, +0.3] | 0.0 [−0.4, +0.5] |
| A4 → A7 (both regressors) | −0.1 [−0.4, +0.2] | +0.1 [−0.5, +0.7] |
| A7 → B0 (strip factor pt; hold CI fixed) | −0.4 [−1.2, +0.4] | 0.0 (by construction) |

Negative $\Delta$ sharpness means tighter bands. Bold rows are those whose 95% CI excludes zero.

**The factor-switchboard point + empirical residual quantile (A0 → A1) deliver essentially all of the pooled sharpness gain: bands are 39.3% tighter (CI [37.3%, 41.3%]) at the cost of 6.2pp lower raw-forecaster coverage.** Every subsequent rung's pooled sharpness effect is either flat or a small widening. The earnings regressor (A4 → A5) and the long-weekend flag (A4 → A6) have no statistically detectable pooled effect — both confidence intervals span zero on coverage and sharpness.

**The forward-curve-implied baseline (A0 → A0_VIX) delivers a *larger* sharpness gain than F1 — 49.3% tighter against A0's realised-vol Gaussian — but undercovers by 7.9pp at $q = 0.95$.** The mechanism is the structural mismatch between an *index-level* implied-vol input (VIX) and a *single-stock* weekend tail: VIX prices the SPX 30-day forward variance, which is systematically below per-name single-stock variance for the high-beta universe (NVDA, TSLA, MSTR especially). The miscalibration is uniform across regimes — the equity-matched per-regime A0 → A0_VIX deltas are:

| Regime | $n$ | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) |
|---|---:|---|---|
| normal | 3,095 | **−8.14 [−9.29, −7.02]** | **−51.3 [−52.6, −50.0]** |
| long_weekend | 496 | **−6.65 [−9.04, −4.61]** | **−53.4 [−56.7, −50.3]** |
| high_vol | 1,128 | **−7.62 [−9.79, −5.60]** | **−43.5 [−46.2, −40.5]** |

Every regime's coverage CI excludes zero in the negative direction; the gap is not a shock-tertile artefact. The headline is that the most natural reviewer-asked baseline — "just use the market's price for uncertainty" — is *not* a competitive alternative to F1's per-stock empirical residual machinery; it is a sharp-but-miscalibrated band. Adding F1's factor-switchboard point and empirical-quantile band on top of A0_VIX (A0_VIX → A1) recovers +1.5pp of coverage [CI +0.1, +2.9] while *widening* the band by +17.5% [CI +13.3, +21.9]; the gap closes faster in `normal` (+5.3pp coverage / +42.4% wider) than in `high_vol`, where A0_VIX is *over*-conservative on this sample (Δcov −8.5pp). The §7.4 serving-layer evidence shows that the full deployed Oracle (per-stock vol indexing + log-log regression + empirical-quantile inversion + per-target buffer) closes the residual gap entirely; the A0_VIX rung therefore frames F1's per-stock machinery as the load-bearing path from the natural baseline to a calibrated served band, not as a marginal refinement of an already-defensible default.

The B0 variant strips the factor-adjusted point while holding A7's empirical CI width *constant* and centring on the stale point estimate. Pooled $\Delta$ coverage is −0.4pp (CI [−1.2, +0.4]) — not statistically distinguishable from A7. The MAE rises 4.8 bps (94.8 vs 90.0). The factor-switchboard point's contribution is therefore concentrated in *point accuracy*, not in served-band coverage; at $n = 5{,}996$ the coverage contribution of the point shift is below detection.

## 7.3 Per-regime effect — where the regime-specific knobs earn their keep

The pooled view obscures three regime-specific findings.

| A → B | regime | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) |
|---|---|---|---|
| A0 → A1 (factor pt + emp Q) | normal | **−3.0 [−3.9, −2.2]** | **−29.9 [−32.3, −27.5]** |
|  | long_weekend | **−6.0 [−8.6, −3.9]** | **−50.7 [−55.0, −46.1]** |
|  | high_vol | **−14.5 [−18.3, −11.0]** | **−52.1 [−55.3, −49.0]** |
| A1 → A2 (VIX-scale) | normal | **−1.5 [−2.2, −0.8]** | **−15.1 [−17.1, −13.3]** |
|  | long_weekend | −1.9 [−3.6, 0.0] | **−16.6 [−21.6, −11.2]** |
|  | high_vol | **+7.2 [+5.3, +9.6]** | **+41.1 [+34.2, +48.7]** |
| A2 → A3 (log-log) | normal | **−0.7 [−1.2, −0.2]** | **−2.2 [−3.1, −1.2]** |
|  | long_weekend | −0.5 [−2.3, +1.1] | −1.7 [−4.3, +0.8] |
|  | high_vol | **+3.2 [+1.4, +5.1]** | **+15.6 [+9.6, +22.0]** |
| A4 → A6 (long-weekend flag) | normal | −0.1 [−0.4, +0.1] | **−1.8 [−2.1, −1.5]** |
|  | long_weekend | +1.1 [−0.3, +2.4] | **+10.6 [+8.5, +12.9]** |
|  | high_vol | −0.1 [−0.6, +0.4] | +0.1 [−0.6, +0.9] |

Three observations.

1. **The log-log VIX regression (A1 → A3 cumulatively) exists for the `high_vol` regime.** It lifts high-vol coverage by 10.4pp (cumulative across A2 + A3) at the cost of 65% wider bands — the insurance trade a consumer wants in elevated-volatility weekends. In `normal` regime the same transition *costs* coverage by 2.2pp at no sharpness gain, which is why the §4.4 hybrid policy assigns `high_vol` to F0_stale rather than to A7.
2. **The long-weekend flag is a localised effect.** It widens bands by +10.6% **only in its own regime** (`long_weekend`), with statistically-flat effects in `normal` and `high_vol`. The flag costs nothing outside its regime and earns its keep inside it.
3. **The earnings regressor is not detectable in any regime.** Every cell of A4 → A5 has a 95% CI containing zero on both coverage and sharpness. A weekend-ahead binary flag is too coarse to carry signal through the empirical-quantile band-construction at $n = 5{,}996$. We retain it for *auditability* — every PricePoint receipt records whether the flag was active — but not for performance, and we flag it as a v2 candidate for replacement with a finer event-granularity dataset (scheduled datetime + implied-move).

## 7.4 Serving-layer matrix — hybrid policy and calibration buffer

The forecaster ladder of §7.1–§7.3 measures the *raw-forecaster* contribution of each knob. The serving layer adds two additional design choices: the per-regime forecaster selection (§4.4) and the per-target empirical buffer (§4.3). We isolate these by re-serving the same OOS 2023+ panel (1,730 rows × 173 weekends) at the §6 headline target $\tau = 0.95$ across five deployed-comparator cells (C0–C4) plus two F0_VIX challenger cells (B1, B2; equity-only, 1,384 rows × 173 weekends). The calibration surface is fit on the pre-2023 calibration set and held fixed; the deployed buffer at $\tau = 0.95$ is $0.020$ per `BUFFER_BY_TARGET` (§4.3).

| Cell | Forecaster policy | Buffer | Realised | Half-width (bps) | Kupiec $p_{uc}$ | Christoffersen $p_{ind}$ |
|---|---|---:|---:|---:|---:|---:|
| C0 | F1 everywhere | 0.000 | 0.922 | 360.1 | 0.000 | 0.146 |
| C1 | F0 everywhere | 0.000 | 0.921 | 292.9 | 0.000 | 0.470 |
| C2 | hybrid (F1 normal/LW, F0 high_vol) | 0.000 | 0.921 | 351.6 | 0.000 | 0.381 |
| C3 | F1 everywhere | 0.020 | 0.949 | 454.1 | 0.869 | 0.220 |
| C4 | **hybrid (deployed Oracle)** | **0.020** | **0.950** | **443.5** | **0.956** | **0.483** |
| B1 | F0_VIX everywhere (equity-only) | 0.000 | 0.860 | 238.1 | 0.000 | 0.129 |
| B2 | F0_VIX everywhere (equity-only) | 0.020 | 0.876 | 266.4 | 0.000 | 0.059 |

| Comparison | $\Delta$ coverage (pp) | $\Delta$ sharpness (%) | Interpretation |
|---|---|---|---|
| C0 → C2 (hybrid effect, no buffer) | −0.1 [−0.7, +0.5] | −2.4 [−5.6, +1.1] | Hybrid alone doesn't change realised coverage; saves ~2% bandwidth |
| **C0 → C3 (buffer effect, no hybrid)** | **+2.7 [+1.9, +3.6]** | **+26.1 [+24.8, +27.4]** | Buffer closes OOS coverage gap at ~26% wider bands |
| **C2 → C4 (buffer effect, with hybrid)** | **+2.9 [+2.1, +3.9]** | **+26.1 [+24.7, +27.6]** | Buffer effect is approximately independent of hybrid |
| **C0 → C4 (total serving layer)** | **+2.8 [+2.0, +3.8]** | **+23.2 [+19.3, +27.6]** | Full Oracle delivers target coverage; pays ~23% sharpness vs raw F1 |
| **B1 → B2 (F0_VIX buffer effect)** | **+1.7 [+0.9, +2.5]** | **+11.9 [+10.8, +12.9]** | Deployed buffer recovers <2pp of F0_VIX's 9pp coverage gap |
| **B2 → C4 (F0_VIX buffered vs deployed Oracle)** | **+6.7 [+4.3, +9.1]** | **+88.5 [+79.9, +96.3]** | C4 covers 6.7pp more than F0_VIX-buffered, on equity-matched rows; C4 bands ~88% wider |
| **B2 → C3 (F0_VIX buffered vs F1-everywhere buffered)** | **+6.7 [+4.2, +9.2]** | **+93.7 [+87.5, +100.4]** | F1-everywhere covers 6.7pp more than F0_VIX-buffered, ~94% wider |

Negative $\Delta$ sharpness means tighter bands; CIs are 95% block-bootstrap by weekend over 1,000 resamples (`reports/tables/v1b_serving_ablation_bootstrap.csv`).

**Four findings.**

1. **The per-target buffer is the load-bearing serving-layer knob for coverage.** $+2.7$ to $+2.9$pp of the OOS gap is closed by the buffer at $\tau = 0.95$; the hybrid regime policy alone closes essentially none of it. Without the buffer, surface inversion delivers $0.92$ realised against a $0.95$ target and Kupiec rejects at every cell.

2. **The hybrid regime policy is the empirically preferred deployment choice on the evaluated sample, not a binary necessity.** At the deployed buffer, both F1-everywhere (C3) and the hybrid (C4) pass Kupiec and Christoffersen at $\alpha = 0.05$. The hybrid is *weakly dominant* over F1-everywhere on both evaluation axes: bands tighten from $454.1 \to 443.5$ bps ($-2.3\%$), Kupiec margin tightens from $p_{uc} = 0.869$ to $p_{uc} = 0.956$, and Christoffersen margin tightens from $p_{ind} = 0.220$ to $p_{ind} = 0.483$, with no observed trade-off between the two criteria. This is the empirical content of property P3 of §3.4 — *per-regime serving efficiency* defined as empirical dominance on the evaluated sample under (i) mean bandwidth at matched realised coverage and (ii) the Christoffersen independence $p$-value as a violation-clustering diagnostic (not as a decision-theoretic optimisation target). The hybrid is the preferred deployment choice under the paper's evaluation objective.

3. **The buffer effect is approximately additive to the hybrid effect.** The buffer-vs-no-buffer delta is $+2.7$pp without hybrid (C0 → C3) and $+2.9$pp with hybrid (C2 → C4) — bracketing CIs overlap, so we cannot reject buffer-hybrid additivity at $n = 173$ OOS weekends. Practically: deciding hybrid-vs-no-hybrid does not affect the buffer-tuning decision, and vice versa, which simplifies the schedule re-fitting required by any V2.2 rolling rebuild (§10.1).

4. **The forward-curve-implied baseline (F0_VIX) is structurally miscalibrated through the deployed serving stack and cannot be repaired by the deployed buffer.** F0_VIX served with no buffer (B1) realises $0.860$ — a 9pp gap to target. The deployed $0.020$ buffer (B2) lifts realised coverage to $0.876$ but Kupiec still rejects at $p_{uc} \approx 0$; Christoffersen sits at $p_{ind} = 0.059$, marginal. The bootstrap delta against the deployed Oracle (B2 → C4) shows the gap is $+6.7$pp coverage [CI $+4.3, +9.1$] at $+88\%$ width [CI $+80\%, +96\%$], on the equity-matched intersection. Closing F0_VIX's calibration gap to the C4 level on this serving stack would require either (a) a buffer schedule large enough to wipe out the implied-vol baseline's headline width advantage — i.e., to ask for an $\tilde\tau \approx 0.99$ to deliver realised $0.95$, blowing F0_VIX's bands well past F1's — or (b) per-symbol implied vol from OPRA / Cboe options chains, the natural v2 baseline (§10). The empirical content of finding 4 is that the most-natural reviewer-asked baseline — "use the market's price for uncertainty" — is sharper than F1 on its raw bands but cannot meet a calibrated coverage target through the deployed serving layer; F1's per-symbol vol indexing + log-log regression + empirical-quantile inversion is what closes that gap on freely-available data.

The historical record of the v1 development sequence — including an earlier scalar 0.025 buffer that produced cleanly-different numbers, in particular a Christoffersen rejection at the F1-everywhere cell — is preserved in `reports/v1b_ablation.md` and the methodology evolution log at `reports/methodology_history.md`.

## 7.5 Load-bearing-vs-cosmetic taxonomy

Synthesising §7.2–§7.4:

| Component | Role | Evidence |
|---|---|---|
| Factor-switchboard point + empirical residual quantile (A0 → A1) | **Load-bearing for sharpness.** Pooled 39.3% tighter at $n = 5{,}996$. | §7.2 |
| VIX-scaled residual standardisation + log-log VIX regression (A1 → A3) | **Load-bearing for `high_vol` coverage.** Cumulative +10.4pp coverage in `high_vol` at the cost of 65% wider bands — the insurance trade. | §7.3 |
| Per-symbol vol index (VIX / GVZ / MOVE) | **Load-bearing for non-equity RWA generalisation.** The 0.3% pooled bandwidth effect is statistically resolved but small; the substantive justification is the GLD/TLT $\hat\beta$ recovery documented in §5.4. | §5.4, §7.2 |
| Regime model + buffer schedule vs constant-buffer baseline | **Load-bearing for distribution-shift calibration and `high_vol` tail protection; not load-bearing for pooled width-at-coverage at $\tau \leq 0.95$.** Train-fit constant buffer undercovers OOS by 5–14pp at $\tau \leq 0.95$ (Kupiec $p_{uc} < 10^{-6}$). At matched OOS coverage, Oracle is $11$–$12\%$ wider pooled but with Christoffersen-independent violations and $+6.3$pp `high_vol` coverage at $\tau = 0.95$. | §7.6 |
| Long-weekend flag | **Load-bearing inside `long_weekend` regime, neutral outside.** Targeted +10.6% widening only when the regime fires. | §7.3 |
| Earnings-next-week flag | **Disclosed for auditability; no detectable performance contribution at our sample size.** Candidate for v2 replacement with finer event granularity. | §7.3 |
| Empirical calibration buffer (per-target schedule) | **Load-bearing for OOS coverage.** +2.7 to +2.9pp coverage closes the OOS gap at the deployed buffer; without it, surface inversion alone delivers raw realised 0.92 at $\tau = 0.95$ and Kupiec rejects. | §7.4 |
| Hybrid regime-to-forecaster policy | **Empirically preferred deployment choice on the evaluated sample; weakly dominant over F1-everywhere on (sharpness, Christoffersen margin).** At deployed buffer: tighter bands ($-2.3\%$ vs F1-everywhere) and larger Christoffersen $p_{ind}$ margin ($0.483$ vs $0.220$), with no observed trade-off. | §7.4 |
| Forward-curve-implied Gaussian baseline (A0_VIX) | **Disclosed challenger, not deployed.** Sharper raw bands than F1 ($-49.3\%$ on the equity-matched panel) but undercovers by $-7.9$pp. The deployed buffer recovers <2pp; structural Kupiec rejection persists at $p_{uc} \approx 0$. The natural reviewer-asked baseline cannot meet a calibrated coverage target on freely-available data — F1's per-symbol machinery is what closes the gap. | §7.2, §7.4 |

Two components above (the per-symbol vol index and the earnings flag) sit at the boundary of statistical resolution and are disclosed accordingly; the F0_VIX challenger is disclosed as a sharper-but-miscalibrated baseline that the deployed serving stack cannot repair on its own data; the constant-buffer baseline is the deployable simple-stack alternative whose absence of regime/factor structure is what the regime model defends against in §7.6. The remainder are load-bearing, with each contribution attributed to a specific regime or serving-layer property and bracketed by a bootstrap CI that excludes zero. The reviewer-facing claim of §3.4 — that the deployed methodology is fit for purpose, with each component justified by either bootstrap evidence (load-bearing) or transparent disclosure (cosmetic) — is supported component-by-component by this ablation.

## 7.6 Constant-buffer baseline (width-at-coverage)

§7.1–§7.5 strips knobs from inside $\texttt{F1\_emp\_regime}$ and the serving layer; §7.4's A0_VIX cell tests the natural alternative-data baseline. This subsection compares the deployed Oracle against the *external* baseline most likely to be deployed by a protocol team unwilling to absorb the modelling complexity: the Pyth/Chainlink Friday close held forward, with a single global symmetric buffer $b(\tau)$ per claimed quantile. One parameter per $\tau$. No factor switchboard, no empirical residual quantile, no regime model, no per-symbol tuning, no calibration surface. The mechanic is

$$\big[\;p_{\text{Fri}}\,(1 - b(\tau)),\;p_{\text{Fri}}\,(1 + b(\tau))\;\big],\qquad b(\tau)\;\text{calibrated globally on the training panel}.$$

Sample-size argument for taking it seriously. Pooled across 10 symbols and 466 training weekends, the constant-buffer fit has $N = 4{,}266$ observations supporting one scalar — a coverage CI on the holdout of roughly $\pm 2$pp at $\tau = 0.95$ — versus the per-(symbol, regime) fit windows of the deployed Oracle that ride at $N \approx 50$–$250$ for the rolling residual-quantile estimate ($\pm 5$–$15$pp). If the regime model only delivers a small width reduction at matched realised coverage, the modelling complexity isn't earning its keep. We test against three measures: realised coverage at the consumer's $\tau$, mean half-width at matched coverage, and per-regime decomposition. Raw tables: `reports/tables/v1b_constant_buffer_*.csv`. Script: `scripts/run_constant_buffer_baseline.py`.

### 7.6.1 Trained-buffer fit

Each $b(\tau)$ is the smallest multiplicative buffer such that the pooled training panel's empirical coverage of $[p_{\text{Fri}}(1 - b), p_{\text{Fri}}(1 + b)]$ is $\geq \tau$ — equivalently, the empirical $\tau$-quantile of $|p_{\text{Mon}} - p_{\text{Fri}}|/p_{\text{Fri}}$ on the pre-2023 calibration set ($N = 4{,}266$, 466 weekends, 2014-01-17 → 2022-12-30):

| $\tau$ | $b(\tau)$ | training realised | half-width (bps) |
|---:|---:|---:|---:|
| 0.68 | 0.76% | 0.682 | 76.0 |
| 0.85 | 1.40% | 0.850 | 140.0 |
| 0.95 | 2.72% | 0.950 | 272.0 |
| 0.99 | 6.95% | 0.990 | 695.0 |

These buffers reproduce the $\tau$-quantile in-sample by construction.

### 7.6.2 Train-fit baseline on the OOS slice

We carry the trained $b(\tau)$ to the same 2023+ panel that §7.4 evaluates the Oracle on (1,730 rows × 173 weekends), apply the symmetric band, and report pooled diagnostics alongside the deployed Oracle (cell C4 of §7.4, the hybrid regime-policy with the per-target buffer schedule):

| $\tau$ | method | realised | half-width (bps) | $p_{uc}$ | $p_{ind}$ |
|---:|---|---:|---:|---:|---:|
| 0.68 | constant buffer (train-fit) | 0.538 | 76.0 | 0.000 | 0.001 |
| 0.68 | deployed Oracle | 0.680 | 136.1 | 0.984 | 0.645 |
| 0.85 | constant buffer (train-fit) | 0.731 | 140.0 | 0.000 | 0.000 |
| 0.85 | deployed Oracle | 0.856 | 251.4 | 0.477 | 0.182 |
| 0.95 | constant buffer (train-fit) | 0.897 | 272.0 | 0.000 | 0.013 |
| 0.95 | deployed Oracle | 0.950 | 443.5 | 0.956 | 0.483 |
| 0.99 | constant buffer (train-fit) | 0.984 | 695.0 | 0.018 | 0.927 |
| 0.99 | deployed Oracle | 0.972 | 522.8 | 0.000 | 0.897 |

The training-fit constant buffer **catastrophically undercovers** at every $\tau \leq 0.95$: the OOS deficit is $-14.2$pp at $\tau = 0.68$, $-12.0$pp at $\tau = 0.85$, $-5.4$pp at $\tau = 0.95$, all rejecting Kupiec at $p_{uc} < 10^{-6}$. The mechanism is non-stationarity: $b(\tau)$ is calibrated on a 2014–2022 window whose pooled weekend-volatility distribution is calmer than the 2023+ holdout (post-COVID, post-rate-hikes, plus the 2024–2026 single-stock vol regime including MSTR, NVDA, TSLA, HOOD names with distributional shift relative to their 2014–2022 history). At $\tau = 0.99$ the trained buffer overcovers (0.984) and Kupiec rejects from the other side. The Oracle delivers calibrated coverage at $\tau \in \{0.68, 0.85, 0.95\}$ on the same slice and hits the disclosed finite-sample tail ceiling at $\tau = 0.99$ (§9.1).

The fair conclusion of §7.6.2 alone is therefore: **the deployable constant-buffer baseline does not deliver coverage on the holdout. The Oracle does.** This is the *adaptivity-to-distribution-shift* contribution of the regime model and the deployment-tuned buffer schedule. But it is not yet a width-at-coverage claim — the Oracle is also wider, and width comparisons across miscalibrated cells aren't meaningful.

### 7.6.3 Coverage-matched comparison (the headline metric)

To answer the width-at-coverage question — at the same realised coverage on the same OOS slice, how much narrower is the regime model than a constant buffer? — we re-fit $b(\tau)$ post-hoc on the OOS slice itself, choosing the smallest $b$ such that pooled OOS coverage matches the Oracle's realised coverage at that $\tau$. This is an *oracle-fit* baseline that uses the holdout to set $b$; it is not deployable, but it gives the constant buffer the most generous possible width-at-coverage trade-off and removes the train/holdout distribution-shift confound:

| $\tau$ | matched $b$ | matched-CB realised | matched-CB hw (bps) | Oracle realised | Oracle hw (bps) | $\Delta$ width (Oracle − CB) |
|---:|---:|---:|---:|---:|---:|---|
| 0.68 | 1.21% | 0.680 | 120.9 | 0.680 | 136.1 | **+12.4% [+7.2, +18.5]** |
| 0.85 | 2.26% | 0.857 | 226.4 | 0.856 | 251.4 | **+11.1% [+6.1, +16.4]** |
| 0.95 | 3.96% | 0.951 | 395.6 | 0.950 | 443.5 | **+12.2% [+6.4, +18.8]** |
| 0.99 | 5.46% | 0.972 | 545.8 | 0.972 | 522.8 | $-4.3\%$ [−9.8, +1.6] |

Bootstrap CIs are 95% block-bootstrap by weekend over 1,000 resamples (`v1b_constant_buffer_bootstrap.csv`); deltas in bold have CIs that exclude zero.

**The Oracle is 11–12% wider than a coverage-matched constant buffer at every $\tau \leq 0.95$.** The CI excludes zero in all three cases. Phrased against the test the constant-buffer challenge sets — "the regime model has earned its place if it produces a $\tau = 0.95$ band on average 200 bps narrower than the constant-buffer baseline at the same realised coverage" — the regime model is **47.9 bps wider**, not narrower, than the matched constant buffer at $\tau = 0.95$. Only at $\tau = 0.99$ does the regime model match (and marginally beat) the constant buffer in pooled width-at-coverage, with a CI that straddles zero.

The regime model's modelling complexity therefore does **not** buy pooled width-at-coverage on the OOS slice; it buys *coverage at all* on a non-stationary distribution where the deployable constant buffer fails by 5–14pp. This is a smaller and more honest claim than implied by a face-value reading of §6: the headline 27% sharpness premium of the deployed Oracle over its no-buffer ablation cell (C0 → C4 of §7.4) is not a sharpness premium over a deployable simpler baseline — against the simpler baseline, the buffer-equipped Oracle pays a sharpness penalty for buying calibration through the distribution shift.

### 7.6.4 Per-regime decomposition — where the regime model actually earns its keep

The pooled $+12\%$ width premium of §7.6.3 obscures a sharply regime-conditional structure. Decomposing the $\tau = 0.95$ cell:

| regime | $n$ | matched-CB realised | matched-CB hw (bps) | Oracle realised | Oracle hw (bps) | Oracle premium |
|---|---:|---:|---:|---:|---:|---|
| normal | 1,160 | 0.965 | 395.6 | 0.946 | 402.7 | $+1.8\%$ wider, $-1.9$pp coverage |
| long_weekend | 190 | 0.968 | 395.6 | 0.953 | 396.5 | $+0.2\%$ wider, $-1.6$pp coverage |
| high_vol | 380 | 0.900 | 395.6 | 0.963 | 591.6 | **$+49.5\%$ wider, $+6.3$pp coverage** |

In `normal` and `long_weekend`, the regime model is **statistically indistinguishable from a constant buffer** at matched pooled coverage on the OOS slice — the band widths bracket each other within $\pm 2\%$ and the regime model in fact *overshoots in width* by a hair while *undershooting in coverage* by 1.6–1.9pp. In `high_vol`, the regime model widens sharply ($+49.5\%$) and gains 6.3pp of coverage (96.3% vs 90.0%). The constant buffer's pooled coverage is "average right but worst where it matters most": its violations concentrate in high-vol weekends — exactly the weekends where a downstream lending protocol incurs the largest mark-to-market gap if the band fails. The matched-CB Christoffersen test reflects this directly: $p_{ind} = 0.024$ on the pooled $\tau = 0.95$ cell, *rejecting* independence at $\alpha = 0.05$, while the Oracle's $p_{ind} = 0.483$ does not. At $\tau = 0.68$ the gap is starker still — matched-CB $p_{ind} = 7.7 \times 10^{-7}$ vs Oracle 0.645.

The honest claim. The regime model's contribution is **(i) calibration through distribution shift** (training-fit constant buffer fails Kupiec by 5–14pp; Oracle passes) and **(ii) tail-protection in `high_vol` weekends** ($+49.5\%$ width premium, $+6.3$pp coverage at $\tau = 0.95$, with Christoffersen-independent violations at every $\tau \leq 0.95$). The implicit pooled-width-at-coverage claim — that the regime model produces tighter bands than a simple constant buffer at matched realised coverage — does **not survive this baseline** at any $\tau \leq 0.95$. Reviewers of §6's headline should read it conditional on the calibration property (the actual product) rather than as an unconditional sharpness improvement.
