"""
One-shot verification: does Chainlink Data Streams v10 publish during weekends?

Today is Saturday 2026-04-25. Three possible outcomes:
  (1) Latest obs from today AND tokenized_price ≠ Friday close → v10 updates weekends
  (2) Latest obs from today AND tokenized_price == Friday close → publishes but tokenized_price is stale
  (3) Latest obs from Friday → fully stops publishing on weekends

Tests SPYx specifically (single feed = fast). Run unbuffered for live progress:
    PYTHONUNBUFFERED=1 uv run python scripts/check_chainlink_weekend.py
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pandas as pd

from soothsayer.sources.scryer import load_v5_window


def fmt_ts(ts: int | float | None) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(int(ts), UTC).strftime("%Y-%m-%d %a %H:%M:%S UTC")


def main() -> None:
    now = int(time.time())
    print(f"now: {fmt_ts(now)}")
    print()

    start = datetime.fromtimestamp(now - 12 * 3600, UTC).date()
    end = datetime.fromtimestamp(now, UTC).date()
    tape = load_v5_window(start, end)
    tape = tape[tape["symbol"] == "SPYx"].copy()
    if tape.empty:
        print("✗ No SPYx rows found in scryer soothsayer_v5 tape for the last 12h window.")
        return
    tape["poll_ts"] = pd.to_numeric(tape["poll_ts"], errors="coerce")
    tape = tape[tape["poll_ts"].notna()].sort_values("poll_ts").reset_index(drop=True)
    tape["poll_ts"] = tape["poll_ts"].astype(int)
    tape_12h = tape[tape["poll_ts"] >= now - 12 * 3600].copy()

    print("=" * 60)
    print("Pass 1: latest SPYx observation in the last 12h")
    print("=" * 60)
    if tape_12h.empty:
        print("\n✗ NO SPYx observations found in the last 12h.")
        print("  This is consistent with outcome (3): Chainlink stops publishing on weekends.")
        return

    obs = tape_12h.iloc[-1]
    print()
    print("Latest SPYx observation:")
    print(f"  poll_ts            : {fmt_ts(obs['poll_ts'])}")
    print(f"  price (w7)         : {obs['cl_venue_px']:.4f}")
    print(f"  tokenized_price    : {obs['cl_tokenized_px']:.4f}")
    print(f"  market_status      : {obs['cl_market_status']}")
    print()

    obs_dt = datetime.fromtimestamp(int(obs["poll_ts"]), UTC)
    today = datetime.now(UTC).date()
    is_today = obs_dt.date() == today

    print("Pre-pass-2 verdict:")
    if is_today:
        print(f"  ✓ Latest observation is from TODAY ({today.isoformat()}). "
              "Chainlink IS publishing on weekends.")
        print(f"  → Pass 2 will check whether tokenized_price evolves.")
    else:
        print(f"  ✗ Latest observation is from {obs_dt.date().isoformat()} (NOT today).")
        print("  → This points to outcome (3): Chainlink does not publish on weekends.")
        print("  → Skipping Pass 2.")
        return

    print()
    print("=" * 60)
    print("Pass 2: collect all SPYx observations in the last 4h")
    print("=" * 60)
    obs_list = tape[(tape["poll_ts"] >= now - 4 * 3600) & (tape["poll_ts"] <= now)].to_dict(orient="records")
    print(f"\nfound {len(obs_list)} SPYx observations")

    if not obs_list:
        print("  no observations in last 4h — try expanding window")
        return

    obs_list.sort(key=lambda o: o["poll_ts"])
    prices = sorted({round(float(o["cl_venue_px"]), 4) for o in obs_list})
    tok_prices = sorted({round(float(o["cl_tokenized_px"]), 4) for o in obs_list})

    print()
    print(f"Distinct price (w7) values     : {len(prices)} → {prices[:8]}{'...' if len(prices) > 8 else ''}")
    print(f"Distinct tokenized_price values: {len(tok_prices)} → {tok_prices[:8]}{'...' if len(tok_prices) > 8 else ''}")
    print()
    print("First and last observation in window:")
    for label, o in [("first", obs_list[0]), ("last", obs_list[-1])]:
        print(f"  {label}: poll_ts={fmt_ts(o['poll_ts'])} "
              f"price={o['cl_venue_px']:.4f} tok={o['cl_tokenized_px']:.4f} "
              f"mkt={o['cl_market_status']}")

    print()
    print("=" * 60)
    print("Verdict")
    print("=" * 60)
    if len(tok_prices) > 1:
        print("✓ tokenized_price EVOLVED across the 4h window.")
        print("  → Outcome (1): v10 updates tokenized_price on weekends.")
        print("  → plan-b's '24/7 CEX mark, updates weekends' claim has support.")
    elif len(prices) > 1:
        print("⚠ price (w7) evolved but tokenized_price did NOT.")
        print("  Surprising — suggests tokenized_price is stale while price isn't.")
    else:
        print("✗ Both price AND tokenized_price are FROZEN across the 4h window.")
        print("  → Outcome (2): Chainlink publishes heartbeat reports on weekends, but the")
        print("    payload is stale. The 'updates weekends' claim in v10.py is wrong.")


if __name__ == "__main__":
    main()
