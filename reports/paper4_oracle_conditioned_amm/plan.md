# Paper 4 Plan — Oracle-Conditioned AMMs for Tokenized RWA Pools on Solana

**Status:** planning document (internal). Drafted 2026-04-27.
**Working title (TBD):** *Calibration-Conditioned Liquidity: An Auditable LVR-Recovery Mechanism for Tokenized-RWA AMM Pools on Solana.*

**Relationship to Papers 1, 3, 4:**
- **Paper 1** establishes that an oracle's *calibration claim* on the served band can be made auditable from public data (the empirical-coverage-inversion primitive).
- **Paper 3** is the lending-protocol policy capstone: given a calibrated band, what should the protocol's liquidation defaults be?
- **Paper 4 (this paper)** extends the calibration-transparency primitive to the **AMM execution layer**, with the contribution being a derivable, audit-grade LVR-recovery lower bound for tokenized-RWA pools during closed-market windows.

The firm thesis is two-arc: a **lending arc** (Papers 1/3) and an **AMM arc** (Paper 4). Both share the calibration-transparency primitive applied to different protocol surfaces. The AMM arc is one paper, not two — what was originally sketched as a separate empirical Paper 4 is folded into §3–§4 of this paper, with the dataset shipping as a HuggingFace release + technical report. (See `feedback_publication_depth.md`.)

---

## 1) One-sentence thesis

**A BAM Plugin AMM that conditions execution on a calibration-transparent oracle band exposes a derivable LVR-recovery lower bound for tokenized-RWA pools during closed-market windows, where both the oracle's calibration claim and the Plugin's compliance with that bound are independently verifiable from public data.**

The contribution is the auditable bound, not the absolute LVR-recovery number. Following Paper 1's discipline: the auditable primitive is the contribution; the absolute value is empirical and contested.

---

## 2) Research question

### Primary question
**Given a calibration-transparent oracle that serves the band primitive validated in Paper 1, what AMM execution mechanism on Solana CLMMs handling tokenized-RWA pools admits an auditable LVR-recovery lower bound in closed-market windows, and what does the bound look like as a function of disclosed quantities?**

### Sub-questions
- How does realized LVR on RWA AMM pools partition between in-market windows (where Pyth's regular-hours feed is the integrity primitive) and closed-market windows (where Soothsayer's calibration-transparent band is the reference)? *Conjecture: closed-market windows dominate.*
- Does the σ²/8·V approximation systematically mispredict closed-market RWA LVR, and in what direction?
- Is realized closed-market LVR bundle-conditional in the sense Paper 4's first sketch hypothesized (bimodal — bundle slots capture, non-bundle slots don't)?
- What functional form of the bound `g(q, ρ, f_min, band_width, σ)` is consistent with the empirical surface, and is it non-trivial in the parameter range observed?

### What this is *not*
- A general LVR-aware AMM proposal — Angstrom, CoW AMM, am-AMM, FM-AMM occupy that design space; this paper is specifically about **calibration-conditioned execution for RWA closed-market windows**.
- An AMM proposal for non-RWA pools (deferred to (β) expansion, gated on market adoption signal — see §13).
- A welfare-optimality claim in deployment (requires live data).
- A measurement paper of all Solana AMM LVR (the empirical foundation is RWA-pool-only at v1).

---

## 3) The conceptual gap Paper 4 closes

The deployed and academic LVR-aware AMM literature treats the oracle as either absent (LVR is measured against an external CEX reference and the mechanism is oracle-blind) or as a black-box price feed that informs the mechanism but doesn't expose calibration claims:
- **Angstrom** (Sorella Labs, 2025) — Uniswap v4 hook, batch-clearing arb-recapture, oracle-blind.
- **CoW AMM / FM-AMM** (Canidio & Fritsch) — batch-auction LVR-recovery proof on a single per-block clearing price.
- **am-AMM** (Adams et al., FC 2025) — auction the LP role, oracle-blind.
- **Pyth-anchored CLMMs (hypothetical on Solana)** — would consume Pyth `price ± conf`, but Pyth's confidence is documented as an aggregation diagnostic and empirically under-covers by ~10× at face value (Paper 1 §2.1 + `reports/v1b_pyth_comparison.md`).

The conceptual gap: **an AMM whose LVR-recovery rate is bounded below by a function of the oracle's published calibration claim, with both the bound and the mechanism's compliance with it verifiable on-chain**. No deployed or proposed AMM does this. The Soothsayer calibration receipt is the input the Plugin consumes; BAM's TEE-attested ordering is the on-chain enforcement primitive that closes the audit chain; the bound `g(·)` is the contribution.

The literature has reached this design point but stops at the manipulability caveat. Anthony Lee Zhang summarising Milionis et al.: *"AMM LPs lose money from price slippage: when Binance prices move, AMM quotes become 'stale'. An obvious solution is that if AMMs updated price quotes when Binance prices move, LVR would be reduced. This is quite tricky to implement in practice — it requires a very high-frequency oracle, and is vulnerable to oracle manipulation attacks — but in theory with a perfectly fast and non-manipulable oracle, this could eliminate LVR."* The "vulnerable to oracle manipulation" caveat is precisely what a *band* (rather than a point) is designed to neutralise: manipulation that pushes the served price within calibrated band edges should not trigger fee-free arb, because the band is the calibration claim's confidence region rather than a manipulable point. Paper 4's Plugin specification is the unbuilt design point the literature has reached but no Solana production AMM has shipped.

This is the Paper 1 audit-chain primitive translated to the AMM layer: Paper 1 says "the band is calibrated to τ"; Paper 4 says "given the calibrated band, the AMM's LVR-recovery is bounded below by `g(τ, ρ, f_min)`; both the band's calibration and the Plugin's compliance with `g(·)` are independently verifiable."

---

## 4) Draft claims

**Discipline note (data-first):** empirical claims are conditional on what the foundation phase measures and are reported regardless of sign. Listed here as the falsifiable structure the paper aims to populate, not as pre-registered findings.

### Theoretical claims (provable from disclosed primitives)

**C1 — The bound exists.** Given a Soothsayer band $[L_t, U_t]$ served at quantile $q$ with regime $\rho_t$, and a measured Jito tip distribution implying per-slot arb floor $f_{\min}(t)$, the proposed BAM Plugin's per-slot LVR-recovery rate is bounded below by a function $g(q, \rho, f_{\min}, w_t, \sigma_t)$ — where $w_t$ is the band width and $\sigma_t$ is realised volatility — that is computable from public data. The bound is derived in a stylised model where Plugin behaviour is fully specified.

**C2 — The bound is non-trivial.** $g(\cdot)$ implies meaningful LVR recovery in the parameter range Phase A measures on Solana RWA pools. (Non-triviality is conditional on empirical findings; the theoretical statement is "a non-trivial bound is derivable"; the empirical statement is C4 below.)

**C3 — The bound is auditable.** A third party with access to (i) the Soothsayer calibration surface + receipt, (ii) on-chain pool state, (iii) BAM TEE attestations, and (iv) public Jito bundle data can verify post-hoc that the Plugin delivered $\geq g(\cdot)$ over any time window. This is the **audit-chain claim** — calibration-transparency at the AMM layer.

### Empirical claims (data-first; reported regardless of sign)

**E1 — Closed-market concentration.** Realised LVR on Solana RWA CLMM/DLMM pools (xStock pairs on Orca / Raydium / Meteora) is concentrated in closed-market windows (weekend-reopen, overnight). Shape and magnitude reported.

**E2 — σ²/8·V misprediction.** The continuous-time σ²/8·V approximation systematically mispredicts realised LVR in closed-market RWA windows. Direction and magnitude reported.

**E3 — Bundle-conditional realisation.** The fraction of closed-market LVR captured by Jito-bundle-arbed slots vs non-bundle slots is reported. The conjecture is bimodality (bundle slots capture, non-bundle slots don't); the empirical finding tests this directly. **Subject to bundle-attribution-rate disclosure** (§12 R3).

### Mechanism-empirical bridge

**C4 — Plugin LVR-recovery on the panel.** The Plugin's counterfactual LVR-recovery rate on the historical panel — what the mechanism would have delivered if it had been the venue — is reported alongside `g(·)`. C4 is C2 evaluated on the empirical foundation.

---

## 5) Explicit non-claims

- Welfare optimality in deployment.
- Dominance over Angstrom or am-AMM on a matched basis (different chains, different microstructures, not directly comparable).
- Production-readiness without live deployment.
- Generalisation to non-RWA pools (see §13: (β) expansion gated on market signal).
- That LVR is the dominant LP cost on RWA pools — IL and spread costs may dominate; this paper measures LVR specifically as the load-bearing component for the bound, and reports the LVR / IL / spread decomposition as a disclosure-grade finding.

---

## 5.5) Scope filter — which RWA classes Paper 4 covers

Paper 4's mechanism is meaningful only on RWA classes where two conditions both hold: (1) there is an **exogenous true price the AMM cannot observe directly** — so the calibrated band has informational content beyond the pool's own marginal price; and (2) that price has **time-varying uncertainty large enough to matter** — so the band width is regime-dependent and the LVR-recovery bound $g(\cdot)$ is non-trivial in the regimes that matter.

This is the same four-question filter that `docs/methodology_scope.md` applies to the oracle layer; the AMM layer inherits the constraint by construction because the Plugin's only input is the calibrated band. Two failure modes follow:

- **Pure-crypto pairs (SOL/USDC, ETH/USDC) fail (1).** The AMM *is* a primary price-discovery venue, not a follower of an exogenous reference, so there is no "true price" the band can be calibrated against. The bound $g(\cdot)$ has no input.
- **Stablecoin pairs / LSTs fail (2).** Implied uncertainty is near-deterministic; the band collapses toward the point estimate; $g(\cdot)$ reduces to a no-op and the mechanism is dominated by simpler designs (Curve-style stable swaps; LST AMMs that consume on-chain stake state directly).

The natural set Paper 4 targets:

| Asset class | Exogenous price? | Time-varying uncertainty? | Paper 4 relevance |
|---|---|---|---|
| Tokenized US equities (xStocks) | Yes — NASDAQ / NYSE | Huge — nights, weekends, halts | **Primary** |
| Tokenized commodities with closed sessions (oil, ags) | Yes — CME / ICE futures | Significant | **Primary** |
| Tokenized non-US equities (LSE / TSE / HK) | Yes — overseas venues | Significant per region | Primary, gated on data accumulation |
| Tokenized FX | Yes — regional sessions | Modest — 24/5 weekly close | Secondary |
| Tokenized gold | Yes — COMEX | Modest — 23/5 | Secondary |
| Tokenized treasuries | Yes — Treasury futures | Low — well-modelled | Out of scope; mechanism advantage too small |
| LSTs (jitoSOL, mSOL) | NAV from validator state | Deterministic | Out of scope |
| Pure crypto (SOL/USDC, ETH/USDC) | None — AMM is price discovery | n/a | Out of scope |

The (β) gates in §13 govern *expansion beyond RWA pools entirely* (i.e., applying the mechanism to crypto-native pools despite condition (1) failing); the table above governs *which RWAs the methodology applies to within the RWA scope*. Both are scope filters at different abstraction levels and do not contradict each other.

This narrowing is a feature: it forces the paper to compete only on terrain where the calibration-conditioned mechanism has a structural edge over oracle-blind CFMMs, and aligns Paper 4's domain with the same domain where Papers 1 and 3 have already validated the oracle and policy primitives.

---

## 6) Formal problem statement (minimal)

### 6.1 Objects
- **Time:** discrete slots $t = 1, 2, \ldots$ aligned to Solana slot boundaries.
- **Oracle output at slot $t$:** $\mathcal{O}_t = (\hat P_t, L_t, U_t, q, \rho_t, r_t)$ where $r_t$ is the calibration receipt. The opaque-oracle baseline emits $\hat P_t$ alone (B0); the Pyth-anchored baseline emits $(\hat P_t, \text{conf}_t)$ as a publisher-dispersion diagnostic (B1).
- **Pool state:** $(x_t, y_t, \text{fee tier})$ for each underlying CLMM/DLMM.
- **Realised truth:** path-aware — the worst executable price at the next venue open during a closed-market window (matching Paper 3 §8 path-aware truth semantics).

### 6.2 Plugin specification
At slot $t$, the Plugin reads $\mathcal{O}_t$, the pool state, and the observed Jito tip distribution. It emits:
- A **standard-fee band** $[L_t, U_t]$: trades that move price within the band execute at the AMM's standard fee.
- A **scaled-fee tier** for trades that move price outside the band, with the scaling derived from band-width and disclosed $q$.
- An **outside-band auction** sequenced via the BAM Plugin: trades that exit the band trigger an intra-slot auction whose proceeds are routed to LPs.

The BAM TEE attestation per slot verifies the Plugin executed as specified, producing the cryptographic receipt that makes C3 enforceable.

**Oracle-update cadence assumption.** The Plugin's specification and the bound $g(\cdot)$ are stated under a *sub-second* oracle-update assumption, matching the cadence Pyth Pro (formerly Pyth Lazer; cf. canonical [`docs/sources/oracles/pyth_lazer.md`](../../docs/sources/oracles/pyth_lazer.md)) and RedStone Bolt are shipping in 2026, not the 30-second cadence implicit in earlier oracle-conditioned AMM sketches. (Per the canonical doc, regular-Pyth slot cadence is ~400ms — already sub-second; Pyth Pro adds subscriber-customizable cadence whose specific values are not surfaced in the public overview.) The cadence enters the bound through the per-slot freshness term in $g(q, \rho, f_{\min}, w_t, \sigma_t)$ — at sub-second cadence the band-edge race is between the Plugin's outside-band auction and the next builder slot, so the bound is tight; at multi-block cadence the auction window is dominated by oracle staleness and the bound degenerates. Phase A measures both regimes (cf. §9.1) so the cadence-sensitivity of $g(\cdot)$ is reported, not assumed.

### 6.3 LVR-recovery rate
Per slot, define $\text{LVR}(t)$ as the rebalance-portfolio-value gap against the realised-truth price (path-aware). The Plugin's LVR-recovery rate is the fraction of $\text{LVR}(t)$ that the Plugin redirects to LPs vs. lets escape to searchers/builders. The mechanism design problem is to maximise expected LVR-recovery subject to (a) participation constraints for LPs and bundle searchers, (b) a censorship-proofness constraint on builders, and (c) the calibration receipt being an honest signal under Paper 1's coverage assumption.

### 6.4 The bound
$g(q, \rho, f_{\min}, w_t, \sigma_t) = $ a closed-form (or numerically-evaluable) lower bound on per-slot Plugin LVR-recovery rate, derived from the Plugin's specification + the published oracle quantities + the measured Jito tip distribution. **The functional form is data-first**: Phase A's empirical surface dictates which terms in $g(\cdot)$ are dominant and whether the bound has a closed form or only a numerical evaluation.

---

## 7) Mechanism families to compare

- **B0 — Status-quo CLMM** (Orca / Raydium / Meteora baseline). Oracle-blind, standard CLMM execution.
- **B1 — Pyth-anchored CLMM** (hypothetical). Reads Pyth $(\hat P, \text{conf})$ and applies a fee scaling. Empirical baseline shows Pyth's `conf` is an aggregation diagnostic, so the implied calibration is consumer-supplied; the v1b benchmark (`reports/v1b_pyth_comparison.md`) measures the gap.
- **B2 — Calibration-conditioned CLMM via BAM Plugin** (the proposed mechanism). Reads the Soothsayer band + receipt; applies band-conditional execution; routes outside-band auction revenue to LPs.
- **B3 — Calibration-conditioned CLMM with bundle-aware reopen auction.** Adds a closed→open transition auction sequenced via BAM Plugin specifically for the weekend-reopen / overnight-reopen RWA windows. **B3 is the natural extension if E3 supports bimodality** — the reopen auction is the mechanism that captures the gap-realisation slice.

The paper compares B0–B3 on the empirical foundation panel and reports per-mechanism LVR-recovery rate against `g(·)` as a tightness check.

---

## 8) Truth semantics and known traps

LVR truth on RWA pools is genuinely harder than on SOL/USDC pools because the canonical LVR definition (Milionis et al.) assumes a continuously-tradable reference, which doesn't exist during closed-market windows by construction. The paper uses two truth proxies:

- **(a) Path-aware truth at next open.** The worst executable price at the next venue open. Used in C1's bound derivation. This is the harder test (you have to wait for the open) and is the one that connects to Paper 3's path-aware truth framing.
- **(b) Soothsayer-served band as closed-market reference.** Used in real-time mechanism execution. Available at every slot but is the band, not a point.

Both are reported; the gap between (a) and (b) is the closed-market analogue of Paper 1 §9.12's MEV-aware-coverage gap and is documented as a disclosure-grade finding.

---

## 9) Evaluation protocol

### 9.1 Phase A — Empirical foundation (~6–9 months)
- **Panel:** xStock CLMM/DLMM pools on Orca / Raydium / Meteora, post-xStocks-launch (2025-07-14) through panel end. Top pools by TVL and weekend-window N.
- **Data:** slot-resolution swap data, pool state, Pyth update timestamps, Jito bundle data, Soothsayer band reconstruction at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$.
- **Validator-client labelling per slot** (BAM / Jito-Agave / Frankendancer / vanilla) for the bundle-conditional analysis. **Power caveat:** RWA-pool slice may be small enough to limit statistical power on the BAM-vs-non-BAM stratification — disclosure-grade if so, headline if not.
- **Oracle-cadence stratification.** Slot-resolution capture of Pyth Pro (formerly Lazer) / Pyth pull / Pyth Hermes / RedStone Bolt update timestamps so per-mechanism evaluation can be reported at *each cadence regime* (sub-second, ~400ms-block, multi-block). The default reporting axis is sub-second since that is the production trajectory; the multi-block regime is included as a degeneracy benchmark and as backwards-compatibility for any consumer protocol still wired to a 30s feed. This replaces the implicit 30s-update assumption used in earlier oracle-conditioned AMM sketches.
- **CEX reference for in-market windows** (Binance + Coinbase + OKX) for cross-validation of the Soothsayer band.
- **Output artefacts:** technical report + HuggingFace dataset under CC-BY (matching grant Milestone 2's licensing).

### 9.2 Phase B — Theoretical analysis (~3 months, partial overlap with A)
- Specify the Plugin formally (Anchor / Rust sketch).
- Derive `g(·)` from the Plugin specification + the empirical surface — the **functional form is shaped by Phase A's findings**, not pre-committed.
- Prove C1 in a stylised model with disclosed assumptions.
- Numerical evaluation of `g(·)` on the Phase A panel for the C2 / C4 statement.

### 9.3 Phase C — Counterfactual replay (~3 months)
- Replay the historical panel under B0 / B1 / B2 / B3.
- Compute realised LVR-recovery rate per mechanism per slot.
- Compare to `g(·)` as a **tightness check** — does the bound bind, or is the realised mechanism well above the bound? Both findings are interesting.

### 9.4 Sensitivity grid
- $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ (Soothsayer's served quantiles).
- Regime $\rho \in \{\text{normal}, \text{long-weekend}, \text{high-vol}\}$ — matching Paper 1's regime labelling.
- Bundle-attribution-rate sensitivity — treat unattributed slots as either full-arb or zero-arb endpoints.
- Validator-client mix — BAM-share variation across the panel; per-quarter stratification.
- Truth semantics — (a) path-aware-at-next-open vs (b) Soothsayer-band-as-reference.

### 9.5 Uncertainty
- Weekend-window block-bootstrap (matching Paper 1 v1b methodology).
- Sensitivity on the calibration-band reconstruction.
- Ranking-stability across resamples for the B0–B3 ordering.

---

## 10) Existing repo artefacts to reuse

### Available now
- **Soothsayer calibration surface** (Paper 1 deliverable) — the band primitive the Plugin consumes.
- **V5 forward-cursor on-chain tape** (live since 2026-04-26) — extended to capture pool state + bundle attribution.
- **Weekend-window methodology + block-bootstrap apparatus** (Paper 1) — directly applicable to closed-market LVR measurement.
- **Methodology evolution log** (`reports/methodology_history.md`) — append-only convention transferred to Paper 4 work.
- **xStock token list + pool registry** — same pools as the grant lending-side panel; reuses the same token universe.
- **Pyth Hermes benchmark** (`scripts/pyth_benchmark_comparison.py`) — directly reusable as the B1 baseline.

### Needs to be built
- **Pool-state reconstructor:** V5 tape → CLMM/DLMM pool state at slot resolution (Orca / Raydium / Meteora).
- **Bundle-attribution → RWA pool LVR labels:** integrates with the grant Milestone 1 reconstructor (lending side), reuses the Jito bundle parsing, adds AMM pool state.
- **Path-aware truth labeller:** realised-truth-at-next-open for closed-market slot windows.
- **BAM Plugin reference implementation** (Anchor / Rust). Open-sourced as a research artefact, not a production-ready Plugin.
- **Counterfactual replay engine:** replays panel under B0–B3 and computes per-mechanism LVR-recovery.
- **Mechanism simulator (validation pass):** stylised model + numerical `g(·)` evaluation; validates the C1 derivation against the replay.

---

## 11) Risks / load-bearing assumptions

- **R1 — Empirical findings may not support a strong mechanism contribution.** Data-first means we don't know in advance whether *RWA-pool* LVR is large enough to make the Plugin economically interesting. The aggregate magnitude is materially de-risked: independent analyses size the Solana CLMM/DLMM ecosystem at roughly $400M–$2B in annualised LP fees (10–30 bp blended on $400–700B annualised volume) with similar-order LVR leakage; even capturing a single-digit percent of LVR back to LPs on the volatile-RWA subset is in the tens of millions of ARR (cf. `market-research.md` §Layer 1). The residual R1 risk is therefore narrow: how much of that aggregate concentrates on the *RWA subset* of the panel during the Phase A window. *Mitigation:* report E1–E3 regardless of sign; if RWA-pool LVR is small relative to crypto-pair LVR, the paper's contribution shifts toward the audit-chain primitive (C1 + C3) and the magnitude becomes a deferred (β)-expansion question rather than a load-bearing claim. The paper still lands as the first auditable LVR-recovery bound applied to RWA AMM pools, even if the realised RWA-subset LVR is modest.
- **R2 — RWA pool TVL / volume may be too small for statistical power.** xStock pools are early-deployment; panel may be N = hundreds of weekend-windows × handful of pools. *Mitigation:* weekend-window block-bootstrap is well-suited to small N (Paper 1 used the same apparatus on similar N); explicit power analysis pre-registered.
- **R3 — Bundle-attribution rate on RWA pools may be poor.** RWA pool bundle activity is smaller than SOL/USDC; attribution may be incomplete. *Mitigation:* explicit attribution-rate disclosure + sensitivity grid (§9.4); E3's bimodality finding must be robust to the disclosed attribution gap.
- **R4 — BAM stake share evolves during the panel.** Late-2025 launch → growing stake share through 2026; Alpenglow consensus shift possibly arrives mid-panel. *Mitigation:* per-quarter stratification or explicit regime-break section; tighten the panel window to a single regime if the break is material.
- **R5 — Plugin SDK maturity.** BAM Plugin docs are still solidifying as of April 2026. *Mitigation:* not a paper blocker — the reference implementation is a research artefact; production-readiness is explicitly Paper 5+ scope. If the SDK changes, the Plugin specification adapts; the bound `g(·)` is invariant under SDK changes that preserve the calibration-receipt + TEE-attestation primitives.
- **R6 — Off-anchor calibration of `g(·)` is gated on a PIT-uniformity check, not a planned model upgrade.** Paper 1 v1 calibrates at discrete anchor τ ∈ {0.68, 0.85, 0.95, 0.99}; `g(·)` is therefore only formally bounded at those τ values without further evidence. Soothsayer V2.4 (`docs/v2.md` §V2.4) is the **diagnostic** — a Kolmogorov-Smirnov test on the full PIT distribution — that reports whether calibration is uniform across τ. *Two outcomes:* (a) PIT-uniformity holds → anchor calibration generalises and `g(·)` is bounded across the full τ range; (b) PIT-uniformity fails → `g(·)` is stated explicitly as anchor-only with off-anchor disclosed as a limitation, and a separate (not-currently-planned) model change is required to lift the limitation. *Mitigation:* sequence the V2.4 diagnostic before Paper 4's Phase B starts so the bound's scope is known before `g(·)` is derived.
- **R7 — Oracle-update cadence vs Solana block production.** LVR-minimising AMMs are tight when the oracle is faster than the underlying market and degenerate when it is slower. Pyth Pro (formerly Lazer) and RedStone Bolt are racing to sub-second updates as of 2026; the Plugin specification (§6.2) and `g(·)` are therefore stated against sub-second cadence, not the 30-second cadence implicit in earlier oracle-conditioned AMM sketches. *Mitigation:* §9.1 stratifies Phase A measurement by cadence regime (sub-second / ~400ms-block / multi-block) so the cadence-sensitivity of the realised mechanism vs `g(·)` is reported, not assumed; the bound's degeneracy at multi-block cadence is a disclosure-grade finding, not a paper blocker.

---

## 12) Sequencing and dependencies

- **Soothsayer V2.4 PIT-uniformity diagnostic** (`docs/v2.md` §V2.4) — load-bearing for the *scope* of `g(·)`, not a model fix. Determines whether the bound is anchor-only or full-τ. Already on the firm roadmap as a paper deliverable.
- **Paper 1** must be on arXiv; **Paper 3** plan should be substantive — Paper 4 cites both as upstream.
- **Grant deliverables** (Papers 2/3 + reconstructor + dataset) ship before Paper 4 begins in earnest. The V5 tape extensions for the grant are inputs to Paper 4's empirical foundation; the lending-side reconstructor and the AMM-side pool-state reconstructor share most of their parser surface.
- **Earliest plausible Paper 4 timeline:** post-grant Milestone 4 (~4 months from grant kickoff) → Phase A begins → ~6–9 months data → Phase B/C ~6 months → arXiv submission ~16–18 months from grant kickoff. This is firm-thesis work, not on the grant's critical path.

---

## 13) (β) expansion gates

The user's principle: deploy on RWA, prove value, build market trust; expand only if market signals insufficient adoption. Formalised as gates for advancing Paper 4's panel beyond RWA pools:

- **G1 — Adoption signal from at least one Solana RWA-pool DEX** (Orca / Raydium / Meteora) acknowledging or piloting the calibration-conditioned mechanism. Either a public reference to the methodology or a testnet pilot suffices.
- **G2 — Citation / replication signal** — at least one external research group references or replicates the Phase A measurements.
- **G3 — Market-failure signal** — RWA AMM pools fail to attract LP capital in volumes that justify the mechanism, suggesting the value proposition is too narrow at the RWA-only scope.

If G1 or G2 fires, expansion to (β) is justified offensively (the work has traction; broaden the contribution). If G3 fires, expansion is justified defensively (the RWA-only scope is too small to matter; broaden to demonstrate generality). Absent any of the three, the firm holds the focused scope.

---

## 14) Open planning questions for next iteration

1. **The functional form of `g(·)`.** Data-first commits us to letting Phase A shape it, but a rough sketch helps decide what Phase A *must* measure to make the bound non-trivial. Worth a separate planning artefact once Phase A starts.
2. **The Plugin specification at the slot level.** Anchor / Rust sketch — what the Plugin actually does on read. The fee schedule, the band-conditional branch, the outside-band auction routing.
3. **Pyth-Express-Relay vs standalone BAM Plugin.** Pyth Express Relay is moving toward BAM. The reopen-window auction (B3) may be more natural as a Pyth-Express-Relay extension than as a standalone Plugin rather than a separate surface. Worth resolving before §6.2 is finalised.
4. **Title.** "Calibration-Conditioned Liquidity" vs "Oracle-Conditioned AMMs" vs "Auditable LVR-Recovery Bounds for RWA AMMs" — the framing affects venue selection (AFT vs ICML/NeurIPS-financial vs Paradigm/Flashbots).

---

## 15) Non-grant scope

This paper is **not** part of the Solana Foundation grant proposal. The grant covers the lending arc (Papers 2/3 deliverables: dataset + reconstructor + paper + mechanism memo on Pyth Express Relay). Paper 4 is firm-thesis post-grant work, sequenced after the grant deliverables ship. Treating this work as in-scope for the grant would dilute the public-good framing the grant is built on (open dataset, open reconstructor, deployable mechanism overlay) and over-extend the proposal beyond what's defensible at the current methodology and deployment maturity.

If Paper 4 lands well, the natural follow-on is a **Paper 5 live-deployment companion** — a partner DEX runs the Plugin in production, measurements compare realised LVR-recovery to `g(·)` over the deployment window, and welfare claims are then defensible. Paper 5 is not planned at this time and is not on the firm roadmap; it would be triggered by §13's G1 (DEX-adoption signal).

---

## 16) Product-stack relationship

Paper 4 is the academic anchor for what `docs/product-stack.md` calls **Layer 1 — the band-AMM (spot)** — the foundational product the Soothsayer oracle layer enables. The product stack identifies three downstream consumers of the same calibrated-band primitive that Paper 4 does *not* address but whose viability depends on Paper 4's empirical foundation:

- **Layer 2 — band-perp.** Synthetic perpetual where mark = band midpoint, liquidation buffer = band edges, funding spikes when band widens during halts. Uses the spot pool as a hedging venue.
- **Layer 3 — band-options / band-vaults.** Calibrated implied volatility derives directly from band width; structured vaults sell or buy band-edge volatility against the spot pool.
- **Layer 4 — settlement / index licensing.** Reference-rate provider for third parties (other perp DEXes, prediction markets) using the calibrated band, independent of whether those third parties consume the AMM.

**Layer-2 competitive geometry (one-paragraph note).** Hyperliquid HIP-3 (with Trade.XYZ as the reference deployer) has, on the evidence to date, won the *generic* equity-perp slot: $25B cumulative volume since Oct 2025, 35% of Hyperliquid volume, an official S&P 500 license, and a continuous orderbook with relayer-oracle ~3s updates (Blockworks Equity Perpetuals Landscape Report, Dec 2025). The wedge for Soothsayer's Layer 2 is therefore not "be a better generic equity perp" — it is *halt-aware* mark and liquidation, and *xStocks-collateralised cross-margin*, which the Blockworks survey explicitly calls out as "promised but unrealised on Solana." The §13 (β) gates and any future Layer-2 paper should pre-commit to that narrower wedge rather than a head-to-head HIP-3 framing; Paper 4's Layer-1 contribution does not depend on Layer 2 winning a venue battle.

The lending-side consumer (Kamino) is covered by **Paper 3**, not by the product stack — soothsayer publishes the oracle, Kamino is the protocol; we do not build a competing lending market.

**Sequencing implication.** Paper 4 must establish the spot-AMM contribution (C1 audit-chain bound + C3 verifiability claim, plus the empirical foundation for E1–E3) before any of Layers 2–4 are publication-grade. The product stack documents the *direction* of the build-out, not a parallel research arc; only Layer 1 has a paper attached at this time.

**Pipeline implication.** The scryer pipelines required for Paper 4's empirical foundation (per-slot CLMM/DLMM pool state, Jito bundle attribution, BAM validator-client labelling) are simultaneously the pipelines required to evaluate Layers 2–4 as products. Standing them up early — even before Paper 4's Phase A formally begins — is therefore both a paper deliverable and a product-decision deliverable. See `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md` for the priority order.

**Phase-A capture urgency.** The window for Paper 4's contribution is open but visibly narrowing: Chainlink's RWA Advanced (v11) schema already surfaces a discrete 6-state session enum (`Unknown / Pre-market / Regular / Post-market / Overnight / Closed-weekend`; canonical [`docs/sources/oracles/chainlink_v11.md`](../../docs/sources/oracles/chainlink_v11.md) §1.2), and Pyth Pro / Pyth Data Marketplace is moving toward institutional-grade calibrated data products (cf. `market-research.md` §0). The probability of an incumbent shipping a calibrated-uncertainty primitive within 18 months is non-trivial; Paper 4's moat is therefore the *empirical receipt* — pool-state + bundle-attribution + cadence-stratified LVR-recovery measurement on RWA pools — and is data-pipeline-bound. Note that v11's wire `bid`/`ask` carry a synthetic `.01`-suffix marker on weekends for SPYx/QQQx/TSLAx (canonical `chainlink_v11.md` §3), so the v11 session enum is a *coarse* coverage signal even where the band itself is non-readable; the moat for Paper 4 is the *continuous calibrated band*, not a finer enum. This reinforces the priority order in `scryer_pipeline_plan.md`: scryer item 51 (`jito_bundle_tape`, `validator_client`, `clmm_pool_state`, `dlmm_pool_state`, `dex_xstock_swaps`) is clock-dependent and should run forward-only from now even though Paper 4's drafting is post-grant.
