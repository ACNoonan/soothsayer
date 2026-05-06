# §6.6 Path coverage — robustness checks

The headline §6.6 result under the deployed M6 LWC artefact is a +16.1pp gap at τ=0.95 between endpoint coverage (0.949) and perp-path coverage (0.788) on 118 (symbol, weekend) rows. This file reports three robustness checks before treating the gap as the product-level truth: (A) perp-vs-spot basis at the Friday-close anchor, (B) volume floor on perp bars, (C) sustained-crossing definition via rolling-median.

## (A) Perp-vs-spot basis at Friday 16:00 ET

If the perp anchors significantly off the NYSE close, the raw perp path is in different units than the band. Recenter every perp bar by `fri_close / perp_anchor` and recompute path coverage. The basis distribution across 118 (symbol, weekend) pairs:

|   n_pairs |   basis_mean_bps |   basis_median_bps |   basis_p5_bps |   basis_p95_bps |   basis_abs_mean_bps |   basis_abs_p95_bps |
|----------:|-----------------:|-------------------:|---------------:|----------------:|---------------------:|--------------------:|
|    118.00 |            -5.33 |              -8.54 |        -249.95 |          253.89 |               106.43 |              393.11 |


**Pooled by τ — raw vs basis-normalized path coverage:**

|    tau |        n |   endpoint_cov |   path_cov_raw |   path_cov_norm |   gap_pp_raw |   gap_pp_norm |   delta_norm_vs_raw_pp |
|-------:|---------:|---------------:|---------------:|----------------:|-------------:|--------------:|-----------------------:|
| 0.6800 | 118.0000 |         0.6441 |         0.3475 |          0.3898 |      29.6610 |       25.4237 |                 4.2373 |
| 0.8500 | 118.0000 |         0.8644 |         0.5678 |          0.6186 |      29.6610 |       24.5763 |                 5.0847 |
| 0.9500 | 118.0000 |         0.9492 |         0.7881 |          0.8390 |      16.1017 |       11.0169 |                 5.0847 |
| 0.9900 | 118.0000 |         0.9915 |         0.9153 |          0.9407 |       7.6271 |        5.0847 |                 2.5424 |


*Reading.* If `basis_abs_mean_bps` is < 50bps the perp anchors cleanly and `delta_norm_vs_raw_pp` should be small. A large delta (say > 5pp) means the headline number was driven by perp-spot basis at the start-of-window, not by intra-weekend price moves.


## (B) Volume floor on perp bars

Drop bars below `volume_base` thresholds and recompute path coverage on the survivors. Tests whether thin-liquidity prints drive the violations. `survival_share` = mean fraction of the weekend-window bars that survive the filter.

|   vol_floor |    tau |        n |   endpoint_cov |   path_cov |   n_bars_mean |   survival_share |   gap_pp |
|------------:|-------:|---------:|---------------:|-----------:|--------------:|-----------------:|---------:|
|      0.0000 | 0.6800 | 118.0000 |         0.6441 |     0.3475 |     3990.9407 |          20.4664 |  29.6610 |
|      0.0000 | 0.8500 | 118.0000 |         0.8644 |     0.5678 |     3990.9407 |          20.4664 |  29.6610 |
|      0.0000 | 0.9500 | 118.0000 |         0.9492 |     0.7881 |     3990.9407 |          20.4664 |  16.1017 |
|      0.0000 | 0.9900 | 118.0000 |         0.9915 |     0.9153 |     3990.9407 |          20.4664 |   7.6271 |
|      0.1000 | 0.6800 |  76.0000 |         0.6447 |     0.3816 |       11.4079 |           0.0585 |  26.3158 |
|      0.1000 | 0.8500 |  76.0000 |         0.8816 |     0.6316 |       11.4079 |           0.0585 |  25.0000 |
|      0.1000 | 0.9500 |  76.0000 |         0.9474 |     0.8553 |       11.4079 |           0.0585 |   9.2105 |
|      0.1000 | 0.9900 |  76.0000 |         0.9868 |     0.9342 |       11.4079 |           0.0585 |   5.2632 |
|      1.0000 | 0.6800 |  63.0000 |         0.6508 |     0.3968 |        8.6190 |           0.0442 |  25.3968 |
|      1.0000 | 0.8500 |  63.0000 |         0.8889 |     0.6349 |        8.6190 |           0.0442 |  25.3968 |
|      1.0000 | 0.9500 |  63.0000 |         0.9524 |     0.8571 |        8.6190 |           0.0442 |   9.5238 |
|      1.0000 | 0.9900 |  63.0000 |         1.0000 |     0.9206 |        8.6190 |           0.0442 |   7.9365 |
|     10.0000 | 0.6800 |  42.0000 |         0.6667 |     0.5000 |        4.0952 |           0.0210 |  16.6667 |
|     10.0000 | 0.8500 |  42.0000 |         0.8810 |     0.8095 |        4.0952 |           0.0210 |   7.1429 |
|     10.0000 | 0.9500 |  42.0000 |         0.9762 |     0.9524 |        4.0952 |           0.0210 |   2.3810 |
|     10.0000 | 0.9900 |  42.0000 |         1.0000 |     0.9762 |        4.0952 |           0.0210 |   2.3810 |


*Reading.* If `path_cov` rises substantially as `vol_floor` increases — say from 0.84 to 0.92 at vol_floor = 1.0 — then the headline gap is partly perp microstructure noise on thin bars. If `path_cov` is flat across thresholds, the gap is real and not a thin-liquidity artifact.


## (C) Sustained crossing (rolling median)

Replace the `any 1m bar` violation definition with a rolling median of the close. Most lending protocols TWAP the on-chain price before liquidating, so a 5–15 minute median is closer to the consumer-relevant trigger than a single tick.

|   sustain_window_min |    tau |        n |   endpoint_cov |   path_cov |   gap_pp |
|---------------------:|-------:|---------:|---------------:|-----------:|---------:|
|               1.0000 | 0.6800 | 118.0000 |         0.6441 |     0.3559 |  28.8136 |
|               1.0000 | 0.8500 | 118.0000 |         0.8644 |     0.5678 |  29.6610 |
|               1.0000 | 0.9500 | 118.0000 |         0.9492 |     0.7881 |  16.1017 |
|               1.0000 | 0.9900 | 118.0000 |         0.9915 |     0.9153 |   7.6271 |
|               5.0000 | 0.6800 | 118.0000 |         0.6441 |     0.3644 |  27.9661 |
|               5.0000 | 0.8500 | 118.0000 |         0.8644 |     0.5847 |  27.9661 |
|               5.0000 | 0.9500 | 118.0000 |         0.9492 |     0.7966 |  15.2542 |
|               5.0000 | 0.9900 | 118.0000 |         0.9915 |     0.9153 |   7.6271 |
|              15.0000 | 0.6800 | 118.0000 |         0.6441 |     0.3729 |  27.1186 |
|              15.0000 | 0.8500 | 118.0000 |         0.8644 |     0.5847 |  27.9661 |
|              15.0000 | 0.9500 | 118.0000 |         0.9492 |     0.8051 |  14.4068 |
|              15.0000 | 0.9900 | 118.0000 |         0.9915 |     0.9237 |   6.7797 |


*Reading.* The `sustain_window_min = 1` row reproduces the headline (single-bar definition). Higher windows test whether the gap is sustained drift or single-print noise. A drop from 16pp at win=1 to ~5pp at win=15 says most violations are transient prints; a flat profile says the gap is sustained.
