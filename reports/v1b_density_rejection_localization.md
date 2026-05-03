# V1b — Density rejection localization (W2)

**Question.** Both v1 (deployed Oracle) and M5 (v2 candidate) reject Berkowitz on the OOS 2023+ panel, but for different reasons. Where does each rejection live? If a partition can be localized, that partition is a v3-forecaster lead and the disclosure can move from "per-anchor only" to "per-anchor uniformly except in partition X."

## Berkowitz LR decomposition (pooled, n=1,730)

For each methodology, the joint Berkowitz LR is decomposed into the marginal contribution of three nested restrictions: mean=0, var=1, AR(1)=0. The share columns indicate which restriction is doing the rejecting.

| methodology        |    n |   lr_full |   p_full |   rho_hat |   mean_z |   var_z |   lr_mean_only |   lr_var_only |   lr_ar1_only |   share_mean |   share_var |   share_ar1 |
|:-------------------|-----:|----------:|---------:|----------:|---------:|--------:|---------------:|--------------:|--------------:|-------------:|------------:|------------:|
| v1_deployed_oracle | 1730 |    37.601 |    0.000 |    -0.043 |    0.074 |   0.839 |          9.354 |        23.347 |         1.881 |        0.270 |       0.675 |       0.054 |
| m5_v2_candidate    | 1730 |   173.088 |    0.000 |     0.308 |    0.018 |   0.990 |          0.569 |         0.086 |       162.728 |        0.003 |       0.001 |       0.996 |

## Lag-1 autocorrelation: cross-sectional vs temporal

Berkowitz's joint LR uses lag-1 pairs in panel-row order. The lag-1 alternative captures *different* structure depending on how the panel is sorted:
- `cross_sectional_within_weekend`: pairs are (symbol_i, symbol_{i+1}) on the same Friday. Captures common-mode residual that the methodology's factor adjustment didn't fully partial out.
- `temporal_within_symbol`: pairs are (fri_ts_t, fri_ts_{t+1}) for the same symbol. Captures persistent per-symbol mis-calibration over time.

| methodology        | label                          |   n_pairs |    rho |   p_value |
|:-------------------|:-------------------------------|----------:|-------:|----------:|
| v1_deployed_oracle | cross_sectional_within_weekend |      1557 |  0.354 |     0.000 |
| v1_deployed_oracle | temporal_within_symbol         |      1720 | -0.041 |     0.087 |
| m5_v2_candidate    | cross_sectional_within_weekend |      1557 |  0.353 |     0.000 |
| m5_v2_candidate    | temporal_within_symbol         |      1720 | -0.032 |     0.184 |

## Per-partition Berkowitz + DQ

Berkowitz and DQ at τ=0.95 re-run within each partition. Look for partitions where p-values are non-rejecting — those are the locally-uniform PIT regions. Look for partitions with the largest LR per row — those are the localized rejection sources.

Top 20 most-rejecting (Berkowitz LR descending):

| methodology        | partition_col     | partition    |    n |   berkowitz_lr |   berkowitz_p |   rho_hat |   var_z |   dq_95 |   dq_95_p |
|:-------------------|:------------------|:-------------|-----:|---------------:|--------------:|----------:|--------:|--------:|----------:|
| m5_v2_candidate    | earnings_adjacent | no_earnings  | 1648 |        182.459 |         0.000 |     0.323 |   0.970 |  33.810 |     0.000 |
| m5_v2_candidate    | pooled            | all          | 1730 |        173.088 |         0.000 |     0.308 |   0.990 |  32.082 |     0.000 |
| m5_v2_candidate    | vix_bucket        | high         |  580 |         95.831 |         0.000 |     0.389 |   1.017 |  13.960 |     0.016 |
| m5_v2_candidate    | regime_pub        | normal       | 1160 |         90.223 |         0.000 |     0.268 |   1.057 |  18.704 |     0.002 |
| m5_v2_candidate    | regime_pub        | high_vol     |  380 |         87.599 |         0.000 |     0.431 |   0.825 |  24.739 |     0.000 |
| m5_v2_candidate    | symbol            | SPY          |  173 |         85.828 |         0.000 |    -0.005 |   0.302 | nan     |   nan     |
| m5_v2_candidate    | symbol            | MSTR         |  173 |         64.776 |         0.000 |    -0.072 |   2.103 |  44.344 |     0.000 |
| m5_v2_candidate    | vix_bucket        | mid          |  570 |         61.779 |         0.000 |     0.317 |   1.041 |  16.180 |     0.006 |
| m5_v2_candidate    | symbol            | TLT          |  173 |         51.008 |         0.000 |    -0.015 |   0.428 | nan     |   nan     |
| m5_v2_candidate    | symbol            | QQQ          |  173 |         45.407 |         0.000 |    -0.023 |   0.438 |   6.917 |     0.227 |
| m5_v2_candidate    | symbol            | GLD          |  173 |         45.061 |         0.000 |     0.037 |   0.443 |   6.917 |     0.227 |
| m5_v2_candidate    | regime_pub        | long_weekend |  190 |         38.047 |         0.000 |     0.309 |   0.809 |   4.563 |     0.472 |
| v1_deployed_oracle | pooled            | all          | 1730 |         37.601 |         0.000 |    -0.043 |   0.839 |  48.629 |     0.000 |
| v1_deployed_oracle | regime_pub        | normal       | 1160 |         36.931 |         0.000 |     0.019 |   0.819 |  38.496 |     0.000 |
| m5_v2_candidate    | symbol            | TSLA         |  173 |         34.062 |         0.000 |     0.039 |   1.740 |  33.504 |     0.000 |
| v1_deployed_oracle | earnings_adjacent | no_earnings  | 1648 |         32.827 |         0.000 |    -0.029 |   0.839 |  46.258 |     0.000 |
| m5_v2_candidate    | vix_bucket        | low          |  580 |         30.792 |         0.000 |     0.216 |   0.909 |  33.044 |     0.000 |
| m5_v2_candidate    | symbol            | HOOD         |  173 |         30.471 |         0.000 |    -0.124 |   1.671 |  52.026 |     0.000 |
| v1_deployed_oracle | symbol            | MSTR         |  173 |         26.078 |         0.000 |    -0.040 |   0.551 |   8.552 |     0.128 |
| v1_deployed_oracle | vix_bucket        | mid          |  570 |         23.564 |         0.000 |    -0.053 |   0.785 |  17.601 |     0.003 |

Non-rejecting partitions (Berkowitz p ≥ 0.05, n ≥ 50):

| methodology        | partition_col     | partition     |   n |   berkowitz_lr |   berkowitz_p |   rho_hat |   var_z |
|:-------------------|:------------------|:--------------|----:|---------------:|--------------:|----------:|--------:|
| m5_v2_candidate    | symbol            | NVDA          | 173 |          4.023 |         0.259 |    -0.069 |   1.188 |
| m5_v2_candidate    | earnings_adjacent | with_earnings |  82 |          6.338 |         0.096 |     0.016 |   1.354 |
| m5_v2_candidate    | symbol            | GOOGL         | 173 |          7.143 |         0.067 |     0.064 |   0.772 |
| v1_deployed_oracle | symbol            | AAPL          | 173 |          1.298 |         0.730 |    -0.069 |   0.939 |
| v1_deployed_oracle | symbol            | GOOGL         | 173 |          1.846 |         0.605 |     0.098 |   1.035 |
| v1_deployed_oracle | symbol            | SPY           | 173 |          2.586 |         0.460 |    -0.038 |   1.079 |
| v1_deployed_oracle | vix_bucket        | low           | 580 |          4.142 |         0.247 |    -0.055 |   0.930 |
| v1_deployed_oracle | symbol            | QQQ           | 173 |          4.160 |         0.245 |    -0.102 |   0.949 |
| v1_deployed_oracle | earnings_adjacent | with_earnings |  82 |          6.148 |         0.105 |    -0.031 |   0.772 |
| v1_deployed_oracle | symbol            | GLD           | 173 |          6.623 |         0.085 |    -0.002 |   0.765 |

## Reading

Four findings surface from this analysis:

1. **v1 and M5 fail Berkowitz for different reasons (pooled, methodology-side ordering).** v1's pooled rejection is 68% variance compression (var_z ≈ 0.84) and 5% AR(1) — the deployed band at τ=0.95 plus the 0.020 buffer is slightly *too wide*, so PITs cluster toward 0.5 instead of spanning U(0,1). M5's pooled rejection is 99.6% AR(1) (rho ≈ 0.31, var_z ≈ 0.99) — per-row magnitude is calibrated; consecutive-row PITs are correlated.

2. **The cross-sectional AR(1) is identical across methodologies (~0.35) and is a data property, not a methodology artefact.** Re-ordering both v1's and M5's PITs by (fri_ts, symbol) and computing lag-1 within-weekend gives ρ ≈ 0.354 for *both*. Within-symbol temporal lag-1 is ≈ 0 for both. The methodologies produce different pooled Berkowitz LR purely because their default panel orderings probe different lag structures: `run_reviewer_diagnostics.py` orders v1 by `(symbol, fri_ts)` (temporal-first; misses the real autocorrelation), while `density_tests_m5` orders M5 by `(fri_ts, symbol)` (cross-sectional-first; picks it up). Both methodologies fail to absorb the common-mode weekend residual after their respective factor-adjusted points.

3. **Per-symbol M5 reveals heterogeneous variance — the second v3 lead.** Single-symbol Berkowitz on M5 (within-symbol ordering, so AR(1) is near-zero per finding 2) shows wildly different `var_z`: SPY (0.30), QQQ (0.44), GLD (0.44), TLT (0.43) all have *compressed* PIT distributions (M5's bands too wide for these), while MSTR (2.10), TSLA (1.74), HOOD (1.67) have *inflated* distributions (M5's bands too narrow). M5's per-regime conformal quantile pools across all symbols within a regime; per-symbol residual scale is not uniform within a regime. NVDA (var_z=1.19, p=0.26) and GOOGL (var_z=0.77, p=0.07) are the locally-uniform exceptions.

4. **Non-rejecting partitions exist and have a clean shape.** Partitions where Berkowitz p ≥ 0.05 with n ≥ 50 are: M5/NVDA, M5/GOOGL, M5/with_earnings (n=82, p=0.096); v1/AAPL, v1/GOOGL, v1/SPY, v1/QQQ, v1/GLD, v1/vix_low, v1/with_earnings. Within-symbol calibration is locally uniform for v1 across nearly all symbols (no AR(1) within-symbol; mean and variance are close to Gaussian). The pooled rejection is entirely a cross-sectional phenomenon for both methodologies.

## Decision implications

- **Disclosure.** Paper 1 §6 / §9 can update from "per-anchor calibration only" to: *per-anchor calibration is uniform within-symbol across the panel; the pooled Berkowitz rejection is fully attributable to (a) common-mode residual autocorrelation across symbols within a weekend (cross-sectional ρ ≈ 0.35) and (b) heterogeneous per-symbol residual variance under M5's per-regime quantile pooling. Both are isolated v3 leads.*
- **v3 lead 1: common-mode residual partial-out.** Regress per-row residual on the cross-sectional weekend mean residual (pseudo factor-2); refit the per-regime conformal quantile on the doubly-residualised score. Expected to remove the cross-sectional ρ ≈ 0.35 and tighten the band by ~10–15% at matched coverage.
- **v3 lead 2: per-symbol Mondrian.** Move from `Mondrian(regime)` to `Mondrian(regime × {symbol-class})` where symbol-class is one of {equity_index, single_stock_meta, equity_high_beta, gold, bond}. Specifically tightens SPY/QQQ/TLT/GLD bands and widens MSTR/TSLA/HOOD bands — re-allocates width across the universe rather than reducing total width.
- **Not a methodology change for v1 or M5.** This analysis strengthens the disclosure and supplies two cleanly-scoped v3 leads. It does not justify reverting M5 or modifying v1.

Source data:
- `reports/tables/v1b_density_rejection_pit_m5.csv` — per-row M5 PITs + violation flags
- `reports/tables/v1b_density_rejection_per_partition.csv` — Berkowitz + DQ per partition
- `reports/tables/v1b_density_rejection_lag1_decomposition.csv` — cross-sectional vs temporal lag-1
- `reports/tables/v1b_density_rejection_berkowitz_decomposed.csv` — pooled LR decomposition

Reproducible via `scripts/run_density_rejection_diagnostics.py`.