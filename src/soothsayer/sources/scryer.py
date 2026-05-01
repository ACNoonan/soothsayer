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


def load_yahoo_earnings(symbol: str, start: DateLike, end: DateLike) -> pd.DataFrame:
    """Yahoo earnings-calendar rows for one symbol in ``[start, end]``.

    Schema: ``earnings.v1``. Columns include ``symbol``, ``earnings_date``
    (arrow Date32) plus the four scryer metadata columns.
    """
    paths = _yearly_partition_paths(
        "yahoo", "earnings", start, end, key=("symbol", symbol)
    )
    df = _read_concat(
        paths,
        empty_columns=[
            "symbol", "earnings_date", "_schema_version", "_fetched_at",
            "_source", "_dedup_key",
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
