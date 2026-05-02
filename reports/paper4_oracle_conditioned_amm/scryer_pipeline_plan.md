# Paper 4 — Scryer pipeline plan

**Status:** planning document (internal). Drafted 2026-05-01; reconciled 2026-05-01 against scryer phase 77 (schemas + methodology row + wishlist item 51 already locked).
**Owner:** Adam (data-engineering hand-off lives in scryer; this doc is the consumer-side spec for what soothsayer needs from scryer to back Paper 4 and the product decisions in `docs/product-stack.md`).
**Read first:** `reports/paper4_oracle_conditioned_amm/plan.md` §10 (existing artefact reuse), §16 (product-stack relationship), `docs/product-stack.md` (pipeline-reuse argument), and the live scryer wishlist at `../scryer/wishlist.md` item 51.

## 1) One-line scope

**Identify the scryer venues + data_types we need running *now* — not at Paper 4 Phase A kickoff — so that the panel period for Paper 4's empirical foundation begins accumulating today, and so that the same pipelines simultaneously inform product decisions for Layers 1–4 of the product stack.**

The binding constraint is *calendar time*. Every week without a forward tape is a week missing from the panel — and three of the four required schemas (`jito_bundle_tape.v1`, `validator_client.v1`, both pool-state schemas) are forward-only-capturable; backfill is impossible past short public-history horizons.

## 2) Status of the input set

### 2a) Live in scryer today (no action needed beyond keeping daemons running)

Verified against `/Users/adamnoonan/Library/Application Support/scryer/dataset/` on 2026-05-01:

| Venue | data_type | Schema | Use in Paper 4 |
|---|---|---|---|
| `pyth` | `oracle_tape` | `pyth.v1` | B1 baseline (Pyth-anchored CLMM); `(P, conf)` per-slot |
| `chainlink_data_streams` | `report_tape` | `chainlink_data_streams.v1` | Closed-market reference cross-validation (v10 `tokenizedPrice` + v11 fields) |
| `redstone` | `oracle_tape` | `redstone.v1` | Closed-market reference cross-validation (SPY/QQQ/MSTR only) |
| `kamino_scope` | `oracle_tape` | `kamino_scope.v1` | Kamino-side oracle path; informs Paper 3 cross-references |
| `soothsayer_v5` | `tape` | `v5_tape.v1` | The oracle's own derived band tape — the Plugin's input |
| `geckoterminal` | `trades` | `geckoterminal.v1` | High-level RWA-pool trade signal; cross-validates the on-chain reconstructor |
| `kraken` | `funding` | `kraken_funding.v1` | xStock-perp funding-rate ground truth |
| `cme` | `intraday_1m` | `cme_intraday_1m.v1` | Continuous off-hours equity reference (ES/NQ/GC/ZN futures) |
| `nasdaq` | `halts` | `nasdaq_halts.v1` | Halt confounder labels for the regime decomposition |
| `backed` | `corp_actions`, `nav_strikes` | `backed.v1`, `backed_nav_strikes.v1` | Corp-action confounder filter on the underlier panel |
| `yahoo` | `equities_daily`, `earnings`, `corp_actions` | `yahoo.v1`, `earnings.v1`, `yahoo_corp_actions.v1` | Daily underlier reference + earnings-event confounder filter |
| `solana_dex` | `xstock_swaps` | `dex_xstock_swaps.v1` | DEX swap-IX tape for xStock pools (Orca + Meteora + Phoenix + Raydium CLMM); shipped phase 36 |

### 2b) Schemas + methodology already locked for Paper 4 Phase A (scryer wishlist item 51, methodology row 2026-05-01)

Phase 77 landed the methodology row in `scryer/methodology_log.md` ("Paper-4 Phase-A capture spec — slot-resolution xStock AMM panel — 2026-05-01 (locked)") plus four schema specs in `scryer/docs/schemas.md` plus the corresponding `scryer-schema` modules. The schemas are:

| Schema | Purpose | Storage path | Backfillable? |
|---|---|---|---|
| `clmm_pool_state.v1` | Per-(pool, slot) Whirlpool + Raydium CLMM tick-state | `dataset/solana_dex/clmm_pool_state/v1/dex={orca_whirlpools\|raydium_clmm}/...` | **No — forward-only** (replay from swap tape would dominate cost) |
| `dlmm_pool_state.v1` | Per-(pool, slot) Meteora DLMM bin-state (sibling schema, not a column-superset of CLMM) | `dataset/solana_dex/dlmm_pool_state/v1/...` | **No — forward-only** |
| `jito_bundle_tape.v1` | Per-bundle slot-keyed tape from Block Engine API | `dataset/jito/bundle_tape/v1/...` | **No — forward-only past Jito's history horizon** |
| `validator_client.v1` | Per-epoch leader→client-family mapping (`getVersion` cross-checked against community labeller) | `dataset/solana_validator/client_label/v1/...` | **No — forward-only past labeller's public-history horizon** |

**Mint allowlist (locked).** SPYx, QQQx, AAPLx, GOOGLx, NVDAx, TSLAx, HOODx, MSTRx — the 8 xStock mints in `src/soothsayer/universe.py`. GLDx and TLTx admissible if Backed lists them during the panel; amendment lands as a follow-up methodology row.

What's *not* locked: Geyser provider choice (Helius vs Triton vs Yellowstone vs operator-run node) — per scryer hard rule #5, this is a proxy/operational decision that lands in the per-fetcher methodology row when the crate ships.

### 2c) Outstanding fetcher work (scryer wishlist item 51 sub-items)

Code-level work that ships as separate phases per the capture-order rationale in the methodology row:

| Sub-item | Schema(s) | Effort | Why it's the priority order it is |
|---|---|---|---|
| **51a** — `jito_bundle_tape.v1` forward-poll daemon | `jito_bundle_tape.v1` | ~4–6 h | **Highest urgency.** Jito's bundle history is finite; every day deferred is unrecoverable data loss. |
| **51b** — `validator_client.v1` per-epoch refresh | `validator_client.v1` | ~6–8 h | Same urgency tier as 51a — forward-only past labeller's horizon. |
| **51c** — `clmm_pool_state.v1` forward-capture (Whirlpool + Raydium CLMM) | `clmm_pool_state.v1` | ~6–9 h (combined with 51d ~12–18 h) | Forward-capture is materially cheaper than swap-replay; deferral cost grows linearly, not catastrophically — P0 but a tier below 51a/51b. |
| **51d** — `dlmm_pool_state.v1` forward-capture (Meteora DLMM) | `dlmm_pool_state.v1` | ~6–9 h | Lands together with 51c if Geyser surface accepts program multiplexing cleanly; otherwise as a follow-up phase. |
| **51e** — `dex_xstock_swaps.v1` backfill-range tightening + forward-poll plist | `dex_xstock_swaps.v1` (no schema/code change) | ~2–3 h | Promotes phase-36 code to data-shipped: backfill `[2025-07-14, forward-cursor)` + new launchd plist mirroring `geckoterminal-trades.plist` at ≤900s cadence. |

**Total effort: ~24–35 engineer-hours.** Realistic wall-clock to all five tapes shipping: ~1 week of focused work, plus operator-side run time for the 51e backfill.

### 2d) Outstanding operator action — historical backfills already coded (scryer wishlist 49a–d)

Inputs to Paper 4's regime decomposition that already exist as code, awaiting operator triggers:

- **49a** — Pyth Hermes ≥90d backfill. Code shipped phase 71. ~9h wall-clock at 4 req/s.
- **49b** — Kamino Scope ≥90d. RPC retention is binding constraint; paid Helius tier required and authorized.
- **49c** — RedStone permaweb ≥90d. Arweave GraphQL replay; no rate ceiling.
- **49d** — Chainlink Data Streams ≥90d. Same RPC-retention pattern as 49b.

These are independent of item 51 and can be triggered now.

### 2e) Cross-paper utility — already-Priority-0 scryer items that benefit Paper 4

- **Item 47 — `marginfi_liquidation.v1`**. Priority 0 in the scryer wishlist for Paper 3. Cross-utility: Paper 4's bundle-join key reads both the AMM swap tape (`dex_xstock_swaps.v1`) and the lending-liquidation tape (item 47) to compute the cross-protocol slot-level OEV picture. Standing item 47 up benefits Paper 4 even though it's gated on Paper 3.

## 3) Priority order — what to start now

**Headline:** the schemas, methodology, and wishlist drafting are *already done* in scryer. The remaining work is fetcher implementation (51a–51e, ~1 week) plus operator-side runs (49a–d). Nothing in this plan asks scryer to file new wishlist items.

### P0 (start this week — every day deferred = data loss for the forward-only schemas)

1. **51a** — Jito bundle-tape forward-poll daemon. Single REST endpoint; pattern matches phase-23 Pyth tape.
2. **51b** — Validator-client per-epoch refresh. Two-source join (`getVersion` + community labeller) with `unknown` on disagreement.
3. **49a–d operator triggers** — fire the four backfills in parallel; they run independently.

### P0.5 (next, ~T+1 week)

4. **51c + 51d** — CLMM + DLMM forward-capture. New `scryer-fetch-solana-pool-state` crate is the architecture surface; Geyser provider lock lands in the per-fetcher methodology row.
5. **51e** — `dex_xstock_swaps.v1` backfill `[2025-07-14, forward-cursor)` + forward-poll plist.

### P1 (post-fetcher-set landing, ~T+2 weeks)

6. **Item 47** — `marginfi_liquidation.v1`. Already Priority 0 in scryer for Paper 3; landing it adds the lending-side leg of the Paper 4 bundle-join.

### P2 (consumer-side, soothsayer repo)

These are *not* scryer pipelines — soothsayer-side analytics that read the scryer parquet:

- **P2.1 Per-slot pool-state reconstructor.** Reads `solana_dex/clmm_pool_state` + `solana_dex/dlmm_pool_state`, denormalizes to canonical pool state at any slot. Lives in `src/soothsayer/sources/solana_dex.py`. Effort ~1 week per venue family once schemas have rows.
- **P2.2 Path-aware truth labeller.** For each closed-market window, computes worst executable price at next venue open from the in-market reference tape (Pyth + CME 1m). Lives in `src/soothsayer/backtest/path_aware_truth.py`. Effort ~1 week.
- **P2.3 Counterfactual replay engine.** Replays the historical panel under B0/B1/B2/B3 mechanisms. Effort ~3–4 weeks (the largest soothsayer-side build).
- **P2.4 Bundle-attribution → RWA-pool LVR labels.** Joins `jito/bundle_tape` to `solana_dex/xstock_swaps` on `signature` + cross-references `solana_validator/client_label` for the BAM-vs-non-BAM stratification. Effort ~1 week.

## 4) Total wall-clock to a Paper-4-Phase-A-ready panel

Reconciled against scryer phase 77 — significantly faster than the original draft because the schemas + methodology are already locked:

| Milestone | Wall-clock from today |
|---|---|
| 49a–d operator triggers fired | T+0–2 days |
| 51a–51b shipping forward tapes (`jito_bundle_tape`, `validator_client`) | T+1 week |
| 51c + 51d shipping forward tapes (CLMM + DLMM pool state) | T+1.5 weeks |
| 51e backfill complete + forward-poll plist running | T+2 weeks |
| Item 47 (`marginfi_liquidation`) shipping | T+3 weeks |
| Soothsayer-side P2 consumers (pool-state reconstructor, truth labeller, attribution joiner) | T+6 weeks |
| Forward tapes accumulating ≥6 months for Phase A | T+6 months from forward-tape start |
| **Paper 4 Phase A panel ready** | **~T+6.5 months from today** |

This is consistent with the existing plan §12 timeline ("post-grant Milestone 4 → Phase A begins → ~6–9 months data") and slightly faster than the §12 estimate because Phase A formally begins when fetchers ship, not when the grant Milestone 4 lands.

## 5) What this plan deliberately does not include

- **Solana program-level execution traces.** Inner-instruction decoding for non-AMM programs is out of scope at v1. If a swap routes through Jupiter, we capture the leg at the AMM venue level via `dex_xstock_swaps.v1`; we do not reconstruct the Jupiter route.
- **xStock-equivalent CEX *spot* tape.** xStock-equivalent CEX *perp* tape exists (item 45, phases 55–58) and covers the 24/7 reference. CEX-listed equity *spot* would be Priority 3.
- **NYSE / NASDAQ TAQ-level in-market reference.** Paid data, large licensing cost. The CME 1m futures tape (already live) is the in-market reference proxy.
- **Solver / RFQ venue tapes.** Conceptually relevant for Layer 4 (settlement/index licensing) but not for Paper 4's mechanism evaluation. Defer.

## 6) Open questions resolved by scryer methodology row

The questions I flagged in the original draft are mostly already answered:

- **~~Should `jito_bundle_tape.v1` capture failed/dropped bundles as well as landed?~~** — Resolved by schema: `landed: bool` column captures both states. Searcher tip is recorded for both.
- **~~Pool-state cadence: every-slot vs every-state-change?~~** — Resolved: per-slot ideal, 60s floor (Geyser stream + polled fallback). The schema's `_dedup_key = (pool_pubkey, slot)` makes every-slot the natural unit; the 60s polled fallback is the floor when the subscription stream is unavailable.
- **~~Validator client labelling: live-only or also historical?~~** — Resolved by reproducibility caveat: forward-only past labeller's public-history horizon. Phase-log row at forward-poll launch records the start timestamp; pre-start data is missing-by-construction.
- **~~xStock universe for the AMM tape filter: same as the oracle universe (10) or broader?~~** — Resolved by mint allowlist: 8 xStocks (no GLDx/TLTx until Backed lists; amendment shape pre-specified). Broader is gated on a methodology-row amendment, not a schema change.

Open questions that *remain*:

1. **Geyser provider choice** (51c/51d). Helius vs Triton vs Yellowstone vs operator-run. Lands in the per-fetcher methodology row when the crate ships, per scryer hard rule #5. Soothsayer-side preference is whichever offers the lowest end-to-end latency on the xStock-pool subscription set; not a soothsayer decision to make.
2. **`getVersion`-vs-community-labeller disagreement rate** is itself a Phase-A diagnostic (per plan §11 R4). If the rate is > 20% the BAM-vs-non-BAM stratification weakens; not a blocker but worth measuring early.
3. **Cross-DEX field nomenclature** for CLMM is normalized to `0/1` at decode time per the schema. Soothsayer-side consumer code should mirror that; document in `src/soothsayer/sources/solana_dex.py` when written.

## 7) See also

- `reports/paper4_oracle_conditioned_amm/plan.md` — the paper plan; §10 lists the consumer-side artefacts these pipelines feed.
- `docs/product-stack.md` — the four-layer product picture this plan's pipelines simultaneously inform.
- `../scryer/wishlist.md` item 51 — the canonical fetcher work order; this doc is the consumer-side mirror.
- `../scryer/methodology_log.md` "Paper-4 Phase-A capture spec — slot-resolution xStock AMM panel — 2026-05-01" — the locked methodology row.
- `../scryer/docs/schemas.md` — schema specs for `clmm_pool_state.v1`, `dlmm_pool_state.v1`, `jito_bundle_tape.v1`, `validator_client.v1`, `dex_xstock_swaps.v1`.
- `reports/paper3_liquidation_policy/plan.md` §11 — Paper 3 reuses item 47 + the Jito bundle pipeline.
