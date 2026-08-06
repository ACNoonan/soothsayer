# M6 LWC forward-tape OOS — 13 weekends since freeze

**Generated:** 2026-07-28 13:30 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-07-24  (n_rows = 130, n_weekends = 13).

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 130 | 0.7462 | 111.3 | 0.0987 | 0.6834 |
| 0.85 | 130 | 0.8692 | 177.1 | 0.5316 | 0.7745 |
| 0.95 | 130 | 0.9692 | 308.6 | 0.2802 | 0.4469 |
| 0.99 | 130 | 1.0000 | 506.0 | 0.1060 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 13 | 0.0000 | 0.2482 | nan | nan |
| GLD | 13 | 0.0000 | 0.2482 | nan | nan |
| GOOGL | 13 | 0.0000 | 0.2482 | nan | nan |
| HOOD | 13 | 0.1538 | 0.1627 | nan | nan |
| MSTR | 13 | 0.1538 | 0.1627 | nan | nan |
| NVDA | 13 | 0.0000 | 0.2482 | nan | nan |
| QQQ | 13 | 0.0000 | 0.2482 | nan | nan |
| SPY | 13 | 0.0000 | 0.2482 | nan | nan |
| TLT | 13 | 0.0000 | 0.2482 | nan | nan |
| TSLA | 13 | 0.0000 | 0.2482 | nan | nan |

**Headline:** 10 / 10 symbols pass per-symbol Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 under M6, 2/10 under M5; see `reports/m6_validation.md`).

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
