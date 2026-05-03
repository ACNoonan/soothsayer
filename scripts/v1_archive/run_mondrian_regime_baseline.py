"""
Mondrian split-conformal by regime — head-to-head against the deployed Oracle.

The §7.6 finding was that the Oracle is 11–12% wider than a coverage-matched
constant buffer at τ ≤ 0.95, with the entire pooled width premium living in
the high_vol regime. The natural competing question: does a *deployable*
Mondrian split-conformal scheme — partition training by regime, take the
per-regime empirical quantile, look up at serving time — get the same OOS
calibration as the Oracle at narrower width? If yes, the factor switchboard +
empirical residual quantile + log-log VIX + earnings/long-weekend regressors
+ per-target buffer schedule are all over-engineering relative to a 3-row
lookup table.

Mondrian taxonomy: regime_pub ∈ {normal, long_weekend, high_vol}.
Conformity score: |mon_open − point| / fri_close (relative absolute residual).
Calibration set: pre-2023 training panel (2014-01-17 → 2022-12-30,
N ≈ 3000 normal, 900 high_vol, 400 long_weekend obs).
Conformal correction: (1−α)(n+1)/n quantile of the calibration scores per
regime — the standard split-CP finite-sample adjustment.

Variants:
  M1  Mondrian by regime, stale-point center (Pyth/Chainlink Friday close)
  M2  Mondrian by regime, factor-adjusted-point center (the Oracle's point)
  M3  Mondrian by (symbol, regime), stale-point — finer Mondrian split

Comparison cells (all on the same OOS panel as §7.4 / §7.6):
  C_M_oracle   deployed Oracle (cell C4 of §7.4)
  C_M_M1       Mondrian-by-regime, stale-point
  C_M_M2       Mondrian-by-regime, factor-adjusted-point
  C_M_M3       Mondrian-by-(symbol, regime), stale-point

Outputs:
  reports/tables/v1b_mondrian_calibration.csv  trained b per (regime, τ)
  reports/tables/v1b_mondrian_oos.csv          pooled OOS metrics per method × τ
  reports/tables/v1b_mondrian_by_regime.csv    per-regime OOS metrics
  reports/tables/v1b_mondrian_bootstrap.csv    bootstrap deltas vs Oracle
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
N_BOOTSTRAP = 1000
RNG_SEED = 20260502
REGIMES = ("normal", "long_weekend", "high_vol")


def calibrate_mondrian_deployable(panel_train: pd.DataFrame, panel_oos: pd.DataFrame,
                                    point_col: str, group_cols: tuple[str, ...]) -> pd.DataFrame:
    """Train-fit Mondrian + single OOS scalar bump c(τ) per target.

    Procedure:
      1. Train: per-(group, τ), compute conformal (1−α)(n+1)/n quantile of
         |residual|/fri_close. This is M2's output.
      2. OOS-tune: per τ, pick the smallest c(τ) ∈ [1, 5] such that pooled OOS
         coverage with b_g(τ)·c(τ) bands ≥ τ. One scalar per τ — 4 total OOS-
         fitted parameters, matching the Oracle's BUFFER_BY_TARGET schedule.

    Returns the same long-form table as `calibrate_mondrian` but with `b`
    column = b_train × c(τ). Same lookup interface as M1/M2/M3/M4.
    """
    base = calibrate_mondrian(panel_train, point_col, group_cols)
    base_pivot = base.pivot_table(index=list(group_cols), columns="target", values="b").reset_index()

    df_oos = panel_oos.copy()
    df_oos["score"] = (df_oos["mon_open"] - df_oos[point_col]).abs() / df_oos["fri_close"]
    df_oos = df_oos.dropna(subset=["score"]).reset_index(drop=True)
    merged = df_oos.merge(base_pivot, on=list(group_cols), how="left")

    bumped_rows = []
    c_grid = np.arange(1.0, 5.0001, 0.001)
    for tau in TARGETS:
        b_for_tau = merged[tau].to_numpy()
        scores = merged["score"].to_numpy()
        valid = np.isfinite(b_for_tau) & np.isfinite(scores)
        b_for_tau = b_for_tau[valid]; scores = scores[valid]
        # Find smallest c with mean(score ≤ b·c) ≥ tau
        chosen_c = c_grid[-1]
        for c in c_grid:
            cov = float(np.mean(scores <= b_for_tau * c))
            if cov >= tau:
                chosen_c = float(c); break
        # Apply bump
        for _, row in base[base["target"] == tau].iterrows():
            r = row.to_dict()
            r["b"] = float(r["b"] * chosen_c)
            r["bump_c"] = chosen_c
            bumped_rows.append(r)
    return pd.DataFrame(bumped_rows)


def calibrate_mondrian_oos_fit(panel_oos: pd.DataFrame, point_col: str,
                                group_cols: tuple[str, ...]) -> pd.DataFrame:
    """The per-(group, τ) empirical quantile fit *on OOS itself* — the best-case
    width for Mondrian, analog of §7.6.3's coverage-matched constant buffer.
    Not deployable; bounds the achievable width at calibrated per-group coverage."""
    df = panel_oos.copy()
    df["score"] = (df["mon_open"] - df[point_col]).abs() / df["fri_close"]
    df = df.dropna(subset=["score"]).reset_index(drop=True)
    rows = []
    for keys, g in df.groupby(list(group_cols)):
        if not isinstance(keys, tuple):
            keys = (keys,)
        n = len(g)
        if n < 5:
            continue
        for tau in TARGETS:
            b = float(np.quantile(g["score"].to_numpy(), tau, method="higher"))
            row = dict(zip(group_cols, keys))
            row.update({"target": tau, "b": b, "n_train": n})
            rows.append(row)
    return pd.DataFrame(rows)


def calibrate_mondrian(panel_train: pd.DataFrame, point_col: str,
                        group_cols: tuple[str, ...]) -> pd.DataFrame:
    """For each (group, τ) pair, compute the conformal (1−α)(n+1)/n quantile
    of |mon_open − point| / fri_close on the training panel.

    Returns long-form DataFrame: group_cols + ['target', 'b', 'n_train']."""
    df = panel_train.copy()
    df["score"] = (df["mon_open"] - df[point_col]).abs() / df["fri_close"]
    df = df.dropna(subset=["score"]).reset_index(drop=True)
    rows = []
    for keys, g in df.groupby(list(group_cols)):
        if not isinstance(keys, tuple):
            keys = (keys,)
        n = len(g)
        if n < 5:
            continue
        scores = g["score"].to_numpy()
        for tau in TARGETS:
            # Standard split-CP finite-sample correction:
            # rank k = ceil((1-α)(n+1)) where α = 1-τ. b = score at rank k.
            k = int(np.ceil((tau) * (n + 1)))
            k = min(max(k, 1), n)
            b = float(np.sort(scores)[k - 1])
            row = dict(zip(group_cols, keys))
            row.update({"target": tau, "b": b, "n_train": n})
            rows.append(row)
    return pd.DataFrame(rows)


def _mondrian_lookup(cal_df: pd.DataFrame, group_cols: tuple[str, ...],
                     panel_oos: pd.DataFrame, target: float) -> pd.Series:
    """Join the trained quantile table to OOS rows by group_cols."""
    sub = cal_df[cal_df["target"] == target][list(group_cols) + ["b"]]
    merged = panel_oos[list(group_cols)].merge(sub, on=list(group_cols), how="left")
    return merged["b"].values  # NaN where the group didn't appear in training


def serve_mondrian(panel_oos: pd.DataFrame, cal_df: pd.DataFrame,
                   point_col: str, group_cols: tuple[str, ...], target: float) -> pd.DataFrame:
    df = panel_oos[["symbol", "fri_ts", "regime_pub", "fri_close", "mon_open", point_col]].copy()
    df["b"] = _mondrian_lookup(cal_df, group_cols, panel_oos, target)
    valid = df["b"].notna() & df["mon_open"].notna() & df["fri_close"].notna()
    df = df.loc[valid].reset_index(drop=True)
    df["lower"] = df[point_col] - df["b"] * df["fri_close"]
    df["upper"] = df[point_col] + df["b"] * df["fri_close"]
    df["half_width_bps"] = df["b"] * 1e4
    df["inside"] = ((df["mon_open"] >= df["lower"]) & (df["mon_open"] <= df["upper"])).astype(int)
    return df


def serve_oracle(oracle: Oracle, panel_oos: pd.DataFrame, target: float) -> pd.DataFrame:
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
    n = len(served)
    realised = float(served["inside"].mean()) if n else float("nan")
    half = float(served["half_width_bps"].mean()) if n else float("nan")
    v = (~served["inside"].astype(bool)).astype(int).values if n else np.array([])
    lr_uc, p_uc = met._lr_kupiec(v, target) if n else (float("nan"), float("nan"))
    lr_ind_total = 0.0; n_groups = 0
    if n:
        for sym, g in served.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
            v_g = (~g["inside"].astype(bool)).astype(int).values
            lr_ind, _ = met._lr_christoffersen_independence(v_g)
            if not np.isnan(lr_ind):
                lr_ind_total += lr_ind; n_groups += 1
    p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
    return {"n": n, "realised": realised, "half_width_bps": half,
            "lr_uc": float(lr_uc), "p_uc": float(p_uc),
            "lr_ind": float(lr_ind_total), "p_ind": p_ind}


def by_regime(served: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for regime, g in served.groupby("regime_pub"):
        rows.append({
            "regime_pub": regime,
            "n": len(g),
            "realised": float(g["inside"].mean()),
            "half_width_bps": float(g["half_width_bps"].mean()),
        })
    return pd.DataFrame(rows).sort_values("regime_pub").reset_index(drop=True)


def bootstrap_delta(serv_a: pd.DataFrame, serv_b: pd.DataFrame,
                    rng: np.random.Generator, n_resamples: int = N_BOOTSTRAP):
    a = serv_a.groupby("fri_ts").agg(a_in=("inside", "sum"), a_hw=("half_width_bps", "sum"),
                                      a_n=("inside", "count"))
    b = serv_b.groupby("fri_ts").agg(b_in=("inside", "sum"), b_hw=("half_width_bps", "sum"),
                                      b_n=("inside", "count"))
    j = a.join(b, how="inner").reset_index()
    if not len(j):
        return np.array([]), np.array([])
    a_in = j["a_in"].to_numpy(float); a_hw = j["a_hw"].to_numpy(float); a_n = j["a_n"].to_numpy(float)
    b_in = j["b_in"].to_numpy(float); b_hw = j["b_hw"].to_numpy(float); b_n = j["b_n"].to_numpy(float)
    nw = len(j)
    dc = np.empty(n_resamples); ds = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, nw, size=nw)
        a_cov = a_in[idx].sum() / a_n[idx].sum()
        b_cov = b_in[idx].sum() / b_n[idx].sum()
        a_hi = a_hw[idx].sum() / a_n[idx].sum()
        b_hi = b_hw[idx].sum() / b_n[idx].sum()
        dc[i] = (b_cov - a_cov) * 100.0
        ds[i] = (b_hi - a_hi) / a_hi * 100.0
    return dc, ds


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(subset=["mon_open", "fri_close", "regime_pub"]).reset_index(drop=True)
    # Add factor-adjusted point column
    panel["point_stale"] = panel["fri_close"].astype(float)
    panel["point_fa"] = panel["fri_close"].astype(float) * (1.0 + panel["factor_ret"].astype(float))
    panel_train = panel[panel["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    # Deployed Oracle (cell C4 of §7.4)
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    surface = cal.compute_calibration_surface(bounds_train)
    surface_pooled = cal.pooled_surface(bounds_train)
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)

    print(f"Train panel: {len(panel_train):,} rows × {panel_train['fri_ts'].nunique()} weekends")
    print(f"OOS panel:   {len(panel_oos):,} rows × {panel_oos['fri_ts'].nunique()} weekends")
    print()

    # Calibrate Mondrian variants
    cal_M1 = calibrate_mondrian(panel_train, point_col="point_stale", group_cols=("regime_pub",))
    cal_M2 = calibrate_mondrian(panel_train, point_col="point_fa", group_cols=("regime_pub",))
    cal_M3 = calibrate_mondrian(panel_train, point_col="point_stale",
                                 group_cols=("symbol", "regime_pub"))
    # M4: oracle-fit Mondrian (per-regime quantile fitted directly on OOS).
    # Same role as §7.6.3's coverage-matched constant buffer — bounds the best
    # possible Mondrian width-at-coverage.
    cal_M4 = calibrate_mondrian_oos_fit(panel_oos, point_col="point_fa", group_cols=("regime_pub",))
    # M5: deployable Mondrian — train-fit per (regime, τ) plus one OOS scalar
    # bump c(τ) per τ. 4 OOS-fitted scalars total, matching the Oracle's
    # BUFFER_BY_TARGET schedule. The fair-fight comparator.
    cal_M5 = calibrate_mondrian_deployable(panel_train, panel_oos,
                                            point_col="point_fa", group_cols=("regime_pub",))
    print("Mondrian deployable bumps c(τ) (M5):")
    print(cal_M5.groupby("target")["bump_c"].first().to_string())
    print()

    print("Mondrian-by-regime (M1, stale point) trained quantiles:")
    print(cal_M1.pivot(index="regime_pub", columns="target", values="b").round(4).to_string())
    print()
    print("Mondrian-by-regime (M2, factor-adjusted point) trained quantiles:")
    print(cal_M2.pivot(index="regime_pub", columns="target", values="b").round(4).to_string())
    print()

    pooled_rows = []
    by_regime_rows = []
    bootstrap_rows = []
    rng = np.random.default_rng(RNG_SEED)

    for tau in TARGETS:
        # Serve all four methods at this τ
        served_or = serve_oracle(oracle, panel_oos, tau)
        served_M1 = serve_mondrian(panel_oos, cal_M1, "point_stale", ("regime_pub",), tau)
        served_M2 = serve_mondrian(panel_oos, cal_M2, "point_fa", ("regime_pub",), tau)
        served_M3 = serve_mondrian(panel_oos, cal_M3, "point_stale", ("symbol", "regime_pub"), tau)
        served_M4 = serve_mondrian(panel_oos, cal_M4, "point_fa", ("regime_pub",), tau)
        served_M5 = serve_mondrian(panel_oos, cal_M5, "point_fa", ("regime_pub",), tau)

        for name, served in [("oracle", served_or), ("M1_mondrian_stale", served_M1),
                              ("M2_mondrian_fa", served_M2), ("M3_mondrian_sym_regime", served_M3),
                              ("M4_mondrian_oos_fit", served_M4),
                              ("M5_mondrian_deployable", served_M5)]:
            s = pooled_summary(served, tau)
            pooled_rows.append({"target": tau, "method": name, **s})
            rb = by_regime(served); rb["method"] = name; rb["target"] = tau
            by_regime_rows.append(rb)

        print(f"τ={tau:.2f}:")
        for name, served in [("Oracle      ", served_or),
                              ("M1 stale-pt ", served_M1),
                              ("M2 fa-pt    ", served_M2),
                              ("M3 sym×reg  ", served_M3),
                              ("M4 OOS-fit  ", served_M4),
                              ("M5 deployable", served_M5)]:
            s = pooled_summary(served, tau)
            print(f"  {name}: n={s['n']}, realised={s['realised']:.4f}, "
                  f"hw={s['half_width_bps']:.1f}bps, p_uc={s['p_uc']:.3f}, p_ind={s['p_ind']:.3f}")

        # Bootstrap deltas: a = oracle, b = each Mondrian → δ = M_i − Oracle
        for name, served in [("M1_mondrian_stale", served_M1),
                              ("M2_mondrian_fa", served_M2),
                              ("M3_mondrian_sym_regime", served_M3),
                              ("M4_mondrian_oos_fit", served_M4),
                              ("M5_mondrian_deployable", served_M5)]:
            d_cov, d_sharp = bootstrap_delta(served_or, served, rng)
            bootstrap_rows.append({
                "target": tau, "comparison": f"{name} − oracle",
                "delta_cov_pp_mean": float(d_cov.mean()),
                "delta_cov_pp_lo": float(np.percentile(d_cov, 2.5)),
                "delta_cov_pp_hi": float(np.percentile(d_cov, 97.5)),
                "delta_sharp_pct_mean": float(d_sharp.mean()),
                "delta_sharp_pct_lo": float(np.percentile(d_sharp, 2.5)),
                "delta_sharp_pct_hi": float(np.percentile(d_sharp, 97.5)),
            })
            print(f"    Δ vs Oracle ({name}): cov {d_cov.mean():+.2f}pp [{np.percentile(d_cov,2.5):+.2f}, {np.percentile(d_cov,97.5):+.2f}], "
                  f"sharp {d_sharp.mean():+.1f}% [{np.percentile(d_sharp,2.5):+.1f}, {np.percentile(d_sharp,97.5):+.1f}]")
        print()

    out = REPORTS / "tables"
    out.mkdir(parents=True, exist_ok=True)
    pd.concat([
        cal_M1.assign(method="M1_mondrian_stale"),
        cal_M2.assign(method="M2_mondrian_fa"),
        cal_M3.assign(method="M3_mondrian_sym_regime"),
        cal_M4.assign(method="M4_mondrian_oos_fit"),
        cal_M5.assign(method="M5_mondrian_deployable"),
    ], ignore_index=True).to_csv(out / "v1b_mondrian_calibration.csv", index=False)
    pd.DataFrame(pooled_rows).to_csv(out / "v1b_mondrian_oos.csv", index=False)
    pd.concat(by_regime_rows, ignore_index=True).to_csv(out / "v1b_mondrian_by_regime.csv", index=False)
    pd.DataFrame(bootstrap_rows).to_csv(out / "v1b_mondrian_bootstrap.csv", index=False)
    print(f"Wrote {out / 'v1b_mondrian_calibration.csv'}")
    print(f"Wrote {out / 'v1b_mondrian_oos.csv'}")
    print(f"Wrote {out / 'v1b_mondrian_by_regime.csv'}")
    print(f"Wrote {out / 'v1b_mondrian_bootstrap.csv'}")


if __name__ == "__main__":
    main()
