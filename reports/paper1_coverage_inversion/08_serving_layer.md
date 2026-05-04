# §8 — Serving-Layer System

The methodology of §4 is implemented as a four-component serving stack designed for two requirements that pull in opposite directions: (i) the model logic is research-iterated in Python and re-validated against the §6 OOS panel after every change; (ii) the production hot path is a Solana program reading bands at consumer-facing latency. This section describes how those requirements are reconciled in a single source of truth.

## 8.1 Split-by-function architecture

The serving stack is a contract between three audiences: the **researcher** iterating against the Python OOS panel, the **protocol integrator** building against on-chain `PriceUpdate` accounts, and the **third-party auditor** verifying a served band against the published artefact. Byte-for-byte parity (§8.5) makes the first two identical at the numeric level; the receipt fields and public artefacts make the third executable from public data alone. This trio is the operational instantiation of $P_1$ (auditability).

The implementation separates *training* (Python) from *serving* (Rust + Solana). The Python `Oracle` (`src/soothsayer/oracle.py`) is the canonical specification: it produces the per-Friday lookup artefact and is the executable reference for the M5 conformal-lookup algorithm. A change — a new $c(\tau)$ schedule, a per-Friday point recompute — is implemented in Python first, validated against the §6 OOS panel, and ported to Rust under the byte-for-byte parity contract of §8.5. No model logic is duplicated: the training pipeline materialises the per-Friday rows and the 20 deployment scalars once offline; the serving stack reads them. The 20 scalars are hardcoded in both `oracle.py` and `crates/soothsayer-oracle/src/config.rs` and mirrored into the JSON sidecar.

## 8.2 The Rust crate stack

| Crate | Purpose | Lines | Tests |
|---|---|---:|---:|
| `soothsayer-oracle` | Library: loads the Mondrian artefact, exposes `Oracle::fair_value` with byte-exact parity to Python | ~330 | 4/4 unit + parity harness |
| `soothsayer-publisher` | CLI binary: serves single reads, prepares on-chain publish payloads | ~440 | 6/6 unit |
| `soothsayer-consumer` | `no_std`, minimal-dep SDK: decodes the on-chain `PriceUpdate` PDA into a typed `PriceBand` | ~330 | 5/5 unit |
| `soothsayer-demo-kamino` | Reference Kamino-style consumer integration | ~400 | included in integration tests |
| `soothsayer-oracle-program` (Anchor) | On-chain program: `initialize`, `publish`, `set_paused`, `rotate_signer_set` | ~400 | scaffolded |

The consumer SDK is `no_std` so it can be vendored into a Solana program account-decoder without the Rust standard library.

## 8.3 On-chain program

`programs/soothsayer-oracle-program/` is a vanilla Anchor program with three PDA account types (`PublisherConfig`, `SignerSet`, per-symbol `PriceUpdate`) and four instructions. The `publish` instruction validates signer membership, enforces the cadence rate-limit, and checks five on-chain invariants before persisting: band ordering ($L \le \hat P \le U$), coverage values $\le 10{,}000$ bps, exponent $\in [-12, 0]$, signer membership, and time since last publish $\ge$ `min_publish_interval_secs`. Every instruction emits an Anchor event so off-chain indexers can trace publish history without re-reading every account.

## 8.4 Wire-format design

The `PriceUpdate` account layout (128 bytes data + 8-byte Anchor discriminator) is informed by the Pyth-Network September-2021 BTC flash-crash post-mortem. Three design rules avoid the failure modes that incident exposed.

```
PriceUpdate:
  version              u8         schema version, currently 1
  regime_code          u8         0=normal, 1=long_weekend, 2=high_vol
  forecaster_code      u8         0=F1_emp_regime (legacy the prior hybrid Oracle), 1=F0_stale (legacy the prior hybrid Oracle), 2=mondrian (M5 / deployed)
  exponent             i8
  target_coverage_bps  u16        consumer's request, integer bp
  claimed_served_bps   u16        served quantile, integer bp
  buffer_applied_bps   u16
  symbol               [u8; 16]   ASCII null-padded
  point, lower, upper, fri_close   i64        absolute fixed-point at `exponent`
  fri_ts, publish_ts, publish_slot, signer, signer_epoch    timestamps + identity
```

The three rules: (1) **Absolute prices, not deltas** — a consumer reading `lower` gets a real price directly. (2) **Single shared exponent** for all price fields, so cross-field comparisons are exact integer comparisons. (3) **Integer basis points, never floats** for coverage and buffer — exact and deterministic across Rust, Anchor IDL, TypeScript clients, and Python. Wire-format sizes are locked by unit tests in `crates/soothsayer-publisher/src/payload.rs`.

## 8.5 Byte-for-byte parity verification

`scripts/verify_rust_oracle.py` runs Python `Oracle.fair_value` and Rust `soothsayer fair-value` on the same `(symbol, fri_ts, target_coverage)` triples and asserts byte-exact agreement on numeric output (point, lower, upper, sharpness_bps, claimed_served, calibration_buffer_applied) plus exact agreement on string fields (regime, forecaster_used). The current panel covers 90 cases (25 random pairs from the artefact + edge cases for SPY, GLD, TLT, MSTR, HOOD at three targets each). **90/90 pass** as of the most recent re-run on M5.

The parity harness is invoked after every methodology change. The the migration from the prior hybrid Oracle to M5 was applied to Python first, then ported to Rust; the harness was re-run before the change was considered shipped. It is the contract that allows a consumer to verify a served `PricePoint` against the published artefact without trusting either implementation in isolation.

**Wire format invariance across the prior hybrid Oracle → M5.** The on-chain `PriceUpdate` Borsh layout is unchanged. The only on-wire change is relabelling the previously-reserved `forecaster_code = 2` slot to `FORECASTER_MONDRIAN`. Pre-M5 accounts decode cleanly under M5 consumers; post-M5 accounts emit code 2. Downstream consumers branching on `forecaster_code` need only add a code-2 case.

## 8.6 Reproduction

```
# Train (Python)
uv sync && uv run python scripts/build_mondrian_artefact.py

# Serve (Rust)
cargo build --release -p soothsayer-publisher
./target/release/soothsayer fair-value --symbol SPY --as-of 2026-04-24 --target 0.85

# Verify Rust ↔ Python parity
PYTHONUNBUFFERED=1 uv run python scripts/verify_rust_oracle.py

# Deploy to devnet
./scripts/deploy_devnet.sh
```

A lending-protocol integrator depends on `soothsayer-consumer` (the `no_std` decoder) and reads the `PriceUpdate` PDA at the symbol's derived address; the demo Kamino-style consumer at `crates/soothsayer-demo-kamino/` shows the full integration in ~400 lines, including LTV decision logic that uses the band's lower bound as the collateral valuation input — the third audience of §8.1 reading the same wire bytes the on-chain program emits.
