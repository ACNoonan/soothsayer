"""
Build Figure H4 — "Does the band widen BEFORE a scheduled earnings release —
and does the actual move land inside it?"

Replaces fig11_earnings_event_study as the earnings exhibit (fig11 is left
untouched). Reviewer verdict on fig11: per-event baseline-normalised units
("multiple of the event's own pre-event baseline width") don't communicate
to a protocol engineer; this redesign stays in bps of the previous close.

Design (one question, one glance):
  Event time on x (trading nights relative to the release, -3..+3). The
  served tau = 0.95 band half-width (median across all releases, bps) is a
  step that sits at ~220 bps on ordinary nights and jumps ~7x on the
  release night — annotated as SCHEDULED widening (the release date is on
  the public earnings calendar; the wide band is published before the
  close, it is not a reaction). Realized |close -> open| moves are overlaid
  as median dots with p10-p90 whiskers, and stay under the step everywhere
  — including the release night. The exact out-of-sample verdict (98.3% of
  n = 60 held-out earnings-night opens inside the tau = 0.95 band) is
  printed on the figure.

Data: same construction as fig11 in scripts/build_paper1_figures.py —
overnight_artefact_v1.{parquet,json} (deployed schedules; byte-for-byte
what a consumer reads) joined to overnight_panel.parquet for realized
opens; per-symbol night sequences, releases aligned at t = 0 (228
releases, 10 symbols). The coverage annotation is recomputed on the
held-out (>= 2023-01-01) slice. All caption numbers are recomputed and
asserted below — a mismatch is a hard error, not a silent caption edit.

Style matches scripts/build_paper1_figures.py (Okabe-Ito, serif + cm
mathtext, 6.0 in single-column width, vector PDF + 200 dpi PNG).

Run:
  uv run python -u scripts/build_fig_h4.py
"""

from __future__ import annotations

import json
from datetime import date

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from soothsayer.backtest.calibration import compute_score_lwc
from soothsayer.config import DATA_PROCESSED, REPORTS

FIG_DIR = REPORTS / "paper1_coverage_inversion" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

SPLIT_DATE = date(2023, 1, 1)
TAU = "0.95"
OFFSETS = list(range(-3, 4))

# Okabe-Ito palette (colorblind-safe) — matches build_paper1_figures.py.
OI = {
    "black": "#000000",
    "blue": "#0072B2",
    "vermilion": "#D55E00",
    "grey": "#777777",
}

# Caption contract — recomputed below and asserted.
CAPTION = {
    "n_events": 228,
    "band_t0_bps": 1620,        # median served half-width on release night
    "band_adj_bps": 225,        # median served half-width on nights +/-1
    "band_ratio": 7.2,          # t0 / adjacent (ratio of medians)
    "move_t0_bps": 410,         # median realized |move| on release night
    "move_t0_p90_bps": 1003,    # p90 realized |move| on release night
    "move_adj_bps": 54,         # median realized |move| on nights +/-1
    "n_earn_oos": 60,
    "cov_earn_oos": 0.9833,     # OOS earnings-night coverage at tau=0.95
}


def setup_rc() -> None:
    mpl.rcParams.update({
        "text.usetex": False,
        "mathtext.fontset": "cm",
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times"],
        "font.size": 10,
        "axes.labelsize": 10,
        "axes.titlesize": 11,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.7,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "lines.linewidth": 1.4,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,
    })


# ============================================================== data


def event_time_stats() -> tuple[dict, int]:
    """Median served half-width and realized-|move| quantiles (bps) at each
    night offset around every earnings release — fig11's construction, kept
    in absolute bps instead of per-event baseline units."""
    art = pd.read_parquet(DATA_PROCESSED / "overnight_artefact_v1.parquet")
    side = json.loads(
        (DATA_PROCESSED / "overnight_artefact_v1.json").read_text())
    qt, cb = side["regime_quantile_table"], side["c_bump_schedule"]

    panel = pd.read_parquet(DATA_PROCESSED / "overnight_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"])
    art["fri_ts"] = pd.to_datetime(art["fri_ts"])
    art = art.merge(panel[["symbol", "fri_ts", "mon_open"]],
                    on=["symbol", "fri_ts"], how="left")
    art["hw_bps"] = (
        float(cb[TAU])
        * art["regime_pub"].map({r: float(qt[r][TAU]) for r in qt})
        * art["sigma_hat_sym_pre_fri"] * 1.0e4
    )
    art["abs_move_bps"] = (
        (art["mon_open"] / art["fri_close"] - 1.0).abs() * 1.0e4)

    widths = {k: [] for k in OFFSETS}
    moves = {k: [] for k in OFFSETS}
    n_events = 0
    for _, grp in art.groupby("symbol"):
        grp = grp.sort_values("fri_ts").reset_index(drop=True)
        for i in grp.index[grp["regime_pub"] == "earnings_night"]:
            n_events += 1
            for k in OFFSETS:
                j = i + k
                if 0 <= j < len(grp):
                    widths[k].append(float(grp.loc[j, "hw_bps"]))
                    mv = float(grp.loc[j, "abs_move_bps"])
                    if np.isfinite(mv):
                        moves[k].append(mv)

    stats = {
        "band_med": {k: float(np.median(widths[k])) for k in OFFSETS},
        "mv_med": {k: float(np.median(moves[k])) for k in OFFSETS},
        "mv_p10": {k: float(np.percentile(moves[k], 10)) for k in OFFSETS},
        "mv_p90": {k: float(np.percentile(moves[k], 90)) for k in OFFSETS},
    }
    stats["band_adj_med"] = float(np.median(widths[-1] + widths[1]))
    stats["mv_adj_med"] = float(np.median(moves[-1] + moves[1]))
    return stats, n_events


def oos_earnings_coverage() -> tuple[float, int]:
    """Held-out earnings-night coverage at tau = 0.95, served from the
    deployed schedules (same recompute as build_fig_s2.py)."""
    panel = pd.read_parquet(DATA_PROCESSED / "overnight_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel["point"] = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float))
    panel["score"] = compute_score_lwc(panel, scale_col="sigma_hat_sym_pre_fri")
    oos = panel[
        panel["score"].notna() & panel["sigma_hat_sym_pre_fri"].notna()
        & (panel["fri_ts"] >= SPLIT_DATE)
    ].reset_index(drop=True)

    side = json.loads(
        (DATA_PROCESSED / "overnight_artefact_v1.json").read_text())
    qt, cb = side["regime_quantile_table"], side["c_bump_schedule"]
    earn = oos[oos["regime_pub"] == "earnings_night"]
    q = earn["regime_pub"].map(
        {r: float(qt[r][TAU]) for r in qt}).astype(float)
    half = float(cb[TAU]) * q * earn["sigma_hat_sym_pre_fri"] * earn["fri_close"]
    inside = (earn["mon_open"] >= earn["point"] - half) & (
        earn["mon_open"] <= earn["point"] + half)
    return float(inside.mean()), int(len(earn))


# ============================================================ figure


def build() -> None:
    stats, n_events = event_time_stats()
    cov, n_earn = oos_earnings_coverage()

    # ---- verify against the caption contract.
    checks = [
        ("n events", n_events, CAPTION["n_events"]),
        ("band t0 (bps)", round(stats["band_med"][0]), CAPTION["band_t0_bps"]),
        ("band adjacent (bps)", round(stats["band_adj_med"]),
         CAPTION["band_adj_bps"]),
        ("band ratio t0/adjacent",
         round(stats["band_med"][0] / stats["band_adj_med"], 1),
         CAPTION["band_ratio"]),
        ("move t0 median (bps)", round(stats["mv_med"][0]),
         CAPTION["move_t0_bps"]),
        ("move t0 p90 (bps)", round(stats["mv_p90"][0]),
         CAPTION["move_t0_p90_bps"]),
        ("move adjacent median (bps)", round(stats["mv_adj_med"]),
         CAPTION["move_adj_bps"]),
        ("OOS earnings nights", n_earn, CAPTION["n_earn_oos"]),
        ("OOS earnings coverage τ=0.95", round(cov, 4),
         CAPTION["cov_earn_oos"]),
    ]
    for name, got, want in checks:
        status = "OK " if got == want else "MISMATCH"
        print(f"  [{status}] {name}: computed {got} vs caption {want}")
        assert got == want, f"{name}: computed {got} != caption {want}"

    fig, ax = plt.subplots(figsize=(6.0, 3.9))

    # Served band as a per-night step (each night's level spans the night).
    edges = np.array([k - 0.5 for k in OFFSETS] + [OFFSETS[-1] + 0.5])
    meds = np.array([stats["band_med"][k] for k in OFFSETS])
    xs = np.repeat(edges, 2)[1:-1]
    ys = np.repeat(meds, 2)
    ax.fill_between(xs, 0.0, ys, color=OI["blue"], alpha=0.10, lw=0, zorder=1)
    ax.plot(xs, ys, color=OI["blue"], lw=2.0, zorder=3,
            solid_joinstyle="miter")

    # Realized |move|: median dot + p10–p90 whisker per night.
    for k in OFFSETS:
        ax.plot([k, k], [stats["mv_p10"][k], stats["mv_p90"][k]],
                color=OI["vermilion"], lw=1.1, zorder=4)
        for q in ("mv_p10", "mv_p90"):
            ax.plot([k - 0.07, k + 0.07], [stats[q][k]] * 2,
                    color=OI["vermilion"], lw=1.1, zorder=4)
        ax.plot([k], [stats["mv_med"][k]], marker="o", ms=5.5,
                color=OI["vermilion"], mec="black", mew=0.4, zorder=5)

    # ---- direct labels.
    ax.text(0, stats["band_med"][0] + 55,
            f"{stats['band_med'][0]:,.0f} bps — "
            f"{stats['band_med'][0] / stats['band_adj_med']:.1f}"
            r"$\times$ the adjacent nights",
            ha="center", va="bottom", fontsize=8.5, color=OI["blue"],
            fontweight="bold")
    ax.text(-2.45, stats["band_med"][-3] + 60,
            f"ordinary nights: band ≈{stats['band_adj_med']:.0f} bps",
            ha="left", va="bottom", fontsize=8.0, color=OI["blue"])
    ax.annotate(
        "widening is scheduled in advance\n"
        "from the public earnings calendar,\n"
        "so the wide band is published\n"
        "before the close — not a reaction",
        xy=(-0.52, 1560.0), xytext=(-3.35, 1390.0),
        fontsize=7.8, color=OI["black"], ha="left", va="top",
        arrowprops=dict(arrowstyle="->", lw=0.8, color=OI["grey"],
                        shrinkA=6, shrinkB=2,
                        connectionstyle="arc3,rad=-0.18"),
    )
    ax.annotate(
        f"release-night move: median {stats['mv_med'][0]:.0f} bps\n"
        f"(≈{stats['mv_med'][0] / stats['mv_adj_med']:.0f}"
        r"$\times$ an ordinary night)"
        " — still inside the band",
        xy=(0.08, stats["mv_med"][0]), xytext=(0.65, 620.0),
        fontsize=8.0, color=OI["vermilion"], va="center",
        arrowprops=dict(arrowstyle="->", lw=0.8, color=OI["vermilion"],
                        shrinkA=4, shrinkB=3),
    )
    ax.text(
        3.35, 1620.0,
        "held-out earnings nights (n = 60):\n"
        f"{cov:.1%} of opens landed inside\n"
        r"the $\tau = 0.95$ band (promised 95%)",
        ha="right", va="top", fontsize=8.0, color=OI["black"],
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                  edgecolor=OI["grey"], linewidth=0.6),
    )

    # Legend.
    handles = [
        Patch(facecolor=OI["blue"], alpha=0.10, edgecolor=OI["blue"],
              linewidth=1.2,
              label=r"served band half-width, median ($\tau = 0.95$)"),
        Line2D([0], [0], marker="o", ms=5.5, color=OI["vermilion"],
               mec="black", mew=0.4, lw=1.1,
               label=r"realized $|$close$\to$open$|$ move "
                     "(median, p10–p90)"),
    ]
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.185), ncol=2, frameon=False,
              fontsize=8.0, handletextpad=0.5, columnspacing=1.4)

    ax.set_title(
        "The band widens ~7$\\times$ for the night of a scheduled earnings "
        "release —\nbefore the close — and the realized move lands inside it",
        fontsize=10.5, loc="left", pad=10)

    ax.set_xticks(OFFSETS)
    ax.set_xticklabels([f"{k:+d}" if k else "release\nnight"
                        for k in OFFSETS])
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(0, 2000)
    ax.set_xlabel(f"trading nights relative to the earnings release "
                  f"({n_events} releases, 10 symbols)")
    ax.set_ylabel("bps of the previous close")

    out = FIG_DIR / "fig_h4_earnings.pdf"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=200)
    plt.close(fig)
    print(f"  wrote {out}")
    print(f"  wrote {out.with_suffix('.png')}")


if __name__ == "__main__":
    setup_rc()
    build()
