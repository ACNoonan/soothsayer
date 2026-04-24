"""
One-off diagnostic: fetch one live v10 SPYx report and dump every 32-byte word
so we can see whether bid/ask slots are genuinely zero on-chain or our decoder
is aligned to the wrong offsets.

Run: uv run python -u scripts/debug_v10_layout.py [SYMBOL]
"""

from __future__ import annotations

import sys
import time
from decimal import Decimal

from soothsayer.chainlink.feeds import feed_id_to_xstock
from soothsayer.chainlink.scraper import _seed_verifier_sig_near_ts
from soothsayer.chainlink.verifier import VERIFIER_PROGRAM_ID, parse_verify_return_data
from soothsayer.sources.helius import get_signatures_for_address, get_transaction

WORD = 32
PRICE_SCALE = 10**18


def _fmt_word(w: bytes) -> tuple[str, int, int]:
    hex_str = w.hex()
    u = int.from_bytes(w, "big", signed=False)
    s = int.from_bytes(w, "big", signed=True)
    return hex_str, u, s


def _find_spyx_report(symbol: str, lookback_hours: int = 2) -> bytes | None:
    now = int(time.time())
    start_ts = now - lookback_hours * 3600
    before = _seed_verifier_sig_near_ts(now + 120)
    if before is None:
        print("could not seed sig near now")
        return None
    cursor: str | None = before
    pages = 0
    while True:
        sigs = get_signatures_for_address(VERIFIER_PROGRAM_ID, before=cursor, limit=1000)
        if not sigs:
            return None
        pages += 1
        for s in sigs:
            bt = s.get("blockTime")
            if bt is None or bt > now or bt <= start_ts:
                continue
            if s.get("err") is not None:
                continue
            try:
                tx = get_transaction(s["signature"])
            except Exception:
                continue
            if not tx:
                continue
            rd = parse_verify_return_data(tx.get("meta", {}).get("returnData"))
            if rd is None or rd.schema != 0x000A:
                continue
            feed_sym = feed_id_to_xstock(rd.raw_report[:32])
            if feed_sym != symbol:
                continue
            print(
                f"  found {symbol} report on sig={s['signature'][:16]}… "
                f"blockTime={bt} (age {now - bt}s) after {pages} pages"
            )
            return rd.raw_report
        if len(sigs) < 1000:
            return None
        cursor = sigs[-1]["signature"]


def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPYx"
    print(f"hunting live v10 report for {symbol}…")
    raw = _find_spyx_report(symbol)
    if raw is None:
        print("no report found")
        return 1
    print(f"raw report: {len(raw)} bytes\n")
    n_words = len(raw) // WORD
    for i in range(n_words):
        w = raw[i * WORD : (i + 1) * WORD]
        hex_str, u, s = _fmt_word(w)
        scaled_s = Decimal(s) / Decimal(PRICE_SCALE)
        print(f"  w{i:>2}  {hex_str}")
        print(f"       u={u}")
        print(f"       i={s}   i/1e18={scaled_s:.6f}")
    if len(raw) % WORD:
        trail = raw[n_words * WORD :]
        print(f"  trailing {len(trail)} bytes: {trail.hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
