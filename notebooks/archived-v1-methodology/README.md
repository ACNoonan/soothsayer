# Archived V1-methodology notebooks

These notebooks were part of the original Phase 0 validation plan, built around the Madhavan-Sobczyk / VECM / HAR-RV / Hawkes methodology stack. The methodology pivoted 2026-04-24 (see `reports/v1b_decision.md` and `docs/product-spec.md`), and these notebooks are retained as historical decision trail rather than live code.

| Notebook | Intent | Outcome |
|---|---|---|
| `V2_ms_half_life.ipynb` | Madhavan-Sobczyk half-life replication on 8 xStocks | Stub (never fully implemented); methodology deprioritised |
| `V3_funding_signal.ipynb` | Kraken perp funding as Monday-gap predictor | Stub. Real V3 ran in `scripts/run_v3.py`; result: FAIL (δ p=0.63, ΔR² ≈ +0.23pp) |
| `V4_hawkes_toxicity.ipynb` | Hawkes branching-ratio DEX toxicity gate | Stub (never built); gate not needed per v1b |

Current methodology: see `src/soothsayer/backtest/` and `src/soothsayer/oracle.py`.

`V1_chainlink_weekend_bias.ipynb` remains at `notebooks/V1_chainlink_weekend_bias.ipynb` — it is an accurate historical record of the test that motivated the pivot and is referenced from `reports/v1b_decision.md`.
