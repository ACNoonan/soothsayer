# Adaptive cell state on the wire — design and decision

**Opened 2026-07-25.** Blocks promotion of W15 (adaptive per-cell level, overnight profile). See `w15_hybrid_adaptive_cells.md` and `w17_promotion_gate.md`.

## The problem

Today a served band is a **pure function of a frozen artefact**:

```
band = f( artefact(SHA-stamped, public pre-split data),  τ,  symbol,  as_of )
```

A consumer downloads one SHA-256-stamped file and re-derives any read in one step. That property *is* the product — §3's primitive is a verifiable coverage claim, not merely a well-calibrated one.

W15 changes the signature:

```
band = f( artefact,  τ,  symbol,  as_of,  m_{r,t} )
m_{r,t} = g( m_{r,0},  every realised outcome in cell r up to t )
```

`m` is no longer in the frozen file. If we ship W15 and say nothing, the receipt becomes insufficient to reconstruct the band — which would quietly break the one claim the paper is built on.

## What is and is not at risk

**Not at risk: verifiability.** `m` is a single scalar per cell, the update rule is deterministic and published, and its only inputs are realised prices — public data. Anyone can recompute the entire trajectory. Nothing here is unauditable.

**At risk: one-step verification.** Verification goes from O(1) — read the artefact — to O(t) — replay every period since inception. That is the cost the user identified as the operative distinction, and correctly noted is about *ability*, not difficulty. Ability survives; cost does not.

**Also at risk, and less obvious: the commitment property.** A frozen artefact is a *pre-commitment* — the provider cannot change what it published. An adaptive `m` is recomputed each period by the provider, so a provider deviating from the update rule is only caught by full replay. That is a weaker trust story than "here is a hash we published in advance", and it is the part worth engineering around.

## Design

Three changes, in dependency order.

**1. `m_{r,t}` in the receipt.** Add `diagnostics.m_regime` alongside the existing `q_regime_lwc`, `c_bump`, `sigma_hat_sym_pre_fri`. The receipt's stated purpose (§3) is to carry sufficient statistics for the band; with W15 live and `m` absent it no longer does. This is the non-negotiable piece — without it the receipt is wrong, not merely incomplete.

**2. `m_regime` column in the public band archive.** `data/band_archive/bands_v1.csv` is the append-only served-band record `soothsayer-verify` audits. A row whose band cannot be reproduced from its own columns is not an audit record. New column, new schema version; existing rows are unaffected because the two-sided weekend profile stays frozen (W16 recommends W15 for the **overnight** profile only).

**3. Periodic signed checkpoints — this is what restores one-step verification.** Publish `(period, cell, m)` on a fixed cadence with a hash, exactly as the artefact freeze does today. Verification then becomes:

- *verify one read* — O(1) against the published `m` in the receipt;
- *audit the state* — replay only since the last checkpoint, not since inception;
- *detect provider deviation* — recompute the checkpoint from public prices and compare hashes.

A quarterly cadence bounds replay at ~65 overnight periods. This is the "aggregate the equation so it is more easily verified" shape: `m` is already an aggregate — 3–4 scalars — and checkpointing bounds how far back anyone must go to trust it.

## Recommendation

**Ship all three together or none.** Shipping W15 with (1) alone leaves the band archive unable to reproduce its own rows. Shipping (1) and (2) without (3) leaves verification unbounded and drops the pre-commitment property — which is the strongest thing the frozen design has.

**Keep the weekend profile frozen.** W15 is inert on the weekend panel (W15/W16), so there is no reason to take on adaptive state there. The recommended split — weekend `W13+W14` frozen, overnight `W15` adaptive — means only one profile carries live state, and the paper's headline weekend results keep the pure-frozen contract unchanged.

**Sequence.** Checkpoint format first, then archive schema, then the receipt field, then promote W15. Doing it in the other order ships a period where served bands are not reproducible from public record.

## Open questions for the paper

If W15 ships, §3 and §8 need a paragraph distinguishing the two contracts, because they are genuinely different claims:

- **frozen** — the band is a deterministic function of a pre-committed artefact; verification is O(1) and the provider cannot revise the artefact after the fact;
- **checkpointed-adaptive** — the band is a deterministic function of a pre-committed artefact plus a published state whose trajectory is itself derived from public data; verification is O(1) against the checkpoint and O(checkpoint interval) to audit the state.

Both are calibration-transparent. Only the first is a pre-commitment. That distinction should be stated by us rather than discovered by a referee, and it is a genuinely interesting design axis to have characterised — the paper currently presents frozen-vs-adaptive as a dichotomy (§7, §9), and this is the point where it turns out to be a spectrum.

## Status — implemented 2026-07-25, not promoted

The state machine and checkpoint format are built and tested; nothing is promoted and the deployed artefact is untouched.

- `src/soothsayer/adaptive_state.py` — `replay()` is the single definition of the update, run identically by publisher and auditor, so the two cannot drift apart by construction. `Checkpoint` carries a canonical serialisation whose SHA-256 covers γ, the clip bounds and the period as well as the numbers, so a provider cannot silently change the rule.
- `scripts/build_overnight_adaptive_checkpoint.py` — splits the artefact in two: frozen per-regime quantiles, SHA-stamped exactly as the two-sided artefact is (`a16a27b0e675c915…`), and a hashed state snapshot (`852a69320fbeb119…`, 2,404 periods through 2026-04-23). Self-verifies on build.
- `tests/test_adaptive_state.py` — 12 tests over the four audit properties.

Learned multipliers at the checkpoint:

| cell | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| `earnings_night` | 0.882 | **0.705** | **0.839** | 0.951 |
| `high_vol` | 1.142 | 1.019 | 1.003 | 0.982 |
| `normal` | 0.932 | 0.972 | 1.007 | 0.985 |

`earnings_night` learns *down*, which is the W14 drift diagnosis being repaired rather than a tuning artefact.

**The two properties that mattered are tested, not asserted.** Replaying from a checkpoint equals replaying from inception to 10 decimal places — that is what bounds audit cost to one checkpoint interval. And a tampered state that has been **re-sealed** with a fresh hash still fails `verify_checkpoint`, because recomputation from public prices does not care what hash the provider published. That is the pre-commitment property restored.

**All three items are now implemented.**

**(1) Receipt.** `Oracle.fair_value_overnight_adaptive()` carries `m_regime`, `artefact_sha256`, `checkpoint_sha256`, `checkpoint_through`, `adaptive_gamma` and `contract: "checkpointed_adaptive"` as **receipt fields**, not metadata — a receipt without them cannot reconstruct the band. The method refuses any τ not in the checkpoint's audited anchors rather than interpolating a multiplier the checkpoint does not authorise, and `_load_overnight_adaptive_constants()` refuses to serve at all if the checkpoint fails its own hash or references a different artefact than the sidecar.

**(2) Archive.** `ADAPTIVE_BANDS_COLUMNS` / `ADAPTIVE_BANDS_PATH` in `band_archive.py`, as a **separate** append-only file rather than a column added to `bands_v1.csv`. Three reasons: `bands_v1` is parsed by the `soothsayer-verify` crate against a fixed schema, STATUS pins its rows as never-edited, and the two profiles have genuinely different verification procedures — a frozen row checks against one hash, an adaptive row against an artefact hash *and* a checkpoint hash. Mixing them would force every consumer to branch on profile.

**(3) Cadence — quarterly.** Bounds an auditor's replay to ~63 overnight periods while keeping the published hash count small enough to eyeball. `overnight_adaptive_checkpoint_chain_v1.json` carries **49 linked checkpoints** (2014-03-31 → 2026-03-31), each referencing its predecessor's hash, verified linked end to end. Each link is built by replaying only its own quarter seeded from the previous state — *the same resume path an auditor uses*, so the chain is constructed by exactly the procedure that verifies it.

An auditor picks their own depth: one interval for a spot check, the whole chain for a full audit, and the chain is tamper-evident throughout because breaking any link breaks every hash after it.

**Remaining before promotion:** emit adaptive rows into `bands_adaptive_v1.csv` from the weekly harness (the schema exists, the emitter does not), and Rust parity for the adaptive serving path. Neither is a design question.
