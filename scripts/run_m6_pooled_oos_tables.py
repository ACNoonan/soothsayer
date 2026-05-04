"""
M6 pooled OOS table + realised-move tertile decomposition — Phase 2.9.

Two paper-ready tables in one runner. Both stratifications are produced
under both forecasters (M5 deployed + M6 LWC) so the §6 results section
of `reports/m6_validation.md` can present a side-by-side.

Tables
------

(1) Pooled OOS at every served τ ∈ {0.68, 0.85, 0.95, 0.99}:
    n, realised, half_width_bps, kupiec p, christoffersen p, c_bump, δ.
    Mirrors §6.3.1 of the paper.

(2) Realised-move tertile decomposition at every τ:
    rows = pooled / calm / normal / shock × forecaster.
    The `realized_bucket` column is the |z-score|-tertile produced by
    `regimes.tag()` and persisted on `v1b_panel.parquet`.

Outputs
-------
  reports/tables/m6_pooled_oos.csv              (both forecasters)
  reports/tables/m6_realised_move_tertile.csv   (both forecasters)

Run
---
  uv run python scripts/run_m6_pooled_oos_tables.py
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
BUCKET_ORDER = ("calm", "normal", "shock")


def _serve_oos(forecaster: str) -> tuple[pd.DataFrame, dict, dict]:
    """Return (oos_panel, bounds_dict, info_dict). bounds_dict[tau] is a
    DataFrame indexed by oos_panel.index."""
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = prep_panel_for_forecaster(panel, forecaster)

    qt, cb, info = fit_split_conformal_forecaster(
        panel, SPLIT_DATE, forecaster, cell_col="regime_pub",
    )
    oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
           .dropna(subset=["score"])
           .sort_values(["fri_ts", "symbol"])
           .reset_index(drop=True))
    bounds = serve_bands_forecaster(
        oos, qt, cb, forecaster, cell_col="regime_pub", taus=DEFAULT_TAUS,
    )
    info["c_bump_schedule"] = cb
    return oos, bounds, info


def _row_metrics(panel: pd.DataFrame, band: pd.DataFrame, tau: float,
                 row_label: dict) -> dict:
    inside = ((panel["mon_open"] >= band["lower"]) &
              (panel["mon_open"] <= band["upper"]))
    v = (~inside).astype(int).to_numpy()
    lr_uc, p_uc = met._lr_kupiec(v, tau)
    cc = met.conditional_coverage_from_bounds(
        panel, {tau: band}, group_by="symbol"
    )
    cc0 = cc.iloc[0]
    return {
        **row_label,
        "tau": float(tau),
        "n": int(len(panel)),
        "realised": float(inside.mean()),
        "half_width_bps": float(((band["upper"] - band["lower"]) / 2
                                 / panel["fri_close"] * 1e4).mean()),
        "kupiec_lr": float(lr_uc),
        "kupiec_p": float(p_uc),
        "christ_lr": float(cc0["lr_ind"]),
        "christ_p": float(cc0["p_ind"]),
    }


def main() -> None:
    pooled_rows = []
    tertile_rows = []

    for forecaster in FORECASTERS:
        oos, bounds, info = _serve_oos(forecaster)
        cb = info["c_bump_schedule"]
        delta_schedule = (
            {0.68: 0.05, 0.85: 0.02, 0.95: 0.0, 0.99: 0.0}
            if forecaster == "m5"
            else {0.68: 0.0, 0.85: 0.0, 0.95: 0.0, 0.99: 0.0}
        )
        print(f"\n=== {forecaster.upper()} === "
              f"n_oos = {len(oos):,} rows × "
              f"{oos['fri_ts'].nunique()} weekends", flush=True)

        # (1) Pooled at each τ.
        for tau in DEFAULT_TAUS:
            row = _row_metrics(oos, bounds[tau], tau,
                               {"forecaster": forecaster, "stratification": "pooled"})
            row["c_bump"] = float(cb[tau])
            row["delta"] = float(delta_schedule[tau])
            pooled_rows.append(row)

        # (2) Realised-move tertile decomposition at each τ.
        if "realized_bucket" in oos.columns:
            for tau in DEFAULT_TAUS:
                # Pooled row in the tertile table for direct comparison.
                tertile_rows.append({
                    **_row_metrics(oos, bounds[tau], tau,
                                   {"forecaster": forecaster, "tertile": "pooled"}),
                })
                for bk in BUCKET_ORDER:
                    mask = (oos["realized_bucket"] == bk).to_numpy()
                    sub = oos[mask].copy()
                    sub_band = bounds[tau].iloc[mask]
                    if len(sub) == 0:
                        continue
                    tertile_rows.append(
                        _row_metrics(
                            sub, sub_band, tau,
                            {"forecaster": forecaster, "tertile": bk},
                        )
                    )
        else:
            print(f"   (skipping realised-move tertile — `realized_bucket` "
                  "not on panel)", flush=True)

    pooled = pd.DataFrame(pooled_rows)
    tertile = pd.DataFrame(tertile_rows)

    out_pooled = REPORTS / "tables" / "m6_pooled_oos.csv"
    out_tertile = REPORTS / "tables" / "m6_realised_move_tertile.csv"
    pooled.to_csv(out_pooled, index=False)
    tertile.to_csv(out_tertile, index=False)
    print(f"\nWrote {out_pooled}", flush=True)
    print(f"Wrote {out_tertile}\n", flush=True)

    print("=" * 100)
    print("POOLED OOS — both forecasters, all four τ")
    print("=" * 100)
    pooled_view = pooled.pivot_table(
        index=["forecaster", "stratification"], columns="tau",
        values=["realised", "half_width_bps", "kupiec_p", "christ_p"],
    )
    print(pooled_view.to_string(float_format=lambda x: f"{x:.4f}"))

    print("\n" + "=" * 100)
    print("REALISED-MOVE TERTILE @ τ=0.95 — both forecasters")
    print("=" * 100)
    sub = tertile[tertile["tau"] == 0.95][
        ["forecaster", "tertile", "n", "realised", "half_width_bps",
         "kupiec_p"]
    ]
    print(sub.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
