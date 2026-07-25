# W17 — promotion gate: W16 recommendation in the deployed configuration

**Run 2026-07-25.** Runner `scripts/run_paper1_w17_promotion_gate.py`; tables `reports/tables/w17_promotion_gate{,_by_regime}.csv`.

Every W10–W16 arm suppressed δ and omitted c(τ) to isolate one knob at a time. This is the gate that asks whether the W16 recommendation survives the configuration actually served.

**One caveat dissolved rather than needing a test.** δ is all-zero under M6 (`oracle.LWC_DELTA_SHIFT_SCHEDULE`), so "δ suppressed" *was already* the deployed configuration. The only real difference is c(τ).

**And c(τ) is the right adversary for this gate.** It is fitted OOS as the smallest `c ≥ 1` reaching pooled coverage τ, so it can only widen, and it is a single **global** scalar with no per-cell channel. If W13/W14/W15 were merely compensating for something c(τ) also fixes, their per-regime gains should evaporate here.

## Weekend — W13 + W14

| arm | τ | c(τ) | realised | half-width | per-symbol | per-regime |
|---|---:|---:|---:|---:|---:|---:|
| deployed | 0.95 | **1.079** | 0.9503 | 370.6 | 10/10 | 3/3 |
| **W16 rec** | 0.95 | **1.021** | 0.9503 | **351.9** | 10/10 | **4/4** |
| deployed | 0.99 | 1.003 | 0.9902 | 635.0 | 10/10 | 3/3 |
| W16 rec | 0.99 | **1.000** | 0.9902 | 641.8 | 10/10 | **4/4** |

**Passes, and the c(τ) movement is the informative part.** The recommendation needs *less* global correction — 1.079 → 1.021 at τ = 0.95, and exactly identity at τ = 0.99. c(τ) was partly papering over a conditional failure it had no channel to fix properly; giving the triple-witching cell its own quantile and stabilising it with shrinkage removes the need.

Result: **5.0% tighter at τ = 0.95** (370.6 → 351.9 bps), per-regime 4/4 including the new cell, per-symbol unchanged at 10/10, identical pooled coverage. The `triple_witching` cell reaches 0.923 with Kupiec p = 0.190 — a clean pass, where without c(τ) it sat at p = 0.047.

## Overnight — W15

| arm | τ | c(τ) | realised | half-width | per-symbol | per-regime |
|---|---:|---:|---:|---:|---:|---:|
| deployed | 0.68 | 1.019 | 0.6800 | 114.8 | 9/10 | 2/3 |
| **W16 rec** | 0.68 | 1.012 | 0.6802 | 114.6 | 9/10 | **3/3** |
| deployed | 0.85 | 1.000 | 0.8507 | 178.9 | 9/10 | 2/3 |
| **W16 rec** | 0.85 | 1.005 | 0.8501 | **175.7** | 9/10 | **3/3** |
| deployed | 0.95 | 1.000 | 0.9510 | 280.1 | 10/10 | 3/3 |
| **W16 rec** | 0.95 | 1.000 | 0.9507 | **277.4** | 10/10 | 3/3 |
| deployed | 0.99 | 1.000 | 0.9918 | 474.3 | 9/10 | 3/3 |
| **W16 rec** | 0.99 | 1.000 | 0.9910 | **464.9** | 9/10 | 3/3 |

**Passes.** Per-regime 2/3 → 3/3 at τ = 0.68 and 0.85, tighter at three of four anchors, pooled coverage unmoved. The `earnings_night` cell at τ = 0.85 goes from Kupiec **p = 0.003** (the one real failure W14 isolated, outside the binomial CI at n = 60) to **p = 0.253**, with the band tightening 1689 → 1293 bps.

## Verdict

**Both arms of the W16 recommendation clear the gate.** The gains are conditional, not a rediscovery of what c(τ) already does — demonstrated by c(τ) shrinking toward identity in the weekend arm rather than the gains shrinking.

Promotable, subject to the two items below.

## What still blocks promotion

1. **The adaptive state has to go on the wire.** If W15 ships overnight, a served band stops being a pure function of the frozen artefact — it becomes a function of the artefact *and* `m_{r,t}`. Design and decision in `reports/active/adaptive_state_wire_design.md`. This is a receipt and band-archive change, not just a serving change, and the calibration-transparency claim depends on getting it right.
2. **Under-powered cells remain under-powered.** `earnings_night` OOS n = 60, `triple_witching` n = 130. The gate improves the *point* estimates and the Kupiec verdicts, but the binomial CIs at those sizes are wide (W14) and only the forward tape resolves them — at four triple-witching weekends per year.

## Residual not addressed

Overnight per-symbol sits at **9/10** at τ = 0.68, 0.85 and 0.99 for *both* arms. That is a pre-existing gap this workstream did not target and W15 does not close; it is not a regression. Worth a separate look before the overnight panel's per-symbol claim is stated as strongly as the weekend's.
