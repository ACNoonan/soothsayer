"""
M6c — combined v3 lead: M6a (common-mode partial-out) + M6b2 (per-class Mondrian).

The two v3 leads modify orthogonal axes of the M5 protocol:
  M6a — residualizes the score against the leave-one-out weekend mean residual
  M6b2 — changes the conformal cell from regime to symbol_class

This script stacks both: residualize first, then partition the conformal
cell by symbol_class. Tests whether the gains compose, and whether the
combined width win is more than the sum of either alone.

Compared variants:
  M5            score=|r|,        cell=regime
  M6a           score=|r-β·r̄|,  cell=regime
  M6b2          score=|r|,        cell=symbol_class
  M6c           score=|r-β·r̄|,  cell=symbol_class

Outputs:
  reports/tables/v1b_m6c_combined_oos.csv         per-(method, τ) coverage + width
  reports/v1b_m6c_combined.md                     paper-ready writeup

NOTE: M6a uses Monday-derived r̄_w^(−i), so M6c is also an upper-bound
diagnostic. Deployment requires a Friday-observable proxy for r̄_w.
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


def _evaluate(panel_oos: pd.DataFrame, base: pd.DataFrame,
              score_col: str, cell_cols: list[str],
              taus: tuple[float, ...]) -> pd.DataFrame:
    rows = []
    for tau in taus:
        c = _fit_bump(panel_oos, base, score_col, cell_cols, tau)
        cell_b = base[base["target"] == tau][cell_cols + ["b"]]
        merged = panel_oos.dropna(subset=[score_col]).merge(
            cell_b, on=cell_cols, how="left"
        ).dropna(subset=[score_col, "b"])
        merged["b_eff"] = merged["b"] * c
        inside = (merged[score_col] <= merged["b_eff"]).astype(int)
        rows.append({
            "target": tau, "bump_c": c, "n_oos": int(len(merged)),
            "realised": float(inside.mean()),
            "half_width_bps_mean": float((merged["b_eff"] * 1e4).mean()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]).copy()
    panel["point_fa"] = panel["fri_close"].astype(float) * (1.0 + panel["factor_ret"].astype(float))
    panel["r"] = (panel["mon_open"] - panel["point_fa"]) / panel["fri_close"]
    g = panel.groupby("fri_ts")["r"]
    panel["r_bar_loo"] = (g.transform("sum") - panel["r"]) / (g.transform("count") - 1).replace(0, np.nan)
    panel["symbol_class"] = panel["symbol"].map(SYMBOL_CLASS)

    panel_train = panel[panel["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"train: {len(panel_train):,}; OOS: {len(panel_oos):,}", flush=True)

    # Train β
    sub = panel_train[["r", "r_bar_loo"]].dropna()
    x = sub["r_bar_loo"].to_numpy(); y = sub["r"].to_numpy()
    beta = float((x * y).sum() / (x ** 2).sum())
    print(f"β = {beta:.4f}", flush=True)

    for df in (panel_train, panel_oos):
        df["score_m5"] = df["r"].abs()
        df["score_m6a"] = (df["r"] - beta * df["r_bar_loo"]).abs()

    variants = [
        ("M5",   "score_m5",   ["regime_pub"]),
        ("M6a",  "score_m6a",  ["regime_pub"]),
        ("M6b2", "score_m5",   ["symbol_class"]),
        ("M6c",  "score_m6a",  ["symbol_class"]),
    ]
    all_eval = []
    for label, score_col, cell_cols in variants:
        base = _conformal_quantile(panel_train, score_col, cell_cols, DENSE_GRID)
        ev = _evaluate(panel_oos, base, score_col, cell_cols, HEADLINE_TAUS)
        ev["method"] = label
        all_eval.append(ev)
    out = pd.concat(all_eval, ignore_index=True)
    out_csv = REPORTS / "tables" / "v1b_m6c_combined_oos.csv"
    out.to_csv(out_csv, index=False)
    print(f"wrote {out_csv}", flush=True)

    # Width-vs-M5 summary
    summary_rows = []
    for tau in HEADLINE_TAUS:
        m5 = out[(out["method"] == "M5") & (out["target"] == tau)].iloc[0]
        for label in ("M6a", "M6b2", "M6c"):
            r = out[(out["method"] == label) & (out["target"] == tau)].iloc[0]
            summary_rows.append({
                "target": tau, "method": label,
                "m5_half_width_bps": m5["half_width_bps_mean"],
                f"{label}_half_width_bps": r["half_width_bps_mean"],
                "realised": r["realised"],
                "width_change_pct": (r["half_width_bps_mean"] - m5["half_width_bps_mean"]) / m5["half_width_bps_mean"],
            })
    summary = pd.DataFrame(summary_rows)
    print("\nM6a / M6b2 / M6c vs M5 (pooled):")
    print(out.pivot_table(index="target", columns="method", values="half_width_bps_mean").to_string(
        float_format=lambda x: f"{x:.1f}"
    ), flush=True)

    # Stacking diagnostic: is M6c gain ≥ M6a gain + M6b2 gain?
    stack_rows = []
    for tau in HEADLINE_TAUS:
        d_m5 = out[(out["method"] == "M5") & (out["target"] == tau)]["half_width_bps_mean"].iloc[0]
        d_m6a = out[(out["method"] == "M6a") & (out["target"] == tau)]["half_width_bps_mean"].iloc[0]
        d_m6b = out[(out["method"] == "M6b2") & (out["target"] == tau)]["half_width_bps_mean"].iloc[0]
        d_m6c = out[(out["method"] == "M6c") & (out["target"] == tau)]["half_width_bps_mean"].iloc[0]
        gain_m6a = (d_m5 - d_m6a) / d_m5
        gain_m6b = (d_m5 - d_m6b) / d_m5
        gain_m6c = (d_m5 - d_m6c) / d_m5
        sum_indep = gain_m6a + gain_m6b
        stack_rows.append({
            "target": tau,
            "gain_m6a": gain_m6a, "gain_m6b2": gain_m6b, "gain_m6c": gain_m6c,
            "sum_individual": sum_indep,
            "stacking_efficiency": gain_m6c / sum_indep if sum_indep > 0 else float("nan"),
        })
    stack_df = pd.DataFrame(stack_rows)
    print("\nStacking diagnostic (gain vs M5):")
    print(stack_df.to_string(index=False, float_format=lambda x: f"{x:.3f}"), flush=True)

    md = [
        "# V3 leads — combined M6c (M6a + M6b2)",
        "",
        "**Question.** v3 lead 1 (M6a, common-mode partial-out) and v3 lead 2 (M6b2, per-class "
        "Mondrian) modify orthogonal axes of the M5 protocol. Do their width gains stack?",
        "",
        "## Variants",
        "",
        "| method | score | cell | params |",
        "|---|---|---|---|",
        "| M5   | \\|r\\|         | regime         | 12 b + 4 c (16) |",
        "| M6a  | \\|r − β·r̄\\| | regime         | 12 b + 4 c + 1 β (17) |",
        "| M6b2 | \\|r\\|         | symbol_class   | 24 b + 4 c (28) |",
        "| M6c  | \\|r − β·r̄\\| | symbol_class   | 24 b + 4 c + 1 β (29) |",
        "",
        f"Train β = {beta:.3f} (R² ≈ 0.28; see `v1b_m6a_common_mode_fit.csv`).",
        "",
        "## Pooled OOS half-width (bps) by method × τ",
        "",
        out.pivot_table(index="target", columns="method", values="half_width_bps_mean").to_markdown(
            floatfmt=".1f"
        ),
        "",
        "## Pooled OOS realised coverage by method × τ",
        "",
        out.pivot_table(index="target", columns="method", values="realised").to_markdown(
            floatfmt=".3f"
        ),
        "",
        "## Stacking diagnostic",
        "",
        "Gain = (M5_width − method_width) / M5_width. Stacking-efficiency = M6c gain / (M6a + M6b2 "
        "gains). Efficiency = 1.00 means perfectly additive; > 1.00 means super-additive (rare); "
        "< 1.00 means partial overlap (the two leads are not fully orthogonal).",
        "",
        stack_df.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Reading",
        "",
        "Read the **stacking_efficiency** column. If ≈ 1.0, the two leads address fully orthogonal "
        "structure and combining them is straightforward. If < 1.0, M6a and M6b2 partly capture the "
        "same residual variance. If > 1.0, there's a synergy term (uncommon).",
        "",
        "**Caveat — M6c is upper-bound.** Like M6a, M6c uses the leave-one-out weekend mean residual "
        "which is Monday-derived. Deployment requires a Friday-observable proxy for r̄_w. The "
        "deployable M6c gain scales with the forward predictor's R²(r̄_w | Friday-state).",
        "",
        "Reproducible via `scripts/run_m6c_combined.py`. "
        "Source data: `reports/tables/v1b_m6c_combined_oos.csv`.",
    ]
    out_md = REPORTS / "v1b_m6c_combined.md"
    out_md.write_text("\n".join(md))
    print(f"wrote {out_md}", flush=True)


if __name__ == "__main__":
    main()
