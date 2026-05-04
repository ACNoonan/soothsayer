# §11 — Conclusion

This paper specified a calibration-transparent oracle primitive for tokenised real-world assets, evaluated it on 12 years of US-listed weekend data, and shipped a reference implementation with end-to-end Python ↔ Rust ↔ on-chain parity. The contribution is the *interface* (consumer-selects-coverage with a per-read receipt) and the *deployable architecture* (Mondrian split-conformal by regime + factor-adjusted point + δ-shifted $c(\tau)$), arrived at through the precursor v1 forecaster ablation, the §7.1 constant-buffer stress test, and the §7.2 Mondrian head-to-head.

## 11.1 The three properties, revisited

- **(P1) Auditability.** The deployment artefact (per-Friday parquet + 20-scalar JSON sidecar) is reconstructible from public data — Soothsayer consumes Scryer parquet for Yahoo daily prices, the per-symbol factor returns (ES / NQ / GC / ZN / BTC), and the regime classifier inputs. The per-read `PricePoint` exposes the eight-field receipt of §4.5, and the on-chain `PriceUpdate` PDA mirrors that receipt under the byte-for-byte parity contract of §8.5. A third party with the sidecar and the per-Friday artefact can reconstruct any served band from the receipt alone.

- **(P2) Conditional empirical coverage.** On the 2023+ slice (1{,}730 rows × 173 weekends), the served band at $\tau = 0.95$ realises $0.950$ with Kupiec $p_{uc} = 0.956$ and Christoffersen $p_{ind} = 0.912$ at $354.5$ bps half-width — a 20% reduction over v1 on the same slice. At $\tau = 0.99$ the band realises $0.990$ ($p_{uc} = 0.942$), closing v1's tail ceiling at the cost of a 22% wider band. Kupiec passes at all four anchors; Christoffersen passes at $\tau \in \{0.85, 0.95, 0.99\}$ and rejects at $\tau = 0.68$. The empirical content of P2 is *per-anchor calibration*, not full-distribution calibration (Berkowitz LR $= 173.1$, DQ at $\tau = 0.95$ $p = 5.7 \times 10^{-6}$). The number is *deployment-calibrated and walk-forward-stable* rather than purely held-out end-to-end (see §6.3 / §9.3); §10.1's V3.2 is the upgrade path.

- **(P3) Per-regime serving efficiency at deployment-tuned parameter budgets.** v2 / M5 matches v1's parameter budget exactly: 4 OOS-fit `BUFFER_BY_TARGET` scalars are replaced by 4 OOS-fit $c(\tau)$ + 4 walk-forward-fit $\delta(\tau)$, with the latter as the structural-conservatism analogue. The 12 trained per-regime quantiles replace the v1 surface (which carried per-(symbol, regime, claimed) cells at $N \approx 50$–$300$). At identical budget, M5 is 19–20% narrower at indistinguishable coverage at every $\tau \le 0.95$.

## 11.2 What the ablation says is doing the work

The §7 ladder reduces to three load-bearing components:

1. **Factor-switchboard point.** The v1 ladder showed it tightens pooled bands by 39.3% (CI [37.3%, 41.3%]). Inherited by v2 / M5 as the conformal lookup's input.

2. **Regime classifier $\rho$.** §7.1 established a deployable architecture without regime structure cannot deliver coverage on the 2023+ slice. §7.2 established the deployable architecture *with* the classifier and *without* v1's hybrid forecaster machinery is the v2 / M5 deployment.

3. **OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedules.** The 4+4 deployment-tuned scalars play the same role under v2 / M5 that the 4 BUFFER_BY_TARGET scalars played under v1: closing the train-OOS distribution-shift gap. §7.2.4 establishes the $\delta$ schedule is load-bearing for walk-forward Kupiec at $\tau \le 0.85$.

The remaining v1 components (VIX-scaled standardisation, log-log vol regression, per-symbol vol index, long-weekend regressor, earnings flag, hybrid regime-to-forecaster policy) are dropped by v2 / M5; the simplification is what enabled the §7.2 width reduction.

## 11.3 Honest framing

The served band is *per-anchor calibrated*, not *full-distribution calibrated* — Berkowitz and DQ both reject. §6.3.1 / §9.4 localise the rejection to *cross-sectional within-weekend* common-mode residual ($\hat\rho_\text{cross} = 0.354$, $p < 10^{-100}$) rather than temporal autocorrelation; a vol-tertile sub-split of `normal` regime leaves Berkowitz LR essentially unchanged, ruling out finer regime granularity as the lever. §6.4.1 reports the per-symbol calibration error is *bimodal*: SPY/QQQ/GLD/TLT/AAPL reject from variance compression (bands too wide); TSLA/HOOD/MSTR reject from variance expansion (bands too narrow); HOOD specifically fails per-symbol Kupiec at $\tau \in \{0.68, 0.85, 0.95\}$ and passes at $\tau = 0.99$. §10.4 enumerates concrete candidate v3 architectures (locally-weighted conformal, full-distribution CQR) targeting these per-symbol and per-anchor disclosures; none are adopted in this paper.

The v1 $\tau = 0.99$ tail ceiling is closed under v2 / M5 at a 22% wider band; a protocol that prefers the v1 trade can recover it by requesting $\tau = 0.97$ from M5 (linearly interpolated between the $\tau = 0.95$ and $\tau = 0.99$ anchors; not directly Kupiec-validated at the anchor grid). The 4+4 OOS-tuned scalars are the load-bearing concession (§9.3): three independent provenance checks (6-split walk-forward, 4-anchor split-date sensitivity, 10-fold leave-one-symbol-out) agree the deployed schedule generalises across time but is moderately fragile to held-out heavy-tail tickers — a symptom of the same single-multiplier-on-heterogeneous-tails mechanism. The served claim is endpoint-conditional; §6.6 reports a residual ${\sim}7$–$10$pp intra-weekend path-coverage shortfall on a small ($n = 118$) perp slice, approximately closed by stepping up one anchor; band-aware AMM consumers (Paper 4) wait for the v3 path-fitted variant (§10.1's V3.3, mechanically validated on the CME-projected subset).

The textbook econometric default — per-symbol GARCH(1,1) on log Friday-to-Monday returns with Gaussian innovations — fails Kupiec at $\tau \in \{0.68, 0.95, 0.99\}$ on the same OOS slice and is at parity at $\tau = 0.85$ (§6.4.2). At matched 95% realised coverage, GARCH's mean half-width is **8.8% wider** than M5's ($385.7$ vs $354.6$ bps), establishing M5 dominance on both calibration and sharpness once the coverage-width point is held fixed.

The remaining statistical gaps are useful bad news rather than project-fatal news. Berkowitz and DQ do not say the coverage-inversion primitive is void; they say the present implementation has reached the boundary of what a single-multiplier anchor-calibrated interval oracle can claim. §10 names the candidate paths forward.

## 11.4 What sits in the companion papers

*Paper 3* addresses the mapping from a calibrated band to a $\{\texttt{Safe}, \texttt{Caution}, \texttt{Liquidate}\}$ action under explicit borrower-book LTV and a protocol-specific cost model. The active research structure is methodology (this paper) → policy (Paper 3). The coverage-inversion primitive stands alone as an oracle contract, regardless of how downstream consumers use the band.
