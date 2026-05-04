"""
Leave-one-symbol-out CV — §10 paper-1 robustness check.

Hardens schedule provenance more than the 6-split walk-forward.
For each of the 10 symbols s_i:

  - Hold out *all of s_i's rows* from the calibration set.
  - Fit quantile_table on (train \\ s_i) and c-bump on (oos \\ s_i).
  - Evaluate τ=0.95 coverage on s_i's OOS rows under that held-out fit.

  ↳ Tests whether the deployed schedule generalises across symbols.

LWC twist: σ̂_sym(t) is per-symbol pre-Friday, so dropping s_i from the
panel does NOT zero its scale at evaluation — the held-out symbol has
its own σ̂_sym from its own past. The held-out generalisation question
becomes: "do the per-regime LWC quantiles fit on the other 9 symbols
calibrate s_i's standardised residuals?"

Outputs:
  reports/tables/v1b_robustness_loso.csv         (--forecaster m5)
  reports/tables/m6_lwc_robustness_loso.csv      (--forecaster lwc)
"""

from __future__ import annotations

import argparse
from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    fit_c_bump_schedule,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
    train_quantile_table,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)


def _output_path(forecaster: str) -> str:
    return (str(REPORTS / "tables" / "v1b_robustness_loso.csv")
            if forecaster == "m5"
            else str(REPORTS / "tables" / "m6_lwc_robustness_loso.csv"))


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

    symbols = sorted(panel["symbol"].unique())
    print(f"Forecaster: {args.forecaster}", flush=True)
    print(f"Panel: {len(panel):,} rows × "
          f"{len(symbols)} symbols × "
          f"{panel['fri_ts'].nunique()} weekends", flush=True)

    rows = []
    for held in symbols:
        keep = panel[panel["symbol"] != held]
        train = keep[keep["fri_ts"] < SPLIT_DATE].dropna(subset=["score"])
        oos_for_cb = keep[keep["fri_ts"] >= SPLIT_DATE].dropna(subset=["score"])
        held_oos = (panel[(panel["symbol"] == held) &
                          (panel["fri_ts"] >= SPLIT_DATE)]
                    .dropna(subset=["score"])
                    .sort_values("fri_ts")
                    .reset_index(drop=True))
        if len(held_oos) < 30:
            print(f"  {held}: only {len(held_oos)} OOS rows — skipping",
                  flush=True)
            continue
        qt = train_quantile_table(train, cell_col="regime_pub",
                                  taus=DEFAULT_TAUS)
        cb = fit_c_bump_schedule(oos_for_cb, qt, cell_col="regime_pub",
                                 taus=DEFAULT_TAUS)
        bounds = serve_bands_forecaster(
            held_oos, qt, cb, args.forecaster,
            cell_col="regime_pub", taus=DEFAULT_TAUS,
        )
        for tau in DEFAULT_TAUS:
            b = bounds[tau]
            inside = ((held_oos["mon_open"] >= b["lower"]) &
                      (held_oos["mon_open"] <= b["upper"]))
            v = (~inside).astype(int).to_numpy()
            lr_uc, p_uc = met._lr_kupiec(v, tau)
            rows.append({
                "held_out_symbol": held,
                "n_held_oos": int(len(held_oos)),
                "tau": tau,
                "realised": float(inside.mean()),
                "half_width_bps": float(((b["upper"] - b["lower"]) / 2 /
                                         held_oos["fri_close"] * 1e4).mean()),
                "kupiec_lr": float(lr_uc),
                "kupiec_p": float(p_uc),
                "n_train": int(len(train)),
                "c_bump": cb[tau],
            })
        print(f"  {held}: τ=0.95 realised "
              f"{rows[-2]['realised']:.4f}  "
              f"hw {rows[-2]['half_width_bps']:.0f} bps  "
              f"Kupiec p {rows[-2]['kupiec_p']:.3f}", flush=True)

    out = pd.DataFrame(rows)
    out["forecaster"] = args.forecaster
    out_path = _output_path(args.forecaster)
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}", flush=True)

    print("\n" + "=" * 90)
    print("LOSO @ τ = 0.95  — should match nominal 0.95 if schedule generalises")
    print("=" * 90)
    sub = out[out["tau"] == 0.95][
        ["held_out_symbol", "n_held_oos", "realised",
         "half_width_bps", "kupiec_p"]
    ]
    print(sub.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\nLOSO mean realised at τ=0.95: {sub['realised'].mean():.4f}  "
          f"std: {sub['realised'].std():.4f}")
    print(f"LOSO mean half-width at τ=0.95: {sub['half_width_bps'].mean():.1f} bps")


if __name__ == "__main__":
    main()
