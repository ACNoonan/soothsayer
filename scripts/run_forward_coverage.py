"""
W5 — Live forward-tape realised coverage.

Reviewer-immune coverage check on weekends that happened *after* the last
fri_ts in the frozen calibration panel (`data/processed/v1b_panel.parquet`,
cutoff 2026-04-24). Sample is small at first (≈1 weekend × 10 symbols) and
grows weekly; the runner is idempotent so it re-runs cheaply each Tuesday
once Monday's open print has landed in scryer.

What this does
--------------

1. Calls `soothsayer.backtest.panel.build()` over a forward-extended window
   (start 2024-01-01 for plenty of rolling-stat headroom; end = today).
   This re-derives the same panel rows as the frozen `v1b_panel.parquet`
   for the historical overlap, *plus* whatever forward weekends scryer has
   complete data for.

2. Cross-checks 3 historical rows against the frozen panel — re-derived
   `(fri_close, mon_open, factor_ret, regime_pub)` must match exactly.
   Catches scryer data revisions or builder drift before the forward
   numbers are reported.

3. For every forward weekend (`fri_ts > 2026-04-24`), applies the deployed
   M5 (AMM-profile) serve formula using the constants in
   `soothsayer.oracle` — by-construction byte-for-byte parity with what
   the live oracle would publish for these weekends.

4. Aggregates realised coverage at τ ∈ {0.68, 0.85, 0.95, 0.99}: pooled
   hit-rate, mean half-width (bps), per-regime n, and a per-symbol table
   for transparency on the small sample.

Outputs
-------
- `data/processed/v1b_forward_coverage.parquet` — per (symbol, fri_ts, τ).
- `reports/v1b_forward_coverage.md`              — paper-ready writeup.

Cross-link
----------
Listed in `reports/active/validation_backlog.md` W5. No methodology change — this is a
reviewer-immune empirical check on the deployed v1 / candidate M5 bands.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.backtest.panel import PanelSpec, build as build_panel
from soothsayer.backtest.regimes import tag as tag_regimes
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import (
    DELTA_SHIFT_SCHEDULE,
    REGIME_QUANTILE_TABLE,
    c_bump_for_target,
    delta_shift_for_target,
    regime_quantile_for,
)


# Last fri_ts in the frozen calibration panel. Anything strictly later is
# "forward" — could not have been in any calibration set.
FROZEN_PANEL_CUTOFF: date = date(2026, 4, 24)
# Wide enough to give _high_vol_flag's rolling 52-week VIX quartile clean
# anchoring; not so wide that the rebuild costs more than a few seconds.
PANEL_BUILD_START: date = date(2024, 1, 1)
TARGETS: tuple[float, ...] = (0.68, 0.85, 0.95, 0.99)
CROSS_CHECK_ROWS: int = 3

OUT_PARQUET: Path = DATA_PROCESSED / "v1b_forward_coverage.parquet"
OUT_MARKDOWN: Path = REPORTS / "v1b_forward_coverage.md"
FROZEN_PANEL_PATH: Path = DATA_PROCESSED / "v1b_panel.parquet"


@dataclass
class CrossCheckResult:
    n_checked: int
    matches: int
    mismatches: list[dict]


def _build_extended_panel() -> pd.DataFrame:
    spec = PanelSpec(start=PANEL_BUILD_START, end=date.today())
    panel = build_panel(spec)
    panel = tag_regimes(panel)
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    panel["point"] = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    return panel.reset_index(drop=True)


def _cross_check_historical(extended: pd.DataFrame) -> CrossCheckResult:
    """Re-derived rows must equal the frozen v1b_panel.parquet exactly on
    the columns the M5 band depends on. Picks rows from the *latest* part
    of the historical overlap so the check is sensitive to recent scryer
    revisions, not just ancient stable history."""
    frozen = pd.read_parquet(FROZEN_PANEL_PATH)
    frozen["fri_ts"] = pd.to_datetime(frozen["fri_ts"]).dt.date
    frozen["point"] = frozen["fri_close"].astype(float) * (
        1.0 + frozen["factor_ret"].astype(float)
    )

    overlap_keys = (
        extended[["symbol", "fri_ts"]]
        .merge(frozen[["symbol", "fri_ts"]], on=["symbol", "fri_ts"], how="inner")
        .sort_values(["fri_ts", "symbol"], ascending=[False, True])
        .head(CROSS_CHECK_ROWS)
    )

    cols = ["fri_close", "mon_open", "factor_ret", "regime_pub", "point"]
    mismatches: list[dict] = []
    for _, key in overlap_keys.iterrows():
        a = extended[
            (extended["symbol"] == key["symbol"]) & (extended["fri_ts"] == key["fri_ts"])
        ].iloc[0]
        b = frozen[
            (frozen["symbol"] == key["symbol"]) & (frozen["fri_ts"] == key["fri_ts"])
        ].iloc[0]
        for col in cols:
            if col == "regime_pub":
                ok = str(a[col]) == str(b[col])
            else:
                ok = np.isclose(float(a[col]), float(b[col]), rtol=1e-6, atol=1e-9)
            if not ok:
                mismatches.append(
                    {
                        "symbol": key["symbol"],
                        "fri_ts": key["fri_ts"],
                        "column": col,
                        "extended": a[col],
                        "frozen": b[col],
                    }
                )

    return CrossCheckResult(
        n_checked=len(overlap_keys),
        matches=len(overlap_keys) * len(cols) - len(mismatches),
        mismatches=mismatches,
    )


def _apply_m5_band(forward: pd.DataFrame) -> pd.DataFrame:
    """For each forward (symbol, fri_ts) row, apply the deployed M5 AMM-profile
    serve formula at every τ in TARGETS and emit per-τ band + hit columns."""
    rows: list[dict] = []
    for _, r in forward.iterrows():
        regime = str(r["regime_pub"])
        fri_close = float(r["fri_close"])
        mon_open = float(r["mon_open"])
        point = float(r["point"])
        for tau in TARGETS:
            delta = delta_shift_for_target(tau)
            served_target = min(tau + delta, 0.99)
            c_bump = c_bump_for_target(served_target)
            q_regime = regime_quantile_for(regime, served_target)
            q_eff = c_bump * q_regime
            lower = point * (1.0 - q_eff)
            upper = point * (1.0 + q_eff)
            half_width = (upper - lower) / 2.0
            half_width_bps = (half_width / fri_close) * 1e4 if fri_close else float("nan")
            hit = bool((mon_open >= lower) and (mon_open <= upper))
            rows.append(
                {
                    "symbol": r["symbol"],
                    "fri_ts": r["fri_ts"],
                    "mon_ts": r["mon_ts"],
                    "regime_pub": regime,
                    "tau": tau,
                    "served_target": served_target,
                    "fri_close": fri_close,
                    "point": point,
                    "mon_open": mon_open,
                    "lower": lower,
                    "upper": upper,
                    "half_width_bps": half_width_bps,
                    "hit": hit,
                }
            )
    return pd.DataFrame(rows)


def _aggregate(per_row: pd.DataFrame) -> pd.DataFrame:
    if per_row.empty:
        return pd.DataFrame(
            columns=[
                "tau",
                "n",
                "n_hits",
                "realised_coverage",
                "mean_half_width_bps",
                "regime_normal_n",
                "regime_long_weekend_n",
                "regime_high_vol_n",
            ]
        )
    out = []
    for tau, g in per_row.groupby("tau", sort=True):
        n = len(g)
        n_hits = int(g["hit"].sum())
        regime_counts = g["regime_pub"].value_counts().to_dict()
        out.append(
            {
                "tau": float(tau),
                "n": n,
                "n_hits": n_hits,
                "realised_coverage": n_hits / n if n else float("nan"),
                "mean_half_width_bps": float(g["half_width_bps"].mean()),
                "regime_normal_n": int(regime_counts.get("normal", 0)),
                "regime_long_weekend_n": int(regime_counts.get("long_weekend", 0)),
                "regime_high_vol_n": int(regime_counts.get("high_vol", 0)),
            }
        )
    return pd.DataFrame(out)


def _wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Two-sided Wilson interval for a binomial proportion. Returns (lo, hi)
    in [0, 1]. Conventional small-sample CI used by the W1 unified report."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def _render_markdown(
    summary: pd.DataFrame,
    per_row: pd.DataFrame,
    cross_check: CrossCheckResult,
    forward_weekends: list[date],
) -> str:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append("# v1b — Live forward-tape realised coverage (W5)")
    lines.append("")
    lines.append(f"_Last run: {now_iso}_")
    lines.append("")
    lines.append(
        "Reviewer-immune coverage check on weekends with `fri_ts > "
        f"{FROZEN_PANEL_CUTOFF.isoformat()}` — the last Friday in the frozen "
        "calibration panel. The deployed M5 (AMM-profile) band is applied "
        "exactly as the live oracle would serve it; realised coverage is "
        "computed against Yahoo Monday open. Sample is small at first and "
        "grows by ≈10 observations (universe size) per evaluable weekend."
    )
    lines.append("")

    lines.append("## Inputs (re-derived from scryer)")
    lines.append("")
    lines.append(f"- Panel-build window: {PANEL_BUILD_START} → {date.today()}")
    lines.append(f"- Frozen-panel cutoff: {FROZEN_PANEL_CUTOFF.isoformat()}")
    lines.append(
        "- M5 serving constants: `soothsayer.oracle` "
        "(`REGIME_QUANTILE_TABLE`, `C_BUMP_SCHEDULE`, `DELTA_SHIFT_SCHEDULE`)."
    )
    lines.append("")

    lines.append("## Historical cross-check")
    lines.append("")
    lines.append(
        f"- Rows checked: {cross_check.n_checked} (latest historical overlap "
        "with `data/processed/v1b_panel.parquet`)"
    )
    lines.append(
        "- Columns checked per row: `fri_close, mon_open, factor_ret, "
        "regime_pub, point`"
    )
    if cross_check.mismatches:
        lines.append(
            f"- **MISMATCHES: {len(cross_check.mismatches)}** — investigate "
            "before trusting the forward numbers below."
        )
        lines.append("")
        lines.append("| symbol | fri_ts | column | extended | frozen |")
        lines.append("|---|---|---|---|---|")
        for m in cross_check.mismatches:
            lines.append(
                f"| {m['symbol']} | {m['fri_ts']} | {m['column']} | "
                f"{m['extended']} | {m['frozen']} |"
            )
    else:
        lines.append("- **All re-derived columns match the frozen panel exactly.**")
    lines.append("")

    lines.append("## Forward sample")
    lines.append("")
    if not forward_weekends:
        lines.append(
            "**No forward weekends evaluable yet.** The next Monday open "
            "(2026-05-04) lands in scryer ~14:30 UTC Tuesday; re-run this "
            "script once Yahoo's `equities_daily/v1` Monday cron completes."
        )
        lines.append("")
        lines.append("Result table will populate from that run forward.")
        return "\n".join(lines) + "\n"

    n_weekends = len(forward_weekends)
    lines.append(
        f"- Forward weekends evaluable: {n_weekends} "
        f"({', '.join(d.isoformat() for d in forward_weekends)})"
    )
    lines.append(f"- Symbol-weekend rows per τ: {len(per_row) // len(TARGETS)}")
    lines.append("")

    lines.append("## Realised coverage by τ")
    lines.append("")
    lines.append(
        "| τ (target) | served τ' | n | hits | realised | 95% Wilson CI | "
        "mean half-width (bps) |"
    )
    lines.append("|---:|---:|---:|---:|---:|---|---:|")
    for _, r in summary.iterrows():
        tau = float(r["tau"])
        served = min(tau + DELTA_SHIFT_SCHEDULE.get(tau, 0.0), 0.99)
        n = int(r["n"])
        n_hits = int(r["n_hits"])
        cov = r["realised_coverage"]
        lo, hi = _wilson_ci(n_hits, n)
        ci = f"[{lo:.3f}, {hi:.3f}]"
        lines.append(
            f"| {tau:.2f} | {served:.2f} | {n} | {n_hits} | "
            f"{cov:.3f} | {ci} | {r['mean_half_width_bps']:.1f} |"
        )
    lines.append("")
    lines.append(
        "_τ' = τ + δ(τ) is the served claim after the walk-forward δ-shift; "
        "consumer-facing target is τ. Realised coverage should sit at or "
        "above τ on average (the schedule is conservative by construction); "
        "with this small a sample the Wilson CI is wide and a single miss can "
        "drop the headline materially._"
    )
    lines.append("")

    lines.append("## Per-regime composition (informational)")
    lines.append("")
    lines.append("| τ | normal | long_weekend | high_vol |")
    lines.append("|---:|---:|---:|---:|")
    for _, r in summary.iterrows():
        lines.append(
            f"| {float(r['tau']):.2f} | {int(r['regime_normal_n'])} | "
            f"{int(r['regime_long_weekend_n'])} | {int(r['regime_high_vol_n'])} |"
        )
    lines.append("")

    lines.append("## Per-(symbol, τ) detail")
    lines.append("")
    lines.append("| symbol | fri_ts | regime | τ | mon_open | point | hw bps | hit |")
    lines.append("|---|---|---|---:|---:|---:|---:|:---:|")
    for _, r in per_row.sort_values(["fri_ts", "symbol", "tau"]).iterrows():
        lines.append(
            f"| {r['symbol']} | {r['fri_ts']} | {r['regime_pub']} | "
            f"{float(r['tau']):.2f} | {r['mon_open']:.4f} | {r['point']:.4f} | "
            f"{r['half_width_bps']:.1f} | {'✓' if r['hit'] else '✗'} |"
        )
    lines.append("")

    lines.append("## Re-run")
    lines.append("")
    lines.append("```")
    lines.append("uv run python scripts/run_forward_coverage.py")
    lines.append("```")
    lines.append("")
    lines.append(
        "Idempotent. Safe to re-run weekly (Tuesday after Yahoo's Monday-open "
        "cron lands). Each new evaluable weekend adds ≈10 observations across "
        "the universe."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    print(f"Building extended panel ({PANEL_BUILD_START} → {date.today()})…")
    extended = _build_extended_panel()
    print(
        f"  extended panel: {len(extended):,} rows × "
        f"{extended['fri_ts'].nunique()} weekends × "
        f"{extended['symbol'].nunique()} symbols"
    )

    print("Cross-checking against frozen v1b_panel.parquet…")
    cross_check = _cross_check_historical(extended)
    if cross_check.mismatches:
        print(
            f"  WARNING: {len(cross_check.mismatches)} mismatches across "
            f"{cross_check.n_checked} rows — see report."
        )
    else:
        print(
            f"  OK ({cross_check.n_checked} rows, "
            f"{cross_check.matches} field comparisons, all match)"
        )

    forward = (
        extended[extended["fri_ts"] > FROZEN_PANEL_CUTOFF]
        .dropna(subset=["fri_close", "mon_open", "factor_ret", "regime_pub"])
        .reset_index(drop=True)
    )
    forward_weekends = sorted(forward["fri_ts"].unique().tolist())
    print(
        f"Forward sample: {len(forward)} rows across "
        f"{len(forward_weekends)} weekend(s)."
    )

    per_row = _apply_m5_band(forward) if not forward.empty else pd.DataFrame()
    summary = _aggregate(per_row)

    if not per_row.empty:
        per_row.to_parquet(OUT_PARQUET, index=False)
        print(f"Wrote {OUT_PARQUET} ({len(per_row):,} rows)")
    else:
        print(f"Skipping {OUT_PARQUET} (no forward rows yet).")

    OUT_MARKDOWN.write_text(
        _render_markdown(summary, per_row, cross_check, forward_weekends)
    )
    print(f"Wrote {OUT_MARKDOWN}")


if __name__ == "__main__":
    main()
