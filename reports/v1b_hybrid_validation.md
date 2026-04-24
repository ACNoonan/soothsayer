# V1b Hybrid Oracle — Product-Level Validation

**Question:** when a consumer asks for target realized coverage via the hybrid-regime Oracle, do they actually get it?

**Method:** run `Oracle.fair_value(symbol, as_of, target_coverage=t)` over every historical weekend in the panel for t ∈ (0.68, 0.95, 0.99), record whether the realized Monday open fell inside the served band, aggregate realized coverage.

Two splits:

- **In-sample:** full calibration surface, full panel. Machinery check — realized should be close to target by construction. If it isn't, there's a bug.
- **Out-of-sample:** calibration surface built from pre-2023-01-01 bounds only (96,384 rows), Oracle served on weekends from 2023-01-01 onward (41,280 rows). Closest analog to production where the surface is rebuilt periodically.

![Hybrid reliability](figures/v1b_hybrid_reliability.png)

## In-sample coverage (machinery check)

| split     | regime_pub   |   target |    n |   realized |   mean_half_width_bps |
|:----------|:-------------|---------:|-----:|-----------:|----------------------:|
| in_sample | high_vol     |    0.680 | 1432 |      0.735 |               174.596 |
| in_sample | long_weekend |    0.680 |  630 |      0.719 |               117.564 |
| in_sample | normal       |    0.680 | 3924 |      0.725 |                97.184 |
| in_sample | high_vol     |    0.950 | 1432 |      0.974 |               585.581 |
| in_sample | long_weekend |    0.950 |  630 |      0.970 |               389.227 |
| in_sample | normal       |    0.950 | 3924 |      0.978 |               341.508 |
| in_sample | high_vol     |    0.990 | 1432 |      0.985 |               700.054 |
| in_sample | long_weekend |    0.990 |  630 |      0.981 |               429.358 |
| in_sample | normal       |    0.990 | 3924 |      0.980 |               384.923 |
| in_sample | pooled       |    0.680 | 5986 |      0.727 |               117.848 |
| in_sample | pooled       |    0.950 | 5986 |      0.976 |               404.919 |
| in_sample | pooled       |    0.990 | 5986 |      0.981 |               464.987 |

### Kupiec / Christoffersen on in-sample pooled

|   target |        n |   violations |   violation_rate |   expected_rate |   lr_uc |   p_uc |   lr_ind |   p_ind |
|---------:|---------:|-------------:|-----------------:|----------------:|--------:|-------:|---------:|--------:|
|    0.680 | 5986.000 |     1637.000 |            0.273 |           0.320 |  61.254 |  0.000 |   28.034 |   0.000 |
|    0.950 | 5986.000 |      144.000 |            0.024 |           0.050 | 104.093 |  0.000 |   19.670 |   0.000 |
|    0.990 | 5986.000 |      111.000 |            0.019 |           0.010 |  35.252 |  0.000 |   20.509 |   0.000 |

## Out-of-sample coverage (the real number)

| split         | regime_pub   |   target |    n |   realized |   mean_half_width_bps |
|:--------------|:-------------|---------:|-----:|-----------:|----------------------:|
| out_of_sample | high_vol     |    0.680 |  380 |      0.663 |               188.042 |
| out_of_sample | long_weekend |    0.680 |  190 |      0.600 |               114.621 |
| out_of_sample | normal       |    0.680 | 1150 |      0.673 |               113.714 |
| out_of_sample | high_vol     |    0.950 |  380 |      0.966 |               614.137 |
| out_of_sample | long_weekend |    0.950 |  190 |      0.953 |               396.469 |
| out_of_sample | normal       |    0.950 | 1150 |      0.958 |               413.949 |
| out_of_sample | high_vol     |    0.990 |  380 |      0.974 |               747.522 |
| out_of_sample | long_weekend |    0.990 |  190 |      0.958 |               435.288 |
| out_of_sample | normal       |    0.990 | 1150 |      0.973 |               457.901 |
| out_of_sample | pooled       |    0.680 | 1720 |      0.663 |               130.235 |
| out_of_sample | pooled       |    0.950 | 1720 |      0.959 |               456.245 |
| out_of_sample | pooled       |    0.990 | 1720 |      0.972 |               519.389 |

### Kupiec / Christoffersen on OOS pooled

|   target |        n |   violations |   violation_rate |   expected_rate |   lr_uc |   p_uc |   lr_ind |   p_ind |
|---------:|---------:|-------------:|-----------------:|----------------:|--------:|-------:|---------:|--------:|
|    0.680 | 1720.000 |      580.000 |            0.337 |           0.320 |   2.320 |  0.128 |    2.050 |   0.152 |
|    0.950 | 1720.000 |       70.000 |            0.041 |           0.050 |   3.337 |  0.068 |    2.939 |   0.086 |
|    0.990 | 1720.000 |       49.000 |            0.028 |           0.010 |  39.595 |  0.000 |    0.245 |   0.621 |

## Reading the tables

- `realized` vs `target` column: the closer these match, the better the hybrid's calibration surface generalises. A difference of ≤2pp is institutional-acceptable; 3–5pp is a disclosure; >5pp means the surface is stale or overfit.
- `mean_half_width_bps` is the mean band half-width (in bps of Friday close) that the consumer actually received at each target.
- Kupiec p-values are for the null that realized rate equals target. Christoffersen p-values are for the null that violations don't cluster in time.
- Compare the in-sample table to the out-of-sample table. In-sample close-to-target confirms the inversion machinery; OOS close-to-target confirms the calibration surface generalises. A large delta between them indicates overfitting.