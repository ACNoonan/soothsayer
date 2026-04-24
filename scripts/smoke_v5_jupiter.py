"""
V5 smoke test — live Chainlink mid vs Jupiter DEX mid for one xStock.

Purpose: confirm the Jupiter source is wired correctly end-to-end and the CL↔DEX
basis is in a believable range (non-zero but not absurd). If this returns |basis|
> ~500 bps or 0 exactly, investigate before committing to the V5 tape daemon.

Run: uv run python -u scripts/smoke_v5_jupiter.py [SYMBOL]
Default SYMBOL is SPYx. Any of the 8 xStocks in jupiter.XSTOCK_MINTS works.
"""

from __future__ import annotations

import math
import sys
import time

from soothsayer.chainlink.scraper import fetch_latest_per_xstock
from soothsayer.sources import jupiter


def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPYx"
    if symbol not in jupiter.XSTOCK_MINTS:
        print(f"unknown symbol {symbol!r}; known: {sorted(jupiter.XSTOCK_MINTS)}")
        return 2

    print(f"symbol: {symbol}")

    # Chainlink side
    t0 = time.monotonic()
    now = int(time.time())
    cl = fetch_latest_per_xstock(
        end_ts=now, lookback_hours=2, target_symbols={symbol}, verbose=True
    )
    cl_dt = time.monotonic() - t0
    if symbol not in cl:
        print(f"  CL: no observation in last 2h (dt={cl_dt:.1f}s)")
        return 1
    cl_obs = cl[symbol]
    cl_mark = cl_obs["tokenized_price"]
    cl_price = cl_obs["price"]
    cl_status = cl_obs["market_status"]
    cl_age_s = now - cl_obs["obs_ts"]
    status_label = {0: "unknown", 1: "closed", 2: "open"}.get(cl_status, f"?({cl_status})")
    print(
        f"  CL: tokenized_price={cl_mark:.4f} venue_price={cl_price:.4f} "
        f"market_status={status_label} age={cl_age_s}s (dt={cl_dt:.1f}s)"
    )

    # Jupiter side — two-sided for a proper mid
    t1 = time.monotonic()
    try:
        jup_bid, jup_ask, jup_mid = jupiter.xstock_two_sided_mid_usdc(symbol, shares=1.0)
    except Exception as e:
        print(f"  Jupiter ERR: {type(e).__name__}: {e}")
        return 1
    jup_dt = time.monotonic() - t1
    print(f"  JUP: mid={jup_mid:.4f} bid={jup_bid:.4f} ask={jup_ask:.4f} (dt={jup_dt:.1f}s)")

    # Basis against the 24/7 CL mark (tokenized_price), which is the field that
    # tracks the live market continuously. venue_price (w7) is stale when US cash
    # tape is closed and is not the right reference for Jupiter comparison.
    basis_bp = (math.log(jup_mid) - math.log(cl_mark)) * 1e4
    spread_bp = (math.log(jup_ask) - math.log(jup_bid)) * 1e4
    venue_gap_bp = (math.log(cl_price) - math.log(cl_mark)) * 1e4 if cl_price > 0 else float("nan")
    print(f"\n  basis (JUP_mid / CL_tokenized):  {basis_bp:+.2f} bp")
    print(f"  JUP bid-ask spread:              {spread_bp:.2f} bp")
    print(f"  CL venue_price vs tokenized_gap: {venue_gap_bp:+.2f} bp  (informational)")

    # Sanity flags
    flags = []
    if abs(basis_bp) > 500:
        flags.append("|basis| > 500bp — check decimals / mint / stale CL?")
    if basis_bp == 0:
        flags.append("basis exactly 0 — CL may be derived from the same pool")
    if spread_bp > 200:
        flags.append("JUP spread > 200bp — thin DEX liquidity, mid is fragile")
    if cl_age_s > 120:
        flags.append(f"CL obs is {cl_age_s}s old — not really 'live'")
    if flags:
        print("\n  flags:")
        for f in flags:
            print(f"   - {f}")
    else:
        print("\n  flags: none — looks sane")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
