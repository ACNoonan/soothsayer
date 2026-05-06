# §9 — Limitations

This section enumerates the assumptions under which the claims of §3.4 hold for M6, the failure modes the backtest exposed, and the domain boundaries outside which we make no assertion. The strongest residual issues are (i) cross-sectional within-weekend common-mode residual (§9.4); (ii) the σ̂ selection procedure's multi-test exposure (mitigated in §7.3 but disclosed here); and (iii) the contraction — but not full closure — of the OOS-tuning provenance disclosure (§9.3).

## 9.1 Shock-tertile empirical ceiling

The shock realised-move tertile ($|z| \ge 0.67$ standardised by Friday's 20-day vol; $n = 632$ in the 2023+ OOS slice, §6.3.2) realises $87.8\%$ coverage on M6's deployed band at the nominal $\tau = 0.95$ claim — a deviation from nominal whose mechanism (cross-sectional within-weekend common-mode, §6.3.6 / §9.4) is identified and whose operational handle (the $k_w$ reserve-guidance threshold of §6.3.4) is what protocol consumers should monitor in real time. Per-symbol σ̂ standardisation does not reach this ceiling because the failure mode is not per-symbol scale; band half-width is approximately flat across tertiles ($365$–$380$ bps), so the band does not widen in shock periods — it just misses more often.

The §6.3.4 joint-tail empirical distribution and the §6.3.5 worst-weekend vignette (2024-08-05 BoJ unwind, $k_w = 10$ at $\tau = 0.85$) make this disclosure operationally addressable: a consumer monitoring $k_w$ in real time would have seen the August 5 weekend exceed the deployment-time 99th percentile ($k = 7$ at $\tau = 0.85$) by the Monday-open print, well in advance of any liquidation processing window. Reserve-guidance threshold $k^\ast = 5$ at $\tau = 0.85$ (or $k^\ast = 3$ at $\tau = 0.95$) carries 0/24 sub-period × threshold-convention stability rejections (§6.3.4); a circuit breaker that pauses borrowing/lending when $k_w$ crosses $k^\ast$ would fire on this exact weekend before liquidations are processed. The empirical $k_w$ distribution is the right operational signal precisely because it captures the cross-sectional common-mode that per-symbol coverage cannot. The ceiling is reported in every `PricePoint` diagnostic.

## 9.2 Stationarity assumption — sub-period evidence (positive)

P2 holds under the assumption that $P_t \mid (\mathcal{F}_t,\ \rho = r,\ s)$ is approximately stationary across $\mathcal{T}_\text{hist}$ and the deployment horizon. M6's EWMA $\hat\sigma_s(t)$ provides *partial adaptive scaling per symbol* (the §6.8 simulation evidence demonstrates σ̂ tracks DGP-C drift and DGP-D structural breaks with a half-life-bounded lag), but the conditional-distribution stationarity of the *standardised* score is still assumed.

Empirical evidence on this assumption is positive. M6's pooled OOS calibration at $\tau = 0.95$ holds across the 2023, 2024, 2025, and 2026-YTD calendar sub-periods (§6.3.3): Kupiec $p \ge 0.054$ in every cell; realised range $0.942$–$0.967$ across four years that span SVB / banking-stress 2023, the 2024 rate-cut transition, the 2025 tokenisation-launch year, and the post-launch 2026-YTD slice. Across the full 16-cell (sub-period × $\tau$) grid M6 carries 2 Kupiec rejections — both *over-coverage* in 2025 (not the under-coverage failure mode that warrants a deployment alarm). Christoffersen lag-1 independence is not rejected in any of the 16 cells.

The assumption may still be violated in three ways the sub-period grid cannot pre-empt: (i) **structural breaks** beyond the panel horizon (a future regime as different from 2014–2026 as 2026 is from 2014) — σ̂ adapts in $\le 26$ weekends per symbol per simulation evidence; (ii) **regime-labeler drift** ($\rho$ uses a trailing 252-day VIX percentile; persistent rises shift the threshold endogenously); (iii) **factor-switchboard drift** (MSTR pivots from ES=F to BTC-USD on 2020-08-01; a second pivot would require re-fit). A conformalised variant (§10) would upgrade P2 from asymptotic-under-stationarity to finite-sample-under-exchangeability.

## 9.3 OOS-tuned $c(\tau)$ provenance — substantially contracted

This is the load-bearing disclosure. M6's deployment carries 16 scalars: 12 trained per-regime quantiles + 4 OOS-fit $c(\tau)$ + 0 walk-forward (the $\delta(\tau)$ schedule is identically zero). Of the 4 OOS-fit $c(\tau)$ scalars, three are essentially identity:

$$c(\tau) \;=\; \{0.68\!:\!1.000,\;0.85\!:\!1.000,\;0.95\!:\!1.079,\;0.99\!:\!1.003\}.$$

**Only $c(0.95) = 1.079$ carries meaningful OOS information** (a 7.9% widening at the headline anchor). The §6.3.3 split-date sensitivity at $\tau = 0.95$ holds realised coverage within $\pm 0.05$pp across {2021, 2022, 2023, 2024} OOS-anchors, with Christoffersen passing every cell (§7.3 also shows the K=26 σ̂ baseline that motivated the EWMA HL=8 promotion did *not* clear those Christoffersen cells, lending operational meaning to the σ̂ choice). The forward-tape harness (§6.7) closes the residual contamination by carrying the deployment artefact onto truly held-out weekends as they accumulate; with $\geq 13$ forward weekends a §6.7 update will push the `c(0.95)` provenance disclosure further from "OOS-fit on a single 2023+ slice with three independent sensitivity checks" toward "OOS-fit + held-out forward-tape re-validation."

Three of 16 deployment scalars carry meaningful OOS-fit information ($c(0.95)$ at 1.079; $c(0.99)$ near-identity at 1.003; $c(\tau \le 0.85)$ both identity). This is a load-bearing concession but a contained one. The `calibration_buffer_applied` field carries $\delta(\tau)$ as a first-class receipt; diagnostics carry $c(\tau)$ and $q_\text{eff}$.

## 9.4 The residual Berkowitz / DQ rejection

The served band is *per-anchor calibrated* (Kupiec passes at every $\tau$, Christoffersen passes at every served $\tau$ on the 2023 split, §7.3 confirms passes at all 16 split-date cells under EWMA HL=8) but *not full-distribution calibrated* (pooled Berkowitz on M6's PITs rejects; pooled DQ at $\tau = 0.95$ also rejects).

**Localising the residual.** §6.3.6 decomposes the lag-1 alternative: the AR(1) signal lives in the *cross-sectional within-weekend* ordering ($\hat\rho_\text{cross} = 0.354$, $p < 10^{-100}$), not the temporal-within-symbol ordering ($\hat\rho_\text{time} = -0.032$, $p = 0.18$). σ̂ standardisation operates *within* a symbol's history, not *across* symbols within a weekend, so the M6 architecture is incapable of reaching this residual. A vol-tertile sub-split of `normal` regime (5 cells) leaves Berkowitz LR essentially unchanged ($170 \to 172$) while widening $\tau = 0.95$ band by $9\%$ — finer regime granularity is not the lever (§6.3.6).

**Per-symbol Berkowitz rejection localisation.** The residual symbols rejecting Berkowitz at $\alpha = 0.01$ are TLT (LR $= 16.7$) and TSLA (LR $= 13.5$) — both trace to cross-sectional common-mode rather than per-symbol scale. The §6.3.4 joint-tail empirical distribution turns the Berkowitz rejection into a measurable, reportable shape (variance overdispersion $2.39$ at $\tau = 0.95$; $P(k_w \ge 3) = 5.20\%$ vs binomial $1.15\%$), and the §6.3.4 reserve-guidance threshold ($k^\ast = 3$) gives a consumer an operational handle that no parametric calibration test would provide.

A protocol consuming Soothsayer at a single $\tau$ on a regime-pooled cell is served by the per-anchor pooled guarantee plus the per-symbol Kupiec evidence; one wanting full-distribution calibration must accept the cross-sectional common-mode residual or wait for the §10 candidate architectures (the cross-sectional partial-out track, gated on a Friday-observable $\bar r_w$ predictor, currently rejected by the W8 prototype's OOS $R^2 < 0.4$).

## 9.5 Forward-tape held-out evidence — operational, accumulating

A content-addressed frozen artefact (`data/processed/lwc_artefact_v1_frozen_20260504.json`, freeze date 2026-05-04) is being evaluated weekly via launchd-driven harness against forward weekends as they accumulate (§6.7). The shipped Rust serving layer remains M5-only with M6's wire-format slot reserved (§4.7); the M6 Rust port is gated to a productionisation milestone independent of this paper's empirical content. Forward-tape evidence is the cleanest possible held-out coverage statement; it is not yet a live integrator-consumed price feed. **Status at submission:** $N = $ [N TBD; first non-stub forward-tape report ETA 2026-05-12; this section's claim must be updated to cite the latest forward-tape report immediately before submission]. A live integrator window — devnet-then-mainnet against a real protocol — would close the external-validity gap; it would not by itself make Berkowitz pass.

## 9.6 Out-of-scope comparators and consumer-experienced effects

**Partial-only numerical incumbent benchmark.** §6.5 reports the partial comparison against regular Pyth (265 obs), Chainlink Data Streams v10 + v11 (87 obs frozen panel), and RedStone Live (12 obs forward tape). The three caveats (wide sample CIs, large-cap normal-regime composition, consumer-supplied wrap multipliers) prevent reading any matched-bandwidth observation as a head-to-head loss. Pyth Pro / Blue Ocean is excluded on access and window grounds. RedStone's forward-cursor tape will become a paper-grade comparator once a multi-symbol weekend sample accumulates beyond the 30-day retention cap.

**Endpoint vs path coverage.** §6.6 quantifies the gap on a 24/7 stock-perp slice ($n = 118$ symbol-weekends). The $\tau = 0.95$ endpoint-vs-path gap on the perp-listed subset is $+16.1$ pp under M6 — what an honestly-calibrated endpoint band exhibits on a sample whose intra-weekend variance is structurally larger than its endpoint variance. After three robustness checks the residual genuine-shortfall band is approximately $9$–$15$ pp at $\tau = 0.95$ (basis-normalisation $11.0$ pp; volume-floor filter at $\geq 1$ contract $9.5$ pp on $n=63$; 15-minute sustained-crossing $14.4$ pp), concentrated in `normal` weekends and approximately closed by stepping up to $\tau = 0.99$ (residual $+7.6$ pp). The served contract remains the endpoint claim.

**MEV and execution-aware coverage.** A consumer transacting at a worse price than the band's mid (front-running, sandwich, block-builder reordering) experiences an *effective* coverage that may differ from §6.6's perp/on-chain path coverage near band edges. Measuring this requires Solana mempool-or-bundle granularity plus a consumer-behaviour model; documented as next-generation work (§10.1).

## 9.7 No optimal liquidation-policy benchmark

The paper validates an oracle interface, not a lending policy. We do not report a decision-theoretic benchmark of "what target $\tau$ should a protocol choose?" Answering requires three ingredients absent here: (i) an explicit borrower-book LTV distribution; (ii) a protocol-specific cost model distinguishing unnecessary liquidation, unnecessary caution, and missed liquidation / bad debt; (iii) a declared semantics for what counts as the correct action under realised prices. Paper 3 addresses this.

## 9.8 Scope of the methodology

**Region scope.** All ten tickers are US-listed; the weekend predicted is the US weekend. The factor switchboard privileges US session data. We make no claim about generalisation to tokenised-JP or tokenised-EU equities.

**Asset-class scope.** The methodology requires a *continuous off-hours information set* — a public, free, sub-daily price signal correlated with the closed-market underlier. Tokenised US equities have this (E-mini futures + VIX), tokenised gold has it (gold futures + GVZ), tokenised US treasuries have it (10Y T-note futures + MOVE), and most major FX pairs have it. Tokenised credit has it through CDS spreads. Out of scope: real estate (no continuous off-hours signal), illiquid commodities (futures discontinuous or thin), and instruments with primarily NAV-based pricing. `docs/methodology_scope.md` carries the per-class fit/no-fit table.

**Newly-listed symbol admission.** The σ̂ warm-up rule (≥8 past observations) sets an empirical floor; the §6.8 sample-size sweep extends this to a panel-admission threshold of $N \geq 200$ weekends under regime-switching DGPs (the production threshold) and $N \geq 80$ under stationary / drift / structural-break DGPs. HOOD's empirical $N \approx 218$ sits inside this band. A protocol admitting a symbol with fewer than 200 weekends of history should treat the per-symbol claim as deferred until the panel accumulates.

## 9.9 Non-claims

Three concerns that do *not* apply, plus one known data-gated gap:

- **Oracle manipulation.** Coverage transparency is orthogonal to upstream-feed integrity. Soothsayer ingests upstream price/oracle signals (Pyth, Chainlink, RedStone, Kamino-Scope, public-market data via Yahoo / Kraken) and republishes them as a calibrated band; the coverage claim is conditional on the integrity of those upstream feeds, and this primitive is intended to be deployed alongside, not in place of, an adversarially-robust price feed.
- **Latency.** The serving-time Oracle is a five-line lookup; nothing in the coverage-inversion mechanism requires a live forecast computation.
- **σ̂ rule optimality.** The §7.3 selection procedure under multi-test correction does not statistically distinguish the five σ̂ variants; the EWMA HL=8 promotion rests on Gate 3 (bootstrap CI on width) plus the held-out forward-tape re-validation. We do not claim the σ̂ rule is optimal among all locally-weighted variants; a finer half-life sweep, alternative weight kernels, or hybrid rules are open future work.
- **On-chain xStock TWAP not consumed.** Cong et al. [cong-tokenized-2025] document off-hour returns on tokenised stocks anticipate Monday opens. The base forecaster does not read this; the V5 forward-cursor tape supplies the data but only ~30 weekends of post-launch history exist (§10.1).

These limitations are disclosures, not retractions. Each has a concrete follow-up in §10.
