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

from soothsayer.chainlink.scraper import (
    fetch_latest_per_xstock,
    iter_xstock_reports_rpc,
)


def fmt_ts(ts: int | float | None) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(int(ts), UTC).strftime("%Y-%m-%d %a %H:%M:%S UTC")


def main() -> None:
    now = int(time.time())
    print(f"now: {fmt_ts(now)}")
    print()

    print("=" * 60)
    print("Pass 1: latest SPYx observation in the last 12h")
    print("=" * 60)
    t0 = time.monotonic()
    latest = fetch_latest_per_xstock(
        now,
        lookback_hours=12,
        target_symbols={"SPYx"},
        use_rpc=True,
        verbose=True,
    )
    t1 = time.monotonic()
    print(f"\npass 1 took {t1 - t0:.1f}s")

    if not latest or "SPYx" not in latest:
        print("\n✗ NO SPYx observations found in the last 12h.")
        print("  This is consistent with outcome (3): Chainlink stops publishing on weekends.")
        print("  Try expanding lookback to confirm last observation was Friday close.")
        return

    obs = latest["SPYx"]
    print()
    print("Latest SPYx observation:")
    print(f"  obs_ts             : {fmt_ts(obs['obs_ts'])}")
    print(f"  tx_block_time      : {fmt_ts(obs['tx_block_time'])}")
    print(f"  last_update_ts_ns  : {fmt_ts(obs['last_update_ts_ns'] / 1e9)}")
    print(f"  price (w7)         : {obs['price']:.4f}")
    print(f"  tokenized_price    : {obs['tokenized_price']:.4f}")
    print(f"  market_status      : {obs['market_status']} (0=Unknown, 1=Closed, 2=Open)")
    print(f"  current_multiplier : {obs['current_multiplier']}")
    print()

    obs_dt = datetime.fromtimestamp(obs["obs_ts"], UTC)
    block_dt = datetime.fromtimestamp(obs["tx_block_time"], UTC)
    today = datetime.now(UTC).date()
    is_today = obs_dt.date() == today or block_dt.date() == today

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
    t0 = time.monotonic()
    obs_list = []
    for o in iter_xstock_reports_rpc(now - 4 * 3600, now, verbose=True):
        if o["symbol"] == "SPYx":
            obs_list.append(o)
    t1 = time.monotonic()
    print(f"\npass 2 took {t1 - t0:.1f}s, found {len(obs_list)} SPYx observations")

    if not obs_list:
        print("  no observations in last 4h — try expanding window")
        return

    obs_list.sort(key=lambda o: o["obs_ts"])
    prices = sorted({round(o["price"], 4) for o in obs_list})
    tok_prices = sorted({round(o["tokenized_price"], 4) for o in obs_list})

    print()
    print(f"Distinct price (w7) values     : {len(prices)} → {prices[:8]}{'...' if len(prices) > 8 else ''}")
    print(f"Distinct tokenized_price values: {len(tok_prices)} → {tok_prices[:8]}{'...' if len(tok_prices) > 8 else ''}")
    print()
    print("First and last observation in window:")
    for label, o in [("first", obs_list[0]), ("last", obs_list[-1])]:
        print(f"  {label}: obs_ts={fmt_ts(o['obs_ts'])} "
              f"price={o['price']:.4f} tok={o['tokenized_price']:.4f} "
              f"mkt={o['market_status']}")

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
