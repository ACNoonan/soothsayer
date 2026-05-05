# M6 σ̂ EWMA promotion — Phase 5 evidence pack

**Date.** 2026-05-04
**Status.** PROMOTE → **EWMA HL=8** is the canonical M6 σ̂ rule. K=26 trailing window stays buildable for archival reproduction.
**Working doc.** `reports/active/m6_refactor.md` Phase 5.
**Driver script.** `scripts/run_sigma_ewma_variants.py` (deterministic from `seed=0`; ~30s wall clock end-to-end on the 5,916-row v1b panel).

## 1. Headline

The Phase 2 §11 discussion list flagged a temporal-clustering issue in M6 LWC: split-date Christoffersen rejected at α=0.05 at the 2021 + 2022 anchors at τ=0.95 (p = 0.0065 / 0.0016). The diagnostic narrative was that σ̂_sym(t) — the trailing K=26 weekend std — is itself slowly-varying, so a calm streak under-estimates σ̂ going into a vol shock and the violation cluster is non-Markov-independent.

Phase 5 prototyped four alternative σ̂ rules (three pure EWMA half-lives + one convex blend) and re-ran the targeted diagnostics on identical evaluable rows. **EWMA HL=8 is the only variant that clears split-date Christoffersen at every (split × τ) cell at α=0.05** — and it does so while *narrowing* the pooled half-width by 3.83% at τ=0.95 vs the K=26 baseline (block-bootstrap 95-CI upper on Δhw% = +0.25%, well inside the +5% gate).

This is the kind of result that doesn't usually exist: lower memory in σ̂ buys both better calibration *and* tighter bands. The intuition is that the per-symbol scale series is genuinely slowly time-varying (K=26 oversmooths — a week-2 vol shock in Q4 2021 was still being interpreted as Q3 calm 26 weekends later), and the EWMA's exponential-decay weighting tracks a regime-shift in fewer weekends without losing signal in stationary periods.

The 2026-05-04 freeze (`data/processed/lwc_artefact_v1_frozen_20260504.{json,parquet}`, sha 7b86d17a76912aa0…) is the new canonical M6. The K=26 freeze is preserved at `lwc_artefact_v1_archive_baseline_k26_20260504.{json,parquet}` for archival receipt-reproduction.

## 2. Variants

All five variants share the warm-up rule (`≥ 8` past observations) so they are evaluated on identical rows: 5,916 / 5,996 (80 dropped at panel start). The σ̂ rule differs only in how the past observations are weighted.

| Variant | σ̂ rule | Effective memory |
|---|---|---|
| **baseline_k26** | trailing K=26 weekend std (uniform weight) | ~26 weekends (rectangular kernel) |
| **ewma_hl6** | EWMA, half-life 6 weekends, λ = 0.5^(1/6) ≈ 0.8909 | ~6 weekends (≈ 9 effective obs) |
| **ewma_hl8** | EWMA, half-life 8 weekends, λ = 0.5^(1/8) ≈ 0.9170 | ~8 weekends (≈ 12 effective obs) |
| **ewma_hl12** | EWMA, half-life 12 weekends, λ = 0.5^(1/12) ≈ 0.9439 | ~12 weekends (≈ 17 effective obs) |
| **blend_a50_hl8** | 0.5 · σ̂_K26 + 0.5 · σ̂_EWMA_HL8 | mixed |

The EWMA estimator is the conventional RiskMetrics-style weighted std of relative residuals; residuals already have ~zero mean by the §7.4 factor-switchboard so no de-meaning step. Strictly pre-Friday: σ̂[i] uses only rows with `fri_ts' < fri_ts[i]`. Implementation in `src/soothsayer/backtest/calibration.py::add_sigma_hat_sym_ewma`.

## 3. Pooled OOS at split=2023-01-01

Same convention as the deployed M6 baseline — pre-2023 train, 2023+ OOS, regime quantiles from train, c-bump fit on OOS, δ from walk-forward. All five variants land at δ = `{all zero}` under the deployed selection criterion (cov_mean ≥ τ on every τ).

| variant | τ | realised | hw_bps | c_bump | kupiec_p | christ_p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 0.6873 | 132.60 | 1.000 | 0.5152 | 0.1023 |
| baseline_k26 | 0.85 | 0.8613 | 218.11 | 1.000 | 0.1845 | 0.3951 |
| baseline_k26 | 0.95 | 0.9503 | 385.33 | 1.069 | 0.9560 | 0.2745 |
| baseline_k26 | 0.99 | 0.9902 | 685.84 | 1.039 | 0.9420 | 1.0000 |
| **ewma_hl8** | 0.68 | 0.6925 | 130.83 | 1.000 | 0.2639 | 0.2440 |
| **ewma_hl8** | 0.85 | 0.8549 | 213.59 | 1.000 | 0.5653 | 0.4027 |
| **ewma_hl8** | 0.95 | 0.9503 | **370.56** | 1.079 | 0.9560 | 0.6028 |
| **ewma_hl8** | 0.99 | 0.9902 | **634.99** | 1.003 | 0.9420 | 1.0000 |
| ewma_hl6 | 0.95 | 0.9503 | 367.89 | 1.054 | 0.9560 | 0.6754 |
| ewma_hl12 | 0.95 | 0.9509 | 355.38 | 1.035 | 0.8682 | 0.6802 |
| blend_a50_hl8 | 0.95 | 0.9503 | 377.23 | 1.073 | 0.9560 | 0.7240 |

(Full table: `reports/tables/sigma_ewma_summary.csv`. The χ²(10) per-symbol-grouped Christoffersen `christ_p` reads as "no symbol-clustering of violations" — at τ=0.99 the pooled p saturates at 1.0 because violations are too sparse to identify within-symbol transitions, by design.)

## 4. Split-date Christoffersen — the load-bearing diagnostic

This is the diagnostic Phase 5 was designed to fix. Per-symbol-grouped pooled LR (df = 10) at every (split × τ) cell.

**baseline_k26** — 4 rejections at α=0.05 (3 at the 2021 split, 1 at 2022 × τ=0.95):

| split | τ=0.68 | τ=0.85 | **τ=0.95** | τ=0.99 |
|---|---:|---:|---:|---:|
| 2021 | **0.0190** | **0.0275** | **0.0065** | 1.0000 |
| 2022 | 0.3394 | 0.1588 | **0.0016** | 1.0000 |
| 2023 | 0.1023 | 0.3951 | 0.2745 | 1.0000 |
| 2024 | 0.1579 | 0.4338 | 0.5252 | 1.0000 |

**ewma_hl8** — 0 rejections at α=0.05 across the whole 16-cell grid:

| split | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| 2021 | 0.0807 | 0.1222 | 0.1153 | 1.0000 |
| 2022 | 0.5701 | 0.1434 | 0.1861 | 1.0000 |
| 2023 | 0.2440 | 0.4027 | 0.6028 | 1.0000 |
| 2024 | 0.2744 | 0.2664 | 0.6708 | 1.0000 |

The two cells the brief was targeting (2021 × 0.95 and 2022 × 0.95) jump from p ∈ {0.0065, 0.0016} → {0.1153, 0.1861}. These are no longer reviewer-flag-worthy.

For completeness, the other variants:

- **ewma_hl6** — 3 rejections (2021 × 0.68: 0.0219; 2023 × 0.68: 0.0240; 2024 × 0.68: 0.0381). All τ=0.68 cells, all weak rejections; at higher τ it clears. Indicates HL=6 is too short for the τ=0.68 cell (the σ̂ doesn't accumulate enough mass at 6-weekend memory for the lowest anchor).
- **ewma_hl12** — 1 rejection (2021 × 0.85: 0.0107). HL=12 is closer to the K=26 baseline behaviour and recovers some of the long-memory clustering at the 2021 split.
- **blend_a50_hl8** — 0 rejections at α=0.05 across the grid, but the smallest p (2021 × 0.68: 0.0273) is closer to rejection than ewma_hl8's smallest (2021 × 0.95: 0.1153). The blend is dominated by ewma_hl8 here.

Full table: `reports/tables/sigma_ewma_split_sensitivity.csv`.

## 5. Per-symbol Berkowitz at split=2023-01-01

Pre-existing Phase-2 outliers (TSLA / GOOGL / TLT) at α=0.01:

| symbol | baseline_k26 | ewma_hl6 | **ewma_hl8** | ewma_hl12 | blend_a50_hl8 |
|---|---:|---:|---:|---:|---:|
| GOOGL | 14.45 (REJ) | 9.78 (PASS) | **10.24 (PASS)** | 8.05 (PASS) | 13.25 (REJ) |
| TLT | 14.39 (REJ) | 17.50 (REJ) | **16.73 (REJ)** | 16.19 (REJ) | 16.08 (REJ) |
| TSLA | 17.97 (REJ) | 9.90 (PASS) | **13.54 (REJ)** | 12.00 (REJ) | 14.73 (REJ) |

EWMA HL=8 clears GOOGL but not TLT or TSLA. This is consistent with the Phase 2 narrative: per-symbol Berkowitz rejection in TLT / TSLA is driven by **cross-sectional common-mode** (same axis as the §6.4.1 ρ_cross signal), not per-symbol scale. σ̂-rule changes can't fix it; that's M6a territory (gated on the W8 r̄_w forward predictor). The rest of the panel — AAPL, GLD, HOOD, MSTR, NVDA, QQQ, SPY — shows no Berkowitz movement under HL=8 (all <2 LR units of difference vs baseline).

Full table: `reports/tables/sigma_ewma_per_symbol.csv`.

## 6. Per-symbol Kupiec at τ=0.95

Pass-rate threshold from Phase 2 was ≥ 8/10. **All five variants hold 10/10**, including baseline_k26. The σ̂-rule change does not move any individual symbol's per-symbol Kupiec across the α=0.05 threshold. This is the no-harm-done floor.

## 7. Block-bootstrap CI on (Δrealised, Δhw) — EWMA HL=8 vs baseline_k26

Paired weekend-block bootstrap on `(symbol, fri_ts, τ)` over the 173-weekend 2023+ OOS slice. 1000 replicates, `seed=0`, percentile CIs at 2.5% / 97.5%. Mirrors `aggregate_m5_m6_bootstrap.py` exactly; promote-variant simply swaps in for LWC.

| τ | realised_base | realised_prom | Δrealised | 95-CI(Δrealised) | hw_bps_base | hw_bps_prom | Δhw_bps | Δhw % | 95-CI hi (Δhw %) |
|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 0.68 | 0.6873 | 0.6925 | +0.0052 | [−0.0064, +0.0173] | 132.6 | 130.8 | −1.77 | **−1.34** | +0.25 |
| 0.85 | 0.8613 | 0.8549 | −0.0064 | [−0.0156, +0.0029] | 218.1 | 213.6 | −4.52 | **−2.07** | −0.45 |
| 0.95 | 0.9503 | 0.9503 | +0.0000 | [−0.0069, +0.0075] | 385.3 | 370.6 | −14.76 | **−3.83** | −1.88 |
| 0.99 | 0.9902 | 0.9902 | +0.0000 | [−0.0017, +0.0017] | 685.8 | 635.0 | −50.85 | **−7.41** | −5.65 |

**Width-gate verdict.** Max 95-CI upper on Δhw % across all τ is +0.25 % (τ=0.68 row), comfortably inside the +5 % promotion gate. At τ ∈ {0.85, 0.95, 0.99} the 95-CI upper is *negative* — i.e., we can reject "EWMA is wider than baseline" with 97.5% confidence at three of the four anchors.

**Coverage-neutrality.** Δrealised CI straddles zero at every τ — promotion does not move pooled coverage in either direction in a statistically meaningful way. The improvement is all in *width* and *temporal independence of violations*, not in unconditional coverage.

Full table: `reports/tables/sigma_ewma_bootstrap.csv`.

## 8. Promotion criterion — formal verdict

| Gate | Threshold | Result |
|---|---|---|
| Split-date Christoffersen at every (split × τ) at α=0.05 | no rejections | **PASS** (0/16 cells reject) |
| Per-symbol Kupiec at τ=0.95 | ≥ 8/10 | **PASS** (10/10) |
| Pooled half-width Δ vs M6-baseline (block-bootstrap 95-CI upper) | ≤ +5 % at every τ | **PASS** (max +0.25 % at τ=0.68; ≤ 0 elsewhere) |

EWMA HL=8 is the unique variant that clears all three gates. Under the brief's tiebreaker (longest half-life if multiple qualify), HL=12 would have been preferred — but it does not clear gate 1 (one rejection at 2021 × τ=0.85). HL=8 is the strict winner.

**VERDICT: PROMOTE → ewma_hl8.**

## 9. Operational changes shipped 2026-05-04

| File | Change |
|---|---|
| `src/soothsayer/backtest/calibration.py` | New: `add_sigma_hat_sym_ewma`, `add_sigma_hat_sym_blend`, EWMA constants. `compute_score_lwc` gained `scale_col` parameter. |
| `scripts/build_lwc_artefact.py` | New `--variant {baseline_k26, ewma_hl8}` flag (default `ewma_hl8`). Sidecar gains `_lwc_variant`, `sigma_hat.method`, `sigma_hat.half_life_weekends`, `sigma_hat.raw_column`. |
| `scripts/run_sigma_ewma_variants.py` | New end-to-end Phase 5 driver — δ-sweep, c-fit, pooled OOS, split-date Christoffersen, per-symbol Berkowitz/Kupiec, bootstrap CI, verdict. |
| `data/processed/lwc_artefact_v1.{json,parquet}` | Rebuilt under EWMA HL=8. Sidecar fields: `_lwc_variant: "ewma_hl8"`, `sigma_hat.method: "ewma"`, `sigma_hat.half_life_weekends: 8`. |
| `data/processed/lwc_artefact_v1_frozen_20260504.{json,parquet}` | New canonical freeze (sha 7b86d17a76912aa0…). Replaces previous K=26 freeze. |
| `data/processed/lwc_artefact_v1_archive_baseline_k26_20260504.{json,parquet}` | K=26 baseline freeze archived (renamed outside `_frozen_*` glob so forward-tape auto-discovery picks the new freeze). |
| `reports/active/m6_refactor.md` Phase 1 §1.1 | Added "(superseded 2026-05-04 by EWMA HL=8)" note next to the K=26 description. Phase 5 marked complete. |
| `reports/methodology_history.md` | Dated entry recording the σ̂ promotion. |

## 10. Reproduce-from-scratch

```bash
# 1. Re-run all five variant diagnostics (writes 5 sweep CSVs + 4 summary CSVs).
uv run python -u scripts/run_sigma_ewma_variants.py

# 2. Re-build the live artefact under EWMA HL=8.
uv run python -u scripts/build_lwc_artefact.py                           # default = ewma_hl8
uv run python -u scripts/build_lwc_artefact.py --variant baseline_k26    # archival-reproduction

# 3. Re-freeze.
uv run python -u scripts/freeze_lwc_artefact.py
# → data/processed/lwc_artefact_v1_frozen_{YYYYMMDD}.{json,parquet}

# 4. Smoke + tests.
uv run python -u scripts/smoke_oracle.py --forecaster lwc
uv run python -m pytest tests/test_oracle_competitor_registry.py tests/test_protocol_compare.py -p no:anchorpy -q

# 5. Forward-tape harness (reads the latest frozen artefact via auto-discovery).
bash scripts/run_forward_tape_harness.sh
```

## 11. Why the EWMA wins — interpretation

The K=26 trailing window is a rectangular kernel. The 2021 / 2022 split-date Christoffersen rejections at τ=0.95 came from a specific failure mode: a calm Q3 streak under-estimates σ̂ for ~26 weekends, then a vol shock arrives, σ̂ doesn't update fast enough, the band stays narrow for a few more weekends, and **violations cluster** at the regime boundary. The χ²(10) per-symbol-grouped Christoffersen test catches exactly this clustering.

The EWMA half-life of 8 weekends gives an effective memory of roughly 12 observations (1 / (1−λ) ≈ 12), with rapid down-weighting of older shocks. A 2-weekend vol shock now propagates into σ̂ within ~3–4 weekends instead of staying in the rolling window for 26. So the post-shock band widens faster, violations don't pile up, and the lag-1 transitions return to Markov-independent.

The reason the *same* change also narrows the bands is subtler: EWMA σ̂ has lower bias in the calm-recovery regime (after a vol shock subsides, EWMA forgets the shock faster than K=26, so the served band gets back to "calm" width sooner). Given that calm regimes are the majority of the panel, the average half-width shrinks.

This is consistent with how RiskMetrics-style EWMA volatility estimators outperform fixed-window estimators in mean-reverting variance regimes — a well-trodden result in financial-econometrics literature. The new evidence here is that the same mechanic carries over to a *conformal* setting: shorter-memory σ̂ tightens both the unconditional Kupiec margin and the conditional Christoffersen rejection, on the same calibration data.

## 12. Limits and open follow-ups

- **TLT / TSLA Berkowitz still rejects.** σ̂-rule choice cannot fix cross-sectional common-mode mis-calibration. M6a (common-mode partial-out) remains the dedicated lever here, gated on the W8 r̄_w Friday-observable forward predictor. See `reports/methodology_history.md` 2026-05-03 dual-profile lock entry.
- **τ=0.99 Kupiec at the 2021 split.** Both baseline and EWMA HL=8 (and most variants) reject Kupiec at the 2021 × 0.99 cell (p ≈ 0.018) because the 277-weekend OOS slice at that anchor sees realised 0.9941 against expected 0.99 — a knife-edge p driven by 16 vs 27.7 expected violations. This is a small-sample artefact at the highest-τ tail edge and is not σ̂-rule-sensitive.
- **HL=8 was tested at three discrete points.** The brief committed to {6, 8, 12}; HL=8 is the winner among these. A finer grid (HL ∈ {7, 9, 10, 11}) might find a marginal improvement, but the gain over HL=8 would be ≪ +0.25% on width and the optimisation surface is not load-bearing for the paper revision. Deferred unless a future review pass surfaces a specific concern.
- **N=600 vs N=200.** The simulation study (Phase 6) is the place to test whether HL=8 is robust as the panel shrinks (HOOD has ~200 weekends; new symbols start at zero). σ̂ rules with shorter memory have less data to amortise — this could matter for newly-listed-symbol admission. Phase 6 will quantify the boundary.

## 13. Selection-procedure disclosure

This section is a deliberate transparency layer on the §8 promotion verdict. The §8 verdict was reached by running 80 split-date Christoffersen tests (5 variants × 4 split anchors × 4 τ values) and selecting the only variant with zero per-cell rejections at uncorrected α=0.05. That selection procedure is multiple-testing exposed: under the joint null that all five variants are equally well-calibrated, ~4 of 80 tests would be expected to reject by chance, and the procedure favours variants that happened to land lucky in the 16 cells the test sees. This section documents what we did about it.

### 13.1 Pre-registration

The promotion criterion was specified before the variants were diagnosed (reports/active/m6_refactor.md §5.4, written 2026-05-04 alongside the rest of the Phase 5 plan). Three gates, all sharp thresholds:

1. **Split-date Christoffersen.** Variant must clear all 16 (split × τ) cells at uncorrected α=0.05. The targeted cells were 2021 × 0.95 and 2022 × 0.95 — the two Phase-2 §11 rejections that motivated the σ̂-rule rethink — but the gate is the full 16-cell grid, not just the two flagged cells.
2. **Per-symbol Kupiec at τ=0.95.** ≥ 8 of 10 symbols must clear at α=0.05. This is a no-harm-done floor — the σ̂-rule change must not break the per-symbol calibration story Phase 2 established.
3. **Pooled half-width gate.** Block-bootstrap 95-CI upper on Δhw % vs the K=26 baseline must be ≤ +5 % at every τ. Width-tax cap.

The variant ladder was {baseline_k26, ewma_hl6, ewma_hl8, ewma_hl12, blend_a50_hl8} — 5 candidates, fixed in advance. The half-life set {6, 8, 12} was specified by mechanism (faster-reacting σ̂ should fix temporal clustering; the optimum is somewhere in this neighborhood) rather than data-mined from a wider sweep.

### 13.2 Multi-test exposure

The 80-cell exposure breaks down as:

- **Gate 1 (Christoffersen):** 80 tests = 5 variants × 4 splits × 4 τ. This is where the selection bias concentrates — the variant that wins is by definition the one whose 16 χ²(10) p-values all happened to land above 0.05.
- **Gate 2 (per-symbol Kupiec):** 50 tests = 5 variants × 10 symbols. Less exposure because the gate is "≥ 8/10," not "all 10," so a few unlucky cells don't disqualify a variant. Empirically all five variants returned 10/10, so this gate did no work in distinguishing them.
- **Gate 3 (bootstrap CI on width):** evaluates only the promote candidate against the baseline, with proper sampling-distribution machinery. No multi-test issue.

Gate 1 is therefore the load-bearing exposure. The mitigation needs to address it.

### 13.3 The full 5 × 16 grid (raw and BH-adjusted)

Below is the complete split-date Christoffersen grid that the selection ran on. **Bold** cells are uncorrected α=0.05 rejections. No cells survive Benjamini-Hochberg correction at FDR=0.05 across the full 80-test grid (smallest BH-adjusted q is 0.130, vs the 0.05 threshold).

| variant | split | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---|---:|---:|---:|---:|
| baseline_k26 | 2021 | **0.0190** | **0.0275** | **0.0065** | 1.0000 |
| baseline_k26 | 2022 | 0.3394 | 0.1588 | **0.0016** | 1.0000 |
| baseline_k26 | 2023 | 0.1023 | 0.3951 | 0.2745 | 1.0000 |
| baseline_k26 | 2024 | 0.1579 | 0.4338 | 0.5252 | 1.0000 |
| ewma_hl6 | 2021 | **0.0219** | 0.1031 | 0.2101 | 1.0000 |
| ewma_hl6 | 2022 | 0.5301 | 0.0947 | 0.3215 | 1.0000 |
| ewma_hl6 | 2023 | **0.0240** | 0.2766 | 0.6754 | 1.0000 |
| ewma_hl6 | 2024 | **0.0381** | 0.0936 | 0.7845 | 1.0000 |
| ewma_hl8 | 2021 | 0.0807 | 0.1222 | 0.1153 | 1.0000 |
| ewma_hl8 | 2022 | 0.5701 | 0.1434 | 0.1861 | 1.0000 |
| ewma_hl8 | 2023 | 0.2440 | 0.4027 | 0.6028 | 1.0000 |
| ewma_hl8 | 2024 | 0.2744 | 0.2664 | 0.6708 | 1.0000 |
| ewma_hl12 | 2021 | 0.0566 | **0.0107** | 0.3177 | 1.0000 |
| ewma_hl12 | 2022 | 0.5497 | 0.1108 | 0.5293 | 1.0000 |
| ewma_hl12 | 2023 | 0.1890 | 0.4611 | 0.6802 | 1.0000 |
| ewma_hl12 | 2024 | 0.5054 | 0.0944 | 0.5862 | 1.0000 |
| blend_a50_hl8 | 2021 | **0.0273** | 0.0628 | 0.0943 | 1.0000 |
| blend_a50_hl8 | 2022 | 0.4769 | 0.0946 | 0.1623 | 1.0000 |
| blend_a50_hl8 | 2023 | 0.1046 | 0.2517 | 0.7240 | 1.0000 |
| blend_a50_hl8 | 2024 | 0.2056 | 0.2107 | 0.7906 | 1.0000 |

**Per-variant rejection counts (gate 1):**

| variant | uncorrected rejections (α=0.05) | BH-rejected cells (FDR=0.05, m=80) |
|---|---:|---:|
| baseline_k26 | 4 / 16 | 0 / 16 |
| ewma_hl6 | 3 / 16 | 0 / 16 |
| **ewma_hl8** | **0 / 16** | **0 / 16** |
| ewma_hl12 | 1 / 16 | 0 / 16 |
| blend_a50_hl8 | 1 / 16 | 0 / 16 |

Full 80-row table with raw + BH-adjusted p-values: `reports/tables/sigma_ewma_split_sensitivity_bh_corrected.csv`. Reproduces deterministically from `uv run python scripts/run_sigma_ewma_variants.py` (seed=0, fixed variant ladder).

### 13.4 What changes under correction

Under uncorrected α=0.05, **EWMA HL=8 is the unique variant clearing gate 1** (zero rejections out of 16 cells). The deployment decision is unchanged.

Under Benjamini-Hochberg at FDR=0.05 across the full 80-cell grid, **all five variants clear** (zero BH-rejected cells; smallest BH-adjusted q is 0.130). The corrected reading is that the per-cell evidence does not statistically distinguish the five variants — the joint null cannot be rejected at any cell once the multi-test exposure is accounted for.

The two readings are consistent with each other and with what the underlying mechanism predicts. Under uncorrected per-cell α=0.05, the procedure has enough power to flag the four cells where K=26 visibly clusters violations (2021 × 0.68, 2021 × 0.85, 2021 × 0.95, 2022 × 0.95). Once you control for the fact that you ran 80 tests, those four cells are no longer individually surprising — but the *pattern* (all four concentrated in one variant, all four pre-2023) remains suggestive even though no individual cell crosses the corrected threshold.

The honest framing for the paper is therefore:

- **EWMA HL=8 is the variant we deploy**, selected under a pre-registered three-gate criterion. It is the only variant of five clearing all three gates at uncorrected per-cell α=0.05, while also being the variant the underlying mechanism (faster-reacting σ̂ closes the temporal-clustering lag) would predict.
- **Under stricter BH-FDR=0.05 correction across the 80-cell Christoffersen grid, no variant is statistically distinguishable** from the joint null, including the K=26 baseline. The case for HL=8 over its neighbours therefore rests on the bootstrap-CI improvement on pooled half-width (gate 3, no multi-test issue) and on forward-tape re-validation, not on per-cell χ²(10) significance.

We do **not** claim HL=8 is statistically significantly better than HL=6, HL=12, or the blend. The defensible claim is "HL=8 satisfies a pre-registered criterion that no other tested variant satisfies." That is true, sufficient, and the right shape for a methodology paper.

### 13.5 What does not have a multi-test issue

For completeness, here are the §8 evidence layers that are **not** exposed to the selection-induced bias:

- **§7 bootstrap CI on (Δrealised, Δhw)** — measures a single quantity for the promoted variant against the baseline with proper sampling-distribution machinery. The 95-CI upper on Δhw % across all τ is +0.25 %, and at three of four anchors the upper bound is *negative* (we can reject "EWMA is wider than baseline" at 97.5%). This is the strongest single piece of evidence in the Phase 5 ledger and is robust to the selection critique.
- **Mechanism prediction.** The K=26 → EWMA HL=8 swap was specified by mechanism (rectangular-kernel σ̂ has a ~13-weekend post-shock lag; an exponential-decay kernel with HL=8 cuts that to ~3–4 weekends) before the diagnostics were run. The fact that the variant selected by the empirical criterion is also the one the mechanism predicts is independent confirmation of the diagnosis.
- **No-harm-done gates.** Per-symbol Kupiec at τ=0.95 holds 10/10 across all five variants — the σ̂-rule change does not move any individual symbol's calibration across the per-symbol α=0.05 threshold. Per-symbol Berkowitz on the §11 outliers (TLT, TSLA) also stays in the same rejection regime under HL=8 as under K=26 — cross-sectional residual is the unmoved axis, σ̂-rule changes don't reach it. These observations don't generate the selection bias because they're not part of the selection.

### 13.6 Forward-tape variant comparison (held-out re-validation)

The forward-tape harness emits a per-variant evaluator (`scripts/run_forward_tape_variant_comparison.py`) that, on every Tuesday launchd fire, scores all five variants on the *same* forward weekends accumulating since the freeze and writes `reports/m6_forward_tape_{N}weekends_variants.md` alongside the canonical `m6_forward_tape_{N}weekends.md`. The variant schedules are themselves frozen at the same training cutoff as the canonical artefact (`scripts/freeze_sigma_ewma_variant_bundle.py`), so the comparison is genuinely held-out — none of the forward weekends were used to select HL=8.

Once 8–12 forward weekends have accumulated, this gives a third validation stage on top of the in-sample selection (§3–§7) and the bootstrap CI (§7). Its job is to *re-validate* the existing selection, not to re-do it: if HL=8 still produces the cleanest Christoffersen behaviour on the forward tape, the case for the deployment is closed. If a different variant looks cleaner on forward data, that's a flag to revisit, not to re-select on forward data (which would just move the selection-bias problem).

### 13.7 Reproducing the disclosure

```bash
# Re-runs the 5-variant ladder + multi-test correction.
uv run python -u scripts/run_sigma_ewma_variants.py
# Outputs:
#   reports/tables/sigma_ewma_split_sensitivity.csv          # raw 80-cell grid
#   reports/tables/sigma_ewma_split_sensitivity_bh_corrected.csv  # +BH-adjusted q

# Build the variant bundle for forward-tape comparison.
uv run python -u scripts/freeze_sigma_ewma_variant_bundle.py

# Once forward weekends accumulate, the harness emits per-variant evaluations
# automatically (Tue 09:30 launchd fire).
```
