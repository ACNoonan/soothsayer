"""Dump every v11 (schema 0x000b) feed_id seen in recent Verifier traffic
with its full hex ID, sample count, median ``last_traded_price``, median
``bid`` and ``ask``, and whether the bid carries the .01 synthetic marker.

Lightweight diagnostic complement to ``scripts/verify_v11_cadence.py`` and
``scripts/enumerate_v11_xstock_feeds.py``: those produce mappings and
verdicts; this just dumps the inventory so a human can spot alternate /
mirror feeds for the same underlier (e.g., the NVDA-class n=32 unmapped
feed at $207.98 vs the n=1 NVDAx-mapped feed at $208.10 we saw earlier).

Run:
    uv run python scripts/dump_v11_feed_inventory.py
    uv run python scripts/dump_v11_feed_inventory.py --sigs 3000
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Optional

from soothsayer.chainlink.feeds import feed_id_to_xstock
from soothsayer.chainlink.v11 import decode as v11_decode
from soothsayer.chainlink.verifier import VERIFIER_PROGRAM_ID, parse_verify_return_data
from soothsayer.sources.helius import get_signatures_for_address, rpc_batch


def fetch_signatures(target_count: int) -> list[dict]:
    all_sigs: list[dict] = []
    before: Optional[str] = None
    while len(all_sigs) < target_count:
        page = get_signatures_for_address(VERIFIER_PROGRAM_ID, limit=1000, before=before)
        if not page:
            break
        all_sigs.extend(s for s in page if s.get("err") is None)
        before = page[-1]["signature"]
        if len(page) < 1000:
            break
    return all_sigs[:target_count]


def is_synth(price: float) -> bool:
    return round(price * 100) % 100 == 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sigs", type=int, default=3000)
    args = ap.parse_args()

    print(f"v11 feed inventory dump  ({datetime.now(timezone.utc).isoformat()})")
    print(f"  scanning {args.sigs} Verifier signatures")

    sigs = fetch_signatures(args.sigs)
    print(f"  {len(sigs)} non-failed sigs")

    BATCH = 25
    tx_opts = {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
    by_feed: dict[str, list[dict]] = defaultdict(list)
    for start in range(0, len(sigs), BATCH):
        chunk = sigs[start:start + BATCH]
        calls = [("getTransaction", [s["signature"], tx_opts]) for s in chunk]
        try:
            txs = rpc_batch(calls)
        except Exception as e:  # noqa: BLE001
            print(f"  batch failed @ {start}: {e}")
            continue
        for tx in txs:
            if not tx:
                continue
            rd = parse_verify_return_data((tx.get("meta") or {}).get("returnData"))
            if rd is None or rd.schema != 0x000B:
                continue
            try:
                r = v11_decode(rd.raw_report)
            except Exception:
                continue
            fid = r.feed_id_hex.removeprefix("0x").lower()
            by_feed[fid].append({
                "bid": float(r.bid),
                "ask": float(r.ask),
                "last": float(r.last_traded_price),
                "obs_ts": int(r.observations_timestamp),
            })
        if (start // BATCH) % 8 == 0:
            print(f"  progress: {start + len(chunk)}/{len(sigs)} sigs; "
                  f"{len(by_feed)} feeds; "
                  f"{sum(len(v) for v in by_feed.values())} reports")

    print()
    print(f"Found {len(by_feed)} distinct v11 feed_ids")
    print()
    print(f"{'#':>3}  {'n':>4}  {'symbol':<14} {'med_last':>10}  "
          f"{'med_bid':>10}  {'bid_01_%':>8}  feed_id")
    print("-" * 130)
    rows = []
    for fid, samples in by_feed.items():
        sym = feed_id_to_xstock(fid) or "(unmapped)"
        n = len(samples)
        last_med = median(s["last"] for s in samples)
        bid_med = median(s["bid"] for s in samples)
        bid_synth_pct = 100.0 * sum(1 for s in samples if is_synth(s["bid"])) / n
        rows.append((sym, n, last_med, bid_med, bid_synth_pct, fid))
    # Sort by n descending (most popular first), then by median price for stability.
    rows.sort(key=lambda r: (-r[1], r[2]))
    for i, (sym, n, last_med, bid_med, bid_synth_pct, fid) in enumerate(rows, 1):
        print(f"{i:>3}  {n:>4}  {sym:<14} ${last_med:>8.2f}  ${bid_med:>8.2f}  "
              f"{bid_synth_pct:>6.0f}%   {fid}")

    # Also surface obvious price-band collisions: feeds within 1% of each other.
    print()
    print("Possible alternate / mirror feeds (within 1% of another feed's median last_traded):")
    seen: set[tuple[str, str]] = set()
    for i, (sym_a, _, last_a, _, _, fid_a) in enumerate(rows):
        for (sym_b, _, last_b, _, _, fid_b) in rows[i + 1:]:
            if last_a <= 0:
                continue
            pct = abs((last_b - last_a) / last_a) * 100
            if pct < 1.0:
                key = tuple(sorted([fid_a, fid_b]))
                if key in seen:
                    continue
                seen.add(key)
                print(f"  ${last_a:.2f}  {sym_a:<14} {fid_a}")
                print(f"  ${last_b:.2f}  {sym_b:<14} {fid_b}  (Δ {pct:.2f}%)")


if __name__ == "__main__":
    main()
