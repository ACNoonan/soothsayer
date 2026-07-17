"""
Build the redesigned H5 main-text figure (joint-tail k_w at tau = 0.95).

Replaces the log-scale three-series fig10 read with a single plain-language
question a protocol engineer can answer at a glance:

    "When bands break, how many of your ten positions break on the SAME
     weekend -- and what should you reserve for?"

Design (reviewer verdict on fig10):
  * linear scale, weekend COUNTS (not log probabilities);
  * observed counts as Okabe-Ito blue bars, expected-if-independent as
    thin grey OUTLINE ghost bars behind them (fill-vs-outline is the
    secondary encoding, so identity is never color-alone);
  * title carries the claim; direct labels in words, no legend box;
  * k* = 3 reserve threshold marked in vermilion (the only vermilion ink);
  * the single k_w = 9 weekend (2024-08-05 BoJ unwind) annotated with the
    tau = 0.95 joint-model vs independence rarity numbers;
  * reserve statement strip (99th percentile ~= 5 simultaneous breaches);
  * the t-copula curve is dropped from this main-text figure -- it
    survives in the appendix original (fig10) and the SS8 prose.

Data: same source as fig10 -- reports/tables/
paper1_a3_joint_baseline_kw_distribution.csv (tau = 0.95 rows), n = 173
OOS weekends. Independence ghost uses the EXACT Binom(10, 0.05) pmf
(math.comb), which reproduces SS8's 1.15% tail (the CSV's P_binom column
is Monte-Carlo and matches to sampling noise).

Outputs:
  research/coverage-inversion/figures/fig_h5_joint_tail.pdf
  research/coverage-inversion/figures/fig_h5_joint_tail.png

Run:
  uv run python -u scripts/build_fig_h5.py
"""

from __future__ import annotations

from math import comb

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soothsayer.config import REPORTS, RESEARCH

FIG_DIR = RESEARCH / "coverage-inversion" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLES = REPORTS / "tables"

N_WEEKENDS = 173
N_SYMBOLS = 10
TAU = 0.95

# Okabe-Ito (matches build_paper1_figures.py OI dict).
BLUE = "#0072B2"       # observed
GREY = "#777777"       # independence ghost outline / muted ink
VERMILION = "#D55E00"  # k* marker ONLY
INK = "#000000"


def setup_rc() -> None:
    """Match build_paper1_figures.py setup_rc exactly."""
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


def load_observed_counts() -> pd.Series:
    """Observed weekend counts by k_w at tau = 0.95, from the fig10 CSV."""
    df = pd.read_csv(TABLES / "paper1_a3_joint_baseline_kw_distribution.csv")
    df = df[np.isclose(df["target"], TAU)].sort_values("k")
    counts = (df.set_index("k")["P_emp"] * N_WEEKENDS).round().astype(int)
    assert counts.sum() == N_WEEKENDS, f"counts sum {counts.sum()} != {N_WEEKENDS}"
    return counts


def binom_pmf(k: int, n: int = N_SYMBOLS, p: float = 1.0 - TAU) -> float:
    return comb(n, k) * p**k * (1.0 - p) ** (n - k)


def verify_section8_numbers(counts: pd.Series) -> None:
    """Reproduce the SS8 / SS6.3.4 headline numbers from the plotted data."""
    p_emp_ge3 = counts.loc[counts.index >= 3].sum() / N_WEEKENDS
    p_binom_ge3 = sum(binom_pmf(k) for k in range(3, N_SYMBOLS + 1))
    max_k = int(counts.index[counts > 0].max())
    print("  -- SS8 numbers check --")
    print(f"  P_emp(k_w >= 3)   = {p_emp_ge3:.4f}  (paper: 0.0462) "
          f"[{counts.loc[counts.index >= 3].sum()} of {N_WEEKENDS} weekends]")
    print(f"  P_binom(k_w >= 3) = {p_binom_ge3:.4f}  (paper: 0.0115)")
    print(f"  max observed k_w  = {max_k}       (paper: 9)")
    assert abs(p_emp_ge3 - 0.0462) < 5e-4
    assert abs(p_binom_ge3 - 0.0115) < 5e-4
    assert max_k == 9
    # BoJ-bar annotation numbers (tau = 0.95, k >= 9), from the same CSV's
    # fitted t-copula column and the exact binomial:
    df = pd.read_csv(TABLES / "paper1_a3_joint_baseline_kw_distribution.csv")
    df = df[np.isclose(df["target"], TAU)]
    p_t_ge9 = df.loc[df["k"] >= 9, "P_t_copula"].sum()
    p_b_ge9 = binom_pmf(9) + binom_pmf(10)
    print(f"  P_t-copula(k_w >= 9) = {p_t_ge9:.5f}  (~1 in {1 / p_t_ge9:,.0f} weekends)")
    print(f"  P_binom(k_w >= 9)    = {p_b_ge9:.2e}  (~1 in {1 / p_b_ge9:,.0f})")
    print("  all checks passed")


def build_figure(counts: pd.Series) -> None:
    ks = np.arange(1, N_SYMBOLS + 1)  # k = 0 stated in words, not plotted
    obs = np.array([counts.get(k, 0) for k in ks], dtype=float)
    ind = np.array([binom_pmf(k) * N_WEEKENDS for k in ks])

    fig, ax = plt.subplots(figsize=(6.0, 3.9))

    # Independence ghost: thin grey outline bars behind the observed bars.
    ax.bar(ks, ind, width=0.74, facecolor="none", edgecolor=GREY,
           lw=1.0, zorder=2)
    # Observed: solid blue bars in front.
    ax.bar(ks, obs, width=0.5, color=BLUE, zorder=3)

    # Count labels above each nonzero observed bar (ink, not series color).
    for k, c in zip(ks, obs):
        if c > 0:
            ax.text(k, c + 0.9, f"{int(c)}", ha="center", va="bottom",
                    fontsize=8, color=INK, zorder=5)

    # Direct series labels (no legend box).
    ax.annotate("expected if independent",
                xy=(1.32, 54.8), xytext=(1.55, 55.3), fontsize=8.5,
                color=GREY, ha="left", va="bottom",
                arrowprops=dict(arrowstyle="-", lw=0.7, color=GREY))
    ax.annotate("observed",
                xy=(1.28, 15.5), xytext=(1.68, 15.1), fontsize=8.5,
                color=BLUE, ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.7, color=BLUE))

    # k* = 3 reserve threshold (the only vermilion ink). Stops below the
    # grey series label so the dashed line never crosses text.
    ax.axvline(2.5, ymax=53.0 / 60.0, color=VERMILION, lw=1.0, ls="--",
               alpha=0.9, zorder=2)
    ax.text(2.66, 51.5, r"$k^\ast = 3$: reserve threshold",
            fontsize=8.5, ha="left", va="top", color=VERMILION)

    # Reserve statement (single line, tied to the k* label above it).
    ax.text(2.85, 46.5,
            "reserve sizing: 99th percentile $\\approx$ 5 simultaneous breaches",
            fontsize=8.5, ha="left", va="top", color=INK)

    # BoJ weekend annotation on the k = 9 bar.
    ax.annotate(
        "2024-08-05 BoJ unwind: 9 of 10 broke at once\n"
        "$\\approx$1-in-1,100 under the fitted joint model; "
        "$\\approx$1-in-$10^{11}$ if independent",
        xy=(9.0, 1.8), xytext=(10.6, 9.0), fontsize=8, color=INK,
        ha="right", va="bottom", linespacing=1.4,
        arrowprops=dict(arrowstyle="->", lw=0.7, color=GREY,
                        connectionstyle="arc3,rad=-0.18",
                        relpos=(0.82, 0.0)))

    ax.set_xlim(0.3, 10.7)
    ax.set_ylim(0, 60)
    ax.set_xticks(ks)
    ax.set_yticks([0, 10, 20, 30, 40, 50])
    ax.set_xlabel("positions breaching their $\\tau = 0.95$ band "
                  "on the same weekend ($k_w$ of 10)")
    ax.set_ylabel("weekends (of 173 out-of-sample)")

    ax.set_title(
        "Bands break together: 3+ at once happens "
        "4$\\times$ what independence predicts",
        fontsize=10.5, loc="left", pad=10)

    # k = 0 disclosure in muted ink under the title, inside the axes.
    ax.text(10.6, 57.5, "121/173 weekends: zero breaches (omitted)",
            fontsize=7.5, color=GREY, ha="right", va="top")

    plt.tight_layout()
    for ext in ("pdf", "png"):
        out = FIG_DIR / f"fig_h5_joint_tail.{ext}"
        fig.savefig(out, dpi=300)
        print(f"  wrote {out}")
    plt.close(fig)


def main() -> None:
    setup_rc()
    counts = load_observed_counts()
    verify_section8_numbers(counts)
    build_figure(counts)


if __name__ == "__main__":
    main()
