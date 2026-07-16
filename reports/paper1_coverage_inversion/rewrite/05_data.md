# §5 — Data

## 5.1 Universe

We evaluate on $K = 10$ symbols spanning three asset classes: eight US equities (SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD, MSTR) — the underliers of the Backed Finance xStock tokens on Solana mainnet — plus tokenised gold (GLD) and long rates (TLT), which share the closed-market structure but exercise different factors and volatility indices, so calibration across all three classes evidences generalisation beyond an equity-only universe. The evaluation target is the underlying-venue price — NYSE Monday opens on the weekend panel, next-day opens on the overnight panel — not the on-chain token price: we predict the underlier the token settles against.

## 5.2 Panels

Each row is one $(s, t)$ close→open window carrying the Friday (or prior-day) close, the next open, the per-symbol factor return, the vol-index close, the calendar-gap length, and an earnings flag (full schema in Appendix A). The **weekend panel** admits pairs of trading days separated by $\ge 3$ calendar days: 5,996 rows across 639 weekend dates, 2014-01-17 → 2026-04-24 (HOOD contributes 246 post-IPO weekends), of which 5,916 remain evaluable after the σ̂ warm-up drop (§4.3). The **overnight panel** applies the same pipeline with the gap selector admitting consecutive-trading-day pairs (§4.7): 22,624 rows across 2,412 weeknights, ≈3.8× the weekend panel. Two cadence-specific treatments apply overnight: each earnings release is assigned to the single gap it drives via BMO/AMC session timing (scryer `yahoo/earnings/v2`), and the 241 ex-dividend-morning opens are reconstructed to their cum-dividend level from `yahoo/corp_actions/v1`, removing the only systematic price-level artefact (Appendix B).

## 5.3 Pre-publish features

The architecture consumes four features fixed at publish time (Friday 16:00 ET or pre-holiday close): the close $P_{t^-}(s)$, the vol-index close (drives `high_vol`), the long-weekend flag, and the factor return $r^{\text{factor}}_t(s)$. Because Globex futures and BTC trade through the weekend, the factor return is observable at serve time while the reference market is closed — in live deployment it is the *only* input requiring post-publish computation.

## 5.4 Factor and volatility-index switchboards

The per-symbol mappings are static:

| Symbol | Factor | Vol index |
|---|---|---|
| SPY, QQQ, AAPL, GOOGL, NVDA, TSLA, HOOD; MSTR pre-2020-08 | `ES=F` | `^VIX` |
| MSTR (2020-08-01 onward) | `BTC-USD` | `^VIX` |
| GLD | `GC=F` | `^GVZ` |
| TLT | `ZN=F` | `^MOVE` |

The MSTR pivot at 2020-08-01 marks MicroStrategy's first Bitcoin treasury purchase — a structural break that turned a software equity into a leveraged BTC-treasury vehicle, so the factor is reconciled to the asset's actual post-break driver (selection evidence in Appendix D).

The factor return $r^{\text{factor}}_t(s)$ is measured over the closed window itself — from the factor's Friday 16:00 ET close to its contemporaneous print at serve time (the latest Globex/BTC quote when the band is read) — so it spans the window rather than being fixed at publish; it is the only input the point estimator requires post-publish (§5.3).

## 5.5 The regime labeler $\rho$

On the weekend panel, $\rho$ is a strict priority cascade: **`high_vol`** — VIX at Friday close in the top quartile of its trailing 252-trading-day window; else **`long_weekend`** — `gap_days` $\ge 4$; else **`normal`**. Shares on the 5,996-row panel: normal 3,934 (65.6%), high_vol 1,432 (23.9%), long_weekend 630 (10.5%).

On the overnight panel the partition is re-derived: `long_weekend` has no analog and is dropped; `high_vol` keeps the 252-trading-day VIX lookback; and **`earnings_night`** is added as the top-priority bucket — a gap is `earnings_night` iff a scheduled release (after-close at $t_0$ or before-open at $t_1$) falls inside it. Because the release date and session are public, this is the architecture's only calendar-conditioned regime (§4.7). Shares on the 22,624-row panel: normal 16,604 (73.4%), high_vol 5,791 (25.6%), earnings_night 229 (1.0%).

## 5.6 Train/test split

Weekends with `fri_ts` before **2023-01-01** are calibration; the remainder is held-out out-of-sample.

| Split | Rows | Weekends |
|---|---:|---:|
| Calibration (2014-01 → 2022-12) | 4,186 | 466 |
| Held-out OOS (2023-01 → 2026-04) | 1,730 | 173 |

The trained per-regime quantiles are fit on the calibration set and held *fixed* throughout evaluation: no post-2023 information enters the quantile table. The $c(\tau)$ bumps are deployment-tuned on the OOS slice — disclosed in §8 — and $\delta(\tau) \equiv 0$ (§4.5). The split places the 2023 banking turbulence and the 2024–2025 macro transition in the held-out slice.

## 5.7 Provenance

All inputs are read from scryer parquet — `yahoo/equities_daily/v1`, `yahoo/earnings/v2`, `yahoo/corp_actions/v1` — with fetch, retry, and schema ownership in the sibling scryer repository. **Data availability:** all upstream data is publicly available and free (Yahoo Finance daily bars and earnings calendar, CME futures, VIX/GVZ/MOVE, BTC-USD). Soothsayer consumes pre-fetched parquet with `_fetched_at` cutoffs preserved in the metadata; rebuild commands and repository details are in Appendix A.

## 5.8 Forward tape

The deployed artefact is frozen and content-addressed (SHA-256, freeze date 2026-05-04) and is evaluated on a forward tape appended weekly and never used to re-select any component. As of 2026-07-10 the tape covers 11 post-freeze weekends (110 rows): pooled Kupiec passes at all four anchors and 10/10 symbols pass per-symbol Kupiec at $\tau = 0.95$ (`reports/m6_forward_tape_11weekends.md`). At $N = 11$ the per-symbol tape is not yet powered, however: two symbols (HOOD and MSTR) each realise a 18.2% violation rate (2 of 11) at $\tau = 0.95$, and Kupiec accepts at that $n$ only because the per-symbol test has no power to reject — the per-symbol forward claim rests on accumulation, not on the current pass.
