# §9 — Limitations

This section enumerates the assumptions under which the claims of §3.4 hold, the failure modes the backtest exposed, and the domain boundaries outside which we make no assertion. Most items here correspond to explicit deferrals rather than unknown unknowns; each points forward to §10 (Future Work) with a concrete follow-up. In particular, the strongest open issues in the present draft — Berkowitz / DQ rejections inherited from the v1 architecture, no live deployment window, and the OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedule provenance — are not contradictions of the coverage-inversion primitive. They are the empirical map of what a v3 system should improve.

## 9.1 The high-$\tau$ tail (closed under M5; v1 disclosure preserved for context)

Under the v1 surface-plus-buffer Oracle at consumer target $\tau = 0.99$, the served band delivered realised coverage $0.972$ on the OOS slice — a $1.8$pp shortfall by Kupiec ($p_{uc} \approx 0$). The structural cause was the per-(symbol, regime) calibration-window size: the log-log residual model was fit on a rolling 156-weekend window, and reliably resolving the 1% tail of that distribution required more observations than any one bucket carried. The 2026-04-25 grid extension to $\{0.997, 0.999\}$ lifted realised at $\tau = 0.99$ from $0.972$ to $0.977$ but did not close the gap.

The M5 deployment closes this ceiling. By collapsing the per-(symbol, regime, claimed) surface into a per-regime conformal quantile, the M5 architecture pools $N \approx 440$–$2{,}774$ observations per regime bucket — sufficient to estimate the 1% relative-residual tail without a sample-size collapse. At $\tau = 0.99$ on the OOS slice, M5 delivers realised coverage of $0.990$, Kupiec passes ($p_{uc} = 0.942$). The trade is a 22% wider band ($677.5$ bps half-width vs the v1 $522.8$ bps); the consumer who requests $\tau = 0.99$ now gets a band whose realised coverage matches the request, in exchange for absorbing the wider tail directly rather than receiving an undisclosed-finite-sample-ceiling band labelled "0.99". This is a bandwidth-for-honesty trade we believe is the right one for the consumer-as-protocol use case.

A protocol that prefers the v1 trade — narrower band at the cost of a disclosed under-coverage at $\tau = 0.99$ — can recover it by requesting $\tau = 0.97$ from M5 instead; the served band will be $\sim 522$ bps half-width and the receipt will disclose $\tau' = 0.97$. The point of the customer-selects-coverage interface is that this trade is a consumer choice, not an oracle-design choice.

## 9.2 Shock-tertile empirical ceiling

The weekend-realised-move distribution has a heavy tail: a realised-move z-score tertile labelled `shock` in our backtest (post-hoc, using $|z| \ge 0.67$ standardised by Friday's 20-day vol) has a structural realised-coverage ceiling of approximately $80\%$ at the nominal $95\%$ claim — because pre-publish information is insufficient to predict those moves. We do not attempt to raise this ceiling; we disclose it. Protocols that accept Soothsayer as a collateral-valuation input should treat shock-tertile tails as explicitly out-of-model and either apply their own exogenous widening (e.g., a circuit breaker tied to overnight futures moves) or reduce collateralisation during periods where shock-tertile entry is plausible.

The ceiling is reported transparently in every `PricePoint` diagnostic via the calibration receipt: the served $q$ carries the historical realised coverage at its bucket, and a consumer can read off the tail risk before using the band.

## 9.3 Stationarity assumption behind P2

Claim P2 (conditional empirical coverage, §3.4) is an *empirical* statement. It holds under the assumption that the conditional distribution $P_t \mid (\mathcal{F}_t,\ \rho(\mathcal{F}_t) = r)$ is approximately stationary across $\mathcal{T}_\text{hist}$ and the target deployment horizon. This assumption is plausibly violated in at least three ways:

- **Structural breaks in microstructure.** The 2020 COVID shock, the 2022 rate regime, and the introduction of 24/7 tokenized-stock trading on Solana in mid-2025 each plausibly shifted the conditional distribution. Our 2023+ OOS slice includes the 2022-→-2023 regime transition; it does not cover a comparable future break.
- **Regime-labeler drift.** $\rho$ uses a trailing 252-trading-day VIX percentile to tag `high_vol`; a persistent rise in baseline vol (e.g., 2022-like) shifts the threshold endogenously. This is a feature for rolling deployment but can defeat the cross-regime fairness of the `high_vol`-vs-`normal` comparison.
- **Factor-switchboard drift.** MSTR's factor mapping pivots from ES=F to BTC-USD on 2020-08-01 (the BTC-proxy transition). This is a hand-coded pivot in `FACTOR_BY_SYMBOL`. A second pivot — e.g., if MSTR's BTC sensitivity decays — would require a re-fit.

A conformalised variant (§9.4 and §10) would upgrade P2's guarantee from asymptotic-under-stationarity to finite-sample-under-exchangeability; the latter is strictly weaker and measurable.

## 9.4 OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedules

The served M5 Oracle applies two deployment-tuned schedules on top of the trained per-regime conformal quantiles: a multiplicative bump $c(\tau)$ and a $\tau$-shift $\delta(\tau)$. The deployed values are:

$$c \in \{0.68 \to 1.498,\ 0.85 \to 1.455,\ 0.95 \to 1.300,\ 0.99 \to 1.076\},$$
$$\delta \in \{0.68 \to 0.05,\ 0.85 \to 0.02,\ 0.95 \to 0.00,\ 0.99 \to 0.00\}.$$

$c(\tau)$ is fit on the same 2023+ OOS slice that §6.4 evaluates the served band on (the smallest $c$ such that pooled realised coverage with effective quantile $c \cdot q_r(\tau)$ matches the consumer's $\tau$). $\delta(\tau)$ is selected from a sweep on the 6-split expanding-window walk-forward (the smallest schedule aligning per-split realised coverage with nominal at every anchor; §7.7.4). Both schedules are 4-scalar each, jointly matching the v1 Oracle's `BUFFER_BY_TARGET` parameter budget exactly.

Three weaknesses of this choice:

1. **OOS-fit on a single slice (partially closed by walk-forward).** Each $c(\tau)$ was fit on the pooled 2023+ slice. The 6-split walk-forward of §7.7.4 produces a distribution of per-split $c(\tau)$: at $\tau = 0.95$, mean $= 1.252$, $\sigma = 0.056$; the deployed $c(0.95) = 1.300$ is $\sim 1\sigma$ above mean by deliberate choice (the conservative side). At $\tau = 0.68$, mean $= 1.344$, $\sigma = 0.040$; the deployed $1.498$ is $\sim 4\sigma$ above mean — load-bearing for the $\delta = 0.05$ shift's coverage-attainment guarantee. The disclosure is therefore tightened, not eliminated: we commit to re-measuring the schedule as part of any rolling artefact rebuild (§10.1).

2. **Per-anchor schedule, not a continuous function.** Off-grid targets interpolate linearly between the four anchor points. A reviewer might prefer a continuous function fit (e.g., spline) on a finer sweep grid; we have not done that comparison under M5. Under v1 the same disclosure applied to BUFFER_BY_TARGET; the M5 swap reframes the question but does not resolve it.

3. **No finite-sample guarantee on the $c(\tau)$ overshoot.** $c(\tau)$ is fit empirically by minimising width subject to a coverage constraint. It does not carry a finite-sample upper bound on coverage of the form a full split-conformal procedure would (i.e., $\tau \le \mathbb{E}[\hat\tau] \le \tau + 1/(n+1)$). A full-distribution conformal upgrade — fitting $c$ as an explicit conformal correction over the residual CDF instead of as a width-minimising scalar — would replace the empirical guarantee with a finite-sample exchangeability-based one. This is reserved as v3 work (§10).

The choice to ship a 4+4 deployment-tuned schedule now and re-evaluate full-distribution conformal in v3 is disclosed, not evaded. The `calibration_buffer_applied` field on every `PricePoint` carries $\delta(\tau)$ as a first-class receipt; the diagnostics carry $c(\tau)$ and $q_\text{eff}$. The consumer sees exactly which schedule was applied to their served band.

This matters for interpretation. The OOS-tuning limitation is not that the current system is unusable; it is that the current correction is empirical rather than theorem-backed. The practical research question for v3 is therefore not "whether a $c(\tau)$ overshoot is needed" — §7.7 already shows that it is load-bearing for OOS coverage at the deployed parameter budget — but which replacement improves on the current 4+4 heuristic under live drift: a continuous fit, a full-distribution conformal wrapper, or a rolling-reestimated schedule.

## 9.5 The Berkowitz / DQ rejections — coarse regime classifier, not a fixable defect

The deployed M5 served band is *per-anchor calibrated* (Kupiec passes at every $\tau \in \{0.68, 0.85, 0.95, 0.99\}$ on OOS, Christoffersen passes at every $\tau \ge 0.85$) but *not full-distribution calibrated* (§6.4.1: Berkowitz LR $= 173.1$, $\hat\rho = 0.31$; DQ at $\tau = 0.95$ stat $= 32.1$, $p = 5.7 \times 10^{-6}$). This pattern is shared with the v1 architecture and was not fixed by the M5 simplification — §7.7.5 confirms the diagnosis.

The mechanism is structural rather than sample-size-bounded. The regime classifier $\rho$ is a coarse three-bin index over the joint distribution of weekend conditioning information (gap-days + VIX percentile, §5.5). Within a regime, the residual distribution still varies across symbols and across $\tau$ that are not anchor-locked — the per-regime conformal quantile $q_r(\tau)$ is correct on average within each regime × anchor cell, but the residual *between* anchors and *between* tickers retains autocorrelation that Berkowitz and DQ pick up. A finer regime classifier (e.g., a continuous regime score; or per-symbol vol indices entering $\rho$ directly) or a full-distribution conformal procedure (which calibrates against the entire residual CDF rather than four discrete anchors) would close this gap.

The disclosure is that the deployed bands meet the consumer's per-anchor target with the right rate; they do not meet a stricter joint-coverage-across-the-distribution test that the underlying calibration architecture is not designed to pass. A protocol that consumes Soothsayer at a single $\tau$ — say $\tau = 0.85$ for a default lending substrate — is fully served by the per-anchor guarantee. A protocol that wants joint coverage across multiple $\tau$ simultaneously (e.g., a structured product whose payoff depends on $P(\tau_1 \le X \le \tau_2)$) needs to either consume multiple anchor reads and accept the residual joint-coverage uncertainty disclosed here, or wait for the v3 full-distribution upgrade.

## 9.6 [retired under M5 — deployed serving has no hybrid forecaster choice]

Under the v1 architecture, this section disclosed that the hybrid regime-to-forecaster policy (F1_emp_regime in normal/long_weekend, F0_stale in high_vol) was the empirically preferred deployment choice rather than a binary necessity. Under M5, the deployed Oracle has no per-regime forecaster choice — a single Mondrian conformal lookup keyed on $\rho$ replaces the v1 hybrid. The §7.7 ablation showed the F1_emp_regime forecaster machinery on top of $\rho$ is over-engineering relative to the per-regime conformal quantile, so the v1 hybrid policy is mooted by the architectural simplification. The historical record of the v1 hybrid policy and its empirical preference is preserved in `reports/methodology_history.md` (entries through 2026-04-25).

## 9.7 No live deployment window

The empirical claims of §6 are backtested, not live. As of the submission of this paper, the shipped Rust serving layer and on-chain publisher program (§8) are functionally verified (byte-for-byte Python↔Rust parity on 90 test cases) but have not run as a live price feed consumed by a production protocol. A live window — with real integrators, real consumers, and an adversarial environment — will exhibit modes that a backtest cannot. The paper should be read as *validation of a calibration primitive on historical data*, not as a production-quality assurance.

This limitation is orthogonal to the stricter diagnostic rejections above. A live deployment window would close the external-validity gap and let us measure drift, consumer-experienced coverage, and rebuild stability in production. It would not by itself make Berkowitz or DQ pass; those failures speak to the current statistical design of the calibration layer and regime structure, which is why §10 separates live-deployment work from methodology upgrades.

## 9.8 Partial-only numerical incumbent benchmark

§6.7 reports a partial numerical comparison against regular Pyth (265-obs Hermes subset, 2024+, eight-of-ten symbol coverage) and Chainlink Data Streams v10 + v11; §6.7 enumerates the three caveats — wide sample-size CIs, large-cap normal-regime sample composition, consumer-supplied wrap multipliers — that prevent reading the matched-bandwidth observation as a head-to-head loss. The Chainlink v11 weekend numbers are computed against the marker-aware classifier in `reports/v11_cadence_verification.md` (v2, 2026-04-26) over a 26-report scan across four mapped xStock feeds; the qualitative conclusion — neither v10 (band-less by construction) nor v11 (synthetic-marker placeholders for SPYx/QQQx/TSLAx; n=1 REAL for NVDAx) publishes a coverage band a consumer can read directly — is the corrected reading. The earlier 87-observation `v1b_chainlink_comparison.md` panel (Feb–Apr 2026, pre-correction decoder) is retained only as bandwidth provenance; its previously-reported "median weekend `bid`/`ask` = 0" was a decoder artefact superseded by the per-symbol synthetic-marker pattern in §6.7.2. RedStone Live is excluded entirely — no calibration object on the wire (§9.8.1); a forward-cursor tape began continuous capture on 2026-04-26 via the scryer ingest fleet and will be reportable once it accumulates a paper-grade weekend sample. Pyth Pro / Blue Ocean is excluded from the numerical comparison on both access (paid enterprise tier; soothsayer holds no Pro subscription) and window (Sun–Thu 8 PM – 4 AM ET overnight, not the Friday-close-to-Monday-open weekend §6.4 evaluates) grounds; the canonical reconciliation in [`docs/sources/oracles/pyth_lazer.md`](../../docs/sources/oracles/pyth_lazer.md) §6 Q1 documents an open empirical question — whether Blue Ocean's overnight prints flow into the public regular-Pyth `PriceAccount` surface or are Pro-tier-gated — that, when resolved, may admit a Sun–Thu overnight comparator without a paid subscription. A research-paper-grade matched-window comparator dashboard against all incumbents on a common evaluation slice — uniform date range, uniform symbol coverage, per-regime stratification, weekend-block bootstrap CIs — remains future work (§10).

### 9.8.1 RedStone-specific scoping limits

Three structural facts further constrain what a RedStone Live comparison can claim, beyond the general incumbent-benchmark limitation above. (i) RedStone's public REST gateway (`api.redstone.finance/prices`) prices the *underlier tickers* (SPY, QQQ, MSTR), not the actual tokenized SPL xStock tokens (SPYx, QQQx, MSTRx) that consumers on Solana hold and that this paper's calibration surface targets — a comparison reads RedStone's view of SPY against our view of SPYx, which are economically related but not the same instrument. (ii) Coverage on the gateway is partial as of 2026-04-25: TSLA, NVDA, HOOD, and GOOGL return empty and AAPL was 33d stale, restricting any matched comparison to the SPY/QQQ/MSTR subset. (iii) Gateway retention is hard-capped at 30 days, which means a parity comparison against our 12-year underlying-equity panel is impossible — only forward-collected weekends from 2026-04-26 onward can enter such a comparison. Whether the paid RedStone Live WebSocket tier serves a confidence field, a longer history, or the missing equity tickers is not verifiable from public artifacts. The "undisclosed methodology" framing of §1 and §2 is therefore restated more precisely as "no calibration claim exposed in any public artifact (REST gateway, on-chain PDA, or launch post)."

## 9.9 No optimal liquidation-policy benchmark

The paper validates an oracle interface, not a lending policy. We do not report a decision-theoretic benchmark of "what target $\tau$ should a protocol choose?" or "does a regime-demoted liquidation threshold dominate a flat threshold once portfolio weights and protocol losses are specified?" Answering those questions requires at least three ingredients absent from the present evaluation: (i) an explicit distribution over borrower-book LTV weights rather than a pure coverage metric, (ii) a protocol-specific cost model distinguishing unnecessary liquidation, unnecessary caution, and missed liquidation / bad debt, and (iii) a declared semantics for what counts as the correct action under realised prices. Without those ingredients, a claim of optimal liquidation-policy default would be stronger than the evidence we present here.

## 9.10 Scope of the methodology — what fits and what does not

**Region scope.** All ten tickers in the backtest are US-listed. The weekend we predict is the US weekend. The factor-switchboard mapping (ES/NQ/GC/ZN/BTC) privileges US session data. We make no claim about the generalisation of the coverage-inversion primitive to tokenized-JP equities, tokenized-EU equities, or commodities whose primary discovery venue is not a US exchange. A multi-region replication is future work (§10.5).

**Asset-class scope.** The methodology requires a *continuous off-hours information set* — a public, free, sub-daily price signal that is observably correlated with the closed-market underlier. Tokenized US equities have this (E-mini index futures + VIX), tokenized gold has it (gold futures + GVZ), tokenized US treasuries have it (10Y T-note futures + MOVE), and most major FX pairs have it (overseas-session prices). Tokenized credit has it through CDS spreads and index volatility, modulo data licensing. We claim the methodology generalises to any RWA class with such a signal.

What the methodology does *not* fit, and we do not claim:

- **Real estate.** No continuous off-hours information set exists; NAV updates are discrete and infrequent. The closed-market problem here is structurally different (no signal, not "stale signal") and requires a different methodology.
- **Illiquid commodities.** Some agricultural and specialty commodities have futures markets but those markets are discontinuous or thinly traded. The factor regression's $\hat\beta$ would be unstable.
- **Instruments with primarily NAV-based pricing.** Money-market-style tokens whose price is administratively set rather than market-observed have no "fair value" question to calibrate against.

`docs/methodology_scope.md` in the artifact released with this paper carries the per-class fit/no-fit table that protocol integrators and risk teams can use as a quick filter. The broader claim of §1 — that calibration-transparent risk reporting is the missing infrastructure layer for responsible institutional-scale RWA onboarding — applies to the substantial subset of RWA classes within scope, and explicitly does *not* claim coverage for classes outside it.

## 9.11 On-chain tokenized-stock prices as an unused signal

Cong et al. [cong-tokenized-2025] document that off-hour returns on tokenized stocks *anticipate*, rather than amplify, subsequent Monday opens. Their finding implies that the contemporaneous on-chain xStock price during a closed-market interval already aggregates a non-trivial part of the weekend information set. Our base forecaster does not read this signal: $\hat P$ is a function of off-chain factor returns and a per-symbol volatility index only. A natural competing baseline — and one a reviewer is likely to raise — is "use the on-chain xStock TWAP as the point estimate."

We do not report this comparison in the present paper for one reason: data history. Tokenized-equity primary venues on Solana launched in mid-2025, providing on the order of 30 weekends of on-chain price data through the cutoff of this evaluation. A stable per-(symbol, regime) Kupiec test requires on the order of 150 observations; per-regime Christoffersen requires more. The xStock-anchored forecaster is documented as a v2 deliverable in `docs/v2.md` §V2.1 (the *F_tok* forecaster, gated on the V5 on-chain tape that began continuous capture on 2026-04-24) and will be reported in the v2 paper once data history supports OOS validation. The omission is a deliberate evaluation-power choice, not an architectural exclusion.

## 9.12 MEV and consumer-experienced coverage

The realised coverage figures reported in §6 are computed against the realised Monday opening reference price $P_t$ on the underlying venue. Daian et al. [flashboys-2] document that on-chain transaction ordering is adversarial: searchers and validators compete to reorder transactions for profit, and band-edge events are economically attractive targets. A consumer who reads the Soothsayer band at on-chain mid and then transacts at a worse price (because of front-running, sandwich attacks, or block-builder reordering) experiences an *effective* coverage rate that may differ from our reported coverage rate near the band edge.

We do not currently measure this gap. The infrastructure to do so requires (i) a Solana tape with mempool-or-bundle granularity (the V5 forward-cursor tape, started 2026-04-24, supplies this but with insufficient history at submission), (ii) a model of consumer transaction behaviour at band-edge thresholds, and (iii) a Jito-bundle reconstruction of bundled flow. The MEV-adjusted coverage measurement is documented as v2 work in `docs/v2.md` §V2.3. The present paper's coverage claim should therefore be read at face value — coverage of $P_t$ at the venue — not as a guarantee on consumer-experienced execution near the band edge.

## 9.13 What is not a limitation

For completeness, we enumerate two concerns that do *not* apply to the coverage-inversion primitive as specified:

- **Oracle manipulation.** Coverage transparency is orthogonal to integrity. Soothsayer is designed to be read alongside an adversarially-robust feed, not as its replacement.
- **Latency.** The serving-time Oracle is a five-line lookup against the per-Friday Mondrian artefact (`mondrian_artefact_v2.parquet`) plus 20 module-level constants; byte-for-byte verified in Rust; nothing in the coverage-inversion mechanism requires a live heavy-weight forecast computation. Performance budgeting is a §8 concern, not a correctness one.

---

These limitations are disclosures, not retractions. Each has a concrete follow-up in §10.
