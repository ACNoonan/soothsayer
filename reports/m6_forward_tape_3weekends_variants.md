# M6 σ̂ variant comparison — forward tape, 3 weekends since freeze

**Generated:** 2026-05-26 13:30 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-05-15.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

> **Preliminary** — fewer than 4 forward weekends accumulated; treat the comparison as anecdotal until ≥ 4 weekends land. Per-variant Christoffersen and Kupiec are uninformative at this n.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 30 | 0.8667 | 108.4 | 0.0179 | 0.0625 |
| baseline_k26 | 0.85 | 30 | 0.9333 | 172.1 | 0.1580 | nan |
| baseline_k26 | 0.95 | 30 | 1.0000 | 288.8 | 0.0794 | nan |
| baseline_k26 | 0.99 | 30 | 1.0000 | 490.7 | 0.4374 | nan |
| ewma_hl6 | 0.68 | 30 | 0.8333 | 105.1 | 0.0563 | 0.0625 |
| ewma_hl6 | 0.85 | 30 | 0.9000 | 166.5 | 0.4188 | 0.0959 |
| ewma_hl6 | 0.95 | 30 | 1.0000 | 285.2 | 0.0794 | nan |
| ewma_hl6 | 0.99 | 30 | 1.0000 | 470.0 | 0.4374 | nan |
| ewma_hl8 (canonical) | 0.68 | 30 | 0.8667 | 104.6 | 0.0179 | 0.0625 |
| ewma_hl8 (canonical) | 0.85 | 30 | 0.9000 | 164.2 | 0.4188 | 0.0959 |
| ewma_hl8 (canonical) | 0.95 | 30 | 1.0000 | 286.0 | 0.0794 | nan |
| ewma_hl8 (canonical) | 0.99 | 30 | 1.0000 | 449.6 | 0.4374 | nan |
| ewma_hl12 | 0.68 | 30 | 0.8667 | 102.6 | 0.0179 | 0.2500 |
| ewma_hl12 | 0.85 | 30 | 0.9000 | 158.7 | 0.4188 | 0.0959 |
| ewma_hl12 | 0.95 | 30 | 1.0000 | 266.2 | 0.0794 | nan |
| ewma_hl12 | 0.99 | 30 | 1.0000 | 439.1 | 0.4374 | nan |
| blend_a50_hl8 | 0.68 | 30 | 0.8667 | 106.0 | 0.0179 | 0.0625 |
| blend_a50_hl8 | 0.85 | 30 | 0.9000 | 167.5 | 0.4188 | 0.0959 |
| blend_a50_hl8 | 0.95 | 30 | 1.0000 | 288.3 | 0.0794 | nan |
| blend_a50_hl8 | 0.99 | 30 | 1.0000 | 451.9 | 0.4374 | nan |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 108.4 | 172.1 | 288.8 | 490.7 |
| ewma_hl6 | 105.1 | 166.5 | 285.2 | 470.0 |
| ewma_hl8 (canonical) | 104.6 | 164.2 | 286.0 | 449.6 |
| ewma_hl12 | 102.6 | 158.7 | 266.2 | 439.1 |
| blend_a50_hl8 | 106.0 | 167.5 | 288.3 | 451.9 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.8667 | 0.9333 | 1.0000 | 1.0000 |
| ewma_hl6 | 0.8333 | 0.9000 | 1.0000 | 1.0000 |
| ewma_hl8 (canonical) | 0.8667 | 0.9000 | 1.0000 | 1.0000 |
| ewma_hl12 | 0.8667 | 0.9000 | 1.0000 | 1.0000 |
| blend_a50_hl8 | 0.8667 | 0.9000 | 1.0000 | 1.0000 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
