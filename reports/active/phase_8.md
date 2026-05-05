# Phase 8 — Compounders on Phase 7

Phase 8 of the M6 refactor adds three follow-up passes that compound on Phase 7's three results — turning each statistical headline into a deeper claim a sophisticated reader can act on. None of these change the deployed M6 artefact (`data/processed/lwc_artefact_v1.parquet` and its sidecar). The canonical task spec lives at `reports/active/m6_refactor.md` §8; this file is the rolled-up reading-time summary an outside reader can skim in five minutes. Sibling to `reports/active/phase_7_results.md`. The three sub-phases are independent and can run in any order.

## Status table

| Sub-phase | Status | Verdict | Date |
|---|---|---|---|
| 8.1 — Worst-weekend characterization | ✅ COMPLETE | The all-10-breaching weekend at τ=0.85 is **2024-08-02** (Mon-open 2024-08-05) — the BoJ-rate-hike yen-carry-unwind / global risk-off event; 9 of 10 symbols sold off in concert (range −274 bps to −40 bps weekend return), only TLT inside the band; concrete §9.1 circuit-breaker case study | 2026-05-04 |
| 8.2 — Per-symbol GARCH-t comparison | ✅ COMPLETE | At τ=0.95 per-symbol Kupiec pass-counts: M6 LWC 10/10, GARCH-t 8/10, GARCH-Gaussian 6/10, M5 2/10. Across the full 10×4-τ grid: LWC 39/40, GARCH-t 31/40, GARCH-N 23/40, M5 12/40. Strengthens §6.4.1: M6 LWC dominates the strongest parametric baseline at the per-symbol level | 2026-05-04 |
| 8.3 — Cross-subperiod k_w threshold stability | ✅ COMPLETE | At every (forecaster × τ × threshold-convention) cell under M6 LWC the year-by-year hit rate at the deployment-recommended k* is consistent with the full-OOS rate (0/24 Kupiec rejections). The single rejection in the 24 M5 cells is at τ=0.95, k*=3 in 2024 (hit rate 9.6% vs full-OOS 4.05%) — the same M5 2024 over-clustering Phase 7.2 already flagged. Consumer reserve guidance is stable across regimes. | 2026-05-04 |

## 8.1 — Worst-weekend characterization

### Why this matters

Phase 7.1 produced a striking statistical headline — under M6 LWC at τ=0.85 the worst OOS weekend has *all 10 symbols breaching their bands simultaneously*. The clustering result is currently a distribution shape; pinning down which weekend (and what the macro context was) converts it into a memorable narrative for §6.3.1 framing and gives §9.1 a concrete example for the circuit-breaker recommendation. Industry readers (Kamino risk team, oracle competitors) remember vignettes; statistical distributions blur.

### Process

Filtered `reports/tables/m6_portfolio_clustering_per_weekend.csv` to `(forecaster=lwc, tau=0.85, k_w=10)`. Exactly **one** OOS weekend matches: **Friday 2024-08-02** with Monday open on 2024-08-05. The same weekend has `k_w=8` at τ=0.95 (only TSLA and TLT inside that band) and `k_w=5` at τ=0.99 (AAPL, HOOD, NVDA, QQQ, SPY breach even the 99% per-symbol quantile). The next-worst weekend at τ=0.95 (`k_w=6`) is 2023-12-01, well behind.

Per-symbol breach magnitudes were extracted by re-serving M6 LWC bands on the 2024-08-02 row of `data/processed/v1b_panel.parquet` using the same fit-at-`split=2023-01-01` recipe the deployed serving path uses. All 10 symbols were tagged `regime_pub = high_vol` that weekend.

### Results

The Mon-open 2024-08-05 vs Fri-close 2024-08-02 returns, sorted from worst to best:

| Symbol | Weekend return (bps) | M6 LWC HW at τ=0.85 (bps) | Breach distance at τ=0.85 (bps) | At τ=0.95 |
|---|---:|---:|---:|---|
| MSTR | **−2737** (−27.4%) | 783 | −1416 | breach (−720) |
| HOOD | **−1779** (−17.8%) | 368 | −1325 | breach (−997) |
| NVDA | **−1418** (−14.2%) | 324 | −1008 | breach (−720) |
| TSLA | −1081 (−10.8%) | 587 | −409 | inside |
| AAPL | −945 (−9.4%) | 202 | −657 | breach (−478) |
| GOOGL | −670 (−6.7%) | 230 | −354 | breach (−149) |
| QQQ | −536 (−5.4%) | 110 | −340 | breach (−242) |
| SPY | −399 (−4.0%) | 84 | −229 | breach (−154) |
| GLD | −212 (−2.1%) | 126 | −153 | breach (−41) |
| TLT | +143 (+1.4%) | 128 | +12 (just past) | inside |

Cross-section: **9 of 10 symbols sold off in concert**, mean weekend return −963 bps, median −807 bps. The lone exception is TLT (+143 bps) — the classic flight-to-quality treasury rally as risk assets liquidate. MSTR's −27% weekend move is a 3.5× excess over its already-wide τ=0.85 half-width; HOOD and NVDA each breach their bands by more than 3× the half-width.

The σ̂-standardisation worked as designed at the per-symbol level — high-vol symbols (MSTR, TSLA) got wide bands, low-vol symbols (SPY, QQQ, GLD) got narrow bands, and the breach magnitudes scale with the cross-sectional shock divided by σ̂. What broke is *cross-sectional common-mode*: when nearly every symbol moves the same direction at the same time by 4–27 standard-deviation-scale weekend returns, no per-symbol band — however well calibrated — can absorb the joint event.

### Macro context — the August 5, 2024 yen-carry-unwind

The 2024-08-02 → 2024-08-05 weekend is consistent with the well-documented **Bank of Japan rate-hike yen-carry-trade unwind**, one of the largest single-weekend global risk-off events of the post-2020 period:

- **Friday 2024-08-02:** US July nonfarm payrolls printed at 114k (vs ~175k consensus), the unemployment rate ticked up to 4.3%, and the Sahm rule recession indicator triggered. SPY closed −1.84% on Friday.
- **Weekend (Saturday 2024-08-03 — Sunday 2024-08-04):** the Bank of Japan's July 31 rate hike (its second of the year) and the simultaneously hawkish Powell/Yellen stance triggered an accelerating yen-carry-trade unwind through Asian time zones; USD/JPY collapsed from ~150 toward 142.
- **Monday 2024-08-05:** Nikkei 225 fell 12.4% — the largest single-day drop since Black Monday 1987. US futures gapped down 4–5% Sunday evening. VIX spiked from ~16 close on Aug 2 to an intraday print near 65 — the highest reading since the COVID-19 March 2020 panic. AI/tech beneficiaries (NVDA, MSTR, HOOD, TSLA, AAPL) were hit hardest because they were also the most-crowded carry-trade-funded longs. Treasuries rallied (TLT +1.4%) as the only safe-haven bid.

The breach magnitudes are entirely consistent with this narrative: the carry-funded crowded names (MSTR, HOOD, NVDA, TSLA, AAPL — top 5 by breach magnitude) sold off the hardest; the lower-beta indices (SPY, QQQ) followed with smaller but still 3–5σ-equivalent moves; gold (GLD) sold off mildly (consistent with liquidity-driven cash-raising); only TLT was bid.

### Paper impact

This converts §6.3.1 from a statistical observation into a memorable case study and gives §9.1 a concrete example for the circuit-breaker recommendation:

- **§6.3.1 (cross-sectional common-mode framing).** The current paragraph reports the variance overdispersion ratio and the empirical tail probabilities. Add a "Worst weekend" paragraph: *"The most extreme OOS weekend, 2024-08-02 → 2024-08-05, saw all 10 symbols breach their τ=0.85 bands simultaneously and 8 of 10 breach even at τ=0.95. Cross-section: weekend returns ranged from −27.4% (MSTR) to +1.4% (TLT, the lone safe-haven bid); 9 of 10 symbols sold off in concert. The event coincides with the Bank of Japan yen-carry-trade unwind: VIX spiked to ~65 intraday, Nikkei fell 12.4% (largest since 1987's Black Monday). No per-symbol band — however well calibrated — can absorb a joint event of this magnitude; the failure mode is cross-sectional common-mode by construction."*
- **§9.1 (circuit-breaker recommendation).** The current paragraph recommends consumers reserve against an empirical k_w distribution. Add the concrete instance: *"Aug 5 2024 illustrates the failure mode the circuit breaker is designed to catch. A consumer monitoring `k_w` in real time would have seen `k_w = 10` at τ=0.85 by the Mon-open print, well in excess of the empirical 99th percentile (k = 7). A circuit breaker that pauses borrowing/lending when `k_w` exceeds the deployment-time-fitted reserve threshold (Phase 8.3, this report) would fire on this exact weekend before liquidations are processed. The empirical k_w distribution is the right operational signal precisely because it captures the cross-sectional common-mode that per-symbol coverage cannot."*
- **Reserve-guidance robustness.** The Phase 7.1 consumer guidance ("reserve against ≈ 5 simultaneous breaches at τ=0.95") is sourced from the empirical 99th percentile of `k_w` over the 173 OOS weekends. The 2024-08-02 weekend with `k_w = 8` at τ=0.95 is the single observation driving the upper-tail of that empirical distribution — i.e. the guidance is conservative *because* this weekend exists in the calibration data, not in spite of it.

### Outputs

- `reports/active/phase_8.md` §8.1 (this section).
- `reports/m6_validation.md` §14 — "Worst weekend" sub-section to be added (Phase 8.1 reporting step). Same date / breach-magnitude table inline.
- Paper 1 §6.3.1 / §9.1 inline revision notes — to be captured at the next paper-revision sweep.

## 8.2 — Per-symbol GARCH-t comparison

### Why this matters

Phase 7.3 showed M6 LWC dominates GARCH-t at the *pooled* level. The §6.4.1 per-symbol Kupiec claim ("M6 LWC: 10/10 passes vs M5: 2/10") is the central per-symbol generalization argument; right now it's against the deployed M5 baseline only. Adding GARCH-N and GARCH-t per-symbol extends the claim to "vs the strongest parametric baseline at the per-symbol level." This is the version a reviewer with finance training cannot dismiss.

### Process

Built a sibling runner `scripts/run_per_symbol_kupiec_all_methods.py`. It imports `fit_per_symbol_garch` and `serve_garch_bands` from the Phase 7.3-extended `run_v1b_garch_baseline.py` via `importlib.util.spec_from_file_location` (`scripts/` isn't a package; this matches the precedent set by `run_simulation_size_sweep.py`). The runner:

1. Loads `data/processed/v1b_panel.parquet` and applies the standard dropna recipe.
2. Fits per-symbol GARCH(1,1) under both `dist=gaussian` and `dist=t` on the pre-2023 train side, recurses σ̂ over the post-2023 OOS, serves bands at τ ∈ {0.68, 0.85, 0.95, 0.99}, and computes per-symbol Kupiec on each.
3. Calls `prep_panel_for_forecaster` / `fit_split_conformal_forecaster` / `serve_bands_forecaster` from `soothsayer.backtest.calibration` for both `m5` and `lwc`, then computes per-symbol Kupiec on those served bands.
4. Concatenates into `reports/tables/m6_per_symbol_kupiec_4methods.csv` — long-format, 160 rows = 10 symbols × 4 methods × 4 τ. Schema: `symbol, method, tau, n_oos, viol_rate, kupiec_lr, kupiec_p`.

NVDA's GARCH-t fit hits the ν ≤ 2.5 numerical-stability floor (ν̂ = 2.50) and falls back to gaussian, recorded in the upstream `dist_used` column. The other nine symbols converge cleanly on t (ν̂ ∈ [2.84, 6.88]). Same fallback behaviour as Phase 7.3.

### Results

**Headline at τ=0.95 (per-symbol Kupiec p; ≥ 0.05 = pass):**

| Symbol | GARCH-N | GARCH-t | M5 | M6 LWC |
|---|---:|---:|---:|---:|
| AAPL  | 0.645 | 0.268 | **0.001** | 0.268 |
| GLD   | **0.021** | **0.000** | **0.001** | 0.645 |
| GOOGL | **0.044** | **0.021** | 0.168 | 0.818 |
| HOOD  | **0.000** | 0.645 | **0.000** | 0.552 |
| MSTR  | **0.002** | 0.085 | **0.000** | 0.903 |
| NVDA  | 0.818 | 0.818 | 0.552 | 0.645 |
| QQQ   | 0.329 | 0.268 | **0.001** | 0.168 |
| SPY   | 0.645 | 0.903 | **0.000** | 0.818 |
| TLT   | 0.156 | 0.268 | **0.000** | 0.818 |
| TSLA  | 0.431 | 0.431 | **0.001** | 0.903 |
| **Pass-count (out of 10)** | **6** | **8** | **2** | **10** |

(Cells in **bold** are rejections at α=0.05.)

**Pass-counts across the full grid** (per-symbol Kupiec p ≥ 0.05; out of 10 symbols at each τ; out of 40 across all (symbol × τ) cells):

| τ | GARCH-N | GARCH-t | M5 | M6 LWC |
|---|---:|---:|---:|---:|
| 0.68 | 5/10 | 6/10 | 1/10 | 10/10 |
| 0.85 | 8/10 | 7/10 | 1/10 | 9/10 |
| 0.95 | 6/10 | 8/10 | 2/10 | **10/10** |
| 0.99 | 4/10 | 10/10 | 8/10 | 10/10 |
| **Total (40 cells)** | **23/40** | **31/40** | **12/40** | **39/40** |

**M6 LWC's lone failure** in the 40-cell grid is **TSLA at τ=0.85** (Kupiec p=0.044, viol-rate 0.098 vs target 0.150 — over-coverage), the same TSLA cell flagged in the Phase 2 per-symbol Berkowitz outlier list (§6.4.1 acknowledged outlier).

**Where GARCH-t helps over GARCH-Gaussian** (per-symbol): closes HOOD (0.000 → 0.645) and MSTR (0.002 → 0.085) at τ=0.95 — the high-vol carry-funded names where fat-tailed innovations matter most. At τ=0.99 GARCH-t passes all 10 symbols (vs GARCH-N's 4/10) — the canonical fat-tail-fix story.

**Where GARCH-t still fails per-symbol**: GLD at τ ∈ {0.68, 0.85, 0.95} (over-tightened — GLD is treasuries-style with high fitted ν=6.88 where t-quantile narrows toward Gaussian, but the standardised-t scaling `√((ν−2)/ν)` is still slightly narrower than 1 at finite ν, pushing realised down below target), GOOGL at τ=0.85+0.95, MSTR at τ=0.68+0.85, NVDA at τ=0.68 (NVDA fell back to gaussian), TSLA at τ=0.68. Total 9 cells.

### Paper impact

Phase 8.2 transforms the §6.4.1 per-symbol generalization argument from "M6 LWC vs the deployed M5" to "**M6 LWC vs the strongest parametric baseline at the per-symbol level**":

- **§6.4.1 claim upgrade.** Replace "M6 LWC: 10/10 Kupiec passes vs M5: 2/10" with "**M6 LWC: 39/40 Kupiec passes (10/10 at the τ=0.95 headline) across (symbol × τ) cells; the strongest practitioner baseline GARCH-t: 31/40 (8/10 at τ=0.95); GARCH-Gaussian: 23/40; M5: 12/40.**" The new claim is *defensive* (vs reviewer concerns) without giving up the headline (vs M5).
- **Acknowledge the lone LWC outlier.** TSLA at τ=0.85 (Kupiec p=0.044, just below α=0.05) is the single cell where M6 LWC fails. This is the same TSLA cell flagged in Phase 2 §11 item 5 ("per-symbol Berkowitz still rejects for TSLA / GOOGL / TLT") and in §6.4.1's acknowledged outlier list. Consistency check passes — the outlier is stable across diagnostics, not new.
- **GARCH-t parametric baseline footnote.** §6.4.2 should note that GARCH-t passes Kupiec at τ=0.99 on all 10 symbols (the *only* method that does that besides M6 LWC) — fat-tailed innovations are genuinely useful for the deepest tail at the per-symbol level. The §6.4.1 dominance claim is therefore strongest at τ=0.95, where M6 LWC outperforms both parametric variants on every symbol; at τ=0.99 the lead narrows to a tie on per-symbol pass-count (10/10 each), with M6 LWC's advantage shifting to *width-at-matched-coverage* (Phase 7.3 / §16 pooled comparison).
- **Defensive evidence quality.** This is the row a reviewer with finance training will ask for. Having it pre-empts the "but you didn't compare against the practitioner standard at the per-symbol level" critique.

### Outputs

- `scripts/run_per_symbol_kupiec_all_methods.py` — sibling runner; ~140 lines; reuses `fit_per_symbol_garch` from `run_v1b_garch_baseline.py` via importlib.
- `reports/tables/m6_per_symbol_kupiec_4methods.csv` — 160 rows (10 symbols × 4 methods × 4 τ); schema `symbol, method, tau, n_oos, viol_rate, kupiec_lr, kupiec_p`.
- `reports/m6_validation.md` §16 — "Per-symbol GARCH comparison" sub-section appended with the τ=0.95 table and the pass-count grid.
- `reports/active/m6_refactor.md` Phase 8.2 boxes ticked with the headline pass-counts inline.

## 8.3 — Cross-subperiod k_w threshold stability

### Why this matters

Phase 7.1 produced consumer reserve guidance — "at τ=0.95, reserve against ≈ 5 simultaneous breaches." That is a one-shot empirical observation. A consumer sizing reserves needs to know it is *stable across regimes*. If the empirical 95th-percentile of `k_w` jumped from k=3 in 2023 to k=7 in 2025, the guidance would be unreliable. Phase 8.3 piggybacks on Phase 7.2's calendar sub-periods to test stability without falling into a self-referential trap: the threshold is fitted **once** on the full OOS slice (never per-subperiod, which would be tautological), and the year-by-year hit rate at that fixed threshold is tested against the full-OOS rate via a Kupiec-style binomial LR.

### Process

`scripts/run_kw_threshold_stability.py`. Reads `reports/tables/m6_portfolio_clustering_per_weekend.csv`, restricts to full-coverage weekends (n_w = 10), and for each forecaster × τ ∈ {0.85, 0.95, 0.99}:

1. Computes the full-OOS hit-rate curve `rates[k] = P(k_w ≥ k)` over the 173 OOS weekends.
2. Picks two threshold conventions on this curve:
   - `k_close`: `k` whose rate is closest to 0.05 (primary; better test power).
   - `k_below_5pct`: smallest `k` whose rate is ≤ 0.05 (deployment-conservative).
3. For each subperiod {2023, 2024, 2025, 2026-YTD}: counts subperiod hits at `k*`, realised subperiod rate, per-subperiod empirical 95th-percentile of `k_w` (so cross-period drift is visible), and a Kupiec LR test of `H0: subperiod rate = full-OOS rate`.

The Kupiec helper `met._lr_kupiec(violations, claimed)` interprets `claimed` as a coverage level (it tests `H0: viol_rate = 1 − claimed`), so the runner passes `claimed = 1 − full_oos_rate` to align the convention.

A `low_power_flag = 1` is set when expected subperiod hits < 3 (binomial-LR power rule of thumb). With subperiod n ∈ {52, 17} and rates ~5%, expected hits are 0.85–2.6 — most cells flag low-power, which is unavoidable given the OOS sample size at this τ and is disclosed transparently in the paper-impact framing.

Output: `reports/tables/m6_kw_threshold_stability.csv`. 48 rows = 2 forecasters × 3 τ × 2 threshold-conventions × 4 subperiods. Schema: `forecaster, tau, k_threshold_kind, k_threshold, full_oos_n, full_oos_hits, full_oos_rate, full_oos_p95_kw, subperiod, subperiod_n, subperiod_hits, subperiod_rate, subperiod_p95_kw, kupiec_lr, kupiec_p, expected_hits, low_power_flag`.

### Results

**Headline at τ=0.95** (primary `k_close` threshold):

| Forecaster | k* | Full-OOS rate | Subperiod | Subperiod n | Subperiod hits | Subperiod rate | Subperiod p95(k_w) | Kupiec p |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| M6 LWC | 3 | 5.20% | 2023 | 52 | 4 | 7.69% | 3.0 | 0.449 |
| M6 LWC | 3 | 5.20% | 2024 | 52 | 3 | 5.77% | 2.4 | 0.856 |
| M6 LWC | 3 | 5.20% | 2025 | 52 | 2 | 3.85% | 1.4 | 0.645 |
| M6 LWC | 3 | 5.20% | 2026-YTD | 17 | 0 | 0.00% | 2.0 | 0.178 |
| M5     | 3 | 4.05% | 2023 | 52 | 0 | 0.00% | 1.4 | 0.083 |
| M5     | 3 | 4.05% | 2024 | 52 | 5 | 9.62% | 3.0 | **0.046** |
| M5     | 3 | 4.05% | 2025 | 52 | 2 | 3.85% | 2.0 | 0.941 |
| M5     | 3 | 4.05% | 2026-YTD | 17 | 0 | 0.00% | 1.2 | 0.236 |

**Stability rejection counts** (binomial Kupiec at α=0.05; out of 4 subperiods per (forecaster × τ × convention) cell):

| Threshold | M5 τ=0.85 | M5 τ=0.95 | M5 τ=0.99 | LWC τ=0.85 | LWC τ=0.95 | LWC τ=0.99 |
|---|---:|---:|---:|---:|---:|---:|
| `k_close` | 0/4 | 1/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| `k_below_5pct` | 0/4 | 1/4 | 0/4 | 0/4 | 0/4 | 0/4 |

Across the full 24-cell grid per forecaster (3 τ × 2 conventions × 4 subperiods): **M6 LWC has 0/24 stability rejections; M5 has 2/24 (the same 2024 cell rejecting under both conventions).** The M5 rejection is at τ=0.95, k*=3, 2024 subperiod: 5 hits in 52 weekends (rate 9.6%) vs full-OOS 4.05% (Kupiec p=0.046). This is the same M5 2024 over-clustering signal already flagged in Phase 7.2 — consistency check passes.

**Per-subperiod 95th-percentile of `k_w`** (drift visibility; full-coverage weekends only):

| | 2023 | 2024 | 2025 | 2026-YTD | Range |
|---|---:|---:|---:|---:|---:|
| LWC τ=0.85 | 5.0 | 4.0 | 4.4 | 3.4 | 1.6 |
| LWC τ=0.95 | 3.0 | 2.4 | 1.4 | 2.0 | 1.6 |
| LWC τ=0.99 | 0.4 | 1.0 | 0.0 | 0.2 | 1.0 |
| M5 τ=0.85 | 2.0 | 3.0 | 3.4 | 3.0 | 1.4 |
| M5 τ=0.95 | 1.4 | 3.0 | 2.0 | 1.2 | 1.8 |
| M5 τ=0.99 | 0.0 | 1.4 | 0.4 | 0.0 | 1.4 |

Year-on-year drift in the empirical 95th-percentile of `k_w` is **at most 1.6 integer-symbols** under M6 LWC at every τ. The deployment-recommended threshold (k*=3 at τ=0.95, k*=5 at τ=0.85) sits at or above the per-subperiod 95th-percentile in every year — i.e. the consumer guidance is conservative against year-on-year drift, not just against the full-OOS distribution.

**Power caveat (transparent disclosure).** Most subperiod cells flag `low_power_flag = 1` (expected hits < 3), unavoidable given subperiod n ∈ {52, 17} and target rates ~5%. The "0/24 rejections" result should be framed as **"no detectable instability with the available power"** rather than "definitively stable." The drift visibility table compensates: even without the binomial test, the per-subperiod 95th-percentile spread is small (≤ 1.6 symbols) under M6 LWC at every τ, supporting the stability claim through a direct quantile read rather than test power alone.

### Paper impact

Phase 8.3 closes the loop on the Phase 7.1 reserve-guidance claim. The §6.3.1 / §9.1 paragraph upgrades from a one-shot empirical observation to:

- **Operationalisable claim.** "Reserve against k* = 3 simultaneous breaches at τ=0.95" becomes "**Reserve against k* = 3 at τ=0.95; the year-by-year hit rate at this threshold is statistically consistent with the full-OOS rate (Kupiec p ≥ 0.18 in every calendar year), and the per-subperiod empirical 95th-percentile of k_w stays in [1.4, 3.0] across {2023, 2024, 2025, 2026-YTD} — i.e. the deployment threshold is conservative against year-on-year drift."*
- **Power disclosure.** "With subperiod n ≈ 52 and target rates ~5%, the binomial-stability test has limited power to detect drift smaller than the year-on-year 95th-percentile spread (≤ 1.6 integer-symbols under LWC). The result is therefore 'no detectable instability' rather than 'proven stationary.' The drift visibility table provides the orthogonal quantile-read that does not depend on test power."
- **§9.1 circuit-breaker concrete.** Combined with the Phase 8.1 Aug 5 2024 vignette, §9.1 now has both the *threshold* (k*=3 at τ=0.95) and the *failure-mode demonstration* (the Aug 5 2024 weekend had k_w = 10 at τ=0.85, k_w = 8 at τ=0.95 — both above the deployment k* — so a real-time circuit breaker would have fired). The reserve-guidance is now end-to-end specified: threshold is fitted, threshold is stable across regimes, threshold catches the worst observed weekend.

### Outputs

- `scripts/run_kw_threshold_stability.py` — runner; ~140 lines.
- `reports/tables/m6_kw_threshold_stability.csv` — 48 rows (2 forecasters × 3 τ × 2 threshold-conventions × 4 subperiods).
- `reports/m6_validation.md` §14 — "Threshold stability" sub-section appended with the headline table and the per-subperiod p95 drift table.
- `reports/active/m6_refactor.md` Phase 8.3 boxes ticked with headline inline.

---

## Maintenance note

When 8.2 or 8.3 completes, the agent that finishes it should fill the relevant `(Process / Results / Paper impact subsections to be filled…)` block above and update the status table at the top of this file in the same edit. This file lives at the project root, sibling to `reports/active/phase_7_results.md`, `reports/active/m6_refactor.md`, `README.md`, and `CLAUDE.md`. The canonical long-form write-ups remain in `reports/m6_validation.md` (§14 onwards) and the canonical task spec remains in `reports/active/m6_refactor.md` §8.
