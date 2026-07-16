"""Build Paper 1 figure S1 — per-symbol calibration at tau = 0.95.

One-glance question the figure answers (revision directive, 2026-07):
"Is every individual symbol calibrated, or only the average?"

Form: per-symbol violation rate at tau = 0.95, symbols on the y-axis
(ordered by the comparator's miss rate), violation rate on the x-axis.
The nominal 5% miss rate is a vertical line with the per-symbol exact
binomial 95% acceptance band (n = 173) shaded around it. Deployed (blue
dots) sits inside the band for all ten symbols; the unweighted-Mondrian
comparator (grey x) fails in BOTH directions — heavy-tail names breach
far too often (under-covers, 11.6–15.6%), defensive names almost never
(over-covers: bands wider than needed). The two failure directions are
labeled in words on the figure.

Data sources (same as fig4_per_symbol in build_paper1_figures.py):

  reports/tables/m6_lwc_robustness_per_symbol.csv   (deployed, per symbol)
  reports/tables/m6_per_symbol_kupiec_4methods.csv  (comparator, method=m5)

Outputs are NEW files — fig4_per_symbol is left untouched:

  reports/paper1_coverage_inversion/figures/fig_s1_per_symbol.{pdf,png}

Run:
  uv run python -u scripts/build_fig_s1.py
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binom

from soothsayer.config import REPORTS

FIG_DIR = REPORTS / "paper1_coverage_inversion" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLES = REPORTS / "tables"

TAU = 0.95

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


def _load() -> pd.DataFrame:
    """Per-symbol violation rates at tau = 0.95: deployed + comparator."""
    dep = pd.read_csv(TABLES / "m6_lwc_robustness_per_symbol.csv")
    dep = dep[["symbol", "n_oos", "viol_rate_0.95"]].rename(
        columns={"viol_rate_0.95": "deployed"})

    grid = pd.read_csv(TABLES / "m6_per_symbol_kupiec_4methods.csv")
    m5 = (grid[(grid["method"] == "m5") & np.isclose(grid["tau"], TAU)]
          [["symbol", "viol_rate"]].rename(columns={"viol_rate": "comparator"}))

    df = dep.merge(m5, on="symbol", how="inner")
    # Order rows by the comparator's miss rate — under-coverers at the
    # top, over-coverers pinned at zero at the bottom; the two failure
    # directions become two visible clusters.
    return (df.sort_values(["comparator", "deployed"], ascending=False)
              .reset_index(drop=True))


# ------------------------------------------------------------------- plot


def build_s1() -> None:
    df = _load()
    n = int(df["n_oos"].iloc[0])  # 173 OOS weekends per symbol

    # Exact binomial 95% acceptance band around the nominal 5% miss rate.
    lo_cnt, hi_cnt = binom.interval(0.95, n, 1.0 - TAU)
    lo_pct = 100.0 * lo_cnt / n
    hi_pct = 100.0 * hi_cnt / n

    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    y = np.arange(len(df))

    ax.axvspan(lo_pct, hi_pct, color=BAND_FC, zorder=0)
    ax.axvline(5.0, color=INK, lw=1.0, ls="--", zorder=1)

    dep_pct = 100.0 * df["deployed"].to_numpy()
    cmp_pct = 100.0 * df["comparator"].to_numpy()

    # Thin connectors pair the two marks per symbol.
    for yi, d, c in zip(y, dep_pct, cmp_pct):
        ax.plot([min(d, c), max(d, c)], [yi, yi],
                color="#BBBBBB", lw=0.7, zorder=2)

    ax.scatter(cmp_pct, y, color=OI["grey"], marker="x", s=58,
               linewidth=1.6, zorder=3)
    ax.scatter(dep_pct, y, color=OI["blue"], s=64, zorder=4,
               edgecolor="white", linewidth=0.8)

    ax.set_yticks(y)
    ax.set_yticklabels(df["symbol"], fontsize=9)
    ax.invert_yaxis()  # worst comparator row on top
    ax.set_xlim(-0.8, 17.6)
    ax.set_ylim(len(df) - 0.5, -0.9)
    ax.set_xlabel("weekends outside the promised 95% band "
                  f"(% of {n} out-of-sample weekends)")
    ax.set_xticks([0, 5, 10, 15])
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    # Nominal + band labels (ink / grey, never series colour).
    ax.annotate("promised miss rate: 5%", xy=(5.0, -0.62),
                ha="center", va="bottom", fontsize=7.5, color=INK,
                annotation_clip=False, zorder=5,
                bbox=dict(facecolor="white", edgecolor="none",
                          pad=0.8, alpha=0.9))
    ax.annotate("grey band: consistent with\nthe promise (binomial 95%, "
                f"n = {n})",
                xy=(hi_pct, 6.9), xytext=(hi_pct + 1.3, 6.9),
                fontsize=7.5, color=OI["grey"], ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"]))

    # Direct series labels.
    ax.annotate("deployed (this paper)",
                xy=(dep_pct[0] + 0.15, 0.12), xytext=(5.9, 0.85),
                fontsize=8.0, color=INK, ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"]))
    ax.annotate("unweighted Mondrian\ncomparator",
                xy=(cmp_pct[1], 1.12), xytext=(14.3, 1.95),
                fontsize=8.0, color=INK, ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"]))

    # The two failure directions, in words.
    ax.annotate("under-covers: breaches 2–3x\nmore often than promised",
                xy=(cmp_pct[2], 2.12), xytext=(9.9, 3.7),
                fontsize=7.8, color=INK, ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"]))
    ax.annotate("over-covers: almost never breaches —\nbands wider than "
                "needed",
                xy=(cmp_pct[-1] + 0.15, len(df) - 1.08),
                xytext=(9.6, len(df) - 1.55),
                fontsize=7.8, color=INK, ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"],
                                connectionstyle="arc3,rad=0.12"))

    ax.set_title(
        "All ten symbols individually calibrated — "
        "the comparator only averages out",
        fontsize=11.5, fontweight="bold", pad=46, loc="left",
    )
    ax.text(0.0, 1.03,
            "Per-symbol share of weekends where Monday's open fell outside "
            "the promised 95% band (2023+ out-of-sample).\n"
            "Every deployed dot lands in the acceptance band; the comparator "
            "misses it for 8 of 10 symbols, in both directions.",
            transform=ax.transAxes, fontsize=8.3, color="#444444",
            ha="left", va="bottom")

    out_pdf = FIG_DIR / "fig_s1_per_symbol.pdf"
    out_png = FIG_DIR / "fig_s1_per_symbol.png"
    plt.savefig(out_pdf)
    plt.savefig(out_png, dpi=200)
    plt.close(fig)
    print(f"  wrote {out_pdf}")
    print(f"  wrote {out_png}")


def main() -> None:
    setup_rc()
    build_s1()


if __name__ == "__main__":
    main()
