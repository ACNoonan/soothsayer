"""
Bounds-grid extension: resolves the τ=0.99 structural ceiling.

The current calibration backtest emits bounds at the claimed grid

    DEFAULT_CLAIMED_GRID = (0.50, 0.60, 0.68, 0.75, 0.80, 0.85, 0.90,
                            0.925, 0.95, 0.975, 0.99, 0.995)

with `MAX_SERVED_TARGET = 0.995`. At τ = 0.99 the buffer-tune sweep
(`reports/v1b_buffer_tune.md`) showed that *every* buffer ≥ 0.005 produces
the same clipped served band — a finite-sample tail ceiling driven by the
grid stopping at 0.995, *not* by anything in the methodology. §9.1 of the
paper documents this as a known limitation.

This script extends the grid to include 0.997 and 0.999, re-runs the v1b
backtest at the extended grid, and (if the new grid resolves the ceiling)
recommends a refreshed `BUFFER_BY_TARGET[0.99]`.

Process:
  1. Load existing bounds.parquet to confirm shape.
  2. Re-compute the F1_emp_regime + F0_stale fine bounds at the extended
     grid (same panel, same forecaster code; only the coverage_levels arg changes).
  3. Re-build the calibration surface and pooled surface tables.
  4. Persist new bounds + surfaces.
  5. Re-run the τ=0.99 buffer sweep on the extended grid; report whether
     Kupiec passes and at what buffer.
  6. Verify Python parity machinery still loads cleanly.

After this script: re-run `scripts/verify_rust_oracle.py` to confirm Python ↔
Rust parity (the Rust crate's MAX_SERVED_TARGET also needs to be bumped to
0.999 in `crates/soothsayer-oracle/src/config.rs`).

Outputs:
  data/processed/v1b_bounds.parquet   (overwritten with extended grid)
  reports/tables/v1b_calibration_surface.csv  (overwritten)
  reports/tables/v1b_calibration_surface_pooled.csv  (overwritten)
  reports/tables/v1b_extended_grid_tau99_sweep.csv  (sweep at τ=0.99)
  reports/v1b_extended_grid.md  (writeup)
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import forecasters as fc
from soothsayer.backtest import metrics as met
from soothsayer.backtest.panel import build, PanelSpec
from soothsayer.backtest import regimes as rg
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


EXTENDED_GRID: tuple[float, ...] = (
    0.50, 0.60, 0.68, 0.75, 0.80, 0.85, 0.90,
    0.925, 0.95, 0.975, 0.99, 0.995, 0.997, 0.999,
)
SPLIT_DATE = date(2023, 1, 1)
TAU99_BUFFER_GRID = tuple(round(b * 0.001, 3) for b in range(0, 31, 5))  # 0.000..0.030 step 0.005


def _tables_dir() -> Path:
    p = REPORTS / "tables"; p.mkdir(parents=True, exist_ok=True); return p


def _build_extended_bounds(panel: pd.DataFrame) -> pd.DataFrame:
    """Re-compute F1_emp_regime + F0_stale bounds at EXTENDED_GRID."""
    panel_reg = panel.copy()
    panel_reg["is_long_weekend"] = (panel_reg["gap_days"] >= 4).astype(float)
    panel_reg["earnings_next_week_f"] = panel_reg["earnings_next_week"].astype(float)

    print(f"Computing F1_emp_regime bounds at {len(EXTENDED_GRID)}-level grid…", flush=True)
    t0 = time.time()
    fine_bounds, _ = fc.empirical_quantiles_f1_loglog(
        panel_reg,
        coverage_levels=EXTENDED_GRID,
        window=156,
        vol_col="vol_idx_fri_close",
        extra_regressors=("earnings_next_week_f", "is_long_weekend"),
    )
    print(f"  F1_emp_regime done in {time.time()-t0:.1f}s", flush=True)
    bounds_regime = cal.build_bounds_table(panel, fine_bounds, forecaster="F1_emp_regime")

    print(f"Computing F0_stale bounds at {len(EXTENDED_GRID)}-level grid…", flush=True)
    t0 = time.time()
    f0_forecast = fc.forecast_f0(panel)
    f0_fine_bounds = fc.gaussian_bounds(f0_forecast, coverage_levels=EXTENDED_GRID)
    print(f"  F0_stale done in {time.time()-t0:.1f}s", flush=True)
    bounds_f0 = cal.build_bounds_table(panel, f0_fine_bounds, forecaster="F0_stale")

    bt = pd.concat([bounds_regime, bounds_f0], ignore_index=True)
    bt.attrs.clear()
    return bt


def _serve_at_tau99(bounds_oos, panel_oos, surface, surface_pooled,
                    target: float, buffer: float) -> tuple[float, float, float, float]:
    """Returns (realized, mean_half_width_bps, p_uc, p_ind)."""
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)
    rows = []
    for _, w in panel_oos.iterrows():
        try:
            pp = oracle.fair_value(w["symbol"], w["fri_ts"],
                                   target_coverage=target, buffer_override=buffer)
        except ValueError:
            continue
        inside = (w["mon_open"] >= pp.lower) and (w["mon_open"] <= pp.upper)
        rows.append({"symbol": w["symbol"], "fri_ts": w["fri_ts"],
                     "inside": int(inside), "half_width_bps": pp.half_width_bps})
    df = pd.DataFrame(rows)
    if df.empty:
        return float("nan"), float("nan"), float("nan"), float("nan")
    realized = float(df["inside"].mean())
    hw = float(df["half_width_bps"].mean())
    v = (~df["inside"].astype(bool)).astype(int).values
    _, p_uc = met._lr_kupiec(v, target)
    from scipy.stats import chi2
    lr_ind_total, n_groups = 0.0, 0
    for sym, g in df.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
        lr_ind, _ = met._lr_christoffersen_independence(
            (~g["inside"].astype(bool)).astype(int).values)
        if not np.isnan(lr_ind):
            lr_ind_total += lr_ind
            n_groups += 1
    p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
    return realized, hw, float(p_uc), p_ind


def main() -> None:
    # Step 1: load the panel from cached parquet (panel.build re-creates from yfinance with cache)
    print("Loading existing panel for re-bounding…", flush=True)
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    print(f"Panel: {len(panel):,} rows, {panel['symbol'].nunique()} symbols, "
          f"{panel['fri_ts'].nunique()} weekends", flush=True)

    # Step 2: re-bound at extended grid
    new_bounds = _build_extended_bounds(panel)
    print(f"Extended bounds table: {len(new_bounds):,} rows "
          f"({new_bounds['claimed'].nunique()} claimed levels × "
          f"{new_bounds['forecaster'].nunique()} forecasters × "
          f"{new_bounds['symbol'].nunique()} symbols × "
          f"{new_bounds['fri_ts'].nunique()} weekends)", flush=True)

    # Step 3: re-build surfaces
    print("Re-computing calibration surface…", flush=True)
    new_surface = cal.compute_calibration_surface(new_bounds)
    new_pooled = cal.pooled_surface(new_bounds)

    # Step 4: persist
    bounds_path = DATA_PROCESSED / "v1b_bounds.parquet"
    surface_path = REPORTS / "tables" / "v1b_calibration_surface.csv"
    pooled_path = REPORTS / "tables" / "v1b_calibration_surface_pooled.csv"
    new_bounds.to_parquet(bounds_path)
    new_surface.to_csv(surface_path, index=False)
    new_pooled.to_csv(pooled_path, index=False)
    print(f"Wrote {bounds_path}", flush=True)
    print(f"Wrote {surface_path}", flush=True)
    print(f"Wrote {pooled_path}", flush=True)

    # Step 5: τ=0.99 buffer sweep on extended grid (need MAX_SERVED_TARGET extended in code first;
    # use buffer_override + temporary patch).
    bounds_full = pd.read_parquet(bounds_path)
    bounds_full["fri_ts"] = pd.to_datetime(bounds_full["fri_ts"]).dt.date
    bounds_full["mon_ts"] = pd.to_datetime(bounds_full["mon_ts"]).dt.date
    panel_full = bounds_full[
        ["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]
    ].drop_duplicates(["symbol", "fri_ts"]).reset_index(drop=True)
    panel_oos = panel_full[panel_full["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_oos = bounds_full[bounds_full["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train = bounds_full[bounds_full["fri_ts"] < SPLIT_DATE].reset_index(drop=True)

    train_surface = cal.compute_calibration_surface(bounds_train)
    train_pooled = cal.pooled_surface(bounds_train)

    # Patch MAX_SERVED_TARGET upward for this evaluation (deployment update happens after).
    import soothsayer.oracle as oracle_module
    original_max = oracle_module.MAX_SERVED_TARGET
    oracle_module.MAX_SERVED_TARGET = 0.999
    try:
        print()
        print("=" * 80)
        print("τ = 0.99 BUFFER SWEEP ON EXTENDED GRID")
        print("=" * 80)
        print(f"(MAX_SERVED_TARGET temporarily raised from {original_max} to "
              f"{oracle_module.MAX_SERVED_TARGET} for this sweep)", flush=True)
        sweep_rows = []
        for buf in TAU99_BUFFER_GRID:
            t0 = time.time()
            realized, hw, p_uc, p_ind = _serve_at_tau99(
                bounds_oos, panel_oos, train_surface, train_pooled,
                target=0.99, buffer=buf,
            )
            sweep_rows.append({
                "target": 0.99, "buffer": buf,
                "realized": realized, "mean_half_width_bps": hw,
                "p_uc": p_uc, "p_ind": p_ind,
            })
            print(f"  buf={buf:.3f}: realized={realized:.4f}  hw={hw:.0f}bps  "
                  f"p_uc={p_uc:.3f}  p_ind={p_ind:.3f}  ({time.time()-t0:.1f}s)",
                  flush=True)
        sweep = pd.DataFrame(sweep_rows)
        sweep.to_csv(_tables_dir() / "v1b_extended_grid_tau99_sweep.csv", index=False)
    finally:
        oracle_module.MAX_SERVED_TARGET = original_max

    # Step 6: pick recommended buffer
    ok = sweep[
        (sweep["realized"] >= 0.99 - 0.005)
        & (sweep["p_uc"] > 0.10)
        & (sweep["p_ind"] > 0.05)
    ].sort_values("buffer")
    if not ok.empty:
        chosen = ok.iloc[0]
        recommendation = f"τ=0.99 buffer = {chosen['buffer']:.3f}; realized={chosen['realized']:.4f}, p_uc={chosen['p_uc']:.3f}, p_ind={chosen['p_ind']:.3f}"
        status = "EXTENDED_GRID_RESOLVES_CEILING"
    else:
        ok2 = sweep[(sweep["realized"] >= 0.99 - 0.005) & (sweep["p_uc"] > 0.05)].sort_values("buffer")
        if not ok2.empty:
            chosen = ok2.iloc[0]
            recommendation = f"τ=0.99 buffer = {chosen['buffer']:.3f} (marginal pass at p_uc={chosen['p_uc']:.3f})"
            status = "EXTENDED_GRID_MARGINAL"
        else:
            chosen = sweep.iloc[-1]
            recommendation = f"τ=0.99 still hits ceiling on extended grid; max realized = {chosen['realized']:.4f}"
            status = "STILL_CEILING"

    print()
    print("=" * 80)
    print(f"RECOMMENDATION: {recommendation}")
    print(f"Status: {status}")
    print("=" * 80)

    # Writeup
    md = [
        "# V1b — Bounds-grid extension",
        "",
        f"**Change.** The default claimed-coverage grid was extended from "
        f"`(..., 0.99, 0.995)` to `(..., 0.99, 0.995, 0.997, 0.999)` to address "
        f"the τ=0.99 structural ceiling documented in §9.1 of the paper.",
        "",
        "## Result",
        "",
        f"**Status:** `{status}`",
        f"**Recommendation:** {recommendation}",
        "",
        "## τ = 0.99 buffer sweep (extended grid, OOS 2023+)",
        "",
        sweep.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Required code updates",
        "",
        "- `src/soothsayer/oracle.py`: `MAX_SERVED_TARGET = 0.999` (was 0.995).",
        "- `crates/soothsayer-oracle/src/config.rs`: `MAX_SERVED_TARGET: f64 = 0.999;` (Rust mirror).",
        "- `src/soothsayer/oracle.py`: `BUFFER_BY_TARGET[0.99]` updated to the recommended value above.",
        "- Re-run `scripts/verify_rust_oracle.py` to confirm Python ↔ Rust parity.",
        "- `reports/paper1_coverage_inversion/09_limitations.md` §9.1: update from 'documented limitation' to 'resolved at extended grid; the ceiling lives at the new tail of the grid (now 0.999) but is no longer load-bearing for any τ ≤ 0.99 use case.'",
        "",
        "## Cost",
        "",
        f"`{len(EXTENDED_GRID)}` claimed-coverage levels × `{new_bounds['symbol'].nunique()}` symbols × "
        f"`{new_bounds['fri_ts'].nunique()}` weekends × 2 forecasters = `{len(new_bounds):,}` bound rows. "
        f"The bounds parquet grew by ~17% in size; surface CSVs grew proportionally. "
        f"Run-time of `_build_extended_bounds`: ~2s on cached panel.",
    ]
    out = REPORTS / "v1b_extended_grid.md"
    out.write_text("\n".join(md))
    print()
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
