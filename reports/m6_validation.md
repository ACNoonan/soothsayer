# M6 (LWC) — Phase 2 validation evidence pack

**Generated:** 2026-05-04. Companion to `M6_REFACTOR.md` Phase 2; downstream of the Phase 1 LWC artefact build (`reports/v3_bakeoff.md` → `data/processed/lwc_artefact_v1.{parquet,json}`).

This document is the same shape as `reports/v1b_calibration.md`: it tabulates the deployed-vs-candidate methodology side-by-side, with every robustness check the paper currently runs against M5 re-run against M6, plus block-bootstrap CIs on the M5 → M6 deltas. Every CSV referenced is in `reports/tables/`. CSV pairs are named `v1b_robustness_*.csv` (M5) and `m6_lwc_robustness_*.csv` (M6).

## 1. Headline at τ = 0.95 (deployed schedules; OOS 2023+)

| | n | realised | half-width (bps) | Kupiec p | Christoffersen p | per-symbol Kupiec ≥ 0.05 |
|---|---:|---:|---:|---:|---:|---:|
| **M5 deployed** | 1,730 | 0.9503 | 354.6 | 0.956 | 0.921 | **2 / 10** |
| **M6 LWC deployed** | 1,730 | 0.9503 | 385.3 | 0.956 | 0.275 | **10 / 10** |
| Δ (LWC − M5) | — | +0.000 | +30.7 | — | −0.65 | +8 |

Bootstrap 95% CI on the deltas (1000 weekend-block resamples, seed 0; rows paired by `(symbol, fri_ts)`):

| τ | Δrealised | 95% CI (Δrealised) | Δhalf-width (bps) | 95% CI (Δhw) |
|---|---:|---:|---:|---:|
| 0.68 | −0.048 | [−0.075, −0.024] | −4.9 | [−10.5, +0.6] |
| 0.85 | −0.025 | [−0.046, −0.005] | −17.0 | [−26.5, −8.0] |
| **0.95** | **+0.000** | **[−0.014, +0.013]** | **+30.7** | **[+12.3, +49.0]** |
| 0.99 | +0.000 | [−0.006, +0.007] | +8.2 | [−25.7, +43.9] |

Source: `reports/tables/m5_vs_m6_bootstrap.csv` (`scripts/aggregate_m5_m6_bootstrap.py`).

**Reading.** M5 and M6 deliver indistinguishable pooled coverage at the deployed-target anchor τ=0.95 (CI on Δ straddles zero). M6 buys per-symbol calibration with a +30.7 bps width tax (CI excludes zero on the high side). At τ=0.85 M6 is *narrower* by 17 bps with CI excluding zero — σ̂-rescaling shifts width across the τ schedule. At τ=0.99 width is statistically neutral.

## 2. Per-symbol diagnostics (the §6.4.1 update — central new evidence)

CSVs: `v1b_robustness_per_symbol.csv` (M5) and `m6_lwc_robustness_per_symbol.csv` (M6).

### 2.1 Kupiec τ=0.95 by symbol

| symbol | M5 viol_rate | M5 Kupiec p | M6 viol_rate | M6 Kupiec p |
|---|---:|---:|---:|---:|
| AAPL  | 0.0058 | 0.001 | 0.0694 | 0.268 |
| GLD   | 0.0058 | 0.001 | 0.0578 | 0.646 |
| GOOGL | 0.0289 | 0.168 | 0.0462 | 0.819 |
| HOOD  | 0.1387 | 0.000 | 0.0405 | 0.552 |
| MSTR  | 0.1561 | 0.000 | 0.0520 | 0.903 |
| NVDA  | 0.0405 | 0.552 | 0.0578 | 0.646 |
| QQQ   | 0.0058 | 0.001 | 0.0289 | 0.168 |
| SPY   | 0.0000 | 0.000 | 0.0462 | 0.819 |
| TLT   | 0.0000 | 0.000 | 0.0462 | 0.819 |
| TSLA  | 0.1156 | 0.001 | 0.0520 | 0.903 |
| **Pass-rate (p ≥ 0.05)** | | **2 / 10** | | **10 / 10** |

The failure-mode is fully inverted. Under M5 the rejecting symbols are bimodal: SPY/QQQ/GLD/TLT/AAPL over-cover (viol rates 0–1.2%), MSTR/HOOD/TSLA under-cover (12–16%). Under M6 every symbol's violation rate sits within [0.029, 0.069] of nominal 0.05.

### 2.2 Per-symbol Berkowitz LR (the per-symbol density rejection)

| symbol | M5 LR | M6 LR | M5 var(z) | M6 var(z) |
|---|---:|---:|---:|---:|
| AAPL  |  40.9 |  6.7 | 0.464 | 0.757 |
| GLD   | 115.7 |  3.3 | 0.239 | 0.831 |
| GOOGL |  33.3 | 14.5 | 0.527 | 0.761 |
| HOOD  |  16.5 |  4.8 | 1.450 | 0.783 |
| MSTR  |  51.5 |  4.5 | 1.953 | 0.801 |
| NVDA  |   0.9 |  7.9 | 0.960 | 0.728 |
| QQQ   | 139.4 |  6.3 | 0.201 | 0.761 |
| SPY   | 223.7 | 10.8 | 0.113 | 0.704 |
| TLT   | 140.7 | 14.4 | 0.200 | 0.704 |
| TSLA  |  26.5 | 18.0 | 1.633 | 0.615 |
| **range** | **0.9 – 224** | **3.3 – 18.0** | | |

LWC compresses the per-symbol Berkowitz LR range from 0.9–224 (250×) to 3.3–18 (5.5×). The bimodality reported in §6.4.1 of Paper 1 collapses. Per-symbol var(z) under M5 is bimodal around the under-/over-cover split (0.11–0.24 for over-coverers, 1.45–1.95 for under-coverers); under M6 var(z) is in [0.62, 0.83] for every symbol — close to the calibrated 1.0 from below in every case.

## 3. Pooled OOS tables (§6.3.1 mirror)

Source: `reports/tables/m6_pooled_oos.csv` (`scripts/run_m6_pooled_oos_tables.py`).

| forecaster | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p | c-bump | δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M5  | 0.68 | 1730 | 0.7353 | 137.5 | 0.000 | 0.339 | 1.498 | 0.05 |
| M5  | 0.85 | 1730 | 0.8867 | 235.1 | 0.000 | 0.424 | 1.455 | 0.02 |
| M5  | 0.95 | 1730 | 0.9503 | 354.6 | 0.956 | 0.921 | 1.300 | 0.00 |
| M5  | 0.99 | 1730 | 0.9902 | 677.7 | 0.942 | 0.344 | 1.076 | 0.00 |
| LWC | 0.68 | 1730 | 0.6873 | 132.6 | 0.515 | 0.102 | 1.000 | 0.00 |
| LWC | 0.85 | 1730 | 0.8613 | 218.1 | 0.185 | 0.395 | 1.000 | 0.00 |
| LWC | 0.95 | 1730 | 0.9503 | 385.3 | 0.956 | 0.275 | 1.069 | 0.00 |
| LWC | 0.99 | 1730 | 0.9902 | 685.8 | 0.942 | 1.000 | 1.039 | 0.00 |

Note the deployed-schedule difference: M5 uses non-zero δ at low τ to clear a worst-split-deficit margin in the 6-split walk-forward; LWC's σ̂-rescaling tightens cross-split variance enough that δ=0 still clears nominal at every anchor. M5 over-covers by +5.5pp at τ=0.68 (`realised=0.735`, nominal 0.68); LWC sits at 0.687 — closer to nominal by design.

## 4. Realised-move tertile decomposition at τ=0.95 (the §6.3 calm/normal/shock table)

Source: `reports/tables/m6_realised_move_tertile.csv`.

| forecaster | tertile | n | realised | half-width (bps) | Kupiec p |
|---|---|---:|---:|---:|---:|
| M5  | calm   | 497 | 1.0000 | 340.2 | 0.000 (over) |
| M5  | normal | 601 | 0.9917 | 351.5 | 0.000 (over) |
| **M5**  | **shock**  | **632** | **0.8718** | **368.9** | **0.000 (under)** |
| LWC | calm   | 497 | 0.9960 | 367.5 | 0.000 (over) |
| LWC | normal | 601 | 0.9884 | 390.3 | 0.000 (over) |
| **LWC** | **shock**  | **632** | **0.8782** | **394.6** | **0.000 (under)** |

The §9.1 shock-tertile floor persists under M6 (87.82% vs M5's 87.18% — +0.64pp). LWC does not fix the shock-tertile rejection; that's the cross-sectional common-mode rejection axis the bake-off and `run_v1b_vol_tertile.py` already established as orthogonal to per-symbol scale (M6a-deployable territory, not M6 LWC).

## 5. Split-date sensitivity

CSVs: `v1b_robustness_split_sensitivity.csv` (M5) and `m6_lwc_robustness_split_sensitivity.csv` (M6).

### 5.1 τ=0.95 row across four splits

| split | M5 realised | M5 hw | M5 Kupiec p | M5 Christ p | LWC realised | LWC hw | LWC Kupiec p | LWC Christ p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021-01-01 | 0.9507 | 397.3 | 0.864 | 0.293 | 0.9506 | 386.1 | 0.892 | **0.007** |
| 2022-01-01 | 0.9502 | 371.4 | 0.961 | 0.666 | 0.9502 | 397.2 | 0.961 | **0.002** |
| 2023-01-01 | 0.9503 | 354.6 | 0.956 | 0.921 | 0.9503 | 385.3 | 0.956 | 0.275 |
| 2024-01-01 | 0.9504 | 388.9 | 0.947 | 0.887 | 0.9504 | 426.8 | 0.947 | 0.525 |

LWC Kupiec passes at every split; pooled coverage tracks 0.9502–0.9506 across all four splits — same stability shape as M5. **LWC Christoffersen rejects (p<0.05) at the 2021 and 2022 splits**: violations cluster more under LWC at lower-τ anchors when the OOS slice is large (n=2,731 / n=2,250). This is the τ=0.95 row only — see §10 below for the full discussion.

## 6. Leave-one-symbol-out CV (the per-symbol generalisation evidence)

CSVs: `v1b_robustness_loso.csv` and `m6_lwc_robustness_loso.csv`.

### 6.1 τ=0.95 row, held-out symbol by held-out symbol

| held-out | M5 realised | M5 hw | M5 Kupiec p | LWC realised | LWC hw | LWC Kupiec p |
|---|---:|---:|---:|---:|---:|---:|
| AAPL  | 0.9942 | 372.0 | 0.001 | 0.9249 | 299.6 | 0.156 |
| GLD   | 0.9942 | 373.1 | 0.001 | 0.9422 | 188.1 | 0.646 |
| GOOGL | 0.9711 | 357.0 | 0.168 | 0.9538 | 291.7 | 0.819 |
| HOOD  | 0.8555 | 328.0 | 0.000 | 0.9653 | 658.9 | 0.329 |
| MSTR  | 0.7861 | 319.6 | 0.000 | 0.9480 | 736.7 | 0.903 |
| NVDA  | 0.9595 | 360.3 | 0.552 | 0.9364 | 494.4 | 0.431 |
| QQQ   | 0.9942 | 367.8 | 0.001 | 0.9711 | 208.9 | 0.168 |
| SPY   | 1.0000 | 371.6 | 0.000 | 0.9538 | 158.4 | 0.819 |
| TLT   | 1.0000 | 375.8 | 0.000 | 0.9480 | 186.0 | 0.903 |
| TSLA  | 0.8786 | 350.4 | 0.000 | 0.9538 | 665.3 | 0.819 |
| **mean** | 0.9434 | 357.5 | | **0.9497** | 388.8 | |
| **std**  | **0.0759** | | | **0.0134** | | |
| **Kupiec ≥ 0.05** | **2 / 10** | | | **10 / 10** | | |

This is the most striking generalisation result. Under M5 the LOSO realised range is [0.786 (MSTR), 1.000 (SPY/TLT)] — a 21.4pp spread. Under M6 it is [0.925 (AAPL), 0.971 (QQQ)] — a 4.6pp spread, **5.7× tighter**. Every held-out symbol passes Kupiec under M6.

The LWC half-width per held-out symbol scales with the held-out symbol's σ̂: SPY/TLT/GLD/QQQ → 158-209 bps (low-σ); HOOD/MSTR/TSLA → 658-736 bps (high-σ). M5's per-pool fit produces a flat ~360 bps for every held-out symbol, which is why the high-σ symbols under-cover and the low-σ symbols over-cover when M5's pool excludes them.

## 7. Per-asset-class breakdown

CSVs: `v1b_robustness_per_class.csv` (M5) and `m6_lwc_robustness_per_class.csv` (M6).

### 7.1 At τ=0.95

| asset_class | n | M5 realised | M5 hw | M5 Kupiec p | LWC realised | LWC hw | LWC Kupiec p |
|---|---:|---:|---:|---:|---:|---:|---:|
| equities (8) | 1384 | 0.9386 | 354.7 | 0.060 | 0.9509 | 435.6 | 0.882 |
| gold (1)     |  173 | 0.9942 | 354.6 | 0.001 | 0.9422 | 184.4 | 0.646 |
| treasuries (1) | 173 | 1.0000 | 354.4 | 0.000 | 0.9538 | 184.3 | 0.819 |

Width redistribution: M5 serves a flat ~355 bps half-width to all classes (per-regime quantile is symbol-agnostic). LWC widens equities (high-σ pool) to 436 bps (+23%) and tightens gold/treasuries (low-σ) to 184 bps (−48%). Coverage matches nominal across every class under LWC; M5 over-covers gold/treasuries severely.

## 8. GARCH(1,1) baseline comparison

CSVs: `v1b_robustness_garch_baseline.csv` (M5 reference) and `m6_lwc_robustness_garch_baseline.csv` (LWC reference).

### 8.1 At τ=0.95 (matched OOS keys, n=1,730)

| method | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|
| GARCH(1,1) | 0.9254 | 322.2 | 0.000 | 0.016 |
| M5 deployed | 0.9503 | 354.6 | 0.956 | 0.921 |
| LWC deployed | 0.9503 | 385.3 | 0.956 | 0.275 |

GARCH undercovers significantly (−2.5pp at τ=0.95) and rejects both Kupiec and Christoffersen. Both calibrated methods clear Kupiec; LWC's Christoffersen p (0.275) is materially lower than M5's (0.921) — see §10.

## 9. Path-fitted conformity score (CME-projected subset)

CSVs: `v1b_robustness_path_fitted.csv` (M5) and `m6_lwc_robustness_path_fitted.csv` (M6).

### 9.1 At τ=0.95 (endpoint-fitted variant on n=1,557 CME-projected OOS)

| forecaster | endpoint realised | path realised | gap (pp) | half-width (bps) |
|---|---:|---:|---:|---:|
| M5  | 0.9512 | 0.9917 | −4.05 | 313.7 |
| LWC | 0.9505 | 0.9621 | **−1.16** | 356.9 |

LWC narrows the path-vs-endpoint mis-coverage gap from −4.05pp to −1.16pp without explicit path-fitting. σ̂-rescaling absorbs some within-weekend path variance (paths in high-σ symbols are wider and the σ̂-scaled band tracks).

## 10. Vol-tertile sub-split (the §10.2 robustness check)

CSVs: `v1b_robustness_vol_tertile.csv` (M5) and `m6_lwc_robustness_vol_tertile.csv` (M6).

| variant | M5 Berkowitz LR | LWC Berkowitz LR |
|---|---:|---:|
| 3-cell baseline (regime_pub) | 173.0 | 165.0 |
| 5-cell sub-split (normal × tertile) | 175.0 | 168.3 |

Bin-structure refutation holds under both: finer regime granularity does NOT drop Berkowitz LR (M5: 173 → 175, +1%; LWC: 165 → 168, +2%). LWC's pooled Berkowitz is 5% lower than M5's but both still strongly reject — the cross-sectional common-mode is orthogonal to per-symbol scale, exactly as `reports/v3_bakeoff.md` predicted.

## 11. Where M6 underperforms M5 — the discussion list

These are the cells where the comparison flips against M6, surfaced for the paper-revision conversation.

1. **Pooled half-width at τ=0.95: +30.7 bps wider** (CI [+12, +49] excludes zero). This is the well-documented +8.6% width tax noted in `reports/v3_bakeoff.md` for the per-symbol-calibration trade-off. M6 still passes Kupiec at the same significance level (p=0.956 for both), so this is a sharpness loss not a calibration loss.

2. **Christoffersen p drops at every τ.** M5's per-anchor Christoffersen is 0.34–0.92; LWC's is 0.10–1.00 with a worst-case of 0.10 (τ=0.68 pooled). On the split-sensitivity table (§5), LWC rejects Christoffersen at τ=0.95 for the 2021 (p=0.007) and 2022 (p=0.002) splits where M5 didn't. **Why:** LWC tightens *unconditional* per-symbol calibration, but introduces some lag-1 clustering in violations because σ̂_sym(t) is itself slowly-varying — a long calm streak under-estimates σ̂ going into a vol shock, producing a cluster of violations. This is a *new*, milder rejection pattern that replaces M5's per-symbol bimodality. **Resolved 2026-05-04 (Phase 5 σ̂ EWMA promotion):** under the canonical EWMA HL=8 σ̂, the 2021 / 2022 split-date Christoffersen rejections at τ=0.95 clear (p ∈ {0.0065, 0.0016} → {0.1153, 0.1861}); 0 rejections across the full 16-cell (split × τ) grid. See `reports/m6_sigma_ewma.md`.

3. **Shock-tertile floor barely improves.** M5: 87.18% at τ=0.95 on the shock tertile; LWC: 87.82%, an improvement of only +0.64pp. The §9.1 shock-tertile ceiling is *not* a per-symbol-scale story — it's the cross-sectional common-mode that M6a (partial-out) targets, not M6 (LWC). The §9.1 narrative survives unchanged.

4. **Path-coverage rejection persists.** Both forecasters still reject Kupiec on the path-coverage criterion at τ=0.68/0.85 (the path scope inflates the implied empirical violation rate). LWC's narrower endpoint-vs-path gap (§9) does not lift the path-fitted Kupiec p above 0.05 at lower τ.

5. **Per-symbol Berkowitz still reject for some symbols.** Under LWC: TSLA (p=0.0004), GLD (p=0.349 — passes), GOOGL (p=0.002), TLT (p=0.002) reject the Berkowitz null at α=0.01. The LR magnitudes are 5–14× smaller than M5's, but the residual rejection is non-zero. Cross-sectional common-mode again — orthogonal to LWC.

6. **NVDA Berkowitz LR rises slightly.** M5: 0.92, M6: 7.92. NVDA was M5's best-calibrated symbol (var(z)=0.96, near nominal). LWC's standardisation marginally over-tightens NVDA (var(z)=0.73) — a small price for fixing 9 other symbols.

## 12. Two findings outside the scope of the original brief

These came out of the validation pass and may be worth surfacing:

### 12.1 No δ-overshoot needed under M6

The δ schedule selected by the walk-forward sweep (`scripts/run_lwc_delta_sweep.py`, `reports/tables/v1b_lwc_delta_sweep.csv`) is `{0, 0, 0, 0}`. M5's deployed δ is `{0.05, 0.02, 0, 0}`. LWC's per-symbol scale standardisation tightens cross-split coverage variance enough that the M5-style overshoot margin no longer earns its keep. **Deployment simplification:** 16 deployable scalars instead of 20 (the LWC artefact JSON keeps the 4 zeros as a structural slot).

### 12.2 Width is symbol-dependent, not pooled

While pooled width at τ=0.95 is +30.7 bps under M6, the per-symbol re-allocation is large:
- SPY at the latest Friday (2026-04-24, normal regime): M5 280 bps → LWC 167 bps (−40%).
- MSTR at the same Friday: M5 280 bps → LWC 555 bps (+98%).
- HOOD at the same Friday: M5 280 bps → LWC 435 bps (+55%).

For consumers who care about per-symbol precision (lending consumers, single-name-options consumers), the per-symbol re-allocation is the headline — not the pooled +8.6%.

## 13. Newly-listed-symbol admission (Phase 6 evidence)

Production guidance for adding a new symbol to the M6 panel: how many calibration weekends does the symbol need before it can be admitted without breaking the per-symbol Kupiec headline?

Source: Phase 6 simulation sample-size sweep (`scripts/run_simulation_size_sweep.py`, `reports/m6_simulation_study.md` §7). Sweep grid N ∈ {80, 100, 150, 200, 300, 400, 600} weekends per symbol, four DGPs, 100 Monte Carlo reps per cell, σ̂ rule = K=26 (Phase 3 convention; EWMA HL=8 only relaxes these thresholds further). N=600 cells reproduce the Phase 3 sim_summary byte-for-byte (regression check passes).

| Regime assumption | Minimum N (weekends) | Expected per-symbol Kupiec pass-rate at N | Notes |
|---|---:|---:|---|
| Stationary scale (DGP A) | 80 | ≥ 0.95 (sim: 1.000) | Pure scale heterogeneity; admission is essentially σ̂-only. |
| Slow drift (DGP C) | 80 | ≥ 0.95 (sim: 0.998) | Trailing-K σ̂ absorbs slow drift before it accumulates. |
| Single recent regime change (DGP D) | 80 | ≥ 0.95 (sim: 1.000) | σ̂ absorbs structural breaks within ~13 weekends. |
| Regime-switching (DGP B) | 600 (strict) / 200 (relaxed) | 0.976 (strict) / 0.938 (relaxed) | σ̂-rule-orthogonal: EWMA HL=8 (post-Phase-5 deployed) produces the same strict threshold — HL=8 N=600 pass-rate = 0.986, +1pp vs K=26's 0.976; intermediate-N differences within Monte Carlo noise. See `reports/m6_simulation_study.md` §7.6. |
| Conservative "no-harm" floor (any DGP) | 80 | ≥ M5 asymptotic (0.31) | LWC dominates M5 at every N in every DGP. |

**Recommended deployment threshold for Soothsayer-style equity-oracle panels: N ≥ 200 weekends (~3.5 years of weekend data).** This clears 0.94 pass-rate even under the regime-switching DGP B and sits comfortably above 0.95 under the stationary DGPs. The strict 0.95 threshold under DGP B (N ≥ 600) is **σ̂-rule-orthogonal** — re-simulated under the post-Phase-5 EWMA HL=8 σ̂ in `reports/m6_simulation_study.md` §7.6, the threshold stays at N=600 (HL=8 N=600 pass-rate = 0.986 vs K=26's 0.976; intermediate-N differences within Monte Carlo noise). The bottleneck is stochastic OOS regime-mixture across symbols, not σ̂'s tracking lag, so faster-reacting σ̂ rules don't help on this axis.

HOOD's empirical N≈218 (246 listed weekends, 28 dropped at the σ̂ warm-up) sits at the relaxed-threshold band. HOOD's per-symbol Kupiec p at τ=0.95 in the 2023+ OOS slice is **0.552** — passes α=0.05 cleanly. The simulation predicts at N=200 a 0.94–0.99 pass-rate range across DGPs; HOOD's empirical value is consistent with that range. The §6.4.1 disclosure "HOOD is the noisy-but-passing edge case" is mechanism-validated by the simulation.

## 14. Files produced this phase

| Phase | Script | Output |
|---|---|---|
| 2.1 | `scripts/run_v1b_per_symbol_diagnostics.py` | `reports/tables/{v1b_robustness,m6_lwc_robustness}_per_symbol.csv` |
| 2.2 | `scripts/run_v1b_garch_baseline.py` | `reports/tables/{v1b_robustness,m6_lwc_robustness}_garch_baseline.csv` |
| 2.3 | `scripts/run_v1b_split_sensitivity.py` | `reports/tables/{v1b_robustness,m6_lwc_robustness}_split_sensitivity.csv` |
| 2.4 | `scripts/run_v1b_loso.py` | `reports/tables/{v1b_robustness,m6_lwc_robustness}_loso.csv` |
| 2.5 | `scripts/run_v1b_per_class.py` | `reports/tables/{v1b_robustness,m6_lwc_robustness}_per_class.csv` |
| 2.6 | `scripts/run_v1b_path_fitted_conformal.py` | `reports/tables/{v1b_robustness,m6_lwc_robustness}_path_fitted.csv` |
| 2.7 | `scripts/run_v1b_vol_tertile.py` | `reports/tables/{v1b_robustness,m6_lwc_robustness}_vol_tertile.csv` |
| 2.8 | `scripts/aggregate_m5_m6_bootstrap.py` | `reports/tables/m5_vs_m6_bootstrap.csv` |
| 2.9 | `scripts/run_m6_pooled_oos_tables.py` | `reports/tables/m6_pooled_oos.csv`, `reports/tables/m6_realised_move_tertile.csv` |
| 5 (σ̂ EWMA) | `scripts/run_sigma_ewma_variants.py` | `reports/tables/sigma_ewma_{summary,split_sensitivity,per_symbol,bootstrap}.csv`, `sigma_ewma_<variant>_delta_sweep.csv` × 5 |
| 6 (sample-size sweep) | `scripts/run_simulation_size_sweep.py` | `reports/tables/sim_size_sweep_{per_symbol_kupiec,summary,admission_thresholds}.csv`, `reports/figures/sim_size_curves.{pdf,png}` |

To regenerate everything from scratch:

```bash
uv run python scripts/build_lwc_artefact.py
for fc in m5 lwc; do
  uv run python scripts/run_v1b_per_symbol_diagnostics.py --forecaster $fc
  uv run python scripts/run_v1b_garch_baseline.py --forecaster $fc
  uv run python scripts/run_v1b_split_sensitivity.py --forecaster $fc
  uv run python scripts/run_v1b_loso.py --forecaster $fc
  uv run python scripts/run_v1b_per_class.py --forecaster $fc
  uv run python scripts/run_v1b_path_fitted_conformal.py --forecaster $fc
  uv run python scripts/run_v1b_vol_tertile.py --forecaster $fc
done
uv run python scripts/aggregate_m5_m6_bootstrap.py
uv run python scripts/run_m6_pooled_oos_tables.py
```

Total runtime is dominated by the path-fitted runner (CME 1m bar load) and the GARCH fits; expect ~5 minutes end-to-end on this machine.
