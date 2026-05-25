# Scope — overnight (close→next-open) panel build

**Status:** scoping doc, not started. **Date:** 2026-05-25.
**Question it answers:** what would it take to extend the deployed weekend-gap
calibration to *overnight* (single weeknight close→open) gaps, and is the
methodology general enough to carry over?

**Prior art:** `scripts/regime_decomposition_probe.py` (2026-05-01) established
that off-hours is *not* one regime — fully-closed weekend, weeknight overnight
(US closed, Asia/Europe live), and extended/after-hours are structurally
distinct (e.g. Chainlink tokenized per-update vol ≈ 3.8 bp weekend vs ≈ 18.2 bp
overnight). That probe characterised *incumbent* oracles; it did **not** build a
soothsayer overnight model. This scope is that follow-on.

---

## 1. Why build it

1. **Paper 1 external validity.** The coverage-inversion result is currently a
   *weekend* claim (panel = 5,996 rows, 100% Fri→Mon). If the same
   calibration-transparency story holds on overnight gaps, the contribution
   generalises from "weekends" to "off-hours" — a materially stronger claim. If
   it *doesn't* transfer cleanly (earnings nights are the prime suspect), that
   is itself a publishable scope boundary.
2. **Paper 4 (oracle-conditioned AMM) substrate.** A 24/7 AMM is exposed to a
   closed underlier *every night*, not just weekends. Overnight is the
   high-frequency version of the exact LVR exposure Paper 4 is about — ~5× more
   events per year, and the natural data substrate for that work.
3. **Honest caveat on the lending angle.** The 2026-05-25 Kamino check (101/102
   xStock liquidations market-hours, 0 weekend) already weakened the
   weekend-lending wedge. An overnight panel does *not* automatically rescue it
   — but overnight gaps adjacent to the 9:30 auction are the plausible *seed* of
   a market-hours cascade, which is a sharper lending question than "weekend
   gap" was. Build it for (1)+(2); treat any lending payoff as a bonus to verify,
   not a premise.

---

## 2. What ports for free

The deployed pipeline is gap-length-agnostic almost everywhere:

- **Panel assembly** (`src/soothsayer/backtest/panel.py`): the *only*
  weekend-specific line is the gap selector in `_weekend_pairs_with_vol`
  (`gap < spec.min_gap_days` → skip). Selecting `gap == 1` (consecutive trading
  days) instead yields overnight pairs. `_join_exog` already joins
  `close→next-open` of each futures factor — identical mechanics for a 1-day gap
  (today's ES close → tomorrow's ES open). The `fri_ts/mon_ts` column names
  become cosmetically wrong but functionally fine; rename to `t0_ts/t1_ts` for a
  clean artefact.
- **Factor switchboard, vol-index selection, σ̂ EWMA, conformal lookup,
  Mondrian/LWC serving, the entire calibration battery** (Kupiec, Christoffersen,
  Berkowitz, per-symbol, LOSO, sub-period, c(τ) bump fit, CUSUM): all consume
  the panel by column, not by gap semantics. They re-run unchanged on the new
  panel.
- **Base data is already in scryer.** `yahoo/equities_daily/v1` carries `open`
  and `close` for every trading day → every consecutive (close, next-open) pair
  is an overnight gap with **no new ingest**. Futures (`cme/intraday_1m` +
  yahoo legacy), vol indices (CBOE), all already loaded by the panel builder.

**Implication:** the panel itself is a ~1-day fork, not a rebuild.

---

## 3. What genuinely changes

### 3.1 Earnings timing — the one real upstream dependency (load-bearing)
Overnight's dominant fat tail is the **earnings-night gap** (routine 5–10%
single-name moves). The current `earnings_next_week` flag is coarse ("any
earnings in the upcoming Mon–Fri week") — useless overnight, where we need "is
there an earnings release *between this close and the next open*."

That requires **session timing (BMO / AMC)** which `yahoo/earnings/v1` does
**not** carry (schema: `symbol, earnings_date` only). Without it there is a ±1
night ambiguity on which gap inherits the jump — fatal for an earnings-night
regime. Good news: the data already shows a `finnhub:earnings:runner` source,
and Finnhub's earnings calendar exposes an `hour` field (`bmo`/`amc`/`dmh`). So
the fix is a **scryer-side enhancement**, not a new fetcher: extend the
`yahoo/earnings` (or a `finnhub/earnings`) schema with a session/timing column.
Per CLAUDE.md rule 2 this lands in scryer first. Estimate: small scryer task.

### 3.2 Regime taxonomy
Re-derive buckets for overnight using the probe's window primitive:
- **drop** `long_weekend` (no analog; mid-week holidays give occasional 2-day
  gaps — handle as a minor `holiday_bridge` bucket or fold into `gap_days`);
- **keep** `high_vol` (VIX-percentile based, ports directly);
- **add** `earnings_night` (the headline new bucket; gated on 3.1);
- **consider** a `macro_event` bucket for scheduled pre-open releases
  (FOMC/CPI mornings) — defer unless the residual demands it.

### 3.3 σ̂ recalibration + earnings contamination
σ̂ EWMA must be refit on the overnight return series (different scale: ~17 h vs
~65 h, so smaller typical moves). Critical subtlety: a plain EWMA will be
**polluted by earnings jumps** — a 8% earnings gap inflates σ̂ for the next ~8
nights, over-widening quiet nights. Likely need to either exclude earnings
nights from the σ̂ update or carry a separate earnings-night scale. This is the
main *methodological* (not engineering) risk.

### 3.4 Ex-dividend mornings
Overnight samples ex-div opens far more often than the weekend panel does (every
ex-div date is an overnight gap). The panel uses raw `close`/`open`, so ex-div
mornings show as systematic small down-gaps that will bias the lower band.
Either switch to dividend-adjusted prices or add an ex-div flag/correction
(scryer has `yahoo/corp_actions` + `backed/corp_actions`). Cheap but must not be
skipped.

### 3.5 Overlap / autocorrelation
Weekend gaps are ~weekly and near-independent. Overnight gaps are consecutive,
and the conditioning state (vol index, realized vol) is highly day-to-day
autocorrelated → Christoffersen independence and the iid-ish framing are more
strained. Mitigation already in-repo: block bootstrap
(`scripts/run_paper1_b5_kw_block_bootstrap.py`) for CIs; report
Christoffersen with that caveat.

---

## 4. Sample size
12 yr × ~250 trading days × 10 symbols ≈ **~30k overnight rows** (vs 6k weekend).
Earnings-night cell ≈ 4 releases/yr × 12 yr × 10 ≈ ~480 rows — enough to
calibrate a regime. Calibration *power* is not the constraint; data *structure*
(3.3–3.5) is.

---

## 5. Phased plan

| Phase | Work | Depends on | Est. |
|---|---|---|---|
| **0** | Scryer: add earnings session timing (BMO/AMC) to earnings schema | — | scryer-side, small |
| **1** | Fork panel build: parameterise gap selector (`gap==1` + holiday bridge), rename `t0/t1`, ex-div flag (3.4) | — (can start now; earnings flag stubbed) | ~1 day |
| **2** | Regime re-derivation (3.2) + σ̂ recalibration with earnings handling (3.3) | Phase 0 (for earnings_night) | ~2–3 days |
| **3** | Run full calibration battery on overnight panel; produce coverage-inversion tables; block-bootstrap CIs | Phase 2 | ~1–2 days |
| **4** | Verdict report: does the inversion generalise? earnings-night boundary? per-class (equity vs GLD/TLT) | Phase 3 | ~1 day |

**Critical path:** Phase 0 (scryer earnings timing) gates the earnings-night
regime, which is the load-bearing piece. Phases 1 + a *non-earnings-conditioned*
version of 2–3 can run in parallel to get a first read while Phase 0 lands.

**Naming/versioning** (CLAUDE.md rule 5): new internal artefact
`data/processed/overnight_panel.parquet`; if/when a band is served, a new
experiment venue (`soothsayer_v{N}/tape` for the overnight cadence). Weekend
artefacts stay untouched at their current paths.

---

## 6. Recommendation
Total ≈ **1–1.5 weeks** of soothsayer work + one small scryer task — *not* a new
model, a retrain-and-revalidate on a forked panel. The engine ports; the
calibration does not transfer and must be re-earned, with earnings-night the
node most likely to break (and most interesting if it does).

Sequencing: this is **Paper 4 infrastructure first, Paper 1 generality second**.
Don't gate the reviewer reply or the Paper 1 §6.5 reframe on it. Right trigger to
start is when Paper 4 work begins needing a per-night exposure substrate, or if
a reviewer explicitly challenges the "weekends only" external validity.

## Reproduction (Phase 1 first read, once forked)
```
# after parameterising PanelSpec.min_gap_days / gap selector:
uv run python scripts/build_overnight_panel.py   # to be written (fork of panel build)
```
