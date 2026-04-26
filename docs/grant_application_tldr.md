# Soothsayer — Solana Grant Cover Sheet

**Project.** A calibration-transparent fair-value oracle for tokenized real-world assets on Solana. A consumer specifies a target coverage rate τ; the oracle returns the price band that empirically delivered τ on historical data, together with auditable receipts describing how the band was served. The mechanism is a coverage-inversion primitive that complements, rather than replaces, integrity-focused oracles such as Chainlink, Pyth, and RedStone.

**Current status (2026-04-26).** Phase 0 is complete and self-funded. The methodology has been validated on 5,986 weekends x 10 tokenized-equity tickers, 2014–2026. On a held-out 2023+ slice, the deployed serving configuration delivers Kupiec + Christoffersen passes at three of four standard targets, including realised 95.0% at τ=0.95 (Kupiec p_uc = 1.000) and 85.5% at τ=0.85, the deployment default. The fairest description of the current result is **deployment-calibrated on a held-out surface**: the calibration surface is held out, the per-anchor buffer is deployment-tuned on the same slice, and a six-split walk-forward reproduces the deployed τ=0.95 buffer at the cross-split mean. Estimated-loss improvement versus Kamino's flat ±300 bps band is ~15%, with bootstrap 95% CI excluding zero.

**Known gaps already identified by Paper 1.** The current system is useful but not final. The per-anchor buffer is still heuristic rather than theorem-backed; Berkowitz rejects, so the system is not yet a full-distribution-calibrated density forecast; DQ rejects, so residual multi-lag conditional structure remains in the hit sequence; and there is no live deployment window yet. These are not project-fatal contradictions. They are the concrete map of what a funded V2 should improve.

**Tier-1 deliverables ($0; already committed).** Finish Paper 1, complete the incumbent-oracle comparator groundwork, and land the V2 methodology backlog already implied by the diagnostics: walk-forward buffer stability, extended-grid tail work, PIT / Berkowitz disclosure, and DQ-motivated regime-refinement planning. These move the methodology from "useful anchor-calibrated interval oracle" to "well-scoped baseline with a quantified upgrade path."

**Tier-2 ask ($500 one-time + $50–500/mo for 3 months).** Wall-Street-Horizon-grade earnings calendar to test whether a finer earnings input makes the regressor detectable, and Databento historical tick data to open the v2-paper "intraday + weekend" prediction-window extension beyond closed-market-only use cases.

**Tier-3 ask / grant-funded unlock ($50k Solana Foundation target).** Live Solana deployment plus the research backlog Paper 1 already identifies: Helius/Triton-grade RPC for the V5 tape, xStocks liquidation reconstruction, MEV-aware consumer-experienced coverage measurement, rolling calibration-surface rebuilds, and validation of an `F_tok` forecaster that consumes live tokenized-stock signals. This is the step that can turn the current DQ/Berkowitz failures from "known boundaries" into "measured before-and-after improvements on a deployed Solana system."

**Why Solana Foundation funding is the leverage point.** Tier 1 is already committed and self-funded. Tier 2 resolves one specific disclosure gap and opens one narrow extension. Tier 3 is the real ecosystem unlock: it funds the live deployment window and the concrete methodology upgrades the current diagnostics already point to. In Solana Foundation terms, the grant would not be paying to discover whether there is a problem; it would be paying to convert a working research primitive into a live, public-good Solana artifact with measurable before-and-after evidence.

**Ecosystem value to Solana.**
- Creates a public uncertainty layer for tokenized RWAs, a category where Solana is already an important deployment venue.
- Produces open infrastructure and data that downstream protocols, risk teams, and researchers can reuse without vendor lock-in.
- De-risks future OEV and liquidation-mechanism work by providing a calibrated band primitive rather than another opaque point-price feed.
- Gives the Foundation a fundable path from paper evidence to a real deployment, with explicit milestones and honest risk boundaries.

**Repository.** Public. Code, calibration surface, backtest evidence, paper drafts, and methodology evolution log all reproducible from the repo. See `docs/data-sources.md` § Grant-impact addendum for the dollar-to-deliverable mapping.

**Contact.** Adam Noonan, [adam@samachi.com](mailto:adam@samachi.com).
