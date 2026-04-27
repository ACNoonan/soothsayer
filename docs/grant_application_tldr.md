# Soothsayer — Solana Foundation Grant Application

> Submission-ready answers in the order the Solana Foundation form asks for them.
> The full proposal — hypothesis, retrospective evidence, methodology, risk register —
> lives in [`docs/grant_solana_oev_band_edge.md`](grant_solana_oev_band_edge.md) and is
> the north-star document this application summarises.

---

## Form fields

| Field | Answer |
|---|---|
| Company / Project name | Soothsayer |
| Website URL | https://soothsayer-landing.vercel.app/ |
| Country | United States |
| First name | Adam |
| Last name | Noonan |
| Email Address | adam@samachi.com |
| Funding category | Research / Public-Good Infrastructure (closest match — open dataset, open-source measurement layer, peer-reviewable paper, and a deployable mechanism-design specification for Pyth Express Relay) |

---

## Your project / idea

**A calibration-transparent fair-value oracle and OEV measurement layer for tokenized real-world assets on Solana.**

Soothsayer is a calibration-transparent oracle primitive for tokenized RWAs. A consumer specifies a target coverage rate τ; the oracle returns the price band that empirically delivered τ on historical data, together with auditable receipts describing how the band was served. The methodology has been validated on 5,986 weekend windows × 10 tokenized-equity tickers, 2014–2026. On a held-out 2023+ slice the deployed serving configuration passes Kupiec + Christoffersen at three of four standard targets, including 95.0% realised coverage at τ=0.95 (Kupiec p_uc = 1.000) and 85.5% at τ=0.85, the deployment default.

The grant converts this working research primitive into a live, public-good Solana measurement layer, anchored on the first publicly available xStocks-on-Kamino + MarginFi liquidation dataset with reconstructed calibration-transparent oracle bands. The output is four open artifacts:

1. **Labelled liquidation panel.** Every Kamino + MarginFi xStocks liquidation event from the 2025-07-14 launch through grant end, labelled with pre-update Pyth/Switchboard price, post-update price, realised liquidation price, reconstructed Soothsayer band at τ ∈ {0.68, 0.85, 0.95, 0.99}, in-band vs out-of-band classification, realised liquidator profit, and builder/searcher identity.
2. **Open-source liquidation reconstructor.** Solana program logs + Pyth update timestamps + Jito bundle data → labelled liquidation event records. Reusable across Drift, Save, Loopscale.
3. **Peer-reviewable paper.** Tests whether oracle-extractable value (OEV) concentrates at oracle-band-edge events vs within-band events of comparable nominal size, on a deployed Solana system.
4. **Mechanism-design specification.** A band-conditional auction overlay on Pyth Express Relay — the only Solana-native deployed OEV auction — with empirical-replay welfare evidence vs the status-quo opaque-oracle baseline.

**Why this matters now.** No equivalent OEV panel exists for Solana. Andreoulis et al. (MARBLE 2025) is the leading academic OEV dataset on Aave V2/V3 across Ethereum and rollups; the Solana cross-check the OEV-research conversation is currently waiting for does not yet exist. Solana is the deployment frontier for tokenized RWAs in 2026: xStocks launched on Kamino 2025-07-14, tokenized-stock total market crossed $1B in March 2026, and MarginFi alone produced ~$88.5M in liquidation fees in Q1 2025 captured by only ~9 active liquidators. The economic rent at stake is large, the data is publicly observable on-chain, and the deployment surface (Pyth Express Relay) is the Solana-native auction primitive every major Solana lending protocol either uses or evaluates.

**Empirical motivation, not projection.** A 12-year retrospective on the same calibration surface (OOS 2023+, 1,720 rows × 172 weekends; calibration not fit on this period) measures a **3.56× dominance ratio** in median per-event liquidator pricing edge between band-exit and in-band events at τ=0.95 ($26,787 vs $7,516 per $1M notional). The grant funds the deployed test of whether this concentration holds on real Solana liquidation events.

Long-form proposal with hypothesis, retrospective tables, methodology, risk register, and sustainability plan: [`docs/grant_solana_oev_band_edge.md`](grant_solana_oev_band_edge.md).

---

## Funding amount

**$50,000 USD**, paid in four equal milestone tranches of $12,500.

Lower bound $25k delivers the xStocks-only dataset, reconstructor, and paper. Upper bound $100k extends the dataset to Drift / Save / Loopscale and materially broadens Solana lending-stack coverage. The $50k midpoint is the smallest amount that delivers all four public-good artifacts (dataset + reconstructor + paper + mechanism-design memo) plus the Pyth/Kamino briefing materials needed for adoption.

Phase 0 (methodology, calibration surface, two paper drafts, ablation suite, Python ↔ Rust parity port) was completed self-funded on $0 by 2026-04-25. The grant accelerates work already in motion, not work being started cold.

---

## Milestones

Milestone-based funding in four tranches of $12,500. Each milestone produces a public artifact released under permissive license (MIT for code, CC-BY for dataset and paper); failure to reach a later milestone does not block release of work-to-date. This is deliberate de-risking: the grant does not hinge on a single all-or-nothing paper outcome.

**Milestone 1 — $12,500 — Liquidation reconstructor + tape pipeline live (estimated time to complete: 1 month).**
- Extend the existing V5 forward-cursor on-chain tape (live since 2026-04-26) to capture Kamino + MarginFi program logs, Pyth Express Relay updates, and Jito bundle metadata.
- Ship the open-source liquidation reconstructor: tape → labelled liquidation event records, with reproducible build instructions and test fixtures.
- **Payment criterion:** ≥30 reconstructed liquidation events match public Helius / Jito Explorer records byte-for-byte; reconstructor repo public under MIT.

**Milestone 2 — $12,500 — Labelled historical panel published (estimated time to complete: 1 month, 2 months elapsed).**
- Apply the deployed Soothsayer calibration surface to xStocks-on-Kamino + MarginFi liquidation events from 2025-07-14 through milestone end; extend to BTC and SOL collateral on the same protocols for statistical power.
- Per-event labelling at τ ∈ {0.68, 0.85, 0.95, 0.99}, plus realised liquidator profit and builder/searcher identity.
- **Payment criterion:** panel published on HuggingFace under CC-BY; per-event band reconstruction reproducible from the open repo with one command; dataset README documents schema, coverage, and known gaps.

**Milestone 3 — $12,500 — H₀ vs H₁ empirical test result (estimated time to complete: 1 month, 3 months elapsed).**
- Test whether OEV concentrates at oracle-band-edge events vs within-band events of comparable nominal size, controlling for nominal liquidation size, time-of-day, and regime.
- Bootstrap CIs on the band-conditional OEV difference; sensitivity grid across τ, regime (`normal` / `long_weekend` / `high_vol`), and builder concentration.
- **Payment criterion:** result reported regardless of sign (pre-registered); publication-grade sensitivity grid; analysis notebook public; H₀-vs-H₁ headline numbers reproducible from a fresh clone in <1 day.

**Milestone 4 — $12,500 — Mechanism-design proposal + paper draft (estimated time to complete: 1 month, 4 months elapsed).**
- Specify a band-conditional auction overlay on Pyth Express Relay; counterfactual welfare replay vs M1 (status quo Pyth Express Relay) on the historical panel.
- Submit paper draft to arXiv q-fin.RM; deliver mechanism-design memo to Pyth Data Association and Kamino risk team; brief Solana Foundation on findings.
- **Payment criterion:** arXiv submission ID issued; mechanism memo URL public; dataset frozen at v1.0 release tag.

---

## Relevant metrics

- **Open dataset adoption.** Dataset downloads on HuggingFace; citations of the dataset on academic preprint servers; distinct downstream consumers reusing the reconstructor (target: ≥3 distinct Solana protocols / risk teams / academic groups in the 12 months post-publication).
- **Reconstruction fidelity.** Byte-for-byte match rate between reconstructed liquidation events and public Helius / Jito Explorer records (target: ≥99%).
- **Empirical reproducibility.** Independent re-runs of the H₀-vs-H₁ test from the public repo produce the same point estimate within Monte-Carlo error (target: anyone can reproduce headline numbers in <1 day from a fresh clone).
- **Mechanism-design adoption signal.** Pyth and Kamino acknowledgement of the mechanism memo; whether either party advances the band-conditional overlay to design-discussion or implementation (binary indicator; reported in good faith regardless of sign).
- **Paper outcome.** arXiv preprint posting (q-fin.RM); submission to ACM AFT 2026 or FC 2027; peer-review status.
- **Ecosystem citation.** External research / risk reports citing the dataset or reconstructor as the canonical Solana OEV panel.

---

## Your experience

Adam Noonan is a software / ML engineer with applied research focus on calibration, conformal prediction, and held-out evaluation. Phase 0 of Soothsayer (early 2026 to 2026-04-25, self-funded on $0) produced a calibration-transparent oracle methodology pivoted to a factor-switchboard + empirical-quantile + log-log-regime architecture, a Python reference implementation with a byte-for-byte-parity Rust port (75/75 tests pass), a 12-year backtest panel (5,986 weekend windows × 10 symbols) with held-out 2023+ Kupiec + Christoffersen evaluation, and two peer-reviewable paper drafts. Paper 1 (*Empirical coverage inversion: a calibration-transparency primitive for decentralized RWA oracles*) is in arXiv-submission state with §1/§2/§3/§6/§9 drafted and a 40-reference §2 survey verified. Paper 2 (the OEV-mechanism-design output of this grant) has a complete planning artifact with hypothesis, claims C1–C4, mechanism families M0–M4, and citation map drafted.

Solana ecosystem experience: active Superteam Solana participant; existing keyed access to Helius and RPC Fast; live V5 forward-cursor on-chain tape running since 2026-04-26; devnet deployment planned for Phase 1; a Kamino-fork consumer demo in scope. The repository is public and reproducible end-to-end — calibration surface, backtest evidence, paper drafts, methodology evolution log, and ablation studies are all under version control with an append-only methodology-history log at `reports/methodology_history.md`.

Engineering rigor: walk-forward buffer-stability analysis, diagnostics (Kupiec, Christoffersen, Berkowitz, DQ), grid extension, and macro-regressor ablation completed Tier-1 engineering pass on 2026-04-25. The known statistical gaps — heuristic per-anchor buffer, Berkowitz reject, DQ reject, no live deployment window — are pre-disclosed in the paper rather than hidden, and the grant deliverables are scoped to address each one. Prior web3 experience includes the public LVR/OEV-adjacent calibration work in a companion repo and active engagement with the Pyth and Kamino developer surfaces. The proposal is intentionally scoped for solo-researcher delivery within the 4-month window at ~50% FTE, with the higher-bandwidth Paper 2 mechanism-design theoretical work sequenced after the grant rather than in parallel.

---

## Differentiation and competitors

**Academic comparator.** Andreoulis et al. (Springer, MARBLE 2025) produced the leading academic OEV panel on Aave V2/V3 across Ethereum and major rollups. There is no Solana counterpart. This grant produces it, focused on tokenized-RWA lending where the question is most economically material in 2026.

**Oracle / risk-data competitors.** Pyth Network, Switchboard, RedStone, and Chronicle as price feed primitives; Gauntlet and Chaos Labs as proprietary risk-parameter consultancies. None publish calibration-transparent uncertainty bands with auditable receipts as a public good. Pyth's confidence intervals are a related signal but are not held-out-calibration-evaluated against published τ targets, and the underlying calibration is not public. Gauntlet and Chaos Labs deliver protocol-specific risk advice under commercial contract, not open infrastructure. Soothsayer's differentiator is **calibration-transparency-as-public-good**: every band is reproducible from the repo, every receipt is auditable against public market data, and the entire methodology evolution log is append-only.

**Measurement / observability competitors.** Helius MEV reports, Jito Explorer, Flashbots-style searcher dashboards. These are real-time observability surfaces, not labelled academic panels with reconstructed oracle uncertainty. The grant's reconstructor is complementary — it consumes public on-chain data plus Jito bundles and produces the labelled panel that downstream researchers can run statistical tests on.

**Structural differentiator.** The deliverable is a *measurement layer plus mechanism-design specification*, not a closed trading edge. The mechanism memo (band-conditional auction overlay on Pyth Express Relay) is designed so that, if adopted, it compresses the very rent the dataset documents — sunset by design rather than perpetual private extraction. Kamino's September 2025 liquidation-penalty drop to 0.1% has already concentrated remaining rent in the band-edge tail regime, which is the regime our analysis specifically targets. No incumbent in the competitive landscape is positioned to ship the same combination of (a) auditable held-out calibration evidence, (b) open Solana liquidation reconstruction, and (c) a deployment-ready mechanism specification on Pyth Express Relay.

---

## Public good

All four grant deliverables ship under permissive licenses: MIT for code (V5 tape, liquidation reconstructor, all analysis notebooks), CC-BY for the dataset and paper. The dataset is hosted on HuggingFace and mirrored on the Solana Foundation public-data repository if accepted. The reconstructor is reusable across Solana lending protocols (Drift, Save, Loopscale) without methodology change.

The structural mental model: **calibration-transparent risk reporting is to RWA infrastructure what block explorers are to transaction visibility** — public infrastructure the ecosystem depends on but that no single private actor produces under current incentives. Block explorers exist because every protocol building its own indexer is wasteful; calibration-transparent risk reporting exists for the same reason. Funding the public-good layer once unlocks the entire downstream RWA ecosystem on Solana — tokenized treasuries (BlackRock BUIDL, Ondo OUSG; collectively > $5B AUM), tokenized commodities (Paxos PAXG, forthcoming silver and broader baskets), tokenized credit, and tokenized FX — wherever a continuous off-hours information set exists. The methodology generalises by construction to any new asset class via a re-fit of the calibration surface on a new (factor, vol-index) pair; the per-class fit/no-fit table is in `docs/methodology_scope.md`.

The success criterion for the grant is therefore not the durability of any private strategy. It is whether the Solana ecosystem ends up with a reusable dataset, a verified open-source measurement layer, and a concrete mechanism-design proposal that compresses opaque band-edge rents. The proposal is intentionally structured so the downside cases still produce useful public goods: if the band-edge effect is smaller than expected, the Foundation still gets the first Solana OEV panel; if the mechanism overlay is not yet deployable, the Foundation still gets the measurement layer that future teams can build on; if xStocks-specific power is limited, the panel still generalises to other Kamino / MarginFi collateral. The repository is public and active end-to-end — methodology evolution, calibration surfaces, backtest evidence, paper drafts, ablation studies, and the append-only methodology-history log are all under version control today, before the grant starts.

---

**Repository.** Public; code, calibration surface, backtest evidence, paper drafts, and methodology evolution log all reproducible from the repo.
**Long-form proposal.** [`docs/grant_solana_oev_band_edge.md`](grant_solana_oev_band_edge.md).
**Contact.** Adam Noonan, [adam@samachi.com](mailto:adam@samachi.com).
