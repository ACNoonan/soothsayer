# `Scope (Kamino's in-house aggregator)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `idl/kamino/scope.json` (v0.33.0, 2204 lines, on-chain-fetched IDL pin), `src/soothsayer/sources/scryer.py:158` `load_kamino_scope_window` loader, **live scryer tape** at `dataset/kamino_scope/oracle_tape/v1/...` (live since 2026-04-26 16:05 UTC; Apr 26 / 28 / 29 / 30 partitions present 13,776 rows across 8 xStocks as of probe 2026-04-29), [`docs/data-sources.md`](../../data-sources.md) §8 lines 241-245 (the Scope account architecture summary), [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md) (the weekly weekend reconciliation report). No public Scope methodology docs page surfaced in our 2026-04-29 probe — Scope is **Kamino-internal infrastructure**, documented via the IDL + Kamino's reserve-config code paths rather than a standalone product page.
**Version pin:** **Scope program `HFn8GnPADiny6XqUoWE8uRPPxb29ikn4yTuPa9MF2fWJ`** (Solana mainnet), IDL v0.33.0 pinned at `idl/kamino/scope.json`. The single `OraclePrices` account holds `[DatedPrice; 512]`; the xStock-class shared feed PDA is **`3t4JZcueEzTbVP6kLxXrL3VpWx45jDer4eqysweBchNH`** with all 8 xStocks differentiated by chain index (`SPYx=344, QQQx=347, TSLAx=338, GOOGLx=326, AAPLx=317, NVDAx=332, MSTRx=335, HOODx=320`).
**Role in soothsayer stack:** `consumer's primary oracle (xStocks-on-Kamino)` — Scope is the **actual price** Kamino's klend reserves consume for xStocks. Every Kamino xStock liquidation, every health-check, every borrow-cap evaluation reads through this surface. Soothsayer's served band is conceptually a **replacement** for the Scope-served point estimate (or an upstream calibration layer that Scope could fold in via a soothsayer feed input). Cross-reference [`docs/sources/lending/kamino_klend.md`](../lending/kamino_klend.md) (planned) for the consumer-side reconciliation.
**Schema in scryer:** **✅ live.** `dataset/kamino_scope/oracle_tape/v1/year=YYYY/month=MM/day=DD.parquet` (schema `kamino_scope.v1`). Loader: `src/soothsayer/sources/scryer.py:158`. Continuous capture since 2026-04-26 16:05 UTC.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

Scope is **Kamino's in-house oracle aggregator** — not a third-party oracle network like Pyth or Chainlink. It is a Solana program that maintains a single fixed-size array `[DatedPrice; 512]` of prices, indexed by **chain ID** (a u16 ranging 0–511). Per the IDL at `idl/kamino/scope.json:153-174`:

```
OraclePrices {
  oracleMappings: publicKey,
  prices: [DatedPrice; 512],
}
```

A `DatedPrice` is `(price: Price, lastUpdatedSlot: u64, unixTimestamp: u64, genericData: [u8; 24])` per `idl/kamino/scope.json:1658-1686`. The `Price` itself is a `(value: u64, exp: u64)` struct (decoded as `value * 10^-exp` for the actual price; example: `271256444232958334` with `exp=15` decodes to `271.256444`, see SPYx in our tape).

The **aggregation methodology is multi-source-fan-in by chain ID**. Each chain ID slot in the 512-entry array is configured (off-chain, by Kamino governance) to source from one of multiple oracle types — Pyth, Chainlink, a constant value, a Kamino-computed TWAP, etc. The IDL enumerates chain types including `ScopeTwap1h`, `ScopeTwap8h`, `ScopeTwap24h`, `ScopeTwap7d` (per `idl/kamino/scope.json:2069-2159`), suggesting Scope itself can produce TWAPs over its own consumed prices. The chain-id-to-oracle-source mapping is held by `oracleMappings` (a separate account); we have not pinned this account yet.

For the 8 xStocks, all 8 chain IDs (317–347 range) point at the **same feed PDA** (`3t4JZcueEzTbVP6kLxXrL3VpWx45jDer4eqysweBchNH`) — a single `OraclePrices` account multiplexed across all 8 xStocks. One `getAccountInfo` call reads all 8 prices. Whether the upstream sources for xStock chain IDs are Chainlink v10 `tokenized_price`, Pyth, or a custom Scope-computed price is **not surfaced in the IDL alone**; the `oracleMappings` account contents are the load-bearing missing piece (see §6).

### 1.2 Cadence / publication schedule

Scope's cadence is **publisher-pushed** by Kamino-operated keeper(s). Per the live scryer tape (Apr 26 / 28 / 29 / 30, 2026), the empirical cadence is **roughly one update per minute per xStock**, with the actual `scope_unix_ts` (the on-chain Scope `unixTimestamp` field) advancing on each push. The keeper appears to push regardless of whether the underlying value has changed (this is the load-bearing weekend-finding, see §3).

The `scope_age_s` column (derived as `wall_clock_at_poll - scope_unix_ts`) ranges 5–95 seconds in our tape. Scope publishes a fresh timestamp roughly every 30–60 seconds; consumer-side staleness reads relative to `tokenInfo.maxAgePriceSeconds` (per Kamino's klend reserve config, see [`docs/data-sources.md`](../../data-sources.md) line 238).

### 1.3 Fallback / degraded behavior

- **Per-chain price-validity heuristic.** Per [`docs/data-sources.md`](../../data-sources.md) line 238, Kamino's klend reserve config carries a `tokenInfo.heuristic` field — an on-chain `[lower, upper, exp]` range that the Scope-served price must lie within for the reserve action to proceed. When Scope's price falls outside this range, klend's reserve actions revert. This is the **outermost guard rail** against an oracle malfunction — it does not correct the price, but it prevents the protocol from acting on an obviously-broken value.
- **`maxAgePriceSeconds`** — when the Scope `unixTimestamp` is older than this threshold, the consumer treats the price as stale.
- **Below-source-quorum fallback.** What happens if the upstream chain-id source (e.g., Chainlink v10) is unavailable is **not surfaced in the IDL**. Scope likely has fallback chains configured (the `scopeChain` errors in the IDL — `BadScopeChainOrPrices` at `idl/kamino/scope.json:285-286` — suggest a multi-chain fallback structure), but the deep semantics need source-code inspection.

### 1.4 Schema / wire format

Per `idl/kamino/scope.json` and the live scryer schema:

| Column | Type | Source |
|---|---|---|
| `poll_ts` | iso string | wall-clock at poll |
| `symbol` | string | derived from chain_id |
| `feed_pda` | base58 string | shared `OraclePrices` PDA — `3t4JZcueEzTbVP6kLxXrL3VpWx45jDer4eqysweBchNH` for xStocks |
| `chain_id` | u16 | per-asset slot index in the 512-entry array |
| `scope_value_raw` | u64 | `Price.value` (raw integer) |
| `scope_exp` | u64 | `Price.exp` (decimal exponent) |
| `scope_price` | f64 | derived `value * 10^-exp` |
| `scope_slot` | u64 | `DatedPrice.lastUpdatedSlot` |
| `scope_unix_ts` | i64 | `DatedPrice.unixTimestamp` |
| `scope_age_s` | i64 | derived `wall_clock_at_poll - scope_unix_ts` |
| `scope_err` | string \| null | non-null on read failure |

The 24-byte `genericData` field (per the IDL at `idl/kamino/scope.json:1675-1683`) is captured as opaque bytes; what it carries varies per chain type and has not been decoded for xStock feeds in our tape.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** `dataset/kamino_scope/oracle_tape/v1/year=YYYY/month=MM/day=DD.parquet` (`kamino_scope.v1`). Live since 2026-04-26 16:05 UTC. Loader: `src/soothsayer/sources/scryer.py:158` `load_kamino_scope_window`. As of probe 2026-04-29: **13,776 rows** across 8 xStocks across 4 days (Sun 26 / Tue 28 / Wed 29 / Thu 30) — the Apr 27 (Monday) partition was not yet observed in our local probe wave; this is a partition-presence detail to verify on next inspection.
- **On-chain account / program:** Scope program `HFn8GnPADiny6XqUoWE8uRPPxb29ikn4yTuPa9MF2fWJ`; `OraclePrices` account `3t4JZcueEzTbVP6kLxXrL3VpWx45jDer4eqysweBchNH`. IDL pinned at `idl/kamino/scope.json` (v0.33.0).
- **Decoder / loader:** the loader at `src/soothsayer/sources/scryer.py:158-176` reads the `kamino_scope.v1` columns; the on-chain decode happens scryer-side via the daemon (the legacy soothsayer-side `collect_kamino_scope_tape.py` was retired in the April 2026 cutover per [`docs/data-sources.md`](../../data-sources.md) §8 lines 244-246).
- **Coverage in current tape:** all 8 xStocks live; ~1-min cadence per asset (629–705 `scope_unix_ts` events per (symbol, full-day) on Apr 28/29). Sunday Apr 26 has 282–284 events per symbol over a partial-day window (16:05 UTC to end of day).

---

## 3. Reconciliation: stated vs. observed

The **load-bearing reconciliation** is the weekend stale-hold pattern, observable directly in the live scryer tape.

| Stated claim | Observation | Verdict |
|---|---|---|
| All 8 xStocks share one feed PDA differentiated by chain index. | Confirmed empirically — the `feed_pda` column has exactly **one** unique value (`3t4JZcueEzTbVP6kLxXrL3VpWx45jDer4eqysweBchNH`) across all 13,776 rows, and `chain_id` partitions cleanly: SPYx=344, QQQx=347, TSLAx=338, GOOGLx=326, AAPLx=317, NVDAx=332, MSTRx=335, HOODx=320. | **confirmed** |
| Scope publishes a continuous price during weekends (when underlying US-equity markets are closed). | **Partially confirmed but with a load-bearing nuance**: `scope_unix_ts` advances every ~30–60 seconds during the weekend window (e.g., Sun Apr 26 has 282–284 unique `scope_unix_ts` events per xStock over a 6.5-hour observation window) — **but `scope_price` itself does not change**. **Sun Apr 26 has exactly 1 unique `scope_price` value per xStock for all 8 underliers** despite hundreds of fresh-timestamp updates. **The aggregator is republishing a stale-held value with rotating timestamps**, not aggregating new closed-market information. | **contradicted (in the form a consumer expects)** |
| Scope's downstream consumers can rely on `scope_unix_ts` freshness to gate stale-rejection. | **Contradicted — `scope_unix_ts` is fresh, but the price it timestamps is stale-held.** A Kamino reserve checking only `tokenInfo.maxAgePriceSeconds` against `scope_unix_ts` will pass freshness-check during the weekend even though the underlying value has not moved. The freshness gate is **decoupled** from the value-update gate. | **contradicted (operational)** |
| Scope produces TWAPs (`ScopeTwap1h`, `ScopeTwap8h`, `ScopeTwap24h`, `ScopeTwap7d`). | Confirmed structurally per the IDL chain-type enum (`idl/kamino/scope.json:2069-2159`). **Unmeasurable** for xStocks specifically without the `oracleMappings` account decoded — the chain-id-to-source mapping is required to know whether any xStock is Scope-TWAP-fed vs. direct-Pyth-fed vs. direct-Chainlink-fed. | **confirmed (capability), unmeasurable (per-feed source)** |
| `scope_price` weekend value tracks Friday-close `tokenizedPrice` from Chainlink v10. | **Plausible but unverified at depth.** [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md) compares the Scope-served price against soothsayer's served band on the Apr 24 weekend; the per-symbol weekend Scope value is consistent with Chainlink v10 `tokenized_price` at 4-significant-figure precision. **Cross-source verification gated** on a join script: `scope_price` Friday-close vs `cl_tokenized_px` Friday-close vs `pyth_price` Friday-close, per xStock. | **plausible, not yet verified** |
| Scope's price-validity heuristic (klend's `tokenInfo.heuristic`) catches Scope outages. | **Unmeasurable in our current tape** — `scope_err` is non-null only on read failure (network / RPC errors), not on heuristic-rejection. The klend-side heuristic check is a *reserve-action revert*, observable as a failed transaction in `kamino/liquidations/v1` (when scryer wishlist item 1 lands). | **unmeasurable from current data** |
| Scope is a Kamino-internal aggregator, not a third-party oracle. | Confirmed structurally — the program is at a Kamino-controlled address; the IDL is in `idl/kamino/scope.json`; no public Scope-as-product docs page surfaces in our 2026-04-29 probe. The "in-house" framing is empirically supported. | **confirmed** |

**The load-bearing single-cell finding:** Scope's DatedPrice indirection + chain-index sharing means **all 8 xStocks share one feed PDA**, so a single Scope outage flips all reserves simultaneously. Combined with the stale-hold-with-fresh-timestamps pattern observed Sun Apr 26 (1 unique price, ~284 fresh timestamps per xStock), the consumer-experienced value is a **point estimate published as if real-time** with no consumer-readable signal that the underlying market is closed.

---

## 4. Market action / consumer impact

Scope is the **direct primary oracle** for Kamino klend's xStock reserves; the entire Kamino-xStocks lending stack hangs off this one PDA.

- **Kamino klend (xStocks)** — every xStock health check, every liquidation trigger, every borrow-cap evaluation reads `scope_price` for the relevant chain-id slot. The Sun-Apr-26 stale-hold pattern (§3) means: during a weekend, klend's risk engine evaluates positions against a **frozen Friday-close price**, even though the operational signals (`scope_unix_ts` freshness) appear healthy. If the realised Monday-open is meaningfully different from Friday close, the entire weekend window is a one-shot revaluation event at Monday open. **This is the canonical xStock weekend-gap problem** Paper 1 §1 frames, materialised at the consumer's actual oracle read.
- **Kamino klend (non-xStock reserves)** — Kamino uses Scope across all its lending markets; whether non-xStock reserves use the same `OraclePrices` PDA or different ones is **TODO when `kamino/reserves/v1` lands** ([`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 4). Likely separate PDAs per market segment.
- **MarginFi** — does not use Scope; uses Switchboard / Pyth / Fixed per [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §1.1. The Scope finding does not transfer to MarginFi-xStock-class banks (if any).
- **Drift / Save / Loopscale / Jupiter Lend** — none documented as Scope consumers in our reading. Scope is Kamino-specific.
- **Pyth / Chainlink (upstream of Scope)** — the question of which upstream oracle source feeds each xStock's Scope chain-id slot is the **§6 load-bearing open question**. If xStock chain-ids are fed from Chainlink v10 `tokenized_price`, the synthetic-bid finding from [`oracles/chainlink_v11.md`](chainlink_v11.md) §3 doesn't directly transfer (v10 has different schema), but the v10-`tokenized_price` weekend-bias (V1: −8.77 bps undetectable) does. If from Pyth, the publisher-dispersion-vs-coverage-SLA finding from [`oracles/pyth_regular.md`](pyth_regular.md) §3 transfers but at the point-estimate level only (Scope strips off the conf interval — see §3 row on no-CI-on-the-wire).
- **Soothsayer's H3 / publishing surface** — soothsayer's served band could plausibly be exposed as a **Scope chain-id source** if Kamino governance accepts it. This is conceptually different from the Switchboard/dedicated-relay paths because it would integrate directly into Scope's existing chain-id space (one chain-id per xStock-bound, with the Scope aggregator selecting between bound vs. raw). **Out of Phase 1 scope; relevant for Phase 2 Kamino governance conversation.**
- **Paper 1 §6 / §7 framing** — Scope is the canonical "consumer's primary oracle" archetype: the actual price the user's lending position is priced against. Soothsayer's served band sits one layer up: a calibrated band that an aggregator like Scope could ingest as a coverage-bounded input. The relationship between soothsayer (band publisher) and Scope (aggregator + serving) is the cleanest single-arrow story for Paper 1 §1's "calibration-transparent oracle for Solana RWAs" framing.
- **Paper 3 §3 / §6 / §7** — Scope's value at the moment of every Kamino-xStock liquidation trigger is the **counterfactual base** for "would soothsayer's served band have prevented this liquidation?" The Paper 3 OEV-recapture analysis is gated on `kamino/liquidations/v1` (item 1) joined with the `kamino_scope/oracle_tape/v1` we already have.
- **Public dashboard (Phase 2)** — Scope's per-xStock current value vs. soothsayer's served band is the **headline dashboard row**. Same window, same xStock, same realised Monday open, two different oracle outputs.

---

## 5. Known confusions / version pitfalls

- **Scope is Kamino-specific.** Cross-referencing "Scope oracle" without specifying Kamino is a mild confusion. There is no public Scope-as-product. The IDL is `kamino/scope.json` because Scope is a Kamino-owned program.
- **All 8 xStocks share one feed PDA.** A naive "one PDA per asset" assumption (which works for many Pyth / Switchboard deployments) is wrong here. Code that reads only the PDA without slicing by chain-id will read SPYx (chain 344), not the asset it expects.
- **`Price.exp` is a u64, not an i64.** The exponent is always positive; the price is `value * 10^-exp`. Code that decodes `exp` as a signed integer with negative values will produce nonsense.
- **`scope_unix_ts` freshness is decoupled from `scope_price` value-change.** This is the load-bearing pitfall: a freshness gate alone does not detect weekend stale-hold. Consumer code that wants real-update detection must compare consecutive `scope_price` values, not just `scope_unix_ts`.
- **`OraclePrices` carries `[DatedPrice; 512]` in a single account.** Account size is large (~25 KB); code that reads the whole account and slices locally is the canonical pattern. `getMultipleAccounts` for individual chain-id slots is not the right primitive — slicing happens after fetching the single account.
- **`chain_id` is the index into the 512-entry array, not a chain-specific identifier.** It's a Scope-internal slot index, not e.g. a Solana cluster ID or Wormhole chain ID. Cross-referencing `chain_id` against any other oracle's "chain id" concept is confusion.
- **`oracleMappings` is the missing piece.** Without decoding it, you cannot tell which upstream oracle feeds each xStock's chain-id slot. The IDL surfaces the field but the account contents need a snapshot decode.
- **The `scope_err` column captures read errors, not heuristic-rejection.** A klend tx that reverts because `tokenInfo.heuristic` rejected the Scope value will not surface in `scope_err`; it surfaces in klend logs (when the liquidation tape lands).
- **Scope-TWAP chains exist (`ScopeTwap1h`, etc.) but are not necessarily used for xStocks.** Don't assume the xStock chain-id slots are TWAP-fed without checking `oracleMappings`.

---

## 6. Open questions

1. **Decode the `oracleMappings` account.** **Why it matters:** the chain-id-to-upstream-source mapping is what tells us whether xStock Scope prices are Chainlink-v10-fed, Pyth-fed, Scope-TWAP-of-something-fed, or some other configuration. The reconciliation in §3 row 5 (`scope_price` weekend value tracks Friday-close Chainlink v10 `tokenized_price`) is gated on knowing this. **Gating:** `getAccountInfo` against the `oracleMappings` PDA pointed at by `OraclePrices.oracleMappings` (per IDL at `idl/kamino/scope.json:158`), then decode against the IDL `MintsToScopeChains` / `MintToScopeChain` types at `idl/kamino/scope.json:52-78`. **One-shot probe.**
2. **Cross-source verification of `scope_price` Friday-close value.** **Why it matters:** the §3 plausibility finding ("Scope tracks Chainlink v10 `tokenized_price`") becomes empirical confirmation. **Gating:** join `dataset/kamino_scope/oracle_tape/v1/...` with `dataset/soothsayer_v5/tape/v1/...` (which carries `cl_tokenized_px`) and `dataset/pyth/oracle_tape/v1/...` at Friday-close timestamps; report per-symbol value tuple.
3. **Quantify the weekend stale-hold pattern across more weekends.** Sun Apr 26 is a single-weekend observation; whether the 1-unique-price-with-fresh-timestamps pattern is universal across weekends, vs. occasional Saturday updates if a venue moves significantly, is unmeasured. **Gating:** scryer-tape accumulation (currently 4 days; need 4+ weekends for robust per-pattern measurement).
4. **Heuristic-rejection events.** **Why it matters:** when Kamino's `tokenInfo.heuristic` rejects a Scope value, that's the protocol's last line of defence against oracle malfunction. **Gating:** `kamino/liquidations/v1` (item 1) — heuristic-rejected reserve actions appear as failed klend txs.
5. **Does Scope source have multiple-source-quorum fallback?** The `BadScopeChainOrPrices` error at `idl/kamino/scope.json:285-286` suggests a fallback chain structure, but the depth is not surfaced in the IDL alone. **Gating:** Scope program source review (Kamino is open-source; the github repo is publicly inspectable).
6. **What does the `genericData: [u8; 24]` field on `DatedPrice` carry?** Different chain types likely use it differently. **Gating:** per-chain-type IDL deep-read + cross-reference against per-feed bytes in our tape.
7. **Why does HOODx have meaningfully fewer `scope_unix_ts` events than the other xStocks on weekdays?** Apr 28/29: HOODx has 481 / 334 events vs. ~630/675 for other xStocks. Suggests a chain-id-source-specific cadence quirk for HOOD specifically. **Gating:** `oracleMappings` decode (open question 1) — likely HOODx is wired to a different upstream than the other 7.
8. **Whether soothsayer's served band could plausibly become a Scope chain-id source.** **Why it matters:** the most direct integration path into the Kamino-xStocks lending stack. **Gating:** Phase 2 design + Kamino governance conversation.

---

## 7. Citations

- [`scope-idl`] Soothsayer internal. [`idl/kamino/scope.json`](../../../idl/kamino/scope.json). v0.33.0, 2204 lines, Anchor IDL pinned via on-chain fetch. Source-of-truth for the `OraclePrices`, `DatedPrice`, `MintsToScopeChains`, `MintToScopeChain`, and `ScopeChain` types.
- [`scope-loader`] Soothsayer internal. [`src/soothsayer/sources/scryer.py`](../../../src/soothsayer/sources/scryer.py) `load_kamino_scope_window` at line 158. Reader for `dataset/kamino_scope/oracle_tape/v1/...`.
- [`kamino-scope-tape-live`] Soothsayer internal. `dataset/kamino_scope/oracle_tape/v1/...` (live since 2026-04-26 16:05 UTC). The 13,776-row probe-window source for §3's empirical findings.
- [`kamino-weekend-comparator`] Soothsayer internal. [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md). The weekly weekend reconciliation; cross-references Scope, Pyth, soothsayer per-symbol on Apr 24.
- [`data-sources-scope`] Soothsayer internal. [`docs/data-sources.md`](../../data-sources.md) §8 lines 241-246. Scope account architecture summary.
- [`chainlink-v10-companion`] Soothsayer internal. [`docs/sources/oracles/chainlink_v10.md`](chainlink_v10.md). The plausible upstream source for Scope xStock chain-ids; weekend-bias finding (V1: −8.77 bps undetectable) transfers if the §6 #1 mapping decode confirms v10 wiring.
- [`pyth-regular-companion`] Soothsayer internal. [`docs/sources/oracles/pyth_regular.md`](pyth_regular.md). Alternative plausible upstream; publisher-dispersion finding transfers as point-estimate-only because Scope strips the conf interval.
- [`marginfi-companion`] Soothsayer internal. [`docs/sources/lending/marginfi.md`](../lending/marginfi.md). Counter-example: MarginFi does not use Scope, so the wider-than-Kamino lending-stack reconciliation is via Switchboard/Pyth, not Scope.
