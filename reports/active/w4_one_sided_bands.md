# W4 — one-sided (downside) bands for the lending track

**Run 2026-07-24.** Runner `scripts/run_paper1_w4_one_sided_bands.py`; tables `reports/tables/w4_one_sided_bands.csv`, `..._by_symbol.csv`, `..._by_regime.csv`. Both off-hours panels.

## The problem

The deployed band is symmetric: score is `|mon_open − point|`, band is `point ± q`. A lending protocol holding tokenised equity is exposed to the **downside only**. A symmetric band at τ puts (1−τ)/2 in each tail, so **its lower edge is a (1+τ)/2 one-sided bound.**

A consumer wiring the default τ = 0.85 band into loan-to-value is provisioning to **92.5%**, not 85% — and paying for it. Both papers this work now positions against (Zhong arXiv:2603.22569, Schmitt arXiv:2602.03903) calibrate one-sided VaR; the symmetric choice is ours, not the literature's.

## Design

Same Mondrian cells, same σ̂ standardisation, same finite-sample rank `ceil(τ(n+1))`, same OOS-fit c(τ) bump as the deployed path — applied to **every** arm so none is advantaged. The c(τ) grid starts at 1.0 and can only widen, so it repairs under-coverage and cannot manufacture a saving.

    score_sym  = |mon_open − point| / (fri_close · σ̂)      (deployed)
    score_down = (point − mon_open) / (fri_close · σ̂)      (signed; + = price below point)

Two comparisons: **(A) same label** — one-sided@τ vs the symmetric band we ship at τ; **(B) matched downside coverage** — one-sided@τ vs symmetric@(2τ−1), both claiming identical protection.

## (A) The product result — the hidden conservatism, priced

Collateral buffer (point → lower edge), deployed symmetric band vs correctly-labelled one-sided, both c-corrected:

| τ | panel | shipped today | one-sided | **buffer freed** |
|---|---|---|---|---|
| 0.68 | weekend | 130.8 bps | 55.0 | **−57.9%** |
| **0.85** | **weekend** | **213.6** | **140.7** | **−34.1%** |
| 0.95 | weekend | 343.4 | 292.8 | **−14.7%** |
| 0.99 | weekend | 633.1 | 589.6 | −6.9% |
| 0.68 | overnight | 112.7 | 34.7 | **−69.2%** |
| **0.85** | **overnight** | **178.9** | **105.7** | **−40.9%** |
| 0.95 | overnight | 280.1 | 213.3 | **−23.8%** |
| 0.99 | overnight | 474.3 | 402.8 | −15.1% |

*(Overnight figures re-run 2026-07-24 against the de-contaminated σ̂ — see `w12_partition_given_sigma.md`. The first pass used a contaminated scale; the correction moved them by 1–4 points and left the conclusion intact.)*

At the **default deployment τ = 0.85**, a lending protocol frees roughly **a third of its collateral buffer** and gets exactly the 85% downside protection it asked for, instead of an unlabelled 92.5%.

The saving shrinks as τ rises because the two tails converge in relative terms — but τ = 0.85 is the default and τ = 0.95 still frees 15–25%.

## (B) The methodology result — one-sided is better *calibrated*

At matched claimed downside coverage, both arms c-corrected, capital is close to a wash and splits by anchor: one-sided is narrower in the body (weekend −6.7% at τ=0.68; overnight −21.4%, −8.2%, −2.7% at 0.68/0.85/0.95) and **wider in the tail** (weekend +11.5% at 0.95, +17.0% at 0.99). That is expected — the absolute-value score pools both tails, so it has roughly twice the effective sample for estimating a tail quantile. Pooling helps where data is thin and costs you where the symmetry assumption is wrong.

Calibration is not a wash, and it is the real argument:

| Kupiec p at matched downside coverage | τ=0.68 | τ=0.85 | τ=0.95 | τ=0.99 |
|---|---|---|---|---|
| one-sided, weekend | 0.975 | 0.973 | 0.956 | 0.942 |
| symmetric-matched, weekend | 0.287 | 0.569 | 0.214 | 0.276 |
| one-sided, overnight | 1.000 | 0.958 | 0.157 | 0.950 |
| **symmetric-matched, overnight** | **0.0000 ❌** | **0.0003 ❌** | **0.0449 ❌** | 0.950 |

Overnight, forcing a symmetric shape onto the gap distribution **fails Kupiec at three of four anchors** and passes per-symbol on only 5/10 and 8/10 symbols at τ=0.68/0.85. It systematically over-covers (0.7095 against a claimed 0.68). The one-sided fit passes everywhere and holds per-regime 2–3/3.

So one-sided is not primarily a capital trick. It is the correct calibration of the quantity the consumer actually acts on, and the symmetric approximation is measurably wrong overnight.

## Recommendation

**Serve a one-sided downside band on the lending track.** It is more honest (τ means what the consumer thinks), materially cheaper in collateral at the deployment default, and better calibrated where it has been tested hardest.

Open design questions before shipping:

1. **Tail anchors.** One-sided is 11–17% wider at τ ≥ 0.95 on the weekend panel. Options: accept the width for correct labelling; keep the absolute-value score for τ ≥ 0.95 only (τ-conditional, which we rejected for the Appendix F correction, so the same objection applies); or widen the calibration sample for the downside tail.
2. **Wire format.** A one-sided band changes the `PriceUpdate` consumer contract — currently a symmetric `(point, half_width)`. This needs a migration plan; see STATUS "Load-bearing today".
3. **Consumer guidance.** This is the answer to "how do we tell integrators to consume the signal": a single downside bound at a chosen τ maps directly onto a loan-to-value haircut, with no need to explain a two-sided interval to someone who only fears one direction.

## Caveats

- c(τ) is OOS-fit here, as in the deployed path (§7 discloses this as a near-identity bump). Both arms get identical treatment, so the comparison is fair, but the absolute levels are not fully out-of-sample.
- Weekend τ=0.99 one-sided rests on the thin end of the downside sample; the tail penalty there is the least reliable number in the table.
- Uses endpoint truth, not path-aware truth (§6.5 applies unchanged).
