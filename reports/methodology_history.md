# Methodology evolution log

**Purpose.** Operational source of truth for Soothsayer methodology and agent handoff. This file is intentionally compact as of 2026-05-02: keep current decisions, active gates, and links to evidence. Long derivations belong in the linked reports, not in startup context.

**Update rule.** When methodology changes, update §0 and append a short dated entry to §1. Keep entries decision-shaped: trigger, decision, evidence pointer, impact, open work. Do not paste full analysis transcripts here.

---

## 0. State of the world

*Last compacted 2026-05-02. Operational state reflects the 2026-05-01 scryer reconciliation.*

### Product and repo role

Soothsayer is the analysis, serving, and on-chain-publish layer for a calibration-transparent fair-value oracle for tokenized RWAs on Solana. Upstream data fetching belongs to the sibling `scryer` repo. Soothsayer consumes parquet from `SCRYER_DATASET_ROOT`, serves calibrated bands, writes derived artefacts, and builds protocol-facing policy demos.

Product progression:

- **v0 — calibrated band primitive / unified-feed router.** Open-hours Layer 0 multi-upstream router plus closed-hours Soothsayer band. Devnet router deployed 2026-04-29 at `AZE8HixpkLpqmuuZbCku5NbjWqoQLWhPRTHp8aMY9xNU`.
- **v1 — calibrated event stream.** Consumer-configured threshold events with calibration receipts; gated on Paper 3.
- **v2 — parameterized decision SDK.** Client-side Rust/TS library for cost-weighted recommendations; 2027 track.

### Current methodology constants

- Default deployment target: `τ = 0.85`.
- Headline Paper 1 validation target: `τ = 0.95`.
- Served range: deployment-quality evidence is strongest for `τ ∈ [0.52, 0.98]`; `τ = 0.99` remains disclosed as a finite-sample tail ceiling.
- Hybrid forecaster: `normal` and `long_weekend` use `F1_emp_regime`; `high_vol` uses `F0_stale`.
- Buffer schedule: `{0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.010}` with linear interpolation off-grid.
- Code truth: `src/soothsayer/oracle.py`, `crates/soothsayer-oracle/src/{config,oracle}.rs`, and `data/processed/v1b_bounds.parquet`.

### Validated empirical claims

Held-out 2023+ slice: 1,720 rows, 172 weekends, 10 tickers.

| τ | Realized | Kupiec | Christoffersen | Status |
|---:|---:|---:|---:|---|
| 0.68 | 0.678 | 0.893 | 0.647 | pass |
| 0.85 | 0.855 | 0.541 | 0.185 | pass |
| 0.95 | 0.950 | 1.000 | 0.485 | pass |
| 0.99 | 0.977 | rejects | 0.956 | disclose ceiling |

Important diagnostics:

- Walk-forward: deployed `τ=0.95` buffer sits at cross-split mean; `τ=0.85` buffer is conservative.
- Inter-anchor sweep: 47/50 targets pass Kupiec; failures at `τ=0.50/0.51` over-cover and `τ=0.99` tail ceiling.
- Leave-one-out: pooled calibration transfers to unseen tickers; 26/30 cells pass Kupiec.
- Reviewer-tier diagnostics: per-anchor calibration is supported; full-distribution PIT uniformity is not claimed.
- Window sweep: 156-weekend calibration window is the only tested window passing all three main anchors simultaneously.

Detailed evidence lives in `reports/v1b_calibration.md`, `reports/v1b_ablation.md`, `reports/v1b_diagnostics_extended.md`, `reports/v1b_window_sensitivity.md`, and `reports/v1b_leave_one_out.md`.

### Data spine

Hard rule: no upstream fetching in Soothsayer. Use `soothsayer.config.SCRYER_DATASET_ROOT` and `soothsayer.sources.scryer` loaders.

Current important scryer datasets:

- Core oracle/paper data: `yahoo/equities_daily`, `yahoo/earnings`, `yahoo/corp_actions`, `nasdaq/halts`, `backed/corp_actions`, `backed/nav_strikes`, `cme/intraday_1m`.
- Oracle tapes: `pyth/oracle_tape`, `chainlink_data_streams/report_tape`, `redstone/oracle_tape`, `kamino_scope/oracle_tape`, `soothsayer_v5/tape`.
- Market / protocol data: `geckoterminal/trades`, `kraken/funding`, `solana_dex/xstock_swaps`, `kamino/liquidations`, `marginfi/reserves`.

If docs and disk disagree, verify the live root and then update the doc; do not infer path names from older shorthand.

### Paper 1 status

Paper 1 validates the calibration-transparent oracle primitive, not welfare-optimal protocol policy. Draft sections exist under `reports/paper1_coverage_inversion/`. Remaining operational work:

- Finish method/data/serving sections and coherence pass.
- Keep comparator wording clean: flat `±300bps` is a stylized continuity baseline, not the literal Kamino incumbent.
- Update Chainlink v10/v11 / 24-5 cadence framing from the latest decoder and scryer evidence.
- Add caveats for Wayback halt sparsity and any live-xStock claim that is not backed by tape.
- Consider replacing daily-factor weekend DiD with `cme/intraday_1m` before submission.

### Paper 3 status

Paper 3 is now a three-claim liquidation-policy paper:

- **Geometric.** Real per-reserve adverse-move buffers split Kamino-xStocks into narrow-buffer SPYx/QQQx (~2.7%) and wide-buffer remaining reserves (14-25%).
- **Structural.** Soothsayer's band avoids Kamino's block-state failure mode from PriceHeuristic, TWAP divergence, or staleness gates.
- **Empirical.** Kamino-xStocks is the xStock event panel: `kamino/liquidations/v1` has 102 events over 2025-08 to 2026-04, including a 2025-11 cluster. The earlier 30-day-zero finding was a sampling artifact.

Deployment framing is **two substrates, two questions**:

- MarginFi is the cleanest deployment-substrate argument for general lending because `assets use P-conf, liabilities use P+conf` maps directly to `(lower, upper)`.
- Kamino-xStocks is the xStock-specific empirical home. MarginFi has zero direct xStock Banks among 422 scanned Banks; xStock exposure there is indirect through Kamino-routed oracle setups and becomes cross-protocol propagation evidence when MarginFi liquidations land.

Current Paper 3 next work:

- Draft §1/§2/§3/§4/§6 around the three-claim structure.
- Analyze the 2025-11 Kamino liquidation cluster.
- Fit dynamic-bonus curve / `D_repaid` distribution from `kamino/liquidations/v1`.
- Extend protocol comparison to reserve-buffer truth, path-aware truth, and class-disaggregated results.

### Router / relay status

Router v0 is deployed on devnet and tested against a real Pyth Pull SOL/USD feed. Layer 0 includes Pyth aggregate, Switchboard On-Demand, Chainlink Streams Relay PDA read, and RedStone placeholder. Open-hours Layer 1 calibration is gated on ~3 months of upstream forward tape.

Relay fleet lock:

- Chainlink Streams needs a relay program + daemon.
- Pyth equities need only a poster daemon using Pyth's existing receiver; no new program.
- Production commitments: verifier-CPI or upstream signature verification, open-source daemons, v1 multi-writer migration, public cadence/uptime reporting, no-position policy with an auditable enforcement mechanism.

Calendar lock:

- Router embeds NYSE full-close and early-close table for 2024-2027 plus DST-safe UTC windows.
- Next refresh trigger: next ICE PR, ad-hoc SEC closure, or 2027 window approaching.
- CME calendar remains deferred until a CME-tracked asset is added to router config.

### Paper 4 / product-stack status

Paper 4 is the AMM arc: calibration-conditioned liquidity / auditable LVR-recovery lower bound for RWA AMM pools. It is post-grant, but its panel needs forward tapes now.

Scryer item 51 is already locked for Phase A capture:

- `jito_bundle_tape.v1`
- `validator_client.v1`
- `clmm_pool_state.v1`
- `dlmm_pool_state.v1`
- `dex_xstock_swaps.v1` promotion/backfill/forward-poll

Soothsayer-side future work after rows exist: pool-state reconstructor, path-aware truth labeller, bundle-attribution labels, counterfactual replay engine. See `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md`.

---

## 1. Recent decision log

### 2026-05-02 — Operational compaction of methodology context

**Trigger.** Agent startup context was dominated by historical methodology prose. The cost was operational: less context left for current work.

**Decision.** This file now keeps current state, recent locks, open gates, and evidence pointers. Older derivations are represented as concise entries and linked artefacts. Future entries should stay short unless the methodology itself changes and no better linked artefact exists.

**Impact.** Agents should read this file for current state and follow links only when working on that area. Do not expand this file back into a research transcript.

### 2026-05-01 — Paper 3 semantics, scryer reconciliation, and two-substrate framing

**Decision.** Paper 3 is Geometric / Structural / Empirical. Kamino-xStocks supplies the xStock empirical panel; MarginFi remains the cleaner general-lending deployment-substrate argument. The earlier "MarginFi-first" phrasing is superseded.

**Evidence.** `docs/protocol_semantics_kamino_xstocks.md`, `reports/paper3_liquidation_policy/protocol_semantics.md`, `reports/paper3_liquidation_policy/plan.md`, `docs/sources/lending/marginfi.md`, and scryer datasets `kamino/liquidations/v1`, `marginfi/reserves/v1`.

**Open work.** Analyze the Kamino 2025-11 cluster; land/consume `marginfi/liquidations/v1` as propagation evidence; update Paper 1 caveats for delegated oracle routing and Wayback halt sparsity.

### 2026-05-01 — Paper 4 Phase-A capture spec

**Decision.** Start clock-dependent scryer capture now for AMM/product-stack evidence: Jito bundle tape, validator-client labels, CLMM/DLMM pool state, and xStock swap backfill/forward poll.

**Evidence.** `reports/paper4_oracle_conditioned_amm/plan.md`, `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md`, `docs/product-stack.md`, and scryer wishlist item 51.

**Open work.** Scryer fetchers 51a-51e; operator triggers for 49a-49d; later Soothsayer consumers once parquet rows exist.

### 2026-04-29 — Scryer live-root and migration lock

**Decision.** Soothsayer reads the canonical live root from `SCRYER_DATASET_ROOT` (`/Users/adamnoonan/Library/Application Support/scryer/dataset` on this machine). The sibling `../scryer/dataset` checkout is offline replay only. Path names must match disk, not older nicknames (`yahoo/equities_daily`, not `yahoo/bars`).

**Impact.** Deleted Soothsayer fetchers stay deleted. If a script imports deleted source modules, migrate it to scryer parquet rather than restoring fetch code.

### 2026-04-29 — Router, relay fleet, product roadmap, and NYSE calendar locks

**Decisions.**

- v0/v1/v2 product progression locked: band primitive -> event stream -> decision SDK.
- Unified-feed router v0 locked around Layer 0 open-hours aggregation and closed-hours Soothsayer band receipts.
- Chainlink Streams uses a Soothsayer relay program; Pyth equities use a poster daemon into Pyth receiver; relay trust commitments locked.
- Router calendar uses an embedded 2024-2027 NYSE holiday/early-close table plus algorithmic DST.
- Mango v4 is methodology inspiration only, not a direct integration contribution.

**Evidence.** Router program code, `docs/ROADMAP.md`, `reports/methodology_history.md` git history before 2026-05-02 compaction, and scryer wishlist relay items.

**Open work.** Chainlink relay program/daemon, Pyth equity poster daemon, no-position attestation mechanism, open-hours upstream forward tape before Layer 1 calibration.

### 2026-04-28 — Depth-first methodology and reviewer diagnostics

**Decision.** Do not publish Paper 1 until the obvious reviewer-grade diagnostics and comparator caveats are addressed. The methodology is per-anchor calibrated, not a full-distribution model.

**Evidence.** `reports/v1b_diagnostics_extended.md`, `reports/v1b_window_sensitivity.md`, `reports/v1b_pooled_tail_trial.md`, `reports/v1b_evt_pot_trial.md`.

**Impact.** `τ=0.99` remains a disclosed ceiling; full PIT uniformity is a future diagnostic, not a current claim.

### 2026-04-27 — Data-fetching cutover

**Decision.** Scryer owns upstream fetching, retry, dedup, schemas, and raw parquet. Soothsayer owns analysis, serving, derived artefacts, and on-chain publish.

**Deleted from Soothsayer.** `crates/soothsayer-ingest/`, old source modules, `cache.py`, Chainlink scraper, and one-off fetch scripts.

**Impact.** New sources go into scryer first with a scryer methodology row and wishlist item.

### 2026-04-26 to 2026-04-24 — v1b serving methodology lock

**Decision.** Ship the simple auditable hybrid:

- F1 empirical-regime forecaster for normal/long-weekend.
- F0 stale-hold fallback for high-vol.
- Empirical calibration surface plus per-target buffers.
- Python produces artefacts; Rust serves them with byte-for-byte parity.

**Evidence.** `reports/v1b_decision.md`, `reports/v1b_calibration.md`, `reports/v1b_ablation.md`, `reports/phase1_week1.md`, `reports/phase1_week2.md`.

**Rejected or deferred.** Scalar buffer, unbuffered surface inversion, conformal alternatives for v1, EVT/GPD tail fixes, full HAR-RV refit as production dependency, and complex pre-v1 state-space/VECM/Hawkes stacks.

---

## 2. Open methodology questions

| ID | Question | Gate / trigger | Current disposition |
|---|---|---|---|
| O1 | Does on-chain xStock TWAP improve weekend calibration? | V5 tape reaches >=150 weekend obs per `(symbol, regime)` | V2.1 |
| O2 | Does conformal prediction beat per-target buffers on finer grids? | Multi-split walk-forward with finer claimed grid | V2 / reviewer request |
| O3 | Is there consumer-experienced coverage loss from MEV/order flow? | V5 tape + Jito bundle data >=3 months | V2.3 / Paper 4 input |
| O4 | Is calibration uniform over full PIT, not just anchors? | One-shot PIT diagnostic | V2.4; not a v1 claim |
| O5 | How should Layer 0 set `min_quorum`? | Design partner + >=3 months upstream forward tape | deferred |
| O6 | How does Layer 0 handle missing upstream feeds per asset? | First non-paper-1 asset in router config | deferred |
| O7 | Calendar fallback for non-NYSE/CME assets? | First JP/EU/FX asset | deferred |
| O8 | v1 event-stream wire format? | Paper 3 publication + v1 design lock | deferred |
| O9 | v2 multi-asset receipt semantics? | Paper 3 §10 + SDK design | deferred |
| O10 | Relay signing / multi-writer model? | First production relay deploy | v0 hot key; v1 multi-writer target |
| O11 | Relay verifier-CPI policy? | Mainnet relay deploy + CU measurement | always verify in production |
| O12 | No-position enforcement mechanism? | Before mainnet relay deploy | attestation-account default |
| O13 | Paper 3 path-aware truth and cost priors | Kamino cluster analysis + DEX/perp truth tapes | active |
| O14 | Paper 4 bound scope full-τ vs anchor-only | PIT diagnostic before Phase B | active |

---

## 3. Artefact map

- `README.md` — product overview and current public evidence snapshot.
- `docs/ROADMAP.md` — phase sequencing and active gates.
- `docs/scryer_consumer_guide.md` — sanctioned data read pattern.
- `docs/methodology_scope.md` — RWA class filter.
- `docs/v2.md` — future methodology upgrades.
- `reports/paper1_coverage_inversion/` — Paper 1 draft.
- `reports/paper3_liquidation_policy/` — Paper 3 plan and protocol semantics.
- `reports/paper4_oracle_conditioned_amm/` — Paper 4 plan and scryer pipeline ask.
- `reports/v1b_*.md` — frozen evidence snapshots for the v1b methodology.
- `src/soothsayer/oracle.py` and `crates/soothsayer-oracle/` — current serving implementation.
