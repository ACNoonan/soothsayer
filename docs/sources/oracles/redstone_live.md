# `RedStone — Live (REST gateway, post-Mar 2026)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://api.redstone.finance/prices` (live REST gateway, schema probed 2026-04-26), [`docs/data-sources.md`](../../data-sources.md#redstone) RedStone empirical surface section, the loader at `src/soothsayer/sources/scryer.py:205`, the cron template at [`scripts/redstone_cron.example`](../../../scripts/redstone_cron.example). The official docs page `https://docs.redstone.finance/docs/dapps-and-defi/redstone-models` returned 404 on 2026-04-29 (link rot — model-page deep links appear to have been refactored on the docs site post-Live launch).
**Version pin:** **RedStone Live** (the 24/7 equity-coverage product launched March 2026). This file describes the **public REST gateway** surface — `https://api.redstone.finance/prices`. The Solana on-chain reads (Wormhole-Queries path), the Classic push model, the X deferred-execution mode, and the Atom atomic-push mode have or will have separate files in this directory.
**Role in soothsayer stack:** `comparator` — secondary, used sparingly. Methodology is undisclosed at the depth our reconciliation requires; the value is *adversarial corroboration* (a competing oracle provider has openly named the weekend-gap problem, see CoinDesk 23 Nov 2025) more than a quantitative comparator on equal footing with Pyth.
**Schema in scryer:** `dataset/redstone/oracle_tape/v1/year=YYYY/month=MM/day=DD.parquet` (schema `redstone.v1`). Loader: `src/soothsayer/sources/scryer.py:205` `load_redstone_window`. Live since 2026-04-26.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

**Methodology is undisclosed at the depth required for a reconciliation file.** RedStone's marketing language ("24/7 equity coverage", "institutional data provider connections combined with traditional crypto market data") and the introduction-page text describe a curated multi-source aggregation passing through "consensus mechanism requiring agreement from multiple independent, collateralized operators," but the deep architecture page (`https://docs.redstone.finance/docs/dapps-and-defi/redstone-models`) returned 404 on 2026-04-29 and the introduction page does not specify:

- which CEX / DEX / market-maker venues are aggregated,
- the weighting or median rule applied,
- whether any confidence interval is computed (no CI field appears in the public REST gateway response — see §1.4 and §3),
- the consensus threshold or operator set composition.

Co-founder Marcin Kazmierczak publicly named the weekend-gap problem for tokenized stocks in CoinDesk on 23 November 2025 — that statement is the most authoritative public acknowledgement that **even RedStone's own team does not claim a solved closed-market methodology**.

### 1.2 Cadence / publication schedule

REST gateway emits ~140 records/day at 10-minute cadence per symbol (probed 2026-04-26). RedStone Live's marketing claims continuous 24/7 emission for the equity coverage; observed retention on the public gateway is **30 days hard cap** (confirmed by direct probe at T-31d; see [`docs/data-sources.md`](../../data-sources.md#redstone)). Beyond 30 days, the gateway returns no records. There is no public archival surface; the paid Live WebSocket tier may serve longer history (not verified — outreach gated, queued in §6).

### 1.3 Fallback / degraded behavior

Public docs do not surface fallback behavior. Empirically (2026-04-26 probe):

- some equity tickers return empty result sets (TSLA, NVDA, HOOD, GOOGL),
- AAPL was 33 days stale at probe time (likely retired),
- the gateway does not return an error code for empty / stale; the consumer must implement age + presence checks themselves.

### 1.4 Schema / wire format

REST gateway response per record:

```json
{
  "value":            <float>,
  "timestamp":        <unix ms>,
  "source":           {"<venue_name>": <price>, ...},
  "liteEvmSignature": "<hex>",
  "providerPublicKey":"<hex>",
  "minutes":          <int>     // age proxy
}
```

**No `confidence` field. No dispersion / sample-count / band field.** This is the most material difference between the RedStone public surface and Pyth's: there is nothing on the wire that corresponds to a coverage-band claim. Soothsayer's `redstone.v1` schema (per the loader docstring `src/soothsayer/sources/scryer.py:205-222`) preserves these fields plus polling metadata:

```
poll_ts, poll_label, symbol, redstone_ts,
minutes_age, value, provider_pubkey, signature,
source_json, permaweb_tx, raw_json
```

`source_json` retains the per-venue price map for downstream reconstruction; `raw_json` is the raw API response for verification.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** `dataset/redstone/oracle_tape/v1/year=YYYY/month=MM/day=DD.parquet`. Live since 2026-04-26 16:05 UTC ([`docs/data-sources.md`](../../data-sources.md#redstone) Engineering inventory).
- **Loader:** `src/soothsayer/sources/scryer.py:205-222` `load_redstone_window`. Day-partitioned (the legacy soothsayer version was a single rolling file pre-cutover).
- **Polling cadence template:** [`scripts/redstone_cron.example`](../../../scripts/redstone_cron.example) — historical reference for Friday 15:55 ET / Monday 09:25 ET poll windows. Pre-cutover scraper (`scripts/run_redstone_scrape.py`) was deleted in April 2026 cutover; the live tape is now fed by the scryer-side daemon.
- **Solana on-chain:** the `redstone-sol` program at `3oHtb7BCqjqhZt8LyqSAZRAubbrYy8xvDRaYoRghHB1T` holds **only 4 PDAs** (AVAX, ETH, SOL, BTC), with last writes Oct 2024 (probed 2026-04-26). **No equity feeds on-chain.** RedStone's Solana-equity path is via Wormhole Queries and does not write on-chain (so it cannot be replayed); their Solana on-chain footprint for equities is effectively nil today.
- **Coverage in current tape:** equity tickers SPY ✓ (databento source), QQQ ✓ (twelve-data source), MSTR ✓ (twelve-data source), IWM ✓, XAU ✓; TSLA / NVDA / HOOD / GOOGL → empty; AAPL → 33-day stale (likely retired). **No xStock SPL tokens** — RedStone Live prices the underlier tickers, not SPYx / QQQx / MSTRx.

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| RedStone Live provides "24/7 equity coverage" for tokenized assets. | **Contradicted for the actual tokenized-asset addressable set.** No xStock SPL tokens are priced; only the underlier tickers (SPY, QQQ, MSTR, IWM, XAU). A protocol holding `SPYx` as collateral cannot directly read a RedStone Live price for `SPYx`; it must consume `SPY` and rely on the implicit "underlier ≈ tokenized" assumption — which is precisely what [Cong et al. 2025] document is *not* true on weekends. | **contradicted (in the form a tokenized-asset consumer would care about)** |
| Equity coverage extends across major US tickers. | **Contradicted in part.** SPY/QQQ/MSTR/IWM/XAU live; TSLA/NVDA/HOOD/GOOGL empty; AAPL 33d stale. Even on the underlier set, coverage is uneven. | **contradicted** |
| Consensus is reached via "multiple independent, collateralized operators." | **Unmeasurable from the public surface.** The wire schema returns one `providerPublicKey` per record; we cannot observe the consensus quorum or operator set from outside. | **unmeasurable from public surface** |
| The published price is reliable for off-hours equity pricing. | **Effectively contradicted on weekends by the no-CI / no-band schema** — there is no published interval, so any "reliability" claim cannot be empirically validated against a coverage SLA. The price may or may not be accurate; the framework to verify is missing on the wire. | **unmeasurable / structurally contradicted** |
| Solana on-chain RedStone surface covers equities. | **Contradicted.** `redstone-sol` program holds only 4 crypto PDAs, no equity feeds, last writes Oct 2024. The Solana-equity path is Wormhole-Queries only and does not persist on-chain. | **contradicted** |
| Per-source breakdown (`source_json`) shows the venues feeding each price. | Confirmed structurally — `source_json` is non-null in the tape and lists e.g. `{"databento": ...}` for SPY. The map is informative but does not constitute a published methodology. | **confirmed (data shape, not methodology)** |
| Co-founder publicly acknowledges weekend-gap problem (CoinDesk 23 Nov 2025). | Confirmed — adversarial corroboration that the problem soothsayer's served band targets is acknowledged industry-wide, not invented. This is the file's most useful residual finding given the methodology opacity above. | **confirmed (rhetorical use)** |

---

## 4. Market action / consumer impact

RedStone Live's downstream impact on Solana lending today is essentially nil for xStock-class collateral, because:

- **No xStock SPL feeds exist** (per §3) → no Solana lending protocol holding xStock collateral can read RedStone Live for that collateral.
- **No on-chain equity feeds on Solana** → Wormhole-Queries path is consumer-side reconstruction only.

For non-xStock RWA collateral (BUIDL, ACRED, VBILL, SCOPE, Canton Network), RedStone is the leading provider per their own marketing. The relevant downstream consumers in that segment are outside the soothsayer xStocks scope — but the broader RWA-wave generalisation argument in Paper 1 §10.5 / docs/methodology_scope.md uses BUIDL / OUSG as the next-class example, so RedStone's tokenized-treasury feeds are worth a follow-up reconciliation file ([`oracles/redstone_classic.md`](redstone_classic.md), 📋 planned).

For **comparator dashboards and Paper 1 framing**, RedStone Live's actual usefulness is:

- **Paper 1 §1 / §2** — quote the CoinDesk co-founder statement to show the weekend-gap problem is acknowledged across providers, not unique to soothsayer's framing.
- **Public dashboard (Phase 2)** — RedStone Live can sit as a `pyth_regular`-equivalent row, but the no-CI surface means there is no half-width to plot. The dashboard row reduces to "did the Friday-close RedStone print cover the Monday open as a point estimate?" — that's a degraded comparator and should be labelled as such.
- **MarginFi / Drift / Jupiter Lend / Save / Loopscale** — public docs do not list RedStone as a primary or secondary oracle for any of these on Solana for xStock-class collateral. The combined no-xStock-feed + no-on-chain-Solana-equity surface means RedStone Live is structurally absent from the xStock lending stack on Solana today. This may change with a future on-chain-equity push from RedStone, but as of 2026-04-29 it is not a live integration target. **TODO when/if RedStone publishes an xStock SPL feed.**

---

## 5. Known confusions / version pitfalls

- **Live vs Classic vs Pull / Push / X / Atom.** RedStone has shipped many product names. **Live** is the 24/7 equity-coverage REST product launched March 2026 — the subject of this file. **Classic** is the older Push (Wormhole-bridged) on-chain push model — separate file. **Pull (Core)** is the consumer-pull pattern (sign + verify in-tx). **X** is deferred-execution for perps. **Atom** is atomic-push. The naming is overloaded; cross-referencing third-party "RedStone supports xyz" claims without checking which surface is the source of confusion.
- **`api.redstone.finance/prices` ≠ on-chain RedStone.** The public REST gateway is one observation surface; consumers integrating RedStone on-chain do **not** read the gateway, they read program PDAs (or use Wormhole Queries). The two surfaces have different update cadences and content sets.
- **Underlier vs xStock symbol convention.** RedStone's equity feeds price `SPY`, not `SPYx`. Same gotcha as Pyth (see [`oracles/pyth_regular.md`](pyth_regular.md) §5).
- **30-day retention is silent.** No HTTP error or warning at T-31d; queries simply return empty result sets indistinguishable from "ticker not covered." Distinguishing retention-cap vs no-coverage requires probing a known-good ticker at the same `T-N` window.
- **`minutes` field is age, not freshness guarantee.** A `minutes=0` record means the record was generated 0 minutes ago, not that the underlying source price is current. For weekend equity, the source price is by definition stale; the 0-minute age is misleading.
- **No `liteEvmSignature` / `providerPublicKey` on-chain proof for Solana equities.** The signature is for EVM verification; Solana consumers cannot use it to validate the price against the operator set. Solana-equity path is "trust the operator" until on-chain Solana-equity feeds exist.

---

## 6. Open questions

1. **Methodology disclosure beyond the introduction page.** Sources, weighting, consensus quorum, confidence interval if any. **Gating:** outreach to RedStone team (the introduction-page model deep links 404'd as of 2026-04-29; ask for current canonical URL or governance disclosure).
2. **Paid Live WebSocket tier — does it serve a CI field, longer history, or the missing equity tickers?** **Gating:** request paid-tier sample data + spec from RedStone sales.
3. **Will RedStone publish on-chain Solana equity feeds at the SPL token granularity?** This would make RedStone a live xStock-collateral comparator on Solana. **Gating:** RedStone roadmap query.
4. **Why are TSLA/NVDA/HOOD/GOOGL empty on the public gateway?** Possible: paid-tier-only tickers, retired feeds, regional restrictions. **Gating:** support ticket + sales conversation.
5. **What does the `source` map indicate for equity tickers on weekends — does it shift composition (e.g., from databento weekday to a different venue weekend)?** This is observable from our `source_json` column and would indicate which venues RedStone is using to fabricate the weekend price. **Gating:** add a §3 row once we run the analysis (not blocked by data; blocked by analysis time).
6. **Does the `liteEvmSignature` differ across consecutive 10-minute records when only the underlying source price has changed?** A signature-stable, value-changing surface would indicate fabrication; signature-changing surface would indicate genuine re-signing. **Gating:** internal scryer-tape audit (`raw_json` column has the signature).

---

## 7. Citations

- [`redstone-introduction`] RedStone. *Introduction*. https://docs.redstone.finance/docs/introduction. Accessed: 2026-04-29.
- [`redstone-models-404`] RedStone. *RedStone Models* (deep page). https://docs.redstone.finance/docs/dapps-and-defi/redstone-models — returned 404 on 2026-04-29; link rot logged.
- [`redstone-rest-gateway`] RedStone. Public REST gateway. https://api.redstone.finance/prices. Probed: 2026-04-26.
- [`coindesk-redstone-weekend`] Kazmierczak, M. (RedStone co-founder). 2025-11-23. *Weekend gap acknowledgement*. CoinDesk. (Specific URL TBD; cited via [`docs/data-sources.md`](../../data-sources.md#redstone).)
- [`redstone-cron-example`] Soothsayer internal. [`scripts/redstone_cron.example`](../../../scripts/redstone_cron.example). Pre-cutover historical polling cadence reference.
- [`scryer-redstone-loader`] Soothsayer internal. [`src/soothsayer/sources/scryer.py`](../../../src/soothsayer/sources/scryer.py) `load_redstone_window` at line 205.
- [`redstone-empirical-surface`] Soothsayer internal. [`docs/data-sources.md`](../../data-sources.md#redstone) §7 RedStone block (2026-04-26 probe).
