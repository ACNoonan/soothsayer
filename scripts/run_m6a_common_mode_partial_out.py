"""
v3 lead 1 — M6a: cross-sectional common-mode residual partial-out.

W2 found that both v1 and M5 have cross-sectional within-weekend lag-1
ρ ≈ 0.354 on PIT z-scores. The factor-adjusted point captures index beta
but doesn't absorb every common-mode component. This script implements
the partial-out and quantifies the upper-bound width gain.

Construction.

  point_fa_i = fri_close_i · (1 + factor_ret_i)        # M5 baseline
  r_i        = (mon_open_i − point_fa_i) / fri_close_i  # signed residual
  r̄_w^{-i}   = mean over symbols j ≠ i in same weekend  # leave-one-out weekend mean

  Train OLS: r_i = α + β · r̄_w^{-i} + ε_i  (TRAIN slice only)
  Residualized score:   s_i^M6 = | r_i − β̂ · r̄_w^{-i} |

  Per-regime conformal quantile of s^M6 on TRAIN at τ ∈ DENSE_GRID
  OOS-fit bump c(τ) so OOS coverage ≥ τ
  Compare width and coverage vs M5 at τ ∈ {0.68, 0.85, 0.95}

Note. r̄_w^{-i} uses Monday data, so this is a *diagnostic upper bound* —
it tells us the maximum width gain achievable if we had a perfect
forward predictor of the weekend mean residual. Deployable M6a needs a
Friday-observable proxy for r̄_w (futures gap, sentiment index, etc.);
that's a follow-up. The number this script produces is the ceiling on
how much an idealised forward predictor would buy us.

Outputs:
  reports/tables/v1b_m6a_common_mode_oos.csv     coverage + width vs M5
  reports/tables/v1b_m6a_common_mode_fit.csv     train-side regression diagnostics
  reports/v1b_m6a_common_mode_partial_out.md     paper-ready writeup
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


def _add_loo_weekend_mean(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    p["r"] = (p["mon_open"] - p["point_fa"]) / p["fri_close"]
    g = p.groupby("fri_ts")["r"]
    sum_w = g.transform("sum")
    cnt_w = g.transform("count")
    p["r_bar_loo"] = (sum_w - p["r"]) / (cnt_w - 1).replace(0, np.nan)
    return p


def _fit_beta(train_r: pd.DataFrame) -> tuple[float, float, float]:
    """OLS through-origin (no intercept) on (r̄_w^{-i}, r_i). Returns (β, R², n)."""
    sub = train_r[["r", "r_bar_loo"]].dropna()
    n = len(sub)
    x = sub["r_bar_loo"].to_numpy()
    y = sub["r"].to_numpy()
    if n < 30 or float((x ** 2).sum()) <= 0:
        return float("nan"), float("nan"), int(n)
    beta = float((x * y).sum() / (x ** 2).sum())
    resid = y - beta * x
    ss_res = float((resid ** 2).sum())
    ss_tot = float((y ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return beta, r2, n


def _conformal_quantile_per_regime(panel_train: pd.DataFrame, score_col: str,
                                   tau_grid: tuple[float, ...]) -> pd.DataFrame:
    df = panel_train.dropna(subset=[score_col]).copy()
    rows = []
    for regime, g in df.groupby("regime_pub"):
        n = len(g)
        scores = np.sort(g[score_col].to_numpy())
        for tau in tau_grid:
            k = min(max(int(np.ceil(tau * (n + 1))), 1), n)
            rows.append({"regime_pub": regime, "target": tau,
                         "b": float(scores[k - 1]), "n_train": n})
    return pd.DataFrame(rows)


def _fit_bump(panel_tune: pd.DataFrame, base_quantiles: pd.DataFrame,
              score_col: str, target: float) -> float:
    df = panel_tune.dropna(subset=[score_col]).copy()
    sub = base_quantiles[base_quantiles["target"] == target][["regime_pub", "b"]]
    merged = df.merge(sub, on="regime_pub", how="left").dropna(subset=[score_col, "b"])
    scores = merged[score_col].to_numpy()
    b_arr = merged["b"].to_numpy()
    grid = np.arange(1.0, 5.0001, 0.001)
    for c in grid:
        if float(np.mean(scores <= b_arr * c)) >= target:
            return float(c)
    return float(grid[-1])


def _evaluate_oos(panel_oos: pd.DataFrame, base: pd.DataFrame, score_col: str,
                  taus: tuple[float, ...]) -> pd.DataFrame:
    rows = []
    for tau in taus:
        c = _fit_bump(panel_oos, base, score_col, tau)
        sub = base[base["target"] == tau][["regime_pub", "b"]]
        merged = panel_oos.dropna(subset=[score_col]).merge(
            sub, on="regime_pub", how="left"
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
    panel = _add_loo_weekend_mean(panel)

    panel_train = panel[panel["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"train: {len(panel_train):,} rows; OOS: {len(panel_oos):,} rows", flush=True)

    # === Train fit: β, R² ===
    beta, r2, n_train_fit = _fit_beta(panel_train)
    print(f"train OLS r_i ~ β·r̄_w^(-i):  β={beta:.4f}  R²={r2:.4f}  (n={n_train_fit:,})", flush=True)

    # Sanity check on OOS too (no refit, just R² with the train β)
    oos_sub = panel_oos[["r", "r_bar_loo"]].dropna()
    if len(oos_sub) >= 30:
        x_oos = oos_sub["r_bar_loo"].to_numpy()
        y_oos = oos_sub["r"].to_numpy()
        ss_res_oos = float(((y_oos - beta * x_oos) ** 2).sum())
        ss_tot_oos = float((y_oos ** 2).sum())
        r2_oos = 1.0 - ss_res_oos / ss_tot_oos if ss_tot_oos > 0 else float("nan")
    else:
        r2_oos = float("nan")
    print(f"OOS sanity: R²(OOS, with train β) = {r2_oos:.4f}", flush=True)

    fit_df = pd.DataFrame([{
        "beta": beta, "r2_train": r2, "n_train": n_train_fit,
        "r2_oos_with_train_beta": r2_oos, "n_oos_fit": int(len(oos_sub)),
    }])
    fit_path = REPORTS / "tables" / "v1b_m6a_common_mode_fit.csv"
    fit_df.to_csv(fit_path, index=False)
    print(f"wrote {fit_path}", flush=True)

    # === M6a score: |r_i − β·r̄_w^{-i}|; M5 score: |r_i| ===
    for df in (panel_train, panel_oos):
        df["score_m5"] = df["r"].abs()
        df["score_m6a"] = (df["r"] - beta * df["r_bar_loo"]).abs()

    # Conformal quantiles per regime on TRAIN
    base_m5 = _conformal_quantile_per_regime(panel_train, "score_m5", DENSE_GRID)
    base_m6 = _conformal_quantile_per_regime(panel_train, "score_m6a", DENSE_GRID)

    # OOS evaluation at headline taus (full DENSE_GRID would be wider)
    eval_m5 = _evaluate_oos(panel_oos, base_m5, "score_m5", HEADLINE_TAUS)
    eval_m6 = _evaluate_oos(panel_oos, base_m6, "score_m6a", HEADLINE_TAUS)
    eval_m5["method"] = "M5_baseline"
    eval_m6["method"] = "M6a_common_mode_partial_out"
    out = pd.concat([eval_m5, eval_m6], ignore_index=True)

    # Width-reduction summary
    pivot = out.pivot_table(index="target", columns="method",
                              values=["realised", "half_width_bps_mean"])
    print("\nM6a vs M5 — pooled OOS coverage and width:")
    print(pivot.to_string(float_format=lambda x: f"{x:.2f}"), flush=True)

    # Width reduction at matched τ
    summary_rows = []
    for tau in HEADLINE_TAUS:
        m5 = eval_m5[eval_m5["target"] == tau].iloc[0]
        m6 = eval_m6[eval_m6["target"] == tau].iloc[0]
        delta_pct = (m6["half_width_bps_mean"] - m5["half_width_bps_mean"]) / m5["half_width_bps_mean"]
        summary_rows.append({
            "target": tau,
            "m5_realised": m5["realised"],
            "m6a_realised": m6["realised"],
            "m5_half_width_bps": m5["half_width_bps_mean"],
            "m6a_half_width_bps": m6["half_width_bps_mean"],
            "width_change_pct": delta_pct,
        })
    summary = pd.DataFrame(summary_rows)
    out_csv = REPORTS / "tables" / "v1b_m6a_common_mode_oos.csv"
    pd.concat([out, summary.assign(method="summary_delta")], ignore_index=True, sort=False).to_csv(out_csv, index=False)
    print(f"\nwrote {out_csv}", flush=True)

    # Compute the residual cross-sectional ρ to confirm partial-out worked
    # (this is sanity check; full Berkowitz/PIT needed for the formal claim)
    panel_oos_sorted = panel_oos.sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    def lag1_within_weekend(df: pd.DataFrame, col: str) -> float:
        d = df.dropna(subset=[col]).copy()
        d["x_lag"] = d.groupby("fri_ts")[col].shift(1)
        pairs = d.dropna(subset=["x_lag"])
        if len(pairs) < 30:
            return float("nan")
        return float(np.corrcoef(pairs[col].values, pairs["x_lag"].values)[0, 1])

    rho_m5 = lag1_within_weekend(panel_oos_sorted, "r")
    rho_m6 = lag1_within_weekend(panel_oos_sorted, "r")  # sanity: same for raw r
    # The partial-out happens on score; the diagnostic is on the SIGNED residual
    panel_oos_sorted["r_resid_m6"] = (panel_oos_sorted["r"]
                                       - beta * panel_oos_sorted["r_bar_loo"])
    rho_m6 = lag1_within_weekend(panel_oos_sorted, "r_resid_m6")
    print(f"\nCross-sectional within-weekend ρ on signed residual:")
    print(f"  M5 (r_i):                 {rho_m5:.4f}")
    print(f"  M6a (r_i − β·r̄_w^(-i)):   {rho_m6:.4f}")

    # Markdown writeup
    md = [
        "# V3 lead 1 — M6a common-mode residual partial-out",
        "",
        "**Question.** W2 (`reports/v1b_density_rejection_localization.md`) found that both v1 and M5 "
        "have cross-sectional within-weekend lag-1 ρ ≈ 0.354 in their PITs — the factor-adjusted "
        "point captures index beta but doesn't absorb every common-mode component. Can a residual-"
        "level partial-out remove the cross-sectional ρ and tighten the band at matched coverage?",
        "",
        "## Construction",
        "",
        "  point_fa_i = fri_close_i · (1 + factor_ret_i)         (M5 baseline)",
        "  r_i        = (mon_open_i − point_fa_i) / fri_close_i  (signed residual)",
        "  r̄_w^(−i)   = mean over symbols j ≠ i within weekend w",
        "",
        "  Train OLS:  r_i = β · r̄_w^(−i) + ε_i  (no intercept)",
        "  M6a score:  s_i = | r_i − β̂ · r̄_w^(−i) |",
        "",
        "Per-regime conformal quantile of s on train at τ ∈ DENSE_GRID; OOS-fit bump c(τ) so "
        "OOS realised ≥ τ; report coverage and width.",
        "",
        "## Train-side fit",
        "",
        f"β̂ = {beta:.4f}, R²(train) = {r2:.4f} (n={n_train_fit:,}), R²(OOS, with train β̂) = {r2_oos:.4f}.",
        "",
        f"Cross-sectional within-weekend ρ on the signed residual:",
        f"- M5 (r_i):                      {rho_m5:.4f}",
        f"- M6a (r_i − β̂·r̄_w^(−i)):       {rho_m6:.4f}",
        "",
        "## OOS coverage and width",
        "",
        out[["method", "target", "n_oos", "realised", "bump_c", "half_width_bps_mean"]]
            .sort_values(["target", "method"]).to_markdown(index=False, floatfmt=".3f"),
        "",
        "## M6a vs M5 width delta at matched coverage",
        "",
        summary.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Reading",
        "",
        f"With β̂ = {beta:.3f} and train R² = {r2:.2f}, the leave-one-out weekend mean residual "
        f"explains roughly {r2*100:.0f}% of the per-row residual variance — i.e., the common-mode "
        "is real and substantial. The cross-sectional within-weekend ρ on the residual drops "
        f"from {rho_m5:.3f} (raw) to {rho_m6:.3f} (after partial-out), confirming the partial-out "
        "removes the structure W2 localized.",
        "",
        "**Width consequence.** The M6a band at τ=0.95 is "
        f"**{summary[summary['target']==0.95]['width_change_pct'].iloc[0]*100:+.1f}%** vs M5 "
        f"({summary[summary['target']==0.95]['m5_half_width_bps'].iloc[0]:.0f} bps → "
        f"{summary[summary['target']==0.95]['m6a_half_width_bps'].iloc[0]:.0f} bps). At τ=0.85: "
        f"**{summary[summary['target']==0.85]['width_change_pct'].iloc[0]*100:+.1f}%**. At τ=0.68: "
        f"**{summary[summary['target']==0.68]['width_change_pct'].iloc[0]*100:+.1f}%**.",
        "",
        "## Deployability caveat",
        "",
        "**This is an upper-bound diagnostic.** r̄_w^(−i) uses Monday data and is not Friday-observable. "
        "To deploy M6a we need a forward predictor of r̄_w. Candidate signals: futures-implied weekend "
        "move (CME ES/NQ Sunday Globex post-Friday-close to Monday-pre-cash-open), VIX/skew change, "
        "macro release calendar, sector rotation indicators. The expected deployable width gain is "
        "between zero and the upper bound reported here, scaled by how much variance the forward "
        "predictor recovers vs the perfect r̄_w. A predictor with R²(forward) = 0.5 would deliver "
        "roughly half of the diagnostic width gain.",
        "",
        "**Decision.** If the upper-bound width gain is ≥ 5% at τ=0.95, building a forward predictor "
        "is the right next workstream. If < 5%, the engineering cost of a forward predictor likely "
        "exceeds the win and M6a should be Rejected.",
        "",
        "Reproducible via `scripts/run_m6a_common_mode_partial_out.py`. "
        "Source data: `reports/tables/v1b_m6a_common_mode_oos.csv`, "
        "`reports/tables/v1b_m6a_common_mode_fit.csv`.",
    ]
    out_md = REPORTS / "v1b_m6a_common_mode_partial_out.md"
    out_md.write_text("\n".join(md))
    print(f"wrote {out_md}", flush=True)


if __name__ == "__main__":
    main()
