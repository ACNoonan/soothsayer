"""
Kamino Scope incumbent-comparison benchmark — W1 deliverable for the validation backlog.

Question. Kamino's Scope oracle publishes a point price (no published
confidence band). Scope is the on-chain feed Kamino's lending markets
read for xStock collateral. *If a downstream protocol wraps Scope's
point with a symmetric ±k% band, what k_pct does it take to deliver
τ-coverage on the same Friday-close → Monday-open weekend gap that
Soothsayer is calibrated against?*

Sample window. Scryer Kamino-Scope tape currently covers
2026-04-26 → 2026-05-03 across the 8-symbol xStock set
(AAPLx / GOOGLx / HOODx / MSTRx / NVDAx / QQQx / SPYx / TSLAx).
xStock symbol → underlier ticker mapping is the natural
strip-the-`x`-suffix rule; we join Scope's xStock point to Yahoo's
underlier mon_open as the realised target.

Procedure (mirrors `scripts/pyth_benchmark_comparison.py`):
  1. Build the comparison panel from scryer Yahoo bars on the underlier
     tickers (strip-x mapping), with fri_ts → next-trading-day mon_open.
  2. For each (xStock, fri_ts), find the latest Scope tape row with
     scope_unix_ts ≤ Friday 16:00 ET (DST-aware), 2-hour lookback.
  3. For each k_pct in K_PCT_GRID, compute the symmetric band on the
     Scope point and check whether the underlier mon_open is inside.
  4. Aggregate to pooled and per-symbol coverage rates.

Outputs:
  data/processed/kamino_scope_benchmark_oos.parquet  per-row Scope obs
  reports/tables/kamino_scope_coverage_by_k_pct.csv  per-(k_pct, scope) coverage
  reports/v1b_kamino_scope_comparison.md             paper-ready writeup

Run unbuffered for live progress:
    PYTHONUNBUFFERED=1 .venv/bin/python scripts/kamino_scope_benchmark_comparison.py
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.sources.scryer import load_kamino_scope_window, load_yahoo_bars

XSTOCK_TO_UNDERLIER = {
    "AAPLx": "AAPL", "GOOGLx": "GOOGL", "HOODx": "HOOD", "MSTRx": "MSTR",
    "NVDAx": "NVDA", "QQQx": "QQQ", "SPYx": "SPY", "TSLAx": "TSLA",
}
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


def _build_panel(underliers: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    rows: list[dict] = []
    for sym in underliers:
        bars = load_yahoo_bars(sym, start, end + timedelta(days=7))
        if bars.empty:
            continue
        bars["ts"] = pd.to_datetime(bars["ts"]).dt.date
        bars = bars.sort_values("ts").reset_index(drop=True)
        bars["dow"] = pd.to_datetime(bars["ts"]).dt.dayofweek
        for _, r in bars[bars["dow"] == 4].iterrows():
            fri_ts = r["ts"]
            if fri_ts < start or fri_ts > end:
                continue
            after = bars[bars["ts"] > fri_ts]
            if after.empty:
                continue
            mon_row = after.iloc[0]
            rows.append({
                "underlier": sym,
                "fri_ts": fri_ts,
                "mon_ts": mon_row["ts"],
                "fri_close": float(r["close"]),
                "mon_open": float(mon_row["open"]),
            })
    if not rows:
        return pd.DataFrame(columns=["underlier", "fri_ts", "mon_ts", "fri_close", "mon_open"])
    return pd.DataFrame(rows).sort_values(["fri_ts", "underlier"]).reset_index(drop=True)


def _pull_scope(df_tape: pd.DataFrame, xstock_symbol: str, target_ts: int) -> dict | None:
    sub = df_tape[df_tape["symbol"] == xstock_symbol].copy()
    if sub.empty:
        return None
    sub = sub[
        sub["scope_unix_ts"].notna()
        & (sub["scope_unix_ts"] <= target_ts)
        & (sub["scope_unix_ts"] >= target_ts - LOOKBACK_SECS)
    ].copy()
    if sub.empty:
        return None
    row = sub.sort_values("scope_unix_ts").iloc[-1]
    return {
        "scope_price": float(row["scope_price"]),
        "scope_unix_ts": int(row["scope_unix_ts"]),
        "scope_age_s": int(row["scope_age_s"]) if pd.notna(row["scope_age_s"]) else None,
    }


def main() -> None:
    cache_path = DATA_PROCESSED / "kamino_scope_benchmark_oos.parquet"

    today = date.today()
    ks_full = load_kamino_scope_window(date(2026, 1, 1), today)
    if ks_full.empty:
        print("Kamino Scope tape empty in scryer; aborting.", flush=True)
        return
    ks_full = ks_full[ks_full["scope_err"].isna() | (ks_full["scope_err"] == "")].copy()
    tape_min_unix = int(pd.to_numeric(ks_full["scope_unix_ts"], errors="coerce").dropna().min())
    tape_max_unix = int(pd.to_numeric(ks_full["scope_unix_ts"], errors="coerce").dropna().max())
    tape_min = datetime.fromtimestamp(tape_min_unix, ZoneInfo("UTC")).date()
    tape_max = datetime.fromtimestamp(tape_max_unix, ZoneInfo("UTC")).date()
    print(f"Kamino Scope tape: {len(ks_full):,} rows, {tape_min} -> {tape_max}; symbols: "
          f"{sorted(ks_full['symbol'].unique().tolist())}", flush=True)

    underliers = tuple(sorted(set(XSTOCK_TO_UNDERLIER.values())))
    panel = _build_panel(underliers, tape_min - timedelta(days=2), today + timedelta(days=2))
    print(f"Panel candidates from yahoo bars: {len(panel)}", flush=True)
    if panel.empty:
        print("No (underlier, fri_ts, mon_ts) panel rows; aborting.", flush=True)
        return

    # Cross-product: for each xStock symbol, attempt to find a Scope row at Friday close.
    rows: list[dict] = []
    n_hit, n_miss = 0, 0
    for xstock, underlier in XSTOCK_TO_UNDERLIER.items():
        sym_panel = panel[panel["underlier"] == underlier]
        for _, w in sym_panel.iterrows():
            target_ts = _friday_pre_close_ts(w["fri_ts"])
            result = _pull_scope(ks_full, xstock, target_ts)
            base = {
                "xstock": xstock, "underlier": underlier,
                "fri_ts": w["fri_ts"], "mon_ts": w["mon_ts"],
                "fri_close": float(w["fri_close"]), "mon_open": float(w["mon_open"]),
                "target_ts": target_ts,
            }
            if result is None:
                rows.append({**base, "scope_price": None, "scope_unix_ts": None,
                             "scope_age_s": None, "scope_unavailable": True})
                n_miss += 1
            else:
                rows.append({**base, **result, "scope_unavailable": False})
                n_hit += 1
    df = pd.DataFrame(rows)
    df.to_parquet(cache_path)
    print(f"Wrote {cache_path}", flush=True)
    print(f"Available: {n_hit}; Unavailable: {n_miss}", flush=True)

    sub = df[~df["scope_unavailable"]].copy()
    if sub.empty:
        print("No Scope rows joined to panel — write empty md and exit.", flush=True)
        md = [
            "# V1b — Kamino Scope incumbent comparison",
            "",
            f"**Status (forward-tape, sample-limited).** As of {today.isoformat()}, Scope scryer tape covers "
            f"{tape_min} → {tape_max}. The earliest tape row is later than any candidate Friday close in "
            f"the panel, so 0 weekends are currently evaluable. Re-run after the next Yahoo Monday-open lands.",
            "",
            "Reproducible via `scripts/kamino_scope_benchmark_comparison.py`.",
        ]
        out = REPORTS / "v1b_kamino_scope_comparison.md"
        out.write_text("\n".join(md))
        print(f"Wrote {out}", flush=True)
        return

    coverage_rows: list[dict] = []
    for k_pct in K_PCT_GRID:
        hw = k_pct * sub["scope_price"]
        sub[f"lower_{k_pct}"] = sub["scope_price"] - hw
        sub[f"upper_{k_pct}"] = sub["scope_price"] + hw
        sub[f"inside_{k_pct}"] = (
            (sub["mon_open"] >= sub[f"lower_{k_pct}"])
            & (sub["mon_open"] <= sub[f"upper_{k_pct}"])
        ).astype(int)

        coverage_rows.append({
            "k_pct": k_pct, "halfwidth_bps": k_pct * 1e4,
            "scope": "pooled", "n": int(len(sub)),
            "realized": float(sub[f"inside_{k_pct}"].mean()),
        })
        for sym, grp in sub.groupby("xstock"):
            coverage_rows.append({
                "k_pct": k_pct, "halfwidth_bps": k_pct * 1e4,
                "scope": sym, "n": int(len(grp)),
                "realized": float(grp[f"inside_{k_pct}"].mean()),
            })

    cov = pd.DataFrame(coverage_rows)
    cov_path = _tables_dir() / "kamino_scope_coverage_by_k_pct.csv"
    cov.to_csv(cov_path, index=False)
    print(f"Wrote {cov_path}", flush=True)

    pooled = cov[cov["scope"] == "pooled"].sort_values("k_pct")
    print("\nKamino Scope pooled coverage by k_pct:")
    print(pooled.to_string(index=False, float_format=lambda x: f"{x:.4f}"), flush=True)

    k_at_tau: dict[float, dict] = {}
    for tau in TAU_GRID:
        passing = pooled[pooled["realized"] >= tau]
        if not passing.empty:
            r = passing.iloc[0]
            k_at_tau[tau] = {"k_pct": float(r["k_pct"]),
                             "halfwidth_bps": float(r["halfwidth_bps"]),
                             "realized": float(r["realized"])}

    md = [
        "# V1b — Kamino Scope incumbent comparison",
        "",
        "**Question.** Kamino's Scope oracle publishes a point price for xStock collateral with no "
        "calibration claim or confidence band. If a downstream protocol wraps Scope's point with a "
        "symmetric ±k% band, what k_pct does it take to deliver τ-coverage on the same Friday-close → "
        "Monday-open weekend gap that Soothsayer is calibrated against?",
        "",
        f"**Sample.** Forward-tape baseline. Scope scryer tape: {tape_min} → {tape_max}. "
        f"Symbols on tape: {sorted(XSTOCK_TO_UNDERLIER.keys())} (xStock; mapped to underliers via "
        "strip-x for the Yahoo `mon_open` join). "
        f"**n = {len(sub)} (xStock × weekend) observations** across {sub['fri_ts'].nunique()} weekend(s). "
        "Re-run weekly as the panel grows.",
        "",
        "**Method.** For each (xStock, fri_ts) where Yahoo has both fri_close and the next-trading-day "
        "open on the matching underlier, find the latest Scope tape row with `scope_unix_ts` ≤ "
        "Friday 15:55 ET (2h lookback). Sweep k_pct ∈ {0.5%, 0.75%, 1%, ..., 20%} symmetric wrap on "
        "the Scope point and ask whether mon_open (underlier) is inside.",
        "",
        "## Pooled — Scope realised coverage at increasing k_pct",
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
        "Scope is xStock-native — it serves the actual on-chain symbols Kamino lends against — but it "
        "does not publish a calibration claim. Like RedStone, the comparator k_pct is consumer-supplied. "
        "This makes Scope's point a fine input to a downstream calibration layer (Soothsayer's role), but "
        "Scope itself does not deliver a verifiable probability statement of the kind Soothsayer's "
        "coverage-inversion primitive supplies.",
        "",
        "## Caveats",
        "",
        f"- **Tape recency.** Scope scryer capture began {tape_min}; the comparison window grows over time.",
        "- **xStock → underlier truth.** We join Scope's xStock point to Yahoo's underlier `mon_open`. "
        "Scope's xStock price *should* track its underlier near 1:1 (per Backed's NAV mechanism, "
        "modulo redemption discount / premium); deviations between Scope's xStock and a hypothetical "
        "xStock-native truth are themselves part of what Soothsayer's served band absorbs.",
        "- **Sample-size CIs.** With `n = {n}` weekend observations a binomial 95% CI on realised "
        "coverage is roughly ±{ci:.0f}pp; treat this report as a baseline that re-runs as more "
        "weekends accrue.".format(n=len(sub), ci=100 * 1.96 * (0.5 / max(len(sub), 1))**0.5),
        "",
        "Raw observations: `data/processed/kamino_scope_benchmark_oos.parquet`. Per-(k_pct, scope) "
        "breakdown: `reports/tables/kamino_scope_coverage_by_k_pct.csv`. Reproducible via "
        "`scripts/kamino_scope_benchmark_comparison.py`.",
    ]
    out = REPORTS / "v1b_kamino_scope_comparison.md"
    out.write_text("\n".join(md))
    print(f"Wrote {out}", flush=True)


if __name__ == "__main__":
    main()
