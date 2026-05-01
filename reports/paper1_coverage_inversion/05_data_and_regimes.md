# §5 — Data and Regime Labeler (draft)

This section specifies the symbol universe, the weekend-panel construction, the per-symbol factor and volatility-index switchboards introduced in §4.1, the regime labeler $\rho$ introduced in §3.1, and the train/test split underlying the §6 evaluation. All inputs are publicly available and free; the panel rebuilds end-to-end via `scripts/run_calibration.py`.

## 5.1 Symbol universe

We evaluate on $K = 10$ symbols spanning three asset classes:

| Class | Symbols | Rationale |
|---|---|---|
| US equities | SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD, MSTR | Eight underliers of the eight Solana xStocks for which Backed-issued tokenised equities trade on-chain |
| Tokenised gold | GLD | RWA-class generalisation: closed-market same as equities, distinct factor (gold futures) and vol index (GVZ) |
| Tokenised long rates | TLT | RWA-class generalisation: closed-market, distinct factor (10Y treasury futures) and vol index (MOVE) |

The eight equity tickers are the underliers of the SPYx, QQQx, AAPLx, GOOGLx, NVDAx, TSLAx, HOODx, and MSTRx tokens deployed on Solana mainnet (Backed Finance, mid-2025 launch; mint addresses verified on-chain in `docs/v5-tape.md`). They are the immediate xStock-protocol consumer set. GLD and TLT are RWA generalisation anchors — they share the closed-market structure with the equities (NYSE hours) but exercise different factors and vol indices, so a coverage-inversion primitive that calibrates well across all three classes generalises to a broader closed-market RWA universe than equity-only evaluation would justify.

We do not use the on-chain xStock prices themselves as an input or evaluation target. Backtest target prices are the *underlying-venue* (NYSE) Monday opens, fetched from Yahoo Finance daily history. The on-chain xStock TWAP is a separate signal, deferred to v2 (`docs/v2.md` §V2.1) once the V5 tape (`docs/v5-tape.md`) accumulates ≥ 150 weekends of post-launch data.

## 5.2 Weekend panel construction

Each row of the panel is a single $(s, t)$ weekend prediction window. For each symbol we walk the daily price history and, for every consecutive pair of trading days separated by a calendar gap of $\ge 3$ days (`gap_days`), emit a row with:

- `fri_close` — close of the day before the gap (Friday or pre-holiday session)
- `mon_open` — open of the day after the gap (Monday or post-holiday session)
- `gap_days` — calendar days in the gap (3 for Friday→Monday, 4 for 3-day weekend, 5 for 4-day weekend, etc.)
- `fri_vol_20d` — rolling 20-trading-day standard deviation of daily log-returns at Friday close
- `factor_ret` — weekend return of the per-symbol conditioning factor (§5.4)
- `vol_idx_fri_close` — close of the per-symbol implied-volatility index at $t_\text{pub}$ (§5.4)
- `earnings_next_week` — calendar flag from Yahoo Finance `earnings_dates` (1 if any earnings in the seven trading days following $t_\text{pub}$, else 0)
- `is_long_weekend` — 1 if `gap_days` $\ge 4$, else 0

The panel spans 2014-01-17 (first Friday on which the rolling 20-day vol is defined for all symbols) through 2026-04-17 (last full weekend before paper compilation), yielding $|\mathcal{T}_\text{hist}| = 5{,}986$ rows across the 10 symbols. The MSTR series begins 2014-01-17; the HOOD series begins 2021-08-13 (post-IPO), contributing $\sim 245$ weekends.

## 5.3 Pre-publish features

All features used by either forecaster are observable at $t_\text{pub} = $ Friday 16:00 ET (or pre-holiday close). The full feature set:

- $P_{t^-}(s)$ — Friday close (or pre-holiday close, generalising)
- $r^{\text{factor}}_t(s)$ — weekend return $\log\bigl(F_{t}(s) / F_{t^-}(s)\bigr)$ of the per-symbol conditioning factor, where $F$ is the futures or BTC contract for $s$
- $v_t(s)$ — close of the per-symbol implied-volatility index at $t_\text{pub}$
- $\hat\sigma^{\text{20d}}_t$ — rolling 20-trading-day standard deviation of daily log-returns at Friday close (used by F0; not used by F1)
- $\mathrm{earn}_t(s) \in \{0, 1\}$ — earnings calendar flag for the post-publish week
- $\ell_t \in \{0, 1\}$ — long-weekend flag (`gap_days` $\ge 4$)

The factor return $r^{\text{factor}}_t(s)$ requires the futures or BTC price at $t = $ Monday 09:30 ET. Globex-traded futures (`ES=F`, `NQ=F`, `GC=F`, `ZN=F`) and Bitcoin (`BTC-USD`) trade through the weekend, so $F_t(s)$ at Monday 09:30 is observable in real time at $t_\text{pub} + 65.5\text{h}$ — well before Monday's NYSE open. In live deployment, the factor return is the *only* feature that requires post-publish computation; in the backtest it is read from cached daily history.

## 5.4 Factor and volatility-index switchboards

The per-symbol mappings are static and module-level constants in `src/soothsayer/backtest/panel.py`:

| Symbol | Factor (`FACTOR_BY_SYMBOL`) | Vol index (`VOL_INDEX_BY_SYMBOL`) |
|---|---|---|
| SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD | `ES=F` (E-mini S&P futures) | `^VIX` |
| MSTR (pre 2020-08-01) | `ES=F` | `^VIX` |
| MSTR (2020-08-01 onward) | `BTC-USD` | `^VIX` |
| GLD | `GC=F` (gold futures) | `^GVZ` (CBOE Gold ETF Volatility Index) |
| TLT | `ZN=F` (10-year T-note futures) | `^MOVE` (ICE BofA MOVE Index) |

The MSTR factor pivot at 2020-08-01 corresponds to MicroStrategy's first Bitcoin treasury purchase; pre-pivot MSTR's price-discovery linkage to broad equities dominated, post-pivot it pivots to BTC. The pivot date is hardcoded in `panel.py:MSTR_BTC_PIVOT` and applied row-wise during panel construction.

The vol-index choices are evidence-driven: an early V1b pass found that fitting the F1 log-log sigma regression with VIX as the volatility covariate yielded $\hat\beta \approx 0.55$ for GLD and $\hat\beta \approx 0.94$ for TLT — both substantially below the equity-class mean of $\hat\beta \approx 1.5$. This indicated VIX is a weak proxy for gold and treasury volatility. Substituting GVZ (gold-options-implied volatility) for GLD and MOVE (treasury-options-implied volatility) for TLT lifted $\hat\beta$ into the equity range and improved coverage at matched bandwidth. The asset-class-appropriate volatility index is one of two ways the methodology generalises beyond equities (the other being the factor switchboard).

## 5.5 The regime labeler $\rho$

The labeler $\rho: \mathcal{F}_t(s) \to \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ is implemented in `src/soothsayer/backtest/regimes.py` as a strict priority cascade:

1. **`high_vol`** — VIX at Friday close is in the top quartile of its trailing 252-trading-day window. Computed weekend-by-weekend from the VIX time series; the rolling-quartile threshold is itself observable at $t_\text{pub}$ (uses VIX values strictly before the current Friday). The threshold is global (uses VIX even for non-equity symbols) — the regime is a market-condition flag, not a symbol-specific volatility measurement.
2. **`long_weekend`** — `gap_days` $\ge 4$ (3-day weekend, 4-day weekend, holiday bridge). Applied only if `high_vol` did not already match.
3. **`normal`** — all other weekends.

Sample sizes per regime on the $5{,}986$-weekend panel:

| Regime | $n$ | Share |
|---|---:|---:|
| `normal` | 3{,}924 | 65.6% |
| `high_vol` | 1{,}432 | 23.9% |
| `long_weekend` | 630 | 10.5% |

A separate post-hoc tertile labeler tags each weekend by realised-move z-score (calm / normal / shock) using $|z| = |\log(P_t / P_{t^-})| / \hat\sigma^{\text{20d}}_t$. This `realized_bucket` is *not* a regime in the §3.1 sense — it depends on the realised target — and is used only for diagnostic stratification (the shock-tertile coverage ceiling reported in §9.2). It never enters $\rho$ or the calibration surface.

We considered two refinements that were tested and dropped from the v1 deployment: a sub-regime split of `normal` into `post_shock` / `calm` / `range_bound`, and an FOMC/CPI/NFP macro-event regressor (`reports/v1b_macro_regressor.md`). Neither lifted shock-tertile coverage measurably; the implied-vol indices already absorb the macro-uncertainty signal those refinements were designed to capture. Sub-regime granularity is retained as a v2 candidate; the empirical motivation for prioritising it is in §10.

## 5.6 Train/test split

The split date is **2023-01-01**: weekends with `fri_ts < 2023-01-01` are the calibration set, the remainder are the held-out OOS evaluation set.

| Split | Rows | Weekends | Ticker-coverage |
|---|---:|---:|---|
| Calibration (2014-01 → 2022-12) | 4{,}266 | 466 | All 10 (HOOD partial; begins 2021-08) |
| Held-out OOS (2023-01 → 2026-04) | 1{,}720 | 172 | All 10 |

The split is temporally disjoint at the surface-construction level. The calibration surface $S^f$ is built from the 4,266 calibration-set rows (per-(symbol, regime, forecaster, claimed-quantile) cells) and held *fixed* throughout the OOS evaluation. Every OOS row is served through the frozen surface: no parameter, threshold, or grid point is updated using OOS data. The per-target buffer schedule (§4.3) was tuned on this same OOS slice using the methodology of `reports/v1b_buffer_tune.md` — this is disclosed as a (then) sample-size-one calibration step in §9.4 and partially closed by the walk-forward stability evidence (`reports/v1b_walkforward.md`, summarised in §9.4) showing the deployed buffer values land at the cross-split mean.

The 2023-01-01 split point is conservative in two respects: (i) it places the 2023 banking turbulence and the 2024–2025 macro-regime transition in the held-out slice, exposing the surface to material out-of-sample regime shifts; (ii) it leaves only $\sim 245$ HOOD rows in the calibration set (HOOD IPO'd in 2021), so the per-symbol surface for HOOD is the leanest of all ten symbols and exercises the pooled-fallback path more often than the others — a stress test for the fallback design.

## 5.7 Provenance and reproducibility

All Phase 0 equity inputs are now read from Scryer parquet: `yahoo/equities_daily/v1` for daily OHLCV and `yahoo/earnings/v1` for the earnings-calendar flag. No credentials are required for the consumer path in soothsayer; upstream fetch, retry, and schema ownership live in the sibling Scryer repo.

The end-to-end calibration backtest runs under fifteen minutes on a 2024 M3 MacBook from a cold cache, and under one minute when the daily-history cache is warm. Reproduction:

```
uv sync
cp .env.example .env       # optional; only required for live on-chain workloads
uv run python scripts/run_calibration.py
```

The single script materialises `data/processed/v1b_bounds.parquet` (the bounds table at every $(s, t, q)$), `reports/tables/v1b_calibration_surface.csv` and `v1b_calibration_surface_pooled.csv` (the per-symbol and pooled surfaces), and refreshes the §6 OOS-evaluation tables. A consumer in possession of these three artifacts can independently verify any served `PricePoint` against the receipt fields specified in §4.5.
