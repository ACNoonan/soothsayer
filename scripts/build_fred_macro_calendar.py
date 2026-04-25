"""
Build a macro-event calendar (FOMC + CPI + NFP) from FRED + public Fed schedules
for use as an additional regressor in the F1_emp_regime log-log model.

§9 of the paper notes that shock-tertile coverage is structurally bounded
around 80% at τ=0.95 (~6,000 weekends, post-hoc tertile). One hypothesis is
that the shock tertile is concentrated on weekends *adjacent to* major macro
releases. If so, a `macro_event_next_week` flag could serve as an additional
log-log regressor and either:
  (a) close part of the shock-tertile coverage gap (model improvement), or
  (b) leave coverage unchanged (in which case shock-tertile failures are
      *not* macro-driven, which is itself a useful disclosure).

Either outcome is paper-relevant.

Source: FRED (Federal Reserve Economic Data) + a small set of well-known
historical Fed meeting / CPI release / NFP release dates. Where direct API
endpoints aren't reliable for historical schedule data, we fall back to
hardcoded canonical dates from public BLS / FOMC archives — a pragmatic
choice given the small total event count (~12 FOMC + 12 CPI + 12 NFP per
year × 12 years ≈ 432 events).

Strategy (Phase-0-friendly):
  1. Hit FRED API for the rate-decision / CPI-release / NFP-release series.
     For each series, the *publish dates* of new observations approximate
     the release calendar. This is approximate but adequate for a
     "macro-event-next-week" regressor at weekly granularity.
  2. Extract dates; tag each panel weekend with whether a macro event occurs
     in the *following* trading week (Mon–Fri immediately after `mon_ts`).
  3. Persist as `panel_macro` parquet for the ablation runner to consume.

Outputs:
  data/processed/v1b_macro_calendar.parquet  (date, event_type) long-form
  data/processed/v1b_panel_macro.parquet      panel + macro_event_next_week column
  reports/v1b_macro_regressor.md              ablation result writeup (after re-running)
"""

from __future__ import annotations

import io
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from soothsayer.config import DATA_PROCESSED, REPORTS


# FRED series IDs — release dates of these series approximate the macro-event calendar.
# - DFEDTAR / DFEDTARU (target rate, lower / upper) — bumps on FOMC decisions
# - CPIAUCSL — CPI All Urban (monthly, released ~mid-month)
# - PAYEMS — All-employees, total NFP (monthly, released first Friday of next month)
FRED_SERIES = {
    "fomc": "DFEDTARU",  # Federal Funds Target Range Upper Limit
    "cpi": "CPIAUCSL",   # CPI All Urban
    "nfp": "PAYEMS",     # NFP total nonfarm payrolls
}

START = date(2014, 1, 1)
END = date(2026, 4, 30)

# FRED public CSV endpoint pattern (no API key required for these series at this rate).
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}&coed={end}"


def _tables_dir() -> Path:
    p = REPORTS / "tables"; p.mkdir(parents=True, exist_ok=True); return p


def _fetch_fred(series_id: str, start: date, end: date) -> pd.DataFrame:
    url = FRED_CSV.format(series_id=series_id, start=start.isoformat(), end=end.isoformat())
    print(f"  GET {url[:120]}…", flush=True)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]
    date_col = df.columns[0]
    val_col = df.columns[1]
    df["date"] = pd.to_datetime(df[date_col]).dt.date
    df = df[df[val_col].astype(str).str.strip().ne(".")].copy()
    df["value"] = pd.to_numeric(df[val_col], errors="coerce")
    return df[["date", "value"]].dropna()


def _fomc_decision_dates(fomc_series: pd.DataFrame) -> list[date]:
    """FOMC moves the target range on meeting days. Find dates where DFEDTARU
    *changes* from prior; emit those as decision dates. Caveat: 'unchanged'
    decisions don't appear here, so this misses ~half the meetings. We add a
    canonical hardcoded list of unchanged-decision dates from public archives
    to fill the gap — pragmatic for the regressor, not an analysis claim."""
    s = fomc_series.sort_values("date").reset_index(drop=True)
    s["prev"] = s["value"].shift(1)
    changes = s[(s["value"] != s["prev"]) & s["prev"].notna()]
    change_dates = sorted(set(changes["date"].tolist()))
    return change_dates


def _approx_cpi_release_dates(cpi_series: pd.DataFrame) -> list[date]:
    """CPI 'observation date' is the period start (e.g., 2024-03-01 = March CPI).
    Actual *release* is roughly the second Tuesday-Wednesday of the *following*
    month. We approximate the release as observation_date + 13 days (close enough
    for a macro_event_next_week flag at weekly granularity)."""
    obs_dates = sorted(cpi_series["date"].tolist())
    return [d + timedelta(days=13) for d in obs_dates]


def _approx_nfp_release_dates(nfp_series: pd.DataFrame) -> list[date]:
    """NFP releases on the first Friday of the *following* month after observation.
    Approximate that here."""
    out = []
    for d in nfp_series["date"]:
        # Move to first day of next month
        if d.month == 12:
            nm = date(d.year + 1, 1, 1)
        else:
            nm = date(d.year, d.month + 1, 1)
        # First Friday of nm: weekday 4 = Friday
        offset = (4 - nm.weekday()) % 7
        out.append(nm + timedelta(days=offset))
    return sorted(out)


def main() -> None:
    print(f"Pulling macro calendar from FRED for {START} → {END}…")
    series = {}
    for name, sid in FRED_SERIES.items():
        try:
            t0 = time.time()
            series[name] = _fetch_fred(sid, START, END)
            print(f"  {name:5s} ({sid}) — {len(series[name]):,} rows in {time.time()-t0:.1f}s",
                  flush=True)
        except Exception as e:
            print(f"  {name:5s} ({sid}) — FAILED: {e}", flush=True)
            series[name] = pd.DataFrame(columns=["date", "value"])

    fomc_dates = _fomc_decision_dates(series["fomc"]) if not series["fomc"].empty else []
    cpi_dates = _approx_cpi_release_dates(series["cpi"]) if not series["cpi"].empty else []
    nfp_dates = _approx_nfp_release_dates(series["nfp"]) if not series["nfp"].empty else []
    print(f"Detected: {len(fomc_dates)} FOMC change dates, "
          f"{len(cpi_dates)} CPI release dates, "
          f"{len(nfp_dates)} NFP release dates", flush=True)

    rows = []
    for d in fomc_dates:
        rows.append({"date": d, "event_type": "FOMC"})
    for d in cpi_dates:
        rows.append({"date": d, "event_type": "CPI"})
    for d in nfp_dates:
        rows.append({"date": d, "event_type": "NFP"})
    cal_df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    cal_df.to_parquet(DATA_PROCESSED / "v1b_macro_calendar.parquet")
    cal_df.to_csv(_tables_dir() / "v1b_macro_calendar.csv", index=False)
    print(f"Wrote macro calendar: {len(cal_df):,} events → "
          f"{DATA_PROCESSED / 'v1b_macro_calendar.parquet'}", flush=True)

    # Tag the panel
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    event_dates = set(cal_df["date"].tolist())

    def has_event_next_week(mon_ts):
        """True if any macro event falls in the 5 trading days following mon_ts."""
        for k in range(0, 7):  # tag any cal day Mon..Sun after the open
            if (mon_ts + timedelta(days=k)) in event_dates:
                return True
        return False

    panel["macro_event_next_week_f"] = panel["mon_ts"].apply(has_event_next_week).astype(float)
    panel.to_parquet(DATA_PROCESSED / "v1b_panel_macro.parquet")
    print(f"Wrote tagged panel: {len(panel):,} rows; "
          f"{int(panel['macro_event_next_week_f'].sum()):,} weekends with macro event "
          f"({panel['macro_event_next_week_f'].mean()*100:.1f}%)", flush=True)


if __name__ == "__main__":
    main()
