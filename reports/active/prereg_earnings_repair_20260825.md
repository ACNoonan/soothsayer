# PREREG — what the repaired `earnings_night` cell does to §6.8

**Registered 2026-08-25, before any coverage number on the repaired panel was computed.**
Author: this session. Repo has no `STRUCTURE.md`, so it is unclassified; this
card follows the repo's own `reports/active/` convention rather than a
`standard/<kind>.md` soothsayer never claimed.

## 1. Question

The paper's §6.8 reports the `earnings_night` regime at **n = 60** OOS nights.
That cell was truncated: Yahoo's earnings upstream stopped confirming sessions
in Apr–Jun 2025, so the overnight panel carried **zero** `earnings_night` rows
after 2025-05-28 despite running to 2026-04-23. The repair (EDGAR item-2.02
acceptance timestamps → `earnings.v3`) recovers 19 nights inside the paper's own
window.

**Does §6.8's printed claim survive the cell it was always supposed to have?**

## 2. What is already known, and what is not

Known before registering — do **not** count these as predictions:

- The cell goes **n = 60 → 79** inside the paper window (2023-01-01 split,
  ≤ 2026-04-23), and to 89 with the panel extended to 2026-08-20.
- The rebuilt panel reproduces the reference on every non-earnings column
  except explained residuals (8 GC=F `NaN`→value rows, 1 extra GLD 2018 row,
  and the σ̂/regime moves that are downstream of the recovered nights).
- The weekend track is **unaffected**: `earnings_night` is not a weekend regime
  (`regimes.tag` weekend mode emits `normal / long_weekend / high_vol`), and
  weekend `regime_pub` did not move. The deployed weekend artefact and its
  15-weekend forward tape are untouched by this defect.

Not yet computed, and the actual object of this card: **every coverage number
on the repaired cell.**

## 3. Arms

Each runs once, on `overnight_panel_ext_20260824.parquet`, through
`scripts/build_overnight_artefact.py` with its methodology unchanged
(split-conformal per-regime quantiles, σ̂ EWMA HL=8 with the earnings exclusion
mask, OOS-fit c(τ) bump, SPLIT_DATE 2023-01-01).

- **A1 — paper-window recomputation.** Restrict to ≤ 2026-04-23, the paper's own
  window. n = 79. This is the number §6.8 must print.
- **A2 — held-out extension.** The 65 nights 2026-04-27 → 2026-08-20 the panel
  has never contained, of which **10** are `earnings_night`.
- **A3 — weekend forward tape.** Extend 15 → 17 weekends (adds 2026-08-14,
  2026-08-21). Included for completeness; it cannot move the earnings claim.

## 4. Criteria, fixed now

**A1 — the printed claim.** §6.8 currently states `earnings_night` realises
`0.767 / 0.967 / 0.983 / 1.000` at τ ∈ {0.68, 0.85, 0.95, 0.99} on n = 60, calls
the upper anchors *over*-coverage, and reports τ = 0.85 as a Kupiec rejection
(p ≈ 0.003, 2 misses where 9 were expected).

- **SURVIVES** — the cell still over-covers at τ ∈ {0.85, 0.95, 0.99}, and
  Kupiec still rejects at τ = 0.85 (p < 0.05). §6.8 keeps its argument and
  updates its numbers and n.
- **MATERIALLY CHANGED** — the τ = 0.85 Kupiec rejection disappears (p ≥ 0.05),
  or any anchor's realised coverage crosses its nominal τ from above to below.
  §6.8's "measurably too wide" sentence must be rewritten, not just renumbered.
- **BREAKS THE PARTITION CLAIM** — realised coverage at τ = 0.95 falls **below**
  0.95. The paper claims the earnings band is "calibrated against that tail, not
  merely wide"; under-coverage on the cell that exists to prevent under-coverage
  contradicts it. This is the outcome that would stop the arXiv submission.

**A2 — held-out extension.** n = 10 earnings nights. **Pre-committed: we will
not run per-anchor Kupiec on n = 10 and report it as evidence.** At τ = 0.95
exact calibration expects 0.5 misses across 10 nights, so no outcome in
{0, 1, 2} misses distinguishes anything. A2 is reported as counts — violations
observed against violations expected, per anchor — and labelled descriptive. It
may **not** be cited as confirmation in the paper. Registering this now because
"10/10 covered" is exactly the sentence a small cell tempts you into.

**A3 — weekend tape.** Pooled Kupiec p ≥ 0.05 at all four anchors and per-symbol
10/10 at τ = 0.95, matching the standing harness criteria. Any anchor below
0.05 is a finding about the weekend track and is reported whether or not it
suits the paper.

## 5. Preconditions — Gate 2

Each names what a failure would have looked like. A check that cannot fail is
not evidence.

- **P1 — panel regression.** Rebuilt panel matches the reference on every
  non-earnings column in-window. *Would have failed if* the rebuild moved a
  price, factor or regime column. **It did fail once, usefully**: the first
  rebuild tagged overnight rows in weekend regime mode (4,828 wrong
  `regime_pub`) and skipped the ex-div step (241 wrong `mon_open`).
- **P2 — every recovered night has a filing behind it.** Each `earnings_night`
  row in the paper window traces to an 8-K accession number. *Would fail if* the
  EDGAR join leaked a date-discovery match; a row with no accession is a phantom.
- **P3 — no phantom dates.** No `earnings_night` falls on an item-2.02 filing
  that did not already match a known earnings date. *Would fail on* TSLA's
  quarterly delivery 8-Ks (09:0x ET, also item 2.02) — 8 such filings exist in
  this window and must all be absent.
- **P4 — σ̂ mask applied.** σ̂ built with `sigma_exclude_mask_col=
  "earnings_next_week"`. *Would fail if* σ̂ matches an unmasked build; omitting
  the mask contaminates scale (+32% GOOGL, +23% NVDA) and fails silently in the
  safe-looking direction.
- **P5 — negative control, already run.** The confirmation-health guard must
  still **reject** the old v2 path. Measured: v2 → 0.16 confirmed fraction
  (5/31), raises; v3 → 1.00 (24/24), passes. A guard that passed on both would
  be measuring nothing.

## 6. What either outcome means

- **SURVIVES** → §6.8 is renumbered on n = 79, the truncation is disclosed as a
  data-provenance note rather than a caveat on the result, and the arXiv
  submission proceeds.
- **MATERIALLY CHANGED** → §6.8's argument is rewritten on the repaired cell.
  Still publishable; the paper gets a better number and an honest history.
- **BREAKS** → the submission stops until the earnings band is re-fit. Publishing
  a partition claim the repaired data contradicts is the one thing this paper's
  framing cannot survive.

No outcome here is a reason not to publish the repair itself. The truncation and
its fix get disclosed either way.

---

# RESULT — 2026-08-25

Run once, as registered. Panel `overnight_panel_ext_20260824.parquet` /
`v1b_panel_ext_20260824.parquet`; methodology unchanged from
`build_overnight_artefact.py`; split 2023-01-01; train n = 16,093.

## Preconditions — 5/5 pass

| | check | result |
|---|---|---|
| P1 | non-earnings columns match reference | pass, **after failing once**: the first rebuild tagged overnight rows in weekend regime mode (4,828 wrong `regime_pub`) and skipped ex-div (241 wrong `mon_open`) |
| P2 | every `earnings_night` row has an 8-K behind it | 0 of 79 rows without an accession number |
| P3 | no phantom item-2.02 date reached the cell | 28 phantom filings in window, 0 leaked |
| P4 | σ̂ built with the earnings exclusion mask | stored σ̂ == masked build 23,193/23,193; differs from unmasked on 12,577 rows; omitting it would inflate σ̂ by 37.0% MSTR / 34.2% GOOGL / 22.3% NVDA and 0.0% on the four ETFs |
| P5 | confirmation guard still rejects v2 | v2 → 0.16 (5/31), raises; v3 → 1.00 (24/24), passes |

## A1 — paper window, repaired cell. **Verdict: SURVIVES.**

`earnings_night`, OOS 2023-01-01 → 2026-04-23:

| τ | paper (n=60) | repaired (n=79) | misses | expected | Kupiec p |
|---|---|---|---:|---:|---:|
| 0.68 | 0.767 | **0.7975** | 16 | 25.3 | 0.0197 |
| 0.85 | 0.967 | **0.9747** | 2 | 11.9 | 0.0002 |
| 0.95 | 0.983 | **0.9873** | 1 | 4.0 | 0.0707 |
| 0.99 | 1.000 | **1.0000** | 0 | 0.8 | 0.2076 |

Registered criteria applied:

- Over-covers at τ ∈ {0.85, 0.95, 0.99} — **yes** (0.9747 > 0.85, 0.9873 > 0.95, 1.0000 > 0.99).
- Kupiec still rejects at τ = 0.85 — **yes**, p = 0.0002, stronger than the paper's ≈0.003.
- τ = 0.95 below nominal (the stop condition) — **no**, 0.9873 ≥ 0.95.

**One change §6.8 must make beyond renumbering.** The paper says "**Two** of these
cells are honestly *significant* over-coverage". At n = 79 it is **three**:
τ = 0.68 now rejects at p = 0.0197, where at n = 60 it did not. The extra
nights sharpened the paper's own honest residual rather than softening it.

Pooled OOS is unaffected: `ALL` realises 0.6806 / 0.8502 / 0.9510 / 0.9927
(Kupiec 0.9150 / 0.9583 / 0.7095 / 0.0214).

## A2 — held-out extension, 65 nights (2026-04-27 → 2026-08-20)

`earnings_night` n = 10: misses 2 / 0 / 0 / 0 against 3.2 / 1.5 / 0.5 / 0.1
expected. **Descriptive only, as pre-committed.** No per-anchor Kupiec on this
cell is cited, and this may not appear in the paper as confirmation.

**Not pre-registered, and reported because it is real:** pooled over all 650
held-out rows, **τ = 0.68 under-covers — 0.6246 against 0.68, Kupiec p = 0.0028**,
while τ = 0.85 / 0.95 / 0.99 hold (0.8277 / 0.9492 / 0.9938; p = 0.1182 /
0.9285 / 0.2887). The `high_vol` cell is the worst of it (0.4211 at τ = 0.68,
0.5789 at τ = 0.85) but carries only n = 19. This was not a registered test and
is a candidate for follow-up, not a finding to lean on.

## A3 — weekend forward tape, 15 → 17 weekends. **Pass.**

Frozen artefact `7b86d17a7691…`, cutoff 2026-04-24, scored on 170 rows /
17 weekends (2026-05-01 → 2026-08-21):

| τ | realised | half-width | misses | expected | Kupiec p |
|---|---|---:|---:|---:|---:|
| 0.68 | 0.6941 | 112.4 bps | 52 | 54.4 | 0.6920 |
| 0.85 | 0.8588 | 178.4 bps | 24 | 25.5 | 0.7453 |
| 0.95 | 0.9647 | 310.8 bps | 6 | 8.5 | 0.3541 |
| 0.99 | 1.0000 | 504.7 bps | 0 | 1.7 | 0.0645 |

Per-symbol Kupiec at τ = 0.95: **10/10**. Registered criteria met at every
anchor. τ = 0.99 at p = 0.0645 is the closest to the line and is zero-miss, so
it will fall below 0.05 on continued zero misses — worth watching, not yet a
finding.

**Note on the VIX feed.** The weekend artefact trained on Yahoo VIX and the
forward tape is built with CBOE. Checked: the two feeds do not flip a single
weekend `high_vol` assignment, and the artefact reads VIX only through
`regime_pub`, so the divergence is inert for A3.
