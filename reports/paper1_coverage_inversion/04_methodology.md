# §4 — Methodology (v2 / locally-weighted Mondrian deployment)

This section instantiates the abstract setup of §3 with the concrete point estimator, per-symbol scale standardisation, conformal quantile fit, deployment-tuned schedules, and serving-time machinery of the deployed locally-weighted Mondrian split-conformal architecture. We refer to it throughout as **v2** — the variant adopted at the bottom of §7.2's ablation ladder. v2 supersedes the previously-deployed Mondrian split-conformal variant **v1**, which now sits one rung up the ladder as the predecessor whose per-symbol calibration failure (§6.4.1) v2 was designed to close. The implementation lives in `src/soothsayer/oracle.py:Oracle.fair_value_lwc` (Python). The Rust parity port (`crates/soothsayer-oracle`) is currently v1-only with the v2 wire-format slot reserved (`forecaster_code = 3`, FORECASTER_LWC); the v2 Rust port is gated to a productionisation milestone independent of this paper's empirical content.

The architecture has four ingredients: a point estimator $\hat P_{\text{Mon},r}$, a strictly pre-Friday per-symbol scale $\hat\sigma_s(t)$ that standardises the conformity score, a per-regime conformal quantile $q_r(\tau)$ trained on the *standardised* residuals on a held-out calibration set, and an OOS-fit multiplicative bump $c(\tau)$ that closes any residual train-OOS distribution-shift gap. Sixteen deployment scalars total (12 trained per-regime quantiles + 4 OOS-fit $c(\tau)$ + 0 walk-forward $\delta(\tau)$, all four of which collapse to zero under v2 — see §4.5). The §7 ablation shows this is the *deployable* simpler architecture that survives the §7.1 constant-buffer stress test and isolates each component's contribution along the M0 → v2 ladder. Figure \ref{fig:pipeline} summarises the serving pipeline.

![v2 serving pipeline: five pre-Friday inputs (factor return $r_t^F$ from the §5.4 switchboard, regime label $r$, per-symbol scale $\hat\sigma_s(t)$ from the §4.2 EWMA, consumer target $\tau$, and Friday close $p_t^{\mathrm{Fri}}$) feed a five-line lookup that returns a band $[L_t, U_t]$ around a factor-adjusted point $\hat p_t$. The 16 deployment scalars are the per-regime quantile table $q_r(\tau)$ on standardised residuals plus the OOS-fit bump schedule $c(\tau)$; the walk-forward $\delta(\tau)$ schedule is identically zero under v2. Every read emits a `PricePoint` receipt carrying the four served scalars and the diagnostic quartet $(c, q_{\mathrm{eff}}, q_r^{\text{LWC}}, \hat\sigma_s)$ — the per-read auditability of $P_1$.\label{fig:pipeline}](figures/fig1_pipeline.pdf)

## 4.1 The point estimator $\hat P_{\text{Mon},r}$

The deployed point estimator is the per-symbol factor switchboard (§5.4):

$$\hat P_{\text{Mon},t}(s) \;=\; P_{\text{Fri},t}(s) \cdot \bigl(1 + r^{\text{factor}}_t(s)\bigr),$$

where $r^{\text{factor}}_t(s)$ is the weekend return of the per-symbol factor (ES=F for equities; GC=F for GLD; ZN=F for TLT; BTC for MSTR post-2020-08). The point estimator is the input whose residual distribution the conformal quantile is fit on, not the product. The same factor-switchboard point estimator is used by v1 and v2; the architectural change at the v2 rung is in the conformity score (§4.3), not the point. Eight point-estimator variants were considered in early development (the Soothsayer-v0 forecaster ladder); the factor-switchboard variant survived empirical pruning and is the shared point input for both deployed methodologies.

## 4.2 Per-symbol pre-Friday scale $\hat\sigma_s(t)$

The locally-weighted Mondrian primitive in v2 standardises the conformity score by a per-symbol estimate of the *relative-residual* scale, computed strictly from past Fridays:

$$\hat\sigma_s(t) \;=\; \mathrm{EWMA}_{\mathrm{HL}=8}\Bigl(\bigl\{\, r^{\text{rel}}_{t'}(s) \;:\; t' < t \,\bigr\}\Bigr),\qquad r^{\text{rel}}_{t'}(s) \;=\; \frac{P_{\text{Mon},t'}(s) - \hat P_{\text{Mon},t'}(s)}{P_{\text{Fri},t'}(s)},$$

with weekend half-life $\mathrm{HL}=8$ — equivalently a geometric decay rate $\lambda = 0.5^{1/8} \approx 0.917$ per past Friday. The window is *one-sided strictly before $t$*: the standardiser at $t$ uses only $\{t' : t' < t\}$, so $\hat\sigma_s$ is itself a pre-publish quantity. We require at least eight past relative-residual observations before $\hat\sigma_s$ is defined; weekends with fewer past Fridays per symbol are dropped at warm-up (80 rows out of the 5,996-weekend panel — roughly the first eight weekends per symbol, rebased per listing date). The warm-up rule and half-life are encoded as constants `SIGMA_HAT_HL_WEEKENDS = 8` and `SIGMA_HAT_MIN = 8` and persisted on the artefact parquet as `sigma_hat_sym_pre_fri`.

The EWMA half-life HL=8 was selected from a five-variant comparison (a 26-weekend trailing-window K=26 baseline, three EWMA half-lives HL ∈ {6, 8, 12}, and a convex K=26/EWMA blend) under a pre-registered three-gate criterion: per-cell split-date Christoffersen, per-symbol Kupiec pass-rate, and a block-bootstrap CI on pooled half-width relative to the K=26 baseline. The selection procedure, its multiple-testing exposure (Benjamini-Hochberg correction at FDR=0.05), and the held-out forward-tape re-validation harness are reported in §7.3. The K=26 trailing-window variant remains buildable for archival reproduction via `scripts/build_lwc_artefact.py --variant baseline_k26`; the deployed parquet column name (`sigma_hat_sym_pre_fri`) is shared across variants so a downstream consumer reads the artefact without knowing which σ̂ rule produced it.

## 4.3 Mondrian split-conformal on standardised residuals

Conformity score: relative absolute residual *standardised by $\hat\sigma_s(t)$*:

$$s_t(s) \;=\; \frac{\bigl|P_{\text{Mon},t}(s) - \hat P_{\text{Mon},t}(s)\bigr|}{P_{\text{Fri},t}(s) \cdot \hat\sigma_s(t)}.$$

Mondrian taxonomy: weekends partition into $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ via the regime classifier $\rho(\mathcal{F}_t)$ specified in §5.5. The trained per-regime conformal quantile $q_r^{\text{LWC}}(\tau)$ is the standard split-CP $\lceil \tau (n+1) \rceil$-th rank quantile on the regime's training-set *standardised* scores, identical in finite-sample form to the v1 fit. The deployed grid has four anchors $\tau \in \mathcal{T}_\text{anch} = \{0.68, 0.85, 0.95, 0.99\}$ and three regimes, yielding twelve trained scalars.

Calibration set: $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ — 4,186 weekend rows after the 80-row σ̂ warm-up drop, decomposing by regime to roughly the same train counts v1 used (v1: 4,266 rows; v2: 4,186 rows; the difference is the 80 warm-up exclusions). Each per-(regime, $\tau$) bin therefore carries $N \approx 430$–$2{,}720$ observations supporting one quantile estimate, comfortably above the $N \approx 50$–$300$ thresholds where Mondrian conformal becomes noisy (the per-(symbol, regime) Mondrian rung M3, §7.2, fails Christoffersen for exactly this sample-size reason). Deployed values of $q_r^{\text{LWC}}(\tau)$ are listed in `data/processed/lwc_artefact_v1.json` (audit-trail sidecar) and loaded at module import into `src/soothsayer/oracle.py:LWC_REGIME_QUANTILE_TABLE`.

The standardisation is the single architectural change between v1 and v2. v1's quantile table absorbs both the cross-symbol scale heterogeneity (HOOD's typical relative residual is ~3× SPY's) and the per-regime heterogeneity into one Mondrian cell; the result is bimodal per-symbol calibration error — heavy-tail tickers (TSLA, HOOD, MSTR) under-cover, low-vol tickers (SPY, QQQ, GLD, TLT) over-cover, with HOOD's violation rate climbing to 13.9% at nominal 5% (§6.4.1). Standardising the score by $\hat\sigma_s(t)$ before fitting the per-regime quantile factors out the per-symbol scale and lets the regime quantile carry only the *shape* of the standardised residual distribution. The §6.4 evidence (10/10 per-symbol Kupiec pass under v2 vs 2/10 under v1; per-symbol Berkowitz LR range collapses from 0.9–224 to 3.3–18) and the §6.Y simulation evidence (predicted in advance under four DGPs with known ground truth) ratify this construction.

## 4.4 OOS-fit $c(\tau)$ bump

Under v1 the OOS bump schedule was $\{0.68\!:\!1.498,\, 0.85\!:\!1.455,\, 0.95\!:\!1.300,\, 0.99\!:\!1.076\}$ — meaningful widening at every anchor, attributable to the train-OOS scale-distribution shift the standardiser was not yet absorbing. Under v2 the schedule is

$$c(\tau) \;=\; \{0.68\!:\!1.000,\;0.85\!:\!1.000,\;0.95\!:\!1.079,\;0.99\!:\!1.003\},$$

a near-identity correction that *only* widens at $\tau = 0.95$ (by 7.9%) and is essentially the identity at the other three anchors. The fit procedure is unchanged: $c(\tau)$ is the smallest $c \in [1, 5]$ such that pooled OOS realised coverage with effective quantile $c \cdot q_r^{\text{LWC}}(\tau)$ matches the target $\tau$. Four scalars total. The shrinkage of the $c(\tau)$ schedule from "meaningful widening at every anchor" to "near-identity at three of four" substantially narrows the OOS-tuning provenance disclosure of §9.3: under v1, eight of the twenty deployment scalars (4 $c$ + 4 $\delta$) were tuned on the OOS slice; under v2, three of the sixteen (one non-trivial $c$, two near-identity $c$) carry meaningful OOS information.

## 4.5 The walk-forward $\delta(\tau)$ schedule collapses to zero

Under v1, a plain $c(\tau)$ fit to the pooled OOS slice produced per-split realised coverage that scattered around nominal — passed Kupiec on the pooled fit by construction, but undercovered in roughly half the splits. v1 added a four-scalar walk-forward $\delta(\tau) = \{0.05,\, 0.02,\, 0.00,\, 0.00\}$ to push every split above nominal. Under v2 the same walk-forward sweep over $\delta \in \{0.00, 0.01, \ldots, 0.07\}$ is run (script: `scripts/run_lwc_delta_sweep.py`; output: `reports/tables/v1b_lwc_delta_sweep.csv`); the selection criterion — smallest $\delta$ such that walk-forward realised coverage $\geq \tau$ on every split — is satisfied at

$$\delta(\tau) \;=\; \{0.68\!:\!0.00,\;0.85\!:\!0.00,\;0.95\!:\!0.00,\;0.99\!:\!0.00\}.$$

Per-symbol scale standardisation tightens cross-split realised-coverage variance enough that the structural-conservatism shim is no longer load-bearing. Worst-split deficits at $\tau=0.95$ ($-1.74$pp) and $\tau=0.99$ ($-0.23$pp) are within walk-forward sampling noise; raising $\delta$ to clear them costs $+30$%/$+53$% on width (the $\tau=0.99$ jump is a $c$-grid discontinuity) for negligible coverage gain. The schedule is retained as a one-zero-vector in the artefact JSON for shape-compatibility with the v1 sidecar, but the deployment carries zero walk-forward-tuned scalars.

## 4.6 Serving-time band construction

Given a consumer-chosen target $\tau \in (0, 1)$ at $(s, t)$, the served band is constructed in five steps:

1. *Look up the regime, point, and per-symbol scale.* Read $r = \rho(\mathcal{F}_t)$, $\hat P_{\text{Mon},t}(s)$, and $\hat\sigma_s(t)$ from `lwc_artefact_v1.parquet`.
2. *Look up the standardised quantile.* $q_r^{\text{LWC}} = q_r^{\text{LWC}}(\tau)$, with $q_r^{\text{LWC}}$ linearly interpolated off-anchor.
3. *Apply the OOS bump.* $q_\text{eff} = c(\tau) \cdot q_r^{\text{LWC}}(\tau) \cdot \hat\sigma_s(t)$, with $c$ linearly interpolated off-anchor; $\delta(\tau) \equiv 0$ under v2 so no shift step is needed.
4. *Construct the band.* $\text{lower} = \hat P_{\text{Mon},t} (1 - q_\text{eff}),\ \text{upper} = \hat P_{\text{Mon},t} (1 + q_\text{eff})$. The half-width in basis points is $10^4 \cdot c(\tau) \cdot q_r^{\text{LWC}}(\tau) \cdot \hat\sigma_s(t)$ — the per-symbol scale enters multiplicatively and is the mechanism by which a heavy-tail ticker receives a wider band than a low-vol ticker at identical $\tau$ and identical regime.
5. *Emit the receipt.* The served band's claimed coverage is $\tau$; the receipt's `forecaster_used` is the literal string `lwc` (on-chain `forecaster_code` slot reserved as 3, FORECASTER_LWC; the Rust parity port is gated on a productionisation milestone — see §8). Diagnostics expose $c(\tau)$, $q_r^{\text{LWC}}(\tau)$, $q_\text{eff}$, $\hat\sigma_s(t)$, $r$, and Friday close.

The serving-time computation is a five-line lookup against the per-Friday artefact + the two constant schedules. There is no surface inversion, no bracketing in claimed-coverage space, and no per-symbol fallback — the per-symbol behaviour is carried *implicitly* by the per-symbol $\hat\sigma_s(t)$ scale on the artefact parquet, not by a per-symbol quantile cell.

## 4.7 The PricePoint receipt and reproducibility

Every read returns a `PricePoint` exposing the band plus eight receipt fields: `target_coverage` ($\tau$), `claimed_coverage_served` ($\tau$ — equal to the request under v2 since $\delta \equiv 0$), `forecaster_used` (`lwc`), `regime` ($r$), `sharpness_bps`, and `diagnostics.{c_bump, q_regime_lwc, sigma_hat_sym_pre_fri, q_eff}`. A third party with the audit-trail sidecar and the per-Friday artefact can reconstruct the served band from the receipt alone: read $\hat P$, $r$, and $\hat\sigma_s$ from the artefact, read $q_\text{eff}$ from the receipt, verify $\text{lower} = \hat P (1 - q_\text{eff})$ and $\text{upper} = \hat P (1 + q_\text{eff})$ to floating-point precision. This is the operational instantiation of $P_1$. The σ̂ standardisation does not change the auditability surface — $\hat\sigma_s(t)$ is itself a deterministic function of past Fridays' relative residuals and the EWMA half-life constant, so the third-party reconstruction is a one-pass scan over the same public-data inputs v1 used.

Implementation: Python (`src/soothsayer/oracle.py:Oracle.fair_value_lwc`) is the canonical reference; the Rust port (`crates/soothsayer-oracle`) is currently v1-only and the v2 parity port is treated as a productionisation milestone (Phase 7 of the v2 promotion plan; Rust port complete or partial state at submission is recorded in §8.5). Reproduction:

```
uv run python scripts/build_lwc_artefact.py        # per-Friday artefact + JSON sidecar
uv run python scripts/freeze_lwc_artefact.py       # content-addressed freeze for forward-tape eval
uv run python scripts/smoke_oracle.py --forecaster lwc   # cross-regime API demo
```

All inputs are public and free (§5.7); verifying a published band needs only the sidecar and the per-Friday artefact — under 100 KB per symbol-year. The σ̂ window is recomputable from the same parquet given only the half-life constant, so the artefact is self-contained.
