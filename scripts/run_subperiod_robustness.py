"""
M6 Phase 7.2 — Sub-period robustness within OOS.

Splits the 2023+ OOS slice into calendar sub-periods {2023, 2024, 2025,
2026-YTD} and reports per-subperiod pooled OOS metrics under both
forecasters:
  • n (weekend × symbol cells), realised coverage, half-width (bps)
  • Kupiec LR + p
  • Christoffersen lag-1 LR + p (within-symbol, cross-sectional grouped)

§9.2 of Paper 1 currently *discloses* stationarity as a limitation. This
runner converts that disclosure into one of two evidence-backed claims:
  • calibration holds across all four years (positive claim), or
  • a specific year breaks calibration (operating boundary that consumers
    need to know).

A 50-cell minimum threshold is applied per (subperiod × τ × forecaster);
cells below that get a `low_n_flag = 1` so the reporting paragraph can
disclose them. With the current panel (10 symbols × 17–52 weekends per
year), every cell sits well above 50 — the flag is a sanity guard.

Output
------
  reports/tables/m6_subperiod_robustness.csv

Run
---
  uv run python -u scripts/run_subperiod_robustness.py
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
FORECASTERS = ("m5", "lwc")
MIN_N_CELLS = 50

# Inclusive lower / exclusive upper boundaries per subperiod label.
SUBPERIODS: tuple[tuple[str, date, date], ...] = (
    ("2023",     date(2023, 1, 1), date(2024, 1, 1)),
    ("2024",     date(2024, 1, 1), date(2025, 1, 1)),
    ("2025",     date(2025, 1, 1), date(2026, 1, 1)),
    ("2026-YTD", date(2026, 1, 1), date(2027, 1, 1)),
)


def serve_oos(forecaster: str) -> tuple[pd.DataFrame, dict[float, pd.DataFrame]]:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = prep_panel_for_forecaster(panel, forecaster)

    qt, cb, _ = fit_split_conformal_forecaster(
        panel, SPLIT_DATE, forecaster, cell_col="regime_pub",
    )
    oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
           .dropna(subset=["score"])
           .sort_values(["fri_ts", "symbol"])
           .reset_index(drop=True))
    bounds = serve_bands_forecaster(
        oos, qt, cb, forecaster, cell_col="regime_pub", taus=DEFAULT_TAUS,
    )
    return oos, bounds


def metrics_row(
    sub: pd.DataFrame, band: pd.DataFrame, tau: float,
    forecaster: str, label: str,
) -> dict:
    n = int(len(sub))
    if n == 0:
        return {
            "forecaster": forecaster, "subperiod": label, "tau": float(tau),
            "n": 0, "n_weekends": 0,
            "realised": float("nan"), "half_width_bps": float("nan"),
            "kupiec_lr": float("nan"), "kupiec_p": float("nan"),
            "christ_lr": float("nan"), "christ_p": float("nan"),
            "low_n_flag": 1,
        }
    inside = ((sub["mon_open"] >= band["lower"]) &
              (sub["mon_open"] <= band["upper"]))
    v = (~inside).astype(int).to_numpy()
    lr_uc, p_uc = met._lr_kupiec(v, tau)
    cc = met.conditional_coverage_from_bounds(
        sub, {tau: band}, group_by="symbol",
    ).iloc[0]
    return {
        "forecaster": forecaster,
        "subperiod": label,
        "tau": float(tau),
        "n": n,
        "n_weekends": int(sub["fri_ts"].nunique()),
        "realised": float(inside.mean()),
        "half_width_bps": float(((band["upper"] - band["lower"]) / 2
                                 / sub["fri_close"] * 1e4).mean()),
        "kupiec_lr": float(lr_uc),
        "kupiec_p": float(p_uc),
        "christ_lr": float(cc["lr_ind"]),
        "christ_p": float(cc["p_ind"]),
        "low_n_flag": int(n < MIN_N_CELLS),
    }


def main() -> None:
    rows: list[dict] = []
    for fc in FORECASTERS:
        print(f"\n=== {fc.upper()} ===", flush=True)
        oos, bounds = serve_oos(fc)
        print(f"OOS pooled: {len(oos):,} cells × "
              f"{oos['fri_ts'].nunique()} weekends", flush=True)

        for label, lo, hi in SUBPERIODS:
            mask = ((oos["fri_ts"] >= lo) & (oos["fri_ts"] < hi)).to_numpy()
            sub = oos.iloc[mask]
            print(f"  [{label:9s}]  n={len(sub):4d}  "
                  f"weekends={sub['fri_ts'].nunique():3d}", flush=True)
            for tau in DEFAULT_TAUS:
                band = bounds[tau].iloc[mask]
                rows.append(metrics_row(sub, band, tau, fc, label))

    out = pd.DataFrame(rows)
    out_path = REPORTS / "tables" / "m6_subperiod_robustness.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}", flush=True)

    # ----------------------- console summary
    print("\n" + "=" * 100)
    print("SUB-PERIOD ROBUSTNESS — pooled within calendar year")
    print("=" * 100)
    for tau in DEFAULT_TAUS:
        print(f"\n  τ = {tau:.2f}")
        sub = out[out["tau"] == tau][
            ["forecaster", "subperiod", "n", "realised",
             "half_width_bps", "kupiec_p", "christ_p"]
        ].copy()
        pivot = sub.pivot_table(
            index="subperiod", columns="forecaster",
            values=["realised", "half_width_bps", "kupiec_p", "christ_p"],
        )
        print(pivot.to_string(float_format=lambda x: f"{x:.4f}"))

    n_flagged = int(out["low_n_flag"].sum())
    if n_flagged > 0:
        print(f"\n⚠  {n_flagged} (subperiod × τ × forecaster) cells below "
              f"the n={MIN_N_CELLS} threshold; see `low_n_flag` column.",
              flush=True)
    else:
        print(f"\nAll cells above the n={MIN_N_CELLS} minimum threshold.",
              flush=True)


if __name__ == "__main__":
    main()
