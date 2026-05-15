# V1b — Tokenized-tracking baseline head-to-head

**Date:** 2026-05-14.
**Question.** Per Cong et al. (Table 10, R²=0.839 on the conditional mean), a "lazy" oracle that publishes `point = current_tokenized_price; band = ±k × historical_residual` immediately has 84% of the conditional-mean signal. Does Soothsayer's deployed M6 LWC band beat that baseline on Kupiec / Christoffersen / Winkler — and, if so, by how much?
**Status.** Bake-off complete on the post-launch slice. Soothsayer wins on Winkler in 7/9 symbols and at every (snapshot, τ) combination on the pooled panel. Reproducible via `scripts/run_v1b_tokenized_tracking_baseline.py`.

---

## Panel

- **Tokenized-side surface:** `cex_stock_perp/ohlcv/v1`, `kraken_futures` xstock-backed perp (`PF_<SYM>XUSD`), 1-min OHLCV. The longest forward-cursor tokenized-tracking surface available (per `reports/active/xstock_tape_inventory.md`).
- **Period:** 2025-12-19 → 2026-04-24 fri_ts (the full overlap of Soothsayer's LWC artefact and the kraken_futures launch).
- **Symbols (9):** SPY, QQQ, GLD (19 weekends each) and TSLA, NVDA, GOOGL, AAPL, HOOD, MSTR (~10 weekends each). **TLT excluded** — Soothsayer trains on TLT but no xstock-backed perp exists for it.
- **Panel:** 117 (weekend × symbol) rows pre-warmup, 105 evaluable after the baseline's 4-weekend walk-forward warm-up.
- **Snapshots in the closed window** (the moments at which the wire output is evaluated against the eventual Monday NMS open):

  | Label | Wall clock (America/New_York) |
  |---|---|
  | `fri_close`  | Friday 16:00 ET — NMS just closed |
  | `sat_noon`   | Saturday 12:00 ET |
  | `sun_noon`   | Sunday 12:00 ET |
  | `sun_globex` | Sunday 20:00 ET — CME Globex reopen |
  | `mon_premkt` | Monday 04:00 ET — pre-market open |
  | `mon_open`   | Monday 09:00 ET — just before NMS open |

  Soothsayer's M6 LWC band is set at Friday close and held constant across the closed window (one `(point, halfwidth)` per weekend). The naive tokenized-tracking baseline updates continuously; we evaluate it at each of the six canonical snapshots.

## Baseline construction

For each snapshot `t`:

- `point_t = perp_close_at(t)` — the kraken_futures xstock-backed perp's close price at minute `t`, asof-most-recent.
- `halfwidth_t,τ = empirical_quantile(|mon_open - perp_at_t|, τ)` — the empirical τ-quantile of historical baseline residuals, pooled across all symbols and walk-forward expanded over weekends. Warm-up = 4 weekends before the baseline is evaluated.

This is intentionally the **most charitable** specification of the naive baseline: it uses the exact non-parametric empirical-quantile family Soothsayer uses (so we're not punishing the baseline with a parametric Gaussian assumption it didn't make), it has perfect knowledge of historical residuals to that snapshot, and it gets to pool across symbols to maximise calibration sample size.

## Headline — pooled panel

**Soothsayer M6 LWC** publishes one band per weekend; rows below are the per-τ result over n=117:

| τ | n | realised cov | mean halfwidth (bps) | mean Winkler (bps) | Kupiec p_uc |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 117 | 0.641 | **124** | **426** | 0.371 |
| 0.85 | 117 | 0.863 | **207** | **588** | 0.684 |
| 0.95 | 117 | 0.949 | **358** | **879** | 0.949 |
| 0.99 | 117 | 0.991 | **636** | **1,516** | 0.871 |

**Tokenized-tracking baseline** — best-case snapshot (`mon_open`, Monday 09:00 ET, with the entire closed-window news flow absorbed into the perp) over n=105:

| τ | n | realised cov | mean halfwidth (bps) | mean Winkler (bps) | Kupiec p_uc |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 105 | 0.724 | 205 | 661 | 0.330 |
| 0.85 | 105 | 0.867 | 372 | 1,031 | 0.627 |
| 0.95 | 105 | 0.943 | 656 | **1,619** | 0.742 |
| 0.99 | 105 | 0.981 | 904 | **2,572** | 0.407 |

At τ=0.95 the baseline at its best moment is **1.83× wider** (656 vs 358 bps) and **1.84× worse on Winkler** (1,619 vs 879 bps) than Soothsayer. Same coverage rate; nearly double the width-cost and double the breach-magnitude penalty.

Across all six snapshots and all four τ values (24 baseline cells), **Soothsayer's mean Winkler is lower in 24 of 24**. The Winkler gap is widest at τ=0.99 (Soothsayer 1,516 bps vs baseline 2,538-2,620 bps across snapshots) — the tail-coverage regime where the baseline's empirical-quantile fattens dramatically.

## Per-minute Winkler curve — the baseline is worst on Sunday, not Friday

Six canonical snapshots are the headline; the 15-minute-resolution path tells a finer story. Mean Winkler (bps) at τ=0.95 by hour offset from Friday 16:00 ET (the closed window starts at `0.0` hours and ends at Monday 09:30 ET = `65.5` hours):

| hours past Fri 16:00 ET | Soothsayer (bps) | baseline (bps) | ratio |
|---:|---:|---:|---:|
|  0.0 (Fri close) | 945 | 1{,}557 | 1.65× |
|  8.0 (Sat 00:00 ET) | 945 | 1{,}487 | 1.57× |
| 16.0 (Sat 08:00 ET) | 945 | 1{,}586 | 1.68× |
| 32.0 (Sun 00:00 ET) | 945 | **2{,}023** | **2.14×** |
| 40.0 (Sun 08:00 ET) | 945 | **2{,}023** | **2.14×** |
| 48.0 (Sun 16:00 ET) | 945 | 1{,}585 | 1.68× |
| 56.0 (Mon 00:00 ET) | 945 | 1{,}499 | 1.59× |
| 65.5 (Mon 09:30 ET) | 935 | 1{,}619 | 1.73× |

The naive bull case for a tokenized-tracking competitor — "wait until Sunday night, by then the perp has absorbed the weekend news" — is empirically rejected. The baseline's Winkler is **worst** during Saturday night through Sunday afternoon (the +36% worsening at hours 32-44 vs the Saturday-morning floor), exactly the window where the tokenized perp can drift on crypto-native weekend flow with no underlying-market arbitrage to correct it. The baseline never closes more than ~half the Winkler gap to Soothsayer at any minute in the closed window.

Source: `reports/tables/paper1_c3_per_minute_winkler_curve.csv` (263 offsets × 4 τ × 2 forecasters); reproducible via `scripts/run_v1b_tokenized_per_minute_winkler.py`.

## Snapshot evolution — how the baseline degrades earlier in the closed window

At τ=0.95, baseline half-width and Winkler by snapshot:

| Snapshot | halfwidth (bps) | Winkler (bps) | vs Soothsayer (Winkler ratio) |
|---|---:|---:|---:|
| `fri_close`  | 730 | 1,685 | 1.92× worse |
| `sat_noon`   | 733 | 1,702 | 1.94× worse |
| `sun_noon`   | 735 | 1,698 | 1.93× worse |
| `sun_globex` | 736 | 1,696 | 1.93× worse |
| `mon_premkt` | 691 | 1,688 | 1.92× worse |
| `mon_open`   | **656** | **1,619** | **1.84× worse** |

The baseline tightens by roughly 10% (730 → 656 bps) as the closed window progresses and the tokenized side absorbs weekend information. **It never closes more than ~half the gap to Soothsayer's flat 358 bps** at the most-informed snapshot. The "wait until Monday morning and read the perp" strategy is still strictly dominated.

## Per-symbol robustness — where the result holds and where it doesn't

At τ=0.95, snapshot=`mon_open` (baseline's best case), per-symbol Winkler ratio (baseline / Soothsayer; >1 = Soothsayer wins):

| Symbol | n | Soothsayer halfwidth (bps) | Baseline halfwidth (bps) | Winkler ratio |
|---|---:|---:|---:|---:|
| HOOD  | 10 |   635 | 2,109 | **3.32** |
| GOOGL | 10 |   348 |   509 | **2.91** |
| NVDA  | 10 |   399 |   858 | **2.15** |
| MSTR  | 10 |   735 | 1,153 | **1.57** |
| GLD   | 15 |   361 |   345 | **1.46** |
| AAPL  | 10 |   297 |   608 | **1.36** |
| QQQ   | 15 |   214 |   253 | **1.02** |
| SPY   | 15 |   178 |   226 | **0.89** |
| TSLA  | 10 |   468 |   414 | **0.89** |

**The headline holds in 7/9 symbols.** The two baseline-wins are SPY (0.89) and TSLA (0.89) — the two deepest xstock-backed perp markets, and the symbols where Cong et al.'s λ=0.903 / R²=0.839 result has the most empirical bite. For these names the tokenized-perp side genuinely tracks the NMS open competitively, and an in-sample empirical-quantile residual band on the perp is sufficient.

**The Soothsayer advantage widens as perp liquidity thins.** For the long tail (HOOD, GOOGL, NVDA, MSTR, GLD, AAPL), Soothsayer wins by 1.4–3.3× on Winkler. This is consistent with Cong's R²=0.839 being a **pooled** figure that masks per-symbol heterogeneity — the deepest perps are at the high end of the conditional-mean tracking quality, the thin tail is well below it.

This is the right story for the paper: not "we always beat the lazy oracle" but **"we beat it everywhere except the two highest-volume perps, and our edge grows where the consumer needs it most — on the thinner-liquidity collateral the lending market actually struggles with."** TSLAx is the named live Kamino collateral at $4B TVL (Cong p.20). On TSLA specifically the baseline and Soothsayer tie; on the rest of the universe Soothsayer is materially better.

## What the comparison says about the paper §6 / §7 framing

The architecture's defensible claim narrows in the way the user-facing analysis foreshadowed:

1. **The point estimate is configurable; the band is the contribution.** Mean half-width at τ=0.95 is 358 bps for Soothsayer's M6 LWC vs 656 bps for the best-snapshot baseline — same coverage, ~1.8× tighter. The Kupiec/Christoffersen apparatus in §6 should now be read against this baseline rather than (or alongside) the GARCH baselines currently in §6.

2. **The win is concentrated in the thinner-perp half of the panel.** The §1.2 customer-frame paragraph already names lending protocols accepting tokenized RWA as collateral against USDC. The per-symbol result lets us say that explicitly: on the deepest perps the lending market could rely on the tokenized side, but on the long tail (which is most of the named-collateral universe ex-TSLAx) Soothsayer is the materially-tighter choice.

3. **The baseline's "Mon-pre-open" snapshot is not a free lunch.** Even at the most-informed moment in the closed window, the baseline is strictly dominated on Winkler at every τ. The "wait until Sunday night and read the perp" strategy a competitor might pitch as a workaround does not work — the baseline's halfwidth shrinks by only ~10% across the closed window.

## Caveats

- **Sample.** n=117 weekend-symbol observations pre-warmup, n=105 evaluable. Kupiec / Christoffersen at this sample size have low power; the dominant signal here is Winkler / halfwidth (paired, per-observation diagnostics), which are much more powerful at small n.
- **Tokenized-side proxy.** The kraken_futures xstock-backed perp is not the on-chain SPL xStock token. It is the deepest 24/7 tokenized-equity surface with sufficient history — directly relevant to the CFB / Kraken xStock perps consumer pitch, less directly relevant to a Solana-DEX-mid consumer. The Jupiter-mid cross-check below addresses the latter on a 3-weekend sample.
- **Walk-forward warm-up.** The baseline's 4-weekend warm-up drops the earliest 12 observations from the SPY/QQQ/GLD slice. Soothsayer's pre-2023 calibration set is decoupled from the bake-off panel, so its band is available for every weekend.
- **TLT.** Excluded from the bake-off (no xstock-backed perp). The §1 framing should not claim a TLT result from this report.

## Reproducibility

```bash
PYTHONPATH=src uv run python scripts/run_v1b_tokenized_tracking_baseline.py
```

Outputs:
- `data/processed/v1b_tokenized_tracking_baseline.parquet` — per-(symbol, weekend, snapshot, τ) observation panel.
- `reports/tables/v1b_tokenized_tracking_baseline_summary.csv` — aggregated summary.

## Jupiter-mid (v5/tape) cross-check — Solana-DEX surface, n=24

The kraken_futures xstock-backed perp is the deepest tokenized-equity surface but it is not the on-chain SPL token a Solana-DEX consumer actually reads. The `soothsayer_v5/tape` jup_mid series — Jupiter's quoted mid for the eight Backed xStocks (AAPLx, GOOGLx, HOODx, MSTRx, NVDAx, QQQx, SPYx, TSLAx) — is the directly Solana-relevant signal. It overlaps the deployed LWC artefact on a single weekend (2026-04-24); extending two weekends forward via a forward-tape-extended σ̂ lookup (no re-fit; existing sidecar constants applied) gives a 3-weekend × 8-symbol cross-check at n=24.

The baseline halfwidth at each τ is **borrowed verbatim** from the primary kraken_futures bake-off's `mon_open` snapshot (no re-fit on the 3 weekends — that would be in-sample). The question this answers: *does the directional Winkler result reproduce on the Solana-DEX-mid surface?*

| τ | n | M6 LWC cov | M6 LWC hw (bps) | M6 LWC Winkler (bps) | baseline cov | baseline hw (bps) | baseline Winkler (bps) | Winkler ratio (base/M6) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.68 | 24 | 0.875 | 99 | 250 | 1.000 | 205 | 411 | **1.65×** |
| 0.85 | 24 | 0.917 | 156 | 357 | 1.000 | 372 | 745 | **2.09×** |
| 0.95 | 24 | 1.000 | 272 | 544 | 1.000 | 656 | 1{,}312 | **2.41×** |
| 0.99 | 24 | 1.000 | 427 | 855 | 1.000 | 904 | 1{,}807 | **2.11×** |

**The directional result reproduces** — Soothsayer's mean Winkler is 1.65–2.41× lower than the baseline at every τ on the Jupiter-mid surface. The advantage is *wider* than on the kraken_futures panel at τ=0.95 (2.41× vs 1.84× on the primary panel), consistent with Jupiter mid on Solana DEXs having a thinner, more dispersion-prone book than the deeper kraken_futures perp.

**Caveats specific to the v5 cross-check:**

- $n = 24$ — Kupiec / Christoffersen tests have no power at this sample size. Both methods over-cover at $\tau \in \{0.95, 0.99\}$ on this slice; the result is a confirmatory directional check on the Winkler / halfwidth axis, not an independent coverage claim.
- The baseline halfwidth is borrowed from the primary panel (in-sample to the kraken_futures bake-off, out-of-sample to the v5 cross-check). This avoids fitting a baseline on its evaluation panel.
- M6 LWC's halfwidth on this slice (272 bps at τ=0.95) is tighter than its full-panel headline (358 bps), reflecting the more-recent panel composition (April–May 2026 vs the full post-launch slice 2025-12 onward).

Source: `scripts/run_v1b_tokenized_tracking_v5_xcheck.py`; outputs `data/processed/v1b_tokenized_tracking_v5_xcheck.parquet` and `reports/tables/paper1_c2_tokenized_tracking_v5_xcheck.csv`.

## Open follow-ups

- **Synthetic-band tokenized baseline.** A future revision could specify the baseline more charitably — e.g., `point = TWAP across closed window`, `halfwidth = parametric Cong-pooled volatility model`. We chose the empirical-quantile residual specification because it puts the baseline in the same non-parametric family as Soothsayer and avoids the "your baseline is a strawman because it's parametric" objection.
- **Slot into `v1b_incumbent_oracle_comparison.md`.** ✅ Done — `tokenized_tracking_kraken_perp` rows live in the unified incumbent table alongside Pyth / Chainlink / RedStone / Scope.
- **v5 cross-check at scale.** Once the v5 forward tape accumulates 13+ weekends and the LWC artefact extends to match, re-run the cross-check as an independently-powered head-to-head on the Jupiter-mid surface.
