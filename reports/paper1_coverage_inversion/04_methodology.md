# §4 — Methodology

This section instantiates the abstract setup of §3 with the concrete point estimator, per-symbol scale standardisation, conformal quantile fit, deployment-tuned schedules, and serving-time machinery of the deployed locally-weighted Mondrian split-conformal architecture, referred to as **M6** throughout. The implementation lives in `src/soothsayer/oracle.py:Oracle.fair_value_lwc` (Python) and `crates/soothsayer-oracle/src/oracle.rs::Oracle::fair_value` under `Forecaster::Lwc` (Rust). The Rust port serves both M5 (`forecaster_code = 2`, the reference path live on-chain) and M6 (`forecaster_code = 3`, `FORECASTER_LWC`) with byte-exact parity against the Python reference (180/180 cases; §8.5).

The architecture has four ingredients: a point estimator $\hat P_{\text{Mon},r}$, a strictly pre-Friday per-symbol scale $\hat\sigma_s(t)$ that standardises the conformity score, a per-regime conformal quantile $q_r(\tau)$ trained on the *standardised* residuals on a held-out calibration set, and an OOS-fit multiplicative bump $c(\tau)$ that closes any residual train-OOS distribution-shift gap. **Sixteen deployment scalars total: 12 trained per-regime quantiles + 4 OOS-fit $c(\tau)$ + 0 walk-forward $\delta(\tau)$.** The §7 ablation establishes M6 as the *deployable* simpler architecture that survives the §7.1 constant-buffer stress test and isolates each component's contribution along the M0 → M6 ladder. Figure \ref{fig:pipeline} summarises the serving pipeline.

![M6 serving pipeline: five pre-Friday inputs (factor return $r_t^F$ from the §5.4 switchboard, regime label $r$, per-symbol scale $\hat\sigma_s(t)$ from the §4.2 EWMA, consumer target $\tau$, and Friday close $p_t^{\mathrm{Fri}}$) feed a five-line lookup that returns a band $[L_t, U_t]$ around a factor-adjusted point $\hat p_t$. The 16 deployment scalars are the per-regime quantile table $q_r(\tau)$ on standardised residuals plus the OOS-fit bump schedule $c(\tau)$. Every read emits a `PricePoint` receipt carrying the four served scalars and the diagnostic quartet $(c, q_{\mathrm{eff}}, q_r, \hat\sigma_s)$ — the per-read auditability of $P_1$.\label{fig:pipeline}](figures/fig1_pipeline.pdf)

## 4.1 The point estimator $\hat P_{\text{Mon},r}$

The deployed point estimator is the per-symbol factor switchboard (§5.4):

$$\hat P_{\text{Mon},t}(s) \;=\; P_{\text{Fri},t}(s) \cdot \bigl(1 + r^{\text{factor}}_t(s)\bigr),$$

where $r^{\text{factor}}_t(s)$ is the weekend return of the per-symbol factor (ES=F for equities; GC=F for GLD; ZN=F for TLT; BTC for MSTR post-2020-08). The point estimator is the input whose residual distribution the conformal quantile is fit on, not the product. The factor-switchboard variant survived empirical pruning over an eight-variant point-estimator ladder during early development; the ladder and the empirical losses against alternatives are documented in `reports/methodology_history.md`.

## 4.2 Per-symbol pre-Friday scale $\hat\sigma_s(t)$

M6 standardises the conformity score by a per-symbol estimate of the *relative-residual* scale, computed strictly from past Fridays:

$$\hat\sigma_s(t) \;=\; \mathrm{EWMA}_{\mathrm{HL}=8}\Bigl(\bigl\{\, r^{\text{rel}}_{t'}(s) \;:\; t' < t \,\bigr\}\Bigr),\qquad r^{\text{rel}}_{t'}(s) \;=\; \frac{P_{\text{Mon},t'}(s) - \hat P_{\text{Mon},t'}(s)}{P_{\text{Fri},t'}(s)},$$

with weekend half-life $\mathrm{HL}=8$ — equivalently a geometric decay rate $\lambda = 0.5^{1/8} \approx 0.917$ per past Friday. The window is *one-sided strictly before $t$*: the standardiser at $t$ uses only $\{t' : t' < t\}$, so $\hat\sigma_s$ is itself a pre-publish quantity. We require at least eight past relative-residual observations before $\hat\sigma_s$ is defined; weekends with fewer past Fridays per symbol are dropped at warm-up (80 rows out of the 5,996-weekend panel — roughly the first eight weekends per symbol, rebased per listing date). The warm-up rule and half-life are encoded as constants `SIGMA_HAT_HL_WEEKENDS = 8` and `SIGMA_HAT_MIN = 8` and persisted on the artefact parquet as `sigma_hat_sym_pre_fri`.

The EWMA half-life HL=8 was selected from a five-variant comparison (a 26-weekend trailing-window K=26 baseline, three EWMA half-lives HL ∈ {6, 8, 12}, and a convex K=26/EWMA blend) under a pre-registered three-gate criterion: per-cell split-date Christoffersen, per-symbol Kupiec pass-rate, and a block-bootstrap CI on pooled half-width relative to the K=26 baseline. The selection procedure, its multiple-testing exposure (Benjamini–Hochberg correction at FDR=0.05), and the held-out forward-tape re-validation harness are reported in §7.3. The K=26 trailing-window variant remains buildable for archival reproduction via `scripts/build_lwc_artefact.py --variant baseline_k26`; the deployed parquet column name (`sigma_hat_sym_pre_fri`) is shared across variants so a downstream consumer reads the artefact without knowing which σ̂ rule produced it.

## 4.3 Mondrian split-conformal on standardised residuals

Conformity score: relative absolute residual *standardised by $\hat\sigma_s(t)$*:

$$s_t(s) \;=\; \frac{\bigl|P_{\text{Mon},t}(s) - \hat P_{\text{Mon},t}(s)\bigr|}{P_{\text{Fri},t}(s) \cdot \hat\sigma_s(t)}.$$

Mondrian taxonomy: weekends partition into $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ via the regime classifier $\rho(\mathcal{F}_t)$ specified in §5.5. The trained per-regime conformal quantile $q_r(\tau)$ is the standard split-CP $\lceil \tau (n+1) \rceil$-th rank quantile on the regime's training-set *standardised* scores. The deployed grid has four anchors $\tau \in \mathcal{T}_\text{anch} = \{0.68, 0.85, 0.95, 0.99\}$ and three regimes, yielding twelve trained scalars.

Calibration set: $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ — 4,186 weekend rows after the 80-row σ̂ warm-up drop. Each per-(regime, $\tau$) bin therefore carries $N \approx 430$–$2{,}720$ observations supporting one quantile estimate, comfortably above the $N \approx 50$–$300$ thresholds where Mondrian conformal becomes noisy (a per-(symbol, regime) Mondrian rung — M3 in the §7.2 ladder — was rejected during ablation development for cell-thinness reasons, with the standardised-score architecture below recovering per-symbol calibration without per-(symbol, regime) cells; details in `reports/methodology_history.md`). Deployed values of $q_r(\tau)$ are listed in `data/processed/lwc_artefact_v1.json` (audit-trail sidecar) and loaded at module import into `src/soothsayer/oracle.py:LWC_REGIME_QUANTILE_TABLE`.

The architectural choice that makes M6 work at the per-symbol level is the standardisation of the conformity score by $\hat\sigma_s(t)$ before the Mondrian quantile fit. An unweighted Mondrian comparator absorbs both the cross-symbol scale heterogeneity (HOOD's typical relative residual is $\sim 3\times$ SPY's) and the per-regime heterogeneity into one Mondrian cell; the result is bimodal per-symbol calibration error — heavy-tail tickers under-cover, low-vol tickers over-cover — and is the failure mode the §6.8 simulation study reproduces under controlled conditions. Standardising the score by $\hat\sigma_s(t)$ before fitting the per-regime quantile factors out the per-symbol scale and lets the regime quantile carry only the *shape* of the standardised residual distribution. The §6.4 evidence (10/10 per-symbol Kupiec pass at $\tau = 0.95$; per-symbol Berkowitz LR range $[3.2,\,16.7]$) and the §6.8 simulation evidence (predicted in advance under four DGPs with known ground truth) ratify this construction.

## 4.4 OOS-fit $c(\tau)$ bump

M6's bump schedule is

$$c(\tau) \;=\; \{0.68\!:\!1.000,\;0.85\!:\!1.000,\;0.95\!:\!1.079,\;0.99\!:\!1.003\},$$

a near-identity correction that *only* widens at $\tau = 0.95$ (by 7.9%) and is essentially the identity at the other three anchors. The fit procedure: $c(\tau)$ is the smallest $c \in [1, 5]$ such that pooled OOS realised coverage with effective quantile $c \cdot q_r(\tau)$ matches the target $\tau$. Four scalars total. Three of the four are essentially identity, so only $c(0.95) = 1.079$ carries meaningful OOS information; §9.3 carries the full provenance disclosure for that one scalar.

## 4.5 The walk-forward $\delta(\tau)$ schedule is identically zero

A 4-split expanding-window walk-forward sweep over $\delta \in \{0.00, 0.01, \ldots, 0.07\}$ on tune fractions $f \in \{0.40, 0.50, 0.60, 0.70\}$ of the OOS index (script: `scripts/run_lwc_delta_sweep.py`; output: `reports/tables/v1b_lwc_delta_sweep.csv`) selects, under the criterion *smallest $\delta$ such that walk-forward realised coverage $\geq \tau$ on every powered split*,

$$\delta(\tau) \;=\; \{0.68\!:\!0.00,\;0.85\!:\!0.00,\;0.95\!:\!0.00,\;0.99\!:\!0.00\}.$$

The smaller $f \in \{0.20, 0.30\}$ tune fractions are excluded as under-powered: at $n_\text{tune} \in \{35, 52\}$ weekends the 4-scalar $c(\tau)$ fit collapses to identity at one or more anchors (the 0.20 split at $\tau \ge 0.95$; the 0.30 split at $\tau = 0.99$, where 52 tune weekends cannot reliably estimate the 99th percentile), so the resulting bands under-cover at those anchors regardless of $\delta$. The 0.40 split ($n_\text{tune} = 69$) is the smallest fraction whose $c(\tau)$ fit is non-identity at every served anchor under the deployed EWMA HL=8 σ̂. Per-symbol scale standardisation tightens cross-split realised-coverage variance enough that no structural-conservatism shift is required across the 4 powered splits — worst-split deficits at $\delta = 0$ are positive at every $\tau$ (worst-split coverage $\ge \tau$), so $\delta(\tau) = 0$ is the smallest schedule satisfying the criterion. The schedule is retained as a four-zero-vector in the artefact JSON for shape-compatibility with the receipt schema, but the deployment carries zero walk-forward-tuned scalars.

## 4.6 Serving-time band construction

Given a consumer-chosen target $\tau \in (0, 1)$ at $(s, t)$, the served band is constructed in five steps:

1. *Look up the regime, point, per-symbol scale, and Friday close.* Read $r = \rho(\mathcal{F}_t)$, $\hat P_{\text{Mon},t}(s)$, $\hat\sigma_s(t)$, and $P_{\text{Fri},t}(s)$ from `lwc_artefact_v1.parquet`.
2. *Look up the standardised quantile.* $q_r = q_r(\tau)$, with $q_r$ linearly interpolated off-anchor.
3. *Apply the OOS bump.* $q_\text{eff} = c(\tau) \cdot q_r(\tau)$, with $c$ linearly interpolated off-anchor; $\delta(\tau) \equiv 0$ so no shift step is needed.
4. *Construct the band.* The conformity score the per-regime quantile was fit on is the *standardised* relative residual $|P_{\text{Mon}} - \hat P| / (P_{\text{Fri}} \cdot \hat\sigma_s)$ (§4.3), so the band is fri-close-relative with the per-symbol scale entering multiplicatively: $\text{half}_t = q_\text{eff} \cdot \hat\sigma_s(t) \cdot P_{\text{Fri},t},\ \text{lower} = \hat P_{\text{Mon},t} - \text{half}_t,\ \text{upper} = \hat P_{\text{Mon},t} + \text{half}_t$. The half-width in basis points is $10^4 \cdot c(\tau) \cdot q_r(\tau) \cdot \hat\sigma_s(t)$ — heavy-tail tickers receive wider bands than low-vol tickers at identical $\tau$ and identical regime.
5. *Emit the receipt.* The served band's claimed coverage is $\tau$; the receipt's `forecaster_used` is the literal string `lwc` (on-chain `forecaster_code = 3`, `FORECASTER_LWC`; live in the Rust serving stack as of the §8.5 parity-180/180 milestone). Diagnostics expose $c(\tau)$, $q_r(\tau)$, $q_\text{eff}$, $\hat\sigma_s(t)$, $r$, and Friday close.

The serving-time computation is a five-line lookup against the per-Friday artefact + the two constant schedules. There is no surface inversion, no bracketing in claimed-coverage space, and no per-symbol fallback — the per-symbol behaviour is carried *implicitly* by the per-symbol $\hat\sigma_s(t)$ scale on the artefact parquet, not by a per-symbol quantile cell.

## 4.7 The PricePoint receipt and reproducibility

Every read returns a `PricePoint` exposing the band plus eight receipt fields: `target_coverage` ($\tau$), `claimed_coverage_served` ($\tau$ — equal to the request since $\delta \equiv 0$), `forecaster_used` (`lwc`), `regime` ($r$), `sharpness_bps`, and `diagnostics.{c_bump, q_regime_lwc, sigma_hat_sym_pre_fri, q_eff}`. A third party with the audit-trail sidecar and the per-Friday artefact can reconstruct the served band from the receipt alone: read $\hat P$, $r$, $\hat\sigma_s$, and $P_{\text{Fri}}$ from the artefact, read $q_\text{eff}$ from the receipt, verify $\text{lower} = \hat P - q_\text{eff} \cdot \hat\sigma_s \cdot P_{\text{Fri}}$ and $\text{upper} = \hat P + q_\text{eff} \cdot \hat\sigma_s \cdot P_{\text{Fri}}$ to floating-point precision. This is the operational instantiation of $P_1$. $\hat\sigma_s(t)$ is itself a deterministic function of past Fridays' relative residuals and the EWMA half-life constant, so the third-party reconstruction is a one-pass scan over public-data inputs.

Implementation: Python (`src/soothsayer/oracle.py:Oracle.fair_value_lwc`) is the canonical reference; the Rust port (`crates/soothsayer-oracle` under `Forecaster::Lwc`) carries byte-exact parity (180/180 cases; §8.5). At submission the on-chain wire-format slot `forecaster_code = 3` is encoded into new publishes from `crates/soothsayer-publisher`; on-chain enablement is gated on the next publisher release. Reproduction:

```
uv run python scripts/build_lwc_artefact.py        # per-Friday artefact + JSON sidecar
uv run python scripts/freeze_lwc_artefact.py       # content-addressed freeze for forward-tape eval
uv run python scripts/smoke_oracle.py --forecaster lwc   # cross-regime API demo
```

All inputs are public and free (§5.7); verifying a published band needs only the sidecar and the per-Friday artefact — under 100 KB per symbol-year. The σ̂ window is recomputable from the same parquet given only the half-life constant, so the artefact is self-contained.
