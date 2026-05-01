# `Chainlink Data Streams v10` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.chain.link/data-streams` (top-level overview accessed 2026-04-29; the specific v10 "Tokenized Asset" sub-page was not surfaced as a stable URL — Chainlink has refactored Data Streams docs around v11 since Q4 2025), `src/soothsayer/chainlink/v10.py` (the canonical decoder, including the field-layout docstring at lines 11-30), `src/soothsayer/chainlink/feeds.py:31-41` (the verified-by-correlation `XSTOCK_FEEDS` registry), the V1 weekend-bias panel in [`reports/v1b_chainlink_comparison.md`](../../../reports/v1b_chainlink_comparison.md).
**Version pin:** `v10` (schema id `0x000a`, 13-field 416-byte ABI-encoded payload; the original Chainlink "Tokenized Asset" schema active for xStock feeds since the Solana mainnet launch through 2025-Q4, when v11 was rolled out alongside it; v10 remains observable on-chain alongside v11 as of 2026-04-29). The `v10` field set is `(feed_id, valid_from_timestamp, observations_timestamp, native_fee, link_fee, expires_at, last_update_timestamp, price, market_status, current_multiplier, new_multiplier, activation_datetime, tokenized_price)`.
**Role in soothsayer stack:** `historical reference` + `comparator` — the Chainlink schema our V1 weekend-bias measurements were computed against (87-obs panel, [`reports/v1_chainlink_bias.md`](../../../reports/v1_chainlink_bias.md)). The active 24/5 archetype framing in Paper 1 §1 chains through both v10 and v11, depending on which schema the per-feed publisher emits.
**Schema in scryer:** `dataset/soothsayer_v5/tape/v1/year=YYYY/month=MM/day=DD.parquet` — the Chainlink v10 columns (`cl_tokenized_px`, `cl_venue_px`, `cl_market_status`) live in the v5 joined tape. The 8 v10 xStock feed IDs are pinned in `src/soothsayer/chainlink/feeds.py:31-41` (`XSTOCK_FEEDS`). Decoding logic: `src/soothsayer/chainlink/v10.py:124` `decode(report: bytes) -> V10Report`. v10-specific schema venue (e.g. `dataset/chainlink_data_streams/v1/...`) ships scryer-side per the new `chainlink_data_streams.v1` schema (per [`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 17, phase 60); the v5 tape remains the joined consumption surface used by Paper 1.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

Chainlink Data Streams v10 is the original "Tokenized Asset" schema for tokenized-equity RWA feeds — the format active for xStock feeds since the Solana mainnet xStocks launch (2025-07-14) through 2025-Q4, when v11 was layered on alongside it. Each report carries **two** price fields with very different semantics:

- `price` (i192, 18-decimal fixed point) — the **last traded price on the underlying venue** (e.g., NYSE / Nasdaq SPY). This field is **stale during closed-market windows**; it is the venue-last-trade and does not move on weekends or holidays. (See the V1 weekend-bias historical note in `src/soothsayer/chainlink/v10.py:36-41`: an earlier decoder mislabeled this field as "mid" and produced meaningless residuals against Monday open until the layout was corrected.)
- `tokenized_price` (i192) — the **24/7 CEX-aggregated mark**, updated continuously through weekends. This is the field Soothsayer's V5 tape compares against the DEX-mid path; in v10's layout, this is the "real Chainlink mark" for tokenized-stock consumers.

The presence of both fields is the v10 schema's distinguishing methodology choice: it preserves the underlying-venue last-trade as a separate signal from the 24/7 aggregated mark. Public docs do **not** publish the underlying source-venue list for `tokenized_price`, the weighting scheme, or the consensus algorithm — same opacity as v11.

The schema additionally carries corporate-action multipliers (`current_multiplier`, `new_multiplier`, `activation_datetime`) so that consumers can apply forward-scheduled splits/dividends without re-syncing.

### 1.2 Cadence / publication schedule

`market_status` is a **3-value** enum on v10 (vs. 6-value on v11):

| Code | Label (per `src/soothsayer/chainlink/v10.py:56-58`) | Soothsayer interpretation |
|---:|---|---|
| 0 | `Unknown` | DON has no session-state signal |
| 1 | `Closed` | Underlying venue is not in regular session (covers weekends + after-hours collectively) |
| 2 | `Open` | Underlying venue is in regular session |

This coarser status enum is the most material difference between v10 and v11 cadence semantics: v10 collapses pre-market / overnight / weekend / post-market into a single `Closed` code, whereas v11 distinguishes them. A consumer reasoning about "session state" on v10 cannot recover the finer windowing without additional context (clock + calendar lookup).

`tokenized_price` is published continuously while the DON is operational — v10's 24/7 promise. `price` updates only during venue regular-session.

### 1.3 Fallback / degraded behavior

- `expires_at` (u32 unix seconds) — invalidates after this timestamp; consumers using the Verifier-CPI integration check this and skip stale reports.
- `last_update_timestamp` is a u64 nanoseconds-since-epoch field; combined with `observations_timestamp` (seconds), large skews indicate the DON is republishing without a fresh source-data tick.
- Public docs surface no formal fallback for `tokenized_price` when the constituent CEX/DEX venues thin out.

### 1.4 Schema / wire format

416-byte ABI-encoded payload, 13 × 32-byte words, field order pinned in `src/soothsayer/chainlink/v10.py:13-29`. Schema id `0x000a` in the leading 2 bytes of the report envelope's `feed_id`. Like v11, integer fields are big-endian and right-aligned; `i192` fields are sign-extended across the full 32-byte word.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet (joined-tape path):** `dataset/soothsayer_v5/tape/v1/...` — the columns `cl_tokenized_px` (mapping to v10 `tokenized_price`), `cl_venue_px` (mapping to v10 `price`), `cl_market_status` are present per the loader at `src/soothsayer/sources/scryer.py:240` `load_v5_window`. Continuous capture since 2026-04-24 (`docs/v5-tape.md`).
- **Scryer parquet (planned, dedicated venue):** `dataset/chainlink_data_streams/v1/...` per scryer phase 60 (`chainlink_data_streams.v1::Report`). Both v10 and v11 reports decode into the same row schema scryer-side; downstream consumers filter on the `schema` column.
- **On-chain reconstruction:** Verifier program (`Gt9S41PtjR58CbG9JhJ3J6vxesqrNAswbWYbLNTMZA3c`) — same Verifier handles both v10 and v11 schemas. Decoder: `src/soothsayer/chainlink/v10.py:124` `decode(report: bytes) -> V10Report`. Parser: `src/soothsayer/chainlink/verifier.py:66` `parse_verify_return_data` (the easy path, reading `meta.returnData`).
- **Symbol mapping:** `XSTOCK_FEEDS` registry at `src/soothsayer/chainlink/feeds.py:31-41` maps the 8 v10 feed IDs (one per xStock) → symbol. All 8 underliers (SPYx, QQQx, TSLAx, GOOGLx, AAPLx, NVDAx, MSTRx, HOODx) are mapped, verified by yfinance correlation at <0.15% match precision. **This is wider coverage than v11**, where only 4 of 8 xStocks are mapped.
- **Coverage in current tape:** The 87-observation V1 panel ([`reports/v1b_chainlink_comparison.md`](../../../reports/v1b_chainlink_comparison.md)) spans 11 weekends 2026-02-06 → 2026-04-17 across all 8 xStocks; v5 tape adds continuous capture forward. The pre-cutover artefact `data/processed/v1_chainlink_vs_monday_open.parquet` is the frozen V1-bias panel (retained for reproducibility of the methodology log entry).

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| v10 publishes `tokenized_price` continuously through weekends. | Confirmed empirically on the 87-obs V1 panel ([`reports/v1b_chainlink_comparison.md`](../../../reports/v1b_chainlink_comparison.md)): every weekend window has non-null `cl_tokenized_px` for all 8 xStocks. | **confirmed** |
| `price` (venue last-trade) is stale during `market_status=1` (Closed). | Confirmed structurally — consistent with v10 design (the historical-note at `src/soothsayer/chainlink/v10.py:36-41` documents the V1 misanalysis that arose from treating `price` as a 24/7 mark). The earlier mislabeling produced "meaningless residuals" against Monday open until the layout was corrected. | **confirmed** |
| `tokenized_price` is unbiased against the actual Monday open. | **Confirmed (point estimate).** [`reports/v1_chainlink_bias.md`](../../../reports/v1_chainlink_bias.md) measures pooled bias `−8.77 bps, t = −0.52, p = 0.605` (undetectable at panel size). v10's 24/7 mark is empirically unbiased as a point estimate. | **confirmed (point)** |
| v10 publishes a coverage band for `tokenized_price`. | **Contradicted (no band exists).** v10's wire format carries no bid/ask, no confidence, no dispersion field. The schema docstring at `src/soothsayer/chainlink/v10.py:8` is explicit: "It does NOT carry bid/ask or order book depth." [`reports/v1b_chainlink_comparison.md`](../../../reports/v1b_chainlink_comparison.md) Finding 1 confirms: a downstream consumer derives a degenerate zero-width band from v10. | **contradicted** |
| Corporate-action multipliers (`current_multiplier`, `new_multiplier`, `activation_datetime`) are populated when an action is scheduled. | Confirmed structurally (`src/soothsayer/chainlink/v10.py:31-34` "during US trading hours with SPY at ~711, w7=708.585 and w12=711.460, with marketStatus=1" sample, multiplier defaulting to `1e18`). Scheduled-action propagation has not been empirically validated against a known dividend/split event in our tape — that's a §6 question. | **confirmed (default), unmeasured (active)** |
| `tokenized_price` aggregation rule is publicly documented. | **Contradicted / unmeasurable.** Same as v11: the underlying source-venue list, weighting, and consensus algorithm for `tokenized_price` are not surfaced in public docs. | **unmeasurable from public surface** |
| `market_status` codes match the docs (0 Unknown / 1 Closed / 2 Open). | Confirmed — the on-chain reports observed in our tape carry `market_status ∈ {1, 2}` per the decoder docstring's live SPYx sample, and the registry consistency is verified by the V1 panel decoding (no out-of-range codes). | **confirmed** |

The 87-observation V1 panel anchors v10's empirical reconciliation: `tokenized_price` provides an unbiased point estimate with no published band — exactly the comparator framing Paper 1 §1 turns on. The v10 surface is a stricter version of the v11 finding: v11 at least carries `bid` / `ask` fields (which we then established are synthetic on weekends, see [`oracles/chainlink_v11.md`](chainlink_v11.md) §3); v10 carries no band fields at all.

---

## 4. Market action / consumer impact

Chainlink v10 is the active schema for several downstream Solana lending integrations — the wider-than-Kamino question is who actually reads `cl_tokenized_px` vs `cl_venue_px`.

- **Kamino klend (Scope-mediated)** — Kamino's xStocks reserves wire through Scope (`HFn8GnPADiny6XqUoWE8uRPPxb29ikn4yTuPa9MF2fWJ`); Scope sources Chainlink v10 (legacy schema) for some feeds and other inputs for xStocks specifically. The 2026-04-24 Kamino weekend reconciliation in [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md) §1 records `PriceHeuristic` ranges that Scope-served xStock prices must lie within; the underlying oracle path is Scope, with v10 as one upstream input.
- **Consumer-direct integrations (non-Kamino)** — any consumer that integrates Chainlink Data Streams via the Verifier program directly without a Scope-style middleware reads v10 reports. **TODO**: enumerate via Verifier program tx logs which consumer programs CPI the Verifier and pin which ones consume v10 vs v11 — this is a §6 open question, gated on `chainlink_data_streams.v1` continuous tape (scryer phase 60, shipped 2026-04-29).
- **MarginFi** — public docs do not list Chainlink as a supported oracle source for marginfi-v2 (per [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §1.1, the README accessed 2026-04-29 lists Switchboard, Pyth, and Fixed only). v10 has no live MarginFi consumer path. **TODO if/when Chainlink lands on MarginFi.**
- **Drift Protocol** — Drift's public oracle stack has supported Chainlink in some form historically; whether xStock-class markets on Drift consume v10 specifically is a §6 open question. **TODO when scryer adds drift_perp_oracle_tape.v1 (not yet in `scryer/wishlist.md`).**
- **Paper 1 §1 framing** — the V1 weekend-bias finding (pooled −8.77 bps, undetectable) anchors the "v10 publishes an unbiased point estimate but no band" claim. This is the *unbiased-point + missing-band* archetype that Paper 1 §1 contrasts with soothsayer's calibrated band — it is the cleanest single-archetype example for the "no incumbent publishes a verifiable calibration claim" framing because the schema itself is structurally band-less.
- **Public dashboard (Phase 2)** — `cl_tokenized_px` is the natural v10 row to put next to soothsayer's served band: same window, same xStock, same realised Monday open, and a degenerate (zero-width) v10 band column making the comparison visually unambiguous.

---

## 5. Known confusions / version pitfalls

- **v10 vs v11 (the headline trap).** Both are active on Solana mainnet as of 2026-04-29. v10 = schema id `0x000a`, 416 bytes, 13 fields, `tokenized_price`-anchored, no bid/ask. v11 = schema id `0x000b`, 448 bytes, 14 fields, `mid`-anchored, with bid/ask (which on weekends are synthetic — see [`oracles/chainlink_v11.md`](chainlink_v11.md) §3). The Verifier program serves both; `parse_verify_return_data` returns the schema in `ParsedVerify.schema` so callers can dispatch. **Cross-referencing third-party "Chainlink xStock" claims without checking schema id is the single most common confusion in this stack.**
- **`price` ≠ `tokenized_price`.** The historical V1 mislabeling (`src/soothsayer/chainlink/v10.py:36-41`) treated `price` as a 24/7 mark and produced meaningless weekend residuals. Always read `tokenized_price` (word 12) for the 24/7 mark; `price` (word 7) is venue-last-trade and frozen during `market_status=1`.
- **`market_status=1` is "Closed" on v10 but "Pre-market" on v11.** The 3-state enum in v10 collapses pre-market / weekend / overnight / post-market into a single `1`; the 6-state enum in v11 maps `1 = Pre-market` and `5 = Closed`. **Status codes are not portable across schemas.**
- **`tokenizedPrice` colloquially refers to v10 word 12 in legacy material**, but is also Chainlink's marketing name for "the 24/7 mark" generally — which on v11 corresponds to `mid` (word 6). Don't assume the same value semantics across schemas.
- **Multiplier semantics.** `current_multiplier` is normalised to `1e18` — a 1.0 multiplier is `10^18`, not `1`. Consumers that read the raw integer without dividing by the scale will think every xStock is in a 10^18-for-1 split.
- **`expires_at` on v10 is u32 unix seconds**, not a relative TTL; same gotcha as v11.
- **Verifier-program return-data path.** Same as v11: when an outer program (e.g., Scope) CPIs the Verifier and forwards the return bytes, `meta.returnData.programId` is the **outer program**, not the Verifier. The payload is still byte-identical so the easy-path parser doesn't filter on `programId`; the caller validates by feed_id + schema (`src/soothsayer/chainlink/verifier.py:74-78`).

---

## 6. Open questions

1. **Are any non-Kamino Solana consumers reading v10 directly via Verifier CPI today?** The phase-60 `chainlink_data_streams.v1` continuous tape (scryer wishlist item 17, shipped 2026-04-29) lets us enumerate Verifier-CPI calls per consumer program; once the tape has a few weeks of cadence, decode the outer-program-program-id in each Verifier call and bucket by schema. **Why it matters:** if v10 has zero non-Kamino consumers, the Paper 1 §1 framing for v10 weakens (it's a museum piece). If it has wide consumers, the 8-feed coverage advantage over v11 (4 mapped) becomes load-bearing. **Gating:** scryer phase-60 tape accumulation + analysis pass.
2. **Is v10 being deprecated for new xStock integrations, or is it co-existing with v11 indefinitely?** Both schemas are observable as of 2026-04-29; the trajectory is not surfaced in Chainlink's public docs. **Why it matters:** if v10 is being deprecated, soothsayer's Paper 1 §1 archetype framing should foreground v11 (with the synthetic-bid finding) and treat v10 as a historical reference; if both will persist, the dual archetype expands the comparator surface. **Gating:** Chainlink Labs outreach, or Verifier program log audit showing v10 publish-rate trend.
3. **Have we observed a corporate-action multiplier change in our v5 tape?** The schema supports forward-scheduled splits/dividends via `new_multiplier` + `activation_datetime`. We have not validated the propagation against a known event. **Why it matters:** Paper 1 §10.2 corp-action confounder filter depends on the issuer-side ground truth (Backed) matching the oracle-side multiplier signal. **Gating:** cross-reference `dataset/backed/corp_actions/v1` against `cl_*_multiplier` columns over the 2026-Q1 → present window.
4. **Does v10 publish the same `tokenized_price` value as v11's `mid` for the 4 underliers where both schemas have feeds (SPYx, QQQx, TSLAx, NVDAx)?** Or do they diverge — i.e., are they computed against different source pools? **Why it matters:** if they diverge, the V1 bias measurement on v10 does not transfer to v11 and we need a separate v11 bias measurement; if they match, the v10 bias result anchors v11 too. **Gating:** matched-window join in our v5 tape (low-effort once both feeds are continuously captured for 4+ weekends).
5. **What is the formal `tokenized_price` aggregation rule?** Same opacity as v11. **Gating:** Chainlink Labs outreach.

---

## 7. Citations

- [`chainlink-streams-v10`] Chainlink Labs. 2025. *Data Streams "Tokenized Asset" (v10) report schema*. Public docs at https://docs.chain.link/data-streams (top-level overview accessed 2026-04-29; v10-specific deep page no longer surfaced as a stable URL — refactor noted, working off the SDK-derived layout pinned in our decoder).
- [`v10.py-decoder`] Soothsayer internal. [`src/soothsayer/chainlink/v10.py`](../../../src/soothsayer/chainlink/v10.py). Python decoder, field-layout docstring, `MARKET_STATUS_*` constants, the historical-note about the V1 mislabeling.
- [`xstock-feed-registry`] Soothsayer internal. [`src/soothsayer/chainlink/feeds.py`](../../../src/soothsayer/chainlink/feeds.py) lines 31-41 (`XSTOCK_FEEDS`). The 8 v10 feed-id → symbol mapping, verified by yfinance correlation at <0.15% match precision.
- [`v1-chainlink-bias`] Soothsayer internal. [`reports/v1_chainlink_bias.md`](../../../reports/v1_chainlink_bias.md). Pooled −8.77 bps weekend bias measurement on v10's `tokenized_price` (87 obs, 8 xStocks, 11 weekends).
- [`v1b-chainlink-comparison`] Soothsayer internal. [`reports/v1b_chainlink_comparison.md`](../../../reports/v1b_chainlink_comparison.md). 87-observation panel; Finding 1 establishes v10/v11 publish no usable weekend band.
- [`verifier-parser`] Soothsayer internal. [`src/soothsayer/chainlink/verifier.py`](../../../src/soothsayer/chainlink/verifier.py). The two-path Verifier parser; the schema-id constants at lines 33-40 enumerate v3 / v7 / v8 / v10 / v11.
- [`chainlink-v11-companion`] Soothsayer internal. [`docs/sources/oracles/chainlink_v11.md`](chainlink_v11.md). The companion v11 reconciliation file — read both before concluding anything about a "Chainlink Data Streams" claim.
