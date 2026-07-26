# STATUS — soothsayer

**As of 2026-07-26.** Single-page operational state for any agent (or human) picking up work in this repo. Read this first. Then read whichever pointer below matches your task. Anything in `reports/methodology_history.md` past §0 is *history* — useful when investigating *why*, not *what*.

> **Maintenance rule.** Update this file when any of {deployed methodology, served τ range, active workstream, headline metrics, deployment artefact path, wire format} changes. Changes that don't move any of those don't belong here. Long rationale belongs in `reports/methodology_history.md`; this file links to that, not the other way around.

---

## Picking back up (2026-07-26)

Two things are unblocked and worth doing first; everything else waits on operator runs.

1. **Email Marc Schmitt for the q-fin.RM endorsement.** He is the binding constraint on the whole Paper 1 track, moved rank 91 → 20 once the ranker saw his revised title, and we now cite him in §2.3. The ask is specific and true: his regime-path conditioning is a candidate replacement for the §4.3 exchangeability assumption we currently defend only with a permutation test. Hook (accurate, checked) in `arxiv-endorsement/outreach_hooks.json` under `marc schmitt`; prefer `marc.schmitt@cs.ox.ac.uk` over the scraped hotmail address.
2. **Disclose the earnings-cell truncation in the paper.** §6.8 reports `earnings_night` at n=60 without noting the cell is truncated by a 14-month upstream outage. The direction is safe — recovering the ~19 nights strengthens the partition claim — but publishing a silently-truncated regime undisclosed is the one thing this paper's framing cannot afford.

Blocked chain, in order, needs your operator runs: **EDGAR fetch → `earnings.v3` migration → panel rebuild → regenerate the overnight arms of W12/W15/W16/W17 once.** Do not regenerate before the rebuild; 19 nights against n=60 moves the earnings arm materially and you would pay for the run twice.

---

## Today

**Deployed methodology:** M6 — Locally-Weighted Conformal (LWC) + per-symbol σ̂ EWMA HL=8 + Mondrian-by-`regime_pub` + δ-shifted c(τ) bump. Python serving path is live; **Rust parity is complete (180/180 Python↔Rust cases across both M5 and M6 paths)**. The Anchor on-chain program serves the M5 reference path on devnet; M6 on-chain enablement is pending the next publisher release.

**Headline at τ=0.95** (OOS 2023+, 1,730 rows × 173 weekends × 10 tickers): realised **0.950**, half-width **370.6 bps**, Kupiec p=0.956, Christoffersen p=0.603, **per-symbol Kupiec 10/10**, held-out LOSO coverage **0.9497 ± 0.0128** (cross-symbol SD). Coverage holds Kupiec at every served τ ∈ {0.68, 0.85, 0.95, 0.99}.

**Served τ range:** [0.68, 0.99]. Default deployment τ = 0.85. Paper 1 headline τ = 0.95.

**Wire format:** `PriceUpdate` Borsh layout preserved across v1 → M5 → M6. `forecaster_code = 2` = M5 Mondrian (live on-chain, devnet). `forecaster_code = 3` = M6 LWC (live in the Rust serving stack at 180/180 parity; on-chain enablement gated on the next publisher release).

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

## Active workstreams (2026-07-26)

| Workstream | Driving doc | Status |
|---|---|---|
| **Paper 1 (coverage-inversion) → arXiv** | `research/coverage-inversion/README.md` then `rewrite/` | **67-page PDF**, 0 LaTeX errors, 0 unresolved citations (`build/build.py --v2 --pdf`). 2026-07-24/25: +13 citations from the related-work sweep; a falsifiable §2 claim corrected (ACon², USENIX Sec'23, joins conformal to an on-chain wire); §7 rewritten on measured evidence; **Appendix G** (one-sided lending instantiation); §3 states the two verification contracts; §5.2/§9 draw the weekend-vs-overnight sectional distinction. **Gate is the q-fin.RM endorsement**, not the draft. |
| **Rust parity** | `crates/soothsayer-oracle/tests/` | ✅ M5/M6 **now a committed regression harness** (`oracle_parity.rs`, 329 cases) — the old 180/180 was a one-off with nothing catching drift. Also pins Rust's *hardcoded* `config.rs` tables against the Python sidecar, which go silently stale on any artefact rebuild. ✅ Adaptive path ported + pinned byte-for-byte (`adaptive_parity.rs`). On-chain M6 enablement (`forecaster_code = 3`) still gated on the next publisher release. |
| **⛔ BLOCKED: earnings data repair** | `reports/active/earnings_flag_coverage_decay.md` | **Live defect.** Overnight panel has **zero `earnings_night` rows after 2025-05-28** — an earnings night served today gets a ~3% band where the calibrated band is ~25% (measured miscoverage without the cell: 0.333 vs a claimed 0.95). Yahoo's earnings upstream is **dead**, not stale (`earnings-backfill` is a no-op that reports success). Fix chain: **EDGAR fetch → `earnings.v3` migration → panel rebuild → regenerate overnight arms ONCE**. Schema drafted in scryer (`docs/schemas.md`, commit 9647379); migration not implemented. Needs operator runs. |
| **Characterised, NOT deployed** | `reports/active/w17_promotion_gate.md` | Six things cleared their gates this week and none is promoted. W17 recommends **weekend `W13+W14`, overnight `W15`** (they interfere — W15 undoes W14's τ=0.95 fix on weekends). Plus the one-sided lending profile (Appendix G) and the checkpointed-adaptive state. Promotion of W15 additionally needs the archive emitter wired into the weekly harness. See "What is NOT current state". |
| **Paper 3 — liquidation policy** | `research/liquidation-policy/` | In flight. Three-claim structure (Geometric / Structural / Empirical). |
| **Paper 4 — forward data capture** | `research/oracle-conditioned-amm/scryer_pipeline_plan.md` | Owned by scryer (item 51). Soothsayer consumers wait until parquet rows land. |
| **Devnet publish path** | `crates/soothsayer-publisher`, `programs/` | Router v0 deployed devnet 2026-04-29 at `AZE8HixpkLpqmuuZbCku5NbjWqoQLWhPRTHp8aMY9xNU`. Publish→read-back not yet wired end-to-end (`initialize` runner is a TODO; see `docs/devnet-quickstart.md`). |
| **Forward-tape harness** | `scripts/run_forward_tape_harness.sh` | Live on launchd, fires weekly Tuesday. **N=12 forward weekends**: pooled Kupiec passes all four anchors, per-symbol 10/10 at τ=0.95. |
| **AMM design-partner onboarding** | `docs/INTEGRATION.md` | Stubs scaffolded (integration guide + devnet quickstart + README section); content gated on the Paper 1 release. ROADMAP Phase 2. |
| **Verifier + band archive (paper→product)** | `reports/active/verifier_cli_scope.md` | v0.1 shipped 2026-07-21: public band archive `data/band_archive/bands_v1.csv` (480 rows / 12 weekends, claims-only, append-only) + `crates/soothsayer-verify` (`coverage` / `receipt` / `artefact`; stats parity-pinned vs scipy ≤1e-9). Harness emits archive weekly (step [6/6]). **Pre-open commitment shipped 2026-07-24**: Saturday width commitments (`commitments_v1.csv`) + Monday pre-open publication (`published_pre_open` provenance) via `scripts/emit_band_commitments.py` + two launchd plists (activation pending Adam); `soothsayer-verify commitment` audits the chain. Validated bit-exact vs the retro path on weekend 2026-07-17. Next: coverage dashboard, then LOI outreach pack. |
| **Repo public-share prep** | this file | ✅ Papers moved to `research/`; committed secrets removed; third-party papers + internal drafts untracked. |

Backlog of candidate workstreams sits in `reports/active/validation_backlog.md`. Treat that as scratch — anything that *sticks* gets folded into `reports/methodology_history.md`.

---

## "If you're working on X, read Y"

| Task | First file | Then |
|---|---|---|
| Understand current deployed methodology | `reports/methodology_history.md` §0 | latest dated entry under §1 |
| Paper 1 revision | `research/coverage-inversion/README.md` **first** — then `research/coverage-inversion/rewrite/{section}.md` (the live tree; `archive-v1/` is superseded and ships nothing) | `reports/m6_validation.md` for the evidence pack |
| Paper 3 (liquidation policy) | `research/liquidation-policy/plan.md` | `docs/protocol_semantics_kamino_xstocks.md` for the verified Kamino semantics |
| Paper 4 (oracle-conditioned AMM) | `research/oracle-conditioned-amm/plan.md` | `research/oracle-conditioned-amm/scryer_pipeline_plan.md` |
| M6 Phase 7 (Rust port) | `reports/active/m6_refactor.md` §7 | `crates/soothsayer-oracle/` (M5 path is the parity reference) |
| Forward-tape monitoring | `scripts/run_forward_tape_harness.sh` | `launchd/com.adamnoonan.soothsayer.forward-tape.plist` + `reports/m6_forward_tape_*.md` |
| Adding a new robustness test on M6 | `reports/active/phase_7_results.md` (template) | `src/soothsayer/backtest/calibration.py` dispatcher |
| One-sided / lending-track bands | `reports/active/w4_one_sided_bands.md` | `research/coverage-inversion/rewrite/16_appendix_G.md`, `Oracle.downside_bound_lwc` |
| Adaptive overnight state + checkpoints | `reports/active/adaptive_state_wire_design.md` | `src/soothsayer/adaptive_state.py`, `crates/soothsayer-oracle/src/adaptive.rs` |
| Regime-cell changes (W13/W14/W15/W16/W17) | `reports/active/w17_promotion_gate.md` | `w16_combined_cell_changes.md` for why they interfere |
| The earnings data defect | `reports/active/earnings_flag_coverage_decay.md` | scryer `docs/schemas.md` → `earnings.v3` |
| Related work / citations | `reports/active/related_work_sweep_202607.md` | `research/coverage-inversion/references.md` (the .bib is generated) |
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
- `data/band_archive/bands_v1.csv` is the **public, append-only** served-band record `soothsayer-verify` audits. Never edit or delete rows; a new freeze appends under its own sha. It is the one committed path under `data/`.
- `data/band_archive/bands_adaptive_v1.csv` is the **separate** append-only record for the adaptive overnight profile — deliberately not a column on `bands_v1.csv`, because `soothsayer-verify` parses that against a fixed schema and the two profiles verify differently (frozen row → one hash; adaptive row → artefact hash **and** checkpoint hash).
- **`prep_panel_for_forecaster` has a footgun.** On the overnight panel it MUST be called with `sigma_exclude_mask_col="earnings_next_week"`. Omit it and σ̂ is silently recomputed contaminated (+32% GOOGL, +23% NVDA), over-widening every ordinary night. Default is `None` so weekend behaviour is unchanged — which means an overnight caller that forgets fails silently, in the safe-looking direction.
- **`check_earnings_confirmation_health()`** (`backtest/panel.py`) is the guard for the 2026-07 earnings outage. It asserts on **confirmed-session fraction and lag**, not date recency — dates stayed current through the entire 14-month outage, so any date-based check stays green while the panel goes dark.
- **Hard rule:** all upstream data fetching goes through scryer. See `CLAUDE.md` rule #1. Scoped exception (2026-07-21): `crates/soothsayer-verify` fetches Yahoo directly — independent truth is the point of a verifier. Analysis code may not call into it.

---

## What is NOT current state

**Everything below cleared a gate and is deliberately unpromoted.** The deployed artefact, the frozen weekend freeze and its forward tape are untouched.

- **One-sided (downside) lending profile** — `Oracle.downside_bound_lwc()`, `lwc_onesided_artefact_v1.*`, Appendix G. Frees ~34% of the collateral buffer at the τ=0.85 default and is better calibrated overnight (symmetry fails Kupiec at 3 of 4 anchors there). Carries none of §6's held-out battery. `_deployed: false`, asserted by a test.
- **W13 triple_witching cell + W14 shrinkage (weekend)** — closes a live 0.869-vs-0.95 hole on quarterly expiry weekends and is 5.0% *tighter* at τ=0.95 with per-regime 4/4. Cleared W17 in the deployed configuration.
- **W15 checkpointed-adaptive level (overnight)** — repairs the earnings drift W14 diagnosed; needs `bands_adaptive_v1.csv` emitted from the weekly harness before promotion.
- **`earnings.v3`** — schema drafted in scryer; no migration, no builder, no helper.

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
