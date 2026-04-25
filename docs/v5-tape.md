# V5 Tape — xStock Operational Notes

**Status:** Phase 1 data infrastructure. Feeds the V2.1 F_tok forecaster (see [`docs/v2.md`](v2.md)) and the Phase 2 comparator dashboard. Not a methodology decision — the v1b oracle ships without it.

This doc covers: (1) the V5 tape daemon design, (2) the verified xStock mint universe, and (3) the Chainlink Data Streams schema reality on Solana — empirically established 2026-04-25 across both v10 and v11 feeds.

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
- **CL side.** Currently logs only v10 fields (`cl_tokenized_px` = w12, `cl_venue_px` = w7). Does NOT log v11. If Phase 2 comparator wants v11 data, the daemon needs to be extended to filter both schemas and log v11 mid/bid/ask/last_traded.

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

## Chainlink Data Streams — schema reality on Solana (verified 2026-04-25)

Both v10 (Tokenized Asset, schema `0x000a`) and v11 (RWA Advanced, schema `0x000b`) are active on Solana. The plan-b doc and pre-2026-04-25 framing were partial. Empirical scan: `scripts/scan_chainlink_schemas.py`; data: `data/raw/v5_tape_*.parquet`.

### Field-level cadence (Saturday 2026-04-25, market_status = closed/weekend)

| Schema | Field | Weekend behaviour | Source of truth |
|---|---|---|---|
| v10 (`0x000a`) | `price` (w7) | Frozen at Friday NYSE close | NYSE last-trade — regular session only |
| v10 (`0x000a`) | **`tokenized_price` (w12)** | **Continuous sub-second updates 24/7** | CEX-aggregated mark (methodology to verify in Chainlink docs) |
| v11 (`0x000b`) | `mid` | (bid + ask) / 2 of placeholder bookends | Derived, not a real mark |
| v11 (`0x000b`) | `bid` / `ask` | Synthetic min/max placeholders (e.g. 21.01 / 715.01 for SPY-class feed) | Not real market quotes |
| v11 (`0x000b`) | `last_traded_price` | Frozen at Friday NYSE close | Same archetype as v10 `price` |

**Net: v10's `tokenized_price` is the only Chainlink field across either schema that updates continuously on weekends.** Everything else is stale at Friday close, and v11 weekend `bid`/`ask`/`mid` are placeholder-derived rather than real prices.

### v10 Tokenized Asset schema (xStocks)

Fields: `feedId, validFromTimestamp, observationsTimestamp, nativeFee, linkFee, expiresAt, lastUpdateTimestamp, price, marketStatus, currentMultiplier, newMultiplier, activationDateTime, tokenizedPrice`. `marketStatus` codes: `0 Unknown, 1 Closed, 2 Open` — coarse; doesn't distinguish weekend / overnight / halt.

`chainlink/v10.py` and the V5 tape's yielded dict reflect this schema. Eight xStock feed_ids enumerated in `chainlink/feeds.py`.

### v11 RWA Advanced schema (active on Solana, distinct feed_ids)

Fields: `feedId, validFromTimestamp, observationsTimestamp, nativeFee, linkFee, expiresAt, mid, lastSeenTimestampNs, bid, bidVolume, ask, askVolume, lastTradedPrice, marketStatus`. `marketStatus` codes: `0 Unknown, 1 Pre-market, 2 Regular, 3 Post-market, 4 Overnight, 5 Closed (weekend)` — fine-grained.

The 8-xStock feed_ids in `chainlink/feeds.py` are v10-only (prefix `0x000a`). v11 publishes under different feed_ids (`0x000b`-prefixed) — likely covering the same underlyings, but the symbol mapping needs verification. Feed-id enumeration deferred until we need to consume v11 (currently only v10 is in production code paths).

### What this changes — and what it doesn't

**V1 (Chainlink weekend bias) was retroactively invalidated.** Pre-fix V1 used `w7` as "mid" but `w7` is `price`. On Sunday evening, `w7` for SPYx equals the Friday NYSE close, so V1's residual `(Mon_open − Fri_close) − (Sun_last_mid − Fri_close)` collapsed to `(Mon_open − Fri_close) − 0` — measuring the realized Monday gap with zero Chainlink content. **Don't cite V1 numbers.** v1b on yfinance underlyings supersedes V1 on a different data substrate; nothing in v1b reads Chainlink, so v1b is unaffected.

**Two competitor archetypes coexist in Chainlink, depending on which field/schema a consumer reads.** This refines (but doesn't overturn) the README + Paper 1 §2 framing:

- A consumer reading **v10 `price`** or **any v11 field** sees stale-hold semantics on weekends — exactly what F0 stale-hold models. The "Chainlink stale-hold during marketStatus=5" framing is correct *for these fields*, which is what most lending integrations historically consume.
- A consumer reading **v10 `tokenized_price`** sees a continuous CEX-aggregated mark with undisclosed methodology — same archetype as RedStone Live.

So Soothsayer has two pitches against Chainlink:
- vs `price` (or v11): tighter band + auditable calibration claim (the 28%-tighter-than-stale-hold story holds).
- vs `tokenized_price`: same temporal coverage, but Soothsayer publishes an auditable calibration claim while `tokenized_price` is undisclosed.

**Phase 2 comparator dashboard should evaluate against ALL three: v10 `price`, v10 `tokenized_price`, and v11 `mid`/`last_traded_price` separately.** This gives the most honest picture and forecloses the "you didn't compare against the right Chainlink field" objection.

### Open empirical question

Our 2026-04-25 scan only covered weekend state (market_status = 5 for v11; market_status = 1 for v10). We have not yet observed v11 behaviour during the 24/5 windows (pre-market, regular, post-market, overnight). The user's claim that v11 has "sub-second updates across all 24/5 sessions" is plausible but unverified.

Verification task scheduled — see `docs/ROADMAP.md` Phase 1 → Methodology / verification.

## Open execution items

- [ ] Monday 2026-04-27 morning ET — verify v11 24/5 cadence (pre-market 04:00-09:30 ET = 08:00-13:30 UTC). Re-run `scripts/scan_chainlink_schemas.py` and check whether v11 `mid`/`bid`/`ask` carry real values during pre-market state.
- [ ] Map v11 feed_ids → xStock symbols (defer until needed for Phase 2 comparator).
- [ ] Extend `scripts/run_v5_tape.py` to log v11 fields alongside v10 (defer until Phase 2 comparator design).
- [ ] FASTRPC wiring — replaces Helius free-tier path for the cold-scrape problem.
- [ ] `scripts/analyze_v5.py` — per-axis charts + pooled stats for the Phase 2 comparator dashboard.

## Done

- [x] Verify xStock mint addresses on-chain (2026-04-22)
- [x] Allow `lite-api.jup.ag` in sandbox; map old `quote-api.jup.ag` deprecation
- [x] `src/soothsayer/sources/jupiter.py` — quote wrapper, `XSTOCK_MINTS`, mid helpers
- [x] V5 smoke test: 3 SPYx snapshots, basis −3.7 / +2.3 / +6.4 bp (sign-flipping, consistent with tight coupling)
- [x] Chainlink v10 decoder corrected to actual schema (2026-04-24)
- [x] **Verified v10 `tokenized_price` updates continuously on weekends** (2026-04-25, 1021 distinct values across 30h Fri+Sat sample)
- [x] **Verified v11 IS active on Solana** (2026-04-25, ~1.6% of recent Verifier txs are schema 0x000b)
- [x] **Verified v11 weekend payload is placeholder-derived** (2026-04-25, bid/ask are synthetic bookends, mid is derived, last_traded frozen)
