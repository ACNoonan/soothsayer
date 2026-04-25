# V1b — Tier-1 Diagnostics

Four cheap diagnostics that close paper-side disclosures with empirical evidence. Each is reproducible from the published artefacts (`data/processed/v1b_bounds.parquet`, `src/soothsayer/oracle.py`).

## D1 — Bias absorption (numerical verification of §6.6 derivation)

The empirical-quantile architecture takes quantiles of $\log(P_t / \hat P_t)$ directly; the served band's lower/upper bounds shift asymmetrically around any point bias, and the served point we publish is the band midpoint $(L+U)/2$. We verify numerically:

|   target |        n |   served_point_offset_from_midpoint_bps_max_abs |   median_residual_vs_served_point_bps |   realized_coverage |
|---------:|---------:|------------------------------------------------:|--------------------------------------:|--------------------:|
|    0.680 | 1720.000 |                                           0.000 |                                10.312 |               0.678 |
|    0.850 | 1720.000 |                                           0.000 |                                14.110 |               0.855 |
|    0.950 | 1720.000 |                                           0.000 |                                23.551 |               0.950 |
|    0.990 | 1720.000 |                                           0.000 |                                31.108 |               0.972 |

`served_point_offset_from_midpoint_bps_max_abs` is the largest deviation between the published served point and the band midpoint across all OOS rows; it should be exactly zero by construction. `median_residual_vs_served_point_bps` is the median of (mon_open − served_point) in bps; small magnitudes confirm the served point is internally consistent with the band's coverage geometry.

## D2 — Stationarity (ADF + KPSS) on per-symbol residual series

§9.3 of the paper assumes approximate stationarity of the conditional residual distribution. We test ADF (null = unit root, reject = stationary) and KPSS (null = stationary, reject = non-stationary) on each symbol's weekend log-return.

| symbol   |   n |   adf_p |   kpss_p | joint_conclusion               |
|:---------|----:|--------:|---------:|:-------------------------------|
| AAPL     | 638 |   0.000 |    0.100 | stationary                     |
| GLD      | 637 |   0.000 |    0.064 | stationary                     |
| GOOGL    | 638 |   0.000 |    0.100 | stationary                     |
| HOOD     | 245 |   0.000 |    0.030 | trend_or_difference_stationary |
| MSTR     | 638 |   0.000 |    0.100 | stationary                     |
| NVDA     | 638 |   0.000 |    0.100 | stationary                     |
| QQQ      | 638 |   0.000 |    0.100 | stationary                     |
| SPY      | 638 |   0.000 |    0.100 | stationary                     |
| TLT      | 638 |   0.000 |    0.042 | trend_or_difference_stationary |
| TSLA     | 638 |   0.000 |    0.100 | stationary                     |

## D3 — PIT uniformity diagnostic

Diebold-Gunther-Tay (1998) framework. The PIT value for each (symbol, weekend) is the smallest claimed quantile at which the band covered the realised Monday open; if our calibration surface is well-specified, the PIT distribution should be uniform on $(0,1)$.

**Result.** KS test against $U(0,1)$: statistic = 0.500, p-value = 0.000. **Rejected** at $\alpha=0.05$ — full-distribution calibration is non-uniform; the calibration claim is target-specific rather than distribution-wide. This is a more cautious finding than what §6.4 reports and should be disclosed explicitly.

PIT histogram is at `reports/figures/v1b_diag_pit.png`. 1,720 PIT values total; 49 non-covered rows assigned PIT=1.0.

## D4 — Christoffersen aggregation sensitivity

We compare three pooling rules for the per-symbol Christoffersen independence test:

- **Method A (deployed):** $\sum_i \mathrm{LR}_i$ vs $\chi^2(n_\text{groups})$ — the test reported in §6.4.
- **Method B (Bonferroni):** $n \cdot \min_i p_i$, capped at 1.
- **Method C (Holm-Šidák):** sequential adjustment of sorted per-symbol $p$-values.

|   target |   n_groups |   sum_LR |   p_sumLR_chi2 |   p_bonferroni |   p_holm_sidak |   min_per_symbol_p |
|---------:|-----------:|---------:|---------------:|---------------:|---------------:|-------------------:|
|    0.680 |     10.000 |    7.818 |          0.647 |          1.000 |          0.683 |              0.109 |
|    0.850 |     10.000 |   13.750 |          0.185 |          0.400 |          0.335 |              0.040 |
|    0.950 |     10.000 |    9.500 |          0.485 |          0.810 |          0.570 |              0.081 |
|    0.990 |     10.000 |    4.910 |          0.897 |          1.000 |          0.869 |              0.184 |

**Reading.** All three methods test the joint null *no symbol's violations cluster*. If the three pooled $p$-values agree on accept/reject at $\alpha = 0.05$ for the τ ∈ {0.85, 0.95} headline targets, the deployed Christoffersen pooling is robust to choice of multiple-testing correction. If they disagree, the deployed claim should be disclosed as pooling-rule-dependent.