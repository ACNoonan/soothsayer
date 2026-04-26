"""Enumerate Chainlink v11 (schema 0x000b) xStock feed IDs by price-band correlation.

Closes the docs/v5-tape.md follow-up "Map v11 feed_ids → xStock symbols"
and unblocks the Paper-1-publication-risk-gate xStock-specific verdict
that ``scripts/verify_v11_cadence.py`` produced as a broader-universe
finding only.

## Why correlation-based matching works

During weekend windows (`market_status = 5`), v11 reports carry their
underlier's frozen Friday close in ``last_traded_price``. If we group
v11 reports by feed_id and take the median ``last_traded_price`` per
feed, that median is the underlier's Friday close (modulo decoding
noise). Matching each xStock's known Friday-close price (from yfinance)
to the feed_id whose median is closest produces the mapping we need.

The 8 xStock underliers occupy well-separated price bands as of
2026-04-26 (HOOD ~$85, MSTR ~$170, NVDA ~$208, AAPL ~$271, GOOGL ~$343,
TSLA ~$376, QQQ ~$663, SPY ~$713) so price-band collisions are bounded.
Match tolerance is set to ±2% to leave room for after-hours moves
between the v11 frozen value and yfinance's daily close.

## Output

Prints the proposed mapping with per-feed match-quality info, and emits
the feeds.py patch text to stdout. Manual review + paste into
``src/soothsayer/chainlink/feeds.py`` adds an ``XSTOCK_V11_FEEDS`` dict
analogous to the existing ``XSTOCK_FEEDS`` (v10).

Run:
    uv run python scripts/enumerate_v11_xstock_feeds.py
    uv run python scripts/enumerate_v11_xstock_feeds.py --sigs 15000 --tolerance-pct 1.5
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Optional

from soothsayer.chainlink.v11 import decode as v11_decode
from soothsayer.chainlink.verifier import VERIFIER_PROGRAM_ID, parse_verify_return_data
from soothsayer.sources.helius import get_signatures_for_address, rpc_batch


# Underliers we want to find v11 feed IDs for. Order chosen for stable output.
TARGET_UNDERLIERS = ["SPY", "QQQ", "AAPL", "GOOGL", "NVDA", "TSLA", "MSTR", "HOOD"]


def fetch_signatures(target_count: int) -> list[dict]:
    """Paginate Verifier signatures back until ``target_count`` non-failed sigs."""
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


def yfinance_friday_close(symbols: list[str], target_friday: date) -> dict[str, float]:
    """yfinance close for ``target_friday``, fallback to most recent prior session."""
    import yfinance as yf
    df = yf.download(
        " ".join(symbols),
        start=(target_friday - timedelta(days=10)).isoformat(),
        end=(target_friday + timedelta(days=1)).isoformat(),
        progress=False, auto_adjust=False, group_by="ticker",
    )
    out: dict[str, float] = {}
    for sym in symbols:
        try:
            sub = df[sym] if sym in df.columns.get_level_values(0) else df
            sub.index = [d.date() for d in sub.index]
            # Walk back from target_friday until we find a close.
            d = target_friday
            for _ in range(7):
                if d in sub.index and not sub.loc[d, "Close"] != sub.loc[d, "Close"]:  # NaN check
                    out[sym] = float(sub.loc[d, "Close"])
                    break
                d -= timedelta(days=1)
            else:
                out[sym] = float("nan")
        except Exception as e:  # noqa: BLE001
            print(f"  yfinance fail for {sym}: {e}")
            out[sym] = float("nan")
    return out


def latest_completed_friday(today: Optional[date] = None) -> date:
    today = today or date.today()
    days_since_friday = (today.weekday() - 4) % 7
    candidate_friday = today - timedelta(days=days_since_friday)
    candidate_monday = candidate_friday + timedelta(days=3)
    if candidate_monday > today:
        candidate_friday -= timedelta(days=7)
    return candidate_friday


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sigs", type=int, default=10000,
                    help="target Verifier signatures to scan (default: 10000)")
    ap.add_argument("--tolerance-pct", type=float, default=2.0,
                    help="match tolerance as % of yfinance close (default: 2.0)")
    args = ap.parse_args()

    target_friday = latest_completed_friday()
    print(f"Enumerating v11 xStock feed IDs by price-band correlation")
    print(f"  Friday close target: {target_friday}")
    print(f"  scan depth: {args.sigs} Verifier signatures")
    print(f"  match tolerance: ±{args.tolerance_pct}%")

    print()
    print("Step 1 — fetch yfinance Friday close per underlier")
    yf_close = yfinance_friday_close(TARGET_UNDERLIERS, target_friday)
    for sym in TARGET_UNDERLIERS:
        v = yf_close.get(sym, float("nan"))
        print(f"  {sym:6s} ${v:>8.2f}")

    print()
    print("Step 2 — paginate Verifier signatures + decode v11 reports")
    sigs = fetch_signatures(args.sigs)
    print(f"  collected {len(sigs)} non-failed signatures")

    BATCH = 25
    tx_opts = {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
    by_feed: dict[str, list[float]] = defaultdict(list)
    feed_obs_count: dict[str, int] = defaultdict(int)

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
            ltp = float(r.last_traded_price)
            if ltp > 0:
                by_feed[fid].append(ltp)
                feed_obs_count[fid] += 1
        if (start // BATCH) % 8 == 0:
            print(f"  progress: {start + len(chunk)}/{len(sigs)} sigs; "
                  f"{len(by_feed)} distinct v11 feeds; "
                  f"{sum(feed_obs_count.values())} v11 reports")

    print(f"\n  done: {len(by_feed)} distinct v11 feed_ids; "
          f"{sum(feed_obs_count.values())} v11 reports total")

    print()
    print("Step 3 — match each xStock to its closest-by-median v11 feed_id")

    feed_medians: dict[str, float] = {fid: median(prices) for fid, prices in by_feed.items()}

    mapping: dict[str, dict] = {}
    used_feeds: set[str] = set()
    for sym in TARGET_UNDERLIERS:
        target_price = yf_close.get(sym, float("nan"))
        if target_price != target_price:  # NaN
            mapping[sym] = {"feed_id": None, "match_pct": None, "n": 0,
                            "reason": "yfinance close unavailable"}
            continue
        # Find closest unused feed.
        candidates = [
            (fid, m, abs((m - target_price) / target_price) * 100)
            for fid, m in feed_medians.items() if fid not in used_feeds
        ]
        if not candidates:
            mapping[sym] = {"feed_id": None, "match_pct": None, "n": 0,
                            "reason": "no feeds available"}
            continue
        candidates.sort(key=lambda c: c[2])
        best_fid, best_med, best_pct = candidates[0]
        if best_pct > args.tolerance_pct:
            mapping[sym] = {"feed_id": None, "match_pct": best_pct, "n": feed_obs_count[best_fid],
                            "reason": f"closest match {best_pct:.2f}% > tolerance {args.tolerance_pct}%",
                            "best_candidate_fid": best_fid, "best_candidate_med": best_med}
            continue
        mapping[sym] = {"feed_id": best_fid, "median_price": best_med, "match_pct": best_pct,
                        "n": feed_obs_count[best_fid]}
        used_feeds.add(best_fid)

    print()
    print(f"{'symbol':6s} {'yfinance Fri':>14s} {'v11 median':>14s} {'match %':>8s} "
          f"{'n obs':>6s} feed_id (or reason)")
    print("-" * 110)
    for sym in TARGET_UNDERLIERS:
        m = mapping[sym]
        if m.get("feed_id"):
            print(f"{sym:6s} ${yf_close.get(sym, 0):>12.2f} ${m['median_price']:>12.2f} "
                  f"{m['match_pct']:>7.2f}% {m['n']:>6d} {m['feed_id']}")
        else:
            yf_v = f"${yf_close.get(sym, float('nan')):>12.2f}" if yf_close.get(sym) == yf_close.get(sym) else "n/a"
            print(f"{sym:6s} {yf_v:>14s} {'—':>14s} {'—':>8s} {m['n']:>6d} "
                  f"NO MATCH — {m['reason']}")

    print()
    print("Step 4 — proposed feeds.py patch")
    print("(paste into src/soothsayer/chainlink/feeds.py alongside XSTOCK_FEEDS)")
    print()
    print("```python")
    print("# feed_id (hex, no 0x prefix, lower case) -> xStock symbol — Schema v11 (0x000b)")
    print("# Identified empirically by enumerate_v11_xstock_feeds.py via price-band")
    print("# correlation (median(last_traded_price) per feed_id matched against yfinance")
    print(f"# Friday close for {target_friday}; tolerance ±{args.tolerance_pct}%).")
    print("XSTOCK_V11_FEEDS: dict[str, str] = {")
    for sym in TARGET_UNDERLIERS:
        m = mapping[sym]
        if m.get("feed_id"):
            xstock_sym = f"{sym}x"
            print(f'    "{m["feed_id"]}": "{xstock_sym}",')
    print("}")
    print("```")

    # Surface unmatched feeds (top by sample count) for diagnostic.
    unmatched_feeds = [
        (fid, feed_obs_count[fid], feed_medians[fid])
        for fid in feed_obs_count
        if fid not in {m["feed_id"] for m in mapping.values() if m.get("feed_id")}
    ]
    unmatched_feeds.sort(key=lambda x: -x[1])
    if unmatched_feeds:
        print()
        print(f"Step 5 — top 10 unmatched v11 feed_ids (probably non-xStock RWAs sharing v11)")
        print(f"{'feed_id':16s} {'n obs':>6s} {'median price':>14s}")
        for fid, n, m in unmatched_feeds[:10]:
            print(f"{fid[:16]}…  {n:>6d}  ${m:>12.2f}")


if __name__ == "__main__":
    main()
