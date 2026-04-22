# Plan B — Chainlink xStocks Quality Monitor

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
- CL side: reuse `fetch_latest_per_xstock(lookback_hours=1)` from `src/soothsayer/chainlink/feeds.py:266`. First-seen short-circuit means ~8 credits/minute.
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
- [ ] Allow Jupiter hosts in sandbox (`tokens.jup.ag`, `quote-api.jup.ag`, `lite-api.jup.ag`)
- [ ] `src/soothsayer/sources/jupiter.py` — quote wrapper + `XSTOCK_MINTS` constant
- [ ] One-shot smoke test: live CL mid vs Jupiter mid for one feed, log basis
- [ ] If smoke basis is non-zero and non-absurd: write `scripts/run_v5_tape.py` daemon
- [ ] Run tape ≥5 days to capture ≥1 full weekend cycle
- [ ] `scripts/analyze_v5.py` — per-axis charts + pooled stats, go/no-go writeup to `reports/v5_cl_quality.md`
- [ ] Decision: commit to Plan B, revert to Plan A, or abandon hackathon submission
