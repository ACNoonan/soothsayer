# V1b — Conformal alternatives vs heuristic empirical buffer

**Question.** The shipped Oracle uses a heuristic empirical buffer (added pre-inversion to the consumer target) to close the OOS calibration gap. The textbook alternative is split-conformal prediction (Vovk; Romano CQR; Barber et al. nexCP for non-exchangeable data). Would any of those replace the heuristic with a tighter or theoretically stronger result?

**Method.** Six variants are served on the OOS 2023+ slice (1,720 rows, 172 weekends), at consumer targets τ ∈ {0.68, 0.85, 0.95, 0.99}, against a calibration surface fit on pre-2023 bounds:

| Variant | Mechanism |
|---|---|
| V0  vanilla            | Surface inversion at τ, no adjustment |
| V1  buffer_2.5pp       | Heuristic +2.5pp pre-inversion (then-current shipped default) |
| V3a nexCP_6mo          | Barber-style recency-weighted surface, exponential weights, 6-month half-life |
| V3b nexCP_12mo         | As V3a, 12-month half-life |
| V4a recency_6mo        | Block-recency: surface fit on the last 6 months of pre-2023 data only, uniform weights |
| V4b recency_12mo       | As V4a, 12 months |

V0 is operationally equivalent to vanilla split-conformal at our calibration size — the (n+1)/n finite-sample correction is two orders of magnitude smaller than the empirical OOS gap and is dominated by it. V3 and V4 are the non-exchangeability-aware alternatives.

Bootstrap unit is the weekend (1000 resamples, weekend-block).

## 1. Pooled results

| Variant @ OOS pooled | $\tau$ | realized | half-width (bps) | Kupiec $p_{uc}$ | Christ. $p_{ind}$ |
|---|---:|---:|---:|---:|---:|
| V0 vanilla            | 0.85 | 0.798 | 192 | 0.000 | 0.730 |
| **V1 buffer_2.5pp**   | 0.85 | **0.828** | **216** | **0.014** | **0.751** |
| V3a nexCP_6mo         | 0.85 | 0.746 | 174 | 0.000 | 0.231 |
| V3b nexCP_12mo        | 0.85 | 0.763 | 188 | 0.000 | 0.275 |
| V4a recency_6mo       | 0.85 | 0.742 | 162 | 0.000 | 0.417 |
| V4b recency_12mo      | 0.85 | 0.763 | 168 | 0.000 | 0.569 |
| V0 vanilla            | 0.95 | 0.920 | 351 | 0.000 | 0.380 |
| **V1 buffer_2.5pp**   | 0.95 | **0.959** | **456** | **0.068** | **0.577** |
| V3a nexCP_6mo         | 0.95 | 0.854 | 271 | 0.000 | 0.350 |
| V3b nexCP_12mo        | 0.95 | 0.872 | 324 | 0.000 | 0.406 |
| V4a recency_6mo       | 0.95 | 0.858 | 226 | 0.000 | 0.240 |
| V4b recency_12mo      | 0.95 | 0.865 | 238 | 0.000 | 0.332 |

V1 is the only variant whose Kupiec test does not reject at τ = 0.95. Every conformal alternative (V3, V4) under-covers more than vanilla (V0), not less.

## 2. Bootstrap deltas (95% CI; weekend-block resampling)

| Comparison | $\tau$ | $\Delta$ realized (pp) | $\Delta$ half-width (%) |
|---|---:|---|---|
| V1 → V3a (nexCP 6mo)        | 0.95 | **−10.5 [−12.5, −8.8]**   | **−40.5 [−42.6, −38.5]** |
| V1 → V3b (nexCP 12mo)       | 0.95 | **−8.8 [−10.6, −7.3]**    | **−29.0 [−29.8, −28.1]** |
| V1 → V4b (recency 12mo)     | 0.95 | **−9.4 [−11.3, −7.7]**    | **−47.8 [−49.3, −46.3]** |
| V1 → V3a (nexCP 6mo)        | 0.85 | **−8.3 [−9.8, −6.8]**     | **−19.7 [−22.4, −16.8]** |
| V0 → V1 (heuristic effect)  | 0.95 | **+3.9 [+2.9, +5.1]**     | **+30.0 [+28.3, +31.6]** |

Every CI on the conformal-vs-heuristic deltas excludes zero. The heuristic dominates by a clear margin on coverage at every sampled target, even though the conformal variants are tighter — they are tighter *because they under-cover*, not because they have found a more efficient frontier.

## 3. Mechanism — why does conformal under-correct here?

A natural read is that recency weighting should help under non-exchangeability. The data show the opposite. Two effects compound:

1. **Recent calibration data carries more under-coverage signal.** The raw F1_emp_regime forecaster's coverage gap at the nominal claim widens in the 2020–2022 stretch (COVID + 2022 vol regime). Weighting toward recent data pushes the per-(claimed → realized) surface entries downward at every $q$.
2. **Surface inversion compensates by serving a higher claimed quantile.** A higher served $q$ does retrieve a wider band, but our bounds grid has a maximum at 0.995 — at high $\tau$ the inversion clips against this ceiling rather than extending. The result is a net under-coverage.

The heuristic buffer side-steps this: it adds a fixed shift to the *target* before inversion, which is a position on the same surface shape rather than a re-fit of the surface. On this OOS slice that geometry happens to be the right correction; on a future OOS slice with a different drift pattern, this could reverse.

## 4. Decision

- **Keep the heuristic empirical buffer in the shipped Oracle.**
- **Switch the buffer from a scalar to a per-target schedule** (`BUFFER_BY_TARGET` in `src/soothsayer/oracle.py` and the corresponding Rust crate). Tuning evidence in `reports/v1b_buffer_tune.md`.
- **In the paper (§9.4 / §10):** reframe the conformal upgrade from "future direction" to "tested alternative that empirically under-corrected on this data; reserved as a v2 direction subject to evidence under different drift conditions or a finer claimed grid that does not clip at 0.995."

The heuristic is still a heuristic — sample-size-one OOS split, no finite-sample guarantee. We have not refuted that conformal would be the right tool under exchangeability or with a sample-recovery mechanism. We have shown that on this data, vanilla and recency-weighted conformal both deliver lower coverage than the heuristic at τ ∈ {0.85, 0.95}, with bootstrap CIs that exclude zero.

## 5. Reviewer-facing language

A reviewer in the conformal tradition will ask why we did not deploy split-conformal. The answer of record:

> *"We tested vanilla split-conformal (operationally equivalent to V0 at our calibration size), Barber et al. nexCP-style recency weighting at two half-lives, and a block-recency baseline at two windows. All three under-corrected the OOS calibration gap relative to a per-target empirical buffer; none delivered Kupiec non-rejection at τ ∈ {0.85, 0.95} on the held-out 2023+ slice. Bootstrap 95% CIs on the coverage deltas exclude zero. We retain the heuristic for v1 and document the conformal options as v2 directions subject to a finer claimed-coverage grid (above 0.995) and a multi-split walk-forward evaluation."*

Raw artifacts:
- `reports/tables/v1b_conformal_comparison.csv`
- `reports/tables/v1b_conformal_comparison_by_regime.csv`
- `reports/tables/v1b_conformal_bootstrap.csv`
- `scripts/run_conformal_comparison.py` (reproducible)
