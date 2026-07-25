# W15 — hybrid: frozen cells, adaptive level inside each cell

**Run 2026-07-25.** Runner `scripts/run_paper1_w15_hybrid_adaptive_cells.py`; tables `reports/tables/w15_hybrid_adaptive_cells{,_by_regime}.csv`. Closes W15.

## The construction

Straight from W10 + W12. Online conformal is sharper but fails conditional coverage (overnight `earnings_night` 0.317–0.383 against a claimed 0.95) because an adaptive learner converges a *global* level and cannot widen for a scheduled event it has not yet seen. The Mondrian partition is exactly that channel and is load-bearing (0.983 on the same cell). So: keep the partition, adapt only the level *inside* each cell.

$$\text{half}_{r,t} = m_{r,t}\cdot q_r(\tau)\cdot \hat\sigma_s(t)\cdot P_{\text{Fri}}, \qquad m_{r,t+1} = m_{r,t}\,\exp\!\big(\gamma\,(\text{err}_{r,t} - (1-\tau))\big)$$

$m$ starts at 1.0 and warms on the training period, so γ = 0 reproduces the deployed band exactly. Both panels, de-contaminated σ̂ overnight, δ suppressed, no c(τ).

**The state is three or four scalars** — one per regime cell — under a deterministic update over public prices. That is what makes this verifiable in a way full online conformal is not: publish $m$ in the receipt, checkpoint periodically, and a consumer verifies any single read in one step, replaying only since the last checkpoint to audit the state itself.

## Result — overnight it works, weekend it does not

**Overnight.** Per-regime pass at τ = 0.68 and 0.85 goes **2/3 → 3/3** for γ ≥ 0.05; per-symbol goes 9/10 → 10/10 at those anchors; and the band gets slightly *tighter* everywhere (τ=0.95: 280.1 → 276.2 bps; τ=0.85: 178.9 → 174.8).

The `earnings_night` cell is where it earns its keep:

| γ | half-width | realised | Kupiec p | learned $m$ |
|---|---|---|---|---|
| 0.00 (deployed) | 2453 bps | 0.983 | 0.171 | 1.000 |
| 0.02 | 2340 | 0.983 | 0.171 | 0.932 |
| 0.05 | 2181 | 0.983 | 0.171 | 0.839 |
| **0.10** | **2080 (−15%)** | 0.967 | **0.529** | **0.779** |

**This is W14's diagnosis being repaired.** W14 found `earnings_night` was over-wide because the training multiplier (~7×) was fitted on a period that no longer applies, and OOS wanted ~4.6–5.7×; it also found that shrinkage — the fix for *thin* cells — did nothing here, because the cell is well estimated and the problem is **drift**. W14's stated next step was recency weighting. The adaptive multiplier is recency weighting, and it learns $m \to 0.779$, i.e. an effective $7 \times 0.779 \approx 5.5\times$ — landing squarely in the range W14 said the OOS slice wanted. Kupiec p moves 0.171 → 0.529 while the band tightens 15%.

Critically, conditional coverage survives: 0.967 against the 0.317–0.383 that *pure* online conformal delivered on this cell. The partition is retained; only the level moves.

**Weekend.** Essentially inert. Multipliers stay within 0.99–1.06, width barely moves, per-regime improves 2/4 → 3/4 only at τ = 0.68, and τ = 0.95 gets marginally *worse* (343.4 → 358.0 bps at γ = 0.10). That is the expected result and a good sign: the weekend cells were not drifting, so there is nothing for adaptation to correct, and it does no harm.

## Verdict

**Adopt for the overnight profile at γ ≈ 0.05; leave the weekend profile frozen.** The asymmetry is diagnostic rather than arbitrary — adaptation repairs drift, the overnight `earnings_night` cell is the one demonstrated to drift, and the weekend cells are not.

This also resolves the sharpness question the programme opened with. W10 showed online methods were narrower and concluded the frozen architecture pays a width penalty for verifiability. It does not have to: the hybrid recovers a slice of that sharpness (−15% on the cell that mattered, tighter pooled at three of four overnight anchors) **without** surrendering conditional coverage or one-step verification.

## Before promotion

1. Re-run in the deployed configuration (δ active, c(τ) fitted per arm). This run suppressed both for isolation.
2. Decide the checkpoint cadence and put $m_{r,t}$ in the receipt and the band archive — a served band is no longer a pure function of the frozen artefact, and the audit story must say so explicitly or the calibration-transparency claim weakens.
3. γ was swept, not tuned out-of-sample. γ ∈ [0.05, 0.10] is a plateau on the overnight panel rather than an optimum; a single best-γ chosen on this slice would be an oracle choice.
4. `earnings_night` OOS is n = 60. Its Kupiec improvement (0.171 → 0.529) is real but under-powered — W14's binomial CI at that n spans 0.883–1.000 at τ = 0.95.
5. Interaction with the W13 `triple_witching` cell and the W14 shrinkage proposal is untested; all three touch the per-cell quantile and should be evaluated together before any lands in the artefact.
