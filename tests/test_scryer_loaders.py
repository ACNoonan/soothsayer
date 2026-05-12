"""Smoke tests for `soothsayer.sources.scryer` loaders that read scryer
parquet directly. Each test skips when the relevant venue/data_type has
no on-disk partitions in the asserted window — keeps CI green when scryer
is bare while still catching schema regressions in normal runs.
"""
from __future__ import annotations

from datetime import date

import pytest

from soothsayer.sources.scryer import (
    _CEX_STOCK_PERP_OHLCV_COLUMNS,
    _CME_INTRADAY_1M_COLUMNS,
    _DEX_XSTOCK_SWAPS_COLUMNS,
    load_cex_stock_perp_ohlcv,
    load_cme_intraday_1m,
    load_dex_xstock_swaps,
)


def test_cex_stock_perp_ohlcv_empty_window():
    df = load_cex_stock_perp_ohlcv(
        "SPY",
        start=date(1990, 1, 1),
        end=date(1990, 1, 2),
    )
    assert list(df.columns) == _CEX_STOCK_PERP_OHLCV_COLUMNS
    assert df.empty


def test_dex_xstock_swaps_empty_window():
    df = load_dex_xstock_swaps(
        "TSLAx",
        start=date(1990, 1, 1),
        end=date(1990, 1, 2),
    )
    assert list(df.columns) == _DEX_XSTOCK_SWAPS_COLUMNS
    assert df.empty


def test_cex_stock_perp_ohlcv_live_window():
    df = load_cex_stock_perp_ohlcv(
        "SPY",
        start=date(2026, 4, 24),
        end=date(2026, 4, 28),
    )
    if df.empty:
        pytest.skip("cex_stock_perp/ohlcv has no SPY rows in [2026-04-24, 2026-04-28]")
    schema_versions = df["_schema_version"].unique()
    assert len(schema_versions) == 1, f"mixed schema versions: {schema_versions}"
    assert schema_versions[0] == "cex_stock_perp_ohlcv.v1"
    assert df["underlier_symbol"].eq("SPY").all()
    assert df["bar_open_ts"].dtype.kind == "i"
    assert (df[["open", "high", "low", "close"]].dtypes == "float64").all()


def test_dex_xstock_swaps_live_window():
    df = load_dex_xstock_swaps(
        "TSLAx",
        start=date(2026, 5, 1),
        end=date(2026, 5, 4),
    )
    if df.empty:
        pytest.skip("dex_xstock/swaps has no TSLAx rows in [2026-05-01, 2026-05-04]")
    schema_versions = df["_schema_version"].unique()
    assert len(schema_versions) == 1, f"mixed schema versions: {schema_versions}"
    assert df["xstock_symbol"].eq("TSLAx").all()
    assert df["block_time"].dtype.kind == "i"
    assert (df["price_per_xstock"] > 0).all()


def test_cme_intraday_1m_empty_window():
    df = load_cme_intraday_1m(
        "ES=F",
        start=date(1990, 1, 1),
        end=date(1990, 1, 2),
    )
    assert list(df.columns) == _CME_INTRADAY_1M_COLUMNS
    assert df.empty


def test_cme_intraday_1m_live_window():
    df = load_cme_intraday_1m(
        "ES=F",
        start=date(2026, 4, 24),
        end=date(2026, 4, 28),
    )
    if df.empty:
        pytest.skip("cme/intraday_1m has no ES=F rows in [2026-04-24, 2026-04-28]")
    schema_versions = df["_schema_version"].unique()
    assert len(schema_versions) == 1, f"mixed schema versions: {schema_versions}"
    assert df["symbol"].eq("ES=F").all()
    assert df["ts"].dtype.kind == "i"
    assert (df[["open", "high", "low", "close"]].dtypes == "float64").all()
