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

- **R1 — Empirical findings may not support a strong mechanism contribution.** Data-first means we don't know in advance whether RWA AMM LVR is large enough to make the Plugin economically interesting. *Mitigation:* report E1–E3 regardless of sign; if LVR is small, the paper's contribution shifts toward the audit-chain primitive (C1 + C3) rather than the magnitude (C4). The paper still lands as the first auditable LVR-recovery bound applied to RWA AMM pools, even if the realised LVR is modest.
- **R2 — RWA pool TVL / volume may be too small for statistical power.** xStock pools are early-deployment; panel may be N = hundreds of weekend-windows × handful of pools. *Mitigation:* weekend-window block-bootstrap is well-suited to small N (Paper 1 used the same apparatus on similar N); explicit power analysis pre-registered.
- **R3 — Bundle-attribution rate on RWA pools may be poor.** RWA pool bundle activity is smaller than SOL/USDC; attribution may be incomplete. *Mitigation:* explicit attribution-rate disclosure + sensitivity grid (§9.4); E3's bimodality finding must be robust to the disclosed attribution gap.
- **R4 — BAM stake share evolves during the panel.** Late-2025 launch → growing stake share through 2026; Alpenglow consensus shift possibly arrives mid-panel. *Mitigation:* per-quarter stratification or explicit regime-break section; tighten the panel window to a single regime if the break is material.
- **R5 — Plugin SDK maturity.** BAM Plugin docs are still solidifying as of April 2026. *Mitigation:* not a paper blocker — the reference implementation is a research artefact; production-readiness is explicitly Paper 5+ scope. If the SDK changes, the Plugin specification adapts; the bound `g(·)` is invariant under SDK changes that preserve the calibration-receipt + TEE-attestation primitives.
- **R6 — Off-anchor calibration of `g(·)` is gated on a PIT-uniformity check, not a planned model upgrade.** Paper 1 v1 calibrates at discrete anchor τ ∈ {0.68, 0.85, 0.95, 0.99}; `g(·)` is therefore only formally bounded at those τ values without further evidence. Soothsayer V2.4 (`docs/v2.md` §V2.4) is the **diagnostic** — a Kolmogorov-Smirnov test on the full PIT distribution — that reports whether calibration is uniform across τ. *Two outcomes:* (a) PIT-uniformity holds → anchor calibration generalises and `g(·)` is bounded across the full τ range; (b) PIT-uniformity fails → `g(·)` is stated explicitly as anchor-only with off-anchor disclosed as a limitation, and a separate (not-currently-planned) model change is required to lift the limitation. *Mitigation:* sequence the V2.4 diagnostic before Paper 4's Phase B starts so the bound's scope is known before `g(·)` is derived.

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
