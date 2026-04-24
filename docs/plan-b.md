# Plan B — Chainlink xStocks Quality Monitor

> **Status note (2026-04-24):** Plan B is no longer "the" pivot. The actual validation landed as a different pivot — see [`reports/v1b_decision.md`](../reports/v1b_decision.md) and [`reports/option_c_spec.md`](../reports/option_c_spec.md). The v1b methodology (factor-switchboard + empirical-quantile CI + log-log VIX regime) replaced the Madhavan-Sobczyk / VECM / HAR-RV / Hawkes stack, and the product reframed from "secondary oracle competing on methodology" to "calibration-transparent oracle with customer-selects-coverage." Plan B (this document) is retained as a **parallel exploration track** — the V5 tape it describes is still valuable as the data feed for Phase 1's xStock-specific calibration overlay, but the "quality monitor as the product" framing has been superseded by Option C.

**Status:** candidate pivot, under evaluation. Not committed. Gating evidence is V5 (see below).

## Why reconsider

Soothsayer's original thesis (per `README.md`) is a secondary oracle publishing a confidence interval around incumbent oracles during closed-market windows. The premise was that incumbents either publish nothing off-hours or publish an opaque 24/7 median.

Chainlink Data Streams for xStocks went live on Solana mainnet on **2026-01-26** with apparently continuous pricing across weekends and overnights. This weakens (does not kill) the premise: "nobody prices these off-hours" becomes "one provider does, but we don't know how accurate it is, nor does anyone publish a quality signal alongside it." That shifts the product question from *build a better oracle* to *monitor the existing oracle and capitalize on its gaps*.

## The pivot, one sentence

Soothsayer becomes a **Chainlink xStocks quality monitor** that publishes (a) a fair-value composite derived from yfinance / futures / DEX flow, (b) a continuous basis measurement against Chainlink's published mid, and (c) signals when the basis exceeds tradeable thresholds. Same infrastructure. Different deliverable.

## What stays from Plan A

- Phase 0 validation-first workflow (Python, no Rust yet)
- Free-only data stack (yfinance, Kraken REST, Helius free tier, Jupiter free tier)
- xStock universe: SPYx, QQQx, TSLAx, GOOGLx, AAPLx, NVDAx, MSTRx, HOODx
- V1 weekend-bias work is directly relevant — it's *one* of the five divergence axes in V5
- Chainlink scraper, v10/v11 decoders, Verifier parser (already built)
- Fair-value modelling (Madhavan-Sobczyk, HAR-RV, Hasbrouck) — the *composite* in (a) above

## What changes

- **Primary deliverable**: quality-monitor dashboard + signal generator, not an oracle consumers read. A trading/monitoring artifact, not infrastructure.
- **New data source**: Jupiter quote API (or direct pool reads) for DEX mid. Captured in `sources/jupiter.py`.
- **New validation test (V5)**: can we detect divergence patterns wide enough and persistent enough to generate a tradeable signal after fees?
- **Success criterion**: reframed from "oracle bias detectable at 10 bps / p<0.05" to "edge captureable after round-trip fees (~30 bps realistic on Jupiter for this size class)".

## V5 — the gating test for this pivot

Same structure as V1–V4: `notebooks/V5_*.ipynb` → `scripts/analyze_v5.py` → `reports/v5_*.md` with go/no-go.

**Hypothesis (H9):** Chainlink's xStock mark diverges from a realistic fair-value composite in patterns that are (i) wider than round-trip fees, (ii) persistent for >1 minute, (iii) not self-referential (CL not merely mirroring DEX).

**Five axes, one notebook:**

1. **CL vs yfinance — regular hours.** Baseline oracle lag. Should be tight (<5 bps). A surprise here invalidates downstream axes.
2. **CL vs yfinance — extended hours (4–9:30 AM ET, 4–8 PM ET).** Real volume, real price discovery. Where weekend bias likely *originates* — bias doesn't start Sunday, it starts at Friday 4 PM.
3. **CL vs DEX mid — continuous.** The core arb signal. Jupiter quote for `{xStock}/USDC`, polled at 1-minute cadence. Thresholds: |basis| > 30 bps gets flagged.
4. **CL vs DEX — weekend-specific.** Underlying dark, CL can only lean on something (DEX? futures? synthetic from correlated ETFs?). If CL is downstream of DEX, basis → 0 by construction and the pivot dies.
5. **Event windows.** Earnings, splits, halts. Only ~3 months of CL history since 2026-01-26; enumerate and eyeball rather than test statistically.

**Data strategy under free-tier rate limits:**

- Don't backfill. Poll forward at 1-minute cadence. ~11,500 samples/day across 8 feeds + DEX, well within Helius free budget.
- CL side: reuse `fetch_latest_per_xstock(lookback_hours=1)` from `src/soothsayer/chainlink/scraper.py:266` **only for the smoke test**. Each cold call walks Verifier sigs backward — measured ~95 s for one xStock on Helius free tier. The actual tape daemon needs a **forward cursor design**: remember the latest Verifier signature seen on the prior tick, then walk only `(last_sig, now]` each minute. That turns ~95 s per feed into ~1 s for the delta. Factor this in when writing `scripts/run_v5_tape.py`.
- DEX side: Jupiter quote API is free, unmetered, no key.
- Writer: append daily parquet partitions `data/raw/v5_tape_YYYYMMDD.parquet`, never rewrite.
- Runner: long-running daemon (`scripts/run_v5_tape.py`) with `PYTHONUNBUFFERED=1`. Let it run ~1 week before committing to pivot.

## Falsifiers (conditions that kill Plan B)

- **Basis too tight**: |CL − DEX mid| < 30 bps median, mean-reverts in <1 minute → no edge after fees.
- **Self-referential oracle**: basis against DEX is ~0 by construction, meaning CL derives from or arbitrages against the DEX pools we're comparing to.
- **Primary-market gate closed**: even if basis is wide off-hours, if Backed's mint/burn window is only open US market hours, the arb is inaccessible to anyone without secondary liquidity and a balance sheet.
- **V1 result is strong**: paradoxically — if weekend bias (V1) is already cleanly tradeable as a standalone Monday-open signal, Plan A's original framing is validated and we don't need the quality-monitor reframe.

## Open risks

- **Regulatory**: tokenized-equity trading is jurisdiction-sensitive. Hackathon demo is fine; productionizing a bot is not. Plan B leans harder on this risk than Plan A.
- **Demo narrative for Colosseum**: "oracle quality monitor" is more compelling than "arb bot" (public good framing, not extractive). Frame the signal as quality-transparency, with the trading strategy as a *validation* that the signal is real.
- **Sample size**: only ~3 months of CL history on xStocks. Most statistical claims will be tentative.

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

## Execution checklist

- [x] Verify xStock mint addresses on-chain (2026-04-22)
- [x] Allow `lite-api.jup.ag` in sandbox (`quote-api.jup.ag` turned out to be decommissioned — NXDOMAIN. Jupiter consolidated the free API under `lite-api.jup.ag/swap/v1/quote` in 2026)
- [x] `src/soothsayer/sources/jupiter.py` — quote wrapper, `XSTOCK_MINTS`, one-sided and two-sided mid helpers
- [x] One-shot smoke test: 3 snapshots on SPYx, basis −3.7 / +2.3 / +6.4 bp. Non-zero, non-absurd, sign-flipping — consistent with noisy but tight coupling. Pivot not yet disproved (2026-04-23 / 2026-04-24).
- [x] Resolve CL v10 bid/ask = 0 **turned out to be a decoder bug, not an on-chain fact** (2026-04-24). v10 on Solana is Chainlink's "Tokenized Asset" schema — NOT the order-book-bearing "RWA Advanced" v11 schema. Actual v10 fields are `price`, `marketStatus`, `currentMultiplier`, `newMultiplier`, `activationDateTime`, `tokenizedPrice`. There is no bid/ask in v10. `chainlink/v10.py` and the scraper's yielded dict now reflect the correct schema. **V5 compares Jupiter mid against `tokenized_price` (24/7 CEX mark), not the old "mid".**

### V1 is now suspect and must be re-run before interpretation

Under the old (wrong) decoder, V1 treated w7 as "mid". But w7 is `price` — the NYSE last-trade, which is **frozen when the underlying is closed**. On Sunday evening, w7 for SPYx equals the Friday NYSE close, not any weekend-moved CL consensus. That means V1's residual `e_T = ln(NYSE_Mon_open / NYSE_Fri_close) − ln(CL_Sun_last / NYSE_Fri_close)` collapsed to `ln(NYSE_Mon_open / NYSE_Fri_close) − 0` — i.e., V1 was measuring the realised Monday gap itself, with no Chainlink content. Any V1 result from before 2026-04-24 is uninterpretable.

To re-run V1 meaningfully, `run_v1_scrape.py` / `run_v1_backfill.py` / `analyze_v1.py` need their `cl_mid` column replaced with `tokenized_price` (not just renamed — the semantics are what changed). This is a separate task from the V5 tape; flag if V1 becomes relevant again, otherwise leave the scripts broken as a forcing function.
- [ ] FASTRPC wiring in progress by another agent — replaces Helius free-tier RPC path. Unblocks tape daemon by turning ~75 s cold-scrape per feed into sub-second delta.
- [ ] `scripts/run_v5_tape.py` — forward-cursor daemon (maintain last-seen Verifier sig per feed, only walk the delta each minute). Needs FASTRPC first.
- [ ] Run tape ≥5 days to capture ≥1 full weekend cycle
- [ ] `scripts/analyze_v5.py` — per-axis charts + pooled stats, go/no-go writeup to `reports/v5_cl_quality.md`
- [ ] Decision: commit to Plan B, revert to Plan A, or abandon hackathon submission
