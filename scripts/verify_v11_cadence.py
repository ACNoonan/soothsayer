"""Verify Chainlink Data Streams v11 24/5 cadence on Solana.

Closes the **must-fix-before-Paper-1-arXiv** publication-risk gate
(`docs/ROADMAP.md` Publication-risk gates §1.2): does v11 carry *real*
``bid`` / ``ask`` / ``mid`` values during pre-market / regular /
post-market / overnight windows, or are they placeholder-derived
synthetic bookends like during weekends?

Background (verified 2026-04-25 in `docs/v5-tape.md`):
  - v11 weekend (`market_status = 5`) bid/ask are synthetic bookends
    (e.g. SPY-class: 21.01 / 715.01). Not real market quotes.
  - v11 weekend `last_traded_price` is frozen at Friday close.
  - v10 weekend `tokenizedPrice` is the only continuous CEX-aggregated
    mark across either schema.

Open question this script answers: do the v11 fields *during 24/5
sessions* (pre-market / regular / post-market / overnight) carry real
quotes, or remain placeholder-derived?

Method:
  1. Paginate deep into Verifier program signatures (default 5000 sigs,
     ~30-60 minutes of history, configurable via --sigs).
  2. Decode every v11 (schema 0x000b) report.
  3. Group by ``market_status`` value.
  4. For each (status, sample): compute bid-ask spread vs last_traded_price
     and classify as REAL / PLACEHOLDER / DEGENERATE. Real markets have
     bid/ask within a few hundred bps of last; placeholders are the
     known synthetic bookends with thousand-bps+ spreads.
  5. Emit a per-status verdict (pass/fail/insufficient) and write a
     report to ``reports/v11_cadence_verification.md``.

The script is idempotent across re-runs; weekend-time invocations will
mostly capture status=5 samples and produce a "weekend confirmed,
24/5 sessions pending" report. Monday-morning re-runs (when pre-market
cadence is active 04:00-09:30 ET) will capture status=1 traffic and
fill in the gates the weekend run cannot.

Run:
    uv run python scripts/verify_v11_cadence.py
    uv run python scripts/verify_v11_cadence.py --sigs 10000
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Optional

from soothsayer.chainlink.feeds import feed_id_to_xstock_label as feed_id_to_xstock
from soothsayer.chainlink.v11 import decode as v11_decode
from soothsayer.chainlink.verifier import VERIFIER_PROGRAM_ID, parse_verify_return_data
from soothsayer.config import REPORTS
from soothsayer.sources.helius import get_signatures_for_address, rpc_batch


# market_status code map per docs/v5-tape.md and src/soothsayer/chainlink/v11.py.
STATUS_LABELS = {
    0: "unknown",
    1: "pre-market",
    2: "regular",
    3: "post-market",
    4: "overnight",
    5: "closed/weekend",
}

# Spread thresholds for the secondary (real-quote) classification — used only
# when neither bid nor ask carries the synthetic marker. < 200 bps = REAL,
# 200-1000 = AMBIGUOUS, > 1000 = WIDE_REAL (unlikely to be a real quote at
# this spread without a synthetic marker, but we keep the class distinct
# from the BID_SYNTHETIC / ASK_SYNTHETIC / PURE_PLACEHOLDER buckets).
SPREAD_BPS_REAL = 200
SPREAD_BPS_AMBIGUOUS = 1000


def is_synthetic_marker(price: float) -> bool:
    """Detect Chainlink v11's synthetic-low/high price marker.

    During weekends, v11 sets bid (and sometimes ask) to ``floor(p) + 0.01``
    for in-session-stale xStocks — i.e. the price's cents component is
    exactly ``01``. A real-market quote can land there occasionally
    (~1-in-100 chance for any given quote), but across N samples per
    feed, a 100% ``.01``-suffix rate on bid is a strong synthetic signal.

    See ``reports/v11_cadence_verification.md`` for the empirical
    derivation: the SPYx 21.01/715.01 canonical pattern, plus the
    QQQx ``$656.01``, TSLAx ``$372.01``, NVDA-class ``$207.01`` weekend
    bids that all share the same suffix.
    """
    cents = round(price * 100) % 100
    return cents == 1


def fetch_signatures(target_count: int) -> list[dict]:
    """Paginate Verifier signatures back until we have ``target_count`` non-failed
    entries, or the API stops paginating."""
    all_sigs: list[dict] = []
    before: Optional[str] = None
    while len(all_sigs) < target_count:
        page = get_signatures_for_address(VERIFIER_PROGRAM_ID, limit=1000, before=before)
        if not page:
            break
        all_sigs.extend(s for s in page if s.get("err") is None)
        before = page[-1]["signature"]
        if len(page) < 1000:
            # API ran out of history.
            break
    return all_sigs[:target_count]


def classify_quote(bid: float, ask: float, last: float) -> str:
    """6-class taxonomy for v11 quote pairs (v2 classifier).

    Distinguishes the systematic synthetic-marker pattern (bid or ask
    ending in ``.01``) from genuine real two-sided quotes. The previous
    spread-only classifier (``REAL`` / ``AMBIGUOUS`` / ``PLACEHOLDER``)
    collapsed partial-placeholder samples (e.g. QQQx ``bid=$656.01,
    ask=$663.78``) into ``REAL`` because the spread looked tight,
    masking the synthetic-low signal that's actually load-bearing for
    Paper 1 §1.1's "v11 weekend bid/ask are placeholder-derived" claim.

    Classes:
      ``DEGENERATE``       bid >= ask, or any non-positive value.
      ``PURE_PLACEHOLDER`` both bid AND ask are ``.01``-marked.
                           Canonical SPYx 21.01/715.01 pattern.
      ``BID_SYNTHETIC``    bid ``.01``-marked, ask is not.
                           QQQx / TSLAx / NVDA-class partial-placeholder.
      ``ASK_SYNTHETIC``    ask ``.01``-marked, bid is not (rare).
      ``REAL``             neither marked, spread < 200 bps.
      ``AMBIGUOUS``        neither marked, spread 200-1000 bps.
      ``WIDE_REAL``        neither marked, spread > 1000 bps.
                           Unlikely real, but we keep it distinct from
                           the synthetic-marker buckets above.
    """
    if bid <= 0 or ask <= 0 or last <= 0 or ask <= bid:
        return "DEGENERATE"
    bid_synth = is_synthetic_marker(bid)
    ask_synth = is_synthetic_marker(ask)
    if bid_synth and ask_synth:
        return "PURE_PLACEHOLDER"
    if bid_synth and not ask_synth:
        return "BID_SYNTHETIC"
    if ask_synth and not bid_synth:
        return "ASK_SYNTHETIC"
    spread = ask - bid
    mid = (ask + bid) / 2.0
    spread_bps = (spread / mid) * 1e4
    if spread_bps < SPREAD_BPS_REAL:
        return "REAL"
    if spread_bps < SPREAD_BPS_AMBIGUOUS:
        return "AMBIGUOUS"
    return "WIDE_REAL"


# Synthetic-marker classes vs real-quote classes — used when computing the
# "is this feed-status pair behaving as placeholder-derived?" verdict.
SYNTHETIC_CLASSES = {"PURE_PLACEHOLDER", "BID_SYNTHETIC", "ASK_SYNTHETIC"}
REAL_CLASSES = {"REAL"}


def synthetic_aware_verdict(class_counts: dict[str, int]) -> str:
    """Resolve the count distribution to a Paper-1-relevant verdict.

    A feed-status pair is **placeholder-derived** if a majority of its
    samples carry the synthetic-marker pattern (any of the three
    synthetic classes). It is **real-quote** if a majority of samples
    are in the ``REAL`` class. Otherwise **mixed**. ``insufficient`` if
    no samples were captured.
    """
    total = sum(class_counts.values())
    if total == 0:
        return "insufficient"
    n_synth = sum(class_counts.get(c, 0) for c in SYNTHETIC_CLASSES)
    n_real = sum(class_counts.get(c, 0) for c in REAL_CLASSES)
    if n_synth / total > 0.5:
        return "placeholder-derived"
    if n_real / total > 0.5:
        return "real-quote"
    return "mixed"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sigs", type=int, default=5000,
                    help="target total v11 signatures to decode (default: 5000)")
    args = ap.parse_args()

    print(f"v11 cadence verification — paginating Verifier program signatures")
    print(f"  target depth: {args.sigs} signatures")
    print(f"  now: {datetime.now(timezone.utc).isoformat()}")

    sigs = fetch_signatures(args.sigs)
    print(f"  collected {len(sigs)} non-failed signatures (~{len(sigs)/1000:.1f}k)")

    # Decode in batches.
    BATCH = 25
    tx_opts = {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}

    by_status: dict[int, list[dict]] = defaultdict(list)
    n_v11 = 0
    n_total = 0

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
            n_total += 1
            rd = parse_verify_return_data((tx.get("meta") or {}).get("returnData"))
            if rd is None or rd.schema != 0x000B:
                continue
            try:
                r = v11_decode(rd.raw_report)
            except Exception:
                continue
            n_v11 += 1
            sym = feed_id_to_xstock(r.feed_id)
            by_status[r.market_status].append({
                "symbol": sym or "(unmapped)",
                "feed_id": r.feed_id_hex,
                "obs_ts": int(r.observations_timestamp),
                "mid": float(r.mid),
                "bid": float(r.bid),
                "ask": float(r.ask),
                "last_traded": float(r.last_traded_price),
                "market_status": r.market_status,
            })
        if (start // BATCH) % 4 == 0:
            print(
                f"  progress: {start + len(chunk)}/{len(sigs)} sigs; "
                f"{n_v11} v11 samples across {len(by_status)} status values"
            )

    print(f"\nfinal: {n_v11} v11 samples / {n_total} decoded txs / "
          f"{len(by_status)} distinct market_status values")

    # Aggregate per-(symbol, status). The v2 verifier reports verdicts at
    # this granularity rather than collapsing across all v11 traffic — the
    # broader-universe aggregate hid the per-symbol synthetic-marker pattern
    # that's actually load-bearing for Paper 1 §1.1.
    sym_status_buckets: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for status, samples in by_status.items():
        for s in samples:
            sym_status_buckets[(s["symbol"], status)].append(s)

    verdicts: dict[tuple[str, int], dict] = {}
    for (sym, status), samples in sym_status_buckets.items():
        class_counts: dict[str, int] = defaultdict(int)
        spreads_bps: list[float] = []
        for s in samples:
            cls = classify_quote(s["bid"], s["ask"], s["last_traded"])
            class_counts[cls] += 1
            if s["ask"] > s["bid"] > 0:
                mid = (s["bid"] + s["ask"]) / 2.0
                spreads_bps.append((s["ask"] - s["bid"]) / mid * 1e4)
        verdicts[(sym, status)] = {
            "n": len(samples),
            "class_counts": dict(class_counts),
            "n_pure_placeholder": class_counts.get("PURE_PLACEHOLDER", 0),
            "n_bid_synthetic": class_counts.get("BID_SYNTHETIC", 0),
            "n_ask_synthetic": class_counts.get("ASK_SYNTHETIC", 0),
            "n_real": class_counts.get("REAL", 0),
            "n_ambiguous": class_counts.get("AMBIGUOUS", 0),
            "n_wide_real": class_counts.get("WIDE_REAL", 0),
            "n_degenerate": class_counts.get("DEGENERATE", 0),
            "median_spread_bps": median(spreads_bps) if spreads_bps else None,
            "verdict": synthetic_aware_verdict(class_counts),
            "samples": samples[:5],
        }

    # Stdout per-(symbol, status) summary.
    print()
    print("=" * 110)
    print(f"{'symbol':<14} {'status':>6}  {'label':<14}  {'n':>4}  "
          f"{'pure':>4}  {'bid':>4}  {'ask':>4}  {'real':>4}  {'amb':>4}  "
          f"{'med_sprd':>9}  {'verdict':<22}")
    print("=" * 110)
    sorted_keys = sorted(verdicts.keys(), key=lambda k: (k[1], k[0] or "~"))
    for (sym, status) in sorted_keys:
        v = verdicts[(sym, status)]
        med = v["median_spread_bps"]
        med_s = f"{med:>7.1f}" if med is not None else "    n/a"
        print(f"  {sym:<12} {status:>4}  {STATUS_LABELS.get(status, '?'):<14}  "
              f"{v['n']:>4}  {v['n_pure_placeholder']:>4}  {v['n_bid_synthetic']:>4}  "
              f"{v['n_ask_synthetic']:>4}  {v['n_real']:>4}  {v['n_ambiguous']:>4}  "
              f"{med_s:>9}  {v['verdict']:<22}")

    # Write the verification report.
    report_path = REPORTS / "v11_cadence_verification.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(report_path, verdicts, n_v11, n_total, len(sigs))
    print(f"\nWrote {report_path}")


def write_report(path: Path, verdicts: dict[tuple[str, int], dict], n_v11: int,
                 n_total: int, n_sigs: int) -> None:
    md: list[str] = []
    md.append("# Chainlink Data Streams v11 — 24/5 cadence verification\n")
    md.append(f"*Generated {datetime.now(timezone.utc).isoformat()} by "
              f"`scripts/verify_v11_cadence.py` (v2 — synthetic-marker classifier, "
              f"per-symbol verdicts). Re-run any time; idempotent.*\n")
    md.append(
        "Closes the **Must-fix-before-Paper-1-arXiv** publication-risk gate "
        "(`docs/ROADMAP.md` Publication-risk gates §1.2). The empirical question: "
        "during pre-market / regular / post-market / overnight windows, does v11 "
        "carry *real* `bid` / `ask` / `mid` values, or are they placeholder-"
        "derived bookends like during weekends?\n"
    )
    md.append(
        "## Method (v2 classifier)\n\n"
        f"Paginated through {n_sigs} non-failed Verifier program signatures, "
        f"decoded {n_total} transactions, isolated {n_v11} v11 (schema `0x000b`) "
        f"reports, grouped by `(symbol, market_status)` using the "
        f"`XSTOCK_V11_FEEDS` registry. Each sample is classified into a 6-class "
        f"taxonomy that distinguishes synthetic-marker patterns from real quotes:\n\n"
        f"  - **PURE_PLACEHOLDER** — both bid AND ask end in `.01` (the canonical "
        f"SPYx 21.01/715.01 bookend pattern).\n"
        f"  - **BID_SYNTHETIC** — bid ends in `.01`, ask does not. Partial-"
        f"placeholder pattern: synthetic-low bid paired with real-ish ask. The "
        f"v1 spread-only classifier missed this when the spread happened to fall "
        f"under 200 bps.\n"
        f"  - **ASK_SYNTHETIC** — ask ends in `.01`, bid does not (rare).\n"
        f"  - **REAL** — neither side `.01`-marked, spread < {SPREAD_BPS_REAL} bps.\n"
        f"  - **AMBIGUOUS** — neither side `.01`-marked, spread "
        f"{SPREAD_BPS_REAL}–{SPREAD_BPS_AMBIGUOUS} bps.\n"
        f"  - **WIDE_REAL** — neither side `.01`-marked, spread > "
        f"{SPREAD_BPS_AMBIGUOUS} bps.\n"
        f"  - **DEGENERATE** — bid ≥ ask, or any non-positive value.\n\n"
        "Per-(symbol, status) verdict (synthetic-aware):\n\n"
        "  - **placeholder-derived** — > 50% of samples are in any synthetic class "
        "(PURE_PLACEHOLDER + BID_SYNTHETIC + ASK_SYNTHETIC).\n"
        "  - **real-quote** — > 50% of samples are REAL.\n"
        "  - **mixed** — neither majority.\n"
        "  - **insufficient** — no samples for that bucket.\n\n"
        "The synthetic-marker (`.01` suffix) was identified empirically: every "
        "v11 weekend bid in the prior scan ended in exactly `.01` across the 4 "
        "mapped xStocks (SPYx 21.01, QQQx 656.01, TSLAx 372.01, NVDA-class "
        "207.01). Real-market bids land on `.01` ~1-in-100 randomly; a 100% "
        "incidence is a strong synthetic signal.\n"
    )

    # Per-(symbol, status) verdicts table.
    md.append("## Per-(symbol, status) verdicts\n\n")
    md.append(
        "| symbol | status | label | n | pure-PH | bid-synth | ask-synth | real | "
        "ambig | wide | median spread (bps) | verdict |\n"
    )
    md.append(
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|\n"
    )
    sorted_keys = sorted(verdicts.keys(), key=lambda k: (k[1], k[0] or "~"))
    for (sym, status) in sorted_keys:
        v = verdicts[(sym, status)]
        med = v["median_spread_bps"]
        med_s = f"{med:.1f}" if med is not None else "–"
        sym_label = sym if sym else "(unmapped)"
        md.append(
            f"| **{sym_label}** | {status} | {STATUS_LABELS.get(status, '?')} | "
            f"{v['n']} | {v['n_pure_placeholder']} | {v['n_bid_synthetic']} | "
            f"{v['n_ask_synthetic']} | {v['n_real']} | {v['n_ambiguous']} | "
            f"{v['n_wide_real']} | {med_s} | **{v['verdict']}** |\n"
        )
    md.append("\n")

    # Sample evidence per (symbol, status).
    md.append("## Sample evidence per (symbol, status)\n\n")
    md.append(
        "Raw decoded fields (first up to 5 per bucket). `bid`, `ask`, `mid`, "
        "`last_traded` are the v11 wire fields. Watch for the `.01` suffix on "
        "bid as the synthetic-low marker; the `class` column shows the v2 "
        "classifier's call.\n"
    )
    for (sym, status) in sorted_keys:
        v = verdicts[(sym, status)]
        if not v["samples"]:
            continue
        sym_label = sym if sym else "(unmapped)"
        md.append(
            f"### `{sym_label}`, `market_status = {status}` "
            f"({STATUS_LABELS.get(status, '?')}) — {v['n']} samples\n\n"
        )
        md.append("| obs_ts | bid | ask | mid | last_traded | spread (bps) | class |\n")
        md.append("|---|---:|---:|---:|---:|---:|---|\n")
        for s in v["samples"]:
            spread = s["ask"] - s["bid"]
            mid = (s["ask"] + s["bid"]) / 2.0
            spread_bps = (spread / mid) * 1e4 if mid > 0 else float("nan")
            cls = classify_quote(s["bid"], s["ask"], s["last_traded"])
            ts = datetime.fromtimestamp(s["obs_ts"], timezone.utc).isoformat()
            md.append(
                f"| {ts} | {s['bid']:.4f} | {s['ask']:.4f} | "
                f"{s['mid']:.4f} | {s['last_traded']:.4f} | "
                f"{spread_bps:.1f} | {cls} |\n"
            )
        md.append("\n")

    # Coverage summary — which (symbol, status) buckets do we have evidence for?
    known_xstocks = ["SPYx", "QQQx", "TSLAx", "GOOGLx", "AAPLx", "NVDAx", "MSTRx", "HOODx"]
    md.append("## Coverage matrix — known xStocks × market_status\n\n")
    md.append(
        "Filled cells have ≥ 1 sample for that bucket; empty cells are pending "
        "the next scan run during the relevant trading window.\n\n"
    )
    md.append(
        "| xStock | pre-mkt (1) | regular (2) | post-mkt (3) | overnight (4) | weekend (5) | unknown (0) |\n"
    )
    md.append("|---|---|---|---|---|---|---|\n")
    for sym in known_xstocks:
        cells: list[str] = [f"**{sym}**"]
        for status in (1, 2, 3, 4, 5, 0):
            v = verdicts.get((sym, status))
            if v is None or v["n"] == 0:
                cells.append("–")
            else:
                cells.append(f"{v['verdict']} (n={v['n']})")
        md.append("| " + " | ".join(cells) + " |\n")
    md.append("\n")

    # Outstanding section.
    seen_statuses = {status for (_, status) in verdicts.keys()}
    missing_statuses = [s for s in (1, 2, 3, 4, 5, 0) if s not in seen_statuses]
    md.append("## Outstanding\n\n")
    if not missing_statuses:
        md.append(
            "All six market_status values have ≥ 1 sample in this scan. "
            "The verdict table above is the canonical answer to the publication-"
            "risk gate.\n"
        )
    else:
        md.append(
            "The following `market_status` values had **no** samples in this scan window:\n\n"
        )
        for s in missing_statuses:
            md.append(f"  - `{s}` ({STATUS_LABELS.get(s, '?')})\n")
        md.append(
            "\nThis is expected if the scan ran outside the relevant trading window "
            "(e.g., a Sunday-afternoon scan only sees `market_status=5`). Re-run during "
            "the appropriate window to fill in the gaps:\n\n"
            "  - pre-market — Mon–Fri 04:00–09:30 ET (08:00–13:30 UTC)\n"
            "  - regular — Mon–Fri 09:30–16:00 ET (13:30–20:00 UTC)\n"
            "  - post-market — Mon–Fri 16:00–20:00 ET (20:00–00:00 UTC)\n"
            "  - overnight — Mon–Fri 20:00 ET–04:00 ET next day (00:00–08:00 UTC)\n\n"
            "The script is idempotent and cron-friendly; re-running through the "
            "week accumulates samples across all sessions.\n"
        )
    md.append("\n")

    # Paper 1 implication footer.
    md.append(
        "## What this verifies for Paper 1 §1.1 / §2.1\n\n"
        "The §1.1 / §2.1 framing claims v11 weekend `bid`/`ask`/`mid` are "
        "placeholder-derived. The v2 classifier supports that claim feed-by-"
        "feed: any `(symbol, status)` bucket whose verdict is "
        "**placeholder-derived** is direct empirical support for §1.1 at that "
        "specific (symbol, status). A **mixed** or **real-quote** verdict "
        "would require qualifying §1.1 to exclude that bucket.\n\n"
        "The 4 mapped xStocks at status=5 (weekend) are the gate-closing rows. "
        "Other (symbol, status) buckets become available as the script accumulates "
        "samples through the trading week. The unmapped rows in the table above "
        "are v11 feeds for non-xStock RWAs sharing the schema; they're useful "
        "context but not load-bearing for Paper 1.\n"
    )
    path.write_text("".join(md))


if __name__ == "__main__":
    main()
