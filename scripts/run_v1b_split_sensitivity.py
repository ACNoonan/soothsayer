"""
Split-date sensitivity — §10 paper-1 robustness check.

The headline §6.3 result uses a single 2023-01-01 OOS split. A reviewer
will ask: "did you get lucky on this holdout?" This script repeats the
fit at four split anchors and reports pooled τ=0.95 coverage, sharpness,
Kupiec, and Christoffersen at each, under the active forecaster.

Forecasters
-----------
  --forecaster m5   (default; deployed Mondrian-by-regime)
  --forecaster lwc  (M6 Locally-Weighted Conformal)

Method (per split d_split)
--------------------------
  - train     = panel[fri_ts <  d_split]
  - oos       = panel[fri_ts >= d_split]
  - quantile_table = per-regime CP quantile on train (active score)
  - c_bump_schedule = OOS-fit bump on (oos, quantile_table)
  - δ-shift schedule held at the deployed values for the active
    forecaster (M5 = {0.05, 0.02, 0, 0}, LWC = {0, 0, 0, 0})
  - serve_bands → realised coverage / half-width / Kupiec / Christoffersen

Outputs:
  reports/tables/v1b_robustness_split_sensitivity.csv     (--forecaster m5)
  reports/tables/m6_lwc_robustness_split_sensitivity.csv  (--forecaster lwc)
"""

from __future__ import annotations

import argparse
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

SPLIT_ANCHORS = (date(2021, 1, 1), date(2022, 1, 1),
                 date(2023, 1, 1), date(2024, 1, 1))


def coverage_row(panel_oos: pd.DataFrame,
                 bounds: dict[float, pd.DataFrame],
                 split_d: date, tau: float) -> dict:
    b = bounds[tau]
    inside = ((panel_oos["mon_open"] >= b["lower"]) &
              (panel_oos["mon_open"] <= b["upper"]))
    v = (~inside).astype(int).to_numpy()
    lr_uc, p_uc = met._lr_kupiec(v, tau)
    cc = met.conditional_coverage_from_bounds(
        panel_oos, {tau: b}, group_by="symbol"
    )
    cc0 = cc.iloc[0]
    return {
        "split_date": split_d.isoformat(),
        "tau": tau,
        "n_oos": int(len(panel_oos)),
        "n_oos_weekends": int(panel_oos["fri_ts"].nunique()),
        "realised": float(inside.mean()),
        "half_width_bps": float(((b["upper"] - b["lower"]) / 2 /
                                 panel_oos["fri_close"] * 1e4).mean()),
        "kupiec_lr": float(lr_uc),
        "kupiec_p": float(p_uc),
        "christ_lr": float(cc0["lr_ind"]),
        "christ_p": float(cc0["p_ind"]),
    }


def _output_path(forecaster: str) -> str:
    return (str(REPORTS / "tables" / "v1b_robustness_split_sensitivity.csv")
            if forecaster == "m5"
            else str(REPORTS / "tables" / "m6_lwc_robustness_split_sensitivity.csv"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecaster", choices=("m5", "lwc"), default="m5")
    args = parser.parse_args()

    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = prep_panel_for_forecaster(panel, args.forecaster)

    print(f"Forecaster: {args.forecaster}", flush=True)
    print(f"Panel: {len(panel):,} rows × "
          f"{panel['fri_ts'].nunique()} weekends "
          f"({panel['fri_ts'].min()} → {panel['fri_ts'].max()})", flush=True)

    rows = []
    for d_split in SPLIT_ANCHORS:
        qt, cb, info = fit_split_conformal_forecaster(
            panel, d_split, args.forecaster, cell_col="regime_pub",
        )
        oos = (panel[panel["fri_ts"] >= d_split]
               .dropna(subset=["score"])
               .sort_values(["symbol", "fri_ts"])
               .reset_index(drop=True))
        bounds = serve_bands_forecaster(
            oos, qt, cb, args.forecaster,
            cell_col="regime_pub", taus=DEFAULT_TAUS,
        )
        for tau in DEFAULT_TAUS:
            rows.append({**coverage_row(oos, bounds, d_split, tau),
                         "n_train": info["n_train"],
                         "forecaster": args.forecaster})

    out = pd.DataFrame(rows)
    out_path = _output_path(args.forecaster)
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}\n", flush=True)

    print("=" * 100)
    print("PER-SPLIT POOLED COVERAGE (deployed δ-shift schedule, c-bump refit per split)")
    print("=" * 100)
    pivot = out.pivot_table(
        index="split_date", columns="tau",
        values=["realised", "half_width_bps", "kupiec_p", "christ_p"]
    )
    print(pivot.to_string(float_format=lambda x: f"{x:.4f}"))

    print("\n" + "=" * 100)
    print("τ = 0.95 ROW")
    print("=" * 100)
    sub = out[out["tau"] == 0.95][
        ["split_date", "n_train", "n_oos", "n_oos_weekends",
         "realised", "half_width_bps", "kupiec_p", "christ_p"]
    ]
    print(sub.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
