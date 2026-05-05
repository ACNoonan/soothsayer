# STATUS — soothsayer

**As of 2026-05-04.** Single-page operational state for any agent (or human) picking up work in this repo. Read this first. Then read whichever pointer below matches your task. Anything in `reports/methodology_history.md` past §0 is *history* — useful when investigating *why*, not *what*.

> **Maintenance rule.** Update this file when any of {deployed methodology, served τ range, active workstream, headline metrics, deployment artefact path, wire format} changes. Changes that don't move any of those don't belong here. Long rationale belongs in `reports/methodology_history.md`; this file links to that, not the other way around.

---

## Today

**Deployed methodology:** M6 — Locally-Weighted Conformal (LWC) + per-symbol σ̂ EWMA HL=8 + Mondrian-by-`regime_pub` + δ-shifted c(τ) bump. Python serving path is live; Rust parity port is gated (Phase 7 below).

**Headline at τ=0.95** (OOS 2023+, 1,730 rows × 173 weekends × 10 tickers): realised **0.950**, half-width **370.6 bps**, Kupiec p=0.956, Christoffersen p=0.603, **per-symbol Kupiec 10/10**, LOSO realised-coverage std **0.0134** (5.7× tighter than M5). Coverage holds Kupiec at every served τ ∈ {0.68, 0.85, 0.95, 0.99}.

**Served τ range:** [0.68, 0.99]. Default deployment τ = 0.85. Paper 1 headline τ = 0.95.

**Wire format:** `PriceUpdate` Borsh layout preserved across v1 → M5 → M6. `forecaster_code = 2` = M5 Mondrian (legacy reference path). `forecaster_code = 3` = M6 LWC (reserved; activates when the Rust port lands).

**Deployment artefacts** (under `data/processed/`):

| File | Role |
|---|---|
| `lwc_artefact_v1.{parquet,json}` | M6 canonical — what's served today |
| `lwc_artefact_v1_frozen_20260504.{parquet,json}` | SHA-256-stamped freeze used by the forward-tape harness (sha 7b86d17a76912aa0…) |
| `mondrian_artefact_v2.{parquet,json}` | M5 reference baseline (Paper 1 §7 ablation comparator) |
| `forward_tape_v1.parquet` | Accumulated forward weekends past the freeze cutoff |
| `lwc_artefact_v1_archive_baseline_k26_*.{parquet,json}` | Archival K=26 σ̂ variant (pre-EWMA promotion) |

20 deployment scalars total: 12 trained per-regime quantiles + 4 OOS-fit `c(τ)` bumps + 4 walk-forward-fit `δ(τ)` shifts. All zero `δ` under M6 — per-symbol scale standardisation closed the cross-split calibration gap that made `δ` load-bearing under M5.

---

## Active workstreams (2026-05-04)

| Workstream | Driving doc | Status |
|---|---|---|
| **M6 Phase 7 — Rust parity port** | `reports/active/m6_refactor.md` | Gated; not yet started. Activates `forecaster_code = 3` on chain. |
| **Paper 1 revision against M6** | `reports/paper1_coverage_inversion/` | In flight. Per-symbol Kupiec 10/10 + LOSO 5.7× tighter + 4-DGP simulation are the new headline pieces. |
| **Paper 3 — Kamino 2025-11 cluster** | `reports/paper3_liquidation_policy/` | In flight. Three-claim structure (Geometric / Structural / Empirical). |
| **Paper 4 — forward data capture** | `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md` | Owned by scryer (item 51). Soothsayer consumers wait until parquet rows land. |
| **Devnet publish path** | `crates/soothsayer-publisher`, `programs/` | Router v0 deployed devnet 2026-04-29 at `AZE8HixpkLpqmuuZbCku5NbjWqoQLWhPRTHp8aMY9xNU`. |
| **Forward-tape harness** | `scripts/run_forward_tape_harness.sh` | Live on launchd, fires weekly Tuesday (`launchd/com.adamnoonan.soothsayer.forward-tape.plist`). |
| **Phase 7 paper-strengthening tests** | `reports/active/phase_7_results.md` | ✅ Complete 2026-05-04. Portfolio clustering, sub-period robustness, GARCH-t baseline. |
| **Phase 8 compounders** | `reports/active/phase_8.md` | ✅ Complete 2026-05-04. Worst-weekend characterisation, per-symbol GARCH-t, k_w threshold stability. |

Backlog of candidate workstreams sits in `reports/active/validation_backlog.md`. Treat that as scratch — anything that *sticks* gets folded into `reports/methodology_history.md`.

---

## "If you're working on X, read Y"

| Task | First file | Then |
|---|---|---|
| Understand current deployed methodology | `reports/methodology_history.md` §0 | latest dated entry under §1 |
| Paper 1 revision | `reports/paper1_coverage_inversion/{section}.md` | `reports/m6_validation.md` for the evidence pack |
| Paper 3 (liquidation policy) | `reports/paper3_liquidation_policy/plan.md` | `docs/protocol_semantics_kamino_xstocks.md` for the verified Kamino semantics |
| Paper 4 (oracle-conditioned AMM) | `reports/paper4_oracle_conditioned_amm/plan.md` | `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md` |
| M6 Phase 7 (Rust port) | `reports/active/m6_refactor.md` §7 | `crates/soothsayer-oracle/` (M5 path is the parity reference) |
| Forward-tape monitoring | `scripts/run_forward_tape_harness.sh` | `launchd/com.adamnoonan.soothsayer.forward-tape.plist` + `reports/m6_forward_tape_*.md` |
| Adding a new robustness test on M6 | `reports/active/phase_7_results.md` (template) | `src/soothsayer/backtest/calibration.py` dispatcher |
| Adding a new data source | `../scryer` wishlist (do not fetch from Soothsayer) | `docs/sources/_template.md`, then `docs/scryer_consumer_guide.md` |
| Devnet / on-chain publish | `crates/soothsayer-publisher/` | `programs/soothsayer-oracle-program/`, `programs/soothsayer-router-program/` |
| Kamino integration demo | `crates/soothsayer-demo-kamino/` | `reports/demo_kamino_comparison.md` |
| Reading parquet from scryer | `docs/scryer_consumer_guide.md` | `src/soothsayer/sources/scryer.py` helpers |
| Building / regenerating the M6 artefact | `scripts/build_lwc_artefact.py` | sidecar JSON schema documented in `reports/methodology_history.md` 2026-05-04 entry |

---

## Load-bearing today

- `data/processed/lwc_artefact_v1.{parquet,json}` is **what is served**. Don't break or rename without coordinating.
- The wire-format invariance guarantee (`PriceUpdate` Borsh layout) is the consumer contract. Any change to it is a breaking on-chain change and needs a migration plan.
- σ̂ rule = **EWMA HL=8** as of 2026-05-04 (promoted from K=26 trailing window). Column name `sigma_hat_sym_pre_fri` is preserved across the swap, so consumers don't need to know which σ̂ rule is live.
- Forward-tape harness on launchd validates the frozen freeze on each new closed weekend. If you change the freeze, update `scripts/freeze_lwc_artefact.py` and let the auto-discovery glob pick it up.
- **Hard rule:** all upstream data fetching goes through scryer. See `CLAUDE.md` rule #1.

---

## What is NOT current state

- **M5** (Mondrian-only, no per-symbol scale standardisation) is the *named reference baseline* for the §7 ablation. Code path stays alive (`Oracle.fair_value`, `forecaster_code = 2`). It is not what is served today.
- **v1 hybrid Oracle** (F1_emp_regime + per-target buffer schedule) was retired 2026-05-XX. Diagnostic scripts moved to `scripts/v1_archive/`.
- **24× `reports/v1b_*.md`** are frozen evidence snapshots tied to the M5 baseline. Read only when chasing a specific historical claim.
- **Dual-profile (M6a + M6b2) architecture** described in earlier revisions of `reports/active/m6_refactor.md` is paused. The current contents of that file are the LWC promotion plan that supersedes it.
- **AMM-track shipping (M6a)** is deferred indefinitely. Re-opens on either (a) a Sunday-Globex republish architecture (W8b, scryer-fetcher-gated) or (b) V3.1 F_tok tape accumulating ≥150 weekends (W8c, ETA Q3–Q4 2026).
- **Pre-M5 reports** (`v1_chainlink_bias.md`, `v3_bakeoff.md`, `v11_cadence_verification.md`, `phase1_week{1,2}.md`) are historical. See `reports/INDEX.md` for the current/historical classification.

---

## Hard rules summary (full list in `CLAUDE.md`)

1. No upstream data fetching in Soothsayer — read scryer parquet from `SCRYER_DATASET_ROOT`.
2. New data sources land in scryer first.
3. Analysis reads parquet, not raw API output.
4. Preserve `_schema_version`, `_fetched_at`, `_source`, `_dedup_key`.
5. Soothsayer-derived datasets use experiment-versioned venues (`soothsayer_v{N}`).
6. Don't restore deleted ingest code — migrate callers to scryer parquet.
