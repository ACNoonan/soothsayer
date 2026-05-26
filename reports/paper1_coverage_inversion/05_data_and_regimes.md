# §5 — Data and Regime Labeler

This section specifies the symbol universe, the construction of the two closed-market panels (weekend and overnight), the per-symbol factor and volatility-index switchboards, the regime labeler $\rho$, and the train/test split underlying §6. All inputs are publicly available and free; the weekend panel rebuilds end-to-end via `scripts/run_calibration.py` and the overnight panel via `scripts/build_overnight_panel.py`.

## 5.1 Symbol universe

We evaluate on $K = 10$ symbols spanning three asset classes: eight US equities (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD, MSTR), tokenised gold (GLD), and tokenised long rates (TLT). The eight equity tickers are the underliers of the SPYx, QQQx, AAPLx, GOOGLx, NVDAx, TSLAx, HOODx, and MSTRx tokens deployed on Solana mainnet (Backed Finance; mint addresses verified in `docs/v5-tape.md`). GLD and TLT are RWA generalisation anchors — they share the closed-market structure with the equities (NYSE hours) but exercise different factors and vol indices, so a primitive that calibrates well across all three classes generalises to a broader closed-market RWA universe than equity-only evaluation would justify.

We do not use the on-chain xStock prices themselves as input or evaluation target. Backtest target prices are the *underlying-venue* (NYSE) Monday opens, fetched from Yahoo Finance. The on-chain xStock TWAP forecaster candidate is deferred to a later iteration once the forward-cursor tape accumulates ≥ 150 weekends post-launch (`docs/ROADMAP.md`).

## 5.2 Weekend panel construction

Each row is a single $(s, t)$ weekend prediction window. For each symbol we walk daily price history and, for every consecutive pair of trading days separated by a calendar gap of $\ge 3$ days, emit a row with: `fri_close`, `mon_open`, `gap_days`, `fri_vol_20d` (rolling 20-trading-day std of daily log-returns at Friday close), `factor_ret` (weekend return of the per-symbol conditioning factor), `vol_idx_fri_close`, `earnings_next_week` (Yahoo `earnings_dates` flag), and `is_long_weekend` (`gap_days` $\ge 4$).

The panel spans 2014-01-17 (first Friday on which rolling 20-day vol is defined for all symbols) through 2026-04-24, yielding $|\mathcal{T}_\text{hist}| = 5{,}996$ raw rows across 639 distinct weekend dates (9 full-history symbols × 639 weekends + 245 HOOD weekends). MSTR begins 2014-01-17; HOOD begins 2021-08-13 (post-IPO), contributing ~245 weekends. After the σ̂ warm-up rule (≥8 past observations per symbol) drops the first eight weekends per ticker, $5{,}916$ rows remain evaluable (§6.1).

![Weekend log-returns (Friday close → Monday open) for the 10-symbol panel, 2014-01-17 through 2026-04-24, with the 2023-01-01 train/OOS split marked. Right marginal: each symbol's weekend-return histogram. Heavy-tail tickers (MSTR, HOOD, NVDA, TSLA), low-vol tickers (SPY, QQQ, GLD, TLT), and the equity middle (AAPL, GOOGL) are all visible at panel-relative scale. The 2024-08-05 BoJ unwind, 2020-03 COVID, and 2025 tariff weekend appear as the largest spikes across symbols.\label{fig:weekend-returns}](figures/fig0_weekend_returns.pdf)

### 5.2.1 Overnight panel construction

The overnight panel applies the same row schema and pipeline to the single-weeknight cadence: the gap selector admits consecutive-trading-day pairs ($\texttt{gap\_days} = 1$, close → next-open) rather than Friday→Monday pairs (the `gap_mode` parameter, §4.3.1), with no other component changed. It spans 2014-01-16 → 2026-04-23, yielding **22,624 rows across 2,412 weeknights** on the same ten symbols (≈3.8× the weekend panel); 22,544 remain evaluable after the σ̂ warm-up. Two cadence-specific data treatments apply. **(i) Earnings timing:** the `earnings_next_week` flag is reassigned by session — an after-close (`amc`) release dated $t_0$ or a before-open (`bmo`) release dated $t_1$ fires inside the close$(t_0)$→open$(t_1)$ gap — using the `session` field of scryer `yahoo/earnings/v2`; session timing is complete for reported earnings from 2015 onward, covering the held-out window. **(ii) Ex-dividend adjustment:** because the index factor does not drop for a single name's distribution, the ex-dividend-morning open is reconstructed to its cum-dividend level (`mon_open += dividend`) from scryer `yahoo/corp_actions/v1` on the 241 affected mornings — this removes the only systematic price-level artefact and leaves pooled coverage unchanged (§6.8, §9.8).

## 5.3 Pre-publish features

The deployed architecture consumes four pre-publish features at $t_\text{pub} = $ Friday 16:00 ET (or pre-holiday close): Friday close $P_{t^-}(s)$, weekend factor return $r^{\text{factor}}_t(s)$, vol-index close $v_t(s)$ (drives the `high_vol` regime via §5.5's VIX-percentile cascade), and the long-weekend flag $\ell_t \in \{0, 1\}$ (drives the `long_weekend` regime). Rolling 20-day realised vol $\hat\sigma^{\text{20d}}_t$ is used downstream of inference for the §6.3.2 realised-move tertile stratification only. The factor return requires the futures or BTC price at $t = $ Monday 09:30 ET; Globex futures and BTC trade through the weekend, so $F_t(s)$ is observable at $t_\text{pub} + 65.5\text{h}$. In live deployment, the factor return is the *only* feature requiring post-publish computation.

## 5.4 Factor and volatility-index switchboards

The per-symbol mappings are static (`src/soothsayer/backtest/panel.py`):

| Symbol | Factor | Vol index |
|---|---|---|
| SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD | `ES=F` (E-mini S&P futures) | `^VIX` |
| MSTR (pre 2020-08-01) | `ES=F` | `^VIX` |
| MSTR (2020-08-01 onward) | `BTC-USD` | `^VIX` |
| GLD | `GC=F` (gold futures) | `^GVZ` |
| TLT | `ZN=F` (10-year T-note futures) | `^MOVE` |

The MSTR factor pivot at 2020-08-01 marks MicroStrategy's first Bitcoin treasury purchase — a structural break in the asset's economic exposure that turned what had been a software equity (driven by tech-equity factors) into a leveraged BTC-treasury vehicle (driven by spot BTC). Holding ES=F as the factor across that pivot would mis-attribute the post-2020 weekend signal; the switchboard is reconciled to the asset's actual driver post-break. The vol-index choices are evidence-driven: an early V1b pass found that fitting the F1 log-log sigma regression with VIX yielded $\hat\beta \approx 0.55$ for GLD and $\hat\beta \approx 0.94$ for TLT, well below the equity-class mean ($\hat\beta \approx 1.5$). Substituting GVZ and MOVE lifted $\hat\beta$ into the equity range and improved coverage at matched bandwidth.

## 5.5 The regime labeler $\rho$

$\rho: \mathcal{F}_t(s) \to \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ is a strict priority cascade (`src/soothsayer/backtest/regimes.py`):

1. **`high_vol`** — VIX at Friday close in the top quartile of its trailing 252-trading-day window. The threshold is global (uses VIX even for non-equity symbols).
2. **`long_weekend`** — `gap_days` $\ge 4$. Applied only if `high_vol` did not match.
3. **`normal`** — all other weekends.

Sample sizes on the 5,996-row raw panel: normal 3,934 (65.6%), high_vol 1,432 (23.9%), long_weekend 630 (10.5%).

On the **overnight** panel the partition is re-derived (§4.3.1): `long_weekend` has no analog and is dropped; `high_vol` is retained but its trailing-VIX quartile uses a 252-trading-day lookback (≈1 year, matching the weekend's 52-weekend window); and `earnings_night` is added as the top-priority bucket — a gap is `earnings_night` iff a scheduled earnings release (by `amc`@$t_0$ / `bmo`@$t_1$ session timing) falls inside it. Because earnings timing is known a priori, this is the architecture's only *calendar-conditioned* regime: the band pre-widens for a scheduled event rather than reacting to realised volatility (§4.3.1). Overnight sample sizes on the 22,624-row panel: normal 16,604 (73.4%), high_vol 5,791 (25.6%), earnings_night 229 (1.0%).

A separate post-hoc tertile labeler tags each weekend by realised-move z-score (calm / normal / shock); this `realized_bucket` is *not* a regime in the §3.1 sense — it depends on the realised target — and is used only for diagnostic stratification (the shock-tertile coverage ceiling reported in §9.1).

We considered two refinements that were tested and dropped: a sub-regime split of `normal` into `post_shock` / `calm` / `range_bound`, and an FOMC/CPI/NFP macro-event regressor. Neither lifted shock-tertile coverage measurably; the implied-vol indices already absorb that signal. Sub-regime granularity is retained as a next-generation candidate (§10).

## 5.6 Train/test split

Split date **2023-01-01**: weekends with `fri_ts < 2023-01-01` are calibration, the remainder is held-out OOS.

| Split | Rows | Weekends |
|---|---:|---:|
| Calibration (2014-01 → 2022-12) | 4{,}186 | 466 |
| Held-out OOS (2023-01 → 2026-04) | 1{,}730 | 173 |

The trained per-regime quantiles (§4.3) are fit from the calibration set and held *fixed* throughout OOS evaluation: no information from the 2023+ slice enters the trained quantile table. The $c(\tau)$ bumps (§4.4) are deployment-tuned on the same OOS slice — disclosed in §9.3 — and the walk-forward $\delta(\tau)$ schedule is identically zero (§4.5). The calibration row count is 4,186 after the 80-row σ̂ warm-up rule (≥8 past observations per symbol) drops the first eight weekends per ticker.

The 2023-01-01 split is conservative: it places the 2023 banking turbulence and the 2024–2025 macro transition in the held-out slice, exposing the trained quantile to material out-of-sample regime shifts. HOOD enters the per-regime quantile fit pooled across symbols within each regime (§4.3), so the per-symbol behaviour at serve time is carried by $\hat\sigma_s(t)$, not by a per-symbol quantile cell.

## 5.7 Provenance and reproducibility

All Phase 0 equity inputs are read from Scryer parquet: `yahoo/equities_daily/v1` for daily OHLCV, `yahoo/earnings/v2` for the earnings-calendar flag and BMO/AMC session timing, and `yahoo/corp_actions/v1` for the overnight ex-dividend adjustment (the trailing `/vN` is the scryer schema version, distinct from the M-series methodology generations used elsewhere in this paper). No credentials are required for the consumer path in soothsayer; upstream fetch, retry, and schema ownership live in the sibling Scryer repo.

The end-to-end calibration backtest runs under fifteen minutes from a cold cache, under one minute warm. Reproduction:

```
uv sync
uv run python scripts/run_calibration.py          # weekend panel + §6.2–§6.7 tables
uv run python scripts/build_overnight_panel.py     # overnight panel (§5.2.1)
uv run python scripts/build_overnight_artefact.py  # overnight artefact + §6.8 battery
```

`run_calibration.py` materialises `data/processed/v1b_bounds.parquet`, the per-symbol and pooled calibration surfaces, and refreshes the §6 OOS-evaluation tables; the two overnight scripts materialise the overnight panel and its calibration battery (§6.8).
