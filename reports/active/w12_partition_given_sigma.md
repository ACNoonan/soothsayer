# W12 — does the regime partition earn its place *given* σ̂?

**Run 2026-07-24.** Runner: `scripts/run_paper1_w12_partition_given_sigma.py`. Tables: `reports/tables/w12_partition_given_sigma.csv`, `..._by_regime.csv`.

## The gap

§7's comparators form a 2×2 on {σ̂ standardisation, regime partition}, and one cell had never been run:

| | no partition | Mondrian partition |
|---|---|---|
| **no σ̂** | constant buffer (§7.1) ✓ | unweighted Mondrian (§7.2) ✓ |
| **σ̂** | **— never run —** | deployed ✓ |

§7.1 tests stratification against a comparator that also lacks σ̂; §7.2 tests σ̂ against a comparator that has the partition. So *"what does the partition buy given σ̂?"* was unanswered — and W10 made it urgent by showing pooled ACI on the σ̂-standardised score reaching per-symbol 10/10 with no partition and 6.2% narrower bands.

## Design

All four cells run as frozen split-conformal through the sanctioned code path, differing only in `(forecaster, cell_col)`: `m5`/`lwc` selects σ̂, `_all`/`regime_pub` selects the partition. **δ(τ) is suppressed on every arm**, because the deployed M5 path would otherwise carry a non-zero walk-forward correction the LWC path does not, contaminating a comparison whose point is to isolate two other knobs.

Run on both off-hours panels: weekend (1,730 OOS rows) and overnight (6,450 OOS rows). The deployed weekend arm reproduces the published 370.56 bps / 10-of-10, confirming the harness is on the same footing as the paper.

## Result — τ = 0.95

**Weekend**

| arm | half-width | pooled Kupiec p | per-symbol | per-regime |
|---|---|---|---|---|
| no σ̂ · pooled | 336.8 | 0.956 | 3/10 | 1/3 |
| no σ̂ · Mondrian | 354.6 | 0.956 | 2/10 | 2/3 |
| **σ̂ · pooled** ← missing cell | 351.2 | 0.286 | **10/10** | **1/3** |
| σ̂ · Mondrian (deployed) | 370.6 | 0.956 | **10/10** | **3/3** |

**Overnight**

| arm | half-width | pooled Kupiec p | per-symbol | per-regime |
|---|---|---|---|---|
| no σ̂ · pooled | 312.4 | 0.977 | 1/10 | 0/3 |
| no σ̂ · Mondrian | 305.0 | 0.977 | 1/10 | 3/3 |
| **σ̂ · pooled** ← missing cell | 283.8 | 0.509 | **10/10** | **0/3** |
| σ̂ · Mondrian (deployed) | 293.7 | 0.977 | 8/10 | **3/3** |

## What it means

**The missing cell passes per-symbol and fails per-regime.** That is why W10's first reading looked favourable to a partition-free architecture: only pooled and per-symbol coverage had been measured.

**It is the §7.2 compensation mechanism, one level up.** Dropping the partition while keeping σ̂ gives weekend `high_vol` 0.926 and `normal` 0.965 — under-covering where volatility concentrates, over-covering where it does not, averaging to nominal by cancellation. Exactly the failure §7.2 documents across symbols, now across regimes.

**Overnight, the earnings regime is the whole argument.**

| overnight `earnings_night`, τ = 0.95 | half-width | realised coverage |
|---|---|---|
| σ̂ · Mondrian (deployed) | 2,508 bps | **0.983** |
| σ̂ · pooled | 342 bps | **0.333** |

Without the partition the band is sized for an ordinary night and is breached on roughly two earnings nights in three while claiming 0.95. This is the single most consequential number in the §7 battery: it is the scenario that produces bad debt in a lending market, and it is the one an averaged metric hides completely.

**The two components are load-bearing on different axes.** σ̂ delivers per-symbol calibration; the partition delivers per-regime calibration. Neither substitutes for the other. §7's "three load-bearing components" framing survives — but the justification is now measured rather than assumed, and it is *not* aggregate calibration efficiency. It is conditional coverage on identifiable, calendar-known regimes, which is also precisely what makes the §6.8 earnings-widening product claim work.

## Cross-check against W10

The W10 online-conformal grid was re-run with per-regime metrics on both panels. It confirms the same picture from the opposite direction: across all twelve online arms, weekend `high_vol` coverage spans 0.905–0.932 (deployed 0.955) and overnight `earnings_night` spans **0.317–0.383** (deployed 0.983). No online configuration clears 0.383. An online learner adapts a *global* miscoverage level from realised feedback and has no channel to widen for a scheduled event it has not yet observed — the partition is exactly that channel, and `earnings_night` is knowable from the calendar at serve time.

## Caveats

- **δ suppressed on all arms.** The weekend deployed configuration carries δ = 0 anyway, so the weekend deployed row is the deployed configuration. δ is not the source of any difference here — the overnight per-symbol result was identical with and without it.

### ✅ Resolved 2026-07-24 — the overnight "8/10" was a harness bug, not an architecture defect

The first run of this experiment reported overnight deployed per-symbol Kupiec at **8/10**, with GOOGL (0.977) and NVDA (0.975) *over*-covering, and flagged it as an open item against §6.8. It was neither.

`build_overnight_panel.py:106` builds the persisted σ̂ with `exclude_mask_col="earnings_next_week"` — earnings residuals are kept out of the baseline scale pool, because earnings fatness is a *regime* effect carried by the `earnings_night` quantile, not a per-symbol scale effect. `prep_panel_for_forecaster` then **unconditionally recomputes σ̂ into the same column without the mask**, silently substituting a contaminated scale. Every runner in this session called prep, so every overnight number was produced against a σ̂ inflated by **+32.2% on GOOGL and +22.8% on NVDA** (and 0% on SPY, an ETF with no earnings) — precisely the two symbols that failed, and precisely in the over-covering direction.

Fixed by threading `sigma_exclude_mask_col` through `prep_panel_for_forecaster` (default `None`, so weekend behaviour is unchanged) and passing `"earnings_next_week"` on the overnight panel in all three runners. Corrected overnight deployed at τ = 0.95:

| | before (contaminated σ̂) | after |
|---|---|---|
| per-symbol Kupiec | 8/10 | **10/10** |
| half-width | 293.7 bps | **280.1 bps** (−4.7%) |
| per-regime Kupiec | 3/3 | 3/3 |
| pooled realised | 0.9501 | 0.9510 |

The conclusion of this experiment is unchanged and marginally strengthened: σ̂ · pooled still reaches per-symbol 10/10 and still fails per-regime **0/3**, realising 0.367 on `earnings_night` against the deployed 0.983.

**Published §6.8 numbers are not affected.** `build_overnight_artefact.py` consumes the panel's `sigma_hat_sym_pre_fri` column directly (`compute_score_lwc(panel, scale_col=...)`) and never calls `prep_panel_for_forecaster`, so it used the de-contaminated scale throughout. The bug was confined to this session's ad-hoc runners.

**Watch item.** Any *other* analysis that has used `prep_panel_for_forecaster` on the overnight panel carries the same contamination. The function now takes the mask explicitly, but the default is still `None`, so an overnight caller that forgets it fails silently and in the safe-looking direction (over-coverage).
- Both experiments use the endpoint (open-price) truth, not path-aware truth; §6.5's endpoint-vs-intra-period distinction applies unchanged.
