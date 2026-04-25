# V1b — Macro-event regressor ablation

**Question.** Does adding a FRED-derived `macro_event_next_week` flag (FOMC + CPI + NFP) to the F1_emp_regime log-log model close the shock-tertile coverage gap documented in §9.2 of the paper (~80% realized at τ=0.95 in the highest-realized-z-score tertile)?

**Calendar.** 324 macro events 2014–2026 (31 FOMC decision dates from DFEDTARU, 146 CPI releases, 147 NFP releases). 48% of weekends have a macro event in the following week — the flag is *frequent*; if shock weekends concentrate within this 48%, we'd expect to see differential coverage improvement.

## Pooled — τ = 0.95

| variant       | scope   |   claimed |    n |   realized |   sharpness_bps |
|:--------------|:--------|----------:|-----:|-----------:|----------------:|
| M0_deployed   | pooled  |     0.950 | 5486 |      0.923 |         253.726 |
| M1_with_macro | pooled  |     0.950 | 5486 |      0.921 |         254.138 |
| M2_macro_swap | pooled  |     0.950 | 5486 |      0.922 |         254.023 |

## Shock-tertile (post-hoc realised-move tertile)

| variant       | scope          |   claimed |    n |   realized |   sharpness_bps |
|:--------------|:---------------|----------:|-----:|-----------:|----------------:|
| M0_deployed   | realized_shock |     0.680 | 1855 |      0.322 |         102.462 |
| M1_with_macro | realized_shock |     0.680 | 1855 |      0.319 |         103.164 |
| M2_macro_swap | realized_shock |     0.680 | 1855 |      0.318 |         103.098 |
| M0_deployed   | realized_shock |     0.850 | 1855 |      0.584 |         165.521 |
| M1_with_macro | realized_shock |     0.850 | 1855 |      0.579 |         166.356 |
| M2_macro_swap | realized_shock |     0.850 | 1855 |      0.578 |         166.230 |
| M0_deployed   | realized_shock |     0.950 | 1855 |      0.803 |         264.404 |
| M1_with_macro | realized_shock |     0.950 | 1855 |      0.796 |         264.586 |
| M2_macro_swap | realized_shock |     0.950 | 1855 |      0.796 |         264.903 |
| M0_deployed   | realized_shock |     0.990 | 1855 |      0.921 |         420.110 |
| M1_with_macro | realized_shock |     0.990 | 1855 |      0.922 |         419.048 |
| M2_macro_swap | realized_shock |     0.990 | 1855 |      0.923 |         417.747 |

## Reading

- M0 (deployed) is the baseline. M1 adds the macro flag, M2 swaps earnings for macro.
- A meaningful improvement is +1pp realized in shock-tertile at τ=0.95 with comparable sharpness — a half-pp shift is within bootstrap noise at this n.
- If M1 ≈ M0 (no detectable lift), shock weekends are *not* macro-event-driven. This is itself a paper-relevant finding: §9.2 stays as 'structural ceiling, mechanism unidentified.' If M1 > M0 with CI excluding zero, deploy M1 and update §9.2 to acknowledge the partial fix.

Raw: `reports/tables/v1b_macro_ablation.csv`, `reports/tables/v1b_macro_ablation_shock.csv`, `data/processed/v1b_macro_calendar.parquet`.