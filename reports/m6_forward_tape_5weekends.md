# M6 LWC forward-tape OOS — 5 weekends since freeze

**Generated:** 2026-06-02 14:30 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-05-29  (n_rows = 50, n_weekends = 5).

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 50 | 0.7600 | 104.5 | 0.2133 | 0.1410 |
| 0.85 | 50 | 0.8200 | 164.2 | 0.5625 | 0.2476 |
| 0.95 | 50 | 0.9600 | 286.5 | 0.7371 | nan |
| 0.99 | 50 | 1.0000 | 457.0 | 0.3161 | nan |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 5 | 0.0000 | 0.4739 | nan | nan |
| GLD | 5 | 0.0000 | 0.4739 | nan | nan |
| GOOGL | 5 | 0.0000 | 0.4739 | nan | nan |
| HOOD | 5 | 0.2000 | 0.2371 | nan | nan |
| MSTR | 5 | 0.2000 | 0.2371 | nan | nan |
| NVDA | 5 | 0.0000 | 0.4739 | nan | nan |
| QQQ | 5 | 0.0000 | 0.4739 | nan | nan |
| SPY | 5 | 0.0000 | 0.4739 | nan | nan |
| TLT | 5 | 0.0000 | 0.4739 | nan | nan |
| TSLA | 5 | 0.0000 | 0.4739 | nan | nan |

**Headline:** 10 / 10 symbols pass per-symbol Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 under M6, 2/10 under M5; see `reports/m6_validation.md`).

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
