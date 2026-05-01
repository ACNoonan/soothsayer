# `Chainlink Data Streams v11` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.chain.link/data-streams` (accessed 2026-04-29; specific RWA-payload sub-page returned 404 on 2026-04-29 — link rot noted, working off the SDK source pinned in §7 instead), `smartcontractkit/data-streams-sdk/rust/crates/report/src/report/v11.rs` via `src/soothsayer/chainlink/v11.py:11`, the empirical scan in [`reports/v11_cadence_verification.md`](../../../reports/v11_cadence_verification.md).
**Version pin:** `v11` (schema id `0x000b`, 14-field 448-byte ABI-encoded payload; first observed in soothsayer's tape Jan 2026; supersedes `v10` for 24/5 US equity streams). The active `v11` field set is `(feed_id, valid_from_timestamp, observations_timestamp, native_fee, link_fee, expires_at, mid, last_seen_timestamp_ns, bid, bid_volume, ask, ask_volume, last_traded_price, market_status)`.
**Role in soothsayer stack:** `comparator` — Paper 1's load-bearing 24/5 incumbent archetype. We do **not** use Chainlink as a soothsayer fair-value input (would be circular for closed-market xStocks; see CLAUDE.md hard rule on tokenized-stock secondary-market prices).
**Schema in scryer:** `dataset/soothsayer_v5/tape/v1/year=YYYY/month=MM/day=DD.parquet` (joined tape; the Chainlink v11 columns `cl_mid`, `cl_bid`, `cl_ask`, `cl_market_status` come from the on-chain Verifier reconstruction, not from a separate `chainlink/...` venue under scryer). The pre-cutover scraper in `crates/soothsayer-ingest/src/chainlink/v11.rs` was deleted in the April 2026 cutover; decoding now happens scryer-side, the Python decoder at `src/soothsayer/chainlink/v11.py` is retained for ad-hoc analysis.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

Chainlink Data Streams v11 is the schema for "24/5 US equity" reports — aimed at tokenized-stock RWA consumers. Each report is a DON-consensus benchmark price plus a top-of-book bid/ask snapshot at the moment of consensus, signed by Chainlink's report-server quorum and verified on-chain via the Verifier program.

Per the SDK source (`smartcontractkit/data-streams-sdk/rust/crates/report/src/report/v11.rs`, pinned via `src/soothsayer/chainlink/v11.py:11`), each v11 report carries:

- `mid` (i192, 18-decimal fixed point) — DON-consensus benchmark price.
- `bid`, `ask` (i192) — top-of-book quotes from the data-source layer at consensus time.
- `bid_volume`, `ask_volume` (i192) — quoted size at the top of book.
- `last_traded_price` (i192) — last on-venue trade price reported to the DON.
- `last_seen_timestamp_ns` (u64) — wall-clock nanoseconds for the data the DON saw.
- `market_status` (u32) — enum 0–5 indicating the venue's session state.

Public docs do **not** publish the underlying source-venue list, the weighting scheme, or the consensus algorithm. The `mid` is described as a benchmark; the formal aggregation rule is not specified at the `data-streams` page granularity.

### 1.2 Cadence / publication schedule

Reports are pushed continuously while the data-source layer is producing observations. The `market_status` enum encodes the underlying venue's session:

| Code | Label (per SDK source) | Soothsayer interpretation |
|---:|---|---|
| 0 | `Unknown` | DON has no session-state signal for this feed |
| 1 | `Pre-market` | US equity pre-market (04:00–09:30 ET) |
| 2 | `Regular` | US equity regular session (09:30–16:00 ET) |
| 3 | `Post-market` | US equity after-hours (16:00–20:00 ET) |
| 4 | `Overnight` | Mon–Fri 20:00 ET → 04:00 ET next day |
| 5 | `Closed` (covers weekends) | Mon-close → next pre-market open |

Critically, **public docs do not state what `bid` / `ask` / `mid` are guaranteed to carry during status ≠ 2**. The framing of "24/5 equity" implies real values during sessions 1, 2, 3, 4; status 5 (weekend) is documented as "closed" but the schema still publishes a price. Whether that price is real or placeholder-derived is the empirical question §3 below answers.

### 1.3 Fallback / degraded behavior

Public docs surface two fallback signals on the wire:

- `expires_at` — report invalidates after this timestamp; downstream consumers (Verifier-CPI integrators, Streams-relay programs) check this and skip the report.
- `last_seen_timestamp_ns` vs. `observations_timestamp` skew — a large gap indicates the DON is republishing without fresh source data.

Chainlink's published 24/5 US-equity guidance separately recommends consumers extend weekend pricing using prices of tokenized stocks on secondary CEX/DEX venues (cited in [`docs/data-sources.md`](../../data-sources.md#chainlink-data-streams) as the cleanest demonstration that the industry still lacks a non-circular closed-market policy primitive). v11 itself does not implement that fallback at the wire layer — it is a recommendation for the consumer.

### 1.4 Schema / wire format

448-byte ABI-encoded payload, 14 × 32-byte words, field order pinned in `src/soothsayer/chainlink/v11.py:13-31`. Integer fields are big-endian and right-aligned; `i192` fields are sign-extended across the full 32-byte word (so signed 256-bit interpretation is correct, see `_read_int` at `src/soothsayer/chainlink/v11.py:108`). Schema id is `0x000b` in the leading bytes of the report envelope.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** `dataset/soothsayer_v5/tape/v1/...` — Chainlink v11 columns are joined into the v5 tape rather than emitted as a standalone `chainlink/...` venue. Continuous capture since 2026-04-24 (`docs/v5-tape.md`).
- **On-chain reconstruction:** Verifier program signatures + decoded transactions; ad-hoc decoding via `src/soothsayer/chainlink/v11.py:114` `decode(report: bytes) -> V11Report`. Plausibility check at `src/soothsayer/chainlink/v11.py:136` `plausible_v11_prefix` (used to locate the report offset inside instruction data).
- **Coverage in current tape:** weekend `market_status=5` samples confirmed for SPYx (n=6), QQQx (n=6), TSLAx (n=7), NVDAx (n=1) per the 2026-04-26 scan in [`reports/v11_cadence_verification.md`](../../../reports/v11_cadence_verification.md). Sessions 0–4 (pre-mkt / regular / post-mkt / overnight / unknown) had no samples in the 2026-04-26 Sunday-afternoon scan window — the script is idempotent and accumulates samples through the trading week.
- **Symbol mapping:** `XSTOCK_V11_FEEDS` registry maps `feed_id` → xStock symbol. Reports with `feed_id` outside the registry classify as `(unmapped)` in the cadence scan.

---

## 3. Reconciliation: stated vs. observed

The empirical centerpiece is the [`reports/v11_cadence_verification.md`](../../../reports/v11_cadence_verification.md) synthetic-marker classifier (v2, 2026-04-26). It decoded 26 v11 reports across 4 mapped xStocks at `market_status=5` and labelled each into a 6-class taxonomy distinguishing real quotes from placeholder bookends.

| Stated claim | Observation | Verdict |
|---|---|---|
| v11 publishes a price during `market_status=5` (weekend). | Confirmed: every weekend report in the scan carries non-null `mid`, `bid`, `ask`, `last_traded_price`. | **confirmed** |
| The published weekend price is a real DON-consensus benchmark. | **Contradicted for SPYx, QQQx, TSLAx**; the bid component of the wire schema carries the synthetic marker `.01` suffix in 100% of weekend samples (SPYx 21.01, QQQx 656.01, TSLAx 372.01). PURE_PLACEHOLDER pattern (both bid and ask `.01`-marked) on SPYx; BID_SYNTHETIC pattern on QQQx and TSLAx. Real-market bids land on `.01` randomly ~1-in-100; a 100% incidence is a strong synthetic signal. | **contradicted** |
| Same as above, NVDAx. | NVDAx weekend sample (n=1) classified REAL — bid 208.07, ask 208.14, spread 3.4 bps. Single-sample evidence; needs replication before generalising. | **mixed** |
| Cadence outside regular hours (sessions 1, 3, 4) carries real values. | **Unmeasurable from current tape** — Sunday-afternoon scan window saw zero samples for sessions 1/3/4. The classifier script is idempotent; re-runs through the trading week will fill the matrix. | **unmeasurable** |
| `mid` and `last_traded_price` are independent fields. | Confirmed: the SPYx weekend sample shows `mid = 368.0100`, `last_traded_price = 713.96`. The "mid" in PURE_PLACEHOLDER is the bookend midpoint of the synthetic 21.01/715.01 bid/ask, not a market mid. `last_traded_price` 713.96 is plausibly the real Friday close. | **confirmed (with caveat)** |
| Spread (`(ask - bid) / mid`) is a usable signal. | **Misleading on weekends.** The PURE_PLACEHOLDER pattern produces an 18,858-bps spread for SPYx (21.01 → 715.01); the BID_SYNTHETIC pattern produces 117–329 bps for QQQx/TSLAx. Spread alone classifies weekend reports as "wide" but masks the synthetic-low mechanism. The v1 spread-only classifier missed BID_SYNTHETIC when spread happened to fall under 200 bps; v2 catches it via the `.01`-suffix check. | **contradicted, requires marker-aware classifier** |

The 2026-02-06–2026-04-17 panel in [`reports/v1b_chainlink_comparison.md`](../../../reports/v1b_chainlink_comparison.md) (87 weekend observations) shows v11 publishes a `tokenizedPrice` during weekend windows but **does not publish a coverage band** — the wire `bid`/`ask` are the closest thing, and they're synthetic per the cadence scan. This is the empirical anchor for Paper 1 §1's "no incumbent publishes a verifiable calibration claim" framing.

[`reports/v1_chainlink_bias.md`](../../../reports/v1_chainlink_bias.md) measures the v11 weekend point-estimate bias as pooled −8.77 bps (undetectable at panel size) — the synthetic-bid / real-mid combination produces a usable point estimate, just not a usable interval.

---

## 4. Market action / consumer impact

Chainlink v11 is **not consumed directly by Kamino's xStocks reserves** — those use Scope as primary oracle, which sources Chainlink v10 (legacy schema) for some feeds and other inputs for xStocks specifically (see [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md) §1, where Kamino's `PriceHeuristic` ranges are recorded but the underlying oracle path is Scope, not v11). So the synthetic-bid finding does **not** directly flip a Kamino price-validity check.

Where v11 *does* matter as a downstream signal:

- **Drift Protocol (perps)** — Drift integrates Chainlink price feeds for some markets per their public oracle stack. Whether xStock perps on Drift consume v11 specifically is a §6 open question; if they do, the synthetic-bid bookend would propagate into their mark-vs-oracle deviation logic. **TODO when scryer adds drift_perp_oracle_tape.v1 (not yet in `scryer/wishlist.md`).**
- **MarginFi** — public docs do not surface oracle-source granularity sufficient to confirm whether v11 feeds any MarginFi reserve. **TODO when MarginFi reserve-config snapshot lands** (see [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §6).
- **Paper 1 §1.1 / §2.1 framing** — the synthetic-marker finding directly supports Paper 1's "incumbent 24/5 archetype publishes placeholder values during closed-market windows" claim. Without v11_cadence_verification.md the §1.1 framing was a hypothesis; with it, the framing is a confirmed empirical result for SPYx/QQQx/TSLAx.
- **Public dashboard (Phase 2)** — v11 is the natural archetype to show next to soothsayer's served band on the comparator dashboard. The `.01`-suffix marker is an audience-readable demonstration of why "24/5 coverage" claims need empirical interrogation.

---

## 5. Known confusions / version pitfalls

- **v10 vs v11.** v10 is a legacy RWA schema with different field set and behavior; v11 is the active 24/5 schema (since Jan 2026). The Verifier program contains decoders for both; cross-referencing Reddit / Discord posts about "Chainlink RWA tokenizedPrice" without checking schema id is the source of past confusion. Schema id `0x000b` = v11; `0x000a` = v10.
- **`market_status=5` ≠ "no value published."** The schema still emits a price + bid/ask during closed/weekend windows. The empirical question is whether those values are real or placeholder; per §3, for SPYx/QQQx/TSLAx the bid is synthetic.
- **`mid` ≠ `(bid + ask) / 2` on weekends.** During PURE_PLACEHOLDER, the `mid` field equals the arithmetic midpoint of the synthetic bookends (368.01 for SPYx 21.01/715.01), not a market mid. During BID_SYNTHETIC, `mid` is closer to `ask` than to `bid`. Code that derives a "mid" from `bid`/`ask` instead of reading the `mid` field will silently disagree.
- **`last_traded_price` is the most recoverable signal during status=5.** It's the field least corrupted by the synthetic-marker pattern (it tracks the real prior-session close, e.g. SPYx 713.96 on the 2026-04-26 sample). Soothsayer's stale-hold Gaussian baseline implicitly already uses this; downstream consumers reading "the chainlink mid" should consider switching to `last_traded_price` during `market_status ∈ {4, 5}` until Chainlink documents the v11 weekend semantics.
- **`expires_at` semantics.** The field is a u32 unix-seconds timestamp, not a relative TTL; consumers checking expiry must compare against the current slot's wall-clock, not against `observations_timestamp + offset`.
- **Stream availability ≠ verifier acceptance.** A v11 report can be valid on the wire (passes our decoder + plausibility check) but fail downstream Verifier CPI checks if the consumer's allowlist or fee-token configuration rejects it. This is operational, not schema-level, but is a frequent source of "the price isn't updating" support traffic.
- **`tokenizedPrice` colloquially refers to v11 `mid`** in marketing material but is also Chainlink's name for a separate Aggregator-style on-chain feed in legacy v10 deployments. Do not assume the same value.

---

## 6. Open questions

1. **Pre-market / regular / post-market / overnight cadence verification.** [`reports/v11_cadence_verification.md`](../../../reports/v11_cadence_verification.md) §"Outstanding" lists sessions 1/2/3/4 as needing samples. Re-running `scripts/verify_v11_cadence.py` through the trading week 2026-04-29 → 2026-05-03 should fill the matrix. **Why it matters:** if sessions 1/3/4 are also synthetic, Paper 1 §2's "24/5 archetype" framing strengthens beyond weekends. **Gating:** scheduled re-run; idempotent.
2. **Why does NVDAx (n=1) classify REAL on the weekend?** Possible explanations: (a) NVDAx feed wiring uses a different DON config than SPYx/QQQx/TSLAx, (b) the single sample is a transition artefact (a lingering Friday-close print misclassified as `market_status=5`), (c) the synthetic-marker pattern is per-feed, not universal. **Why it matters:** if (a), it suggests Chainlink has a real 24/7 path for some xStocks but not others; that's a sharper finding than "all weekend prints are synthetic." **Gating:** more samples + outreach to Chainlink Labs.
3. **Coverage of the 4 unmapped xStocks (GOOGLx, AAPLx, MSTRx, HOODx).** `XSTOCK_V11_FEEDS` registry pins the 4 we've mapped; the others may have v11 streams not yet identified. **Gating:** feed-id discovery via Verifier program logs.
4. **What is the `mid` field actually computed as during PURE_PLACEHOLDER?** Empirically `mid = (bid + ask) / 2` on the SPYx sample; whether that's the documented behavior or coincidence is unclear. **Gating:** Chainlink Labs outreach or SDK source review of the v11 reporter logic (not currently pinned in our repo).
5. **Does v11 deprecate v10 for all 24/5 consumers, or only new integrations?** Some on-chain consumers may still read v10. **Gating:** Verifier program log audit + adjacent ecosystem queries.

---

## 7. Citations

- [`chainlink-streams-v11`] Chainlink Labs. 2026. *Data Streams v11 RWA report schema*. Source-of-truth: `smartcontractkit/data-streams-sdk/rust/crates/report/src/report/v11.rs` (commit pinned via mirror in `src/soothsayer/chainlink/v11.py:11`). Companion docs at https://docs.chain.link/data-streams (top-level overview accessed 2026-04-29; deep RWA-payload sub-page returned 404 — link rot noted).
- [`chainlink-24-5`] Chainlink Labs. 2025. *24/5 US equities feeds: weekend coverage guidance*. Cited via [`docs/data-sources.md`](../../data-sources.md#chainlink-data-streams). Verification status: TODO at the references-catalog level; the operational guidance ("extend weekend pricing using tokenized stocks on secondary venues") is the relevant content for §1.3.
- [`v11-cadence-verification`] Soothsayer internal. 2026-04-26. [`reports/v11_cadence_verification.md`](../../../reports/v11_cadence_verification.md). The `.01`-suffix synthetic-marker classifier and the per-(symbol, status) verdict table.
- [`v11.py-decoder`] Soothsayer internal. [`src/soothsayer/chainlink/v11.py`](../../../src/soothsayer/chainlink/v11.py). Python decoder, `MARKET_STATUS` enum, `plausible_v11_prefix` heuristic.
- [`v1b-chainlink-comparison`] Soothsayer internal. [`reports/v1b_chainlink_comparison.md`](../../../reports/v1b_chainlink_comparison.md). 87-observation weekend panel showing v11 publishes price but not band.
- [`v1-chainlink-bias`] Soothsayer internal. [`reports/v1_chainlink_bias.md`](../../../reports/v1_chainlink_bias.md). Pooled −8.77 bps weekend bias measurement.
