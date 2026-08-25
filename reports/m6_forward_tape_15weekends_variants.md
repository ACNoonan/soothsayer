# M6 σ̂ variant comparison — forward tape, 15 weekends since freeze

**Generated:** 2026-08-11 13:30 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-08-07.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 150 | 0.7467 | 112.9 | 0.0739 | 0.4609 |
| baseline_k26 | 0.85 | 150 | 0.8867 | 181.3 | 0.1918 | 0.7836 |
| baseline_k26 | 0.95 | 150 | 0.9733 | 312.8 | 0.1516 | 0.5118 |
| baseline_k26 | 0.99 | 150 | 1.0000 | 543.3 | 0.0825 | nan |
| ewma_hl6 | 0.68 | 150 | 0.7533 | 111.2 | 0.0487 | 0.3289 |
| ewma_hl6 | 0.85 | 150 | 0.8667 | 176.3 | 0.5613 | 0.8219 |
| ewma_hl6 | 0.95 | 150 | 0.9667 | 302.8 | 0.3200 | 0.5118 |
| ewma_hl6 | 0.99 | 150 | 1.0000 | 517.2 | 0.0825 | nan |
| ewma_hl8 (canonical) | 0.68 | 150 | 0.7467 | 109.9 | 0.0739 | 0.4521 |
| ewma_hl8 (canonical) | 0.85 | 150 | 0.8667 | 174.6 | 0.5613 | 0.8219 |
| ewma_hl8 (canonical) | 0.95 | 150 | 0.9667 | 304.2 | 0.3200 | 0.5118 |
| ewma_hl8 (canonical) | 0.99 | 150 | 1.0000 | 496.3 | 0.0825 | nan |
| ewma_hl12 | 0.68 | 150 | 0.7333 | 107.3 | 0.1546 | 0.3350 |
| ewma_hl12 | 0.85 | 150 | 0.8667 | 169.6 | 0.5613 | 0.8219 |
| ewma_hl12 | 0.95 | 150 | 0.9667 | 285.3 | 0.3200 | 0.5118 |
| ewma_hl12 | 0.99 | 150 | 1.0000 | 489.6 | 0.0825 | nan |
| blend_a50_hl8 | 0.68 | 150 | 0.7467 | 110.2 | 0.0739 | 0.4521 |
| blend_a50_hl8 | 0.85 | 150 | 0.8733 | 177.0 | 0.4129 | 0.8697 |
| blend_a50_hl8 | 0.95 | 150 | 0.9667 | 305.7 | 0.3200 | 0.5118 |
| blend_a50_hl8 | 0.99 | 150 | 1.0000 | 501.5 | 0.0825 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 112.9 | 181.3 | 312.8 | 543.3 |
| ewma_hl6 | 111.2 | 176.3 | 302.8 | 517.2 |
| ewma_hl8 (canonical) | 109.9 | 174.6 | 304.2 | 496.3 |
| ewma_hl12 | 107.3 | 169.6 | 285.3 | 489.6 |
| blend_a50_hl8 | 110.2 | 177.0 | 305.7 | 501.5 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.7467 | 0.8867 | 0.9733 | 1.0000 |
| ewma_hl6 | 0.7533 | 0.8667 | 0.9667 | 1.0000 |
| ewma_hl8 (canonical) | 0.7467 | 0.8667 | 0.9667 | 1.0000 |
| ewma_hl12 | 0.7333 | 0.8667 | 0.9667 | 1.0000 |
| blend_a50_hl8 | 0.7467 | 0.8733 | 0.9667 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
