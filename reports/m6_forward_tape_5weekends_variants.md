# M6 σ̂ variant comparison — forward tape, 5 weekends since freeze

**Generated:** 2026-06-23 13:30 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-05-29.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 50 | 0.7600 | 108.5 | 0.2133 | 0.1410 |
| baseline_k26 | 0.85 | 50 | 0.8600 | 172.5 | 0.8416 | 0.1780 |
| baseline_k26 | 0.95 | 50 | 0.9600 | 294.1 | 0.7371 | nan |
| baseline_k26 | 0.99 | 50 | 1.0000 | 505.0 | 0.3161 | nan |
| ewma_hl6 | 0.68 | 50 | 0.7400 | 104.5 | 0.3541 | 0.1247 |
| ewma_hl6 | 0.85 | 50 | 0.8200 | 164.6 | 0.5625 | 0.2476 |
| ewma_hl6 | 0.95 | 50 | 0.9600 | 282.6 | 0.7371 | nan |
| ewma_hl6 | 0.99 | 50 | 1.0000 | 477.6 | 0.3161 | nan |
| ewma_hl8 (canonical) | 0.68 | 50 | 0.7600 | 104.5 | 0.2133 | 0.1410 |
| ewma_hl8 (canonical) | 0.85 | 50 | 0.8200 | 164.2 | 0.5625 | 0.2476 |
| ewma_hl8 (canonical) | 0.95 | 50 | 0.9600 | 286.5 | 0.7371 | nan |
| ewma_hl8 (canonical) | 0.99 | 50 | 1.0000 | 457.0 | 0.3161 | nan |
| ewma_hl12 | 0.68 | 50 | 0.7600 | 102.5 | 0.2133 | 0.2100 |
| ewma_hl12 | 0.85 | 50 | 0.8200 | 160.3 | 0.5625 | 0.2476 |
| ewma_hl12 | 0.95 | 50 | 0.9600 | 268.5 | 0.7371 | nan |
| ewma_hl12 | 0.99 | 50 | 1.0000 | 450.8 | 0.3161 | nan |
| blend_a50_hl8 | 0.68 | 50 | 0.7600 | 105.4 | 0.2133 | 0.1410 |
| blend_a50_hl8 | 0.85 | 50 | 0.8200 | 167.5 | 0.5625 | 0.2476 |
| blend_a50_hl8 | 0.95 | 50 | 0.9600 | 287.6 | 0.7371 | nan |
| blend_a50_hl8 | 0.99 | 50 | 1.0000 | 462.9 | 0.3161 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 108.5 | 172.5 | 294.1 | 505.0 |
| ewma_hl6 | 104.5 | 164.6 | 282.6 | 477.6 |
| ewma_hl8 (canonical) | 104.5 | 164.2 | 286.5 | 457.0 |
| ewma_hl12 | 102.5 | 160.3 | 268.5 | 450.8 |
| blend_a50_hl8 | 105.4 | 167.5 | 287.6 | 462.9 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.7600 | 0.8600 | 0.9600 | 1.0000 |
| ewma_hl6 | 0.7400 | 0.8200 | 0.9600 | 1.0000 |
| ewma_hl8 (canonical) | 0.7600 | 0.8200 | 0.9600 | 1.0000 |
| ewma_hl12 | 0.7600 | 0.8200 | 0.9600 | 1.0000 |
| blend_a50_hl8 | 0.7600 | 0.8200 | 0.9600 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
