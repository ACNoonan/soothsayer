# Soothsayer integration guide (design partners)

> **Status: scaffold — integration content lands with the Paper 1 release; devnet-only, pre-partner.**
> This is a structural skeleton. Sections carry orientation + `TODO` markers, not
> finished prose. The authoritative wire-format source is
> [`research/coverage-inversion/rewrite/14_appendix_E.md`](../research/coverage-inversion/rewrite/14_appendix_E.md)
> (Appendix E — "The serving layer"). Where a detail here would duplicate the
> paper or the code, this doc points instead of copying.

For the upstream-data read pattern (analysis side, not on-chain), see
[`docs/scryer_consumer_guide.md`](scryer_consumer_guide.md). This guide is the
on-chain consumer counterpart.

---

## 1. Overview — what the oracle provides

Soothsayer publishes, per symbol, a **calibration-receipt band**: a point estimate
plus a lower/upper bound at a requested coverage target `τ`, plus a receipt naming
the exact scalars used. A consumer values collateral (or quotes a swap) against the
*band*, not a bare number, and can audit the coverage claim against public data.
The product shape is documented in [`README.md`](../README.md) ("What consumers get")
and the on-chain serving contract in Appendix E §E.1.

- On-chain, the band lives in a `PriceUpdate` account (PDA per symbol).
- Off-chain/Python callers get the same fields from `Oracle.fair_value_lwc`
  (`src/soothsayer/oracle.py`); Rust/on-chain callers decode the account bytes.
- Byte-for-byte parity between the two is the audit contract (Appendix E §E.5).

TODO: one-paragraph "who this is for" (AMM / lending / perp integrator) and the single
sentence value prop, once the partner segment is fixed (ROADMAP Phase 2).

---

## 2. Reading a band on-chain

A consumer links the `no_std` decoder crate
[`crates/soothsayer-consumer`](../crates/soothsayer-consumer) and calls
`decode_price_update(account_data) -> PriceBand`. That is the entire read surface —
no Anchor program dependency, no std.

Key surface (see `crates/soothsayer-consumer/src/lib.rs`):

- `PRICE_UPDATE_DISCRIMINATOR` — verify before decoding.
- `decode_price_update(&[u8]) -> Result<PriceBand, DecodeError>`.
- `PriceBand::validate_invariants()` — enforces `lower ≤ point ≤ upper`, version,
  and coverage/buffer bounds. **Call this before trusting any field.**
- `PriceBand::lower_f64()` / `point_f64()` / `upper_f64()` — scaled prices.
- `PriceBand::half_width_bps()`, `symbol_str()`, typed `forecaster()` / `profile()`.

TODO: minimal end-to-end code example (fetch account → verify discriminator →
`decode_price_update` → `validate_invariants` → read `lower_f64()`). The
on-chain read is already exercised in `programs/soothsayer-band-amm-program`
(swap path) and `crates/soothsayer-demo-kamino` (lending path) — lift a
minimal snippet from one of those rather than writing fresh.

---

## 3. The `PriceUpdate` wire format

Do **not** re-document the layout here — it is specified once in Appendix E §E.4
(field-by-field `PriceUpdate` table, the three design rules: absolute prices, single
shared exponent, integer basis points). The decoder in
`crates/soothsayer-consumer/src/lib.rs` mirrors it byte-for-byte
(`PRICE_UPDATE_DATA_SIZE = 128` + 8-byte Anchor discriminator).

- Layout / rationale: **Appendix E §E.4**.
- Canonical struct + offsets: `crates/soothsayer-consumer/src/lib.rs`
  (`decode_price_update`) and `programs/soothsayer-oracle-program/src/state.rs`
  (kept in lockstep — a schema bump touches both).

TODO: link the exact `state.rs` line range once the layout is frozen for the
partner release; note the `profile_code` byte (repurposed `_pad0[0]`, per
`reports/active/m6_refactor.md` A4) is part of the contract.

---

## 4. The receipt fields and what they mean for a consumer

The receipt is the differentiator: it tells the consumer what coverage was actually
served and under which regime/forecaster. The decision-theoretic meaning of these
fields (choosing `τ`, mapping band width to reserve headroom) is developed in the
paper — see **§3 (auditability / claims)** and **§4 (deployed serving)**, and the
worked `τ → reserve` example in **Appendix E §E.7**.

Consumer-facing receipt fields (from `PriceBand`):

- `target_coverage_bps` — the `τ` the publisher targeted (integer bps).
- `claimed_served_bps` — the band's actual coverage claim (`τ + δ(τ)`).
- `buffer_applied_bps` — `δ(τ)` shift on the receipt (M6 deploys `δ = 0`; README "How it works").
- `regime_code` — `normal` / `long_weekend` / `high_vol` (typed via `Regime`).
- `forecaster_code` — which forecaster produced the band (see §7 caveats).
- `profile_code` — serving profile (`lending` / `amm`); a consumer should assert it
  matches its integration (`Profile::from_code`; demo enforces this).

TODO: for each field, one line on "what a consumer *does* with it" (e.g. AMM widens
outside-band surcharge on `regime_code = high_vol`). Ground each against §4 / Appendix E,
not invented policy — the paper is explicit that policy optimisation is out of scope (§3.5).

---

## 5. Worked example

Two reference integrations already exist in-repo; the worked example should walk one
of them rather than inventing a new flow.

- **Lending (Kamino-style):** [`crates/soothsayer-demo-kamino`](../crates/soothsayer-demo-kamino)
  (~400 lines) — values collateral at the band's **lower bound**, drives an
  LTV/liquidation ladder off it. Runner: `cargo run --release -p soothsayer-demo-kamino --bin run_demo`
  (consumes `data/processed/demo_kamino_scenarios.json`; see the bin's header). This is
  the "third audience" of Appendix E §E.6/§E.7.
- **AMM (band-conditioned swap):** [`programs/soothsayer-band-amm-program`](../programs/soothsayer-band-amm-program)
  reads the `PriceUpdate` PDA as a plain account, decodes via `soothsayer-consumer`,
  and charges an in-band fee vs. a width-scaled outside-band surcharge. Devnet driver:
  the `soothsayer-band-amm` CLI (`programs/soothsayer-band-amm-cli`) — see
  [`docs/devnet-quickstart.md`](devnet-quickstart.md).

TODO: pick the primary walkthrough for the partner segment (AMM likely, per ROADMAP
Phase 2 + Paper 4), then narrate: publish a band → pool reads it → in-band vs.
outside-band swap outcome, with the actual CLI commands from the quickstart.

---

## 6. Devnet deploy + publish

The runnable 15-minute path (prerequisites, deploy, initialize, publish, read back)
lives in **[`docs/devnet-quickstart.md`](devnet-quickstart.md)**. Do not duplicate the
commands here — link to it.

TODO: once the quickstart is verified end-to-end, add a one-line "you should now see a
decoded band" pointer back into §2.

---

## 7. Status / caveats

- **On-chain currently serves the M5 path.** New on-chain publishes carry
  `forecaster_code = 2` (`FORECASTER_MONDRIAN`). M6 LWC (`forecaster_code = 3`,
  `FORECASTER_LWC`) is live in the Rust serving stack and decodes cleanly via
  `soothsayer-consumer`, but **on-chain enablement is gated on the next publisher
  release** (Appendix E §E.5, "Wire format invariance"; README `crates/` note).
  Consumers branching on `forecaster_code` should handle both code 2 and code 3.
- **Devnet only, not mainnet.** Mainnet / paid-pilot work is gated on Paper 1 + Paper 3
  evidence, ≥4 weeks devnet stability, and ≥1 design-partner LOI (`docs/ROADMAP.md`,
  "Phase 3 Start Conditions"). Treat every address and flow here as devnet.
- **The band-AMM program is an early scaffold.** Its own header notes swap-math and
  staleness-guard bodies were filled in across a multi-day build; verify current state
  in `programs/soothsayer-band-amm-program/src/lib.rs` before relying on any specific
  guarantee.

TODO: add the frozen devnet program IDs + a "last verified" date once the partner
release is cut (current IDs live in `Anchor.toml [programs.devnet]`).
