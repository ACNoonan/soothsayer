# CLAUDE.md — soothsayer

Calibration-transparent fair-value oracle for tokenized RWAs on Solana.
See `README.md` for the product shape and
`reports/methodology_history.md` for the (append-only) methodology log.

## Read first

- `README.md` — what soothsayer is, the served-band shape, the empirical
  evidence (Kupiec / Christoffersen passes at τ ∈ {0.68, 0.85, 0.95}).
- `reports/methodology_history.md` — append-only audit trail. The current
  state of the world is summarised in §0; the path is the dated entries
  in §1. Code that contradicts the locked decisions either updates the
  log first (with a new dated entry) or doesn't get merged.
- `docs/methodology_scope.md` — the four-question filter for which RWA
  classes the methodology applies to.
- `docs/scryer_consumer_guide.md` — how to read scryer parquet from
  soothsayer (the only sanctioned data path; see hard rule #1).

When citing a methodology decision in a response, cite the dated section
so the user can jump to it (e.g., "see the 2026-04-26 serving-layer
ablation entry in `reports/methodology_history.md`").

## Hard rules in this repo

These are the rules where the failure mode is silent — duplicated retry
logic, ad-hoc fetchers that drift from scryer's schemas, analysis
results that aren't reproducible — and where the cost of breaking them
is large.

1. **All data fetching goes via scryer.** Soothsayer is an analysis +
   serving + on-chain-publish project. It does not pull data from the
   network. Never call external APIs from soothsayer code or scripts:
   no `requests.get`, no `httpx`, no `yfinance.download`, no
   `solana-py`/Helius/Jupiter/Kraken HTTP calls, no Web3 RPC. The data
   you want is at
   `/Users/adamnoonan/Library/Application Support/scryer/dataset/{venue}/{data_type}/v{N}/...`
   (the launchd-writable canonical root, available as
   `soothsayer.config.SCRYER_DATASET_ROOT`) or pullable via `scry ...`
   for live runs. See `docs/scryer_consumer_guide.md` for the read
   pattern and `soothsayer.sources.scryer` for the canonical loaders.

2. **New data sources go in scryer first.** If soothsayer needs data
   scryer doesn't have, the work order is: (a) add a phase entry to
   `scryer/methodology_log.md` per scryer's hard rule #1, (b) implement
   the fetcher + schema in scryer, (c) consume the resulting parquet
   here. The queue lives at `scryer/wishlist.md` (Priority 0 / 1 / 2
   buckets, with effort estimates and suggested execution order).
   Do not write a one-off scrape in soothsayer "just to unblock
   analysis" — every previous version of that workaround silently
   diverged from the scryer schema and we are spending this transition
   cleaning that up.

3. **Analysis reads scryer parquet, not raw API output.** Use
   `polars.read_parquet` or `pd.read_parquet` against the
   `dataset/{venue}/{data_type}/v{N}/...` glob. Do not materialise
   JSON→DataFrame inside soothsayer code — that's scryer's job,
   precisely so the dedup / `_dedup_key` semantics and the
   reproducibility-modulo-`_fetched_at` guarantee hold across re-runs.

4. **Preserve `_schema_version`, `_fetched_at`, `_source` on read.**
   Every scryer row carries these three metadata columns. Don't drop
   them when loading. Calibration runs and paper artefacts should
   record which `_fetched_at` cutoff they used so re-runs are
   reproducible. Selecting on `_schema_version` is how you guard
   against silent schema upgrades (`v5_tape.v1` → `v5_tape.v2`).

5. **Soothsayer-side derived datasets follow scryer's experiment-
   versioned venue rule.** When soothsayer writes its own derived
   parquet (calibration surface, panel, served-band log), the venue is
   `soothsayer_v{N}` (matching the experiment iteration), the
   data_type is the artefact (`tape`, `bounds`, `panel`, ...), and the
   schema version is independent. See the 2026-04-27 "Soothsayer venue
   versioning" lock in `scryer/methodology_log.md`. Don't reuse a
   `soothsayer_v5` venue for v6 outputs even if the row schema is
   unchanged — old data stays at the old venue forever.

6. **Reproducibility.** Re-running an analysis script over the same
   `(scryer dataset, _fetched_at cutoff)` must produce identical
   output (modulo wall-clock timestamps in logs). If it doesn't, the
   read pattern is non-deterministic — fix that, don't paper over it.

## When the user proposes something that breaks one of these

Don't silently comply. Name the rule, cite the relevant methodology
section, and ask whether this is a deliberate exception (rare —
think: a one-off probe at the REPL, never committed) or whether the
plan needs to change.

The most common cases:

- "Just pull this data quickly here so I can test something" → No.
  Even in a notebook, the right path is `scry import ...` or
  `scry {venue} {data_type} ...` and read parquet. The notebook should
  not contain `requests.get(...)`.
- "We can add the fetcher to soothsayer and migrate it later" →
  No. The whole point of the cutover (April 2026) was that "later"
  never happens; soothsayer accumulates fetcher code that drifts
  from scryer's contracts. New sources land in scryer first.
- "Helius / Jupiter / Kraken has this nice API endpoint, can we…" →
  Open an item in `scryer/wishlist.md` and a methodology row in
  `scryer/methodology_log.md`; come back here when the parquet exists.

## Project layout

After the April 2026 cutover (data-fetching code consolidated into
scryer; see the 2026-04-27 "Data-fetching cutover" entry in
`reports/methodology_history.md`):

```
src/soothsayer/
  oracle.py                  Oracle.fair_value() serving API
  universe.py                xStock universe + mint registry (constants)
  config.py                  env / paths + SCRYER_DATASET_ROOT
  sources/scryer.py          scryer parquet loaders (kamino_scope, pyth,
                             redstone, soothsayer_v5, geckoterminal) —
                             the canonical read path
  backtest/                  panel assembly, forecasters, regimes,
                             calibration, metrics, protocol-compare
  chainlink/                 v10 / v11 decoders + Verifier parser
                             (decoders only — no fetching;
                             the historical scraper.py was deleted in
                             the April 2026 cutover)
  bot/                       devnet-bot tape + decision logic

scripts/                     analysis runners + reporting
                             (data-fetching scripts deleted in
                             the April 2026 cutover; remaining scripts
                             read scryer parquet)

reports/                     paper drafts + methodology log
                             paper1_coverage_inversion/
                             paper3_liquidation_policy/
                             methodology_history.md  (the log)

crates/
  soothsayer-core            shared types + math
  soothsayer-oracle          Rust port of oracle.py (75/75 parity)
  soothsayer-consumer        on-chain-consumer reference example
  soothsayer-publisher       publish-path crate
  soothsayer-demo-kamino     Kamino-integration demo

programs/soothsayer-oracle-program   Anchor program (BPF/SBF target;
                                     excluded from the host workspace)

data/
  raw/        deprecated; new code reads from
              `/Users/adamnoonan/Library/Application Support/scryer/dataset/`
              via `SCRYER_DATASET_ROOT` (override with the env var of the
              same name). Files retained for the in-flight Phase 1 papers
              until each script's reader is migrated.
  processed/  soothsayer-side derived artefacts (v1b_bounds.parquet,
              v1b_panel.parquet, weekend_comparison_*.json,
              kamino_xstocks_snapshot_*.json, etc.). NOT scryer raw data.
  bot_tape/   devnet-bot output JSONL.

`/Users/adamnoonan/Library/Application Support/scryer/dataset/`
              canonical scryer dataset root. The only sanctioned data
              path. launchd-managed daemons (`scry-*` plists in scryer's
              `ops/launchd/`) write here directly. The legacy
              `../scryer/dataset/` sibling-checkout location is
              deprecated for live tapes.
              See docs/scryer_consumer_guide.md.
```

## Read pattern (canonical)

```python
import polars as pl
from soothsayer.config import SCRYER_DATASET_ROOT

# Yahoo daily bars for SPY across all years
spy_bars = pl.read_parquet(
    SCRYER_DATASET_ROOT / "yahoo" / "equities_daily" / "v1" /
    "symbol=SPY" / "year=*.parquet"
)
# Sanity-check the schema version you expect:
assert (spy_bars.select(pl.col("_schema_version").unique()).item() == "yahoo.v1")

# v5 tape across a date range (the v5 calibration tape)
v5 = pl.read_parquet(
    SCRYER_DATASET_ROOT / "soothsayer_v5" / "tape" / "v1" /
    "year=2026" / "month=04" / "day=*.parquet"
)
```

Full guide with all 12 scryer schemas and gotchas:
`docs/scryer_consumer_guide.md`.

## Available scryer data (live root verified 2026-04-29)

Consumer-readable today, no fetching needed:

| venue              | data_type        | schema                       |
|--------------------|------------------|------------------------------|
| `backed`           | `corp_actions`   | `backed.v1`                  |
| `geckoterminal`    | `trades`         | `geckoterminal.v1`           |
| `kraken`           | `funding`        | `kraken_funding.v1`          |
| `kamino_scope`     | `oracle_tape`    | `kamino_scope.v1`            |
| `nasdaq`           | `halts`          | `nasdaq_halts.v1`            |
| `pyth`             | `oracle_tape`    | `pyth.v1`                    |
| `redstone`         | `oracle_tape`    | `redstone.v1`                |
| `soothsayer_v5`    | `tape`           | `v5_tape.v1`                 |
| `yahoo`            | `equities_daily` | `yahoo.v1` (daily OHLCV)     |
| `yahoo`            | `earnings`       | `earnings.v1`                |

Everything else is in `scryer/wishlist.md`.

## Status

Phase 0 complete (V1b decade-scale backtest, full PASS); Phase 1 in
flight (devnet deploy, Paper 1 drafting, Paper 3 drafting).
Data-fetching cutover April 2026: scryer is the source of truth for
all upstream data; soothsayer is the analysis + serving layer.
