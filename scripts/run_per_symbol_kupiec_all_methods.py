"""
M6 Phase 8.2 — Per-symbol Kupiec across all four §6.4.1 methods.

The §6.4.1 per-symbol generalization claim in Paper 1 currently reads
"M6 LWC: 10/10 Kupiec passes vs M5: 2/10". Phase 8.2 extends the
comparison to the strongest parametric baseline at the per-symbol level:
adds **GARCH(1,1)-Gaussian** and **GARCH(1,1)-t** to the headline table.

Methods compared (per-symbol, OOS 2023-01-01+):
  - garch_gaussian — Phase 7.3 / §6.4.2 baseline at default `--dist gaussian`
  - garch_t        — Phase 7.3 standardised-t innovations
  - m5             — deployed Mondrian-by-regime
  - lwc            — deployed M6 Locally-Weighted Conformal

For each (symbol, method, τ ∈ {0.68, 0.85, 0.95, 0.99}) cell:
  n_oos, viol_rate, kupiec_lr, kupiec_p.

Output
------
  reports/tables/m6_per_symbol_kupiec_4methods.csv
      Long-format: 10 symbols × 4 methods × 4 τ = 160 rows.

Run
---
  uv run python -u scripts/run_per_symbol_kupiec_all_methods.py
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

# Reuse the GARCH machinery from the Phase 7.3-extended runner. `scripts/`
# isn't a package, so import via file path (matching the precedent in
# `run_simulation_size_sweep.py`).
_GARCH_PATH = Path(__file__).resolve().parent / "run_v1b_garch_baseline.py"
_spec = importlib.util.spec_from_file_location(
    "_run_v1b_garch_baseline", _GARCH_PATH,
)
_garch = importlib.util.module_from_spec(_spec)
sys.modules["_run_v1b_garch_baseline"] = _garch
_spec.loader.exec_module(_garch)
fit_per_symbol_garch = _garch.fit_per_symbol_garch
serve_garch_bands = _garch.serve_garch_bands


def per_symbol_kupiec(
    panel: pd.DataFrame, bounds: dict[float, pd.DataFrame],
    method: str, taus: tuple[float, ...] = DEFAULT_TAUS,
) -> pd.DataFrame:
    """One row per (symbol, τ) — n_oos, viol_rate, Kupiec LR + p.

    `panel` and each `bounds[tau]` must share the same index.
    """
    rows: list[dict] = []
    for sym, idx in panel.groupby("symbol").groups.items():
        sub = panel.loc[idx]
        for tau in taus:
            band = bounds[tau].loc[sub.index]
            inside = ((sub["mon_open"] >= band["lower"]) &
                      (sub["mon_open"] <= band["upper"]))
            v = (~inside).astype(int).to_numpy()
            lr_uc, p_uc = met._lr_kupiec(v, tau)
            rows.append({
                "symbol": sym,
                "method": method,
                "tau": float(tau),
                "n_oos": int(len(sub)),
                "viol_rate": float(v.mean()),
                "kupiec_lr": float(lr_uc),
                "kupiec_p": float(p_uc),
            })
    return pd.DataFrame(rows)


def garch_per_symbol_kupiec(
    panel_full: pd.DataFrame, dist: str,
) -> pd.DataFrame:
    """Per-symbol GARCH-{dist} σ̂ → bands → Kupiec at four τ.

    `panel_full` is the full panel (train + OOS) — `fit_per_symbol_garch`
    needs the full series for the recursive σ̂ over the post-split
    weekends. The Kupiec test then restricts to OOS rows only."""
    forecasts = fit_per_symbol_garch(panel_full, dist)
    forecasts["fri_ts"] = pd.to_datetime(forecasts["fri_ts"]).dt.date
    fc_oos = (forecasts[forecasts["fri_ts"] >= SPLIT_DATE]
              .dropna(subset=["sigma_hat"])
              .reset_index(drop=True))
    bounds = serve_garch_bands(fc_oos, DEFAULT_TAUS)
    method = f"garch_{dist}"
    return per_symbol_kupiec(fc_oos, bounds, method)


def deployed_per_symbol_kupiec(
    panel_raw: pd.DataFrame, forecaster: str,
) -> pd.DataFrame:
    """Per-symbol M5 / M6 LWC σ̂ → bands → Kupiec at four τ.

    Mirrors the dispatcher recipe used by every Phase 2 / 7 runner.
    """
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
    return per_symbol_kupiec(panel_oos, bounds, forecaster)


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

    for dist in GARCH_DISTS:
        print(f"\n[GARCH-{dist}] per-symbol fit + Kupiec …", flush=True)
        frames.append(garch_per_symbol_kupiec(panel, dist))

    for fc in DEPLOYED_FORECASTERS:
        print(f"\n[{fc}] dispatcher → per-symbol Kupiec …", flush=True)
        frames.append(deployed_per_symbol_kupiec(panel, fc))

    out = pd.concat(frames, ignore_index=True)
    out_path = REPORTS / "tables" / "m6_per_symbol_kupiec_4methods.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}", flush=True)
    print(f"  rows: {len(out)}  "
          f"(expected {out['symbol'].nunique()} sym × "
          f"{out['method'].nunique()} methods × "
          f"{out['tau'].nunique()} τ = "
          f"{out['symbol'].nunique() * out['method'].nunique() * out['tau'].nunique()})",
          flush=True)

    # ---------------------------- console summary
    print("\n" + "=" * 100)
    print("PER-SYMBOL KUPIEC AT τ=0.95 — four methods")
    print("=" * 100)
    sub = out[out["tau"] == 0.95].copy()
    pivot_p = sub.pivot_table(
        index="symbol", columns="method", values="kupiec_p",
    )[list(["garch_gaussian", "garch_t", "m5", "lwc"])]
    pivot_v = sub.pivot_table(
        index="symbol", columns="method", values="viol_rate",
    )[list(["garch_gaussian", "garch_t", "m5", "lwc"])]
    print("\nKupiec p (≥ 0.05 = pass):")
    print(pivot_p.to_string(float_format=lambda x: f"{x:.3f}"))
    print("\nViolation rate (target = 0.05):")
    print(pivot_v.to_string(float_format=lambda x: f"{x:.3f}"))

    print("\nPass-counts at τ=0.95 (Kupiec p ≥ 0.05, out of 10 symbols):")
    for method in ("garch_gaussian", "garch_t", "m5", "lwc"):
        m = sub[sub["method"] == method]
        n_pass = int((m["kupiec_p"] >= 0.05).sum())
        print(f"  {method:>15s}: {n_pass}/10")


if __name__ == "__main__":
    main()
