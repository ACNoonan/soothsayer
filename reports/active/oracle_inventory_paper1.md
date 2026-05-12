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
| **Chainlink Data Streams v10** ("Tokenized Asset") | Solana, EVM | Ticker last-trade + 24/7 CEX-aggregated `tokenizedPrice`; `marketStatus` enum (3-state) | xStocks: AAPLX, TSLAX, NVDAX, METAX, GOOGLX, MSTRX, SPYX, QQQX (60+) | `price` stale during weekends; `tokenizedPrice` continues from CEX activity | None on wire — no bid/ask/conf | Schema-doc + RWA-Alliance blog; no calibration claim | Kamino lending (xStocks market), Backed xBridge | **Yes** — `chainlink/data_streams` |
| **Chainlink Data Streams v11** ("RWA Advanced") | Solana, EVM | `price`, `bid`, `ask`, `mid`, `last_traded_price`, `bid_volume`, `ask_volume`; 6-state `marketStatus` | Same xStocks set as v10; co-existing | Synthetic `.01`-suffix `bid` on weekends/closed (paper §6.7.2) | Bid/ask spread, but synthetic on weekends | Schema doc; weekend marker behavior undocumented externally | Same as v10 — co-deployed | **Yes** — `chainlink/data_streams` |
| **Chainlink Data Feeds (push)** | EVM (Ethereum, Base, Arbitrum, etc.) | Equity ticker prices via aggregator contracts; corp actions | SPY, AAPL, TSLA, NVDA, etc. | Stale-hold (last on-chain answer until heartbeat) | None on wire | Aggregator design (DON whitepaper); per-feed deviation/heartbeat only | N/A on Solana | No |
| **Pyth Network (core)** | Solana + 100+ chains via Wormhole | First-party publisher (price, conf) for equity tickers and ETFs; ~380 feeds across all asset classes | `Equity.US.SPY/USD`, AAPL, TSLA, NVDA, MSFT, GOOGL, QQQ, ... | Status enum (`trading`, `halted`, `unknown`); aggregate freezes outside session | Aggregate conf interval (max distance from median to 25th/75th vote-percentile); diagnostic, not coverage claim | `[pyth-agg]` + `[pyth-conf]` blog posts; methodology described but no aggregate-level coverage claim | Drift Protocol (primary), MarginFi, Jupiter (until 2025), Kamino (in transition) | **Yes** — `pyth/oracle_tape` |
| **Pyth Pro** (formerly Pyth Lazer) | Solana + EVM | Lower-latency (~1ms) institutional-grade publisher feeds; subscriber-customizable cadence; **exclusive Blue Ocean ATS overnight equity data through end-2026** | Same publisher set + Blue Ocean equity book during 8pm–4am ET Sun–Thu | Blue Ocean book during overnight session (Sun–Thu 8pm–4am ET); **canonical Fri 4pm – Sun 8pm weekend window still uncovered**; standard Pyth status otherwise | Same publisher conf-interval semantics; no aggregate-level coverage claim | `[pyth-pro]` docs; `[blueocean-pyth]` integration blog | HIP-3-as-a-Service for Hyperliquid stock perps; Solana DeFi via MagicBlock | **Yes** — `oracle.pyth_lazer/tape` |
| **RedStone Classic (push)** | EVM-first; Solana since May 2025 (RWA oracle) | Pull-/push-modular feeds across crypto, RWA, tokenized funds; equity feeds for select tickers | Tokenized funds (BUIDL, ACRED) + equity tickers per partner request; xStock symbols (TSLAx, AAPLx etc.) discussed but not all live on-chain | Documented qualitatively — "blends institutional feeds with perpetual-market data during off-hours" | None on wire by default; per-feed customizable | Blog post `[redstone-live]`; specific weights/venues/consensus rule not published; deep methodology page 404 | Securitize tokenized funds (ACRED, BUIDL on Solana); Drift, MarginFi for crypto | **Yes** — `redstone/oracle_tape` |
| **RedStone Live** (forward-cursor gateway, public) | Off-chain REST | Public REST gateway `api.redstone.finance/prices`; 30-day cap; point-only schema | SPY, QQQ, MSTR (verified via memory); no xStock SPL mints; no equity feeds on-chain Solana | Continuous time-series but no off-hours semantics declared at the point | None (point-only) | Gateway docs minimal | None on Solana | **Yes** — `redstone/oracle_tape` |
| **HyperStone** (RedStone, Hyperliquid-only) | Hyperliquid (HIP-3) | Push-based oracle purpose-built for HIP-3 builder-deployed perps; equity perp marks at 3ms cadence | TSLA (first live HIP-3 market, via Felix), expandable to any RWA | Continuous, 24/7 driven by perp orderflow; off-hours behavior governed by deployer | None published | Blog announcement; no detailed methodology paper | None — Hyperliquid only | No |
| **Switchboard** (V3 / On-Demand / Surge) | Solana + EVM (Surge) | Permissionless TEE-attested oracle queues; subscriber-customizable; equity feeds via jobs | Subscriber-defined; SPY/QQQ available via Surge if customer requests | Stale-hold or job-defined; no built-in market-hours logic | Aggregator reducer (median, mean, etc.) — no published coverage claim | `[switchboard]` docs | MarginFi (some feeds), older Solana DeFi; not the canonical xStock oracle | No |
| **DIA / DIA Lumina** | Ethereum L2 (Lasernet) + Solana + 80+ chains | Open, transparent feeds for 3000+ assets; "Real World Asset Price Feeds" advertised | Tokenized RWAs and equity reference prices; symbol list not publicly enumerated for equities | Not documented externally for equities | Median + per-source disclosure on Lumina (transparent methodology) | Lumina launch posts; strongest "open methodology" claim in market | None known for tokenized equities on Solana | No |
| **API3 (dAPIs + OEV)** | 40+ EVM chains | First-party data via Airnode operators; 200+ feeds; OEV auctions return rebate to dApp | Crypto-heavy; some equity dAPIs available on dAPI-docs; coverage shallow vs Pyth/Chainlink | Stale-hold unless searcher updates via OEV auction | OEV auction is integrity-economic, not statistical-coverage | dAPI docs; OEV design papers | None on Solana | No |
| **Supra Oracles** | Supra L1 + 80+ networks (no native Solana) | DORA v2 expanded RWA coverage (FX, equities, commodities); 600–900ms finality | Equities advertised under "RWA expansion"; symbol list shallow | Not documented; behaves as the publisher set behaves | None published as a calibration statement | Blog + product pages | None on Solana | No |
| **Stork Network** | Solana + 70+ chains | Low-latency oracle for perp DEXes; "leading oracle powering equity perpetuals markets"; reference-price input for tokenization platforms | 500+ assets across all classes; equity coverage advertised but no public symbol enumeration for SPL mints | Stated as enabling "24/5 leveraged exposure to US stocks" — confirms equity ticker coverage; weekend handling not documented | None published on the wire | Marketing site only; no methodology paper | None publicly verified on Solana for equities | No |
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

### Chainlink — three coexisting surfaces, one xStock plane

Three Chainlink surfaces are simultaneously live in 2026. **Data Feeds (push)** is the legacy EVM-aggregator model — heartbeat-and-deviation triggered updates of a single mark price into an aggregator contract on Ethereum or an L2. It has no Solana presence for equities. **Data Streams v10 ("Tokenized Asset", schema id `0x000a`, 13 fields, 416 bytes)** is the load-bearing wire format that backs xStocks on Solana from launch (June 2025): a `price` field that goes stale on weekends, a `tokenizedPrice` field that continues updating from a 24/7 CEX-aggregated mark, a 3-state `marketStatus` enum (`Unknown` / `Closed` / `Open`), and corporate-action multipliers. It carries **no bid, ask, or confidence on the wire** — a v10 consumer reading directly derives a degenerate zero-width band. **Data Streams v11 ("RWA Advanced", schema id `0x000b`, 14 fields, 448 bytes)** is the 2026 extension co-existing with v10: adds `bid`/`ask`/`mid`/`last_traded_price`/`bid_volume`/`ask_volume` and a 6-state `marketStatus` distinguishing pre-market / regular / post-market / overnight / closed / weekend. The paper §6.7.2 documents that the v11 weekend `bid` carries a synthetic `.01`-suffix marker on three of four mapped xStocks at 100% incidence — a categorical bookend, not a continuous band.

Chainlink is the **official oracle of the xStocks Alliance** (announced 2025-06-30; Backed/Kraken acquisition of xStocks completed late 2025) and powers Kamino's xStocks lending market, MetaMask earn-on-equities integrations, and the Backed↔Solana xBridge (announced 2025-12-12). Ondo also publicly chose Chainlink as the oracle plane for its early-2026 Solana tokenized-stock rollout. None of the three Chainlink surfaces publishes a calibration claim on the served value.

Sources: [chainlink-streams](https://docs.chain.link/data-streams), [v10 schema](https://docs.chain.link/data-streams/reference/report-schema-v10), [v11 schema](https://docs.chain.link/data-streams/reference/report-schema-v11), [xStocks Alliance announcement](https://x.com/chainlink/status/1939763692301922621), [xBridge announcement](https://www.coindesk.com/web3/2025/12/12/backed-chainlink-launch-xbridge-to-move-tokenized-stocks-between-solana-and-ethereum), [Ondo+Chainlink](https://ondo.finance/blog/defi-adoption-of-ondo-tokenized-stocks-live).

### Pyth Network — core, Pro, and the Blue Ocean exclusivity

Pyth's core Solana surface is the canonical first-party-publisher oracle in DeFi: ~120 permissioned publishers submit `(price, confidence)` reports; the on-chain aggregator takes the median over the three votes each publisher contributes (`price`, `price + conf`, `price - conf`), and the published aggregate confidence is the max distance from the median to the 25th/75th percentile votes. Pyth's documentation [`pyth-conf`] explicitly recommends that each publisher calibrate to ~95% coverage at the publisher level, but **no aggregate-level coverage claim is published** — and the aggregate's behavior outside the calibrated range is undefined. The aggregate has a `status` enum (`trading`, `halted`, `unknown`) but no continuous market-status disclosure.

**Pyth Pro** (rebranded from Pyth Lazer, the rebrand confirmed via CO-PIP-5 passing on Solana mainnet in 2025-Q3) is the institutional tier: single-millisecond latency, ~400× faster than core Pyth, subscriber-customizable cadence, ~28 active subscribers as of Q3 2025. **The economically load-bearing differentiator for equities** is Pyth's exclusive on-chain distribution of the **Blue Ocean ATS** overnight executable book through end-2026: 8pm–4am ET Sunday-through-Thursday, ~$1B nightly volume across ~5,000 NMS symbols. This is the closest published incumbent to a true 24/5 equity feed — but the canonical xStock **weekend** (Friday 4pm ET through Sunday 8pm ET) remains uncovered by Blue Ocean's session and therefore by Pyth Pro.

Pyth additionally offers **HIP-3-as-a-Service** for Hyperliquid builder-deployed perps, providing the price relay for stock perpetuals there. On Solana DeFi the main consumers are Drift (primary), MarginFi, and (historically) Jupiter — Jupiter's perps have since migrated to Edge (Chaos Labs) as their primary oracle.

Sources: [Pyth aggregation proposal](https://www.pyth.network/blog/pyth-price-aggregation-proposal), [Pyth confidence primer](https://www.pyth.network/blog/pyth-primer-dont-be-pretty-confident-be-pyth-confident), [Pyth Pro docs](https://docs.pyth.network/lazer), [Blue Ocean+Pyth](https://www.pyth.network/blog/blue-ocean-ats-joins-pyth-network-institutional-overnight-hours-us-equity-data), [Pyth Lazer Solana mainnet](https://forum.pyth.network/t/passed-co-pip-5-release-pyth-lazer-on-solana-mainnet/1881), [HIP-3-as-a-Service](https://docs.pyth.network/price-feeds/hip-3-service), [Magicblock+Lazer](https://www.pyth.network/blog/magicblock-and-lazer-powering-a-new-wave-of-speed-for-solana-defi).

### RedStone — Classic, Live, RWA-Solana, and HyperStone

RedStone is unusual in operating four distinct equity-relevant surfaces. **RedStone Classic** is the pull-/push-modular EVM-first oracle, integrated by Drift, MarginFi, and other Solana protocols for crypto pricing. **RedStone Live** (March 2026 launch, blog `[redstone-live]`) is a 24/7 equity feed product blending institutional feeds during US hours with perpetual-market data during off-hours; methodology described qualitatively but contributing-venue list, weights, consensus rule, and any confidence statement are **not published in reproducible form**. The deep methodology page that the launch post linked to returns 404. The public gateway `api.redstone.finance/prices` has a 30-day cap, point-only schema, no CI, and serves SPY/QQQ/MSTR but **no SPL xStock mints and no equity feeds on Solana on-chain**.

**RedStone RWA-Solana** (May 2025 launch, partner: Securitize) brings tokenized-fund price feeds to Solana via Wormhole Queries — primary live assets are Apollo's ACRED and BlackRock's BUIDL, not xStocks. **HyperStone** (November 2025) is a Hyperliquid-only push-based oracle purpose-built for HIP-3 builder-deployed perps at 3ms cadence — first live HIP-3 market was Felix's TSLA perp; HyperStone has since powered ~$1.5B in cumulative HIP-3 volume across 12 markets. None of the four surfaces publishes a statistical coverage claim.

Sources: [RedStone Live](https://blog.redstone.finance/2026/03/30/redstone-live-real-time-data-built-for-the-markets-that-never-sleep/), [RedStone RWA Solana](https://blog.redstone.finance/2025/05/28/redstone-rwa-oracle-brings-tokenized-assets-to-solana-ecosystem/), [HyperStone launch](https://www.theblock.co/post/377776/redstone-launches-hyperstone-oracle-to-power-permissionless-markets-on-hyperliquid), [Felix HIP-3 TSLA](https://blog.redstone.finance/2025/11/13/felix-launches-its-first-hyperliquid-hip-3-market-with-tsla-powered-by-hyperstone/).

### Switchboard — under-deployed for equities

Switchboard V3 / On-Demand is the third major Solana oracle, but its deployed surface area for tokenized equities is shallow: no headline xStock integration, no public symbol list for equity feeds, and its model — permissionless TEE-attested queues with subscriber-defined job graphs — leaves market-hours/off-hours handling to the integrator. Switchboard Surge (low-latency variant) is positioned for sub-second crypto pricing rather than for the equity microstructure problem. Aggregation is via configurable reducers (median, mean, etc.); the aggregate is silent on realised coverage against a reference $P_t$ distribution. MarginFi historically consumed some Switchboard feeds for niche assets but has migrated most crypto pricing to Pyth.

Sources: [Switchboard docs](https://docs.switchboard.xyz/docs/switchboard/readme/designing-feeds/oracle-aggregator), [On-Demand GitHub](https://github.com/switchboard-xyz/on-demand), [Switchboard ecosystem](https://solanacompass.com/projects/switchboard).

### DIA / DIA Lumina — strong methodology disclosure, weak equity deployment

DIA Lumina (2024+) is structurally the most transparent oracle stack — every input source, weight, and aggregation step is published, settled on Lasernet (DIA's Ethereum L2 rollup), and re-derivable. DIA advertises Real-World-Asset price feeds across 3000+ assets including equities, but the public symbol list for equities is not enumerated and no Solana xStock-mint feed appears in known integrations. The "open methodology" claim is the strongest in the market but the equity-specific deployment is essentially zero on Solana. Useful as a reference point in the paper: "fully transparent methodology" exists in the design space, but is not the deployed equity-pricing layer.

Sources: [DIA Lumina](https://www.diadata.org/lumina/), [DIA Solana oracles](https://www.diadata.org/solana-price-oracles/).

### Chronicle Protocol — RWA-oriented, MakerDAO-derived, EVM-only

Chronicle (the spinout of MakerDAO's Oracle Core Unit) has secured $10B+ in collateral since 2016 and announced "Onchain Equities Price Feeds" (date: 2024–2025) targeting RWA protocols. In 2026 the deployed surface accelerated via Centrifuge selecting Chronicle as primary RWA oracle and Securitize integrating Chronicle's Proof-of-Asset layer for STAC and BUIDL transparency. **All EVM** — no Solana deployment for tokenized equities as of May 2026. Chronicle's "transparency" pitch is anchored on the verifiable signer set and reserve attestation, not on a statistical-coverage claim on the served price.

Sources: [Chronicle equities launch](https://chroniclelabs.org/blog/chronicle-launches-onchain-equities-price-feeds), [Centrifuge partner](https://www.morningstar.com/news/business-wire/20260108358859/centrifuge-selects-chronicle-as-primary-oracle-partner-for-tokenized-assets).

### Hyperliquid native + HIP-3 deployer ecosystem

Hyperliquid's native oracle is a validator-weighted median of CEX mid prices (Binance 3, OKX 2, Bybit 2, Kraken 1, KuCoin 1, Gate 1, MEXC 1, Hyperliquid 1) — applied to crypto spot only. **Hyperps** (pre-launch perpetuals) use an 8-hour exponentially-weighted moving average of the last day's minutely mark prices, with a 4× one-month-average cap as a manipulation safeguard; this is the most explicit *carry* methodology any of the surveyed oracles publishes. **HIP-3** (October 2025 mainnet) is the open-permissionless model where the deployer chooses the oracle for their market — primary deployer-oracle competitors are Pyth (HIP-3-as-a-Service) and RedStone (HyperStone). The first live HIP-3 stock market was Felix's TSLA, powered by HyperStone, going live 2025-11-05.

Sources: [Hyperliquid oracle](https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle), [Hyperps](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/hyperps), [HIP-3](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals).

### Edge (Chaos Labs) — Jupiter's primary, no equity yet

Edge is Chaos Labs' "next-generation" oracle that ships risk-management functions co-mingled with price reporting. It is **Jupiter Perps' primary oracle** as of mid-2025, securing >$30B in cumulative transaction volume and "90%+ of Solana's total daily perpetual futures volume" per Jupiter's own statement. Edge is not currently the canonical xStock equity oracle — Jupiter perps are crypto-only. Useful as a reference point for "risk-aware oracle" as a design direction, but its public methodology disclosure is a single blog post and detailed coverage claims are not externally peer-reviewed (the linked Chaos Labs page returns 404 as of this writing, suggesting in-progress rewrites). Worth following for Solana-side competitive pressure if Jupiter extends to equity perps.

Sources: [Edge intro](https://chaoslabs.xyz/posts/introducing-edge-the-next-generation-oracle) (404 as of 2026-05-11; cached references via [Jupiter Solana DeFi report](https://eco.com/support/en/articles/14801178-solana-defi-stack-routers-lending-perps)).

### Kamino Scope — aggregator over upstream oracles, not an originating oracle

Scope is **explicitly an aggregation layer**, not a price-discovery primitive. It reads from Pyth, Switchboard, Chainlink, and custom on-chain sources, validates the prices against pre-set rules (deviation bounds, staleness checks, etc.), and writes a single PDA per asset that Kamino lending consumes. Scope is triple-audited and secures $4B+ of Kamino deposits. **Critical for paper §2.1 framing:** Scope is downstream of the providers we survey; it amplifies whatever calibration property the upstream provider has (zero, in every case) and additionally publishes its rule-based gating logic openly. Classify as "router/aggregator" rather than "oracle" — we discuss it because it is the **dominant Solana consumer** of xStock oracle data.

Sources: [Scope GitHub](https://github.com/Kamino-Finance/scope), [Scope SDK](https://github.com/Kamino-Finance/scope-sdk).

### Backed Finance / Ondo — issuers, not pricing layers

A frequent point of confusion: **Backed Finance** (xStocks issuer; acquired by Kraken late 2025) and **Ondo Finance** (preparing 2026-Q1 Solana tokenized-stock launch) are token issuers, not oracles. Both delegate on-chain pricing to Chainlink (and, in Backed's case, also to Pyth via xStocks Alliance partner relationships). Each maintains an off-chain reference NAV used for mint/redemption — but **neither publishes that NAV as an on-chain reference price feed**. The on-chain xStock price plane *is* Chainlink Data Streams v10/v11. We surface this here because §2.1 readers may otherwise assume Backed is publishing a price oracle; they are not.

Sources: [xStocks launch](https://www.prnewswire.co.uk/news-releases/backeds-xstocks-go-live-today-on-bybit-kraken-and-solana-defi-302494379.html), [Kraken acquires Backed](https://blog.kraken.com/news/backed-acquisition), [Ondo+Chainlink](https://ondo.finance/blog/defi-adoption-of-ondo-tokenized-stocks-live), [Ondo Solana plan](https://www.coindesk.com/business/2025/12/15/ondo-finance-to-offer-tokenized-u-s-stocks-etfs-on-solana-early-next-year).

### Stork Network — equity-perp ambient but symbol opacity

Stork claims to be "the leading oracle powering equity perpetuals markets" and "enabling venues to offer 24/5 leveraged exposure to US stocks." Its self-disclosure is marketing-grade — no public symbol list, no methodology paper, no statistical-coverage claim. Stork covers 500+ assets across 70+ chains including Solana, but the equity-specific deployment surface on Solana is not publicly enumerated. Plausibly powers some HIP-3 deployers' equity perps; not currently a verifiable feed in the xStock pricing plane.

Sources: [Stork](https://www.stork.network/), [docs](https://docs.stork.network/).

### Other surveyed providers — sub-paragraph notes

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

1. **The xStock pricing plane on Solana is Chainlink-dominant.** Of the major oracles we surveyed, only Chainlink Data Streams v10/v11 publishes a verifiable xStock-mint-keyed feed at scale; Pyth publishes the *underlying ticker* (`Equity.US.SPY/USD`) but the SPL-mint feeds are not its surface; RedStone Live publishes SPY/QQQ tickers off-chain only; everyone else is either RWA-but-not-equity (Chronicle on EVM) or equity-but-not-Solana (eOracle, Supra) or perp-only (HyperStone, Edge).

2. **No surveyed oracle publishes a statistical-coverage claim on the served value.** Every uncertainty field that exists on-the-wire is either a publisher-dispersion diagnostic (Pyth aggregate conf), a synthetic bookend (Chainlink v11 weekend bid `.01`-suffix), a venue-spread (Chainlink v11 bid/ask during open hours), or absent (v10, RedStone Live, Stork, Switchboard, DIA equity feeds, Edge, HyperStone). The paper's "calibration primitive is orthogonal to the deployed integrity primitive" framing is empirically tight.

3. **Off-hours methodology disclosure is qualitative across the board.** The most explicit *carry* rule in our survey is Hyperliquid's 8-hour EWMA padding for Hyperps; the most explicit *bookend* is the Chainlink v11 synthetic `.01`-suffix; the most explicit *forward-cursor* is Pyth Pro's Blue Ocean session (8pm-4am ET Sun-Thu). None of these are framed as a probability-of-coverage statement on the served value.

4. **The canonical Friday-4pm-to-Sunday-8pm xStock weekend remains uncovered by any incumbent's continuous-discovery feed.** Pyth Pro/Blue Ocean covers Sun-Thu nights only; Chainlink v10 goes stale Friday close; v11 emits the synthetic-marker pattern; RedStone Live blends qualitatively. This is the paper's load-bearing empirical claim and the survey corroborates it.

5. **HIP-3 has spun out a new equity-oracle subcategory** (Pyth-HIP-3, HyperStone, Edge-like Chaos Labs work) where the deployer chooses the oracle and the underlying perpetual orderbook is the off-hours price-discovery mechanism. This is structurally a different problem from the xStock-on-Solana problem: the perp deployer controls the contract and the oracle simultaneously, so calibration disclosure has a different vendor incentive structure.

---

## References

| # | Citation | URL | Verified |
|---|---|---|---|
| 1 | Chainlink Data Streams overview | https://docs.chain.link/data-streams | Yes |
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

---

## Top 3 surprises and "we should know more about this" gaps

1. **Edge (Chaos Labs) has displaced Pyth as Jupiter Perps' primary oracle.** This is a major Solana-DeFi shift not currently reflected in §2.1, and the public methodology disclosure is a single blog post (currently 404'd) — i.e. *less* transparent than Pyth's pyth-conf primer despite handling 90%+ of Solana perp volume. Worth a dedicated paragraph in the rewrite, and worth following the Chaos Labs methodology page status (might be intentional pre-launch, might be deprecation).

2. **HyperStone (RedStone-HIP3) has run ~$1.5B cumulative volume of permissionless-equity-perp markets on Hyperliquid with zero published statistical-coverage claim.** This is the cleanest contemporary "equity-perp oracle with no calibration disclosure" archetype; the paper currently doesn't reference it and arguably should — the framing "Hyperliquid's HIP-3 ecosystem operationalizes equity-perp pricing entirely via opaque oracles" sharpens §2.1's core argument considerably.

3. **Ondo's 2026-Q1 Solana tokenized-stock launch explicitly delegates pricing to Chainlink.** This means both Backed (xStocks) and Ondo concentrate equity pricing on Solana into one provider, raising the systemic-concentration framing for §1.1 / §9 — there are not two competing equity-pricing planes on Solana, there is one (Chainlink) and a non-canonical secondary (Pyth equity tickers). If a future bank-grade RWA integration questions oracle redundancy under SR 11-7 / SR 26-2, this is the answer they will hit. Worth surfacing this concentration in the paper's regulatory framing.

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
| A12 | **Chainlink Smart Data Streams** | Adjacent product to Data Streams v10/v11. Verify whether this is a real distinct product or a rebrand. | docs.chain.link | P2 |
| A13 | **Chainlink Functions / Automation as oracle proxy** | Some teams build app-specific oracles atop Chainlink Functions. Worth a quick survey of who's done this for equities. | docs.chain.link/chainlink-functions | P3 |

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
