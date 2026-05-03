# v3 methodology bake-off — C1 / C2 / C4 vs M5

Date: 2026-05-03
Decision recorded: see `methodology_history.md` 2026-05-03 entry.
Backlog entry: `VALIDATION_BACKLOG.md` W9.

## Question

The §10 robustness pass localised M5's residual rejection to two sources:
(A) per-symbol residual-scale heterogeneity (bimodal Berkowitz, per-symbol
Kupiec failures on HOOD/MSTR/TSLA), and (B) cross-sectional within-weekend
common-mode ($\hat\rho_\text{cross} = 0.354$). Three candidate
methodologies attack (A); none attack (B) directly. Run a head-to-head
against M5 to inform the v3 roadmap.

## Variants

| Variant | Score | Cell | Serve formula |
|---|---|---|---|
| **M5 baseline** | $|y - \hat p| / p_\text{Fri}$ | regime_pub (3) | $q(\tau) \cdot c(\tau) \cdot p_\text{Fri}$ |
| **C1 LWC + regime** | $|y - \hat p| / (p_\text{Fri} \cdot \hat\sigma_\text{sym}(t))$ | regime_pub (3) | $q(\tau) \cdot c(\tau) \cdot p_\text{Fri} \cdot \hat\sigma_\text{sym}(t)$ |
| **C2 M6b2 class** | $|y - \hat p| / p_\text{Fri}$ | symbol_class (6) | $q(\tau) \cdot c(\tau) \cdot p_\text{Fri}$ |
| **C4 stacked** | $|y - \hat p| / (p_\text{Fri} \cdot \hat\sigma_\text{sym}(t))$ | symbol_class (6) | $q(\tau) \cdot c(\tau) \cdot p_\text{Fri} \cdot \hat\sigma_\text{sym}(t)$ |

$\hat\sigma_\text{sym}(t)$ = trailing K=26 weekends standard deviation of
relative residual for that symbol, computed strictly from $\text{fri\_ts}'
< \text{fri\_ts}$, requiring $\ge 8$ past observations. Symbol-class
mapping from the deployed M6b2 lending sidecar (`equity_index` /
`equity_meta` / `equity_highbeta` / `equity_recent` / `gold` / `bond`).
$\delta$-shift schedule held at zero across all variants for fair
comparison; $c(\tau)$ refit on OOS per variant.

Same train/OOS split (2023-01-01), same four served τ. After the σ̂ filter,
panel is 5,916 rows × 631 weekends (4,186 train / 1,730 OOS); 80 rows
dropped at the σ̂ warm-up boundary.

## Headline at τ = 0.95 (pooled)

| Variant | Realised | HW (bps) | Δ vs M5 | Kupiec p | $c(\tau)$ |
|---|---:|---:|---:|---:|---:|
| M5 baseline | 0.9503 | 354.9 | — | 0.956 | 1.303 |
| **C1 LWC + regime** | 0.9503 | 385.3 | **+8.6%** | 0.956 | 1.069 |
| **C2 M6b2 class** | 0.9503 | **302.6** | **−14.7%** | 0.956 | 1.040 |
| C4 stacked | 0.9555 | 379.6 | +7.0% | 0.286 | 1.000 |

## Per-symbol Kupiec at τ = 0.95

| Variant | n_pass(p ≥ 0.05) | Worst p (symbol) | viol_rate range |
|---|---:|---|---|
| M5 | **2/10** | $\approx 0$ (SPY) | 0.000 (SPY) – 0.150 (MSTR) |
| **C1 LWC + regime** | **10/10** | 0.168 (QQQ) | 0.029 – 0.069 |
| C2 M6b2 class | 8/10 | 0.023 (NVDA, SPY tied) | 0.017 – 0.081 |
| C4 stacked | 9/10 | 0.021 (GLD) | 0.035 – 0.092 |

Full per-symbol p-value and violation-rate matrix:
`reports/tables/v3_bakeoff_per_symbol.csv`.

## Mechanism (Berkowitz LR + cross-sectional ρ on PITs)

| Variant | Berkowitz LR | $\hat\rho_\text{cross}$ | $\hat\sigma^2_z$ |
|---|---:|---:|---:|
| M5 baseline | 159.1 | 0.252 | 0.787 |
| C1 LWC + regime | 175.2 | 0.249 | 0.754 |
| C2 M6b2 class | 172.6 | 0.259 | 0.773 |
| C4 stacked | 227.3 | 0.280 | 0.717 |

**None of C1 / C2 / C4 reduce $\hat\rho_\text{cross}$.** All four variants
sit in the same neighbourhood (0.249 – 0.280). The cross-sectional
common-mode residual is orthogonal to the per-symbol scale story; addressing
it requires a partial-out track (M6a) which is independently gated.

C1's Berkowitz LR is *higher* than M5's despite better per-symbol
calibration: LWC tightens $\hat\sigma^2_z$ (0.787 → 0.754, PITs cluster
more around 0.5 because bands are slightly wider on average) but doesn't
touch ρ_cross, so the AR(1) component dominates more in the joint LR.

## Reading

C1 and C2 sit on a Pareto frontier:

- **C1 (LWC + regime)** wins per-symbol calibration (10/10, viol_rates
  2.9–6.9% around nominal 5%). Pays $+8.6\%$ on width. The natural
  candidate for any consumer who reads "calibrated band" as a per-symbol
  claim, not just a pooled claim.
- **C2 (M6b2 class)** wins sharpness ($-14.7\%$). 8/10 per-symbol Kupiec
  pass; the failures (NVDA $p = 0.023$, SPY $p = 0.023$) are *too-wide*
  failures from intra-class heterogeneity (SPY more compact than QQQ
  within `equity_index`; NVDA more compact than TSLA/MSTR within
  `equity_highbeta`). The natural candidate for lending consumers who
  buffer asymmetric LTV and care about sharpness.
- **C4 (stacked)** double-counts per-symbol scale (LWC standardises;
  class cells already partition by scale). The OOS $c(\tau)$ degenerates
  to $1.000$ at every $\tau$ — the score is already conservative, so no
  bump is needed. Pareto-dominated by both C1 and C2.

The choice between C1 and C2 is a values question, not a methodology
question — both deliver pooled $\tau = 0.95$ Kupiec at $p = 0.956$. The
question is which per-symbol-deviation profile the consumer prefers.

## Decision (2026-05-03)

**Freeze M5 as the Paper 1 primitive.** C1, C2, C4 found *after* the
Paper 1 validation loop closed; promoting them into the main methodology
would invite a "how many variants did you try before selecting this?"
review question. Paper 1 reports M5 with the disclosed per-symbol
heterogeneity from §6.4.1, the deployment-tuned schedule sensitivities
from §9.3, and the full-distribution rejections from §9.4.

**Route v3 candidates to forward homes:**

- **C1 LWC** — paper §10.4 lead candidate for v3 per-symbol calibration;
  not adopted. Re-evaluate as a candidate v3 primitive after the V3.2
  rolling-rebuild pipeline is in place and a paper-grade walk-forward of
  C1 vs M5 has been run.
- **C2 M6b2** — already deployed for the lending profile; the per-symbol-class
  buffer story is the right empirical content for **Paper 3**'s lending-
  policy framing (per-class collateral buffers, Kamino/MarginFi reserve
  evaluation), not Paper 1.
- **C4 stacked** — rejected (Pareto-dominated). Recorded so the candidate
  is not re-suggested.
- **M6a common-mode partial-out** — independently gated on a Friday-
  observable $\bar r_w$ predictor (W8 result rejected at OOS $R^2 < 0.4$).
  Paper 1 §10.4 mentions briefly; not on a near-term shipping path.

## Artefacts

- Runner: `scripts/run_v3_bakeoff.py`
- Pooled CSV: `reports/tables/v3_bakeoff_pooled.csv`
- Per-symbol CSV: `reports/tables/v3_bakeoff_per_symbol.csv`
- Mechanism CSV: `reports/tables/v3_bakeoff_mechanism.csv`
