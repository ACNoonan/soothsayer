# AGENTS.md — soothsayer

Agent-facing short form. `CLAUDE.md` has the startup context; `reports/methodology_history.md` has the compact methodology ledger.

## Hard Rules

1. **No upstream fetching in soothsayer.** Do not add `requests.get`, `httpx`, `yfinance.download`, Solana RPC, Helius, Jupiter, Kraken, Web3, or similar fetches here. Data comes from scryer parquet under `SCRYER_DATASET_ROOT`.

2. **New sources go in scryer first.** Add the scryer methodology row / wishlist item, implement fetcher + schema in `../scryer`, then read parquet from Soothsayer.

3. **Read parquet, not raw API output.** Use `polars.read_parquet`, `pd.read_parquet`, or `soothsayer.sources.scryer` loaders against `dataset/{venue}/{data_type}/v{N}/...`.

4. **Preserve provenance.** Keep `_schema_version`, `_fetched_at`, `_source`, and `_dedup_key` where present. Record `_fetched_at` cutoffs in calibration and paper artefacts.

5. **Derived datasets use experiment-versioned venues.** Soothsayer-written parquet uses venue `soothsayer_v{N}` and artefact data_types (`tape`, `bounds`, `panel`, ...). Do not reuse old venues for new experiment iterations.

If a request would break a rule, stop and ask whether this is deliberate.

## Current Operating State

- Phase 0 validation is complete; Phase 1 is active.
- Current product: calibration-transparent band primitive with receipts.
- Current constants: default `τ=0.85`, headline Paper 1 `τ=0.95`, `τ=0.99` disclosed as v1 tail ceiling.
- Paper 3: three claims (Geometric / Structural / Empirical). Kamino-xStocks supplies the xStock event panel; MarginFi is the general-lending deployment-substrate argument.
- Paper 4/Product-stack: scryer item 51 forward tapes are time-sensitive; Soothsayer-side consumers come after parquet rows exist.

## Canonical Read Pattern

```python
import polars as pl
from soothsayer.config import SCRYER_DATASET_ROOT

spy = pl.read_parquet(
    SCRYER_DATASET_ROOT / "yahoo" / "equities_daily" / "v1" /
    "symbol=SPY" / "year=*.parquet"
)
assert spy.select(pl.col("_schema_version").unique()).item() == "yahoo.v1"
```

Read `docs/scryer_consumer_guide.md` before touching exact path layouts.

## Common Trap

The sibling `../scryer/dataset` checkout is offline replay only. The canonical live root is `/Users/adamnoonan/Library/Application Support/scryer/dataset` via `SCRYER_DATASET_ROOT`.

If you find imports from deleted Soothsayer source/fetch modules, migrate the caller to scryer parquet. Do not restore the fetcher.
