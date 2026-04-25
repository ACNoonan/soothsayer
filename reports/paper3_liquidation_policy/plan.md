# Paper 3 Plan — Optimal Liquidation Policy Defaults Under Calibrated Oracle Uncertainty

**Status:** planning document (internal).  
**Relationship to Paper 1 and Paper 2:**
- **Paper 1** validates an **oracle calibration primitive** (coverage inversion + receipts) on held-out data.
- **Paper 2** (in planning, `../paper2_oev_mechanism_design/plan.md`) studies **OEV mechanism design under calibration-transparent oracles** — how publishing the calibration band itself reshapes liquidation-auction equilibria.
- **Paper 3** (this document, `plan.md`) is the **decision-theoretic protocol-policy** capstone: given a calibrated band and the auction structure of Paper 2, what should a lending protocol's liquidation-policy defaults be?

The trilogy is methodology → mechanism → policy. Paper 3 can be read independently of Paper 2, but its strongest claims (welfare-comparable expected loss, robust operating regions) hold most cleanly when the auction layer is the one specified by Paper 2 rather than an arbitrary opaque-oracle baseline.

---

## 1) One-sentence thesis

**Given an oracle that serves auditable, empirically calibrated price bands, a lending protocol can choose liquidation-policy defaults that minimize expected protocol loss out of sample—especially in closed-market regimes where incumbent point-price fallbacks are weakest—provided the protocol specifies (i) book weights, (ii) a cost model, and (iii) action semantics.**

This paper is about that mapping: **band → action**.

---

## 2) Research question (what Paper 3 answers)

### Primary question
**What liquidation-policy default minimizes expected protocol loss out of sample when the protocol consumes a calibrated, regime-aware oracle band?**

### What this is *not*
Paper 3 is not “is the oracle calibrated?” (that is Paper 1).  
Paper 3 is not “what is the best forecaster?” (Paper 1 explicitly does not claim minimum-variance prediction).

---

## 3) The conceptual gap Paper 3 closes

Paper 1’s contract is about a calibrated band:
- the oracle returns `PricePoint(symbol, t_pub, τ) → (lower, upper, receipts)`

A lending protocol’s contract is about actions:
- `Safe / Caution / Liquidate`

Paper 3 supplies the missing layer: a defensible way to select defaults for that action policy, with uncertainty explicitly accounted for.

### What recent external research now makes much sharper

The production landscape is now clearer than when this plan was first drafted:

- **Kamino xStocks is the direct implementation target.** It already runs soft liquidations, dynamic penalties, TWAP/EWMA defenses, and per-asset risk multipliers. Paper 3 does not need to invent a new protocol; it needs to show how a calibrated band plugs into an existing liquidation ladder.
- **Chainlink's published 24/5 equities guidance leaves the weekend unresolved.** Their explicit recommendation for weekend coverage is to use prices of tokenized stocks on secondary CEX/DEX venues. For a lending protocol collateralized by those same tokens, that can become a circular reference: the collateral is priced by the venue where the collateral itself can be pushed around.
- **Kraken/backed-style market makers already behave like "factor switchboards."** Their published off-hours methodology cites ATS venues, index futures, and internal models, with wider off-hours spreads. That is pragmatic validation that Paper 3 is directionally aligned with how desks already approximate fair value off-hours.
- **Gauntlet and Chaos Labs already frame liquidation policy as an optimization problem.** This is strategically excellent for positioning. Paper 3 is not introducing the optimization framing; it is supplying a calibrated uncertainty input that existing consultancy-style optimization stacks currently do not publish.
- **Institutional RWA venues already admit that time-of-day and market-closure constraints matter.** Aave Horizon and similar setups acknowledge custom liquidation logic, custodial delay, and market-closure handling. Paper 3 can therefore frame regime-aware liquidation policy as a standardization of something sophisticated venues already do by hand.

That gives the paper a sharper opening claim: the gap is not "protocols ignore liquidation risk." The gap is that **production systems already optimize liquidation policy, but do so with point-price or aggregation-diagnostic inputs that do not publish an auditable coverage SLA for closed-market uncertainty.**

---

## 4) Draft claims (what Paper 3 would aim to prove)

### C1 — Decision-theoretic framing is necessary (and changes conclusions)
Liquidation-policy defaults are not identifiable from calibration metrics alone. A default depends on:
- portfolio weights (account-weighted vs debt-weighted vs threshold-heavy)
- a protocol loss function (missed liquidation vs unnecessary liquidation vs unnecessary caution)
- semantics of what counts as “correct” under realized outcomes

### C2 — Calibrated-band policies can dominate flat governance bands out of sample
There exists a policy family using Soothsayer’s band (e.g., Case A) that lowers expected loss versus a Kamino-style flat band baseline on walk-forward OOS evaluation, under stated assumptions.

### C3 — Robust regions beat fragile point-optima
The correct publishable output is a **stable region** (e.g. `τ ∈ [0.80, 0.85]` for a class of protocols/books), not a single fragile optimum.

### C4 — The production gap is specifically a closed-market uncertainty problem
The strongest deployment case is not "bands are always better than points everywhere." It is narrower and more defensible: when the reference market is closed, calibrated-band policies outperform flat point-price defaults and flat governance bands because they expose uncertainty precisely where incumbent infrastructure is least trustworthy.

---

## 5) Explicit non-claims (guardrails)

Paper 3 should *not* claim:
- universal optimality for all lending protocols
- optimality without stating cost ratios and portfolio weights
- MEV-aware “execution optimality” unless we measure execution outcomes (bundle reconstruction / slippage model)
- full execution-robust optimality unless we build path-aware ground truth rather than relying only on Monday open

---

## 6) Formal problem statement (minimal version)

### 6.1 Objects
- **State** at publish time: \(x_t = (\mathcal{F}_t, r_t, \text{PricePoint}_t)\), including receipts.
- **Action space**: \(a \in \{\texttt{Safe}, \texttt{Caution}, \texttt{Liquidate}\}\).
- **Policy class** \(\Pi\): mapping from oracle output to action. (Case A, Case B, etc.)
- **Realized outcome**: \(y_t\), derived from realized reference price(s).

### 6.2 Loss function
Define \(L(a, y; \theta)\) with explicit parameters \(\theta\) such as:
- missed liquidation cost (proxy for bad debt / insolvency)
- unnecessary liquidation cost (user harm / reputation / bonus leakage)
- unnecessary caution cost (blocked borrowing / utilization loss)

### 6.3 Portfolio weights
Define weights \(w(\text{position})\) and run multiple explicit schemes:
- account-weighted
- debt-weighted
- threshold-heavy stressed-book
- borrower-heavy / safer-book

### 6.4 Optimality criterion
For a policy \(\pi\), measure expected loss:
\[
\mathbb{E}[ L(\pi(x_t), y_t; \theta) ]\ \text{out of sample}
\]

---

## 7) Policy families to compare (what “defaults” mean)

At minimum:
- **Baseline (Kamino-style):** flat governance band (e.g. `±300bps`), flat liquidation threshold.
- **Soothsayer Case A:** regime-aware band, flat liquidation threshold.
- **Soothsayer Case B:** regime-aware band + regime-demoted threshold (if included, must define evaluation semantics clearly).
- **Sanity baselines:** stale-hold Gaussian, EWMA/realized-vol haircuts, asset-specific fixed bps if available.

All policies must share the same action semantics ladder `Safe / Caution / Liquidate` to be comparable.

---

## 8) “Truth semantics” (what counts as correct)

This is where the literature often cheats by leaving it implicit. Paper 3 should *name it* and treat it as an experimental dimension:

- **Economic truth (flat):** realized Monday price + flat threshold (simple insolvency proxy).
- **Policy-consistent truth:** realized price + the policy’s own threshold semantics.
- **Path-aware truth:** worst executable weekend path rather than a single endpoint.

The goal is not to hide this choice but to show whether conclusions are robust to it.

---

## 9) Evaluation protocol (minimum credible)

### 9.1 Walk-forward OOS
Replace single split with rolling-origin evaluation:
- train on window \(t \in [t_0, t_1]\)
- choose defaults / calibrations on validation
- test on \(t \in (t_1, t_2]\)
- repeat

### 9.2 Sensitivity grid
Every headline result must be presented across:
- weight schemes
- loss-function parameterizations
- truth semantics

### 9.3 Uncertainty
Use weekend-block bootstrap on deltas and ranking stability:
- \(\Delta\)expected_loss
- \(\Delta\)false-liquidation rate
- \(\Delta\)missed-liquidation rate
- probability the ranking flips under resampling

---

## 10) Existing repo artifacts we can reuse immediately

### End-to-end policy evaluation (already exists)
- `scripts/run_protocol_compare.py` — produces the policy-comparison tables with:
  - truth modes (`economic_flat85`, `policy_consistent`)
  - weight schemes (`uniform_ltv`, `borrower_heavy`, `threshold_heavy`, `debt_weighted`)
  - bootstrap CIs
- `src/soothsayer/backtest/protocol_compare.py` — cost matrix, weighting schemes, decision confusion, bootstrap deltas.

### Current outputs (paper-ready appendices)
- `reports/tables/protocol_compare_summary.csv`
- `reports/tables/protocol_compare_bootstrap.csv`
- `reports/tables/protocol_compare_by_regime.csv`
- `reports/tables/protocol_compare_confusion.csv`

### Complementary A/B views
- `scripts/aggregate_ab_matched.py` — matched-width vs matched-miss comparisons vs Kamino.
- `scripts/aggregate_ab_comparison.py` — aggregate per-regime and per-LTV comparisons.
- `scripts/replay_shock_weekend.py` — case-study figures for narrative.

### Protocol semantics reference
- `crates/soothsayer-demo-kamino/src/lib.rs` — the canonical `Safe/Caution/Liquidate` ladder used in the demo.

Paper 3 should treat these as the prototype implementation, then strengthen the evaluation design (walk-forward, richer baselines, path-aware truth, protocol-specific costs).

### External anchors now secured and worth citing directly
- **Kamino xStocks docs / launch materials** for the direct policy target: soft liquidations, dynamic penalty ladder, TWAP/EWMA protections, LTV + borrow factor semantics.
- **Chainlink 24/5 US equities docs** for the critical weekend point: explicit recommendation to extend weekend pricing with tokenized-stock secondary-market venues.
- **Kraken xStocks FAQ / methodology statements** for a citable off-hours desk benchmark: ATS inputs, futures inputs, internal fair-value models, wider weekend spreads.
- **Gauntlet methodology notes** for the explicit loss-optimization framing.
- **Chaos Labs methodology notes** for the key admission that black-swan tails are not statistically testable in their main simulation stack and are handled separately.
- **Aave Horizon / RWA risk materials** for explicit closed-market and operational-friction constraints.

These are not decorative citations. Together they let the introduction say: the paper is aimed squarely at the stack practitioners already use, and the missing piece is the calibrated uncertainty contract.

---

## 11) Practical market structure: **how** on-chain venues work (and why it matters for Paper 3)

Protocols do not trade against an abstract “market.” They depend on *specific* execution paths: a bonding curve, a set of price ticks, or a signed quote from a pro market maker. Paper 3’s policy recommendations are more credible if we describe **how** those mechanisms produce prices, not only *what* they are called.

### 11.1 Passive constant-function AMMs (CFMMs) — how price is formed and updated

- **State.** The pool stores reserves \((R_A, R_B)\) and commits to a public **invariant** \(f(R_A, R_B) = k\) (e.g. two-asset constant product \(R_A R_B = k\), or other curves used for stable pairs).
- **How the marginal price is defined.** The instantaneous *pool price* (up to fee) is the rate at which a tiny trade would move along the curve—equivalently, a function of the current reserves (for constant product, spot \(\propto R_B / R_A\)). It is *not* an independent oracle; it is the slope implied by the curve at the current point.
- **How a user trade executes.** A taker adds one asset to the pool and withdraws the other; reserves change so the invariant holds; the **effective** price for finite size is an average over the path on the curve (**slippage** grows with trade size and curvature).
- **How the on-chain price tracks the rest of the world.** If the pool’s marginal price drifts from off-chain CEX or index “fair” value, **arbitrageurs** buy cheap / sell rich until the gap closes enough to pay fees, gas, and risk. So the AMM price is a **lagged, fee-discounted, inventory-mediated** reflection of *other* venues—not a first-class risk forecast.
- **Implications for lending/oracles (Paper 3 narrative).** A single DEX *spot* is path-dependent, depth-dependent, and can be pushed around in low liquidity or across thin windows. **Time-weighted averages (TWAP)** reduce manipulation but add **lag** and **stale** risk during gaps. A **calibrated fair-value band** is complementary: it states *uncertainty* and auditability, which raw reserves do not.

### 11.2 Concentrated liquidity (CLMMs) — how execution differs from “full-curve” CFMMs

- **State.** LPs place liquidity in **price ranges (ticks)**, not uniformly across the whole curve. Capital is *dense* where LPs choose to work the range.
- **How price moves in a trade.** A swap walks the current price through ticks; at each step, it consumes the liquidity in that **tick** until the price crosses a boundary, then the next tick’s depth applies. The venue price is the **path through deployed liquidity**, not a single smooth pool ratio over all capital.
- **What breaks on large moves.** If the true price *jumps* outside the ranges where LPs have capital, the pool can be **out of range**: remaining liquidity is far from the new price, **depth can collapse**, and the next print can be a poor or volatile executable (until LPs rebalance or new range is set).
- **Informed flow and rebalancing.** Informed takers and JIT liquidity can **pull** the executable price; passive range positions can go **stale** (wrong range after a regime shift). So “the CLMM mid” is even more **state- and path-dependent** than a v2 spot.
- **Implications for Paper 3.** A protocol that treats “DEX mid” as ground truth in a CLMM world is *more* exposed to *executable* dislocations, not less. The paper can argue for defaults that use **calibrated reference bands** (and explicit operational semantics) rather than assuming one venue’s **marginal** price equals **economic** fair value.

### 11.3 Solvers, RFQ, and proprietary / oracle-driven market making — how modern on-chain routing actually works

These designs separate **where fair value is computed** from **where the trade settles**, which matters when we discuss liquidation and oracle policy.

- **Quoting loop (off-chain or trusted infra).** A market maker or protocol maintains a view of “fair” price from **oracles, CEX feeds, inventory, and risk limits**, then produces **tight quotes** (amount in, amount out, expiry) rather than letting reserves alone set price.
- **On-chain settlement.** The user (or an aggregator) lands a transaction that **verifies a signature** or **applies a parameter update** to a program-controlled curve, then performs the asset exchange **atomically** in one bundle.
- **RFQ (request for quote).** The MM signs a *specific* \((\text{in}, \text{out}, \text{expiry}, \text{chain})\) offer; the taker fills that exact quote. Price is **negotiated for that size and moment**, not read purely from a passive formula—useful for size, but **adverse selection** against slow quotes is a first-order risk.
- **Aggregators and route splitting.** Routers (e.g. Jupiter-style on Solana, 1inch-style on EVM) **search many venues** and split flow to minimize user slippage under constraints. The **relevant** price for a borrower/liquidator is the **best executable path**, not a single pool’s mid.
- **Ordering and MEV (brief).** On chains with private bundles (e.g. Jito on Solana) or MEV on EVM, **inclusion order** and **frontrunning** can change the **realized** fill versus the *quoted* one at signing time. Paper 3 should only claim **execution-robust** optimality if we model or measure that layer (Section 5 and §12.5 non-claims already flag this).
- **Implications for Paper 3.** In production, the ecosystem already behaves like **fast-updating, oracle-aware execution** (CFMM/CLMM as *one* source among many) rather than a single static v2 pool. **Liquidation policy defaults** should be stated in terms compatible with: **(i)** uncertain reference levels, **(ii)** multiple venues, and **(iii)** time-varying executability—exactly the setting where a **calibrated band interface** and an explicit **loss/cost** model (Sections 6–9) are the right abstraction, not a single spot print.

### 11.4 One-line contrast (for the paper’s “how” table)

| Mechanism | *How* the price the protocol “sees” is produced | Main fragility for lending use |
|-----------|--------------------------------------------------|---------------------------------|
| CFMM | Invariant from **reserves**; updates via **swaps** and **arbitrage** | Manipulation, thin depth, off-hours dislocation |
| CLMM | **Tick-by-tick** walk through **range-bound** liquidity | Out-of-range depth collapse, stale LP ranges |
| Solver / RFQ / prop MM | **Off-chain** FV + **signed** quote or param update, **on-chain** settle | Quote staleness, adverse selection, bundle/MEV gap |

### 11.5 Production comparables to keep front-and-center in the paper

- **Kamino xStocks** should be the main narrative anchor, not a side example. Its liquidation ladder is already close to the policy interface we need.
- **Chainlink weekend fallback** should appear in the introduction, not buried in related work. It is the cleanest empirical demonstration that the industry still lacks a non-circular closed-market policy primitive.
- **RedStone's public weekend-gap framing** is useful adversarial corroboration: even a competing oracle provider is openly stating that weekend dislocation remains unresolved.
- **Perp/synthetic equity venues** should be used as a "continuous quoting" comparator, not as proof that the problem disappears. Their mark/index separation and off-hours quoting logic show that sophisticated venues explicitly manage uncertainty rather than pretending the spot is exact.

The practical implication is that Paper 3 should read less like abstract mechanism design and more like a policy standard for venues already operating under uncertain off-hours fair value.

---

## 12) What new evidence Paper 3 must add (beyond current repo)

This is the real “bar to publication” list.

### 12.1 Walk-forward policy selection
Produce a distribution of “best regions” across time, not one split.

### 12.2 Protocol-specific cost models
Replace purely stylized costs with at least a small set of plausible protocol cost scenarios (even if still parameterized):
- liquidation bonus assumptions
- bad debt severity assumptions
- utilization cost assumptions

### 12.3 Realistic book-weight priors
The current weight schemes are a good sensitivity scaffold, but Paper 3 should add at least one “Kamino-like” synthetic book and one “risk-on” skewed book (explicitly declared).

### 12.4 Broader baseline set
At least one baseline beyond “flat ±300bps” to show we are not only beating one strawman:
- asset-specific governance bands (if obtainable)
- EWMA/realized-vol haircuts
- stale-hold + Gaussian
- a simple futures-gap heuristic

### 12.5 Path-aware truth is no longer optional
Recent external research makes this upgrade mandatory before publication-quality claims. Monday open is still useful, but it is rhetorically too clean. A protocol cares about the worst executable off-hours price, not only the endpoint once the primary venue reopens.

Minimum credible upgrade:
- build a **weekend path truth** using tokenized-stock DEX OHLC / executable prints
- optionally layer in ATS / extended-hours proxies where available
- report both **endpoint truth** and **path-aware truth**

This does two things:
- makes the paper robust against the obvious reviewer objection ("you only validated the Monday print")
- creates the right benchmark against claims like "mismatch is usually <1% by Monday open," which can be true at the endpoint while still hiding liquidating intrawindow excursions

### 12.6 Related-work spine to make explicit in the draft
The paper should cite a tight, pragmatic shelf rather than a broad literature dump:

- **Coverage / calibration:** Kupiec, Christoffersen, adaptive conformal / temporal conformal work for the upgrade path from empirical inversion to stronger online guarantees
- **DeFi liquidation theory:** formal lending-protocol models and empirical liquidation studies showing that threshold choice depends on information the chain does not directly observe
- **Weekend / overnight risk in TradFi:** weekend-gap and overnight-return literature establishing that off-hours price risk is real, priced, and structurally different from intraday risk
- **Adaptive-LTV / time-friction analogues:** the closest prior work arguing that leverage constraints should vary with time-of-market and market-closure frictions

The goal of this section is not to claim novelty over every adjacent paper. It is to show that Paper 3 sits at the intersection of three mature ideas that have not yet been joined cleanly in production: calibration, liquidation optimization, and off-hours market microstructure.

---

## 13) Success criteria (what would make the second paper a “yes”)

I would consider Paper 3 ready to draft when we can show:
- A Soothsayer-based policy family beats baselines in expected loss on walk-forward OOS.
- The win is robust across a reasonable grid of cost and weight assumptions.
- We can explain the mechanism (narrow when calm, widen when risky, fewer expensive misses without too many unnecessary liquidations).
- The result still holds when tested against **path-aware weekend truth**, not only Monday-open truth.
- We can disclose where it does *not* win (assumption-sensitive regions) without undermining the core claim.

---

## 14) Concrete next steps (research execution order)

1. Extend `run_protocol_compare` into walk-forward evaluation.
2. Expand cost scenarios (parameter sweep) and record ranking stability.
3. Add at least one additional baseline family beyond flat ±300bps, ideally including a futures/ATS-informed heuristic.
4. Build path-aware weekend truth before treating the paper as draft-ready.
5. Only after that decide how much explicit MEV / execution realism is needed for the claim we want to make.

This order keeps the project honest: prove the decision-layer story under clearly stated assumptions, but do not stop at endpoint truth. The paper's biggest strategic advantage is precisely that closed-market uncertainty is observable, material, and mishandled by today's production stack.

---

## 15) Draft abstract + introduction skeleton

The goal here is not polished prose. It is a draftable structure that preserves the sharper positioning from Sections 3, 10, 11, and 12.

### 15.1 Working abstract skeleton

Existing DeFi lending risk systems already frame liquidation-parameter selection as a constrained optimization problem, but the price inputs they consume during closed-market hours are weakly specified. In tokenized-equity markets, incumbent oracle and pricing stacks typically publish point prices, quote-dispersion diagnostics, or venue-specific fallback prices, without an auditable aggregate-level coverage statement for off-hours uncertainty. This matters because the largest reference-price gaps and the most policy-sensitive liquidation decisions occur precisely when the underlying venue is closed.

We study the mapping from **calibrated price band to liquidation action**. Taking as given an oracle that serves empirically calibrated, regime-aware price bands with auditable receipts, we formulate liquidation-policy selection as an out-of-sample expected-loss minimization problem over explicit action semantics, cost models, and portfolio-weight assumptions. We compare policy families that consume calibrated bands against flat governance-band and flat-threshold baselines modeled on current tokenized-equity lending practice.

Our central claim is not that one liquidation threshold is universally optimal. It is that, in closed-market regimes, calibrated-band policies can dominate flat point-price defaults in expected-loss terms over a robust region of cost and book assumptions, and that the publishable object is a **stable operating region** rather than a fragile single optimum. We evaluate these policies on weekend windows for tokenized US equities, report sensitivity to truth semantics and book composition, and require path-aware off-hours validation in addition to endpoint reopening prices.

The paper's contribution is therefore a policy layer, not a new oracle primitive: a decision-theoretic, audit-friendly framework for choosing liquidation defaults when the protocol's price input is explicitly uncertain and that uncertainty is empirically calibrated.

### 15.2 Alternate abstract opening sentence options

- **Production-first:** Existing DeFi risk engines already optimize liquidation parameters, but they do so with off-hours price inputs that rarely publish an auditable coverage SLA.
- **Problem-first:** Tokenized equities trade continuously on-chain while their primary price-discovery venues close overnight and on weekends, forcing lending protocols to liquidate against uncertain off-hours reference prices.
- **Comparative-first:** Flat liquidation thresholds and point-price oracle fallbacks are a poor fit for closed-market tokenized-equity lending, where uncertainty, not just level, is the object the protocol should consume.

### 15.3 Introduction skeleton

#### Intro ¶1 — Structural problem
Start with the architecture mismatch: tokenized RWAs trade continuously, underlying venues do not. Emphasize that the economically relevant problem is not merely "what is the price?" but "what action should a lending protocol take when the reference level is uncertain and the venue that anchors fair value is closed?"

#### Intro ¶2 — Why this matters for liquidation policy
Move immediately from oracle language to policy language. Liquidation is where uncertainty becomes costly: missed liquidations create bad debt; unnecessary liquidations destroy borrower value and trust; unnecessary caution reduces utilization and revenue. This paragraph should make clear that Paper 3 is about protocol loss, not forecast elegance.

#### Intro ¶3 — What production systems do today
Name the real stack directly. Kamino xStocks is the main comparable. Gauntlet and Chaos Labs already formulate parameter selection as optimization. Aave Horizon already admits closed-market and operational-friction constraints. This paragraph should say: the industry is not missing optimization; it is missing a calibrated uncertainty input for optimization.

#### Intro ¶4 — The critical closed-market gap
This is where Chainlink belongs. State clearly that published 24/5 equities guidance recommends extending weekend coverage with tokenized-stock prices on secondary venues. For a protocol using those same tokens as collateral, this can become circular. Then add the corroborating desk-style contrast: Kraken/backed-style market makers cite ATS, futures, and internal models, which shows sophisticated operators already treat off-hours fair value as a modeling problem rather than a single authoritative print.

#### Intro ¶5 — What Paper 1 gives us, and why that still does not answer the policy question
Briefly summarize Paper 1 as the primitive: a calibrated, auditable band with receipts and empirical coverage evidence. Then pivot: calibration alone does not tell a protocol when to warn, liquidate, or demote thresholds. That requires action semantics, costs, and book assumptions.

#### Intro ¶6 — Paper 3's formal question
State the paper's question in one sentence: given a calibrated band, which liquidation-policy default minimizes expected protocol loss out of sample? Introduce the three explicit modeling axes: cost model, weight scheme, and truth semantics. This is where the reader should understand why "optimal" must be conditional, not universal.

#### Intro ¶7 — Main claims
Use three claims:
- decision-theoretic framing changes the answer
- calibrated-band policies can beat flat defaults in closed-market regimes
- the right output is a stable operating region, not a single magic number

Keep the claims narrow and production-facing.

#### Intro ¶8 — Evaluation design and publication bar
Preview walk-forward evaluation, sensitivity grids, and bootstrap stability. Explicitly mention that endpoint Monday-open truth is insufficient on its own and that the paper uses or requires path-aware weekend truth as the harsher validation target.

#### Intro ¶9 — Contributions
List contributions in Paper 3 language, not Paper 1 language:
- a formal band-to-action decision problem
- a protocol-comparable evaluation stack using current lending semantics
- evidence on robust operating regions under explicit costs and book assumptions
- a deployable policy template / governance-facing output format

#### Intro ¶10 — Scope and non-claims
Close the introduction by narrowing scope: no universal optimality, no claim of full execution optimality without MEV/slippage measurement, and no replacement of existing risk consultancies. The paper is a calibrated decision layer designed to plug into those systems.

### 15.4 Sentence-level material worth reusing

These are candidate lines or near-lines, not final prose:

- "The production gap is not that protocols fail to optimize liquidation policy; it is that they optimize against off-hours price inputs that do not publish an auditable uncertainty contract."
- "Paper 1 asks whether a served band is calibrated. Paper 2 asks how OEV auctions should be designed to consume that band. Paper 3 asks what a lending protocol should do with the resulting (band, auction) primitive."
- "In closed-market tokenized-equity lending, uncertainty is not an implementation detail of the price feed; it is part of the state variable that should govern liquidation."
- "The relevant benchmark is not a single Monday reopening print but the worst executable off-hours path the protocol would have had to survive."

---

## 16) Citation-to-section map for the draft

This is a pragmatic map for where each citation family should do real argumentative work. The rule is: every citation should either establish a live production fact, support a modeling choice, or anchor a methodological claim.

### 16.1 Abstract

- **No dense citation load if avoidable.** At most one or two anchor citations if the venue expects them.
- If one citation is used, prefer a **production-anchor citation** showing that current risk systems already optimize liquidation parameters, so the paper is clearly additive rather than naive.

### 16.2 Introduction

#### Structural market-closure problem
- **Weekend / overnight gap literature**
  - Use to support the claim that off-hours price risk is real, persistent, and distinct from intraday variation.
  - Good home for empirical stylized-fact citations on weekend gaps and overnight-return information content.

#### Current production practice
- **Kamino xStocks docs / launch materials**
  - Cite when introducing the direct protocol comparable and its liquidation semantics.
- **Chainlink 24/5 equities docs**
  - Cite in the paragraph that establishes the weekend fallback gap.
- **Kraken xStocks / backed methodology**
  - Cite as a production benchmark for how market makers approximate fair value off-hours.
- **RedStone public statements**
  - Use sparingly as corroboration that weekend dislocation is acknowledged by practitioners, not as the primary evidentiary source.
- **Aave Horizon / RWA risk materials**
  - Cite where the introduction says institutional venues already encode time-of-market and operational constraints.
- **Gauntlet methodology**
  - Cite when claiming existing stacks frame parameter choice as optimization.
- **Chaos Labs methodology**
  - Cite when claiming simulation-heavy stacks still leave tail validation / black-swan treatment as a separate problem.

#### Positioning versus Paper 1 / prior oracle work
- **Paper 1 / internal prior paper**
  - Cite for the calibrated-band primitive and the coverage-inversion contract.
- **Oracle docs (Chainlink, Pyth, RedStone)**
  - Use to contrast point prices, quote-dispersion intervals, or undisclosed methods with an auditable coverage SLA.

### 16.3 Related work

Organize the related-work section into four shelves, each with a distinct job:

#### Shelf A — Calibration and statistical coverage
- **Kupiec**
  - For unconditional coverage testing.
- **Christoffersen**
  - For conditional coverage / independence.
- **Adaptive conformal / temporal conformal papers**
  - For the upgrade path beyond empirical inversion and buffer heuristics.

Job: establish that the paper's uncertainty contract is about auditable coverage, not generic forecast quality.

#### Shelf B — DeFi lending and liquidation theory
- **Formal lending-protocol theory papers**
  - For state-based modeling of collateral, debt, and liquidation thresholds.
- **Empirical liquidation studies**
  - For evidence of excessive liquidation, borrower behavior, and liquidation externalities.
- **DeFi leverage / fragility papers**
  - For the argument that optimal thresholds depend on information not directly observable on-chain.

Job: justify why liquidation policy is an economic decision problem rather than a pure oracle-design problem.

#### Shelf C — Production risk methodology
- **Gauntlet**
  - Optimization objective and agent-based simulation framing.
- **Chaos Labs**
  - Same framing plus explicit black-swan caveat.
- **Aave governance literature on optimal liquidation / protocol equity**
  - For the fact that the ecosystem already has a mathematical language for liquidation-policy choice.

Job: show that Paper 3 plugs into an existing production/governance workflow.

#### Shelf D — Off-hours price discovery and adaptive leverage
- **Weekend / overnight TradFi literature**
  - For stylized facts and why off-hours risk deserves its own treatment.
- **Adaptive-LTV / liquidity-of-time / time-friction papers**
  - For the closest in-spirit precedent that leverage constraints should move with market-closure or off-hours conditions.
- **Perp / synthetic venue docs**
  - For practical comparators on mark/index handling under continuous trading of discontinuously anchored underlyings.

Job: establish that Paper 3's regime-aware liquidation idea has both empirical and practical precedent.

### 16.4 Problem statement / model section

- **Formal DeFi lending papers**
  - Cite for notation, state/action framing, or health-factor semantics if useful.
- **Aave / Kamino / protocol docs**
  - Cite for actual action semantics when defining `Safe / Caution / Liquidate`, liquidation bonuses, and threshold rules.

This section should be lightly cited. Its main job is to define your model cleanly.

### 16.5 Data / market structure / truth semantics

- **Kamino docs**
  - When mapping policy semantics to a real protocol.
- **Chainlink / Pyth / RedStone docs**
  - When explaining incumbent oracle behavior.
- **Kraken / backed / market-maker methodology**
  - When motivating ATS/futures/internal-model comparators.
- **Perp / synthetic venue docs**
  - When motivating mark/index comparisons or path-aware off-hours benchmarks.

This is where citations should explain market plumbing, not just decorate the narrative.

### 16.6 Evaluation section

- **Minimal external citations.**
  - Most of the evaluation section should stand on your own methods and results.
- Cite **Kupiec / Christoffersen / bootstrap** references only where a test or interval construction needs a formal anchor.

### 16.7 Discussion / recommendations

- **Gauntlet / Chaos / governance-post comparators**
  - Use when arguing that the paper's output should be a governance-facing operating region rather than a single threshold.
- **Aave Horizon / institutional RWA materials**
  - Use when discussing operational constraints and qualified-liquidator realities.
- **Kraken / market-maker methodology**
  - Use when making the case that band-aware policies resemble how off-hours desks already think.

### 16.8 Appendix / implementation notes

- **Protocol docs and oracle docs**
  - Good place for implementation details, feed behavior, parameter ladders, and fallback logic.
- **Paper 1**
  - Good place to offload primitive-specific details so Paper 3 stays a policy paper.

### 16.9 Anti-bloat rules for citation use

- Do not spend scarce introduction real estate on broad "blockchain adoption" citations.
- Do not bury the strongest production evidence in related work; `Chainlink`, `Kamino`, `Gauntlet`, `Chaos`, and `Aave Horizon` belong in the main narrative.
- Prefer one citation that directly establishes a live production fact over three adjacent academic citations that only gesture at it.
- Use academic citations to justify methodology and stylized facts; use production citations to justify relevance and deployment realism.


