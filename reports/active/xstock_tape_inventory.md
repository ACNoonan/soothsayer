# xStock Price Tape Inventory — WS1 Phase 1

**Status:** Inventory complete; recommendation for WS1 Phase 2 primary surface stated below.
**Date:** 2026-05-10.
**Purpose:** Establish which scryer surface(s) carry usable xStock-relevant price observations across post-launch weekends, so WS1 Phase 2 (token-path-vs-band breach check) can be scoped against real coverage rather than assumed coverage.

## Headline

All four candidate scryer surfaces are **forward-cursor launchd-fetched** with no historical backfill before late 2025. The only surface with panel-grade depth is `cex_stock_perp/ohlcv`, which carries 18 complete Friday → Monday windows for SPY / QQQ / GLD back to 2025-12-26 and ~10 windows for the other equity tickers from mid-February 2026. Everything else is too short to support more than 1–3 weekends of evidence.

`geckoterminal/trades` is unusable: only one indexed pool, and it is not an xStock pool.

## Surface-by-surface

### 1. `cex_stock_perp/ohlcv/v1` — **PRIMARY surface for WS1 Phase 2**

- **Coverage:** 2025-12-22 → 2026-05-01.
- **Per-underlier depth (complete Fri → Mon windows):**
  - SPY, QQQ, GLD: **18 weekends** (2025-12-26 → 2026-04-24).
  - TSLA, NVDA, GOOGL, AAPL, HOOD, MSTR: ~10 weekends each (panel begins mid-Feb 2026).
  - TLT: not present in ohlcv (only in `cex_stock_perp/tape`).
- **Venue:** `kraken_futures` only (single source today). Instruments are `PF_<TICKER>XUSD` perps (e.g. `PF_TSLAXUSD`) with `backing_kind = "xstock_backed"`.
- **Resolution:** 1-minute OHLCV bars (`bar_open_ts`, `bar_close_ts` ~60 s apart). 1440 bars/day = full 24/7 perp coverage.
- **Schema:** `exchange, exchange_symbol, underlier_symbol, backing_kind, bar_open_ts, bar_close_ts, open, high, low, close, volume_base, volume_quote, trade_count, _schema_version=cex_stock_perp_ohlcv.v1`.
- **Caveat — what this actually measures.** A kraken_futures perp backed by xStocks is not the SPL xStock spot token. The perp can carry funding-driven premium / discount to spot. For Soothsayer's stated gap-risk-against-Monday-open use case this is fine — we want a 24/7 tradeable proxy for the closed-market equity reference — but the breach check measures whether the *kraken-futures-perp-mark* exited our band, not whether the *on-chain SPL token* did. We must label this explicitly in the WS1 write-up.
- **Caveat — sparse-trade bars.** First-row spot check: `volume_base = 0, trade_count = NaN` on many bars. Consistent with Cong's thin-liquidity finding for xStock-class instruments. Use `close` for the path value (carried forward through no-trade minutes) rather than VWAP.

### 2. `soothsayer_v5/tape/v1` — secondary surface (our own forward tape)

- **Coverage:** 2026-04-24 → 2026-05-10 (17 days; ~2.5 complete Fri → Mon windows).
- **Symbols:** AAPLx, GOOGLx, HOODx, MSTRx, NVDAx, QQQx, SPYx, TSLAx (all 8 Backed equities; **no GLD / TLT** — Backed does not tokenize those).
- **Resolution:** ~50 polls / symbol / hour (1224 rows / symbol / day, every ~70 s).
- **Schema highlights:** per poll, Chainlink (`cl_tokenized_px`, `cl_venue_px`, `cl_market_status`, `cl_age_s`) **and** Jupiter (`jup_bid`, `jup_ask`, `jup_mid`, `spread_bp`) side-by-side. `basis_bp = (jup_mid − cl_tokenized_px) / cl_tokenized_px × 1e4`.
- **Why useful despite the short window.** This is the *exact* surface a Nomad-shaped LP would price-anchor against: `jup_mid` is what Jupiter quotes on the spot venue. Cross-checking our band against `jup_mid` on the available weekends gives the most directly-relevant breach signal for the AMM-consumer pitch.
- **Sample at AAPLx 2026-05-03 (Sun):** `cl_tokenized_px = $281.47`, `jup_mid = $280.48`, `basis_bp = −35` → Jupiter quoted a 35 bp discount to Chainlink. Single observation; reported for sanity.
- **Loader available:** `soothsayer.sources.scryer.load_v5_window(start, end)`.

### 3. `dex_xstock/swaps/v1` — validation sample (one weekend only)

- **Coverage:** 2026-04-30 → 2026-05-04 (5 days; **one weekend window**, May 2–4).
- **Symbols:** all 8 xStock equities (AAPLx → TSLAx). **Note path discrepancy:** `CLAUDE.md` and the consumer guide reference `solana_dex/xstock_swaps`; on-disk path is `dex_xstock/swaps`. Update the consumer guide as a side-task.
- **Resolution:** swap-level, every actual on-chain trade. Density (2026-05-03 Sun): TSLAx 2445, NVDAx 1321, SPYx 888, MSTRx 762, QQQx 565, GOOGLx 416, AAPLx 215, HOODx 177.
- **Schema:** `signature, slot, block_time, dex_program, xstock_mint, xstock_symbol, counter_mint, counter_symbol, xstock_amount_lamports, counter_amount_lamports, price_per_xstock, trader, _schema_version`.
- **Quote currencies (TSLAx 2026-05-03):** USDC 2233 / WSOL 212. The USDC slice is directly comparable to our USD-denominated band; the WSOL slice needs SOL/USD multiplication.
- **DEX programs (TSLAx):** Raydium CLMM 900, Orca Whirlpools 658, Meteora DLMM 33, "other" 514, "aggregator" 340. Aggregator hits are routed (not single-pool); a per-pool filter is a Phase-2 design choice.
- **Why useful even at 1 weekend.** Ground-truth on-chain price for the one weekend it covers — the closest thing to "did the SPL token leave our band" we will get without backfill.
- **No `soothsayer.sources.scryer` loader exists yet.** Implementation gap for Phase 2.

### 4. `cex_stock_perp/tape/v1` — multi-venue tape (10 days)

- **Coverage:** 2026-05-01 → 2026-05-10 (10 days; ~2 weekends).
- **Venues:** broad multi-venue coverage on AAPL / GOOGL / HOOD / MSTR / NVDA / QQQ / SPY / TSLA — combinations of okx, bingx, kucoin_futures, phemex, mexc, gate, coinbase_intl, htx, kraken_futures, bitget (and crypto_com on SPY / QQQ). TLT only on `gate`. GLD only on `kraken_futures`.
- **Resolution:** 1800 rows / underlier / day → ~75 / hour aggregated across venues.
- **Schema:** `exchange, exchange_symbol, underlier_symbol, backing_kind, ts, mark_price, index_price, last_price, bid, ask, bid_size, ask_size, funding_rate, ...`.
- **Why parked, not primary.** Multi-venue is more methodologically attractive than `kraken_futures`-only, but the 10-day window only delivers ~2 weekends. Worth promoting once 26+ weekends accumulate; for now, use as a recent-window robustness cross-check against `ohlcv`.

### 5. `geckoterminal/trades/v1` — **OUT**

- **Coverage:** 2026-04-28 → 2026-05-10 (13 days), but **only one pool indexed**: mint `58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2`.
- **Pool identity:** does **not** match any xStock mint in `soothsayer.universe.XSTOCK_MINTS`. Price stats (median $84.14, range $83–$86 over 8K trades/day) are inconsistent with any xStock equity; likely a memecoin or low-cap SPL token captured incidentally by the `geckoterminal:trades:runner` launchd job.
- **Verdict:** unusable for WS1. If we want geckoterminal coverage on xStocks, that is a scryer-side fetcher-config change (add xStock pool addresses to the runner's pool registry), not a Soothsayer-side issue.

## Recommendation for WS1 Phase 2

**Use `cex_stock_perp/ohlcv` (kraken_futures) as the primary path surface,** with two complementary cross-checks:

1. **Primary panel** — replay our LWC band against the kraken_futures perp 1-min path on **18 weekends for SPY / QQQ / GLD** (full window 2025-12-26 → 2026-04-24) and **~10 weekends for TSLA / NVDA / GOOGL / AAPL / HOOD / MSTR** (mid-Feb 2026 onward). This is the panel.
2. **Sol-DEX quote cross-check** — for the 2–3 weekends since 2026-04-24, additionally replay against `soothsayer_v5/tape`'s `jup_mid` series. This is the most directly Nomad-relevant signal (what a Solana LP would actually quote against), but it carries no panel weight — just gives us a "does the breach pattern hold on the venue Nomad cares about" honest disclaimer.
3. **On-chain swap cross-check (n = 1 weekend)** — for the 2026-05-02 → 05-04 weekend, additionally replay against `dex_xstock/swaps` per-swap USDC prices. A single anecdote, but it is the only direct on-chain xStock-spot evidence we have.

**Honest reporting frame for the WS1 write-up:**

- Headline panel = "kraken_futures xstock-backed perp mark path vs Soothsayer band" on 18/10 weekends.
- The framing is *not* "did the SPL xStock token leave our band" (we lack the historical token tape for that). It is *"did a continuously-tradable proxy for the underlying fair value during the closed window leave our band"*.
- For the Nomad pitch specifically, the soothsayer_v5/tape cross-check is the closer-to-direct evidence (Jupiter quotes are the actual venue), and we report it as a 2-weekend supplement with the appropriate sample-size caveat.

## Implementation gaps surfaced

- No `load_cex_stock_perp_ohlcv` or `load_dex_xstock_swaps` helper in `soothsayer.sources.scryer`. WS1 Phase 2 will need to add these — they are thin loaders, ~30 lines each.
- The consumer guide (`docs/scryer_consumer_guide.md` §"Important Data Surfaces") lists `solana_dex / xstock_swaps`; on-disk path is `dex_xstock/swaps`. Update line 111.
- The consumer guide does not list `cex_stock_perp` at all. Add `cex_stock_perp / {ohlcv, tape}` to the table.

## Backfill / scryer wishlist items (not blocking WS1)

To extend the panel into the post-launch period Cong covers (July 2025 →):

1. **`dex_xstock/swaps`** backfill to 2025-07-01 (xStock launch). All inputs are public on-chain history; this is a fetcher-design question, not a data-availability one.
2. **`cex_stock_perp/tape`** backfill to 2025-12-01 (or to each venue's listing date) for multi-venue robustness.
3. **`geckoterminal/trades`** pool registry expansion to include the canonical xStock USDC pools (Raydium CLMM + Orca Whirlpool addresses per `dex_xstock/swaps`'s `dex_program` field).

All three are scryer-side and should go through `../scryer/wishlist.md` per the project's hard rules.

## Sources and reproducibility

All inventory commands run against `SCRYER_DATASET_ROOT = /Users/adamnoonan/Library/Application Support/scryer/dataset`. No upstream API calls; on-disk parquet only. Coverage windows are derived from `year=/month=/day=.parquet` partition keys; per-day rows are read from a single representative file (2026-05-03 Sunday where available); per-day densities and per-symbol coverage are reproduced by listing each `underlier=/symbol=/pool=` directory.
