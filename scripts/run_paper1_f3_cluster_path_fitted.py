"""Paper 1 — Tier D item F3.

A1.5 cluster-internal partial-out with the path-fitted conformity score
from B6 — does max-over-path scoring close the DQ rejection at τ ∈
{0.68, 0.85} that A1.5's endpoint-scored partial-out exhibited?

Hypothesis (from F3 spec):
  A1.5's DQ rejection at lower τ is the violation-reordering artifact
  documented in A1: under endpoint scoring, partial-out shifts violations
  onto the few rows whose residual disagrees with the cluster median,
  creating fresh autocorrelation under panel-row ordering. Path-fitted
  scoring (max over the closed-market window) doesn't toggle on/off near
  the band edge — the path-supremum usually exceeds endpoint magnitudes
  enough that the per-row "breach vs no-breach" decision is *less*
  sensitive to a small shift in band centre. So path-fitted partial-out
  should reduce the violation reordering and improve DQ.

Structure:
  point     = fri_close · (1 + factor_ret)             (pre-partial-out centre)
  m_w      = within-equity-cluster LOO median of (mon_open − point) / fri_close
  point_po = fri_close · (1 + factor_ret) + m_w · fri_close   (shifted band centre)

Score variants on the CME-projected equity-cluster subset:
  (1) baseline_endpoint      — A1.5 baseline equity-cluster
                                  s = |mon_open − point| / (fri_close · σ̂)
  (2) partial_out_endpoint   — A1.5 partial-out equity-cluster
                                  s = |mon_open − point − m_w · fri_close| /
                                      (fri_close · σ̂)
  (3) baseline_path           — B6 path-fitted, no partial-out
                                  s = max(point − path_lo, path_hi − point,
                                            |mon_open − point|) / (fri_close · σ̂)
  (4) partial_out_path       — F3 NEW: path-fitted + cluster partial-out
                                  s = max(point_po − path_lo, path_hi − point_po,
                                            |mon_open − point_po|) /
                                      (fri_close · σ̂)

For each variant report at τ ∈ {0.68, 0.85, 0.95, 0.99}:
  pooled realised, Kupiec p, Christoffersen p, **DQ p**, half-width,
  per-symbol Kupiec count at τ=0.95.

Output:
  reports/tables/paper1_f3_cluster_path_fitted.csv
  reports/tables/paper1_f3_cluster_path_fitted_per_symbol.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    SIGMA_HAT_HL_WEEKENDS,
    add_sigma_hat_sym_ewma,
    train_quantile_table,
    fit_c_bump_schedule,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

import sys
sys.path.insert(0, str((REPORTS.parent / "scripts").resolve()))
from run_v1b_path_fitted_conformal import (  # type: ignore
    compute_path_panel,
)

SPLIT_DATE = date(2023, 1, 1)
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
EQUITY_CLUSTER = ("AAPL", "GOOGL", "HOOD", "MSTR", "NVDA", "QQQ", "SPY", "TSLA")


def add_loo_cluster_median(panel: pd.DataFrame,
                           cluster_symbols: tuple[str, ...]) -> pd.DataFrame:
    p = panel.copy()
    in_clust = p["symbol"].isin(cluster_symbols)
    p["r_signed"] = (
        (p["mon_open"].astype(float)
         - p["fri_close"].astype(float) * (1.0 + p["factor_ret"].astype(float)))
        / p["fri_close"].astype(float)
    )
    m = np.full(len(p), np.nan)
    sub = p[in_clust].copy()
    for w, idx in sub.groupby("fri_ts").groups.items():
        rs = sub.loc[idx, "r_signed"].to_numpy()
        for k, src_lab in enumerate(idx):
            others = np.delete(rs, k)
            others = others[np.isfinite(others)]
            if len(others) >= 1:
                m[p.index.get_loc(src_lab)] = float(np.median(others))
    p["m_w_clust_med"] = m
    return p


def score_path_with_partial_out(panel: pd.DataFrame, sigma_col: str,
                                use_partial_out: bool) -> np.ndarray:
    """Path-fitted score with optional cluster-median partial-out applied
    to the band centre (point)."""
    fri_close = panel["fri_close"].astype(float).to_numpy()
    point0 = (panel["fri_close"].astype(float)
              * (1.0 + panel["factor_ret"].astype(float))).to_numpy()
    if use_partial_out:
        m = panel["m_w_clust_med"].astype(float).to_numpy()
        point = point0 + m * fri_close
    else:
        point = point0
    mon_open = panel["mon_open"].astype(float).to_numpy()
    path_lo = panel["path_lo"].astype(float).to_numpy()
    path_hi = panel["path_hi"].astype(float).to_numpy()
    sigma = panel[sigma_col].astype(float).to_numpy()
    breach_lo = np.maximum(0.0, point - path_lo)
    breach_hi = np.maximum(0.0, path_hi - point)
    breach_end = np.abs(mon_open - point)
    abs_path = np.maximum.reduce([breach_lo, breach_hi, breach_end])
    out = abs_path / (fri_close * sigma)
    bad = (~np.isfinite(sigma)) | (sigma <= 0) | (~np.isfinite(path_lo)) | (~np.isfinite(path_hi))
    out[bad] = np.nan
    return out


def score_endpoint_with_partial_out(panel: pd.DataFrame, sigma_col: str,
                                    use_partial_out: bool) -> np.ndarray:
    fri_close = panel["fri_close"].astype(float).to_numpy()
    point0 = (panel["fri_close"].astype(float)
              * (1.0 + panel["factor_ret"].astype(float))).to_numpy()
    if use_partial_out:
        m = panel["m_w_clust_med"].astype(float).to_numpy()
        point = point0 + m * fri_close
    else:
        point = point0
    mon_open = panel["mon_open"].astype(float).to_numpy()
    sigma = panel[sigma_col].astype(float).to_numpy()
    out = np.abs(mon_open - point) / (fri_close * sigma)
    bad = (~np.isfinite(sigma)) | (sigma <= 0)
    out[bad] = np.nan
    return out


def evaluate_variant(panel_train: pd.DataFrame, panel_oos: pd.DataFrame,
                     score_col: str, sigma_col: str,
                     variant_tag: str) -> dict:
    qt = train_quantile_table(panel_train, cell_col="regime_pub",
                               taus=HEADLINE_TAUS, score_col=score_col)
    cb = fit_c_bump_schedule(panel_oos, qt, cell_col="regime_pub",
                              taus=HEADLINE_TAUS, score_col=score_col)
    cells = panel_oos["regime_pub"].astype(str).to_numpy()
    score = panel_oos[score_col].astype(float).to_numpy()
    sigma = panel_oos[sigma_col].astype(float).to_numpy()
    base_valid = np.isfinite(score) & np.isfinite(sigma) & (sigma > 0)
    pooled_rows = []
    for tau in HEADLINE_TAUS:
        c = cb[tau]
        b_per_row = np.array(
            [qt.get(cells[i], {}).get(tau, np.nan)
             for i in range(len(panel_oos))],
            dtype=float,
        )
        valid = base_valid & np.isfinite(b_per_row)
        s = score[valid]
        b_eff = b_per_row[valid] * c
        inside = (s <= b_eff).astype(int)
        viol = (1 - inside).astype(int)
        lr_uc, p_uc = met._lr_kupiec(viol, tau)
        lr_ind, p_ind = met._lr_christoffersen_independence(viol)
        dq = met.dynamic_quantile_test(viol, claimed=tau, n_lags=4)
        sigma_v = sigma[valid]
        hw_bps = b_eff * sigma_v * 1e4
        pooled_rows.append({
            "variant": variant_tag, "target": tau, "bump_c": float(c),
            "n_oos": int(valid.sum()),
            "realised": float(inside.mean()),
            "kupiec_p": float(p_uc),
            "christoffersen_p": float(p_ind),
            "dq_p": float(dq.get("p_value", np.nan)),
            "half_width_bps_mean": float(hw_bps.mean()),
        })

    # Per-symbol Kupiec at τ=0.95
    tau = 0.95
    c = cb[tau]
    b_per_row = np.array(
        [qt.get(cells[i], {}).get(tau, np.nan)
         for i in range(len(panel_oos))],
        dtype=float,
    )
    valid = base_valid & np.isfinite(b_per_row)
    sub = panel_oos[valid].copy()
    sub["score"] = score[valid]
    sub["b_eff"] = b_per_row[valid] * c
    sub["viol"] = (sub["score"] > sub["b_eff"]).astype(int)
    persym = []
    for sym, g in sub.groupby("symbol"):
        v = g["viol"].to_numpy()
        if len(v) < 5:
            continue
        lr, p = met._lr_kupiec(v, tau)
        persym.append({"variant": variant_tag, "symbol": str(sym),
                        "n": int(len(v)), "viol_rate": float(v.mean()),
                        "kupiec_p": float(p)})
    return {"pooled": pooled_rows, "per_symbol": persym}


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HAT_HL_WEEKENDS)
    panel["sigma_hat_sym_pre_fri"] = panel[
        f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HAT_HL_WEEKENDS}"
    ]
    sigma_col = "sigma_hat_sym_pre_fri"

    print("Loading CME path data via run_v1b_path_fitted_conformal pipeline …",
          flush=True)
    pp = compute_path_panel(panel)
    pp["fri_ts"] = pd.to_datetime(pp["fri_ts"]).dt.date
    print(f"path-data rows: {len(pp):,}", flush=True)

    # Merge σ̂ into pp
    sigma_lookup = panel[["symbol", "fri_ts", "sigma_hat_sym_pre_fri"]].drop_duplicates(
        subset=["symbol", "fri_ts"]
    )
    pp = pp.merge(sigma_lookup, on=["symbol", "fri_ts"], how="left")
    pp = pp.dropna(subset=["sigma_hat_sym_pre_fri"]).reset_index(drop=True)

    # Restrict to equity cluster
    cp = pp[pp["symbol"].isin(EQUITY_CLUSTER)].reset_index(drop=True).copy()
    print(f"equity cluster + path data: {len(cp):,} rows × "
          f"{cp['symbol'].nunique()} symbols × {cp['fri_ts'].nunique()} weekends",
          flush=True)

    # Compute LOO equity-cluster median of signed relative residual
    cp = add_loo_cluster_median(cp, EQUITY_CLUSTER)

    # Compute four score variants
    cp["score_baseline_endpoint"]    = score_endpoint_with_partial_out(cp, sigma_col, False)
    cp["score_partial_out_endpoint"] = score_endpoint_with_partial_out(cp, sigma_col, True)
    cp["score_baseline_path"]        = score_path_with_partial_out(cp, sigma_col, False)
    cp["score_partial_out_path"]     = score_path_with_partial_out(cp, sigma_col, True)

    # Drop rows with NaN in any score (apples-to-apples)
    score_cols = ["score_baseline_endpoint", "score_partial_out_endpoint",
                  "score_baseline_path", "score_partial_out_path"]
    m = cp[score_cols].notna().all(axis=1)
    cp_e = cp[m].reset_index(drop=True)

    train = cp_e[cp_e["fri_ts"] <  SPLIT_DATE].reset_index(drop=True)
    # Match A1.5's panel ordering for DQ comparison: A1.5 used the default
    # post-merge order (≈ symbol, fri_ts grouped). DQ on (symbol, fri_ts)
    # tests temporal-within-symbol autocorrelation — the artifact A1
    # diagnosed. (fri_ts, symbol) ordering would test cross-sectional
    # within-weekend autocorrelation = the ρ̂_cross signal directly.
    oos   = (cp_e[cp_e["fri_ts"] >= SPLIT_DATE]
             .sort_values(["symbol", "fri_ts"])
             .reset_index(drop=True))
    print(f"  after dropna: {len(cp_e):,} rows; train={len(train):,}, oos={len(oos):,}",
          flush=True)

    pooled_all = []
    persym_all = []
    for tag, score_col in [
        ("baseline_endpoint",     "score_baseline_endpoint"),
        ("partial_out_endpoint",  "score_partial_out_endpoint"),
        ("baseline_path",         "score_baseline_path"),
        ("partial_out_path",      "score_partial_out_path"),
    ]:
        print(f"\n=== {tag} ===", flush=True)
        res = evaluate_variant(train, oos, score_col, sigma_col, tag)
        pooled_all.extend(res["pooled"])
        persym_all.extend(res["per_symbol"])
        for r in res["pooled"]:
            print(f"  τ={r['target']:.2f}: realised={r['realised']:.4f}  "
                  f"c={r['bump_c']:.3f}  Kp={r['kupiec_p']:.3f}  "
                  f"Cp={r['christoffersen_p']:.3f}  "
                  f"DQp={r['dq_p']:.3f}  hw={r['half_width_bps_mean']:.0f}bps")
        n_pass = sum(1 for r in res["per_symbol"] if r["kupiec_p"] >= 0.05)
        print(f"  per-symbol Kupiec at τ=0.95: {n_pass}/{len(res['per_symbol'])} pass")

    pd.DataFrame(pooled_all).to_csv(
        REPORTS / "tables" / "paper1_f3_cluster_path_fitted.csv", index=False
    )
    pd.DataFrame(persym_all).to_csv(
        REPORTS / "tables" / "paper1_f3_cluster_path_fitted_per_symbol.csv", index=False
    )
    print(f"\nwrote reports/tables/paper1_f3_cluster_path_fitted{{,_per_symbol}}.csv")

    print("\n=== DQ p-value at lower τ across variants ===")
    df = pd.DataFrame(pooled_all)
    pivot = df[df["target"].isin([0.68, 0.85])].pivot_table(
        index="variant", columns="target", values="dq_p"
    )
    print(pivot.to_string(float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
