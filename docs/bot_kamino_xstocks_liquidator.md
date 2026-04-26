# Kamino xStocks Weekend-Reopen Liquidator — Scoping & Modeling

**Status:** scoping document, 2026-04-25.
**Purpose:** specify a narrow Solana liquidator bot whose primary purpose is **research-grade C4 data collection** and whose secondary purpose is small-scale infra-covering revenue. Tertiary purpose: deployment-story credibility for the Solana Foundation OEV grant ([`grant_solana_oev_band_edge.md`](grant_solana_oev_band_edge.md)) and Paper 2 ([`reports/paper2_oev_mechanism_design/plan.md`](../reports/paper2_oev_mechanism_design/plan.md)).

**Core thesis being tested in production.** Paper 2 §C4 conjectures that OEV concentrates at oracle-band-edge events. A bot that consumes the Soothsayer band as its pricing input and competes for xStocks-weekend-reopen liquidations on Kamino is the smallest deployable artifact that *empirically tests this hypothesis in real time* rather than retrospectively.

---

## 1. Scope (and explicit non-scope)

### In-scope (MVP)
- Solana mainnet (eventually); Solana devnet (Phase 1 of Soothsayer roadmap).
- Single venue: **Kamino Lend / Kamino Multiply** xStocks markets.
- Single event class: **weekend-reopen liquidations** — positions whose health factor crosses the liquidation threshold during the Friday-16:00-ET-to-Monday-09:30-ET window.
- Single auction venue: **Pyth Express Relay** (the deployed Solana-native OEV recapture system).
- Single pricing input: **Soothsayer served band** at consumer-target $\tau \in \{0.85, 0.95\}$.

### Out-of-scope (deliberately)
- General-purpose Solana liquidator (SOL/USDC, MarginFi, Save, Drift, Loopscale). Wintermute/Jump-tier teams own that lane; solo-bot net EV is small after Kamino's Sep 2025 penalty drop to 0.1%.
- Sandwich attacks, JIT liquidity, oracle manipulation, sequencer-front-running. None of those are OEV in the sense Paper 2 studies.
- Cross-chain MEV, EVM lending markets. EVM cross-check stays as Andreoulis-et-al-style retrospective replay, not active bot operation.
- Full automation of capital deployment beyond the test budget. The bot operates within a fixed working-capital ceiling for instrumentation purposes; scaling the capital is a separate decision.

### Why this scope is the right scope
- **Smallest set of moving parts** that exercises every primitive Paper 2 claims about: calibration band as pricing input, band-conditional trigger logic, Pyth Express Relay as M1 baseline, builder/searcher coalition observability via Jito.
- **Highest signal-to-noise for C4.** xStocks weekend-reopen events are exactly the band-edge events Paper 2 predicts OEV concentrates at — every event is a relevant datapoint, none is wasted.
- **Lowest competitive friction.** The ~9-liquidator MarginFi concentration and Kamino-penalty-drop dynamics together mean general-purpose lanes are saturated; the xStocks-weekend lane is too narrow for top-tier teams to bother optimising for, but exactly the lane where calibration-aware pricing has an information advantage.

---

## 2. Success metrics

The bot is "successful" if it satisfies both:

1. **Research success** — captures **≥80% of all Kamino xStocks weekend-reopen liquidations** as labelled events in the V5 forward-cursor tape (whether or not the bot wins the auction), with reconstructed Soothsayer band attached at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ for each event.
2. **Economic success** — gross capture rate covers infra cost over a rolling 6-month window. Realistic floor: $1.5k/mo infra ⇒ ~$18k/yr, or roughly 5–15 winning liquidations per quarter at current Kamino penalty + xStocks volume.

If only (1) holds: the bot is doing its primary job — generating the dataset Paper 2 and the grant need. Cover infra from grant funds.
If only (2) holds: the dataset is incomplete, but the bot is profitable and the deployment story is real. Re-instrument and re-launch.
If neither holds: shut it down within 90 days; cite the null result honestly in Paper 2's empirical section.

---

## 3. Architecture (high-level data flow)

```
┌─────────────────────────────────────────────────────────────────┐
│                  Soothsayer Oracle (Paper 1)                    │
│  served (point, [L, U], q_served, regime, receipts) per symbol  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Decision pipeline (this doc)                 │
│   1. Monitor Kamino positions for health-factor approach        │
│   2. Compare position-implied price to Soothsayer band          │
│   3. Classify: in-band / approaching-edge / band-exit           │
│   4. If band-exit + Pyth update imminent → bid via Express Relay│
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
        ┌──────────────┐ ┌──────────┐ ┌────────────────────┐
        │ Pyth Express │ │ Jito     │ │ V5 forward-cursor  │
        │ Relay (bid)  │ │ bundle   │ │ tape (instrument)  │
        └──────────────┘ └──────────┘ └────────────────────┘
                              │             │
                              ▼             ▼
                ┌─────────────────────────────────────┐
                │     Research dataset (Paper 2 C4)   │
                │  (event, band, in/out, profit)      │
                └─────────────────────────────────────┘
```

---

## 4. Core components

### 4.1 Position monitor
- Poll Kamino lending pool state (open positions, collateral, debt, current LTV, liquidation threshold) at ≤2-second intervals during weekend windows; ≤30-second intervals otherwise.
- Subscribe to `accountSubscribe` over WebSocket for the Kamino lending program for low-latency state changes.
- Filter to xStocks collateral: SPYx, QQQx, TSLAx, NVDAx, AAPLx, GOOGLx, METAx, MSTRx (the 8 Kamino-onboarded xStocks).
- Output: stream of `(position_id, collateral_token, debt_token, ltv, liquidation_threshold, time_to_liquidation_at_current_price)`.

### 4.2 Band evaluator
- Consume Soothsayer Oracle (`Oracle.fair_value(symbol, as_of, target_coverage=τ)`).
- For each position, compute the *position-implied liquidation price* (the price at which the position's LTV reaches its liquidation threshold).
- Classify the position-implied price relative to the Soothsayer band:
  - **In-band:** position-implied liquidation price falls within the served band $[L_t(\tau), U_t(\tau)]$. Action: monitor, do not bid.
  - **Approaching-edge:** position-implied price is within X bps of the band edge (X tunable; default 100 bps). Action: pre-warm, prepare bid.
  - **Band-exit:** position-implied price has crossed the band edge. Action: place bid via Pyth Express Relay if the bot's expected profit conditional on winning exceeds gas + tip + slippage.

**Bid-floor and upside reference values (anchored in §10.1 + §10.2 + §10.4 retrospective):**
- `min_margin` floor — set against the **OOS in-band p95** at τ=0.95: $37k per $1M position notional (an in-band event of this magnitude is the boundary between "ordinary" and "actionable" for the bot).
- Realistic upside — **OOS band-exit median** at τ=0.95: $27k per $1M notional. Median is the right anchor (not mean — distribution is heavy-tailed; p95 is $53k, max $294k).
- Annual EV the bot is competing for at the panel scale, OOS τ=0.95: **$283,745 per $1M working notional**. This is the upper bound assuming a rational band-blind competitor; realised P&L is a fraction of this depending on win rate.
- Source: [`reports/band_edge_oev_oos_counterfactual.md`](../reports/band_edge_oev_oos_counterfactual.md).

### 4.3 Pyth Express Relay client
- Register as a permissioned searcher with Pyth Express Relay (one-time onboarding).
- Construct atomic bundle: Pyth price update + Kamino liquidation transaction + asset swap.
- Submit bid via the Express Relay auction interface; bid amount = (expected liquidation bonus) − (target net margin) − (gas + tip).

### 4.4 Jito bundle integration
- Connect to Jito block engine; submit liquidation transactions as part of bundles when Express Relay path is unavailable or sub-optimal.
- Tip schedule: dynamic, based on observed competitive rate at the relevant block (Jito Explorer feed).
- Capture lost auctions: even when the bot does not win, it records the winning bundle's metadata for the dataset.

### 4.5 Forward-cursor tape (V5)
- Every observed event — bot-won, lost-to-competitor, observed-but-not-bid — is logged to the V5 tape with:
  - position state at trigger
  - oracle outputs (Pyth price + Soothsayer band) at trigger and at execution
  - bid stack (winning bid, runner-up bid, bot's bid)
  - realised liquidation parameters (collateral seized, debt repaid, bonus realised)
  - builder / searcher identity (where observable)
  - latency from oracle update to liquidation execution
  - in-band / approaching-edge / band-exit classification at trigger
- Tape format compatible with the Andreoulis-style panel structure for cross-chain comparison.

---

## 5. Decision pipeline (per-event logic)

```
on_position_state_change(position):
    p_implied = liquidation_price(position)
    band = soothsayer.fair_value(position.collateral_symbol, now, τ=0.95)
    classification = classify(p_implied, band)

    log_to_tape(position, band, classification)   # ALWAYS log (research first)

    if classification != "band-exit":
        return  # do not bid

    expected_profit = (
        kamino_liquidation_bonus(position)
        - position.collateral_value * slippage_estimate
        - gas_cost - jito_tip_estimate
    )

    if expected_profit < min_margin:
        return

    bid = expected_profit - target_net_margin
    submit_to_pyth_express_relay(position, bid)

    on_outcome(outcome):
        log_outcome_to_tape(position, bid, outcome)
        if outcome.won:
            execute_swap_and_realise(outcome)
```

The instrumentation-first design is non-negotiable: **every event hits the tape before any bidding decision**, and the tape is the primary deliverable.

---

## 6. Instrumentation contract (the C4 dataset)

Every event in the tape carries a `(position, band, classification, bid, outcome)` tuple sufficient to:

- Test H₀ vs H₁ from the grant proposal (band-edge events have higher OEV than within-band events).
- Compute counterfactual welfare under M0 (status quo), M1-SOL (Pyth Express Relay opaque), M3 (Soothsayer × Pyth Express Relay band-aware), and M4 (tail-trigger overlay).
- Cross-validate against Andreoulis et al.'s Aave V2/V3 panel.

The tape schema is documented as part of the grant proposal's open-dataset deliverable.

---

## 7. Phased delivery

| Phase | Scope | Time | Capital | Net goal |
|---|---|---|---|---|
| **MVP (devnet)** | Position monitor + band evaluator + tape logger only. No bidding. Synthetic positions. | 2–3 weeks | $0 | Validate end-to-end instrumentation contract. |
| **v1 (mainnet, observe-only)** | Production tape, observe-and-log mode. Real Kamino positions, real Pyth feeds, no bid submission. | 2–3 weeks | $0 | Generate first 30+ band-classified events. Validate band reconstruction matches retrospective Soothsayer outputs byte-for-byte. |
| **v2 (mainnet, bidding)** | Real Pyth Express Relay bids. Conservative capital ceiling. | 4–6 weeks | $25k–$50k | Win 5–15 liquidations/quarter; cover infra; produce ground-truth profit data. |
| **v3 (scaled)** | Increased capital, refined bid logic, possibly extend to MarginFi xStocks. | Quarter+ | $50k–$200k | Scale dataset; if economically viable, run as continuing income. |

**Hard stop conditions** (from MVP onward):
- Tape integrity drops below 99% (events missed) → halt and fix before bidding.
- Bid logic produces a single >$5k loss → halt, post-mortem, restart conservatively.
- Soothsayer band reconstruction parity fails (live ≠ retrospective) → halt; treat as a Paper 1 §8 verification regression.

---

## 8. Capital and infra

### Working capital
- **MVP/v1:** $0. Observe-only.
- **v2:** $25k–$50k. Stable inventory of USDC + small allocations of each xStock to seed the swap path.
- **v3:** $50k–$200k. Justified only if v2 economic-success metric is met.

### Infra
- **Solana RPC:** Helius or Triton dedicated tier ($500–$2.5k/month). User has both keyed (per `project_rpc_providers` memory).
- **Jito block engine:** free.
- **Latency-optimised VPS:** Frankfurt or Amsterdam, $300–$1.5k/month. Co-located if v3 ramps.
- **Monitoring + database:** Postgres for tape, Grafana for liveness, ~$200/month.
- **Total monthly burn:** $1k–$5k depending on tier.

---

## 9. Risk register (operational)

- **R1 — Pyth Express Relay searcher onboarding takes longer than expected.** Mitigated by reaching out to Pyth Data Association early (also relevant to the grant's letter-of-support ask).
- **R2 — Solana RPC rate limits cap event capture rate.** Mitigated by using both Helius and RPC Fast keys (both already provisioned per memory) plus dedicated paid-tier upgrade if the V5 tape proves rate-limited.
- **R3 — A single losing bid burns $X.** Mitigated by hard stop conditions (Section 7) and conservative `target_net_margin` floor.
- **R4 — Kamino changes liquidation parameters mid-run.** Mitigated by the instrumentation-first design: parameter changes are themselves events worth recording, and the tape format is robust to them.
- **R5 — The bot is competitive enough to *create* the Andreoulis-style coalition concentration we are studying.** Acknowledged. The paper reports the bot's role honestly; the dataset is more valuable if the bot's behaviour is documented than if it pretends to be neutral.

---

## 10. Open questions for the modeling phase

These are the questions the modeling phase (now beginning) should answer before v2 capital deployment.

### 10.1 What does the per-event EV distribution look like, conditional on band-exit? ✅ Done (2026-04-25)
**Result.** OOS τ=0.95: in-band median $7,516/M; band-exit median $26,787/M; **dominance ratio 3.56×**. In-sample dominance is 5.34× at the same τ. Tail at OOS τ=0.95 band-exit: p95 $53,259/M, max $293,750/M. Full distribution by τ and regime: [`reports/band_edge_oev_analysis.md`](../reports/band_edge_oev_analysis.md), [`reports/band_edge_oev_oos_counterfactual.md`](../reports/band_edge_oev_oos_counterfactual.md), `reports/tables/band_edge_oev_distribution.csv`.

### 10.2 What is the band-exit event frequency? ✅ Done (2026-04-25)
**Result.** OOS τ=0.95: P(band-exit) = 4.0%, **~21 events/year panel-wide** (10 symbols × ~52 weekends); higher at τ=0.85 (66/yr); lower at τ=0.99 (11/yr). Per-symbol-per-regime breakdown: `reports/tables/band_edge_oev_frequency.csv`. Notably, the **OOS rate is ~2× the in-sample rate** — post-2023 regimes are more bot-favourable.

### 10.3 What is the minimum capital required for the bot to clear the average winning bundle? — TODO
**Status:** non-trivial; needs external data (Kamino TVL/position-size distribution scrape + Jito Explorer tip-rate sample). Defer to Phase 1 v1-mainnet-observe-only build, where the data is collected naturally as part of instrumentation.

### 10.4 What is the EV gap between band-aware and band-blind liquidators? ✅ Done (2026-04-25)
**Result.** Aggregate counterfactual: at τ=0.95 OOS, the panel-scale **annual band-aware-vs-band-blind advantage is $283,745 per $1M working notional**. At $50k working capital → ~$14k/yr (covers 9.5 months of $1.5k/mo infra). At $250k → ~$71k/yr; at $500k → ~$142k/yr; at $1M → $284k/yr. This is the upper bound (rational band-blind bidder priced to band edge); realised P&L is a fraction depending on auction win rate. Full table: [`reports/band_edge_oev_oos_counterfactual.md`](../reports/band_edge_oev_oos_counterfactual.md) §3.

### 10.5 How sensitive is the result to band-tightness? ✅ Done (2026-04-25)
**Result.** Finer-grid τ sweep ({0.50, 0.60, 0.68, 0.75, 0.85, 0.90, 0.95, 0.99}) reveals **two patterns pointing in different directions**:

- **OOS multiplicative dominance ratio is U-shaped**, not monotonic. Series: 3.99× → 3.85× → 3.60× → 3.61× → **3.29× (minimum at τ=0.85)** → 3.34× → 3.56× → 3.83×. The minimum sits at the empirically well-calibrated mid-range τ.
- **OOS aggregate annual band-aware advantage in $ is monotonically *decreasing* in τ.** $2.27M → $1.97M → $1.71M → $1.39M → $815k → $584k → $284k → $148k per $1M notional per year. Frequency dominates — sharper bands have many more band-exit events.

This is a **richer empirical finding than Paper 2's original C1 conjecture** (which predicts simple monotonic decline in rent with sharpness). The U-shape on the per-event ratio + frequency-dominated monotonicity on aggregate $ points to a refined C1 statement worth publishing in its own right. Full analysis: [`reports/band_edge_oev_tau_sweep.md`](../reports/band_edge_oev_tau_sweep.md).

**Operational implication for the bot.** There is a real tradeoff: lower τ = larger annual EV but ~10× more events to handle (237/yr at τ=0.50 vs 21/yr at τ=0.95). MVP serves at τ=0.95 (capital-efficient). v3 scaling can argue for τ=0.85 or below once the throughput layer matures.

---

## 11. First concrete next step ✅ Done — and the modeling cascade behind it

§10.1 + §10.2 + §10.4 ran 2026-04-25 against the Paper 1 dataset. Headline OOS numbers (τ=0.95): 3.56× dominance ratio, 21 events/year, $283,745 annual band-aware-vs-band-blind advantage per $1M working notional.

The grant's "if we can extract value" argument is therefore upgraded to **"here is the OOS-validated per-event distribution and panel-scale annual advantage on a 3-year holdout slice; the bot's job is to verify these numbers in production on the Solana xStocks-Kamino subset."** Section 2 of [`grant_solana_oev_band_edge.md`](grant_solana_oev_band_edge.md) carries the empirical anchors; Section 4.2 of this scoping doc carries the bid-floor implications; Paper 2 §C4 carries the retrospective baseline.

**Status of modeling phase:** §10.1 + §10.2 + §10.4 + §10.5 done. §10.3 (capital analysis) deferred to v1-mainnet-observe-only build where the underlying data is collected naturally. **Next concrete step:** Phase 1 v0/v1 implementation — MVP devnet observe-only build per Section 7. The modeling has produced everything needed to design the bid logic, set the bid floor, and justify the grant ask.
