"""Paper 1 — Tier A item A2.

Nested temporal × symbol holdout for the c(τ) bump.

Today the §6.3 headline is fit-on-evaluate at the *time* level:
  q_cell^LWC(τ) trained on pre-2023; c(τ) fit on OOS 2023+; evaluated on
  OOS 2023+. LOSO holds out a symbol but not time.

This script splits OOS three ways:
  TRAIN = fri_ts < 2023-01-01     (per-regime CP quantile, unchanged)
  TUNE  = 2023-01-01 ≤ fri_ts < 2024-01-01   (c(τ) bump fit slice — held out)
  EVAL  = fri_ts ≥ 2024-01-01     (true holdout for headline)

Three reporting modes for a clean fit-on-eval ablation:

  M_full    q on TRAIN; c on (TUNE ∪ EVAL); eval on (TUNE ∪ EVAL)   (current)
  M_evalsub q on TRAIN; c on (TUNE ∪ EVAL); eval on EVAL            (strips eval slice change)
  M_a2      q on TRAIN; c on TUNE only;     eval on EVAL            (true holdout)

For each mode we report at τ ∈ {0.68, 0.85, 0.95, 0.99}:
  - Realised coverage, mean half-width (bps of fri_close)
  - Kupiec uc (LR + p), Christoffersen ind (LR + p)
  - Per-symbol Kupiec at τ=0.95 (count of pass/fail)

The diff M_full → M_a2 is the proper-holdout headline. The diff M_full →
M_evalsub isolates "different evaluation period" from "fit-on-evaluate":
M_a2's degradation should equal (M_full → M_evalsub change due to era
shift) + (extra degradation from fitting c on tune-only). If M_a2 still
shows realised ≈ τ at τ=0.95, the headline holds out properly.

Output:
  reports/tables/paper1_a2_nested_holdout_c_tau.csv
  reports/tables/paper1_a2_nested_holdout_c_tau_per_symbol.csv
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

TRAIN_END = date(2023, 1, 1)   # exclusive
TUNE_END  = date(2024, 1, 1)   # exclusive (2023 = TUNE)
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)


def evaluate_at_taus(panel_eval: pd.DataFrame,
                     qt: dict[str, dict[float, float]],
                     cb: dict[float, float],
                     taus: tuple[float, ...]) -> pd.DataFrame:
    """Coverage / Kupiec / Christoffersen / half-width at each τ on `panel_eval`."""
    rows = []
    cells = panel_eval["regime_pub"].astype(str).to_numpy()
    sigma = panel_eval["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    fri_close = panel_eval["fri_close"].astype(float).to_numpy()
    score = panel_eval["score_lwc"].astype(float).to_numpy()
    base_valid = np.isfinite(score) & np.isfinite(sigma) & (sigma > 0)
    for tau in taus:
        c = cb[tau]
        b_per_row = np.array(
            [qt.get(cells[i], {}).get(tau, np.nan) for i in range(len(panel_eval))],
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
        fri_v = fri_close[valid]
        # half-width in bps: q_eff · σ̂ · fri_close, divided by fri_close, ×1e4
        hw_bps = b_eff * sigma_v * 1e4
        rows.append({
            "target": tau, "bump_c": float(c),
            "n_eval": int(valid.sum()),
            "realised": float(inside.mean()),
            "kupiec_lr": float(lr_uc), "kupiec_p": float(p_uc),
            "christoffersen_lr": float(lr_ind),
            "christoffersen_p": float(p_ind),
            "half_width_bps_mean": float(hw_bps.mean()),
            "half_width_bps_median": float(np.median(hw_bps)),
        })
    return pd.DataFrame(rows)


def per_symbol_kupiec(panel_eval: pd.DataFrame,
                      qt: dict, cb: dict, tau: float = 0.95) -> pd.DataFrame:
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
    rows = []
    for sym, g in sub.groupby("symbol"):
        v = g["viol"].to_numpy()
        if len(v) < 5:
            continue
        lr, p = met._lr_kupiec(v, tau)
        rows.append({"symbol": str(sym), "n": int(len(v)),
                     "viol_rate": float(v.mean()),
                     "kupiec_lr": float(lr), "kupiec_p": float(p)})
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    # Deployed σ̂ rule
    panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HAT_HL_WEEKENDS)
    sigma_col = f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HAT_HL_WEEKENDS}"
    panel["sigma_hat_sym_pre_fri"] = panel[sigma_col]
    panel["score_lwc"] = compute_score_lwc(panel, scale_col="sigma_hat_sym_pre_fri")

    panel_eval_mask = panel["score_lwc"].notna()
    panel = panel[panel_eval_mask].reset_index(drop=True)

    train = panel[panel["fri_ts"] <  TRAIN_END].reset_index(drop=True)
    tune  = panel[(panel["fri_ts"] >= TRAIN_END)
                  & (panel["fri_ts"] <  TUNE_END)].reset_index(drop=True)
    eval_ = panel[panel["fri_ts"] >= TUNE_END].reset_index(drop=True)
    full_oos = panel[panel["fri_ts"] >= TRAIN_END].reset_index(drop=True)

    print(f"TRAIN: {len(train):,} rows × {train['fri_ts'].nunique()} weekends "
          f"({train['fri_ts'].min()} → {train['fri_ts'].max()})", flush=True)
    print(f"TUNE:  {len(tune):,} rows × {tune['fri_ts'].nunique()} weekends "
          f"({tune['fri_ts'].min()} → {tune['fri_ts'].max()})", flush=True)
    print(f"EVAL:  {len(eval_):,} rows × {eval_['fri_ts'].nunique()} weekends "
          f"({eval_['fri_ts'].min()} → {eval_['fri_ts'].max()})", flush=True)

    # Per-regime CP quantile on TRAIN, shared across all modes
    qt = train_quantile_table(train, cell_col="regime_pub",
                              taus=HEADLINE_TAUS, score_col="score_lwc")

    # cb fit on full OOS = TUNE ∪ EVAL (current paper convention)
    cb_full = fit_c_bump_schedule(full_oos, qt, cell_col="regime_pub",
                                   taus=HEADLINE_TAUS, score_col="score_lwc")
    # cb fit on TUNE only (2023) — A2 true holdout convention
    cb_tune = fit_c_bump_schedule(tune, qt, cell_col="regime_pub",
                                   taus=HEADLINE_TAUS, score_col="score_lwc")

    print("\nbump c(τ):")
    print(f"  cb_full ({{TUNE ∪ EVAL}}): {cb_full}")
    print(f"  cb_tune ({{TUNE only}}):   {cb_tune}")

    # Three reporting modes
    modes = [
        ("M_full_fit_on_eval",         full_oos, cb_full),
        ("M_evalsub_full_cb",          eval_,    cb_full),
        ("M_a2_proper_holdout",        eval_,    cb_tune),
    ]

    pooled_rows = []
    persym_frames = []
    for name, slice_df, cb in modes:
        print(f"\n[{name}] eval on {len(slice_df):,} rows × "
              f"{slice_df['fri_ts'].nunique()} weekends", flush=True)
        df = evaluate_at_taus(slice_df, qt, cb, HEADLINE_TAUS)
        print(df[["target","realised","bump_c","kupiec_p",
                  "christoffersen_p","half_width_bps_mean"]]
              .to_string(index=False, float_format=lambda x: f"{x:.3f}"))
        for r in df.to_dict("records"):
            pooled_rows.append({"mode": name, **r})
        persym = per_symbol_kupiec(slice_df, qt, cb, tau=0.95)
        persym["mode"] = name
        persym_frames.append(persym)
        n_pass = int((persym["kupiec_p"] >= 0.05).sum())
        print(f"  per-symbol Kupiec at τ=0.95: {n_pass}/{len(persym)} pass")

    pooled_df = pd.DataFrame(pooled_rows)
    persym_df = pd.concat(persym_frames, ignore_index=True)
    out_pooled = REPORTS / "tables" / "paper1_a2_nested_holdout_c_tau.csv"
    out_persym = REPORTS / "tables" / "paper1_a2_nested_holdout_c_tau_per_symbol.csv"
    pooled_df.to_csv(out_pooled, index=False)
    persym_df.to_csv(out_persym, index=False)
    print(f"\nwrote {out_pooled}\nwrote {out_persym}")

    # Headline diff at τ=0.95
    print("\n=== headline τ=0.95 cross-mode comparison ===")
    pivot = pooled_df[pooled_df["target"] == 0.95].set_index("mode")[
        ["n_eval", "realised", "bump_c", "kupiec_p", "christoffersen_p",
         "half_width_bps_mean"]
    ]
    print(pivot.to_string(float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
