# M6 LWC forward-tape OOS — 11 weekends since freeze

**Generated:** 2026-07-14 13:30 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-07-10  (n_rows = 110, n_weekends = 11).

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 110 | 0.7455 | 112.3 | 0.1330 | 0.7908 |
| 0.85 | 110 | 0.8455 | 179.2 | 0.8942 | 0.4758 |
| 0.95 | 110 | 0.9636 | 312.2 | 0.4912 | 0.3640 |
| 0.99 | 110 | 1.0000 | 515.6 | 0.1370 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 11 | 0.0000 | 0.2881 | nan | nan |
| GLD | 11 | 0.0000 | 0.2881 | nan | nan |
| GOOGL | 11 | 0.0000 | 0.2881 | nan | nan |
| HOOD | 11 | 0.1818 | 0.1157 | nan | nan |
| MSTR | 11 | 0.1818 | 0.1157 | nan | nan |
| NVDA | 11 | 0.0000 | 0.2881 | nan | nan |
| QQQ | 11 | 0.0000 | 0.2881 | nan | nan |
| SPY | 11 | 0.0000 | 0.2881 | nan | nan |
| TLT | 11 | 0.0000 | 0.2881 | nan | nan |
| TSLA | 11 | 0.0000 | 0.2881 | nan | nan |

**Headline:** 10 / 10 symbols pass per-symbol Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 under M6, 2/10 under M5; see `reports/m6_validation.md`).

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
