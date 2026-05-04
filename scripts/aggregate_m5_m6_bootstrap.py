"""
M5 vs M6 (LWC) block-bootstrap CIs on coverage and width — Phase 2.8.

The brief calls for "M5-vs-M6 block-bootstrap CIs on coverage and width
at every anchor (1000 weekend-block resamples, seed 0)". This is the
companion to the per-symbol headline (Phase 2.1): rather than localising
where M6 wins or loses, it puts an honest CI on the pooled deltas.

Method
------
- Build the OOS panel for both forecasters on the same split (2023-01-01).
  Different forecasters drop different rows (LWC's σ̂ warm-up filter ~80
  rows; M5 keeps everything with a defined score). Block-bootstrap
  operates on the inner-join `(symbol, fri_ts)` keys so the comparison
  is row-paired.
- The bootstrap unit is **weekend** (the §6.3.1 cross-sectional ordering
  scheme): each replicate samples weekends with replacement and keeps
  every (symbol) row within the sampled weekend. This preserves the
  cross-sectional common-mode that the §10.2 / §6.3.1 evidence flagged
  as the load-bearing rejection axis.
- Statistics:
    realised(τ)        per forecaster
    half_width_bps(τ)  per forecaster
    Δrealised(τ)       LWC - M5
    Δhalf_width_bps(τ) LWC - M5
- 1000 replicates with `numpy.random.default_rng(0)`. CI quantiles 2.5% /
  97.5% (95% percentile interval — same convention §10.3 uses).

Output
------
  reports/tables/m5_vs_m6_bootstrap.csv

  Columns: tau, statistic, point_m5, point_lwc, point_delta,
           ci_lo_delta, ci_hi_delta, ci_lo_m5, ci_hi_m5,
           ci_lo_lwc, ci_hi_lwc, n_weekends, n_rows, n_replicates, seed.

Run
---
  uv run python scripts/aggregate_m5_m6_bootstrap.py
"""

from __future__ import annotations

import argparse
from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
N_REPLICATES = 1000
SEED = 0
CI_LO, CI_HI = 0.025, 0.975
OUT_PATH = REPORTS / "tables" / "m5_vs_m6_bootstrap.csv"


def _serve_oos(forecaster: str) -> pd.DataFrame:
    """Build a long-form OOS table with one row per (symbol, fri_ts, tau).

    Columns: symbol, fri_ts, tau, inside (0/1), half_width_bps. Bands are
    served at the deployed schedule for the active forecaster."""
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = prep_panel_for_forecaster(panel, forecaster)

    qt, cb, info = fit_split_conformal_forecaster(
        panel, SPLIT_DATE, forecaster, cell_col="regime_pub",
    )
    oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
           .dropna(subset=["score"])
           .sort_values(["symbol", "fri_ts"])
           .reset_index(drop=True))
    bounds = serve_bands_forecaster(
        oos, qt, cb, forecaster,
        cell_col="regime_pub", taus=DEFAULT_TAUS,
    )

    rows = []
    for tau in DEFAULT_TAUS:
        b = bounds[tau]
        inside = ((oos["mon_open"] >= b["lower"]) &
                  (oos["mon_open"] <= b["upper"])).astype(int).to_numpy()
        hw_bps = ((b["upper"] - b["lower"]) / 2 / oos["fri_close"] * 1e4).to_numpy()
        for j, (_, row) in enumerate(oos.iterrows()):
            rows.append({
                "symbol": row["symbol"],
                "fri_ts": row["fri_ts"],
                "tau": float(tau),
                "inside": int(inside[j]),
                "half_width_bps": float(hw_bps[j]),
            })
    return pd.DataFrame(rows)


def _bootstrap_one_replicate(
    weekend_index: np.ndarray,
    sampled_weekends: np.ndarray,
    inside_m5: np.ndarray,
    inside_lwc: np.ndarray,
    hw_m5: np.ndarray,
    hw_lwc: np.ndarray,
) -> tuple[float, float, float, float]:
    """Compute (cov_m5, cov_lwc, hw_m5, hw_lwc) for one resampled weekend
    set. The replication picks rows whose `weekend_index` matches one of
    `sampled_weekends`. Duplicate weekends in `sampled_weekends` get their
    rows duplicated."""
    # np.in1d → mask of rows in sampled set; duplicates handled by counting.
    counts = pd.Series(sampled_weekends).value_counts()
    weights = np.zeros(weekend_index.max() + 2, dtype=int)
    weights[counts.index.values] = counts.values
    row_weights = weights[weekend_index]
    if row_weights.sum() == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    cov_m5 = float((inside_m5 * row_weights).sum() / row_weights.sum())
    cov_lwc = float((inside_lwc * row_weights).sum() / row_weights.sum())
    hw_m5_b = float((hw_m5 * row_weights).sum() / row_weights.sum())
    hw_lwc_b = float((hw_lwc * row_weights).sum() / row_weights.sum())
    return cov_m5, cov_lwc, hw_m5_b, hw_lwc_b


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-replicates", type=int, default=N_REPLICATES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    print(f"[1/4] Serving OOS bands for both forecasters …", flush=True)
    df_m5 = _serve_oos("m5").rename(columns={
        "inside": "inside_m5", "half_width_bps": "hw_m5"
    })
    df_lwc = _serve_oos("lwc").rename(columns={
        "inside": "inside_lwc", "half_width_bps": "hw_lwc"
    })
    print(f"      M5 rows: {len(df_m5):,}  LWC rows: {len(df_lwc):,}",
          flush=True)

    # Inner-join on (symbol, fri_ts, tau) so the bootstrap operates on
    # rows that exist for both forecasters. The σ̂ warm-up filter shaves
    # ~80 weekends from LWC; row-pairing is the cleanest comparison.
    paired = df_m5.merge(df_lwc, on=["symbol", "fri_ts", "tau"],
                         how="inner")
    print(f"      Paired rows: {len(paired):,} ({paired['fri_ts'].nunique()} "
          f"weekends, {paired['symbol'].nunique()} symbols, "
          f"{paired['tau'].nunique()} τ)", flush=True)

    # Pre-compute per-tau arrays for the bootstrap inner loop. Each τ has
    # the same (symbol, fri_ts) keys and the same weekend ordering since
    # both forecasters were sorted the same way.
    rng = np.random.default_rng(args.seed)
    weekends = sorted(paired["fri_ts"].unique())
    weekend_to_idx = {w: i for i, w in enumerate(weekends)}
    n_weekends = len(weekends)

    print(f"[2/4] Sampling {args.n_replicates} weekend-blocks "
          f"(seed={args.seed}) …", flush=True)
    sampled_weekend_idx_replicates = rng.integers(
        low=0, high=n_weekends, size=(args.n_replicates, n_weekends)
    )

    out_rows = []
    for tau in DEFAULT_TAUS:
        sub = paired[paired["tau"] == tau].sort_values(
            ["fri_ts", "symbol"]).reset_index(drop=True)
        weekend_idx = sub["fri_ts"].map(weekend_to_idx).to_numpy()
        inside_m5 = sub["inside_m5"].to_numpy(int)
        inside_lwc = sub["inside_lwc"].to_numpy(int)
        hw_m5 = sub["hw_m5"].to_numpy(float)
        hw_lwc = sub["hw_lwc"].to_numpy(float)

        cov_m5_reps = np.empty(args.n_replicates, dtype=float)
        cov_lwc_reps = np.empty(args.n_replicates, dtype=float)
        hw_m5_reps = np.empty(args.n_replicates, dtype=float)
        hw_lwc_reps = np.empty(args.n_replicates, dtype=float)

        for r in range(args.n_replicates):
            sampled = sampled_weekend_idx_replicates[r]
            cov_m5_reps[r], cov_lwc_reps[r], hw_m5_reps[r], hw_lwc_reps[r] = (
                _bootstrap_one_replicate(
                    weekend_idx, sampled, inside_m5, inside_lwc,
                    hw_m5, hw_lwc,
                )
            )

        d_cov = cov_lwc_reps - cov_m5_reps
        d_hw = hw_lwc_reps - hw_m5_reps

        point_cov_m5 = float(inside_m5.mean())
        point_cov_lwc = float(inside_lwc.mean())
        point_hw_m5 = float(hw_m5.mean())
        point_hw_lwc = float(hw_lwc.mean())

        for stat, m5_val, lwc_val, m5_reps, lwc_reps, delta_reps in [
            ("realised",
             point_cov_m5, point_cov_lwc,
             cov_m5_reps, cov_lwc_reps, d_cov),
            ("half_width_bps",
             point_hw_m5, point_hw_lwc,
             hw_m5_reps, hw_lwc_reps, d_hw),
        ]:
            out_rows.append({
                "tau": float(tau),
                "statistic": stat,
                "point_m5": m5_val,
                "point_lwc": lwc_val,
                "point_delta": lwc_val - m5_val,
                "ci_lo_m5": float(np.quantile(m5_reps, CI_LO)),
                "ci_hi_m5": float(np.quantile(m5_reps, CI_HI)),
                "ci_lo_lwc": float(np.quantile(lwc_reps, CI_LO)),
                "ci_hi_lwc": float(np.quantile(lwc_reps, CI_HI)),
                "ci_lo_delta": float(np.quantile(delta_reps, CI_LO)),
                "ci_hi_delta": float(np.quantile(delta_reps, CI_HI)),
                "n_weekends": int(n_weekends),
                "n_rows": int(len(sub)),
                "n_replicates": int(args.n_replicates),
                "seed": int(args.seed),
            })

    out = pd.DataFrame(out_rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"\n[3/4] Wrote {OUT_PATH}\n", flush=True)

    print("[4/4] M5 → LWC delta with 95% percentile CI (1000 weekend-block "
          "resamples, seed 0)")
    print("=" * 100)
    headers = ("τ", "stat", "M5", "LWC", "Δ", "95% CI on Δ")
    print(f"{headers[0]:>5}  {headers[1]:>15}  {headers[2]:>10}  "
          f"{headers[3]:>10}  {headers[4]:>10}  {headers[5]}")
    for _, r in out.iterrows():
        ci_str = f"[{r['ci_lo_delta']:+.4f}, {r['ci_hi_delta']:+.4f}]"
        print(f"{r['tau']:>5.2f}  {r['statistic']:>15}  "
              f"{r['point_m5']:>10.4f}  {r['point_lwc']:>10.4f}  "
              f"{r['point_delta']:>+10.4f}  {ci_str}")


if __name__ == "__main__":
    main()
