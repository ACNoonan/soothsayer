# References — Paper 2 (OEV Mechanism Design Under Calibration-Transparent Oracles)

Working bibliography. Verified entries follow the `[tag]` convention used in Paper 1's `references.md` (`../paper1_coverage_inversion/references.md`). Cross-references inherited from Paper 1 are listed by tag only and not re-stated below; see Paper 1 for the full entry.

Buckets:
- **oev-mechanism** — production OEV-recapture systems and academic OEV mechanism design
- **auction-theory** — foundational mechanism design / auction theory
- **pbs-builder** — proposer-builder separation, censorship-resistance, order-flow auctions
- **defi-liquidations** — empirical lending-protocol liquidation studies
- **calibration-transparent-oracle** — Paper 1 self-references and tail-calibration parent literature

---

## Bucket: oev-mechanism

### [andreoulis-fair-oev] Andreoulis, N., Maggio, M. D., Merino, L. H., Montag, K., Ward, J. 2026. Designing for Fair Oracle Extractable Value: A Theoretical Framework and Empirical Findings from DeFi.
- **Venue:** *Mathematical Research for Blockchain Economy* (MARBLE 2025), Lecture Notes in Operations Research, Springer.
- **URL / DOI:** https://doi.org/10.1007/978-3-032-13377-9_3 · https://infoscience.epfl.ch/entities/publication/c394fa03-ca56-417f-a627-57a132a9c309
- **Contribution:** Studies OEV as a distinct rent/risk channel in DeFi. Using granular Aave V2/V3 liquidation data across Ethereum and major rollups (2023–2025), documents that OEV is large, heavy-tailed, and increasingly captured by vertically integrated builder–searcher coalitions during market stress. Introduces a stylised model of the **Oracle Update Rebate Window (OURW)** mechanism with a refund + fallback-window structure; establishes conditions under which censorship is unprofitable and how refund rates, fallback windows, and builder competition interact to deter attacks.
- **Why we cite it:** Primary academic anchor for Paper 2. The OURW mechanism is the opaque-oracle baseline (M2) we extend under the calibration-transparency assumption (M3); their censorship-proofness inequality is what we re-derive in C3.
- **Bucket:** oev-mechanism

### [chainlink-svr] Chainlink Labs. 2024. Smart Value Recapture (SVR): a Chainlink-powered MEV recapture solution for DeFi.
- **Venue:** Chainlink product announcement / engineering blog
- **URL / DOI:** https://blog.chain.link/chainlink-smart-value-recapture-svr/ · https://blog.chain.link/chainlink-svr-analysis/
- **Contribution:** Top-of-block auctions co-developed with Flashbots; the right to perform the first liquidation immediately after a Chainlink oracle update is auctioned, with proceeds rebated to the protocol. Treats the oracle as a price-emitting black box.
- **Why we cite it:** Production exemplar of the M1 mechanism class (opaque-oracle + top-of-block auction). Establishes that opaque-oracle OEV recapture is already deployed at scale and provides a reference parameter set (refund rate, latency) for our simulator.
- **Bucket:** oev-mechanism
- **Verification status:** URL confirmed; recheck author/title styling at draft time against the canonical Chainlink whitepaper or follow-up technical doc when published.

### [redstone-oev-blog] RedStone. 2024–2025. *Oracle Extractable Value in DeFi* (blog series).
- **Venue:** RedStone engineering blog (multi-part series, July 2024 onward)
- **URL / DOI:** https://blog.redstone.finance/2024/07/05/oracle-extractable-value-in-defi-part-1what-is-oev-and-how-does-it-work/
- **Contribution:** Industry framing of OEV as a distinct MEV channel with oracle updates as the trigger event. Subsequent posts describe RedStone Atom, an atomic OEV auction mechanism that bundles oracle update + liquidation in a single transaction.
- **Why we cite it:** Production exemplar of the M1 mechanism class with atomic execution. Useful for the practical-landscape section (§11.2 of plan).
- **Bucket:** oev-mechanism
- **Verification status:** Blog series; cite specific posts with exact dates at draft time.

### [api3-oev-litepaper] API3 DAO. 2024. *Oracle Extractable Value (OEV) through Order Flow Auctions* (litepaper).
- **Venue:** API3 DAO public litepaper, GitHub-hosted
- **URL / DOI:** https://raw.githubusercontent.com/api3dao/oev-litepaper/main/oev-litepaper.pdf
- **Contribution:** First-party-oracle order-flow auction model in which OEV proceeds (up to ~80%) are returned to integrating dApps in API3 token. Companion Medium series by Burak Benligiray expands the design rationale.
- **Why we cite it:** Production exemplar of the order-flow-auction variant of the M1/M2 class. Useful contrast to top-of-block (Chainlink SVR) and atomic (RedStone Atom) variants.
- **Bucket:** oev-mechanism
- **Verification status:** URL confirmed; capture exact litepaper version/date at draft time.

### [uma-oval] UMA Project. 2024. *Oval: a permissionless MEV recapture system*.
- **Venue:** UMA Protocol product announcement
- **URL / DOI:** TODO — confirm exact announcement post URL and date.
- **Contribution:** MEV-recapture system targeted at lending dApps consuming UMA price feeds; integrates with Flashbots for ordering control.
- **Why we cite it:** Production exemplar adjacent to the OURW class with UMA-specific oracle staleness assumptions.
- **Bucket:** oev-mechanism
- **Verification status:** TODO — chase down primary source.

---

## Bucket: auction-theory

### [myerson-1981] Myerson, R. B. 1981. Optimal auction design.
- **Venue:** *Mathematics of Operations Research* 6(1), 58–73.
- **URL / DOI:** https://doi.org/10.1287/moor.6.1.58
- **Contribution:** Foundational result on revenue-maximising auction design under independent private values; introduces the "virtual valuations" technique.
- **Why we cite it:** Reference point for the optimal-auction comparison in §15.5 of the plan; anchors the rent-monotonicity proof (C1).
- **Bucket:** auction-theory
- **Verification status:** Standard reference.

### [milgrom-weber-1982] Milgrom, P. R., Weber, R. J. 1982. A theory of auctions and competitive bidding.
- **Venue:** *Econometrica* 50(5), 1089–1122.
- **URL / DOI:** https://doi.org/10.2307/1911865
- **Contribution:** Introduces affiliated values and the **linkage principle**: making more public information available in an auction (weakly) raises seller revenue under affiliation.
- **Why we cite it:** Direct theoretical anchor for C1. Publishing the calibration band increases public information; the linkage principle predicts (weakly) higher auction revenue, which is the rent-monotonicity-in-band-sharpness result.
- **Bucket:** auction-theory
- **Verification status:** Standard reference.

### [krishna-auction-theory] Krishna, V. 2009. *Auction Theory* (2nd edition).
- **Venue:** Academic Press / Elsevier
- **URL / DOI:** ISBN 978-0-12-374507-1
- **Contribution:** Standard graduate textbook on auction theory; covers private-value, common-value, and affiliated-value settings; revenue equivalence; multi-unit auctions.
- **Why we cite it:** Pedagogical reference for the auction-format taxonomy and equilibrium-derivation tools used in the theoretical section.
- **Bucket:** auction-theory
- **Verification status:** Standard reference.

### [bulow-klemperer-1996] Bulow, J., Klemperer, P. 1996. Auctions versus negotiations.
- **Venue:** *American Economic Review* 86(1), 180–194.
- **URL / DOI:** https://www.jstor.org/stable/2118262
- **Contribution:** Shows that adding one more bidder to a standard auction dominates running an optimal mechanism with fewer bidders.
- **Why we cite it:** Useful for sensitivity analysis: comparing "more searchers" vs "tighter band" as alternative levers for shrinking searcher rents.
- **Bucket:** auction-theory
- **Verification status:** Standard reference.

---

## Bucket: pbs-builder

### TODO [heimbach-pbs] Heimbach, L., et al. (year TBD). Empirical analysis of proposer-builder separation on Ethereum.
- **Venue:** TBD — likely AFT, FC, or arXiv preprint.
- **Contribution:** Empirical work on builder concentration, MEV-Boost relay dynamics, and validator-builder relationships post-Merge.
- **Why we cite it:** Grounds the builder-concentration assumption used in §6 (the formal model) and §9 (sensitivity analysis).
- **Bucket:** pbs-builder
- **Verification status:** TODO — settle on the most authoritative single reference (likely Heimbach + Wang or similar 2024–2025 paper).

### TODO [wadhwa-ofa] Wadhwa, S., Bahrani, A., Ferreira, M. V. X., et al. (year TBD). Order flow auctions and mechanism design.
- **Venue:** TBD — Flashbots research preprint or AFT/EC.
- **Contribution:** Theoretical and empirical study of order-flow auction design.
- **Why we cite it:** Closely related production-mechanism research that motivated API3 OEV and adjacent designs.
- **Bucket:** pbs-builder
- **Verification status:** TODO.

---

## Bucket: defi-liquidations

### TODO [gudgeon-2020] Gudgeon, L., Perez, D., Harz, D., Livshits, B., Gervais, A. 2020. The decentralized financial crisis.
- **Venue:** Crypto Valley Conference on Blockchain Technology (CVCBT) 2020 / arXiv:2002.08099.
- **Contribution:** Stress-tests DeFi lending protocols under historical price shocks; quantifies under-collateralisation and liquidation behaviour.
- **Why we cite it:** Empirical baseline for the historical-replay design and a precedent for stress-testing lending protocols against extreme price moves.
- **Bucket:** defi-liquidations
- **Verification status:** TODO — confirm exact title/year.

### TODO [qin-cefi-defi] Qin, K., et al. (year TBD). Empirical study of CeFi/DeFi liquidation cascades.
- **Bucket:** defi-liquidations
- **Verification status:** TODO — placeholder; identify the strongest single empirical-cascade reference.

---

## Cross-references inherited from Paper 1

The following Paper 1 entries will be cited in Paper 2 without restatement here. See `../paper1_coverage_inversion/references.md` for full bibliographic entries.

- `[allen-tail-2025]` — Allen et al., JASA 2025 — tail-calibration parent literature; relevant when band sharpness interacts with tail behaviour.
- `[flashboys-2]` — Daian et al. 2020 — broader MEV framing.
- `[sok-oracles]` — Eskandari et al. 2021 — opaque-oracle assumption baked into existing oracle-design surveys.
- `[chainlink-2]`, `[chainlink-streams]` — Chainlink design references for the M1 mechanism description.
- `[redstone-live]` — RedStone 24/7 product context for the RedStone Atom comparison.
- `[pyth-conf]` — Pyth confidence-interval semantics.

---

## Self-reference (Paper 1 of the trilogy)

### [soothsayer-paper-1] (this trilogy) Paper 1 — *Empirical coverage inversion: a calibration-transparency primitive for decentralized RWA oracles*.
- **Status:** in submission / arXiv pending.
- **Why we cite it:** Defines the calibration-transparent oracle primitive that Paper 2's mechanism design assumes as input. Paper 2 cites Paper 1 for the formal oracle output structure $(\hat P_t, [L_t, U_t], q_\text{served}, \rho_t, r_t)$ and its empirical calibration evidence.

---

## Verification summary

- **Verified:** 5 references (andreoulis-fair-oev, myerson-1981, milgrom-weber-1982, krishna-auction-theory, bulow-klemperer-1996).
- **TODO — verification pending:** chainlink-svr (URL only), redstone-oev-blog (specific post pending), api3-oev-litepaper (version/date pending), uma-oval (primary source), heimbach-pbs, wadhwa-ofa, gudgeon-2020, qin-cefi-defi.
- **Inherited from Paper 1 (no re-verification needed):** allen-tail-2025, flashboys-2, sok-oracles, chainlink-2, chainlink-streams, redstone-live, pyth-conf.

Pre-draft action: convert each TODO entry to a Verified entry by chasing primary sources before §2 is drafted.
