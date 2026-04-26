# Kamino xStocks — weekend comparator: 2026-04-17 → 2026-04-20
*Generated 2026-04-26T16:38:27.418806+00:00; reserve config snapshot from 2026-04-26.*
Forward-running comparator that scores Soothsayer bands and free-data baselines against the realized Monday open under Kamino's actually-deployed xStock reserve parameters. All 8 xStocks live in lending market `5wJeMrUYECGq41fxRESKALVcHnNX26TAWy4W98yULsua` and consume Scope as the primary oracle. The numbers below are reproducible from the on-chain klend program (`KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD`) via `scripts/snapshot_kamino_xstocks.py` + `scripts/score_weekend_comparison.py`.
## Section 1 — What was observed
Per-symbol Friday close (yfinance underlier), Monday open (yfinance underlier), Kamino reserve config (LTV at origination / liquidation threshold / heuristic guard rail), and weekend tape coverage. Kamino's `PriceHeuristic` is a *validity guard rail* — Scope reads outside the range are rejected — not a coverage band, so it is reported here as a recorded incumbent parameter rather than scored against the realized move.
| Symbol | Reserve PDA | LTV / liq | Gap (pp) | Heuristic guard rail | Fri close | Mon open | Realized (bps) | V5 tape obs | Scope tape obs |
|---|---|---|---:|---|---:|---:|---:|---:|---:|
| **SPYx** | `UvXjBuC7…` | 73 / 75 | 2 | \[\$515, \$858\] | \$710.14 | \$708.78 | -19.2 | 0 | 0 |
| **QQQx** | `2jerdAXR…` | 70 / 72 | 2 | \[\$400, \$700\] | \$648.85 | \$648.04 | -12.5 | 0 | 0 |
| **TSLAx** | `5iTiczqg…` | 55 / 65 | 10 | \[\$300, \$520\] | \$400.62 | \$402.58 | +48.9 | 0 | 0 |
| **GOOGLx** | `4wg6rEkG…` | 60 / 70 | 10 | \[\$224, \$416\] | \$341.68 | \$340.76 | -26.9 | 0 | 0 |
| **AAPLx** | `CKJbqakb…` | 40 / 50 | 10 | \[\$190, \$300\] | \$270.23 | \$270.33 | +3.7 | 0 | 0 |
| **NVDAx** | `7B66Az3t…` | 55 / 65 | 10 | \[\$100, \$250\] | \$201.68 | \$199.98 | -84.3 | 0 | 0 |
| **MSTRx** | `Cwy2WJos…` | 30 / 40 | 10 | \[\$65, \$250\] | \$166.52 | \$162.30 | -253.4 | 0 | 0 |
| **HOODx** | `4UBJu5Xp…` | 30 / 40 | 10 | \[\$54, \$100\] | \$90.75 | \$89.70 | -115.7 | 0 | 0 |

## Section 2 — Coverage context for the same weekend
Coverage and half-width comparison across the three methods that publish a coverage band: Soothsayer at τ=0.85 (deployment default), Soothsayer at τ=0.95 (stricter oracle-validation comparator), and a simple free-data heuristic (`Friday close ± max(|Chainlink tokenizedPrice − Friday close|)` over the V5 tape). This section is descriptive rather than load-bearing: the more important question for Kamino-shaped protocols is how the same weekend interacts with the real reserve buffer and near-threshold borrower states. Excess width is half-width minus the realized absolute move; positive values indicate over-protection, negative values indicate the band missed the move.
| Symbol | Realized (bps) | Soothsayer τ=0.85 cov / hw / excess | Soothsayer τ=0.95 cov / hw / excess | Simple heuristic cov / hw / excess |
|---|---:|---|---|---|
| **SPYx** | -19.2 | ✓ in / 114.7 / +95.5 | ✓ in / 181.2 / +162.0 | ✗ out / 0.0 / -19.2 |
| **QQQx** | -12.5 | ✓ in / 120.7 / +108.3 | ✓ in / 244.2 / +231.7 | ✗ out / 0.0 / -12.5 |
| **TSLAx** | +48.9 | ✓ in / 374.7 / +325.7 | ✓ in / 786.4 / +737.5 | ✗ out / 0.0 / -48.9 |
| **GOOGLx** | -26.9 | ✓ in / 202.7 / +175.7 | ✓ in / 296.4 / +269.4 | ✗ out / 0.0 / -26.9 |
| **AAPLx** | +3.7 | ✓ in / 193.5 / +189.8 | ✓ in / 403.5 / +399.8 | ✗ out / 0.0 / -3.7 |
| **NVDAx** | -84.3 | ✓ in / 309.3 / +225.1 | ✓ in / 754.7 / +670.4 | ✗ out / 0.0 / -84.3 |
| **MSTRx** | -253.4 | ✓ in / 510.0 / +256.5 | ✓ in / 1244.9 / +991.5 | ✗ out / 0.0 / -253.4 |
| **HOODx** | -115.7 | ✓ in / 704.2 / +588.5 | ✓ in / 956.2 / +840.5 | ✗ out / 0.0 / -115.7 |

**Aggregate coverage on this weekend** (method ✓ / total scorable rows): Soothsayer τ=0.85 = 8/8; Soothsayer τ=0.95 = 8/8; simple heuristic = 0/8.
*One weekend is a tiny sample by design — this report is a forward-running tape; the cross-week aggregate becomes the meaningful comparison after several weekends.*

## Section 3 — Primary comparison: lending consequence under real reserve params
For each method's lower bound, what does the same reserve config classify a near-origination borrower (debt sized to LTV = max-LTV − 0.5pp) and a near-liquidation borrower (debt sized to LTV = liquidation threshold − 0.05pp) as on Monday? `Kamino-incumbent` uses the Scope-served Monday-open price (or Friday close as fallback when Scope tape is absent for past weekends) — this is the *actually-deployed* incumbent decision rule, not a reconstruction. Soothsayer rows use the band's lower bound as the conservative collateral price. This is the section to read first if the question is whether the closed-market signal changes reserve-buffer-relevant decisions.
| Symbol | LTV / liq / gap | Method | Near-origination | Near-liquidation | Effective LTV (orig / liq) |
|---|---|---|---|---|---|
| **SPYx** | 73 / 75 / 2pp | `kamino_incumbent` | Safe | Caution | 0.725 / 0.750 |
| **SPYx** | 73 / 75 / 2pp | `soothsayer_t085` | Caution | Liquidate | 0.742 / 0.767 |
| **SPYx** | 73 / 75 / 2pp | `soothsayer_t095` | Caution | Liquidate | 0.749 / 0.774 |
| **SPYx** | 73 / 75 / 2pp | `simple_heuristic` | Safe | Caution | 0.725 / 0.750 |
| **QQQx** | 70 / 72 / 2pp | `kamino_incumbent` | Safe | Caution | 0.695 / 0.720 |
| **QQQx** | 70 / 72 / 2pp | `soothsayer_t085` | Caution | Liquidate | 0.711 / 0.736 |
| **QQQx** | 70 / 72 / 2pp | `soothsayer_t095` | Liquidate | Liquidate | 0.725 / 0.751 |
| **QQQx** | 70 / 72 / 2pp | `simple_heuristic` | Safe | Caution | 0.695 / 0.720 |
| **TSLAx** | 55 / 65 / 10pp | `kamino_incumbent` | Safe | Caution | 0.545 / 0.649 |
| **TSLAx** | 55 / 65 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.567 / 0.676 |
| **TSLAx** | 55 / 65 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.587 / 0.699 |
| **TSLAx** | 55 / 65 / 10pp | `simple_heuristic` | Safe | Caution | 0.545 / 0.649 |
| **GOOGLx** | 60 / 70 / 10pp | `kamino_incumbent` | Safe | Caution | 0.595 / 0.700 |
| **GOOGLx** | 60 / 70 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.613 / 0.721 |
| **GOOGLx** | 60 / 70 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.622 / 0.731 |
| **GOOGLx** | 60 / 70 / 10pp | `simple_heuristic` | Safe | Caution | 0.595 / 0.700 |
| **AAPLx** | 40 / 50 / 10pp | `kamino_incumbent` | Safe | Caution | 0.395 / 0.499 |
| **AAPLx** | 40 / 50 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.407 / 0.515 |
| **AAPLx** | 40 / 50 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.416 / 0.526 |
| **AAPLx** | 40 / 50 / 10pp | `simple_heuristic` | Safe | Caution | 0.395 / 0.499 |
| **NVDAx** | 55 / 65 / 10pp | `kamino_incumbent` | Safe | Caution | 0.545 / 0.649 |
| **NVDAx** | 55 / 65 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.569 / 0.678 |
| **NVDAx** | 55 / 65 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.615 / 0.733 |
| **NVDAx** | 55 / 65 / 10pp | `simple_heuristic` | Safe | Caution | 0.545 / 0.649 |
| **MSTRx** | 30 / 40 / 10pp | `kamino_incumbent` | Safe | Caution | 0.295 / 0.400 |
| **MSTRx** | 30 / 40 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.324 / 0.438 |
| **MSTRx** | 30 / 40 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.366 / 0.495 |
| **MSTRx** | 30 / 40 / 10pp | `simple_heuristic` | Safe | Caution | 0.295 / 0.400 |
| **HOODx** | 30 / 40 / 10pp | `kamino_incumbent` | Safe | Caution | 0.295 / 0.400 |
| **HOODx** | 30 / 40 / 10pp | `soothsayer_t085` | Caution | Liquidate | 0.316 / 0.428 |
| **HOODx** | 30 / 40 / 10pp | `soothsayer_t095` | Caution | Liquidate | 0.323 / 0.437 |
| **HOODx** | 30 / 40 / 10pp | `simple_heuristic` | Safe | Caution | 0.295 / 0.400 |

### Decision divergence summary
Cases where Soothsayer (τ=0.85) and Kamino-incumbent reach a *different* classification for the near-liquidation borrower. Treat this as a one-week illustration of the decision surface, not a welfare conclusion by itself:

| Symbol | Realized (bps) | Kamino near-liq | Soothsayer τ=0.85 near-liq | Direction |
|---|---:|---|---|---|
| **SPYx** | -19.2 | Caution | Liquidate | Soothsayer more conservative |
| **QQQx** | -12.5 | Caution | Liquidate | Soothsayer more conservative |
| **TSLAx** | +48.9 | Caution | Liquidate | Soothsayer more conservative |
| **GOOGLx** | -26.9 | Caution | Liquidate | Soothsayer more conservative |
| **AAPLx** | +3.7 | Caution | Liquidate | Soothsayer more conservative |
| **NVDAx** | -84.3 | Caution | Liquidate | Soothsayer more conservative |
| **MSTRx** | -253.4 | Caution | Liquidate | Soothsayer more conservative |
| **HOODx** | -115.7 | Caution | Liquidate | Soothsayer more conservative |

**Single-week decision divergence: 8 of 8 symbols** on the near-liquidation borrower. The meaningful aggregate is the cross-week false-liquidation and missed-risk rate under the same reserve parameters.

## Section 4 — LTV-gap breach analysis (the actually-Kamino-shaped metric)
The metrics above (coverage, decision-classification) ask Soothsayer-shaped questions. Kamino consumes a Scope-served *point* and applies an `(LTV-at-origination, liquidation-threshold)` gap, not a coverage band. The question its risk team would actually ask is: *did the realized Monday move cross the threshold below which a borrower originated at max-LTV gets liquidated, and did each method's lower bound warn about that breach beforehand?*

For a borrower originated at the LTV ceiling on Friday, the **trigger drop** is `(max_ltv / liq_threshold − 1) × Friday close`. Below that price the new LTV exceeds the liquidation threshold. Per-method classification is a 2×2: a method **flags** the breach if its lower bound is at or below the trigger price; the realized move **breaches** if Monday open is at or below the trigger price.

  - `matched` — flagged AND realized → correct warning
  - `preemptive` — flagged but not realized → safe-side false positive
  - `missed` — not flagged but realized → dangerous false negative
  - `silent_safe` — not flagged AND not realized → correct silence

| Symbol | Trigger drop (bps) | Realized (bps) | Realized breach? | Kamino-incumbent | Soothsayer τ=0.85 | Soothsayer τ=0.95 | Simple heuristic |
|---|---:|---:|---|---|---|---|---|
| **SPYx** | -266.7 | -19.2 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-230bps) | ⚠️ preemptive (-323bps) | ✓ silent_safe (+0bps) |
| **QQQx** | -277.8 | -12.5 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-222bps) | ⚠️ preemptive (-418bps) | ✓ silent_safe (+0bps) |
| **TSLAx** | -1538.5 | +48.9 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-387bps) | ✓ silent_safe (-710bps) | ✓ silent_safe (+0bps) |
| **GOOGLx** | -1428.6 | -26.9 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-297bps) | ✓ silent_safe (-432bps) | ✓ silent_safe (+0bps) |
| **AAPLx** | -2000.0 | +3.7 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-294bps) | ✓ silent_safe (-511bps) | ✓ silent_safe (+0bps) |
| **NVDAx** | -1538.5 | -84.3 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-415bps) | ✓ silent_safe (-1143bps) | ✓ silent_safe (+0bps) |
| **MSTRx** | -2500.0 | -253.4 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-886bps) | ✓ silent_safe (-1933bps) | ✓ silent_safe (+0bps) |
| **HOODx** | -2500.0 | -115.7 | — | ✓ silent_safe (+0bps) | ✓ silent_safe (-664bps) | ✓ silent_safe (-851bps) | ✓ silent_safe (+0bps) |

**Aggregate this weekend:** 0 of 8 symbols realized a breach (Monday open below the LTV-gap trigger). Per-method tallies:

| Method | matched | preemptive | missed | silent_safe |
|---|---:|---:|---:|---:|
| `kamino_incumbent` | 0 | 0 | 0 | 8 |
| `soothsayer_t085` | 0 | 0 | 0 | 8 |
| `soothsayer_t095` | 0 | 2 | 0 | 6 |
| `simple_heuristic` | 0 | 0 | 0 | 8 |

*Welfare-relevant ratios over time:* the cross-week ratio of `matched / (matched + missed)` is the *recall* on actual breaches, and `matched / (matched + preemptive)` is the *precision* on flagged breaches. A single weekend with no breaches doesn't distinguish the methods on this axis; the comparison emerges over multiple weekends.

## Honest framing
- The Kamino-incumbent row uses the actually-deployed Scope oracle path; it is not a reconstruction or proxy.
- The Soothsayer rows are the deployed methodology serving at consumer τ; they are not tuned to this weekend.
- The simple heuristic exists to prevent the comparison from looking like 'Soothsayer vs one arbitrary number'. It is intentionally weak and is expected to be the worst of the three coverage methods most weeks.
- Coverage on a single weekend is too small a sample to support a welfare claim. The quantity that matters across weeks is the *false-liquidation rate* and *missed-risk rate* under the same reserve parameters — that aggregation is in scope for Paper 3 (`reports/paper3_liquidation_policy/plan.md`) once enough forward weekends have accumulated.
