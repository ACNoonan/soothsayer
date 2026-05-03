# Bear case ledger — soothsayer

**Started:** 2026-05-02
**Last updated:** 2026-05-02
**Purpose:** Forward-track the strongest counter-case to the planned platform. The bull case lives in `README.md`, `docs/ROADMAP.md`, and the active papers; this document keeps each branch of the bear case durable, with explicit gates that would either kill it or harden it, and pre-committed alternative routes per branch.

**Update protocol:**
- New evidence on a gate → append a dated row to that gate's evidence log; do not edit history.
- Verdict change → update the verdict cell with `(was: <prior>, <date>)` so prior reads are preserved.
- New bear branch surfaces → add a new section with the same template.
- This file is the bear-case mirror of `reports/methodology_history.md`. Cross-link entries when methodology changes are motivated by a gate trigger.

**Verdict legend:**
- `OPEN` — no evidence yet; gate is live.
- `PARTIAL` — partial evidence, not yet decisive.
- `WEAKENS-BEAR` — gate triggered in a way that weakens this branch.
- `STRENGTHENS-BEAR` — gate triggered in a way that hardens this branch.

---

## Branch 1: Insufficient demand for a calibrated weekend band

**Thesis:** xStocks (and tokenized RWAs more broadly on Solana) are a niche speculative product without a natural credit market. The lending protocols that would consume a calibrated band have refused to list these assets directly (MarginFi: zero direct xStock Banks, 2026-05-01 scan). The end-user is a weekend speculator who exits Monday, not a borrower. The issuers themselves (Backed, Securitize, Ondo) are the natural canonical source of weekend pricing long-run, so soothsayer is third-party reconstruction of something the issuer already knows.

### Invalidating gates (would weaken bear)

| # | Gate | Evidence required | Verdict | Last checked |
|---|---|---|---|---|
| 1.A | Named lending protocol commits to soothsayer integration | Public LOI, governance proposal, or signed integration | OPEN | 2026-05-02 |
| 1.B | Solana xStock TVL crosses $250M aggregate | Cross-protocol DefiLlama scan | OPEN | 2026-05-02 |
| 1.C | Treasury-token protocol (Ondo/BUIDL/USDY consumer) asks for calibrated band | Direct request or RFP | OPEN | 2026-05-02 |
| 1.D | Solana-native AMM team requests band-aware quoting | Public statement or LOI | OPEN | 2026-05-02 |
| 1.E | xStock perp basis demand grows on Solana (Drift listing) | Drift adds xStock perp markets | OPEN | 2026-05-02 |

### Strengthening signals (would harden bear)

| # | Signal | Evidence required |
|---|---|---|
| 1.X | MarginFi explicitly declines xStock listing after better oracle exists | Governance vote or public statement |
| 1.Y | Backed/Securitize/Ondo publish their own weekend NAV band | Issuer product announcement |
| 1.Z | xStock TVL stagnates or declines through 2026-Q4 | Cross-protocol on-chain |
| 1.W | xStock pair turnover concentrates in weekend speculation, not weekday lending | DEX volume + lending utilisation analysis |

### Alternative routes if Branch 1 holds

1. **Pivot to treasury-token oracle.** Treasuries (BUIDL/OUSG/USDY) have less off-hours move but materially larger AUM and institutional consumers who actually price calibrated risk. Methodology mostly carries; calibration target shifts to NAV-strike vs realised redemption.
2. **Pivot to research-only.** Publish Papers 1 + 3 as academic output, skip the protocol build. Lower cost, slower payoff, optional consulting tail with issuers.
3. **Pivot to issuer-side calibration tooling.** If the canonical source is the issuer, build the calibration framework as B2B for Backed/Securitize/Ondo to publish their own bands. Different sales motion, different revenue shape.

---

## Branch 2: Paper 1 methodology is not the right way to produce the band

**Thesis:** The current pipeline (regime classifier + factor switchboard + empirical quantile + buffer schedule) is overfit on N ≈ 11 weekends per regime. The buffer schedule `{0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.010}` reads as ad hoc. Simpler, parameter-light methodologies (forward-curve implied vol, stale-Pyth + constant buffer, EVT-POT, issuer-aware band) are likely to be competitive at a small fraction of the modelling complexity. The headline comparator framing ("Pyth conf 0/8 vs soothsayer τ=0.85 8/8") is a strawman against an uncalibrated dispersion proxy that nobody actually uses for Monday-open coverage; against a hand-tuned `Pyth + 5%` LTV gap (what protocols actually deploy), the win shrinks substantially or disappears on benign weekends.

### Invalidating gates (would weaken bear)

| # | Gate | Evidence required | Verdict | Last checked |
|---|---|---|---|---|
| 2.A | Regime model beats stale-Pyth + constant buffer on width-at-fixed-coverage | Ablation across full panel; report avg width at τ=0.85, 0.95 | **PARTIAL — v2 / M5 closes** | 2026-05-XX |
| 2.B | Regime model beats VIX-implied band on width-at-fixed-coverage | Same; one-parameter VIX-scaled baseline | OPEN | 2026-05-02 |
| 2.C | Forward capture grows N ≥ 40 weekends with empirical coverage holding ±2 pp of target across regimes | Methodology_history.md tracking | OPEN | 2026-05-02 |
| 2.D | Walk-forward coverage stays within ±2 pp of target | `v1b_walkforward.md` refresh on extended panel | PARTIAL | 2026-05-02 |
| 2.E | Macro factor switchboard shows clean ablation lift after refresh | Re-run `v1b_macro_regressor.md` on extended panel | OPEN | 2026-05-02 |
| 2.F | Comparator reframed around Pyth + constant buffer; soothsayer holds width-at-coverage advantage | Paper 1 baselines extended to {Pyth+2%, +5%, +7.5%, +10%}; report Winkler / interval score | OPEN | 2026-05-02 |
| 2.G | EVT-POT tail estimator does not outperform regime model at τ ≥ 0.95 | Refresh of `v1b_evt_pot_trial.md` | PARTIAL | 2026-05-02 |
| 2.H | Issuer-aware band (corp-action / NAV-strike conditioning) does not outperform regime model on conditioned subsamples | Build issuer-tagged holdout | OPEN | 2026-05-02 |

### Strengthening signals (would harden bear)

| # | Signal | Evidence required |
|---|---|---|
| 2.X | VIX-implied or stale-Pyth+constant baseline within 5 pp coverage at comparable width | Baseline run |
| 2.Y | Distribution shift breaks regime classifier on a new weekend (out-of-regime realised move not covered) | Each weekend's coverage check |
| 2.Z | arXiv referee response rejects calibration claims at current N | Submission feedback |
| 2.W | Buffer schedule rationale fails consumer / risk-committee defensibility test | Direct consumer feedback |

### Alternative routes if Branch 2 holds

1. **Reframe Paper 1 around the simplest defensible methodology.** Lead with stale-Pyth + constant buffer as the baseline; position regime model as marginal improvement *or* kill it. Reports become a width-at-coverage ablation study, not a calibration-narrative paper.
2. **Adopt market-implied vol as the primary methodology.** VIX (index-level), single-stock options-implied vol where available, ES/NQ futures basis as forward signal. Lead with "market-priced uncertainty" framing — harder to attack on overfitting grounds because it's a market price, not a fitted parameter.
3. **Hybrid simpler stack.** stale-Pyth + EVT-POT tail (τ ≥ 0.95) + issuer-aware corp-action adjustment. Three parameters total. Easier to defend to a risk committee than the current pipeline.

---

## Branch 3: Even with a great band, an oracle-aware AMM is not a viable product

**Thesis:** LVR / toxic-flow against external venues is the dominant LP cost. A band lets the LP "skip the band interior" but informed traders arbitrage at the band edges instead — toxic flow is moved, not eliminated. LP incentives run opposite to the design assumption: the band is wide *because* uncertainty is high, which is exactly when an LP should not want to quote inside it. Existing concentrated AMMs already handle off-hours xStocks by simply not quoting. OEV recapture requires a separate auction/relay layer (Pyth Express Relay or analogue), which Paper 4 does not provide. The Colosseum hackathon framing pulls toward a working *demo*, not a working *protocol*; conflating the two is a real risk.

### Invalidating gates (would weaken bear)

| # | Gate | Evidence required | Verdict | Last checked |
|---|---|---|---|---|
| 3.A | Band-aware AMM achieves lower LVR than constant-product baseline on toxic-flow simulation | Paper 4 simulation harness with adversarial informed-trader model | OPEN | 2026-05-02 |
| 3.B | LP onboards to a band-aware AMM in non-trivial size | Mainnet TVL > $1M post-hackathon | OPEN | 2026-05-02 |
| 3.C | Documented OEV recapture (not savings claim) on a live or replay tape | Auction tape vs realised arb gap | OPEN | 2026-05-02 |
| 3.D | Solana DEX team requests band-aware bin / curve policy | Public engagement, RFC, integration discussion | OPEN | 2026-05-02 |
| 3.E | Band width is empirically tight enough during normal regime that an LP would prefer it over fixed-spread | LP profitability simulation | **PARTIAL — v2 / M5 normal-regime hw 280 bps at τ=0.95 (was 418 bps under v1)** | 2026-05-XX |

### Strengthening signals (would harden bear)

| # | Signal | Evidence required |
|---|---|---|
| 3.X | LVR simulation shows band-aware quoting amplifies LVR | Paper 4 simulation result |
| 3.Y | Off-hours xStock pair volume stays near-zero on existing DEXs through 2026-Q4 | On-chain volume scan |
| 3.Z | Concentrated AMMs (Orca / Raydium / Meteora) ship band-aware bin policies themselves | Competitor DEX changelogs |
| 3.W | LPs continue manual liquidity withdrawal around earnings / weekends despite band-aware option | LP behaviour analysis |

### Alternative routes if Branch 3 holds

1. **Drop the AMM, ship the oracle.** Distribution via Switchboard `OracleJob`, dedicated publisher PDA, or upstream into Scope. Concentrate on Paper 3 (lending-consumer evidence) over Paper 4 (AMM mechanism).
2. **Pivot to an OEV-auction layer.** Pyth Express Relay analogue on top of the soothsayer band. Different product, different infra, but reuses the band as the truth signal.
3. **Treat Paper 4 as research-only.** Hackathon demo + paper; no protocol build, no LP onboarding, no audit cost.

---

## Cross-cutting risks (orthogonal to the three branches)

| Risk | Description | Tracking signal |
|---|---|---|
| **Regulatory** | Mirror-style SEC action against tokenized equities. xStocks have a redemption mechanic Mirror lacked (structurally weaker fact pattern), but not zero. | SEC docket on Backed / Solana RWA issuers |
| **Issuer-in-house** | Backed / Securitize / Ondo publish their own off-hours bands, displacing third-party reconstruction. | Issuer product announcements |
| **Market-readiness mismatch** | Solana RWA demand may not form on the timeline soothsayer can survive. Mirror, Synthetix-on-Solana, others built ahead of demand that never arrived. | Forward-capture cadence vs runway |
| **Competing oracle entrant** | Pyth Pro extends to full Friday-Sunday weekend coverage; Chainlink ships v12 with explicit calibrated bands. | Provider docs cadence (`docs/sources/oracles/`) |
| **Sample-size dependence on calendar time** | Methodology defensibility scales with weekends observed; nothing accelerates calendar accumulation. | Weekend count tracking in `methodology_history.md` |

---

## Review cadence

- **Weekly:** Gates 1.A, 1.D, 3.B, 3.D (any named-protocol or LP-engagement signal). One line per gate per check, even if "no movement."
- **Per-weekend:** Gates 2.C, 2.D, 2.Y (forward capture and out-of-sample coverage).
- **Per-paper checkpoint:** All Branch-2 and Branch-3 gates refreshed at Paper 1 / 3 / 4 publication points.
- **Quarterly:** Full review with verdict updates and any new branch additions.

---

## Decision rules

- If **two or more invalidating gates** in a single branch trigger `WEAKENS-BEAR`, the branch is downgraded and the corresponding bull case is hardened in the operational ledger.
- If **two or more strengthening signals** in a single branch trigger `STRENGTHENS-BEAR`, evaluate the alternative-route pivot for that branch within 30 days.
- If a cross-cutting risk triggers, escalate to a project-level review regardless of branch state.
