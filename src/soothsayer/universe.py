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


# Kamino-onboarded xStocks (as of April 2026 per research — DS 05 in vault).
# Token-2022 program, 8 decimals. Mints verified on-chain 2026-04-22 via
# Helius getAccountInfo; metadata symbols match exactly.
CORE_XSTOCKS: tuple[XStock, ...] = (
    XStock("SPYx",   "SPY",   mint="XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W"),
    XStock("QQQx",   "QQQ",   mint="Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ"),
    XStock("GOOGLx", "GOOGL", mint="XsCPL9dNWBMvFtTmwcCA5v3xWPSMEBCszbQdiLLq6aN"),
    XStock("AAPLx",  "AAPL",  mint="XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp"),
    XStock("NVDAx",  "NVDA",  mint="Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh"),
    XStock("TSLAx",  "TSLA",  mint="XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB"),
    XStock("MSTRx",  "MSTR",  mint="XsP7xzNPvEHS1m6qfanPUGjNmdnmsLKEoNAnHjdxxyZ"),
    XStock("HOODx",  "HOOD",  mint="XsvNBAYkrDRNhA7wPHQfX3ZUXZyZLdnCQDfHZ56bzpg"),
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

# symbol -> mint, for callers that just want the registry as a flat dict.
# Replaces the old `from soothsayer.sources.jupiter import XSTOCK_MINTS` import
# (sources/ was deleted in the April 2026 scryer cutover).
XSTOCK_MINTS: dict[str, str] = {
    x.symbol: x.mint for x in ALL_XSTOCKS if x.mint is not None
}

# USDC on Solana (mainnet). Lives here rather than in a deleted `sources/`
# module so analysis scripts that quote against USDC still have a single
# source of truth for the mint.
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_DECIMALS = 6
XSTOCK_DECIMALS = 8
