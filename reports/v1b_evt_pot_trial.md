# V1b — Trial 1: EVT/POT (Generalized Pareto Distribution) for τ ≥ 0.95 anchors

**Hypothesis (per methodology log 2026-04-28 late evening).** Replacing the empirical-quantile estimator at τ ≥ 0.95 with a parametric GPD fit on threshold exceedances reduces the per-symbol DQ reject-count at τ = 0.99 to ≤ 3 / 10, addressing the small-sample noise mechanism that we hypothesised was driving the 5 / 10 per-symbol DQ rejections in §6.4.1.

**Result. Hypothesis rejected.** GPD does not improve per-symbol DQ at τ = 0.99 on this data. The diagnostic implication is that the τ = 0.99 per-symbol miscalibration is *not* a small-sample tail-estimator issue — it is a different mechanism (conditional dynamics / volatility clustering) that GPD's parametric tail extrapolation does not address.

## Experimental setup

Standalone re-fit of the F1 log-log forecaster on the full 5,996-row panel; for each (symbol, fri\_ts) in OOS (1,730 rows, 173 weekends), we capture the rolling-window standardized residuals $z_\text{hist}$ and compute τ ∈ {0.68, 0.85, 0.95, 0.99} bounds two ways:

* **empirical:** $z_\text{hi} = \text{quantile}(z_\text{hist}, 1 - (1-\tau)/2)$ (current production estimator at the *claimed* grid).
* **gpd:** Pickands-Balkema-de Haan extrapolation. Threshold $u$ at the 90th percentile of $z_\text{hist}$ (McNeil-Frey default; window=156 → ~15-16 exceedances per fit, comfortably above the 8-exceedance stability floor). Fit GPD to $z - u$ for $z > u$ via `scipy.stats.genpareto.fit(excess, floc=0)`, returning shape $\hat\xi$ and scale $\hat\sigma$. Tail quantile by inversion of the GPD CDF: for conditional tail probability $p_\text{cond} = (1-\tau)/2 \div (1-0.90)$ above $u$, $z_q = u + (\hat\sigma / \hat\xi) \bigl[ p_\text{cond}^{-\hat\xi} - 1 \bigr]$ (with $\xi \to 0$ giving the exponential limit). Lower-tail symmetric. GPD path for τ ∈ {0.95, 0.99} only; τ ≤ 0.85 unchanged from empirical.

Bounds at each (symbol, fri\_ts, target) constructed as $L = P^\text{F1} \cdot \exp(z_\text{lo} \cdot \sigma_\text{now})$ and analogously for $U$, mirroring `forecasters.py:empirical_quantiles_f1_loglog` lines 270-271. Reviewer diagnostics rerun on the OOS slice.

**Caveat on baseline comparability.** The standalone replay computes *raw* bounds at the claimed-grid point τ (no calibration-surface inversion, no per-target buffer, no extended-grid resolution). Production (`§6.4.1`) computes *served* bounds with τ → buffer → claimed-grid lookup → surface inversion, and consequently shows realised 0.977 / per-symbol reject 5 / 10 at τ = 0.99 vs my replay's 0.966 / 6 / 10. The Trial 1 internal comparison (empirical-replay vs GPD-replay) is the apples-to-apples experimental contrast; the absolute baseline differs from production by the surface + buffer machinery, which is orthogonal to the GPD swap being tested here.

## Decision-threshold scorecard

| threshold | empirical replay | GPD (Trial 1) | pass? |
|---|---|---|---|
| 1. per-symbol DQ reject-count ≤ 3 / 10 | 6 / 10 | 6 / 10 | **fail** |
| 2. pooled realised within ±2pp of 0.99 | 0.966 | 0.969 | fail (both) |
| 3. pooled Christoffersen $p_\text{ind} > 0.05$ | 0.500 | 0.344 | pass |
| 4. mean half-width ≤ 1.5× empirical (cap 674 bps) | 449 bps | 484 bps | pass |

GPD passes thresholds 3 and 4 but fails on the headline diagnostic (threshold 1) and is no better than empirical on threshold 2.

## Per-symbol DQ at τ = 0.99 (the diagnostic of record)

| symbol | empirical $p_\text{DQ}$ | GPD $p_\text{DQ}$ | rejects (α=0.05) |
|---|---:|---:|---|
| AAPL  | small | 0.000 | both |
| GLD   | large | 0.999 | neither |
| GOOGL | medium | 0.128 | neither |
| HOOD  | small | 0.000 | both |
| MSTR  | large | 0.999 | neither |
| NVDA  | small | 0.000 | both |
| QQQ   | small | 0.000 | both |
| SPY   | small | 0.000 | both |
| TLT   | large | 0.999 | neither |
| TSLA  | small | 0.000 | both |

The pattern is invariant under the GPD swap: the same six mainstream-equity tickers (AAPL, HOOD, NVDA, QQQ, SPY, TSLA) reject under both estimators, and the same four (GLD, MSTR, GOOGL, TLT) pass. The non-rejectors are split between (a) wide-bound asset classes where the band catches almost everything and DQ has no power (GLD, TLT) and (b) symbols whose factor-residual structure is well-described by VIX-conditional log-log regression (GOOGL, MSTR — though MSTR's "pass" is driven by the same band-catches-everything mechanism, not signal). Per-symbol full table: `reports/tables/v1b_oos_dq_per_symbol_evt.csv`.

## Diagnostic implication — what the rejection tells us

The fact that GPD changes the per-symbol DQ pattern by zero is informative. GPD addresses one specific failure mode: small-sample noise in tail-quantile estimation. The empirical estimator at the 0.995-quantile of a 156-row window has ~0.8 expected sample points at the cell; the GPD extrapolation pools the upper-15-or-so exceedances into a parametric fit, which is dramatically more sample-efficient. *If* the rejection pattern were caused by noisy tail-quantile estimation, GPD would visibly help. It does not — therefore, that is not the mechanism.

The remaining candidate mechanisms, in rough order of likelihood:

1. **Conditional volatility clustering (GARCH effects) on the residuals.** The $\sigma_\text{now}$ estimator is a level model: it regresses $\log|\varepsilon|$ on $\log v_t$ and a few level shifts. It does not model conditional persistence in $\sigma$ — i.e., no GARCH(1,1) recursion, no HAR-RV, no realized-volatility-from-intraday. If post-shock weekends carry elevated $\sigma$ that the VIX-level regressor under-states, the standardized residuals retain time-varying scale that DQ catches as autocorrelation in the hit indicator.

2. **Regime-transition state.** The current $\rho$ labeler has three states (`normal`, `long_weekend`, `high_vol`); a single VIX-quartile flag is the only conditioning on volatility regime. A "post-shock recovery" or "vol-spike-decay" sub-state of `normal` would absorb part of the conditional structure. The §10.2 sub-regime granularity follow-up addresses this.

3. **Symbol-specific tail behaviour the regime labeler doesn't encode.** TSLA's idiosyncratic volatility, AAPL's earnings-cycle clustering, NVDA's AI-beta-rotation transitions, HOOD's IPO-era sample composition. The factor switchboard (`ES=F` for all seven equities) does not carry name-specific tail shape.

4. **Halt / corp-action structural exceptions.** Already on the §10.2 follow-up plan, gated on scryer wishlist 15a + 15b. Orthogonal to this trial.

Note that mechanism (1) is the canonical McNeil-Frey diagnosis: their *conditional* EVT framework (CEVT) fits a GARCH model first, computes standardized residuals, *then* applies GPD to the residuals. The unconditional GPD tested here (Trial 1) skips the GARCH step. If the problem is GARCH-style conditional persistence, CEVT is the next swing — but it is significantly heavier than Trial 1 (per-symbol GARCH fits, refit on every rolling window) and belongs in the v2 calibration-surface revision rather than a Paper 1 disclosure addendum.

## Bandwidth

GPD widened the τ = 0.99 mean half-width from 449 bps (empirical replay) to 484 bps (+8%). For comparison, the production-served τ = 0.99 half-width (with surface + buffer + extended grid) is 580.8 bps — both Trial 1 numbers are tighter than production because they don't include the buffer. The 1.5× cap (threshold 4) of 674 bps is comfortable for either; bandwidth is not the binding constraint here.

GPD's $\hat\xi$ values across the 1,730 OOS fits are bounded but show meaningful per-symbol variation. The non-rejectors (GLD, TLT) have tighter $\hat\xi$ distributions (closer to exponential, $\xi \approx 0$); the rejectors (AAPL, NVDA, QQQ, SPY, TSLA) have $\hat\xi$ more often in the heavy-tail range (positive, sometimes > 0.3). This is a per-symbol signature of the residual-distribution shape that the regime labeler does not currently capture.

## Implications for the trial program

- **Trial 2 (Mondrian conformal layered on Trial 1):** *Recommend deferring.* Mondrian is a different aggregation, not a different mechanism. With the per-symbol mechanism unaddressed by GPD, Mondrian's group-conditional coverage guarantee is unlikely to close the per-symbol DQ gap. The exception is if the trial reframes from "fix τ = 0.99 reject-count" to "absorb the per-symbol heterogeneity into the calibration surface itself" — but that's a v2 design change, not a Paper 1 patch.

- **Trial 3 (pooled-tail-only):** *Recommend running anyway as a control.* If pooled-tail also shows 6 / 10 reject, that confirms the small-sample-noise mechanism is fully ruled out; if pooled-tail moves the count, that contradicts Trial 1 and the joint reading is more nuanced. Cheap (1-2 days) and produces a clean falsification.

- **New candidate Trial 5 — conditional EVT (GARCH + GPD on standardized residuals).** McNeil-Frey 2000 canonical two-stage. Targets the volatility-clustering mechanism this trial's negative result points at. Effort: ~1-2 weeks. Belongs in v2 calibration-surface revision, not Paper 1.

- **New candidate Trial 6 — state augmentation: post-shock realized-vol indicator.** Add `realized_vol_4w` (or VIX-percentile rank, or GARCH-implied $\sigma$ surrogate) as an extra regressor in F1's $\sigma$ model. Targets mechanism (2) above. Effort: ~3-5 days; lighter than full GARCH and may capture much of the same signal. Run as Trial 6 if Trial 3 also fails to move the count.

- **Strategic alternative remains live.** Drop τ = 0.99 from the deployed product surface; deploy τ ∈ [0.50, 0.95] only. Trial 1's negative result *strengthens* this option — the per-symbol miscalibration at the 1% tail is a structural property of the empirical-quantile / regime-conditioned methodology rather than an estimator-tuning issue, and the cleanest disclosure is to scope the deployed range to where the methodology demonstrably holds.

## Artefacts

- `scripts/exp_evt_pot_tail.py` — Trial 1 standalone experiment.
- `data/processed/exp_evt_pot_bounds.parquet` — per-(symbol, fri\_ts, target) raw bounds, both estimators side-by-side.
- `reports/tables/v1b_oos_evt_pot_summary.csv` — per-(label, target) summary diagnostics.
- `reports/tables/v1b_oos_dq_per_symbol_evt.csv` — per-(label, target, symbol) DQ p-values.

## Reading

A clean "GPD doesn't work" result is more valuable for project direction than a "GPD works but it's noisy" result. We now know that the τ = 0.99 per-symbol miscalibration is not a tail-estimator-precision problem, which falsifies the cheapest fix and refines the candidate-mechanism list. The actionable next moves are Trial 6 (state augmentation, lightweight) and Trial 5 / strategic-alternative (heavier; v2 territory). Paper 1's §6.4.1 disclosure framing — pooled rejection partly aggregation-inflated, irreducible 5 / 10 at τ = 0.99 — is unchanged by this result; if anything the negative trial *strengthens* the disclosure by ruling out the obvious counter-claim ("did you try a parametric tail estimator?") with explicit citation.
