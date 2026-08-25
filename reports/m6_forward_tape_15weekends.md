# M6 LWC forward-tape OOS — 15 weekends since freeze

**Generated:** 2026-08-11 13:30 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-08-07  (n_rows = 150, n_weekends = 15).

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 150 | 0.7467 | 109.9 | 0.0739 | 0.4521 |
| 0.85 | 150 | 0.8667 | 174.6 | 0.5613 | 0.8219 |
| 0.95 | 150 | 0.9667 | 304.2 | 0.3200 | 0.5118 |
| 0.99 | 150 | 1.0000 | 496.3 | 0.0825 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 15 | 0.0667 | 0.7776 | nan | nan |
| GLD | 15 | 0.0000 | 0.2148 | nan | nan |
| GOOGL | 15 | 0.0000 | 0.2148 | nan | nan |
| HOOD | 15 | 0.1333 | 0.2152 | nan | nan |
| MSTR | 15 | 0.1333 | 0.2152 | nan | nan |
| NVDA | 15 | 0.0000 | 0.2148 | nan | nan |
| QQQ | 15 | 0.0000 | 0.2148 | nan | nan |
| SPY | 15 | 0.0000 | 0.2148 | nan | nan |
| TLT | 15 | 0.0000 | 0.2148 | nan | nan |
| TSLA | 15 | 0.0000 | 0.2148 | nan | nan |

**Headline:** 10 / 10 symbols pass per-symbol Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 under M6, 2/10 under M5; see `reports/m6_validation.md`).

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
