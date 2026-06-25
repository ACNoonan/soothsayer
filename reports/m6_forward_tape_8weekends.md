# M6 LWC forward-tape OOS — 8 weekends since freeze

**Generated:** 2026-06-25 20:10 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-06-18  (n_rows = 80, n_weekends = 8).

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 80 | 0.7000 | 112.6 | 0.6997 | 0.2331 |
| 0.85 | 80 | 0.8125 | 180.6 | 0.3627 | 0.1982 |
| 0.95 | 80 | 0.9625 | 314.4 | 0.5921 | 0.3715 |
| 0.99 | 80 | 1.0000 | 523.9 | 0.2048 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 8 | 0.0000 | 0.3650 | nan | nan |
| GLD | 8 | 0.0000 | 0.3650 | nan | nan |
| GOOGL | 8 | 0.0000 | 0.3650 | nan | nan |
| HOOD | 8 | 0.2500 | 0.0577 | nan | nan |
| MSTR | 8 | 0.1250 | 0.4092 | nan | nan |
| NVDA | 8 | 0.0000 | 0.3650 | nan | nan |
| QQQ | 8 | 0.0000 | 0.3650 | nan | nan |
| SPY | 8 | 0.0000 | 0.3650 | nan | nan |
| TLT | 8 | 0.0000 | 0.3650 | nan | nan |
| TSLA | 8 | 0.0000 | 0.3650 | nan | nan |

**Headline:** 10 / 10 symbols pass per-symbol Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 under M6, 2/10 under M5; see `reports/m6_validation.md`).

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
