# M6 σ̂ variant comparison — forward tape, 13 weekends since freeze

**Generated:** 2026-07-28 13:30 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-07-24.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 130 | 0.7385 | 113.8 | 0.1457 | 0.6824 |
| baseline_k26 | 0.85 | 130 | 0.8923 | 183.0 | 0.1582 | 0.6074 |
| baseline_k26 | 0.95 | 130 | 0.9692 | 317.0 | 0.2802 | 0.4469 |
| baseline_k26 | 0.99 | 130 | 1.0000 | 552.2 | 0.1060 | nan |
| ewma_hl6 | 0.68 | 130 | 0.7538 | 112.7 | 0.0646 | 0.3684 |
| ewma_hl6 | 0.85 | 130 | 0.8692 | 178.8 | 0.5316 | 0.7745 |
| ewma_hl6 | 0.95 | 130 | 0.9692 | 307.2 | 0.2802 | 0.4469 |
| ewma_hl6 | 0.99 | 130 | 1.0000 | 527.4 | 0.1060 | nan |
| ewma_hl8 (canonical) | 0.68 | 130 | 0.7462 | 111.3 | 0.0987 | 0.6834 |
| ewma_hl8 (canonical) | 0.85 | 130 | 0.8692 | 177.1 | 0.5316 | 0.7745 |
| ewma_hl8 (canonical) | 0.95 | 130 | 0.9692 | 308.6 | 0.2802 | 0.4469 |
| ewma_hl8 (canonical) | 0.99 | 130 | 1.0000 | 506.0 | 0.1060 | nan |
| ewma_hl12 | 0.68 | 130 | 0.7308 | 108.5 | 0.2076 | 0.6243 |
| ewma_hl12 | 0.85 | 130 | 0.8692 | 172.0 | 0.5316 | 0.7745 |
| ewma_hl12 | 0.95 | 130 | 0.9692 | 289.5 | 0.2802 | 0.4469 |
| ewma_hl12 | 0.99 | 130 | 1.0000 | 499.4 | 0.1060 | nan |
| blend_a50_hl8 | 0.68 | 130 | 0.7462 | 111.2 | 0.0987 | 0.6834 |
| blend_a50_hl8 | 0.85 | 130 | 0.8769 | 179.1 | 0.3774 | 0.8370 |
| blend_a50_hl8 | 0.95 | 130 | 0.9692 | 309.5 | 0.2802 | 0.4469 |
| blend_a50_hl8 | 0.99 | 130 | 1.0000 | 510.8 | 0.1060 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 113.8 | 183.0 | 317.0 | 552.2 |
| ewma_hl6 | 112.7 | 178.8 | 307.2 | 527.4 |
| ewma_hl8 (canonical) | 111.3 | 177.1 | 308.6 | 506.0 |
| ewma_hl12 | 108.5 | 172.0 | 289.5 | 499.4 |
| blend_a50_hl8 | 111.2 | 179.1 | 309.5 | 510.8 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.7385 | 0.8923 | 0.9692 | 1.0000 |
| ewma_hl6 | 0.7538 | 0.8692 | 0.9692 | 1.0000 |
| ewma_hl8 (canonical) | 0.7462 | 0.8692 | 0.9692 | 1.0000 |
| ewma_hl12 | 0.7308 | 0.8692 | 0.9692 | 1.0000 |
| blend_a50_hl8 | 0.7462 | 0.8769 | 0.9692 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
