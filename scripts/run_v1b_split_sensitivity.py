"""
Split-date sensitivity — §10 paper-1 robustness check.

The headline §6.3 result uses a single 2023-01-01 OOS split. A reviewer
will ask: "did you get lucky on this holdout?" This script repeats the
M5 fit at four split anchors and reports pooled τ=0.95 coverage,
sharpness, Kupiec, and Christoffersen at each.

Method (per split d_split)
--------------------------
  - train     = panel[fri_ts <  d_split]
  - oos       = panel[fri_ts >= d_split]
  - quantile_table = M5 per-regime quantile on train (`_train_quantile`)
  - c_bump_schedule = OOS-fit bump on (oos, quantile_table)
  - δ-shift schedule held at the *deployed* values (selected on the
    6-split walk-forward, not re-tuned per split)
  - serve_bands → realised coverage / mean half-width / Kupiec / Christoffersen

Output: reports/tables/v1b_robustness_split_sensitivity.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    compute_score,
    fit_split_conformal,
    serve_bands,
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


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel["score"] = compute_score(panel)

    print(f"Panel: {len(panel):,} rows × "
          f"{panel['fri_ts'].nunique()} weekends "
          f"({panel['fri_ts'].min()} → {panel['fri_ts'].max()})", flush=True)

    rows = []
    for d_split in SPLIT_ANCHORS:
        qt, cb, info = fit_split_conformal(panel, d_split,
                                           cell_col="regime_pub")
        oos = (panel[panel["fri_ts"] >= d_split]
               .dropna(subset=["score"])
               .sort_values(["symbol", "fri_ts"])
               .reset_index(drop=True))
        bounds = serve_bands(oos, qt, cb, cell_col="regime_pub",
                             taus=DEFAULT_TAUS)
        for tau in DEFAULT_TAUS:
            rows.append({**coverage_row(oos, bounds, d_split, tau),
                         "n_train": info["n_train"]})

    out = pd.DataFrame(rows)
    out_path = REPORTS / "tables" / "v1b_robustness_split_sensitivity.csv"
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
