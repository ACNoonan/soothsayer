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

## Dual-profile methodology family (post-M5)

Different consumers want different properties from the band. Layer 1 (Band-AMM) cares about *common-mode responsiveness* — calm weekend → tighter LP region → more throughput; shock weekend → wider band → more LVR protection. Lending consumers (Kamino, MarginFi) and per-asset products (Layer 2 perp, Layer 3 single-underlier options) care about *per-asset width re-allocation* — SPYx tighter than MSTRx, with a calibrated receipt that reserve-buffer config can read directly. M6 leads (`reports/v1b_m6a_common_mode_partial_out.md`, `reports/v1b_m6b_per_symbol_class_mondrian.md`, `reports/v1b_m6c_combined.md`) confirm both axes deliver real width reductions over M5 at matched coverage on the OOS 2023+ panel — and that they are *mostly orthogonal* (~0.87 stacking efficiency at τ ∈ {0.85, 0.95}).

The post-M5 rollout therefore runs **two profiles in parallel under one methodology family**, sharing the factor-adjusted point, regime classifier, scryer data spine, and `PriceUpdate` Borsh wire format. Profiles differ only in (a) score residualisation and (b) conformal cell partition. See `M6_REFACTOR.md` for the staged rollout and `reports/methodology_history.md` for the dated decision log.

| Track | Methodology | Cell axis | Score | Best for | Deploy state |
|---|---|---|---|---|---|
| **Lending-track** | M6b2 | symbol_class (6 cells) | `\|r\|` | per-asset products: lending, perp, single-underlier options/vaults | shipping next per `M6_REFACTOR.md` Phase A |
| **AMM-track** | M6a | regime (3 cells) | `\|r − β·r̄_w\|` | universe-aggregate products: Band-AMM, portfolio vaults, common-mode-aware indexes | gated on r̄_w forward predictor; see `VALIDATION_BACKLOG.md` W8 |

Both tracks publish under `forecaster_code = 2` (`mondrian`); the `profile_code` byte in the receipt distinguishes (`profile_code = 1` Lending, `profile_code = 2` AMM). Same Borsh layout, byte-identical on the rest of the wire.

### Per-layer track assignment

| Stack item | Track | Why |
|---|---|---|
| **Layer 0 — Oracle (the band itself)** | publishes both | Layer 0 *is* the methodology. Two parallel publisher daemons; two parallel parquet venues. |
| **Layer 1 — Band-AMM (spot)** | **AMM-track** | LP-region sizing is a universe-aggregate concern; common-mode responsiveness is the LVR-aware claim. |
| **Layer 2 — Band-perp** | **Lending-track** | Single-asset; mark = band midpoint, liquidation buffer = band edges; τ=0.99 safety margin. |
| **Layer 3 — Band-options (single-underlier)** | **Lending-track** | Implied vol from per-asset band width. |
| **Layer 3 — Band-vaults (portfolio)** | **AMM-track** | Sells/buys band-edge volatility across the universe → common-mode responsive. |
| **Layer 4 — Settlement / index licensing** | both, licensed separately | Per-asset licensees → Lending-track; common-mode-signal licensees → AMM-track. Pricing-tier differentiation. |
| Lending integration (Kamino, Paper 3) | **Lending-track** | Per-class half-width feeds per-reserve buffer config directly. |
| MarginFi integration | **Lending-track** + W4 asymmetric layer | Per-Bank consumer; W4 asymmetric quantile pair maps to assets-vs-liabilities P-conf/P+conf. |
| Calibrated event stream (v1 product, gated on Paper 3) | both | Per-asset thresholds → Lending; portfolio thresholds → AMM. |
| Decision SDK (v2 product, 2027) | both | `recommend(symbol, tau, cost_curve, profile=AMM \| Lending)`. |
| Policy mapping (Safe / Caution / Liquidate) | **Lending-track** | Per-reserve. |
| Layer 0 router (open-hours upstream aggregation) | profile-agnostic | Layer 0 infra — routes upstream price, doesn't itself produce a band. |
| Pyth equity poster, Chainlink Streams relay program | profile-agnostic | Layer 0 infra. |
| xStock universe / Backed corp-actions integration | profile-agnostic | Universe definition. |
| Path-aware truth labelling (Paper 4) | profile-aware *validator* | Validates either profile against consumer-experienced prices. |
| Counterfactual replay engine (Paper 4) | profile-aware *comparator* | A/B-tests profiles for any future product. |
| Bundle-attribution labels (Paper 4) | profile-aware analytics | MEV/Jito attribution differs by profile. |
| Pool-state reconstructor (Paper 4) | profile-agnostic | Infrastructure. |
| Reserve-buffer evaluation (Paper 3 active work) | **Lending-track** | Per-class. |
| Dynamic-bonus / `D_repaid` fit (Paper 3 active work) | **Lending-track** | Per-asset elasticity. |
| Cross-protocol propagation (MarginFi cascade) | **Lending-track** | Both protocols are lending-style. |
| CEX in-market reference tape (scryer item 51) | profile-agnostic | Truth labeller input. |
| BAM validator-client labelling (scryer item 51) | profile-agnostic | Settlement-determinism analysis. |

Of ~22 stack items, 8 map to AMM-track, 8 to Lending-track, 4 to both, 8 are profile-agnostic infrastructure. No item is left without a clean assignment — the two-profile partition does real work across the planned stack.

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
