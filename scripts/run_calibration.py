"""
Run the decade-scale calibration backtest for F0/F1/F2 weekend forecasters.

Output:
  reports/v1b_calibration.md  — summary tables + per-symbol breakdown
  reports/figures/v1b_calibration_curve.png  — calibration plot
  reports/tables/v1b_summary.csv
  reports/tables/v1b_per_symbol.csv
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import forecasters as fc
from soothsayer.backtest import metrics as met
from soothsayer.backtest import regimes as rg
from soothsayer.backtest.panel import build, PanelSpec, _universe, FUTURES, VIX
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.sources.yahoo import fetch_daily


FORECASTERS = (
    "F0_stale",
    "F1_futures_adj",
    "F1_emp",
    "F1_emp_vol",
    "F1_emp_loglog",
    "F1_emp_regime",
    "F2_har_rv",
)


def _tables_dir() -> Path:
    p = REPORTS / "tables"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _figures_dir() -> Path:
    p = REPORTS / "figures"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _run_forecasters(panel: pd.DataFrame, daily: pd.DataFrame) -> dict:
    """Returns a dict where each value is either:
      - ('gauss', DataFrame[point, sigma])       for parametric Gaussian forecasters, or
      - ('bounds', (point: Series, bounds: dict[cov, DataFrame[lower, upper]]))
    Both shapes fold through the metrics layer with the appropriate helper."""
    coverage_levels = met.COVERAGE_LEVELS
    emp_bounds = fc.empirical_quantiles_f1(panel, coverage_levels=coverage_levels, window=104)
    emp_vol_bounds = fc.empirical_quantiles_f1_vol(panel, coverage_levels=coverage_levels, window=104)

    # Baseline log-log: VIX only, for comparison
    emp_ll_bounds, ll_diag = fc.empirical_quantiles_f1_loglog(
        panel, coverage_levels=coverage_levels, window=156, vol_col="vix_fri_close"
    )
    ll_diag.to_csv(_tables_dir() / "v1b_loglog_fit.csv", index=False)

    # Regime-aware log-log: per-symbol vol_idx + earnings + long-weekend regressors
    panel_reg = panel.copy()
    panel_reg["is_long_weekend"] = (panel_reg["gap_days"] >= 4).astype(float)
    panel_reg["earnings_next_week_f"] = panel_reg["earnings_next_week"].astype(float)
    emp_regime_bounds, regime_diag = fc.empirical_quantiles_f1_loglog(
        panel_reg,
        coverage_levels=coverage_levels,
        window=156,
        vol_col="vol_idx_fri_close",
        extra_regressors=("earnings_next_week_f", "is_long_weekend"),
    )
    regime_diag.to_csv(_tables_dir() / "v1b_regime_loglog_fit.csv", index=False)

    return {
        "F0_stale": ("gauss", fc.forecast_f0(panel)),
        "F1_futures_adj": ("gauss", fc.forecast_f1(panel, window=52)),
        "F1_emp": ("bounds", (fc.point_futures_adjusted(panel), emp_bounds)),
        "F1_emp_vol": ("bounds", (fc.point_futures_adjusted(panel), emp_vol_bounds)),
        "F1_emp_loglog": ("bounds", (fc.point_futures_adjusted(panel), emp_ll_bounds)),
        "F1_emp_regime": ("bounds", (fc.point_futures_adjusted(panel), emp_regime_bounds)),
        "F2_har_rv": ("gauss", fc.forecast_f2(panel, daily)),
    }


def _summarize_one(name: str, panel: pd.DataFrame, spec) -> pd.DataFrame:
    kind, payload = spec
    if kind == "gauss":
        return met.summarize(name, panel, payload)
    elif kind == "bounds":
        point, bounds = payload
        return met.summarize_bounds(name, panel, point, bounds)
    else:
        raise ValueError(f"unknown forecaster kind: {kind}")


def _overall_summary(panel: pd.DataFrame, forecasts: dict) -> pd.DataFrame:
    rows = [_summarize_one(name, panel, spec) for name, spec in forecasts.items()]
    return pd.concat(rows, ignore_index=True)


def _slice_forecast(spec, idx) -> tuple:
    kind, payload = spec
    if kind == "gauss":
        return (kind, payload.loc[idx])
    elif kind == "bounds":
        point, bounds = payload
        return (kind, (point.loc[idx], {c: b.loc[idx] for c, b in bounds.items()}))
    raise ValueError(kind)


def _per_symbol_summary(panel: pd.DataFrame, forecasts: dict) -> pd.DataFrame:
    rows = []
    for sym, idx in panel.groupby("symbol").groups.items():
        pm = panel.loc[idx]
        for name, spec in forecasts.items():
            sliced = _slice_forecast(spec, idx)
            row = _summarize_one(name, pm, sliced).iloc[0].to_dict()
            row["symbol"] = sym
            rows.append(row)
    df = pd.DataFrame(rows)
    cols = ["symbol", "forecaster", "n"] + [c for c in df.columns if c not in {"symbol", "forecaster", "n"}]
    return df[cols]


def _per_regime_summary(panel: pd.DataFrame, forecasts: dict, regime_col: str) -> pd.DataFrame:
    rows = []
    for regime, idx in panel.groupby(regime_col).groups.items():
        pm = panel.loc[idx]
        for name, spec in forecasts.items():
            sliced = _slice_forecast(spec, idx)
            row = _summarize_one(name, pm, sliced).iloc[0].to_dict()
            row[regime_col] = regime
            rows.append(row)
    df = pd.DataFrame(rows)
    cols = [regime_col, "forecaster", "n"] + [
        c for c in df.columns if c not in {regime_col, "forecaster", "n"}
    ]
    return df[cols]


def _plot_calibration(panel: pd.DataFrame, forecasts: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect")
    for name, spec in forecasts.items():
        kind, payload = spec
        if kind == "gauss":
            curve = met.calibration_curve(panel, payload)
        else:
            point, bounds = payload
            curve = met.calibration_curve_from_bounds(panel, bounds)
        ax.plot(curve["claimed"], curve["realized"], marker="o", label=name, linewidth=1.2, markersize=3)
    ax.set_xlabel("Claimed coverage")
    ax.set_ylabel("Realized coverage")
    ax.set_title(f"Calibration curve — {len(panel)} weekends across {panel.symbol.nunique()} tickers")
    ax.legend()
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _write_report(
    overall: pd.DataFrame,
    per_symbol: pd.DataFrame,
    per_regime_pub: pd.DataFrame,
    per_realized: pd.DataFrame,
    panel: pd.DataFrame,
    figure_path: Path,
    product_diag: dict | None = None,
) -> Path:
    lines = [
        "# V1b — Decade-scale calibration backtest",
        "",
        f"- Panel: {len(panel):,} weekend observations across {panel.symbol.nunique()} tickers",
        f"- Window: {panel.fri_ts.min()} to {panel.fri_ts.max()}",
        f"- Publish time: Friday 16:00 ET (US equity close)",
        f"- Target: Monday 09:30 ET open (from yfinance daily 'Open')",
        "",
        "## Overall summary (pooled across tickers)",
        "",
        overall.to_markdown(index=False, floatfmt=".3f"),
        "",
        "### Interpretation rubric",
        "",
        "- `cov95_realized` close to 0.95 → calibrated",
        "- `cov95_sharp_bps` is the mean 95% half-width in bps of Friday close. Lower = sharper.",
        "- `mae_bps` is point-estimate error. `F0 > F1` means futures-adjustment pays.",
        "",
        f"![Calibration curve]({figure_path.relative_to(REPORTS).as_posix()})",
        "",
        "## Per-symbol 95% coverage and sharpness",
        "",
    ]
    pivot_cov = per_symbol.pivot(index="symbol", columns="forecaster", values="cov95_realized")
    pivot_sharp = per_symbol.pivot(index="symbol", columns="forecaster", values="cov95_sharp_bps")
    pivot_mae = per_symbol.pivot(index="symbol", columns="forecaster", values="mae_bps")
    lines.append("### 95% coverage")
    lines.append(pivot_cov.to_markdown(floatfmt=".3f"))
    lines.append("")
    lines.append("### 95% half-width (bps)")
    lines.append(pivot_sharp.to_markdown(floatfmt=".1f"))
    lines.append("")
    lines.append("### MAE (bps)")
    lines.append(pivot_mae.to_markdown(floatfmt=".1f"))
    lines.append("")
    lines.append("## Pre-publish regimes (actionable — these are states the publisher can know at Friday 16:00)")
    lines.append("")
    lines.append(per_regime_pub.to_markdown(index=False, floatfmt=".3f"))
    lines.append("")
    lines.append("## Realized-move tertiles (post-hoc diagnostic — how does each forecaster hold up when Mon move is big?)")
    lines.append("")
    lines.append(per_realized.to_markdown(index=False, floatfmt=".3f"))
    lines.append("")

    if product_diag is not None:
        lines.append("## Conditional coverage — Kupiec + Christoffersen (F1_emp_regime)")
        lines.append("")
        lines.append(
            "Unconditional coverage (Kupiec POF) tests whether realized violation rate "
            "matches expected. Independence (Christoffersen) tests whether violations "
            "cluster — an institutional-grade disclosure. Conditional coverage (CC) "
            "combines both; `p_cc >= 0.05` means the forecaster is not rejected. "
            "Tests run per symbol's time series to respect weekend ordering; pooled "
            "p-values apply χ²(1 + n_symbols) under H0."
        )
        lines.append("")
        lines.append("### Pooled across symbols")
        lines.append("")
        cc_pooled = product_diag.get("cc_pooled")
        if cc_pooled is not None and not cc_pooled.empty:
            lines.append(cc_pooled.to_markdown(index=False, floatfmt=".3f"))
        lines.append("")
        lines.append("### By pre-publish regime")
        lines.append("")
        cc_by_regime = product_diag.get("cc_by_regime")
        if cc_by_regime is not None and not cc_by_regime.empty:
            lines.append(cc_by_regime.to_markdown(index=False, floatfmt=".3f"))
        lines.append("")

        rel_path = product_diag.get("reliability_path")
        if rel_path is not None:
            lines.append("## Reliability diagram (the artifact no oracle provider has published)")
            lines.append("")
            lines.append(
                "Claimed coverage (x-axis) vs realized coverage (y-axis). "
                "Diagonal = perfect calibration. Dots are coloured by pre-publish regime. "
                "Empty black circles are pooled. This is the ECMWF reliability-diagram format, "
                "which maps 1:1 onto the calibration artifacts an institutional model-validation "
                "function (SR 11-7 / 26-02) is required to produce."
            )
            lines.append("")
            lines.append(f"![Reliability diagram]({Path(rel_path).relative_to(REPORTS).as_posix()})")
            lines.append("")

    report_path = REPORTS / "v1b_calibration.md"
    report_path.write_text("\n".join(lines))
    return report_path


def _plot_reliability_diagram(
    panel: pd.DataFrame,
    fine_bounds: dict[float, pd.DataFrame],
    path: Path,
) -> None:
    """Reliability diagram in the ECMWF tradition: claimed coverage (x-axis) vs
    realized coverage (y-axis), with the perfect-calibration diagonal marked and
    dots stratified by pre-publish regime. One plot — the figure that no oracle
    provider has ever published and that maps 1:1 onto an institutional model-
    validation artifact (SR 11-7 style)."""
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect calibration", linewidth=1.0)
    ax.axhspan(0.93, 0.97, xmin=(0.95 - 0.0) / 1.0, xmax=(0.95 - 0.0) / 1.0, alpha=0)  # placeholder
    # 95% target band shading
    ax.axvline(0.95, color="grey", alpha=0.15, linewidth=8)

    regime_styles = {
        "normal": {"color": "#2ca02c", "marker": "o", "label": "normal"},
        "long_weekend": {"color": "#1f77b4", "marker": "s", "label": "long_weekend"},
        "high_vol": {"color": "#d62728", "marker": "^", "label": "high_vol"},
    }
    pooled_rows = []
    for cov, band in sorted(fine_bounds.items()):
        mask = panel["mon_open"].notna() & band["lower"].notna() & band["upper"].notna()
        p = panel.loc[mask]
        b = band.loc[mask]
        inside = (p["mon_open"] >= b["lower"]) & (p["mon_open"] <= b["upper"])
        pooled_rows.append({"claimed": cov, "realized": float(inside.mean()), "n": int(len(p))})
        for regime, style in regime_styles.items():
            r_mask = p["regime_pub"] == regime
            if r_mask.sum() < 20:
                continue
            r_inside = inside.loc[r_mask]
            ax.scatter(cov, r_inside.mean(), **{k: v for k, v in style.items() if k != "label"},
                       s=45, alpha=0.75, edgecolors="white", linewidth=0.5)

    # Pooled dots as empty circles (on top)
    for row in pooled_rows:
        ax.scatter(row["claimed"], row["realized"], facecolors="none", edgecolors="black",
                   s=110, linewidth=1.5)

    # Regime legend entries (dummy scatter)
    for regime, style in regime_styles.items():
        ax.scatter([], [], color=style["color"], marker=style["marker"],
                   s=55, label=style["label"])
    ax.scatter([], [], facecolors="none", edgecolors="black", s=110, linewidth=1.5, label="pooled")

    ax.set_xlabel("Claimed coverage")
    ax.set_ylabel("Realized coverage")
    ax.set_title(
        f"Reliability diagram — F1_emp_regime\n"
        f"{len(panel):,} weekends, {panel['symbol'].nunique()} tickers, {panel['fri_ts'].min()} to {panel['fri_ts'].max()}"
    )
    ax.set_xlim(0.45, 1.02)
    ax.set_ylim(0.20, 1.02)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right", frameon=True)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _build_product_artifacts(panel: pd.DataFrame) -> dict:
    """Run the regime-aware forecaster at a fine claimed-coverage grid and
    persist the bounds table + calibration surface + conditional-coverage tests
    + reliability diagram. These are the artifacts the Oracle API consumes at
    runtime and the pitch deck cites as evidence.

    Returns a dict of key diagnostics suitable for inclusion in the written
    report."""
    panel_reg = panel.copy()
    panel_reg["is_long_weekend"] = (panel_reg["gap_days"] >= 4).astype(float)
    panel_reg["earnings_next_week_f"] = panel_reg["earnings_next_week"].astype(float)

    fine_grid = cal.DEFAULT_CLAIMED_GRID
    print(f"Computing bounds at fine grid: {fine_grid}")
    fine_bounds, _ = fc.empirical_quantiles_f1_loglog(
        panel_reg,
        coverage_levels=fine_grid,
        window=156,
        vol_col="vol_idx_fri_close",
        extra_regressors=("earnings_next_week_f", "is_long_weekend"),
    )

    # F1_emp_regime bounds (our primary forecaster — tightest on normal/long_weekend)
    bounds_regime = cal.build_bounds_table(panel, fine_bounds, forecaster="F1_emp_regime")

    # F0_stale bounds at the same fine grid (Gaussian, cheap to compute). The
    # hybrid product uses F0 in high_vol regime because F1 stretches to cover
    # there and F0's already-wide Gaussian band is more efficient at matched
    # realized coverage per v1b evidence (normal 27% tighter / long 43% tighter
    # for F1, but high_vol ~10% tighter for F0).
    f0_forecast = fc.forecast_f0(panel)
    f0_fine_bounds = fc.gaussian_bounds(f0_forecast, coverage_levels=fine_grid)
    bounds_f0 = cal.build_bounds_table(panel, f0_fine_bounds, forecaster="F0_stale")

    bounds_table = pd.concat([bounds_regime, bounds_f0], ignore_index=True)
    bounds_table.attrs.clear()
    surface = cal.compute_calibration_surface(bounds_table)
    surface_pooled = cal.pooled_surface(bounds_table)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    bounds_path = DATA_PROCESSED / "v1b_bounds.parquet"
    bounds_table.to_parquet(bounds_path)
    surface.to_csv(_tables_dir() / "v1b_calibration_surface.csv", index=False)
    surface_pooled.to_csv(_tables_dir() / "v1b_calibration_surface_pooled.csv", index=False)

    # Persist the regime-tagged panel too — LiveOracle reloads this rather than
    # rebuilding from scratch on each serve.
    panel_path = DATA_PROCESSED / "v1b_panel.parquet"
    panel_out = panel_reg.copy()
    panel_out.attrs.clear()
    panel_out.to_parquet(panel_path)
    print(f"Panel: {len(panel_out):,} rows → {panel_path}")

    # Conditional-coverage tests (Kupiec unconditional + Christoffersen independence)
    # Reported at a pitch-relevant subset of the grid: 0.68, 0.95, 0.99.
    pitch_grid = {q: fine_bounds[q] for q in (0.68, 0.95, 0.99) if q in fine_bounds}
    cc_pooled = met.conditional_coverage_from_bounds(panel, pitch_grid, group_by="symbol")
    cc_pooled.to_csv(_tables_dir() / "v1b_conditional_coverage_pooled.csv", index=False)

    cc_by_regime_rows = []
    for regime, grp in panel.groupby("regime_pub"):
        if len(grp) < 30:
            continue
        regime_bounds = {q: fine_bounds[q].loc[grp.index] for q in pitch_grid}
        cc = met.conditional_coverage_from_bounds(grp, regime_bounds, group_by="symbol")
        cc["regime_pub"] = regime
        cc_by_regime_rows.append(cc)
    cc_by_regime = pd.concat(cc_by_regime_rows, ignore_index=True) if cc_by_regime_rows else pd.DataFrame()
    cc_by_regime.to_csv(_tables_dir() / "v1b_conditional_coverage_by_regime.csv", index=False)

    # Reliability diagram
    rel_path = _figures_dir() / "v1b_reliability_diagram.png"
    _plot_reliability_diagram(panel, fine_bounds, rel_path)

    print(f"Bounds table: {len(bounds_table):,} rows → {bounds_path}")
    print(f"Calibration surface: {len(surface):,} (symbol, regime, claimed) rows")
    print(f"  pooled rows: {len(surface_pooled):,}")
    print(f"Reliability diagram: {rel_path}")
    print("Conditional coverage (pooled):")
    print(cc_pooled.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    if not cc_by_regime.empty:
        print("Conditional coverage (by regime):")
        print(cc_by_regime.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    return {
        "cc_pooled": cc_pooled,
        "cc_by_regime": cc_by_regime,
        "reliability_path": rel_path,
    }


def main() -> None:
    spec = PanelSpec(start=date(2014, 1, 1), end=date(2026, 4, 30))
    panel = build(spec)
    panel = rg.tag(panel)

    # Daily bars are needed again for HAR-RV (F2). They're cached from panel.build().
    equities = _universe()
    daily = fetch_daily(equities + list(FUTURES) + [VIX], spec.start, spec.end)

    forecasts = _run_forecasters(panel, daily)

    overall = _overall_summary(panel, forecasts)
    per_symbol = _per_symbol_summary(panel, forecasts)
    per_regime_pub = _per_regime_summary(panel, forecasts, "regime_pub")
    per_realized = _per_regime_summary(panel, forecasts, "realized_bucket")

    overall.to_csv(_tables_dir() / "v1b_summary.csv", index=False)
    per_symbol.to_csv(_tables_dir() / "v1b_per_symbol.csv", index=False)
    per_regime_pub.to_csv(_tables_dir() / "v1b_per_regime_pub.csv", index=False)
    per_realized.to_csv(_tables_dir() / "v1b_per_realized.csv", index=False)

    fig_path = _figures_dir() / "v1b_calibration_curve.png"
    _plot_calibration(panel, forecasts, fig_path)

    # Build product artifacts first so their diagnostics can land in the report.
    print()
    print("=" * 80)
    print("PRODUCT ARTIFACTS")
    print("=" * 80)
    product_diag = _build_product_artifacts(panel)

    report_path = _write_report(
        overall, per_symbol, per_regime_pub, per_realized, panel, fig_path,
        product_diag=product_diag,
    )

    print("=" * 80)
    print("V1b CALIBRATION BACKTEST — SUMMARY")
    print("=" * 80)
    print(overall.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print("--- Pre-publish regimes (actionable for the product) ---")
    print(per_regime_pub.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print("--- Realized-move tertiles (post-hoc diagnostic) ---")
    print(per_realized.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print(f"Report:  {report_path}")
    print(f"Figure:  {fig_path}")


if __name__ == "__main__":
    main()
