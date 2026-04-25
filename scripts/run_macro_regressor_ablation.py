"""
Macro-event regressor ablation.

Re-fit F1_emp_regime with `macro_event_next_week_f` (FOMC + CPI + NFP) added
to the log-log residual regressors and compare:

  M0  current deployed F1_emp_regime (vol_idx + earnings + long_weekend)
  M1  + macro_event_next_week_f
  M2  swap earnings_next_week_f → macro_event_next_week_f

Question (pre-registered): does the macro-event flag close the shock-tertile
coverage gap (~80% at τ=0.95) documented in §9.2 of the paper?

Outputs:
  reports/tables/v1b_macro_ablation.csv          per-(variant, regime, claimed) coverage / sharpness
  reports/tables/v1b_macro_ablation_shock.csv   shock-tertile breakdown
  reports/v1b_macro_regressor.md                writeup
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import forecasters as fc
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS

COVERAGE_LEVELS = (0.68, 0.85, 0.95, 0.99)


def _tables_dir() -> Path:
    p = REPORTS / "tables"; p.mkdir(parents=True, exist_ok=True); return p


def _summarise(name: str, panel: pd.DataFrame, point: pd.Series,
               bounds: dict[float, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    cov = met.coverage_and_sharpness_from_bounds(panel, point, bounds)
    for _, r in cov.iterrows():
        rows.append({
            "variant": name, "scope": "pooled", "claimed": float(r["claimed"]),
            "n": int(r["n"]), "realized": float(r["realized"]),
            "sharpness_bps": float(r["sharpness_bps"]),
        })
    for regime, idx in panel.groupby("regime_pub").groups.items():
        pm = panel.loc[idx]; pp = point.loc[idx]
        bb = {c: b.loc[idx] for c, b in bounds.items()}
        cov_r = met.coverage_and_sharpness_from_bounds(pm, pp, bb)
        for _, r in cov_r.iterrows():
            rows.append({
                "variant": name, "scope": regime, "claimed": float(r["claimed"]),
                "n": int(r["n"]), "realized": float(r["realized"]),
                "sharpness_bps": float(r["sharpness_bps"]),
            })
    for bucket, idx in panel.groupby("realized_bucket").groups.items():
        pm = panel.loc[idx]; pp = point.loc[idx]
        bb = {c: b.loc[idx] for c, b in bounds.items()}
        cov_b = met.coverage_and_sharpness_from_bounds(pm, pp, bb)
        for _, r in cov_b.iterrows():
            rows.append({
                "variant": name, "scope": f"realized_{bucket}", "claimed": float(r["claimed"]),
                "n": int(r["n"]), "realized": float(r["realized"]),
                "sharpness_bps": float(r["sharpness_bps"]),
            })
    return pd.DataFrame(rows)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel_macro.parquet")
    if "macro_event_next_week_f" not in panel.columns:
        raise RuntimeError("panel missing macro_event_next_week_f — run build_fred_macro_calendar.py first")
    if "is_long_weekend" not in panel.columns:
        panel["is_long_weekend"] = (panel["gap_days"] >= 4).astype(float)
    if "earnings_next_week_f" not in panel.columns:
        panel["earnings_next_week_f"] = panel["earnings_next_week"].astype(float)

    print(f"Panel: {len(panel):,} rows; "
          f"macro_event_next_week_f = {int(panel['macro_event_next_week_f'].sum()):,} positives "
          f"({panel['macro_event_next_week_f'].mean()*100:.1f}%)", flush=True)

    point_fa = fc.point_futures_adjusted(panel)
    summaries = []

    # M0 = current deployed F1_emp_regime
    print("[M0] vol_idx + earnings + long_weekend (deployed)…", flush=True)
    t0 = time.time()
    bounds_m0, _ = fc.empirical_quantiles_f1_loglog(
        panel, coverage_levels=COVERAGE_LEVELS, window=156,
        vol_col="vol_idx_fri_close",
        extra_regressors=("earnings_next_week_f", "is_long_weekend"),
    )
    print(f"  done in {time.time()-t0:.1f}s")
    summaries.append(_summarise("M0_deployed", panel, point_fa, bounds_m0))

    # M1 = + macro_event_next_week_f
    print("[M1] vol_idx + earnings + long_weekend + macro_event_next_week…", flush=True)
    t0 = time.time()
    bounds_m1, _ = fc.empirical_quantiles_f1_loglog(
        panel, coverage_levels=COVERAGE_LEVELS, window=156,
        vol_col="vol_idx_fri_close",
        extra_regressors=("earnings_next_week_f", "is_long_weekend", "macro_event_next_week_f"),
    )
    print(f"  done in {time.time()-t0:.1f}s")
    summaries.append(_summarise("M1_with_macro", panel, point_fa, bounds_m1))

    # M2 = swap earnings → macro
    print("[M2] vol_idx + macro_event + long_weekend (earnings dropped)…", flush=True)
    t0 = time.time()
    bounds_m2, _ = fc.empirical_quantiles_f1_loglog(
        panel, coverage_levels=COVERAGE_LEVELS, window=156,
        vol_col="vol_idx_fri_close",
        extra_regressors=("macro_event_next_week_f", "is_long_weekend"),
    )
    print(f"  done in {time.time()-t0:.1f}s")
    summaries.append(_summarise("M2_macro_swap", panel, point_fa, bounds_m2))

    df = pd.concat(summaries, ignore_index=True)
    df.to_csv(_tables_dir() / "v1b_macro_ablation.csv", index=False)

    # Print headline pooled at τ=0.95
    print()
    print("=" * 80)
    print("HEADLINE — pooled, τ = 0.95")
    print("=" * 80)
    headline = df[(df["scope"] == "pooled") & (df["claimed"] == 0.95)]
    print(headline.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # Shock tertile (the §9.2 question)
    print()
    print("=" * 80)
    print("SHOCK-TERTILE coverage (the §9.2 question)")
    print("=" * 80)
    shock = df[(df["scope"] == "realized_shock")].sort_values(["claimed", "variant"])
    shock.to_csv(_tables_dir() / "v1b_macro_ablation_shock.csv", index=False)
    print(shock.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # Writeup
    md = [
        "# V1b — Macro-event regressor ablation",
        "",
        "**Question.** Does adding a FRED-derived `macro_event_next_week` flag (FOMC + CPI + NFP) to the F1_emp_regime log-log model close the shock-tertile coverage gap documented in §9.2 of the paper (~80% realized at τ=0.95 in the highest-realized-z-score tertile)?",
        "",
        f"**Calendar.** 324 macro events 2014–2026 (31 FOMC decision dates from DFEDTARU, 146 CPI releases, 147 NFP releases). 48% of weekends have a macro event in the following week — the flag is *frequent*; if shock weekends concentrate within this 48%, we'd expect to see differential coverage improvement.",
        "",
        "## Pooled — τ = 0.95",
        "",
        headline.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Shock-tertile (post-hoc realised-move tertile)",
        "",
        shock.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Reading",
        "",
        "- M0 (deployed) is the baseline. M1 adds the macro flag, M2 swaps earnings for macro.",
        "- A meaningful improvement is +1pp realized in shock-tertile at τ=0.95 with comparable sharpness — a half-pp shift is within bootstrap noise at this n.",
        "- If M1 ≈ M0 (no detectable lift), shock weekends are *not* macro-event-driven. This is itself a paper-relevant finding: §9.2 stays as 'structural ceiling, mechanism unidentified.' If M1 > M0 with CI excluding zero, deploy M1 and update §9.2 to acknowledge the partial fix.",
        "",
        "Raw: `reports/tables/v1b_macro_ablation.csv`, `reports/tables/v1b_macro_ablation_shock.csv`, `data/processed/v1b_macro_calendar.parquet`.",
    ]
    out = REPORTS / "v1b_macro_regressor.md"
    out.write_text("\n".join(md))
    print()
    print(f"Wrote {out}")
    print(f"Wrote {_tables_dir() / 'v1b_macro_ablation.csv'}")
    print(f"Wrote {_tables_dir() / 'v1b_macro_ablation_shock.csv'}")


if __name__ == "__main__":
    main()
