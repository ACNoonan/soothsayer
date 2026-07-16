# §4 — Architecture

The deployed architecture is a locally-weighted Mondrian split-conformal band around a factor-adjusted point estimate, and it has four ingredients: a point estimator $\hat P_{\text{Mon},r}$, a strictly pre-publish per-symbol scale $\hat\sigma_s(t)$ that standardises the conformity score, per-regime conformal quantiles $q_r(\tau)$ fit on the standardised residuals, and a near-identity out-of-sample bump $c(\tau)$. This section presents each ingredient in serving order — the order in which a read resolves them — then the five-step lookup and the receipt every read emits. Figure \ref{fig:pipeline} summarises the pipeline; §7 isolates which components are load-bearing.

![Serving pipeline: five pre-Friday inputs (factor return $r_t^F$ from the §5.4 switchboard, regime label $r$, per-symbol scale $\hat\sigma_s(t)$, consumer target $\tau$, and Friday close $p_t^{\mathrm{Fri}}$) feed a five-step lookup that returns a band $[L_t, U_t]$ around a factor-adjusted point $\hat p_t$. The sixteen deployment scalars are the per-regime quantile table $q_r(\tau)$ plus the bump schedule $c(\tau)$. Every read emits a `PricePoint` receipt carrying the served scalars — the per-read auditability of $P_1$.\label{fig:pipeline}](figures/fig1_pipeline.pdf)

## 4.1 Regime labeler

Every read first resolves a regime label $r = \rho(\mathcal{F}_t) \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ via the strict priority cascade defined in §5.5, computed from pre-publish quantities only: the VIX percentile at Friday close and the calendar-gap length. The label selects which quantile column serves the read; nothing downstream of the label is symbol-specific except the scale $\hat\sigma_s(t)$.

## 4.2 Point estimator

The point estimator is the per-symbol factor switchboard (§5.4):

$$\hat P_{\text{Mon},t}(s) \;=\; P_{\text{Fri},t}(s) \cdot \bigl(1 + r^{\text{factor}}_t(s)\bigr),$$

where $r^{\text{factor}}_t(s)$ is the weekend return of the per-symbol factor (ES=F for equities; GC=F for GLD; ZN=F for TLT; BTC for MSTR post-2020-08). The construction encodes a standard result of the price-discovery literature — index futures lead the cash market and carry the dominant information share [stoll-whaley-1990; hasbrouck-1995; gonzalo-granger] — and Globex futures and BTC trade through the weekend, so the factor return is observable while the reference market is closed. The point estimator is the input whose residual distribution the conformal quantile is fit on, not the product.

## 4.3 Per-symbol pre-publish scale $\hat\sigma_s(t)$

The conformity score is standardised by a per-symbol estimate of the relative-residual scale, computed strictly from past Fridays:

$$\hat\sigma_s(t) \;=\; \mathrm{EWMA}_{\mathrm{HL}=8}\Bigl(\bigl\{\, r^{\text{rel}}_{t'}(s) : t' < t \,\bigr\}\Bigr),\qquad r^{\text{rel}}_{t'}(s) \;=\; \frac{P_{\text{Mon},t'}(s) - \hat P_{\text{Mon},t'}(s)}{P_{\text{Fri},t'}(s)},$$

with half-life $\mathrm{HL}=8$ weekends (geometric decay $\lambda = 0.5^{1/8} \approx 0.917$ per past Friday). The window is one-sided, strictly before $t$, so $\hat\sigma_s$ is itself a pre-publish quantity. At least eight past observations are required before $\hat\sigma_s$ is defined; weekends with fewer are dropped at warm-up (80 of 5,996 panel rows). The half-life was selected under a pre-registered three-gate criterion (Appendix D); constants and the construction algorithm are in Appendix A.

## 4.4 Mondrian split-conformal on standardised residuals

The conformity score is the relative absolute residual standardised by $\hat\sigma_s(t)$:

$$s_t(s) \;=\; \frac{\bigl|P_{\text{Mon},t}(s) - \hat P_{\text{Mon},t}(s)\bigr|}{P_{\text{Fri},t}(s) \cdot \hat\sigma_s(t)}.$$

Weekends partition into the three regimes of §4.1, and the trained per-regime quantile $q_r(\tau)$ is the standard split-conformal $\lceil \tau(n+1) \rceil$-th rank quantile of the regime's training-set standardised scores. The deployed grid has four anchors $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ and three regimes: twelve trained scalars, fit on the 4,186-row pre-2023 calibration set (§5.6), leaving $N \approx 430$–$2{,}720$ observations per (regime, $\tau$) bin — comfortably above the $N \approx 50$–$300$ range where Mondrian conformal becomes noisy. With the four $c(\tau)$ bumps below, the complete deployment surface is sixteen scalars (Table A.2).

Standardising the score *before* the Mondrian fit is the choice that makes the per-symbol calibration claim hold. A comparator that skips it absorbs cross-symbol scale heterogeneity — HOOD's typical relative residual is $\sim 3\times$ SPY's — into one cell, producing bimodal per-symbol calibration error: heavy-tail tickers under-cover, low-vol tickers over-cover. Standardisation factors out the per-symbol scale so the regime quantile carries only the *shape* of the residual distribution. The evidence is in §6.4 (10/10 per-symbol Kupiec at $\tau = 0.95$) and the Appendix C simulation study, which reproduces the bimodality under known ground truth and closes it with σ̂ standardisation on every generating process. Within-bin exchangeability — the assumption yielding finite-sample marginal coverage per cell — is empirically supported (Appendix B).

## 4.5 The $c(\tau)$ bump

The deployed bump schedule,

$$c(\tau) \;=\; \{0.68\!:\!1.000,\;0.85\!:\!1.000,\;0.95\!:\!1.079,\;0.99\!:\!1.003\},$$

is the smallest $c \in [1, 5]$ per anchor such that pooled out-of-sample realised coverage with effective quantile $c \cdot q_r(\tau)$ matches the target. Three of the four values are essentially identity; only $c(0.95) = 1.079$ carries meaningful out-of-sample information, and §8 carries the provenance disclosure for that one scalar. A companion additive shift $\delta(\tau)$ is identically zero under walk-forward selection (Appendix D) and is retained in the artefact only for receipt-schema compatibility.

## 4.6 Serving-time band construction

Given a consumer-chosen $\tau$ at $(s, t)$, the served band is a five-step lookup:

1. *Read the inputs.* $r$, $\hat P_{\text{Mon},t}(s)$, $\hat\sigma_s(t)$, and $P_{\text{Fri},t}(s)$ from the per-Friday artefact.
2. *Look up the quantile.* $q_r(\tau)$, linearly interpolated between the four anchors and clipped outside them.
3. *Apply the bump.* $q_\text{eff} = c(\tau) \cdot q_r(\tau)$, with $c$ interpolated on the same anchors.
4. *Construct the band.* $\text{half}_t = q_\text{eff} \cdot \hat\sigma_s(t) \cdot P_{\text{Fri},t}$; $[L, U] = \hat P_{\text{Mon},t} \pm \text{half}_t$. The half-width in basis points is $10^4 \cdot c(\tau) \cdot q_r(\tau) \cdot \hat\sigma_s(t)$: heavy-tail tickers receive wider bands than low-vol tickers at identical $\tau$ and regime.
5. *Emit the receipt* (§4.8).

Calibration evidence in §6 is reported at the four audited anchors only; off-anchor $\tau$ values receive interpolated multipliers with no separate audited evidence, a disclosure §8 carries. There is no surface inversion and no per-symbol fallback — per-symbol behaviour is carried implicitly by $\hat\sigma_s(t)$ on the artefact, not by a per-symbol quantile cell.

## 4.7 Calendar-conditioned coverage

The architecture is parameterised by a gap selector: the weekend panel admits Friday→Monday pairs; the overnight panel of §6.8 admits consecutive-trading-day pairs with a one-line change and no change to any downstream component. The regime partition is re-derived per cadence (definitions and counts in §5.5); the overnight set adds `earnings_night`, the first regime the architecture conditions on *a priori*. Unlike `high_vol` — a market state inferred from trailing VIX — an earnings release is a scheduled event with a publicly known date and session, so the band widens deterministically *ahead* of the information event, before any volatility is realised. We term this **calendar-conditioned coverage**; to our knowledge, no production oracle (Pyth, Chainlink Data Streams, RedStone, Kamino Scope) widens its feed for a scheduled earnings release. Each release is assigned to the single overnight gap it drives via session timing — an after-close report dated $t_0$ or a before-open report dated $t_1$ fires inside the close$(t_0)$→open$(t_1)$ gap. Standardised by the same $\hat\sigma_s(t)$ the band uses, the realised move on earnings nights has $p_{99} \approx 9.7$ versus $\approx 2.0$ on other nights; the fitted $q_{\texttt{earnings\_night}}(\tau)$ runs $\approx 8\times$ $q_{\texttt{normal}}(\tau)$, and §6 shows the resulting band is calibrated, not merely wide, with the event-study result in Figure H4.

**σ̂ de-contamination.** Because an earnings residual can be $\sim 8\sigma$, admitting it to the EWMA scale would over-widen the subsequent half-life of *normal* nights and induce clustered post-earnings violations. Earnings-night residuals are therefore excluded from the $\hat\sigma_s$ estimation pool — every night still receives a $\hat\sigma_s$ built from its non-earnings history — assigning the earnings excess to the `earnings_night` quantile rather than the scale. Earnings fatness is a regime effect, not a per-symbol scale effect. This separation restores overnight violation independence and collapses the overnight $c(\tau)$ bumps to $\approx 1.0$ (§6.8).

## 4.8 The PricePoint receipt

Every read returns a `PricePoint` carrying the band plus the receipt fields formalised in §3: the target $\tau$, the regime $r$, the wire-format forecaster tag, sharpness in basis points, and the diagnostic quartet $(c(\tau),\, q_r(\tau),\, q_\text{eff},\, \hat\sigma_s(t))$. A third party holding the audit-trail sidecar and the per-Friday artefact can re-derive the served band from the receipt alone — read $\hat P$, $r$, $\hat\sigma_s$, and $P_{\text{Fri}}$ from the artefact, read $q_\text{eff}$ from the receipt, and verify $L = \hat P - q_\text{eff} \cdot \hat\sigma_s \cdot P_{\text{Fri}}$ and $U = \hat P + q_\text{eff} \cdot \hat\sigma_s \cdot P_{\text{Fri}}$ to floating-point precision. And because every input upstream of the artefact is public (§5.7), the audit does not stop at the band: the same third party can rebuild the calibration surface itself — re-fit the sixteen scalars from public data — and check that the published quantiles are the ones the method produces. Verifying a published band needs only the sidecar and the per-Friday artefact, under 100 KB per symbol-year; the σ̂ column is recomputable from the same parquet given only the half-life constant, so the artefact is self-contained. This is the operational instantiation of $P_1$.

## 4.9 Deployment

The architecture is deployed. The Python `Oracle` (`src/soothsayer/oracle.py`) is the executable specification; a Rust serving stack (`crates/soothsayer-oracle`) and an Anchor on-chain program serve the same bands under a byte-for-byte parity contract — 180/180 verification cases across both forecaster paths (Appendix E) — so a consumer can verify a served `PricePoint` against the published artefact without trusting either implementation in isolation. Wire format, on-chain invariants, and the crate stack are documented in Appendix E.
