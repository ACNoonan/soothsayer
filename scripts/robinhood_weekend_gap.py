"""Weekend freeze of the Robinhood Chain Chainlink stock feeds.

For each feed and each weekend in the window, find the last round before
Saturday 00:00 UTC (the price a lending market reads all weekend) and the
first round after it (the Sunday-evening resume), and measure:

  gap_h        hours between the two rounds
  pre_close_h  hours before Friday's 16:00 ET close that the frozen round printed
  resume_ret   first resumed print / frozen print − 1

For the symbols Soothsayer bands (SPY QQQ AAPL GOOGL NVDA TSLA MSTR) it also
joins Yahoo's Friday close and Monday open and the archived band, to show how
far Monday's open moved from Friday and whether the band held it.

Reads scryer parquet only (``oracle.chainlink_feeds.round.v2``, ``yahoo.v1``)
and ``data/band_archive/bands_v1.csv``.

    uv run python scripts/robinhood_weekend_gap.py --start 2026-09-11 --end 2026-10-16 \\
        --out internal/active/robinhood-weekend-gap.md
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from soothsayer.sources.scryer import load_chainlink_feed_rounds, load_yahoo_bars

ET = ZoneInfo("America/New_York")
BANDED = ["SPY", "QQQ", "AAPL", "GOOGL", "NVDA", "TSLA", "MSTR"]
USDG_PROXY = "0x61b7e5650328764b076a108eff5fa7282a1b9ad2"
REPO = Path(__file__).resolve().parents[1]


def ticker(description: str) -> str:
    """'RHNVDA / USD', 'Robinhood NVDA / USD', 'Robinhood DELL-USD' -> 'NVDA'."""
    s = description.replace("Robinhood ", "").split("/")[0].split("-USD")[0].strip()
    return s[2:] if s.startswith("RH") and s[2:].isupper() and len(s) > 2 else s


def fridays(start: date, end: date) -> list[date]:
    d = start + timedelta(days=(4 - start.weekday()) % 7)
    out = []
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


def weekend_rows(rounds: pd.DataFrame, fri: date) -> list[dict]:
    sat0 = int(datetime.combine(fri + timedelta(days=1), time(0), timezone.utc).timestamp())
    close = int(datetime.combine(fri, time(16), ET).timestamp())
    out = []
    for proxy, g in rounds.groupby("feed_proxy"):
        g = g.sort_values("updated_at")
        before, after = g[g.updated_at < sat0], g[g.updated_at >= sat0]
        if before.empty or after.empty:
            continue
        f, r = before.iloc[-1], after.iloc[0]
        out.append({
            "weekend": fri.isoformat(),
            "ticker": ticker(f.feed_description),
            "feed_proxy": proxy,
            "frozen_utc": datetime.fromtimestamp(int(f.updated_at), timezone.utc).strftime("%a %H:%M"),
            "resume_utc": datetime.fromtimestamp(int(r.updated_at), timezone.utc).strftime("%a %H:%M"),
            "gap_h": (r.updated_at - f.updated_at) / 3600,
            "pre_close_h": (close - f.updated_at) / 3600,
            "frozen_price": f.price,
            "resume_price": r.price,
            "resume_ret": r.price / f.price - 1,
        })
    return out


def band_join(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    bands = pd.read_csv(REPO / "data/band_archive/bands_v1.csv")
    bands = bands[bands.tau == 0.95][["weekend_date", "mon_date", "symbol", "lower", "upper", "provenance"]]
    rows = []
    for sym in BANDED:
        y = load_yahoo_bars(sym, start, end + timedelta(days=7))
        if y.empty:
            continue
        y = y.assign(d=pd.to_datetime(y.ts).dt.date).set_index("d")
        for _, b in bands[bands.symbol == sym].iterrows():
            fri, mon = date.fromisoformat(b.weekend_date), date.fromisoformat(b.mon_date)
            if fri not in y.index or mon not in y.index or not (start <= fri <= end):
                continue
            c, o = y.loc[fri, "close"], y.loc[mon, "open"]
            rows.append({"weekend": b.weekend_date, "ticker": sym, "fri_close": c, "mon_open": o,
                         "wkd_ret": o / c - 1, "band_lo": b.lower, "band_hi": b.upper,
                         "in_band": b.lower <= o <= b.upper, "provenance": b.provenance})
    cols = ["weekend", "ticker", "fri_close", "mon_open", "wkd_ret", "band_lo", "band_hi", "in_band", "provenance"]
    return df.merge(pd.DataFrame(rows, columns=cols), on=["weekend", "ticker"], how="left")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="first Friday (YYYY-MM-DD)")
    ap.add_argument("--end", required=True, help="last Friday (YYYY-MM-DD)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)

    rounds = load_chainlink_feed_rounds(start - timedelta(days=3), end + timedelta(days=4))
    rounds = rounds[rounds.feed_proxy != USDG_PROXY]
    rows = [r for fri in fridays(start, end) for r in weekend_rows(rounds, fri)]
    df = band_join(pd.DataFrame(rows), start, end)
    out = Path(a.out)
    df.to_csv(out.with_suffix(".csv"), index=False)

    n_w, n_f = df.weekend.nunique(), df.feed_proxy.nunique()
    q = lambda s, p: s.quantile(p)  # noqa: E731
    absr = df.resume_ret.abs() * 1e4
    lines = [
        f"# Robinhood Chain stock feeds: weekend freeze, {a.start} to {a.end}",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/robinhood_weekend_gap.py`. "
        f"{n_w} weekends × {n_f} feeds = {len(df)} feed-weekends. Source: `oracle.chainlink_feeds.round.v2`.",
        "",
        "## Freeze length and resume jump",
        "",
        "| | median | p90 | max |",
        "|---|---|---|---|",
        f"| hours frozen (last Friday round → first resumed round) | {q(df.gap_h,.5):.1f} | {q(df.gap_h,.9):.1f} | {df.gap_h.max():.1f} |",
        f"| hours before Friday 16:00 ET the frozen round printed (negative = after-hours) | {q(df.pre_close_h,.5):.1f} | {q(df.pre_close_h,.9):.1f} | {df.pre_close_h.max():.1f} |",
        f"| abs resume jump, bps | {q(absr,.5):.0f} | {q(absr,.9):.0f} | {absr.max():.0f} |",
        "",
        "## Largest resume jumps",
        "",
        "| weekend | ticker | frozen (UTC) | resumed (UTC) | hours | frozen | resumed | jump |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, r in df.reindex(df.resume_ret.abs().sort_values(ascending=False).index).head(12).iterrows():
        lines.append(f"| {r.weekend} | {r.ticker} | {r.frozen_utc} | {r.resume_utc} | {r.gap_h:.1f} | "
                     f"{r.frozen_price:.2f} | {r.resume_price:.2f} | {r.resume_ret*100:+.2f}% |")
    b = df.dropna(subset=["mon_open"])
    if not b.empty:
        lines += [
            "",
            "## Banded symbols: Friday close → Monday open vs Soothsayer's 95% band",
            "",
            f"{len(b)} symbol-weekends ({', '.join(sorted(b.ticker.unique()))}). "
            f"Monday's open was inside the 95% band {b.in_band.mean():.1%} of the time "
            f"({int(b.in_band.sum())}/{len(b)}). Provenance: {', '.join(sorted(b.provenance.unique()))}.",
            "",
            "| weekend | ticker | Fri close | Mon open | move | band 95% | in band |",
            "|---|---|---|---|---|---|---|",
        ]
        for _, r in b.reindex(b.wkd_ret.abs().sort_values(ascending=False).index).head(10).iterrows():
            lines.append(f"| {r.weekend} | {r.ticker} | {r.fri_close:.2f} | {r.mon_open:.2f} | "
                         f"{r.wkd_ret*100:+.2f}% | {r.band_lo:.2f}–{r.band_hi:.2f} | {'yes' if r.in_band else 'NO'} |")
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
