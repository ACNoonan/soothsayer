# One-sided lending commercial backtest

**Run date:** 2026-07-25  
**Status:** Internal gut check, not a protocol revenue claim.

## Question

If a lending protocol values xStock collateral at Soothsayer's one-sided
downside bound, how much borrowing capacity can it safely leave available
compared with a blanket freeze or a fixed haircut?

The experiment normalizes every observation to **$1 million of collateral at
Friday close** and applies the actual Kamino xStock max-LTV and liquidation
threshold for that reserve. A counterfactual maximum-size loan is unsafe when
its permitted debt exceeds the reserve's liquidation-threshold value at the
realized Monday open.

## Gut-check verdict

**The product clearly beats a blanket freeze and preserves the intended risk
level better than a static policy frozen before the test. It does not show a
large capital-efficiency advantage over a static haircut chosen with hindsight
to match the realised test risk.**

- At the current τ=0.85 default, the chronology-honest Friday policy permits
  about **$709,003**
  per $1m of SPY/QQQ collateral rather than the freeze policy's $0.
- Against the per-reserve fixed τ=0.85 policy selected on 2023–2024 and then
  frozen, Soothsayer gives up
  **$3,212**
  per $1m of Friday capacity (0.45%)
  but cuts the held-out lower-bound breach rate from
  **27.54% to
  16.67%** and records
  **0 versus
  3** endpoint-unsafe loans.
- At Monday pre-open, the same frozen comparison gives up
  **$2,218**
  per $1m while cutting bound breaches from
  **20.29% to
  10.87%**.
- If the static haircut is instead selected *after seeing 2025+* to match
  realised endpoint risk, the Friday τ=0.85 product adds only
  **$240**
  per $1m; its block-bootstrap interval
  [$-261,
  $686]
  crosses zero. At matched lower-bound coverage it adds
  **$1,153**
  (0.16%).
- At τ=0.95, the narrow-reserve product also loses
  **$2,763**
  per $1m to per-reserve fixed haircuts even when matching the bound's own
  breach rate.

The gut-check therefore supports a narrower commercial proposition:
**Soothsayer's value is maintaining a declared downside risk level through
distribution shift, not manufacturing large extra capacity relative to the
best static rule in hindsight.** The next evidence should price the avoided
risk drift on a real book and path-aware stress periods.

## Primary result — chronology-honest, Monday pre-open

Quantiles are fit before 2023, the global one-sided `c(τ)` schedule is tuned
on 2023–2024, and the following rows are evaluated only on untouched 2025+
weekends. The test contains
**69 weekends**.

| Scope          |    τ | Capacity / $1m   |   Unsafe n | Unsafe rate   | Mean shortfall / $1m   | Lower-bound breach   |   Mean buffer (bps) |
|:---------------|-----:|:-----------------|-----------:|:--------------|:-----------------------|:---------------------|--------------------:|
| narrow_spy_qqq | 0.68 | $711,899         |          0 | 0.00%         | $0                     | 28.99%               |                34.2 |
| narrow_spy_qqq | 0.85 | $708,080         |          0 | 0.00%         | $0                     | 10.87%               |                87.8 |
| narrow_spy_qqq | 0.95 | $700,895         |          0 | 0.00%         | $0                     | 2.17%                |               188.6 |
| narrow_spy_qqq | 0.99 | $686,694         |          0 | 0.00%         | $0                     | 0.00%                |               387.9 |
| all_8_xstocks  | 0.68 | $512,249         |          0 | 0.00%         | $0                     | 28.99%               |                75.4 |
| all_8_xstocks  | 0.85 | $506,811         |          0 | 0.00%         | $0                     | 11.59%               |               193.6 |
| all_8_xstocks  | 0.95 | $496,562         |          0 | 0.00%         | $0                     | 2.54%                |               416.5 |
| all_8_xstocks  | 0.99 | $476,291         |          0 | 0.00%         | $0                     | 0.18%                |               857.4 |

`Unsafe` is deliberately stricter and more commercial than a lower-bound
breach: it asks whether a loan originated at the maximum allowed LTV against
the conservative bound would already exceed the reserve's liquidation
threshold at Monday open.

## Primary comparator — fixed before the held-out test

The fixed policy is fit per reserve on 2023–2024 at the same labelled τ, frozen,
and evaluated untouched alongside Soothsayer on 2025+. This is the deployable
chronology-honest comparison. A negative capacity delta can be worthwhile when
the fixed policy misses its intended risk level, so read capacity and breach
columns together.

| Comparison                          | Scope          |    τ |   Mean fixed (bps) | Product capacity   | Fixed capacity   | Δ capacity   | Δ vs fixed   | 95% CI low   | 95% CI high   | Product breach   | Fixed breach   |   Product unsafe |   Fixed unsafe |
|:------------------------------------|:---------------|-----:|-------------------:|:-------------------|:-----------------|:-------------|:-------------|:-------------|:--------------|:-----------------|:---------------|-----------------:|---------------:|
| frozen_pretest_same_tau_per_reserve | narrow_spy_qqq | 0.68 |                 18 | $711,899           | $713,055         | $-1,156      | -0.16%       | $-1,380      | $-944         | 28.99%           | 33.33%         |                0 |              1 |
| frozen_pretest_same_tau_per_reserve | narrow_spy_qqq | 0.85 |                 57 | $708,080           | $710,299         | $-2,218      | -0.31%       | $-2,711      | $-1,778       | 10.87%           | 20.29%         |                0 |              0 |
| frozen_pretest_same_tau_per_reserve | narrow_spy_qqq | 0.95 |                131 | $700,895           | $705,013         | $-4,118      | -0.58%       | $-5,501      | $-2,906       | 2.17%            | 2.90%          |                0 |              0 |
| frozen_pretest_same_tau_per_reserve | narrow_spy_qqq | 0.99 |                385 | $686,694           | $686,933         | $-238        | -0.03%       | $-3,624      | $2,784        | 0.00%            | 0.00%          |                0 |              0 |
| frozen_pretest_same_tau_per_reserve | all_8_xstocks  | 0.68 |                 50 | $512,249           | $513,475         | $-1,225      | -0.24%       | $-1,570      | $-929         | 28.99%           | 32.07%         |                0 |              1 |
| frozen_pretest_same_tau_per_reserve | all_8_xstocks  | 0.85 |                126 | $506,811           | $509,800         | $-2,989      | -0.59%       | $-3,711      | $-2,365       | 11.59%           | 18.12%         |                0 |              0 |
| frozen_pretest_same_tau_per_reserve | all_8_xstocks  | 0.95 |                240 | $496,562           | $504,477         | $-7,915      | -1.57%       | $-9,924      | $-6,169       | 2.54%            | 6.88%          |                0 |              0 |
| frozen_pretest_same_tau_per_reserve | all_8_xstocks  | 0.99 |              1,076 | $476,291           | $468,906         | $7,385       | 1.57%        | $2,348       | $11,738       | 0.18%            | 0.00%          |                0 |              0 |

## Diagnostic ceiling — fixed haircut selected with hindsight

This second comparison allows the risk team to pick
the **smallest fixed haircut on a 25 bps grid separately for every reserve**,
then aggregates those choices. Unlike the primary comparator, it selects the
haircuts after seeing the test outcomes. It is an ex-post efficiency ceiling,
not a deployable backtest. It matches risk on one of two bases:

- `endpoint_safety`: no higher observed unsafe-loan rate and no larger mean
  shortfall after applying the reserve's additional max-LTV-to-liquidation
  cushion;
- `lower_bound_coverage`: no higher rate of the realised price falling below
  the bound itself, which tests the oracle primitive before the reserve cushion.

Positive Δ means the dynamic one-sided product permits more debt at matched
observed risk. Confidence intervals resample whole weekends.

| Comparison                       | Scope          |    τ |   Mean fixed (bps) | Product capacity   | Fixed capacity   | Δ capacity   | Δ vs fixed   | 95% CI low   | 95% CI high   | Product breach   | Fixed breach   |   Product unsafe |   Fixed unsafe |
|:---------------------------------|:---------------|-----:|-------------------:|:-------------------|:-----------------|:-------------|:-------------|:-------------|:--------------|:-----------------|:---------------|-----------------:|---------------:|
| endpoint_safety_per_reserve      | narrow_spy_qqq | 0.68 |                 25 | $711,899           | $712,587         | $-688        | -0.10%       | $-912        | $-476         | 28.99%           | 33.33%         |                0 |              0 |
| lower_bound_coverage_per_reserve | narrow_spy_qqq | 0.68 |                 50 | $711,899           | $710,764         | $1,135       | 0.16%        | $912         | $1,347        | 28.99%           | 21.74%         |                0 |              0 |
| endpoint_safety_per_reserve      | narrow_spy_qqq | 0.85 |                 25 | $708,080           | $712,587         | $-4,507      | -0.63%       | $-5,001      | $-4,065       | 10.87%           | 33.33%         |                0 |              0 |
| lower_bound_coverage_per_reserve | narrow_spy_qqq | 0.85 |                 88 | $708,080           | $708,104         | $-23         | -0.00%       | $-516        | $417          | 10.87%           | 10.14%         |                0 |              0 |
| endpoint_safety_per_reserve      | narrow_spy_qqq | 0.95 |                 25 | $700,895           | $712,587         | $-11,692     | -1.64%       | $-13,073     | $-10,474      | 2.17%            | 33.33%         |                0 |              0 |
| lower_bound_coverage_per_reserve | narrow_spy_qqq | 0.95 |                150 | $700,895           | $703,658         | $-2,763      | -0.39%       | $-4,145      | $-1,552       | 2.17%            | 2.17%          |                0 |              0 |
| endpoint_safety_per_reserve      | narrow_spy_qqq | 0.99 |                 25 | $686,694           | $712,587         | $-25,893     | -3.63%       | $-29,266     | $-22,864      | 0.00%            | 33.33%         |                0 |              0 |
| lower_bound_coverage_per_reserve | narrow_spy_qqq | 0.99 |                250 | $686,694           | $696,589         | $-9,895      | -1.42%       | $-13,276     | $-6,870       | 0.00%            | 0.00%          |                0 |              0 |
| endpoint_safety_per_reserve      | all_8_xstocks  | 0.68 |                  6 | $512,249           | $515,283         | $-3,033      | -0.59%       | $-3,377      | $-2,737       | 28.99%           | 43.66%         |                0 |              0 |
| lower_bound_coverage_per_reserve | all_8_xstocks  | 0.68 |                 75 | $512,249           | $511,908         | $341         | 0.07%        | $-3          | $637          | 28.99%           | 25.00%         |                0 |              0 |
| endpoint_safety_per_reserve      | all_8_xstocks  | 0.85 |                  6 | $506,811           | $515,283         | $-8,472      | -1.64%       | $-9,196      | $-7,858       | 11.59%           | 43.66%         |                0 |              0 |
| lower_bound_coverage_per_reserve | all_8_xstocks  | 0.85 |                172 | $506,811           | $507,778         | $-967        | -0.19%       | $-1,689      | $-341         | 11.59%           | 10.69%         |                0 |              0 |
| endpoint_safety_per_reserve      | all_8_xstocks  | 0.95 |                  6 | $496,562           | $515,283         | $-18,721     | -3.63%       | $-20,726     | $-16,966      | 2.54%            | 43.66%         |                0 |              0 |
| lower_bound_coverage_per_reserve | all_8_xstocks  | 0.95 |                394 | $496,562           | $498,098         | $-1,536      | -0.31%       | $-3,543      | $214          | 2.54%            | 2.36%          |                0 |              0 |
| endpoint_safety_per_reserve      | all_8_xstocks  | 0.99 |                  6 | $476,291           | $515,283         | $-38,992     | -7.57%       | $-44,010     | $-34,610      | 0.18%            | 43.66%         |                0 |              0 |
| lower_bound_coverage_per_reserve | all_8_xstocks  | 0.99 |                506 | $476,291           | $492,116         | $-15,825     | -3.22%       | $-20,854     | $-11,454      | 0.18%            | 0.18%          |                0 |              0 |

## Reserve detail at the product default, τ = 0.85

| Reserve   | Capacity / $1m   |   Unsafe n | Unsafe rate   | Mean shortfall / $1m   | Lower-bound breach   |   Mean buffer (bps) |
|:----------|:-----------------|-----------:|:--------------|:-----------------------|:---------------------|--------------------:|
| AAPL      | $393,906         |          0 | 0.00%         | $0                     | 7.25%                |               143.2 |
| GOOGL     | $591,797         |          0 | 0.00%         | $0                     | 11.59%               |               127.6 |
| HOOD      | $289,264         |          0 | 0.00%         | $0                     | 11.59%               |               348.8 |
| MSTR      | $291,581         |          0 | 0.00%         | $0                     | 14.49%               |               258.9 |
| NVDA      | $536,692         |          0 | 0.00%         | $0                     | 11.59%               |               232.9 |
| QQQ       | $692,473         |          0 | 0.00%         | $0                     | 10.14%               |                98.3 |
| SPY       | $723,688         |          0 | 0.00%         | $0                     | 11.59%               |                77.3 |
| TSLA      | $535,087         |          0 | 0.00%         | $0                     | 14.49%               |               262   |

## Evidence views and timing

- **Exact current product:** pre-2023 regime quantiles plus the current
  one-sided `c(τ)` schedule (0.68: 1.217, 0.85: 1.057, 0.95: 1.074, 0.99: 1.121), characterised on 2023+. Because
  those `c` values were selected using the same 2023+ outcomes, this view is
  descriptive and must not be called held out.
- **Chronology-honest product architecture:** the same pre-2023 quantiles,
  `c(τ)` tuned only on 2023–2024 (0.68: 1.309, 0.85: 1.142, 0.95: 1.182, 0.99: 1.245), tested from 2025 onward.
- **Monday pre-open:** uses the factor-adjusted point, which is available at
  that decision time.
- **Friday commitment:** uses Friday close plus a Friday-known buffer. The
  chronology-honest version is independently calibrated to Friday-to-Monday
  downside moves. The exact-current Friday view merely re-centres the current
  buffer and is diagnostic.

## What this answers

This backtest measures:

1. borrowing capacity made available per $1 million of collateral;
2. endpoint liquidation-threshold crossings for maximum-size new loans;
3. shortfall severity when a crossing occurs;
4. whether dynamic symbol/regime buffers dominate a fixed haircut at matched
   observed risk.

It does **not** measure realized borrower demand, actual historical protocol
revenue, full-position health across multi-asset books, or intra-weekend
executable-path liquidations. Revenue columns in the CSV are capacity
scenarios at a 5% annual borrow rate, not forecasts.

## Data and reproducibility

- Historical underlier panel: `/Users/adamnoonan/Documents/soothsayer/data/processed/v1b_panel.parquet`
- Reserve configuration: `/Users/adamnoonan/Documents/soothsayer/data/processed/kamino_xstocks_snapshot_20260427.json`
- Current one-sided sidecar: `/Users/adamnoonan/Documents/soothsayer/data/processed/lwc_onesided_artefact_v1.json`
- Runner: `scripts/run_lending_commercial_backtest.py`
- Full summary: `/Users/adamnoonan/Documents/soothsayer/reports/tables/lending_commercial_backtest_summary.csv`
- Per-reserve detail: `/Users/adamnoonan/Documents/soothsayer/reports/tables/lending_commercial_backtest_by_reserve.csv`
- Matched fixed-haircut frontier: `/Users/adamnoonan/Documents/soothsayer/reports/tables/lending_commercial_matched_fixed.csv`

All inputs are local parquet/JSON artefacts. No upstream data is fetched.
