# §4 — Methodology (M5 / Mondrian deployment)

This section instantiates the abstract setup of §3 with the concrete point estimator, conformal quantile fit, deployment-tuned schedules, and serving-time machinery of the deployed M5 architecture. The implementation lives in `src/soothsayer/oracle.py` (Python) and `crates/soothsayer-oracle/src/{config,oracle,types}.rs` (Rust); the two are byte-for-byte verified by `scripts/verify_rust_oracle.py` (90/90 cases match).

The architecture has four ingredients: a point estimator $\hat P_{\text{Mon},r}$, a per-regime conformal quantile $q_r(\tau)$ trained on a held-out calibration set, an OOS-fit multiplicative bump $c(\tau)$ that closes the train-OOS distribution-shift gap, and a walk-forward-fit shift $\delta(\tau)$ that pushes per-split realised coverage above nominal. Twenty deployment scalars total (12 trained + 4 + 4); the §7 ablation shows this is the *deployable* simpler baseline that survives the §7.1 constant-buffer stress test plus the §7.2 head-to-head against the v1 surface-plus-buffer Oracle.

## 4.1 The point estimator $\hat P_{\text{Mon},r}$

The deployed point estimator is the per-symbol factor switchboard (§5.4):

$$\hat P_{\text{Mon},t}(s) \;=\; P_{\text{Fri},t}(s) \cdot \bigl(1 + r^{\text{factor}}_t(s)\bigr),$$

where $r^{\text{factor}}_t(s)$ is the weekend return of the per-symbol factor (ES=F for equities; GC=F for GLD; ZN=F for TLT; BTC for MSTR post-2020-08). The point estimator is the input whose residual distribution the conformal quantile is fit on, not the product. Eight point-estimator variants were considered in early development (the v1 hybrid forecaster ladder); the factor-switchboard variant survived empirical pruning. §7.2 shows the additional v1 machinery is cosmetic on top of the regime classifier.

## 4.2 Mondrian split-conformal by regime

Conformity score: relative absolute residual

$$s_t(s) \;=\; \frac{\bigl|P_{\text{Mon},t}(s) - \hat P_{\text{Mon},t}(s)\bigr|}{P_{\text{Fri},t}(s)}.$$

Mondrian taxonomy: weekends partition into $r \in \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ via the regime classifier $\rho(\mathcal{F}_t)$ specified in §5.5. The trained per-regime conformal quantile $q_r(\tau)$ is the standard split-CP $(1-\alpha)(n+1)$-th rank quantile on the regime's training-set residuals. The deployed grid has four anchors $\tau \in \mathcal{T}_\text{anch} = \{0.68, 0.85, 0.95, 0.99\}$ and three regimes, yielding twelve trained scalars.

Calibration set: $\mathcal{T}_\text{train} = \{t : t < \text{2023-01-01}\}$ — 4,266 weekend rows across 466 weekends, decomposing by regime to 2,774 (normal), 440 (long_weekend), 1,052 (high_vol). Each per-(regime, $\tau$) bin therefore carries $N \approx 440$–$2{,}774$ observations supporting one quantile estimate, comfortably above the $N \approx 50$–$300$ thresholds where Mondrian conformal becomes noisy (the per-(symbol, regime) Mondrian rung M3, §7.2.2, fails Christoffersen for exactly this sample-size reason).

Deployed values of $q_r(\tau)$ are listed in `data/processed/mondrian_artefact_v2.json` (audit-trail sidecar) and hardcoded in `src/soothsayer/oracle.py:REGIME_QUANTILE_TABLE` and `crates/soothsayer-oracle/src/config.rs:REGIME_QUANTILE_TABLE`.

## 4.3 OOS-fit $c(\tau)$ bump and walk-forward $\delta(\tau)$ shift

A naive deployment of the trained $q_r(\tau)$ on the 2023+ OOS slice undercovers by 6–14pp at every $\tau \le 0.95$ (M2 row of §7.2.2), the same distribution-shift mechanism §7.1 identifies for a global constant-buffer baseline. The fix is two deployment-tuned schedules.

**Multiplicative bump $c(\tau)$.** For each anchor, $c(\tau)$ is the smallest $c \in [1, 5]$ such that pooled OOS realised coverage with effective quantile $c \cdot q_r(\tau)$ matches the consumer's request. Four scalars total, matching v1's `BUFFER_BY_TARGET` parameter budget exactly. Deployed values: $c(0.68) = 1.498,\ c(0.85) = 1.455,\ c(0.95) = 1.300,\ c(0.99) = 1.076$. Off-anchor $\tau$ are linearly interpolated and clamped at the schedule endpoints.

**Walk-forward shift $\delta(\tau)$.** A plain $c(\tau)$ fit to the pooled OOS slice produces per-split realised coverage that scatters around nominal — passes Kupiec on the pooled fit by construction, but undercovers in roughly half the splits and overcovers in the other half. The deployed schedule serves $c(\tau + \delta(\tau)) \cdot q_r(\tau + \delta(\tau))$, where the $\delta$ schedule is selected from the sweep $\delta \in \{0.00, 0.01, \dots, 0.07\}$ as the smallest schedule aligning walk-forward realised coverage with nominal at every anchor (§7.2.4). Deployed values: $\delta(0.68) = 0.05,\ \delta(0.85) = 0.02,\ \delta(0.95) = 0.00,\ \delta(0.99) = 0.00$. Both schedules are 4-scalar; both push the deployed band to the safe side of nominal coverage.

The $c(\tau)$ and $\delta(\tau)$ schedules are deployment-tuned on the same 2023+ slice that §6 evaluates the served band on. The §6.4 walk-forward block is the empirical mitigation; §9.3 carries the wider disclosure of OOS-tuning provenance.

## 4.4 Serving-time band construction

Given a consumer-chosen target $\tau \in (0, 1)$ at $(s, t)$, the served band is constructed in five steps:

1. *Look up the regime and point.* Read $r = \rho(\mathcal{F}_t)$ and $\hat P_{\text{Mon},t}(s)$ from `mondrian_artefact_v2.parquet`.
2. *Apply the $\delta$-shift.* $\tau' = \min\bigl(\tau + \delta(\tau),\ 0.99\bigr)$.
3. *Look up the effective quantile.* $q_\text{eff} = c(\tau') \cdot q_r(\tau')$, with $c$ and $q_r$ linearly interpolated off-anchor.
4. *Construct the band.* $\text{lower} = \hat P_{\text{Mon},t} (1 - q_\text{eff}),\ \text{upper} = \hat P_{\text{Mon},t} (1 + q_\text{eff})$.
5. *Emit the receipt.* The served band's claimed coverage is $\tau'$; the consumer's request is $\tau$; the receipt's `forecaster_used` is the literal string `mondrian` (on-chain `forecaster_code` = 2). Diagnostics expose $c(\tau')$, $q_r(\tau')$, $q_\text{eff}$, and Friday close.

The serving-time computation is a five-line lookup against the per-Friday artefact + the three constant schedules. There is no surface inversion, no bracketing in claimed-coverage space, no per-symbol fallback — the v1 architecture's complexity is collapsed into the per-regime conformal table.

## 4.5 The PricePoint receipt and reproducibility

Every read returns a `PricePoint` exposing the band plus eight receipt fields: `target_coverage` ($\tau$), `calibration_buffer_applied` ($\delta(\tau)$), `claimed_coverage_served` ($\tau'$), `forecaster_used` (`mondrian`), `regime` ($r$), `sharpness_bps`, and `diagnostics.{c_bump, q_regime, q_eff}`. A third party with the audit-trail sidecar and the per-Friday artefact can reconstruct the served band from the receipt alone — read $\hat P$, $r$ from the artefact, read $\tau'$ and $q_\text{eff}$ from the receipt, verify $\text{lower} = \hat P (1 - q_\text{eff})$ and $\text{upper} = \hat P (1 + q_\text{eff})$ to floating-point precision. This is the operational instantiation of P1.

Implementation: Python (`src/soothsayer/oracle.py`) is the canonical reference; Rust (`crates/soothsayer-oracle/src/{config,oracle}.rs`) is the production binary. `scripts/verify_rust_oracle.py` asserts byte-for-byte equality across 90 cases (randomised + edge); the latest run passes 90/90. Reproduction:

```
uv run python scripts/build_mondrian_artefact.py   # per-Friday artefact + JSON sidecar
uv run python scripts/smoke_oracle.py              # cross-regime API demo
```

All inputs are public and free (§5.7); verifying a published band needs only the sidecar and the per-Friday artefact — under 100 KB per symbol-year.
