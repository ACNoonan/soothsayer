# M6 LWC forward-tape OOS — 10 weekends since freeze

**Generated:** 2026-07-09 21:48 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-07-02  (n_rows = 100, n_weekends = 10).

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 100 | 0.7400 | 112.6 | 0.1900 | 0.7462 |
| 0.85 | 100 | 0.8300 | 179.9 | 0.5820 | 0.5268 |
| 0.95 | 100 | 0.9600 | 313.5 | 0.6350 | 0.4282 |
| 0.99 | 100 | 1.0000 | 520.1 | 0.1563 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 10 | 0.0000 | 0.3111 | nan | nan |
| GLD | 10 | 0.0000 | 0.3111 | nan | nan |
| GOOGL | 10 | 0.0000 | 0.3111 | nan | nan |
| HOOD | 10 | 0.2000 | 0.0945 | nan | nan |
| MSTR | 10 | 0.2000 | 0.0945 | nan | nan |
| NVDA | 10 | 0.0000 | 0.3111 | nan | nan |
| QQQ | 10 | 0.0000 | 0.3111 | nan | nan |
| SPY | 10 | 0.0000 | 0.3111 | nan | nan |
| TLT | 10 | 0.0000 | 0.3111 | nan | nan |
| TSLA | 10 | 0.0000 | 0.3111 | nan | nan |

**Headline:** 10 / 10 symbols pass per-symbol Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 under M6, 2/10 under M5; see `reports/m6_validation.md`).

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
