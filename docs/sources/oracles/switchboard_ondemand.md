# `Switchboard — On-Demand (PullFeed + OracleJob + TEE)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.switchboard.xyz/` (canonical docs root, accessed 2026-04-29; the deep on-demand page at `https://docs.switchboard.xyz/switchboard/readme/on-demand` 307-redirects but does not resolve in our probe wave — link rot noted), search-result excerpts from `https://github.com/switchboard-xyz/on-demand` and `https://docs.rs/switchboard-on-demand-client` (cited via 2026-04-29 search), [`docs/data-sources.md`](../../data-sources.md) §7 lines 199-202 (the catalog summary citing OracleJob tasks `httpTask`, `jsonParseTask`, `oracleTask` + WASM/JS sandbox + max_staleness check), [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §1 (which surfaces the load-bearing fact that **Switchboard requires caller-initiated crank instructions** before consuming price data — different staleness behavior from Pyth).
**Version pin:** **Switchboard On-Demand** (the Pull-style successor to Switchboard V2's V2-Aggregator Push model). Two Solana program IDs are load-bearing per search-result references: **Oracle Program `SW1TCH7qEPTdLsDHRgPuMQjbQxKdH2aBStViMFnt64f`** and **Attestation Program (V3) `sbattyXrzedoNATfc4L31wC9Mhxsi1BmFhTiN8gDshx`** (TEE-enabling). Pin verification via on-chain probe is gated as a §6 task (no IDL pinned in `idl/switchboard/` today — this is a §6 hand-off if Switchboard becomes a soothsayer publishing surface per H3).
**Role in soothsayer stack:** `publishing-surface candidate` — soothsayer's published served-band could be exposed as a Switchboard `OracleJob` returning `(lower, mid, upper, k)` from a soothsayer-controlled HTTP endpoint, with on-chain consumers reading the soothsayer band via `PullFeedAccountData::get_value()` + `max_staleness` check. This is the H3-compatible publishing path and the operational basis for soothsayer's option to integrate as a Switchboard data-source rather than ship a dedicated relay program. Also a **comparator** in the sense that Switchboard is the **typical oracle provider** for marginfi-v2 banks (per [`oracles/marginfi.md`](../lending/marginfi.md) §1.1: "Typically, Switchboard is the oracle provider, but Pyth is also supported, and some banks have a Fixed price.").
**Schema in scryer:** **not in scryer.** `dataset/switchboard/...` does not exist; soothsayer does not consume Switchboard PullFeeds today. **TODO** if/when (a) soothsayer publishes via Switchboard (H3) and needs a self-mirror, or (b) Paper 3's MarginFi cross-reference requires capturing the Switchboard-wired bank prices at liquidation time. Add to scryer wishlist as a Paper-3 dependency once `marginfi/reserves/v1` lands and we identify the Switchboard-wired bank set.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

Switchboard On-Demand is a **permissionless, pull-based oracle protocol** where price computation is defined by an `OracleJob` — a sequential pipeline of tasks that fetch, transform, and aggregate data from external sources. Per the docs corpus accessed via search 2026-04-29:

- A `PullFeed` is the on-chain account holding the latest aggregated value plus metadata. Decoded via `PullFeedAccountData::get_value()` (per `switchboard-on-demand-client` Rust crate).
- An `OracleJob` is a **collection of sequential tasks**, where each task performs a specific operation:
  - `httpTask` — fetches data from an external HTTP endpoint.
  - `jsonParseTask` — parses the response JSON, typically via JSONPath.
  - `oracleTask` — folds in another oracle's value (e.g., Pyth, Chainlink) as a sub-input.
  - WASM/JS sandbox tasks — custom logic in attested compute.
- Each oracle node executes the same `OracleJob` independently, fetches the data, aggregates, and submits a signed value. The on-chain aggregator takes the **median** across nodes' submissions per the canonical Switchboard model. Median is the documented default; specific weighting / outlier-rejection rules are not surfaced in our 2026-04-29 docs read at the depth Pyth's 3N publisher-vote rule is.

The **TEE attestation path** (Attestation Program V3) lets oracle nodes execute the `OracleJob` inside a Trusted Execution Environment and attest on-chain that the execution was genuine. This is a Switchboard-specific trust mechanism distinct from Chainlink's DON-quorum or Pyth's publisher-vote — it's a single-node-with-attestation rather than a cross-node-quorum primitive.

### 1.2 Cadence / publication schedule

Switchboard On-Demand's defining cadence property is **caller-initiated**: there is no automatic push schedule. Per [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §1.2, "Switchboard requires caller-initiated 'crank' instructions before consuming price data — i.e., a consumer (or keeper) must trigger the Switchboard feed update; the price MarginFi reads is whatever the most recent crank produced." The crank pattern is two-instruction:

1. **Ed25519 Signature Verification** — Verifies the oracle operator's signature on the fresh price.
2. **Quote Program Storage** — Stores the verified data in the canonical `PullFeed` account.

The consumer reads the stored value after the two instructions land. Consumer code typically bundles all three instructions (crank-verify + crank-store + protocol-action) in a single tx so the price read is guaranteed fresh.

The operational consequence: during low-activity windows (weekends, low-keeper-coverage windows), a Switchboard-wired feed's on-chain `PullFeed` value can be **arbitrarily stale** because no consumer has cranked it. This is a fundamental difference from Pyth's regular `PriceAccount` (which Pyth publishers update every ~400ms regardless of consumer activity) and from Chainlink Data Streams (where the DON quorum drives a continuous update).

### 1.3 Fallback / degraded behavior

- **`max_staleness` check** — every consumer reads the `PullFeed` with a `max_staleness` parameter; the read fails (or returns a degraded code) if the on-chain value's age exceeds the threshold. This is the consumer-side stale-reject gate.
- **TEE attestation failure** — if the Attestation Program rejects an oracle's submitted attestation, the on-chain value is not refreshed.
- **Below-quorum oracle submissions** — the docs specify quorum threshold per feed; below-quorum, the aggregator does not commit a new value. Specific threshold semantics not surfaced in our probe.
- **OracleJob failure** (e.g., HTTP endpoint 5xx, JSON parse error) — the oracle node returns an error rather than a fabricated value; the aggregator excludes failed submissions when computing the median.

### 1.4 Schema / wire format

On-chain — `PullFeedAccountData` (per `switchboard-on-demand-client` Rust crate, search 2026-04-29):
- The current value (`i128` per docs, converted to `Decimal` by the SDK).
- The slot at which the value was last refreshed.
- The feed's `OracleJob` definition (or a hash thereof + an off-chain spec store).
- Operator-quorum signatures (or attestation references).

Off-chain — the `OracleJob` JSON spec is the human-authored oracle definition. A spec for a soothsayer-published band might look like:

```
{
  "tasks": [
    { "httpTask": { "url": "https://soothsayer.example/v1/band?asset=SPYx" } },
    { "jsonParseTask": { "path": "$.upper" } }
  ]
}
```

and a parallel job for `lower`. The deployment specifies which oracle nodes run the spec, the quorum threshold, and the attestation requirement.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** **not present.** No `dataset/switchboard/...` venue.
- **On-chain reads** are possible today via the program IDs above (`SW1TCH7qEPTdLsDHRgPuMQjbQxKdH2aBStViMFnt64f` for Oracle, `sbattyXrzedoNATfc4L31wC9Mhxsi1BmFhTiN8gDshx` for Attestation V3). No active soothsayer code reads these — neither H3 publishing nor a Switchboard consumer-side comparator.
- **Indirect surface (via MarginFi):** when `marginfi/reserves/v1` lands (per [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §6 #4), each bank's `bank.config.oracle_keys` will resolve to a Switchboard `PullFeed` account for the Switchboard-wired bank set. Cross-referencing the Switchboard `PullFeed.last_updated_slot` against marginfi liquidation events (when `marginfi/liquidations/v1` lands per [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §6 #7) will measure the empirical Switchboard staleness during liquidation moments. **This is the most concrete near-term measurement gating.**
- **No IDL pinned:** there is no `idl/switchboard/` in the soothsayer repo. If H3 publishing or scryer-side mirroring lands, IDL pin via `anchor idl fetch` against the program IDs above is a §6 setup task.

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| Switchboard On-Demand uses caller-initiated crank — no automatic push cadence. | Confirmed structurally per docs ("Every Switchboard oracle update requires two instructions in sequence: Ed25519 Signature Verification + Quote Program Storage"). **Operationally** this means a Switchboard-wired marginfi-v2 bank's price is whatever the most recent crank produced, which can be arbitrarily stale during low-activity windows. | **confirmed** |
| OracleJob aggregation is **median** across oracle nodes. | Confirmed structurally per the docs corpus reference: "each oracle fetches data from configured data sources, aggregates them, and submits a single i128 value to the feed on-chain." Median across nodes' submissions is the canonical Switchboard rule. **Specific weighting / outlier-rejection rules** at the depth Pyth's 3N rule is documented are **not surfaced** in our probe. | **partial (mechanism confirmed, depth opaque)** |
| TEE attestation provides verifiable off-chain compute. | Confirmed structurally via the Attestation Program V3 (`sbattyXrzedoNATfc4L31wC9Mhxsi1BmFhTiN8gDshx`). **Unmeasurable from soothsayer side** — we have no Switchboard consumer or attestation audit. | **confirmed (by docs)** |
| Switchboard is a "typical oracle provider" for marginfi-v2 banks. | Confirmed per [`oracles/marginfi.md`](../lending/marginfi.md) §1.1: "Typically, Switchboard is the oracle provider." **TODO when `marginfi/reserves/v1` lands** to measure actual provider distribution across xStock-adjacent and high-volume banks. | **confirmed (by README), unmeasured (distribution)** |
| Switchboard-wired feed staleness during weekends is a real liquidation-risk vector. | **TODO when `marginfi/liquidations/v1` + `marginfi/reserves/v1` land.** Cross-reference Switchboard `PullFeed.last_updated_slot` against marginfi liquidation events; segment by oracle provider; report stale-distribution at the moment of trigger. **Load-bearing for Paper 3 §3.** | **TODO (Paper 3 load-bearing)** |
| `max_staleness` is the consumer-side stale-reject gate. | Confirmed structurally per the docs. The exact `max_staleness` value used per marginfi-v2 bank is **TODO when `marginfi/reserves/v1` lands.** | **confirmed (mechanism), unmeasured (per-feed values)** |
| Switchboard supports custom feeds via `httpTask` + `jsonParseTask` + `oracleTask` (and WASM/JS sandbox). | Confirmed per [`docs/data-sources.md`](../../data-sources.md) §7 lines 200-201. The `oracleTask` is what enables a Switchboard feed to fold in Pyth or Chainlink as a sub-input. | **confirmed (by docs)** |
| Switchboard publishes a confidence interval / band. | **Contradicted by default surface.** A standard `PullFeed` carries a single value (`i128`); there is no built-in CI/dispersion field. A custom `OracleJob` could publish a band as multiple feeds (e.g., one per bound), but that's consumer-defined, not built-in. **This is the soothsayer-relevant note**: H3 publishing would deploy soothsayer's band as a multi-feed Switchboard configuration, not as a single feed. | **contradicted (default surface), opportunity (custom job)** |
| Solana program IDs `SW1TCH7qEPTdLsDHRgPuMQjbQxKdH2aBStViMFnt64f` (Oracle) + `sbattyXrzedoNATfc4L31wC9Mhxsi1BmFhTiN8gDshx` (Attestation V3). | Confirmed via search-result references; **not yet pinned via on-chain probe** in soothsayer repo. **TODO** if H3 publishing lands. | **confirmed (by docs), unverified (on-chain probe)** |

---

## 4. Market action / consumer impact

Switchboard's downstream impact is most concentrated in the Solana lending stack via MarginFi:

- **MarginFi (typical-oracle-provider)** — per [`oracles/marginfi.md`](../lending/marginfi.md) §1.1, Switchboard is the typical oracle provider. The conf-haircut rule (`P - conf` for assets, `P + conf` for liabilities) is structurally compatible with reading a calibrated band's `(lower, upper)` from soothsayer; the H3 publishing path would deploy soothsayer's band as a Switchboard `OracleJob` returning `(lower, upper)` and downstream marginfi-v2 banks could read it via the same `PullFeedAccountData::get_value()` interface. **Load-bearing for Paper 3 §6 / §7.**
- **Drift Protocol** — Drift uses Pyth on most markets per their public oracle stack; whether Drift consumes Switchboard feeds for any market class (xStock perps, niche assets) is a §6 open question.
- **Save (Solend) / Loopscale** — Solana lending; likely Pyth-primary but possibly Switchboard for some assets. **TODO** when respective reserve-config snapshots land.
- **Jupiter Lend (Fluid Vaults)** — likely Pyth-primary; Switchboard usage unverified. **TODO when `fluid_vault_config.v1` lands** ([`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 3, Priority 0).
- **Kamino klend (xStocks reserves only)** — uses Scope as primary oracle for xStocks, not Switchboard directly. For non-xStock Kamino reserves (other RWAs, stablecoins, crypto), Switchboard is plausibly used — TODO via `kamino/reserves/v1` snapshot when it lands ([`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 4).
- **Soothsayer's H3 publishing path (potential)** — the H3 hypothesis was: deploy soothsayer's served band as a Switchboard publisher. The Switchboard-publishing path would be:
  1. Spin up soothsayer-controlled HTTP endpoint returning `(lower, upper, k, asset)` JSON.
  2. Deploy a multi-`PullFeed` configuration (one per `(asset, bound)` pair) with `OracleJob` specs that `httpTask`+`jsonParseTask` against soothsayer's endpoint.
  3. Optionally enforce TEE attestation so consumers can verify the spec-execution provenance.
  4. Downstream marginfi-v2 banks (or other Switchboard consumers) integrate by adding the soothsayer feed accounts to `bank.config.oracle_keys`.
  - **Trade-off vs. dedicated relay program** ([`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 42): Switchboard publishing reuses an existing trusted oracle infrastructure, avoiding the soothsayer-streams-relay-program build cost but inheriting Switchboard's caller-crank cadence problem. Dedicated relay gives better cadence control but more bespoke infrastructure. The trade-off resolves on whether soothsayer wants caller-initiated freshness (Switchboard's pattern) or daemon-pushed freshness (relay's pattern).
- **Paper 1 §1 / §2 framing** — Switchboard's confidence-interval handling is consumer-defined (`OracleJob` shape). Unlike Pyth, there is no published-band-to-coverage-SLA finding to make against Switchboard's default surface. The soothsayer-relevant framing is "Switchboard is the cleanest publishing-surface for soothsayer's calibrated band because the OracleJob primitive accommodates band shapes natively."
- **Public dashboard (Phase 2)** — relevant as the reference target if H3 publishing ships.

---

## 5. Known confusions / version pitfalls

- **Switchboard V2 (Aggregator) ≠ On-Demand.** V2 had a Push-style Aggregator surface (legacy) where oracles ran a continuous-cadence loop; On-Demand is the Pull-style replacement. Cross-referencing pre-2024 Switchboard docs / blog posts is a frequent confusion. The Aggregator is deprecated; On-Demand is current.
- **`PullFeed` value freshness depends on the most recent crank, not on Switchboard's nominal cadence.** Code that assumes "Switchboard updates every X seconds" is wrong on On-Demand — there is no nominal cadence; consumers crank when they need the price.
- **Two program IDs (Oracle + Attestation).** Cross-referencing on-chain Switchboard activity must distinguish the two.
- **OracleJob is consumer-authored.** A "Switchboard feed for SPY" is not a Switchboard product per se — it's a job definition someone deployed. Two SPY feeds from different deployers can use different sources, different aggregation rules, different TEE configs.
- **TEE attestation is opt-in.** A `PullFeed` can be deployed with or without attestation; an attestation-required feed has different trust properties than a non-attested one.
- **`max_staleness` is consumer-side.** Each consumer chooses its own staleness threshold. A Switchboard feed value can be cross-consumed by two protocols with different staleness gates and produce different "is the price fresh" answers.
- **The crank tx pays the gas.** The consumer (or keeper) initiating the crank pays the on-chain gas plus any oracle-network fee. This is a per-update cost, not a subscription. For a low-traffic feed, the per-read cost can dominate.
- **Median across `n` nodes ≠ Pyth's 3N publisher-vote median.** Different aggregation primitive; the "robustness to outlier" properties are similar conceptually but not identical mathematically.
- **Docs link rot.** The deep on-demand readme page (`/switchboard/readme/on-demand`) 307-redirects but does not resolve in our probe. Use the `docs.switchboard.xyz/product-documentation/...` paths or the GitHub on-demand repo (`switchboard-xyz/on-demand`) for canonical references; the deeper deep-link space is unstable.

---

## 6. Open questions

1. **Pin the program IDs via on-chain probe.** **Why it matters:** if H3 publishing lands, the IDL pin is a setup prerequisite. **Gating:** `anchor idl fetch SW1TCH7qEPTdLsDHRgPuMQjbQxKdH2aBStViMFnt64f` + `... sbattyXrzedoNATfc4L31wC9Mhxsi1BmFhTiN8gDshx`; pin under `idl/switchboard/oracle.json` + `idl/switchboard/attestation_v3.json`. (This is on-chain reads, allowed under CLAUDE.md hard rule #1.)
2. **What is the operational distribution of Switchboard-wired vs Pyth-wired marginfi-v2 banks?** **Why it matters:** sets the marginfi-v2 surface that soothsayer's H3 publishing would integrate against. **Gating:** `marginfi/reserves/v1` snapshot ([`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §6 #4).
3. **What's the empirical staleness distribution of Switchboard-wired marginfi-v2 banks during weekends?** **Why it matters:** load-bearing for Paper 3 §3's "conf-haircut works as a real risk gate during off-hours" reconciliation. **Gating:** join `marginfi/reserves/v1` (when it lands) with on-chain Switchboard `PullFeed.last_updated_slot` reads (one-shot probe).
4. **Median or weighted-median or other Switchboard aggregation rule?** Docs surface "median" at high level; the precise rule (with weighting, outlier rejection, attestation-tiering) is not pinned to source-code depth. **Gating:** `switchboard-xyz/on-demand` GitHub repo source review.
5. **Per-feed quorum threshold semantics.** Below-quorum, the aggregator doesn't commit; what's the threshold? Configurable per deployment? **Gating:** docs depth probe + source review.
6. **Switchboard publishing fee model.** Per-crank gas + a per-update Switchboard-network fee; what's the magnitude for a Solana-mainnet crank with TEE attestation? **Why it matters:** sets the per-update cost soothsayer would pay if H3 publishes. **Gating:** Switchboard docs / sales conversation.
7. **Whether soothsayer's H3 publishing path or the dedicated relay path** ([`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 42) is the better deployment surface. The decision turns on cadence preference + ecosystem-integration cost. **Gating:** soothsayer roadmap decision; design comparison memo.
8. **Custom-job CI publishing pattern.** What's the canonical Switchboard-published-band shape — multi-feed (one per bound) or single-feed-with-custom-encoding (e.g., a `(lower, upper, k)` triple in a single `i128` via a packing convention)? **Gating:** Switchboard docs depth + community-pattern review.
9. **TEE-attestation real-world track record.** Has the Attestation V3 program had any verified attestation failures or compromises? **Why it matters:** if H3 ships with attestation as the trust assumption, the empirical record is load-bearing. **Gating:** Switchboard incident-history query.

---

## 7. Citations

- [`switchboard-docs-root`] Switchboard. *Switchboard Documentation*. https://docs.switchboard.xyz/. Accessed: 2026-04-29.
- [`switchboard-on-demand-github`] Switchboard. *on-demand* (GitHub). https://github.com/switchboard-xyz/on-demand. Cited via 2026-04-29 search results.
- [`switchboard-rust-client`] Switchboard. *switchboard-on-demand-client* (Rust crate). https://docs.rs/switchboard-on-demand-client. Cited via 2026-04-29 search results.
- [`switchboard-solana-sdk`] Switchboard. *solana-sdk* (GitHub). https://github.com/switchboard-xyz/solana-sdk. Cited via 2026-04-29 search results.
- [`rareskills-switchboard`] RareSkills. *Solana Switchboard Oracle*. https://rareskills.io/post/solana-switchboard-oracle. Cited via 2026-04-29 search results (reference for the two program IDs and high-level architecture).
- [`solana-compass-switchboard`] Solana Compass. *Switchboard Oracle Network: Customizable Data Feeds, TEEs, and Jito Integration*. https://solanacompass.com/learn/Midcurve/plug-in-with-switchboard-ep-41. Cited via 2026-04-29 search results.
- [`marginfi-companion`] Soothsayer internal. [`docs/sources/lending/marginfi.md`](../lending/marginfi.md). The §1.1 "typical oracle provider" finding + §1.2 caller-initiated-crank consequence.
- [`switchboard-data-sources-catalog`] Soothsayer internal. [`docs/data-sources.md`](../../data-sources.md) §7 lines 199-202. The `OracleJob` task list summary used as a high-level reference.
- [`switchboard-deep-page-redirect`] Switchboard. *On-Demand readme* (deep page). https://docs.switchboard.xyz/switchboard/readme/on-demand → 307 redirect, target does not resolve in our 2026-04-29 probe; documented as link rot.
