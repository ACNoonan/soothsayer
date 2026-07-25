# W11 — proxy-reliance exponent ρ sweep

**Run 2026-07-25.** Runner `scripts/run_paper1_w11_rho_sweep.py`; tables `reports/tables/w11_rho_sweep{,_by_regime}.csv`. Closes W11.

## Question

Zhong (arXiv:2603.22569, q-fin.RM) parameterises the exponent on the volatility proxy in the nonconformity score, $u_s^{(\rho)} = (Y_s - \hat q_s)/v_s^{\rho}$, and reports that **intermediate ρ is more robust when the proxy underreacts in stress.** Our deployed score sits at ρ = 1; the §7.1 constant-buffer comparator at ρ ≈ 0. §7 ablates both endpoints and none of the interior, and ρ = 1 was never a considered choice — it was never considered at all.

Only the exponent moves: `score_ρ = |mon_open − point| / (fri_close · σ̂^ρ)`, `half = q_r(τ) · σ̂^ρ · fri_close`. Same panel, cells, split, rank formula. δ suppressed, no c(τ) on any arm. Both panels, de-contaminated σ̂ overnight.

## Result — ρ = 1 dominates, monotonically

Per-symbol Kupiec pass (of 10), by ρ and τ:

| ρ | weekend 0.68 / 0.85 / 0.95 / 0.99 | overnight 0.68 / 0.85 / 0.95 / 0.99 |
|---|---|---|
| 0.00 | 3 / 3 / 2 / 7 | 2 / 1 / 0 / 2 |
| 0.25 | 5 / 3 / 3 / 7 | 3 / 2 / 2 / 3 |
| 0.50 | 5 / 5 / 6 / 7 | 3 / 3 / 3 / 4 |
| 0.75 | 7 / 6 / 9 / 8 | 5 / 5 / 7 / 5 |
| **1.00** | **10 / 10 / 10 / 10** | **9 / 9 / 10 / 9** |

Strictly monotone increasing in ρ on both panels at every anchor. Per-regime pass is monotone too (weekend 0→2, overnight 1→2 at τ=0.68; 2→3 at τ=0.95). **There is no interior optimum.**

Lower ρ *is* narrower — weekend τ=0.95 half-width falls 343.4 → 260.9 bps at ρ = 0.5 — but that is under-coverage, not efficiency: per-symbol drops 10/10 → 6/10 at the same setting. The same pattern as every other "tighter" comparator in this programme.

## Zhong's stress claim does not transfer

Tested directly on the `high_vol` cell, where it should appear:

| ρ | weekend `high_vol` @ τ=0.95 | overnight `high_vol` @ τ=0.95 |
|---|---|---|
| 0.00 | 0.934 | 0.915 |
| 0.50 | 0.937 | 0.929 |
| 0.75 | 0.950 | 0.947 |
| **1.00** | **0.955** | **0.949** |

Coverage in stress improves monotonically *with* ρ. Intermediate ρ is not more robust here — it is worse, on both panels.

**Why it does not transfer, and this is the interesting part.** Zhong's $v$ is a generic volatility proxy (20-day realised + GARCH + a VIX transform) applied to one asset's daily VaR, and his failure mode is the proxy *underreacting* to a stress move it did not anticipate. Our σ̂ is not a generic proxy: it is a per-symbol EWMA of the same gap type being predicted, and — per W10 and W12 — its job is **cross-sectional scale normalisation across ten heterogeneous symbols**, not temporal stress responsiveness. Lowering ρ partially disables the per-symbol channel, which is precisely the thing σ̂ exists to supply.

Zhong's setting has no cross-sectional axis at all: one asset at a time, so the tradeoff he identifies cannot arise there and the tradeoff we face cannot arise in his. Both results are correct in their own setting. The exponent is a real design axis; its optimum is domain-dependent, and on a heterogeneous panel it sits at the boundary.

## Verdict

**ρ = 1 stays, and is now justified rather than assumed.** The §7 claim that σ̂ standardisation is load-bearing strengthens: not only does removing it fail (§7.2, 2/10), *partially* removing it fails proportionally, with no configuration in between recovering per-symbol calibration.

Worth one sentence in §2.3 or §7 when citing Zhong: the axis was swept, ρ = 1 is the boundary optimum on this panel, and the divergence from his finding is attributable to the cross-sectional load our σ̂ carries and his proxy does not.

## Caveats

- δ suppressed and no c(τ) on any arm. A c(τ) bump can only widen, so it would lift the low-ρ arms toward nominal *pooled* coverage — but c(τ) is a single global scalar with no per-symbol channel, so it cannot repair the per-symbol failures that decide this comparison.
- Deployed regime taxonomy only (`regime_pub`); the W13 `triple_witching` cell is not included, to keep ρ the single moving part.
