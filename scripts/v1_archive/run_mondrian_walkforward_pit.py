"""
M5 deployable Mondrian — walk-forward stability + Berkowitz/DQ tests.

Settles two open questions raised by the head-to-head Mondrian-vs-Oracle test:

  1. Walk-forward stability of c(τ). The full-OOS bump scalar fit (4 scalars,
     analog to Oracle's BUFFER_BY_TARGET) was fitted on the entire 2023+
     holdout. Does it survive a 6-split expanding-window walk-forward, the
     same protocol §6's abstract uses to ratify the Oracle's buffer schedule?

  2. Density-calibration tests. The Oracle's abstract notes that Berkowitz
     and Engle-Manganelli DQ both reject — the calibration claim is per-
     anchor, not full-distribution. Does M5 share that limitation, or does
     the cleaner per-regime quantile structure pass density tests too?

Procedure:

  Walk-forward. For each split f ∈ {0.20, 0.30, 0.40, 0.50, 0.60, 0.70} of
  the OOS weekend index:
    train: pre-2023 panel (fixed) → per-regime per-τ quantile b_r(τ)
    tune:  first f% of OOS weekends → fit c(τ) such that pooled tune
           coverage with b_r(τ)·c(τ) bands ≥ τ
    test:  remaining (1-f)% of OOS weekends → realised coverage
  Report cross-split mean and std of c(τ); cross-split mean test coverage.

  PIT / Berkowitz. Build a 19-anchor quantile grid τ ∈
    {0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.93,
     0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999}.
  For each anchor τ: per-regime training quantile + linearly-interpolated
  bump c(τ) (interpolating the M5 anchor bumps over τ). For each (symbol,
  fri_ts) on the OOS test slice, compute PIT via interpolation on the
  symmetric-band CDF. Run Berkowitz + DQ on τ=0.95.

Outputs:
  reports/tables/v1b_mondrian_walkforward.csv     per-split c(τ), test cov, n
  reports/tables/v1b_mondrian_density_tests.csv   Berkowitz + DQ summary
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95, 0.99)
DENSE_GRID = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85,
              0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999)
WALKFORWARD_FRACTIONS = (0.20, 0.30, 0.40, 0.50, 0.60, 0.70)
RNG_SEED = 20260502


def conformal_quantile_per_regime(panel_train: pd.DataFrame, point_col: str,
                                   tau_grid: tuple[float, ...]) -> pd.DataFrame:
    """Per-regime (1-α)(n+1)/n conformal quantiles of |residual|/fri_close at
    every τ in tau_grid. Long-form: regime_pub, target, b, n_train."""
    df = panel_train.copy()
    df["score"] = (df["mon_open"] - df[point_col]).abs() / df["fri_close"]
    df = df.dropna(subset=["score"])
    rows = []
    for regime, g in df.groupby("regime_pub"):
        n = len(g); scores = np.sort(g["score"].to_numpy())
        for tau in tau_grid:
            k = min(max(int(np.ceil(tau * (n + 1))), 1), n)
            rows.append({"regime_pub": regime, "target": tau,
                         "b": float(scores[k - 1]), "n_train": n})
    return pd.DataFrame(rows)


def fit_bump(panel_tune: pd.DataFrame, base_quantiles: pd.DataFrame,
             point_col: str, target: float, coverage_target: float | None = None) -> float:
    """Smallest c ∈ [1, 5] such that mean(score ≤ b_r(target)·c) ≥
    coverage_target on the tune slice. coverage_target defaults to `target`
    (vanilla fit). Pass coverage_target = target + delta to "shoot slightly
    high" — fit c so tune coverage ≥ target+δ rather than target exactly."""
    if coverage_target is None:
        coverage_target = target
    df = panel_tune.copy()
    df["score"] = (df["mon_open"] - df[point_col]).abs() / df["fri_close"]
    sub = base_quantiles[base_quantiles["target"] == target][["regime_pub", "b"]]
    merged = df.merge(sub, on="regime_pub", how="left").dropna(subset=["score", "b"])
    scores = merged["score"].to_numpy()
    b_arr = merged["b"].to_numpy()
    grid = np.arange(1.0, 5.0001, 0.001)
    for c in grid:
        if float(np.mean(scores <= b_arr * c)) >= coverage_target:
            return float(c)
    return float(grid[-1])


def walk_forward_m5(panel_train: pd.DataFrame, panel_oos: pd.DataFrame,
                     point_col: str = "point_fa", delta: float = 0.0) -> pd.DataFrame:
    """6-split expanding-window walk-forward, fitting c(τ) such that tune
    coverage ≥ τ+delta. delta is the "shoot-slightly-high" margin — a per-τ
    scalar absorbed into the deployment protocol so test-slice nonstationarity
    doesn't drop realised coverage below τ."""
    base = conformal_quantile_per_regime(panel_train, point_col, TARGETS)
    weekends = sorted(panel_oos["fri_ts"].unique())
    rows = []
    for f in WALKFORWARD_FRACTIONS:
        n_tune = max(int(round(len(weekends) * f)), 8)
        tune_ws = set(weekends[:n_tune])
        test_ws = set(weekends[n_tune:])
        panel_tune = panel_oos[panel_oos["fri_ts"].isin(tune_ws)].copy()
        panel_test = panel_oos[panel_oos["fri_ts"].isin(test_ws)].copy()
        for tau in TARGETS:
            cov_target = min(tau + delta, 0.999)
            c = fit_bump(panel_tune, base, point_col, target=tau, coverage_target=cov_target)
            sub = base[base["target"] == tau][["regime_pub", "b"]]
            test = panel_test.merge(sub, on="regime_pub", how="left")
            test["score"] = (test["mon_open"] - test[point_col]).abs() / test["fri_close"]
            test = test.dropna(subset=["score", "b"])
            test["b_eff"] = test["b"] * c
            inside = (test["score"] <= test["b_eff"]).astype(int)
            rows.append({
                "split_fraction": f,
                "n_tune_weekends": n_tune,
                "n_test_weekends": len(test_ws),
                "target": tau,
                "delta": delta,
                "bump_c": c,
                "n_test": int(inside.size),
                "test_realised": float(inside.mean()) if len(inside) else float("nan"),
                "test_half_width_bps_mean": float((test["b_eff"] * 1e4).mean()) if len(test) else float("nan"),
            })
    return pd.DataFrame(rows)


def walk_forward_oracle(panel_oos: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward of the deployed Oracle's per-target buffer schedule.
    Vectorised directly off `v1b_bounds.parquet` — no per-row Oracle.fair_value
    calls. The Oracle's hybrid policy maps regime → forecaster, then looks up
    the band at claimed = round_up(target + buffer) on a fixed grid. We
    pre-build the (symbol, fri_ts) → {claimed: (inside, half_width_bps)} table
    once, then sweep buffer per (split, τ) by table lookup."""
    REGIME_FC = {"normal": "F1_emp_regime", "long_weekend": "F1_emp_regime",
                 "high_vol": "F0_stale"}
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].copy()
    bounds_oos["fc_for_regime"] = bounds_oos["regime_pub"].map(REGIME_FC)
    bounds_oos = bounds_oos[bounds_oos["forecaster"] == bounds_oos["fc_for_regime"]].copy()
    bounds_oos["inside"] = ((bounds_oos["mon_open"] >= bounds_oos["lower"]) &
                              (bounds_oos["mon_open"] <= bounds_oos["upper"])).astype(int)
    bounds_oos["half_width_bps"] = ((bounds_oos["upper"] - bounds_oos["lower"]) /
                                     2.0 / bounds_oos["fri_close"] * 1e4)
    claimed_grid = sorted(bounds_oos["claimed"].unique())

    def claimed_for(target: float, buffer_value: float) -> float:
        eff = min(target + buffer_value, 0.999)
        higher = [c for c in claimed_grid if c >= eff - 1e-9]
        return higher[0] if higher else claimed_grid[-1]

    weekends = sorted(panel_oos["fri_ts"].unique())
    buffer_grid = np.round(np.arange(0.0, 0.10001, 0.005), 5)
    rows = []
    for f in WALKFORWARD_FRACTIONS:
        n_tune = max(int(round(len(weekends) * f)), 8)
        tune_ws = set(weekends[:n_tune]); test_ws = set(weekends[n_tune:])
        for tau in TARGETS:
            chosen = float(buffer_grid[-1])
            for b in buffer_grid:
                cl = claimed_for(tau, float(b))
                row_at = bounds_oos[(bounds_oos["claimed"].sub(cl).abs() < 1e-9) &
                                      bounds_oos["fri_ts"].isin(tune_ws)]
                if len(row_at) and float(row_at["inside"].mean()) >= tau:
                    chosen = float(b); break
            cl = claimed_for(tau, chosen)
            test = bounds_oos[(bounds_oos["claimed"].sub(cl).abs() < 1e-9) &
                                bounds_oos["fri_ts"].isin(test_ws)]
            rows.append({
                "split_fraction": f, "n_tune_weekends": n_tune,
                "n_test_weekends": len(test_ws), "target": tau,
                "buffer": chosen, "claimed_used": cl, "n_test": int(len(test)),
                "test_realised": float(test["inside"].mean()) if len(test) else float("nan"),
                "test_half_width_bps_mean": float(test["half_width_bps"].mean()) if len(test) else float("nan"),
            })
    return pd.DataFrame(rows)


def cross_split_oracle(wf: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tau, g in wf.groupby("target"):
        rows.append({
            "target": tau, "n_splits": len(g),
            "buffer_mean": float(g["buffer"].mean()),
            "buffer_std": float(g["buffer"].std(ddof=1)),
            "buffer_min": float(g["buffer"].min()),
            "buffer_max": float(g["buffer"].max()),
            "test_realised_mean": float(g["test_realised"].mean()),
            "test_realised_std": float(g["test_realised"].std(ddof=1)),
            "deficit_pp_mean": float((g["test_realised"] - tau).mean() * 100),
            "deficit_pp_max": float((g["test_realised"] - tau).min() * 100),
            "test_hw_mean": float(g["test_half_width_bps_mean"].mean()),
        })
    return pd.DataFrame(rows).sort_values("target")


def cross_split_summary(wf: pd.DataFrame) -> pd.DataFrame:
    """Per-τ cross-split summary: mean/std of c(τ), mean/std of test coverage."""
    rows = []
    for tau, g in wf.groupby("target"):
        rows.append({
            "target": tau,
            "n_splits": len(g),
            "c_mean": float(g["bump_c"].mean()),
            "c_std": float(g["bump_c"].std(ddof=1)),
            "c_min": float(g["bump_c"].min()),
            "c_max": float(g["bump_c"].max()),
            "test_realised_mean": float(g["test_realised"].mean()),
            "test_realised_std": float(g["test_realised"].std(ddof=1)),
            "deficit_pp_mean": float((g["test_realised"] - tau).mean() * 100),
            "deficit_pp_max": float((g["test_realised"] - tau).min() * 100),
        })
    return pd.DataFrame(rows).sort_values("target")


def density_tests_m5(panel_train: pd.DataFrame, panel_oos: pd.DataFrame,
                      point_col: str = "point_fa") -> dict:
    """Density-calibration tests on the full-OOS-fit M5.

    PIT construction: the Mondrian band is symmetric around point_fa with
    half-width b_r(τ)·c(τ)·fri_close. For each (symbol, fri_ts) and each
    τ in DENSE_GRID, the symmetric band [point - b_r·c·fri, point + b_r·c·fri]
    has interior probability τ. Equivalently, the absolute residual
    |mon_open - point|/fri_close has CDF F(b_r·c) ≈ τ. We construct the
    *full* CDF over the signed residual r = (mon - point)/fri:
       F(r) = 0.5 + 0.5·F_abs(|r|) · sign(r)
    where F_abs is interpolated on the (b_r·c, τ) anchors. PIT(realized) =
    F(realized) ∈ (0, 1).

    Berkowitz on PITs and DQ on τ=0.95 violations.
    """
    base = conformal_quantile_per_regime(panel_train, point_col, DENSE_GRID)
    # Fit per-τ bump scalar c(τ) on full OOS (M5's protocol)
    bump_by_tau = {}
    for tau in DENSE_GRID:
        bump_by_tau[tau] = fit_bump(panel_oos, base, point_col, tau)

    # For each row, build the per-regime quantile grid (b_r·c) at every τ.
    panel_oos = panel_oos.sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    grid_taus = np.array(sorted(DENSE_GRID))
    pits = []
    violations_95 = []
    for _, row in panel_oos.iterrows():
        regime = row["regime_pub"]
        b_anchors = []
        for tau in grid_taus:
            sub = base[(base["regime_pub"] == regime) & (base["target"] == float(tau))]
            if sub.empty:
                b_anchors.append(np.nan)
            else:
                b_anchors.append(float(sub["b"].iloc[0]) * bump_by_tau[float(tau)])
        b_anchors = np.array(b_anchors)
        if not np.all(np.isfinite(b_anchors)):
            pits.append(np.nan); continue
        r = (row["mon_open"] - row[point_col]) / row["fri_close"]
        # Build the full signed-residual CDF: at +b_anchor, F = 0.5 + 0.5·τ;
        # at −b_anchor, F = 0.5 − 0.5·τ. The mapping from |r| to τ:
        #   |r| = 0 → τ = 0
        #   |r| = b_anchor[k] → τ = grid_taus[k]
        # interp τ from |r|, then F = 0.5 + 0.5·τ·sign(r).
        abs_r = abs(float(r))
        # Anchor sequence has b at τ=grid_taus, with τ=0 implicitly at b=0.
        anchor_b = np.concatenate(([0.0], b_anchors))
        anchor_tau = np.concatenate(([0.0], grid_taus))
        if abs_r >= anchor_b[-1]:
            tau_hat = anchor_tau[-1]
        else:
            tau_hat = float(np.interp(abs_r, anchor_b, anchor_tau))
        pit = 0.5 + 0.5 * tau_hat * (1 if r >= 0 else -1)
        pits.append(pit)
        # τ=0.95 violation indicator: |r| > b_r(0.95)·c(0.95)
        b_95 = float(base[(base["regime_pub"] == regime) & (base["target"] == 0.95)]["b"].iloc[0])
        c_95 = bump_by_tau[0.95]
        violations_95.append(int(abs_r > b_95 * c_95))

    pits = np.array(pits, dtype=float)
    pits = pits[np.isfinite(pits)]
    bw = met.berkowitz_test(pits)
    dq = met.dynamic_quantile_test(np.array(violations_95), claimed=0.95, n_lags=4)
    return {"berkowitz": bw, "dq_95": dq, "pit_n": int(len(pits)),
            "viol_95_n": int(sum(violations_95)),
            "viol_95_rate": float(np.mean(violations_95))}


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(subset=["mon_open", "fri_close", "regime_pub"]).reset_index(drop=True)
    panel["point_fa"] = panel["fri_close"].astype(float) * (1.0 + panel["factor_ret"].astype(float))
    panel_train = panel[panel["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    print(f"Train panel: {len(panel_train):,} rows × {panel_train['fri_ts'].nunique()} weekends")
    print(f"OOS panel:   {len(panel_oos):,} rows × {panel_oos['fri_ts'].nunique()} weekends")
    print()

    # Walk-forward — M5
    print("[1a/3] 6-split expanding-window walk-forward on M5 c(τ)…")
    wf = walk_forward_m5(panel_train, panel_oos, point_col="point_fa")
    summ = cross_split_summary(wf)
    print()
    print("M5 cross-split summary (mean/std of c(τ) per τ; test-slice realised coverage; mean test half-width):")
    summ_m5_aug = summ.copy()
    summ_m5_aug["test_hw_mean"] = wf.groupby("target")["test_half_width_bps_mean"].mean().values
    print(summ_m5_aug.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()

    # Walk-forward — deployed Oracle
    print("[1b/3] 6-split expanding-window walk-forward on deployed Oracle buffer schedule…")
    wf_oracle = walk_forward_oracle(panel_oos)
    summ_oracle = cross_split_oracle(wf_oracle)
    print()
    print("Oracle cross-split summary (mean/std of buffer per τ; test-slice realised coverage; mean test half-width):")
    print(summ_oracle.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()
    print("Per-split c(τ) and test coverage (every row):")
    print(wf[["split_fraction", "n_tune_weekends", "n_test_weekends", "target",
              "bump_c", "test_realised", "test_half_width_bps_mean"]].to_string(
        index=False, float_format=lambda x: f"{x:.4f}"))
    print()

    # Density tests
    print("[2/3] Density-calibration tests (Berkowitz, DQ at τ=0.95)…")
    dens = density_tests_m5(panel_train, panel_oos, point_col="point_fa")
    print()
    print("Berkowitz on PITs from 19-anchor M5:")
    print(f"  n        = {dens['pit_n']}")
    print(f"  LR       = {dens['berkowitz']['lr']:.4f}")
    print(f"  p-value  = {dens['berkowitz']['p_value']:.4f}")
    print(f"  rho_hat  = {dens['berkowitz'].get('rho_hat', float('nan')):.4f}")
    print(f"  mean(z)  = {dens['berkowitz'].get('mean_z', float('nan')):.4f}")
    print(f"  var(z)   = {dens['berkowitz'].get('var_z', float('nan')):.4f}")
    print()
    print("Dynamic Quantile (Engle-Manganelli) at τ=0.95, n_lags=4:")
    print(f"  violations = {dens['viol_95_n']} of {dens['pit_n']} ({dens['viol_95_rate']*100:.2f}%, expected 5%)")
    print(f"  DQ         = {dens['dq_95']['dq']:.4f}")
    print(f"  p-value    = {dens['dq_95']['p_value']:.4f}")
    print(f"  df         = {dens['dq_95']['df']}")
    print()

    out = REPORTS / "tables"
    out.mkdir(parents=True, exist_ok=True)
    wf.to_csv(out / "v1b_mondrian_walkforward.csv", index=False)
    summ.to_csv(out / "v1b_mondrian_walkforward_summary.csv", index=False)
    wf_oracle.to_csv(out / "v1b_oracle_walkforward.csv", index=False)
    summ_oracle.to_csv(out / "v1b_oracle_walkforward_summary.csv", index=False)
    pd.DataFrame([{
        "test": "berkowitz",
        "n": dens["pit_n"],
        "stat": dens["berkowitz"]["lr"],
        "p_value": dens["berkowitz"]["p_value"],
        **{k: v for k, v in dens["berkowitz"].items() if k not in ("lr", "p_value", "n")},
    }, {
        "test": "dq_95",
        "n": dens["pit_n"],
        "stat": dens["dq_95"]["dq"],
        "p_value": dens["dq_95"]["p_value"],
        "df": dens["dq_95"]["df"],
        "viol_n": dens["viol_95_n"],
        "viol_rate": dens["viol_95_rate"],
    }]).to_csv(out / "v1b_mondrian_density_tests.csv", index=False)
    print(f"Wrote {out / 'v1b_mondrian_walkforward.csv'}")
    print(f"Wrote {out / 'v1b_mondrian_walkforward_summary.csv'}")
    print(f"Wrote {out / 'v1b_mondrian_density_tests.csv'}")


if __name__ == "__main__":
    main()
