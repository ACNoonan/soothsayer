# Solana Foundation Grant — Band-Edge OEV in Tokenized-RWA Lending

**Working title:** *Empirical Oracle-Extractable-Value Concentration at Band-Edge Events in Solana Tokenized-Stock Lending — A Public Dataset and Mechanism-Design Analysis.*

**Submitter:** Adam Noonan (Soothsayer / Samachi).
**Status:** internal one-pager draft, 2026-04-25.
**Target program:** Solana Foundation grants — research / public-good infrastructure track.
**Ask:** $50k for a 4-month deliverable (range $25k–$100k justifiable).

---

## 1. One-sentence pitch

Build the first public **xStocks-on-Kamino + MarginFi liquidation dataset** with reconstructed calibration-transparent oracle bands, publish empirical findings on whether oracle-extractable value (OEV) concentrates at oracle-band-edge events, and specify a band-conditional auction overlay on Pyth Express Relay that, if adopted, eliminates the very rent the dataset documents. Deliverables: an open dataset, an open-source reconstructor, a peer-reviewable paper, and a mechanism-design memo to Pyth and Kamino. The public dataset and reconstructor are the primary artifact; the mechanism memo is the deployable follow-through.

### Why this fits a Solana Foundation grant

This proposal is a good fit for the Foundation because it finances a public-good artifact the private market is unlikely to produce on its own:

- **Open infrastructure, not a closed trading edge.** The core deliverables are a dataset, reconstructor, paper, and mechanism memo released under permissive licenses.
- **Direct relevance to a live Solana problem.** The work targets tokenized-stock lending, Pyth Express Relay, Jito bundles, and the protocols where Solana already has real deployment stakes.
- **Measurable ecosystem outcome.** Success is not "we think the mechanism is better"; success is a public panel, a testable empirical result, and a deployable specification for reducing OEV rents.
- **Honest technical scope.** Paper 1 already identifies the current system's boundaries. The grant funds the next research step with those boundaries treated as milestones rather than hidden caveats.

---

## 2. Hypothesis

> **H₀ (null):** OEV captured by liquidator-builder coalitions on Solana lending protocols is uniformly distributed across realised price moves, conditional on liquidation-eligibility being triggered. Whether the realised liquidation price falls inside or outside a calibration-transparent oracle band has no effect on the size of the rent extracted.
>
> **H₁ (alternative, our prediction):** OEV is **strictly larger** at oracle-band-edge events — i.e., when the realised price exits a calibration-transparent oracle's served band — than at within-band events of comparable nominal size. The information asymmetry between liquidator and protocol/borrower is largest precisely at the edge of the oracle's published uncertainty, and that asymmetry is the rent.

If H₁ is supported empirically, then:
- (a) **Calibration-transparent oracles strictly dominate opaque-oracle systems** in protocol welfare under reasonable mechanism design — a deployable result the Solana DeFi stack can act on.
- (b) **A band-conditional auction overlay on Pyth Express Relay** (the deployed Solana-native OEV recapture system) can recapture a measurable fraction of currently-extracted OEV and return it to protocols/borrowers.
- (c) The result is the **first empirical confirmation of the oracle-transparency-as-mechanism-improvement thesis** on a deployed system, complementing Andreoulis et al. (2026) on Aave V2/V3 and providing the Solana cross-check that does not currently exist.

### Retrospective evidence (2026-04-25)

H₁ is not a conjecture — it has been measured retrospectively on the 12-year Soothsayer Paper 1 dataset (5,986 weekend windows × 10 symbols), with the headline numbers derived on the **post-2023 OOS slice** (1,720 rows × 172 weekends; calibration surface was *not* fit on this period):

| Metric | Value (τ = 0.95, OOS) |
|---|---|
| Median per-event liquidator pricing edge — band-exit events | **$26,787 per $1M notional** |
| Median per-event liquidator pricing edge — in-band events | $7,516 per $1M notional |
| **Dominance ratio (band-exit / in-band median)** | **3.56×** |
| Band-exit event frequency (panel-scale) | **~21 events/year** |
| **Annual band-aware-vs-band-blind liquidator advantage at $1M working notional** | **$283,745** |
| Realised coverage at τ = 0.95 (OOS) | 96.0% |

Full analysis: [`reports/band_edge_oev_oos_counterfactual.md`](../reports/band_edge_oev_oos_counterfactual.md) and companion [`reports/band_edge_oev_analysis.md`](../reports/band_edge_oev_analysis.md). The grant funds a *deployed* test of this retrospective: instrumenting xStocks-on-Kamino + MarginFi liquidations against reconstructed Soothsayer bands to confirm whether the predicted ~3.5× dominance ratio holds on real liquidation events — and to specify the band-conditional auction overlay that captures it.

### Why the current statistical gaps strengthen the grant case

Paper 1's current boundary conditions are precisely the reason this grant is worth funding rather than a reason to defer it. The present Soothsayer system is already a meaningful improvement over stale / opaque off-hours oracle designs, but the diagnostics also say exactly what V2 must improve: the per-anchor buffer is still heuristic rather than theorem-backed; Berkowitz rejects, so the system is not yet a full-distribution-calibrated density forecast; DQ rejects, so residual multi-lag conditional structure remains in the hit sequence; and there is no live Solana deployment window yet. The grant turns those from paper-side disclosures into a funded research program on the chain where the deployment stakes are real.

Concretely, the same infrastructure needed for the band-edge OEV panel also closes the main Paper 1 follow-ups:

- **Live deployment window.** Running the band-aware reconstructor and liquidation tape in production yields the first consumer-experienced coverage evidence rather than a backtest-only read.
- **MEV-aware calibration.** The bundle-level reconstruction needed for Paper 2 also lets us measure the gap between venue-reference coverage and consumer-experienced coverage near band edges.
- **On-chain signal upgrades.** The xStocks / Pyth / Kamino tape is the missing dataset for validating an `F_tok` forecaster that consumes tokenized-stock prices directly rather than treating them as future work.
- **Rolling rebuilds.** A grant-funded live window is the natural place to re-measure `BUFFER_BY_TARGET` on a schedule and test whether the current heuristic can be replaced by a more stable continuous correction.
- **Mechanism-design leverage.** If band-edge events are where OEV concentrates, then the same statistical gaps that motivate better calibration also increase the value of a band-aware auction overlay.

For a funder, this is the key point: the proposal does not ask Solana Foundation to underwrite open-ended research exploration. It asks the Foundation to fund a tightly linked package where the same deployment and data-collection work advances (i) a public OEV dataset, (ii) a mechanism-design output for a Solana-native auction surface, and (iii) the next empirical upgrade cycle of the underlying calibration-transparent oracle.

---

## 3. Why this is a Solana-specific public good

- **No comparable dataset exists.** Andreoulis et al. (Springer, MARBLE 2025) published the leading academic OEV panel on Aave V2/V3 across Ethereum and major rollups. There is **no equivalent panel for Solana**. This proposal builds the first one, focused on tokenized-RWA lending where the question is most economically material.
- **Solana is the deployment frontier for tokenized RWAs.** xStocks on Kamino launched 2025-07-14; tokenized-stock total market crossed $1B in March 2026. Solana is where the question has direct economic stakes in 2026, not retrospectively.
- **Pyth Express Relay is the only Solana-native deployed OEV auction.** It is the M1 baseline our analysis runs against and the deployment surface for any band-aware overlay we propose. The grant directly improves a Pyth-developed primitive that the Solana ecosystem already depends on.
- **MarginFi alone produced ~$88.5M in liquidation fees in Q1 2025** — captured by **only ~9 active liquidators**, an Andreoulis-style coalition concentration that is publicly observable on-chain. The economic rent at stake is not hypothetical.
- **Kamino reduced its liquidation penalty to 0.1% in September 2025** — the median event is now unprofitable for solo bots. Whatever rent remains is concentrated in the tail (band-edge) regime, which is exactly the subset our analysis targets.

### 3a. The broader public-good frame: missing infrastructure for the next $10B of RWA on Solana

The dataset + reconstructor + mechanism memo above are the grant's deliverables. The reason they matter beyond xStocks specifically is that they instantiate a piece of public-good infrastructure the broader RWA wave on Solana needs: **a calibration-transparent risk-reporting layer that is auditable against public data, free at the point of consumption, and applicable across asset classes with continuous off-hours information sets**.

The 2025–2026 RWA wave is not just xStocks. Tokenized treasuries (BlackRock BUIDL, Ondo OUSG; collectively > $5B AUM as of submission) are scaling on Solana and elsewhere. Tokenized commodities (Paxos PAXG and forthcoming silver / broader baskets) are following. Tokenized credit and FX are next. Each new class brings the same closed-market pricing question and would benefit from the same primitive — the Soothsayer methodology generalises by construction wherever a continuous off-hours information set exists (futures, vol indices, overseas-session prices, CDS spreads). The per-class fit/no-fit table is in `docs/methodology_scope.md`.

The structural mental model: **Soothsayer is to RWA risk reporting what block explorers are to transaction visibility** — public infrastructure that the ecosystem depends on but that no single private actor produces under current incentives. Block explorers exist because the alternative (every protocol building its own indexer) is wasteful; calibration-transparent risk reporting exists for the same reason: every RWA-issuing or RWA-consuming protocol needs auditable risk evidence, and no incumbent oracle publishes it. Funding the public-good layer once unlocks the entire downstream ecosystem.

This grant is therefore the *concrete first instantiation* (xStocks-on-Kamino + MarginFi, where the data and the empirical question are most tractable) of a broader public-good infrastructure thesis. The dataset and reconstructor architecture are designed to extend to additional asset classes — tokenized treasuries on the same Kamino market, tokenized gold via Paxos PAXG, etc. — without methodology change. Each future extension is a re-fit of the calibration surface on a new `(factor, vol_index)` pair (the switchboard architecture in Paper 1 §5.4 was built for this), not a new methodology.

The honest scope boundary: the methodology does *not* claim universality. Real estate, illiquid agricultural commodities, and pure NAV-update instruments do not satisfy the continuous-off-hours-signal precondition. Those classes need different methodology and are explicitly out of scope for this grant. `docs/methodology_scope.md` carries the four-question structural test that any prospective adopter (Backed, Ondo, Paxos, future tokenized-credit issuers) can use to determine fit in 60 seconds.

---

## 4. Public-good output

All four deliverables released under permissive licenses (MIT for code, CC-BY for dataset/paper). The project is structured so that every milestone leaves behind a reusable ecosystem artifact even if later milestones slip.

1. **Open dataset: `solana-oev-band-edge-2026`.** xStocks-on-Kamino + MarginFi liquidations from 2025-07-14 (xStocks launch) through grant end. Every event labelled with: pre-update Pyth/Switchboard price, post-update price, realised liquidation price, reconstructed Soothsayer band at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$, in-band vs out-of-band classification, realised liquidator profit, builder/searcher identity, Jito bundle metadata.
2. **Open-source liquidation reconstructor.** Solana program logs + Pyth update timestamps + Jito bundle data → liquidation events with bid stacks. Reusable for other Solana lending protocols (Drift, Save, Loopscale).
3. **Empirical paper.** *"Empirical OEV concentration at oracle-band-edge events in Solana tokenized-stock lending."* Targeted at ACM AFT 2026 / FC 2027 / arXiv q-fin.RM. Anchored on the public dataset.
4. **Mechanism-design proposal.** A specification for a band-conditional auction overlay on Pyth Express Relay, with simulation + empirical-replay evidence of welfare dominance over the opaque-oracle baseline. Submitted to Pyth and Kamino for review.

---

## 5. Methodology (4 months)

### Month 1 — Tape and reconstructor
- Extend existing **V5 forward-cursor tape** (started 2026-04-24 in the Soothsayer repo) to capture Kamino + MarginFi program logs, Pyth Express Relay updates, Jito bundles, and Solend/Save liquidation events.
- Build the reconstructor: tape → labelled liquidation event records.
- Validate reconstruction against publicly observable liquidation events (Helius MEV reports, Jito Explorer).

### Month 2 — Soothsayer-band reconstruction on the historical panel
- Apply the deployed Soothsayer calibration surface (12-year backtest, 5,986 weekend windows × 10 symbols, OOS 2023+ Kupiec + Christoffersen pass) to xStocks weekend-reopen liquidation events.
- For each event, compute the served band at the published $\tau$ schedule and label in-band vs out-of-band.
- Produce a labelled panel: (event, pre-update price, post-update price, band, realised profit, in/out-of-band).

### Month 3 — Empirical analysis (the H₀ vs H₁ test)
- Per-event OEV proxy: realised liquidator profit minus competitive-bid floor (estimated from Jito bundle data).
- Test H₀ vs H₁: compare OEV distribution conditional on band-exit vs within-band, controlling for nominal liquidation size, time-of-day, regime.
- Bootstrap CIs on the OEV-conditional-on-band-exit difference.
- Sensitivity: across $\tau \in \{0.68, 0.85, 0.95, 0.99\}$, across regimes (`normal` / `long_weekend` / `high_vol`), across builder concentration.

### Month 4 — Mechanism-design proposal + writeup
- Specify a **band-conditional auction overlay on Pyth Express Relay**: trigger fires only on $N$-of-$M$ band exits at $\tau = 0.95$ (or per-protocol configured); searcher bid floor includes a band-derived public-information component to reduce information rents.
- Counterfactual welfare replay: realised welfare under M1-SOL (status quo Pyth Express Relay) vs M3 (band-aware overlay) vs M4 (tail-trigger overlay) on the historical panel.
- Paper draft + dataset documentation + Pyth/Kamino briefing materials.

---

## 6. Timeline + milestones

| Month | Deliverable | Verification |
|---|---|---|
| 1 | Reconstructor v0.1 + tape pipeline live | ≥30 reconstructed liquidation events match public Helius/Jito Explorer records byte-for-byte |
| 2 | Labelled historical panel (xStocks since 2025-07-14, BTC/SOL since tape start) | Per-event band reconstruction reproducible from `data/processed/v1b_bounds.parquet` |
| 3 | H₀-vs-H₁ test result with bootstrap CIs | Result reported regardless of sign; publication-grade sensitivity grid |
| 4 | Paper draft + open dataset + mechanism-design memo to Pyth/Kamino | arXiv submission ready; dataset on HuggingFace + Solana Foundation repository |

Each milestone produces a public artifact released under permissive license; failure to reach a milestone does not block release of work-to-date. This is deliberate de-risking for the funder: the grant does not hinge on a single all-or-nothing paper outcome.

---

## 7. Budget

Total ask: **$50,000** (4 months × $12,500/month). Range $25k (lower-bound) to $100k (full-time equivalent at standard junior-quant-research rate).

**Public-good justification.**
- **First Solana OEV panel.** Andreoulis et al. (Springer, MARBLE 2025) is the leading academic OEV dataset for Aave V2/V3 across Ethereum and major rollups. There is no equivalent for Solana. The grant produces the cross-chain comparator the OEV-research conversation is actively waiting for, anchored on the chain where tokenized-RWA lending has the largest 2026 deployment surface.
- **Deployable mechanism leverage.** The dataset is not the end-state; it grounds a concrete, deployable upgrade (band-conditional overlay) to Pyth Express Relay, the Solana-native OEV auction every major Solana lending protocol either uses or evaluates. Welfare improvement is measurable on the same panel the grant produces.
- **Researcher subsidy already paid.** Phase 0 (methodology pivot, calibration surface, two paper drafts, ablation suite) was completed self-funded on $0 by 2026-04-25. The grant accelerates work already in motion, not work being started cold. The retrospective §2 evidence ($283,745/yr/$1M notional band-aware advantage at τ=0.95, OOS) is the empirical motivation for the live test, not a profit projection for the funder.
- **Lower-bound vs upper-bound.** $25k delivers the xStocks-only dataset, reconstructor, and paper. $50k adds the mechanism-design memo and the Pyth/Kamino briefing materials. $100k extends the dataset to Drift / Save / Loopscale, materially broadening Solana lending-stack coverage.

| Category | Amount | Justification |
|---|---|---|
| Researcher time (~50% FTE × 4 months) | $32,000 | Solo researcher; covers methodology, paper, and open-source release |
| Solana RPC infrastructure (Helius/Triton paid tier) | $8,000 | $2k/mo × 4 months; required for V5 tape and reconstructor |
| Working capital for liquidator instrumentation | $5,000 | Test capital for ground-truth liquidation event capture; net P&L flows to runway |
| Compute (data processing, simulation) | $3,000 | Cloud GPU/CPU for backtest and reconstruction at scale |
| Conference / dissemination (AFT 2026 or FC 2027) | $2,000 | Publication-related travel or registration |

If awarded the lower bound, the conference + working-capital buckets are first to scale down. If awarded the upper bound, additional researcher time goes into a Drift/Save/Loopscale extension of the dataset.

---

## 7a. Sustainability and sunset

The project is structured as a public-good ecosystem artifact with an explicit three-phase lifecycle:

1. **Grant period (4 months).** Solana Foundation funds the dataset, reconstructor, paper, and mechanism-design memo. All four deliverables ship under permissive licenses (MIT for code, CC-BY for dataset and paper).
2. **Post-grant maintenance.** Ongoing operating costs — RPC, dataset hosting, occasional reconstructor updates as Kamino / MarginFi / Pyth iterate — are expected to be modest relative to the main build. Preferred path is low-cost maintenance of the public artifact itself; if parallel instrumentation work later produces surplus, that surplus is ringfenced to ecosystem operating costs rather than researcher compensation. If no such surplus exists, dataset hosting falls back to the HuggingFace free tier and the reconstructor enters maintenance-only mode (event schema frozen; breaking-change patches at best-effort cadence).
3. **Sunset by design.** The mechanism-design memo this grant produces specifies a band-conditional auction overlay on Pyth Express Relay. If that overlay is adopted, the value of private band-edge extraction should compress. The dataset and reconstructor remain as the public historical artifact of what OEV looked like before the fix and as a baseline for future Solana mechanism work.

The success criterion for the public-good deliverable is therefore not the durability of any private strategy. It is whether the ecosystem ends up with a reusable dataset, a verified measurement layer, and a concrete mechanism proposal that compresses opaque band-edge rents.

---

## 8. Track record

- **Paper 1 — *Empirical coverage inversion: a calibration-transparency primitive for decentralized RWA oracles*.** In submission (target: arXiv q-fin.RM + ACM AFT 2026). Status: §1/§2/§3/§6/§9 drafted, 40-reference §2 survey verified; §4/§5/§7/§8 + coherence review in flight. Phase 0 PASS-LITE: held-out Kupiec + Christoffersen passes at $\tau \in \{0.68, 0.85, 0.95\}$ on 1,720 OOS rows / 172 weekends.
- **Paper 2 (this grant's primary academic output) — planning artifact at [`reports/paper2_oev_mechanism_design/plan.md`](../reports/paper2_oev_mechanism_design/plan.md).** Hypothesis, claims (C1–C4), mechanism families (M0–M4), formal model, and citation map already drafted; this grant funds the empirical C4 evidence and the deployment-side C3 mechanism specification.
- **Paper 3 — *Optimal liquidation-policy defaults under calibrated oracle uncertainty*.** Planning artifact at [`reports/paper3_liquidation_policy/plan.md`](../reports/paper3_liquidation_policy/plan.md); existing protocol-compare scaffolding (`scripts/run_protocol_compare.py`).
- **Engineering rigor.** Soothsayer Python reference + Rust port at byte-for-byte parity (75/75 tests pass). Methodology-history append-only log at [`reports/methodology_history.md`](../reports/methodology_history.md). Walk-forward + diagnostics + grid extension + macro-regressor ablation completed Tier-1 engineering pass on 2026-04-25.
- **Solana ecosystem ties.** Active Superteam Solana participant; existing Helius + RPC Fast keyed access; planned devnet deployment in Phase 1 (4 weeks); Kamino-fork consumer demo in scope.

---

## 9. Risk register (honest)

- **R1 — H₀ is supported (band-edge effect is null or small).** Mitigated by pre-registration: the paper publishes regardless of sign. A null result is still a valid public-good contribution and a meaningful constraint on Paper 2's mechanism-design claim.
- **R2 — Sample size on xStocks is too small.** xStocks launched 2025-07-14; by grant start there will be ~9 months of liquidation data. Mitigated by: (a) extending the panel to BTC, SOL, and other liquid Kamino/MarginFi collateral for power, (b) reporting xStocks-specific results separately as the deployment-target analysis.
- **R3 — Pyth Express Relay's auction specifics are partly opaque.** Mitigated by direct outreach to Pyth Data Association (open-source contributors are responsive); we will document any API uncertainty in the dataset README and in the paper.
- **R4 — Solo-researcher bandwidth.** The Soothsayer Phase 1 work (devnet deploy + Paper 1 finish + Paper 3 first draft) is concurrent. Mitigated by: 4-month timeline includes ~50% FTE bandwidth, and Paper 2 mechanism-design (theoretical) work is sequenced after this grant rather than in parallel.

### Funder read on risk

The proposal is intentionally structured so that the downside cases still produce useful public goods:

- If the effect is smaller than expected, the Foundation still gets the first Solana OEV panel.
- If the mechanism overlay is not yet deployable, the Foundation still gets the measurement layer that future teams can build on.
- If xStocks-specific power is limited, the panel still generalises to other Kamino / MarginFi collateral and keeps xStocks as the headline deployment case.
- If the final output is "only" a strong paper plus open dataset, that is still a meaningful ecosystem artifact for a grant in the research/public-goods bucket.

---

## 10. Why now

- xStocks-on-Kamino has been live for ~9 months by the time this grant could start; sufficient liquidation events to measure but recent enough that the dataset is a first-mover artifact.
- Pyth Express Relay is actively iterating; a band-aware overlay proposal lands in a moment where the team is open to upgrades rather than locked in.
- Kamino's Sep 2025 penalty drop to 0.1% is a structural change that *concentrates* rent at the band edge — making the H₁ test sharper than it would have been against the pre-Sep-2025 economics.
- Andreoulis et al. (2026) just provided the academic baseline this work cites against; Solana cross-check is the natural follow-up the OEV-research conversation is currently waiting for.
- The Soothsayer trilogy (Paper 1 → Paper 2 → Paper 3) lands its strongest deployment story in 2026 if Paper 2's empirical evidence is from a deployed Solana system rather than a theoretical EVM extension.

---

## 11. Submission packet (next steps)

- [ ] Confirm Solana Foundation's current grants programme intake (open-grants vs convertible-grant route).
- [ ] Convert this one-pager into the foundation's specific proposal template.
- [ ] Letter of support from Pyth Data Association (target: open-source contributor / research lead) — strengthens the deployment-relevance argument and accelerates Pyth Express Relay API access.
- [ ] Letter of support from Kamino BD (target: tokenized-RWA / risk lead) — strengthens the deployment-target argument and pre-validates the dataset's relevance.
- [ ] Cross-link from `reports/paper2_oev_mechanism_design/plan.md` and `docs/ROADMAP.md` Phase 1 funding section.

---

## Appendix A — Optional parallel instrumentation

The highest-leverage optional extension is **running a narrow xStocks-weekend-reopen liquidator instrument in parallel as an auxiliary data-collection path**. This is explicitly secondary to the grant deliverables: the dataset is the artifact, not the bot.

If run, the instrument could:

- (a) generate ground-truth bid-stack observations rather than reconstructed-from-logs estimates;
- (b) provide an additional deployment-side check that the Soothsayer band is usable as a liquidator pricing input;
- (c) offset a portion of operating costs that would otherwise come out of general project runway.

Pre-registration commitment: if any such instrument is run, its P&L and empirical hit rate are reported alongside the paper's findings. If it fails to capture OEV at band-edge events, that null result is reported. If it succeeds, it strengthens the deployment story. Either way, it remains auxiliary to the public dataset and measurement layer the grant is funding.
