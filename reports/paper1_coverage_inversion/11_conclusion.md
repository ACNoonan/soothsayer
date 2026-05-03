# §11 — Conclusion

This paper specified a calibration-transparent oracle primitive for tokenised real-world assets, evaluated it on 12 years of US-listed weekend data, and shipped a reference implementation with end-to-end Python ↔ Rust ↔ on-chain parity. The contribution is the *interface* (consumer-selects-coverage with a per-read receipt) and the *deployable architecture* (Mondrian split-conformal by regime + factor-adjusted point + δ-shifted $c(\tau)$), arrived at through the precursor v1 forecaster ablation, the §7.1 constant-buffer stress test, and the §7.2 Mondrian head-to-head.

## 11.1 The three properties, revisited

- **(P1) Auditability.** The deployment artefact (per-Friday parquet + 20-scalar JSON sidecar) is reconstructible from public data — Soothsayer consumes Scryer parquet for Yahoo daily prices, the per-symbol factor returns (ES / NQ / GC / ZN / BTC), and the regime classifier inputs. The per-read `PricePoint` exposes the eight-field receipt of §4.5, and the on-chain `PriceUpdate` PDA mirrors that receipt under the byte-for-byte parity contract of §8.5. A third party with the sidecar and the per-Friday artefact can reconstruct any served band from the receipt alone.

- **(P2) Conditional empirical coverage.** On the 2023+ slice (1{,}730 rows × 173 weekends; 12 trained quantiles frozen on the 4{,}266 pre-2023 rows; 4+4 schedules deployment-tuned and walk-forward-stable), the served band at $\tau = 0.95$ realises $0.950$ with Kupiec $p_{uc} = 0.956$ and Christoffersen $p_{ind} = 0.912$ at $354.5$ bps half-width — a 20% reduction over v1 on the same slice. At $\tau = 0.99$ the band realises $0.990$ ($p_{uc} = 0.942$), closing v1's tail ceiling at the cost of a 22% wider band. Kupiec passes at all four anchors; Christoffersen passes at $\tau \in \{0.85, 0.95, 0.99\}$ and rejects at $\tau = 0.68$. The empirical content of P2 is *per-anchor calibration* and *not full-distribution calibration* (Berkowitz LR $= 173.1$, DQ at $\tau = 0.95$ $p = 5.7 \times 10^{-6}$). The number is *deployment-calibrated and walk-forward-stable* rather than purely held-out end-to-end; §10.1's V3.2 (rolling artefact rebuild) is the upgrade path.

- **(P3) Per-regime serving efficiency at deployment-tuned parameter budgets.** The v2 / M5 deployment matches v1's parameter budget exactly: 4 OOS-fit `BUFFER_BY_TARGET` scalars are replaced by 4 OOS-fit $c(\tau)$ + 4 walk-forward-fit $\delta(\tau)$, with the latter as the structural-conservatism analogue. The 12 trained per-regime quantiles replace the v1 surface (which carried per-(symbol, regime, claimed) cells at $N \approx 50$–$300$). At identical budget, M5 is 19–20% narrower at indistinguishable coverage at every $\tau \le 0.95$.

## 11.2 What the ablation says is doing the work

The §7 ladder reduces to three load-bearing components:

1. **Factor-switchboard point.** The v1 ladder showed it tightens pooled bands by 39.3% (CI [37.3%, 41.3%]). Inherited by v2 / M5 as the conformal lookup's input.

2. **Regime classifier $\rho$.** §7.1 established a deployable architecture without regime structure cannot deliver coverage on the 2023+ slice. §7.2 established the deployable architecture *with* the classifier and *without* v1's hybrid forecaster machinery is the v2 / M5 deployment.

3. **OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedules.** The 4+4 deployment-tuned scalars play the same role under v2 / M5 that the 4 BUFFER_BY_TARGET scalars played under v1: closing the train-OOS distribution-shift gap that the trained quantile leaves. §7.2.4 establishes the $\delta$ schedule is load-bearing for walk-forward Kupiec at $\tau \le 0.85$.

The remaining v1 components (VIX-scaled standardisation, log-log vol regression, per-symbol vol index, long-weekend regressor, earnings flag, hybrid regime-to-forecaster policy) are dropped by v2 / M5; the simplification is what enabled the §7.2 width reduction.

## 11.3 Honest framing

Three scoping points warrant restatement. First, the served band is *per-anchor calibrated*, not *full-distribution calibrated* — Berkowitz and DQ both reject; the rejections diagnose the regime classifier as a coarse three-bin index that absorbs first-moment variation but leaves residual autocorrelation through high-vol weekend clusters. The product contract was always per-anchor; the disclosure makes the boundary explicit and identifies the v3 target.

Second, the $\tau = 0.99$ tail ceiling under v1 is closed under v2 / M5. The trade is a 22% wider band ($677.5$ vs $522.8$ bps) for honest coverage at the consumer's nominal target. A protocol that prefers the v1 trade can recover it by requesting $\tau = 0.97$ from M5 instead. The customer-selects-coverage interface makes this trade a consumer choice.

Third, the v2 / M5 deployment is *deployment-calibrated* on the same OOS slice that §6 evaluates the served band on, via 4+4 OOS-fit scalars. The 6-split walk-forward ratifies the deployed schedule (per-anchor Kupiec $p$ = 0.43, 0.37, 0.36, 0.32) but does not upgrade the result to a purely held-out end-to-end validation. §9.3 carries the wider disclosure; §10.1's V3.2 is the upgrade path.

The remaining statistical gaps are useful bad news rather than project-fatal news. Berkowitz and DQ do not say the coverage-inversion primitive is void; they say the present implementation has reached the boundary of what an anchor-calibrated interval oracle can claim, and the §10 v3 roadmap names the path forward.

## 11.4 What sits in the companion papers

*Paper 3* addresses the mapping from a calibrated band to a $\{\texttt{Safe}, \texttt{Caution}, \texttt{Liquidate}\}$ action under explicit borrower-book LTV and a protocol-specific cost model. The active research structure is methodology (this paper) → policy (Paper 3). The coverage-inversion primitive stands alone as an oracle contract, regardless of how downstream consumers use the band.
