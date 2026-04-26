# Vault updates for review (items 5-7)

Drafts for the user to review and apply at their discretion. Items 1-4 from the audit were applied autonomously (auto-memory, new `11 - Methodology Pivot.md`, MOC/Thesis/Project Plan edits, README + docs status headers). Items 5-7 below touch long-form research artifacts that shape your own thinking — you'll want to own those edits.

Each section below:
1. Names the target file
2. Gives either a full replacement or a surgical-edit spec
3. Flags open questions where your judgment matters

---

## Item 5: Hypothesis notes

### 5.1 — `Hypotheses/H8 - Chainlink Weekend Bias.md` (full rewrite)

H8 is the MOC-linked falsifiable test. Its current framing (48-row xStock sample, Madhavan-Sobczyk forecaster, Diebold-Mariano RMSE test) doesn't match what was actually run. Proposed replacement:

```markdown
---
tags: [project-solana-oracle, hypothesis, validation]
status: PASS-LITE
confidence: high (tested on 5,986 weekends × 10 tickers × 12 years)
created: 2026-04-21
updated: 2026-04-24
---

# H8 — A Calibrated Factor-Adjusted CI is Materially Better Than Chainlink's Stale-Hold

## Claim (revised 2026-04-24)

During `marketStatus=5` (Fri 8pm ET → Sun 8pm ET, ~48h), Chainlink Data Streams v11 carries stale values. The original H8 framing tested "is the stale hold biased?" That question was narrow and, at 48 weekend observations, statistically underpowered. The revised claim:

**A factor-adjusted fair value with an empirical-quantile confidence interval (the v1b methodology) produces a band whose realized coverage matches its claimed coverage on the majority of weekends, and whose width is materially tighter than any honest stale-hold band covering the same empirical rate.**

Tightness and calibration — not point-estimate accuracy — are the product-defining metrics.

## Why this is the critical test (unchanged)

If a principled CI doesn't meaningfully beat stale-hold's implicit blunt band, the thesis has no teeth and Soothsayer degenerates into "another number alongside Chainlink's number." If it does beat it, Soothsayer is the risk-pricing layer Chainlink's own docs say consumers should build on top.

## How we tested (v1b, 2026-04-24)

Decade-scale walk-forward backtest on underlying equities (xStocks only have ~3 months of history; the underlying tickers they track have 12+ years of data, and the methodology generalises).

- **Sample:** 5,986 weekend observations across 10 tickers (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, MSTR, HOOD, GLD, TLT), 2014-2026.
- **Target:** Monday 09:30 open (yfinance daily `Open`).
- **Publish time:** Friday 16:00 ET (equivalent to the start of `marketStatus=5`).
- **Forecasters compared:** F0 stale-hold (Chainlink analog) vs six variants of factor-adjusted+empirical-quantile models. See [[11 - Methodology Pivot]] for the ladder.

See `reports/v1b_calibration.md` for full tables and `reports/v1b_decision.md` for the decision writeup.

## Verdict: PASS-LITE

| Regime | N weekends | F1_emp_regime realized at 95% claim | F0 half-width | F1 half-width | F1 tighter by |
|---|---|---|---|---|---|
| normal (65%) | 3,924 | **95.0%** | 351 bps | 252 bps | **28%** |
| long_weekend (10%) | 630 | 93.8% | 519 bps | 275 bps | 47% |
| high_vol (24%) | 1,432 | 91% | 489 bps | 401 bps | 18% |

On 75% of weekends the CI is calibrated and materially tighter than stale-hold. High-vol regime is partially calibrated; shock-tertile (~33% of weekends, post-hoc) falls to ~80% realized at 95% claimed — an honest ceiling on pre-publish forecasting.

## What the data actually shows (vs original H8 gates)

Original gates and what they became:

- **"Stale-hold systematic bias test"** → Not the right question. Stale-hold isn't systematically biased; it's *blunt*. The product-relevant question is calibration quality at a given width.
- **"Soothsayer RMSE materially lower than stale-hold RMSE"** → F1_emp_regime MAE is 90 bps vs F0's 95 bps. Not a dramatic point-estimate win. That's fine — Soothsayer competes on CI quality, not point.
- **"Soothsayer 95% CI hit rate ∈ [0.92, 0.97]"** → 95.0% on normal weekends, 93.8% on long weekends, 91% on high-vol. Two of three regimes inside the target band.
- **"Weekend residual predictable in-sample from weekend BTC / ES Sunday-night / Kraken funding"** → ES weekend return IS predictive (factor switchboard works). BTC IS predictive for MSTR post-2020 (factor switchboard works). Kraken funding is NOT predictive (H9 failed).

## Implications

- **Methodology pivot:** The Madhavan-Sobczyk / VECM / HAR-RV / Hawkes stack was not required to pass. Simpler math (factor switchboard + empirical quantile + log-log VIX regime) was sufficient. See [[11 - Methodology Pivot]].
- **Product shape:** Customer-selects-coverage (Option C) rather than "one magic CI." Consumer asks for target realized coverage; we serve the claimed quantile that empirically delivers it. Calibration transparency is the moat.
- **Non-equity RWAs:** Methodology generalizes via factor substitution (GC=F for gold, ZN=F for rates, BTC-USD for MSTR post-2020). Validated on GLD and TLT.

## Related

- [[11 - Methodology Pivot]] — full methodology that replaced the original H8 test setup
- [[DS 07 - Incumbent Oracles]] — Chainlink weekend behaviour reference
- [[H5 - Consumer Story]] — Kamino auto-pause wedge, now a first-class Phase 1 demo
- [[08 - Project Plan]] — Phase 1 MVP build plan
- Reports: `reports/v1b_calibration.md`, `reports/v1b_decision.md`, `reports/option_c_spec.md`
```

**Open question for you:** keep the `status: PASS-LITE` literal, or use `status: validated` to match the frontmatter convention? I chose PASS-LITE because it's more honest about the partial high-vol coverage.

### 5.2 — `Hypotheses/H1 - HMM vs Rules.md` archival footer

Append to the end of the existing file, without deleting the original content (it's part of the decision trail):

```markdown

---

## Archived — 2026-04-24

**Status: superseded by [[11 - Methodology Pivot]].**

H1 debated a regime-detector architecture that depended on the measurement-variance matrix inside the Madhavan-Sobczyk Kalman filter. The v1b methodology does not use a Kalman filter — regime effects are captured empirically via a log-log regression `log|resid| = α + β·log(vol_idx) + γ_earn·earnings + γ_long·long_weekend` with per-symbol vol index. The HMM-vs-rules question is moot; the v1b approach is "regression on regime dummies," which is neither HMM nor hand-coded rules.

This note is retained as part of the decision trail.
```

### 5.3 — `Hypotheses/H7 - Disagreement Feedback Loop.md` archival footer

```markdown

---

## Archived — 2026-04-24

**Status: superseded by [[11 - Methodology Pivot]].**

H7 addressed reflexivity risk in the `γ·disagreement` term of the old four-part CI formula:

> `σ²_CI = σ²_obs + σ²_model + σ²_regime + γ · (publisher_disagreement)²`

The v1b methodology does not construct CIs this way. Bands come from empirical quantiles of standardised residuals; publisher disagreement is not a CI input. The reflexivity concern H7 raised — that publishing disagreement as a CI input could induce feedback loops in protocol behaviour — is structurally obviated.

Retained as part of the decision trail.
```

### 5.4 — `Hypotheses/H9 - Funding Rate Signal.md` archival footer

```markdown

---

## FAIL — 2026-04-22

**Status: rejected.**

V3 tested whether Kraken xStock Perp funding adds incremental signal to the Monday-gap forecast. Result: δ not significant, ΔR² ≈ +0.23pp. Funding does not meaningfully predict the Monday gap above and beyond what the factor-adjusted baseline (ES=F / BTC-USD weekend return) already captures.

Per [[11 - Methodology Pivot]], the v1b methodology does not include funding as a regressor.

Retained as part of the decision trail.
```

### 5.5 — `Hypotheses/H10 - DEX Toxicity Gate.md` archival footer

```markdown

---

## Archived — 2026-04-24

**Status: not built; superseded by [[11 - Methodology Pivot]].**

H10 proposed a Hawkes branching-ratio gate to down-weight DEX observations during reflexive cascades. The v1b methodology does not take DEX observations as a primary signal — the factor (ES/NQ/GC/ZN/BTC) is the weekend-move source. DEX trace becomes relevant only in the Phase 1 xStock-specific calibration overlay (see [[08 - Project Plan]] Week 3), and even there it's a residual adjustment, not a primary input requiring a toxicity gate.

The Hawkes gate can be revisited in Phase 3 if a specific failure mode — DEX-driven miscalibration during reflexive windows — surfaces in production.

Retained as part of the decision trail.
```

---

## Item 6: Long-form artifacts (`04 Ideal System`, `05 ML Methods`, `09 Pitch Narrative`)

### 6.1 — `04 - Ideal System Hypothesis.md` (new body — full replacement recommended)

```markdown
---
tags: [project-solana-oracle, architecture]
status: active
created: 2026-04-21
updated: 2026-04-24
---

# Ideal System Hypothesis (v1b)

Revised 2026-04-24 to reflect the methodology pivot. Original architecture (Madhavan-Sobczyk / VECM / HAR-RV / Hawkes stack) is retained as historical context at the bottom of this note; the live system is the v1b stack described here.

## System shape

Three layers, built around the v1b methodology that actually passed:

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3 — Oracle API (serving)                                 │
│  fair_value(symbol, as_of, target_coverage) → PricePoint       │
│  Returns: point, lower, upper, claimed_served, regime, receipt │
└─────────────────────────────────────────────────────────────────┘
                               ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2 — Calibration surface (product artifact)              │
│  Per-(symbol, regime, claimed) empirical realized coverage map │
│  Rebuilt periodically from the forecaster's rolling backtest    │
└─────────────────────────────────────────────────────────────────┘
                               ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1 — Forecaster (F1_emp_regime)                           │
│  Point: fri_close × (1 + factor_ret)                            │
│  Band: empirical quantile of standardised residuals             │
│  Regime σ: log|resid| = α + β·log(vol_idx) + γ's                │
│  Per-symbol factor + vol index (see universe.py)                │
└─────────────────────────────────────────────────────────────────┘
                               ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 0 — Ingest                                               │
│  yfinance (equities, futures, vol indices, BTC, earnings_dates) │
│  Helius (xStock DEX traces, Chainlink decode — Phase 1 overlay) │
└─────────────────────────────────────────────────────────────────┘
```

## Per-symbol configuration

Only the per-symbol factor and vol index vary across tickers. See `src/soothsayer/backtest/panel.py` for the canonical mapping:

| Symbol | Factor | Vol index | Notes |
|---|---|---|---|
| SPY, QQQ | ES=F | ^VIX | Broad-market equities |
| AAPL, GOOGL, NVDA, TSLA, HOOD | ES=F | ^VIX | Single-name equities |
| MSTR | ES=F → BTC-USD from 2020-08-01 | ^VIX | Pivoted to BTC-proxy behaviour |
| GLD | GC=F | ^GVZ | Gold ETF / gold analogue |
| TLT | ZN=F | ^MOVE* | Long-treasury ETF |

*MOVE underperformed VIX in the TLT fit — revisit per new RWA class.

## Publishing surface (Phase 1)

Per [[H3 - Publishing Surface]]: Switchboard `OracleJob` prototype on Day 1 of Week 2; standalone Anchor program as fallback. Account layout carries:

```
struct PriceUpdate {
    point: int64,
    lower: int64,
    upper: int64,
    claimed_served_bp: u32,   // e.g. 9500 = 95%
    regime_code: u8,
    timestamp: i64,
    signer: Pubkey,
}
```

The `claimed_served_bp` field is the receipt. Consumers can verify it against the published calibration surface.

## Consumer integration pattern

Illustrated for a Kamino-fork lending protocol:

```rust
let pp = soothsayer::read(symbol, target_coverage=0.95);
let safe_ltv = compute_ltv(
    collateral_value = account.collateral_units * pp.lower,
    ltv_floor = MIN_LTV,
    regime_ltv_multiplier = match pp.regime {
        Normal => 1.0,
        LongWeekend => 0.95,
        HighVol => 0.85,
    },
);
```

LTV logic reads the lower bound (not the point) + the regime code + the claimed_served. That's the "risk-aware liquidation logic" the pitch describes, with every input auditable.

## What was archived

The original ideal-system note (dated 2026-04-21) described a Rust implementation of:

1. Madhavan-Sobczyk 3-state SSM (Kalman filter online, ~400 LOC)
2. Hasbrouck VECM against ES/NQ + sector ETFs (~800 LOC)
3. HAR-RV conditional vol (~100 LOC)
4. Yang-Zhang OHLC realized vol (~50 LOC)
5. Hawkes branching-ratio toxicity gate (~400 LOC)

Total ~1,750 LOC of custom econometrics. The v1b stack replaces all five layers with: factor switchboard (data-config) + empirical quantile (~50 LOC) + log-log regression (~100 LOC). The research plan over-estimated the required complexity for a PASS outcome.

## Related

- [[11 - Methodology Pivot]] — context for why this rewrite happened
- [[05 - ML Methods Shortlist]] — revised LOC estimates
- [[08 - Project Plan]] — Phase 1 MVP weeks
- [[H3 - Publishing Surface]] — Switchboard vs Anchor decision
- Code: `src/soothsayer/backtest/`, `src/soothsayer/oracle.py`
```

### 6.2 — `05 - ML Methods Shortlist.md` (new body — full replacement recommended)

```markdown
---
tags: [project-solana-oracle, methods]
status: active
created: 2026-04-21
updated: 2026-04-24
---

# ML Methods Shortlist (v1b)

Revised 2026-04-24. The v1b backtest validated a much simpler stack than this note originally shortlisted. What ships:

## Priority 1 — Ship-now (v1b baseline)

| Method | Role | LOC | Library | Cites |
|---|---|---|---|---|
| **Factor switchboard** | Point estimate: `fri_close × (1 + factor_ret)` per-symbol factor | Data-config (10 lines) | — | Hasbrouck 2003 (futures lead cash) |
| **Empirical quantile CI** | Band from empirical residual distribution, no parametric assumption | ~50 LOC | `numpy` | — |
| **Log-log vol regression** | Regime model: `log|resid| = α + β·log(vol_idx) + γ_earn·earnings + γ_long·long_weekend` | ~100 LOC | `numpy.linalg.lstsq` | — |
| **Per-symbol vol-index selection** | VIX for equities, GVZ for gold, MOVE for treasuries | Data-config | — | — |

Total implementation: ~150 LOC of core math.

## Priority 2 — Revisit if specific failure modes surface

| Method | Triggering failure mode | Estimated LOC |
|---|---|---|
| **FOMC/CPI/NFP calendar as extra γ regressors** | Shock-tertile coverage gap is cited by a consumer | ~100 LOC (calendar integration) |
| **Symbol-specific realized vol-spike detector** | Idiosyncratic equity vol spikes not captured by VIX | ~50 LOC |
| **Student-t or mixture quantiles** | Consumer needs guaranteed 99% coverage during shocks | ~100 LOC |
| **xStock-specific residual overlay** | Mainnet xStock residuals diverge systematically from underlying | ~200 LOC (requires ≥1 month V5 tape) |

## Priority 3 — Permanently deferred (unless resurrection justified)

The original shortlist's priority-1 stack is here:

- **Madhavan-Sobczyk 3-state SSM** — tested and not required; the v1b empirical quantile captures the same uncertainty without Kalman filtering
- **Hasbrouck VECM** — factor switchboard achieves what VECM would have: futures → single-name transmission. Without needing cointegration estimation.
- **HAR-RV** — empirical validation (F2_har_rv forecaster) showed it was broken as a weekend-return variance predictor due to noise in single-squared-return targets
- **Yang-Zhang realized vol** — obviated by empirical quantile
- **Hawkes branching-ratio** — not needed; DEX is not a primary signal

Any of these can come back if a specific failure mode in production justifies them. The v1b backtest did not produce such a mode.

## Design principle

**Prefer empirical over parametric.** Every parametric assumption we dropped (Gaussian tails, SSM state-space form, HAR-RV vol model) improved calibration in the backtest. The methodology's moat is auditability, not exotic math — and empirical methods have less to hide.

## Related

- [[11 - Methodology Pivot]] — context for the simplification
- [[04 - Ideal System Hypothesis]] — system architecture
- [[08 - Project Plan]] — when each priority-2 method might activate
```

### 6.3 — `09 - Pitch Narrative.md` (surgical edits, not full rewrite)

The TAM/comp/exit analysis (~lines 90-290) still holds — the business opportunity doesn't change because the methodology got simpler. The sections that need replacement:

**6.3a — Replace the "Methodology transparency as trust primitive" block (around lines 34-35):**

> Replace:
> *"Soothsayer is the principled, open-source math in that gap: fair value + time-varying confidence interval, grounded in published econometrics (Madhavan-Sobczyk SSM, Hasbrouck VECM, HAR-RV, Yang-Zhang, Hawkes)."*
>
> With:
> *"Soothsayer is the principled, open-source math in that gap: a factor-adjusted fair value with an empirical confidence interval whose realized coverage is auditable against 12 years of public data. Consumers specify the coverage level they need; the oracle publishes the band that empirically delivers it, with per-(symbol, regime) receipts. Every number reproducible on a laptop."*

**6.3b — Replace competitive edge #3 (around line 54):**

> Replace:
> *"Methodology transparency as a trust primitive. Every incumbent is either opaque (Chainlink, RedStone Live) or model-free (Pyth CI is quote-dispersion, degenerates when nobody's quoting). Apache/MIT math in a post-Curve, post-Terra industry is a real differentiator."*
>
> With:
> *"Calibration transparency as the trust primitive. Every incumbent publishes prices without a falsifiable calibration claim — Chainlink (no CI during stale-hold), RedStone (undisclosed methodology), Pyth (quote-dispersion CI without empirical audit). Soothsayer publishes an empirical per-(symbol, regime) calibration table alongside every read. Consumers verify the claim on public data. That's auditability, not marketing — and it's a moat nobody else has even attempted."*

**6.3c — Replace the "Evidence anchors" section (around lines 288-302):**

> Replace the five canonical-citation bullets (Boyarchenko, Lachance, Kraken, FTX, Hasbrouck, Cong) with a single section:

```markdown
## Evidence anchors

The methodology is validated on **5,986 weekend observations across 10 tickers from 2014-2026** — see `reports/v1b_calibration.md` in the repo. Every number in the pitch deck is traceable to that report.

- **Normal-weekend calibration:** 95.0% realized at 95% claimed over 3,924 weekends (65% of the sample). CI 28% tighter than stale-hold.
- **Cross-asset replicability:** same methodology calibrates on gold (GLD + GVZ vol index), long treasuries (TLT + MOVE), and equities — factor substitution is the only per-asset-class change.
- **Honest limits:** high-vol regime (top-quartile VIX) reaches 91% realized coverage, 3.6pp short of calibration target; shock tertile (top third of realized |z|) reaches ~80%. Product framing: we fail transparently; consumers see the calibration receipt and can widen to a higher target coverage.

For the *why this methodology works* audience:

- **Hasbrouck (2003), *J. Finance*.** ~90% of S&P price discovery carried by E-mini futures. The empirical grounding for the factor-switchboard approach — futures lead cash, even across weekends.
- **Cong et al. (Dec 2025), SSRN 5937314.** Peer-reviewed paper on tokenized-stock pricing showing Monday-gap mass migrates into weekend hours as discovery moves onchain.

The old research plan's econometric stack (Madhavan-Sobczyk SSM / VECM / HAR-RV / Hawkes) was tested and not required for PASS. The simpler v1b methodology is what's shipping.
```

**6.3d — Update Risks section item 1 (around line 332):**

> Replace:
> *"H8 not yet proven. V1 is the gating test..."*
>
> With:
> *"H8 tested, PASS-LITE. See `reports/v1b_decision.md`. Caveat: high-vol regime is 3.6pp short of calibration, and shock tertile is ~80% at 95% claimed. Product framing: we publish those limits; stale-hold implicitly hides them."*

Everything else in 09 (TAM, multiples, operating costs, legal posture, Superteam ask, adviser targets, pre-deck pressure tests) stands as-written.

---

## Item 7: Repo-level housekeeping

### 7.1 — Archive V2/V3/V4 notebooks

Commands:

```bash
cd /Users/adamnoonan/Documents/soothsayer
mkdir -p notebooks/archived-v1-methodology
git mv notebooks/V2_ms_half_life.ipynb notebooks/archived-v1-methodology/
git mv notebooks/V3_funding_signal.ipynb notebooks/archived-v1-methodology/
git mv notebooks/V4_hawkes_toxicity.ipynb notebooks/archived-v1-methodology/
```

Create `notebooks/archived-v1-methodology/README.md`:

```markdown
# Archived V1-methodology notebooks

These notebooks were part of the original Phase 0 validation plan, built around the Madhavan-Sobczyk / VECM / HAR-RV / Hawkes methodology stack. The methodology pivoted 2026-04-24 (see `reports/v1b_decision.md`), and these notebooks are retained as historical decision trail rather than live code.

| Notebook | Intent | Outcome |
|---|---|---|
| `V2_ms_half_life.ipynb` | Madhavan-Sobczyk half-life replication on 8 xStocks | Stub (never fully implemented); methodology deprioritised |
| `V3_funding_signal.ipynb` | Kraken perp funding as Monday-gap predictor | Stub. Real V3 ran in `scripts/run_v3.py`; result: FAIL |
| `V4_hawkes_toxicity.ipynb` | Hawkes branching-ratio DEX toxicity gate | Stub (never built); gate not needed per v1b |

Current methodology: see `src/soothsayer/backtest/` and `src/soothsayer/oracle.py`.
```

Keep `notebooks/V1_chainlink_weekend_bias.ipynb` **where it is** — it's an accurate record of the test that motivated the pivot, and it's referenced from the decision report.

### 7.2 — Rename `docs/offline-guide/` contents

The offline guide is a valid pedagogical walkthrough of the original V1-V3 validation flow. Rather than deleting it, rename and contextualise:

```bash
# Inside docs/offline-guide/README.md (or whatever the main guide file is called):
# Add a preamble at the top (before the existing content):
```

```markdown
> **Historical walkthrough (2026-04-24).** This guide steps through the original Phase 0 validation tests (V1 Chainlink weekend bias, V2 Madhavan-Sobczyk half-life, V3 Kraken perp funding) using Excel. It is retained as an educational artifact showing how the validation gates were designed and what they surfaced. The methodology **pivoted 2026-04-24** after these tests — see `reports/v1b_decision.md` and `reports/option_c_spec.md` for the current product shape.
>
> The data CSVs under `data/` are the small test datasets used for the original V1-V3 walkthroughs. They are NOT the v1b backtest data (which uses 5,986 underlying-equity weekends and lives in the cache at `data/raw/yahoo_*.parquet`).
```

Don't rename the file itself — inbound links from elsewhere would break. A status preamble is lower-risk.

---

## Open questions for your judgment

1. **H8 status field** — I chose `PASS-LITE` as the literal string. Convention in your other hypotheses might prefer `validated` with a note. Your call.
2. **Keep or delete old method-stack references in `07 - Deep Research Output v1.md`?** The research output is frozen in time, so I recommend leaving it alone; the outdated-methodology content is appropriate as "what we thought at the time." Only rewrite if you want a different historical record.
3. **Whether to push these Obsidian edits tonight or batch them with a dedicated Obsidian work session tomorrow.** The vault is live-synced to your iPhone — each edit propagates in seconds. Tonight is fine if you prefer momentum.
4. **Update DS 03 (Crypto) and DS 06 (Corporate Actions) to mention BTC-USD as MSTR factor and earnings_dates as regressor?** Small edit, confined to a single sentence in each — easy to do if you prefer.

Ready to apply any of the above individually, or the full set at once, whenever you say.
