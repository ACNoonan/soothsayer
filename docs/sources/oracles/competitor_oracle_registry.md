# `Competitor Oracle Registry` — Canonical comparator contract

---

**Last verified:** `2026-05-02`
**Scope:** Chainlink Data Streams v10/v11, Pyth (regular + Pro), RedStone Live.
**Role in soothsayer stack:** `canonical comparator registry` (source-of-truth summary that maps public docs to observed schema/tape behavior).
**Upstream ownership boundary:** Raw schemas and captured oracle data are owned by scryer; Soothsayer owns reconciliation, comparator semantics, and publication framing.

---

## 1. Purpose

This file is the single canonical place for "what competitors publish" in the form Soothsayer needs:

- what providers claim in current public docs,
- what fields/schemas we actually receive in scryer parquet,
- which signals are valid comparator inputs,
- which signals are not valid for coverage claims,
- where documentation and observed behavior disagree.

Use this file first, then drill into per-provider files in `docs/sources/oracles/`.

---

## 2. Canonical sources

### 2.1 Public docs snapshots (current)

- Chainlink v10 Tokenized Asset schema:
  - [https://docs.chain.link/data-streams/reference/report-schema-v10](https://docs.chain.link/data-streams/reference/report-schema-v10)
- Chainlink v11 RWA Advanced schema:
  - [https://docs.chain.link/data-streams/reference/report-schema-v11](https://docs.chain.link/data-streams/reference/report-schema-v11)
- Chainlink report-schema overview:
  - [https://docs.chain.link/data-streams/reference/report-schema-overview](https://docs.chain.link/data-streams/reference/report-schema-overview)
- Pyth Pro payload reference:
  - [https://docs.pyth.network/price-feeds/pro/payload-reference](https://docs.pyth.network/price-feeds/pro/payload-reference)
- Pyth market hours:
  - [https://docs.pyth.network/price-feeds/core/market-hours](https://docs.pyth.network/price-feeds/core/market-hours)
- RedStone Live feeds:
  - [https://docs.redstone.finance/docs/dapps/redstone-live-feeds/](https://docs.redstone.finance/docs/dapps/redstone-live-feeds/)

### 2.2 Scryer/Soothsayer observed surfaces (current)

- `dataset/soothsayer_v5/tape/v1/...` via `load_v5_window(...)` for joined comparator fields.
- `dataset/chainlink/data_streams/v1/...` (transport + decoded report tape).
- `dataset/pyth/oracle_tape/v1/...` via `load_pyth_window(...)`.
- `dataset/redstone/oracle_tape/v1/...` via `load_redstone_window(...)`.

---

## 3. Provider registry (docs vs observed vs comparator contract)

| Provider | Version / surface | Provider-published signals (docs) | Observed Soothsayer/Scryer signals | Comparator contract |
|---|---|---|---|---|
| Chainlink | v10 Tokenized Asset | `price`, `marketStatus`, `currentMultiplier`, `newMultiplier`, `activationDateTime`, `tokenizedPrice` | `cl_venue_px` (v10 `price`), `cl_tokenized_px` (v10 `tokenizedPrice`), `cl_market_status` in `soothsayer_v5/tape` | Use `tokenizedPrice` as the weekend point-estimate comparator. Never treat v10 as publishing a coverage interval. |
| Chainlink | v11 RWA Advanced | `mid`, `lastSeenTimestampNs`, `bid`, `ask`, `bidVolume`, `askVolume`, `lastTradedPrice`, expanded `marketStatus` | v11 decoded reports in `chainlink_data_streams/report_tape`; weekend synthetic-marker evidence in `reports/v11_cadence_verification.md` | Treat v11 weekend bid/ask-based spread as non-canonical unless bucket-level evidence says "real-quote". Keep provenance-specific verdicts by symbol/session. |
| Pyth | Regular feeds | `price`, `conf`, `expo`, publish time semantics; market-hour guidance by asset class | `pyth_price`, `pyth_conf`, `pyth_expo`, `pyth_publish_time`, EMA twins in `pyth/oracle_tape` | Use `k * conf` only as dispersion proxy comparator, not as a calibrated coverage SLA. |
| Pyth | Pro (formerly Lazer) | `feedUpdateTimestamp`, `marketSession`, optional `price/confidence`, experimental `bestBidPrice`/`bestAskPrice`; carry-forward semantics | No dedicated `pyth_pro` tape in Soothsayer today | Treat Pro claims as docs-only until we capture Pro-specific rows; do not silently map Pro behavior onto regular tape without evidence. |
| RedStone | Live feeds | WebSocket `price` (median from quorum), `redstonePackages` (raw signer packages), `passthrough` | `value`, `redstone_ts`, `source_json`, `provider_pubkey`, `signature` in `redstone/oracle_tape` | Use as point-estimate comparator only. No native confidence/band field exists on current public surface. |

---

## 4. Session behavior registry (coverage-critical)

These rows are canonical until replaced by newer evidence with explicit provenance.

| Provider | Session | Current canonical reading | Evidence anchor |
|---|---|---|---|
| Chainlink v10 | Weekend/closed | `price` stale; `tokenizedPrice` can continue updating | Chainlink v10 docs + `docs/sources/oracles/chainlink_v10.md` |
| Chainlink v11 | Weekend/closed | Non-null fields can exist, but bid/ask may be placeholder-derived by symbol; do not universalize from one feed | `reports/v11_cadence_verification.md`, `docs/sources/oracles/chainlink_v11.md` |
| Pyth regular | Weekend (US equities) | Market closed; comparator behavior depends on stale/age handling and confidence semantics | Pyth market-hours docs + `docs/sources/oracles/pyth_regular.md` |
| Pyth Pro | Sun-Thu overnight | Covered window exists, but this is not full Fri-close to Sun-open weekend coverage | Pyth Pro payload + market-hours docs + `docs/sources/oracles/pyth_lazer.md` |
| RedStone Live | Weekend/off-hours | Point estimates available for some underliers; no canonical band/confidence on public surface | RedStone Live docs + `docs/sources/oracles/redstone_live.md` |

---

## 5. Hard anti-regression rules

1. Do not collapse Chainlink v10 and v11 into a single schema claim.
2. Do not describe Pyth `conf` as a calibrated coverage guarantee.
3. Do not infer v11 weekend quote realism from `marketStatus` alone; require bucket-level evidence.
4. Do not claim RedStone publishes a confidence interval unless a documented field exists in captured schema.
5. Do not overwrite historical contradiction provenance; add new rows with date/source range/version.
6. If docs and observed parquet conflict, record both and mark verdict (`confirmed`, `contradicted`, `unmeasurable`) instead of rewriting history.

---

## 6. Relationship to per-provider files

This file is the canonical index/contract. Detailed reconciliations remain in:

- `docs/sources/oracles/chainlink_v10.md`
- `docs/sources/oracles/chainlink_v11.md`
- `docs/sources/oracles/chainlink_data_streams.md`
- `docs/sources/oracles/pyth_regular.md`
- `docs/sources/oracles/pyth_lazer.md`
- `docs/sources/oracles/redstone_live.md`

When any detailed file changes comparator semantics, update this file in the same PR.

---

## 7. Parquet analytics snapshot (`2026-05-02`)

Computed from local live parquet using `scripts/compute_competitor_oracle_analytics.py`.

### 7.1 Coverage sufficiency

| Surface | Rows | Window (UTC) | Sufficiency for trend claims |
|---|---:|---|---|
| `soothsayer_v5/tape/v1` | 44,224 | 2026-04-24 -> 2026-05-02 | Early but usable for preliminary weekend/off-hours basis behavior |
| `pyth/oracle_tape/v1` | 247,148 | 2026-01-31 -> 2026-05-02 | Sufficient for session-level variance/confidence analytics |
| `redstone/oracle_tape/v1` | 11,689 | 2026-03-27 -> 2026-05-02 | Sufficient for preliminary off-hours point-estimate variability analytics |
| `chainlink/data_streams/v1` | 53,781 | 2026-05-02 only | Snapshot diagnostics only; not enough for stable trend claims |

### 7.2 Current signal analytics

- `soothsayer_v5/tape` basis magnitude is slightly wider on weekends (`median |basis| ~10.49 bps`, `p90 ~23.61 bps`) vs weekdays (`median ~9.59 bps`, `p90 ~22.24 bps`).
- Pyth weekend rows show wider confidence (`median conf ~8.11 bps`, `p90 ~42.31 bps`) than weekdays (`median ~5.65 bps`, `p90 ~15.33 bps`), with near-zero step returns in weekend windows on this tape snapshot.
- RedStone weekend rows are materially higher-variance in point-estimate moves (`p90 abs return ~196 bps`) than weekdays (`~25 bps`) on the current SPY/QQQ/MSTR coverage.
- Chainlink v11 rows in current dedicated stream snapshot are all `market_status=5` with wide spread distribution (`median ~237 bps`, `p90 ~1037 bps`), but this is one-day evidence and symbols are not yet mapped in the parquet.

### 7.3 Interpretation guardrail

Do not publish regime-invariant claims from the current `chainlink/data_streams/v1` alone until at least multi-week coverage is present and feed_id->symbol mapping is recovered in the analysis layer.

---

## 8. Recurrence / feed-forward analytics job

- Recompute this snapshot by running:
  - `uv run python scripts/compute_competitor_oracle_analytics.py`
- Intended output is JSON for machine checks and dashboard ingestion; keep this registry section as the human-readable policy summary.
- Recommended next step (scryer-owned): add a scheduled analytics task that runs after tape updates and writes a derived analytics parquet (venue `soothsayer_vN`) so downstream docs/dashboards consume stable, versioned metrics rather than ad-hoc notebook outputs.

