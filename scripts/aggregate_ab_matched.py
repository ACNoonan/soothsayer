"""
Matched-coverage A/B: Kamino flat ±300bps vs Soothsayer across its full coverage
grid. Fixes the apples-to-oranges problem in `aggregate_ab_comparison.py`, which
pitted Kamino (an uncalibrated ~99%-in-calm, <95%-in-shock heuristic) against
Soothsayer at a single target=0.95 and called Soothsayer's tail-sensitive "FPs"
a failure.

Three outputs that answer the business question honestly:

  1. **ROC-style sweep.** Sweep Soothsayer across all 12 claimed grid levels
     (0.50–0.995). Plot miss-rate vs FP-rate. Overlay Kamino's single point.
     This shows the *frontier* Soothsayer operates on.

  2. **Matched-width comparison.** Find the Soothsayer target that yields
     mean band half-width = 300bps (pooled). At that target, does Soothsayer
     beat Kamino? This is the "same width budget, allocated smarter" test.

  3. **Matched-recall comparison.** Find the Soothsayer target that yields
     miss-rate = Kamino's pooled miss rate. At that target, is Soothsayer's
     FP rate + width distribution better? This is the "same safety, fewer
     false alarms" test.

Uses the hybrid per-regime forecaster choice from `oracle.REGIME_FORECASTER`:
  normal + long_weekend → F1_emp_regime
  high_vol             → F0_stale

Does NOT apply the 2.5pp calibration buffer. The buffer is a shift applied at
serving time; a sweep over the raw claimed grid already covers the range the
buffer would produce. We flag the buffered Oracle target=0.95 operating point
on the chart for reference.

Outputs:
  reports/tables/aggregate_ab_matched_sweep.csv   — per-claim rates, pooled + per-regime
  reports/tables/aggregate_ab_matched_summary.csv — matched-width and matched-recall rows
  reports/figures/aggregate_ab_roc.png            — miss vs FP curve
  reports/figures/aggregate_ab_width_curves.png   — mean width vs claimed coverage per regime
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import REGIME_FORECASTER


LTV_BUCKETS = [0.50, 0.65, 0.75, 0.80, 0.85, 0.88, 0.90]
MAX_LTV_AT_ORIGINATION = 0.75
LIQUIDATION_THRESHOLD = 0.85
KAMINO_BPS = 300.0


def classify(ltv: float, threshold: float) -> str:
    if ltv >= threshold:
        return "Liquidate"
    if ltv >= MAX_LTV_AT_ORIGINATION:
        return "Caution"
    return "Safe"


def prepare_hybrid_bounds(bounds: pd.DataFrame) -> pd.DataFrame:
    """Filter bounds to the hybrid-chosen forecaster per regime, matching the
    serving Oracle's REGIME_FORECASTER policy. Returns a copy with exactly one
    forecaster per (symbol, fri_ts, claimed)."""
    pieces = []
    for regime, forecaster in REGIME_FORECASTER.items():
        sub = bounds[(bounds["regime_pub"] == regime) & (bounds["forecaster"] == forecaster)]
        pieces.append(sub)
    result = pd.concat(pieces, ignore_index=True)
    # Sanity: each (symbol, fri_ts, claimed) should appear exactly once
    dup = result.duplicated(["symbol", "fri_ts", "claimed"]).sum()
    if dup > 0:
        raise RuntimeError(f"hybrid bounds has {dup} duplicates")
    return result


def evaluate_at_claim(
    fri_close: np.ndarray,
    mon_open: np.ndarray,
    lower: np.ndarray,
    regime: np.ndarray,
    ltv_target: float,
    threshold: float = LIQUIDATION_THRESHOLD,
) -> pd.DataFrame:
    """Vectorized evaluation of a single LTV bucket across all weekends at one
    Soothsayer claimed level. Returns a DataFrame with per-weekend decisions and
    realized decisions. Also includes Kamino for the same positions."""
    debt = ltv_target  # normalize collateral_value_at_origination = 1
    # collateral_qty = 1 / fri_close  (so collateral_qty × price = value)
    # current_ltv = debt / (collateral_qty × price) = debt × fri_close / price
    ltv_ss = debt * fri_close / lower
    ltv_realized = debt * fri_close / mon_open

    kamino_lower = fri_close * (1 - KAMINO_BPS / 10_000.0)
    ltv_kamino = debt * fri_close / kamino_lower

    def vec_classify(ltv_arr: np.ndarray) -> np.ndarray:
        out = np.full(len(ltv_arr), "Safe", dtype=object)
        out[ltv_arr >= MAX_LTV_AT_ORIGINATION] = "Caution"
        out[ltv_arr >= threshold] = "Liquidate"
        return out

    return pd.DataFrame({
        "regime": regime,
        "ltv_target": ltv_target,
        "decision_ss": vec_classify(ltv_ss),
        "decision_kamino": vec_classify(ltv_kamino),
        "decision_realized": vec_classify(ltv_realized),
    })


def _rates(df: pd.DataFrame, band_col: str) -> tuple[float, float, float]:
    band_liq = df[f"decision_{band_col}"] == "Liquidate"
    realized_liq = df["decision_realized"] == "Liquidate"
    fp = float(((band_liq) & (~realized_liq)).mean())
    miss = float(((~band_liq) & (realized_liq)).mean())
    liq = float(band_liq.mean())
    return fp, miss, liq


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="Debug limit on weekends; 0 = all")
    args = p.parse_args()

    print("Loading bounds table...")
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    print(f"  raw rows: {len(bounds):,}")

    hybrid = prepare_hybrid_bounds(bounds)
    print(f"  hybrid-filtered rows: {len(hybrid):,}")

    if args.limit > 0:
        keep = hybrid[["symbol", "fri_ts"]].drop_duplicates().head(args.limit)
        hybrid = hybrid.merge(keep, on=["symbol", "fri_ts"])
        print(f"  debug-limited to {len(keep)} weekends / {len(hybrid)} rows")

    claimed_levels = sorted(hybrid["claimed"].unique())
    print(f"  sweeping {len(claimed_levels)} claimed levels: {claimed_levels}")

    # ---------------------------------------------------------------- SWEEP

    sweep_rows = []  # one row per (claimed, regime_scope, ltv_target or pooled)

    for claim in claimed_levels:
        sub = hybrid[hybrid["claimed"] == claim]
        fri = sub["fri_close"].to_numpy()
        mon = sub["mon_open"].to_numpy()
        lower = sub["lower"].to_numpy()
        upper = sub["upper"].to_numpy()
        regime = sub["regime_pub"].to_numpy()
        point = 0.5 * (lower + upper)  # band midpoint
        hw_bps = (upper - lower) / 2.0 / point * 1e4  # half-width in bps

        # Mean width per regime + pooled at this claim
        width_by_regime = {}
        for r in ["normal", "long_weekend", "high_vol"]:
            mask = regime == r
            if mask.sum() > 0:
                width_by_regime[r] = float(np.mean(hw_bps[mask]))
        width_by_regime["pooled"] = float(np.mean(hw_bps))

        for ltv in LTV_BUCKETS:
            df_eval = evaluate_at_claim(fri, mon, lower, regime, ltv)
            # pooled across regimes, this LTV
            for scope_name, scope_df in [
                ("pooled", df_eval),
                ("normal", df_eval[df_eval["regime"] == "normal"]),
                ("long_weekend", df_eval[df_eval["regime"] == "long_weekend"]),
                ("high_vol", df_eval[df_eval["regime"] == "high_vol"]),
            ]:
                if len(scope_df) == 0:
                    continue
                ss_fp, ss_miss, ss_liq = _rates(scope_df, "ss")
                km_fp, km_miss, km_liq = _rates(scope_df, "kamino")
                realized_liq = float((scope_df["decision_realized"] == "Liquidate").mean())
                sweep_rows.append(dict(
                    claimed=claim,
                    scope=scope_name,
                    ltv_target=ltv,
                    n=len(scope_df),
                    ss_mean_hw_bps=width_by_regime.get(scope_name, np.nan),
                    ss_fp_rate=ss_fp,
                    ss_miss_rate=ss_miss,
                    ss_liq_rate=ss_liq,
                    kamino_fp_rate=km_fp,
                    kamino_miss_rate=km_miss,
                    kamino_liq_rate=km_liq,
                    realized_liq_rate=realized_liq,
                ))

    sweep = pd.DataFrame(sweep_rows)
    tables_dir = REPORTS / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    sweep.to_csv(tables_dir / "aggregate_ab_matched_sweep.csv", index=False)

    # ---------------------------------------------------- POOLED-ACROSS-LTV VIEW

    # Aggregate pooled across LTV buckets: weighted by n (equal weight since each LTV
    # has same n per scope).
    pooled_scope_claim_rows = []
    for (claim, scope), g in sweep.groupby(["claimed", "scope"]):
        total_n = int(g["n"].sum())
        w = g["n"] / total_n
        row = dict(
            claimed=claim,
            scope=scope,
            n=total_n,
            ss_mean_hw_bps=float(g["ss_mean_hw_bps"].iloc[0]),  # width is per-scope, not LTV
            ss_fp_rate=float((g["ss_fp_rate"] * w).sum()),
            ss_miss_rate=float((g["ss_miss_rate"] * w).sum()),
            ss_liq_rate=float((g["ss_liq_rate"] * w).sum()),
            kamino_fp_rate=float((g["kamino_fp_rate"] * w).sum()),
            kamino_miss_rate=float((g["kamino_miss_rate"] * w).sum()),
            kamino_liq_rate=float((g["kamino_liq_rate"] * w).sum()),
            realized_liq_rate=float((g["realized_liq_rate"] * w).sum()),
        )
        pooled_scope_claim_rows.append(row)
    pooled_sweep = pd.DataFrame(pooled_scope_claim_rows)

    # Kamino's FP/miss don't depend on the Soothsayer claim — pick from any claim
    km_pooled = pooled_sweep[pooled_sweep["scope"] == "pooled"].iloc[0]
    km_fp = float(km_pooled["kamino_fp_rate"])
    km_miss = float(km_pooled["kamino_miss_rate"])
    km_liq = float(km_pooled["kamino_liq_rate"])

    # -------------------------------------------- MATCHED-WIDTH + MATCHED-MISS

    pooled_only = pooled_sweep[pooled_sweep["scope"] == "pooled"].sort_values("claimed").reset_index(drop=True)

    # Matched-width: find claim where ss_mean_hw_bps ≈ 300 (pooled)
    width_gap = (pooled_only["ss_mean_hw_bps"] - 300).abs()
    mw_idx = int(width_gap.idxmin())
    mw_row = pooled_only.iloc[mw_idx]

    # Matched-miss: find claim where ss_miss_rate ≈ km_miss (pooled)
    miss_gap = (pooled_only["ss_miss_rate"] - km_miss).abs()
    mm_idx = int(miss_gap.idxmin())
    mm_row = pooled_only.iloc[mm_idx]

    summary_rows = [
        dict(
            comparison="Kamino flat ±300bps",
            ss_claim=None,
            ss_mean_hw_bps=300.0,
            fp_rate=km_fp,
            miss_rate=km_miss,
            liq_rate=km_liq,
        ),
        dict(
            comparison=f"Soothsayer at matched WIDTH (claim={mw_row['claimed']:.3f})",
            ss_claim=float(mw_row["claimed"]),
            ss_mean_hw_bps=float(mw_row["ss_mean_hw_bps"]),
            fp_rate=float(mw_row["ss_fp_rate"]),
            miss_rate=float(mw_row["ss_miss_rate"]),
            liq_rate=float(mw_row["ss_liq_rate"]),
        ),
        dict(
            comparison=f"Soothsayer at matched MISS (claim={mm_row['claimed']:.3f})",
            ss_claim=float(mm_row["claimed"]),
            ss_mean_hw_bps=float(mm_row["ss_mean_hw_bps"]),
            fp_rate=float(mm_row["ss_fp_rate"]),
            miss_rate=float(mm_row["ss_miss_rate"]),
            liq_rate=float(mm_row["ss_liq_rate"]),
        ),
    ]
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(tables_dir / "aggregate_ab_matched_summary.csv", index=False)

    # ---------------------------------------------------------------- CHART 1

    figures_dir = REPORTS / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # (a): ROC — miss vs FP curve
    ax = axes[0]
    ax.plot(
        pooled_only["ss_fp_rate"] * 100,
        pooled_only["ss_miss_rate"] * 100,
        "s-", color="#1f77b4", label="Soothsayer (target coverage sweep)", markersize=6,
    )
    for _, r in pooled_only.iterrows():
        ax.annotate(
            f"{r['claimed']:.3f}",
            (r["ss_fp_rate"] * 100, r["ss_miss_rate"] * 100),
            fontsize=7, xytext=(4, 2), textcoords="offset points", alpha=0.7,
        )
    ax.scatter(
        [km_fp * 100], [km_miss * 100],
        s=180, color="#d62728", marker="*", label="Kamino flat ±300bps",
        zorder=5, edgecolor="black", linewidth=0.8,
    )
    # Matched points
    ax.scatter(
        [mw_row["ss_fp_rate"] * 100], [mw_row["ss_miss_rate"] * 100],
        s=120, color="#2ca02c", marker="o", label=f"Matched width ({mw_row['ss_mean_hw_bps']:.0f}bps)",
        zorder=4, edgecolor="black",
    )
    ax.scatter(
        [mm_row["ss_fp_rate"] * 100], [mm_row["ss_miss_rate"] * 100],
        s=120, color="#ff7f0e", marker="^", label=f"Matched miss (claim={mm_row['claimed']:.3f})",
        zorder=4, edgecolor="black",
    )
    ax.set_xlabel("False-positive liquidation rate (%)")
    ax.set_ylabel("Missed liquidation rate (%)")
    ax.set_title("Miss vs FP frontier — pooled across regimes & LTV buckets\n(down-and-left = better)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right", fontsize=9)
    ax.invert_yaxis()

    # (b): Mean band width vs claimed coverage, per regime
    ax = axes[1]
    for regime, color in [("normal", "#2ca02c"), ("long_weekend", "#ff7f0e"), ("high_vol", "#d62728")]:
        sub = pooled_sweep[pooled_sweep["scope"] == regime].sort_values("claimed")
        ax.plot(
            sub["claimed"], sub["ss_mean_hw_bps"],
            "o-", color=color, label=f"Soothsayer — {regime}",
        )
    pooled_sub = pooled_sweep[pooled_sweep["scope"] == "pooled"].sort_values("claimed")
    ax.plot(
        pooled_sub["claimed"], pooled_sub["ss_mean_hw_bps"],
        "s--", color="#1f77b4", label="Soothsayer — pooled", linewidth=2,
    )
    ax.axhline(300, color="#d62728", linestyle=":", label="Kamino flat ±300bps", linewidth=2)
    ax.set_xlabel("Claimed coverage (target)")
    ax.set_ylabel("Mean band half-width (bps)")
    ax.set_title("Band width as a function of target coverage\n(Kamino's 300bps = a single operating point)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=9)

    fig.suptitle(
        f"Matched-coverage A/B — Kamino vs Soothsayer across {km_pooled['n']:,} observations",
        fontsize=12, weight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out1 = figures_dir / "aggregate_ab_roc.png"
    fig.savefig(out1, dpi=140)
    plt.close(fig)

    # ---------------------------------------------------------------- CONSOLE

    def pct(x: float) -> str:
        return f"{x*100:5.2f}%"

    print()
    print("=" * 92)
    print("SWEEP (pooled across regimes & LTV buckets, per Soothsayer claimed coverage)")
    print("=" * 92)
    print(f"  {'claim':>6s}  {'mean hw':>9s}   {'SS FP':>7s}   {'SS miss':>8s}   {'SS liq':>8s}   {'vs realized':>12s}")
    for _, r in pooled_only.iterrows():
        print(
            f"  {r['claimed']:6.3f}  {r['ss_mean_hw_bps']:7.1f}bps   "
            f"{pct(r['ss_fp_rate']):>7s}   {pct(r['ss_miss_rate']):>8s}   "
            f"{pct(r['ss_liq_rate']):>8s}   {pct(r['realized_liq_rate']):>12s}"
        )
    print()
    print(f"  Kamino flat ±300bps →  FP={pct(km_fp)}   miss={pct(km_miss)}   liq={pct(km_liq)}")

    print()
    print("=" * 92)
    print("MATCHED COMPARISONS")
    print("=" * 92)
    for _, r in summary.iterrows():
        print(
            f"  {r['comparison']:55s}  "
            f"width={r['ss_mean_hw_bps']:6.1f}bps   "
            f"FP={pct(r['fp_rate'])}   miss={pct(r['miss_rate'])}   liq={pct(r['liq_rate'])}"
        )

    # Per-regime breakdown at matched-width and matched-miss
    print()
    print("=" * 92)
    print("PER-REGIME at matched-width point")
    print("=" * 92)
    print(f"  Soothsayer @ claim={mw_row['claimed']:.3f}  (mean hw {mw_row['ss_mean_hw_bps']:.0f}bps pooled)")
    for r in ["normal", "long_weekend", "high_vol"]:
        sub = pooled_sweep[(pooled_sweep["scope"] == r) & (pooled_sweep["claimed"] == mw_row["claimed"])]
        if not sub.empty:
            row = sub.iloc[0]
            print(
                f"    {r:14s}  hw={row['ss_mean_hw_bps']:6.1f}bps   "
                f"SS FP={pct(row['ss_fp_rate'])}   SS miss={pct(row['ss_miss_rate'])}   "
                f"KM FP={pct(row['kamino_fp_rate'])}   KM miss={pct(row['kamino_miss_rate'])}"
            )

    print()
    print(f"Charts: {out1}")
    print(f"Tables: {tables_dir}/aggregate_ab_matched_*.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
