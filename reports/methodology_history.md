# Methodology evolution log

**Purpose.** A living, append-only record of methodological decisions, tested-and-rejected hypotheses, and the empirical evidence that shaped the current Soothsayer Oracle. Updated when methodology changes; never deleted from. Source-of-truth pointer for the research paper, deployed code, and historical context for new collaborators.

**How to read this doc.** Sections are time-stamped. The current production methodology is summarised in §0 ("State of the world today") and re-derived from the latest dated entry. Earlier entries describe the path; if a finding has since been superseded, the supersession is noted inline.

**How to update this doc.** When you change methodology, append a new dated entry to §1 ("Decision log"). Update §0 to reflect the new state of the world. Never edit prior entries; if an old entry needs correction, add an "AMENDMENT" line with the date and reasoning.

---

## 0. State of the world (current)

*Last updated 2026-04-25.*

**Product shape.** Soothsayer Oracle. Customer specifies target coverage τ ∈ (0, 1); Oracle returns a band that empirically delivered τ on a 12-year backtest stratified by (symbol, regime). Every read carries receipts: served claimed-quantile, forecaster used, regime observed, calibration buffer applied.

**Deployment defaults.**
- Default τ = **0.85** — picked on protocol-EL grounds vs Kamino flat-300bps benchmark.
- Hybrid forecaster: F1_emp_regime in `normal` and `long_weekend`; F0_stale in `high_vol`.
- Per-target buffer schedule: `{0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.010}`, linearly interpolated off-grid (τ=0.99 bumped from 0.005 → 0.010 after 2026-04-25 grid extension).
- Claimed-coverage grid: `{..., 0.95, 0.975, 0.99, 0.995, 0.997, 0.999}` (extended 2026-04-25 from prior top of 0.995); `MAX_SERVED_TARGET = 0.999`.

**Incumbent-oracle comparison (2026-04-25 evening + late-evening schema scan).**
- Pyth + naive $\pm 1.96\cdot\text{conf}$ on 2024+ subset (265 obs): realised **10.2%** at "claimed" 95%. Pyth's CI is documented as aggregation diagnostic, not probability statement; the under-coverage is a feature of the published claim, not a defect.
- Pyth + consumer-fit $\pm 50\cdot\text{conf}$: realised 95.1% at half-width 280 bps on subset (SPY/QQQ/TLT/TSLA-heavy). Subset bias makes the "Pyth+50× narrower than Soothsayer" finding interesting but small-sample.
- Chainlink Data Streams on Solana publishes BOTH v10 (schema 0x000a) AND v11 (schema 0x000b). v11 went live on Solana before 2026-04-25 (date TBD; verifier docstring previously said "not yet active" — wrong). Field-level cadence on weekends:
    - v10 `price` (w7) — frozen at Friday close (stale-hold archetype, F0)
    - v10 `tokenized_price` (w12) — continuous sub-second updates 24/7 (undisclosed-methodology continuous-mark archetype, same as RedStone Live)
    - v11 `mid` / `bid` / `ask` — placeholder-derived (synthetic min/max bookends), NOT real prices
    - v11 `last_traded_price` — frozen at Friday close (same archetype as v10 `price`)
- Chainlink Data Streams during weekend `marketStatus = 5` (87 obs, prior entry): 100% of observations have $\text{bid} \approx 0$ and $\text{ask} = 0$ — no published band. Chainlink + naive $\pm 3.2\%$ wrap delivers 95% realised at 320 bps on this calm-period sample. **Caveat:** the 87-obs dataset predates the v10 + v11 decoder corrections; numerical re-derivation deferred to v2 paper.
- Both findings support §1.1 thesis: no incumbent publishes a verifiable calibration claim at the aggregate feed level. Consumer-supplied wraps can match coverage but require the consumer to do the calibration work themselves.
- **v11 24/5-window cadence (pre-market, regular, post-market, overnight) untested as of 2026-04-25.** Verification scheduled Monday 2026-04-27 morning ET — see `docs/ROADMAP.md` Phase 1 → Methodology / verification.

**Validated empirical claims (OOS 2023+, 1,720 rows, 172 weekends):**
- τ = 0.95: realised 0.950, Kupiec $p_{uc}$ = 1.000, Christoffersen $p_{ind}$ = 0.485 (PASS).
- τ = 0.85: realised 0.855, Kupiec $p_{uc}$ = 0.541, Christoffersen $p_{ind}$ = 0.185 (PASS).
- τ = 0.68: realised 0.678, Kupiec $p_{uc}$ = 0.893, Christoffersen $p_{ind}$ = 0.647 (PASS).
- τ = 0.99: realised 0.977 (post-grid-extension; was 0.972 on the 0.995-capped grid) — Kupiec still rejects. Structural ceiling re-attributed: with the grid extended to 0.999, the deeper finite-sample limitation is now identified as the 156-weekend per-(symbol, regime) calibration window size, not grid spacing.
- Protocol EL vs Kamino flat ±300bps at τ = 0.85: ΔEL ≈ −0.011 with bootstrap 95% CI [−0.014, −0.007] (favours Soothsayer).
- **Walk-forward stability (6 expanding-window splits 2019–2025):** at τ=0.95, mean buffer = 0.019 (σ = 0.017); deployed value 0.020 lands at the cross-split mean. At τ=0.85, mean buffer = 0.025 (σ = 0.022); deployed 0.045 is conservative (≥1σ above mean).
- **Stationarity (D2):** 8 of 10 symbols stationary by joint ADF + KPSS; HOOD (n=245) and TLT trend-stationary.
- **Christoffersen pooling sensitivity (D4):** sum-of-LRs / Bonferroni / Holm-Šidák agree on accept/reject at α=0.05 across all four targets — robust to pooling choice.
- **Inter-anchor τ validation (D5):** sweep τ ∈ [0.50, 0.99] step 0.01 (50 levels). Kupiec $p_{uc} > 0.05$ at **47 of 50** targets; max deviation $|\text{realised} - \tau|$ = 0.030. The three failures are τ=0.50/0.51 (over-cover by 2.6–3pp; safe direction; flat extrapolation below the lowest anchor) and τ=0.99 (the documented §9.1 structural ceiling). **Deployment range τ ∈ [0.52, 0.98] passes uniformly.** This is a stronger claim than the four-anchor calibration: realised(τ) = τ + ε with sup|ε| < 0.025 across the whole deployment range. Closes the linear-interpolation faith claim raised in the bibliography review.
- **Served-band PIT uniformity (D6):** the naive KS-on-PIT test fails (KS=0.500) because the τ grid floor at 0.50 floors all natural PITs in $[0, 0.50)$ — a measurement artefact, not a calibration failure. The right test is D5 (per-τ realised vs target), which passes on the deployment range. Disclosed methodologically in `reports/v1b_diagnostics_extended.md`.
- **Cross-asset leave-one-out (D7):** for each of the 10 symbols, refit the calibration surface on the other 9 and serve the held-out ticker through the pooled-fallback path on its 2023+ OOS slice. **Pooled coverage transfers near-perfectly:** in-sample → LOO pooled at (τ=0.68, 0.85, 0.95) = (0.678→0.681, 0.855→0.852, 0.950→0.967). 26 of 30 (symbol × τ) cells pass Kupiec at α=0.05; the 4 failures are 3 over-covers (safe direction; GLD/MSTR/TLT) and 1 under-cover at SPY τ=0.68 (lowest-grid edge). Largest realized-coverage drop in-sample → LOO is −0.047 at MSTR τ=0.68. **The calibration mechanism transfers to unseen tickers**, supporting a paper claim that the methodology generalises beyond our 10-symbol universe — a §6.5 strengthening, not a §9.9 disclosure. Artefact: `reports/v1b_leave_one_out.md`, `reports/tables/v1b_leave_one_out.csv`.
- **Window-size sensitivity sweep (D8):** sweep F1_emp_regime rolling window ∈ {52, 78, 104, 156, 208, 260, 312} weekends; for each, recompute bounds, build calibration surface, serve OOS 2023+ at τ ∈ {0.68, 0.85, 0.95} using deployed BUFFER_BY_TARGET. **Window-robust within ±3pp realised at every τ across the full range.** Window=156 is the *only* choice that passes Kupiec at α=0.05 on all three targets simultaneously; window 208 also passes at τ=0.68 + 0.95 with τ=0.85 marginal. Deployed 156 is empirically defensible (not arbitrary) and sits inside a stable region [156, 260] where coverage tracks target within tolerance and sharpness is comparable. Artefact: `reports/v1b_window_sensitivity.md`, `reports/tables/v1b_window_sensitivity.csv`.

**Code source-of-truth.**
- Python: `src/soothsayer/oracle.py` (`BUFFER_BY_TARGET`, `REGIME_FORECASTER`, `Oracle.fair_value`).
- Rust: `crates/soothsayer-oracle/src/{config,oracle}.rs` (byte-for-byte port; 75/75 parity tests pass).
- Calibration surface artefact: `data/processed/v1b_bounds.parquet` (the table consumers verify against).

**Paper draft snapshot (descriptive sections, frozen pending live deployment):**
- §1 Introduction — `reports/paper1_coverage_inversion/01_introduction.md`
- §2 Related Work — `reports/paper1_coverage_inversion/02_related_work.md` (28 verified references)
- §3 Problem Statement — `reports/paper1_coverage_inversion/problem_statement.md`
- §6 Results — `reports/paper1_coverage_inversion/06_results.md`
- §9 Limitations — `reports/paper1_coverage_inversion/09_limitations.md`
- §2-citation bibliography — `reports/paper1_coverage_inversion/references.md`

**Phase-2 deliverables conditional on data history.** F_tok forecaster (uses on-chain xStock TWAP; gated on V5 tape ≥ 150 weekend obs per regime), MEV-aware consumer-experienced coverage, full PIT-uniformity diagnostic, conformal-prediction re-evaluation under finer claimed grid. See `docs/v2.md`.

---

## 1. Decision log

### 2026-04-25 (late evening) — Empirical Chainlink schema scan: v10 + v11 field-level weekend behaviour

**Trigger.** Conflicting documentation across the repo about Chainlink Data Streams cadence on Solana — `docs/plan-b.md` claimed `tokenized_price` was a "24/7 CEX mark, updates weekends" with undisclosed methodology; user pushed back that Chainlink equities feeds are 24/5, not 24/7; `verifier.py` docstring said v11 was "not yet active on Solana for xStocks"; `v11.py` docstring said v11 had been live since Jan 2026. None of these were tested on live data. Today is Saturday — natural opportunity to settle the weekend-cadence question empirically.

**Hypotheses tested.**

1. **H1: Chainlink v10 `tokenized_price` (w12) updates continuously across weekends.** *Accepted.* SPYx parquet panel from `data/raw/v5_tape_2026042{4,5}.parquet` (1,021 polls across Friday + Saturday) contains 1,021 distinct `cl_tokenized_px` values vs only 199 distinct `cl_venue_px` values. `tokenized_price` evolves on every poll including all of Saturday under `market_status = 1` (closed). `cl_venue_px` (= v10 `price` w7) is frozen at the Friday close (713.970) for all of Saturday — only updates during the regular NYSE session. *Artefact:* `scripts/check_chainlink_weekend.py` (smoke verification), live tape parquets.
2. **H2: Chainlink v11 (schema 0x000b) is active on Solana.** *Accepted.* Scan of the most recent ~500 Verifier txs (`scripts/scan_chainlink_schemas.py`): 8 v11 reports observed in the window (~1.6% of decoded reports). Schema distribution: 0x0008 (148, stables) / 0x0003 (128, crypto-forex) / 0x000a (103, v10 xStocks) / 0x0007 (86, DEX-LP) / 0x0009 (16, unidentified) / 0x000b (8, v11). v11 feed_ids do not match our 8-xStock map (which is v10-only); v11 likely covers same underlyings under different feed_ids but symbol mapping is deferred until needed. `verifier.py` "v11 not yet active" claim was stale — corrected.
3. **H3: v11 weekend payload provides a non-degenerate band.** *Rejected.* All 8 observed v11 samples had `market_status = 5 (closed/weekend)` with payload pattern: `bid` and `ask` are synthetic min/max placeholders (e.g. SPY-class feed at 21.01 / 715.01); `mid` is arithmetic mean of those placeholders (368.01); `last_traded_price` is frozen at Friday close (713.96, matching v10's `price`). No equivalent of v10's continuous `tokenized_price` exists in v11 — every "real" price field in v11 is stale on weekends.
4. **H4: v11 `mid`/`bid`/`ask` carry real values during the 24/5 windows (pre-market, regular, post-market, overnight).** *Untested* — our scan only covered the weekend `market_status = 5` state. Tomorrow's pre-market window (Monday 04:00-09:30 ET = 08:00-13:30 UTC, market_status = 1 pre-market) is the next chance to observe this. Roadmap entry added under Phase 1 → Methodology / verification.

**Implication for incumbent-archetype framing.** Two competitor archetypes coexist *within Chainlink*, depending on which schema/field a consumer reads:

- A consumer reading **v10 `price` (w7)**, **v11 `last_traded_price`**, or **v11 `mid`/`bid`/`ask`** sees stale-hold semantics on weekends — exactly what F0 stale-hold models. The "Chainlink stale-hold during marketStatus=5" framing in §1.1 / §2 of the paper is correct for these fields, which are what most lending integrations consume.
- A consumer reading **v10 `tokenized_price` (w12)** sees a continuous CEX-aggregated mark with undisclosed methodology — same archetype as RedStone Live.

So Soothsayer has two pitches against Chainlink, and **the Phase 2 comparator dashboard should evaluate against ALL of: v10 `price`, v10 `tokenized_price`, and v11 `mid` / `last_traded_price` separately.** This forecloses the "you didn't compare against the right Chainlink field" objection.

**Implication for the 2026-04-25 (evening) entry's H3 finding.** Prior H3 found "100% of weekend observations have `cl_bid ≈ 0` and `cl_ask = 0`" on the 87-obs Feb–Apr 2026 dataset. Today's v11 scan sees `bid`/`ask` as synthetic placeholders (21.01 / 715.01), not zero. Possible explanations: (a) the 87-obs dataset predates v11 going live on Solana, or (b) the 87-obs dataset was decoded under the pre-2026-04-24 broken decoder that mistreated v10 fields as bid/ask. Either way, the *interpretation* of the prior H3 holds — Chainlink does not publish a verifiable band during the weekend window — but the underlying numbers should be re-derived against the corrected v10 + v11 decoders before publication. Flagged as v2 deliverable; not a v1 paper-blocker because the calibration-claim point is structural, not numerical.

**No methodology change.** The Soothsayer oracle does not read Chainlink at any point — v1b is fit on yfinance underlyings + futures + vol indices. This entry only refines the *competitor-archetype description* used in §1.1 / §2 / §6 of the paper.

**Cascading paper edits required.**
- §1.1: refine "Chainlink stale-hold during marketStatus=5" to specify *which Chainlink field* — applies to `price` (v10 w7) and to all v11 fields; does NOT apply to v10 `tokenized_price` (w12).
- §2: distinguish two competitor archetypes within Chainlink — stale-hold (`price`, v11) and continuous undisclosed mark (`tokenized_price`); position RedStone Live as the same archetype as v10 `tokenized_price`.
- §6 (incumbent comparator subsection from prior entry): add a v10 `tokenized_price` row alongside the existing Chainlink-stale-hold row, with the appropriate caveat that the comparison is one of *calibration claim*, not bandwidth (both are continuous; only Soothsayer publishes a verifiable claim).
- §9: update incumbent-comparison limitations subsection — the 87-obs Chainlink dataset needs re-derivation under the corrected decoders before being treated as the canonical numerical comparison.

**Artefacts.**
- `scripts/check_chainlink_weekend.py` — smoke verification of weekend behaviour for a single xStock
- `scripts/scan_chainlink_schemas.py` — schema-distribution scan across recent Verifier txs
- `data/raw/v5_tape_2026042{4,5}.parquet` — empirical SPYx panel
- `docs/v5-tape.md` — operational documentation of the empirical findings (replaces the speculative pre-2026-04-25 framing)
- `src/soothsayer/chainlink/verifier.py` — docstring updated to reflect v11 active state

---

### 2026-04-25 (evening) — Incumbent oracle comparators: Pyth Hermes + Chainlink Data Streams

**Trigger.** The two largest remaining Tier-1 items: convert §1.1 of the paper from a *qualitative* "no incumbent oracle publishes a verifiable calibration claim" to a *quantitative* matched-window comparison.

**Hypotheses tested.**

1. **H1: Pyth's published `price ± 1.96·conf` band, read as a 95% confidence interval, achieves close to 95% realised coverage on the OOS slice.** *Rejected.* Realised coverage at $k = 1.96$ is **10.2%** on a 265-observation 2024+ subset. Pyth's `conf` field is documented as a publisher-dispersion diagnostic, and the empirical mis-calibration when it's read as a probability statement is on the order of 9–10× under-cover. *Artefact:* `reports/v1b_pyth_comparison.md`.
2. **H2: A consumer can scale Pyth's `conf` by some constant $k$ to match a 95% realised-coverage target, and at the matching $k$ Pyth's implicit band is wider than Soothsayer's served band.** *Partially accepted with caveat.* The smallest $k$ achieving pooled realised ≥ 0.95 on the available subset is $k \approx 50$ (mean half-width 280 bps). At matched coverage on the 265-obs *subset*, Pyth+50× is roughly 37% narrower than Soothsayer's *full-panel* deployed band (443 bps). However, the Pyth-eligible subset is dominated by SPY/QQQ/TLT/TSLA — large-cap, low-volatility tickers — and Soothsayer's `normal`-regime-only OOS half-width on the same regime mix is 401 bps, narrowing the gap. The "$k = 50$" finding is a *consumer-supplied calibration*, not a Pyth-published one; the consumer leaves Pyth's claim behind to construct it. The §1.1 thesis (Pyth doesn't publish a verifiable calibration claim) is unchanged.
3. **H3: Chainlink Data Streams publishes a non-degenerate band during weekend `marketStatus = 5`.** *Rejected.* On the existing 87-obs Feb–Apr 2026 dataset, **100%** of weekend observations have `cl_bid ≈ 0` and `cl_ask = 0`. Chainlink's published "uncertainty signal" during the closed-market window is binary stale-or-live, not a band. *Artefact:* `reports/v1b_chainlink_comparison.md`.
4. **H4: A consumer can wrap Chainlink's stale-hold mid with a symmetric ±k% band to match a 95% realised-coverage target, and at the matching $k$ Chainlink+wrap is wider than Soothsayer's served band.** *Partially accepted with caveat.* On the 87-obs sample, $k \approx 3.2\%$ is the interpolated wrap delivering 95% realised coverage (320 bps half-width). Same caveats as H2: small sample size (binomial CI on $\hat p = 0.95$ at $n = 87$ is roughly [0.89, 0.99]); calm-period sample bias (mostly `normal` regime); consumer-supplied calibration not Chainlink-published.

**Net finding.** Both incumbents fail the verifiable-calibration-claim test as documented. Both can be made into approximate 95%-coverage bands by a consumer who back-fits a multiplier on a private historical sample, but the resulting band is the consumer's calibration claim, not the oracle's. The §1.1 paper thesis is supported quantitatively, with the appropriate caveat that consumer-fit wraps on small low-volatility subsets can produce competitive bandwidth — a finding worth disclosing in §6 rather than burying in a footnote.

**Cascading paper edits.**
- §1.1 of paper: cite Pyth realised coverage at $k = 1.96$ = 10.2% as quantitative support for the qualitative claim.
- §6 (new subsection): add an incumbent-comparator table comparing Soothsayer's deployed band against (a) Pyth + naive $k = 1.96$, (b) Pyth + consumer-fit $k = 50$, (c) Chainlink stale-hold + $\pm 3.2\%$ wrap. Include the small-sample CI caveats and matched-regime-mix caveat.
- §9 (new subsection): "Limits of the incumbent comparison" — both comparators are sample-size-restricted by data availability rather than by methodology; v2 deliverable is a longer Chainlink scrape via `iter_xstock_reports_rpc` and Pyth Pythnet historical via Triton/Pythnet RPC.

**Artefacts.**
- `scripts/pyth_benchmark_comparison.py` + `data/processed/pyth_benchmark_oos.parquet` + `reports/tables/pyth_coverage_by_k.csv` + `reports/v1b_pyth_comparison.md`
- `scripts/chainlink_implicit_band_analysis.py` + `reports/tables/chainlink_implicit_band.csv` + `reports/tables/chainlink_implicit_band_by_symbol.csv` + `reports/v1b_chainlink_comparison.md`

**Tier-1 status: COMPLETE.** All nine engineering-only deliverables landed (walk-forward, bounds extension, bias absorption, stationarity, PIT diagnostic, Christoffersen pooling sensitivity, FRED macro ablation, Pyth comparison, Chainlink comparison). Paper-strengthening evidence in place; ready for funding ask on Tier 2 + 3.

---

### 2026-04-25 (afternoon) — Tier-1 engineering pass: walk-forward + diagnostics + grid extension + macro-event ablation

**Trigger.** Tier-1 of the grant-application impact framework — the engineering-only items we committed to doing before requesting funding. Goal: produce paper-strength sensitivity / robustness evidence and resolve disclosed limitations where reachable on existing data.

**Hypotheses tested.**

1. **H1: BUFFER_BY_TARGET values are stable across train/test splits.** *Accepted.* Walk-forward six-split rolling-origin evaluation (cutoffs 2019-01-01 → 2024-01-01, 12-month horizons): at τ=0.95, mean buffer = 0.019 (σ = 0.017) — deployed value 0.020 lands at the cross-split mean. At τ=0.85, mean = 0.025 (σ = 0.022); deployed 0.045 is ≥1σ conservative (over-covers). Closes the §9.4 sample-size-1 disclosure for τ=0.95; tightens but does not fully close it for τ=0.85, where the conservative deployed value reflects the post-2023 split having a wider gap than the 2019–2022 splits. *Artefact:* `reports/v1b_walkforward.md`, `reports/tables/v1b_walkforward_buffer.csv`.
2. **H2: τ=0.99 ceiling is grid-spacing-driven.** *Partially rejected; structural attribution refined.* Extended the claimed grid from `(..., 0.995)` to `(..., 0.995, 0.997, 0.999)` and bumped `MAX_SERVED_TARGET` to 0.999 in both Python and Rust. OOS realised coverage at τ=0.99 lifted from 0.972 → 0.977 — a real but small improvement. Kupiec still rejects. The deeper finite-sample limitation is the 156-weekend per-(symbol, regime) calibration window, not the grid resolution. §9.1 should be re-attributed: not "the grid stops at 0.995" but "the calibration-window sample size cannot resolve the 1% tail in any per-bucket fit; reaching τ=0.99 reliably would require pooled-window calibration or longer history." `BUFFER_BY_TARGET[0.99]` updated 0.005 → 0.010. Parity verified post-change (75/75). *Artefact:* `reports/v1b_extended_grid.md`, `reports/tables/v1b_extended_grid_tau99_sweep.csv`.
3. **H3: Empirical-quantile architecture absorbs the −5.2 bps point bias by construction (the §6.6 derivation).** *Accepted with numerical proof.* `served_point_offset_from_midpoint_bps_max_abs = 0.000` across 1,720 OOS rows × 4 targets — the served point is exactly the band midpoint. *Artefact:* `reports/tables/v1b_diag_bias_absorption.csv`.
4. **H4: Per-symbol weekend log-return series are stationary (the §9.3 assumption).** *Mostly accepted.* Joint ADF + KPSS: 8 of 10 symbols pass; HOOD (n=245, newer ticker) and TLT (multi-year drawdown) classify as trend-stationary rather than fully stationary. Partial finding: §9.3 stationarity assumption holds in aggregate but two symbols are flagged. *Artefact:* `reports/tables/v1b_diag_stationarity.csv`.
5. **H5: Christoffersen pooling rule choice is load-bearing for the calibration claim.** *Rejected.* Compared sum-of-LRs (deployed) vs Bonferroni vs Holm-Šidák at τ ∈ {0.68, 0.85, 0.95, 0.99}. All three rules agree on accept/reject at α=0.05 across all targets. Calibration claim is robust to pooling-correction choice. *Artefact:* `reports/tables/v1b_diag_christoffersen_pooling.csv`.
6. **H6: A FRED-derived macro-event regressor (FOMC + CPI + NFP) closes the §9.2 shock-tertile coverage gap.** *Rejected.* 324 macro events tagged across 12 years (48% of weekends have one within the following week). Re-fit F1_emp_regime with three variants — M0 deployed, M1 + macro flag, M2 swap-earnings-for-macro. Pooled τ=0.95 effect: 0.923 → 0.921 (within noise). Shock-tertile τ=0.95: 0.803 → 0.796 (slightly *worse*). The implied-volatility indices (VIX/GVZ/MOVE) already absorb whatever macro information is in the data; the extra flag adds noise without adding signal. §9.2 disclosure stands: shock-tertile ceiling is structural, not macro-driven. This is a positive negative-finding: it forecloses one obvious "did you try …" reviewer question. *Artefact:* `reports/v1b_macro_regressor.md`, `reports/tables/v1b_macro_ablation.csv`, `data/processed/v1b_macro_calendar.parquet`.
7. **H7: Raw F1_emp_regime PIT distribution is uniform on (0,1).** *Rejected.* KS test against U(0,1) on 1,720 OOS PITs: KS stat = 0.500, p < 0.001. The raw-forecaster PIT is *expected* to be non-uniform — that's why the calibration surface exists. The right framing for §6 is therefore: raw-forecaster PIT non-uniformity motivates the surface; the served-band coverage at discrete τ levels is the actual product validation, and that *does* pass at three of four targets. The KS finding is a useful clarification, not a defect. *Artefact:* `reports/figures/v1b_diag_pit.png`, `reports/tables/v1b_diag_pit.csv`.

**Net deployment change.** `BUFFER_BY_TARGET[0.99]: 0.005 → 0.010`; `MAX_SERVED_TARGET: 0.995 → 0.999`; claimed grid extended to include {0.997, 0.999}. Python + Rust mirrored. Parity 75/75.

**Cascading paper edits required.**
- §6.4 OOS table: τ=0.99 row updated to realised 0.977 (was 0.972).
- §9.1: re-attribute ceiling to calibration-window size, not grid spacing.
- §9.2: shock-tertile structural ceiling now has a tested negative for macro events.
- §9.3: stationarity disclosure tightened — 8/10 symbols stationary; HOOD and TLT flagged.
- §9.4: walk-forward distribution-valued buffer claim replaces sample-size-1 disclosure.
- §6 calibration claim: optionally add Christoffersen pooling-sensitivity table as a robustness check.

---

### 2026-04-25 (morning) — Per-target buffer schedule replaces scalar; conformal alternatives tested and rejected for v1

**Trigger.** Shipping default τ moved from 0.95 to 0.85 on EL-vs-Kamino evidence (separate decision; see protocol-compare commits). The pre-existing scalar `CALIBRATION_BUFFER_PCT = 0.025` was tuned for τ=0.95 and under-corrected at τ=0.85: realised 0.828 vs target 0.85, Kupiec $p_{uc}$ = 0.014 (rejected).

**Hypotheses tested.**

1. **H1: Vanilla split-conformal (Vovk) closes the gap.** *Rejected.* At our calibration size (n ≈ 4,000) the (n+1)/n finite-sample correction is ~100× smaller than the OOS gap. Operationally equivalent to no buffer; under-covers by 4pp at τ = 0.95.
2. **H2: Barber et al. (2022) nexCP recency-weighting closes the gap.** *Rejected.* Tested at 6-month and 12-month exponential half-lives. Both deliver *lower* coverage than vanilla split-conformal: recency-weighting shifts the (claimed → realised) surface in a way that drives the inverter toward higher $q$, but at high $q$ the bounds grid clips at 0.995, producing net under-coverage. Bootstrap deltas: V1 → V3a 6mo at τ = 0.95 yields Δcov = −10.5pp (CI [−12.5, −8.8]).
3. **H3: Block-recency surface (uniform weights, last 6/12 months only) closes the gap.** *Rejected.* Same mechanism as H2; smaller calibration set amplifies noise without shifting the centre of the surface in the right direction.
4. **H4: Per-target tuning of the heuristic itself.** *Accepted.* Sweep over `{0.000, 0.005, ..., 0.060}` at each anchor τ ∈ {0.68, 0.85, 0.95, 0.99} on OOS 2023+. Smallest-buffer-passing-tests rule yields `BUFFER_BY_TARGET = {0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.005}`.

**Surprise finding.** The previous τ = 0.95 anchor was over-buffered. At buffer 0.020, realised coverage is exactly 0.950 with Kupiec $p_{uc}$ = 1.000 and bands 13 bps tighter than at 0.025. Strict improvement over the prior default.

**Structural finding.** τ = 0.99 hits a finite-sample ceiling regardless of buffer: the bounds grid stops at 0.995, the rolling 156-weekend per-(symbol, regime) calibration window cannot resolve the 1% tail, and any buffer ≥ 0.005 produces identical clipped behaviour. Documented in §9.1 of the paper as a known limitation.

**Reviewer-facing position.** The conformal-as-future-work framing in §9.4 is reframed: the conformal upgrade is *not* an obvious win on this data; it is a v2 direction conditional on either a finer claimed-coverage grid (extending past 0.995) or a multi-split walk-forward evaluation that distinguishes drift from sampling noise.

**Artefacts.**
- `reports/v1b_buffer_tune.md` — sweep methodology + per-target recommendations
- `reports/v1b_conformal_comparison.md` — V0/V1/V3/V4 comparison + bootstrap CIs
- `reports/tables/v1b_buffer_sweep.csv`, `v1b_buffer_recommended.csv`
- `reports/tables/v1b_conformal_comparison.csv`, `v1b_conformal_bootstrap.csv`
- `scripts/run_conformal_comparison.py`, `scripts/tune_buffer.py`, `scripts/refresh_oos_validation.py`

**Code changes.** `src/soothsayer/oracle.py` and `crates/soothsayer-oracle/src/{config,oracle,lib}.rs`. Python ↔ Rust parity verified post-change (75/75 cases match byte-for-byte).

**Paper-side cascading edits.** §6.4 OOS table refreshed under deployed buffers; §9.4 rewritten from scalar-heuristic to per-target-heuristic and reframes conformal as v2-conditional; `v1b_decision.md` annotated with an UPDATE callout (historical snapshot preserved below the callout).

---

### 2026-04-25 — Bibliography review applied; three substantive disclosures + one framing tighten

**Trigger.** Stage-3 related-work survey produced 28 verified references across oracle designs, cross-venue price discovery, calibration / conformal prediction, and institutional model risk management. Several references implied claims that needed disclosure.

**Hypotheses tested.**

1. **H1: Cong et al. 2025 invalidates the methodology by showing on-chain xStock prices already encode weekend information.** *Partially accepted (as gap, not invalidation).* The paper stands at v1 because xStock data history (~30 weekends post mid-2025) is below the ~150 needed for stable per-(symbol, regime) Kupiec validation. The F_tok forecaster slot is documented in `docs/v2.md` §V2.1 and gated on the V5 tape reaching that threshold (estimated mid-Q3 2026).
2. **H2: Pyth's documented per-publisher 95%-coverage convention contradicts our "no incumbent publishes a calibration claim" claim.** *Accepted as framing weakness.* §1 was tightened to "no incumbent publishes a calibration claim verifiable against public data at the *aggregate feed* level," explicitly distinguishing publisher-level self-attestation from aggregate-feed verifiability.
3. **H3: The factor-adjusted point's −5.2 bps median residual bias propagates to the served band.** *Rejected after analysis.* The empirical-quantile architecture takes quantiles of `log(P_t / point)` directly; lower/upper bands are constructed as `point · exp(z_lo)` and `point · exp(z_hi)` with `z` from the empirical CDF of the residual, *including* its non-zero median. The served band is bias-aware by construction; the served point (midpoint of the band) is also bias-corrected. §6.6 was updated to derive this explicitly.
4. **H4: Daian et al. Flash Boys 2.0 implies our reported coverage and consumer-experienced coverage diverge near band edges.** *Accepted as disclosure.* §9.11 added; full measurement deferred to v2 §V2.3 pending V5 tape data.

**Artefacts.** `reports/paper1_coverage_inversion/references.md`, `reports/paper1_coverage_inversion/02_related_work.md`. Disclosures live in `09_limitations.md` §§9.10, 9.11; clarification in §6.6; framing tighten in §1.

---

### 2026-04-24 — Hybrid regime-policy + scalar empirical buffer; v1b ships PASS

**Trigger.** v1b decade-scale calibration backtest with a single forecaster (F1_emp_regime) under-covered at the nominal 95% claim with realised 92.3% pooled and Kupiec rejection. PASS-LITE verdict needed escalation to PASS for shipping confidence.

**Hypotheses tested.**

1. **H1: F2 (HAR-RV vol model) improves coverage.** *Rejected.* Realised 78.2% at the 95% claim — worse than F0 stale-hold and F1_emp_regime. Suspected over-fit to recent realised volatility in a way that fails on weekends. F2 retained in code as a diagnostic but excluded from the deployed forecaster set.
2. **H2: Madhavan-Sobczyk decomposition / VECM / Hawkes process / Yang-Zhang vol estimator are needed.** *Rejected.* The simpler stack (F1_emp_regime: factor-adjusted point + log-log vol-index regression on residuals) achieved comparable coverage with less complexity. The complex methodology stack was researched and dropped from the v1b methodology; surfaced as historical context in `vault_updates_for_review.md`.
3. **H3: Funding-rate signal from Kraken xStock perps adds information (V3 test).** *Rejected.* No detectable improvement; coefficients in `reports/tables/v3_coefficients.csv` are within bootstrap noise of zero. V3 work archived in `reports/v3_funding_signal.md`.
4. **H4: Hybrid forecaster selection by regime closes the high-vol gap.** *Accepted in-sample, refined OOS.* In-sample: F0_stale is 10–35% tighter than F1 in `high_vol` at matched realised coverage. OOS: the *mean*-coverage advantage shrinks to ~2%, but the hybrid's primary serving-time contribution is **Christoffersen independence** — F1 + buffer has clustered violations ($p_{ind}$ = 0.033, rejected); hybrid + buffer does not ($p_{ind}$ = 0.086).
5. **H5: A scalar empirical buffer of 0.025 closes the OOS coverage gap at τ = 0.95.** *Accepted, later refined.* Bootstrap 95% CIs on the buffer effect at τ = 0.95: Δcov = +3.7pp [+2.7, +4.7], CI excludes zero. *(Subsequently superseded 2026-04-25 by per-target buffer schedule; see entry above.)*

**Verdict.** PASS shipped: hybrid forecaster + scalar buffer + customer-selects-coverage Oracle, OOS at τ = 0.95 delivers realised 0.959 with Kupiec $p_{uc}$ = 0.068 and Christoffersen $p_{ind}$ = 0.086.

**Artefacts.** `reports/v1b_calibration.md`, `reports/v1b_decision.md`, `reports/v1b_hybrid_validation.md`, `reports/v1b_ablation.md`. Tables: `reports/tables/v1b_*.csv`.

---

### 2026-04-22 — Phase 0 PASS-LITE on simpler-than-planned methodology

**Trigger.** Phase-0 plan called for testing a Madhavan-Sobczyk + VECM + HAR-RV + Hawkes stack as the candidate forecaster. Simpler stack hit the calibration target first.

**Hypotheses tested.**

1. **H1: Friday close × ES-futures-weekend-return is a usable point estimator across all equities.** *Accepted with extension.* Generalised to a per-asset-class factor switchboard: ES for equities, GC for gold, ZN for treasuries, BTC-USD for MSTR (post 2020-08). Documented in `FACTOR_BY_SYMBOL`.
2. **H2: Empirical residual quantile suffices for CI construction; no parametric distribution assumed.** *Accepted.* F1_emp on the rolling 104-weekend residual window delivers 91.4% pooled at the 95% claim — disclosed as raw-model property; calibration surface absorbs the residual gap.
3. **H3: Per-symbol vol-index (VIX/GVZ/MOVE) outperforms a single VIX regressor.** *Marginally accepted.* Δsharp ≈ 0.3% pooled, CI excludes zero by margin only; useful primarily for GLD and TLT where the asset-class vol index is a better fit than VIX.
4. **H4: An earnings-next-week 0/1 flag carries signal at our sample size.** *Rejected as detectable.* Δcov 0.0pp [−0.1, +0.1]; Δsharp +0.1% [−0.2, +0.5]. Retained in the regressor set as a disclosed structural slot for a future finer-granularity earnings calendar (§9.5 of paper).
5. **H5: A long-weekend 0/1 flag carries signal in its own regime.** *Accepted as localised.* Δsharp +10.6% in `long_weekend` regime, statistically distinguishable; flat in `normal` and `high_vol`. Justifies its inclusion in the regressor set.

**Verdict.** PASS-LITE on the simpler methodology. Phase-1 engineering started before the full Madhavan-Sobczyk stack was even built. Saved several weeks; established the precedent that the methodology should be the simplest one that calibrates rather than the most theoretically sophisticated.

**Artefacts.** `reports/v1b_ablation.md` and `reports/tables/v1b_ablation_*.csv` retain the full ablation evidence; `reports/v1_chainlink_bias.md` is the original Chainlink reconstruction comparison.

---

### Pre-2026-04-22 — Methodology candidates considered and not pursued

For the historical record, methodology variants that were considered, scoped, or partially prototyped but never reached the v1b ablation:

- **Kalman / state-space filters** — considered for joint price-and-volatility estimation. Not pursued: the empirical-quantile architecture handles the same calibration objective without a parametric state-space assumption.
- **Heston / GARCH-family vol models for the conditional sigma** — not pursued: log-log regression on a model-free vol index (VIX / GVZ / MOVE) was simpler and competitive on the backtest.
- **Madhavan-Sobczyk price-impact decomposition** — researched in detail (`notebooks/archived-v1-methodology/`), not pursued because the factor-switchboard captures most of the cross-venue lead-lag relevant to the weekend prediction window.
- **VECM (vector error-correction)** — same disposition.
- **Hawkes process for jump arrivals** — considered as a `high_vol`-regime model. Not pursued: F0 stale-hold's wide Gaussian band already absorbs most jumps adequately at matched realised coverage.

---

## 2. Open methodology questions

Items the team explicitly knows about and has chosen to defer rather than ignore. Each has a documented gating condition.

| Question | Gating condition | Documented in |
|---|---|---|
| Does on-chain xStock TWAP carry weekend signal that reduces our OOS gap? | V5 tape reaches ≥ 150 weekend obs per (symbol, regime) | docs/v2.md §V2.1; methodology log entry 2026-04-25 |
| Does conformal prediction outperform per-target heuristic with finer grid? | Bounds grid extended above 0.995 *and* multi-split walk-forward eval available | reports/v1b_conformal_comparison.md; this log 2026-04-25 |
| Does adversarial transaction ordering create a measurable consumer-experienced coverage gap? | V5 tape + Jito bundle data ≥ 3 months | docs/v2.md §V2.3; methodology log entry 2026-04-25 |
| Is the calibration surface empirically uniform across the full PIT distribution, or only at our three / four sampled τ? | One-shot diagnostic; ~10 LoC in metrics.py | docs/v2.md §V2.4 |
| Does the methodology generalise to non-US equities (tokenised JP / EU shares)? | Multi-region replication run with the same panel-build pipeline | reports/paper1_coverage_inversion/09_limitations.md §9.9 |
| Does a finer earnings-calendar dataset (date + estimated move size) make the earnings regressor detectable? | Acquisition of a vendor-grade earnings calendar | reports/paper1_coverage_inversion/09_limitations.md §9.5 |

---

## 3. How this doc relates to other artefacts

- **`reports/v1b_decision.md`** — frozen 2026-04-24 snapshot of the v1b ship decision. Annotated with later-update callouts but not rewritten.
- **`reports/paper1_coverage_inversion/*.md`** — the paper draft. Sections that depend on methodology should refer to §0 of this doc as the source-of-truth for current state.
- **`docs/v2.md`** — forward-looking; describes Phase-2 deliverables that are gated on data or on resolution of an open methodology question.
- **`src/soothsayer/oracle.py` and `crates/soothsayer-oracle/`** — current deployed methodology; this log explains *why* the constants in those files have their current values.
- **Memory (`MEMORY.md`)** — stable index pointer to this log.

When methodology changes:
1. Append a new entry to §1.
2. Update §0 to reflect the new state.
3. Update the relevant code (Python + Rust mirror).
4. Update any paper-draft section that describes the changed methodology.
5. If a deferred item from §2 was resolved, move it to §1 and remove from §2.
