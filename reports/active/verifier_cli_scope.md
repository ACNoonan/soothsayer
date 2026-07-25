# `soothsayer-verify` — scoping doc

**Status:** IMPLEMENTED (P0 + v0.1 + v0.2) 2026-07-21 — see the decision log in §9 and the dated entry in `reports/methodology_history.md`. Crate: `crates/soothsayer-verify` (README there is the user-facing doc). Retained as the design record for the paper→product push. Sequencing per §11.2: **pre-open commitment next**, then dashboard; T3 deferred.
**Objective:** a third party runs one command and independently confirms — from data they fetch themselves — that the bands Soothsayer published achieved the coverage they claimed. "Don't trust the dashboard; run it yourself."
**Strategic anchor:** `docs/product-stack.md` §9.1 rows 1–2 (methodology + coverage receipts are *open*; auditability is the value). The verifier is the productisation of Paper 1's C3 audit-chain claim.

---

## 1. Trust model — what "verify" means, in tiers

| Tier | Claim verified | Inputs the verifier needs | Who supplies them |
|---|---|---|---|
| **T1 — Coverage audit** | "The published bands covered the realised opens at the claimed rate" (Kupiec, Christoffersen, per-symbol) | (a) band archive: `[L, U]` + receipt per (weekend, symbol, τ); (b) realised Fri-close/Mon-open truth | (a) Soothsayer publishes; (b) **verifier fetches from Yahoo itself** — independence is the point |
| **T2 — Receipt/wire audit** | "The on-chain account decodes to the same claim the archive records" (discriminator, invariants, receipt fields, artefact SHA-256) | live RPC read of the `PriceUpdate` PDA + the frozen artefact JSON | on-chain + public repo |
| **T3 — Band reproduction** | "The frozen artefact's 20 scalars + public market data deterministically reproduce the published bands" | frozen artefact + public feature inputs (futures settles, VIX/GVZ/MOVE via Yahoo) | public, but heavy — see §6 |

v0.1 ships T1. v0.2 adds T2. T3 is a stretch tier — scoped but explicitly deferred (§6).

**The independence principle (drives the language choice, §4):** the verifier must NOT reuse `src/soothsayer/backtest/metrics.py`. If the verifier imports the same statistics code the paper used, a bug self-confirms. Independent re-implementation, with a Python↔Rust parity test in CI (same culture as the 180/180 oracle parity), is a *feature* of the design, not duplicated effort.

---

## 2. Prerequisite (P0): the public band archive

**Today no served-band history exists anywhere.** `soothsayer_v5/tape` is the Chainlink/Jupiter comparison tape; the forward-tape harness recomputes bands from the frozen artefact on each fire and persists only summary tables (`reports/tables/`, gitignored). Nothing for a third party to audit.

**Fix (small):** `run_forward_tape_evaluation.py` gains a step that appends per-weekend served bands to a committed CSV:

```
data/band_archive/bands_v1.csv    # public, append-only, committed weekly
```

Schema (one row per weekend × symbol × τ — claims only, deliberately **no truth column**; the verifier fetches truth independently):

```
weekend_date, symbol, tau, lower, upper, point, half_width_bps,
regime_code, forecaster_code, profile_code, artefact_sha256, computed_ts
```

Volume: 10 symbols × 4 τ ≈ 40 rows/week — trivially committable. The harness does not git-commit (per the phase-commit convention); rows land untracked and get committed with the existing weekly rollup.

**Backfill honesty note (must appear in the archive README and verifier output):** rows for the 12 forward weekends to date are *retro-computed* from the SHA-stamped 2026-05-04 freeze, not contemporaneously published. They are still audit-grade (deterministic function of a frozen artefact that predates the outcomes), but the distinction must be disclosed: a `provenance` column with `retro_frozen` vs `published_pre_open`. Going forward, the credibility upgrade path is Friday-close emission (archive row written *before* the weekend outcome exists), eventually anchored by an on-chain `publish_ts` once the mainnet publish path is live.

---

## 3. CLI shape (v0.1–v0.2)

```
soothsayer-verify coverage [--tau 0.95] [--symbol SPY] [--since 2026-05-01]
    # T1: fetch band archive (GitHub raw URL or --archive local path),
    # fetch Mon-open truth from Yahoo, recompute violations,
    # print realised vs claimed coverage + Kupiec/Christoffersen p per τ,
    # per-symbol table. Exit 0 = consistent, 1 = coverage claim rejected,
    # 2 = data/integrity error.

soothsayer-verify receipt --account <pubkey> [--url devnet|mainnet|<rpc>]
    # T2: fetch account, verify discriminator, decode via the
    # soothsayer-consumer crate (dogfoods the consumer contract),
    # validate_invariants(), print receipt fields.

soothsayer-verify artefact --file lwc_artefact_v1_frozen_20260504.json
    # T2: recompute SHA-256, compare against the hash the archive rows
    # and reports claim.

--json on every command    # machine-readable, so a partner can wire it into CI
```

Output discipline follows the brand rules: print the caveats inline (retro-computed provenance, small-n per-symbol power, τ=0.99 finite-sample ceiling) — never a bare green checkmark.

---

## 4. Language: Rust

- **Independence** (§1): re-implement Kupiec LR, Christoffersen independence + conditional coverage, and the coverage aggregation from the paper's formulas. Chi-square CDF via `statrs`. Parity test against `metrics.py` outputs on a golden fixture becomes CI.
- **Distribution:** `cargo install soothsayer-verify` + prebuilt binaries on GitHub releases. A static binary is the right shape for the audience; `pip install` is a weaker verifier story.
- **Reuse:** `soothsayer-consumer` as a dependency for T2 decode (that's the consumer contract itself — reusing it is dogfooding, unlike the stats). `reqwest` for Yahoo `/v8/chart` + archive fetch; CSV parsing by hand or `csv` crate. No parquet dependency needed if the archive is CSV.
- Crate lives at `crates/soothsayer-verify` in the public repo (stays public durably per §9.4 — it's the L5.0 audit layer).

## 5. Hard-rule exception (needs sign-off)

CLAUDE.md rule 1: soothsayer does not call external APIs for upstream data. The verifier *by design* fetches Yahoo truth directly — fetching through scryer would defeat its purpose (a third party auditing us must not depend on our data plumbing). Proposed scoped exception:

- The exception applies to `crates/soothsayer-verify` only.
- Nothing under `src/soothsayer/` or `scripts/` may ever import/shell out to it for analysis; the analysis-side rule is unchanged.
- Documented in the crate README + a line in `reports/methodology_history.md` when the crate ships.

## 6. T3 (band reproduction) — scoped, deferred

Recomputing `[L, U]` from the frozen artefact requires the feature pipeline: per-symbol σ̂ EWMA (HL=8) from close history, factor construction from futures settles (ES/NQ/GC/ZN), vol-index regime classification (VIX/GVZ/MOVE), earnings flags. All inputs have free public proxies (Yahoo `ES=F`, `^VIX`, …) but the CME-vs-Yahoo settle mismatch and the earnings-calendar join make exact reproduction a real project (~1–2 wk) with fidelity caveats. Defer to v0.3; the T1+T2 audit chain (frozen-hash artefact → published bands → independently-fetched truth) already closes the loop that matters for LOI conversations.

## 7. Truth-rule precision (open item)

The verifier README must state the truth semantics exactly as the paper does — which print counts as "Monday open", and the split/dividend adjustment policy for Fri→Mon returns — citing the paper section rather than paraphrasing. Action: lift the precise statement from the Paper 1 methodology section / Appendix E during implementation; if the panel builder applies a corp-action adjustment the public Yahoo field doesn't, that delta must be documented (it is exactly the kind of gap a hostile verifier-runner will find).

## 8. Phasing + effort

| Phase | Deliverable | Effort |
|---|---|---|
| **P0** | Band-archive emission in the harness + backfilled 12 weekends + archive README | ~0.5–1 day |
| **v0.1** | `coverage` command end-to-end (archive fetch, Yahoo truth, stats, table/JSON, parity CI vs `metrics.py`) | ~2–4 days |
| **v0.2** | `receipt` + `artefact` commands (RPC decode, SHA check) | ~1–2 days |
| **v0.3** | T3 band reproduction | ~1–2 wk, deferred |

P0 + v0.1 + v0.2 ≈ one focused week; after that the dashboard consumes the same archive, so P0 is shared infrastructure for both halves of the "explore" package.

## 9. Decision log (2026-07-21)

1. **Rule-1 scoped exception — approved by Adam.** Confined to `crates/soothsayer-verify`; analysis code may not call into it. Recorded in `reports/methodology_history.md` and STATUS.
2. **Archive location — committed CSV in-repo** (`data/band_archive/bands_v1.csv`, exempted path under the otherwise-gitignored `data/`). HF mirror deferred until a dataset release exists to bundle it with.
3. **Rust — confirmed by Adam.** Stats re-implemented independently; parity vs scipy ≤1e-9 incl. the real 12-weekend panel (`tests/parity.rs`).
4. **Emission cadence — Tuesday harness for now** (step [6/6], fails-open, idempotent). `published_pre_open` provenance starts when a pre-open publisher path exists; the provenance column already distinguishes the two.

## 10. Implementation findings worth keeping

- **The stamped artefact hash is a canonical-JSON self-hash**, not a file hash (`freeze_lwc_artefact.py`: `sort_keys` + compact separators + `ensure_ascii` escaping, self-sha field excluded). The Rust `artefact` command reproduces it byte-exactly — including Python's `\uXXXX` escaping (the σ̂ description's λ was the divergence found in testing). Known limitation: exponent-notation floats would format differently; none appear in current artefacts.
- **Truth revision is real (§7 validated).** Live run reproduces the 12-weekend report exactly at τ ∈ {0.85, 0.95, 0.99}; at τ=0.68 one AAPL row (2026-07-06 open, 4.6 bps inside the edge at capture time) has since been revised by Yahoo to just outside — 33→34 violations of 120, no verdict change. Documented in the crate README as expected audit behaviour.
- **Yahoo operational facts:** endpoint is `query2.finance.yahoo.com/v8/finance/chart/` with a fully browser-shaped UA (tool-shaped UAs get HTML error pages); anonymous bursts get 429 — verifier paces at 300 ms/symbol and retries 5/15/30 s.

## 11. Verifier-network design principles (recorded 2026-07-24)

Captured from the post-v0.1 design discussion (truth-revision finding → distributed verifiers → feedback loops). These constrain any future "verifier network" feature — read before designing one.

### 11.1 The calibration claim decomposes into three separately-checkable parts

| Check | Proves | Status |
|---|---|---|
| **Timing** | the band existed *before* the outcome | The load-bearing check. Today proxied by the frozen-artefact hash predating outcomes + (unverified) derivation determinism; the real fix is pre-open publication with a public timestamp. |
| **Coverage** | outcomes land inside at rate τ | T1, shipped. The *ongoing scientific check on the model* — the forward-tape harness externalized so adversaries validate it for us. Never superfluous. |
| **Derivation** | band = f(frozen scalars, public data) | T3, deferred. **Only a substitute for missing timing:** once bands carry a pre-outcome public timestamp, derivation fidelity stops being an audit requirement — the conformal guarantee is on coverage of *pre-committed* intervals, not on the score function that produced them. Derivation then matters for width efficiency and confidence in future coverage, not audit validity. |

### 11.2 Pre-open commitment is the priority, and M6's factorisation makes it cheap

Half-width `q_eff · σ̂ · fri_close` is fully determined at Friday close; only the band *center* moves with weekend futures. So the commitment scheme is: **Friday commit** (per symbol: σ̂, regime, dollar half-width per τ) + **Monday pre-open commit** (point = fri_close × (1 + factor_ret), final band), each publicly timestamped (git push / OpenTimestamps / devnet publish — any public clock). The verifier then checks: half-widths match the Friday commitment; the point replays from *public futures data* (the one small T3 leg, the easiest one); the open is covered. Full audit chain at ~1/10 of full-T3 effort. The 12-weekend `retro_frozen` era stays bounded by the freeze hash; a one-time T3 replay can retire its trust-me link later. **Sequencing decision: pulled ahead of both the dashboard and T3.** *(Implemented 2026-07-24 — `scripts/emit_band_commitments.py`, `soothsayer-verify commitment`; validated bit-exact against the retro path on weekend 2026-07-17. See the methodology entry of that date.)*

### 11.3 The asymmetry rule — hard constraint on any feedback loop

**External verifier signals may only move the system toward conservatism** (alarm, dashboard flag, widen, halt-mode). **Only first-party data may move it toward confidence** (tighten, recalibrate — scryer capture and market data like the F_tok on-chain flow, which is market behaviour, not anyone's report about us).

Rationale: the moment verifier output can steer the oracle, verifiers become an oracle *input* and inherit the entire oracle threat model — corruption becomes profitable (convince the system its bands are too wide → it tightens → exploit the tightening). Under asymmetry, a corrupted or sybiled verifier can at worst cause a false alarm — griefing that temporarily widens bands: a worse product, never an unsafe one, and never false confidence. This is the watchtower / fraud-proof pattern: verifiers pull the andon cord; they do not steer the machine. Note the disclosure-boundary interaction (product-stack §9): the *response policy* to alarms is operator discretion (closed), but the *existence* of the fail-conservative rule is public — it is part of what makes the verifier network credible.

### 11.4 What a verifier network actually contributes — operational signals, not statistical ones

1. **Credibility** — the audit claim stops being self-attested.
2. **Distributed diff** — truth revisions, our capture bugs, and upstream poisoning of our own data spine. Tripwire: independent verifiers using *independent truth sources* reporting coverage failure while our harness reports a pass points the finger at our capture, not the model.
3. **Liveness / censorship monitoring** of the published feed.

The model's calibration signal was always the realised opens from first-party capture; verifier reports over the same public data add no statistical information the pipeline lacks. Design accordingly: feedback surfaces are alarms and diffs, never calibration inputs.

### 11.5 Shape of the network

A handful of **named, reputationally-staked verifiers** (a partner risk desk running `--truth-csv` against their licensed feed, an auditor, an academic group) beats an anonymous incentivised swarm: N copies of the same binary against the same Yahoo endpoint are correlated, not independent. No rewards, no tokens, no write path; permissionless to run, powerless to steer. The lightweight "network" is an attestation trail — a future `--attest` mode emitting signed result JSON, accumulating third-party signatures over the same append-only archive.
