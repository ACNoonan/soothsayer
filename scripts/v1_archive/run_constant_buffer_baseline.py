"""
Stale-price + global-buffer baseline (Paper 1 §7.6).

The "stupidest possible band": take the Friday close (stale Pyth/Chainlink
analog) and add a single global symmetric buffer b(τ) per claimed quantile.
One parameter per τ. No factor switchboard, no empirical residual quantile,
no regime model, no per-symbol tuning, no calibration surface.

Why it deserves a place in the ablation. The deployed methodology is fitted
to N ≈ 50–250 weekends per (symbol, regime) cell. A globally pooled
constant-buffer fit uses N ≈ 4,266 obs on the same training window, so its
coverage CI on the holdout is roughly ±2pp instead of ±15pp. If the regime
model only delivers a small width reduction at matched coverage, the modelling
complexity is not earning its keep.

Procedure (matches `run_serving_ablation.py` for fair comparison):
  1. Split panel at SPLIT_DATE = 2023-01-01 (training = pre-2023, OOS = 2023+).
  2. For each τ ∈ {0.68, 0.85, 0.95, 0.99}, calibrate the smallest b(τ) such
     that pooled training coverage of [fri_close·(1−b), fri_close·(1+b)] ≥ τ.
  3. Apply b(τ) symmetrically on the OOS panel; record realised coverage,
     mean half-width (bps), Kupiec, Christoffersen, per regime.
  4. Compute the same quantities for the deployed Oracle (hybrid + per-target
     buffer schedule) on the identical OOS panel.
  5. Block-bootstrap by weekend (1000 resamples) on Δcoverage and Δhalf-width%
     between the constant-buffer baseline and the deployed Oracle.

Outputs:
  reports/tables/v1b_constant_buffer_calibration.csv  trained b(τ) and training fit
  reports/tables/v1b_constant_buffer_oos.csv          OOS coverage/width per τ (both methods)
  reports/tables/v1b_constant_buffer_by_regime.csv    per-regime OOS breakdown per τ
  reports/tables/v1b_constant_buffer_bootstrap.csv    bootstrap CI on Δcoverage, Δsharpness%
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle, buffer_for_target


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95, 0.99)
N_BOOTSTRAP = 1000
RNG_SEED = 20260502
B_GRID = np.arange(0.0, 0.50001, 0.0001)  # 0 → 50% in 1bp steps


def _rel_dev(panel: pd.DataFrame) -> np.ndarray:
    fri = panel["fri_close"].astype(float).values
    mon = panel["mon_open"].astype(float).values
    valid = np.isfinite(fri) & np.isfinite(mon) & (fri > 0)
    return np.abs(mon[valid] - fri[valid]) / fri[valid]


def calibrate_global_buffer(panel_train: pd.DataFrame, target: float) -> dict:
    """Smallest symmetric multiplicative buffer b such that pooled empirical
    coverage of [fri_close·(1−b), fri_close·(1+b)] ≥ target on the training panel.

    Returns the calibrated b plus the training-fit diagnostic (realised
    coverage at the chosen b, n training obs, training half-width bps).
    """
    rel_dev = _rel_dev(panel_train)
    # The smallest b satisfying mean(rel_dev ≤ b) ≥ target is the empirical
    # quantile of rel_dev at level `target` (one-sided abs, so this is a
    # symmetric two-sided band by construction).
    b_emp = float(np.quantile(rel_dev, target, method="higher"))
    # Round up to the grid for reproducibility with the sweep loop.
    b = float(B_GRID[B_GRID >= b_emp][0]) if (B_GRID >= b_emp).any() else float(B_GRID[-1])
    realised_train = float(np.mean(rel_dev <= b))
    half_width_bps_train = float(b * 1e4)  # b in fraction → bps directly
    return {
        "target": target,
        "b": b,
        "n_train": int(len(rel_dev)),
        "realised_train": realised_train,
        "half_width_bps_train": half_width_bps_train,
    }


def coverage_matched_buffer(panel_oos: pd.DataFrame, target_realised: float) -> dict:
    """Smallest symmetric multiplicative buffer b such that pooled OOS coverage
    of [fri_close·(1−b), fri_close·(1+b)] ≥ target_realised. This is an
    *oracle* fit (uses the holdout to set b) — it gives the constant-buffer
    baseline its best possible width-at-coverage trade-off and answers the
    "width ratio at fixed realised coverage" question without the training/
    holdout distribution-shift confound."""
    rel_dev = _rel_dev(panel_oos)
    b_emp = float(np.quantile(rel_dev, target_realised, method="higher"))
    realised = float(np.mean(rel_dev <= b_emp))
    return {"b": b_emp, "realised_oos": realised, "half_width_bps": b_emp * 1e4}


def serve_constant_buffer(panel_oos: pd.DataFrame, b: float) -> pd.DataFrame:
    """Apply b symmetrically on OOS panel, return per-row table."""
    df = panel_oos[["symbol", "fri_ts", "regime_pub", "fri_close", "mon_open"]].copy()
    df["lower"] = df["fri_close"] * (1.0 - b)
    df["upper"] = df["fri_close"] * (1.0 + b)
    df["half_width_bps"] = b * 1e4  # fri_close cancels in the relative measure
    df["inside"] = ((df["mon_open"] >= df["lower"]) & (df["mon_open"] <= df["upper"])).astype(int)
    return df


def serve_oracle(oracle: Oracle, panel_oos: pd.DataFrame, target: float) -> pd.DataFrame:
    """Serve every (symbol, fri_ts) under the deployed Oracle config at `target`."""
    rows = []
    for _, w in panel_oos.iterrows():
        try:
            pp = oracle.fair_value(w["symbol"], w["fri_ts"], target_coverage=target)
        except (ValueError, KeyError):
            continue
        inside = (w["mon_open"] >= pp.lower) and (w["mon_open"] <= pp.upper)
        rows.append({
            "symbol": w["symbol"],
            "fri_ts": w["fri_ts"],
            "regime_pub": w["regime_pub"],
            "fri_close": float(w["fri_close"]),
            "mon_open": float(w["mon_open"]),
            "lower": float(pp.lower),
            "upper": float(pp.upper),
            "half_width_bps": float(pp.half_width_bps),
            "inside": int(bool(inside)),
        })
    return pd.DataFrame(rows)


def pooled_summary(served: pd.DataFrame, target: float) -> dict:
    """Pooled coverage + mean half-width + Kupiec + Christoffersen-by-symbol."""
    n = len(served)
    realised = float(served["inside"].mean())
    half = float(served["half_width_bps"].mean())
    v = (~served["inside"].astype(bool)).astype(int).values
    lr_uc, p_uc = met._lr_kupiec(v, target)
    lr_ind_total = 0.0
    n_groups = 0
    for sym, g in served.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
        v_g = (~g["inside"].astype(bool)).astype(int).values
        lr_ind, _ = met._lr_christoffersen_independence(v_g)
        if not np.isnan(lr_ind):
            lr_ind_total += lr_ind
            n_groups += 1
    p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
    return {
        "n": n,
        "realised": realised,
        "half_width_bps": half,
        "lr_uc": float(lr_uc),
        "p_uc": float(p_uc),
        "lr_ind": float(lr_ind_total),
        "p_ind": p_ind,
    }


def by_regime_summary(served: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for regime, g in served.groupby("regime_pub"):
        rows.append({
            "regime_pub": regime,
            "n": len(g),
            "realised": float(g["inside"].mean()),
            "half_width_bps": float(g["half_width_bps"].mean()),
        })
    return pd.DataFrame(rows).sort_values("regime_pub").reset_index(drop=True)


def block_bootstrap_delta(serv_a: pd.DataFrame, serv_b: pd.DataFrame,
                          rng: np.random.Generator, n_resamples: int = N_BOOTSTRAP):
    """Per-weekend block bootstrap on Δcoverage (pp) and Δsharpness% ((b/a−1)·100).

    Vectorised: aggregate (inside_sum, half_width_sum, n) per weekend once,
    then resample weekend indices and pool via cumulative sums.
    """
    keys = ["fri_ts"]
    a_grp = serv_a.groupby(keys, as_index=True).agg(
        a_inside=("inside", "sum"),
        a_hw=("half_width_bps", "sum"),
        a_n=("inside", "count"),
    )
    b_grp = serv_b.groupby(keys, as_index=True).agg(
        b_inside=("inside", "sum"),
        b_hw=("half_width_bps", "sum"),
        b_n=("inside", "count"),
    )
    joined = a_grp.join(b_grp, how="inner").reset_index()
    if len(joined) == 0:
        return np.array([]), np.array([])
    a_in = joined["a_inside"].to_numpy(dtype=float)
    a_hw = joined["a_hw"].to_numpy(dtype=float)
    a_n  = joined["a_n"].to_numpy(dtype=float)
    b_in = joined["b_inside"].to_numpy(dtype=float)
    b_hw = joined["b_hw"].to_numpy(dtype=float)
    b_n  = joined["b_n"].to_numpy(dtype=float)
    n_w = len(joined)

    deltas_cov = np.empty(n_resamples)
    deltas_sharp = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, n_w, size=n_w)
        a_cov = a_in[idx].sum() / a_n[idx].sum()
        b_cov = b_in[idx].sum() / b_n[idx].sum()
        a_hw_i = a_hw[idx].sum() / a_n[idx].sum()
        b_hw_i = b_hw[idx].sum() / b_n[idx].sum()
        deltas_cov[i] = (b_cov - a_cov) * 100.0
        deltas_sharp[i] = (b_hw_i - a_hw_i) / a_hw_i * 100.0
    return deltas_cov, deltas_sharp


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(subset=["mon_open", "fri_close", "regime_pub"]).reset_index(drop=True)
    panel_train = panel[panel["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    surface = cal.compute_calibration_surface(bounds_train)
    surface_pooled = cal.pooled_surface(bounds_train)
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)

    print(f"Train panel: {len(panel_train):,} rows × {panel_train['fri_ts'].nunique()} weekends "
          f"({panel_train['fri_ts'].min()} → {panel_train['fri_ts'].max()})")
    print(f"OOS panel:   {len(panel_oos):,} rows × {panel_oos['fri_ts'].nunique()} weekends "
          f"({panel_oos['fri_ts'].min()} → {panel_oos['fri_ts'].max()})")
    print()

    # 1. Calibrate global b(τ) on training, summarise both methods on OOS
    cal_rows = []
    pooled_rows = []
    by_regime_rows = []
    bootstrap_rows = []
    rng = np.random.default_rng(RNG_SEED)

    for tau in TARGETS:
        cal_info = calibrate_global_buffer(panel_train, tau)
        cal_rows.append(cal_info)
        b = cal_info["b"]
        print(f"τ={tau:.2f}: trained b(τ)={b:.4f} ({b*100:.2f}%), training realised {cal_info['realised_train']:.4f}")

        # Constant-buffer OOS
        served_cb = serve_constant_buffer(panel_oos, b)
        s_cb = pooled_summary(served_cb, tau)
        # Deployed Oracle OOS at the same τ
        served_or = serve_oracle(oracle, panel_oos, tau)
        s_or = pooled_summary(served_or, tau)

        deployed_buf = buffer_for_target(tau)
        pooled_rows.append({
            "target": tau, "method": "constant_buffer", "b_or_buffer": b,
            **s_cb,
        })
        pooled_rows.append({
            "target": tau, "method": "deployed_oracle", "b_or_buffer": deployed_buf,
            **s_or,
        })
        print(f"  CB:     n={s_cb['n']}, realised={s_cb['realised']:.4f}, "
              f"hw={s_cb['half_width_bps']:.1f}bps, p_uc={s_cb['p_uc']:.3f}, p_ind={s_cb['p_ind']:.3f}")
        print(f"  Oracle: n={s_or['n']}, realised={s_or['realised']:.4f}, "
              f"hw={s_or['half_width_bps']:.1f}bps, p_uc={s_or['p_uc']:.3f}, p_ind={s_or['p_ind']:.3f}")

        # Per-regime breakdown
        rb_cb = by_regime_summary(served_cb); rb_cb["method"] = "constant_buffer"; rb_cb["target"] = tau
        rb_or = by_regime_summary(served_or); rb_or["method"] = "deployed_oracle"; rb_or["target"] = tau
        by_regime_rows.append(rb_cb); by_regime_rows.append(rb_or)

        # Bootstrap: a = constant_buffer, b = deployed_oracle → δ = oracle − cb
        d_cov, d_sharp = block_bootstrap_delta(served_cb, served_or, rng)
        bootstrap_rows.append({
            "target": tau,
            "comparison": "deployed_oracle − constant_buffer (train-fit b)",
            "delta_cov_pp_mean": float(d_cov.mean()),
            "delta_cov_pp_lo": float(np.percentile(d_cov, 2.5)),
            "delta_cov_pp_hi": float(np.percentile(d_cov, 97.5)),
            "delta_sharp_pct_mean": float(d_sharp.mean()),
            "delta_sharp_pct_lo": float(np.percentile(d_sharp, 2.5)),
            "delta_sharp_pct_hi": float(np.percentile(d_sharp, 97.5)),
        })
        print(f"  Bootstrap Δcov = {d_cov.mean():+.2f}pp [{np.percentile(d_cov,2.5):+.2f}, {np.percentile(d_cov,97.5):+.2f}]; "
              f"Δsharp = {d_sharp.mean():+.1f}% [{np.percentile(d_sharp,2.5):+.1f}, {np.percentile(d_sharp,97.5):+.1f}]")

        # Coverage-matched: pick b on OOS to match the Oracle's realised coverage.
        # This is the headline width-at-coverage comparison.
        cm = coverage_matched_buffer(panel_oos, s_or["realised"])
        served_cb_match = serve_constant_buffer(panel_oos, cm["b"])
        s_cb_match = pooled_summary(served_cb_match, tau)
        pooled_rows.append({
            "target": tau, "method": "constant_buffer_coverage_matched",
            "b_or_buffer": cm["b"], **s_cb_match,
        })
        d_cov_m, d_sharp_m = block_bootstrap_delta(served_cb_match, served_or, rng)
        bootstrap_rows.append({
            "target": tau,
            "comparison": "deployed_oracle − constant_buffer (coverage-matched b)",
            "delta_cov_pp_mean": float(d_cov_m.mean()),
            "delta_cov_pp_lo": float(np.percentile(d_cov_m, 2.5)),
            "delta_cov_pp_hi": float(np.percentile(d_cov_m, 97.5)),
            "delta_sharp_pct_mean": float(d_sharp_m.mean()),
            "delta_sharp_pct_lo": float(np.percentile(d_sharp_m, 2.5)),
            "delta_sharp_pct_hi": float(np.percentile(d_sharp_m, 97.5)),
        })
        print(f"  Coverage-matched CB: b={cm['b']:.4f}, realised={s_cb_match['realised']:.4f}, "
              f"hw={s_cb_match['half_width_bps']:.1f}bps  →  "
              f"Oracle is {(s_or['half_width_bps']/s_cb_match['half_width_bps'] - 1)*100:+.1f}% of CB width "
              f"(Δsharp_oracle_minus_cb = {d_sharp_m.mean():+.1f}% [{np.percentile(d_sharp_m,2.5):+.1f}, {np.percentile(d_sharp_m,97.5):+.1f}])")
        # Per-regime breakdown for coverage-matched CB and Oracle
        rb_cm = by_regime_summary(served_cb_match); rb_cm["method"] = "constant_buffer_coverage_matched"; rb_cm["target"] = tau
        by_regime_rows.append(rb_cm)
        print()

    # Write tables
    out = REPORTS / "tables"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cal_rows).to_csv(out / "v1b_constant_buffer_calibration.csv", index=False)
    pd.DataFrame(pooled_rows).to_csv(out / "v1b_constant_buffer_oos.csv", index=False)
    pd.concat(by_regime_rows, ignore_index=True).to_csv(out / "v1b_constant_buffer_by_regime.csv", index=False)
    pd.DataFrame(bootstrap_rows).to_csv(out / "v1b_constant_buffer_bootstrap.csv", index=False)
    print(f"Wrote {out / 'v1b_constant_buffer_calibration.csv'}")
    print(f"Wrote {out / 'v1b_constant_buffer_oos.csv'}")
    print(f"Wrote {out / 'v1b_constant_buffer_by_regime.csv'}")
    print(f"Wrote {out / 'v1b_constant_buffer_bootstrap.csv'}")


if __name__ == "__main__":
    main()
