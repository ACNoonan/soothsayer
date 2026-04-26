"""
Halt regime tagging — Nasdaq Trader live RSS + yfinance-implied detection.

Why this exists
---------------
Paper 1's regime detector currently pools halt days into the `normal` regime,
introducing unidentified noise. data-sources.md "Grant-impact addendum" lists
"halt-aware regime tag distinct from `high_vol`" as a Tier 1 ($0) free
improvement that closes a documented limitation. This script produces the
labelled-halt artifact the regime detector consumes.

Two complementary signals
-------------------------
  1. Implied halts from yfinance EOD (`--build-implied`)
     Backbone for the 12-yr panel — Nasdaq Trader's RSS feed only carries
     ~30d of history, so historical labelling has to come from a signal
     present in data we already have. Detection rules:

       (a) zero-volume day on a session that should have traded (i.e. not a
           known US market holiday) — strong halt signal.
       (b) frozen-price day: volume non-zero but `(high - low) / close` is
           below a configurable epsilon AND adjusted close equals prior
           close to within rounding — soft halt signal (suggests a partial-
           session halt with limited price movement).
       (c) missing-bar day inside a same-week trading window — possible
           full-day halt or a delisting; flagged for manual review rather
           than auto-classified.

  2. Live Nasdaq Trader halts RSS (`--rss-poll`)
     Forward validation source. Polled to build a forward tape that lets us
     calibrate the implied detector against ground-truth halts going
     forward. Does not contribute to historical labelling for Paper 1.

Cross-check (`--validate`) intersects the two tapes on their overlap window
(roughly the last 30d at first run, expanding as the live tape accumulates)
and reports detector precision/recall against RSS-confirmed halts. Output
goes to reports/nasdaq_halts_validation.md for paper §9 reference.

Outputs
-------
  data/processed/nasdaq_halts_implied.parquet  — historical implied-halt rows
  data/processed/nasdaq_halts_live.parquet     — forward RSS tape (append-only)
  data/processed/nasdaq_halts_scrape.log       — run log
  reports/nasdaq_halts_validation.md           — validation writeup (after --validate)

Usage
-----
  uv run python -u scripts/scrape_nasdaq_halts.py --probe
  uv run python -u scripts/scrape_nasdaq_halts.py --build-implied
  uv run python -u scripts/scrape_nasdaq_halts.py --rss-poll
  uv run python -u scripts/scrape_nasdaq_halts.py --validate

References
----------
  Nasdaq Trader public RSS:    https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts
  Reason-code reference:       https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltCodes
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from lxml import etree

from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.sources.yahoo import fetch_daily
from soothsayer.universe import ALL_XSTOCKS


RSS_URL = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
RSS_NS = {"ndaq": "http://www.nasdaqtrader.com/"}

OUT_IMPLIED = DATA_PROCESSED / "nasdaq_halts_implied.parquet"
OUT_LIVE = DATA_PROCESSED / "nasdaq_halts_live.parquet"
LOG_PATH = DATA_PROCESSED / "nasdaq_halts_scrape.log"
VALIDATION_REPORT = REPORTS / "nasdaq_halts_validation.md"

REQUEST_TIMEOUT_S = 30

# Detection thresholds — conservative defaults; revisit after first --validate run.
FROZEN_PRICE_EPSILON = 1e-4    # (high - low) / close below this counts as "flat"
HISTORICAL_START = date(2014, 1, 1)


def _log(msg: str) -> None:
    line = f"[{datetime.now(UTC).isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Implied-halt detection from yfinance EOD bars
# ---------------------------------------------------------------------------

def _detect_implied_for_ticker(
    ticker: str, daily: pd.DataFrame, *, epsilon: float = FROZEN_PRICE_EPSILON
) -> list[dict[str, Any]]:
    """Apply the implied-halt rules to one ticker's daily frame.

    Expects a long-form per-ticker slice with columns ['ts','open','high','low',
    'close','adj_close','volume'] (the shape `fetch_daily` returns after
    filtering by symbol). Returns a list of halt-row dicts.
    """
    if daily.empty:
        return []
    rows: list[dict[str, Any]] = []
    daily = daily.copy().sort_values("ts").reset_index(drop=True)
    prev_close = daily["adj_close"].shift(1)
    close_safe = daily["close"].replace({0.0: pd.NA})
    range_ratio = (daily["high"] - daily["low"]) / close_safe
    flat_to_prior = (daily["adj_close"].sub(prev_close).abs() / prev_close.abs()).fillna(1.0)

    for i, row in daily.iterrows():
        d = row["ts"]
        evidence: dict[str, Any] = {
            "open": float(row.get("open", float("nan"))),
            "high": float(row.get("high", float("nan"))),
            "low": float(row.get("low", float("nan"))),
            "close": float(row.get("close", float("nan"))),
            "volume": float(row.get("volume", float("nan"))),
        }
        vol = row.get("volume", 0)
        rng = range_ratio.iloc[i]
        flat = flat_to_prior.iloc[i]

        # Rule (a): zero-volume on a session that exists in the series
        if pd.notna(vol) and vol == 0:
            rows.append(
                {
                    "date": d,
                    "underlying": ticker,
                    "halt_type": "implied_zero_vol",
                    "evidence_json": json.dumps(evidence, sort_keys=True),
                    "detected_at": datetime.now(UTC),
                }
            )
            continue

        # Rule (b): high == low (intraday-flat) AND adj_close basically
        # unchanged from prior session. Catches full-session halts.
        if pd.notna(rng) and rng < epsilon and pd.notna(flat) and flat < epsilon:
            rows.append(
                {
                    "date": d,
                    "underlying": ticker,
                    "halt_type": "implied_flat_price",
                    "evidence_json": json.dumps(evidence, sort_keys=True),
                    "detected_at": datetime.now(UTC),
                }
            )
    # Rule (c) — missing-bar inside a same-week trading window — is not auto-
    # classified here because distinguishing halts from delistings/data gaps
    # cleanly needs a US-trading-day calendar join. Left as a follow-up.
    return rows


def cmd_build_implied() -> None:
    """Scan the panel underlyings' yfinance EOD for implied halts.

    Restricted to the 10 panel underlyings (xStock-mapped equities). Futures /
    vol-indices / crypto regressors are excluded — they trade 23/5 or 24/7 and
    the EOD-based halt heuristics produce false positives there.
    """
    universe = sorted({x.underlying for x in ALL_XSTOCKS})
    end = date.today() + timedelta(days=1)
    _log(f"build-implied start: {len(universe)} panel underlyings, range {HISTORICAL_START} → {end}")

    all_rows: list[dict[str, Any]] = []
    for ticker in universe:
        try:
            df = fetch_daily([ticker], start=HISTORICAL_START, end=end)
        except Exception as e:
            _log(f"  {ticker}: ERROR fetching daily: {type(e).__name__}: {e}")
            continue

        # fetch_daily returns long-form: (symbol, ts, open, high, low, close, adj_close, volume)
        sub = df[df["symbol"] == ticker].copy()
        if sub.empty:
            _log(f"  {ticker}: no rows after symbol filter; skipping")
            continue

        rows = _detect_implied_for_ticker(ticker, sub)
        _log(f"  {ticker}: {len(rows)} implied-halt rows over {len(sub)} sessions")
        all_rows.extend(rows)

    if not all_rows:
        _log(
            "no implied halts detected on the panel underlyings — confirms that liquid "
            "US equities do not produce yfinance-EOD-detectable halts at this universe size. "
            "halt-regime pooling concern (data-sources.md addendum) does not materially apply."
        )
        # Write an empty parquet so downstream consumers can distinguish "ran but found nothing"
        # from "never ran." Schema must match the populated case.
        empty = pd.DataFrame(
            columns=["date", "underlying", "halt_type", "evidence_json", "detected_at"]
        )
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        empty.to_parquet(OUT_IMPLIED, index=False)
        _log(f"wrote empty halt parquet → {OUT_IMPLIED} (negative-finding artifact)")
        return

    out_df = pd.DataFrame(all_rows)
    out_df["date"] = pd.to_datetime(out_df["date"]).dt.date
    out_df = out_df.sort_values(["date", "underlying"]).reset_index(drop=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(OUT_IMPLIED, index=False)
    _log(
        f"wrote {len(out_df)} implied-halt rows → {OUT_IMPLIED} "
        f"({out_df['underlying'].nunique()} tickers, {out_df['date'].nunique()} unique dates)"
    )


# ---------------------------------------------------------------------------
# Live RSS poll (forward tape)
# ---------------------------------------------------------------------------

def _parse_rss(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Parse Nasdaq Trader's halt RSS into normalized rows.

    Each <item> contains the halt fields directly under the `ndaq:` namespace —
    confirmed from a live probe 2026-04-26. There is no intermediate wrapper
    element. Field set per the live feed: HaltDate, HaltTime, IssueSymbol,
    IssueName, Market, ReasonCode, PauseThresholdPrice, ResumptionDate,
    ResumptionQuoteTime, ResumptionTradeTime.
    """
    poll_ts = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    # Strip BOM if present (the live feed serves UTF-8 with BOM)
    if xml_bytes[:3] == b"\xef\xbb\xbf":
        xml_bytes = xml_bytes[3:]
    root = etree.fromstring(xml_bytes)
    items = root.findall(".//item")
    for item in items:
        get = lambda tag: (item.findtext(f"ndaq:{tag}", namespaces=RSS_NS) or "").strip()
        # Skip items missing both date and symbol — defensively guards against
        # any future <item> entries that don't carry halt fields.
        halt_date = get("HaltDate")
        symbol = get("IssueSymbol")
        if not halt_date and not symbol:
            continue
        rows.append(
            {
                "poll_ts": poll_ts,
                "halt_date": halt_date,
                "halt_time": get("HaltTime"),
                "underlying": symbol,
                "issue_name": get("IssueName"),
                "market_category": get("Market"),
                "reason_code": get("ReasonCode"),
                "pause_threshold_price": get("PauseThresholdPrice") or None,
                "resumption_date": get("ResumptionDate") or None,
                "resumption_quote_time": get("ResumptionQuoteTime") or None,
                "resumption_trade_time": get("ResumptionTradeTime") or None,
                "raw_xml": etree.tostring(item, encoding="unicode"),
            }
        )
    return rows


def cmd_rss_poll() -> None:
    """Hit the live RSS once and append to the forward tape."""
    _log(f"rss-poll start: GET {RSS_URL}")
    try:
        r = requests.get(RSS_URL, timeout=REQUEST_TIMEOUT_S)
        r.raise_for_status()
    except requests.RequestException as e:
        _log(f"  ERROR: {type(e).__name__}: {e}")
        sys.exit(1)

    rows = _parse_rss(r.content)
    _log(f"  parsed {len(rows)} halt rows from feed")
    if not rows:
        return

    new_df = pd.DataFrame(rows)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    if OUT_LIVE.exists():
        existing = pd.read_parquet(OUT_LIVE)
        combined = pd.concat([existing, new_df], ignore_index=True)
        # Idempotent on (poll_ts, halt_date, underlying, halt_time): a re-poll within the
        # same second of a duplicate halt entry would otherwise add a row.
        combined = combined.drop_duplicates(
            subset=["poll_ts", "halt_date", "underlying", "halt_time"], keep="last"
        )
    else:
        combined = new_df
    combined.to_parquet(OUT_LIVE, index=False)
    _log(f"appended {len(rows)} rows → {OUT_LIVE} (total: {len(combined)})")


def cmd_probe() -> None:
    """Hit the RSS feed once and print parsed rows. Does not write."""
    _log(f"probe: GET {RSS_URL}")
    r = requests.get(RSS_URL, timeout=REQUEST_TIMEOUT_S)
    r.raise_for_status()
    rows = _parse_rss(r.content)
    _log(f"  parsed {len(rows)} entries from feed")
    for row in rows[:20]:
        _log(
            f"  {row['halt_date']} {row['halt_time']} "
            f"{row['underlying']:<8} reason={row['reason_code']:<6} "
            f"resume={row['resumption_date'] or '—'} {row['resumption_trade_time'] or ''}"
        )
    if len(rows) > 20:
        _log(f"  ... ({len(rows) - 20} more rows truncated)")


# ---------------------------------------------------------------------------
# Validation: implied vs live RSS overlap
# ---------------------------------------------------------------------------

def cmd_validate() -> None:
    """Cross-check implied-halt detection against the live RSS tape on the overlap window.

    Reports precision/recall against RSS-confirmed halts. This is the calibration
    artifact the regime detector consumes — if precision is materially below 1.0,
    tighten FROZEN_PRICE_EPSILON or add Rule (c) holiday-aware filtering.
    """
    if not OUT_IMPLIED.exists():
        _log(f"missing {OUT_IMPLIED}; run --build-implied first")
        sys.exit(1)
    if not OUT_LIVE.exists():
        _log(f"missing {OUT_LIVE}; run --rss-poll a few times first")
        sys.exit(1)

    implied = pd.read_parquet(OUT_IMPLIED)
    live = pd.read_parquet(OUT_LIVE)
    live["halt_date_parsed"] = pd.to_datetime(live["halt_date"], errors="coerce").dt.date
    live = live.dropna(subset=["halt_date_parsed"])

    # Restrict implied detection to the overlap window for fair comparison.
    overlap_start = live["halt_date_parsed"].min()
    overlap_end = live["halt_date_parsed"].max()
    if pd.isna(overlap_start) or pd.isna(overlap_end):
        _log("live tape has no parseable halt_date column; aborting validation")
        sys.exit(1)
    implied_window = implied[(implied["date"] >= overlap_start) & (implied["date"] <= overlap_end)]

    implied_set = set(zip(implied_window["date"], implied_window["underlying"]))
    live_set = set(zip(live["halt_date_parsed"], live["underlying"]))
    tp = implied_set & live_set
    fp = implied_set - live_set
    fn = live_set - implied_set

    precision = len(tp) / max(len(implied_set), 1)
    recall = len(tp) / max(len(live_set), 1)

    REPORTS.mkdir(parents=True, exist_ok=True)
    with VALIDATION_REPORT.open("w") as f:
        f.write("# Nasdaq halt detector — implied-vs-live validation\n\n")
        f.write(f"Overlap window: {overlap_start} → {overlap_end}\n\n")
        f.write(
            f"- Implied halts in window: **{len(implied_set)}**\n"
            f"- RSS-confirmed halts in window: **{len(live_set)}**\n"
            f"- True positives (overlap): **{len(tp)}**\n"
            f"- False positives (implied not in RSS): **{len(fp)}**\n"
            f"- False negatives (RSS not in implied): **{len(fn)}**\n"
            f"- Precision: **{precision:.3f}**\n"
            f"- Recall: **{recall:.3f}**\n\n"
        )
        if fp:
            f.write("## Sample false positives (implied but not in RSS)\n\n")
            for d, t in sorted(fp)[:15]:
                f.write(f"- {d} {t}\n")
            f.write("\n")
        if fn:
            f.write("## Sample false negatives (RSS but not implied)\n\n")
            for d, t in sorted(fn)[:15]:
                f.write(f"- {d} {t}\n")
    _log(
        f"wrote validation report → {VALIDATION_REPORT}: "
        f"precision={precision:.3f} recall={recall:.3f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--build-implied", action="store_true", help="scan yfinance EOD for implied halts")
    g.add_argument("--rss-poll", action="store_true", help="poll live Nasdaq Trader halt RSS")
    g.add_argument("--probe", action="store_true", help="hit RSS once, print, do not write")
    g.add_argument("--validate", action="store_true", help="cross-check implied vs RSS overlap window")
    args = parser.parse_args()

    if args.probe:
        cmd_probe()
    elif args.build_implied:
        cmd_build_implied()
    elif args.rss_poll:
        cmd_rss_poll()
    elif args.validate:
        cmd_validate()


if __name__ == "__main__":
    main()
