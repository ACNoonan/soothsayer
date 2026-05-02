# Paper 4 — Colosseum implementation brief (spot oracle-aware AMM)

**Status:** research brief, drafted 2026-05-02. Input to the 8-day hackathon scope (deadline 2026-05-10).
**Audience:** Adam, scoping the devnet MVP + pitch deck.
**Read first:** `reports/paper4_oracle_conditioned_amm/plan.md`, `reports/paper4_oracle_conditioned_amm/market-research.md`, `docs/product-stack.md`, `docs/product-spec.md`.
**Companion:** the implementation plan that flows from this brief should be drafted into `reports/paper4_oracle_conditioned_amm/colosseum_plan.md` (not yet written).

---

## Executive summary

Soothsayer already publishes a calibrated band on-chain (`PriceUpdate` PDA per symbol via `soothsayer-oracle-program`; regime-routed via `soothsayer-router-program`). What does *not* yet exist is a spot DEX that *uses* the band as a first-class quote object rather than a point reference. That is the wedge.

**Recommended 8-day MVP: a single-active-range "BandAMM" — a pool whose entire quoted range *is* the calibrated band `[L_τ, U_τ]`, with a band-breach surcharge fee outside it.** This is the simplest mechanism that consumes both edges + the receipt (`claimed_served_bps`, `regime_code`), is implementable in one ~600-line Anchor program, demonstrates visibly different behaviour from CPMM at weekend reopen, and routes Jupiter via the existing `jupiter-amm-interface`. Bigger mechanisms (am-AMM-style auctions, Angstrom-style ASS, FM-AMM batch clearing) are the right academic targets for Paper 4's published `g(·)` bound but are not 8-day-shippable on Solana without BAM Plugin SDK maturity.

The pitch lead is *the LVR problem on tokenized equities*, not the academic bound. LVR literature (Milionis 2022, am-AMM 2024, Angstrom 2025, FM-AMM 2023) has reached the design point but no Solana production AMM has shipped a band-conditioned execution layer; xStocks volume is concentrated on oracle-blind CPMMs (Raydium ~90% share, ~$517M cumulative DEX volume by Jan 2026). The mechanism is intuitive in 30 seconds; the calibration receipts are the credibility wedge. **Hardest risks:** publisher cadence on devnet, xStock devnet mint availability, and counterfactual fidelity without the forward pool-state tape (scryer item 51 in flight).

---

## Phase 1 — Repo state of art

### 1.1 What Paper 4 currently asserts

From `reports/paper4_oracle_conditioned_amm/plan.md`:

- **Thesis (§1):** *"A BAM Plugin AMM that conditions execution on a calibration-transparent oracle band exposes a derivable LVR-recovery lower bound for tokenized-RWA pools during closed-market windows, where both the oracle's calibration claim and the Plugin's compliance with that bound are independently verifiable from public data."* (`plan.md:17`)
- **Three theoretical claims (§4):** C1 the bound exists; C2 it is non-trivial; C3 it is auditable. (`plan.md:62-68`)
- **Three empirical claims (§4):** E1 closed-market LVR concentration; E2 σ²/8·V misprediction; E3 bundle-conditional realisation. (`plan.md:72-76`)
- **Mechanism families (§7):** B0 status-quo CLMM, B1 Pyth-anchored CLMM, B2 calibration-conditioned CLMM via BAM Plugin, B3 + reopen auction. (`plan.md:150-153`)
- **Plugin spec (§6.2):** standard-fee band `[L_t, U_t]`; scaled-fee tier outside; outside-band auction sequenced via BAM. Stated under sub-second oracle-update assumption. (`plan.md:130-138`)
- **Scope filter (§5.5):** the mechanism is meaningful only on RWA classes with an exogenous true price + time-varying uncertainty — i.e., xStocks and other halt-bearing tokenized equities. Pure-crypto pairs and stablecoin/LST pairs are explicitly out of scope. (`plan.md:96-118`)
- **Sequencing (§12, §15):** Paper 4 is post-grant, ~16-18 months from grant kickoff to arXiv. *Hackathon repositions Paper 4's mechanism as the live demo / lead pitch — the academic bound becomes the credibility primitive, not the deliverable.*
- **Phase-A urgency (§16):** the moat is the empirical receipt; pool-state + bundle-attribution + cadence-stratified LVR-recovery on RWA pools. Forward-only data; deferral cost grows linearly. Driver of `scryer_pipeline_plan.md`.

### 1.2 What evidence backs each claim

Paper 4 itself has zero empirical evidence yet — it is plan + market research only. The evidence Adam can rely on for the hackathon pitch is:

| Layer | Evidence | Source |
|---|---|---|
| Calibration receipt is real | OOS Kupiec + Christoffersen pass at τ ∈ {0.68, 0.85, 0.95} on 5,986 weekends × 10 tickers × 12 years | `reports/v1b_calibration.md`, `reports/v1b_decision.md` |
| The band as a serving primitive ships | Devnet `soothsayer-router` deployed 2026-04-29; on-chain `PriceUpdate` PDA layout locked | `docs/product-stack.md` row 0; `programs/soothsayer-oracle-program/src/state.rs:75-119` |
| LVR is a real, large LP cost | a16z, Milionis et al., Anthony Lee Zhang summary; size estimate $400M–$2B/yr Solana CLMM/DLMM fees with same-order LVR leakage | `reports/paper4_oracle_conditioned_amm/market-research.md:43-61` (compiled cite block) |
| xStocks demand is real and concentrating on Solana | $1.3B Q1 2026 tokenized volume (+164% QoQ); ~94% all-time tokenized-equity settlement on Solana; Raydium ~90% xStock-DEX share | `market-research.md:178-199` |

What is *not* yet evidence: a concrete LP-economics number for any band-conditioned mechanism on a real xStock pool. The hackathon counterfactual gap (§3.5).

### 1.3 What mechanisms are spec'd vs. shipped

| Item | Spec | Built |
|---|---|---|
| `g(q, ρ, f_min, w_t, σ_t)` bound | sketched, data-first; functional form deferred to Phase B | none |
| BAM Plugin reference | sketched (`plan.md:130-138`); stated against sub-second cadence | none |
| Pool-state reconstructor (P2.1) | spec in `scryer_pipeline_plan.md:101` | none |
| Path-aware truth labeller (P2.2) | spec in `scryer_pipeline_plan.md:102` | none |
| Counterfactual replay engine (P2.3) | spec in `scryer_pipeline_plan.md:103` | none |
| Bundle-attribution → LVR labels (P2.4) | spec in `scryer_pipeline_plan.md:104` | none |

### 1.4 Oracle / publish primitives the AMM can already rely on

Strong existing surface — this is where the hackathon timeline becomes feasible.

- **`programs/soothsayer-oracle-program`** (`src/lib.rs:1-199`): four-instruction Anchor program. Per-symbol `PriceUpdate` PDA seeded `[b"price", symbol]`. Wire shape locked at version 1: `point: i64, lower: i64, upper: i64, target_coverage_bps: u16, claimed_served_bps: u16, buffer_applied_bps: u16, regime_code: u8, forecaster_code: u8, exponent: i8, publish_ts, publish_slot, signer, signer_epoch`. Single shared `exponent` for all price fields — clean for AMM consumption. (`programs/soothsayer-oracle-program/src/state.rs:75-119`)
- **`programs/soothsayer-router-program`** (`src/lib.rs:30-296`): regime-routes between (a) open-hours multi-upstream median + filter pipeline (`UnifiedFeedSnapshot`) and (b) closed-hours `soothsayer_band` PDA. Same `(point, lower, upper)` shape on output. v0 governance: 2-of-3 multisig authority. Devnet-deployed 2026-04-29.
- **`programs/soothsayer-streams-relay-program`**: Chainlink Data Streams ingestion path (relay PDAs). Not on the AMM critical path but provides the open-hours leg for the router.
- **`crates/soothsayer-consumer`** (`src/lib.rs:1-324`): `no_std` decoder. `decode_price_update(&[u8]) -> Result<PriceBand, _>` plus invariant validation (`lower ≤ point ≤ upper`, coverage ≤ 10000 bps, version match, anchor discriminator check). The AMM program imports this directly.
- **`crates/soothsayer-demo-kamino`** (`src/lib.rs:1-120`): teaching artefact for "how a consumer protocol reads the band into protocol action." Pattern-match for the AMM consumer; same `PriceBand` import surface.
- **`crates/soothsayer-publisher`**: CLI that fans `oracle.fair_value()` outputs into `PublishPayload` for the on-chain program.
- **xStock universe (locked):** SPYx, QQQx, AAPLx, GOOGLx, NVDAx, TSLAx, HOODx, MSTRx (`scryer_pipeline_plan.md:45`). GLDx/TLTx pending Backed listing.

**Implication:** the band-feed primitive the AMM needs to read is already on devnet. The hackathon work is on the *consumer* side — a new Anchor program that reads `PriceUpdate` PDAs as its quote source.

---

## Phase 2 — External research

### 2.1 LVR / oracle-aware AMM literature (1-2 lines each)

| Mechanism | Idea | Why it matters for our pitch |
|---|---|---|
| **Milionis–Moallemi–Roughgarden–Zhang 2022** "Automated Market Making and Loss-Versus-Rebalancing" ([arxiv:2208.06046](https://arxiv.org/abs/2208.06046), [a16z explainer](https://a16zcrypto.com/posts/article/lvr-quantifying-the-cost-of-providing-liquidity-to-automated-market-makers/)) | Black-Scholes-for-AMMs; LVR is the LP-side cost of stale prices arbitraged against a continuous reference. σ²/8·V approximation. | The foundational citation. Quantifies the $400M–$2B/yr Solana addressable pie. The σ²/8·V *fails* in closed-market windows — that gap is where Paper 4 lives. |
| **am-AMM** (Adams–Moallemi–Reynolds–Robinson, FC 2025) ([arxiv:2403.03367](https://arxiv.org/abs/2403.03367), [FC25 PDF](https://fc25.ifca.ai/preproceedings/183.pdf)) | Auction the LP-manager role via Harberger lease; manager keeps fees + first-arb rights, pays rent to LPs. | Auction the *role*, not the trade. Oracle-blind. Soothsayer's wedge is band-conditioned execution; am-AMM is complementary, not competitive. |
| **Angstrom / Sorella** (Uniswap v4 hook, mainnet-tracking 2025) ([Crypto-Economy](https://crypto-economy.com/uniswap-presents-angstrom-new-dex-with-native-mev-protection-for-swappers-and-lps/), [Arrakis](https://arrakis.finance/blog/the-amm-renaissance-how-mev-auctions-and-dynamic-fees-prevent-lvr)) | App-Specific Sequencer via v4 hook; runs an arb-recapture auction every block, redirects bid to LPs. | Closest live cousin to B3 in `plan.md`. Oracle-blind. Solana has no v4-hook equivalent; the closest primitive is BAM Plugin (post-2026). |
| **FM-AMM / CoW AMM** (Canidio–Fritsch, AFT 2023) ([arxiv:2307.02074](https://arxiv.org/abs/2307.02074), [CoW AMM](https://cow.fi/cow-amm)) | Function-maximizing AMM with batch clearing — single per-block clearing price; arb-profit-eliminating in equilibrium. | Mechanism-design proof that LVR can be eliminated via auction structure, oracle-blind. Soothsayer's framing is *complementary* — band = uncertainty primitive, batch = execution primitive. |
| **McAMM** (Hermann / Gnosis, ethresear.ch 2022) ([Ethresearch](https://ethresear.ch/t/mev-capturing-amm-mcamm/13336)) | Auction the right to be first-tx-of-block against the pool; rebate to LPs. | Earliest "MEV-capturing AMM" framing. Inspires Paper 4's B3 (reopen-window auction). |
| **RediSwap** ([arxiv:2410.18434](https://arxiv.org/html/2410.18434)) | Application-level MEV redistribution; claims <0.5% of original LVR retained in 89% of trades. | Redistribution-style design — useful as a comparator for Paper 4's `g(·)` baseline if any post-grant work targets ICML-financial. |
| **Lifinity (Solana, live since Jan 2022)** ([docs](https://docs.lifinity.io/), [DefiLlama](https://defillama.com/protocol/lifinity-v2)) | Pyth-priced proactive market maker, protocol-owned liquidity, lazy rebalancing. Closest extant Solana analogue. | The *exact* "oracle-priced AMM on Solana" surface. **Caveat:** winding down, all assets to be claimed by Dec 31 2026. The wedge is wide open. Soothsayer's differentiator vs. Lifinity: Lifinity quotes the Pyth point + an internal spread; Soothsayer would quote *the calibrated band itself*, eliminating the consumer-side `k·conf` heuristic. |
| **Hashflow (Solana RFQ)** ([blog](https://blog.hashflow.com/hashflow-solana-expansion-deeper-liquidity-more-tokens-9851fb4c4c5a)) | Off-chain market makers sign quotes; on-chain execution is settle-only. | Adjacent design point — RFQ avoids LVR by construction (no pool to arb) but requires off-chain MM relationships. Not the path for an open-pool xStock LP product. |
| **Pyth-anchored hypothetical** | Read `(price, conf)`, fee-scale on `conf`. | Paper 1 §2.1 + `reports/v1b_pyth_comparison.md` documents that Pyth `conf` under-covers by ~10× at face value — the consumer-side calibration burden is what the band primitive removes. This is the B1 baseline. |

### 2.2 Solana DEX surfaces and the right primitive

For an oracle-priced AMM that wants Jupiter routing + xStock LP capital, the question is: clone, plug in, or invent?

- **Orca Whirlpools** ([github](https://github.com/orca-so/whirlpools)). Open-source CLMM with mature tick math (`tick_math.rs`, `tick_manager.rs`, 88-tick arrays). Forking the full Whirlpool program in 8 days is heavy — tick-array account creation logic + tick crossing during swap is the bulk of the LOC. **Useful as a reference, not as the fork base.**
- **Meteora DLMM** ([docs](https://docs.meteora.ag/user-guide/guides/how-to-use-dlmm), [github](https://github.com/MeteoraAg)). Bin-based DLMM where a single *active bin* earns all fees with zero slippage in-bin. Conceptually closest match to "the band IS the active range." DLMM source is partially open; bin-step + variable-fee math is the relevant subset. *(Trading volume scaled from $987M Dec 2024 → $39.9B Jan 2025; >15% Solana DEX volume by Q1 2025.)*
- **Raydium CLMM** ([liquidity-pools](https://raydium.io/liquidity-pools/)). Top Solana DEX by volume — $35.6B 30-day volume May 2025 — and the xStock liquidity venue (~90% cross-protocol share). Raydium CLMM is closed-source-leaning; not a fork base.
- **Phoenix CLOB**. Order-book; wrong primitive for an oracle-quoted band model.
- **Lifinity** ([site](https://lifinity.io/), [solanacompass](https://solanacompass.com/projects/lifinity)). Closed-source, protocol-owned liquidity, oracle-priced. *Not* a fork base — but the live-product comparable to cite in the deck. The product wind-down (Dec 2026 sunset) creates open shelf-space.
- **Jupiter aggregator interface** ([repo](https://github.com/jup-ag/jupiter-amm-interface), [dev docs](https://dev.jup.ag/docs/routing/dex-integration)). The trait you implement (Rust `Amm` trait) to be discoverable in Jupiter routing. Free integration, security-and-traction-gated. **Critical primitive to wire late in the hackathon for distribution.**

**Right primitive for the hackathon:** a *single-active-range AMM* where the active range tracks the served band. This is essentially **a one-bin DLMM whose bin moves with the oracle** — minimal swap math, no tick-array account proliferation, full receipt-aware execution. See §3.2 for the build path.

### 2.3 Backed Finance / xStocks ecosystem

- **Issuer:** Backed Finance (Swiss-regulated). Each xStock SPL is 1:1 with custodied shares. ([Backed](https://backed.fi/), [Solana case study](https://solana.com/news/case-study-xstocks)).
- **Universe:** 60+ tokenized stocks live since 2025-06-30; 74 xStocks tracked on RWA.xyz as of Jan 2026 ([k.co.cr list](https://www.k.co.cr/2026/02/liquidity-pools-for-74-xstocks-on.html), [coin metrics](https://coinmetrics.io/state-of-the-network/tokenized-equities-and-xstocks-on-solana/)).
- **Onchain volume / supply:** Jan 2026 cumulative onchain xStock volume >$3B; cumulative DEX volume >$517M; 57k+ unique holders; total xStock value ~$196M (~$182M on Solana). ([k.co.cr](https://www.k.co.cr/2026/02/xstocks-on-solana-complete-list-and.html))
- **DEX concentration:** primary pool per xStock typically Raydium CLMM, secondary Orca Whirlpools; some Meteora DLMM exposure on long-tail names. ~90% cross-protocol share concentrated in Raydium per `market-research.md:52`.
- **Pool quality observation:** the public pool list shows wide spreads + thin depth on most non-SPYx/QQQx names; this is the "halt-aware band quoting beats CPMM" demo waiting to happen. SPYx and QQQx have the deepest pools and would be the obvious primary demo pair.

### 2.4 Market-need cites for the deck (drop-in)

8–15 cites Adam can use directly. Each item: source + URL + 1-line takeaway.

1. [Milionis–Moallemi–Roughgarden–Zhang (2022)](https://arxiv.org/abs/2208.06046) — *foundational LVR paper; every LP costs paper since cites it.*
2. [a16z crypto: "LVR — quantifying the cost of providing liquidity to AMMs"](https://a16zcrypto.com/posts/article/lvr-quantifying-the-cost-of-providing-liquidity-to-automated-market-makers/) — *practitioner-friendly summary; 5–7% LP cost figure widely cited.*
3. [Anthony Lee Zhang's LVR explainer](https://anthonyleezhang.github.io/pdfs/lvr.pdf) — *"with a perfectly fast and non-manipulable oracle, this could eliminate LVR" — the literal sentence we are responding to.*
4. [Fenbushi: "Ending LP's Losing Game"](https://fenbushi.vc/2024/01/20/ending-lps-losing-game-exploring-the-loss-versus-rebalancing-lvr-problem-and-its-solutions/) — *VC-side framing of the problem and solution taxonomy (minimization vs. redistribution).*
5. [Arrakis: "The AMM Renaissance — Dynamic Fees and MEV Auctions"](https://arrakis.finance/blog/the-amm-renaissance-how-mev-auctions-and-dynamic-fees-prevent-lvr) — *"Angstrom seeks to mitigate MEV leakages... protecting LPs against CEX-DEX arb (LVR)."*
6. [am-AMM (Adams et al., FC25 preproceedings)](https://fc25.ifca.ai/preproceedings/183.pdf) — *peer-reviewed mechanism in the same design family; cite as evidence the literature is converging.*
7. [Sorella Angstrom Cantina security review](https://cantina.xyz/portfolio/2c7d45e3-0358-4254-8698-b4500fe7c6a9) — *signals Paradigm-backed v4 hook is shipping production.*
8. [CoW AMM](https://cow.fi/cow-amm) — *"the first MEV-capturing AMM, now live on Balancer" — proof that the design family is shipping on production EVM.*
9. [Helius: "Solana's Proprietary AMM Revolution"](https://www.helius.dev/blog/solanas-proprietary-amm-revolution) — *Solana-native framing; Lifinity-style proprietary AMMs already capturing real volume.*
10. [Pyth Network: "Introducing Pyth Lazer"](https://www.pyth.network/blog/introducing-pyth-lazer-launching-defi-into-real-time) — *sub-second updates ship 2026; the cadence assumption that makes `g(·)` tight is now real.*
11. [Pyth + MagicBlock perpetuals demo](https://legacy.pyth.network/blog/magicblock-and-lazer-powering-a-new-wave-of-speed-for-solana-defi) — *production case study of low-latency oracle consumption on Solana.*
12. [Coin Metrics: "Tokenized Equities and the Rise of xStocks on Solana"](https://coinmetrics.io/state-of-the-network/tokenized-equities-and-xstocks-on-solana/) — *headline volume numbers for the deck's "why xStocks, why now" slide.*
13. [Hashflow Solana expansion announcement](https://blog.hashflow.com/hashflow-solana-expansion-deeper-liquidity-more-tokens-9851fb4c4c5a) — *RFQ alternative; shows the design space is being actively populated.*
14. [Coinbureau: "Top Solana DEXs 2026"](https://coinbureau.com/analysis/top-solana-dex-platforms) — *current Solana DEX landscape snapshot for the competitive-context slide.*
15. [Volcano Exchange: "Liquidity — The Broken Promise of Tokenized Assets"](https://www.k.co.cr/2026/02/liquidity-pools-for-74-xstocks-on.html) (referenced in `market-research.md`; cited as the strongest public articulation of failure modes for tokenized-equity DEX liquidity).

### 2.5 Rough market sizing (numbers for the deck)

Reusable for the pitch — sourced and dated.

- **Solana CLMM/DLMM aggregate annualised volume:** $400–$700B at 10–30 bp blended fees → $400M–$2B/yr LP fees, similar-order LVR leakage. (`market-research.md:58-59`)
- **Solana DEX share of onchain spot:** 41% Q1 2026, exceeding ETH+L2 combined. (`market-research.md:51`, [Blockworks Advisory](https://www.blockworks.com/research))
- **xStock-specific Solana metrics:** $1.3B Q1 2026 tokenized volume (+164% QoQ); ~93% tokenized-stock market share; ~94% all-time tokenized-equity settlement on Solana; >$517M cumulative DEX volume; 57k+ holders. (`market-research.md:188-199`; [k.co.cr xStock list](https://www.k.co.cr/2026/02/xstocks-on-solana-complete-list-and.html))
- **Lifinity TVL benchmark:** $30M+ historical at peak ([DefiLlama lifinity-v2](https://defillama.com/protocol/lifinity-v2)). The *living-proof* that an oracle-priced AMM can hold material LP capital on Solana, even before the calibrated-band wedge.
- **HIP-3 / Trade.XYZ comparable:** $25B cumulative volume since Oct 2025, $87M annualised fees. *Not* an AMM but the closest "tokenized-equity-onchain" volume comparable for the macro slide. (`market-research.md:88-90`)
- **Conservative bottom-up model from `market-research.md:60-61`:** target 15% xStocks AMM volume by end-2027 → ~$5–10B annualised → at 25 bp fee × 50% LVR-recapture × 20% protocol take = **~$1.25–5M ARR** at base case. The pitch slide should reuse this number with the disclosure already in `market-research.md`.

---

## Phase 3 — Implementation plan starter (8 days)

### 3.1 Recommendation: pick *one* mechanism — band-bounded active range with band-breach surcharge

The candidates (from the prompt):

1. Band-conditioned dynamic fee
2. Band-conditioned spread / bin width
3. JIT-LP gating around band breach
4. Arb-rebate auction conditioned on band breach
5. Oracle-fallback guard / circuit breaker

Evaluation against four hackathon criteria:

| Criterion | (1) dyn fee | (2) band as range | (3) JIT-LP gate | (4) arb auction | (5) circuit breaker |
|---|---|---|---|---|---|
| 8-day buildable | ✓ | ✓ | – needs JIT-LP infra | ✗ needs auction infra | ✓ |
| Uses both edges (not just point) | partial | ✓ | partial | ✓ | partial |
| Uses receipt fields | ✓ | ✓ | – | – | – |
| Differentiated vs. Lifinity / Pyth-anchored | partial | **strong** | partial | strong | weak |
| Demo-able in 30 seconds | medium | **strong** | hard | hard | trivial |
| Pitch alignment with Paper 4's B2/B3 | partial | **strong** | – | matches B3 | weak |

**Choose mechanism (2) = "the band IS the active range," fused with mechanism (1) outside-band fee tier and a small dose of (5) as a defensive guard.** Concretely:

- **Inside band:** swaps that leave the pool's effective price within `[L_τ, U_τ]` execute at the standard fee `f_in` (e.g., 5 bps).
- **Outside band:** swaps that would push the effective price outside the band incur a surcharge `f_out(d, w)`, where `d` is the distance outside the band and `w` is the band width. Concretely: `f_out = f_in + α · clamp(d / w, 0, w_max)`. The surcharge revenue accrues to LPs.
- **Receipt:** every swap event emits the band state at execution (`lower`, `upper`, `claimed_served_bps`, `regime_code`, `publish_slot`). This is the on-chain analogue of Paper 1's calibration receipt — same audit-chain story, applied to AMM execution.
- **Guard (5):** if `now_ts - band.publish_ts > MAX_STALENESS` (e.g., 60s) the pool refuses to swap. Already-stable surface; one line of program logic.

**Why this is the strongest demo:**

- **Visual narrative:** during a halt or weekend, the band tightens (Paper 1 §V1b: 166–540 bps half-width depending on regime). The CPMM keeps quoting on stale Friday-close anchored reserves; the BandAMM's quoted range *moves with the band and tightens.* The receipt records that it did. This is the entire value prop in one chart.
- **Uses everything:** consumes `lower`, `upper`, `claimed_served_bps`, `regime_code`, `publish_ts` — none of those are wasted, none of them are point-only.
- **Matches Paper 4 §6.2:** the Plugin spec is exactly "standard-fee band + scaled-fee tier outside." This isn't a hackathon-special; it *is* B2 minus the BAM auction layer (which is the post-2026 horizon and out of 8-day scope).
- **Differentiated vs. Lifinity:** Lifinity quotes `Pyth.point + internal spread`. Soothsayer quotes `[L_τ, U_τ]` directly with empirical-coverage receipts. The talking point: "Lifinity guesses the spread; we publish the calibration."

**Drop the auction (mechanism 4) for the hackathon.** It's the right academic target for Paper 4's `g(·)` and the right production target post-BAM-Plugin-SDK, but neither the auction primitive nor the BAM Plugin attestation surface are 8-day-shippable; faking either with a centralised sequencer hurts the pitch's audit-chain story.

### 3.2 Smallest reasonable Solana program scaffold

Recommendation: **build a single new Anchor program from scratch — `programs/soothsayer-band-amm-program`** — modelled on Meteora's single-active-bin pattern, *not* a Whirlpools fork. Forking Whirlpools is heavy: tick-array account creation/management is most of the LOC and gives the AMM nothing the band already provides. A single-active-range pool collapses tick crossing into a band-update event.

**Sketch:**

- `BandAmmPool` PDA seeded `[b"band_amm_pool", base_mint, quote_mint]`. Holds `(reserves_base, reserves_quote, lp_supply, fee_bps_in, fee_alpha_out, fee_max_out, max_band_staleness_secs, soothsayer_price_pda)`.
- `LpPosition` PDA per provider (or use an LP mint; an LP mint is simpler and Jupiter-routing-friendly).
- Instructions:
  - `initialize_pool(base_mint, quote_mint, soothsayer_price_pda, fee_params)`.
  - `deposit(amount_base, amount_quote)` — accepts both legs at the band's current point ratio; mints LP tokens.
  - `withdraw(lp_amount)` — burns LP, returns prorata reserves.
  - `swap(amount_in, min_amount_out, side)` — reads the soothsayer `PriceUpdate` PDA via account loading, decodes via `soothsayer-consumer::decode_price_update`, validates invariants + staleness, computes effective post-swap price, applies fee tier (in/out), executes SPL token transfers, emits `Swap` event with full receipt.
  - `set_paused(paused: bool)` — authority emergency stop.
- **Cross-program data flow:** the AMM does *not* CPI the oracle program; it reads the `PriceUpdate` PDA as a regular account (already the soothsayer-consumer pattern). Zero new dependencies on the oracle program crate.
- **Token program:** start with classic SPL Token. Token-2022 support is a v2 if any xStock SPL ends up requiring transfer hooks (Backed currently mints classic SPLs).

**Reference materials:**
- [solana-developers/program-examples token-swap](https://github.com/solana-developers/program-examples/blob/main/tokens/token-swap/README.md) — minimal AMM scaffold to crib structure from.
- [jup-ag/jupiter-amm-interface](https://github.com/jup-ag/jupiter-amm-interface) — the trait to implement (off-chain, in a separate crate) for Jupiter routing once the program is live.
- [orca-so/whirlpools tick math](https://github.com/orca-so/whirlpools/blob/main/programs/whirlpool/src/math/tick_math.rs) — reference for fixed-point sqrt-price math if the BandAMM uses CLMM-style x*y=k semantics inside the band.

**Estimated scope:** ~600–900 lines of Rust + Anchor; ~300 lines of tests; ~200 lines of TypeScript devnet harness.

### 3.3 On-chain vs. off-chain split

| Layer | Where | Why |
|---|---|---|
| Band publishing (price + receipt) | On-chain — already shipped in `soothsayer-oracle-program` | The audit-chain story requires the band to be on-chain. Done. |
| Band consumption + fee-tier decision | **On-chain — new BandAMM program** | Must run inside the swap atomicity boundary; off-chain decisioning can't sign the receipt. |
| Pool reserves + LP accounting | On-chain | Standard AMM. |
| Publisher loop driving `PriceUpdate` updates | Off-chain — already shipped in `soothsayer-publisher` | Devnet path live. **Action item:** confirm publisher cadence ≤ 30s and is running through demo window. |
| Counterfactual replay (LP-economics chart) | Off-chain — Python notebook | Hackathon pitch artefact; not on-chain. |
| Jupiter routing wire-up | Off-chain — `jupiter-amm-interface` adapter crate | Discoverability post-deploy. |
| Demo client (web UI or CLI) | Off-chain — minimal CLI sufficient | Demo, not product. |

The on-chain program is small *because* the audit-chain primitive is the existing on-chain band. The AMM's job is to honour the band, not to recompute it.

### 3.4 Day-by-day sequencing (8 days)

Realistic scoping; each day has cut lines (§3.6).

| Day | Goal | Output |
|-----|------|--------|
| 1 | Scaffold `programs/soothsayer-band-amm-program`. Wire `soothsayer-consumer` import. Stub `initialize_pool`, `deposit`, `withdraw`, `swap`. | Compiles + Anchor IDL emits. |
| 2 | Implement `swap` math: post-swap effective-price calc, in-band vs. out-of-band branch, `f_out(d, w)` schedule, SPL transfers. | Unit tests pass on a stylized pool with mocked `PriceUpdate`. |
| 3 | Receipt event emission; staleness guard; pause IX; integration tests against a real `PriceUpdate` PDA on local-validator. | Localnet end-to-end swap with real band PDA. |
| 4 | Devnet deploy; SPYx-USDC + QQQx-USDC test pools (or test mints if xStock devnet mints unavailable — see §3.5 R3); seed liquidity. | Devnet swaps confirmed; receipts visible on explorer. |
| 5 | Off-chain counterfactual notebook: replay weekend window from the existing Soothsayer panel under (a) CPMM baseline, (b) BandAMM mechanism. Output LP-economics delta + receipt log. | One chart that lands the pitch. |
| 6 | Pitch deck (slide A — the LVR problem, slide B — the band as the missing input, slide C — the BandAMM in 30s, slide D — counterfactual chart, slide E — Paper 1 + Paper 4 + product stack). Cribbed from `docs/pitch_deck_content.md` + `market-research.md`. | Deck + pitch script. |
| 7 | Demo recording (devnet swap during simulated halt; show the band tighten, the fee tier flip, the receipt update). README. Jupiter adapter scaffolding (off-chain). | Submission package. |
| 8 | Polish, buffer, submission to Colosseum. | Submitted. |

### 3.5 Hardest unknowns / risks for the 8-day window

**R1 — Publisher cadence + devnet publisher health.**
The on-chain `min_publish_interval_secs` defaults to 30s (`programs/soothsayer-oracle-program/src/lib.rs:42`). The demo needs the publisher loop running continuously through the demo window. *Mitigation:* confirm the publisher launchd plist (or equivalent) is active on the dev machine; manual trigger script as backup. *Cut line if it slips:* mock the band PDA with a manually-pumped pubkey and disclose in the demo voiceover.

**R2 — xStock SPL availability on devnet.**
Backed mints are mainnet-only. The hackathon devnet pool will likely use placeholder mints (`SPYx_test`, `QQQx_test`) seeded by the demo authority. *Mitigation:* honest framing — "the demo runs against placeholder SPL mints with the band feed pulled live from the same Soothsayer publisher that would drive mainnet." Show the on-chain receipt links in addition. *Cut line if it slips:* drop to one demo pool (SPY-only).

**R3 — Counterfactual fidelity.**
Paper 4's empirical foundation requires `clmm_pool_state.v1` + `dlmm_pool_state.v1` + `jito_bundle_tape.v1` (forward-only, just landing in scryer item 51). For the hackathon those aren't ready. The counterfactual must use the *daily/intraday-1m underlier reference* (`yahoo/equities_daily` + `cme/intraday_1m` already live) plus Soothsayer's existing weekend-tape replay — a stylized LP-economics number, not a slot-resolution receipt. *Mitigation:* disclose explicitly in the deck and in the README; frame the hackathon as "mechanism + calibration receipt shipped — empirical bound is post-grant Paper 4 work." *Cut line if it slips:* drop the counterfactual entirely; lean on the visual narrative + Paper 1's existing 12-year evidence.

**R4 — Pitch story without an empirical receipt yet.**
Paper 4 explicitly says the moat IS the empirical receipt and the moat is data-pipeline-bound (`plan.md:291`). The hackathon pitch leans on the *mechanism + Soothsayer's existing Paper-1-grade calibration receipt*, not on Paper 4's future LVR measurement. The deck must be honest about this — the calibration receipt is shipped, the LVR-recovery receipt is the ~6-month forward-tape-bound deliverable. *Mitigation:* this is `feedback_publication_depth.md` discipline; do not overclaim. The honest framing is also the strongest framing — Paper 1's evidence is real now, Paper 4's empirical receipt is pre-registered + clock-running.

**R5 — Single-active-range vs. CPMM sticker shock.**
LPs accustomed to CPMM may bounce off a "the AMM only quotes inside the band" framing. *Mitigation:* the surcharge fee tier (mechanism 1) outside the band means the AMM still quotes — just at a higher fee that compensates LPs for the band-breach risk. The narrative is "your fees adapt to your uncertainty, instead of being a flat 30 bps regardless of regime." This is the same framing that worked for `feedback_phase_commits.md`-style "tighter when conservative, wider when uncertain."

### 3.6 Cut lines if scope slips

In priority order — drop highest items first:

1. **Drop Jupiter adapter** — defer post-hackathon. Distribution waits.
2. **Drop the off-chain counterfactual** — fall back to Paper 1's existing weekend-tape evidence + the live devnet receipt as the only artefacts. Hurts the deck but doesn't kill the demo.
3. **Drop `withdraw_liquidity`** — ship deposit-only; LPs locked for the demo period. Two-instruction program.
4. **Drop the band-breach surcharge tier** — ship band-bounded quote only; the AMM refuses to quote outside the band, returns a clear error. Pure mechanism (2). Even simpler narrative; arguably tighter.
5. **Drop the new program entirely** — ship a *Plugin-style* off-chain client that consumes the existing `soothsayer-router` PDA and quotes via a relay-mints test pool. Last-resort fallback; loses the on-chain story.

If R1 (publisher) or R2 (devnet mints) can't be resolved, escalate to cut line 5 by Day 4 — no point shipping a program with no devnet demo path.

### 3.7 What's *not* in this plan (deliberately)

- **No new scryer fetcher** for the hackathon. The demo data is the existing Soothsayer panel + `cme/intraday_1m`; nothing new is fetched outside scryer (CLAUDE.md hard rule §1).
- **No `g(·)` derivation** — that's Paper 4 Phase B. The hackathon ships the mechanism; the bound is post-grant.
- **No production audit / formal verification** — devnet MVP only. README must say so.
- **No Token-2022 transfer-hook handling** — start with classic SPL; Token-2022 is a v2 if Backed migrates xStock mints.
- **No multi-pool routing logic** — one pool per (base, USDC) pair; no cross-pool path discovery.
- **No oracle-update CPI** — the AMM is a pure consumer of the existing on-chain `PriceUpdate` PDA; no upstream dependency on the oracle program crate.

---

## Cross-references

- `reports/paper4_oracle_conditioned_amm/plan.md` — academic plan; B2 mechanism is the production target this hackathon MVP is the minimal implementation of.
- `reports/paper4_oracle_conditioned_amm/market-research.md` — Layer-1 (band-AMM) market sizing + LVR cite block; pitch-deck-grade.
- `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md` — pipelines that, when they ship, give Paper 4 its empirical receipt; *not* on the hackathon critical path but on the post-hackathon clock.
- `docs/product-stack.md` — the four-layer stack this AMM is the foundation of (band-AMM → band-perp → band-options → settlement).
- `docs/product-spec.md` — the band itself (Layer 0); the consumer-facing projections section §"Consumer-facing projections" lists the surfaces this AMM is the AMM-shaped instance of.
- `programs/soothsayer-oracle-program/src/state.rs:75-119` — the `PriceUpdate` PDA layout the BandAMM reads.
- `crates/soothsayer-consumer/src/lib.rs:97-150` — the `PriceBand` decoder + invariant validator the BandAMM imports.
- `crates/soothsayer-demo-kamino/src/lib.rs` — the consumer-pattern reference; the BandAMM mirrors this shape.
