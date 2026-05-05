# §11 — Conclusion

This paper specified a calibration-transparent oracle primitive for tokenised real-world assets, evaluated it on 12 years of US-listed weekend data, and shipped a reference implementation. The contribution is the *interface* (consumer-selects-coverage with a per-read receipt) and the *deployable architecture* (locally-weighted Mondrian split-conformal under EWMA HL=8 σ̂; v2). The architecture was arrived at through the §7.1 constant-buffer stress test that ruled out the deployable simpler baseline; the §7.2 ladder that isolated the per-regime conformal lookup as the load-bearing replacement for Soothsayer-v0's hybrid forecaster machinery (the v1 narrowing); and the §7.2.4 isolation of σ̂ standardisation as the v1 → v2 fix for per-symbol bimodality. The §6.Y simulation study predicted the per-symbol fix from architecture under four DGPs *before* real-data confirmation; the §6.7 forward-tape harness carries the held-out evidence forward weekly against a content-addressed frozen artefact.

## 11.1 The three properties, revisited

- **(P1) Auditability.** The deployment artefact (per-Friday parquet + 16-scalar JSON sidecar) is reconstructible from public data — Soothsayer consumes Scryer parquet for Yahoo daily prices, the per-symbol factor returns (ES / NQ / GC / ZN / BTC), the regime classifier inputs, and computes σ̂ as a deterministic function of past Fridays. The per-read `PricePoint` exposes the eight-field receipt of §4.7, and the on-chain `PriceUpdate` PDA mirrors that receipt under the byte-for-byte parity contract of §8.5 (M5 / v1 path; v2 Rust port reserved). A third party with the sidecar and the per-Friday artefact can reconstruct any served band from the receipt alone.

- **(P2) Conditional empirical coverage.** On the 2023+ slice (1,730 rows × 173 weekends), the served v2 band at $\tau = 0.95$ realises $0.950$ with Kupiec $p_{uc} = 0.956$ and Christoffersen $p_{ind} = 0.603$ at $370.6$ bps half-width. **All 10 symbols pass per-symbol Kupiec** (vs v1's 2/10); per-symbol Berkowitz LR range collapses from $0.9$–$224$ to $3.2$–$16.7$. At $\tau = 0.99$ the band realises $0.990$ ($p_{uc} = 0.942$). Kupiec passes at all four anchors; Christoffersen passes at every anchor on the deployed split *and* at every (split × $\tau$) cell across the four split-date anchors {2021, 2022, 2023, 2024} (the K=26 σ̂ baseline of v2 had 2021/2022 split-date Christoffersen rejections at $\tau = 0.95$ that the EWMA HL=8 promotion clears, §7.3). The empirical content of P2 remains *per-anchor calibration*, not full-distribution calibration (Berkowitz still rejects pooled — the residual is cross-sectional within-weekend common-mode, orthogonal to σ̂; §9.4). The number is *deployment-calibrated and walk-forward-stable*, with §6.7 forward-tape held-out re-validation accumulating weekly.

- **(P3) Per-regime serving efficiency at deployment-tuned parameter budgets.** v2 deploys 16 scalars: 12 trained per-regime quantiles + 4 OOS-fit $c(\tau)$ + 0 walk-forward (the $\delta(\tau)$ schedule collapses to zero under per-symbol σ̂ standardisation). Of the 4 $c(\tau)$ scalars, three are essentially identity ($c \in \{1.000,\,1.000,\,1.003\}$ at $\tau \in \{0.68,\,0.85,\,0.99\}$); only $c(0.95) = 1.079$ carries meaningful OOS information. **3 of 16 deployment scalars carry meaningful OOS-fit information** (vs v1's 8 of 20). v2 redistributes width across symbols within a regime via σ̂: equity bands widen $+23\%$ to absorb the heavy-tail per-symbol calibration that v1 left under-covered; gold/treasury bands narrow $-48\%$, releasing width on the over-covered defensive class.

## 11.2 What the ablation says is doing the work

The §7 ladder reduces to four load-bearing components:

1. **Factor-switchboard point.** Inherited from v1; tightens pooled bands $\sim 39\%$ vs a stale-hold reference.

2. **Regime classifier $\rho$.** §7.1 established a deployable architecture without regime structure cannot deliver coverage on the 2023+ slice; §7.2 isolated the M2 → v1 narrowing as the per-regime conformal lookup replacing Soothsayer-v0's hybrid forecaster ladder.

3. **Per-symbol pre-Friday σ̂ standardisation (the v1 → v2 fix).** Adding a per-symbol $\hat\sigma_s(t)$ multiplier to the conformity score, with no other architectural change, takes per-symbol Kupiec at $\tau = 0.95$ from 2/10 → 10/10, collapses the Berkowitz LR range from $0.9$–$224$ to $3.2$–$16.7$, and tightens LOSO realised-coverage std by $5.7\times$. The §6.Y / Phase 6 simulation study confirms this fix is structural — predicted in advance under four DGPs with known ground truth.

4. **Near-identity OOS-fit $c(\tau)$ bump.** Under v2 the bump is meaningful only at $\tau = 0.95$ (a 7.9% widening); at the other three anchors it is essentially the identity. The walk-forward $\delta(\tau)$ schedule is identically zero (vs v1's $\{0.05, 0.02, 0, 0\}$).

The remaining components from earlier ladders (Soothsayer-v0's VIX-scaled standardisation, log-log vol regression, per-symbol vol index, long-weekend regressor, earnings flag, hybrid regime-to-forecaster policy; v1's walk-forward $\delta(\tau)$ schedule) are dropped at v2; the simplification is what makes the §11.1 P3 contraction possible.

## 11.3 Honest framing

The list of disclosures is much shorter under v2 than under v1.

- **Per-anchor calibration, not full-distribution calibration.** Berkowitz and DQ both reject pooled. §6.3.1 / §9.4 localise the residual to *cross-sectional within-weekend* common-mode ($\hat\rho_\text{cross} = 0.354$), orthogonal to σ̂ standardisation. The §10.2 cross-sectional partial-out track is the candidate fix; gated on a Friday-observable predictor not yet available.

- **σ̂ selection multi-test exposure (mitigated).** The §7.3 σ̂ selection ran 80 split-date Christoffersen tests across 5 variants × 16 cells; under BH correction at FDR=0.05, no variant has any rejected cell. The deployment decision rests on Gate 3 (bootstrap CI on width — no multi-test issue) plus the §6.7 / §7.3.6 forward-tape variant comparison harness (held-out re-validation, never used to re-select). We do not claim the σ̂ rule is optimal among all locally-weighted variants.

- **OOS-fit $c(0.95) = 1.079$.** One scalar of the 16 is meaningfully OOS-fit. §9.3 reports the three independent provenance checks (6-split walk-forward, 4-anchor split-date sensitivity, 10-fold leave-one-symbol-out) under v2; all pass. Forward-tape evidence accumulates weekly.

- **Shock-tertile floor.** Realised $\tau = 0.95$ coverage on the heaviest-move tertile is $87.8\%$ ($+0.6$pp over v1) — the residual is cross-sectional common-mode, not per-symbol scale, and does not yield to σ̂ choice.

- **Forward-tape held-out window operational, accumulating.** Live integrator window remains an open external-validity gap; forward-tape carries the held-out coverage statement weekly until that window opens.

The textbook econometric default — per-symbol GARCH(1,1) on log Friday-to-Monday returns with Gaussian innovations — fails Kupiec at $\tau \in \{0.68, 0.95, 0.99\}$ on the same OOS slice. At matched 95% realised coverage, GARCH's mean half-width is **3.9% wider** than v2's ($385.7$ vs $370.6$ bps), establishing v2 dominance on both calibration and sharpness once the coverage-width point is held fixed.

The remaining statistical gaps are useful bad news rather than project-fatal news. They name the boundary of what a per-anchor-calibrated locally-weighted-Mondrian interval oracle can claim. §10 names the candidate paths forward; §6.7 carries the held-out evidence weekly.

## 11.4 What sits in the companion papers

*Paper 3* addresses the mapping from a calibrated band to a $\{\texttt{Safe}, \texttt{Caution}, \texttt{Liquidate}\}$ action under explicit borrower-book LTV and a protocol-specific cost model. The active research structure is methodology (this paper) → policy (Paper 3). The coverage-inversion primitive stands alone as an oracle contract, regardless of how downstream consumers use the band.
