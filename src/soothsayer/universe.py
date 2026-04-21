"""
The tradeable universe for Phase 0 validation.

The 8 xStocks Kamino has onboarded (SPYx, QQQx, GOOGLx, APPLx, NVDAx, TSLAx, MSTRx, HOODx)
are the core universe for V1/V2/V4. V3 adds GLDx and CRCLx from Kraken's perp listings where
present, but drops any ticker without a Kamino listing for the gap regression.

Mint addresses, pool addresses, and Chainlink feed IDs are filled in as each validation
module is implemented — left as None here so the file stays a single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XStock:
    symbol: str           # e.g. "SPYx"
    underlying: str       # yfinance ticker for the underlying, e.g. "SPY"
    mint: str | None = None          # Solana SPL mint (Token-2022)
    kamino_listed: bool = True


# Kamino-onboarded xStocks (as of April 2026 per research — DS 05 in vault)
CORE_XSTOCKS: tuple[XStock, ...] = (
    XStock("SPYx",  "SPY"),
    XStock("QQQx",  "QQQ"),
    XStock("GOOGLx", "GOOGL"),
    XStock("APPLx", "AAPL"),
    XStock("NVDAx", "NVDA"),
    XStock("TSLAx", "TSLA"),
    XStock("MSTRx", "MSTR"),
    XStock("HOODx", "HOOD"),
)

# Kraken xStock Perp markets (10 total — 2 without Kamino listings at time of writing)
KRAKEN_PERP_EXTRA: tuple[XStock, ...] = (
    XStock("GLDx",  "GLD",  kamino_listed=False),
    XStock("CRCLx", "CRCL", kamino_listed=False),
)

ALL_XSTOCKS: tuple[XStock, ...] = CORE_XSTOCKS + KRAKEN_PERP_EXTRA

# Exogenous regressors for VECM and the V3 macro baseline
EXOGENOUS_EQUITY = ("ES=F", "NQ=F", "XLK", "XLF")

BY_SYMBOL: dict[str, XStock] = {x.symbol: x for x in ALL_XSTOCKS}
BY_UNDERLYING: dict[str, XStock] = {x.underlying: x for x in ALL_XSTOCKS}
