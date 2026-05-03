# §6.6 Path coverage — robustness checks

The headline §6.6 result is a 14.4pp gap at τ=0.95 between endpoint coverage (0.983) and perp-path coverage (0.839) on 118 (symbol, weekend) rows. This file reports three robustness checks before treating the gap as the product-level truth: (A) perp-vs-spot basis at the Friday-close anchor, (B) volume floor on perp bars, (C) sustained-crossing definition via rolling-median.

## (A) Perp-vs-spot basis at Friday 16:00 ET

If the perp anchors significantly off the NYSE close, the raw perp path is in different units than the band. Recenter every perp bar by `fri_close / perp_anchor` and recompute path coverage. The basis distribution across 118 (symbol, weekend) pairs:

|   n_pairs |   basis_mean_bps |   basis_median_bps |   basis_p5_bps |   basis_p95_bps |   basis_abs_mean_bps |   basis_abs_p95_bps |
|----------:|-----------------:|-------------------:|---------------:|----------------:|---------------------:|--------------------:|
|    118.00 |            -5.33 |              -8.54 |        -249.95 |          253.89 |               106.43 |              393.11 |


**Pooled by τ — raw vs basis-normalized path coverage:**

|    tau |        n |   endpoint_cov |   path_cov_raw |   path_cov_norm |   gap_pp_raw |   gap_pp_norm |   delta_norm_vs_raw_pp |
|-------:|---------:|---------------:|---------------:|----------------:|-------------:|--------------:|-----------------------:|
| 0.6800 | 118.0000 |         0.7712 |         0.5085 |          0.5254 |      26.2712 |       24.5763 |                 1.6949 |
| 0.8500 | 118.0000 |         0.9153 |         0.7288 |          0.7966 |      18.6441 |       11.8644 |                 6.7797 |
| 0.9500 | 118.0000 |         0.9831 |         0.8390 |          0.8814 |      14.4068 |       10.1695 |                 4.2373 |
| 0.9900 | 118.0000 |         1.0000 |         0.9661 |          0.9746 |       3.3898 |        2.5424 |                 0.8475 |


*Reading.* If `basis_abs_mean_bps` is < 50bps the perp anchors cleanly and `delta_norm_vs_raw_pp` should be small. A large delta (say > 5pp) means the headline number was driven by perp-spot basis at the start-of-window, not by intra-weekend price moves.


## (B) Volume floor on perp bars

Drop bars below `volume_base` thresholds and recompute path coverage on the survivors. Tests whether thin-liquidity prints drive the violations. `survival_share` = mean fraction of the weekend-window bars that survive the filter.

|   vol_floor |    tau |        n |   endpoint_cov |   path_cov |   n_bars_mean |   survival_share |   gap_pp |
|------------:|-------:|---------:|---------------:|-----------:|--------------:|-----------------:|---------:|
|      0.0000 | 0.6800 | 118.0000 |         0.7712 |     0.5085 |     3990.9407 |          20.4664 |  26.2712 |
|      0.0000 | 0.8500 | 118.0000 |         0.9153 |     0.7288 |     3990.9407 |          20.4664 |  18.6441 |
|      0.0000 | 0.9500 | 118.0000 |         0.9831 |     0.8390 |     3990.9407 |          20.4664 |  14.4068 |
|      0.0000 | 0.9900 | 118.0000 |         1.0000 |     0.9661 |     3990.9407 |          20.4664 |   3.3898 |
|      0.1000 | 0.6800 |  76.0000 |         0.7500 |     0.5526 |       11.4079 |           0.0585 |  19.7368 |
|      0.1000 | 0.8500 |  76.0000 |         0.9079 |     0.7500 |       11.4079 |           0.0585 |  15.7895 |
|      0.1000 | 0.9500 |  76.0000 |         0.9737 |     0.8553 |       11.4079 |           0.0585 |  11.8421 |
|      0.1000 | 0.9900 |  76.0000 |         1.0000 |     0.9737 |       11.4079 |           0.0585 |   2.6316 |
|      1.0000 | 0.6800 |  63.0000 |         0.7143 |     0.4762 |        8.6190 |           0.0442 |  23.8095 |
|      1.0000 | 0.8500 |  63.0000 |         0.9048 |     0.7143 |        8.6190 |           0.0442 |  19.0476 |
|      1.0000 | 0.9500 |  63.0000 |         0.9841 |     0.8413 |        8.6190 |           0.0442 |  14.2857 |
|      1.0000 | 0.9900 |  63.0000 |         1.0000 |     0.9683 |        8.6190 |           0.0442 |   3.1746 |
|     10.0000 | 0.6800 |  42.0000 |         0.6905 |     0.5714 |        4.0952 |           0.0210 |  11.9048 |
|     10.0000 | 0.8500 |  42.0000 |         0.9048 |     0.7381 |        4.0952 |           0.0210 |  16.6667 |
|     10.0000 | 0.9500 |  42.0000 |         0.9762 |     0.9048 |        4.0952 |           0.0210 |   7.1429 |
|     10.0000 | 0.9900 |  42.0000 |         1.0000 |     1.0000 |        4.0952 |           0.0210 |   0.0000 |


*Reading.* If `path_cov` rises substantially as `vol_floor` increases — say from 0.84 to 0.92 at vol_floor = 1.0 — then the headline gap is partly perp microstructure noise on thin bars. If `path_cov` is flat across thresholds, the gap is real and not a thin-liquidity artifact.


## (C) Sustained crossing (rolling median)

Replace the `any 1m bar` violation definition with a rolling median of the close. Most lending protocols TWAP the on-chain price before liquidating, so a 5–15 minute median is closer to the consumer-relevant trigger than a single tick.

|   sustain_window_min |    tau |        n |   endpoint_cov |   path_cov |   gap_pp |
|---------------------:|-------:|---------:|---------------:|-----------:|---------:|
|               1.0000 | 0.6800 | 118.0000 |         0.7712 |     0.5085 |  26.2712 |
|               1.0000 | 0.8500 | 118.0000 |         0.9153 |     0.7288 |  18.6441 |
|               1.0000 | 0.9500 | 118.0000 |         0.9831 |     0.8390 |  14.4068 |
|               1.0000 | 0.9900 | 118.0000 |         1.0000 |     0.9661 |   3.3898 |
|               5.0000 | 0.6800 | 118.0000 |         0.7712 |     0.5254 |  24.5763 |
|               5.0000 | 0.8500 | 118.0000 |         0.9153 |     0.7373 |  17.7966 |
|               5.0000 | 0.9500 | 118.0000 |         0.9831 |     0.8559 |  12.7119 |
|               5.0000 | 0.9900 | 118.0000 |         1.0000 |     0.9661 |   3.3898 |
|              15.0000 | 0.6800 | 118.0000 |         0.7712 |     0.5339 |  23.7288 |
|              15.0000 | 0.8500 | 118.0000 |         0.9153 |     0.7458 |  16.9492 |
|              15.0000 | 0.9500 | 118.0000 |         0.9831 |     0.8559 |  12.7119 |
|              15.0000 | 0.9900 | 118.0000 |         1.0000 |     0.9661 |   3.3898 |


*Reading.* The `sustain_window_min = 1` row reproduces the headline (single-bar definition). Higher windows test whether the gap is sustained drift or single-print noise. A drop from 14pp at win=1 to ~5pp at win=15 says most violations are transient prints; a flat profile says the gap is sustained.
