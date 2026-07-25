# M6 σ̂ variant comparison — forward tape, 12 weekends since freeze

**Generated:** 2026-07-21 13:30 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-07-17.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 120 | 0.7167 | 114.2 | 0.3840 | 0.6452 |
| baseline_k26 | 0.85 | 120 | 0.8833 | 183.9 | 0.2903 | 0.5064 |
| baseline_k26 | 0.95 | 120 | 0.9667 | 319.3 | 0.3737 | 0.4081 |
| baseline_k26 | 0.99 | 120 | 1.0000 | 557.4 | 0.1204 | nan |
| ewma_hl6 | 0.68 | 120 | 0.7333 | 113.3 | 0.2030 | 0.3418 |
| ewma_hl6 | 0.85 | 120 | 0.8583 | 179.8 | 0.7967 | 0.6606 |
| ewma_hl6 | 0.95 | 120 | 0.9667 | 308.9 | 0.3737 | 0.4081 |
| ewma_hl6 | 0.99 | 120 | 1.0000 | 531.9 | 0.1204 | nan |
| ewma_hl8 (canonical) | 0.68 | 120 | 0.7250 | 111.8 | 0.2841 | 0.6696 |
| ewma_hl8 (canonical) | 0.85 | 120 | 0.8583 | 178.2 | 0.7967 | 0.6606 |
| ewma_hl8 (canonical) | 0.95 | 120 | 0.9667 | 310.5 | 0.3737 | 0.4081 |
| ewma_hl8 (canonical) | 0.99 | 120 | 1.0000 | 510.8 | 0.1204 | nan |
| ewma_hl12 | 0.68 | 120 | 0.7083 | 109.1 | 0.5023 | 0.5764 |
| ewma_hl12 | 0.85 | 120 | 0.8583 | 173.2 | 0.7967 | 0.6606 |
| ewma_hl12 | 0.95 | 120 | 0.9667 | 291.5 | 0.3737 | 0.4081 |
| ewma_hl12 | 0.99 | 120 | 1.0000 | 504.6 | 0.1204 | nan |
| blend_a50_hl8 | 0.68 | 120 | 0.7250 | 111.7 | 0.2841 | 0.6696 |
| blend_a50_hl8 | 0.85 | 120 | 0.8667 | 180.1 | 0.6034 | 0.7377 |
| blend_a50_hl8 | 0.95 | 120 | 0.9667 | 311.2 | 0.3737 | 0.4081 |
| blend_a50_hl8 | 0.99 | 120 | 1.0000 | 515.7 | 0.1204 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 114.2 | 183.9 | 319.3 | 557.4 |
| ewma_hl6 | 113.3 | 179.8 | 308.9 | 531.9 |
| ewma_hl8 (canonical) | 111.8 | 178.2 | 310.5 | 510.8 |
| ewma_hl12 | 109.1 | 173.2 | 291.5 | 504.6 |
| blend_a50_hl8 | 111.7 | 180.1 | 311.2 | 515.7 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.7167 | 0.8833 | 0.9667 | 1.0000 |
| ewma_hl6 | 0.7333 | 0.8583 | 0.9667 | 1.0000 |
| ewma_hl8 (canonical) | 0.7250 | 0.8583 | 0.9667 | 1.0000 |
| ewma_hl12 | 0.7083 | 0.8583 | 0.9667 | 1.0000 |
| blend_a50_hl8 | 0.7250 | 0.8667 | 0.9667 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
