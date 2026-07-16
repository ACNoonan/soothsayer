"""Build the Paper 1 hero figure H3 — promised-vs-delivered coverage.

One-glance question the figure answers (revision directive, 2026-07):
"Each method promised a coverage level — did it deliver?"

Form: for each of the four promised anchors tau in {0.68, 0.85, 0.95,
0.99}, delivered coverage is shown as its distance from the promise
(delivered − promised, percentage points). The vertical zero line is
"promise kept exactly"; the grey band per row is the exact binomial 95%
acceptance region (n = 1,730) — where a truly calibrated method may land
by chance. Deployed (blue dots) sits inside the band at all four
promises; GARCH(1,1)-t (vermilion squares) falls short at three. The
half-width story is carried as one sentence of ink on the figure.

Data sources (identical to the previous H3 composition):

  reports/tables/m6_pooled_oos.csv                       (deployed, pooled OOS)
  reports/tables/m6_lwc_robustness_garch_t_baseline.csv  (GARCH(1,1)-t)

Restricted to methods that emit a calibrated coverage band — no incumbent
oracle surfaces, no internal codenames in artwork (revision_critique A1/A5).

Run:
  uv run python -u scripts/build_fig_h3.py
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from scipy.stats import binom

from soothsayer.config import REPORTS

FIG_DIR = REPORTS / "paper1_coverage_inversion" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLES = REPORTS / "tables"

TAUS = (0.68, 0.85, 0.95, 0.99)

# Okabe-Ito palette (colorblind-safe) — matches build_paper1_figures.py.
OI = {
    "black":     "#000000",
    "blue":      "#0072B2",
    "vermilion": "#D55E00",
    "grey":      "#777777",
}
INK = "#1A1A1A"          # text ink — labels never wear the series colour
BAND_FC = "#D9D9D9"      # acceptance-region fill


def setup_rc() -> None:
    """Identical rcParams to build_paper1_figures.py::setup_rc."""
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


# ------------------------------------------------------------------- data


def _load_garch_t() -> pd.DataFrame:
    """GARCH(1,1)-t baseline at the four served anchors."""
    garch = pd.read_csv(TABLES / "m6_lwc_robustness_garch_t_baseline.csv")
    if "garch_dist" in garch.columns:
        garch = garch[garch["garch_dist"] == "t"]
    if "method" in garch.columns:
        # The CSV also carries LWC_deployed comparison rows; keep only the
        # GARCH(1,1)-t baseline proper.
        garch = garch[garch["method"] == "GARCH(1,1)-t"]
    return garch.sort_values("tau")


def _load_deployed_pooled() -> pd.DataFrame:
    """Deployed architecture pooled-OOS rows at the four served anchors."""
    pooled = pd.read_csv(TABLES / "m6_pooled_oos.csv")
    return pooled[(pooled["forecaster"] == "lwc")
                  & (pooled["stratification"] == "pooled")].sort_values("tau")


# ------------------------------------------------------------------- plot


def build_h3() -> None:
    garch = _load_garch_t().set_index("tau")
    m6 = _load_deployed_pooled().set_index("tau")
    n = int(m6["n"].iloc[0])  # 1,730 pooled OOS weekends

    fig, ax = plt.subplots(figsize=(6.6, 4.6))

    # Rows: one per promise, 68% at the top.
    ys = {tau: i for i, tau in enumerate(TAUS)}
    ROW_H = 0.30  # half-height of the acceptance-region band

    for tau in TAUS:
        y = ys[tau]
        # Exact binomial 95% acceptance region around the promise,
        # expressed as delivered − promised in percentage points.
        lo_cnt, hi_cnt = binom.interval(0.95, n, tau)
        lo_pp = (lo_cnt / n - tau) * 100.0
        hi_pp = (hi_cnt / n - tau) * 100.0
        ax.add_patch(Rectangle(
            (lo_pp, y - ROW_H), hi_pp - lo_pp, 2 * ROW_H,
            facecolor=BAND_FC, edgecolor="none", zorder=1,
        ))

        d_dep = (float(m6.loc[tau, "realised"]) - tau) * 100.0
        d_gar = (float(garch.loc[tau, "realised"]) - tau) * 100.0

        # Thin connector pairs the two marks within a row.
        ax.plot([d_gar, d_dep], [y, y], color="#BBBBBB", lw=0.7, zorder=2)

        ax.scatter([d_dep], [y], s=78, color=OI["blue"], zorder=4,
                   edgecolor="white", linewidth=0.8)
        ax.scatter([d_gar], [y], s=52, color=OI["vermilion"], marker="s",
                   zorder=4, edgecolor="white", linewidth=0.8)

        # Delivered values in ink beside each mark (white halo so the
        # zero line never strikes through a label).
        ax.annotate(f"{m6.loc[tau, 'realised'] * 100:.1f}%",
                    (d_dep, y), xytext=(0, 9), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7.5, color=INK,
                    zorder=5,
                    bbox=dict(facecolor="white", edgecolor="none",
                              pad=0.6, alpha=0.85))
        ax.annotate(f"{garch.loc[tau, 'realised'] * 100:.1f}%",
                    (d_gar, y), xytext=(0, -10), textcoords="offset points",
                    ha="center", va="top", fontsize=7.5, color=INK)

    # Zero line = the promise itself.
    ax.axvline(0.0, color=INK, lw=1.0, zorder=3)
    ax.annotate("promise kept exactly", xy=(0.0, -0.72),
                ha="center", va="bottom", fontsize=7.5, color=INK,
                annotation_clip=False, zorder=5,
                bbox=dict(facecolor="white", edgecolor="none",
                          pad=0.6, alpha=0.9))

    # Direct series labels (ink text, identity carried by the mark it names).
    d_dep0 = (float(m6.loc[0.68, "realised"]) - 0.68) * 100.0
    d_gar0 = (float(garch.loc[0.68, "realised"]) - 0.68) * 100.0
    ax.annotate("deployed architecture\n(this paper)",
                xy=(d_dep0, 0.08), xytext=(2.15, 0.55),
                fontsize=8.0, color=INK, ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"]))
    ax.annotate("GARCH(1,1)-$t$\nbaseline",
                xy=(d_gar0, 0.10), xytext=(-3.75, 0.85),
                fontsize=8.0, color=INK, ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"]))

    # Acceptance-region label, once, pointing at the narrow 99% band —
    # the lower-right quadrant is empty.
    lo_cnt, hi_cnt = binom.interval(0.95, n, 0.99)
    hi_pp99 = (hi_cnt / n - 0.99) * 100.0
    ax.annotate("grey: consistent with a kept\npromise (binomial 95%)",
                xy=(hi_pp99, 3.0), xytext=(1.35, 2.95),
                fontsize=7.5, color=OI["grey"], ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"]))

    ax.set_yticks([ys[t] for t in TAUS])
    ax.set_yticklabels([f"{t * 100:.0f}%" for t in TAUS])
    ax.set_ylabel("promised coverage " + r"$\tau$")
    ax.set_xlabel("delivered coverage minus promised (percentage points)")
    ax.set_xticks([-3, -2, -1, 0, 1, 2, 3])
    ax.set_xticklabels(["−3", "−2", "−1", "0",
                        "+1", "+2", "+3"])
    ax.set_xlim(-3.9, 3.1)
    ax.set_ylim(3.85, -1.05)  # 68% on top
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    ax.set_title(
        "Each method promised a coverage level — did it deliver?",
        fontsize=11.5, fontweight="bold", pad=30, loc="left",
    )
    ax.text(0.0, 1.03,
            "Delivered minus promised coverage, 1,730 held-out weekends "
            "(2023+).",
            transform=ax.transAxes, fontsize=8.3, color="#444444",
            ha="left", va="bottom")

    # Width story — one sentence of ink under the axis, so "narrower
    # bands" cannot be read as a GARCH win.
    ax.text(0.0, -0.175,
            "Widened after the fact to matched 95% delivered coverage, "
            "GARCH-$t$ needs 378 bps vs 371 (tied) —\n"
            "but only the deployed band stated its coverage in advance.",
            transform=ax.transAxes, fontsize=7.8, color=INK,
            ha="left", va="top")

    out_pdf = FIG_DIR / "fig_h3_calibration_pareto.pdf"
    out_png = FIG_DIR / "fig_h3_calibration_pareto.png"
    plt.savefig(out_pdf)
    plt.savefig(out_png, dpi=200)
    plt.close(fig)
    print(f"  wrote {out_pdf}")
    print(f"  wrote {out_png}")


def main() -> None:
    setup_rc()
    build_h3()


if __name__ == "__main__":
    main()
