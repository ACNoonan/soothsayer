# M6 σ̂ variant comparison — forward tape, 25 weekends since freeze

**Generated:** 2026-10-19 15:22 UTC.
**Variant bundle:** `lwc_variant_bundle_v1_frozen_20260504.json` (SHA-256 `7cef6132d970…`, freeze date 2026-05-04).
**Forward window:** 2026-05-01 → 2026-10-16.

**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes the selection-procedure transparency layer — the canonical M6 σ̂ rule (EWMA HL=8) was selected from a 5-variant ladder under a multi-test-exposed criterion (80 split-date Christoffersen cells). To re-validate the selection on data it never saw, this report scores all five variants on the same forward weekends. The intent is *re-validation*, not *re-selection*: a different variant looking cleaner here is a flag to revisit, not to re-deploy.

## 1. Pooled OOS — all variants at every served τ

| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |
|---|---:|---:|---:|---:|---:|---:|
| baseline_k26 | 0.68 | 250 | 0.7040 | 111.7 | 0.4127 | 0.9949 |
| baseline_k26 | 0.85 | 250 | 0.8720 | 179.5 | 0.3196 | 0.9273 |
| baseline_k26 | 0.95 | 250 | 0.9720 | 309.5 | 0.0828 | 0.9634 |
| baseline_k26 | 0.99 | 250 | 0.9960 | 537.6 | 0.2781 | 0.7680 |
| ewma_hl6 | 0.68 | 250 | 0.6720 | 110.1 | 0.7867 | 0.2944 |
| ewma_hl6 | 0.85 | 250 | 0.8520 | 175.0 | 0.9293 | 0.8136 |
| ewma_hl6 | 0.95 | 250 | 0.9600 | 300.5 | 0.4529 | 0.9763 |
| ewma_hl6 | 0.99 | 250 | 0.9960 | 511.4 | 0.2781 | 0.7680 |
| ewma_hl8 (canonical) | 0.68 | 250 | 0.6800 | 109.1 | 1.0000 | 0.9686 |
| ewma_hl8 (canonical) | 0.85 | 250 | 0.8680 | 173.5 | 0.4174 | 0.8147 |
| ewma_hl8 (canonical) | 0.95 | 250 | 0.9680 | 302.2 | 0.1632 | 0.9148 |
| ewma_hl8 (canonical) | 0.99 | 250 | 0.9960 | 493.1 | 0.2781 | 0.7680 |
| ewma_hl12 | 0.68 | 250 | 0.6840 | 107.0 | 0.8920 | 0.8479 |
| ewma_hl12 | 0.85 | 250 | 0.8720 | 169.0 | 0.3196 | 0.9048 |
| ewma_hl12 | 0.95 | 250 | 0.9640 | 284.4 | 0.2860 | 0.9546 |
| ewma_hl12 | 0.99 | 250 | 0.9960 | 488.1 | 0.2781 | 0.7680 |
| blend_a50_hl8 | 0.68 | 250 | 0.6960 | 109.3 | 0.5859 | 0.9937 |
| blend_a50_hl8 | 0.85 | 250 | 0.8720 | 175.7 | 0.3196 | 0.8545 |
| blend_a50_hl8 | 0.95 | 250 | 0.9720 | 303.8 | 0.0828 | 0.9634 |
| blend_a50_hl8 | 0.99 | 250 | 0.9960 | 497.3 | 0.2781 | 0.7680 |

## 2. Headline comparison — variant × τ pooled half-width (bps)

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 111.7 | 179.5 | 309.5 | 537.6 |
| ewma_hl6 | 110.1 | 175.0 | 300.5 | 511.4 |
| ewma_hl8 (canonical) | 109.1 | 173.5 | 302.2 | 493.1 |
| ewma_hl12 | 107.0 | 169.0 | 284.4 | 488.1 |
| blend_a50_hl8 | 109.3 | 175.7 | 303.8 | 497.3 |

## 3. Headline comparison — realised coverage

| variant | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---:|---:|---:|---:|
| baseline_k26 | 0.7040 | 0.8720 | 0.9720 | 0.9960 |
| ewma_hl6 | 0.6720 | 0.8520 | 0.9600 | 0.9960 |
| ewma_hl8 (canonical) | 0.6800 | 0.8680 | 0.9680 | 0.9960 |
| ewma_hl12 | 0.6840 | 0.8720 | 0.9640 | 0.9960 |
| blend_a50_hl8 | 0.6960 | 0.8720 | 0.9720 | 0.9960 |

## 4. Reproducibility

```bash
uv run python scripts/freeze_sigma_ewma_variant_bundle.py
uv run python scripts/collect_forward_tape.py
uv run python scripts/run_forward_tape_variant_comparison.py
```

The variant bundle is read-only. To advance the freeze date, re-run `scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and re-run this evaluator.
