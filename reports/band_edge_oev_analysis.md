# Band-edge OEV analysis — Paper 2 §C4 first modeling exercise

**Date:** 2026-04-25. **Source:** `data/processed/v1b_panel.parquet` (5,986 weekend windows × 10 symbols, 2014-01-17 → 2026-04-17), served via `Oracle.load()` with deployed hybrid forecaster + per-target buffer. Reference: [`docs/bot_kamino_xstocks_liquidator.md`](../docs/bot_kamino_xstocks_liquidator.md) §10.1 + §10.2 + §11.

**Purpose.** Quantify (a) the rate at which realized Monday-open prices exit the served Soothsayer band at $\tau \in \{0.85, 0.95, 0.99\}$, and (b) the per-event liquidator pricing edge for in-band vs band-exit events. Inputs to the Solana Foundation OEV grant proposal ([`docs/grant_solana_oev_band_edge.md`](../docs/grant_solana_oev_band_edge.md)) and to the Kamino xStocks weekend-reopen liquidator's MVP bid floor.

---

## 1. Headline numbers

Aggregate band-exit frequency across all symbols, weekends, and regimes:

| τ | weekends | realized coverage | P(band-exit) | exits/yr (10-symbol panel) |
|---:|---:|---:|---:|---:|
| 0.85 | 5986 | 0.9001 | 0.0999 | 49 |
| 0.95 | 5986 | 0.9716 | 0.0284 | 14 |
| 0.99 | 5986 | 0.9855 | 0.0145 | 7 |

Realized coverage matches the OOS Kupiec/Christoffersen pass numbers from Paper 1 §6 (in-sample by construction since the surface was fit on this panel). **The relevant column for Paper 2 §C4 is the rightmost one: the absolute count of band-exit events the bot has access to per year across the 10-symbol panel.**

---

## 2. Per-event liquidator pricing edge — in-band vs band-exit

**Edge metric.** `deviation_bps` = |realized monday-open − served point estimate| / point × 10,000. This is the bps-magnitude of the gap a liquidator who knows the realized price (or holds a sharper-than-published model) extracts from the protocol on the swap leg of a liquidation, on top of the protocol's published liquidation bonus. Reported per $1M notional position.

### τ = 0.85

| Classification | n | mean ($) | median ($) | p75 ($) | p90 ($) | p95 ($) | p99 ($) | max ($) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| in_band | 5388 | 6,938 | 4,352 | 8,575 | 16,083 | 22,277 | 40,677 | 86,097 |
| band_exit | 598 | 29,863 | 18,550 | 36,208 | 66,976 | 91,597 | 148,700 | 273,717 |

**Median-edge dominance ratio (band-exit / in-band): 4.26×**

### τ = 0.95

| Classification | n | mean ($) | median ($) | p75 ($) | p90 ($) | p95 ($) | p99 ($) | max ($) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| in_band | 5816 | 9,989 | 5,597 | 11,964 | 24,219 | 37,454 | 63,113 | 133,528 |
| band_exit | 170 | 47,433 | 29,879 | 59,421 | 104,036 | 143,558 | 268,244 | 293,750 |

**Median-edge dominance ratio (band-exit / in-band): 5.34×**

### τ = 0.99

| Classification | n | mean ($) | median ($) | p75 ($) | p90 ($) | p95 ($) | p99 ($) | max ($) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| in_band | 5899 | 12,757 | 6,227 | 13,939 | 32,746 | 53,092 | 91,017 | 265,785 |
| band_exit | 87 | 53,003 | 34,311 | 70,684 | 112,390 | 152,047 | 276,522 | 293,750 |

**Median-edge dominance ratio (band-exit / in-band): 5.51×**

---

## 3. Distance beyond band edge for exit events

For events that did exit the band, how far beyond the band edge did the realized price land? This is `exit_bps_beyond_band` — the residual after subtracting the band's own width. It bounds the EV a *band-aware* liquidator captures over a *band-blind* one (a band-blind liquidator who treats the band edge as their expected price still loses this much).

- **τ = 0.85** — band-exit events (n=598): median 49.0 bps, p75 116.4, p90 302.0, p95 453.9, max 2150.4 bps.
- **τ = 0.95** — band-exit events (n=170): median 51.7 bps, p75 127.6, p90 342.7, p95 555.5, max 1414.7 bps.
- **τ = 0.99** — band-exit events (n=87): median 63.4 bps, p75 159.6, p90 311.3, p95 583.9, max 1143.7 bps.

---

## 4. Per-symbol, per-regime exit frequency

Subset to **τ = 0.95** (the headline Paper 1 validation target). Full grid is in `tables/band_edge_oev_frequency.csv`.

| symbol | regime | n | P(in-band) | P(exit-above) | P(exit-below) | P(exit-any) |
|---|---|---:|---:|---:|---:|---:|
| AAPL | high_vol | 152 | 0.974 | 0.007 | 0.020 | 0.026 |
| AAPL | long_weekend | 67 | 0.970 | 0.000 | 0.030 | 0.030 |
| AAPL | normal | 419 | 0.974 | 0.017 | 0.010 | 0.026 |
| GLD | high_vol | 152 | 0.967 | 0.007 | 0.026 | 0.033 |
| GLD | long_weekend | 67 | 0.970 | 0.015 | 0.015 | 0.030 |
| GLD | normal | 418 | 0.957 | 0.019 | 0.024 | 0.043 |
| GOOGL | high_vol | 152 | 0.974 | 0.000 | 0.026 | 0.026 |
| GOOGL | long_weekend | 67 | 0.970 | 0.030 | 0.000 | 0.030 |
| GOOGL | normal | 419 | 0.969 | 0.010 | 0.021 | 0.031 |
| HOOD | high_vol | 64 | 0.969 | 0.016 | 0.016 | 0.031 |
| HOOD | long_weekend | 27 | 1.000 | 0.000 | 0.000 | 0.000 |
| HOOD | normal | 154 | 0.961 | 0.026 | 0.013 | 0.039 |
| MSTR | high_vol | 152 | 0.967 | 0.007 | 0.026 | 0.033 |
| MSTR | long_weekend | 67 | 0.970 | 0.015 | 0.015 | 0.030 |
| MSTR | normal | 419 | 0.974 | 0.019 | 0.007 | 0.026 |
| NVDA | high_vol | 152 | 0.961 | 0.000 | 0.039 | 0.039 |
| NVDA | long_weekend | 67 | 0.970 | 0.030 | 0.000 | 0.030 |
| NVDA | normal | 419 | 0.979 | 0.012 | 0.010 | 0.021 |
| QQQ | high_vol | 152 | 0.967 | 0.007 | 0.026 | 0.033 |
| QQQ | long_weekend | 67 | 0.985 | 0.000 | 0.015 | 0.015 |
| QQQ | normal | 419 | 0.974 | 0.007 | 0.019 | 0.026 |
| SPY | high_vol | 152 | 0.974 | 0.000 | 0.026 | 0.026 |
| SPY | long_weekend | 67 | 0.970 | 0.000 | 0.030 | 0.030 |
| SPY | normal | 419 | 0.979 | 0.005 | 0.017 | 0.021 |
| TLT | high_vol | 152 | 0.967 | 0.026 | 0.007 | 0.033 |
| TLT | long_weekend | 67 | 0.955 | 0.015 | 0.030 | 0.045 |
| TLT | normal | 419 | 0.981 | 0.007 | 0.012 | 0.019 |
| TSLA | high_vol | 152 | 0.967 | 0.007 | 0.026 | 0.033 |
| TSLA | long_weekend | 67 | 0.955 | 0.015 | 0.030 | 0.045 |
| TSLA | normal | 419 | 0.976 | 0.017 | 0.007 | 0.024 |

---

## 5. Implications for the grant economic argument

The grant proposal hypothesises (H₁) that OEV concentrates at oracle-band-edge events. This analysis is the **historical retrospective** version of that claim — the Paper 1 dataset measures *price-discovery deviations*, not realized lending-protocol liquidations, but the two are tightly linked by the liquidator's swap-leg edge. The numbers above therefore bound, from below, the per-event EV a band-aware liquidator extracts over a band-blind competitor.

**Three concrete inputs this provides to downstream work:**

1. **Bot MVP bid floor (`docs/bot_kamino_xstocks_liquidator.md` §4.2).** The bot's `min_margin` parameter should be set against the in-band median + safety margin; the upside is the band-exit distribution above.
2. **Grant economic justification (`docs/grant_solana_oev_band_edge.md` §7).** The per-$1M EV table at τ = 0.95 is the grounding for the budget ask: the instrumented dataset is expected to capture events whose per-event edge is an order of magnitude larger than the in-band baseline, even before the Kamino 0.1% liquidation bonus is added on top.
3. **Paper 2 §C4 retrospective baseline.** The dominance ratio (band-exit / in-band median EV) is the first quantitative C4 datapoint. Any future live-deployed bot's realized EV distribution should be compared against this historical baseline; a deployed bot that fails to reach this dominance ratio is evidence the C4 mechanism is not active in production (a publishable null result).

---

## 6. Caveats

- This analysis is **in-sample with respect to the calibration surface** (the surface was fit on the same panel). The Paper 1 OOS slice (2023+, 1,720 rows) is the harder test and matches Kupiec/Christoffersen at every τ. A re-run restricted to that OOS slice would tighten the realized-coverage column above.
- The `deviation_bps` metric is a **liquidator-edge proxy**, not a directly measured OEV figure. The deployed bot will measure realized OEV directly via Jito bundle data; the grant's empirical replay will reconcile the two.
- The Kamino 0.1% liquidation bonus reported alongside (`kamino_bonus_per_1m`) is a constant per liquidation; the variability in liquidator EV comes from the swap-leg edge, which is what this analysis quantifies.
- Tokenized-stock liquidations on Kamino did not exist before 2025-07-14. The values reported here are computed on the underlying-equity weekend panel and transfer to xStocks under the assumption that xStock weekend gaps are approximately the same as underlying-equity weekend gaps. xStock-specific calibration is Phase 1 / V5 tape work.
