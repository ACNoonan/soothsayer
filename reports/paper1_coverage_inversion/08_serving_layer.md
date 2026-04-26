# §8 — Serving-Layer System (draft)

The methodology of §4 is implemented as a four-component serving stack designed for two requirements that pull in opposite directions: (i) the model logic is research-iterated in Python and re-validated against the §6 OOS panel after every change; (ii) the production hot path is a Solana program reading bands at consumer-facing latency. This section describes how those requirements are reconciled in a single source of truth, and how the serving-time output of the Rust + on-chain stack is contractually identical to the Python reference's.

## 8.1 Split-by-function architecture

We separate *training* (Python) from *serving* (Rust + Solana).

```
Python (model + train)               Rust (serve)
──────────────────────              ──────────────────
scripts/run_calibration.py            soothsayer-oracle (lib)
  └─> v1b_bounds.parquet      ──>      └─> Oracle::fair_value()
  └─> v1b_calibration_surface.csv         (hybrid + buffer + inversion)
  └─> v1b_calibration_surface_pooled.csv
                                      soothsayer-publisher (CLI)
                                      └─> prepare-publish → on-chain payload
                                      
                                      soothsayer-oracle-program (Anchor)
                                      └─> publish() → PriceUpdate PDA
                                      
                                      soothsayer-consumer (no_std SDK)
                                      └─> decode_price_update(&[u8])
```

The Python `Oracle` (`src/soothsayer/oracle.py`) is the canonical specification. It both (a) produces the calibration artefacts consumed by every downstream serving component and (b) is the executable reference for the inversion algorithm. A change to the methodology — a new buffer schedule, a new regime, a grid extension — is implemented in Python first, validated end-to-end against the §6 OOS panel, and then ported to Rust under the byte-for-byte parity contract of §8.5. No model logic is duplicated between the two implementations: the training pipeline materialises the surface and bounds table once offline; the serving stack reads them.

## 8.2 The Rust crate stack

Four crates plus one Anchor program, with deliberately narrow responsibilities.

| Crate | Purpose | Lines | Tests |
|---|---|---:|---:|
| `soothsayer-oracle` | Library: loads the Python artefacts, exposes `Oracle::fair_value` with byte-exact equivalence to Python | ~600 | included in parity harness |
| `soothsayer-publisher` | CLI binary `soothsayer`: serves single reads, lists available `(symbol, fri_ts)` pairs, prepares on-chain publish payloads | ~500 | 6/6 unit tests |
| `soothsayer-consumer` | `no_std`, minimal-dep SDK for downstream protocols: decodes the on-chain `PriceUpdate` PDA into a typed `PriceBand` view | ~300 | 5/5 unit tests |
| `soothsayer-demo-kamino` | Reference Kamino-style consumer integration: consumes a `PriceBand` and emits `Safe / Caution / Liquidate` decisions | ~400 | included in integration tests |
| `soothsayer-oracle-program` (Anchor) | On-chain program: `initialize`, `publish`, `set_paused`, `rotate_signer_set` | ~400 | scaffolded, devnet deployment one command away |

The publisher CLI's primary subcommand is `fair-value`; its secondary subcommand `prepare-publish` converts an off-chain `PricePoint` (Python's nine-field receipt of §4.5) into the on-chain `PublishPayload` wire format of §8.4. The consumer SDK is intentionally `no_std` so it can be vendored into a Solana program account-decoder without dragging in the Rust standard library.

## 8.3 On-chain program

`programs/soothsayer-oracle-program/` is a vanilla Anchor program with three PDA account types and four instructions.

**Accounts.**

- `PublisherConfig` — global PDA seeded `[b"config"]`. Carries the authority pubkey, an emergency-pause flag, and the minimum-publish-interval rate-limit.
- `SignerSet` — global PDA seeded `[b"signer_set"]`. For Phase 1 the "Merkle root" is just the single publisher's pubkey stored directly; the multi-replicator Merkle-verification path is scaffolded for Phase 3.
- `PriceUpdate` — per-symbol PDA seeded by the symbol bytes. One account per symbol in the universe; first publish creates the account (`init_if_needed`), subsequent publishes overwrite in place.

**Instructions.**

- `initialize` — one-time setup; creates `PublisherConfig` and `SignerSet` PDAs.
- `publish(payload: PublishPayload)` — validates the signer membership, enforces the cadence rate-limit, checks on-chain band-ordering and coverage-bound invariants, and writes the new `PriceUpdate`. Emits a structured Anchor `Published` event.
- `set_paused` — authority-only emergency stop.
- `rotate_signer_set` — authority-only signer rotation.

Every instruction emits an Anchor event so off-chain indexers can trace publish history without re-reading every account state. The `publish` instruction enforces five on-chain invariants before persisting: band ordering ($L \le \hat P \le U$), coverage values $\le 10{,}000$ basis points, exponent $\in [-12, 0]$, signer membership in the `SignerSet`, and time since the last publish $\ge$ `min_publish_interval_secs`.

## 8.4 Wire-format design

The `PriceUpdate` account layout is informed by the Pyth-Network September-2021 BTC flash-crash post-mortem (publicly disclosed; see external references). Three design rules avoid the failure modes that incident exposed.

```
PriceUpdate (128 bytes data + 8-byte Anchor discriminator):

  version              u8         schema version, currently 1
  regime_code          u8         0=normal, 1=long_weekend, 2=high_vol
  forecaster_code      u8         0=F1_emp_regime, 1=F0_stale
  exponent             i8         shared across price fields, default -8
  _pad0                [u8; 4]
  
  target_coverage_bps  u16        consumer's request, integer bp
  claimed_served_bps   u16        served quantile, integer bp
  buffer_applied_bps   u16        empirical buffer, integer bp
  _pad1                [u8; 2]
  
  symbol               [u8; 16]   ASCII null-padded
  
  point                i64        absolute fixed-point at `exponent`
  lower                i64        absolute fixed-point at `exponent`
  upper                i64        absolute fixed-point at `exponent`
  fri_close            i64        absolute fixed-point at `exponent`
  
  fri_ts               i64        unix timestamp of anchor Friday 20:00 UTC
  publish_ts           i64        unix timestamp of this publish
  publish_slot         u64
  
  signer               Pubkey     32 bytes
  signer_epoch         u64
```

The three rules:

1. **Absolute prices, not deltas.** A consumer reading `lower` gets a real price directly. There is no `point + lower_delta` arithmetic that a downstream integration could get wrong.
2. **Single shared exponent.** The same `exponent` field applies to `point`, `lower`, `upper`, and `fri_close`, so cross-field comparisons are exact integer comparisons after a single multiply. There is no per-field-exponent mismatch footgun.
3. **Integer basis points, never floats.** Coverage and buffer values are `u16` basis points (9{,}500 = 95.00%). This is exact and deterministic across Rust, the Anchor IDL, TypeScript clients, and downstream Python consumers — no float-parse or float-compare drift between layers.

The full publish payload serialises to 66 bytes; the on-chain account is 128 bytes after Anchor padding. Both sizes are locked by unit tests in `crates/soothsayer-publisher/src/payload.rs` so a future schema change cannot silently break the wire format.

## 8.5 Byte-for-byte parity verification

`scripts/verify_rust_oracle.py` runs the Python `Oracle.fair_value` and the Rust `soothsayer fair-value` binary on the same `(symbol, fri_ts, target_coverage)` triples and asserts byte-exact agreement on the numeric output (point, lower, upper, sharpness_bps, claimed_served, calibration_buffer_applied) plus exact agreement on the string fields (regime, forecaster_used, calibration, clipped, bracketed). The current panel covers 75 cases: a deterministic sample of 25 random `(symbol, fri_ts)` pairs from the bounds table, plus explicit edge cases for SPY, GLD, TLT, MSTR, and HOOD at their most-recent Friday, served at three targets each ($\tau \in \{0.68, 0.95, 0.99\}$). **75/75 cases pass** as of the most recent re-run.

The parity harness is invoked after every methodology change. The 2026-04-25 sequence — per-target buffer landing (replacing the scalar 0.025), grid extension to {0.997, 0.999} with `MAX_SERVED_TARGET = 0.999`, and the $\tau = 0.99$ buffer bump from 0.005 to 0.010 — was applied to Python first, then ported to Rust; in each case the parity harness was re-run and re-verified before the change was considered shipped. The harness is the operational guarantee that the on-chain published bands correspond to the methodology evaluated in §6 and ablated in §7. It is also the contract that allows a consumer to verify a served `PricePoint` against the published surface artefact without trusting either the Python or the Rust implementation in isolation: the two implementations produce identical output on identical inputs.

## 8.6 Reproduction and end-to-end serve path

End-to-end reproduction is a small number of commands per stage:

```
# Train (Python, ~1 min warm cache, ~15 min cold)
uv sync
uv run python scripts/run_calibration.py

# Serve (Rust, single read)
cargo build --release -p soothsayer-publisher
./target/release/soothsayer fair-value --symbol SPY --as-of 2026-04-17 --target 0.85

# Verify Rust ↔ Python parity (~30 s)
PYTHONUNBUFFERED=1 uv run python scripts/verify_rust_oracle.py

# Deploy to devnet (after a one-time Solana + Anchor toolchain install)
./scripts/deploy_devnet.sh
```

The on-chain publish step is a separate concern handled by `soothsayer prepare-publish` (which produces the borsh-encoded `PublishPayload` bytes) plus a TypeScript signer that calls the program's `publish` instruction. The TS integration harness lives at `tests/integration.ts` and is exercised against `solana-test-validator` for local development; the devnet path is exercised by `scripts/deploy_devnet.sh`. A lending-protocol integrator wanting to consume the on-chain band depends on `soothsayer-consumer` (the `no_std` decoder) and reads the `PriceUpdate` PDA at the symbol's derived address; the demo Kamino-style consumer at `crates/soothsayer-demo-kamino/` shows the full integration in ~400 lines, including the LTV decision logic that uses the band's lower bound (the conservative reading) rather than the point estimate as the collateral valuation input.

The design of the serving stack is therefore a contract between three audiences: (a) the *researcher* iterating methodology against the Python OOS panel; (b) the *protocol integrator* building against the on-chain `PriceUpdate` accounts; and (c) the *third-party auditor* verifying that a served band corresponds to the published surface. The byte-for-byte parity contract of §8.5 makes (a) and (b) identical at the numeric level, while the receipt fields of §4.5 plus the public artefacts of §4.6 make (c) executable from public data alone.
