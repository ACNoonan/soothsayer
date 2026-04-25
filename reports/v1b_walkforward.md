# V1b — Walk-forward calibration backtest

**Method.** Rolling-origin expanding-window walk-forward. For each cutoff in ['2019-01-01', '2020-01-01', '2021-01-01', '2022-01-01', '2023-01-01', '2024-01-01'], train calibration surface on bounds with fri_ts < cutoff, evaluate Oracle on bounds in [cutoff, cutoff + 12 months). For each τ ∈ {0.68, 0.85, 0.95, 0.99}, sweep buffer over `[0.000, 0.060]` step 0.005 and pick the smallest passing realized ≥ τ−0.005 + Kupiec $p_{uc}$ > 0.10 + Christoffersen $p_{ind}$ > 0.05.

## Per-target buffer summary across splits

|   target |   n_splits |   buffer_mean |   buffer_std |   buffer_min |   buffer_max |   deployed_buffer |   realized_mean |   realized_std |   p_uc_min |   n_pass |
|---------:|-----------:|--------------:|-------------:|-------------:|-------------:|------------------:|----------------:|---------------:|-----------:|---------:|
|    0.680 |      6.000 |         0.016 |        0.022 |        0.000 |        0.055 |             0.045 |           0.706 |          0.030 |      0.000 |    3.000 |
|    0.850 |      6.000 |         0.025 |        0.022 |        0.000 |        0.055 |             0.045 |           0.859 |          0.017 |      0.045 |    4.000 |
|    0.950 |      6.000 |         0.019 |        0.017 |        0.000 |        0.045 |             0.020 |           0.951 |          0.012 |      0.004 |    5.000 |
|    0.990 |      6.000 |         0.050 |        0.024 |        0.000 |        0.060 |             0.005 |           0.970 |          0.017 |      0.000 |    1.000 |

## Per-split detail

|   split | cutoff     | horizon_end   |   n_train_b |   n_test_p |   target |   buffer_chosen |   realized |   mean_half_width_bps |   p_uc |   p_ind | status   |
|--------:|:-----------|:--------------|------------:|-----------:|---------:|----------------:|-----------:|----------------------:|-------:|--------:|:---------|
|       0 | 2019-01-01 | 2020-01-01    |       50088 |        468 |    0.680 |           0.010 |      0.679 |                75.091 |  0.981 |   0.592 | PASS     |
|       0 | 2019-01-01 | 2020-01-01    |       50088 |        468 |    0.850 |           0.035 |      0.853 |               123.024 |  0.876 |   0.365 | PASS     |
|       0 | 2019-01-01 | 2020-01-01    |       50088 |        468 |    0.950 |           0.025 |      0.947 |               251.777 |  0.737 |   0.383 | PASS     |
|       0 | 2019-01-01 | 2020-01-01    |       50088 |        468 |    0.990 |           0.060 |      0.966 |               314.701 |  0.000 |   0.808 | CEILING  |
|       1 | 2020-01-01 | 2021-01-01    |       61320 |        477 |    0.680 |           0.030 |      0.709 |               173.409 |  0.177 |   0.054 | PASS     |
|       1 | 2020-01-01 | 2021-01-01    |       61320 |        477 |    0.850 |           0.055 |      0.849 |               299.856 |  0.954 |   0.068 | PASS     |
|       1 | 2020-01-01 | 2021-01-01    |       61320 |        477 |    0.950 |           0.045 |      0.948 |               677.093 |  0.810 |   0.725 | PASS     |
|       1 | 2020-01-01 | 2021-01-01    |       61320 |        477 |    0.990 |           0.060 |      0.948 |               677.093 |  0.000 |   0.725 | CEILING  |
|       2 | 2021-01-01 | 2022-01-01    |       72768 |        489 |    0.680 |           0.000 |      0.753 |               118.042 |  0.000 |   0.568 | CEILING  |
|       2 | 2021-01-01 | 2022-01-01    |       72768 |        489 |    0.850 |           0.000 |      0.881 |               193.907 |  0.045 |   0.542 | CEILING  |
|       2 | 2021-01-01 | 2022-01-01    |       72768 |        489 |    0.950 |           0.000 |      0.947 |               340.903 |  0.750 |   0.842 | PASS     |
|       2 | 2021-01-01 | 2022-01-01    |       72768 |        489 |    0.990 |           0.060 |      0.980 |               569.905 |  0.042 |   0.606 | CEILING  |
|       3 | 2022-01-01 | 2023-01-01    |       84252 |        520 |    0.680 |           0.000 |      0.731 |               184.602 |  0.012 |   0.860 | CEILING  |
|       3 | 2022-01-01 | 2023-01-01    |       84252 |        520 |    0.850 |           0.000 |      0.879 |               285.878 |  0.058 |   0.165 | MARGINAL |
|       3 | 2022-01-01 | 2023-01-01    |       84252 |        520 |    0.950 |           0.000 |      0.975 |               492.380 |  0.004 |   0.012 | CEILING  |
|       3 | 2022-01-01 | 2023-01-01    |       84252 |        520 |    0.990 |           0.000 |      0.996 |               723.292 |  0.107 |   0.686 | PASS     |
|       4 | 2023-01-01 | 2024-01-01    |       96384 |        520 |    0.680 |           0.000 |      0.679 |               108.344 |  0.955 |   0.375 | PASS     |
|       4 | 2023-01-01 | 2024-01-01    |       96384 |        520 |    0.850 |           0.020 |      0.846 |               194.044 |  0.807 |   0.312 | PASS     |
|       4 | 2023-01-01 | 2024-01-01    |       96384 |        520 |    0.950 |           0.020 |      0.946 |               358.609 |  0.691 |   0.846 | PASS     |
|       4 | 2023-01-01 | 2024-01-01    |       96384 |        520 |    0.990 |           0.060 |      0.973 |               402.716 |  0.001 |   0.746 | CEILING  |
|       5 | 2024-01-01 | 2025-01-01    |      108864 |        520 |    0.680 |           0.055 |      0.687 |               122.973 |  0.749 |   0.002 | MARGINAL |
|       5 | 2024-01-01 | 2025-01-01    |      108864 |        520 |    0.850 |           0.040 |      0.846 |               197.577 |  0.807 |   0.163 | PASS     |
|       5 | 2024-01-01 | 2025-01-01    |      108864 |        520 |    0.950 |           0.025 |      0.946 |               398.090 |  0.691 |   0.866 | PASS     |
|       5 | 2024-01-01 | 2025-01-01    |      108864 |        520 |    0.990 |           0.060 |      0.956 |               448.519 |  0.000 |   0.928 | CEILING  |

## Reading

- `buffer_mean ± buffer_std` is the empirical distribution of optimal buffers across walk-forward splits — the single-split values in `BUFFER_BY_TARGET` should fall within ~1σ of `buffer_mean`.
- `n_pass / n_splits` is the fraction of splits in which the chosen buffer satisfies the strict (PASS) criteria. Lower fractions reveal targets where calibration is fundamentally harder (typically the tails).
- `realized_std` quantifies how stable the served calibration is across deployment windows; small values support a fixed `BUFFER_BY_TARGET` schedule with rolling re-fits, large values argue for adaptive per-window re-tuning.

## Use

1. For paper §9.4 ('sample-size-one buffer' disclosure): replace with measured `buffer_mean ± buffer_std` per τ.
2. For deployment cadence (`docs/v2.md` §V2.2): the `realized_std` figure caps the rolling rebuild interval — if drift is bounded, quarterly rebuilds suffice; otherwise monthly or event-driven.
3. For grant application (`docs/grant_application_tldr.md`): the walk-forward result is the Tier-1 deliverable that converts a single-split anchor into a distribution-valued claim.