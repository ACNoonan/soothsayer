"""
Vol-tertile sub-split of `normal` regime — §10.2 robustness check.

The §6.3.1 Berkowitz LR=173.1 rejection on M5 PITs is hypothesised in §9.4
to be driven by the coarse three-bin classifier (`normal | long_weekend |
high_vol`). The cheapest test of that hypothesis is to split `normal` into
trailing-vol tertiles and re-fit Mondrian conformal with five cells:

    {normal_calm, normal_mid, normal_heavy, long_weekend, high_vol}

where the normal-regime split uses VIX at fri_close tertiles within the
training window — the natural pre-publish vol axis.

Decision criterion
------------------
- If pooled Berkowitz LR drops materially (e.g., < 100), the bin-structure
  story is supported and CQR can stay deferred (§10.2).
- If LR stays near 173, the rejection is *not* driven by the three-bin
  classifier and CQR moves up the priority list.

Output
------
  reports/tables/v1b_robustness_vol_tertile.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import norm

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    compute_score,
    fit_c_bump_schedule,
    serve_bands,
    train_quantile_table,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)


def assign_vol_tertile(panel: pd.DataFrame, split_date: date) -> pd.DataFrame:
    """Within the `normal` regime, split into VIX-tertile cells using
    pre-split (training-window) terciles.

    Returns the panel with a new `vol_tertile_cell` column matching one of:
        normal_calm | normal_mid | normal_heavy | long_weekend | high_vol
    """
    out = panel.copy()
    train_normal = out[(out["fri_ts"] < split_date) &
                       (out["regime_pub"] == "normal")]
    if len(train_normal) < 30:
        raise RuntimeError("too few train-side normal-regime rows for "
                           "tertile split")
    q33, q67 = train_normal["vix_fri_close"].quantile([1/3, 2/3]).values
    cell = out["regime_pub"].astype(str).copy()
    is_normal = out["regime_pub"] == "normal"
    cell.loc[is_normal & (out["vix_fri_close"] <= q33)] = "normal_calm"
    cell.loc[is_normal & (out["vix_fri_close"] > q33) &
             (out["vix_fri_close"] < q67)] = "normal_mid"
    cell.loc[is_normal & (out["vix_fri_close"] >= q67)] = "normal_heavy"
    out["vol_tertile_cell"] = cell.values
    out.attrs["vix_tertile_anchors"] = (float(q33), float(q67))
    return out


def m5_pit(panel_oos: pd.DataFrame, qt: dict, c: dict,
           cell_col: str, dense_grid: tuple) -> np.ndarray:
    """Build M5 PITs at the per-row served-band CDF using a dense τ grid.

    Mirrors the construction in `run_density_rejection_diagnostics.py`:
    served τ' = τ; q_eff(τ) = c(τ) · b_cell(τ); CDF anchors at
    F(point ± q_eff·point) = 0.5 ± τ/2; PIT(realised) = interp.

    Caller is responsible for the row order — Berkowitz's lag-1 alternative
    is order-dependent. Match the §6.3.1 reference which sorts by
    (fri_ts, symbol) so the lag-1 pairs are cross-sectional within a
    weekend (the load-bearing common-mode autocorrelation source).
    """
    grid_taus = np.array(sorted(dense_grid))
    point = panel_oos["fri_close"].astype(float) * (
        1.0 + panel_oos["factor_ret"].astype(float)
    )
    cells = panel_oos[cell_col].astype(str).to_numpy()
    pits = np.full(len(panel_oos), np.nan)
    for i, ((idx, row), cell) in enumerate(zip(panel_oos.iterrows(), cells)):
        q_row = qt.get(cell)
        if q_row is None:
            continue
        b_anchors = []
        for tau in grid_taus:
            tau_anchors = sorted(q_row.keys())
            if tau <= tau_anchors[0]:
                b = q_row[tau_anchors[0]]
            elif tau >= tau_anchors[-1]:
                b = q_row[tau_anchors[-1]]
            else:
                for j in range(len(tau_anchors) - 1):
                    lo, hi = tau_anchors[j], tau_anchors[j + 1]
                    if lo <= tau <= hi:
                        frac = (tau - lo) / (hi - lo)
                        b = q_row[lo] + frac * (q_row[hi] - q_row[lo])
                        break
            c_anchors = sorted(c.keys())
            if tau <= c_anchors[0]:
                cv = c[c_anchors[0]]
            elif tau >= c_anchors[-1]:
                cv = c[c_anchors[-1]]
            else:
                for j in range(len(c_anchors) - 1):
                    lo, hi = c_anchors[j], c_anchors[j + 1]
                    if lo <= tau <= hi:
                        frac = (tau - lo) / (hi - lo)
                        cv = c[lo] + frac * (c[hi] - c[lo])
                        break
            b_anchors.append(b * cv)
        b_anchors = np.array(b_anchors, dtype=float)
        if not np.all(np.isfinite(b_anchors)):
            continue
        r = (row["mon_open"] - point.iloc[i]) / row["fri_close"]
        abs_r = abs(float(r))
        anchor_b = np.concatenate(([0.0], b_anchors))
        anchor_tau = np.concatenate(([0.0], grid_taus))
        if abs_r >= anchor_b[-1]:
            tau_hat = anchor_tau[-1]
        else:
            tau_hat = float(np.interp(abs_r, anchor_b, anchor_tau))
        pits[i] = 0.5 + 0.5 * tau_hat * (1 if r >= 0 else -1)
    return pits


def run_one(name: str, panel: pd.DataFrame, cell_col: str,
            dense_grid: tuple) -> dict:
    """Fit M5 with the supplied cell axis on pre-2023 train, c-bump on
    post-2023 OOS, and report Berkowitz on OOS PITs at the dense grid."""
    train = panel[panel["fri_ts"] < SPLIT_DATE].dropna(subset=["score"])
    # Sort cross-sectionally so the Berkowitz lag-1 pair is (sym_i, sym_{i+1})
    # within the same Friday — matches the §6.3.1 LR = 173 reference.
    oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
           .dropna(subset=["score"])
           .sort_values(["fri_ts", "symbol"])
           .reset_index(drop=True))

    # Train on dense grid so the PIT interpolation has fine support.
    qt = train_quantile_table(train, cell_col=cell_col, taus=dense_grid)
    cb = fit_c_bump_schedule(oos, qt, cell_col=cell_col, taus=dense_grid)

    pits = m5_pit(oos, qt, cb, cell_col=cell_col, dense_grid=dense_grid)
    bw = met.berkowitz_test(pits[np.isfinite(pits)])

    # Headline coverage at the deployed four anchors with the deployed
    # δ-shift schedule.
    served = serve_bands(oos, qt, cb, cell_col=cell_col, taus=DEFAULT_TAUS)
    cov_rows = []
    for tau, band in served.items():
        inside = ((oos["mon_open"] >= band["lower"]) &
                  (oos["mon_open"] <= band["upper"]))
        cov_rows.append({"tau": tau, "realised": float(inside.mean()),
                         "half_width_bps": float(((band["upper"] - band["lower"])
                                                  / 2 / oos["fri_close"] * 1e4).mean())})
    cov_df = pd.DataFrame(cov_rows)

    return {
        "name": name,
        "cell_col": cell_col,
        "n_train": int(len(train)),
        "n_oos": int(len(oos)),
        "n_cells": int(len(qt)),
        "berkowitz_lr": float(bw.get("lr", np.nan)),
        "berkowitz_p": float(bw.get("p_value", np.nan)),
        "berkowitz_n": int(bw.get("n", 0)),
        "rho_hat": float(bw.get("rho_hat", np.nan)),
        "var_z": float(bw.get("var_z", np.nan)),
        "coverage": cov_df,
    }


def main() -> None:
    DENSE_GRID = (
        0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.68, 0.70, 0.80, 0.85,
        0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999,
    )

    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret",
                "vix_fri_close"]
    ).reset_index(drop=True)
    panel["score"] = compute_score(panel)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    print(f"Panel: {len(panel):,} rows × "
          f"{panel['fri_ts'].nunique()} weekends", flush=True)

    print("\n[A] Baseline — 3-cell M5 (regime_pub) …", flush=True)
    base = run_one("baseline_3cell_M5", panel, "regime_pub", DENSE_GRID)
    print(f"     n_oos = {base['n_oos']:,}  "
          f"berkowitz LR = {base['berkowitz_lr']:.2f} "
          f"(p = {base['berkowitz_p']:.2e})  var_z = {base['var_z']:.3f}",
          flush=True)
    print(base["coverage"].to_string(index=False,
                                     float_format=lambda x: f"{x:.4f}"))

    print("\n[B] 5-cell sub-split — normal {calm/mid/heavy} | long_weekend | "
          "high_vol …", flush=True)
    panel_t = assign_vol_tertile(panel, SPLIT_DATE)
    q33, q67 = panel_t.attrs["vix_tertile_anchors"]
    print(f"     normal-regime VIX tertile anchors (train-window): "
          f"q33 = {q33:.2f}  q67 = {q67:.2f}", flush=True)
    sub = run_one("sub_split_5cell", panel_t, "vol_tertile_cell", DENSE_GRID)
    print(f"     n_oos = {sub['n_oos']:,}  "
          f"berkowitz LR = {sub['berkowitz_lr']:.2f} "
          f"(p = {sub['berkowitz_p']:.2e})  var_z = {sub['var_z']:.3f}",
          flush=True)
    print(sub["coverage"].to_string(index=False,
                                    float_format=lambda x: f"{x:.4f}"))

    out_rows = [
        {"variant": v["name"], "cell_col": v["cell_col"],
         "n_cells": v["n_cells"], "n_oos": v["n_oos"],
         "berkowitz_lr": v["berkowitz_lr"], "berkowitz_p": v["berkowitz_p"],
         "rho_hat": v["rho_hat"], "var_z": v["var_z"],
         **{f"realised_{r['tau']:.2f}": r["realised"]
            for _, r in v["coverage"].iterrows()},
         **{f"hw_bps_{r['tau']:.2f}": r["half_width_bps"]
            for _, r in v["coverage"].iterrows()}}
        for v in (base, sub)
    ]
    out = pd.DataFrame(out_rows)
    out_path = REPORTS / "tables" / "v1b_robustness_vol_tertile.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}", flush=True)

    print("\n" + "=" * 80)
    print("DECISION")
    print("=" * 80)
    drop = base["berkowitz_lr"] - sub["berkowitz_lr"]
    if base["berkowitz_lr"] > 0:
        pct = 100.0 * drop / base["berkowitz_lr"]
    else:
        pct = float("nan")
    print(f"Berkowitz LR: 3-cell = {base['berkowitz_lr']:.2f}  →  "
          f"5-cell = {sub['berkowitz_lr']:.2f}  "
          f"(Δ = {drop:.2f}, {pct:.1f}% drop)")
    if drop > 50:
        print("→ Bin-structure story SUPPORTED. CQR can stay deferred (§10.2).")
    elif drop < 20:
        print("→ Bin-structure story REFUTED. CQR is the load-bearing fix.")
    else:
        print("→ Mixed evidence: classifier helps but CQR remains a candidate.")


if __name__ == "__main__":
    main()
