# M6 σ̂ variant comparison — forward tape, 10 weekends since freeze

**Generated:** 2026-07-09 21:48 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-07-02.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 100 | 0.7400 | 114.9 | 0.1900 | 0.7462 |
| baseline_k26 | 0.85 | 100 | 0.8600 | 185.4 | 0.7774 | 0.4338 |
| baseline_k26 | 0.95 | 100 | 0.9600 | 324.1 | 0.6350 | 0.4282 |
| baseline_k26 | 0.99 | 100 | 1.0000 | 568.4 | 0.1563 | nan |
| ewma_hl6 | 0.68 | 100 | 0.7500 | 113.9 | 0.1250 | 0.4246 |
| ewma_hl6 | 0.85 | 100 | 0.8300 | 180.8 | 0.5820 | 0.5268 |
| ewma_hl6 | 0.95 | 100 | 0.9600 | 310.9 | 0.6350 | 0.4282 |
| ewma_hl6 | 0.99 | 100 | 1.0000 | 539.7 | 0.1563 | nan |
| ewma_hl8 (canonical) | 0.68 | 100 | 0.7400 | 112.6 | 0.1900 | 0.7462 |
| ewma_hl8 (canonical) | 0.85 | 100 | 0.8300 | 179.9 | 0.5820 | 0.5268 |
| ewma_hl8 (canonical) | 0.95 | 100 | 0.9600 | 313.5 | 0.6350 | 0.4282 |
| ewma_hl8 (canonical) | 0.99 | 100 | 1.0000 | 520.1 | 0.1563 | nan |
| ewma_hl12 | 0.68 | 100 | 0.7300 | 110.0 | 0.2765 | 0.6894 |
| ewma_hl12 | 0.85 | 100 | 0.8300 | 175.5 | 0.5820 | 0.5268 |
| ewma_hl12 | 0.95 | 100 | 0.9600 | 295.6 | 0.6350 | 0.4282 |
| ewma_hl12 | 0.99 | 100 | 1.0000 | 516.0 | 0.1563 | nan |
| blend_a50_hl8 | 0.68 | 100 | 0.7400 | 112.2 | 0.1900 | 0.7462 |
| blend_a50_hl8 | 0.85 | 100 | 0.8400 | 181.7 | 0.7813 | 0.6267 |
| blend_a50_hl8 | 0.95 | 100 | 0.9600 | 314.2 | 0.6350 | 0.4282 |
| blend_a50_hl8 | 0.99 | 100 | 1.0000 | 526.0 | 0.1563 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 114.9 | 185.4 | 324.1 | 568.4 |
| ewma_hl6 | 113.9 | 180.8 | 310.9 | 539.7 |
| ewma_hl8 (canonical) | 112.6 | 179.9 | 313.5 | 520.1 |
| ewma_hl12 | 110.0 | 175.5 | 295.6 | 516.0 |
| blend_a50_hl8 | 112.2 | 181.7 | 314.2 | 526.0 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.7400 | 0.8600 | 0.9600 | 1.0000 |
| ewma_hl6 | 0.7500 | 0.8300 | 0.9600 | 1.0000 |
| ewma_hl8 (canonical) | 0.7400 | 0.8300 | 0.9600 | 1.0000 |
| ewma_hl12 | 0.7300 | 0.8300 | 0.9600 | 1.0000 |
| blend_a50_hl8 | 0.7400 | 0.8400 | 0.9600 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
