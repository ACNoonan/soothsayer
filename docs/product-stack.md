# Soothsayer Stack — strategic architecture for the band-AMM and the products it underwrites

**Status:** living doc; aligned with `reports/methodology_history.md` §0 product progression and `reports/paper4_oracle_conditioned_amm/`.
**Audience:** internal — strategic clarity on what the firm builds, in what sequence, and the moat at each layer.

## 1. Objective

**Soothsayer Stack** is a calibrated, multi-cadence interval-oracle for tokenized RWAs on Solana, plus the family of AMM, auction, and audit primitives that consume it natively.

Headline product positioning:

> **The first Solana AMM that's calibrated to be open when the underlying market is closed.**

Three structural claims:

1. **Closed-market RWAs are the wedge.** xStock LVR concentrates in halts, weekends, earnings, and gap-opens — exactly when the band widens to reflect uncertainty. Pyth-anchored AMMs (Lifinity) and proprietary prop AMMs (HumidiFi, Lifinity v3) optimise for fast-tape calm regimes and have nothing structurally novel to say about closed-market quoting.
2. **The band primitive is the foundation.** Paper 1 establishes a calibration-transparent fair-value band with audited coverage (Kupiec + Christoffersen, OOS $\tau \in \{0.68, 0.85, 0.95, 0.99\}$). No other Solana oracle publishes interval calibration at this rigour; no production AMM on any chain consumes one.
3. **Each layer above the band has a structural moat tied to the calibration receipt.** Even when individual mechanics (DLMM bins, Jito bundle attribution, JIT-LP) are commoditised, the band is the truth signal that makes them honest — and the per-swap receipt is the institutional risk disclosure no other Solana AMM offers.

This is not a roadmap commitment. It is a **direction-of-travel** for deciding which scryer pipelines, research artefacts, and engineering scaffolds to invest in now so they are reusable across multiple downstream products.

## 2. Two axes of progression

The stack progresses along two orthogonal axes:

- **Product axis (§3)** — which financial primitives we ship over time: AMM → Perp → Options → Settlement.
- **Architecture axis (§4)** — which internal layers compose the band-AMM specifically: Oracle → Core → Auction → Active → Audit → Distribution.

Product axis is the long-arc roadmap (years). Architecture axis is the next 18 months of band-AMM build-out.

## 3. Product axis — four primitives consuming the band

| # | Layer | What the band does | Paper anchor | Build-status |
|---|---|---|---|---|
| 0 | **Oracle** — calibration-transparent fair-value band | The band itself: $[L_\tau, U_\tau]$ with empirical coverage receipts | Paper 1 (live; OOS Kupiec + Christoffersen pass at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ under v2 / M5; M6b2 in flight) | **Live** — devnet `soothsayer-router` deployed 2026-04-29; Phase 1 mainnet pending |
| 1 | **Band-AMM (spot)** — calibration-conditioned pool family | Active range bounded by served band; band-edge fees absorb LVR; outside-band auction routes proceeds to LPs | **Paper 4** (plan locked; Phase A pipeline in flight) | L1.0 (single-active-range) on devnet 2026-05-02; hackathon submission 2026-05-10 |
| 2 | **Band-perp** — synthetic perpetual on tokenized RWAs | Mark = band midpoint; liquidation buffer = band edges; funding spikes when band widens during halts | Future paper (gated on Layer 1) | Concept only |
| 3 | **Band-options / band-vaults** — derivative + structured products | Calibrated implied vol derives directly from band width; vaults sell/buy band-edge volatility | Future paper (gated on Layers 1 + 2) | Concept only |
| 4 | **Settlement / index licensing** — reference-rate provider | Calibrated band feed consumed by third-party perp DEXes, prediction markets, RFQ venues | Not a paper — productisation of Layer 0 | Implied by router on-chain publish |

Each row consumes the calibrated band. Each row also depends on the rows above it being live or imminent — band-perp needs a band-AMM to hedge against; band-options need both spot and perp depth; settlement licensing is dispositionally orthogonal to the AMM stack but practically gated on the band being on-chain in production.

## 4. Architecture axis — the band-AMM internal stack

Within product Layer 1, the band-AMM decomposes into six internal layers (numbered L1–L6 to disambiguate from the product axis above). Each is independently shippable; the hackathon (deadline 2026-05-10) ships L1.0 + L2.0 + L5.0; the rest is the post-hackathon roadmap.

| # | Internal layer | What it is | Status / ETA |
|---|---|---|---|
| **L1** | **Multi-cadence oracle** | Friday-close (M5 live, M6b2 in flight) + Sunday-Globex republish (W8b) + intraday basis-risk band (Paper 5) + event republish, all per-class Mondrian, with F_tok feedback once $\geq 150$ weekends accumulate | L1.0 live; L1.1 ~3-4 wks post-scryer Sunday-fetcher; L1.2 6-9 mo (Paper 5) |
| **L2** | **Band-AMM core** | Single-active-range pool today → DLMM-style bin curve keyed to band edges; in/out-of-band asymmetric fees; halt-mode refuse-to-trade; bundle-aware receipts; Jupiter-quoted | L2.0 live (`programs/soothsayer-band-amm-program/`); L2.1 (DLMM bins) ~2 mo; L2.2 (Jupiter integration) ~1 mo |
| **L3** | **Auction layer** | Jito-restaking AVS for bundle attribution; arb rents rebated to LPs; receipts include `bundle_id` + attributed profit. The Solana-native equivalent of Sorella Angstrom's validator-staked auction; substitutes for waiting on BAM Plugin SDK (2027+) | 12-18 mo, gated on validator BD (Jito relationship) |
| **L4** | **Active layer** | Phoenix-CLOB fallback for halt-mode (auto-route when band > halt-threshold); JIT-LP integration for sophisticated MMs (Drift v3 hybrid pattern); POL bootstrapping pool seeded by treasury (Lifinity precedent) | 6-12 mo, sequencing flexible |
| **L5** | **Audit + LP UI** | Per-receipt verifier (paste swap signature → returns band, source publisher, calibration p-values); rolling Kupiec / Christoffersen dashboard; per-pool LP-return audit (in-band fee yield vs out-of-band penalty yield vs L3 bundle rebates); institutional deposit UI with disclosed risk profile | L5.0 hackathon (verifier MVP); L5.1+ ongoing |
| **L6** | **Distribution** | Jupiter quote source; RFQ integration for size; cross-pool routing (xStock pair → underlying ETF wrapper) | Concurrent with L2.2 |

### What each internal layer borrows from the Solana frontier

| Frontier project | What we crib | Where it lands |
|---|---|---|
| **Meteora DLMM** | Discrete-bin architecture, zero in-bin slippage | L2.1 (one wide bin = `[lo, hi]`; narrow bins outside) |
| **Phoenix** | CLOB venue for halt-mode fallback | L4 |
| **Jupiter** | Aggregator interface (`jupiter-amm-interface`); RFQ for size | L2.2, L6 |
| **Drift v3** | Hybrid passive/active/keeper architecture | L4 |
| **Lifinity** | Protocol-owned-liquidity bootstrapping pattern | L4 (we improve their oracle layer with the band) |
| **Jito** | Restaking AVS infrastructure; bundle data | L3 (attribution + rebate) |
| **Pyth Express Relay / BAM Plugin** | Auction-at-oracle design pattern | L3 reference; we ship Jito version first |
| **am-AMM / Sorella Angstrom (EVM)** | Auction mechanism design | L3 (port to Jito infra) |
| **Curve LLAMMA** | Bin-shaped liquidity-distribution math precedent | L2.1 |
| **HumidiFi / Lifinity v3** | Competitive benchmark for normal-flow quote | We don't match their latency; we win on auditability |

### What we explicitly don't try to do

- **Not a quote-latency war with prop AMMs.** HumidiFi at 143 CU/update is a different game; we don't try to match. We win on auditability and disclosed risk.
- **Not a 24/7 oracle-aware AMM.** The band's value concentrates in closed-market windows; that's where we lead. Open-hours is a "solved enough" problem (Pyth + thin-fee CPMM); the band collapses to a tight ε-band intraday and the asymmetric-fee mechanic doesn't fire (see Paper 5 / L1.2 for the basis-risk-band path that does add intraday value, but it's a research arc, not a Layer-1 dependency).
- **Not auction-mode LVR recapture via Ethereum-style block-builder cooperation.** Sorella, Diamond, am-AMM, CoW assume a builder market Solana doesn't expose cleanly. On Solana we route through Jito-restaking instead, in L3.
- **Not a generic spot DEX.** The product is the band-conditioned pool, not a routing layer. Jupiter integration in L6 makes us a discoverable quote source, not a Jupiter competitor.
- **Not an everything-app bundling Layers 1–4.** Each product needs its own LP-incentive design and risk parameters. Bundling early hides which one is actually working and dilutes the calibration-transparency story across surfaces it does not improve.

## 5. Multi-cadence band publication (L1 detail)

The L1 band publisher is itself a multi-cadence system. Each cadence has its own conformal quantile fit and its own residual-distribution structure.

| Cadence | Trigger | Expected width @ τ=0.95 | Status |
|---|---|---|---|
| Friday-close | 16:00 ET Fri / pre-holiday | 280-560 bps per regime | **Live** (M5); M6b2 (per-class) -14% in flight |
| Sunday-Globex republish | 18:00 ET Sun (ES/NQ futures reopen) | likely 100-250 bps | **W8b** — engineering-gated on scryer Sunday-evening fetcher; ~3-4 wks once scryer item lands. R²(OOS) > 0.5 ex-ante. |
| Intraday basis-risk band | Pyth-cadence or vol-trigger during NYSE hours | likely 15-40 bps depending on regime | **Paper 5** — research arc, ~6-9 mo data accumulation. Calibrates the xStock-on-Solana vs underlying-on-NYSE basis residual. |
| Earnings / event republish | T-1 hour from `yahoo/earnings_dates` | Wider, regime-flagged | Future, low priority |

Receipts record the publishing cadence implicitly via `publish_ts` and `regime_code`; explicit `cadence_code` is a forward-compatible byte in the Borsh layout.

**W8 result (2026-05-03) and its implications.** The W8 ablation tested whether week-over-week residuals (`r̄_w`) carry predictable structure observable at Friday-close — they do not. R²(OOS) was negative across every macro-vol feature set and regularisation. The AMM-track methodology (`|r − β·r̄_w|` score, M6a) is therefore **parked indefinitely** until either (a) **W8b** (Sunday-Globex republish architecture, engineering-gated, the strongest near-term moat for the AMM specifically) or (b) **W8c** (F_tok-based predictor on accumulated `soothsayer_v5/tape` cross-section, data-gated, ~Q3-Q4 2026) opens.

This **does not block Layer-1 (Band-AMM) shipping**. The band-AMM consumes the **Lending-track band (M6b2 / M5)** today; AMM-track is a future width-tightening optimisation, not a launch dependency. The band primitive is calibrated; the AMM is shippable; W8b/W8c make the underlying band tighter without changing the AMM mechanics.

**F_tok feedback loop.** Once $\geq 150$ weekends of `soothsayer_v5/tape` accumulate, the on-chain xStock cross-section becomes a near-perfect proxy for `r̄_w` (W8c). The AMM's own activity then feeds back into the next calibration — a self-improving primitive that no competitor without our oracle stack can replicate.

## 6. Dual-profile methodology (post-M5)

Different consumers want different properties from the band. The band-AMM cares about *common-mode responsiveness* — calm weekend → tighter LP region → more throughput; shock weekend → wider band → more LVR protection. Lending consumers (Kamino, MarginFi) and per-asset products (Layer-2 perp, Layer-3 single-underlier options) care about *per-asset width re-allocation* — SPYx tighter than MSTRx, with a calibrated receipt that reserve-buffer config can read directly. M6 leads (`reports/v1b_m6a_common_mode_partial_out.md`, `reports/v1b_m6b_per_symbol_class_mondrian.md`, `reports/v1b_m6c_combined.md`) confirm both axes deliver real width reductions over M5 at matched coverage on the OOS 2023+ panel — and that they are *mostly orthogonal* (~0.87 stacking efficiency at $\tau \in \{0.85, 0.95\}$).

The post-M5 rollout therefore runs **two profiles in parallel under one methodology family**, sharing the factor-adjusted point, regime classifier, scryer data spine, and `PriceUpdate` Borsh wire format. Profiles differ only in (a) score residualisation and (b) conformal cell partition. See `M6_REFACTOR.md` for the staged rollout and `reports/methodology_history.md` for the dated decision log.

| Track | Methodology | Cell axis | Score | Best for | Deploy state |
|---|---|---|---|---|---|
| **Lending-track** | M6b2 | symbol_class (6 cells) | $\|r\|$ | per-asset products: lending, perp, single-underlier options/vaults; **Band-AMM today** | shipping next per `M6_REFACTOR.md` Phase A |
| **AMM-track** | M6a | regime (3 cells) | $\|r − β·\bar r_w\|$ | universe-aggregate products: portfolio vaults, common-mode-aware indexes; future Band-AMM width optimisation | parked on W8 result; reopens on W8b (Sunday-Globex republish) or W8c (F_tok signal accumulation) |

Both tracks publish under `forecaster_code = 2` (`mondrian`); the `profile_code` byte in the receipt distinguishes (`profile_code = 1` Lending, `profile_code = 2` AMM). Same Borsh layout, byte-identical on the rest of the wire.

### Per-layer track assignment

| Stack item | Track | Why |
|---|---|---|
| **Layer 0 — Oracle (the band itself)** | publishes both | Layer 0 *is* the methodology. Two parallel publisher daemons; two parallel parquet venues. |
| **Layer 1 — Band-AMM (spot)** | **Lending-track today; AMM-track future** | Lending-track (M6b2) ships now and powers L2.0. AMM-track (M6a) reopens on W8b/W8c and provides further width-tightening for L2.1+. |
| **Layer 2 — Band-perp** | **Lending-track** | Single-asset; mark = band midpoint, liquidation buffer = band edges; τ=0.99 safety margin. |
| **Layer 3 — Band-options (single-underlier)** | **Lending-track** | Implied vol from per-asset band width. |
| **Layer 3 — Band-vaults (portfolio)** | **AMM-track (when reopened)** | Sells/buys band-edge volatility across the universe → common-mode responsive. |
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

## 7. What each layer is *not*, and what we do not build

- **Layer 0 (Oracle).** Not a price predictor. Soothsayer makes no claim to minimum-variance forecasting; the contribution is the calibration receipt, not the point estimate. We do not compete with Pyth on aggregation latency or with Chainlink on integration breadth.
- **Layer 1 (Band-AMM).** Not a generic spot DEX. The product is the band-conditioned pool, not a routing layer. We do not compete with Jupiter, Raydium routing, or 1inch-style aggregators. We also do not try to out-quote prop AMMs (HumidiFi, Lifinity v3) on inside-the-band spread tightness — we win on auditability and on closed-market quoting.
- **Layer 2 (Band-perp).** Not a perp DEX competing with Drift on liquidity or UX. The product is *halt-aware* perp mark/liquidation logic specifically for tokenized equities. If the team is not Drift, scope is single-asset class, not all perps.
- **Layer 3 (Band-options/vaults).** Not a Solana options venue from scratch. Either we layer on Zeta / a future RWA-options venue, or we ship vaults that operate against our own AMM/perp depth.
- **Layer 4 (Settlement / index).** Not a competing oracle network. Pyth's business model lives here; we license a band-feed *layer* on top of an existing oracle distribution rail rather than building a new publisher network.
- **Lending market.** Out of stack. Kamino exists, has TVL, and is the natural Paper 3 consumer. We license the oracle to Kamino; we do not build a competing borrow/lend protocol.
- **Stablecoin / LST AMMs.** Out of stack — fails the methodology scope filter (`docs/methodology_scope.md`).

## 8. Pipeline reuse across layers

The scryer pipelines required to validate Layer 1 are the same pipelines required to evaluate Layers 2–4 as products *and* the same pipelines that unlock the band-AMM internal layers L3 (auction) and L4 (active). Standing them up now is therefore both a paper deliverable and a product-decision deliverable. The full priority order lives in `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md`; the headline list:

1. **Per-slot CLMM/DLMM pool state** (Orca, Raydium, Meteora) — feeds Layer 1 directly; needed by Layers 2/3 as the hedging-venue depth ground truth; needed by L2.1 (DLMM bin design) as comparable.
2. **Jito bundle parser with RWA-pool attribution** — feeds Layer 1's E3 bundle-conditional analysis; needed by Layers 2/3 to model adversarial flow at halt boundaries; **load-bearing for L3 (auction layer)**.
3. **CEX in-market reference tape** — needed by Layer 1's truth labeller; needed by Layer 2's funding-rate calibration; needed by Layer 4 as the comparable for licensing-grade band feeds; **needed by L1.2 (Paper 5 intraday basis band) as truth signal**.
4. **BAM validator-client labelling per slot** — needed by Layer 1's mechanism counterfactual; needed by Layers 2/4 to reason about settlement-determinism guarantees.
5. **Sunday-evening Globex futures snapshot** — engineering-gated; unlocks **L1.1 (W8b Sunday republish)**.

## 9. Disclosure boundaries — what's open, what's closed, when each line moves

The Soothsayer Stack is built on the premise that **calibration math is open** (auditability is the credibility moat for institutional capital) and **operational risk parameters are closed** (operator discretion is where defensible book-management lives). This section pre-commits the boundary so future paper drafts, public-repo commits, and private-repo splits don't accidentally leak load-bearing decision logic — or, conversely, accidentally close primitives that need to stay open for the audit-chain story to hold.

### 9.1 The five-component split

| # | Component | Disclosure | Rationale |
|---|---|---|---|
| 1 | **Academic methodology** — Paper 1/4/5 math, Mondrian split-conformal architecture, factor adjustment, per-class cells, the 20-scalar deployment shape | **Open** — papers + reports + scripts; durable | Credibility moat. Copying gets math, not track record. Closing the math costs more than it costs a copier. |
| 2 | **Coverage receipts** — Kupiec / Christoffersen p-values per τ per regime per period; mean half-width; per-class disaggregation | **Open** — public dashboard (L5.0 hackathon → L5.1+ rolling); durable | Auditability *is* the value. Institutional disclosure layer; this is what an LP's risk team underwrites against. |
| 3 | **Trained parameter values at version $n$** — the 12 quantiles, 4 c(τ) bumps, 4 δ(τ) shifts in `mondrian_artefact_v2.parquet` and successors | **Versioned-open** — disclose v$n$ while operating v$n+1$ | We always operate one publication cycle ahead. Tax-code-style: rules are public, year-over-year recalibrations lag. |
| 4 | **AMM-internal risk scalars** — per-class fee multipliers, halt-mode width thresholds, JIT-LP gating rules, refuse-to-trade thresholds, weak-coverage class premia | **Closed** — operator discretion; observable on-chain only after `set_fee_params` execution, not pre-disclosed | Concern #2 (calibration-hole exploitation) lives here. The methodology paper says "calibration is weaker on HOOD/MSTR"; the AMM's *pricing response* to that disclosure is the operator's call. |
| 5 | **F_tok feedback function** — the function mapping on-chain xStock cross-section → next-period calibration, post-W8c (~Q4 2026) | **Closed** — internal | Structural moat. Inputs are public (the on-chain flow); the *function* converting flow to calibration is not. Creates path-dependence vs copiers who lack our deployed flow. |

### 9.2 Three operating principles

- **P1 — Open the math, version the parameters.** Methodology is publicly documented and auditable. Trained parameter values are versioned; v$n$ is the open reference, v$n+1$ is what we operate.
- **P2 — Open the calibration, close the operational risk parameters.** Paper 1 says "the band is calibrated to τ"; that's open. The AMM's specific per-class fee multipliers, halt-thresholds, and JIT-LP gates are operator decisions, observable on-chain only at execution time (in the swap receipt), not pre-disclosed.
- **P3 — Open the back-test, close the live adaptive signal.** F_tok feedback uses on-chain flow that's publicly observable, but the function mapping flow → calibration is closed.

### 9.3 What this is *not*

- **Not security through obscurity.** The closed components are *risk-management decisions and adaptive functions*, not safety-critical primitives. Smart-contract bytecode is on-chain and fully auditable; closure operates above the protocol layer. A failure of a closed component cannot harm consumers in a way an open one wouldn't.
- **Not deferred openness.** Closed components in rows 4 + 5 stay closed. P1's version lag is the only "delayed-open" element. P2 and P3 are durable.
- **Not a wall.** Auditability obligations can override closure on demand — a regulator, auditor, or counterparty with contractual disclosure rights can read closed components under NDA. The default is closed; the contract overrides.
- **Not absolute.** P3's F_tok closure is *additional friction*, not perfect opacity — a sufficiently sophisticated observer of public on-chain flow could in principle reverse-engineer parts of the function. Closure raises the cost of replication; it doesn't eliminate it. Complement to L3 / L6 integration moats, not a substitute.

### 9.4 Repo-split implications

The current `soothsayer` repo is public and stays public through the 2026-05-10 hackathon — the hackathon's value proposition depends on transparency, and there is nothing operationally sensitive in scope. Post-hackathon, a separate private repo (`soothsayer-internal` or similar) accumulates the closed operational layer on a measured cadence tied to product-layer launches.

**Trigger calendar:**

| Trigger | Migrates to / created in `soothsayer-internal` |
|---|---|
| **Post-hackathon (2026-05-11+)** | Per-class fee multiplier proposals; halt-threshold tuning notes; operator runbooks for the deployed pool; pre-disclosure draft parameters at v$n+1$; pitch / BD materials |
| **L2.1 — DLMM bin curve (~Q3 2026)** | Production bin-sizing logic and asymmetric fee-schedule tuning (math methodology stays public; specific values are operator discretion) |
| **L4 — POL pool launch (~Q4 2026)** | POL sizing logic; protocol-owned-liquidity treasury allocation; L5.1+ operator dashboards beyond the public auditability layer |
| **W8c / F_tok feedback (~Q4 2026)** | F_tok function implementation; the feedback-fit code; closed back-tests using F_tok signal; the internal v$n+1$ recalibrations downstream of F_tok |
| **L3 — Auction AVS launch (~Q4 2027)** | Validator BD materials; AVS slashing-parameter tuning; multisig operator config; rebate-distribution heuristics beyond the on-chain attribution module |

**What stays in `soothsayer` (public) durably:**

- All papers (1, 3, 4, 5) and `reports/methodology_history.md`.
- All calibration scripts that fit on public scryer data.
- Anchor programs (`soothsayer-oracle-program`, `soothsayer-router-program`, `soothsayer-band-amm-program`, future AVS contracts) — bytecode is on-chain regardless.
- The `soothsayer-consumer` decoder crate and consumer-pattern references (e.g., `soothsayer-demo-kamino`).
- Public coverage-receipt dashboard code (the L5.0 verifier webapp and successors).
- Versioned deployment artefacts at v$n$ once v$n+1$ is operating internally.
- All hackathon materials (deck, demo, README).

**What moves to `soothsayer-internal`:**

- Components in §9.1 rows 4 and 5 (AMM-internal risk scalars; F_tok feedback function).
- Operator runbooks, on-call documentation, monitoring config beyond the public auditability layer.
- Pre-disclosure draft parameters at v$n+1$.
- Validator BD, partner materials, institutional LP onboarding.
- Internal pricing models, forecasts, financial planning.

**The split is additive, not destructive.** No code currently in the public repo gets removed or relocated by the split — the private repo accumulates the operational layer as it materializes. CI, branch protection, and contributor access on `soothsayer-internal` should be tighter than `soothsayer` from inception.

### 9.5 What we re-evaluate quarterly

- Whether any component currently closed is structurally non-load-bearing and should be opened (test: would opening it cost us > X bps of LP economics, or > Y institutional LP rejections? If not, open it — closure has its own cost in trust).
- Whether the version-lag in P1 is the right cadence (default: ~1-2 quarters; tighten if observed copiers can't react that fast; loosen if paper-grade artefacts demand fresher numbers for credibility).
- Whether F_tok closure is still defensible after the band-AMM has accumulated enough on-chain flow that the feedback function may be inferable from outside (estimated: not before 2027 even at aggressive deployment).
- Whether the public/private *split itself* is the right structural form, or whether selective monorepo with branch-level access controls would serve better (default: split repos for clarity; revisit if it costs us merge friction).

## 10. See also

- `reports/methodology_history.md` §0 — current product progression (v0 router live, v1 event stream gated on Paper 3, v2 decision SDK 2027); W8 dated entry for the AMM-track parking decision.
- `reports/paper4_oracle_conditioned_amm/plan.md` — Paper 4 academic plan; B2 mechanism is the production target Layer 1 builds toward.
- `reports/paper4_oracle_conditioned_amm/colosseum_implementation_brief.md` — hackathon shipping doc; aligned with §3 Layer 1 + §4 L1.0/L2.0/L5.0.
- `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md` — the data pipeline priority order this doc references.
- `docs/methodology_scope.md` — which RWA classes the underlying methodology applies to (the same scope filter that gates Layer 1).
- `docs/product-spec.md` — Option C product specification from the oracle layer's perspective (Layer 0 detail).
