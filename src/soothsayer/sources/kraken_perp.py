"""
Kraken perpetual futures funding rates for xStock perps.

Used by V3 (funding-signal regression). Public REST, no auth.

Symbol convention: `PF_{TICKER}XUSD` where `{TICKER}X` matches our xStock symbol.
Example: SPYx -> PF_SPYXUSD.

API endpoints used:
  GET /derivatives/api/v3/instruments                             (discovery)
  GET /derivatives/api/v3/historical-funding-rates?symbol=...     (history)

As of April 2026: rates are hourly (not 8h as originally assumed in research note);
~2999 observations returned per call, covering roughly Dec 2025 -> present. If a
future horizon hits a response cap, this module will need windowed paging.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

import pandas as pd
import requests

from ..cache import parquet_cached

BASE = "https://futures.kraken.com/derivatives/api/v3"
TIMEOUT = 20


def to_perp_symbol(xstock_symbol: str) -> str:
    """'SPYx' -> 'PF_SPYXUSD'. Idempotent on already-normalised input."""
    base = xstock_symbol.upper().rstrip("X") + "X"
    return f"PF_{base}USD"


def list_matching_perps(known_underlyings: Sequence[str]) -> list[str]:
    """Return the PF_*XUSD symbols Kraken lists whose underlying ticker is in `known_underlyings`.

    The raw instruments endpoint mixes xStock perps with crypto-asset perps (AVAX, GMX, CFX, ...),
    all sharing `type=flexible_futures`. Filtering by known underlyings avoids false matches.
    """
    r = requests.get(f"{BASE}/instruments", timeout=TIMEOUT)
    r.raise_for_status()
    instr = r.json().get("instruments", [])
    expected = {f"PF_{u.upper()}XUSD" for u in known_underlyings}
    return sorted(
        i["symbol"]
        for i in instr
        if i.get("type") == "flexible_futures"
        and i.get("tradeable")
        and i["symbol"] in expected
    )


def fetch_funding(perp_symbol: str) -> pd.DataFrame:
    """Full available history of funding rates for a perp symbol, hourly cadence."""
    key = {"symbol": perp_symbol}

    def _go() -> pd.DataFrame:
        r = requests.get(
            f"{BASE}/historical-funding-rates",
            params={"symbol": perp_symbol},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        payload = r.json()
        if payload.get("result") != "success":
            raise RuntimeError(f"kraken error for {perp_symbol}: {payload}")
        rates = payload.get("rates", [])
        if not rates:
            raise RuntimeError(
                f"kraken returned zero rates for {perp_symbol} — symbol may not exist"
            )
        df = pd.DataFrame(rates)
        df["ts"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.rename(
            columns={
                "fundingRate": "funding_rate",
                "relativeFundingRate": "relative_funding_rate",
            }
        )
        df["symbol"] = perp_symbol
        return (
            df[["symbol", "ts", "funding_rate", "relative_funding_rate"]]
            .sort_values("ts")
            .reset_index(drop=True)
        )

    return parquet_cached("kraken_funding", key, _go)


def fetch_funding_many(
    perp_symbols: Sequence[str], *, rest_between: float = 0.25
) -> pd.DataFrame:
    """Concat funding history for multiple perps, with a small pause between requests."""
    frames: list[pd.DataFrame] = []
    for s in perp_symbols:
        frames.append(fetch_funding(s))
        time.sleep(rest_between)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
