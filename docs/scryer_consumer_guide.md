# Soothsayer consumer guide for scryer

Operational guide for reading scryer parquet from Soothsayer. This is the only sanctioned upstream data path.

## Rules

- Use `soothsayer.config.SCRYER_DATASET_ROOT` or `soothsayer.sources.scryer` loaders.
- Do not fetch upstream data directly from Soothsayer code or notebooks.
- Preserve `_schema_version`, `_fetched_at`, `_source`, and `_dedup_key` when present.
- Record `_fetched_at` cutoffs in calibration runs and paper artefacts.
- If the dataset is missing, add it to scryer first; do not write a local fetcher here.

## Dataset Root

Canonical live root on this machine:

```text
/Users/adamnoonan/Library/Application Support/scryer/dataset
```

Use the constant:

```python
from soothsayer.config import SCRYER_DATASET_ROOT
```

`../scryer/dataset` is offline replay only. It is not the live default.

## Path Shape

```text
{SCRYER_DATASET_ROOT}/{venue}/{data_type}/v{N}/{partition_path}.parquet
```

Common partition shapes:

| Shape | Example |
|---|---|
| `year=YYYY/month=MM/day=DD.parquet` | `pyth/oracle_tape/v1/year=2026/month=04/day=27.parquet` |
| `{key}=X/year=YYYY/month=MM/day=DD.parquet` | `geckoterminal/trades/v1/pool=.../year=2026/month=04/day=27.parquet` |
| `{key}=X/year=YYYY.parquet` | `yahoo/equities_daily/v1/symbol=SPY/year=2024.parquet` |
| `year=YYYY.parquet` | `nasdaq/halts/v1/year=2026.parquet` |

If exact layout matters, verify on disk. Older docs may contain stale shorthand.

## Read Recipes

Prefer helper loaders where available:

```python
from soothsayer.sources.scryer import (
    load_kamino_scope_window,
    load_pyth_window,
    load_redstone_window,
    load_v5_window,
    load_geckoterminal_trades,
)

scope = load_kamino_scope_window("2026-04-24", "2026-04-28")
v5 = load_v5_window("2026-04-24", "2026-04-28")
```

Direct polars read:

```python
import polars as pl
from soothsayer.config import SCRYER_DATASET_ROOT

spy = pl.read_parquet(
    SCRYER_DATASET_ROOT / "yahoo" / "equities_daily" / "v1" /
    "symbol=SPY" / "year=*.parquet"
)

assert spy.select(pl.col("_schema_version").unique()).item() == "yahoo.v1"
```

Date-range read:

```python
import datetime as dt
import polars as pl
from soothsayer.config import SCRYER_DATASET_ROOT

start, end = dt.date(2026, 4, 1), dt.date(2026, 4, 28)
paths = [
    SCRYER_DATASET_ROOT / "pyth" / "oracle_tape" / "v1" /
    f"year={d.year}" / f"month={d.month:02d}" / f"day={d.day:02d}.parquet"
    for d in (start + dt.timedelta(days=i) for i in range((end - start).days + 1))
]
pyth = pl.read_parquet([p for p in paths if p.exists()])
```

## Important Data Surfaces

Current high-value venues/data_types for Soothsayer work:

| Venue | data_type | Use |
|---|---|---|
| `yahoo` | `equities_daily`, `earnings`, `corp_actions` | underlier history and event filters |
| `cme` | `intraday_1m` | intraday factor / path-aware reference |
| `nasdaq` | `halts` | halt confounder filter |
| `backed` | `corp_actions`, `nav_strikes` | tokenized-stock issuer events |
| `pyth` | `oracle_tape` | oracle comparator |
| `chainlink_data_streams` | `report_tape` | v10/v11 comparator |
| `redstone` | `oracle_tape` | off-hours comparator |
| `kamino_scope` | `oracle_tape` | Kamino oracle path |
| `soothsayer_v5` | `tape` | Soothsayer forward band tape |
| `kamino` | `liquidations` | Paper 3 xStock empirical panel |
| `marginfi` | `reserves` | MarginFi deployment-substrate scan |
| `geckoterminal` | `trades` | pool trade signal |
| `solana_dex` | `xstock_swaps` | Paper 4 AMM panel root |
| `kraken` | `funding` | xStock perp funding |

Everything else should be checked against `../scryer/wishlist.md`.

## Reproducibility Hygiene

Assert schema:

```python
versions = df["_schema_version"].unique()
assert len(versions) == 1, f"mixed schema versions: {versions}"
```

Pin fetched-at:

```python
cutoff_unix = 1777411200
df = df.filter(pl.col("_fetched_at") <= cutoff_unix)
```

Carry provenance into derived outputs. At minimum, record source venue/data_type/schema and cutoff.

## When Data Is Missing

Use scryer, then read parquet:

```bash
cd ../scryer
cargo run --release --bin scry -- <venue> <data_type> ...
```

If no `scry` subcommand or schema exists, open/update `../scryer/wishlist.md` and add the required scryer methodology row before implementation.

## Gotchas

- Date columns usually arrive as Arrow `Date32`; keep them typed.
- Some large integer fields are decimal strings; cast deliberately.
- Timestamp precision varies by schema; inspect before time math.
- All timestamps are UTC. Convert to `America/New_York` only at window-definition boundaries.
