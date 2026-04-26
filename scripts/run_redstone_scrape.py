"""
RedStone Live forward-cursor tape.

Polls api.redstone.finance/prices for the underlier tickers RedStone Live serves
(SPY, QQQ, MSTR — confirmed available 2026-04-25; TSLA, NVDA, HOOD, GOOGL returned
empty at scoping time, AAPL was 33d stale). Appends every observation to
data/processed/redstone_live_tape.parquet.

Three modes:

  --poll {fri_close,mon_open,manual}
      Single-shot: hit `?symbol={S}&provider=redstone&limit=1` per symbol, append.
      The label is recorded in the parquet so we can stratify later.

  --backfill
      One-shot: hit `?fromTimestamp=...&toTimestamp=...&interval=600000` over the
      last 30d (RedStone gateway hard cap). Useful on day-of-deploy to grab any
      pre-existing history that's still in the gateway's retention window.

  --probe
      Hit each symbol once, print the response, do NOT append. For sanity checks.

Schema (parquet, append-safe):
  poll_ts (UTC)        — when WE polled
  poll_label (str)     — fri_close | mon_open | manual | backfill
  symbol (str)         — RedStone-side query symbol
  redstone_ts (UTC)    — `timestamp` field on the served record
  minutes_age (Int64)  — RedStone's `minutes` field at poll time
  value (float)        — `value` field
  provider_pubkey (str)
  signature (str)      — `liteEvmSignature`
  source_json (str)    — JSON-serialised `source` dict (variable schema across symbols)
  permaweb_tx (str)
  raw_json (str)       — full record, for forensic replay if their schema changes

Usage:
  uv run python scripts/run_redstone_scrape.py --probe
  uv run python scripts/run_redstone_scrape.py --poll fri_close
  uv run python scripts/run_redstone_scrape.py --poll mon_open
  uv run python scripts/run_redstone_scrape.py --backfill

The script is idempotent on (poll_ts, symbol) — re-running the same poll overwrites
nothing because each call's poll_ts is fresh. Duplicate redstone_ts across polls is
expected (the gateway holds the last-seen value during off-hours) and is the headline
empirical observation we want to capture.

Reference: scoping note 2026-04-25, conversation transcript. Endpoint docs at
https://api.docs.redstone.finance/http-api/prices. Hard 30-day retention cap on the
gateway — confirmed by direct probe at T-31d.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from soothsayer.config import DATA_PROCESSED

GATEWAY = "https://api.redstone.finance/prices"
PROVIDER = "redstone"

# Confirmed available 2026-04-25 against the public gateway.
# Re-verify periodically with --probe; coverage drift is itself a finding.
SYMBOLS = ["SPY", "QQQ", "MSTR"]

# Symbols probed at scoping time that returned [] or stale data.
# Listed here so future maintainers see what's been ruled out and can re-probe.
KNOWN_EMPTY_2026_04_25 = ["TSLA", "NVDA", "HOOD", "GOOGL"]
KNOWN_STALE_2026_04_25 = ["AAPL"]  # 33d behind, may have been retired

OUT_PARQUET = DATA_PROCESSED / "redstone_live_tape.parquet"
LOG_PATH = DATA_PROCESSED / "redstone_scrape.log"

REQUEST_TIMEOUT_S = 30  # backfill responses can be 4k+ records; poll mode is tiny
RETRY_DELAY_S = 5
MAX_RETRIES = 3


def _log(msg: str) -> None:
    line = f"[{datetime.now(UTC).isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def _fetch(params: dict[str, Any]) -> list[dict[str, Any]]:
    """One GET against the gateway, with light retry on transient errors."""
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(GATEWAY, params=params, timeout=REQUEST_TIMEOUT_S)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "error" in data:
                # gateway returns {"error": "..."} for out-of-range timestamps etc.
                _log(f"  gateway error for params={params}: {data['error']}")
                return []
            return data if isinstance(data, list) else [data]
        except (requests.RequestException, ValueError) as e:
            last_err = e
            _log(f"  attempt {attempt}/{MAX_RETRIES} failed: {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
    raise RuntimeError(f"all {MAX_RETRIES} attempts failed; last={last_err!r}")


def _normalise(record: dict[str, Any], poll_ts: datetime, label: str) -> dict[str, Any]:
    """Flatten a gateway record into the tape schema. Defensive on missing fields."""
    rs_ts_ms = record.get("timestamp")
    rs_ts = (
        datetime.fromtimestamp(rs_ts_ms / 1000, tz=UTC) if isinstance(rs_ts_ms, (int, float)) else None
    )
    return {
        "poll_ts": poll_ts,
        "poll_label": label,
        "symbol": record.get("symbol"),
        "redstone_ts": rs_ts,
        "minutes_age": record.get("minutes"),
        "value": record.get("value"),
        "provider_pubkey": record.get("providerPublicKey", ""),
        "signature": record.get("liteEvmSignature", ""),
        "source_json": json.dumps(record.get("source", {}), sort_keys=True),
        "permaweb_tx": record.get("permawebTx", ""),
        "raw_json": json.dumps(record, sort_keys=True),
    }


def _append(rows: list[dict[str, Any]]) -> None:
    if not rows:
        _log("nothing to append")
        return
    new_df = pd.DataFrame(rows)
    new_df["minutes_age"] = new_df["minutes_age"].astype("Int64")
    if OUT_PARQUET.exists():
        existing = pd.read_parquet(OUT_PARQUET)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_parquet(OUT_PARQUET, index=False)
    _log(f"appended {len(rows)} rows -> {OUT_PARQUET} (total: {len(combined)})")


def cmd_probe() -> None:
    """Hit each symbol once and print the response, no parquet write."""
    for sym in SYMBOLS + KNOWN_EMPTY_2026_04_25 + KNOWN_STALE_2026_04_25:
        try:
            data = _fetch({"symbol": sym, "provider": PROVIDER, "limit": 1})
        except Exception as e:
            _log(f"{sym}: ERROR {type(e).__name__}: {e}")
            continue
        if not data:
            _log(f"{sym}: empty")
            continue
        rec = data[0]
        ts_ms = rec.get("timestamp", 0)
        age_s = (datetime.now(UTC).timestamp() * 1000 - ts_ms) / 1000 if ts_ms else None
        age_str = f" wall_age_s={age_s:.0f}" if age_s is not None else ""
        _log(f"{sym}: value={rec.get('value')} minutes_age={rec.get('minutes')}{age_str}")
        _log(f"  source={rec.get('source')}")


def cmd_poll(label: str) -> None:
    poll_ts = datetime.now(UTC)
    _log(f"poll start label={label} ts={poll_ts.isoformat(timespec='seconds')}")
    rows: list[dict[str, Any]] = []
    for sym in SYMBOLS:
        try:
            data = _fetch({"symbol": sym, "provider": PROVIDER, "limit": 1})
        except Exception as e:
            _log(f"  {sym}: ERROR {type(e).__name__}: {e}")
            continue
        if not data:
            _log(f"  {sym}: empty (no data returned)")
            continue
        row = _normalise(data[0], poll_ts, label)
        rows.append(row)
        _log(
            f"  {sym}: value={row['value']} "
            f"minutes_age={row['minutes_age']} "
            f"redstone_ts={row['redstone_ts']}"
        )
    _append(rows)


def cmd_backfill() -> None:
    """Pull last 30d at 10-min interval per symbol. One-shot; intended for day-of-deploy."""
    poll_ts = datetime.now(UTC)
    to_ts_ms = int(poll_ts.timestamp() * 1000)
    from_ts_ms = int((poll_ts - timedelta(days=29, hours=22)).timestamp() * 1000)  # safety margin
    interval_ms = 10 * 60 * 1000  # 10 min — matches gateway native cadence
    _log(f"backfill start: from={from_ts_ms} to={to_ts_ms} interval=10min")
    rows: list[dict[str, Any]] = []
    for sym in SYMBOLS:
        try:
            data = _fetch(
                {
                    "symbol": sym,
                    "provider": PROVIDER,
                    "fromTimestamp": from_ts_ms,
                    "toTimestamp": to_ts_ms,
                    "interval": interval_ms,
                }
            )
        except Exception as e:
            _log(f"  {sym}: ERROR {type(e).__name__}: {e}")
            continue
        _log(f"  {sym}: {len(data)} historical points")
        for rec in data:
            rows.append(_normalise(rec, poll_ts, "backfill"))
    _append(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--poll", choices=["fri_close", "mon_open", "manual"], help="single-shot poll, append to tape")
    g.add_argument("--backfill", action="store_true", help="one-shot 30d backfill")
    g.add_argument("--probe", action="store_true", help="probe all symbols, print, do not append")
    args = parser.parse_args()

    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)

    if args.probe:
        cmd_probe()
    elif args.backfill:
        cmd_backfill()
    elif args.poll:
        cmd_poll(args.poll)
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
