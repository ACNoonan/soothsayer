"""Per-symbol master grid — Kupiec + Christoffersen + DQ + half-width.

Extends scripts/run_per_symbol_kupiec_all_methods.py with the additional
columns the Paper-1 §6.4.2 master table requires: per-(symbol, method, τ)
Christoffersen independence p, Engle-Manganelli DQ p, and mean half-width
in basis points of Friday close.

Output
------
  reports/tables/m6_per_symbol_master_grid.csv
      Long-format: 10 symbols × 5 methods × 4 τ = 200 rows.

DQ specification
----------------
  Engle-Manganelli (2004) Dynamic Quantile test with K=4 lagged hits and
  no contemporaneous covariate (CAViaR §4 Table 1, regressor block 1
  "constant + lagged hits"). Sample size per (symbol × τ) cell is
  n=173 weekends; per-symbol DQ has limited power against tail
  conditional miscalibration, so we report p alongside Kupiec/
  Christoffersen rather than as a stand-alone gate. CAViaR Tables 3-8
  also report DQ with a `(VaR)`-conditioned variant; that variant
  requires a per-cell point forecast which is not symmetric across the
  five methods compared here, so we report the lag-only specification
  for direct cross-method comparison.

Methods compared (per-symbol, OOS 2023-01-01+):
  - constant_buffer  — global symmetric buffer, train-fit (§7.1.1)
  - garch_gaussian   — GARCH(1,1)-N (§6.4.3)
  - garch_t          — GARCH(1,1)-t (§6.4.3); NVDA falls back to N at ν→2.5
  - m5               — unweighted Mondrian conformal (§7.2)
  - lwc              — deployed M6 Locally-Weighted Conformal (§4)

Run
---
  uv run python -u scripts/run_per_symbol_master_grid.py
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

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
GARCH_DISTS = ("gaussian", "t")
DEPLOYED_FORECASTERS = ("m5", "lwc")
DQ_LAGS = 4

_GARCH_PATH = Path(__file__).resolve().parent / "run_v1b_garch_baseline.py"
_spec = importlib.util.spec_from_file_location(
    "_run_v1b_garch_baseline", _GARCH_PATH,
)
_garch = importlib.util.module_from_spec(_spec)
sys.modules["_run_v1b_garch_baseline"] = _garch
_spec.loader.exec_module(_garch)
fit_per_symbol_garch = _garch.fit_per_symbol_garch
serve_garch_bands = _garch.serve_garch_bands


def per_symbol_master_row(
    panel: pd.DataFrame,
    bounds: dict[float, pd.DataFrame],
    method: str,
    taus: tuple[float, ...] = DEFAULT_TAUS,
) -> pd.DataFrame:
    """One row per (symbol, τ) with the master-grid metric set."""
    rows: list[dict] = []
    for sym, idx in panel.groupby("symbol").groups.items():
        sub = panel.loc[idx].sort_values("fri_ts")
        sub_idx = sub.index
        fri_close = sub["fri_close"].to_numpy(dtype=float)
        for tau in taus:
            band = bounds[tau].loc[sub_idx]
            inside = ((sub["mon_open"] >= band["lower"]) &
                      (sub["mon_open"] <= band["upper"]))
            v = (~inside).astype(int).to_numpy()
            half_width = ((band["upper"].to_numpy() - band["lower"].to_numpy())
                          / 2.0)
            half_width_bps = float(np.nanmean(
                10_000.0 * half_width / fri_close
            ))
            lr_uc, p_uc = met._lr_kupiec(v, tau)
            lr_ind, p_ind = met._lr_christoffersen_independence(v)
            dq = met.dynamic_quantile_test(v, tau, n_lags=DQ_LAGS)
            rows.append({
                "symbol": sym,
                "method": method,
                "tau": float(tau),
                "n_oos": int(len(sub)),
                "viol_rate": float(v.mean()),
                "half_width_bps": half_width_bps,
                "kupiec_lr": float(lr_uc),
                "kupiec_p": float(p_uc),
                "christoffersen_lr": float(lr_ind),
                "christoffersen_p": float(p_ind),
                "dq_lr": float(dq["dq"]),
                "dq_p": float(dq["p_value"]),
                "dq_n": int(dq["n"]),
                "dq_df": int(dq["df"]),
            })
    return pd.DataFrame(rows)


def garch_per_symbol_grid(
    panel_full: pd.DataFrame, dist: str,
) -> pd.DataFrame:
    forecasts = fit_per_symbol_garch(panel_full, dist)
    forecasts["fri_ts"] = pd.to_datetime(forecasts["fri_ts"]).dt.date
    fc_oos = (forecasts[forecasts["fri_ts"] >= SPLIT_DATE]
              .dropna(subset=["sigma_hat"])
              .reset_index(drop=True))
    bounds = serve_garch_bands(fc_oos, DEFAULT_TAUS)
    return per_symbol_master_row(fc_oos, bounds, f"garch_{dist}")


def deployed_per_symbol_grid(
    panel_raw: pd.DataFrame, forecaster: str,
) -> pd.DataFrame:
    panel = prep_panel_for_forecaster(panel_raw.copy(), forecaster)
    qt, cb, _ = fit_split_conformal_forecaster(
        panel, SPLIT_DATE, forecaster, cell_col="regime_pub",
    )
    panel_oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
                 .dropna(subset=["score"])
                 .sort_values(["symbol", "fri_ts"])
                 .reset_index(drop=True))
    bounds = serve_bands_forecaster(
        panel_oos, qt, cb, forecaster,
        cell_col="regime_pub", taus=DEFAULT_TAUS,
    )
    return per_symbol_master_row(panel_oos, bounds, forecaster)


def constant_buffer_per_symbol_grid(
    panel_raw: pd.DataFrame,
) -> pd.DataFrame:
    """Train-fit global symmetric buffer baseline (§7.1.1)."""
    panel = panel_raw.copy()
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close"]
    ).reset_index(drop=True)
    rel_resid = ((panel["mon_open"] - panel["fri_close"]).abs()
                 / panel["fri_close"]).to_numpy(dtype=float)
    train_mask = panel["fri_ts"] < SPLIT_DATE
    train_resid = rel_resid[train_mask.to_numpy()]
    bounds_dict: dict[float, pd.DataFrame] = {}
    for tau in DEFAULT_TAUS:
        b = float(np.quantile(train_resid, tau))
        fri = panel["fri_close"].to_numpy(dtype=float)
        bounds_dict[tau] = pd.DataFrame({
            "lower": fri * (1.0 - b),
            "upper": fri * (1.0 + b),
        }, index=panel.index)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].copy()
    bounds_oos = {tau: bounds_dict[tau].loc[panel_oos.index]
                  for tau in DEFAULT_TAUS}
    return per_symbol_master_row(panel_oos, bounds_oos, "constant_buffer")


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    print(f"Panel: {len(panel):,} rows × "
          f"{panel['fri_ts'].nunique()} weekends × "
          f"{panel['symbol'].nunique()} symbols", flush=True)

    frames: list[pd.DataFrame] = []

    print("\n[constant_buffer] per-symbol grid …", flush=True)
    frames.append(constant_buffer_per_symbol_grid(panel))

    for dist in GARCH_DISTS:
        print(f"\n[GARCH-{dist}] per-symbol grid …", flush=True)
        frames.append(garch_per_symbol_grid(panel, dist))

    for fc in DEPLOYED_FORECASTERS:
        print(f"\n[{fc}] per-symbol grid …", flush=True)
        frames.append(deployed_per_symbol_grid(panel, fc))

    out = pd.concat(frames, ignore_index=True)
    out_path = REPORTS / "tables" / "m6_per_symbol_master_grid.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}", flush=True)
    print(f"  rows: {len(out)}  "
          f"(expected {out['symbol'].nunique()} sym × "
          f"{out['method'].nunique()} methods × "
          f"{out['tau'].nunique()} τ = "
          f"{out['symbol'].nunique() * out['method'].nunique() * out['tau'].nunique()})",
          flush=True)

    print("\n" + "=" * 100)
    print("MASTER GRID — pass-counts at α = 0.05 (out of 10 symbols)")
    print("=" * 100)
    method_order = ["constant_buffer", "garch_gaussian", "garch_t", "m5", "lwc"]
    for tau in DEFAULT_TAUS:
        print(f"\nτ = {tau:.2f}")
        sub = out[out["tau"] == tau]
        for method in method_order:
            m = sub[sub["method"] == method]
            kup = int((m["kupiec_p"] >= 0.05).sum())
            chr = int((m["christoffersen_p"] >= 0.05).sum())
            dq = int((m["dq_p"] >= 0.05).sum())
            hw = float(m["half_width_bps"].mean())
            print(f"  {method:>16s}:  Kupiec {kup:>2d}/10  "
                  f"Christ {chr:>2d}/10  DQ {dq:>2d}/10  "
                  f"hw̄ {hw:>7.1f} bps")


if __name__ == "__main__":
    main()
