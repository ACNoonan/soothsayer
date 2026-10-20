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
            if fri not in y.index or not (start <= fri <= end):
                continue
            # Monday's bar may not have settled yet; the restart check doesn't need it.
            c = y.loc[fri, "close"]
            o = y.loc[mon, "open"] if mon in y.index else float("nan")
            rows.append({"weekend": b.weekend_date, "ticker": sym, "fri_close": c, "mon_open": o,
                         "wkd_ret": o / c - 1, "band_lo": b.lower, "band_hi": b.upper,
                         "in_band": (b.lower <= o <= b.upper) if o == o else None,
                         "provenance": b.provenance})
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
    b = df.dropna(subset=["mon_open"]).astype({"in_band": bool}, errors="ignore")
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
    r = df.dropna(subset=["band_lo"]).copy()
    if not r.empty:
        # The feed's frozen price must be Yahoo's Friday close in the same units, or the band
        # (built on Yahoo prices) can't be compared with the feed's restart price. A share
        # multiplier would show as a gap of tens of percent; a frozen round printed after hours
        # legitimately drifts about 1%, so the tolerance is 5%.
        r["frozen_vs_close"] = r.frozen_price / r.fri_close - 1
        r["restart_in_band"] = (r.band_lo <= r.resume_price) & (r.resume_price <= r.band_hi)
        r["restart_pos"] = (r.resume_price - (r.band_lo + r.band_hi) / 2) / ((r.band_hi - r.band_lo) / 2)
        r["open_pos"] = (r.mon_open - (r.band_lo + r.band_hi) / 2) / ((r.band_hi - r.band_lo) / 2)
        ok = r.frozen_vs_close.abs() < 0.05
        g = r[ok]
        both = g.dropna(subset=["mon_open"])
        lines += [
            "",
            "## Sunday 8pm ET restart vs Soothsayer's 95% band",
            "",
            f"Unit check: the feed's frozen price sits within 5% of Yahoo's Friday close on "
            f"{int(ok.sum())}/{len(r)} symbol-weekends (median gap "
            f"{r.frozen_vs_close.abs().median()*1e4:.1f} bps, max {r.frozen_vs_close.abs().max()*1e4:.0f} bps, "
            f"the largest from rounds printed after hours). Rows that fail it are dropped below.",
            "",
            f"The restart price (first feed round at or after Mon 00:00 UTC) was inside the 95% band on "
            f"{int(g.restart_in_band.sum())}/{len(g)} symbol-weekends ({g.restart_in_band.mean():.1%}). "
            f"Position in the band, as a fraction of its half-width (0 = centre, ±1 = edge): "
            f"restart median |pos| {g.restart_pos.abs().median():.2f}, max {g.restart_pos.abs().max():.2f}; "
            f"on the {len(both)} rows with a settled Monday bar, Monday open median |pos| "
            f"{both.open_pos.abs().median():.2f} vs restart {both.restart_pos.abs().median():.2f}.",
            "",
            "| weekend | ticker | Fri close | frozen | restart | Mon open | band 95% | restart pos | open pos | restart in band |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for _, x in g.reindex(g.restart_pos.abs().sort_values(ascending=False).index).iterrows():
            lines.append(f"| {x.weekend} | {x.ticker} | {x.fri_close:.2f} | {x.frozen_price:.2f} | "
                         f"{x.resume_price:.2f} | {x.mon_open:.2f} | {x.band_lo:.2f}–{x.band_hi:.2f} | "
                         f"{x.restart_pos:+.2f} | {x.open_pos:+.2f} | {'yes' if x.restart_in_band else 'NO'} |")
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
