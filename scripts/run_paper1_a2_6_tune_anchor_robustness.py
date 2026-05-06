"""Paper 1 — Tier A v2 item A2.6.

Refit the A2 nested-temporal-holdout design at each of {2021, 2022, 2023,
2024} as the TUNE-only window. The A2 result picks 2023 because that's where
the v1 panel naturally splits, but a hostile referee will ask "what if you'd
tuned on 2022, or 2024?". The robustness sweep answers that pre-emptively.

For each TUNE anchor year Y:
  TRAIN = panel where fri_ts < {Y}-01-01
  TUNE  = panel where {Y}-01-01 ≤ fri_ts < {Y+1}-01-01    (52 weekends)
  EVAL  = panel where fri_ts ≥ {Y+1}-01-01                (held-out)

Run the deployed M6 LWC pipeline (per-regime CP quantile on TRAIN; c(τ)
bump on TUNE only) and evaluate on EVAL. Report at τ ∈ {0.68, 0.85, 0.95,
0.99}: realised coverage, Kupiec, Christoffersen, per-symbol Kupiec count
at τ=0.95.

Decision rule (per the work doc):
  - If τ=0.95 realised coverage stays in [0.945, 0.955] across all four
    anchors → A2 + existing split-date sensitivity tell one coherent story.
  - If anchors vary materially → add a TUNE-window-sensitivity disclosure.

Output:
  reports/tables/paper1_a2_6_tune_anchor_robustness.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    add_sigma_hat_sym_ewma,
    SIGMA_HAT_HL_WEEKENDS,
    train_quantile_table,
    fit_c_bump_schedule,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
TUNE_ANCHORS = (2021, 2022, 2023, 2024)


def evaluate_at_taus(panel_eval: pd.DataFrame,
                     qt: dict, cb: dict,
                     taus: tuple[float, ...]) -> pd.DataFrame:
    rows = []
    cells = panel_eval["regime_pub"].astype(str).to_numpy()
    sigma = panel_eval["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    score = panel_eval["score_lwc"].astype(float).to_numpy()
    base_valid = np.isfinite(score) & np.isfinite(sigma) & (sigma > 0)
    for tau in taus:
        c = cb[tau]
        b_per_row = np.array(
            [qt.get(cells[i], {}).get(tau, np.nan)
             for i in range(len(panel_eval))],
            dtype=float,
        )
        valid = base_valid & np.isfinite(b_per_row)
        s = score[valid]
        b_eff = b_per_row[valid] * c
        inside = (s <= b_eff).astype(int)
        viol = (1 - inside).astype(int)
        lr_uc, p_uc = met._lr_kupiec(viol, tau)
        lr_ind, p_ind = met._lr_christoffersen_independence(viol)
        sigma_v = sigma[valid]
        hw_bps = b_eff * sigma_v * 1e4
        rows.append({
            "target": tau, "bump_c": float(c),
            "n_eval": int(valid.sum()),
            "realised": float(inside.mean()),
            "kupiec_p": float(p_uc),
            "christoffersen_p": float(p_ind),
            "half_width_bps_mean": float(hw_bps.mean()),
        })
    return pd.DataFrame(rows)


def per_symbol_pass_count(panel_eval: pd.DataFrame, qt: dict, cb: dict,
                          tau: float = 0.95) -> tuple[int, int]:
    cells = panel_eval["regime_pub"].astype(str).to_numpy()
    score = panel_eval["score_lwc"].astype(float).to_numpy()
    sigma = panel_eval["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    c = cb[tau]
    b_per_row = np.array(
        [qt.get(cells[i], {}).get(tau, np.nan) for i in range(len(panel_eval))],
        dtype=float,
    )
    valid = np.isfinite(score) & np.isfinite(b_per_row) & np.isfinite(sigma) & (sigma > 0)
    sub = panel_eval[valid].copy()
    sub["score"] = score[valid]
    sub["b_eff"] = b_per_row[valid] * c
    sub["viol"] = (sub["score"] > sub["b_eff"]).astype(int)
    n_pass = 0
    n_total = 0
    for sym, g in sub.groupby("symbol"):
        v = g["viol"].to_numpy()
        if len(v) < 5:
            continue
        n_total += 1
        _, p = met._lr_kupiec(v, tau)
        if p >= 0.05:
            n_pass += 1
    return n_pass, n_total


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HAT_HL_WEEKENDS)
    sigma_col = f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HAT_HL_WEEKENDS}"
    panel["sigma_hat_sym_pre_fri"] = panel[sigma_col]
    panel["score_lwc"] = compute_score_lwc(panel, scale_col="sigma_hat_sym_pre_fri")
    panel = panel[panel["score_lwc"].notna()].reset_index(drop=True)

    rows_pool = []
    for anchor_year in TUNE_ANCHORS:
        train_end = date(anchor_year, 1, 1)
        tune_end  = date(anchor_year + 1, 1, 1)

        train = panel[panel["fri_ts"] <  train_end].reset_index(drop=True)
        tune  = panel[(panel["fri_ts"] >= train_end)
                      & (panel["fri_ts"] <  tune_end)].reset_index(drop=True)
        eval_ = panel[panel["fri_ts"] >= tune_end].reset_index(drop=True)

        if len(eval_) < 100 or tune["fri_ts"].nunique() < 20:
            print(f"[anchor {anchor_year}] SKIP — eval/tune too small "
                  f"(eval={len(eval_)}, tune_weekends={tune['fri_ts'].nunique()})",
                  flush=True)
            continue

        print(f"\n[anchor {anchor_year}] TRAIN={len(train):,} ({train['fri_ts'].min()} → {train['fri_ts'].max()})  "
              f"TUNE={len(tune):,} ({tune['fri_ts'].min()} → {tune['fri_ts'].max()}, {tune['fri_ts'].nunique()} weekends)  "
              f"EVAL={len(eval_):,} ({eval_['fri_ts'].min()} → {eval_['fri_ts'].max()}, {eval_['fri_ts'].nunique()} weekends)",
              flush=True)

        qt = train_quantile_table(train, cell_col="regime_pub",
                                   taus=HEADLINE_TAUS, score_col="score_lwc")
        cb = fit_c_bump_schedule(tune, qt, cell_col="regime_pub",
                                  taus=HEADLINE_TAUS, score_col="score_lwc")
        print(f"  c(τ): " + ", ".join(f"τ={t:.2f}→{cb[t]:.3f}" for t in HEADLINE_TAUS))

        df = evaluate_at_taus(eval_, qt, cb, HEADLINE_TAUS)
        n_pass, n_total = per_symbol_pass_count(eval_, qt, cb, tau=0.95)
        for r in df.to_dict("records"):
            rows_pool.append({
                "tune_anchor_year": anchor_year,
                "n_train_weekends": int(train["fri_ts"].nunique()),
                "n_tune_weekends":  int(tune["fri_ts"].nunique()),
                "n_eval_weekends":  int(eval_["fri_ts"].nunique()),
                "per_symbol_pass_at_0.95": n_pass,
                "per_symbol_total":         n_total,
                **r,
            })
        print(df[["target","realised","bump_c","kupiec_p",
                  "christoffersen_p","half_width_bps_mean"]]
              .to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        print(f"  per-symbol Kupiec at τ=0.95: {n_pass}/{n_total} pass")

    out_df = pd.DataFrame(rows_pool)
    out_path = REPORTS / "tables" / "paper1_a2_6_tune_anchor_robustness.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}", flush=True)

    print("\n=== headline τ=0.95 across TUNE anchors ===")
    pivot = out_df[out_df["target"] == 0.95].set_index("tune_anchor_year")[
        ["n_eval_weekends", "realised", "bump_c", "kupiec_p",
         "christoffersen_p", "per_symbol_pass_at_0.95",
         "half_width_bps_mean"]
    ]
    print(pivot.to_string(float_format=lambda x: f"{x:.4f}"))

    if len(pivot) > 0:
        spread = pivot["realised"].max() - pivot["realised"].min()
        in_band = ((pivot["realised"] >= 0.945) & (pivot["realised"] <= 0.955)).all()
        print(f"\nτ=0.95 realised spread: {spread:.4f} "
              f"(in [0.945, 0.955] for all anchors: {in_band})")


if __name__ == "__main__":
    main()
