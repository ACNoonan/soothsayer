# M6 LWC forward-tape OOS — 2 weekends since freeze

**Generated:** 2026-05-12 13:30 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-05-08  (n_rows = 20, n_weekends = 2).

> **Preliminary** — fewer than 4 forward weekends accumulated; treat the headline as anecdotal until ≥ 4 weekends land. Per-symbol Kupiec is uninformative at this n.

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 20 | 0.9000 | 106.3 | 0.0197 | nan |
| 0.85 | 20 | 0.9500 | 166.9 | 0.1543 | nan |
| 0.95 | 20 | 1.0000 | 290.7 | 0.1520 | nan |
| 0.99 | 20 | 1.0000 | 456.9 | 0.5261 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 2 | 0.0000 | 0.6506 | nan | nan |
| GLD | 2 | 0.0000 | 0.6506 | nan | nan |
| GOOGL | 2 | 0.0000 | 0.6506 | nan | nan |
| HOOD | 2 | 0.0000 | 0.6506 | nan | nan |
| MSTR | 2 | 0.0000 | 0.6506 | nan | nan |
| NVDA | 2 | 0.0000 | 0.6506 | nan | nan |
| QQQ | 2 | 0.0000 | 0.6506 | nan | nan |
| SPY | 2 | 0.0000 | 0.6506 | nan | nan |
| TLT | 2 | 0.0000 | 0.6506 | nan | nan |
| TSLA | 2 | 0.0000 | 0.6506 | nan | nan |

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
