# Soothsayer product stack — what each layer is, what it consumes, what it does not

**Status:** living doc; aligned with `reports/methodology_history.md` §0 product progression and `reports/paper4_oracle_conditioned_amm/plan.md` §16.
**Audience:** internal — for strategic clarity on what the firm builds vs. what it licenses out vs. what it explicitly declines to build.

## The one-line frame

Soothsayer publishes a *calibration-transparent fair-value band* as the foundational primitive (the oracle layer). Every product layer below is a DeFi primitive whose existing implementations leak value because their oracle is point-only. The product stack is the set of primitives that need *uncertainty* as an input to price correctly, in priority order of how directly they consume the band and how clearly they have a defensible edge.

This is not a roadmap commitment. It is a **direction-of-travel**, useful for deciding which scryer pipelines, research artefacts, and engineering scaffolds to invest in now so they are reusable across multiple downstream products. Only Layer 1 has a paper attached at the time of writing (Paper 4); subsequent layers are gated on Layer 1 landing.

## The four layers

| # | Layer | What the band does | Paper anchor | Build-status |
|---|---|---|---|---|
| 0 | **Oracle** — calibration-transparent fair-value band | The band itself: $[L_\tau, U_\tau]$ with empirical coverage receipts | Paper 1 (live; OOS Kupiec + Christoffersen pass at $\tau \in \{0.68, 0.85, 0.95\}$) | **Live** — devnet `soothsayer-router` deployed 2026-04-29; Phase 1 mainnet pending |
| 1 | **Band-AMM (spot)** — calibration-conditioned CLMM/DLMM | Active range bounded by served band; band-edge fees absorb LVR; outside-band auction routes proceeds to LPs | **Paper 4** (plan locked; Phase A pipeline in flight) | Pre-research |
| 2 | **Band-perp** — synthetic perpetual on tokenized RWAs | Mark = band midpoint; liquidation buffer = band edges; funding spikes when band widens during halts | Future paper (gated on L1) | Concept only |
| 3 | **Band-options / band-vaults** — derivative + structured products | Calibrated implied vol derives directly from band width; vaults sell/buy band-edge volatility | Future paper (gated on L1 + L2) | Concept only |
| 4 | **Settlement / index licensing** — reference-rate provider | Calibrated band feed consumed by third-party perp DEXes, prediction markets, RFQ venues | Not a paper — productisation of L0 | Implied by router on-chain publish |

Each row consumes the calibrated band. Each row also depends on the rows above it being live or imminent — band-perp needs a band-AMM to hedge against; band-options need both spot and perp depth; settlement licensing is dispositionally orthogonal to the AMM stack but practically gated on the band being on-chain in production.

## What each layer is *not*, and what we do not build

- **Layer 0 (Oracle).** Not a price predictor. Soothsayer makes no claim to minimum-variance forecasting; the contribution is the calibration receipt, not the point estimate. We do not compete with Pyth on aggregation latency or with Chainlink on integration breadth.
- **Layer 1 (Band-AMM).** Not a generic spot DEX. The product is the band-aware pool, not a routing layer. We do not compete with Jupiter, Raydium routing, or 1inch-style aggregators.
- **Layer 2 (Band-perp).** Not a perp DEX competing with Drift on liquidity or UX. The product is *halt-aware* perp mark/liquidation logic specifically for tokenized equities. If the team is not Drift, scope is single-asset class, not all perps.
- **Layer 3 (Band-options/vaults).** Not a Solana options venue from scratch. Either we layer on Zeta / a future RWA-options venue, or we ship vaults that operate against our own AMM/perp depth.
- **Layer 4 (Settlement / index).** Not a competing oracle network. Pyth's business model lives here; we license a band-feed *layer* on top of an existing oracle distribution rail rather than building a new publisher network.
- **Lending market.** Out of stack. Kamino exists, has TVL, and is the natural Paper 3 consumer. We license the oracle to Kamino; we do not build a competing borrow/lend protocol.
- **Stablecoin / LST AMMs.** Out of stack — fails the methodology scope filter (`docs/methodology_scope.md`).
- **An "everything app" bundling the above.** Each product needs its own LP-incentive design and risk parameters. Bundling early hides which one is actually working and dilutes the calibration-transparency story across surfaces it does not improve.

## Pipeline reuse across layers

The scryer pipelines required to validate Layer 1 are the same pipelines required to evaluate Layers 2–4 as products. Standing them up now is therefore both a paper deliverable and a product-decision deliverable. The full priority order lives in `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md`; the headline list:

1. **Per-slot CLMM/DLMM pool state** (Orca, Raydium, Meteora) — feeds Layer 1 directly; needed by Layers 2/3 as the hedging-venue depth ground truth.
2. **Jito bundle parser with RWA-pool attribution** — feeds Layer 1's E3 bundle-conditional analysis; needed by Layers 2/3 to model adversarial flow at halt boundaries.
3. **CEX in-market reference tape** — needed by Layer 1's truth labeller; needed by Layer 2's funding-rate calibration; needed by Layer 4 as the comparable for licensing-grade band feeds.
4. **BAM validator-client labelling per slot** — needed by Layer 1's mechanism counterfactual; needed by Layers 2/4 to reason about settlement-determinism guarantees.

## See also

- `reports/methodology_history.md` §0 — current product progression (v0 router live, v1 event stream gated on Paper 3, v2 decision SDK 2027).
- `reports/paper4_oracle_conditioned_amm/plan.md` — Paper 4 plan + §5.5 scope filter + §16 product-stack pointer back to this doc.
- `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md` — the data pipeline priority order this doc references.
- `docs/methodology_scope.md` — which RWA classes the underlying methodology applies to (the same scope filter that gates Layer 1).
- `docs/product-spec.md` — Option C product specification from the oracle layer's perspective (Layer 0 detail).
