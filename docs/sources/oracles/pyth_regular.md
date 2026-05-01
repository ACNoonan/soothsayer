# `Pyth Network — Regular feed (publisher-vote aggregation)` — Methodology vs. Observed

---

**Last verified:** `2026-04-29`
**Verified by:** `https://docs.pyth.network/price-feeds/how-pyth-works/price-aggregation` (accessed 2026-04-29; complete on the 3N median rule and Q25/Q75 confidence formula, partial on EMA half-life and on-chain `PriceAccount` field set), `https://pythnetwork.medium.com/pyth-price-aggregation-proposal-770bfb686641` (referenced for EMA detail), the loader at `src/soothsayer/sources/scryer.py:179`, the comparator script `scripts/pyth_benchmark_comparison.py`, the empirical surface in [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md) §2.
**Version pin:** Aggregation v2 (the 3N publisher-vote rule is the current production aggregation; the EMA twin is the slot-weighted, inverse-confidence-weighted complement). This file describes the **regular** Pyth feed surface — the on-chain Solana `PriceAccount` reads — not Pyth Pull / Lazer / Express Relay (those have separate files in this directory).
**Role in soothsayer stack:** `comparator` (first-class, free, most rigorous published incumbent). We do **not** consume Pyth as a soothsayer fair-value input — Pyth's confidence interval is the closest published "band" in the existing Solana oracle stack and is precisely what soothsayer's served band is meant to be measured against.
**Schema in scryer:** `dataset/pyth/oracle_tape/v1/year=YYYY/month=MM/day=DD.parquet` (schema `pyth.v1`). Loader: `src/soothsayer/sources/scryer.py:179` `load_pyth_window`.

---

## 1. Stated methodology

### 1.1 Aggregation / pricing rule

From the Pyth aggregation docs (accessed 2026-04-29):

> "The first step computes the aggregate price by giving each publisher three votes — one vote at their price and one vote at each of their price +/- their confidence interval — then taking the median of all the votes."

Formally, with `N` publishers each submitting `(p_i, c_i)`:

- Each publisher contributes 3 votes: `{p_i - c_i, p_i, p_i + c_i}`.
- Aggregate price `R` = median of the 3N votes.
- Aggregate confidence `C = max(|R - Q_25|, |R - Q_75|)` — the larger of the two distances from the median to the 25th and 75th percentiles of the votes.

Design properties Pyth claims:
- robustness to outlier manipulation,
- weighted influence based on publisher confidence accuracy (high-confidence publishers cluster their 3 votes; low-confidence publishers spread them), and
- aggregate confidence reflects price variation between sources.

The on-chain `PriceAccount` additionally maintains an EMA price and EMA confidence as a slot-weighted, inverse-confidence-weighted complement to the aggregate. Per soothsayer's prior summary in [`docs/data-sources.md`](../../data-sources.md#pyth-network) the EMA half-life is ~1 hour. The Pyth aggregation page (accessed 2026-04-29) does **not** restate the EMA formula in detail — the medium-post reference is the deeper surface and is queued for the §6 outreach list.

### 1.2 Cadence / publication schedule

Pyth publishers update on Solana slot cadence (~400ms) when active. The `PriceAccount.status` enum captures the venue's session state per Pyth's understanding:

- `Trading` — feed is live, aggregate is current.
- `Halted` — feed is administratively halted (per-feed; matches venue halts for some feeds).
- `Auction` — feed is in opening/closing auction (some equity feeds).
- `Unknown` — no usable status signal.

A **minimum publisher count** governs whether the aggregate is computed; below that count the aggregate is suppressed. The aggregation-page excerpt accessed 2026-04-29 does not state the minimum value, only that it exists. (TODO: cite the medium post or governance config for the exact threshold.)

When the underlying venue closes (US equities outside regular session), publishers thin out, the 3N vote pool shrinks, and the aggregate confidence widens — Pyth's confidence interval mechanically wraps the publisher-dispersion contraction/expansion. **This is the structural reason Pyth's regular feed produces a near-zero half-width during closed-market windows: at the Friday-close moment the publishers are still in lockstep, their `c_i` values are tight, and the 3N median collapses to a tight interval.** The Pyth confidence band is *publisher-dispersion-implied*, not a coverage SLA.

### 1.3 Fallback / degraded behavior

- Below `min_publishers` → aggregate suppressed; the on-chain `PriceAccount.status` reflects this and consumers must check status before reading.
- EMA price and EMA conf continue to update slot-weighted as new aggregates land, with downweighting on staleness — the EMA is the soft fallback when the snap aggregate goes degraded.
- Per-publisher staleness handling: publishers whose last update is too old are dropped from the 3N pool. The exact age threshold is not surfaced in the public aggregation page (TODO §6).

### 1.4 Schema / wire format

On-chain `PriceAccount` (Solana) is the source of truth for the wire format. The fields we read in our tape per the loader at `src/soothsayer/sources/scryer.py:179-201` are:

```
poll_ts, poll_unix, symbol, session,
pyth_feed_id, pyth_price, pyth_conf, pyth_expo, pyth_publish_time,
pyth_age_s, pyth_half_width_bps,
pyth_ema_price, pyth_ema_conf, pyth_ema_publish_time,
pyth_ema_half_width_bps, slot, pyth_err
```

`pyth_expo` is the price exponent (negative integer; `actual_price = pyth_price * 10**pyth_expo`). `pyth_half_width_bps` is the soothsayer-side derived field `pyth_conf / pyth_price * 10000`. Per-publisher prices are not exposed in `pyth.v1` — the on-chain `PriceAccount` carries `[PriceComponent; 32]` per-publisher entries but those are not currently captured in the tape (a separate `pyth_components.v1` stream is queued in `scryer/wishlist.md`).

---

## 2. Observable signals (where this lives in our data)

- **Scryer parquet:** `dataset/pyth/oracle_tape/v1/year=YYYY/month=MM/day=DD.parquet`. Continuous capture (✅ live per [`docs/data-sources.md`](../../data-sources.md) Engineering inventory). The symbol convention is the **underlier** ticker (`SPY`), not the xStock (`SPYx`); map xStock → underlier before filtering (loader docstring `src/soothsayer/sources/scryer.py:188`).
- **Comparator script:** `scripts/pyth_benchmark_comparison.py:1-69` — compares Pyth's CI-as-band realization at multiples of `k·conf` to soothsayer's served band on a matched panel (10 equities, 172 OOS weekends). This is the canonical artefact for Pyth-vs-soothsayer coverage comparison and feeds Paper 1 §6.
- **Empirical surface (per-weekend):** [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md) §2 — for each weekend, Pyth's `pyth_regular cov / hw / excess` is reported alongside soothsayer's bands and a simple heuristic.
- **On-chain reads (live):** the `PriceAccount` per `pyth_feed_id` — readable via `getAccountInfo` against Pyth's program. We do not maintain a live decoder in soothsayer; reads happen scryer-side.
- **Per-publisher data:** **not in our tape today.** `pyth_components.v1` (per-publisher `PriceComponent` decode) is queued; the file's §3 reconciliation cannot currently disaggregate "the aggregate confidence widened because publishers thinned" vs. "publishers stayed but disagreed" — that's a §6 open question.

---

## 3. Reconciliation: stated vs. observed

| Stated claim | Observation | Verdict |
|---|---|---|
| Pyth aggregate widens during closed-market windows because publishers thin out. | **Contradicted at the closing snap.** [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md) §2: at Friday close (the read used to score the weekend), all 8 xStock-underlier Pyth feeds report `cov/hw/excess` of `✗ out / 0.0 / -<realized_bps>` — the half-width is effectively zero at the Friday close, so the band misses **every** subsequent Monday open. The widening, if it happens, occurs after Friday close as publishers drop off — not at the close itself, which is the moment the consumer reads. | **contradicted (mechanism widens, but consumer-relevant read happens before widening)** |
| The 3N publisher-vote median is robust to outlier manipulation. | **Unmeasurable from our tape.** Without `pyth_components.v1` we cannot observe per-publisher behaviour; we only see the aggregate. The claim is plausible from first principles but cannot be empirically confirmed against soothsayer data today. | **unmeasurable** |
| `Confidence = max(|R - Q_25|, |R - Q_75|)`. | Confirmed structurally — the `pyth_conf` field in our tape is the on-chain published confidence; we have not independently re-derived the formula from per-publisher data (gated on `pyth_components.v1`). | **confirmed (by reading the published value, not by independent reconstruction)** |
| `min_publishers` threshold suppresses the aggregate when too few publishers are active. | Plausible from `pyth_err` non-empty rows in our tape (publish failures or status ≠ Trading). Specific threshold unknown; not reconstructed. | **partial (mechanism observed, threshold unknown)** |
| EMA half-life is ~1 hour. | **Unmeasurable from our weekend panel** — weekend windows are 60+ hours, so the EMA is fully decayed by Monday open. The half-life claim is consistent with this but underdetermined. Validating it requires intraday EMA-vs-snap decay measurement, which is a §6 task. | **unmeasurable on weekend cadence** |
| Pyth confidence is a *publisher-dispersion* signal, not a coverage SLA. | **Confirmed empirically.** The matched-window panel in `pyth_benchmark_comparison.py` shows Pyth `k·conf` band realised coverage at typical `k` values does **not** track Pyth's implicit coverage promise — the band is mechanically tied to publisher dispersion rather than to a Kupiec-calibrated coverage target. This is the central reconciliation Paper 1 §1 / §2 turns on. | **confirmed** |
| Symbol convention is the underlier ticker, not the tokenised xStock. | Confirmed via the loader docstring `src/soothsayer/sources/scryer.py:188`. Pyth does **not** publish a feed on the SPL token `SPYx` itself; the comparison feed is `SPY` (the US-listed underlier). | **confirmed** |

---

## 4. Market action / consumer impact

Pyth feeds are consumed across the Solana ecosystem more broadly than any other oracle, which makes the publisher-dispersion-vs-coverage-SLA distinction load-bearing for every downstream protocol that treats `pyth_conf` as a risk band:

- **Drift Protocol (perps + spot)** — Drift reads Pyth `PriceAccount` directly for many markets. Mark-vs-oracle deviation logic uses the aggregate; whether they consume the conf interval as a validity gate or only the price is a §6 question. **TODO when scryer adds drift-oracle wiring snapshot.**
- **MarginFi** — public docs do not surface oracle-source granularity at the bank/reserve level. Pyth is plausibly a primary oracle for many marginfi banks (it's the default Solana oracle for non-stablecoin assets). **TODO when MarginFi reserve-config snapshot lands** — see [`docs/sources/lending/marginfi.md`](../lending/marginfi.md) §6.
- **Jupiter Lend / Fluid Vaults** — Pyth is plausibly the primary oracle here too (TODO confirm; queued in `scryer/wishlist.md` under Priority 1 #3).
- **Save (Solend) / Loopscale** — same pattern; both are Solana lending protocols and Pyth is the default oracle layer.
- **Kamino klend (xStocks reserves only)** — does **not** use Pyth on xStocks; uses Scope (which sources Chainlink v10 and other inputs). The §3 finding does not directly flip a Kamino price-validity check on xStocks. For non-xStock Kamino reserves, Pyth is the dominant primary oracle.
- **Paper 1 §2 framing** — the publisher-dispersion-vs-coverage-SLA finding is the cleanest single-sentence frame for "no incumbent publishes a verifiable calibration claim." The Pyth confidence interval is the most-published incumbent "band"; soothsayer's served band is what an incumbent calibration SLA would look like.
- **Public dashboard (Phase 2)** — Pyth `pyth_regular` is the natural row to put next to soothsayer's served band: same window, same underlier, same realised Monday open, different coverage outcome.

---

## 5. Known confusions / version pitfalls

- **Pyth regular vs Pull vs Lazer vs Pro X vs Express Relay.** This file documents the **regular** on-Solana `PriceAccount` read. Pull (Wormhole-bridged `PriceUpdate` to non-Solana chains), Lazer (Pyth's low-latency push), Pro X (the 24/5 Blue Ocean ATS path documented as launched March 2026), and Express Relay (the OEV auction) all have separate files in this directory. Cross-referencing "Pyth confidence" without checking which surface is the source of confusion.
- **`pyth_price * 10**pyth_expo` is the actual price.** The raw `pyth_price` is an integer with the exponent stored separately. Code that reads `pyth_price` directly without applying `pyth_expo` will be off by orders of magnitude.
- **Underlier ≠ tokenized.** Pyth's `SPY` feed is for the SPY ETF underlier; soothsayer's calibration concerns the SPYx token. The two diverge on weekends (xStocks trade continuously; SPY does not). Code that filters Pyth on `symbol == "SPYx"` will return empty.
- **Confidence at Friday close ≠ confidence at Monday open.** `pyth_conf` evaluated at Friday close is the publisher-dispersion among regular-session publishers; the band that wraps the weekend is the *Friday close* confidence, not a forward-looking estimate. Treat Pyth's weekend "coverage" as "did the band published Friday cover the Monday open" — that's the correct framing and it's the one [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md) §2 implements.
- **EMA price ≠ aggregate price.** The EMA is the slot-weighted complement; downstream code that toggles between `pyth_price` and `pyth_ema_price` based on staleness must be intentional about the half-life difference. The two columns exist for a reason; using whichever is non-null is a recipe for invisible regime-switches.
- **`pyth_age_s` is age relative to `poll_ts`, not relative to read time.** When joining Pyth tape against another tape (e.g., v5_tape) the age semantics depend on the join key.

---

## 6. Open questions

1. **EMA half-life — exact value and whether it's per-feed or global.** Cited as ~1h in soothsayer's prior summary; not surfaced in the aggregation page. Resolving this matters for any soothsayer baseline that uses `pyth_ema_*` as a stale-hold proxy. **Gating:** medium-post review or Pyth Discord outreach.
2. **`min_publishers` threshold — exact value and how `pyth_err` correlates with it.** **Gating:** governance config audit + cross-reference against `pyth_err` non-empty rows in our tape.
3. **Per-publisher data (`pyth_components.v1`).** Without this stream, §3 cannot disaggregate "publishers thinned" vs. "publishers disagreed" as the cause of conf-interval changes. **Gating:** scryer wishlist item — currently planned per `docs/data-sources.md` §7 "On-chain `PriceAccount` decode (planned tape, see §8)". Add to scryer wishlist explicitly if not already there.
4. **`status = Auction` semantics on Pyth equity feeds.** Whether Pyth-equity feeds emit `Auction` during US equity opening/closing auctions, and if so whether `pyth_price` is meaningful during that window. **Gating:** intraday Pyth tape audit (existing parquet has `pyth_publish_time`; cross-reference against US equity auction times).
5. **Pyth Pro X (24/5 Blue Ocean ATS path).** Whether Pyth's publicly-marketed 24/5 equity feed actually flows through the regular `PriceAccount` surface or through a separate `PriceUpdate`-style endpoint. Documented in [`oracles/pyth_lazer.md`](pyth_lazer.md) (📋 planned in INDEX); resolution there will tighten this file's §1.2 cadence claim.
6. **Whether MarginFi / Drift consume `pyth_conf` as a validity gate or only `pyth_price`.** This determines whether the publisher-dispersion-vs-coverage-SLA finding has live downstream consequence. **Gating:** consumer reserve-config decode for each protocol.

---

## 7. Citations

- [`pyth-aggregation`] Pyth Network. *Price Aggregation*. https://docs.pyth.network/price-feeds/how-pyth-works/price-aggregation. Accessed: 2026-04-29.
- [`pyth-aggregation-medium`] Pyth Network. *Pyth Price Aggregation Proposal*. https://pythnetwork.medium.com/pyth-price-aggregation-proposal-770bfb686641. Referenced by the docs page for EMA detail; not yet directly accessed by soothsayer; queued for §6 resolution.
- [`pyth-benchmark-comparison`] Soothsayer internal. [`scripts/pyth_benchmark_comparison.py`](../../../scripts/pyth_benchmark_comparison.py). Pyth-vs-soothsayer matched-window coverage comparison (10 equities, 172 OOS weekends).
- [`scryer-pyth-loader`] Soothsayer internal. [`src/soothsayer/sources/scryer.py`](../../../src/soothsayer/sources/scryer.py) `load_pyth_window` at line 179. Reader for `dataset/pyth/oracle_tape/v1/...`.
- [`kamino-weekend-comparator`] Soothsayer internal. [`reports/kamino_xstocks_weekend_20260424.md`](../../../reports/kamino_xstocks_weekend_20260424.md) §2. Per-weekend Pyth-vs-soothsayer coverage table at the kamino reserve granularity.
