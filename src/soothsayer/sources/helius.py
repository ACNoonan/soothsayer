"""
Solana JSON-RPC client + Helius Enhanced Transactions API.

Two orthogonal surfaces:

  1. Standard Solana JSON-RPC (`rpc`, `get_signatures_for_address`, `get_transaction`,
     `rpc_batch`): routes to either Helius or RPC Fast per the `provider=` kwarg
     (or config.PRIMARY_RPC as default). Used by V1 — decoding Chainlink Verifier
     calls embedded in Kamino lending txs.

  2. Enhanced Transactions v0 (`enhanced_address_transactions`, ...):
     Parsed tx envelopes with `type` (SWAP, TRANSFER, ...) and `tokenTransfers`.
     Helius-proprietary — no RPC Fast equivalent. Used by V4 — DEX swap
     extraction from Meteora/Raydium/Orca pools.

Rate limits we target (one below each documented cap):
  Helius free    : RPC  9 req/s, DAS 1.8 req/s
                   (docs: 10 req/s RPC + 1M credits/mo; 2 req/s DAS + 100k/mo;
                    getProgramAccounts capped at 5 req/s)
  RPC Fast Start : RPC 14 req/s (docs: 15 req/s, 1.5M CU/mo)

The per-provider throttle is thread-safe so `rpc_batch` can fan out concurrent
serial calls without breaching the per-second cap. The monthly quotas are the
caller's responsibility — there's no introspection endpoint for remaining budget.

Why concurrent-serial instead of JSON-RPC array batching: both Helius free
(403 "Batch requests are only available for paid plans") and RPC Fast Start
(500 Internal Server Error on any batch payload) reject array batching. Firing
N individual POSTs through a bounded thread pool is the only path that works
on the free tier of either provider.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

import requests

from ..config import (
    HELIUS_API_KEY,
    PRIMARY_RPC,
    helius_rpc_url,
    rpcfast_rpc_url,
)

T = TypeVar("T")

ENHANCED_BASE = "https://api.helius.xyz/v0"


class _RateLimiter:
    """Lock-based token-bucket-ish throttle. Thread-safe.

    Each caller reserves an exclusive send slot `min_interval` after the previous
    reservation. Sleeping happens outside the lock so concurrent callers queue
    their slots without serialising on the sleep itself.
    """

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._next_slot = 0.0
        self._lock = threading.Lock()

    def reserve(self) -> None:
        with self._lock:
            now = time.monotonic()
            slot = max(self._next_slot, now)
            self._next_slot = slot + self.min_interval
        wait = slot - time.monotonic()
        if wait > 0:
            time.sleep(wait)


class _Provider:
    def __init__(self, url: str, min_interval: float, pool_size: int = 64) -> None:
        self.url = url
        self.limiter = _RateLimiter(min_interval)
        # Connection-pooled Session: reuses TCP+TLS across rpc() calls.
        # Without this each `requests.post()` does a fresh handshake, which
        # measured at ~300-500ms overhead on cold cache — dominating the
        # wall time for a 200-300ms getTransaction round-trip and capping
        # observed throughput far below the rate-limit ceiling.
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=pool_size,
            pool_maxsize=pool_size,
            max_retries=0,  # we own retries via _with_retry
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)


_PROVIDERS: dict[str, _Provider] = {}
_PROVIDERS_LOCK = threading.Lock()


def _get_provider(name: str) -> _Provider:
    with _PROVIDERS_LOCK:
        if name not in _PROVIDERS:
            if name == "helius":
                _PROVIDERS[name] = _Provider(helius_rpc_url(), 1.0 / 9.0)
            elif name == "rpcfast":
                _PROVIDERS[name] = _Provider(rpcfast_rpc_url(), 1.0 / 14.0)
            else:
                raise ValueError(
                    f"unknown RPC provider {name!r} — expected 'helius' or 'rpcfast'"
                )
        return _PROVIDERS[name]


# Enhanced API uses Helius's DAS quota, not the RPC quota — separate bucket.
_das_limiter = _RateLimiter(1.0 / 1.8)


def _with_retry(fn: Callable[[], T], *, attempts: int = 6, base_delay: float = 1.0) -> T:
    """Retry fn() on transient errors: timeouts, connection resets, 429s, and 5xx responses."""
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
        except requests.HTTPError as e:
            if e.response is not None and (
                e.response.status_code == 429
                or 500 <= e.response.status_code < 600
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


def rpc(
    method: str,
    params: list[Any] | None = None,
    *,
    provider: str | None = None,
) -> Any:
    """Single JSON-RPC call. Raises on `error`. Retries on transient network errors.

    `provider` routes to "helius" or "rpcfast"; default is config.PRIMARY_RPC.
    """
    prov = _get_provider(provider or PRIMARY_RPC)

    def _call() -> Any:
        prov.limiter.reserve()
        r = prov.session.post(
            prov.url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise RuntimeError(f"RPC error {method}: {body['error']}")
        return body.get("result")

    return _with_retry(_call)


def rpc_batch(
    calls: list[tuple[str, list[Any]]],
    *,
    provider: str | None = None,
    max_concurrent: int = 8,
) -> list[Any]:
    """Fan out N JSON-RPC calls concurrently, results positionally aligned with `calls`.

    Each call consumes one request of the provider's rate budget (this is NOT a
    JSON-RPC array batch — both free tiers reject those). The per-provider
    `_RateLimiter` enforces the per-second cap across all threads.

    `max_concurrent` bounds the thread pool. On Helius (9 req/s target) values
    above ~8 give diminishing returns because the limiter becomes the bottleneck;
    on RPC Fast (14 req/s) ~12 is the comparable saturation point.

    If any call fails, the first failure is re-raised after all in-flight
    futures complete — same all-or-nothing semantics as the old array-batch path.
    """
    if not calls:
        return []
    workers = min(max_concurrent, len(calls))
    results: list[Any] = [None] * len(calls)
    first_err: tuple[int, Exception] | None = None
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [
            ex.submit(rpc, method, params, provider=provider)
            for method, params in calls
        ]
        for i, fut in enumerate(futures):
            try:
                results[i] = fut.result()
            except Exception as e:
                if first_err is None:
                    first_err = (i, e)
    if first_err is not None:
        i, e = first_err
        method, _ = calls[i]
        raise RuntimeError(f"concurrent RPC error id={i} method={method}: {e}") from e
    return results


def get_signatures_for_address(
    address: str,
    *,
    before: str | None = None,
    until: str | None = None,
    limit: int = 1000,
    provider: str | None = None,
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
    return rpc("getSignaturesForAddress", [address, opts], provider=provider) or []


def paginate_signatures(
    address: str,
    *,
    until: str | None = None,
    min_block_time: int | None = None,
    page_size: int = 1000,
    provider: str | None = None,
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
            address,
            before=before,
            until=until,
            limit=page_size,
            provider=provider,
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
    provider: str | None = None,
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
        provider=provider,
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
    params: dict[str, Any] = {"api-key": HELIUS_API_KEY, "limit": limit}
    if before:
        params["before"] = before
    if until:
        params["until"] = until
    if source:
        params["source"] = source
    if tx_type:
        params["type"] = tx_type

    def _call() -> list[dict]:
        _das_limiter.reserve()
        r = requests.get(
            f"{ENHANCED_BASE}/addresses/{address}/transactions",
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    return _with_retry(_call)


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
