# Paper 2 Plan — OEV Mechanism Design Under Calibration-Transparent Oracles

**Status:** planning document (internal).
**Relationship to Paper 1 and Paper 3:**
- **Paper 1** validates a calibration-transparent oracle primitive (coverage inversion + receipts) on held-out data.
- **Paper 2** (this document) studies how *publishing the calibration band itself* reshapes the equilibrium of OEV-recapture auctions and liquidation-trigger mechanisms in lending protocols.
- **Paper 3** (`../paper3_liquidation_policy/plan.md`) is the protocol-side capstone: given a calibrated band and the auction structure of Paper 2, what should a lending protocol's liquidation-policy defaults be?

The trilogy is methodology → mechanism → policy. Paper 2 sits at the centre and is the most novel of the three: existing OEV mechanism literature treats the oracle as a black box, and the calibration-transparency assumption breaks that abstraction.

---

## 1) One-sentence thesis

**An oracle that publishes its calibration band as a first-class, audit-receipted output strictly dominates an opaque-price oracle in OEV-recapture auction welfare under reasonable assumptions, because the published band collapses the liquidator's private-information advantage without weakening borrower protection or protocol solvency guarantees — and band-conditional liquidation-trigger mechanisms strictly dominate point-conditional triggers in expected protocol welfare over a robust region of cost and book assumptions.**

This paper is about the auction-and-trigger layer between Paper 1's primitive and Paper 3's policy.

---

## 2) Research question (what Paper 2 answers)

### Primary question
**Given a calibration-transparent oracle that serves $(\hat P_t, [L_t, U_t], q_\text{served}, \rho)$ at every read, what auction mechanisms and liquidation-trigger rules should a lending protocol adopt to (i) maximise OEV recapture for protocol/borrowers and (ii) minimise welfare losses from spurious liquidations, relative to the opaque-oracle baseline?**

### What this is *not*
Paper 2 is not "is the oracle calibrated?" (Paper 1).
Paper 2 is not "what LTV/LT should a protocol set?" (Paper 3).
Paper 2 is not a generic MEV survey: it is specifically about the auction layer that consumes oracle reads in lending-protocol liquidations.

---

## 3) The conceptual gap Paper 2 closes

The deployed and academic OEV literature has converged on a clear pattern:

- **Chainlink SVR (Smart Value Recapture).** Top-of-block auctions in collaboration with Flashbots; opaque oracle, recapture goes to protocols as a refund.
- **RedStone Atom.** Atomic OEV auctions with builder/searcher participation; opaque oracle.
- **API3 OEV / Order Flow Auctions.** OEV auction proceeds redistributed in API3 token; opaque oracle.
- **UMA Oval.** MEV recapture for lending dApps that consume UMA price feeds; opaque oracle.
- **Andreoulis et al. (2026) OURW** [andreoulis-fair-oev]. Theoretical Oracle Update Rebate Window: refund + fallback-window mechanism establishing censorship-proofness conditions; opaque oracle.

Every existing mechanism treats the oracle as a *price-emitting black box*. The mechanism designer's task is to recapture extractable rents *given* an opaque feed. The mechanisms differ in auction format (top-of-block, atomic, order-flow) and in the censorship-resistance argument they make, but they share the abstraction.

Soothsayer's calibration-transparent oracle breaks that abstraction. When the oracle publishes its band $[L_t, U_t]$ alongside the price, *and* a receipt that asserts a verifiable empirical coverage rate, the information structure of the auction game changes:

1. **Searcher information rents shrink.** The private model edge a sophisticated searcher uses to price the next-oracle-update value is now partly public. The *tighter* the published band, the smaller the private edge.
2. **Trigger semantics become richer.** A protocol can specify "trigger liquidation only when the realised price exits the served 99% band for $N$ consecutive epochs" — a condition that is verifiable on-chain and that no opaque-oracle protocol can specify without inventing its own band on top of the feed.
3. **Censorship arguments change.** The OURW result depends on a builder/searcher's expected profit from censoring an oracle update relative to including it. With a calibration receipt, the protocol can characterise the *distribution* of expected next-update values, which tightens the bound on profitable censorship strategies.

The conceptual gap is that **the entire OEV mechanism-design literature has been written under an assumption (opaque oracle) that an emerging class of oracle systems explicitly violate.** Paper 2 redoes the mechanism design under the transparency assumption.

---

## 4) Draft claims (what Paper 2 would aim to prove)

### C1 — Calibration disclosure shrinks searcher information rents in equilibrium
In a stylised auction model where searchers compete to win liquidation rights on a position whose health depends on a future oracle update, equilibrium searcher rents are weakly decreasing in the *sharpness* (narrowness) of the published calibration band. In the limit of a degenerate band ($L_t = U_t$), private information collapses and searcher rents go to the auction-format minimum.

### C2 — Band-conditional liquidation triggers can dominate point triggers in expected protocol welfare
There exists a family of band-conditional trigger rules (e.g., $N$-of-$M$ exits from the served $\tau$ band) that strictly dominates the equivalent point-conditional rule in expected protocol welfare under stated assumptions about cost ratios, book composition, and the realised-price distribution. The dominance is mechanical at calm regimes (band is wide enough that a point trigger is too sensitive) and becomes interesting in transition regimes.

### C3 — A band-aware OURW mechanism achieves censorship-proofness at a lower fallback-window cost than the opaque-oracle OURW of Andreoulis et al.
Their main theoretical result is that censorship is unprofitable when the refund rate, fallback-window length, and builder-competition parameters jointly satisfy an inequality. We conjecture that the inequality slackens monotonically as the published band tightens, allowing a shorter fallback window (less staleness cost) at the same censorship-proofness guarantee, or a higher censorship-proofness margin at the same fallback window.

### C4 — Empirically, OEV in tokenized-RWA lending is concentrated at band-edge events
Using Aave + Kamino historical liquidations against Soothsayer's reconstructed historical bands, OEV (proxy: liquidation bonus minus competitive-bid floor) is concentrated in the subset of events where the realised liquidation price exits the served band. This is the empirical analogue of the heavy-tail finding in Andreoulis et al., and it is what makes calibration disclosure economically material rather than just theoretically clean.

---

## 5) Explicit non-claims (guardrails)

Paper 2 should *not* claim:
- Universal welfare dominance of band-aware mechanisms across all auction formats.
- That calibration disclosure eliminates OEV (it shifts the rent-extraction frontier; it does not collapse it to zero).
- That builder-searcher coalition concentration is solved by calibration disclosure alone (Andreoulis et al. show this is structural).
- Anything about MEV channels other than the oracle-update channel: sandwich attacks, JIT liquidity, and front-running of orderbook flow are out of scope.
- Optimality without explicit auction-format and information-structure assumptions. The paper makes parameterised claims, not universal ones.

---

## 6) Formal problem statement (minimal version)

### 6.1 Objects
- **Time:** discrete epochs $t = 1, 2, \ldots$ corresponding to oracle update windows.
- **Oracle output at epoch $t$:** $\mathcal{O}_t = (\hat P_t, L_t, U_t, q_\text{served}, \rho_t, r_t)$ where $r_t$ is the audit receipt asserting empirical coverage at $q_\text{served}$ for regime $\rho_t$. The opaque-oracle baseline emits only $\hat P_t$.
- **Position state:** for each borrower $i$, a tuple $(c_i, d_i, \text{LTV}_i, \text{LT}_i)$ of collateral, debt, current LTV, and liquidation threshold.
- **Realised price:** $P_t^\text{true}$ revealed to the protocol via the oracle's next read or via a path-aware truth model (cf. Paper 3 §12.5).

### 6.2 Players
- **Protocol** (the mechanism designer): chooses a mechanism $\mathcal{M}$ specifying the auction format, the trigger rule, and the rebate split.
- **Borrower** (passive): incurs cost from spurious or punitive liquidation.
- **Searchers / liquidators** $\{S_1, \ldots, S_K\}$: each holds a private model $\mu_k(\cdot)$ producing an estimate of $P_t^\text{true}$ given the public oracle output and history.
- **Builder** (block constructor): orders transactions and may collude with a subset of searchers (vertical integration, per Andreoulis et al.).

### 6.3 Mechanism
A mechanism $\mathcal{M}$ is a tuple $(\text{Trigger}, \text{Auction}, \text{Rebate}, \text{Fallback})$:
- **Trigger:** a function $g(\mathcal{O}_t, \text{state}) \to \{0, 1\}$ that decides whether a position is eligible for liquidation. Point-trigger: $g = \mathbb{1}[\hat P_t \cdot c_i / d_i < \text{LT}_i]$. Band-trigger: $g$ depends on $\hat P_t$ relative to $[L_t, U_t]$ and on a multi-epoch persistence count.
- **Auction:** a one-shot mechanism (first-price, second-price, or order-flow) that assigns liquidation rights to the highest-bidding searcher and produces a transfer.
- **Rebate:** a split of the auction proceeds across protocol, borrower, builder, and searcher.
- **Fallback:** a rule for what happens if no searcher participates within a window (the OURW concept).

### 6.4 Welfare measure
Define protocol welfare as
$$W(\mathcal{M}) = \mathbb{E}\bigl[\,\text{rebate to protocol} - L_\text{spurious} \cdot \mathbb{1}[\text{spurious liquidation}] - L_\text{missed} \cdot \mathbb{1}[\text{missed liquidation}]\,\bigr]$$
parameterised by spurious-liquidation cost $L_\text{spurious}$ and missed-liquidation cost $L_\text{missed}$. The mechanism design problem is $\max_\mathcal{M} W(\mathcal{M})$ subject to a participation constraint for searchers and a censorship-proofness constraint on builders.

### 6.5 Information structure
The opaque-oracle baseline gives searchers $(\hat P_t, \text{history})$ as public information; their private signal is $\mu_k$. The calibration-transparent variant gives searchers $(\hat P_t, [L_t, U_t], q_\text{served}, \rho_t, r_t, \text{history})$ as public information; the private signal $\mu_k$ now lives strictly inside the band, since by construction $P_t^\text{true} \in [L_t, U_t]$ with empirical probability $q_\text{served}$.

This information-structure shift is the formal hook for all four claims.

---

## 7) Mechanism families to compare

At minimum:
- **M0 — Opaque first-price liquidation auction (status quo baseline).** Aave/Compound-style: anyone can call `liquidationCall`; price priority.
- **M1 — Chainlink-SVR top-of-block auction with opaque oracle.** Flashbots integration, top-of-block priority, refund to protocol.
- **M2 — Andreoulis-style OURW with opaque oracle.** Refund + fallback window mechanism with censorship-proofness inequality.
- **M3 — Band-conditional auction with calibration receipts (Soothsayer × OURW).** Same auction format as M2 but with band-conditional triggers and a censorship-proofness inequality re-derived under transparent oracle.
- **M4 — Calibration-band-tail trigger.** Trigger fires only on $N$-of-$M$ band exits; auction format identical to M2/M3.

All five mechanisms share a common rebate split for comparability; the paper sweeps the split as a sensitivity dimension.

---

## 8) Welfare measure and "truth semantics"

This is the same trap as Paper 3 §8 — what counts as the "right" liquidation outcome must be named explicitly:

- **Solvency-truth:** liquidation is correct iff the realised endpoint price puts the position below the protocol's liquidation threshold.
- **Path-aware truth:** liquidation is correct iff the *worst executable price* during the liquidation window puts the position below threshold (the same path-aware truth Paper 3 requires).
- **Welfare-truth:** the mechanism's outcome is correct iff the realised social welfare (protocol + borrower + ecosystem) under the assigned action exceeds the counterfactual under no-action.

These three definitions can disagree, and the paper should report sensitivity across all three.

---

## 9) Evaluation protocol (minimum credible)

### 9.1 Theoretical analysis
Under stated assumptions on the searcher private-model distribution, derive equilibrium bid distributions and expected searcher rents for M0–M4. Prove C1 (rents weakly decreasing in band sharpness) and the conditional version of C2.

### 9.2 Simulation
Build an agent-based simulator instantiating M0–M4 with parameterised searcher count, builder concentration, refund rate, and fallback window. Calibrate to historical Aave V2/V3 + Kamino liquidation data 2023–2026 plus Soothsayer's reconstructed bands on the same window.

### 9.3 Empirical reconstruction
Replay historical liquidations under each mechanism using observed bid stacks (Flashbots transparent mempool data + Solana Jito bundle reconstruction) and Soothsayer historical bands. Compute counterfactual welfare under M3 vs M0/M1/M2 baseline. This is the empirical analogue to C4.

### 9.4 Sensitivity grid
Every headline result reported across:
- searcher count and builder concentration
- refund-rate split
- fallback-window length (for OURW-style mechanisms)
- band sharpness (Soothsayer's published $q_\text{served}$ and bandwidth)
- truth semantics (solvency / path-aware / welfare)

### 9.5 Uncertainty
Block-bootstrap on the historical liquidation panel; ranking-stability under resampling; sensitivity analysis on the calibration-band reconstruction.

---

## 10) Existing repo artifacts we can reuse

This is the big difference from Paper 3 — Paper 2 is more theoretical and has fewer existing artifacts.

### Available now
- **Soothsayer historical band serving** (Paper 1 deliverable). Reconstructable bands on 5,986 weekend windows × 10 symbols.
- **`scripts/run_protocol_compare.py`** can be partially adapted to evaluate mechanism-level welfare in addition to policy-level welfare.
- **Historical liquidation data** for Aave V2/V3 (Andreoulis et al. published the 2023–2025 panel; we should request access or reconstruct from on-chain).
- **Kamino xStocks liquidations** since launch — small N but the most directly relevant venue.

### Needs to be built
- **Auction simulator.** New tool: parameterised agent-based simulator for M0–M4 with builder/searcher coalition modelling.
- **Solana Jito bundle reconstruction.** V5 forward-cursor tape (started 2026-04-24) is the input source; need a reconstructor that maps liquidation transactions to bid stacks.
- **Counterfactual welfare engine.** Replay historical liquidations under each mechanism using the simulator and observed bid stacks.

The auction simulator is the load-bearing build. Without it, the paper is purely theoretical and reviewers will (rightly) ask for empirical grounding.

---

## 11) Practical OEV-mechanism landscape (and why each maps onto a Paper 2 comparator)

Production systems are converging fast. The paper should anchor each mechanism family to a specific deployed comparable so the contribution reads as additive, not abstract.

### 11.1 Chainlink SVR — opaque oracle + top-of-block auction
Smart Value Recapture (Chainlink + Flashbots, 2024). Auctions the right to perform the first liquidation immediately after a Chainlink oracle update at the top of an Ethereum block; refunds to the protocol. The oracle is a black box. **Maps to M1 in our taxonomy.**

### 11.2 RedStone Atom — opaque oracle + atomic auction
Atomic OEV auctions from RedStone (2024–2025); the auction is atomic in the sense that price update + liquidation execute in a single bundle. Reduces the gap between oracle update and liquidation execution. **Maps to M1 with a tighter atomicity guarantee.**

### 11.3 API3 OEV / Order Flow Auctions
First-party oracle with explicit order-flow auctions; up to 80% of OEV proceeds redistributed in API3 token. Documented in [api3-oev-litepaper] and the Burak Benligiray Medium series. **Maps to M1/M2 hybrid: order-flow rather than top-of-block.**

### 11.4 UMA Oval
MEV recapture for lending dApps that consume UMA price feeds; integrates with Flashbots. **Maps to M1 with UMA-specific oracle staleness assumptions.**

### 11.5 Andreoulis et al. OURW
Theoretical mechanism: Oracle Update Rebate Window with explicit censorship-proofness inequality. Empirical evidence on Aave V2/V3 2023–2025. **Maps directly to M2; the band-aware variant we propose is M3.**

### 11.6 Soothsayer × OURW (proposed M3)
The novel contribution. Replaces the opaque-oracle assumption in OURW with a calibration-transparent oracle and re-derives the censorship-proofness inequality, the trigger rule, and the welfare comparison.

### 11.7 Calibration-band-tail trigger (proposed M4)
A simpler deployment-ready variant: instead of restructuring the auction, modify only the trigger rule. Liquidation eligibility requires an $N$-of-$M$ band exit at the served $\tau$. Compatible with any auction format, including M0. The minimum-viable calibration-aware mechanism.

### 11.8 Comparator table (for the paper)

| Mechanism | Oracle assumption | Auction format | Censorship-proofness | Soothsayer-compatible? |
|---|---|---|---|---|
| M0 — `liquidationCall` baseline | Opaque price | First-price, on-demand | None | Yes (degraded) |
| M1 — Chainlink SVR | Opaque price | Top-of-block, sealed | Top-of-block ordering | Yes (drop-in) |
| M2 — Andreoulis OURW | Opaque price | Refund + fallback window | Inequality on (refund, window, builder) | Yes (drop-in) |
| **M3 — Soothsayer × OURW** | **Calibration-transparent** | Refund + fallback window with band-conditional triggers | Tightened inequality; band-aware fallback | **Native** |
| **M4 — Tail-trigger overlay** | **Calibration-transparent** | Any (M0/M1/M2) | Inherits from base mechanism | **Native overlay** |

---

## 12) What new evidence Paper 2 must add

### 12.1 Equilibrium analysis for M3 and M4
Closed-form (or numerical) equilibrium results for searcher bid distributions and protocol welfare under each mechanism. C1 and the rent-monotonicity result are theoretical claims that need a proof.

### 12.2 Simulator-based welfare comparison
Agent-based simulation under realistic searcher-count and builder-concentration parameters, with parameter sweeps. Output: welfare-dominance regions for each mechanism family.

### 12.3 Empirical replay on Aave + Kamino historical panels
Counterfactual welfare reconstruction under M0–M4 using observed historical liquidations and Soothsayer historical bands. Output: realised welfare delta per mechanism, with bootstrap confidence intervals.

### 12.4 Sensitivity of the OURW inequality to band sharpness
A formal restatement of the Andreoulis et al. censorship-proofness inequality with the published band as a parameter. Show how the inequality slackens as the band tightens. This is the load-bearing C3 evidence.

### 12.5 At least one reviewer-bait robustness check
Likely candidate: re-run the empirical comparison on a non-Solana, non-Aave venue (Compound on Ethereum, or Morpho on Base) to show the result is not Solana- or Aave-specific. Reviewers will ask.

---

## 13) Success criteria

I would consider Paper 2 ready to draft when we can show:
- A theoretical result establishing C1 (rent monotonicity in band sharpness) under named auction-format and information-structure assumptions.
- Simulation evidence that M3 strictly dominates M2 in expected protocol welfare across a robust region of (searcher count, builder concentration, refund rate, fallback window) parameters.
- Empirical evidence on at least one historical lending-protocol panel that band-conditional triggers (M4) reduce spurious-liquidation rates without raising missed-liquidation rates beyond a stated threshold.
- A formal restatement of the OURW censorship-proofness inequality with the band as a parameter, plus simulation evidence that the inequality tightens monotonically.
- A clear description of where the dominance fails (assumption-sensitive regions) without undermining the core claim.

---

## 14) Concrete next steps (research execution order)

1. **Build the auction simulator** (the load-bearing artifact). Parameterised M0–M4 with builder/searcher coalition modelling. Validate against the Andreoulis et al. M2 numerical results as a sanity check.
2. **Reconstruct Soothsayer historical bands on the Aave/Kamino liquidation panel.** Cross-reference Paper 1's served-band artifacts with the historical liquidation timestamps.
3. **Derive the equilibrium analysis for C1.** Closed-form under stylised assumptions; numerical under richer ones.
4. **Restate the OURW inequality with band as a parameter.** Direct extension of Andreoulis et al. §3–§4.
5. **Run the empirical replay.** Counterfactual welfare under each mechanism, with bootstrap CIs.
6. **Write the draft.** Theory section first, simulation second, empirical third.

This order produces a paper whose strongest claim is theoretical (C1), whose most surprising claim is empirical (C4), and whose most deployment-relevant claim is the simulation-backed mechanism comparison.

Estimate: 4–6 months solo part-time to ready-to-draft; 6–9 months to submission. The auction simulator is the rate-limiting build.

---

## 15) Draft abstract + introduction skeleton

### 15.1 Working abstract skeleton

Existing oracle-extractable-value (OEV) recapture mechanisms — Chainlink SVR, RedStone Atom, API3 OEV, UMA Oval, and the OURW framework of Andreoulis et al. — share a common abstraction: the oracle is a price-emitting black box, and the mechanism's job is to redirect liquidation rents from searcher-builder coalitions back to the protocol or borrower. We study how this abstraction breaks under a recently deployed class of *calibration-transparent* oracles that publish empirically calibrated price bands and audit-receipted coverage SLAs alongside the served price.

We formalise the OEV mechanism-design problem with the calibration band as public information. We show, under stated assumptions on the searcher private-model distribution, that searcher information rents are weakly decreasing in band sharpness; that band-conditional liquidation triggers strictly dominate point-conditional triggers in expected protocol welfare over a robust region of cost and book assumptions; and that the censorship-proofness inequality of the OURW mechanism slackens monotonically as the published band tightens, allowing shorter fallback windows at the same censorship-proofness margin.

We complement the theoretical results with an agent-based simulation calibrated to historical Aave V2/V3 and Kamino tokenized-stock liquidations 2023–2026 against reconstructed Soothsayer bands. We document that historical OEV in tokenized-RWA lending markets is concentrated at band-edge events, validating that calibration disclosure is economically material rather than just theoretically clean.

The paper's contribution is therefore a re-derivation of OEV mechanism design under an explicit transparency assumption, plus empirical evidence that the resulting mechanisms strictly dominate opaque-oracle counterparts in protocol welfare on the deployment data we have.

### 15.2 Alternate abstract opening sentence options

- **Theory-first:** Existing OEV-recapture mechanisms assume the oracle is a price-emitting black box; we redo the mechanism design under the assumption that the oracle publishes its calibration band as a first-class output.
- **Empirical-first:** Historical OEV in tokenized-RWA lending markets is concentrated at oracle-band-edge events, suggesting that the rent extracted by liquidators is in part a private-information rent that calibration disclosure could collapse.
- **Production-first:** A new generation of oracles — calibration-transparent, audit-receipted — is deploying on Solana for tokenized RWAs; the OEV-recapture mechanisms designed for opaque-oracle systems leave welfare on the table when applied to these feeds.

### 15.3 Introduction skeleton

#### Intro ¶1 — The OEV problem and its current solutions
Open with the now-mature OEV-recapture mechanism literature: Chainlink SVR, RedStone Atom, API3 OEV, UMA Oval, OURW. State that these systems are deployed and have non-trivial empirical effects, citing the Andreoulis et al. result that OEV in Aave 2023–2025 is large, heavy-tailed, and concentrated in builder-searcher coalitions.

#### Intro ¶2 — The shared abstraction these mechanisms make
Name the abstraction explicitly: the oracle is a price-emitting black box. Mechanism design is about redirecting rents *given* an opaque feed. The auction format varies (top-of-block, atomic, order-flow); the abstraction does not.

#### Intro ¶3 — The transparency assumption that breaks the abstraction
Introduce calibration-transparent oracles (Paper 1 / Soothsayer). The published output is not a single price but a tuple $(\hat P_t, [L_t, U_t], q_\text{served}, \rho_t, r_t)$ with a verifiable empirical-coverage receipt. State that this is not a hypothetical: the design is deployed on Solana for tokenized US equities since mid-2026 and is the target consumer interface for the new generation of RWA-collateral lending protocols.

#### Intro ¶4 — Why the transparency assumption matters
Three mechanisms by which the band changes the game:
- searcher private-model rents shrink as the public band tightens
- protocols can specify band-conditional triggers that are richer than point-conditional triggers
- censorship-proofness arguments for OURW-style mechanisms tighten

#### Intro ¶5 — Paper 2's formal question
State the question in one sentence: given a calibration-transparent oracle, what auction-and-trigger mechanism maximises protocol welfare relative to the opaque-oracle baseline? Introduce the four claims and the welfare measure.

#### Intro ¶6 — Main results
- C1 — Calibration disclosure shrinks searcher information rents in equilibrium
- C2 — Band-conditional triggers can dominate point triggers in expected protocol welfare
- C3 — Band-aware OURW achieves censorship-proofness at lower fallback-window cost
- C4 — Empirically, OEV in tokenized-RWA lending is concentrated at band-edge events

#### Intro ¶7 — Evaluation design
Theoretical analysis + agent-based simulation calibrated to historical liquidation panels + empirical replay on Aave V2/V3 + Kamino. Sensitivity across truth semantics, builder concentration, refund split, fallback window.

#### Intro ¶8 — Contributions
- A formal re-derivation of OEV mechanism design under transparency
- A theoretical rent-monotonicity result and a band-conditional welfare-dominance result
- A re-derived OURW censorship-proofness inequality with band as a parameter
- An empirical demonstration that band-edge events are where OEV concentrates

#### Intro ¶9 — Scope and non-claims
No claim about MEV channels other than the oracle channel. No claim that calibration disclosure eliminates OEV. No claim about builder-coalition concentration as a structural problem. The paper extends OEV mechanism design under one specific assumption shift.

### 15.4 Sentence-level material worth reusing

- "Existing OEV mechanism-design literature is written under one shared assumption: that the oracle is a price-emitting black box."
- "When the oracle publishes its calibration band as a first-class output, the searcher's private-information advantage collapses inside the band, and the auction game changes."
- "Paper 1 asks whether a served band is calibrated. Paper 2 asks how OEV auctions should be designed to consume that band. Paper 3 asks what a lending protocol should do with the resulting (band, auction) primitive."
- "The censorship-proofness inequality of OURW is not a property of the OURW mechanism; it is a property of the OURW mechanism *given an opaque oracle*. The inequality slackens monotonically as the oracle's published band tightens."

---

## 16) Citation map for the draft

### 16.1 Abstract
At most one or two anchor citations. Strongest candidate: **Andreoulis et al. (2026)** [andreoulis-fair-oev] establishing OEV's empirical magnitude in production lending markets — same role Kamino plays in Paper 3.

### 16.2 Introduction

#### Existing OEV mechanism literature
- **[andreoulis-fair-oev]** — primary academic anchor; OURW model + Aave V2/V3 empirics.
- **[chainlink-svr]** Chainlink Smart Value Recapture announcement / docs (2024).
- **[redstone-atom]** RedStone Atom auction docs and OEV blog series.
- **[api3-oev-litepaper]** API3 OEV litepaper (api3dao/oev-litepaper).
- **[uma-oval]** UMA Oval product announcement.
- **[chorus-oev]** Chorus One survey "An introduction to OEV" for a non-academic but well-organised landscape view.

#### The shared abstraction
- **[flashboys-2]** Daian et al. 2020 (already in Paper 1 references) — establishes the broader MEV framing.
- **[sok-oracles]** Eskandari et al. (already in Paper 1 references) — for the opaque-oracle assumption baked into existing oracle-design surveys.

#### Calibration-transparent oracles (Paper 1)
- **[soothsayer-paper-1]** Self-reference. The deployed Soothsayer system and its calibration evidence.
- **[allen-tail-2025]** Tail-calibration framework — relevant when the band sharpness assumption interacts with tail behaviour.

### 16.3 Related work

#### Shelf A — OEV-recapture mechanisms
- **[andreoulis-fair-oev]** — central reference; OURW model + empirics.
- **[chainlink-svr]**, **[redstone-atom]**, **[api3-oev-litepaper]**, **[uma-oval]** — production landscape.
- **[chorus-oev]** — non-technical landscape survey.
- API3 academic blog series by Burak Benligiray for additional context.

Job: establish the existing mechanism design space and its shared opaque-oracle abstraction.

#### Shelf B — Auction theory and mechanism design under information asymmetry
- **[krishna-auction-theory]** Krishna, *Auction Theory* (textbook reference).
- **[myerson-1981]** Myerson, optimal auction design.
- **[bulow-klemperer-1996]** Bulow & Klemperer — when adding a bidder dominates optimal mechanism design.
- **[milgrom-weber-1982]** Milgrom & Weber — affiliated values + linkage principle (relevant: published band reduces winner's curse).

Job: ground the rent-monotonicity result (C1) in standard mechanism-design theory.

#### Shelf C — Censorship-proofness and proposer-builder separation
- **[andreoulis-fair-oev]** — primary; their inequality is what we extend.
- **[heimbach-pbs]** literature on proposer-builder separation and builder competition.
- **[wadhwa-ofa]** order-flow auction papers from Flashbots and others.

Job: justify the censorship-proofness framing and connect to recent Ethereum mechanism literature.

#### Shelf D — Empirical liquidation studies
- **[gudgeon-2020]** DeFi protocol risk-modelling and liquidation behaviour.
- **[qin-cefi-defi]** empirical studies of CeFi/DeFi liquidation cascades.
- **[andreoulis-fair-oev]** as the most current empirical reference.

Job: motivate the empirical replay design and ground the heavy-tail OEV claim.

### 16.4 Problem statement / model section
- **[andreoulis-fair-oev]** for OURW notation.
- **[krishna-auction-theory]**, **[myerson-1981]** for the auction-format taxonomy.
- **[soothsayer-paper-1]** for the oracle output structure.

### 16.5 Theoretical results section
- **[milgrom-weber-1982]** — anchor for the rent-monotonicity proof (linkage principle).
- **[bulow-klemperer-1996]** — comparison-style result if we extend C1 to "more searchers" vs "tighter band".
- **[myerson-1981]** — for the optimal-auction reference point.
- **[allen-tail-2025]** — when the band tightness assumption interacts with the high-$\tau$ ceiling.

### 16.6 Simulation / empirical section
- **[andreoulis-fair-oev]** — for the M2 numerical sanity check.
- **[chainlink-svr]**, **[redstone-atom]** — for production-mechanism parameter estimates (refund rate, top-of-block latency).
- Aave V2/V3 protocol docs and Kamino docs for liquidation-bonus parameters.

### 16.7 Discussion / deployment recommendations
- Production-mechanism citations again, for the comparison table.
- **[soothsayer-paper-1]** for the deployment-readiness argument.

### 16.8 Anti-bloat rules for citation use
- Production OEV mechanism citations belong in the introduction and related work, not buried.
- Auction-theory citations belong in the theoretical-results section, not the introduction.
- Do not duplicate Paper 1's bibliography; rely on a single forward citation to Paper 1 for the oracle primitive.
- Do not pad with generic "DeFi adoption" citations; every citation should establish a live production fact, support a modeling choice, or anchor a methodological claim.

---

## 17) Open questions to resolve before writing

These are explicit forks the planning document leaves unresolved; the user should pick a fork before starting Section 6 and Section 12 work.

1. **Auction format choice for M3.** First-price sealed-bid? Second-price? Order-flow? Each implies a different equilibrium analysis; the "right" choice is the one closest to deployed M1/M2 mechanisms, which suggests sealed first-price + top-of-block ordering.
2. **Builder-coalition modelling depth.** Andreoulis et al. model coalitions in reduced form. We should match their treatment unless there's a specific reason to extend it.
3. **Empirical-replay venue selection.** Aave V2/V3 (Andreoulis-replicable, large N) vs Kamino (deployment-target, small N) vs both (best). Cost-benefit: doing both is the right answer; the marginal cost is mostly engineering on the Solana Jito reconstructor.
4. **Whether to publish the auction simulator as a standalone artifact.** Likely yes — it's a small open-source release that carries reputational weight independent of the paper, and slots into the consultancy/risk-research positioning from the broader career strategy.
5. **Target venue.** ACM AFT 2026 (DeFi-friendly, fast cycle), ACM EC 2027 (mechanism-design canonical), Financial Cryptography 2027 (RWA-friendly), or arXiv-only as a research-program signal. AFT seems strongest fit; EC if the theoretical results land cleanly.
