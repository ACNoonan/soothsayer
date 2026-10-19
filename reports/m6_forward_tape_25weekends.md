# M6 LWC forward-tape OOS — 25 weekends since freeze

**Generated:** 2026-10-19 15:22 UTC.
**Frozen artefact:** `lwc_artefact_v1_frozen_20260504.json` (SHA-256 `7b86d17a7691…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-10-16  (n_rows = 250, n_weekends = 25).

## 1. Pooled OOS at every served τ

| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|
| 0.68 | 250 | 0.6800 | 109.1 | 1.0000 | 0.9686 |
| 0.85 | 250 | 0.8680 | 173.5 | 0.4174 | 0.8147 |
| 0.95 | 250 | 0.9680 | 302.2 | 0.1632 | 0.9148 |
| 0.99 | 250 | 0.9960 | 493.1 | 0.2781 | 0.7680 |

## 2. Per-symbol diagnostics at τ = 0.95

| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |
|---|---:|---:|---:|---:|---:|
| AAPL | 25 | 0.0400 | 0.8124 | nan | nan |
| GLD | 25 | 0.0400 | 0.8124 | nan | nan |
| GOOGL | 25 | 0.0400 | 0.8124 | nan | nan |
| HOOD | 25 | 0.0800 | 0.5251 | nan | nan |
| MSTR | 25 | 0.1200 | 0.1698 | nan | nan |
| NVDA | 25 | 0.0000 | 0.1093 | nan | nan |
| QQQ | 25 | 0.0000 | 0.1093 | nan | nan |
| SPY | 25 | 0.0000 | 0.1093 | nan | nan |
| TLT | 25 | 0.0000 | 0.1093 | nan | nan |
| TSLA | 25 | 0.0000 | 0.1093 | nan | nan |

**Headline:** 10 / 10 symbols pass per-symbol Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 under M6, 2/10 under M5; see `reports/m6_validation.md`).

## 3. Reproducibility

```bash
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_evaluation.py
```

The frozen artefact is read-only. To advance the freeze date (after a planned methodology refresh), re-run `scripts/freeze_lwc_artefact.py` with a new `--date` and re-run the harness.
