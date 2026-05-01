# Phase 1 Week 1 — Rust Oracle scaffold + byte-for-byte parity

**Date:** 2026-04-24
**Status:** Rust serving layer live, Python parity verified on 105/105 test cases

> **Storage-path note (2026-04-29).** This report preserves the Week 1 engineering snapshot. Where it discusses a future "live data fetcher," the current architecture is now Scryer-first: Soothsayer consumes parquet from `SCRYER_DATASET_ROOT` rather than fetching from `src/soothsayer/sources/yahoo.py` or other deleted Soothsayer-side source modules.

## What shipped

### New crates

- **`crates/soothsayer-oracle`** — serving-layer library. Loads the Python-produced calibration artifacts (`v1b_bounds.parquet`, `v1b_calibration_surface.csv`, `v1b_calibration_surface_pooled.csv`) and implements `Oracle::fair_value` with the same hybrid regime + empirical-buffer + surface-inversion logic as `src/soothsayer/oracle.py`.
- **`crates/soothsayer-publisher`** — CLI binary named `soothsayer` with `fair-value`, `list-available`, and `info` subcommands. Entry point for Week 2's on-chain publisher.

### Split-by-function architecture (locked in)

Per the 2026-04-24 decision: Python is the reference implementation that produces static artifacts; Rust consumes those artifacts and serves. No model logic is duplicated — Python produces the calibration surface and bounds table once offline via `scripts/run_calibration.py`; Rust reads them.

```
Python (model/train)                    Rust (serve)
───────────────────────                ──────────────────
run_calibration.py                      soothsayer-oracle
  └─> v1b_bounds.parquet         ──>       └─> Oracle::fair_value()
  └─> v1b_calibration_surface.csv           (hybrid + buffer + inversion)
  └─> v1b_calibration_surface_pooled.csv
                                          soothsayer-publisher (CLI)
                                          [Week 2: + Anchor program]
```

The Python `Oracle` stays in the repo as the canonical spec. A change to the inversion algorithm goes through Python, is validated via backtest, then is ported to Rust. The verification script below enforces this contract.

## Byte-for-byte parity verification

`scripts/verify_rust_oracle.py` runs both implementations on the same (symbol, fri_ts, target) triples and diffs output JSON.

**Last run: 105/105 cases pass.** The test covers:

- A deterministic sample of 30 random (symbol, fri_ts) pairs from the bounds table
- Explicit edge cases: SPY, GLD, TLT, MSTR, HOOD at their most-recent Friday
- Three targets each: 0.68, 0.95, 0.99

**Matching rules:**

- Consumer-facing numeric fields (`point`, `lower`, `upper`, `claimed_coverage_served`, `sharpness_bps`, `half_width_bps`) — **exact match required** (`tol=0`)
- Diagnostic intermediates (e.g. `requested_claimed_pre_clip`) — tolerated within `1e-12` (1 ULP of machine precision; operation-ordering differences between Python and Rust can produce ≤2.22e-16 deltas)
- String fields (`regime`, `forecaster_used`, `calibration`) — exact match required

**Sample representative output (SPY 2026-04-17, target=0.95):**

| Field | Python | Rust |
|---|---|---|
| point | 700.0755895327402 | 700.0755895327402 |
| lower | 687.2102286091069 | 687.2102286091069 |
| upper | 712.9409504563733 | 712.9409504563733 |
| claimed_coverage_served | 0.99 | 0.99 |
| sharpness_bps | 181.16653981260782 | 181.16653981260782 |
| regime | "normal" | "normal" |
| forecaster_used | "F1_emp_regime" | "F1_emp_regime" |

## Performance characteristics

| Mode | Avg per-call time | Notes |
|---|---|---|
| Rust CLI, cold (new process each call) | ~17 ms | Binary startup + artifact load dominates |
| Python CLI-equivalent (one interpreter, 10 warm calls) | ~25 ms total ≈ 2.5 ms/call | Interpreter overhead dominates |
| Rust release binary size | 15 MB | Self-contained; ready for deployment |

The cold-start ~17ms includes loading a 10 MB parquet (137K rows) and two CSVs on every invocation. For production this becomes a long-running service (HTTP/gRPC; Week 2) that loads artifacts once and serves at ~microseconds per call.

## What this unblocks

- **Week 2 (on-chain publisher):** Rust binary exists; adds Ed25519 signing, Solana RPC client, and Anchor program writes. The `fair-value` CLI subcommand becomes a `publish` subcommand.
- **Week 3 (Kamino-fork demo):** The demo's oracle consumer reads from a Solana account populated by the publisher; the same Rust binary can drive the publish side.
- **Week 4 (x402 premium endpoint):** HTTP server scaffolded on top of the Rust `Oracle`; serves richer decomposition (per-regime surface slice, α/β/γ components) from the same in-memory state.

## What's NOT done (Week 1.5 + scope calls)

The current Rust Oracle serves **historical Fridays in the bounds table only** — i.e., Fridays from 2015-01-02 through the last successful `run_calibration.py` end date (currently 2026-04-17). This meets the Week 1 exit criterion ("any Friday ≥ 2020") since the bounds table covers 2015+.

What's explicitly not yet built:

1. **Rust live data consumer / Scryer bridge** — now understood as a Scryer-backed path that reads fresh Friday-close inputs from the canonical parquet dataset rather than reintroducing a Soothsayer-side Yahoo / Kraken / Helius fetcher. Needed for a "current weekend" serve that consumes fresh Friday-close data and runs the model online. Scope: ~1 week, covers Week 1.5 or Week 2.
2. **Rust forecaster fit** — port of `empirical_quantiles_f1_loglog` + Gaussian bounds for F0. Needed if we want the Rust binary to produce bounds for a brand-new Friday independently of Python. Scope: ~3–5 days.
3. **Rolling calibration rebuild cron** — periodically re-run `scripts/run_calibration.py` to extend the bounds table through the latest completed weekend. Production deployment would run this weekly. Scope: ~1 day (it's already scriptable).

**Pragmatic Week 2 plan:** items (1) and (3) land during Week 2's on-chain publisher work. Item (2) stays Python-only — the Rust binary pulls fresh calibration artifacts from the rolling rebuild, it doesn't refit the model in process. Matches the architecture decision.

## Current artifacts on disk

```
crates/
  soothsayer-core/           (pre-existing, unchanged)
  soothsayer-ingest/         (historical note: removed in the April 2026 scryer cutover)
  soothsayer-oracle/         NEW — serving-layer library
    src/
      config.rs              REGIME_FORECASTER, CALIBRATION_BUFFER_PCT, MAX_SERVED_TARGET
      error.rs               OracleError + Result alias
      types.rs               PricePoint, PricePointDiagnostics, Regime
      surface.rs             CalibrationSurface + PooledSurface + invert_with_fallback
      oracle.rs              Oracle::load, ::fair_value, ::list_available
      lib.rs                 public exports
  soothsayer-publisher/      NEW — CLI binary
    src/main.rs              `soothsayer fair-value` / `list-available` / `info`

scripts/
  verify_rust_oracle.py      NEW — byte-for-byte parity check, 105 cases
```

## Week 2 readiness check

Prerequisites for starting Week 2 (on-chain publisher + Anchor program):

- [x] Rust Oracle compiles, serves, byte-for-byte matches Python
- [x] CLI binary exists as the entry-point scaffold
- [x] V5 tape daemon running (PID per `/tmp/v5_tape.pid`); will have ≥1 month of data by Week 3
- [x] [H3 - Publishing Surface] decided (standalone Anchor program, Switchboard fallback per 2026-04-24 Project Plan edit)
- [ ] Anchor program scaffold (Week 2 deliverable)
- [ ] Live Yahoo equivalent in Rust (Week 2 parallel deliverable)

All Week 1 exit criteria met. Week 2 can start.
