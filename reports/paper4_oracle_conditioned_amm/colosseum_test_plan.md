# BandAMM — pre- and post-launch test plan

**Status:** scoping draft, 2026-05-02. Companion to `colosseum_implementation_brief.md`.
**Scope:** the 8-day Colosseum MVP only — devnet + pitch quality, *not* production audit.

## 1) Ground rules

- **Calibration discipline carries to tests.** Every assertion is held-out evidence, not "looks right at-a-glance." Random fixtures land in CI; manually-crafted fixtures land in the deck.
- **Two surfaces are load-bearing and get the most coverage:** (a) the band-conditional swap-fee path (the mechanism), (b) the receipt-vs-on-chain-band reconciliation (the audit-chain story).
- **One surface is explicitly out of scope:** formal verification / full audit. Document the gap in the README; do not ship pretending otherwise.
- **No external data fetching in tests.** Mock `PriceUpdate` accounts in unit/integration; on devnet, read the live publisher's PDA. CLAUDE.md §1 still applies.
- **No `unsafe`. No floats on-chain.** Linter floor (`crates/*` already has Restate-style lint floor per recent commit).

## 2) Test surface map

| Layer | Tool | Where | Speed | Mocks band? |
|---|---|---|---|---|
| Unit (math + decode) | `cargo test` (Rust `#[test]`) | `programs/soothsayer-band-amm-program/src/**/*.rs` `#[cfg(test)]` modules | <2s | n/a |
| Property / fuzz | `proptest` | same crate, gated test module | <30s | n/a |
| Anchor integration | `solana-program-test` (BanksClient) + `anchor test` | `programs/soothsayer-band-amm-program/tests/` | <60s | yes — synthetic PDA |
| Devnet smoke | TS + `@solana/web3.js` script | `programs/soothsayer-band-amm-program/tests/devnet/` | minutes | no — real publisher |
| Devnet soak | launchd plist running smoke loop, structured-log scrape | `~/Library/LaunchAgents/` (Adam's standard pattern) | hours | no |
| Counterfactual | Python notebook reading scryer parquet | `notebooks/paper4_band_amm_counterfactual.ipynb` | minutes | n/a — historical data |

## 3) Unit tests (Rust, in-crate)

### 3.1 Swap math

- `swap_inside_band_charges_f_in` — pre-swap and post-swap effective price both inside `[lower, upper]`; output equals constant-product math at `f_in` exactly.
- `swap_exits_band_charges_f_out` — pre-swap inside, post-swap outside; surcharge applied; effective fee equals `f_in + α · clamp(d/w, 0, w_max)`.
- `swap_already_outside_band` — pre-swap outside (band moved post-deposit); apply outside-tier from byte 1.
- `swap_crossing_band_edge` — output spans the boundary; verify the fee blends correctly per the chosen rule (single-tier-by-end-state is the simplest spec; document and test exactly that rule).
- `min_amount_out_enforced` — output below `min_amount_out` returns `SlippageExceeded`, no state change.
- `zero_amount_in_rejected`.
- `amount_in_exceeds_reserves_rejected_cleanly` — no panic, named error.
- `fee_alpha_zero_collapses_to_flat_fee` — sanity for ablation comparator.

### 3.2 LP accounting

- `first_deposit_sets_initial_lp_supply` — uses `sqrt(base * quote)` or chosen formula; document and test.
- `subsequent_deposit_prorata` — small, large, and 1-wei-deviation deposits.
- `withdraw_returns_exact_reserves` — full and partial; verify rounding direction is *down for user* (no LP-funded griefing).
- `lp_supply_invariant` — `sum(positions) == lp_mint.supply` after a randomized deposit/withdraw sequence.

### 3.3 Band-PDA decode

These exercise `soothsayer-consumer::decode_price_update` from inside the AMM:

- `wrong_discriminator_returns_decode_error_not_panic`.
- `version_mismatch_rejected` — set `version=2` byte; expect `BandRejected::VersionMismatch`.
- `inverted_band_rejected` — `lower > upper` should never reach the swap math.
- `coverage_out_of_range_rejected` — `target_coverage_bps > 10_000`.
- `stale_band_rejected` — `now - publish_ts > MAX_STALENESS_SECS`. Test at boundary (`==`), just-over (`+1s`), and well-over (`+1h`).

### 3.4 Authority + pause

- `non_authority_cannot_pause`.
- `paused_pool_refuses_swap_and_deposit`.
- `paused_pool_allows_withdraw` — policy choice; test whichever is shipped, document in IDL doc.
- `unpause_restores_swap_path`.

## 4) Property / fuzz tests (`proptest`)

Single goal: catch math bugs the unit tests miss. Run in CI on every push.

- **Reserves-product monotonicity** — for any random `(reserves_pre, amount_in, side, band)`, `reserves_post.base * reserves_post.quote ≥ reserves_pre.base * reserves_pre.quote` modulo accrued fees. Single property covers a huge bug class.
- **Band-invariant trickle-through** — for any decoded `PriceBand`, the swap path either rejects it pre-math or returns a result whose effective price respects `lower ≤ effective_price ≤ upper` (inside-band branch) or whose surcharge is non-negative (outside-band branch). Never a free arb.
- **LP roundtrip** — `deposit(a, b) → withdraw(all)` returns exactly `(a, b)` minus 0–1 wei rounding *to the user's disadvantage*, never their advantage.
- **Fee schedule monotonicity** — `f_out` is monotonic non-decreasing in `d` (distance outside band) and monotonic non-increasing in `w` (band width). Surfaces sign-flip bugs in the schedule.
- **No-op symmetry** — swapping `ε` then `-ε` returns to within 1-wei of pre-state.

## 5) Anchor integration tests (localnet)

Run via `anchor test` against `solana-program-test`. Synthesise the `PriceUpdate` PDA inline — Anchor program-test lets you write arbitrary account data to any pubkey before invoking the IX.

### 5.1 Happy path

- `deposit → swap_in_band → withdraw` round-trip; verify SPL token balances + LP mint supply match expectations.
- `swap` with realistic SPYx-USDC band (e.g., `point=70000_00000000` exp=-8, ±150 bps band). Decode receipt event; assert all band fields preserved at execution.
- `deposit_two_lps_then_swaps_then_withdraw_both` — fees accrue prorata.

### 5.2 Adversarial path

- `swap_with_attacker_supplied_fake_price_pda` — caller passes a different account at the `soothsayer_price_update` slot. Anchor account-constraint catches it; named error.
- `swap_with_stale_band` — synthesize a band 5 minutes old; expect `BandStale`. Then advance the block clock and re-publish; expect success.
- `swap_when_oracle_program_paused` — staleness eventually triggers the same path; covers the publisher-outage scenario.
- `pool_refuses_swap_when_band_pda_does_not_exist` — uninitialized account; clean error not panic.

### 5.3 Receipt invariant (the audit-chain test)

This is the test that backs the pitch.

- `swap_event_matches_band_pda_at_publish_slot` — every emitted `Swap` event's `(lower, upper, claimed_served_bps, regime_code, publish_slot)` *exactly equals* the band PDA's bytes at the `publish_slot` it claims. No drift, no fast-forward, no fall-back. This is the on-chain analogue of Paper 1's calibration receipt.

## 6) Pre-deploy checklist (gate to devnet)

Hackathon-grade hygiene, not a full audit. Run through this list before `solana program deploy`:

- [ ] All `Signer<'info>` accounts are validated where required (authority on `pause`, `set_authority`; payer on `deposit`).
- [ ] All PDAs derive deterministically from documented seeds; no caller-supplied bumps.
- [ ] All SPL token transfers use `anchor_spl::token::transfer` (no manual `invoke`); signer seeds are program-PDA-owned, never user-controlled.
- [ ] No `unsafe` blocks (`#![forbid(unsafe_code)]` at crate root).
- [ ] No `f32`/`f64` arithmetic in program logic (bps + i64 fixed-point only).
- [ ] Cross-program account reads check Anchor discriminator + version *before* deserializing fields.
- [ ] `init_if_needed` only on the LP mint and pool PDA — not on user positions.
- [ ] Compute budget: swap IX fits in default 200k CU. If it doesn't, set `ComputeBudgetInstruction::set_compute_unit_limit` explicitly; do not silently over-run.
- [ ] LP mint authority = pool PDA. Not the program upgrade authority. Not a hot key.
- [ ] No CPI back into self; no recursive `swap` paths.
- [ ] All numeric ops use `checked_*` or `saturating_*`; no implicit wrap.
- [ ] `set_paused` is reversible without re-init.
- [ ] Anchor IDL emits cleanly and matches the on-chain schema. Commit the IDL.
- [ ] `cargo clippy --all-targets -- -D warnings` clean.
- [ ] `cargo test --release` clean.
- [ ] `anchor test` clean on localnet.
- [ ] Program ID in `declare_id!` matches the keypair the deploy will use.

## 7) Devnet smoke (first 60 minutes post-deploy)

Tight, scripted, 60-minute window after `solana program deploy` lands on devnet.

1. **Pool init.** `initialize_pool(SPYx_test, USDC_devnet, soothsayer_price_pda)` lands. Read the pool PDA back; confirm fields match init payload.
2. **First deposit.** Deposit ~$1k notional from the demo authority; LP mint emits; balances reconcile.
3. **First swap inside band.** $100 notional swap; receipt event indexable on RPC; off-chain reconciler asserts receipt matches band PDA at the claimed slot.
4. **First swap outside band.** Force the pool past band edge with a larger trade; surcharge fee tier visible in event; LPs accrue the surcharge.
5. **Pause / unpause cycle.** Authority pauses; swap fails with `Paused`; unpause; swap succeeds again.
6. **Withdraw.** Authority withdraws partial LP; balances reconcile.
7. **Explorer artefacts captured.** Tx signatures + receipt events linked from README.

If any of the seven fail, do not proceed to soak; debug + redeploy.

## 8) Devnet soak (24–72h before pitch)

Background loop. Adam's standard pattern is launchd; one plist runs the smoke loop on a 5–10 minute cadence and writes structured logs to disk. Dashboard is a `tail | jq` one-liner — not a real monitor, just enough for the demo.

Soak invariants:

- **Publisher freshness.** Median `now - band.publish_ts` < `MAX_STALENESS_SECS / 2` over the 24h window. Below this, the staleness guard wouldn't trip; above it, demo risk.
- **Swap success rate** ≥ 99% on the smoke-loop path. Sub-99% gets one investigation pass before the pitch.
- **Receipt-band reconciliation** off-chain script: pull every swap event in the soak window, join to `PriceUpdate` PDA history at `publish_slot`, assert exact match. Zero mismatches is the bar.
- **Compute units per swap** stable within the budget headroom; rising CU is a regression flag.
- **No accrued bad debt / no negative reserves** at any sampled point. The math should make this impossible; the soak proves it.

Synthetic-event drills during the soak:

- **Halt drill.** Pause the publisher for 2× `MAX_STALENESS_SECS`. Pool refuses swaps; receipts log no events; resume publisher; pool resumes swaps. *Captures the live demo's most pitch-able moment.*
- **Regime drill.** Manually publish a `regime_code = high_vol` band update with widened `[lower, upper]`. Watch the surcharge tier kick in on a borderline swap; verify the receipt's `regime_code` matches.

## 9) Counterfactual validation (deck artefact)

Off-chain Python notebook; reads scryer parquet only.

- **Inputs.** `yahoo/equities_daily/v1/symbol=SPY/...` + `cme/intraday_1m/v1/...` + `soothsayer_v5/tape/v1/...` + `nasdaq/halts/v1/...`. All already live (`scryer_pipeline_plan.md` §2a).
- **Replay.** For each weekend window in the panel, simulate `(a) CPMM`, `(b) BandAMM-no-surcharge`, `(c) BandAMM-with-surcharge` against the band time-series. Realised "LP economics" proxy = fee revenue net of LVR-against-Monday-open.
- **Validation.** The chart only ships if `(c) > (b) > (a)` *on the median window* with a disclosed sign of the high-vol-tertile result. If high-vol tertile inverts, disclose — Paper 1's discipline; the pitch is stronger when honest.
- **What the chart is *not*.** Slot-resolution. Bundle-attributed. Path-aware. Those are Paper 4 Phase A deliverables; the deck must say so.

## 10) Cut lines if test scope slips

In priority order — drop highest first:

1. **Drop the synthetic regime drill** in §8. Rely on natural intra-day band variation during the soak.
2. **Drop the off-chain receipt reconciler.** Eyeball ~10 receipts via `solana logs` + a scratch `jq`. Disclose in README.
3. **Drop `proptest` fuzz** (§4). Unit + anchor only. Flag as v2.
4. **Compress the soak from 24–72h to 4–6h.** Pitch ships with thinner soak evidence.
5. **Drop the counterfactual notebook entirely.** Lean on Paper 1's existing 12-year evidence + the live devnet receipt as the only artefacts.
6. **Drop the surcharge-tier tests + ship band-bounded-only.** Mirrors `colosseum_implementation_brief.md` §3.6 cut line 4 — simpler mechanism, smaller test surface.

If any of the §6 pre-deploy checklist items fail and can't be fixed in <4h, hold the deploy. A late deploy is better than a deploy that gets dunked on at submission review.

## 11) See also

- `reports/paper4_oracle_conditioned_amm/colosseum_implementation_brief.md` — the mechanism + scope this plan tests.
- `crates/soothsayer-consumer/src/lib.rs:97-150,264-323` — invariants the BandAMM inherits and must not regress.
- `programs/soothsayer-oracle-program/src/state.rs:75-119` — the `PriceUpdate` shape every receipt test reconciles against.
- `reports/v1b_calibration.md` — the empirical evidence the AMM's on-chain receipt is the AMM-layer analogue of.
