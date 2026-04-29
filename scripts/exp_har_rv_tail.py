"""
Family D — HAR-RV multi-horizon realized-vol regressors on top of pooled-tail.

Per methodology log entry 2026-04-28 (late evening, +4). Trial 6 added a
single-horizon log(fri_vol_20d) regressor and helped at τ ≤ 0.95 but not
at τ = 0.99. This trial extends to a multi-horizon HAR-style structure
adapted to the weekend-prediction setting.

Three horizons, all derivable from the existing weekly panel (no new data):
  * rv_w1:    |log return| from last weekend's fri_close to this weekend's
              (short horizon — most recent weekly return magnitude)
  * fri_vol_20d:    trailing 20-trading-day daily-return std (medium horizon,
              already in panel)
  * rv_w13:   std of last 13 weekly log-returns (long horizon ~ quarterly)

Joint regression in F1's σ model:
  log|residual_t| = α + β · log(VIX_t) + γ_d · log(rv_w1_t)
                                       + γ_w · log(fri_vol_20d_t)
                                       + γ_m · log(rv_w13_t)
                                       + γ_e · earnings_t
                                       + γ_l · long_weekend_t

Stacks on Trial 3's pooled-tail base. Same four-threshold scorecard.

Hypothesis: multi-horizon vol persistence captures conditional-vol
structure beyond the single-horizon Trial 6 augmentation; helps at
τ = 0.99 specifically (the corner Trial 6 missed).
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
EXTRA_REGRESSORS_HAR = (
    "earnings_next_week_f", "is_long_weekend",
    "log_rv_w1", "log_fri_vol_20d", "log_rv_w13",
)
VOL_COL_BY_SYMBOL = {
    "SPY": "vix_fri_close", "QQQ": "vix_fri_close",
    "AAPL": "vix_fri_close", "GOOGL": "vix_fri_close",
    "NVDA": "vix_fri_close", "TSLA": "vix_fri_close",
    "HOOD": "vix_fri_close", "MSTR": "vix_fri_close",
    "GLD": "gvz_fri_close", "TLT": "move_fri_close",
}


def add_har_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Add three HAR-style multi-horizon vol features to the panel.

    Computed per-symbol from the weekly fri_close series (no external data):
      * log_rv_w1:        log of |last weekend's log-return|
      * log_fri_vol_20d:  log of existing fri_vol_20d (trailing daily-RV proxy)
      * log_rv_w13:       log of trailing 13-weekend std of weekly log-returns

    All three are observable at fri_ts (no look-ahead).
    """
    out_parts = []
    for sym, g in panel.groupby("symbol"):
        g = g.sort_values("fri_ts").copy()
        # Weekly log-return from previous fri_close to this fri_close
        g["weekly_ret"] = np.log(g["fri_close"].astype(float) /
                                  g["fri_close"].shift(1).astype(float))
        # Short horizon: |last weekend's weekly log-return|
        # (shift by 1: row i uses the return ending at fri_ts of row i-1)
        last_abs = g["weekly_ret"].shift(1).abs()
        g["log_rv_w1"] = np.log(last_abs.clip(lower=1e-6))
        # Medium horizon: existing fri_vol_20d, log-transformed
        g["log_fri_vol_20d"] = np.log(g["fri_vol_20d"].astype(float).clip(lower=1e-6))
        # Long horizon: trailing 13-weekend std of weekly returns
        # (rolling window ending at row i-1, since row i hasn't observed its own weekly_ret yet)
        rw13 = g["weekly_ret"].shift(1).rolling(window=13, min_periods=8).std()
        g["log_rv_w13"] = np.log(rw13.clip(lower=1e-6))
        out_parts.append(g)
    return pd.concat(out_parts).sort_index()


def replay_with_pooled_tail(panel: pd.DataFrame, extra_regressors: tuple[str, ...]) -> pd.DataFrame:
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
            alpha_p = beta_hat[0]; b = beta_hat[1]
            gammas = dict(zip(kept, beta_hat[2:]))

            sigma_hist_log = alpha_p + b * np.log(v_v)
            for col in kept:
                sigma_hist_log = sigma_hist_log + gammas[col] * past_extras[col][valid]
            sigma_hist = np.exp(sigma_hist_log)
            sigma_now_log = alpha_p + b * np.log(vol_i)
            for col in kept:
                # Skip the now_extra if it's NaN (e.g. log_rv_w13 in early window)
                v_now = now_extras[col]
                if not np.isfinite(v_now):
                    v_now = float(np.nanmean(past_extras[col][valid]))
                sigma_now_log += gammas[col] * v_now
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
                "sigma_now": c["sigma_now"],
            })
    return pd.DataFrame(out_rows)


def run_diag_battery(served: pd.DataFrame, label: str) -> dict:
    rows = []
    per_symbol_rows = []
    for tau in HEADLINE_TAUS:
        sub = served[served["target"] == tau].copy()
        sub["inside"] = ((sub["mon_open"] >= sub["lo"]) & (sub["mon_open"] <= sub["hi"])).astype(int)
        sub["half_width_bps"] = ((sub["hi"] - sub["lo"]) / 2.0 / sub["fri_close"] * 1e4)
        sub = sub.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)

        v_pooled = (1 - sub["inside"].values).astype(int)
        kup_lr, kup_p = met._lr_kupiec(v_pooled, tau)
        chr_lr, chr_p = met._lr_christoffersen_independence(v_pooled)

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
                per_symbol_rows.append({"label": label, "target": tau, "symbol": sym,
                                        "n": int(res["n"]), "dq": float(res["dq"]),
                                        "p_value": float(res["p_value"])})
        p_dq_pooled = (float(1.0 - _chi2.cdf(max(dq_total, 0.0), df=max(dq_df_total, 1)))
                       if dq_df_total > 0 else float("nan"))
        arr = np.array(per_sym_p) if per_sym_p else np.array([float("nan")])
        n_reject_05 = int((arr < 0.05).sum()) if per_sym_p else 0
        median_p = float(np.median(arr)) if per_sym_p else float("nan")

        rows.append({
            "label": label, "target": tau, "n": int(len(sub)),
            "realised": float(sub["inside"].mean()),
            "n_violations": int((1 - sub["inside"]).sum()),
            "mean_hw_bps": float(sub["half_width_bps"].mean()),
            "kupiec_p": float(kup_p), "christoffersen_p": float(chr_p),
            "p_dq_pooled": p_dq_pooled,
            "p_dq_per_symbol_median": median_p,
            "n_symbols_reject_05": n_reject_05,
        })
    return {"summary": pd.DataFrame(rows), "per_symbol": pd.DataFrame(per_symbol_rows)}


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    panel = add_har_features(panel)
    print(f"Full panel: {len(panel):,} rows; HAR features added", flush=True)
    print(f"  log_rv_w1   range: [{panel['log_rv_w1'].min():.2f}, {panel['log_rv_w1'].max():.2f}], "
          f"non-null: {panel['log_rv_w1'].notna().sum():,}/{len(panel):,}")
    print(f"  log_fri_vol_20d range: [{panel['log_fri_vol_20d'].min():.2f}, {panel['log_fri_vol_20d'].max():.2f}]")
    print(f"  log_rv_w13  range: [{panel['log_rv_w13'].min():.2f}, {panel['log_rv_w13'].max():.2f}], "
          f"non-null: {panel['log_rv_w13'].notna().sum():,}/{len(panel):,}")

    # Trial 6 base for comparison: pooled-tail + log_fri_vol_20d only
    print("\n--- Trial 6 baseline (pooled-tail + log_fri_vol_20d) ---", flush=True)
    t0 = time.time()
    bounds_t6 = replay_with_pooled_tail(panel, ("earnings_next_week_f", "is_long_weekend", "log_fri_vol_20d"))
    print(f"  Done in {time.time()-t0:.1f}s; {len(bounds_t6):,} rows")

    # Family D: HAR-RV (3 vol horizons)
    print("\n--- Family D HAR-RV (pooled-tail + log_rv_w1 + log_fri_vol_20d + log_rv_w13) ---", flush=True)
    t0 = time.time()
    bounds_d = replay_with_pooled_tail(panel, EXTRA_REGRESSORS_HAR)
    print(f"  Done in {time.time()-t0:.1f}s; {len(bounds_d):,} rows")

    bounds_t6_oos = bounds_t6[bounds_t6["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_d_oos = bounds_d[bounds_d["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"\nOOS slices: trial6={len(bounds_t6_oos):,}, family_d={len(bounds_d_oos):,}", flush=True)

    print("\n=== Trial 6 baseline (1 vol horizon) ===", flush=True)
    res_t6 = run_diag_battery(bounds_t6_oos, label="trial6_1horizon")
    print(res_t6["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Family D HAR-RV (3 vol horizons) ===", flush=True)
    res_d = run_diag_battery(bounds_d_oos, label="family_d_har_rv")
    print(res_d["summary"].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\n=== Per-symbol DQ at τ=0.99 — Trial 6 vs Family D ===", flush=True)
    t6_99 = res_t6["per_symbol"][res_t6["per_symbol"]["target"] == 0.99].set_index("symbol")[["p_value"]]
    d_99 = res_d["per_symbol"][res_d["per_symbol"]["target"] == 0.99].set_index("symbol")[["p_value"]]
    cmp = t6_99.join(d_99, lsuffix="_t6", rsuffix="_d").sort_index()
    cmp["t6_reject"] = cmp["p_value_t6"] < 0.05
    cmp["d_reject"] = cmp["p_value_d"] < 0.05
    print(cmp.to_string(float_format=lambda x: f"{x:.4f}"))

    out_dir = REPORTS / "tables"
    summary = pd.concat([res_t6["summary"], res_d["summary"]], ignore_index=True)
    per_sym = pd.concat([res_t6["per_symbol"], res_d["per_symbol"]], ignore_index=True)
    summary.to_csv(out_dir / "v1b_oos_har_rv_summary.csv", index=False)
    per_sym.to_csv(out_dir / "v1b_oos_dq_per_symbol_har_rv.csv", index=False)
    print(f"\nWrote {out_dir / 'v1b_oos_har_rv_summary.csv'}")
    print(f"Wrote {out_dir / 'v1b_oos_dq_per_symbol_har_rv.csv'}")

    print("\n" + "=" * 80)
    print("DECISION SCORECARD — Family D (pooled-tail + HAR-RV) at τ = 0.99")
    print("=" * 80)
    t6_99_sum = res_t6["summary"][res_t6["summary"]["target"] == 0.99].iloc[0]
    d_99_sum = res_d["summary"][res_d["summary"]["target"] == 0.99].iloc[0]
    cap = 1.5 * t6_99_sum["mean_hw_bps"]
    print(f"  Threshold 1: per-symbol DQ reject-count ≤ 3/10")
    print(f"    trial6_1h: {int(t6_99_sum['n_symbols_reject_05'])}/10   "
          f"family_d_3h: {int(d_99_sum['n_symbols_reject_05'])}/10   "
          f"PASS: {d_99_sum['n_symbols_reject_05'] <= 3}")
    print(f"  Threshold 2: realised within ±2pp of 0.99")
    print(f"    trial6_1h: {t6_99_sum['realised']:.3f}   family_d_3h: {d_99_sum['realised']:.3f}")
    print(f"  Threshold 3: Christoffersen p_ind > 0.05")
    print(f"    trial6_1h: {t6_99_sum['christoffersen_p']:.3f}   family_d_3h: {d_99_sum['christoffersen_p']:.3f}")
    print(f"  Threshold 4: bandwidth ≤ 1.5× trial6_1h baseline (cap = {cap:.0f} bps)")
    print(f"    trial6_1h: {t6_99_sum['mean_hw_bps']:.0f} bps   family_d_3h: {d_99_sum['mean_hw_bps']:.0f} bps   "
          f"PASS: {d_99_sum['mean_hw_bps'] <= cap}")
    print(f"\n  Marginal value of HAR-RV vs Trial 6 single-horizon:")
    print(f"    DQ rejects:  {int(t6_99_sum['n_symbols_reject_05'])}/10 → {int(d_99_sum['n_symbols_reject_05'])}/10")
    print(f"    Realised:    {t6_99_sum['realised']:.3f} → {d_99_sum['realised']:.3f}")
    print(f"    Bandwidth:   {t6_99_sum['mean_hw_bps']:.0f} → {d_99_sum['mean_hw_bps']:.0f} bps "
          f"({(d_99_sum['mean_hw_bps'] - t6_99_sum['mean_hw_bps']) / t6_99_sum['mean_hw_bps'] * 100:+.1f}%)")
    print()
    print("  Lower-anchor sums (per-symbol reject-count summed across τ ∈ {0.68, 0.85, 0.95}):")
    t6_low_sum = sum(int(res_t6["summary"][res_t6["summary"]["target"] == t]["n_symbols_reject_05"].iloc[0])
                     for t in [0.68, 0.85, 0.95])
    d_low_sum = sum(int(res_d["summary"][res_d["summary"]["target"] == t]["n_symbols_reject_05"].iloc[0])
                    for t in [0.68, 0.85, 0.95])
    print(f"    trial6_1h: {t6_low_sum}/30   family_d_3h: {d_low_sum}/30")


if __name__ == "__main__":
    main()
