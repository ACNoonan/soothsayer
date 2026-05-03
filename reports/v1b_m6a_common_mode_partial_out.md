# V3 lead 1 — M6a common-mode residual partial-out

**Question.** W2 (`reports/v1b_density_rejection_localization.md`) found that both v1 and M5 have cross-sectional within-weekend lag-1 ρ ≈ 0.354 in their PITs — the factor-adjusted point captures index beta but doesn't absorb every common-mode component. Can a residual-level partial-out remove the cross-sectional ρ and tighten the band at matched coverage?

## Construction

  point_fa_i = fri_close_i · (1 + factor_ret_i)         (M5 baseline)
  r_i        = (mon_open_i − point_fa_i) / fri_close_i  (signed residual)
  r̄_w^(−i)   = mean over symbols j ≠ i within weekend w

  Train OLS:  r_i = β · r̄_w^(−i) + ε_i  (no intercept)
  M6a score:  s_i = | r_i − β̂ · r̄_w^(−i) |

Per-regime conformal quantile of s on train at τ ∈ DENSE_GRID; OOS-fit bump c(τ) so OOS realised ≥ τ; report coverage and width.

## Train-side fit

β̂ = 0.8114, R²(train) = 0.2781 (n=4,266), R²(OOS, with train β̂) = 0.2552.

Cross-sectional within-weekend ρ on the signed residual:
- M5 (r_i):                      0.4147
- M6a (r_i − β̂·r̄_w^(−i)):       0.0705

## OOS coverage and width

| method                      |   target |   n_oos |   realised |   bump_c |   half_width_bps_mean |
|:----------------------------|---------:|--------:|-----------:|---------:|----------------------:|
| M5_baseline                 |    0.680 |    1730 |      0.680 |    1.498 |               110.170 |
| M6a_common_mode_partial_out |    0.680 |    1730 |      0.681 |    1.547 |               102.836 |
| M5_baseline                 |    0.850 |    1730 |      0.850 |    1.455 |               200.977 |
| M6a_common_mode_partial_out |    0.850 |    1730 |      0.850 |    1.452 |               178.311 |
| M5_baseline                 |    0.950 |    1730 |      0.950 |    1.300 |               354.513 |
| M6a_common_mode_partial_out |    0.950 |    1730 |      0.950 |    1.318 |               308.962 |
| M5_baseline                 |    0.990 |    1730 |      0.990 |    1.076 |               677.454 |
| M6a_common_mode_partial_out |    0.990 |    1730 |      0.990 |    1.150 |               595.603 |

## M6a vs M5 width delta at matched coverage

|   target |   m5_realised |   m6a_realised |   m5_half_width_bps |   m6a_half_width_bps |   width_change_pct |
|---------:|--------------:|---------------:|--------------------:|---------------------:|-------------------:|
|    0.680 |         0.680 |          0.681 |             110.170 |              102.836 |             -0.067 |
|    0.850 |         0.850 |          0.850 |             200.977 |              178.311 |             -0.113 |
|    0.950 |         0.950 |          0.950 |             354.513 |              308.962 |             -0.128 |
|    0.990 |         0.990 |          0.990 |             677.454 |              595.603 |             -0.121 |

## Reading

With β̂ = 0.811 and train R² = 0.28, the leave-one-out weekend mean residual explains roughly 28% of the per-row residual variance — i.e., the common-mode is real and substantial. The cross-sectional within-weekend ρ on the residual drops from 0.415 (raw) to 0.070 (after partial-out), confirming the partial-out removes the structure W2 localized.

**Width consequence.** The M6a band at τ=0.95 is **-12.8%** vs M5 (355 bps → 309 bps). At τ=0.85: **-11.3%**. At τ=0.68: **-6.7%**.

## Deployability caveat

**This is an upper-bound diagnostic.** r̄_w^(−i) uses Monday data and is not Friday-observable. To deploy M6a we need a forward predictor of r̄_w. Candidate signals: futures-implied weekend move (CME ES/NQ Sunday Globex post-Friday-close to Monday-pre-cash-open), VIX/skew change, macro release calendar, sector rotation indicators. The expected deployable width gain is between zero and the upper bound reported here, scaled by how much variance the forward predictor recovers vs the perfect r̄_w. A predictor with R²(forward) = 0.5 would deliver roughly half of the diagnostic width gain.

**Decision.** If the upper-bound width gain is ≥ 5% at τ=0.95, building a forward predictor is the right next workstream. If < 5%, the engineering cost of a forward predictor likely exceeds the win and M6a should be Rejected.

Reproducible via `scripts/run_m6a_common_mode_partial_out.py`. Source data: `reports/tables/v1b_m6a_common_mode_oos.csv`, `reports/tables/v1b_m6a_common_mode_fit.csv`.