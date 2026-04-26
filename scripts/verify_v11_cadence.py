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

from soothsayer.chainlink.feeds import feed_id_to_xstock
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

# Heuristic thresholds for classifying a (bid, ask) pair as real vs
# placeholder. Real-market quotes for liquid equities have spreads of a
# few bps to ~50 bps; the known weekend placeholders sit around
# (21.01, 715.01) for SPY-class, i.e. > 90% of mid. We bucket spreads
# in three bands: < 200 bps "real-ish", 200-1000 bps "ambiguous",
# > 1000 bps "almost certainly placeholder".
SPREAD_BPS_REAL = 200
SPREAD_BPS_AMBIGUOUS = 1000


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
    """Spread-based heuristic for real vs placeholder vs degenerate quotes."""
    if bid <= 0 or ask <= 0 or last <= 0 or ask <= bid:
        return "DEGENERATE"
    spread = ask - bid
    mid = (ask + bid) / 2.0
    spread_bps = (spread / mid) * 1e4
    if spread_bps < SPREAD_BPS_REAL:
        return "REAL"
    if spread_bps < SPREAD_BPS_AMBIGUOUS:
        return "AMBIGUOUS"
    return "PLACEHOLDER"


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

    # Per-status verdict.
    verdicts: dict[int, dict] = {}
    for status, samples in sorted(by_status.items()):
        spreads_bps: list[float] = []
        classifications: list[str] = []
        for s in samples:
            cls = classify_quote(s["bid"], s["ask"], s["last_traded"])
            classifications.append(cls)
            mid = (s["bid"] + s["ask"]) / 2.0
            if mid > 0 and s["ask"] > s["bid"]:
                spreads_bps.append((s["ask"] - s["bid"]) / mid * 1e4)
        n_real = classifications.count("REAL")
        n_amb = classifications.count("AMBIGUOUS")
        n_ph = classifications.count("PLACEHOLDER")
        n_deg = classifications.count("DEGENERATE")
        n = len(samples)
        if n == 0:
            verdict = "insufficient"
        elif n_real / n > 0.5:
            verdict = "REAL"
        elif n_ph / n > 0.5:
            verdict = "PLACEHOLDER"
        else:
            verdict = "MIXED"
        verdicts[status] = {
            "n": n,
            "n_real": n_real,
            "n_ambiguous": n_amb,
            "n_placeholder": n_ph,
            "n_degenerate": n_deg,
            "median_spread_bps": median(spreads_bps) if spreads_bps else None,
            "max_spread_bps": max(spreads_bps) if spreads_bps else None,
            "min_spread_bps": min(spreads_bps) if spreads_bps else None,
            "verdict": verdict,
            "samples": samples[:5],  # keep up to 5 raw samples for the report
        }

    # Stdout summary.
    print()
    print("=" * 70)
    print(f"{'status':>6}  {'label':<16}  {'n':>5}  {'real':>5}  {'amb':>5}  "
          f"{'plh':>5}  {'med_sprd':>10}  {'verdict':<12}")
    print("=" * 70)
    for status in (1, 2, 3, 4, 5, 0):
        v = verdicts.get(status)
        if v is None:
            print(f"  {status:>4}  {STATUS_LABELS.get(status, '?'):<16}  "
                  f"{'(none)':>5}  {'-':>5}  {'-':>5}  {'-':>5}  {'-':>10}  "
                  f"insufficient")
            continue
        med = v["median_spread_bps"]
        med_s = f"{med:>8.1f}" if med is not None else "    n/a"
        print(f"  {status:>4}  {STATUS_LABELS.get(status, '?'):<16}  "
              f"{v['n']:>5}  {v['n_real']:>5}  {v['n_ambiguous']:>5}  "
              f"{v['n_placeholder']:>5}  {med_s:>10}  {v['verdict']:<12}")

    # Write the verification report.
    report_path = REPORTS / "v11_cadence_verification.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(report_path, verdicts, n_v11, n_total, len(sigs))
    print(f"\nWrote {report_path}")


def write_report(path: Path, verdicts: dict[int, dict], n_v11: int, n_total: int,
                 n_sigs: int) -> None:
    md: list[str] = []
    md.append("# Chainlink Data Streams v11 — 24/5 cadence verification\n")
    md.append(f"*Generated {datetime.now(timezone.utc).isoformat()} by "
              f"`scripts/verify_v11_cadence.py`. Re-run any time; idempotent.*\n")
    md.append(
        "Closes the **Must-fix-before-Paper-1-arXiv** publication-risk gate "
        "(`docs/ROADMAP.md` Publication-risk gates §1.2). The empirical question: "
        "during pre-market / regular / post-market / overnight windows, does v11 "
        "carry *real* `bid` / `ask` / `mid` values, or are they placeholder-"
        "derived bookends like during weekends?\n"
    )
    md.append(
        "## Method\n\n"
        f"Paginated through {n_sigs} non-failed Verifier program signatures, "
        f"decoded {n_total} transactions, isolated {n_v11} v11 (schema `0x000b`) "
        f"reports, grouped by `market_status`. For each sample the spread between "
        f"`bid` and `ask` (in bps of mid) classifies the quote as:\n\n"
        f"  - **REAL** — spread < {SPREAD_BPS_REAL} bps (consistent with a live "
        f"liquid-equity quote)\n"
        f"  - **AMBIGUOUS** — {SPREAD_BPS_REAL}–{SPREAD_BPS_AMBIGUOUS} bps "
        f"(could be a halt or stressed real quote, or a partial placeholder)\n"
        f"  - **PLACEHOLDER** — > {SPREAD_BPS_AMBIGUOUS} bps (consistent with the "
        f"known weekend synthetic bookends, e.g. SPY-class `(21.01, 715.01)`)\n"
        f"  - **DEGENERATE** — bid ≥ ask, or any of bid/ask/last ≤ 0\n\n"
        "Per-status verdict: **REAL** if > 50% of samples classify REAL, "
        "**PLACEHOLDER** if > 50% PLACEHOLDER, otherwise **MIXED**. "
        "**insufficient** if no samples were captured.\n"
    )
    md.append("## Per-status verdicts\n\n")
    md.append("| status | label | n | real | ambig | placeh | median spread (bps) | verdict |\n")
    md.append("|---:|---|---:|---:|---:|---:|---:|---|\n")
    for status in (1, 2, 3, 4, 5, 0):
        v = verdicts.get(status)
        if v is None:
            md.append(f"| {status} | {STATUS_LABELS.get(status, '?')} | 0 | – | – | – | – | **insufficient** |\n")
            continue
        med = v["median_spread_bps"]
        med_s = f"{med:.1f}" if med is not None else "–"
        verdict_md = f"**{v['verdict']}**"
        md.append(
            f"| {status} | {STATUS_LABELS.get(status, '?')} | {v['n']} | "
            f"{v['n_real']} | {v['n_ambiguous']} | {v['n_placeholder']} | "
            f"{med_s} | {verdict_md} |\n"
        )
    md.append("\n")

    # Sample dumps per status.
    md.append("## Sample reports per status\n\n")
    md.append(
        "Raw decoded fields (first up to 5 per status). `bid`, `ask`, `mid`, "
        "`last_traded` are the v11 wire fields.\n"
    )
    for status in (1, 2, 3, 4, 5, 0):
        v = verdicts.get(status)
        if v is None or not v["samples"]:
            continue
        md.append(f"### `market_status = {status}` ({STATUS_LABELS.get(status, '?')}) — {v['n']} total samples\n\n")
        md.append("| symbol | obs_ts | bid | ask | mid | last_traded | spread (bps) | classification |\n")
        md.append("|---|---|---:|---:|---:|---:|---:|---|\n")
        for s in v["samples"]:
            spread = s["ask"] - s["bid"]
            mid = (s["ask"] + s["bid"]) / 2.0
            spread_bps = (spread / mid) * 1e4 if mid > 0 else float("nan")
            cls = classify_quote(s["bid"], s["ask"], s["last_traded"])
            ts = datetime.fromtimestamp(s["obs_ts"], timezone.utc).isoformat()
            md.append(
                f"| {s['symbol']} | {ts} | {s['bid']:.4f} | {s['ask']:.4f} | "
                f"{s['mid']:.4f} | {s['last_traded']:.4f} | "
                f"{spread_bps:.1f} | {cls} |\n"
            )
        md.append("\n")

    # Outstanding-gates note.
    missing = [s for s in (1, 2, 3, 4, 5, 0) if verdicts.get(s) is None or verdicts[s]["n"] == 0]
    md.append("## Outstanding\n\n")
    if not missing:
        md.append(
            "All six market_status values have ≥ 1 sample in this scan. The verdict "
            "table above is the canonical answer to the publication-risk gate.\n"
        )
    else:
        md.append(
            "The following `market_status` values had no samples in this scan window:\n\n"
        )
        for s in missing:
            md.append(f"  - `{s}` ({STATUS_LABELS.get(s, '?')})\n")
        md.append(
            "\nThis is expected if the scan ran outside the relevant trading window "
            "(e.g., a Sunday-afternoon scan only sees `market_status=5`). Re-run during "
            "the appropriate window to fill in the gaps:\n\n"
            "  - pre-market — Mon–Fri 04:00–09:30 ET (08:00–13:30 UTC)\n"
            "  - regular — Mon–Fri 09:30–16:00 ET (13:30–20:00 UTC)\n"
            "  - post-market — Mon–Fri 16:00–20:00 ET (20:00–00:00 UTC)\n"
            "  - overnight — Mon–Fri 20:00 ET–04:00 ET next day (00:00–08:00 UTC)\n\n"
            "Re-running this script periodically over the next week will accumulate "
            "samples across all sessions; the verdict table below is the running answer.\n"
        )
    md.append("\n")
    md.append(
        "## What this verifies\n\n"
        "The Paper 1 framing (§1.1, §2.1) describes Chainlink Data Streams' v11 schema "
        "as carrying placeholder-derived `bid`/`ask`/`mid` during the weekend window. "
        "The honest open question for v11 has been whether those fields go *real* during "
        "24/5 sessions (pre/regular/post/overnight) or stay synthetic bookends. The "
        "verdicts above answer that question per session class. If pre-market / regular / "
        "post-market / overnight all classify **REAL**, the §1.1 weekend-only framing is "
        "correct as-is. If any of those classify **PLACEHOLDER** or **MIXED**, Paper 1 §1.1 "
        "and §2.1 should be updated to reflect that the placeholder behaviour is *not* "
        "weekend-only.\n"
    )
    path.write_text("".join(md))


if __name__ == "__main__":
    main()
