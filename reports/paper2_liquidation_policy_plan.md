# Paper 2 Plan — Optimal Liquidation Policy Defaults Under Calibrated Oracle Uncertainty

**Status:** planning document (internal).  
**Relationship to Paper 1:** Paper 1 validates an **oracle calibration primitive** (coverage inversion + receipts) on held-out data. Paper 2 is a **decision-theoretic protocol policy** paper: given a calibrated band, what should a lending protocol do?

---

## 1) One-sentence thesis

**Given an oracle that serves auditable, empirically calibrated price bands, a lending protocol can choose liquidation-policy defaults that minimize expected protocol loss out of sample—provided the protocol specifies (i) book weights, (ii) a cost model, and (iii) action semantics.**

This paper is about that mapping: **band → action**.

---

## 2) Research question (what Paper 2 answers)

### Primary question
**What liquidation-policy default minimizes expected protocol loss out of sample when the protocol consumes a calibrated, regime-aware oracle band?**

### What this is *not*
Paper 2 is not “is the oracle calibrated?” (that is Paper 1).  
Paper 2 is not “what is the best forecaster?” (Paper 1 explicitly does not claim minimum-variance prediction).

---

## 3) The conceptual gap Paper 2 closes

Paper 1’s contract is about a calibrated band:
- the oracle returns `PricePoint(symbol, t_pub, τ) → (lower, upper, receipts)`

A lending protocol’s contract is about actions:
- `Safe / Caution / Liquidate`

Paper 2 supplies the missing layer: a defensible way to select defaults for that action policy, with uncertainty explicitly accounted for.

---

## 4) Draft claims (what Paper 2 would aim to prove)

### C1 — Decision-theoretic framing is necessary (and changes conclusions)
Liquidation-policy defaults are not identifiable from calibration metrics alone. A default depends on:
- portfolio weights (account-weighted vs debt-weighted vs threshold-heavy)
- a protocol loss function (missed liquidation vs unnecessary liquidation vs unnecessary caution)
- semantics of what counts as “correct” under realized outcomes

### C2 — Calibrated-band policies can dominate flat governance bands out of sample
There exists a policy family using Soothsayer’s band (e.g., Case A) that lowers expected loss versus a Kamino-style flat band baseline on walk-forward OOS evaluation, under stated assumptions.

### C3 — Robust regions beat fragile point-optima
The correct publishable output is a **stable region** (e.g. `τ ∈ [0.80, 0.85]` for a class of protocols/books), not a single fragile optimum.

---

## 5) Explicit non-claims (guardrails)

Paper 2 should *not* claim:
- universal optimality for all lending protocols
- optimality without stating cost ratios and portfolio weights
- MEV-aware “execution optimality” unless we measure execution outcomes (bundle reconstruction / slippage model)
- path-aware liquidation truth unless we build a path-based ground truth (not just Monday open)

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

This is where the literature often cheats by leaving it implicit. Paper 2 should *name it* and treat it as an experimental dimension:

- **Economic truth (flat):** realized Monday price + flat threshold (simple insolvency proxy).
- **Policy-consistent truth:** realized price + the policy’s own threshold semantics.
- **(Later / optional) Path-aware truth:** worst executable weekend path rather than a single endpoint.

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

Paper 2 should treat these as the prototype implementation, then strengthen the evaluation design (walk-forward, richer baselines, path-aware truth, protocol-specific costs).

---

## 11) Practical market structure: **how** on-chain venues work (and why it matters for Paper 2)

Protocols do not trade against an abstract “market.” They depend on *specific* execution paths: a bonding curve, a set of price ticks, or a signed quote from a pro market maker. Paper 2’s policy recommendations are more credible if we describe **how** those mechanisms produce prices, not only *what* they are called.

### 11.1 Passive constant-function AMMs (CFMMs) — how price is formed and updated

- **State.** The pool stores reserves \((R_A, R_B)\) and commits to a public **invariant** \(f(R_A, R_B) = k\) (e.g. two-asset constant product \(R_A R_B = k\), or other curves used for stable pairs).
- **How the marginal price is defined.** The instantaneous *pool price* (up to fee) is the rate at which a tiny trade would move along the curve—equivalently, a function of the current reserves (for constant product, spot \(\propto R_B / R_A\)). It is *not* an independent oracle; it is the slope implied by the curve at the current point.
- **How a user trade executes.** A taker adds one asset to the pool and withdraws the other; reserves change so the invariant holds; the **effective** price for finite size is an average over the path on the curve (**slippage** grows with trade size and curvature).
- **How the on-chain price tracks the rest of the world.** If the pool’s marginal price drifts from off-chain CEX or index “fair” value, **arbitrageurs** buy cheap / sell rich until the gap closes enough to pay fees, gas, and risk. So the AMM price is a **lagged, fee-discounted, inventory-mediated** reflection of *other* venues—not a first-class risk forecast.
- **Implications for lending/oracles (Paper 2 narrative).** A single DEX *spot* is path-dependent, depth-dependent, and can be pushed around in low liquidity or across thin windows. **Time-weighted averages (TWAP)** reduce manipulation but add **lag** and **stale** risk during gaps. A **calibrated fair-value band** is complementary: it states *uncertainty* and auditability, which raw reserves do not.

### 11.2 Concentrated liquidity (CLMMs) — how execution differs from “full-curve” CFMMs

- **State.** LPs place liquidity in **price ranges (ticks)**, not uniformly across the whole curve. Capital is *dense* where LPs choose to work the range.
- **How price moves in a trade.** A swap walks the current price through ticks; at each step, it consumes the liquidity in that **tick** until the price crosses a boundary, then the next tick’s depth applies. The venue price is the **path through deployed liquidity**, not a single smooth pool ratio over all capital.
- **What breaks on large moves.** If the true price *jumps* outside the ranges where LPs have capital, the pool can be **out of range**: remaining liquidity is far from the new price, **depth can collapse**, and the next print can be a poor or volatile executable (until LPs rebalance or new range is set).
- **Informed flow and rebalancing.** Informed takers and JIT liquidity can **pull** the executable price; passive range positions can go **stale** (wrong range after a regime shift). So “the CLMM mid” is even more **state- and path-dependent** than a v2 spot.
- **Implications for Paper 2.** A protocol that treats “DEX mid” as ground truth in a CLMM world is *more* exposed to *executable* dislocations, not less. The paper can argue for defaults that use **calibrated reference bands** (and explicit operational semantics) rather than assuming one venue’s **marginal** price equals **economic** fair value.

### 11.3 Solvers, RFQ, and proprietary / oracle-driven market making — how modern on-chain routing actually works

These designs separate **where fair value is computed** from **where the trade settles**, which matters when we discuss liquidation and oracle policy.

- **Quoting loop (off-chain or trusted infra).** A market maker or protocol maintains a view of “fair” price from **oracles, CEX feeds, inventory, and risk limits**, then produces **tight quotes** (amount in, amount out, expiry) rather than letting reserves alone set price.
- **On-chain settlement.** The user (or an aggregator) lands a transaction that **verifies a signature** or **applies a parameter update** to a program-controlled curve, then performs the asset exchange **atomically** in one bundle.
- **RFQ (request for quote).** The MM signs a *specific* \((\text{in}, \text{out}, \text{expiry}, \text{chain})\) offer; the taker fills that exact quote. Price is **negotiated for that size and moment**, not read purely from a passive formula—useful for size, but **adverse selection** against slow quotes is a first-order risk.
- **Aggregators and route splitting.** Routers (e.g. Jupiter-style on Solana, 1inch-style on EVM) **search many venues** and split flow to minimize user slippage under constraints. The **relevant** price for a borrower/liquidator is the **best executable path**, not a single pool’s mid.
- **Ordering and MEV (brief).** On chains with private bundles (e.g. Jito on Solana) or MEV on EVM, **inclusion order** and **frontrunning** can change the **realized** fill versus the *quoted* one at signing time. Paper 2 should only claim **execution-robust** optimality if we model or measure that layer (Section 5 and §12.5 non-claims already flag this).
- **Implications for Paper 2.** In production, the ecosystem already behaves like **fast-updating, oracle-aware execution** (CFMM/CLMM as *one* source among many) rather than a single static v2 pool. **Liquidation policy defaults** should be stated in terms compatible with: **(i)** uncertain reference levels, **(ii)** multiple venues, and **(iii)** time-varying executability—exactly the setting where a **calibrated band interface** and an explicit **loss/cost** model (Sections 6–9) are the right abstraction, not a single spot print.

### 11.4 One-line contrast (for the paper’s “how” table)

| Mechanism | *How* the price the protocol “sees” is produced | Main fragility for lending use |
|-----------|--------------------------------------------------|---------------------------------|
| CFMM | Invariant from **reserves**; updates via **swaps** and **arbitrage** | Manipulation, thin depth, off-hours dislocation |
| CLMM | **Tick-by-tick** walk through **range-bound** liquidity | Out-of-range depth collapse, stale LP ranges |
| Solver / RFQ / prop MM | **Off-chain** FV + **signed** quote or param update, **on-chain** settle | Quote staleness, adverse selection, bundle/MEV gap |

---

## 12) What new evidence Paper 2 must add (beyond current repo)

This is the real “bar to publication” list.

### 12.1 Walk-forward policy selection
Produce a distribution of “best regions” across time, not one split.

### 12.2 Protocol-specific cost models
Replace purely stylized costs with at least a small set of plausible protocol cost scenarios (even if still parameterized):
- liquidation bonus assumptions
- bad debt severity assumptions
- utilization cost assumptions

### 12.3 Realistic book-weight priors
The current weight schemes are a good sensitivity scaffold, but Paper 2 should add at least one “Kamino-like” synthetic book and one “risk-on” skewed book (explicitly declared).

### 12.4 Broader baseline set
At least one baseline beyond “flat ±300bps” to show we are not only beating one strawman:
- asset-specific governance bands (if obtainable)
- EWMA/realized-vol haircuts
- stale-hold + Gaussian
- a simple futures-gap heuristic

### 12.5 (Optional but strong) Path-aware truth + execution realism
If the goal is truly “optimal defaults,” the most persuasive upgrade is path-aware liquidation truth (worst weekend path) and an execution model (slippage/MEV). Otherwise the claim remains “optimal under endpoint-truth proxy.”

---

## 13) Success criteria (what would make the second paper a “yes”)

I would consider Paper 2 ready to draft when we can show:
- A Soothsayer-based policy family beats baselines in expected loss on walk-forward OOS.
- The win is robust across a reasonable grid of cost and weight assumptions.
- We can explain the mechanism (narrow when calm, widen when risky, fewer expensive misses without too many unnecessary liquidations).
- We can disclose where it does *not* win (assumption-sensitive regions) without undermining the core claim.

---

## 14) Concrete next steps (research execution order)

1. Extend `run_protocol_compare` into walk-forward evaluation.
2. Expand cost scenarios (parameter sweep) and record ranking stability.
3. Add at least one additional baseline family beyond flat ±300bps.
4. Only then consider path-aware truth and MEV/execution realism.

This order keeps the project honest: prove the decision-layer story under clearly stated assumptions first, then spend time on realism upgrades.


