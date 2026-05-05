"""
W8 — r̄_w forward predictor prototype (AMM-track shipping gate).

M6a's upper-bound width gain (-13% at τ=0.95) uses the leave-one-out
weekend-mean residual r̄_w^(−i), which is Monday-derived. To deploy the
AMM-track (`reports/active/m6_refactor.md` Phase B), the Oracle needs a Friday-observable
predictor of r̄_w with R²(forward) ≥ 0.4 against realised r̄_w on a TRAIN/OOS
holdout.

  Dependent variable:   r̄_w = mean over symbols in weekend w of r_i,
                              where r_i = (mon_open_i − point_fa_i) / fri_close_i
                              and point_fa_i = fri_close_i · (1 + factor_ret_i).
  Features (Friday-observable only):
    macro vol:        vix_fri_close, gvz_fri_close, move_fri_close (+ week-Δ)
    panel realised:   panel_mean_fri_vol_20d, panel_std_fri_vol_20d
    calendar:         is_long_weekend, gap_days, earnings_count
    regime mix:       regime_high_vol_share
    autoregressive:   r_bar_lag1 (last weekend's realised mean residual; this is
                                  Friday-observable on the publish date because
                                  the prior Monday open is in the past)

Three model families × multiple regularisations:
    M0  — AR(1) only:                    r̄_w ~ r_bar_lag1
    M1  — macro-vol only (level + Δ):    r̄_w ~ {vix, gvz, move, Δvix, Δgvz, Δmove}
    M2  — full Friday-observable set:    union of M0 + M1 + panel + calendar

Decision rule at the gate (R²(OOS) on r̄_w):
    PASS    R²(OOS) ≥ 0.40   →  AMM-track ships under reports/active/m6_refactor.md Phase B.
    DEFER   0.20 ≤ R²(OOS) < 0.40  →  workstream continues; revisit after V3.1
                                      F_tok signal accumulation OR build a
                                      Sunday-Globex republish variant.
    REJECT  R²(OOS) < 0.20   →  archive negative result; defer M6a until either
                                a Sunday-Globex predictor or richer scryer
                                features are available.

Outputs:
  data/processed/r_bar_predictor_v1.json    fitted coefficients + decision
  reports/v1b_r_bar_forward_predictor.md    paper-ready writeup
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
GATE_PASS_R2 = 0.40
GATE_DEFER_R2 = 0.20


# ---------------------------------------------------------------------- panel

def build_weekend_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """One row per weekend (fri_ts) with the dependent variable + features."""
    p = panel.copy()
    p["point_fa"] = p["fri_close"].astype(float) * (1.0 + p["factor_ret"].astype(float))
    p["r"] = (p["mon_open"] - p["point_fa"]) / p["fri_close"]

    weekend = p.groupby("fri_ts", as_index=False).agg(
        r_bar=("r", "mean"),
        n_symbols=("r", "count"),
        vix=("vix_fri_close", "first"),
        gvz=("gvz_fri_close", "first"),
        move=("move_fri_close", "first"),
        gap_days=("gap_days", "first"),
        is_long_weekend=("is_long_weekend", "first"),
        panel_mean_vol_20d=("fri_vol_20d", "mean"),
        panel_std_vol_20d=("fri_vol_20d", "std"),
        earnings_count=("earnings_next_week_f", "sum"),
        regime_high_vol_share=("regime_pub", lambda s: float((s == "high_vol").mean())),
    )
    weekend = weekend.sort_values("fri_ts").reset_index(drop=True)

    # Lagged + week-over-week deltas (Friday-observable)
    weekend["r_bar_lag1"] = weekend["r_bar"].shift(1)
    for col in ("vix", "gvz", "move"):
        weekend[f"delta_{col}"] = weekend[col] - weekend[col].shift(1)

    return weekend


# ---------------------------------------------------------- linear model fit

def _standardize(X_train: np.ndarray, X_oos: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mu = X_train.mean(axis=0)
    sd = X_train.std(axis=0, ddof=0)
    sd = np.where(sd > 0, sd, 1.0)
    return (X_train - mu) / sd, (X_oos - mu) / sd, mu, sd


def fit_ridge(
    X: np.ndarray, y: np.ndarray, alpha: float
) -> tuple[np.ndarray, float]:
    """Ridge regression with intercept. Returns (coef, intercept)."""
    n, p = X.shape
    X1 = np.hstack([X, np.ones((n, 1))])
    A = X1.T @ X1
    if alpha > 0:
        # Penalise coefficients but not the intercept (last column)
        pen = np.eye(p + 1) * alpha
        pen[-1, -1] = 0.0
        A = A + pen
    b = X1.T @ y
    sol = np.linalg.solve(A, b)
    return sol[:-1], float(sol[-1])


def evaluate_model(
    weekend: pd.DataFrame,
    features: list[str],
    label: str,
    alpha: float,
) -> dict:
    train = weekend[weekend["fri_ts"] < SPLIT_DATE].dropna(subset=features + ["r_bar"]).reset_index(drop=True)
    oos = weekend[weekend["fri_ts"] >= SPLIT_DATE].dropna(subset=features + ["r_bar"]).reset_index(drop=True)
    X_tr = train[features].to_numpy(dtype=float)
    y_tr = train["r_bar"].to_numpy(dtype=float)
    X_oo = oos[features].to_numpy(dtype=float)
    y_oo = oos["r_bar"].to_numpy(dtype=float)

    X_tr_s, X_oo_s, mu, sd = _standardize(X_tr, X_oo)
    coef, intercept = fit_ridge(X_tr_s, y_tr, alpha=alpha)
    y_tr_hat = X_tr_s @ coef + intercept
    y_oo_hat = X_oo_s @ coef + intercept

    ss_res_tr = float(((y_tr - y_tr_hat) ** 2).sum())
    ss_tot_tr = float(((y_tr - y_tr.mean()) ** 2).sum())
    r2_tr = 1.0 - ss_res_tr / ss_tot_tr if ss_tot_tr > 0 else float("nan")

    # OOS R² uses train-mean as the null predictor (no information leakage)
    ss_res_oo = float(((y_oo - y_oo_hat) ** 2).sum())
    ss_tot_oo = float(((y_oo - y_tr.mean()) ** 2).sum())
    r2_oo = 1.0 - ss_res_oo / ss_tot_oo if ss_tot_oo > 0 else float("nan")

    return {
        "label": label,
        "alpha": alpha,
        "features": features,
        "n_train_weekends": int(len(train)),
        "n_oos_weekends": int(len(oos)),
        "r2_train": r2_tr,
        "r2_oos": r2_oo,
        "feature_means_train": mu.tolist(),
        "feature_stds_train": sd.tolist(),
        "coef_standardized": coef.tolist(),
        "intercept_standardized": intercept,
        "y_train_mean": float(y_tr.mean()),
        "y_train_std": float(y_tr.std(ddof=0)),
        "y_oos_mean": float(y_oo.mean()),
        "y_oos_std": float(y_oo.std(ddof=0)),
        "_train_dates": [str(d) for d in train["fri_ts"].tolist()],
        "_oos_dates": [str(d) for d in oos["fri_ts"].tolist()],
        "_y_oos": y_oo.tolist(),
        "_y_oos_hat": y_oo_hat.tolist(),
    }


# ----------------------------------------------------- sanity check on rho

def cross_sectional_rho_after_partial_out(
    panel: pd.DataFrame,
    weekend: pd.DataFrame,
    best_model: dict,
    features: list[str],
) -> dict:
    """Compute cross-sectional within-weekend lag-1 ρ on the partialled-out
    signed residual r_i − r̄_w_hat, where r̄_w_hat is the model's prediction
    using only Friday-observable features. β=1 (full subtraction) for the
    upper-bound diagnostic."""
    p = panel.copy()
    p["point_fa"] = p["fri_close"].astype(float) * (1.0 + p["factor_ret"].astype(float))
    p["r"] = (p["mon_open"] - p["point_fa"]) / p["fri_close"]

    # Reconstruct r̄_w_hat for every weekend
    mu = np.array(best_model["feature_means_train"])
    sd = np.array(best_model["feature_stds_train"])
    coef = np.array(best_model["coef_standardized"])
    intercept = best_model["intercept_standardized"]

    feat_df = weekend[features].copy()
    feat_df = feat_df.fillna(0.0)
    X = feat_df.to_numpy(dtype=float)
    X_s = (X - mu) / sd
    weekend["r_bar_hat"] = X_s @ coef + intercept

    p = p.merge(weekend[["fri_ts", "r_bar_hat"]], on="fri_ts", how="left")
    p["r_resid"] = p["r"] - p["r_bar_hat"]

    p_oos = p[p["fri_ts"] >= SPLIT_DATE].copy()
    p_oos = p_oos.dropna(subset=["r", "r_resid"])
    p_oos = p_oos.sort_values(["fri_ts", "symbol"]).reset_index(drop=True)

    def _rho_within_weekend(df: pd.DataFrame, col: str) -> tuple[float, int]:
        d = df.copy()
        d["x_lag"] = d.groupby("fri_ts")[col].shift(1)
        pairs = d.dropna(subset=["x_lag"])
        if len(pairs) < 30:
            return float("nan"), int(len(pairs))
        rho = float(np.corrcoef(pairs[col].values, pairs["x_lag"].values)[0, 1])
        return rho, int(len(pairs))

    rho_raw, n_raw = _rho_within_weekend(p_oos, "r")
    rho_after, n_after = _rho_within_weekend(p_oos, "r_resid")
    return {
        "rho_raw_oos": rho_raw,
        "rho_after_partial_out_oos": rho_after,
        "n_pairs_within_weekend_oos": int(n_after),
        "expected_rho_after_under_linear_partial_out_R2": float(
            (1 - max(best_model["r2_oos"], 0.0)) * rho_raw
        ),
    }


# --------------------------------------------------------------------- main

def gate_decision(r2_oos: float) -> str:
    if r2_oos >= GATE_PASS_R2:
        return "PASS"
    elif r2_oos >= GATE_DEFER_R2:
        return "DEFER"
    return "REJECT"


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret",
                "vix_fri_close", "gvz_fri_close", "move_fri_close"]
    ).copy()

    weekend = build_weekend_panel(panel)
    n_train_w = (weekend["fri_ts"] < SPLIT_DATE).sum()
    n_oos_w = (weekend["fri_ts"] >= SPLIT_DATE).sum()
    print(f"weekend panel: {len(weekend):,} weekends "
          f"(train {n_train_w}, OOS {n_oos_w})", flush=True)
    print(f"r̄_w (train) mean={weekend.loc[weekend.fri_ts < SPLIT_DATE, 'r_bar'].mean():.5f}  "
          f"std={weekend.loc[weekend.fri_ts < SPLIT_DATE, 'r_bar'].std(ddof=0):.5f}", flush=True)
    print(f"r̄_w (OOS)   mean={weekend.loc[weekend.fri_ts >= SPLIT_DATE, 'r_bar'].mean():.5f}  "
          f"std={weekend.loc[weekend.fri_ts >= SPLIT_DATE, 'r_bar'].std(ddof=0):.5f}", flush=True)

    F_AR1 = ["r_bar_lag1"]
    F_VOL = ["vix", "gvz", "move", "delta_vix", "delta_gvz", "delta_move"]
    F_FULL = list(dict.fromkeys(F_AR1 + F_VOL + [
        "panel_mean_vol_20d", "panel_std_vol_20d",
        "earnings_count", "is_long_weekend", "gap_days",
        "regime_high_vol_share",
    ]))

    variants = [
        ("M0_ar1",          F_AR1,  0.0),
        ("M1_vol_ols",      F_VOL,  0.0),
        ("M1_vol_ridge1",   F_VOL,  1.0),
        ("M2_full_ols",     F_FULL, 0.0),
        ("M2_full_ridge1",  F_FULL, 1.0),
        ("M2_full_ridge10", F_FULL, 10.0),
    ]
    results = [evaluate_model(weekend, feat, label, alpha)
               for label, feat, alpha in variants]

    print("\n=== Model comparison: R² on r̄_w ===")
    print(pd.DataFrame([{
        "label": r["label"], "alpha": r["alpha"],
        "n_features": len(r["features"]),
        "n_train": r["n_train_weekends"], "n_oos": r["n_oos_weekends"],
        "r2_train": r["r2_train"], "r2_oos": r["r2_oos"],
    } for r in results]).to_string(index=False, float_format=lambda x: f"{x:.4f}"),
        flush=True,
    )

    best = max(results, key=lambda r: r["r2_oos"])
    decision = gate_decision(best["r2_oos"])
    print(f"\nBest model: {best['label']} (alpha={best['alpha']})  "
          f"R²(OOS)={best['r2_oos']:.4f}  → DECISION: {decision}", flush=True)

    # Sanity check: cross-sectional ρ after partial-out using best model
    rho_check = cross_sectional_rho_after_partial_out(
        panel, weekend, best, best["features"]
    )
    print("\n=== Cross-sectional within-weekend lag-1 ρ (OOS) ===")
    print(f"  raw r_i:                       {rho_check['rho_raw_oos']:.4f}")
    print(f"  after r̄_w_hat partial-out:    {rho_check['rho_after_partial_out_oos']:.4f}")
    print(f"  expected (linear model, β=1): {rho_check['expected_rho_after_under_linear_partial_out_R2']:.4f}")
    print(f"  (n_pairs={rho_check['n_pairs_within_weekend_oos']})")

    # Save coefficient JSON (drop the per-weekend prediction arrays for size)
    out_payload = {
        "decision": decision,
        "gate_pass_r2": GATE_PASS_R2,
        "gate_defer_r2": GATE_DEFER_R2,
        "best_model_label": best["label"],
        "best_model_r2_oos": best["r2_oos"],
        "best_model_r2_train": best["r2_train"],
        "best_model": {k: v for k, v in best.items() if not k.startswith("_")},
        "all_models": [{k: v for k, v in r.items() if not k.startswith("_")} for r in results],
        "rho_diagnostic": rho_check,
        "split_date": SPLIT_DATE.isoformat(),
    }
    out_json = DATA_PROCESSED / "r_bar_predictor_v1.json"
    out_json.write_text(json.dumps(out_payload, indent=2, default=str))
    print(f"\nWrote {out_json}", flush=True)

    # Markdown writeup
    md = _build_markdown(weekend, results, best, decision, rho_check, n_train_w, n_oos_w)
    out_md = REPORTS / "v1b_r_bar_forward_predictor.md"
    out_md.write_text(md)
    print(f"Wrote {out_md}", flush=True)


def _build_markdown(
    weekend: pd.DataFrame,
    results: list[dict],
    best: dict,
    decision: str,
    rho_check: dict,
    n_train_w: int,
    n_oos_w: int,
) -> str:
    summary = pd.DataFrame([{
        "model": r["label"], "α (ridge)": r["alpha"],
        "n_features": len(r["features"]),
        "R²(train)": r["r2_train"], "R²(OOS)": r["r2_oos"],
    } for r in results])
    coef_table = pd.DataFrame({
        "feature": best["features"],
        "coef (standardized)": best["coef_standardized"],
        "feature_mean_train": best["feature_means_train"],
        "feature_std_train":  best["feature_stds_train"],
    })
    decision_blurb = {
        "PASS": (
            f"R²(OOS) = {best['r2_oos']:.3f} ≥ {GATE_PASS_R2:.2f}. "
            "**AMM-track shipping unblocked** under `reports/active/m6_refactor.md` Phase B. "
            "Hand the predictor JSON (`data/processed/r_bar_predictor_v1.json`) to Phase B1 "
            "(`scripts/build_m6a_amm_artefact.py`) and Phase B2 (Python serving wiring)."
        ),
        "DEFER": (
            f"R²(OOS) = {best['r2_oos']:.3f} sits in [{GATE_DEFER_R2:.2f}, {GATE_PASS_R2:.2f}). "
            "**AMM-track shipping deferred.** Friday-close-only state captures some signal but "
            "not enough to deliver a meaningful fraction of M6a's upper-bound width gain. "
            "Two productive next steps: (1) build a Sunday-Globex republish variant — capture "
            "ES/NQ moves through Sunday 18:00 ET reopen and re-evaluate; this materially raises "
            "R² but requires a forward-tape fetcher for futures (scryer wishlist). (2) Wait for "
            "V3.1 F_tok signal to accumulate (≥ 150 weekends of on-chain xStock cross-section); "
            "the cross-sectional mean of weekend xStock drift is a near-perfect proxy for r̄_w "
            "by construction. ETA Q3–Q4 2026."
        ),
        "REJECT": (
            f"R²(OOS) = {best['r2_oos']:.3f} < {GATE_DEFER_R2:.2f}. **Friday-close-only signal "
            "is too weak to support M6a deployment.** AMM-track shipping is parked. The negative "
            "result is informative: the M6a upper-bound width gain (-13% at τ=0.95) is *not* "
            "available with currently-observable Friday-close state. Either a Sunday-Globex "
            "republish architecture or a future on-chain xStock signal (V3.1 F_tok) is required. "
            "Log the result in `methodology_history.md`; revisit when scryer adds Sunday-evening "
            "futures snapshots or when V5 tape accumulates."
        ),
    }[decision]
    rho_table = pd.DataFrame([{
        "metric": "raw r_i",
        "OOS lag-1 ρ within weekend": rho_check["rho_raw_oos"],
        "n pairs": rho_check["n_pairs_within_weekend_oos"],
    }, {
        "metric": "after r̄_w_hat partial-out",
        "OOS lag-1 ρ within weekend": rho_check["rho_after_partial_out_oos"],
        "n pairs": rho_check["n_pairs_within_weekend_oos"],
    }])

    lines: list[str] = [
        "# V1b — r̄_w forward predictor prototype (W8)",
        "",
        "**Question.** M6a's upper-bound width gain (-13% at τ=0.95 OOS, see "
        "`reports/v1b_m6a_common_mode_partial_out.md`) uses the Monday-derived "
        "leave-one-out weekend-mean residual r̄_w^(−i). To deploy the AMM-track "
        "(`reports/active/m6_refactor.md` Phase B), the Oracle needs a Friday-observable "
        "predictor of r̄_w with R²(forward) ≥ 0.40 against realised r̄_w on a "
        "TRAIN/OOS holdout. This script tests whether such a predictor is "
        "achievable on currently-available Friday-close state.",
        "",
        f"**Sample.** {n_train_w} train weekends (pre-{SPLIT_DATE.isoformat()}) "
        f"+ {n_oos_w} OOS weekends ({SPLIT_DATE.isoformat()}+). Dependent "
        "variable r̄_w = panel-mean over symbols of the M6a signed residual "
        "r_i = (mon_open − point_fa) / fri_close.",
        "",
        "## Models tested",
        "",
        "| ID | Features | Comment |",
        "|---|---|---|",
        "| M0_ar1 | `r_bar_lag1` | Last-weekend autoregressive baseline. |",
        "| M1_vol_{ols, ridge1} | `vix, gvz, move, Δvix, Δgvz, Δmove` | Macro-vol level + week-Δ. |",
        "| M2_full_{ols, ridge1, ridge10} | M0 ∪ M1 ∪ panel cross-section ∪ calendar ∪ regime-mix | All Friday-observable features. |",
        "",
        "## Results",
        "",
        summary.to_markdown(index=False, floatfmt=".4f"),
        "",
        f"**Best model (by R²(OOS)):** `{best['label']}` (α={best['alpha']}). "
        f"R²(train) = {best['r2_train']:.4f}; R²(OOS) = {best['r2_oos']:.4f}.",
        "",
        "### Best-model standardised coefficients",
        "",
        coef_table.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Sanity check — cross-sectional within-weekend lag-1 ρ",
        "",
        "If the predictor is doing real work, partialling out `β·r̄_w_hat` "
        "(β=1 for the upper-bound diagnostic) should drop the cross-sectional "
        "lag-1 ρ from the W2-baseline 0.41 toward zero. Under a perfectly "
        "linear model with no idiosyncratic component, the post-partial-out ρ "
        "should equal `(1 − R²) · ρ_raw`.",
        "",
        rho_table.to_markdown(index=False, floatfmt=".4f"),
        "",
        f"Expected ρ under a perfect linear model with this R²: "
        f"`(1 − {best['r2_oos']:.3f}) · {rho_check['rho_raw_oos']:.3f} "
        f"= {rho_check['expected_rho_after_under_linear_partial_out_R2']:.4f}`.",
        "",
        "## Decision",
        "",
        f"**{decision}** — gate at R²(OOS) ≥ {GATE_PASS_R2:.2f}; "
        f"defer threshold at {GATE_DEFER_R2:.2f}.",
        "",
        decision_blurb,
        "",
        "## What's *not* in the predictor",
        "",
        "Three feature classes were left out by design and remain candidates "
        "for a follow-up if this predictor lands in DEFER:",
        "",
        "1. **Sunday-Globex futures returns.** ES/NQ reopen Sunday 18:00 ET; "
        "the gap to Monday cash open is a strong predictor of r̄_w but is "
        "not Friday-close-observable. A republish-at-Sunday architecture would "
        "capture this; scryer needs a Sunday-evening futures snapshot fetcher.",
        "2. **Sector rotation indicators.** XLK/XLF/XLE/etc. relative-strength "
        "change Friday close vs prior week. Plausibly Friday-observable from "
        "Yahoo daily ETF bars; not currently in `v1b_panel.parquet` but "
        "ingestible from `yahoo/equities_daily/v1` directly.",
        "3. **On-chain xStock cross-section signal.** The cross-sectional "
        "mean of weekend xStock drift on `soothsayer_v5/tape` is a near-perfect "
        "proxy for r̄_w by construction. Today (~30 weekends) is too small; "
        "Q3–Q4 2026 ETA per V3.1 F_tok gate.",
        "",
        "## Sources & reproducibility",
        "",
        "- Input: `data/processed/v1b_panel.parquet`",
        "- Output JSON: `data/processed/r_bar_predictor_v1.json`",
        "- Reproducible via `scripts/run_r_bar_forward_predictor.py`",
        "",
        f"Run on {pd.Timestamp.today().date().isoformat()}.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
