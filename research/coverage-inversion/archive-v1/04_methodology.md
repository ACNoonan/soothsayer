# §4 — Methodology

This section instantiates the abstract setup of §3 with the concrete point estimator, per-symbol scale standardisation, conformal quantile fit, deployment-tuned schedules, and serving-time machinery of the deployed locally-weighted Mondrian split-conformal architecture. The implementation lives in `src/soothsayer/oracle.py:Oracle.fair_value_lwc` (Python) and `crates/soothsayer-oracle/src/oracle.rs::Oracle::fair_value` (Rust), with byte-exact parity against the Python reference (180/180 cases; §8.5). The on-chain wire format and code-tag taxonomy are described in §8.

The architecture has four ingredients: a point estimator $\hat P_{\text{Mon},r}$, a strictly pre-Friday per-symbol scale $\hat\sigma_s(t)$ that standardises the conformity score, a per-regime conformal quantile $q_r(\tau)$ trained on the *standardised* residuals on a held-out calibration set, and an OOS-fit multiplicative bump $c(\tau)$ that closes any residual train-OOS distribution-shift gap. The trained / tuned scalar count and the a-priori hyperparameter list are tabulated in §A.2. The §7 ablation isolates the load-bearing components — regime stratification, per-symbol σ̂ standardisation, and the near-identity OOS $c(\tau)$ bump — by descriptive comparator (constant-buffer baseline, unweighted Mondrian) rather than by code tag. Figure \ref{fig:pipeline} summarises the serving pipeline.

![Serving pipeline: five pre-Friday inputs (factor return $r_t^F$ from the §5.4 switchboard, regime label $r$, per-symbol scale $\hat\sigma_s(t)$ from the §4.2 EWMA, consumer target $\tau$, and Friday close $p_t^{\mathrm{Fri}}$) feed a five-line lookup that returns a band $[L_t, U_t]$ around a factor-adjusted point $\hat p_t$. The 16 deployment scalars are the per-regime quantile table $q_r(\tau)$ on standardised residuals plus the OOS-fit bump schedule $c(\tau)$. Every read emits a `PricePoint` receipt carrying the four served scalars and the diagnostic quartet $(c, q_{\mathrm{eff}}, q_r, \hat\sigma_s)$ — the per-read auditability of $P_1$.\label{fig:pipeline}](figures/fig1_pipeline.pdf)

## 4.1 The point estimator $\hat P_{\text{Mon},r}$

The deployed point estimator is the per-symbol factor switchboard (§5.4):

$$\hat P_{\text{Mon},t}(s) \;=\; P_{\text{Fri},t}(s) \cdot \bigl(1 + r^{\text{factor}}_t(s)\bigr),$$

where $r^{\text{factor}}_t(s)$ is the weekend return of the per-symbol factor (ES=F for equities; GC=F for GLD; ZN=F for TLT; BTC for MSTR post-2020-08). The point estimator is the input whose residual distribution the conformal quantile is fit on, not the product. The factor-switchboard variant survived empirical pruning over an eight-variant point-estimator ladder during early development; the ladder and the empirical losses against alternatives are documented in `reports/methodology_history.md`.

## 4.2 Per-symbol pre-Friday scale $\hat\sigma_s(t)$

The architecture standardises the conformity score by a per-symbol estimate of the *relative-residual* scale, computed strictly from past Fridays:

$$\hat\sigma_s(t) \;=\; \mathrm{EWMA}_{\mathrm{HL}=8}\Bigl(\bigl\{\, r^{\text{rel}}_{t'}(s) \;:\; t' < t \,\bigr\}\Bigr),\qquad r^{\text{rel}}_{t'}(s) \;=\; \frac{P_{\text{Mon},t'}(s) - \hat P_{\text{Mon},t'}(s)}{P_{\text{Fri},t'}(s)},$$

with weekend half-life $\mathrm{HL}=8$ — equivalently a geometric decay rate $\lambda = 0.5^{1/8} \approx 0.917$ per past Friday. The window is *one-sided strictly before $t$*: the standardiser at $t$ uses only $\{t' : t' < t\}$, so $\hat\sigma_s$ is itself a pre-publish quantity. We require at least eight past relative-residual observations before $\hat\sigma_s$ is defined; weekends with fewer past Fridays per symbol are dropped at warm-up (80 rows out of the 5,996-weekend panel — roughly the first eight weekends per symbol, rebased per listing date). The warm-up rule and half-life are encoded as constants `SIGMA_HAT_HL_WEEKENDS = 8` and `SIGMA_HAT_MIN = 8` and persisted on the artefact parquet as `sigma_hat_sym_pre_fri`.

The EWMA half-life HL=8 was selected from a five-variant ladder under a pre-registered three-gate criterion (split-date Christoffersen, per-symbol Kupiec, bootstrap CI on pooled half-width vs the K=26 baseline) with Benjamini–Hochberg correction across the 80-cell grid; full procedure and held-out forward-tape re-validation in §7.4.

## 4.3 Mondrian split-conformal on standardised residuals

Conformity score: relative absolute residual *standardised by $\hat\sigma_s(t)$*:

$$s_t(s) \;=\; \frac{\bigl|P_{\text{Mon},t}(s) - \hat P_{\text{Mon},t}(s)\bigr|}{P_{\text{Fri},t}(s) \cdot \hat\sigma_s(t)}.$$

Mondrian taxonomy: weekends partition into $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ via the regime classifier $\rho(\mathcal{F}_t)$ specified in §5.5. The trained per-regime conformal quantile $q_r(\tau)$ is the standard split-CP $\lceil \tau (n+1) \rceil$-th rank quantile on the regime's training-set *standardised* scores. The deployed grid has four anchors $\tau \in \mathcal{T}_\text{anch} = \{0.68, 0.85, 0.95, 0.99\}$ and three regimes, yielding twelve trained scalars.

Calibration set: $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ — 4,186 weekend rows after the 80-row σ̂ warm-up drop. Each per-(regime, $\tau$) bin therefore carries $N \approx 430$–$2{,}720$ observations supporting one quantile estimate, comfortably above the $N \approx 50$–$300$ thresholds where Mondrian conformal becomes noisy (a per-(symbol, regime) Mondrian rung was rejected during ablation development for cell-thinness reasons, with the standardised-score architecture below recovering per-symbol calibration without per-(symbol, regime) cells; details in `reports/methodology_history.md`). Deployed values of $q_r(\tau)$ are listed in `data/processed/lwc_artefact_v1.json` (audit-trail sidecar) and loaded at module import into `src/soothsayer/oracle.py:LWC_REGIME_QUANTILE_TABLE`.

The architectural choice that makes the per-symbol calibration claim hold is the standardisation of the conformity score by $\hat\sigma_s(t)$ before the Mondrian quantile fit. An unweighted Mondrian comparator absorbs both the cross-symbol scale heterogeneity (HOOD's typical relative residual is $\sim 3\times$ SPY's) and the per-regime heterogeneity into one Mondrian cell; the result is bimodal per-symbol calibration error — heavy-tail tickers under-cover, low-vol tickers over-cover — and is the failure mode the §6.7 simulation study reproduces under controlled conditions. Standardising the score by $\hat\sigma_s(t)$ before fitting the per-regime quantile factors out the per-symbol scale and lets the regime quantile carry only the *shape* of the standardised residual distribution. The §6.4 evidence (10/10 per-symbol Kupiec pass at $\tau = 0.95$; per-symbol Berkowitz LR range $[3.2,\,16.7]$) and the §6.7 simulation evidence (the bimodality reproduced under four DGPs with known ground truth and σ̂ standardisation closes it on every DGP) ratify this construction.

Within-bin exchangeability — the assumption that yields finite-sample marginal coverage within each Mondrian cell — is empirically supported (permutation test on lag-1 standardised-score autocorrelation; §A.9). The §6.3.6 / §9.4 cross-sectional dependence is *across* bins, not within.

### 4.3.1 Overnight regime set and calendar-conditioned coverage

The architecture is parameterised by a gap selector (`gap_mode`): the deployed weekend panel admits Friday→Monday pairs; the overnight panel of §6.8 admits consecutive-trading-day pairs with a one-line change and no change to any downstream component. The Mondrian taxonomy is re-derived per cadence. Overnight, `long_weekend` has no analog and is dropped; `high_vol` is retained but its trailing-VIX quartile uses a 252-trading-day lookback (≈1 year, matching the weekend's 52-weekend window); and a new regime, `earnings_night`, is added.

`earnings_night` is the first regime the architecture conditions on *a priori*. Unlike `high_vol` — a market state inferred from trailing VIX — an earnings release is a **scheduled event with a publicly known date and session**, so the band can widen deterministically *ahead* of a known information event, before any volatility is realised. We term this **calendar-conditioned coverage**, and to our knowledge no production oracle (Pyth, Chainlink Data Streams, RedStone, Kamino Scope) widens its feed for a scheduled earnings release. An earnings event is assigned to the single overnight gap it actually drives via session timing: an after-close (`amc`) report dated $t_0$ or a before-open (`bmo`) report dated $t_1$ fires inside the close$(t_0)$→open$(t_1)$ gap (a date-only flag that brackets both adjacent nights dilutes the regime with normal nights and is strictly dominated). Standardised by the same $\hat\sigma_s(t)$ the band uses, the realised overnight move on earnings nights has $p_{99} \approx 9.7$ versus $\approx 2.0$ on other nights; the fitted per-regime quantile $q_{\texttt{earnings\_night}}(\tau)$ runs ≈ $8\times$ $q_{\texttt{normal}}(\tau)$, and §6.8 shows the resulting band is calibrated, not merely wide.

**σ̂ de-contamination.** Because an earnings residual can be $\sim 8\sigma$, admitting it to the per-symbol EWMA scale $\hat\sigma_s(t)$ over-widens the subsequent ~`half_life` *normal* nights and induces clustered post-earnings violations. We therefore exclude earnings-night residuals from the $\hat\sigma_s$ estimation pool — every night still receives a $\hat\sigma_s$ built from its non-earnings history — assigning the earnings excess to the `earnings_night` quantile rather than the scale. Earnings fatness is a regime effect, not a per-symbol scale effect. This separation lifts the overnight Christoffersen independence $p$ at $\tau = 0.95$ from a rejecting $0.013$ to a passing $0.165$ and collapses the OOS $c(\tau)$ bumps to ≈1.0 (§6.8). Figure \ref{fig:earnings-event-study} shows both mechanisms in event time.

![Calendar-conditioned widening in event time: all 228 earnings nights on the overnight panel aligned at $t = 0$, each event's served $\tau = 0.95$ half-width (deployed artefact schedules) at night offsets $t-5 \ldots t+5$ normalised by that event's own pre-event baseline (median width over $t-5 \ldots t-2$). The band widens $7.1\times$ (median; IQR shaded) exactly at the release gap — deterministically, because the release date and session are public — and the median realised $|$close$\to$open$|$ move at $t = 0$ is $1.78\times$ the *entire baseline band width* (vermilion), so an unwidened band would routinely breach. The flat shoulder at $t \ge +1$ ($0.95\times$ baseline, indistinguishable from the pre-event level) is the σ̂ de-contamination at work: without the exclusion, the $\sim 8\sigma$ earnings residual would inflate $\hat\sigma_s$ — and hence width — for roughly a half-life of subsequent normal nights.\label{fig:earnings-event-study}](figures/fig11_earnings_event_study.pdf)

## 4.4 OOS-fit $c(\tau)$ bump

The deployed bump schedule is

$$c(\tau) \;=\; \{0.68\!:\!1.000,\;0.85\!:\!1.000,\;0.95\!:\!1.079,\;0.99\!:\!1.003\},$$

a near-identity correction that *only* widens at $\tau = 0.95$ (by 7.9%) and is essentially the identity at the other three anchors. The fit procedure: $c(\tau)$ is the smallest $c \in [1, 5]$ such that pooled OOS realised coverage with effective quantile $c \cdot q_r(\tau)$ matches the target $\tau$. Four scalars total. Three of the four are essentially identity, so only $c(0.95) = 1.079$ carries meaningful OOS information; §9.3 carries the full provenance disclosure for that one scalar.

## 4.5 The walk-forward $\delta(\tau)$ schedule is identically zero

A 4-split expanding-window walk-forward sweep over $\delta \in \{0.00, \ldots, 0.07\}$ at tune fractions $f \in \{0.40, 0.50, 0.60, 0.70\}$ (script: `scripts/run_lwc_delta_sweep.py`) selects $\delta(\tau) \equiv 0$ under the criterion *smallest $\delta$ such that walk-forward realised coverage $\geq \tau$ on every powered split* — per-symbol σ̂ standardisation tightens cross-split realised-coverage variance enough that no structural-conservatism shift is required (§7.2.3 ablation). The vector is retained in the artefact JSON for receipt-schema compatibility.

## 4.6 Serving-time band construction

Given a consumer-chosen target $\tau \in (0, 1)$ at $(s, t)$, the served band is constructed in five steps:

1. *Look up the regime, point, per-symbol scale, and Friday close.* Read $r = \rho(\mathcal{F}_t)$, $\hat P_{\text{Mon},t}(s)$, $\hat\sigma_s(t)$, and $P_{\text{Fri},t}(s)$ from `lwc_artefact_v1.parquet`.
2. *Look up the standardised quantile.* $q_r = q_r(\tau)$, with $q_r$ linearly interpolated between anchors $\mathcal{T}_\text{anch} = \{0.68, 0.85, 0.95, 0.99\}$ and clipped to the nearest anchor outside that range.
3. *Apply the OOS bump.* $q_\text{eff} = c(\tau) \cdot q_r(\tau)$, with $c$ linearly interpolated between the same four anchors; $\delta(\tau) \equiv 0$ so no shift step is needed. The $c(\tau)$ schedule is non-monotonic — $c$ peaks at the $\tau = 0.95$ anchor (1.079) and dips back at $\tau = 0.99$ (1.003) — so linear interpolation hands an off-anchor consumer a multiplier (e.g. $c(0.90) \approx 1.040$ and $c(0.97) \approx 1.041$) at a point with no separate audited calibration evidence. Calibration evidence in §6 is reported at the four audited anchors only; §9.10 carries the off-anchor disclosure (denser-anchor-grid follow-up tracked in `docs/ROADMAP.md`).
4. *Construct the band.* The conformity score the per-regime quantile was fit on is the *standardised* relative residual $|P_{\text{Mon}} - \hat P| / (P_{\text{Fri}} \cdot \hat\sigma_s)$ (§4.3), so the band is fri-close-relative with the per-symbol scale entering multiplicatively: $\text{half}_t = q_\text{eff} \cdot \hat\sigma_s(t) \cdot P_{\text{Fri},t},\ \text{lower} = \hat P_{\text{Mon},t} - \text{half}_t,\ \text{upper} = \hat P_{\text{Mon},t} + \text{half}_t$. The half-width in basis points is $10^4 \cdot c(\tau) \cdot q_r(\tau) \cdot \hat\sigma_s(t)$ — heavy-tail tickers receive wider bands than low-vol tickers at identical $\tau$ and identical regime.
5. *Emit the receipt.* The served band's claimed coverage is $\tau$; the receipt's `forecaster_used` carries the architecture's wire-format tag (the on-chain code-tag taxonomy is documented once in §8). Diagnostics expose $c(\tau)$, $q_r(\tau)$, $q_\text{eff}$, $\hat\sigma_s(t)$, $r$, and Friday close.

The serving-time computation is a five-line lookup against the per-Friday artefact + the two constant schedules. There is no surface inversion, no bracketing in claimed-coverage space, and no per-symbol fallback — the per-symbol behaviour is carried *implicitly* by the per-symbol $\hat\sigma_s(t)$ scale on the artefact parquet, not by a per-symbol quantile cell.

## 4.7 The PricePoint receipt and reproducibility

Every read returns a `PricePoint` exposing the band plus eight receipt fields: `target_coverage` ($\tau$), `claimed_coverage_served` ($\tau$ — equal to the request since $\delta \equiv 0$), `forecaster_used`, `regime` ($r$), `sharpness_bps`, and `diagnostics.{c_bump, q_regime_lwc, sigma_hat_sym_pre_fri, q_eff}`. A third party with the audit-trail sidecar and the per-Friday artefact can reconstruct the served band from the receipt alone: read $\hat P$, $r$, $\hat\sigma_s$, and $P_{\text{Fri}}$ from the artefact, read $q_\text{eff}$ from the receipt, verify $\text{lower} = \hat P - q_\text{eff} \cdot \hat\sigma_s \cdot P_{\text{Fri}}$ and $\text{upper} = \hat P + q_\text{eff} \cdot \hat\sigma_s \cdot P_{\text{Fri}}$ to floating-point precision. This is the operational instantiation of $P_1$.

Implementation: Python (`src/soothsayer/oracle.py:Oracle.fair_value_lwc`) is the canonical reference; the Rust port (`crates/soothsayer-oracle`) carries byte-exact parity (180/180 cases; §8.5). The on-chain wire-format details and the Rust serving-stack rollout state live in §8. Reproduction:

```
uv run python scripts/build_lwc_artefact.py        # per-Friday artefact + JSON sidecar
uv run python scripts/freeze_lwc_artefact.py       # content-addressed freeze for forward-tape eval
uv run python scripts/smoke_oracle.py --forecaster lwc   # cross-regime API demo
```

All inputs are public and free (§5.7); verifying a published band needs only the sidecar and the per-Friday artefact — under 100 KB per symbol-year. The σ̂ window is recomputable from the same parquet given only the half-life constant, so the artefact is self-contained.
