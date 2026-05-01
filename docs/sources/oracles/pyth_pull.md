# `Pyth Network — Pull (Wormhole-bridged PriceUpdate)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.pyth.network/price-feeds/core/how-pyth-works/hermes` (accessed 2026-04-29; describes the Wormhole-VAA + Merkle-proof flow at a high level, returns the Hermes REST schema with `id`, `price{price, conf, expo, publish_time}`, `ema_price{...}` — the on-Solana `PriceAccount` schema is the canonical surface for the *regular* feed and is documented in [`oracles/pyth_regular.md`](pyth_regular.md)), `https://docs.pyth.network/price-feeds/core/pull-updates` (accessed 2026-04-29; describes the consumer-pull pattern conceptually but is thin on the on-EVM `PriceUpdate` envelope structure — multiple deep pages 404'd, see §5), `https://docs.pyth.network/price-feeds/core/how-pyth-works/cross-chain` (accessed 2026-04-29; the Wormhole + Pythnet bridge architecture).
**Version pin:** **Pull oracle (Wormhole-VAA-bridged PriceUpdate)** — the Pyth deployment model active on every non-Solana chain (EVM, Aptos, Sui, Cosmos via IBC, etc.) and the **alternative** consumer-side pattern on Solana itself (since 2024 — Solana's regular `PriceAccount` is the *push* path; Pull is also available on Solana via the `pyth-solana-receiver`). Aggregation is identical to regular Pyth (3N publisher-vote median + Q25/Q75 confidence) — the **transport** is what differs.
**Role in soothsayer stack:** `comparator (off-Solana primarily)` — soothsayer is a Solana-native oracle and consumes Pyth via the on-Solana `PriceAccount` (regular) path. The Pull surface is relevant primarily as: (a) the architecture of any future cross-chain consumer of soothsayer's bands; (b) the comparator that non-Solana xStock-equivalent venues (EVM tokenized stocks, when they ship) read; (c) the reference for Pyth Lazer's transport (which extends the same VAA + Merkle architecture, see [`oracles/pyth_lazer.md`](pyth_lazer.md)).
**Schema in scryer:** **not in scryer.** No EVM consumer paths are currently captured; `dataset/pyth_pull/...` does not exist. Soothsayer reads the on-Solana regular path via `dataset/pyth/oracle_tape/v1/...` (`pyth.v1`); see [`oracles/pyth_regular.md`](pyth_regular.md) §2 for the loader. **TODO**: if a future paper requires cross-chain xStock comparison, add `pyth_pull/...` venue + a Hermes consumer in scryer.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

The aggregation rule is **identical** to Pyth regular (the on-Solana `PriceAccount` path):

- Each publisher submits `(p_i, c_i)` on Pythnet.
- Pythnet's on-chain oracle program computes the 3N publisher-vote median + Q25/Q75 confidence. (Verbatim from the Hermes docs: "data providers publish their prices on Pythnet, and the on-chain oracle program then aggregates prices for a feed to obtain the aggregate price and confidence.")
- The result is the same `(price, conf, expo, publish_time)` tuple plus EMA twin.

What differs is the **transport** — the path from Pythnet's aggregation result to a non-Solana consumer:

1. **Pythnet validators emit a Wormhole message every Pythnet slot** containing the Merkle root of all the prices in that slot.
2. **Wormhole guardians observe the Merkle root** and create a signed VAA (Verifiable Action Approval) — a multi-signature attestation of the Pythnet message.
3. **Hermes** continually listens to both Pythnet (for the price messages themselves) and Wormhole (for the signed VAAs of the Merkle roots), and stores the latest tuple of `(price_message, merkle_proof, signed_vaa)` in memory.
4. **Consumers** retrieve the latest update from Hermes via REST/SSE, submit the bundle in their on-chain transaction, and the consumer chain's Pyth receiver contract verifies the VAA's Wormhole signatures + Merkle proof before exposing the price to the calling contract.

The on-EVM consumer surface (Pyth's `IPyth` interface) exposes:

- `getPrice(bytes32 id)` — returns `(price, conf, expo, publishTime)`.
- `getPriceUnsafe(bytes32 id)` — same, without staleness checking.
- `getEmaPrice(bytes32 id)`, `getEmaPriceUnsafe(bytes32 id)` — the EMA twin.
- `updatePriceFeeds(bytes[] calldata updateData)` — the consumer-side call that takes the Hermes-fetched bundle, verifies the VAA, and writes to on-chain storage.
- `getUpdateFee(bytes[] calldata updateData)` — the per-update fee, paid in the consumer chain's native token.

### 1.2 Cadence / publication schedule

Pythnet aggregation cadence: every Pythnet slot (~400ms per the Pyth docs at `core/pull-updates`: "every Pyth price feed updates at every 400 milliseconds"). Wormhole guardian observation + signing adds a few seconds of latency. Hermes serves the latest. Consumer-chain `updatePriceFeeds` is **on-demand, paid per update** — there is no automatic re-push to consumer chains; it is the consumer's responsibility to bundle the update with their tx (or run a keeper that does).

This is the pattern's defining trade-off: lower aggregate operating cost (Pyth doesn't pay gas to maintain a pushed feed on every chain), but consumer-side update cost on every read. A consumer reading `getPriceUnsafe` against a stale storage value pays nothing; a consumer that needs fresh data pays `getUpdateFee` + the transaction's gas to update.

### 1.3 Fallback / degraded behavior

- **`publishTime` staleness gate.** `getPrice` reverts if the on-chain `publishTime` is older than a configurable threshold (default 60 seconds for `getPrice`); `getPriceUnsafe` skips this check. Consumers that allow stale reads via `getPriceUnsafe` accept any non-zero stored value.
- **Wormhole guardian-quorum requirement.** The VAA must carry at least 13 guardian signatures (out of 19) to verify on-chain. If fewer are available — e.g., during a Wormhole-network incident — the on-chain receiver rejects the update and storage is not refreshed.
- **EMA fallback.** When the snap aggregate is suppressed (below `min_publishers`), the EMA twin still updates per publisher activity. Consumer code that toggles between `price` and `ema_price` based on `publishTime` is the documented degraded-state pattern.
- **Per-chain receiver upgrade path.** Chainlink's Verifier program is a single contract; Pyth's pull-receivers are per-chain (one EVM contract per EVM chain, etc.) — a bug in the receiver requires a per-chain upgrade campaign. The Pythnet-side aggregation is unaffected.

### 1.4 Schema / wire format

The bundle a consumer pulls from Hermes per the `/v2/updates/price/latest` endpoint includes (per `core/how-pyth-works/hermes` accessed 2026-04-29):

```
{
  "id":            "<bytes32 hex feed id>",
  "price":     { "price": "<i64>", "conf": "<u64>", "expo": "<i32>", "publish_time": "<unix-seconds>" },
  "ema_price": { "price": "<i64>", "conf": "<u64>", "expo": "<i32>", "publish_time": "<unix-seconds>" },
  "metadata":  { "slot": "<u64>", "proof_available_time": "<unix>", "prev_publish_time": "<unix>" },
  "vaa":       "<base64-encoded-signed-VAA>"
}
```

The `vaa` blob, when base64-decoded, is a Wormhole VAA carrying a Merkle root commitment over a batch of price messages; the Merkle proof for each individual feed lives alongside the price message in Hermes's response. The on-chain receiver verifies (a) Wormhole's guardian-quorum signatures on the VAA, (b) the Merkle proof linking the per-feed price message to the VAA-committed root, and (c) optionally a staleness check against `publish_time`.

**Per-publisher data is not in the Pull bundle** — the same constraint as the on-Solana regular path. The pull receiver exposes the aggregate only.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** **not present.** Soothsayer's tape includes the on-Solana regular Pyth path (`dataset/pyth/oracle_tape/v1/...`, `pyth.v1` schema), not the Pull / Hermes-bundle path. There is no `dataset/pyth_pull/...` venue.
- **No on-chain reads:** soothsayer does not pull Hermes bundles into any production code path. The only places a Pull surface would appear in our work are: (a) hypothetical EVM-side consumer comparators if the xStock universe expanded off-Solana; (b) the soothsayer-streams-relay-program design discussion as a structural reference (the relay's `post_relay_update` PDA is conceptually a Pyth-pull-style "verified once, read many" surface — see [`oracles/chainlink_data_streams.md`](chainlink_data_streams.md) §4).
- **Cross-reference to regular path:** for any xStock-underlier feed (SPY, QQQ, etc.), the Pull bundle and the on-Solana regular `PriceAccount` carry the **same aggregate value at the same Pythnet slot** — they are two views of the same upstream computation. The reconciliation in [`oracles/pyth_regular.md`](pyth_regular.md) §3 (publisher-dispersion-vs-coverage-SLA) applies identically to the Pull surface; the `pyth_conf` widening / collapse on closed-market windows is a Pythnet-aggregation phenomenon, not transport-layer.
- **TODO when needed:** if a future paper requires EVM-side comparison (for example, EVM-tokenized treasuries reading Pyth Pull), the scryer wishlist needs a `pyth_pull` venue + a Hermes consumer daemon. Not currently in `scryer/wishlist.md` Priority 0–4.

---

## 3. Reconciliation: stated vs. observed

The reconciliation is structurally limited because we do not have a Pull-side tape. What we *can* state from the cross-reference to the regular path and from public-doc reading:

| Stated claim | Observation | Verdict |
|---|---|---|
| Pull aggregation is identical to regular Pyth — same 3N median rule. | Confirmed structurally — the docs explicitly state "data providers publish their prices on Pythnet, and the on-chain oracle program then aggregates prices for a feed to obtain the aggregate price and confidence" — this is the same Pythnet-side aggregation as the regular feed. | **confirmed (by transitivity to regular path)** |
| The transport is Wormhole-VAA-bridged with Merkle proofs. | Confirmed — the `vaa` field in Hermes's response is base64-encoded VAA bytes; the Merkle-proof structure is the documented bundle shape. | **confirmed** |
| The Wormhole guardian quorum is the single point of trust on the bridge. | Confirmed structurally (per the cross-chain docs page accessed 2026-04-29). The 13-of-19 quorum is well-known industry-wide; soothsayer has not independently audited it. | **confirmed (by reference)** |
| Update fees are paid per-`updatePriceFeeds`-call by the consumer. | Confirmed structurally via `IPyth.getUpdateFee`. **Unmeasurable from soothsayer's side** — we have no EVM consumer producing a fee log. | **confirmed (by docs), unmeasured** |
| Pyth Pull on EVM publishes a confidence interval / band that consumers can use as a coverage SLA. | **Inherits the publisher-dispersion-vs-coverage-SLA finding from the regular path.** Per [`oracles/pyth_regular.md`](pyth_regular.md) §3, Pyth's confidence is a publisher-dispersion signal, not a calibrated coverage SLA. The Pull transport does not change this — the band is computed Pythnet-side and shipped over the Wormhole bridge. | **contradicted (transitively from regular path)** |
| Pyth Pull is available on Solana as an alternative to the regular `PriceAccount` push path. | Confirmed structurally per the `pyth-solana-receiver` integration docs at `core/use-real-time-data/pull-integration/solana`. **Unmeasured in our tape** — soothsayer reads the regular path. | **confirmed (by docs)** |
| Per-publisher data is not exposed in the Pull bundle. | Confirmed — the documented response schema (`price`, `ema_price`, `metadata`, `vaa`) carries only the aggregate, not the underlying `[PriceComponent; 32]`. Same constraint as the on-Solana regular path. | **confirmed** |
| Hermes returns the latest update with a configurable staleness threshold (default 60s for `getPrice`). | Confirmed structurally via the `IPyth` interface. **Unmeasurable from our data.** | **confirmed (by docs)** |

The substantive reconciliation cells live in [`oracles/pyth_regular.md`](pyth_regular.md) §3 and apply to Pull by transitivity (same Pythnet-side aggregation). The Pull-specific surface is the transport; the headline empirical finding (publisher-dispersion-vs-coverage-SLA) does not change.

---

## 4. Market action / consumer impact

Pyth Pull is the active oracle path for tokenized-equity exposures **off-Solana**:

- **EVM tokenized-stock issuance (Backed Finance EVM xStocks)** — Backed Finance has issued some xStocks on EVM chains (per their public docs, the bxStock token family is multi-chain). EVM-side consumers reading those tokens use Pyth Pull. The publisher-dispersion-vs-coverage-SLA finding applies here too: any EVM lending protocol haircuting collateral by `pyth_conf` will mechanically narrow during pre-close (publishers cluster) and widen post-close (publishers thin). **TODO when scryer adds an EVM-side comparator surface.**
- **Aave / Compound / EVM-lending consumers** — most major EVM lending markets read Pyth Pull for non-Chainlink-Aggregator-supported feeds. Where soothsayer's bands could plausibly be consumed off-chain, the integration shape is "publish a soothsayer band as an EVM-readable feed (analogous to a Pyth Pull receiver), and EVM consumers read it via the same `getPrice / getPriceUnsafe` interface pattern."
- **Drift Protocol** — Solana-native; uses the regular `PriceAccount` path, not Pull. Cross-reference to [`oracles/pyth_regular.md`](pyth_regular.md) §4 for Drift's actual oracle integration.
- **MarginFi** — Solana-native; same regular-path consumer.
- **Hyperliquid** — runs its own native chain; Pyth Pull is the bridge if Hyperliquid uses Pyth at all (Hyperliquid's mark / liquidation oracle is its own venue per [`perps/hyperliquid_perps.md`](../perps/hyperliquid_perps.md), so this is not a live integration).
- **Soothsayer-streams-relay-program (analogy, not consumer)** — the soothsayer-side relay design (`scryer/wishlist.md` item 42) is conceptually similar to a Pyth Pull receiver: verify-once, read-many, with a soothsayer-controlled PDA carrying the verified bytes. The architecture transfer is intentional.
- **Paper 1 framing** — Pull does not change the §1 publisher-dispersion-vs-coverage-SLA finding; it extends the framing's geographic scope ("the same calibration claim applies on every chain a Pyth pull-receiver is deployed to"). Useful in §10's generalisation discussion as the reach of the publisher-dispersion-vs-SLA finding.
- **Public dashboard (Phase 2)** — not a primary dashboard row given the soothsayer Solana focus, but worth noting for "this is what a non-Solana consumer of Pyth sees" framing.

---

## 5. Known confusions / version pitfalls

- **Pyth Pull ≠ Pyth regular.** Same aggregation, different transport. Cross-referencing "Pyth confidence" without checking which surface is the source of confusion. **Pyth on Solana** is by default the regular `PriceAccount` push path; **Pyth on EVM** is by default the Pull / Hermes-bundle path. **Pyth on Solana** can also be Pull (via `pyth-solana-receiver`) if a consumer prefers — same chain, two patterns.
- **Hermes is not a price source — it's a relay of signed-VAAs.** Treating Hermes as the authoritative endpoint instead of as a relay of Pythnet-aggregated values is a frequent confusion; the Hermes service can go down without affecting on-chain Pyth state where storage is already populated.
- **`getPrice` vs `getPriceUnsafe`.** The former applies the staleness gate (default 60s); the latter does not. Production consumers that need to differentiate "no price available" from "stale price" must use `getPriceUnsafe` + their own freshness check.
- **Wormhole guardian quorum is the bridge trust assumption.** A Pyth Pull consumer is also implicitly a Wormhole consumer; cross-domain assumption stacking. Many Pyth Pull integration audits flag this as a re-entrancy / governance risk.
- **`publish_time` is *Pythnet's* publish time, not the consumer chain's update time.** A consumer reading `publish_time` after a fresh `updatePriceFeeds` will see Pythnet's slot timestamp, which can be tens of seconds before the consumer-chain block. Code that compares against `block.timestamp` for staleness must account for this.
- **`updateData` byte format is opaque ABI.** Consumer contracts that hardcode the byte layout will break if Pyth ships a v2 envelope. Use the `IPyth.parsePriceFeedUpdates` helper rather than walking bytes manually.
- **Per-chain receiver versions can drift.** Solana's pull-receiver, EVM's pull-receiver, Aptos's pull-receiver are independently upgraded. A claim like "Pyth Pull supports xyz" must be qualified by chain and receiver version.
- **Fee in the consumer chain's native token.** EVM Pull pays in ETH/MATIC/BNB; Solana Pull pays in SOL. The fee schedule is per-chain and not reconcilable globally.
- **Docs link rot.** The pythnet-price-feeds/pull-updates page at `https://docs.pyth.network/price-feeds/pythnet-price-feeds/pull-updates` exists but is thin; deeper reference pages (`/pythnet-reference/structure`) returned 404 on 2026-04-29 — Pyth has refactored docs around the `core/` namespace. When citing, prefer `docs.pyth.network/price-feeds/core/...` URLs.

---

## 6. Open questions

1. **Per-feed update fee for xStock-underlier feeds** (SPY, QQQ, TSLA, ...) on each EVM chain. **Why it matters:** if an EVM consumer wanted to compare soothsayer's served band to Pyth Pull, the per-update fee sets the comparison cadence. **Gating:** Pyth Hermes API probe per chain (would need a non-soothsayer client; not soothsayer-blocking).
2. **Whether the Wormhole-quorum failure mode has ever manifested for an xStock-underlier feed.** **Why it matters:** if a guardian-quorum stale-out has historically blocked a Pull update during a closed-market window, the publisher-dispersion-vs-SLA finding is compounded by transport-layer risk. **Gating:** Wormhole guardian-status historical scrape.
3. **Is Pyth Pull's `publish_time` ever observably later than the regular `PriceAccount.publish_time` for the same feed at the same Pythnet slot?** **Why it matters:** Pull's transport latency (Pythnet → Wormhole → Hermes → consumer chain) is plausibly larger than regular's (Pythnet → Solana, since Solana validators run Pythnet). **Gating:** dual-tape capture (would require a non-Solana scryer fetcher).
4. **Whether any Solana-native consumer reads Pyth via `pyth-solana-receiver` (Pull on Solana) rather than the regular `PriceAccount`** path. **Why it matters:** the loader at `src/soothsayer/sources/scryer.py:179` reads the regular path; if a downstream consumer reads Pull on Solana instead, our reconciliation may not transfer cleanly. **Gating:** Solana program-log audit for `pyth-solana-receiver` CPI calls.
5. **Whether soothsayer's eventual cross-chain consumer surface should mirror Pyth Pull** (Wormhole-VAA + Merkle proof) or take a simpler approach (e.g., LayerZero-style direct messaging, or a per-chain Switchboard-style oracle job). **Why it matters:** mirroring Pull lets soothsayer reuse Pyth's on-chain receiver pattern; a different model needs custom on-chain code. **Gating:** soothsayer roadmap decision; not in scope for Phase 1.

---

## 7. Citations

- [`pyth-hermes-overview`] Pyth Network. *Hermes — high-performance web service for delivering Pyth price updates*. https://docs.pyth.network/price-feeds/core/how-pyth-works/hermes. Accessed: 2026-04-29.
- [`pyth-pull-updates`] Pyth Network. *What is a Pull Oracle?*. https://docs.pyth.network/price-feeds/core/pull-updates. Accessed: 2026-04-29.
- [`pyth-cross-chain`] Pyth Network. *Cross-chain (Wormhole + Pythnet bridge architecture)*. https://docs.pyth.network/price-feeds/core/how-pyth-works/cross-chain. Accessed: 2026-04-29.
- [`pyth-solana-pull`] Pyth Network. *Use Real-Time Data in Solana Programs*. https://docs.pyth.network/price-feeds/core/use-real-time-data/pull-integration/solana. Accessed: 2026-04-29.
- [`pyth-pull-original`] Pyth Network. *Pull, Don't Push: A New Price Oracle Architecture*. https://www.pyth.network/blog/pyth-a-new-model-to-the-price-oracle. (Original blog post on the Pull model, referenced for historical context.)
- [`pyth-regular-companion`] Soothsayer internal. [`docs/sources/oracles/pyth_regular.md`](pyth_regular.md). The on-Solana regular `PriceAccount` reconciliation file — Pull's aggregation findings transfer transitively from this file.
- [`pyth-pull-deeper-pages-404`] Pyth Network. *Deeper reference pages on PriceUpdate envelope structure* (e.g., `/pythnet-reference/structure`, `/how-pyth-works/pull-updates`). https://docs.pyth.network/price-feeds/pythnet-reference/structure → 404 on 2026-04-29; documented as link rot — Pyth has refactored docs around the `core/` namespace.
