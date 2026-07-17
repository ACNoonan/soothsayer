# §7 — Ablation Study

Three components are load-bearing for the calibration claim; we isolate each by descriptive comparator (full per-component tables and the σ̂-selection procedure are in Appendix C). All deltas carry weekend-block-bootstrap 95% CIs (1000 resamples, paired by `(symbol, fri_ts)`).

**§7.1 Regime stratification — vs a constant-buffer baseline.** The deployable comparator a protocol team reaches for first is Friday's close held forward with one global symmetric buffer $b(\tau)$ per quantile, $b(\tau)$ fit on the calibration set and carried to the 2023+ holdout:

| $\tau$ | constant buffer (train-fit) | deployed | $p_\text{uc}$ (CB / deployed) |
|---:|---:|---:|---:|
| 0.68 | 0.538 | 0.693 | $0.000$ / $0.264$ |
| 0.85 | 0.731 | 0.855 | $0.000$ / $0.565$ |
| 0.95 | 0.897 | 0.950 | $0.000$ / $0.956$ |
| 0.99 | 0.984 | 0.990 | $0.018$ / $0.942$ |

The training-fit constant buffer **catastrophically under-covers** at every $\tau \le 0.95$ (deficits $-14.2 / -12.0 / -5.4$ pp, all rejecting Kupiec at $p < 10^{-6}$) — its buffer is calibrated on a 2014–2022 window calmer than the holdout. The regime-stratified architecture holds coverage through the shift and, coverage-matched against an *oracle-fit* constant buffer, is **narrower** at $\tau \in \{0.85, 0.95\}$ ($-5.7\%$, $-6.3\%$), concentrating width in `high_vol` weekends where the constant buffer's violations would otherwise cluster.

**§7.2 Per-symbol σ̂ standardisation — vs unweighted Mondrian.** The same per-regime conformal architecture without per-symbol scale standardisation pools to nominal coverage but is per-symbol bimodal — heavy-tail tickers under-cover, low-vol over-cover — failing Kupiec on 8 of 10 symbols at $\tau = 0.95$. Standardising the conformity score by a per-symbol pre-Friday $\hat\sigma_s(t)$, with no other architectural change, takes per-symbol Kupiec from **2/10 to 10/10**. The §6 four-DGP simulation reproduces this bimodality under known ground truth and confirms σ̂ standardisation closes it on every DGP.

**§7.3 Near-identity OOS $c(\tau)$.** The four-scalar multiplicative correction is essentially identity at three anchors; only $c(0.95) = 1.079$ carries meaningful OOS information, and it is held out at the time level (§6.3, §9).

**§7.6 Tokenized-tracking baseline (post-Cong).** Against a non-parametric empirical-quantile band on the xStock-backed perp — the continuously-updating archetype Cong et al. motivate empirically — the deployed architecture wins on the Winkler interval score for **7 of 9** perp-listed names and ties on SPY and TSLA, the two deepest perps where the Cong passthrough has the most bite and a simple perp band is competitive. The edge is largest on thin-liquidity long-tail collateral (HOOD, GOOGL, NVDA, MSTR, GLD, AAPL; Winkler $1.36$–$3.32\times$): the advantage concentrates precisely where a consumer's closed-market risk-management need is greatest. (Powered backtest: the §6 panel; §7.6 is a smaller-$n$ head-to-head where the paired Winkler comparison, not the coverage test, is the discriminating signal.)
