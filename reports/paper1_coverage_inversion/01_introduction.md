# §1 — Introduction

Tokenised equities and other real-world assets (RWAs) on public blockchains trade 24/7. Their underlying price-discovery venues do not. A US equity listed on NASDAQ is open 6.5 hours per weekday — roughly 32% of wall-clock time. In the other 68% the price continues to move (earnings, macro prints, overseas sessions) but the venues that establish reference prices are closed. The JELLYJELLY incident on Hyperliquid (March 2025) drove ~$12M of HLP losses through a manipulable single-venue oracle path; a Volcano Exchange post-mortem of a tokenized-asset perp episode documents $9.21M in Hyperliquid liquidations exceeding the Binance volume that fed the oracle, and identifies the propagation mechanism as "uncertainty present in the input, not represented in the output." Any DeFi protocol that accepts tokenised RWAs as collateral or as inputs to an automated market maker must answer at every block: *with the underlying venue closed, what is the fair price — and how uncertain is it?*

The question recurs across the broader RWA wave moving on-chain in 2025–2026: tokenised equities (xStocks on Solana, Backed-issued tokens), treasuries (BlackRock BUIDL, Ondo OUSG; >$5B AUM), commodities (Paxos PAXG), and the next wave of credit and FX. Every asset class with a continuous off-hours information set inherits the same closed-market-pricing problem and would benefit from the same calibration-transparent risk-reporting primitive. The methodology fits asset classes with such a signal; it does not fit instruments without one (illiquid commodities, pure NAV real estate). §9.8 enumerates the generalisation map.

## 1.1 How existing oracles answer, and what they leave unanswered

Five classes of RWA oracle are deployed at scale today. Each resolves the *what*; none publishes a *calibration claim verifiable against public data at the aggregate feed level* — a statement of the form *"over $N$ historical prediction windows, our 95% band contained the realised price $N_\text{in}$ times."*

| Archetype | Representative | What a consumer sees |
|---|---|---|
| Stale-hold | Chainlink Data Streams v10 [chainlink-v10] | Last trade held forward + binary stale/live flag; no `bid`/`ask`/confidence on the wire |
| Synthetic-marker | Chainlink Data Streams v11 [chainlink-v11] | Weekend `bid`/`ask` with a `.01` suffix at 100% incidence on SPYx/QQQx/TSLAx (§6.5.2) — generated bookends, not real quotes |
| Publisher-dispersion metric | Pyth regular [pyth-agg; pyth-conf] | $\sigma$ across permissioned publishers; not an aggregate coverage claim; collapses to near-zero at venue close |
| Executable-overnight | Pyth Pro / Blue Ocean [pyth-pro; blueocean-pyth] | Real 24/5 book Sun–Thu 8 PM – 4 AM ET; does not cover the canonical xStock weekend; paid enterprise |
| Undisclosed methodology | RedStone Live [redstone-live]; v10 `tokenizedPrice` | Continuous closed-market value; methodology described qualitatively only |

Two structural observations. (i) Pyth's documentation [pyth-conf] recommends *individual publishers* calibrate to ~95%, but this is per-publisher self-attestation, not a verifiable property of the aggregate. (ii) Cong et al. [cong-tokenized-2025] document that off-hour tokenised-stock returns anticipate Monday opens, so the on-chain SPL xStock is informationally distinct from its underlier in exactly the closed-market window the oracle covers; feeds pricing the underlier ticker carry an additional instrument-mismatch gap. None publishes the rolling dataset from which an aggregate-level calibration claim could be independently reproduced.

## 1.2 Coverage as a first-class API parameter

The design point of this paper is an oracle whose *product contract* is a calibration statement. Instead of publishing a single band and leaving its coverage level implicit, we take consumer-specified target coverage $\tau \in (0,1)$ as a request parameter and return the band that has *empirically* delivered coverage $\tau$ on a rolling historical sample, stratified by asset and pre-publish regime.

For a point estimator $\hat P_{\text{Mon},r}(s)$ trained per regime $r = \rho(\mathcal{F}_t)$ and a per-regime conformal quantile $q_r(\tau)$ trained on absolute relative residuals on a held-out calibration set, the deployed v2 / M5 architecture serves at consumer target $\tau$ via

$$\bigl[\hat P_{\text{Mon},r}(s) \cdot \bigl(1 - c(\tau') \, q_r(\tau')\bigr),\;\hat P_{\text{Mon},r}(s) \cdot \bigl(1 + c(\tau') \, q_r(\tau')\bigr)\bigr],\quad \tau' = \tau + \delta(\tau),$$

where $c(\tau)$ is an OOS-fit multiplicative bump that closes the train-OOS distribution-shift gap, and $\delta(\tau)$ is a walk-forward-fit shift that pushes per-split realised coverage above nominal. Twenty deployment scalars total: 12 trained per-regime quantiles, 4 OOS-fit $c(\tau)$, 4 walk-forward-fit $\delta(\tau)$ — matching v1's 4-scalar `BUFFER_BY_TARGET` parameter budget.

Two properties follow that are absent from incumbents: (1) **Auditability** — the 20 scalars and the per-Friday $\hat P_{\text{Mon},r}$ are deterministic functions of public data; any third party can reconstruct the artefact and verify a served band. (2) **Served-coverage receipts** — every read exposes $(\tau',\, c(\tau'),\, q_r(\tau'),\, r)$ alongside the band, so a protocol integrator can log it, backtest, and challenge the provider if realised rate drifts. The framework traces to Christoffersen [christoffersen-1998] and SR 11-7 [sr11-7] / SR 26-2 [sr26-2] model-risk guidance; what is new is the application to a decentralised oracle with a consumer-facing SLA on realised coverage rather than on point accuracy.

## 1.3 What this paper shows

We evaluate on 5,996 weekend prediction-window rows (639 weekends × 10 symbols) spanning 2014-01-17 through 2026-04-24: seven US equities/ETFs (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD), gold (GLD), long treasuries (TLT), and a Bitcoin-proxy equity (MSTR). Each window runs Friday 16:00 ET to Monday 09:30 ET. The contribution is the *primitive* surrounding any point estimator — the artefact, its serving-time lookup, and the audit receipts — together with empirical evidence that this primitive delivers its coverage promise.

Headline empirical claims:

- **At $\tau = 0.95$ on the 2023+ slice (1,730 rows, 173 weekends):** realised $0.950$, Kupiec $p_{uc} = 0.956$, Christoffersen $p_{ind} = 0.912$, mean half-width $354.5$ bps — a 20% reduction over v1 on the same slice (CI excludes zero on width). The 12 quantiles are held-out (frozen on the 4{,}266 pre-2023 rows); the 4+4 schedules are deployment-tuned on the same OOS slice, matching v1's parameter budget (deployment-calibrated; §9.3). A six-split walk-forward passes Kupiec at every anchor ($p$ = 0.43, 0.37, 0.36, 0.32 at $\tau \in \{0.68, 0.85, 0.95, 0.99\}$); a four-anchor split-date sensitivity (§6.3) holds the headline within $\pm 0.05$pp of nominal. We use $\tau = 0.95$ as the paper's primary *oracle-validation* target; the deployed default for protocol consumption is $\tau = 0.85$, picked on protocol-EL grounds (Paper 3).

- **At $\tau = 0.99$:** realised $0.990$, $p_{uc} = 0.942$ — closing the v1 tail ceiling at $0.972$ at the cost of a 22% wider band ($677.5$ vs $522.8$ bps). Bandwidth-for-honesty: a consumer requesting $\tau = 0.99$ now receives a band whose realised coverage matches the request.

- **Two-layer ablation.** The constant-buffer stress test (§7.1) rules out the deployable simpler baseline (train-fit constant buffer fails Kupiec by 5–14pp on OOS). The Mondrian-by-regime ablation (§7.2) keeps the classifier and replaces v1's forecaster machinery — 19–20% narrower than v1 at indistinguishable Kupiec calibration through $\tau \le 0.95$.

- **Diagnostics define the v3 roadmap.** Berkowitz rejects ($\text{LR} = 173.1$); DQ at $\tau = 0.95$ rejects ($p = 5.7 \times 10^{-6}$). The diagnosis — the classifier is a coarse three-bin index — points to v3 gains: full-distribution conformal, finer regime structure, richer on-chain signals (§10).

These claims are about the oracle interface and serving-time calibration; they do not prove the same $\tau$ is the welfare-optimal liquidation rule (Paper 3).

## 1.4 Contributions and structure

**C1.** Coverage inversion as an oracle primitive (§3). **C2.** A 12-year Mondrian split-conformal-by-regime calibration on public data, with a 20-scalar artefact rebuildable by any third party (§4, §5). **C3.** Held-out-quantile, deployment-calibrated Kupiec + Christoffersen validation in the form required by institutional model-risk management (§6), with DQ and Berkowitz disclosures narrowing the empirical content to per-anchor calibration. **C4.** A two-layer ablation with bootstrap CIs (§7) isolating M5 as 19–20% narrower than v1 at indistinguishable Kupiec calibration through $\tau \le 0.95$.

We do not claim point-accuracy or absolute bandwidth dominance over a hand-tuned consumer-supplied wrap of an existing publisher-dispersion feed (§6.5 reports width parity at matched coverage against a Pyth $\pm 50 \cdot \mathrm{conf}$ wrap on the available subset); the contribution is the calibration receipt and its reproducibility, not the band width.

§2 surveys related work; §3 gives the problem statement; §4 the methodology; §5 the data and regime labeler; §6 calibration results; §7 the ablation; §8 the serving-layer system; §9 limitations; §10 future work.
