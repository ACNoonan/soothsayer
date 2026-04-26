"""Forward-running Pyth Hermes tape — observe the published price + confidence
interval for each xStock underlier, every minute, across all four Pyth
session feeds (regular / overnight / pre-market / post-market).

Phase 1 / post-Kamino-discovery extension to the comparator. Adds Pyth as a
fourth "method" alongside Kamino-incumbent / Soothsayer τ=0.85 / Soothsayer
τ=0.95 / simple-market-heuristic in the weekly report. Why Pyth as its own
method: among deployed Solana oracles it's the closest existing thing to a
published "band" — its confidence interval is the publisher-dispersion
analog of what Soothsayer publishes calibrated. The comparator's primary
intellectual question — *publisher-dispersion vs calibration-transparent
coverage* — has Pyth on one side of it.

Why session-flavored feeds matter: Pyth publishes *four feeds per equity*:

    Equity.US.SPY/USD          — regular session (NYSE/NASDAQ hours)
    Equity.US.SPY/USD.PRE      — pre-market session
    Equity.US.SPY/USD.POST     — post-market session
    Equity.US.SPY/USD.ON       — overnight session

The interesting empirical fact (verified at smoke-test 2026-04-26 Sunday
afternoon): the *regular* feed widens its confidence aggressively during
off-hours (e.g. SPY regular conf 343 bps vs SPY.ON conf 1.9 bps). A
single-feed comparator hides this behaviour. We collect all four sessions
per symbol so the report can pick the right comparator per-window.

Output: ``data/raw/pyth_xstock_tape_YYYYMMDD.parquet`` (daily partitions).

Run modes:
    uv run python scripts/collect_pyth_xstock_tape.py --once
        — snapshot once and exit. Cron-friendly.
    PYTHONUNBUFFERED=1 nohup uv run python -u scripts/collect_pyth_xstock_tape.py \
        > /tmp/pyth_tape.log 2>&1 &
        — daemon, 60s cadence, 600s buffered flush.

Schema columns:
    poll_ts, poll_unix, symbol, session, pyth_feed_id,
    pyth_price, pyth_conf, pyth_expo, pyth_publish_time, pyth_age_s, pyth_half_width_bps,
    pyth_ema_price, pyth_ema_conf, pyth_ema_publish_time, pyth_ema_half_width_bps,
    slot, pyth_err.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from soothsayer.config import DATA_RAW

# Pyth Hermes price-feed registry for the 8 xStock underliers. Each symbol has
# four session variants. IDs are stable and were enumerated 2026-04-26 against
# https://hermes.pyth.network/v2/price_feeds?asset_type=equity ; if Pyth ever
# rotates a feed ID, this dict needs to be re-derived.
PYTH_FEEDS: dict[str, dict[str, str]] = {
    "SPY": {
        "regular": "19e09bb805456ada3979a7d1cbb4b6d63babc3a0f8e8a9509f68afa5c4c11cd5",
        "on":      "05d590e94e9f51abe18ed0421bc302995673156750e914ac1600583fe2e03f99",
        "post":    "5374a7d76a45ae2443cef351d10482b7bcc6ef5a928e75030d63b5fb3abe7cb5",
        "pre":     "34f6ef70940cb9b6a37e030689612bf454f59f4a2fc5d3e03bdf2b330a088107",
    },
    "QQQ": {
        "regular": "9695e2b96ea7b3859da9ed25b7a46a920a776e2fdae19a7bcfdf2b219230452d",
        "on":      "0eda5e8f3e5881e7e64971b02359250f9d70977e63940c4c9c0d77f54195f13e",
        "post":    "e0746896538f836f754adae0aff16859b33344736cbd85f2e36fb8ca057b9d26",
        "pre":     "fbbbc98c9d0591ad0ca0b0e53ff2efb955fef8958ffa6890f5a3599e91ec1d49",
    },
    "AAPL": {
        "regular": "49f6b65cb1de6b10eaf75e7c03ca029c306d0357e91b5311b175084a5ad55688",
        "on":      "241b9a5ce1c3e4bfc68e377158328628f1b478afaa796c4b1760bd3713c2d2d2",
        "post":    "5a207c4aa0114baecf852fcd9db9beb8ec715f2db48caa525dbd878fd416fb09",
        "pre":     "8c320e4cd87c6cef41513aead15db413cf9253211923fef6e87187a7f6688906",
    },
    "GOOGL": {
        "regular": "5a48c03e9b9cb337801073ed9d166817473697efff0d138874e0f6a33d6d5aa6",
        "on":      "07d24bb76843496a45bce0add8b51555f2ea02098cb04f4c6d61f7b5720836b4",
        "post":    "88d0800b1649d98e21b8bf9c3f42ab548034d62874ad5d80e1c1b730566d7f61",
        "pre":     "43c3a42db1a663a22551d6c35d5bab823e86c1a05f27de3dd900e68952fce175",
    },
    "NVDA": {
        "regular": "b1073854ed24cbc755dc527418f52b7d271f6cc967bbf8d8129112b18860a593",
        "on":      "c949a96fd1626e82abc5e1496e6e8d44683ac8ac288015ee90bf37257e3e6bf6",
        "post":    "25719379353a508b1531945f3c466759d6efd866f52fbaeb3631decb70ba381f",
        "pre":     "61c4ca5b9731a79e285a01e24432d57d89f0ecdd4cd7828196ca8992d5eafef6",
    },
    "TSLA": {
        "regular": "16dad506d7db8da01c87581c87ca897a012a153557d4d578c3b9c9e1bc0632f1",
        "on":      "713631e41c06db404e6a5d029f3eebfd5b885c59dce4a19f337c024e26584e26",
        "post":    "2a797e196973b72447e0ab8e841d9f5706c37dc581fe66a0bd21bcd256cdb9b9",
        "pre":     "42676a595d0099c381687124805c8bb22c75424dffcaa55e3dc6549854ebe20a",
    },
    "HOOD": {
        "regular": "306736a4035846ba15a3496eed57225b64cc19230a50d14f3ed20fd7219b7849",
        "on":      "f6a467733ed71ee41f7e50132b14cff1d6857554a40d8a92c63859d1bcd64e57",
        "post":    "d2cecc2b72dc91fcc71750fbdb811b4ff04eff36e26a6ae6628dbeaed01e6d62",
        "pre":     "52ecf79ab14d988ca24fbd282a7cb91d41d36cb76aa3c9075a3eabce9ff63e2f",
    },
    "MSTR": {
        "regular": "e1e80251e5f5184f2195008382538e847fafc36f751896889dd3d1b1f6111f09",
        "on":      "c3055f49e1dc863a7f24d9b83e86fe10d7d16fb583bc6445505b01d230e0d647",
        "post":    "d8b856d7e17c467877d2d947f27b832db0d65b362ddb6f728797d46b0a8b54c0",
        "pre":     "1a11eb21c271f3127e4c9ec8a0e9b1042dc088ccba7a94a1a7d1aa37599a00f6",
    },
}

HERMES_LATEST = "https://hermes.pyth.network/v2/updates/price/latest"
POLL_INTERVAL_SECS_DEFAULT = 60
FLUSH_INTERVAL_SECS = 600


def build_id_meta() -> tuple[list[str], dict[str, tuple[str, str]]]:
    """Return (flat list of feed IDs, dict mapping id → (symbol, session))."""
    ids: list[str] = []
    meta: dict[str, tuple[str, str]] = {}
    for sym, sessions in PYTH_FEEDS.items():
        for session, fid in sessions.items():
            ids.append(fid)
            meta[fid] = (sym, session)
    return ids, meta


def fetch_hermes(ids: list[str], timeout: int = 15) -> list[dict]:
    """Single Hermes call returning the parsed price entries for all IDs."""
    params = [("ids[]", i) for i in ids]
    r = requests.get(HERMES_LATEST, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json().get("parsed", [])


def expand_row(entry: dict, meta: dict[str, tuple[str, str]], poll_ts: str,
               poll_unix: int) -> dict:
    fid = entry["id"]
    sym, session = meta[fid]
    px = entry.get("price", {})
    ema = entry.get("ema_price", {})
    md = entry.get("metadata", {})

    expo = int(px.get("expo", 0))
    scale = 10 ** expo if expo != 0 else 1.0

    price_real = float(px.get("price", 0)) * scale
    conf_real = float(px.get("conf", 0)) * scale
    pub_ts = int(px.get("publish_time", 0))
    age = poll_unix - pub_ts if pub_ts else None
    hw_bps = (conf_real / price_real) * 1e4 if price_real > 0 else None

    ema_price_real = float(ema.get("price", 0)) * scale if ema else None
    ema_conf_real = float(ema.get("conf", 0)) * scale if ema else None
    ema_pub_ts = int(ema.get("publish_time", 0)) if ema else None
    ema_hw_bps = (
        (ema_conf_real / ema_price_real) * 1e4
        if (ema_price_real and ema_price_real > 0) else None
    )

    return {
        "poll_ts": poll_ts,
        "poll_unix": poll_unix,
        "symbol": sym,
        "session": session,
        "pyth_feed_id": fid,
        "pyth_price": price_real,
        "pyth_conf": conf_real,
        "pyth_expo": expo,
        "pyth_publish_time": pub_ts,
        "pyth_age_s": age,
        "pyth_half_width_bps": hw_bps,
        "pyth_ema_price": ema_price_real,
        "pyth_ema_conf": ema_conf_real,
        "pyth_ema_publish_time": ema_pub_ts,
        "pyth_ema_half_width_bps": ema_hw_bps,
        "slot": int(md.get("slot")) if md.get("slot") is not None else None,
        "pyth_err": None,
    }


def tick(ids: list[str], meta: dict[str, tuple[str, str]]) -> list[dict]:
    poll_unix = int(time.time())
    poll_ts = datetime.fromtimestamp(poll_unix, timezone.utc).isoformat()
    try:
        parsed = fetch_hermes(ids)
    except Exception as e:  # noqa: BLE001
        # On full-batch failure, emit one error row per (symbol, session) so the
        # tape captures the outage rather than silently gapping.
        err = str(e)
        return [
            {
                "poll_ts": poll_ts, "poll_unix": poll_unix,
                "symbol": sym, "session": session, "pyth_feed_id": fid,
                "pyth_err": err,
            }
            for fid, (sym, session) in meta.items()
        ]
    return [expand_row(p, meta, poll_ts, poll_unix) for p in parsed]


def parquet_path_for(now: datetime) -> Path:
    return DATA_RAW / f"pyth_xstock_tape_{now.strftime('%Y%m%d')}.parquet"


def append_rows(buf: list[dict]) -> int:
    """Read-modify-write parquet append. At 60s cadence the overhead is fine;
    if we ever push to 1s cadence we'd switch to a pyarrow ParquetWriter.
    """
    if not buf:
        return 0
    now = datetime.now(timezone.utc)
    target = parquet_path_for(now)
    target.parent.mkdir(parents=True, exist_ok=True)
    new_df = pd.DataFrame(buf)
    if target.exists():
        existing = pd.read_parquet(target)
        out = pd.concat([existing, new_df], ignore_index=True)
    else:
        out = new_df
    out.to_parquet(target, index=False)
    return len(new_df)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true",
                    help="snapshot once and exit (cron-friendly)")
    ap.add_argument("--interval", type=int, default=POLL_INTERVAL_SECS_DEFAULT,
                    help=f"poll interval seconds (default: {POLL_INTERVAL_SECS_DEFAULT})")
    args = ap.parse_args()

    ids, meta = build_id_meta()
    print(f"Pyth Hermes tape — {len(ids)} feeds across {len(PYTH_FEEDS)} underliers")
    print(f"Sessions per symbol: {sorted(set(s for sessions in PYTH_FEEDS.values() for s in sessions))}")
    print(f"Mode: {'one-shot' if args.once else f'daemon @ {args.interval}s'}")

    if args.once:
        rows = tick(ids, meta)
        n = append_rows(rows)
        ok = [r for r in rows if r.get("pyth_err") is None]
        print(f"  fetched {len(ok)}/{len(rows)} ok rows; wrote {n} to "
              f"{parquet_path_for(datetime.now(timezone.utc)).name}")
        for sym in PYTH_FEEDS:
            for sess in ("regular", "pre", "post", "on"):
                row = next(
                    (r for r in ok if r["symbol"] == sym and r["session"] == sess),
                    None,
                )
                if row:
                    age = row.get("pyth_age_s") or 0
                    hw = row.get("pyth_half_width_bps") or 0
                    print(
                        f"    {sym:6s} {sess:8s}  ${row['pyth_price']:>8.2f}  "
                        f"conf=${row['pyth_conf']:>6.2f}  hw={hw:>7.1f}bps  age={age}s"
                    )
        return

    buf: list[dict] = []
    last_flush = time.time()
    print(f"Daemon started; flushing every {FLUSH_INTERVAL_SECS}s. Ctrl-C to stop.")
    while True:
        try:
            rows = tick(ids, meta)
            buf.extend(rows)
            now_iso = datetime.now(timezone.utc).isoformat()
            print(f"  [{now_iso}] buffered +{len(rows)} (total {len(buf)})")
            if time.time() - last_flush >= FLUSH_INTERVAL_SECS:
                n = append_rows(buf)
                print(f"  ⇒ flushed {n} rows to {parquet_path_for(datetime.now(timezone.utc)).name}")
                buf.clear()
                last_flush = time.time()
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nInterrupted; flushing buffer before exit...")
            n = append_rows(buf)
            print(f"  flushed {n} rows; exiting.")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  [tick error] {e}; backing off 30s")
            time.sleep(30)


if __name__ == "__main__":
    main()
