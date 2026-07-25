# Handoff — pre-open commitment (next task on the verifier track)

> **STATUS: IMPLEMENTED 2026-07-24** (same day, later session). Shipped: `scripts/emit_band_commitments.py` (friday/monday modes, honesty guards), `scripts/run_band_commitment.sh`, two launchd plists (`launchd/com.adamnoonan.soothsayer.band-{commit,preopen}.plist`), `data/band_archive/commitments_v1.csv` schema, `soothsayer-verify commitment` + pending-row tolerance in `coverage`. Validated against weekend 2026-07-17: committed widths match the retro archive **bit-exactly**; Monday-replay bands match to print precision. See the 2026-07-24 methodology entry. **Remaining:** launchd activation decision (auto-push on/off — Adam's call), T3-lite factor replay in the verifier, `--truth-csv`, capture-time truth record + `--explain-deltas`, scryer wishlist ask for an early-Monday equities-daily run (unblocks MSTR pre-open). The sections below are retained as the design record.

**Written 2026-07-24.** For the next agent picking up the paper→product verifier track. Read chain: `STATUS.md` (verifier workstream row) → `reports/active/verifier_cli_scope.md` (**§11 is binding design law**) → `crates/soothsayer-verify/README.md` → `reports/methodology_history.md` 2026-07-21 entry.

## Why this task is next

Scope doc §11.1: the calibration audit decomposes into timing / coverage / derivation, and **timing is the load-bearing check** — a band publicly timestamped *before* the outcome needs no derivation-verification at all (the conformal guarantee is on coverage of pre-committed intervals). Today every archive row is `provenance=retro_frozen` (computed after outcomes from the SHA-stamped 2026-05-04 freeze — honest, but it leaves a "trust that the emitter ran the frozen formula" link). Pre-open commitment removes that link for every weekend going forward. Sequencing decision (§11.2, STATUS row): this comes **before** the coverage dashboard and before any T3 work.

## What to build

M6 factorisation makes this cheap: half-width `q_eff · σ̂ · fri_close` is fully determined at **Friday close**; only the band center moves with weekend futures until **Monday pre-open**.

1. **Friday post-close emission** — new script (suggest `scripts/emit_band_commitments.py`): per symbol, write `data/band_archive/commitments_v1.csv`: `weekend_date, symbol, fri_close, sigma_hat, regime_code, tau, half_width_bps, half_width_abs, artefact_sha256, computed_ts`. Everything is computable at Friday close from scryer parquet via `soothsayer.backtest.frozen_serving` — **reuse that module; do not reimplement the serving formula** (it exists precisely so serving paths can't drift).
2. **Monday pre-open emission** — append full band rows to `bands_v1.csv` with `provenance=published_pre_open` (the column and both values already exist; see `data/band_archive/README.md`). Point = `fri_close × (1 + factor_ret)` with factor inputs read from scryer (`cme/intraday_1m` + vol indices), same construction as the panel builder.
3. **Timestamping** — the public clock is a git commit + push right after each emission. ⚠️ **Convention change needing Adam's explicit sign-off:** the forward-tape harness deliberately does NOT git-commit (Adam reviews and phase-commits manually). Auto-commit/push for commitment rows is the whole point of the feature, but do not wire it without asking him first. Interim alternative: OpenTimestamps the row hashes and let Adam push manually.
4. **Scheduling** — launchd plists (Adam's hard preference; never Claude-side schedulers): Friday ~18:00 ET and Monday ~09:15 ET. **Verify scryer freshness at those wall-clock times before trusting the schedule** — pattern in `scripts/check_scryer_freshness.py` / `check_forward_partitions.py`. Empirically confirm `cme/intraday_1m`'s forward cursor lands by 09:15 ET Monday; if it doesn't, the Monday emission needs its own poll-and-wait pre-flight (root cause of the 2026-05-04 empty-tape incident — see harness header comments).
5. **Verifier side** (`crates/soothsayer-verify`) — a `commitment` command (or `coverage` extension): (a) Monday band half-widths match the Friday commitment rows; (b) the point replays from *public* futures data (Yahoo `ES=F` etc. — this replay lives in the crate, which IS allowed to fetch); (c) coverage as before.
6. **Known edge case you must fix:** `coverage` currently treats a missing truth bar as a hard error (exit 2). `published_pre_open` rows will exist *before* their Monday open does — the command must skip future-dated `mon_date` rows with a note instead of erroring.

## Constraints (do not violate)

- **§11.3 asymmetry rule:** external verifier signals may only move the system toward conservatism; only first-party data moves it toward confidence. No verifier write path, ever.
- **Archive is append-only.** Never edit or delete rows; a new freeze appends under its own sha.
- **Hard rule #1:** soothsayer-side emitters read scryer parquet only. The direct-fetch exception is confined to `crates/soothsayer-verify` (recorded in methodology history 2026-07-21).
- Hashes always full-length — never transcribe truncated identifiers.
- Phase commits by concern, one push at the end. **No Claude Co-Authored-By trailers on this repo.**
- `PriceUpdate` wire format untouched (consumer contract).

## Gotchas already solved — reuse, don't rediscover

- **Yahoo:** `query2.finance.yahoo.com/v8/finance/chart/` with the browser-shaped UA in `crate::http::USER_AGENT` (tool-shaped UAs get HTML error pages); 429s on bursts → pacing + 5/15/30 s backoff already in `truth.rs`.
- **Artefact hash** is a canonical-JSON self-hash (Python `json.dumps` sort_keys + compact + `ensure_ascii`, self-sha field excluded) — reproduced in `artefact.rs::canonical_json`. Exponent-notation floats would diverge; none exist in current artefacts.
- **Truth revisions are real:** AAPL 2026-07-06 open was revised by Yahoo from 4.6 bps inside the τ=0.68 edge to outside (report 33 vs live 34 violations, no verdict change). ±1-row deltas on edge-marginal rows are expected audit behaviour, documented in the crate README. Optional add-ons from the same discussion (scope doc, unbuilt): capture-time truth companion record + `--explain-deltas`, marginal-row verdict-sensitivity, `--truth-csv` for partner-supplied truth.
- **Stats parity:** any change to statistics requires regenerating the fixture (`uv run python scripts/gen_verify_parity_fixture.py`) and `cargo test -p soothsayer-verify` (tolerance ≤1e-9 vs scipy).

## State as of 2026-07-24

- Shipped: band archive (480 `retro_frozen` rows, 12 weekends) + emitter as harness step [6/6]; `soothsayer-verify` v0.1/v0.2 (`coverage`/`receipt`/`artefact`), all tests green, end-to-end run consistent at every τ.
- Untested: `receipt` against a live devnet account — no `PriceUpdate` account exists yet (publish→read-back wiring is a separate TODO, `docs/devnet-quickstart.md`).
- **A parallel Paper 1 workstream is in flight** (coverage-inversion restructure: `archive-v1/` renames staged, `rewrite/` edits, W10/W12 scripts, rebuilt PDF). Do not touch `research/coverage-inversion/`, `landing/`, `reports/active/validation_backlog.md`, or the staged renames — they belong to that session.
