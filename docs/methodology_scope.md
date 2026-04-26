# Soothsayer methodology scope — what fits and what does not

**Status:** living doc; pinned to Paper 1 §9.10 and §10.5.
**Audience:** protocol integrators, risk teams, paper reviewers, and prospective adopters evaluating whether the calibration-transparency primitive applies to their RWA class.

## The one-line filter

The methodology fits any RWA class with a **continuous off-hours information set** — a public, free, sub-daily price signal that is observably correlated with the closed-market underlier and that remains observable while the primary venue is closed. Where this requirement is satisfied, the same factor-switchboard + log-log volatility-regime architecture validated in Paper 1 §6 generalises by construction; where it is not, the methodology does not apply and we do not claim it does.

## What fits (in scope)

| Class | Closed-market window | Continuous off-hours signal | Factor switchboard candidate | Vol-index candidate | Status |
|---|---|---|---|---|---|
| US equities (single names) | weekends + after-hours | E-mini S&P / Nasdaq futures (`ES=F`, `NQ=F`); overseas equity sessions for ADR-eligible names | ES=F, NQ=F | VIX | **Validated in Paper 1** (10 symbols, 12 years) |
| US equity ETFs | same | same | ES=F, NQ=F | VIX | **Validated** (SPY, QQQ in paper) |
| Tokenized gold | weekends + COMEX off-hours | gold futures (`GC=F`); spot continues 23/5 | GC=F | GVZ (CBOE Gold ETF Volatility Index) | **Validated** (GLD anchor in paper) |
| Tokenized US treasuries | weekends; Treasury futures trade Sunday 18:00 ET to Friday 17:00 ET | 10Y / 5Y / 2Y T-note futures (`ZN=F`, `ZF=F`, `ZT=F`) | ZN=F + duration scaling | MOVE Index | **Validated** (TLT anchor in paper) |
| Tokenized BTC-proxy equities | weekends | BTC perpetual + BTC spot, 24/7 | BTC-USD | VIX (or BVOL once liquid) | **Validated** (MSTR anchor in paper, with 2020-08 BTC pivot) |
| Tokenized non-US equities (LSE / TSE / HK) | each region's own weekend | overseas-session futures (`FTSE`, `^N225`, `HSI`) | per-region futures | per-region vol indices (`^VFTSE`, `^VXJ`) | **In-scope; pending replication** (Paper 1 §10.5) |
| Tokenized commodity baskets (silver, copper, oil) | weekends; futures trade through | per-commodity futures (`SI=F`, `HG=F`, `CL=F`) | per-commodity factor | OVX (Crude Oil VIX), where it exists | **In-scope; pending data accumulation** |
| Tokenized FX pairs | major-region holiday closures | overseas-session FX prices, 24/5 | spot FX | currency-pair implied vol where observable | **In-scope; methodology compatible** |
| Tokenized credit (CDS-referenced products) | weekends + region closures | CDX / iTraxx index spreads + index vol | CDX index level | MOVE or CDX-specific implied vol | **In-scope, modulo data licensing** (CDS feeds are not always free-tier) |

## What does not fit (out of scope)

| Class | Why the methodology does not apply |
|---|---|
| **Tokenized real estate** (REIT-backed, fractional-ownership) | No continuous off-hours information set exists. NAV updates are discrete (monthly / quarterly / annual). The closed-market problem here is *structural absence of signal*, not *staleness of signal*. A different methodology is required. |
| **Illiquid agricultural commodities** | Futures markets exist but are thinly traded or discontinuous. The factor regression's $\hat\beta$ on the underlier becomes unstable; the empirical-quantile residual distribution is too sparse to invert reliably. |
| **Money-market-style tokens** (yield-bearing stablecoin variants) | Price is administratively set rather than market-observed. There is no "fair value" question to calibrate against — the claim is the protocol's, not the market's. |
| **Tokenized art, collectibles, IP rights** | Auction-cadence pricing; no continuous information set; thin observation count. Outside the methodology's domain. |
| **Tokenized private credit (loan-by-loan)** | Discrete payment events drive valuation; there is no continuous off-hours volatility regime to estimate. The empirical-quantile residual model has no domain to fit on. |

## The structural test

For any candidate RWA class, ask:

1. **Does the underlier have a primary venue that closes for material wall-clock periods?** If no, calibration over closed-market windows is unnecessary. If yes, continue.

2. **Is there a public, free, sub-daily price signal that remains observable while the primary venue is closed and that is correlated with the underlier?** If no, the methodology does not apply (out of scope above). If yes, continue.

3. **Are there ≥ ~150 historical closed-market windows of joint underlier + signal data?** This is the rolling per-(symbol, regime) window required for the calibration surface inversion to be statistically resolvable. If no, the class is *future-in-scope* and waits on data accumulation. If yes, continue.

4. **Is there an implied-volatility index (or analog) for the underlier?** Strictly required for the F1 log-log regression that produces conditional sigma. If no, F0 stale-Gaussian still works as a fallback forecaster, but the high-volatility regime tightening of Paper 1 §7.3 is unavailable.

If steps 1–3 pass, the calibration-transparency primitive applies. Step 4 affects which forecaster set the regime cascade has access to but not the primitive's applicability.

## Why we publish this

The "missing infrastructure layer" claim of Paper 1 §1 is broader than what we have empirically validated (US equities + GLD + TLT + MSTR with BTC pivot). The honest version of the claim requires being explicit about which classes are within the methodology's domain and which are not, before institutional adopters or paper reviewers infer overclaim. This document is that explicit per-class enumeration.

If you are evaluating whether Soothsayer applies to a specific tokenized RWA you are issuing or integrating, the structural test above is the four-question filter; the per-class table is the quick lookup. If your class is in-scope but not yet validated (e.g., tokenized FX, tokenized commodity baskets), the work is a re-fit of the calibration surface on a new `(factor, vol_index)` pair — no methodology change is required, and the resulting calibration receipts are directly auditable against public data via the same Kupiec / Christoffersen disclosure framework as Paper 1 §6.

## See also

- Paper 1 §1 — the missing-layer framing
- Paper 1 §5.4 — `FACTOR_BY_SYMBOL` and `VOL_INDEX_BY_SYMBOL` switchboards
- Paper 1 §9.10 — explicit out-of-scope disclosure (region + asset class)
- Paper 1 §10.5 — scope expansion as future work
- `src/soothsayer/sources/jupiter.py` — current xStock mint registry (the immediate Solana adopter set)
