# M6 LWC forward-tape OOS — 12 weekends since freeze

**Generated:** 2026-07-22 02:56 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-07-17  (n_rows = 120, n_weekends = 12).

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 120 | 0.7250 | 111.8 | 0.2841 | 0.6696 |
| 0.85 | 120 | 0.8583 | 178.2 | 0.7967 | 0.6606 |
| 0.95 | 120 | 0.9667 | 310.5 | 0.3737 | 0.4081 |
| 0.99 | 120 | 1.0000 | 510.8 | 0.1204 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 12 | 0.0000 | 0.2672 | nan | nan |
| GLD | 12 | 0.0000 | 0.2672 | nan | nan |
| GOOGL | 12 | 0.0000 | 0.2672 | nan | nan |
| HOOD | 12 | 0.1667 | 0.1384 | nan | nan |
| MSTR | 12 | 0.1667 | 0.1384 | nan | nan |
| NVDA | 12 | 0.0000 | 0.2672 | nan | nan |
| QQQ | 12 | 0.0000 | 0.2672 | nan | nan |
| SPY | 12 | 0.0000 | 0.2672 | nan | nan |
| TLT | 12 | 0.0000 | 0.2672 | nan | nan |
| TSLA | 12 | 0.0000 | 0.2672 | nan | nan |

**Headline:** 10 / 10 symbols pass per-symbol Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 under M6, 2/10 under M5; see `reports/m6_validation.md`).

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
