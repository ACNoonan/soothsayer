# Band archive — the public served-band record

`bands_v1.csv` is the append-only public record of the bands Soothsayer's
frozen artefact serves for each closed-market weekend: one row per
(weekend, symbol, τ). It exists to be **audited**: the
`soothsayer-verify` CLI (`crates/soothsayer-verify`) reads this file,
fetches realised Monday opens independently from Yahoo, and recomputes
the coverage statistics — no Soothsayer infrastructure in the loop.

Unlike the rest of `data/`, this directory is committed.

## What the archive is (and is not)

- **Claims only.** Rows carry band edges, the point estimate, and the
  receipt fields. The realised Monday open is deliberately absent — a
  verifier must fetch truth itself, or the audit is circular.
- **Append-only.** Rows are never edited or deleted. A methodology
  refresh (new freeze) appends rows under the new `artefact_sha256`;
  old rows stand as the historical claim record.
- **Deterministic.** Every row is a pure function of (a) the frozen
  artefact JSON in `data/processed/` whose SHA-256 the row names, and
  (b) public market data. `scripts/emit_band_archive.py` regenerates
  rows bit-identically (modulo `computed_ts`).

## Column reference

| Column | Meaning |
|---|---|
| `weekend_date` | Friday (last in-market close) the band spans from |
| `mon_date` | target session date — the open the band claims to cover |
| `symbol` | underlying ticker (band targets the underlying's open, per Paper 1) |
| `tau` | target coverage τ ∈ {0.68, 0.85, 0.95, 0.99} |
| `lower`, `upper`, `point` | band edges + point estimate, absolute prices, as-traded scale at emission time |
| `half_width_bps` | (upper − lower) / 2 / fri_close × 10⁴ |
| `regime_code` | Mondrian regime cell (`normal` / `long_weekend` / `high_vol`) |
| `forecaster_code` | 3 = M6 LWC (mirrors `crates/soothsayer-consumer` codes) |
| `profile_code` | 1 = lending-track |
| `artefact_sha256` | full SHA-256 of the frozen artefact JSON that produced the row |
| `provenance` | see below |
| `computed_ts` | UTC time the row was emitted |

## Provenance — read this before trusting a row

- `retro_frozen` — the row was computed **after** the weekend outcome
  existed, by serving an artefact frozen **before** the weekend
  (SHA-stamped; freeze 2026-05-04 predates every archived weekend).
  The calibration scalars could not have been tuned to the outcome,
  but the row itself was not published pre-open. This covers the
  backfilled forward tape.
- `published_pre_open` — the row was emitted before the target open
  existed. Not yet produced; lands when archive emission is wired into
  the pre-open publisher path (ultimately anchored by an on-chain
  `publish_ts`).

**Point-construction disclosure:** `point` = Friday close × (1 + factor
return), where the factor return uses weekend futures moves through the
Monday pre-open — i.e. the band is the oracle's *pre-open* serving
state, the same object Paper 1's coverage claims are stated on. The
factor inputs are public (CME futures, vol indices); reproducing
`point` from them is the verifier's T3 tier (deferred), while T1
verifies coverage of the recorded bands as claimed.

## Truth rule for verification

Realised truth is the **regular-session opening print on `mon_date`
for `symbol`** (Yahoo daily-bar `open`, the same source/convention as
the evaluation panel). Prices are as-traded at emission time: a stock
split after `weekend_date` rescales Yahoo's historical series, so a
verifier must renormalise (multiply reported opens by the cumulative
ratio of splits dated after `mon_date`) before comparing —
`soothsayer-verify` does this automatically and discloses when it did.

## Regenerate / extend

```bash
uv run python scripts/emit_band_archive.py            # latest freeze
uv run python scripts/emit_band_archive.py --frozen-suffix 20260504
```

Runs weekly as step [6/6] of the forward-tape harness
(`scripts/run_forward_tape_harness.sh`); rows land untracked and are
committed with the weekly rollup.
