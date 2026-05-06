"""Paper 1 — Tier A item A1.

Cross-sectional common-mode partial-out applied to the *deployed M6 LWC*
score (not the legacy M5 baseline). Two non-parametric variants of the
within-weekend common-mode estimator:

  m_w^LOO_med  = median over symbols j ≠ i in weekend w of r_j
  m_w^LOO_mean = mean   over symbols j ≠ i in weekend w of r_j

Partial-out residual: r_i^{po} = r_i − m_w(i, w).
Standardised score:    s_i^{po} = | r_i^{po} | / σ̂_sym(t_i)
                                    where σ̂_sym is the deployed EWMA HL=8 rule.

Per-regime conformal quantile q_r^{po}(τ) on TRAIN (pre-2023);
c(τ) bump on OOS (2023+); evaluation on OOS:
  - Realised coverage at τ ∈ {0.68, 0.85, 0.95, 0.99}
  - Mean half-width (in bps of fri_close)
  - Kupiec, Christoffersen, Berkowitz, Engle-Manganelli DQ
  - Cross-sectional within-weekend lag-1 ρ on the (signed) partial-out residual
  - Per-symbol Kupiec at τ = 0.95

This is a *diagnostic* — m_w uses Monday data and is not Friday-observable.
The question is whether removing the realised common-mode materially closes
the §9.4 / §6.3.6 disclosure (Berkowitz LR, DQ, ρ̂_cross). If yes → invest
in a forward predictor. If no → ship the negative result.

Output:
  reports/tables/paper1_a1_common_mode_partial_out_m6.csv
  reports/tables/paper1_a1_common_mode_partial_out_m6_per_symbol.csv
  reports/active/paper1_methodology_revisions.md  (A1 result section appended)
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import norm

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    add_sigma_hat_sym_ewma,
    SIGMA_HAT_HL_WEEKENDS,
    train_quantile_table,
    fit_c_bump_schedule,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
PIT_DENSE_GRID = (
    0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.68, 0.70, 0.80, 0.85,
    0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999,
)


# ---------------------------------------------------------------- partial-out

def add_loo_common_mode(panel: pd.DataFrame) -> pd.DataFrame:
    """Add per-row leave-one-out within-weekend median + mean residual.

    r_i = (mon_open_i - fri_close_i · (1 + factor_ret_i)) / fri_close_i
    m_w_loo_med[i]  = median over j ≠ i in weekend w of r_j
    m_w_loo_mean[i] = mean   over j ≠ i in weekend w of r_j
    """
    p = panel.copy()
    p["r_signed"] = (
        (p["mon_open"].astype(float)
         - p["fri_close"].astype(float) * (1.0 + p["factor_ret"].astype(float)))
        / p["fri_close"].astype(float)
    )
    # LOO mean is closed-form
    g = p.groupby("fri_ts")["r_signed"]
    sum_w = g.transform("sum")
    cnt_w = g.transform("count")
    p["m_w_loo_mean"] = (sum_w - p["r_signed"]) / (cnt_w - 1).replace(0, np.nan)

    # LOO median requires per-row recompute
    loo_med = np.full(len(p), np.nan)
    for w, idx in p.groupby("fri_ts").groups.items():
        sub = p.loc[idx, "r_signed"].to_numpy()
        for k, src in enumerate(idx):
            others = np.delete(sub, k)
            others = others[np.isfinite(others)]
            if len(others) >= 1:
                loo_med[p.index.get_loc(src)] = float(np.median(others))
    p["m_w_loo_med"] = loo_med
    return p


# ----------------------------------------------------------- score variants

def _score_variant(panel: pd.DataFrame, common_mode_col: str | None,
                   sigma_col: str) -> pd.Series:
    """Standardised LWC conformity score under a chosen partial-out.

    common_mode_col=None     → baseline (no partial-out): s = |r| / σ̂
    common_mode_col=col_name → partial-out: s = |r − m_w| / σ̂
    """
    r = panel["r_signed"].astype(float)
    if common_mode_col is not None:
        r = r - panel[common_mode_col].astype(float)
    sigma = panel[sigma_col].astype(float)
    out = r.abs() / sigma
    out[~(sigma > 0)] = np.nan
    return out


# -------------------------------------------------------------- pit builder

def _interp_table(table: dict, x: float) -> float:
    keys = sorted(float(k) for k in table.keys())
    if x <= keys[0]:
        return float(table[keys[0]])
    if x >= keys[-1]:
        return float(table[keys[-1]])
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= x <= hi:
            frac = (x - lo) / (hi - lo)
            return float(table[lo] + frac * (table[hi] - table[lo]))
    return float(table[keys[-1]])


def build_pits_lwc_po(panel: pd.DataFrame,
                      qt_dense: dict[str, dict[float, float]],
                      cb_dense: dict[float, float],
                      common_mode_col: str | None,
                      sigma_col: str,
                      grid: tuple[float, ...] = PIT_DENSE_GRID) -> np.ndarray:
    """Per-row PITs at the served-band CDF, partial-out aware.

    For row i with regime r, σ̂_i, and signed residual r_i^{po}:
      half_i(τ) = q_r(τ) · c(τ) · σ̂_i · fri_close_i
      tau_hat   = piecewise-linear inverse of half_i in |r_i^{po}|
      pit       = 0.5 + 0.5 · sign(r_i^{po}) · tau_hat
    """
    grid_taus = np.array(sorted(grid))
    fri_close = panel["fri_close"].astype(float).to_numpy()
    sigma = panel[sigma_col].astype(float).to_numpy()
    cells = panel["regime_pub"].astype(str).to_numpy()
    r_signed = panel["r_signed"].astype(float).to_numpy()
    if common_mode_col is None:
        r_po = r_signed.copy()
    else:
        m = panel[common_mode_col].astype(float).to_numpy()
        r_po = r_signed - m

    pits = np.full(len(panel), np.nan)
    for i in range(len(panel)):
        q_row = qt_dense.get(cells[i])
        if q_row is None:
            continue
        s = sigma[i]
        if not (np.isfinite(s) and s > 0):
            continue
        scale = fri_close[i] * s
        if not (np.isfinite(scale) and scale > 0):
            continue
        b_anchors = np.array(
            [_interp_table(q_row, tau) * _interp_table(cb_dense, tau)
             for tau in grid_taus],
            dtype=float,
        )
        if not np.all(np.isfinite(b_anchors)):
            continue
        half_i = b_anchors * scale
        r = r_po[i]
        if not np.isfinite(r):
            continue
        abs_r = abs(r)
        anchor_b = np.concatenate(([0.0], half_i))
        anchor_tau = np.concatenate(([0.0], grid_taus))
        if abs_r >= anchor_b[-1]:
            tau_hat = anchor_tau[-1]
        else:
            tau_hat = float(np.interp(abs_r, anchor_b, anchor_tau))
        pits[i] = 0.5 + 0.5 * tau_hat * (1 if r >= 0 else -1)
    return pits


# ------------------------------------------------------------- diagnostics

def lag1_within_weekend_signed(panel_oos: pd.DataFrame,
                               common_mode_col: str | None) -> float:
    """Pearson lag-1 ρ on the signed residual within weekend, sorted by symbol.

    Captures the cross-sectional ρ̂_cross statistic from §6.3.6.
    """
    p = panel_oos.copy().sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    if common_mode_col is None:
        v = p["r_signed"].astype(float).to_numpy()
    else:
        v = (p["r_signed"].astype(float)
             - p[common_mode_col].astype(float)).to_numpy()
    p["v"] = v
    p["v_lag"] = p.groupby("fri_ts")["v"].shift(1)
    pairs = p.dropna(subset=["v", "v_lag"])
    if len(pairs) < 30:
        return float("nan")
    return float(np.corrcoef(pairs["v"], pairs["v_lag"])[0, 1])


def evaluate_variant(panel_train: pd.DataFrame,
                     panel_oos: pd.DataFrame,
                     score_col: str,
                     common_mode_col: str | None,
                     sigma_col: str) -> dict:
    """One row of results for a given partial-out variant."""

    # Per-regime conformal quantile on TRAIN at dense grid (for PIT inversion)
    # plus headline grid (for c(τ) bump fit).
    dense = tuple(sorted(set(PIT_DENSE_GRID) | set(HEADLINE_TAUS)))
    qt_dense = train_quantile_table(panel_train, cell_col="regime_pub",
                                    taus=dense, score_col=score_col)
    qt_head = {c: {t: qt_dense[c][t] for t in HEADLINE_TAUS}
               for c in qt_dense}
    cb_head = fit_c_bump_schedule(panel_oos, qt_head,
                                  cell_col="regime_pub",
                                  taus=HEADLINE_TAUS, score_col=score_col)
    # cb on dense grid (interpolated from headline anchors)
    cb_dense = {tau: _interp_table(cb_head, tau) for tau in dense}

    # Pooled coverage / Kupiec / Christoffersen / DQ at each headline tau
    rows_pool = []
    cells_oos = panel_oos["regime_pub"].astype(str).to_numpy()
    sigma_oos = panel_oos[sigma_col].astype(float).to_numpy()
    fri_oos = panel_oos["fri_close"].astype(float).to_numpy()
    score_oos = panel_oos[score_col].astype(float).to_numpy()
    finite_mask = np.isfinite(score_oos) & np.isfinite(sigma_oos) & (sigma_oos > 0)

    for tau in HEADLINE_TAUS:
        c = cb_head[tau]
        b_per_row = np.array(
            [qt_head.get(cells_oos[i], {}).get(tau, np.nan)
             for i in range(len(panel_oos))],
            dtype=float,
        )
        valid = finite_mask & np.isfinite(b_per_row)
        s = score_oos[valid]
        b_eff = b_per_row[valid] * c
        inside = (s <= b_eff).astype(int)
        violations = (1 - inside).astype(int)

        lr_uc, p_uc = met._lr_kupiec(violations, tau)
        lr_ind, p_ind = met._lr_christoffersen_independence(violations)
        dq = met.dynamic_quantile_test(violations, claimed=tau, n_lags=4)

        # Half-width in bps of fri_close: q_eff · σ̂ · fri_close → bps
        sigma_v = sigma_oos[valid]
        fri_v = fri_oos[valid]
        hw_bps = (b_eff * sigma_v * fri_v) / fri_v * 1e4
        rows_pool.append({
            "target": tau, "bump_c": float(c),
            "n_oos": int(valid.sum()),
            "realised": float(inside.mean()),
            "kupiec_lr": float(lr_uc), "kupiec_p": float(p_uc),
            "christoffersen_lr": float(lr_ind),
            "christoffersen_p": float(p_ind),
            "dq_stat": float(dq.get("dq", np.nan)),
            "dq_p": float(dq.get("p_value", np.nan)),
            "half_width_bps_mean": float(hw_bps.mean()),
            "half_width_bps_median": float(np.median(hw_bps)),
        })

    # Berkowitz on PITs at dense grid (full distribution)
    pits = build_pits_lwc_po(panel_oos, qt_dense, cb_dense, common_mode_col,
                             sigma_col)
    pits_clean = pits[(np.isfinite(pits)) & (pits > 0) & (pits < 1)]
    bw = met.berkowitz_test(pits_clean) if len(pits_clean) >= 30 else {
        "lr": np.nan, "p_value": np.nan, "n": int(len(pits_clean)),
        "rho_hat": np.nan, "var_z": np.nan,
    }
    rho_cross = lag1_within_weekend_signed(panel_oos, common_mode_col)

    return {
        "pooled_by_tau": pd.DataFrame(rows_pool),
        "berkowitz_lr": float(bw.get("lr", np.nan)),
        "berkowitz_p": float(bw.get("p_value", np.nan)),
        "berkowitz_n": int(bw.get("n", len(pits_clean))),
        "berkowitz_rho_z": float(bw.get("rho_hat", np.nan)),
        "berkowitz_var_z": float(bw.get("var_z", np.nan)),
        "rho_cross_signed": float(rho_cross),
        "qt_head": qt_head, "cb_head": cb_head,
        "score_col": score_col,
    }


def per_symbol_kupiec_at_tau(panel_oos: pd.DataFrame,
                             qt_head: dict, cb_head: dict,
                             score_col: str, tau: float = 0.95) -> pd.DataFrame:
    cells = panel_oos["regime_pub"].astype(str).to_numpy()
    score = panel_oos[score_col].astype(float).to_numpy()
    c = cb_head[tau]
    b_per_row = np.array(
        [qt_head.get(cells[i], {}).get(tau, np.nan)
         for i in range(len(panel_oos))],
        dtype=float,
    )
    valid = np.isfinite(score) & np.isfinite(b_per_row)
    sub = panel_oos[valid].copy()
    sub["score"] = score[valid]
    sub["b"] = b_per_row[valid]
    sub["viol"] = (sub["score"] > sub["b"] * c).astype(int)
    rows = []
    for sym, g in sub.groupby("symbol"):
        v = g["viol"].to_numpy()
        if len(v) < 5:
            continue
        lr_uc, p_uc = met._lr_kupiec(v, tau)
        rows.append({"symbol": str(sym), "n": int(len(v)),
                     "viol_rate": float(v.mean()),
                     "kupiec_lr": float(lr_uc),
                     "kupiec_p": float(p_uc)})
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


# ----------------------------------------------------------------- driver

def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    # Deployed σ̂: EWMA HL=8 (matches lwc_artefact_v1.json)
    panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HAT_HL_WEEKENDS)
    sigma_col = f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HAT_HL_WEEKENDS}"
    panel["sigma_hat_sym_pre_fri"] = panel[sigma_col]

    # Add LOO common-mode columns
    panel = add_loo_common_mode(panel)

    # Score variants
    panel["score_baseline"] = _score_variant(panel, None, sigma_col)
    panel["score_po_med"]   = _score_variant(panel, "m_w_loo_med", sigma_col)
    panel["score_po_mean"]  = _score_variant(panel, "m_w_loo_mean", sigma_col)

    # Drop rows where any of the three scores is NaN so all variants
    # evaluate on the same row set (apples-to-apples).
    eval_mask = (panel[["score_baseline", "score_po_med", "score_po_mean"]]
                 .notna().all(axis=1))
    panel_e = panel[eval_mask].reset_index(drop=True)
    print(f"eval rows after dropping NaN scores across all variants: "
          f"{len(panel_e):,} / {len(panel):,}", flush=True)

    panel_train = panel_e[panel_e["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel_e[panel_e["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"  train: {len(panel_train):,} rows × {panel_train['fri_ts'].nunique()} weekends",
          flush=True)
    print(f"  oos:   {len(panel_oos):,} rows × {panel_oos['fri_ts'].nunique()} weekends",
          flush=True)

    variants = [
        ("baseline_no_po",              "score_baseline", None),
        ("partial_out_loo_median",      "score_po_med",   "m_w_loo_med"),
        ("partial_out_loo_mean",        "score_po_mean",  "m_w_loo_mean"),
    ]

    pooled_rows = []
    summary_rows = []
    persym_frames = []
    for name, score_col, common_col in variants:
        print(f"\n[{name}] fit + evaluate…", flush=True)
        res = evaluate_variant(panel_train, panel_oos, score_col,
                               common_col, sigma_col)
        for r in res["pooled_by_tau"].to_dict("records"):
            pooled_rows.append({"variant": name, **r})
        summary_rows.append({
            "variant": name,
            "berkowitz_lr": res["berkowitz_lr"],
            "berkowitz_p":  res["berkowitz_p"],
            "berkowitz_n":  res["berkowitz_n"],
            "berkowitz_rho_z": res["berkowitz_rho_z"],
            "berkowitz_var_z": res["berkowitz_var_z"],
            "rho_cross_signed": res["rho_cross_signed"],
        })
        persym = per_symbol_kupiec_at_tau(panel_oos, res["qt_head"],
                                          res["cb_head"], score_col, 0.95)
        persym["variant"] = name
        persym_frames.append(persym)

        print(f"  rho_cross(signed): {res['rho_cross_signed']:.4f}")
        print(f"  Berkowitz LR: {res['berkowitz_lr']:.2f}  "
              f"p={res['berkowitz_p']:.4f}  (n={res['berkowitz_n']})")
        print(res["pooled_by_tau"][[
            "target", "realised", "bump_c", "kupiec_p", "christoffersen_p",
            "dq_p", "half_width_bps_mean",
        ]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # Tables
    pooled_df = pd.DataFrame(pooled_rows)
    summary_df = pd.DataFrame(summary_rows)
    persym_df = pd.concat(persym_frames, ignore_index=True)

    out_pooled = REPORTS / "tables" / "paper1_a1_common_mode_partial_out_m6.csv"
    out_summary = REPORTS / "tables" / "paper1_a1_common_mode_partial_out_m6_summary.csv"
    out_persym  = REPORTS / "tables" / "paper1_a1_common_mode_partial_out_m6_per_symbol.csv"
    pooled_df.to_csv(out_pooled, index=False)
    summary_df.to_csv(out_summary, index=False)
    persym_df.to_csv(out_persym, index=False)
    print(f"\nwrote {out_pooled}")
    print(f"wrote {out_summary}")
    print(f"wrote {out_persym}")

    # Quick paired-comparison table at τ=0.95
    print("\n=== headline τ=0.95 cross-variant comparison ===")
    pivot = pooled_df[pooled_df["target"] == 0.95].set_index("variant")[
        ["realised", "bump_c", "kupiec_p", "christoffersen_p", "dq_p",
         "half_width_bps_mean"]
    ]
    print(pivot.to_string(float_format=lambda x: f"{x:.3f}"))

    print("\n=== Berkowitz / ρ̂_cross summary ===")
    print(summary_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
