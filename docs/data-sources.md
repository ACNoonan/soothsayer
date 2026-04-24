# Data Sources — Analysis & Aggregated List

> **Methodology pivot note (2026-04-24):** Soothsayer's methodology pivoted away from the Madhavan-Sobczyk / VECM / HAR-RV / Hawkes stack to a simpler factor-switchboard + empirical-quantile + log-log regime model (see [`reports/v1b_decision.md`](../reports/v1b_decision.md) and [`reports/option_c_spec.md`](../reports/option_c_spec.md)). The data sources below are still broadly correct — **venue choices, pricing, and licensing status all stand** — but method-specific caveats like "feeds the Kalman measurement-variance priors" or "input to the MS half-life fit" are now stale. The data the oracle actually uses in v1b: yfinance (daily equities, ES/NQ/GC/ZN futures, ^VIX/^GVZ/^MOVE, BTC-USD, earnings_dates) + Kraken REST (still available but V3 funding signal FAILED) + Helius (reserved for Phase 1 on-chain publish path). Budget remains $0 for Phase 0; $310–800/mo run rate for Phase 1 MVP.

Comprehensive catalog of every data source under consideration for Soothsayer, grouped by category, with cost, access type (open public / company-licensed / restricted / on-chain), and current verdict.

Supersedes ad-hoc discussion; mirrors the per-category notes in the Obsidian vault under `Projects/Solana Fair Value Oracle/Data Sources/DS 00–07`.

## Landscape shape

**Bimodal.** Crypto, on-chain, and the new CeFi xStock venues (Kraken/Bybit) are free and excellent. US equity tick data is the one real cost center and has non-trivial licensing. Incumbent oracle observations (Pyth Hermes, Chainlink via chain reconstruction, Switchboard PDA reads) are free.

---

## 1. US Equity — cash tape (real-time + historical)

The one real cost center. ~80% of the data budget lives here.

| Provider | Real-time | Historical | Access | Verdict |
|---|---|---|---|---|
| **Polygon.io Stocks Advanced** | $199/mo real-time NBBO ($29/mo delayed) | Tick history included in paid tiers, back to 2003 | Company, licensed (CTA/UTP redistribution restricted) | **Default for real-time** |
| **Databento** | Pay-per-use, ~$100–400/mo live | ~$150–400 one-time for 6–12 mo tick on xStocks + futures + sector ETFs | Company, licensed | **Default for one-time historical** |
| Alpaca | Free tier = IEX only (unusable, ~2–3% vol); SIP tier $99/mo | Tick on paid | Company | **Never use free tier** — miscalibrates Kalman |
| Finnhub | $50–100/mo | 1 yr depth paid | Company | OK for calendars, weak tick |
| Twelve Data / EODHD / FMP | $20–80/mo | Daily + 1-min bars | Company | Retail-grade, insufficient for tick |
| IBKR TWS API | ~$10/mo if already customer | 1 yr intraday | Company | Cheapest if already IBKR, ugly integration |
| yfinance | Free | Daily EOD, 1-min ~60 days | Open library | **Phase 0 only** — used for V1/V2/V3 validation |

**Licensing gotcha:** SIP/consolidated-tape (CTA/UTP) redistribution is restricted. Publishing derived prices on-chain at hackathon scale has no surfaced enforcement precedent, but confirm scope directly with Polygon/Databento sales before production.

---

## 2. Equity Futures (Globex — the off-hours hero)

ES (E-mini S&P), NQ (Nasdaq-100), sector futures. Friendlier licensing than cash-equity SIP, ~23 hours/day availability, ~90% of S&P price discovery when SPY is closed (Hasbrouck 2003).

| Provider | Cost | Access | Notes |
|---|---|---|---|
| **Databento** | Pay-per-use, bundle with equity historical | Company, licensed | Recommended — piggyback on equity pull |
| CME DataMine | Enterprise $$$ | Company | Skip for hackathon |
| Polygon.io | $299+/mo higher tier | Company | Skip if Databento covers |
| IBKR TWS | ~$10/mo CME real-time if customer | Company | Cheapest real-time path |

Every dollar on clean ES/NQ returns more than a dollar on cash-equity tick during closed-market windows.

---

## 3. Crypto (BTC / ETH / SOL) — free across the board

Crypto is the only live large-volume risk-asset signal on weekends. Feeds the regime HMM and Kalman measurement-variance priors.

| Provider | Real-time | Historical | Cost | Access |
|---|---|---|---|---|
| **Binance / OKX / Bybit / Coinbase / Kraken** | Free REST + WebSocket | Back to listing, free | $0 | Open public |
| Tardis.dev | Paid | Unified cross-CEX tick incl. perps/funding | ~$50–200 one-time | Company, paid |
| CryptoCompare / CoinGecko | Free | Aggregated | $0 | Open aggregator |

Real-time: Binance + OKX WebSocket direct. Skip Tardis unless cross-CEX unified tick is needed.

---

## 4. Solana on-chain

Easiest category — every xStock DEX trade since June 2025 launch is reconstructable.

| Provider | What you get | Cost | Access |
|---|---|---|---|
| **Helius** | Solana RPC + Yellowstone gRPC + webhooks + Enhanced Transactions API | Free tier (1M credits + 100k DAS calls/mo); paid from $49/mo | Company RPC, free tier |
| Triton One | Low-latency Yellowstone gRPC + ShredStream | From $250/mo | Company — overkill for publisher |
| QuickNode | RPC + gRPC | Free tier + paid from $49/mo | Company |
| **Flipside Crypto** | SQL, Solana-native | Free tier (was usable for solo devs) | Company — **ruled out Apr 2026** (signup now requires org + sales demo) |
| Dune Analytics | SQL over historical | Free tier + ~$390/mo serious | Company |
| Bitquery | GraphQL | Free tier + paid | Company |
| Birdeye / Shyft | DEX aggregated APIs | Free tier + paid | Company |

**What to pull:**

- Pool state (reserves, liquidity) for every xStock pool on Meteora, Raydium, Orca
- Trade events
- Token-2022 `ScaledUiAmountConfig` updates (dividends, splits) — see H6
- Token-2022 `PausableConfig` state changes (halts)
- Chainlink and Pyth `PriceUpdate` transactions (reconstruction of their feeds)

Recommendation: **Helius free/Yellowstone for real-time**, **Helius Enhanced Transactions for historical** (Flipside's replacement).

---

## 5. CeFi xStock venues (Kraken, Bybit) — all free, highest-value new signal

xStocks trade on Kraken and Bybit spot. Kraken Perp (launched Feb 24 2026 via Bermuda-licensed Payward Digital Solutions) is the first regulated tokenized-equity perp venue.

| Venue | Products | API | Cost | Access | Priority |
|---|---|---|---|---|---|
| **Kraken spot** | All Alliance xStocks | Public REST + WebSocket | $0 | Open public | High |
| **Kraken Perp** | 10 xStock perps + **8h funding rate** | Public REST + WebSocket | $0 | Open public | **High — NEW (H9)** |
| **Bybit spot** | xStock spot | Public REST + WebSocket | $0 | Open public | Medium (redundancy) |

### Kraken Perp markets (10)

SPYx, QQQx, GLDx, TSLAx, AAPLx, NVDAx, GOOGLx, HOODx, MSTRx, CRCLx. Up to 20× leverage. Funding paid every 8 hours.

### Ingest endpoints

| Signal | Endpoint | Cadence | Source variance priors |
|---|---|---|---|
| Kraken spot mid | `/0/public/Ticker` | seconds | Low in RTH, high off-hours |
| Kraken spot OHLC | `/0/public/OHLC` | 1 min | Yang-Zhang realized vol |
| Kraken Perp mark | `/derivatives/api/v3/tickers` | seconds | Medium; basis-to-spot is signal |
| **Kraken Perp funding** | `/derivatives/api/v3/historical-funding-rates` | 8 h | **Low noise, high information** |
| Bybit spot mid | `/v5/market/tickers` | seconds | Redundancy |

Funding rate is a market-implied forecast of the weekend Monday-gap — direct input to the Madhavan-Sobczyk filter.

---

## 6. Corporate actions, halts, calendars

The boring data that silently breaks a naive fair-value oracle.

### Corporate actions (dividends, splits)

| Provider | Cost | Access |
|---|---|---|
| **Polygon.io** | Included in paid tiers | Company |
| FMP | ~$20/mo | Company |
| EODHD | $20–60/mo | Company |
| **Backed Finance blog / Discord** | Free | Open (scrape) — ground truth for xStock-specific actions |

### Halts

| Provider | Cost | Access |
|---|---|---|
| **Nasdaq Trader Halts XML** | Free | Open — poll 1/min |
| NYSE halts | Paid | Company — skip unless needed |
| **Token-2022 `PausableConfig`** | Free | On-chain listener |
| Backed Finance announcements | Free | Open — cross-check |

### Earnings & macro calendars

| Provider | Cost | Access |
|---|---|---|
| **FRED API** | Free | Open (US gov) — gold standard for US macro |
| Finnhub free tier | Free | Company — earnings calendar |
| Trading Economics | Free tier + paid | Company |
| Benzinga / Econoday | Paid | Company — overkill |

---

## 7. Incumbent oracles (observation inputs, not sources of truth)

Counterintuitively, the hardest data to get cleanly is competitors' data. We observe these alongside exchange data; we do **not** derive our fair value from Chainlink's weekend print (circular).

### Pyth Network

- **Hermes HTTP + WebSocket** — free, real-time.
- Historical via Hermes: ~7 days depth.
- Deeper historical: reconstruct from Solana ledger (free via Helius / Dune).
- **Aggregation formula** (`docs.pyth.network/price-feeds/core/how-pyth-works/price-aggregation`):
  - Each publisher submits $(p_i, c_i)$; gets three votes $\{p_i - c_i, p_i, p_i + c_i\}$.
  - Aggregate $R$ = median of $3N$ votes.
  - Aggregate confidence $C = \max(|R - Q_{25}|, |R - Q_{75}|)$.
  - Plus slot-weighted, inverse-confidence-weighted EMA price + EMA conf (~1 h half-life).
- **Pyth Pro X** (March 2026): 24/5 US equity via Blue Ocean ATS exclusive through end-2026, 50+ equities, vendor-reported 96%+ NBBO accuracy, sub-100ms.
- **Treat as first-class observation day one** (free + most rigorous comparator).

### Chainlink Data Streams

- **Permissioned.** Direct access requires a report-server integration — not a public API.
- **Apply day one** — latency-to-access is the bottleneck, not cost.
- For hackathon: reconstruct from chain by observing consumer programs (Kamino's Scope oracle, Ondo v10 consumers, xBridge CCIP txs).
- **v11 RWA schema** is the active format for xStocks. Fields: `feedId, timestamp (ns), price, bid, ask, bidVolume, askVolume, lastTradedPrice, midPrice, lastUpdateTimestamp, marketStatus, expiresAt, ripcord`.
- `marketStatus` codes: `0 Unknown, 1 Pre-market, 2 Regular, 3 Post-market, 4 Overnight, 5 Weekend`.
- v11 publishes a price during `marketStatus = 5` — opaque methodology. **H8 is the validation test for whether it's biased.**

### Switchboard

- Job-based custom feeds; PDA reads via `PullFeedAccountData::get_value()` + `max_staleness` check.
- `OracleJob` tasks: `httpTask`, `jsonParseTask`, `oracleTask` (can fold Pyth/Chainlink in), WASM/JS sandbox.
- **Relevant as a publishing surface** (see H3), not as an input. No model-based equity feed exists on Switchboard itself.

### RedStone

- **Solana live May 28 2025** via Wormhole Queries (13 Guardian signatures verified on-chain).
- **RedStone Live** (March 2026) markets "24/7 equity coverage" — methodology undisclosed. Co-founder publicly named the weekend-gap problem (CoinDesk, 23 Nov 2025).
- Modes: Pull (Core), Push (Classic), X (deferred-execution for perps), Atom (atomic push).
- RWA leader for BUIDL, ACRED, VBILL, SCOPE, Canton Network.
- Secondary comparator only — methodology undisclosed = can't reason about independence.

### Band v3 / API3

- Band v3 (July 2025): DPoS BandChain, 53 validators. No CI, no closed-market model, no native Solana.
- **API3 is EVM-only** — no Solana deployment. Not relevant on our venue.

---

## Budget

### Phase 0 (now, validation-only)

- **$0.** yfinance + Kraken public REST + Helius free tier only.
- Paid signups deferred until a validation task is blocked by data gaps (raise with user before signing up anywhere new).

### MVP (Phase 1, 4–6 week hackathon build)

| Line | Cost | Notes |
|---|---|---|
| Historical equity + futures tick (one-time) | **$200–500** | Databento, 6–12 mo depth, 8 Kamino xStocks + ES/NQ + XLK/XLF/QQQ/SPY |
| US equity real-time | **$199/mo** | Polygon.io Stocks Advanced |
| Helius (Solana gRPC) | $0–49/mo | Free tier usable |
| Kraken xStock Perp funding | **$0** | Public REST |
| Everything else | $0 | Dune free, Binance/OKX/Coinbase free, FRED, Nasdaq halts, Kraken/Bybit spot, Pyth Hermes, Chainlink on-chain reconstruction |

**MVP total:** ~$200–500 one-time + ~$200–250/month.

### Production steady state

- Add Databento real-time (~$200–300/mo) for redundancy.
- Add FMP or EODHD (~$30/mo) for corp-actions cross-check.
- Optional: Triton gRPC ($250/mo) if latency matters.
- **Realistic:** ~$500–800/mo.

---

## Licensing watch-list

- **CTA/UTP SIP redistribution** — publishing derived prices on-chain at hackathon scale is gray; no enforcement precedent surfaced. Status: known-risk, low-probability, small-magnitude-if-enforced. Not a blocker for MVP.
- **SEC Rule 2a-5 (17 CFR 270.2a-5)** — applies to registered-fund NAV fair-valuation. xStocks are SPV-issued bearer bonds (not 40-Act funds), so direct applicability is low. Flagged anyway for US-distributed consumer protocols.
- **Chainlink Data Streams access** — permissioned; apply day one; treat as observation input, not settlement source.
- **Databento / Polygon** — confirm derived-data publication scope directly with sales before production launch (not required for hackathon).

---

## Three decisions that matter most

1. **Databento one-time for history, Polygon real-time for live.** Don't double-pay.
2. **Never use Alpaca's free IEX tier.** IEX = 2–3% of US volume; miscalibrated priors kill the Kalman.
3. **Globex futures are the off-hours hero.** Friendlier licensing than cash-equity SIP, 23/5 availability, ~90% of S&P price discovery when SPY is closed. **Kraken xStock Perp funding is the second hero** — 24/7, free, market-implied Monday-gap forecast.

## Cost-minimization playbook

- Pay Databento once for history. Run real-time on one paid provider (Polygon).
- Use Dune for on-chain backtests (free tier).
- Start free on Binance/OKX/Coinbase crypto feeds.
- Pyth Hermes is free — treat Pyth as a comparator observation from day one.
- Apply for Chainlink access day one even if not immediately used.
- Kraken/Bybit public APIs are free for spot and (Kraken) perp funding — take everything.
