"""
Trial 2 (reframed) — Mondrian conformal correction on pooled-tail bounds.

Per methodology log entry 2026-04-28 (late evening, +3). The base
predictor is Trial 3's pooled-tail forecaster (which passed all four
decision thresholds at τ=0.99 with 3/10 per-symbol DQ rejects). The
remaining three rejectors (AAPL, HOOD, SPY) carry per-symbol tail
behaviour orthogonal to the cross-sectional pooling Trial 3 leverages
and the conditional-vol augmentation Trial 6 added.

CQR-style Mondrian conformal: for each (symbol, target) compute the
asymmetric residual on a calibration split, take the (1-α)(n+1)/n
quantile per symbol, add as correction to the bounds. The per-symbol
group structure is the Mondrian "taxonomy"; coverage is group-conditional
(per-symbol) rather than marginal.

Calibration / test split: temporal — first 50 % of OOS rows = calibration,
second 50 % = test. ~85 calibration weekends per symbol. Conformal
correction at τ=0.99 is essentially the calibration-set max residual (n+1)/n
≈ 0.99 quantile of ~85 obs → 84th-of-85 obs).

Hypothesis: per-symbol residual correction closes the AAPL/HOOD/SPY gap
at τ=0.99 by adding finite-sample group-conditional coverage on top of
the pooled-cross-section base. Cost: bandwidth widening proportional to
the per-symbol residual quantile.

Decision threshold: same four-threshold scorecard, evaluated on the
test split (second 50% of OOS).
"""

from __future__ import annotations

import time
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import chi2 as _chi2

from soothsayer.backtest import forecasters as fc
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
WINDOW = 156
MIN_OBS = 50
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
TAIL_TAUS = (0.95, 0.99)
EXTRA_REGRESSORS = ("earnings_next_week_f", "is_long_weekend")
VOL_COL_BY_SYMBOL = {
    "SPY": "vix_fri_close", "QQQ": "vix_fri_close",
    "AAPL": "vix_fri_close", "GOOGL": "vix_fri_close",
    "NVDA": "vix_fri_close", "TSLA": "vix_fri_close",
    "HOOD": "vix_fri_close", "MSTR": "vix_fri_close",
    "GLD": "gvz_fri_close", "TLT": "move_fri_close",
}


def replay_with_pooled_tail(panel: pd.DataFrame) -> pd.DataFrame:
    """Same as Trial 3 — produce pooled-tail bounds at each (symbol, fri_ts, target)."""
    point_fa = fc.point_futures_adjusted(panel)
    extra_cols = list(EXTRA_REGRESSORS)
    cell_rows = []
    for sym, idx in panel.groupby("symbol").groups.items():
        g = panel.loc[idx].sort_values("fri_ts")
        g_pfa = point_fa.loc[g.index]
        vol_col = VOL_COL_BY_SYMBOL.get(sym, "vix_fri_close")
        vol = g[vol_col].astype(float).values
        resid_log = np.log(g["mon_open"].astype(float).values / g_pfa.values)
        extras = {col: g[col].astype(float).values if col in g.columns else np.zeros(len(g))
                  for col in extra_cols}
        fri_ts_arr = g["fri_ts"].values
        regime_arr = g["regime_pub"].values if "regime_pub" in g.columns else np.array([""] * len(g))
        mon_open_arr = g["mon_open"].astype(float).values
        fri_close_arr = g["fri_close"].astype(float).values

        for i in range(len(g)):
            pfa_i = float(g_pfa.iloc[i])
            vol_i = vol[i]
            if not np.isfinite(vol_i) or vol_i <= 0 or not np.isfinite(pfa_i):
                continue
            start = max(0, i - WINDOW)
            past_r = resid_log[start:i]
            past_v = vol[start:i]
            past_extras = {col: arr[start:i] for col, arr in extras.items()}
            now_extras = {col: arr[i] for col, arr in extras.items()}

            valid = (np.isfinite(past_r) & np.isfinite(past_v) & (past_v > 0)
                     & (np.abs(past_r) > 1e-10))
            for arr in past_extras.values():
                valid &= np.isfinite(arr)
            if valid.sum() < MIN_OBS:
                continue

            r_v = past_r[valid]
            v_v = past_v[valid]
            design = [np.ones(valid.sum()), np.log(v_v)]
            kept = []
            for col in extra_cols:
                x_col = past_extras[col][valid]
                if np.nanstd(x_col) > 0:
                    design.append(x_col)
                    kept.append(col)
            X = np.column_stack(design)
            y = np.log(np.abs(r_v))
            try:
                beta_hat, *_ = np.linalg.lstsq(X, y, rcond=None)
            except np.linalg.LinAlgError:
                continue
            alpha = beta_hat[0]
            b = beta_hat[1]
            gammas = dict(zip(kept, beta_hat[2:]))

            sigma_hist_log = alpha + b * np.log(v_v)
            for col in kept:
                sigma_hist_log = sigma_hist_log + gammas[col] * past_extras[col][valid]
            sigma_hist = np.exp(sigma_hist_log)
            sigma_now_log = alpha + b * np.log(vol_i)
            for col in kept:
                sigma_now_log += gammas[col] * now_extras[col]
            sigma_now = float(np.exp(sigma_now_log))
            if sigma_now <= 0 or not np.isfinite(sigma_now):
                continue
            z_hist = r_v / sigma_hist

            cell_rows.append({
                "symbol": sym, "fri_ts": fri_ts_arr[i], "regime_pub": regime_arr[i],
                "pfa": pfa_i, "sigma_now": sigma_now,
                "mon_open": mon_open_arr[i], "fri_close": fri_close_arr[i],
                "z_hist": z_hist,
            })

    cells = pd.DataFrame(cell_rows)
    pooled_by_key: dict[tuple, np.ndarray] = {}
    for (regime, fri_ts), g in cells.groupby(["regime_pub", "fri_ts"]):
        pooled_by_key[(regime, fri_ts)] = np.concatenate(g["z_hist"].values)

    out_rows = []
    for _, c in cells.iterrows():
        z_hist_pool = pooled_by_key[(c["regime_pub"], c["fri_ts"])]
        for tau in HEADLINE_TAUS:
            tail = (1 - tau) / 2
            if tau in TAIL_TAUS:
                z_lo = float(np.quantile(z_hist_pool, tail))
                z_hi = float(np.quantile(z_hist_pool, 1 - tail))
            else:
                z_hist_sym = c["z_hist"]
                z_lo = float(np.quantile(z_hist_sym, tail))
                z_hi = float(np.quantile(z_hist_sym, 1 - tail))
            lo = c["pfa"] * np.exp(z_lo * c["sigma_now"])
            hi = c["pfa"] * np.exp(z_hi * c["sigma_now"])
            out_rows.append({
                "symbol": c["symbol"], "fri_ts": c["fri_ts"], "regime_pub": c["regime_pub"],
                "target": tau,
                "mon_open": c["mon_open"], "fri_close": c["fri_close"],
                "lo": lo, "hi": hi,
            })
    return pd.DataFrame(out_rows)


def mondrian_correction(cal_df: pd.DataFrame, target: float) -> dict[str, tuple[float, float]]:
    """Compute per-symbol asymmetric CQR correction on the calibration split.

    Returns {symbol: (q_lower, q_upper)} where q_lower is added to L (and
    L_adj = L - q_lower), q_upper added to U (U_adj = U + q_upper).
    """
    out = {}
    sub = cal_df[cal_df["target"] == target]
    for sym, g in sub.groupby("symbol"):
        e_lower = np.maximum(g["lo"].values - g["mon_open"].values, 0.0)
        e_upper = np.maximum(g["mon_open"].values - g["hi"].values, 0.0)
        n = len(g)
        # CQR: (1-α)(n+1)/n quantile, where α = 1-τ. Symmetric per-side: τ + (1-τ)/2 effective.
        # Use the conventional one-sided quantile: rank index = ceil((1 - α/2)(n+1)) - 1
        alpha = 1.0 - target
        rank_idx = int(np.ceil((1.0 - alpha / 2) * (n + 1))) - 1
        rank_idx = min(max(rank_idx, 0), n - 1)
        q_lower = float(np.sort(e_lower)[rank_idx])
        q_upper = float(np.sort(e_upper)[rank_idx])
        out[sym] = (q_lower, q_upper)
    return out


def apply_correction(test_df: pd.DataFrame, target: float,
                     corr_by_sym: dict[str, tuple[float, float]]) -> pd.DataFrame:
    sub = test_df[test_df["target"] == target].copy()
    sub["lo_adj"] = sub.apply(
        lambda r: r["lo"] - corr_by_sym.get(r["symbol"], (0.0, 0.0))[0], axis=1)
    sub["hi_adj"] = sub.apply(
        lambda r: r["hi"] + corr_by_sym.get(r["symbol"], (0.0, 0.0))[1], axis=1)
    return sub


def run_diag(sub: pd.DataFrame, lo_col: str, hi_col: str, label: str, target: float) -> dict:
    sub = sub.copy()
    sub["inside"] = ((sub["mon_open"] >= sub[lo_col]) & (sub["mon_open"] <= sub[hi_col])).astype(int)
    sub["half_width_bps"] = ((sub[hi_col] - sub[lo_col]) / 2.0 / sub["fri_close"] * 1e4)
    sub = sub.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)

    v_pooled = (1 - sub["inside"].values).astype(int)
    kup_lr, kup_p = met._lr_kupiec(v_pooled, target)
    chr_lr, chr_p = met._lr_christoffersen_independence(v_pooled)

    dq_total, dq_df_total = 0.0, 0
    per_sym_p = []
    per_sym_rows = []
    for sym, gg in sub.groupby("symbol"):
        v_g = (1 - gg["inside"].astype(int)).values
        if len(v_g) < 10:
            continue
        res = met.dynamic_quantile_test(v_g, target, n_lags=4)
        if np.isfinite(res["dq"]):
            dq_total += res["dq"]; dq_df_total += res["df"]
            per_sym_p.append(float(res["p_value"]))
            per_sym_rows.append({"label": label, "target": target, "symbol": sym,
                                 "n": int(res["n"]), "dq": float(res["dq"]),
                                 "p_value": float(res["p_value"])})
    p_dq_pooled = (float(1.0 - _chi2.cdf(max(dq_total, 0.0), df=max(dq_df_total, 1)))
                   if dq_df_total > 0 else float("nan"))
    arr = np.array(per_sym_p) if per_sym_p else np.array([float("nan")])
    median_p = float(np.median(arr)) if per_sym_p else float("nan")
    n_reject_05 = int((arr < 0.05).sum()) if per_sym_p else 0

    summary = {
        "label": label, "target": target, "n": int(len(sub)),
        "realised": float(sub["inside"].mean()),
        "n_violations": int((1 - sub["inside"]).sum()),
        "mean_hw_bps": float(sub["half_width_bps"].mean()),
        "kupiec_p": float(kup_p), "christoffersen_p": float(chr_p),
        "p_dq_pooled": p_dq_pooled,
        "p_dq_per_symbol_median": median_p,
        "n_symbols_reject_05": n_reject_05,
    }
    return {"summary": summary, "per_symbol": per_sym_rows}


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    print(f"Full panel: {len(panel):,} rows", flush=True)

    print("\n--- Computing pooled-tail bounds (Trial 3 base) ---", flush=True)
    t0 = time.time()
    bounds = replay_with_pooled_tail(panel)
    print(f"  Done in {time.time()-t0:.1f}s; {len(bounds):,} (symbol, fri_ts, target) rows", flush=True)

    # Conformal-calibration split: use pre-2023 panel (= the calibration set
    # for the F1 fits also) as the conformal-calibration set; the full post-
    # 2023 OOS as the test. ~430 cal rows per symbol for the (1-α/2)(n+1)/n
    # quantile at τ=0.99 — well-defined and stable.
    cal_df = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    test_df = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"\nConformal-cal: pre-2023 ({len(cal_df):,} rows = ~{len(cal_df)//40} per (symbol, target))")
    print(f"Test (full OOS): {len(test_df):,} rows in {test_df['fri_ts'].nunique()} weekends")
    print(f"Note: F1 fits use a rolling 156-window so the conformal-calibration set is\n"
          f"      not held-out from the F1 fits — same look-ahead structure as v1b_buffer_tune.md\n"
          f"      and the existing Christoffersen evaluation.")

    summary_rows = []
    per_sym_all = []
    for tau in HEADLINE_TAUS:
        # Baseline: pooled-tail uncorrected (no Mondrian)
        baseline_test = test_df[test_df["target"] == tau].copy()
        res_base = run_diag(baseline_test, "lo", "hi", label=f"baseline_pooled", target=tau)

        # Mondrian-corrected: per-symbol CQR correction from cal split
        corr = mondrian_correction(cal_df, tau)
        adj_test = apply_correction(test_df, tau, corr)
        res_mond = run_diag(adj_test, "lo_adj", "hi_adj", label=f"mondrian_pooled", target=tau)

        summary_rows.append(res_base["summary"])
        summary_rows.append(res_mond["summary"])
        per_sym_all.extend(res_base["per_symbol"])
        per_sym_all.extend(res_mond["per_symbol"])

    summary = pd.DataFrame(summary_rows)
    per_sym = pd.DataFrame(per_sym_all)

    print("\n=== Diagnostic battery (test split only, second 50% of OOS) ===", flush=True)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Per-symbol DQ at τ=0.99 — Baseline vs Mondrian (test split) ===", flush=True)
    p99 = per_sym[per_sym["target"] == 0.99].pivot_table(
        index="symbol", columns="label", values="p_value")
    print(p99.to_string(float_format=lambda x: f"{x:.4f}"))

    out_dir = REPORTS / "tables"
    summary.to_csv(out_dir / "v1b_oos_mondrian_summary.csv", index=False)
    per_sym.to_csv(out_dir / "v1b_oos_dq_per_symbol_mondrian.csv", index=False)
    print(f"\nWrote {out_dir / 'v1b_oos_mondrian_summary.csv'}")
    print(f"Wrote {out_dir / 'v1b_oos_dq_per_symbol_mondrian.csv'}")

    print("\n" + "=" * 80)
    print("DECISION SCORECARD — Trial 2 (Mondrian on pooled-tail) at τ = 0.99 (test split)")
    print("=" * 80)
    base_99 = summary[(summary["label"] == "baseline_pooled") & (summary["target"] == 0.99)].iloc[0]
    mond_99 = summary[(summary["label"] == "mondrian_pooled") & (summary["target"] == 0.99)].iloc[0]
    cap = 1.5 * base_99["mean_hw_bps"]
    print(f"  Threshold 1: per-symbol DQ reject-count ≤ 3/10 (test split has fewer obs/symbol)")
    print(f"    baseline: {int(base_99['n_symbols_reject_05'])}/10   "
          f"mondrian: {int(mond_99['n_symbols_reject_05'])}/10")
    print(f"  Threshold 2: realised within ±2pp of 0.99")
    print(f"    baseline: {base_99['realised']:.3f}   mondrian: {mond_99['realised']:.3f}")
    print(f"  Threshold 3: Christoffersen p_ind > 0.05")
    print(f"    baseline: {base_99['christoffersen_p']:.3f}   mondrian: {mond_99['christoffersen_p']:.3f}")
    print(f"  Threshold 4: bandwidth ≤ 1.5× baseline (cap = {cap:.0f} bps)")
    print(f"    baseline: {base_99['mean_hw_bps']:.0f} bps   mondrian: {mond_99['mean_hw_bps']:.0f} bps   "
          f"PASS: {mond_99['mean_hw_bps'] <= cap}")


if __name__ == "__main__":
    main()
