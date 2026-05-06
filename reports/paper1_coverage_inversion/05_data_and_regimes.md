# §5 — Data and Regime Labeler

This section specifies the symbol universe, the weekend-panel construction, the per-symbol factor and volatility-index switchboards, the regime labeler $\rho$, and the train/test split underlying §6. All inputs are publicly available and free; the panel rebuilds end-to-end via `scripts/run_calibration.py`.

## 5.1 Symbol universe

We evaluate on $K = 10$ symbols spanning three asset classes: eight US equities (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD, MSTR), tokenised gold (GLD), and tokenised long rates (TLT). The eight equity tickers are the underliers of the SPYx, QQQx, AAPLx, GOOGLx, NVDAx, TSLAx, HOODx, and MSTRx tokens deployed on Solana mainnet (Backed Finance; mint addresses verified in `docs/v5-tape.md`). GLD and TLT are RWA generalisation anchors — they share the closed-market structure with the equities (NYSE hours) but exercise different factors and vol indices, so a primitive that calibrates well across all three classes generalises to a broader closed-market RWA universe than equity-only evaluation would justify.

We do not use the on-chain xStock prices themselves as input or evaluation target. Backtest target prices are the *underlying-venue* (NYSE) Monday opens, fetched from Yahoo Finance. The on-chain xStock TWAP is deferred to §10.1's on-chain-TWAP forecaster candidate, once the forward-cursor tape accumulates ≥ 150 weekends post-launch.

## 5.2 Weekend panel construction

Each row is a single $(s, t)$ weekend prediction window. For each symbol we walk daily price history and, for every consecutive pair of trading days separated by a calendar gap of $\ge 3$ days, emit a row with: `fri_close`, `mon_open`, `gap_days`, `fri_vol_20d` (rolling 20-trading-day std of daily log-returns at Friday close), `factor_ret` (weekend return of the per-symbol conditioning factor), `vol_idx_fri_close`, `earnings_next_week` (Yahoo `earnings_dates` flag), and `is_long_weekend` (`gap_days` $\ge 4$).

The panel spans 2014-01-17 (first Friday on which rolling 20-day vol is defined for all symbols) through 2026-04-17, yielding $|\mathcal{T}_\text{hist}| = 5{,}986$ rows. MSTR begins 2014-01-17; HOOD begins 2021-08-13 (post-IPO), contributing ~245 weekends.

## 5.3 Pre-publish features

All features are observable at $t_\text{pub} = $ Friday 16:00 ET (or pre-holiday close): $P_{t^-}(s)$ Friday close, $r^{\text{factor}}_t(s)$ weekend factor return, $v_t(s)$ vol-index close, $\hat\sigma^{\text{20d}}_t$ rolling realised vol, $\mathrm{earn}_t(s) \in \{0, 1\}$ earnings flag, and $\ell_t \in \{0, 1\}$ long-weekend flag. The factor return requires the futures or BTC price at $t = $ Monday 09:30 ET; Globex futures and BTC trade through the weekend, so $F_t(s)$ is observable at $t_\text{pub} + 65.5\text{h}$. In live deployment, the factor return is the *only* feature requiring post-publish computation.

## 5.4 Factor and volatility-index switchboards

The per-symbol mappings are static (`src/soothsayer/backtest/panel.py`):

| Symbol | Factor | Vol index |
|---|---|---|
| SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD | `ES=F` (E-mini S&P futures) | `^VIX` |
| MSTR (pre 2020-08-01) | `ES=F` | `^VIX` |
| MSTR (2020-08-01 onward) | `BTC-USD` | `^VIX` |
| GLD | `GC=F` (gold futures) | `^GVZ` |
| TLT | `ZN=F` (10-year T-note futures) | `^MOVE` |

The MSTR factor pivot at 2020-08-01 corresponds to MicroStrategy's first Bitcoin treasury purchase. The vol-index choices are evidence-driven: an early V1b pass found that fitting the F1 log-log sigma regression with VIX yielded $\hat\beta \approx 0.55$ for GLD and $\hat\beta \approx 0.94$ for TLT, well below the equity-class mean ($\hat\beta \approx 1.5$). Substituting GVZ and MOVE lifted $\hat\beta$ into the equity range and improved coverage at matched bandwidth.

## 5.5 The regime labeler $\rho$

$\rho: \mathcal{F}_t(s) \to \{\texttt{normal}, \texttt{long\_weekend}, \texttt{high\_vol}\}$ is a strict priority cascade (`src/soothsayer/backtest/regimes.py`):

1. **`high_vol`** — VIX at Friday close in the top quartile of its trailing 252-trading-day window. The threshold is global (uses VIX even for non-equity symbols).
2. **`long_weekend`** — `gap_days` $\ge 4$. Applied only if `high_vol` did not match.
3. **`normal`** — all other weekends.

Sample sizes on the 5,986-weekend panel: normal 3,924 (65.6%), high_vol 1,432 (23.9%), long_weekend 630 (10.5%).

A separate post-hoc tertile labeler tags each weekend by realised-move z-score (calm / normal / shock); this `realized_bucket` is *not* a regime in the §3.1 sense — it depends on the realised target — and is used only for diagnostic stratification (the shock-tertile coverage ceiling reported in §9.1).

We considered two refinements that were tested and dropped: a sub-regime split of `normal` into `post_shock` / `calm` / `range_bound`, and an FOMC/CPI/NFP macro-event regressor. Neither lifted shock-tertile coverage measurably; the implied-vol indices already absorb that signal. Sub-regime granularity is retained as a next-generation candidate (§10).

## 5.6 Train/test split

Split date **2023-01-01**: weekends with `fri_ts < 2023-01-01` are calibration, the remainder is held-out OOS.

| Split | Rows | Weekends |
|---|---:|---:|
| Calibration (2014-01 → 2022-12) | 4{,}186 | 466 |
| Held-out OOS (2023-01 → 2026-04) | 1{,}730 | 173 |

The 12 trained per-regime quantiles (§4.3) are fit from the calibration set and held *fixed* throughout OOS evaluation: no information from the 2023+ slice enters the trained quantile table. The 4 $c(\tau)$ bumps (§4.4) are deployment-tuned on the same OOS slice — disclosed in §9.3 — but three of the four are essentially identity ($c \in \{1.000,\,1.000,\,1.003\}$ at $\tau \in \{0.68,\,0.85,\,0.99\}$) so only $c(0.95) = 1.079$ carries meaningful OOS information; the walk-forward $\delta(\tau)$ schedule is identically zero (§4.5). The calibration row count is 4,186 after the 80-row σ̂ warm-up rule (≥8 past observations per symbol) drops the first eight weekends per ticker.

The 2023-01-01 split is conservative: it places the 2023 banking turbulence and the 2024–2025 macro transition in the held-out slice, exposing the trained quantile to material out-of-sample regime shifts. HOOD enters the per-regime quantile fit pooled across symbols within each regime (the trained quantile does not stratify by symbol — see §4.3), so the calibration thinness for HOOD is absorbed into the pooled regime bin rather than producing a per-symbol fallback; the per-symbol behaviour at serve time is carried by $\hat\sigma_s(t)$, not by a per-symbol quantile cell. The §7.2 M3 row confirms further per-symbol stratification thins each cell to $N \approx 50$–$300$ and degrades Christoffersen.

## 5.7 Provenance and reproducibility

All Phase 0 equity inputs are read from Scryer parquet: `yahoo/equities_daily/v1` for daily OHLCV and `yahoo/earnings/v1` for the earnings-calendar flag (the trailing `/v1` is the scryer schema version, distinct from the M-series methodology generations used elsewhere in this paper). No credentials are required for the consumer path in soothsayer; upstream fetch, retry, and schema ownership live in the sibling Scryer repo.

The end-to-end calibration backtest runs under fifteen minutes from a cold cache, under one minute warm. Reproduction:

```
uv sync
uv run python scripts/run_calibration.py
```

This single script materialises `data/processed/v1b_bounds.parquet`, the per-symbol and pooled calibration surfaces, and refreshes the §6 OOS-evaluation tables.
