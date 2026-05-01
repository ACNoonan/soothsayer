# `Drift v2 — Perpetuals (Solana)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.drift.trade/protocol/trading/oracles` (accessed 2026-04-29; the canonical Drift oracle methodology surface — staleness thresholds, confidence interval treatment, TWAP intervals), `https://docs.drift.trade/trading/market-specs` (cited via 2026-04-29 search; Perpetual Markets Specs), `https://docs.drift.trade/protocol/trading/perpetuals-trading/funding-rates` (cited via search; funding-rate methodology), `https://www.pyth.network/blog/drift-protocol-revolutionizing-decentralized-derivatives-i-pyth-case-study` (Pyth's case study confirming Drift's primary-oracle integration with Pyth).
**Version pin:** **Drift v2** (the active production protocol; v2 added on-chain orderbook, Just-in-Time / JIT liquidity, unified cross-margining). Program ID is the canonical mainnet Drift v2 deployment; pin via `anchor idl fetch` is gated as a §6 task — no IDL pinned in `idl/drift/` today.
**Role in soothsayer stack:** `comparator + downstream-Pyth-consumer reference` — Drift is one of the **largest non-Kamino downstream Pyth consumers on Solana**, and a structural reference for how the publisher-dispersion-vs-coverage-SLA finding ([`oracles/pyth_regular.md`](../oracles/pyth_regular.md) §3) propagates into a perps protocol's mark-vs-oracle deviation logic. **However**, Drift does not appear to list xStock-class perps as of 2026-04-29 — the canonical xStock perp comparator on Solana via Drift is empty. The relevance is the **mechanism** Drift uses to ingest Pyth (10-slot staleness gate, 10%-confidence-interval rejection threshold) — soothsayer's served band would integrate via the same staleness+CI primitive if Drift adds xStock-class markets.
**Schema in scryer:** **not in scryer.** `dataset/drift_perp_oracle_tape/...` does not exist; `dataset/drift_perp_market_specs/...` does not exist; not in `scryer/wishlist.md` Priority 0–4. Adding to scryer would surface (a) the per-market oracle-wiring snapshot (which Pyth feeds Drift consumes per market, what staleness thresholds are configured), and (b) the historical mark-vs-oracle deviation tape per market. **Hand-off** when xStock-class markets ship on Drift, or when Paper 3's wider-than-Kamino lending-stack reconciliation needs Drift's deposit / borrow markets (Drift v2 includes spot-lending in addition to perps).

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

Drift v2 perps consume **external oracle prices** (Pyth-primary per the Pyth case study; the Drift docs surface the consumption pattern, not the oracle source name explicitly in the section we accessed) and produce a **mark price** via the protocol's risk engine:

> "Price oracles feed spot prices, and the protocol calculates mark price, funding rates, and per-position margin ratios in real time."

The protocol distinguishes between **oracle price** (the externally-fed reference) and **mark price** (the protocol-internal price at which trades execute). Funding rates are the mechanism that aligns mark to oracle:

> "Funding rate payments are used as the incentive mechanism to bring the perpetual futures' mark price in line with the oracle price."

This is the standard perp-protocol structure: oracle is the index, mark is the actionable price, funding is the convergence force. The Drift-specific design choice is **multi-oracle staleness checks at different criticality levels** (see §1.3) and an **oracle confidence-interval rejection threshold** (10% — see §1.3) that maps directly into the publisher-dispersion-vs-coverage-SLA reconciliation.

The **on-chain oracle TWAP** is computed Drift-side: 1-hour TWAP (funding period) and 5-minute TWAP. During invalid-oracle windows, the on-chain TWAP shrinks toward the mark TWAP to avoid erroneous funding payments — i.e., when oracle is rejected, funding falls back to mark-anchored.

### 1.2 Cadence / publication schedule

- **Oracle reads:** at instruction time. Drift does not maintain its own publication cadence; it consumes whatever Pyth `PriceAccount.publish_time` carries at the slot it reads.
- **Mark price updates:** sub-second per the orderbook + JIT liquidity activity.
- **Funding settlement:** the funding period is 1 hour per the funding-rate docs (cited via search). 1-hour TWAP is the funding-anchor TWAP.
- **5-minute TWAP:** secondary smoothing for short-window deviation logic.

### 1.3 Fallback / degraded behavior

**Drift's oracle-validity gates** are the load-bearing methodology surface and the cleanest single-shot reconciliation cell for Paper 1 / Paper 3:

1. **Staleness check by criticality:**
   - **`ForAmm` (mark-vs-oracle deviation, used for the AMM)**: oracle must be ≤ **10 slots** behind current slot (~4 seconds at 400ms slots).
   - **`ForMargin` (margin / health calculations)**: oracle must be ≤ **120 slots** behind current slot (~48 seconds).
   - The two thresholds are deliberately different: the AMM-internal use is more sensitive (4s) than the user-facing margin check (48s), reflecting that the AMM is making real-time pricing decisions while margin is a slower-cadence health check.
2. **Confidence-interval rejection:** oracle data is rejected when "confidence interval is too large (confidence is a very large percentage of the price, >10%)." The 10% threshold is binding — at Pyth's typical per-feed conf intervals (often <1% during regular session, can exceed 10% during stale-publisher-on-overnight windows), this gate catches the worst-case publisher-dispersion blowups.
3. **TWAP fallback during invalid-oracle periods:** "on-chain oracle TWAP calculation shrink[s] toward mark TWAP to avoid erroneous funding payment magnitudes."

The **publisher-dispersion-vs-coverage-SLA finding from [`oracles/pyth_regular.md`](../oracles/pyth_regular.md) §3 directly maps onto Drift's >10% conf rejection**: when Pyth's conf widens beyond 10% of price (which it can on overnight/post-market for thinly-published feeds), Drift rejects the oracle entirely and falls back to TWAP. **This is good defensive design**, but it has the failure mode that during a wide-conf event, Drift's mark drifts from the (rejected) oracle and funding-rate alignment fails — the protocol is operating without an oracle anchor for the duration of the rejection.

### 1.4 Schema / wire format

On-chain — Drift's perps state is in Anchor accounts; per-market state includes oracle wiring, mark price, AMM state, funding-period accumulator, and TWAP storage. Specific account names + field set are gated on IDL fetch (§6). The market-spec docs page surfaces high-level parameters (max leverage, contract size, fee schedule) per market.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** **not present.** No Drift venue.
- **On-chain reads** are possible today via the Drift v2 program ID; the IDL is publicly fetchable. **No active soothsayer code reads Drift markets.** Adding `drift_perp_market_specs/v1` (snapshot) and `drift_perp_oracle_deviation_tape/v1` (forward-running) is gated on either (a) Drift adding xStock-class perps, or (b) Paper 3's wider lending-stack scope reaching Drift's spot-lending side.
- **Indirect via Pyth tape:** for any Drift market that consumes a Pyth feed, the upstream `pyth_publish_time` and `pyth_conf` are observable in `dataset/pyth/oracle_tape/v1/...`. This means soothsayer can already characterise the *upstream* signal Drift consumes, without a Drift-side capture. The 10%-conf-rejection threshold is structurally observable: any Pyth feed with `pyth_half_width_bps > 1000` (10%) at publish_time is a Drift-rejection-event candidate. **One-shot probe target.**
- **No xStock-class perps on Drift today.** The Drift docs page accessed 2026-04-29 contains "no mention of xStock-class assets or equity tokenization." Per the search-result excerpts, Drift's market list is crypto + commodity + index perps, not US-equity exposures. **Confirm via market-specs snapshot when scryer wishlist add lands.**

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| Drift consumes Pyth as primary oracle. | Confirmed structurally per the Pyth case study + the Drift oracle docs page. **Per-market wiring TODO when scryer adds drift_perp_market_specs.** | **confirmed (by docs)** |
| `ForAmm` staleness threshold is 10 slots; `ForMargin` is 120 slots. | Confirmed per docs. **Unmeasurable from soothsayer side without Drift tape.** | **confirmed (by docs), unmeasured** |
| Drift rejects oracle reads when confidence > 10% of price. | Confirmed per docs. **Cross-check from soothsayer side**: query `dataset/pyth/oracle_tape/v1/...` for `pyth_half_width_bps > 1000` rows — these are the Drift-rejection candidates. **One-shot probe**: identify per-feed how many such rows exist over a representative window. **Load-bearing** for the publisher-dispersion-vs-coverage-SLA finding's downstream propagation. | **confirmed (by docs), cross-checkable from soothsayer Pyth tape** |
| Funding payments align mark to oracle. | Confirmed structurally per the funding-rate docs. **Unmeasurable from soothsayer side without Drift tape.** | **confirmed (by docs), unmeasured** |
| Drift maintains 1h and 5min on-chain TWAPs. | Confirmed per docs. **Unmeasurable.** | **confirmed (by docs), unmeasured** |
| During invalid-oracle windows, oracle TWAP shrinks toward mark TWAP. | Confirmed per docs. **The operational consequence:** during a wide-Pyth-conf event, Drift's mark drifts from the rejected oracle; consumers see a "mark anchored to itself" rather than a "mark anchored to oracle" pattern. | **confirmed (by docs)** |
| Drift offers xStock-class perpetual markets. | **Contradicted (as of 2026-04-29).** Drift docs and case studies do not list xStock-class assets. The closest exposures are crypto perps + some commodity / index perps. **TODO when scryer adds drift_perp_market_specs.v1** to confirm via direct snapshot. | **contradicted (as of 2026-04-29)** |
| Drift's mark-vs-oracle deviation logic is structurally compatible with consuming a soothsayer-published band. | **Plausible** — soothsayer's band publishes `(lower, upper)`; Drift's oracle-conf-rejection logic ingests `(price, confidence)`. The translation is `confidence = (upper - lower) / 2`. **However**, Drift's >10% rejection threshold would reject any soothsayer band wider than ~10% of price during high-vol regimes — soothsayer's empirical bands at τ=0.95 are typically narrower (single-digit-percent), so the integration is not gated by the threshold. **Forward-design point**, gated on Drift wanting to integrate. | **plausible (not yet a real integration)** |
| Drift's funding period is 1 hour (vs. Kraken's 1-hour). | Confirmed structurally per the funding-rate docs reference. **Same hourly cadence as Kraken xStock perps** — the two-venue funding-rate comparison is symmetric on cadence. | **confirmed** |

---

## 4. Market action / consumer impact

Drift is the cleanest **non-Kamino, large-volume, Pyth-consuming** Solana protocol — useful for the wider-than-Kamino enforcement in Paper 1 / Paper 3:

- **Drift's mark-vs-oracle deviation logic** (≤ 10 slots staleness for AMM, ≤ 120 slots for margin, ≤ 10% confidence) is a real-world implementation of "what publisher-dispersion-vs-coverage-SLA looks like in production." When `pyth_half_width_bps` exceeds 1000 (~10%) on a Drift-consumed feed, the protocol falls back to mark TWAP. **A soothsayer-published band that exposed `(lower, upper)` directly would not need the >10% rejection because the band itself bounds the validity range.** This is the architectural argument for soothsayer's served band as a calibration-transparent oracle: protocols have to wrap raw Pyth in defensive logic; a calibrated band ships the defensive logic with the price.
- **Drift v2 spot lending** — Drift v2 includes a spot-lending arm (deposit/borrow against the same cross-margined account). Whether xStock-class collateral exists on Drift's spot side is the same answer as for perps: not as of 2026-04-29 per docs survey. **TODO** if Drift v2 adds xStock collateral support.
- **MarginFi cross-reference** — both Drift and MarginFi consume Pyth as the dominant oracle. The Drift staleness/conf gates are tighter than MarginFi's documented behaviour ([`oracles/marginfi.md`](../lending/marginfi.md) §1.1's `P ± conf` haircut applies a smaller asymmetry; Drift's >10% rejection is more aggressive). Comparing the two protocols' weekend-behaviour is a §6 future-work direction.
- **Kamino cross-reference** — Kamino uses Scope as primary oracle ([`oracles/scope.md`](../oracles/scope.md)), not Pyth directly. The Drift-vs-Kamino comparison is at the architectural level: Drift = direct Pyth consumer with explicit staleness/conf gates; Kamino = Scope-mediated Pyth consumer with the conf interval stripped at the Scope layer.
- **Hyperliquid / Kraken Perps cross-reference** — Drift's mark-vs-oracle gating is structurally similar to other perps venues (Kraken: 1% premium cap; Drift: 10% conf rejection + slot-staleness gate). The methodology comparison forms a useful "perp-venue oracle hardening" cross-reference for Paper 1's framing.
- **Paper 1 §1 / §2 framing** — Drift's >10% conf rejection is the cleanest single example of a production protocol making the publisher-dispersion-vs-coverage-SLA distinction operational. Worth explicitly citing as "Drift defensively rejects when Pyth's publisher-dispersion exceeds 10%, exactly to avoid acting on a degenerate `(price, conf)` tuple — soothsayer's served band moves this defensive logic from the consumer to the publisher."
- **Paper 3 §6 / §7 framing** — when xStock-class collateral lands on Drift (if), the same OEV-recapture-rate question Paper 3 asks for Kamino + MarginFi extends. Until then, Drift is a *mechanism reference*, not a Paper-3 empirical site.
- **Public dashboard (Phase 2)** — when xStock perps land on Drift, the dashboard would extend to "soothsayer band vs Kraken Perp mark vs Drift Perp mark" — a same-asset, same-timestamp three-venue panel.

---

## 5. Known confusions / version pitfalls

- **Drift v1 vs v2.** v1 was the original Mango-style on-chain perp DEX; v2 added orderbook + JIT + cross-margining + spot lending. Cross-referencing pre-2024 forum / blog posts is risk-prone — always check whether the post is v1 or v2.
- **Mark price ≠ Oracle price.** Drift's terminology distinguishes them; conflating leads to wrong reasoning about deviation gates.
- **`ForAmm` vs `ForMargin` staleness** — different thresholds for different uses. Code that assumes a single staleness threshold will be wrong on at least one path.
- **10% conf rejection is on the *aggregate* `pyth_conf`, not per-publisher dispersion.** Code that derives a different conf measure (e.g., per-publisher std-dev) and compares against 10% is reasoning about a different surface.
- **TWAP fallback during oracle rejection means funding can be unanchored from the underlier.** A long-running invalid-oracle window means funding rates align mark to mark, not mark to underlier — which can drift cumulatively.
- **JIT liquidity providers** are a Drift-specific construct (off-chain RFQ-style providers competing with the on-chain orderbook). Comparing "Drift mark" to other perp venues should account for JIT-driven price discovery vs. pure orderbook.
- **xStock-class perps not (yet) on Drift.** Surveying Drift for xStock comparisons today returns empty. Don't assume parity with Kraken Perp's xStock list.
- **Drift v2 has spot lending in addition to perps.** When the soothsayer Paper 3 lending-stack survey extends to Drift, the relevant surface is the spot-lending arm, not the perps arm.
- **Funding period 1 hour matches Kraken.** Same cadence as [`perps/kraken_futures_xstocks.md`](kraken_futures_xstocks.md) §1.2 — a parallel comparison is structurally feasible.

---

## 6. Open questions

1. **Does Drift list any xStock-class perps as of 2026-04-29?** Docs survey says no, but a definitive answer requires a market-specs snapshot. **Why it matters:** if yes, Drift becomes a Paper-3 empirical site immediately; if no, this file remains a mechanism-reference until that changes. **Gating:** scryer wishlist add — `drift_perp_market_specs.v1` snapshot.
2. **What's the mark-vs-oracle deviation distribution on Drift's existing markets during weekends / overnight (high-vol windows)?** **Why it matters:** if Drift's >10% conf rejection is binding empirically (i.e., regularly fires), the protocol is operating without an oracle anchor for non-trivial fractions of weekend windows — that's a Pyth+Drift hardening story Paper 1 §1 / §2 can cite. **Gating:** `drift_perp_oracle_deviation_tape.v1` (forward-running tape) + a join with `dataset/pyth/oracle_tape/v1/...` for the upstream conf widths.
3. **Pin the Drift v2 program ID and IDL.** **Why it matters:** any soothsayer-side analysis needs the IDL. **Gating:** `anchor idl fetch <DRIFT_PROGRAM_ID>` + pin under `idl/drift/`.
4. **Does Drift v2 spot lending include xStock-class collateral?** **Why it matters:** Paper 3's wider-than-Kamino lending-stack scope. **Gating:** docs probe + market-list snapshot.
5. **Drift's funding-rate cap (if any)** — Kraken's is ±0.25%/h; Drift's funding-rate docs reference 1-hour cadence but the cap (if any) isn't surfaced in our probe. **Gating:** docs deeper read or source review.
6. **Cross-check upstream Pyth conf > 10% events from `dataset/pyth/oracle_tape/v1/...`.** **Why it matters:** soothsayer can identify the would-be Drift-rejection events even without a Drift tape, by querying our existing Pyth tape for `pyth_half_width_bps > 1000`. The frequency of these events is informative for Paper 1's framing. **Gating:** one-shot analysis script (low-effort, in-scope).
7. **Whether Drift's TWAP-fallback during oracle rejection ever produces persistent mark-vs-underlier divergence.** **Why it matters:** if extended invalid-oracle windows produce cumulative funding errors, that's a soothsayer-band-could-help-here story. **Gating:** Drift tape capture + analysis.

---

## 7. Citations

- [`drift-oracles`] Drift Protocol. *Oracles*. https://docs.drift.trade/protocol/trading/oracles. Accessed: 2026-04-29. The load-bearing source for staleness thresholds (`ForAmm: 10 slots`, `ForMargin: 120 slots`) and confidence-interval rejection (`>10%`).
- [`drift-market-specs`] Drift Protocol. *Perpetual Markets Specs*. https://docs.drift.trade/trading/market-specs. Cited via 2026-04-29 search results.
- [`drift-funding-rates`] Drift Protocol. *Funding Rates*. https://docs.drift.trade/protocol/trading/perpetuals-trading/funding-rates. Cited via 2026-04-29 search results.
- [`drift-pyth-case-study`] Pyth Network. *Drift Protocol: Revolutionizing Decentralized Derivatives — Pyth Case Study*. https://www.pyth.network/blog/drift-protocol-revolutionizing-decentralized-derivatives-i-pyth-case-study. Cited via 2026-04-29 search results.
- [`pyth-regular-companion`] Soothsayer internal. [`docs/sources/oracles/pyth_regular.md`](../oracles/pyth_regular.md). The publisher-dispersion-vs-coverage-SLA finding that Drift's >10% conf rejection makes operationally explicit.
- [`marginfi-companion`] Soothsayer internal. [`docs/sources/lending/marginfi.md`](../lending/marginfi.md). Comparator: Drift's >10% conf rejection vs. MarginFi's `P ± conf` haircut — the two production conf-treatment patterns side by side.
- [`kraken-perp-companion`] Soothsayer internal. [`docs/sources/perps/kraken_futures_xstocks.md`](kraken_futures_xstocks.md). Comparator perp venue with xStock-class markets (Drift's missing piece).
- [`scope-companion`] Soothsayer internal. [`docs/sources/oracles/scope.md`](../oracles/scope.md). Comparator: Kamino's Scope-mediated Pyth consumption strips conf; Drift's direct Pyth consumption preserves conf and acts on it.
