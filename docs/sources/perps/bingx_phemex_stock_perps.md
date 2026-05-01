# `BingX + Phemex — Stock Perpetuals (small-X-coverage CEX panel)` — Methodology vs. Observed

> **Combined-venue file rationale.** Both BingX and Phemex are small-X-coverage CEX stock-perp venues (3 + 1 X-suffix tickers respectively, vs. Kraken's 9, Gate.io's 12, HTX's 6). They share the same role in the soothsayer comparator stack — minor cross-CEX dispersion contributors to the §1.1 Paper-1 panel — and their methodologies are similar enough that a single file is more useful than two thin ones. Where their methodologies differ materially (BingX's **NCSK-prefix** alternate-issuer tickers; Phemex's **6-source-with-min-3-quorum** index logic), the differences are called out per-section. **If a future probe reveals NCSK to be a meaningfully different issuer-class than Backed, this file should split.**

---

**Last verified:** `2026-04-29`
**Verified by:** *BingX:* `https://bingx.com/en/learn/article/what-is-nvdax-nvidia-tokenized-stock` (cited via 2026-04-29 search; "26 tokenized stock futures markets backed by institutional liquidity providers such as **NCKS**"), `https://bingx.com/en/price/tesla-tokenized-stock-xstock` (cited via search), `https://bingx.com/en/learn/article/what-are-the-top-tokenized-stocks-xstocks-on-solana` (cited via search). BingX-specific futures index/mark documentation **was not surfaced in our 2026-04-29 probe** — link rot or thin documentation; the index methodology depth gap is a §6 open question. *Phemex:* `https://phemex.com/help-center/Introduction-to-Mark-price-Index-Price` (accessed 2026-04-29; the load-bearing source for index + mark formulas — 6-source spot index, exclude-outliers-then-average, mark = Median(Price1, Price2, Contract Price)), `https://phemex.com/contract/mark-price` (cited via search), `https://phemex.com/contract/index-price` (cited via search), `https://phemex.com/how-to-buy/tesla-xstock` (cited via search; confirms TSLAX on Phemex).
**Version pin (BingX):** **3 X-suffix tickers** (xStock-backed, e.g., `NVDAX/USDT`, `TSLAX/USDT`, `AAPLX/USDT`) **+ 13 NCSK-prefix tickers** (alternate-issuer; the soothsayer coverage memo notes "NCSK issuer needs methodology investigation; may differ from Backed"). The BingX promotional material describes "26 tokenized stock futures markets backed by institutional liquidity providers such as NCKS" — note `NCKS` (with K) in the marketing copy vs. `NCSK` (with S) in the soothsayer memo; one of these is a typo / variant naming. Reconciling the issuer name and verifying NCSK vs Backed-class is a §6 gating task.
**Version pin (Phemex):** **1 X-suffix ticker** (`TSLAX/USDT` per the Phemex marketing page) **+ 12 plain-suffix tickers** (synthetic / cash-settled). Index methodology applies the same 6-source spot-aggregation formula to all contract types per the help-center page, but constituent exchanges (Binance / Coinbase / OKX / Kraken / Bitstamp / Bitfinex) **don't list xStocks**, so the xStock-specific constituent set is necessarily different. Methodology depth gap: same as BingX.
**Role in soothsayer stack:** `comparator (continuous-quoting; minor cross-venue dispersion contributors)` — both venues are minor contributors to the §1.1 cross-CEX dispersion panel for Paper 1. Phemex's mark-price formula (`Median(Price1, Price2, Contract Price)` with 15-minute MA) is structurally similar to HTX's median-of-three; BingX's methodology is opaque enough that we cannot compare. **Practical consequence**: at Paper 1 §1.1 figure-time, treat BingX + Phemex as two of five xStock-backed venues for the cross-venue dispersion measurement, but do not depend on either as the primary reference comparator.
**Schema in scryer:** **planned, gated on item 45.** Same as Gate.io + HTX. **Phemex OHLCV companion is explicitly blocked** per [`scryer/wishlist.md`](../../../../scryer/wishlist.md) line 50 ("Phemex OHLCV → US-IP geo-blocked at CDN; same geo-block class as Binance + Bybit; tickers fetcher works (different endpoint, no geo-gate); OHLCV stays deferred"). I.e., Phemex tickers are scryer-readable; OHLC bars are not from operator IP without a VPN-access path. **This is Pattern 3 from the final report.**

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

**BingX:**
- The promotional material states that BingX's xStock-class perps are "backed by institutional liquidity providers such as NCKS [or NCSK]." This language is closer to "issuer / liquidity-provider on the underlying token side" than to "index methodology" — i.e., NCSK / NCKS is plausibly an alternate xStock issuer (not Backed Finance), where the underlying tokenized-stock instrument is issued by a different counterparty.
- **Index price + mark price methodology for BingX xStock perps is not surfaced in our 2026-04-29 probe.** BingX has BTC/ETH-perp methodology pages but the xStock-specific application is not documented at this depth. **§6 open question.**

**Phemex:**
- **Index methodology (per help-center page accessed 2026-04-29):** "Phemex [BTC] indices are sourced from the last traded prices of multiple spot markets. These include: Binance, Coinbase, Okex, Kraken, and Bitfinex." (5 named, but the formula references 6 — Bitstamp is plausibly the 6th per cross-reference in another search hit.) **Methodology**: "Every time Phemex computes an index, it begins by removing the highest and lowest last traded prices found amongst these 6 exchanges. The final index price is the average value of the remaining last traded prices."
- **Index refresh rate:** "The Phemex index engine refreshes and publishes new indices every second."
- **Outlier-rejection rule** (the Phemex-specific defensive mechanism): "Phemex excludes and invalidates sources with broken connections or updates that have stalled for more than 15 seconds. At any given time, the index engine requires at least **3 valid sources** to compute an average price. If the number of valid sources drops below 3, the index price will remain unchanged."
- **Mark price formula:** `Mark Price = Median(Price1, Price2, Contract Price)` where:
  - Price1 = Index × (1 + Last Funding Rate × (Time until next Funding / Funding period))
  - Price2 = Index + Moving Average (15-minute Basis), refreshed every 1 minute
  - Contract Price = the live last-traded price on the Phemex orderbook
- **Critical caveat (xStock-relevant):** the 5-named-source list is BTC-specific. xStocks don't trade on Binance/Coinbase/Bitfinex/OKX. **The xStock-specific constituent list is opaque and is the key §6 question for Phemex.**

### 1.2 Cadence / publication schedule

- **BingX:** index/mark cadence not surfaced in our probe. Funding cadence likely 8h (BingX BTC/ETH default) but xStock-specific not pinned.
- **Phemex:** index per-second (per docs); mark continuous; 15-min basis MA refreshed every 1 minute; funding rate cadence and cap **not surfaced** in the help-center page accessed today.

### 1.3 Fallback / degraded behavior

- **BingX:** unmeasured.
- **Phemex:** the **min-3-valid-sources** rule is the explicit defensive primitive. Below 3 valid sources, the index "remains unchanged" — i.e., stale-hold on the previous index value. **For xStocks, where the constituent venue set is necessarily smaller than for BTC** (because xStocks don't trade on the canonical 5-6 venues), the min-3 quorum may be more frequently binding. **§6 question.**
- **Phemex outlier exclusion (15s stall threshold)** — any source whose most recent print is >15 seconds stale is excluded. Tighter than HTX's 10-min / 100-data-point window.

### 1.4 Schema / wire format

- **BingX:** REST API at `api.bingx.com/openApi/swap/...`. Schema gated on probe.
- **Phemex:** REST API at `api.phemex.com/...`. Schema gated on probe. **OHLCV endpoint is geo-blocked** from operator IP per [`scryer/wishlist.md`](../../../../scryer/wishlist.md) line 50; tickers endpoint is reachable.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet (both venues):** **planned, gated on item 45.** Phemex OHLCV explicitly blocked per the geo-block notice above; tickers should be capturable.
- **Pre-cutover artefacts:** none.
- **Coverage in current tape:** none from soothsayer side.
- **BingX coverage (3 X-suffix + 13 NCSK-prefix):** per the soothsayer coverage matrix probed 2026-04-28. The 13 NCSK-prefix tickers are an alternate-issuer surface that may or may not share the Backed-issued xStock underlier — needs methodology investigation.
- **Phemex coverage (1 X-suffix `TSLAX` + 12 plain):** narrow X-suffix coverage; Phemex is primarily a synthetic-stock-perp venue with one xStock-backed exception.

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| BingX lists 3 X-suffix xStock-backed perps + 13 NCSK-prefix alternate-issuer perps. | Confirmed via the soothsayer coverage matrix (probed 2026-04-28). | **confirmed** |
| BingX's NCSK / NCKS issuer is a different counterparty from Backed Finance. | **Plausible structurally** — the BingX promotional language ("backed by institutional liquidity providers such as NCKS") is consistent with NCSK being an issuer/LP, but **the methodology investigation is gated** — same xStock-class reference asset under a different issuer with potentially different on-chain proof-of-reserves and corp-action handling. **§6 open question.** | **plausible, gated** |
| BingX's index methodology is a weighted average across multiple CEXs. | **Unverified from public surface accessed today.** | **TODO** |
| Phemex's index = exclude-highest-and-lowest of 6 spot sources, average the rest. | Confirmed per the help-center page accessed 2026-04-29. | **confirmed (for BTC-class indices)** |
| Phemex's xStock-class index uses the same exclude-outliers methodology. | **Plausible structurally**, but the BTC-named constituent set (Binance / Coinbase / Bitstamp / Kraken / OKX / Bitfinex / Huobi) **does not list xStocks**. The xStock-specific constituent set is opaque. | **plausible, opaque** |
| Phemex requires at least 3 valid sources for the index; falls back to stale-hold on the previous value below. | Confirmed per docs. **For xStocks, the constituent venue set is plausibly smaller**, so the 3-source quorum may be binding more often. | **confirmed (mechanism), unmeasured (xStock-specific)** |
| Phemex's mark = Median(Price1, Price2, Contract Price) with 15-minute basis MA. | Confirmed per docs. The median-of-three structure is similar to HTX's (see [`perps/htx_stock_perps.md`](htx_stock_perps.md) §1.1) but applied uniformly to all contracts (no median-vs-EMA contract-tier distinction noted). | **confirmed (by docs)** |
| TSLAX/USDT is on Phemex. | Confirmed per the Phemex how-to-buy page. | **confirmed** |
| Phemex OHLCV endpoint is geo-blocked from operator IP. | Confirmed per [`scryer/wishlist.md`](../../../../scryer/wishlist.md) line 50. **Pattern 3 (operational geo-block on data-source endpoints).** | **confirmed (operational)** |
| Cross-venue dispersion on the same xStock at Friday close is observable on BingX + Phemex vs. other xStock-backed perps. | **TODO when scryer item 45 lands.** Same gating as Gate.io + HTX. | **TODO** |
| BingX + Phemex are minor contributors to the cross-CEX dispersion panel (compared to Kraken's 9 / Gate.io's 12 / HTX's 6 X-suffix). | Confirmed structurally — 3 + 1 X-suffix tickers between them is the smallest coverage among the 5 xStock-backed venues. | **confirmed** |

---

## 4. Market action / consumer impact

Both venues are **minor cross-venue dispersion contributors** to the Paper 1 §1.1 incumbent-benchmark panel. Their roles diverge slightly:

- **BingX (alternate-issuer wildcard via NCSK-prefix)** — if NCSK is a different issuer with materially different proof-of-reserves or corp-action handling than Backed, the NCSK-prefix tickers add a **second xStock-class issuer** to soothsayer's addressable comparator set. Either:
  - NCSK is a Backed-Finance equivalent (same instrument, different distribution channel) → marginal additional dispersion contributor;
  - NCSK is a wrapped-or-different-structure issuer → the price may not be apples-to-apples with Backed's xStocks, and BingX's NCSK-prefix tickers should be excluded from the cross-venue dispersion analysis or treated as a separate panel.
- **Phemex (small X-coverage, public methodology)** — the one X-suffix ticker (TSLAX) is a single data point against the panel. Phemex's documented methodology (6-source exclude-outliers + min-3-quorum + median-of-three mark) is **structurally clean** — the cleanest publicly-documented index methodology among the 5 xStock-backed perp venues.
- **Soothsayer (xStock weekend bands)** — both venues' marks at Friday close are minor cross-references vs. Kraken / Gate.io / HTX. Including them in the §1.1 figure adds robustness to the dispersion measurement; excluding them does not significantly weaken the argument.
- **Backed Finance (issuer ground truth)** — BingX's NCSK relationship is the most interesting unknown: if NCSK is an alternate Backed-class issuer, soothsayer's RWA-class generalisation (Paper 1 §10.5) extends naturally; if it's a different structure entirely (synthetic, market-maker LP backed), the cross-issuer comparator opens.
- **MarginFi / Kamino / Drift / Save / Loopscale / Jupiter Lend** — neither BingX nor Phemex perp marks are consumed by Solana lending markets directly. Signal, not oracle source.
- **Paper 1 §1.1 / §1.2** — included in the cross-CEX dispersion + volume-decay analysis but not load-bearing for either argument.
- **Paper 1 §10.5** — BingX's NCSK relationship is the most interesting cross-issuer line; if a future probe finds NCSK to be a meaningfully different issuer, this could be a sub-section in §10.5 about "the soothsayer methodology applies to *any* tokenized-equity issuer regardless of distribution channel."
- **Paper 3 §6 / §7** — not load-bearing.
- **Public dashboard (Phase 2)** — minor rows alongside the primary 3 venues.

---

## 5. Known confusions / version pitfalls

- **BingX's "NCSK" vs "NCKS" — verify the spelling.** The BingX marketing page says "NCKS" (with K); soothsayer memory says "NCSK" (with S). One is a typo. The actual issuer name affects any §6 outreach.
- **NCSK ≠ Backed.** Don't conflate the NCSK-prefix tickers with the X-suffix tickers on BingX — different issuers (probably), different proof-of-reserves, potentially different corp-action handling.
- **Phemex's 5-named-source list is BTC-class.** Don't assume the same constituent set for xStock perps; the xStock constituent set is opaque.
- **Phemex's min-3-source quorum may bind more frequently for xStocks** because the xStock-listing CEX universe is smaller than the BTC-listing one. Stale-hold pattern at the index level is a real failure mode.
- **Phemex's 15-second stall threshold is tighter than HTX's 10-min window.** Different defensive philosophies — Phemex prefers fast exclude-and-fall-back; HTX prefers slower exclude-and-recover.
- **Phemex OHLCV is geo-blocked from US IPs.** Not unique to soothsayer — same CDN-level geo-block as Binance + Bybit. Tickers reachable.
- **BingX index/mark methodology is opaque at the depth a reconciliation file requires.** Don't infer methodology from BTC-perp documentation; xStock-class is plausibly different.
- **Funding cadence + cap unverified for both venues.** Don't assume Kraken's ±0.25%/h or Hyperliquid's ±4%/h.
- **TSLAX-only on Phemex.** Other xStock symbols on Phemex are plain-suffix synthetic; don't treat the synthetic versions as comparable to Backed-issued tokens.
- **`X` ambiguity in tickers.** BingX uses `NVDAX` / `TSLAX` etc.; Gate.io uses `NVDAX_USDT` / `TSLAX_USDT`; Kraken uses `PF_NVDAXUSD` / `PF_TSLAXUSD`. Ticker formatting is per-venue and not portable.

---

## 6. Open questions

1. **Verify scryer phases 55-58 (item 45) actually shipped end-to-end and the cex_stock_perp tape is live.** Same Pattern 1 as Gate.io + HTX. **Phemex OHLCV stays geo-blocked** per Pattern 3.
2. **Pin the BingX NCSK / NCKS issuer identity.** **Why it matters:** if NCSK is a different issuer-class than Backed, the cross-issuer comparator is a Paper 1 §10.5 sub-finding. **Gating:** outreach to BingX support or NCSK direct.
3. **Pin BingX's xStock-perp index methodology and constituent set.** **Why it matters:** without this, BingX cannot be cleanly included in the §1.1 dispersion analysis. **Gating:** docs probe (deeper than today's surface) or outreach.
4. **Pin Phemex's xStock-class constituent set.** **Why it matters:** the BTC-named 6-source list does not transfer; the xStock-specific list is what determines whether the min-3-quorum binds. **Gating:** docs probe or outreach.
5. **Confirm funding cadence + cap on both venues.** **Why it matters:** cross-venue funding-signal comparison. **Gating:** docs probe.
6. **Has Phemex's min-3-source quorum ever bound for an xStock contract** (causing index stale-hold)? **Why it matters:** if yes, that's a real-world failure event for the cross-venue dispersion analysis (Phemex would silently report an unchanged index while other venues' marks moved). **Gating:** scryer item 45 + Phemex-side analysis.
7. **Cross-venue Friday-close mark dispersion across all 5 xStock-backed perp venues** including BingX X-suffix + Phemex TSLAX. **Why it matters:** load-bearing §1.1 figure. **Gating:** scryer item 45 + analysis script joining 5 venues.
8. **Whether the BingX NCSK-prefix tickers are 24/7-tradable like the X-suffix ones, or have different operational hours.** **Why it matters:** differing operational windows would complicate the dispersion analysis. **Gating:** BingX docs / support.

---

## 7. Citations

*BingX:*
- [`bingx-nvdax-learn`] BingX. *What Is Nvidia Tokenized Stock and How to Buy NVDA xStock?*. https://bingx.com/en/learn/article/what-is-nvdax-nvidia-tokenized-stock. Cited via 2026-04-29 search results.
- [`bingx-tslax-price`] BingX. *Tesla tokenized stock (xStock) (TSLAX) Price*. https://bingx.com/en/price/tesla-tokenized-stock-xstock. Cited via 2026-04-29 search results.
- [`bingx-xstocks-survey`] BingX. *Top 7 Tokenized Stocks (xStocks) on Solana to Trade in 2026*. https://bingx.com/en/learn/article/what-are-the-top-tokenized-stocks-xstocks-on-solana. Cited via 2026-04-29 search results.

*Phemex:*
- [`phemex-mark-price-help`] Phemex. *Introduction to Mark Price & Index Price*. https://phemex.com/help-center/Introduction-to-Mark-price-Index-Price. Accessed: 2026-04-29. The load-bearing source for the index + mark formulas.
- [`phemex-mark-page`] Phemex. *Mark Price (Futures)*. https://phemex.com/contract/mark-price. Cited via 2026-04-29 search results.
- [`phemex-index-page`] Phemex. *Index Price*. https://phemex.com/contract/index-price. Cited via 2026-04-29 search results.
- [`phemex-tslax-howto`] Phemex. *How to Buy Tesla xStock (TSLAX) Guide*. https://phemex.com/how-to-buy/tesla-xstock. Cited via 2026-04-29 search results.

*Cross-references:*
- [`coverage-matrix-memory`] Soothsayer agent memory. *CEX stock-perp coverage map (paper 1 incumbent benchmark)*. (Internal-memory note, probed 2026-04-28; BingX 3 X-suffix + 13 NCSK-prefix; Phemex 1 X-suffix + 12 plain.)
- [`scryer-wishlist-item-45-phemex-block`] Scryer internal. [`scryer/wishlist.md`](../../../../scryer/wishlist.md) line 50 — Phemex OHLCV US-IP geo-blocked. The load-bearing operational caveat.
- [`gate-companion`] Soothsayer internal. [`docs/sources/perps/gate_io_stock_perps.md`](gate_io_stock_perps.md). Sister venue with broader xStock coverage.
- [`htx-companion`] Soothsayer internal. [`docs/sources/perps/htx_stock_perps.md`](htx_stock_perps.md). Sister venue with median-of-three mark structurally similar to Phemex's.
- [`kraken-perp-companion`] Soothsayer internal. [`docs/sources/perps/kraken_futures_xstocks.md`](kraken_futures_xstocks.md). Primary xStock-backed CEX comparator with the deepest tape.
