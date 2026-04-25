"""
Historical shock-weekend replay — Kamino flat band vs Soothsayer calibrated band.

Produces the pitch chart + A/B summary. Slide-worthy version of the
`flat_gov_band_vs_empirical_side_by_side` unit test in
`crates/soothsayer-demo-kamino/src/lib.rs`.

Usage:
    uv run python scripts/replay_shock_weekend.py                         # 2020-03-13 SPY
    uv run python scripts/replay_shock_weekend.py --date 2024-08-02       # yen unwind
    uv run python scripts/replay_shock_weekend.py --date 2025-04-04 --symbol NVDA
    uv run python scripts/replay_shock_weekend.py --kamino-bps 500 --target 0.99

Output:
    reports/figures/replay_<SYMBOL>_<DATE>.png
    console summary

The decision logic mirrors `crates/soothsayer-demo-kamino/src/lib.rs::evaluate`:
    conservative_value = lower_bound * qty
    current_ltv        = debt / conservative_value
    threshold_effective = liquidation_threshold * regime_multiplier[regime]
    Decision: Safe | Caution | Liquidate
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from soothsayer.oracle import Oracle
from soothsayer.config import REPORTS


# Mirrors soothsayer-demo-kamino::LendingParams defaults.
MAX_LTV_AT_ORIGINATION = 0.75
LIQUIDATION_THRESHOLD = 0.85
REGIME_MULTIPLIERS = {"normal": 1.00, "long_weekend": 0.95, "high_vol": 0.85}


@dataclass
class Position:
    label: str
    debt_usdc: float
    collateral_qty: float

    def ltv_under(self, lower_bound_price: float) -> float:
        return self.debt_usdc / (self.collateral_qty * lower_bound_price)


@dataclass
class Decision:
    name: str             # "Safe" / "Caution" / "Liquidate"
    ltv: float
    threshold: float


def classify(ltv: float, threshold_effective: float, clipped_forces_caution: bool) -> Decision:
    if ltv >= threshold_effective:
        return Decision("Liquidate", ltv, threshold_effective)
    if ltv >= MAX_LTV_AT_ORIGINATION:
        return Decision("Caution", ltv, threshold_effective)
    return Decision(
        "Caution" if clipped_forces_caution else "Safe",
        ltv, threshold_effective,
    )


def kamino_flat_band(fri_close: float, deviation_bps: int) -> tuple[float, float]:
    frac = deviation_bps / 10_000.0
    return fri_close * (1 - frac), fri_close * (1 + frac)


def build_sample_portfolio(fri_close: float) -> list[Position]:
    """5 positions at LTV-at-origination of 50/65/75/82/88% against fri_close.
    Collateral value per position = $10,000; debt = 10_000 × target LTV."""
    COLLAT_VALUE = 10_000.0
    target_ltvs = [0.50, 0.65, 0.75, 0.82, 0.88]
    out = []
    for ltv_target in target_ltvs:
        qty = COLLAT_VALUE / fri_close
        debt = COLLAT_VALUE * ltv_target
        out.append(
            Position(
                label=f"LTV@orig={int(ltv_target*100)}%",
                debt_usdc=debt,
                collateral_qty=qty,
            )
        )
    return out


def regime_multiplier(regime: str) -> float:
    return REGIME_MULTIPLIERS.get(regime, REGIME_MULTIPLIERS["high_vol"])


def evaluate_portfolio(
    portfolio: list[Position],
    lower_bound_price: float,
    regime: str,
    *,
    is_soothsayer: bool,
    claimed_served: float = 0.0,
) -> list[tuple[Position, Decision]]:
    """Mirror of the Rust demo-kamino `evaluate` path."""
    threshold = LIQUIDATION_THRESHOLD * regime_multiplier(regime)
    clipped = is_soothsayer and claimed_served >= 0.995
    out = []
    for p in portfolio:
        ltv = p.ltv_under(lower_bound_price)
        decision = classify(ltv, threshold, clipped_forces_caution=clipped)
        out.append((p, decision))
    return out


def evaluate_counterfactual_realized(
    portfolio: list[Position],
    mon_open_price: float,
    threshold_effective: float,
) -> list[tuple[Position, Decision]]:
    """What the 'god-view' says: using realized Monday open as the true price,
    which positions were genuinely at risk? A liquidation Friday evening is
    "correct" if the position's LTV at realized Monday open exceeds the
    threshold; otherwise it's a false positive."""
    out = []
    for p in portfolio:
        ltv_realized = p.debt_usdc / (p.collateral_qty * mon_open_price)
        decision = classify(ltv_realized, threshold_effective, clipped_forces_caution=False)
        out.append((p, decision))
    return out


def _color_for(decision_name: str) -> str:
    return {"Safe": "#2ca02c", "Caution": "#ff9800", "Liquidate": "#d62728"}[decision_name]


def plot(
    symbol: str,
    fri_ts: date,
    mon_ts: date,
    fri_close: float,
    mon_open: float,
    kamino_lo: float,
    kamino_hi: float,
    ss_lo: float,
    ss_hi: float,
    ss_point: float,
    regime: str,
    target_coverage: float,
    claimed_served: float,
    forecaster_used: str,
    kamino_bps: int,
    kamino_eval: list,
    soothsayer_eval: list,
    realized_eval: list,
    out_path: Path,
) -> None:
    fig, (ax_price, ax_portfolio) = plt.subplots(
        2, 1, figsize=(12, 9),
        gridspec_kw={"height_ratios": [2.2, 1]},
    )

    # ── top panel: bands vs realized ──
    x_fri, x_mon = 0.0, 1.0
    ax_price.axvline(x_fri, color="#888", alpha=0.3, linestyle=":")
    ax_price.axvline(x_mon, color="#888", alpha=0.3, linestyle=":")

    # Soothsayer band (shaded, teal)
    ax_price.fill_between(
        [x_fri - 0.02, x_mon + 0.02], [ss_lo, ss_lo], [ss_hi, ss_hi],
        color="#1f77b4", alpha=0.18, label=(
            f"Soothsayer band\n  target={target_coverage:.2f}, claim_served={claimed_served:.3f}\n"
            f"  forecaster={forecaster_used}, regime={regime}\n"
            f"  ≈{(ss_hi-ss_lo)/2/ss_point*1e4:.0f}bps half-width"
        ),
    )

    # Kamino flat band (hatched, red)
    ax_price.fill_between(
        [x_fri - 0.02, x_mon + 0.02], [kamino_lo, kamino_lo], [kamino_hi, kamino_hi],
        color="none", edgecolor="#d62728", hatch="///", alpha=0.6, linewidth=0.8,
        label=f"Kamino flat band\n  ±{kamino_bps}bps governance param\n  regime-agnostic",
    )

    # Price markers
    ax_price.scatter([x_fri], [fri_close], color="black", s=90, zorder=5, label=f"Fri close = ${fri_close:,.2f}")
    ax_price.scatter([x_mon], [mon_open], color="#d62728", marker="X", s=130, zorder=5,
                     label=f"Mon open = ${mon_open:,.2f}  (realized move {(mon_open/fri_close - 1)*1e4:+.0f}bps)")

    # Soothsayer point
    ax_price.scatter([x_mon - 0.05], [ss_point], color="#1f77b4", marker="d", s=80, zorder=4,
                     label=f"Soothsayer point = ${ss_point:,.2f}")

    ax_price.set_xlim(-0.15, 1.15)
    ax_price.set_xticks([x_fri, x_mon])
    ax_price.set_xticklabels([f"Fri {fri_ts}", f"Mon {mon_ts}"])
    ax_price.set_ylabel(f"{symbol} price (USD)")
    ax_price.set_title(
        f"{symbol} shock-weekend replay: {fri_ts} → {mon_ts}  "
        f"(regime = {regime}, realized move = {(mon_open/fri_close - 1)*1e4:+.0f}bps)",
        fontsize=11, weight="bold",
    )
    ax_price.legend(loc="lower left", fontsize=8, framealpha=0.9)
    ax_price.grid(True, alpha=0.2)

    # ── bottom panel: decision grid (positions × 3 bands) ──
    labels = [p.label for p, _ in kamino_eval]
    n_pos = len(labels)
    band_cols = [
        ("Kamino\n(±{} bps)".format(kamino_bps), kamino_eval),
        ("Soothsayer\n(calibrated)", soothsayer_eval),
        ("Realized\n(god-view)", realized_eval),
    ]

    # Build a grid of colored rectangles with decision text.
    cell_h = 1.0
    cell_w = 1.0
    for col_idx, (col_label, evl) in enumerate(band_cols):
        for row_idx, (_, d) in enumerate(evl):
            rect = mpatches.Rectangle(
                (col_idx * cell_w, (n_pos - 1 - row_idx) * cell_h),
                cell_w, cell_h,
                facecolor=_color_for(d.name), edgecolor="white", linewidth=1.5, alpha=0.88,
            )
            ax_portfolio.add_patch(rect)
            text_color = "white" if d.name != "Caution" else "#222"
            ax_portfolio.text(
                col_idx * cell_w + cell_w / 2,
                (n_pos - 1 - row_idx) * cell_h + cell_h / 2,
                d.name, ha="center", va="center",
                fontsize=10, weight="bold", color=text_color,
            )

    # Column labels at the TOP of the grid.
    for col_idx, (col_label, _) in enumerate(band_cols):
        ax_portfolio.text(
            col_idx * cell_w + cell_w / 2, n_pos * cell_h + 0.08,
            col_label, ha="center", va="bottom",
            fontsize=10, weight="bold", color="#222",
        )

    # Row labels at the LEFT.
    for row_idx, label in enumerate(labels):
        ax_portfolio.text(
            -0.08, (n_pos - 1 - row_idx) * cell_h + cell_h / 2, label,
            ha="right", va="center", fontsize=9, color="#333",
        )

    ax_portfolio.set_xlim(-1.8, len(band_cols) * cell_w + 0.3)
    ax_portfolio.set_ylim(-0.2, n_pos * cell_h + 0.7)
    ax_portfolio.set_xticks([])
    ax_portfolio.set_yticks([])
    for spine in ax_portfolio.spines.values():
        spine.set_visible(False)
    ax_portfolio.set_title(
        "Portfolio decisions under each band (collateral $10k per position; debt = LTV-at-origination × $10k)",
        fontsize=10, pad=14,
    )

    # Legend for decision colors — outside the grid on the right.
    legend_patches = [
        mpatches.Patch(color="#2ca02c", label="Safe"),
        mpatches.Patch(color="#ff9800", label="Caution"),
        mpatches.Patch(color="#d62728", label="Liquidate"),
    ]
    ax_portfolio.legend(
        handles=legend_patches, loc="center right",
        bbox_to_anchor=(1.0, 0.5), fontsize=9, framealpha=0.95,
    )

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def summarize(
    kamino_eval: list,
    soothsayer_eval: list,
    realized_eval: list,
) -> dict:
    """Count decisions per band + quantify false-positive liquidations."""
    def counts(evl):
        c = {"Safe": 0, "Caution": 0, "Liquidate": 0}
        for _, d in evl:
            c[d.name] += 1
        return c

    def false_positive_liq(band_evl, realized_evl):
        """Positions where band says Liquidate but realized says not."""
        n = 0
        for (pb, db), (pr, dr) in zip(band_evl, realized_evl):
            if db.name == "Liquidate" and dr.name != "Liquidate":
                n += 1
        return n

    def missed_liq(band_evl, realized_evl):
        """Positions where band passes (Safe/Caution) but realized says Liquidate."""
        n = 0
        for (pb, db), (pr, dr) in zip(band_evl, realized_evl):
            if db.name != "Liquidate" and dr.name == "Liquidate":
                n += 1
        return n

    return {
        "kamino": {
            "counts": counts(kamino_eval),
            "false_positive_liquidations": false_positive_liq(kamino_eval, realized_eval),
            "missed_liquidations": missed_liq(kamino_eval, realized_eval),
        },
        "soothsayer": {
            "counts": counts(soothsayer_eval),
            "false_positive_liquidations": false_positive_liq(soothsayer_eval, realized_eval),
            "missed_liquidations": missed_liq(soothsayer_eval, realized_eval),
        },
        "realized_counts": counts(realized_eval),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Replay a historical shock weekend as Kamino vs Soothsayer.")
    p.add_argument("--date", default="2020-03-13", help="Friday date (YYYY-MM-DD). Default: 2020-03-13 (COVID Monday).")
    p.add_argument("--symbol", default="SPY", help="Symbol. Default: SPY.")
    p.add_argument("--target", type=float, default=0.85, help="Soothsayer target coverage. Default: 0.85 (EL-optimal vs Kamino on OOS bootstrap; see reports/tables/protocol_compare_*.csv).")
    p.add_argument("--kamino-bps", type=int, default=300, help="Kamino flat-band half-width in bps. Default: 300.")
    p.add_argument("--out", type=str, default=None, help="Output PNG path. Default: reports/figures/replay_<SYM>_<DATE>.png")
    args = p.parse_args()

    fri_ts = date.fromisoformat(args.date)
    symbol = args.symbol

    oracle = Oracle.load()

    # Pull fri_close, mon_open, regime from the bounds table (any forecaster row works).
    row = oracle._bounds[
        (oracle._bounds["symbol"] == symbol) & (oracle._bounds["fri_ts"] == fri_ts)
    ].head(1)
    if row.empty:
        print(f"No data for {symbol} @ {fri_ts} — use list_available or pick another date.")
        return 2
    fri_close = float(row["fri_close"].iloc[0])
    mon_open = float(row["mon_open"].iloc[0])
    mon_ts = pd.to_datetime(row["mon_ts"].iloc[0]).date()
    regime = str(row["regime_pub"].iloc[0])

    # Soothsayer band
    pp = oracle.fair_value(symbol, fri_ts, target_coverage=args.target)
    ss_lo, ss_hi, ss_point = float(pp.lower), float(pp.upper), float(pp.point)

    # Kamino flat band
    kamino_lo, kamino_hi = kamino_flat_band(fri_close, args.kamino_bps)

    # Sample portfolio
    portfolio = build_sample_portfolio(fri_close)

    # Evaluate each band + realized counterfactual (under realized regime's threshold)
    kamino_eval = evaluate_portfolio(portfolio, kamino_lo, regime, is_soothsayer=False)
    soothsayer_eval = evaluate_portfolio(
        portfolio, ss_lo, regime, is_soothsayer=True,
        claimed_served=float(pp.claimed_coverage_served),
    )
    realized_eval = evaluate_counterfactual_realized(
        portfolio, mon_open,
        threshold_effective=LIQUIDATION_THRESHOLD * regime_multiplier(regime),
    )

    # Plot
    out_path = Path(args.out) if args.out else (
        REPORTS / "figures" / f"replay_{symbol}_{fri_ts.isoformat()}.png"
    )
    plot(
        symbol=symbol, fri_ts=fri_ts, mon_ts=mon_ts,
        fri_close=fri_close, mon_open=mon_open,
        kamino_lo=kamino_lo, kamino_hi=kamino_hi,
        ss_lo=ss_lo, ss_hi=ss_hi, ss_point=ss_point,
        regime=regime,
        target_coverage=args.target,
        claimed_served=float(pp.claimed_coverage_served),
        forecaster_used=pp.forecaster_used,
        kamino_bps=args.kamino_bps,
        kamino_eval=kamino_eval,
        soothsayer_eval=soothsayer_eval,
        realized_eval=realized_eval,
        out_path=out_path,
    )

    summary = summarize(kamino_eval, soothsayer_eval, realized_eval)

    print("=" * 72)
    print(f"{symbol} shock-weekend replay — {fri_ts} → {mon_ts}")
    print("=" * 72)
    print(f"  regime (pre-publish):   {regime}")
    print(f"  fri_close:              ${fri_close:,.4f}")
    print(f"  mon_open (realized):    ${mon_open:,.4f}  ({(mon_open/fri_close - 1)*1e4:+.0f} bps)")
    print()
    print("  Bands at 95% target:")
    ss_half = (ss_hi - ss_lo) / 2 / ss_point * 1e4
    km_half = float(args.kamino_bps)
    print(f"    Soothsayer:  [{ss_lo:,.3f}, {ss_hi:,.3f}]  ({ss_half:.0f} bps half-width; claim_served={pp.claimed_coverage_served:.3f}; forecaster={pp.forecaster_used})")
    print(f"    Kamino flat: [{kamino_lo:,.3f}, {kamino_hi:,.3f}]  ({km_half:.0f} bps half-width; governance-set)")
    print()
    print(f"  Realized Mon open inside Soothsayer band?  {ss_lo <= mon_open <= ss_hi}")
    print(f"  Realized Mon open inside Kamino flat band? {kamino_lo <= mon_open <= kamino_hi}")
    print()
    print("  Portfolio decisions (5 positions):")
    print(f"    Kamino     counts: {summary['kamino']['counts']}")
    print(f"                 false-positive liquidations (band says Liq but realized says not): {summary['kamino']['false_positive_liquidations']}")
    print(f"                 missed liquidations (band passes but realized says Liq):         {summary['kamino']['missed_liquidations']}")
    print(f"    Soothsayer counts: {summary['soothsayer']['counts']}")
    print(f"                 false-positive liquidations:    {summary['soothsayer']['false_positive_liquidations']}")
    print(f"                 missed liquidations:            {summary['soothsayer']['missed_liquidations']}")
    print(f"    Realized   counts: {summary['realized_counts']}   (god-view ground truth using realized Mon open)")
    print()
    # Narrative
    k_fp, s_fp = summary["kamino"]["false_positive_liquidations"], summary["soothsayer"]["false_positive_liquidations"]
    k_miss, s_miss = summary["kamino"]["missed_liquidations"], summary["soothsayer"]["missed_liquidations"]
    if s_fp < k_fp:
        print(f"  → Soothsayer avoided {k_fp - s_fp} false-positive liquidation(s) that Kamino triggered.")
    elif s_fp > k_fp:
        print(f"  → Soothsayer triggered {s_fp - k_fp} extra false-positive liquidation(s) vs Kamino.")
    if s_miss < k_miss:
        print(f"  → Soothsayer caught {k_miss - s_miss} risky position(s) Kamino missed.")
    elif s_miss > k_miss:
        print(f"  → Kamino caught {s_miss - k_miss} risky position(s) Soothsayer missed.")
    print()
    print(f"  Figure: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
