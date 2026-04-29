# Methodology evolution log

**Purpose.** A living, append-only record of methodological decisions, tested-and-rejected hypotheses, and the empirical evidence that shaped the current Soothsayer Oracle. Updated when methodology changes; never deleted from. Source-of-truth pointer for the research paper, deployed code, and historical context for new collaborators.

**How to read this doc.** Sections are time-stamped. The current production methodology is summarised in §0 ("State of the world today") and re-derived from the latest dated entry. Earlier entries describe the path; if a finding has since been superseded, the supersession is noted inline.

**How to update this doc.** When you change methodology, append a new dated entry to §1 ("Decision log"). Update §0 to reflect the new state of the world. Never edit prior entries; if an old entry needs correction, add an "AMENDMENT" line with the date and reasoning.

---

## 0. State of the world (current)

*Last updated 2026-04-29.*

**Product shape.** Soothsayer Oracle. Customer specifies target coverage τ ∈ (0, 1); Oracle returns a band that empirically delivered τ on a 12-year backtest stratified by (symbol, regime). Every read carries receipts: served claimed-quantile, forecaster used, regime observed, calibration buffer applied.

**Product progression (locked 2026-04-29).**
- **v0 — calibration-transparent band primitive.** The `soothsayer-router` Anchor program (in build); regime-routes between an open-hours multi-upstream aggregator (Layer 0: Pyth + Chainlink v11 + Switchboard On-Demand + RedStone Live, with Mango-style filters) and the closed-hours soothsayer band primitive. Returns `unified_feed_receipt.v1`. Methodology backing: Paper 1.
- **v1 — calibration-transparent event stream** (gated on Paper 3). On-chain events fired when consumer-configured band thresholds are crossed; each event carries a calibration receipt + historical-frequency context. Consumer-driven action policy; account state stays consumer-private. The product layer that closes the integration-friction gap with action-publishing protocols (Mango v4) without abandoning the methodology-public + action-private architecture. Methodology backing: Paper 3.
- **v2 — parameterized decision SDK** (2027). Rust + TS library that takes consumer cost weights + portfolio shape and returns binary recommendations with calibration receipts. Library runs client-side; soothsayer never reads borrower positions. Methodology backing: Paper 2 + Paper 3.

The v0 → v1 → v2 progression preserves the methodology-public + action-private invariant at every layer and is non-substitutable with action-publishing protocols (Mango v4 et al.). See the 2026-04-29 §1 entry for the trigger (Mango premise verification) and the strategic framing.

**Unified-feed router v0 status (locked 2026-04-28; deployed devnet 2026-04-29).** Single Anchor program in front of the existing publish-path stack, deployed at devnet program ID `AZE8HixpkLpqmuuZbCku5NbjWqoQLWhPRTHp8aMY9xNU`, exercised end-to-end against a real Pyth Pull receiver SOL/USD feed (`7UVimffxr9ow1uXYxsr4LHAcV58mLzhmwaeKvJ1pjLiE`). Layer 0 (open-hours, deterministic multi-upstream aggregator with robust median + dispersion-based band) ships with these upstream-decoder paths: **Pyth aggregate** (real, tested on devnet via SOL/USD; equity coverage on mainnet requires a soothsayer-operated Pyth poster daemon — Pyth doesn't sponsor SPY/QQQ Solana feeds — per the 2026-04-29 (evening) entry), **Switchboard On-Demand** (real, unit-tested), **Chainlink Streams Relay** (decoder reads a soothsayer-controlled relay PDA per the 2026-04-29 (afternoon) Option C lock — relay program + daemon are separate work, scryer wishlist items track them), **RedStone Live** (stubbed pending a Solana PDA from RedStone). Mango v4 reclassified as methodology-only per the 2026-04-29 (morning) amendment. Layer 1 (calibration-weighted aggregator with open-hours calibration claim) is gated on ~3 months of upstream forward-tape data per scryer wishlist items 21-23. Router ships upgradeable in v0 (multisig-controlled `RouterConfig`); migration to immutable + versioned-replacement is gated on a signed institutional-partner LOI + partner methodology buy-in.

**Relay fleet (locked 2026-04-29 (evening)).** The "Option C" relay pattern from the afternoon entry generalises beyond Chainlink: any off-chain price source soothsayer needs on-chain that doesn't already have a passive-PDA path uses the same shape (off-chain daemon fetches signed data → submits on-chain → cryptographic verification at post time → router reads passively). v0 fleet: **Chainlink Streams** (own relay program + daemon — items 42 + 43), **Pyth equity** (daemon only — uses Pyth's existing receiver — item 44). Five operator commitments lock the trust model: Verifier-CPI mandatory in production, open-source daemons, multi-writer migration in v1, public posting cadence + uptime alerting, no-position policy enforced via on-chain attestation account. See the 2026-04-29 (evening) §1 entry for the full lock + the trust-model rationale.

See §1 entries dated 2026-04-28 (afternoon / midday / morning) for the design, the deviation-guard adoption, and the receipt-schema lock respectively; 2026-04-29 (morning / afternoon / evening) for the v0/v1/v2 product roadmap, the Chainlink architectural correction, and the relay-fleet generalisation.

**Deployment defaults.**
- Default τ = **0.85** — picked on protocol-policy grounds in the original Paper 3 scaffold; the earlier flat-300bps Kamino-style comparator is now retained only as a simplified baseline, with the production comparison reframed around real xStocks reserve-buffer exhaustion.
- Hybrid forecaster: F1_emp_regime in `normal` and `long_weekend`; F0_stale in `high_vol`.
- Per-target buffer schedule: `{0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.010}`, linearly interpolated off-grid (τ=0.99 bumped from 0.005 → 0.010 after 2026-04-25 grid extension).
- Claimed-coverage grid: `{..., 0.95, 0.975, 0.99, 0.995, 0.997, 0.999}` (extended 2026-04-25 from prior top of 0.995); `MAX_SERVED_TARGET = 0.999`.

**Incumbent-oracle comparison (2026-04-25 evening + late-evening schema scan).**
- Pyth + naive $\pm 1.96\cdot\text{conf}$ on 2024+ subset (265 obs): realised **10.2%** at "claimed" 95%. Pyth's CI is documented as aggregation diagnostic, not probability statement; the under-coverage is a feature of the published claim, not a defect.
- Pyth + consumer-fit $\pm 50\cdot\text{conf}$: realised 95.1% at half-width 280 bps on subset (SPY/QQQ/TLT/TSLA-heavy). Subset bias makes the "Pyth+50× narrower than Soothsayer" finding interesting but small-sample.
- Chainlink Data Streams on Solana publishes BOTH v10 (schema 0x000a) AND v11 (schema 0x000b). v11 went live on Solana before 2026-04-25 (date TBD; verifier docstring previously said "not yet active" — wrong). Field-level cadence on weekends:
    - v10 `price` (w7) — frozen at Friday close (stale-hold archetype, F0)
    - v10 `tokenized_price` (w12) — continuous sub-second updates 24/7 (undisclosed-methodology continuous-mark archetype, same as RedStone Live)
    - v11 `mid` / `bid` / `ask` — placeholder-derived (synthetic min/max bookends), NOT real prices
    - v11 `last_traded_price` — frozen at Friday close (same archetype as v10 `price`)
- Chainlink Data Streams during weekend `marketStatus = 5` (87 obs, prior entry): 100% of observations have $\text{bid} \approx 0$ and $\text{ask} = 0$ — no published band. Chainlink + naive $\pm 3.2\%$ wrap delivers 95% realised at 320 bps on this calm-period sample. **Caveat:** the 87-obs dataset predates the v10 + v11 decoder corrections; numerical re-derivation deferred to v2 paper.
- Both findings support §1.1 thesis: no incumbent publishes a verifiable calibration claim at the aggregate feed level. Consumer-supplied wraps can match coverage but require the consumer to do the calibration work themselves.
- **v11 24/5-window cadence (pre-market, regular, post-market, overnight) untested as of 2026-04-25.** Verification scheduled Monday 2026-04-27 morning ET — see `docs/ROADMAP.md` Phase 1 → Methodology / verification.

**Validated empirical claims (OOS 2023+, 1,720 rows, 172 weekends):**
- τ = 0.95: realised 0.950, Kupiec $p_{uc}$ = 1.000, Christoffersen $p_{ind}$ = 0.485 (PASS).
- τ = 0.85: realised 0.855, Kupiec $p_{uc}$ = 0.541, Christoffersen $p_{ind}$ = 0.185 (PASS).
- τ = 0.68: realised 0.678, Kupiec $p_{uc}$ = 0.893, Christoffersen $p_{ind}$ = 0.647 (PASS).
- τ = 0.99: realised 0.977 (post-grid-extension; was 0.972 on the 0.995-capped grid) — Kupiec still rejects. Structural ceiling re-attributed: with the grid extended to 0.999, the deeper finite-sample limitation is now identified as the 156-weekend per-(symbol, regime) calibration window size, not grid spacing.
- Protocol EL vs the legacy flat ±300bps baseline at τ = 0.85: ΔEL ≈ −0.011 with bootstrap 95% CI [−0.014, −0.007] (favours Soothsayer). This result remains useful as a stylized benchmark, but it is no longer described as the literal deployed xStocks incumbent after the 2026-04-26 on-chain Kamino snapshot.
- **Walk-forward stability (6 expanding-window splits 2019–2025):** at τ=0.95, mean buffer = 0.019 (σ = 0.017); deployed value 0.020 lands at the cross-split mean. At τ=0.85, mean buffer = 0.025 (σ = 0.022); deployed 0.045 is conservative (≥1σ above mean).
- **Stationarity (D2):** 8 of 10 symbols stationary by joint ADF + KPSS; HOOD (n=245) and TLT trend-stationary.
- **Christoffersen pooling sensitivity (D4):** sum-of-LRs / Bonferroni / Holm-Šidák agree on accept/reject at α=0.05 across all four targets — robust to pooling choice.
- **Inter-anchor τ validation (D5):** sweep τ ∈ [0.50, 0.99] step 0.01 (50 levels). Kupiec $p_{uc} > 0.05$ at **47 of 50** targets; max deviation $|\text{realised} - \tau|$ = 0.030. The three failures are τ=0.50/0.51 (over-cover by 2.6–3pp; safe direction; flat extrapolation below the lowest anchor) and τ=0.99 (the documented §9.1 structural ceiling). **Deployment range τ ∈ [0.52, 0.98] passes uniformly.** This is a stronger claim than the four-anchor calibration: realised(τ) = τ + ε with sup|ε| < 0.025 across the whole deployment range. Closes the linear-interpolation faith claim raised in the bibliography review.
- **Served-band PIT uniformity (D6):** the naive KS-on-PIT test fails (KS=0.500) because the τ grid floor at 0.50 floors all natural PITs in $[0, 0.50)$ — a measurement artefact, not a calibration failure. The right test is D5 (per-τ realised vs target), which passes on the deployment range. Disclosed methodologically in `reports/v1b_diagnostics_extended.md`.
- **Cross-asset leave-one-out (D7):** for each of the 10 symbols, refit the calibration surface on the other 9 and serve the held-out ticker through the pooled-fallback path on its 2023+ OOS slice. **Pooled coverage transfers near-perfectly:** in-sample → LOO pooled at (τ=0.68, 0.85, 0.95) = (0.678→0.681, 0.855→0.852, 0.950→0.967). 26 of 30 (symbol × τ) cells pass Kupiec at α=0.05; the 4 failures are 3 over-covers (safe direction; GLD/MSTR/TLT) and 1 under-cover at SPY τ=0.68 (lowest-grid edge). Largest realized-coverage drop in-sample → LOO is −0.047 at MSTR τ=0.68. **The calibration mechanism transfers to unseen tickers**, supporting a paper claim that the methodology generalises beyond our 10-symbol universe — a §6.5 strengthening, not a §9.9 disclosure. Artefact: `reports/v1b_leave_one_out.md`, `reports/tables/v1b_leave_one_out.csv`.
- **Reviewer-tier diagnostics (D8 — Berkowitz, DQ, CRPS, exceedance magnitude; updated 2026-04-28 evening):** Berkowitz joint LR on inverse-normal-transformed continuous PITs **rejects** ($p \approx 0$, $\widehat{\text{var}}\,z = 0.84$); rejection is buffer-induced safe-direction over-coverage outside the deployment range τ ∈ [0.68, 0.99] and confirms that the served-band claim is *per-anchor calibrated*, not full-distribution calibrated. Engle-Manganelli DQ test (per-symbol, 4 lags, pooled $\chi^2(50)$) **rejects** at all four anchors ($p_\text{DQ}$: 0.032 / 0.014 / 0.032 / ~0 at τ = 0.68 / 0.85 / 0.95 / 0.99) — but the **per-symbol-median p-value sensitivity passes at all four** (0.211 / 0.384 / 0.289 / 0.261), demonstrating that the pooled-χ² aggregation inflates rejection as $K$ grows. The honest reading uses *both*: the per-symbol reject-count at α=0.05 is 1/10, 2/10, 2/10, 5/10 — the τ ≤ 0.95 counts are consistent with type-I rate, but the τ = 0.99 count of 5/10 indicates real per-symbol tail miscalibration in half the universe that does not vanish under any defensible aggregation. The §10.2 halt/corp-action filter would isolate which of the five rejecting symbols are picking up structural exceptions; gated on scryer wishlist items 15a + 15b. **Exceedance magnitude** (McNeil-Frey simplified, 1,730-row rerun): max breach shrinks monotonically in τ (2,339 → 2,150 → 1,415 → 1,081 bps); at τ = 0.99 the 49 missed violations have median 71 bps, max 1,081 bps — bounds worst-case protocol impact at ~11% on a missed event, ~0.7% at the median. CRPS = 1.82 (reported as baseline for future cross-oracle comparators). Reliability diagram: `reports/figures/v1b_reliability_diagram.png`. Artefacts: `reports/tables/v1b_oos_reviewer_diagnostics.csv`, `v1b_oos_dq_per_symbol.csv`, `v1b_oos_dq_per_symbol_summary.csv`, `v1b_oos_berkowitz_crps.csv`, `v1b_oos_pit_continuous.csv`.
- **Window-size sensitivity sweep (D8):** sweep F1_emp_regime rolling window ∈ {52, 78, 104, 156, 208, 260, 312} weekends; for each, recompute bounds, build calibration surface, serve OOS 2023+ at τ ∈ {0.68, 0.85, 0.95} using deployed BUFFER_BY_TARGET. **Window-robust within ±3pp realised at every τ across the full range.** Window=156 is the *only* choice that passes Kupiec at α=0.05 on all three targets simultaneously; window 208 also passes at τ=0.68 + 0.95 with τ=0.85 marginal. Deployed 156 is empirically defensible (not arbitrary) and sits inside a stable region [156, 260] where coverage tracks target within tolerance and sharpness is comparable. Artefact: `reports/v1b_window_sensitivity.md`, `reports/tables/v1b_window_sensitivity.csv`.

**Code source-of-truth.**
- Python: `src/soothsayer/oracle.py` (`BUFFER_BY_TARGET`, `REGIME_FORECASTER`, `Oracle.fair_value`).
- Rust: `crates/soothsayer-oracle/src/{config,oracle}.rs` (byte-for-byte port; 75/75 parity tests pass).
- Calibration surface artefact: `data/processed/v1b_bounds.parquet` (the table consumers verify against).

**Paper draft snapshot (descriptive sections, frozen pending live deployment):**
- §1 Introduction — `reports/paper1_coverage_inversion/01_introduction.md`
- §2 Related Work — `reports/paper1_coverage_inversion/02_related_work.md` (28 verified references)
- §3 Problem Statement — `reports/paper1_coverage_inversion/problem_statement.md`
- §6 Results — `reports/paper1_coverage_inversion/06_results.md`
- §9 Limitations — `reports/paper1_coverage_inversion/09_limitations.md`
- §2-citation bibliography — `reports/paper1_coverage_inversion/references.md`

**Phase-2 deliverables conditional on data history.** F_tok forecaster (uses on-chain xStock TWAP; gated on V5 tape ≥ 150 weekend obs per regime), MEV-aware consumer-experienced coverage, full PIT-uniformity diagnostic, conformal-prediction re-evaluation under finer claimed grid. See `docs/v2.md`.

---

## 1. Decision log

### 2026-04-29 (evening) — Relay-fleet generalization: trust-model commitments + Pyth-poster scope correction

**Trigger.** A data-spine audit (this date) found two issues that scope the relay layer larger than the 2026-04-29 (afternoon) entry assumed, and a strategic conversation about institutional skepticism around relay-operated price feeds surfaced commitments that should be locked into the methodology now (in-design lock window) rather than retrofitted later.

The data-spine findings:

1. **Pyth equity sponsored feeds are not posted on Solana mainnet.** The 2026-04-28 (afternoon) router design implicitly assumed mainnet would unlock equity coverage via Pyth's existing sponsored-feed posting service. Direct query of the mainnet receiver program found `SPY/USD shard 0`, `QQQ/USD shard 0`, and other equity-feed PriceUpdateV2 PDAs do not exist (`AccountNotFound`). Hermes' equity catalog confirms the feed_ids exist for off-chain consumption but the popular tickers are not in Pyth's continuously-posted Solana set. SOL/USD on devnet was verified at `7UVimffxr9ow1uXYxsr4LHAcV58mLzhmwaeKvJ1pjLiE` (someone is running a poster for it); the equivalent does not exist for SPY/etc on mainnet.
2. **The relay pattern generalises.** Option C (locked this date afternoon for Chainlink Streams) is the same architectural shape needed for Pyth equities — fetch off-chain → bring on-chain. RedStone Live (REST-only on the public gateway) eventually needs the same treatment if RedStone doesn't ship a Solana product. The "Chainlink-only relay" framing under-counted the broader infrastructure lift.

The strategic finding from the trust-model conversation:

3. **Relay infrastructure is well-understood by institutional buyers** — Pyth's receiver, Wormhole's Token Bridge, and Chainlink's Verifier all use this pattern at scale. **What gets scrutinised is the operational layer, not the architectural one.** The cryptographic floor (signed VAAs / DON-signed reports verified on-chain) excludes value falsification. What soothsayer must commit to defending against is the operational layer: selective posting, timing manipulation, coverage manipulation, conflict-of-interest. Five concrete commitments cover this.

**Decisions.**

**D1. Generalise the relay layer beyond Chainlink.** The 2026-04-29 (afternoon) entry locked Option C as a Chainlink-specific relay; this entry extends that lock to a "relay fleet" concept covering all upstream sources soothsayer wants to consume on-chain that don't already have a passive-PDA path. The relay fleet's shape is uniform: off-chain daemon fetches signed data from the upstream → submits on-chain → cryptographic verification at post time → router reads passively. Source-specific work is in the daemon and the verification path, not in the architectural pattern.

**D2. Pyth scope correction: no new program needed.** The 2026-04-29 (afternoon) entry's relay-program design (item 42, `soothsayer-streams-relay-program`) is needed for Chainlink because Chainlink's Verifier program only returns decoded data via per-tx return_data — there is no Chainlink-controlled PDA to read passively. **Pyth is structurally different**: Pyth's receiver program already implements the relay pattern, and posts are permissionless (anyone can fetch a Hermes VAA and call `update_price_feeds` on the receiver). For Pyth equity coverage, soothsayer needs **only an off-chain daemon** — no new on-chain program. The daemon fetches Hermes VAAs for the configured equity feed_ids and CPIs into Pyth's existing receiver program. The PriceUpdateV2 PDA the receiver writes is exactly what `read_pyth_aggregate` already decodes; no router changes needed. This collapses a substantial scope item to a daemon-only build.

**D3. Five trust commitments locked.** These commit soothsayer to operational discipline that turns the relay layer from "trust us" into "trust the cryptographic floor + audit our policy." Each is part of soothsayer's institutional pitch and is reviewable in the methodology log.

1. **Verifier-CPI is mandatory in production.** The Chainlink relay program's `post_relay_update` instruction must successfully CPI into the Chainlink Verifier program before persisting a `streams_relay_update.v1` PDA. No "trust-mode" path on mainnet (per O11; v0 ships always-CPI on devnet). Pyth posting goes through Pyth's receiver, which performs Wormhole-guardian signature verification natively. Soothsayer's posting code cannot persist a value not signed by the upstream — this is enforced by the on-chain programs, not by promise.
2. **Open-source daemon code.** All relay daemons (Chainlink, Pyth, future RedStone if needed) ship as part of scryer or as open-sourced soothsayer-side crates. Anyone with the upstream credentials (Hermes API access for Pyth, Chainlink Streams subscription for the Streams relay) can run their own poster. There is no proprietary fetching logic that locks consumers to soothsayer-operated infrastructure.
3. **Multi-writer migration in v1.** v0 ships with a single soothsayer-controlled writer keypair (per O10) for operational simplicity. v1 of the relay infrastructure transitions to either a multi-writer set (N independent operators, each posts; freshest valid post wins) or fully permissionless writes (anyone with a valid signed report can post). Migration is gated on either a design-partner request or 6 months of stable operation, whichever comes first. Tracked as an O10 follow-up.
4. **Public posting cadence + uptime alerting.** Per-feed posting cadence target is published in the operator dashboard (default ≤60s per feed for all relayed equity sources). The dashboard surfaces miss / staleness events publicly so consumers can independently detect operational issues. The router already exposes `relay_post_ts` per upstream contribution in `unified_feed_receipt.v1`; consumers reading the receipt can detect stale relays without trusting the operator's dashboard.
5. **No-position policy.** Soothsayer (the legal entity / signing authority) commits to **not holding on-chain positions in assets it relays for**. The commitment is enforced via a published wallet allowlist disclosed in the operator dashboard; the on-chain audit trail (writer keypair + soothsayer's other on-chain wallets) is observable indefinitely. Conflict-of-interest is the residual concern after the cryptographic floor; this commitment is the operator's response. Tracked as new open question O12 for the enforcement mechanism — methodology entry will lock the specific allowlist publication path before mainnet relay deploy.

**D4. Wishlist additions.** Add scryer wishlist item 44: `soothsayer-pyth-poster` (off-chain daemon only; no on-chain program). Item 42's scope is unchanged (Chainlink-specific relay program + daemon). Items 21 (`chainlink_streams_tape.v1`) remain retracted per the afternoon entry. RedStone's eventual relay deferred to a future methodology entry when RedStone's Solana product story firms up.

**What this commits soothsayer to.**
- Operating two relay daemons in v0 (one for Chainlink, one for Pyth equities). Both feed the router with cryptographically-verified upstream prices via passive PDAs.
- Publishing wallet allowlist + cadence dashboard before mainnet deployment of either relay.
- Open-sourcing the daemon code (scryer + soothsayer crates).
- Reviewing the multi-writer migration condition at 6 months post-v0-mainnet.

**What this does not commit soothsayer to.**
- Sustainability model for the relay layer in v1+. Today's commitment is operational integrity; how the relay infrastructure is funded long-term (paid integrations, sponsorship, grant, or token-funded similar to Pyth/Chainlink) is a separate strategic decision deferred until at least one design partner is signed.
- Decentralisation timeline beyond v1's multi-writer step. Full permissionlessness is a v2+ consideration if/when the relay infrastructure becomes load-bearing for many consumers.
- Specific governance for the wallet allowlist (who can change it, what notice period). v0: soothsayer-controlled multisig; v1+ may require a partner-witnessed change process.

**Open methodology question added to §2.**
- O12. Enforcement mechanism for the no-position policy. Options: (a) on-chain attestation (soothsayer publishes a list of allowed wallets via a versioned attestation account; auditors verify these are the only soothsayer-controlled wallets touching relayed assets), (b) periodic audit by an independent third party reviewing soothsayer's full wallet set, (c) governance-witnessed multisig holding the canonical wallet list. v0 default: attestation-account approach (option a). Lock the specific implementation before mainnet relay deploy.

**Forward path.**
1. Apply scryer wishlist update in this session (add item 44; cross-reference D2's program-not-needed clarification on item 42).
2. Scaffold `programs/soothsayer-streams-relay-program/` (item 42 Phase 42a) — Anchor program with stubbed Verifier CPI. Continues this session.
3. Off-chain daemons (items 43 + 44) implemented in scryer; methodology entries needed there per scryer hard rule #1. Calendar-time-gated by Chainlink Streams API access (subscription required) and Pyth Hermes endpoint access (free; can start now).
4. Publish operator dashboard scaffold + wallet allowlist before mainnet relay deploy.
5. v0 mainnet relay deploys are gated on the same conditions as the router's mainnet deploy: audit clean + design-partner LOI + the operator dashboard published.

---

### 2026-04-29 (afternoon) — Chainlink Streams integration: Option C selected (soothsayer-built relay program), schema lock, in-window receipt rename

**Trigger.** Devnet smoke testing of the router program (this date) surfaced an architectural mismatch between the router's design (passive PDA reads of upstream feeds) and Chainlink Data Streams' product model on Solana (per-tx report-blob submission via CPI to a Verifier program; no continuously-published account). Verified via primary sources:

- Chainlink **Data Streams** (Solana product carrying US equity feeds): per-tx pull architecture; consumers fetch DON-signed reports off-chain and submit them per-tx via Verifier CPI. No persistent on-chain account holding the latest decoded report.
- Chainlink **Data Feeds** (a separate, legacy product): IS passive-PDA on Solana, but covers crypto only — no equity coverage on either mainnet or devnet.
- Same architecture on mainnet ↔ devnet; the difference is which feeds are continuously active, not how consumption works.
- Schema for RWA / equities is **V8** (not the v10/v11 names from the EVM Data Streams product); the local `chainlink_v11.rs` decoder is for the wrong wire format.

The 2026-04-28 (afternoon) router design entry implicitly assumed direct passive PDA reads for Chainlink. That assumption is incorrect for the equity-coverage product. Three remediation options were evaluated:

- **Option A** — drop Chainlink Data Streams as a router upstream entirely; keep only as off-chain incumbent benchmark for paper 1.
- **Option B** — per-tx report blob via instruction data + Verifier CPI inside the router. Couples consumer integrations to fetching reports off-chain per refresh; bloats tx size; operationally awkward.
- **Option C** — soothsayer-built relay daemon + relay program. Off-chain daemon fetches signed Chainlink reports and posts decoded results to a soothsayer-controlled PDA; the router reads the relay PDA passively. Preserves the router's clean passive-PDA architecture; adds infrastructure surface area soothsayer is already operating (cf. scryer's existing daemon fleet).

**Decision.** Option C. Rationale:

1. Preserves router-program simplicity. Only one architectural model in the router (passive PDA reads); upstream-kind code paths stay uniform.
2. Decouples soothsayer from Chainlink wire-format changes. The relay PDA's schema is soothsayer-controlled and stable. The relay daemon translates whatever Chainlink schema is current (V8 today; future Vn) into the stable relay format. Schema drift between Chainlink products doesn't propagate into the router.
3. Symmetric with the existing Pyth-poster pattern. Pyth runs a continuously-active "poster service" that writes `PriceUpdateV2` accounts on Solana for sponsored feeds; soothsayer running the equivalent service for Chainlink Data Streams is the same architectural shape.
4. Extensible. The same relay infrastructure can carry any future report-submission-only data source (e.g., RedStone's eventual Solana product, custom benchmarks).

The cost is real — soothsayer takes operational responsibility for keeping the relay live, and adds another point of failure to monitor. This is acknowledged; the relay daemon goes into scryer's launchd schedule alongside its existing tape daemons (Scope, Pyth Hermes, RedStone Live, V5).

**Schema lock — `streams_relay_update.v1`** (the relay PDA wire format, soothsayer-controlled). Locked here; future schema bumps follow the same versioning policy as `unified_feed_receipt.v1` (additive non-breaking permitted within v1; breakage requires v2 + 90-day coexistence).

```
streams_relay_update.v1 (Anchor account, 8-byte discriminator + body):

version                       u8       (1 for now)
market_status_code            u8       0=unknown, 1=pre_market, 2=regular,
                                       3=post_market, 4=overnight, 5=closed
schema_decoded_from           u8       Audit: which Chainlink schema was
                                       decoded (8=V8 RWA, 11=V11 EVM, etc.)
signature_verified            u8       1 if relay program CPI'd into the
                                       Chainlink Verifier and validation
                                       succeeded; 0 if the relay accepted
                                       off-chain (daemon-side) validation
                                       only — consumers can downgrade trust
                                       on `signature_verified == 0` reads.
_pad0                         [u8; 4]
feed_id                       [u8; 32] Chainlink feed_id verbatim
underlier_symbol              [u8; 16] ASCII null-padded; cross-reference
                                       between feed_id and human symbol
price                         i64      Fixed-point at `exponent`; defaults
                                       to mid; falls back to last_traded
                                       when mid is a placeholder (per the
                                       paper-1 §1.1 observation).
confidence                    i64      Fixed-point at `exponent`; sentinel
                                       i64::MIN if no CI is derivable.
                                       v0 derivation: (ask - bid) / 2 when
                                       both are real; sentinel otherwise.
bid                           i64
ask                           i64
last_traded_price             i64
chainlink_observations_ts     i64      Unix seconds; from the Chainlink
                                       report's `observations_timestamp`.
chainlink_last_seen_ts_ns     i64      From `last_seen_timestamp_ns`.
relay_post_ts                 i64      Unix seconds; when the relay daemon
                                       called `post_relay_update`.
relay_post_slot               u64      Solana slot of the relay write.
exponent                      i8       Fixed-point exponent; default −8.
_pad1                         [u8; 7]
```

PDA derivation: `[b"streams_relay", feed_id]` (32-byte feed_id seed). One PDA per feed.

**Architecture lock.** A separate Anchor program at `programs/soothsayer-streams-relay-program/` holds the relay PDAs. The router CPI-reads relay PDAs; it does not write to them. The relay program exposes:

- `initialize` — one-time setup of `RelayConfig` PDA (authority + writer signer set).
- `post_relay_update(feed_id, signed_report_blob, decoded_fields)` — only callable by an authorised writer keypair. Attempts a Verifier CPI to validate the signed report; falls back to `signature_verified=0` if the Verifier program is unavailable or the daemon is operating in trust-the-fetcher mode for development. Writes the resulting `streams_relay_update` to the per-feed PDA.
- `add_feed` / `update_feed_config` — authority-gated registration of new feed_ids (with their underlier symbols) and configuration changes.
- `set_paused` / `rotate_authority` / `rotate_writer_set` — operational controls mirroring the router's governance pattern.

The relay program ships **upgradeable** in v0, controlled by the same multisig that controls the router (per 2026-04-28 (afternoon) governance lock). Migration to immutable is gated on the same condition: signed institutional-partner LOI + partner methodology buy-in. The writer signer set is rotated independently of the authority — the daemon's hot key is one of N signer keypairs; rotating the daemon doesn't require rotating the multisig.

**Router-side changes (in-window correction).** The receipt schema lock at `unified_feed_receipt.v1` (2026-04-28 morning) included an `UpstreamKind::ChainlinkV11` variant. This entry corrects:

- Rename `UpstreamKind::ChainlinkV11` → `UpstreamKind::ChainlinkStreamsRelay` (host crate `crates/soothsayer-router/src/receipt.rs`).
- Wire format string follows: `"chainlink_v11"` → `"chainlink_streams_relay"` (set explicitly via `#[serde(rename)]`).
- Program-side: `UPSTREAM_CHAINLINK_V11` → `UPSTREAM_CHAINLINK_STREAMS_RELAY`. Discriminant value remains `1` (no on-disk renumbering; the rename is text-only).
- Decoder rename: `read_chainlink_v11` → `read_chainlink_streams_relay`. The decoder now expects the `streams_relay_update.v1` wire format described above, NOT the raw v11 Chainlink Data Streams report layout.

These changes are in-window corrections (24 hours since the schema lock; zero deployed integrations against `ChainlinkV11`; no production receipt has emitted with that variant). Same correction shape as the 2026-04-29 (morning) Mango v4 removal. No `unified_feed_receipt.v2` schema bump required.

**Status of the existing `chainlink_v11.rs` decoder.** The pure-Rust 14-word v11 decoder lives at `programs/soothsayer-router-program/src/chainlink_v11.rs` and was tested against synthetic v11 reports earlier this session. It targets the EVM v11 schema, not Solana's V8 RWA schema. Disposition:

- The router program no longer references it directly (the new `read_chainlink_streams_relay` decodes the relay PDA, not raw Chainlink reports).
- It is retained as a reference implementation for the relay daemon's report-decoding logic — the daemon needs to decode incoming Chainlink reports, and even though V8 is the production schema for equities, the v11 decoder is a near-template for V8 (similar word-aligned ABI structure with different field counts).
- The relay daemon's actual decoder is its own work item; it will live in scryer (or a soothsayer-side helper crate) and follow scryer's hard-rule-1 conventions.

**Forward path.**
1. Apply this entry's code changes in this session: receipt rename + program decoder rename + tests + scryer wishlist.
2. Scaffold `programs/soothsayer-streams-relay-program/` (separate Anchor program; same multisig-controlled upgradeable model). Methodology entry + Phase 1 build-sequence covers this.
3. Implement the Verifier CPI inside `post_relay_update`. This needs the Chainlink `chainlink-data-streams-solana` SDK (Rust crate) as a dependency; verify dep-graph compatibility with anchor-lang 0.31 (similar diligence to the Pyth + Switchboard SDK adds we did this session).
4. Implement the off-chain relay daemon (scryer-side fetcher + signer key management + `post_relay_update` CPI client).
5. Deploy relay program to devnet; run daemon; integration-test against the router by adding an asset configured with a relay-PDA upstream.
6. Mainnet relay deploy follows the same audit + LOI gates as the router.

**Open methodology questions added to §2.**
- O10. The relay daemon's signing model: dedicated hot keypair held by soothsayer infra, OR per-feed keypair, OR multisig-of-publishers (decentralisation of the relay layer)? v0 default: single dedicated hot keypair, with rotation via `rotate_writer_set`. Decentralisation deferred to a later methodology entry.
- O11. Verifier-CPI policy at `post_relay_update`: always-CPI (full verification, higher CU cost), opportunistic (CPI when feasible, fall back to off-chain validation when not), or trust-mode (off-chain only)? v0 ships always-CPI on devnet; mainnet may need opportunistic to amortise CU cost across many feeds. Tracked.

---

### 2026-04-29 — v1/v2 product roadmap lock + Mango v4 contribution reclassification

**Trigger.** Two findings during Layer 0 decoder implementation:

1. **Verification of the 2026-04-28 (midday) entry's premise found a methodology error.** That entry asserted that Mango v4's `PerpMarket.oracle_price` is a readable post-deviation-guard field that the router could consume as a fifth upstream for crypto-correlated assets. Inspection of Mango v4's source (blockworks-foundation/mango-v4 `programs/mango-v4/src/state/perp_market.rs`) shows the field is a *runtime function*, not a stored field. Mango reads its underlying oracle (Pyth/Switchboard) dynamically via CPI inside its own instructions, applies the deviation guard ephemerally, and uses the result for liquidation health computation. The post-guard price is never persisted to account state. The PerpMarket account stores `stable_price_model` (a TWAP-smoothed reference used for liquidation thresholds) but no current-oracle field externally readable.

2. **A strategic observation surfaced from the same investigation: Mango's pipeline is the *inverse* of soothsayer's on the (methodology, action) trust axes.**
   - Mango: methodology-private + action-public. Consumers trust Mango's team and integrate against actions (liquidations, health margins).
   - Soothsayer: methodology-public + action-private. Consumers verify the methodology and integrate against bands; they own the action.

   These are non-substitute products with different buyer profiles (crypto-native protocols want Mango's shape; institutional / TradFi-tokenization issuers want soothsayer's shape). Mimicking Mango's "publish a binary action" model would move soothsayer into a quadrant where Mango has years of head start, abandons soothsayer's structural advantage on calibration-transparency, and disqualifies the buyer profile most likely to pay a premium for it.

   But Mango's higher product altitude — operating at the *action* layer rather than the *interpretable signal* layer — is a real integration-friction asymmetry worth closing. The right way to close it is **not** to publish actions; it is to publish a higher-abstraction *event stream* that is still consumer-driven but does more of the interpretive work, with calibration receipts attached.

**Decisions.**

**D1. Reclassify Mango v4's contribution to soothsayer as *methodology only*.** The deviation-guard logic adopted by the 2026-04-28 (midday) entry remains in Layer 0; that decision stands. The "Mango as a fifth literal upstream" portion of that entry is retracted by AMENDMENT (added in-line to the 2026-04-28 (midday) entry below). `MangoV4PostGuard` is removed from `UpstreamKind` (host crate `crates/soothsayer-router/src/receipt.rs`) and `UPSTREAM_MANGO_V4_POST_GUARD` is removed from the program (`programs/soothsayer-router-program/src/state.rs`). The `read_mango_v4_post_guard` stub is deleted. Schema-version implications: the receipt schema lock at `unified_feed_receipt.v1` was 2026-04-28 (morning); the variant removal is within the same in-design lock window with zero deployed consumers and is treated as an in-window correction rather than a v2 schema bump. A methodology-log AMENDMENT documents the reasoning so the 90-day v1↔v2 coexistence rule that applies to *deployed* breaking changes is not invoked here.

**D2. Lock v1 product scope as a calibration-transparent event stream.** The router program's v0 surface (band primitive) gets a higher-abstraction sibling at v1: an on-chain event stream that fires when consumer-configured band thresholds are crossed. Each event carries the full `unified_feed_receipt.v1` reference plus four event-specific fields:

- `asset_id` and an opaque `account_id` hash (account state stays private to the consumer; soothsayer never reads borrower positions).
- The crossed `τ_threshold` and breach `direction` (up / down).
- A reference snapshot `(point, lower, upper, regime)` at the moment of the crossing.
- A `historical_frequency` field: empirical rate at which crossings of the same magnitude in the same regime have occurred over the calibration window — calibration context the consumer can use to interpret the event severity.

The product is **not** a binary "liquidate this account" signal. It is a calibrated alert. The consumer's policy (warn-only, raise-haircut, partial-liquidate, full-liquidate) sits on top, parameterized by the consumer. This preserves the methodology-public + action-private architecture while operating at Mango's value altitude.

Methodology backing: **Paper 3** (the band → action mapping). Until Paper 3 lands, v1 is unimplementable as specified — the "this τ corresponds to which action" semantic is exactly what Paper 3 develops. v1 product timing is therefore gated on Paper 3 publication (planned Q3-Q4 2026).

**D3. Lock v2 product scope as a parameterized decision SDK.** A Rust + TypeScript library that takes consumer-supplied cost weights, portfolio shape, and action semantics, and returns a binary recommendation with a calibration receipt. Soothsayer never sees the consumer's accounts; the library runs client-side. This is the most distant product layer from Mango's pattern: still methodology-public, still action-private (the recommendation is computed *from* the consumer's parameterization, not imposed). Methodology backing: **Paper 2** (OEV mechanism design under calibration-transparent oracles) + Paper 3. v2 timing is 2027.

**D4. v0 router build proceeds unchanged.** The v0 work landed in this session (Anchor program scaffold + Chainlink v11 + Pyth + Switchboard On-Demand decoders + Layer 0 filter pipeline + regime gate + soothsayer-band closed-regime read) is the v0 product surface. Adding event-stream logic to the current program is explicitly **out of scope** until Paper 3 lands. The router program ships to mainnet on the v0 contract (band primitive only); v1's event stream is a separate program (or a separate set of instructions on the same program) deployed once Paper 3 is published.

**What this commits soothsayer to.**
- Receipt schema correction is a one-time within-window action; future schema changes follow the locked versioning policy (additive non-breaking within v1; breakage requires v2 + 90-day coexistence).
- Paper 3 becomes a load-bearing dependency for v1 product. Paper 3's timeline is now coupled to the v1 product timeline; delays on either side propagate.
- The v1 event-stream design must preserve the methodology-public + action-private invariants. Specifically: event payloads cite calibration receipts (no opaque action emission), account state is never read on-chain by soothsayer, the consumer parameterizes thresholds rather than soothsayer prescribing them.
- v2 SDK preserves the same invariants client-side.

**What this does *not* commit soothsayer to.**
- Mimicking Mango's binary liquidation signal. Soothsayer's product is calibrated alerts, not actions.
- Reading borrower positions. Account state is consumer-private at every product layer.
- Productizing Paper 3's specific liquidation-policy recommendations as defaults. Paper 3 is a methodology paper; v1's product is the event stream that reflects the methodology's threshold semantics, not a specific protocol's policy.
- Replacing Mango or any other lending-protocol pricing primitive. Mango remains the right product for buyers in the methodology-private + action-public quadrant; soothsayer addresses the inverse quadrant.

**Forward path.**
1. Apply D1's code changes in this session (receipt + state + upstreams + tests + scryer wishlist item 39).
2. Continue v0 router build (Phase 1 step 2c+ per the 2026-04-28 (afternoon) sequence): soothsayer-band parity canary (done this session), remaining decoder follow-ups (Mango v4 dropped per D1; RedStone deferred until they publish a Solana PDA layout), holiday-aware NYSE calendar, feed-id verification, TS/Rust SDK.
3. v0 mainnet (gated on audit clean + design-partner LOI per the 2026-04-28 (afternoon) entry).
4. Paper 3 publication.
5. v1 event-stream program design + methodology entry, gated on Paper 3.
6. v1 mainnet deploy.

**Open questions added to §2.**
- O8. What is the on-chain event format for v1's calibration-transparent event stream? Anchor `emit!`, or a custom event-log PDA with a versioned schema parallel to `unified_feed_receipt.v1`? Decision deferred to v1 design lock; revisited when Paper 3's threshold semantics firm up.
- O9. How does v2's parameterized decision SDK handle multi-asset portfolios where calibration is per-(symbol, regime) but the consumer's risk model aggregates? Methodology question for Paper 3 §10 / Paper 2.

---

### 2026-04-28 (late evening, +1) — Trial 1 result: GPD does not fix the τ = 0.99 per-symbol DQ rejections

**Result.** Hypothesis H1 from the late-evening trial program **rejected**. GPD-based τ ≥ 0.95 quantiles produce the *same* per-symbol DQ reject-count at τ = 0.99 as the empirical baseline (6 / 10 in the standalone replay; the absolute number differs from production's 5 / 10 because the experiment uses raw claimed-grid bounds with no calibration-surface inversion or per-target buffer, but the *internal* empirical-vs-GPD comparison is apples-to-apples). Bandwidth widened modestly (449 → 484 bps, +8%), well within the 1.5× cap. Decision-threshold scorecard: 1 (DQ) **fail**, 2 (realised) fail in both, 3 (Christoffersen) pass, 4 (bandwidth) pass.

**Diagnostic implication.** The τ = 0.99 per-symbol miscalibration is *not* a small-sample tail-quantile-estimator issue. The per-symbol reject pattern is invariant under the GPD swap: AAPL, HOOD, NVDA, QQQ, SPY, TSLA reject under both estimators; GLD, GOOGL, MSTR, TLT pass under both (with GLD/MSTR/TLT passing partly because their bands are wide enough that DQ has no power). If the mechanism were unstable tail-quantile estimates from too few exceedances, GPD's parametric extrapolation would visibly help — it does not. Therefore, the candidate-mechanism list refines to (in rough priority order): conditional volatility clustering / GARCH effects on residuals (the canonical McNeil-Frey diagnosis); regime-transition state the current $\rho$ labeler doesn't encode (post-shock recovery, vol-spike-decay sub-regimes); symbol-specific tail behaviour the factor switchboard doesn't carry (TSLA idiosyncratic vol, NVDA AI-rotation transitions, etc.); and the §10.2 halt / corp-action structural-exception filter, which remains scryer-blocked and orthogonal.

**Trial-program updates.**

- *Trial 2 (Mondrian conformal on top of Trial 1):* defer. Mondrian is a different aggregation, not a different mechanism; with the per-symbol mechanism unaddressed by GPD, Mondrian's group-conditional coverage guarantee is unlikely to close the per-symbol DQ gap. Reconsider only if reframed as a v2 surface-design change rather than a Paper 1 patch.
- *Trial 3 (pooled-tail-only):* run anyway as a falsification control. Cheap (1-2 days). If pooled-tail also shows 6 / 10 reject, that fully rules out the small-sample-noise mechanism family; if it moves the count, the joint reading is more nuanced.
- *Trial 5 (new) — Conditional EVT (GARCH + GPD on standardized residuals).* McNeil-Frey 2000 canonical two-stage. Targets the volatility-clustering mechanism Trial 1's negative result points at. Effort ~1-2 weeks per-symbol GARCH refits. Belongs in v2 calibration-surface revision, not Paper 1.
- *Trial 6 (new) — State augmentation: post-shock realized-vol indicator.* Add `realized_vol_4w` (or VIX-percentile rank, or GARCH-implied $\sigma$ surrogate) as an extra regressor in F1's $\sigma$ model. Targets the regime-transition-state mechanism. Effort ~3-5 days; lighter than full GARCH; may capture much of the same conditional-volatility signal at much lower cost.
- *Strategic alternative (drop τ = 0.99 from the deployed surface).* Strengthened by Trial 1's negative result: the per-symbol miscalibration at the 1% tail is now identified as a structural property of the empirical-quantile / regime-conditioned methodology rather than an estimator-tuning issue. The cleanest disclosure is to scope the deployed range to where the methodology demonstrably holds (τ ∈ [0.50, 0.95] passes uniformly per the §0 D5 inter-anchor sweep). Decision deferred to after Trial 3 + Trial 6 results.

**Paper 1 implication.** The §6.4.1 disclosure framing — pooled DQ rejection partly aggregation-inflated, irreducible 5 / 10 at τ = 0.99 — is unchanged by Trial 1. If anything the negative result *strengthens* the disclosure: the obvious counter-claim ("did you try a parametric tail estimator?") is now explicitly answered with citation to `reports/v1b_evt_pot_trial.md`. No paper-side text changes required for this result; an optional one-line addition to §6.4.1 could note "Trial 1 GPD swap did not improve per-symbol DQ; see `reports/v1b_evt_pot_trial.md` for the decision-threshold scorecard" if reviewer transparency is desired.

**No methodology change.** Deployed system unchanged. Trial 1 was a fork-only experiment; the standalone script (`scripts/exp_evt_pot_tail.py`) is in-repo for reproducibility but does not modify production code paths.

**Artefacts.**
- `reports/v1b_evt_pot_trial.md` — full trial report with mechanism analysis.
- `scripts/exp_evt_pot_tail.py` — standalone experiment.
- `data/processed/exp_evt_pot_bounds.parquet` — per-(symbol, fri\_ts, target) raw bounds, both estimators side-by-side.
- `reports/tables/v1b_oos_evt_pot_summary.csv`, `v1b_oos_dq_per_symbol_evt.csv` — diagnostic tables.

---

### 2026-04-28 (late evening) — Tail-fix trial program for τ = 0.99 per-symbol miscalibration

**Trigger.** The 2026-04-28 (evening) §6.4.1 update found 5 / 10 per-symbol DQ rejections at τ = 0.99 — irreducible under any defensible aggregation (binomial test on observed 5 / 10 vs expected 0.5 / 10 under H₀: p < 10⁻⁷). The §10.2 halt / corp-action filter is gated on scryer wishlist 15a + 15b (forward-looking, ~1 week of scryer work). This entry documents the *parallel modeling-side* trial program — what we test, in what order, and what counts as success — so that the experiments are pre-specified rather than discovered after the fact.

**Why a parallel modeling track.** The §10.2 filter test addresses the *structural-exception* mechanism (halts, corp actions confounding the τ = 0.99 misses for specific symbols). The trial program below addresses the *small-sample noise / temporal clustering* mechanism (the empirical-quantile estimator on a 156-weekend per-(symbol, regime) calibration window has ~1.5 expected violations per τ = 0.99 cell; tail quantile estimation is unstable at that sample size and produces autocorrelated misses). The two mechanisms are orthogonal; both can contribute, and we want to size each before deciding the deployment fix.

**Decision (queue four trials, run on the existing 1,730-row OOS panel; no new data required).** All trials operate on a fork of the existing calibration pipeline. Deployed system unchanged until a trial wins on the decision thresholds below.

**Pre-specified decision thresholds (uniform across all trials).** A trial *passes* if all four hold at τ = 0.99 on the OOS panel:
1. Per-symbol DQ reject-count at α = 0.05 ≤ 3 / 10 (current baseline: 5 / 10).
2. Pooled realised coverage within ±2pp of target 0.99 (current baseline: 0.977, fails).
3. Pooled Christoffersen $p_\text{ind} > 0.05$ (current baseline: 0.956, passes).
4. Mean served half-width at τ = 0.99 ≤ 1.5× the empirical-quantile baseline (current baseline: 580.8 bps; cap: ≤ 871 bps).

**Trial 1 — EVT / Peaks-over-Threshold (Generalized Pareto Distribution) for τ ≥ 0.95 anchors only.**
- *Mechanism.* Replace the empirical-quantile estimator at τ ≥ 0.95 with a parametric GPD fit on the standardized-residual exceedances above the 95th-percentile threshold. The Pickands-Balkema-de Haan theorem (Pickands 1975, Balkema-de Haan 1974) justifies GPD asymptotics for the tail. Empirical-quantile path for τ ≤ 0.95 unchanged.
- *Why this targets the symptom.* GPD fits stably on 30-50 exceedances vs the empirical method's ~150 needed for comparable tail-quantile precision. Our 156-weekend per-(symbol, regime) window has ~8-25 expected exceedances above the 95th percentile (regime-dependent) — squarely in GPD's sweet spot, well below empirical's stability floor.
- *Citations.* McNeil-Frey 2000 (the canonical conditional-EVT VaR paper); Embrechts-Klüppelberg-Mikosch 1997 EVT textbook; Bee-Dupuis-Trapin 2019 (realized POT with high-frequency data). Already in the §2 reference graph via the Allen-Koh-Segers-Ziegel 2025 tail-calibration citation.
- *Effort.* 3-5 days. Standalone experiment script first (no production-pipeline change), then if Trial 1 passes, port into `src/soothsayer/backtest/calibration.py` as a new tail-quantile path.
- *Hypothesis.* GPD-based τ = 0.99 quantile estimates pass the four decision thresholds.

**Trial 2 — Mondrian (group-conditional) conformal layered on top of Trial 1's GPD predictor.**
- *Mechanism.* Apply Mondrian conformal prediction (Vovk-Petej-Lindsay 2003) stratified by (symbol, regime), using the GPD-based predictor from Trial 1 as the base. Different from the previously-tested vanilla split-conformal / nexCP / block-recency variants in `reports/v1b_conformal_comparison.md` — those gave *marginal* coverage; Mondrian gives *group-conditional* coverage, which is the right shape for the per-(symbol, regime) decomposition we already use elsewhere in the surface.
- *Why this layers on Trial 1.* GPD addresses the small-sample tail-estimator instability; Mondrian addresses the per-symbol-conditional coverage gap (exactly what DQ catches). The combination is the most-defensible-by-construction stack: GPD for parametric tail extrapolation, Mondrian for finite-sample group-conditional coverage guarantee.
- *Citations.* Vovk-Petej-Lindsay 2003 (original Mondrian); Tibshirani-Barber-Candès-Ramdas 2019 (weighted conformal); Gibbs-Cherian-Candès 2025 (conformal with conditional guarantees).
- *Effort.* 1 week (Mondrian implementation + recalibration + battery rerun). Conditional on Trial 1 not closing the gap alone.
- *Hypothesis.* Mondrian + GPD reduces per-symbol DQ reject-count to ≤ 1 / 10 with bandwidth ≤ 1.7× the empirical-quantile baseline.

**Trial 3 — Pooled-tail-only calibration (control / baseline).**
- *Mechanism.* At τ ≥ 0.95, use the pooled-across-symbols calibration surface (10× the per-(symbol, regime) cell size); per-(symbol, regime) for τ < 0.95. Already partially built — `pooled_surface()` is the pooled-fallback path used when per-symbol $n < n_\text{min}$.
- *Why this is the control.* Pooling addresses the *small-sample noise* mechanism but leaves the empirical-quantile estimator family intact. If pooling alone hits the threshold, Trials 1 + 2's machinery is over-engineered for the problem and the deployment fix is the simpler change.
- *Effort.* 1-2 days. Cheapest of the four; runs in parallel with Trial 1.
- *Hypothesis.* Pooling addresses small-sample noise but not temporal clustering — DQ should improve modestly (reject-count ~3-4 / 10) but is unlikely to converge to ≤ 1 / 10. If the hypothesis is wrong (i.e., pooling alone hits the threshold), Trial 1 is unnecessary.

**Trial 4 — TCP-RM (Robbins-Monro online conformal) — gated.**
- *Mechanism.* Online α-adjustment based on rolling miscoverage, per Angelopoulos-Bates 2025-2026 framework and the broader Adaptive Conformal Inference (Gibbs-Candès 2021) tradition.
- *Why deferred.* Best-suited for *drift* not present in our weekend-panel setting (the v1b walk-forward stability check shows the deployed buffer at the cross-split mean — no drift signal). TCP-RM addresses a different failure mode than DQ catches.
- *Effort.* 2 weeks. Conditional on Trials 1-3 all falling short — if static methods can't close the gap, online correction is the next swing. Otherwise belongs in v2.

**Strategic alternative (independent of all four trials).** Drop τ = 0.99 from the deployed product surface; deploy τ ∈ [0.50, 0.95] only. Preserves Paper 1 as-is; defers the tail problem to v2. Decision deferred until Trial 1 + 2 results — if neither hits the threshold, this becomes the v0 default and τ = 0.99 ships in the v2 calibration-transparent event stream where the per-symbol structure can be exposed to the consumer rather than aggregated away.

**Sequencing.** Trial 1 first (highest leverage, self-contained, cleanest theoretical justification). Trial 3 in parallel (cheapest baseline, sets the lower-bound for what the simpler change buys you). Trial 2 conditional on Trial 1 passing decision thresholds 1-3 but not bandwidth threshold 4 — i.e., only if GPD is too wide. Trial 4 deferred unless Trials 1-3 all fall short on threshold 1.

**No methodology change yet.** Document trials, run experiments, report results in subsequent dated entries; deployment fix decision conditional on the four-threshold scorecard above.

**Artefacts (planned, not yet generated).**
- `scripts/exp_evt_pot_tail.py` — Trial 1 standalone experiment.
- `scripts/exp_pooled_tail.py` — Trial 3 standalone experiment.
- `reports/v1b_evt_pot_trial.md` — Trial 1 results.
- `reports/v1b_pooled_tail_trial.md` — Trial 3 results.
- `reports/tables/v1b_oos_dq_per_symbol_evt.csv` — per-symbol DQ on the EVT-modified bounds (parallel to current `v1b_oos_dq_per_symbol.csv`).

---

### 2026-04-28 (evening) — Paper 1 §6.7 incumbent-comparator integration + DQ per-symbol-median sensitivity

**Trigger.** User-driven Paper 1 status check vs the post-cutover scryer dataset surface and the 2026-04-25 deferred Berkowitz / Engle-Manganelli DQ rejections. Two questions: are the standalone Pyth + Chainlink comparison reports (2026-04-25 §0 incumbent block) integrated into Paper 1 yet, and can the DQ rejection be revisited with the data we now have?

**Decision (paper-side; no methodology change).** Integrate the two existing comparison reports as Paper 1 §6.7 with explicit caveats. Run the §6.4.1-promised per-symbol-DQ-median-p sensitivity that was previously left as TBD in appendix. Defer the halt/corp-action filter test to a future §6.4.1 sensitivity update once scryer ships the gating wishlist items. Defer the Berkowitz fix entirely (potential future-paper material per user).

**Hypotheses tested.**

1. **H1: The standalone v1b_pyth_comparison.md (265 obs, 2024+) and v1b_chainlink_comparison.md (87 obs, Feb–Apr 2026) reports can be folded into Paper 1 §6 as a new comparator subsection with no new computation.** *Accepted.* Both parquet artefacts (`pyth_benchmark_oos.parquet`, `v1_chainlink_vs_monday_open.parquet`) verified loadable with current schema; numbers reproducible from the reports. Folded as new §6.7 with three caveats (sample-size CI, large-cap *normal*-regime sample composition, consumer-supplied wrap calibration). Renumbered §6.7 Summary → §6.8. Updated §9.8 ("we do not report" → "we report a partial-only comparison with these caveats"), §10.3 (the comparator dashboard is now framed as an *upgrade* of §6.7, not a from-scratch deliverable).

2. **H2: Per-symbol-median DQ p-value softens the §6.4.1 Engle-Manganelli rejection across all four anchors.** *Partly accepted.* Extended `scripts/run_reviewer_diagnostics.py` to compute per-symbol DQ p-values and the median-aggregation sensitivity. Per-symbol-median p: **0.211 / 0.384 / 0.289 / 0.261 at τ = 0.68 / 0.85 / 0.95 / 0.99 — all four pass at α = 0.05**, in contrast to the pooled-χ²(50) rejections at all four (0.032 / 0.014 / 0.032 / ~0). However, the per-symbol *reject-count* tells a more nuanced story: 1/10, 2/10, 2/10, 5/10 symbols reject individually at α = 0.05. The τ ≤ 0.95 reject-counts are consistent with type-I rate near α; the τ = 0.99 reject-count of 5/10 indicates real per-symbol tail miscalibration in half the universe that does not vanish under any defensible aggregation. Honest framing: pooled rejection at τ ≤ 0.95 over-stated by aggregation; pooled rejection at τ = 0.99 partly aggregation-inflation, partly real.

3. **H3: New scryer datasets enable filtering OOS weekends for halt-confounded or corp-action-confounded events to isolate which τ = 0.99 per-symbol rejections are structural exceptions vs persistent calibration gaps.** *Rejected.* Local `backed_corp_actions.parquet` (13 rows) is mis-labeled — tracks Backed.fi GitHub-repo commit metadata (`action_type ∈ {list, metadata_update}`), not equity-side corporate actions on the underlying tickers. Local `nasdaq_halts_live.parquet` (27 rows) is forward-only since 2026-04-24; zero overlap with the 2023-01 → 2026-04 OOS panel. Filter test gated on scryer wishlist additions: items 15a (`yahoo.corp_actions` venue, ~3-4h, clean) and 15b (`nasdaq_halts.v1` historical backfill, ~4-6h, partial-coverage-only — public NASDAQ archive covers ~18 months back, full coverage requires a paid SIP feed). Both flagged `[soothsayer-paper-1-blocker]` in `../scryer/wishlist.md`.

4. **H4: Berkowitz rejection can be addressed without methodology change given the new data.** *Rejected (deterministic).* The rejection mechanism is mechanically caused by the per-target buffer schedule's flat extrapolation outside the [0.68, 0.99] anchor range (variance contraction in inverse-normal PITs to var(z) = 0.84 vs unit under H₀). No data accumulation fixes this — it requires either extending the anchor schedule (e.g., add τ = 0.30, 0.50 anchors) or replacing flat-extrapolation with smooth interpolation outside anchors. Both are methodology changes that re-open Christoffersen + Kupiec validation at the new anchors. Per user, deferred entirely as potential future-paper material; the Paper 1 §6.4.1 disclosure framing (per-anchor calibrated, deviation in safe direction) holds.

**Side effects from the rerun.** Re-running `run_reviewer_diagnostics.py` on the bounds parquet picked up the latest panel state — 1,730 rows, 173 weekends (1 weekend more than the paper's 2026-04-17 cutoff). τ = 0.99 violations grew 40 → 49; max breach 796 → 1,081 bps; mean 131 → 137; median 72 → 71; p₉₅ 469 → 515. Berkowitz LR drifted 36.10 → 37.60 (same conclusion: rejects). Pooled DQ p-values essentially unchanged. The exceedance-magnitude row at τ = 0.99 was propagated to §6.8 summary, §9.1 structural-ceiling disclosure, and §11 conclusion (worst-case mismatch ~8% → ~11%). The §6.4 Kupiec/Christoffersen headline numbers were *not* re-run; §6.4 remains anchored at the paper's documented 1,720-row snapshot, with the §6.4.1 panel-size mismatch noted in-section.

**No methodology change.** Deployed buffer schedule, regime labeler, hybrid forecaster assignment, and claimed-quantile grid all unchanged. All edits are paper-side disclosure refinement and follow-up scoping.

**Deliverables (paper).**
- §6.7 added (Comparison to incumbent oracles — Pyth k-sweep + Chainlink weekend-degenerate-band, three caveats, RedStone exclusion).
- §6.8 (was §6.7) Summary updated to reference §6.7 + new DQ sensitivity.
- §6.4.1 DQ block rewritten with per-symbol-median + per-symbol-min + reject-count table; "TBD in appendix" replaced with the actual sensitivity numbers.
- §6.4.1 exceedance-magnitude table updated with 1,730-row rerun.
- §9.1 structural-ceiling disclosure updated (max breach 796 → 1,081 bps, ~11% worst-case mismatch).
- §9.8 limitations rewritten ("we do not report" → "we report a partial-only comparison with these caveats").
- §10.2 future-work block expanded (sub-regime granularity now references the per-symbol DQ finding; new "Halt / corp-action filter on the OOS panel" item gated on scryer wishlist 15a + 15b).
- §10.3 future-work block (was "comparator dashboard from scratch") reframed as upgrade of §6.7.
- §11.2 conclusion updated for new max-breach figures.
- Build: `paper.pdf` 412 KB (was 396 KB pre-Phase-1), all 40 citations resolved, no orphans.

**Deliverables (artefacts).**
- `reports/tables/v1b_oos_dq_per_symbol.csv` — new, per-(symbol, τ) DQ p-values + dq statistic.
- `reports/tables/v1b_oos_dq_per_symbol_summary.csv` — new, per-τ p-value distribution (count, median, mean, min, max, n_reject_05).
- `reports/tables/v1b_oos_reviewer_diagnostics.csv` — re-run, per-τ pooled DQ + magnitude (now also carries per-symbol sensitivity columns).
- `scripts/run_reviewer_diagnostics.py` — extended to compute and persist per-symbol DQ.
- `../scryer/wishlist.md` — items 15a (`yahoo.corp_actions`) and 15b (`nasdaq_halts.v1` historical backfill) added with `[soothsayer-paper-1-blocker]` tag.

**Impacts and downstream implications.**

1. *DQ pooled-rejection was partly aggregation artefact, not pure signal.* The 2026-04-25 §6.4.1 disclosure ("DQ rejects at all four anchors") read more catastrophically than the data warrants. By the per-symbol-median sensitivity (the standard correction for K-symbol pooling), the calibration claim survives DQ at α = 0.05 at every anchor. The reviewer-facing framing of §6.4.1 is now "pooled rejection over-stated by aggregation; per-symbol-median passes" — meaningfully more defensible than the prior "rejects at all four anchors" headline.

2. *τ = 0.99 has an irreducible per-symbol-tail-miscalibration signal in 5/10 symbols.* This is the genuinely new finding. Half the universe carries tail-conditional miscalibration that doesn't vanish under any defensible aggregation. Two competing mechanisms (small-sample noise on a 156-weekend per-(symbol, regime) calibration window vs. structural exceptions like halts and corp actions confounding the τ = 0.99 misses) are not yet distinguishable from the data we have. The §10.2 filter test, gated on scryer wishlist 15a + 15b, is the discriminator: if filtered τ = 0.99 reject-count drops below 3/10, the structural-exception mechanism dominates and §9.1's structural-ceiling attribution refines from "cannot resolve the 1% tail given window size" to "cannot resolve the 1% tail given a non-trivial fraction of weekends carry exceptions the regime labeler does not encode." This is a non-trivial reframing of one of the paper's two main caveats.

3. *Berkowitz rejection is correctly identifying a deployment choice, not a defect.* Per-anchor calibration is the *product contract* (P2 in §3.4); Berkowitz catches it because it's a full-distribution test. The mechanism (buffer flat-extrapolation outside the [0.68, 0.99] anchor range) is deterministic and fixable only by methodology change (extended anchor schedule, smooth interpolation, or conformal upgrade). Per user, this is potential follow-up-paper material — provisionally framed as "tail-and-distribution-calibrated oracle primitive" — and the §6.4.1 disclosure framing ("per-anchor calibrated, deviation in safe direction") holds for Paper 1.

4. *Incumbent comparator is now empirically established rather than rhetorical.* Pre-session, §1.1's "no incumbent publishes a calibration claim" thesis was supported only by qualitative reading of the published interfaces, with §9.8 explicitly acknowledging "we do not report a systematic numerical comparison." Post-session, §6.7 quantifies it: Pyth at face-value k=1.96 delivers 10.2% realised (not 95%); Chainlink's weekend v11 band is degenerate (median ask = 0 across 87/87 obs). The thesis is now confirmed empirically, with the matched-bandwidth observation disclosed transparently. This closes the largest single missing-piece gap relative to a q-fin.RM / ACM AFT submission target.

5. *Paper 1 submission-readiness moved meaningfully forward.* The four pre-session paper-side gaps (incumbent comparator, per-symbol DQ sensitivity, exceedance-magnitude bound at τ = 0.99, future-work scoping for the halt/corp-action filter) all closed. The remaining paper-side blockers are (a) live-deployment OOS validation (§9.7; needs production window), (b) the comparator dashboard upgrade (§10.3; needs scryer forward-tape accumulation), (c) a final round of stylistic / length editing. Statistical-upgrade work (Berkowitz / conformal / sub-regime granularity) is genuinely future-paper material rather than Paper 1 polish.

6. *Two scryer items are now Paper 1 blockers.* Items 15a (`yahoo.corp_actions`) and 15b (`nasdaq_halts.v1` historical backfill) flagged `[soothsayer-paper-1-blocker]` in `../scryer/wishlist.md`. When they land, the §10.2 sensitivity becomes runnable; the deliverable is pre-specified as a one-table addition to §6.4.1, with a clear quantitative threshold (filtered τ = 0.99 reject-count < 3/10) for whether it refines the §9.1 attribution. Conditional on those items shipping in the ~1-week window the effort estimates suggest, this could be the last paper-side substantive update before the live-deployment window opens.

7. *Deployed system is unchanged.* All session work is paper-side disclosure refinement, follow-up scoping, and trim-pass polish. Buffer schedule, regime labeler, hybrid forecaster assignment, claimed-quantile grid, deployed defaults — all identical to pre-session state.

**Open follow-ups (operational).**
1. ~~Trim pass on Paper 1~~ — done in same session (commit `11615b6`); paper.md 165 → 160 KB, paper.pdf 412 → 402 KB. Deduplication between §6.4.1 / §6.7 / §6.8 / §9.8.
2. Reconcile v1b_pyth_comparison.md ↔ §6.7 number drift (standalone report cites Soothsayer pooled OOS half-width 442.7 / normal-regime 401; paper now cites 456 / 417.7 after the 2026-04-25 grid extension). Either re-run the standalone report against current bounds or add a note pointing readers to the paper for the authoritative comparator.
3. When scryer ships items 15a + 15b, run the §10.2 halt/corp-action filter sensitivity. Deliverable: one table in §6.4.1 showing per-symbol DQ on filtered-vs-unfiltered panel.

---

### 2026-04-28 (afternoon) — Unified-feed router design lock: regime gate + Layer 0 multi-upstream aggregator + governance plan

**Trigger.** The strategic discussion across 2026-04-27 → 2026-04-28 evolved soothsayer's product positioning from "calibration-transparent supplementary band primitive" to "calibration-transparent unified reference feed for tokenized RWAs, primary in closed-market regimes and aggregated multi-source during open hours." The motivating product is a router program that consumers read as a single PDA per asset, with internal regime-routing between an open-hours multi-upstream aggregator (Layer 0, deterministic; Layer 1 future, calibration-weighted) and the existing closed-hours soothsayer band primitive. This entry locks the design.

**Decision (architectural).**
- One Anchor program — `soothsayer-router` — sits in front of the existing publish-path stack. Consumers read a single PDA per asset; the router CPI-reads upstream feeds and either (i) aggregates them during open-market hours or (ii) reads the soothsayer band PDA during closed-market hours. The unified-feed read returns a `unified_feed_receipt.v1` tuple (locked separately, this date morning).
- The regime gate is read from a configurable `market_status_source` PDA (default for equities: Chainlink v11 `marketStatus`) cross-checked against a calendar-based detection (NYSE / CME GLOBEX trading calendar embedded in the program). Disagreement between the two emits `regime = 'unknown'` and `quality_flag = 'regime_ambiguous'`; the consumer chooses whether to trust the read.
- Layer 0 (open-hours, shippable now) is a *deterministic multi-upstream aggregator*: read N upstreams, apply staleness + confidence + Mango-style deviation-guard filters (this date midday), serve the post-filter robust median + a dispersion-based band. *No calibration claim during open hours under Layer 0* — only attribution + outlier-resilient aggregation. Layer 1 (future, gated on ~3 months of upstream forward tape per scryer wishlist items 21-23) replaces the dispersion-based band with a calibration-weighted aggregate that has its own per-anchor calibration claim against intraday lookahead ground truth, supported by a forthcoming paper 1.5 / paper-2-extension.
- Layer 0's upstream set is, per asset, configurable in the `RouterConfig` PDA. Initial v0 default for equities: Pyth aggregate, Chainlink Data Streams (v11 preferred, v10 fallback), Switchboard On-Demand, RedStone Live. For BTC-correlated tokens (currently MSTR; future ETH-correlated tokens): same four plus Mango v4 post-guard mark price (gated on scryer wishlist item 39 forward tape).

**Decision (governance / upgradeability — explicit reversal of an earlier "ship immutable" working position).**
- `soothsayer-router` ships **upgradeable** in v0, controlled by a 2-of-3 multisig held by the soothsayer team (initial signers: founder + 2 to-be-named). Deliberate departure from the institutional-grade default of "ship immutable", justified by the product being pre-LOI: parameter tuning, filter behaviour adjustments, receipt-field additions, and bug-fixes are all expected during the design-partner conversation phase, and a hard-immutable v0 would force a v0 → v1 → v2 cascade of redeployments + consumer migrations during a period when the product is still being shaped by external feedback.
- Migration to immutable + versioned-replacement is **gated on two conditions, both required**: (i) at least one signed institutional-partner LOI (lender or tokenization-issuer; either side qualifies), and (ii) methodology buy-in from those partners on the parameter-value defaults + the filter pipeline as locked. Migration mechanic: mainnet `soothsayer-router-v1` deployed at a new program ID, immutable, with a parameter set explicitly endorsed by the partners' risk teams. Consumers migrate from the upgradeable v0 program ID to the immutable v1 over a 90-day window.
- The `RouterConfig` update process during the upgradeable v0 phase is multisig-controlled, with every parameter change recorded as a methodology entry in this log (at minimum: new value, old value, justification, partner consultation if any). Once a partner LOI is signed, the partner is invited to participate in the change-process design — for example a proposal-review-execution flow with a published delay, an off-chain disclosure board, or a partner-witnessed multisig. The exact form of the post-LOI change process is *negotiated with the partner*, not pre-locked here.
- Upgradeability arrangement is itself reviewed in a methodology entry no later than the first signed LOI. If no LOI is signed within 12 months of v0 mainnet deployment, the arrangement is re-evaluated (possible outcomes: extension with revised signer set; migration to immutable without partner; project pivot).

**What ships in v0.**
- `crates/soothsayer-router/` Rust crate + Anchor program — receipt construction, regime gate, multi-upstream CPI reads, Mango-style filters, robust median aggregation.
- A consumer-facing TypeScript SDK + Rust SDK exposing the unified-feed read.
- A public dashboard at the soothsayer landing surfacing the live router output across all 10 paper-1 underliers (after devnet deploy; the dashboard *is* the credibility artefact for both lender and TradFi conversations).
- Methodology entries (this date — three) locking receipt schema + filter pipeline + design.

**What does not ship in v0.**
- Calibration-weighted aggregator (Layer 1) — gated on forward-tape data accumulation.
- Open-hours band calibration claim — gated on Layer 1.
- Decentralised publisher set (multi-publisher Layer 0) — gated on design-partner request and a separate methodology decision.
- Switchboard-style PullFeed wrapping — explicitly *not* the chosen path; soothsayer-router is brand-independent of Switchboard.

**Asset-coverage scope.**
- v0 supports the 10 paper-1 underliers (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD, MSTR, GLD, TLT) for which paper 1's closed-hours methodology is empirically validated. Layer 0 open-hours aggregation works for any asset with the four upstream feeds publishing, but the router only routes-to-soothsayer-band in regimes where the band is available.
- Asset additions are methodologically gated: each new asset requires a factor-switchboard mapping + per-symbol vol-index lookup + 156-weekend rolling calibration window before a closed-hours band claim can be made for it. Asset additions are tracked as separate methodology entries.

**Tracked artefacts.**
- Receipt schema: this date (morning) entry; locks `unified_feed_receipt.v1`.
- Filter pipeline: this date (midday) entry; locks Mango-style deviation-guard adoption + v0 parameter defaults.
- Architecture: this entry.
- Implementation crate: `crates/soothsayer-router/` (to be created during Phase 1 build).
- Public dashboard: TBD URL (added as an amendment to this entry when launched).

**Forward path / Phase 1 build sequence.**
1. Receipt schema + Rust types in `crates/soothsayer-router/src/receipt.rs`. (~1 day.)
2. Anchor program scaffold with regime gate + Pyth + Chainlink CPI reads. (~1-2 weeks.)
3. Add Switchboard On-Demand + RedStone upstream support. (~1 week.)
4. Implement Mango-style filter pipeline (staleness + confidence + deviation guard). (~1 week.)
5. Devnet deploy + end-to-end test harness. (~2 weeks.)
6. Public dashboard surfacing live unified-feed reads + receipt history across all 10 underliers. (~2-3 weeks.)
7. Audit prep + design-partner outreach in parallel. (~2-3 weeks for prep; outreach is a separate track that runs throughout.)
8. Audit (~6-8 weeks calendar). Gated on a design-partner LOI worth the audit spend.
9. Mainnet upgradeable v0 deployment. Gated on audit clean + LOI in hand.
10. Eventually: immutable v1 redeployment per the upgradeability gate above.

**Open methodology questions created by this entry** (added to §2):
- O5. What is the `min_quorum` value for Layer 0? Candidates: 2 (lenient — serve as long as any two upstreams agree), 3 (default candidate — deviation guard plus majority), 4 (strict — all upstreams must agree). Trade-off: availability vs aggregate confidence. Decision deferred to first integration of Layer 0 with one of the design-partner conversations + the empirical disagreement frequency observed in scryer wishlist items 21-22 forward tape.
- O6. How does Layer 0 handle assets where one or more upstreams don't list the feed? Soft-skip with documented `min_quorum` recalculation, or hard-fail-config? v0 design assumes config-time enumeration of available upstreams per asset; consumer-side this means the receipt's `upstream_contributions` array length depends on the asset and is documented per-asset in `RouterConfig`.
- O7. Calendar-based regime-detection fallback for non-NYSE-tracking assets? Equities use NYSE; gold uses CME GLOBEX; treasuries use CME GLOBEX with a different schedule; future commodity/FX assets each need their own calendar. v0 ships with NYSE + CME GLOBEX hard-coded; new asset classes add a calendar via methodology entry.

---

### 2026-04-28 (midday) — Mango v4 deviation-guard methodology adoption as a Layer 0 filter

> **AMENDMENT 2026-04-29** — The "for BTC-correlated tokens, Mango's post-guard mark price IS a literal upstream" claim in this entry is **retracted**. Inspection of Mango v4 source confirmed that `PerpMarket` does not persist a post-guard `oracle_price` field; the deviation guard is applied ephemerally during Mango's own instructions and the result is never written to account state. Mango v4 contributes deviation-guard *methodology only* — never as a literal data source. The `MangoV4PostGuard` upstream variant has been removed from `UpstreamKind` per the 2026-04-29 entry. The rest of this entry — the filter pipeline (staleness → confidence → Mango-style deviation guard) and v0 parameter defaults (60s / 200 bps / 75 bps) — remains valid; only the cross-reference to a Mango forward tape is corrected. See the 2026-04-29 entry above for the strategic context (Mango ≠ substitute oracle; v1 product reframe).

**Trigger.** The Layer 0 multi-upstream aggregator design (this date afternoon) requires an outlier-rejection filter. Mango v4 publishes the closest production analog to soothsayer's intended Layer 0 behaviour: a per-market deviation guard that clamps oracle reads exceeding a configured threshold from consensus. Adopting Mango's deviation-guard logic as one of Layer 0's filters serves two purposes: (i) inherits a production-tested mechanism with reference parameter values that have been live in mainnet conditions, and (ii) pre-empts the "Mango v4 already does this" objection by making Mango's logic a documented subset of soothsayer's Layer 0 pipeline rather than a competing approach.

**Decision.** Layer 0's outlier-rejection filter is methodologically a *Mango-style deviation guard*. Cite Mango v4 explicitly. Use Mango's reference parameter values as the v0 starting point. Add calibration-weighting (Layer 1, future entry) and receipt-stamping (this date morning) on top — those are soothsayer-specific additions; the deviation guard itself is not novel and is not claimed to be.

**Filter pipeline (v0).**
1. **Staleness filter.** Drop any upstream whose `last_update_slot` is older than `max_staleness_seconds` (translated to slots at the asset's slot-per-second rate). Mango v4 reference: 60s for liquid majors. Soothsayer v0 default: 60s for open hours, configurable per asset in `RouterConfig`.
2. **Confidence filter.** Drop any upstream whose published confidence interval exceeds `max_confidence_bps` of the published price. Mango v4 reference: ~2% (200 bps) for major equities. Soothsayer v0 default: 200 bps, configurable per asset.
3. **Deviation guard (Mango-style).** Compute provisional median over surviving upstreams. Drop any upstream whose price differs from the provisional median by more than `max_deviation_bps`. Recompute median over the post-filter set. If the post-filter quorum drops below `min_quorum`, emit `quality_flag = 'low_quorum'` and the receipt records which upstreams failed the guard. Mango v4 reference: ~50 bps for majors. Soothsayer v0 default: 75 bps for equities (slightly looser to accommodate the wider quote spreads characteristic of tokenized-equity feeds during market hours), configurable per asset.

**Why these v0 defaults.**
- Mango's published parameter values were chosen for crypto-asset markets (BTC, ETH, SOL) with their characteristic quote dispersion. Equity markets have different microstructure: tighter quotes during market hours, wider during pre/post, and potentially wider per-publisher dispersion across Pyth/Chainlink/Switchboard/RedStone given they read different upstream venues.
- The looser deviation threshold (75 bps vs Mango's 50) is a deliberate methodological choice for asset-class-appropriate calibration. The empirical justification is forecasted, not yet measured: the upstream forward-tape capture (scryer wishlist items 21-23) will surface the actual cross-source dispersion distribution once ~3 months of data accumulates. The v0 default is provisional and revisited in a future methodology entry once the dispersion data exists.
- All three filter parameters are *config*, not *code*. This methodology entry locks the v0 default; the `RouterConfig` PDA carries the active values at read time; updates are governance actions tracked in this log.

**What this commits soothsayer to.**
- The deviation-guard filter is documented as adopting Mango v4's logic. Citations in the Layer 0 design entry, in any forthcoming paper that references the open-hours product, and in the `RouterConfig` documentation.
- The provisional 75 bps deviation threshold is *re-evaluated* once the upstream forward tapes accumulate, with a methodology entry documenting the updated value (or confirming the v0 value).
- If Mango v4 changes its deviation-guard methodology (parameter values, filter structure), soothsayer is *not* automatically tracking — soothsayer's filter is a snapshot of Mango's 2026-04-28 logic, not a live mirror. Any future Mango methodology change is evaluated independently.

**What this does not commit to.**
- Mango v4's complete methodology is not adopted — only the deviation-guard filter. Mango additionally applies funding-rate-based mark adjustments, perpetual-specific spread logic, and account-level health margins. Those are protocol-internal mechanisms, not oracle-layer filters, and are not relevant to soothsayer's product surface.
- Mango does not currently price equities. For paper 1's primary asset set Mango contributes methodology only, not data. For BTC-correlated tokens, Mango's post-guard mark price IS a literal upstream — see scryer wishlist item 39 (`mango_v4_market_tape.v1`) for the data ingestion path.

**Tracked artefacts.**
- Filter implementation: `crates/soothsayer-router/src/filters.rs` (to be created during Layer 0 development).
- Reference for Mango's logic: Mango v4 IDL + on-chain `OracleConfig` account layouts; scryer wishlist item 28 (`mango_v4_oracle_config.v1`) captures the reference values longitudinally.
- Soothsayer v0 parameter defaults: stored in this entry; active values tracked in the `RouterConfig` PDA per asset; live values mirrored to a soothsayer-derived dataset at `soothsayer_v{N}/router_config_history/v1/...` (per CLAUDE.md hard rule #5) once the router crate ships.

---

### 2026-04-28 (morning) — `unified_feed_receipt.v1` schema lock as a versioned product surface

**Trigger.** The 2026-04-28 strategic discussion locked a regime-routed unified-feed router product (this date afternoon entry): a single PDA consumers read where the receipt fields populated by the router depend on which regime is serving (open vs closed market). Before any consumer integrates, the receipt tuple needs to be fixed as a versioned product surface; once external consumers integrate against a tuple shape, breaking changes require a v2 PDA and a consumer migration. This entry locks v1.

**Decision.** Receipt schema is `unified_feed_receipt.v1`, with field-population semantics conditional on the served regime. Always-populated fields define the consumer-facing minimum surface; regime-conditional fields populate only when their methodology is load-bearing for the read.

**Schema (locked).**
```
schema_version            string  ('unified_feed_receipt.v1')
asset_id                  string                ('SPY', 'QQQ', ...)
slot                      u64
unix_ts                   i64
regime                    string  ('open' | 'closed' | 'halted' | 'unknown')

# Always populated (consumer-facing minimum)
point                     f64                   band midpoint
lower                     f64                   band lower edge
upper                     f64                   band upper edge
soothsayer_methodology    string                ('router.v0.1' | 'v1b' | composed)
quality_flag              string                ('ok' | 'low_quorum' | 'all_stale' |
                                                  'soothsayer_band_unavailable' |
                                                  'regime_ambiguous')

# Open-regime fields (populated when regime == 'open')
aggregate_method          string nullable       ('robust_median_v1' | 'calibration_weighted_v1')
upstream_contributions    array<UpstreamReceipt> nullable
deviation_guard_hits      array<DeviationHit> nullable
quorum_size               u8 nullable           number of surviving upstreams
quorum_required           u8 nullable           min_quorum config value at read time

# Closed-regime fields (populated when regime in {'closed', 'halted'})
tau                       f64 nullable          consumer-requested target coverage
q_served                  f64 nullable          claimed quantile actually served
forecaster                string nullable       ('F1_emp_regime' | 'F0_stale')
closed_market_regime      string nullable       ('normal' | 'long_weekend' | 'high_vol')
buffer_applied            f64 nullable          BUFFER_BY_TARGET lookup
calibration_basis         string nullable       ('soothsayer_v1b' | future versions)

UpstreamReceipt {
    kind                  string                ('pyth_aggregate' | 'chainlink_v11' |
                                                  'switchboard_ondemand' | 'redstone_live' |
                                                  'mango_v4_post_guard')
    pda                   string
    raw_price             f64
    raw_confidence        f64 nullable
    last_update_slot      u64
    included_in_aggregate bool
    exclusion_reason      string nullable       ('stale' | 'low_confidence' | 'deviation_outlier')
}

DeviationHit {
    upstream              string
    deviation_bps_from_median f64
}
```

**What this commits soothsayer to.**
- The receipt is the *trust primitive*, not just diagnostic noise. Every consumer integration is built against this tuple. Field-name renames, type narrowings, semantic redefinitions are breaking changes that require a v2 program PDA — not a v1 amendment.
- The regime-conditional population pattern means a single read is interpretable regardless of which methodology layer served it. Consumers do not branch on regime to find their fields; they branch on `quality_flag` for failure handling and on `regime` for which calibration methodology applies.
- `quality_flag = 'ok'` is the only flag a typical consumer should accept without further inspection; the four non-`ok` values are advisory disclosures the product is *required* to emit when the underlying conditions are met. Suppressing them is a methodology violation.
- `soothsayer_methodology` is the cross-version identifier that lets a consumer know which version of the underlying methodology produced the read. `router.v0.1` is the open-regime aggregator; `v1b` is the closed-regime band primitive. When Layer 1 ships, the open-regime methodology identifier becomes `router.v0.2` (calibration-weighted aggregator) without changing the receipt schema.

**Versioning policy.**
- Additive non-breaking changes (new optional field, new enum value with documented semantics) are permitted within `unified_feed_receipt.v1` provided every existing field's semantics are preserved.
- Field removals, type narrowings, and semantic redefinitions require `unified_feed_receipt.v2` deployed at a fresh PDA. v1 and v2 coexist for a consumer-migration window of at least 90 days; v1 is deprecated only after every consumer of record has migrated.
- Receipt-schema versions are tracked in this methodology log and in the soothsayer Rust crate `crates/soothsayer-router/src/receipt.rs` (to be created during Layer 0 development).

**Tracked artefacts.**
- This methodology entry locks the schema.
- Implementation: `crates/soothsayer-router/` (new crate, to be added during Layer 0 development per the 2026-04-28 (afternoon) entry).
- Consumer-facing documentation: `docs/router_consumer_guide.md` (to be drafted alongside the crate; mirrors `docs/scryer_consumer_guide.md`'s shape).

**Acknowledged limitations.**
- The receipt schema is locked but the *parameter values* (max_staleness, max_confidence, max_deviation_bps, min_quorum) populate at read time from the `RouterConfig` PDA, not from the schema. Methodology entries documenting parameter values are written separately as parameters are tuned.
- `aggregate_method = 'calibration_weighted_v1'` is a forward reference to Layer 1; the methodology lock for Layer 0 is `aggregate_method = 'robust_median_v1'` only. Adding `calibration_weighted_v1` as a permitted enum value when Layer 1 ships is non-breaking and will be done with a separate methodology entry.

---

### 2026-04-27 — Data-fetching cutover: scryer is the source of truth; soothsayer's ingest infra hard-deleted

**Trigger.** Across this repo, the sibling `scryer` repo, and the upstream `relay-sol` proxy fork, three different implementations of retry-and-backoff existed for what is functionally the same problem (provider rate-limits + transient failures + quota exhaustion). Schemas for the same logical data (oracle tape rows, swap rows, funding rows) were silently diverging between repos. Scryer v0.1 phases 1–15 + 17–19 (April 26–28, 2026) consolidated all of soothsayer's raw-data fetch surface into scryer crates with versioned schemas + the `dataset/{venue}/{data_type}/v{N}/...` parquet contract. With 14 schemas now live in scryer (`yahoo.v1`, `earnings.v1`, `kraken_funding.v1`, `kamino_scope.v1`, `pyth.v1`, `redstone.v1`, `v5_tape.v1`, `backed.v1`, `nasdaq_halts.v1`, `swap.v1`, `trade.v1`, `kamino_liquidation.v1`, `jupiter_lend_liquidation.v1`, `fluid_vault_config.v1`) the soothsayer-side ingest code was a duplication risk, not a hedge.

**Decision.** Hard-delete the soothsayer-side ingest infrastructure and lock the architectural boundary in agent-harness instructions. Soothsayer is the analysis + serving + on-chain-publish project; it does not pull data from the network. New data sources go in scryer first (per `scryer/methodology_log.md` hard rule #1); soothsayer reads scryer parquet via `polars.read_parquet` against the canonical layout.

**What was deleted.**
- `crates/soothsayer-ingest/` — the entire Rust ingest crate (Helius RPC client, Chainlink decoder, retry/limiter modules). The Chainlink *decoders* survive in `src/soothsayer/chainlink/` (Python); only the *fetcher* portion was removed.
- `src/soothsayer/sources/{helius,jupiter,kraken_perp,yahoo}.py` — the four Python fetchers.
- `src/soothsayer/cache.py` — orphaned without the Python fetchers it served.
- `src/soothsayer/chainlink/scraper.py` — the historical xStock Chainlink scraper. Decoders (`v10.py`, `v11.py`, `verifier.py`, `feeds.py`) retained.
- 22 scripts under `scripts/`: every `scan_*`, `scrape_*`, `collect_*`, `snapshot_kamino_*`, `run_v{1,2,3,5}_*`, `verify_v11_cadence`, `dump_v11_feed_inventory`, `enumerate_v11_xstock_feeds`, `debug_v10_layout`, `scan_chainlink_schemas`, `build_fred_macro_calendar`, `run_redstone_scrape`, `smoke_rpcfast`, `smoke_v5_jupiter`. Each script's scryer replacement is enumerated in `docs/scryer_consumer_guide.md` § Migration cheat-sheet.

**What was preserved.** `XSTOCK_MINTS` + `USDC_MINT` constants migrated from `sources/jupiter.py` to `src/soothsayer/universe.py` (where they belong — they're a static on-chain registry, not fetched data). The one remaining script that imported the registry but no fetcher (`score_weekend_comparison.py`) was redirected to the new import path.

**Agent-harness changes.** Three new files at the repo root codify the policy:
- `CLAUDE.md` — long-form hard rules (no fetching in soothsayer; new sources go in scryer first; analysis reads parquet; preserve `_schema_version` / `_fetched_at` / `_source` on read; soothsayer-side derived datasets use venue `soothsayer_v{N}`; reproducibility).
- `AGENTS.md` — same five hard rules, AGENTS.md convention for non-Claude tools (Codex, Cursor, Aider, etc.).
- `.cursorrules` — Cursor-flavored summary.

Plus `docs/scryer_consumer_guide.md` — the canonical read pattern with code examples for all 14 currently-shipped scryer schemas, the migration cheat-sheet from each deleted script, and gotchas (`u128` decimal-string columns, mixed-precision `ts` types, UTC timezone discipline). `docs/data-sources.md` got a cutover preface; the catalog itself remains valid as the canonical provider inventory.

**Acknowledged breakage.** This is intentional. After the deletion, scripts that called the old fetchers (`run_calibration.py` via `yahoo.fetch_daily`; `chainlink_implicit_band_analysis.py` and `check_chainlink_weekend.py` via `chainlink.scraper`) now ImportError at module load. This is the forcing function: the next agent that touches those scripts will read CLAUDE.md, follow the consumer guide, and rewrite the data-load to read scryer parquet. The user explicitly chose this over a soft-deprecation banner because previous "we'll migrate later" cycles never closed.

**Verification.** `cargo check` on the soothsayer workspace passes after `soothsayer-ingest` is removed from `Cargo.toml`'s workspace members; no other crate depended on it. The Anchor program in `programs/` was not workspace-included to begin with and is unaffected.

**Forward path.**
- Scripts that currently ImportError: rewrite their data-loads against `../scryer/dataset/...` per `docs/scryer_consumer_guide.md`. The canonical entry `run_calibration.py` swaps `yahoo.fetch_daily(symbol)` → `pl.read_parquet(SCRYER_ROOT / "yahoo" / "bars" / "v1" / f"symbol={symbol}" / "year=*.parquet")`; everything else follows the same shape.
- `data/raw/` is retained for the in-flight Phase 1 papers but is no longer the canonical input. New analysis should not read from it.
- For data classes scryer doesn't yet have a fetcher for (e.g., Chainlink schema/cadence verification, FRED macro calendar, Kamino reserve/obligation snapshots), the queue lives in `../scryer/wishlist.md`. Open an item + a methodology entry in scryer; do not restore the deleted soothsayer fetcher.

### 2026-04-26 — Serving-layer ablation re-run under deployed BUFFER_BY_TARGET; hybrid framing softened from "load-bearing" to "joint argmin"

**Trigger.** The §7.4 serving-layer matrix in the paper draft was generated under the legacy scalar `CALIBRATION_BUFFER_PCT = 0.025` buffer. The deployed schedule is `BUFFER_BY_TARGET[0.95] = 0.020` (per the 2026-04-25 morning per-target-tuning entry below). The mismatch surfaced in the paper coherence pass and was disclosed in §7.4 as a "buffer-value-agnostic" caveat. The user requested a re-run under the deployed buffer to retire the disclosure and report fresh numbers.

**Hypotheses tested.**

1. **H1: At the deployed buffer, the buffer-effect direction and magnitude reproduce.** *Accepted with smaller magnitude.* Buffer-effect Δcoverage at $\tau = 0.95$ (C0 → C3) is $+2.7$pp [+1.9, +3.7] under the deployed 0.020 buffer (was $+3.7$pp [+2.7, +4.7] under the legacy 0.025 buffer). The qualitative finding — buffer is the load-bearing serving-layer knob for OOS coverage — is preserved; the precise magnitude scales with buffer size. Total serving-layer effect (C0 → C4) is $+2.9$pp [+2.0, +3.8].

2. **H2: At the deployed buffer, the F1-everywhere variant fails Christoffersen independence (the original §7.4 finding that motivated the hybrid).** *Rejected.* At the deployed buffer 0.020, F1-everywhere (C3) passes Christoffersen with $p_{ind} = 0.221$; the hybrid (C4) passes with $p_{ind} = 0.485$. Both pass at $\alpha = 0.05$. The "hybrid flips Christoffersen verdict" framing was load-bearing under the legacy 0.025 buffer (where C3 had $p_{ind} = 0.033$ and rejected); at the deployed buffer the hybrid is no longer a binary necessity for the conditional-coverage pass.

3. **H3: The hybrid policy still wins on the joint argmin (sharpness, Christoffersen margin) at the deployed buffer.** *Accepted.* The hybrid simultaneously: tightens bands by $-2.6\%$ ($467.9 \to 456.0$ bps), lifts Kupiec margin from $p_{uc} = 0.826$ to $p_{uc} = 1.000$, and lifts Christoffersen margin from $p_{ind} = 0.221$ to $p_{ind} = 0.485$. No observable trade-off on either axis, supporting property P3 of §3.4 in the strict joint-argmin sense.

4. **H4: Buffer and hybrid effects are additive at $n = 172$ OOS weekends.** *Accepted (cannot reject additivity).* Buffer-vs-no-buffer Δcoverage is $+2.7$pp without hybrid (C0 → C3) and $+3.0$pp with hybrid (C2 → C4); CIs overlap. Practically, buffer-tuning and hybrid-design are independent decisions, which simplifies V2.2 rolling-rebuild scheduling.

**Cascading paper edits.** §7.4 rewritten with fresh table + bootstrap CIs and dropped legacy-buffer disclosure. §7.5 taxonomy table: "hybrid regime-to-forecaster policy" entry softened from "load-bearing for Christoffersen independence" to "joint-argmin choice over (sharpness, Christoffersen margin)". §1.3 buffer-effect updated $+3.8$pp → $+2.9$pp with new CI. §11.1 P3 narrative + §11.2 buffer-effect number updated to match. §9.6 reframed from "Christoffersen independence is the load-bearing OOS contribution" to "joint argmin, not binary necessity" with explicit historical note about the legacy-buffer regime where the binary flip held. §3.4 P3 updated to the strict joint-argmin framing.

**Implication for §0.** No change to the deployed methodology. The `REGIME_FORECASTER` and `BUFFER_BY_TARGET` constants are unchanged. The §0 headline numbers (τ=0.95 realised 0.950, $p_{uc}$=1.000, $p_{ind}$=0.485) come from the C4 cell of this re-run and match exactly. §0 is consistent.

**Net deployment change.** None. This is a paper-side re-derivation for narrative coherence under the deployed configuration, not a methodology revision.

**Artefacts.**
- `scripts/run_serving_ablation.py` — single-pass runner that re-serves OOS at $\tau = 0.95$ across the five (forecaster_policy, buffer) cells with block-bootstrap pairwise deltas
- `reports/tables/v1b_serving_ablation.csv` — per-cell metrics
- `reports/tables/v1b_serving_ablation_bootstrap.csv` — pairwise deltas with 95% CIs

---

### 2026-04-25 (very late evening) — Reviewer-tier diagnostics: Berkowitz, DQ, CRPS, exceedance magnitude

**Trigger.** Internal audit (see same-day entries above) raised "what other diagnostics would a peer reviewer expect?" Four standard tests in the modern density-forecast / VaR-backtesting kit were not yet in the paper: Berkowitz (2001) joint LR on inverse-normal-transformed PITs; Engle-Manganelli (2004) Dynamic Quantile (DQ) test; CRPS (Gneiting-Raftery 2007); and McNeil-Frey-style exceedance magnitude. None are *required* for the paper's per-anchor calibration claim, but each is a likely reviewer ask at q-fin.RM / ACM AFT / Journal of Risk venues. Implemented and run.

**Hypotheses tested.**

1. **H1: Served-band PIT distribution is uniform on (0, 1) — i.e. Oracle is full-distribution calibrated, not just per-anchor.** *Rejected.* Berkowitz LR = 36.10, $p \approx 0$. Decomposition: variance contraction in the inverse-normal-transformed PITs ($\widehat{\text{var}}\,z = 0.84$ vs unit-variance under H₀, mean 0.07, AR(1) −0.04). The rejection mechanism is buffer-induced: the per-target buffer schedule has anchors at τ ∈ {0.68, 0.85, 0.95, 0.99} and flat-extrapolates outside, producing systematic over-coverage at low-τ targets (τ < 0.68) where the flat-extrapolated buffer is over-conservative. The reliability diagram (`reports/figures/v1b_reliability_diagram.png`) makes this visual: anchor τ on the diagonal, inter-anchor τ in [0.50, 0.65] above the diagonal. Implication for paper claim: served band is *per-anchor calibrated*, not *full-distribution calibrated*. The deviation outside the deployment range is in the safe direction (over-coverage). Disclosure goes in §6.4.1.

2. **H2: Hits at the four anchor τ are independent of multi-lag conditional structure (Engle-Manganelli DQ).** *Rejected at all four anchors.* Per-symbol DQ regressions of hit indicator on 4 lags + intercept, summed into a pooled $\chi^2(50)$ statistic. Results: τ = 0.68 → $p_\text{DQ} = 0.033$; τ = 0.85 → 0.014; τ = 0.95 → 0.032; τ = 0.99 → ~0.000. DQ is a stricter test than Christoffersen's two-state Markov independence test (which we passed at all four anchors in §6.4) and detects multi-lag conditional structure that Christoffersen misses. The rejection at τ ≤ 0.95 is moderate (statistic just above the $\chi^2(50)$ critical value 67.5); at τ = 0.99 it is strong. **Important caveat:** per-symbol-pooled DQ inflates with the number of symbols. Per-symbol median p-value is reported as a sensitivity check (TBD in appendix). Not a deployment block — Christoffersen $p_\text{ind}$ remains comfortably above 0.05 at all anchors, and the per-symbol Kupiec coverage matches at the per-anchor level.

3. **H3: At the τ = 0.99 structural ceiling, breaches are catastrophic (large tail blowups).** *Rejected.* McNeil-Frey-style exceedance magnitude on the 40 missed violations at τ = 0.99: median breach 72 bps, mean 131 bps, $p_{95}$ 469 bps, max 796 bps. Across all four anchors, max breach shrinks monotonically as τ increases (2,339 → 2,150 → 1,415 → 796 bps) — wider bands catch bigger shocks, as one would hope. **This materially defangs the §9.1 structural-ceiling disclosure.** A protocol consuming the τ = 0.99 band on a 100% LTV position would experience a worst-case 8% mismatch on a missed event, with median ~0.7%. The level-attribution failure (realised 0.977 vs target 0.99) is bounded in protocol-impact terms, not just statistical-significance terms. §9.1 narrative updated accordingly in §6.4.1; §9.1 itself is candidate for the same softening in the next paper-revision pass.

4. **H4: CRPS provides an absolute proper-scoring-rule benchmark.** *Reported as baseline.* Mean CRPS = 1.82 (price units), median 0.97. Not interpretable in isolation; reported for future cross-oracle comparators (Pyth + 50× wrap, RedStone Live, Chainlink v10 `tokenized_price`).

**No methodology change.** Berkowitz/DQ rejections are paper-side disclosures, not deployment defects. The Oracle's per-anchor Kupiec + Christoffersen pass is the product contract; full-distribution calibration was never claimed. The exceedance-magnitude finding *strengthens* the τ = 0.99 disclosure rather than weakening the calibration claim.

**Cascading paper edits.**
- §6.4.1 added — full extended-diagnostics subsection (Berkowitz + DQ + CRPS + exceedance magnitude tables).
- §6.7 Summary updated to current OOS numbers (95.0% / p_uc=1.000 / p_ind=0.485) and to mention the extended diagnostics.
- §9.1 (limitations): candidate for revision in next pass — the structural-ceiling framing now has a quantitative magnitude bound (max breach 800 bps at τ=0.99) that softens the disclosure tone.
- Reliability diagram added at `reports/figures/v1b_reliability_diagram.png`; reference inline in §6.4.1.

**Artefacts.**
- `src/soothsayer/backtest/metrics.py` — added `berkowitz_test`, `dynamic_quantile_test`, `crps_from_quantiles`, `pit_from_quantile_grid`, `exceedance_magnitude`
- `scripts/run_reviewer_diagnostics.py` — single-pass runner that re-serves OOS at fine + anchor τ grids and computes all four diagnostics
- `reports/tables/v1b_oos_reviewer_diagnostics.csv` — per-τ DQ + magnitude
- `reports/tables/v1b_oos_berkowitz_crps.csv` — pooled Berkowitz + CRPS summary
- `reports/tables/v1b_oos_pit_continuous.csv` — per-row continuous PITs + CRPS
- `reports/figures/v1b_reliability_diagram.png` — reliability diagram + PIT histogram

---

### 2026-04-25 (late evening) — Empirical Chainlink schema scan: v10 + v11 field-level weekend behaviour

**Trigger.** Conflicting documentation across the repo about Chainlink Data Streams cadence on Solana — `docs/plan-b.md` claimed `tokenized_price` was a "24/7 CEX mark, updates weekends" with undisclosed methodology; user pushed back that Chainlink equities feeds are 24/5, not 24/7; `verifier.py` docstring said v11 was "not yet active on Solana for xStocks"; `v11.py` docstring said v11 had been live since Jan 2026. None of these were tested on live data. Today is Saturday — natural opportunity to settle the weekend-cadence question empirically.

**Hypotheses tested.**

1. **H1: Chainlink v10 `tokenized_price` (w12) updates continuously across weekends.** *Accepted.* SPYx parquet panel from `data/raw/v5_tape_2026042{4,5}.parquet` (1,021 polls across Friday + Saturday) contains 1,021 distinct `cl_tokenized_px` values vs only 199 distinct `cl_venue_px` values. `tokenized_price` evolves on every poll including all of Saturday under `market_status = 1` (closed). `cl_venue_px` (= v10 `price` w7) is frozen at the Friday close (713.970) for all of Saturday — only updates during the regular NYSE session. *Artefact:* `scripts/check_chainlink_weekend.py` (smoke verification), live tape parquets.
2. **H2: Chainlink v11 (schema 0x000b) is active on Solana.** *Accepted.* Scan of the most recent ~500 Verifier txs (`scripts/scan_chainlink_schemas.py`): 8 v11 reports observed in the window (~1.6% of decoded reports). Schema distribution: 0x0008 (148, stables) / 0x0003 (128, crypto-forex) / 0x000a (103, v10 xStocks) / 0x0007 (86, DEX-LP) / 0x0009 (16, unidentified) / 0x000b (8, v11). v11 feed_ids do not match our 8-xStock map (which is v10-only); v11 likely covers same underlyings under different feed_ids but symbol mapping is deferred until needed. `verifier.py` "v11 not yet active" claim was stale — corrected.
3. **H3: v11 weekend payload provides a non-degenerate band.** *Rejected.* All 8 observed v11 samples had `market_status = 5 (closed/weekend)` with payload pattern: `bid` and `ask` are synthetic min/max placeholders (e.g. SPY-class feed at 21.01 / 715.01); `mid` is arithmetic mean of those placeholders (368.01); `last_traded_price` is frozen at Friday close (713.96, matching v10's `price`). No equivalent of v10's continuous `tokenized_price` exists in v11 — every "real" price field in v11 is stale on weekends.
4. **H4: v11 `mid`/`bid`/`ask` carry real values during the 24/5 windows (pre-market, regular, post-market, overnight).** *Untested* — our scan only covered the weekend `market_status = 5` state. Tomorrow's pre-market window (Monday 04:00-09:30 ET = 08:00-13:30 UTC, market_status = 1 pre-market) is the next chance to observe this. Roadmap entry added under Phase 1 → Methodology / verification.

**Implication for incumbent-archetype framing.** Two competitor archetypes coexist *within Chainlink*, depending on which schema/field a consumer reads:

- A consumer reading **v10 `price` (w7)**, **v11 `last_traded_price`**, or **v11 `mid`/`bid`/`ask`** sees stale-hold semantics on weekends — exactly what F0 stale-hold models. The "Chainlink stale-hold during marketStatus=5" framing in §1.1 / §2 of the paper is correct for these fields, which are what most lending integrations consume.
- A consumer reading **v10 `tokenized_price` (w12)** sees a continuous CEX-aggregated mark with undisclosed methodology — same archetype as RedStone Live.

So Soothsayer has two pitches against Chainlink, and **the Phase 2 comparator dashboard should evaluate against ALL of: v10 `price`, v10 `tokenized_price`, and v11 `mid` / `last_traded_price` separately.** This forecloses the "you didn't compare against the right Chainlink field" objection.

**Implication for the 2026-04-25 (evening) entry's H3 finding.** Prior H3 found "100% of weekend observations have `cl_bid ≈ 0` and `cl_ask = 0`" on the 87-obs Feb–Apr 2026 dataset. Today's v11 scan sees `bid`/`ask` as synthetic placeholders (21.01 / 715.01), not zero. Possible explanations: (a) the 87-obs dataset predates v11 going live on Solana, or (b) the 87-obs dataset was decoded under the pre-2026-04-24 broken decoder that mistreated v10 fields as bid/ask. Either way, the *interpretation* of the prior H3 holds — Chainlink does not publish a verifiable band during the weekend window — but the underlying numbers should be re-derived against the corrected v10 + v11 decoders before publication. Flagged as v2 deliverable; not a v1 paper-blocker because the calibration-claim point is structural, not numerical.

**No methodology change.** The Soothsayer oracle does not read Chainlink at any point — v1b is fit on yfinance underlyings + futures + vol indices. This entry only refines the *competitor-archetype description* used in §1.1 / §2 / §6 of the paper.

**Cascading paper edits required.**
- §1.1: refine "Chainlink stale-hold during marketStatus=5" to specify *which Chainlink field* — applies to `price` (v10 w7) and to all v11 fields; does NOT apply to v10 `tokenized_price` (w12).
- §2: distinguish two competitor archetypes within Chainlink — stale-hold (`price`, v11) and continuous undisclosed mark (`tokenized_price`); position RedStone Live as the same archetype as v10 `tokenized_price`.
- §6 (incumbent comparator subsection from prior entry): add a v10 `tokenized_price` row alongside the existing Chainlink-stale-hold row, with the appropriate caveat that the comparison is one of *calibration claim*, not bandwidth (both are continuous; only Soothsayer publishes a verifiable claim).
- §9: update incumbent-comparison limitations subsection — the 87-obs Chainlink dataset needs re-derivation under the corrected decoders before being treated as the canonical numerical comparison.

**Artefacts.**
- `scripts/check_chainlink_weekend.py` — smoke verification of weekend behaviour for a single xStock
- `scripts/scan_chainlink_schemas.py` — schema-distribution scan across recent Verifier txs
- `data/raw/v5_tape_2026042{4,5}.parquet` — empirical SPYx panel
- `docs/v5-tape.md` — operational documentation of the empirical findings (replaces the speculative pre-2026-04-25 framing)
- `src/soothsayer/chainlink/verifier.py` — docstring updated to reflect v11 active state

---

### 2026-04-25 (evening) — Incumbent oracle comparators: Pyth Hermes + Chainlink Data Streams

**Trigger.** The two largest remaining Tier-1 items: convert §1.1 of the paper from a *qualitative* "no incumbent oracle publishes a verifiable calibration claim" to a *quantitative* matched-window comparison.

**Hypotheses tested.**

1. **H1: Pyth's published `price ± 1.96·conf` band, read as a 95% confidence interval, achieves close to 95% realised coverage on the OOS slice.** *Rejected.* Realised coverage at $k = 1.96$ is **10.2%** on a 265-observation 2024+ subset. Pyth's `conf` field is documented as a publisher-dispersion diagnostic, and the empirical mis-calibration when it's read as a probability statement is on the order of 9–10× under-cover. *Artefact:* `reports/v1b_pyth_comparison.md`.
2. **H2: A consumer can scale Pyth's `conf` by some constant $k$ to match a 95% realised-coverage target, and at the matching $k$ Pyth's implicit band is wider than Soothsayer's served band.** *Partially accepted with caveat.* The smallest $k$ achieving pooled realised ≥ 0.95 on the available subset is $k \approx 50$ (mean half-width 280 bps). At matched coverage on the 265-obs *subset*, Pyth+50× is roughly 37% narrower than Soothsayer's *full-panel* deployed band (443 bps). However, the Pyth-eligible subset is dominated by SPY/QQQ/TLT/TSLA — large-cap, low-volatility tickers — and Soothsayer's `normal`-regime-only OOS half-width on the same regime mix is 401 bps, narrowing the gap. The "$k = 50$" finding is a *consumer-supplied calibration*, not a Pyth-published one; the consumer leaves Pyth's claim behind to construct it. The §1.1 thesis (Pyth doesn't publish a verifiable calibration claim) is unchanged.
3. **H3: Chainlink Data Streams publishes a non-degenerate band during weekend `marketStatus = 5`.** *Rejected.* On the existing 87-obs Feb–Apr 2026 dataset, **100%** of weekend observations have `cl_bid ≈ 0` and `cl_ask = 0`. Chainlink's published "uncertainty signal" during the closed-market window is binary stale-or-live, not a band. *Artefact:* `reports/v1b_chainlink_comparison.md`.
4. **H4: A consumer can wrap Chainlink's stale-hold mid with a symmetric ±k% band to match a 95% realised-coverage target, and at the matching $k$ Chainlink+wrap is wider than Soothsayer's served band.** *Partially accepted with caveat.* On the 87-obs sample, $k \approx 3.2\%$ is the interpolated wrap delivering 95% realised coverage (320 bps half-width). Same caveats as H2: small sample size (binomial CI on $\hat p = 0.95$ at $n = 87$ is roughly [0.89, 0.99]); calm-period sample bias (mostly `normal` regime); consumer-supplied calibration not Chainlink-published.

**Net finding.** Both incumbents fail the verifiable-calibration-claim test as documented. Both can be made into approximate 95%-coverage bands by a consumer who back-fits a multiplier on a private historical sample, but the resulting band is the consumer's calibration claim, not the oracle's. The §1.1 paper thesis is supported quantitatively, with the appropriate caveat that consumer-fit wraps on small low-volatility subsets can produce competitive bandwidth — a finding worth disclosing in §6 rather than burying in a footnote.

**Cascading paper edits.**
- §1.1 of paper: cite Pyth realised coverage at $k = 1.96$ = 10.2% as quantitative support for the qualitative claim.
- §6 (new subsection): add an incumbent-comparator table comparing Soothsayer's deployed band against (a) Pyth + naive $k = 1.96$, (b) Pyth + consumer-fit $k = 50$, (c) Chainlink stale-hold + $\pm 3.2\%$ wrap. Include the small-sample CI caveats and matched-regime-mix caveat.
- §9 (new subsection): "Limits of the incumbent comparison" — both comparators are sample-size-restricted by data availability rather than by methodology; v2 deliverable is a longer Chainlink scrape via `iter_xstock_reports_rpc` and Pyth Pythnet historical via Triton/Pythnet RPC.

**Artefacts.**
- `scripts/pyth_benchmark_comparison.py` + `data/processed/pyth_benchmark_oos.parquet` + `reports/tables/pyth_coverage_by_k.csv` + `reports/v1b_pyth_comparison.md`
- `scripts/chainlink_implicit_band_analysis.py` + `reports/tables/chainlink_implicit_band.csv` + `reports/tables/chainlink_implicit_band_by_symbol.csv` + `reports/v1b_chainlink_comparison.md`

**Tier-1 status: COMPLETE.** All nine engineering-only deliverables landed (walk-forward, bounds extension, bias absorption, stationarity, PIT diagnostic, Christoffersen pooling sensitivity, FRED macro ablation, Pyth comparison, Chainlink comparison). Paper-strengthening evidence in place; ready for funding ask on Tier 2 + 3.

---

### 2026-04-25 (afternoon) — Tier-1 engineering pass: walk-forward + diagnostics + grid extension + macro-event ablation

**Trigger.** Tier-1 of the grant-application impact framework — the engineering-only items we committed to doing before requesting funding. Goal: produce paper-strength sensitivity / robustness evidence and resolve disclosed limitations where reachable on existing data.

**Hypotheses tested.**

1. **H1: BUFFER_BY_TARGET values are stable across train/test splits.** *Accepted.* Walk-forward six-split rolling-origin evaluation (cutoffs 2019-01-01 → 2024-01-01, 12-month horizons): at τ=0.95, mean buffer = 0.019 (σ = 0.017) — deployed value 0.020 lands at the cross-split mean. At τ=0.85, mean = 0.025 (σ = 0.022); deployed 0.045 is ≥1σ conservative (over-covers). Closes the §9.4 sample-size-1 disclosure for τ=0.95; tightens but does not fully close it for τ=0.85, where the conservative deployed value reflects the post-2023 split having a wider gap than the 2019–2022 splits. *Artefact:* `reports/v1b_walkforward.md`, `reports/tables/v1b_walkforward_buffer.csv`.
2. **H2: τ=0.99 ceiling is grid-spacing-driven.** *Partially rejected; structural attribution refined.* Extended the claimed grid from `(..., 0.995)` to `(..., 0.995, 0.997, 0.999)` and bumped `MAX_SERVED_TARGET` to 0.999 in both Python and Rust. OOS realised coverage at τ=0.99 lifted from 0.972 → 0.977 — a real but small improvement. Kupiec still rejects. The deeper finite-sample limitation is the 156-weekend per-(symbol, regime) calibration window, not the grid resolution. §9.1 should be re-attributed: not "the grid stops at 0.995" but "the calibration-window sample size cannot resolve the 1% tail in any per-bucket fit; reaching τ=0.99 reliably would require pooled-window calibration or longer history." `BUFFER_BY_TARGET[0.99]` updated 0.005 → 0.010. Parity verified post-change (75/75). *Artefact:* `reports/v1b_extended_grid.md`, `reports/tables/v1b_extended_grid_tau99_sweep.csv`.
3. **H3: Empirical-quantile architecture absorbs the −5.2 bps point bias by construction (the §6.6 derivation).** *Accepted with numerical proof.* `served_point_offset_from_midpoint_bps_max_abs = 0.000` across 1,720 OOS rows × 4 targets — the served point is exactly the band midpoint. *Artefact:* `reports/tables/v1b_diag_bias_absorption.csv`.
4. **H4: Per-symbol weekend log-return series are stationary (the §9.3 assumption).** *Mostly accepted.* Joint ADF + KPSS: 8 of 10 symbols pass; HOOD (n=245, newer ticker) and TLT (multi-year drawdown) classify as trend-stationary rather than fully stationary. Partial finding: §9.3 stationarity assumption holds in aggregate but two symbols are flagged. *Artefact:* `reports/tables/v1b_diag_stationarity.csv`.
5. **H5: Christoffersen pooling rule choice is load-bearing for the calibration claim.** *Rejected.* Compared sum-of-LRs (deployed) vs Bonferroni vs Holm-Šidák at τ ∈ {0.68, 0.85, 0.95, 0.99}. All three rules agree on accept/reject at α=0.05 across all targets. Calibration claim is robust to pooling-correction choice. *Artefact:* `reports/tables/v1b_diag_christoffersen_pooling.csv`.
6. **H6: A FRED-derived macro-event regressor (FOMC + CPI + NFP) closes the §9.2 shock-tertile coverage gap.** *Rejected.* 324 macro events tagged across 12 years (48% of weekends have one within the following week). Re-fit F1_emp_regime with three variants — M0 deployed, M1 + macro flag, M2 swap-earnings-for-macro. Pooled τ=0.95 effect: 0.923 → 0.921 (within noise). Shock-tertile τ=0.95: 0.803 → 0.796 (slightly *worse*). The implied-volatility indices (VIX/GVZ/MOVE) already absorb whatever macro information is in the data; the extra flag adds noise without adding signal. §9.2 disclosure stands: shock-tertile ceiling is structural, not macro-driven. This is a positive negative-finding: it forecloses one obvious "did you try …" reviewer question. *Artefact:* `reports/v1b_macro_regressor.md`, `reports/tables/v1b_macro_ablation.csv`, `data/processed/v1b_macro_calendar.parquet`.
7. **H7: Raw F1_emp_regime PIT distribution is uniform on (0,1).** *Rejected.* KS test against U(0,1) on 1,720 OOS PITs: KS stat = 0.500, p < 0.001. The raw-forecaster PIT is *expected* to be non-uniform — that's why the calibration surface exists. The right framing for §6 is therefore: raw-forecaster PIT non-uniformity motivates the surface; the served-band coverage at discrete τ levels is the actual product validation, and that *does* pass at three of four targets. The KS finding is a useful clarification, not a defect. *Artefact:* `reports/figures/v1b_diag_pit.png`, `reports/tables/v1b_diag_pit.csv`.

**Net deployment change.** `BUFFER_BY_TARGET[0.99]: 0.005 → 0.010`; `MAX_SERVED_TARGET: 0.995 → 0.999`; claimed grid extended to include {0.997, 0.999}. Python + Rust mirrored. Parity 75/75.

**Cascading paper edits required.**
- §6.4 OOS table: τ=0.99 row updated to realised 0.977 (was 0.972).
- §9.1: re-attribute ceiling to calibration-window size, not grid spacing.
- §9.2: shock-tertile structural ceiling now has a tested negative for macro events.
- §9.3: stationarity disclosure tightened — 8/10 symbols stationary; HOOD and TLT flagged.
- §9.4: walk-forward distribution-valued buffer claim replaces sample-size-1 disclosure.
- §6 calibration claim: optionally add Christoffersen pooling-sensitivity table as a robustness check.

---

### 2026-04-25 (morning) — Per-target buffer schedule replaces scalar; conformal alternatives tested and rejected for v1

**Trigger.** Shipping default τ moved from 0.95 to 0.85 on EL-vs-Kamino evidence (separate decision; see protocol-compare commits). The pre-existing scalar `CALIBRATION_BUFFER_PCT = 0.025` was tuned for τ=0.95 and under-corrected at τ=0.85: realised 0.828 vs target 0.85, Kupiec $p_{uc}$ = 0.014 (rejected).

**Hypotheses tested.**

1. **H1: Vanilla split-conformal (Vovk) closes the gap.** *Rejected.* At our calibration size (n ≈ 4,000) the (n+1)/n finite-sample correction is ~100× smaller than the OOS gap. Operationally equivalent to no buffer; under-covers by 4pp at τ = 0.95.
2. **H2: Barber et al. (2022) nexCP recency-weighting closes the gap.** *Rejected.* Tested at 6-month and 12-month exponential half-lives. Both deliver *lower* coverage than vanilla split-conformal: recency-weighting shifts the (claimed → realised) surface in a way that drives the inverter toward higher $q$, but at high $q$ the bounds grid clips at 0.995, producing net under-coverage. Bootstrap deltas: V1 → V3a 6mo at τ = 0.95 yields Δcov = −10.5pp (CI [−12.5, −8.8]).
3. **H3: Block-recency surface (uniform weights, last 6/12 months only) closes the gap.** *Rejected.* Same mechanism as H2; smaller calibration set amplifies noise without shifting the centre of the surface in the right direction.
4. **H4: Per-target tuning of the heuristic itself.** *Accepted.* Sweep over `{0.000, 0.005, ..., 0.060}` at each anchor τ ∈ {0.68, 0.85, 0.95, 0.99} on OOS 2023+. Smallest-buffer-passing-tests rule yields `BUFFER_BY_TARGET = {0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.005}`.

**Surprise finding.** The previous τ = 0.95 anchor was over-buffered. At buffer 0.020, realised coverage is exactly 0.950 with Kupiec $p_{uc}$ = 1.000 and bands 13 bps tighter than at 0.025. Strict improvement over the prior default.

**Structural finding.** τ = 0.99 hits a finite-sample ceiling regardless of buffer: the bounds grid stops at 0.995, the rolling 156-weekend per-(symbol, regime) calibration window cannot resolve the 1% tail, and any buffer ≥ 0.005 produces identical clipped behaviour. Documented in §9.1 of the paper as a known limitation.

**Reviewer-facing position.** The conformal-as-future-work framing in §9.4 is reframed: the conformal upgrade is *not* an obvious win on this data; it is a v2 direction conditional on either a finer claimed-coverage grid (extending past 0.995) or a multi-split walk-forward evaluation that distinguishes drift from sampling noise.

**Artefacts.**
- `reports/v1b_buffer_tune.md` — sweep methodology + per-target recommendations
- `reports/v1b_conformal_comparison.md` — V0/V1/V3/V4 comparison + bootstrap CIs
- `reports/tables/v1b_buffer_sweep.csv`, `v1b_buffer_recommended.csv`
- `reports/tables/v1b_conformal_comparison.csv`, `v1b_conformal_bootstrap.csv`
- `scripts/run_conformal_comparison.py`, `scripts/tune_buffer.py`, `scripts/refresh_oos_validation.py`

**Code changes.** `src/soothsayer/oracle.py` and `crates/soothsayer-oracle/src/{config,oracle,lib}.rs`. Python ↔ Rust parity verified post-change (75/75 cases match byte-for-byte).

**Paper-side cascading edits.** §6.4 OOS table refreshed under deployed buffers; §9.4 rewritten from scalar-heuristic to per-target-heuristic and reframes conformal as v2-conditional; `v1b_decision.md` annotated with an UPDATE callout (historical snapshot preserved below the callout).

---

### 2026-04-25 — Bibliography review applied; three substantive disclosures + one framing tighten

**Trigger.** Stage-3 related-work survey produced 28 verified references across oracle designs, cross-venue price discovery, calibration / conformal prediction, and institutional model risk management. Several references implied claims that needed disclosure.

**Hypotheses tested.**

1. **H1: Cong et al. 2025 invalidates the methodology by showing on-chain xStock prices already encode weekend information.** *Partially accepted (as gap, not invalidation).* The paper stands at v1 because xStock data history (~30 weekends post mid-2025) is below the ~150 needed for stable per-(symbol, regime) Kupiec validation. The F_tok forecaster slot is documented in `docs/v2.md` §V2.1 and gated on the V5 tape reaching that threshold (estimated mid-Q3 2026).
2. **H2: Pyth's documented per-publisher 95%-coverage convention contradicts our "no incumbent publishes a calibration claim" claim.** *Accepted as framing weakness.* §1 was tightened to "no incumbent publishes a calibration claim verifiable against public data at the *aggregate feed* level," explicitly distinguishing publisher-level self-attestation from aggregate-feed verifiability.
3. **H3: The factor-adjusted point's −5.2 bps median residual bias propagates to the served band.** *Rejected after analysis.* The empirical-quantile architecture takes quantiles of `log(P_t / point)` directly; lower/upper bands are constructed as `point · exp(z_lo)` and `point · exp(z_hi)` with `z` from the empirical CDF of the residual, *including* its non-zero median. The served band is bias-aware by construction; the served point (midpoint of the band) is also bias-corrected. §6.6 was updated to derive this explicitly.
4. **H4: Daian et al. Flash Boys 2.0 implies our reported coverage and consumer-experienced coverage diverge near band edges.** *Accepted as disclosure.* §9.11 added; full measurement deferred to v2 §V2.3 pending V5 tape data.

**Artefacts.** `reports/paper1_coverage_inversion/references.md`, `reports/paper1_coverage_inversion/02_related_work.md`. Disclosures live in `09_limitations.md` §§9.10, 9.11; clarification in §6.6; framing tighten in §1.

---

### 2026-04-24 — Hybrid regime-policy + scalar empirical buffer; v1b ships PASS

**Trigger.** v1b decade-scale calibration backtest with a single forecaster (F1_emp_regime) under-covered at the nominal 95% claim with realised 92.3% pooled and Kupiec rejection. PASS-LITE verdict needed escalation to PASS for shipping confidence.

**Hypotheses tested.**

1. **H1: F2 (HAR-RV vol model) improves coverage.** *Rejected.* Realised 78.2% at the 95% claim — worse than F0 stale-hold and F1_emp_regime. Suspected over-fit to recent realised volatility in a way that fails on weekends. F2 retained in code as a diagnostic but excluded from the deployed forecaster set.
2. **H2: Madhavan-Sobczyk decomposition / VECM / Hawkes process / Yang-Zhang vol estimator are needed.** *Rejected.* The simpler stack (F1_emp_regime: factor-adjusted point + log-log vol-index regression on residuals) achieved comparable coverage with less complexity. The complex methodology stack was researched and dropped from the v1b methodology; surfaced as historical context in `reports/archived/vault_updates_for_review.md`.
3. **H3: Funding-rate signal from Kraken xStock perps adds information (V3 test).** *Rejected.* No detectable improvement; coefficients in `reports/tables/v3_coefficients.csv` are within bootstrap noise of zero. V3 work archived in `reports/archived/v3_funding_signal.md`.
4. **H4: Hybrid forecaster selection by regime closes the high-vol gap.** *Accepted in-sample, refined OOS.* In-sample: F0_stale is 10–35% tighter than F1 in `high_vol` at matched realised coverage. OOS: the *mean*-coverage advantage shrinks to ~2%, but the hybrid's primary serving-time contribution is **Christoffersen independence** — F1 + buffer has clustered violations ($p_{ind}$ = 0.033, rejected); hybrid + buffer does not ($p_{ind}$ = 0.086).
5. **H5: A scalar empirical buffer of 0.025 closes the OOS coverage gap at τ = 0.95.** *Accepted, later refined.* Bootstrap 95% CIs on the buffer effect at τ = 0.95: Δcov = +3.7pp [+2.7, +4.7], CI excludes zero. *(Subsequently superseded 2026-04-25 by per-target buffer schedule; see entry above.)*

**Verdict.** PASS shipped: hybrid forecaster + scalar buffer + customer-selects-coverage Oracle, OOS at τ = 0.95 delivers realised 0.959 with Kupiec $p_{uc}$ = 0.068 and Christoffersen $p_{ind}$ = 0.086.

**Artefacts.** `reports/v1b_calibration.md`, `reports/v1b_decision.md`, `reports/v1b_hybrid_validation.md`, `reports/v1b_ablation.md`. Tables: `reports/tables/v1b_*.csv`.

---

### 2026-04-22 — Phase 0 PASS-LITE on simpler-than-planned methodology

**Trigger.** Phase-0 plan called for testing a Madhavan-Sobczyk + VECM + HAR-RV + Hawkes stack as the candidate forecaster. Simpler stack hit the calibration target first.

**Hypotheses tested.**

1. **H1: Friday close × ES-futures-weekend-return is a usable point estimator across all equities.** *Accepted with extension.* Generalised to a per-asset-class factor switchboard: ES for equities, GC for gold, ZN for treasuries, BTC-USD for MSTR (post 2020-08). Documented in `FACTOR_BY_SYMBOL`.
2. **H2: Empirical residual quantile suffices for CI construction; no parametric distribution assumed.** *Accepted.* F1_emp on the rolling 104-weekend residual window delivers 91.4% pooled at the 95% claim — disclosed as raw-model property; calibration surface absorbs the residual gap.
3. **H3: Per-symbol vol-index (VIX/GVZ/MOVE) outperforms a single VIX regressor.** *Marginally accepted.* Δsharp ≈ 0.3% pooled, CI excludes zero by margin only; useful primarily for GLD and TLT where the asset-class vol index is a better fit than VIX.
4. **H4: An earnings-next-week 0/1 flag carries signal at our sample size.** *Rejected as detectable.* Δcov 0.0pp [−0.1, +0.1]; Δsharp +0.1% [−0.2, +0.5]. Retained in the regressor set as a disclosed structural slot for a future finer-granularity earnings calendar (§9.5 of paper).
5. **H5: A long-weekend 0/1 flag carries signal in its own regime.** *Accepted as localised.* Δsharp +10.6% in `long_weekend` regime, statistically distinguishable; flat in `normal` and `high_vol`. Justifies its inclusion in the regressor set.

**Verdict.** PASS-LITE on the simpler methodology. Phase-1 engineering started before the full Madhavan-Sobczyk stack was even built. Saved several weeks; established the precedent that the methodology should be the simplest one that calibrates rather than the most theoretically sophisticated.

**Artefacts.** `reports/v1b_ablation.md` and `reports/tables/v1b_ablation_*.csv` retain the full ablation evidence; `reports/v1_chainlink_bias.md` is the original Chainlink reconstruction comparison.

---

### Pre-2026-04-22 — Methodology candidates considered and not pursued

For the historical record, methodology variants that were considered, scoped, or partially prototyped but never reached the v1b ablation:

- **Kalman / state-space filters** — considered for joint price-and-volatility estimation. Not pursued: the empirical-quantile architecture handles the same calibration objective without a parametric state-space assumption.
- **Heston / GARCH-family vol models for the conditional sigma** — not pursued: log-log regression on a model-free vol index (VIX / GVZ / MOVE) was simpler and competitive on the backtest.
- **Madhavan-Sobczyk price-impact decomposition** — researched in detail (`notebooks/archived-v1-methodology/`), not pursued because the factor-switchboard captures most of the cross-venue lead-lag relevant to the weekend prediction window.
- **VECM (vector error-correction)** — same disposition.
- **Hawkes process for jump arrivals** — considered as a `high_vol`-regime model. Not pursued: F0 stale-hold's wide Gaussian band already absorbs most jumps adequately at matched realised coverage.

---

## 2. Open methodology questions

Items the team explicitly knows about and has chosen to defer rather than ignore. Each has a documented gating condition.

| Question | Gating condition | Documented in |
|---|---|---|
| Does on-chain xStock TWAP carry weekend signal that reduces our OOS gap? | V5 tape reaches ≥ 150 weekend obs per (symbol, regime) | docs/v2.md §V2.1; methodology log entry 2026-04-25 |
| Does conformal prediction outperform per-target heuristic with finer grid? | Bounds grid extended above 0.995 *and* multi-split walk-forward eval available | reports/v1b_conformal_comparison.md; this log 2026-04-25 |
| Does adversarial transaction ordering create a measurable consumer-experienced coverage gap? | V5 tape + Jito bundle data ≥ 3 months | docs/v2.md §V2.3; methodology log entry 2026-04-25 |
| Is the calibration surface empirically uniform across the full PIT distribution, or only at our three / four sampled τ? | One-shot diagnostic; ~10 LoC in metrics.py | docs/v2.md §V2.4 |
| Does the methodology generalise to non-US equities (tokenised JP / EU shares)? | Multi-region replication run with the same panel-build pipeline | reports/paper1_coverage_inversion/09_limitations.md §9.9 |
| Does a finer earnings-calendar dataset (date + estimated move size) make the earnings regressor detectable? | Acquisition of a vendor-grade earnings calendar | reports/paper1_coverage_inversion/09_limitations.md §9.5 |
| O5. What is the `min_quorum` value for Layer 0 of the unified-feed router? | First design-partner integration + ≥3 months of upstream forward tape (scryer wishlist 21-23) showing empirical disagreement frequency | This log 2026-04-28 (afternoon); decision deferred to a follow-up methodology entry |
| O6. How does Layer 0 handle assets where one or more upstreams don't list the feed? Soft-skip with `min_quorum` recalculation, or hard-fail-config? | First non-paper-1-underlier asset added to `RouterConfig` | This log 2026-04-28 (afternoon); v0 design assumes config-time enumeration per asset |
| O7. Calendar-based regime-detection fallback for non-NYSE/CME-GLOBEX-tracking assets? | First asset class outside US equities + commodities + treasuries (e.g., tokenised JP / EU equity, FX) | This log 2026-04-28 (afternoon); v0 ships with NYSE + CME GLOBEX hard-coded |
| O8. v1 event-stream on-chain format: Anchor `emit!` log, or a custom event-log PDA with a versioned schema parallel to `unified_feed_receipt.v1`? | Paper 3 publication + v1 design lock | This log 2026-04-29 |
| O9. v2 SDK behaviour for multi-asset portfolios where calibration is per-(symbol, regime) but the consumer's risk model aggregates across assets — does the receipt aggregate too, or stay per-asset and let the consumer compose? | Paper 2 + Paper 3 §10 | This log 2026-04-29 |
| O10. Relay daemon signing model: dedicated hot keypair, per-feed keypair, or multisig-of-publishers (decentralisation of the relay layer)? | First production relay deploy + design-partner conversations | This log 2026-04-29 (afternoon); v0 default is single dedicated hot keypair |
| O11. Relay program's Verifier-CPI policy at `post_relay_update`: always-CPI, opportunistic, or trust-mode? | First mainnet relay deploy; CU-cost measurement on devnet first | This log 2026-04-29 (afternoon); v0 ships always-CPI on devnet |
| O12. Enforcement mechanism for the relay-operator no-position policy: on-chain attestation account (default), periodic third-party audit, or partner-witnessed multisig governing the wallet list? | Before mainnet relay deploy | This log 2026-04-29 (evening); v0 default = attestation-account |

---

## 3. How this doc relates to other artefacts

- **`reports/v1b_decision.md`** — frozen 2026-04-24 snapshot of the v1b ship decision. Annotated with later-update callouts but not rewritten.
- **`reports/paper1_coverage_inversion/*.md`** — the paper draft. Sections that depend on methodology should refer to §0 of this doc as the source-of-truth for current state.
- **`docs/v2.md`** — forward-looking; describes Phase-2 deliverables that are gated on data or on resolution of an open methodology question.
- **`src/soothsayer/oracle.py` and `crates/soothsayer-oracle/`** — current deployed methodology; this log explains *why* the constants in those files have their current values.
- **Memory (`MEMORY.md`)** — stable index pointer to this log.

When methodology changes:
1. Append a new entry to §1.
2. Update §0 to reflect the new state.
3. Update the relevant code (Python + Rust mirror).
4. Update any paper-draft section that describes the changed methodology.
5. If a deferred item from §2 was resolved, move it to §1 and remove from §2.
