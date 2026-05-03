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

### Current methodology constants (v2 / M5)

- Architecture: Mondrian split-conformal by regime + factor-adjusted point + δ-shifted `c(τ)`.
- Default deployment target: `τ = 0.85`.
- Headline Paper 1 validation target: `τ = 0.95`.
- Served range: `τ ∈ [0.68, 0.99]`; M5 closes the v1 finite-sample tail ceiling at τ=0.99 at the cost of a 22% wider band.
- Forecaster: single `mondrian` lookup (wire `forecaster_code = 2`); no per-regime forecaster choice.
- `REGIME_QUANTILE_TABLE` (12 trained scalars, pre-2023 calibration set):
  - normal: `{0.68: 0.006070, 0.85: 0.011236, 0.95: 0.021530, 0.99: 0.049663}`
  - long_weekend: `{0.68: 0.006648, 0.85: 0.014248, 0.95: 0.031032, 0.99: 0.071228}`
  - high_vol: `{0.68: 0.011628, 0.85: 0.021460, 0.95: 0.042911, 0.99: 0.099418}`
- `C_BUMP_SCHEDULE` (4 OOS-fit scalars on the 2023+ slice): `{0.68: 1.498, 0.85: 1.455, 0.95: 1.300, 0.99: 1.076}`.
- `DELTA_SHIFT_SCHEDULE` (4 walk-forward-fit shifts): `{0.68: 0.05, 0.85: 0.02, 0.95: 0.00, 0.99: 0.00}`.
- Code truth: `src/soothsayer/oracle.py`, `crates/soothsayer-oracle/src/{config,oracle}.rs`, `data/processed/mondrian_artefact_v2.parquet` (per-Friday rows), and `data/processed/mondrian_artefact_v2.json` (audit-trail sidecar). v1 bounds parquet (`v1b_bounds.parquet`) and v1 oracle code path are deprecated; v1 diagnostic scripts archived under `scripts/v1_archive/`.

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

### 2026-05-XX — M5 / v2 deployment shipped; v1 hybrid Oracle retired

**Trigger.** Completion of `M5_REFACTOR.md` working doc following the 2026-05-02 M5 validation entry below. After re-evaluating the Colosseum constraint (the user is no longer firmly committed to a 2026-05-10 hackathon submission), the staged migration was collapsed: M5 deploys directly with no v1 transition window.

**Decision.** Deployed the v2 / M5 architecture (Mondrian split-conformal by regime + factor-adjusted point + δ-shifted `c(τ)`) end-to-end. v1 hybrid forecaster Oracle (F1_emp_regime + per-target additive buffer + per-regime forecaster choice) is retired; v1 calibration-surface API (`compute_calibration_surface`, `pooled_surface`, `invert`) deleted from `src/soothsayer/backtest/calibration.py`; v1 Oracle constructor signature replaced with single-arg artefact load; v1 diagnostic and validation scripts moved to `scripts/v1_archive/` (24 scripts) under a deprecation banner.

**Code changes.**

- Python serving: `src/soothsayer/oracle.py` rewritten (~210 lines) around `REGIME_QUANTILE_TABLE` + `C_BUMP_SCHEDULE` + `DELTA_SHIFT_SCHEDULE` module constants; `Oracle.fair_value` is now a 5-line lookup. `band_evaluator.py` unchanged (constructor signature compatible).
- Python build: new `scripts/build_mondrian_artefact.py` train-fits the 12 quantiles + 4 c(τ) scalars from the panel + writes `data/processed/mondrian_artefact_v2.parquet` (per-Friday rows) + `mondrian_artefact_v2.json` (audit-trail sidecar).
- Rust serving: `crates/soothsayer-oracle/src/{config,oracle,types}.rs` rewritten; `surface.rs` deleted. Single `Oracle::load(artefact_path)` entry point; output byte-identical to Python on 90/90 parity cases (`scripts/verify_rust_oracle.py`).
- Wire format: **byte-identical across the v1 → M5 migration.** `PriceUpdate` Borsh layout unchanged; `forecaster_code = 2` slot relabelled `FORECASTER_RESERVED_2 → FORECASTER_MONDRIAN` in `programs/soothsayer-oracle-program/src/state.rs` and `crates/soothsayer-consumer/src/lib.rs`. Existing v1 PriceUpdate accounts (codes 0/1) decode cleanly under M5 consumers.
- Publisher CLI: `--surface` and `--pooled` args dropped; default artefact path is `data/processed/mondrian_artefact_v2.parquet`. PrepPublish + payload encoder updated to emit `forecaster_code = 2` for `forecaster_used = "mondrian"`.

**Paper / docs cascade.**

- Paper 1 (`reports/paper1_coverage_inversion/`): §0 abstract rewritten; §1 introduction headline numbers updated (354 bps at τ=0.95, 0.990 realised at τ=0.99); §4 methodology rewritten around Mondrian; §5 split-section description updated; §6 results regenerated at M5 numbers (per-regime, pooled, walk-forward, density tests); §7 ablation re-framed (§7.1–§7.5 retained as v1-historical, §7.5 taxonomy updated to mark each component as inherited / cosmetic / removed under M5; §7.6 stress test retained; §7.7 Mondrian ablation retained as the architecture-justification ablation); §8 serving-layer prose updated (90/90 parity, wire-format invariance disclosure); §9 limitations updated (§9.1 tail ceiling closed, §9.4 OOS-tuning provenance restated for c(τ)+δ(τ), §9.5 Berkowitz / DQ disclosure restated, §9.6 hybrid policy retired, §9.7 90/90 parity); §10 future work re-sequenced as v3 items; §11 conclusion restated under M5; §2.3 + references.md updated with Mondrian split-conformal citations.
- Paper 3 (`reports/paper3_liquidation_policy/protocol_semantics.md`): worked example numerics regenerated for SPY 2026-04-24 at M5 widths; per-reserve flip-threshold table updated to per-regime widths.
- Paper 4 (`reports/paper4_oracle_conditioned_amm/`): `devnet_artefacts.json` updated with M5-derived SPY/QQQ bands and `forecaster_code = 2`; `colosseum_implementation_brief.md` narrative updated for M5 widths.
- Top-level docs: `README.md` evidence snapshot regenerated; `CLAUDE.md` Current State replaces v1 constants with M5; `docs/product-spec.md` hybrid-forecaster section replaced with M5 description; `docs/v1.5-deployment-spec.md` marked superseded; `reports/bear_case.md` gates 2.A and 3.E updated to "PARTIAL — v2 / M5 closes". Landing page (`landing/{index,dashboard}.html`) headline numbers and methodology blocks updated.

**Empirical headline (unchanged from 2026-05-02 validation).** OOS 2023+ slice (1,730 rows × 173 weekends): at τ=0.95, realised 0.950 with Kupiec p=0.956, Christoffersen p=0.912, mean half-width 354.5 bps — 20% narrower than the v1 Oracle's 443.5 bps at indistinguishable Kupiec calibration (block-bootstrap CIs exclude zero on width, straddle zero on coverage). At τ=0.99, M5 hits realised 0.990 with Kupiec p=0.942 (closes the v1 finite-sample tail ceiling at 0.972 at the cost of a 22% wider band). 6-split walk-forward passes Kupiec at every anchor (per-anchor p=0.43, 0.37, 0.36, 0.32). Berkowitz LR=173.1 and DQ at τ=0.95 (stat=32.1, p=5.7e-6) both reject — same per-anchor-only calibration profile as v1.

**Working doc deleted.** `M5_REFACTOR.md` removed from repo root; this methodology log entry is the deployment receipt.

**Open work — v3.** Full-distribution conformal upgrade to close the Berkowitz / DQ rejections (§10.1 V3.5); rolling artefact rebuild on a live deployment window (§10.1 V3.2); MEV-aware consumer-experienced coverage (§10.1 V3.3); intra-weekend forward-signal updating (§10.1 V3.4); F_tok forecaster gated on V5 tape accumulation (§10.1 V3.1).

### 2026-05-02 — M5 deployable Mondrian validated as v2 methodology candidate

**Trigger.** Reviewer-defensibility critique of the F1_emp_regime + per-target buffer schedule: §7.6 (constant-buffer baseline, 2026-05-02) showed the deployed Oracle is 11–12% wider than a coverage-matched constant buffer at every τ ≤ 0.95, with the entire pooled width premium concentrated in the high_vol regime. The natural follow-up question — "would Mondrian split-conformal by `regime_pub` give the same coverage at narrower width without the factor switchboard / log-log VIX / earnings / long-weekend forecaster machinery?" — was tested head-to-head against the deployed Oracle on the identical OOS 2023+ slice.

**Decision.** Validate but defer. M5 is the v2 methodology target; deployment migration is scheduled post-2026-05-10 (Colosseum hackathon delivers under current v1 Oracle to preserve hackathon timeline). This entry records the empirical case and the deferral reason, not a deployment switch. Working doc with task-level checklist: `M5_REFACTOR.md` (root), to be deleted on completion.

**Evidence.** Five comparison variants tested, all on the same OOS 2023+ panel (1,730 rows × 173 weekends) the §7.4 serving-layer matrix evaluates the deployed Oracle on. The deployable variant — M5: train-fit per-regime conformal quantile + factor-adjusted point + per-target c(τ) bump tuned on OOS, 12 trained scalars + 4 OOS scalars (matching the Oracle's BUFFER_BY_TARGET parameter budget) — under the 6-split expanding-window walk-forward + δ-shift schedule {0.68: 0.05, 0.85: 0.02, 0.95: 0.00, 0.99: 0.00}:

| τ | M5 test realised | M5 test hw (bps) | Oracle test hw (bps) | M5 width advantage |
|---:|---:|---:|---:|---|
| 0.68 | 0.672 (Kupiec p=0.43) | 124 | 186 | −33% |
| 0.85 | 0.832 (p=0.37) | 215 | 287 | −25% |
| 0.95 | 0.943 (p=0.36) | 357 | 526 | −32% |
| 0.99 | 0.991 (p=0.32) | 746 | 609 | +22% (M5 hits target where Oracle hits structural ceiling) |

Berkowitz (LR=173, ρ̂=0.31) and DQ at τ=0.95 (DQ=32) both reject for M5 — same per-anchor-only calibration profile as the deployed Oracle (per §6 abstract). M5 doesn't fix the density-test rejection; it doesn't make it worse either.

Tables: `reports/tables/v1b_constant_buffer_*.csv` (the §7.6 baseline that prompted this), `reports/tables/v1b_mondrian_calibration.csv`, `reports/tables/v1b_mondrian_oos.csv`, `reports/tables/v1b_mondrian_by_regime.csv`, `reports/tables/v1b_mondrian_bootstrap.csv`, `reports/tables/v1b_mondrian_walkforward*.csv`, `reports/tables/v1b_oracle_walkforward*.csv`, `reports/tables/v1b_mondrian_density_tests.csv`, `reports/tables/v1b_mondrian_delta_sweep.csv`. Scripts: `scripts/run_constant_buffer_baseline.py`, `scripts/run_mondrian_regime_baseline.py`, `scripts/run_mondrian_walkforward_pit.py`, `scripts/run_mondrian_delta_sweep.py`.

**Impact.** **No methodology-constants change in §0 of this file.** Current Oracle (v1: F1_emp_regime + hybrid + buffer schedule) remains deployed and remains the basis for Paper 1's headline numbers (τ=0.95: half-width 443 bps, realised 0.950, p_uc=1.000) and the Colosseum 2026-05-10 submission. M5 is staked as a v2 candidate: per-regime Mondrian conformal quantile + factor-adjusted point + δ-shifted c(τ) bump, ~20% narrower at matched OOS calibration, simpler implementation (~50 lines of serving code vs ~300), strict improvement at τ=0.99 (passes Kupiec where v1 hits the bounds-grid ceiling at 0.972). The diagnosis: the regime classifier `regime_pub` is the load-bearing piece of v1; the F1_emp_regime forecaster machinery on top of it (log-log VIX / per-symbol vol index / earnings flag / long-weekend flag) is over-engineering relative to a per-regime conformal quantile lookup.

**Open work.** Tracked in `M5_REFACTOR.md`. Phases: (1) no-regrets disclosure now (this entry + Paper 1 §7.7 + abstract footnote — the latter two deferred); (2) Colosseum delivery 2026-05-10 under v1; (3) post-Colosseum Python+Rust Oracle rewrite + parity test refresh; (4) Paper 1 v2 + Paper 3 numerical updates + devnet artefact regen. The wire format (`PriceUpdate` Borsh layout in `crates/soothsayer-consumer`) is preserved across the migration — only published *values* change. Paper 4 (Colosseum AMM) is methodology-agnostic in its consumer interface.

### 2026-05-02 — Paper 1 §7 forward-curve-implied baseline rung (F0_VIX)

**Trigger.** Reviewer-defensibility critique on Paper 1 §7 ablation: the ladder includes A0 (20-day realised Gaussian) and A1+ (factor-switchboard + empirical quantile) but no standalone forward-curve-implied Gaussian rung. The "use VIX × z_τ × √(2/252) × P" baseline is what every reviewer is likely to ask for as the natural alternative to F1's per-symbol vol machinery.

**Decision.** Land F0_VIX as a §7.1 rung between A0 and A1, plumb F0_VIX bounds into `v1b_bounds.parquet`, and serve B1 / B2 challenger cells in §7.4 (zero-buffer + deployed-buffer) on the OOS 2023+ slice. Equity-only — GLD/TLT use GVZ/MOVE in F1 and require per-class unit conversions for an analogous standalone baseline; that's a v2 candidate. Add a corresponding v2 architectural workstream (V2.4) for intra-weekend forward-signal updating from the Sunday 18:00 ET ES Globex reopen, distinct from the F\_tok V2.1 workstream. Add scryer wishlist item 52 for per-symbol implied vol from OPRA / Cboe.

**Evidence.** `reports/paper1_coverage_inversion/07_ablation.md` (rung, serving cells, taxonomy); `reports/tables/v1b_ablation.csv`, `reports/tables/v1b_serving_ablation.csv`, `reports/tables/v1b_serving_ablation_bootstrap.csv`. Headline: F0_VIX raw is 49.3% sharper than A0 on equity-matched rows (n=4,719) but undercovers by 7.86pp; through the deployed serving stack (B2: 0.020 buffer) it realises 0.876 against τ=0.95 (Kupiec rejects p≈0); the bootstrap delta against C4 is +6.7pp coverage [+4.3, +9.1] at +88% width. Mechanism: index-level VIX systematically misprices single-stock weekend tails, particularly for high-beta names (NVDA / TSLA / MSTR).

**Impact.** §7 is now closed against the canonical reviewer-asked baseline. The F0_VIX rung is disclosed-not-deployed; F1's per-symbol vol-indexing + log-log regression + empirical-quantile inversion is the load-bearing path from the natural baseline to a calibrated served band on freely-available data. No methodology-constants change.

**Open work.** Stage1 bootstrap CIs for the new (A0 → A0_VIX) and (A0_VIX → A1) ladder pairs are pending the next `run_stage1_stats.py` completion; matched-pair point estimates landed via the per-row ablation parquet. Per-symbol IV ingest (scryer item 52) gates a future F0_singleIV rung in v2.

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
