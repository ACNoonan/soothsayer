# §9 — Limitations (draft)

This section enumerates the assumptions under which the claims of §3.4 hold, the failure modes the backtest exposed, and the domain boundaries outside which we make no assertion. Most items here correspond to explicit deferrals rather than unknown unknowns; each points forward to §10 (Future Work) with a concrete follow-up.

## 9.1 The high-$\tau$ tail ceiling

At consumer target $\tau = 0.99$, the served Oracle delivered $97.2\%$ realised coverage on the OOS slice — a $1.8$pp shortfall and a Kupiec rejection ($p_{uc} < 0.001$). The 99% band is structurally limited by the calibration window size. Our per-(symbol, regime) log-log residual model is fit on a rolling $156$-weekend window; reliably resolving the $1\%$ tail of that distribution requires more observations than any one bucket carries. The pooled-surface fallback partially mitigates this, but does not eliminate it: the pooled bucket draws on $\sim 600$ observations per regime, which is still tight for 1-in-100 events.

This is not a failure of the coverage-inversion primitive. It is a finite-sample artefact of the empirical quantile estimator. A conformalised upgrade (see §9.4) would report finite-sample coverage bounds instead, at the cost of assumption strength.

## 9.2 Shock-tertile empirical ceiling

The weekend-realised-move distribution has a heavy tail: a realised-move z-score tertile labelled `shock` in our backtest (post-hoc, using $|z| \ge 0.67$ standardised by Friday's 20-day vol) has a structural realised-coverage ceiling of approximately $80\%$ at the nominal $95\%$ claim — because pre-publish information is insufficient to predict those moves. We do not attempt to raise this ceiling; we disclose it. Protocols that accept Soothsayer as a collateral-valuation input should treat shock-tertile tails as explicitly out-of-model and either apply their own exogenous widening (e.g., a circuit breaker tied to overnight futures moves) or reduce collateralisation during periods where shock-tertile entry is plausible.

The ceiling is reported transparently in every `PricePoint` diagnostic via the calibration receipt: the served $q$ carries the historical realised coverage at its bucket, and a consumer can read off the tail risk before using the band.

## 9.3 Stationarity assumption behind P2

Claim P2 (conditional empirical coverage, §3.4) is an *empirical* statement. It holds under the assumption that the conditional distribution $P_t \mid (\mathcal{F}_t,\ \rho(\mathcal{F}_t) = r)$ is approximately stationary across $\mathcal{T}_\text{hist}$ and the target deployment horizon. This assumption is plausibly violated in at least three ways:

- **Structural breaks in microstructure.** The 2020 COVID shock, the 2022 rate regime, and the introduction of 24/7 tokenized-stock trading on Solana in mid-2025 each plausibly shifted the conditional distribution. Our 2023+ OOS slice includes the 2022-→-2023 regime transition; it does not cover a comparable future break.
- **Regime-labeler drift.** $\rho$ uses a trailing 252-trading-day VIX percentile to tag `high_vol`; a persistent rise in baseline vol (e.g., 2022-like) shifts the threshold endogenously. This is a feature for rolling deployment but can defeat the cross-regime fairness of the `high_vol`-vs-`normal` comparison.
- **Factor-switchboard drift.** MSTR's factor mapping pivots from ES=F to BTC-USD on 2020-08-01 (the BTC-proxy transition). This is a hand-coded pivot in `FACTOR_BY_SYMBOL`. A second pivot — e.g., if MSTR's BTC sensitivity decays — would require a re-fit.

A conformalised variant (§9.4 and §10) would upgrade P2's guarantee from asymptotic-under-stationarity to finite-sample-under-exchangeability; the latter is strictly weaker and measurable.

## 9.4 Heuristic per-target calibration buffer

The served Oracle applies an empirical buffer to the consumer target before surface inversion, persisted in `BUFFER_BY_TARGET` and looked up by linear interpolation off-grid. The deployed values are $\{\tau\!=\!0.68 \to 0.045,\ \tau\!=\!0.85 \to 0.045,\ \tau\!=\!0.95 \to 0.020,\ \tau\!=\!0.99 \to 0.005\}$, each chosen as the smallest buffer satisfying realised coverage within $0.5$pp of target with both Kupiec $p_{uc} > 0.10$ and Christoffersen $p_{ind} > 0.05$ on the OOS 2023+ slice (`reports/v1b_buffer_tune.md`). The buffer is *load-bearing* for the OOS Kupiec pass at every $\tau \le 0.95$; without it, the surface inversion delivers $92.2\%$ realised at target $0.95$ and Kupiec rejects.

Three weaknesses of this choice:

1. **Sample-size-one buffer.** Each per-target buffer is fit on one train/test split. A walk-forward sequence of splits would produce a distribution of buffers, with its own standard error. We commit to this re-measurement as part of any rolling calibration-surface rebuild.
2. **Per-target schedule, not a continuous function.** Off-grid targets interpolate linearly between the four anchor points. A reviewer might prefer a continuous function fit (e.g., spline) on a finer sweep grid; we have not done that comparison.
3. **No finite-sample guarantee.** The buffer is a heuristic, not a theorem. We tested vanilla split-conformal (operationally equivalent at our calibration size), Barber et al. nexCP-style recency-weighted conformal at two half-lives, and a block-recency baseline at two windows; all three under-corrected the OOS gap relative to the per-target heuristic, with bootstrap 95% CIs that exclude zero. The full evidence is in `reports/v1b_conformal_comparison.md`. The conformal upgrade therefore is *not* an obvious win on this data; it is reserved as a v2 direction subject to either a finer claimed-coverage grid (above $0.995$, removing the structural ceiling) or a multi-split walk-forward evaluation that distinguishes drift from sampling noise.

The choice to ship a per-target heuristic now and re-evaluate conformal in v2 is disclosed, not evaded. The `calibration_buffer_applied` field on every `PricePoint` is the first-class receipt — the consumer sees exactly which buffer was applied to their served band.

## 9.5 The earnings regressor is a disclosure, not a contribution

The `F1_emp_regime` base forecaster includes a 0/1 `earnings_next_week` flag among its log-log regressors. The ablation in §7 shows that this regressor has no detectable effect on coverage or sharpness at our sample size ($\Delta\text{cov} = 0.0$pp, CI $[-0.1, +0.1]$; $\Delta\text{sharp}\% = +0.1\%$, CI $[-0.2, +0.5]$). The regressor was included in anticipation of earnings-week volatility premia; at $N = 5{,}986$ and a weekly-granularity flag it is not detectable.

We retain it for two reasons: (a) it is part of the audit receipt — removing it would silently change the surface, and we consider surface stability across documented methodology a product property; (b) a future iteration may replace the weekly flag with a finer event-granularity dataset (earnings date + estimated move), in which case the structural slot is already in place. A paper reviewer who prefers the minimal model should feel free to read the ablation as authorising its removal.

## 9.6 Hybrid regime policy is defended on independence, not mean coverage

In-sample evidence (matched-realised-coverage sharpness dominance of F0 in `high_vol`) motivated the hybrid serving policy. Out-of-sample, the hybrid's mean-coverage effect is statistically indistinguishable from F1-everywhere ($\Delta\text{cov} = -0.1$pp, CI $[-0.7, +0.4]$). What the hybrid *does* buy on OOS is Christoffersen independence: without it, F1 + buffer has clustered violations ($p_\text{ind} = 0.033$, rejected); with it, violations are not clustered ($p_\text{ind} = 0.086$). This is a real and institutionally-meaningful property — clustered violations are precisely the failure mode that model-risk-management frameworks target — but it is a *different* property than the one we originally pitched the hybrid on. The honest framing used in this paper is the independence-based one.

## 9.7 No live deployment window

The empirical claims of §6 are backtested, not live. As of the submission of this paper, the shipped Rust serving layer and on-chain publisher program (§8) are functionally verified (byte-for-byte Python↔Rust parity on 105 test cases) but have not run as a live price feed consumed by a production protocol. A live window — with real integrators, real consumers, and an adversarial environment — will exhibit modes that a backtest cannot. The paper should be read as *validation of a calibration primitive on historical data*, not as a production-quality assurance.

## 9.8 No numerical incumbent benchmark

We do not report a systematic numerical comparison of Soothsayer's served bands against Pyth, Chainlink Data Streams, or RedStone Live on a matched evaluation window. The conceptual comparison in §1.1 (stale-hold, dispersion CI, undisclosed methodology) is qualitative; a numerical benchmark would require either access to incumbent-internal historical bands or a reconstruction of incumbent values from on-chain feeds. Our team has partial Chainlink v10 / v11 reconstruction infrastructure in-repo that was used for a sanity-check comparison (reports/v1_chainlink_bias.md) but not at the rigor required for a research-paper-grade benchmark. We flag this as future work (§10) — specifically, an AFT-community-facing public comparator dashboard computed on a common historical window.

## 9.9 No optimal liquidation-policy benchmark

The paper validates an oracle interface, not a lending policy. We do not report a decision-theoretic benchmark of "what target $\tau$ should a protocol choose?" or "does a regime-demoted liquidation threshold dominate a flat threshold once portfolio weights and protocol losses are specified?" Answering those questions requires at least three ingredients absent from the present evaluation: (i) an explicit distribution over borrower-book LTV weights rather than a pure coverage metric, (ii) a protocol-specific cost model distinguishing unnecessary liquidation, unnecessary caution, and missed liquidation / bad debt, and (iii) a declared semantics for what counts as the correct action under realised prices. Without those ingredients, a claim of optimal liquidation-policy default would be stronger than the evidence we present here.

## 9.10 Single market-region coverage

All ten tickers in the backtest are US-listed. The weekend we predict is the US weekend. The factor-switchboard mapping (ES/NQ/GC/ZN/BTC) privileges US session data. We make no claim about the generalisation of the coverage-inversion primitive to tokenized-JP equities, tokenized-EU equities, or commodities whose primary discovery venue is not a US exchange. A multi-region replication is future work.

## 9.11 On-chain tokenized-stock prices as an unused signal

Cong et al. [cong-tokenized-2025] document that off-hour returns on tokenized stocks *anticipate*, rather than amplify, subsequent Monday opens. Their finding implies that the contemporaneous on-chain xStock price during a closed-market interval already aggregates a non-trivial part of the weekend information set. Our base forecaster does not read this signal: $\hat P$ is a function of off-chain factor returns and a per-symbol volatility index only. A natural competing baseline — and one a reviewer is likely to raise — is "use the on-chain xStock TWAP as the point estimate."

We do not report this comparison in the present paper for one reason: data history. Tokenized-equity primary venues on Solana launched in mid-2025, providing on the order of 30 weekends of on-chain price data through the cutoff of this evaluation. A stable per-(symbol, regime) Kupiec test requires on the order of 150 observations; per-regime Christoffersen requires more. The xStock-anchored forecaster is documented as a v2 deliverable in `docs/v2.md` §V2.1 (the *F_tok* forecaster, gated on the V5 on-chain tape that began continuous capture on 2026-04-24) and will be reported in the v2 paper once data history supports OOS validation. The omission is a deliberate evaluation-power choice, not an architectural exclusion.

## 9.12 MEV and consumer-experienced coverage

The realised coverage figures reported in §6 are computed against the realised Monday opening reference price $P_t$ on the underlying venue. Daian et al. [flashboys-2] document that on-chain transaction ordering is adversarial: searchers and validators compete to reorder transactions for profit, and band-edge events are economically attractive targets. A consumer who reads the Soothsayer band at on-chain mid and then transacts at a worse price (because of front-running, sandwich attacks, or block-builder reordering) experiences an *effective* coverage rate that may differ from our reported coverage rate near the band edge.

We do not currently measure this gap. The infrastructure to do so requires (i) a Solana tape with mempool-or-bundle granularity (the V5 forward-cursor tape, started 2026-04-24, supplies this but with insufficient history at submission), (ii) a model of consumer transaction behaviour at band-edge thresholds, and (iii) a Jito-bundle reconstruction of bundled flow. The MEV-adjusted coverage measurement is documented as v2 work in `docs/v2.md` §V2.3. The present paper's coverage claim should therefore be read at face value — coverage of $P_t$ at the venue — not as a guarantee on consumer-experienced execution near the band edge.

## 9.13 What is not a limitation

For completeness, we enumerate two concerns that do *not* apply to the coverage-inversion primitive as specified:

- **Oracle manipulation.** Coverage transparency is orthogonal to integrity. Soothsayer is designed to be read alongside an adversarially-robust feed, not as its replacement.
- **Latency.** The serving-time Oracle is a read against persisted artefacts (`v1b_bounds.parquet` plus two CSV surfaces); byte-for-byte verified in Rust; nothing in the coverage-inversion mechanism requires a live heavy-weight forecast computation. Performance budgeting is a §8 concern, not a correctness one.

---

These limitations are disclosures, not retractions. Each has a concrete follow-up in §10.
