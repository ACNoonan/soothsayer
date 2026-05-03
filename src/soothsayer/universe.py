"""
The tradeable universe for Phase 0 validation.

The 8 xStocks Kamino has onboarded (SPYx, QQQx, GOOGLx, APPLx, NVDAx, TSLAx, MSTRx, HOODx)
are the core universe for V1/V2/V4. V3 adds GLDx and CRCLx from Kraken's perp listings where
present, but drops any ticker without a Kamino listing for the gap regression.

Mint addresses, pool addresses, and Chainlink feed IDs are filled in as each validation
module is implemented — left as None here so the file stays a single source of truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .config import DATA_PROCESSED


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


# --- Lending-profile symbol_class mapping (M6b2) ----------------------------
# Single source of truth = the artefact JSON sidecar produced by
# `scripts/build_m6b2_lending_artefact.py`. Keying is on the *underlying*
# ticker (SPY, QQQ, ...) — same key set the conformal cells were trained on.
# `symbol_class_for(...)` accepts both forms so callers holding xStock symbols
# (SPYx) and callers holding underlyings (SPY) hit the same lookup.

LENDING_ARTEFACT_JSON_PATH = DATA_PROCESSED / "m6b2_lending_artefact_v1.json"


def _load_symbol_class_map() -> dict[str, str]:
    if not LENDING_ARTEFACT_JSON_PATH.exists():
        return {}
    sidecar = json.loads(LENDING_ARTEFACT_JSON_PATH.read_text())
    return dict(sidecar.get("symbol_class_mapping", {}))


SYMBOL_CLASS_MAP: dict[str, str] = _load_symbol_class_map()


def symbol_class_for(symbol: str) -> str | None:
    """Resolve symbol → symbol_class. Accepts either an underlying ticker
    ('SPY') or its xStock form ('SPYx'). Returns None for unknown symbols."""
    if symbol in SYMBOL_CLASS_MAP:
        return SYMBOL_CLASS_MAP[symbol]
    xs = BY_SYMBOL.get(symbol)
    if xs is not None and xs.underlying in SYMBOL_CLASS_MAP:
        return SYMBOL_CLASS_MAP[xs.underlying]
    if symbol.endswith("x"):
        underlying = symbol[:-1]
        if underlying in SYMBOL_CLASS_MAP:
            return SYMBOL_CLASS_MAP[underlying]
    return None
