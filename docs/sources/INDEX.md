# `docs/sources/` — Index

Per-venue methodology-vs-observed reconciliation files. Each file follows the canonical structure in [`_template.md`](_template.md): stated methodology, observable signals in our scryer tape, side-by-side reconciliation, downstream consumer impact, known confusions, open questions, citations.

This index is the lookup. Pin your read by **venue + version** here so you don't end up cross-referencing the wrong schema (the v10/v11 trap).

For the budget / access / licensing catalog see [`../data-sources.md`](../data-sources.md). That file is a ledger of *what we pay for and where it lives*; this directory is *what each venue actually does and how it lines up against our tape*.

---

## How to use this directory

- **Find a venue:** scan the role-grouped tables below; click through to the file.
- **Add a venue:** copy [`_template.md`](_template.md) to the right sub-directory, fill in all 7 sections, then add the row here.
- **Schema fork:** when a venue ships a breaking schema change, add a *new* file (e.g., `chainlink_v12.md`). Don't overwrite the old one — past calibration runs still depend on the old wire format.
- **Status legend:**
  - `✅ live` — file written, reconciliation grounded in our tape.
  - `🚧 draft` — file exists but §3/§4 still has TODOs.
  - `📋 planned` — listed but not yet written.
  - `❌ wontfix` — file will not be written; reason in the table.

---

## Oracles (price feeds we observe or could publish through)

| File | Version pin | Role | Status |
|---|---|---|---|
| [`oracles/chainlink_v11.md`](oracles/chainlink_v11.md) | `v11` (24/5 RWA schema, live Jan 2026) | comparator | ✅ live |
| [`oracles/chainlink_v10.md`](oracles/chainlink_v10.md) | `v10` (legacy RWA schema, pre-2025-Q4) | historical reference + comparator | ✅ live |
| [`oracles/chainlink_data_streams.md`](oracles/chainlink_data_streams.md) | Streams API surface | transport layer | ✅ live |
| [`oracles/pyth_regular.md`](oracles/pyth_regular.md) | Aggregation v2 (current) | comparator (first-class) | ✅ live |
| [`oracles/pyth_pull.md`](oracles/pyth_pull.md) | Wormhole-bridged PriceUpdate | comparator | 🚧 draft |
| [`oracles/pyth_lazer.md`](oracles/pyth_lazer.md) | Pyth Pro (formerly Lazer) / Blue Ocean ATS path | comparator (24/5 equity) | 🚧 draft |
| [`oracles/pyth_express_relay.md`](oracles/pyth_express_relay.md) | PER OEV auction program `PytERJFhAKuNNuaiXkApLfWzwNwSNDACpigT3LwQfou` | OEV-mechanism reference | 🚧 draft |
| [`oracles/redstone_live.md`](oracles/redstone_live.md) | Live REST gateway (post-Mar 2026) | comparator | ✅ live |
| [`oracles/redstone_classic.md`](oracles/redstone_classic.md) | Classic Push model (EVM-only) | comparator (cross-chain) | 🚧 draft |
| [`oracles/switchboard_ondemand.md`](oracles/switchboard_ondemand.md) | On-Demand `PullFeed` + `OracleJob` (programs `SW1TCH7…` / `sbattyXr…`) | publishing surface candidate | 🚧 draft |
| [`oracles/scope.md`](oracles/scope.md) | Kamino in-house aggregator (program `HFn8GnPADiny6XqUoWE8uRPPxb29ikn4yTuPa9MF2fWJ`) | consumer's primary oracle | ✅ live |
| [`oracles/stork.md`](oracles/stork.md) | Solana RWA stack | comparator | 🚧 draft |

## DEXs (on-chain execution venues that could anchor Solana fair value)

| File | Version pin | Role | Status |
|---|---|---|---|
| [`dexs/jupiter_router.md`](dexs/jupiter_router.md) | Jupiter v6 router | on-chain mid + execution | 📋 planned |
| [`dexs/orca_clmm.md`](dexs/orca_clmm.md) | Whirlpools | execution | 📋 planned |
| [`dexs/raydium_clmm.md`](dexs/raydium_clmm.md) | Raydium CLMM | execution | 📋 planned |
| [`dexs/meteora_dlmm.md`](dexs/meteora_dlmm.md) | Dynamic LMM | execution | 📋 planned |
| [`dexs/phoenix_orderbook.md`](dexs/phoenix_orderbook.md) | Orderbook DEX | execution | 📋 planned |
| [`dexs/geckoterminal.md`](dexs/geckoterminal.md) | aggregator we already consume | observation input | 📋 planned |

## Perps (continuous-quoting venues for closed-market signals)

| File | Version pin | Role | Status |
|---|---|---|---|
| [`perps/kraken_futures_xstocks.md`](perps/kraken_futures_xstocks.md) | 10 xStock perps, **1h funding (not 8h — see file §1.2)**, ±0.25%/h cap | comparator (off-hours signal) | ✅ live |
| [`perps/drift_perps.md`](perps/drift_perps.md) | Drift v2 (no xStock perps as of 2026-04-29; mechanism reference) | comparator | 🚧 draft |
| [`perps/hyperliquid_perps.md`](perps/hyperliquid_perps.md) | Hyperliquid mainnet (crypto-only; non-Solana) | comparator | 🚧 draft |
| [`perps/gate_io_stock_perps.md`](perps/gate_io_stock_perps.md) | xStock-backed (12 X-suffix + 4 plain); only TLT-perp venue | comparator | 🚧 draft |
| [`perps/htx_stock_perps.md`](perps/htx_stock_perps.md) | xStock-backed (6 X-suffix + 9 plain) | comparator | 🚧 draft |
| [`perps/bingx_phemex_stock_perps.md`](perps/bingx_phemex_stock_perps.md) | xStock-backed (BingX 3 X + 13 NCSK; Phemex 1 X + 12 plain) | comparator | 🚧 draft |

## Lending (downstream consumer protocols Paper 3 must reason about)

| File | Version pin | Role | Status |
|---|---|---|---|
| [`lending/marginfi.md`](lending/marginfi.md) | marginfi-v2 | consumer target (Paper 3 load-bearing) | ✅ live |
| [`lending/kamino_klend.md`](lending/kamino_klend.md) | klend v1.19.0 | consumer target | 📋 planned |
| [`lending/drift_lending.md`](lending/drift_lending.md) | Drift v2 lending | consumer target | 📋 planned |
| [`lending/jupiter_lend_fluid.md`](lending/jupiter_lend_fluid.md) | Fluid Vaults | consumer target | 📋 planned |
| [`lending/save_solend.md`](lending/save_solend.md) | Save (formerly Solend) | consumer target | 📋 planned |
| [`lending/loopscale.md`](lending/loopscale.md) | Loopscale | consumer target | 📋 planned |

## Issuers (NAV / proof-of-reserves ground truth)

| File | Version pin | Role | Status |
|---|---|---|---|
| [`issuers/backed_xstocks.md`](issuers/backed_xstocks.md) | xStocks bearer-bond structure | issuer ground truth | 📋 planned |
| [`issuers/ondo_ousg_usdy.md`](issuers/ondo_ousg_usdy.md) | OUSG / USDY | issuer ground truth | 📋 planned |
| [`issuers/securitize_buidl.md`](issuers/securitize_buidl.md) | BUIDL distribution | issuer ground truth | 📋 planned |

## TradFi context (closed-market reference inputs)

| File | Version pin | Role | Status |
|---|---|---|---|
| [`tradfi/nasdaq_halts.md`](tradfi/nasdaq_halts.md) | Nasdaq halt-code XML | regime input | 📋 planned |
| [`tradfi/fred.md`](tradfi/fred.md) | FRED macro events | regime input | 📋 planned |
| [`tradfi/yahoo_v_databento.md`](tradfi/yahoo_v_databento.md) | free Yahoo vs paid tick | data-quality reference | 📋 planned |

---

## Discipline rules for this directory

1. **Version-pin or fork.** Never silently overwrite an `_v11.md` to describe v12. Add `_v12.md` and update this index. The old file stays as the contract our historical tape was decoded against.
2. **§4 must cite a non-Kamino consumer** before a file is `✅ live`. Soothsayer is a wider-than-Kamino oracle play; if every reconciliation chains back to Klend, the doc set silently re-Kamino-ifies the project.
3. **`Last verified` is mandatory** on every file and re-stamped on every substantive edit.
4. **Open questions are append-only.** When §6 entries resolve, mark them resolved + link to the §3 row that absorbed the answer; don't delete.
5. **Don't fetch market data from this directory.** Per `CLAUDE.md` hard rule #1, only public docs (`WebFetch`) and existing scryer parquet should be touched. New data needs go in `scryer/wishlist.md`.
6. **Two coverage rules** for whether a file should be `✅ live` rather than `🚧 draft`:
   - §3 has at least one numerical reconciliation grounded in our tape (not just docs-only paraphrase).
   - §4 names at least one consumer, with the impact backed by either a scryer query result or an explicit `TODO when scryer item N lands` pointer.

---

*Index version: 1.0 (2026-04-29). Add rows when files land; never delete rows.*
