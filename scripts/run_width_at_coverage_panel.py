"""
Width-at-coverage panel — Paper 1 §7 honest comparator headline.

Motivation. Paper 1's existing headline pairs (Pyth conf 0/8) with (Soothsayer
τ=0.85 8/8) on benign weekends. That comparator is true but uses Pyth's raw
publisher-dispersion confidence — nobody actually deploys that for Monday-open
coverage. The comparator a Kamino-style risk committee would deploy if forced
to pick one number is `Pyth + b%`, with b ∈ {2, 5, 10}. The honest question is:
at matched realised coverage τ, how much narrower is the deployed Oracle than
a one-parameter constant-buffer or VIX-scaled baseline, and what does the
Winkler interval score say about each method's full sharpness × penalty
trade-off?

What this produces.
  reports/tables/v1b_width_at_coverage_pooled.csv     pooled OOS per (method, τ)
  reports/tables/v1b_width_at_coverage_by_regime.csv  per-regime breakdown
  reports/tables/v1b_width_at_coverage_fixed.csv      Pyth+{2,5,10}% fixed-width rows
  reports/tables/v1b_width_at_coverage_bootstrap.csv  block-bootstrap CIs

Methods.
  fixed_pyth_2 / 5 / 10           Friday close ± {0.02, 0.05, 0.10}; not τ-conditional.
                                  Reported with the realised coverage they happen to
                                  hit, the mean half-width, and the Winkler score
                                  evaluated at each τ ∈ {0.68, 0.85, 0.95, 0.99}.
  empirical_const_buffer          Smallest pooled symmetric multiplicative buffer b(τ)
                                  s.t. training coverage of [fri_close·(1−b),
                                  fri_close·(1+b)] ≥ τ. Globally pooled across symbols
                                  and regimes — no per-(symbol, regime) tuning.
                                  This is the parameter-frugal floor: 4 params total,
                                  one per τ.
  vix_scaled                      b(τ, t) = c(τ) · vix_fri_close[t] / vix_median(train),
                                  with c(τ) the smallest constant satisfying training
                                  pooled coverage ≥ τ. One additional knob per τ over
                                  empirical_const_buffer; uses a public market signal
                                  for regime conditioning.
  deployed_oracle                 The deployed Soothsayer Oracle (factor-switchboard
                                  point + empirical residual quantile + log-log VIX
                                  regression + per-regime hybrid forecaster + per-target
                                  empirical buffer schedule). Calibration surface fit
                                  on pre-2023 panel and held fixed for OOS serving.

Winkler interval score (Gneiting & Raftery 2007, eq. 43). For a (1−α) prediction
interval [L, U] given realised y, W_α(L, U; y) = (U − L) + (2/α)·max(L−y, 0) +
(2/α)·max(y−U, 0); α = 1 − τ. We report W in basis points (relative to fri_close)
so methods are comparable across symbols.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95, 0.99)
FIXED_PYTH_BUFFERS = (0.02, 0.05, 0.10)
N_BOOTSTRAP = 1000
RNG_SEED = 20260502
B_GRID = np.arange(0.0, 0.50001, 0.0001)
C_GRID = np.arange(0.0, 0.50001, 0.0001)  # VIX-multiplier grid (relative-VIX units)


# ---------------------------------------------------------------------------
# Method calibrators
# ---------------------------------------------------------------------------

def calibrate_const_buffer(panel_train: pd.DataFrame, target: float) -> float:
    """Smallest b s.t. pooled |Mon−Fri|/Fri ≤ b on ≥ τ of training rows."""
    fri = panel_train["fri_close"].astype(float).values
    mon = panel_train["mon_open"].astype(float).values
    valid = np.isfinite(fri) & np.isfinite(mon) & (fri > 0)
    rel_dev = np.abs(mon[valid] - fri[valid]) / fri[valid]
    b_emp = float(np.quantile(rel_dev, target, method="higher"))
    return float(B_GRID[B_GRID >= b_emp][0]) if (B_GRID >= b_emp).any() else float(B_GRID[-1])


def calibrate_vix_scaled(panel_train: pd.DataFrame, target: float) -> tuple[float, float]:
    """Smallest c s.t. pooled empirical coverage of [fri_close·(1 − c·v_t/v̄),
    fri_close·(1 + c·v_t/v̄)] ≥ τ on training, with v̄ = median VIX on training.

    Returns (c, v_median).
    """
    df = panel_train.dropna(subset=["fri_close", "mon_open", "vix_fri_close"]).copy()
    fri = df["fri_close"].astype(float).values
    mon = df["mon_open"].astype(float).values
    vix = df["vix_fri_close"].astype(float).values
    v_median = float(np.median(vix))
    rel_dev_scaled = (np.abs(mon - fri) / fri) / (vix / v_median)
    c_emp = float(np.quantile(rel_dev_scaled, target, method="higher"))
    c = float(C_GRID[C_GRID >= c_emp][0]) if (C_GRID >= c_emp).any() else float(C_GRID[-1])
    return c, v_median


# ---------------------------------------------------------------------------
# Servers — produce per-row (lower, upper, half_width_bps, inside)
# ---------------------------------------------------------------------------

def _per_row(panel: pd.DataFrame, lower: np.ndarray, upper: np.ndarray) -> pd.DataFrame:
    df = panel[["symbol", "fri_ts", "regime_pub", "fri_close", "mon_open"]].copy()
    df["lower"] = lower
    df["upper"] = upper
    df["half_width_bps"] = (upper - lower) / 2.0 / df["fri_close"].astype(float).values * 1e4
    df["inside"] = ((df["mon_open"].astype(float).values >= lower) &
                    (df["mon_open"].astype(float).values <= upper)).astype(int)
    return df


def serve_const_buffer(panel: pd.DataFrame, b: float) -> pd.DataFrame:
    fri = panel["fri_close"].astype(float).values
    return _per_row(panel, fri * (1.0 - b), fri * (1.0 + b))


def serve_vix_scaled(panel: pd.DataFrame, c: float, v_median: float) -> pd.DataFrame:
    df = panel.dropna(subset=["fri_close", "mon_open", "vix_fri_close"]).reset_index(drop=True)
    fri = df["fri_close"].astype(float).values
    vix = df["vix_fri_close"].astype(float).values
    b_t = c * (vix / v_median)
    return _per_row(df, fri * (1.0 - b_t), fri * (1.0 + b_t))


def serve_oracle(oracle: Oracle, panel: pd.DataFrame, target: float) -> pd.DataFrame:
    rows = []
    for _, w in panel.iterrows():
        try:
            pp = oracle.fair_value(w["symbol"], w["fri_ts"], target_coverage=target)
        except (ValueError, KeyError):
            continue
        rows.append({
            "symbol": w["symbol"],
            "fri_ts": w["fri_ts"],
            "regime_pub": w["regime_pub"],
            "fri_close": float(w["fri_close"]),
            "mon_open": float(w["mon_open"]),
            "lower": float(pp.lower),
            "upper": float(pp.upper),
            "half_width_bps": float(pp.half_width_bps),
            "inside": int((w["mon_open"] >= pp.lower) and (w["mon_open"] <= pp.upper)),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def winkler_bps(served: pd.DataFrame, target: float) -> float:
    """Mean Winkler interval score (bps) at target τ. Lower is better."""
    alpha = 1.0 - target
    fri = served["fri_close"].astype(float).values
    lo = served["lower"].astype(float).values
    hi = served["upper"].astype(float).values
    y = served["mon_open"].astype(float).values
    width = hi - lo
    under = np.maximum(lo - y, 0.0)
    over = np.maximum(y - hi, 0.0)
    w_price = width + (2.0 / alpha) * (under + over)
    return float(np.mean(w_price / fri) * 1e4)


def pooled_summary(served: pd.DataFrame, target: float) -> dict:
    n = len(served)
    realised = float(served["inside"].mean())
    half = float(served["half_width_bps"].mean())
    wk = winkler_bps(served, target)
    v = (~served["inside"].astype(bool)).astype(int).values
    lr_uc, p_uc = met._lr_kupiec(v, target)
    lr_ind_total = 0.0
    n_groups = 0
    for _, g in served.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
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
        "winkler_bps": wk,
        "lr_uc": float(lr_uc),
        "p_uc": float(p_uc),
        "lr_ind": float(lr_ind_total),
        "p_ind": p_ind,
    }


def by_regime_summary(served: pd.DataFrame, target: float) -> pd.DataFrame:
    rows = []
    for regime, g in served.groupby("regime_pub"):
        rows.append({
            "regime_pub": regime,
            "n": len(g),
            "realised": float(g["inside"].mean()),
            "half_width_bps": float(g["half_width_bps"].mean()),
            "winkler_bps": winkler_bps(g, target),
        })
    return pd.DataFrame(rows).sort_values("regime_pub").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Bootstrap — Δ vs deployed Oracle, by weekend
# ---------------------------------------------------------------------------

def block_bootstrap_delta(method_served: pd.DataFrame, oracle_served: pd.DataFrame,
                          target: float, rng: np.random.Generator,
                          n_resamples: int = N_BOOTSTRAP) -> dict:
    """Per-weekend bootstrap of (Δcoverage pp, Δsharpness%, ΔWinkler%) for
    method vs deployed Oracle. Δ is method − oracle (positive Δsharpness% means
    method is wider; positive ΔWinkler means method is worse).
    """
    weekends = sorted(set(method_served["fri_ts"]).intersection(set(oracle_served["fri_ts"])))
    m_by_w = method_served.set_index(["fri_ts", "symbol"]).sort_index()
    o_by_w = oracle_served.set_index(["fri_ts", "symbol"]).sort_index()
    deltas_cov = []
    deltas_sharp = []
    deltas_winkler = []
    alpha = 1.0 - target
    for _ in range(n_resamples):
        idx = rng.choice(len(weekends), size=len(weekends), replace=True)
        sample = [weekends[i] for i in idx]
        m_inside, o_inside = [], []
        m_hw, o_hw = [], []
        m_wk, o_wk = [], []
        for w in sample:
            try:
                mr = m_by_w.loc[w]; or_ = o_by_w.loc[w]
            except KeyError:
                continue
            if isinstance(mr, pd.Series):
                mr = mr.to_frame().T
            if isinstance(or_, pd.Series):
                or_ = or_.to_frame().T
            common = mr.index.intersection(or_.index)
            if len(common) == 0:
                continue
            mr = mr.loc[common]; or_ = or_.loc[common]
            m_inside.extend(mr["inside"].tolist()); o_inside.extend(or_["inside"].tolist())
            m_hw.extend(mr["half_width_bps"].tolist()); o_hw.extend(or_["half_width_bps"].tolist())
            for r in mr.itertuples():
                under = max(r.lower - r.mon_open, 0.0); over = max(r.mon_open - r.upper, 0.0)
                m_wk.append(((r.upper - r.lower) + (2.0 / alpha) * (under + over)) / r.fri_close * 1e4)
            for r in or_.itertuples():
                under = max(r.lower - r.mon_open, 0.0); over = max(r.mon_open - r.upper, 0.0)
                o_wk.append(((r.upper - r.lower) + (2.0 / alpha) * (under + over)) / r.fri_close * 1e4)
        if not m_inside or not o_inside:
            continue
        deltas_cov.append((np.mean(m_inside) - np.mean(o_inside)) * 100.0)
        deltas_sharp.append((np.mean(m_hw) - np.mean(o_hw)) / np.mean(o_hw) * 100.0)
        deltas_winkler.append((np.mean(m_wk) - np.mean(o_wk)) / np.mean(o_wk) * 100.0)
    def _stats(arr):
        a = np.array(arr)
        return float(a.mean()), float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))
    cov_m, cov_lo, cov_hi = _stats(deltas_cov)
    sh_m, sh_lo, sh_hi = _stats(deltas_sharp)
    wk_m, wk_lo, wk_hi = _stats(deltas_winkler)
    return {
        "delta_cov_pp_mean": cov_m, "delta_cov_pp_lo": cov_lo, "delta_cov_pp_hi": cov_hi,
        "delta_sharp_pct_mean": sh_m, "delta_sharp_pct_lo": sh_lo, "delta_sharp_pct_hi": sh_hi,
        "delta_winkler_pct_mean": wk_m, "delta_winkler_pct_lo": wk_lo, "delta_winkler_pct_hi": wk_hi,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(subset=["mon_open", "fri_close", "regime_pub"]).reset_index(drop=True)
    panel_train = panel[panel["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    surface = cal.compute_calibration_surface(bounds_train)
    surface_pooled = cal.pooled_surface(bounds_train)
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)

    print(f"Train: {len(panel_train):,} rows × {panel_train['fri_ts'].nunique()} weekends "
          f"({panel_train['fri_ts'].min()} → {panel_train['fri_ts'].max()})")
    print(f"OOS:   {len(panel_oos):,} rows × {panel_oos['fri_ts'].nunique()} weekends "
          f"({panel_oos['fri_ts'].min()} → {panel_oos['fri_ts'].max()})")
    print()

    rng = np.random.default_rng(RNG_SEED)
    pooled_rows = []
    by_regime_rows = []
    bootstrap_rows = []
    fixed_rows = []

    # -- 1. Calibrated comparators × τ ----------------------------------------
    served_oracle_cache: dict[float, pd.DataFrame] = {}
    for tau in TARGETS:
        b_const = calibrate_const_buffer(panel_train, tau)
        c_vix, v_med = calibrate_vix_scaled(panel_train, tau)
        print(f"τ={tau:.2f}  const_b={b_const:.4f} ({b_const*1e4:.1f}bps)  "
              f"vix c={c_vix:.4f} (v̄={v_med:.2f})")

        served_const = serve_const_buffer(panel_oos, b_const)
        served_vix = serve_vix_scaled(panel_oos, c_vix, v_med)
        served_or = serve_oracle(oracle, panel_oos, tau)
        served_oracle_cache[tau] = served_or

        for name, served in [("empirical_const_buffer", served_const),
                             ("vix_scaled", served_vix),
                             ("deployed_oracle", served_or)]:
            s = pooled_summary(served, tau)
            pooled_rows.append({"target": tau, "method": name, **s})
            r = by_regime_summary(served, tau)
            r["method"] = name; r["target"] = tau
            by_regime_rows.append(r)

        for name, served in [("empirical_const_buffer", served_const),
                             ("vix_scaled", served_vix)]:
            d = block_bootstrap_delta(served, served_or, tau, rng)
            bootstrap_rows.append({"target": tau, "method": name,
                                   "comparison": f"{name} − deployed_oracle", **d})

        # Inline summary
        print(f"  const : realised={pooled_rows[-3]['realised']:.4f}, "
              f"hw={pooled_rows[-3]['half_width_bps']:.1f}bps, "
              f"W={pooled_rows[-3]['winkler_bps']:.1f}bps, p_uc={pooled_rows[-3]['p_uc']:.3f}")
        print(f"  vix   : realised={pooled_rows[-2]['realised']:.4f}, "
              f"hw={pooled_rows[-2]['half_width_bps']:.1f}bps, "
              f"W={pooled_rows[-2]['winkler_bps']:.1f}bps, p_uc={pooled_rows[-2]['p_uc']:.3f}")
        print(f"  oracle: realised={pooled_rows[-1]['realised']:.4f}, "
              f"hw={pooled_rows[-1]['half_width_bps']:.1f}bps, "
              f"W={pooled_rows[-1]['winkler_bps']:.1f}bps, p_uc={pooled_rows[-1]['p_uc']:.3f}")
        print()

    # -- 2. Fixed Pyth+b table ------------------------------------------------
    print("Fixed Pyth+b (not τ-conditional; Winkler reported per τ):")
    for b in FIXED_PYTH_BUFFERS:
        served = serve_const_buffer(panel_oos, b)
        n = len(served)
        realised = float(served["inside"].mean())
        hw = float(served["half_width_bps"].mean())
        v = (~served["inside"].astype(bool)).astype(int).values
        # Regime breakdown (one row per regime per b)
        for tau in TARGETS:
            wk = winkler_bps(served, tau)
            lr_uc, p_uc = met._lr_kupiec(v, tau)
            fixed_rows.append({
                "method": f"fixed_pyth_{int(b*100)}pct",
                "b": b,
                "target_for_winkler": tau,
                "n": n,
                "realised": realised,
                "half_width_bps": hw,
                "winkler_bps": wk,
                "p_uc_at_tau": float(p_uc),
            })
        print(f"  +{b*100:.0f}%: realised={realised:.4f}, hw={hw:.1f}bps")

    # Per-regime breakdown for fixed (only one b → one set of rows; informative
    # to show high_vol regime alone)
    fixed_regime_rows = []
    for b in FIXED_PYTH_BUFFERS:
        served = serve_const_buffer(panel_oos, b)
        for regime, g in served.groupby("regime_pub"):
            for tau in TARGETS:
                fixed_regime_rows.append({
                    "method": f"fixed_pyth_{int(b*100)}pct",
                    "b": b,
                    "regime_pub": regime,
                    "target_for_winkler": tau,
                    "n": len(g),
                    "realised": float(g["inside"].mean()),
                    "half_width_bps": float(g["half_width_bps"].mean()),
                    "winkler_bps": winkler_bps(g, tau),
                })

    # -- 3. Persist tables ----------------------------------------------------
    out = REPORTS / "tables"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(pooled_rows).to_csv(out / "v1b_width_at_coverage_pooled.csv", index=False)
    pd.concat(by_regime_rows, ignore_index=True).to_csv(
        out / "v1b_width_at_coverage_by_regime.csv", index=False)
    pd.DataFrame(fixed_rows).to_csv(out / "v1b_width_at_coverage_fixed.csv", index=False)
    pd.DataFrame(fixed_regime_rows).to_csv(out / "v1b_width_at_coverage_fixed_by_regime.csv", index=False)
    pd.DataFrame(bootstrap_rows).to_csv(out / "v1b_width_at_coverage_bootstrap.csv", index=False)
    print(f"Wrote {out / 'v1b_width_at_coverage_pooled.csv'}")
    print(f"Wrote {out / 'v1b_width_at_coverage_by_regime.csv'}")
    print(f"Wrote {out / 'v1b_width_at_coverage_fixed.csv'}")
    print(f"Wrote {out / 'v1b_width_at_coverage_fixed_by_regime.csv'}")
    print(f"Wrote {out / 'v1b_width_at_coverage_bootstrap.csv'}")

    # -- 4. Headline matrix in console ----------------------------------------
    print()
    print("=" * 88)
    print("HEADLINE: width-at-coverage on OOS 2023+ panel")
    print("=" * 88)
    print(f"{'method':<28} {'τ':>5} {'realised':>9} {'hw_bps':>9} {'Winkler':>9} "
          f"{'p_uc':>6} {'p_ind':>6}")
    for r in pooled_rows:
        print(f"{r['method']:<28} {r['target']:>5.2f} {r['realised']:>9.4f} "
              f"{r['half_width_bps']:>9.1f} {r['winkler_bps']:>9.1f} "
              f"{r['p_uc']:>6.3f} {r['p_ind']:>6.3f}")
    print()
    print("Bootstrap: method − deployed_oracle (negative Δsharp/ΔWinkler = method better)")
    print(f"{'τ':>5} {'method':<26} {'Δcov pp':>15} {'Δsharp %':>17} {'ΔWinkler %':>17}")
    for r in bootstrap_rows:
        print(f"{r['target']:>5.2f} {r['method']:<26} "
              f"{r['delta_cov_pp_mean']:>+6.2f} [{r['delta_cov_pp_lo']:>+5.2f},{r['delta_cov_pp_hi']:>+5.2f}] "
              f"{r['delta_sharp_pct_mean']:>+6.1f} [{r['delta_sharp_pct_lo']:>+5.1f},{r['delta_sharp_pct_hi']:>+5.1f}] "
              f"{r['delta_winkler_pct_mean']:>+6.1f} [{r['delta_winkler_pct_lo']:>+5.1f},{r['delta_winkler_pct_hi']:>+5.1f}]")


if __name__ == "__main__":
    main()
