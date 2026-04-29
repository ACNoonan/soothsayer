# V1b — Trial 3: Pooled-tail-only calibration (control turned positive result)

**Hypothesis (per methodology log 2026-04-28 late evening).** Pooling the standardized residuals across all 10 symbols (within regime, within time) for the τ ≥ 0.95 quantile estimate addresses the small-sample-noise mechanism that Trial 1's GPD swap ruled out as the *sole* driver. As designed, this trial was the cheap falsification control: if pooled-tail also showed 6 / 10 reject, the small-sample-noise family would be fully ruled out and the search would shift entirely to conditional-dynamics mechanisms (Trials 5 / 6).

**Result. Hypothesis accepted in part; trial passes the four-threshold scorecard.** Pooled-tail τ = 0.99 per-symbol DQ reject-count drops from 6 / 10 (empirical baseline) to 3 / 10 (pooled). Pooled realised coverage improves to 0.976 (within the ±2pp threshold). Christoffersen $p_\text{ind} = 0.984$ (very strong pass). Bandwidth widens 9 % (449 → 489 bps), well within the 1.5× cap. The trial program scoreboard now reads: Trial 1 (GPD) **fail**, Trial 3 (pooled-tail) **pass**, Trial 2 deferred, Trials 5 / 6 / strategic-alt under reconsideration.

This is the first deployable v1 fix the trial program has produced.

## Decision-threshold scorecard

| threshold | empirical replay | pooled-tail (Trial 3) | pass? |
|---|---|---|---|
| 1. per-symbol DQ reject-count ≤ 3 / 10 | 6 / 10 | 3 / 10 | **pass** |
| 2. pooled realised within ±2pp of 0.99 | 0.966 | 0.976 | **pass** |
| 3. pooled Christoffersen $p_\text{ind} > 0.05$ | 0.500 | 0.984 | **pass** |
| 4. mean half-width ≤ 1.5× empirical (cap 674 bps) | 449 bps | 489 bps | **pass** |

All four thresholds met. Trial 3 is the only trial in the program (so far) that closes the τ = 0.99 per-symbol DQ gap to within the pre-specified target.

## Per-symbol DQ at τ = 0.99 — empirical vs pooled

| symbol | empirical $p_\text{DQ}$ | pooled $p_\text{DQ}$ | shift |
|---|---:|---:|---|
| AAPL  | small  | 0.000 | reject → reject |
| GLD   | large  | 0.998 | pass → pass |
| GOOGL | medium | 0.522 | pass → pass |
| HOOD  | small  | 0.000 | reject → reject |
| MSTR  | large  | 0.920 | pass → pass |
| NVDA  | small  | 0.128 | **reject → pass** |
| QQQ   | small  | 0.920 | **reject → pass** |
| SPY   | small  | 0.000 | reject → reject |
| TLT   | (no test — too few violations under both) | — | — |
| TSLA  | small  | 0.522 | **reject → pass** |

Three symbols flip from reject to pass under the pooled-tail estimator (NVDA, QQQ, TSLA); three remain rejecting (AAPL, HOOD, SPY); three were always passing (GLD, MSTR, GOOGL). TLT drops out of the test because pooled-tail's wider bands left fewer than 10 violations for the DQ regression to be defined.

## Mechanism interpretation — Trial 1 vs Trial 3

Trial 1 (GPD on per-symbol exceedances) and Trial 3 (empirical quantile on pooled-across-symbols residuals) both address sample-size issues, at different levels. The contrast in their results is the diagnostic:

* If the τ = 0.99 per-symbol miscalibration were *purely* small-sample tail-quantile noise, both trials should help. Trial 1 didn't; Trial 3 did. **Therefore the issue isn't pure sample-size noise.**
* What both trials *share* is sample-size mitigation. What Trial 3 has *additionally* is: pooling assumes cross-sectional homogeneity of the standardized residuals (after F1's per-symbol σ standardization removes the scale heterogeneity). Pooling 10 symbols × ~150 observations → ~1,500 standardized residuals → ~7-8 effective samples in the upper 0.5 % tail vs the per-symbol's ~0.8.
* Trial 1's GPD inherited the per-symbol tail-shape instability (xi estimated from ~15 per-symbol exceedances, themselves drawn from a distribution that varies symbol-to-symbol), so GPD's parametric extrapolation was as noisy as the empirical estimator it replaced.

The refined diagnostic: **the per-symbol tail SHAPE is unstable on a 156-weekend window, even after F1's σ standardization.** The 3 / 10 symbols that remain rejecting under pooled-tail (AAPL, HOOD, SPY) have idiosyncratic per-symbol tail shape that does not match the cross-sectional average. The 7 / 10 that pass either had matched-to-cross-section tails (NVDA, QQQ, TSLA, GOOGL) or have wide-enough bounds that DQ has no power (GLD, MSTR, TLT).

This connects to the Mondrian-conformal hypothesis from Trial 2: pooling across symbols at the standardized-residual level is essentially a *Mondrian-style* calibration where the "groups" are (regime, time-window) instead of (symbol, regime, time-window). Trial 3 is therefore a *partial* version of Trial 2 without the conformal-prediction machinery — and it works. This suggests Trial 2's full Mondrian conformal might further close the AAPL / HOOD / SPY gap by adding a per-symbol residual-correction layer on top of the pooled-tail base.

## What this means for the trial program

* **Trial 3 result reorders the program.** Pooled-tail is now the leading v1 candidate. Worth porting from the standalone experiment script to a production code path: add a `pool_tail_at` parameter to the calibration-surface construction in `src/soothsayer/backtest/calibration.py`, defaulting to `None` (current per-symbol behaviour) and accepting a quantile threshold (e.g., 0.95) above which the surface is pooled.
* **Trial 6 (state augmentation, post-shock realized vol) is still worth running.** The 3 / 10 residual rejections (AAPL, HOOD, SPY) suggest there's a per-symbol tail-shape heterogeneity that pooling can't capture. State augmentation may close part of that residual via the σ̂_now path rather than the quantile-estimation path.
* **Trial 2 (Mondrian conformal on top of Trial 3) is back on the table.** Reframe Trial 2 as "Mondrian conformal correction layered on the pooled-tail base predictor" — different from the originally-proposed "Mondrian on top of GPD" because the pooled-tail base now passes the four thresholds. The marginal gain Mondrian would add is closing the AAPL / HOOD / SPY gap.
* **Trial 5 (conditional EVT) and the strategic alternative remain v2 territory.** No change.

## Caveats

* **Standalone-replay vs production discrepancy persists.** This trial uses raw bounds at the claimed-grid point τ (no calibration surface, no per-target buffer). Production gets to 5 / 10 reject-count via surface + buffer + extended grid; my replay's empirical baseline is 6 / 10. Pooled-tail's 3 / 10 may map to ~2 / 10 in production after the same surface + buffer machinery is applied — but this needs to be verified by porting pooled-tail into the production calibration pipeline, not just by reading off the standalone numbers.
* **TLT drops out.** Pooled-tail's wider bands at τ = 0.99 leave TLT with fewer than 10 violations in OOS, below the DQ-test's stability floor. This is technically a "not tested" rather than a "passes" — TLT's actual per-symbol DQ behaviour at the pooled-tail bounds is unknown. (TLT was passing under empirical with a similar mechanism: bounds wide enough that DQ has no power.)
* **The pooled-tail assumption (cross-sectional homogeneity of standardized residuals) is empirical, not theorem.** It works on this 10-symbol universe under the current factor switchboard / regime labeler. A symbol added to the universe with a meaningfully different tail shape (e.g., a meme stock, a small-cap, an emerging-market ETF) might require a regime-stratified pooling rather than a single pooled-cross-section.
* **Bandwidth cost is real.** +9 % vs the per-symbol empirical baseline. For a τ = 0.99 product surface this is acceptable (still well below the 1.5× cap); for a default-deployed τ = 0.85 product surface this trade-off might not be worth it (unclear without rerunning the trial on lower targets — but Trial 3's design only changes τ ≥ 0.95 anchors so the τ = 0.85 bandwidth is unchanged).

## Implications for v1 deployment

Pooled-tail-at-τ ≥ 0.95 is a **deployable v1 fix.** Production-code work required:

1. Add a `pool_tail_above_q: float | None = None` parameter to `compute_calibration_surface()` in `src/soothsayer/backtest/calibration.py`.
2. When set, the surface for q ≥ pool_tail_above_q is constructed by pooling across symbols rather than per-symbol.
3. Update `oracle.py` to consult the pooled-tail path at serve time when target τ would invert to a claimed-q ≥ pool_tail_above_q.
4. Re-run reviewer diagnostics on the surface-served bounds to confirm production-side numbers match the standalone experiment's improvements.
5. Update §6.4.1 with the production-side per-symbol DQ post-pooling.
6. Methodology log entry documenting the methodology change (this is now a methodology change, not just a paper-side disclosure).
7. Rust port: byte-for-byte parity test, update `crates/soothsayer-oracle/src/{config,oracle}.rs`.

Effort: ~3-5 days for the Python + Rust + parity + paper-update cycle. This is a Paper 1 enhancement (improves the headline P2 calibration claim at the τ = 0.99 anchor specifically) rather than v2 work.

## Artefacts

* `scripts/exp_pooled_tail.py` — Trial 3 standalone experiment.
* `reports/tables/v1b_oos_pooled_tail_summary.csv` — per-(label, target) summary.
* `reports/tables/v1b_oos_dq_per_symbol_pooled.csv` — per-(label, target, symbol) DQ p-values.

## Reading

Trial 3 was scoped as a falsification control and turned into the first positive trial. The right next move depends on whether the user accepts pooled-tail as a v1 deployment or wants to see Trial 6's state augmentation result first (the latter could close the remaining 3 / 10 gap further, at modest extra cost). Trial 1's reading is refined, not replaced — small-sample tail-quantile *noise* isn't the issue, but small-sample tail-quantile *shape instability* is, and pooling-across-symbols mitigates it for the symbols whose tails align with the cross-section.
