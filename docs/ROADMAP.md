# Soothsayer — Roadmap

**Last updated:** 2026-04-25

This is the single aggregate view of where Soothsayer is headed across three parallel tracks: **product/deploy**, **research**, and **methodology**. Detailed source-of-truth specs live in the linked files; this doc only sequences them.

## TL;DR

Phase 0 (validation) is done. Phase 1 (now) is **devnet deploy + Paper 1 to arXiv + Paper 2 drafted in parallel**. Phase 2 is **public dashboard + both papers live + design-partner conversations**. Phase 3 (mainnet + B2B) is **gated on Paper 2 evidence and at least one design-partner LOI**, not on a calendar date.

## The three tracks

| Phase | Product / Deploy | Research | Methodology (v2) |
|---|---|---|---|
| **Phase 0** ✅ | Backtest + serving API + smoke test | Paper 1 §1/§2/§3/§6/§9 drafted (28-ref survey, ablations, bootstrap CIs) | — (V1b shipping methodology locked) |
| **Phase 1** (now, ~4 wks) | Devnet deploy: on-chain publish path + Kamino-fork consumer demo + x402-gated premium endpoint + xStock calibration overlay | **Paper 1 §4/§5/§7/§8 + coherence review → arXiv** • **Paper 2 outline + first draft** (parallel) | — (static V1b surface) |
| **Phase 2** (~2 wks after Phase 1) | Public comparator dashboard (Soothsayer vs Chainlink vs Pyth, every weekend 2025–2026) + first design-partner conversations | **arXiv live → SSRN cross-post → cold-email researchers** (Capponi, Imperial DeFi group, IC3) • **Paper 2 to arXiv** | V2.2 prep: rolling-rebuild cron + buffer drift alerting |
| **Phase 3** (gated, post-hackathon) | **Mainnet deploy** + B2B data-license conversations + Kamino BD deepening | **AFT / FC submission** + workshop talks (SBC, FC DeFi workshop) + journal track for Paper 2 (Capponi-style coauthor consideration) | V2.1 ship when V5 tape ≥ 150 weekends (Q3-Q4 2026); V2.3 (MEV-aware coverage) when Jito bundle data ≥ 3 months |

## Why Paper 2 sits parallel to devnet (and gates mainnet)

Paper 2 is the **decision-theoretic protocol policy** layer: given a calibrated band, what should a lending protocol *do*? It strengthens the design-partner pitch ("here's how Kamino/Aave/Marginfi should set defaults against our band") and is the artifact that turns a calibration claim into a revenue argument. See [`reports/paper2_liquidation_policy_plan.md`](../reports/paper2_liquidation_policy_plan.md) for scope.

- **Why parallel to devnet, not after:** the protocol-compare scaffolding (`scripts/run_protocol_compare.py`, `src/soothsayer/backtest/protocol_compare.py`) already exists; Paper 2's bar is walk-forward extension + broader baselines + cost scenarios. None of that blocks devnet engineering.
- **Why it gates mainnet:** mainnet justification is a B2B conversation, and the B2B conversation is much harder without Paper 2's "here's the expected-loss reduction at policy-X" evidence. Devnet ships on Paper 1 + working code; mainnet ships on Paper 2 + a design partner.

## Phase detail

### Phase 0 ✅ — Validation (complete 2026-04-24)

V1b decade-scale backtest → PASS-LITE → Option C product shape locked. Full results in [`reports/v1b_decision.md`](../reports/v1b_decision.md) and [`reports/v1b_calibration.md`](../reports/v1b_calibration.md).

### Phase 1 — Devnet + Paper 1 + Paper 2 draft (now)

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

**Research — Paper 2 outline + first draft (parallel):**
- Walk-forward extension of `run_protocol_compare`
- Expand cost scenarios + broader baselines (beyond flat ±300bps)
- Add Kamino-like and risk-on synthetic books
- Outline → first draft

### Phase 2 — Dashboard + papers live + design partners

**Product/deploy:**
- Public comparator dashboard (Soothsayer vs Chainlink vs Pyth, every weekend 2025–2026)
- Methodology writeup (web-readable companion to Paper 1)
- Hackathon submission
- First design-partner conversations (Backed, Ondo, Kamino BD)

**Research:**
- Paper 1 live on arXiv → SSRN cross-post
- Cold emails to named researchers (see review-strategy notes: Capponi at Columbia for Paper 2 fit, Imperial DeFi group, IC3)
- Paper 2 to arXiv

**Methodology — V2.2 prep** (see [`docs/v2.md`](v2.md) for full spec):
- Rolling monthly calibration-surface rebuild cron
- Atomic surface swap + buffer drift alerting

### Phase 3 — Mainnet + B2B + formal publication (gated)

**Gating signals** (need at least 2 of 3 before starting):
- Paper 1 + Paper 2 have absorbed at least one round of external feedback
- At least one design-partner LOI or paid pilot
- Devnet has been live for ≥ 4 weeks with no calibration regression

**Product/deploy:**
- Mainnet deployment
- B2B data-license conversations (first paid pilot)
- Kamino BD deepening

**Research:**
- AFT or FC submission (Paper 1)
- Workshop talks: SBC, FC DeFi workshop, CESC
- Journal track for Paper 2 (Journal of Risk / Quantitative Finance; consider Capponi-style coauthor for top-tier ceiling)

**Methodology** (data-gated, fires when triggers hit):
- V2.1 — F_tok forecaster: when V5 tape ≥ 150 weekends with all 8 xStocks (ETA Q3-Q4 2026)
- V2.3 — MEV-aware coverage: when Jito bundle data ≥ 3 months (ETA Q3 2026)
- V2.4 — Full PIT uniformity: on reviewer request or Stage 4/5 of paper
- Engineering-gated v2 items (split-conformal, post-violation cooldown, sub-regime granularity, calendar regressors): see [`docs/v2.md`](v2.md) and Obsidian `Projects/Soothsayer - Solana Oracle/08 - Project Plan.md`

## Source-of-truth cross-reference

This doc is a sequencer. Detail lives in:

- **Product spec** → [`reports/option_c_spec.md`](../reports/option_c_spec.md)
- **Methodology v2** → [`docs/v2.md`](v2.md)
- **Paper 1 status** → [`reports/paper/`](../reports/paper/) (drafted sections + `09_limitations.md` for deferred work)
- **Paper 2 plan** → [`reports/paper2_liquidation_policy_plan.md`](../reports/paper2_liquidation_policy_plan.md)
- **Phase 1 execution logs** → [`reports/phase1_week1.md`](../reports/phase1_week1.md), [`reports/phase1_week2.md`](../reports/phase1_week2.md)
- **Phase 0 decision record** → [`reports/v1b_decision.md`](../reports/v1b_decision.md)
- **Engineering-gated v2 items + post-Phase 3 methodology** → Obsidian `Projects/Soothsayer - Solana Oracle/08 - Project Plan.md`

## What this roadmap explicitly does NOT cover

- Day-to-day execution within a phase (tracked in week logs and Obsidian)
- Hiring, fundraising, legal — separate workstream
- Post-V2.4 methodology research (lives in Obsidian)
- Specific JD/integration partner names beyond what's already public
