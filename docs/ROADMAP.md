# Soothsayer — Roadmap

**Last updated:** 2026-04-25

This is the single aggregate view of where Soothsayer is headed across three parallel tracks: **product/deploy**, **research**, and **methodology**. Detailed source-of-truth specs live in the linked files; this doc only sequences them.

## TL;DR

Phase 0 (validation) is done. Phase 1 (now) is **devnet deploy + Paper 1 to arXiv + Paper 3 first draft + Paper 2 plan refinement**, in parallel. Phase 2 is **public dashboard + Paper 1 & Paper 3 live + Paper 2 simulator build + design-partner conversations**. Phase 3 (mainnet + B2B + AFT/FC) is **gated on Paper 3 evidence and at least one design-partner LOI**, with Paper 2 shipping to arXiv before AFT/EC submission.

The trilogy structure: Paper 1 = methodology (calibration-transparent oracle), Paper 2 = mechanism (OEV auctions under that primitive), Paper 3 = policy (lending-protocol liquidation defaults). Paper 3 ships first because the protocol-compare scaffolding already exists; Paper 2 is sequenced after because it requires a new auction simulator.

## The three tracks

| Phase | Product / Deploy | Research | Methodology (v2) |
|---|---|---|---|
| **Phase 0** ✅ | Backtest + serving API + smoke test | Paper 1 §1/§2/§3/§6/§9 drafted (28-ref survey, ablations, bootstrap CIs) | — (V1b shipping methodology locked) |
| **Phase 1** (now, ~4 wks) | Devnet deploy: on-chain publish path + Kamino-fork consumer demo + x402-gated premium endpoint + xStock calibration overlay | **Paper 1 §4/§5/§7/§8 + coherence review → arXiv** • **Paper 3 outline + first draft** (existing protocol-compare scaffolding) • **Paper 2 plan refinement + auction-simulator design** | — (static V1b surface) |
| **Phase 2** (~2 wks after Phase 1) | Public comparator dashboard (Soothsayer vs Chainlink vs Pyth, every weekend 2025–2026) + first design-partner conversations | **Paper 1 arXiv live → SSRN cross-post → cold-email researchers** (Capponi, Imperial DeFi group, IC3) • **Paper 3 to arXiv** • **Paper 2 simulator build + theoretical results (C1, C3)** | V2.2 prep: rolling-rebuild cron + buffer drift alerting |
| **Phase 3** (gated, post-hackathon) | **Mainnet deploy** + B2B data-license conversations + Kamino BD deepening | **AFT / FC submission (Paper 1 + Paper 3)** + workshop talks (SBC, FC DeFi workshop) • **Paper 2 to arXiv → AFT or ACM EC** + journal track for Paper 3 (Capponi-style coauthor consideration) | V2.1 ship when V5 tape ≥ 150 weekends (Q3-Q4 2026); V2.3 (MEV-aware coverage) when Jito bundle data ≥ 3 months |

## Why Paper 3 sits parallel to devnet (and gates mainnet)

Paper 3 is the **decision-theoretic protocol policy** layer: given a calibrated band, what should a lending protocol *do*? It strengthens the design-partner pitch ("here's how Kamino/Aave/Marginfi should set defaults against our band") and is the artifact that turns a calibration claim into a revenue argument. See [`reports/paper3_liquidation_policy/plan.md`](../reports/paper3_liquidation_policy/plan.md) for scope.

- **Why parallel to devnet, not after:** the protocol-compare scaffolding (`scripts/run_protocol_compare.py`, `src/soothsayer/backtest/protocol_compare.py`) already exists; Paper 3's bar is walk-forward extension + broader baselines + cost scenarios. None of that blocks devnet engineering.
- **Why it gates mainnet:** mainnet justification is a B2B conversation, and the B2B conversation is much harder without Paper 3's "here's the expected-loss reduction at policy-X" evidence. Devnet ships on Paper 1 + working code; mainnet ships on Paper 3 + a design partner.

## Why Paper 2 sequences after Paper 3

Paper 2 is the **OEV mechanism design** layer: given a calibration-transparent oracle, what auction and trigger mechanism maximises protocol welfare? See [`reports/paper2_oev_mechanism_design/plan.md`](../reports/paper2_oev_mechanism_design/plan.md) for scope.

- **Why not parallel to devnet:** the load-bearing build is a new auction simulator (M0–M4 instantiation with builder/searcher coalition modelling). That is months of theoretical + engineering work with no existing repo artifacts; sequencing it after Paper 3 keeps Phase 1 honest.
- **Why it does not gate mainnet:** Paper 2's pitch audience is OEV mechanism designers (Chainlink Labs, RedStone, API3, Flashbots, Gauntlet) and the academic mechanism-design community (AFT / ACM EC / Financial Cryptography), not lending-protocol design partners. Its role is academic / research-program credibility, not B2B revenue.
- **Why ship it at all:** the trilogy ("methodology → mechanism → policy") is materially stronger than three disconnected papers. Paper 2 is the most novel of the three because the entire OEV literature is written under an opaque-oracle assumption that calibration-transparent oracles explicitly violate. It is the bet that compounds Paper 1's methodology directly into a hot research conversation in 2026.

## Phase detail

### Phase 0 ✅ — Validation (complete 2026-04-24)

V1b decade-scale backtest → PASS-LITE → Option C product shape locked. Full results in [`reports/v1b_decision.md`](../reports/v1b_decision.md) and [`reports/v1b_calibration.md`](../reports/v1b_calibration.md).

### Phase 1 — Devnet + Paper 1 finish + Paper 3 draft + Paper 2 plan (now)

**Product/deploy** — see [`reports/option_c_spec.md`](../reports/option_c_spec.md) "Deferred to Phase 1" for the canonical list:
- On-chain publish path (Solana program + Token-2022 account structure)
- Live-mode serving (current-weekend fetch + online model)
- x402 payment gating for premium endpoints
- xStock-specific calibration overlay (DEX noise, mint/burn friction)
- Devnet deployment across 8 Kamino-onboarded xStocks
- Kamino-fork consumer demo

**Research — Paper 1 finish:**
- Draft remaining sections §4/§5/§7/§8
- Coherence review across all sections
- Post to arXiv (target venues: q-fin.RM + ACM AFT)

**Research — Paper 3 outline + first draft (parallel):**
- Walk-forward extension of `run_protocol_compare`
- Expand cost scenarios + broader baselines (beyond flat ±300bps)
- Add Kamino-like and risk-on synthetic books
- Outline → first draft

**Research — Paper 2 plan refinement + simulator design (parallel, lower-bandwidth):**
- ✅ Fold **Pyth Express Relay** (the only Solana-native deployed OEV-recapture auction) into the Paper 2 plan as the M1 empirical-replay baseline — the prior plan listed only EVM-only mechanisms (Chainlink SVR, RedStone Atom, API3 OEV, UMA Oval), which would not match the Solana replay venue.
- Resolve open forks in [`reports/paper2_oev_mechanism_design/plan.md`](../reports/paper2_oev_mechanism_design/plan.md) §17 (auction format for M3, builder-coalition modelling depth, empirical-replay venue, target conference)
- Auction-simulator architecture spec (M0–M4 instantiation; builder/searcher coalition model; Andreoulis OURW M2 sanity-check baseline)
- Verify open production-anchor citations (Chainlink SVR, RedStone Atom, API3 OEV, UMA Oval, Pyth Express Relay) and convert TODO entries in `paper2_oev_mechanism_design/references.md` to verified entries
- Equilibrium-analysis sketch for C1 (rent monotonicity in band sharpness) under stylised assumptions

**Funding — Solana Foundation OEV-research grant** (parallel to Paper 2 plan refinement):
- Draft + submit a one-page proposal: build the first public **xStocks-on-Kamino liquidation dataset** (2025-07-14 onward) instrumented with reconstructed Soothsayer bands, and publish empirical findings on whether OEV concentrates at oracle-band-edge events. This deliverable is *literally* Paper 2's §C4 wrapped as a grant; the same data-collection effort feeds the paper, the bot (below), and the public-good dataset.
- One-pager scope and hypothesis: [`docs/grant_solana_oev_band_edge.md`](grant_solana_oev_band_edge.md). Target ask $25k–$100k for a 4-month deliverable.

**Product / research bridge — narrow xStocks liquidator bot** (parallel; instrumentation-first):
- Scoping + modeling doc: [`docs/bot_kamino_xstocks_liquidator.md`](bot_kamino_xstocks_liquidator.md). Single-purpose Kamino-on-Solana liquidator targeting xStocks weekend-reopen LTV breaches. Consumes the Soothsayer band as its pricing input (dogfooding); every event is logged into the V5 forward-cursor tape as research-grade C4 data; net revenue covers infra.
- Strategic value: (i) tests Paper 2's C4 conjecture in production rather than retrospect, (ii) builds the dataset Paper 2 needs anyway, (iii) generates a deployment story for Paper 2's empirical section, (iv) underwrites the grant proposal with "we already have a tape and a working consumer."
- The general-purpose Solana-liquidator path is not pursued: Kamino's Sep 2025 penalty drop to 0.1% means median liquidations are unprofitable for solo bots; rents now concentrate in tail (band-edge) events, which is exactly the subset Soothsayer was designed for.
- Phased delivery: MVP devnet (observe-only, 2–3 weeks) → v1 mainnet observe-only (2–3 weeks) → v2 mainnet bidding (4–6 weeks, $25k–$50k working capital). Hard stop conditions specified in scoping doc Section 7.
- **First modeling exercise (cheap, fast, today):** quantify per-event gross EV distribution and band-exit event frequency on the existing Paper 1 dataset (5,986 weekend windows × 10 symbols). Output is a single notebook + table that becomes the grant's economic justification and the bot's bid-floor input — derivable today, before any bot is deployed. See scoping doc §10.1 + §10.2.

**Methodology / verification — open empirical questions:**
- **Monday 2026-04-27 morning ET** — verify Chainlink Data Streams **v11 24/5 cadence** during pre-market window (04:00–09:30 ET = 08:00–13:30 UTC). Re-run [`scripts/scan_chainlink_schemas.py`](../scripts/scan_chainlink_schemas.py) and inspect a v11 sample with `market_status ∈ {1 pre-market, 2 regular, 3 post-market, 4 overnight}` to confirm whether `mid`/`bid`/`ask` carry real values during 24/5 sessions or are placeholder-derived as they are during weekend (`market_status = 5`). Outcome shapes Phase 2 comparator design and Paper 1 §2 incumbent-archetype framing. Context: [`docs/v5-tape.md`](v5-tape.md) "Open empirical question".

### Phase 2 — Dashboard + Paper 1 & 3 live + Paper 2 simulator + design partners

**Product/deploy:**
- Public comparator dashboard (Soothsayer vs Chainlink vs Pyth, every weekend 2025–2026)
- Methodology writeup (web-readable companion to Paper 1)
- Hackathon submission
- First design-partner conversations (Backed, Ondo, Kamino BD)

**Research — Paper 1 + Paper 3 publication:**
- Paper 1 live on arXiv → SSRN cross-post
- Cold emails to named researchers (see review-strategy notes: Capponi at Columbia for Paper 3 fit, Imperial DeFi group, IC3)
- Paper 3 to arXiv

**Research — Paper 2 active drafting (parallel, ramping):**
- Auction simulator implementation (M0–M4) and validation against Andreoulis OURW numerical results
- Theoretical results: C1 (rent monotonicity), C3 (band-aware OURW censorship-proofness inequality)
- Reconstruct Soothsayer historical bands on Aave V2/V3 + Kamino liquidation panel
- Begin empirical replay design

**Methodology — V2.2 prep** (see [`docs/v2.md`](v2.md) for full spec):
- Rolling monthly calibration-surface rebuild cron
- Atomic surface swap + buffer drift alerting

### Phase 3 — Mainnet + B2B + formal publication (gated)

**Gating signals** (need at least 2 of 3 before starting):
- Paper 1 + Paper 3 have absorbed at least one round of external feedback
- At least one design-partner LOI or paid pilot
- Devnet has been live for ≥ 4 weeks with no calibration regression

**Product/deploy:**
- Mainnet deployment
- B2B data-license conversations (first paid pilot)
- Kamino BD deepening

**Research:**
- AFT or FC submission (Paper 1 + Paper 3)
- Workshop talks: SBC, FC DeFi workshop, CESC
- Journal track for Paper 3 (Journal of Risk / Quantitative Finance; consider Capponi-style coauthor for top-tier ceiling)
- Paper 2 to arXiv → AFT or ACM EC submission (mechanism-design venue; Financial Cryptography also viable). C4 (empirical: OEV concentrated at band-edge events) is the result that lands hardest at this audience; line up the historical-replay panel before submission.

**Methodology** (data-gated, fires when triggers hit):
- V2.1 — F_tok forecaster: when V5 tape ≥ 150 weekends with all 8 xStocks (ETA Q3-Q4 2026)
- V2.3 — MEV-aware coverage: when Jito bundle data ≥ 3 months (ETA Q3 2026)
- V2.4 — Full PIT uniformity: on reviewer request or Stage 4/5 of paper
- Engineering-gated v2 items (split-conformal, post-violation cooldown, sub-regime granularity, calendar regressors): see [`docs/v2.md`](v2.md) and Obsidian `Projects/Soothsayer - Solana Oracle/08 - Project Plan.md`

## Source-of-truth cross-reference

This doc is a sequencer. Detail lives in:

- **Product spec** → [`reports/option_c_spec.md`](../reports/option_c_spec.md)
- **Methodology v2** → [`docs/v2.md`](v2.md)
- **Paper 1 status** → [`reports/paper1_coverage_inversion/`](../reports/paper1_coverage_inversion/) (drafted sections + `09_limitations.md` for deferred work)
- **Paper 2 plan (OEV mechanism design)** → [`reports/paper2_oev_mechanism_design/plan.md`](../reports/paper2_oev_mechanism_design/plan.md)
- **Paper 3 plan (liquidation policy)** → [`reports/paper3_liquidation_policy/plan.md`](../reports/paper3_liquidation_policy/plan.md)
- **Phase 1 execution logs** → [`reports/phase1_week1.md`](../reports/phase1_week1.md), [`reports/phase1_week2.md`](../reports/phase1_week2.md)
- **Phase 0 decision record** → [`reports/v1b_decision.md`](../reports/v1b_decision.md)
- **Engineering-gated v2 items + post-Phase 3 methodology** → Obsidian `Projects/Soothsayer - Solana Oracle/08 - Project Plan.md`

## Pending content additions (deck + landing page)

Drafted but not yet incorporated — see [`docs/pitch_deck_content.md`](pitch_deck_content.md):

- **Slide A — "Why this gap is still open"** (structural reasons the calibration-transparency gap persisted until 2025–26). Targets `landing/pitch.html` near slide 03 and a new band in `landing/index.html` between `#gap` and `#product`.
- **Slide B — "Why an ML engineer found this, not a quant"** (conformal-prediction port across a domain boundary). Targets a founder/insight slide near the back of `landing/pitch.html`; sidebar candidate for `#method` in `landing/index.html`.

## What this roadmap explicitly does NOT cover

- Day-to-day execution within a phase (tracked in week logs and Obsidian)
- Hiring, fundraising, legal — separate workstream
- Post-V2.4 methodology research (lives in Obsidian)
- Specific JD/integration partner names beyond what's already public
