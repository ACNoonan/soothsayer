"""
RedStone incumbent-comparison benchmark — W1 deliverable for the validation backlog.

Question. RedStone publishes a point price (no published confidence band).
*If a downstream protocol wants a calibrated band on top of the RedStone
point, what symmetric ±k% wrap delivers τ-coverage of the realised
Friday-close → Monday-open gap?* This is the matched comparison to
Soothsayer's served band, framed in the same coverage-inversion language.

Sample window. RedStone scryer capture began 2026-04-26 (forward-cursor
gateway poll, see `reference_redstone_gateway.md`). Symbol set on tape:
SPY, QQQ, MSTR (underlier tickers, not xStocks). Pre-2026-04-26 weekends
have no RedStone data; weekends where Yahoo's Monday open hasn't yet
landed are deferred. The script reports n explicitly and degrades
gracefully when the panel is empty.

Procedure (mirrors `scripts/pyth_benchmark_comparison.py`):
  1. Build the comparison panel from scryer Yahoo bars: every (symbol,
     fri_ts, mon_ts, fri_close, mon_open) where fri_ts is a regular
     Friday close, mon_ts is the next regular trading day's open, and
     both rows exist on disk.
  2. For each (symbol, fri_ts), find the latest RedStone tape row with
     `redstone_ts ≤ fri_close_cutoff` (Friday 16:00 ET → UTC, DST-aware,
     2-hour lookback to handle the gateway's 10-min cron cadence).
  3. For each k_pct in K_PCT_GRID, compute the symmetric band
     [redstone_value · (1 - k_pct), redstone_value · (1 + k_pct)] and
     check whether mon_open is inside.
  4. Aggregate to pooled and per-symbol coverage rates.

Outputs:
  data/processed/redstone_benchmark_oos.parquet     per-row RedStone obs
  reports/tables/redstone_coverage_by_k_pct.csv     per-(k_pct, scope) coverage
  reports/v1b_redstone_comparison.md                paper-ready writeup

Run unbuffered for live progress:
    PYTHONUNBUFFERED=1 .venv/bin/python scripts/redstone_benchmark_comparison.py
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.sources.scryer import load_redstone_window, load_yahoo_bars

REDSTONE_SYMBOLS = ("SPY", "QQQ", "MSTR")
EASTERN = ZoneInfo("America/New_York")
LOOKBACK_SECS = 7_200
K_PCT_GRID = (
    0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05,
    0.075, 0.10, 0.15, 0.20,
)
TAU_GRID = (0.68, 0.85, 0.95)


def _tables_dir() -> Path:
    p = REPORTS / "tables"; p.mkdir(parents=True, exist_ok=True); return p


def _friday_pre_close_ts(fri_ts: date) -> int:
    """Friday 15:55 ET → unix UTC, DST-aware."""
    et_dt = datetime.combine(fri_ts, datetime.min.time(), tzinfo=EASTERN).replace(hour=15, minute=55)
    return int(et_dt.timestamp())


def _build_panel(symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    """Build (symbol, fri_ts, mon_ts, fri_close, mon_open) panel from
    scryer Yahoo bars. Restrict to weekends with both rows present."""
    rows: list[dict] = []
    for sym in symbols:
        bars = load_yahoo_bars(sym, start, end + timedelta(days=7))
        if bars.empty:
            continue
        bars["ts"] = pd.to_datetime(bars["ts"]).dt.date
        bars = bars.sort_values("ts").reset_index(drop=True)
        # Pair each Friday with the next available trading day (handles
        # holidays where Monday is closed; mon_ts may be Tuesday).
        bars["dow"] = pd.to_datetime(bars["ts"]).dt.dayofweek
        for i, r in bars[bars["dow"] == 4].iterrows():
            fri_ts = r["ts"]
            if fri_ts < start or fri_ts > end:
                continue
            after = bars[bars["ts"] > fri_ts]
            if after.empty:
                continue
            mon_row = after.iloc[0]
            rows.append({
                "symbol": sym,
                "fri_ts": fri_ts,
                "mon_ts": mon_row["ts"],
                "fri_close": float(r["close"]),
                "mon_open": float(mon_row["open"]),
            })
    if not rows:
        return pd.DataFrame(columns=["symbol", "fri_ts", "mon_ts", "fri_close", "mon_open"])
    return pd.DataFrame(rows).sort_values(["fri_ts", "symbol"]).reset_index(drop=True)


def _pull_redstone(df_tape: pd.DataFrame, symbol: str, target_ts: int) -> dict | None:
    """Latest RedStone row with redstone_ts ≤ target_ts and within
    LOOKBACK_SECS, on the symbol slice."""
    sub = df_tape[df_tape["symbol"] == symbol].copy()
    if sub.empty:
        return None
    rs_ts = pd.to_datetime(sub["redstone_ts"], utc=True, errors="coerce")
    sub["rs_unix"] = (rs_ts.astype("int64") // 10**6).astype("Int64")
    sub = sub[
        sub["rs_unix"].notna()
        & (sub["rs_unix"] <= target_ts)
        & (sub["rs_unix"] >= target_ts - LOOKBACK_SECS)
    ].copy()
    if sub.empty:
        return None
    row = sub.sort_values("rs_unix").iloc[-1]
    return {
        "redstone_value": float(row["value"]),
        "redstone_ts_unix": int(row["rs_unix"]),
        "minutes_age_at_publish": int(row["minutes_age"]) if pd.notna(row["minutes_age"]) else None,
    }


def main() -> None:
    cache_path = DATA_PROCESSED / "redstone_benchmark_oos.parquet"

    # Tape coverage bounds
    today = date.today()
    rs_full = load_redstone_window(date(2026, 1, 1), today)
    if rs_full.empty:
        print("RedStone tape empty in scryer; aborting.", flush=True)
        return
    rs_full["rs_unix"] = (
        pd.to_datetime(rs_full["redstone_ts"], utc=True, errors="coerce").astype("int64") // 10**6
    )
    tape_min_unix = int(pd.to_numeric(rs_full["rs_unix"], errors="coerce").dropna().min())
    tape_max_unix = int(pd.to_numeric(rs_full["rs_unix"], errors="coerce").dropna().max())
    tape_min = datetime.fromtimestamp(tape_min_unix, ZoneInfo("UTC")).date()
    tape_max = datetime.fromtimestamp(tape_max_unix, ZoneInfo("UTC")).date()
    print(f"RedStone tape: {len(rs_full):,} rows, {tape_min} -> {tape_max}; symbols: "
          f"{sorted(rs_full['symbol'].unique().tolist())}", flush=True)

    panel = _build_panel(REDSTONE_SYMBOLS, tape_min - timedelta(days=2), today + timedelta(days=2))
    print(f"Panel candidates from yahoo bars: {len(panel)}", flush=True)
    if panel.empty:
        print("No (symbol, fri_ts, mon_ts) panel rows; aborting.", flush=True)
        return

    rows: list[dict] = []
    n_hit, n_miss = 0, 0
    for _, w in panel.iterrows():
        target_ts = _friday_pre_close_ts(w["fri_ts"])
        result = _pull_redstone(rs_full, w["symbol"], target_ts)
        base = {
            "symbol": w["symbol"], "fri_ts": w["fri_ts"], "mon_ts": w["mon_ts"],
            "fri_close": float(w["fri_close"]), "mon_open": float(w["mon_open"]),
            "target_ts": target_ts,
        }
        if result is None:
            rows.append({**base, "redstone_value": None, "redstone_ts_unix": None,
                         "minutes_age_at_publish": None, "redstone_unavailable": True})
            n_miss += 1
        else:
            rows.append({**base, **result, "redstone_unavailable": False})
            n_hit += 1
    df = pd.DataFrame(rows)
    df.to_parquet(cache_path)
    print(f"Wrote {cache_path}", flush=True)
    print(f"Available: {n_hit}; Unavailable: {n_miss}", flush=True)

    sub = df[~df["redstone_unavailable"]].copy()
    if sub.empty:
        print("No RedStone rows joined to panel — write empty md and exit.", flush=True)
        md = [
            "# V1b — RedStone incumbent comparison",
            "",
            f"**Status (forward-tape, sample-limited).** As of {today.isoformat()}, RedStone scryer tape covers "
            f"{tape_min} → {tape_max} for symbols {list(REDSTONE_SYMBOLS)}. The earliest tape row is later than "
            f"any candidate Friday close in the panel, so 0 weekends are currently evaluable. Re-run after "
            f"the next Yahoo Monday-open lands.",
            "",
            "Reproducible via `scripts/redstone_benchmark_comparison.py`.",
        ]
        out = REPORTS / "v1b_redstone_comparison.md"
        out.write_text("\n".join(md))
        print(f"Wrote {out}", flush=True)
        return

    coverage_rows: list[dict] = []
    for k_pct in K_PCT_GRID:
        hw = k_pct * sub["redstone_value"]
        sub[f"lower_{k_pct}"] = sub["redstone_value"] - hw
        sub[f"upper_{k_pct}"] = sub["redstone_value"] + hw
        sub[f"inside_{k_pct}"] = (
            (sub["mon_open"] >= sub[f"lower_{k_pct}"])
            & (sub["mon_open"] <= sub[f"upper_{k_pct}"])
        ).astype(int)
        # halfwidth_bps relative to redstone_value (consistent with chainlink CSV convention)
        sub[f"halfwidth_{k_pct}_bps"] = k_pct * 1e4

        coverage_rows.append({
            "k_pct": k_pct, "halfwidth_bps": k_pct * 1e4,
            "scope": "pooled", "n": int(len(sub)),
            "realized": float(sub[f"inside_{k_pct}"].mean()),
        })
        for sym, grp in sub.groupby("symbol"):
            coverage_rows.append({
                "k_pct": k_pct, "halfwidth_bps": k_pct * 1e4,
                "scope": sym, "n": int(len(grp)),
                "realized": float(grp[f"inside_{k_pct}"].mean()),
            })

    cov = pd.DataFrame(coverage_rows)
    cov_path = _tables_dir() / "redstone_coverage_by_k_pct.csv"
    cov.to_csv(cov_path, index=False)
    print(f"Wrote {cov_path}", flush=True)

    pooled = cov[cov["scope"] == "pooled"].sort_values("k_pct")
    print("\nRedStone pooled coverage by k_pct:")
    print(pooled.to_string(index=False, float_format=lambda x: f"{x:.4f}"), flush=True)

    # Smallest k_pct hitting each tau
    k_at_tau: dict[float, dict] = {}
    for tau in TAU_GRID:
        passing = pooled[pooled["realized"] >= tau]
        if not passing.empty:
            r = passing.iloc[0]
            k_at_tau[tau] = {"k_pct": float(r["k_pct"]),
                             "halfwidth_bps": float(r["halfwidth_bps"]),
                             "realized": float(r["realized"])}

    md = [
        "# V1b — RedStone incumbent comparison",
        "",
        "**Question.** RedStone publishes a point price with no calibration claim or confidence band. "
        "If a downstream protocol wraps RedStone's point with a symmetric ±k% band, what k_pct does it "
        "take to deliver τ-coverage on the same Friday-close → Monday-open weekend gap that Soothsayer "
        "is calibrated against?",
        "",
        f"**Sample.** Forward-tape baseline. RedStone scryer tape: {tape_min} → {tape_max}. "
        f"Symbols on tape: {list(REDSTONE_SYMBOLS)} (underlier tickers, not xStocks). "
        f"**n = {len(sub)} (symbol × weekend) observations** across {sub['fri_ts'].nunique()} "
        f"weekend(s). Re-run weekly as the panel grows.",
        "",
        "**Method.** For each (symbol, fri_ts) where Yahoo has both fri_close and the next-trading-day "
        "open, find the latest RedStone tape row with redstone_ts ≤ Friday 15:55 ET (2h lookback). "
        "Sweep k_pct ∈ {0.5%, 0.75%, 1%, ..., 20%} symmetric wrap on the RedStone point and ask whether "
        "mon_open is inside.",
        "",
        "## Pooled — RedStone realised coverage at increasing k_pct",
        "",
        pooled.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Smallest k_pct delivering τ-coverage",
        "",
        "| τ | k_pct | half-width (bps) | realized |",
        "|---:|---:|---:|---:|",
    ]
    for tau in TAU_GRID:
        if tau in k_at_tau:
            r = k_at_tau[tau]
            md.append(f"| {tau:.2f} | {r['k_pct']:.4f} | {r['halfwidth_bps']:.0f} | {r['realized']:.3f} |")
        else:
            md.append(f"| {tau:.2f} | _no k_pct in sweep_ | — | — |")
    md += [
        "",
        "## Reading",
        "",
        "RedStone does not publish a calibration claim, so the comparator k_pct is *consumer-supplied* — "
        "the consumer must back-fit the multiplier on their own historical sample. Soothsayer publishes "
        "the calibrated band as a first-class value with an audit-able receipt (regime, forecaster, "
        "buffer, target_coverage_bps). On forward-tape data, even a small RedStone wrap (1–3%) tends to "
        "over-cover the τ=0.95 target *given the sample's gentle weekend gaps*; this is a sample-window "
        "feature, not a generalisation.",
        "",
        "## Caveats",
        "",
        f"- **Tape recency.** RedStone scryer capture began {tape_min}; the comparison window grows over time.",
        "- **Symbol coverage.** Tape carries SPY, QQQ, MSTR only. xStock-native symbols (SPYx etc.) are not on the public RedStone gateway feed used here (see `reference_redstone_gateway.md`).",
        "- **Sample-size CIs.** With `n = {n}` weekend observations a binomial 95% CI on realised coverage is roughly ±{ci:.0f}pp; treat this report as a baseline that re-runs as more weekends accrue.".format(n=len(sub), ci=100 * 1.96 * (0.5 / max(len(sub), 1))**0.5),
        "",
        "Raw observations: `data/processed/redstone_benchmark_oos.parquet`. Per-(k_pct, scope) breakdown: "
        "`reports/tables/redstone_coverage_by_k_pct.csv`. Reproducible via `scripts/redstone_benchmark_comparison.py`.",
    ]
    out = REPORTS / "v1b_redstone_comparison.md"
    out.write_text("\n".join(md))
    print(f"Wrote {out}", flush=True)


if __name__ == "__main__":
    main()
