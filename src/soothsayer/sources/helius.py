"""
Helius client — Solana JSON-RPC + Enhanced Transactions (parsed) API.

Two orthogonal surfaces:

  1. Standard Solana JSON-RPC (`rpc`, `get_signatures_for_address`, `get_transaction`):
       Raw chain access. Used for V1 — decoding Chainlink Verifier calls embedded
       in Kamino lending txs.
  2. Enhanced Transactions v0 (`enhanced_address_transactions`, ...):
       Parsed tx envelopes with `type` (SWAP, TRANSFER, ...) and `tokenTransfers`.
       Used for V4 — DEX swap extraction from Meteora/Raydium/Orca pools.

Rate limits — Helius free tier (April 2026):
  RPC    10 req/s,  1,000,000 credits / month
  DAS     2 req/s,    100,000 calls   / month
  getProgramAccounts 5 req/s

The module throttles client-side to stay safely under both per-second limits. The
monthly quotas are the caller's responsibility — there is no introspection
endpoint for remaining credits.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import requests

from ..config import HELIUS_API_KEY, helius_rpc_url

RPC_URL = helius_rpc_url()
ENHANCED_BASE = "https://api.helius.xyz/v0"

_RPC_MIN_INTERVAL = 1.0 / 9.0    # target 9 req/s, under the 10 req/s cap
_DAS_MIN_INTERVAL = 1.0 / 1.8    # target 1.8 req/s, under the 2 req/s cap
_last_rpc_t = 0.0
_last_das_t = 0.0


def _throttle_rpc() -> None:
    global _last_rpc_t
    wait = (_last_rpc_t + _RPC_MIN_INTERVAL) - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_rpc_t = time.monotonic()


def _throttle_das() -> None:
    global _last_das_t
    wait = (_last_das_t + _DAS_MIN_INTERVAL) - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_das_t = time.monotonic()


def rpc(method: str, params: list[Any] | None = None) -> Any:
    """Single JSON-RPC call. Raises on any `error` field."""
    _throttle_rpc()
    r = requests.post(
        RPC_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(f"RPC error {method}: {body['error']}")
    return body.get("result")


def get_signatures_for_address(
    address: str,
    *,
    before: str | None = None,
    until: str | None = None,
    limit: int = 1000,
) -> list[dict]:
    """One page of confirmed signatures for an address, newest-first.

    `before` / `until` are signature strings marking page boundaries. `limit` max
    per Helius docs is 1000.
    """
    opts: dict[str, Any] = {"limit": limit}
    if before:
        opts["before"] = before
    if until:
        opts["until"] = until
    return rpc("getSignaturesForAddress", [address, opts]) or []


def paginate_signatures(
    address: str,
    *,
    until: str | None = None,
    min_block_time: int | None = None,
    page_size: int = 1000,
) -> Iterator[dict]:
    """Walk back through `getSignaturesForAddress`, yielding sig records newest→oldest.

    Stops when:
      - a batch comes back short (no more pages), OR
      - `until` signature reached (respected by the API), OR
      - the current sig's `blockTime` is older than `min_block_time` (Unix seconds).
    """
    before: str | None = None
    while True:
        batch = get_signatures_for_address(
            address, before=before, until=until, limit=page_size
        )
        if not batch:
            return
        for sig in batch:
            if min_block_time is not None and sig.get("blockTime") is not None:
                if sig["blockTime"] < min_block_time:
                    return
            yield sig
        if len(batch) < page_size:
            return
        before = batch[-1]["signature"]


def get_transaction(
    signature: str,
    *,
    encoding: str = "jsonParsed",
    max_supported_tx_version: int = 0,
) -> dict | None:
    return rpc(
        "getTransaction",
        [
            signature,
            {
                "encoding": encoding,
                "maxSupportedTransactionVersion": max_supported_tx_version,
            },
        ],
    )


def enhanced_address_transactions(
    address: str,
    *,
    before: str | None = None,
    until: str | None = None,
    source: str | None = None,
    tx_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """GET /v0/addresses/{address}/transactions — parsed tx envelopes.

    `source`  e.g. 'RAYDIUM', 'METEORA', 'ORCA'
    `tx_type` e.g. 'SWAP', 'TRANSFER'
    Helius caps `limit` at 100 per call.
    """
    _throttle_das()
    params: dict[str, Any] = {"api-key": HELIUS_API_KEY, "limit": limit}
    if before:
        params["before"] = before
    if until:
        params["until"] = until
    if source:
        params["source"] = source
    if tx_type:
        params["type"] = tx_type
    r = requests.get(
        f"{ENHANCED_BASE}/addresses/{address}/transactions",
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def paginate_enhanced_transactions(
    address: str,
    *,
    until_signature: str | None = None,
    source: str | None = None,
    tx_type: str | None = None,
    min_block_time: int | None = None,
) -> Iterator[dict]:
    """Walk Enhanced Transactions newest→oldest. Stops on short batch or block-time floor."""
    before: str | None = None
    while True:
        batch = enhanced_address_transactions(
            address,
            before=before,
            until=until_signature,
            source=source,
            tx_type=tx_type,
            limit=100,
        )
        if not batch:
            return
        for tx in batch:
            if min_block_time is not None and tx.get("timestamp") is not None:
                if tx["timestamp"] < min_block_time:
                    return
            yield tx
        if len(batch) < 100:
            return
        before = batch[-1]["signature"]
