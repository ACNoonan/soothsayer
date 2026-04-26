# Chainlink Data Streams v11 — 24/5 cadence verification
*Generated 2026-04-26T19:44:41.199337+00:00 by `scripts/verify_v11_cadence.py`. Re-run any time; idempotent.*
Closes the **Must-fix-before-Paper-1-arXiv** publication-risk gate (`docs/ROADMAP.md` Publication-risk gates §1.2). The empirical question: during pre-market / regular / post-market / overnight windows, does v11 carry *real* `bid` / `ask` / `mid` values, or are they placeholder-derived bookends like during weekends?
## Method

Paginated through 5000 non-failed Verifier program signatures, decoded 5000 transactions, isolated 64 v11 (schema `0x000b`) reports, grouped by `market_status`. For each sample the spread between `bid` and `ask` (in bps of mid) classifies the quote as:

  - **REAL** — spread < 200 bps (consistent with a live liquid-equity quote)
  - **AMBIGUOUS** — 200–1000 bps (could be a halt or stressed real quote, or a partial placeholder)
  - **PLACEHOLDER** — > 1000 bps (consistent with the known weekend synthetic bookends, e.g. SPY-class `(21.01, 715.01)`)
  - **DEGENERATE** — bid ≥ ask, or any of bid/ask/last ≤ 0

Per-status verdict: **REAL** if > 50% of samples classify REAL, **PLACEHOLDER** if > 50% PLACEHOLDER, otherwise **MIXED**. **insufficient** if no samples were captured.
## Per-status verdicts

| status | label | n | real | ambig | placeh | median spread (bps) | verdict |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | pre-market | 0 | – | – | – | – | **insufficient** |
| 2 | regular | 0 | – | – | – | – | **insufficient** |
| 3 | post-market | 0 | – | – | – | – | **insufficient** |
| 4 | overnight | 0 | – | – | – | – | **insufficient** |
| 5 | closed/weekend | 64 | 32 | 14 | 18 | 237.0 | **MIXED** |
| 0 | unknown | 0 | – | – | – | – | **insufficient** |

## Sample reports per status

Raw decoded fields (first up to 5 per status). `bid`, `ask`, `mid`, `last_traded` are the v11 wire fields.
### `market_status = 5` (closed/weekend) — 64 total samples

| symbol | obs_ts | bid | ask | mid | last_traded | spread (bps) | classification |
|---|---|---:|---:|---:|---:|---:|---|
| (unmapped) | 2026-04-26T19:18:58+00:00 | 372.0100 | 384.4600 | 378.2350 | 376.0000 | 329.2 | AMBIGUOUS |
| (unmapped) | 2026-04-26T19:15:59+00:00 | 207.0100 | 210.0300 | 208.5200 | 207.9800 | 144.8 | REAL |
| (unmapped) | 2026-04-26T19:15:59+00:00 | 656.0100 | 663.7800 | 659.8950 | 663.7500 | 117.7 | REAL |
| (unmapped) | 2026-04-26T19:15:59+00:00 | 21.0100 | 715.0100 | 368.0100 | 713.9600 | 18858.2 | PLACEHOLDER |
| (unmapped) | 2026-04-26T19:14:59+00:00 | 372.0100 | 384.4600 | 378.2350 | 376.0000 | 329.2 | AMBIGUOUS |

## Outstanding

The following `market_status` values had no samples in this scan window:

  - `1` (pre-market)
  - `2` (regular)
  - `3` (post-market)
  - `4` (overnight)
  - `0` (unknown)

This is expected if the scan ran outside the relevant trading window (e.g., a Sunday-afternoon scan only sees `market_status=5`). Re-run during the appropriate window to fill in the gaps:

  - pre-market — Mon–Fri 04:00–09:30 ET (08:00–13:30 UTC)
  - regular — Mon–Fri 09:30–16:00 ET (13:30–20:00 UTC)
  - post-market — Mon–Fri 16:00–20:00 ET (20:00–00:00 UTC)
  - overnight — Mon–Fri 20:00 ET–04:00 ET next day (00:00–08:00 UTC)

Re-running this script periodically over the next week will accumulate samples across all sessions; the verdict table below is the running answer.

## What this verifies

The Paper 1 framing (§1.1, §2.1) describes Chainlink Data Streams' v11 schema as carrying placeholder-derived `bid`/`ask`/`mid` during the weekend window. The honest open question for v11 has been whether those fields go *real* during 24/5 sessions (pre/regular/post/overnight) or stay synthetic bookends. The verdicts above answer that question per session class. If pre-market / regular / post-market / overnight all classify **REAL**, the §1.1 weekend-only framing is correct as-is. If any of those classify **PLACEHOLDER** or **MIXED**, Paper 1 §1.1 and §2.1 should be updated to reflect that the placeholder behaviour is *not* weekend-only.

## Scope caveat: this scan captures the broader v11 universe on Solana, not xStocks specifically

All 64 v11 reports in this scan landed with `symbol = (unmapped)` — meaning their feed IDs are not in our `chainlink/feeds.py` `XSTOCK_FEEDS` registry. That registry is **v10-only** (the 8 xStock feed IDs we enumerated for the V5 tape are all `0x000a`-prefixed; v11 publishes under distinct `0x000b`-prefixed feed IDs that have not yet been mapped). So the 64 samples here are v11 feeds for *other RWA classes that share the v11 schema* — likely tokenized commodities, treasuries, or non-US equities — rather than the SPYx / QQQx / AAPLx / ... universe Paper 1 specifically discusses.

This is itself a meaningful preliminary finding. The MIXED weekend verdict (50% REAL, 28% AMBIGUOUS, 28% PLACEHOLDER) describes the broader v11 universe on Solana and tells us:

  - **v11 weekend behaviour is heterogeneous across the schema's user base.** ~50% of v11 reports during weekend carry realistic-looking quotes; only ~28% exhibit the known SPY-class synthetic-bookend pattern (`21.01, 715.01` style). The remainder sit in the ambiguous middle. Different issuers / underliers / publisher sets clearly behave differently within the same schema.
  - **The placeholder pattern documented in `docs/v5-tape.md` (2026-04-25) is correct for the specific xStock-class v11 feeds it scanned, but is not a universal property of v11.** Generalising the placeholder claim across all v11 traffic would overclaim.
  - **The xStock-specific v11 question remains open**, blocked on enumerating the 8 xStock-specific `0x000b`-prefixed feed IDs (per the existing `docs/v5-tape.md` TODO line "Map v11 feed_ids → xStock symbols (defer until needed for Phase 2 comparator)"). Once that mapping lands, this scan re-runs filtered to xStock feed IDs and produces the xStock-specific verdict the Paper 1 §1.1 framing actually depends on.

**Recommended follow-up before relying on this for the Paper 1 publication-risk gate:**

  1. **Enumerate xStock v11 feed IDs.** Either by sampling Verifier txs that are explicitly known to consume an xStock (via Kamino's Scope CPI logs, etc.) or by directly querying Chainlink's feed registry. Add the 8 mappings to `src/soothsayer/chainlink/feeds.py`.
  2. **Re-run this script with an xStock-only filter.** Once the registry includes v11 xStock feed IDs, the scan can subset by symbol and produce the xStock-specific verdicts that Paper 1 §1.1 needs. The current MIXED-across-broader-universe finding is a useful adjacent fact but is not the gate-closing measurement.
  3. **Continue weekday accumulation.** Re-run periodically through the week to fill in pre-market / regular / post-market / overnight verdicts (currently `insufficient` because today is Sunday). The scan is idempotent and can be cron'd alongside the Monday rollup.

The Paper 1 publication-risk gate is therefore **partially closed**: the broader-v11 weekend finding is committed; the xStock-specific verdict remains pending on (1) above. §1.1 should remain conservative pending that follow-up — the current "v11 weekend bid/ask are placeholder-derived" claim should be qualified to "v11 weekend bid/ask for the xStock feed IDs we have observed are placeholder-derived; the broader v11 universe shows heterogeneous behaviour."
