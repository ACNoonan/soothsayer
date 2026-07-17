# M6 LWC forward-tape OOS — 9 weekends since freeze

**Generated:** 2026-06-30 13:30 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-06-26  (n_rows = 90, n_weekends = 9).

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 90 | 0.7222 | 112.0 | 0.3845 | 0.6957 |
| 0.85 | 90 | 0.8222 | 179.2 | 0.4711 | 0.1983 |
| 0.95 | 90 | 0.9667 | 312.1 | 0.4411 | 0.4391 |
| 0.99 | 90 | 1.0000 | 517.0 | 0.1786 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 9 | 0.0000 | 0.3366 | nan | nan |
| GLD | 9 | 0.0000 | 0.3366 | nan | nan |
| GOOGL | 9 | 0.0000 | 0.3366 | nan | nan |
| HOOD | 9 | 0.2222 | 0.0752 | nan | nan |
| MSTR | 9 | 0.1111 | 0.4653 | nan | nan |
| NVDA | 9 | 0.0000 | 0.3366 | nan | nan |
| QQQ | 9 | 0.0000 | 0.3366 | nan | nan |
| SPY | 9 | 0.0000 | 0.3366 | nan | nan |
| TLT | 9 | 0.0000 | 0.3366 | nan | nan |
| TSLA | 9 | 0.0000 | 0.3366 | nan | nan |

**Headline:** 10 / 10 symbols pass per-symbol Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 under M6, 2/10 under M5; see `reports/m6_validation.md`).

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
