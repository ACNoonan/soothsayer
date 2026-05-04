# §9 — Limitations

This section enumerates the assumptions under which the claims of §3.4 hold, the failure modes the backtest exposed, and the domain boundaries outside which we make no assertion. Most items correspond to explicit deferrals; each points forward to §10. The strongest open issues — Berkowitz / DQ rejections, no live deployment window, and the OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedule provenance — are the empirical map of what a v3 system should improve.

## 9.1 Shock-tertile empirical ceiling

The weekend-realised-move distribution has a heavy tail: a realised-move z-score tertile labelled `shock` ($|z| \ge 0.67$ standardised by Friday's 20-day vol) realises $87.2\%$ coverage on the deployed band at the nominal $\tau = 0.95$ claim ($n = 632$ shock-tertile weekends in the 2023+ OOS slice; §6.3 sub-table) — materially below nominal but $\sim 7$pp above the conservative $80\%$ figure prior versions of this paper reported. The structural mechanism is unchanged: pre-publish information is insufficient to predict shock-tertile moves, and band half-width is approximately flat across tertiles ($340$–$369$ bps), so the band does not widen in shock periods — it just misses more often. We disclose, not raise, this ceiling. Protocols accepting Soothsayer should treat shock-tertile tails as explicitly out-of-model and either apply exogenous widening (e.g., a circuit breaker tied to overnight futures moves) or reduce collateralisation when shock-tertile entry is plausible. The ceiling is reported in every `PricePoint` diagnostic.

## 9.2 Stationarity assumption behind P2

P2 holds under the assumption that $P_t \mid (\mathcal{F}_t,\ \rho = r)$ is approximately stationary across $\mathcal{T}_\text{hist}$ and the deployment horizon. Plausibly violated in three ways: (i) **structural breaks** (2020 COVID, 2022 rate regime, mid-2025 24/7 tokenised-stock launch); (ii) **regime-labeler drift** ($\rho$ uses a trailing 252-day VIX percentile; persistent rises shift the threshold endogenously); (iii) **factor-switchboard drift** (MSTR pivots from ES=F to BTC-USD on 2020-08-01; a second pivot would require re-fit). A conformalised variant (§10) would upgrade P2 from asymptotic-under-stationarity to finite-sample-under-exchangeability.

## 9.3 OOS-tuned $c(\tau)$ + $\delta(\tau)$ schedules

This is the load-bearing disclosure. Deployed values: $c \in \{1.498, 1.455, 1.300, 1.076\}$, $\delta \in \{0.05, 0.02, 0.00, 0.00\}$ at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$. Three weaknesses:

1. **OOS-fit on a single slice (substantially closed by sensitivity analyses).** Each $c(\tau)$ was fit on the pooled 2023+ slice. Three independent provenance checks:
   - **6-split walk-forward** (§7.2.3) at $\tau = 0.95$: mean $c = 1.252$, $\sigma = 0.056$; deployed $c(0.95) = 1.300$ is $\sim 1\sigma$ conservative.
   - **Split-date sensitivity** (§6.3) at OOS-anchors {2021, 2022, 2023, 2024}: realised $\tau = 0.95$ coverage is $\{0.9507, 0.9502, 0.9503, 0.9504\}$; Kupiec $p > 0.86$ at every anchor; mean half-width within $\pm 5\%$ of the deployed $354.6$ bps.
   - **Leave-one-symbol-out CV** (§6.3) at $\tau = 0.95$: 8 of 10 LOSO bands within $\pm 5$pp of nominal; mean $0.943$, std $0.076$. The schedule is moderately fragile to held-out heavy-tail tickers (MSTR $0.786$, HOOD $0.856$, TSLA $0.879$) — a symptom of the §6.4.1 bimodal calibration error — and over-covers when well-behaved tickers are held out (SPY/TLT $1.000$).

   The headline does not depend on the 2023-01-01 split anchor; the LOSO read sharpens the §9.4 disclosure rather than weakens it.

2. **Per-anchor schedule, not a continuous function.** Off-grid targets interpolate linearly; a continuous (spline) fit comparison was not run.
3. **No finite-sample guarantee on the $c(\tau)$ overshoot.** A full-distribution conformal upgrade would replace the empirical guarantee with a finite-sample exchangeability-based one (§10.2).

The `calibration_buffer_applied` field carries $\delta(\tau)$ as a first-class receipt; diagnostics carry $c(\tau)$ and $q_\text{eff}$.

## 9.4 The Berkowitz / DQ rejections

The served band is *per-anchor calibrated* (Kupiec passes at every $\tau$, Christoffersen passes at $\tau \ge 0.85$) but *not full-distribution calibrated* (Berkowitz LR $= 173.1$; DQ at $\tau = 0.95$ $p = 5.7 \times 10^{-6}$).

**Localising the rejection.** §6.3.1 decomposes the lag-1 alternative: the AR(1) signal lives in the *cross-sectional within-weekend* ordering ($\hat\rho_\text{cross} = 0.354$, $p < 10^{-100}$), not the temporal-within-symbol ordering ($\hat\rho_\text{time} = -0.032$, $p = 0.18$). A vol-tertile sub-split of `normal` regime (5 cells) leaves Berkowitz LR essentially unchanged ($173 \to 175$) while widening $\tau = 0.95$ band by $9\%$ — finer regime granularity is not the lever. The residual is common-mode within a weekend that the $(\rho, s)$ factor switchboard does not fully partial out, and a single $(r, \tau)$-keyed multiplier mis-allocates across heterogeneous symbols (§6.4.1's bimodal pattern). M5 ships with these rejections disclosed; §10.4 enumerates the v3 candidates that target each.

**Per-symbol disclosure.** Per-symbol Berkowitz / Kupiec on M5 OOS PITs is *bimodal* (§6.4.1): SPY/QQQ/GLD/TLT/AAPL reject from variance compression (bands too wide, $0$–$1\%$ violation rate at $\tau = 0.95$); TSLA/HOOD/MSTR reject from variance expansion (bands too narrow, $11$–$16\%$ violation rate); NVDA, GOOGL pass. **HOOD specifically fails per-symbol Kupiec at $\tau \in \{0.68, 0.85, 0.95\}$** (violation rate $13.9\%$ at $\tau = 0.95$ vs nominal $5\%$); HOOD passes at $\tau = 0.99$ (violation rate $2.3\%$, $p = 0.138$). Cold-start heavy-tail symbols are the load-bearing per-symbol failure mode: HOOD has the shortest history (~73 train rows), and the deployed schedule is fit on a panel where heavy-tail tickers drive the conformity quantile. Production deployments that face HOOD-equivalent newly-listed tickers should treat the per-symbol claim as deferred until V3.2's rolling rebuild and the §10.4 per-symbol-calibration candidates land.

A protocol consuming Soothsayer at a single $\tau$ on a regime-pooled cell is served by the per-anchor pooled guarantee; one wanting per-symbol or full-distribution calibration must accept the disclosed residual or wait for v3.

## 9.5 No live deployment window

The empirical claims of §6 are backtested, not live. The shipped Rust serving layer and on-chain publisher (§8) are functionally verified (90/90 parity) but have not run as a live price feed consumed by a production protocol. A live window — with real integrators, real consumers, an adversarial environment — will exhibit modes a backtest cannot. The paper should be read as *validation of a calibration primitive on historical data*, not production-quality assurance. A live window would close the external-validity gap; it would not by itself make Berkowitz or DQ pass.

## 9.6 Out-of-scope comparators and consumer-experienced effects

**Partial-only numerical incumbent benchmark.** §6.5 reports the partial comparison against regular Pyth (265 obs), Chainlink Data Streams v10 + v11 (87 obs frozen panel), and RedStone Live (12 obs forward tape). The three caveats (wide sample CIs, large-cap normal-regime composition, consumer-supplied wrap multipliers) prevent reading any matched-bandwidth observation as a head-to-head loss. Pyth Pro / Blue Ocean is excluded on access and window grounds. RedStone's forward-cursor tape will become a paper-grade comparator once a multi-symbol weekend sample accumulates beyond the 30-day retention cap.

**Endpoint vs path coverage.** §6.6 quantifies the gap on a 24/7 stock-perp slice ($n = 118$ symbol-weekends): at $\tau = 0.95$, the raw perp-path gap is $14.4$pp, decomposing after three robustness checks to a residual ${\sim}7$–$10$pp of genuine intra-weekend shortfall, concentrated in `normal` weekends and approximately closed by stepping up to $\tau = 0.99$. The served contract remains the endpoint claim.

**MEV and execution-aware coverage.** A consumer transacting at a worse price than the band's mid (front-running, sandwich, block-builder reordering) experiences an *effective* coverage that may differ from §6.6's perp/on-chain path coverage near band edges. Measuring this requires Solana mempool-or-bundle granularity plus a consumer-behaviour model; documented as v3 work (§10.1's V3.3).

## 9.7 No optimal liquidation-policy benchmark

The paper validates an oracle interface, not a lending policy. We do not report a decision-theoretic benchmark of "what target $\tau$ should a protocol choose?" Answering requires three ingredients absent here: (i) an explicit borrower-book LTV distribution; (ii) a protocol-specific cost model distinguishing unnecessary liquidation, unnecessary caution, and missed liquidation / bad debt; (iii) a declared semantics for what counts as the correct action under realised prices. Paper 3 addresses this.

## 9.8 Scope of the methodology

**Region scope.** All ten tickers are US-listed; the weekend predicted is the US weekend. The factor switchboard privileges US session data. We make no claim about generalisation to tokenised-JP or tokenised-EU equities.

**Asset-class scope.** The methodology requires a *continuous off-hours information set* — a public, free, sub-daily price signal correlated with the closed-market underlier. Tokenised US equities have this (E-mini futures + VIX), tokenised gold has it (gold futures + GVZ), tokenised US treasuries have it (10Y T-note futures + MOVE), and most major FX pairs have it. Tokenised credit has it through CDS spreads. Out of scope: real estate (no continuous off-hours signal), illiquid commodities (futures discontinuous or thin), and instruments with primarily NAV-based pricing. `docs/methodology_scope.md` carries the per-class fit/no-fit table.

## 9.9 Non-claims

Three concerns that do *not* apply, plus one known data-gated gap:

- **Oracle manipulation.** Coverage transparency is orthogonal to integrity. Soothsayer is designed to be read alongside an adversarially-robust feed, not as its replacement.
- **Latency.** The serving-time Oracle is a five-line lookup; nothing in the coverage-inversion mechanism requires a live forecast computation.
- **On-chain xStock TWAP not consumed.** Cong et al. [cong-tokenized-2025] document off-hour returns on tokenised stocks anticipate Monday opens. Our base forecaster does not read this; the V5 forward-cursor tape supplies the data but only ~30 weekends of post-launch history exist (§10.1's V3.1).

These limitations are disclosures, not retractions. Each has a concrete follow-up in §10.
