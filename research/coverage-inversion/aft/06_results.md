# §6 — Results

We report calibration of the deployed locally-weighted Mondrian split-conformal architecture on two closed-market panels. The full diagnostic battery — realised-move tertiles, the joint-tail empirical distribution, the worst-weekend vignette, DQ/Berkowitz localisation, the 4-method per-symbol master grid, the forward-tape harness, and the four-DGP simulation study — is in Appendix B.

## 6.1 Evaluation protocol

The primary panel is $N = 5{,}996$ weekend prediction windows (ten US-listed tickers × 639 weekends, 2014-01-17 → 2026-04-24); the overnight panel (§6.6) is 22,624 close→next-open rows on the same symbols, constructed identically bar the gap selector (§5.2.1). The σ̂ warm-up (≥8 past observations per symbol) leaves 5,916 evaluable weekend rows. Per-regime quantiles are fit on the pre-2023 calibration slice (4,186 rows) and served on the 2023+ OOS slice (1,730 rows × 173 weekends); the four-scalar $c(\tau)$ schedule is OOS-fit (provenance in §9), and the walk-forward $\delta(\tau)$ schedule is identically zero (§4.5). All $p$-values are two-sided Kupiec POF and Christoffersen independence tests.

## 6.2 Pooled out-of-sample calibration

| $\tau$ | Violations | Rate | Kupiec $p_\text{uc}$ | Christoffersen $p_\text{ind}$ | $c(\tau)$ |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 532 | 0.308 | 0.264 | 0.244 | 1.000 |
| 0.85 | 251 | 0.145 | 0.565 | 0.403 | 1.000 |
| **0.95** | **86** | **0.050** | **0.956** | **0.603** | **1.079** |
| 0.99 | 17 | 0.010 | 0.942 | $\approx 1.0$ | 1.003 |

Kupiec and Christoffersen pass at every served anchor; the $\tau = 0.95$ headline realises $0.9503$ at mean half-width $370.6$ bps.

![Weekend calibration on the 1,730-row 2023+ OOS slice. The deployed architecture (blue) tracks the $45^\circ$ diagonal across $\tau \in [0.68, 0.99]$; GARCH(1,1)-$t$ markers (vermilion) under-cover at $\tau \in \{0.68, 0.85, 0.95\}$. Star marks the $\tau = 0.95$ headline.\label{fig:calibration}](figures/fig2_calibration.pdf)

## 6.3 Held-out calibration — leave-one-symbol-out and temporal holdout

The headline is held out on two orthogonal axes. **Symbol:** leave-one-symbol-out CV — each symbol's rows withheld from both the quantile and $c(\tau)$ fits — realises $0.9497 \pm 0.0128$ at $\tau = 0.95$ with all 10 held-out bands passing Kupiec. **Time:** a nested split fitting $c(0.95)$ on 2023 alone and evaluating on the true-holdout 2024-01-05 → 2026-04-24 slice realises $0.9504$ (Kupiec $p = 0.947$, Christoffersen $p = 0.989$, per-symbol Kupiec 10/10); $c(0.95)$ on the TUNE slice matches the full-OOS fit to three decimals. Calibration holds across the 2023 / 2024 / 2025 / 2026-YTD calendar sub-periods (Appendix B).

## 6.4 Per-symbol generalisation and baselines

All ten symbols pass per-symbol Kupiec at $\tau = 0.95$ (violation rates $3.5$–$6.9\%$). On a 40-cell (symbol × $\tau$) grid jointly evaluated under Kupiec, Christoffersen, and Engle–Manganelli DQ, the architecture carries **40/40 Kupiec, 38/40 Christoffersen, 39/40 DQ** — leading the strongest practitioner baseline, GARCH(1,1)-$t$ (31/40, 37/40, 31/40), which visibly under-covers at $\tau \in \{0.68, 0.85, 0.95\}$ despite tighter bands. The single residual is a **pooled DQ rejection** that appears only when violations are concatenated across symbols: the bands are *per-anchor calibrated*, not full-distribution calibrated, and the rejection localises to a within-weekend cross-sectional cluster topology ($\hat\rho_\text{cross} = 0.354$) orthogonal to the per-symbol σ̂ standardisation (§9; full localisation in Appendix B). Against a tokenised-tracking baseline the architecture wins on Winkler for 7 of 9 perp-listed names and ties on SPY and TSLA — the two deepest xStock perps, where a simple empirical-quantile band on the perp is competitive — with the edge largest on thin-liquidity long-tail collateral (§7.6).

![Anatomy of the served band on the worst observed weekend (2024-08-02 → 2024-08-05, BoJ yen-carry unwind), computed from the deployment artefact. Nested served bands at $\tau \in \{0.85, 0.95, 0.99\}$, factor-adjusted point (black tick), realised Monday open (filled = breach at $\tau = 0.95$). Per-symbol $\hat\sigma_s$ width differentiation is direct — MSTR's $\tau = 0.85$ half-width (663 bps) is $\approx 8\times$ SPY's (85 bps) — and so is the cross-sectional common-mode: nine opens march left past their bands in concert ($k_w = 9$ at $\tau = 0.95$; only TLT inside), which no per-symbol band can absorb. The joint-tail $k_w$ distribution (Appendix B) is the operational handle for this event class.\label{fig:boj-anatomy}](figures/fig9_boj_anatomy.pdf)

## 6.5 Path coverage — endpoint vs intra-weekend

The §6.2 result is *endpoint* coverage. On a 24/7 stock-perp reference (Kraken Futures, $n = 118$ symbol-weekends) the $\tau = 0.95$ endpoint-vs-path gap is $+16.1$ pp; after thin-liquidity confound checks the residual genuine shortfall is $\sim 9$–$15$ pp. An excursion-inflation diagnostic decomposes the source: on the CME factor-projected path, the band-widening required for $\tau$ path coverage is $\lambda(\tau) \approx 1.0$ — the endpoint-sized band already covers the projectable fair-value path — so the perp residual is predominantly venue basis and microstructure, not forecaster deficiency. The served contract remains the endpoint claim; a continuous-consumption consumer steps up one anchor (the gap closes at $\tau = 0.99$) or adopts the path-fitted conformity score (§10.2).

## 6.6 Off-hours generalisation — overnight gaps

The closed-market problem recurs every trading night, not only on weekends. We rebuild the panel with a single change — the gap selector admits consecutive-trading-day pairs (close → next-open) — yielding **22,624 overnight rows across 2,412 weeknights** on the same ten symbols (≈3.8× the weekend panel); every downstream component is reused unchanged, and the §6.2–§6.5 weekend results are byte-identical under the default selector. The regime set is re-derived for the cadence (§4.3.1): `long_weekend` is dropped and an `earnings_night` regime is added.

| $\tau$ | Violations | Rate | Kupiec $p_\text{uc}$ | Christoffersen $p_\text{ind}$ | $c(\tau)$ |
|---:|---:|---:|---:|---:|---:|
| 0.68 | 2,062 | 0.320 | 0.957 | 0.573 | 1.019 |
| 0.85 |   965 | 0.150 | 0.931 | 0.243 | 1.000 |
| **0.95** | **311** | **0.048** | **0.509** | **0.165** | **1.000** |
| 0.99 |    52 | 0.008 | 0.105 | 1.000 | 1.000 |

**Kupiec and Christoffersen pass at every anchor on the overnight OOS slice (6,450 rows × 645 nights)** — the same property as the weekend panel, on a different and larger panel, with the OOS-fit $c(\tau)$ collapsing to ≈1.0. A moving-block-bootstrap (block lengths $L \in \{1, 5, 10\}$) places the nominal violation rate inside the 95% CI at every $\tau$, so consecutive-night autocorrelation does not invalidate the claim. `normal` and `high_vol` are near-nominal; `earnings_night` over-covers (the contract-favourable direction). This regime is the architecture's only *calendar-conditioned* one: because an earnings release is a scheduled, publicly dated event, the band widens deterministically ahead of it — which no incumbent oracle does — and stays calibrated despite an earnings-night tail roughly $8\times$ the normal-night scale (§4.3.1).

![Overnight calibration on the 645-night OOS slice. Pooled realised coverage (blue) tracks the nominal diagonal at all four served anchors. Per-regime: `normal` (grey) and `high_vol` (amber) near-nominal; `earnings_night` (vermilion, $n \approx 60$) over-covers, the contract-favourable direction. The visual parallel to the weekend calibration is the point: the same architecture calibrates on a ≈3.8× larger closed-market panel.\label{fig:overnight-calibration}](figures/fig8_overnight_calibration.pdf)
