# Appendix G — The lending-track instantiation: one-sided downside bands

The deployed architecture of §4 serves a two-sided band. A lending protocol holding tokenised equity as collateral is exposed in **one** direction: the collateral falling below the debt it secures. This appendix instantiates the §3 primitive with a one-sided downside score, quantifies what the two-sided band costs a consumer who only faces downside, and states what would be required before it replaces the two-sided path. It is characterised, not deployed — the same standing as the full-distribution variant of Appendix F.

## G.1 Why the direction matters to the contract, not the primitive

The §3 contract is direction-agnostic. Target coverage $\tau$ is the consumer's input, the band is the output, and the receipt exposes the sufficient statistics for re-derivation. Nothing in that construction requires the served interval to be symmetric about the point estimate; symmetry enters only through the conformity score of §4.2, which is an absolute value.

That choice has a consequence the consumer does not see on the wire. A two-sided band at $\tau$ places $(1-\tau)/2$ in each tail, so **its lower edge is a $(1+\tau)/2$ one-sided bound.** A protocol wiring the $\tau = 0.85$ band into a loan-to-value haircut is provisioning to $92.5\%$, and one wiring $\tau = 0.95$ is provisioning to $97.5\%$. The number they requested and the protection they received differ, and the gap is paid in collateral.

This is also where the paper meets the conformal-VaR literature it cites. Both Schmitt [schmitt-rwc-2026] and Zhong [zhong-proxy-2026] calibrate *one-sided* VaR; the two-sided choice here is ours, not the field's, and it is a modelling convenience rather than a property of the primitive.

## G.2 Construction

Everything is held fixed against §4 except the score. Same factor-switchboard point estimator, same per-symbol $\hat\sigma_s(t)$, same Mondrian cells, same finite-sample rank $\lceil \tau(n+1) \rceil$, same $2023$-01-01 split, and the same OOS-fit $c(\tau)$ bump — applied to *every* arm, so no arm is advantaged. Because the $c(\tau)$ grid begins at $1.0$ it can only widen; it repairs under-coverage and cannot manufacture a capital saving.

$$s^{\text{2s}} = \frac{\lvert P_{\text{Mon}} - \hat P \rvert}{P_{\text{Fri}}\,\hat\sigma_s}, \qquad s^{\text{1s}} = \frac{\hat P - P_{\text{Mon}}}{P_{\text{Fri}}\,\hat\sigma_s}$$

$s^{\text{1s}}$ is signed and positive when the realised price lands *below* the point estimate, so its upper $\tau$-quantile is the downside buffer directly. The served lower edge is $\hat P - q_r(\tau)\,\hat\sigma_s\,P_{\text{Fri}}$ and no upper edge is published.

Two comparisons are reported, because they answer different questions. **Same-label** compares the one-sided band at $\tau$ against the two-sided band this paper deploys at $\tau$ — it prices the hidden conservatism. **Matched-protection** compares the one-sided band at $\tau$ against the two-sided band at $2\tau - 1$, both of which *claim* the same downside coverage — it asks whether a directly-fitted downside quantile is better than an absolute-value quantile at equal protection.

## G.3 Same-label: what the two-sided band costs

Collateral buffer, measured as the distance from the point estimate to the served lower edge in basis points of $P_{\text{Fri}}$, on the 2023+ holdout:

| $\tau$ | panel | two-sided (deployed) | one-sided | buffer freed |
|---:|---|---:|---:|---:|
| 0.68 | weekend | 130.8 | 55.0 | $-57.9\%$ |
| **0.85** | **weekend** | **213.6** | **140.7** | $\mathbf{-34.1\%}$ |
| 0.95 | weekend | 343.4 | 292.8 | $-14.7\%$ |
| 0.99 | weekend | 633.1 | 589.6 | $-6.9\%$ |
| 0.68 | overnight | 112.7 | 34.7 | $-69.2\%$ |
| **0.85** | **overnight** | **178.9** | **105.7** | $\mathbf{-40.9\%}$ |
| 0.95 | overnight | 280.1 | 213.3 | $-23.8\%$ |
| 0.99 | overnight | 474.3 | 402.8 | $-15.1\%$ |

At the default deployment anchor $\tau = 0.85$ a consumer frees roughly a third of the collateral buffer **and** receives the protection level it requested rather than an unlabelled tighter one. The saving compresses as $\tau \to 1$ because the two tails converge in relative terms; it is largest exactly where the deployment default sits.

## G.4 Matched-protection: the one-sided fit is better calibrated

At equal claimed downside coverage the capital comparison is close to a wash and splits by anchor — the one-sided fit is narrower in the body (overnight $-21.4\%$, $-8.2\%$, $-2.7\%$ at $\tau = 0.68, 0.85, 0.95$) and wider in the tail (weekend $+11.5\%$ at $0.95$, $+17.0\%$ at $0.99$). That ordering is expected rather than anomalous: the absolute-value score pools both tails and therefore carries roughly twice the effective sample for a tail quantile. Pooling helps where data is thin and costs where the symmetry assumption is wrong.

Calibration is not a wash, and it is the substantive result. Kupiec $p$ on downside breaches at matched protection:

| | $\tau=0.68$ | $\tau=0.85$ | $\tau=0.95$ | $\tau=0.99$ |
|---|---:|---:|---:|---:|
| one-sided, weekend | 0.975 | 0.973 | 0.956 | 0.942 |
| two-sided at $2\tau-1$, weekend | 0.287 | 0.569 | 0.214 | 0.276 |
| one-sided, overnight | 1.000 | 0.958 | 0.157 | 0.950 |
| **two-sided at $2\tau-1$, overnight** | **0.000** | **0.000** | **0.045** | 0.950 |

Overnight, imposing a symmetric shape on the gap distribution **fails Kupiec at three of four anchors** and holds per-symbol on only 5 of 10 and 8 of 10 symbols at $\tau = 0.68$ and $0.85$; it over-covers systematically ($0.710$ against a claimed $0.680$). The one-sided fit passes at every anchor on both panels. The symmetry assumption is measurably wrong for overnight gaps, and the direction of the error is conservative — which is why it has been invisible.

So the one-sided instantiation is not a capital optimisation dressed as a methodology change. It is the correct calibration of the quantity a lending consumer acts on.

## G.5 What is not established

This appendix reports a single experiment on the 2023+ holdout. It does **not** carry the evidence pack that supports the two-sided architecture in §6 and Appendices B–D: no leave-one-symbol-out generalisation, no nested temporal holdout, no forward-tape validation against a frozen artefact, no simulation study on synthetic ground truth, no block-bootstrap confidence intervals, no DQ or Berkowitz diagnostics, and no Rust parity. The two-sided path remains the validated deployment and the basis of every claim in the main text.

Three items would have to close before a one-sided band could replace it:

1. **The full validation battery**, re-run on the one-sided score. The machinery is score-parameterised, so this is largely re-execution rather than new construction.
2. **A new frozen artefact and its own forward tape.** This is the binding constraint and it is calendar-bound rather than effort-bound: a new freeze restarts forward accumulation at $N = 0$ and accrues one weekend per week. The two-sided freeze carries roughly a quarter of accumulated forward evidence that a switch would forfeit.
3. **A wire-format decision.** `PriceUpdate` currently carries a symmetric $(\text{point}, \text{half\_width})$; a one-sided band changes the consumer contract of §8. No integrator is live at the time of writing, so the migration cost is presently nil — a window that closes with the first integration.

## G.6 Consumer guidance

Independent of deployment, G.3 changes what a protocol should be told. A consumer whose exposure is one-directional should read the deployed two-sided band at $\tau$ as a $(1+\tau)/2$ downside bound and size collateral accordingly, or request the anchor $2\tau - 1$ to obtain $\tau$ downside protection from the two-sided path. The integration guidance of §8 states the symmetric interval without stating that consequence; that is a documentation gap in the current release, not a defect in the served value, and G.3 quantifies what it costs.
