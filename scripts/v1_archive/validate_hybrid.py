"""
Product-level validation of the hybrid-regime Oracle.

Two tests:
  (1) In-sample sanity check — machinery test. Full calibration surface used;
      realized coverage should be close to target by construction. If it
      isn't, there's a bug.
  (2) Out-of-sample split — real number. Build calibration surface from
      pre-2023 bounds, serve Oracle on 2023+ weekends; check realized
      coverage against target. This is the closest analog to a production
      rebuild cadence.

Outputs:
  reports/v1b_hybrid_validation.md          — writeup + tables
  reports/figures/v1b_hybrid_reliability.png — product-level reliability diagram
  reports/tables/v1b_hybrid_validation.csv  — raw per-(target, regime, split) rows
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import REGIME_FORECASTER, Oracle


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.95, 0.99)


def _tables_dir() -> Path:
    p = REPORTS / "tables"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _figures_dir() -> Path:
    p = REPORTS / "figures"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _serve_panel(bounds: pd.DataFrame, surface: pd.DataFrame, surface_pooled: pd.DataFrame,
                 panel_rows: pd.DataFrame, targets: tuple[float, ...]) -> pd.DataFrame:
    """Run the Oracle over every row in `panel_rows` at each target.
    Returns long-form: row_idx, symbol, fri_ts, regime_pub, target, claim_served,
    forecaster_used, lower, upper, mon_open, inside, half_width_bps."""
    oracle = Oracle(bounds=bounds, surface=surface, surface_pooled=surface_pooled)
    out_rows = []
    for _, row in panel_rows.iterrows():
        for t in targets:
            try:
                pp = oracle.fair_value(row["symbol"], row["fri_ts"], target_coverage=t)
            except ValueError:
                continue
            inside = (row["mon_open"] >= pp.lower) and (row["mon_open"] <= pp.upper)
            out_rows.append({
                "symbol": row["symbol"],
                "fri_ts": row["fri_ts"],
                "regime_pub": row["regime_pub"],
                "target": t,
                "claim_served": pp.claimed_coverage_served,
                "forecaster_used": pp.forecaster_used,
                "lower": pp.lower,
                "upper": pp.upper,
                "mon_open": row["mon_open"],
                "fri_close": row["fri_close"],
                "inside": bool(inside),
                "half_width_bps": pp.half_width_bps,
            })
    return pd.DataFrame(out_rows)


def _aggregate(served: pd.DataFrame, split_label: str) -> pd.DataFrame:
    """Per-(target, regime) aggregate coverage and mean half-width."""
    grp = served.groupby(["target", "regime_pub"], observed=True)
    agg = grp.agg(
        n=("inside", "count"),
        realized=("inside", "mean"),
        mean_half_width_bps=("half_width_bps", "mean"),
    ).reset_index()
    agg["split"] = split_label
    # Pooled across regimes
    pooled = served.groupby("target", observed=True).agg(
        n=("inside", "count"),
        realized=("inside", "mean"),
        mean_half_width_bps=("half_width_bps", "mean"),
    ).reset_index()
    pooled["regime_pub"] = "pooled"
    pooled["split"] = split_label
    return pd.concat([agg, pooled], ignore_index=True)[
        ["split", "regime_pub", "target", "n", "realized", "mean_half_width_bps"]
    ]


def _kupiec_per_target(served: pd.DataFrame) -> pd.DataFrame:
    """Kupiec POF test per target on the pooled served bands."""
    rows = []
    for t, grp in served.groupby("target"):
        violations = (~grp["inside"]).astype(int).values
        lr_uc, p_uc = met._lr_kupiec(violations, t)
        lr_ind, p_ind = met._lr_christoffersen_independence(violations)
        rows.append({
            "target": t,
            "n": len(grp),
            "violations": int(violations.sum()),
            "violation_rate": float(violations.mean()),
            "expected_rate": 1.0 - t,
            "lr_uc": lr_uc,
            "p_uc": p_uc,
            "lr_ind": lr_ind,
            "p_ind": p_ind,
        })
    return pd.DataFrame(rows)


def _plot_hybrid_reliability(served_pre: pd.DataFrame, served_post: pd.DataFrame,
                              path: Path) -> None:
    """Product-level reliability diagram for the hybrid-served bands.

    One plot, x=target (consumer-requested coverage), y=realized (what the
    hybrid delivered), two panels: in-sample (full surface) vs out-of-sample
    (pre-2023 surface on 2023+ weekends)."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharey=True)

    for ax, served, title in [
        (axes[0], served_pre, "In-sample (full surface, full panel)"),
        (axes[1], served_post, "Out-of-sample (pre-2023 surface → 2023+ weekends)"),
    ]:
        ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect", linewidth=1.0)
        regime_styles = {
            "normal": ("#2ca02c", "o"),
            "long_weekend": ("#1f77b4", "s"),
            "high_vol": ("#d62728", "^"),
        }
        # Fine grid for the chart: include the three demo targets + interpolate
        # For the plot, use what was served. We passed TARGETS=(0.68, 0.95, 0.99).
        for t in TARGETS:
            # Pooled
            sub = served[served["target"] == t]
            if len(sub) < 20:
                continue
            realized = sub["inside"].mean()
            ax.scatter(t, realized, facecolors="none", edgecolors="black",
                       s=110, linewidth=1.5, zorder=3)
            # Regime-stratified
            for regime, (color, marker) in regime_styles.items():
                r_sub = sub[sub["regime_pub"] == regime]
                if len(r_sub) < 20:
                    continue
                ax.scatter(t, r_sub["inside"].mean(), color=color, marker=marker,
                           s=55, alpha=0.75, edgecolors="white", linewidth=0.5)
        for regime, (color, marker) in regime_styles.items():
            ax.scatter([], [], color=color, marker=marker, s=55, label=regime)
        ax.scatter([], [], facecolors="none", edgecolors="black", s=110, linewidth=1.5, label="pooled")
        ax.set_xlabel("Target coverage (consumer-requested)")
        ax.set_title(title + f"\nN={len(served):,}")
        ax.set_xlim(0.55, 1.02)
        ax.set_ylim(0.55, 1.02)
        ax.grid(True, alpha=0.25)
        ax.set_aspect("equal")
        ax.legend(loc="lower right", frameon=True, fontsize=8)
    axes[0].set_ylabel("Realized coverage")
    fig.suptitle("Hybrid Oracle product-level reliability diagram — what the consumer actually gets")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _write_report(
    in_sample_agg: pd.DataFrame,
    oos_agg: pd.DataFrame,
    in_sample_kupiec: pd.DataFrame,
    oos_kupiec: pd.DataFrame,
    fig_path: Path,
    split_date: date,
    n_train: int,
    n_test: int,
) -> Path:
    lines = [
        "# V1b Hybrid Oracle — Product-Level Validation",
        "",
        "**Question:** when a consumer asks for target realized coverage via the hybrid-regime Oracle, do they actually get it?",
        "",
        "**Method:** run `Oracle.fair_value(symbol, as_of, target_coverage=t)` over every historical weekend in the panel for t ∈ (0.68, 0.95, 0.99), record whether the realized Monday open fell inside the served band, aggregate realized coverage.",
        "",
        "Two splits:",
        "",
        f"- **In-sample:** full calibration surface, full panel. Machinery check — realized should be close to target by construction. If it isn't, there's a bug.",
        f"- **Out-of-sample:** calibration surface built from pre-{split_date} bounds only ({n_train:,} rows), Oracle served on weekends from {split_date} onward ({n_test:,} rows). Closest analog to production where the surface is rebuilt periodically.",
        "",
        f"![Hybrid reliability]({fig_path.relative_to(REPORTS).as_posix()})",
        "",
        "## In-sample coverage (machinery check)",
        "",
        in_sample_agg.to_markdown(index=False, floatfmt=".3f"),
        "",
        "### Kupiec / Christoffersen on in-sample pooled",
        "",
        in_sample_kupiec.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Out-of-sample coverage (the real number)",
        "",
        oos_agg.to_markdown(index=False, floatfmt=".3f"),
        "",
        "### Kupiec / Christoffersen on OOS pooled",
        "",
        oos_kupiec.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Reading the tables",
        "",
        "- `realized` vs `target` column: the closer these match, the better the hybrid's calibration surface generalises. A difference of ≤2pp is institutional-acceptable; 3–5pp is a disclosure; >5pp means the surface is stale or overfit.",
        "- `mean_half_width_bps` is the mean band half-width (in bps of Friday close) that the consumer actually received at each target.",
        "- Kupiec p-values are for the null that realized rate equals target. Christoffersen p-values are for the null that violations don't cluster in time.",
        "- Compare the in-sample table to the out-of-sample table. In-sample close-to-target confirms the inversion machinery; OOS close-to-target confirms the calibration surface generalises. A large delta between them indicates overfitting.",
    ]
    report_path = REPORTS / "v1b_hybrid_validation.md"
    report_path.write_text("\n".join(lines))
    return report_path


def main() -> None:
    bounds_full = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    # Ensure fri_ts and mon_ts are pd.Timestamp-compatible date types
    bounds_full["fri_ts"] = pd.to_datetime(bounds_full["fri_ts"]).dt.date
    bounds_full["mon_ts"] = pd.to_datetime(bounds_full["mon_ts"]).dt.date

    # Build a per-row panel frame (unique symbol × fri_ts × regime with mon_open + fri_close)
    panel = bounds_full[["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]].drop_duplicates(
        subset=["symbol", "fri_ts"]
    ).reset_index(drop=True)

    full_surface = cal.compute_calibration_surface(bounds_full)
    full_surface_pooled = cal.pooled_surface(bounds_full)

    # ---- In-sample: full surface, full panel
    print("=" * 80)
    print("IN-SAMPLE VALIDATION (machinery check)")
    print("=" * 80)
    served_in = _serve_panel(bounds_full, full_surface, full_surface_pooled, panel, TARGETS)
    in_sample_agg = _aggregate(served_in, split_label="in_sample")
    in_sample_kupiec = _kupiec_per_target(served_in)
    print(in_sample_agg.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print("Kupiec / Christoffersen (pooled):")
    print(in_sample_kupiec.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # ---- Out-of-sample: pre-2023 surface, 2023+ panel
    print()
    print("=" * 80)
    print(f"OUT-OF-SAMPLE VALIDATION (pre-{SPLIT_DATE} surface, {SPLIT_DATE}+ panel)")
    print("=" * 80)
    train_bounds = bounds_full[bounds_full["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    test_panel = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    test_bounds = bounds_full[bounds_full["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    train_surface = cal.compute_calibration_surface(train_bounds)
    train_surface_pooled = cal.pooled_surface(train_bounds)

    # Serve on test weekends — but the Oracle needs the bounds for those weekends too,
    # so we pass `test_bounds` as the bounds side. Surface side is `train_surface`.
    # Oracle uses bounds_df for the actual (lower, upper) at the requested claim and
    # the surface for the claimed-quantile inversion.
    served_oos = _serve_panel(test_bounds, train_surface, train_surface_pooled,
                              test_panel, TARGETS)
    oos_agg = _aggregate(served_oos, split_label="out_of_sample")
    oos_kupiec = _kupiec_per_target(served_oos)
    print(oos_agg.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print("Kupiec / Christoffersen (pooled):")
    print(oos_kupiec.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # Persist
    combined = pd.concat([in_sample_agg, oos_agg], ignore_index=True)
    combined.to_csv(_tables_dir() / "v1b_hybrid_validation.csv", index=False)

    fig_path = _figures_dir() / "v1b_hybrid_reliability.png"
    _plot_hybrid_reliability(served_in, served_oos, fig_path)

    report_path = _write_report(
        in_sample_agg, oos_agg,
        in_sample_kupiec, oos_kupiec,
        fig_path, SPLIT_DATE,
        n_train=len(train_bounds), n_test=len(test_bounds),
    )
    print()
    print(f"Report: {report_path}")
    print(f"Figure: {fig_path}")


if __name__ == "__main__":
    main()
