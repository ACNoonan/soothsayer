# W10 — online-conformal baselines (ACI / DtACI / conformal PI)

**Run 2026-07-24.** Closes W10 in `reports/active/validation_backlog.md`. Opened from the related-work sweep (`related_work_sweep_202607.md`) after Schmitt's RWC paper established ACI / DtACI / conformal PID as the comparator set the conformal-VaR literature benchmarks against, and §7 was found to contain no adaptive-conformal method at all.

Runner: `scripts/run_paper1_w10_online_conformal_baselines.py`
Tables: `reports/tables/w10_online_conformal_baselines.csv`, `..._headline.csv`

## Setup

Same panel (`v1b_panel.parquet`), same point estimator, same 2023-01-01 split, same metrics as every other §7 comparator. 5,916 rows / 631 weekends / 10 symbols; **1,730 OOS rows**. The deployed arm was re-scored inside the same runner and reproduces the paper's published figures exactly — realised 0.9503, half-width **370.56 bps** at τ = 0.95 — so the comparison is on identical footing rather than against quoted numbers.

Five fairness commitments, each written to forestall a "you crippled the baseline" objection:

1. Online state is **warmed up on the training period**, so the baselines see exactly the data the split-conformal arms are fit on. Only 2023+ rows are scored.
2. Run in **both score spaces**: the unstandardised relative residual (`raw`) and the σ̂-standardised score (`lwc` — this hands the baseline our per-symbol fix).
3. Run **per-symbol** as well as pooled. Pooled ACI has no per-symbol channel; ten independent per-symbol ACI instances do, and that is the strong form of the baseline.
4. ACI reported at a default γ = 0.01 **and** at an oracle-best γ selected on the evaluation slice — a configuration we could not deploy, granted to the baseline anyway.
5. `pi` is labelled `pi`, never `pid`: it is conformal PID **without the scorecaster**, the standard model-free configuration. A scorecaster would require choosing and fitting a score-forecasting model, which then becomes a design choice we would have to defend as part of someone else's baseline.

## Result — the mechanism, not the engine

Per-symbol Kupiec pass count at τ = 0.95 (identical pattern at 0.68 and 0.85):

| | **pooled** | **per-symbol** |
|---|---|---|
| **raw score** | ACI 3/10 · DtACI 3/10 · PI 2/10 | ACI 10/10 · DtACI 10/10 · PI 7/10 |
| **σ̂-standardised** | ACI 10/10 · DtACI 10/10 · PI 10/10 | ACI 10/10 · DtACI 10/10 · PI 10/10 |

Deployed (Mondrian split-conformal on σ̂-standardised scores): **10/10**.

Every configuration pools to roughly nominal — realised coverage spans 0.947–0.957 across the entire grid — so **pooled coverage does not separate any of these methods.** What separates them is per-symbol calibration, and the split is governed by one thing: whether the method has a per-symbol channel at all.

This is §7.2's claim reproduced under three calibration engines the paper had never tested. The unweighted-Mondrian comparator fails per-symbol (2/10) not because Mondrian is the wrong partition but because a pooled quantile on an unstandardised score has no way to express cross-symbol scale heterogeneity. Swap the entire engine for ACI, DtACI, or PI and the same failure appears at 2–3/10. Supply the channel — by σ̂-standardising, *or* by running independent per-symbol learners — and every engine reaches 10/10.

**σ̂-standardisation alone is sufficient for the *per-symbol* axis: pooled ACI/DtACI/PI on the standardised score pass 10/10 at every τ.**

> ### ⚠️ Correction, 2026-07-24 (same day)
>
> The first version of this report concluded from the paragraph above that "the load-bearing component is the σ̂, not the partition and not the online adaptation." **That was wrong, and it was wrong because it rested on a metric this run had not computed.** Only pooled and per-symbol coverage were measured. Adding per-**regime** coverage (W12, `w12_partition_given_sigma.md`, and a re-run of this grid) inverts the conclusion:
>
> | τ = 0.95 | deployed | best online arm | all online arms |
> |---|---|---|---|
> | weekend `high_vol` coverage | **0.955** | 0.932 | 0.905 – 0.932 |
> | overnight `earnings_night` coverage | **0.983** | 0.383 | **0.317 – 0.383** |
> | per-regime Kupiec, weekend | **3/3** | 2/3 | 1–2/3 |
> | per-regime Kupiec, overnight | **3/3** | 1/3 | 0–1/3 |
>
> Not one of the twelve online configurations clears 0.383 on earnings nights against a claimed 0.95. The deployed architecture is the only configuration tested, on either panel, passing pooled *and* per-symbol *and* per-regime simultaneously.
>
> The two components are load-bearing on **different axes**: σ̂ delivers per-symbol calibration, the Mondrian partition delivers per-regime calibration. Neither substitutes for the other, and an online learner substitutes for neither — it adapts a *global* level from realised feedback and has no channel to widen for a scheduled event it has not yet observed. `earnings_night` is knowable from the calendar when the band is served; the deployed band widens to 2,508 bps against 342 bps un-partitioned.
>
> The lesson for future comparisons: **a configuration that passes pooled and per-symbol can still be conditionally broken.** Measure every conditioning axis the architecture claims, or the result will flatter whichever arm is missing a channel that is not being tested.

## The "competitive" configuration — and why it isn't

Per-symbol ACI on the raw score is 10/10 per-symbol Kupiec at **338.4 bps**, 8.7% narrower than the deployed 370.6 bps. On the overnight panel several online arms are narrower still. Read on width and per-symbol coverage alone, that looks like a better product.

It is not. The same arm realises **0.911** coverage in weekend `high_vol` against a claimed 0.95, and every online arm lands between 0.317 and 0.383 on overnight `earnings_night`. The narrowness is not sharpness under a calibration constraint — it is the band being under-provisioned in exactly the periods that generate the losses an oracle exists to bound. A lending protocol consuming the 338.4 bps band would be under-collateralised precisely on earnings nights and volatile weekends.

Two further things qualify the width comparison, and neither is a rescue:

**Information set.** The online methods update their miscoverage state after *every observed weekend inside the evaluation slice*. The deployed artefact is frozen at 2023-01-01 and never sees an OOS outcome. So a narrower online band is not a like-for-like win on width — it is bought with test-period feedback the deployed oracle does not consume. This is intrinsic to online conformal, not a flaw in the comparison, and it is exactly how Schmitt benchmarks; it just means the two arms are answering different questions.

**Auditability, which is the product claim.** The deployment artefact is a deterministic function of public pre-split data, SHA-256 stamped, so any third party can rebuild it and re-derive a served band from the receipt. An online-adapting band depends on the entire realised outcome path, so the contract changes: the adaptive state has to be published and replayed to verify any single read, and a consumer cannot reconstruct the band from public data plus a frozen artefact. The paper's primitive is a *verifiable* coverage claim, not merely a well-calibrated one — and that is the axis on which the frozen architecture is chosen, not sharpness.

## What changed in the paper

- **§7** gains a paragraph reporting the 2×2 and the competitive per-symbol-ACI configuration.
- **§2** previously said the online-conformal family was "a comparator set §7 does not include and §9 records as outstanding." Now benchmarked; clause corrected.
- **§9** previously predicted these methods "carry no per-symbol channel, so the comparison we expect to be informative is per-symbol calibration rather than pooled." Half right: pooled has no channel and fails at 2–3/10, but **run per-symbol they do have one and reach 10/10**. The prediction was written before the run and is now replaced by the measured result.

## Caveats on the implementation

- DtACI's η and σ follow the paper's local-adaptation heuristic with a lookback of I = 100 weekends; they are stated in the runner, not tuned. A materially different η/σ could move DtACI, though it would have to move it across the pooled/per-symbol divide to change any conclusion here, which the 2×2 makes unlikely.
- With a panel, the ACI update uses the *fraction* of a weekend's symbols outside the band as `err_t` rather than a single {0,1} indicator — the natural multi-series reading, and lower-variance than collapsing a weekend to one Bernoulli draw. Per-symbol runs use the plain indicator.
- No infinite or NaN half-widths were served anywhere in the grid (checked), so no configuration is silently inflating coverage through a degenerate band.
- Only the endpoint (Friday→Monday) weekend panel is covered. The overnight panel of §6.8 was not re-run under these baselines.
