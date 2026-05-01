# `Chainlink Data Streams` — transport layer (Verifier program, fee structure, expiresAt) — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.chain.link/data-streams` (accessed 2026-04-29; top-level overview present, deep pages on the verify-and-fee-mgr instructions returned 404 in the same probe wave that flagged v10/v11 link rot — see [`oracles/chainlink_v11.md`](chainlink_v11.md) §7), `src/soothsayer/chainlink/verifier.py:1-146` (the two-path parser, including the SDK-derived snappy + ABI envelope layout), `crates/soothsayer-publisher/` Verifier-CPI integration scaffolding, `scryer/wishlist.md` items 42 (on-chain relay program scaffold) and 43 (relay daemon mirror tape).
**Version pin:** Verifier program **`Gt9S41PtjR58CbG9JhJ3J6vxesqrNAswbWYbLNTMZA3c`** (Solana mainnet). The Verifier itself is schema-agnostic — it accepts any signed report (v3 / v7 / v8 / v10 / v11) per the schema-id table at `src/soothsayer/chainlink/verifier.py:33-40`. This file documents the **transport layer**: the Verifier program, the snappy-compressed envelope, the report-context signature framing, fee accounting, and `expires_at` semantics. Schema-specific reconciliation (e.g., v10 `tokenized_price` semantics, v11 weekend bid/ask) lives in the per-schema files [`oracles/chainlink_v10.md`](chainlink_v10.md) and [`oracles/chainlink_v11.md`](chainlink_v11.md).
**Role in soothsayer stack:** `transport-layer reference` — soothsayer's own Streams-relay program (queued at scryer wishlist item 42, design locked in `reports/methodology_history.md` 2026-04-29 (afternoon)) is the soothsayer-side mirror of this transport. Understanding the Verifier's instruction shape, fee model, and CPI surface is a prerequisite for the relay design.
**Schema in scryer:** `dataset/chainlink_data_streams/v1/...` — the continuous report tape (scryer phase 60, shipped 2026-04-29) decodes the report **content**; the **transport** (instruction discriminator, snappy envelope, report-context signature blob, fee accounting) is captured in the same rows where applicable. The transport layer per se has no separate dataset; it's the wire format underneath every per-schema row.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule (transport-layer responsibilities)

The Data Streams transport layer is not a price aggregator — that's the schema's job. Its responsibilities are narrower:

1. **Signature verification.** The Verifier program verifies the DON-quorum signature attached to each `signed_report` envelope. Until verification succeeds, downstream consumers (CPI integrators, on-chain relay programs) treat the inner `report_data` as untrusted bytes.
2. **Fee accounting.** Each verified report charges either `native_fee` (SOL) or `link_fee` (LINK) to the verifying caller. Both fees are encoded as `u192`-scaled fields inside the per-schema report and are exposed by the Verifier's verify instruction so the fee manager can collect.
3. **Return-data forwarding.** On success the verify instruction calls `set_return_data(&report_data)` so the caller (or its outer CPI parent) can read the bare report bytes from `meta.returnData` without needing to parse the full envelope. This is the "easy path" used by `parse_verify_return_data` at `src/soothsayer/chainlink/verifier.py:66-100`.

The full envelope, decompressed, is a Solidity-ABI-encoded `SignedReport` tuple:

```
w0..w2    report_context        3 × bytes32 (inlined)
w3        offset to report_data dynamic-bytes pointer
...       signatures            DON-quorum signatures follow
@offset:  report_len            u256 length word
@offset+32: report_data         versioned report bytes (288 v3, 416 v10, 448 v11, ...)
```

The first two bytes of `feed_id` (which lives at `report_data[0..32]`) are the schema id: `0x0003` = v3 (crypto/forex), `0x0007` = v7 (DEX/LP), `0x0008` = v8 (stables extension), `0x000a` = v10 (tokenized asset / xStocks), `0x000b` = v11 (RWA Advanced / 24/5 equity). Reference: `src/soothsayer/chainlink/verifier.py:33-40`.

### 1.2 Cadence / publication schedule

The transport itself has no cadence — that's per-schema. What the Verifier does have is a per-call gas/compute-units cost (`verify` is a non-trivial CPI, especially on v11 with 14 fields + signature batch). Operationally, fast-path consumers minimise verify-CPI calls by reading the `meta.returnData` of the latest verifier touch (the same primitive `parse_verify_return_data` exposes) rather than re-verifying — this is the soothsayer-streams-relay-program design (`scryer/wishlist.md` item 42): the relay daemon CPIs the Verifier once on each fresh report and persists the verified bytes to a soothsayer-owned PDA, so downstream consumers read the PDA rather than re-paying the verify cost.

### 1.3 Fallback / degraded behavior

- **`expires_at` (u32 unix seconds)** — present on every schema (`v10.py:64`, `v11.py:60`). After this timestamp, the Verifier still verifies the signature but downstream consumers must reject the report on staleness. **This is a u32 unix-seconds wall-clock timestamp, not a relative TTL.** Code that compares `expires_at` against `observations_timestamp + offset` is wrong; it must compare against the current slot's wall-clock.
- **Verify-CPI failure path** — if the signature does not verify (e.g., DON quorum below threshold, malformed envelope), the verify instruction fails atomically; the caller's transaction reverts. There is no partial-success path.
- **Fee-token mismatch** — if the caller pays in the wrong token (e.g., LINK when the feed is `native_fee`-only), the Verifier rejects. Operationally, this is the most common silent integration failure ("the price isn't updating") and is a known Chainlink support-traffic class.

### 1.4 Schema / wire format

The transport envelope is documented in `src/soothsayer/chainlink/verifier.py:30-45`:

```
Instruction-data framing (raw, base58-encoded):
  [0..8]     Anchor instruction discriminator (8 bytes)
  [8..12]    u32 little-endian length of signed_report
  [12..]     signed_report (snappy-compressed)

After snappy.decompress(...), the SignedReport ABI tuple:
  w0..w2    report_context (3 × bytes32, inlined)
  w3        offset to report_data
  ...       DON-quorum signatures
  @offset:  u256 length word + report_data bytes
```

The `report_context` is a 96-byte signed payload (3 × 32-byte words) — typically `(config_digest, epoch, round)` per OCR2 conventions. It is exposed via `ParsedVerify.report_context` in the hard-path parser (`parse_verify` at `src/soothsayer/chainlink/verifier.py:119`) and is `None` in the easy-path return-data parser (where only the bare report bytes survive).

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** `dataset/chainlink_data_streams/v1/...` (scryer phase 60, shipped 2026-04-29 per `scryer/wishlist.md` line 50). The continuous report tape decodes the **report content**; transport-layer fields like `expires_at`, the schema id, and the verify-instruction discriminator land in the same rows. The exact column list is `chainlink_data_streams.v1::Report` per scryer's `docs/schemas.md`.
- **On-chain Verifier program:** `Gt9S41PtjR58CbG9JhJ3J6vxesqrNAswbWYbLNTMZA3c`. Direct probe path: any tx that touches this program is a verify call; `meta.returnData` is the bare report bytes (when the outer program forwards) or a `set_return_data(&report_data)` payload (when the verify caller is the direct receiver).
- **Two parser paths:** `src/soothsayer/chainlink/verifier.py:66` `parse_verify_return_data` (easy path: read `meta.returnData`, base64-decode, schema = first 2 bytes); `src/soothsayer/chainlink/verifier.py:119` `parse_verify` (hard path: snappy-decompress the instruction data, walk the ABI offset to the report bytes). Most analysis uses the easy path.
- **Pre-cutover fetcher:** `crates/soothsayer-ingest/src/chainlink/v11.rs` (deleted in the April 2026 cutover). The Rust ingest path lived here; transport-layer parsing is now in scryer per phase 60.
- **Soothsayer-streams-relay-program (planned):** `programs/soothsayer-streams-relay-program/` per `scryer/wishlist.md` item 42 (scaffold + Verifier CPI). When live, this program's `post_relay_update` instruction is the soothsayer-side consumer surface for verified Chainlink reports — i.e., other Solana consumers will read soothsayer's PDA (`[b"streams_relay", feed_id]`) rather than re-paying the Verifier's verify cost. **Methodology entry:** `reports/methodology_history.md` 2026-04-29 (afternoon).

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| The verify instruction calls `set_return_data(&report_data)` so consumers can read the bare report from `meta.returnData`. | Confirmed — `parse_verify_return_data` is the production path used in soothsayer's analysis tooling and works against live mainnet txs. The easy-path parser at `src/soothsayer/chainlink/verifier.py:66-100` is a one-base64-decode-away utility because the claim holds. | **confirmed** |
| `meta.returnData.programId` corresponds to the Verifier program. | **Contradicted in CPI-from-outer-program scenarios.** When Kamino's Scope (`HFn8GnPADiny6XqUoWE8uRPPxb29ikn4yTuPa9MF2fWJ`) CPIs the Verifier and itself calls `set_return_data` to forward the bytes upward, the transaction-level `meta.returnData.programId` is **Scope**, not the Verifier. The payload is byte-identical, so soothsayer's parser does not filter on `programId` (`src/soothsayer/chainlink/verifier.py:74-78`). | **contradicted (in the load-bearing CPI case)** |
| `expires_at` is a u32 unix-seconds wall-clock timestamp. | Confirmed structurally — `v10.py:64` and `v11.py:60` both decode it as u32, and the historical-note in v11's docs explicitly flags the trap of treating it as a relative TTL. | **confirmed** |
| The instruction-data framing is `[disc:8][len:u32-le][snappy(signed_report)]`. | Confirmed — the hard-path parser `_decompress_ix_data` at `src/soothsayer/chainlink/verifier.py:103-112` is a production utility against live verify-instruction data. | **confirmed** |
| Fees are charged in either SOL (`native_fee`) or LINK (`link_fee`). | Confirmed structurally — both fields are present and decoded in v10 (`v10.py:67-68`) and v11 (`v11.py:60-61`). Whether a given feed is `native_fee`-only, `link_fee`-only, or dual-payable is operational and not surfaced in the schema; consumers learn it by attempting payment and observing the rejection. | **partial (mechanism present, per-feed fee-token policy not exposed)** |
| The Verifier program is **schema-agnostic** — same program serves v3, v7, v8, v10, v11. | Confirmed — the program ID is constant and the schema-id discrimination happens **inside** the report payload (first 2 bytes of `feed_id`). The same Verifier-touching tx can be either a v10 or a v11 report depending on which feed was queried. | **confirmed** |
| Snappy decompression on the signed-report payload is required. | Confirmed — without `snappy.decompress`, the inner ABI envelope is unreadable; the hard-path parser's first step is decompression. The `snappy` Python package is a runtime dependency (see `pyproject.toml`). | **confirmed** |
| `report_context` is exposed by the verify instruction. | Confirmed in the hard path (`parse_verify` returns `report_context` as 96 bytes). **`None` in the easy path** — when reading `meta.returnData`, the outer envelope has already been stripped and only the bare report survives. Code that needs `report_context` must use the hard path. | **partial (path-dependent)** |

---

## 4. Market action / consumer impact

The transport layer is the bottleneck for any consumer that wants verified Chainlink Data Streams pricing on Solana:

- **Kamino klend (via Scope)** — Scope CPIs the Verifier and forwards the bytes via `set_return_data`. The `programId`-confusion item in §3 is the load-bearing observation: any naive parser that filters by Verifier programId will miss the Scope-mediated path entirely. Soothsayer's parser explicitly sidesteps this by validating on (schema, feed_id) instead.
- **MarginFi** — public docs do not list Chainlink Data Streams as a supported oracle source for marginfi-v2 (per [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §1.1: Switchboard / Pyth / Fixed only as of 2026-04-29). The transport layer is not a live MarginFi consumer surface today.
- **Drift Protocol** — Drift integrates Chainlink price feeds for some markets per their public oracle stack. Whether xStock-class markets on Drift use Data Streams (verified-CPI path) vs. legacy pull (Functions/Aggregator) is a §6 open question.
- **Soothsayer-streams-relay-program (planned)** — soothsayer's own consumer surface. The relay daemon CPIs the Verifier once on each fresh signed report (~60s cadence per feed per `scryer/wishlist.md` item 43), persists the verified bytes to `[b"streams_relay", feed_id]`-seeded PDAs, and downstream Solana consumers read the PDA. This converts the Chainlink transport from a per-call-CPI cost into a one-write-per-update-and-many-reads model. **Live-bearing for Paper 1 §1's Option-C deployment plan.**
- **Paper 1 §1 framing (transport-side)** — the Verifier program is the gating primitive between "Chainlink publishes a price" and "a Solana consumer trusts it." The transport layer is not where the synthetic-bid finding lives (that's the v11 schema layer); but **all reasoning about whether a given xStock consumer "uses Chainlink" must specify whether it CPIs the Verifier directly, reads via Scope, or reads a relay PDA.** This file's existence is the operational realisation of that distinction.
- **Public dashboard (Phase 2)** — the transport-layer view ("how many Solana programs touched the Verifier in the last 24h, segmented by schema") is the natural ecosystem-health row. Not a price comparator, but a load-bearing measurement of who's actually consuming.

---

## 5. Known confusions / version pitfalls

- **The Verifier program is schema-agnostic.** A "Chainlink integration" claim is incomplete without specifying the schema (v10 / v11 / other). The Verifier program ID does not tell you which schema was verified — that's inside the report bytes.
- **`meta.returnData.programId` is the **outer** program, not the Verifier, in CPI-mediated paths.** Filtering tx logs by Verifier programId works for direct-CPI consumers but silently loses the Scope-mediated Kamino path. Validate by (schema, feed_id) instead.
- **Snappy compression is on the wire — required to parse.** The instruction data is not human-readable until decompressed.
- **`expires_at` is wall-clock unix seconds, not a TTL.** Stale-reject must compare against the current slot's wall-clock, not against `observations_timestamp + offset`.
- **`set_return_data` is a single-slot transient.** `meta.returnData` reflects the *most recent* CPI in the tx. If two Verifier CPIs happen in the same tx (rare), only the second's bytes survive. Production consumers serialise verify calls.
- **Fee-token mismatch silently rejects.** Per-feed fee-token policy is operational, not in the schema; "the price isn't updating" support traffic is most often a `native_fee`-vs-`link_fee` configuration error.
- **`signed_report` length prefix is little-endian u32, not big-endian.** Easy mistake when transitioning from the report-content (big-endian ABI) to the outer envelope.
- **The hard-path parser handles report-context; the easy-path does not.** Code that needs OCR2 epoch/round must use the hard path.

---

## 6. Open questions

1. **Per-feed fee-token policy.** Which xStock feeds are `native_fee`-only vs `link_fee`-only vs dual? **Why it matters:** the soothsayer-streams-relay-program needs a fee-token configuration per feed at deploy time (`scryer/wishlist.md` item 42, methodology entry in `reports/methodology_history.md` 2026-04-29). **Gating:** Chainlink Labs outreach + per-feed test-verify probe (verify with each token, observe rejection).
2. **Verify-CPI compute-unit cost** by schema. v11 with 14 fields + DON-quorum signatures is plausibly more expensive than v10 with 13 fields. **Why it matters:** the relay daemon's per-update tx-fee budget is gated on this. **Gating:** simulated `verify` against representative reports for each schema, measured against the soothsayer-streams-relay-program testbench (Phase 42a).
3. **DON-quorum threshold.** How many signatures must verify for the Verifier to accept the report? Documented in OCR2 conventions but not surfaced in the per-feed config we can read on-chain. **Gating:** SDK source review + Chainlink Labs outreach.
4. **`report_context` content meaning per schema.** OCR2 convention is `(config_digest, epoch, round)`, but Data Streams may overload these fields. **Why it matters:** if `epoch` indicates DON-config rotation, an external monitor could detect operator-set changes (a Sybil-resistance check). **Gating:** hard-path parser instrumentation against a multi-week tape window.
5. **Whether the same Verifier program serves all 5 schema ids in production today.** v3/v7/v8 are crypto/forex/DEX/stables — likely not actively rotating into our xStock-focused tape, but the schema-id table at `verifier.py:33-40` claims they are accepted. **Gating:** per-schema observation count over a representative tape window.
6. **Forward compatibility — what happens when Chainlink ships v12?** Does the same Verifier accept it, or does a new program ID launch alongside? **Gating:** Chainlink Labs roadmap query; the soothsayer-streams-relay-program design must accommodate either path.

---

## 7. Citations

- [`chainlink-data-streams-overview`] Chainlink Labs. *Data Streams (overview)*. https://docs.chain.link/data-streams. Accessed: 2026-04-29 (top-level overview present; deep verify-instruction and fee-mgr pages not surfaced as stable URLs in the same probe wave that flagged v10/v11 link rot).
- [`verifier.py`] Soothsayer internal. [`src/soothsayer/chainlink/verifier.py`](../../../src/soothsayer/chainlink/verifier.py). The two-path parser, the SDK-derived envelope layout, the schema-id table at lines 33-40, the production easy-path parser at lines 66-100.
- [`v10-companion`] Soothsayer internal. [`docs/sources/oracles/chainlink_v10.md`](chainlink_v10.md). Schema layer for v10 (`tokenized_price` semantics, market_status enum, V1 weekend-bias measurement).
- [`v11-companion`] Soothsayer internal. [`docs/sources/oracles/chainlink_v11.md`](chainlink_v11.md). Schema layer for v11 (mid/bid/ask, the synthetic-bid weekend finding).
- [`scryer-wishlist-relay`] Scryer internal. [`scryer/wishlist.md`](../../../../scryer/wishlist.md) items 42 (program scaffold) and 43 (relay daemon mirror tape). The forward-running soothsayer-side mirror of the Chainlink Data Streams transport.
- [`scryer-phase60`] Scryer internal. `chainlink_data_streams.v1` continuous report tape, shipped 2026-04-29. Phase row in scryer's `docs/phase_log.md` v0.1-phase-60.
- [`methodology-history-relay`] Soothsayer internal. [`reports/methodology_history.md`](../../../reports/methodology_history.md) 2026-04-29 (afternoon) — the soothsayer-streams-relay-program design lock.
