# `RedStone — Classic (Push model)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.redstone.finance/docs/dapps/redstone-push/` (accessed 2026-04-29; canonical Push-model documentation, structurally complete on relayer+adapter pattern, EVM-only chain support, and configurable cadence/deviation knobs), `https://blog.redstone.finance/2024/08/21/pull-oracles-vs-push-oracles/` (RedStone's own pull-vs-push pedagogy, cited via 2026-04-29 search), `https://blog.redstone.finance/2026/03/30/blockchain-oracles-comparison-chainlink-vs-pyth-vs-redstone-2026/` (RedStone's 2026 comparison, cited via 2026-04-29 search), `https://docs.redstone.finance/docs/dapps-and-defi/redstone-models` returned 404 on 2026-04-29 (link rot, same cluster as [`oracles/redstone_live.md`](redstone_live.md) §7).
**Version pin:** **RedStone Classic / Push** — the older push-on-chain product, layered on top of RedStone's Pull (Core) model. The Push model is **EVM-only by design** per the canonical documentation: deployment targets are "all EVM-compatible L1s & L2s + Starknet + Fuel Network." **No Solana support is documented for the Push model.** RedStone's Solana presence (the `redstone-sol` program at `3oHtb7BCqjqhZt8LyqSAZRAubbrYy8xvDRaYoRghHB1T`) is the Wormhole-Queries Pull integration, which is a different surface (see [`oracles/redstone_live.md`](redstone_live.md) §1.4 and §2).
**Role in soothsayer stack:** `comparator (limited)` — RedStone Classic is documented for completeness but is **structurally absent from the Solana xStock lending stack soothsayer targets**. The relevance is rhetorical: "RedStone has a push-model on-chain product, but it does not deploy to Solana, so any Solana RWA-lending integration of RedStone is via Wormhole Queries (Pull-style, see [`oracles/redstone_live.md`](redstone_live.md))." Cross-chain comparison only.
**Schema in scryer:** **not in scryer.** `dataset/redstone_classic/...` does not exist; soothsayer's RedStone tape (`dataset/redstone/oracle_tape/v1/...`, `redstone.v1`) is the Live REST gateway path. RedStone Classic is structurally not addressable from a Solana-native data pipeline.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

RedStone Classic / Push retains the **same RedStone Core aggregation** under the hood — the off-chain operator nodes sign price packages from a multi-source aggregation, and downstream consumption is via the on-chain adapter. Per RedStone's canonical Push documentation accessed 2026-04-29: the on-chain Push surface is "built on top of the RedStone Pull model maintaining the security of on-chain validation of data providers and timestamps."

The on-chain architecture has two contracts:

- **`PriceFeedsAdapter`** — the central on-chain data store. Maps RedStone `dataFeedId` strings to price values + update timestamps. Supports batch updates (multiple feeds in one tx) and batch reads.
- **`PriceFeed` (per-feed)** — optional individual-feed contracts deployed for **"100% compatible with the Chainlink PriceFeed architecture."** This is the key compatibility hook: a consumer that already integrates Chainlink's `AggregatorV3Interface` can swap in a RedStone PriceFeed without code changes.

The aggregation rule itself (which CEX/DEX venues feed each `dataFeedId`, the median/mean weighting, the operator-quorum threshold) is **not surfaced in the Push docs at depth** — it is the same opacity that affects RedStone Live (see [`oracles/redstone_live.md`](redstone_live.md) §1.1). Multi-source aggregation is claimed; the specific rule is not published.

### 1.2 Cadence / publication schedule

Push cadence is **configurable per deployment**, controlled by an off-chain relayer that decides when to push a fresh on-chain update. Two trigger conditions, evaluable with OR logic:

- **Time-based heartbeat:** `UPDATE_PRICE_INTERVAL` (milliseconds). E.g., a 24-hour heartbeat ensures at least one update per day.
- **Deviation-based:** `MIN_DEVIATION_PERCENTAGE`. E.g., a 0.5% threshold pushes whenever the current price deviates by ≥0.5% from the last on-chain value.

Either condition triggers a push: "if any conditions are met prices will be updated."

**Relayers are permissionless** per the Push docs: "Relayers are permissionless and anyone could run the service as the data is eventually validated on-chain." This is structurally different from Chainlink Data Streams (DON-quorum-only push) and from Pyth Pull (consumer-pull). RedStone Classic operationally relies on **multiple independent relayers** to mitigate single-relayer failure or censorship, with on-chain validation of operator-quorum signatures providing the trust anchor.

### 1.3 Fallback / degraded behavior

- **Heartbeat-only (no deviation push for an extended period)** — the on-chain value can be up to `UPDATE_PRICE_INTERVAL` stale. Consumer code must check the on-chain timestamp before trusting the price.
- **Relayer outage** — if no relayer pushes during a window, the on-chain value remains the last successfully-pushed value. There is no "auto-fallback to a different feed" mechanism documented.
- **Operator-quorum signature failure** — the on-chain adapter validates the operator-quorum signature on each push; below-quorum pushes are rejected. This is the chain's protection against a relayer-side compromise.
- **Chainlink-compatibility gotcha** — a `PriceFeed` deployed in Chainlink-compatible mode exposes `latestRoundData()`. The semantics of "round" are RedStone-side (each push is a new round) and not the same as Chainlink's OCR-round semantics. Consumer code that depends on round-id monotonicity is OK; code that depends on round-id meaning Chainlink's OCR round will be confused.

### 1.4 Schema / wire format

On-chain (per RedStone Push docs accessed 2026-04-29):
- **`PriceFeedsAdapter`** carries:
  - mapping `dataFeedId -> (uint256 price, uint256 timestamp)` (specific Solidity field names not surfaced in the overview page; require source-code probe).
  - batch-update entry point.
- **`PriceFeed`** (per-feed, optional, Chainlink-compatible): exposes `latestRoundData()` returning `(roundId, answer, startedAt, updatedAt, answeredInRound)`.
- **Operator-quorum signature blob** is consumed by the adapter on each push; the on-chain validation logic verifies it.

Off-chain (relayer-side) — the relayer fetches signed price packages from RedStone's Core / Pull layer and bundles them into the adapter's batch-update tx. The relayer is essentially a keeper that owes the gas cost.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** **not present.** `dataset/redstone_classic/...` does not exist. RedStone's Solana on-chain footprint per [`oracles/redstone_live.md`](redstone_live.md) §2 is the `redstone-sol` program holding 4 crypto PDAs (AVAX, ETH, SOL, BTC) — that's the Wormhole-Queries Pull surface, **not** the Classic Push surface.
- **EVM-side data:** soothsayer does not consume EVM data. If a future paper requires EVM-side comparison (e.g., RedStone Classic vs. soothsayer for an EVM-deployed RWA token), the scryer wishlist would need an EVM consumer + per-chain `dataset/redstone_classic/<chain>/...` partitioning. Not currently in scryer's Priority 0–4.
- **What an EVM-side capture would surface:** per-chain `PriceFeedsAdapter` reads (for SPY-equivalent feeds, if RedStone Classic publishes them on EVM at all — which is itself a §6 question), the per-push tx signatures, the relayer addresses, and the on-chain `(price, timestamp)` time series.
- **Cross-reference to redstone_live.md:** the equity-coverage gap finding (no SPYx feed, only underlier ticker like SPY; weekend gap acknowledged by RedStone's own co-founder) **transitively applies** to RedStone Classic because the underlying aggregation is the same. A RedStone Classic deployment of SPY on Polygon (hypothetical — needs verification) would have the same closed-market-window pricing problem because the aggregation rule is identical to Live.

---

## 3. Reconciliation: stated vs. observed

The reconciliation here is **structurally limited** because soothsayer has no EVM tape.

| Stated claim | Observation | Verdict |
|---|---|---|
| RedStone Classic / Push is deployable on Solana. | **Contradicted.** Per the Push canonical docs accessed 2026-04-29: deployment targets are "all EVM-compatible L1s & L2s + Starknet + Fuel Network." **Solana is not in the documented deployment-target list.** RedStone's Solana on-chain presence is the Wormhole-Queries Pull surface ([`oracles/redstone_live.md`](redstone_live.md) §2), not the Classic Push adapter. | **contradicted (by Solana-pin)** |
| Push uses the RedStone Pull/Core aggregation under the hood. | Confirmed structurally per the Push docs: "built on top of the RedStone Pull model maintaining the security of on-chain validation of data providers and timestamps." The aggregation findings transfer transitively from the Live/Pull surface. | **confirmed (by docs)** |
| Push relayers are permissionless. | Confirmed per the Push docs: "Relayers are permissionless and anyone could run the service as the data is eventually validated on-chain." **Unmeasurable from soothsayer side** (no EVM tape). | **confirmed (by docs), unmeasured** |
| Push cadence is heartbeat OR deviation, configurable per deployment. | Confirmed per the docs. **Unmeasurable from soothsayer side** without an EVM tape sampling the on-chain `PriceFeedsAdapter`. | **confirmed (by docs), unmeasured** |
| RedStone Classic provides 100% Chainlink-PriceFeed-compatible interface. | Confirmed structurally — the optional `PriceFeed` contract deploys with the Chainlink `AggregatorV3Interface`. | **confirmed (by docs)** |
| RedStone publishes a confidence interval / coverage band on its Push surface. | **Contradicted** — the Push docs surface no CI / dispersion / band field. The on-chain adapter stores `(price, timestamp)` only. Same finding as RedStone Live (no published band). | **contradicted** |
| RedStone Classic on EVM publishes equity feeds (SPY, QQQ, etc.). | **Unverified from soothsayer side.** [`oracles/redstone_live.md`](redstone_live.md) §2 documents which equity tickers RedStone Live serves on the public REST gateway (SPY ✓, QQQ ✓, MSTR ✓, IWM ✓, XAU ✓; TSLA / NVDA / HOOD / GOOGL empty). Whether the same set is deployed via Classic on any EVM chain is **gated on EVM probe** (not in scryer). | **unmeasurable from current data** |
| The Push model is the dominant mode for RedStone integrations. | **Contradicted** — RedStone explicitly markets itself as offering both Pull and Push, and the modular dual-model is their differentiator vs. Chainlink (Push-dominant) and Pyth (Pull-dominant). The Push model is one of two; Pull is the more recent / dominant integration pattern. | **contradicted (rhetorical framing)** |

---

## 4. Market action / consumer impact

RedStone Classic's downstream impact for **Solana lending soothsayer targets is structurally zero** — the surface is not deployed there. For the wider RWA-wave generalisation argument:

- **EVM lending markets (Aave, Spark, Morpho, etc.)** — RedStone Classic is a live integration target on EVM chains, with `PriceFeed` deployments visible on Etherscan equivalents. Most of RedStone's marquee integrations (per their case-study material) are EVM-side. Soothsayer has no EVM consumer surface today.
- **Solana lending (Kamino, MarginFi, Drift, Save, Loopscale, Jupiter Lend)** — none of these consume RedStone Classic because it is not Solana-deployed. They consume RedStone Live (REST gateway) only if their integration is consumer-pull-style — which, per [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §1 and the Solana lending stack survey in [`docs/data-sources.md`](../../data-sources.md) §8, is **none of the major Solana lending markets today**. RedStone Live is structurally absent from Solana xStock lending stack.
- **Hyperliquid / Drift / dYdX (perps cross-reference)** — none documented as RedStone Classic consumers in our reading.
- **Paper 1 §10.5 RWA-wave generalisation** — RedStone Classic is the canonical "push-style RWA oracle" comparator on EVM. The methodology-fits-this-asset-class argument in `docs/methodology_scope.md` extends to EVM tokenized treasuries (e.g., BUIDL, OUSG); a soothsayer EVM-deployment would naturally be compared against RedStone Classic's same-asset feeds. Not a Phase 1 priority but the right reference point for the §10.5 framing.
- **Public dashboard (Phase 2)** — not a primary dashboard row given the Solana focus. Could appear as a "what an EVM RedStone Classic consumer sees" comparator if the dashboard scope extends off-Solana.
- **Methodology-disclosure asymmetry framing** — RedStone Classic is structurally identical to Live in disclosure terms (publishes a price + timestamp, no CI), so the publisher-dispersion-vs-coverage-SLA distinction soothsayer makes for Pyth applies in a stronger form here: RedStone Classic publishes neither a band nor a publisher-dispersion proxy. Useful in §1 framing as "even within RedStone, neither product publishes a verifiable calibration claim."

---

## 5. Known confusions / version pitfalls

- **Classic ≠ Live.** Classic is the EVM Push product (`PriceFeedsAdapter` + `PriceFeed`); Live is the 24/7-equity REST gateway (post-March-2026). Cross-referencing third-party "RedStone supports xyz" claims without checking which surface is the source of confusion. See [`oracles/redstone_live.md`](redstone_live.md) §5.
- **Classic ≠ Pull (Core).** Pull is the consumer-pull pattern (sign + verify in-tx, on-demand). Classic Push is the relayer-pushed-on-chain pattern. Both are RedStone products with overlapping documentation; the distinction is the consumption pattern.
- **Classic is EVM-only.** Cross-referencing "RedStone on Solana" presumes Pull (Wormhole-Queries) — Classic does not deploy on Solana. The four-PDA `redstone-sol` program (AVAX/ETH/SOL/BTC) is **not** Classic.
- **`PriceFeed` Chainlink-compat ≠ Chainlink semantics.** RedStone's `roundId` increments per push, not per OCR round; Chainlink's `roundId` carries OCR-round semantics. Code that relies on round-id semantics will be subtly different.
- **Permissionless relayers ≠ trustless prices.** The relayer can re-order or drop pushes; on-chain operator-quorum-signature validation prevents *forging* prices but not *withholding* them. Consumer code must check `updatedAt` for staleness.
- **`MIN_DEVIATION_PERCENTAGE` is per-deployment, not per-feed.** A consumer that integrates a RedStone-deployed adapter must inspect the deployment's configuration; assumptions about the deviation threshold do not transfer across deployments.
- **Heartbeat is in milliseconds.** Easy to misread as seconds.
- **Aggregation methodology depth opacity.** Same as Live — the underlying source-venue list and weighting are not surfaced in the Push docs at depth.
- **Docs link rot.** The deeper "models" page (`/docs/dapps-and-defi/redstone-models`) returned 404 on 2026-04-29 — same link-rot cluster as [`oracles/redstone_live.md`](redstone_live.md). The Push canonical page (`/docs/dapps/redstone-push/`) is currently accessible and is the load-bearing reference.

---

## 6. Open questions

1. **Does RedStone Classic publish equity feeds (SPY, QQQ, etc.) on any EVM chain?** **Why it matters:** if yes, soothsayer's Paper 1 §10.5 RWA-wave generalisation argument has a same-product cross-chain comparator (EVM RedStone Classic SPY vs. soothsayer's served band on SPYx); if no, the argument rests on Live and the Pull-Wormhole-Solana paths only. **Gating:** EVM contract probe (Etherscan-equivalent search for RedStone-deployed `PriceFeed` contracts; not soothsayer-blocking — could be a future analysis script outside the soothsayer/scryer pipeline).
2. **Why is RedStone Classic absent from Solana?** Architectural choice (Solana's account model is structurally different from EVM's contract-call model and the per-feed `PriceFeed` pattern doesn't translate cleanly), or roadmap choice (deferred for Pull/Wormhole-Queries to come first)? **Gating:** RedStone roadmap query.
3. **What's the `MIN_DEVIATION_PERCENTAGE` and `UPDATE_PRICE_INTERVAL` distribution across RedStone Classic deployments?** **Why it matters:** sets the operational stale-bound on RedStone Classic prices for any EVM consumer. **Gating:** EVM contract probe.
4. **Operator-quorum threshold for RedStone Classic.** Same opacity as for Live — the operator set composition and quorum threshold are not surfaced. **Gating:** RedStone team outreach (same hand-off as [`oracles/redstone_live.md`](redstone_live.md) §6 #1).
5. **Whether the `roundId` in a Chainlink-compat `PriceFeed` increments monotonically across deployments or resets on contract upgrade.** **Why it matters:** consumer code that relies on monotonicity. **Gating:** EVM contract probe.
6. **Cross-product price consistency.** For an asset (e.g., SPY) where RedStone publishes via Live (REST), Classic (EVM Push), and presumably Pull (EVM consumer-pull), is the price tuple identical at the same timestamp? Or do per-mode operator subsets produce small divergences? **Why it matters:** if divergent, choosing which mode to compare against soothsayer's band is a methodology choice that would affect Paper 1 §1's framing. **Gating:** multi-mode probe (REST + EVM contract + EVM consumer-pull tx).

---

## 7. Citations

- [`redstone-push-canonical`] RedStone. *Standardized Access for DeFi Interoperability — Push Model*. https://docs.redstone.finance/docs/dapps/redstone-push/. Accessed: 2026-04-29.
- [`redstone-pull-vs-push-blog`] RedStone. 2024-08-21. *Pull oracles vs Push oracles*. https://blog.redstone.finance/2024/08/21/pull-oracles-vs-push-oracles/. Cited via search results 2026-04-29.
- [`redstone-2026-comparison`] RedStone. 2026-03-30. *Blockchain Oracles Comparison: Chainlink vs Pyth vs RedStone [2026]*. https://blog.redstone.finance/2026/03/30/blockchain-oracles-comparison-chainlink-vs-pyth-vs-redstone-2026/. Cited via search results 2026-04-29.
- [`redstone-rwa-solana-blog`] RedStone. 2025-05-28. *RedStone RWA Oracle Brings Tokenized Assets to Solana Ecosystem*. https://blog.redstone.finance/2025/05/28/redstone-rwa-oracle-brings-tokenized-assets-to-solana-ecosystem/. Cited via search results 2026-04-29.
- [`redstone-models-404`] RedStone. *RedStone Models* (deep page). https://docs.redstone.finance/docs/dapps-and-defi/redstone-models → 404 on 2026-04-29; link rot logged (same cluster as [`oracles/redstone_live.md`](redstone_live.md) §7).
- [`redstone-live-companion`] Soothsayer internal. [`docs/sources/oracles/redstone_live.md`](redstone_live.md). The 24/7-equity REST gateway reconciliation file — Live's findings transfer transitively to Classic where the underlying aggregation is shared.
