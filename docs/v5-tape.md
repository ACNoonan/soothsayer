# V5 Tape — xStock Operational Notes

**Status:** Phase 1 data infrastructure. Feeds the V2.1 F_tok forecaster (see [`docs/v2.md`](v2.md)) and the Phase 2 comparator dashboard. Not a methodology decision — the v1b oracle ships without it.

This doc covers: (1) the V5 tape daemon design, (2) the verified xStock mint universe, and (3) the Chainlink decoder schema corrections from 2026-04-24 (which retired V1 and reshape how we compare against live Chainlink).

> **Historical context.** This file replaces `docs/plan-b.md`, which evaluated a "Chainlink xStock quality monitor" pivot in early April 2026. That pivot was not taken — Option C (calibration transparency) won instead, see [`reports/v1b_decision.md`](../reports/v1b_decision.md) and [`reports/option_c_spec.md`](../reports/option_c_spec.md). The operational content (V5 tape design, mints, decoder schema) survives here because it's still load-bearing for Phase 1.

## V5 tape daemon

The V5 tape is a 1-minute parquet log of (Chainlink xStock mark, Jupiter DEX mid) pairs across the 8-xStock universe. It runs continuously and feeds two downstream uses:

- **V2.1 F_tok forecaster** — once ≥150 weekends of tape are collected (ETA Q3-Q4 2026), the on-chain xStock TWAP becomes a third forecaster in the hybrid stack alongside F1_emp_regime and F0_stale.
- **Phase 2 public comparator dashboard** — Soothsayer vs Chainlink vs Pyth across every weekend of 2025–2026.

### Design

- **Cadence.** 1-minute polling. ~11,500 samples/day across 8 feeds + DEX, well within Helius free budget.
- **Cursor design.** Forward cursor, not backfill. Each tick, walk only `(last_sig, now]` per feed — turns ~95s cold-scrape per feed into sub-second delta. The naive `fetch_latest_per_xstock(lookback_hours=1)` from `src/soothsayer/chainlink/scraper.py` is for smoke tests only; production daemon (`scripts/run_v5_tape.py`) maintains a per-feed last-seen Verifier signature.
- **Storage.** Daily parquet partitions: `data/raw/v5_tape_YYYYMMDD.parquet`. Append-only, never rewrite.
- **Runner.** Long-running daemon with `PYTHONUNBUFFERED=1`:

```bash
nohup uv run python -u scripts/run_v5_tape.py > /tmp/v5_tape.log 2>&1 &
```

- **DEX side.** Jupiter quote API (`lite-api.jup.ag/swap/v1/quote`) — free, unmetered, no key. The older `quote-api.jup.ag` was decommissioned (NXDOMAIN); Jupiter consolidated under `lite-api.jup.ag` in 2026.
- **CL side.** Compares Jupiter mid against `tokenized_price` (the 24/7 CEX mark Chainlink publishes via the v10 schema), NOT a synthetic "mid" from bid/ask — see decoder section below.

### Five tape axes (for the Phase 2 comparator)

The original V5 design enumerated five divergence axes. They survive as the structure for the Phase 2 comparator dashboard, not as go/no-go gates:

1. **CL vs yfinance — regular hours.** Baseline oracle lag (<5 bps expected).
2. **CL vs yfinance — extended hours (4–9:30 AM ET, 4–8 PM ET).** Real-volume price-discovery window.
3. **CL vs DEX mid — continuous.** The core off-hours basis signal. Threshold: |basis| > 30 bps gets flagged.
4. **CL vs DEX — weekend-specific.** Whether CL leans on DEX during dark hours, or has an independent off-hours mark.
5. **Event windows.** Earnings, splits, halts. Enumerate-and-eyeball; statistical power is limited by ~3 months of CL history.

## Verified xStock mints (2026-04-22)

All 8 verified on-chain via Helius RPC (`getAccountInfo` + `getTokenSupply`). Token-2022 program (`TokenzQd…`), 8 decimals, on-chain metadata symbols match exactly.

| Symbol | Mint | Supply at verification |
|---|---|---|
| SPYx   | `XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W` | 53,036 |
| QQQx   | `Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ` | 58,527 |
| TSLAx  | `XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB` | 156,639 |
| GOOGLx | `XsCPL9dNWBMvFtTmwcCA5v3xWPSMEBCszbQdiLLq6aN` | 117,650 |
| AAPLx  | `XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp` | 105,108 |
| NVDAx  | `Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh` | 231,317 |
| MSTRx  | `XsP7xzNPvEHS1m6qfanPUGjNmdnmsLKEoNAnHjdxxyZ` | 225,252 |
| HOODx  | `XsvNBAYkrDRNhA7wPHQfX3ZUXZyZLdnCQDfHZ56bzpg` | 263,394 |

USDC on Solana: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`.

## Chainlink v10 vs v11 decoder schema

Resolved 2026-04-24. Pre-fix, the scraper was treating v10 like v11 (assuming bid/ask/mid). v10 is a different schema with no order book.

### v10 — "Tokenized Asset" schema (xStocks)

Fields: `price`, `marketStatus`, `currentMultiplier`, `newMultiplier`, `activationDateTime`, `tokenizedPrice`.

- `price` is the NYSE last-trade — **frozen when the underlying market is closed**.
- `tokenizedPrice` is Chainlink's **continuous 24/7 CEX mark** (undisclosed methodology).
- There is no bid/ask. `chainlink/v10.py` and the scraper's yielded dict reflect the corrected schema.

### v11 — "RWA Advanced" schema

Has bid/ask/mid. Different feed family from v10.

### What this changed

**V1 (Chainlink weekend bias) was retroactively invalidated.** Pre-fix V1 used `w7` as "mid" but `w7` is `price`. On Sunday evening, `w7` for SPYx equals the Friday NYSE close, so V1's residual `(Mon_open − Fri_close) − (Sun_last_mid − Fri_close)` collapsed to `(Mon_open − Fri_close) − 0` — measuring the realized Monday gap with zero Chainlink content. **Don't cite V1 numbers.** v1b on yfinance underlyings supersedes V1 on a different data substrate; nothing in v1b reads Chainlink, so v1b is unaffected.

**Live Chainlink xStocks is NOT the stale-hold archetype.** Chainlink Data Streams for xStocks went live 2026-01-26 publishing `tokenized_price` continuously. Our F0 stale-hold remains a valid academic baseline (and is what we report 28%-tighter against), but live Chainlink xStocks is structurally closer to RedStone Live ("continuous undisclosed mark") than to true stale-hold. The Phase 2 comparator should compare against `tokenized_price`, not synthetic stale-hold. README and Paper 1 §1/§2 framing should be threaded with this nuance — calibration transparency is the live differentiator, sharpness vs F0 is the academic one.

## Open execution items

- [ ] FASTRPC wiring — replaces Helius free-tier path for the cold-scrape problem.
- [ ] `scripts/run_v5_tape.py` — forward-cursor daemon (depends on FASTRPC).
- [ ] Run tape ≥5 days to capture ≥1 full weekend cycle (V2.1 trigger needs ≥150 weekends).
- [ ] `scripts/analyze_v5.py` — per-axis charts + pooled stats for the Phase 2 comparator dashboard.

## Done

- [x] Verify xStock mint addresses on-chain (2026-04-22)
- [x] Allow `lite-api.jup.ag` in sandbox; map old `quote-api.jup.ag` deprecation
- [x] `src/soothsayer/sources/jupiter.py` — quote wrapper, `XSTOCK_MINTS`, mid helpers
- [x] V5 smoke test: 3 SPYx snapshots, basis −3.7 / +2.3 / +6.4 bp (sign-flipping, consistent with tight coupling)
- [x] Chainlink v10 decoder corrected to actual schema (2026-04-24)
