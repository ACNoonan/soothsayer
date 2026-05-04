"""
Per-asset-class generalisation table — §10 paper-1 robustness check.

The §6.3 OOS table is regime-stratified; §9.8 claims generalisation
across asset classes (equities, gold, treasuries) but reports no
per-class numbers. This script stratifies pooled OOS coverage by asset
class under the active forecaster.

Forecasters
-----------
  --forecaster m5   (default; deployed Mondrian-by-regime)
  --forecaster lwc  (M6 Locally-Weighted Conformal)

Asset-class taxonomy (broader than the M6b2 lending-class mapping):

  equities   = SPY QQQ AAPL GOOGL NVDA TSLA HOOD MSTR  (8 syms)
  gold       = GLD                                       (1 sym)
  treasuries = TLT                                       (1 sym)

For each (class × τ) cell: n, realised, mean half-width, Kupiec p.

Outputs:
  reports/tables/v1b_robustness_per_class.csv         (--forecaster m5)
  reports/tables/m6_lwc_robustness_per_class.csv      (--forecaster lwc)
"""

from __future__ import annotations

import argparse
from datetime import date

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

CLASS_BY_SYMBOL: dict[str, str] = {
    "SPY": "equities", "QQQ": "equities", "AAPL": "equities",
    "GOOGL": "equities", "NVDA": "equities", "TSLA": "equities",
    "HOOD": "equities", "MSTR": "equities",
    "GLD": "gold",
    "TLT": "treasuries",
}


def _output_path(forecaster: str) -> str:
    return (str(REPORTS / "tables" / "v1b_robustness_per_class.csv")
            if forecaster == "m5"
            else str(REPORTS / "tables" / "m6_lwc_robustness_per_class.csv"))


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
    panel["asset_class"] = panel["symbol"].map(CLASS_BY_SYMBOL).fillna("other")

    print(f"Forecaster: {args.forecaster}", flush=True)

    qt, cb, info = fit_split_conformal_forecaster(
        panel, SPLIT_DATE, args.forecaster, cell_col="regime_pub",
    )
    oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
           .dropna(subset=["score"])
           .sort_values(["asset_class", "symbol", "fri_ts"])
           .reset_index(drop=True))
    bounds = serve_bands_forecaster(
        oos, qt, cb, args.forecaster,
        cell_col="regime_pub", taus=DEFAULT_TAUS,
    )
    print(f"OOS panel: {len(oos):,} rows × "
          f"{oos['fri_ts'].nunique()} weekends", flush=True)
    print(oos.groupby("asset_class").size().to_string(), flush=True)

    rows = []
    for cls, idx in oos.groupby("asset_class").groups.items():
        sub = oos.loc[idx]
        for tau in DEFAULT_TAUS:
            b = bounds[tau].loc[idx]
            inside = ((sub["mon_open"] >= b["lower"]) &
                      (sub["mon_open"] <= b["upper"]))
            v = (~inside).astype(int).to_numpy()
            lr_uc, p_uc = met._lr_kupiec(v, tau)
            rows.append({
                "asset_class": cls,
                "n_symbols": int(sub["symbol"].nunique()),
                "tau": tau,
                "n": int(len(sub)),
                "realised": float(inside.mean()),
                "half_width_bps": float(((b["upper"] - b["lower"]) / 2 /
                                         sub["fri_close"] * 1e4).mean()),
                "kupiec_lr": float(lr_uc),
                "kupiec_p": float(p_uc),
            })

    out = pd.DataFrame(rows)
    out["forecaster"] = args.forecaster
    out_path = _output_path(args.forecaster)
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}\n", flush=True)
    print("=" * 80)
    print("PER-CLASS POOLED OOS COVERAGE")
    print("=" * 80)
    pivot = out.pivot_table(
        index=["asset_class", "n_symbols"], columns="tau",
        values=["realised", "half_width_bps", "kupiec_p"]
    )
    print(pivot.to_string(float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
