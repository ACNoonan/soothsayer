"""
Smoke test — does RPC Fast cover the Solana JSON-RPC methods our scraper uses?

Probes:
  1. getVersion / getSlot / getHealth — basic connectivity
  2. getAccountInfo on an xStock mint — account reads work
  3. getSignaturesForAddress on Chainlink Verifier — pagination works
  4. getTransaction (single + batched) — what scraper._rpc_iter_xstock_reports does
  5. getProgramAccounts — tier probe; expected to fail on Start tier

Also times each call side-by-side against the Helius endpoint in .env so we
can see whether the swap is a net improvement. Does NOT modify any project
code; pure standalone curl-equivalent to verify the endpoint before wiring.

Run: uv run python -u scripts/smoke_rpcfast.py
"""

from __future__ import annotations

import os
import statistics
import sys
import time
from typing import Any

import requests
from dotenv import load_dotenv

from soothsayer.chainlink.verifier import VERIFIER_PROGRAM_ID
from soothsayer.sources.jupiter import XSTOCK_MINTS

load_dotenv()

RPCFAST_URL = (
    f"{os.environ['RPCFAST_RPC_URL']}/?api_key={os.environ['RPCFAST_API_KEY']}"
)
HELIUS_KEY = os.environ.get("HELIUS_API_KEY", "")
HELIUS_URL = (
    f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}" if HELIUS_KEY else None
)


def rpc(url: str, method: str, params: list[Any] | None = None) -> tuple[Any, float]:
    t0 = time.monotonic()
    r = requests.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
        timeout=30,
    )
    dt = time.monotonic() - t0
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(f"{method}: {body['error']}")
    return body.get("result"), dt


def rpc_batch(
    url: str, calls: list[tuple[str, list[Any]]]
) -> tuple[list[Any], float]:
    batch = [
        {"jsonrpc": "2.0", "id": i, "method": m, "params": p}
        for i, (m, p) in enumerate(calls)
    ]
    t0 = time.monotonic()
    r = requests.post(url, json=batch, timeout=60)
    dt = time.monotonic() - t0
    r.raise_for_status()
    body = r.json()
    by_id = {item.get("id"): item for item in body}
    results = []
    for i, (m, _) in enumerate(calls):
        item = by_id[i]
        if "error" in item:
            raise RuntimeError(f"batch {m}: {item['error']}")
        results.append(item.get("result"))
    return results, dt


def bench(label: str, fn, *, n: int = 3) -> list[float] | None:
    """Run fn() n times, return list of dt's (or None on failure)."""
    times = []
    last_err = None
    for i in range(n):
        try:
            _, dt = fn()
            times.append(dt)
        except Exception as e:
            last_err = e
            break
    if last_err is not None:
        err_msg = str(last_err)
        if len(err_msg) > 140:
            err_msg = err_msg[:137] + "..."
        print(f"    {label:<20} FAIL: {type(last_err).__name__}: {err_msg}")
        return None
    p50 = statistics.median(times)
    p_max = max(times)
    print(
        f"    {label:<20} OK   median={p50 * 1000:6.0f} ms  max={p_max * 1000:6.0f} ms  (n={n})"
    )
    return times


def probe_endpoint(name: str, url: str) -> None:
    print(f"\n=== {name} ({url.split('?')[0]}) ===")
    spyx_mint = XSTOCK_MINTS["SPYx"]

    # 1. Basic health
    print("  basic:")
    bench("getVersion", lambda: rpc(url, "getVersion"))
    bench("getSlot", lambda: rpc(url, "getSlot"))
    bench("getHealth", lambda: rpc(url, "getHealth"))

    # 2. Account read — confirm SPYx mint is readable
    print("  account reads:")
    bench(
        "getAccountInfo",
        lambda: rpc(
            url,
            "getAccountInfo",
            [spyx_mint, {"encoding": "base64"}],
        ),
    )

    # 3. getSignaturesForAddress on Verifier — scraper's page fetch
    print("  signature pagination:")
    sigs_n100 = bench(
        "getSigsForAddr(100)",
        lambda: rpc(
            url,
            "getSignaturesForAddress",
            [VERIFIER_PROGRAM_ID, {"limit": 100}],
        ),
    )
    sigs_n1000 = bench(
        "getSigsForAddr(1000)",
        lambda: rpc(
            url,
            "getSignaturesForAddress",
            [VERIFIER_PROGRAM_ID, {"limit": 1000}],
        ),
        n=2,
    )

    # 4. getTransaction — single + batch-of-20 (scraper's hot path)
    print("  tx fetches:")
    probe_sigs, _ = rpc(
        url,
        "getSignaturesForAddress",
        [VERIFIER_PROGRAM_ID, {"limit": 20}],
    )
    if probe_sigs:
        first_sig = probe_sigs[0]["signature"]
        bench(
            "getTransaction",
            lambda: rpc(
                url,
                "getTransaction",
                [
                    first_sig,
                    {
                        "encoding": "jsonParsed",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            ),
        )
        batch_calls = [
            (
                "getTransaction",
                [
                    s["signature"],
                    {
                        "encoding": "jsonParsed",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            )
            for s in probe_sigs
        ]
        bench(
            "getTx batch(20)",
            lambda: rpc_batch(url, batch_calls),
            n=2,
        )
    else:
        print("    (no sigs returned — cannot test getTransaction)")

    # 5. Tier probe — expected to FAIL on Start
    print("  tier probe (expected to fail on Start):")
    bench(
        "getProgramAccounts",
        lambda: rpc(
            url,
            "getProgramAccounts",
            [
                VERIFIER_PROGRAM_ID,
                {"encoding": "base64", "dataSlice": {"offset": 0, "length": 0}},
            ],
        ),
        n=1,
    )
    bench(
        "getTokenAccountsBy…",
        lambda: rpc(
            url,
            "getTokenAccountsByOwner",
            [
                # pick any owner; we just want to see if the method is allowed
                "11111111111111111111111111111111",
                {"mint": spyx_mint},
                {"encoding": "base64"},
            ],
        ),
        n=1,
    )


def main() -> int:
    print(f"RPCFAST_URL target: {RPCFAST_URL.split('?')[0]}")
    print(f"HELIUS_URL target:  {(HELIUS_URL or 'not set').split('?')[0]}")

    probe_endpoint("RPC Fast", RPCFAST_URL)
    if HELIUS_URL:
        probe_endpoint("Helius (reference)", HELIUS_URL)
    else:
        print("\n(skipping Helius comparison — HELIUS_API_KEY not set)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
