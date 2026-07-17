# M6 σ̂ variant comparison — forward tape, 9 weekends since freeze

**Generated:** 2026-06-30 13:30 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-06-26.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 90 | 0.7222 | 114.5 | 0.3845 | 0.6957 |
| baseline_k26 | 0.85 | 90 | 0.8556 | 185.1 | 0.8821 | 0.1628 |
| baseline_k26 | 0.95 | 90 | 0.9667 | 322.3 | 0.4411 | 0.4391 |
| baseline_k26 | 0.99 | 90 | 1.0000 | 564.3 | 0.1786 | nan |
| ewma_hl6 | 0.68 | 90 | 0.7333 | 113.2 | 0.2702 | 0.1551 |
| ewma_hl6 | 0.85 | 90 | 0.8222 | 180.3 | 0.4711 | 0.1983 |
| ewma_hl6 | 0.95 | 90 | 0.9667 | 309.7 | 0.4411 | 0.4391 |
| ewma_hl6 | 0.99 | 90 | 1.0000 | 533.5 | 0.1786 | nan |
| ewma_hl8 (canonical) | 0.68 | 90 | 0.7222 | 112.0 | 0.3845 | 0.6957 |
| ewma_hl8 (canonical) | 0.85 | 90 | 0.8222 | 179.2 | 0.4711 | 0.1983 |
| ewma_hl8 (canonical) | 0.95 | 90 | 0.9667 | 312.1 | 0.4411 | 0.4391 |
| ewma_hl8 (canonical) | 0.99 | 90 | 1.0000 | 517.0 | 0.1786 | nan |
| ewma_hl12 | 0.68 | 90 | 0.7111 | 109.9 | 0.5231 | 0.6601 |
| ewma_hl12 | 0.85 | 90 | 0.8222 | 174.9 | 0.4711 | 0.1983 |
| ewma_hl12 | 0.95 | 90 | 0.9667 | 294.9 | 0.4411 | 0.4391 |
| ewma_hl12 | 0.99 | 90 | 1.0000 | 513.7 | 0.1786 | nan |
| blend_a50_hl8 | 0.68 | 90 | 0.7222 | 112.0 | 0.3845 | 0.6957 |
| blend_a50_hl8 | 0.85 | 90 | 0.8333 | 181.3 | 0.6626 | 0.2659 |
| blend_a50_hl8 | 0.95 | 90 | 0.9667 | 314.1 | 0.4411 | 0.4391 |
| blend_a50_hl8 | 0.99 | 90 | 1.0000 | 522.5 | 0.1786 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 114.5 | 185.1 | 322.3 | 564.3 |
| ewma_hl6 | 113.2 | 180.3 | 309.7 | 533.5 |
| ewma_hl8 (canonical) | 112.0 | 179.2 | 312.1 | 517.0 |
| ewma_hl12 | 109.9 | 174.9 | 294.9 | 513.7 |
| blend_a50_hl8 | 112.0 | 181.3 | 314.1 | 522.5 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.7222 | 0.8556 | 0.9667 | 1.0000 |
| ewma_hl6 | 0.7333 | 0.8222 | 0.9667 | 1.0000 |
| ewma_hl8 (canonical) | 0.7222 | 0.8222 | 0.9667 | 1.0000 |
| ewma_hl12 | 0.7111 | 0.8222 | 0.9667 | 1.0000 |
| blend_a50_hl8 | 0.7222 | 0.8333 | 0.9667 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
