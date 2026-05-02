# Soothsayer — Roadmap

**Last compacted:** 2026-05-02
**Purpose:** phase sequencer and active gate list. Detailed rationale lives in `reports/methodology_history.md` and the linked paper plans.

## TL;DR

Phase 0 validation is done. Phase 1 is active: finish Paper 1, draft Paper 3 on the sharpened three-claim structure, keep devnet/publish-path work moving, and make sure time-sensitive scryer forward tapes start now.

Mainnet and B2B work remain gated on Paper 3 evidence, devnet stability, and at least one serious design-partner signal.

## Active Gates

### Paper 1 before arXiv

- Keep comparator wording clean: flat `±300bps` is a stylized baseline, not the literal Kamino incumbent.
- Refresh Chainlink v10/v11 and 24/5 cadence framing from current decoder/scryer evidence.
- Keep scope explicit: Paper 1 validates the oracle calibration primitive, not welfare-optimal policy.
- Back live-xStock claims with tape or mark them as future work.
- Add current caveats where relevant: Wayback halt sparsity, delegated oracle routing, and any daily-factor approximation that should be rerun with `cme/intraday_1m`.

### Paper 3 before publication-quality claims

- **Closed:** Kamino-xStocks action semantics verified end-to-end in `docs/protocol_semantics_kamino_xstocks.md`.
- **Closed:** reserve-buffer geometry in `reports/paper3_liquidation_policy/protocol_semantics.md`.
- **Now active:** use `kamino/liquidations/v1` (102 events, 2025-08 to 2026-04) for the xStock empirical claim; analyze the 2025-11 cluster.
- **Still needed:** path-aware weekend truth, protocol-specific cost priors, dynamic-bonus / `D_repaid` fit, broader baselines, class-disaggregated reserve-buffer evaluation.

### Paper 4 / product-stack data clock

Paper 4 is later, but its forward-only data cannot wait. Scryer item 51 owns the urgent tapes:

- `jito_bundle_tape.v1`
- `validator_client.v1`
- `clmm_pool_state.v1`
- `dlmm_pool_state.v1`
- `dex_xstock_swaps.v1` backfill + forward poll

See `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md`.

## Phase Sequencer

| Phase | Product / deploy | Research | Data / methodology |
|---|---|---|---|
| Phase 0 | Done: v1b backtest + serving API | Done: validation evidence | v1b methodology locked |
| Phase 1 (now) | Devnet / publish path / router work | Paper 1 finish; Paper 3 first draft | Paper 3 event analysis; Paper 4 forward-capture setup |
| Phase 2 | Public comparator dashboard; first design-partner conversations | Paper 1 + Paper 3 live after gates | Rolling rebuild prep; buffer drift alerts |
| Phase 3 | Mainnet + paid pilot / B2B | AFT/FC/workshop submissions | V2 items when data gates fire |

## Current Paper Tracks

### Paper 1 — calibration-transparent oracle

Contribution: consumers choose target coverage `τ`; Soothsayer serves the empirically calibrated band plus receipts.

Current state:

- Held-out 2023+ passes Kupiec + Christoffersen at `τ ∈ {0.68, 0.85, 0.95}`.
- `τ=0.99` is out of v1 scope as a finite-sample tail ceiling.
- Draft sections live in `reports/paper1_coverage_inversion/`.

Immediate work:

- Finish §4/§5/§7/§8 and coherence pass.
- Refresh comparator and caveat language.
- Decide whether the CME 1m factor rerun is pre-submission or a disclosed follow-up.

### Paper 3 — liquidation policy under calibrated uncertainty

Contribution: map calibrated bands to lending-protocol action under real reserve buffers, costs, and truth semantics.

Current structure:

- **Geometric:** per-reserve adverse-move buffers split Kamino-xStocks into narrow SPYx/QQQx and wide remaining reserves.
- **Structural:** Soothsayer avoids Kamino's block-state failure mode when validity gates fail.
- **Empirical:** Kamino-xStocks now has the event panel; MarginFi is deployment-substrate / propagation evidence, not the primary xStock panel.

Immediate work:

- Draft §1/§2/§3/§4/§6 around that structure.
- Analyze Kamino 2025-11 cluster and fit dynamic-bonus / repayment distributions.
- Extend `run_protocol_compare` to real reserve-buffer and path-aware truth semantics.

### Paper 4 — oracle-conditioned AMMs

Contribution: auditable LVR-recovery lower bound for tokenized-RWA AMM pools consuming calibrated bands.

Current state:

- Not on the grant critical path.
- Data capture is urgent because bundle, validator-client, and pool-state tapes are forward-only or retention-limited.
- Consumer-side work starts after scryer rows exist.

## Design-Partner Framing

Use **two substrates, two questions**:

- **MarginFi:** cleanest general-lending deployment-substrate argument because `assets use P-conf, liabilities use P+conf` maps directly to `(lower, upper)`. No direct xStock Banks in current 422-Bank scan.
- **Kamino-xStocks:** xStock-specific empirical home and demo/comparator surface. The 9-month liquidation panel supports Paper 3's empirical claim; MarginFi xStock-adjacent events become cross-protocol propagation evidence when available.

Do not revert to the superseded "Kamino-first" or "MarginFi-first" simplification without updating `reports/methodology_history.md`.

## Phase 3 Start Conditions

Need at least two before mainnet push:

- Paper 1 and Paper 3 have absorbed external feedback.
- At least one design-partner LOI or paid pilot.
- Devnet has been live for >=4 weeks with no calibration regression.

## Source-of-Truth Links

- Methodology state: `reports/methodology_history.md`
- Product spec: `docs/product-spec.md`
- Data read pattern: `docs/scryer_consumer_guide.md`
- Paper 1: `reports/paper1_coverage_inversion/`
- Paper 3: `reports/paper3_liquidation_policy/plan.md`
- Paper 4: `reports/paper4_oracle_conditioned_amm/plan.md`
- Paper 4 data clock: `reports/paper4_oracle_conditioned_amm/scryer_pipeline_plan.md`
- Future methodology: `docs/v2.md`
