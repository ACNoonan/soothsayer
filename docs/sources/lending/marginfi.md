# `MarginFi (marginfi-v2)` — Methodology vs. Observed

---

**Last verified:** `2026-05-01` (scryer-side IDL pin + reserve-config snapshot; supersedes 2026-04-29 README-only verification).
**Verified by:** scryer's 2026-05-01 MarginFi IDL pin + `marginfi/reserves/v1` snapshot of all 422 production Banks; `https://github.com/mrgnlabs/marginfi-v2` README (accessed 2026-04-29; covers oracle wiring, liquidator fee structure, group/bank/account hierarchy); `https://docs.marginfi.com/` introduction (accessed 2026-04-29; high-level architecture only, thin on liquidation parameters); [`reports/methodology_history.md`](../../../reports/methodology_history.md) 2026-05-01 entry (scryer-reconciliation amendment) for the indirect-xStock-exposure finding and the strategic-pivot reconciliation that supersedes the 2026-04-29 framing of this file.
**Version pin:** **marginfi-v2** (the active production protocol). v1 is deprecated; cross-referencing pre-v2 forum posts is a known confusion (see §5). Mainnet program ID: **`MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA`** (verified by scryer 2026-05-01 — the prior `MFv2hWf31Z4i1g2AhULZWnuwvvfuBQg4P4HFcXyFZi5` reading from public ecosystem references does not exist on mainnet; this was an open question at draft time and is now closed).
**Role in soothsayer stack:** `consumer target` — **deployment substrate for general lending; not the xStock-specific empirical event source.** The 2026-04-29 framing of this file leaned on a 30-day Kamino-xStocks zero-event scan to position MarginFi as "the load-bearing event source." Scryer's 2026-05-01 verification reframes this in two directions. First, the Kamino-xStocks panel is *not* empirically empty: a 9-month Kamino liquidation panel (`scryer/dataset/kamino/liquidations/v1/`) carries 102 events with a structural cluster 2025-11-04 → 2025-11-21 (8 events / 18 days, 7% of the panel). Second, MarginFi has **zero direct xStock Banks** among its 422 production Banks; xStock exposure on MarginFi exists only via `KaminoPythPush` / `KaminoSwitchboardPull` `OracleSetup` routes (i.e., MarginFi Banks that delegate their oracle read to Kamino-position infrastructure). A MarginFi liquidation on xStock-adjacent collateral is therefore a *downstream re-emission of a Kamino-position event*, not an independent observation — the cross-protocol comparison has structural asymmetry, not venue diversity (see §1.5 below). Net: MarginFi remains the cleanest **deployment substrate** for the conf-haircut substitution argument (general-lending; see §4.2), but Paper 3's xStock-specific **empirical event panel** is Kamino-xStocks, not MarginFi.
**Schema in scryer:** `marginfi/reserves/v1` landed 2026-05-01 (a snapshot of all 422 production Banks; this is the source of the no-direct-xStock-Banks finding above). `marginfi/liquidations/v1` is **not yet in scryer** — gating an empirical event panel; queued in `scryer/wishlist.md`. With the indirect-only xStock exposure, this panel will be mostly crypto-collateral events; xStock-attributable MarginFi liquidations (via Kamino-position routes) require a join on `OracleSetup` to disambiguate.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule (oracle consumption)

MarginFi-v2 does not compute a price; it consumes oracle prices from external providers. Per the marginfi-v2 README (accessed 2026-04-29):

> "Typically, **Switchboard** is the oracle provider, but **Pyth** is also supported, and some banks have a **Fixed price**."

Per-bank wiring lives at `bank.config.oracle_keys` (an account list — multi-oracle support exists; some banks, e.g. Kamino-position banks, point at multiple oracle accounts).

Critically — and this is the methodology cell that distinguishes MarginFi from many consumer protocols on Solana — **the oracle's confidence interval is consumed as a haircut**:

> "Oracles report price ±confidence; **assets use `P - confidence`, liabilities use `P + confidence`**."

This is a conservative-mark rule applied to *both sides* of the book. A widening Pyth confidence interval (publishers thinning during off-hours) directly reduces the credit MarginFi extends against the asset and inflates the liability for the borrower. Soothsayer's served band, in MarginFi-shaped terms, is conceptually the same primitive — but with an empirically-calibrated coverage promise rather than a publisher-dispersion-implied one. (See [`oracles/pyth_regular.md`](../oracles/pyth_regular.md) §3 for the publisher-dispersion-vs-coverage-SLA reconciliation.)

**Chainlink is not mentioned in the README.** The marginfi-v2 oracle-keys wiring as of 2026-04-29 supports Switchboard + Pyth + Fixed; Chainlink Data Streams v11 is not a supported oracle source on MarginFi. (See §1.5 for the actual taxonomy the IDL surfaces.)

### 1.5 OracleSetup taxonomy — delegated routing (verified 2026-05-01)

The README's "Switchboard / Pyth / Fixed" trichotomy understates reality. The on-chain `OracleSetup` enum surfaced by scryer's 2026-05-01 IDL pin is **18 variants**, including (non-exhaustive): `PythLegacy`, `SwitchboardV2`, `PythPushOracle`, `SwitchboardPull`, `StakedWithPythPush`, `KaminoPythPush`, `KaminoSwitchboardPull`, `DriftPythPull`, `JuplendPythPull`, `SolendPythPull`, and four `Fixed*` variants. Several of these are **delegated routing**: a MarginFi Bank reading `KaminoPythPush` does not consume Pyth directly — it consumes the price written by Kamino's oracle infrastructure, which itself reads Pyth.

This matters in two ways for soothsayer:

1. **xStock exposure on MarginFi is indirect-only.** Of the 422 production Banks scanned 2026-05-01, **zero are direct xStock SPL-token Banks**. The xStock collateral that does flow through MarginFi does so via `KaminoPythPush` and `KaminoSwitchboardPull` Banks — i.e., MarginFi Banks whose oracle read is delegated to Kamino-position infrastructure. This closes §6 #2 with the answer "indirect-only," which is sharper than either branch the prior draft anticipated. A MarginFi liquidation on xStock-adjacent collateral is therefore a downstream re-emission of a Kamino-position event, not an independent observation; the cross-protocol comparison has structural asymmetry, not venue diversity. Operationally, this means Paper 3's xStock empirical event panel is Kamino-xStocks (`scryer/dataset/kamino/liquidations/v1/`, 102 events 9-month, with the Nov 2025 cluster), and a MarginFi liquidations panel — once it lands — adds cross-protocol confirmation rather than an independent panel.

2. **The "calibration-transparent vs opaque" framing in Paper 1 §1.1 / §2.1 strengthens.** "MarginFi reads Pyth" is not a literal statement at the Bank granularity for many assets; the actual on-chain wiring routes through other protocols' oracle infrastructure, which is itself opaque to a MarginFi consumer. The simple Pyth-vs-Chainlink-vs-Switchboard taxonomy is a *naming* layer above a *delegated-routing* layer that the literature does not surface. (Paper 1 §1.1 / §2.1 should add a "delegated routing" axis; tracked separately as a Paper-1 framing item.)

### 1.6 BankCache.last_oracle_price — per-Bank staleness panel (verified 2026-05-01)

Each MarginFi Bank carries a `BankCache` field with `last_oracle_price`, `last_oracle_confidence`, and `cache_last_oracle_price_timestamp` — a cached `(price, confidence, timestamp)` tuple from the most recent instruction that consumed the Bank's oracle. Scryer's `marginfi/reserves/v1` snapshot preserves these as columns. This collapses the §6 #4 Switchboard-crank-staleness analysis from "build an oracle-tape join" to "filter `cache_last_oracle_price_timestamp` in `marginfi_reserve.v1`." See §6 #4 below.

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
| Confidence-interval haircut works as a real risk gate during off-hours. | **TODO when `marginfi/liquidations/v1` lands.** Cross-reference Pyth `pyth_conf` widening on weekends with marginfi liquidation events on weekends; show whether the haircut absorbs the realised move (good) or only marginally widens before the buffer is exhausted (bad). The §1.6 `BankCache.last_oracle_price` panel already carries the per-Bank cached `(price, conf, timestamp)` for general-lending analysis; the haircut-vs-realised-move scoring still requires the events panel. | **TODO (deployment-substrate evidence; cross-protocol confirmation, not the xStock-specific empirical claim)** |
| MarginFi has higher xStock-adjacent liquidation activity than Kamino. | **Empirically wrong.** Was inferred from a 30-day Kamino-xStocks zero-event scan. Scryer's 2026-05-01 verification: (a) Kamino has a 9-month liquidation panel with 102 events (`scryer/dataset/kamino/liquidations/v1/`) including a Nov 2025 cluster; (b) MarginFi has zero direct xStock Banks among 422 production Banks — xStock exposure on MarginFi is indirect-only via `KaminoPythPush` / `KaminoSwitchboardPull` routes (§1.5). MarginFi xStock-adjacent liquidations are downstream re-emissions of Kamino-position events, not an independent panel. | **closed: the original premise was a 30-day-sample artifact. xStock empirical home is Kamino-xStocks; MarginFi adds cross-protocol confirmation, not an independent panel.** |

---

## 4. Market action / consumer impact

### 4.1 Why MarginFi matters for Paper 3 (reconciled 2026-05-01)

The 2026-04-29 draft of this section claimed MarginFi was *the* load-bearing event source for Paper 3 because a 30-day Kamino-xStocks scan found zero events. Scryer's 2026-05-01 verification reframes both halves of that argument:

1. **Kamino-xStocks is not empirically empty.** The 30-day-zero finding was a sampling artifact. The 9-month Kamino liquidation panel at `scryer/dataset/kamino/liquidations/v1/` carries 102 events with a structural cluster 2025-11-04 → 2025-11-21 (8 events / 18 days, 7% of panel). The xStock-specific empirical event panel for Paper 3 lives there.

2. **MarginFi has no direct xStock Banks (§1.5).** xStock exposure on MarginFi is indirect-only via `KaminoPythPush` and `KaminoSwitchboardPull` routes; events surfaced on those Banks are downstream re-emissions of Kamino-position events, not independent observations.

The reconciled role of MarginFi for Paper 3 is therefore:

- **Deployment substrate (general lending; §4.2)** — MarginFi-v2's `assets use P − conf, liabilities use P + conf` haircut rule is structurally compatible with soothsayer's `(lower, upper)` band as a one-line substitution. This argument applies to MarginFi's general-lending book (mostly crypto-collateral) and is the strongest *deployment-shape* argument for MarginFi-as-design-partner. It does not depend on direct xStock listings.
- **Cross-protocol confirmation (gated on `marginfi/liquidations/v1`)** — once the events panel lands, MarginFi events on `KaminoPythPush` / `KaminoSwitchboardPull` Banks can be joined back to upstream Kamino-position events to characterize the *propagation* of an oracle-staleness event across the lending stack. This is a sharper finding than "MarginFi vs Kamino as parallel comparators" because it speaks to systemic risk, not venue choice.
- **Not the xStock-specific empirical home for Paper 3.** That role belongs to Kamino-xStocks, on the 9-month panel referenced above.

### 4.2 Downstream-of-oracle impact (where soothsayer's served band could plausibly change a MarginFi outcome)

- **Pyth-wired MarginFi banks** — if soothsayer's served band were available as a MarginFi-readable oracle source, the conf-haircut rule (`P - conf` for assets, `P + conf` for liabilities) is structurally compatible with reading a calibrated band's `(lower, upper)` directly. The substitution is one-line: `P - conf → lower`, `P + conf → upper`. Paper 3 §6 / §7 should explicitly compare `pyth_conf`-haircut vs `soothsayer_band`-haircut on the realised liquidation panel.
- **Switchboard-wired MarginFi banks** — Switchboard publishes via `OracleJob` pipeline; soothsayer could publish a `OracleJob` that returns a calibrated band. The `pyth_conf`-vs-soothsayer reconciliation extends naturally.
- **Fixed-price banks** — these are typically pegged-asset banks (e.g., USDC, USDT); soothsayer is structurally not a comparator here.

### 4.3 OEV / liquidation-rent tie-in

MarginFi liquidations join with Jito bundles and (potentially) Pyth Express Relay auctions to form the OEV story Paper 3's wider scope is interested in. Once `marginfi/liquidations/v1` and `jito/bundles/v1` exist scryer-side, the join is a one-liner; today, the surface is empty.

### 4.4 Other consumers worth comparing in §4 (non-Kamino enforcement)

To honour the INDEX rule that §4 must cite a non-Kamino consumer: **MarginFi is the non-Kamino consumer in this file by construction.** Even with the 2026-05-01 reframing — where MarginFi xStock exposure is indirect via Kamino-position oracle routes — MarginFi's general-lending book remains a non-Kamino consumer (the deployment-substitution argument in §4.2 doesn't require direct xStock listings). The wider-than-Kamino discipline is preserved at the protocol layer; the xStock-event-panel layer happens to have structural asymmetry, which is itself a paper finding.

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

1. ~~**Exact mainnet program ID for marginfi-v2.**~~ **Closed 2026-05-01.** Verified by scryer's IDL pin against on-chain `getAccountInfo`: the canonical mainnet program ID is `MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA`. The address `MFv2hWf31Z4i1g2AhULZWnuwvvfuBQg4P4HFcXyFZi5` cited in the prior draft (and in some public ecosystem references) does not exist on mainnet. The header verification block carries the corrected address.
2. ~~**Are any xStock SPL tokens listed as collateral or borrow assets in any marginfi-v2 Group?**~~ **Closed 2026-05-01: indirect-only.** Scryer's 422-Bank scan found zero direct xStock SPL-token Banks. xStock exposure exists only via `KaminoPythPush` / `KaminoSwitchboardPull` `OracleSetup` routes (Kamino-position banks delegating their oracle read). See §1.5. Strategic implication for Paper 3: the xStock-specific empirical event panel is Kamino-xStocks, not MarginFi; MarginFi's role is deployment substrate (general lending) + cross-protocol confirmation, not parallel xStock event source.
3. **Liquidation-trigger formal condition.** Health-threshold formula and the exact trigger condition (`maintenance health factor < 1.0`?). **Gating:** IDL fetch + bank-config field decode.
4. ~~**Switchboard crank cadence on production banks during weekends.**~~ **Reframed 2026-05-01: free panel via `BankCache.last_oracle_price`.** Each Bank's cached `(price, conf, timestamp)` from the most recent oracle-consuming instruction is now a column in `marginfi/reserves/v1` (see §1.6). The analysis collapses from "build oracle-tape join" to "filter `cache_last_oracle_price_timestamp`" segmented by `OracleSetup` variant — a substantial scope reduction. **Gating:** none data-side; analysis pending.
5. **Insurance-fund socialisation.** Does the insurance fund explicitly absorb bad debt (no socialisation across banks/users), or does it socialise via reserve dilution? **Gating:** README + governance forum search.
6. ~~**Liquidator fee distribution across banks.**~~ **Closed 2026-05-01: not per-Bank.** Scryer's IDL-level verification: liquidation fees (`liquidation_max_fee`, `liquidation_flat_sol_fee`) live in the global `FeeState` account, not per-Bank. Per-Bank fee variation is restricted to IR-tier fees (`insurance_fee_fixed_apr`, `insurance_ir_fee`, etc., already captured in `marginfi/reserves/v1`). The liquidator-fee histogram across Banks is therefore a one-row global question; the per-Bank variation that prior draft framed as empirically open does not exist.
7. **Whether the conf-haircut is bypassable.** Some MarginFi-style protocols offer a bypass for "trusted" oracles (e.g., Fixed-price banks). Whether any non-trivial bank has the haircut effectively disabled is risk-relevant. **Gating:** snapshot review on `marginfi/reserves/v1`.
8. **Does Chainlink v11 land as a marginfi-v2 supported oracle in the future?** Currently not supported per the README. If/when it does, the synthetic-marker finding in [`oracles/chainlink_v11.md`](../oracles/chainlink_v11.md) §3 becomes directly relevant to MarginFi liquidation outcomes.
9. **Is `marginfi/liquidations/v1` worth historical-scrape-prioritising?** The xStock-empirical-home reframe (§1.5) makes a MarginFi liquidations panel cross-protocol-confirmation rather than load-bearing. The decision is whether the deployment-substrate evidence (does the conf-haircut absorb realised moves on the general book?) is worth the historical-scrape cost now, or whether forward-accumulation is sufficient. **Gating:** decision sits with scryer wishlist prioritisation.

---

## 7. Citations

- [`marginfi-v2-readme`] mrgnlabs. *marginfi-v2 README*. https://github.com/mrgnlabs/marginfi-v2. Accessed: 2026-04-29.
- [`marginfi-docs-intro`] mrgnlabs. *marginfi documentation* (introduction). https://docs.marginfi.com/. Accessed: 2026-04-29.
- [`kamino-liquidations-first-scan`] Soothsayer internal. [`reports/kamino_liquidations_first_scan.md`](../../../reports/kamino_liquidations_first_scan.md). Source of the load-bearing-event-source finding (Kamino-xStocks 30-day = 0 events; MarginFi is the next-density source).
- [`coindesk-redstone-weekend`] Cited indirectly via [`docs/sources/oracles/redstone_live.md`](../oracles/redstone_live.md) §1.1; the weekend-gap industry framing is consistent with MarginFi's exposure on equity-class banks if any are added in future.
- [`pyth-regular-reconciliation`] Soothsayer internal. [`docs/sources/oracles/pyth_regular.md`](../oracles/pyth_regular.md). The publisher-dispersion-vs-coverage-SLA reconciliation that directly informs MarginFi's `P ± conf` haircut behavior at off-hours.
