# `Gate.io — Stock Perpetuals (xStock-backed + cash-settled mix)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://www.gate.com/help/futures/logical/22067/instructions-of-dual-price-mechanism-mark-price-last-traded-price` (cited via 2026-04-29 search; the dual-price mechanism — mark vs. last-traded), `https://www.gate.com/help/futures/logical/22069/index-price-calculation` (cited via search; the weighted-average index price formula), `https://www.gate.com/help/futures/futures-logic/27569/funding-rate-and-funding-fee` (cited via search; funding-rate methodology), `https://www.gate.com/learn/articles/no-account-no-limits-gate-x-stocks-opens-the-door-to-global-stock-trading/10108` (Gate's xStocks landing material, cited via search), the soothsayer-internal coverage matrix at `~/.claude/projects/.../memory/project_cex_stock_perp_coverage.md` (probed 2026-04-28). Direct WebFetch to Gate's price-index pages 403'd from operator IP — Gate has region-restricted access on some help pages; the search-result excerpts are the load-bearing source.
**Version pin:** **Gate.io xStocks Perpetual Futures (current 2026-04-29)** — **xStock-backed** (12 X-suffix tickers, e.g., `NVDAX_USDT`, `TSLAX_USDT`) plus **4 cash-settled** (plain-suffix). Leverage: 1× to 10× per the xStocks marketing material. **The most distinctive feature among CEX stock-perp venues per the soothsayer coverage matrix: Gate.io is the only venue that lists `TLT_USDT` (TLT = iShares 20+ Year Treasury Bond ETF) on the perp surface** — a single-venue Treasury-token comparator.
**Role in soothsayer stack:** `comparator (continuous-quoting; 24/7 against the same xStock-backed underlier soothsayer prices)` — Gate.io's X-suffix perps share the **exact same underlying instruments** soothsayer prices (no translation gap, unlike synthetic-perp venues). The Friday-close → Monday-open weekend window on Gate.io's NVDAX/TSLAX/QQQX is directly observable as a venue-side mark-price formula in production. Combined with [`perps/kraken_futures_xstocks.md`](kraken_futures_xstocks.md) and the other xStock-backed venues (HTX, BingX, Phemex), this is the **strongest §1.1 incumbent-benchmark panel** for Paper 1 (per the cross-CEX coverage memory note).
**Schema in scryer:** **planned, not yet shipped.** [`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 45 (`cex_stock_perp_tape.v1` + `cex_stock_perp_ohlcv.v1`); the wishlist index marks 45 as Done — phases 55-58 — but the tape is not yet live in our `dataset/` probe (cex_stock_perp dataset directory not present as of 2026-04-29). **TODO**: confirm whether scryer phases 55–58 actually shipped end-to-end (live partitions) or only the schema lock landed; if live, add a loader to `src/soothsayer/sources/scryer.py`. Cross-reference [Pattern 1 in this batch's final report] — this is the canonical "tape marked done in wishlist but not yet visible at the dataset root."

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

**Index price (per Gate's "Index Price Calculation" help page, via 2026-04-29 search):** weighted average across multiple exchanges:

> "Index Price = (A Constituent Price × A Constituent Weight) + (B Constituent Price × B Constituent Weight) + (C Constituent Price × C Constituent Weight) + ……"

**Constituent venues:** "Gate, Binance, OKX, Bybit, Bitget, Coinbase, KuCoin, MEXC, Gate Alpha, and PancakeSwap" (per the help page) — and "Gate selects appropriate index constituents for each trading pair based on market conditions and may adjust constituent weights from time to time, and reserves the right to modify index constituents and weights at any time without prior notice."

**For xStock-backed perps** (X-suffix: `NVDAX_USDT`, `TSLAX_USDT`, etc.): the underlying is the **Backed-issued xStock SPL token traded on Solana DEXs**. The constituent set for an xStock-backed perp is necessarily venues that list the same xStock — the universe collapses substantially compared to BTC/ETH (which trade on every CEX). For an xStock SPL token, plausible constituents are: Gate's own xStock spot, Solana DEX xStock pools (PancakeSwap is mentioned, but we suspect they meant Solana DEX aggregators — the help page may be a generic constituent-list and not xStock-specific). **The xStock-perp-specific constituent list is not surfaced in our 2026-04-29 probe and is a §6 open question.**

**Mark price (per Gate's "Mark Price Calculation" page, via search):**

> "Mark price tends to be the fair price of the contract, which is calculated based on underlying asset's spot index price and premium index. The mark price calculation uses a sampling methodology: the sampled basis is typically a set of basis values calculated every second over the past 5 minutes, and Gate may flexibly adjust the sampling time window based on market volatility to ensure the mark price remains fair and is not subject to manipulation."

This is structurally a **5-minute basis sample averaged into a premium index**, similar to Kraken's 30-of-60 minute mid (see [`perps/kraken_futures_xstocks.md`](kraken_futures_xstocks.md) §1.2) but at a finer cadence (per-second sampling, 5-minute window, vs Kraken's per-minute sampling, 60-minute window). The resulting mark = index + smoothed premium.

### 1.2 Cadence / publication schedule

- **Index price:** continuous (per-second basis sampling implies sub-second updates).
- **Mark price:** sub-minute, with the 5-minute smoothing window.
- **Funding rate:** per Gate's funding-rate-and-fee help page (cited via search), funding is paid every 8 hours (typical CEX cadence for stock perps; not explicitly confirmed in our probe — TODO §6). Gate's BTC/ETH perps are commonly 8h-funded; whether xStock perps follow the same cadence or a different one (e.g., 1h to match Kraken's xStock perps) is **gated on probe**.

### 1.3 Fallback / degraded behavior

- **Constituent venue outage** — the index re-weights across remaining sources without docs-disclosed re-normalisation rules. Same opacity as Hyperliquid's source-selection logic (see [`perps/hyperliquid_perps.md`](hyperliquid_perps.md) §1.3).
- **Sampling-window adjustment** — "Gate may flexibly adjust the sampling time window based on market volatility" — i.e., the 5-minute default can be widened or narrowed at Gate's discretion. The trigger criteria are not surfaced.
- **Manipulation-resistance via sampling** — the 5-minute average is the explicit defence against single-tick-driven mark manipulation.

### 1.4 Schema / wire format

REST/WebSocket API at `api.gateio.ws/api/v4/futures/usdt/contracts/...` per Gate's API docs. The exact response schema is not in our 2026-04-29 probe; capture would surface mark price, last-traded price, funding rate, index price, basis, volume, and OHLC bars. Pre-cutover scryer phase 55-58 reportedly schemas this out per `cex_stock_perp_tape.v1` + `cex_stock_perp_ohlcv.v1` — pin the exact column list when the live tape lands.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** **claimed live (phases 55-58 per wishlist), but not present at dataset root probe 2026-04-29.** `dataset/cex_stock_perp/...` directory is absent. **Action item:** verify with scryer maintainer whether the daemon shipped to launchd or whether phases 55-58 only locked the schema. (This is Pattern 1 from the final report — a tape marked done but not yet visible.)
- **Indirect via DEX flow:** Gate.io xStock spot trades + Solana DEX xStock pool reserves are visible in `dataset/geckoterminal/trades/v1/...` (geckoterminal venue) per the existing scryer fetcher — but Gate's CEX *perp* mark/funding is not in scryer until item 45 ships live.
- **Universe gap (Treasury):** Gate.io is the **only venue listing TLT-suffix perp** (`TLT_USDT`) per the soothsayer coverage matrix. This makes Gate.io the single-venue Treasury-token perp comparator. Note: the underlying TLT (iShares 20+ Year Treasury) is a different asset class than xStock equity backers — the same perp-mark methodology applies but the underlier is a US-Treasury-bond-ETF.
- **Coverage in current tape:** none from soothsayer side until §6 #1 resolves.

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| Gate.io lists xStock-backed perps (X-suffix tickers settled against Backed-issued tokens). | Confirmed via the soothsayer-internal coverage matrix (12 X-suffix + 4 cash-settled, probed 2026-04-28). | **confirmed** |
| Gate.io is the only CEX stock-perp venue listing a Treasury-bond-ETF perp (TLT_USDT). | Confirmed via the coverage matrix. **Single-venue Treasury comparator** — useful for Paper 1 §10.5 RWA-wave generalisation as the cleanest stock-perp-style tokenized-treasury benchmark in our addressable set. | **confirmed** |
| Index price is a weighted average across multiple CEXs (Gate, Binance, OKX, Bybit, Bitget, Coinbase, KuCoin, MEXC, Gate Alpha, PancakeSwap). | Confirmed structurally per docs. **The xStock-specific constituent list is not surfaced** — likely some subset because xStocks don't trade on Binance / Coinbase (which generic stock-spot wouldn't list). **§6 open question.** | **partial (mechanism confirmed, xStock-specific opaque)** |
| Mark price uses 5-minute per-second-sampling smoothing of basis. | Confirmed per docs. **Unmeasurable from soothsayer side without scryer tape.** | **confirmed (by docs), unmeasured** |
| Funding rate cadence is 8 hours on Gate.io xStock perps. | **Unverified — typical Gate.io BTC/ETH cadence but xStock-specific cadence not confirmed in our probe.** TODO. | **TODO** |
| Cross-venue dispersion on the same xStock during weekend windows is observable. | **TODO when scryer item 45 tape goes live.** Once Gate.io NVDAX_USDT, Kraken Perp NVDAx, HTX NVDA-X, BingX NVDAX, Phemex NVDAX are all in scryer, the cross-venue mark dispersion at the same Friday-close moment is the load-bearing §1.1 figure. | **TODO (load-bearing)** |
| Gate.io xStock perps have meaningfully lower volume than BTC/ETH perps on the same venue. | Confirmed structurally per the soothsayer coverage matrix: "Aggregate stock-perp volume across all 11 venues is rounding-error vs the same venues' BTC/ETH perps (TSLAX ≈ $2.6k/24h on Kraken Futures vs ~$millions for BTC)." | **confirmed (qualitative)** |
| Trust-gap pattern (open-vs-closed-hours volume collapse) is observable on Gate.io. | **TODO when scryer item 45 OHLCV tape is live.** The coverage memo flags this as the §1.2 / Paper 1 trust-gap argument; the per-venue cut + decay-shape-at-Friday-edge analysis is the load-bearing measurement. | **TODO (Paper 1 §1.2 load-bearing)** |
| Backed-issued xStock SPL tokens are the underlying for Gate's X-suffix perps. | Confirmed structurally per Gate's xStocks marketing material ("issuing tokens based on Solana SPL and ERC-20 standards"). The X-suffix on Gate matches the X-suffix on Kraken Perp (both reference the Backed token), so the underliers are shared. | **confirmed** |

---

## 4. Market action / consumer impact

Gate.io's stock-perp surface is a **direct comparator on the same instrument soothsayer prices**:

- **Soothsayer (xStock weekend bands)** — Gate.io's NVDAX_USDT mark at Friday close vs. soothsayer's served NVDAx band for the upcoming weekend is a direct apples-to-apples comparator. The cross-venue dispersion across Gate.io / Kraken Perp / HTX / BingX / Phemex marks at the same Friday close moment is the **central §1.1 incumbent-benchmark figure** for Paper 1.
- **Backed Finance (issuer ground truth)** — Gate.io listing the X-suffix means there's a real CEX clearinghouse with a position-margining mark on the same Backed-issued tokens. The trust-gap argument (per the coverage memo) is most useful framed as: "Gate.io's NVDAX trade volume during regular hours is X; during weekends is Y; the gap measures the consumer's distrust of the formula-only mark." Soothsayer's served band is the missing trust primitive.
- **Kamino klend / MarginFi** — neither consumes Gate.io perp marks directly. Gate.io is a *signal* (live mark), not an *oracle source*.
- **Drift Protocol** — not a Drift consumer; the cross-reference is structural (both run mark-vs-oracle alignment, but Drift's Pyth-derived oracle is structurally distinct from Gate's CEX-aggregated index).
- **Paper 1 §1.1 — incumbent-benchmark panel.** Gate.io is one of 5 xStock-backed perp venues forming the strongest panel — the cross-venue dispersion at the same Friday close, on the same Backed-issued token, is empirical evidence that production CEX oracles do not converge on a single off-hours number.
- **Paper 1 §1.2 — trust-gap framing.** Gate.io's per-venue volume decay at Friday 16:00 ET (US-equity close) is the cleanest single-venue measurement of "consumer trust in the formula-only mark." Combined with the other xStock-backed venues, the per-venue cut decomposes brand-shaped vs. methodology-shaped trust gap.
- **Paper 1 §10.5 — Treasury-token generalisation.** Gate.io's TLT_USDT perp is the single-venue tokenized-Treasury comparator. Useful in the methodology-fits-this-class argument as the empirical bridge between equity-class and Treasury-class.
- **Public dashboard (Phase 2)** — Gate.io NVDAX live mark next to soothsayer's band, alongside Kraken Perp, HTX, BingX, Phemex marks — five-venue dispersion plot. Visually clean and decisive.

---

## 5. Known confusions / version pitfalls

- **X-suffix vs plain-suffix on Gate.io.** X-suffix = xStock-backed (settles against Backed-issued tokens); plain-suffix = synthetic / cash-settled USDT. They have **different underliers** despite similar tickers. Don't conflate `NVDAX_USDT` (xStock-backed) with `NVDA_USDT` (synthetic) — the latter, if it exists, references a different mark methodology.
- **`TLT_USDT` is the single-venue Treasury comparator.** Cross-CEX surveys for TLT-class perps return Gate.io only.
- **Constituent venue list is "Gate, Binance, OKX, Bybit, Bitget, Coinbase, KuCoin, MEXC, Gate Alpha, PancakeSwap" — but** xStocks don't trade on most of these. The xStock-specific constituent list is opaque. Don't assume the same constituents as Gate's BTC/ETH perps.
- **5-minute sampling window can be adjusted at Gate's discretion.** Code that assumes a fixed 5-minute window for mark-price construction is risk-prone during volatility.
- **Gate.io is geo-blocked or restricted in some regions for spot/perps.** Soothsayer's analysis is jurisdiction-agnostic, but consumer-facing claims about "trading on Gate.io" must respect regional availability.
- **Volume on stock perps is rounding-error compared to BTC/ETH perps** on the same venue. Order book depth during US-equity-closed hours is degraded. Mark price reliability during weekends is gated on the formula, not the book.
- **Funding cadence not pinned for xStock-specific perps.** Probably 8h (Gate.io BTC/ETH default), but xStock-specific cadence not confirmed in our probe.
- **Item 45 tape claim vs visible disk state.** [`scryer/wishlist.md`](../../../../scryer/wishlist.md) marks item 45 (cex_stock_perp_tape) as Done — phases 55-58 — but the tape is not visible at our dataset root probe. Investigate before concluding the tape is live.

---

## 6. Open questions

1. **Verify scryer phases 55-58 (item 45) actually shipped end-to-end and the cex_stock_perp tape is live.** **Why it matters:** Paper 1 §1.1 cross-venue dispersion analysis is entirely gated on this. **Gating:** scryer-side check (talk to scryer maintainer or run `find <SCRYER_DATASET_ROOT>/cex_stock_perp -name '*.parquet'` to confirm presence). **This is Pattern 1 from the final report.**
2. **Pin the xStock-specific constituent list for Gate.io's X-suffix perps.** **Why it matters:** the index methodology depends on which CEX/DEX prices feed the xStock-specific weighting. **Gating:** Gate.io support outreach or finer docs probe.
3. **Confirm funding-rate cadence on Gate.io xStock perps.** **Why it matters:** allows direct cross-venue comparison of funding signals (Kraken: 1h; Hyperliquid: 1h; Drift: 1h; Gate.io: 8h or 1h?). **Gating:** Gate.io futures-rules page deeper read.
4. **Pin the funding-rate cap on Gate.io xStock perps.** **Why it matters:** Kraken's ±0.25%/h cap is the binding empirical surface (see [`perps/kraken_futures_xstocks.md`](kraken_futures_xstocks.md) §3); Gate.io's cap is unknown. **Gating:** docs probe.
5. **Cross-venue Friday-close mark dispersion on the same xStock.** **Why it matters:** the load-bearing §1.1 figure for Paper 1. **Gating:** scryer item 45 + analysis script joining all 5 xStock-backed perp venues at Friday 16:00 ET.
6. **Per-venue volume decay shape at Friday 16:00 ET.** **Why it matters:** the §1.2 trust-gap argument's empirical core. **Gating:** scryer item 45 OHLCV tape + DiD analysis per the coverage memo's H₀ specification.
7. **Whether Gate.io xStock perps consume any external oracle (Pyth, Chainlink, RedStone) as input to their index.** **Why it matters:** if yes, Gate.io is downstream of the same publisher-dispersion-vs-coverage-SLA finding; if not, Gate.io's index is upstream-independent and is a separate datapoint. **Gating:** Gate.io's index methodology depth probe.

---

## 7. Citations

- [`gate-mark-price`] Gate.com. *Mark Price Calculation (Dual Price Mechanism)*. https://www.gate.com/help/futures/logical/22067/instructions-of-dual-price-mechanism-mark-price-last-traded-price. Cited via 2026-04-29 search results.
- [`gate-index-price`] Gate.com. *Index Price Calculation*. https://www.gate.com/help/futures/logical/22069/index-price-calculation. Cited via 2026-04-29 search results. The load-bearing source for the weighted-average index methodology.
- [`gate-funding`] Gate.com. *Funding Rate and Funding*. https://www.gate.com/help/futures/futures-logic/27569/funding-rate-and-funding-fee. Cited via 2026-04-29 search results.
- [`gate-xstocks-learn`] Gate.com. *What Is Gate xStocks: 24/7 Tokenized Stock Trading Explained*. https://www.gate.com/learn/articles/no-account-no-limits-gate-x-stocks-opens-the-door-to-global-stock-trading/10108. Cited via 2026-04-29 search results.
- [`coverage-matrix-memory`] Soothsayer agent memory. *CEX stock-perp coverage map (paper 1 incumbent benchmark)*. (Internal-memory note, probed 2026-04-28, project-scoped.) The load-bearing source for the cross-venue X-suffix vs synthetic split, and for the TLT-only-on-Gate.io finding.
- [`scryer-wishlist-item-45`] Scryer internal. [`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 45 — `cex_stock_perp_tape.v1` and `cex_stock_perp_ohlcv.v1`. Marked Done (phases 55-58) per the wishlist short-index but not visible at dataset root probe 2026-04-29.
- [`kraken-perp-companion`] Soothsayer internal. [`docs/sources/perps/kraken_futures_xstocks.md`](kraken_futures_xstocks.md). Cross-CEX comparator at the same X-suffix underlier.
- [`hyperliquid-perp-companion`] Soothsayer internal. [`docs/sources/perps/hyperliquid_perps.md`](hyperliquid_perps.md). Architectural comparator (different oracle paradigm).
