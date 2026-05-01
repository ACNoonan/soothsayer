# `MarginFi (marginfi-v2)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://github.com/mrgnlabs/marginfi-v2` README (accessed 2026-04-29; covers oracle wiring, liquidator fee structure, group/bank/account hierarchy), `https://docs.marginfi.com/` introduction (accessed 2026-04-29; high-level architecture only, thin on liquidation parameters), [`reports/kamino_liquidations_first_scan.md:32-36`](../../../reports/kamino_liquidations_first_scan.md) (the load-bearing-source finding for Paper 3).
**Version pin:** **marginfi-v2** (the active production protocol). v1 is deprecated; cross-referencing pre-v2 forum posts is a known confusion (see §5). Exact program ID is **TODO** — pinning it is a §6 open question rather than a guess (the README references the `id-crate` directory but the README excerpt accessed today did not surface the literal address; mainnet program ID is canonically `MFv2hWf31Z4i1g2AhULZWnuwvvfuBQg4P4HFcXyFZi5` per public ecosystem references, but we have not pinned it via on-chain probe).
**Role in soothsayer stack:** `consumer target` — **load-bearing for Paper 3.** Per [`reports/kamino_liquidations_first_scan.md:34`](../../../reports/kamino_liquidations_first_scan.md), MarginFi is now the dominant on-chain source of liquidation events for any xStock-adjacent event-panel build (Kamino-xStocks produced zero events in a 30-day scan). The Paper 3 scope explicitly extends from Kamino-only to a wider lending-stack view; MarginFi is the highest-priority second consumer.
**Schema in scryer:** **not yet in scryer.** `dataset/marginfi/...` does not exist. There is no entry for MarginFi in `scryer/wishlist.md` Priority 0–3 buckets as of 2026-04-29 — adding one is a Paper-3 prerequisite. Target schemas: `marginfi/reserves/v1` (snapshot) and `marginfi/liquidations/v1` (event panel). Queue: see §6.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule (oracle consumption)

MarginFi-v2 does not compute a price; it consumes oracle prices from external providers. Per the marginfi-v2 README (accessed 2026-04-29):

> "Typically, **Switchboard** is the oracle provider, but **Pyth** is also supported, and some banks have a **Fixed price**."

Per-bank wiring lives at `bank.config.oracle_keys` (an account list — multi-oracle support exists; some banks, e.g. Kamino-position banks, point at multiple oracle accounts).

Critically — and this is the methodology cell that distinguishes MarginFi from many consumer protocols on Solana — **the oracle's confidence interval is consumed as a haircut**:

> "Oracles report price ±confidence; **assets use `P - confidence`, liabilities use `P + confidence`**."

This is a conservative-mark rule applied to *both sides* of the book. A widening Pyth confidence interval (publishers thinning during off-hours) directly reduces the credit MarginFi extends against the asset and inflates the liability for the borrower. Soothsayer's served band, in MarginFi-shaped terms, is conceptually the same primitive — but with an empirically-calibrated coverage promise rather than a publisher-dispersion-implied one. (See [`oracles/pyth_regular.md`](../oracles/pyth_regular.md) §3 for the publisher-dispersion-vs-coverage-SLA reconciliation.)

**Chainlink is not mentioned in the README.** The marginfi-v2 oracle-keys wiring as of 2026-04-29 supports Switchboard + Pyth + Fixed; Chainlink Data Streams v11 is not a supported oracle source on MarginFi. (Open question §6 #1.)

### 1.2 Cadence / publication schedule

MarginFi-v2 oracle reads happen at instruction time — there is no internal cadence; the oracle cadence is whatever the wired provider publishes. Two operational gotchas per the README:

- **Pyth oracles are managed by administrators** (price updates flow in via the Pyth program; MarginFi reads `PriceAccount` state).
- **Switchboard requires caller-initiated "crank" instructions** before consuming price data — i.e., a consumer (or keeper) must trigger the Switchboard feed update; the price MarginFi reads is whatever the most recent crank produced.

The crank requirement is operationally significant: during weekends or low-activity windows, a Switchboard-wired bank's price may be staler than the timestamp suggests because no one has cranked it. (Open question §6 #4.)

### 1.3 Fallback / degraded behavior

The README does not describe degraded-state behavior at the depth required for full reconciliation. The **insurance fee** structure (2.5%, paired with a 2.5% liquidator fee for a 5% total spread, range 2.5–10% depending on bank config) is the closest thing to a bad-debt buffer: when a liquidation closes a position, the insurance fund accrues 2.5% of the seized collateral. Whether the insurance fund socialises bad debt explicitly or only de-facto is a §6 open question.

The risk-engine layer ("End-to-End Risk Engine") is referenced as the off-chain monitoring/keeper system; what triggers it is not specified in the README excerpt.

### 1.4 Schema / wire format (account hierarchy)

| Account | Description | One-per |
|---|---|---|
| **Group** | Collection of banks; single administrator + delegate admins | per deployment / market |
| **Bank** | One per asset; stores settings, interest curves, oracle config (`bank.config.oracle_keys`), interest cache (`bank.cache`) | per asset within a Group |
| **Account** | User-created (multiple allowed per group); holds up to **16 balances** | per user (multiple) |
| **Balance** | One per (Bank, Account); either asset (collateral) or liability (debt), not both | per (user, bank, side) |

Interest curve parameters (per bank): `zero_util_rate`, `hundred_util_rate`, `points` (up to 7 curve points). Liquidation parameters live in the bank config — exact field names are not surfaced at this granularity in the README excerpt and are a §6 open question (target: pin them once the IDL is fetched).

---

## 2. Observable signals (where this lives in our data)

**Currently: nothing.** MarginFi is not in scryer; no IDL pinned at `idl/marginfi/`; no snapshot or scan scripts exist (target paths `scripts/snapshot_marginfi_xstocks.py` and `scripts/scrape_marginfi_liquidations.py` are referenced as planned in [`docs/data-sources.md`](../../data-sources.md) §8 but not implemented). Per [`docs/data-sources.md`](../../data-sources.md) Engineering inventory (line 311), MarginFi reserve config + historical liquidations is `📋 planned` at medium priority.

What needs to land for §3 / §4 to be empirically grounded:

1. **IDL pin** at `idl/marginfi/marginfi-v2.json` — fetchable via `anchor idl fetch <PROGRAM_ID>`. Same pattern as Kamino's `idl/kamino/klend.json` (v1.19.0, 8542 lines) and `idl/kamino/scope.json` (v0.33.0, 2204 lines).
2. **Reserve-config snapshot** scryer-side: `dataset/marginfi/reserves/v1/...`. One row per (Group, Bank) capturing oracle keys, LTV / liquidation threshold, liquidator + insurance fee config, interest-curve points, asset metadata, and `_fetched_at` for the on-chain snapshot moment.
3. **Liquidation-event panel** scryer-side: `dataset/marginfi/liquidations/v1/...`. One row per liquidation event decoded from program logs; includes pre/post collateral + debt, oracle prices at trigger time, liquidator address, fee splits, bundle-join key (for §4 MEV cross-reference). Same shape conceptually as the queued `kamino/liquidations/v1` (`scryer/wishlist.md` Priority-0 #1).

The right work order — from CLAUDE.md hard rule #2 — is: scryer phase entry first, fetcher + schema in scryer, then this file's §3 / §4 fills in.

---

## 3. Reconciliation: stated vs. observed

**Mostly TODO.** Reconciliation rows below are gated on the scryer landing of `marginfi/reserves/v1` and `marginfi/liquidations/v1` (§2). Listed here so the file is structurally complete and the rows can be filled in-place when data lands.

| Stated claim | Observation | Verdict |
|---|---|---|
| Oracle providers are Switchboard (typical), Pyth (supported), Fixed (some banks). | **TODO when `marginfi/reserves/v1` lands.** Once the snapshot is in scryer, decode `bank.config.oracle_keys` for each xStock-adjacent and high-volume bank; report the actual provider distribution. | **TODO** |
| `assets use P - conf, liabilities use P + conf`. | **TODO when `marginfi/liquidations/v1` lands.** At each event, capture the oracle's published `(P, conf)` and the marginfi-effective price used for both sides; verify the haircut. | **TODO** |
| Liquidator fee is 2.5% (range 2.5–10% per bank config). | **TODO** — extract from each bank's snapshot; report the distribution. | **TODO** |
| Insurance fee is 2.5%. | **TODO** — same. | **TODO** |
| Partial liquidations are standard; minimum seizure restores health. | **TODO** — observe seized-collateral / debt-repaid ratio per event; verify it's the minimum to clear the health threshold rather than a fixed close-factor. | **TODO** |
| Switchboard requires caller-initiated crank — staleness varies with keeper activity. | **TODO** — measure `oracle_publish_time` vs `liquidation_event_time` across the panel; segment by oracle provider. | **TODO** |
| Confidence-interval haircut works as a real risk gate during off-hours. | **TODO and load-bearing for Paper 3.** Cross-reference Pyth `pyth_conf` widening on weekends with marginfi liquidation events on weekends; show whether the haircut absorbs the realised move (good) or only marginally widens before the buffer is exhausted (bad). | **TODO (Paper 3 §3 / §4 will lean on this)** |
| MarginFi has higher xStock-adjacent liquidation activity than Kamino. | **Provisionally confirmed by inference**: [`reports/kamino_liquidations_first_scan.md:34`](../../../reports/kamino_liquidations_first_scan.md) found 0 Kamino-xStock liquidation events in 30 days; the grant retrospective cited ~$88.5M Q1 2025 fees / ~9 active liquidators on MarginFi, suggesting non-zero event rate. **Direct comparison TODO when `marginfi/liquidations/v1` lands.** | **provisional, pending direct measurement** |

---

## 4. Market action / consumer impact

### 4.1 Why MarginFi is load-bearing for Paper 3

The original Paper 3 scope was Kamino-xStocks-centric. The 30-day Kamino-xStocks liquidation scan ([`reports/kamino_liquidations_first_scan.md`](../../../reports/kamino_liquidations_first_scan.md)) found zero events, which means the Paper-3 empirical "did the served band change a real liquidation outcome" question cannot be answered on Kamino-xStocks alone over recent windows. MarginFi is the next-densest source of on-chain liquidation events on Solana; it is **the** load-bearing event source per the scan's own conclusion (line 34): *"MarginFi is now the load-bearing source of liquidation events for any serious event-panel build, not Kamino."*

This is the strongest single argument against an over-Kamino-centric file set in this directory: Paper 3's empirical contribution depends on a non-Kamino consumer, and that consumer is MarginFi.

### 4.2 Downstream-of-oracle impact (where soothsayer's served band could plausibly change a MarginFi outcome)

- **Pyth-wired MarginFi banks** — if soothsayer's served band were available as a MarginFi-readable oracle source, the conf-haircut rule (`P - conf` for assets, `P + conf` for liabilities) is structurally compatible with reading a calibrated band's `(lower, upper)` directly. The substitution is one-line: `P - conf → lower`, `P + conf → upper`. Paper 3 §6 / §7 should explicitly compare `pyth_conf`-haircut vs `soothsayer_band`-haircut on the realised liquidation panel.
- **Switchboard-wired MarginFi banks** — Switchboard publishes via `OracleJob` pipeline; soothsayer could publish a `OracleJob` that returns a calibrated band. The `pyth_conf`-vs-soothsayer reconciliation extends naturally.
- **Fixed-price banks** — these are typically pegged-asset banks (e.g., USDC, USDT); soothsayer is structurally not a comparator here.

### 4.3 OEV / liquidation-rent tie-in

MarginFi liquidations join with Jito bundles and (potentially) Pyth Express Relay auctions to form the OEV story Paper 3's wider scope is interested in. Once `marginfi/liquidations/v1` and `jito/bundles/v1` exist scryer-side, the join is a one-liner; today, the surface is empty.

### 4.4 Other consumers worth comparing in §4 (non-Kamino enforcement)

To honour the INDEX rule that §4 must cite a non-Kamino consumer: **MarginFi is the non-Kamino consumer in this file by construction.** This file's existence and Paper 3 prioritisation is the operational realisation of the wider-than-Kamino discipline.

---

## 5. Known confusions / version pitfalls

- **marginfi-v1 vs marginfi-v2.** v1 is deprecated; cross-referencing pre-v2 forum posts, audits, or risk write-ups will surface different account schemas, oracle wiring, and liquidation parameters. Always check whether a citation is v1 or v2.
- **Bank-level oracle wiring is not group-level.** Different banks within the same Group can use different oracle providers. Code that says "MarginFi uses Pyth" is wrong at the bank granularity — some use Switchboard, some Fixed, some multi-oracle. Always read `bank.config.oracle_keys`.
- **Confidence-interval haircut applies asymmetrically.** `P - conf` for assets, `P + conf` for liabilities. A user with both an asset balance and a liability balance in the same Account experiences both haircuts simultaneously — the effective LTV impact is more aggressive than either side alone.
- **Switchboard staleness vs Pyth staleness are not interchangeable.** Switchboard requires a caller-initiated crank; Pyth is administrator-pushed. A Switchboard-wired bank during a low-keeper-activity window can have arbitrarily stale prices. Code that treats `oracle_publish_time` as freshness must segment by oracle provider.
- **`Account` has 16 balances max.** A user reading "MarginFi positions" must not assume one Account = one position; typical user has multiple Accounts.
- **`mrgnlend` ≠ marginfi-v2.** mrgnlend is the borrowing/lending product; marginfi-v2 is the protocol. mrgnloop is a leveraged-loop strategy on top. Cross-referencing "mrgnlend liquidation" against v2 program-log decode requires understanding that mrgnlend logic resolves to v2 instructions.

---

## 6. Open questions

1. **Exact mainnet program ID for marginfi-v2.** README accessed today references `id-crate` but did not surface the literal address. **Gating:** read `marginfi-v2/programs/marginfi/src/lib.rs` declare_id! macro, or fetch the IDL via `anchor idl fetch <PROGRAM_ID>` against the canonical address (`MFv2hWf31Z4i1g2AhULZWnuwvvfuBQg4P4HFcXyFZi5`, per public ecosystem references — pin via on-chain `getAccountInfo` confirmation before trusting).
2. **Are any xStock SPL tokens listed as collateral or borrow assets in any marginfi-v2 Group?** Critical for whether MarginFi is a direct consumer of soothsayer's xStock-targeted output, vs. an adjacent comparator. **Gating:** snapshot all marginfi-v2 banks, filter by mint == xStock-mint-registry. The xStock mint registry is in `src/soothsayer/universe.py`.
3. **Liquidation-trigger formal condition.** Health-threshold formula and the exact trigger condition (`maintenance health factor < 1.0`?). **Gating:** IDL fetch + bank-config field decode.
4. **Switchboard crank cadence on production banks during weekends.** Empirically, how stale do Switchboard-wired bank prices get on Sat/Sun? **Gating:** `marginfi/reserves/v1` snapshot + cross-reference with Switchboard PullFeed last-update timestamps.
5. **Insurance-fund socialisation.** Does the insurance fund explicitly absorb bad debt (no socialisation across banks/users), or does it socialise via reserve dilution? **Gating:** README + governance forum search.
6. **Liquidator fee distribution across banks.** The 2.5–10% range is documented; the actual distribution across banks is not. **Gating:** snapshot all banks; report the histogram.
7. **Whether the conf-haircut is bypassable.** Some MarginFi-style protocols offer a bypass for "trusted" oracles (e.g., Fixed-price banks). Whether any non-trivial bank has the haircut effectively disabled is risk-relevant. **Gating:** snapshot review.
8. **Does Chainlink v11 land as a marginfi-v2 supported oracle in the future?** Currently not supported per the README. If/when it does, the synthetic-marker finding in [`oracles/chainlink_v11.md`](../oracles/chainlink_v11.md) §3 becomes directly relevant to MarginFi liquidation outcomes.

---

## 7. Citations

- [`marginfi-v2-readme`] mrgnlabs. *marginfi-v2 README*. https://github.com/mrgnlabs/marginfi-v2. Accessed: 2026-04-29.
- [`marginfi-docs-intro`] mrgnlabs. *marginfi documentation* (introduction). https://docs.marginfi.com/. Accessed: 2026-04-29.
- [`kamino-liquidations-first-scan`] Soothsayer internal. [`reports/kamino_liquidations_first_scan.md`](../../../reports/kamino_liquidations_first_scan.md). Source of the load-bearing-event-source finding (Kamino-xStocks 30-day = 0 events; MarginFi is the next-density source).
- [`coindesk-redstone-weekend`] Cited indirectly via [`docs/sources/oracles/redstone_live.md`](../oracles/redstone_live.md) §1.1; the weekend-gap industry framing is consistent with MarginFi's exposure on equity-class banks if any are added in future.
- [`pyth-regular-reconciliation`] Soothsayer internal. [`docs/sources/oracles/pyth_regular.md`](../oracles/pyth_regular.md). The publisher-dispersion-vs-coverage-SLA reconciliation that directly informs MarginFi's `P ± conf` haircut behavior at off-hours.
