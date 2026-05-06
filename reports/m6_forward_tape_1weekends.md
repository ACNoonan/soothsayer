# M6 LWC forward-tape OOS — 1 weekends since freeze

**Generated:** 2026-05-05 13:30 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-05-01  (n_rows = 10, n_weekends = 1).

> **Preliminary** — fewer than 4 forward weekends accumulated; treat the headline as anecdotal until ≥ 4 weekends land. Per-symbol Kupiec is uninformative at this n.

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 10 | 1.0000 | 108.1 | 0.0055 | nan |
| 0.85 | 10 | 1.0000 | 169.8 | 0.0714 | nan |
| 0.95 | 10 | 1.0000 | 295.7 | 0.3111 | nan |
| 0.99 | 10 | 1.0000 | 464.7 | 0.6539 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 1 | 0.0000 | 0.7487 | nan | nan |
| GLD | 1 | 0.0000 | 0.7487 | nan | nan |
| GOOGL | 1 | 0.0000 | 0.7487 | nan | nan |
| HOOD | 1 | 0.0000 | 0.7487 | nan | nan |
| MSTR | 1 | 0.0000 | 0.7487 | nan | nan |
| NVDA | 1 | 0.0000 | 0.7487 | nan | nan |
| QQQ | 1 | 0.0000 | 0.7487 | nan | nan |
| SPY | 1 | 0.0000 | 0.7487 | nan | nan |
| TLT | 1 | 0.0000 | 0.7487 | nan | nan |
| TSLA | 1 | 0.0000 | 0.7487 | nan | nan |

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
