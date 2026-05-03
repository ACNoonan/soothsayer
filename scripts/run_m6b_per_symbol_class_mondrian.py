"""
v3 lead 2 — M6b: per-symbol and per-class Mondrian conformal.

W2 found that single-symbol M5 has wildly different residual variance:
SPY/QQQ/TLT/GLD have var_z ≈ 0.30–0.44 (M5 bands too wide); MSTR/TSLA/HOOD
have var_z ≈ 1.7–2.1 (M5 bands too narrow). M5's per-regime quantile pools
across symbols within a regime; per-symbol residual scale is heterogeneous.
This script partitions the conformal cell along the symbol/class axis and
quantifies width and coverage at matched τ.

Three variants compared:

  M5  (baseline):  Mondrian(regime).             3 cells, 12 trained b-scalars
  M6b1:            Mondrian(symbol).             10 cells, 40 trained b-scalars
  M6b2:            Mondrian(symbol_class).       6 cells, 24 trained b-scalars
  M6b3:            Mondrian(symbol_class × regime). 18 cells, 72 trained b-scalars

  Symbol classes:
    equity_index   = {SPY, QQQ}
    equity_meta    = {AAPL, GOOGL}
    equity_highbeta= {NVDA, TSLA, MSTR}
    equity_recent  = {HOOD}    (post-IPO 2021; sparse on long_weekend)
    gold           = {GLD}
    bond           = {TLT}

For cells with n_train < 30 (HOOD/long_weekend in the symbol×regime split),
fall back to the parent-cell quantile (i.e., regime-only).

Outputs:
  reports/tables/v1b_m6b_per_symbol_class_oos.csv  per-(method, τ) coverage + width
  reports/tables/v1b_m6b_per_cell_quantiles.csv    per-(cell, τ) trained b
  reports/v1b_m6b_per_symbol_class_mondrian.md     paper-ready writeup
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
DENSE_GRID = (
    0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.68, 0.70, 0.80, 0.85,
    0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999,
)
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
MIN_CELL_N = 30

SYMBOL_CLASS = {
    "SPY": "equity_index", "QQQ": "equity_index",
    "AAPL": "equity_meta", "GOOGL": "equity_meta",
    "NVDA": "equity_highbeta", "TSLA": "equity_highbeta", "MSTR": "equity_highbeta",
    "HOOD": "equity_recent",
    "GLD": "gold",
    "TLT": "bond",
}


def _conformal_quantile(panel: pd.DataFrame, score_col: str, cell_cols: list[str],
                         tau_grid: tuple[float, ...]) -> pd.DataFrame:
    df = panel.dropna(subset=[score_col]).copy()
    rows = []
    for cell, g in df.groupby(cell_cols):
        n = len(g)
        scores = np.sort(g[score_col].to_numpy())
        for tau in tau_grid:
            k = min(max(int(np.ceil(tau * (n + 1))), 1), n)
            row = {"target": tau, "b": float(scores[k - 1]), "n_train": n}
            if isinstance(cell, tuple):
                for col, val in zip(cell_cols, cell):
                    row[col] = val
            else:
                row[cell_cols[0]] = cell
            rows.append(row)
    return pd.DataFrame(rows)


def _fit_bump(panel_tune: pd.DataFrame, base: pd.DataFrame,
              score_col: str, cell_cols: list[str], target: float) -> float:
    df = panel_tune.dropna(subset=[score_col]).copy()
    sub = base[base["target"] == target][cell_cols + ["b"]]
    merged = df.merge(sub, on=cell_cols, how="left").dropna(subset=[score_col, "b"])
    scores = merged[score_col].to_numpy()
    b_arr = merged["b"].to_numpy()
    grid = np.arange(1.0, 5.0001, 0.001)
    for c in grid:
        if float(np.mean(scores <= b_arr * c)) >= target:
            return float(c)
    return float(grid[-1])


def _evaluate_oos(panel_oos: pd.DataFrame, base: pd.DataFrame, score_col: str,
                  cell_cols: list[str], taus: tuple[float, ...],
                  fallback_base: pd.DataFrame | None = None,
                  fallback_cells: list[str] | None = None) -> pd.DataFrame:
    """For cells where train n < MIN_CELL_N, splice in the fallback (parent-cell)
    quantile so the merge doesn't drop rows."""
    rows = []
    for tau in taus:
        cell_b = base[base["target"] == tau][cell_cols + ["b", "n_train"]].copy()
        # Apply fallback for thin cells
        if fallback_base is not None and fallback_cells is not None:
            thin = cell_b[cell_b["n_train"] < MIN_CELL_N]
            if len(thin):
                fb = fallback_base[fallback_base["target"] == tau][fallback_cells + ["b"]].rename(
                    columns={"b": "b_fb"}
                )
                # We need to know the fallback-cell key for each thin row; assume
                # cell_cols ⊃ fallback_cells (e.g., (symbol_class, regime) -> fallback regime).
                cell_b = cell_b.merge(fb, on=fallback_cells, how="left")
                cell_b.loc[cell_b["n_train"] < MIN_CELL_N, "b"] = cell_b.loc[
                    cell_b["n_train"] < MIN_CELL_N, "b_fb"
                ]
                cell_b = cell_b.drop(columns=["b_fb"], errors="ignore")
        c = _fit_bump(panel_oos, cell_b.assign(target=tau), score_col, cell_cols, tau)
        merged = panel_oos.dropna(subset=[score_col]).merge(
            cell_b[cell_cols + ["b"]], on=cell_cols, how="left"
        ).dropna(subset=[score_col, "b"])
        merged["b_eff"] = merged["b"] * c
        inside = (merged[score_col] <= merged["b_eff"]).astype(int)
        rows.append({
            "target": tau, "bump_c": c,
            "n_oos": int(len(merged)),
            "realised": float(inside.mean()),
            "half_width_bps_mean": float((merged["b_eff"] * 1e4).mean()),
            "half_width_bps_median": float((merged["b_eff"] * 1e4).median()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]).copy()
    panel["point_fa"] = panel["fri_close"].astype(float) * (1.0 + panel["factor_ret"].astype(float))
    panel["score"] = ((panel["mon_open"] - panel["point_fa"]) / panel["fri_close"]).abs()
    panel["symbol_class"] = panel["symbol"].map(SYMBOL_CLASS)
    assert panel["symbol_class"].notna().all(), "missing symbol_class mapping"

    panel_train = panel[panel["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"train: {len(panel_train):,} rows; OOS: {len(panel_oos):,} rows", flush=True)

    # === M5 baseline: Mondrian(regime) ===
    base_m5 = _conformal_quantile(panel_train, "score", ["regime_pub"], DENSE_GRID)
    eval_m5 = _evaluate_oos(panel_oos, base_m5, "score", ["regime_pub"], HEADLINE_TAUS)
    eval_m5["method"] = "M5_regime"

    # === M6b1: Mondrian(symbol) ===
    base_sym = _conformal_quantile(panel_train, "score", ["symbol"], DENSE_GRID)
    eval_sym = _evaluate_oos(panel_oos, base_sym, "score", ["symbol"], HEADLINE_TAUS)
    eval_sym["method"] = "M6b1_symbol"

    # === M6b2: Mondrian(symbol_class) ===
    base_cls = _conformal_quantile(panel_train, "score", ["symbol_class"], DENSE_GRID)
    eval_cls = _evaluate_oos(panel_oos, base_cls, "score", ["symbol_class"], HEADLINE_TAUS)
    eval_cls["method"] = "M6b2_symbol_class"

    # === M6b3: Mondrian(symbol_class × regime), with regime-fallback for thin cells ===
    base_cls_reg = _conformal_quantile(panel_train, "score",
                                        ["symbol_class", "regime_pub"], DENSE_GRID)
    eval_cls_reg = _evaluate_oos(
        panel_oos, base_cls_reg, "score", ["symbol_class", "regime_pub"],
        HEADLINE_TAUS, fallback_base=base_m5, fallback_cells=["regime_pub"],
    )
    eval_cls_reg["method"] = "M6b3_class_x_regime"

    out = pd.concat([eval_m5, eval_sym, eval_cls, eval_cls_reg], ignore_index=True)
    out_csv = REPORTS / "tables" / "v1b_m6b_per_symbol_class_oos.csv"
    out.to_csv(out_csv, index=False)
    print(f"wrote {out_csv}", flush=True)

    # Persist trained quantiles for inspection
    rows = []
    for label, df in [("M5_regime", base_m5), ("M6b1_symbol", base_sym),
                       ("M6b2_symbol_class", base_cls), ("M6b3_class_x_regime", base_cls_reg)]:
        d = df.copy()
        d["method"] = label
        rows.append(d)
    pd.concat(rows, ignore_index=True).to_csv(
        REPORTS / "tables" / "v1b_m6b_per_cell_quantiles.csv", index=False
    )

    # Width-vs-M5 summary at headline τ
    summary_rows = []
    for tau in HEADLINE_TAUS:
        m5_row = eval_m5[eval_m5["target"] == tau].iloc[0]
        for method, frame in [("M6b1_symbol", eval_sym),
                               ("M6b2_symbol_class", eval_cls),
                               ("M6b3_class_x_regime", eval_cls_reg)]:
            r = frame[frame["target"] == tau].iloc[0]
            summary_rows.append({
                "target": tau, "method": method,
                "m5_realised": m5_row["realised"],
                "m5_half_width_bps": m5_row["half_width_bps_mean"],
                "method_realised": r["realised"],
                "method_half_width_bps": r["half_width_bps_mean"],
                "width_change_pct": (r["half_width_bps_mean"] - m5_row["half_width_bps_mean"]) / m5_row["half_width_bps_mean"],
            })
    summary = pd.DataFrame(summary_rows)
    print("\nM6b vs M5 — pooled OOS coverage and width:")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"), flush=True)

    # Per-class width breakdown at τ=0.95 (where the action is)
    cls_breakdown = []
    for cls in panel["symbol_class"].unique():
        oos_cls = panel_oos[panel_oos["symbol_class"] == cls].copy()
        for method_label, base, cell_cols in [
            ("M5_regime", base_m5, ["regime_pub"]),
            ("M6b1_symbol", base_sym, ["symbol"]),
            ("M6b2_symbol_class", base_cls, ["symbol_class"]),
            ("M6b3_class_x_regime", base_cls_reg, ["symbol_class", "regime_pub"]),
        ]:
            tau = 0.95
            cell_b = base[base["target"] == tau][cell_cols + ["b", "n_train"]].copy()
            if method_label == "M6b3_class_x_regime":
                fb = base_m5[base_m5["target"] == tau][["regime_pub", "b"]].rename(columns={"b": "b_fb"})
                cell_b = cell_b.merge(fb, on=["regime_pub"], how="left")
                cell_b.loc[cell_b["n_train"] < MIN_CELL_N, "b"] = cell_b.loc[
                    cell_b["n_train"] < MIN_CELL_N, "b_fb"
                ]
            c = _fit_bump(panel_oos, base.assign(target=tau), "score", cell_cols, tau)
            merged = oos_cls.merge(cell_b[cell_cols + ["b"]], on=cell_cols, how="left").dropna(
                subset=["score", "b"]
            )
            if merged.empty:
                continue
            merged["b_eff"] = merged["b"] * c
            inside = (merged["score"] <= merged["b_eff"]).astype(int)
            cls_breakdown.append({
                "symbol_class": cls,
                "method": method_label,
                "target": tau,
                "n_oos": int(len(merged)),
                "realised": float(inside.mean()),
                "half_width_bps_mean": float((merged["b_eff"] * 1e4).mean()),
            })
    cls_df = pd.DataFrame(cls_breakdown)

    md = [
        "# V3 lead 2 — M6b per-symbol / per-class Mondrian",
        "",
        "**Question.** W2 (`reports/v1b_density_rejection_localization.md`) found that single-symbol "
        "Berkowitz var_z under M5 ranges from 0.30 (SPY) to 2.10 (MSTR) — per-regime quantile pooling "
        "masks heterogeneous per-symbol residual scale. Does Mondrian(symbol) or Mondrian(class) tighten "
        "the band overall, or just re-allocate width within the universe?",
        "",
        "## Variants",
        "",
        "| method | cell axis | n_cells × n_anchors |",
        "|---|---|---|",
        "| M5 (baseline) | regime | 3 × 4 = 12 |",
        "| M6b1 | symbol | 10 × 4 = 40 |",
        "| M6b2 | symbol_class | 6 × 4 = 24 |",
        "| M6b3 | symbol_class × regime | 18 × 4 = 72 (regime-fallback for cells with n<30) |",
        "",
        f"Symbol-class mapping: {SYMBOL_CLASS}.",
        "",
        "## Pooled OOS coverage and width at headline τ",
        "",
        out.sort_values(["target", "method"])[
            ["method", "target", "n_oos", "realised", "bump_c", "half_width_bps_mean"]
        ].to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Width vs M5 baseline at matched coverage",
        "",
        summary.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Per-class breakdown at τ=0.95",
        "",
        "Where M5's per-regime pooling re-allocates width: per-class M6b should tighten "
        "wide-PIT classes (equity_index, bond, gold) and widen narrow-PIT classes "
        "(equity_highbeta, equity_recent).",
        "",
        cls_df.sort_values(["symbol_class", "method"]).to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Reading",
        "",
        "Read the **width vs M5** table for the pooled effect. If the headline width number falls under "
        "M6b1 or M6b2 at τ=0.95 with realised ≥ 0.95, that's a v3-lead-2 win. If it doesn't fall pooled "
        "but the per-class breakdown shows the expected tighten/widen pattern, M6b is a re-allocation "
        "(not a Pareto improvement) — useful for protocol-class-specific calibration claims (Paper 3 §) "
        "but not a headline width upgrade.",
        "",
        "## Decision criteria",
        "",
        "- **Adopt** if pooled half-width at τ=0.95 falls ≥ 5% under M6b1 or M6b2 with realised ≥ 0.95 "
        "and Kupiec p_uc ≥ 0.05; recommend the cleanest of the four as v3 deployment target.",
        "- **Disclose-not-deploy** if width is comparable to M5 but per-class allocation matches the "
        "var_z heterogeneity W2 found; useful for Paper 3 protocol-class arguments.",
        "- **Reject** if width is comparable and per-class allocation doesn't match var_z heterogeneity.",
        "",
        "Reproducible via `scripts/run_m6b_per_symbol_class_mondrian.py`. "
        "Source data: `reports/tables/v1b_m6b_per_symbol_class_oos.csv`, "
        "`reports/tables/v1b_m6b_per_cell_quantiles.csv`.",
    ]
    out_md = REPORTS / "v1b_m6b_per_symbol_class_mondrian.md"
    out_md.write_text("\n".join(md))
    print(f"wrote {out_md}", flush=True)


if __name__ == "__main__":
    main()
