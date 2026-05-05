# reports/ — Index

Classification of every file under `reports/`. **Read this before picking a `v1b_*.md` or other dated report** — most are historical evidence snapshots tied to a methodology (M5) that is no longer deployed.

For the current deployed state, read [`STATUS.md`](../STATUS.md) (root). For the dated decision log, read [`methodology_history.md`](methodology_history.md).

## Conventions

- **current** — describes what is deployed or what an in-flight workstream is working on. Read these freely.
- **paper-evidence** — frozen evidence pack for a paper section. Read when revising or citing that section.
- **historical** — evidence snapshot tied to a superseded methodology. Read only when investigating *why* something is the way it is, not *what* is true today.
- **operational** — recurring monitoring output. Read when on-call or auditing live coverage.

---

## Current

| File | Role |
|---|---|
| [`methodology_history.md`](methodology_history.md) | Append-only dated decision log. §0 = current state, §1 = chronological entries, §2 = open questions, §3 = artefact map. Source of truth for *why* the deployed methodology looks the way it does. |
| [`m6_validation.md`](m6_validation.md) | Full M6 LWC robustness battery — per-symbol Kupiec, LOSO, GARCH baselines, Phase 7/8 evidence. Companion to Paper 1 §6 / §7 revision. |
| [`m6_sigma_ewma.md`](m6_sigma_ewma.md) | Phase 5 evidence for the σ̂ K=26 → EWMA HL=8 promotion (current canonical σ̂ rule). |
| [`m6_simulation_study.md`](m6_simulation_study.md) | 4-DGP Monte Carlo + Phase 6 sample-size sweep (newly-listed-symbol admission threshold). |
| [`active/`](active/) | In-flight working docs (M6 refactor plan, Phase 7/8 results, validation backlog). See [`active/INDEX.md`](active/INDEX.md). |

## Operational (recurring monitoring)

| File | Role |
|---|---|
| [`m6_forward_tape_0weekends.md`](m6_forward_tape_0weekends.md), [`m6_forward_tape_1weekends.md`](m6_forward_tape_1weekends.md), [`m6_forward_tape_1weekends_variants.md`](m6_forward_tape_1weekends_variants.md) | Forward-tape harness output (auto-rolling N-weekends report; regenerated weekly Tuesday by `launchd/com.adamnoonan.soothsayer.forward-tape.plist`). |
| [`kamino_xstocks_weekend_20260417.md`](kamino_xstocks_weekend_20260417.md), [`20260424.md`](kamino_xstocks_weekend_20260424.md), [`20260501.md`](kamino_xstocks_weekend_20260501.md) | Per-weekend Kamino-xStocks oracle comparison snapshots. |
| [`backed_corp_actions_enriched.md`](backed_corp_actions_enriched.md), [`backed_corp_actions_summary.md`](backed_corp_actions_summary.md) | Backed corporate-action audit snapshots. |
| [`kamino_liquidations_first_scan.md`](kamino_liquidations_first_scan.md) | First-scan write-up of the `kamino/liquidations/v1` panel (102 events, 2025-08 → 2026-04). Paper 3 evidence. |

## Paper drafts

| Subdirectory | Paper |
|---|---|
| [`paper1_coverage_inversion/`](paper1_coverage_inversion/) | Paper 1 — calibration-transparent oracle. **In revision against M6.** |
| [`paper3_liquidation_policy/`](paper3_liquidation_policy/) | Paper 3 — liquidation policy under calibrated uncertainty. Three-claim structure (Geometric / Structural / Empirical). |
| [`paper4_oracle_conditioned_amm/`](paper4_oracle_conditioned_amm/) | Paper 4 — oracle-conditioned AMM. Forward data capture in flight (scryer item 51); Soothsayer consumers pending parquet rows. |

## Paper-evidence (frozen)

These are evidence snapshots cited by paper sections. Don't edit unless the paper section's claim changes.

| File | Cited from |
|---|---|
| [`v1b_paper1_robustness.md`](v1b_paper1_robustness.md) | Paper 1 §6.4.1, §6.3, §9.3, §9.4 (per-symbol bimodality, split-date sensitivity, LOSO, per-class) |
| [`v1b_calibration.md`](v1b_calibration.md), [`v1b_ablation.md`](v1b_ablation.md), [`v1b_buffer_tune.md`](v1b_buffer_tune.md), [`v1b_decision.md`](v1b_decision.md) | Paper 1 §4 / §5 (M5 reference baseline lineage) |
| [`v1b_walkforward.md`](v1b_walkforward.md), [`v1b_window_sensitivity.md`](v1b_window_sensitivity.md), [`v1b_leave_one_out.md`](v1b_leave_one_out.md) | Paper 1 §6.3 (walk-forward + window sensitivity + LOSO) |
| [`v1b_diagnostics.md`](v1b_diagnostics.md), [`v1b_diagnostics_extended.md`](v1b_diagnostics_extended.md), [`v1b_density_rejection_localization.md`](v1b_density_rejection_localization.md) | Paper 1 §6.4 / §9 (density tests, Berkowitz / DQ disclosure, W2 lead-finding) |
| [`v1b_path_coverage.md`](v1b_path_coverage.md), [`v1b_path_coverage_robustness.md`](v1b_path_coverage_robustness.md) | Paper 1 §6.6 / §10.1 (path-fitted conformity) |
| [`v1b_pyth_comparison.md`](v1b_pyth_comparison.md), [`v1b_chainlink_comparison.md`](v1b_chainlink_comparison.md), [`v1b_redstone_comparison.md`](v1b_redstone_comparison.md), [`v1b_kamino_scope_comparison.md`](v1b_kamino_scope_comparison.md), [`v1b_incumbent_oracle_comparison.md`](v1b_incumbent_oracle_comparison.md) | Paper 1 §6.5 / §6.6 + Paper 3 §Structural (incumbent oracle benchmarks) |
| [`v1b_forward_coverage.md`](v1b_forward_coverage.md) | W5 (live forward-tape coverage; recurring) |
| [`v1b_w4_asymmetric_coverage_lending.md`](v1b_w4_asymmetric_coverage_lending.md) | Paper 3 §Structural (one-sided lending-consumer table) |
| [`v1b_m6a_common_mode_partial_out.md`](v1b_m6a_common_mode_partial_out.md), [`v1b_m6b_per_symbol_class_mondrian.md`](v1b_m6b_per_symbol_class_mondrian.md), [`v1b_m6c_combined.md`](v1b_m6c_combined.md), [`v1b_r_bar_forward_predictor.md`](v1b_r_bar_forward_predictor.md) | Methodology log (W2-followup, W8 — dual-profile architecture and AMM-track gating). M6a/c are the "documented upper bound, not deployed" leads. |
| [`v3_bakeoff.md`](v3_bakeoff.md) | Methodology log 2026-05-03 (lead-up to the M6 LWC promotion) |
| [`bear_case.md`](bear_case.md) | Strategic gate log; updated when validation gates flip |
| [`demo_kamino_comparison.md`](demo_kamino_comparison.md) | Crate `crates/soothsayer-demo-kamino` evidence |

## Historical (do not consult for current state)

These predate M5 / M6 or were trial methodologies that did not progress. Read only when investigating a specific historical claim.

| File | Note |
|---|---|
| [`v1_chainlink_bias.md`](v1_chainlink_bias.md) | v1-era Chainlink weekend-bias post-mortem |
| [`v11_cadence_verification.md`](v11_cadence_verification.md) | Chainlink v11 24/5 cadence verification (subsumed by current `docs/sources/oracles/chainlink_v11.md`) |
| [`v1b_extended_grid.md`](v1b_extended_grid.md), [`v1b_macro_regressor.md`](v1b_macro_regressor.md), [`v1b_pooled_tail_trial.md`](v1b_pooled_tail_trial.md), [`v1b_evt_pot_trial.md`](v1b_evt_pot_trial.md), [`v1b_conformal_comparison.md`](v1b_conformal_comparison.md), [`v1b_hybrid_validation.md`](v1b_hybrid_validation.md) | Trial methodologies; not adopted into M5/M6 |
| [`phase1_week1.md`](phase1_week1.md), [`phase1_week2.md`](phase1_week2.md) | Phase-1 weekly scoping (pre-M5) |

## Subdirectories

| Path | Contents |
|---|---|
| [`active/`](active/) | In-flight working docs. See [`active/INDEX.md`](active/INDEX.md). |
| [`archived/`](archived/) | Explicit archive (vault updates, retired v2/v3 trial notes). |
| [`figures/`](figures/) | Persisted plots cited by paper drafts and methodology entries. |
| [`tables/`](tables/) | CSV snapshots for every numerical claim in the reports above. |
