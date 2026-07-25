# W13 — triple-witching as a regime cell (weekend panel)

**Run 2026-07-24.** Runner `scripts/run_paper1_w13_triple_witching_regime.py`; tables `reports/tables/w13_triple_witching{,_by_regime}.csv`.

## Why this candidate

W12 established *why* the Mondrian partition is load-bearing: it is the only channel that can widen the band for an event identifiable from the calendar **before** it happens. No online learner can do that (W10: `earnings_night` 0.317–0.383 against the deployed 0.983). That makes the regime taxonomy the architecture's moat, so the move is to widen it.

Triple witching — quarterly simultaneous expiry of index futures, index options and single-stock options, the **third Friday of Mar/Jun/Sep/Dec** — is the strongest remaining candidate that needs **no new upstream data**. It is purely calendrical (the third Friday is always day-of-month 15–21), so it is computable in-repo without violating CLAUDE.md rules #1/#2. FOMC and CPI dates *are* new upstream data and must land in scryer first. The S&P quarterly rebalance is effective at the open following the same session, so this cell captures both events.

Weekend-panel only: a triple-witching Friday's next open is Monday, a weekend gap.

## The defect it found

**Under the deployed taxonomy, triple-witching weekends are a live, unmeasured coverage hole.**

At τ = 0.95, deployed, the 130 OOS triple-witching rows realise **0.8692 coverage against a claimed 0.95 — Kupiec p = 0.0004.** A 13% breach rate where 5% is promised. Nobody had seen it because triple witching was not a cell, so no one had sliced on it: 327 of those rows sit in `normal`, 123 in `high_vol`, 10 in `long_weekend`, and each of those cells passes on aggregate while hiding this sub-population.

This is the §7.2 compensation mechanism a third time — pooled and per-symbol both look fine, and the failure lives on an axis nobody measured.

## Result of carving out the cell

τ = 0.95, both arms scored on the *same* partition so the sub-population is visible in both:

| cell | n | deployed coverage | +TW coverage | deployed width | +TW width |
|---|---|---|---|---|---|
| **triple_witching** | 130 | **0.8692** (p=0.0004 ❌) | **0.9077** (p=0.0465 ❌) | 367.4 | **449.7** |
| normal | 1,070 | 0.9542 (p=0.522) | 0.9495 (p=0.944) | 299.1 | **273.6** |
| high_vol | 350 | 0.9657 | 0.9657 | 606.7 | 585.2 |
| long_weekend | 180 | 0.9556 | 0.9556 | 338.3 | 327.6 |

Pooled effects:

| τ | pooled half-width | per-regime Kupiec pass |
|---|---|---|
| 0.68 | 130.8 → 130.7 | 2/4 → **3/4** |
| 0.85 | 213.6 → 212.3 | 2/4 → **3/4** |
| 0.95 | **370.6 → 355.5 (−4.1%)** | 3/4 → 3/4 |
| 0.99 | 635.0 → 638.8 | 3/4 → **4/4** |

Pooled realised coverage is unchanged (0.9503) and per-symbol stays 10/10 at every anchor.

## Read

**Net positive, and it should be adopted — but it is an improvement, not a fix.**

Three things happen at once. The triple-witching cell widens from 367 to 450 bps and its coverage moves 0.869 → 0.908. The `normal` cell gets **6% tighter** (299 → 274 bps) and better calibrated (p 0.52 → 0.94), because the triple-witching fat tail had been inflating it. And the pooled band is **4.1% tighter** at τ = 0.95 while conditional coverage improves at three of four anchors.

So carving out the cell is close to free: it buys back width on the 62% of weekends that are `normal`, and spends it where it is actually needed.

**The honest limit: the new cell still fails Kupiec at τ = 0.95 (p = 0.0465, coverage 0.9077).** Its own quantile is not enough. Two plausible causes, and this run cannot separate them:

1. **Cell thinness** — 330 training rows across 33 Fridays. §4.3 rejected a per-(symbol, regime) rung on exactly these grounds, and this cell is at the same scale.
2. **Shape, not width** — triple-witching residuals may need a different distributional shape rather than a wider scalar, the same diagnosis as the `earnings_night` body-vs-tail miscalibration (which over-covers at τ = 0.68/0.85 while passing at 0.95).

## Recommendation

Adopt the cell — it strictly improves the taxonomy and pays for itself in `normal`-cell width — and record the residual failure honestly rather than claiming the hole is closed. Then treat "thin calendar cells need shape, not just width" as one shared problem across `triple_witching` and `earnings_night`, because the evidence now points the same way in both.

Do **not** promote this into the deployed artefact until:

- it is re-run with δ active and the c(τ) bump in the deployed configuration (this run suppressed δ for a clean comparison);
- the interaction with `high_vol` priority is checked — 123 of 460 triple-witching rows were previously `high_vol`, and this run gave triple witching top priority by analogy with `earnings_night`. The reverse priority is untested;
- forward-tape rows accumulate; 4 triple-witching weekends per year means OOS power grows slowly.

## Next in the same direction

FOMC and CPI are the highest-value remaining calendar regimes and both are blocked on scryer (rules #1/#2). Worth opening a scryer wishlist item: FOMC statement dates back to 2014 and BLS CPI release dates are both small, stable, public calendars.
