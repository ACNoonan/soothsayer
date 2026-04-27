# Kamino xStocks Weekend-Reopen Liquidator — Observe-First Instrumentation Plan

**Status:** scoping document, revised 2026-04-26 after the on-chain Kamino xStocks snapshot.  
**Purpose:** specify a narrow Solana research instrument whose primary purpose is **research-grade C4 data collection** and whose secondary purpose is optional later-stage revenue if, and only if, real production data supports bidding. Tertiary purpose: deployment-story credibility for the Solana Foundation OEV grant ([`grant_solana_oev_band_edge.md`](grant_solana_oev_band_edge.md)) and Paper 2 ([`reports/paper2_oev_mechanism_design/plan.md`](../reports/paper2_oev_mechanism_design/plan.md)).

**Core thesis being tested in production.** The first production question is no longer "does a Soothsayer band-exit identify the right liquidation events?" The 2026-04-26 on-chain Kamino snapshot showed that the economically relevant object is the **real reserve buffer** between max-LTV-at-origination and liquidation threshold, while Kamino's `PriceHeuristic` ranges are **price-validity guard rails**, not literal coverage bands. The bot's job is therefore to test whether Soothsayer's calibrated uncertainty is informative about **reserve-buffer exhaustion, liquidation-event severity, and OEV concentration** on real Kamino xStocks events.

---

## 1. Scope (and explicit non-scope)

### In-scope (MVP / v1)
- Solana mainnet (eventually); Solana devnet (Phase 1 of Soothsayer roadmap).
- Single venue: **Kamino Lend / Kamino Multiply** xStocks markets.
- Single event class: **weekend-reopen risk transitions** — positions whose remaining reserve buffer materially compresses or is exhausted during the Friday-16:00-ET-to-Monday-09:30-ET window.
- Single auction venue for later phases: **Pyth Express Relay** (the deployed Solana-native OEV recapture system).
- Single uncertainty input: **Soothsayer served band** at consumer-target $\tau \in \{0.85, 0.95\}$, scored against real reserve semantics rather than treated as the trigger by itself.

### Out-of-scope (deliberately)
- General-purpose Solana liquidator (SOL/USDC, MarginFi, Save, Drift, Loopscale). Wintermute/Jump-tier teams own that lane; solo-bot net EV is small after Kamino's Sep 2025 penalty drop to 0.1%.
- Sandwich attacks, JIT liquidity, oracle manipulation, sequencer-front-running. None of those are OEV in the narrow sense Paper 2 studies.
- Cross-chain MEV, EVM lending markets. EVM cross-check stays as retrospective replay, not active bot operation.
- Full automation of capital deployment before the observe-only phases prove that the real production semantics support it.

### Why this scope is still the right scope
- **Smallest set of moving parts** that exercises every primitive Paper 2 claims about: calibrated uncertainty input, real reserve-buffer monitoring, Pyth Express Relay as M1 baseline, builder/searcher coalition observability via Jito.
- **Highest signal-to-noise for C4, if the thesis is true.** xStocks weekend-reopen events are still the best place to test whether OEV concentrates when reserve buffers are thin and uncertainty is high.
- **Lowest cost of being wrong early.** An observe-first instrument can falsify the deployment thesis cheaply before capital is committed.

---

## 2. Success metrics

The instrument is "successful" if it satisfies the research metric first and only then graduates to economic evaluation.

1. **Research success** — captures **≥80% of all Kamino xStocks weekend-reopen liquidation-relevant events** as labelled rows in the V5 forward-cursor tape (whether or not the bot ever bids), with:
   - observed Kamino reserve semantics,
   - reconstructed Soothsayer bands at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$,
   - reserve-buffer-exhaustion labels,
   - path-aware weekend truth where available.
2. **Semantic success** — verifies that Soothsayer's classifications are informative about the real production object: reserve-buffer exhaustion, liquidation-event severity, or later OEV concentration.
3. **Economic success** — only after (1) and (2): gross capture rate covers infra cost over a rolling 6-month window.

If only (1) holds: the instrument is doing its primary job — generating the dataset Paper 2 and the grant need.  
If (1) and (2) hold but not (3): the data story is real but bidding is not justified; keep observe-only mode.  
If none hold: shut it down within 90 days and report the null result honestly.

---

## 3. Architecture (high-level data flow)

```
┌──────────────────────────────────────────────────────────────────────┐
│                  Soothsayer Oracle (Paper 1)                        │
│   served (point, [L, U], q_served, regime, receipts) per symbol     │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                 Observation pipeline (this doc)                     │
│ 1. Monitor Kamino positions + reserve semantics                     │
│ 2. Read live oracle / heuristic state                               │
│ 3. Measure remaining reserve buffer                                 │
│ 4. Compare Soothsayer uncertainty to real reserve-buffer exhaustion │
│ 5. Log every event to the forward tape                              │
└──────────────────────────────────────────────────────────────────────┘
                               │
                 ┌─────────────┼─────────────┐
                 ▼             ▼             ▼
        ┌──────────────┐ ┌──────────┐ ┌────────────────────┐
        │ Pyth Express │ │ Jito     │ │ V5 forward-cursor  │
        │ Relay (later)│ │ bundle   │ │ tape (primary)     │
        └──────────────┘ └──────────┘ └────────────────────┘
                               │             │
                               ▼             ▼
                ┌──────────────────────────────────────┐
                │ Research dataset (Paper 2 / Paper 3) │
                │ reserve gap, path truth, event, OEV  │
                └──────────────────────────────────────┘
```

The tape is the artifact. Bidding is a later optional consumer of the tape, not the other way around.

---

## 4. Core components

### 4.1 Position and reserve monitor
- Poll Kamino lending state (open positions, collateral, debt, current LTV, liquidation threshold, reserve config) at low latency during weekend windows.
- Subscribe to relevant account changes over WebSocket where possible.
- Filter to xStocks collateral: SPYx, QQQx, TSLAx, NVDAx, AAPLx, GOOGLx, METAx, MSTRx.
- Output: `(position_id, collateral_token, debt_token, ltv, liquidation_threshold, reserve_gap, heuristic_state, oracle_state)`.

### 4.2 Reserve-buffer evaluator
- Consume Soothsayer Oracle (`Oracle.fair_value(symbol, as_of, target_coverage=τ)`).
- For each position, compute the *position-implied liquidation price* and the *remaining reserve buffer* under the actual Kamino reserve configuration.
- Classify the position relative to the reserve buffer and Soothsayer uncertainty:
  - **Inside-buffer:** realized / observed prices remain inside the reserve buffer. Action: observe and log.
  - **Approaching exhaustion:** remaining reserve buffer is thin relative to Soothsayer downside. Action: pre-warm, log aggressively, still no automatic bid.
  - **Exhausted:** the reserve buffer is crossed or would have been crossed under path-aware truth. Action: log as candidate liquidation event; bidding remains separately gated.
  - **Heuristic-reject / oracle-invalid:** Kamino's `PriceHeuristic` or oracle validity logic would block or alter use of the raw price. Action: log as semantic edge case; these events are first-class data.

### 4.3 Auction / execution client (later phase only)
- Pyth Express Relay remains the intended M1-SOL auction surface.
- Jito integration remains relevant for observing winning bundles and later for bidding.
- Neither is part of MVP truth discovery; both are part of later execution once the tape validates the thesis.

### 4.4 Forward-cursor tape (V5)
- Every observed event — non-event, approach, exhaustion, bot-won, lost-to-competitor, observed-but-not-bid — is logged with:
  - position state at trigger,
  - reserve parameters in force,
  - oracle outputs (Pyth / Scope / Soothsayer) at trigger and execution,
  - Kamino heuristic/oracle-validity state,
  - realized liquidation parameters where liquidation occurs,
  - builder / searcher identity where observable,
  - latency from oracle update to liquidation execution,
  - reserve-buffer classification and any Soothsayer-derived classification,
  - path-aware weekend truth where reconstructable.

The tape schema should be rich enough for both Paper 2 and Paper 3. If a field is needed by either paper, it belongs in the tape.

---

## 5. Decision pipeline (observe-first logic)

```
on_position_state_change(position):
    reserve_state = current_kamino_reserve_state(position)
    p_implied = liquidation_price(position, reserve_state)
    gap_state = reserve_buffer_state(position, reserve_state)
    band = soothsayer.fair_value(position.collateral_symbol, now, τ=0.95)
    classification = classify_against_gap_and_band(position, reserve_state, band)

    log_to_tape(position, reserve_state, band, classification)   # ALWAYS log

    if mode != "bidding":
        return

    if not bidding_gate_is_green(classification, reserve_state):
        return

    expected_profit = expected_profit_under_real_execution_constraints(...)
    if expected_profit < min_margin:
        return

    submit_to_pyth_express_relay(...)
```

**Non-negotiable rule:** every event hits the tape before any bidding decision, and bidding mode is forbidden until the observe-only phases validate that the real production object is the one the strategy thinks it is.

---

## 6. Instrumentation contract (the C4 dataset)

Every event in the tape carries enough information to:

- test whether OEV concentrates when **reserve buffers are exhausted or nearly exhausted**;
- test whether Soothsayer uncertainty is informative about that exhaustion;
- compute counterfactual welfare under M0 (status quo), M1-SOL (Pyth Express Relay opaque), M3 (Soothsayer × Pyth Express Relay band-aware), and M4 (tail-trigger overlay);
- cross-validate against Andreoulis et al.'s Aave V2/V3 panel without pretending the Solana stack is identical.

The current null to beat is no longer "band-exit always matters." It is: **conditional on the actual Kamino reserve semantics, does a calibrated uncertainty layer identify the subset of events where the rent is largest?**

---

## 7. Phased delivery

| Phase | Scope | Time | Capital | Net goal |
|---|---|---|---|---|
| **MVP (devnet)** | Position monitor + reserve-buffer evaluator + tape logger only. No bidding. Synthetic positions allowed for plumbing. | 2–3 weeks | $0 | Validate end-to-end instrumentation contract. |
| **v1 (mainnet, observe-only)** | Production tape, observe-and-log mode. Real Kamino positions, real oracle feeds, no bid submission. | 2–4 weeks | $0 | Learn real trigger semantics; generate first 30+ labelled events; validate Soothsayer reconstruction and reserve-gap labels. |
| **v2 (mainnet, constrained bidding)** | Real Pyth Express Relay bids only after v1 confirms the real production object and minimum event economics. Conservative capital ceiling. | 4–6 weeks | $25k–$50k | Produce ground-truth profit data on a thesis already validated in observe-only mode. |
| **v3 (scaled)** | Increased capital, refined bid logic, possibly extend to MarginFi xStocks. | Quarter+ | $50k–$200k | Scale dataset and continue only if the economics survive real execution. |

**Hard stop conditions**
- Tape integrity drops below 99% → halt and fix before any bidding.
- Real Kamino semantics differ from the modeled semantics in a way that changes the trigger logic → halt and rewrite the strategy before any bidding.
- Soothsayer reconstruction parity fails (live ≠ retrospective) → halt; treat as a Paper 1 verification regression.
- A single constrained-bid loss exceeds the pre-committed threshold → halt and post-mortem.

---

## 8. Capital and infra

### Working capital
- **MVP/v1:** $0. Observe-only.
- **v2:** $25k–$50k only after observe-only validation.
- **v3:** $50k–$200k only if v2 proves both data quality and economics.

### Infra
- **Solana RPC:** Helius or Triton dedicated tier ($500–$2.5k/month).
- **Jito block engine:** free.
- **Latency-optimised VPS:** Frankfurt or Amsterdam, $300–$1.5k/month.
- **Monitoring + database:** Postgres for tape, Grafana for liveness, ~$200/month.
- **Total monthly burn:** $1k–$5k depending on tier.

---

## 9. Risk register (operational and methodological)

- **R1 — The real Kamino trigger semantics differ from the stylized thesis.** This is no longer a surprise failure; it is the main thing the observe-only phase is designed to discover.
- **R2 — Pyth Express Relay onboarding takes longer than expected.** Fine; observe-only mode does not depend on it.
- **R3 — Solana RPC rate limits cap event capture rate.** Mitigate with dual providers and upgrade if the tape proves rate-limited.
- **R4 — Kamino changes parameters mid-run.** Treat parameter changes as first-class events and version the tape accordingly.
- **R5 — xStocks sample size is too small for clean inference.** Expand later to MarginFi / other collateral while keeping xStocks as the named deployment case if needed.
- **R6 — The bot becomes part of the market structure it is studying.** If bidding ever begins, report that role honestly; the tape remains more valuable with explicit self-observation than with the pretense of neutrality.

---

## 10. Modeling status and what survives from the retrospective work

This section is intentionally demoted from "deployment economics" to **legacy retrospective priors**.

### 10.1 What survives
- The underlier-based retrospective OOS work remains useful as **hypothesis-generation**.
- It still motivates why the observe-only instrument is worth building.
- It does **not** by itself justify capital deployment or trigger logic on the live Kamino stack.

### 10.2 What is now explicitly legacy
The following are legacy retrospective priors, not production-validated bot economics:

- per-event EV distributions conditional on Soothsayer band-exit;
- band-exit event frequency on the Paper 1 underlier panel;
- annual band-aware-vs-band-blind advantage estimates;
- tau-sensitivity results tied to the band-exit framing.

These outputs remain useful in:
- `reports/band_edge_oev_analysis.md`
- `reports/band_edge_oev_oos_counterfactual.md`
- `reports/band_edge_oev_tau_sweep.md`

But they must be read as: **"reasons to collect the production tape"**, not **"grounds to bid now."**

### 10.3 New required modeling questions
Before v2 capital deployment, the instrument must answer:

1. What are the actual Kamino xStocks trigger semantics, end to end?
2. How often is the real reserve buffer approached or exhausted on weekend paths?
3. Does Soothsayer identify those events better than the observed production stack and simple heuristics?
4. Conditional on real reserve-buffer exhaustion, where does OEV actually concentrate?
5. What is the minimum capital required once real event frequency, bonus realization, and execution costs are measured on the production tape?

---

## 11. Next concrete step

The next concrete step is **not** capital deployment. It is:

1. finish the observe-only implementation;
2. collect a first real weekend tape;
3. verify the real Kamino semantics against the modeled ones;
4. decide whether bidding remains justified after that evidence.

The grant and Paper 2 should now describe the bot as:

> an auxiliary observe-first instrumentation path whose main job is to learn the real Solana xStocks liquidation surface and attach calibrated Soothsayer uncertainty to it.

If that evidence later supports bidding, great. If it does not, the observe-only instrument still produced the public dataset the grant and the papers need.
