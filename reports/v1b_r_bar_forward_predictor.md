# V1b — r̄_w forward predictor prototype (W8)

**Question.** M6a's upper-bound width gain (-13% at τ=0.95 OOS, see `reports/v1b_m6a_common_mode_partial_out.md`) uses the Monday-derived leave-one-out weekend-mean residual r̄_w^(−i). To deploy the AMM-track (`M6_REFACTOR.md` Phase B), the Oracle needs a Friday-observable predictor of r̄_w with R²(forward) ≥ 0.40 against realised r̄_w on a TRAIN/OOS holdout. This script tests whether such a predictor is achievable on currently-available Friday-close state.

**Sample.** 458 train weekends (pre-2023-01-01) + 173 OOS weekends (2023-01-01+). Dependent variable r̄_w = panel-mean over symbols of the M6a signed residual r_i = (mon_open − point_fa) / fri_close.

## Models tested

| ID | Features | Comment |
|---|---|---|
| M0_ar1 | `r_bar_lag1` | Last-weekend autoregressive baseline. |
| M1_vol_{ols, ridge1} | `vix, gvz, move, Δvix, Δgvz, Δmove` | Macro-vol level + week-Δ. |
| M2_full_{ols, ridge1, ridge10} | M0 ∪ M1 ∪ panel cross-section ∪ calendar ∪ regime-mix | All Friday-observable features. |

## Results

| model           |   α (ridge) |   n_features |   R²(train) |   R²(OOS) |
|:----------------|------------:|-------------:|------------:|----------:|
| M0_ar1          |      0.0000 |            1 |      0.0029 |    0.0053 |
| M1_vol_ols      |      0.0000 |            6 |      0.0785 |   -0.0603 |
| M1_vol_ridge1   |      1.0000 |            6 |      0.0785 |   -0.0597 |
| M2_full_ols     |      0.0000 |           13 |      0.1124 |   -0.0569 |
| M2_full_ridge1  |      1.0000 |           13 |      0.1123 |   -0.0580 |
| M2_full_ridge10 |     10.0000 |           13 |      0.1112 |   -0.0495 |

**Best model (by R²(OOS)):** `M0_ar1` (α=0.0). R²(train) = 0.0029; R²(OOS) = 0.0053.

### Best-model standardised coefficients

| feature    |   coef (standardized) |   feature_mean_train |   feature_std_train |
|:-----------|----------------------:|---------------------:|--------------------:|
| r_bar_lag1 |               -0.0005 |               0.0004 |              0.0100 |

## Sanity check — cross-sectional within-weekend lag-1 ρ

If the predictor is doing real work, partialling out `β·r̄_w_hat` (β=1 for the upper-bound diagnostic) should drop the cross-sectional lag-1 ρ from the W2-baseline 0.41 toward zero. Under a perfectly linear model with no idiosyncratic component, the post-partial-out ρ should equal `(1 − R²) · ρ_raw`.

| metric                    |   OOS lag-1 ρ within weekend |   n pairs |
|:--------------------------|-----------------------------:|----------:|
| raw r_i                   |                       0.4147 |      1557 |
| after r̄_w_hat partial-out |                       0.4134 |      1557 |

Expected ρ under a perfect linear model with this R²: `(1 − 0.005) · 0.415 = 0.4125`.

## Decision

**REJECT** — gate at R²(OOS) ≥ 0.40; defer threshold at 0.20.

R²(OOS) = 0.005 < 0.20. **Friday-close-only signal is too weak to support M6a deployment.** AMM-track shipping is parked. The negative result is informative: the M6a upper-bound width gain (-13% at τ=0.95) is *not* available with currently-observable Friday-close state. Either a Sunday-Globex republish architecture or a future on-chain xStock signal (V3.1 F_tok) is required. Log the result in `methodology_history.md`; revisit when scryer adds Sunday-evening futures snapshots or when V5 tape accumulates.

## What's *not* in the predictor

Three feature classes were left out by design and remain candidates for a follow-up if this predictor lands in DEFER:

1. **Sunday-Globex futures returns.** ES/NQ reopen Sunday 18:00 ET; the gap to Monday cash open is a strong predictor of r̄_w but is not Friday-close-observable. A republish-at-Sunday architecture would capture this; scryer needs a Sunday-evening futures snapshot fetcher.
2. **Sector rotation indicators.** XLK/XLF/XLE/etc. relative-strength change Friday close vs prior week. Plausibly Friday-observable from Yahoo daily ETF bars; not currently in `v1b_panel.parquet` but ingestible from `yahoo/equities_daily/v1` directly.
3. **On-chain xStock cross-section signal.** The cross-sectional mean of weekend xStock drift on `soothsayer_v5/tape` is a near-perfect proxy for r̄_w by construction. Today (~30 weekends) is too small; Q3–Q4 2026 ETA per V3.1 F_tok gate.

## Sources & reproducibility

- Input: `data/processed/v1b_panel.parquet`
- Output JSON: `data/processed/r_bar_predictor_v1.json`
- Reproducible via `scripts/run_r_bar_forward_predictor.py`

Run on 2026-05-03.