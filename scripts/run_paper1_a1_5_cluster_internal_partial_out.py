"""Paper 1 — Tier A v2 item A1.5.

Cluster-internal partial-out — the follow-up to A1's homogeneous-panel
negative result. A1 found that subtracting a within-weekend median over
all 10 symbols breaks per-symbol Kupiec on GLD/TLT (which are negatively
correlated with the equity-dominated cluster median). The next-level
question: can we partial out within each cluster *separately* and
preserve cluster-level Kupiec?

Cluster definitions:
  equity        = AAPL, GOOGL, HOOD, MSTR, NVDA, QQQ, SPY, TSLA   (8 symbols)
  safe_haven    = GLD, TLT                                         (2 symbols)

For each cluster:
  1. r_i = signed LWC residual = (mon_open_i − point_i) / fri_close_i
  2. m_w_clust(i) = median over j ≠ i in same cluster, same weekend, of r_j
                    (for safe_haven with 2 symbols, this is just the other one)
  3. r_i^{po,clust} = r_i − m_w_clust(i)
  4. Standardised score s_i = |r_i^{po,clust}| / σ̂_sym
  5. Per-regime conformal quantile q_r(τ) on TRAIN within the cluster
  6. c(τ) bump on OOS within the cluster
  7. Evaluate on OOS: cluster-pooled Kupiec, Christoffersen, DQ, per-symbol
     Kupiec, within-cluster ρ̂_cross (signed, lag-1 within weekend sorted
     by symbol within cluster)

Two outcomes are both useful:
  - Equity-only LOO median *preserves* Kupiec while reducing within-cluster
    ρ̂_cross_equity → confirms cluster topology is load-bearing; gives §10
    a concrete architectural target (cluster-conditional conformity heads).
  - Equity-only doesn't preserve Kupiec → residual is even more structural
    than A1 implies; intra-equity heterogeneity (mega-cap vs MSTR vs HOOD)
    isn't absorbable by a homogeneous procedure either.

Output:
  reports/tables/paper1_a1_5_cluster_internal_partial_out.csv
  reports/tables/paper1_a1_5_cluster_internal_partial_out_per_symbol.csv
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
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)

CLUSTERS = {
    "equity":     ("AAPL", "GOOGL", "HOOD", "MSTR", "NVDA", "QQQ", "SPY", "TSLA"),
    "safe_haven": ("GLD", "TLT"),
}


def add_cluster_internal_loo_median(panel: pd.DataFrame,
                                    cluster_symbols: tuple[str, ...]) -> pd.DataFrame:
    """Add `m_w_clust_med` column = LOO median residual within cluster.

    Operates only on rows whose symbol is in `cluster_symbols`. Other rows
    get NaN. Caller is responsible for sub-setting the panel before scoring.
    """
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
        local_pos = list(idx)
        for k, src_lab in enumerate(local_pos):
            others = np.delete(rs, k)
            others = others[np.isfinite(others)]
            if len(others) >= 1:
                m[p.index.get_loc(src_lab)] = float(np.median(others))
    p["m_w_clust_med"] = m
    return p


def lag1_within_weekend(panel: pd.DataFrame, value_col: str) -> float:
    """Pearson lag-1 ρ within weekend, sorted by symbol within weekend."""
    p = panel.dropna(subset=[value_col]).sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    p["v"] = p[value_col].astype(float)
    p["v_lag"] = p.groupby("fri_ts")["v"].shift(1)
    pairs = p.dropna(subset=["v", "v_lag"])
    if len(pairs) < 30:
        return float("nan")
    return float(np.corrcoef(pairs["v"], pairs["v_lag"])[0, 1])


def evaluate_cluster_variant(panel_train: pd.DataFrame,
                             panel_oos: pd.DataFrame,
                             score_col: str,
                             sigma_col: str,
                             tag: str) -> dict:
    """Cluster-pooled Kupiec/Christoffersen/DQ + per-symbol Kupiec at τ=0.95
    on `panel_oos`, with q on TRAIN and c on OOS. The TRAIN/OOS are already
    cluster-restricted by the caller."""
    qt = train_quantile_table(panel_train, cell_col="regime_pub",
                              taus=HEADLINE_TAUS, score_col=score_col)
    cb = fit_c_bump_schedule(panel_oos, qt, cell_col="regime_pub",
                              taus=HEADLINE_TAUS, score_col=score_col)

    cells = panel_oos["regime_pub"].astype(str).to_numpy()
    sigma = panel_oos[sigma_col].astype(float).to_numpy()
    fri = panel_oos["fri_close"].astype(float).to_numpy()
    score = panel_oos[score_col].astype(float).to_numpy()
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
            "variant": tag, "target": tau, "bump_c": float(c),
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
        [qt.get(cells[i], {}).get(tau, np.nan) for i in range(len(panel_oos))],
        dtype=float,
    )
    valid = base_valid & np.isfinite(b_per_row)
    sub = panel_oos[valid].copy()
    sub["score_e"] = score[valid]
    sub["b_eff"] = b_per_row[valid] * c
    sub["viol"] = (sub["score_e"] > sub["b_eff"]).astype(int)
    persym_rows = []
    for sym, g in sub.groupby("symbol"):
        v = g["viol"].to_numpy()
        if len(v) < 5:
            continue
        lr, p = met._lr_kupiec(v, tau)
        persym_rows.append({"variant": tag, "symbol": str(sym),
                             "n": int(len(v)), "viol_rate": float(v.mean()),
                             "kupiec_p": float(p)})

    return {"pooled": pooled_rows, "per_symbol": persym_rows,
            "qt": qt, "cb": cb}


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

    all_pooled = []
    all_persym = []
    rho_rows = []

    for clust_name, clust_syms in CLUSTERS.items():
        print(f"\n=== cluster: {clust_name} (symbols={clust_syms}) ===", flush=True)
        cp = panel[panel["symbol"].isin(clust_syms)].reset_index(drop=True).copy()
        cp = add_cluster_internal_loo_median(cp, clust_syms)

        # Score variants on cluster-restricted panel
        cp["score_baseline_clust"] = cp.apply(
            lambda row: abs(row["r_signed"]) / row[sigma_col]
            if (np.isfinite(row[sigma_col]) and row[sigma_col] > 0) else np.nan,
            axis=1,
        )
        cp["r_po"] = cp["r_signed"] - cp["m_w_clust_med"]
        cp["score_po_clust"] = cp.apply(
            lambda row: abs(row["r_po"]) / row[sigma_col]
            if (np.isfinite(row["r_po"]) and np.isfinite(row[sigma_col]) and row[sigma_col] > 0) else np.nan,
            axis=1,
        )

        # Drop rows where either score is NaN (apples-to-apples)
        m = cp[["score_baseline_clust", "score_po_clust"]].notna().all(axis=1)
        cp_e = cp[m].reset_index(drop=True)

        train = cp_e[cp_e["fri_ts"] <  SPLIT_DATE].reset_index(drop=True)
        oos   = cp_e[cp_e["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
        print(f"  rows after NaN drop: {len(cp_e):,} / {len(cp):,}")
        print(f"  train: {len(train):,} × {train['fri_ts'].nunique()} weekends")
        print(f"  oos:   {len(oos):,} × {oos['fri_ts'].nunique()} weekends")

        # Variants:
        for tag, score_col, signed_col in [
            (f"{clust_name}_baseline",         "score_baseline_clust", "r_signed"),
            (f"{clust_name}_partial_out_med",  "score_po_clust",       "r_po"),
        ]:
            res = evaluate_cluster_variant(train, oos, score_col, sigma_col, tag)
            all_pooled.extend(res["pooled"])
            all_persym.extend(res["per_symbol"])
            n_pass = sum(1 for r in res["per_symbol"] if r["kupiec_p"] >= 0.05)
            n_total = len(res["per_symbol"])
            print(f"  [{tag}] per-symbol Kupiec at τ=0.95: {n_pass}/{n_total} pass")
            print("  pooled by τ:")
            for r in res["pooled"]:
                print(f"    τ={r['target']:.2f}: realised={r['realised']:.3f} "
                      f"c={r['bump_c']:.3f}  Kp={r['kupiec_p']:.3f}  "
                      f"Cp={r['christoffersen_p']:.3f}  "
                      f"DQp={r['dq_p']:.3f}  hw={r['half_width_bps_mean']:.0f}bps")

            # within-cluster rho (signed) on OOS
            rho = lag1_within_weekend(oos, signed_col)
            rho_rows.append({"cluster": clust_name, "variant": tag,
                              "rho_within_cluster_signed": rho,
                              "n_oos_weekends": int(oos["fri_ts"].nunique())})
            print(f"    within-cluster ρ̂(signed lag-1): {rho:.4f}")

    pooled_df = pd.DataFrame(all_pooled)
    persym_df = pd.DataFrame(all_persym)
    rho_df = pd.DataFrame(rho_rows)

    out_pool = REPORTS / "tables" / "paper1_a1_5_cluster_internal_partial_out.csv"
    out_per  = REPORTS / "tables" / "paper1_a1_5_cluster_internal_partial_out_per_symbol.csv"
    out_rho  = REPORTS / "tables" / "paper1_a1_5_cluster_internal_partial_out_rho.csv"
    pooled_df.to_csv(out_pool, index=False)
    persym_df.to_csv(out_per, index=False)
    rho_df.to_csv(out_rho, index=False)
    print(f"\nwrote {out_pool}\nwrote {out_per}\nwrote {out_rho}")

    print("\n=== ρ̂_cross within cluster (signed, lag-1) ===")
    print(rho_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n=== headline τ=0.95 cross-variant ===")
    pivot = pooled_df[pooled_df["target"] == 0.95].set_index("variant")[
        ["n_oos", "realised", "bump_c", "kupiec_p", "christoffersen_p",
         "dq_p", "half_width_bps_mean"]
    ]
    print(pivot.to_string(float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
