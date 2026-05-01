# `Pyth Lazer / Pyth Pro (Blue Ocean ATS path)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.pyth.network/lazer` (accessed 2026-04-29; page now reframes the product as **"Pyth Pro (formerly Pyth Lazer)"** — a documented name change. Top-level overview present, deeper methodology pages defer to subscription/API docs not surfaced as stable URLs in the same probe wave), `https://www.pyth.network/blog/blue-ocean-ats-joins-pyth-network-institutional-overnight-hours-us-equity-data` (accessed 2026-04-29; the load-bearing source for hours, equity coverage, and exclusivity), `https://blueocean-tech.io/2025/09/25/pyth-blue-ocean-ats-joins-pyth-network-institutional-overnight-hours-us-equity-data/` (Blue Ocean's announcement page; cross-references the same partnership). [`docs/data-sources.md`](../../data-sources.md) §7 line 185 (the catalog summary citing 24/5, 50+ equities, vendor-reported 96%+ NBBO accuracy, sub-100ms — those specific numbers came from a prior reading and are *not* surfaced in the docs pages re-accessed 2026-04-29; treat as stale).
**Version pin:** **Pyth Pro (formerly Lazer)** — the low-latency, customizable-cadence enterprise tier of Pyth, with the **Blue Ocean ATS** integration as its load-bearing 24/5-equity differentiator. Blue Ocean partnership: **exclusive through end-2026** ("Pyth will be the only data distributor publishing overnight US equity trading data onchain from the Blue Ocean ATS platform"). Hours covered by Blue Ocean: **8:00 PM – 4:00 AM ET, Sunday through Thursday**, providing the overnight slice that completes a 24/5 view when joined with Pyth's regular regular-session feeds.
**Role in soothsayer stack:** `comparator (24/5 equity, partial)` — the closest published incumbent to a "real" 24/5 equity feed, structurally distinct from Chainlink v11's synthetic-bid weekend pattern (see [`oracles/chainlink_v11.md`](chainlink_v11.md) §3) because Blue Ocean's overnight pricing is from **executable** order-book data (~$1B nightly volume per Pyth's blog), not from extrapolation. **However:** Blue Ocean covers Sunday-overnight through Thursday-overnight; **the Saturday + most of Sunday window — the canonical xStock weekend — is *not* covered**, so this product does not solve the soothsayer-targeted weekend gap. It solves the *overnight* gap.
**Schema in scryer:** **not in scryer.** No paid-tier subscription, no tape capture; `dataset/pyth_pro/...` does not exist. Pyth Pro is a paid enterprise product (per the docs page). **TODO** if soothsayer ever has Tier-2 paid budget for a comparator (see [`docs/data-sources.md`](../../data-sources.md) §"Production steady state" — currently $0 Phase-0 budget).

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

Pyth Pro's documented architecture is **the same publisher-vote aggregation as regular Pyth** (3N-vote median + Q25/Q75 confidence — see [`oracles/pyth_regular.md`](pyth_regular.md) §1.1) extended with two operational customisations:

1. **Customizable feed configuration and update schedule.** Per the Pyth Pro overview accessed 2026-04-29: "Subscribers can configure their price feeds and update schedules." This is the enterprise tier's primary distinguishing feature vs. the free regular Pyth — paying subscribers tune cadence and feed selection rather than reading the public default.
2. **Direct-from-first-party-publisher distribution.** Per the same page: "Pyth Pro delivers customizable, enterprise-grade price data directly from first-party publishers." The phrasing implies a tighter publisher set or a direct-feed integration relative to the public Pythnet aggregation, but the docs page does not make this concrete enough to reconcile against the regular path.

The **Blue Ocean ATS** integration extends this with overnight-equity coverage that the regular path does not have:

- **Source:** Blue Ocean ATS — a US-regulated NMS-securities ATS operating 8:00 PM – 4:00 AM ET, Sun–Thu. Per Pyth's blog: "executable prices from ~$1B volume traded nightly" rather than indicative pricing. ~11,000 NMS symbols are enabled overnight, with ~5,000 actively traded each night.
- **Distribution:** Pyth is the **exclusive on-chain distributor of Blue Ocean's overnight equity data through end-2026**. Off-chain, Blue Ocean's data is distributed through Cboe Global Markets (per the partnership announcements).
- **Methodology language for the off-hours price:** the Pyth blog post (accessed 2026-04-29) does **not** describe how the on-chain Pro-distributed overnight price is computed beyond stating that the source is "executable" rather than "indicative" — i.e., the price is from real Blue Ocean order-book activity rather than from a stale-hold or extrapolation. Whether multiple publishers contribute during the overnight window, or whether Blue Ocean is the sole publisher with the regular-session publisher set absent, is not surfaced. **Open question.**

### 1.2 Cadence / publication schedule

- **Regular Pyth Pro feeds (non-Blue-Ocean):** customizable per subscriber. The free / regular Pyth slot cadence is ~400ms; Pro subscribers can request finer or coarser cadence per their docs (specific values not surfaced in the overview page).
- **Blue Ocean ATS overnight slice:** 8:00 PM – 4:00 AM ET, Sun–Thu nights. **Saturday + most of Sunday is not covered.** This is the load-bearing limitation for soothsayer's weekend-targeted use case: the Sunday-overnight-into-Monday-morning window is filled, but Friday-close-through-Sunday-late is not.

The combined coverage map for US equities reading **regular Pyth + Pyth Pro (Blue Ocean)** thus spans:

| Window | Source |
|---|---|
| Mon-Fri 9:30 AM – 4:00 PM ET (regular session) | Regular Pyth (publisher-vote aggregation) |
| Mon-Fri 4:00 PM – 8:00 PM ET (post-market) | Regular Pyth (publishers thin; conf widens — same dispersion-vs-SLA pattern) |
| Mon-Thu 8:00 PM – 4:00 AM ET (overnight) | Pyth Pro (Blue Ocean ATS, executable book data) |
| Mon-Fri 4:00 AM – 9:30 AM ET (pre-market) | Regular Pyth (publishers thin) |
| **Friday 8:00 PM ET – Sunday 8:00 PM ET (the canonical weekend)** | **Neither covers this — the soothsayer-targeted gap** |
| Sunday 8:00 PM ET – Monday 4:00 AM ET (Sunday overnight) | Pyth Pro (Blue Ocean) |

### 1.3 Fallback / degraded behavior

- **Regular Pyth fallback semantics apply** to Pyth Pro's underlying aggregation — see [`oracles/pyth_regular.md`](pyth_regular.md) §1.3 (`min_publishers` threshold, EMA twin, per-publisher staleness drop).
- **Blue Ocean transitions to/from regular session** are an operational seam: at 4:00 AM ET (open of pre-market), Blue Ocean stops publishing and the publisher set rotates to regular-session participants. Whether the conf interval widens or remains stable across this rotation is unmeasured.
- **Sunday morning and Saturday gap.** During the canonical weekend window, the docs do not state what Pyth Pro returns. The most plausible behaviour (by analogy to the regular path during closed-market) is a stale-hold from Friday close with a confidence interval that may or may not widen mechanically — but this is a **§6 open question** because the docs are silent.

### 1.4 Schema / wire format

The docs page accessed 2026-04-29 directs to `/price-feeds/pro/api` for the integration details; that page was not surfaced in our probe. The overview claims "standard APIs for seamless integration" without specifying whether the Pro tier shares the same `IPyth` interface, the same Hermes endpoints, or a separate API surface. **Open question.**

What can be inferred: since the underlying aggregation is the same publisher-vote median, the **on-the-wire `(price, conf, expo, publish_time)` tuple shape is the same as regular Pyth**. The differentiation is operational (cadence customisation, feed selection, Blue Ocean integration), not in the value-tuple schema.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** **not present.** Pyth Pro is a paid enterprise product; soothsayer has no subscription. `dataset/pyth_pro/...` does not exist; not in `scryer/wishlist.md`.
- **Indirect cross-reference:** the Pyth Pro / Blue Ocean overnight feed is, in principle, observable on-chain via the same Pyth on-Solana `PriceAccount` infrastructure if Blue Ocean's overnight prices flow into the same feed-id space as regular Pyth (the docs are unclear on this — they may flow into separate "Pro-only" feed IDs that require a paid subscription to read, or into the same public PriceAccount that everyone else reads). **TODO**: probe whether `dataset/pyth/oracle_tape/v1/...` shows non-stale `pyth_publish_time` values during the 8 PM – 4 AM ET overnight window for SPY/QQQ/etc. — if yes, then Blue Ocean's overnight prices are flowing through the public regular-Pyth surface. **This is a single-script analysis pass against existing scryer data**, not a new data source — it lives in §6 as an actionable open question.
- **Pyth Pro on-chain footprint:** the Pyth Pro docs reference an SVM runtime (per the Fogo-docs page); whether Pyth Pro has a separate Solana program ID from regular Pyth is unmeasured. Regular Pyth's Solana program is `FsJ3A3u2vn5cTVofAjvy6y5kwABJAqYWpe4975bi2epH` (oracle program); Pyth Pro may use the same program with feed-id-based access control or a separate program. **Open question.**

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| Pyth Pro extends Pyth coverage to 24/5 US equities. | **Partially confirmed**, structurally — the 8 PM – 4 AM ET overnight window Sun–Thu is documented to be covered via Blue Ocean. **Not confirmed** for Saturday + most of Sunday — those windows are not in Blue Ocean's operating hours and the docs do not state that Pyth Pro fills them. | **partial — overnight gap closed, weekend gap remains** |
| Blue Ocean overnight prices are executable, not indicative. | Confirmed by the Pyth blog post: "executable prices from ~$1B volume traded nightly." This is structurally different from Chainlink v11's synthetic-bid weekend pattern (which is non-executable, see [`oracles/chainlink_v11.md`](chainlink_v11.md) §3). **However, soothsayer cannot independently verify the executable nature without Pro-tier access.** | **confirmed by docs, unmeasured from soothsayer side** |
| Pyth Pro is the **exclusive** on-chain distributor of Blue Ocean ATS overnight equity data through end-2026. | Confirmed in both Pyth's blog post and Blue Ocean's mirror announcement. After end-2026, the partnership exclusivity expires and the surface may broaden or contract. | **confirmed (rhetorical use, time-limited)** |
| Vendor-reported 96%+ NBBO accuracy, sub-100ms latency. | **Stale — these numbers were cited in [`docs/data-sources.md`](../../data-sources.md) line 185 from a prior probe but are *not* surfaced in the docs pages re-accessed 2026-04-29.** Re-probe gated, see §6. | **stale citation, needs re-verification** |
| ~50+ equities covered. | **Stale — re-probe shows ~5,000 actively-traded NMS symbols in Blue Ocean's overnight window** per the Pyth blog. The "50+" figure cited in our prior catalog appears to refer to the Pyth Pro feed-set initially configured for institutional subscribers, not the addressable set Blue Ocean provides. | **stale citation, larger than documented** |
| Pyth Pro is the same publisher-vote aggregation as regular Pyth, with subscriber-customizable cadence. | Confirmed structurally per the overview page; the underlying mechanism is the same. | **confirmed (by docs)** |
| Blue Ocean prices flow into the public regular-Pyth `PriceAccount` surface. | **Unmeasurable from public docs** — the integration model (separate Pro-only feed IDs vs. shared with regular) is not surfaced. **TODO**: scryer probe — check `dataset/pyth/oracle_tape/v1/...` for SPY/QQQ during 8 PM – 4 AM ET Sun-Thu and look for non-stale `pyth_publish_time`. If yes, Blue Ocean is flowing into the public surface; if stale, it is Pro-only. | **unmeasurable from docs, scryer-probable** |

---

## 4. Market action / consumer impact

Pyth Pro's downstream consumer impact is **structurally different** from soothsayer's xStock-weekend focus, but the partial-overlap matters:

- **Drift Protocol (perps + spot)** — Coinbase International Exchange (per the search results) "integrated Pyth Lazer to enhance the speed and precision of pricing data used across its derivatives." Drift is Solana-native and uses the public regular-Pyth path; whether Drift will adopt Pyth Pro overnight feeds for equity-class markets specifically is a §6 open question. **TODO when scryer adds drift_perp_oracle_tape.v1.**
- **MarginFi** — public docs do not list Pyth Pro feeds for any marginfi-v2 bank (per [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §1.1). **TODO** if/when an xStock-class bank lands on MarginFi with overnight-equity pricing.
- **Tokenized-equity issuers (Backed, Ondo)** — issuers may use Pyth Pro for Sunday-overnight NAV computation if they wish; soothsayer has no visibility into issuer-side NAV computation paths.
- **Non-Solana EVM consumers** — Pyth Pro's Pull-style transport (presumably mirroring [`oracles/pyth_pull.md`](pyth_pull.md)) extends 24/5 equity coverage off-chain. Most relevant for EVM tokenized stocks (e.g., Backed's bxStock family on EVM chains). Cross-reference [`oracles/pyth_pull.md`](pyth_pull.md) §4.
- **Paper 1 §1 framing** — the existence of Pyth Pro / Blue Ocean **strengthens** the framing in a specific way: the canonical-incumbent claim "no published 24/7 equity feed exists" must be qualified to "no published 24/7 equity feed covering Saturday + Sunday-pre-overnight exists" — Pyth Pro fills the overnight gap with executable data, which is real-coverage progress. The soothsayer-targeted gap (Friday 4 PM ET → Sunday 8 PM ET, ~52 hours) is precisely the residual that Pro doesn't cover and is the loose thread Paper 1 isolates.
- **Public dashboard (Phase 2)** — Pyth Pro is the natural *upper-bound comparator* for an "executable real-time" claim in the equity-overnight window; soothsayer's served band sits *next* to it for the weekend window where Pyth Pro is also unavailable. The dashboard composition is "Pyth regular + Pyth Pro overnight + soothsayer band weekend" as a complete-coverage claim.

---

## 5. Known confusions / version pitfalls

- **"Pyth Lazer" was renamed to "Pyth Pro" in Pyth's docs around 2026.** The `/lazer` URL accessed 2026-04-29 displays "Pyth Pro (formerly Pyth Lazer)" — citing "Lazer" alone is now temporally ambiguous. Use "Pyth Pro" going forward; "Lazer" is a legacy term retained for backward reference (and is the term used in [`docs/data-sources.md`](../../data-sources.md) line 185 prior to this rename observation). **Update line 185 when convenient.**
- **Pyth Pro ≠ Pyth regular.** Same Pythnet aggregation, different distribution tier (paid, customizable cadence, additional feed sources like Blue Ocean). Cross-referencing "Pyth confidence" without specifying tier is the source of confusion.
- **Pyth Pro overnight ≠ Pyth Pro 24/7.** Blue Ocean's hours are 8 PM – 4 AM ET Sun–Thu. The phrase "24/5 equity" describes the **combined** Pyth-regular + Pyth-Pro coverage during the trading week; **the canonical Saturday + Sunday-pre-overnight weekend is uncovered**. Code that assumes Pyth Pro fills the weekend will be wrong.
- **Blue Ocean is one publisher, not necessarily the only overnight publisher.** The Pyth Pro aggregation could pull from additional overnight sources beyond Blue Ocean; the docs do not enumerate. Don't assume Pro-overnight = Blue-Ocean-only.
- **The "96%+ NBBO accuracy, sub-100ms latency, 50+ equities" line in the soothsayer data-sources catalog is from a prior probe and is not surfaced in current docs.** Treat that line as stale until re-verified.
- **Exclusivity is end-2026.** Until then, no other on-chain data distributor publishes Blue Ocean overnight equity data; after end-2026 the surface may broaden. Long-term reasoning that depends on Pyth Pro being the unique overnight on-chain source has a 2026-12-31 expiry.
- **Pyth Pro is a paid enterprise product.** Soothsayer's $0 Phase-0 budget cannot subscribe; comparator analysis is via the regular Pyth `PriceAccount` surface (which may or may not carry Blue Ocean's overnight flows — see §3).
- **Customizable cadence ≠ random cadence.** Pyth Pro subscribers configure their feed cadence at subscription time; the value-shape (`price, conf, expo, publish_time`) is the same. Code that assumes "Pyth Pro values change every X seconds" must read the configured cadence per feed, not a global default.

---

## 6. Open questions

1. **Does Blue Ocean ATS overnight pricing flow into the public regular-Pyth on-Solana `PriceAccount` surface, or is it Pro-tier-gated?** **Why it matters:** if it flows into the public surface, soothsayer can immediately incorporate Sun-Thu overnight as a comparator without paying for Pyth Pro. **Gating:** scryer probe — analyse `dataset/pyth/oracle_tape/v1/...` for SPY/QQQ during 8 PM – 4 AM ET Sun-Thu, segmented by `pyth_publish_time` freshness. Single-script analysis, no new data source needed. **Add to a future analysis pass.**
2. **What does Pyth Pro return for Saturday + most of Sunday?** Stale-hold from Friday close? Mechanical conf-widening? An explicit "no data" status code? **Why it matters:** the canonical xStock weekend gap. **Gating:** Pyth Pro tier subscription or a sponsored probe.
3. **Re-verify the "96%+ NBBO accuracy, sub-100ms latency, 50+ equities" claim.** These numbers are stale relative to the 2026-04-29 docs read. **Gating:** Pyth marketing-page probe + cross-reference against current Blue Ocean public materials.
4. **Pyth Pro program ID and feed-ID space on Solana.** Whether Pro feeds use the same program + a separate feed-id namespace, or a separate program, is unsurfaced in public docs. **Why it matters:** if separate, scryer needs a distinct fetcher; if same, the existing Pyth fetcher may already capture Pro flows for free. **Gating:** Pyth Labs outreach + on-chain audit.
5. **What is the publisher set during the Blue Ocean overnight window?** Is Blue Ocean the sole publisher with all other Pyth equity publishers absent (in which case the 3N-vote aggregation degenerates to just Blue Ocean's votes), or are there additional overnight publishers? **Why it matters:** if Blue Ocean is sole, the "publisher-vote aggregation" framing is degenerate during overnight and Pyth Pro overnight is structurally an "echoed" Blue Ocean print. **Gating:** Pyth on-Solana per-publisher data (see [`oracles/pyth_regular.md`](pyth_regular.md) §6, gated on `pyth_components.v1` scryer queue).
6. **End-2026 exclusivity expiry — what's the planned successor / continuation policy?** **Why it matters:** if exclusivity ends and Pyth Pro loses its Blue Ocean differentiator, the comparator surface for Paper 1 shifts. **Gating:** Pyth roadmap query.
7. **Does Pyth Pro / Blue Ocean carry SPYx or other xStock SPL feeds, or only the underlier US equity tickers?** **Why it matters:** same gotcha as Pyth regular — the underlier ≠ tokenized. Even with overnight Blue Ocean coverage, an xStock consumer reads the underlier feed, not the SPYx token. **Gating:** Pyth Pro feed-ID list query.

---

## 7. Citations

- [`pyth-pro-overview`] Pyth Network. *Pyth Pro (formerly Pyth Lazer) — Enterprise-grade price data with customizable cadence*. https://docs.pyth.network/lazer. Accessed: 2026-04-29.
- [`pyth-blue-ocean-blog`] Pyth Network. 2025-09-25. *Blue Ocean ATS Joins Pyth Network: Institutional Overnight Hours US Equity Data*. https://www.pyth.network/blog/blue-ocean-ats-joins-pyth-network-institutional-overnight-hours-us-equity-data. Accessed: 2026-04-29.
- [`blue-ocean-mirror`] Blue Ocean Technologies LLC. 2025-09-25. *Blue Ocean ATS Joins Pyth Network*. https://blueocean-tech.io/2025/09/25/pyth-blue-ocean-ats-joins-pyth-network-institutional-overnight-hours-us-equity-data/. Accessed: 2026-04-29.
- [`pyth-lazer-fogo`] Fogo. *Pyth Lazer Oracle*. https://docs.fogo.io/ecosystem/pyth-lazer-oracle.html. Accessed: 2026-04-29.
- [`pyth-regular-companion`] Soothsayer internal. [`docs/sources/oracles/pyth_regular.md`](pyth_regular.md). The regular-path reconciliation file — Pro inherits the same Pythnet-side aggregation findings.
- [`pyth-pull-companion`] Soothsayer internal. [`docs/sources/oracles/pyth_pull.md`](pyth_pull.md). The pull-transport reference for off-Solana consumers; Pyth Pro on EVM extends from this base.
- [`data-sources-catalog-stale`] Soothsayer internal. [`docs/data-sources.md`](../../data-sources.md) line 185. Stale citation: "96%+ NBBO accuracy, sub-100ms, 50+ equities" — re-probe gated per §6 #3.
