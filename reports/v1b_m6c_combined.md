# V3 leads — combined M6c (M6a + M6b2)

**Question.** v3 lead 1 (M6a, common-mode partial-out) and v3 lead 2 (M6b2, per-class Mondrian) modify orthogonal axes of the M5 protocol. Do their width gains stack?

## Variants

| method | score | cell | params |
|---|---|---|---|
| M5   | \|r\|         | regime         | 12 b + 4 c (16) |
| M6a  | \|r − β·r̄\| | regime         | 12 b + 4 c + 1 β (17) |
| M6b2 | \|r\|         | symbol_class   | 24 b + 4 c (28) |
| M6c  | \|r − β·r̄\| | symbol_class   | 24 b + 4 c + 1 β (29) |

Train β = 0.811 (R² ≈ 0.28; see `v1b_m6a_common_mode_fit.csv`).

## Pooled OOS half-width (bps) by method × τ

|   target |    M5 |   M6a |   M6b2 |   M6c |
|---------:|------:|------:|-------:|------:|
|      0.7 | 110.2 | 102.8 |  116.1 | 105.1 |
|      0.8 | 201.0 | 178.3 |  185.3 | 168.0 |
|      0.9 | 354.5 | 309.0 |  303.7 | 270.7 |
|      1.0 | 677.5 | 595.6 |  663.9 | 642.7 |

## Pooled OOS realised coverage by method × τ

|   target |    M5 |   M6a |   M6b2 |   M6c |
|---------:|------:|------:|-------:|------:|
|    0.680 | 0.680 | 0.681 |  0.680 | 0.680 |
|    0.850 | 0.850 | 0.850 |  0.850 | 0.850 |
|    0.950 | 0.950 | 0.950 |  0.950 | 0.950 |
|    0.990 | 0.990 | 0.990 |  0.990 | 0.990 |

## Stacking diagnostic

Gain = (M5_width − method_width) / M5_width. Stacking-efficiency = M6c gain / (M6a + M6b2 gains). Efficiency = 1.00 means perfectly additive; > 1.00 means super-additive (rare); < 1.00 means partial overlap (the two leads are not fully orthogonal).

|   target |   gain_m6a |   gain_m6b2 |   gain_m6c |   sum_individual |   stacking_efficiency |
|---------:|-----------:|------------:|-----------:|-----------------:|----------------------:|
|    0.680 |      0.067 |      -0.054 |      0.046 |            0.013 |                 3.552 |
|    0.850 |      0.113 |       0.078 |      0.164 |            0.191 |                 0.861 |
|    0.950 |      0.128 |       0.143 |      0.236 |            0.272 |                 0.870 |
|    0.990 |      0.121 |       0.020 |      0.051 |            0.141 |                 0.365 |

## Reading

Read the **stacking_efficiency** column. If ≈ 1.0, the two leads address fully orthogonal structure and combining them is straightforward. If < 1.0, M6a and M6b2 partly capture the same residual variance. If > 1.0, there's a synergy term (uncommon).

**Caveat — M6c is upper-bound.** Like M6a, M6c uses the leave-one-out weekend mean residual which is Monday-derived. Deployment requires a Friday-observable proxy for r̄_w. The deployable M6c gain scales with the forward predictor's R²(r̄_w | Friday-state).

Reproducible via `scripts/run_m6c_combined.py`. Source data: `reports/tables/v1b_m6c_combined_oos.csv`.