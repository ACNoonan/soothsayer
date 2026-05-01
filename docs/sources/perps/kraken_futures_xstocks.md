# `Kraken Futures — xStock perps (10 contracts)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://support.kraken.com/articles/xstocks-perps-kraken-pro` (accessed 2026-04-29; the 10-contract list, 20× max leverage, 24/7 trading claim), `https://support.kraken.com/articles/4844359082772-linear-multi-collateral-derivatives-contract-specifications` (accessed 2026-04-29; the load-bearing methodology surface — funding rate hourly, ±0.25% cap, mark = Index + EMA_30s(Impact Mid - Index), funding-multiplier `n=24`), `https://blog.kraken.com/product/quick-primer-on-funding-rates` (cited via 2026-04-29 search; the funding-rate pedagogy), **live scryer tape** at `dataset/kraken/funding/v1/symbol=PF_*XUSD/year=*/month=*.parquet`, the V3 funding-rate signal investigation in [`reports/archived/v3_funding_signal.md`](../../../reports/archived/v3_funding_signal.md).
**Version pin:** **Kraken xStock Perps (linear multi-collateral)** — 10 contracts as of 2026-04-29: `SPYx, QQQx, GLDx, TSLAx, AAPLx, NVDAx, GOOGLx, HOODx, MSTRx, CRCLx`. Up to 20× leverage. Funding **settles every 1 hour at the end of the hour** (despite our prior catalog text referencing "8h funding" — empirically and per current docs, funding is hourly, not 8-hourly; the "8h" in [`docs/data-sources.md`](../../data-sources.md) §5 line 122 is stale and should be corrected). Operator: per the support article footer, "© 2011 - 2026 Payward, Inc."; the **Payward Digital Solutions / Bermuda** path was previously surfaced in soothsayer notes but is not stated on the current support page in our 2026-04-29 read — separate cross-reference needed (see §6).
**Role in soothsayer stack:** `comparator (off-hours signal, supplementary)` — Kraken's xStock perps are the cleanest free 24/7 venue with both a **mark price** (continuous quotes) and a **funding rate** (market-implied next-window forecast). Per [`docs/data-sources.md`](../../data-sources.md) §5 lines 124-132, Kraken Perp funding was **the first hypothesised weekend Monday-gap forecaster** (V3 hypothesis H9). V3 testing rejected this at our sample size; the funding signal is retained as supplementary, not primary.
**Schema in scryer:** **✅ live.** `dataset/kraken/funding/v1/symbol=PF_*XUSD/year=YYYY/month=MM.parquet` (schema `kraken_funding.v1`). Earliest data: 2025-12-17 (SPY/QQQ/GLD launch); other 7 xStocks back-filled from 2026-02-06. Mark / spot price tape is **not yet captured** — only funding rate is in scryer today.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule (mark price)

Per Kraken's contract specifications (accessed 2026-04-29):

> "Mark Price = Index Price + EMA_{30 seconds}(Impact Mid Price − Index Price), with the premium capped at 1% for perpetuals."

In rare circumstances where the Index Price is unavailable: "the Mark Price will be equal to the Impact Mid Price."

The **Index Price** is constructed from a "Real Time Platform Ticker" and "Real Time Index" — the support page does not detail per-contract index construction beyond this label. For xStock contracts, the index is presumably constructed against US-equity-market underlier prices (SPY, QQQ, ...) during regular session and against extended-hours / overnight pricing or stale-hold during closed-market windows. **The exact off-hours index construction methodology is not surfaced in public docs** — this is the load-bearing weekend question (see §6).

The **Impact Mid Price** is Kraken's measure of the actionable mid: the midpoint of the bid/ask weighted by sufficient depth to absorb a reference notional. The 30-second EMA of `(Impact Mid - Index)` smooths short-term basis fluctuations into the published mark, while the 1% premium cap prevents the mark from drifting more than 1% from the index.

### 1.2 Cadence / publication schedule

**Funding rate cadence: hourly.** Per the contract specifications:

> "the time-weighted average premium, and standardised to a per-hour basis"
> "Funding Rate Multiplier n = 24"
> "Settlement: Every 1 hour at the end of the hour"
> "Premium values calculated from minutely perpetual contract prices (60 observations) using an Impact Mid"
> "The Average Premium is calculated as the average of the mid 30 values recorded from the above 60 observations."

The hourly funding rate is computed from 60 minutely Impact Mid observations within the hour, sorted, and averaged across the middle 30 (i.e., a 30-of-60 mid-mean — robust to outliers at the head and tail of the sorted observations). The published rate is the 30-of-60 average premium, time-weighted, divided by 24 to express per-hour.

**Funding rate cap:** ±0.25% per hour, equivalent to ±6% per 24-hour period at the ±0.25%-per-hour cap. **Confirmed empirically** — our scryer tape's `relative_funding_rate` for SPYx (2,999 hourly observations 2025-12-17 → 2026-04-21) shows max +0.002500 / min −0.002500 (= ±0.25%). The cap is binding in the historical record, suggesting the underlying premium has historically reached the cap (i.e., the scaled-funding-rate has saturated, meaning the unconstrained premium exceeds 0.25%/hr).

**Mark price cadence:** continuous (sub-second per Kraken's matching engine cadence). Mark price tape is not yet captured in scryer (only funding is); add to scryer wishlist when needed for §3 reconciliation.

**Settlement cadence:** funding settles "Every 1 hour at the end of the hour" or "when user changes net open position (whichever occurs first)." Continuous accrual between settlements.

### 1.3 Fallback / degraded behavior

- **Index unavailable** — Mark Price defaults to Impact Mid Price (no premium adjustment). This is the single-source fallback.
- **Premium > 1% cap** — the cap clips the EMA term in the Mark formula. The published mark cannot deviate more than 1% from the index.
- **Funding rate > ±0.25% cap** — the cap clips the published rate. **Empirically reached** in our tape.
- **Below-quorum index sources** — the support page does not detail what happens if the underlying NMS quote feeds for the equity component go offline.
- **Settlement at position-close** — if a user closes their position mid-hour, the accrued funding settles at close, not at the next hourly boundary.

### 1.4 Schema / wire format

The Kraken Futures REST API exposes `/derivatives/api/v3/historical-funding-rates` per [`docs/data-sources.md`](../../data-sources.md) §5 line 126. The scryer schema `kraken_funding.v1` (live) has:

| Column | Type | Notes |
|---|---|---|
| `symbol` | string | `PF_<ASSET>USD`, e.g., `PF_SPYXUSD` |
| `ts` | timestamp(UTC) | hourly boundary |
| `funding_rate` | f64 | absolute funding rate (per Kraken's published value, USD-denominated) |
| `relative_funding_rate` | f64 | rate as a fraction of the underlying price (capped at ±0.25%) |
| `_schema_version`, `_fetched_at`, `_source`, `_dedup_key` | — | scryer metadata |

The **distinction between `funding_rate` and `relative_funding_rate`** is operational: `relative_funding_rate` is the per-hour rate fraction (the per-hour cost a long pays a short, expressed as a percent of position notional); `funding_rate` is the absolute USD amount per unit of contract. Soothsayer's V3 hypothesis testing used `relative_funding_rate`; it's the right column for "funding as a Monday-gap signal" framing.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet (funding tape):** `dataset/kraken/funding/v1/symbol=PF_*XUSD/year=YYYY/month=MM.parquet`. ✅ live since the cutover; per-asset partitioning. All 10 xStock perps in the tape with hourly cadence (3600s ± 0s median delta, occasional ~7200s gaps observed in the SPYx tape per probe 2026-04-29). Earliest: SPY/QQQ/GLD from 2025-12-17 launch; other 7 from 2026-02-06.
- **Mark / spot price tape:** **not yet in scryer.** [`docs/data-sources.md`](../../data-sources.md) §5 line 125 references `/derivatives/api/v3/tickers` for mark price. Adding to scryer would close the §3 mark-vs-funding reconciliation. **Hand-off:** scryer wishlist add — schema `kraken_perp_ticker.v1` with `(symbol, ts, mark_price, last_price, ask, bid, volume_24h)`.
- **V3 funding-signal investigation:** [`reports/archived/v3_funding_signal.md`](../../../reports/archived/v3_funding_signal.md) is the canonical historical analysis. **102 (weekend, ticker) rows** across 8 xStock underliers, earliest Kraken listing 2025-12-17 (SPY/QQQ/GLD) and 2026-02-06 (others). Pooled δ = +0.01257 (SE 0.02624, t = +0.479, p = 0.6331); per-ticker p-values all > 0.10. **The V3 verdict was FAIL** — funding is not adding meaningful signal at this sample size. ΔR² = +0.23 percentage points (well below the 2-pp gate).
- **Earliest history:** SPY/QQQ/GLD have ~12 weekends each by April 2026; other 7 perps have ~6 weekends. The V3 sample-size gate is the load-bearing constraint on signal detectability — see §3.

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| Funding rate cap is ±0.25% per hour. | Confirmed empirically — SPYx tape (2,999 hourly observations, 2025-12-17 → 2026-04-21) shows max +0.002500 / min −0.002500 in `relative_funding_rate`. Cap is binding (i.e., the underlying premium has reached the cap historically). | **confirmed** |
| Funding settles every 1 hour at the end of the hour. | Confirmed empirically — median Δt between consecutive `ts` rows is 3600s (1 hour); 75th percentile is 3600s. Some ~7200s gaps observed (2-hour ones, plausibly: ingestion gap, exchange downtime, or scryer back-fill discontinuity). | **confirmed (with occasional gaps)** |
| Mark price = Index + EMA_30s(Impact Mid - Index), capped at 1% premium. | **Unmeasurable from current scryer tape** — mark price tape not yet captured. Confirmed structurally per docs. **TODO when scryer adds `kraken_perp_ticker.v1`.** | **confirmed (by docs), unmeasured** |
| Funding rate = the 30-of-60 minute-mid mean of premium, time-weighted, divided by 24. | Confirmed structurally per docs. **Unmeasurable from soothsayer side** without per-minute Kraken Impact-Mid tape — this is granularity Kraken does not publish. | **confirmed (by docs), unmeasurable** |
| Funding rate at Sunday-evening predicts the Monday-open gap for the underlying, beyond what BTC / ES / sector ETF returns predict (H9). | **Contradicted at our sample size.** [`reports/archived/v3_funding_signal.md`](../../../reports/archived/v3_funding_signal.md): pooled δ = +0.01257 (p = 0.6331), ΔR² = +0.23 pp. **Per-ticker:** all 8 individual-ticker p-values > 0.10. The V3 gate (δ significant at 5% AND ΔR² > 2 pp) failed on both criteria. **At sample sizes of 102 weekend-rows, the funding-as-Monday-gap-predictor signal is undetectable.** | **contradicted (V3 FAIL)** |
| Funding rate carries information about the **direction** of weekend basis (positive = perp paying long, negative = short paying long). | Confirmed structurally — the rate's sign is interpretable. The per-ticker mean rates in our tape (e.g., SPYx mean −0.000117, max +0.002500, min −0.002500) show predominantly-negative rates: longs are typically receiving from shorts on SPYx perp basis. This is consistent with a "perp generally trades at a slight discount to spot" pattern over our window. | **confirmed (qualitative)** |
| Kraken xStock perps are 24/7 — they keep trading through US-equity-market closed hours. | Confirmed by the support page ("can be traded 24/7, including weekends and holidays") and by the continuous funding-tape cadence (no Saturday/Sunday gaps in the funding tape). | **confirmed** |
| Up to 20× max leverage. | Confirmed by the support page. | **confirmed** |
| Operator entity is Payward Digital Solutions, Bermuda-licensed. | **Stale citation** — [`docs/data-sources.md`](../../data-sources.md) §5 line 110 references this; the current Kraken support page's footer says only "© 2011 - 2026 Payward, Inc." The Payward Digital Solutions / Bermuda specificity was sourced previously and is not on the page accessed today. **Re-verify gated as §6 task.** | **stale, needs re-verification** |
| Funding cadence is 8 hours. | **Contradicted** — empirically and per current Kraken docs, funding is **hourly** (cadence median 3600s; docs explicit "n = 24" multiplier per hour). The "8h" reference in [`docs/data-sources.md`](../../data-sources.md) §5 line 122 is stale and should be corrected to "1h." | **contradicted** |
| The funding rate is a leading or lagging signal for the Monday gap. | **Unmeasurable as either at our sample size.** V3 found undetectable signal. Whether the rate becomes detectable at 200+ weekend-rows (the n that would be available in mid-2027) is a §6 question. | **unmeasurable at current sample** |

---

## 4. Market action / consumer impact

Kraken's xStock perps are the **cleanest free 24/7 off-hours signal** in our stack:

- **Soothsayer (own consumer of funding signal)** — V3 hypothesis-tested and rejected at current sample size. Funding remains a **candidate input** for v2-paper re-evaluation when sample size grows (per [`docs/data-sources.md`](../../data-sources.md) §5 line 132). The hypothesis is preserved, not abandoned.
- **Drift Protocol (perps comparator)** — Drift v2 also runs perps with mark-vs-oracle deviation logic. Whether Drift's xStock-class markets exist and how their mark+funding compare to Kraken's is a §6 open question. **TODO when scryer adds drift_perp_oracle_tape.v1.**
- **Hyperliquid Perps** — separate continuous-quoting venue; cross-reference to [`oracles/hyperliquid_perps.md`](hyperliquid_perps.md) (this batch) — Hyperliquid's mark vs Kraken's mark on xStock-equivalent positions is a comparator question. Soothsayer has no Hyperliquid tape in scryer.
- **MarginFi / Kamino / Drift / Save / Loopscale / Jupiter Lend** — none consume Kraken Perp prices directly as oracle inputs; Kraken Perp is a *signal* (funding implies forward gap expectation, mark implies live-fair-value), not an *oracle source* in these protocols.
- **Paper 1 §1 framing** — Kraken xStock perps are the **only-direct-tradable-24/7-xStock-exposure venue** soothsayer can reference. The funding rate is the "market-implied weekend pricing" — when Sunday's perp funding rate is high, the market is pricing a skew that soothsayer's empirical band should plausibly capture; when funding is low/zero, the market is not pricing a skew and a wide soothsayer band is excessive. This is the "market-implied benchmark" framing for §1 / §2 even when the signal is too noisy at our sample size.
- **Paper 3 §6 / §7** — Kraken Perp basis (mark - underlier) at the moment of any liquidation event is a real-time market-implied "forced-sale fair value" — a comparator to soothsayer's served band for liquidation pricing. **TODO when both `kamino/liquidations/v1` lands AND `kraken_perp_ticker.v1` lands** (the second is gated on scryer add — currently only funding is captured).
- **Public dashboard (Phase 2)** — Kraken Perp mark + funding is the cleanest "what does the market actually price the xStock at right now (off-hours)?" comparator alongside soothsayer's served band. Visually simple: same axis, two values, real-time.

---

## 5. Known confusions / version pitfalls

- **Funding cadence is 1h, not 8h.** [`docs/data-sources.md`](../../data-sources.md) §5 line 122 cites "8h funding" — this is stale. Empirically and per current Kraken docs, funding is hourly. Update on next data-sources edit pass.
- **Funding rate cap (±0.25%/h) is binding empirically.** Code that assumes "the funding rate ranges roughly between ±0.1%" will silently miss capped observations. Always check whether your sample contains capped values.
- **Mark price ≠ Last price ≠ Index price.** Three distinct concepts:
  - Mark price = Index + EMA_30s premium (capped) — used for liquidation triggers and unrealised PnL.
  - Last price = most recent traded price on the perp.
  - Index price = the underlying-equity-market reference, constructed off-platform.
- **`relative_funding_rate` vs `funding_rate`.** Use `relative_funding_rate` (per-hour fraction of position) for "funding-as-signal" analyses; use `funding_rate` (absolute USD per contract) for cost calculations.
- **Per-asset funding history starts at different dates.** SPY/QQQ/GLD launched 2025-12-17; AAPL/HOOD/MSTR/NVDA/GOOGL/TSLA from 2026-02-06; CRCL is most recent. Cross-asset analyses must filter to a common-history window.
- **`PF_<ASSET>USD` vs `PI_<ASSET>USD`.** PF = perpetual forward (the perp); PI = perpetual inverse (crypto-collateralised, not used for xStocks). The xStock contracts are PF.
- **24/7 trading ≠ 24/7 high liquidity.** Kraken's xStock perps are 24/7 tradable but liquidity during US-equity-closed hours is meaningfully lower; the Impact Mid price reference is degraded during low-liquidity windows.
- **Bermuda licensing claim.** The "Payward Digital Solutions, Bermuda" framing was previously surfaced; the current Kraken support page's footer is "© 2011 - 2026 Payward, Inc." Don't conflate Payward Inc. with a Bermuda-licensed sub-entity without re-verification.
- **The "30-of-60 minute mid" rule is robust to outliers.** A burst of an unusual Impact Mid in the first or last 15 minutes of an hour will be discarded. This is a deliberate methodology choice; the funding rate is not the simple "average of all 60 minutes."
- **Settlement at position-close changes the realised funding.** Users who close mid-hour pay only the elapsed fraction; the published `funding_rate` row applies to the full hour. Consumer code computing "user's realised funding" must integrate over the user's actual position-time.

---

## 6. Open questions

1. **What is Kraken's index-construction methodology for xStock perps during US-equity-market closed hours?** **Why it matters:** the entire mark-price formula chains through the Index Price; if the off-hours index is itself stale-held or extrapolated, soothsayer's "Kraken Perp mark vs underlier" comparison is structural rather than empirical. **Gating:** Kraken support deeper docs probe + outreach.
2. **Re-verify Payward Digital Solutions / Bermuda licensing claim.** **Why it matters:** regulatory framing and the "Bermuda-licensed" specificity affect any soothsayer commentary on the venue. **Gating:** Kraken legal disclosure probe + cross-reference against [`docs/data-sources.md`](../../data-sources.md) §5 line 110.
3. **Add `kraken_perp_ticker.v1` to scryer wishlist.** **Why it matters:** §3 mark-vs-funding reconciliation, Paper 3 mark-vs-oracle deviation comparison, and dashboard live-mark all depend on mark price tape. Currently only funding is captured. **Gating:** scryer wishlist add (target schema: `(symbol, ts, mark_price, last_price, bid, ask, volume_24h)` from `/derivatives/api/v3/tickers`).
4. **Re-test the V3 funding-as-Monday-gap-predictor hypothesis at larger sample size.** Per [`reports/archived/v3_funding_signal.md`](../../../reports/archived/v3_funding_signal.md) line 41: keep funding as a backup input. When the funding-tape sample has 200+ weekend-rows per ticker (mid-2027 timeline), re-run V3. **Why it matters:** if the signal becomes detectable, the soothsayer methodology gets a market-implied weekend-gap regressor. **Gating:** scryer-tape accumulation + a re-run of `scripts/run_macro_regressor_ablation.py`-style analysis on the updated panel.
5. **Empirical mark-vs-soothsayer-band comparison.** **Why it matters:** at any instant during a closed-market window, Kraken's perp mark is the live "market-implied" fair value; soothsayer's served band is the empirical-coverage prediction. The reconciliation between them is the cleanest live-vs-empirical comparator. **Gating:** open question 3 + a join script.
6. **What's the actual Impact Mid notional reference Kraken uses for xStock perps?** "Impact Mid" is meaningful only at a stated notional (e.g., the mid-of-the-bid-and-ask weighted to absorb $X). Kraken's specific reference is not in the support page. **Gating:** Kraken docs depth or support outreach.
7. **Liquidity / depth profile during weekends vs weekdays.** Order book depth on the perp during the soothsayer-target weekend window is the binding consumer experience. **Gating:** order-book snapshot capture (would require WebSocket consumption — not in soothsayer; could be in scryer as `kraken_perp_orderbook.v1`).

---

## 7. Citations

- [`kraken-xstocks-perps`] Kraken. *xStocks Perps on Kraken Pro*. https://support.kraken.com/articles/xstocks-perps-kraken-pro. Accessed: 2026-04-29.
- [`kraken-perpetual-spec`] Kraken. *Linear Multi-Collateral Derivatives Contract Specifications*. https://support.kraken.com/articles/4844359082772-linear-multi-collateral-derivatives-contract-specifications. Accessed: 2026-04-29. Source for the funding-rate methodology, mark price formula, and ±0.25%/h cap.
- [`kraken-funding-blog`] Kraken. *A Quick Primer on Funding Rates*. https://blog.kraken.com/product/quick-primer-on-funding-rates. Cited via 2026-04-29 search results.
- [`kraken-cf-benchmarks`] CF Benchmarks. *CF Bitcoin Kraken Perpetual Funding Rate Index*. https://www.cfbenchmarks.com/data/indices/KFRI. Cited via 2026-04-29 search results (illustrative; this is a BTC-perp index, not xStock).
- [`v3-funding-signal-archived`] Soothsayer internal. [`reports/archived/v3_funding_signal.md`](../../../reports/archived/v3_funding_signal.md). The V3 hypothesis-testing report — funding-rate-as-Monday-gap-predictor rejected at 102-row sample.
- [`scryer-kraken-funding-live`] Soothsayer internal. `dataset/kraken/funding/v1/...` (live since the cutover). 10 xStock perps, hourly cadence; SPY/QQQ/GLD from 2025-12-17, others from 2026-02-06.
- [`data-sources-kraken-perp`] Soothsayer internal. [`docs/data-sources.md`](../../data-sources.md) §5 lines 110-132. Kraken xStock Perp catalog; the "8h funding" line at 122 is stale (now 1h).
- [`pyth-regular-companion`] Soothsayer internal. [`docs/sources/oracles/pyth_regular.md`](../oracles/pyth_regular.md). Cross-reference for the publisher-dispersion-vs-coverage-SLA distinction; Kraken's funding-rate cap is structurally analogous to Pyth's `pyth_conf` mechanical widening — both are market-implied / dispersion-implied, not coverage-SLA.
