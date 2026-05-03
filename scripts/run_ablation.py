"""
Stage-1 ablation runs for the arXiv paper.

Measures the incremental contribution of each knob in the F1_emp_regime
forecaster by evaluating a ladder of variants that differ by one knob at a time:

  A0     F0_stale         Gaussian baseline (no factor adj, no empirical quantile)
  A0_VIX F0_VIX           Friday-close + VIX-implied Gaussian (σ from forward curve, not 20d realised)
  A1     F1_emp           + factor-adjusted point + empirical residual quantile
  A2  F1_emp_vol          + residual standardisation by VIX
  A3  F1_emp_ll_vix       + log-log VIX regression on |residual|
  A4  F1_emp_ll_volidx    + per-symbol vol index (VIX eq / GVZ gold / MOVE rates)
  A5  F1_emp_ll_vi_earn   + earnings-next-week regressor (only)
  A6  F1_emp_ll_vi_lw     + is_long_weekend regressor (only)
  A7  F1_emp_regime       full model (vol_idx + earnings + long_weekend)

Also:
  B0  F1_emp_regime_stale_pt  regime CI widths with stale point (isolates the
                              factor-switchboard point's contribution)

Outputs:
  reports/tables/v1b_ablation.csv            per-variant pooled metrics (95% level)
  reports/tables/v1b_ablation_all_levels.csv per-variant at 68/95/99
  reports/tables/v1b_ablation_by_regime.csv  per-variant per-regime metrics (95% level)

Uses the persisted v1b_panel.parquet so we don't re-pull yfinance data.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.backtest import forecasters as fc
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS


COVERAGE_LEVELS = (0.68, 0.95, 0.99)


def _tables_dir() -> Path:
    p = REPORTS / "tables"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _pooled_row(name: str, panel: pd.DataFrame, point: pd.Series,
                bounds: dict[float, pd.DataFrame]) -> dict:
    cov = met.coverage_and_sharpness_from_bounds(panel, point, bounds)
    m = panel["mon_open"].notna() & point.notna()
    err_bps = ((point.loc[m] - panel.loc[m, "mon_open"]) / panel.loc[m, "fri_close"] * 1e4)
    row = {"variant": name, "n": int(m.sum())}
    for _, r in cov.iterrows():
        pct = int(round(r["claimed"] * 100))
        row[f"cov{pct}_realized"] = float(r["realized"])
        row[f"cov{pct}_sharp_bps"] = float(r["sharpness_bps"])
    row["mae_bps"] = float(err_bps.abs().mean())
    # Kupiec + Christoffersen on the 95% level (the pitch level)
    cc = met.conditional_coverage_from_bounds(panel, {0.95: bounds[0.95]}, group_by="symbol")
    if not cc.empty:
        r0 = cc.iloc[0]
        row["kupiec_lr"] = float(r0["lr_uc"])
        row["kupiec_p"] = float(r0["p_uc"])
        row["christ_lr"] = float(r0["lr_ind"])
        row["christ_p"] = float(r0["p_ind"])
    return row


def _by_regime_rows(name: str, panel: pd.DataFrame, point: pd.Series,
                    bounds: dict[float, pd.DataFrame]) -> list[dict]:
    rows = []
    for regime, idx in panel.groupby("regime_pub").groups.items():
        pm = panel.loc[idx]
        pp = point.loc[idx]
        bb = {c: b.loc[idx] for c, b in bounds.items()}
        cov = met.coverage_and_sharpness_from_bounds(pm, pp, bb)
        for _, r in cov.iterrows():
            rows.append({
                "variant": name,
                "regime_pub": regime,
                "claimed": float(r["claimed"]),
                "realized": float(r["realized"]),
                "sharpness_bps": float(r["sharpness_bps"]),
                "n": int(r["n"]),
            })
    return rows


def _run_variant(name: str, panel: pd.DataFrame, compute_fn) -> tuple[pd.Series, dict[float, pd.DataFrame]]:
    t0 = time.time()
    print(f"[{name}] computing…", flush=True)
    point, bounds = compute_fn(panel)
    print(f"[{name}] done in {time.time() - t0:.1f}s", flush=True)
    return point, bounds


def _variant_f0(panel: pd.DataFrame):
    """A0: stale-hold + Gaussian CI from realised 20-day vol."""
    forecast = fc.forecast_f0(panel)
    bounds = fc.gaussian_bounds(forecast, COVERAGE_LEVELS)
    return forecast["point"], bounds


def _variant_f0_vix(panel: pd.DataFrame):
    """A0_VIX: stale-hold + Gaussian CI from VIX-implied vol (equity-only)."""
    forecast = fc.forecast_f0_vix(panel)
    bounds = fc.gaussian_bounds(forecast, COVERAGE_LEVELS)
    return forecast["point"], bounds


def _variant_f1_emp(panel: pd.DataFrame):
    """A1: factor-adjusted point + empirical residual quantile."""
    point = fc.point_futures_adjusted(panel)
    bounds = fc.empirical_quantiles_f1(panel, coverage_levels=COVERAGE_LEVELS, window=104)
    return point, bounds


def _variant_f1_emp_vol(panel: pd.DataFrame):
    """A2: + VIX-scaled residuals."""
    point = fc.point_futures_adjusted(panel)
    bounds = fc.empirical_quantiles_f1_vol(panel, coverage_levels=COVERAGE_LEVELS, window=104)
    return point, bounds


def _variant_loglog(panel: pd.DataFrame, vol_col: str, extras: tuple[str, ...]):
    point = fc.point_futures_adjusted(panel)
    bounds, _ = fc.empirical_quantiles_f1_loglog(
        panel,
        coverage_levels=COVERAGE_LEVELS,
        window=156,
        vol_col=vol_col,
        extra_regressors=extras,
    )
    return point, bounds


def _variant_stale_point_regime_ci(panel: pd.DataFrame, regime_bounds: dict[float, pd.DataFrame]):
    """B0: regime CI widths rebuilt around the stale-hold point (not factor-adjusted).

    We already have the full regime bounds. To 'apply' them to a stale point we
    keep the band half-width of the regime model but recentre on fri_close
    rather than the futures-adjusted point. This isolates the factor-switchboard
    point's coverage contribution from the CI-width contribution."""
    fa_point = fc.point_futures_adjusted(panel)
    stale_point = fc.point_stale(panel)
    out = {}
    for cov, band in regime_bounds.items():
        # half_width in price units is (upper - lower) / 2 — same regardless of centre
        half_width = (band["upper"] - band["lower"]) / 2.0
        out[cov] = pd.DataFrame({
            "lower": stale_point - half_width,
            "upper": stale_point + half_width,
        }, index=band.index)
    return stale_point, out


def main() -> None:
    panel_path = DATA_PROCESSED / "v1b_panel.parquet"
    panel = pd.read_parquet(panel_path)
    # Ensure derived regressors exist (panel.build may not have persisted them).
    if "is_long_weekend" not in panel.columns:
        panel["is_long_weekend"] = (panel["gap_days"] >= 4).astype(float)
    if "earnings_next_week_f" not in panel.columns:
        panel["earnings_next_week_f"] = panel["earnings_next_week"].astype(float)

    print(f"Panel: {len(panel):,} rows, {panel['symbol'].nunique()} symbols, "
          f"{panel['fri_ts'].nunique()} weekends, "
          f"{panel['fri_ts'].min()} → {panel['fri_ts'].max()}", flush=True)

    # ---- A-ladder: one knob at a time
    variants = [
        ("A0_f0_stale",       _variant_f0),
        ("A0_VIX_f0_vix",     _variant_f0_vix),
        ("A1_f1_emp",         _variant_f1_emp),
        ("A2_f1_emp_vol",     _variant_f1_emp_vol),
        ("A3_f1_ll_vix",      lambda p: _variant_loglog(p, "vix_fri_close", ())),
        ("A4_f1_ll_volidx",   lambda p: _variant_loglog(p, "vol_idx_fri_close", ())),
        ("A5_f1_ll_vi_earn",  lambda p: _variant_loglog(p, "vol_idx_fri_close", ("earnings_next_week_f",))),
        ("A6_f1_ll_vi_lw",    lambda p: _variant_loglog(p, "vol_idx_fri_close", ("is_long_weekend",))),
        ("A7_f1_emp_regime",  lambda p: _variant_loglog(p, "vol_idx_fri_close",
                                                        ("earnings_next_week_f", "is_long_weekend"))),
    ]

    results: dict[str, tuple[pd.Series, dict]] = {}
    for name, fn in variants:
        point, bounds = _run_variant(name, panel, fn)
        results[name] = (point, bounds)

    # ---- B: stale-point with regime CI widths
    regime_point, regime_bounds = results["A7_f1_emp_regime"]
    print("[B0] building stale-point + regime-CI variant…", flush=True)
    b0_point, b0_bounds = _variant_stale_point_regime_ci(panel, regime_bounds)
    results["B0_stale_pt_regime_ci"] = (b0_point, b0_bounds)

    # ---- Pooled per-variant summary
    pooled_rows = []
    by_regime_rows: list[dict] = []
    for name, (point, bounds) in results.items():
        pooled_rows.append(_pooled_row(name, panel, point, bounds))
        by_regime_rows.extend(_by_regime_rows(name, panel, point, bounds))

    pooled = pd.DataFrame(pooled_rows)
    by_regime = pd.DataFrame(by_regime_rows)

    # Keep a scannable "all levels" view and a 95-only view
    all_levels_cols = ["variant", "n",
                       "cov68_realized", "cov68_sharp_bps",
                       "cov95_realized", "cov95_sharp_bps",
                       "cov99_realized", "cov99_sharp_bps",
                       "mae_bps", "kupiec_lr", "kupiec_p", "christ_lr", "christ_p"]
    pooled_all = pooled[[c for c in all_levels_cols if c in pooled.columns]]
    pooled_95 = pooled[["variant", "n", "cov95_realized", "cov95_sharp_bps",
                        "mae_bps", "kupiec_lr", "kupiec_p", "christ_lr", "christ_p"]]

    pooled_all.to_csv(_tables_dir() / "v1b_ablation_all_levels.csv", index=False)
    pooled_95.to_csv(_tables_dir() / "v1b_ablation.csv", index=False)
    by_regime.to_csv(_tables_dir() / "v1b_ablation_by_regime.csv", index=False)

    # Persist per-row inside/half_width diagnostics for downstream bootstrap.
    # Each variant contributes n rows; we merge on (symbol, fri_ts).
    rows_bootstrap = []
    for name, (point, bounds) in results.items():
        b95 = bounds[0.95]
        m = panel["mon_open"].notna() & b95["lower"].notna() & b95["upper"].notna()
        sub = panel.loc[m, ["symbol", "fri_ts", "regime_pub", "mon_open", "fri_close"]].copy()
        sub["variant"] = name
        sub["lower"] = b95.loc[m, "lower"].values
        sub["upper"] = b95.loc[m, "upper"].values
        sub["inside"] = ((sub["mon_open"] >= sub["lower"]) & (sub["mon_open"] <= sub["upper"])).astype(int)
        sub["half_width_bps"] = (sub["upper"] - sub["lower"]) / 2.0 / sub["fri_close"] * 1e4
        rows_bootstrap.append(sub)
    per_row = pd.concat(rows_bootstrap, ignore_index=True)
    per_row.to_parquet(DATA_PROCESSED / "v1b_ablation_rows.parquet")

    print()
    print("=" * 80)
    print("POOLED ABLATION — 95% level")
    print("=" * 80)
    print(pooled_95.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print("BY REGIME at 95% level")
    print("=" * 80)
    br95 = by_regime[by_regime["claimed"] == 0.95].sort_values(["regime_pub", "variant"])
    print(br95.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print()
    print(f"Wrote:")
    print(f"  {_tables_dir() / 'v1b_ablation.csv'}")
    print(f"  {_tables_dir() / 'v1b_ablation_all_levels.csv'}")
    print(f"  {_tables_dir() / 'v1b_ablation_by_regime.csv'}")
    print(f"  {DATA_PROCESSED / 'v1b_ablation_rows.parquet'}")


if __name__ == "__main__":
    main()
