"""
Jupiter quote API — DEX mid for xStock / USDC pairs.

Used by V5 (Chainlink xStock quality monitor): we poll Jupiter alongside the
Chainlink feed to measure basis between the oracle's published mid and the
best-routed DEX mid. Jupiter aggregates Raydium, Orca, Meteora, Phoenix, etc.,
so its quote is the closest thing to "the market" without picking a single pool.

Endpoint: https://lite-api.jup.ag/swap/v1/quote (free, no key). The older
`quote-api.jup.ag/v6/quote` host was sunset; Jupiter consolidated the free
tier under lite-api.jup.ag in 2026. Param + response shapes are compatible
across the transition (inputMint, outputMint, amount, slippageBps in; outAmount,
routePlan, priceImpactPct out).

We throttle client-side at ~2 req/s to stay polite and well under the
public-tier ceiling.

Mint inventory (verified on-chain 2026-04-22 via Helius getAccountInfo;
Token-2022 program, 8 decimals, metadata symbols match exactly).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

import requests

T = TypeVar("T")

QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote"

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_DECIMALS = 6

XSTOCK_DECIMALS = 8

# symbol -> mint (Token-2022, 8 decimals). Verified on-chain 2026-04-22.
XSTOCK_MINTS: dict[str, str] = {
    "SPYx":   "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W",
    "QQQx":   "Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ",
    "TSLAx":  "XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB",
    "GOOGLx": "XsCPL9dNWBMvFtTmwcCA5v3xWPSMEBCszbQdiLLq6aN",
    "AAPLx":  "XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp",
    "NVDAx":  "Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh",
    "MSTRx":  "XsP7xzNPvEHS1m6qfanPUGjNmdnmsLKEoNAnHjdxxyZ",
    "HOODx":  "XsvNBAYkrDRNhA7wPHQfX3ZUXZyZLdnCQDfHZ56bzpg",
}

TIMEOUT = 15
_MIN_INTERVAL = 0.5    # ~2 req/s
_last_t = 0.0


def _throttle() -> None:
    global _last_t
    wait = (_last_t + _MIN_INTERVAL) - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_t = time.monotonic()


def _with_retry(fn: Callable[[], T], *, attempts: int = 5, base_delay: float = 1.0) -> T:
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
        except requests.HTTPError as e:
            if e.response is not None and (
                e.response.status_code == 429 or 500 <= e.response.status_code < 600
            ):
                last_exc = e
            else:
                raise
        if i == attempts - 1:
            assert last_exc is not None
            raise last_exc
        time.sleep(base_delay * (2**i))
    assert last_exc is not None
    raise last_exc


def quote(
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    *,
    slippage_bps: int = 50,
) -> dict:
    """Thin wrapper over Jupiter v6 GET /quote.

    `amount_raw` is in base units of `input_mint` (i.e. already scaled by decimals).
    Returns the parsed JSON response. `outAmount` is likewise in base units of `output_mint`.
    """

    def _call() -> dict:
        _throttle()
        r = requests.get(
            QUOTE_URL,
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount_raw),
                "slippageBps": str(slippage_bps),
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    return _with_retry(_call)


def xstock_mid_usdc(symbol: str, shares: float = 1.0) -> float:
    """Return USDC-per-share implied by Jupiter's best route for `shares` of `symbol`.

    Quotes xStock -> USDC (a sell-side estimate). For small `shares` (e.g. 1)
    price impact is negligible for liquid xStocks and this approximates mid.
    For a true two-sided mid, call this and the reverse direction and average.
    """
    mint = XSTOCK_MINTS.get(symbol)
    if mint is None:
        raise KeyError(f"unknown xStock symbol: {symbol!r}")
    amount_raw = int(round(shares * (10**XSTOCK_DECIMALS)))
    resp = quote(mint, USDC_MINT, amount_raw)
    out_raw = int(resp["outAmount"])
    return out_raw / (10**USDC_DECIMALS) / shares


def xstock_two_sided_mid_usdc(symbol: str, shares: float = 1.0) -> tuple[float, float, float]:
    """Return (bid, ask, mid) USDC-per-share from two Jupiter quotes.

    bid = proceeds from selling `shares` xStock.
    ask = cost of buying `shares` xStock (reverse route, USDC -> xStock).
    mid = geometric mean — appropriate for multiplicative price quotes.
    """
    mint = XSTOCK_MINTS.get(symbol)
    if mint is None:
        raise KeyError(f"unknown xStock symbol: {symbol!r}")

    sell_raw = int(round(shares * (10**XSTOCK_DECIMALS)))
    sell = quote(mint, USDC_MINT, sell_raw)
    bid = int(sell["outAmount"]) / (10**USDC_DECIMALS) / shares

    # Buy: send USDC-equivalent of `shares * bid` to get ~shares back
    buy_usdc_raw = int(round(bid * shares * (10**USDC_DECIMALS)))
    buy = quote(USDC_MINT, mint, buy_usdc_raw)
    shares_out = int(buy["outAmount"]) / (10**XSTOCK_DECIMALS)
    ask = (bid * shares) / shares_out if shares_out > 0 else float("nan")

    mid = (bid * ask) ** 0.5
    return bid, ask, mid
