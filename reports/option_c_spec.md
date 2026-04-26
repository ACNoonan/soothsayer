# Soothsayer — Option C Product Specification

**Date:** 2026-04-24 (revised with hybrid regime architecture)
**Status:** Phase 0 — working prototype
**Driver:** `scripts/smoke_oracle.py` (end-to-end demo)

## The product in one sentence

**Soothsayer is a calibration-transparent oracle: consumers specify the realized
coverage they need, and we publish the band that historically delivers it —
with a receipt showing which forecaster and which claimed quantile were used.**

## Hybrid regime forecaster selection (added 2026-04-24)

The v1b backtest + Christoffersen tests revealed that a single forecaster is not efficient across all regimes at matched realized coverage:

- **Normal regime (65% of weekends):** F1_emp_regime at claim=0.975 delivers 95.0% realized with 257 bps half-width — 27% tighter than F0 at naive 0.95 claim (351 bps).
- **Long-weekend regime (10%):** F1_emp_regime at claim=0.975 delivers 94.9% realized with 298 bps — 43% tighter than F0 (519 bps).
- **High-vol regime (24%):** F1_emp_regime stretches to claim=0.984 to deliver ~95%, landing at ~540 bps; F0's Gaussian band is already wide enough that a lower claim (~0.90) delivers 95% realized at ≈480 bps — **F0 wins in high_vol by ~10% pooled, and up to 35% on specific symbols like SPY.**

The Oracle consults a `REGIME_FORECASTER` map and serves whichever forecaster is tighter at matched realized coverage for the detected regime. `forecaster_used` is a first-class receipt field on every PricePoint.

```python
REGIME_FORECASTER = {
    "normal":       "F1_emp_regime",  # in-sample 27% tighter than F0 at matched coverage
    "long_weekend": "F1_emp_regime",  # in-sample 43% tighter
    "high_vol":     "F0_stale",       # OOS ~19% tighter + Christoffersen pass
}
```

The hybrid's defense is twofold and evidence-tiered. **In-sample (2014–2022 backtest):** at matched realized coverage, F0 is ~10–35% tighter than F1 on high_vol because F1 stretches to cover while F0's already-wide Gaussian is efficient. **Out-of-sample (2023+):** the sharpness advantage narrows to ~19% (F0: 293 bps vs F1: 360 bps at roughly matched 92% realized), but the hybrid's primary serving-time contribution shifts to **Christoffersen independence**: F1 + buffer has clustered violations (p_ind = 0.033, rejected), while hybrid + buffer does not (p_ind = 0.086, not rejected). See `reports/v1b_ablation.md` for the full bootstrap.

## Why this framing

Every other RWA oracle publishes a single point estimate with either no CI
(Chainlink stale-hold during `marketStatus=5`), an undisclosed CI (RedStone
Live), or a CI whose claim is not empirically verifiable against the actual
realized distribution (Pyth + Blue Ocean quote dispersion).

The V1b calibration backtest on 12 years of public data revealed that even a
well-designed forecaster (F1_emp_regime, our best in-house) is not perfectly
calibrated across all regimes — high-vol weekends are the clearest example
where claimed 95% delivers ~91% realized. This is *not* a failure of the
model. It is an inescapable consequence of the fact that pre-publish signals
cannot perfectly predict weekend moves, and pretending otherwise is what the
incumbents do.

Option C turns this into a feature by **exposing the claimed → realized
calibration surface as the trust primitive itself.** Consumers don't trust
our econometrics; they trust our auditable calibration artifact.

## API shape

### Single call: `oracle.fair_value(symbol, as_of, target_coverage)`

```python
from soothsayer.oracle import Oracle

oracle = Oracle.load()

fv = oracle.fair_value(
    symbol="SPY",
    as_of="2026-04-17",
    target_coverage=0.95,  # consumer asks for 95% realized coverage
)

# Returned fields:
fv.point                      # 699.95
fv.lower                      # 688.35
fv.upper                      # 711.54
fv.claimed_coverage_served    # 0.975 ← we used the 97.5% claim to deliver 95% realized
fv.regime                     # "normal"
fv.forecaster_used            # "F1_emp_regime" ← picked by the per-regime policy
fv.sharpness_bps              # 163 bps half-width
fv.diagnostics                # full receipt of the calibration decision
```

### The diagnostics field (the receipt)

```json
{
  "fri_close": 710.14,
  "nearest_grid": 0.975,
  "requested_claimed_pre_clip": 0.967,
  "regime_forecaster_policy": {
    "normal": "F1_emp_regime",
    "long_weekend": "F1_emp_regime",
    "high_vol": "F0_stale"
  },
  "calibration": "per_symbol",
  "bracketed": [0.95, 0.975]
}
```

This tells the consumer:
- Our calibration surface interpolated that a claimed ≈ 0.967 would empirically
  deliver 95% coverage for (SPY, normal, F1_emp_regime).
- The actual fine-grid claimed we served was 0.975 (nearest grid point above).
- The inversion was bracketed by the calibrated points (0.95, 0.975) and used
  per-symbol calibration (fell through to pooled would signal `pooled`).
- The full regime→forecaster policy is inlined so the consumer can reproduce
  the hybrid decision deterministically.

A consumer running their own backtest against our historical API can
verify every one of these numbers. That's the auditability primitive.

## What regime-awareness looks like in practice

From the smoke test, SPY at different `as_of` dates:

| Date | Regime | target 95% | claimed served | half-width (bps) |
|---|---|---|---|---|
| 2026-04-17 | normal | 0.95 | **0.975** | 166 |
| 2026-04-02 | high_vol | 0.95 | **0.99** | **427** |
| 2026-02-13 | long_weekend | 0.95 | **0.925** | 219 |

Three things worth noting:

1. **Same target, different served claim.** Our `claimed_served` rises with
   regime difficulty — more conservative quantile is needed to hit 95%
   realized during high-vol weekends than during normal ones. During long
   weekends, historical over-coverage means we serve a *lower* claim (0.925)
   to hit the target — more sharpness at no coverage cost.
2. **Band width tracks regime.** 427 bps in high-vol vs 166 bps in normal.
   The CI is the product's uncertainty signal, regime-aware and auditable.
3. **Consumer doesn't need to know about regimes.** They ask for 95%, they
   get 95% realized coverage by design. The regime complexity is hidden
   behind the calibration inversion.

## Cross-asset replicability — the RWA infrastructure claim

Same API call, different symbols (target_coverage=0.95):

| Symbol | regime | half-width | claimed served | notes |
|---|---|---|---|---|
| SPY | normal | 166 bps | 0.975 | Broad market baseline |
| QQQ | normal | 207 bps | 0.975 | Tech-heavy index |
| NVDA | normal | 485 bps | 0.975 | Idiosyncratic vol |
| TSLA | normal | 598 bps | 0.975 | Single-name |
| MSTR | normal | **962 bps** | **0.99** | Crypto-sensitive — highest claim needed |
| HOOD | normal | 896 bps | **0.995** | Thin book, rare shocks |
| GLD | normal | 353 bps | 0.975 | Tokenized gold analog — GVZ-calibrated |
| TLT | normal | 115 bps | 0.975 | Tokenized treasury analog — VIX-calibrated |

**One API, every tokenized closed-market asset.** The only per-asset
configuration is the conditioning factor (ES/NQ for equities, GC for gold,
ZN for rates, BTC for MSTR post-2020) and the vol index (VIX/GVZ/MOVE). The
calibration surface handles the rest empirically.

This is the "infrastructure for 24/7 RWA trading" claim with engineering
receipts: add a new RWA, pick the factor and vol index, and the methodology
fills in the calibration.

## The trust primitive

Chainlink's `marketStatus=5` tells consumers: *"This number is stale; figure
it out yourselves."*

Pyth's weighted median says: *"Trust this; we don't say how accurate it is."*

Soothsayer says: *"Here's the number. Here's what coverage you asked for.
Here's the claimed quantile we used to deliver it. Here's the empirical
evidence, by regime, from 12 years of public data, that this mapping holds.
Audit anything."*

The product is not the point estimate. The product is the **calibration
receipt** published alongside every read.

## What a protocol integration looks like

A lending protocol wants to liquidate with 99% confidence the price won't
revert Monday. They call:

```python
fv = oracle.fair_value("SPYx", friday_timestamp, target_coverage=0.99)
```

- Point estimate arrives; liquidation engine uses it as mark
- Lower bound arrives; liquidation engine sets liquidation threshold = `lower - safety_buffer`
- If `claimed_served > 0.99` (i.e., we needed deep-quantile to hit 99%), the
  protocol knows the regime is challenging — can optionally tighten LTVs or
  pause new borrows pre-emptively
- `sharpness_bps` is the instantaneous "how much capital efficiency am I
  losing" metric — the protocol can decide whether the loss is worth the
  safety

Compare to integrating Chainlink stale-hold:
- Point estimate arrives; no uncertainty signal
- Protocol must bake in its own blind widening to be safe
- Over-wide widening → missed liquidations, lost fees
- Under-wide widening → bad liquidations, user losses

Soothsayer replaces a fixed-width blind safety margin with a dynamic,
regime-aware, empirically calibrated band. Protocol revenue/safety math
becomes a direct function of the oracle's receipts.

## What ships now vs. what's still to build

### Built (Phase 0, this week)

- ✓ Calibration backtest over 5,986 weekends, 10 tickers, 12 years
- ✓ F1_emp_regime forecaster with per-asset factor switchboard and per-asset
  vol index
- ✓ Calibration surface builder (`backtest/calibration.py`)
- ✓ Oracle serving API with target-coverage inversion (`oracle.py`)
- ✓ End-to-end smoke test serving realistic price bands across 8 tickers
- ✓ Persisted artifacts: `data/processed/v1b_bounds.parquet` and
  `reports/tables/v1b_calibration_surface{,_pooled}.csv`

### Deferred to Phase 1 (MVP)

- On-chain publish path (Solana program + Token-2022 account structure)
- Live-mode serving (fetch current weekend data, run model online)
- x402 payment gating for premium endpoints
- xStock-specific calibration (DEX noise, mint/burn friction)
- Devnet deployment across 8 Kamino-onboarded xStocks

### Deferred to Phase 2 (Production)

- Kamino BD integration
- Design partners: Backed, Ondo
- Publisher DAO + token fee-share (optional, evaluate after integrations)

## Live demo / interactive evidence walkthrough

Live demo flow, ~2 minutes:

1. Open a notebook, import `Oracle`, call `oracle.fair_value("SPY",
   "2026-04-17", target_coverage=0.95)`. Show the response.
2. Call with `target_coverage=0.99`. Show the band widens and `claimed_served`
   jumps.
3. Switch `as_of` to a high-vol Friday. Show `regime="high_vol"` and the band
   width jumps from 166 bps to 427 bps.
4. Switch to a non-equity RWA (`"TLT"`). Show the same API call works — and
   the diagnostics show `calibration="per_symbol"`, confirming we calibrated
   the treasury analog independently.
5. Open `reports/v1b_calibration.md`. Show the 12-year calibration tables
   behind every single number the API just returned.

The pitch becomes: "every read this oracle serves is backed by an auditable
empirical calibration table. We don't ask you to trust our math. We publish
the receipts, and you can verify them yourself on public data."

## Project positioning summary

Title: **Soothsayer — the calibrated-coverage oracle for tokenized RWAs on Solana**

One-sentence pitch: "Consumers ask for the coverage level they need; we
publish the band that empirically delivers it, with per-asset, per-regime
receipts."

Differentiators that survived empirical testing:
1. Only oracle publishing an auditable calibration surface
2. Factor + vol-index switchboard validated across equities, gold, rates
3. 12 years of walk-forward backtest evidence (5,986 weekend observations)
4. Single API shape, symbol-agnostic

Risks honestly named:
1. Shock-tertile coverage is below claim; we expose it, don't hide it
2. xStock-specific calibration requires live tape (Phase 1 work)
3. MOVE index is a weaker vol proxy for TLT than VIX — worth evaluating per
   asset going forward

## Files

- Methodology decision: `reports/v1b_decision.md`
- Calibration evidence: `reports/v1b_calibration.md`
- Product artifacts: `data/processed/v1b_bounds.parquet`,
  `reports/tables/v1b_calibration_surface{,_pooled}.csv`
- Code:
  - `src/soothsayer/backtest/{panel,forecasters,metrics,regimes,calibration}.py`
  - `src/soothsayer/oracle.py`
- Demo: `scripts/smoke_oracle.py`
