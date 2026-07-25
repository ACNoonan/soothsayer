# W14 — thin calendar cells: noise, drift, or shape?

**Run 2026-07-24.** Runner `scripts/run_paper1_w14_thin_calendar_cells.py`; tables `reports/tables/w14_thin_cells_{diagnosis,remedies}.csv`.

Opened because two calendar-known cells — `earnings_night` (overnight) and `triple_witching` (weekend, W13) — both failed Kupiec, and it looked like one shared "thin cell needs shape" problem. **It is two different problems**, and treating them as one would have applied the wrong fix to half of them.

## Step 1 — how much of the failure is just small samples?

Binomial 95% CI on realised coverage at each cell's actual OOS size, against what was observed:

| cell | τ | observed | 95% CI at this n | verdict |
|---|---|---|---|---|
| `triple_witching` (n=130) | 0.68 | 0.715 | [0.600, 0.762] | inside — noise |
| | 0.85 | 0.808 | [0.785, 0.908] | inside — noise |
| | **0.95** | **0.900** | **[0.915, 0.985]** | **below — real** |
| | 0.99 | 1.000 | [0.969, 1.000] | inside |
| `earnings_night` (n=60) | 0.68 | 0.733 | [0.567, 0.800] | inside — noise |
| | **0.85** | **0.967** | **[0.750, 0.933]** | **above — real over-coverage** |
| | 0.95 | 0.983 | [0.883, 1.000] | inside |
| | 0.99 | 1.000 | [0.950, 1.000] | inside |

**Most of what looked like failure is small-sample noise.** Only one anchor per cell survives — and note that `earnings_night` at τ = 0.68 (previously 0.800, Kupiec p = 0.038) is now 0.733 and *inside* the CI: the σ̂ de-contamination fix already resolved it. What remains is one real miss in each cell, in **opposite directions**.

## Step 2 — the diagnostic that separates them

Ratio of the cell's quantile to the pooled quantile, as fitted on train versus what the OOS slice actually needed:

| | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---|---|---|---|
| `triple_witching` train | 1.421 | 1.379 | **1.229** | 1.352 |
| `triple_witching` OOS wanted | 1.341 | 1.587 | **1.563** | 1.212 |
| `earnings_night` train | 7.404 | **7.712** | 6.909 | 7.037 |
| `earnings_night` OOS wanted | 7.260 | **5.704** | 4.552 | 5.467 |

Two different signatures:

- **`triple_witching` — estimation noise in a thin cell.** The train ratios wander non-monotonically (1.42, 1.38, 1.23, 1.35) with no stable profile; 329 training rows cannot pin four separate quantiles. The τ=0.95 estimate happened to land low, and under-coverage followed.
- **`earnings_night` — a genuine train→OOS drift in the multiplier.** The train profile is *stable and consistent* (7.4, 7.7, 6.9, 7.0 — a well-estimated ~7× cell) but OOS wants systematically **less** (7.3, 5.7, 4.6, 5.5). The cell is well estimated; the world moved. Plausibly a calmer post-2023 earnings-reaction regime relative to ordinary nights than 2014–2022 (which carries 2018 and 2020).

## Step 3 — the remedy, and where it works

Tested: `q_r(τ) = w_r·q_cell(τ) + (1−w_r)·m_r·q_pooled(τ)`, with `w_r = n_r/(n_r+k)` and `m_r = median(score_cell)/median(score_pooled)`. Shape from the pool, scale from the cell. `k=0` is the deployed architecture; `k=∞` is pure scale-family.

Shrinking toward the *unscaled* pooled quantile — what Rafe & Das evaluate (arXiv:2605.05562) and find only marginally helpful — would be wrong here: it would collapse a 7×-fatter earnings cell toward normal-night width. The `m_r` rescaling is what makes shrinkage safe across heterogeneous cells.

**Weekend — it works.**

| k | per-regime pass @ τ=0.95 | `triple_witching` coverage | pooled half-width |
|---|---|---|---|
| 0 (deployed) | 3/4 | 0.900 ❌ | 340.2 bps |
| 50 | 3/4 | 0.908 | 341.6 |
| **200** | **4/4 ✅** | **0.923** | **344.7 (+1.3%)** |
| 500 | 4/4 ✅ | 0.923 | 348.1 (+2.3%) |
| ∞ | 4/4 @0.95 but **3/4 @0.99** | 0.938 | 363.3 (+6.8%) |

**k ≈ 200 closes the triple-witching hole for a 1.3% width cost, with no regression at any other anchor.** Pure scale-family (`k=∞`) over-corrects and breaks τ=0.99.

**Overnight — it does not.** Per-regime pass is flat at 2/2/3/3 for every finite k and *degrades* at `k=∞` (2/2/2/1). `earnings_night` coverage at τ=0.85 moves only 0.967 → 0.933, still above the CI. That is the expected result: shrinkage repairs *estimation noise*, and the earnings cell's problem is *drift*. No amount of borrowing shape from the pool fixes a multiplier that was correctly estimated on a period that no longer applies.

## Conclusions

1. **The two cells do not share a problem.** `triple_witching` is thin-cell estimation noise; `earnings_night` is regime-multiplier drift. The unified "thin calendar cell needs shape" hypothesis that motivated this run is **wrong**, and acting on it would have shipped a fix that helps one cell and does nothing for the other.
2. **Adopt m_r-rescaled shrinkage at k ≈ 200 for the weekend taxonomy.** It closes the W13 hole at ~1.3% width and degrades nothing. It is also self-limiting: as any cell accumulates rows, `w_r → 1` and it reverts to the deployed behaviour, so it is a strict generalisation rather than a replacement.
3. **`earnings_night` needs a recency-weighted cell quantile, not shrinkage.** The natural analogue is the σ̂ EWMA promotion (2026-05-04): weight the cell's own history by recency so a stale multiplier decays out. Untested — this is the next experiment, not a recommendation.
4. **Report the residual honestly.** After the σ̂ fix, three of the four original "failures" across both cells are inside the binomial CI at their sample sizes. The paper should say these cells are *under-powered*, not that they are calibrated — with n=60, coverage anywhere from 0.88 to 1.00 is indistinguishable at τ=0.95.

## Caveats

- δ suppressed and no c(τ) bump on any arm, for clean isolation. Before promotion, re-run in the deployed configuration.
- `k` was swept, not tuned on held-out data. k≈200 is a plateau, not an optimum, and the plateau (200–500) is what makes it defensible; a single best-k selected on this OOS slice would be an oracle choice.
- Overnight per-regime pass is 2/3 at τ=0.68/0.85 for *every* arm, including deployed — a separate failure in a non-thin cell that this run did not chase.
