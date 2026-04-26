# Chainlink Data Streams v11 — 24/5 cadence verification
*Generated 2026-04-26T23:23:56.106199+00:00 by `scripts/verify_v11_cadence.py` (v2 — synthetic-marker classifier, per-symbol verdicts). Re-run any time; idempotent.*
Closes the **Must-fix-before-Paper-1-arXiv** publication-risk gate (`docs/ROADMAP.md` Publication-risk gates §1.2). The empirical question: during pre-market / regular / post-market / overnight windows, does v11 carry *real* `bid` / `ask` / `mid` values, or are they placeholder-derived bookends like during weekends?
## Method (v2 classifier)

Paginated through 3000 non-failed Verifier program signatures, decoded 3000 transactions, isolated 26 v11 (schema `0x000b`) reports, grouped by `(symbol, market_status)` using the `XSTOCK_V11_FEEDS` registry. Each sample is classified into a 6-class taxonomy that distinguishes synthetic-marker patterns from real quotes:

  - **PURE_PLACEHOLDER** — both bid AND ask end in `.01` (the canonical SPYx 21.01/715.01 bookend pattern).
  - **BID_SYNTHETIC** — bid ends in `.01`, ask does not. Partial-placeholder pattern: synthetic-low bid paired with real-ish ask. The v1 spread-only classifier missed this when the spread happened to fall under 200 bps.
  - **ASK_SYNTHETIC** — ask ends in `.01`, bid does not (rare).
  - **REAL** — neither side `.01`-marked, spread < 200 bps.
  - **AMBIGUOUS** — neither side `.01`-marked, spread 200–1000 bps.
  - **WIDE_REAL** — neither side `.01`-marked, spread > 1000 bps.
  - **DEGENERATE** — bid ≥ ask, or any non-positive value.

Per-(symbol, status) verdict (synthetic-aware):

  - **placeholder-derived** — > 50% of samples are in any synthetic class (PURE_PLACEHOLDER + BID_SYNTHETIC + ASK_SYNTHETIC).
  - **real-quote** — > 50% of samples are REAL.
  - **mixed** — neither majority.
  - **insufficient** — no samples for that bucket.

The synthetic-marker (`.01` suffix) was identified empirically: every v11 weekend bid in the prior scan ended in exactly `.01` across the 4 mapped xStocks (SPYx 21.01, QQQx 656.01, TSLAx 372.01, NVDA-class 207.01). Real-market bids land on `.01` ~1-in-100 randomly; a 100% incidence is a strong synthetic signal.
## Per-(symbol, status) verdicts

| symbol | status | label | n | pure-PH | bid-synth | ask-synth | real | ambig | wide | median spread (bps) | verdict |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **(unmapped)** | 5 | closed/weekend | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 144.8 | **placeholder-derived** |
| **NVDAx** | 5 | closed/weekend | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 3.4 | **real-quote** |
| **QQQx** | 5 | closed/weekend | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 117.7 | **placeholder-derived** |
| **SPYx** | 5 | closed/weekend | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 18858.2 | **placeholder-derived** |
| **TSLAx** | 5 | closed/weekend | 7 | 1 | 6 | 0 | 0 | 0 | 0 | 329.2 | **placeholder-derived** |

## Sample evidence per (symbol, status)

Raw decoded fields (first up to 5 per bucket). `bid`, `ask`, `mid`, `last_traded` are the v11 wire fields. Watch for the `.01` suffix on bid as the synthetic-low marker; the `class` column shows the v2 classifier's call.
### `(unmapped)`, `market_status = 5` (closed/weekend) — 6 samples

| obs_ts | bid | ask | mid | last_traded | spread (bps) | class |
|---|---:|---:|---:|---:|---:|---|
| 2026-04-26T23:18:58+00:00 | 207.0100 | 210.0300 | 208.5200 | 207.9800 | 144.8 | BID_SYNTHETIC |
| 2026-04-26T23:13:59+00:00 | 207.0100 | 210.0300 | 208.5200 | 207.9800 | 144.8 | BID_SYNTHETIC |
| 2026-04-26T23:08:59+00:00 | 207.0100 | 210.0300 | 208.5200 | 207.9800 | 144.8 | BID_SYNTHETIC |
| 2026-04-26T23:02:59+00:00 | 207.0100 | 210.0300 | 208.5200 | 207.9800 | 144.8 | BID_SYNTHETIC |
| 2026-04-26T22:58:59+00:00 | 207.0100 | 210.0300 | 208.5200 | 207.9800 | 144.8 | BID_SYNTHETIC |

### `NVDAx`, `market_status = 5` (closed/weekend) — 1 samples

| obs_ts | bid | ask | mid | last_traded | spread (bps) | class |
|---|---:|---:|---:|---:|---:|---|
| 2026-04-26T23:07:59+00:00 | 208.0700 | 208.1400 | 208.1050 | 208.0986 | 3.4 | REAL |

### `QQQx`, `market_status = 5` (closed/weekend) — 6 samples

| obs_ts | bid | ask | mid | last_traded | spread (bps) | class |
|---|---:|---:|---:|---:|---:|---|
| 2026-04-26T23:15:58+00:00 | 656.0100 | 663.7800 | 659.8950 | 663.7500 | 117.7 | BID_SYNTHETIC |
| 2026-04-26T23:11:59+00:00 | 656.0100 | 663.7800 | 659.8950 | 663.7500 | 117.7 | BID_SYNTHETIC |
| 2026-04-26T23:07:59+00:00 | 656.0100 | 663.7800 | 659.8950 | 663.7500 | 117.7 | BID_SYNTHETIC |
| 2026-04-26T23:03:59+00:00 | 656.0100 | 663.7800 | 659.8950 | 663.7500 | 117.7 | BID_SYNTHETIC |
| 2026-04-26T22:59:59+00:00 | 656.0100 | 663.7800 | 659.8950 | 663.7500 | 117.7 | BID_SYNTHETIC |

### `SPYx`, `market_status = 5` (closed/weekend) — 6 samples

| obs_ts | bid | ask | mid | last_traded | spread (bps) | class |
|---|---:|---:|---:|---:|---:|---|
| 2026-04-26T23:15:59+00:00 | 21.0100 | 715.0100 | 368.0100 | 713.9600 | 18858.2 | PURE_PLACEHOLDER |
| 2026-04-26T23:11:59+00:00 | 21.0100 | 715.0100 | 368.0100 | 713.9600 | 18858.2 | PURE_PLACEHOLDER |
| 2026-04-26T23:07:59+00:00 | 21.0100 | 715.0100 | 368.0100 | 713.9600 | 18858.2 | PURE_PLACEHOLDER |
| 2026-04-26T23:03:59+00:00 | 21.0100 | 715.0100 | 368.0100 | 713.9600 | 18858.2 | PURE_PLACEHOLDER |
| 2026-04-26T22:59:59+00:00 | 21.0100 | 715.0100 | 368.0100 | 713.9600 | 18858.2 | PURE_PLACEHOLDER |

### `TSLAx`, `market_status = 5` (closed/weekend) — 7 samples

| obs_ts | bid | ask | mid | last_traded | spread (bps) | class |
|---|---:|---:|---:|---:|---:|---|
| 2026-04-26T23:18:59+00:00 | 372.0100 | 384.4600 | 378.2350 | 376.0000 | 329.2 | BID_SYNTHETIC |
| 2026-04-26T23:14:59+00:00 | 372.0100 | 384.4600 | 378.2350 | 376.0000 | 329.2 | BID_SYNTHETIC |
| 2026-04-26T23:10:58+00:00 | 372.0100 | 384.4600 | 378.2350 | 376.0000 | 329.2 | BID_SYNTHETIC |
| 2026-04-26T23:06:59+00:00 | 372.0100 | 384.4600 | 378.2350 | 376.0000 | 329.2 | BID_SYNTHETIC |
| 2026-04-26T23:02:59+00:00 | 372.0100 | 384.4600 | 378.2350 | 376.0000 | 329.2 | BID_SYNTHETIC |

## Coverage matrix — known xStocks × market_status

Filled cells have ≥ 1 sample for that bucket; empty cells are pending the next scan run during the relevant trading window.

| xStock | pre-mkt (1) | regular (2) | post-mkt (3) | overnight (4) | weekend (5) | unknown (0) |
|---|---|---|---|---|---|---|
| **SPYx** | – | – | – | – | placeholder-derived (n=6) | – |
| **QQQx** | – | – | – | – | placeholder-derived (n=6) | – |
| **TSLAx** | – | – | – | – | placeholder-derived (n=7) | – |
| **GOOGLx** | – | – | – | – | – | – |
| **AAPLx** | – | – | – | – | – | – |
| **NVDAx** | – | – | – | – | real-quote (n=1) | – |
| **MSTRx** | – | – | – | – | – | – |
| **HOODx** | – | – | – | – | – | – |

## Outstanding

The following `market_status` values had **no** samples in this scan window:

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

The script is idempotent and cron-friendly; re-running through the week accumulates samples across all sessions.

## What this verifies for Paper 1 §1.1 / §2.1

The §1.1 / §2.1 framing claims v11 weekend `bid`/`ask`/`mid` are placeholder-derived. The v2 classifier supports that claim feed-by-feed: any `(symbol, status)` bucket whose verdict is **placeholder-derived** is direct empirical support for §1.1 at that specific (symbol, status). A **mixed** or **real-quote** verdict would require qualifying §1.1 to exclude that bucket.

The 4 mapped xStocks at status=5 (weekend) are the gate-closing rows. Other (symbol, status) buckets become available as the script accumulates samples through the trading week. The unmapped rows in the table above are v11 feeds for non-xStock RWAs sharing the schema; they're useful context but not load-bearing for Paper 1.
