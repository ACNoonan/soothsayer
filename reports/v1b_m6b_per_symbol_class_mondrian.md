# V3 lead 2 — M6b per-symbol / per-class Mondrian

**Question.** W2 (`reports/v1b_density_rejection_localization.md`) found that single-symbol Berkowitz var_z under M5 ranges from 0.30 (SPY) to 2.10 (MSTR) — per-regime quantile pooling masks heterogeneous per-symbol residual scale. Does Mondrian(symbol) or Mondrian(class) tighten the band overall, or just re-allocate width within the universe?

## Variants

| method | cell axis | n_cells × n_anchors |
|---|---|---|
| M5 (baseline) | regime | 3 × 4 = 12 |
| M6b1 | symbol | 10 × 4 = 40 |
| M6b2 | symbol_class | 6 × 4 = 24 |
| M6b3 | symbol_class × regime | 18 × 4 = 72 (regime-fallback for cells with n<30) |

Symbol-class mapping: {'SPY': 'equity_index', 'QQQ': 'equity_index', 'AAPL': 'equity_meta', 'GOOGL': 'equity_meta', 'NVDA': 'equity_highbeta', 'TSLA': 'equity_highbeta', 'MSTR': 'equity_highbeta', 'HOOD': 'equity_recent', 'GLD': 'gold', 'TLT': 'bond'}.

## Pooled OOS coverage and width at headline τ

| method              |   target |   n_oos |   realised |   bump_c |   half_width_bps_mean |
|:--------------------|---------:|--------:|-----------:|---------:|----------------------:|
| M5_regime           |    0.680 |    1730 |      0.680 |    1.498 |               110.170 |
| M6b1_symbol         |    0.680 |    1730 |      0.680 |    1.353 |               118.214 |
| M6b2_symbol_class   |    0.680 |    1730 |      0.680 |    1.324 |               116.067 |
| M6b3_class_x_regime |    0.680 |    1730 |      0.680 |    1.350 |               116.992 |
| M5_regime           |    0.850 |    1730 |      0.850 |    1.455 |               200.977 |
| M6b1_symbol         |    0.850 |    1730 |      0.851 |    1.208 |               184.649 |
| M6b2_symbol_class   |    0.850 |    1730 |      0.850 |    1.207 |               185.315 |
| M6b3_class_x_regime |    0.850 |    1730 |      0.850 |    1.280 |               195.215 |
| M5_regime           |    0.950 |    1730 |      0.950 |    1.300 |               354.513 |
| M6b1_symbol         |    0.950 |    1730 |      0.950 |    1.048 |               298.836 |
| M6b2_symbol_class   |    0.950 |    1730 |      0.950 |    1.049 |               303.719 |
| M6b3_class_x_regime |    0.950 |    1730 |      0.950 |    1.142 |               319.515 |
| M5_regime           |    0.990 |    1730 |      0.990 |    1.076 |               677.454 |
| M6b1_symbol         |    0.990 |    1730 |      0.990 |    1.085 |               718.215 |
| M6b2_symbol_class   |    0.990 |    1730 |      0.990 |    1.100 |               663.933 |
| M6b3_class_x_regime |    0.990 |    1730 |      0.990 |    1.154 |               673.390 |

## Width vs M5 baseline at matched coverage

|   target | method              |   m5_realised |   m5_half_width_bps |   method_realised |   method_half_width_bps |   width_change_pct |
|---------:|:--------------------|--------------:|--------------------:|------------------:|------------------------:|-------------------:|
|    0.680 | M6b1_symbol         |         0.680 |             110.170 |             0.680 |                 118.214 |              0.073 |
|    0.680 | M6b2_symbol_class   |         0.680 |             110.170 |             0.680 |                 116.067 |              0.054 |
|    0.680 | M6b3_class_x_regime |         0.680 |             110.170 |             0.680 |                 116.992 |              0.062 |
|    0.850 | M6b1_symbol         |         0.850 |             200.977 |             0.851 |                 184.649 |             -0.081 |
|    0.850 | M6b2_symbol_class   |         0.850 |             200.977 |             0.850 |                 185.315 |             -0.078 |
|    0.850 | M6b3_class_x_regime |         0.850 |             200.977 |             0.850 |                 195.215 |             -0.029 |
|    0.950 | M6b1_symbol         |         0.950 |             354.513 |             0.950 |                 298.836 |             -0.157 |
|    0.950 | M6b2_symbol_class   |         0.950 |             354.513 |             0.950 |                 303.719 |             -0.143 |
|    0.950 | M6b3_class_x_regime |         0.950 |             354.513 |             0.950 |                 319.515 |             -0.099 |
|    0.990 | M6b1_symbol         |         0.990 |             677.454 |             0.990 |                 718.215 |              0.060 |
|    0.990 | M6b2_symbol_class   |         0.990 |             677.454 |             0.990 |                 663.933 |             -0.020 |
|    0.990 | M6b3_class_x_regime |         0.990 |             677.454 |             0.990 |                 673.390 |             -0.006 |

## Per-class breakdown at τ=0.95

Where M5's per-regime pooling re-allocates width: per-class M6b should tighten wide-PIT classes (equity_index, bond, gold) and widen narrow-PIT classes (equity_highbeta, equity_recent).

| symbol_class    | method              |   target |   n_oos |   realised |   half_width_bps_mean |
|:----------------|:--------------------|---------:|--------:|-----------:|----------------------:|
| bond            | M5_regime           |    0.950 |     173 |      1.000 |              1363.511 |
| bond            | M6b1_symbol         |    0.950 |     173 |      1.000 |               659.968 |
| bond            | M6b2_symbol_class   |    0.950 |     173 |      1.000 |               659.968 |
| bond            | M6b3_class_x_regime |    0.950 |     173 |      1.000 |               657.948 |
| equity_highbeta | M5_regime           |    0.950 |     519 |      0.994 |              1363.511 |
| equity_highbeta | M6b1_symbol         |    0.950 |     519 |      1.000 |              2219.563 |
| equity_highbeta | M6b2_symbol_class   |    0.950 |     519 |      1.000 |              2257.009 |
| equity_highbeta | M6b3_class_x_regime |    0.950 |     519 |      1.000 |              2229.199 |
| equity_index    | M5_regime           |    0.950 |     346 |      1.000 |              1363.511 |
| equity_index    | M6b1_symbol         |    0.950 |     346 |      1.000 |               819.086 |
| equity_index    | M6b2_symbol_class   |    0.950 |     346 |      1.000 |               843.478 |
| equity_index    | M6b3_class_x_regime |    0.950 |     346 |      1.000 |               862.122 |
| equity_meta     | M5_regime           |    0.950 |     346 |      1.000 |              1363.511 |
| equity_meta     | M6b1_symbol         |    0.950 |     346 |      1.000 |              1129.667 |
| equity_meta     | M6b2_symbol_class   |    0.950 |     346 |      1.000 |              1158.674 |
| equity_meta     | M6b3_class_x_regime |    0.950 |     346 |      1.000 |              1172.227 |
| equity_recent   | M5_regime           |    0.950 |     173 |      1.000 |              1363.511 |
| equity_recent   | M6b1_symbol         |    0.950 |     173 |      1.000 |              2314.807 |
| equity_recent   | M6b2_symbol_class   |    0.950 |     173 |      1.000 |              2314.807 |
| equity_recent   | M6b3_class_x_regime |    0.950 |     173 |      1.000 |              1851.909 |
| gold            | M5_regime           |    0.950 |     173 |      1.000 |              1363.511 |
| gold            | M6b1_symbol         |    0.950 |     173 |      1.000 |               726.497 |
| gold            | M6b2_symbol_class   |    0.950 |     173 |      1.000 |               726.497 |
| gold            | M6b3_class_x_regime |    0.950 |     173 |      1.000 |               723.138 |

## Reading

Read the **width vs M5** table for the pooled effect. If the headline width number falls under M6b1 or M6b2 at τ=0.95 with realised ≥ 0.95, that's a v3-lead-2 win. If it doesn't fall pooled but the per-class breakdown shows the expected tighten/widen pattern, M6b is a re-allocation (not a Pareto improvement) — useful for protocol-class-specific calibration claims (Paper 3 §) but not a headline width upgrade.

## Decision criteria

- **Adopt** if pooled half-width at τ=0.95 falls ≥ 5% under M6b1 or M6b2 with realised ≥ 0.95 and Kupiec p_uc ≥ 0.05; recommend the cleanest of the four as v3 deployment target.
- **Disclose-not-deploy** if width is comparable to M5 but per-class allocation matches the var_z heterogeneity W2 found; useful for Paper 3 protocol-class arguments.
- **Reject** if width is comparable and per-class allocation doesn't match var_z heterogeneity.

Reproducible via `scripts/run_m6b_per_symbol_class_mondrian.py`. Source data: `reports/tables/v1b_m6b_per_symbol_class_oos.csv`, `reports/tables/v1b_m6b_per_cell_quantiles.csv`.