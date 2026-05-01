# `Stork (Solana RWA stack)` — Methodology vs. Observed [DRAFT]

> **Status: 🚧 draft.** Public documentation is structurally thin in two ways that gate a full reconciliation: (a) no aggregation methodology is surfaced ("continuously aggregates, verifies, and audits data from trusted publishers" is the depth available); (b) no Solana program ID is surfaced in the public docs page accessed today. This file is intentionally smaller (~10 KB) than the v11/Pyth files; §1 / §3 / §6 are populated honestly with what's missing rather than padded.

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.stork.network/` (accessed 2026-04-29; landing page only — covers high-level cadence claim "sub-second latency and frequency", "500+ assets on 70+ chains", and lists supported chains as "EVM chains, Solana, Sui, Aptos, and more"; **no aggregation methodology, no fee model, no confidence/dispersion fields surfaced**), `https://github.com/Stork-Oracle/Documentation/blob/main/api-reference/contract-apis/solana.md` (accessed 2026-04-29; references `stork-solana-sdk` on crates.io and "Temporal Numeric Value Feed PDA accounts" but **does not surface the Solana program ID**), `https://www.stork.network/case-studies/ostium-rwa-custom-oracle` (cited via 2026-04-29 search; positions Stork as "first built for perp DEX oracle, then extended"; mentions "custom Stork aggregator capable of parsing both market hours and bid/ask data for inclusion in price reports" — relevant to the RWA framing but methodology depth opaque).
**Version pin:** **Stork (current)** — the docs landing page does not version its content. The Solana SDK is `stork-solana-sdk >= 0.0.7` per the GitHub docs page; pin verification via on-chain probe is gated as a §6 task.
**Role in soothsayer stack:** `comparator (lower priority)` — Stork is in the Solana RWA-oracle landscape but does not surface as a consumer for any major Solana lending market in our stack reads (Kamino uses Scope; MarginFi uses Switchboard/Pyth/Fixed; Drift uses Pyth on most markets). Stork's positioning is "low-latency perp / DEX oracle, extended into RWA" via custom aggregator; its addressable consumer set on Solana for xStock-class assets is unverified and likely small. Cross-reference value is rhetorical: "Stork exists in the Solana oracle landscape, the methodology is undisclosed at the depth required, and it is not currently consumed by any major xStock lending market we observe."
**Schema in scryer:** **not in scryer.** `dataset/stork/...` does not exist; not in `scryer/wishlist.md` Priority 0–4. **No active integration target** — would require a downstream consumer cite (e.g., a Solana lending market reading Stork PDAs) to justify scryer-side capture.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

**Methodology is undisclosed at the depth required for a reconciliation file.** Per the Stork docs landing page (accessed 2026-04-29): Stork "continuously aggregates, verifies, and audits data from trusted publishers." This is the depth surface — there is no published rule comparable to:

- Pyth's 3N publisher-vote median + Q25/Q75 confidence (see [`oracles/pyth_regular.md`](pyth_regular.md) §1.1),
- Chainlink's DON-quorum signature + per-schema field set (see [`oracles/chainlink_v11.md`](chainlink_v11.md) §1.1),
- RedStone's modular-source aggregation (which is *also* opaque at the source-list and weighting level — see [`oracles/redstone_live.md`](redstone_live.md) §1.1).

Stork's RWA case-study material (Ostium) mentions "custom pricing algorithms" and "a bespoke Stork aggregator capable of parsing both market hours and bid/ask data" — i.e., Stork's aggregator can consume bid/ask information into its outputs, which is a methodology design choice but not a methodology *disclosure*.

### 1.2 Cadence / publication schedule

Per the docs landing page: "sub-second latency and frequency" with "pull as often as needed." This is consistent with a Pull-style model where consumers initiate updates (similar to Pyth Pull / Switchboard On-Demand), but the docs page does not specify whether Stork uses a Pull or Push pattern on Solana, what the per-update cost is, or whether there is a default cadence in absence of consumer pulls.

### 1.3 Fallback / degraded behavior

**Not surfaced in public docs.** No mention of stale-rejection thresholds, publisher-quorum failure handling, or fee-token-mismatch rejection.

### 1.4 Schema / wire format

The Solana docs page references "Temporal Numeric Value Feed PDA accounts that represent Stork data feeds" but does not surface field names, types, or layout. The `stork-solana-sdk` Rust crate provides "useful methods and structs for reading from stork price feed account." Pin the layout via:

- `cargo doc --open` against `stork-solana-sdk` (gates on toolchain availability), or
- on-chain probe of the Stork program ID (which is **not surfaced in the public Solana docs page accessed today** — separate "Solana Contract Addresses" page exists per the GitHub material but was not retrieved in our probe wave).

---

## 2. Observable signals (where this lives in our data)

**Currently: nothing.** No scryer venue, no Solana program ID pinned in soothsayer, no IDL at `idl/stork/`. The `stork-solana-sdk` Rust crate is a public artefact but soothsayer does not depend on it.

What needs to land for §3 / §4 to be empirically grounded:

1. **Program ID pin.** Fetch the Solana contract address from `https://github.com/Stork-Oracle/Documentation/blob/main/resources/contract-addresses/solana.md` (the page referenced but not surfaced in our probe wave).
2. **IDL pin** at `idl/stork/stork-solana.json` — fetchable via `anchor idl fetch <PROGRAM_ID>` once the program ID is known.
3. **A consumer-cite.** Without at least one downstream consumer reading Stork on Solana for an xStock-class or RWA-class asset, scryer-side capture is not justified. Per §4 below: no major Solana lending market we observe consumes Stork.

---

## 3. Reconciliation: stated vs. observed

The reconciliation here is **structurally limited** because the public methodology surface is thin and soothsayer has no Stork tape.

| Stated claim | Observation | Verdict |
|---|---|---|
| Stork supports Solana for price feeds. | Confirmed structurally per the docs landing page ("500+ assets on 70+ chains, including ... Solana"). **Unverified at the per-feed level** — whether Stork publishes any xStock-class or US-equity feeds on Solana is **TODO**: the Asset ID Registry referenced in the docs was not surfaced in our probe wave. | **partial** |
| Stork's aggregator can parse "market hours and bid/ask data" for RWA price reports. | Confirmed structurally per the Ostium case study. **Unmeasurable from soothsayer side** — we have no Stork tape. **Indirect comparison to Chainlink v11 weekend bid/ask** ([`oracles/chainlink_v11.md`](chainlink_v11.md) §3): Chainlink's bid/ask weekend behaviour is the synthetic-bookend pattern; whether Stork's "market hours and bid/ask" parsing produces a different shape is the load-bearing question, but unmeasurable today. | **unmeasurable from public surface** |
| Stork provides sub-second latency and frequency on Solana. | Confirmed by docs claim. **Unmeasurable from soothsayer side** without integration. | **confirmed (by docs), unmeasured** |
| Stork is consumed by major Solana lending markets for xStock-class assets. | **Contradicted (no live consumer surface).** Kamino uses Scope ([`oracles/scope.md`](scope.md)); MarginFi uses Switchboard/Pyth/Fixed ([`oracles/marginfi.md`](../lending/marginfi.md)); Drift uses Pyth on most markets ([`oracles/pyth_regular.md`](pyth_regular.md) §4). No Solana lending market we have surveyed consumes Stork. | **contradicted (for our addressable set)** |
| Stork publishes a confidence interval / coverage band. | **Unmeasurable from public surface.** No CI / dispersion / band field is surfaced in the docs. The `stork-solana-sdk` PDA structure may carry such a field, but the depth is not in our probe. | **unmeasurable** |
| Stork's methodology is comparable in disclosure depth to Pyth or Chainlink. | **Contradicted.** Pyth publishes the 3N publisher-vote rule (precise); Chainlink publishes the v11 schema (precise) and acknowledges weekend semantics (less precise, see [`oracles/chainlink_v11.md`](chainlink_v11.md) §3); RedStone's methodology is opaque but their modular-source structure has a public taxonomy. Stork's docs page surfaces "trusted publishers" + "continuously aggregates, verifies, and audits" — this is the thinnest-disclosure surface among the four oracles in our stack. | **contradicted (relative)** |
| Stork is "the leading oracle for low-latency DeFi protocols" (per their own marketing). | **Unmeasurable empirically.** "Leading" is a marketing claim; soothsayer has no comparison data. | **unmeasurable (marketing claim)** |

---

## 4. Market action / consumer impact

Stork's downstream impact for **soothsayer's xStock target stack is structurally minimal** — no major Solana lending market we observe consumes Stork. The relevance is rhetorical:

- **Solana lending stack** — Kamino (Scope), MarginFi (Switchboard / Pyth / Fixed), Drift (Pyth on most markets), Save/Loopscale (likely Pyth), Jupiter Lend (likely Pyth). None document Stork as a primary or secondary oracle. **TODO** if any of these add Stork integration in future.
- **Perps venues** — Stork's positioning is "first built for perp DEX oracle" (per their case-study material). Whether Drift or Hyperliquid consume Stork for any market class is a §6 open question. Ostium (the case study) is a non-Solana perp DEX (per the search result link — Ostium-labs.gitbook.io context). Drift v2 spot/perps appear to consume Pyth predominantly per their public oracle stack.
- **MarginFi** — public docs do not list Stork (per [`oracles/marginfi.md`](../lending/marginfi.md) §1.1).
- **Jupiter Lend / Save / Loopscale** — same; no Stork integration documented.
- **Kamino klend** — uses Scope, not Stork. Kamino is not an addressable Stork consumer.
- **Paper 1 §1 / §2 framing** — Stork is the cleanest single-line example of the **methodology disclosure asymmetry** Paper 1's framing turns on. "Of the four major Solana oracles (Pyth / Chainlink / RedStone / Stork), three publish at least a partial methodology and one (Stork) publishes essentially marketing language." This is rhetorically useful but factually applies to the *most opaque* end of the asymmetry — the Pyth-vs-Chainlink-vs-RedStone reconciliation captures the load-bearing comparator analysis.
- **Public dashboard (Phase 2)** — not a primary dashboard row; could appear as a "fourth oracle archetype: methodology fully undisclosed" framing. Low priority.
- **Non-Kamino consumer enforcement (INDEX rule):** because Stork has no measurable Solana consumer in our stack, this file does **not** satisfy the INDEX §4 "non-Kamino consumer cite required for ✅ live" rule. **Mark as 🚧 draft in INDEX.md.**

---

## 5. Known confusions / version pitfalls

- **Stork ≠ Stork as in the SQL/JSON streaming engine.** Multiple unrelated products use the "Stork" name; this file is about the oracle protocol at `stork.network`.
- **Stork ≠ Storm Trade.** Storm Trade is a separate platform (`storm.tg`) that mentions price oracle infrastructure; not Stork Oracle.
- **`stork-solana-sdk` versioning.** Rust crate at `>=0.0.7` per the docs page; pre-1.0, schema may evolve. Pin a specific version in any soothsayer-side integration.
- **"Temporal Numeric Value Feed PDA"** is Stork-specific terminology — not a synonym for Pyth's `PriceAccount` or Switchboard's `PullFeed`. Cross-referencing without the term-level distinction is a confusion.
- **Per-chain program IDs.** Stork is multi-chain; Solana, EVM, Aptos, Sui, etc. all have their own deployments. The docs landing page does not enumerate them; cross-referencing "Stork has X feature" without specifying the chain is risk-prone.
- **RWA framing is from the case-study material, not from a documented RWA-product page.** Stork's RWA positioning ("Long or Short Anything with Stork's Custom Oracle Solution") is marketing copy from a case study, not a methodology page. The "custom Stork aggregator capable of parsing market hours and bid/ask data" is a phrase from this material; the underlying mechanism is not specified.

---

## 6. Open questions

1. **What is the Solana program ID for Stork?** Referenced in `Stork-Oracle/Documentation/resources/contract-addresses/solana.md` but not surfaced in our probe wave. **Why it matters:** without the program ID, we can't fetch the IDL, decode `Temporal Numeric Value Feed PDA` accounts, or even determine whether Stork is consumed by any Solana program for xStock-class assets. **Gating:** docs probe at the contract-addresses page or `cargo doc --open` against `stork-solana-sdk`.
2. **Does Stork publish any xStock or US-equity feeds on Solana?** Referenced via the Asset ID Registry but not surfaced in our probe wave. **Why it matters:** if no equity feeds, Stork is structurally absent from the soothsayer-target asset class. **Gating:** Asset ID Registry probe.
3. **What is the actual Stork aggregation rule?** "Trusted publishers" + "continuously aggregates" is the docs depth. **Why it matters:** without a concrete rule, the methodology-disclosure asymmetry framing is structural rather than empirical. **Gating:** Stork team outreach or `stork-external` GitHub repo source review.
4. **Whether any major Solana lending or perp market consumes Stork for any asset class.** Survey gap: we observed Kamino (Scope), MarginFi (Switchboard/Pyth/Fixed), Drift (Pyth), Save/Loopscale/Jupiter Lend (likely Pyth) — none cite Stork. **Why it matters:** if zero, Stork is rhetorically interesting but not empirically a comparator we need to spend tape on. **Gating:** ecosystem survey across additional lending markets + perp venues.
5. **Is Stork a Pull or Push pattern on Solana?** "Sub-second latency, pull as often as needed" suggests Pull, but the docs page does not specify. **Why it matters:** if Pull, the same caller-initiated-crank staleness gotcha that affects Switchboard ([`oracles/switchboard_ondemand.md`](switchboard_ondemand.md) §1.2) likely applies. **Gating:** Solana docs page deep read or SDK source review.
6. **Stork's confidence-interval treatment.** Does the `Temporal Numeric Value Feed PDA` carry a CI / dispersion / band field, or only a point estimate? The docs page is silent. **Why it matters:** if Stork carries a CI, it's a third soothsayer comparator alongside Pyth's `pyth_conf` and a hypothetical Chainlink v11 bid-ask spread; if not, it joins RedStone as a no-band oracle. **Gating:** SDK source review or program-account probe.
7. **What does "parsing market hours and bid/ask data for inclusion in price reports" actually mean?** Is the bid/ask carried in the published value, or processed off-chain into a single value? **Gating:** case-study deep read or Stork team outreach.

---

## 7. Citations

- [`stork-docs-landing`] Stork. *Welcome to Stork*. https://docs.stork.network/. Accessed: 2026-04-29.
- [`stork-solana-docs`] Stork. *Solana Contract APIs*. https://github.com/Stork-Oracle/Documentation/blob/main/api-reference/contract-apis/solana.md. Accessed: 2026-04-29.
- [`stork-rwa-case-study`] Stork. *Long or Short Anything with Stork's Custom Oracle Solution* (Ostium RWA case study). https://www.stork.network/case-studies/ostium-rwa-custom-oracle. Cited via 2026-04-29 search results.
- [`stork-rwa-blog`] Stork. *The Key to 'RWAfi': How RWA Oracles Integrate Real-World Assets and DeFi Lending*. https://www.stork.network/blog/rwafi-rwa-defi-oracle. Cited via 2026-04-29 search results.
- [`pyth-regular-companion`] Soothsayer internal. [`docs/sources/oracles/pyth_regular.md`](pyth_regular.md). The contrasting case where methodology is published precisely.
- [`marginfi-companion`] Soothsayer internal. [`docs/sources/lending/marginfi.md`](../lending/marginfi.md). Confirms Stork is not a marginfi-v2 oracle source.
- [`scope-companion`] Soothsayer internal. [`docs/sources/oracles/scope.md`](scope.md). Confirms Kamino uses Scope, not Stork.
