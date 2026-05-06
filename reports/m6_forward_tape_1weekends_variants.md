# M6 σ̂ variant comparison — forward tape, 1 weekends since freeze

**Generated:** 2026-05-05 13:30 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-05-01.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

> **Preliminary** — fewer than 4 forward weekends accumulated; treat the comparison as anecdotal until ≥ 4 weekends land. Per-variant Christoffersen and Kupiec are uninformative at this n.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 10 | 1.0000 | 110.0 | 0.0055 | nan |
| baseline_k26 | 0.85 | 10 | 1.0000 | 174.5 | 0.0714 | nan |
| baseline_k26 | 0.95 | 10 | 1.0000 | 292.9 | 0.3111 | nan |
| baseline_k26 | 0.99 | 10 | 1.0000 | 497.6 | 0.6539 | nan |
| ewma_hl6 | 0.68 | 10 | 1.0000 | 109.7 | 0.0055 | nan |
| ewma_hl6 | 0.85 | 10 | 1.0000 | 173.8 | 0.0714 | nan |
| ewma_hl6 | 0.95 | 10 | 1.0000 | 297.8 | 0.3111 | nan |
| ewma_hl6 | 0.99 | 10 | 1.0000 | 490.7 | 0.6539 | nan |
| ewma_hl8 (canonical) | 0.68 | 10 | 1.0000 | 108.1 | 0.0055 | nan |
| ewma_hl8 (canonical) | 0.85 | 10 | 1.0000 | 169.8 | 0.0714 | nan |
| ewma_hl8 (canonical) | 0.95 | 10 | 1.0000 | 295.7 | 0.3111 | nan |
| ewma_hl8 (canonical) | 0.99 | 10 | 1.0000 | 464.7 | 0.6539 | nan |
| ewma_hl12 | 0.68 | 10 | 0.9000 | 105.0 | 0.0992 | nan |
| ewma_hl12 | 0.85 | 10 | 1.0000 | 162.5 | 0.0714 | nan |
| ewma_hl12 | 0.95 | 10 | 1.0000 | 272.4 | 0.3111 | nan |
| ewma_hl12 | 0.99 | 10 | 1.0000 | 449.4 | 0.6539 | nan |
| blend_a50_hl8 | 0.68 | 10 | 1.0000 | 108.5 | 0.0055 | nan |
| blend_a50_hl8 | 0.85 | 10 | 1.0000 | 171.5 | 0.0714 | nan |
| blend_a50_hl8 | 0.95 | 10 | 1.0000 | 295.1 | 0.3111 | nan |
| blend_a50_hl8 | 0.99 | 10 | 1.0000 | 462.7 | 0.6539 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 110.0 | 174.5 | 292.9 | 497.6 |
| ewma_hl6 | 109.7 | 173.8 | 297.8 | 490.7 |
| ewma_hl8 (canonical) | 108.1 | 169.8 | 295.7 | 464.7 |
| ewma_hl12 | 105.0 | 162.5 | 272.4 | 449.4 |
| blend_a50_hl8 | 108.5 | 171.5 | 295.1 | 462.7 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| ewma_hl6 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| ewma_hl8 (canonical) | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| ewma_hl12 | 0.9000 | 1.0000 | 1.0000 | 1.0000 |
| blend_a50_hl8 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
