# Appendix F — Oracle comparator detail and extended diagnostics

This appendix has two halves. The first carries the full methodology behind Table T1's measured findings (§1.2): the Pyth availability and multiplier-ladder measurements, the Chainlink v11 synthetic-marker classification, and the per-venue schema and wire-field evidence summarised in §2. The second carries the extended diagnostics behind §8: the cluster topology of the full-distribution residual, the CUSUM drift bank, the unmeasured execution-side effects, the scope boundaries, and a full-distribution architectural variant that is characterised but not deployed.

## F.1 Scope and attribution

No incumbent oracle surface emits a calibrated coverage band, so a coverage-vs-sharpness comparison against them is not well-defined and is not reported (§2). The measurements below therefore characterise something narrower and precisely stated: what realised coverage a *consumer* receives if they read an incumbent's published fields as a probability statement. Where a multiplier or a scaling is required to reach a target coverage level, that calibration is the consumer's, not the venue's — no venue publishes one, and no venue's stated claim is contradicted by any measurement here.

One exclusion for integrity: the source report behind the Pyth measurements (`reports/v1b_pyth_comparison.md`) also contains a band-width comparison against a v1-era Soothsayer surface. That comparison predates the deployed M6 architecture and is excluded here; only the Pyth-side measurements port.

## F.2 Pyth dispersion field — availability and the multiplier ladder

**Method.** For each (symbol, fri_ts) in the 2024+ subset of the OOS panel (1,200 symbol × weekend pairs across 120 weekends), pull Pyth's (price, conf) via the Hermes Benchmarks API at the nearest publish to Friday 15:55 ET, retrying up to 2 hours back if the queried timestamp falls outside Pyth's publish cadence. For $k \in \{1,\, 1.96,\, 3,\, 5,\, 10,\, 25,\, 50,\, 100,\, 250,\, 500,\, 1000\}$, define the implicit band $[\text{price} - k\cdot\text{conf},\, \text{price} + k\cdot\text{conf}]$ and check whether the realised Monday open lies inside.

**Panel restriction.** The panel is restricted to 2024+ because Pyth's regular-hours US-equity feeds did not exist before then; queries against 2023 timestamps return empty consistently across all tested tickers. The comparison therefore covers the 120 weekends of the 2024+ window within the 2023+ OOS slice. Pyth's documentation describes `conf` as a publisher-dispersion diagnostic, not a probability-of-coverage claim [pyth-conf], so any multiplier $k$ found below is a *consumer-supplied calibration*, not a Pyth-published one.

**Per-symbol availability.**

| symbol | Pyth available rate |
|:---|---:|
| SPY   | 0.692 |
| QQQ   | 0.650 |
| TLT   | 0.592 |
| TSLA  | 0.250 |
| MSTR  | 0.017 |
| GLD   | 0.008 |
| AAPL  | 0.000 |
| GOOGL | 0.000 |
| HOOD  | 0.000 |
| NVDA  | 0.000 |

Pooled availability across 2024+ is **22.1%** (265 of 1,200 attempts had Pyth data within ±2h of Friday close). The coverage analysis below uses the 265-obs subset; on this subset the symbol mix is SPY-, QQQ-, TLT- and TSLA-heavy — large-cap, low-realised-volatility names by composition, which biases the sample toward easier weekends than the pooled OOS slice.

**Pooled realised coverage at increasing k.**

| $k$ | $n$ | realised | mean half-width (bps) |
|---:|---:|---:|---:|
| 1.00   | 265 | 0.049 |    5.6 |
| 1.96   | 265 | 0.102 |   11.0 |
| 3.00   | 265 | 0.155 |   16.8 |
| 5.00   | 265 | 0.242 |   27.9 |
| 10.00  | 265 | 0.434 |   55.9 |
| 25.00  | 265 | 0.800 |  139.7 |
| **50.00**  | **265** | **0.951** |  **279.5** |
| 100.00 | 265 | 0.992 |  559.0 |
| 250.00 | 265 | 1.000 | 1397.4 |
| 500.00 | 265 | 1.000 | 2794.9 |
| 1000.00| 265 | 1.000 | 5589.7 |

A consumer reading `conf` as a Gaussian standard deviation ($k = 1.96$, the textbook 95% wrap) realises **10.2%** coverage on the available subset; tripling the field ($k = 3$) recovers only 15.5%. The `conf` field is tight relative to weekend-gap dispersion because it measures publisher dispersion at venue close, which is not the object a closed-market coverage statement needs. The $k = 50$ that realises 95% on this sample is fit in hindsight on the evaluation data: no ex-ante-choosable multiplier on the published dispersion yields a known coverage level, and a consumer who back-fits $k$ on their own historical sample has constructed their own calibration — with no audit trail and no per-symbol stratification — rather than read one off the wire. This is the k-ladder finding carried in Table T1.

**Caveats.** (i) The benchmark uses Pyth's regular-hours feeds (`Equity.US.{TICKER}/USD`); Pyth also publishes overnight (`.ON`) and pre/post-market (`.PRE`/`.POST`) feeds not probed here. (ii) AAPL, GOOGL, HOOD, NVDA show 0% availability at the 15:55 ET probe despite valid feed IDs — consistent with session-restricted publishing at the probe time or feed launches after the window opened. (iii) The ladder values are point estimates on a 265-obs sample without bootstrap CIs. Raw observations: `data/processed/pyth_benchmark_oos.parquet`; per-(k, scope) breakdown: `reports/tables/pyth_coverage_by_k.csv`; runner: `scripts/pyth_benchmark_comparison.py`.

## F.3 Chainlink Data Streams v11 — synthetic weekend markers

v11 is the active 24/5 US-equity report schema (schema id `0x000b`, 14-field 448-byte ABI-encoded payload) [chainlink-v11]; its `market_status` enum encodes the underlying venue session, with `market_status = 5` covering weekends. Public documentation does not state what `bid`/`ask`/`mid` carry during `market_status ≠ 2` (regular session); the schema still publishes a price on weekends, and whether that price is real or placeholder-derived is an empirical question the wire answers.

**Panel and classifier.** An 87-observation weekend panel (2026-02-06 → 2026-04-17; `reports/v1b_chainlink_comparison.md`) establishes that v11 publishes a price during weekend windows but no coverage band — the wire `bid`/`ask` are the closest fields. A synthetic-marker classifier (v2, scan of 2026-04-26; `reports/v11_cadence_verification.md`) decoded 26 v11 weekend reports at `market_status = 5` — 20 on the four mapped xStocks (SPYx $n=6$, QQQx $n=6$, TSLAx $n=7$, NVDAx $n=1$) plus 6 on unmapped tickers — and labelled each against a six-class taxonomy distinguishing real quotes from placeholder bookends.

**Per-symbol findings.**

- **SPYx — pure placeholder.** Both bid and ask carry the synthetic `.01`-suffix marker in 100% of weekend samples (bid 21.01, ask 715.01; spread 18,858 bps). The `mid` field (368.0100) is the arithmetic midpoint of the synthetic bookends, not a market mid; `last_traded_price` (713.96) is plausibly the real Friday close.
- **QQQx, TSLAx — bid-synthetic.** The bid carries the `.01` marker in 100% of weekend samples (QQQx 656.01, TSLAx 372.01) while the ask is not so marked; spreads 117–329 bps. Real-market bids land on `.01` at roughly a 1-in-100 base rate; a 100% incidence is a strong synthetic signal.
- **NVDAx — mixed.** The single weekend sample ($n=1$) classifies as real (bid 208.07, ask 208.14, spread 3.4 bps). Single-sample evidence; it needs replication before generalising, and it leaves open whether the synthetic-marker pattern is per-feed rather than universal.
- **Sessions 1/3/4** (pre-market, post-market, overnight) had no samples in the scan window and are unmeasured.

Two consequences for a consumer. First, the spread is a misleading signal on weekends: the pure-placeholder pattern produces an 18,858-bps spread while the bid-synthetic pattern can fall under 200 bps, so a spread-threshold filter misses the synthetic-low mechanism — classification requires the marker check. Second, the point estimate survives where the interval does not: the measured pooled weekend point-estimate bias is −8.77 bps (undetectable at panel size; `reports/v1_chainlink_bias.md`) — the synthetic-bid / real-mid combination yields a usable point and no usable interval. These are the synthetic-marker findings carried in Table T1, with sample bounds as stated (26 decoded reports, 20 on the four mapped xStocks, `market_status = 5`, Feb–Apr 2026).

## F.4 Per-venue schema and wire-field evidence

§2 states the categorical claim — no surveyed incumbent surface publishes a calibration claim on the served value; this section catalogues the per-venue field evidence behind it.

**Chainlink Data Streams** ships three co-existing RWA schemas as of 2026-Q2: v8 RWA Standard [chainlink-v8], v10 Tokenized Asset [chainlink-v10], and v11 RWA Advanced [chainlink-v11]. v8 is the load-bearing path for tokenized-equity lending on Solana: Kamino Finance consumes every xStock collateral asset through Kamino Scope's `OracleType::ChainlinkRWA` adaptor [scope-oracle-type; kamino-xstocks-gov], routed through the v8 dispatcher, with two parallel feeds per xStock registered in Scope's mainnet config [scope-mainnet-cfg] — an `Open` mode that refuses updates outside US trading hours and an `AllUpdates` mode clamped to ±500 bps of the Open feed's Friday-close value. On the wire, v8 is mid-only (no `bid`/`ask`/confidence) with `marketStatus` as the only off-hours regime signal. v10 backs the Backed↔Solana xBridge but is not consumed by the canonical Solana lending market; it carries no `bid`/`ask`/confidence field and serves a 24/7 `tokenizedPrice` whose CEX-aggregation methodology is qualitatively described. v11's weekend `bid` carries the synthetic `.01`-suffix at 100% incidence on three of four mapped xStocks (F.3).

**Pyth** [pyth-agg; pyth-conf] aggregates first-party publisher submissions: each permissioned publisher submits a price and confidence interval, and the aggregate rule assigns three votes per publisher (price, price ± confidence) before taking the median. The published `(price, conf)` reports low publisher disagreement at venue close; documentation asserts ~95% coverage at the *publisher* level, which is per-publisher self-attestation, not a property of the aggregate a protocol reads. Pyth Pro layers subscriber-customisable cadence and the Blue Ocean ATS overnight integration [pyth-pro; blueocean-pyth], covering 8:00 PM – 4:00 AM ET Sun–Thu — the canonical xStock weekend remains uncovered.

**CF Benchmarks** (Kraken-owned, FCA + BMR-supervised) launched the xStocks Indices family on 2026-05-07 [cfb-xstocks-indices; cfb-methodology-guide]: regulated per-second scalars per xStock (Price Return + Total Return variants) powering Kraken's tokenized-equity perpetuals. The BMR Article 27 Benchmark Statement contains no language about realised coverage; no confidence, band, or coverage field is on the wire.

**SEDA** publishes session-aware single-asset feeds and a USA500 composite (60% equities / 25% crypto / 15% commodities) consumed by Hyperliquid HIP-3 markets via Dreamcash, Injective, and Perps.Fun [seda-benchmark], governed by a four-pillar continuity rule (session tags, cost-of-carry futures-to-spot, self-referencing EMA, staleness fallback); the output is a single scalar plus session-flag metadata.

**Others.** Switchboard generalises aggregation into permissionless queues with shallow tokenized-equity deployment [switchboard]; RedStone Live blends institutional feeds with perpetual-market data into a 24/7 scalar [redstone-live]; optimistic oracles UMA [uma] and Tellor [tellor] guarantee *eventual* correctness under economic security but define no distributional statement conditional on time-of-week or realised volatility.

## F.5 External-evidence epistemic status

Two external-evidence inputs to the §1/§2 framing warrant explicit disclosure.

**Cong et al. (2025) panel [cong-tokenized-2025].** The empirical premise — that tokenized-equity prices deviate from underlying closes with documented frequency during closed-market windows, that the wedge is structural rather than transitional, and that off-hour tokenized returns carry a conditional-mean signal on the underlying open — leans on Cong, Landsman, Rabetti, Zhang and Zhao. Their sample is four months (July–October 2025), 100 tokenized stocks, $420M aggregate market cap concentrated in Backed Finance and Ondo Global Markets, and a late-2025 volatility regime. The deviation-frequency table cited most directly (Table 4, p.32) is for TSLAx alone; the panel-level passthrough regression (Table 10, p.40: $\lambda = 0.903$, adjusted $R^2 = 0.839$) pools across the 100 names without per-symbol stability evidence. We do not assume any specific Cong-cited number carries forward in distributional shape; the citations establish the empirical context for the §1 motivation, and the deployed primitive's coverage claim is validated independently on the twelve-year ten-symbol panel of public-data underliers (§6).

**Kamino's per-reserve `Open` / `AllUpdates` mapping.** Scope's dual-feed architecture (F.4) offers two serving modes per xStock; we do not pin which mode any given xStock lending reserve currently subscribes to. The per-reserve selection is governance-set in the mainnet config [scope-mainnet-cfg], but the live `kamino-lending` reserve PDA mapping is governance-mutable and was not decoded end-to-end. The claim as stated — neither mode publishes a calibrated coverage band, and the choice between them is a governance parameter — is stable across reconfigurations; if the on-chain decoding completes, the claim sharpens to the single archetype actually selected without weakening the categorical contribution. This bound is also stated in Table T1's caption (§1.2), whose rows 1–2 describe the two available modes, not a per-reserve assignment.

## F.6 Cluster topology of the full-distribution residual

§8 states the headline: the served band is per-anchor calibrated but not full-distribution calibrated, and the residual is within-weekend cross-sectional co-breach. This section carries the localisation detail.

**Cluster structure.** The residual is a within-weekend cluster structure separating equities (8 symbols, positively correlated with the weekend equity factor) from safe-haven assets (GLD, TLT, with negative or near-zero correlation to the equity factor). Within the equity cluster $\hat\rho_\text{within} = 0.477$ — *higher* than the panel-wide mean intra-weekend pairwise correlation $\bar\rho_\text{intra} = 0.41$, because the cross-cluster correlations dilute it. Within the safe-haven cluster $\hat\rho_\text{within} = -0.016$ — there is no common-mode to remove.

**Why a naive partial-out fails.** A non-parametric partial-out using either the within-weekend median or mean reduces $\bar\rho_\text{intra}$ from $0.41$ to $\{0.12, 0.06\}$ but breaks per-symbol Kupiec on the safe-haven cluster (GLD violation rate $14.5\%$, TLT $9.2\%$ under the median variant; $5/10$ per-symbol pass under the mean variant) and rejects DQ at $\tau \in \{0.68, 0.85\}$. The mechanism is structural: subtracting an equity-dominated weekend median from a negatively-correlated asset creates fresh violations on equity-rally weekends and pulls residuals toward the band centre on selloff weekends. Any operation that treats the panel as exchangeable inherits this failure mode; a working architecture-level fix must respect the cluster topology (F.10).

**Two views of the same structure.** The over-dispersion of the homogeneous t-copula (§8; emp/t variance $0.63$ at $\tau = 0.95$) and the cluster failure of the naive partial-out are two views of the same equity-vs-safe-haven structure: a single Pearson $\hat R$ averages high equity-equity correlations against negative equity-safe-haven correlations; a single weekend median centres on the equity cluster's mean. Either rendering of the panel as homogeneous misses the same topology. (Source: A1, A1.5, A3 — `paper1_a1_*.csv`, `paper1_a1_5_*.csv`, `paper1_a3_*.csv`.)

**Localising the lag-1 alternative.** The AR(1) signal lives in the *cross-sectional within-weekend* ordering ($\hat\rho_\text{cross} = 0.354$, $p < 10^{-100}$), not the temporal-within-symbol ordering ($\hat\rho_\text{time} = -0.032$, $p = 0.18$). σ̂ standardisation operates *within* a symbol's history, not *across* symbols within a weekend, so the deployed architecture is structurally unable to reach this residual. A vol-tertile sub-split of the `normal` regime (5 cells) leaves Berkowitz LR essentially unchanged ($170 \to 172$) while widening the $\tau = 0.95$ band by $9\%$ — finer regime granularity is not the lever. Within-bin exchangeability separately holds (permutation test on lag-1 score autocorrelation within each regime × symbol bin: $1/30$ nominally rejecting at uncorrected $\alpha = 0.05$, $0/30$ after Benjamini–Hochberg correction; Appendix B). The cross-sectional dependence is *across* bins, not within.

**Per-symbol Berkowitz localisation.** The residual symbols rejecting Berkowitz at $\alpha = 0.01$ are TLT (LR $= 16.7$) and TSLA (LR $= 13.5$) — both trace to cross-sectional common-mode rather than per-symbol scale. The joint-tail distribution of §8 turns the Berkowitz rejection into a measurable, reportable shape ($2.34\times$ variance overdispersion vs independence at $\tau = 0.95$; $P(k_w \ge 3) = 4.62\%$ vs binomial $1.15\%$, t-copula $8.2\%$), and the $k^\ast$ threshold gives the consumer an operational handle that holds up against the joint-volatility model a CCAR-style risk team would run, not just against independence.

## F.7 τ-stratified CUSUM drift bank

The CUSUM drift monitor — calibration, detection power, and its SVB (2023-03-10) and BoJ (2024-08-02) firings — is documented in Appendix B §B.17, alongside the forward-tape harness whose weekly ingest path it re-uses; §8 and §9 cite it there. The residual it monitors is the cross-sectional co-breach structure of §F.6.

## F.8 MEV and execution-aware coverage — not measured

A consumer transacting at a worse price than the band's mid (front-running, sandwich, block-builder reordering) experiences an *effective* coverage that may differ from the measured path coverage near band edges. Measuring this requires Solana mempool-or-bundle granularity plus a consumer-behaviour model; neither is in this paper's data, and no execution-aware coverage number is claimed. The data requirement is stated with the path-fitted variant in F.11.

## F.9 Region and asset-class scope

**Region.** All ten tickers are US-listed; the closed-market window predicted is the US weekend or US overnight, and the factor switchboard privileges US session data. We make no claim about generalisation to tokenized-JP or tokenized-EU equities.

**Asset class.** The methodology requires a *continuous off-hours information set* — a public, free, sub-daily price signal correlated with the closed-market underlier. Tokenized US equities have this (E-mini futures + VIX), tokenized gold has it (gold futures + GVZ), tokenized US treasuries have it (10Y T-note futures + MOVE), and most major FX pairs have it; tokenized credit has it through CDS spreads. Out of scope: real estate (no continuous off-hours signal), illiquid commodities (futures discontinuous or thin), and instruments with primarily NAV-based pricing. `docs/methodology_scope.md` carries the per-class fit/no-fit table.

## F.10 Full-distribution conformal variant — characterised, not deployed

Per §9: this variant is characterised, not deployed, and nothing the paper claims depends on it.

The pooled Berkowitz and DQ rejections at $\tau = 0.95$ (§8) are the deepest residual. The deployed architecture is *partially* conformal — per-regime Mondrian quantiles on per-symbol-σ̂-standardised residuals with a near-identity $c(\tau)$ bump; a full-distribution variant replaces the four-anchor schedule with a single conformal correction over the residual CDF, delivering exchangeability-based finite-sample coverage at every $\tau$ simultaneously (Romano–Patterson–Candès CQR [romano-cqr-2019] is the closest match). Because the residual localises to the equity-vs-safe-haven cluster topology (F.6), the correction must be cluster-conditional: a cluster-internal partial-out within the equity cluster reduces $\hat\rho_\text{within}$ from $0.477$ to $0.077$, preserves per-symbol Kupiec 8/8 on the cluster, and tightens half-width $-11.6\%$ at $\tau = 0.95$. Composed with the path-fitted conformity score of F.11, the characterisation is $\tau$-conditional: at $\tau \ge 0.95$ the cluster-conditional + path-fitted combination is empirically calibrated on the equity-cluster + CME-projected subset, moving pooled DQ at $\tau = 0.95$ from rejection to $p = 0.912$; at $\tau < 0.95$ endpoint scoring on the unpartialled residual remains dominant — path extrema introduce within-symbol temporal autocorrelation that DQ catches at body-of-distribution $\tau$. The recommendation is bounded to the anchors where it is calibrated, not blanket.

## F.11 Path-fitted conformity score and the earnings-night bake-off — technical detail

**Path-fitted score.** The path-fitted conformity score is implemented and unit-tested (`soothsayer.backtest.calibration.compute_score_lwc_path`; 7 unit tests, all pass), and an empirical first cut on the CME-projected subset ($n = 1{,}557$ OOS rows) confirms mechanical correctness. Continuous-consumption AMM use cases require this path-fitted variant rather than the endpoint score — the endpoint-not-path bound of §8. The binding empirical question — whether path-fitting closes the measured endpoint-vs-path gap on consumer-experienced path data — is answerable once the V5 forward-cursor tape (continuous capture since 2026-04-24) accumulates $N \ge 300$ path-coverage weekends. An MEV-conditional variant additionally requires Solana bundle-level granularity to reconstruct the price a consumer would have *executed at* near band-edge events (F.8).

**Earnings-night bake-off.** The `earnings_night` regime (§6.5) is the underlying-side confirmation of Cong et al.'s value-relevant-news mechanism; the sharper head-to-head is the calendar-conditioned band against the Cong-implied tokenized passthrough baseline (`point = tokenised_price_at_t`; band = ±k × historical residual), evaluated under matched-$\tau$ Kupiec / Christoffersen *on earnings nights specifically*, once the V5 forward-cursor tape accumulates enough post-launch earnings nights. That comparison is the empirical bridge from the present underlying-side result to a tokenized-side claim, and it is deliberately not asserted here.
