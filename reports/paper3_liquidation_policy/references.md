# References — Paper 3 (Optimal Liquidation Policy Defaults Under Calibrated Oracle Uncertainty)

Working bibliography. Verified entries follow the `[tag]` convention used in Paper 1's `references.md` (`../paper1_coverage_inversion/references.md`). Cross-references inherited from Paper 1 are listed by tag only and not re-stated below; see Paper 1 for the full entry.

Buckets (per `plan.md` §16.3):
- **calibration-coverage** — Kupiec / Christoffersen / conformal upgrades for the policy's input
- **defi-lending-theory** — formal lending-protocol modelling and empirical liquidation studies
- **production-risk-methodology** — Gauntlet / Chaos Labs / governance literature framing parameter selection as optimization
- **off-hours-microstructure** — weekend / overnight / adaptive-leverage / perp microstructure literature
- **production-anchors** — Kamino, Aave Horizon, Chainlink 24/5 docs, Kraken / backed methodology

---

## Bucket: production-anchors

### TODO [kamino-xstocks] Kamino Finance. 2025. *xStocks integration: liquidation ladder, soft liquidations, dynamic penalties*.
- **Venue:** Kamino docs / blog (multi-page).
- **Contribution:** Defines the production liquidation ladder Paper 3 maps onto: TWAP/EWMA defenses, soft liquidations, dynamic penalty schedule, per-asset risk multipliers.
- **Why we cite it:** Primary deployment-target reference. Paper 3 does not propose a new protocol; it shows how the calibrated band plugs into Kamino's existing ladder.
- **Verification status:** TODO — capture exact URLs (likely several Kamino docs pages plus the xStocks integration announcement).

### TODO [chainlink-24-5] Chainlink Labs. 2025. *24/5 US equities feeds: weekend coverage guidance*.
- **Venue:** Chainlink product documentation.
- **Contribution:** Explicit recommendation that consumers extend weekend pricing using prices of tokenized stocks on secondary CEX/DEX venues.
- **Why we cite it:** The cleanest empirical demonstration that the industry still lacks a non-circular closed-market policy primitive. Sets up Paper 3's closed-market gap argument.
- **Verification status:** TODO.

### TODO [kraken-xstocks] Kraken (Backed). 2025. *xStocks methodology and FAQ*.
- **Venue:** Kraken / Backed product documentation.
- **Contribution:** Off-hours fair-value methodology citing ATS venues, index futures, and internal models, with wider weekend spreads.
- **Why we cite it:** Pragmatic validation that Paper 3's regime-aware band is directionally aligned with how desks already approximate fair value off-hours.
- **Verification status:** TODO.

### TODO [aave-horizon] Aave. 2025. *Aave Horizon: institutional RWA risk and liquidation framework*.
- **Venue:** Aave governance forum / documentation.
- **Contribution:** Acknowledges custom liquidation logic, custodial delay, and market-closure handling for institutional RWA collateral.
- **Why we cite it:** Confirms that institutional venues already encode time-of-market and operational constraints; Paper 3's regime-aware policy is a standardisation of what sophisticated venues already do by hand.
- **Verification status:** TODO.

### TODO [gauntlet-methodology] Gauntlet. 2024–2025. *Methodology notes on liquidation parameter optimization*.
- **Venue:** Gauntlet research blog / governance posts.
- **Contribution:** Frames liquidation-parameter selection as constrained optimization over agent-based simulations.
- **Why we cite it:** Establishes that production stacks already use the optimization framing; Paper 3 supplies the calibrated-uncertainty input that current optimization does not have.
- **Verification status:** TODO — multiple blog posts; pick canonical one.

### TODO [chaos-labs-methodology] Chaos Labs. 2024–2025. *Risk modeling methodology and black-swan handling*.
- **Venue:** Chaos Labs documentation / blog.
- **Contribution:** Same optimization framing as Gauntlet plus an explicit admission that black-swan tails are not statistically testable in the main simulation stack and are handled separately.
- **Why we cite it:** Aligns with Paper 3's calibration-buffer disclosure approach: tails get explicit treatment, not silent confidence.
- **Verification status:** TODO.

### TODO [redstone-weekend-gap] RedStone. 2025. *Weekend dislocation framing for tokenized equities*.
- **Venue:** RedStone blog (specific post TBD).
- **Contribution:** Adversarial corroboration that weekend dislocation remains unresolved across oracle providers.
- **Why we cite it:** Used sparingly to show that even a competing oracle provider acknowledges the gap.
- **Verification status:** TODO.

---

## Bucket: defi-lending-theory

### TODO [perez-defi-2020] Perez, D., Werner, S. M., Xu, J., Livshits, B. 2020. Liquidations: DeFi on a knife-edge.
- **Venue:** Financial Cryptography 2021 / arXiv:2009.13235.
- **Contribution:** Empirical analysis of DeFi lending liquidations and threshold dynamics.
- **Why we cite it:** Justifies why liquidation policy is an economic decision problem rather than a pure oracle-design problem.
- **Verification status:** TODO — confirm exact venue + year.

### TODO [chitra-defi-leverage] Chitra, T., et al. (year TBD). DeFi leverage and fragility.
- **Venue:** TBD.
- **Contribution:** Models leverage constraints under information not directly observable on-chain.
- **Why we cite it:** Optimal thresholds depend on information the chain does not directly observe — the framing Paper 3 uses for calibrated-uncertainty inputs.
- **Verification status:** TODO — identify specific paper.

### TODO [aave-governance-liquidation] Aave Governance. 2024–2025. *Optimal liquidation and protocol-equity governance posts*.
- **Venue:** Aave governance forum.
- **Contribution:** Mathematical language for liquidation-policy choice already adopted in DAO governance.
- **Why we cite it:** Shows Paper 3 plugs into existing production/governance workflow.
- **Verification status:** TODO.

---

## Bucket: off-hours-microstructure

### TODO [adaptive-ltv-paper] Adaptive-LTV / liquidity-of-time literature.
- **Venue:** TBD — academic precedent for time-varying leverage constraints.
- **Why we cite it:** Closest in-spirit precedent that leverage constraints should move with market-closure or off-hours conditions.
- **Verification status:** TODO — identify the strongest 1-2 papers.

### TODO [perp-mark-index] Perpetuals / synthetic-equity venue documentation.
- **Venue:** Drift, Hyperliquid, dYdX, GMX docs.
- **Contribution:** Mark/index handling under continuous trading of discontinuously anchored underlyings.
- **Why we cite it:** Practical comparators for a continuous-quoting context that explicitly manages closed-market uncertainty.
- **Verification status:** TODO — pick canonical references per venue.

---

## Cross-references inherited from Paper 1

The following Paper 1 entries will be cited in Paper 3 without restatement here. See `../paper1_coverage_inversion/references.md` for full bibliographic entries.

- `[kupiec-1995]`, `[christoffersen-1998]` — coverage tests Paper 3 inherits as the calibrated-input contract.
- `[bcbs-backtest-1996]` — Basel traffic-light framework for the institutional vocabulary.
- `[allen-tail-2025]` — tail-calibration parent literature; relevant when policy meets the high-$\tau$ ceiling.
- `[romano-cqr-2019]`, `[barber-nexcp-2023]`, `[xu-xie-2021]` — conformal upgrades for the policy input.
- `[french-1980]`, `[barclay-hendershott-2003]`, `[barclay-hendershott-2004]` — weekend / after-hours microstructure.
- `[madhavan-sobczyk-2016]` — ETF dynamics for the tokenized-equity comparison.
- `[cong-tokenized-2025]` — empirical motivation: weekend price discovery migrating to crypto-native venues.
- `[hasbrouck-1995]`, `[hasbrouck-2003]` — price-discovery methodology underlying Soothsayer's factor switchboard.
- `[chainlink-2]`, `[chainlink-streams]`, `[chainlink-v10]`, `[chainlink-v11]`, `[redstone-live]`, `[pyth-conf]`, `[pyth-pro]`, `[blueocean-pyth]`, `[switchboard]` — incumbent oracle landscape (per-schema Chainlink pins and the Pyth Pro / Blue Ocean overnight integration added in the 2026-05-02 oracle-comparator drift fix to Paper 1).
- `[flashboys-2]` — MEV / adversarial-ordering context for §12.5 non-claims.
- `[sok-oracles]`, `[bis-oracle]`, `[uma]`, `[tellor]` — oracle-integrity-vs-calibration distinction.

---

## Additional cross-reference

- `[andreoulis-fair-oev]` — Andreoulis et al. 2026 — relevant for §12.5 (MEV / OEV non-claims) and for positioning the policy paper against existing liquidation / OEV work.

---

## Self-reference

### [soothsayer-paper-1] Paper 1 — *Empirical coverage inversion*.
- Defines the calibrated band that Paper 3 consumes.

---

## Verification summary

- **Verified:** 0 Paper-3-specific references (all TODO; production anchors and DeFi-lending-theory references need to be chased before §2 is drafted).
- **Inherited from Paper 1 (no re-verification needed):** 17 entries (the cross-reference list above).
- **Additional cross-reference:** 1 entry (andreoulis-fair-oev).

Pre-draft action: production anchors (Kamino, Chainlink 24/5, Aave Horizon, Gauntlet, Chaos Labs, Kraken/backed) are the load-bearing citations for the introduction. They should be verified first.
