# soothsayer

**A statistically principled secondary price oracle for tokenized equities on Solana.**

Soothsayer publishes a continuous fair-value estimate and a time-varying confidence interval for xStocks (and similar tokenized real-world equity assets) during the closed-market windows — weekends, overnights, halts — where existing oracle feeds either publish nothing, or publish an opaque 24/7 median without a statement of uncertainty.

It is designed to be read **alongside** a primary price oracle (Chainlink, Pyth), not to replace one. Consumers — lending protocols, perp DEXs, RWA money markets — compose the two: primary oracle gives you the number, soothsayer gives you the band around it.

> This repo is currently in **Phase 0 — validation**. Four empirical tests on public data gate the build phase. The Rust/Anchor implementation begins only after the gating test (V1) produces a green-light result. See the roadmap below.

## Why this exists

Tokenized equities (xStocks from Backed Finance, Ondo Global Markets, SPVs generally) trade 24/7 on-chain while their underlyings are open only ~32% of wall-clock hours. During the other 68% — overnight gaps, weekends, halts — the on-chain token price drifts from a stale last-trade based on:

- Weekend index-future moves (ES, NQ)
- Cross-asset signals (BTC, sector ETF Friday close)
- On-chain swap flow on Meteora / Raydium / Orca
- CEX perp funding rates (Kraken xStock Perp launched Feb 2026)
- Residual issuer-credit and liquidity premia

Incumbents publish a single price through these windows. None publish a statistically-derived confidence interval conditioned on the drift regime. Consumers who want risk-aware behaviour — wider liquidation bands on weekends, size-down during toxic flow, pause on anomalies — currently build bespoke mechanisms over the top (Kamino's price-band shim is the canonical example).

Soothsayer is what you'd build if you wanted that second signal to come from one dedicated, transparent, model-based source.

## How it works (planned architecture)

Heavy lifting happens off-chain in Rust. A small on-chain program stores signed publisher updates for consumers to read.

| Layer | Role | Method |
|---|---|---|
| Ingest | Normalise ticks, swaps, funding, macro | Tokio async per-source |
| State | Per-asset fair-value + vol | Madhavan-Sobczyk 3-state SSM (Kalman filter online) |
| Cross-asset anchor | Tighten CI using related assets | Hasbrouck-style VECM against ES/NQ + sector ETFs |
| Conditional vol | HAR-RV + Yang-Zhang OHLC | Shapes the CI as a function of recent realized vol |
| Toxicity gate | Down-weight DEX flow during reflexive cascades | Exponential-kernel Hawkes branching ratio |
| Regime | Clock-based + residual anomaly | Rules first; HMM only if rules miss earnings/halts |
| Publisher | Sign + publish at a cadence that reflects uncertainty | Ed25519, update-on-threshold policy |

Full method stack with citations: see the project plan in the research vault (private, being migrated into `docs/` here as chapters stabilise).

## Current phase — validation

Four empirical tests, each with a pre-registered gate criterion:

| # | Test | Gate |
|---|---|---|
| V1 | Chainlink v11 weekend price bias vs NYSE Monday open | Pooled $E[e_T]$ significant with > 10 bps effect size |
| V2 | Madhavan-Sobczyk half-life replicates on xStock underlyings | Fit converges, φ > 0, half-life minutes–hours |
| V3 | Kraken perp funding adds incremental signal for Monday gap | δ significant at 5%, ΔR² > 2% |
| V4 | Hawkes toxicity gate beats fixed-weight DEX aggregation | Regime-dependent ordering across branching-ratio buckets |

V1 is the go/no-go for the full thesis. V2–V4 shape the MVP feature set.

Outputs land in `notebooks/V[1-4]_*.ipynb` and get consolidated into `reports/` as one-page writeups per test.

## Setup

```bash
uv sync
cp .env.example .env           # Helius key from dashboard.helius.dev — free tier is sufficient
uv run python -m ipykernel install --user --name soothsayer --display-name "soothsayer"
uv run jupyter lab
```

Phase 0 runs on free data only (`yfinance`, Kraken public REST, Helius free tier). Paid providers (Polygon, Databento) are on the TODO list for Phase 1 calibration.

## Repo layout

```
src/soothsayer/
  config.py       — env + constants
  universe.py     — tradeable universe
  cache.py        — parquet/json cache keyed by API call
  sources/        — one module per data feed
notebooks/        — V1-V4 validation notebooks
data/             — raw + processed (gitignored; recreated by running notebooks)
reports/          — charts, tables, per-test writeups
```

## Roadmap

- **Phase 0 (now).** V1–V4. Single-page Phase 0 writeup → go/no-go decision.
- **Phase 1.** Rust ingest + SSM + VECM + publisher. On-chain program choice (standalone Anchor vs Switchboard OracleJob) decided on day 1 of the implementation.
- **Phase 2.** Dashboard replaying known dislocations (Sep 2025 $TSLAr gap, Oct 10 2025 Solana cascade). Integration docs for Kamino-style consumers.
- **Beyond.** Token-2022 `ScaledUiAmount` rebasing correctness; MS-GARCH regime detector if rules miss earnings/halts; factor-model shrinkage for the long-tail xStocks.

## Contributing

Methodology critiques and new data sources are especially welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache-2.0](LICENSE).
