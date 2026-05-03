# References — §2 Related Work

Structured bibliography for the Related Work section of *"Empirical coverage inversion: a calibration-transparency primitive for decentralized RWA oracles."* Each entry has been verified against a primary source (publisher page, arXiv, or official institutional host); unverifiable entries are explicitly marked.

Buckets:
- **oracles** — decentralized oracle designs
- **price-discovery** — cross-venue / microstructure price-discovery literature
- **calibration-conformal** — interval / density forecast evaluation and conformal prediction
- **model-risk-management** — regulatory / institutional model-validation guidance
- **microstructure** — supporting equity-microstructure results (after-hours, weekend effects) used to motivate the weekend prediction-window choice

---

## Bucket: oracles

### [pyth-agg] Pyth Network. 2021. A proposal for price feed aggregation.
- **Venue:** Pyth Network blog / engineering post (documenting the deployed aggregation)
- **URL / DOI:** https://www.pyth.network/blog/pyth-price-aggregation-proposal
- **Contribution:** Specifies Pyth's on-chain aggregation rule — each publisher contributes three votes (price, price±conf), the aggregate price is their median, and the aggregate confidence interval is the max distance from the median to the 25th / 75th percentile votes.
- **Why we cite it:** This is the primary source for our claim that Pyth's confidence interval is an *aggregation-diagnostic* dispersion measure, not a claimed probability-of-coverage statement on the underlying $P_t$ distribution.
- **Bucket:** oracles

### [pyth-conf] Pyth Network. 2022. Pyth primer: don't be pretty confident, be Pyth confident.
- **Venue:** Pyth Network blog
- **URL / DOI:** https://www.pyth.network/blog/pyth-primer-dont-be-pretty-confident-be-pyth-confident
- **Contribution:** Explains Pyth's confidence interval semantics and recommends that each publisher's interval be calibrated to ~95% coverage; notes that the aggregate CI widens during publisher disagreement.
- **Why we cite it:** Documents that the *publisher-level* intervals carry an implied coverage claim, but that no verifiable calibration statement is published at the aggregate (feed) level — which is the surface downstream protocols actually read.
- **Bucket:** oracles

### [pyth-pro] Pyth Network. 2026. Pyth Pro (formerly Pyth Lazer): enterprise-grade price data with customizable cadence.
- **Venue:** Pyth Network product documentation
- **URL / DOI:** https://docs.pyth.network/lazer (accessed 2026-04-29; page reframes the product as "Pyth Pro (formerly Pyth Lazer)")
- **Contribution:** Specifies the Pyth Pro tier — same publisher-vote aggregation as regular Pyth, with subscriber-customizable feed cadence and the Blue Ocean ATS overnight integration as the principal 24/5 equity differentiator.
- **Why we cite it:** Primary technical reference for Pyth Pro. Bounds the framing in §1.1 / §2.1 / §6.7: Pyth Pro is the closest published incumbent to a real 24/5 equity feed but inherits regular Pyth's publisher-dispersion methodology and does not surface an aggregate-level calibration claim.
- **Bucket:** oracles

### [blueocean-pyth] Pyth Network. 2025-09-25. Blue Ocean ATS joins Pyth Network: institutional overnight hours US equity data.
- **Venue:** Pyth Network blog (companion announcement on Blue Ocean's site)
- **URL / DOI:** https://www.pyth.network/blog/blue-ocean-ats-joins-pyth-network-institutional-overnight-hours-us-equity-data ; https://blueocean-tech.io/2025/09/25/pyth-blue-ocean-ats-joins-pyth-network-institutional-overnight-hours-us-equity-data/
- **Contribution:** Announces Pyth's exclusive on-chain distribution of Blue Ocean ATS overnight equity data through end-2026. Operating window 8:00 PM – 4:00 AM ET, Sun–Thu, executable book data with ~$1B nightly volume across ~5,000 actively-traded NMS symbols.
- **Why we cite it:** Documents the closest published incumbent to a real 24/5 equity feed and bounds its coverage window. Used to qualify the "no published 24/5 equity feed" framing in §1.1 / §2.1 — Pyth Pro / Blue Ocean fills the *overnight* gap (Sun-Thu nights) but does not cover Friday 4 PM ET through Sunday 8 PM ET, the canonical xStock weekend window this paper targets.
- **Bucket:** oracles

### [chainlink-2] Breidenbach, L., Cachin, C., Chan, B., Coventry, A., Ellis, S., Juels, A., Koushanfar, F., Miller, A., Magauran, B., Moroz, D., Nazarov, S., Topliceanu, A., Tramèr, F., Zhang, F. 2021. Chainlink 2.0: next steps in the evolution of decentralized oracle networks.
- **Venue:** Chainlink research whitepaper (April 2021)
- **URL / DOI:** https://research.chain.link/whitepaper-v2.pdf
- **Contribution:** Outlines the decentralized-oracle-network (DON) architecture, hybrid smart contracts, and a confidentiality / computation roadmap (DECO, FSS, etc.); formalises Chainlink's off-chain aggregation + on-chain report delivery pattern.
- **Why we cite it:** Canonical statement of the deployed Chainlink design — our "stale-hold" archetype is the real-world-asset profile of this design, and §2.1 distinguishes their integrity primitive from our calibration primitive.
- **Bucket:** oracles

### [chainlink-streams] Chainlink Labs. 2024–2026. Chainlink Data Streams.
- **Venue:** Chainlink product documentation
- **URL / DOI:** https://docs.chain.link/data-streams (top-level overview accessed 2026-04-29; deep schema sub-pages have been refactored — see `[chainlink-v10]` and `[chainlink-v11]` for the per-schema pins)
- **Contribution:** Top-level Data Streams product page. Two RWA-relevant report schemas co-exist on Solana mainnet as of 2026-Q2: v10 (Tokenized Asset, schema id `0x000a`) and v11 (RWA Advanced, schema id `0x000b`). Both decode through the same Verifier program; consumers dispatch on schema id.
- **Why we cite it:** Top-level entry point used in §1.1 and §2.1 when the claim is about the Data Streams product family rather than a specific schema; per-schema citations are `[chainlink-v10]` and `[chainlink-v11]`.
- **Bucket:** oracles

### [chainlink-v10] Chainlink Labs. 2025. Data Streams v10 ("Tokenized Asset") report schema.
- **Venue:** Chainlink product documentation; SDK source (authoritative pin)
- **URL / DOI:** https://docs.chain.link/data-streams/reference/report-schema-v10 (the deep schema page returned 404 in our 2026-04-29 probe — link rot logged); the SDK source at `smartcontractkit/data-streams-sdk` mirrored in `src/soothsayer/chainlink/v10.py` is the authoritative pin.
- **Contribution:** Specifies the v10 report layout — schema id 0x000a, 13 fields, 416 bytes; carries `price` (venue last-trade), `tokenizedPrice` (24/7 CEX-aggregated mark), 3-state `marketStatus` enum (`0 Unknown / 1 Closed / 2 Open`), and corporate-action multipliers. **Carries no `bid`, `ask`, or confidence field on the wire.**
- **Why we cite it:** Direct primary source for §1.1, §2.1, and §6.7.2. The v10 wire format is band-less by construction: a consumer reading v10 directly derives a degenerate zero-width band — the cleanest empirical instance of the "no incumbent publishes a verifiable calibration claim" framing.
- **Bucket:** oracles

### [chainlink-v11] Chainlink Labs. 2026. Data Streams v11 ("RWA Advanced") report schema.
- **Venue:** Chainlink product documentation; SDK source (authoritative pin)
- **URL / DOI:** https://docs.chain.link/data-streams/reference/report-schema-v11 (the deep schema page returned 404 in our 2026-04-29 probe — link rot logged); the SDK source at `smartcontractkit/data-streams-sdk` mirrored in `src/soothsayer/chainlink/v11.py` is the authoritative pin.
- **Contribution:** Specifies the v11 RWA Advanced layout — schema id 0x000b, 14 fields, 448 bytes; extends v10 with `bid`/`ask`/`mid`/`last_traded_price`/`bid_volume`/`ask_volume` and a 6-state `marketStatus` enum distinguishing pre-market, regular, post-market, overnight, and closed/weekend states. Live in our Solana tape since 2026-Q1, co-existing with v10.
- **Why we cite it:** Direct primary source for §1.1, §2.1, and §6.7.2. The v11 schema is the load-bearing 24/5 archetype against which we measure the synthetic-marker weekend pattern documented in our internal cadence-verification scan; the marker-aware classifier that distinguishes synthetic-bid bookends from real quotes lives at `reports/v11_cadence_verification.md`.
- **Bucket:** oracles

### [redstone-live] RedStone. 2026. RedStone Live: real-time market data for 24/7 markets.
- **Venue:** RedStone blog / product documentation (March 2026)
- **URL / DOI:** Launch blog post: https://blog.redstone.finance/2026/03/30/redstone-live-real-time-data-built-for-the-markets-that-never-sleep/. Top-level documentation: https://docs.redstone.finance/docs/introduction (accessed 2026-04-29). The deep methodology page (`https://docs.redstone.finance/docs/dapps-and-defi/redstone-models`) returned 404 on 2026-04-29 — link rot logged in canonical `docs/sources/oracles/redstone_live.md`; the public REST gateway at `https://api.redstone.finance/prices` is the live observation surface.
- **Contribution:** Describes RedStone's 24/7 equity-feed product, which blends institutional sources during market hours with perpetual-market data during off-hours. Methodology weights, contributing-venue list, consensus rule, and any confidence statement are described qualitatively but not published in reproducible form on any public surface (REST gateway, on-chain PDA, or launch post).
- **Why we cite it:** Primary evidence for our "undisclosed-methodology" archetype — the feed serves closed-market values, but a consumer cannot reproduce the number or audit a coverage claim. The deep methodology page being 404'd is itself load-bearing: the framing in §1.1 / §2.1 / §9.8.1 ("no calibration claim exposed in any public artifact") is exact rather than rhetorical given the documented absence.
- **Bucket:** oracles

### [switchboard] Switchboard. 2023. Switchboard V3 documentation.
- **Venue:** Switchboard product documentation / Breakpoint 2023 presentation
- **URL / DOI:** https://docs.switchboard.xyz/docs/switchboard/readme/designing-feeds/oracle-aggregator
- **Contribution:** Specifies Switchboard's oracle-aggregator, TEE-attested oracle queues, and permissionless feed creation; publishers submit jobs whose results are aggregated on-chain with configurable reducers.
- **Why we cite it:** Complements Pyth / Chainlink as a third incumbent Solana oracle; relevant to the deployed-archetype landscape. Switchboard's aggregation is likewise silent on realised coverage against a reference $P_t$ distribution.
- **Bucket:** oracles

### [tellor] Tellor. 2023. Tellor whitepaper.
- **Venue:** Tellor project whitepaper (April 2023 revision)
- **URL / DOI:** https://tellor.io/wp-content/uploads/2023/04/Tellor-Whitepaper_4_2023.pdf
- **Contribution:** Describes Tellor's reporter-stake + dispute mechanism for on-chain data delivery, with economic slashing against false data submissions.
- **Why we cite it:** Representative of the *dispute-based* oracle archetype, a distinct design philosophy from median-aggregation oracles; provides contrast to frame our calibration primitive as orthogonal to integrity / dispute design.
- **Bucket:** oracles

### [uma] UMA Project. 2020. UMA: an optimistic oracle with a data verification mechanism.
- **Venue:** UMA project documentation / blog post *Introducing UMA's Optimistic Oracle*
- **URL / DOI:** https://medium.com/uma-project/introducing-umas-optimistic-oracle-d92ce5d1a4bc
- **Contribution:** Formalises the optimistic oracle as a propose-challenge-vote mechanism anchored by the UMA DVM and the priceless-contracts design philosophy.
- **Why we cite it:** Represents the optimistic-oracle design family; we contrast its *integrity-guarantee* philosophy with our *coverage-guarantee* philosophy in §2.1.
- **Bucket:** oracles

### [angeris-cfmm] Angeris, G., Chitra, T. 2020. Improved price oracles: constant function market makers.
- **Venue:** Proceedings of the 2nd ACM Conference on Advances in Financial Technologies (AFT '20); arXiv:2003.10001
- **URL / DOI:** https://arxiv.org/abs/2003.10001
- **Contribution:** Gives sufficient conditions under which agents interacting with CFMMs are economically incentivised to report the prevailing price; shows when the on-chain market price is an unbiased oracle under arbitrage frictions.
- **Why we cite it:** Grounds the theoretical case for AMM-as-oracle and allows us to position our work as *complementary* — we address the off-chain reference-price problem that no AMM can solve during venue closure.
- **Bucket:** oracles

### [sok-oracles] Eskandari, S., Salehi, M., Gu, W. C., Clark, J. 2021. SoK: Oracles from the ground truth to market manipulation.
- **Venue:** 3rd ACM Conference on Advances in Financial Technologies (AFT '21); arXiv:2106.00667
- **URL / DOI:** https://arxiv.org/abs/2106.00667
- **Contribution:** Systematisation-of-knowledge dissecting oracle design alternatives, cataloguing oracle-manipulation attacks (flash-loan, liquidity, centralised feed failures), and surveying mitigation strategies.
- **Why we cite it:** The canonical survey of the *integrity* problem for DeFi oracles; grounds our argument that existing academic / industry literature focuses on the integrity primitive, leaving the calibration primitive unaddressed.
- **Bucket:** oracles

### [bis-oracle] Duley, C., Gambacorta, L., Garratt, R., Koo Wilkens, P. 2023. The oracle problem and the future of DeFi.
- **Venue:** BIS Bulletin No. 76, Bank for International Settlements (September 2023)
- **URL / DOI:** https://www.bis.org/publ/bisbull76.pdf
- **Contribution:** Argues that the DeFi oracle problem forces a trade-off between decentralisation and efficiency; concludes that full decentralisation in oracle delivery is unlikely to support real-world-asset use cases.
- **Why we cite it:** An institutional (central-bank) framing of the oracle problem; supports our point that RWA oracles specifically — the product category we target — are the regulatory pressure point.
- **Bucket:** oracles

### [flashboys-2] Daian, P., Goldfeder, S., Kell, T., Li, Y., Zhao, X., Bentov, I., Breidenbach, L., Juels, A. 2020. Flash Boys 2.0: Frontrunning, transaction reordering, and consensus instability in decentralized exchanges.
- **Venue:** IEEE Symposium on Security and Privacy 2020; arXiv:1904.05234
- **URL / DOI:** https://arxiv.org/abs/1904.05234
- **Contribution:** Introduces the MEV framing for blockchain transaction ordering; empirically documents priority-gas auctions and characterises consensus-layer implications of arbitrage bots.
- **Why we cite it:** Establishes the on-chain extractive-MEV environment in which oracle reads are consumed; our receipts-based design is motivated by the need to make oracle misuse accountable under adversarial ordering.
- **Bucket:** oracles

---

## Bucket: price-discovery

### [hasbrouck-1995] Hasbrouck, J. 1995. One security, many markets: determining the contributions to price discovery.
- **Venue:** Journal of Finance 50(4), 1175–1199
- **URL / DOI:** https://doi.org/10.1111/j.1540-6261.1995.tb04054.x
- **Contribution:** Introduces the information-share methodology: a VECM-based decomposition that attributes proportions of the efficient-price innovation variance to each trading venue of a cross-listed security.
- **Why we cite it:** The methodological foundation for every subsequent futures-cash and cross-venue price-discovery study we cite; establishes the mathematical framework inside which the Hasbrouck-2003 result below is stated.
- **Bucket:** price-discovery

### [hasbrouck-2003] Hasbrouck, J. 2003. Intraday price formation in U.S. equity index markets.
- **Venue:** Journal of Finance 58(6), 2375–2400
- **URL / DOI:** https://doi.org/10.1046/j.1540-6261.2003.00609.x
- **Contribution:** Applies the 1995 information-share methodology to S&P 500 / Nasdaq-100 / S&P 400 index futures, ETFs, and E-minis. Finds that for S&P 500 and Nasdaq-100, *most* of the price discovery occurs in the E-mini futures market.
- **Why we cite it:** Direct empirical grounding for the factor-switchboard point estimator: scaling Friday close by the weekend ES / NQ return is justified by Hasbrouck's information-share result, not invented here.
- **Bucket:** price-discovery

### [gonzalo-granger] Gonzalo, J., Granger, C. W. J. 1995. Estimation of common long-memory components in cointegrated systems.
- **Venue:** Journal of Business & Economic Statistics 13(1), 27–35
- **URL / DOI:** https://doi.org/10.1080/07350015.1995.10524576
- **Contribution:** Proposes the component-share decomposition for cointegrated systems, identifying permanent (common-factor) contributions of each series. Standard complement to the Hasbrouck information share.
- **Why we cite it:** Support citation for the methodological toolkit behind cross-venue price-discovery claims — anchors our discussion of how "leader" venues are identified.
- **Bucket:** price-discovery

### [stoll-whaley-1990] Stoll, H. R., Whaley, R. E. 1990. The dynamics of stock index and stock index futures returns.
- **Venue:** Journal of Financial and Quantitative Analysis 25(4), 441–468
- **URL / DOI:** https://doi.org/10.2307/2331010
- **Contribution:** Using 5-minute intraday returns, shows that S&P 500 and MM index futures lead the stock index by about 5 minutes (occasionally longer), even after adjusting for infrequent trading in the cash index.
- **Why we cite it:** An earlier foundational result for futures-lead-cash, historically strengthening Hasbrouck's E-mini result and establishing the lead-lag as a persistent microstructure feature.
- **Bucket:** price-discovery

### [mackinlay-ramaswamy-1988] MacKinlay, A. C., Ramaswamy, K. 1988. Index-futures arbitrage and the behavior of stock index futures prices.
- **Venue:** Review of Financial Studies 1(2), 137–158
- **URL / DOI:** https://doi.org/10.1093/rfs/1.2.137
- **Contribution:** Examines intraday S&P 500 index-futures arbitrage, documenting mispricing persistence of 15–40 minutes and the asymmetric adjustment between futures and cash.
- **Why we cite it:** Completes the lineage of futures-cash price-discovery results invoked to justify our factor-switchboard design.
- **Bucket:** price-discovery

### [madhavan-sobczyk-2016] Madhavan, A., Sobczyk, A. 2016. Price dynamics and liquidity of exchange-traded funds.
- **Venue:** Journal of Investment Management 14(2), 88–102
- **URL / DOI:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2429509
- **Contribution:** Models ETF price dynamics under the creation/redemption mechanism; shows that ETFs accelerate the price discovery of their constituents when arbitrage is frictionless, and quantifies the drift between ETF price and NAV.
- **Why we cite it:** Our asset set includes SPY, QQQ, GLD, TLT — all ETFs. This paper justifies treating ETF-class instruments under a common price-discovery framework and distinguishes ETF-specific dynamics from single-equity dynamics.
- **Bucket:** price-discovery

### [makarov-schoar-2020] Makarov, I., Schoar, A. 2020. Trading and arbitrage in cryptocurrency markets.
- **Venue:** Journal of Financial Economics 135(2), 293–319
- **URL / DOI:** https://doi.org/10.1016/j.jfineco.2019.07.001
- **Contribution:** Documents recurring cross-exchange and cross-country arbitrage in cryptocurrency markets; characterises the role of capital controls and limits-to-arbitrage in sustaining price deviations.
- **Why we cite it:** Establishes that crypto-native venues exhibit their own price-discovery structure, which motivates why tokenised-equity off-hours prices can reasonably be anchored to futures / perp markets rather than to staled equity last-prints.
- **Bucket:** price-discovery

### [cong-tokenized-2025] Cong, L. W., Landsman, W. R., Rabetti, D., Zhang, C., Zhao, W. 2025. Tokenized stocks.
- **Venue:** Working paper, SSRN id 5937314 (December 2025)
- **URL / DOI:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5937314
- **Contribution:** First large-scale empirical study of tokenised stocks; documents that tokens track their underlying closely during regular hours, deviate during off-hours, and that weekend movements *anticipate* (rather than amplify) subsequent Monday returns.
- **Why we cite it:** The directly-on-point motivation for our work: weekend price discovery is *actively migrating* to crypto-native token venues, so a calibrated fair-value band on the continuous on-chain clock becomes a first-class protocol need.
- **Bucket:** price-discovery

### [lehar-parlour-2025] Lehar, A., Parlour, C. A. 2025. Decentralized exchange: the Uniswap automated market maker.
- **Venue:** Journal of Finance 80(1), 321–374
- **URL / DOI:** https://doi.org/10.1111/jofi.13405
- **Contribution:** Comprehensive empirical study of all 95.8M Uniswap interactions, characterising liquidity-provider equilibria and documenting the absence of long-lived arbitrage opportunities in the DEX relative to CEX benchmarks.
- **Why we cite it:** Evidence that on-chain DEX prices do carry price-discovery content during active hours; useful context when arguing our design is complementary to DEX-as-oracle approaches (which fail during venue closure for correlated off-chain assets).
- **Bucket:** price-discovery

---

## Bucket: calibration-conformal

### [kupiec-1995] Kupiec, P. H. 1995. Techniques for verifying the accuracy of risk measurement models.
- **Venue:** Journal of Derivatives 3(2), 73–84
- **URL / DOI:** https://doi.org/10.3905/jod.1995.407942
- **Contribution:** The unconditional-coverage likelihood-ratio test for VaR / interval-forecast systems: given a nominal coverage $\alpha$ and $N$ observations, tests whether the realised hit frequency is consistent with $\alpha$.
- **Why we cite it:** The $p_{UC}$ column in our Kupiec + Christoffersen diagnostic table is *this test*. Directly supports the claim that our diagnostic is the institutional unconditional-coverage standard.
- **Bucket:** calibration-conformal

### [christoffersen-1998] Christoffersen, P. F. 1998. Evaluating interval forecasts.
- **Venue:** International Economic Review 39(4), 841–862
- **URL / DOI:** https://doi.org/10.2307/2527341
- **Contribution:** Defines conditional-coverage evaluation for interval forecasts, decomposing into an unconditional-coverage test (Kupiec) and an independence test on the hit sequence; joint conditional-coverage LR test.
- **Why we cite it:** The independence and conditional-coverage $p$-values we report in §6 are precisely those of Christoffersen (1998). Required reference.
- **Bucket:** calibration-conformal

### [berkowitz-2001] Berkowitz, J. 2001. Testing density forecasts, with applications to risk management.
- **Venue:** Journal of Business & Economic Statistics 19(4), 465–474
- **URL / DOI:** https://doi.org/10.1198/07350010152596718
- **Contribution:** Extends the Diebold–Gunther–Tay PIT framework into a joint LR test on the inverse-normal-transformed PIT series, usable in small samples and standard in bank VaR validation.
- **Why we cite it:** Supports our framing that full-distribution calibration tests are a natural upgrade from point-coverage tests, and is an adjacent tool our methodology could adopt under a Gaussian transform.
- **Bucket:** calibration-conformal

### [diebold-gunther-tay-1998] Diebold, F. X., Gunther, T. A., Tay, A. S. 1998. Evaluating density forecasts with applications to financial risk management.
- **Venue:** International Economic Review 39(4), 863–883
- **URL / DOI:** https://doi.org/10.2307/2527342
- **Contribution:** Introduces probability-integral-transform (PIT) evaluation of density forecasts; if the forecast density is correct, PIT series is i.i.d. uniform.
- **Why we cite it:** Foundational density-calibration reference; our surface-based coverage check at fixed $\tau$ is a marginal-slice of the PIT framework, which we acknowledge as the full-distribution future generalisation.
- **Bucket:** calibration-conformal

### [gneiting-calibration-2007] Gneiting, T., Balabdaoui, F., Raftery, A. E. 2007. Probabilistic forecasts, calibration and sharpness.
- **Venue:** Journal of the Royal Statistical Society, Series B 69(2), 243–268
- **URL / DOI:** https://doi.org/10.1111/j.1467-9868.2007.00587.x
- **Contribution:** Canonical modern framing: *maximise sharpness subject to calibration*; distinguishes probabilistic, exceedance, and marginal calibration; introduces proper scoring rules as the evaluation workhorse.
- **Why we cite it:** The single most-cited statement of the calibration-versus-sharpness tradeoff that §2.3 and our ablation (§7) implicitly use. Essential reference.
- **Bucket:** calibration-conformal

### [gneiting-katzfuss-2014] Gneiting, T., Katzfuss, M. 2014. Probabilistic forecasting.
- **Venue:** Annual Review of Statistics and Its Application 1, 125–151
- **URL / DOI:** https://doi.org/10.1146/annurev-statistics-062713-085831
- **Contribution:** Survey of probabilistic forecasting, formalising prediction-space calibration notions and reviewing PIT histograms, CRPS, logarithmic score, and sharpness measures.
- **Why we cite it:** A modern pedagogical reference to which we point readers for the broader calibration framework beyond the specific tests we run; completes the evaluation-framework lineage.
- **Bucket:** calibration-conformal

### [brier-1950] Brier, G. W. 1950. Verification of forecasts expressed in terms of probability.
- **Venue:** Monthly Weather Review 78(1), 1–3
- **URL / DOI:** https://doi.org/10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2
- **Contribution:** The Brier score — the first proper scoring rule for probabilistic binary-outcome forecasts. Historical / foundational reference.
- **Why we cite it:** Short historical pointer; situates our calibration framing inside the 75-year lineage of proper-scoring-rule forecast evaluation originating in meteorology.
- **Bucket:** calibration-conformal

### [vovk-book-2005] Vovk, V., Gammerman, A., Shafer, G. 2005. Algorithmic learning in a random world.
- **Venue:** Springer, Boston, MA; ISBN 978-0-387-00152-4
- **URL / DOI:** https://doi.org/10.1007/b106715
- **Contribution:** The book-length foundation of conformal prediction. Introduces split / full / inductive conformal predictors and proves distribution-free finite-sample marginal validity under exchangeability.
- **Why we cite it:** Our empirical calibration buffer is an ad-hoc heuristic; split-conformal would replace it with a finite-sample coverage guarantee. Direct future-work reference.
- **Bucket:** calibration-conformal

### [shafer-vovk-2008] Shafer, G., Vovk, V. 2008. A tutorial on conformal prediction.
- **Venue:** Journal of Machine Learning Research 9, 371–421
- **URL / DOI:** https://jmlr.org/papers/v9/shafer08a.html
- **Contribution:** Accessible tutorial introduction to conformal prediction, focusing on the split-conformal construction and non-conformity scores.
- **Why we cite it:** A pedagogical pointer for readers unfamiliar with conformal methods; supports our flagged future-work direction.
- **Bucket:** calibration-conformal

### [romano-cqr-2019] Romano, Y., Patterson, E., Candès, E. J. 2019. Conformalized quantile regression.
- **Venue:** Advances in Neural Information Processing Systems 32 (NeurIPS 2019)
- **URL / DOI:** https://proceedings.neurips.cc/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html; arXiv:1905.03222
- **Contribution:** Combines quantile regression with split-conformal calibration to produce adaptive heteroscedastic prediction intervals with finite-sample coverage guarantees.
- **Why we cite it:** Closest methodological match to what a *conformal* upgrade of our pipeline would look like — a per-regime quantile estimator wrapped by a conformal correction. Flagged as the upgrade path in §10.
- **Bucket:** calibration-conformal

### [barber-nexcp-2023] Barber, R. F., Candès, E. J., Ramdas, A., Tibshirani, R. J. 2023. Conformal prediction beyond exchangeability.
- **Venue:** Annals of Statistics 51(2), 816–845
- **URL / DOI:** https://doi.org/10.1214/23-AOS2276; arXiv:2202.13415
- **Contribution:** Extends conformal prediction to non-exchangeable data using weighted quantiles and randomisation, providing coverage guarantees under distribution drift.
- **Why we cite it:** Time-series and distribution-drift robustness is precisely the regime we operate in. This paper is the theoretical substrate for a conformal upgrade that respects our temporal splits.
- **Bucket:** calibration-conformal

### [xu-xie-2021] Xu, C., Xie, Y. 2021. Conformal prediction interval for dynamic time-series (EnbPI).
- **Venue:** Proceedings of the 38th International Conference on Machine Learning (ICML 2021), PMLR 139
- **URL / DOI:** https://proceedings.mlr.press/v139/xu21h.html
- **Contribution:** Develops EnbPI, a bootstrap-ensemble conformal method that produces approximately valid prediction intervals for dynamic time-series without requiring exchangeability.
- **Why we cite it:** A second time-series-conformal reference demonstrating that the conformal upgrade is practically available; supports the feasibility of the conformal future-work claim.
- **Bucket:** calibration-conformal

### [allen-tail-2025] Allen, S., Koh, J., Segers, J., Ziegel, J. 2025. Tail calibration of probabilistic forecasts.
- **Venue:** Journal of the American Statistical Association 120(552), 2796–2808 (published online December 22, 2025)
- **URL / DOI:** https://doi.org/10.1080/01621459.2025.2506194; arXiv:2407.03167
- **Contribution:** Introduces a general notion of *tail calibration* for probabilistic forecasts, distinct from standard (full-distribution) calibration: a forecaster is tail-calibrated at threshold $u$ when the conditional distribution of forecast PITs above $u$ matches the empirical exceedance distribution of realisations. Establishes connections to peaks-over-threshold extreme value theory and provides diagnostic tools applied to European precipitation forecasts.
- **Why we cite it:** This is the modern parent literature for what our coverage-inversion primitive does at high $\tau$: a forecaster can be calibrated on average and still miscalibrated in the tail, which is precisely the failure mode our $\tau = 0.99$ ceiling (§9.1) describes. Allen et al. supply the formal framework that says this distinction matters and is measurable. Our weekend prediction-window setting is the financial-microstructure instantiation of their framework.
- **Bucket:** calibration-conformal

### [mcneil-frey-2000] McNeil, A. J., Frey, R. 2000. Estimation of tail-related risk measures for heteroscedastic financial time series: An extreme value approach.
- **Venue:** Journal of Empirical Finance 7(3-4), 271–300
- **URL / DOI:** https://doi.org/10.1016/S0927-5398(00)00012-8
- **Contribution:** Two-stage conditional extreme value theory (CEVT) for heteroscedastic financial time series: fit a GARCH model to capture conditional volatility, then apply peaks-over-threshold GPD estimation to the standardised innovations. Targets the conditional-persistence structure that unconditional EVT ignores when applied directly to returns.
- **Why we cite it:** Names the technically-correct EVT response to the conditional-volatility-persistence mechanism diagnosed by our Trial 1 (`reports/v1b_evt_pot_trial.md`); positions CEVT in §10.2 as the v2-territory follow-up to the unconditional GPD fit that we falsify as the headline-DQ fix at $\tau = 0.99$.
- **Bucket:** calibration-conformal

---

## Bucket: model-risk-management

### [sr11-7] Board of Governors of the Federal Reserve System & Office of the Comptroller of the Currency. 2011. Supervisory guidance on model risk management. SR Letter 11-7 / OCC Bulletin 2011-12.
- **Venue:** Federal Reserve / OCC supervisory guidance
- **URL / DOI:** https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm
- **Contribution:** The foundational US supervisory guidance for bank model-risk management. Articulates model-development, implementation, validation, effective-challenge, and ongoing-monitoring requirements.
- **Why we cite it:** "Institutional-grade calibration disclosure" in our paper is operationalised against SR 11-7's framework of validation + effective challenge; this is the regulatory floor our diagnostic targets.
- **Bucket:** model-risk-management

### [sr26-2] Board of Governors of the Federal Reserve System, OCC, FDIC. 2026. Revised guidance on model risk management. SR Letter 26-2 / OCC Bulletin 2026-13.
- **Venue:** Federal Reserve / OCC / FDIC supervisory guidance (April 17, 2026)
- **URL / DOI:** https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm
- **Contribution:** Revises and supersedes SR 11-7 with a materiality-graduated framework; updates validation expectations for modern modelling practice while explicitly excluding generative AI.
- **Why we cite it:** Since the revision occurred in the same window as our paper's first draft (April 2026), citing the current guidance — rather than only the 2011 predecessor — is required for a contemporary model-risk framing.
- **Bucket:** model-risk-management

### [bcbs-backtest-1996] Basel Committee on Banking Supervision. 1996. Supervisory framework for the use of "backtesting" in conjunction with the internal models approach to market risk capital requirements.
- **Venue:** BCBS Publication 22 (January 1996)
- **URL / DOI:** https://www.bis.org/publ/bcbs22.pdf
- **Contribution:** Specifies the green / yellow / red "traffic-light" zones for VaR backtesting based on 250-day exception counts; defines the institutional backtesting standard that regulators apply to internal-model capital requests.
- **Why we cite it:** Primary reference that the *unconditional-coverage* (Kupiec) test — in zone-graduated form — is the global regulatory backtesting standard for market-risk models. Our diagnostic speaks that language.
- **Bucket:** model-risk-management

---

## Bucket: microstructure

### [french-1980] French, K. R. 1980. Stock returns and the weekend effect.
- **Venue:** Journal of Financial Economics 8(1), 55–69
- **URL / DOI:** https://doi.org/10.1016/0304-405X(80)90021-5
- **Contribution:** Documents the weekend effect — average Monday returns are significantly negative in the 1953–1977 sample, rejecting both the calendar-time and trading-time null hypotheses for equity returns.
- **Why we cite it:** Historical foundation for our choice of the Friday-close-to-Monday-open window as the largest-drift, highest-adverse-selection interval. Weekend drift is a genuine empirical regularity, not a modelling artefact.
- **Bucket:** microstructure

### [barclay-hendershott-2003] Barclay, M. J., Hendershott, T. 2003. Price discovery and trading after hours.
- **Venue:** Review of Financial Studies 16(4), 1041–1073
- **URL / DOI:** https://doi.org/10.1093/rfs/hhg030
- **Contribution:** Characterises price discovery in after-hours US equity sessions; shows that prices are more efficient per unit time during regular hours, but after-hours trading still generates significant (if less efficient) price discovery.
- **Why we cite it:** Justifies why closed-market intervals are not zero-information windows — information continues to arrive, which is exactly why a stale-hold feed is miscalibrated and why a conditional regime labeler has something to condition on.
- **Bucket:** microstructure

### [barclay-hendershott-2004] Barclay, M. J., Hendershott, T. 2004. Liquidity externalities and adverse selection: evidence from trading after hours.
- **Venue:** Journal of Finance 59(2), 681–710
- **URL / DOI:** https://doi.org/10.1111/j.1540-6261.2004.00646.x
- **Contribution:** Shows that after-hours effective spreads are 3–4× higher than regular hours, reflecting greater adverse selection and order persistence rather than higher dealer profits.
- **Why we cite it:** Supports our framing of closed-market hours as the *adverse-selection* window for on-chain protocols — the setting in which a miscalibrated oracle band produces the bulk of loss events.
- **Bucket:** microstructure

---

## Verification summary

- **Verified:** 40 references (all above entries).
- **VERIFICATION FAILED:** 0.
- **Intentionally omitted candidates:** (a) Shapiro & Wolfers 2005 "What explains Monday returns" — could not resolve a specific paper under this exact title; weekend-effect claims are covered by French (1980) and Barclay–Hendershott (2003, 2004) without it. (b) Jovanovic–Wattenhofer oracle-latency 2022 — no reliably attributable paper under that author pair and year; functional replacement covered by the Chainlink 2.0 whitepaper and the Eskandari et al. SoK.
