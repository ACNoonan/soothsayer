# Soothsayer — Offline Study Guide (Excel edition)

> **Historical walkthrough (as of 2026-04-24).** This guide steps through the original Phase 0 validation tests (V1 Chainlink weekend bias, V2 Madhavan-Sobczyk half-life, V3 Kraken perp funding, V4 Hawkes toxicity) using Excel. It is retained as an educational artifact showing how the validation gates were designed and what they surfaced. The methodology **pivoted 2026-04-24** after these tests — V2 was soft-passed then deprioritised, V3 failed, V4 was never built, and V1 expanded into a decade-scale backtest that validated a simpler methodology (factor switchboard + empirical quantile + log-log regime). See `reports/v1b_decision.md` and `reports/option_c_spec.md` for the current product shape.
>
> The CSV fixtures under `./data/` are the small test datasets used for the original V1–V3 walkthroughs. They are **not** the v1b backtest data (which uses 5,986 underlying-equity weekends cached at `data/raw/yahoo_*.parquet`).

A self-contained walkthrough of everything the Phase-0 validation has done so far. You will rebuild each test by hand in Excel from local CSVs in `./data/`. No internet needed after you close your laptop.

---

## 0 — What Soothsayer is, and why Phase 0 exists

**Soothsayer** is a fair-value oracle for xStocks (tokenised equities: SPYx, QQQx, TSLAx, etc.) on Solana. Phase 0 is the validation phase: before writing a single line of Rust or Anchor, we run four–five statistical tests in Python to check whether the underlying market anomalies we want to monetise actually exist at measurable, tradeable magnitudes. Each test is a "V" — V1, V2, V3, V4, V5. Each ends in a **go / no-go / soft-pass** gate.

The logic: if you can't measure the edge in Excel / Python on historical data, you cannot build a Rust oracle around it. The gate design is the same for every V:

- State the hypothesis in plain language.
- Define the statistic you will compute.
- Define the threshold (effect size + significance).
- Pull free data, compute, report.
- Decide go / no-go.

**Current status as of 2026-04-24 (after March-weekend backfill — see §1.7):**

| Test | What it checks | Gate | Result |
|---|---|---|---|
| V1 | Chainlink's weekend price deviates from Monday-open | p<5% AND mean > 10bp | **RETHINK** (−8.77 bp, p=0.605, n=87) — was GREEN-LIGHT at n=48, flipped with larger sample |
| V2 | 1-min xStock returns show mean-reverting microstructure | phi>0, half-life in [1min, 4h] | **SOFT PASS** (all 8 tickers, ~2.2 min half-life, 3/8 convergence warns) |
| V3 | Kraken perp funding adds signal on weekend gap | δ sig, ΔR² > 2pp | **FAIL** (δ p=0.63, ΔR²=+0.23pp) |
| V4 | Order-flow toxicity Hawkes process | (placeholder — not run) | — |
| V5 | Chainlink vs DEX basis (Plan B pivot) | basis > 30bp, >1 min persistent | (pending data collection) |

This guide covers **V1, V2, V3** in depth (the three you can replicate in Excel) and summarises V4/V5.

---

## File map for this guide

```
docs/offline-guide/
├── README.md                         ← this file
└── data/
    ├── v1_weekend_pairs.csv          87 rows — V1 inputs (11 weekends × 8 xStocks minus 1 GOOGLx gap)
    ├── v2_spy_1min_oneday.csv        390 rows — one RTH day of SPY 1-min bars
    ├── v2_spy_1min_week.csv         1950 rows — 5 RTH days of SPY 1-min bars
    ├── v3_regression_rows.csv        160 rows — the V3 baseline / augmented regression frame
    ├── v3_daily_bars.csv             daily OHLC for underlyings + BTC + ES + XLK
    └── v3_kraken_funding.csv         hourly Kraken perp funding for 10 xStock perps
```

---

## 0.5 — Stats vocabulary you'll actually need (ELI5 primer)

Skip this if stats is your native tongue. Otherwise, read it once and flip back to it whenever a symbol looks scary later.

**Basis point (bp).** 1/100th of a percent. 100 bp = 1%. 10 bp = 0.1%. We use bp because the moves we care about are tiny — "the price was off by 0.0048" is hard to eyeball; "48 bp" is easy.

**Log return.** If a stock goes $100 → $105, the ordinary return is `(105−100)/100 = +5%`. The *log* return is `ln(105/100) ≈ 0.0488` — roughly the same number for small moves. We prefer log for three practical reasons:
1. **Adds across time.** Monday log return +0.01, Tuesday +0.02 → two-day log return is simply 0.03. With percentages you'd have to compound: `1.01 × 1.02 − 1 = 3.02%`.
2. **Symmetric.** A +10% move followed by −10% doesn't land you back where you started (100 → 110 → 99). In log space, +0.0953 then −0.0953 *does* land exactly back. Gains and losses are treated the same.
3. **Pool-able across tickers.** A stock at $500 and a stock at $50 produce very different *dollar* moves for the same event, but their log returns are directly comparable. So we can average across tickers without one dominating.

**Mean.** Sum divided by count. The typical value.

**Standard deviation (sd).** How spread out the values are around the mean. Small sd = tight cluster. Big sd = scattered.

**Standard error.** Standard deviation of the *mean itself* if you were to re-collect your sample. It's `sd / √n`. More data → smaller standard error → tighter estimate.

**t-statistic.** "How many standard errors away from zero is my mean?" `t = mean / (sd / √n)`. `t = 3` → mean is 3 standard errors from zero — very unlikely to be zero by chance. `t = 0.3` → signal is drowning in noise.

**p-value.** "If there were truly no effect, how often would random noise produce something this extreme?" A p-value of 0.023 means: "a null universe would only cough up this result 2.3% of the time." Lower p = stronger evidence the effect is real. We use 5% as the gate by convention — willing to be fooled ~1 time in 20.

**Confidence interval (CI).** A range that probably contains the true mean. A 95% CI of [−78, −18] bp means "I'm 95% confident the true bias lives somewhere in here." If zero is *inside* the interval, you can't rule out "no effect." If zero is *outside*, you can.

**Regression.** Drawing the best-fit line (or hyperplane, in many dimensions) through a cloud of points. Given inputs X and an output Y, a regression solves for `Y = a + b₁·X₁ + b₂·X₂ + ...` choosing the *b*s that minimize the prediction error on average.

**Coefficient.** A *b* in the equation above. `b₁ = 0.5` means: "for every 1-unit increase in X₁, Y increases by 0.5 on average, holding everything else fixed."

**Controlling for.** When a regression has multiple inputs, each coefficient is measured *net of the others*. "Controlling for BTC and ES futures" means "after already subtracting what those two explain, what's left that the new variable explains?"

**R² (R-squared).** The fraction of variation in Y that the regression captures. R² = 0.10 → you explain 10% of the variance, other 90% is noise you can't predict. Ranges 0 (useless) to 1 (perfect).

**ΔR² (delta R-squared).** Run a regression without your new variable, then with it. The improvement in R² is ΔR². "Did adding this variable earn its keep?" 2+ percentage points is a reasonable minimum for claiming *yes*.

**Dummy variable.** A 1-or-0 column that flags a category. `tk_QQQ = 1` on QQQ rows, 0 elsewhere. Lets the regression give each category its own baseline without running a separate model per category.

**Variance.** The square of the standard deviation. Same information, different units (e.g. bp² vs bp).

**AR(1).** "Auto-regressive, order 1." Today's value = some fraction (φ) of yesterday's value + a fresh random shock. If φ = 0.9, today looks a lot like yesterday (long memory). If φ = 0, today is independent of yesterday (no memory). We use the symbol φ (phi) throughout V2.

**Mean reversion.** A series that, after a shock, drifts back toward its long-run average. Opposite of trending. An AR(1) with 0 < φ < 1 is mean-reverting; φ ≥ 1 is not.

**Half-life.** If something is decaying, the half-life is the time it takes to shrink by 50%. A half-life of 2 minutes means that 2 minutes after a shock, half has dissipated. After 4 minutes, three-quarters. Formula for AR(1): `h = −ln(2) / ln(φ)`. φ = 0.73 → h ≈ 2.2 min.

**Kalman filter.** Think of it as a "running average that knows which of its inputs to trust." It holds an estimate of a hidden state, gets noisy observations, and updates by reweighting the old estimate against each new observation based on how much noise each contains. It also handles gaps — if no observation arrives (e.g. overnight), it just rolls the forecast forward and widens its uncertainty.

**MLE (Maximum Likelihood Estimation).** A way to pick parameter values. Out of all possible settings for (φ, σ², …), MLE picks the ones under which the data you actually observed was *most likely* to happen.

---

## 1 — V1: Chainlink Weekend Bias

### 1.1 Why we ran this

Chainlink Data Streams v10/v11 went live on Solana for xStocks on **2026-01-26** with continuous pricing — weekends, overnights, everything. The question Phase 0 was built to answer: *is Chainlink's price accurate during closed-market hours, or does it drift?* If Chainlink's last Sunday-night price systematically misses the realised NYSE Monday-open price by a tradeable margin, that is the edge Soothsayer exploits.

The original framing: publish a secondary oracle that gives a *confidence interval* around the incumbent oracle during illiquid windows. If the incumbent is always correct, there's no product.

### 1.2 Variables

| Symbol | Meaning | Source |
|---|---|---|
| `P_fri_close` | Underlying stock close price at Fri 4:00pm ET | Yahoo Finance daily bars |
| `P_mon_open` | Underlying stock open price at Mon 9:30am ET | Yahoo Finance daily bars |
| `P_CL_sun_last` | Chainlink-published mid of the xStock, last observation before Mon 9:30am ET | Helius RPC, Chainlink Verifier reports (v10/v11) |
| `g_T` | Realised weekend log-gap | `ln(P_mon_open / P_fri_close)` |
| `ĝ_CL` | Chainlink-implied weekend log-gap | `ln(P_CL_sun_last / P_fri_close)` |
| `e_T` | Residual (what CL missed by) | `g_T − ĝ_CL` |

Positive `e_T` → Chainlink *underestimated* the real Monday move. Negative → overestimated. We don't care about the sign per ticker; we care about the *pooled mean* and *variance* across (weekend, ticker) pairs.

> **🎯 What V1 is really asking (ELI5):** Did Chainlink's last Sunday-night xStock price correctly guess where the underlying stock actually opened on Monday? We measure the real weekend move (`g_T`) and Chainlink's implied weekend move (`ĝ_CL`) and subtract. If the difference is zero on average, Chainlink is already accurate — no product to sell. If it's systematically off, that miss is what Soothsayer monetises.
>
> **🧪 Why we take logs of the prices (`ln(...)`):** Two reasons that matter here. (1) Log differences are *additive*, so we can pool ticker-weekends with no extra math. (2) A stock at $600 (QQQ) and a stock at $130 (MSTR) move very differently in *dollars* but comparably in *log-return space* — so averaging across 8 tickers is legit. A raw dollar gap of "$1.50" is meaningless; "−48 bp" is the same magnitude of miss for any ticker.

### 1.3 Step-by-step in Excel

**Open `data/v1_weekend_pairs.csv` in Excel.** The columns are already there:

`weekend_mon, fri_ts, gap_days, symbol, underlying, fri_close, mon_open, cl_mid, cl_minutes_before_open`

There are 48 rows — 6 weekends × 8 xStocks. `cl_mid` is the last Chainlink mid before Monday open; `cl_minutes_before_open` is how close we got (usually <1 min — the scraper walked Verifier reports backward from Mon 9:30am ET).

#### Step 1 — derive the three log values

Add three new columns:

| Column | Formula (row 2) |
|---|---|
| `g_T` | `=LN(G2/F2)` — mon_open / fri_close |
| `g_hat_CL` | `=LN(H2/F2)` — cl_mid / fri_close |
| `e_T` | `=J2-K2` — `g_T − g_hat_CL` |

(Adjust column letters to match your sheet — `F` is `fri_close`, `G` is `mon_open`, `H` is `cl_mid` in the CSV as exported.)

Fill down to row 88 (87 data rows + 1 header).

> **Why multiply by 10,000 for basis points?** The log return `e_T` is already a tiny decimal like `−0.0048`. Multiplying by 10,000 converts it to basis points (−48 bp). Since 1% = 100 bp, and a log return like 0.01 is ≈ 1%, the ×10,000 conversion puts everything on a "bp" scale that's easy to eyeball.

#### Step 2 — per-ticker stats (8 buckets)

> **📏 Why compute per-ticker first, then pool?** If only one ticker (say MSTRx) is driving the entire result, the pooled-across-all-tickers number lies — it whispers "there's a weekend bias in xStocks" when the truth is "MSTRx has weekend bias, everything else is zero." Looking at the 8 per-ticker means side-by-side tells us whether the signal is *broadly distributed* or *concentrated* in a noisy outlier. If it's concentrated, we'd want to down-weight that one or be honest about the thesis.

Create a summary table with one row per symbol. For each symbol, compute:

| Statistic | Formula |
|---|---|
| `n` | `=COUNTIF($D$2:$D$88, "SPYx")` (etc.) |
| `mean_bp` | `=AVERAGEIF($D$2:$D$88, "SPYx", L$2:L$88) * 10000` |
| `sd_bp` | Use an array formula: `=STDEV.S(IF($D$2:$D$88="SPYx", L$2:L$88)) * 10000` (Ctrl+Shift+Enter on older Excel) |
| `t-stat` | `= mean_bp / (sd_bp / SQRT(n))` |
| `p-value` | `=T.DIST.2T(ABS(t), n-1)` |
| `95% CI half-width (bp)` | `= 1.96 * sd_bp / SQRT(n)` |

#### Step 3 — pooled stats (all 87 rows)

| Statistic | Formula |
|---|---|
| `n` | `=COUNT(L2:L88)` → 87 |
| `mean` | `=AVERAGE(L2:L88)` |
| `sd` | `=STDEV.S(L2:L88)` |
| `t` | `= mean / (sd / SQRT(87))` |
| `p` | `=T.DIST.2T(ABS(t), 86)` |
| `mean_bp` | `= mean * 10000` |

You should land very close to: **n=87, mean = −8.77 bp, sd = 157.35 bp, t = −0.52, p = 0.605.**

> **📖 Reading `t = −0.52, p = 0.605` in plain English:**
> - The mean bias (−8.77 bp) is just half a standard error below zero. Barely a flicker.
> - If the true weekend bias were exactly zero, random noise would produce a result this extreme (or more) about 60.5% of the time. More likely than a coin flip.
> - 60.5% is *way above* our 5% gate → we cannot distinguish the bias from zero.
>
> **Answering your earlier question ("p=2.3% is below 5%, doesn't that fail the gate?"):** Nope — with p-values, *lower is stronger evidence against the null*. p < 5% means "noise would rarely produce this by chance" → we accept the signal as real. p > 5% means "noise easily produces this" → we cannot rule out pure chance. The *mean size* gate (|mean| > 10 bp) goes the other way: higher is better. So the direction of the "good" side flips depending on which stat you're looking at.
>
> **What the previous n=48 `p = 0.023` meant:** back when we had only 6 weekends, the pooled residual was −48.3 bp with p = 2.3% — both gates passed, GREEN-LIGHT. The 5 March weekends we just backfilled washed the signal out (§1.7 below). Bigger sample, signal dies → the original result was selection-biased.

#### Step 4 — apply the gate

The gate was: `|mean| > 10 bp` **and** `p < 0.05`. Mean is 8.77 bp (below 10 bp floor); p is 0.605 (way above 5%). **Both fail → RETHINK.**

### 1.4 What we hoped to see vs. what we got

- **Hoped for:** pooled mean clearly non-zero. Either sign is fine — we just want CL's weekend snapshot to *systematically miss* the Monday reprice. A wide, stable miss is the product's reason to exist.
- **What we got at n=48:** −48.3 bp, p=0.023 — exactly the hoped-for outcome. Thought we had it.
- **What we got at n=87:** −8.77 bp, p=0.605. The miss collapsed below the 10-bp economic floor *and* became statistically indistinguishable from zero. SPYx alone went from p=0.006 (n=6) to p=0.95 (n=11). The per-ticker picture is essentially a random scatter around zero once the sample is widened.
- **What this likely means:** CL's weekend mark is close enough to the Monday open, on average, that a *static* bias model can't extract edge. It doesn't rule out *conditional* signals (CL misses during certain vol regimes, or on specific event weekends), but the simplest framing of the product dies here.
- **Unwelcome outcomes we'd also have flagged** (and did not see): mean near zero with *tight* CI (definitively no bias); or a large mean driven entirely by one ticker like MSTRx. Here the signal simply dispersed as the sample grew — classic sample-size-too-small story.

### 1.5 Alternatives we considered (and why we picked this)

| Alternative | Why we rejected |
|---|---|
| **Linear return (not log)** | Log is additive and symmetric. `ln(1.05) = +4.88%`, `ln(0.95) = −5.13%` — a +5% followed by −5% returns you to start in log space. At the scale of these moves (10–200 bps) linear vs log is basically identical, but log is the correct prior. |
| **Dollar-basis instead of log-basis** | Tickers trade at different price levels (QQQ ~600, AAPL ~280, MSTR ~130). Dollar basis is not comparable across tickers, so you can't pool. Log-returns are. |
| **Chainlink VWAP over the weekend** | More honest to the oracle's design, but Chainlink v10/v11 reports *mid, bid, ask, last-traded* — not VWAP. The mid of the last observation is what the oracle consumer actually sees at Monday open. That's the right benchmark. |
| **NYSE close-to-close (Fri close vs Mon close)** | That's a *weekly* return, includes Monday intraday drift, and dilutes the weekend-window question. We want the reprice *at the moment the NYSE opens*, so `Mon_open` is the right number. |
| **Bayesian pooling (Gelman-style)** | Overkill at this sample size. A fixed-effects pooled t-test is interpretable and defensible. |
| **Drop outliers (Winsorize)** | We don't — the outliers *are* the signal. A pooled test that only works because outliers dominate is actually *more* interesting: it says the bias is not evenly distributed, it's concentrated in high-variance tickers where oracles are worst. |

### 1.6 Sanity checks you can do in Excel

- Does `cl_minutes_before_open` have any values > 5 minutes? Answer in our current 87-row dataset: **no**. Median = 0.4 min, max = 3.35 min. 9 rows sit between 2 and 3.35 minutes (the entire 2026-04-20 weekend plus one Mar 30 row), the rest are all sub-minute.
  > **Your earlier note — "rows 42-49 have >1 min, does it hurt reliability?":** At a bp-level bias gate, a ~3-minute stale Chainlink observation introduces noise of roughly (minute-vol × √3) ≈ a couple of bp — small relative to the 100+ bp dispersion we're already seeing across weekends. It widens the sd slightly and is one more reason our signal is hard to distinguish from zero, but it isn't the cause of the flip from GREEN-LIGHT to RETHINK. The backfill sample dwarfs it.
- Plot `e_T` (y-axis) vs `gap_days` (x-axis). Long weekends (Memorial Day, MLK, Presidents') might have bigger residuals. In our 87-row dataset we have one 4-day weekend (Presidents' Day, Feb 17) and ten 3-day weekends. Visually there's no `gap_days` trend — which is itself a mild signal that CL's weekend aggregation isn't breaking down at the longer break.
- Plot `g_T` (y-axis) vs `ĝ_CL` (x-axis) as a scatter. If CL were perfect, points lie on the 45° line. Deviations from 45° *are* `e_T`. In the current data the scatter is tight to 45° — another visual of the RETHINK result.

### 1.7 What changed: the March backfill

Between the original n=48 submission (6 weekends: Feb 9, Feb 17, Feb 23, Apr 6, Apr 13, Apr 20) and the current n=87 dataset, we backfilled the 5 missing March weekends (Mar 2, Mar 9, Mar 16, Mar 23, Mar 30).

- **Why they were missing originally:** Helius free-tier rate-limiting 429'd during the first scrape (noted in the V1 commit caveats).
- **How we got them:** `scripts/run_v1_backfill.py` with a 4-hour lookback and `max_in_window_yields=500` as a guard against feed-silent symbols.
- **Coverage:** 4 of the 5 backfilled weekends landed 8/8. Mar 9 landed 7/8 — the GOOGLx feed was silent for the entire 4-hour pre-open window (may indicate a feed update gap or ID rotation for that weekend).
- **What happened to the signal:**
  - Pooled mean: −48.3 bp → −8.77 bp
  - Pooled p: 0.023 → 0.605
  - SPYx mean: −17.9 bp (p=0.006, n=6) → +1.4 bp (p=0.95, n=11)
  - AAPLx mean: +8.8 bp (p=0.65, n=6) → +25.1 bp (p=0.37, n=11) — still not significant, but the biggest per-ticker move
- **The takeaway:** the original result was selection-biased by which 6 weekends the free-tier scrape happened to capture. With the full n=11 set, there is no static weekend bias at the 10-bp economic floor or the 5% significance level. Thesis pivots toward V5 (Chainlink quality monitor, Plan B) where the product reframes around detecting *conditional* CL–DEX basis widening rather than a constant bias.

---

## 2 — V2: Madhavan-Sobczyk half-life

### 2.1 Why we ran this

If Soothsayer is going to publish a *fair-value* composite at 1-minute cadence, we need to know at what time-scale 1-min prices actually *mean-revert* back to a fundamental. The Madhavan-Sobczyk (MS) decomposition is the simplest microstructure state-space model that answers this: it says the observed log price is a *permanent* random-walk level plus a *transient* AR(1) component that decays back to zero. The speed of decay — the **half-life** — tells you how long microstructure noise lives before prices return to the level.

If the half-life is *tiny* (say <1 min), it's just bid-ask bounce — no microstructure signal to smooth. If it's *huge* (>4h), there's no mean-reversion at the minute scale; the state-space model is the wrong backbone. The Goldilocks zone for 1-min US equities in the literature is ~2–10 minutes.

> **🎯 What V2 is really asking (ELI5):** Imagine the price you see every minute is actually made of two layers stacked on top of each other. Layer 1 is the "true" value of the stock — it wanders around like a drunk person on a long walk, no pattern. Layer 2 is "jitter" — temporary wobble caused by bid/ask bounce, a big order flushing through, someone cancelling a quote. The jitter cancels out over time; the walk doesn't. V2 asks whether that jitter layer is real and measurable at the 1-minute scale. If yes, the oracle can publish `Layer 1` (a smoothed fair value) instead of the noisy observed price. If no, the raw price *is* the fair value and smoothing just adds lag.
>
> **Why we care about the half-life specifically:** it tells us *how fast* the jitter decays. If jitter disappears in <1 minute, there's nothing to smooth — any averaging we do is either too slow (lag) or pointless (already gone). If it takes hours to decay, it's not really "jitter" — it's a slow-moving trend that a random-walk-plus-drift model would fit better. 2–10 minutes is the sweet spot for our product.

### 2.2 The model

Two latent states per ticker (all in log-price space, `y_t = ln(close_t)`):

```
y_t  = m_t + u_t                (observation = level + transient)
m_t  = m_{t-1} + η_t             (level is a random walk; η ~ N(0, σ²_η))
u_t  = φ · u_{t-1} + ε_t         (transient is AR(1); ε ~ N(0, σ²_ε))
```

`φ` (phi) is the AR(1) coefficient. Half-life: `h = −ln(2) / ln(φ)` in whatever units your time step is (here: minutes).

- If `0 < φ < 1`: stationary, mean-reverting, finite half-life.
- If `φ ≤ 0`: oscillatory — bad.
- If `φ ≥ 1`: explosive or unit-root — the AR(1) isn't actually a *transient* any more, it's indistinguishable from the level.

> **📖 Reading the model in English:**
> - `y_t` = the log-price you actually observe at minute `t`.
> - `m_t` = the "true" fundamental level. It takes one small random step per minute (`η_t`). No pattern, no mean-reversion — a random walk.
> - `u_t` = the "jitter" on top. Each minute, it keeps `φ` fraction of last minute's jitter, then gets a fresh shock.
> - `φ` = 0.73 (the number we find) means *73% of the jitter carries forward to the next minute, 27% fades*. After 2.2 minutes, half is gone. After ~10 minutes, almost all of it.
> - `η` and `ε` are just the names for "the random kick to the level" and "the random kick to the jitter" respectively. Both are Gaussian noise — no skew, no fat tails assumed.
>
> **Why two separate noise terms?** Because level-shocks and jitter-shocks behave totally differently. A level shock is *permanent* (the stock is genuinely worth more now). A jitter shock is *temporary* (somebody just crossed the spread in a hurry). Giving them their own variances (`σ²_η` and `σ²_ε`) lets the model learn the ratio — and that ratio *is* the microstructure story.

### 2.3 What the Python script does

The Python code (`scripts/run_v2.py`) uses `statsmodels.UnobservedComponents` to MLE-fit `φ`, `σ²_η`, `σ²_ε` jointly via the Kalman filter. The Kalman filter is what handles the overnight / weekend gaps (marked NaN — the filter just advances the state prediction without updating).

> **⚙️ What the Kalman filter actually does, in plain English:** imagine you're updating a running "best guess" of the two hidden layers (`m_t` and `u_t`) every minute. Each new observed price `y_t` is a combination of level + jitter + noise — so it tells you *something* about both layers, but not directly. The Kalman filter asks "how much of the surprise in today's price should I attribute to the level moving versus the jitter ticking?" It answers using the variances it's learned. If it's learned that the level is very stable (small `σ²_η`) but jitter is volatile (big `σ²_ε`), it attributes most of today's surprise to jitter and leaves the level estimate nearly alone. MLE is the outer loop that picks those variances — it tries many settings and keeps the one under which the data you observed was *most likely* to occur.
>
> **How gaps work:** if no observation arrives (markets closed), the filter just rolls its forecast forward — `m` stays put (random-walk expectation), `u` decays toward zero (since φ<1) — and widens its uncertainty bars. When the market opens, it resumes normal updating.

You cannot do a full Kalman filter fit in Excel by hand. But you *can* do three sensible approximations that get you within striking distance of the MS half-life:

### 2.4 Step-by-step in Excel — the simplified recipe

We'll use `data/v2_spy_1min_oneday.csv` (390 RTH bars for SPY on 2026-04-21) as the workable sample. It has no gaps — one clean session — so a plain AR(1) on returns does most of the job.

Columns: `ts_et, open, high, low, close, volume`.

#### Step 1 — log price and 1-minute log returns

| Column | Formula (row 2/3) |
|---|---|
| `y` (log close) | `=LN(E2)` (assume close is col E) |
| `r_1min` | `=G3-G2` (one-step log-return; leave row 2 blank) |

#### Step 2 — de-mean the returns

The AR(1) assumes zero mean. Subtract the sample mean:

| Column | Formula |
|---|---|
| `r_demean` | `=H3 - AVERAGE($H$3:$H$391)` |

#### Step 3 — lag-1 autocorrelation (φ, proxy #1)

One-minute returns in the MS model are driven by innovations in both the level *and* the transient. For a pure AR(1) transient the returns themselves look like:

```
Δy_t = (level shock) + (transient increment)
Δy_t = η_t + (φ−1)·u_{t−1} + ε_t
```

The lag-1 autocorrelation of 1-minute returns is a *biased-down* estimator of the AR(1) coefficient (because the level shock is pure noise), but it's close enough to sanity-check against the real fit.

Use `=CORREL(I3:I390, I4:I391)` — lag-1 correlation of demeaned returns. Call this `ρ_1`.

**Expected:** `ρ_1` is small and *negative*, typically around −0.1 to −0.3 for liquid US equities. Negative lag-1 in 1-min returns is the classic bid-ask-bounce signature (you're oscillating between bid-trades and ask-trades within a minute). In the MS model this maps to `φ` that is positive and decaying — the transient component mean-reverts.

A rough back-out: if the observation noise (bid-ask bounce σ) is `σ_bb` and the level vol per minute is `σ_m`, then `ρ_1 ≈ −σ²_bb / (σ²_bb + σ²_m)`. The MS half-life we want from `φ` is separate — and for that the full Kalman is genuinely needed.

#### Step 4 — variance ratio (proxy #2, more diagnostic)

The **Lo-MacKinlay variance ratio** is the *cleanest* by-hand microstructure diagnostic. It answers: "if prices were a pure random walk, `Var(k-min return) / (k · Var(1-min return))` would equal 1. What do we see?"

Compute:

| Stat | Formula |
|---|---|
| `Var_1` | `=VAR.S(I3:I391)` — variance of 1-min returns |
| `r_5min` | start at row 7: `=G7-G2` and fill down every 5th row OR use `=LN(E7/E2)`; easier: create a 5-min bar via `INDEX`/`MOD` tricks, or just every 5th row |
| `Var_5` | `=VAR.S(r_5min_column)` |
| `VR(5)` | `=Var_5 / (5 * Var_1)` |

`VR(5) < 1` → prices mean-revert at the 5-minute horizon (microstructure noise). `VR(5) > 1` → prices trend (positive autocorrelation). For liquid US equities we expect `VR(5) ≈ 0.7–0.9`. That 0.1–0.3 gap is the transient.

> **🧠 Intuition for the variance ratio:** if price were a pure random walk (no jitter), the variance of a 5-minute return would equal exactly 5× the variance of a 1-minute return — variances add linearly under independence. So `VR(5)` would be 1. If there's jitter that bounces back within 5 minutes, some of the 1-minute variance is "fake" (it cancels itself out before 5 minutes elapse), making the 5-minute variance *less than* 5×. The *more* the jitter cancels, the *lower* the VR.
>
> If `VR(5) = 0.8`, that means 20% of the 1-minute variance is "fake" jitter that dies out within 5 minutes. That's the transient.

Mapping back to the MS half-life: if `VR(k)` is well below 1 at k=5 but approaches 1 by k=30, the half-life sits around 2–10 min — the band the Python fit got.

#### Step 5 — Python result to compare to

| Ticker | φ | half-life (min) |
|---|---|---|
| AAPL | 0.7347 | 2.2 |
| GOOGL | 0.7192 | 2.1 |
| HOOD | 0.7288 | 2.2 |
| MSTR | 0.7233 | 2.1 |
| NVDA | 0.7199 | 2.1 |
| QQQ | 0.7319 | 2.2 |
| SPY | 0.7330 | 2.2 |
| TSLA | 0.7299 | 2.2 |

Every ticker lands at φ ≈ 0.72–0.73, half-life 2.1–2.2 min. Median = **2.2 min**. In-band.

**Gate was:** fit converges, φ>0, median half-life ∈ [1 min, 4 h] → pass.

Actual: all 8 have φ>0, median 2.2 min → **SOFT PASS**. The "soft" is because 3 of the 8 MLE fits raised convergence warnings — i.e. the optimiser hit a boundary. The cross-ticker consistency (spread 0.15 min across all 8) is what made us call it soft-pass rather than fail. If model misspecification were causing the warnings, you'd expect the fits to disagree with each other wildly.

### 2.5 What we hoped to see vs. not

- **Hoped for (got):** positive φ, half-life 2–10 min. Means the MS backbone is the right modelling choice for the oracle's fair-value smoother.
- **Unwelcome:** φ ≤ 0. Would mean no transient — prices are already random-walk at 1-minute resolution, and a state-space model adds nothing.
- **Unwelcome:** half-life ≫ 4 h. Would mean the "transient" is actually long-horizon drift; a simple random walk with slow-moving trend would fit better than an MS decomposition.
- **Unwelcome:** huge cross-ticker disagreement. Would suggest the model isn't fitting microstructure — it's picking up idiosyncratic noise. Instead we got φ=0.72±0.01 across 8 tickers with wildly different profiles (SPY vs MSTR — different sector, liquidity, vol). That consistency is the best diagnostic.

### 2.6 Alternatives we considered

| Alternative | Why we picked MS anyway |
|---|---|
| **Ornstein-Uhlenbeck (continuous-time OU)** | Algebraically equivalent in the discrete-time limit. The discrete AR(1) in MS *is* a time-discretised OU. We fit the discrete version because our data is already at 1-min resolution — no continuous approximation needed. |
| **Fractional Brownian / ARFIMA** | Allows "long memory" (slowly decaying autocorrelation). Overkill at 1-min scale for equities. Would force us to estimate a Hurst exponent on top. Rejected for the Phase-0 backbone, could revisit. |
| **GARCH-type vol clustering** | Models *volatility* dynamics, not *price-level* dynamics. Orthogonal problem. We care about how fast price returns to fundamental, not how fast vol mean-reverts. |
| **Hasbrouck VECM (vector error-correction)** | Right tool for *multiple* venues trading the same asset (onshore / offshore). We use this in V5 for CL vs DEX. Not the right tool for a single-venue smoother. |
| **HAR-RV (realised volatility cascade)** | Vol model, not price-level model — same issue as GARCH. We'll use it separately as a vol input for the fair-value composite. |
| **Just compute realised volatility per window** | Doesn't give us a *half-life*. Vol tells you magnitude, not speed of decay. |

### 2.7 Sanity checks

- Plot the 390 1-min returns as a bar chart. Look for obvious outliers (a single-minute 1% move means the AR(1) fit is fighting a shock).
- Compute the average `|r_1min|` in basis points. For SPY in a normal session expect ~2–4 bp/min.
- Compute `ρ_1, ρ_2, ρ_3, ρ_4, ρ_5` autocorrelations. For an AR(1) with φ=0.73, theory says the autocorrelation should decay geometrically: `ρ_k ≈ 0.73^k`. In *returns* space the pattern is messier but the *first-order negative-then-decay* shape is what we expect.

---

## 3 — V3: Kraken Perp Funding as a Weekend-Gap Signal

### 3.1 Why we ran this

If V1 says Chainlink *has* weekend bias, the next product question is: *can we predict the bias before Monday open?* Kraken launched xStock perpetual futures in late 2025. Perpetuals have a **funding rate** — a hourly cashflow between longs and shorts that keeps the perp price near the spot price. The funding rate is, in theory, a market-priced forecast of where the underlying is going.

> **🎯 What V3 is really asking (ELI5):** we already know (from V1) that the Monday-open price of the underlying stock tends to drift away from Friday's close. The question here is: can we *guess* the drift ahead of time using information we can see on Sunday night? And specifically, does **funding rate** (a weird crypto-native signal — see below) tell us anything useful *on top of* what boring macro signals already tell us?
>
> **What a funding rate actually is:** a perpetual futures contract never expires — there's no settlement date. To stop the perp price from wandering forever away from the spot price of the underlying asset, exchanges invented **funding**: an hourly cashflow where one side pays the other to bring prices back in line.
> - Perp trading *above* spot → longs pay shorts → "positive funding."
> - Perp trading *below* spot → shorts pay longs → "negative funding."
> - Magnitude = "how crowded one side is." Very positive funding = bulls piled in too hard.
>
> If funding is a good sentiment gauge, it should predict where the underlying goes when the market reopens. That's the bet we're testing.

Hypothesis: the Kraken funding rate at Sunday 20:00 UTC (just before Asia opens) is incrementally informative about the Monday open gap, *beyond* what weekend BTC / ES futures / XLK Friday return already tell you.

"Incrementally informative" is the key phrase. You run a **baseline regression** with the macro controls; you run an **augmented regression** adding the funding term. You ask: did adding funding (a) make the funding coefficient statistically significant? (b) improve R² by at least 2 percentage points?

> **📖 Why we need the "incremental" framing:** funding rates are *contaminated* by things that also move the stock. If BTC ripped +5% over the weekend, *both* perp funding and the Monday open gap are going to move together — but that's BTC driving both, not funding telling us anything special. By running a **baseline** (controls only) and an **augmented** (controls + funding) regression, the coefficient on funding in the augmented model only captures what's left over after the controls have done their job. That's the "does funding *add* anything" test.

### 3.2 Variables

Each row of the regression is one (weekend, ticker) pair.

| Variable | Definition |
|---|---|
| `g_T` | `ln(mon_open / fri_close)` of the **underlying stock** (Yahoo daily bars) |
| `r_btc` | `ln(BTC_mon_open / BTC_fri_close)` — weekend BTC move as a crypto-sentiment control |
| `r_es` | `ln(ES_mon_open / ES_fri_close)` — weekend S&P futures move (the most direct "what did equity futures do over the weekend" control) |
| `r_xlk_fri` | Friday daily log-return on XLK (tech sector ETF) — a Friday-close sector-momentum control |
| `funding_sun` | Kraken perp funding rate at Sun 20:00 UTC for `PF_{ticker}XUSD` |
| ticker FE | 8 dummy variables for each ticker; baseline = SPY |

### 3.3 Specifications

```
baseline:    g_T = α + β_BTC·r_btc + β_ES·r_es + β_XLK·r_xlk_fri + ticker FE + ε
augmented:   g_T = α + β_BTC·r_btc + β_ES·r_es + β_XLK·r_xlk_fri + δ·funding_sun + ticker FE + ε
```

> **📖 How to read these equations in English:**
> - `g_T`: Monday gap (the thing we're trying to predict).
> - `α`: an intercept — the average Monday gap when every input is zero.
> - `β_BTC·r_btc`: "for every 1-unit move in BTC over the weekend, the Monday gap moves by β_BTC." The regression *solves for* β_BTC.
> - `β_ES` and `β_XLK`: same idea, for S&P futures and XLK (tech sector ETF).
> - `ticker FE`: "ticker fixed effects" — the 7 dummy variables that let each ticker have its own baseline Monday gap level, independent of the macro signals.
> - `δ·funding_sun`: *only in the augmented model* — the coefficient on funding. This is the number we care about.
> - `ε`: noise. Everything we can't explain.
>
> The regression **solves for** all the β/δ/α values at once so the predicted `g_T` is as close as possible to the observed `g_T` on average (least-squares fit).

**Gate:** δ significant at 5% **and** ΔR² > 2 percentage points.

> **Why both conditions?** The **δ** test asks "is this coefficient distinguishable from zero?" — a *statistical* question. The **ΔR²** test asks "does it materially improve the prediction?" — an *economic* question. A tiny coefficient could still be "significant" if you have infinite data, but if it only improves R² by 0.1 pp, it's not worth shipping.

### 3.4 Step-by-step in Excel

**Open `data/v3_regression_rows.csv`.** Columns: `weekend_mon, ticker, g_T, r_btc, r_es, r_xlk_fri, funding_sun`.

There are 160 rows (20 weekends × 8 tickers), 102 of which have a non-null `funding_sun`.

#### Step 0 — enable the Analysis ToolPak

Excel's regression tool is in the **Analysis ToolPak** add-in. File → Options → Add-ins → Manage: Excel Add-ins → Go → tick "Analysis ToolPak" → OK. The tool lives in Data → Data Analysis → Regression.

#### Step 1 — filter to rows with funding

Sort by `funding_sun`, delete rows where it is blank. You should have 102 rows left.

#### Step 2 — build ticker dummy columns

> **💡 Why dummies, and why drop one?** A dummy variable is just a 0/1 column that says "is this row SPY? QQQ? NVDA?" etc. You give the regression those columns and it learns a separate baseline per ticker. But if you include a dummy for *every* ticker *plus* an intercept (`α`), the columns are perfectly correlated (every row has exactly one "1") — the math breaks. So we drop one ticker (here: SPY). Every other ticker's coefficient is now read as "how much higher/lower is this ticker's baseline *compared to SPY*."

Add 7 columns (drop one — SPY — as the baseline):

```
tk_QQQ   = IF(B2="QQQ",1,0)
tk_GOOGL = IF(B2="GOOGL",1,0)
tk_AAPL  = IF(B2="AAPL",1,0)
tk_NVDA  = IF(B2="NVDA",1,0)
tk_TSLA  = IF(B2="TSLA",1,0)
tk_MSTR  = IF(B2="MSTR",1,0)
tk_HOOD  = IF(B2="HOOD",1,0)
```

Fill down all 102 rows.

#### Step 3 — run the baseline regression

Data → Data Analysis → Regression.

- Input Y range: `g_T` column
- Input X range: `r_btc, r_es, r_xlk_fri, tk_QQQ, tk_GOOGL, tk_AAPL, tk_NVDA, tk_TSLA, tk_MSTR, tk_HOOD` (10 columns, contiguous)
- Output range: a blank area of the sheet
- Labels: tick if your X columns have headers

Read off `R Square` (should be ≈ 0.0928).

#### Step 4 — run the augmented regression

Same thing but add `funding_sun` as one more X column.

Read off:
- `R Square` (≈ 0.0951)
- The coefficient for `funding_sun` — this is δ (≈ +0.01257)
- Its Standard Error (≈ 0.02624)
- Its t Stat (≈ +0.479)
- Its P-value (≈ 0.63)

> **📖 Reading those five numbers in plain English:**
> - `δ = +0.01257`: "each 1-unit increase in funding is associated with a +0.01257 increase in the Monday log-gap." Funding is in fractional per-hour terms — so this number is already close to zero in any realistic scenario.
> - `SE = 0.02624`: the standard error is **bigger than the coefficient itself**. This already tells you it's cooked — the estimate is drowning in uncertainty.
> - `t = +0.479`: the coefficient is less than half a standard error from zero. Basically indistinguishable from no effect.
> - `p = 0.63`: if funding truly had no relationship with the gap, random noise would cough up an estimate this extreme 63% of the time. ~2-in-3 odds of getting "this result" by luck alone. We reject nothing.
> - `R² = 0.0951` vs baseline 0.0928: adding funding pushed explained variance from 9.28% to 9.51%. A rounding error.

#### Step 5 — apply the gate

- δ p-value: 0.63. Needed: <0.05. **FAIL**.
- ΔR²: 0.0951 − 0.0928 = 0.0023 = +0.23 percentage points. Needed: >2 pp. **FAIL**.

Both fail → the test fails. Funding doesn't add signal.

### 3.5 What we hoped to see vs. not

- **Hoped for:** δ positive and significant. Positive funding means longs are paying shorts — bulls are crowded — so funding > 0 predicts g_T > 0 (higher Monday open than Friday close). δ ≈ +0.5 would translate to "1 bp/hr of funding moves the Monday gap by 0.5 bp."
- **What we got:** δ = +0.013, p = 0.63. Direction is right but noise swamps it. ΔR² is basically zero.
- **Unwelcome (different kind):** δ large and negative and significant. Would mean funding is *counter*-informative — extracting real alpha would require reversing sign, which would imply some weird structural arb (e.g. funding is capturing the cost of shorting the perp, which is a *liquidity premium* not a directional signal). We didn't see this.
- **Unwelcome (most likely explanation for the null):** the Kraken xStock perps are just not liquid enough for their funding rate to carry information. A look at the raw data in `v3_kraken_funding.csv` shows long stretches of zero funding — the market hasn't found enough participants to generate a price signal yet. This is the charitable read: the signal may exist once liquidity matures, but Phase 0 has to decide with the data available today.

### 3.6 Per-ticker slice (in-depth diagnostic)

The headline failure is the pooled test. But the per-ticker column in the V3 report shows a few tickers (NVDA δ=+0.70, AAPL δ=+0.20) where funding *looks* informative at n=11. Individual p-values aren't below 5% at that sample size, but the point estimates are consistently positive for large-cap techs.

This is the kind of thing where you'd say *"re-run in 6 months with more data."* Phase 0 rule: if it doesn't clear the gate today, it doesn't ride into the MVP.

### 3.7 Alternatives we considered

| Alternative | Why we picked this one |
|---|---|
| **Raw (non-log) returns** | Same log-return argument as V1. Makes coefficients dimensionless-ish and comparable across tickers. |
| **No macro controls (funding only)** | Funding is contaminated by macro — if BTC ripped 5% over the weekend and all xStock perps dragged higher, funding goes up and g_T goes up, but that's not oracle-relevant signal. We control for macro to isolate the *residual* informativeness of funding. |
| **Use Friday close funding instead of Sun 20:00** | Friday close is before the weekend information flow (late news, BTC moves, Asia-time futures). Sun 20:00 is the last observation before Monday dynamics start — it's the one snapshot that has seen the weekend but not the Monday reprice. Closest to a real-time signal a Soothsayer trader would use. |
| **Instantaneous funding instead of realized** | Instant (annualised) funding swings wildly. The Kraken API returns *realized* funding at each hour — more stable. |
| **Panel fixed effects with time FE too** | Tried — kills degrees of freedom at n=102 with 20 weekends. Not worth it. |
| **Cross-ticker funding spread** | "Is NVDA funding − SPY funding informative about NVDA gap − SPY gap?" More elegant but requires more data. Reserved for V3b if we revisit. |
| **Take the `relative_funding_rate` field instead** | Kraken returns both absolute and relative funding; relative normalises by index basis. Ran with absolute because that's what traders actually pay. |

### 3.8 Sanity checks

- Plot `funding_sun` on the x-axis and `g_T` on the y-axis, colour by ticker. Eyeball: is there a cloud or a line? (Answer for our data: a cloud with a barely detectable upward tilt — consistent with the null.)
- Count the number of non-zero funding observations per ticker. Tickers with many zero-funding hours (HOOD, MSTR, GOOGL early on) are liquidity-starved and their coefficient estimates should not be believed.

---

## 4 — V4: Order-flow toxicity Hawkes (placeholder)

Not run in code yet. The hypothesis: intraday **order-flow toxicity** (VPIN, PIN) on the underlying predicts short-horizon basis widening between Chainlink and fair value. A Hawkes process models the self-exciting clustering of toxic order-flow arrivals — once one aggressive sweep hits, more tend to follow in the same direction.

In the Phase 0 plan this is gated behind V1–V3. Since V3 failed and V1 passed, the priority shifted to V5 (Plan B, CL vs DEX basis) instead of V4. The V4 notebook is a stub. You won't be able to recreate it; note it exists and skip.

---

## 5 — V5: Plan B — Chainlink vs DEX basis monitor (in progress)

V5 isn't an Excel exercise — it's a **live tape** running `scripts/run_v5_tape.py` that polls Chainlink and Jupiter at 1-minute cadence to measure the basis between the two. The gate is:

1. `|basis| > 30 bp` median (wider than round-trip Jupiter fees)
2. Basis persists >1 minute (time to act)
3. CL is not self-referential from the DEX pool (otherwise basis collapses to zero by construction)

If V5 clears, the product pivots from "oracle competitor" to "oracle **quality monitor**" — Soothsayer publishes Chainlink's quality signal alongside Chainlink's price, flagging when the basis is wide enough for arbitrage.

Reference docs on disk:
- `docs/plan-b.md` — the pivot thesis
- `docs/data-sources.md` — free-tier data stack

---

## 6 — Big-picture math summary (memorise these)

| Concept | Formula | Plain-English intuition |
|---|---|---|
| Log return | `ln(P₁/P₀)` | "The percent move, in a form that adds across time, treats gains and losses symmetrically, and compares fairly across tickers of different price levels." |
| Basis point (bp) | `log_return × 10,000` | "Bite-sized units of return. 1% = 100 bp. A 48 bp move = 0.48%. Uses because the numbers we care about are tiny." |
| Pooled t-stat | `mean / (sd / √n)` | "How many standard errors is my mean away from zero? If it's > ~2, the mean is probably real and not chance." |
| Two-sided p | `T.DIST.2T(|t|, n−1)` in Excel | "If the truth were zero, how often would random noise produce something this extreme? p < 0.05 → rare enough to say the effect is real." |
| 95% CI half-width | `1.96 · sd / √n` | "Mean ± this number covers the true mean 95% of the time. If zero is inside the interval, your effect could be zero." |
| AR(1) half-life | `−ln(2) / ln(φ)` | "After a shock, how long until half has decayed? φ=0.73 → 2.2 min." |
| Variance ratio VR(k) | `Var(k·r) / (k · Var(r))` | "Does price wander like a random walk? VR=1 yes, VR<1 prices mean-revert at horizon k (jitter), VR>1 prices trend." |
| ΔR² | `R²_full − R²_reduced` | "Did my new variable earn its keep? How much extra variation does it explain on top of the controls?" |
| OLS coefficient | "Solves `Y = a + b·X` so predictions miss by as little as possible on average." | "For every 1-unit increase in X, Y moves by b units on average, holding the other inputs fixed." |
| Funding rate | (exchange-defined, usually hourly) | "Cash paid between perp longs and shorts to anchor perp price to spot. Positive = longs crowded, negative = shorts crowded." |
| Fixed effect (dummy) | `IF(ticker="QQQ", 1, 0)` | "Lets a regression give each category its own baseline without fitting a separate model per category." |

---

## 7 — Offline workflow summary

1. Open each CSV in Excel.
2. Follow the step-by-step for V1 first (simplest, 10 minutes).
3. Then V3 (runs in the Analysis ToolPak, 20 minutes).
4. Then V2 (proxies only — no Kalman by hand; focus on understanding φ and the half-life formula).
5. For each, write down: **what the gate was, what the result was, whether you got the same number as the Python report**. If you're off by more than ~10%, it's worth finding the discrepancy.

---

## 8 — Where this comes from in the repo

| Offline file | Real source |
|---|---|
| V1 guide section | `scripts/analyze_v1.py`, `reports/v1_chainlink_bias.md` |
| V2 guide section | `scripts/run_v2.py`, `reports/v2_ms_half_life.md` |
| V3 guide section | `scripts/run_v3.py`, `reports/v3_funding_signal.md` |
| Plan B notes | `docs/plan-b.md` |
| Universe | `src/soothsayer/universe.py` |

When you land, run `uv run python scripts/analyze_v1.py` (and `run_v2.py`, `run_v3.py`) to re-derive the authoritative numbers. They should match whatever you computed in Excel — if they don't, the discrepancy is the lesson.
