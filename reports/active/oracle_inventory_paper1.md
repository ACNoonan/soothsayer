# Oracle inventory for Paper 1 §2 "Setting"

- **Date:** 2026-05-11
- **Scope:** Every oracle currently live on Solana or major EVM L1/L2s that touches tokenized equities (xStocks, Ondo equity tokens, Backed certificates) or equity underliers (SPY, QQQ, TSLA, AAPL, NVDA, etc.) — as input material for the §2.1 rewrite of *Empirical coverage inversion: a calibration-transparency primitive for decentralized RWA oracles*.
- **Author:** research-agent (Claude, parent-thread tasked)
- **What this is not:** a survey of crypto-native price oracles in general. We filter to oracles that either (a) publish an equity ticker feed, (b) publish a tokenized-equity SPL/ERC-20 mark, or (c) are consumed by a Solana protocol that prices an equity-backed instrument.

The paper's load-bearing distinction throughout: a feed that publishes the **ticker** `SPY/USD` is economically distinct from a feed that publishes the **SPL mint** `XsCS1W9F6tEDoeRPYHipoiBM6Z2sFKZ...` (SPYx). The first relays NYSE last-trade plus whatever off-hours rule the oracle chooses; the second is a mark on an instrument that trades 24/7 on Solana DEXes and may have its own off-hour discovery process. Provider docs are inconsistent about which they're publishing — we flag the distinction throughout.

---

## Master table

| Provider | Chain(s) | What it reports for equities | Symbols covered (sample) | Off-hours behavior | Uncertainty field | Methodology disclosure | Known Solana integrations | We have parquet? |
|---|---|---|---|---|---|---|---|---|
| **Chainlink Data Streams v8** ("RWA Standard", schema id `0x0008`) | Solana, EVM | Mid-only schema: `midPrice` (int192) + `marketStatus` enum (3-state: `0=Unknown, 1=Closed, 2=Open`); no `bid`, `ask`, `conf`, or `last_traded_price` on the wire | All xStocks Kamino accepts (TSLAx, AAPLx, SPYx, NVDAx, GOOGLx, MSTRx, HOODx, QQQx, AMZNx, COINx); each gets a dedicated v8 feed (TSLAx feed id `0x00084edc844a6f88449c59c8cfcdb2225799a2330503472cb0bc4f9369a717fa`) | Two consumption modes via Kamino Scope: `Open` (rejects updates when `marketStatus ≠ Open` → freezes at Friday 16:00 ET close); `AllUpdates` (accepts off-hours `midPrice` clamped to ±500 bps of the Open feed's last-good value) | None — single mid-scalar plus a 3-state enum | v8 schema doc; no calibration claim; off-hours `midPrice` provenance ("how it was derived") not on the wire | **Kamino Finance** (`OracleType::ChainlinkRWA = 34` in Scope; $4B-TVL lending market); the load-bearing xStock-lending path on Solana | **Partial** — `chainlink/data_streams` family captures v8/v10/v11 wire shapes; v8-specific tape pending verification |
| **Chainlink Data Streams v10** ("Tokenized Asset") | Solana, EVM | Ticker last-trade + 24/7 CEX-aggregated `tokenizedPrice`; `marketStatus` enum (3-state) | xStocks: AAPLX, TSLAX, NVDAX, METAX, GOOGLX, MSTRX, SPYX, QQQX (60+) | `price` stale during weekends; `tokenizedPrice` continues from CEX activity | None on wire — no bid/ask/conf | Schema-doc + RWA-Alliance blog; no calibration claim | Backed xBridge; **not** the Kamino-consumed path | **Yes** — `chainlink/data_streams` |
| **Chainlink Data Streams v11** ("RWA Advanced") | Solana, EVM | `price`, `bid`, `ask`, `mid`, `last_traded_price`, `bid_volume`, `ask_volume`; 6-state `marketStatus` | Same xStocks set as v10; co-existing | Synthetic `.01`-suffix `bid` on weekends/closed (paper §6.7.2) | Bid/ask spread, but synthetic on weekends | Schema doc; weekend marker behavior undocumented externally | Same as v10 — co-deployed | **Yes** — `chainlink/data_streams` |
| **Chainlink Data Feeds (push)** | EVM (Ethereum, Base, Arbitrum, etc.) | Equity ticker prices via aggregator contracts; corp actions | SPY, AAPL, TSLA, NVDA, etc. | Stale-hold (last on-chain answer until heartbeat) | None on wire | Aggregator design (DON whitepaper); per-feed deviation/heartbeat only | N/A on Solana | No |
| **Pyth Network (core)** | Solana + 100+ chains via Wormhole | First-party publisher (price, conf) for equity tickers and ETFs; ~380 feeds across all asset classes | `Equity.US.SPY/USD`, AAPL, TSLA, NVDA, MSFT, GOOGL, QQQ, ... | Status enum (`trading`, `halted`, `unknown`); aggregate freezes outside session | Aggregate conf interval (max distance from median to 25th/75th vote-percentile); diagnostic, not coverage claim | `[pyth-agg]` + `[pyth-conf]` blog posts; methodology described but no aggregate-level coverage claim | Drift Protocol (primary), MarginFi, Jupiter (until 2025), Kamino (in transition) | **Yes** — `pyth/oracle_tape` |
| **Pyth Pro** (formerly Pyth Lazer) | Solana + EVM | Lower-latency (~1ms) institutional-grade publisher feeds; subscriber-customizable cadence; **exclusive Blue Ocean ATS overnight equity data through end-2026** | Same publisher set + Blue Ocean equity book during 8pm–4am ET Sun–Thu | Blue Ocean book during overnight session (Sun–Thu 8pm–4am ET); **canonical Fri 4pm – Sun 8pm weekend window still uncovered**; standard Pyth status otherwise | Same publisher conf-interval semantics; no aggregate-level coverage claim | `[pyth-pro]` docs; `[blueocean-pyth]` integration blog | HIP-3-as-a-Service for Hyperliquid stock perps; Solana DeFi via MagicBlock | **Yes** — `oracle.pyth_lazer/tape` |
| **RedStone Classic (push)** | EVM-first; Solana since May 2025 (RWA oracle) | Pull-/push-modular feeds across crypto, RWA, tokenized funds; equity feeds for select tickers | Tokenized funds (BUIDL, ACRED) + equity tickers per partner request; xStock symbols (TSLAx, AAPLx etc.) discussed but not all live on-chain | Documented qualitatively — "blends institutional feeds with perpetual-market data during off-hours" | None on wire by default; per-feed customizable | Blog post `[redstone-live]`; specific weights/venues/consensus rule not published; deep methodology page 404 | Securitize tokenized funds (ACRED, BUIDL on Solana); Drift, MarginFi for crypto | **Yes** — `redstone/oracle_tape` |
| **RedStone Live** (forward-cursor gateway, public) | Off-chain REST | Public REST gateway `api.redstone.finance/prices`; 30-day cap; point-only schema | SPY, QQQ, MSTR (verified via memory); no xStock SPL mints; no equity feeds on-chain Solana | Continuous time-series but no off-hours semantics declared at the point | None (point-only) | Gateway docs minimal | None on Solana | **Yes** — `redstone/oracle_tape` |
| **CF Benchmarks — CFB xStocks Indices** | Off-chain (REST/WebSocket), regulated | FCA-supervised, BMR-aligned `CCRTI_T` scalar published ~1Hz per xStock; PR + TR variants (~100 benchmarks total); 24/7 by construction (inputs are crypto-venue order books) | All xStocks: AAPLX, TSLAX, NVDAX, METAX, GOOGLX, MSTRX, SPYX, QQQX, HOODX, COINX, ...; corp-actions feed separate | Continuous; no closed-NBBO carry rule because inputs are crypto-venue (Kraken Spot, Bybit, Bitget, Kraken Futures, DEXes) trading 24/7. §5.5 Calculation Failure halts publication if all contributors >30s stale | None on wire — single scalar per second; cross-venue outlier filter (§5.3) is an input filter, not an output band | **Methodology Guide v1.0 (Feb 2026) + BMR Article 27 Benchmark Statement** — strongest regulatory methodology disclosure in survey, but zero coverage / confidence / band / calibration language anywhere | **Kraken xStock perpetual futures** (regulated tokenized-equity perps, launched 2026-02-24, 10 symbols, up to 20× leverage) | No (not yet captured) |
| **HyperStone** (RedStone, Hyperliquid-only) | Hyperliquid (HIP-3) | Push-based oracle purpose-built for HIP-3 builder-deployed perps; equity perp marks at 3ms cadence | TSLA (first live HIP-3 market, via Felix), expandable to any RWA | Continuous, 24/7 driven by perp orderflow; off-hours behavior governed by deployer | None published | Blog announcement; no detailed methodology paper | None — Hyperliquid only | No |
| **SEDA Protocol — SEDA Benchmark / USA500** | EVM + Hyperliquid HIP-3 + Injective (no Solana) | Single continuous on-chain scalar with `{active_session, was_stale}` flags; USA500 composite (60% equities / 25% crypto / 15% commodities); per-symbol session-aware equity feeds (NVDA, AAPL, TSLA, SPY) also available | USA500 composite (constituents/weights not published); per-symbol equity scalars in docs examples | 4-pillar continuity rule: (i) session tags (premarket/regular/post/overnight), (ii) cost-of-carry futures-to-spot, (iii) self-referencing EMA during closed hours ("closes Friday-to-Monday gaps by ~95%"), (iv) staleness fallback | None on wire — scalar + session flags only; no numerical drift bound or dispersion under closed-market regime | seda.xyz product pages + `docs.seda.xyz` corpus; methodology *qualitative* (continuity-focused), no coverage claim | None — Hyperliquid (via Dreamcash HIP-3), Injective, Perps.Fun, Outcome, Nunchi | No |
| **DIA / DIA Lumina** | Ethereum L2 (Lasernet) + Solana + 80+ chains | Open, transparent feeds for 3000+ assets; per-input source, weight, and aggregation step published on-chain | RWA reference prices advertised; no enumerated xStock SPL or equity-ticker deployment on Solana for tokenized-equity consumers | Not documented externally for equities | Median + per-source contributor disclosure on Lumina (input transparency, not output coverage) | **Strongest open-methodology claim in survey, but for equities the disclosed methodology is for an undeployed surface** — input transparency ≠ statistical coverage claim on the served value | None known for tokenized equities on Solana | No |
| **API3 (dAPIs + OEV)** | 40+ EVM chains | First-party data via Airnode operators; 200+ feeds; OEV auctions return rebate to dApp | Crypto-heavy; some equity dAPIs available on dAPI-docs; coverage shallow vs Pyth/Chainlink | Stale-hold unless searcher updates via OEV auction | OEV auction is integrity-economic, not statistical-coverage | dAPI docs; OEV design papers | None on Solana | No |
| **Supra Oracles** | Supra L1 + 80+ networks (no native Solana) | DORA v2 expanded RWA coverage (FX, equities, commodities); 600–900ms finality | Equities advertised under "RWA expansion"; symbol list shallow | Not documented; behaves as the publisher set behaves | None published as a calibration statement | Blog + product pages | None on Solana | No |
| **eOracle** | Ethereum (EigenLayer AVS) | Restaking-secured price feeds | Crypto-heavy; equities not in advertised core surface | Not applicable to equities | None | Whitepaper + docs (oracle-AVS architecture) | None on Solana | No |
| **Chronicle Protocol** (ex-Maker Oracle CU) | EVM (Ethereum, Base, zkSync, Polygon, etc.) | "Onchain Equities Price Feeds" launched 2024–2025 for tokenized-equity protocols; Proof-of-Asset transparency layer | Equities feeds + Securitize STAC + BlackRock BUIDL Proof-of-Asset | Not documented for the equity feeds — RWA-PoA is reserve-attestation not real-time pricing | Per-attester signatures (integrity); no statistical-coverage claim | Blog + methodology docs (verifiable signer set) | None on Solana | No |
| **UMA Optimistic Oracle** | EVM (Ethereum, Optimism, Polygon, Arbitrum, Base) | Dispute-and-stake oracle for arbitrary claims; powers Across bridge feeds, Polymarket | No live tokenized-equity ticker feeds; useful for *resolutions* (e.g., earnings, corp actions) not real-time pricing | N/A — eventual-correctness model | None (dispute window, not a band) | DVM whitepaper + blog `[uma]` | None for equities | No |
| **Tellor** | EVM (Ethereum, Polygon, ...) | Reporter-stake oracle for arbitrary spot data | Crypto-heavy; equities possible but not productized | Stale-hold | None on wire | `[tellor]` whitepaper | None on Solana | No |
| **Hyperliquid native oracle** | Hyperliquid L1 only | Validator-weighted-median of CEX mid prices (Binance 3, OKX 2, Bybit 2, Kraken 1, KuCoin 1, Gate 1, MEXC 1, Hyperliquid 1) for crypto; Hyperps use 8h EWMA of last-day minutely mark prices | Crypto only natively; equity perps via HIP-3 use deployer-chosen external oracle | Hyperps: EWMA carry; spot oracles: median freezes if venues halt | None (point only) | Hyperliquid docs `oracle.md` | N/A on Solana | No |
| **Edge** (Chaos Labs) | Solana, EVM | Risk-aware oracle protocol; designed to be "more than price reporting" (risk + market integrity) | Primary: Jupiter perps (90%+ of Solana perp volume); crypto-first | Not documented externally for equities | Not published in public docs | Chaos Labs blog post; methodology not externally peer-reviewed | **Jupiter perps** (primary Solana integration, >$30B cumulative volume); not currently the canonical xStock equity feed | No |
| **Kamino Scope** (aggregator, not originator) | Solana | Aggregates Pyth / Switchboard / Chainlink / custom into a single PDA; validates prices against pre-set rules | xStock collateral routing for Kamino lending market | Inherits upstream behavior + rule-based gating | Inherits upstream | GitHub repo + audit reports; rule set is on-chain | Kamino lending markets (primary consumer); $4B+ deposits secured | **Yes** — `kamino_scope/oracle_tape` |
| **Drift oracle aggregation** | Solana | Drift consumes Pyth as primary; arbitrary other sources per market; calculates mark/funding/margin in real time | Crypto perps; equity perps teased Feb 2026 but not live as of May 2026 | Inherits Pyth status | Inherits Pyth conf | Drift docs `oracles.md` | Drift itself (primary) | No (post-hack relaunch May–Jun 2026) |
| **Phoenix orderbook** (price-reference, not oracle) | Solana | On-chain CLOB; spot mid usable as reference for derivative protocols | Crypto only; no equity orderbooks | N/A | Bid/ask on the book (effective uncertainty) | Whitepaper / GitHub | Not an oracle per se; some consumers read TWAP | No |
| **Backed Finance / Ondo native pricing** | Solana, Ethereum (via issuer) | Issuer mints/redeems with reference NAV; **no on-chain reference-price feed published by issuer**; relies on Chainlink Data Streams as the canonical price layer | xStocks (Backed) and forthcoming Ondo equity tokens | Issuer reference NAV declared off-chain; on-chain price comes from Chainlink/Pyth | None published by issuer | Backed token docs + Ondo blog; both delegate pricing to Chainlink | Backed Finance owns issuance; Chainlink owns on-chain price plane | No (issuer NAV not on parquet) |

---

## Per-provider deep dives

### Chainlink — four coexisting surfaces, with v8 as the load-bearing xStock-lending path

Four Chainlink surfaces are simultaneously live in 2026, and the surface a downstream consumer actually reads matters. **Data Feeds (push)** is the legacy EVM-aggregator model — heartbeat-and-deviation triggered updates of a single mark price into an aggregator contract on Ethereum or an L2. No Solana presence for equities.

**Data Streams v8 ("RWA Standard", schema id `0x0008`)** is a **mid-only schema** — fields are `feedId`, `validFromTimestamp`, `observationsTimestamp`, `nativeFee`, `linkFee`, `expiresAt`, `lastUpdateTimestamp`, **`midPrice`** (int192), **`marketStatus`** (uint32: `0=Unknown, 1=Closed, 2=Open`). There is no `bid`, `ask`, `conf`, `last_traded_price`, or `tokenizedPrice` field anywhere in the wire format. This is the schema **Kamino Finance ($4B TVL) actually consumes** for every xStock it accepts as collateral, routed through Kamino Scope's `OracleType::ChainlinkRWA` adaptor (enum discriminant 34 in `programs/scope/src/states/oracle_type.rs`). Scope's mainnet config registers two parallel v8 feeds per xStock, governance-set per lending reserve: an `Open` feed that refuses every update when `marketStatus ≠ Open` (price freezes at Friday 16:00 ET close until Monday open, refresh attempts fail with `OutsideMarketHours`), and an `AllUpdates` feed that accepts off-hours `midPrice` clamped to **±500 bps of the Open feed's last-good value** (`ref_price_tolerance_bps: 500`). Both knobs are uncalibrated: the `Open` feed is a stale-hold for ~65 hours every weekend; the `AllUpdates` feed will refuse off-hours moves exceeding the ±5% static bound (which Cong et al. 2025 Table 4 shows occurs in 12% of weekday off-hours for TSLAx). Cross-referenced xStock feed IDs (Token-2022 Backed mints; canonical TSLAx mint `XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB`): TSLAx `0x00084edc...717fa`, AAPLx `0x0008e64e...c450`, SPYx `0x00081025...21f`, NVDAx `0x0008adc1...647d`, GOOGLx `0x00081e84...d6b1`, QQQx `0x00087074...fbd9`, MSTRx `0x00081af0...9739`, HOODx `0x00088cf4...ef37`, AMZNx `0x0008fdc9...dd8b`, COINx `0x000807d2...cc49`.

**Data Streams v10 ("Tokenized Asset", schema id `0x000a`, 13 fields, 416 bytes)** adds a `price` field, a `tokenizedPrice` field continuing from a 24/7 CEX-aggregated mark, a 3-state `marketStatus` enum, and corporate-action multipliers. v10 is the surface most often cited in marketing as backing xStocks on Solana — and it is the schema Backed↔Solana xBridge consumes — but **Kamino does not read v10**; the live xStock-lending price plane is v8. v10 carries **no `bid`, `ask`, or confidence on the wire** — a v10 consumer reading directly derives a degenerate zero-width band.

**Data Streams v11 ("RWA Advanced", schema id `0x000b`, 14 fields, 448 bytes)** is the 2026 extension co-existing with v10 (and with v8): adds `bid`/`ask`/`mid`/`last_traded_price`/`bid_volume`/`ask_volume` and a 6-state `marketStatus` distinguishing pre-market / regular / post-market / overnight / closed / weekend. The paper §6.7.2 documents that the v11 weekend `bid` carries a synthetic `.01`-suffix marker on three of four mapped xStocks at 100% incidence — a categorical bookend, not a continuous band. **No production xStock-lending consumer reads v11 directly** as of 2026-05-14; the v11 synthetic-bookend finding is a parallel failure mode (potential v11 consumer's gap), not Kamino's specific gap.

Chainlink is the **official oracle of the xStocks Alliance** (announced 2025-06-30; Backed/Kraken acquisition of xStocks completed late 2025) and the canonical Solana xStock pricing plane via the v8 path through Kamino Scope. MetaMask earn-on-equities integrations, the Backed↔Solana xBridge (announced 2025-12-12), and Ondo's early-2026 Solana tokenized-stock rollout each select different Chainlink surfaces. None of the four Chainlink surfaces publishes a calibration claim on the served value; the choice between them is a routing-and-bandwidth decision, not a coverage-disclosure decision.

Sources: [chainlink-streams](https://docs.chain.link/data-streams), [v8 schema](https://docs.chain.link/data-streams/reference/report-schema-v8), [v10 schema](https://docs.chain.link/data-streams/reference/report-schema-v10), [v11 schema](https://docs.chain.link/data-streams/reference/report-schema-v11), [Kamino Scope `oracle_type.rs`](https://github.com/Kamino-Finance/scope/blob/master/programs/scope/src/states/oracle_type.rs), [Scope Chainlink handler](https://github.com/Kamino-Finance/scope/blob/master/programs/scope/src/handlers/handler_refresh_chainlink_price.rs), [Scope mainnet config (all xStock feeds)](https://github.com/Kamino-Finance/scope/blob/master/configs/mainnet/3NJYftD5sjVfxSnUdZ1wVML8f3aC6mp1CXCL6L7TnU8C.json), [Kamino governance — xStocks integration](https://gov.kamino.finance/t/kamino-is-integrating-xstocks-powered-by-the-chainlink-data-standard-to-enable-tokenized-equities-lending/792), [xStocks Alliance announcement](https://x.com/chainlink/status/1939763692301922621), [xBridge announcement](https://www.coindesk.com/web3/2025/12/12/backed-chainlink-launch-xbridge-to-move-tokenized-stocks-between-solana-and-ethereum), [Ondo+Chainlink](https://ondo.finance/blog/defi-adoption-of-ondo-tokenized-stocks-live).

### Pyth Network — core, Pro, and the Blue Ocean exclusivity

Pyth's core Solana surface is the canonical first-party-publisher oracle in DeFi: ~120 permissioned publishers submit `(price, confidence)` reports; the on-chain aggregator takes the median over the three votes each publisher contributes (`price`, `price + conf`, `price - conf`), and the published aggregate confidence is the max distance from the median to the 25th/75th percentile votes. Pyth's documentation [`pyth-conf`] explicitly recommends that each publisher calibrate to ~95% coverage at the publisher level, but **no aggregate-level coverage claim is published** — and the aggregate's behavior outside the calibrated range is undefined. The aggregate has a `status` enum (`trading`, `halted`, `unknown`) but no continuous market-status disclosure.

**Pyth Pro** (rebranded from Pyth Lazer, the rebrand confirmed via CO-PIP-5 passing on Solana mainnet in 2025-Q3) is the institutional tier: single-millisecond latency, ~400× faster than core Pyth, subscriber-customizable cadence, ~28 active subscribers as of Q3 2025. **The economically load-bearing differentiator for equities** is Pyth's exclusive on-chain distribution of the **Blue Ocean ATS** overnight executable book through end-2026: 8pm–4am ET Sunday-through-Thursday, ~$1B nightly volume across ~5,000 NMS symbols. This is the closest published incumbent to a true 24/5 equity feed — but the canonical xStock **weekend** (Friday 4pm ET through Sunday 8pm ET) remains uncovered by Blue Ocean's session and therefore by Pyth Pro.

Pyth additionally offers **HIP-3-as-a-Service** for Hyperliquid builder-deployed perps, providing the price relay for stock perpetuals there. On Solana DeFi the main consumers are Drift (primary), MarginFi, and (historically) Jupiter — Jupiter's perps have since migrated to Edge (Chaos Labs) as their primary oracle.

Sources: [Pyth aggregation proposal](https://www.pyth.network/blog/pyth-price-aggregation-proposal), [Pyth confidence primer](https://www.pyth.network/blog/pyth-primer-dont-be-pretty-confident-be-pyth-confident), [Pyth Pro docs](https://docs.pyth.network/lazer), [Blue Ocean+Pyth](https://www.pyth.network/blog/blue-ocean-ats-joins-pyth-network-institutional-overnight-hours-us-equity-data), [Pyth Lazer Solana mainnet](https://forum.pyth.network/t/passed-co-pip-5-release-pyth-lazer-on-solana-mainnet/1881), [HIP-3-as-a-Service](https://docs.pyth.network/price-feeds/hip-3-service), [Magicblock+Lazer](https://www.pyth.network/blog/magicblock-and-lazer-powering-a-new-wave-of-speed-for-solana-defi).

### RedStone — Classic, Live, RWA-Solana, and HyperStone

RedStone is unusual in operating four distinct equity-relevant surfaces. **RedStone Classic** is the pull-/push-modular EVM-first oracle, integrated by Drift, MarginFi, and other Solana protocols for crypto pricing. **RedStone Live** (March 2026 launch, blog `[redstone-live]`) is a 24/7 equity feed product blending institutional feeds during US hours with perpetual-market data during off-hours; methodology described qualitatively but contributing-venue list, weights, consensus rule, and any confidence statement are **not published in reproducible form**. The deep methodology page that the launch post linked to returns 404. The public gateway `api.redstone.finance/prices` has a 30-day cap, point-only schema, no CI, and serves SPY/QQQ/MSTR but **no SPL xStock mints and no equity feeds on Solana on-chain**.

**RedStone RWA-Solana** (May 2025 launch, partner: Securitize) brings tokenized-fund price feeds to Solana via Wormhole Queries — primary live assets are Apollo's ACRED and BlackRock's BUIDL, not xStocks. **HyperStone** (November 2025) is a Hyperliquid-only push-based oracle purpose-built for HIP-3 builder-deployed perps at 3ms cadence — first live HIP-3 market was Felix's TSLA perp; HyperStone has since powered ~$1.5B in cumulative HIP-3 volume across 12 markets. None of the four surfaces publishes a statistical coverage claim.

Sources: [RedStone Live](https://blog.redstone.finance/2026/03/30/redstone-live-real-time-data-built-for-the-markets-that-never-sleep/), [RedStone RWA Solana](https://blog.redstone.finance/2025/05/28/redstone-rwa-oracle-brings-tokenized-assets-to-solana-ecosystem/), [HyperStone launch](https://www.theblock.co/post/377776/redstone-launches-hyperstone-oracle-to-power-permissionless-markets-on-hyperliquid), [Felix HIP-3 TSLA](https://blog.redstone.finance/2025/11/13/felix-launches-its-first-hyperliquid-hip-3-market-with-tsla-powered-by-hyperstone/).

### CF Benchmarks — CFB xStocks Indices (Kraken-owned regulated benchmark)

CF Benchmarks is Kraken's UK FCA-supervised, BMR-aligned regulated-benchmark subsidiary, acquired 2019. On **2026-05-07** they launched the **CFB xStocks Indices** product family: ~100 benchmarks (every onboarded xStock gets a Price Return and Total Return variant) plus a separate Corporate Action Feed, governed by the **"Token Market Price Benchmarks Series — Methodology Guide v1.0"** (02 Feb 2026) and a per-family BMR Article 27 **Benchmark Statement**. The same methodology powering CFB's bitcoin and ETH reference rates is ported to xStock tokens; xStocks does not get its own methodology document, only inherited input parameters via the §6.2 supported-benchmarks parameters file (not publicly linked).

**Wire shape.** A single scalar `CCRTI_T` per second per index (Eq. 3 of the Methodology Guide). The Specifications table (§7) lists Administrator, Calculation Agent, Calculation Methodology, and Dissemination Time *("Approximately every second of each day for the entire year including weekends and holidays")*. There is **no confidence interval, band, standard error, dispersion field, volatility metric, depth/utilization field, or contributor-count field on the wire** — verified by exhaustive search of the Methodology Guide and Benchmark Statement for `coverage`, `confidence`, `calibration`, `uncertainty`, `band`, `standard error`, `dispersion`, `tolerance`, `interval`, with zero substantive matches. The only `deviation` references are §5.3 (cross-venue outlier filter for Potentially Erroneous Data) and the input-side `D` parameter (deviation-from-mid trimming of the consolidated order book). **Both are input filters, not output uncertainty disclosures.**

**Closed-market behavior.** Because all inputs are crypto-venue order books (Kraken Spot, Bybit, Bitget, Kraken Futures, and Solana DEXes) trading the xStock SPL mints 24/7, the index is **continuous by construction** — there is no carry-forward rule, no freeze, no halt-on-closed-NBBO, no synthetic-extrapolation rule for the Friday-16:00-to-Sunday-20:00 ET window. The index simply consumes the same order books continuously. The only off-switch is §5.5 Calculation Failure: if all Contributed Exchange order books are >30s stale or flagged erroneous, the index is not published for that second. The methodology nowhere distinguishes regular-hours vs. closed-hours regime, and nowhere acknowledges that closed-NBBO is a regime where price is structurally less informative — this is the single sharpest methodology-vs-coverage gap in the survey, because CFB is the most regulatory-rigorous provider on the disclosure-of-construction axis and yet says nothing about the disclosure-of-coverage axis.

**Why this matters for §2.1.** CFB is the closest contemporary incumbent to "doing what Soothsayer does" in the sense of regulated tokenized-equity benchmark publishing — and it **strictly does not break the §2.1 categorical claim**. The BMR Article 27 Benchmark Statement, which is the document where any coverage / accuracy / "potential vulnerabilities" disclosure would be regulatorily required, contains zero language about realised coverage, calibration, or bounds on the served value (only Article 12 boilerplate: "robust and reliable", "rigorous, continuous and capable of validation including back-testing against available transaction data"). BMR Article 27 itself does not mandate output-uncertainty disclosure — only methodology, discretion, input data, and limitations of representativeness. CFB is fully BMR-compliant by disclosing methodology + cessation rules + ESG governance; none of that approaches Soothsayer's calibration-transparent statement. The contrast is the strongest available demonstration that **regulation alone has not produced a coverage-disclosed equity benchmark** for tokenized markets.

**Solana exposure.** CFB powers Kraken's xStock perpetual futures (launched 2026-02-24; the world's first regulated tokenized-equity perps; 10 symbols, up to 20× leverage) — these are off-chain CEX-listed derivatives, not Solana on-chain consumers. CFB is **off-chain only** as a distribution channel (REST/WebSocket to venues); no on-chain oracle integration is announced. The combination of (Kraken acquired Backed late 2025) + (CFB published xStock indices on 2026-05-07) + (Kraken xStock perps already live, settled against these indices) makes Kraken the **vertically integrated tokenized-equity issuer + regulated benchmark + perp venue stack**; Soothsayer sits orthogonally to this stack as an **on-chain coverage primitive over the same instruments**, not a competitor on the regulated-benchmark axis.

Sources: [CFB launch blog](https://cfbenchmarks.com/blog/cf-benchmarks-xstocks-product-suite-is-live-with-regulated-indices-and-a-corporate-actions-feed), [CFB indices catalog](https://cfbenchmarks.com/documentation/indices), [Token Market Price Benchmarks Methodology Guide PDF](http://docs.cfbenchmarks.com/Token%20Market%20Price%20Benchmarks%20Series%20-%20Methodology%20Guide.pdf), [Benchmark Statement PDF](https://docs.cfbenchmarks.com/Token%20Market%20Price%20Benchmarks%20Series%20-%20Benchmark%20Statement.pdf), [xStocks Corporate Action Feed PDF](https://docs.cfbenchmarks.com/CFB%20xStocks%20Corporate%20Action%20Feed.pdf), [Kraken xStock perps product page](https://blog.kraken.com/product/xstocks/tokenized-equity-perpetual-futures).

### DIA / DIA Lumina — methodology-disclosed-but-no-coverage-claim contrast

DIA Lumina (2024+) is structurally the most transparent **input-side** oracle stack: every contributing source, weight, and aggregation step is published, settled on Lasernet (DIA's Ethereum L2 rollup), and re-derivable. Critically, this is **input transparency**, not **output coverage** — DIA discloses the methodology that produces its served scalar, but does not publish a realised-coverage claim, prediction band, or any statistical statement about the joint distribution of (served value, future realised price). The two transparency primitives are orthogonal: DIA proves *how* its number is computed; Soothsayer proves *what coverage rate* its band achieves. The paper should cite DIA as the existence proof against the strawman "an oracle that fully discloses methodology is impossible" — but also as the empirical demonstration that input transparency alone does not solve the closed-market problem.

DIA advertises Real-World-Asset price feeds across 3000+ assets including equities, but the public symbol list for equities is not enumerated and no Solana xStock-mint feed appears in known integrations. Equity-specific deployment is essentially zero on Solana. DIA's role in the survey is the **methodology-disclosed-but-no-coverage-claim** counterexample: the disclosure axis is solved in design space (DIA's Lumina design) but the deployment in the tokenized-equity surface is absent, and even if DIA shipped an xStock feed tomorrow, its disclosure primitive would not contest §2.1's coverage-categorical.

Sources: [DIA Lumina](https://www.diadata.org/lumina/), [DIA Solana oracles](https://www.diadata.org/solana-price-oracles/).

### Chronicle Protocol — RWA-oriented, MakerDAO-derived, EVM-only

Chronicle (the spinout of MakerDAO's Oracle Core Unit) has secured $10B+ in collateral since 2016 and announced "Onchain Equities Price Feeds" (date: 2024–2025) targeting RWA protocols. In 2026 the deployed surface accelerated via Centrifuge selecting Chronicle as primary RWA oracle and Securitize integrating Chronicle's Proof-of-Asset layer for STAC and BUIDL transparency. **All EVM** — no Solana deployment for tokenized equities as of May 2026. Chronicle's "transparency" pitch is anchored on the verifiable signer set and reserve attestation, not on a statistical-coverage claim on the served price.

Sources: [Chronicle equities launch](https://chroniclelabs.org/blog/chronicle-launches-onchain-equities-price-feeds), [Centrifuge partner](https://www.morningstar.com/news/business-wire/20260108358859/centrifuge-selects-chronicle-as-primary-oracle-partner-for-tokenized-assets).

### Hyperliquid native + HIP-3 deployer ecosystem

Hyperliquid's native oracle is a validator-weighted median of CEX mid prices (Binance 3, OKX 2, Bybit 2, Kraken 1, KuCoin 1, Gate 1, MEXC 1, Hyperliquid 1) — applied to crypto spot only. **Hyperps** (pre-launch perpetuals) use an 8-hour exponentially-weighted moving average of the last day's minutely mark prices, with a 4× one-month-average cap as a manipulation safeguard; this is the most explicit *carry* methodology any of the surveyed oracles publishes. **HIP-3** (October 2025 mainnet) is the open-permissionless model where the deployer chooses the oracle for their market — primary deployer-oracle competitors are Pyth (HIP-3-as-a-Service) and RedStone (HyperStone). The first live HIP-3 stock market was Felix's TSLA, powered by HyperStone, going live 2025-11-05.

Sources: [Hyperliquid oracle](https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle), [Hyperps](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/hyperps), [HIP-3](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals).

### SEDA Protocol — USA500 composite and the perp-DEX equity-class oracle archetype

SEDA Protocol (`seda.xyz`) is the live successor to Flux Protocol (Flux's repositories archived late 2022; team migrated, distinct product). Its **SEDA Benchmark** product publishes session-aware equity feeds and a **USA500 composite** = 60% equities + 25% crypto + 15% commodities, currently consumed by Hyperliquid (via Dreamcash HIP-3), Injective, Perps.Fun, Outcome, and Nunchi. SEDA has **no Solana deployment** as of mid-2026.

**Wire shape.** Per the SEDA docs corpus (`docs.seda.xyz/home/llms-full.txt`) and the session-aware oracle programs documentation, each feed emits "a single continuous onchain price feed." Example responses are scalar prices in either Pyth-style `{mantissa, expo}` or hex-encoded EVM `uint256`. The only auxiliary fields shown in any documented example are `"active_session": "PREMARKET"` (a session enum) and `"was_stale": false` (a staleness flag) — **no confidence interval, dispersion measure, prediction band, or any statistical width.** Cadence is "configurable update cadence, aggregation, weighting and smoothing methodology" set per oracle program.

**USA500 composite construction.** The only public disclosure is the 60/25/15 asset-class split. No constituent list, no per-name weight, no cap-weighted-vs-equal-weighted rule, no rebalance cadence, no source-venue weights are published. Third-party context confirms USA500 is "a custom index built with SEDA and live on HIP-3 via Dreamcash" — but the actual composite math is undisclosed.

**Closed-market continuity ("four pillars").** SEDA documents a continuity-focused methodology: (i) **session awareness** (per-symbol session tags: pre-market / regular / post-market / overnight); (ii) **cost-of-carry futures-to-spot conversion** (use dated futures to back out a spot during off-hours); (iii) **self-referencing EMA pricing during closed hours** ("anchors to the last known price and slowly drifts it based on actual order book activity," reportedly "closing Friday-to-Monday gaps by ~95%"); (iv) **staleness fallback**. This is the most explicit *carry methodology* in our survey — more granular than Hyperliquid's 8-hour Hyperps EWMA, more transparent than RedStone Live's "blends institutional + perp data" qualitative line. **However:** SEDA never quotes a numerical drift bound, dispersion, or any uncertainty inflation under the closed-market regime. The methodology delivers a *continuous scalar*, not a *coverage-disclosed band*.

**Why this matters for §2.1.** SEDA is the cleanest contemporary example of a perp-DEX-oriented equity oracle that takes the *carry-methodology disclosure* axis seriously while leaving the *coverage-claim disclosure* axis untouched. The composite-vs-per-asset distinction means SEDA is not a direct Soothsayer competitor (Soothsayer publishes per-symbol bands on xStock SPL mints; SEDA's primary product is a composite multi-asset proxy used as a single perp underlying), but the per-symbol session-aware feeds (NVDA, AAPL, TSLA, SPY appear in docs examples) bring SEDA architecturally closer to the same surface — distinguished only by output shape (scalar with session flags vs. (lower, upper, claimed_coverage_served) tuple). For the paper's §5 audit-gap table, SEDA's "self-referencing EMA closes ~95% of Fri→Mon gap" is the *closest claim that does* resemble a coverage statement, but it is a marketing claim about an unspecified gap metric on an unspecified test set — not a held-out, time-stratified, Kupiec/Christoffersen-verifiable realised-coverage number.

Sources: [SEDA homepage](https://www.seda.xyz/), [SEDA docs](https://docs.seda.xyz/), [session-aware oracle programs](https://docs.seda.xyz/home/session-aware-oracle-programs), [docs llms-full corpus](https://docs.seda.xyz/home/llms-full.txt), [blocmates SEDA methodology coverage](https://www.blocmates.com/articles/seda-the-backbone-of-24-7-markets).

### Edge (Chaos Labs) — Jupiter's primary, no equity yet

Edge is Chaos Labs' "next-generation" oracle that ships risk-management functions co-mingled with price reporting. It is **Jupiter Perps' primary oracle** as of mid-2025, securing >$30B in cumulative transaction volume and "90%+ of Solana's total daily perpetual futures volume" per Jupiter's own statement. Edge is not currently the canonical xStock equity oracle — Jupiter perps are crypto-only. Useful as a reference point for "risk-aware oracle" as a design direction, but its public methodology disclosure is a single blog post and detailed coverage claims are not externally peer-reviewed (the linked Chaos Labs page returns 404 as of this writing, suggesting in-progress rewrites). Worth following for Solana-side competitive pressure if Jupiter extends to equity perps.

Sources: [Edge intro](https://chaoslabs.xyz/posts/introducing-edge-the-next-generation-oracle) (404 as of 2026-05-11; cached references via [Jupiter Solana DeFi report](https://eco.com/support/en/articles/14801178-solana-defi-stack-routers-lending-perps)).

### Kamino Scope — aggregator over upstream oracles, not an originating oracle

Scope is **explicitly an aggregation layer**, not a price-discovery primitive. It reads from Pyth, Switchboard, Chainlink, and custom on-chain sources, validates the prices against pre-set rules (deviation bounds, staleness checks, etc.), and writes a single PDA per asset that Kamino lending consumes. Scope is triple-audited and secures $4B+ of Kamino deposits. **Critical for paper §2.1 framing:** Scope is downstream of the providers we survey; it amplifies whatever calibration property the upstream provider has (zero, in every case) and additionally publishes its rule-based gating logic openly. Classify as "router/aggregator" rather than "oracle" — we discuss it because it is the **dominant Solana consumer** of xStock oracle data.

Sources: [Scope GitHub](https://github.com/Kamino-Finance/scope), [Scope SDK](https://github.com/Kamino-Finance/scope-sdk).

### Backed Finance / Ondo — issuers, not pricing layers

A frequent point of confusion: **Backed Finance** (xStocks issuer; acquired by Kraken late 2025) and **Ondo Finance** (preparing 2026-Q1 Solana tokenized-stock launch) are token issuers, not oracles. Both delegate on-chain pricing to Chainlink (and, in Backed's case, also to Pyth via xStocks Alliance partner relationships). Each maintains an off-chain reference NAV used for mint/redemption — but **neither publishes that NAV as an on-chain reference price feed**. The on-chain xStock price plane *is* Chainlink Data Streams v10/v11. We surface this here because §2.1 readers may otherwise assume Backed is publishing a price oracle; they are not.

Sources: [xStocks launch](https://www.prnewswire.co.uk/news-releases/backeds-xstocks-go-live-today-on-bybit-kraken-and-solana-defi-302494379.html), [Kraken acquires Backed](https://blog.kraken.com/news/backed-acquisition), [Ondo+Chainlink](https://ondo.finance/blog/defi-adoption-of-ondo-tokenized-stocks-live), [Ondo Solana plan](https://www.coindesk.com/business/2025/12/15/ondo-finance-to-offer-tokenized-u-s-stocks-etfs-on-solana-early-next-year).

### Other surveyed providers — sub-paragraph notes

- **Switchboard** (V3 / On-Demand / Surge, Solana + EVM): permissionless TEE-attested oracle queues with subscriber-defined job graphs; deployed equity surface is shallow — no headline xStock integration, no public symbol list for equity feeds, market-hours/off-hours handling delegated to the integrator. Aggregation reducers (median, mean, etc.) are integrity primitives, not coverage primitives. Not the canonical xStock oracle on Solana. Sources: [Switchboard docs](https://docs.switchboard.xyz/docs/switchboard/readme/designing-feeds/oracle-aggregator), [On-Demand GitHub](https://github.com/switchboard-xyz/on-demand).
- **Stork Network** (Solana + 70+ chains): marketing-grade self-disclosure ("leading oracle powering equity perpetuals markets", "24/5 leveraged exposure to US stocks") with no public symbol enumeration for SPL mints, no methodology paper, no statistical-coverage claim. Equity-specific deployment surface on Solana is not publicly enumerated; Solana-dormant for verifiable xStock feeds. Sources: [Stork](https://www.stork.network/), [docs](https://docs.stork.network/).
- **API3** (40+ EVM chains, no Solana): first-party Airnode operators + OEV auctions. The OEV mechanism is an integrity-economic primitive (front-runner auction with rebate to dApp), orthogonal to the statistical-coverage primitive this paper targets. Equity feed coverage shallow; not the xStock pricing plane.
- **Supra Oracles** (80+ chains, no native Solana): DORA v2 RWA expansion advertised mid-2025; equity coverage exists in marketing material but not in the deployed Solana surface for tokenized equities. Sub-second finality is the headline.
- **eOracle** (Ethereum AVS, EigenLayer-restaking-secured): crypto-pricing focused, no equity productization. The restaking-economic-security primitive is orthogonal to the coverage primitive.
- **UMA** (EVM-only): optimistic-oracle, used for **resolution events** (Polymarket payouts, Across-bridge claims) — not continuous price feeds. Mentioned for completeness; not in the §2.1 archetype set.
- **Tellor** (EVM): dispute-and-stake; no productized equity feeds. Mentioned as the canonical economic-dispute archetype.
- **Drift internal oracle** (Solana): not an originating oracle — Drift consumes Pyth as primary and computes mark/funding/margin downstream. Surfaced here because Drift teased equity perps in February 2026 and is the most likely Solana protocol to enter the xStock-derivative market next; the protocol relaunch post-April-2026 hack is targeting May–June 2026.

### Borderline / out-of-scope

- **Phoenix orderbook (Solana)**: on-chain CLOB. Some consumers derive a TWAP from Phoenix mid-prices for use as a reference, but Phoenix is a venue not an oracle, and has no equity orderbooks (crypto only). Not in §2.1.
- **DoubleZero / specialty data-distribution networks**: Solana-side high-speed-data infrastructure (announced April 2026); plumbing, not a price oracle.
- **GeckoTerminal / on-chain TWAP feeds**: dex-internal references used by some Solana protocols; for tokenized equities the dex-internal TWAP *is* the xStock secondary-market price, which is what an oracle for the SPL mint is presumably trying to publish — but it is not itself an oracle product. Worth noting in §2.1 as the "raw on-chain mid" baseline the oracle is competing with.
- **Solana validator-level price publishers** (Jito, Jupiter Lend pricing PDAs): protocol-internal, not standalone oracles.

---

## Cross-cutting findings relevant to §2.1

1. **The xStock pricing plane has bifurcated into four tiers, none of which are coverage-disclosed.** (a) **Issuer NAV** — Backed Finance + Ondo maintain off-chain reference NAV for mint/redemption, not published on-chain. (b) **Regulated benchmark** — CFB xStocks Indices (Kraken-owned, FCA/BMR) publishes per-second PR/TR scalars from crypto-venue order books; off-chain only; powers Kraken xStock perps. (c) **On-chain Solana lending plane** — Chainlink Data Streams **v8 RWA Standard** (mid-only schema, no bid/ask/conf, 3-state `marketStatus` enum) is the load-bearing path consumed by Kamino Finance via Scope's `OracleType::ChainlinkRWA` adaptor for every xStock collateral asset; Scope offers two governance-set behaviors per reserve (`Open` freezes at Friday close, `AllUpdates` accepts off-hours `midPrice` clamped to ±500 bps), both uncalibrated. v10/v11 are *adjacent* Chainlink surfaces (Backed↔Solana xBridge consumes v10; v11 is the 6-state marketStatus extension whose synthetic `.01`-suffix weekend bid §6.7.2 documents — a parallel failure mode of a potential v11 consumer, not Kamino's). Pyth publishes the *underlying ticker* (`Equity.US.SPY/USD`) but the SPL-mint feeds are not its surface; RedStone Live publishes SPY/QQQ tickers off-chain only. (d) **DEX-internal mid** — the secondary-market price any consumer can compute directly from Orca/Raydium/Meteora xStock pools. None of the four tiers publishes a statistical coverage claim on the served value, even though tier (b) is the most regulatory-rigorous methodology-disclosure surface in the survey.

2. **No surveyed oracle publishes a statistical-coverage claim on the served value.** Every uncertainty field that exists on-the-wire is either a publisher-dispersion diagnostic (Pyth aggregate conf), a synthetic bookend (Chainlink v11 weekend bid `.01`-suffix), a venue-spread (Chainlink v11 bid/ask during open hours), or absent (v10, RedStone Live, Stork, Switchboard, DIA equity feeds, Edge, HyperStone, **CFB xStocks Indices**, **SEDA Benchmark / USA500**). The two most recent regulated/perp-DEX-oriented entrants (CFB launched 2026-05-07; SEDA established under its rebrand) both publish scalar-only outputs — CFB is FCA/BMR-rigorous on the input-methodology axis, SEDA is the most explicit on the carry-methodology axis (four-pillar continuity rule), and **neither contests the categorical**. The paper's "calibration primitive is orthogonal to the deployed integrity primitive" framing is empirically tight and is sharpened, not weakened, by the 2026 entrants.

3. **Off-hours methodology disclosure is qualitative across the board, but the qualitative palette is widening.** The most explicit *carry* rule in our survey is now SEDA's four-pillar continuity (session tags + cost-of-carry futures-to-spot + self-referencing EMA + staleness fallback) with a marketing claim of "closes Friday-to-Monday gaps by ~95%" — but no held-out coverage number. Hyperliquid's 8-hour Hyperps EWMA padding, the Chainlink v11 synthetic `.01`-suffix bookend, and Pyth Pro's Blue Ocean forward-cursor session (8pm-4am ET Sun-Thu) round out the explicit-rule palette. CFB sits at the opposite pole — fully continuous by construction (crypto-venue inputs, no closed-NBBO regime in the methodology) and silent on coverage. None of these are framed as a probability-of-coverage statement on the served value.

4. **The canonical Friday-4pm-to-Sunday-8pm xStock weekend remains uncovered by any incumbent's continuous-discovery feed.** Pyth Pro/Blue Ocean covers Sun-Thu nights only; Chainlink v10 goes stale Friday close; v11 emits the synthetic-marker pattern; RedStone Live blends qualitatively; SEDA self-referencing-EMAs through the gap; CFB consumes crypto-venue order books continuously (i.e., the answer is "whatever the xStock SPL trades for on Kraken Spot at 3am Saturday" — which is itself an unverified discovery surface). This is the paper's load-bearing empirical claim and the survey corroborates it.

5. **HIP-3 has spun out a new equity-oracle subcategory** (Pyth-HIP-3, HyperStone, **SEDA**, Edge-like Chaos Labs work) where the deployer chooses the oracle and the underlying perpetual orderbook is the off-hours price-discovery mechanism. This is structurally a different problem from the xStock-on-Solana problem: the perp deployer controls the contract and the oracle simultaneously, so calibration disclosure has a different vendor incentive structure. SEDA's USA500 composite is the cleanest example — a single proxy used as the underlying for HIP-3 perps on Dreamcash, with no per-symbol band and no published constituent weights.

6. **The 2026 entrants are confirmatory market signal, not displacement.** CFB xStocks Indices (2026-05-07 launch) and SEDA Benchmark / USA500 (now-live under SEDA rebrand) both validate two adjacent demands — regulated reference-rate disclosure for tokenized equities (CFB) and 24/7 equity-class pricing for perp-DEX deployers (SEDA) — while leaving the coverage-disclosed-band primitive uncontested. The competitive read is: **the tokenized-equity oracle stack is splitting into specialized layers** (regulated benchmark + on-chain SPL feed + composite-for-perps), and the calibration-transparent layer remains an open slot above all three.

---

## §5 — CEX stock-perp comparator panel

For Paper 1 §5 the strongest empirical-incumbent benchmark is not another oracle product but the production CEX stock-perp marketplaces. Every venue listed below runs a 24/7 mark-price formula in production for the same instruments Soothsayer prices, so the Friday→Monday weekend gap is directly observable as a venue-by-venue methodology comparison. Cross-venue dispersion during weekend windows is itself a §5 figure; thin order-flow on these perps is a *feature* for the argument because the venue's mark-price formula dominates over book-driven discovery, making the oracle methodology observable with minimal noise.

**Panel scope:** the four venues listed publish **xStock-backed perpetuals** — X-suffix tickers settled against Backed-issued tokenized stock, i.e., the *exact* underlying instrument Soothsayer prices, zero translation gap. Synthetic CEX-internal stock perps (OKX, Coinbase International, MEXC, KuCoin, Crypto.com, BingX-NCSK, Bitget-RWA-hybrid) are surveyed for completeness in the related scryer panel but are not included here because they sit at one extra translation layer. The panel is captured under scryer wishlist item 45 (`cex_stock_perp_tape.v1`).

| Venue | xStock-perp surface (probed 2026-04-28) | Mark-price methodology disclosure | Off-hours behavior | Universe / volume note |
|---|---|---|---|---|
| **Kraken Futures** | 9/10 X-suffix tickers (`PF_*XUSD`); 10× max leverage | Mark price disclosed at family level ("CF Benchmarks reference rate"); per-symbol decomposition not published. Settles against **CFB xStocks Indices** post-2026-05-07. | 24/5; weekend behavior inherits CFB index → crypto-venue inputs continuous. No coverage / band on the wire. | Lead venue for regulated-tokenized-equity perps; world's first such product launched 2026-02-24. Volume per-symbol low (TSLAX ≈ $2.6k/24h) — methodology, not flow, dominates. |
| **Gate.io** | 12 X-suffix + 4 plain tickers; **only panel venue listing TLT** (`TLT_USDT`) | Index methodology page describes generic "composite of major spot exchanges with deviation drop and stale-feed exclusion"; per-symbol contributors not enumerated | 24/7 trading window claimed; off-hours mark methodology not separately documented | TLT singleton gives the panel a fixed-income x-axis Kraken doesn't cover; lifts symbol coverage to ~95% relative to other panel venues |
| **HTX (Huobi)** | 5 X-suffix (TSLAX/MSTRX/AMZNX/COINX/PLTRX) + 9 plain | Index methodology page describes weighted average of "major spot exchanges" with deviation filtering; contributors not enumerated | 24/7; off-hours mark methodology not separately documented | ~$22M / 24h aggregate (2026-05-14 probe); meaningful volume floor — useful for the cross-venue dispersion test |
| **BingX** | 4 X-suffix (AAPLX/NVDAX/METAX/PLTRX); separate NCSK-prefix synthetic stack (53 tickers, non-xStock) | Index methodology page brief; per-symbol contributors not enumerated; NCSK methodology distinct and not in the xStock-backed slice | 24/7; off-hours mark methodology not separately documented | **Panel volume leader at ~$252M / 24h** combined across X + NCSK; the X-suffix slice alone is a credible weekend-dispersion lens |

### What this panel tests for §5

**§5.1 — Methodology cross-validation against CFB.** Kraken Futures is now an *implementation* of the CFB xStocks Indices (off-chain regulated reference rate → on-CEX-platform mark price); BingX, Gate.io, HTX run their own composites. The panel exposes the methodology-vs-methodology gap: does the CFB-anchored venue (Kraken Futures) emit a meaningfully different weekend mark than the three independent venues, holding the underlying SPL constant?

**§5.2 — Forward-tape weekend dispersion.** Pairwise cross-venue mark dispersion during Friday-4pm-to-Sunday-8pm ET windows is the §5 headline figure. Hypothesis: under thin-flow, mark-formula divergence dominates and produces a directly observable band. Soothsayer's served (lower, upper) tuple at the corresponding target coverage either (a) brackets the cross-venue cluster — strong calibration win — or (b) is dominated by one venue's mark, indicating Soothsayer is anchoring on a single discovery surface.

**§5.3 — Trust-gap auxiliary test.** Per-venue volume collapse at the Friday 16:00 ET cash-market edge stratified per [[project_cex_stock_perp_coverage]]. A uniform open→closed collapse across reputable + disreputable venues is *methodology-shaped* and strengthens Soothsayer's pitch (it's the formula, not the brand). Retained weekend volume on reputable venues weakens the pitch toward a brand story.

**Calendar-time constraint.** ≥4 weeks of forward tape minimum before §5.2's DiD test has power against weekly demand drift. Tape capture daemons should be the gating ops task once wishlist 45 lands in scryer.

### Out-of-panel (mentioned for §5 completeness)

- **Bitget RWA-flagged stock perps** (14 tickers, ~$128M / 24h, 24/5 only with hard weekend freeze + funding suspended + liquidations halted Mon 04:00 → Sat 04:00 UTC+8): re-classified from "synthetic" in 2026-05-13 update. The Bitget hybrid is a *non-comparator* — its frozen-weekend posture is what §5.3 contrasts against the four-venue 24/7 xStock-backed panel.
- **MEXC stock-perps** reference the **Ondo Global Markets** tokenized-stock spot index (separate hidden oracle layer; 24/5 only, weekends + US holidays suspended) — surveyed in §2.1's tokenized-equity-surface analysis, not in this panel.
- **Phemex** (1 X-suffix SPYXUSDT + 13 plain, ~$5M / 24h): tiny volume floor, retained as a sanity-floor satellite if needed.
- **Geo-blocked from operator IP** (future-work, VPN-access path required): Binance Futures, Bybit. Listings overlap heavily with venues already in the panel; unblock is not gating for §5.

---

## References

| # | Citation | URL | Verified |
|---|---|---|---|
| 1 | Chainlink Data Streams overview | https://docs.chain.link/data-streams | Yes |
| 1a | Chainlink Data Streams v8 schema (RWA Standard, mid-only) | https://docs.chain.link/data-streams/reference/report-schema-v8 | Yes |
| 1b | Kamino Scope — `oracle_type.rs` (defines `ChainlinkRWA` adaptor) | https://github.com/Kamino-Finance/scope/blob/master/programs/scope/src/states/oracle_type.rs | Yes |
| 1c | Kamino Scope — Chainlink refresh handler (v8 dispatcher) | https://github.com/Kamino-Finance/scope/blob/master/programs/scope/src/handlers/handler_refresh_chainlink_price.rs | Yes |
| 1d | Kamino Scope — mainnet config (all xStock v8 feed IDs) | https://github.com/Kamino-Finance/scope/blob/master/configs/mainnet/3NJYftD5sjVfxSnUdZ1wVML8f3aC6mp1CXCL6L7TnU8C.json | Yes |
| 1e | Kamino governance — xStocks integration via Chainlink Data Standard | https://gov.kamino.finance/t/kamino-is-integrating-xstocks-powered-by-the-chainlink-data-standard-to-enable-tokenized-equities-lending/792 | Yes |
| 2 | Chainlink Data Streams v10 schema | https://docs.chain.link/data-streams/reference/report-schema-v10 | Yes |
| 3 | Chainlink Data Streams v11 schema | https://docs.chain.link/data-streams/reference/report-schema-v11 | Yes |
| 4 | Chainlink Data Streams — Tokenized Asset streams | https://docs.chain.link/data-streams/tokenized-asset-streams | Partial (page truncated) |
| 5 | Chainlink Data Streams — RWA streams | https://docs.chain.link/data-streams/rwa-streams | Partial (page truncated) |
| 6 | Chainlink Data Feeds on Solana | https://docs.chain.link/data-feeds/solana | Yes |
| 7 | Chainlink xStocks Alliance announcement | https://x.com/chainlink/status/1939763692301922621 | Yes |
| 8 | Chainlink ecosystem — xStocks | https://www.chainlinkecosystem.com/ecosystem/xstocks | Yes |
| 9 | Backed↔Chainlink xBridge launch (Dec 2025) | https://www.coindesk.com/web3/2025/12/12/backed-chainlink-launch-xbridge-to-move-tokenized-stocks-between-solana-and-ethereum | Yes |
| 10 | Pyth aggregation proposal | https://www.pyth.network/blog/pyth-price-aggregation-proposal | Yes |
| 11 | Pyth confidence interval primer | https://www.pyth.network/blog/pyth-primer-dont-be-pretty-confident-be-pyth-confident | Yes |
| 12 | Pyth Pro (formerly Pyth Lazer) docs | https://docs.pyth.network/lazer | Yes |
| 13 | Pyth blog — introducing Pyth Lazer | https://www.pyth.network/blog/introducing-pyth-lazer-launching-defi-into-real-time | Yes |
| 14 | Blue Ocean ATS + Pyth announcement | https://www.pyth.network/blog/blue-ocean-ats-joins-pyth-network-institutional-overnight-hours-us-equity-data | Yes |
| 15 | Pyth Lazer Solana mainnet (CO-PIP-5) | https://forum.pyth.network/t/passed-co-pip-5-release-pyth-lazer-on-solana-mainnet/1881 | Yes |
| 16 | Pyth HIP-3-as-a-Service docs | https://docs.pyth.network/price-feeds/hip-3-service | Yes |
| 17 | MagicBlock + Pyth Lazer | https://www.pyth.network/blog/magicblock-and-lazer-powering-a-new-wave-of-speed-for-solana-defi | Yes |
| 18 | Pyth Solana feed addresses | https://docs.pyth.network/price-feeds/core/push-feeds/solana | Yes |
| 19 | RedStone Live launch | https://blog.redstone.finance/2026/03/30/redstone-live-real-time-data-built-for-the-markets-that-never-sleep/ | Yes |
| 20 | RedStone RWA Solana launch (May 2025) | https://blog.redstone.finance/2025/05/28/redstone-rwa-oracle-brings-tokenized-assets-to-solana-ecosystem/ | Yes |
| 21 | RedStone HyperStone (Hyperliquid) launch | https://www.theblock.co/post/377776/redstone-launches-hyperstone-oracle-to-power-permissionless-markets-on-hyperliquid | Yes |
| 22 | Felix HIP-3 TSLA + HyperStone | https://blog.redstone.finance/2025/11/13/felix-launches-its-first-hyperliquid-hip-3-market-with-tsla-powered-by-hyperstone/ | Yes |
| 23 | Switchboard On-Demand docs | https://docs.switchboard.xyz/docs/switchboard/readme/designing-feeds/oracle-aggregator | Yes |
| 24 | Switchboard On-Demand GitHub | https://github.com/switchboard-xyz/on-demand | Yes |
| 25 | DIA Lumina product page | https://www.diadata.org/lumina/ | Yes |
| 26 | DIA Solana native oracles | https://www.diadata.org/solana-price-oracles/ | Yes |
| 27 | API3 dAPI documentation | https://docs.api3.org/oev-searchers/in-depth/dapis/ | Yes |
| 28 | API3 OEV mechanism | https://docs.api3.org/oev-searchers/in-depth/oev-network/ | Yes |
| 29 | Supra Oracles RWA expansion | https://www.financemagnates.com/thought-leadership/supra-expands-oracle-price-feeds-to-real-world-assets/ | Yes |
| 30 | Stork Network homepage | https://www.stork.network/ | Yes |
| 31 | Stork Network docs | https://docs.stork.network/ | Yes |
| 32 | eOracle EigenLayer launch | https://blog.eo.app/the-ethereum-oracle-now-live-on-eigenlayer-mainnet/ | Yes |
| 33 | eOracle docs (price feeds integration) | https://docs.eo.app/docs/price-feeds/integration-guide | Yes (redirect) |
| 34 | Chronicle Protocol equities launch | https://chroniclelabs.org/blog/chronicle-launches-onchain-equities-price-feeds | Unverified (429 rate-limit on fetch; secondary refs confirm) |
| 35 | Chronicle + Centrifuge partnership | https://www.morningstar.com/news/business-wire/20260108358859/centrifuge-selects-chronicle-as-primary-oracle-partner-for-tokenized-assets | Yes |
| 36 | UMA Optimistic Oracle | https://oracle.uma.xyz/ | Yes |
| 37 | Tellor whitepaper | https://tellor.io/wp-content/uploads/2023/04/Tellor-Whitepaper_4_2023.pdf | Yes |
| 38 | Hyperliquid native oracle docs | https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle | Yes |
| 39 | Hyperliquid Hyperps docs | https://hyperliquid.gitbook.io/hyperliquid-docs/trading/hyperps | Yes |
| 40 | Hyperliquid HIP-3 docs | https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals | Yes |
| 41 | Edge oracle introduction (Chaos Labs) | https://chaoslabs.xyz/posts/introducing-edge-the-next-generation-oracle | **404 at time of writing**; cached references survive in secondary coverage |
| 42 | Kamino Scope GitHub | https://github.com/Kamino-Finance/scope | Yes |
| 43 | Kamino Scope SDK | https://github.com/Kamino-Finance/scope-sdk | Yes |
| 44 | Drift Oracles docs | https://docs.drift.trade/protocol/trading/oracles | Yes |
| 45 | Drift Protocol Pyth case study | https://www.pyth.network/blog/drift-protocol-revolutionizing-derivatives-i-pyth-case-study | Yes |
| 46 | Backed Finance xStocks launch | https://www.prnewswire.co.uk/news-releases/backeds-xstocks-go-live-today-on-bybit-kraken-and-solana-defi-302494379.html | Yes |
| 47 | Kraken acquires Backed | https://blog.kraken.com/news/backed-acquisition | Yes |
| 48 | Ondo Finance + Chainlink (oracle layer) | https://ondo.finance/blog/defi-adoption-of-ondo-tokenized-stocks-live | Yes |
| 49 | Ondo Finance Solana 2026 plan | https://www.coindesk.com/business/2025/12/15/ondo-finance-to-offer-tokenized-u-s-stocks-etfs-on-solana-early-next-year | Yes |
| 50 | xStocks ecosystem case study (Solana foundation) | https://solana.com/news/case-study-xstocks | Yes |
| 51 | xStocks ecosystem audit critique | https://blockeden.xyz/blog/2025/10/30/xstocks/ | Yes |
| 52 | Cong et al. (2025) — Tokenized stocks | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5937314 | Already cited in references.md |
| 53 | State of Pyth Q3 2025 (Messari) | https://messari.io/report/state-of-pyth-q3-2025 | Yes |
| 54 | Pyth tokenized stocks integration roundup | https://www.mexc.com/news/198989 | Yes (secondary) |
| 55 | Phoenix orderbook (Ellipsis Labs) | https://github.com/Ellipsis-Labs/phoenix-v1 | Yes |
| 56 | Solana DeFi 2026 routers/lending/perps map (Eco support article) | https://eco.com/support/en/articles/14801178-solana-defi-stack-routers-lending-perps | Yes |
| 57 | CF Benchmarks — xStocks product suite launch | https://cfbenchmarks.com/blog/cf-benchmarks-xstocks-product-suite-is-live-with-regulated-indices-and-a-corporate-actions-feed | Yes |
| 58 | CF Benchmarks — indices documentation catalog | https://cfbenchmarks.com/documentation/indices | Yes |
| 59 | CFB Token Market Price Benchmarks Methodology Guide (v1.0, Feb 2026) | http://docs.cfbenchmarks.com/Token%20Market%20Price%20Benchmarks%20Series%20-%20Methodology%20Guide.pdf | Yes (PDF; 19 pp) |
| 60 | CFB Token Market Price Benchmarks Benchmark Statement (BMR Article 27) | https://docs.cfbenchmarks.com/Token%20Market%20Price%20Benchmarks%20Series%20-%20Benchmark%20Statement.pdf | Yes (PDF) |
| 61 | CFB xStocks Corporate Action Feed (May 2026) | https://docs.cfbenchmarks.com/CFB%20xStocks%20Corporate%20Action%20Feed.pdf | Yes (PDF; 18 pp) |
| 62 | Kraken — tokenized-equity perpetual futures product | https://blog.kraken.com/product/xstocks/tokenized-equity-perpetual-futures | Yes |
| 63 | SEDA Protocol homepage | https://www.seda.xyz/ | Yes |
| 64 | SEDA Protocol documentation | https://docs.seda.xyz/ | Yes |
| 65 | SEDA — session-aware oracle programs | https://docs.seda.xyz/home/session-aware-oracle-programs | Yes |
| 66 | SEDA docs llms-full corpus (canonical methodology source) | https://docs.seda.xyz/home/llms-full.txt | Yes |
| 67 | blocmates — SEDA: the backbone of 24/7 markets | https://www.blocmates.com/articles/seda-the-backbone-of-24-7-markets | Yes |
| 68 | Kraken Futures — xStock perpetuals (panel venue 1) | https://futures.kraken.com/ | Verified live |
| 69 | Gate.io Futures — stock perpetuals (panel venue 2) | https://www.gate.io/futures | Verified live |
| 70 | HTX (Huobi) Futures — stock perpetuals (panel venue 3) | https://www.htx.com/en-us/futures/ | Verified live |
| 71 | BingX Perpetual Futures — stock perpetuals (panel venue 4) | https://bingx.com/en/perpetual/ | Verified live |
| 72 | Dreamcash — USA500 HIP-3 market on Hyperliquid (SEDA consumer reference) | https://dreamcash.io/ | Verified via 3rd-party coverage |

---

## Top surprises and "we should know more about this" gaps

1. **CF Benchmarks (Kraken-owned) launched regulated xStock benchmarks on 2026-05-07 — and the methodology is silent on output coverage.** This is the strongest 2026-Q2 market signal: the vertically integrated Kraken-Backed-CFB stack has the regulatory rigor (FCA + BMR + Article 27) to ship a coverage-disclosed equity benchmark for tokenized markets, and chose not to. The Methodology Guide and Benchmark Statement publish a single per-second scalar $CCRTI_T$, with input-side trimming and contributor disclosure, but **no confidence / band / coverage / dispersion field on the wire and no statistical claim on the served value in any governance document**. The categorical surface for Soothsayer's calibration-transparency primitive is at its widest precisely as the tokenized-equity oracle space becomes a regulated category. **Strategic read: confirmatory market signal — validates demand for regulated tokenized-equity benchmarks while leaving the coverage-disclosed-band niche uncontested.**

2. **SEDA Protocol's USA500 composite is now in production on Hyperliquid (Dreamcash), Injective, Perps.Fun, Outcome, and Nunchi — with a four-pillar closed-market continuity methodology but a marketing-only "~95% Friday-to-Monday gap closure" claim and no held-out coverage number.** This is the cleanest contemporary example of a perp-DEX-oriented equity oracle that takes the *carry-methodology disclosure* axis seriously while leaving the *coverage-claim disclosure* axis untouched. Wire shape is scalar + `{active_session, was_stale}` flags; no band. Reinforces §2.1's framing that the calibration primitive remains orthogonal to all deployed integrity primitives.

3. **Edge (Chaos Labs) has displaced Pyth as Jupiter Perps' primary oracle.** This is a major Solana-DeFi shift, and the public methodology disclosure is a single blog post (currently 404'd) — i.e. *less* transparent than Pyth's pyth-conf primer despite handling 90%+ of Solana perp volume. Worth a dedicated paragraph in the rewrite, and worth following the Chaos Labs methodology page status (might be intentional pre-launch, might be deprecation).

4. **HyperStone (RedStone-HIP3) has run ~$1.5B cumulative volume of permissionless-equity-perp markets on Hyperliquid with zero published statistical-coverage claim.** This is the cleanest contemporary "equity-perp oracle with no calibration disclosure" archetype; the framing "Hyperliquid's HIP-3 ecosystem operationalizes equity-perp pricing entirely via opaque oracles" sharpens §2.1's core argument considerably.

5. **Ondo's 2026-Q1 Solana tokenized-stock launch explicitly delegates pricing to Chainlink — but Ondo Global Markets is already live on MEXC spot, with MEXC stock-perps referencing the Ondo-tracked spot index.** The Solana SPL launch hasn't materialized in the form originally expected, but the Ondo tokenized-equity layer is operational *today* on a major CEX spot venue and being indexed upstream of derivatives. The systemic-concentration framing for §1.1 / §9 needs softening: on Solana the canonical path is Chainlink-only by default, but the broader tokenized-equity pricing surface now has Ondo's parallel pipeline alongside Backed/CFB.

---

## Candidates for next-pass investigation

### What this section is for

The 22 surfaces above were the agent's pass on "what's deployed." Next pass is **claim vs. reality**: for every candidate below, two artefacts produced in parallel.

- **Methodology brief** (dedicated research agent) — what the provider *claims* the feed does: contributing venues, weights, off-hours rule, freshness/staleness logic, any stated calibration target. Source = docs / whitepaper / blog / forum / GitHub README. Output is a one-pager per provider, slotting into this memo's per-provider deep-dive shape.
- **Captured signal** (scryer scrape, new wishlist item) — what the feed *actually emits* under live observation. Output is a parquet venue under `dataset/{venue}/{data_type}/v1/`, ≥30 days of forward observation, with `_schema_version` / `_fetched_at` / `_source` metadata so we can run the same calibration battery (Kupiec / Christoffersen / DQ) on the incumbent we are surveying.

The point of doing both is that §2.1 currently says "no incumbent publishes a calibration claim on the served value" — which is the categorical claim — but the stronger paper claim is "no incumbent's *behavior under realised conditions* matches what its docs describe." Establishing that requires both halves.

**Scope filter.** Every candidate must plausibly publish a price or band that touches (a) an equity ticker (SPY/AAPL/etc.), (b) a tokenized-equity SPL/ERC-20 mint, (c) an RWA NAV that downstream Solana consumers price against, or (d) a perp/synthetic-equity contract reference. Pure-crypto oracles are out. Anything we already cover above is omitted unless flagged as "methodology gap" — those go in §"Methodology gaps in existing inventory."

### Methodology gaps in existing inventory (chase first)

These are in the 22-surface table but with thin or unverifiable methodology disclosure. Highest leverage because we already have parquet for several.

| # | Provider | Gap | Methodology source to chase | Scryer status |
|---|---|---|---|---|
| G1 | **Edge (Chaos Labs)** | Public methodology page (chaoslabs.xyz/posts/introducing-edge-the-next-generation-oracle) 404 at 2026-05-11. Powers Jupiter perps + >$30B cumulative volume. | Chaos Labs blog, GitHub `chaos-labs/edge-*` (verify), Jupiter Perps technical docs, any podcast/conference talk transcripts from the Chaos Labs founders 2025–2026 | No parquet. Worth a forward-cursor scrape if a public endpoint exists; otherwise on-chain reads of the Jupiter perps oracle PDA. |
| G2 | **Stork Network** | Marketing claims "leading equity-perp oracle"; no public symbol list, no methodology paper. | docs.stork.network deep pages, Stork GitHub, any HIP-3 deployer that names Stork as oracle, Stork API token-gating model | No parquet. Likely scrapeable via public Stork REST or pull-aggregator pattern. |
| G3 | **RedStone Live methodology** | Blog post links a deep methodology page that 404s; contributing-venue list, weights, off-hours consensus rule not published. | Re-fetch periodically (page may be intentionally pre-launch); RedStone forum, GitHub `redstone-finance/redstone-oracles-monorepo` config files for the Live feed | Have `redstone/oracle_tape` parquet already. Diff what's in-flight vs. what docs claim. |
| G4 | **Chronicle Onchain Equities Price Feeds** | Original launch blog (chroniclelabs.org/blog/chronicle-launches-onchain-equities-price-feeds) returned 429 on fetch; need to retry off-hours. | Chronicle docs, Chronicle GitHub, the Centrifuge partnership announcement | No parquet. EVM-only; on-chain reads possible via Ethereum/Base RPC. |
| G5 | **Switchboard equity aggregation semantics** | Aggregator reducers (median/mean/etc.) documented; what publishers a *deployed* equity feed actually reads from is per-feed config and not in public docs. | Switchboard On-Demand GitHub, any deployed equity-feed PDA on Solana mainnet, MarginFi historical feed configs | No parquet. On-chain reads of any equity feed PDA. |
| G6 | **Chainlink v10/v11 `tokenizedPrice` provenance** | Doc says "24/7 CEX-aggregated mark" for v10 `tokenizedPrice`; venues, weights, halt rule not published per-feed. | Chainlink Data Streams reference, Chainlink Ecosystem (xStocks), Chainlink GitHub `chainlink/chainlink` for the verifier program code | Have `chainlink/data_streams` parquet. Cross-reference v10 `tokenizedPrice` vs. observable CEX mids on the same minute. |
| G7 | **Pyth aggregate vs. publisher behaviour outside session** | `pyth-conf` recommends 95% publisher coverage but the aggregate's behaviour outside the calibrated range (e.g., during equity halt) is undefined. | Pyth governance forum, Pyth GitHub `pyth-network/pyth-client`, recent published-publisher list for equity feeds | Have `pyth/oracle_tape` parquet. The empirical answer is in the parquet. |

### Tier A — Net-new oracle providers worth a methodology pass

| # | Provider | Hypothesis | Docs URL (start here) | Priority |
|---|---|---|---|---|
| A1 | **Band Protocol / BandChain** | Cosmos-rooted oracle with historical equity feeds via Yahoo/CEX aggregation. Verify whether any 2026-era surface still publishes equity prices and to which destination chains. | docs.bandchain.org | P1 |
| A2 | **Pragma Network** | Starknet-native oracle; 2025–2026 RWA push. Verify equity feed list and bridge to Solana/EVM (if any). | pragma.build / docs.pragma.build | P1 |
| A3 | **Acurast** | TEE-attested confidential-compute oracle, Polkadot-rooted, Solana-bridged. Plausible niche for issuer-NAV attestation. | acurast.com / docs.acurast.com | P2 |
| A4 | **Ojo Network** | Cosmos restaking-secured oracle, 2025 launch. Verify equity feed coverage and EVM/Solana bridges. | ojo.network | P2 |
| A5 | **TruFlation** | Index oracle (inflation), but also publishes synthetic asset/macro indices. Verify whether any equity-index feed is deployed. | truflation.com | P2 |
| A6 | **Witnet** | Decentralized witness-based oracle, EVM-rooted. Historically thin on equities. | witnet.io | P3 |
| A7 | **Razor Network** | Staking-based, claims equity feeds in marketing. | razor.network | P3 |
| A8 | **Umbrella Network** | L2 oracle aggregator. | umb.network | P3 |
| A9 | **Nest Protocol** | Chinese quotation-mining oracle (interesting mechanism); unclear if equity coverage is real. | nestprotocol.org | P3 |
| A10 | **Flux Protocol** | Cross-chain, NEAR-rooted. | fluxprotocol.org | P3 |
| A11 | **DIA Custom Feeds** | DIA Lumina advertised but the *custom-feed* configuration is the actually-deployed surface. Verify any equity custom feed on EVM or Solana. | docs.diadata.org | P2 |
| A12 | **Chainlink Functions / Automation as oracle proxy** | Some teams build app-specific oracles atop Chainlink Functions. Worth a quick survey of who's done this for equities. | docs.chain.link/chainlink-functions | P3 |

> **Footnote on "Chainlink Smart Data Streams".** This phrase appears in conference talks, integrator decks, and verbal product-marketing — but it is **not a discrete Chainlink product**. The Chainlink umbrella has "Smart Data" (a general-purpose feed family that includes Data Feeds, Data Streams, CCIP, Proof-of-Reserve, Functions, Automation) and "Data Streams" (the v10/v11 schema family this paper analyses); "Smart Data Streams" is a verbal cluster collapsing the two and does not correspond to a separate methodology, schema, or wire format. Removed from candidate inventory; not pursued further.

### Tier B — RWA NAV publishers (equity-adjacent; institutional anchor surfaces)

These are *not* general-purpose oracles. They publish the reference value used by issuers for mint/redemption and by downstream lenders for collateral marks. Verify whether each one publishes an on-chain reference price or only an off-chain NAV.

| # | Surface | Hypothesis | Source to chase | Priority |
|---|---|---|---|---|
| B1 | **BlackRock BUIDL NAV publisher (BNY Mellon)** | NAV published off-chain; consumed on-chain by RedStone RWA-Solana. Verify the publication cadence and any on-chain reference. | securitize.io BUIDL page, RedStone RWA-Solana blog | P1 |
| B2 | **Ondo OUSG / USDY NAV publisher** | Ondo runs its own NAV pipeline for OUSG/USDY independent of the Chainlink price layer it delegates to for tokenized stocks. | ondo.finance docs, OUSG token contract on Ethereum | P1 |
| B3 | **Franklin Templeton BENJI NAV** | Mature on-chain fund, NAV published daily. | franklintempleton.com, BENJI Stellar/Polygon contracts | P2 |
| B4 | **Hashnote USYC oracle** | On-chain reference rate for the Hashnote yield fund; methodology partially published. | hashnote.com, USYC contract docs | P1 |
| B5 | **Securitize STAC reference value** | Securitize publishes a per-share reference used by Chronicle's Proof-of-Asset; verify the data path. | securitize.io, Chronicle blog (STAC integration) | P1 |
| B6 | **Backed Finance issuer reference NAV** | Backed runs an internal NAV pipeline for xStock mint/redemption; verify whether it is ever published on-chain. | backedfi.com docs, Kraken acquisition disclosures | P1 |
| B7 | **Apollo ACRED NAV publisher** | Apollo + Securitize tokenized fund consumed by RedStone RWA-Solana. | redstone blog, Securitize ACRED page | P2 |
| B8 | **Maple Finance pool NAV** | Maple lends against tokenized-credit pools; pool NAV is the effective mark. | maple.finance, pool contracts | P3 |

### Tier C — Upstream data sources oracles consume (ground-truth comparators)

These are the *input* feeds that Pyth publishers, Chainlink node operators, Switchboard jobs, etc. read from. For the empirical-vs-claimed methodology comparison we need at least one of these as an independent benchmark, otherwise we are comparing one opaque feed to another.

| # | Source | Why we care | Access | Priority |
|---|---|---|---|---|
| C1 | **Polygon.io equities** | Widely used by Pyth publishers and Switchboard jobs. Real-time + historical, REST + WebSocket. Free tier limited. | polygon.io API | P0 |
| C2 | **Alpaca Markets** | Broker-grade equity data, free tier with paper-account auth. | alpaca.markets API | P1 |
| C3 | **Finnhub** | Equity data, free + paid tiers, decent historical depth. | finnhub.io API | P1 |
| C4 | **IEX Cloud** | Wind-down 2024; verify if any successor (IEX Cloud → Iexapis) is still queryable. | iexcloud.io / iexapis.com | P3 |
| C5 | **Blue Ocean ATS direct** | Pyth has exclusive on-chain distribution of Blue Ocean overnight book; the upstream itself is a paid feed. Useful for ground-truth on Pyth Pro overnight prices. | blueoceanats.com (institutional sales) | P2 |
| C6 | **Databento OPRA / GLBX.MDP3 / XCEC** | Already used by scryer for CME futures and Blue Ocean overnight (`bo_intraday_1m.v1`). Could extend to equity-options surface for tail-distribution comparators. | databento.com | P1 |
| C7 | **NYSE TAQ / NASDAQ TotalView** | Institutional T&S; gold-standard but paid only. Worth pricing for the paper's calibration baseline. | nyse.com, nasdaq.com | P2 |
| C8 | **Yahoo Finance** | Already on scryer (`yahoo/equities_daily`). End-of-day only; not an oracle comparator at sub-day granularity. Mentioned for completeness. | — | — |

### Tier D — Effective oracles via CEX index marks and DEX TWAPs

No standalone oracle product, but the price plane these surfaces emit is what HIP-3 deployers, perp DEXes, and lending markets are *actually* pricing against — sometimes routed through one of the oracles above, sometimes not. Each of these is plausibly a hidden oracle layer.

| # | Surface | Hypothesis | Access | Priority |
|---|---|---|---|---|
| D1 | **Kraken Pro xStock reference price** | Kraken acquired Backed/xStocks late 2025. Verify whether Kraken publishes a reference/index price for xStocks as part of the post-acquisition product surface. | kraken.com API | P0 |
| D2 | **MEXC stock-perp index price** | Per `[[project_cex_stock_perp_coverage]]`, MEXC lists synthetic stock perps; the index they reference is functionally an oracle. | mexc.com perpetual-index API | P1 |
| D3 | **Gate.io stock-perp index** | Same pattern. | gate.io perpetual-index API | P1 |
| D4 | **Bitget / BingX / HTX / Phemex stock-perp indices** | Same pattern, lower volume; bundle as a single sweep. | per-venue API | P2 |
| D5 | **Solana DEX TWAPs for xStock mints** | Orca / Raydium / Meteora / Phoenix-equivalents — the xStock secondary-market mid that any on-chain consumer can compute directly. Plausibly the cheapest "shadow oracle" available. | scryer already has `dex_xstock_swaps.v1` and `dlmm_pool_state.v1` / `clmm_pool_state.v1` (per scryer wishlist 51c–51e); compute TWAP consumer-side. | P0 (already in flight) |
| D6 | **GeckoTerminal API for xStock mints** | Aggregates Solana DEX mids into a single endpoint; broker-grade but free-tier accessible. | api.geckoterminal.com | P1 |
| D7 | **Birdeye API for xStock mints** | Solana-specific aggregator; some protocols read from Birdeye directly. | public-api.birdeye.so | P1 |
| D8 | **CoinGecko API for xStock mints** | Mainstream aggregator; xStocks listed individually as crypto assets there. | api.coingecko.com | P2 |

### Cross-cutting scryer scrape plan

Per CLAUDE.md hard rule #2 ("New data sources land in scryer first"), each scrape candidate above becomes a scryer wishlist row, not a soothsayer-side fetcher. Pattern for the proposal (drop-in for `/Users/adamnoonan/Documents/scryer/wishlist.md`):

```
| 55 | oracle.{provider}.tape.v1 | proposed | Endpoint: {URL}. Cadence: {interval}. Schema: {symbol, ts_publish, price, bid?, ask?, conf?, status, raw_payload}. Methodology lock: TBD post-research-agent pass. |
```

Priority ordering for scryer queue (suggested):
1. **P0 first** — Edge (G1), Kraken xStock reference (D1), Polygon.io equity ticks (C1), DEX TWAP harness (D5, already in flight via wishlist 51).
2. **P1 next** — Stork (G2), Chronicle (G4), Pragma (A2), Band Protocol (A1), the BUIDL/OUSG/USYC NAV publishers (B1, B2, B4), Alpaca/Finnhub (C2, C3), MEXC/Gate.io index marks (D2, D3), GeckoTerminal/Birdeye xStock TWAPs (D6, D7).
3. **P2 / P3** — defer until the P0/P1 tape is producing the audit-gap table.

### What this enables for §2.1

Once the methodology briefs + at least 30 days of captured signal exist for the P0 candidates, the paper can replace its current "no incumbent publishes a calibration claim" categorical with an **audit-gap table**:

| Provider | Methodology claim (docs) | Observed weekend behaviour (scryer) | Audit gap |
|---|---|---|---|
| Chainlink v11 weekend bid | "extended-hours quote" | 100% incidence of `.01`-suffix synthetic bookend on SPYx/QQQx/TSLAx | Synthetic, not extended-hours |
| Edge / Jupiter Perps oracle | (TBD) | (TBD) | (TBD) |
| RedStone Live | "blends institutional + perp data" | (TBD) | (TBD) |
| Stork equity-perp | "real-time 24/5" | (TBD) | (TBD) |
| Pyth Pro overnight (Blue Ocean) | "8pm–4am ET Sun–Thu executable book" | Verifiable against scryer `bo_intraday_1m.v1` | Likely matches claim; weekend remains uncovered |

That's the table the rewrite is aimed at producing. The candidates list above is the work plan for filling its rows.

---

## 2026-05-13 research update — closed candidates and new entries

This section captures the outcomes of three rounds of follow-up research (P0 audit-gap closure, Tier A net-new providers, G-gap remainder, Tier D shadow oracles). Findings that warrant a master-table row are reproduced here as drop-in markdown; corrections to existing rows are listed so they can be merged on the next pass; closed candidates from §"Methodology gaps" / §"Tier A" / §"Tier D" are marked with their dated outcome.

The two slices still open are **Tier B (NAV publishers)** and **Tier C (upstream comparators)**. Everything else in the candidates list above has been resolved.

### TL;DR — what changed in the inventory

- **2 new full rows to add** to the master table: **CFB xStocks Indices** (regulated off-chain benchmark powering Kraken xStock perps, launched 2026-05-07) and **SEDA Protocol** (Flux's successor; USA500 composite consumed by Hyperliquid/Injective/Dreamcash/Perps.Fun).
- **1 new tokenized-equity issuer surface** alongside Backed/xStocks: **Ondo Global Markets** is operational on MEXC spot (under "Ondo tokenized U.S. stock spot index"), upstream of MEXC's stock-perpetual index. The original survey treated Ondo as a Q1-2026 announcement; it is live on MEXC today.
- **6 CEX stock-perp rows worth a §5 panel block**: BingX (panel volume leader, ~$252M / 24h, 57 stock-themed perps), Gate.io (most index-transparent: closed venue list + clip-band + 20s stale + public `/index_constituents`), HTX (5 X-suffix Backed-xStocks, low volume), Bitget (24/5 not 24/7, RWA-flagged hybrid, weekend mark-freeze), Phemex (worked example of "hold-last on quorum < 3"), MEXC (Ondo dependency).
- **3 row corrections to existing master-table entries**: Pyth aggregate `status` semantics (never emits `Halted`); RedStone Live methodology disclosure (no public methodology page exists; the load-bearing disclosure is the public node-manifest JSON in the monorepo, sources are 6 tier-2 redistributors, off-hours blending is stepwise session-gated, not continuous); Stork (Solana surface dormant since 2025-09-25, equity feeds only on RISE testnet, but methodology *is* published in `24-7-price-feeds.md` — the original "marketing-grade only" framing was too harsh).
- **2 row downgrades**: Switchboard (full row → one-line dismissal; zero deployed equity feeds, AAPL only in tutorial example), Stork (full row → one-line dismissal on Solana terms specifically; full row may still be warranted on EVM-perp-DEX terms).
- **1 footnote clarification**: "Chainlink Smart Data Streams" is **not a real product** — verbal-cluster confusion between Data Streams (pull, low-latency reports v3-v11) and SmartData (a Data Feeds sub-suite for NAV / Proof-of-Reserve / AUM, schema v9). The two overlap once: Data Streams schema v9 reuses the SmartData label.
- **DIA reframe**: Lumina ≠ Custom Feeds — Custom Feeds is a *capability inside* Lumina; xReal is the RWA marketing wrapper; deployed equity tickers (ADBE, META, NFLX, MSTR, MA, HOOD) on Arbitrum / Optimism / Base / Sonic only; AAPL/MSFT/NVDA appear only as marketing examples; SPY/TSLA not deployed; no Solana presence; no xStocks-issuer partnership. Belongs in §2.1 as a **contrast**: "publishes *how* a number was computed, not *how often it's wrong*."

### New full rows to add to master table

To merge into the §"Master table" block above (insert in Chainlink-Pyth-RedStone neighborhood):

| Provider | Chain(s) | What it reports for equities | Symbols covered (sample) | Off-hours behavior | Uncertainty field | Methodology disclosure | Known Solana integrations | We have parquet? |
|---|---|---|---|---|---|---|---|---|
| **CFB xStocks Indices** (CF Benchmarks, Kraken-owned) | Off-chain only (REST/WebSocket) | Regulated PR + TR benchmark per xStock symbol; ~100 indices | All ~50 xStock symbols (per Kraken xStocks Spot listing) | "anchored to underlying during regular hours; market-makers blend ATS + index-futures + internal models off-hours" | None published per index | FCA-supervised, BMR-aligned; "Token Market Price Benchmarks Series" with public Methodology Guide + Benchmark Statement | None on-chain — powers Kraken xStocks perp markets | No |
| **SEDA Protocol** (Flux successor) | Multiple rollups (not Solana as of 2026-05-13) | "SEDA Benchmark" composite = 60% equities + 25% crypto + 15% commodities (USA500); also single-name benchmarks | USA500 composite; per-name product roadmap | Continuous via composite construction | None published | Whitepaper + GitHub `seda-xyz/*` | None on Solana | No |
| **Ondo Global Markets** (Ondo Finance) | Off-chain index → MEXC spot venue (live); Solana SPL launch announced for 2026 | Issuer-tracked tokenized US equity spot index ("Ondo tokenized U.S. stock spot index"); referenced upstream by MEXC stock-perp `fairPrice` | TSLA, AAPL, NVDA, MSFT, GOOGL, META, AMZN, MSTR, COIN, HOOD, PLTR, AMD, TSM, JPM, BABA + SPY, QQQ ETFs (per MEXC listing) | 24/5 only on MEXC (suspended weekends + US holidays); off-chain index continuous | None on the wire | Ondo blog announcements; MEXC stock-futures landing; constituent venues for the index not publicly enumerated | Solana SPL launch announced 2025-12-15 for Q1-2026 (Coindesk); not verified live as of 2026-05-13 | No |

CEX stock-perp panel — these belong in §5 as a comparison block:

| Venue | Surface | Backing model | Stock-perp coverage | Index methodology | Wire fields | 24h volume (2026-05-14 probe) | Confidence/coverage field |
|---|---|---|---|---|---|---|---|
| **BingX** | USDT-M perps | 4 X-suffix Backed.fi xStocks + 53 NCSK-prefix from "institutional liquidity provider" (NCSK ≠ Backed) | AAPLX, NVDAX, METAX, PLTRX + NCSK-MRVL/ASML/CRCL/INTC/NVDA/META/AAPL... | Mark = `Median(Price1, Price2, Last)`; index = 9-venue (Binance/OKX/Coinbase/Bitstamp/Bittrex/Gate/MEXC/Kraken/Bybit) 3% trim + re-equal-weighted | `markPrice`, `indexPrice`, `lastFundingRate`, `nextFundingTime`, `min/maxFundingRate`, `fundingIntervalHours` | **~$252M (panel leader)** | None |
| **Gate.io** | USDT-M perps | xStock-backed (X-suffix); plain-ticker variants exist | GOOGLX, TSLAX, DFDVX, MSTRX, QQQX, SPYX, AMZNX, AAPLX, NVDAX, COINX, METAX, HOODX, CRCLX (1-10× lev) | Closed-list weighted avg over Gate/Binance/OKX/Bybit/Bitget/Coinbase/KuCoin/MEXC/Gate-Alpha/PancakeSwap; **clip to [0.2×, 1.8×] band** at rebalance; 20-second stale-out → weight zero; daily 08:00 UTC rebalance | `index_price`, `time` (klines add OHLCV); **`/futures/{settle}/index_constituents/{index}` exposes constituent set publicly (no auth, no weights)** | Material but small relative to crypto perps; TSLAX spot ~$10-12M / 24h | None |
| **HTX** | USDT-M perps | 5 X-suffix Backed-xStocks (TSLAX/MSTRX/AMZNX/COINX/PLTRX) + 9 plain | TSLAX, MSTRX, AMZNX, COINX, PLTRX (X-suffix); NVDA, META, MSFT, SPY, GOOGL, AAPL, QQQ, AMD (synthetic) | Per-symbol disclosure missing; X-suffix `swap_premium_index_kline` returned 404 (premium-index telemetry thinner than crypto) | `index_price`, `index_ts`, `contract_code`, `trade_partition` | ~$22M aggregate / 24h | None |
| **Bitget** | USDT-M perps | RWA-flagged hybrid (`isRwa: YES`); xStock-anchored basket, cash-settled | TSLA, AAPL, NVDA, SPY, QQQ, MSFT, AMZN, GOOGL, META, MSTR, COIN + leveraged-ETF TQQQ/SQQQ | Liquidity-and-volume-weighted composite of "tokenized stock prices from multiple issuing platforms and exchanges" | `indexPrice`, `markPrice`, `fundingRate`, `usdtVolume`, `lastPr` | **~$128M / 24h but 24/5 only** (Mon 04:00 → Sat 04:00 UTC+8); weekend mark frozen, funding suspended, liquidations halted | None |
| **Phemex** | USDT-M perps | 1 X-suffix (SPYXUSDT, Backed) + 13 plain (synthetic) | SPYX (Backed); TSLA, AAPL, NVDA, QQQ, MSFT, AMZN, GOOGL, META, MSTR, COIN, PLTR, AMD (synthetic) | 6-venue (Binance/Coinbase/OKEx/Kraken/Bitfinex + Binance USDT/USD) **trim-mean of middle 4**; **min 3 sources or hold-last**; 15-second staleness rejection | `markRp`, `indexRp`, `lastRp`, `fundingRateRr`, `predFundingRateRr`, `openInterestRv`, `turnoverRv`, `bidRp/askRp` | ~$5M / 24h (smallest of panel) | None on the wire; bid/ask available so spread is computable |
| **MEXC** | USDT-M perps | Synthetic, but **references the Ondo Global Markets tokenized-stock spot index** (third hidden oracle layer) | TSLA, AAPL, NVDA, COIN, HOOD, AMZN, GOOGL, META, MSTR, MCD, MSFT, AMD, TSM, JPM, BABA + SPY, QQQ ETFs; up to 25× lev; funding waived (zero) | Weighted avg of "major spot exchanges" with ±1% deviation drop + stale-feed exclusion; constituent list **not publicly disclosed** (only BTC index discloses constituents = Bitget/Bybit/Binance/HTX/OKX/MEXC/KuCoin) | `symbol`, `indexPrice`, `timestamp` (no spread/conf/status) | Per-pair stock-perp volume not exposed by aggregators (diagnostic of small book) | None |

Aggregate stock-perp 24h volume on **just BingX + Bitget + HTX + Phemex** = **~$407M**, roughly 3-4 orders of magnitude above the on-Solana xStock DEX flow soothsayer prices natively. This sharpens the §1.2 trust-gap framing considerably.

### Corrections to existing master-table rows

1. **Pyth Network (core)** — the `status` enum on the *aggregate* is `trading | halted | unknown`, but per `pyth-client/program/c/src/oracle/upd_aggregate.h:135-222` the on-chain aggregator **never produces `Halted`**. `Halted` exists only as a publisher-input value; if too few publishers are TRADING (`numv < min_pub_`), the aggregator returns `Unknown` and **does not overwrite `agg.price_` or `agg.conf_`**, leaving the consumer to fall back to `prev_price_/prev_conf_/prev_slot_/prev_timestamp_`. Update the "Off-hours behavior" cell to: "`status` enum on aggregate is `Trading | Unknown` (Halted only on publisher inputs); on insufficient TRADING publishers the aggregate freezes — `prev_*` fields preserve last-good across the outage."

2. **Pyth Pro / Lazer** — replace the explicit `PriceStatus` enum description with the actual Pro semantics: 3 softer signals — `marketSession` enum (`closed | preMarket | postMarket | regular`); `feedUpdateTimestamp < timestampUs` ⇒ carried-forward stale price; the `price` field can be **absent** during off-hours. Behavior at the **Blue Ocean → pre-market 4am ET handover is documented nowhere**.

3. **RedStone Classic + Live** — the "deep methodology page that 404s" claim should be replaced with a stronger, more accurate finding: **no separate methodology page exists**. The load-bearing disclosure is the public node-manifest JSON in `redstone-finance/redstone-oracles-monorepo/packages/node-remote-config/dev/manifests/data-services/{primary-ws,hip3-mainnet,main}.json`. From the `primary-ws` ("Live") manifest:
   - **Equity sources are 6 tier-2 redistributors per symbol**: AllTick (`alltick-stocks-api-deferred`), Databento, FMP (`financialmodelingprep-deferred`), Polygon.io websocket (`ws-polygon-massive`), Twelve Data websocket (`ws-twelve-data`), DXfeed websocket (`ws-dx-feed`). **No Bloomberg, no Refinitiv, no NYSE TAQ direct, no Nasdaq TotalView direct.**
   - Top-level aggregator = `median` at 500ms interval. No LWAP/VWAP for equities.
   - **Off-hours blending is NOT continuous.** It is stepwise gated by exchange-session enums (`NY_MARKET_CURRENT_STATUS`, `CME_MARKET_CURRENT_STATUS`, etc.) sourced from `*-market-timeline` providers. The "blends institutional + perpetual" marketing is achieved at the *consumer* level (the dApp picks spot vs `<SYM>---PERP` feed), not at the oracle level.
   - HIP-3 (HyperStone) feeds use `constantWeightMedian` with `{hyperliquid:10, hydromancer:1}` (Hydromancer = RedStone's internal perp-aggregation feeder).
   - Wire schema: no confidence / spread / coverage field. Signed by 3 RedStone nodes per batch (5-of-N quorum on mainnet).
   - **Solana RedStone publish path covers RWAs only** (BUIDL, ACRED, VBILL, SCOPE) — **no xStock SPL feed exists in any RedStone manifest**. Equities are HyperEVM/HIP-3.

4. **Switchboard** — downgrade verdict. Confirmed zero curated equity catalog: AAPL appears only in a Polygon.io tutorial example; MarginFi uses Switchboard for static stub feeds (zero/1e-6/1e-8 placeholders); Kamino xStocks integration explicitly chose Chainlink, not Switchboard. Wire schema = `(price=median, std_dev, slot, oracle_pubkey_list)` — std_dev is sample standard deviation, not a symmetric confidence band. No native market-hours/halt semantics; left to integrator's job graph + consumer's staleness gate.

5. **Stork Network** — original "marketing-grade only" framing was too harsh in one direction and not harsh enough in another. **Methodology IS published** in `Stork-Oracle/Documentation/resources/24-7-price-feeds.md`: per-venue Impact Bid/Ask → EMA smoothing (parameter τ) → median across venues → weighted blend with last traditional close (parameter W) → deviation cap C bps. Source venues for liquid RWA: Binance, Bitget, Hyperliquid, Lighter, OKX. **But** per-asset publisher identities, weights, and parameter values are NOT published; wire schema (`TemporalNumericValueFeed = { id: [u8;32], latest_value: { timestamp_ns: u64, quantized_value: i128 } }`) carries no confidence band. **Solana surface is dormant**: program `stork1JUZMKYgjNagHiK2KdMmb42iTnYe9bYUCDUk8n` has only ~10 active feeds (BTCUSD/ETHUSD/APTUSD/DOGEUSD + 6 unidentified crypto) — **zero equity tickers on Solana mainnet**. Last on-chain push: **2025-09-25**. Equity `_24_5` feeds (TSLA/SPY/NVDA/HOOD/COIN) exist **only on RISE testnet**. Mainnet equity-perp consumers (Lighter, Ostium, Paradex, etc.) are EVM L2/zk only. **Stork's 8-asset 24/7 RWA launch was announced 2026-05-13** (TSLA/CRCL/NVDA/MSTR + gold/silver/WTI/Brent).

6. **Edge (Chaos Labs)** — no major correction needed; the "404'd intro post" finding still holds but the schema is now confirmed via the Dove wrapper accounts (`DoVEsk76QybCEHQGzkvYPWLQu9gzNoZZZt3TPiL597e`, account discriminator `priceFeed`, fields `{price: i64, expo: i32, timestamp: i64}`). Edge has **no confidence field**, only **5 crypto pairs** (SOL/ETH/BTC/USDC/USDT), and **no equities/RWA roadmap publicly hinted**. Jupiter wraps Edge in 2-of-3 fallback with Pyth + Chainlink.

7. **Chronicle Protocol** — equity launch confirmed as 2025-07-28; only **SPY/USD** verified live on Chronicle's dashboard (`chroniclelabs.org/dashboard/oracle/SPY/USD`); EVM-only across 14 chains; no Solana deployment, no announced Solana roadmap; PoA layer is reserve-attestation, structurally separate from equity price feed. Aggregation is "median-of-medians, unopinionated"; signed via Schnorr/MuSig2 over `(asset, price, timestamp)`. **No confidence wire field, no off-hours/halt policy disclosed.** Best read as "credibility play built on PoA brand — methodology-light, no confidence semantics on the wire, EVM-only competitor to Chainlink Data Streams."

### New per-provider deep dives

#### CFB xStocks Indices (CF Benchmarks, Kraken-owned)

CF Benchmarks is the regulated benchmark subsidiary Kraken acquired in 2019. On **2026-05-07**, four days after Kraken's Bybit-rivaling xStocks-perpetual-futures product cycle, CFB launched the **CFB xStocks Indices** family at `cfbenchmarks.com/blog/cf-benchmarks-xstocks-product-suite-is-live-with-regulated-indices-and-a-corporate-actions-feed`. The product:

- ~100 regulated real-time benchmarks: each xStock symbol gets a Price Return (PR) and Total Return (TR) variant
- FCA-supervised, BMR-aligned; sits inside CFB's "Token Market Price Benchmarks Series" parent family with public Methodology Guide + Benchmark Statement (`cfbenchmarks.com/documentation/indices`)
- Distribution: REST / WebSocket to venues; **off-chain only — no on-chain oracle integration mentioned**
- "Already power Kraken xStocks perpetual markets" (Kraken launched its xStock perps 2026-02-24, world's first regulated tokenized-equity perps; 10 symbols, up to 20× lev)

For Paper 1 §5 framing this is consequential: the upstream price layer for xStocks bifurcates into four operational tiers — **Backed internal NAV → CFB regulated indices (off-chain) → Chainlink Data Streams (on-chain) → DEX-derived TWAPs (Solana)** — and **neither CFB nor Chainlink publishes a coverage-vs-width calibration curve**. The contrast is a cleaner version of the §1.1 thesis than was available before this launch.

This was missed by every prior xStock oracle survey (it post-dates them by days), so it is also citation-novelty.

Sources: [CF Benchmarks xStocks launch (2026-05-07)](https://www.cfbenchmarks.com/blog/cf-benchmarks-xstocks-product-suite-is-live-with-regulated-indices-and-a-corporate-actions-feed), [CFB indices catalog](https://www.cfbenchmarks.com/documentation/indices), [Kraken xStocks perp launch (2026-02-24)](https://blog.kraken.com/product/xstocks/tokenized-equity-perpetual-futures), [Kraken xStocks FAQ](https://support.kraken.com/articles/xstocks-faq).

#### SEDA Protocol (Flux Protocol successor)

Flux Protocol is sunset (last commits on `fpo-evm`/`fpo-node` core repos late 2022; multiple repos archived). The team migrated to **SEDA Protocol** (`seda.xyz`), now operating as a distinct, live oracle product family. SEDA's "Benchmark" product publishes:

- **USA500 composite** = 60% equities + 25% crypto + 15% commodities
- Production consumers as of 2026-05-13: **Hyperliquid, Injective, Dreamcash, Perps.Fun** — i.e., 24/7 derivatives venues that need a continuous equity-class reference
- Distinct chain support; Solana not currently listed

For Paper 1 §2.1 framing, SEDA is structurally a peer of HyperStone (RedStone-Hyperliquid) and Pyth-HIP-3-as-a-Service: equity-composite-as-a-service for perp protocols, with no published statistical-coverage claim. Distinct from Chainlink/Pyth-core (single-name equity tickers / xStock SPL mints) and from CFB xStocks Indices (regulated benchmark for spot tokenized equities). It is **not a Solana xStock pricing-plane competitor**; it is a HIP-3-equivalent perp-oracle competitor that the original survey missed because of the Flux→SEDA brand migration.

Sources: SEDA whitepaper / docs (`seda.xyz`), GitHub `seda-xyz/*`, public consumer announcements from Hyperliquid / Injective / Dreamcash / Perps.Fun (per indexed coverage).

#### Ondo Global Markets — third operational tokenized-equity surface

Ondo Finance was previously known in this inventory as the OUSG/USDY issuer with a 2026-Q1 Solana tokenized-stock launch announcement (Coindesk 2025-12-15). Independently, **Ondo Global Markets** has been listing tokenized US equities on **MEXC spot** in batched cohorts through 2026 (`blog.mexc.com/mexc-ondo-expand-tokenized-stock-19-new-spot-pairs/`). MEXC's USDT-margined stock perpetuals reference this Ondo-tracked spot index, NOT direct CEX/CME equity feeds (`mexc.com/futures/stock-futures` explicitly states "fair price pegged to the Ondo tokenized U.S. stock spot index").

This makes Ondo a third operational tokenized-equity surface alongside (a) Backed/xStocks (Chainlink Data Streams + CFB Indices) and (b) the dispersed CEX-internal synthetics (BingX NCSK, Bitget RWA-flagged baskets). For Paper 1 §1.1 the implication is that the "single-vendor concentration" claim — Backed + Ondo both delegate to Chainlink — needs softening to reflect Ondo's parallel pipeline through MEXC.

The Ondo-tracked-spot-index methodology, constituent venues, weights, and confidence semantics are not publicly enumerated.

Sources: [MEXC stock-futures landing](https://www.mexc.com/futures/stock-futures), [MEXC + Ondo expansion blog](https://blog.mexc.com/mexc-ondo-expand-tokenized-stock-19-new-spot-pairs/), [Ondo Solana plan (Coindesk)](https://www.coindesk.com/business/2025/12/15/ondo-finance-to-offer-tokenized-u-s-stocks-etfs-on-solana-early-next-year).

#### CEX stock-perp panel (BingX / Gate.io / HTX / Bitget / Phemex / MEXC)

Eleven CEXs list 24/7 (or 24/5) stock perpetuals on the xStock universe; the six in this section are the methodology-disclosure-present subset whose published index rules + observed behavior matter for §5.

**BingX** runs the largest book in the panel (~$252M / 24h, 57 stock-themed perps). Mark price = `Median(Price1, Price2, Last)`; index = 9-venue (Binance/OKX/Coinbase/Bitstamp/Bittrex/Gate/MEXC/Kraken/Bybit) 3% trim + re-equal-weighted. Critically, the **NCSK-prefix tickers are not Backed-issued** — BingX support copy describes NCSK as an "institutional liquidity provider," distinct from Backed.fi's xStocks. Only the 4 X-suffix tickers (AAPLX, NVDAX, METAX, PLTRX) are confirmable Backed-backed; the 53 NCSK tickers are an independent tokenized-equity surface that warrants its own scryer methodology row.

**Gate.io** is the most index-transparent venue in the panel. Closed, named constituent list (Gate, Binance, OKX, Bybit, Bitget, Coinbase, KuCoin, MEXC, Gate Alpha, PancakeSwap); outlier rule = clip to [0.2×, 1.8×] band around rebalance-time anchor (hard cap/floor, not deviation drop); 20-second stale-out → weight zero; daily 08:00 UTC rebalance. The `/futures/{settle}/index_constituents/{index}` REST endpoint is publicly queryable (no auth) but only returns membership, not weights. xStock perps cover GOOGLX, TSLAX, DFDVX, MSTRX, QQQX, SPYX, AMZNX, AAPLX, NVDAX, COINX, METAX, HOODX, CRCLX. 1-10× leverage. TSLAX spot ~$10-12M / 24h — material but small relative to crypto perps on the same venue.

**HTX** runs a thin xStock-backed comparator: TSLAX, MSTRX, AMZNX, COINX, PLTRX direct Backed-issued (X-suffix), plus 9 plain-tickered HTX-internal cash-settled synthetics. Total stock-perp aggregate ~$22M / 24h. Per-symbol index disclosure for X-suffix perps is not published; the `swap_premium_index_kline` endpoint returned 404 for TSLAX, suggesting premium-index telemetry is thinner for stock perps than for crypto perps. Useful as the "thin liquidity / opaque methodology" reference point.

**Bitget** carries a `isRwa: YES` flag on its 14 stock-themed perps (TSLA, AAPL, NVDA, SPY, QQQ, MSFT, AMZN, GOOGL, META, MSTR, COIN + leveraged-ETF TQQQ/SQQQ). Index methodology = "liquidity-and-volume-weighted composite of tokenized stock prices from multiple issuing platforms and exchanges." **Trading is 24/5 only** (Mon 04:00 → Sat 04:00 UTC+8); weekend mark frozen, funding suspended, liquidations halted. This contradicts the prior memo's "synthetic, no underlying token backing" framing — it is actually a hybrid: tokenized-stock-anchored basket with cash settlement and an explicit NYSE-calendar gate. The 24/5 freeze makes Bitget orthogonal to the §5 weekend-dispersion figure (no weekend mark exists to compare against), but with $128M / 24h in regular-hours volume it is the second-largest book in the panel.

**Phemex** is the worked-example value-add. Single Backed-token surface (SPYXUSDT) with material-but-tiny volume; the 13 synthetic siblings (TSLA, AAPL, NVDA, etc.) reference Phemex's published 6-venue index methodology: Binance/Coinbase/OKEx/Kraken/Bitfinex + Binance USDT/USD, **trim-mean of the middle 4, 15-second staleness rejection, min-3-source quorum**. **When quorum drops below 3, the index holds last** — itself a semi-public coverage-failure mode worth citing as a §1 worked example of formula-only off-hours behavior.

**MEXC** lists ~15 USDT-margined stock perpetuals at up to 25× leverage with funding currently waived (zero). Methodology is a generic weighted average of "major spot exchanges" with ±1% deviation drop and stale-feed exclusion; the constituent list is not publicly disclosed (only the BTC index discloses constituents). What sets MEXC apart in this panel is the upstream dependency on the **Ondo Global Markets** tokenized-stock spot index (per MEXC's own stock-futures landing copy) — a distinct hidden oracle layer separate from xStocks/Chainlink. Trading is 24/5 only (suspended weekends + US holidays).

**Cross-cutting:** None of the six venues publishes a confidence interval, spread guarantee, or statistical-coverage claim on its index price. Aggregate stock-perp 24h volume on just BingX + Bitget + HTX + Phemex = ~$407M, roughly 3-4 orders of magnitude above on-Solana xStock DEX flow. The §1.2 trust-gap framing — that traders won't put real size against a mark price they can't audit — has its strongest empirical backing in the absolute volume gap between these CEX surfaces and the on-chain xStock DEX surface that soothsayer prices natively.

#### Solana DEX-data aggregators (GeckoTerminal / Birdeye / CoinGecko)

All three publish DEX-pool spot mids for the full xStock universe; none publishes a confidence field, spread field, or TWAP at the public-price endpoint. **All three resolve to the same underlying signal** — the top Raydium-CLMM `xStock/USDC` pool mid, with Meteora DAMM-v2 / Orca Whirlpool / Pancakeswap-V3-Solana / Byreal as secondary — making them statistically near-identical sources.

- **GeckoTerminal** indexes 11+ xStock symbols live (AAPLx through CRCLx, plus a `xstocks/SOL` index pool on Meteora DAMM-v2). Headline `price_usd` is the spot mid in the **first pool of the `top_pools` array** (highest-liquidity pool, NOT volume-weighted, NOT TWAP). Schema: `{address, symbol, price_usd, fdv_usd, total_reserve_in_usd, volume_usd.{m5..h24}, market_cap_usd, top_pools[]}`. Free tier 30 calls/min, no key. **Hidden-oracle relevance: MEDIUM** — broad coverage, trivial access, but no on-chain consumer.
- **Birdeye** indexes all 8 Kamino-tier mints; `/defi/price` returns `{value, updateUnixTime, updateHumanTime, liquidity?}`; methodology not formally published; aggregates across "180+ DEXes" but doesn't document whether the headline price is highest-liquidity / volume-weighted / last-trade. **All tiers require an API key.** WebSocket on paid tiers. **Hidden-oracle relevance: MEDIUM** — highest-quality wallet-layer "shadow quote," but the API-key requirement makes it less of a path-of-least-resistance for an on-chain integrator vs GeckoTerminal/CoinGecko.
- **CoinGecko** has 178 records with `-xstock` ID suffix, of which **126 carry a Solana platform address** — broader than the live tradeable Backed roster (~74 active mints). `/simple/price` returns `{usd, usd_24h_vol, last_updated_at}`. Volume-weighted average across all venues (dominated by Solana DEX pools since CEXes don't list xStock SPL tickers). Demo tier 30/min, 10k/month, no key. **Hidden-oracle relevance: LOW** — same underlying signal as GeckoTerminal, ~60s polling cadence, useful as sanity-check tape.

**Crucially: no on-chain Solana DeFi protocol publicly names any of these aggregators as the xStock oracle source.** Kamino's xStocks Market consumes Chainlink Data Streams; Jupiter Lend runs its own multi-source oracle with freshness/confidence validation; Loopscale post-hack pipes through Pyth/Chainlink adapters. The shadow-oracle exposure for xStocks is via wallets / UIs / bots (Phantom, Backpack, trading bots) — not on-chain DeFi.

For §5 framing this is a **structural** finding: the "transparent calibration" gap our paper claims has no quantile/CI surface to read at the aggregator layer either.

### Updated cross-cutting findings (revisions to §"Cross-cutting findings relevant to §2.1")

1. **(Revised) The xStock pricing plane on Solana is Chainlink-dominant on-chain, but the upstream price layer bifurcates into four operational tiers**: Backed internal NAV (mint/redemption only) → CFB regulated indices (off-chain, FCA-supervised) ↔ Chainlink Data Streams (on-chain, sub-second) ↔ DEX-derived TWAPs (Solana, capturable from scryer not published as a feed). **Ondo Global Markets runs a parallel pipeline through MEXC** for a non-xStock tokenized-equity surface that is operational today, softening the original "single-vendor concentration" framing of §1.1.

2. **(Unchanged, reinforced) No surveyed oracle publishes a statistical-coverage claim on the served value.** The Tier D shadow-oracle research extends this finding to GeckoTerminal, Birdeye, and CoinGecko: none of the three publishes a confidence field, spread field, or TWAP at the public-price endpoint. The "transparent calibration" gap is structural across both oracle and aggregator layers.

3. **(Unchanged, but with new worked example) Off-hours methodology disclosure is qualitative across the board.** The most explicit *carry* rule remains Hyperliquid's 8-hour EWMA padding for Hyperps; the most explicit *bookend* remains the Chainlink v11 synthetic `.01`-suffix; the most explicit *forward-cursor* remains Pyth Pro's Blue Ocean session. **New worked example**: Phemex's published 6-venue trim-mean with "hold-last when quorum < 3" is a semi-public coverage-failure mode that should be cited in §1 — it is one of the rare cases where an incumbent's methodology explicitly admits the failure mode our paper measures.

4. **(Unchanged) The canonical Friday-4pm-to-Sunday-8pm xStock weekend remains uncovered by any incumbent's continuous-discovery feed.** Bitget's RWA-flagged 24/5 freeze (mark frozen, funding suspended, liquidations halted on weekends) is the latest empirical confirmation of this — the second-largest stock-perp book in the panel explicitly gives up the weekend window.

5. **(Unchanged) HIP-3 has spun out a new equity-oracle subcategory** — Pyth-HIP-3, RedStone HyperStone, and now SEDA Protocol's USA500 composite consumed by Hyperliquid + Injective + Dreamcash + Perps.Fun.

### Updated "Top surprises and gaps" (replaces §"Top 3 surprises…")

1. **CFB xStocks Indices launched 2026-05-07.** Regulated FCA-supervised PR + TR benchmarks for ~100 xStock symbols, powering Kraken xStock perpetual markets. Off-chain only. Missed by every prior xStock oracle survey. The strongest empirical anchor for the §5 thesis: Kraken now ships a *regulated benchmark* for the same symbols where Chainlink ships a *black-box Data Stream*, and **neither publishes a coverage-vs-width calibration curve.**

2. **SEDA Protocol (Flux's successor) ships a USA500 composite consumed by 4 perp venues.** Was hidden behind Flux's defunct branding; HIP-3-equivalent perp-oracle competitor with no published statistical-coverage claim. Should get its own §2.1 row.

3. **Ondo Global Markets is operational on MEXC today** — the original survey treated Ondo as "Q1-2026 Solana announcement" but the Ondo-tracked tokenized-stock spot index is already live and is the upstream reference for MEXC's stock perpetual `fairPrice`. Third operational tokenized-equity surface alongside xStocks and CEX-internal synthetics.

4. **RedStone has no public methodology page; the load-bearing disclosure is the node-manifest JSON in the monorepo.** Equity sources are 6 tier-2 redistributors (AllTick / Databento / FMP / Polygon.io / Twelve Data / DXfeed). No Bloomberg, Refinitiv, NYSE TAQ direct, or Nasdaq TotalView direct. Off-hours blending is **stepwise session-gated, not continuous** — happens at the *consumer* level, not the oracle level. **No xStock SPL feed in any RedStone manifest** — Solana RedStone publish path is RWA-only (BUIDL, ACRED, VBILL, SCOPE).

5. **The Pyth on-chain aggregator never produces `Halted`** — only `Unknown` when too few publishers are TRADING. `prev_*` fields preserve last-good across the outage. Pyth Pro / Lazer replaces the explicit enum with `marketSession` (`closed | preMarket | postMarket | regular`) + carry-forward stamps + sometimes simply omits `price`. Blue Ocean → pre-market 4am ET handover behavior is documented nowhere. Our `pyth/oracle_tape` schema does not capture `status` or `prev_*` — a scryer schema bump (`pyth_status`, `pyth_prev_price`, `pyth_prev_publish_time`) is the cleanest path to resolve "Unknown freeze" vs "Trading on stale publishers" empirically.

6. **Chainlink's per-feed `tokenizedPrice` venue list is unrecoverable from public sources.** Disclosure is asset-class-only ("aggregated across CEXs"); v11 `mid` = "liquidity-weighted", `bid`/`ask` = "median". The strongest circumstantial inference is the xStocks Alliance member exchanges (Kraken, Bybit, Bitget, Gate). The NVDAX-REAL-vs-others-synthetic v11 weekend pattern documented in §6.7.2 is consistent with per-symbol wiring differences. **For the audit-gap table, this must be reverse-engineered empirically** — regress `cl_tokenized_px` on minute-aligned alliance-CEX mids.

7. **Edge (Chaos Labs) has no equities path and no confidence field.** Schema = `{price: i64, expo: i32, timestamp: i64}` via Dove wrapper accounts. Only 5 crypto pairs (SOL / ETH / BTC / USDC / USDT). Methodology disclosure is genuinely thin — even press-release mirrors of the 404'd intro post are positioning-only. Jupiter wraps Edge in a 2-of-3 fallback with Pyth + Chainlink. For §2.1, classify as "high-throughput crypto-only feed, calibration-opaque" — *not* a competitor in the xStock plane today.

8. **Stork's 8-asset 24/7 RWA launch was announced 2026-05-13.** TSLA / CRCL / NVDA / MSTR + gold / silver / WTI / Brent, on EVM-perp-DEX deployers (Lighter, Ostium, Paradex, etc.). Solana surface is dormant since 2025-09-25; equity feeds only on RISE testnet on the Solana side.

### Updated audit-gap table

Filling in the TBD rows in §"What this enables for §2.1":

| Provider | Methodology claim (docs) | Observed behaviour (scryer / live probe) | Audit gap |
|---|---|---|---|
| Chainlink v11 weekend bid | "extended-hours quote" | 100% incidence of `.01`-suffix synthetic bookend on SPYx/QQQx/TSLAx | Synthetic, not extended-hours |
| Chainlink v10 `tokenizedPrice` | "Aggregated price across centralized exchanges where the tokenized asset trades" | `tokenizedPrice` continues 24/7 but per-symbol venue list, weights, and outlier rule undisclosed | **Provenance unverifiable from public sources** — must reverse-engineer via regression vs xStocks Alliance CEX mids |
| Edge / Jupiter Perps oracle | "high-throughput integrity-and-latency oracle, sub-200ms p99" | 5 crypto pairs on Solana via Dove wrapper; **schema has no confidence field** | No equity surface; not directly comparable to xStock pricing plane |
| RedStone Live | "blends institutional + perp data" | Step-gated by session-enum providers; consumer-side regime selection (no continuous blend); 6 tier-2 redistributors, no Bloomberg/Refinitiv | Marketing language overstates the smoothness; the actual blend is two parallel feeds the consumer chooses between |
| Stork equity-perp | "real-time 24/5"; full RWA framework documented in `24-7-price-feeds.md` | Solana surface dormant since 2025-09-25; equity `_24_5` feeds only on RISE testnet; mainnet equity-perp consumers are EVM L2/zk only | **Solana zero, EVM real**; per-asset publisher identities/weights/parameters not published (τ/W/C/N) |
| Pyth Pro overnight (Blue Ocean) | "8pm-4am ET Sun-Thu executable book" | Verifiable against scryer `bo_intraday_1m.v1` | Likely matches claim; **weekend remains uncovered** and **4am ET handover behavior undocumented** |
| Pyth core aggregate | `status` enum is `trading \| halted \| unknown`; ~95% publisher-level coverage recommended in `pyth-conf` primer | Aggregator never produces `Halted` (publisher-only value); `Unknown` + `prev_*` last-good when quorum drops; aggregate-level coverage never claimed | Wide implicit gap between publisher-level conf semantics and aggregate-level halt semantics; resolvable with scryer schema bump (`pyth_status`, `pyth_prev_*`) |
| Switchboard | Aggregator reducer (median/mean/etc.) per-feed configurable | **Zero deployed equity feeds**; AAPL appears only in Polygon.io tutorial; MarginFi uses Switchboard as static stub | Equity-capable in principle, ships none; downgrade to one-line dismissal in §2.1 |
| Chronicle equities | "verifiable signer-set + reserve attestation" | Only **SPY/USD** confirmed live on Chronicle dashboard; EVM-only; no Solana | Methodology-light; PoA layer is structurally separate from price feed; no off-hours/halt policy |
| BingX stock-perps | `Median(Price1, Price2, Last)`; 9-venue 3% trim index | NCSK-prefix (53 of 57 symbols) is **not Backed-issued** ("institutional liquidity provider"); 4 X-suffix tickers are Backed-direct | Largest panel volume (~$252M / 24h) but methodology of NCSK source not disclosed |
| Gate.io stock-perps | Closed-list weighted avg; clip-band [0.2×, 1.8×]; 20s stale; daily 08:00 UTC rebalance | Public `/index_constituents/{index}` endpoint returns membership only (no weights) | **Most index-transparent CEX in panel**; weights are the unfilled gap |
| HTX stock-perps | TSLAX/MSTRX/AMZNX/COINX/PLTRX = direct Backed-xStocks | Per-symbol index disclosure absent; X-suffix `swap_premium_index_kline` returned 404 | Premium-index telemetry thinner for stock perps than crypto |
| Bitget stock-perps | Liquidity-and-volume-weighted composite; `isRwa: YES` flag | **24/5 only** (weekend mark frozen, funding suspended, liquidations halted); $128M / 24h regular-hours volume | RWA-flagged hybrid; explicit weekend gate is itself a §5 worked example |
| Phemex stock-perps | 6-venue trim-mean of middle 4; 15s staleness; **min-3 quorum or hold-last** | Documented behavior; one Backed-xStock (SPYXUSDT) | "Hold-last on quorum failure" is a published coverage-failure mode |
| MEXC stock-perps | Weighted avg of "major spot exchanges"; ±1% deviation drop; stale-feed exclusion | **References Ondo Global Markets tokenized-stock spot index upstream**; constituent list undisclosed | Third hidden oracle layer (Ondo) introduced into the perp's price formation |
| GeckoTerminal | "spot mid-price in the first pool of the `top_pools` array" | Live xStock coverage 11+ symbols; raw spot mid, no TWAP | No confidence/spread field; same underlying signal as Birdeye/CoinGecko |
| Birdeye | "aggregate across 180+ DEXes" (methodology not formally published) | All 8 Kamino-tier mints indexed; API-key gated | No confidence/spread field; not the path-of-least-resistance for an on-chain consumer |
| CoinGecko | Volume-weighted average across all tickers | 178 `-xstock` records, 126 on Solana (broader than live tradeable roster) | ~60s cadence; same underlying signal; sanity-check tape only |
| CFB xStocks Indices | Regulated FCA-supervised PR + TR benchmark; "Token Market Price Benchmarks Series" Methodology Guide + Benchmark Statement | Off-chain REST/WebSocket only; "powers Kraken xStocks perp markets" | Regulated does not imply calibration-disclosed; coverage-vs-width curve not published |
| SEDA USA500 composite | "60% equities + 25% crypto + 15% commodities" | Consumed by Hyperliquid + Injective + Dreamcash + Perps.Fun in production | Composite weights documented; per-name component methodology not |
| DIA Lumina + xReal | "every input source, weight, and aggregation step published on Lasernet" | 6+ deployed equity tickers (ADBE/META/NFLX/MSTR/MA/HOOD) on Arbitrum/Optimism/Base/Sonic; SPY/TSLA/AAPL not deployed; **zero Solana presence** | Methodology disclosure is real but ≠ coverage claim — single point estimate from Aggregator median, no confidence interval, no calibration evidence |

### Closed research candidates (status update for §"Candidates for next-pass investigation")

**G1-G7 methodology gaps** — all closed:
- **G1 Edge (Chaos Labs)** — closed 2026-05-11. No equities path; no confidence field; 5 crypto pairs only via Dove wrapper. Disclosure thin (not for lack of searching).
- **G2 Stork** — closed 2026-05-13. Methodology IS published in `24-7-price-feeds.md`; Solana surface dormant since 2025-09-25; equity feeds only on RISE testnet.
- **G3 RedStone Live methodology** — closed 2026-05-13. The 404'd page doesn't exist; methodology is the node-manifest JSON in the monorepo; 6 tier-2 redistributors; off-hours stepwise-gated.
- **G4 Chronicle equities** — closed 2026-05-11. Equity launch 2025-07-28; only SPY/USD live on dashboard; EVM-only.
- **G5 Switchboard equity aggregation** — closed 2026-05-13. Zero deployed equity feeds; downgrade to one-line dismissal.
- **G6 Chainlink v10/v11 `tokenizedPrice` provenance** — closed 2026-05-11 with the verdict that public disclosure is asset-class-only; **must reverse-engineer empirically**.
- **G7 Pyth aggregate vs publisher behavior outside session** — closed 2026-05-11. Aggregator never emits `Halted`; cleanest empirical distinction needs scryer schema bump.

**Tier A net-new providers** — all closed; net result = 0 new full rows from Tier A (Band, Pragma, Acurast, Ojo, Witnet, Razor, Nest, Flux, Chainlink-Functions all refuted; TruFlation + Umbrella one-line mentions only; DIA reframed; "Smart Data Streams" footnote-only). **One unanticipated finding from the P3 sweep: SEDA Protocol** (Flux's successor) is a real, live equity-composite oracle and warrants its own row.

**Tier D shadow oracles** — all closed. Net result = 1 new full row (CFB), 6 CEX-stock-perp rows for §5 panel block, 3 aggregator entries (GeckoTerminal/Birdeye/CoinGecko) classed as wallet-layer shadow quotes with no on-chain DeFi consumer.

**Open candidates — Tier B (NAV publishers) and Tier C (upstream comparators)** still pending. Tier B is the highest remaining leverage for §1.1 systemic-concentration framing — confirms which RWA NAV publishers (BUIDL, OUSG, USYC, Securitize STAC, Backed reference NAV) actually publish on-chain reference vs. off-chain NAV only.

### Empirical follow-up work emergent from this research

1. **Reverse-engineer Chainlink `tokenizedPrice` venues by regression.** Per-feed venue list is unrecoverable from public sources. Regress minute-aligned `cl_tokenized_px` from `chainlink/data_streams` parquet against minute-aligned mids from xStocks Alliance CEXs (Kraken, Bybit, Bitget, Gate). Per-symbol regression coefficients reveal the implicit weight set; residual analysis reveals the outlier-rejection rule. The NVDAX-REAL-vs-others-synthetic v11 weekend pattern (§6.7.2) is the strongest indicator that per-symbol wiring differs.

2. **Scryer schema bump request: `pyth_status`, `pyth_prev_price`, `pyth_prev_publish_time`.** Cleanest path to distinguish "aggregator returned `Unknown` and froze at last-good" from "aggregator kept emitting `Trading` on stale publisher quotes." Would let §6 make a precise empirical statement about Pyth halt behavior. Filed as a future scryer wishlist row; can also be inferred indirectly from `pyth_age_s` jumps relative to slot cadence.

3. **§1.1 systemic-concentration framing softening.** Original claim: "Backed (xStocks) and Ondo concentrate equity pricing on Solana into one provider (Chainlink)." Revised: "Two parallel pipelines exist — Backed → Chainlink + CFB Indices on Solana, and Ondo → MEXC spot + perps off-chain (with announced 2026 Solana SPL launch)." Under SR 11-7 / SR 26-2 this is still a concentration concern but the dominant-vendor failure mode has at least one parallel pathway around it.

4. **CEX stock-perp panel as §5 evidence block.** With BingX + Bitget + HTX + Phemex aggregating to ~$407M / 24h, the panel is materially larger than originally framed (the original memory cited TSLAX ≈ $2.6k / 24h on Kraken Futures, which was a single-venue snapshot of one Backed-direct ticker). The aggregate volume gap between CEX stock-perp surfaces (~$407M+) and the on-Solana xStock DEX surface that soothsayer prices natively (~$8M / 24h aggregate per the 74-pool inventory) is 2 orders of magnitude — the strongest empirical anchor for §1.2's trust-gap framing.

5. **NCSK methodology brief** (BingX's 53-perp non-Backed tokenized-equity surface). NCSK is described as an "institutional liquidity provider" but methodology, custody, and proof-of-reserve are not publicly disclosed. Worth a dedicated research-agent pass and a scryer methodology row before treating NCSK-prefix tickers as xStock-class for dispersion analysis.
