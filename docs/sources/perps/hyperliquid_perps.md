# `Hyperliquid — Perpetuals (own L1)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle` (accessed 2026-04-29; the canonical oracle methodology — validator-computed weighted median, 3-second cadence, 8-CEX source list with explicit weights), `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding` (cited via 2026-04-29 search; funding rate methodology, 4%/hour cap, hourly settlement), `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/hyperps` (cited via search; hyperps / pre-launch perp methodology), `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/robust-price-indices` (cited via search; robust price index methodology), the Hyperliquid CEO post on X (Jan 2025) confirming hyperps oracle independence.
**Version pin:** **Hyperliquid mainnet (current)** — Hyperliquid runs its own L1 (Hypercore + HyperEVM); this file documents Hypercore's perp infrastructure. Not on Solana. Spot-oracle source weights (per docs accessed 2026-04-29): **Binance 3, OKX 2, Bybit 2, Kraken 1, Kucoin 1, Gate IO 1, MEXC 1, Hyperliquid 1**.
**Role in soothsayer stack:** `comparator (continuous-quoting; non-Solana; crypto-only)` — Hyperliquid is **the largest non-Solana continuous-quoting perp venue** but is structurally outside the soothsayer-target xStock universe because **Hyperliquid lists crypto perps only** as of 2026-04-29 per the docs survey. Cross-reference value is **architectural**: Hyperliquid's validator-computed weighted-median oracle is a cleanly different oracle paradigm from Pyth's publisher-vote, Chainlink's DON-quorum, or RedStone's modular-source — useful in §1 / §2 framing as the "fourth distinct oracle architecture" comparator. Funding-rate cap (±4%/h) is structurally far more permissive than Kraken's ±0.25%/h, providing useful upper-bound contrast.
**Schema in scryer:** **not in scryer.** `dataset/hyperliquid/...` does not exist; not in `scryer/wishlist.md` Priority 0–4. Adding to scryer would require a non-Solana-RPC fetcher (Hyperliquid has its own REST/WebSocket API). Per the soothsayer Solana focus, this is **not a near-term priority**; relevance is reference-only unless Paper 1's framing extends to non-Solana venues for §10.5 generalisation.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

Hyperliquid's oracle is a **validator-computed weighted median across 8 external CEX spot prices**, with stake-weighted aggregation across validators. Per the canonical oracle docs accessed 2026-04-29:

- **Per-validator computation:** each validator independently computes a weighted-median spot price from 8 source venues:
  - Binance (weight 3), OKX (2), Bybit (2), Kraken (1), Kucoin (1), Gate IO (1), MEXC (1), Hyperliquid (1)
- **Per-cluster final price:** "the weighted median of each validator's submitted oracle prices, where the validators are weighted by their stake."
- **Cadence:** validators publish spot oracle prices **every 3 seconds**.

This is a **double-weighted-median** structure: weighted across CEX sources (per validator), then weighted across validators by stake. Architecturally distinct from:

- Pyth (3N publisher-vote median + Q25/Q75 confidence — see [`oracles/pyth_regular.md`](../oracles/pyth_regular.md) §1.1),
- Chainlink (DON-quorum signature on a benchmark price — see [`oracles/chainlink_v11.md`](../oracles/chainlink_v11.md) §1.1),
- RedStone (modular-source, undocumented aggregation — see [`oracles/redstone_live.md`](../oracles/redstone_live.md) §1.1),
- Switchboard (consumer-defined OracleJob, median across nodes — see [`oracles/switchboard_ondemand.md`](../oracles/switchboard_ondemand.md) §1.1),
- Scope (Kamino-internal multi-source-fan-in by chain ID — see [`oracles/scope.md`](../oracles/scope.md) §1.1).

**Source-selection rules** (per docs):
1. **Hyperliquid-primary assets** (e.g., HYPE token itself): "do not include external sources in the oracle until sufficient liquidity is met" — protection against thin-market-driven manipulation when the asset's liquidity is mostly on Hyperliquid.
2. **External-primary assets** (e.g., BTC): "do not include Hyperliquid spot prices in the oracle" — the asset's price discovery happens primarily on the listed CEXs, so Hyperliquid's own spot is excluded to avoid feedback.

The **mark price** for perps is "an unbiased and robust estimate of the fair perp price, and is used for margining, liquidations, triggering TP/SL, and computing unrealized pnl. Mark price is updated whenever validators publish new oracle prices."

### 1.2 Cadence / publication schedule

- **Spot oracle:** every 3 seconds (validator publish cadence).
- **Mark price:** updated on each oracle publish (sub-3s when the validator stake-weighted aggregation produces a fresh value).
- **Funding rate:** **paid every hour** per the funding docs. Hourly settlement, capped at **±4%/hour** — about **16× more permissive than Kraken's ±0.25%/hour cap**. This is the most permissive funding-cap among continuous-quoting venues we surveyed.
- **Hyperps cadence (pre-launch perps):** the external oracle is "replaced with an 8 hour exponentially weighted moving average of the last day's minutely mark prices" — an internal-mark-anchored oracle used when no external reference exists.

### 1.3 Fallback / degraded behavior

- **Source-venue outage** — if one of the 8 weighted sources goes offline, the weighted median is computed across the remaining sources. The weights are not re-normalised explicitly per the docs, so the effective weighting shifts.
- **Sufficient-liquidity gate for Hyperliquid-primary assets** — until the gate is met, the oracle excludes external sources. Threshold not surfaced in our probe.
- **Validator-quorum fallback** — if validators fail to publish, the stake-weighted aggregation degrades. Specific threshold not surfaced.
- **Hyperps invalid-mark windows** — the 8-hour EMA fallback (using the last day's minutely mark) is the documented pattern.

### 1.4 Schema / wire format

Hyperliquid's perp state is in Hypercore (their L1's native account model, separate from EVM). Schema is exposed via Hyperliquid's REST/WebSocket API rather than via Solana-style on-chain account decode. Not addressable from soothsayer's Solana-native pipeline today. Documentation: the API surface at `https://hyperliquid.gitbook.io/hyperliquid-docs/api`.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** **not present.** No Hyperliquid venue. Not in `scryer/wishlist.md`.
- **No on-chain reads from soothsayer** — Hyperliquid runs its own L1.
- **Indirect cross-reference:** several of the 8 source venues that feed Hyperliquid's oracle (Kraken, MEXC, Gate IO, Bybit, BingX/Phemex via their respective xStock perp listings) are themselves the subject of separate files in this directory (Kraken Futures here; Gate.io / HTX / BingX / Phemex elsewhere in this batch). For an asset that exists on multiple of these source venues + Hyperliquid, the cross-CEX consensus formed at Hyperliquid's oracle layer is implicitly observable from the source-venue tapes alone. **Crypto-only**, however, since Hyperliquid does not list xStock-class perps.
- **No xStock-class perps on Hyperliquid as of 2026-04-29.** Per the docs survey, Hyperliquid's perp universe is crypto-only. The xStock-equivalent comparator does not exist on this venue.

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| Oracle is validator-computed weighted median across 8 CEXs (Binance 3, OKX 2, Bybit 2, Kraken 1, Kucoin 1, Gate IO 1, MEXC 1, Hyperliquid 1). | Confirmed structurally per the canonical oracle docs. **Unmeasurable from soothsayer side** without a Hyperliquid tape. The choice of source weights is interesting: Binance is 3× the weight of Kraken, suggesting Binance liquidity is treated as the primary global reference. | **confirmed (by docs), unmeasured** |
| Validators publish every 3 seconds. | Confirmed per docs. **Unmeasurable.** | **confirmed (by docs), unmeasured** |
| Mark price is updated on every oracle publish. | Confirmed per docs. | **confirmed (by docs)** |
| Funding rate cap is ±4%/hour. | Confirmed per docs. **17× more permissive than Kraken's ±0.25%/hour cap.** Architectural difference: Hyperliquid prioritises mark-anchored alignment over funding-cost-stability; Kraken prioritises funding-cost-stability for retail / low-leverage users. | **confirmed (by docs)** |
| Funding settles every hour. | Confirmed per docs. **Same cadence as Kraken Perp + Drift Perp** — three Solana-or-non-Solana perp venues all on hourly funding settlement. | **confirmed (by docs)** |
| Funding payment uses oracle price (not mark) for notional conversion. | Confirmed per docs: "the spot oracle price is used to convert the position size to notional value, not the mark price." This is a deliberate choice — using oracle (more stable) for notional + mark (more sensitive) for execution. | **confirmed** |
| Hyperliquid lists xStock-class or US-equity perps. | **Contradicted (as of 2026-04-29).** Docs survey shows crypto-only perp universe. **TODO** if Hyperliquid adds equity perps. | **contradicted** |
| Hyperps (pre-launch perps) decouple oracle from external sources. | Confirmed per the Hyperliquid CEO post on X: "hyperps do not rely on any external data for the oracle price." The 8-hour EMA fallback is the internal-mark-anchored oracle. **Architecturally interesting**: hyperps invert the standard "external oracle → internal mark" relationship into "internal mark → derived oracle." | **confirmed** |
| Source-selection rules exclude Hyperliquid spot for external-primary assets. | Confirmed per docs ("e.g., BTC: do not include Hyperliquid spot prices in the oracle"). Sensible defence against feedback loops. | **confirmed** |
| Stake-weighted aggregation across validators. | Confirmed per docs ("the validators are weighted by their stake"). | **confirmed (by docs)** |
| Hyperliquid's oracle architecture is materially distinct from Pyth's publisher-vote primitive. | Confirmed by the dual-weighted-median structure (CEX sources + stake weights) vs. Pyth's per-publisher 3-vote contribution. The architectural distinction is **load-bearing for Paper 1's "fourth oracle paradigm"** framing. | **confirmed** |

---

## 4. Market action / consumer impact

Hyperliquid's downstream impact for **soothsayer's xStock-class target stack is structurally zero** — no xStock perps, not on Solana, no shared consumer with our addressable lending stack:

- **Solana lending stack** — no integration. Hyperliquid is on its own L1.
- **Cross-chain comparator** — Hyperliquid is **the** dominant non-Solana continuous-quoting perp venue. For an EVM-side or off-Solana xStock comparator (gated on Hyperliquid listing equity perps), the venue would be load-bearing. **Not relevant in 2026-04-29 scope.**
- **Drift Protocol cross-reference** — both Drift v2 and Hyperliquid are continuous-quoting perp venues with mark-vs-oracle alignment via funding. Drift's >10% conf rejection ([`perps/drift_perps.md`](drift_perps.md) §1.3) is a single-tier defensive logic; Hyperliquid's source-selection rules + stake-weighted-validator aggregation is a multi-tier defensive structure. Comparing the two is a useful "perp-venue oracle hardening" cross-reference for Paper 1 §1 / §2.
- **Kraken Perp xStocks comparator** — Hyperliquid's ±4%/hour funding cap vs. Kraken's ±0.25%/hour cap is the cleanest operational contrast: Hyperliquid prioritises mark-alignment via aggressive funding; Kraken caps funding for cost-stability. Not soothsayer-targeted, but structurally informative.
- **Tokenized-equity issuer perspective (Backed Finance, Ondo)** — Hyperliquid is not currently a venue for tokenized-equity exposures. If equity perps land on Hyperliquid, the same publisher-dispersion-vs-coverage-SLA reconciliation soothsayer makes for Solana would extend cross-chain.
- **Paper 1 §1 / §2 framing** — Hyperliquid's oracle architecture is the cleanest example of a **non-Pyth, non-Chainlink, non-RedStone, non-Switchboard, non-Scope** oracle paradigm — useful in §1 as the "fifth oracle approach" comparator. The double-weighted-median structure is architecturally novel and worth explicit citation. **Independent of any xStock-class consumer integration.**
- **Paper 1 §10.5 generalisation** — the "calibration-transparent oracle for RWAs" framing extends cross-chain to any venue where (a) tokenized-RWA collateral exists and (b) the venue publishes a price methodology that doesn't admit a coverage SLA. Hyperliquid is not such a venue today, but the framing applies if equity perps land.
- **Public dashboard (Phase 2)** — not a primary dashboard row given the Solana focus.

---

## 5. Known confusions / version pitfalls

- **Hyperliquid is its own L1, not Solana.** Cross-referencing "Hyperliquid integration" without specifying that it requires non-Solana RPC infrastructure is risk-prone. The HyperEVM exists alongside Hypercore and is a separate consumer surface.
- **Hyperps ≠ Perps.** Hyperps are pre-launch perpetuals (e.g., trading a token before its launch via internal-mark-anchored oracle). Perps are the standard CEX-aggregated continuous-quoting markets. Different oracle methodology.
- **Funding rate cap is 4%/hour, not 4%/period.** ±4%/h cumulates dramatically over 24 hours (~+/- 96%) — the cap is permissive at the per-payment level but non-binding for typical market conditions. Code reasoning about "extreme funding events" must use the per-hour cap.
- **Oracle uses spot price for funding-notional conversion, mark for execution.** Don't conflate.
- **Source weights are constants, not adaptive.** Binance always carries 3× Kraken's weight regardless of Binance-specific liquidity changes. A regime where Binance's liquidity shifts (e.g., regulatory pressure) would shift the effective oracle without docs-disclosure.
- **Hyperliquid-spot-included rule depends on liquidity gates.** "Sufficient liquidity met" threshold not surfaced. A Hyperliquid-primary asset's oracle composition silently changes when the gate is crossed.
- **Validator-stake weighting introduces a stake-correlated trust assumption.** Code reasoning about "Hyperliquid's oracle is decentralised" must specify that the decentralisation is bounded by validator stake distribution.
- **3-second cadence is coarser than Pyth's 400ms.** A high-frequency consumer (e.g., HFT) reasoning about cross-venue oracle latency must account for the 3s vs 400ms gap.
- **No xStock perps as of 2026-04-29.** Don't assume parity with Kraken Perp's xStock list.

---

## 6. Open questions

1. **Will Hyperliquid add xStock-class or US-equity perps?** Roadmap-level question. **Why it matters:** if yes, Hyperliquid becomes a Paper-1-relevant comparator with both a non-Pyth oracle paradigm and equity-class coverage. **Gating:** Hyperliquid roadmap query.
2. **Per-validator publication-failure threshold.** What stake-fraction validator outage degrades the oracle? **Why it matters:** sets the operational risk floor on Hyperliquid's oracle. **Gating:** Hyperliquid docs depth probe + governance review.
3. **"Sufficient liquidity met" threshold for Hyperliquid-primary assets.** **Why it matters:** silently changes oracle composition. **Gating:** docs depth probe.
4. **Funding-rate-cap binding empirics.** Has the ±4%/hour cap ever bound on Hyperliquid? Per-asset frequency? **Why it matters:** if not binding, the cap is operationally non-restrictive; if binding, the venue has experienced events that would have required uncapped funding for mark-alignment. **Gating:** Hyperliquid funding-rate tape (would need a non-Solana fetcher).
5. **Cross-validation against the source-venue tapes soothsayer already has.** For a single asset (e.g., BTC), does the Hyperliquid oracle published value materially differ from the soothsayer-recoverable weighted median across the source venues? **Why it matters:** sanity-checks the Hyperliquid double-weighted-median methodology. **Gating:** out-of-scope without Hyperliquid tape (and far afield from soothsayer's xStock focus).
6. **Hyperps internal-mark-anchored oracle stability.** Has the 8-hour EMA fallback ever produced persistent mark divergence vs. external markets when the asset eventually lists? **Why it matters:** if Hyperps mark drifted significantly, that's a "self-anchored oracle has weakness" cautionary tale relevant for design discussions. **Gating:** Hyperliquid-side analysis.

---

## 7. Citations

- [`hyperliquid-oracle`] Hyperliquid. *Oracle (Hypercore)*. https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle. Accessed: 2026-04-29. Source for the 8-CEX weighted-median methodology, source weights (Binance 3, OKX 2, Bybit 2, Kraken 1, Kucoin 1, Gate IO 1, MEXC 1, Hyperliquid 1), 3-second cadence, source-selection rules.
- [`hyperliquid-funding`] Hyperliquid. *Funding*. https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding. Cited via 2026-04-29 search. Source for the ±4%/hour cap, hourly settlement, oracle-price-for-notional convention.
- [`hyperliquid-hyperps`] Hyperliquid. *Hyperps*. https://hyperliquid.gitbook.io/hyperliquid-docs/trading/hyperps. Cited via 2026-04-29 search. Source for the 8-hour EMA fallback methodology.
- [`hyperliquid-robust-indices`] Hyperliquid. *Robust price indices*. https://hyperliquid.gitbook.io/hyperliquid-docs/trading/robust-price-indices. Cited via 2026-04-29 search.
- [`hyperliquid-contract-spec`] Hyperliquid. *Contract specifications*. https://hyperliquid.gitbook.io/hyperliquid-docs/trading/contract-specifications. Cited via 2026-04-29 search.
- [`hyperliquid-x-hyperps`] Hyperliquid (CEO post on X). 2025-01. *Hyperps oracle independence*. https://x.com/HyperliquidX/status/1881726072238326093. Cited via 2026-04-29 search.
- [`pyth-regular-companion`] Soothsayer internal. [`docs/sources/oracles/pyth_regular.md`](../oracles/pyth_regular.md). Comparator: Pyth's 3N-vote vs. Hyperliquid's double-weighted-median.
- [`drift-perps-companion`] Soothsayer internal. [`docs/sources/perps/drift_perps.md`](drift_perps.md). Comparator: Drift's >10% conf rejection vs. Hyperliquid's source-selection rules.
- [`kraken-perp-companion`] Soothsayer internal. [`docs/sources/perps/kraken_futures_xstocks.md`](kraken_futures_xstocks.md). Comparator: Kraken's ±0.25%/h funding cap vs. Hyperliquid's ±4%/h cap.
