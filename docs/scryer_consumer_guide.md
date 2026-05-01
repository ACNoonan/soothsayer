# Soothsayer consumer guide for scryer

How to read scryer parquet from soothsayer code. This is the only
sanctioned data path after the April 2026 cutover; see CLAUDE.md hard
rule #1.

## Locating the dataset root

Production canonical root is **macOS Application Support**:

```
/Users/adamnoonan/Library/Application Support/scryer/dataset
```

scryer's launchd-managed live tapes write here, not `~/Documents/`,
because macOS 26.x TCC restricts launchd-spawned processes from
reading user-document directories. Soothsayer code should consume
this constant from `soothsayer.config`:

```python
from soothsayer.config import SCRYER_DATASET_ROOT  # canonical
# or via the loader helpers:
from soothsayer.sources.scryer import (
    load_kamino_scope_window, load_pyth_window, load_redstone_window,
    load_v5_window, load_geckoterminal_trades,
)
```

For replays / offline analysis you can override with the
`SCRYER_DATASET_ROOT` env var (e.g., point at a sibling
`../scryer/dataset` checkout that's been seeded with a snapshot).

The legacy sibling-checkout pattern (`../scryer/dataset`) is
deprecated; production is Application Support.

## Path layout

```
{SCRYER_ROOT}/{venue}/{data_type}/v{N}/{partition_path}.parquet
```

The `{partition_path}` shape depends on the data class:

| shape                                                  | granularity | example                                                                  |
|--------------------------------------------------------|-------------|--------------------------------------------------------------------------|
| `year=YYYY/month=MM/day=DD.parquet`                    | daily       | `dataset/pyth/oracle_tape/v1/year=2026/month=04/day=27.parquet`          |
| `{key}={value}/year=YYYY/month=MM/day=DD.parquet`      | daily/keyed | `dataset/solana_raydium_v4/swaps/v1/pool=...PQ/year=2024/month=11/day=05.parquet` |
| `{key}={value}/year=YYYY/month=MM.parquet`             | monthly/keyed | `dataset/kraken/funding/v1/symbol=PF_SPYUSD/year=2026/month=04.parquet`           |
| `{key}={value}/year=YYYY.parquet`                      | yearly/keyed  | `dataset/yahoo/equities_daily/v1/symbol=SPY/year=2024.parquet`                    |
| `year=YYYY.parquet`                                    | yearly      | `dataset/backed/corp_actions/v1/year=2026.parquet`                                |

Hive-style partitioning. `polars.read_parquet` and
`pd.read_parquet(engine="pyarrow")` auto-discover partition columns.

## Available datasets

Verified against the live `SCRYER_DATASET_ROOT` layout on 2026-04-29.

| venue              | data_type        | schema                       | partition shape          |
|--------------------|------------------|------------------------------|--------------------------|
| `backed`           | `corp_actions`   | `backed.v1`                  | yearly, no key           |
| `geckoterminal`    | `trades`         | `geckoterminal.v1`           | daily, keyed by `pool`   |
| `kraken`           | `funding`        | `kraken_funding.v1`          | monthly, keyed by `symbol`|
| `kamino_scope`     | `oracle_tape`    | `kamino_scope.v1`            | daily, no key            |
| `nasdaq`           | `halts`          | `nasdaq_halts.v1`            | yearly, no key           |
| `pyth`             | `oracle_tape`    | `pyth.v1`                    | daily, no key            |
| `redstone`         | `oracle_tape`    | `redstone.v1`                | daily, no key            |
| `soothsayer_v5`    | `tape`           | `v5_tape.v1`                 | daily, no key            |
| `yahoo`            | `equities_daily` | `yahoo.v1`                   | yearly, keyed by `symbol`|
| `yahoo`            | `earnings`       | `earnings.v1`                | yearly, keyed by `symbol`|

If a dataset you want isn't here, it's not in scryer yet. Don't write
a fetcher in soothsayer — open an item in `../scryer/wishlist.md` (it
already lists the queue) and add a methodology entry to
`../scryer/methodology_log.md` per scryer's hard rule #1.

## Read recipes

### Easiest: the helper module

For the common shapes (oracle tapes, soothsayer-v5 tape, geckoterminal
pool trades), prefer the loaders in `soothsayer.sources.scryer`:

```python
from soothsayer.sources.scryer import (
    load_kamino_scope_window, load_pyth_window, load_redstone_window,
    load_v5_window, load_geckoterminal_trades,
)

scope = load_kamino_scope_window("2026-04-24", "2026-04-28")
v5    = load_v5_window("2026-04-24", "2026-04-28")
trades = load_geckoterminal_trades(
    pool="PQ7Hh7yEkLRTd9Hh3eQiUhjWhCk8sx9MJWi9TejRnxqf",
    start="2024-11-01", end="2024-11-05",
)
```

Each loader globs the daily partitions across the date range and
returns a single `pandas.DataFrame` with the four metadata columns
preserved. Empty windows return empty DataFrames with the expected
columns rather than raising — call sites can skip the existence dance.

### Whole-dataset read

```python
import polars as pl
df = pl.read_parquet(SCRYER_ROOT / "yahoo" / "equities_daily" / "v1" / "**" / "*.parquet")
```

### One symbol across all years

```python
spy = pl.read_parquet(SCRYER_ROOT / "yahoo" / "equities_daily" / "v1" / "symbol=SPY" / "year=*.parquet")
```

### Date-range slice (no-key, daily)

```python
import datetime as dt

start, end = dt.date(2026, 4, 1), dt.date(2026, 4, 28)

paths = []
d = start
while d <= end:
    paths.append(SCRYER_ROOT / "pyth" / "oracle_tape" / "v1" /
                 f"year={d.year}" / f"month={d.month:02d}" / f"day={d.day:02d}.parquet")
    d += dt.timedelta(days=1)

pyth = pl.read_parquet([p for p in paths if p.exists()])
```

### One pool across one month (keyed, daily)

```python
pool = "PQ7Hh7yEkLRTd9Hh3eQiUhjWhCk8sx9MJWi9TejRnxqf"  # full address, never truncated
swaps = pl.read_parquet(
    SCRYER_ROOT / "solana_raydium_v4" / "swaps" / "v1" /
    f"pool={pool}" / "year=2024" / "month=11" / "day=*.parquet"
)
```

### pandas equivalent

```python
import pandas as pd
df = pd.read_parquet(SCRYER_ROOT / "yahoo" / "equities_daily" / "v1",
                     filters=[("symbol", "=", "SPY")])
```

## Mandatory hygiene

### 1. Assert the schema version

```python
versions = df["_schema_version"].unique()
assert len(versions) == 1, f"mixed schema versions: {versions}"
assert versions[0] == "yahoo.v1", f"expected yahoo.v1, got {versions[0]}"
```

The version column is how you catch silent schema upgrades. If
`yahoo.v2` lands in scryer, your code should explicitly opt in.

### 2. Pin and record `_fetched_at` for reproducibility

Calibration runs and paper artefacts must record which `_fetched_at`
cutoff they used:

```python
cutoff_unix = int(dt.datetime(2026, 4, 28, tzinfo=dt.timezone.utc).timestamp())
df = df.filter(pl.col("_fetched_at") <= cutoff_unix)
# ... record cutoff_unix in your output artefact
```

A re-run with the same cutoff produces identical results (modulo
later re-fetches that filled gaps), per scryer's
"reproducibility-modulo-`_fetched_at`" guarantee.

### 3. Don't drop the meta columns

`_schema_version`, `_fetched_at`, `_source`, and `_dedup_key` belong
on every soothsayer-side derived dataset that's traceable to scryer
input. If you write `data/processed/something.parquet`, carry the
provenance forward — at least `_source` (now meaning "scryer venue +
data_type + schema") and `_fetched_at` (the cutoff you pinned).

## Live data (when scryer parquet doesn't yet cover what you need)

Use `scry` directly, then re-read parquet:

```bash
# from the scryer checkout
cd ../scryer
cargo run --release --bin scry -- \
    solana kamino-liquidations \
    --start 2026-04-01 --end 2026-04-28 \
    --lending-market <PDA> \
    --proxy-url http://127.0.0.1:8899 \
    --helius-api-key $HELIUS_API_KEY
# then read the resulting parquet from soothsayer
```

If the data class you want has no `scry` subcommand yet, that means it
hasn't shipped — open a wishlist item, don't fetch from soothsayer.

## Migration cheat-sheet (deleted soothsayer scripts → scryer commands)

| deleted soothsayer script                          | scryer replacement                                                                |
|----------------------------------------------------|-----------------------------------------------------------------------------------|
| `scripts/scan_kamino_liquidations.py`              | `scry solana kamino-liquidations …`                                               |
| `scripts/scan_jupiter_lend_liquidations.py`        | `scry solana jupiter-lend-liquidations …`                                         |
| `scripts/snapshot_kamino_xstocks.py` / `..._obligations.py` | scryer wishlist Priority-1 #4 + #5 (kamino_reserve.v1 / kamino_obligation.v1) |
| `scripts/collect_pyth_xstock_tape.py`              | read `dataset/pyth/oracle_tape/v1/...`                                            |
| `scripts/collect_kamino_scope_tape.py`             | read `dataset/kamino_scope/oracle_tape/v1/...`                                    |
| `scripts/scrape_nasdaq_halts.py`                   | read `dataset/nasdaq/halts/v1/...`                                                |
| `scripts/scrape_backed_corp_actions.py`            | read `dataset/backed/corp_actions/v1/...`                                         |
| `scripts/run_redstone_scrape.py`                   | read `dataset/redstone/oracle_tape/v1/...`                                        |
| `scripts/build_fred_macro_calendar.py`             | scryer wishlist Priority-2 #16                                                    |
| `scripts/run_v5_tape.py`                           | read `dataset/soothsayer_v5/tape/v1/...`                                          |
| `scripts/run_v1_scrape.py` / `run_v1_backfill.py`  | read `dataset/yahoo/equities_daily/v1/...`                                        |
| `scripts/run_v2.py`                                | yfinance-minutes fetch superseded; current methodology uses daily bars            |
| `scripts/run_v3.py`                                | read `dataset/yahoo/equities_daily/v1/...` + `dataset/kraken/funding/v1/...`      |
| `scripts/scan_chainlink_schemas.py`                | scryer wishlist Priority-3 #17                                                    |
| `scripts/dump_v11_feed_inventory.py`, `enumerate_v11_xstock_feeds.py`, `verify_v11_cadence.py`, `debug_v10_layout.py` | scryer wishlist Priority-3 #17 (chainlink schema/cadence)               |
| `scripts/smoke_rpcfast.py`, `smoke_v5_jupiter.py`  | obsolete (smoke tests for deleted modules)                                        |

## Common gotchas

- **Date-typed columns.** scryer schemas use arrow `Date32` for daily
  dates (yahoo bars, earnings, backed corp_actions, nasdaq_halts).
  Polars surfaces these as `pl.Date`; pandas as `datetime64[ns]`.
  Don't reformat them — operate on the typed column.

- **`u128` columns are stored as decimal strings.** Currently only
  `jupiter_lend_liquidation.v1.col_per_unit_debt_raw`. Cast with
  `decimal.Decimal` (Python) or arrow `i256` (Rust) at read time.

- **Sub-second timestamps.** Some schemas store `ts` as `i64` unix
  seconds (swap.v1, kamino_liquidation.v1), some as `f64` unix
  seconds (trade.v1), some as arrow `Timestamp(Microsecond, UTC)`
  (kraken_funding.v1, redstone.v1, nasdaq_halts.v1, backed.v1
  `detected_at`). Inspect the schema before doing time math.

- **Daylight-saving / timezones.** All scryer timestamps are UTC.
  When converting to NYSE wall-clock for window definitions, use
  `pytz.timezone("America/New_York")` (or polars' tz cast).
