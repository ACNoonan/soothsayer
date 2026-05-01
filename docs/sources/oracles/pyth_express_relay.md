# `Pyth Express Relay (PER)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.pyth.network/express-relay` (accessed 2026-04-29; introduction page present, top-level overview clear, deep "How Express Relay Works" page returned 404 in our probe wave — link rot noted), `https://www.pyth.network/blog/express-relay-priority-auctions` (the original Express Relay blog post; cited via search results), `https://forum.pyth.network/t/passed-op-pip-54-upgrade-the-pyth-express-relay-program-on-solana/1977` (Pyth DAO PIP-54, accessed 2026-04-29; the load-bearing source for program ID, instruction structure, and fee mechanics), `https://forum.pyth.network/t/passed-op-pip-106-upgrade-the-pyth-express-relay-program-on-solana-to-add-an-spl-token-withdrawal-instruction/2490` (PIP-106; latest known on-chain-program upgrade), `https://www.pyth.network/success-stories/kamino` (Kamino integration writeup; not directly accessed today but cited via search-result excerpt).
**Version pin:** **Express Relay Solana program `PytERJFhAKuNNuaiXkApLfWzwNwSNDACpigT3LwQfou`**, version commit `00940ec5d4c6cb8c2c23870daa98bdf1ece14680` per PIP-54 (passed; semver not explicit), with PIP-106 layering the SPL-token-withdrawal instruction. Off-chain auction infrastructure (`opportunity server`) is the relayer's; on-chain settlement is via the program above.
**Role in soothsayer stack:** `OEV-mechanism reference` — Express Relay is the **only Solana-native deployed OEV auction** (per [`docs/data-sources.md`](../../data-sources.md) §7 line 184 and §9 line 261). Paper 3's wider scope on liquidation-policy + OEV-recapture turns on whether liquidations clear through PER (and what fraction of the recovered OEV the protocol vs. the searcher captures). Soothsayer is **not a publisher** to PER; PER is downstream of Pyth's price publication and uses Pyth feeds to compute auction-eligible opportunities. The relevance is the **mechanism**: PER is the canonical example of "publish a price + auction the right to act on it" that Paper 3 references when comparing protocol-level OEV policies.
**Schema in scryer:** **planned, not yet shipped.** Target dataset: `dataset/pyth_express_relay/auction_tape/v1/...` per [`docs/data-sources.md`](../../data-sources.md) §11 line 314 ("Pyth Express Relay auction tape — 📋 planned"). Not currently in `scryer/wishlist.md` Priority 0–4 buckets explicitly, but is a Paper-3-load-bearing target. **Hand-off:** add to `scryer/wishlist.md` as a Priority-1 candidate alongside `kamino_liquidation.v1` (item 1) and `jupiter_lend_liquidation.v1` (item 2) — the three datasets join at the (auction event, liquidation event) level for the Paper-3 OEV-recapture-rate measurement.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule (auction-mechanism rule)

Express Relay is **not a price aggregator** — it is a **priority auction** layered on top of Pyth's price publication. Its responsibility is sequencing the *acts* downstream of a price update: liquidation transactions, swap fills, and other operations whose value depends on a price the auction participants are reading from a Pyth feed.

Per the Pyth Express Relay introduction page (accessed 2026-04-29): "a priority auction which enables better orderflow mechanisms that eliminate [MEV]." Per the Pyth blog: "isolated priority auctions allowing searchers to compete for priority to perform lucrative operations (such as liquidations) on the integrated DeFi protocols."

The auction lifecycle, per Pyth's blog + PIP-54:

1. **Opportunity exposure.** A DeFi protocol exposes a liquidation/swap/etc. opportunity to integrated searchers via the **opportunity server** operated by the relayer. The opportunity carries the parameters (account to liquidate, repay amount, collateral seizure constraints, etc.) plus a deadline.
2. **Off-chain auction.** Searchers submit competing offers (bids) to the opportunity server. The auction is **off-chain** — the relayer collects bids and selects the winner. The bid amount is what the searcher pays the protocol on top of executing the underlying operation.
3. **On-chain settlement.** The winning searcher's transaction is submitted on-chain via the Express Relay program (`PytERJFhAKuNNuaiXkApLfWzwNwSNDACpigT3LwQfou`). The program acts as an **entry point** that permissions the searcher's interaction with the integrated DeFi protocol and enforces payment of the offered bid.
4. **Fee distribution (per PIP-54).** Two fees apply to swaps (the same pattern extends to liquidations):
   - **Referral fee** — set by the integrating protocol.
   - **Platform fee** — set by the Pyth DAO; initially 0 bps. Of the platform fee, **6% to relayer, 94% to DAO**.

### 1.2 Cadence / publication schedule

PER's cadence is **event-driven** — auctions trigger when a protocol exposes an opportunity (e.g., a liquidatable position, a fillable swap intent). There is no fixed publication cadence. The auction's **deadline** parameter (per PIP-54: the `swap` instruction includes a deadline so "searchers can know for how long their quote might be valid") gates the time window for bids.

For liquidations specifically, the cadence is bounded by the underlying Pyth feed cadence — a position becomes liquidatable when Pyth's price update crosses the position's health threshold; the opportunity server exposes the resulting liquidation-eligibility within milliseconds. The relayer's opportunity-server latency (off-chain bid collection) plus Solana block time (on-chain settlement) bound the sub-second auction-to-settlement window.

### 1.3 Fallback / degraded behavior

- **Opportunity-server unavailability.** If the relayer's opportunity server is down, no auctions occur — protocol opportunities default to whatever non-PER fallback the protocol implements (typically: open mempool / public RPC liquidation, where MEV is captured by the validator/builder rather than the protocol).
- **No winning bid.** If no searcher submits a bid above the protocol's reserve price (if any), the opportunity expires without on-chain settlement. The opportunity is then re-exposed on the next eligible state change.
- **Settlement-tx failure.** The on-chain `entry point` program enforces payment of the winning bid atomically with the underlying operation. If the underlying operation reverts (e.g., the price moved adversely between auction-win and settlement), the bid is also unpaid. The searcher's bid is contingent on successful operation execution.

### 1.4 Schema / wire format

On-chain (per PIP-54 + PIP-106):
- **Program ID:** `PytERJFhAKuNNuaiXkApLfWzwNwSNDACpigT3LwQfou`
- **Instructions** known publicly:
  - `swap` (added in PIP-54) — accepts user token accounts, searcher token accounts, signatures from user + searcher + relayer (3 signers), and a deadline parameter.
  - SPL-token-withdrawal instruction (added in PIP-106).
  - Plus the original liquidation-priority instruction set predating PIP-54, not enumerated in the PIP-54 forum post.
- **Auction outcomes** are visible in transaction logs / Anchor events; specific event names are not surfaced in the public PIP posts and require IDL fetch to enumerate. **TODO**: `anchor idl fetch PytERJFhAKuNNuaiXkApLfWzwNwSNDACpigT3LwQfou` to pin the IDL.

Off-chain:
- **Opportunity server REST/WebSocket.** Exposes opportunities to registered searchers; submission of bids. Specific API surface is in the Express Relay deep docs, which 404'd in our probe — gated on docs re-accessibility or direct integration.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** **not present.** `dataset/pyth_express_relay/...` does not exist. Listed as 📋 planned in [`docs/data-sources.md`](../../data-sources.md) §11 line 314.
- **On-chain auction events:** observable today via `getSignaturesForAddress(PytERJFhAKuNNuaiXkApLfWzwNwSNDACpigT3LwQfou)` + Anchor event-log decode. The same pattern as the Kamino/MarginFi liquidation scrape (see [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §2). **No active scraper today** — the planned tape lives in `scripts/collect_pyth_express_relay_tape.py` per [`docs/data-sources.md`](../../data-sources.md) §9 line 266 (target script not yet written).
- **Pre-cutover artefacts:** none — soothsayer has not yet pulled PER auction events. This is greenfield in the soothsayer/scryer stack.
- **What the planned tape would capture:** per [`docs/data-sources.md`](../../data-sources.md) §9 line 263:
  - auction events via Anchor program logs;
  - per-event bid stack;
  - winning bid;
  - tip distribution;
  - latency between Pyth update and auction settle;
  - searcher / protocol identifiers for each settled auction.
- **Cross-reference target (Paper 3):** join PER auction events with `kamino/liquidations/v1` (scryer wishlist item 1) and `jupiter_lend_liquidations/v1` (item 2) to identify which liquidations cleared through PER vs. spot mempool, and what the auction-recovered OEV was. The OEV-recapture rate is the load-bearing metric.

---

## 3. Reconciliation: stated vs. observed

The reconciliation here is structurally limited because **soothsayer has no PER auction tape yet**. Rows below are gated on the tape landing per §2.

| Stated claim | Observation | Verdict |
|---|---|---|
| Express Relay eliminates MEV by sequencing transactions in an off-chain auction. | **TODO when `pyth_express_relay/auction_tape/v1` lands.** Once we have on-chain auction events, segment liquidations on integrated protocols (Kamino is the reference integration per Pyth's success-stories page) by whether they cleared through PER or via spot mempool; report the bid-stack distribution and the protocol-vs-searcher OEV split. | **TODO** |
| Pyth DAO platform fee is initially 0 bps; 6% to relayer / 94% to DAO when activated. | Confirmed structurally per PIP-54. **Not yet activated** as of PIP-54 passage (specific activation event would need a forum + on-chain audit). | **confirmed (by docs), not yet activated** |
| The on-chain entry-point program enforces atomic payment of the winning bid + operation execution. | **TODO** — when the tape lands, validate by checking that every settled-auction tx has either both (bid paid + operation executed) or neither (revert). | **TODO** |
| Express Relay is the only Solana-native deployed OEV auction. | Confirmed by survey — no competing Solana-native OEV-auction primitive surfaces in [`docs/data-sources.md`](../../data-sources.md) §9 or in the broader ecosystem. **However**, "deployed" qualifier matters: Jito's bundle infrastructure handles MEV-style ordering at the validator-bundling layer (different mechanism, same outcome class — see [`docs/data-sources.md`](../../data-sources.md) §9 line 268). | **confirmed (with Jito caveat)** |
| Auction outcomes (winning bid, searcher identity, settled tx) are on-chain-readable. | **Partial — confirmed in principle by the program-ID being public and Anchor events being the standard pattern.** Concrete event names + IDL pin TODO. | **partial (confirmed by structure, unverified by tape)** |
| The auction is off-chain (relayer-operated opportunity server). | Confirmed per Pyth's blog post: "Searchers participate in an off-chain auction to access these operations." This is a centralisation point — the relayer can in principle censor opportunities or favour subsets of searchers. **No public empirical study of relayer behaviour exists in our reading.** | **confirmed (mechanism), unmeasured (governance)** |
| Searchers + user + relayer all sign the swap-settlement tx (3 signers). | Confirmed structurally per PIP-54. The 3-signer requirement is what enforces the auction's off-chain conclusion atomically. | **confirmed** |
| Kamino integrates Express Relay for swap execution. | Confirmed per Pyth's success-stories page (cited via search). The exact integration scope (whether Kamino's xStock liquidations clear through PER or only Kamino Swap user-flow does) is **not surfaced in the public material we accessed today**. **TODO when scryer tape lands.** | **partial** |
| Searchers compete on bid amount; winner pays the bid + executes the operation; the fee is captured by the protocol. | Confirmed structurally per the blog + PIP-54. | **confirmed (mechanism)** |

---

## 4. Market action / consumer impact

PER is the load-bearing mechanism for Paper 3's OEV-recapture analysis. The downstream-consumer story is dense:

- **Kamino klend (liquidations)** — Kamino is publicly cited as a PER integrator (per the Pyth success-stories page, cited via search). The relevant question for Paper 3: of the Kamino liquidation events captured in `kamino/liquidations/v1` (scryer wishlist item 1), what fraction clear through PER vs. spot mempool? And among those that clear through PER, what fraction of the realised OEV is captured by the protocol vs. the searcher?
- **Jupiter Lend (Fluid Vaults)** — similar question; whether Jupiter Lend integrates PER is a §6 open question. **TODO when scryer adds `jupiter_lend_liquidation.v1`** (item 2).
- **MarginFi** — MarginFi liquidator dynamics are documented in [`reports/kamino_liquidations_first_scan.md:34`](../../../reports/kamino_liquidations_first_scan.md) (~9 active liquidators per the grant retrospective). Whether MarginFi has a PER integration is a §6 open question; not surfaced in their README accessed 2026-04-29 ([`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §1).
- **Drift Protocol** — Drift handles its own keeper-network for market-making and liquidations; whether xStock-class markets on Drift route via PER is a §6 question. **TODO when scryer adds drift_perp_oracle_tape.v1.**
- **Pyth Network (oracle layer)** — PER is downstream of Pyth's price feed; an auction cannot clear without a recent Pyth update. The pyth_publish_time freshness gate (see [`oracles/pyth_regular.md`](pyth_regular.md) §1.3) is the upstream blocker for PER auction availability.
- **Soothsayer (publisher candidate, not consumer)** — PER's mechanism is *informative* for Paper 2 / Paper 3 OEV-mechanism design but is **not a soothsayer integration target** in Phase 1. Soothsayer publishes a calibrated band; PER auctions the right to act on a Pyth point estimate. Convergence (PER auctioning the right to act on a soothsayer band) is a Phase 2+ design conversation, not currently scoped.
- **Paper 3 §6 / §7** — the load-bearing reconciliation: protocol-OEV-recapture vs. searcher-OEV-capture, segmented by (PER-routed vs. mempool-routed). Without `pyth_express_relay/auction_tape/v1`, Paper 3 §6 is descriptive only; with the tape, it becomes the empirical OEV-recapture-rate paper.
- **Paper 1 §1 framing (peripheral but relevant)** — PER as a Solana-native OEV-auction primitive is the canonical example of "the price oracle and the auction-on-the-price-event are separable primitives" — useful in §10's generalisation discussion as a structural point about why soothsayer's calibration-transparency primitive is independently valuable from any OEV-recapture mechanism.
- **Public dashboard (Phase 2)** — PER auction settlement events would be a natural row in the OEV-recapture dashboard alongside per-protocol liquidation rates.

---

## 5. Known confusions / version pitfalls

- **PER is a sequencing primitive, not a price oracle.** Cross-referencing "Pyth Express Relay" alongside "Pyth Hermes" or "Pyth Pro" without distinguishing what each does is a frequent confusion. PER reads Pyth prices but does not produce them.
- **Off-chain auction, on-chain settlement.** The auction itself is off-chain (opportunity server, relayer-operated). On-chain visibility is *settlement* (winning tx + bid distribution), not the bid stack. Code that wants the full bid stack must ingest the relayer's API or maintain a researcher-tier subscription.
- **Program ID `PytERJFhAKuNNuaiXkApLfWzwNwSNDACpigT3LwQfou`.** This is the canonical Solana mainnet program ID; PIPs upgrade the program *in place*. Cross-referencing older PER-related forum posts must check which PIP version is being discussed.
- **Platform fee initially 0 bps.** PIP-54 enabled the platform fee mechanism but set the initial value to 0. Forum-thread search for the activation PIP is gated; until activated, PER is operationally subsidised by the relayer (the 6% relayer / 94% DAO split applies to a 0-bps fee, i.e., $0).
- **Three signers (user + searcher + relayer) on `swap`.** Code that simulates a PER swap tx without all three signatures will fail; the 3-signer pattern is enforced.
- **PER `swap` ≠ Jupiter Router swap.** Both are Solana swap primitives; PER's `swap` is auction-mediated (intent-style: user submits intent, searcher fills via auction), Jupiter's is router-mediated (user submits direct route, executes against on-chain liquidity). Not interchangeable.
- **Jito bundles + PER both reduce MEV but operate at different layers.** Jito bundles operate at the validator-block-builder layer; PER operates at the opportunity-server-relayer layer. A liquidation can in principle be both (PER-routed *and* Jito-bundled). Counting them as separate or overlapping requires the bundle-tape join (`jito/bundles/v1`, [`docs/data-sources.md`](../../data-sources.md) §9 line 268).
- **Docs link rot.** The Express Relay introduction page is accessible; the deep "How Express Relay Works" page returned 404 in our 2026-04-29 probe. Forum PIPs are the most reliable source for current technical details.
- **Express Relay is permissioned for searchers.** Searchers must register with the relayer; the network is not open-mempool. Comparator dashboards that frame "everyone can compete" must qualify.

---

## 6. Open questions

1. **Pin the program IDL via on-chain fetch** (`anchor idl fetch PytERJFhAKuNNuaiXkApLfWzwNwSNDACpigT3LwQfou`). **Why it matters:** the Auction Anchor event names + payload structure are needed to write the planned `collect_pyth_express_relay_tape.py`. **Gating:** anchor toolchain run + IDL pin under `idl/pyth_express_relay/`. (CLAUDE.md hard rule #1 — this is on-chain reads, NOT market-data fetching, so it's allowed.)
2. **Build `dataset/pyth_express_relay/auction_tape/v1/` in scryer.** Per [`docs/data-sources.md`](../../data-sources.md) §11 line 314 ("📋 planned"). **Why it matters:** Paper 3 §6 / §7 OEV-recapture-rate measurement is gated. **Gating:** scryer wishlist add (currently absent from Priority 0–4); methodology log entry per scryer hard rule #1.
3. **Has the platform fee been activated above 0 bps?** **Why it matters:** changes the searcher-incentive vs. protocol-incentive math. **Gating:** Pyth DAO forum search for the activation PIP + on-chain audit of the program's fee state.
4. **What fraction of Kamino liquidations clear through PER?** **Why it matters:** the load-bearing measurement for Paper 3 §6's "OEV-recapture rate by protocol" table. **Gating:** Both `kamino_liquidation.v1` (item 1) and `pyth_express_relay/auction_tape/v1` (open question #2) must land + a join script.
5. **Does MarginFi integrate PER for liquidations?** [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §1 does not surface PER as part of the marginfi-v2 oracle / liquidation stack. **Gating:** MarginFi reserve config snapshot + on-chain audit + outreach.
6. **Does Drift integrate PER for any market class (perps, spot, lending)?** **Gating:** Drift on-chain audit + their docs.
7. **Auction-server centralisation risk.** The relayer is a single point operating the opportunity server. What is the relayer's identity, governance accountability, and historical uptime record? **Why it matters:** if PER becomes the dominant Solana liquidation route, relayer downtime = ecosystem-wide liquidation freeze. **Gating:** Pyth governance review + historical incident query.
8. **What constitutes a `lucrative operation` exposed to PER beyond liquidations + swaps?** Per PIP-54, `swap` is the most recently added category; what's the next category, and what's the protocol-integrator on-ramp? **Gating:** Pyth roadmap query.
9. **PER-vs-Jito overlap.** A liquidation can be both PER-routed and Jito-bundled. What's the empirical overlap on Solana mainnet? **Gating:** join `pyth_express_relay/auction_tape/v1` + `jito/bundles/v1` (open question #2 + [`docs/data-sources.md`](../../data-sources.md) §9 line 268).

---

## 7. Citations

- [`pyth-express-relay-intro`] Pyth Network. *Express Relay — Introduction*. https://docs.pyth.network/express-relay. Accessed: 2026-04-29.
- [`pyth-express-relay-blog`] Pyth Network. *Express Relay: Priority Auctions for Efficient DeFi Markets*. https://www.pyth.network/blog/express-relay-priority-auctions. Cited via search results 2026-04-29.
- [`pyth-pip-54`] Pyth DAO. *OP-PIP-54: Upgrade the Pyth Express Relay program on Solana (PASSED)*. https://forum.pyth.network/t/passed-op-pip-54-upgrade-the-pyth-express-relay-program-on-solana/1977. Accessed: 2026-04-29. (Source for program ID `PytERJFhAKuNNuaiXkApLfWzwNwSNDACpigT3LwQfou`, commit `00940ec5...`, swap-instruction details, fee mechanics 6/94 split.)
- [`pyth-pip-106`] Pyth DAO. *OP-PIP-106: Upgrade the Pyth Express Relay Program on Solana to add an SPL token withdrawal instruction (PASSED)*. https://forum.pyth.network/t/passed-op-pip-106-upgrade-the-pyth-express-relay-program-on-solana-to-add-an-spl-token-withdrawal-instruction/2490. Accessed: 2026-04-29.
- [`pyth-kamino-success`] Pyth Network. *Kamino: How Kamino Swap achieves CEX-like execution with Pyth*. https://www.pyth.network/success-stories/kamino. Cited via search results 2026-04-29.
- [`pyth-deep-page-404`] Pyth Network. *How Express Relay Works* (deep page). https://docs.pyth.network/express-relay/protocols/how-express-relay-works → 404 on 2026-04-29; link rot logged.
- [`data-sources-per-planning`] Soothsayer internal. [`docs/data-sources.md`](../../data-sources.md) §9 line 261, §11 line 314. The `pyth_express_relay/auction_tape/v1` planned-tape ledger.
- [`paper3-references-companion`] Soothsayer internal. [`reports/paper3_liquidation_policy/references.md`](../../../reports/paper3_liquidation_policy/references.md). The Paper-3 references list — PER work is the empirical-OEV component.
