# §3 — Problem Statement (draft for arXiv paper)

## 3.1 Setup and notation

Let $\mathcal{S} = \{s_1, \ldots, s_K\}$ be a finite universe of assets (in our evaluation, ten US equities, ETFs, and hybrid crypto-proxies) and let $t \in \mathbb{N}$ index a sequence of *prediction windows* — in this paper, non-trading weekends defined by $[t_\mathrm{pub}, t_\mathrm{tgt}] =$ (Friday 16:00 ET, Monday 09:30 ET).

For each $(s, t)$ we observe:

- $P_t(s) \in \mathbb{R}_{>0}$: the realised reference price at $t_\mathrm{tgt}$ (Monday open).
- $\mathcal{F}_t(s)$: pre-publish information available at $t_\mathrm{pub}$. This includes $P_{t^-}(s)$ (Friday close), contemporaneous factor returns (E-mini S&P, gold, 10Y treasury, BTC futures), implied-vol indices (VIX, GVZ, MOVE), a calendar flag $\mathrm{earn}_t(s) \in \{0,1\}$ for an earnings release in the coming week, and a gap-length flag $\ell_t \in \{0,1\}$ for calendar weekends $\geq 4$ days.
- A *regime labeler* $\rho: \mathcal{F}_t(s) \to \mathcal{R}$ with $\mathcal{R} = \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$, defined purely on pre-publish information.

A *base forecaster* $f$ emits, at each $(s, t, q)$ with claimed quantile $q \in (0,1)$, a band $\bigl[L^f_t(s; q), U^f_t(s; q)\bigr]$.

## 3.2 The classical oracle problem

A conventional point-plus-CI oracle publishes, at each $t_\mathrm{pub}$, a triple $(\hat P_t, L_t, U_t)$ with an *implicit* or *undisclosed* coverage level. The consumer has no contract on the realised rate at which $P_t \in [L_t, U_t]$. When CI widths are derived from publisher dispersion (Pyth) or a fixed Gaussian heuristic (Chainlink staleness fallback), the mapping from the CI to a realised probability-of-coverage statement is neither asserted nor auditable.

## 3.3 The coverage-inversion primitive

We define a stricter contract. Fix a base forecaster $f$, a regime labeler $\rho$, a discrete claimed-quantile grid $\mathcal{Q} \subset (0,1)$, and a rolling historical dataset

$$\mathcal{D} = \bigl\{ \bigl( P_t(s), \mathcal{F}_t(s), \{(L^f_t(s;q), U^f_t(s;q))\}_{q \in \mathcal{Q}}, \rho(\mathcal{F}_t(s)) \bigr) : t \in \mathcal{T}_\mathrm{hist} \bigr\}.$$

The **empirical calibration surface** is the mapping

$$S^f(s, r, q) \;=\; \frac{1}{|\mathcal{T}_{s,r}|} \sum_{t \in \mathcal{T}_{s,r}} \mathbf{1}\!\bigl[\, L^f_t(s; q) \le P_t(s) \le U^f_t(s; q)\, \bigr],$$

where $\mathcal{T}_{s,r} = \{t \in \mathcal{T}_\mathrm{hist} : \text{symbol}=s,\ \rho(\mathcal{F}_t(s)) = r\}$.

Given a *consumer-chosen* target coverage $\tau \in (0,1)$, the oracle serves the band at

$$q_\mathrm{served}(s, r, \tau) \;=\; (S^f)^{-1}(s, r, \tau),$$

with $(S^f)^{-1}$ defined by linear interpolation between bracketing grid points and a documented fallback to a pooled surface $S^f(\cdot, r, q)$ when $|\mathcal{T}_{s,r}| < n_\mathrm{min}$.

The oracle read is the tuple

$$\texttt{PricePoint}(s, t, \tau) \;=\; \bigl(\hat P, L^f_t(s; q_\mathrm{served}), U^f_t(s; q_\mathrm{served}),\ q_\mathrm{served},\ r,\ f\bigr),$$

exposing $q_\mathrm{served}$ and $f$ as calibration *receipts* alongside the band itself.

## 3.4 Properties we claim

**(P1) Auditability.** $\mathcal{D}$ is reproducible from public data sources (freely available price feeds, vol indices, and earnings calendars). Given $(\mathcal{D}, f, \rho, \mathcal{Q})$, the surface $S^f$ is deterministic; thus any third party can reconstruct $S^f$ and independently verify that the served band corresponds to the published $q_\mathrm{served}$.

**(P2) Conditional empirical coverage.** Under the assumption that the conditional distribution $P_t \mid (\mathcal{F}_t,\ \text{regime})$ is stationary across $\mathcal{T}_\mathrm{hist}$ and the evaluation set, the realised coverage of the served band satisfies

$$\Pr\!\bigl[\,P_t \in [L^f_t(s; q_\mathrm{served}),\ U^f_t(s; q_\mathrm{served})]\ \big|\ \rho(\mathcal{F}_t)=r,\ s\,\bigr] \;\longrightarrow\; \tau$$

as $|\mathcal{T}_{s,r}| \to \infty$. Finite-sample deviations are measurable, tested (§6), and disclosed as a per-regime *calibration buffer* applied pre-inversion.

**(P3) Per-regime sharpness dominance.** For each regime $r$, the oracle selects $f^\star(r) \in \arg\min_{f} \mathrm{E}\!\bigl[U^f - L^f \mid \text{realised cov} = \tau,\, r\bigr]$ from a candidate set $\mathcal{F}$. In our evaluation $\mathcal{F} = \{\texttt{F0\_stale}, \texttt{F1\_emp\_regime}\}$; §7 reports the ablation matrix that justifies both the inclusion of $\texttt{F1\_emp\_regime}$'s extra regressors and the hybrid regime-to-forecaster assignment $f^\star(\cdot)$.

## 3.5 Non-goals

We explicitly do not claim:

1. **Optimal point estimates.** $\hat P$ is the midpoint of a band calibrated for coverage, not a minimum-variance estimator. We make no claim to improve over Pyth / Chainlink on point accuracy during market hours.
2. **Parametric tail guarantees.** The surface is empirical; shock-regime coverage is bounded above by the fraction of historical observations in the same tail of the forecast distribution (§9).
3. **Distribution-free coverage.** P2 requires stationarity of the conditional distribution. A conformalised variant (Vovk, Barber et al.) would upgrade the statement to a finite-sample guarantee under exchangeability; we flag this as future work.
4. **Protection against adversarial data feeds.** Soothsayer is a calibration-transparency primitive, not an integrity primitive. Its value proposition is orthogonal to oracle manipulation resistance; it is intended to be integrated *alongside*, not in place of, an adversarially-robust price feed.

## 3.6 Evaluation questions

The body of the paper answers:

- **Q1** (calibration, §6). Does the served band achieve $\tau$ within 2pp on held-out data? What is the Kupiec unconditional-coverage $p$-value, and do violations cluster (Christoffersen independence $p$)?
- **Q2** (sharpness, §6–§7). How much tighter than a naïve stale-hold Gaussian baseline is the served band at matched realised coverage, per regime?
- **Q3** (ablations, §7). Which components of $f^\star$ (factor switchboard, log-log vol regression, earnings regressor, long-weekend regressor, hybrid regime selection, empirical buffer) are load-bearing for the P2/P3 claims, and which are not?
- **Q4** (auditability, §4 + artifact). Can a third party reconstruct $S^f$ on public data and independently verify a served `PricePoint`?
