"""
Empirical scan: which Chainlink Data Streams schemas are actually flowing through
the Solana Verifier program right now? We have conflicting docs:
  - verifier.py: "0x000b v11 not yet active on Solana for xStocks"
  - v11.py: "v11 is used for 24/5 US equity streams (xStocks, since Jan 2026)"

Pull a single page of recent Verifier txs (~1000), decode the report from each,
count by schema. Also identify any feed_ids that don't match our XSTOCK_FEEDS map.
"""

from __future__ import annotations

import time
from collections import Counter
from datetime import UTC, datetime

from soothsayer.chainlink.feeds import XSTOCK_FEEDS, feed_id_to_xstock
from soothsayer.chainlink.v10 import decode as v10_decode
from soothsayer.chainlink.v11 import decode as v11_decode
from soothsayer.chainlink.verifier import VERIFIER_PROGRAM_ID, parse_verify_return_data
from soothsayer.sources.helius import (
    get_signatures_for_address,
    rpc_batch,
)


def main() -> None:
    print(f"now: {datetime.now(UTC).isoformat()}")
    print(f"scanning latest 1000 Verifier txs ...")

    sigs = get_signatures_for_address(VERIFIER_PROGRAM_ID, limit=1000)
    print(f"got {len(sigs)} signatures")
    in_window = [s for s in sigs if s.get("err") is None][:500]
    print(f"fetching {len(in_window)} txs in batches of 25 ...")

    schema_counter: Counter[str] = Counter()
    feed_counter: Counter[str] = Counter()
    v11_samples: list[dict] = []
    v10_non_xstock_samples: list[tuple[str, int]] = []

    BATCH = 25
    tx_opts = {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
    for chunk_start in range(0, len(in_window), BATCH):
        chunk = in_window[chunk_start : chunk_start + BATCH]
        calls = [("getTransaction", [s["signature"], tx_opts]) for s in chunk]
        try:
            txs = rpc_batch(calls)
        except Exception as e:
            print(f"  batch failed: {e}")
            continue
        for s, tx in zip(chunk, txs):
            if not tx:
                continue
            rd = parse_verify_return_data((tx.get("meta") or {}).get("returnData"))
            if rd is None:
                continue
            schema_hex = f"0x{rd.schema:04x}"
            schema_counter[schema_hex] += 1
            feed_id_hex = rd.raw_report[:32].hex() if len(rd.raw_report) >= 32 else "?"
            feed_counter[feed_id_hex] += 1

            if rd.schema == 0x000B and len(v11_samples) < 5:
                try:
                    r = v11_decode(rd.raw_report)
                    sym = feed_id_to_xstock(r.feed_id)
                    v11_samples.append({
                        "symbol": sym,
                        "feed_id": r.feed_id_hex,
                        "obs_ts": datetime.fromtimestamp(r.observations_timestamp, UTC).isoformat(),
                        "mid": float(r.mid),
                        "bid": float(r.bid),
                        "ask": float(r.ask),
                        "last_traded": float(r.last_traded_price),
                        "market_status": r.market_status,
                        "market_status_label": r.market_status_label,
                    })
                except Exception as e:
                    print(f"  v11 decode failed for {feed_id_hex}: {e}")
            elif rd.schema == 0x000A:
                sym = feed_id_to_xstock(rd.raw_report[:32])
                if sym is None and len(v10_non_xstock_samples) < 5:
                    try:
                        r = v10_decode(rd.raw_report)
                        v10_non_xstock_samples.append((feed_id_hex, r.market_status))
                    except Exception:
                        pass

        print(f"  batch {chunk_start // BATCH + 1}: total decoded so far = {sum(schema_counter.values())}")

    print()
    print("=" * 60)
    print("Schema distribution across last ~500 Verifier txs:")
    print("=" * 60)
    for sch, cnt in schema_counter.most_common():
        print(f"  {sch}: {cnt}")

    print()
    print("=" * 60)
    print("Feed-id top 20 (most active):")
    print("=" * 60)
    for fid, cnt in feed_counter.most_common(20):
        sym = feed_id_to_xstock(fid) or "(unknown)"
        print(f"  {fid[:8]}... → {sym:<10} cnt={cnt}")

    print()
    print(f"Distinct feed_ids: {len(feed_counter)}")
    known_xstock_feed_ids = {fid.lower() for fid in XSTOCK_FEEDS}
    unknown_feeds = [fid for fid in feed_counter if fid.lower() not in known_xstock_feed_ids]
    print(f"Unknown feed_ids: {len(unknown_feeds)}")

    if v11_samples:
        print()
        print("=" * 60)
        print(f"V11 samples ({len(v11_samples)}):")
        print("=" * 60)
        for s in v11_samples:
            print(f"  symbol={s['symbol']} feed={s['feed_id'][:14]}...")
            print(f"    obs_ts={s['obs_ts']}")
            print(f"    mid={s['mid']:.4f} bid={s['bid']:.4f} ask={s['ask']:.4f} last={s['last_traded']:.4f}")
            print(f"    market_status={s['market_status']} ({s['market_status_label']})")
    else:
        print()
        print("⚠ No v11 reports found in this scan — v11 may not be active on Solana for xStocks.")

    if v10_non_xstock_samples:
        print()
        print("V10 non-xStock samples:")
        for fid, mkt in v10_non_xstock_samples:
            print(f"  {fid[:16]}... market_status={mkt}")


if __name__ == "__main__":
    main()
