# Appendix C — Simulation study

<!-- Assembled 2026-07-16 per internal/paper1_process/DISPOSITION.md Appendix C rows: 06_results.md §6.7 whole
     + 09_limitations.md §9.8 symbol-admission floor. The corroborative-not-predictive
     chronology disclosure is retained verbatim as an integrity disclosure — the one
     place chronology is allowed (internal/paper1_process/SPINE.md voice rule 1 exemption). -->

This appendix carries the synthetic-DGP corroboration of the per-symbol fix cited from §4.4, §6.2, and §7. Under known ground truth, it isolates the failure mechanism the σ̂ standardisation closes and the one it does not.

## C.1 Headline and epistemic status

**Across four DGPs spanning stationary, regime-switching, drift, and structural-break specifications, the σ̂-standardised architecture's per-symbol Kupiec pass-rate at $\tau = 0.95$ is 98.6–99.9% while the unweighted-Mondrian comparator's collapses to 31–38% — the per-symbol bimodality is reproducible in synthetic data with known DGP, and σ̂ standardisation closes it on every DGP tested.** This answers the methodological question raised by §6.2 and §7: the bimodality is a structural property of the architecture (a single per-(regime, $\tau$) multiplier on heterogeneous-tail symbols mis-calibrates in opposing directions), not a property of the unweighted comparator on this particular real-data panel. The simulation is corroborative — a known-DGP control isolating the failure mechanism — not a pre-real-data prediction (the bimodality was first observed on real data under an unweighted Mondrian fit before the simulation was run; σ̂ standardisation was implemented next; this section was committed before the real-data confirmation).

## C.2 Setup

Source: `scripts/run_simulation_study.py` (~30 s end-to-end). Each DGP uses 10 synthetic symbols × 600 weekend returns, $\sigma_i \in \mathrm{linspace}(0.005, 0.030, 10)$ — spanning the empirical real-panel range. Train/OOS split at $t = 400$. Returns drawn from Student-$t$ df=4 rescaled to $\mathrm{std}(r) = \sigma_i$ (or $\sigma_i \cdot m_t$ under DGP B/C/D's vol modifications). 100 Monte Carlo replications per DGP, seed $= 0$.

## C.3 Per-DGP results

| DGP | Unweighted-Mondrian pass-rate at $\tau = 0.95$ | σ̂-standardised pass-rate | Mechanism |
|---|---:|---:|---|
| A — homoskedastic baseline | $0.311$ | $\mathbf{0.993}$ | Per-symbol scale heterogeneity is the entire failure mode |
| B — regime-switching vol multiplier | $0.310$ | $\mathbf{0.986}$ | σ̂ tracks regime transitions with a half-life lag |
| C — non-stationary scale (drift) | $0.309$ | $\mathbf{0.996}$ | Adaptive σ̂ is built for this DGP |
| D — variance shock (10× / 50-week transient at $t = 400$) | $0.380$ | $\mathbf{0.999}$ | σ̂ tracks even 10× variance shocks within EWMA HL=8 |
| E — mean jump (+$\Delta = 200$ bps at $t = 400$, $\sigma_\text{true}$ unchanged) | $0.335$ | $0.595$ | Location shift; σ̂ absorbs $\Delta$ as variance, over-deflates low-σ scores |

Both methods pool to mean realised $\approx 0.95$ across DGPs A–D (within $0.005$ of nominal); the split is on the *per-symbol* failure rate. The σ̂-standardised architecture's smallest pass-rate (DGP B, $0.986$) reflects σ̂'s ~13-weekend tracking lag at regime flips. **DGP D upgrade:** the original $3\times$ variance break became a $10\times / 50$-week transient (matching real-world weekend events: 2024-08-05 BoJ unwind, March-2020 COVID-month vol multiplier $\sim 5\times$ for 6–8 weeks). LWC's per-symbol pass rate is unchanged at $99.9\%$ (`reports/tables/paper1_c3_stronger_dgp_d.csv`).

DGPs A–D hard-code the cross-symbol scale heterogeneity that σ̂ standardisation is built to remove, so they isolate the *scale* effect under known ground truth; they do not stress cross-symbol dependence or a location shift, and cannot corroborate calibration under those. DGP-E (§C.4) supplies the location-shift stress, and it is the one specification where the method's per-symbol pass-rate drops (to 59.5% at $\Delta = 200$ bps).

## C.4 DGP E — location-shift limitation with closed-form phase transition

A complementary stress test — a discrete $+\Delta$ conditional-mean shift at the OOS boundary, variance unchanged — exposes a location-shift limitation that σ̂-standardisation does not absorb. $\hat\sigma$ EWMA on the post-shift residual stream sees apparent variance $\hat\sigma^2 \approx \sigma_\text{true}^2 + \Delta^2$, inflating bands across the panel and over-deflating the standardised score on symbols whose $\sigma_\text{true}$ falls below the phase-transition threshold

$$\sigma^\ast(\Delta) \;\approx\; \frac{\Delta}{q \cdot c \,-\, 1}.$$

At the simulation's fitted $q_r(0.95) \cdot c(0.95) \approx 2.23$ (vs the deployed real-panel product $1.9682 \times 1.079 \approx 2.12$; §A.2), $\sigma^\ast(\Delta) \approx 0.81 \cdot \Delta$ — empirically validated across $\Delta \in \{100, 200, 400\}$ bps within $4\%$ of the closed-form prediction ($\sigma^\ast_\text{pred} / \sigma^\ast_\text{emp}$ ratio in $[0.96, 0.99]$ at $\Delta \in \{100, 200\}$ bps; bounded by the $\sigma_i$ grid endpoints elsewhere — `reports/tables/paper1_f2_5_sigma_star_formula.csv`). Symbols with $\sigma_\text{true} < \sigma^\ast(\Delta)$ over-cover (a sharpness deficit, the contract-favourable side per §8); symbols with $\sigma_\text{true} \ge \sigma^\ast(\Delta)$ remain calibrated. At $\Delta = 200$ bps, LWC pooled coverage over-shoots to $0.9727$ and per-symbol Kupiec drops to $59.5\%$ — the failure is *over-coverage on low-σ symbols*, not under-coverage. A complementary location-shift detector — CUSUM on the standardised residual mean, composable with the violation-rate CUSUM bank of B.17 — closes this gap at the monitoring layer, since the violation-rate CUSUM is by-construction blind to location shifts that produce nominal violation rates. This is the "location shifts" bound listed in §8. Source: `reports/tables/paper1_f2_mean_jump_bimodality.csv`.

## C.5 Sample-size sweep and the symbol-admission floor

A sample-size sweep (`scripts/run_simulation_size_sweep.py`; 7 N-values × 4 DGPs × 100 reps × 2 forecasters = 22,400 cells) establishes the newly-listed-symbol admission threshold: $N \geq 80$ weekends under stationary / drift / structural-break DGPs, $N \geq 200$ under regime-switching (the production threshold). HOOD's empirical $N \approx 238$ (246 listed − 8 σ̂ warm-up) sits inside this band; HOOD's empirical Kupiec $p = 0.329$ at $\tau = 0.95$ (violation rate $0.035$, slight over-coverage; B.11) is consistent with the simulation's pass-rate range at $N = 200$. See `reports/m6_simulation_study.md` and `reports/tables/sim_size_sweep_admission_thresholds.csv`.

Operationally, the σ̂ warm-up rule (≥8 past observations, §4.3) sets only the empirical floor; the sweep extends it to a panel-admission threshold. A protocol admitting a symbol with fewer than 200 weekends of history should treat the per-symbol calibration claim as deferred until the panel accumulates.

## C.6 Summary figure

![Simulation study at $\tau = 0.95$ — half-width and coverage in the visual idiom of [romano-cqr-2019] (their Fig. 4), adapted to the per-symbol Mondrian setting. Eight rows: 4 DGPs $\times$ 2 forecasters (M5 unweighted-Mondrian comparator in vermilion; LWC deployed σ̂-standardised in blue, bold). Each box is the per-(rep, symbol) cell distribution ($N = 1{,}000$ per row). Median pills annotate the leftmost edge of each box. Left panel: avg. half-width (bps). Right panel: avg. coverage; dotted vertical marks nominal $\tau = 0.95$. The σ̂ contribution is the *coverage panel*: M5 boxes scatter from $\sim 0.81$ to $\sim 1.00$ — the per-symbol bimodality documented in §7 and Appendix D — while LWC boxes sit tightly on $\tau = 0.95$ across every DGP. The half-width panel makes the Appendix D redistribution visible: M5 widths concentrate on a single per-rep value (the unweighted multiplier applied uniformly across the σ-grid); LWC widths span a wide range within each rep (per-symbol $\hat\sigma_s$ scaling).\label{fig:simulation}](figures/simulation_summary.pdf)
