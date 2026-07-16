# M6 σ̂ variant comparison — forward tape, 11 weekends since freeze

**Generated:** 2026-07-14 13:30 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-07-10.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 110 | 0.7364 | 114.5 | 0.1972 | 0.8381 |
| baseline_k26 | 0.85 | 110 | 0.8727 | 184.6 | 0.4949 | 0.3550 |
| baseline_k26 | 0.95 | 110 | 0.9636 | 321.5 | 0.4912 | 0.3640 |
| baseline_k26 | 0.99 | 110 | 1.0000 | 562.4 | 0.1370 | nan |
| ewma_hl6 | 0.68 | 110 | 0.7545 | 113.8 | 0.0861 | 0.4125 |
| ewma_hl6 | 0.85 | 110 | 0.8455 | 180.6 | 0.8942 | 0.4758 |
| ewma_hl6 | 0.95 | 110 | 0.9636 | 310.4 | 0.4912 | 0.3640 |
| ewma_hl6 | 0.99 | 110 | 1.0000 | 536.3 | 0.1370 | nan |
| ewma_hl8 (canonical) | 0.68 | 110 | 0.7455 | 112.3 | 0.1330 | 0.7908 |
| ewma_hl8 (canonical) | 0.85 | 110 | 0.8455 | 179.2 | 0.8942 | 0.4758 |
| ewma_hl8 (canonical) | 0.95 | 110 | 0.9636 | 312.2 | 0.4912 | 0.3640 |
| ewma_hl8 (canonical) | 0.99 | 110 | 1.0000 | 515.6 | 0.1370 | nan |
| ewma_hl12 | 0.68 | 110 | 0.7273 | 109.6 | 0.2810 | 0.7681 |
| ewma_hl12 | 0.85 | 110 | 0.8455 | 174.4 | 0.8942 | 0.4758 |
| ewma_hl12 | 0.95 | 110 | 0.9636 | 293.6 | 0.4912 | 0.3640 |
| ewma_hl12 | 0.99 | 110 | 1.0000 | 510.2 | 0.1370 | nan |
| blend_a50_hl8 | 0.68 | 110 | 0.7455 | 112.0 | 0.1330 | 0.7908 |
| blend_a50_hl8 | 0.85 | 110 | 0.8545 | 180.9 | 0.8933 | 0.5595 |
| blend_a50_hl8 | 0.95 | 110 | 0.9636 | 312.8 | 0.4912 | 0.3640 |
| blend_a50_hl8 | 0.99 | 110 | 1.0000 | 520.7 | 0.1370 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 114.5 | 184.6 | 321.5 | 562.4 |
| ewma_hl6 | 113.8 | 180.6 | 310.4 | 536.3 |
| ewma_hl8 (canonical) | 112.3 | 179.2 | 312.2 | 515.6 |
| ewma_hl12 | 109.6 | 174.4 | 293.6 | 510.2 |
| blend_a50_hl8 | 112.0 | 180.9 | 312.8 | 520.7 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.7364 | 0.8727 | 0.9636 | 1.0000 |
| ewma_hl6 | 0.7545 | 0.8455 | 0.9636 | 1.0000 |
| ewma_hl8 (canonical) | 0.7455 | 0.8455 | 0.9636 | 1.0000 |
| ewma_hl12 | 0.7273 | 0.8455 | 0.9636 | 1.0000 |
| blend_a50_hl8 | 0.7455 | 0.8545 | 0.9636 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
