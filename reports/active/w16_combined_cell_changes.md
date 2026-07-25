# W16 — W13 + W14 + W15 evaluated together

**Run 2026-07-25.** Runner `scripts/run_paper1_w16_combined_cell_changes.py`; tables `reports/tables/w16_combined_cell_changes{,_by_regime}.csv`.

Three experiments each modify the per-cell conformal quantile and each was tested alone. W14 already carried the W13 cell, so W13+W14 was co-tested; what was untested was W15 on top — and there was a specific reason to suspect trouble: **shrinkage stabilises a thin cell's estimate toward a pooled shape, while adaptation moves the level period by period.** On the same thin cell they can fight.

They do.

## Weekend

| arm | per-regime pass 0.68 / 0.85 / **0.95** / 0.99 | half-width @0.95 | `triple_witching` @0.95 |
|---|---|---|---|
| base (deployed) | 2 / 2 / **3** / 3 | 343.4 | — |
| W13 | 3 / 3 / **3** / 4 | 340.2 | 0.900 |
| **W13+W14** | 3 / 3 / **4** / 4 | 344.7 | **0.923** |
| W13+W15 | 4 / 3 / **3** / 4 | 349.1 | 0.900 |
| W13+W14+W15 | 4 / 3 / **3** / 4 | 351.0 | 0.908 |

**W15 undoes W14's fix.** W13+W14 is the only arm reaching 4/4 at τ = 0.95, with the triple-witching cell at 0.923. Adding W15 pushes it back to 0.908 and 3/4, while costing width (344.7 → 351.0 bps). The mechanism is the one anticipated: the adaptive multiplier chases period-to-period noise in a 130-row OOS cell, which is precisely the noise shrinkage was introduced to suppress.

W13+W15 picks up a pass at τ = 0.68 and loses one at 0.95. Total passes across anchors tie at 14, but τ = 0.95 is the headline anchor and the one the paper leads with, so the tie is not a wash.

## Overnight

| arm | per-regime 0.68 / 0.85 / 0.95 / 0.99 | per-symbol | half-width @0.95 |
|---|---|---|---|
| base | 2 / 2 / 3 / 3 | 9 / 9 / 10 / 9 | 280.1 |
| W14 | 2 / 2 / 3 / 3 | 9 / 9 / 10 / 9 | 280.0 |
| **W15** | **3 / 3 / 3 / 3** | 9 / **10** / 10 / 9 | **277.4** |
| W14+W15 | 3 / 3 / 3 / 3 | 9 / 10 / 10 / 9 | 278.1 |

**W15 alone is best.** W14 adds nothing here — consistent with W14's own finding that the overnight problem is drift, not thinness — and combining the two costs a little width without buying a pass.

The `earnings_night` cell confirms the mechanism. At τ = 0.85 the base arm realises 0.967 against a claimed 0.85, which W14 established is a *real* over-coverage failure (outside the binomial CI at n = 60). W15 moves it to 0.900, inside the CI, and that is where the τ = 0.85 per-regime pass comes from. At τ = 0.68 both arms sit inside the CI (0.733 base, 0.617 with W15), so the movement there is noise in both directions.

## Recommended configuration

| panel | adopt | reject | why |
|---|---|---|---|
| **weekend** | **W13 + W14** | W15 | The weekend cells are *noisy*, not drifting (W14). Shrinkage suppresses noise; adaptation amplifies it. |
| **overnight** | **W15** | W13, W14 | Triple witching is a weekend event. The overnight failure is *drift*, which only adaptation repairs. |

The split is panel-specific but not arbitrary — each component is matched to the diagnosis that motivated it. W13 adds a cell for a real hole; W14 repairs estimation noise in a thin cell; W15 repairs drift in a well-estimated one. Applying a remedy to the panel whose failure it does not address is at best inert (W14 overnight) and at worst harmful (W15 weekend).

**This is the reason the three could not be promoted independently.** Read in isolation, each experiment says "adopt". Read together, one pairing is actively harmful.

## Still open before any of this touches the artefact

1. **Deployed configuration.** Every arm here suppresses δ and omits c(τ). Re-run with both active before promotion; a c(τ) bump can only widen and may absorb part of what W14 supplies.
2. **`m_{r,t}` becomes live state.** If W15 ships overnight, a served band stops being a pure function of the frozen artefact. It must go in the receipt and the band archive, with a checkpoint cadence, or the calibration-transparency claim weakens. This is a wire-format and audit-story change, not just a serving change.
3. **Under-powered cells.** `earnings_night` OOS n = 60 and `triple_witching` n = 130. Several distinctions above sit inside binomial noise at those sizes and are labelled accordingly; the forward tape is the only thing that resolves them, at 4 triple-witching weekends per year.
4. **k and γ are plateaus, not optima.** k ≈ 200 and γ ≈ 0.05 were selected as flat regions on this OOS slice, not tuned out-of-sample. A single best value chosen here would be an oracle choice.
5. **Nothing here is in the deployed artefact.** The two-sided frozen artefact and its forward tape are untouched, deliberately — see `w4_one_sided_bands.md` for the same reasoning applied to the one-sided profile.
