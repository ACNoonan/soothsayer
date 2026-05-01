# Soothsayer — Roadmap

**Last updated:** 2026-04-26

This is the single aggregate view of where Soothsayer is headed across three parallel tracks: **product/deploy**, **research**, and **methodology**. Detailed source-of-truth specs live in the linked files; this doc only sequences them.

## TL;DR

Phase 0 (validation) is done. Phase 1 (now) is **devnet deploy + Paper 1 to arXiv + Paper 3 first draft**, in parallel. Phase 2 is **public dashboard + Paper 1 & Paper 3 live + design-partner conversations**. Phase 3 (mainnet + B2B + AFT/FC) is **gated on Paper 3 evidence and at least one design-partner LOI**.

The active research structure is now two-paper: Paper 1 = methodology (calibration-transparent oracle), Paper 3 = policy (lending-protocol liquidation defaults). Paper 3 follows Paper 1 because the protocol-compare scaffolding already exists and is the shortest path from calibrated uncertainty to protocol action.

## Publication-risk gates

The repo now treats the following items as **hard publication-risk gates**, not soft future work. The 2026-04-26 Kamino xStocks on-chain snapshot retired the old flat-`±300bps` incumbent story and is the model for how we should handle every other production-facing assumption: if a claim depends on the real stack, back it with the real stack before publishing.

### Must fix before Paper 1 arXiv submission

These are the minimum items required so Paper 1 cannot be attacked for silently depending on a production claim it does not actually verify.

1. **Comparator wording audit must stay clean.**
   - Do not describe the legacy flat-`±300bps` benchmark as the literal deployed Kamino xStocks incumbent anywhere in the Paper 1 narrative.
   - Paper 1 may cite the legacy policy benchmark as a stylized scaffold only.

2. **Chainlink v11 24/5 cadence verification must be completed and written up.**
   - Confirm whether `mid` / `bid` / `ask` carry real values in pre-market / overnight windows or remain placeholder-derived outside regular hours.
   - This directly affects incumbent-archetype framing in Paper 1 §2 and the web/dashboard comparator story.

3. **The Paper 1 scope boundary must remain explicit.**
   - Paper 1 validates the oracle calibration primitive.
   - It does **not** claim the welfare-optimal protocol policy, actual Kamino liquidation semantics, or xStocks-specific production superiority.

4. **If any statement relies on live xStocks rather than underlier history, it must be disclosed as future work or supported by real tape.**
   - In particular: xStock-vs-underlier divergence and live deployment drift are not allowed to appear as implicit solved problems.

### Must fix before Paper 3 is credible

These are the items that now determine whether Paper 3 is merely a stylized policy note or a production-relevant policy paper.

1. **Actual Kamino xStocks action semantics must be verified end-to-end.**
   - Reserve params alone are not enough.
   - Need the actual trigger path: oracle source, validity checks, TWAP / EWMA defenses, liquidation ladder, soft-liquidation behavior, dynamic penalty behavior, and any conditions that block or defer liquidation.

2. **Primary metric must be reserve-buffer exhaustion, backed by real data.**
   - The economically relevant object is the gap between max-LTV-at-origination and liquidation threshold under the real reserve config.
   - Paper 3 must score whether realized weekend moves exhaust that buffer, not merely whether Monday open lands inside an abstract band.

3. **Path-aware weekend truth must be built.**
   - Monday open alone is not sufficient.
   - Need a defensible off-hours path truth from free xStock venues and on-chain prints where possible.
   - If the path-aware layer is missing, Paper 3 can still exist as a draft, but it is **not** publication-ready.

4. **Book priors and cost ranges must be anchored in observed protocol data, not only stylized assumptions.**
   - At least one Kamino-like book prior.
   - At least one empirically grounded range for bad debt severity, false-liquidation cost, and utilization / blocked-borrow cost.

5. **The baseline family must include the observed production setup.**
   - The old flat-`±300bps` baseline can remain only as a legacy continuity check.
   - The main comparable must be the observed Kamino xStocks reserve/oracle configuration plus at least one simple heuristic baseline.

## Non-negotiable execution rule

If a claim in Paper 1 or Paper 3 depends on the **production semantics of a named protocol**, the roadmap now assumes the burden is on us to either:

1. verify it directly from real on-chain / live data, or
2. downgrade the claim to an explicitly stylized benchmark.

No third option.

## The three tracks

| Phase | Product / Deploy | Research | Methodology (v2) |
|---|---|---|---|
| **Phase 0** ✅ | Backtest + serving API + smoke test | Paper 1 §1/§2/§3/§6/§9 drafted (28-ref survey, ablations, bootstrap CIs) | — (V1b shipping methodology locked) |
| **Phase 1** (now, ~4 wks) | Devnet deploy: on-chain publish path + Kamino-fork consumer demo + xStock calibration overlay | **Paper 1 §4/§5/§7/§8 + coherence review → arXiv** • **Paper 3 outline + first draft** (existing protocol-compare scaffolding) | — (static V1b surface) |
| **Phase 2** (~2 wks after Phase 1) | Public comparator dashboard (Soothsayer vs Chainlink vs Pyth, every weekend 2025–2026) + first design-partner conversations | **Paper 1 arXiv live → SSRN cross-post → cold-email researchers** (Capponi, Imperial DeFi group, IC3) • **Paper 3 to arXiv** | V2.2 prep: rolling-rebuild cron + buffer drift alerting |
| **Phase 3** (gated, post-Phase-2) | **Mainnet deploy** + B2B data-license conversations + Kamino BD deepening | **AFT / FC submission (Paper 1 + Paper 3)** + workshop talks (SBC, FC DeFi workshop) + journal track for Paper 3 (Capponi-style coauthor consideration) | V2.1 ship when V5 tape ≥ 150 weekends (Q3-Q4 2026); V2.3 (MEV-aware coverage) when Jito bundle data ≥ 3 months |

## Why Paper 3 sits parallel to devnet (and gates mainnet)

Paper 3 is the **decision-theoretic protocol policy** layer: given a calibrated band, what should a lending protocol *do*? It strengthens the design-partner pitch ("here's how Kamino/Aave/Marginfi should set defaults against our band") and is the artifact that turns a calibration claim into a revenue argument. See [`reports/paper3_liquidation_policy/plan.md`](../reports/paper3_liquidation_policy/plan.md) for scope.

- **Why parallel to devnet, not after:** the protocol-compare scaffolding (`scripts/run_protocol_compare.py`, `src/soothsayer/backtest/protocol_compare.py`) already exists; Paper 3's bar is walk-forward extension + broader baselines + cost scenarios. None of that blocks devnet engineering.
- **Why it gates mainnet:** mainnet justification is a B2B conversation, and the B2B conversation is much harder without Paper 3's "here's the expected-loss reduction at policy-X" evidence. Devnet ships on Paper 1 + working code; mainnet ships on Paper 3 + a design partner.

## Phase detail

### Phase 0 ✅ — Validation (complete 2026-04-24)

V1b decade-scale backtest → PASS-LITE → Option C product shape locked. Full results in [`reports/v1b_decision.md`](../reports/v1b_decision.md) and [`reports/v1b_calibration.md`](../reports/v1b_calibration.md).

### Phase 1 — Devnet + Paper 1 finish + Paper 3 draft (now)

**Product/deploy** — see [`docs/product-spec.md`](product-spec.md) "Deferred to Phase 1" for the canonical list:
- On-chain publish path (Solana program + Token-2022 account structure)
- Live-mode serving (current-weekend fetch + online model)
- xStock-specific calibration overlay (DEX noise, mint/burn friction)
- Devnet deployment across 8 Kamino-onboarded xStocks
- Kamino-fork consumer demo

**Research — Paper 1 finish:**
- Draft remaining sections §4/§5/§7/§8
- Coherence review across all sections
- Complete the publication-risk gate items above for Paper 1:
  - finish repo-wide comparator-wording audit
  - verify Chainlink v11 24/5 cadence and update incumbent-archetype framing
  - ensure any xStock-live claims are either backed by tape or explicitly deferred
- Post to arXiv (target venues: q-fin.RM + ACM AFT)

**Research — Paper 3 outline + first draft (parallel):**
- Walk-forward extension of `run_protocol_compare`
- Expand cost scenarios + broader baselines (beyond the legacy flat ±300bps baseline and toward the real Kamino reserve/oracle setup)
- Add Kamino-like and risk-on synthetic books
- Complete the publication-risk gate items above for Paper 3:
  - verify actual Kamino xStocks action semantics end-to-end
  - build reserve-buffer-exhaustion scoring
  - build path-aware weekend truth
  - anchor book priors and cost ranges in observed data
- Outline → first draft

**Methodology / verification — open empirical questions:**
- **Monday 2026-04-27 morning ET** — verify Chainlink Data Streams **v11 24/5 cadence** during pre-market window (04:00–09:30 ET = 08:00–13:30 UTC). Re-run [`scripts/scan_chainlink_schemas.py`](../scripts/scan_chainlink_schemas.py) and inspect a v11 sample with `market_status ∈ {1 pre-market, 2 regular, 3 post-market, 4 overnight}` to confirm whether `mid`/`bid`/`ask` carry real values during 24/5 sessions or are placeholder-derived as they are during weekend (`market_status = 5`). Outcome shapes Phase 2 comparator design and Paper 1 §2 incumbent-archetype framing. Context: [`docs/v5-tape.md`](v5-tape.md) "Open empirical question".
- **Immediate Phase 1 validation work (same urgency as paper drafting):**
  - capture real Kamino xStocks reserve snapshots and oracle mappings continuously enough to verify semantic stability
  - start weekend forward tape (`Kraken` / `Bybit` / on-chain Scope / Chainlink observations)
  - measure xStock-vs-underlier weekend divergence so Paper 1 and Paper 3 do not quietly inherit underlier-only assumptions as deployment truth

### Phase 2 — Dashboard + Paper 1 & 3 live + design partners

**Product/deploy:**
- Public comparator dashboard (Soothsayer vs Chainlink vs Pyth, every weekend 2025–2026)
- Methodology writeup (web-readable companion to Paper 1)
- First design-partner conversations (Backed, Ondo, Kamino BD)

**Research — Paper 1 + Paper 3 publication:**
- Paper 1 live on arXiv → SSRN cross-post **only after all Paper 1 publication-risk gates are green**
- Cold emails to named researchers (see review-strategy notes: Capponi at Columbia for Paper 3 fit, Imperial DeFi group, IC3)
- Paper 3 to arXiv **only after all Paper 3 publication-risk gates are green**

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

**Methodology** (data-gated, fires when triggers hit):
- V2.1 — F_tok forecaster: when V5 tape ≥ 150 weekends with all 8 xStocks (ETA Q3-Q4 2026)
- V2.3 — MEV-aware coverage: when Jito bundle data ≥ 3 months (ETA Q3 2026)
- V2.4 — Full PIT uniformity: on reviewer request or Stage 4/5 of paper
- Engineering-gated v2 items (split-conformal, post-violation cooldown, sub-regime granularity, calendar regressors): see [`docs/v2.md`](v2.md) and Obsidian `Projects/Soothsayer - Solana Oracle/08 - Project Plan.md`

## Source-of-truth cross-reference

This doc is a sequencer. Detail lives in:

- **Product spec** → [`docs/product-spec.md`](product-spec.md)
- **Methodology v2** → [`docs/v2.md`](v2.md)
- **Paper 1 status** → [`reports/paper1_coverage_inversion/`](../reports/paper1_coverage_inversion/) (drafted sections + `09_limitations.md` for deferred work)
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
