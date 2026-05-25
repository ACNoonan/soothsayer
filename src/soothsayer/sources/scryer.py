"""Scryer dataset readers.

The only sanctioned data path in soothsayer (per ``CLAUDE.md`` hard rule
#1). Each public ``load_*_window`` function takes a ``(start, end)`` date
range, globs the per-day partitions under ``SCRYER_DATASET_ROOT``,
and returns a single ``pandas.DataFrame``. Empty inputs return an
empty frame with the expected columns so downstream filtering is safe.

The loaders preserve the four scryer metadata columns
(``_schema_version``, ``_fetched_at``, ``_source``, ``_dedup_key``) — do
not drop them in callers; they are how reproducibility is enforced
across re-runs (see consumer guide §"Mandatory hygiene").
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Union

import pandas as pd

from soothsayer.config import SCRYER_DATASET_ROOT

DateLike = Union[str, date, datetime]


def _to_date(d: DateLike) -> date:
    if isinstance(d, datetime):
        return d.astimezone(timezone.utc).date() if d.tzinfo else d.date()
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d))


def _daily_partition_paths(
    venue: str,
    data_type: str,
    start: DateLike,
    end: DateLike,
    schema_version: str = "v1",
    key: Optional[tuple[str, str]] = None,
) -> list[Path]:
    """Resolve the list of ``year=Y/month=M/day=D.parquet`` files in
    ``[start, end]``. ``key`` is an optional ``(name, value)`` for
    pool/symbol-keyed datasets (e.g., ``("pool", "PQ7Hh...")``).
    """
    start_d = _to_date(start)
    end_d = _to_date(end)
    base = SCRYER_DATASET_ROOT / venue / data_type / schema_version
    if key is not None:
        base = base / f"{key[0]}={key[1]}"
    paths: list[Path] = []
    for d in pd.date_range(start_d, end_d, freq="D", tz="UTC"):
        p = (
            base
            / f"year={d.year:04d}"
            / f"month={d.month:02d}"
            / f"day={d.day:02d}.parquet"
        )
        if p.exists():
            paths.append(p)
    return paths


def _yearly_partition_paths(
    venue: str,
    data_type: str,
    start: DateLike,
    end: DateLike,
    schema_version: str = "v1",
    key: Optional[tuple[str, str]] = None,
) -> list[Path]:
    """Resolve the list of yearly partition files touched by ``[start, end]``.

    Used by low-frequency keyed datasets like ``yahoo/equities_daily`` and
    ``yahoo/earnings`` that partition as ``symbol=.../year=YYYY.parquet``.
    """
    start_d = _to_date(start)
    end_d = _to_date(end)
    base = SCRYER_DATASET_ROOT / venue / data_type / schema_version
    if key is not None:
        base = base / f"{key[0]}={key[1]}"
    paths: list[Path] = []
    for year in range(start_d.year, end_d.year + 1):
        p = base / f"year={year:04d}.parquet"
        if p.exists():
            paths.append(p)
    return paths


def _read_concat(paths: Iterable[Path], empty_columns: list[str]) -> pd.DataFrame:
    paths = list(paths)
    if not paths:
        return pd.DataFrame(columns=empty_columns)
    frames = [pd.read_parquet(p) for p in paths]
    return pd.concat(frames, ignore_index=True)


def load_yahoo_bars(symbol: str, start: DateLike, end: DateLike) -> pd.DataFrame:
    """Yahoo daily OHLCV rows for one symbol in ``[start, end]``.

    Schema: ``yahoo.v1``. Columns include ``symbol``, ``ts`` (arrow Date32),
    ``open``, ``high``, ``low``, ``close``, ``adj_close``, ``volume`` plus
    the four scryer metadata columns. Scryer's canonical live layout stores
    these rows under data_type ``equities_daily``; the ``bars`` fallback below
    exists only for older offline snapshots.
    """
    paths = _yearly_partition_paths(
        "yahoo", "equities_daily", start, end, key=("symbol", symbol)
    )
    if not paths:
        # Legacy sibling-checkout snapshots may still use the pre-cutover name.
        paths = _yearly_partition_paths(
            "yahoo", "bars", start, end, key=("symbol", symbol)
        )
    df = _read_concat(
        paths,
        empty_columns=[
            "symbol", "ts", "open", "high", "low", "close", "adj_close",
            "volume", "_schema_version", "_fetched_at", "_source",
            "_dedup_key",
        ],
    )
    if df.empty:
        return df
    ts = pd.to_datetime(df["ts"]).dt.date
    start_d = _to_date(start)
    end_d = _to_date(end)
    mask = (ts >= start_d) & (ts <= end_d)
    return df.loc[mask].reset_index(drop=True)


def load_cboe_index_daily(
    index_symbol: str, start: DateLike, end: DateLike,
) -> pd.DataFrame:
    """CBOE daily index rows (VIX, VIX9D, VIX1D, VIX3M, VIX6M, SKEW) in
    ``[start, end]``. Schema: ``cboe_indices.v1`` (venue ``cboe``, data_type
    ``indices``). Path layout ``cboe/indices/v1/index={IDX}/year={YYYY}.parquet``.

    The on-disk schema is ``(index, date, open, high, low, close)``. This
    loader normalises to a yahoo-bars-shaped frame so panel.py can join
    it without special-casing — `index` column is renamed to `symbol` and
    `date` to `ts`. Returns columns: ``symbol, ts, open, high, low,
    close`` plus the four scryer metadata columns.

    Note: CBOE indices have no `volume`, no `adj_close`. Soothsayer never
    reads either of those for VIX, so the absence is harmless.
    """
    paths = _yearly_partition_paths(
        "cboe", "indices", start, end, key=("index", index_symbol),
    )
    df = _read_concat(
        paths,
        empty_columns=[
            "index", "date", "open", "high", "low", "close",
            "_schema_version", "_fetched_at", "_source", "_dedup_key",
        ],
    )
    if df.empty:
        return pd.DataFrame(columns=[
            "symbol", "ts", "open", "high", "low", "close",
            "_schema_version", "_fetched_at", "_source", "_dedup_key",
        ])
    df = df.rename(columns={"index": "symbol", "date": "ts"})
    df["ts"] = pd.to_datetime(df["ts"]).dt.date
    start_d = _to_date(start)
    end_d = _to_date(end)
    mask = (df["ts"] >= start_d) & (df["ts"] <= end_d)
    return df.loc[mask].reset_index(drop=True)


def load_cme_daily_from_intraday(
    symbol: str, start: DateLike, end: DateLike,
) -> pd.DataFrame:
    """Resample ``cme/intraday_1m/v1`` to daily OHLCV for one futures
    symbol. Path layout ``cme/intraday_1m/v1/symbol={SYM}/year=Y/month=M/day=D.parquet``.

    Convention: each ``day=D.parquet`` partition holds 1m bars whose ``ts``
    (unix seconds UTC) falls within UTC-day D. Daily aggregation:

      open  = first bar's open
      high  = max bar high
      low   = min bar low
      close = last bar's close
      volume = sum

    The UTC-day boundary differs from Yahoo's daily-bar convention for
    futures (Yahoo aligns to ~17:00 ET CME session close). For ES=F,
    yahoo's daily close ≈ 21:00 UTC; this resample's daily close ≈ 21:59
    UTC (last 1m bar before CME's 22:00 UTC daily break). Drift is
    typically <0.1% on the close-to-close return; documented for the
    forward-tape harness consumer.

    Returns columns: ``symbol, ts (date), open, high, low, close, volume``.
    """
    paths = _daily_partition_paths(
        "cme", "intraday_1m", start, end,
        key=("symbol", symbol),
    )
    if not paths:
        return pd.DataFrame(columns=[
            "symbol", "ts", "open", "high", "low", "close", "volume",
        ])
    rows: list[dict] = []
    for p in paths:
        df = pd.read_parquet(p)
        if df.empty:
            continue
        # Group by UTC date — every bar in `day=D.parquet` is by definition
        # within UTC day D, but rare edge cases can leak (e.g., midnight
        # boundary). Use date(ts) to be safe.
        df = df.sort_values("ts")
        date_series = pd.to_datetime(df["ts"], unit="s", utc=True).dt.date
        for ts_date, g in df.groupby(date_series, sort=True):
            rows.append({
                "symbol": symbol,
                "ts": ts_date,
                "open": float(g["open"].iloc[0]),
                "high": float(g["high"].max()),
                "low": float(g["low"].min()),
                "close": float(g["close"].iloc[-1]),
                "volume": int(g["volume"].sum()),
            })
    if not rows:
        return pd.DataFrame(columns=[
            "symbol", "ts", "open", "high", "low", "close", "volume",
        ])
    out = pd.DataFrame(rows).drop_duplicates(subset=["symbol", "ts"])
    return out.sort_values("ts").reset_index(drop=True)


def load_yahoo_earnings(symbol: str, start: DateLike, end: DateLike) -> pd.DataFrame:
    """Yahoo earnings-calendar rows for one symbol in ``[start, end]``.

    Schema: ``earnings.v2``. Columns include ``symbol``, ``earnings_date``
    (arrow Date32), ``session`` (enum: bmo / amc / dmh / unknown, relative to
    ``earnings_date`` in US/Eastern), ``session_confirmed`` (nullable bool:
    True = already reported / timing is fact, False = forward-estimated,
    None = migrated legacy row) plus the four scryer metadata columns.

    Timing (session) is 100% complete for already-reported earnings from 2015
    onward on the reporting universe; pre-2015 rows carry dates with
    session="unknown" (no source times that far back).
    """
    paths = _yearly_partition_paths(
        "yahoo", "earnings", start, end, key=("symbol", symbol),
        schema_version="v2",
    )
    df = _read_concat(
        paths,
        empty_columns=[
            "symbol", "earnings_date", "session", "session_confirmed",
            "_schema_version", "_fetched_at", "_source", "_dedup_key",
        ],
    )
    if df.empty:
        return df
    earnings_date = pd.to_datetime(df["earnings_date"]).dt.date
    start_d = _to_date(start)
    end_d = _to_date(end)
    mask = (earnings_date >= start_d) & (earnings_date <= end_d)
    return df.loc[mask].reset_index(drop=True)


def load_kamino_scope_window(start: DateLike, end: DateLike) -> pd.DataFrame:
    """Scope oracle-tape rows in ``[start, end]``.

    Schema: ``kamino_scope.v1``. Columns include ``poll_ts`` (iso str),
    ``symbol``, ``feed_pda``, ``scope_price``, ``scope_unix_ts``,
    ``scope_age_s``, ``scope_err``. Identical to the legacy
    ``kamino_scope_tape_*.parquet`` schema plus the four scryer
    metadata columns.
    """
    paths = _daily_partition_paths("kamino_scope", "oracle_tape", start, end)
    return _read_concat(
        paths,
        empty_columns=[
            "poll_ts", "symbol", "feed_pda", "chain_id",
            "scope_value_raw", "scope_exp", "scope_price", "scope_slot",
            "scope_unix_ts", "scope_age_s", "scope_err",
            "_schema_version", "_fetched_at", "_source", "_dedup_key",
        ],
    )


def load_pyth_window(start: DateLike, end: DateLike) -> pd.DataFrame:
    """Pyth oracle-tape rows in ``[start, end]``.

    Schema: ``pyth.v1``. Columns include ``poll_ts`` (iso str),
    ``poll_unix`` (int64), ``symbol`` (UNDERLIER ticker, e.g. "SPY"),
    ``session`` (regular/on/pre/post), ``pyth_price``, ``pyth_conf``,
    ``pyth_publish_time``, ``pyth_age_s``, ``pyth_half_width_bps``, plus
    EMA twin and per-feed metadata.

    Symbol convention is the *underlier* ticker; if you have an
    xStock symbol (``SPYx``) map to ``SPY`` before filtering.
    """
    paths = _daily_partition_paths("pyth", "oracle_tape", start, end)
    return _read_concat(
        paths,
        empty_columns=[
            "poll_ts", "poll_unix", "symbol", "session", "pyth_feed_id",
            "pyth_price", "pyth_conf", "pyth_expo", "pyth_publish_time",
            "pyth_age_s", "pyth_half_width_bps",
            "pyth_ema_price", "pyth_ema_conf", "pyth_ema_publish_time",
            "pyth_ema_half_width_bps", "slot", "pyth_err",
            "_schema_version", "_fetched_at", "_source", "_dedup_key",
        ],
    )


def load_redstone_window(start: DateLike, end: DateLike) -> pd.DataFrame:
    """RedStone oracle-tape rows in ``[start, end]``.

    Schema: ``redstone.v1``. Day-partitioned (the legacy soothsayer
    version was a single rolling file). ``poll_ts`` and ``redstone_ts``
    are arrow ``Timestamp(Microsecond, "UTC")``; cast to int via
    ``.view("int64") // 10**3`` if you need unix microseconds.
    """
    paths = _daily_partition_paths("redstone", "oracle_tape", start, end)
    return _read_concat(
        paths,
        empty_columns=[
            "poll_ts", "poll_label", "symbol", "redstone_ts",
            "minutes_age", "value", "provider_pubkey", "signature",
            "source_json", "permaweb_tx", "raw_json",
            "_schema_version", "_fetched_at", "_source", "_dedup_key",
        ],
    )


def load_v5_window(start: DateLike, end: DateLike) -> pd.DataFrame:
    """Soothsayer-v5 joined-tape rows in ``[start, end]``.

    Schema: ``v5_tape.v1`` (venue ``soothsayer_v5``). ``poll_ts`` is
    int64 unix seconds. The Jupiter columns
    (``jup_bid``, ``jup_ask``, ``jup_mid``, ``spread_bp``) are
    **non-null** in scryer — when a Jupiter call fails, scryer writes
    ``0.0`` sentinels plus a non-empty ``jup_err`` string. Filter
    Jupiter-valid rows with ``df[df["jup_err"] == ""]`` rather than
    the legacy ``df[df["jup_mid"].notna()]``.
    """
    paths = _daily_partition_paths("soothsayer_v5", "tape", start, end)
    return _read_concat(
        paths,
        empty_columns=[
            "poll_ts", "symbol", "cl_obs_ts", "cl_age_s",
            "cl_tokenized_px", "cl_venue_px", "cl_market_status", "cl_err",
            "jup_bid", "jup_ask", "jup_mid", "spread_bp", "jup_err",
            "basis_bp",
            "_schema_version", "_fetched_at", "_source", "_dedup_key",
        ],
    )


def load_geckoterminal_trades(
    pool: str, start: DateLike, end: DateLike
) -> pd.DataFrame:
    """GeckoTerminal pool-keyed trades in ``[start, end]``.

    Schema: ``geckoterminal.v1``. Columns match the legacy
    ``quant-work/lvr/fetch_geckoterminal.py`` output minus the ``dt``
    convenience column — derive it inline via
    ``df["dt"] = pd.to_datetime(df["ts"], unit="s", utc=True)``.

    ``pool`` is the full base58 address; never truncate.
    """
    paths = _daily_partition_paths(
        "geckoterminal", "trades", start, end, key=("pool", pool)
    )
    return _read_concat(
        paths,
        empty_columns=[
            "ts", "tx_hash", "block_number", "kind", "from_token", "to_token",
            "from_amount", "to_amount", "price_usd", "volume_usd",
            "_schema_version", "_fetched_at", "_source", "_dedup_key",
        ],
    )


_CME_INTRADAY_1M_COLUMNS = [
    "symbol", "ts", "open", "high", "low", "close", "volume",
    "_schema_version", "_fetched_at", "_source", "_dedup_key",
]


def load_cme_intraday_1m(
    symbol: str,
    start: DateLike,
    end: DateLike,
) -> pd.DataFrame:
    """Raw CME intraday 1m bars for one futures factor in ``[start, end]``.

    Schema: ``cme_intraday_1m.v1``. Path layout
    ``cme/intraday_1m/v1/symbol=X/year=Y/month=M/day=D.parquet``. ``ts`` is
    int64 unix seconds UTC. The companion ``load_cme_daily_from_intraday``
    helper resamples this surface to daily OHLCV; this loader returns the
    raw 1m bars and is the right call for path-coverage and intraday
    factor projection.

    ``symbol`` is the futures contract symbol (e.g. ``"ES=F"``, ``"GC=F"``,
    ``"ZN=F"``), matching the on-disk partition key.
    """
    paths = _daily_partition_paths(
        "cme", "intraday_1m", start, end, key=("symbol", symbol),
    )
    return _read_concat(paths, empty_columns=_CME_INTRADAY_1M_COLUMNS)


_CEX_STOCK_PERP_OHLCV_COLUMNS = [
    "exchange", "exchange_symbol", "underlier_symbol", "backing_kind",
    "bar_open_ts", "bar_close_ts",
    "open", "high", "low", "close",
    "volume_base", "volume_quote", "trade_count",
    "_schema_version", "_fetched_at", "_source", "_dedup_key",
]


def load_cex_stock_perp_ohlcv(
    underlier: str,
    start: DateLike,
    end: DateLike,
) -> pd.DataFrame:
    """1m OHLCV bars for one underlier's xStock-backed CEX perps in
    ``[start, end]``.

    Schema: ``cex_stock_perp_ohlcv.v1``. Path layout
    ``cex_stock_perp/ohlcv/v1/underlier=X/year=Y/month=M/day=D.parquet``.
    The on-disk venue today is Kraken Futures (``PF_<sym>XUSD``), but the
    partition is venue-agnostic — multi-venue rows will land in the same
    parquet once item 45's other operators ship.

    Returns all rows for ``underlier`` whose ``bar_open_ts`` UTC-date falls
    in ``[start, end]``. The caller is responsible for downstream filtering
    (e.g., ``backing_kind == "xstock_backed"``, ``volume_base > 0``, exchange
    selection). ``bar_open_ts`` and ``bar_close_ts`` are int64 unix seconds.
    """
    paths = _daily_partition_paths(
        "cex_stock_perp", "ohlcv", start, end, key=("underlier", underlier),
    )
    return _read_concat(paths, empty_columns=_CEX_STOCK_PERP_OHLCV_COLUMNS)


_DEX_XSTOCK_SWAPS_COLUMNS = [
    "signature", "slot", "block_time",
    "dex_program", "xstock_mint", "xstock_symbol",
    "counter_mint", "counter_symbol",
    "xstock_amount_lamports", "counter_amount_lamports",
    "price_per_xstock", "trader",
    "_schema_version", "_fetched_at", "_source", "_dedup_key",
]


def load_dex_xstock_swaps(
    xsymbol: str,
    start: DateLike,
    end: DateLike,
) -> pd.DataFrame:
    """On-chain Solana DEX swaps for one xStock symbol in ``[start, end]``.

    Schema: ``dex_xstock_swaps.v1``. Path layout
    ``dex_xstock/swaps/v1/symbol=X/year=Y/month=M/day=D.parquet``. Each
    row is one swap-IX from Raydium CLMM / Orca Whirlpools / Meteora DLMM
    / aggregator routes against the xStock SPL mint.

    Returns all swaps whose ``block_time`` (int64 unix seconds) UTC-date
    falls in ``[start, end]``. ``price_per_xstock`` is denominated in the
    counter asset; callers must filter on ``counter_symbol`` (typically
    ``"USDC"``) to get a USD-comparable series and scale ``WSOL``-quoted
    rows separately. ``xsymbol`` is the X-suffixed token symbol
    (``"TSLAx"``, ``"SPYx"``, ...) — not the underlying equity ticker.
    """
    paths = _daily_partition_paths(
        "dex_xstock", "swaps", start, end, key=("symbol", xsymbol),
    )
    return _read_concat(paths, empty_columns=_DEX_XSTOCK_SWAPS_COLUMNS)
