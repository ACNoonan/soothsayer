"""
Trial 3 — Pooled-tail-only calibration (control / falsification).

Per methodology log entry 2026-04-28 (late evening). At τ ≥ 0.95 the tail
quantile of the standardized residuals z_hist is computed by pooling
across all 10 symbols' z_hist values within the same calibration window
(rolling 156 weekends prior). At τ ≤ 0.85 the per-symbol empirical
quantile is unchanged.

Standardization rationale: z_hist is already symbol-specific (each
symbol's residuals divided by its own σ_now). Pooling z values across
symbols is therefore a valid pooling-of-standardized-residuals — a
much larger sample (~150 × 10 = 1500 vs single-symbol's ~150) that
gives ~7-8 effective tail observations at the 99.5th percentile vs the
single-symbol's ~0.8.

If pooled-tail also gives 6/10 per-symbol DQ rejections at τ=0.99
(matching Trial 1 EVT), that fully rules out the small-sample-noise
mechanism family and the residual signal is conditional dynamics. If
pooled-tail moves the count, the joint reading with Trial 1 EVT is
more nuanced.

Decision threshold same as Trial 1.
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
    """Replay the per-(symbol, fri_ts) F1 fit and produce both
    per-symbol-empirical and pooled-tail bounds at each headline τ.

    For each (symbol, fri_ts) we compute:
      * z_hist: symbol-specific standardized residuals (rolling 156-window)
      * empirical bounds (current production): quantile of THIS symbol's z_hist
      * pooled-tail bounds: at τ ≥ 0.95 only, the quantile is taken from
        the union of z_hist across all symbols whose calibration window
        ends at the same (or nearest) fri_ts.

    To keep things tractable we aggregate within a regime: pooled z_hist
    at fri_ts = union of z_hist across all symbols in the same regime.
    """
    point_fa = fc.point_futures_adjusted(panel)
    extra_cols = list(EXTRA_REGRESSORS)

    # First pass: compute z_hist per (symbol, fri_ts) and store
    # alongside sigma_now and pfa for later bound construction.
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
    print(f"  Cells: {len(cells):,} (symbol, fri_ts) pairs", flush=True)

    # Second pass: for each (regime, fri_ts), build a pooled z_hist
    # by concatenating across all symbols in that regime/time cell.
    pooled_by_key: dict[tuple, np.ndarray] = {}
    for (regime, fri_ts), g in cells.groupby(["regime_pub", "fri_ts"]):
        pooled = np.concatenate(g["z_hist"].values)
        pooled_by_key[(regime, fri_ts)] = pooled

    # Third pass: emit bounds at each headline τ. For τ ≤ 0.85, use
    # per-symbol empirical (current production). For τ ≥ 0.95, use the
    # pooled-tail empirical quantile.
    out_rows = []
    for _, c in cells.iterrows():
        z_hist_sym = c["z_hist"]
        z_hist_pool = pooled_by_key[(c["regime_pub"], c["fri_ts"])]
        for tau in HEADLINE_TAUS:
            tail = (1 - tau) / 2
            # Empirical (current production: per-symbol)
            z_lo_emp = float(np.quantile(z_hist_sym, tail))
            z_hi_emp = float(np.quantile(z_hist_sym, 1 - tail))
            lo_emp = c["pfa"] * np.exp(z_lo_emp * c["sigma_now"])
            hi_emp = c["pfa"] * np.exp(z_hi_emp * c["sigma_now"])

            if tau in TAIL_TAUS:
                z_lo_pool = float(np.quantile(z_hist_pool, tail))
                z_hi_pool = float(np.quantile(z_hist_pool, 1 - tail))
                lo_pool = c["pfa"] * np.exp(z_lo_pool * c["sigma_now"])
                hi_pool = c["pfa"] * np.exp(z_hi_pool * c["sigma_now"])
            else:
                lo_pool = lo_emp
                hi_pool = hi_emp

            out_rows.append({
                "symbol": c["symbol"], "fri_ts": c["fri_ts"], "regime_pub": c["regime_pub"],
                "target": tau,
                "mon_open": c["mon_open"], "fri_close": c["fri_close"],
                "lo_emp": lo_emp, "hi_emp": hi_emp,
                "lo_pool": lo_pool, "hi_pool": hi_pool,
                "n_pool": len(z_hist_pool),
            })

    return pd.DataFrame(out_rows)


def run_diag_battery(served: pd.DataFrame, bound_cols: tuple[str, str], label: str) -> dict:
    lo_col, hi_col = bound_cols
    rows = []
    per_symbol_rows = []
    for tau in HEADLINE_TAUS:
        sub = served[served["target"] == tau].copy()
        sub["inside"] = ((sub["mon_open"] >= sub[lo_col]) & (sub["mon_open"] <= sub[hi_col])).astype(int)
        sub["half_width_bps"] = ((sub[hi_col] - sub[lo_col]) / 2.0 / sub["fri_close"] * 1e4)
        sub = sub.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)

        v_pooled = (1 - sub["inside"].values).astype(int)
        kup_lr, kup_p = met._lr_kupiec(v_pooled, tau)
        chr_lr, chr_p = met._lr_christoffersen_independence(v_pooled)
        realised = float(sub["inside"].mean())
        n_violations = int((1 - sub["inside"]).sum())
        mean_hw = float(sub["half_width_bps"].mean())

        dq_total, dq_df_total = 0.0, 0
        per_sym_p = []
        for sym, gg in sub.groupby("symbol"):
            v_g = (1 - gg["inside"].astype(int)).values
            if len(v_g) < 10:
                continue
            res = met.dynamic_quantile_test(v_g, tau, n_lags=4)
            if np.isfinite(res["dq"]):
                dq_total += res["dq"]; dq_df_total += res["df"]
                per_sym_p.append(float(res["p_value"]))
                per_symbol_rows.append({
                    "label": label, "target": tau, "symbol": sym,
                    "n": int(res["n"]), "dq": float(res["dq"]),
                    "p_value": float(res["p_value"]),
                })
        p_dq_pooled = (float(1.0 - _chi2.cdf(max(dq_total, 0.0), df=max(dq_df_total, 1)))
                       if dq_df_total > 0 else float("nan"))
        per_sym_arr = np.array(per_sym_p) if per_sym_p else np.array([float("nan")])
        median_p = float(np.median(per_sym_arr)) if per_sym_p else float("nan")
        n_reject_05 = int((per_sym_arr < 0.05).sum()) if per_sym_p else 0

        rows.append({
            "label": label, "target": tau, "n": int(len(sub)),
            "realised": realised, "n_violations": n_violations,
            "mean_hw_bps": mean_hw,
            "kupiec_lr": float(kup_lr), "kupiec_p": float(kup_p),
            "christoffersen_lr": float(chr_lr), "christoffersen_p": float(chr_p),
            "dq_pooled": dq_total, "dq_df": dq_df_total, "p_dq_pooled": p_dq_pooled,
            "p_dq_per_symbol_median": median_p,
            "n_symbols_reject_05": n_reject_05,
        })
    return {"summary": pd.DataFrame(rows), "per_symbol": pd.DataFrame(per_symbol_rows)}


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    print(f"Full panel: {len(panel):,} rows", flush=True)

    t0 = time.time()
    bounds_long = replay_with_pooled_tail(panel)
    print(f"\nReplay+pool complete in {time.time()-t0:.1f}s; "
          f"{len(bounds_long):,} (symbol, fri_ts, target) rows", flush=True)

    bounds_oos = bounds_long[bounds_long["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"OOS slice: {len(bounds_oos):,} rows in {bounds_oos['fri_ts'].nunique()} weekends", flush=True)
    print(f"Pooled z_hist sample sizes (first 5 rows): "
          f"{bounds_oos['n_pool'].head().tolist()}", flush=True)

    print("\n=== Empirical (per-symbol; baseline replay) ===", flush=True)
    res_emp = run_diag_battery(bounds_oos, ("lo_emp", "hi_emp"), label="empirical")
    print(res_emp["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Pooled-tail (Trial 3) ===", flush=True)
    res_pool = run_diag_battery(bounds_oos, ("lo_pool", "hi_pool"), label="pooled")
    print(res_pool["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Per-symbol DQ — Pooled (τ=0.99 row) ===", flush=True)
    sub99 = res_pool["per_symbol"][res_pool["per_symbol"]["target"] == 0.99].sort_values("symbol")
    print(sub99.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    out_dir = REPORTS / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.concat([res_emp["summary"], res_pool["summary"]], ignore_index=True)
    per_symbol = pd.concat([res_emp["per_symbol"], res_pool["per_symbol"]], ignore_index=True)
    summary.to_csv(out_dir / "v1b_oos_pooled_tail_summary.csv", index=False)
    per_symbol.to_csv(out_dir / "v1b_oos_dq_per_symbol_pooled.csv", index=False)
    print(f"\nWrote {out_dir / 'v1b_oos_pooled_tail_summary.csv'}")
    print(f"Wrote {out_dir / 'v1b_oos_dq_per_symbol_pooled.csv'}")

    print("\n" + "=" * 80)
    print("DECISION SCORECARD — Trial 3 (Pooled-tail) at τ = 0.99")
    print("=" * 80)
    emp_99 = res_emp["summary"][res_emp["summary"]["target"] == 0.99].iloc[0]
    pool_99 = res_pool["summary"][res_pool["summary"]["target"] == 0.99].iloc[0]
    cap_hw = 1.5 * emp_99["mean_hw_bps"]
    print(f"  Threshold 1: per-symbol DQ reject-count ≤ 3/10")
    print(f"    empirical: {int(emp_99['n_symbols_reject_05'])}/10   "
          f"pooled: {int(pool_99['n_symbols_reject_05'])}/10   "
          f"PASS: {pool_99['n_symbols_reject_05'] <= 3}")
    print(f"  Threshold 2: pooled realised within ±2pp of 0.99")
    print(f"    empirical: {emp_99['realised']:.3f}   pooled: {pool_99['realised']:.3f}   "
          f"PASS: {abs(pool_99['realised'] - 0.99) <= 0.02}")
    print(f"  Threshold 3: Christoffersen p_ind > 0.05")
    print(f"    empirical: {emp_99['christoffersen_p']:.3f}   pooled: {pool_99['christoffersen_p']:.3f}   "
          f"PASS: {pool_99['christoffersen_p'] > 0.05}")
    print(f"  Threshold 4: mean half-width ≤ 1.5× empirical (cap = {cap_hw:.0f} bps)")
    print(f"    empirical: {emp_99['mean_hw_bps']:.0f} bps   pooled: {pool_99['mean_hw_bps']:.0f} bps   "
          f"PASS: {pool_99['mean_hw_bps'] <= cap_hw}")


if __name__ == "__main__":
    main()
