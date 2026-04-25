# Soothsayer — Grant Application Cover Sheet

**Project.** A calibration-transparent fair-value oracle for tokenized real-world assets on Solana. Customer specifies a target coverage rate τ; the oracle returns the price band that empirically delivered τ on a 12-year backtest, with auditable receipts. The mechanism is a coverage-inversion primitive that complements (rather than replaces) integrity-focused oracles like Chainlink, Pyth, and RedStone.

**Status (2026-04-25).** Phase 0 complete on $0. Methodology validated on 5,986 weekends × 10 tokenized-equity tickers, 2014–2026. On held-out 2023+ data, the deployed Oracle delivers Kupiec + Christoffersen calibration test passes at three of four standard targets — including realised 95.0% at τ=0.95 (Kupiec p_uc = 1.000) and 85.5% at τ=0.85, the deployment default. Production EL improvement vs Kamino's flat ±300bps band: ~15% with bootstrap 95% CI excluding zero.

**Tier-1 deliverables ($0; in flight).** Walk-forward distribution-valued calibration claims; bounds-grid extension that resolves the τ=0.99 structural ceiling; quantitative incumbent-oracle comparison (Pyth + Chainlink reconstruction on the same matched window); macro-event regime regressor; full PIT-uniformity diagnostic. These move the methodology from "marginal pass with disclaimers" to "robust pass with sensitivity analysis."

**Tier-2 ask ($500 one-time + $50–500/mo for 3 months).** Wall-Street-Horizon-grade earnings calendar: tests whether a finer earnings input makes the regressor detectable (currently disclosed but unconfirmed). Databento historical tick: opens the v2-paper "intraday + weekend" prediction-window extension, expanding the addressable consumer set beyond closed-market-only.

**Tier-3 ask ($200–250/mo + Superteam-eligible RPC credits, 6-month runway ≈ $4,700).** Polygon.io real-time live deployment; Helius Pro tier (or Triton/QuickNode credits) for V5 on-chain tape accumulation; F_tok forecaster validation that closes the Cong et al. 2025 "on-chain prices anticipate Monday opens" baseline gap.

**Why the staged ask.** Tier 1 is engineering-only; we have committed to it before funding. Tier 2 unlocks one specific paper-disclosure resolution and one v2-paper enabler. Tier 3 unlocks live deployment + the v2 forecaster validation gated by data history. Each tier has measurable, time-boxed deliverables with named output artefacts.

**Repository.** Public. Code, calibration surface, backtest evidence, paper drafts, and methodology evolution log all reproducible from the repo. See `docs/data-sources.md` § Grant-impact addendum for the dollar-to-deliverable mapping.

**Contact.** Adam Noonan, [adam@samachi.com](mailto:adam@samachi.com).
