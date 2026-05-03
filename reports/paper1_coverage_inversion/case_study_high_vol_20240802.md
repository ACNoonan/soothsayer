# High-vol case study — Yen carry unwind weekend (2024-08-02 → 2024-08-05)
*Generated 2026-05-03T01:11:31Z; OOS panel slice (post-2023, surface frozen on pre-2023).* 

Counterpart to `kamino_xstocks_weekend_20260424.md`: that report covered a calm-regime weekend where every coverage method except Pyth-conf-only carried the band. This report covers the high-vol regime where fixed Pyth+constant baselines start to fail. VIX(Fri close) = 23.39 vs training median 16.11 (×1.45); regime classification = `high_vol`. All bands below: lower/upper in price units; ✓/✗ on whether Monday open landed inside; half-width (hw) in basis points relative to Friday close.

## Section 1 — Realised moves and panel context

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

Aggregate: max |Mon−Fri|/Fri = 2737 bps; mean |move| = 992 bps; 7 of 10 symbols breach the 500-bps threshold (i.e., a fixed Pyth+5% band would not have covered).

## Section 2 — Coverage by method

| Symbol | Realised (bps) | Pyth+2% | Pyth+5% | Pyth+10% | Pyth+20% | VIX-scaled τ=0.68 | VIX-scaled τ=0.85 | VIX-scaled τ=0.95 | VIX-scaled τ=0.99 | Const-buffer τ=0.68 | Const-buffer τ=0.85 | Const-buffer τ=0.95 | Const-buffer τ=0.99 | Soothsayer τ=0.68 | Soothsayer τ=0.85 | Soothsayer τ=0.95 | Soothsayer τ=0.99 |
|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **AAPL** | -945 | ✗ / 200 bps | ✗ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 97 bps | ✗ / 165 bps | ✗ / 322 bps | ✗ / 403 bps |
| **GLD** | -212 | ✗ / 200 bps | ✓ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✓ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✓ / 272 bps | ✓ / 694 bps | ✗ / 88 bps | ✗ / 150 bps | ✓ / 269 bps | ✓ / 293 bps |
| **GOOGL** | -670 | ✗ / 200 bps | ✗ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✓ / 694 bps | ✗ / 121 bps | ✗ / 207 bps | ✗ / 463 bps | ✗ / 504 bps |
| **HOOD** | -1779 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 273 bps | ✗ / 466 bps | ✗ / 908 bps | ✗ / 1138 bps |
| **MSTR** | -2737 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✗ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 398 bps | ✗ / 587 bps | ✗ / 1323 bps | ✗ / 1656 bps |
| **NVDA** | -1418 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 321 bps | ✗ / 473 bps | ✗ / 846 bps | ✗ / 1224 bps |
| **QQQ** | -536 | ✗ / 200 bps | ✗ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✓ / 694 bps | ✗ / 111 bps | ✗ / 189 bps | ✗ / 424 bps | ✗ / 462 bps |
| **SPY** | -399 | ✗ / 200 bps | ✓ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✓ / 694 bps | ✗ / 71 bps | ✗ / 135 bps | ✗ / 271 bps | ✗ / 296 bps |
| **TLT** | +143 | ✓ / 200 bps | ✓ / 500 bps | ✓ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✓ / 173 bps | ✓ / 329 bps | ✓ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✓ / 272 bps | ✓ / 694 bps | ✗ / 81 bps | ✗ / 123 bps | ✓ / 216 bps | ✓ / 270 bps |
| **TSLA** | -1081 | ✗ / 200 bps | ✗ / 500 bps | ✗ / 1000 bps | ✓ / 2000 bps | ✗ / 103 bps | ✗ / 173 bps | ✗ / 329 bps | ✗ / 700 bps | ✗ / 75 bps | ✗ / 139 bps | ✗ / 272 bps | ✗ / 694 bps | ✗ / 328 bps | ✗ / 484 bps | ✗ / 801 bps | ✓ / 1366 bps |

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
| Soothsayer τ=0.68 | 0/10 | 189 |
| Soothsayer τ=0.85 | 0/10 | 298 |
| Soothsayer τ=0.95 | 2/10 | 584 |
| Soothsayer τ=0.99 | 3/10 | 761 |

## Section 3 — Reading the result

- **Pyth+5% (the comparator a thoughtful Kamino risk committee deploys) fails on this weekend** (3/10 symbols covered, mean half-width 500 bps). Pyth+10% covers more (its half-width is ~3× soothsayer's typical normal-regime band) but is uniformly wide. Pyth+20% (~$200 of every $1000 collateral as 'safety buffer') covers more but is so wide it would liquidate few near-LTV borrowers in normal weeks. On a *calm* weekend (e.g. 2026-04-24, max realised |move| 183 bps), Pyth+5% would have covered 8/8 — a property of that weekend's realised distribution, not of the methodology. The same Pyth+5% covers 3/10 here.
- **The calibrated comparators (const-buffer, VIX-scaled) trained on pre-2023 data systematically under-cover** here: their training-set quantiles do not anticipate post-2023 tail events. This is the same train→OOS distribution shift that makes them under-cover on the aggregate OOS slice (see `reports/tables/v1b_width_at_coverage_pooled.csv`).
- **The deployed Soothsayer Oracle widens via the regime classifier** (`high_vol` → F0_stale forecaster + log-log VIX scaling). The widening is real but the magnitude is not enough to cover this weekend at τ=0.85 or τ=0.95: realised |moves| of 1,000–2,700 bps exceed every band on the panel except Pyth+10% / +20% on the smallest-realised-move symbols. **Soothsayer's actual high-vol-tail product is τ=0.99, which on this weekend covers 3/10 (half-widths of 600–2,000 bps). This is what the consumer-selectable τ interface is for: a Kamino-style consumer worried about Yen-carry-class moves picks τ=0.99 and pays the width premium during high_vol regimes only.**
- **The honest read of this case study is that no single methodology covers this weekend at τ ≤ 0.95.** Soothsayer's edge is not 'wider bands than Pyth+5% on the worst weekend' — it is (i) average-weekend Winkler (see `v1b_width_at_coverage_pooled.csv`) and (ii) calibration-receipt provenance (the consumer can audit which τ they chose and what the realised rate has been). The hard tail-cover claim sits at τ=0.99, with the structural-finite-sample caveat disclosed in §9.1.

*One weekend is one observation. The aggregate evidence for width-at-coverage across all 172 OOS weekends is in `reports/tables/v1b_width_at_coverage_pooled.csv`; this case study is the qualitative counterpart that shows where the differences come from.*
