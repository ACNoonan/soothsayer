# §6.x Path coverage — endpoint vs intra-weekend

Endpoint coverage (§6.2) tests whether the realised Monday open lies inside the served band. A DeFi consumer holding an xStock as collateral is exposed at every block over the weekend, not only at Monday open. This section reports the fraction of weekends on which a 24/7-traded reference for each symbol stays inside the served band over the entire prediction window `[Fri 16:00 ET, Mon 09:30 ET]`.

Three complementary references are used:

1. **Stock-perp 24/7 reference** (`cex_stock_perp/ohlcv/v1`). Kraken Futures `PF_<sym>XUSD` perps backed by xStocks; price the underlier continuously over the weekend. *Primary path measure.*
2. **On-chain xStock path** (`dex_xstock/swaps/v1`). The consumer-experienced object on Solana. *Ground-truth check.*
3. **Factor-projected path** (CME 1m). Tests whether the band holds against the band's own factor projection — a smoothness check on the deployed point estimator, **not** a consumer-experienced measure.


## (1) Stock-perp 24/7 reference (primary)

Sample: 118 (symbol, weekend) pairs across 19 unique calendar weekends, 2025-12-19 → 2026-04-24. SPY/QQQ/GLD perps live since 2025-12-22; AAPL/TSLA/HOOD/MSTR/GOOGL/NVDA since 2026-02-16+. TLT excluded (no perp listing). The sample is small but it is the right object — every reading is what a consumer would have observed on a 24/7 reference venue at that minute.

**Pooled by τ.**

|    tau |        n |   endpoint_cov |   path_cov |   gap_pp |
|-------:|---------:|---------------:|-----------:|---------:|
| 0.6800 | 118.0000 |         0.6441 |     0.3475 |  29.6610 |
| 0.8500 | 118.0000 |         0.8644 |     0.5678 |  29.6610 |
| 0.9500 | 118.0000 |         0.9492 |     0.7881 |  16.1017 |
| 0.9900 | 118.0000 |         0.9915 |     0.9153 |   7.6271 |


**Pooled by τ × regime.**

|    tau | regime_pub   |   n |   endpoint_cov |   path_cov |   gap_pp |
|-------:|:-------------|----:|---------------:|-----------:|---------:|
| 0.6800 | high_vol     |  45 |         0.6000 |     0.4000 |  20.0000 |
| 0.6800 | long_weekend |   7 |         0.4286 |     0.2857 |  14.2857 |
| 0.6800 | normal       |  66 |         0.6970 |     0.3182 |  37.8788 |
| 0.8500 | high_vol     |  45 |         0.8222 |     0.6444 |  17.7778 |
| 0.8500 | long_weekend |   7 |         0.7143 |     0.5714 |  14.2857 |
| 0.8500 | normal       |  66 |         0.9091 |     0.5152 |  39.3939 |
| 0.9500 | high_vol     |  45 |         0.9333 |     0.8222 |  11.1111 |
| 0.9500 | long_weekend |   7 |         0.8571 |     0.8571 |   0.0000 |
| 0.9500 | normal       |  66 |         0.9697 |     0.7576 |  21.2121 |
| 0.9900 | high_vol     |  45 |         1.0000 |     0.9778 |   2.2222 |
| 0.9900 | long_weekend |   7 |         1.0000 |     0.8571 |  14.2857 |
| 0.9900 | normal       |  66 |         0.9848 |     0.8788 |  10.6061 |


## (2) On-chain xStock path (ground truth, post-launch slice)

On-chain xStock swaps from `dex_xstock/swaps/v1` give the consumer-experienced object directly (no scaling). Sample is the post-launch slice currently cached in scryer; this is the right object for the DeFi consumer story but small-N until V3.1 / scryer item 51 backfill matures.


_No on-chain weekend overlap with the panel (0 weekends found). The dex_xstock cache currently begins after the panel's last Monday — the next artefact rebuild will pick this up._



## (3) Factor-projected path (CME 1m, smoothness check)

For each (symbol, weekend) the path is constructed from the per-symbol futures factor (ES=F for equities, GC=F for GLD, ZN=F for TLT) by scaling with `fri_close / F_anchor`. The band centre `point` is itself a function of the factor return, so this measures whether the band holds against the *projection's* trajectory — not whether it holds against an independent observation of fair value. CME 1m covers Friday 09:30–17:00 ET and Sunday 18:00 ET onwards; the Friday 17:00 ET → Sunday 18:00 ET Globex-dark window is unobservable. Mean observable share: `95.1%`. MSTR post-2020-08 is excluded (BTC tape absent from scryer cache). CME tape coverage starts 2018-01-05; the resulting panel is 15412 (symbol, weekend) rows.

**Pooled by τ.**

|    tau |         n |   endpoint_cov |   path_cov |   gap_pp |
|-------:|----------:|---------------:|-----------:|---------:|
| 0.6800 | 3853.0000 |         0.6867 |     0.6787 |   0.8046 |
| 0.8500 | 3853.0000 |         0.8505 |     0.8523 |  -0.1817 |
| 0.9500 | 3853.0000 |         0.9556 |     0.9608 |  -0.5191 |
| 0.9900 | 3853.0000 |         0.9927 |     0.9922 |   0.0519 |


**Pooled by τ × regime.**

|    tau | regime_pub   |    n |   endpoint_cov |   path_cov |   gap_pp |
|-------:|:-------------|-----:|---------------:|-----------:|---------:|
| 0.6800 | high_vol     | 1025 |         0.6937 |     0.6429 |   5.0732 |
| 0.6800 | long_weekend |  405 |         0.6617 |     0.6691 |  -0.7407 |
| 0.6800 | normal       | 2423 |         0.6880 |     0.6954 |  -0.7429 |
| 0.8500 | high_vol     | 1025 |         0.8498 |     0.8312 |   1.8537 |
| 0.8500 | long_weekend |  405 |         0.8321 |     0.8420 |  -0.9877 |
| 0.8500 | normal       | 2423 |         0.8539 |     0.8630 |  -0.9080 |
| 0.9500 | high_vol     | 1025 |         0.9561 |     0.9493 |   0.6829 |
| 0.9500 | long_weekend |  405 |         0.9580 |     0.9753 |  -1.7284 |
| 0.9500 | normal       | 2423 |         0.9550 |     0.9633 |  -0.8254 |
| 0.9900 | high_vol     | 1025 |         0.9922 |     0.9902 |   0.1951 |
| 0.9900 | long_weekend |  405 |         1.0000 |     1.0000 |   0.0000 |
| 0.9900 | normal       | 2423 |         0.9917 |     0.9917 |   0.0000 |


## Reading
- For (1) and (2), `gap_pp = endpoint_cov - path_cov`. Positive `gap_pp` is the share of weekends where the band held at Monday open but was punctured at some point intra-weekend. This is the load-bearing risk for a DeFi consumer.
- For (3), `gap_pp` is typically *negative* — the projected path stays inside the band by construction (the centre is the projection); the residual surprise is concentrated at the Monday open print. The signed gap diagnoses *where* coverage failures occur (Monday open vs intra-weekend), not their absolute level.
- A consumer requiring path coverage at level τ rather than endpoint coverage at level τ should consult the (1)/(2) gap and either widen via the circuit-breaker mechanism of §9.1 or step up to the next anchor.
- The full path-coverage validation requires (1)/(2) sample size to mature; the present table establishes the methodology and the first read on direction. Continued capture is tracked under scryer item 51 and §10.1's V3.3.
