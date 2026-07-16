# Gap-tail statistics for §1 / H1 (K1 sub-claim: the window is large)

**Generated:** 2026-07-16, from `data/processed/v1b_panel.parquet` (5,996 weekend
rows, 10 symbols × 639 weekends, 2014–2026) and `data/processed/overnight_panel.parquet`
(22,624 rows). Computation: `|mon_open / fri_close − 1|` in bps; no filtering.
Rerun snippet lives in git history of this file's generating session; one-liner:
`pd.read_parquet(...); mv = (df.mon_open/df.fri_close - 1).abs()*1e4`.

## Row-level |close→open| move distribution (bps)

| Panel | n | median | p90 | p95 | p99 | p99.9 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Weekend | 5,996 | 51 | 209 | 319 | 732 | 1,487 | 2,737 |
| Overnight | 22,624 | 46 | 180 | 270 | 615 | 1,211 | 2,615 |

## Exceedance shares (row-level)

| Threshold | Weekend | Overnight |
|---|---:|---:|
| >100 bps | 27.6% | 23.2% |
| >300 bps | 5.6% | 4.2% |
| >500 bps | 2.2% | 1.5% |
| >1,000 bps | 0.5% | 0.2% |

## Per-weekend worst-symbol view (639 weekends, max |move| across the 10 symbols)

| Threshold | Share of weekends |
|---|---:|
| ≥1 symbol >300 bps | 30.8% |
| ≥1 symbol >500 bps | **13.8%** |
| ≥1 symbol >1,000 bps | 3.1% |

## Usage notes for the §1 writer

- **The anchor juxtaposition (guardrail-compliant):** state as two adjacent facts —
  (a) the bounded-deviation off-hours feed enforces a fixed ±500 bps clamp around
  Friday close (feed mechanics, documented); (b) on 13.8% of the 639 panel weekends
  — about one weekend in seven — at least one of the ten underlyings moved beyond
  500 bps (market measurement). Do NOT write "the clamp failed" or attribute a
  coverage claim; the juxtaposition carries it.
- Weekend tails are uniformly fatter than overnight (p99: 732 vs 615 bps) — supports
  the weekend-first presentation, overnight as generalization.
- The earnings-night tail multiplier (~8× normal-night scale) is NOT recomputed
  here — cite the §4.3.1/fig11 value; verification of §6.8 earnings-night numbers
  against the post-earnings.v2 artefact is a separate pre-pass item.
- These are underlier moves (NYSE/Nasdaq opens as target), consistent with the
  paper's calibration target scoping (§5.1).
