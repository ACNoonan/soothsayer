# §8 — Serving-Layer System

The methodology of §4 is implemented as a four-component serving stack designed for two requirements that pull in opposite directions: (i) the model logic is research-iterated in Python and re-validated against the §6 OOS panel after every change; (ii) the production hot path is a Solana program reading bands at consumer-facing latency. This section describes how those requirements are reconciled in a single source of truth.

## 8.1 Split-by-function architecture

The serving stack is a contract between three audiences: the **researcher** iterating against the Python OOS panel, the **protocol integrator** building against on-chain `PriceUpdate` accounts, and the **third-party auditor** verifying a served band against the published artefact. Byte-for-byte parity (§8.5) makes the first two identical at the numeric level; the receipt fields and public artefacts make the third executable from public data alone. This trio is the operational instantiation of $P_1$ (auditability).

The implementation separates *training* (Python) from *serving* (Rust + Solana). The Python `Oracle` (`src/soothsayer/oracle.py`) is the canonical specification: it produces the per-Friday lookup artefact and is the executable reference for both the M5 Mondrian conformal-lookup algorithm (`Oracle.fair_value`) and M6's locally-weighted variant (`Oracle.fair_value_lwc`). A change — a new $c(\tau)$ schedule, a per-Friday point recompute, a σ̂ rule swap — is implemented in Python first, validated against the §6 OOS panel, and ported to Rust under the byte-for-byte parity contract of §8.5. No model logic is duplicated: the training pipeline materialises the per-Friday rows (including $\hat\sigma_s(t)$ per symbol pre-Friday) and the deployment scalars once offline; the serving stack reads them. M6 carries 16 deployment scalars hardcoded in `oracle.py` and mirrored into the JSON sidecar; the M5 reference path carries 20 scalars (12 quantiles + 4 OOS-fit + 4 walk-forward) duplicated in `crates/soothsayer-oracle/src/config.rs` for the Rust serving binary.

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
  forecaster_code      u8         0=F1_emp_regime (legacy Soothsayer-v0), 1=F0_stale (legacy Soothsayer-v0), 2=mondrian (M5; live on-chain), 3=lwc (M6 / deployed; on-chain slot reserved pending Rust parity port)
  exponent             i8
  target_coverage_bps  u16        publisher-set target coverage, integer bp
  claimed_served_bps   u16        served quantile, integer bp
  buffer_applied_bps   u16
  symbol               [u8; 16]   ASCII null-padded
  point, lower, upper, fri_close   i64        absolute fixed-point at `exponent`
  fri_ts, publish_ts, publish_slot, signer, signer_epoch    timestamps + identity
```

The three rules: (1) **Absolute prices, not deltas** — a consumer reading `lower` gets a real price directly. (2) **Single shared exponent** for all price fields, so cross-field comparisons are exact integer comparisons. (3) **Integer basis points, never floats** for coverage and buffer — exact and deterministic across Rust, Anchor IDL, TypeScript clients, and Python. Wire-format sizes are locked by unit tests in `crates/soothsayer-publisher/src/payload.rs`.

## 8.5 Byte-for-byte parity verification

`scripts/verify_rust_oracle.py` runs Python `Oracle.fair_value` (M5) / `Oracle.fair_value_lwc` (M6) and the Rust `soothsayer fair-value --forecaster {mondrian, lwc}` CLI on the same `(symbol, fri_ts, target_coverage)` triples and asserts byte-exact agreement on numeric output (point, lower, upper, sharpness_bps, claimed_served, calibration_buffer_applied) plus exact agreement on string fields (regime, forecaster_used). Each forecaster's panel covers 90 cases (25 random pairs from the artefact + edge cases for SPY, GLD, TLT, MSTR, HOOD at three targets each). **180/180 pass** as of the most recent re-run — 90/90 on the M5 path and 90/90 on the M6 LWC path. The Rust crate now serves both forecasters; `forecaster_code = 3` (`FORECASTER_LWC`) is encoded into new publishes from `crates/soothsayer-publisher` and decoded into the `Forecaster::Lwc` variant by the no_std `soothsayer-consumer` crate.

The parity harness is invoked after every methodology change. Each migration is applied to Python first, then ported to Rust; the harness re-runs before the change is considered shipped. It is the contract that allows a consumer to verify a served `PricePoint` against the published artefact without trusting either implementation in isolation.

**Wire format invariance.** The on-chain `PriceUpdate` Borsh layout is unchanged across all methodology migrations to date. The only on-wire change at each step is relabelling reserved `forecaster_code` slots: code 2 → `FORECASTER_MONDRIAN` (M5; live), code 3 → `FORECASTER_LWC` (M6; live in the Rust serving stack as of the parity-180/180 milestone above; on-chain enablement gated on the next publisher release). Older accounts decode cleanly under newer consumers; M6 accounts decode cleanly under any consumer that reads the `forecaster_code` byte (`soothsayer-consumer` exposes the typed `Forecaster::Lwc` variant). Downstream consumers branching on `forecaster_code` need only add code-2 and code-3 cases.

## 8.6 Reproduction

```
# Train (Python) — M6 (deployed)
uv sync && uv run python scripts/build_lwc_artefact.py
uv run python scripts/freeze_lwc_artefact.py     # content-addressed freeze for forward-tape

# Train (Python) — M5 (still buildable as the §7.2 ablation rung)
uv run python scripts/build_mondrian_artefact.py

# Serve (Rust)
cargo build --release -p soothsayer-publisher
./target/release/soothsayer fair-value --symbol SPY --as-of 2026-04-24 --target 0.85

# Verify Rust ↔ Python parity
PYTHONUNBUFFERED=1 uv run python scripts/verify_rust_oracle.py

# Deploy to devnet
./scripts/deploy_devnet.sh
```

A lending-protocol integrator depends on `soothsayer-consumer` (the `no_std` decoder) and reads the `PriceUpdate` PDA at the symbol's derived address; the demo Kamino-style consumer at `crates/soothsayer-demo-kamino/` shows the full integration in ~400 lines, including LTV decision logic that uses the band's lower bound as the collateral valuation input — the third audience of §8.1 reading the same wire bytes the on-chain program emits.
