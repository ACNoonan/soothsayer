# M6 LWC forward-tape OOS — 3 weekends since freeze

**Generated:** 2026-05-26 13:30 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-05-15  (n_rows = 30, n_weekends = 3).

> **Preliminary** — fewer than 4 forward weekends accumulated; treat the headline as anecdotal until ≥ 4 weekends land. Per-symbol Kupiec is uninformative at this n.

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 30 | 0.8667 | 104.6 | 0.0179 | 0.0625 |
| 0.85 | 30 | 0.9000 | 164.2 | 0.4188 | 0.0959 |
| 0.95 | 30 | 1.0000 | 286.0 | 0.0794 | nan |
| 0.99 | 30 | 1.0000 | 449.6 | 0.4374 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 3 | 0.0000 | 0.5791 | nan | nan |
| GLD | 3 | 0.0000 | 0.5791 | nan | nan |
| GOOGL | 3 | 0.0000 | 0.5791 | nan | nan |
| HOOD | 3 | 0.0000 | 0.5791 | nan | nan |
| MSTR | 3 | 0.0000 | 0.5791 | nan | nan |
| NVDA | 3 | 0.0000 | 0.5791 | nan | nan |
| QQQ | 3 | 0.0000 | 0.5791 | nan | nan |
| SPY | 3 | 0.0000 | 0.5791 | nan | nan |
| TLT | 3 | 0.0000 | 0.5791 | nan | nan |
| TSLA | 3 | 0.0000 | 0.5791 | nan | nan |

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
