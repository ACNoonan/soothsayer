# Kamino xStocks — weekend comparator: 2026-04-24 → 2026-04-27
*Generated 2026-04-27T14:34:30.712210+00:00; reserve config snapshot from 2026-04-27.*
Forward-running comparator that scores Soothsayer bands and free-data baselines against the realized Monday open under Kamino's actually-deployed xStock reserve parameters. All 8 xStocks live in lending market `5wJeMrUYECGq41fxRESKALVcHnNX26TAWy4W98yULsua` and consume Scope as the primary oracle. The numbers below are reproducible from the on-chain klend program (`KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD`) via `scripts/snapshot_kamino_xstocks.py` + `scripts/score_weekend_comparison.py`.
## Section 1 — What was observed
Per-symbol Friday close (yfinance underlier), Monday open (yfinance underlier), Kamino reserve config (LTV at origination / liquidation threshold / heuristic guard rail), and weekend tape coverage. Kamino's `PriceHeuristic` is a *validity guard rail* — Scope reads outside the range are rejected — not a coverage band, so it is reported here as a recorded incumbent parameter rather than scored against the realized move.
| Symbol | Reserve PDA | LTV / liq | Gap (pp) | Heuristic guard rail | Fri close | Mon open | Realized (bps) | V5 tape obs | Scope tape obs |
|---|---|---|---:|---|---:|---:|---:|---:|---:|
| **SPYx** | `UvXjBuC7…` | 73 / 75 | 2 | \[\$515, \$858\] | \$713.94 | \$713.17 | -10.8 | 1466 | 0 |
| **QQQx** | `2jerdAXR…` | 70 / 72 | 2 | \[\$400, \$700\] | \$663.88 | \$663.39 | -7.5 | 1466 | 0 |
| **TSLAx** | `5iTiczqg…` | 55 / 65 | 10 | \[\$300, \$520\] | \$376.30 | \$372.17 | -109.8 | 1466 | 0 |
| **GOOGLx** | `4wg6rEkG…` | 60 / 70 | 10 | \[\$224, \$416\] | \$344.40 | \$345.75 | +39.2 | 1466 | 0 |
| **AAPLx** | `CKJbqakb…` | 40 / 50 | 10 | \[\$190, \$300\] | \$271.06 | \$266.09 | -183.4 | 1466 | 0 |
| **NVDAx** | `7B66Az3t…` | 55 / 65 | 10 | \[\$100, \$250\] | \$208.27 | \$209.65 | +66.0 | 1466 | 0 |
| **MSTRx** | `Cwy2WJos…` | 30 / 40 | 10 | \[\$65, \$250\] | \$171.02 | \$170.92 | -5.8 | 1466 | 0 |
| **HOODx** | `4UBJu5Xp…` | 30 / 40 | 10 | \[\$54, \$100\] | \$84.71 | \$84.24 | -55.5 | 1466 | 0 |

## Section 2 — Coverage context for the same weekend
Coverage and half-width comparison across the three methods that publish a coverage band: Soothsayer at τ=0.85 (deployment default), Soothsayer at τ=0.95 (stricter oracle-validation comparator), and a simple free-data heuristic (`Friday close ± max(|Chainlink tokenizedPrice − Friday close|)` over the V5 tape). This section is descriptive rather than load-bearing: the more important question for Kamino-shaped protocols is how the same weekend interacts with the real reserve buffer and near-threshold borrower states. Excess width is half-width minus the realized absolute move; positive values indicate over-protection, negative values indicate the band missed the move.
| Symbol | Realized (bps) | Soothsayer τ=0.85 cov / hw / excess | Soothsayer τ=0.95 cov / hw / excess | Pyth (regular) cov / hw / excess | Simple heuristic cov / hw / excess |
|---|---:|---|---|---|---|
| **SPYx** | -10.8 | ✓ in / 131.2 / +120.4 | ✓ in / 207.1 / +196.4 | ✓ in / 343.5 / +332.7 | ✓ in / 66.6 / +55.8 |
| **QQQx** | -7.5 | ✓ in / 137.9 / +130.4 | ✓ in / 278.0 / +270.5 | ✓ in / 99.4 / +92.0 | ✓ in / 42.9 / +35.5 |
| **TSLAx** | -109.8 | ✓ in / 480.6 / +370.9 | ✓ in / 1015.5 / +905.7 | ✗ out / 2.3 / -107.5 | ✗ out / 86.4 / -23.3 |
| **GOOGLx** | +39.2 | ✓ in / 178.4 / +139.2 | ✓ in / 264.1 / +224.9 | ✓ in / 843.5 / +804.3 | ✓ in / 46.3 / +7.1 |
| **AAPLx** | -183.4 | ✓ in / 157.0 / -26.4 | ✓ in / 326.3 / +142.9 | ✗ out / 5.4 / -178.0 | ✗ out / 58.3 / -125.0 |
| **NVDAx** | +66.0 | ✓ in / 338.1 / +272.1 | ✓ in / 824.3 / +758.3 | ✗ out / 2.3 / -63.7 | ✓ in / 83.8 / +17.8 |
| **MSTRx** | -5.8 | ✓ in / 553.2 / +547.4 | ✓ in / 1348.9 / +1343.0 | ✗ out / 5.8 / -0.0 | ✓ in / 189.1 / +183.2 |
| **HOODx** | -55.5 | ✓ in / 1154.8 / +1099.3 | ✓ in / 1494.4 / +1438.9 | ✗ out / 0.6 / -54.9 | ✓ in / 102.0 / +46.5 |

**Aggregate coverage on this weekend** (method ✓ / total scorable rows): Soothsayer τ=0.85 = 8/8; Soothsayer τ=0.95 = 8/8; Pyth regular = 3/8; simple heuristic = 6/8.

*Pyth regular* is the publisher-dispersion confidence band from Pyth's regular-session feed at Friday close — the closest existing on-Solana analog to a published "band". It widens during off-hours via Pyth's aggregation rule (publishers thinning out → wider $\sigma$). The comparator's intellectual question is *publisher-dispersion-based confidence vs calibration-transparent coverage*; Pyth regular is the publisher-dispersion side of that comparison.
*One weekend is a tiny sample by design — this report is a forward-running tape; the cross-week aggregate becomes the meaningful comparison after several weekends.*

## Section 3 — Primary comparison: lending consequence under real reserve params
For each method's lower bound, what does the same reserve config classify a near-origination borrower (debt sized to LTV = max-LTV − 0.5pp) and a near-liquidation borrower (debt sized to LTV = liquidation threshold − 0.05pp) as on Monday? `Kamino-incumbent` uses the Scope-served Monday-open price (or Friday close as fallback when Scope tape is absent for past weekends) — this is the *actually-deployed* incumbent decision rule, not a reconstruction. Soothsayer rows use the band's lower bound as the conservative collateral price. This is the section to read first if the question is whether the closed-market signal changes reserve-buffer-relevant decisions.
| Symbol | LTV / liq / gap | Method | Near-origination | Near-liquidation | Effective LTV (orig / liq) |
|---|---|---|---|---|---|
| **SPYx** | 73 / 75 / 2pp | `kamino_incumbent` | Safe | Caution | 0.725 / 0.750 |
| **SPYx** | 73 / 75 / 2pp | `soothsayer_t085` | Caution | Liquidate | 0.738 / 0.763 |
| **SPYx** | 73 / 75 / 2pp | `soothsayer_t095` | Caution | Liquidate | 0.747 / 0.772 |
| **SPYx** | 73 / 75 / 2pp | `simple_heuristic` | Safe | Liquidate | 0.730 / 0.754 |
| **SPYx** | 73 / 75 / 2pp | `pyth_regular` | Liquidate | Liquidate | 0.751 / 0.776 |
| **QQQx** | 70 / 72 / 2pp | `kamino_incumbent` | Safe | Caution | 0.695 / 0.720 |
| **QQQx** | 70 / 72 / 2pp | `soothsayer_t085` | Caution | Liquidate | 0.707 / 0.732 |
| **QQQx** | 70 / 72 / 2pp | `soothsayer_t095` | Liquidate | Liquidate | 0.724 / 0.749 |
| **QQQx** | 70 / 72 / 2pp | `simple_heuristic` | Safe | Liquidate | 0.698 / 0.723 |
| **QQQx** | 70 / 72 / 2pp | `pyth_regular` | Caution | Liquidate | 0.702 / 0.727 |
| **TSLAx** | 55 / 65 / 10pp | `kamino_incumbent` | Safe | Caution | 0.545 / 0.649 |
| **TSLAx** | 55 / 65 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.568 / 0.677 |
| **TSLAx** | 55 / 65 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.593 / 0.707 |
| **TSLAx** | 55 / 65 / 10pp | `simple_heuristic` | Safe | Liquidate | 0.550 / 0.655 |
| **TSLAx** | 55 / 65 / 10pp | `pyth_regular` | Safe | Caution | 0.545 / 0.650 |
| **GOOGLx** | 60 / 70 / 10pp | `kamino_incumbent` | Safe | Caution | 0.595 / 0.700 |
| **GOOGLx** | 60 / 70 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.607 / 0.714 |
| **GOOGLx** | 60 / 70 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.615 / 0.723 |
| **GOOGLx** | 60 / 70 / 10pp | `simple_heuristic` | Safe | Liquidate | 0.598 / 0.703 |
| **GOOGLx** | 60 / 70 / 10pp | `pyth_regular` | Caution | Liquidate | 0.650 / 0.764 |
| **AAPLx** | 40 / 50 / 10pp | `kamino_incumbent` | Safe | Caution | 0.395 / 0.499 |
| **AAPLx** | 40 / 50 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.403 / 0.509 |
| **AAPLx** | 40 / 50 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.410 / 0.518 |
| **AAPLx** | 40 / 50 / 10pp | `simple_heuristic` | Safe | Liquidate | 0.397 / 0.502 |
| **AAPLx** | 40 / 50 / 10pp | `pyth_regular` | Safe | Caution | 0.395 / 0.500 |
| **NVDAx** | 55 / 65 / 10pp | `kamino_incumbent` | Safe | Caution | 0.545 / 0.649 |
| **NVDAx** | 55 / 65 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.566 / 0.675 |
| **NVDAx** | 55 / 65 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.617 / 0.736 |
| **NVDAx** | 55 / 65 / 10pp | `simple_heuristic` | Safe | Liquidate | 0.550 / 0.655 |
| **NVDAx** | 55 / 65 / 10pp | `pyth_regular` | Safe | Caution | 0.545 / 0.650 |
| **MSTRx** | 30 / 40 / 10pp | `kamino_incumbent` | Safe | Caution | 0.295 / 0.400 |
| **MSTRx** | 30 / 40 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.305 / 0.414 |
| **MSTRx** | 30 / 40 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.346 / 0.469 |
| **MSTRx** | 30 / 40 / 10pp | `simple_heuristic` | Caution | Liquidate | 0.301 / 0.407 |
| **MSTRx** | 30 / 40 / 10pp | `pyth_regular` | Safe | Caution | 0.295 / 0.400 |
| **HOODx** | 30 / 40 / 10pp | `kamino_incumbent` | Safe | Caution | 0.295 / 0.400 |
| **HOODx** | 30 / 40 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.326 / 0.441 |
| **HOODx** | 30 / 40 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.334 / 0.453 |
| **HOODx** | 30 / 40 / 10pp | `simple_heuristic` | Safe | Liquidate | 0.298 / 0.404 |
| **HOODx** | 30 / 40 / 10pp | `pyth_regular` | Safe | Caution | 0.295 / 0.400 |

### Decision divergence summary
Cases where Soothsayer (τ=0.85) and Kamino-incumbent reach a *different* classification for the near-liquidation borrower. Treat this as a one-week illustration of the decision surface, not a welfare conclusion by itself:

| Symbol | Realized (bps) | Kamino near-liq | Soothsayer τ=0.85 near-liq | Direction |
|---|---:|---|---|---|
| **SPYx** | -10.8 | Caution | Liquidate | Soothsayer more conservative |
| **QQQx** | -7.5 | Caution | Liquidate | Soothsayer more conservative |
| **TSLAx** | -109.8 | Caution | Liquidate | Soothsayer more conservative |
| **GOOGLx** | +39.2 | Caution | Liquidate | Soothsayer more conservative |
| **AAPLx** | -183.4 | Caution | Liquidate | Soothsayer more conservative |
| **NVDAx** | +66.0 | Caution | Liquidate | Soothsayer more conservative |
| **MSTRx** | -5.8 | Caution | Liquidate | Soothsayer more conservative |
| **HOODx** | -55.5 | Caution | Liquidate | Soothsayer more conservative |

**Single-week decision divergence: 8 of 8 symbols** on the near-liquidation borrower. The meaningful aggregate is the cross-week false-liquidation and missed-risk rate under the same reserve parameters.

## Section 4 — LTV-gap breach analysis (the actually-Kamino-shaped metric)
The metrics above (coverage, decision-classification) ask Soothsayer-shaped questions. Kamino consumes a Scope-served *point* and applies an `(LTV-at-origination, liquidation-threshold)` gap, not a coverage band. The question its risk team would actually ask is: *did the realized Monday move cross the threshold below which a borrower originated at max-LTV gets liquidated, and did each method's lower bound warn about that breach beforehand?*

For a borrower originated at the LTV ceiling on Friday, the **trigger drop** is `(max_ltv / liq_threshold − 1) × Friday close`. Below that price the new LTV exceeds the liquidation threshold. Per-method classification is a 2×2: a method **flags** the breach if its lower bound is at or below the trigger price; the realized move **breaches** if Monday open is at or below the trigger price.

  - `matched` — flagged AND realized → correct warning
  - `preemptive` — flagged but not realized → safe-side false positive
  - `missed` — not flagged but realized → dangerous false negative
  - `silent_safe` — not flagged AND not realized → correct silence

| Symbol | Trigger drop (bps) | Realized (bps) | Realized breach? | Kamino-incumbent | Soothsayer τ=0.85 | Soothsayer τ=0.95 | Pyth regular | Simple heuristic |
|---|---:|---:|---|---|---|---|---|---|
| **SPYx** | -266.7 | -10.8 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-182bps) | ⚠️ preemptive (-288bps) | ⚠️ preemptive (-344bps) | ✓ silent_safe (-67bps) |
| **QQQx** | -277.8 | -7.5 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-173bps) | ⚠️ preemptive (-395bps) | ✓ silent_safe (-98bps) | ✓ silent_safe (-43bps) |
| **TSLAx** | -1538.5 | -109.8 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-400bps) | ✓ silent_safe (-816bps) | ✓ silent_safe (-4bps) | ✓ silent_safe (-86bps) |
| **GOOGLx** | -1428.6 | +39.2 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-204bps) | ✓ silent_safe (-326bps) | ✓ silent_safe (-846bps) | ✓ silent_safe (-46bps) |
| **AAPLx** | -2000.0 | -183.4 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-187bps) | ✓ silent_safe (-361bps) | ✓ silent_safe (-9bps) | ✓ silent_safe (-58bps) |
| **NVDAx** | -1538.5 | +66.0 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-377bps) | ✓ silent_safe (-1173bps) | ✓ silent_safe (-5bps) | ✓ silent_safe (-84bps) |
| **MSTRx** | -2500.0 | -5.8 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-344bps) | ✓ silent_safe (-1475bps) | ✓ silent_safe (-6bps) | ✓ silent_safe (-189bps) |
| **HOODx** | -2500.0 | -55.5 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-943bps) | ✓ silent_safe (-1171bps) | ✓ silent_safe (-2bps) | ✓ silent_safe (-102bps) |

**Aggregate this weekend:** 0 of 8 symbols realized a breach (Monday open below the LTV-gap trigger). Per-method tallies:

| Method | matched | preemptive | missed | silent_safe |
|---|---:|---:|---:|---:|
| `kamino_incumbent` | 0 | 0 | 0 | 8 |
| `soothsayer_t085` | 0 | 0 | 0 | 8 |
| `soothsayer_t095` | 0 | 2 | 0 | 6 |
| `pyth_regular` | 0 | 1 | 0 | 7 |
| `simple_heuristic` | 0 | 0 | 0 | 8 |

*Welfare-relevant ratios over time:* the cross-week ratio of `matched / (matched + missed)` is the *recall* on actual breaches, and `matched / (matched + preemptive)` is the *precision* on flagged breaches. A single weekend with no breaches doesn't distinguish the methods on this axis; the comparison emerges over multiple weekends.

## Honest framing
- The Kamino-incumbent row uses the actually-deployed Scope oracle path; it is not a reconstruction or proxy.
- The Soothsayer rows are the deployed methodology serving at consumer τ; they are not tuned to this weekend.
- The simple heuristic exists to prevent the comparison from looking like 'Soothsayer vs one arbitrary number'. It is intentionally weak and is expected to be the worst of the three coverage methods most weeks.
- Coverage on a single weekend is too small a sample to support a welfare claim. The quantity that matters across weeks is the *false-liquidation rate* and *missed-risk rate* under the same reserve parameters — that aggregation is in scope for Paper 3 (`reports/paper3_liquidation_policy/plan.md`) once enough forward weekends have accumulated.
