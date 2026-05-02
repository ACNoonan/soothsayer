# Soothsayer product stack — market research, May 2026

**Audience:** internal — companion to `docs/product_stack.md`. Each section answers two questions per layer: (a) is there demonstrated, communicated demand for this kind of primitive? (b) what is a defensible market-size estimate?

**Headline.** The window is open and visibly narrowing. Tokenized equities on Solana hit ~$2B in onchain RWA value by March 2026, ~94% of all-time tokenized equity spot volume settled on Solana, and Q1 2026 tokenized-asset trading volumes hit a record $1.3B. The structural problems Soothsayer addresses — LVR bleed for LPs, halt-driven oracle gaps for perps, calibration-free uncertainty — are now openly discussed by Blockworks Research, FalconX, MetaMask/Hyperliquid commentary, and academic work as the *binding constraints* on this market growing further. At the same time, Chainlink has already shipped an "RWA Advanced (v11)" schema that exposes session state (regular hours / pre-market / overnight / weekend) and won the official xStocks oracle slot at Kamino. The slot above point-in-time data — calibrated bands with coverage receipts — is empty but will not stay empty for long.

---

## Layer 0 — Calibration-transparent oracle band

### Demonstrated demand

**Yes, but heavily filtered through the existing oracle vendors' product surface.** The market does not demand "calibration receipts" as a stated requirement; it demands the *outcome* — fewer bad liquidations, less LP bleed, perps that survive halts. The chain of evidence:

- **MetaMask/Hyperliquid commentary on perp liquidations** explicitly identifies oracle design (aggregation, circuit breakers, TWAPs) as critical, with a worked scenario where "a transient price spike on a single exchange feeds into an index with too much weight, momentarily lifting the mark price; short positions are liquidated onchain before the feed normalizes" — this is exactly the failure mode a calibrated band defends against.
- **The JELLYJELLY incident on Hyperliquid (March 2025)** caused $12M of HLP losses via oracle manipulation and is repeatedly cited as the canonical "your oracle is your single point of failure" reference.
- **The Volcano Exchange analysis of tokenized-asset liquidity** documents a real case where a single illiquid spot market triggered $9.21M in Hyperliquid liquidations *exceeding the Binance liquidation volume that fed the oracle*. The conclusion in their piece is that the oracle's input weighting is the propagation mechanism — uncertainty was present in the input, was not represented in the output, and the consumers were forced to act as if the point was certain.
- **Chainlink's "RWA Advanced (v11)" schema** ships a session enum (0=Unknown, 1=Pre-market, 2=Regular, 3=Post-market, 4=Overnight, 5=Weekend). The market for *some* notion of "this price is more or less reliable right now" is already real enough that the incumbent surfaces a coarse version of it. The latent demand for a continuous, calibrated version is implied.
- **Pyth's roadmap pivot to "Pyth Pro" and the Pyth Data Marketplace (April 2026, with Fidelity and Euronext)** validates the thesis that the oracle layer's commercial future is institutional-grade, calibrated data products — not just commodity price-point feeds.

### Market sizing

The relevant comparables are the two oracle incumbents' revenue:

- **Chainlink TVS:** $93B (mid-2025) growing to $66.3B–$95B reported across late-2025/early-2026 sources, with $58.8M annualised fees / $55.5M annualised revenue per DefiLlama. Oracle fees are roughly 5–6 bp of TVS annualised in this regime.
- **Pyth Network TVS:** ~$6.14B with the protocol moving to subscription-style revenue via Pyth Pro.
- **Bloomberg Intelligence's projection** is for the overall oracle market to expand ~10× by 2030. RedStone has emerged as the third pole on the strength of bespoke RWA feeds (BUIDL, ACRED).

A calibration-band oracle does not need to displace either — it sits as a layer on top, monetised either as licensing to existing oracle distribution (Pyth Pro–style) or as protocol-fee capture inside layered products. The realistic bracket for the standalone oracle business at this layer's maturity:

- **Bear case (license-only, 1% of Chainlink-equivalent fee pool by 2028):** ~$0.5–1M ARR.
- **Base case (oracle-band layer used by 5–10 RWA-perp/AMM/lending protocols handling $5–15B notional):** ~$3–8M ARR.
- **Bull case (becomes the *default* uncertainty layer for tokenized-equity DeFi at sub-$30B TVS by 2028):** ~$15–25M ARR.

The constraint at this layer is not TAM — it's distribution. Pyth and Chainlink already own the publish/distribute rails, and Kamino + xStocks chose Chainlink. Layer 0 alone is a thin business; its defensibility comes from being the *primitive* the rest of the stack consumes.

---

## Layer 1 — Band-AMM (calibration-conditioned CLMM/DLMM)

### Demonstrated demand

**The strongest yes in the stack, and the demand is openly stated by the affected party (LPs).** LVR is no longer an academic debate. The literature has hardened — the original Milionis et al. paper, the QuantAMM RVR refinement (Nov 2024), the deterministic-block-time generalisation (May 2025), and the IL-vs-LVR statistical analysis (Feb 2025). Practitioner write-ups from CoW, Anthony Lee Zhang, and Gate explicitly identify oracle-conditioned AMMs as the canonical solution class:

> *"AMM LPs lose money from price slippage: when Binance prices move, AMM quotes become 'stale'. An obvious solution is that if AMMs updated price quotes when Binance prices move, LVR would be reduced. This is quite tricky to implement in practice — it requires a very high-frequency oracle, and is vulnerable to oracle manipulation attacks — but in theory with a perfectly fast and non-manipulable oracle, this could eliminate LVR."*  
> — Anthony Lee Zhang summarising Milionis et al.

The "vulnerable to oracle manipulation" caveat is precisely what a *band* (rather than a point) is designed to neutralise — manipulation that pushes the served price within band edges should not trigger fee-free arb. This is an unbuilt design point that the literature has reached but no Solana production AMM has shipped.

The Solana DLMM/CLMM ecosystem is the natural deployment surface:
- Raydium's CLMM, Orca's Whirlpools, and Meteora's DLMM dominate Solana spot. Daily volumes routinely run $1–3B aggregate, with Raydium alone hitting $1.2B+ on active days. Solana captured 41% of all onchain spot volume in Q1 2026 per Blockworks Advisory.
- xStocks-specific volume is concentrated on Raydium ($250M+ in tokenized stock volume by late 2025, ~90% of cross-protocol share).
- Tokenized-asset trading volume hit a Q1 2026 ATH of $1.3B, *up 164% QoQ*.

### Market sizing

The fee pool that LVR currently leaks out of LPs is the addressable pie:

- Independent analyses estimate LVR is roughly comparable in magnitude to total LP fee revenue on volatile-pair CLMMs. On a Solana CLMM/DLMM ecosystem doing roughly $400–700B annualised volume at 10–30 bp blended fees, that's $400M–$2B per year in LP fees, with a similar order of magnitude in LVR leakage.
- Even capturing **5% of LVR back to LPs through band-edge auctions** on the volatile RWA subset (~5–15% of Solana DEX volume by 2027 base case) is in the range of **$10–50M ARR of recapturable value**, of which a band-AMM protocol could plausibly retain 10–25% as protocol revenue.
- A more conservative bottom-up: target 15% of xStocks AMM volume by end-2027. xStocks DEX volume is currently ~$500M+ cumulative on Solana with monthly run-rates that have been accelerating; assume $5–10B annualised by 2027 base case, 25 bp fee, 50% LVR-recapture share to LPs, 20% protocol take = **~$1.25–5M ARR** at base case, scaling sharply with tokenized-equity adoption.

### Risks specific to this layer

- **Oracle latency vs. block production.** LVR-minimising AMMs depend on the oracle being faster than the underlying market. Pyth Lazer / RedStone Bolt are racing to provide sub-second updates; the band-AMM needs to be evaluated against that timing, not against a 30s-update assumption.
- **Bin-based DLMMs ≠ CLMMs ≠ TFMMs.** QuantAMM's RVR analysis showed that the LVR benchmark itself depends on rebalancing assumptions. The methodology paper (Paper 4) needs to be honest about which of these architectures the band-conditioning improves, and by how much.

---

## Layer 2 — Band-perp (halt-aware perpetual on tokenized RWAs)

### Demonstrated demand

**Yes, and Blockworks Research has named the exact gap your stack fills.** The Equity Perpetuals Landscape Report (Dec 2025) is the single best market-validation document for Soothsayer's L2:

> *"Three critical design requirements define viable equity perps: (1) continuous oracles, (2) deep orderbook liquidity to prevent mark volatility and cascading liquidations, and (3) reliable hedging mechanisms that accommodate TradFi's limited trading hours and T+1 settlement."*

And then it surveys the four live competing approaches and shows each one has an unsolved gap that maps directly to the band primitive:

| Venue | Approach | Unsolved gap |
|---|---|---|
| **Hyperliquid HIP-3 (Trade.XYZ)** | Validator orderbook + relayer oracle ~3s updates | "Off-hours pricing" risk + "bounded discovery" required during halts; weekend delta gaps |
| **Ostium (Arbitrum)** | Peer-to-pool with offchain hedge | Halts on weekends; LP buffer under-collateralised 85+ days |
| **Solana xStocks-collateralised perps (concept)** | Atomic cross-margin with spot xStocks | "Promises atomic cross-margining yet remains unrealized" |
| **Vest** | Dynamic offchain hedging | Adaptive weekend pricing — exactly the function a calibrated band performs |

Volumes already happening:
- HIP-3 hit **$25B cumulative volume** since Oct 2025 launch, **$1.43B peak open interest** (March 2026), **35% of all Hyperliquid volume**, with ~75K unique traders.
- Trade.XYZ alone: **$87M annualised fees / $43M annualised revenue** (DefiLlama), got an official S&P 500 license March 2026.
- The TD Securities piece ("Perpetual Futures: The Missing Link in Tokenized Equities", Oct 2025) confirms regulatory tailwinds — CFTC and SEC have explicitly named PERPs as in scope for 2026 rulemaking.

The "perp vs. tokenized equity" Sentora article frames the dichotomy cleanly: tokenized equities are "digitising the asset," perps are "digitising the variance." Soothsayer's L2 is the only design where the *uncertainty in the underlying* is a first-class input to mark-and-liquidation, rather than something the protocol either ignores (Hyperliquid) or operationally hedges around (Ostium).

### Market sizing

The reference TAM is the global retail flow into US-equity leveraged exposure that currently leaks to CFDs and offshore venues:

- **CFDs outside the US: ~$30T monthly notional** per the MEXC piece on RWA perps.
- **US options monthly notional: ~$89T (~$48T in 0DTE)**, per the same Blockworks landscape report.
- **South Korea alone accounts for ~40% of overnight US equity volume**, with Asia-Pacific the dominant retail-flow source.

Realistic capture for a Solana-native, halt-aware single-asset-class perp DEX:

- **Bear case (1% of HIP-3-style volume by 2027):** $250M cumulative volume, ~$1–2M annualised fees at HIP-3 economics.
- **Base case (5% — i.e., the Solana-native tokenized-equity perp captures parity with xStocks' Solana spot share within the perp space):** $1.25B cumulative volume, ~$5–10M annualised fees.
- **Bull case (becomes the reference equity-perp venue on Solana, displacing Drift's equity ambitions):** $20–50M annualised fees by 2028.

### Risks specific to this layer

- **Hyperliquid is the elephant.** HIP-3 + 880K user base + S&P 500 license is a deep moat for the *generic* equity-perp. Soothsayer's L2 wins only on the halt-aware narrative — that's a thin wedge unless the cross-margin xStocks-collateral story (which Blockworks calls out as "yet unrealised on Solana") gets executed.
- **"Halt-aware" is hard to sell pre-incident.** The product matures in value the moment another HLP-equivalent loss happens. Until then, the demand is largely from sophisticated LPs and risk-aware liquidators — not retail flow.

---

## Layer 3 — Band-options / band-vaults

### Demonstrated demand

**Real but earlier-stage.** The demand signal is the existence of forward-looking IV indices (Volmex SVIV for Solana, BVIV/EVIV for BTC/ETH) and the CME's launch of options on SOL/XRP futures (Oct 2025) — the institutional plumbing for "I want to trade volatility on these assets" exists. What's missing is a Solana-native onchain options venue with credible IV pricing for tokenized RWAs specifically.

The thesis at this layer is that *calibrated band width is itself a usable IV proxy*. If Paper 4 lands and Layer 1's band-edge fees demonstrate empirical coverage, then the same band width (per τ) is a structurally consistent input to options pricing — without needing an independent IV surface to be modelled and maintained. This is a real product wedge but it's downstream of Paper 4 + Paper 2-equivalent (an options paper) landing first.

### Market sizing

Onchain options is small compared to perps. Deribit dominates centralised crypto options at $40–60B monthly notional; onchain (Lyra, Zeta, Aevo, Premia) is collectively well under $1B monthly. The demand growth path is:

- Crypto options grew from BTC/ETH to SOL/XRP through 2025; the natural next leg is *tokenized equity* options as the underlying onchain spot deepens.
- Conservative 2028 sizing: $200M–$2B monthly notional onchain RWA options if tokenized equities reach $50–100B AUM (vs. ~$1B today, $30B+ projected by year-end 2026 per RWA.xyz/Blockworks).
- Vault/structured-product overlay: 2–10% of underlying options notional in vault TVL; 50–200 bp blended fees → **~$2–20M ARR** in the optimistic 2028 case.

This layer is a *strategy slot* not a near-term build commitment, consistent with how the product-stack doc already frames it.

### Risks specific to this layer

- **Composability dependency.** Layer 3 is the layer most dependent on Layer 1 + 2 actually shipping with measurable LP economics. If Paper 4's empirical results are weaker than the calibration receipts suggest, the IV-from-band-width thesis collapses.
- **Zeta/Drift options expansion.** Drift has signalled options ambitions and Zeta has the existing Solana options venue. The build vs. layer-on decision in your doc is correct — building from scratch here is unwise.

---

## Layer 4 — Settlement / index licensing

### Demonstrated demand

**Yes, and partially already-claimed.** This is the most uncomfortable finding in the research:

- **Chainlink already won the xStocks oracle slot at Kamino**, with a "custom-built xStocks oracle delivering sub-second price updates for tokenized equities," and is the official oracle infrastructure of the xStocks Alliance (Kraken, Bybit, Raydium, Jupiter, Kamino).
- **Pyth integrated with Polymarket** for prediction-market settlement on RWAs (gold, oil, US equities) and launched the Pyth Data Marketplace with Fidelity and Euronext backing in April 2026.
- **RedStone won the BlackRock BUIDL and Apollo ACRED tokenized-fund feeds**, plus the Ethena and Gearbox slots.

The licensing pattern that's actually working in 2026 is the *bespoke* RWA feed — a custom oracle product co-designed with the consumer protocol — not a generic data feed. RedStone's framing ("By builders, for builders") and Pyth's first-party data publisher model are both validation that the licensing market is structured around *trust-bearing custom feeds*, not commodity price points.

The wedge for Soothsayer at this layer is *the calibration receipt itself* as a contract clause. A consuming protocol like Kamino or Loopscale today has no machine-verifiable answer to "how do I size my liquidation buffer?" beyond manual risk-committee judgement. A licensable band feed with empirically-passing Kupiec/Christoffersen results gives them an auditable input. This is a different product than what Chainlink/Pyth/RedStone currently sell.

### Market sizing

Direct comparables:
- **Chainlink:** ~$58M annualised fees off ~$90B TVS.
- **Pyth Pro subscription:** institutional pricing, exact figures undisclosed but implied to be 6–8 figure annual contracts with institutional buyers.
- **RedStone:** undisclosed but reportedly ~40-person team with bespoke RWA contracts; a few million ARR run-rate is the public estimate.

Soothsayer at L4 is realistically a *secondary-rail licensee*, riding on Pyth's distribution. Realistic 2027–2028 sizing:

- **Bear (1–2 anchor consumers, e.g. one lending market + one perp DEX):** $500K–1.5M ARR.
- **Base (5–10 consumer protocols, recurring):** $3–8M ARR.
- **Bull (becomes the licensed reference rate for tokenized-equity DeFi, displacing Chainlink xStocks oracle as Kamino's default):** $15–30M ARR by 2028.

The bull case requires either (a) Chainlink's xStocks oracle to publicly fail in a way the band primitive obviously fixes, or (b) a new tokenized-equity protocol (a Kamino-equivalent that doesn't yet exist) picking Soothsayer at launch as the default.

### Risks specific to this layer

- **Distribution disadvantage is structural.** Chainlink has 700 oracle networks, 2,400+ integrations, partnerships with Swift/UBS/JPMorgan. RedStone has shown a small fast team can win bespoke slots, but it took 3+ years.
- **The "calibration receipt" framing has not been market-tested.** It's intellectually correct. Whether risk committees at Kamino-tier protocols will pay a premium for it, vs. continuing to manually parameterise around Chainlink point feeds, is unproven.

---

## Cross-cutting observations

1. **Solana wins the asset-class venue battle, decisively.** ~94% of all-time tokenized-equity spot settlement is on Solana per March 2026 data; xStocks holds ~93% of tokenized-stock market share; Kamino is the dominant lending venue. The tokenized-equity-on-Solana thesis is now consensus, not a bet. The bet you're actually making is *which infrastructure layer captures the value within that consensus*.

2. **The competitive geometry favours layered specialisation, not a competing oracle network.** Chainlink/Pyth/RedStone have won the "deliver a price" race. The undefended slot is "deliver a price *with a credible uncertainty representation that downstream protocols can use as a contract input*." That's a thin slot but it's structurally above where the incumbents compete.

3. **Layer 1 and Layer 2 are the two layers with the strongest near-term commercial pull.** Layer 1's pull comes from LVR being a measurable, painful, well-formalised problem with an active LP audience. Layer 2's pull comes from the Blockworks landscape report essentially specifying your product. Layer 0 is the necessary primitive but is not a standalone business. Layers 3 and 4 are correctly gated.

4. **The calibration angle needs to ship as a *protocol-level integration story*, not as a "better oracle" story.** Every market-validation source above frames demand in terms of "what does the consuming protocol need" — fewer bad liquidations, less LVR bleed, halt-aware mark prices. Selling "calibrated bands" abstractly is a category error; selling "Kamino's liquidation buffer that doesn't blow up on a halt" is the same product, packaged for the buyer.

5. **The window closes when Chainlink ships a band primitive of their own.** Their RWA Advanced (v11) session enum is already directional. Pyth Pro is moving toward institutional data products. Probability of an incumbent shipping calibrated-uncertainty within 18 months is non-trivial; the moat is the empirical receipt — *demonstrated coverage on RWA-specific halt boundaries* — and is therefore data-pipeline-bound. This reinforces the priority order in `scryer_pipeline_plan.md`.

## Headline numbers to remember

- Solana tokenized-asset trading volume Q1 2026: **$1.3B (+164% QoQ)**
- Onchain tokenized RWA total (ex-stablecoins): **$26.4B (March 2026), 300% YoY**, projection $100B+ by end-2026
- Solana DEX share of onchain spot: **41% (Q1 2026)**, exceeding Ethereum + L2s combined
- xStocks Solana share: **~93% of tokenized stocks**, Solana settled ~94% of all-time onchain tokenized-equity volume
- Kamino TVL: **$2–3B**, first major DeFi lender to accept tokenized stocks (Chainlink-powered)
- HIP-3 cumulative volume since Oct 2025: **$25B**, 35% of Hyperliquid volume, $1.43B peak OI
- Trade.XYZ annualised: **$87M fees / $43M revenue** — single deployer
- Chainlink TVS: **$66–93B** depending on source, **~$58M annualised fees**
- Pyth TVS: **~$6.14B**, pivoting to institutional subscription via Pyth Pro
- BCG / McKinsey / Standard Chartered 2030–2034 RWA forecasts: **$2T / $16T / $30T**

## See also

- `docs/product_stack.md` — the layered framing this memo serves.
- `reports/paper4_oracle_conditioned_amm/plan.md` §16 — links back to product stack.
- `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md` — the data pipelines whose value is reinforced by every layer's demand evidence.
- Blockworks Research: "Equity Perpetuals Landscape Report" (Dec 2025) — single most useful external doc for Layer 2.
- FalconX: "The Transformational Potential of Hyperliquid's HIP-3" — the upside scenario for what your competitor would do.
- Volcano Exchange: "Liquidity: The Broken Promise of Tokenized Assets" (Jan 2026) — best public articulation of the failure modes Soothsayer's band addresses.