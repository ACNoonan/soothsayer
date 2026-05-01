# `HTX (Huobi) — Stock Perpetuals (xStock-backed + cash-settled mix)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://www.htx.com/support/900000089963` (HTX *Index Calculation Rules*, cited via 2026-04-29 search; the load-bearing source for the weighted-average index methodology + the 10%-data-threshold weight-zeroing rule), `https://www.huobi.com/support/en-us/detail/900000088923` (HTX *Trading Rules of Perpetual Swaps*, cited via search; mark-price formula), `https://www.huobi.com/support/en-us/detail/84918582771013` (HTX *The Ultimate Guide to Trading on HTX Futures*, cited via search), `https://www.panewslab.com/en/articles/21177b9a-54e0-45a9-a53d-30ad7c20a939` (PANews announcement of TSLAX/USDT perpetual launch on HTX with 20× max leverage; the first xStock-backed perp by HTX), the soothsayer-internal coverage matrix at `~/.claude/projects/.../memory/project_cex_stock_perp_coverage.md` (probed 2026-04-28; HTX has 6 X-suffix + 9 plain stock-perp tickers).
**Version pin:** **HTX (formerly Huobi) Stock Perpetuals (current 2026-04-29)** — **6 X-suffix tickers** (xStock-backed: settles against Backed-issued tokenized stock, e.g., `TSLAX/USDT`) plus **9 plain-suffix tickers** (cash-settled / synthetic). Up to 20× max leverage on the X-suffix tickers per the PANews TSLAX launch announcement. Index-calculation methodology applies the same weighted-average formula across both X and plain tickers, but constituent venues differ (X-suffix necessarily uses xStock-listing venues; plain-suffix uses generic stock-quote sources).
**Role in soothsayer stack:** `comparator (continuous-quoting; xStock-backed + synthetic mix)` — HTX's X-suffix perps share the **exact same Backed-issued underlier** soothsayer prices (zero translation gap, like Kraken Perp + Gate.io xStock perps). The 6 X-suffix coverage is narrower than Gate.io's 12 but wider than BingX's 3 + NCSK and Phemex's 1. **The 10%-data-threshold weight-zeroing rule is HTX's defensive feature**, structurally analogous to Drift's >10% conf rejection (see [`perps/drift_perps.md`](drift_perps.md) §1.3) and Hyperliquid's source-selection logic ([`perps/hyperliquid_perps.md`](hyperliquid_perps.md) §1.3) — useful for Paper 1's "perp-venue oracle hardening" comparator framing.
**Schema in scryer:** **planned, gated on item 45** — same as [`perps/gate_io_stock_perps.md`](gate_io_stock_perps.md). [`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 45 marked Done — phases 55-58 — but `dataset/cex_stock_perp/` is not present at root probe 2026-04-29. **TODO**: confirm tape state.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

**Index price (per HTX *Index Calculation Rules*, cited via 2026-04-29 search):** weighted average across multiple exchanges:

> "The HTX Futures platform performs a weighted average based on the latest transaction prices of multiple exchanges on the market to calculate the index price. The latest price of exchanges is retrieved via API every 1 second."

**Defensive rule against thin-data sources** — distinctive to HTX vs. other CEX stock-perp venues we've surveyed:

> "If the valid data obtained by an exchange from the previous 100 data points (10 min) is less than 10%, it will be considered that this exchange's price lose its guiding significance, and the weight of this exchange will be temporarily adjusted to zero. When the data of this exchange recovered, and there are at least 90 efficient data points out of 100 (90%), then the weight of this exchange will be recovered."

I.e., HTX **dynamically zeros the weight** of any constituent venue that's not actively reporting at least 10% of expected data points over the last 10 minutes. Recovery requires 90% of expected data points back in the same window. **This is the most explicit constituent-data-quality rule among the perp venues we've surveyed** — Pyth's `min_publishers` is conceptually similar but coarser; Hyperliquid's source-selection rules are coarser (whole-asset, not per-venue dynamic).

**Mark price formula (per HTX *Trading Rules of Perpetual Swaps*, cited via search):**

> "Mark Price = Median (Bid and Ask Middle Price Basis Fair Price, Depth Weighted Fair Price, Latest EMA)"

— with the caveat that "Currently, only a few contracts calculate the mark price by using the median, while the others adopt 'Mark Price = Latest EMA' to calculate."

The median-of-three structure applies a defensive trio:
1. **Bid-Ask Mid Basis Fair Price** = Index Price + MA(basis of last 60 bid-ask mids).
2. **Depth-Weighted Fair Price** = a depth-weighted average bid-ask mid.
3. **Latest EMA** = exponentially weighted moving average of recent marks.

For x-suffix stock perps, whether HTX uses the median-of-three or only the EMA fallback is **not surfaced explicitly**, but the docs phrasing ("only a few contracts calculate by median") suggests stock perps may be on the EMA-only path. **§6 open question.**

### 1.2 Cadence / publication schedule

- **Index price:** per-second update (via API polling per docs).
- **Mark price:** continuous, EMA-anchored.
- **Funding rate:** per HTX *Trading Rules of Perpetual Swaps* — typical HTX cadence is 8h, but xStock-specific cadence not pinned in our 2026-04-29 probe. **TODO §6.**
- **Liquidation:** "Partial Liquidation of Futures" page exists but content not surfaced in our probe; HTX has both partial- and full-liquidation paths.

### 1.3 Fallback / degraded behavior

- **Constituent-data-quality weight zeroing** (the 10% / 90% rule above) — explicit defensive mechanism.
- **MA window of 60** for the basis-of-bid-ask-mid component. Smooths short-term basis fluctuations.
- **Median-of-three vs. EMA-only** depending on contract. Which contracts get which path is not enumerated; xStock perps likely get EMA-only.
- **Sampling-window adjustment** is not surfaced in our probe (Gate.io explicitly mentions adjustment; HTX does not).

### 1.4 Schema / wire format

REST/WebSocket API at `api.huobi.pro/swap/...` (HTX retains "huobi" subdomain on some API endpoints). The exact mark-price + index-price + funding response schema is gated on probe; pre-cutover scryer phase 55-58 reportedly schemas this out per `cex_stock_perp_tape.v1`.

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** **claimed live (phase 55-58 per wishlist), but not present at dataset root probe 2026-04-29.** Same as Gate.io; investigate.
- **Indirect via DEX flow:** xStock token spot trades on Solana DEX pools are visible in `dataset/geckoterminal/trades/v1/...`. HTX-specific spot mark / perp mark is gated on item 45 tape.
- **Coverage in current tape:** none from soothsayer side until §6 #1 resolves.
- **HTX X-suffix tickers (6):** per the soothsayer coverage matrix probed 2026-04-28 — TSLAX, NVDAX, MSTRX, AAPLX, COINX, plus one additional (registry list TBD).
- **HTX plain-suffix (9):** synthetic / cash-settled stock perps (e.g., TSLA, NVDA without the X). Different methodology — these reference standard equity-quote sources rather than xStock-token spot.

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| HTX lists 6 X-suffix xStock-backed perps + 9 plain-suffix synthetic perps. | Confirmed via the soothsayer-internal coverage matrix (probed 2026-04-28). | **confirmed** |
| Index price is a weighted average across multiple CEXs, polled per-second. | Confirmed per docs. **Constituent venue list and weights** for xStock-specific perps are not surfaced; the BTC/ETH constituent list (Binance, OKX, Bybit, etc.) does not transfer cleanly because xStocks don't trade on most of those. **§6 open question.** | **partial (mechanism confirmed, xStock-specific opaque)** |
| HTX zeros constituent weight when valid data falls below 10% over last 100 data points (10 min). | Confirmed per docs. **Most explicit constituent-data-quality rule** among the perp venues we've surveyed. The 10% / 90% asymmetry (zero on weak, recover on strong) is structurally robust against single-source flakiness. | **confirmed (by docs)** |
| Mark price = Median(Basis Fair Price, Depth-Weighted Fair Price, Latest EMA). | Confirmed structurally per docs, **with the caveat that "only a few contracts calculate the mark price by using the median, while the others adopt Mark Price = Latest EMA."** Whether xStock perps are in the median or EMA-only group is **TODO**. | **partial** |
| TSLAX/USDT perpetual launched on HTX with 20× max leverage. | Confirmed per the PANews announcement (cited 2026-04-29 search). | **confirmed** |
| Cross-venue dispersion on the same xStock during weekend windows is observable on HTX vs. other xStock-backed perps. | **TODO when scryer item 45 lands.** Same gating as [`perps/gate_io_stock_perps.md`](gate_io_stock_perps.md) §3. | **TODO (Paper 1 §1.1 load-bearing)** |
| Funding rate cadence on HTX xStock perps. | **Unverified** — HTX BTC/ETH default is 8h; xStock-specific cadence not pinned. | **TODO** |
| HTX's constituent venue list for xStock perps necessarily differs from BTC/ETH perps (because xStocks don't trade on Binance/Coinbase/etc.). | **Plausible structurally**, unconfirmed empirically. **§6 open question.** | **plausible, unverified** |
| HTX's 10%/90% data-quality rule is structurally analogous to Drift's >10% conf rejection. | Confirmed structurally — both gate against degraded-input quality, but at different layers (HTX at constituent-source granularity; Drift at oracle-aggregate granularity). The two rules together represent a "thin-source defence at index layer" + "wide-conf defence at oracle-consumption layer." | **confirmed (architectural)** |

---

## 4. Market action / consumer impact

HTX's role mirrors Gate.io's structurally: a CEX continuous-quoting venue with X-suffix perps on the same Backed-issued underliers soothsayer prices.

- **Soothsayer (xStock weekend bands)** — HTX TSLAX/USDT mark vs. soothsayer's served TSLAx band is direct comparator. Combined with Gate.io NVDAX_USDT, Kraken Perp NVDAx, BingX NVDAX, Phemex NVDAX — the 5-venue cross-CEX dispersion at Friday close is the **load-bearing §1.1 incumbent-benchmark figure** for Paper 1.
- **Backed Finance** — HTX is one of 5 CEX clearinghouses providing a position-margining mark on Backed-issued tokens. The trust-gap framing applies symmetrically.
- **Kamino klend / MarginFi / Drift / Save / Loopscale / Jupiter Lend** — none consume HTX perp marks directly. HTX is signal, not oracle source.
- **Paper 1 §1.1 / §1.2** — same role as Gate.io. The HTX-specific differentiator is the 10%/90% data-quality rule, which is the cleanest single example among CEX stock-perp venues of "production-grade defensive logic against degraded-source dispersion." Cite explicitly in §1's framing as "production CEX oracles already implement defensive degradation logic — but at the source-input layer, not at the calibration-output layer; soothsayer's served band moves the defensive logic to the latter."
- **Paper 3 §6 / §7** — not a Paper-3-load-bearing site (no liquidation events Paper 3 needs to count); rhetorically useful as a "perp-venue oracle hardening" cross-reference.
- **Public dashboard (Phase 2)** — five-venue dispersion plot row: Kraken Perp + Gate.io + HTX + BingX + Phemex marks at Friday close, soothsayer's band overlaid, Monday open as ground truth.

---

## 5. Known confusions / version pitfalls

- **HTX is the post-2023 rebrand of Huobi.** Documentation URLs alternate between `htx.com` and `huobi.com`; both are the same exchange. Cross-referencing pre-2023 docs as "HTX" is risk-prone.
- **X-suffix vs plain-suffix.** Same gotcha as Gate.io: X-suffix references Backed-issued tokens, plain-suffix is synthetic / cash-settled USDT against equity-quote sources. Different mark methodology applies despite similar tickers.
- **Mark price formula is contract-specific.** Some contracts use the median-of-three; others use EMA-only. Don't assume one applies to the xStock-class perps without confirmation.
- **The 10%/90% data-quality rule is at constituent-venue granularity, not at per-tick granularity.** A constituent with sporadic-but-valid data avoids weight zeroing if it stays >10%; a constituent that goes silent for 10 min gets zeroed.
- **Index-price polling cadence is 1 second.** Per-second cadence is finer than soothsayer's typical analysis granularity; production-grade for liquidation reasoning.
- **Constituent venue list for xStock perps is not surfaced.** Don't assume parity with BTC/ETH constituent lists.
- **Funding cadence not pinned.** Probably 8h (HTX default) but xStock-specific not confirmed.
- **Item 45 tape claim vs visible disk state.** Same Pattern-1 caveat as Gate.io.
- **HTX has historically had operational reliability concerns** at the broader exchange level (custodian / regulatory). Paper 1's framing should distinguish "reputable-CEX trust gap" from "less-reputable-CEX trust gap" if the per-venue cut shows asymmetric volume decay (per the coverage memo's stratification).

---

## 6. Open questions

1. **Verify scryer phases 55-58 (item 45) actually shipped end-to-end and the cex_stock_perp tape is live.** Same as Gate.io §6 #1. Pattern 1 from the final report.
2. **Pin the xStock-specific constituent venue list for HTX X-suffix perps.** **Why it matters:** the index methodology depends on which spot venues feed the xStock-specific weighting. **Gating:** HTX support outreach or finer docs probe.
3. **Confirm whether HTX xStock perps use median-of-three or EMA-only mark formula.** **Why it matters:** the median-of-three is more defensive against book/EMA divergence; EMA-only is sensitive to recent print noise. **Gating:** docs deeper read or per-contract spec lookup.
4. **Confirm funding-rate cadence on HTX xStock perps.** **Why it matters:** cross-venue funding-signal comparison. **Gating:** docs probe.
5. **Confirm HTX funding-rate cap on xStock perps.** **Why it matters:** Kraken's ±0.25%/h cap is binding empirically; HTX's cap unknown. **Gating:** docs probe.
6. **Cross-venue Friday-close mark dispersion on the same xStock.** Load-bearing §1.1 figure. Gating: scryer item 45 + analysis.
7. **Per-venue volume decay shape at Friday 16:00 ET.** Gating: scryer item 45 OHLCV tape + DiD per the coverage memo.
8. **Whether HTX's 10%/90% rule has empirically zeroed any xStock-feeding source.** **Why it matters:** if yes, that's a real-world example of production-grade defensive degradation in action — useful for Paper 1's framing. **Gating:** scryer tape + analysis script (when item 45 lands).

---

## 7. Citations

- [`htx-index-rules`] HTX. *Index Calculation Rules*. https://www.htx.com/support/900000089963. Cited via 2026-04-29 search results. The load-bearing source for the weighted-average index methodology and the 10%/90% data-quality rule.
- [`htx-perp-rules`] HTX. *Trading Rules of Perpetual Swaps*. https://www.huobi.com/support/en-us/detail/900000088923. Cited via 2026-04-29 search results. The mark-price formula source.
- [`htx-futures-guide`] HTX. *The Ultimate Guide to Trading on HTX Futures*. https://www.huobi.com/support/en-us/detail/84918582771013. Cited via 2026-04-29 search results.
- [`htx-tslax-launch`] PANews. *Huobi HTX launches its first cryptocurrency-equity contract: Tesla stock token TSLAX perpetual contract*. https://www.panewslab.com/en/articles/21177b9a-54e0-45a9-a53d-30ad7c20a939. Cited via 2026-04-29 search results.
- [`coverage-matrix-memory`] Soothsayer agent memory. *CEX stock-perp coverage map (paper 1 incumbent benchmark)*. (Internal-memory note, probed 2026-04-28; HTX 6 X-suffix + 9 plain.)
- [`scryer-wishlist-item-45`] Scryer internal. [`scryer/wishlist.md`](../../../../scryer/wishlist.md) item 45.
- [`gate-companion`] Soothsayer internal. [`docs/sources/perps/gate_io_stock_perps.md`](gate_io_stock_perps.md). Sister venue in the xStock-backed CEX panel.
- [`drift-perps-companion`] Soothsayer internal. [`docs/sources/perps/drift_perps.md`](drift_perps.md). Comparator: Drift's >10% conf rejection vs. HTX's 10%/90% data-quality rule.
- [`hyperliquid-perps-companion`] Soothsayer internal. [`docs/sources/perps/hyperliquid_perps.md`](hyperliquid_perps.md). Comparator: Hyperliquid's source-selection rules vs. HTX's per-venue weight zeroing.
