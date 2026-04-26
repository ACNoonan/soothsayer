# Data Sources — Analysis & Aggregated List

> **Methodology snapshot (2026-04-25).** Soothsayer's deployed methodology is a factor-switchboard point estimate + log-log regression on a per-symbol vol index + empirical-quantile residual band + per-target empirical buffer + hybrid-by-regime forecaster. See [`reports/methodology_history.md`](../reports/methodology_history.md) for the full evolution and [`reports/v1b_decision.md`](../reports/v1b_decision.md) for the original v1b ship decision. The complex Madhavan-Sobczyk / VECM / HAR-RV / Hawkes / Kalman stack initially scoped for Phase 0 was tested and rejected as unnecessary for the calibration objective; references to those methods earlier in the doc have been updated inline to the current model.
>
> **Phase-0 data the oracle actually uses:** yfinance (daily equities for 10 tickers + ES/NQ/GC/ZN futures + VIX/GVZ/MOVE vol indices + BTC-USD + earnings_dates calendar) + Helius free tier (reserved for Phase 1 on-chain publish). Kraken Perp funding still ingestible but V3 evaluation found no detectable signal at our sample size. Phase-0 budget remains $0; Phase-1 MVP run rate $310–800/mo. **For impact-per-dollar mapping suitable for grant applications, see the Grant-impact addendum at the bottom of this doc.**

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
| Alpaca | Free tier = IEX only (unusable, ~2–3% vol); SIP tier $99/mo | Tick on paid | Company | **Never use free tier** — IEX-only flow miscalibrates the empirical-quantile residual distribution and breaks the calibration surface |
| Finnhub | $50–100/mo | 1 yr depth paid | Company | OK for calendars, weak tick |
| Twelve Data / EODHD / FMP | $20–80/mo | Daily + 1-min bars | Company | Retail-grade, insufficient for tick |
| IBKR TWS API | ~$10/mo if already customer | 1 yr intraday | Company | Cheapest if already IBKR, ugly integration |
| yfinance | Free | Daily EOD, 1-min ~60 days | Open library | **Phase 0 only** — used for V1/V2/V3 validation |

**Licensing gotcha:** SIP/consolidated-tape (CTA/UTP) redistribution is restricted. Publishing derived prices on-chain at MVP/Phase-1 scope has no surfaced enforcement precedent, but confirm scope directly with Polygon/Databento sales before production.

---

## 2. Equity Futures (Globex — the off-hours hero)

ES (E-mini S&P), NQ (Nasdaq-100), sector futures. Friendlier licensing than cash-equity SIP, ~23 hours/day availability, ~90% of S&P price discovery when SPY is closed (Hasbrouck 2003).

| Provider | Cost | Access | Notes |
|---|---|---|---|
| **Databento** | Pay-per-use, bundle with equity historical | Company, licensed | Recommended — piggyback on equity pull |
| CME DataMine | Enterprise $$$ | Company | Skip for Phase 1 |
| Polygon.io | $299+/mo higher tier | Company | Skip if Databento covers |
| IBKR TWS | ~$10/mo CME real-time if customer | Company | Cheapest real-time path |

Every dollar on clean ES/NQ returns more than a dollar on cash-equity tick during closed-market windows.

---

## 3. Crypto (BTC / ETH / SOL) — free across the board

Crypto is the only live large-volume risk-asset signal on weekends. Powers the BTC-USD factor for MSTR (post 2020-08), provides a cross-check for the `high_vol` regime label, and is the natural fallback signal when overnight US futures (ES/NQ) are not yet open early Sunday.

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

Funding rate is a market-implied forecast of the weekend Monday-gap. V3 testing on Phase-0 data ([`reports/v3_funding_signal.md`](../reports/v3_funding_signal.md)) found no detectable signal at our sample size; the regressor is retained as a candidate for v2 re-evaluation once the V5 on-chain tape supplies sufficient history alongside Kraken's perp funding archive.

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
- For Phase 1 / MVP: reconstruct from chain by observing consumer programs (Kamino's Scope oracle, Ondo v10 consumers, xBridge CCIP txs).
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

### MVP (Phase 1, 4–6 week research-deployment build)

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

- **CTA/UTP SIP redistribution** — publishing derived prices on-chain at MVP/Phase-1 scope is gray; no enforcement precedent surfaced. Status: known-risk, low-probability, small-magnitude-if-enforced. Not a blocker for MVP.
- **SEC Rule 2a-5 (17 CFR 270.2a-5)** — applies to registered-fund NAV fair-valuation. xStocks are SPV-issued bearer bonds (not 40-Act funds), so direct applicability is low. Flagged anyway for US-distributed consumer protocols.
- **Chainlink Data Streams access** — permissioned; apply day one; treat as observation input, not settlement source.
- **Databento / Polygon** — confirm derived-data publication scope directly with sales before production launch (not required for Phase 1).

---

## Three decisions that matter most

1. **Databento one-time for history, Polygon real-time for live.** Don't double-pay.
2. **Never use Alpaca's free IEX tier.** IEX = 2–3% of US volume; the resulting tape biases the residual quantiles in the calibration surface, producing systematic under-coverage at high τ.
3. **Globex futures are the off-hours hero.** Friendlier licensing than cash-equity SIP, 23/5 availability, ~90% of S&P price discovery when SPY is closed. **Kraken xStock Perp funding is the second hero** — 24/7, free, market-implied Monday-gap forecast.

## Cost-minimization playbook

- Pay Databento once for history. Run real-time on one paid provider (Polygon).
- Use Dune for on-chain backtests (free tier).
- Start free on Binance/OKX/Coinbase crypto feeds.
- Pyth Hermes is free — treat Pyth as a comparator observation from day one.
- Apply for Chainlink access day one even if not immediately used.
- Kraken/Bybit public APIs are free for spot and (Kraken) perp funding — take everything.

---

## Grant-impact addendum

This section maps each data-source line item to a specific, measurable methodology gain — the format we use for funding-grant applications and Superteam credit requests. Costs are dollar-per-month or one-time as marked. Each row answers four questions: *what does this dollar buy, what model claim does it unlock, how do we know we got it, and what open methodology question does it close?*

### Grant-impact summary table

| Source | Cost | Buys (validation milestone) | Validation metric | Closes open question |
|---|---|---|---|---|
| **Pyth Hermes reconstruction** | $0 (engineering only) | First quantitative incumbent-oracle benchmark on a 12-year matched window | Bootstrap-CI table comparing Pyth aggregate-CI realised coverage to Soothsayer per-target served band, on the same 5,986 weekend panel | Paper §1 framing currently rests on a *qualitative* "no incumbent publishes a verifiable calibration claim" — Hermes work converts this to a quantitative comparator |
| **Chainlink Data Streams reconstruction** | $0 (engineering only; via Helius) | Second incumbent comparator (stale-hold + `marketStatus=5` archetype) | Same matched-window coverage comparison; reports/v1_chainlink_bias.md is partial infra | Same — adds a second comparator alongside Pyth |
| **FRED API (Fed macro calendar)** | $0 | FOMC / CPI / NFP regressor for the regime model | Re-run ablation with macro-event flag; bootstrap CI on coverage delta in shock-tertile bucket | Currently shock-tertile structural ceiling (~80% at τ=0.95) is unexplained — FRED tests whether macro-event clustering accounts for it |
| **Nasdaq Trader Halts XML** | $0 | Halt-aware regime tag distinct from `high_vol` | Per-regime ablation including new `halt` regime | Currently halts are pooled into `normal` regime; introduces unidentified noise |
| **Backed Finance Discord/blog scrape** | $0 (one-time) | Authoritative xStock corp-actions backfill | Diff against yfinance corp-actions; re-run backtest; report Δcoverage | Possible silent bias from missed dividends/splits in the 2014–2026 panel |
| **Crypto exchange WebSocket (Binance / Coinbase / Kraken direct)** | $0 | Tick-level BTC/ETH/SOL for MSTR factor + cross-asset weekend signals | MSTR factor-switchboard MAE comparison vs daily-yfinance baseline | MSTR's 2020-08 factor pivot is hand-coded; tick-level BTC enables drift detection |
| **Walk-forward backtest (engineering)** | $0 | Distribution of buffer values + standard errors instead of point estimates from one OOS split | Six expanding-window splits 2018→2026; report buffer mean ± SE per τ; re-derive Kupiec CI | Single-split sample-size-1 buffer (§9.4) — biggest paper-vulnerability fix |
| **Bounds-grid extension (engineering)** | $0 | Resolves τ=0.99 structural ceiling | Re-run v1b backtest with claimed grid {0.995, 0.997, 0.999}; report new Kupiec at τ=0.99 | §9.1 limitation becomes solvable |
| **Helius Pro / Triton / QuickNode (Superteam credit eligible)** | $50–250/mo (or sponsored) | Faster V5 on-chain tape accumulation for F_tok forecaster | Time-to-150-weekend-obs per (symbol, regime) accelerated from ~Q3 2026 to ~Q2 2026 | Cong et al. 2025 baseline gap (§9.10): on-chain xStock TWAP forecaster gated on tape size |
| **Wall Street Horizon / Estimize earnings calendar** | $50–500/mo | Earnings-event regressor with date + estimated-move-size + timing | Re-run ablation with finer earnings input; report Δcoverage with bootstrap CI; either kills disclosure or becomes detectable contribution | §9.5 "earnings regressor not detectable at our sample size" — testable |
| **Trading Economics macro events** | $0 (free tier) – $100/mo | Cross-vendor macro calendar for FRED redundancy | Sanity-check shock-tertile finding against second source | Secondary insurance on FRED-based finding |
| **Databento historical equity + futures tick** | $200–500 one-time | Validates factor switchboard at intraday granularity; opens overnight-prediction window | Compare daily-yfinance factor switchboard MAE vs minute-level reconstruction; identifies which weekends the daily window obscured | Enables v2-paper "intraday + weekend" prediction-window extension |
| **Polygon.io Stocks Advanced** | $199/mo real-time | Live-mode Oracle deployment (currently historical-mode-only) | First production weekend with live-mode `fair_value` calls; consumer-experienced coverage measurement begins | §9.7 "no live deployment window" — opens the live measurement record |
| **DefiLlama / Birdeye xStock TWAP backfill** | $0–200/mo | Fast-forward F_tok validation rather than waiting for tape accumulation | Run F_tok serve at OOS targets; report Kupiec/Christoffersen vs deployed F1_emp_regime baseline | Same as Helius Pro tier — Cong baseline gap |

### Grant-application narrative (template)

For a grant proposal, frame the asks as **three tiers, each with a specific paper-quality milestone**:

**Tier 1 — Engineering-only (no funding required, listed for completeness; ~3–4 weeks):**

- Pyth Hermes + Chainlink reconstruction → **first quantitative incumbent-oracle comparison table** in the literature.
- Walk-forward backtest → **distribution-valued calibration claims with standard errors** instead of point estimates.
- Bounds-grid extension → **resolves the τ=0.99 structural ceiling** documented in §9.1.

**Tier 2 — Funded data ($500 one-time + $50–500/mo; ~6–8 weeks of follow-on work):**

- Earnings calendar (Wall Street Horizon or equivalent): tests the §9.5 disclosure that a finer-granularity earnings input would make the regressor detectable. Either confirms the methodology already captures the available signal (paper-strengthening) or improves served-band sharpness measurably (model-improvement). **Either result is a publishable finding.**
- Databento one-time historical: enables v2-paper "intraday + weekend" prediction-window extension. Fundamentally expands the addressable consumer set from "weekend bands" to "any closed-market window."

**Tier 3 — Production-readiness ($200–250/mo + Superteam credits; ~12-week deployment runway):**

- Polygon.io real-time: first live deployment, opens the consumer-experienced coverage measurement record (§9.11 + docs/v2.md §V2.3).
- Helius Pro tier (Superteam credits could substitute): unlocks F_tok forecaster timeline (Cong baseline gap, §9.10 + docs/v2.md §V2.1) on Q2-2026 cadence rather than Q3+.

### Grant-impact dollar ranges

For grant applications that prefer ranges:

- **$0** (Tier 1 engineering): three publishable improvements, ~3–4 weeks.
- **~$500 one-time + ~$300/mo for 3 months** (Tier 1 + Tier 2 minimum): adds earnings-calendar test + Databento historical → v2-paper enabler.
- **~$500 one-time + ~$700/mo for 6 months ≈ $4,700** (Tier 1 + 2 + 3): full production-readiness path, including live-deployment first quarter and F_tok forecaster validation.

### Open methodology questions this addendum maps to

Each row above closes or partially closes an entry in [`reports/methodology_history.md`](../reports/methodology_history.md) §2 (Open methodology questions). When an item closes, the corresponding row in this table can be moved to a Completed-deliverables sub-section and the methodology log entry resolved.

Cross-reference: any new paid-source decision should append to both `methodology_history.md` §1 (Decision log) and update §0 (State of the world).
