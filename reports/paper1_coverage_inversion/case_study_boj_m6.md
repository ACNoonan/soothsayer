# High-vol case study, M6 recompute — Yen carry unwind weekend (2024-08-02 → 2024-08-05)

*Generated 2026-07-16T19:08:02Z by `scripts/build_case_study_boj_m6.py` (band logic mirrors `scripts/build_paper1_figures.py::fig9_boj_anatomy` / paper §6.3.5). M6-current counterpart to `case_study_high_vol_20240802.md`, whose "Soothsayer" columns describe the retired v1 surface; that file is preserved unmodified as a historical record.*

## Provenance

| Input | Path | SHA-256 |
|---|---|---|
| lwc_artefact_v1.parquet | `data/processed/lwc_artefact_v1.parquet` | `726eb3c5df692d7522d6b95a218e5600d6b8bec4127f6396dbd91e54323cfbde` |
| lwc_artefact_v1.json | `data/processed/lwc_artefact_v1.json` | `1e5366528fa72e3f9297ac9ed70096264c9ab13ad50de5e72b3ad71722cc9c7e` |
| v1b_panel.parquet | `data/processed/v1b_panel.parquet` | `d875a8ce010eafb5a513f59e026489ca14bb3f0a97256cbc6347633873f1d9ac` |

- Deployment artefact: methodology `M6_LWC`, variant `ewma_hl8`, `_fetched_at` = `2026-05-04T22:35:25.842537+00:00`, source `scripts/build_lwc_artefact.py`, split date 2023-01-01.
- M6 served band per (symbol, τ): half-width = `c_bump[τ] × regime_quantile_table[regime_pub][τ] × σ̂_sym_pre_fri`, centred on the factor-adjusted point `point` from the per-Friday artefact row (`delta_shift_schedule` is identically 0 at all τ in the deployed sidecar). σ̂ is EWMA HL=8. Bands are read from the deployment artefact, not refit — byte-aligned with what a consumer read on 2024-08-02.
- The 2024-08-02 row sits in the OOS slice (post-2023; schedules fitted on pre-2023 train only).
- Comparator configs are **hypothetical consumer configurations**, carried verbatim from `case_study_high_vol_20240802.md` for comparability. They are not incumbent products: Pyth+k% wraps a Pyth-style point price in a fixed symmetric k% buffer; "VIX-scaled" and "Const-buffer" are the paper's v1-era calibrated baselines (pre-2023 train), centred on Friday close. Coverage = Monday 09:30 ET open inside the band.
- The original case study's "Soothsayer" columns describe the retired v1 surface (F0_stale forecaster + log-log VIX scaling) and are superseded by the M6 columns here. The original file is preserved unmodified.

## Section 1 — Realised moves and panel context

Market facts, unchanged from the original case study. Regime classification for 2024-08-02 = `high_vol` for all 10 symbols (artefact `regime_pub`).

| Symbol | Regime | Fri close | Mon open | Realised (bps) |
|---|---|---:|---:|---:|
| **AAPL** | high_vol | $219.86 | $199.09 | -944.7 |
| **GLD** | high_vol | $225.34 | $220.56 | -212.1 |
| **GOOGL** | high_vol | $166.66 | $155.50 | -669.6 |
| **HOOD** | high_vol | $17.88 | $14.70 | -1778.5 |
| **MSTR** | high_vol | $144.80 | $105.17 | -2737.2 |
| **NVDA** | high_vol | $107.27 | $92.06 | -1417.9 |
| **QQQ** | high_vol | $448.75 | $424.71 | -535.7 |
| **SPY** | high_vol | $532.90 | $511.64 | -398.9 |
| **TLT** | high_vol | $98.28 | $99.69 | +143.5 |
| **TSLA** | high_vol | $207.67 | $185.22 | -1081.0 |

Aggregate: max |Mon−Fri|/Fri = 2737 bps; mean |move| = 992 bps; 7 of 10 symbols exceed 500 bps.

## Section 2 — Coverage by method (M6 deployed bands)

| Symbol | Realised (bps) | Pyth+2% | Pyth+5% | Pyth+10% | Pyth+20% | VIX-scaled τ=0.68 | VIX-scaled τ=0.85 | VIX-scaled τ=0.95 | VIX-scaled τ=0.99 | Const-buffer τ=0.68 | Const-buffer τ=0.85 | Const-buffer τ=0.95 | Const-buffer τ=0.99 | M6 τ=0.68 | M6 τ=0.85 | M6 τ=0.95 | M6 τ=0.99 |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **AAPL** | -945 | ✗ / 200 bps | ✗ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 114 bps | ✗ / 201 bps | ✗ / 345 bps | ✗ / 668 bps |
| **GLD** | -212 | ✗ / 200 bps | ✓ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✓ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✓ / 272 bps | ✓ / 694 bps | ✗ / 62 bps | ✗ / 108 bps | ✗ / 185 bps | ✓ / 359 bps |
| **GOOGL** | -670 | ✗ / 200 bps | ✗ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✓ / 694 bps | ✗ / 111 bps | ✗ / 194 bps | ✗ / 334 bps | ✓ / 647 bps |
| **HOOD** | -1779 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 204 bps | ✗ / 357 bps | ✗ / 614 bps | ✗ / 1190 bps |
| **MSTR** | -2737 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✗ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 378 bps | ✗ / 663 bps | ✗ / 1139 bps | ✓ / 2208 bps |
| **NVDA** | -1418 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 189 bps | ✗ / 332 bps | ✗ / 571 bps | ✗ / 1106 bps |
| **QQQ** | -536 | ✗ / 200 bps | ✗ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✓ / 694 bps | ✗ / 69 bps | ✗ / 120 bps | ✗ / 207 bps | ✗ / 402 bps |
| **SPY** | -399 | ✗ / 200 bps | ✓ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✓ / 694 bps | ✗ / 49 bps | ✗ / 85 bps | ✗ / 146 bps | ✗ / 283 bps |
| **TLT** | +143 | ✓ / 200 bps | ✓ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✓ / 173 bps | ✓ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✓ / 272 bps | ✓ / 694 bps | ✗ / 75 bps | ✗ / 131 bps | ✓ / 225 bps | ✓ / 435 bps |
| **TSLA** | -1081 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 285 bps | ✗ / 499 bps | ✗ / 859 bps | ✓ / 1664 bps |

**Aggregate coverage on this weekend** (✓ count / total):

| Method | Covered | Mean half-width (bps) |
|---|---|---:|
| Pyth+2% | 1/10 | 200 |
| Pyth+5% | 3/10 | 500 |
| Pyth+10% | 6/10 | 1000 |
| Pyth+20% | 9/10 | 2000 |
| VIX-scaled τ=0.68 | 0/10 | 103 |
| VIX-scaled τ=0.85 | 1/10 | 173 |
| VIX-scaled τ=0.95 | 2/10 | 329 |
| VIX-scaled τ=0.99 | 5/10 | 700 |
| Const-buffer τ=0.68 | 0/10 | 75 |
| Const-buffer τ=0.85 | 0/10 | 139 |
| Const-buffer τ=0.95 | 2/10 | 272 |
| Const-buffer τ=0.99 | 5/10 | 694 |
| M6 τ=0.68 | 0/10 | 153 |
| M6 τ=0.85 | 0/10 | 269 |
| M6 τ=0.95 | 1/10 | 463 |
| M6 τ=0.99 | 5/10 | 896 |

## Section 3 — Reading the result

- **M6 at τ = 0.68 and τ = 0.85 covers 0/10.** All ten symbols breach the τ = 0.85 band simultaneously; this weekend is the single k_w = 10 event at τ = 0.85 in the OOS record (paper §6.3.4–§6.3.5).
- **M6 at τ = 0.95 covers 1/10** (TLT only; k_w = 9, the OOS maximum at that anchor). The σ̂ standardisation works at the per-symbol level — MSTR's τ = 0.85 half-width (663 bps) is ≈ 8× SPY's (85 bps) — but nine symbols moving the same direction by 4–27 σ̂-scale weekend returns is a cross-sectional common-mode event that no per-symbol band absorbs. The §6.3.4 joint-breach distribution (k* = 3 reserve-guidance threshold at τ = 0.95) is the operational handle for this event class.
- **M6 at τ = 0.99 covers 5/10** (GLD, GOOGL, MSTR, TLT, TSLA; mean half-width 896 bps). Coverage at this anchor comes from per-symbol width differentiation plus the factor-adjusted centre: MSTR's served band is 2,208 bps wide and centred −538 bps below Friday close, so its −2,737 bps realised move lands inside; SPY's 283 bps band does not reach its −399 bps move.
- **Fixed-buffer comparators:** Pyth+5% covers 3/10; Pyth+10% covers 6/10 and Pyth+20% covers 9/10, at uniform 1,000 / 2,000 bps half-widths on every symbol in every week regardless of regime. The v1-era calibrated comparators (VIX-scaled, const-buffer; pre-2023 train) cover at most 2/10 at τ ≤ 0.95 and 5/10 at τ = 0.99.
- **No method on this grid attains its nominal coverage at τ ≤ 0.95 on this weekend.** The best τ ≤ 0.95 cell is 2/10. The tail-coverage story on this event sits at τ = 0.99, where M6 matches the best comparator count (5/10) with regime- and symbol-conditional widths rather than a flat buffer.

**Change vs the retired v1 columns** (`case_study_high_vol_20240802.md`, generated 2026-05-03 against F0_stale + log-log VIX scaling):

| Anchor | v1 covered | v1 mean hw (bps) | M6 covered | M6 mean hw (bps) |
|---|---|---:|---|---:|
| τ=0.68 | 0/10 | 189 | 0/10 | 153 |
| τ=0.85 | 0/10 | 298 | 0/10 | 269 |
| τ=0.95 | 2/10 | 584 | 1/10 | 463 |
| τ=0.99 | 3/10 | 761 | 5/10 | 896 |

M6 serves narrower bands at τ ≤ 0.95 (and loses GLD at τ = 0.95 relative to v1) and wider, better-targeted bands at τ = 0.99 (adding GOOGL and MSTR). The v1 rows are superseded; they are retained in the original file as a historical record only.

*One weekend is one observation. The aggregate OOS calibration evidence for the deployed M6 architecture is in paper §6.3–§6.4 (pooled and per-symbol Kupiec, joint-tail k_w distribution: `reports/tables/paper1_a3_joint_baseline_kw_distribution.csv`, `reports/tables/m6_kw_threshold_stability.csv`); this case study is the qualitative counterpart on the worst observed weekend.*
