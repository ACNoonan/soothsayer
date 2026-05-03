# M6 Dual-Profile Rollout — Working Document

**Status:** Phase A (Lending-track / M6b2) ready to start. Phase B (AMM-track / M6a) gated on the r̄_w forward-predictor prototype (`VALIDATION_BACKLOG.md` W8).

**Delete this file when:** both profiles are deployed, methodology log entries committed, Paper 1 §10 + product-stack docs updated, and this checklist's items are all closed.

**Sequence relative to prior work:** picks up after `M5_REFACTOR.md` (deleted on completion 2026-05-XX, see `reports/methodology_history.md` deployment receipt). M5 is the deployed single-profile baseline; M6 is the planned post-M5 expansion to two parallel profiles.

**Source of truth for the architecture:** `docs/product-stack.md` (dual-profile section + per-layer track assignment).

**Source of truth for the empirical case:** `reports/v1b_m6a_common_mode_partial_out.md`, `reports/v1b_m6b_per_symbol_class_mondrian.md`, `reports/v1b_m6c_combined.md`. Headline at τ=0.95 on the OOS 2023+ panel:

| | half-width (bps) | vs M5 | vs v1 |
|---|---:|---:|---:|
| v1 (deployed pre-M5) | 443 | — | — |
| M5 (deployed) | 355 | — | −20% |
| M6b2 (Lending-track candidate) | 304 | −14% | −31% |
| M6a (AMM-track candidate, upper bound) | 309 | −13% | −30% |
| M6c (M6b2 + M6a, ceiling) | 271 | −24% | −39% |

All variants pass Kupiec at every anchor τ ∈ {0.68, 0.85, 0.95, 0.99}. M6a's number is an upper bound that uses Monday-derived r̄_w; deployable M6a depends on a Friday-observable forward predictor.

---

## Why two profiles instead of one

Different consumers want different properties of the band. M6a tightens the band universe-wide when common-mode is benign (Band-AMM's LVR-aware claim); M6b2 re-allocates width per asset class (lending's per-reserve buffer config). The full per-layer assignment is in `docs/product-stack.md`. The architectural commitment recorded here:

- One methodology family (factor-adjusted point + Mondrian split-conformal + δ-shifted c(τ) bump).
- Two profiles published in parallel: `profile_code = 1` Lending (M6b2), `profile_code = 2` AMM (M6a-deployable).
- Same `PriceUpdate` Borsh wire format on both. Single byte (`profile_code`) distinguishes the receipt; everything else byte-identical.
- Two parquet venues: `soothsayer_v6_lending/tape/v1`, `soothsayer_v6_amm/tape/v1`. (Working venue names; final naming pending scryer-convention resolution.)

---

## Phase A — Lending-track (M6b2) shipping

Goal: deploy M6b2 per-class Mondrian as the Lending-track band publish. Same wire format as M5; new conformal cell partition. Direct Kamino integration win + Paper 3 numerical update.

**Validation gates already passed (do not redo).**

- [x] M6b validation runner (`scripts/run_m6b_per_symbol_class_mondrian.py`); evidence `reports/v1b_m6b_per_symbol_class_mondrian.md`, tables `reports/tables/v1b_m6b_per_symbol_class_oos.csv`, `reports/tables/v1b_m6b_per_cell_quantiles.csv`. M6b2 chosen over M6b1 / M6b3: see `VALIDATION_BACKLOG.md` W2-followup decision rationale.

### A1 — Artefact build

- [ ] New `scripts/build_m6b2_lending_artefact.py`. Reads `data/processed/v1b_panel.parquet`, fits per-(symbol_class, target) trained b's on the pre-2023 calibration set, fits per-target c(τ) bump on OOS, applies the same δ-shift schedule slot as M5 (`{0.68: 0.05, 0.85: 0.02, 0.95: 0.00, 0.99: 0.00}`). Writes `data/processed/m6b2_lending_artefact_v1.parquet` (per-(symbol_class, fri_ts) rows) + `m6b2_lending_artefact_v1.json` (audit-trail sidecar with the 24 train-fit b's, 4 c(τ) scalars, 4 δ shifts, plus the symbol_class mapping and sample-size-per-cell counts).
- [ ] Symbol-class mapping locked (matches `scripts/run_m6b_per_symbol_class_mondrian.py` SYMBOL_CLASS): `equity_index = {SPY, QQQ}`, `equity_meta = {AAPL, GOOGL}`, `equity_highbeta = {NVDA, TSLA, MSTR}`, `equity_recent = {HOOD}`, `gold = {GLD}`, `bond = {TLT}`. New symbols join the closest class on first publication; documented in the artefact JSON.
- [ ] Verification: artefact reproduces the headline numbers in `reports/v1b_m6b_per_symbol_class_mondrian.md` to within 1 bp at every τ.

### A2 — Python serving path

- [ ] `src/soothsayer/oracle.py`: extend `Oracle` with a `profile: Profile` parameter (`Profile = Literal["lending", "amm"]`). Profile selection routes to per-class lookup table for `lending` vs current per-regime table for `amm` (M5-equivalent under the AMM profile until Phase B replaces it). Default profile = `"lending"` (the deployable v3 winner).
- [ ] `src/soothsayer/oracle.py`: add `LENDING_QUANTILE_TABLE` (24 trained scalars), `LENDING_C_BUMP_SCHEDULE` (4 OOS-fit), `LENDING_DELTA_SHIFT_SCHEDULE` (= existing schedule). Constants loaded from the artefact JSON sidecar at module import; runtime serve is the same 5-line lookup.
- [ ] `src/soothsayer/universe.py`: ensure xStock-to-symbol-class mapping is derived from the artefact JSON (single source of truth), not hardcoded.
- [ ] Smoke test: `scripts/smoke_oracle.py` runs both profiles on the Sample Friday and prints both bands; visual diff matches `reports/v1b_m6b_per_symbol_class_mondrian.md` per-class table.

### A3 — Rust serving path

- [ ] `crates/soothsayer-oracle/src/config.rs`: add `LendingQuantileTable` and `LendingCBumpSchedule` constants (mirrors Python).
- [ ] `crates/soothsayer-oracle/src/oracle.rs`: extend `Oracle::load(...)` with a profile parameter; same artefact-load pattern as M5. Output byte-identical to Python on the regenerated parity corpus.
- [ ] `crates/soothsayer-oracle/src/types.rs`: add `Profile` enum with `Lending = 1`, `Amm = 2` Borsh-coded; expose on `PricePoint`.
- [ ] Parity refresh: regenerate `scripts/verify_rust_oracle.py` corpus for both profiles. Target: 90/90 per profile.

### A4 — Wire format

- [ ] `programs/soothsayer-oracle-program/src/state.rs`: add `profile_code: u8` to `PriceUpdate`. Reuse a currently-reserved byte slot — verify via Borsh-layout regression test that the existing `forecaster_code = 2` Mondrian receipt round-trips byte-identically when `profile_code = 1` (back-compat for any in-flight v0 mainnet receipts).
- [ ] `crates/soothsayer-consumer/src/lib.rs`: decode the new `profile_code`; expose `Profile` enum to consumers; document the consumer's responsibility to assert the profile matches their integration spec.
- [ ] `crates/soothsayer-publisher/src/main.rs`: support `--profile {lending,amm}` flag; default to `lending`; supports parallel-stream operation (two daemons publishing different profile_codes from the same hot key).
- [ ] On-chain decode test: existing devnet `PriceUpdate` accounts decode under the new consumer with `profile_code = 0` (legacy) handled cleanly as "M5 single-profile receipt"; new accounts with `profile_code = 1` decode cleanly under both old (ignore byte) and new consumers.

### A5 — Scryer venue + publish path

- [ ] Stage parquet receipt output venue: `soothsayer_v6_lending/tape/v1` (working name; align with scryer convention before final cutover). Add a corresponding scryer methodology row + wishlist item (per CLAUDE.md hard rule #2).
- [ ] Publisher daemon: lending-profile cron at the same cadence as the M5 daemon; same operator key; parallel transactions.
- [ ] Devnet smoke deploy: publish lending-profile band for SPYx as a single-symbol test; verify Band-AMM router reads the new profile_code without error.

### A6 — Paper / docs cascade

- [ ] `reports/methodology_history.md`: append shipping-receipt entry. Update §0 to reflect dual-profile state ("Default deployment target … Lending-track for per-asset products, AMM-track for universe-aggregate products" once both ship; for now record Lending shipping).
- [ ] `reports/paper3_liquidation_policy/protocol_semantics.md`: regenerate worked-example numerics under M6b2 widths. Update the per-reserve flip-threshold table.
- [ ] `reports/paper3_liquidation_policy/plan.md`: update §13 success criteria with M6b2 widths if cited.
- [ ] `reports/paper1_coverage_inversion/10_future_work.md`: add V3.4 entry "M6b2 per-class Mondrian shipped under Lending-track" pointing to the methodology log entry.
- [ ] `docs/product-stack.md`: change M6b2 row in the Lending-track table from "shipping next" to "shipping" with the deployment date.
- [ ] `docs/product-spec.md`: add a "Profile selection" subsection describing `lending` vs `amm` and the consumer-side guarantee on `profile_code`.
- [ ] `CLAUDE.md` Current State: replace the M5 single-profile constants block with the dual-profile structure (Lending shipped, AMM gated on W8).
- [ ] `README.md`: replace the M5 evidence-snapshot row with a Lending-track row at τ=0.95: 304 bps, realised 0.950, p_uc ≥ 0.05 on OOS 2023+.

### A7 — Auxiliary one-sided lending-consumer table (W4 result)

W4 completed 2026-05-03 (`reports/v1b_w4_asymmetric_coverage_lending.md`). Two-sided asymmetric pair was **rejected** (pooled width-delta +2% vs symmetric at τ=0.95; only 2/21 cells materially asymmetric). One-sided per-class quantile table was **adopted as auxiliary** — it delivers 14–39% narrower buffers at matched one-sided coverage for lending consumers (MarginFi-style asset/liability Banks, band-perp long/short liquidation buffers, single-underlier options).

Implementation is artefact + consumer-SDK only — no wire-format change, no on-chain program changes:

- [ ] Extend `scripts/build_m6b2_lending_artefact.py` to emit `LENDING_QUANTILE_ONE_SIDED_LOW` and `LENDING_QUANTILE_ONE_SIDED_HIGH` keyed by `(symbol_class, tau_one)`. Anchors: τ_one ∈ {0.95, 0.99}. 6 classes × 2 anchors × 2 sides = 24 additional scalars. `equity_recent` (HOOD) gates τ=0.95 only per the n_train < MIN_N_FOR_TAU_99 cell-size rule (matches `scripts/run_asymmetric_coverage.py`).
- [ ] Source numerics: read directly from `reports/tables/v1b_w4_asymmetric_one_sided.csv` (already validated; or re-fit at artefact-build time using identical logic — pick whichever the other agent prefers for code locality).
- [ ] `crates/soothsayer-consumer/src/lib.rs`: add `one_sided_quantile(symbol_class, tau, side) -> bps` accessor reading from the artefact JSON sidecar's auxiliary table on construction. Document as: "for lending-style consumers that target one-sided coverage; default consumers continue to use `lower` / `upper` at the symmetric two-sided coverage level."
- [ ] `docs/scryer_consumer_guide.md` (or equivalent): add a short "One-sided lending-consumer quantiles" subsection pointing at the auxiliary table and the SDK accessor.
- [ ] Wire format: **NO CHANGE.** Published `lower` / `upper` continue to be `point ± b_sym(class, τ)·fri_close` per Phase A4.
- [ ] Effort: ~half-day on the artefact builder, ~hour on the consumer SDK + doc.

**Skipped (struck from the original A7 scope):**

- ~~Two-sided asymmetric `LENDING_QUANTILE_LOW` / `LENDING_QUANTILE_HIGH` pair replacing the symmetric `LENDING_QUANTILE_TABLE`.~~ Q1 of W4 rejected this — width-neutral at matched two-sided τ.
- ~~Wire-format change to write `lower = point − q_low·fri_close` and `upper = point + q_high·fri_close`.~~ Same reason; symmetric stays canonical on the wire.

### A8 — Validation gate before shipping

- [ ] Lending-track Berkowitz + DQ on OOS 2023+: same per-anchor profile as M5 (rejects pooled by ~the same magnitude); per-class Berkowitz no longer rejects on the SPY/QQQ/TLT/GLD partitions that under-disperse under M5 (this was the W2 finding that motivated M6b2).
- [ ] Walk-forward: 6-split coverage at every τ within ±0.005 of nominal.
- [ ] Block-bootstrap CI on Δhalfwidth M5 → M6b2: excludes zero on width, straddles zero on coverage.
- [ ] Production readiness: parity 90/90, devnet decode test green, consumer SDK doc updated, scryer venue staged.

---

## Phase B — AMM-track (M6a-deployable) shipping

**Status (2026-05-03): DEFERRED at Friday-close-only feature set.** W8 prototype completed 2026-05-03; Friday-observable predictor of r̄_w achieves R²(OOS) ≈ 0.005 (autoregressive baseline) to negative (vol/calendar feature variants overfit); cross-sectional ρ partial-out is a no-op (0.4147 → 0.4134). See `reports/v1b_r_bar_forward_predictor.md` and the W8 entry in `VALIDATION_BACKLOG.md` for the full result.

Phase B is **not abandoned**, just gated differently. Two reopened paths, neither blocked on the other:

- **Phase B (Sunday-Globex republish).** Tracked as `VALIDATION_BACKLOG.md` W8b. Architecture: ES/NQ Sunday 18:00 ET reopen → re-publish AMM-track band Sunday evening with the partialled-out r̄_w_hat substituted in. Engineering-gated: scryer needs a Sunday-evening futures snapshot fetcher; Soothsayer publisher needs a second cron at Globex reopen. ~3–4 weeks of total work once scryer item lands. Consumer-facing distinction: AMM-track has a Friday-close + Sunday-republish cadence; Lending-track stays Friday-close-only.
- **Phase B (V3.1 F_tok deployment).** Tracked as `VALIDATION_BACKLOG.md` W8c. The on-chain xStock cross-section on `soothsayer_v5/tape` is a near-perfect proxy for r̄_w by construction. Data-gated: ≥ 150 weekends of post-launch xStock history needed; ETA Q3–Q4 2026. No engineering work until the data accumulates.

The phases below are kept in the document as a reference for what shipping AMM-track will look like when one of the two paths fires; the checkbox states are reset to `[ ]` and re-gated on whichever predictor variant clears the R²(forward) ≥ 0.4 bar first.

**Pre-gate dependencies (re-stated post-W8).**

- [ ] **Either** Path 1 (W8b Sunday-Globex variant) clears R²(OOS) ≥ 0.40 on the same train/OOS split, **or** Path 2 (W8c V3.1 F_tok variant) clears the same bar once V5 tape accumulates. Below the bar on both paths, Phase B remains deferred and the M6c "ceiling" of 271 bps at τ=0.95 stays a documented future state, not a deployment target.

### B1 — Artefact build

- [ ] New `scripts/build_m6a_amm_artefact.py`. Reads the panel + the Friday-observable predictor's outputs; fits β̂ on TRAIN; computes residualised score; fits per-regime conformal quantile + per-target c(τ) bump on OOS. Writes `data/processed/m6a_amm_artefact_v1.parquet` + JSON sidecar (β̂, 12 train-fit b's, 4 c(τ) scalars, predictor coefficients).

### B2 — Python serving path

- [ ] `src/soothsayer/oracle.py`: AMM profile path. Per-row inputs include the forward-predicted r̄_w_hat at serve time; oracle subtracts β̂·r̄_w_hat from the score before quantile lookup.
- [ ] Predictor wiring: at serve time the oracle reads predictor inputs from a small `data/processed/forward_state_v1.parquet` (Friday-evening snapshot) — produced by a separate cron daemon that consumes the predictor inputs (futures, vol indices, etc.).

### B3 — Rust serving path

- [ ] `crates/soothsayer-oracle/src/oracle.rs`: AMM profile path mirrors Python. r̄_w_hat is part of the serve input alongside (symbol, fri_ts).
- [ ] Parity: 90/90 on the AMM-profile parity corpus.

### B4 — Wire format

- [ ] No change. `profile_code = 2` already reserved for AMM. The β̂·r̄_w_hat correction is internal to the oracle's computation; consumers see only the resulting `lower / upper / point`.

### B5 — Scryer venue + publish path

- [ ] Venue: `soothsayer_v6_amm/tape/v1`.
- [ ] Publisher daemon: AMM-profile cron, parallel to Lending. Same operator key; same cadence; reads forward_state at publish time.
- [ ] Devnet smoke deploy: publish AMM-profile band for SPY (underlier) as a single-symbol test; verify Band-AMM consumer (Layer 1) reads the new profile correctly.

### B6 — Paper / docs cascade

- [ ] `reports/methodology_history.md`: AMM-track shipping receipt entry. §0 updates to dual-profile final state.
- [ ] `reports/paper4_oracle_conditioned_amm/`: refresh devnet artefacts under AMM-track widths. Add a §x.x section on calibration-conditioned LP-region sizing under the M6a-deployable band.
- [ ] `reports/paper1_coverage_inversion/10_future_work.md`: V3.5 entry "AMM-track shipped" with the realised forward-predictor R² and width gain.
- [ ] `docs/product-stack.md`: Lending and AMM rows both move to "shipping"; pricing-tier note for Layer 4 licensing becomes operational.

### B7 — Validation gate before shipping

- [ ] AMM-track Berkowitz: cross-sectional ρ on PITs drops materially toward zero (the W2 finding said upper-bound partial-out brings it from 0.41 to 0.07; deployable will be intermediate).
- [ ] Walk-forward: 6-split coverage at every τ within ±0.005.
- [ ] Block-bootstrap CI on Δhalfwidth M5 → AMM-track: excludes zero on width if the predictor is good enough; if the gain is small, evaluate the deployment cost vs benefit.
- [ ] Production readiness: parity 90/90, devnet test green for Band-AMM consumer, predictor daemon operationally stable for ≥ 4 weeks.

---

## Cleanup

- [ ] `git grep "M5_REFACTOR\|profile_code = 0"` returns zero hits in active code (only archived references and old PriceUpdate accounts allowed).
- [ ] Final 2026-MM-DD entry in `reports/methodology_history.md`: "Dual-profile family deployed; Lending-track and AMM-track both live; M6_REFACTOR working doc deleted."
- [ ] **Delete this file (`M6_REFACTOR.md`).**
