# §4 — Methodology (M5 / Mondrian deployment)

This section instantiates the abstract setup of §3 with the concrete point estimator, conformal quantile fit, deployment-tuned schedules, and serving-time machinery of the M5 / Mondrian split-conformal-by-regime deployment. The deployed implementation lives in `src/soothsayer/oracle.py` (Python) and `crates/soothsayer-oracle/src/{config,oracle,types}.rs` (Rust); the two are byte-for-byte verified by `scripts/verify_rust_oracle.py` (90/90 cases match) and we cite line-anchors in this section to make the artifact-paper correspondence explicit.

The architecture has four ingredients: a point estimator $\hat P_{\text{Mon},r}$ for next Monday's open, a per-regime conformal quantile $q_r(\tau)$ trained on a held-out calibration set, an OOS-fit multiplicative bump $c(\tau)$ that closes the train-OOS distribution-shift gap, and a walk-forward-fit shift $\delta(\tau)$ that pushes per-split realised coverage above nominal so the deployed schedule is conservative. Twenty deployment scalars total (12 trained + 4 + 4); the §7 ablation shows the architecture is the *deployable* simpler baseline that survives the §7.6 constant-buffer stress test plus the §7.7 head-to-head against the v1 surface-plus-buffer Oracle.

## 4.1 The point estimator $\hat P_{\text{Mon},r}$

The deployed point estimator is the §7.4 factor switchboard:

$$\hat P_{\text{Mon},t}(s) \;=\; P_{\text{Fri},t}(s) \cdot \bigl(1 + r^{\text{factor}}_t(s)\bigr),$$

where $r^{\text{factor}}_t(s)$ is the weekend return of the per-symbol conditioning factor (E-mini S&P futures `ES=F` for the seven equities; gold futures `GC=F` for `GLD`; 10-year treasury futures `ZN=F` for `TLT`; BTC for `MSTR` post-2020-08; full registry in §5.4). The point estimator is *not* the product — protocols integrate against the band, not the point — but it is the input whose residual distribution the conformal quantile is fit on.

We considered eight point-estimator variants in early development (§7.1–§7.5; the v1 hybrid forecaster ladder). The factor-switchboard variant survived empirical pruning as the cleanest input for the residual-quantile fit; richer variants (the v1 log-log VIX / earnings-flag / long-weekend-flag layers) widened the residual quantile by absorbing structure into $\hat P$ rather than into the per-regime quantile. §7.7 shows the cleanly-pruned point estimator is what M5 deploys; the additional v1 machinery is over-engineering relative to the regime classifier.

## 4.2 Mondrian split-conformal by regime

Conformity score: relative absolute residual

$$s_t(s) \;=\; \frac{\bigl|P_{\text{Mon},t}(s) - \hat P_{\text{Mon},t}(s)\bigr|}{P_{\text{Fri},t}(s)}.$$

Mondrian taxonomy: weekends partition into three regimes $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ via the regime classifier $\rho(\mathcal{F}_t)$ specified in §5.5. The trained per-regime conformal quantile is

$$q_r(\tau) \;=\; \mathrm{Q}^+\!\bigl(\{s_\tau\}_{\tau \in \mathcal{T}_\text{train},\,\rho(\mathcal{F}_\tau) = r},\ \tau\bigr),$$

the standard split-CP finite-sample $(1-\alpha)(n+1)$-th rank quantile (where $\alpha = 1 - \tau$, $n$ is the regime's training-set size, $\mathrm{Q}^+$ is the higher-rank empirical quantile). The deployed grid has four anchors $\tau \in \mathcal{T}_\text{anch} = \{0.68, 0.85, 0.95, 0.99\}$ and three regimes, yielding twelve trained scalars.

Calibration set: $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ — 4,266 weekend rows across 466 weekends, which decomposes by regime to 2,774 rows (normal), 440 (long_weekend), 1,052 (high_vol). The per-(regime, $\tau$) bin therefore carries $N \approx 440$–$2{,}774$ observations supporting one quantile estimate, comfortably above the $N \approx 50$–$300$ thresholds where Mondrian conformal becomes noisy (the per-(symbol, regime) Mondrian rung M3, §7.7.2, fails Christoffersen for exactly this sample-size reason).

The deployed values of $q_r(\tau)$ are listed in `data/processed/mondrian_artefact_v2.json` (the audit-trail sidecar) and hardcoded in `src/soothsayer/oracle.py:REGIME_QUANTILE_TABLE` and `crates/soothsayer-oracle/src/config.rs:REGIME_QUANTILE_TABLE`, for byte-for-byte traceability between paper, audit artefact, and serving code.

## 4.3 OOS-fit $c(\tau)$ bump and walk-forward $\delta(\tau)$ shift

A naive deployment of the trained $q_r(\tau)$ on the 2023+ OOS slice undercovers by 6–14pp at every $\tau \le 0.95$ (M2 row of §7.7.2), the same distribution-shift mechanism §7.6 identified for a global constant-buffer baseline. The fix is two deployment-tuned schedules:

**Multiplicative bump $c(\tau)$.** For each anchor $\tau \in \mathcal{T}_\text{anch}$, $c(\tau)$ is the smallest $c \in [1, 5]$ such that pooled OOS realised coverage with effective quantile $c \cdot q_r(\tau)$ matches the consumer's request:

$$c(\tau) \;=\; \arg\min \bigl\{ c \ge 1 \;:\; \mathbb{E}_{\text{OOS}}\!\left[\mathbf{1}\bigl(s_t \le c \cdot q_{\rho(\mathcal{F}_t)}(\tau)\bigr)\right] \ge \tau \bigr\}.$$

Four scalars total, matching the v1 Oracle's `BUFFER_BY_TARGET` parameter budget exactly. Deployed values: $c(0.68) = 1.498,\ c(0.85) = 1.455,\ c(0.95) = 1.300,\ c(0.99) = 1.076$. Off-anchor $\tau$ are linearly interpolated between adjacent anchors and clamped at the schedule endpoints. The bump is the M5 structural successor to v1's per-target additive buffer.

**Walk-forward shift $\delta(\tau)$.** A plain $c(\tau)$ fit to the pooled OOS slice produces per-split realised coverage that scatters around nominal — passes Kupiec on the pooled fit by construction, but undercovers in roughly half the splits and overcovers in the other half. The deployed schedule pushes serving to the conservative side via a $\tau$-shift: instead of serving $c(\tau) \cdot q_r(\tau)$, the deployed Oracle serves $c(\tau + \delta(\tau)) \cdot q_r(\tau + \delta(\tau))$, where the $\delta(\tau)$ schedule is selected from the sweep $\delta \in \{0.00, 0.01, \dots, 0.07\}$ as the smallest schedule aligning walk-forward realised coverage with nominal at every anchor (§7.7.4). Deployed values: $\delta(0.68) = 0.05,\ \delta(0.85) = 0.02,\ \delta(0.95) = 0.00,\ \delta(0.99) = 0.00$. The shift is the M5 analogue of v1's deployment-tuned BUFFER_BY_TARGET conservative overshoot — both are 4-scalar OOS-fit schedules; both push the deployed band to the safe side of nominal coverage.

The $c(\tau)$ and $\delta(\tau)$ schedules are deployment-tuned on the same 2023+ slice that §6 evaluates the served band on. The §6.4 walk-forward block is the empirical mitigation (six-split walk-forward of the conformal fit + bump fit + shift selection passes Kupiec at every anchor). §9.4 carries the wider disclosure of the OOS-tuning provenance.

## 4.4 Serving-time band construction

Given a consumer-chosen target $\tau \in (0, 1)$ at $(s, t)$, the served band is constructed in five steps:

1. *Look up the regime and point.* Read $r = \rho(\mathcal{F}_t)$ and $\hat P_{\text{Mon},t}(s)$ from the per-Friday artefact `data/processed/mondrian_artefact_v2.parquet`. The regime is computed offline at artefact-build time; $\hat P_{\text{Mon},t}$ is the precomputed factor-switchboard point.

2. *Apply the $\delta$-shift.* $\tau' = \min\bigl(\tau + \delta(\tau),\ 0.99\bigr)$, where $\delta(\tau)$ is the schedule of §4.3 with linear interpolation off-anchor.

3. *Look up the effective quantile.* $q_\text{eff} = c(\tau') \cdot q_r(\tau')$, with $c$ and $q_r$ also linearly interpolated off-anchor.

4. *Construct the band.* $\text{lower} = \hat P_{\text{Mon},t} \cdot (1 - q_\text{eff}),\ \text{upper} = \hat P_{\text{Mon},t} \cdot (1 + q_\text{eff})$, and $\text{point} = \hat P_{\text{Mon},t}$.

5. *Emit the receipt.* The served band's claimed coverage is $\tau'$; the consumer's request is $\tau$; the OOS-fit shift is $\delta(\tau)$; the regime is $r$; the receipt's `forecaster_used` is the literal string `mondrian` (on-chain `forecaster_code` = 2, in `crates/soothsayer-consumer/src/lib.rs:FORECASTER_MONDRIAN`). The diagnostics expose $c(\tau')$, $q_r(\tau')$, $q_\text{eff}$, and Friday close.

The serving-time computation is therefore a five-line lookup against the per-Friday artefact + the three constant schedules. There is no surface inversion, no bracketing interpolation in claimed-coverage space, no per-symbol fallback, and no scalar buffer override — the v1 architecture's complexity is collapsed into the per-regime conformal table.

## 4.5 The PricePoint receipt

Every oracle read returns a `PricePoint` exposing the band plus eight receipt fields:

| Field | Source | Used by |
|---|---|---|
| `target_coverage` | request $\tau$ | echoed for audit |
| `calibration_buffer_applied` | $\delta(\tau)$ from §4.3 | reproducing $\tau'$ |
| `claimed_coverage_served` | $\tau'$ from §4.4 step 2 | the served band's claim |
| `forecaster_used` | constant `mondrian` | wire `forecaster_code = 2` |
| `regime` | $r = \rho(\mathcal{F}_t)$ from §5.5 | identifies the conformal-table row |
| `sharpness_bps` | $(U - L)/(2 \cdot P_\text{Fri})$ in bp | consumer's instantaneous capital-efficiency cost |
| `diagnostics.served_target` | $\tau'$ | identifies the conformal-table column |
| `diagnostics.{c_bump,q_regime,q_eff}` | $c(\tau'),\ q_r(\tau'),\ q_\text{eff}$ | reproducing the band edges |

A third party with the audit-trail sidecar (`data/processed/mondrian_artefact_v2.json`) and the per-Friday artefact can reconstruct the served band from the receipt alone: read $\hat P$, $r$ from the artefact at $(s, t)$; read $\tau'$ and $q_\text{eff}$ from the receipt; verify $\text{lower} = \hat P (1 - q_\text{eff})$ and $\text{upper} = \hat P (1 + q_\text{eff})$ to floating-point precision. This is the operational instantiation of property P1 (auditability) of §3.4.

## 4.6 Implementation and reproducibility

The deployed Oracle is implemented in two languages with byte-for-byte parity:

- *Python.* `src/soothsayer/oracle.py` — `Oracle.fair_value(symbol, as_of, target_coverage)`. The 20 deployment scalars are exposed as module-level constants (`REGIME_QUANTILE_TABLE`, `C_BUMP_SCHEDULE`, `DELTA_SHIFT_SCHEDULE`).

- *Rust.* `crates/soothsayer-oracle/src/{config,oracle}.rs` — same API, same constants, same arithmetic. The Rust port is the production serving binary; the Python is the research and reference implementation. `scripts/verify_rust_oracle.py` runs both implementations on a randomised + edge-case panel and asserts byte-for-byte equality on every field of the returned `PricePoint`. The latest run (2026-MM-DD, M5 deployment) passes 90/90 cases.

End-to-end reproduction is a two-command sequence:

```
uv run python scripts/build_mondrian_artefact.py   # builds the per-Friday artefact + JSON sidecar
uv run python scripts/smoke_oracle.py              # cross-regime demo of the served API
```

The artefact build re-trains the 12 per-regime quantiles and re-fits the 4 $c(\tau)$ bumps from the 2023+ OOS slice; the $\delta$ schedule is hardcoded as the walk-forward selection. All inputs are public and free (§5.7); no credentials are required for the calibration backtest itself. A consumer who wants to verify a published band needs only the audit-trail sidecar and the per-Friday artefact for the date in question — under 100 KB of structured data per symbol-year.
