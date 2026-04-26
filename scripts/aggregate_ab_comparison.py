"""
Aggregate A/B comparison — legacy flat-band baseline vs Soothsayer (Case A: flat threshold
+ regime band) vs Soothsayer (Case B: regime-demoted threshold + regime band,
CURRENTLY SHIPPING in crates/soothsayer-demo-kamino) — across all 5,986 weekends
in the v1b bounds table.

Answers two questions:

  1. Does the shipping Soothsayer (Case B) actually beat the legacy flat-band baseline in aggregate?
     On which regimes, at which LTV levels? Where does Soothsayer LOSE?

  2. Does the double-demote (Case B) pay for itself vs single-demote (Case A)?
     The Case A variant applies regime-awareness only through the band width,
     keeping the liquidation threshold flat at 0.85. Case B also multiplies the
     threshold by 0.85 in high_vol (the pattern in the current demo-kamino crate).

Four bands per weekend, per position:

    Legacy   — flat ±300bps band, flat 0.85 liquidation threshold
    SS_A     — Soothsayer regime-aware band, flat 0.85 threshold (no double-demote)
    SS_B     — Soothsayer regime-aware band, regime-demoted threshold (current shipping)
    Realized — uses mon_open as price; flat 0.85 threshold (god-view baseline)

Decisions per position: Safe / Caution / Liquidate, using the same formula as the
demo-kamino crate:

    conservative_value = lower_price × collateral_qty
    current_ltv        = debt / conservative_value
    Liquidate if current_ltv >= effective_threshold
    Caution  if current_ltv >= 0.75 (max-LTV-at-origination)
    Safe     otherwise

Output:
    reports/tables/aggregate_ab_summary.csv   — per-regime, per-LTV, per-band rates
    reports/figures/aggregate_ab_comparison.png
    reports/aggregate_ab_comparison.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soothsayer.config import REPORTS
from soothsayer.oracle import Oracle


# Portfolio LTV-at-origination bucket edges
LTV_BUCKETS = [0.50, 0.65, 0.75, 0.80, 0.85, 0.88, 0.90]

# Demo-kamino default params
MAX_LTV_AT_ORIGINATION = 0.75
LIQUIDATION_THRESHOLD = 0.85
REGIME_MULTIPLIERS = {"normal": 1.00, "long_weekend": 0.95, "high_vol": 0.85}

# Legacy flat-band half-width retained from the original protocol-comparison scaffold
KAMINO_BPS = 300

# Soothsayer target coverage for this comparison
SOOTHSAYER_TARGET = 0.95


def classify(ltv: float, threshold: float) -> str:
    """Safe / Caution / Liquidate decision mirror of soothsayer-demo-kamino."""
    if ltv >= threshold:
        return "Liquidate"
    if ltv >= MAX_LTV_AT_ORIGINATION:
        return "Caution"
    return "Safe"


def evaluate_portfolio_on_bands(
    fri_close: float,
    mon_open: float,
    regime: str,
    ss_lower: float,
    ss_claim_served: float,
) -> list[dict]:
    """For this weekend (fixed fri_close, mon_open, regime, SS band), evaluate
    each LTV in LTV_BUCKETS under all four configs. Returns a list of dict
    rows suitable for pd.DataFrame.

    Design choice: we do NOT apply `treat_clipped_as_caution` here — the
    aggregate A/B should reflect the raw band + threshold logic. The
    clipped-forces-caution rule is a separate consumer-side policy decision
    that can be bolted on any of the three band configs uniformly.
    """
    kamino_lower = fri_close * (1 - KAMINO_BPS / 10_000.0)
    regime_mult = REGIME_MULTIPLIERS.get(regime, REGIME_MULTIPLIERS["high_vol"])

    rows = []
    for ltv_target in LTV_BUCKETS:
        # Normalize: $10k collateral-at-origination per position
        collat_value_at_orig = 10_000.0
        debt = collat_value_at_orig * ltv_target
        collateral_qty = collat_value_at_orig / fri_close

        # Current LTV under each band's conservative lower-bound reading
        ltv_kamino = debt / (collateral_qty * kamino_lower)
        ltv_soothsayer = debt / (collateral_qty * ss_lower)
        ltv_realized = debt / (collateral_qty * mon_open)

        # Three config-specific thresholds
        thr_flat = LIQUIDATION_THRESHOLD
        thr_demote = LIQUIDATION_THRESHOLD * regime_mult

        decisions = {
            "kamino": classify(ltv_kamino, thr_flat),
            "ss_a": classify(ltv_soothsayer, thr_flat),           # flat threshold
            "ss_b": classify(ltv_soothsayer, thr_demote),          # regime-demoted
            "realized": classify(ltv_realized, thr_flat),          # god-view baseline
        }

        rows.append(
            dict(
                ltv_target=ltv_target,
                regime=regime,
                fri_close=fri_close,
                mon_open=mon_open,
                ss_lower=ss_lower,
                ss_claim_served=ss_claim_served,
                kamino_lower=kamino_lower,
                ltv_kamino=ltv_kamino,
                ltv_soothsayer=ltv_soothsayer,
                ltv_realized=ltv_realized,
                **{f"decision_{k}": v for k, v in decisions.items()},
            )
        )
    return rows


def _band_half_width_bps(lower: float, upper: float, point: float) -> float:
    if point == 0:
        return 0.0
    return (upper - lower) / 2 / point * 1e4


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="Limit weekends for debugging; 0 = all.")
    args = p.parse_args()

    print("Loading Oracle + bounds table...")
    oracle = Oracle.load()
    bounds = oracle._bounds  # (symbol, fri_ts, claimed, lower, upper, fri_close, mon_open, regime_pub, forecaster)
    unique_weekends = bounds[
        ["symbol", "fri_ts", "mon_ts", "regime_pub", "fri_close", "mon_open"]
    ].drop_duplicates(subset=["symbol", "fri_ts"]).reset_index(drop=True)
    print(f"Total unique weekends: {len(unique_weekends):,}")

    if args.limit > 0:
        unique_weekends = unique_weekends.head(args.limit)

    rows = []
    widths = []  # band-half-width in bps per (band, regime)
    errors = 0
    for i, row in unique_weekends.iterrows():
        try:
            pp = oracle.fair_value(
                row["symbol"], row["fri_ts"],
                target_coverage=SOOTHSAYER_TARGET,
            )
        except Exception as e:
            errors += 1
            continue

        ss_lower = float(pp.lower)
        ss_upper = float(pp.upper)
        ss_point = float(pp.point)
        ss_claim_served = float(pp.claimed_coverage_served)

        position_rows = evaluate_portfolio_on_bands(
            fri_close=float(row["fri_close"]),
            mon_open=float(row["mon_open"]),
            regime=str(row["regime_pub"]),
            ss_lower=ss_lower,
            ss_claim_served=ss_claim_served,
        )
        for pr in position_rows:
            pr["symbol"] = row["symbol"]
            pr["fri_ts"] = row["fri_ts"]
            pr["forecaster_used"] = pp.forecaster_used
            rows.append(pr)

        # Per-band half-widths (for the width summary)
        widths.append(
            dict(
                regime=row["regime_pub"],
                kamino=KAMINO_BPS,
                soothsayer=_band_half_width_bps(ss_lower, ss_upper, ss_point),
            )
        )

        if (i + 1) % 500 == 0:
            print(f"  processed {i+1:,} / {len(unique_weekends):,} weekends")

    print(f"Done. {errors} weekend(s) errored.")

    df = pd.DataFrame(rows)
    widths_df = pd.DataFrame(widths)

    # -------------------------------------------------------- AGGREGATE STATS

    def rate_false_positive(group: pd.DataFrame, band_col: str) -> float:
        """Band liquidates but realized says not Liquidate."""
        band_liq = group[f"decision_{band_col}"] == "Liquidate"
        realized_not_liq = group["decision_realized"] != "Liquidate"
        return float((band_liq & realized_not_liq).mean()) if len(group) else 0.0

    def rate_missed(group: pd.DataFrame, band_col: str) -> float:
        """Band passes (Safe or Caution) but realized says Liquidate."""
        band_pass = group[f"decision_{band_col}"] != "Liquidate"
        realized_liq = group["decision_realized"] == "Liquidate"
        return float((band_pass & realized_liq).mean()) if len(group) else 0.0

    def rate_liquidated(group: pd.DataFrame, band_col: str) -> float:
        return float((group[f"decision_{band_col}"] == "Liquidate").mean())

    # Per-regime × per-LTV table
    agg_rows = []
    for (regime, ltv), grp in df.groupby(["regime", "ltv_target"]):
        row = dict(regime=regime, ltv_target=ltv, n=len(grp))
        for band in ["kamino", "ss_a", "ss_b"]:
            row[f"{band}_fp_rate"] = rate_false_positive(grp, band)
            row[f"{band}_miss_rate"] = rate_missed(grp, band)
            row[f"{band}_liq_rate"] = rate_liquidated(grp, band)
        row["realized_liq_rate"] = rate_liquidated(grp, "realized")
        agg_rows.append(row)
    per_regime_ltv = pd.DataFrame(agg_rows).sort_values(["regime", "ltv_target"]).reset_index(drop=True)

    # Regime-level (pooled across LTVs)
    regime_rows = []
    for regime, grp in df.groupby("regime"):
        row = dict(regime=regime, n_positions=len(grp), n_weekends=grp[["symbol","fri_ts"]].drop_duplicates().shape[0])
        for band in ["kamino", "ss_a", "ss_b"]:
            row[f"{band}_fp_rate"] = rate_false_positive(grp, band)
            row[f"{band}_miss_rate"] = rate_missed(grp, band)
            row[f"{band}_liq_rate"] = rate_liquidated(grp, band)
        row["realized_liq_rate"] = rate_liquidated(grp, "realized")
        regime_rows.append(row)
    per_regime = pd.DataFrame(regime_rows).sort_values("regime").reset_index(drop=True)

    # Pooled (one row)
    pooled_row = dict(regime="pooled", n_positions=len(df), n_weekends=df[["symbol","fri_ts"]].drop_duplicates().shape[0])
    for band in ["kamino", "ss_a", "ss_b"]:
        pooled_row[f"{band}_fp_rate"] = rate_false_positive(df, band)
        pooled_row[f"{band}_miss_rate"] = rate_missed(df, band)
        pooled_row[f"{band}_liq_rate"] = rate_liquidated(df, band)
    pooled_row["realized_liq_rate"] = rate_liquidated(df, "realized")
    pooled_df = pd.DataFrame([pooled_row])

    # Per-band mean half-width, per regime
    widths_agg_rows = []
    for regime, grp in widths_df.groupby("regime"):
        widths_agg_rows.append(dict(
            regime=regime,
            kamino_half_width_bps=float(grp["kamino"].mean()),
            soothsayer_half_width_bps=float(grp["soothsayer"].mean()),
            soothsayer_half_width_p50=float(grp["soothsayer"].quantile(0.5)),
            soothsayer_half_width_p95=float(grp["soothsayer"].quantile(0.95)),
        ))
    widths_summary = pd.DataFrame(widths_agg_rows).sort_values("regime").reset_index(drop=True)

    # -------------------------------------------------------- PERSIST

    tables_dir = REPORTS / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = REPORTS / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    per_regime_ltv.to_csv(tables_dir / "aggregate_ab_per_regime_ltv.csv", index=False)
    per_regime.to_csv(tables_dir / "aggregate_ab_per_regime.csv", index=False)
    pooled_df.to_csv(tables_dir / "aggregate_ab_pooled.csv", index=False)
    widths_summary.to_csv(tables_dir / "aggregate_ab_widths.csv", index=False)
    df.to_parquet(tables_dir / "aggregate_ab_raw.parquet")

    # -------------------------------------------------------- CHART

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    plt.subplots_adjust(wspace=0.3, hspace=0.4)

    # (0,0): False-positive liquidation rate by LTV, per band (normal regime)
    # (0,1): False-positive by LTV, per band (high_vol regime)
    # (1,0): Missed liquidation by LTV, per band (pooled)
    # (1,1): Mean band width per regime (bar chart)

    for ax, regime_label, regime_filter in [
        (axes[0, 0], "Normal regime (65% of weekends)", "normal"),
        (axes[0, 1], "High-vol regime (24% of weekends)", "high_vol"),
    ]:
        sub = per_regime_ltv[per_regime_ltv["regime"] == regime_filter]
        if sub.empty:
            continue
        x = sub["ltv_target"].values
        ax.plot(x, sub["kamino_fp_rate"] * 100, "o-", label="Legacy flat baseline", color="#d62728", alpha=0.85)
        ax.plot(x, sub["ss_a_fp_rate"] * 100, "s--", label="Soothsayer Case A (flat threshold)", color="#2ca02c", alpha=0.85)
        ax.plot(x, sub["ss_b_fp_rate"] * 100, "d-", label="Soothsayer Case B (demote threshold — current)", color="#1f77b4", alpha=0.85)
        ax.set_xlabel("LTV at origination")
        ax.set_ylabel("False-positive liquidation rate (%)")
        ax.set_title(f"False-positive liquidations — {regime_label}")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left", fontsize=8)

    # (1,0): Pooled missed liquidation by LTV
    ax = axes[1, 0]
    pooled_by_ltv = df.groupby("ltv_target").apply(
        lambda g: pd.Series({
            "kamino": rate_missed(g, "kamino") * 100,
            "ss_a": rate_missed(g, "ss_a") * 100,
            "ss_b": rate_missed(g, "ss_b") * 100,
        }),
    )
    x = pooled_by_ltv.index.values
    ax.plot(x, pooled_by_ltv["kamino"], "o-", label="Legacy flat baseline", color="#d62728")
    ax.plot(x, pooled_by_ltv["ss_a"], "s--", label="Soothsayer Case A", color="#2ca02c")
    ax.plot(x, pooled_by_ltv["ss_b"], "d-", label="Soothsayer Case B", color="#1f77b4")
    ax.set_xlabel("LTV at origination")
    ax.set_ylabel("Missed-liquidation rate (%)")
    ax.set_title("Missed liquidations — pooled across regimes\n(band passes but realized says Liquidate)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)

    # (1,1): Mean band width per regime
    ax = axes[1, 1]
    regimes = widths_summary["regime"].values
    x_pos = np.arange(len(regimes))
    w = 0.35
    ax.bar(x_pos - w/2, widths_summary["kamino_half_width_bps"], width=w, color="#d62728", label="Legacy flat ±300bps")
    ax.bar(x_pos + w/2, widths_summary["soothsayer_half_width_bps"], width=w, color="#1f77b4", label="Soothsayer mean (at target=0.95)")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(regimes)
    ax.set_ylabel("Band half-width (bps)")
    ax.set_title("Mean band half-width per regime\n(lower = more capital efficiency)")
    ax.grid(True, alpha=0.25, axis="y")
    ax.legend(loc="upper left", fontsize=8)

    fig.suptitle(
        f"Aggregate A/B — legacy flat baseline vs Soothsayer across {pooled_df['n_weekends'].iloc[0]:,} weekends × {len(LTV_BUCKETS)} LTV buckets",
        fontsize=12, weight="bold",
    )
    out_path = figures_dir / "aggregate_ab_comparison.png"
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_path, dpi=140)
    plt.close(fig)

    # -------------------------------------------------------- CONSOLE SUMMARY

    def pct(x: float) -> str:
        return f"{x*100:5.2f}%"

    print()
    print("=" * 88)
    print("POOLED (across all regimes and LTV buckets)")
    print("=" * 88)
    p = pooled_df.iloc[0]
    print(f"  n = {p['n_positions']:,} position-weekend observations across {p['n_weekends']:,} weekends")
    print()
    print(f"  {'':16s}  {'false-pos liq':>15s}   {'missed liq':>15s}   {'liq rate':>15s}")
    for band_label, band in [("Legacy flat", "kamino"), ("Soothsayer A (flat thresh)", "ss_a"), ("Soothsayer B (demote)", "ss_b")]:
        print(f"  {band_label:16s}  {pct(p[f'{band}_fp_rate']):>15s}   {pct(p[f'{band}_miss_rate']):>15s}   {pct(p[f'{band}_liq_rate']):>15s}")
    print(f"  {'Realized god-view':16s}  {'—':>15s}   {'—':>15s}   {pct(p['realized_liq_rate']):>15s}")
    print()
    print("=" * 88)
    print("PER REGIME")
    print("=" * 88)
    for _, r in per_regime.iterrows():
        regime = r["regime"]
        print(f"\n  regime = {regime}  (n = {r['n_positions']:,} positions, {r['n_weekends']:,} weekends)")
        print(f"    {'':16s}  {'false-pos liq':>15s}   {'missed liq':>15s}   {'liq rate':>15s}")
        for band_label, band in [("Legacy flat", "kamino"), ("Soothsayer A", "ss_a"), ("Soothsayer B", "ss_b")]:
            print(f"    {band_label:16s}  {pct(r[f'{band}_fp_rate']):>15s}   {pct(r[f'{band}_miss_rate']):>15s}   {pct(r[f'{band}_liq_rate']):>15s}")
        print(f"    {'Realized':16s}  {'—':>15s}   {'—':>15s}   {pct(r['realized_liq_rate']):>15s}")

    print()
    print("=" * 88)
    print("MEAN BAND HALF-WIDTH (bps)")
    print("=" * 88)
    print(widths_summary.to_string(index=False, float_format=lambda x: f"{x:8.1f}"))

    print()
    print(f"Figure: {out_path}")
    print(f"Raw data: {tables_dir}/aggregate_ab_*.csv,parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
