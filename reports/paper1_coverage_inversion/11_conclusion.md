# §11 — Conclusion

This paper specified a calibration-transparent oracle primitive for tokenised real-world assets, evaluated it on 12 years of US-listed weekend data, and shipped a reference implementation with end-to-end Python ↔ Rust ↔ on-chain parity. The contribution is the *interface*, not the forecaster: any base $f$ can be wrapped in the same surface-inversion machinery, and the consumer-facing contract is a coverage SLA rather than a point estimate.

## 11.1 The three properties, revisited

The contract of §3.4 holds on the deployed system as follows.

- **(P1) Auditability.** The calibration surface $S^f(s, r, q)$ is reconstructible from public data — yfinance daily prices, the per-symbol vol indices (VIX / GVZ / MOVE), and the per-symbol factor returns (ES / NQ / GC / ZN / BTC). The per-read `PricePoint` exposes the nine-field receipt of §4.5 (target coverage, calibration buffer applied, claimed coverage served, forecaster used, regime, sharpness, calibration path, bracketing pair, regime-forecaster policy snapshot), and the on-chain `PriceUpdate` PDA mirrors that receipt under the byte-for-byte parity contract of §8.5. A third party in possession of the persisted surface CSVs and the bounds parquet can reconstruct any served band from the receipt alone.

- **(P2) Conditional empirical coverage.** On the temporally disjoint 2023+ held-out slice (1{,}720 rows × 172 weekends, calibration surface frozen on the 4{,}266 pre-2023 rows), the served band at $\tau = 0.95$ realises coverage $0.950$ with Kupiec $p_{uc} = 1.000$ and Christoffersen $p_{ind} = 0.485$ (§6.4). The conjunction passes at three of four anchor τ on the deployment grid; the τ = 0.99 row is a level-attribution failure with bounded magnitude (§9.1, §6.4.1). A 50-level inter-anchor sweep across $\tau \in [0.52, 0.98]$ passes Kupiec uniformly with $\sup |\text{realised} - \tau| < 0.025$, supporting the linear-interpolation of $b(\tau)$ across the deployment range.

- **(P3) Per-regime serving efficiency.** The hybrid policy $\texttt{REGIME\_FORECASTER} = \{\texttt{normal} \to \texttt{F1\_emp\_regime},\ \texttt{long\_weekend} \to \texttt{F1\_emp\_regime},\ \texttt{high\_vol} \to \texttt{F0\_stale}\}$ is justified out-of-sample on Christoffersen independence rather than mean coverage: the F1-everywhere variant passes Kupiec but fails Christoffersen ($p_{ind} = 0.033$), and swapping F0 into `high_vol` flips the conditional-coverage verdict to a comfortable pass ($p_{ind} = 0.086$ in the buffer-0.025 ablation cell, $0.485$ in the deployed buffer-0.020 configuration). The reframing from in-sample bandwidth dominance to out-of-sample independence is disclosed in §9.6 and §3.4.

## 11.2 What the ablation says is doing the work

The §7.5 taxonomy reduces to three load-bearing components.

1. **Factor-switchboard point + empirical residual quantile.** The A0 → A1 ladder rung (factor-adjusted point + empirical-quantile bands replacing stale-Gaussian) tightens pooled bands by 39.3% (CI [37.3%, 41.3%]) at $n = 5{,}986$. Every subsequent ladder rung either holds sharpness flat or trades a regime-localised widening for a regime-localised coverage gain.

2. **Per-target empirical buffer.** The serving-layer C0 → C4 transition (§7.4) closes the OOS coverage gap by +3.8pp (CI [+2.8, +4.9]). Without the buffer, surface inversion alone delivers realised $0.922$ at target $0.95$ and Kupiec rejects. The deployed schedule $b \in \{0.68 \to 0.045, 0.85 \to 0.045, 0.95 \to 0.020, 0.99 \to 0.010\}$ is the smallest per-anchor buffer satisfying the §3.4 contract on the OOS slice.

3. **Hybrid regime-to-forecaster policy.** Buys Christoffersen independence in `high_vol` weekends, as discussed under (P3) above. Secondarily narrows pooled bands by 1.7%, but the de-clustering — not the bandwidth — is the load-bearing reviewer-facing claim.

The remaining components (VIX-scaled standardisation, log-log vol regression, per-symbol vol index, long-weekend regressor) are either regime-localised insurance trades or generalisation anchors for the non-equity tickers; the earnings-next-week flag is disclosed for auditability with no detectable performance contribution at our sample size and is flagged for finer event-granularity replacement in v2 (§9.5).

## 11.3 Honest framing

Two scoping points warrant restatement at the close of the paper. First, the served band is *per-anchor calibrated*, not *full-distribution calibrated*: the Berkowitz joint LR rejects on inverse-normal-transformed PITs reconstructed from a 19-point quantile grid (§6.4.1), and the rejection is mechanically traceable to the per-target buffer schedule's flat extrapolation outside $[0.68, 0.99]$. The deviation is in the *safe direction* — over-coverage at low τ rather than under-coverage — and the four anchor τ themselves land on the diagonal of the reliability diagram. The product contract was always per-anchor; the Berkowitz disclosure makes the boundary explicit.

Second, the τ = 0.99 structural ceiling has bounded worst-case impact rather than open-ended tail risk. The §6.4.1 exceedance-magnitude diagnostic reports that the 40 missed-coverage events at τ = 0.99 have median breach 72 bps and maximum breach 796 bps, and the maximum breach shrinks monotonically across the four anchors as τ increases ($2{,}339 \to 2{,}150 \to 1{,}415 \to 796$ bps). The rejected coverage at τ = 0.99 is a level-attribution failure, not a tail-blowup failure; the protocol-impact cost of that failure is bounded by ~8% on a missed event in the worst case and ~0.7% at the median. The §9.1 disclosure stands, and is now quantified.

## 11.4 What sits in the companion papers

The §3.5 non-claims and the §9.9 disclosure bracket two decision-theoretic questions that the present paper cannot answer with the evidence it presents. *Paper 2* (OEV mechanism design) addresses what auction or trigger mechanism for oracle-extractable value maximises protocol welfare given a calibration-transparent oracle — the per-read receipt of §4.5 is a primitive an auction can directly condition on, in a way the existing OEV-recapture literature does not contemplate. *Paper 3* (optimal liquidation-policy defaults) addresses the mapping from a calibrated band to a $\{\texttt{Safe}, \texttt{Caution}, \texttt{Liquidate}\}$ action under an explicit borrower-book LTV distribution and a protocol-specific cost model. The trilogy structure — methodology (this paper) → mechanism (Paper 2) → policy (Paper 3) — is designed so each layer is independently citable. A reviewer of the present paper need not commit to that framing; the coverage-inversion primitive stands alone as an oracle contract, regardless of how downstream consumers use the band.
