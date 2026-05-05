# Soothsayer — Product Specification

**Date:** 2026-05-XX (updated for v2 / M5 deployment)
**Status:** Phase 1 — v2 / M5 Mondrian split-conformal-by-regime methodology shipping; devnet deploy + Paper 1 v2 to arXiv + Paper 3 first draft in progress.
**Driver:** `scripts/smoke_oracle.py` (end-to-end demo)

## The product in one sentence

**Soothsayer is a calibration-transparent oracle: we ingest upstream price/oracle signals and publish a calibrated band per symbol — point plus bounds plus a receipt — whose realised coverage rate can be checked against 12 years of public weekend data. Other oracles publish a number; Soothsayer publishes a number, a band, and a coverage claim, and stakes the product on that claim being verifiable from public data.**

## Status taxonomy

This spec uses three explicit status levels to keep "what's locked" separate
from "what we're still deciding."

- **Locked.** Calibrated band + receipts. Shipping in v1b; validated by Paper 1's
  12-year walk-forward backtest. Covered by every section between "Hybrid regime
  forecaster selection" and "The trust primitive" below.
- **Locked-pending Paper 3.** The policy mapping — a `Safe / Caution / Liquidate`
  ladder driven by the band and scored against reserve-buffer exhaustion. Shape
  committed; default thresholds lock once Paper 3's walk-forward evaluation
  resolves into a stable operating region. Covered in "Policy mapping" below.
- **Open hypothesis.** Other consumer-facing projections of the band — scalar,
  haircut, event stream, raw-band-direct. Each carries an explicit feedback gate
  that would move it from hypothesis to committed product. Covered in
  "Consumer-facing projections" below.

The band is the epistemic root. The consumable interface is a serving choice.
Paper 1 establishes the root; Paper 3 evaluates the primary projection (policy);
the others remain hypothesis until a gate fires.

## v2 / M5 Mondrian split-conformal-by-regime architecture

The deployed v2 / M5 architecture is a Mondrian split-conformal predictor (Vovk et al. 2003) keyed on the regime classifier:

- **Point estimator.** Friday close × (1 + factor return), where the factor is asset-class-matched (ES/NQ/GC/ZN/BTC). See Paper 1 §4.1 + §5.4.
- **Per-regime conformal quantile $q_r(\tau)$.** The empirical $\tau$-quantile of the absolute relative residual on the pre-2023 calibration set, stratified by regime $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$. Twelve trained scalars (3 regimes × 4 anchors).
- **OOS-fit multiplicative bump $c(\tau)$.** Smallest scalar such that pooled OOS realised coverage with effective quantile $c \cdot q_r$ matches the target $\tau$ at each anchor. Four scalars total (the v2 / M5 analogue of v1's `BUFFER_BY_TARGET`).
- **Walk-forward $\delta(\tau)$ shift.** Smallest schedule that aligns walk-forward realised coverage with nominal at every anchor. Four scalars total. Deployed: $\{0.05, 0.02, 0.00, 0.00\}$ at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$.

The Oracle's serving-time computation is a five-line lookup:

```python
tau_prime = tau + delta_shift_for_target(tau)
q_eff = c_bump_for_target(tau_prime) * regime_quantile_for(regime, tau_prime)
lower = point * (1 - q_eff)
upper = point * (1 + q_eff)
# `forecaster_used` is the literal string "mondrian" (on-chain forecaster_code = 2)
```

`forecaster_used` is preserved as a first-class receipt field on every PricePoint; under v2 / M5 it is constant `"mondrian"` (the wire-format `forecaster_code = 2` reuses the previously-reserved slot in the Borsh layout). At the consumer-facing target $\tau = 0.95$ on the 2023+ OOS slice, this delivers realised coverage $0.950$ at mean half-width $354.5$ bps — 20% narrower than the v1 hybrid Oracle at indistinguishable Kupiec calibration. See Paper 1 §6 + §7.7 for the full validation.

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

Soothsayer turns this into a feature by **exposing the claimed → realized
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

## Policy mapping (locked-pending Paper 3)

**Status.** Primary projection of the band into protocol action. Shape
committed; default thresholds lock once Paper 3's walk-forward evaluation
across cost grids and book schemes resolves into a stable operating region.
This is where Paper 3 spends its empirical evidence.

### Action ladder

```
Safe       — borrow / no action
Caution    — pause new borrows, demote, warn
Liquidate  — initiate liquidation
```

### Inputs

The mapping consumes:

- the calibrated band (`lower`, `upper`, `point`, `claimed_coverage_served`)
- a protocol cost model (missed-liquidation cost, false-liquidation cost,
  blocked-borrow / utilization cost)
- a portfolio weight scheme (account-weighted, debt-weighted, threshold-heavy)
- the protocol's reserve configuration (origination LTV → liquidation threshold
  gap), since reserve-buffer exhaustion is the truth metric — not abstract
  band coverage

### What's locked now

- the action vocabulary (`Safe / Caution / Liquidate`)
- the principle that defaults are chosen on out-of-sample expected loss
- the use of reserve-buffer exhaustion (rather than abstract band coverage) as
  the truth metric
- the requirement that any default ship as a robust *region*, not a single
  fragile threshold

### What locks when Paper 3 evidence lands

- specific threshold defaults (the τ region a protocol-class should serve at)
- regime-specific demotion rules (e.g. high-vol regime → wider buffer)
- recommended cost-model parameter ranges
- recommended book-weight priors

### Source of truth

Paper 3 plan (scope, claims, evaluation protocol):
[`reports/paper3_liquidation_policy/plan.md`](../reports/paper3_liquidation_policy/plan.md).
Demo implementation of the ladder against a Kamino-fork consumer:
`crates/soothsayer-demo-kamino/src/lib.rs`.

## Consumer-facing projections (open hypothesis)

The band is the epistemic root. Beyond the policy ladder above, the same band
can be projected to other consumable surfaces. Each below is a **hypothesis**
about what an integrating consumer would actually want — none are committed
product yet.

The framing: we publish whichever projection(s) make integration cheaper than
re-deriving them from the raw band. Each carries an explicit **feedback gate**
that would move it from hypothesis to commitment. When a gate fires, the
projection moves under "Policy mapping" semantics (locked-pending) or directly
to locked, depending on the evidence shape.

### Projection A — Raw band

- **Interface.** `lower`, `point`, `upper`, `claimed_coverage_served`,
  `forecaster_used`, `regime`, full receipt.
- **Status.** Already shipping as the §Locked primitive. Listed here for
  completeness in the projection enumeration.
- **Consumer archetype.** Risk teams, sophisticated protocols, research
  integrators.
- **Closest incumbent comparable.** None direct; closest is Chainlink point
  plus a self-built consumer wrap.
- **Feedback gate to commit "raw band is the right surface."** ≥1 design
  partner integrates against `lower` / `upper` directly and ships against that
  interface, without first asking us to derive a scalar or haircut for them.

### Projection B — Point + calibrated scalar

- **Interface.** `point` plus a single uncertainty scalar — half-width in bps,
  a calibrated risk score, or a coverage-class flag (`tight / wide / very wide`).
- **Hypothesis.** Pyth-style consumers want `price + conf` semantics, and a
  calibrated version of that scalar is a drop-in upgrade path. The band is
  retained internally; the publication shape is scalarized.
- **Closest incumbent comparable.** Pyth `price + conf`, Pyth `price + k·conf`,
  Chainlink point plus a consumer-side wrap.
- **Feedback gate to commit.** ≥1 design partner asks for "price + a number"
  rather than "lower / upper", or design-partner conversations consistently
  surface "we are not going to consume an interval."

### Projection C — Haircut-ready output

- **Interface.** `asset_safe_price` and `liability_safe_price` (or equivalent),
  pre-computed from the calibrated band — a calibrated drop-in for protocols
  already using conservative-valuation rules.
- **Hypothesis.** Lending protocols already think in conservative-valuation
  terms (MarginFi-style `P − conf` / `P + conf`, fixed-bps haircuts) and want a
  calibrated drop-in for that interface rather than a new conceptual object.
- **Closest incumbent comparable.** MarginFi-style haircuts, fixed-bps protocol
  defaults, simple stale-Gaussian wraps.
- **Feedback gate to commit.** ≥1 lending protocol says "we'd integrate if you
  published asset / liability safe prices directly", **or** Paper 3 surfaces
  evidence that haircut-shaped consumption captures most of the band's
  expected-loss gain (i.e. the interface is empirically as good as the policy
  ladder for a class of protocols).

### Projection D — Event stream

- **Interface.** Threshold-cross alerts, reserve-buffer-at-risk alerts,
  uncertainty-regime escalations.
- **Hypothesis.** Some consumers (ops teams, risk monitors, governance
  ladders) don't want continuous interval consumption; they want actionable
  triggers.
- **Closest incumbent comparable.** Ad-hoc Discord / PagerDuty wiring, manual
  risk dashboards, stale-threshold alerts.
- **Feedback gate to commit.** Explicit ask from an ops team or risk
  consultancy for a triggered surface, **or** internal evidence that the Phase 2
  comparator dashboard can drive useful alerts before continuous consumption is
  wired in by a design partner.

### Explicit non-claims for §3

- We are **not** running a Paper-3-scale empirical bake-off across all four
  projections. Paper 3 evaluates the policy mapping (the locked-pending §
  above). The other projections are hypothesis with explicit feedback gates,
  not parallel evaluation tracks. This is a deliberate scope choice; see the
  related discussion in the Paper 3 plan for why a five-way interface bake-off
  would dilute the closed-market reserve-buffer story.
- None of these projections becomes a published product surface absent its
  feedback gate firing. We do not pre-commit to publishing every interface
  the band can be projected to.

### Recording feedback against gates

When integration conversations or design partners surface a projection
preference, the signal goes in `reports/methodology_history.md` with a dated
entry under the relevant gate. When a gate fires, the projection migrates out
of this section — either into "Policy mapping" semantics (if the evidence
shape is Paper-3-like) or directly into the §Locked primitive (if the evidence
is integration-ready and gate-clean).

## What ships now vs. what's still to build

### Built (Phase 0, complete 2026-04-24)

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
