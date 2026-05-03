# §9 — Limitations

This section enumerates the assumptions under which the claims of §3.4 hold, the failure modes the backtest exposed, and the domain boundaries outside which we make no assertion. Most items correspond to explicit deferrals; each points forward to §10. The strongest open issues — Berkowitz / DQ rejections, no live deployment window, and the OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedule provenance — are not contradictions of the primitive but the empirical map of what a v3 system should improve.

## 9.1 Shock-tertile empirical ceiling

The weekend-realised-move distribution has a heavy tail: a realised-move z-score tertile labelled `shock` ($|z| \ge 0.67$ standardised by Friday's 20-day vol) has a structural realised-coverage ceiling of approximately $80\%$ at the nominal $95\%$ claim, because pre-publish information is insufficient to predict those moves. We do not attempt to raise this ceiling; we disclose it. Protocols that accept Soothsayer should treat shock-tertile tails as explicitly out-of-model and either apply exogenous widening (e.g., a circuit breaker tied to overnight futures moves) or reduce collateralisation when shock-tertile entry is plausible. The ceiling is reported transparently in every `PricePoint` diagnostic.

## 9.2 Stationarity assumption behind P2

P2 holds under the assumption that $P_t \mid (\mathcal{F}_t,\ \rho = r)$ is approximately stationary across $\mathcal{T}_\text{hist}$ and the deployment horizon. This is plausibly violated in three ways: (i) **structural breaks** (2020 COVID, 2022 rate regime, mid-2025 24/7 tokenised-stock launch); (ii) **regime-labeler drift** ($\rho$ uses a trailing 252-day VIX percentile; persistent rises shift the threshold endogenously); (iii) **factor-switchboard drift** (MSTR pivots from ES=F to BTC-USD on 2020-08-01; a second pivot would require re-fit). A conformalised variant (§10) would upgrade P2 from asymptotic-under-stationarity to finite-sample-under-exchangeability.

## 9.3 OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedules

Deployed values: $c \in \{1.498, 1.455, 1.300, 1.076\}$, $\delta \in \{0.05, 0.02, 0.00, 0.00\}$ at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$. Three weaknesses:

1. **OOS-fit on a single slice (partially closed by walk-forward).** Each $c(\tau)$ was fit on the pooled 2023+ slice. The 6-split walk-forward (§7.2.3) produces a distribution: at $\tau = 0.95$, mean $1.252$, $\sigma = 0.056$; the deployed $c(0.95) = 1.300$ is $\sim 1\sigma$ above mean by deliberate choice. We commit to re-measuring as part of any rolling rebuild (§10.1).

2. **Per-anchor schedule, not a continuous function.** Off-grid targets interpolate linearly. A continuous (spline) fit comparison was not run.

3. **No finite-sample guarantee on the $c(\tau)$ overshoot.** A full-distribution conformal upgrade would replace the empirical guarantee with a finite-sample exchangeability-based one (§10).

The `calibration_buffer_applied` field carries $\delta(\tau)$ as a first-class receipt; diagnostics carry $c(\tau)$ and $q_\text{eff}$.

## 9.4 The Berkowitz / DQ rejections

The served band is *per-anchor calibrated* (Kupiec passes at every $\tau$, Christoffersen passes at every $\tau \ge 0.85$) but *not full-distribution calibrated* (Berkowitz LR $= 173.1$; DQ at $\tau = 0.95$ $p = 5.7 \times 10^{-6}$). The mechanism is structural: $\rho$ is a coarse three-bin index. Within a regime the residual distribution varies across symbols and across non-anchor $\tau$; the per-regime quantile is correct on average within each regime × anchor cell, but residual autocorrelation *between* anchors and tickers is what Berkowitz and DQ pick up. A finer classifier or full-distribution conformal would close this gap. A protocol consuming Soothsayer at a single $\tau$ is fully served by the per-anchor guarantee; one wanting joint coverage across multiple $\tau$ simultaneously must either accept the disclosed residual uncertainty or wait for v3.

## 9.5 No live deployment window

The empirical claims of §6 are backtested, not live. The shipped Rust serving layer and on-chain publisher (§8) are functionally verified (90/90 parity) but have not run as a live price feed consumed by a production protocol. A live window — with real integrators, real consumers, an adversarial environment — will exhibit modes a backtest cannot. The paper should be read as *validation of a calibration primitive on historical data*, not production-quality assurance. A live window would close the external-validity gap; it would not by itself make Berkowitz or DQ pass, which is why §10 separates live-deployment work from methodology upgrades.

## 9.6 Partial-only numerical incumbent benchmark

§6.5 reports a partial comparison against regular Pyth (265 obs) and Chainlink Data Streams v10 + v11; the three caveats (wide sample CIs, large-cap normal-regime composition, consumer-supplied wrap multipliers) prevent reading any matched-bandwidth observation as a head-to-head loss. RedStone Live is excluded (no calibration object on the wire); a forward-cursor tape began capture on 2026-04-26 and will be reportable once a paper-grade sample accumulates. Pyth Pro / Blue Ocean is excluded on access and window grounds. RedStone-specific scoping: the public REST gateway prices underlier tickers (SPY, QQQ, MSTR), not the SPL xStock tokens consumers hold; coverage on TSLA, NVDA, HOOD, GOOGL is empty and AAPL was 33d stale (2026-04-25); retention is hard-capped at 30 days, so only forward-collected weekends can enter such a comparison.

## 9.7 No optimal liquidation-policy benchmark

The paper validates an oracle interface, not a lending policy. We do not report a decision-theoretic benchmark of "what target $\tau$ should a protocol choose?" Answering requires three ingredients absent here: (i) an explicit borrower-book LTV distribution; (ii) a protocol-specific cost model distinguishing unnecessary liquidation, unnecessary caution, and missed liquidation / bad debt; (iii) a declared semantics for what counts as the correct action under realised prices. Paper 3 addresses this.

## 9.8 Scope of the methodology

**Region scope.** All ten tickers are US-listed; the weekend predicted is the US weekend. The factor switchboard privileges US session data. We make no claim about generalisation to tokenised-JP or tokenised-EU equities.

**Asset-class scope.** The methodology requires a *continuous off-hours information set* — a public, free, sub-daily price signal correlated with the closed-market underlier. Tokenised US equities have this (E-mini futures + VIX), tokenised gold has it (gold futures + GVZ), tokenised US treasuries have it (10Y T-note futures + MOVE), and most major FX pairs have it. Tokenised credit has it through CDS spreads. Out of scope: real estate (no continuous off-hours signal; NAV updates discrete and infrequent), illiquid commodities (futures discontinuous or thin), and instruments with primarily NAV-based pricing. `docs/methodology_scope.md` carries the per-class fit/no-fit table.

## 9.9 Scope and non-claims

Three concerns that do *not* apply, plus two known gaps deferred:

- **Oracle manipulation.** Coverage transparency is orthogonal to integrity. Soothsayer is designed to be read alongside an adversarially-robust feed, not as its replacement.
- **Latency.** The serving-time Oracle is a five-line lookup; nothing in the coverage-inversion mechanism requires a live forecast computation.
- **On-chain xStock TWAP not consumed.** Cong et al. [cong-tokenized-2025] document off-hour returns on tokenised stocks anticipate Monday opens. Our base forecaster does not read this; the V5 forward-cursor tape supplies the data but only ~30 weekends of post-launch history exist. Documented as v2 work (§10.1's V3.1).
- **MEV and consumer-experienced coverage.** Realised coverage in §6 is computed against the venue Monday opening reference. A consumer transacting at a worse price (front-running, sandwich, block-builder reordering) experiences an *effective* coverage that may differ near band edges. Measuring this requires Solana mempool-or-bundle granularity plus a consumer-behaviour model; documented as v3 work (§10.1's V3.3).

These limitations are disclosures, not retractions. Each has a concrete follow-up in §10.
