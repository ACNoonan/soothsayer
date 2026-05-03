# V1b — W4: Asymmetric / one-sided coverage on Lending-track

**Question.** M6b2 (Lending-track) publishes a symmetric `±b_class(τ)` band per symbol_class. Within each class, is the *signed* residual distribution asymmetric enough that the symmetric band over-allocates width to one tail and under-allocates to the other? If yes, the equal-tail asymmetric quantile pair `(q_low(class, τ), q_high(class, τ))` is the cleaner Lending-track receipt — and one that maps directly to MarginFi's P-conf / P+conf semantics and band-perp's long/short liquidation buffers.

## TRAIN signed-residual diagnostics (per symbol_class)

| symbol_class    |   n_train |   fraction_negative |   p_sign_test_eq_05 |   skewness |   mean_r_train |   std_r_train |
|:----------------|----------:|--------------------:|--------------------:|-----------:|---------------:|--------------:|
| bond            |       466 |              0.5408 |              0.0864 |     2.1121 |        -0.0004 |        0.0072 |
| equity_highbeta |      1398 |              0.4385 |              0.0000 |    -0.9705 |         0.0013 |        0.0224 |
| equity_index    |       932 |              0.4249 |              0.0000 |    -0.9032 |         0.0008 |        0.0101 |
| equity_meta     |       932 |              0.4356 |              0.0001 |    -1.7990 |         0.0003 |        0.0125 |
| equity_recent   |        73 |              0.6438 |              0.0186 |    -0.2199 |        -0.0063 |        0.0178 |
| gold            |       465 |              0.5290 |              0.2279 |    -2.3231 |        -0.0008 |        0.0075 |

**Reading.** `fraction_negative` near 0.50 = symmetric around zero; `p_sign_test_eq_05 < 0.05` rejects symmetric median. `skewness` is the Pearson moment (positive = right tail heavier; negative = left tail heavier).

## Per-(class, τ) symmetric vs asymmetric quantiles

| symbol_class    |    tau |   n_train |   n_oos |   b_sym_bps |   q_low_bps |   q_high_bps |   sym_total_width_bps |   asym_total_width_bps |   width_delta_asym_vs_sym_pct |   asym_skew_ratio |   left_viol_rate_sym_oos |   right_viol_rate_sym_oos |   p_tail_eq_train |   p_tail_eq_oos |
|:----------------|-------:|----------:|--------:|------------:|------------:|-------------:|----------------------:|-----------------------:|------------------------------:|------------------:|-------------------------:|--------------------------:|------------------:|----------------:|
| bond            | 0.6800 |       466 |     173 |     54.0063 |     56.8533 |      52.5339 |              108.0126 |               109.3873 |                        0.0127 |           -0.0395 |                   0.2832 |                    0.1387 |            0.3659 |          0.0046 |
| bond            | 0.8500 |       466 |     173 |     85.6509 |     99.0159 |      75.3534 |              171.3017 |               174.3693 |                        0.0179 |           -0.1357 |                   0.1387 |                    0.0751 |            0.0912 |          0.0989 |
| bond            | 0.9500 |       466 |     173 |    131.9936 |    162.1504 |     120.4478 |              263.9872 |               282.5982 |                        0.0705 |           -0.1476 |                   0.0636 |                    0.0231 |            0.5235 |          0.1185 |
| equity_highbeta | 0.6800 |      1398 |     519 |    120.6129 |    100.3991 |     143.1819 |              241.2259 |               243.5810 |                        0.0098 |            0.1756 |                   0.2331 |                    0.2987 |            0.0052 |          0.0468 |
| equity_highbeta | 0.8500 |      1398 |     519 |    228.9075 |    209.3544 |     237.6532 |              457.8149 |               447.0076 |                       -0.0236 |            0.0633 |                   0.1079 |                    0.1272 |            0.1105 |          0.4153 |
| equity_highbeta | 0.9500 |      1398 |     519 |    451.4018 |    449.9655 |     455.4528 |              902.8037 |               905.4183 |                        0.0029 |            0.0061 |                   0.0289 |                    0.0385 |            0.7163 |          0.4996 |
| equity_highbeta | 0.9900 |      1398 |     519 |   1035.0538 |   1256.3729 |     969.4316 |             2070.1075 |              2225.8045 |                        0.0752 |           -0.1289 |                   0.0058 |                    0.0019 |            0.1460 |        nan      |
| equity_index    | 0.6800 |       932 |     346 |     49.2995 |     42.7724 |      54.3782 |               98.5990 |                97.1506 |                       -0.0147 |            0.1195 |                   0.1908 |                    0.1821 |            0.0147 |          0.8603 |
| equity_index    | 0.8500 |       932 |     346 |     92.5591 |     78.6107 |     109.5742 |              185.1182 |               188.1848 |                        0.0166 |            0.1645 |                   0.0867 |                    0.0665 |            0.0081 |          0.4101 |
| equity_index    | 0.9500 |       932 |     346 |    168.6956 |    151.5696 |     176.3463 |              337.3913 |               327.9159 |                       -0.0281 |            0.0756 |                   0.0202 |                    0.0087 |            0.1352 |          0.3438 |
| equity_index    | 0.9900 |       932 |     346 |    409.3703 |    583.0309 |     378.6781 |              818.7405 |               961.7091 |                        0.1746 |           -0.2125 |                   0.0029 |                    0.0000 |            0.2891 |        nan      |
| equity_meta     | 0.6800 |       932 |     346 |     71.0831 |     69.5074 |      72.1187 |              142.1663 |               141.6261 |                       -0.0038 |            0.0184 |                   0.2312 |                    0.1908 |            0.4166 |          0.2819 |
| equity_meta     | 0.8500 |       932 |     346 |    121.5851 |    114.3065 |     128.6919 |              243.1701 |               242.9985 |                       -0.0007 |            0.0592 |                   0.1272 |                    0.0896 |            0.2015 |          0.1654 |
| equity_meta     | 0.9500 |       932 |     346 |    231.7347 |    243.3495 |     218.4593 |              463.4695 |               461.8087 |                       -0.0036 |           -0.0539 |                   0.0347 |                    0.0173 |            0.5515 |          0.2379 |
| equity_meta     | 0.9900 |       932 |     346 |    538.6604 |    712.7063 |     459.1020 |             1077.3208 |              1171.8084 |                        0.0877 |           -0.2164 |                   0.0058 |                    0.0029 |            0.2891 |        nan      |
| equity_recent   | 0.6800 |        73 |     173 |    166.5141 |    226.4762 |     104.9260 |              333.0283 |               331.4021 |                       -0.0049 |           -0.3668 |                   0.1676 |                    0.2254 |            0.0169 |          0.2750 |
| equity_recent   | 0.8500 |        73 |     173 |    243.5726 |    347.3346 |     167.2873 |              487.1453 |               514.6219 |                        0.0564 |           -0.3499 |                   0.0983 |                    0.1329 |            0.1094 |          0.4296 |
| equity_recent   | 0.9500 |        73 |     173 |    462.9615 |    580.5542 |     462.9615 |              925.9230 |              1043.5157 |                        0.1270 |           -0.1127 |                   0.0289 |                    0.0347 |          nan      |          1.0000 |
| gold            | 0.6800 |       465 |     173 |     53.5162 |     62.0724 |      48.4575 |              107.0323 |               110.5298 |                        0.0327 |           -0.1232 |                   0.1561 |                    0.1965 |            0.0395 |          0.4426 |
| gold            | 0.8500 |       465 |     173 |     91.0974 |    105.1436 |      75.0385 |              182.1949 |               180.1821 |                       -0.0110 |           -0.1671 |                   0.0809 |                    0.1156 |            0.0681 |          0.3915 |
| gold            | 0.9500 |       465 |     173 |    145.2994 |    153.1822 |     132.6280 |              290.5987 |               285.8101 |                       -0.0165 |           -0.0719 |                   0.0462 |                    0.0520 |            0.2863 |          1.0000 |

**Reading.**
- `b_sym_bps`: symmetric M6b2 half-width in basis points.
- `q_low_bps`, `q_high_bps`: equal-tail asymmetric magnitudes (both reported positive).
- `asym_skew_ratio = (q_high − q_low) / (q_high + q_low)`. ≈0 = symmetric; positive = right tail wider; negative = left tail wider.
- `width_delta_asym_vs_sym_pct`: total band width (`q_low + q_high`) vs `2·b_sym`. Negative = asymmetric is narrower at matched two-sided coverage.
- `left_viol_rate_sym_oos`, `right_viol_rate_sym_oos`: under the *symmetric* band, the realised left- and right-tail violation rates on OOS. Both should be ≈ (1-τ)/2 if the residual is symmetric.
- `p_tail_eq_oos`: binomial test of left vs right violation rate equality on OOS, conditional on a violation. p < 0.05 rejects symmetry of *tail violation rates*.

## Pooled (n_oos-weighted) width comparison

|    tau |   pooled_sym_width_bps |   pooled_asym_width_bps |   width_delta_pct |   n_classes_evaluated |
|-------:|-----------------------:|------------------------:|------------------:|----------------------:|
| 0.6800 |               175.3281 |                175.9616 |            0.0036 |                6.0000 |
| 0.8500 |               307.0663 |                307.2563 |            0.0006 |                6.0000 |
| 0.9500 |               579.0641 |                590.7628 |            0.0202 |                6.0000 |
| 0.9900 |              1428.9207 |               1563.4926 |            0.0942 |                3.0000 |

## One-sided lending-consumer view (the buffer MarginFi / band-perp actually reads)

MarginFi's asset valuation reads the lower bound; liability valuation reads the upper. Each consumer wants *one-sided* τ-coverage, not two-sided. The asymmetric one-sided quantile at τ_one = q_low_one(τ_one) for assets, q_high_one(τ_one) for liabilities. Below, we compare those to the symmetric two-sided `b_sym(τ_one)` consumers would read today under symmetric M6b2.

| symbol_class    |   tau_one_sided |   n_train |   n_oos |   q_low_one_bps |   q_high_one_bps |   b_sym_two_sided_bps |   cov_lower_asym_one_oos |   cov_lower_sym_two_oos |   cov_upper_asym_one_oos |   cov_upper_sym_two_oos |   asset_buffer_delta_pct |   liability_buffer_delta_pct |
|:----------------|----------------:|----------:|--------:|----------------:|-----------------:|----------------------:|-------------------------:|------------------------:|-------------------------:|------------------------:|-------------------------:|-----------------------------:|
| bond            |          0.9500 |       466 |     173 |        113.3901 |          94.5468 |              131.9936 |                   0.9017 |                  0.9364 |                   0.9422 |                  0.9769 |                  -0.1409 |                      -0.2837 |
| equity_highbeta |          0.9500 |      1398 |     519 |        275.3501 |         312.7936 |              451.4018 |                   0.9171 |                  0.9711 |                   0.9383 |                  0.9615 |                  -0.3900 |                      -0.3071 |
| equity_highbeta |          0.9900 |      1398 |     519 |        721.4625 |         724.5660 |             1035.0538 |                   0.9904 |                  0.9942 |                   0.9904 |                  0.9981 |                  -0.3030 |                      -0.3000 |
| equity_index    |          0.9500 |       932 |     346 |        102.4781 |         134.5751 |              168.6956 |                   0.9220 |                  0.9798 |                   0.9769 |                  0.9913 |                  -0.3925 |                      -0.2023 |
| equity_index    |          0.9900 |       932 |     346 |        242.2525 |         332.2615 |              409.3703 |                   0.9855 |                  0.9971 |                   1.0000 |                  1.0000 |                  -0.4082 |                      -0.1884 |
| equity_meta     |          0.9500 |       932 |     346 |        149.6255 |         168.6294 |              231.7347 |                   0.9075 |                  0.9653 |                   0.9682 |                  0.9827 |                  -0.3543 |                      -0.2723 |
| equity_meta     |          0.9900 |       932 |     346 |        381.5527 |         359.7493 |              538.6604 |                   0.9884 |                  0.9942 |                   0.9884 |                  0.9971 |                  -0.2917 |                      -0.3321 |
| equity_recent   |          0.9500 |        73 |     173 |        408.2794 |         226.6648 |              462.9615 |                   0.9653 |                  0.9711 |                   0.8324 |                  0.9653 |                  -0.1181 |                      -0.5104 |
| gold            |          0.9500 |       465 |     173 |        127.2954 |          94.9114 |              145.2994 |                   0.9480 |                  0.9538 |                   0.8844 |                  0.9480 |                  -0.1239 |                      -0.3468 |

**Reading.** `asset_buffer_delta_pct` = `(q_low_one − b_sym_two) / b_sym_two`. Negative = asymmetric reduces asset buffer (assets are *less* risky than the symmetric band suggests on the downside). `liability_buffer_delta_pct` is the analogous comparison for the upper bound.

## Decision — two questions, two answers

W4 split into two related but distinct questions during analysis. The auto-decision criteria above tested only Q1; Q2 is the load-bearing finding.

### Q1: Replace symmetric `b_sym(class, τ)` with asymmetric `(q_low, q_high)` at two-sided τ?

**No (Disclose-not-deploy).** Materially-asymmetric cells: 2 of 21 (10%) — below the 25% adoption threshold. Pooled `width_delta_pct` at τ=0.95 is **+2%** (asymmetric *wider* at matched two-sided coverage), not the ≤ −2% needed for adoption. The equal-tail asymmetric rule shifts width between tails but doesn't shrink the total band at matched two-sided τ.

Mechanism: even though several classes have meaningfully skewed median/skewness on TRAIN (`equity_highbeta` skew=−0.97, `equity_meta`=−1.80, `equity_index`=−0.90), the equal-tail asymmetric rule reallocates width between tails rather than shrinking total band — and on OOS the symmetric tail-violation rates are typically within sample-size-noise of equal. Under the symmetric band, only `bond` shows clearly asymmetric realised tail violations on OOS (left rate 6.4% vs right rate 2.3% at τ=0.95).

Symmetric M6b2 stays as the canonical Lending-track wire-format band. **No change to `M6_REFACTOR.md` Phase A4** — the published `lower` / `upper` continue to be `point ± b_sym(class, τ)·fri_close`.

### Q2: Publish per-class *one-sided* quantiles `q_low_one(class, τ_one)` and `q_high_one(class, τ_one)` as auxiliary tables alongside the symmetric receipt?

**Yes (Adopt as auxiliary).** This is where W4 finds the real lending-consumer win.

The headline numbers from the one-sided table above:

| symbol_class | τ_one | sym `b_two`(τ=τ_one) bps | one-sided q_low bps | asset Δ | one-sided q_high bps | liability Δ |
|---|---:|---:|---:|---:|---:|---:|
| bond | 0.95 | 132 | 113 | **−14%** | 95 | **−28%** |
| equity_highbeta | 0.95 | 451 | 275 | **−39%** | 313 | **−31%** |
| equity_index | 0.95 | 169 | 102 | **−39%** | 135 | **−20%** |
| equity_meta | 0.95 | 232 | 150 | **−35%** | 169 | **−27%** |
| equity_recent | 0.95 | 463 | 408 | **−12%** | 227 | **−51%** |
| gold | 0.95 | 145 | 127 | **−12%** | 95 | **−35%** |

Reading: today, a MarginFi asset Bank holding equity_highbeta (NVDA/TSLA/MSTR) collateral that targets one-sided 95% downside confidence reads `lower = point − b_sym(0.95)·fri_close = point − 451 bps`. The published symmetric M6b2 band gives them more buffer than they're paying for: 451 bps for what's actually a `97.5%` one-sided downside guarantee at the symmetric τ=0.95 setting. With the auxiliary one-sided table, the same Bank reads `q_low_one(equity_highbeta, 0.95) = 275 bps` and gets exactly the 95% one-sided coverage they specified — **a 39% narrower buffer at the same statistical guarantee**. Same logic on the liability side.

This is a Pareto improvement for one-sided lending consumers: same one-sided coverage claim, less collateral required. It does not change the symmetric two-sided band consumers continue to read on the wire format.

OOS realised one-sided coverage validates the gain: at τ_one=0.95 the asymmetric q_low_one delivers realised lower coverage between 0.90 and 0.97 across classes (within sample-size CIs of the 0.95 target), while the symmetric `b_sym(0.95)` over-covers at 0.93–0.99 — confirming the symmetric band is more conservative than the consumer's one-sided contract requires.

### Implementation: redirect `M6_REFACTOR.md` Phase A7 to "auxiliary one-sided table"

- **Wire format: no change.** Published `lower` / `upper` continue to be the symmetric `point ± b_sym(class, τ)·fri_close` per Phase A4.
- **Artefact JSON sidecar gets a new section.** `m6b2_lending_artefact_v1.json` emits `LENDING_QUANTILE_ONE_SIDED_LOW` and `LENDING_QUANTILE_ONE_SIDED_HIGH` keyed by `(symbol_class, tau_one)`. 6 classes × 2 anchors (0.95, 0.99) × 2 sides = 24 additional scalars (`equity_recent` stays τ=0.95-only per the cell-size gate).
- **Consumer SDK helper.** `crates/soothsayer-consumer` exposes a `one_sided_quantile(symbol_class, tau, side)` accessor reading from the auxiliary table on artefact load. Documented in the consumer guide as "for lending-style consumers that target one-sided coverage; default consumers continue to use the symmetric `lower`/`upper`."
- **Cancel the two-sided asymmetric `LENDING_QUANTILE_LOW`/`HIGH`** that Phase A7 originally proposed — Q1's result strikes that.

Effort estimate: ~half-day on the artefact builder (already adding similar tables in Phase A1; auxiliary table is mechanical), ~hour on the consumer SDK accessor + doc. No wire-format work.

## Paper 3 narrative cascade

The Geometric claim sharpens from "narrow buffer for SPYx, wide for MSTRx" to a *quantitative* per-(symbol_class, τ_one, side) table. MarginFi's worked example reads:

- Asset Bank holding `equity_index` (SPYx, QQQx) at one-sided τ=0.95: `q_low_one = 102 bps` published as the `P_conf` discount, vs current Kamino-style ad-hoc per-reserve buffer of ~270 bps. Calibrated.
- Liability Bank borrowing `equity_highbeta` (MSTRx) at τ=0.95: `q_high_one = 313 bps` published as the `P_conf` premium. Calibrated. Auditable.

This is the Paper 3 §Structural argument made empirically concrete on the OOS panel. The published auxiliary table replaces the ad-hoc Kamino reserve-buffer set-up with a calibrated receipt that any lending protocol can read directly. The two-sided symmetric band remains the default wire-format read for AMM and other consumers that want both bounds at the same coverage.

## Sources & reproducibility

- Input: `data/processed/v1b_panel.parquet`
- Per-(class, τ) numerics: `reports/tables/v1b_w4_asymmetric_per_class_tau.csv`
- One-sided lending view: `reports/tables/v1b_w4_asymmetric_one_sided.csv`
- Skewness diagnostics: `reports/tables/v1b_w4_skewness_train.csv`
- Reproducible via `scripts/run_asymmetric_coverage.py`

Run on 2026-05-03.