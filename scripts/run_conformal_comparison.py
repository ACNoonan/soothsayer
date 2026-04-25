"""
Stage-1.5 conformal comparison: heuristic 2.5pp empirical buffer vs split-
conformal alternatives, on the OOS 2023+ slice.

Question: would textbook conformal prediction (Vovk; Barber et al. nexCP) do
as well as or better than the heuristic empirical buffer in closing the OOS
calibration gap?

Variants tested:
  V0  vanilla            calibration surface inversion at τ (no adjustment).
                         Equivalent to vanilla split-conformal at our n_cal,
                         since the (n+1)/n correction is ~0.025% — two orders
                         of magnitude smaller than our heuristic buffer.
  V1  buffer_2.5pp       heuristic empirical buffer (current shipping default).
                         τ → τ + 0.025 before surface inversion.
  V3a nexcp_6mo          Barber-style recency-weighted calibration surface,
                         exponential weights with 6-month half-life on the
                         pre-2023 calibration set; serve at τ (no buffer).
  V3b nexcp_12mo         As V3a, 12-month half-life.
  V4a recency_6mo        Block-recency: calibration surface fit on only the
                         last 6 months pre-2023 (uniform weights).
  V4b recency_12mo       As V4a, 12 months.

Targets swept: τ ∈ {0.68, 0.85, 0.95, 0.99} — includes the new shipping
default τ = 0.85 (oracle.py 2026-04-25).

Outputs:
  reports/tables/v1b_conformal_comparison.csv            per-variant per-target
  reports/tables/v1b_conformal_comparison_by_regime.csv  per-variant per-regime
  reports/tables/v1b_conformal_bootstrap.csv             pairwise deltas with 95% CI
  reports/v1b_conformal_comparison.md                    writeup
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


SPLIT_DATE = date(2023, 1, 1)
TARGETS: tuple[float, ...] = (0.68, 0.85, 0.95, 0.99)
N_BOOT = 1000
RNG_SEED = 0xC0FFEE_BABE


def _tables_dir() -> Path:
    p = REPORTS / "tables"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Surface builders
# ---------------------------------------------------------------------------

def _weighted_surface(
    bounds_train: pd.DataFrame, half_life_months: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Barber nexCP-style: recency-weighted empirical coverage on the pre-2023
    calibration set. Exponential weights w_i = exp(-(split_date - fri_ts) / hl)
    where hl is in days."""
    b = bounds_train.copy()
    b["inside"] = (b["mon_open"] >= b["lower"]) & (b["mon_open"] <= b["upper"])
    b["half_width_bps"] = (b["upper"] - b["lower"]) / 2.0 / b["fri_close"] * 1e4
    half_life_days = half_life_months * 30.5
    days_old = (SPLIT_DATE - pd.to_datetime(b["fri_ts"]).dt.date).apply(lambda d: d.days)
    b["w"] = np.exp(-np.asarray(days_old, dtype=float) / half_life_days)

    def _agg(g: pd.DataFrame) -> pd.Series:
        w = g["w"].values
        return pd.Series({
            "realized": float(np.average(g["inside"], weights=w)),
            "n_obs": int(len(g)),
            "mean_half_width_bps": float(np.average(g["half_width_bps"], weights=w)),
        })

    group_cols_sym = ["symbol", "regime_pub", "forecaster", "claimed"]
    surface = b.groupby(group_cols_sym, observed=True).apply(_agg).reset_index()
    surface = surface.sort_values(group_cols_sym).reset_index(drop=True)

    group_cols_pool = ["regime_pub", "forecaster", "claimed"]
    pooled = b.groupby(group_cols_pool, observed=True).apply(_agg).reset_index()
    pooled["symbol"] = "__pooled__"
    pooled = pooled.sort_values(group_cols_pool).reset_index(drop=True)
    return surface, pooled


def _recency_restricted_surface(
    bounds_train: pd.DataFrame, lookback_months: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Block-recency: only the last `lookback_months` of pre-2023 data, uniform
    weights. The 'simple recency' baseline against which weighted-quantile
    nexCP is the smoother alternative."""
    cutoff = SPLIT_DATE - timedelta(days=int(lookback_months * 30.5))
    sub = bounds_train[bounds_train["fri_ts"] >= cutoff].reset_index(drop=True)
    return cal.compute_calibration_surface(sub), cal.pooled_surface(sub)


# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------

def _serve_panel(
    bounds_oos: pd.DataFrame,
    panel_oos: pd.DataFrame,
    surface: pd.DataFrame,
    surface_pooled: pd.DataFrame,
    targets: tuple[float, ...],
    *,
    buffer: float,
    variant: str,
) -> pd.DataFrame:
    oracle = Oracle(
        bounds=bounds_oos,
        surface=surface,
        surface_pooled=surface_pooled,
        calibration_buffer_pct=buffer,
    )
    rows = []
    for _, row in panel_oos.iterrows():
        for t in targets:
            try:
                pp = oracle.fair_value(row["symbol"], row["fri_ts"], target_coverage=t)
            except ValueError:
                continue
            inside = (row["mon_open"] >= pp.lower) and (row["mon_open"] <= pp.upper)
            rows.append({
                "variant": variant,
                "symbol": row["symbol"],
                "fri_ts": row["fri_ts"],
                "regime_pub": row["regime_pub"],
                "target": float(t),
                "inside": int(inside),
                "half_width_bps": float(pp.half_width_bps),
                "claim_served": float(pp.claimed_coverage_served),
                "forecaster_used": pp.forecaster_used,
                "buffer_applied": float(pp.calibration_buffer_applied),
                "fri_close": float(row["fri_close"]),
                "mon_open": float(row["mon_open"]),
                "lower": float(pp.lower),
                "upper": float(pp.upper),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _summarize(served: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (variant, target), grp in served.groupby(["variant", "target"]):
        v = (~grp["inside"].astype(bool)).astype(int).values
        lr_uc, p_uc = met._lr_kupiec(v, target)
        # Christoffersen pooled across symbols (sum of LRs, χ² with k = number of symbols)
        lr_ind_total = 0.0
        n_groups = 0
        for sym, sgrp in grp.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
            lr_ind, _ = met._lr_christoffersen_independence(
                (~sgrp["inside"].astype(bool)).astype(int).values
            )
            if not np.isnan(lr_ind):
                lr_ind_total += lr_ind
                n_groups += 1
        if n_groups > 0:
            from scipy.stats import chi2
            p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups))
        else:
            p_ind = float("nan")

        rows.append({
            "variant": variant,
            "target": float(target),
            "n": int(len(grp)),
            "realized": float(grp["inside"].mean()),
            "mean_half_width_bps": float(grp["half_width_bps"].mean()),
            "violations": int(v.sum()),
            "violation_rate": float(v.mean()),
            "lr_uc": float(lr_uc),
            "p_uc": float(p_uc),
            "lr_ind": float(lr_ind_total) if n_groups > 0 else float("nan"),
            "p_ind": p_ind,
        })
    return pd.DataFrame(rows)


def _by_regime(served: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (variant, target, regime), grp in served.groupby(["variant", "target", "regime_pub"]):
        rows.append({
            "variant": variant,
            "target": float(target),
            "regime_pub": regime,
            "n": int(len(grp)),
            "realized": float(grp["inside"].mean()),
            "mean_half_width_bps": float(grp["half_width_bps"].mean()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _bootstrap_pair(
    served: pd.DataFrame, variant_a: str, variant_b: str, target: float,
    n_boot: int = N_BOOT, seed: int = RNG_SEED,
) -> dict:
    sa = served[(served["variant"] == variant_a) & (served["target"] == target)]
    sb = served[(served["variant"] == variant_b) & (served["target"] == target)]
    sa = sa.set_index(["symbol", "fri_ts"])
    sb = sb.set_index(["symbol", "fri_ts"])
    common = sa.index.intersection(sb.index)
    sa = sa.loc[common].reset_index()
    sb = sb.loc[common].reset_index()

    weekends = pd.unique(sa["fri_ts"].values)
    rng = np.random.default_rng(seed)

    pt_dcov = sb["inside"].mean() - sa["inside"].mean()
    sa_sh = sa["half_width_bps"].mean()
    pt_dsh_pct = (sb["half_width_bps"].mean() / sa_sh - 1.0) if sa_sh > 0 else float("nan")

    sa_by_wk = {w: g for w, g in sa.groupby("fri_ts")}
    sb_by_wk = {w: g for w, g in sb.groupby("fri_ts")}

    dcovs = np.empty(n_boot)
    dshs = np.empty(n_boot)
    n_wk = len(weekends)
    for i in range(n_boot):
        draw = rng.integers(0, n_wk, size=n_wk)
        sampled = weekends[draw]
        a_cat = pd.concat([sa_by_wk[w] for w in sampled], ignore_index=True)
        b_cat = pd.concat([sb_by_wk[w] for w in sampled], ignore_index=True)
        dcovs[i] = b_cat["inside"].mean() - a_cat["inside"].mean()
        a_sh = a_cat["half_width_bps"].mean()
        dshs[i] = (b_cat["half_width_bps"].mean() / a_sh - 1.0) if a_sh > 0 else float("nan")

    return {
        "variant_a": variant_a, "variant_b": variant_b, "target": target,
        "n_weekends": int(n_wk), "n_rows": int(len(sa)),
        "delta_cov": float(pt_dcov),
        "delta_cov_ci_lo": float(np.quantile(dcovs, 0.025)),
        "delta_cov_ci_hi": float(np.quantile(dcovs, 0.975)),
        "delta_sharp_pct": float(pt_dsh_pct),
        "delta_sharp_pct_ci_lo": float(np.nanquantile(dshs, 0.025)),
        "delta_sharp_pct_ci_hi": float(np.nanquantile(dshs, 0.975)),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds["mon_ts"] = pd.to_datetime(bounds["mon_ts"]).dt.date

    panel_full = bounds[
        ["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]
    ].drop_duplicates(["symbol", "fri_ts"]).reset_index(drop=True)
    panel_oos = panel_full[panel_full["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)

    print(f"OOS panel: {len(panel_oos):,} rows in {panel_oos['fri_ts'].nunique()} weekends; "
          f"calibration: {len(bounds_train):,} bound-rows pre-{SPLIT_DATE}", flush=True)

    # ---------------- Build surfaces ----------------
    full_surface = cal.compute_calibration_surface(bounds_train)
    full_pooled = cal.pooled_surface(bounds_train)

    print("Building recency-weighted surfaces…", flush=True)
    t0 = time.time()
    surf_w6, pool_w6 = _weighted_surface(bounds_train, half_life_months=6)
    surf_w12, pool_w12 = _weighted_surface(bounds_train, half_life_months=12)
    print(f"  weighted surfaces ready in {time.time()-t0:.1f}s", flush=True)

    print("Building recency-restricted surfaces…", flush=True)
    surf_r6, pool_r6 = _recency_restricted_surface(bounds_train, lookback_months=6)
    surf_r12, pool_r12 = _recency_restricted_surface(bounds_train, lookback_months=12)

    # ---------------- Serve all variants ----------------
    variants = [
        ("V0_vanilla",     full_surface, full_pooled, 0.000),
        ("V1_buffer_25pp", full_surface, full_pooled, 0.025),
        ("V3a_nexcp_6mo",  surf_w6,      pool_w6,     0.000),
        ("V3b_nexcp_12mo", surf_w12,     pool_w12,    0.000),
        ("V4a_recency_6mo",  surf_r6,    pool_r6,     0.000),
        ("V4b_recency_12mo", surf_r12,   pool_r12,    0.000),
    ]
    served_all = []
    for name, surf, pool, buf in variants:
        t0 = time.time()
        s = _serve_panel(bounds_oos, panel_oos, surf, pool, TARGETS,
                         buffer=buf, variant=name)
        served_all.append(s)
        cov95 = s[s["target"] == 0.95]["inside"].mean()
        cov85 = s[s["target"] == 0.85]["inside"].mean()
        print(f"[{name}] {len(s):,} rows in {time.time()-t0:.1f}s; "
              f"cov@0.85={cov85:.3f}  cov@0.95={cov95:.3f}", flush=True)
    served = pd.concat(served_all, ignore_index=True)

    # ---------------- Summaries ----------------
    summary = _summarize(served).sort_values(["target", "variant"]).reset_index(drop=True)
    by_regime = _by_regime(served).sort_values(["target", "regime_pub", "variant"]).reset_index(drop=True)

    summary.to_csv(_tables_dir() / "v1b_conformal_comparison.csv", index=False)
    by_regime.to_csv(_tables_dir() / "v1b_conformal_comparison_by_regime.csv", index=False)

    print()
    print("=" * 80)
    print("VARIANT × TARGET — pooled OOS")
    print("=" * 80)
    cols = ["variant", "target", "n", "realized", "mean_half_width_bps", "p_uc", "p_ind"]
    print(summary[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # ---------------- Bootstrap ----------------
    print()
    print("=" * 80)
    print("BOOTSTRAP (95% CI on pairwise deltas; per target)")
    print("=" * 80)
    pairs = [
        ("V0_vanilla",     "V1_buffer_25pp"),  # heuristic buffer effect
        ("V0_vanilla",     "V3a_nexcp_6mo"),   # nexCP 6mo vs vanilla
        ("V0_vanilla",     "V3b_nexcp_12mo"),  # nexCP 12mo vs vanilla
        ("V1_buffer_25pp", "V3a_nexcp_6mo"),   # nexCP vs heuristic — the headline question
        ("V1_buffer_25pp", "V3b_nexcp_12mo"),
        ("V0_vanilla",     "V4a_recency_6mo"),
        ("V1_buffer_25pp", "V4b_recency_12mo"),
    ]
    boot_rows = []
    for a, b in pairs:
        for t in TARGETS:
            t0 = time.time()
            r = _bootstrap_pair(served, a, b, target=t)
            boot_rows.append(r)
            print(f"  τ={t:.2f}  {a} → {b}: "
                  f"Δcov={r['delta_cov']:+.3f} [{r['delta_cov_ci_lo']:+.3f}, {r['delta_cov_ci_hi']:+.3f}]  "
                  f"Δsharp={r['delta_sharp_pct']:+.1%} "
                  f"[{r['delta_sharp_pct_ci_lo']:+.1%}, {r['delta_sharp_pct_ci_hi']:+.1%}]  "
                  f"({time.time()-t0:.1f}s)", flush=True)
    boot = pd.DataFrame(boot_rows)
    boot.to_csv(_tables_dir() / "v1b_conformal_bootstrap.csv", index=False)

    print()
    print(f"Wrote:")
    print(f"  {_tables_dir() / 'v1b_conformal_comparison.csv'}")
    print(f"  {_tables_dir() / 'v1b_conformal_comparison_by_regime.csv'}")
    print(f"  {_tables_dir() / 'v1b_conformal_bootstrap.csv'}")


if __name__ == "__main__":
    main()
