"""
Per-symbol calibration diagnostics for §10 paper-1 robustness pass.

Addresses two reviewer-anticipated gaps:

  G1 — Per-symbol Berkowitz LR. Localises the §6.3.1 LR=173.1 rejection.
        Already computed by `run_density_rejection_diagnostics.py` (M5 row,
        partition_col=symbol). This script reads that CSV and emits a
        paper-ready `v1b_robustness_per_symbol.csv`.

  G8 — Per-symbol Kupiec at the four served τ. HOOD is the spotlight
        ticker (n=246 weekends pooled in across train+OOS). Computed from
        the served bands directly — no refit.

Forecasters
-----------
  --forecaster m5   (default; deployed Mondrian-by-regime). Output:
                    reports/tables/v1b_robustness_per_symbol.csv
  --forecaster lwc  (M6 Locally-Weighted Conformal). Output:
                    reports/tables/m6_lwc_robustness_per_symbol.csv

Per-symbol Berkowitz LR is computed inline for each forecaster (the original
script merged in numbers from a separate density-rejection CSV; under M6
that CSV doesn't exist yet, so we compute Berkowitz here too).

Outputs
-------
  reports/tables/v1b_robustness_per_symbol.csv             (--forecaster m5)
  reports/tables/m6_lwc_robustness_per_symbol.csv          (--forecaster lwc)

  Columns: symbol, n_oos, kupiec_p_{0.68/0.85/0.95/0.99},
           berkowitz_lr, berkowitz_p, var_z, rho_hat
           (and merged-from-CSV M5 reference under --forecaster m5).

Run:
  uv run python scripts/run_v1b_per_symbol_diagnostics.py --forecaster m5
  uv run python scripts/run_v1b_per_symbol_diagnostics.py --forecaster lwc
"""

from __future__ import annotations

import argparse
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import norm

from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)

# Dense PIT τ-grid; matches `run_density_rejection_diagnostics.py` and the
# v3 bake-off PIT construction.
PIT_DENSE_GRID = (
    0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.68, 0.70, 0.80, 0.85,
    0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999,
)


def _interp_table(table: dict[float, float], x: float) -> float:
    keys = sorted(table.keys())
    if x <= keys[0]:
        return float(table[keys[0]])
    if x >= keys[-1]:
        return float(table[keys[-1]])
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= x <= hi:
            frac = (x - lo) / (hi - lo)
            return float(table[lo] + frac * (table[hi] - table[lo]))
    return float(table[keys[-1]])


def build_pits(
    panel: pd.DataFrame,
    qt: dict[str, dict[float, float]],
    cb: dict[float, float],
    forecaster: str,
    cell_col: str = "regime_pub",
    dense_grid: tuple[float, ...] = PIT_DENSE_GRID,
) -> np.ndarray:
    """Per-row PITs at the served-band CDF, dense τ grid.

    Caller must order `panel` by (fri_ts, symbol) so the lag-1 in Berkowitz
    captures cross-sectional within-weekend AR(1) — the §6.3.1 frame.

    For LWC the half-width anchors are q · c · σ̂ · fri_close (price units);
    for M5 they are q · c · fri_close. Both fold into the symmetric CDF
    F(point ± half) = 0.5 ± τ/2."""
    grid_taus = np.array(sorted(dense_grid))
    point = (panel["fri_close"].astype(float)
             * (1.0 + panel["factor_ret"].astype(float))).to_numpy()
    fri_close = panel["fri_close"].astype(float).to_numpy()
    mon_open = panel["mon_open"].astype(float).to_numpy()
    cells = panel[cell_col].astype(str).to_numpy()
    sigma = (panel["sigma_hat_sym_pre_fri"].to_numpy(float)
             if forecaster == "lwc" else None)

    pits = np.full(len(panel), np.nan)
    for i in range(len(panel)):
        q_row = qt.get(cells[i])
        if q_row is None:
            continue
        b_anchors = np.array(
            [_interp_table(q_row, tau) * _interp_table(cb, tau)
             for tau in grid_taus],
            dtype=float,
        )
        scale = fri_close[i]
        if forecaster == "lwc":
            s = sigma[i]
            if not (np.isfinite(s) and s > 0):
                continue
            scale = scale * s
        if not (np.isfinite(scale) and scale > 0):
            continue
        half_i = b_anchors * scale
        if not np.all(np.isfinite(half_i)):
            continue
        r = mon_open[i] - point[i]
        abs_r = abs(r)
        anchor_b = np.concatenate(([0.0], half_i))
        anchor_tau = np.concatenate(([0.0], grid_taus))
        if abs_r >= anchor_b[-1]:
            tau_hat = anchor_tau[-1]
        else:
            tau_hat = float(np.interp(abs_r, anchor_b, anchor_tau))
        pits[i] = 0.5 + 0.5 * tau_hat * (1 if r >= 0 else -1)
    return pits


def per_symbol_berkowitz(
    panel: pd.DataFrame,
    qt: dict[str, dict[float, float]],
    cb: dict[float, float],
    forecaster: str,
) -> pd.DataFrame:
    """Berkowitz LR + p + var_z + rho_hat per symbol on OOS PITs."""
    rows = []
    for sym, idx in panel.groupby("symbol").groups.items():
        sub = panel.loc[idx].sort_values("fri_ts").reset_index(drop=True)
        pits = build_pits(sub, qt, cb, forecaster)
        clean = pits[(np.isfinite(pits)) & (pits > 0) & (pits < 1)]
        if len(clean) < 30:
            rows.append({"symbol": sym, "berkowitz_lr": float("nan"),
                         "berkowitz_p": float("nan"),
                         "var_z": float("nan"),
                         "rho_hat": float("nan"),
                         "berkowitz_n": int(len(clean))})
            continue
        bw = met.berkowitz_test(clean)
        rows.append({"symbol": sym,
                     "berkowitz_lr": float(bw.get("lr", float("nan"))),
                     "berkowitz_p": float(bw.get("p_value", float("nan"))),
                     "var_z": float(bw.get("var_z", float("nan"))),
                     "rho_hat": float(bw.get("rho_hat", float("nan"))),
                     "berkowitz_n": int(bw.get("n", len(clean)))})
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


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


def _output_path(forecaster: str) -> str:
    return (str(REPORTS / "tables" / "v1b_robustness_per_symbol.csv")
            if forecaster == "m5"
            else str(REPORTS / "tables" / "m6_lwc_robustness_per_symbol.csv"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecaster", choices=("m5", "lwc"), default="m5",
                        help="Active methodology — m5 (deployed) or lwc (M6).")
    args = parser.parse_args()

    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = prep_panel_for_forecaster(panel, args.forecaster)

    print(f"Forecaster: {args.forecaster}", flush=True)
    print(f"Panel: {len(panel):,} rows × {panel['fri_ts'].nunique()} weekends",
          flush=True)

    print(f"[1/3] Re-fitting {args.forecaster.upper()} "
          f"(split=2023-01-01) and serving deployed bands…", flush=True)
    qt, cb, info = fit_split_conformal_forecaster(
        panel, SPLIT_DATE, args.forecaster, cell_col="regime_pub",
    )
    print(f"      train={info['n_train']:,}  oos={info['n_oos']:,}", flush=True)
    print(f"      c-bumps: {cb}", flush=True)

    panel_oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
                 .dropna(subset=["score"]).copy())
    bounds = serve_bands_forecaster(
        panel_oos, qt, cb, args.forecaster,
        cell_col="regime_pub", taus=DEFAULT_TAUS,
    )

    # Sanity: pooled coverage at the deployed schedule.
    for tau in DEFAULT_TAUS:
        b = bounds[tau]
        cov = ((panel_oos["mon_open"] >= b["lower"]) &
               (panel_oos["mon_open"] <= b["upper"])).mean()
        print(f"      τ={tau:.2f}  pooled OOS realised={cov:.4f}", flush=True)

    print("[2/3] Per-symbol Kupiec at four served τ …", flush=True)
    kup = per_symbol_kupiec(panel_oos, bounds, DEFAULT_TAUS)

    print("[3/3] Per-symbol Berkowitz on OOS PITs (dense grid) …", flush=True)
    bw = per_symbol_berkowitz(panel_oos, qt, cb, args.forecaster)
    merged = kup.merge(bw, on="symbol", how="left")

    if args.forecaster == "m5":
        # Optional cross-reference into the legacy density-rejection CSV
        # produced by `run_density_rejection_diagnostics.py`. Tagged
        # `_legacy_csv` so the new inline columns above stay primary.
        pp_path = REPORTS / "tables" / "v1b_density_rejection_per_partition.csv"
        if pp_path.exists():
            pp = pd.read_csv(pp_path)
            m5_legacy = pp[(pp["methodology"] == "m5_v2_candidate") &
                           (pp["partition_col"] == "symbol")].copy()
            m5_legacy = m5_legacy.rename(
                columns={"partition": "symbol",
                         "berkowitz_lr": "berkowitz_lr_legacy_csv",
                         "berkowitz_p": "berkowitz_p_legacy_csv",
                         "var_z": "var_z_legacy_csv",
                         "rho_hat": "rho_hat_legacy_csv"}
            )
            merged = merged.merge(
                m5_legacy[["symbol", "berkowitz_lr_legacy_csv",
                           "berkowitz_p_legacy_csv",
                           "var_z_legacy_csv", "rho_hat_legacy_csv"]],
                on="symbol", how="left",
            )

    out_path = _output_path(args.forecaster)
    merged.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}\n", flush=True)
    print("=" * 100)
    print(f"PER-SYMBOL DIAGNOSTICS — {args.forecaster.upper()} OOS "
          f"({info['n_oos']} rows post-2023)")
    print("=" * 100)
    print(merged.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # Headline at τ=0.95: how many symbols pass Kupiec?
    n_pass_95 = int((merged["kupiec_p_0.95"] >= 0.05).sum())
    n_total = len(merged)
    print(f"\nKupiec τ=0.95 pass rate (p ≥ 0.05): {n_pass_95}/{n_total} symbols",
          flush=True)

    # Spotlight HOOD
    if "HOOD" in merged["symbol"].values:
        hood = merged[merged["symbol"] == "HOOD"].iloc[0]
        n_total_hood = int((panel["symbol"] == "HOOD").sum())
        print()
        print("=" * 100)
        print(f"HOOD spotlight  (panel-total weekends = {n_total_hood}; "
              f"OOS rows = {int(hood['n_oos'])})")
        print("=" * 100)
        for tau in DEFAULT_TAUS:
            print(f"  τ = {tau:.2f}: violation rate = "
                  f"{hood[f'viol_rate_{tau}']:.4f}  "
                  f"(expected = {1-tau:.2f}); Kupiec p = "
                  f"{hood[f'kupiec_p_{tau}']:.3f}")


if __name__ == "__main__":
    main()
