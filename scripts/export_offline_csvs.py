"""One-shot: export CSVs of V1/V2/V3 core data for offline Excel work.

Reads only local parquets; no network. Writes to docs/offline-guide/data/.
"""
from __future__ import annotations

import glob
from datetime import UTC, datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

OUT = Path("docs/offline-guide/data")
OUT.mkdir(parents=True, exist_ok=True)
ET = ZoneInfo("America/New_York")

# ---------- V1 ----------
v1 = pd.read_parquet("data/processed/v1_chainlink_vs_monday_open.parquet")
keep = [
    "weekend_mon", "fri_ts", "gap_days", "symbol", "underlying",
    "fri_close", "mon_open", "cl_mid", "cl_minutes_before_open",
]
v1[keep].sort_values(["weekend_mon", "symbol"]).to_csv(OUT / "v1_weekend_pairs.csv", index=False)
print("V1:", len(v1), "rows ->", OUT / "v1_weekend_pairs.csv")

# ---------- Separate yahoo minute vs daily parquets ----------
minute_frames, daily_frames = [], []
for f in sorted(glob.glob("data/raw/yahoo_*.parquet")):
    d = pd.read_parquet(f)
    if "ts" not in d.columns:
        continue
    # Heuristic: daily bars land at 00:00 UTC; minute bars don't.
    ts = pd.to_datetime(d["ts"], utc=True, errors="coerce")
    is_midnight = ((ts.dt.hour == 0) & (ts.dt.minute == 0)).mean()
    if is_midnight > 0.9:
        daily_frames.append(d)
    else:
        minute_frames.append(d)

mins = (
    pd.concat(minute_frames, ignore_index=True)
      .drop_duplicates(["symbol", "ts"])
      .sort_values(["symbol", "ts"])
) if minute_frames else pd.DataFrame()
daily = (
    pd.concat(daily_frames, ignore_index=True)
      .drop_duplicates(["symbol", "ts"])
      .sort_values(["symbol", "ts"])
) if daily_frames else pd.DataFrame()

# ---------- V2: SPY 1-min RTH, one representative day + one-week sample ----------
if len(mins):
    spy = mins[mins["symbol"] == "SPY"][["ts", "open", "high", "low", "close", "volume"]].copy()
    spy["ts_utc"] = pd.to_datetime(spy["ts"], utc=True)
    spy["ts_et"] = spy["ts_utc"].dt.tz_convert(ET)
    spy = spy[
        ((spy["ts_et"].dt.hour > 9) | ((spy["ts_et"].dt.hour == 9) & (spy["ts_et"].dt.minute >= 30)))
        & (spy["ts_et"].dt.hour < 16)
    ]
    spy["date_et"] = spy["ts_et"].dt.date
    by_day = spy.groupby("date_et").size().reset_index(name="n").sort_values("date_et")
    full_days = by_day[by_day["n"] >= 370]
    if len(full_days):
        target_day = full_days.iloc[-1]["date_et"]
        spy_day = spy[spy["date_et"] == target_day][["ts_et", "open", "high", "low", "close", "volume"]].copy()
        spy_day["ts_et"] = spy_day["ts_et"].dt.strftime("%Y-%m-%d %H:%M")
        spy_day.to_csv(OUT / "v2_spy_1min_oneday.csv", index=False)
        print("V2 one-day SPY:", target_day, len(spy_day), "rows")

        # 5-day sample
        last5 = full_days.tail(5)["date_et"].tolist()
        spy_week = spy[spy["date_et"].isin(last5)][["ts_et", "date_et", "open", "high", "low", "close", "volume"]].copy()
        spy_week["ts_et"] = spy_week["ts_et"].dt.strftime("%Y-%m-%d %H:%M")
        spy_week.to_csv(OUT / "v2_spy_1min_week.csv", index=False)
        print("V2 5-day SPY:", len(spy_week), "rows")

# ---------- V3: assemble (weekend, ticker) regression rows ----------
kraken = pd.concat(
    [pd.read_parquet(f) for f in sorted(glob.glob("data/raw/kraken_funding_*.parquet"))],
    ignore_index=True,
).drop_duplicates(["symbol", "ts"]).sort_values(["symbol", "ts"])
print("Kraken funding rows:", len(kraken))

if len(daily):
    d = daily.copy()
    d["ts"] = pd.to_datetime(d["ts"]).dt.date
    daily_out = d.copy()
    daily_out.to_csv(OUT / "v3_daily_bars.csv", index=False)

    fri_close = d.set_index(["symbol", "ts"])["close"].to_dict()
    mon_open = d.set_index(["symbol", "ts"])["open"].to_dict()

    spy_d = d[d["symbol"] == "SPY"].sort_values("ts").reset_index(drop=True)
    dates = spy_d["ts"].tolist()
    pairs = []
    for i in range(1, len(dates)):
        prev, curr = dates[i - 1], dates[i]
        if (curr - prev).days >= 3:
            pairs.append({"fri_ts": prev, "mon_ts": curr, "gap_days": (curr - prev).days})
    pairs = pd.DataFrame(pairs)

    xlk = d[d["symbol"] == "XLK"].sort_values("ts").reset_index(drop=True).copy()
    xlk["prev_close"] = xlk["close"].shift(1)
    xlk["r_fri"] = np.log(xlk["close"] / xlk["prev_close"])
    xlk_fri = dict(zip(xlk["ts"], xlk["r_fri"]))

    kr = kraken.copy()
    kr["ts"] = pd.to_datetime(kr["ts"], utc=True)

    def fsun(underlying: str, mon_d) -> float | None:
        perp = f"PF_{underlying.upper()}XUSD"
        target = (
            datetime.combine(mon_d, dt_time(9, 30), tzinfo=ET).astimezone(UTC)
            + timedelta(hours=-14, minutes=-30)
        ).replace(minute=0, second=0, microsecond=0)
        sub = kr[(kr["symbol"] == perp) & (kr["ts"] == pd.Timestamp(target))]
        if not sub.empty:
            return float(sub["funding_rate"].iloc[0])
        return None

    tickers = ["SPY", "QQQ", "GOOGL", "AAPL", "NVDA", "TSLA", "MSTR", "HOOD"]
    rows = []
    for _, r in pairs.iterrows():
        fd, md = r["fri_ts"], r["mon_ts"]
        btc_fri = fri_close.get(("BTC-USD", fd))
        btc_mon = mon_open.get(("BTC-USD", md))
        es_fri = fri_close.get(("ES=F", fd))
        es_mon = mon_open.get(("ES=F", md))
        r_xlk = xlk_fri.get(fd)
        if None in (btc_fri, btc_mon, es_fri, es_mon):
            continue
        if any(pd.isna(v) for v in (btc_fri, btc_mon, es_fri, es_mon, r_xlk)):
            continue
        r_btc = float(np.log(btc_mon / btc_fri))
        r_es = float(np.log(es_mon / es_fri))
        for t in tickers:
            uf = fri_close.get((t, fd))
            um = mon_open.get((t, md))
            if uf is None or um is None or pd.isna(uf) or pd.isna(um):
                continue
            g_T = float(np.log(um / uf))
            f_sun = fsun(t, md)
            rows.append({
                "weekend_mon": md, "ticker": t, "g_T": g_T, "r_btc": r_btc,
                "r_es": r_es, "r_xlk_fri": float(r_xlk), "funding_sun": f_sun,
            })
    v3df = pd.DataFrame(rows)
    v3df.to_csv(OUT / "v3_regression_rows.csv", index=False)
    n_with = int(v3df["funding_sun"].notna().sum())
    print(f"V3: {len(v3df)} rows ({n_with} with funding) -> v3_regression_rows.csv")

kraken_out = kraken.copy()
kraken_out["ts"] = pd.to_datetime(kraken_out["ts"]).dt.strftime("%Y-%m-%d %H:%M:%S")
kraken_out.to_csv(OUT / "v3_kraken_funding.csv", index=False)
print("Kraken funding ->", OUT / "v3_kraken_funding.csv")

print("\nAll exports in", OUT.resolve())
for p in sorted(OUT.glob("*.csv")):
    print(" ", p.name, p.stat().st_size, "bytes")
