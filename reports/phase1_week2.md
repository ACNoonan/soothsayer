# Phase 1 Week 2 — On-chain publisher scaffold

**Date:** 2026-04-24 (revised post-review 2026-04-24)
**Status:** Source + tests complete and reviewed. Toolchain install + devnet deploy remain as user-run steps.

## What shipped (code-complete)

### On-chain program

- **`programs/soothsayer-oracle-program/`** — Anchor program with:
  - `initialize`, `publish`, `set_paused`, `rotate_signer_set` instructions
  - `PublisherConfig`, `SignerSet`, `PriceUpdate` accounts (all PDAs)
  - Structured Anchor events for every state change
  - On-chain invariant checks: band ordering, coverage ≤ 10 000 bps, exponent ∈ [-12, 0], signer membership, publish cadence rate-limit
  - Pyth-Sep-2021-RCA-informed layout: absolute fixed-point `i64` prices, single shared exponent, `u16` basis-points encoding for coverage/buffer (no float on the wire)
- **`Anchor.toml`** at repo root — Anchor workspace config. Placeholder program ID is `11111111111111111111111111111111` (the system program address); `scripts/deploy_devnet.sh` rewrites both `lib.rs :: declare_id!` and `Anchor.toml :: programs.*` to the generated keypair's pubkey on first deploy.

### Consumer SDK

- **`crates/soothsayer-consumer/`** — `no_std`, minimal-dep decoder for downstream protocols. Exposes:
  - `PriceBand` typed view with `point_f64()`, `lower_f64()`, `upper_f64()`, `symbol_str()`, `half_width_bps()`, `validate_invariants()`
  - `decode_price_update(&[u8]) -> Result<PriceBand, DecodeError>` — straight little-endian memcpy matching `state.rs` layout byte-for-byte
  - Regime + forecaster codes mirrored as public constants
- 5/5 unit tests pass (symbol null-padding, invariant detection, data-size match, discriminator rejection, etc.)

### Publisher CLI extension

- **`soothsayer prepare-publish`** subcommand — converts the off-chain `PricePoint` into the on-chain `PublishPayload`:
  - Float prices → fixed-point `i64` at exponent `-8` (8-decimal precision)
  - Float coverage → integer basis points (0.95 → 9 500)
  - Friday timestamp anchored at **20:00 UTC** (US equity close)
  - Outputs JSON with full decomposition, or `--bytes-only` hex for piping into a signer
- Byte round-trip: 66-byte payload encodes all fields losslessly at 10⁻⁸ precision
- 6/6 tests pass, including an exact fri_ts lock (`1776456000` for 2026-04-17) and a payload-size lock at 66 bytes

### Deploy flow

- **`scripts/deploy_devnet.sh`** — idempotent-ish Bash script that:
  1. Checks Solana + Anchor tooling
  2. Sets cluster, wallet, airdrops SOL if balance is low (devnet only)
  3. Generates a program keypair if missing
  4. Syncs the program ID into `lib.rs` `declare_id!()` + `Anchor.toml`
  5. Runs `anchor build` + `anchor deploy`
  6. Prints the next-step command for TS initialization

## Account layout (wire format)

```rust
// programs/soothsayer-oracle-program/src/state.rs
#[account]
pub struct PriceUpdate {
    // 8 bytes
    pub version: u8,
    pub regime_code: u8,             // 0=normal, 1=long_weekend, 2=high_vol, 3=shock
    pub forecaster_code: u8,         // 0=F1_emp_regime, 1=F0_stale
    pub exponent: i8,                // shared across price fields; default -8
    pub _pad0: [u8; 4],

    // 8 bytes
    pub target_coverage_bps: u16,    // what consumer asked for (9500 = 95%)
    pub claimed_served_bps: u16,     // what we actually served (9750 = 97.5%)
    pub buffer_applied_bps: u16,     // empirical calibration buffer (250 = 2.5%)
    pub _pad1: [u8; 2],

    pub symbol: [u8; 16],            // ASCII null-padded

    // 32 bytes — 4 × i64 prices, absolute fixed-point at shared `exponent`
    pub point: i64,
    pub lower: i64,
    pub upper: i64,
    pub fri_close: i64,

    // 24 bytes — timestamps
    pub fri_ts: i64,                 // unix timestamp of anchor Friday 20:00 UTC
    pub publish_ts: i64,             // unix timestamp of this publish
    pub publish_slot: u64,

    // 40 bytes — signer identity
    pub signer: Pubkey,              // 32
    pub signer_epoch: u64,           // 8
}

// Total on-chain: 8 (discriminator) + 128 (data) = 136 bytes per symbol
```

Design notes from `07.1 - Deep Research Output v2` Topic 5 (Pyth Sep-2021 BTC flash-crash post-mortem):

- **Absolute prices, not deltas.** A consumer reading `lower` gets a real price; no `point + lower_delta` trap.
- **Single exponent.** No per-field exponent mismatch.
- **Integer basis points.** `claimed_served_bps: u16` is exact and deterministic across Rust/Anchor IDL-ts/JS/Python.

## What's still user-run (one-time toolchain install)

This machine doesn't have `solana`, `anchor`, or `cargo-build-sbf`. The program `cargo check`s cleanly on the normal toolchain (with 15 noisy-but-harmless `unexpected_cfgs` warnings from Anchor's macros that disappear under `anchor build`). The BPF build + devnet deploy requires:

```bash
# Solana CLI (Anza fork):
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"

# Anchor CLI + version manager:
cargo install --git https://github.com/coral-xyz/anchor avm --locked --force
avm install 0.30.1
avm use 0.30.1

# Then from repo root:
./scripts/deploy_devnet.sh
```

On a preinstalled machine:

```bash
./scripts/deploy_devnet.sh         # build, deploy, print program ID
./target/release/soothsayer prepare-publish --symbol SPY --as-of 2026-04-17 --target 0.95 --bytes-only
# feed those bytes to a TS publish script (Week 2.5)
```

## What's explicitly deferred to Week 2.5

1. **TS integration harness** — `tests/integration.ts` using `@coral-xyz/anchor` to call `initialize` once, then drive `publish` instructions. Natural consumer of `prepare-publish --bytes-only` output.
2. **Full `publish` subcommand** — Rust side that signs + submits the tx via `solana-client` / `anchor-client`. Adds ~15 min first-build compile for the solana-sdk dep tree.
3. **CU benchmark** — needs a live validator. `solana-test-validator` locally + `solana logs` parse, or devnet + `getTransaction` compute-budget field. Expected ~2–5 k CU per publish.
4. **Keypair rotation test** — exercise `rotate_signer_set` + verify old signer rejection.

## Review-pass fixes (applied 2026-04-24)

A review pass fixed concrete blockers in my initial scaffold:

1. `programs/soothsayer-oracle-program/Cargo.toml` — replaced broken `version.workspace = true` inheritance (the program is intentionally outside the Cargo workspace) with explicit package fields; added Anchor's `init-if-needed` feature that my `Publish` accounts context requires.
2. `programs/soothsayer-oracle-program/src/lib.rs` — corrected the placeholder program ID from `"SootHSayer..."` (not a valid 32-byte base58 pubkey) to `"11111111111111111111111111111111"` (the system program's address, the Solana-standard placeholder convention); fixed the PDA seed from `&payload.symbol` to `payload.symbol.as_ref()` so Anchor's `Seeds` trait resolves cleanly.
3. `Anchor.toml` — matched the same placeholder ID so `declare_id!` + the `programs.*` table stay in sync until deploy tooling rewrites them.
4. `crates/soothsayer-publisher/src/payload.rs` — fixed `fri_ts` to consistently encode 20:00 UTC (US equity close), removing the previous comment/code contradiction; added tests locking the exact `fri_ts` value for 2026-04-17 (`1776456000`) and the serialized payload size (66 bytes).

After these fixes:

- `cargo check` on the Anchor program succeeds
- `cargo test -p soothsayer-publisher` — 6/6 pass
- `cargo test -p soothsayer-consumer` — 5/5 pass
- `scripts/verify_rust_oracle.py` — 30/30 Python-Rust parity cases still pass

## What's ready for Week 3

Week 3's Kamino-fork demo + xStock-specific overlay needs:

- [x] A decoded on-chain price band (via `soothsayer-consumer`)
- [x] Regime-aware serving logic (hybrid per-regime forecaster)
- [x] Calibration receipt exposed to consumer (`claimed_served_bps`, `buffer_applied_bps`, `regime_code`, `forecaster_code`)
- [x] V5 tape running (PID `/tmp/v5_tape.pid`, gathering basis data since 2026-04-24 04:16)
- [ ] A devnet-deployed program to read from (Week 2.5, blocked on toolchain)
- [ ] xStock-specific overlay calibration (Week 3 proper, needs ≥ 1 month V5 tape)

The Kamino-fork **consumer-integration demo** — LTV logic + regime multiplier against a `PriceBand` — can be built immediately in Rust without waiting on either the devnet deploy or the V5-tape-driven overlay. That's the most valuable Week 3 artifact to kick off now; the xStock overlay calibration waits on tape data.

## Files touched

```
programs/
  soothsayer-oracle-program/      NEW — Anchor program
    Cargo.toml                    explicit metadata + init-if-needed feature
    src/lib.rs                    Program entry + instruction handlers + events
    src/state.rs                  PublisherConfig / SignerSet / PriceUpdate account structs
    src/errors.rs                 SoothsayerError enum

crates/
  soothsayer-consumer/            NEW — no_std decoder for downstream protocols
    Cargo.toml
    src/lib.rs                    PriceBand + decode_price_update + 5 unit tests

crates/soothsayer-publisher/      (extended)
  Cargo.toml                      + thiserror, + soothsayer-consumer
  src/main.rs                     + prepare-publish subcommand
  src/payload.rs                  NEW — PricePoint → PublishPayload + 6 tests

Anchor.toml                       NEW — Anchor workspace config
scripts/deploy_devnet.sh          NEW — end-to-end deploy flow
```
