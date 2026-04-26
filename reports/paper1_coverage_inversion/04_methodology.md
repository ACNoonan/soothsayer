# §4 — Methodology (draft)

This section instantiates the abstract setup of §3 with the concrete forecasters, surface, inversion procedure, and serving-time machinery used in our evaluation. The deployed implementation lives in `src/soothsayer/oracle.py` (Python) and `crates/soothsayer-oracle/src/{config,oracle}.rs` (Rust); the two are byte-for-byte verified by `scripts/verify_rust_oracle.py` (75/75 cases match) and we cite line-anchors in this section to make the artifact-paper correspondence explicit.

## 4.1 The forecaster pair $\mathcal{F}$

Our evaluation uses two base forecasters $\mathcal{F} = \{\texttt{F0\_stale},\ \texttt{F1\_emp\_regime}\}$. Both emit, for every $(s, t, q)$ with $q$ on the claimed-coverage grid $\mathcal{Q}$ defined in §4.2, a band $[L^f_t(s; q),\ U^f_t(s; q)]$.

**$\texttt{F0\_stale}$** — the stale-hold Gaussian baseline. Point estimate $\hat P^{\text{F0}}_t = P_{t^-}(s)$ (Friday close held forward). Conditional sigma $\sigma^{\text{F0}}_t = \hat\sigma^{\text{20d}}_t \cdot \sqrt{\ell_t} \cdot P_{t^-}(s)$ where $\hat\sigma^{\text{20d}}_t$ is the rolling 20-trading-day daily-return standard deviation at Friday close and $\sqrt{\ell_t}$ is a calendar-gap scaling ($\sqrt{1}$ for a standard Friday→Monday weekend, $\sqrt{2}$ for a 4-day weekend, $\sqrt{3}$ for 5-day, etc.). Bands are constructed parametrically: $L^{\text{F0}}_t(s; q) = \hat P^{\text{F0}}_t - z_q \cdot \sigma^{\text{F0}}_t$ and analogously for $U$, where $z_q = \Phi^{-1}\!\bigl(\tfrac{1+q}{2}\bigr)$. F0 is the methodological analog of a Chainlink-style stale `price` feed wrapped with a vol-scaled Gaussian — the "what does the simplest principled baseline look like" comparator.

**$\texttt{F1\_emp\_regime}$** — the factor-switchboard / log-log volatility-regime / empirical-quantile forecaster. Three components:

1. *Point estimate.* $\hat P^{\text{F1}}_t = P_{t^-}(s) \cdot (1 + r^{\text{factor}}_t(s))$ where $r^{\text{factor}}_t(s)$ is the weekend return of the per-symbol conditioning factor (E-mini S&P futures `ES=F` for the seven equities, gold futures `GC=F` for `GLD`, 10-year treasury futures `ZN=F` for `TLT`, BTC for `MSTR` post-2020-08). Section 5.4 specifies `FACTOR_BY_SYMBOL` in full.

2. *Conditional sigma.* For each $(s, t)$ we fit a per-symbol log-log regression on the prior 156-weekend window:
$$\log|\varepsilon_\tau| \;=\; \alpha + \beta \log v_\tau(s) + \gamma_\text{earn} \cdot \mathrm{earn}_\tau(s) + \gamma_\text{long} \cdot \ell_\tau \;+\; \xi_\tau,\quad \tau \in [t-156,\ t-1],$$
where $\varepsilon_\tau = \log\bigl(P_\tau(s) / \hat P^{\text{F1}}_\tau\bigr)$ is the return-residual of F1's point estimate and $v_\tau(s)$ is the per-symbol implied-volatility index (VIX for equities, GVZ for `GLD`, MOVE for `TLT` — see §5.4). Regressors with zero in-window variance are silently dropped from that fit (avoids singular matrices when a ticker has no in-window earnings observations). The implied conditional sigma at $t$ is $\sigma^{\text{F1}}_t = \exp(\hat\alpha + \hat\beta \log v_t(s) + \hat\gamma_\text{earn} \cdot \mathrm{earn}_t(s) + \hat\gamma_\text{long} \cdot \ell_t)$.

3. *Empirical-quantile bands.* In-window residuals are standardised by the regression-implied sigma, $z_\tau = \varepsilon_\tau / \sigma_\tau^{\text{F1, hist}}$. Bands at claimed quantile $q$ are $L^{\text{F1}}_t(s; q) = \hat P^{\text{F1}}_t \cdot \exp\!\bigl(z_{(1-q)/2} \cdot \sigma^{\text{F1}}_t\bigr)$ and analogously for $U$ at $z_{(1+q)/2}$, where $z_{(\cdot)}$ are empirical quantiles of the in-window standardised residuals. There is no Gaussian assumption on the residuals; non-zero median residuals propagate into the band without distortion (see §6.6 for the bias-absorption derivation). The earnings and long-weekend regressors enter as level shifts in $\log\sigma$ — they widen or tighten the conditional sigma deterministically without altering the residual distribution itself.

The pair $\mathcal{F}$ is deliberately small. We considered eight forecaster variants in early development (§7 reports the ablation matrix); the final pair survived empirical pruning. F0 is retained not as a deployed default but as the high-volatility fallback in the hybrid serving policy of §4.4.

## 4.2 Calibration surface and claimed-quantile grid

The claimed-coverage grid is $\mathcal{Q} = \{0.50, 0.60, 0.68, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95, 0.975, 0.99, 0.995, 0.997, 0.999\}$ — fourteen points concentrated near the high-coverage end where consumers operate. The grid's upper tail was extended from a $0.995$ cap to $\{0.997, 0.999\}$ in our 2026-04-25 revision after the buffer-tuning sweep showed serving at $\tau \ge 0.99$ benefited from finer grid resolution at the tail (see `reports/v1b_extended_grid.md`).

For each base forecaster $f \in \mathcal{F}$ we materialise the bounds at every $(s, t, q) \in \mathcal{S} \times \mathcal{T}_\mathrm{hist} \times \mathcal{Q}$ into a long-form table persisted at `data/processed/v1b_bounds.parquet`. The empirical calibration surface
$$S^f(s, r, q) \;=\; \frac{1}{|\mathcal{T}_{s,r}|} \sum_{\tau \in \mathcal{T}_{s,r}} \mathbf{1}\!\bigl[\,L^f_\tau(s; q) \le P_\tau(s) \le U^f_\tau(s; q)\,\bigr]$$
is computed from this table, with $\mathcal{T}_{s,r} = \{\tau \in \mathcal{T}_\mathrm{hist} : \text{symbol}(\tau) = s,\ \rho(\mathcal{F}_\tau(s)) = r\}$.

A pooled fallback surface $\bar S^f(\cdot, r, q)$, computed with the symbol axis collapsed, is materialised alongside. At serve time, the per-symbol surface is consulted first; the pooled surface is used when $|\mathcal{T}_{s,r}| < n_\text{min}$ for the active rolling window. The pooled-fallback path is exposed in the receipt as a `calibration` field with values `per_symbol` or `pooled`, so a consumer can identify which surface produced their served band.

## 4.3 Inversion, per-target buffer, and the served quantile

Given a consumer-chosen target $\tau \in (0, 1)$, the served claimed quantile is determined in three steps:

1. *Per-target buffer.* The consumer's $\tau$ is shifted by an empirical buffer:
$$\tilde\tau \;=\; \min\!\bigl(\tau + b(\tau),\ \tau_\text{max}\bigr),\quad \tau_\text{max} = 0.999,$$
where $b(\tau)$ is the value of the deployed buffer schedule:
$$b \in \{(0.68 \mapsto 0.045),\ (0.85 \mapsto 0.045),\ (0.95 \mapsto 0.020),\ (0.99 \mapsto 0.010)\}$$
with linear interpolation between anchors and flat extrapolation outside $[0.68, 0.99]$. The buffer is exposed in the receipt as `calibration_buffer_applied`. The four-anchor schedule was tuned on the OOS 2023+ slice as the smallest buffer per anchor satisfying realised-within-0.5pp of target plus Kupiec $p_{uc} > 0.10$ plus Christoffersen $p_{ind} > 0.05$ — see `reports/v1b_buffer_tune.md` for the sweep.

2. *Surface inversion.* The buffered target is mapped to a claimed quantile by inverting $S^f(s, r, \cdot)$. Off-grid targets are resolved by linear interpolation between the bracketing claimed-grid points. The bracketing pair is exposed in the diagnostic as `bracketed`.

3. *Bound lookup.* The served band is read from the bounds table at $q_\text{served}$. The two natural alternatives — interpolating the bounds rather than the surface, or rounding $q_\text{served}$ to the nearest grid point and serving that band — were tested in early development; the surface-interpolation, bound-lookup approach was chosen because it preserves the deterministic correspondence between $q_\text{served}$ (which is in the receipt) and the actual band edges (which the consumer can verify against the persisted bounds parquet).

## 4.4 Hybrid regime-to-forecaster policy

The serving layer consults a per-regime forecaster map:
$$\texttt{REGIME\_FORECASTER} \;=\; \{\texttt{normal} \to \texttt{F1\_emp\_regime},\ \texttt{long\_weekend} \to \texttt{F1\_emp\_regime},\ \texttt{high\_vol} \to \texttt{F0\_stale}\}.$$

The choice of $f^\star(r)$ for each $r$ is justified empirically in §7 (in-sample bandwidth at matched coverage) and §6.4 (out-of-sample Christoffersen independence). The policy is static — it is fixed pre-deployment and exposed as a constant in `oracle.py:REGIME_FORECASTER` rather than being re-derived from data at serve time. A consumer reading the `regime` and `forecaster_used` fields of the `PricePoint` can verify the policy was applied as documented.

## 4.5 The PricePoint receipt

Every oracle read returns a `PricePoint` exposing nine fields beyond the band itself:

| Field | Source | Used by |
|---|---|---|
| `target_coverage` | request | echoed for audit |
| `calibration_buffer_applied` | $b(\tau)$ from §4.3 | reproducing the buffered $\tilde\tau$ |
| `claimed_coverage_served` | $q_\text{served}$ from §4.3 | identifies the band's claimed quantile |
| `forecaster_used` | $f^\star(r)$ from §4.4 | identifies which $S^f$ was inverted |
| `regime` | $r = \rho(\mathcal{F}_t)$ from §5.5 | identifies the surface bucket |
| `sharpness_bps` | $(U - L)/(2 \cdot P_{t^-})$ in bp | consumer's instantaneous capital-efficiency cost |
| `diagnostics.calibration` | `per_symbol` or `pooled` | identifies whether the fallback was used |
| `diagnostics.bracketed` | bracketing $\mathcal{Q}$ pair | verifies the inversion interpolation |
| `diagnostics.regime_forecaster_policy` | full $\texttt{REGIME\_FORECASTER}$ | snapshot of the deployed policy |

Together these fields fully specify how a given $(s, t, \tau)$ request was resolved: a third party with the surface CSV (`reports/tables/v1b_calibration_surface.csv`) and the bounds parquet can reconstruct the served band from the receipt alone. This is the operational instantiation of property P1 (auditability) of §3.4.

## 4.6 Implementation and reproducibility

The deployed Oracle is implemented in two languages with byte-for-byte parity:

- *Python.* `src/soothsayer/oracle.py` — `Oracle.fair_value(symbol, as_of, target_coverage)`. Numeric parameters are exposed as module-level constants (`BUFFER_BY_TARGET`, `MAX_SERVED_TARGET`, `REGIME_FORECASTER`, `DEFAULT_FORECASTER`).

- *Rust.* `crates/soothsayer-oracle/src/{config,oracle}.rs` — same API, same constants, same arithmetic. The Rust port is the production serving binary; the Python is the research and backtest implementation. `scripts/verify_rust_oracle.py` runs both implementations on a 75-case test panel and asserts byte-for-byte equality on every field of the returned `PricePoint`. Parity was verified after every methodology change in the 2026-04-25 sequence (per-target buffer landing, grid extension, $\tau=0.99$ buffer bump).

End-to-end reproduction is a single command per stage:

```
uv run python scripts/run_calibration.py    # rebuild bounds + surface artifacts
uv run python scripts/smoke_oracle.py        # cross-symbol demo of the served API
uv run python scripts/refresh_oos_validation.py  # produces the §6.4 OOS tables
```

All inputs are public and free (§5.7); no credentials are required for the calibration backtest itself.
