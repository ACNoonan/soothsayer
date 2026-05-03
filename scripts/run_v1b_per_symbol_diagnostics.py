"""
Per-symbol calibration diagnostics for §10 paper-1 robustness pass.

Addresses two reviewer-anticipated gaps:

  G1 — Per-symbol Berkowitz LR. Localises the §6.3.1 LR=173.1 rejection.
        Already computed by `run_density_rejection_diagnostics.py` (M5 row,
        partition_col=symbol). This script reads that CSV and emits a
        paper-ready `v1b_robustness_per_symbol.csv`.

  G8 — Per-symbol Kupiec at the four served τ. HOOD is the spotlight
        ticker (n=246 weekends pooled in across train+OOS). Computed from
        the deployed M5 served bands directly — no refit.

Outputs
-------
  reports/tables/v1b_robustness_per_symbol.csv

  Columns: symbol, n_oos, kupiec_p_{0.68/0.85/0.95/0.99},
           berkowitz_lr, berkowitz_p, var_z (M5 OOS PITs).

Run:
  uv run python scripts/run_v1b_per_symbol_diagnostics.py
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    compute_score,
    fit_split_conformal,
    serve_bands,
)
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)


def per_symbol_kupiec(panel_oos: pd.DataFrame,
                      bounds: dict[float, pd.DataFrame],
                      taus: tuple[float, ...]) -> pd.DataFrame:
    """One row per symbol with Kupiec + violation-rate at each τ."""
    rows = []
    for sym, idx in panel_oos.groupby("symbol").groups.items():
        sub = panel_oos.loc[idx]
        row: dict = {"symbol": sym, "n_oos": int(len(sub))}
        for tau in taus:
            band = bounds[tau].loc[sub.index]
            inside = (sub["mon_open"] >= band["lower"]) & (sub["mon_open"] <= band["upper"])
            v = (~inside).astype(int).to_numpy()
            lr_uc, p_uc = met._lr_kupiec(v, tau)
            row[f"viol_rate_{tau}"] = float(v.mean())
            row[f"kupiec_lr_{tau}"] = lr_uc
            row[f"kupiec_p_{tau}"] = p_uc
        rows.append(row)
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["score"] = compute_score(panel)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    print(f"Panel: {len(panel):,} rows × {panel['fri_ts'].nunique()} weekends",
          flush=True)

    print("[1/3] Re-fitting M5 (split=2023-01-01) and serving deployed bands…",
          flush=True)
    qt, cb, info = fit_split_conformal(panel, SPLIT_DATE, cell_col="regime_pub")
    print(f"      train={info['n_train']:,}  oos={info['n_oos']:,}", flush=True)
    print(f"      c-bumps: {cb}", flush=True)

    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].dropna(subset=["score"]).copy()
    bounds = serve_bands(panel_oos, qt, cb, cell_col="regime_pub", taus=DEFAULT_TAUS)

    # Sanity: pooled coverage should match nominal at each τ (deployed
    # schedule by construction).
    for tau in DEFAULT_TAUS:
        b = bounds[tau]
        cov = ((panel_oos["mon_open"] >= b["lower"]) &
               (panel_oos["mon_open"] <= b["upper"])).mean()
        print(f"      τ={tau:.2f}  pooled OOS realised={cov:.4f}", flush=True)

    print("[2/3] Per-symbol Kupiec at four served τ …", flush=True)
    kup = per_symbol_kupiec(panel_oos, bounds, DEFAULT_TAUS)

    print("[3/3] Loading per-symbol Berkowitz from "
          "v1b_density_rejection_per_partition.csv …", flush=True)
    pp_path = REPORTS / "tables" / "v1b_density_rejection_per_partition.csv"
    if pp_path.exists():
        pp = pd.read_csv(pp_path)
        m5 = pp[(pp["methodology"] == "m5_v2_candidate") &
                (pp["partition_col"] == "symbol")].copy()
        m5 = m5.rename(columns={"partition": "symbol",
                                "berkowitz_lr": "berkowitz_lr_m5",
                                "berkowitz_p": "berkowitz_p_m5",
                                "var_z": "var_z_m5",
                                "rho_hat": "rho_hat_m5"})
        merged = kup.merge(
            m5[["symbol", "berkowitz_lr_m5", "berkowitz_p_m5",
                "var_z_m5", "rho_hat_m5"]],
            on="symbol", how="left",
        )
    else:
        print("      (no Berkowitz CSV found — emitting Kupiec only)",
              flush=True)
        merged = kup

    out_path = REPORTS / "tables" / "v1b_robustness_per_symbol.csv"
    merged.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}\n", flush=True)
    print("=" * 90)
    print("PER-SYMBOL DIAGNOSTICS — M5 OOS (1,730 rows post-2023)")
    print("=" * 90)
    print(merged.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # Spotlight HOOD
    if "HOOD" in merged["symbol"].values:
        hood = merged[merged["symbol"] == "HOOD"].iloc[0]
        n_total_hood = int((panel["symbol"] == "HOOD").sum())
        print()
        print("=" * 90)
        print(f"HOOD spotlight  (panel-total weekends = {n_total_hood}; "
              f"OOS rows = {int(hood['n_oos'])})")
        print("=" * 90)
        for tau in DEFAULT_TAUS:
            print(f"  τ = {tau:.2f}: violation rate = "
                  f"{hood[f'viol_rate_{tau}']:.4f}  "
                  f"(expected = {1-tau:.2f}); Kupiec p = "
                  f"{hood[f'kupiec_p_{tau}']:.3f}")


if __name__ == "__main__":
    main()
