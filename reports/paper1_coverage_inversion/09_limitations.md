# §9 — Limitations

This section enumerates the assumptions under which the claims of §3.4 hold, the failure modes the backtest exposed, and the domain boundaries outside which we make no assertion. Most items here correspond to explicit deferrals rather than unknown unknowns; each points forward to §10 with a concrete follow-up. The strongest open issues — Berkowitz / DQ rejections, no live deployment window, and the OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedule provenance — are not contradictions of the coverage-inversion primitive. They are the empirical map of what a v3 system should improve.

## 9.1 Shock-tertile empirical ceiling

The weekend-realised-move distribution has a heavy tail: a realised-move z-score tertile labelled `shock` in our backtest (post-hoc, using $|z| \ge 0.67$ standardised by Friday's 20-day vol) has a structural realised-coverage ceiling of approximately $80\%$ at the nominal $95\%$ claim — because pre-publish information is insufficient to predict those moves. We do not attempt to raise this ceiling; we disclose it. Protocols that accept Soothsayer as a collateral-valuation input should treat shock-tertile tails as explicitly out-of-model and either apply their own exogenous widening (e.g., a circuit breaker tied to overnight futures moves) or reduce collateralisation during periods where shock-tertile entry is plausible.

The ceiling is reported transparently in every `PricePoint` diagnostic via the calibration receipt: the served $q$ carries the historical realised coverage at its bucket, and a consumer can read off the tail risk before using the band.

## 9.2 Stationarity assumption behind P2

Claim P2 (conditional empirical coverage, §3.4) is an *empirical* statement. It holds under the assumption that the conditional distribution $P_t \mid (\mathcal{F}_t,\ \rho(\mathcal{F}_t) = r)$ is approximately stationary across $\mathcal{T}_\text{hist}$ and the target deployment horizon. This assumption is plausibly violated in at least three ways:

- **Structural breaks in microstructure.** The 2020 COVID shock, the 2022 rate regime, and the introduction of 24/7 tokenized-stock trading on Solana in mid-2025 each plausibly shifted the conditional distribution. Our 2023+ OOS slice includes the 2022-→-2023 regime transition; it does not cover a comparable future break.
- **Regime-labeler drift.** $\rho$ uses a trailing 252-trading-day VIX percentile to tag `high_vol`; a persistent rise in baseline vol (e.g., 2022-like) shifts the threshold endogenously. This is a feature for rolling deployment but can defeat the cross-regime fairness of the `high_vol`-vs-`normal` comparison.
- **Factor-switchboard drift.** MSTR's factor mapping pivots from ES=F to BTC-USD on 2020-08-01 (the BTC-proxy transition). This is a hand-coded pivot in `FACTOR_BY_SYMBOL`. A second pivot — e.g., if MSTR's BTC sensitivity decays — would require a re-fit.

A conformalised variant (§9.3 and §10) would upgrade P2's guarantee from asymptotic-under-stationarity to finite-sample-under-exchangeability; the latter is strictly weaker and measurable.

## 9.3 OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedules

The served M5 Oracle applies two deployment-tuned schedules on top of the trained per-regime conformal quantiles: a multiplicative bump $c(\tau)$ and a $\tau$-shift $\delta(\tau)$. The deployed values are:

$$c \in \{0.68 \to 1.498,\ 0.85 \to 1.455,\ 0.95 \to 1.300,\ 0.99 \to 1.076\},$$
$$\delta \in \{0.68 \to 0.05,\ 0.85 \to 0.02,\ 0.95 \to 0.00,\ 0.99 \to 0.00\}.$$

$c(\tau)$ is fit on the same 2023+ OOS slice that §6.4 evaluates the served band on (the smallest $c$ such that pooled realised coverage with effective quantile $c \cdot q_r(\tau)$ matches the consumer's $\tau$). $\delta(\tau)$ is selected from a sweep on the 6-split expanding-window walk-forward (the smallest schedule aligning per-split realised coverage with nominal at every anchor; §7.2.4). Both schedules are 4-scalar each, jointly matching the v1 Oracle's `BUFFER_BY_TARGET` parameter budget exactly.

Three weaknesses of this choice:

1. **OOS-fit on a single slice (partially closed by walk-forward).** Each $c(\tau)$ was fit on the pooled 2023+ slice. The 6-split walk-forward of §7.2.4 produces a distribution of per-split $c(\tau)$: at $\tau = 0.95$, mean $= 1.252$, $\sigma = 0.056$; the deployed $c(0.95) = 1.300$ is $\sim 1\sigma$ above mean by deliberate choice (the conservative side). At $\tau = 0.68$, mean $= 1.344$, $\sigma = 0.040$; the deployed $1.498$ is $\sim 4\sigma$ above mean — load-bearing for the $\delta = 0.05$ shift's coverage-attainment guarantee. The disclosure is therefore tightened, not eliminated: we commit to re-measuring the schedule as part of any rolling artefact rebuild (§10.1).

2. **Per-anchor schedule, not a continuous function.** Off-grid targets interpolate linearly between the four anchor points. A reviewer might prefer a continuous function fit (e.g., spline) on a finer sweep grid; we have not done that comparison.

3. **No finite-sample guarantee on the $c(\tau)$ overshoot.** $c(\tau)$ is fit empirically by minimising width subject to a coverage constraint. It does not carry a finite-sample upper bound on coverage of the form a full split-conformal procedure would (i.e., $\tau \le \mathbb{E}[\hat\tau] \le \tau + 1/(n+1)$). A full-distribution conformal upgrade — fitting $c$ as an explicit conformal correction over the residual CDF instead of as a width-minimising scalar — would replace the empirical guarantee with a finite-sample exchangeability-based one. This is reserved as v3 work (§10).

The choice to ship a 4+4 deployment-tuned schedule now and re-evaluate full-distribution conformal in v3 is disclosed, not evaded. The `calibration_buffer_applied` field on every `PricePoint` carries $\delta(\tau)$ as a first-class receipt; the diagnostics carry $c(\tau)$ and $q_\text{eff}$. The consumer sees exactly which schedule was applied to their served band.

## 9.4 The Berkowitz / DQ rejections — coarse regime classifier, not a fixable defect

The deployed M5 served band is *per-anchor calibrated* (Kupiec passes at every $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ on OOS, Christoffersen passes at every $\tau \ge 0.85$) but *not full-distribution calibrated* (§6.4.1: Berkowitz LR $= 173.1$, $\hat\rho = 0.31$; DQ at $\tau = 0.95$ stat $= 32.1$, $p = 5.7 \times 10^{-6}$); §7.2.5 confirms the diagnosis on M5's walk-forward PITs.

The mechanism is structural rather than sample-size-bounded. The regime classifier $\rho$ is a coarse three-bin index over the joint distribution of weekend conditioning information (gap-days + VIX percentile, §5.5). Within a regime, the residual distribution still varies across symbols and across $\tau$ that are not anchor-locked — the per-regime conformal quantile $q_r(\tau)$ is correct on average within each regime × anchor cell, but the residual *between* anchors and *between* tickers retains autocorrelation that Berkowitz and DQ pick up. A finer regime classifier (e.g., a continuous regime score; or per-symbol vol indices entering $\rho$ directly) or a full-distribution conformal procedure (which calibrates against the entire residual CDF rather than four discrete anchors) would close this gap.

The disclosure is that the deployed bands meet the consumer's per-anchor target with the right rate; they do not meet a stricter joint-coverage-across-the-distribution test that the underlying calibration architecture is not designed to pass. A protocol that consumes Soothsayer at a single $\tau$ — say $\tau = 0.85$ for a default lending substrate — is fully served by the per-anchor guarantee. A protocol that wants joint coverage across multiple $\tau$ simultaneously (e.g., a structured product whose payoff depends on $P(\tau_1 \le X \le \tau_2)$) needs to either consume multiple anchor reads and accept the residual joint-coverage uncertainty disclosed here, or wait for the v3 full-distribution upgrade.

## 9.5 No live deployment window

The empirical claims of §6 are backtested, not live. As of the submission of this paper, the shipped Rust serving layer and on-chain publisher program (§8) are functionally verified (byte-for-byte Python↔Rust parity on 90 test cases) but have not run as a live price feed consumed by a production protocol. A live window — with real integrators, real consumers, and an adversarial environment — will exhibit modes that a backtest cannot. The paper should be read as *validation of a calibration primitive on historical data*, not as a production-quality assurance.

This limitation is orthogonal to the stricter diagnostic rejections above. A live deployment window would close the external-validity gap and let us measure drift, consumer-experienced coverage, and rebuild stability in production. It would not by itself make Berkowitz or DQ pass; those failures speak to the current statistical design of the calibration layer and regime structure, which is why §10 separates live-deployment work from methodology upgrades.

## 9.6 Partial-only numerical incumbent benchmark

§6.7 reports a partial numerical comparison against regular Pyth (265-obs Hermes subset, 2024+, eight-of-ten symbol coverage) and Chainlink Data Streams v10 + v11; §6.7 enumerates the three caveats — wide sample-size CIs, large-cap normal-regime sample composition, consumer-supplied wrap multipliers — that prevent reading the matched-bandwidth observation as a head-to-head loss. The Chainlink v11 weekend numbers are computed against the marker-aware classifier in `reports/v11_cadence_verification.md` (v2, 2026-04-26) over a 26-report scan across four mapped xStock feeds; the qualitative conclusion — neither v10 (band-less by construction) nor v11 (synthetic-marker placeholders for SPYx/QQQx/TSLAx; n=1 REAL for NVDAx) publishes a coverage band a consumer can read directly — is the corrected reading. RedStone Live is excluded entirely — no calibration object on the wire (§9.6.1); a forward-cursor tape began continuous capture on 2026-04-26 via the scryer ingest fleet and will be reportable once it accumulates a paper-grade weekend sample. Pyth Pro / Blue Ocean is excluded from the numerical comparison on both access (paid enterprise tier; soothsayer holds no Pro subscription) and window (Sun–Thu 8 PM – 4 AM ET overnight, not the Friday-close-to-Monday-open weekend §6.4 evaluates) grounds. A research-paper-grade matched-window comparator dashboard against all incumbents on a common evaluation slice — uniform date range, uniform symbol coverage, per-regime stratification, weekend-block bootstrap CIs — remains future work (§10).

### 9.6.1 RedStone-specific scoping limits

Three structural facts further constrain what a RedStone Live comparison can claim, beyond the general incumbent-benchmark limitation above. (i) RedStone's public REST gateway (`api.redstone.finance/prices`) prices the *underlier tickers* (SPY, QQQ, MSTR), not the actual tokenized SPL xStock tokens (SPYx, QQQx, MSTRx) that consumers on Solana hold and that this paper's calibration surface targets — a comparison reads RedStone's view of SPY against our view of SPYx, which are economically related but not the same instrument. (ii) Coverage on the gateway is partial as of 2026-04-25: TSLA, NVDA, HOOD, and GOOGL return empty and AAPL was 33d stale, restricting any matched comparison to the SPY/QQQ/MSTR subset. (iii) Gateway retention is hard-capped at 30 days, which means a parity comparison against our 12-year underlying-equity panel is impossible — only forward-collected weekends from 2026-04-26 onward can enter such a comparison. Whether the paid RedStone Live WebSocket tier serves a confidence field, a longer history, or the missing equity tickers is not verifiable from public artifacts. The "undisclosed methodology" framing of §1 and §2 is therefore restated more precisely as "no calibration claim exposed in any public artifact (REST gateway, on-chain PDA, or launch post)."

## 9.7 No optimal liquidation-policy benchmark

The paper validates an oracle interface, not a lending policy. We do not report a decision-theoretic benchmark of "what target $\tau$ should a protocol choose?" or "does a regime-demoted liquidation threshold dominate a flat threshold once portfolio weights and protocol losses are specified?" Answering those questions requires at least three ingredients absent from the present evaluation: (i) an explicit distribution over borrower-book LTV weights rather than a pure coverage metric, (ii) a protocol-specific cost model distinguishing unnecessary liquidation, unnecessary caution, and missed liquidation / bad debt, and (iii) a declared semantics for what counts as the correct action under realised prices. Without those ingredients, a claim of optimal liquidation-policy default would be stronger than the evidence we present here.

## 9.8 Scope of the methodology — what fits and what does not

**Region scope.** All ten tickers in the backtest are US-listed. The weekend we predict is the US weekend. The factor-switchboard mapping (ES/NQ/GC/ZN/BTC) privileges US session data. We make no claim about the generalisation of the coverage-inversion primitive to tokenized-JP equities, tokenized-EU equities, or commodities whose primary discovery venue is not a US exchange.

**Asset-class scope.** The methodology requires a *continuous off-hours information set* — a public, free, sub-daily price signal that is observably correlated with the closed-market underlier. Tokenized US equities have this (E-mini index futures + VIX), tokenized gold has it (gold futures + GVZ), tokenized US treasuries have it (10Y T-note futures + MOVE), and most major FX pairs have it (overseas-session prices). Tokenized credit has it through CDS spreads and index volatility, modulo data licensing. We claim the methodology generalises to any RWA class with such a signal. Out of scope: real estate (no continuous off-hours information set; NAV updates discrete and infrequent), illiquid commodities (futures discontinuous or thin; $\hat\beta$ unstable), and instruments with primarily NAV-based pricing (no market-observed "fair value" question to calibrate against). `docs/methodology_scope.md` carries the per-class fit/no-fit table.

## 9.9 Scope and non-claims

Three concerns that do *not* apply to the coverage-inversion primitive as specified, plus two known gaps deferred to v2 / v3:

- **Oracle manipulation.** Coverage transparency is orthogonal to integrity. Soothsayer is designed to be read alongside an adversarially-robust feed, not as its replacement.
- **Latency.** The serving-time Oracle is a five-line lookup against the per-Friday Mondrian artefact (`mondrian_artefact_v2.parquet`) plus 20 module-level constants; byte-for-byte verified in Rust; nothing in the coverage-inversion mechanism requires a live heavy-weight forecast computation. Performance budgeting is a §8 concern, not a correctness one.
- **On-chain xStock TWAP not consumed.** Cong et al. [cong-tokenized-2025] document that off-hour returns on tokenized stocks anticipate, rather than amplify, subsequent Monday opens. Our base forecaster does not read this signal; the V5 forward-cursor tape supplies the data but only ~30 weekends of post-launch history exist as of submission, well short of the ~150 weekends required for stable per-(symbol, regime) Kupiec validation. Documented as v2 work (§10.1's V3.1 F\_tok forecaster).
- **MEV and consumer-experienced coverage.** Realised coverage in §6 is computed against the venue Monday opening reference price $P_t$. A consumer who reads the Soothsayer band at on-chain mid and then transacts at a worse price (front-running, sandwich, block-builder reordering) experiences an *effective* coverage rate that may differ from our reported coverage near the band edge. Measuring this gap requires Solana mempool-or-bundle granularity plus a consumer-behaviour model; documented as v3 work (§10.1's V3.3).

---

These limitations are disclosures, not retractions. Each has a concrete follow-up in §10.
