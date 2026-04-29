"""
Trial 6 — State augmentation: log(fri_vol_20d) as an extra F1 σ regressor.

Per methodology log entry 2026-04-28 (late evening, +3). F1's current σ
model regresses log|residual| on log(VIX) + earnings_next_week +
is_long_weekend. This trial adds log(fri_vol_20d) — the trailing 20-trading-day
std of THIS symbol's log-returns at Friday close — as a fourth regressor.
fri_vol_20d carries per-symbol realized-vol information that VIX (forward-
looking, market-wide) doesn't.

Hypothesis: per-symbol conditional-volatility persistence is the residual
mechanism beyond pooled-tail (Trial 3 PASSES at 3/10 reject; AAPL, HOOD,
SPY remain rejecting). Adding the per-symbol realized-vol predictor
should reduce the AAPL/HOOD/SPY tail miscalibration via a tighter
symbol-specific σ_now.

Stacks on top of the pooled-tail base from Trial 3 — at τ ≥ 0.95 the
quantile is from the pooled-cross-section z_hist, but the σ_now applied
to convert z to bound is from the augmented regression.

Decision threshold: same four-threshold scorecard. Improvement over
Trial 3 (pooled-tail) on threshold 1 is the goal.
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
EXTRA_REGRESSORS_BASE = ("earnings_next_week_f", "is_long_weekend")
EXTRA_REGRESSORS_AUG = ("earnings_next_week_f", "is_long_weekend", "log_fri_vol_20d")
VOL_COL_BY_SYMBOL = {
    "SPY": "vix_fri_close", "QQQ": "vix_fri_close",
    "AAPL": "vix_fri_close", "GOOGL": "vix_fri_close",
    "NVDA": "vix_fri_close", "TSLA": "vix_fri_close",
    "HOOD": "vix_fri_close", "MSTR": "vix_fri_close",
    "GLD": "gvz_fri_close", "TLT": "move_fri_close",
}


def replay_with_pooled_tail(panel: pd.DataFrame, extra_regressors: tuple[str, ...]) -> pd.DataFrame:
    """Replay F1 fit + pooled-tail bound construction; parameterised by the
    extra-regressor list so the same code drives both Trial 3 base and Trial 6
    state-augmented variants.
    """
    point_fa = fc.point_futures_adjusted(panel)
    extra_cols = list(extra_regressors)
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
        z_hist_sym = c["z_hist"]
        z_hist_pool = pooled_by_key[(c["regime_pub"], c["fri_ts"])]
        for tau in HEADLINE_TAUS:
            tail = (1 - tau) / 2
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
                lo_pool = lo_emp; hi_pool = hi_emp
            out_rows.append({
                "symbol": c["symbol"], "fri_ts": c["fri_ts"], "regime_pub": c["regime_pub"],
                "target": tau,
                "mon_open": c["mon_open"], "fri_close": c["fri_close"],
                "lo_emp": lo_emp, "hi_emp": hi_emp,
                "lo_pool": lo_pool, "hi_pool": hi_pool,
                "sigma_now": c["sigma_now"],
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
    # Add log_fri_vol_20d for Trial 6 augmentation
    panel["log_fri_vol_20d"] = np.log(panel["fri_vol_20d"].astype(float).clip(lower=1e-6))
    print(f"Full panel: {len(panel):,} rows; "
          f"log_fri_vol_20d range [{panel['log_fri_vol_20d'].min():.2f}, "
          f"{panel['log_fri_vol_20d'].max():.2f}]", flush=True)

    # Trial 3 base (pooled-tail) — for direct comparison
    print("\n--- Computing Trial 3 base (pooled-tail, original σ regressors) ---", flush=True)
    t0 = time.time()
    bounds_base = replay_with_pooled_tail(panel, EXTRA_REGRESSORS_BASE)
    print(f"  Done in {time.time()-t0:.1f}s; {len(bounds_base):,} rows", flush=True)

    # Trial 6 augmented (pooled-tail + log_fri_vol_20d in σ regression)
    print("\n--- Computing Trial 6 augmented (pooled-tail + log_fri_vol_20d) ---", flush=True)
    t0 = time.time()
    bounds_aug = replay_with_pooled_tail(panel, EXTRA_REGRESSORS_AUG)
    print(f"  Done in {time.time()-t0:.1f}s; {len(bounds_aug):,} rows", flush=True)

    bounds_base_oos = bounds_base[bounds_base["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_aug_oos = bounds_aug[bounds_aug["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"\nOOS slices: base={len(bounds_base_oos):,} rows, aug={len(bounds_aug_oos):,} rows", flush=True)

    print("\n=== Trial 3 base — pooled-tail (per-symbol σ from VIX + earnings + long_weekend) ===", flush=True)
    res_base = run_diag_battery(bounds_base_oos, ("lo_pool", "hi_pool"), label="trial3_base")
    print(res_base["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Trial 6 augmented — pooled-tail + log(fri_vol_20d) in σ regression ===", flush=True)
    res_aug = run_diag_battery(bounds_aug_oos, ("lo_pool", "hi_pool"), label="trial6_aug")
    print(res_aug["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Per-symbol DQ at τ=0.99 — Trial 3 base vs Trial 6 augmented ===", flush=True)
    base99 = res_base["per_symbol"][res_base["per_symbol"]["target"] == 0.99].set_index("symbol")[["p_value"]]
    aug99 = res_aug["per_symbol"][res_aug["per_symbol"]["target"] == 0.99].set_index("symbol")[["p_value"]]
    cmp = base99.join(aug99, lsuffix="_base", rsuffix="_aug").sort_index()
    cmp["base_reject"] = cmp["p_value_base"] < 0.05
    cmp["aug_reject"] = cmp["p_value_aug"] < 0.05
    print(cmp.to_string(float_format=lambda x: f"{x:.4f}"))

    out_dir = REPORTS / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.concat([res_base["summary"], res_aug["summary"]], ignore_index=True)
    per_symbol = pd.concat([res_base["per_symbol"], res_aug["per_symbol"]], ignore_index=True)
    summary.to_csv(out_dir / "v1b_oos_state_aug_summary.csv", index=False)
    per_symbol.to_csv(out_dir / "v1b_oos_dq_per_symbol_state_aug.csv", index=False)
    bounds_aug_oos.to_parquet(DATA_PROCESSED / "exp_state_aug_bounds.parquet", index=False)
    print(f"\nWrote {out_dir / 'v1b_oos_state_aug_summary.csv'}")
    print(f"Wrote {out_dir / 'v1b_oos_dq_per_symbol_state_aug.csv'}")

    print("\n" + "=" * 80)
    print("DECISION SCORECARD — Trial 6 (pooled-tail + state augmentation) at τ = 0.99")
    print("=" * 80)
    base_99 = res_base["summary"][res_base["summary"]["target"] == 0.99].iloc[0]
    aug_99 = res_aug["summary"][res_aug["summary"]["target"] == 0.99].iloc[0]
    cap_hw_baseline = 1.5 * base_99["mean_hw_bps"]
    print(f"  Threshold 1: per-symbol DQ reject-count ≤ 3/10")
    print(f"    trial3_base: {int(base_99['n_symbols_reject_05'])}/10   "
          f"trial6_aug: {int(aug_99['n_symbols_reject_05'])}/10   "
          f"PASS: {aug_99['n_symbols_reject_05'] <= 3}")
    print(f"  Threshold 2: pooled realised within ±2pp of 0.99")
    print(f"    trial3_base: {base_99['realised']:.3f}   trial6_aug: {aug_99['realised']:.3f}   "
          f"PASS: {abs(aug_99['realised'] - 0.99) <= 0.02}")
    print(f"  Threshold 3: Christoffersen p_ind > 0.05")
    print(f"    trial3_base: {base_99['christoffersen_p']:.3f}   trial6_aug: {aug_99['christoffersen_p']:.3f}   "
          f"PASS: {aug_99['christoffersen_p'] > 0.05}")
    print(f"  Threshold 4: mean half-width ≤ 1.5× trial3 baseline (cap = {cap_hw_baseline:.0f} bps)")
    print(f"    trial3_base: {base_99['mean_hw_bps']:.0f} bps   trial6_aug: {aug_99['mean_hw_bps']:.0f} bps   "
          f"PASS: {aug_99['mean_hw_bps'] <= cap_hw_baseline}")
    print(f"\n  Marginal value of state augmentation:")
    print(f"    DQ rejects: {int(base_99['n_symbols_reject_05'])}/10 → {int(aug_99['n_symbols_reject_05'])}/10")
    print(f"    Realised:   {base_99['realised']:.3f} → {aug_99['realised']:.3f}")
    print(f"    Bandwidth:  {base_99['mean_hw_bps']:.0f} → {aug_99['mean_hw_bps']:.0f} bps "
          f"({(aug_99['mean_hw_bps'] - base_99['mean_hw_bps']) / base_99['mean_hw_bps'] * 100:+.1f}%)")


if __name__ == "__main__":
    main()
