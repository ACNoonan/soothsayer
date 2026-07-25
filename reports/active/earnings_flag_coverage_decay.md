# earnings_night flag coverage — live defect

**Found 2026-07-25** while verifying the adaptive band-archive emitter. **Rewritten 2026-07-25 after an operator run falsified the first diagnosis.** The superseded version prescribed a repair that cannot work; §"What the first version got wrong" records it, because a wrong runbook entry is worse than no entry.

## Symptom

The overnight panel carries **zero** `earnings_night` rows after 2025-05-28, despite running to 2026-04-23. Six earnings-reporting symbols (SPY/QQQ/GLD/TLT are ETFs) should produce ~24 flagged nights a year. Observed: 2023 → 24, 2024 → 24, **2025 → 12, 2026 → 0**.

## What the first version got wrong

**1. The prescribed fix is a no-op.** `scry equities earnings-backfill` returns `rows_added=0 rows_deduped=461 symbols_failed=0` and exits 0. Against a clean dataset root it fetches 461 rows, and Yahoo's earnings history **terminates Apr–Jun 2025** for all six symbols (AAPL 2025-05-01, MSTR 05-22, TSLA 04-22, GOOGL 06-06, HOOD 06-26, NVDA 06-26). Not a `--size` truncation: GOOGL/HOOD/TSLA return 84/18/59 rows against a cap of 100 and still stop there. **The upstream is dead, not stale** — and has been for ~14 months.

That is the part worth dwelling on. The prescribed repair reports success forever, so it fails silently in the *same conservative-looking direction* as the defect it was meant to fix. Filing it made the situation worse than filing nothing.

**2. "2025-05-28" is not a panel-side boundary.** It is NVDA's last Yahoo-confirmed date. The panel logic never had a cutoff; the source ran out.

## Actual root cause — three independent latches

**(a) Dead upstream.** Yahoo earnings history ends Apr–Jun 2025. The Finnhub forward runner keeps *dates* current; only the Yahoo backfill ever produced confirmed sessions. Confirmation decays while dates look healthy — which is exactly why any dates-based health check is blind to it.

**(b) First-writer-wins shadowing.** `merge_dedup` (`crates/scryer-store/src/lib.rs:397`) keeps the first row on a `(symbol, earnings_date)` collision. `earnings-migrate` ran 2026-04-27 and the backfill 2026-05-25 — **inverting the ordering `equities_cmd.rs:226` documents as mandatory**. Twenty legacy `session=unknown, session_confirmed=NULL` rows now permanently shadow the 2025-07 → 2026-04 quarters. Even a live Yahoo would return `rows_added=0`.

**(c) Date-revision duplicates — a separate, previously unfiled defect.** Because dedup is keyed on `(symbol, earnings_date)`, a Finnhub date revision writes a *second* row rather than updating the first: AAPL 07-29/07-30, GOOGL 07-21/07-22/07-28, MSTR 07-29/07-30/08-04, NVDA 08-25/08-26, and similarly HOOD/TSLA. That is why counts run 5–6/yr against a true 4. Downstream this manufactures **phantom** earnings nights — the opposite error to (a), perturbing the same count.

## Why it matters

An earnings night served today is classified `normal` and receives a ≈3% band where the calibrated earnings band is ≈25%. That is precisely the failure W12 measured: without the partition, `earnings_night` coverage is **0.333 against a claimed 0.95**. The cell exists to prevent this and is not firing.

Secondarily, the paper's `earnings_night` OOS n = 60 is smaller than it should be — and that n is what every power caveat in W14/W16/W17 is written around.

Third silent failure in the conservative-looking direction in this programme, after the σ̂ contamination and the triple-witching hole. The first-version fix would have been the fourth.

## The fix — EDGAR as a timing oracle

`edgar_8k.v1` is already shipped in scryer (Phase 51) with `filing_ts` acceptance timestamps, `items`, and `accession_number` (604 filings). Item-2.02 acceptance times in ET **close 19 of the 22 dark rows in the panel window, exactly and authoritatively** — AAPL/GOOGL/NVDA all `amc` 16:01–16:31, TSLA 2026-04-22 `amc` 16:10, MSTR/HOOD likewise.

**The trap, which must be encoded rather than remembered:** join on *known earnings dates only*. A naive "item 2.02 ⇒ earnings" rule adds **8 phantoms**, because TSLA's quarterly delivery 8-Ks file at ~09:05 ET and are also item 2.02. EDGAR is a **timing oracle for dates already held**, never a date-discovery source.

The 3 residual dark rows (GOOGL 2025-06-06, HOOD/NVDA 2025-06-26) have no 2.02 placeholder and remain correctly excluded today.

## Sequencing — repair, rebuild, regenerate once

Do **not** regenerate the paper numbers yet. The panel rebuild is *blocked*, not queued: inside the panel window there are currently zero usable rows (22 dark, 19 recoverable only via EDGAR). Regenerating now burns a full re-run of the overnight arms of W12/W15/W16/W17 and then needs a second once the 19 nights land — and the `earnings_night` arm moves materially when they do, since 19 against n = 60 is a ~32% change to the thinnest, most-cited cell in the evidence pack.

Repair → rebuild → regenerate **once**.

## Durable fix on the soothsayer side

A build-time assertion, with the predicate tightened from the first version. "Latest `earnings_night` within a quarter of panel end" **would not have caught this**, because dates stayed current the whole time and only confirmation decayed. The check asserts on **confirmed-session recency and confirmed fraction inside the panel window**.

Implemented as `soothsayer.backtest.panel.check_earnings_confirmation_health()`.
