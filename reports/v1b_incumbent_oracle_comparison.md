# V1b — Incumbent oracle unified comparison

**Question.** Across the four incumbent oracles serving xStock-relevant symbols on Solana (Pyth, Chainlink Data Streams, RedStone, Kamino Scope), what published-band half-width (in bps of price) does each require to deliver τ-coverage of the realised Friday-close → Monday-open weekend gap? How does that compare to Soothsayer's deployed v1 served band?

**Construction.** This table is *not* a single-panel head-to-head — incumbent tape recency varies (Pyth 2024+, Chainlink frozen 2026-02→04 panel, RedStone + Scope forward-tape 2026-04→ ongoing) and the symbol coverage differs (Pyth covers 8 underliers; RedStone covers SPY/QQQ/MSTR only; Scope covers 8 xStocks). Per-row n is the available-subset n on each oracle's own panel. The row-level comparison is *width-cost-to-target on each oracle's own data*. The Soothsayer v1 row uses the same OOS 2023+ panel that backs §6 / §7 of Paper 1.

## Headline table

|   tau | oracle                           |    n | panel                                                      |   halfwidth_bps_at_tau |   realized_at_tau_band | k_or_kpct_supplier                                | notes                                                                              |
|------:|:---------------------------------|-----:|:-----------------------------------------------------------|-----------------------:|-----------------------:|:--------------------------------------------------|:-----------------------------------------------------------------------------------|
|  0.68 | soothsayer_v1_deployed           | 1730 | OOS 2023+ (yahoo daily, 173 weekends)                      |                    136 |                  0.680 | published                                         | Kupiec p_uc=0.984. Soothsayer publishes the calibrated band; no consumer back-fit. |
|  0.68 | soothsayer_m5_v2_candidate       | 1730 | OOS 2023+ (yahoo daily, 173 weekends)                      |                    110 |                  0.680 | published                                         | Kupiec p_uc=0.975. v2 candidate; deployment deferred until post-2026-05-10.        |
|  0.68 | pyth_smallest_k                  |  265 | OOS 2024+ available subset (n=265, SPY/QQQ/TLT/TSLA-heavy) |                    140 |                  0.800 | consumer-supplied k = 25.0 on `pyth_conf`         | Pyth `conf` is publisher-dispersion diagnostic, not coverage claim.                |
|  0.68 | chainlink_streams_smallest_k_pct |   87 | frozen 87-obs panel 2026-02-06 → 2026-04-17                |                    150 |                  0.736 | consumer-supplied k_pct = 1.50% on stale mid      | Chainlink bid/ask zeroed under marketStatus=5 (weekend); we wrap the stale mid.    |
|  0.68 | redstone_smallest_k_pct          |   12 | forward-tape, n=12 (4 weekends × 3 symbols)                |                    100 |                  0.750 | consumer-supplied k_pct = 1.00% on RedStone point | Forward-tape; sample grows weekly. Tape carries SPY/QQQ/MSTR underliers only.      |
|  0.85 | soothsayer_v1_deployed           | 1730 | OOS 2023+ (yahoo daily, 173 weekends)                      |                    251 |                  0.856 | published                                         | Kupiec p_uc=0.477. Soothsayer publishes the calibrated band; no consumer back-fit. |
|  0.85 | soothsayer_m5_v2_candidate       | 1730 | OOS 2023+ (yahoo daily, 173 weekends)                      |                    201 |                  0.850 | published                                         | Kupiec p_uc=0.973. v2 candidate; deployment deferred until post-2026-05-10.        |
|  0.85 | pyth_smallest_k                  |  265 | OOS 2024+ available subset (n=265, SPY/QQQ/TLT/TSLA-heavy) |                    279 |                  0.951 | consumer-supplied k = 50.0 on `pyth_conf`         | Pyth `conf` is publisher-dispersion diagnostic, not coverage claim.                |
|  0.85 | chainlink_streams_smallest_k_pct |   87 | frozen 87-obs panel 2026-02-06 → 2026-04-17                |                    250 |                  0.885 | consumer-supplied k_pct = 2.50% on stale mid      | Chainlink bid/ask zeroed under marketStatus=5 (weekend); we wrap the stale mid.    |
|  0.85 | redstone_smallest_k_pct          |   12 | forward-tape, n=12 (4 weekends × 3 symbols)                |                    250 |                  1.000 | consumer-supplied k_pct = 2.50% on RedStone point | Forward-tape; sample grows weekly. Tape carries SPY/QQQ/MSTR underliers only.      |
|  0.95 | soothsayer_v1_deployed           | 1730 | OOS 2023+ (yahoo daily, 173 weekends)                      |                    443 |                  0.950 | published                                         | Kupiec p_uc=0.956. Soothsayer publishes the calibrated band; no consumer back-fit. |
|  0.95 | soothsayer_m5_v2_candidate       | 1730 | OOS 2023+ (yahoo daily, 173 weekends)                      |                    355 |                  0.950 | published                                         | Kupiec p_uc=0.956. v2 candidate; deployment deferred until post-2026-05-10.        |
|  0.95 | pyth_smallest_k                  |  265 | OOS 2024+ available subset (n=265, SPY/QQQ/TLT/TSLA-heavy) |                    279 |                  0.951 | consumer-supplied k = 50.0 on `pyth_conf`         | Pyth `conf` is publisher-dispersion diagnostic, not coverage claim.                |
|  0.95 | chainlink_streams_smallest_k_pct |   87 | frozen 87-obs panel 2026-02-06 → 2026-04-17                |                    400 |                  0.977 | consumer-supplied k_pct = 4.00% on stale mid      | Chainlink bid/ask zeroed under marketStatus=5 (weekend); we wrap the stale mid.    |
|  0.95 | redstone_smallest_k_pct          |   12 | forward-tape, n=12 (4 weekends × 3 symbols)                |                    250 |                  1.000 | consumer-supplied k_pct = 2.50% on RedStone point | Forward-tape; sample grows weekly. Tape carries SPY/QQQ/MSTR underliers only.      |

## Reading

Three things this table makes precise:

1. **Only Soothsayer publishes `halfwidth_bps_at_tau` directly.** Every other row's `halfwidth_bps_at_tau` is the smallest in the consumer-supplied k-sweep (k or k_pct) that crosses τ realised. The consumer pays the calibration cost themselves — Soothsayer publishes it as a first-class field with an audit-able receipt.
2. **Per-row sample sizes differ by an order of magnitude.** Soothsayer's row is on 1,720 OOS observations; Pyth's row is on its 265-obs available subset; Chainlink's row is on a 87-obs frozen panel; RedStone and Scope are forward-tape baselines whose sample grows weekly. Cell-to-cell differences must be read with this caveat.
3. **Forward-tape rows over-cover trivially under sample-window-specific gentle weekends.** RedStone's smallest k_pct hitting τ=0.95 looks small on a 12-obs sample where weekends have been mild; this is a sample-window feature and should be expected to widen as more weekends accrue (especially long weekends and earnings-adjacent windows).

## Per-oracle source reports

- Pyth: `reports/v1b_pyth_comparison.md`
- Chainlink Data Streams: `reports/v1b_chainlink_comparison.md`
- RedStone: `reports/v1b_redstone_comparison.md`
- Kamino Scope: `reports/v1b_kamino_scope_comparison.md`

## How to keep this current

Re-run the four per-oracle scripts then this unified runner whenever a new weekend's Yahoo Monday-open lands in scryer (typically Tuesday by 14:00 UTC):

```bash
PYTHONPATH=src .venv/bin/python scripts/redstone_benchmark_comparison.py
PYTHONPATH=src .venv/bin/python scripts/kamino_scope_benchmark_comparison.py
PYTHONPATH=src .venv/bin/python scripts/run_incumbent_oracle_unified_report.py
```

Pyth and Chainlink are not re-run by default (Pyth's panel is 2024+; Chainlink's is a frozen pre-cutover artifact); refresh those when extending their respective historical backfills.

Reproducible via `scripts/run_incumbent_oracle_unified_report.py`. Per-row data: `reports/tables/incumbent_oracle_unified_summary.csv`.