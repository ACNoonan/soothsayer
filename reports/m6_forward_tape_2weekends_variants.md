# M6 σ̂ variant comparison — forward tape, 2 weekends since freeze

**Generated:** 2026-05-12 13:30 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-05-08.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

> **Preliminary** — fewer than 4 forward weekends accumulated; treat the comparison as anecdotal until ≥ 4 weekends land. Per-variant Christoffersen and Kupiec are uninformative at this n.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 20 | 0.9000 | 109.4 | 0.0197 | nan |
| baseline_k26 | 0.85 | 20 | 1.0000 | 173.6 | 0.0108 | nan |
| baseline_k26 | 0.95 | 20 | 1.0000 | 291.4 | 0.1520 | nan |
| baseline_k26 | 0.99 | 20 | 1.0000 | 495.0 | 0.5261 | nan |
| ewma_hl6 | 0.68 | 20 | 0.9000 | 107.3 | 0.0197 | nan |
| ewma_hl6 | 0.85 | 20 | 0.9500 | 170.0 | 0.1543 | nan |
| ewma_hl6 | 0.95 | 20 | 1.0000 | 291.2 | 0.1520 | nan |
| ewma_hl6 | 0.99 | 20 | 1.0000 | 479.9 | 0.5261 | nan |
| ewma_hl8 (canonical) | 0.68 | 20 | 0.9000 | 106.3 | 0.0197 | nan |
| ewma_hl8 (canonical) | 0.85 | 20 | 0.9500 | 166.9 | 0.1543 | nan |
| ewma_hl8 (canonical) | 0.95 | 20 | 1.0000 | 290.7 | 0.1520 | nan |
| ewma_hl8 (canonical) | 0.99 | 20 | 1.0000 | 456.9 | 0.5261 | nan |
| ewma_hl12 | 0.68 | 20 | 0.9000 | 103.7 | 0.0197 | nan |
| ewma_hl12 | 0.85 | 20 | 0.9500 | 160.6 | 0.1543 | nan |
| ewma_hl12 | 0.95 | 20 | 1.0000 | 269.2 | 0.1520 | nan |
| ewma_hl12 | 0.99 | 20 | 1.0000 | 444.1 | 0.5261 | nan |
| blend_a50_hl8 | 0.68 | 20 | 0.9000 | 107.3 | 0.0197 | nan |
| blend_a50_hl8 | 0.85 | 20 | 0.9500 | 169.6 | 0.1543 | nan |
| blend_a50_hl8 | 0.95 | 20 | 1.0000 | 291.9 | 0.1520 | nan |
| blend_a50_hl8 | 0.99 | 20 | 1.0000 | 457.6 | 0.5261 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 109.4 | 173.6 | 291.4 | 495.0 |
| ewma_hl6 | 107.3 | 170.0 | 291.2 | 479.9 |
| ewma_hl8 (canonical) | 106.3 | 166.9 | 290.7 | 456.9 |
| ewma_hl12 | 103.7 | 160.6 | 269.2 | 444.1 |
| blend_a50_hl8 | 107.3 | 169.6 | 291.9 | 457.6 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.9000 | 1.0000 | 1.0000 | 1.0000 |
| ewma_hl6 | 0.9000 | 0.9500 | 1.0000 | 1.0000 |
| ewma_hl8 (canonical) | 0.9000 | 0.9500 | 1.0000 | 1.0000 |
| ewma_hl12 | 0.9000 | 0.9500 | 1.0000 | 1.0000 |
| blend_a50_hl8 | 0.9000 | 0.9500 | 1.0000 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
