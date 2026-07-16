# §3 — The Primitive

## 3.1 Setup and notation

Let $\mathcal{S} = \{s_1, \ldots, s_K\}$ be a finite universe of assets (in our evaluation, ten US equities, ETFs, and hybrid crypto-proxies) and let $t \in \mathbb{N}$ index a sequence of *closed-market prediction windows* $[t_\mathrm{pub}, t_\mathrm{tgt}]$, each the interval between a venue close ($t_\mathrm{pub}$) and its next open ($t_\mathrm{tgt}$). We evaluate two instances: the **weekend** window (Friday 16:00 ET → Monday 09:30 ET), the primary panel of §6, and the **overnight** window (close → next-day 09:30 ET open), §6's generalization panel.

For each $(s, t)$ we observe:

- $P_t(s) \in \mathbb{R}_{>0}$: the realised reference price at $t_\mathrm{tgt}$ (the next open).
- $\mathcal{F}_t(s)$: the conditioning information for the window. The features fixed at $t_\mathrm{pub}$ are $P_{t^-}(s)$ (the close), the implied-vol indices (VIX, GVZ, MOVE), a calendar flag $\mathrm{earn}_t(s) \in \{0,1\}$ for a scheduled earnings release inside the window (a release in the coming week on the weekend panel; a release dated inside the close→open gap, by BMO/AMC session, on the overnight panel), and a gap-length flag $\ell_t \in \{0,1\}$ for calendar weekends $\geq 4$ days (weekend panel only). The one input that is *not* fixed at $t_\mathrm{pub}$ is the contemporaneous factor return (E-mini S&P, gold, 10Y Treasury, BTC futures): it is observable *during* the closed window because Globex futures and BTC trade through it, and is the sole input requiring post-publish computation at serve time (§5.3, §5.4).
- A *regime labeler* $\rho: \mathcal{F}_t(s) \to \mathcal{R}$ defined purely on pre-publish information, with a cadence-specific partition: $\mathcal{R}_\text{weekend} = \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ and $\mathcal{R}_\text{overnight} = \{\texttt{normal}, \texttt{high\_vol}, \texttt{earnings\_night}\}$ (§5).

A *base forecaster* $f$ emits, at each $(s, t, q)$ with claimed quantile $q \in (0,1)$, a band $\bigl[L^f_t(s; q), U^f_t(s; q)\bigr]$.

## 3.2 The classical oracle problem

A conventional point-plus-band oracle publishes, at each $t_\mathrm{pub}$, a triple $(\hat P_t, L_t, U_t)$ whose coverage level is *implicit* or *undisclosed*, so the consumer holds no contract on the realised rate at which $P_t \in [L_t, U_t]$. The §1.2 taxonomy (Table T1) confirms this concretely: whether a band is derived from publisher dispersion, a deviation clamp, or a staleness heuristic, the mapping to a realised probability-of-coverage statement is neither asserted nor auditable.

## 3.3 The coverage-inversion primitive

We define a stricter contract. Fix a base forecaster $f$, a regime labeler $\rho$, a discrete claimed-quantile grid $\mathcal{Q} \subset (0,1)$, and a rolling historical dataset

$$\mathcal{D} = \bigl\{ \bigl( P_t(s), \mathcal{F}_t(s), \{(L^f_t(s;q), U^f_t(s;q))\}_{q \in \mathcal{Q}}, \rho(\mathcal{F}_t(s)) \bigr) : t \in \mathcal{T}_\mathrm{hist} \bigr\}.$$

The **empirical calibration surface** is the mapping

$$S^f(s, r, q) \;=\; \frac{1}{|\mathcal{T}_{s,r}|} \sum_{t \in \mathcal{T}_{s,r}} \mathbf{1}\!\bigl[\, L^f_t(s; q) \le P_t(s) \le U^f_t(s; q)\, \bigr],$$

where $\mathcal{T}_{s,r} = \{t \in \mathcal{T}_\mathrm{hist} : \text{symbol}=s,\ \rho(\mathcal{F}_t(s)) = r\}$.

Given a *consumer-chosen* target coverage $\tau \in (0,1)$, the oracle serves the band at

$$q_\mathrm{served}(s, r, \tau) \;=\; (S^f)^{-1}(s, r, \tau),$$

with $(S^f)^{-1}$ defined by linear interpolation between bracketing grid points and a documented fallback to a pooled surface $S^f(\cdot, r, q)$ when $|\mathcal{T}_{s,r}| < n_\mathrm{min}$. The deployed grid anchors $\tau$ at four audited targets, $\{0.68, 0.85, 0.95, 0.99\}$; an off-anchor request is served by interpolation and disclosed as interpolated rather than separately validated (§8).

The oracle read is the tuple

$$\texttt{PricePoint}(s, t, \tau) \;=\; \bigl(\hat P,\ L,\ U;\ \tau,\ c(\tau),\ q_r(\tau),\ \hat\sigma_s(t),\ r,\ f\bigr),$$

the band plus a six-field calibration **receipt**. Authoritatively, the receipt fields and their wire names are: the target coverage $\tau$ (`target_coverage`, echoed as `claimed_coverage_served`, equal to the request since the deployed shift $\delta \equiv 0$); the calibration buffer $c(\tau)$ (`diagnostics.c_bump`); the per-regime conformal quantile $q_r(\tau)$ (`diagnostics.q_regime_lwc`); the pre-window per-symbol scale $\hat\sigma_s(t)$ (`diagnostics.sigma_hat_sym_pre_fri`); the regime label $r$ (`regime`); and the base-forecaster identifier $f$ (`forecaster_used`). The half-width is echoed in basis points (`sharpness_bps`) and the composite $q_\mathrm{eff} = c(\tau)\, q_r(\tau)$ as a derived convenience field (`diagnostics.q_eff`). Under the deployed architecture (§4), the receipt fields are sufficient statistics for the band — $q_\mathrm{served}$ realises as the factorisation $c(\tau)\, q_r(\tau)$ applied at the per-symbol scale $\hat\sigma_s(t)$, giving

$$L = \hat P - c(\tau)\, q_r(\tau)\, \hat\sigma_s(t)\, P_{t^-}, \qquad U = \hat P + c(\tau)\, q_r(\tau)\, \hat\sigma_s(t)\, P_{t^-},$$

so a verifier recomputes the band from the receipt to floating-point precision, and re-derives the surface behind it from public data. Figure H2 traces this round trip — $\tau$ in, band plus receipt out, third-party re-derivation of $S^f$ and the served band from public inputs alone.

![**H2 — Anatomy of a read.** A consumer chooses the target coverage $\tau$ at one of four audited anchors $\{0.68, 0.85, 0.95, 0.99\}$; the oracle resolves the five-step lookup against the frozen per-Friday artefact and returns the band $(\hat P, L, U)$ together with the calibration receipt — $\tau$ (`target_coverage`), $r$ (`regime`), $f$ (`forecaster_used`), and the diagnostic triple $c(\tau)$, $q_r(\tau)$, $\hat\sigma_s(t)$ (`diagnostics.c_bump`, `diagnostics.q_regime_lwc`, `diagnostics.sigma_hat_sym_pre_fri`). Because the receipt fields are sufficient statistics for the band, a third party re-derives $L$ and $U$ to floating-point precision from the receipt plus the public artefact (under 100 KB per symbol-year) and can rebuild the calibration surface itself from public data: coverage is the input, and the receipt makes the claim checkable.](figures/fig_h2_anatomy_of_a_read.pdf)

## 3.4 Properties we claim

**(P1) Auditability.** $\mathcal{D}$ is reproducible from public data sources (freely available price feeds, vol indices, and earnings calendars). Given $(\mathcal{D}, f, \rho, \mathcal{Q})$, the surface $S^f$ is deterministic; thus any third party can reconstruct $S^f$ and independently verify that the served band corresponds to the published receipt.

**(P2) Conditional empirical coverage.** Under the assumption that the conditional distribution $P_t \mid (\mathcal{F}_t,\ \text{regime})$ is stationary across $\mathcal{T}_\mathrm{hist}$ and the evaluation set, the realised coverage of the served band satisfies

$$\Pr\!\bigl[\,P_t \in [L^f_t(s; q_\mathrm{served}),\ U^f_t(s; q_\mathrm{served})]\ \big|\ \rho(\mathcal{F}_t)=r,\ s\,\bigr] \;\longrightarrow\; \tau$$

as $|\mathcal{T}_{s,r}| \to \infty$. Finite-sample deviations are measured, tested (§6), and disclosed as the calibration buffer $c(\tau)$; the power of each test — minimum detectable effect per anchor — is tabulated in Appendix B.

**(P3) Per-regime serving efficiency at deployment-tuned parameter budgets.** The efficiency criterion is mean bandwidth at matched realised coverage *and* per-symbol Kupiec pass rate. On this criterion, §7's ablation establishes empirical dominance over the deployable alternatives evaluated on this panel — the constant-buffer baseline, the un-standardised Mondrian comparator, and parametric GARCH-Gaussian / GARCH-$t$ baselines — with the band served as the §3.3 factorisation at a sixteen-scalar parameter budget (Appendix A) and the σ̂ rule itself selected under a pre-registered, multiple-testing-corrected gate (§7; variant ladder in Appendix D).

## 3.5 Non-goals

We explicitly do not claim:

1. **Optimal point estimates.** $\hat P$ is the midpoint of a band calibrated for coverage, not a minimum-variance estimator. We make no claim to improve on incumbent oracles' point accuracy during market hours.
2. **Parametric tail guarantees.** The surface is empirical; shock-regime coverage is bounded above by the fraction of historical observations in the same tail of the forecast distribution (§8).
3. **Distribution-free coverage.** P2 assumes stationarity of the *standardised* conditional distribution; $\hat\sigma_s(t)$ provides partial adaptive scaling, but the assumption remains. A conformalised variant (Vovk; Barber et al.) would upgrade the statement to a finite-sample guarantee under exchangeability — an open extension (§9).
4. **Protection against adversarial data feeds.** Coverage transparency is orthogonal to upstream-feed integrity: the primitive ingests upstream price signals and republishes them as a calibrated band, its coverage claim conditional on the integrity of those feeds. It is designed to operate alongside, not in place of, an adversarially-robust price feed.
5. **σ̂ rule optimality.** The deployed σ̂ rule (EWMA, half-life 8) is justified by a pre-registered three-gate selection procedure under multiple-testing correction with held-out forward-tape re-validation (§7). We do not claim it is optimal among locally-weighted variants.
6. **Optimal lending-policy defaults.** We do not identify the welfare-optimal liquidation rule, collateral haircut, or target $\tau$ for a lending protocol; those require account-weight distributions, protocol-specific loss functions, and outcome semantics outside this paper's evidence.
7. **Universal asset-class scope.** The primitive requires a *continuous off-hours information set* — a public, sub-daily signal correlated with the closed-market underlier, as index futures and VIX supply for equities, gold futures and GVZ for gold, Treasury futures and MOVE for rates, and CDS spreads for credit. Real estate, illiquid commodities, and primarily NAV-priced instruments lack such a signal and are out of scope.
