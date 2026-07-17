"""
Build Figures H1a + H1b — "The blind window" — the Paper 1 hero pair.

Two standalone figures (§1.1 caption contract, rewrite/01_blind_window.md;
split from the original combined H1 after reviewer feedback that the two
panels represent different things):

  H1a  fig_h1a_week_timeline — one wall-clock week (Mon 00:00 →
       Sun 24:00 ET) for a US-listed equity, coloured by reference-
       market state. One blue hue on a light→dark lightness ramp
       ordered by "closedness": regular session (lightest) →
       after-hours → overnight → weekend (darkest). Direct labels for
       the 65.5-hour Friday-close→Monday-open span and the
       32.5-of-168-hours regular-session fact. Compact strip aspect
       (~6.0 × 1.8 in) — an inline exhibit, not a full plot.

  H1b  fig_h1b_gap_distributions — realised |close→open| gap densities
       (bps, log-x) on the evaluation panels: 5,996 weekend windows
       (v1b_panel.parquet), 22,624 overnight windows
       (overnight_panel.parquet), and the 229-row earnings-night subset
       (regime_pub == "earnings_night" in the overnight panel). Weekend
       p99 = 732 bps and overnight p99 = 615 bps marked and
       direct-labelled; the 13.8%-of-weekends ≥1-symbol->500 bps fact
       annotated. Standard figure aspect.

Style matches scripts/build_paper1_figures.py (Okabe-Ito, serif +
cm mathtext, 6.0 in single-column width, vector PDF). Standalone on
purpose — do not fold into build_paper1_figures.py. The old combined
fig_h1_blind_window outputs are no longer regenerated.

Run:
  uv run python -u scripts/build_fig_h1.py
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from scipy.stats import gaussian_kde

from soothsayer.config import DATA_PROCESSED, REPORTS, RESEARCH

FIG_DIR = RESEARCH / "coverage-inversion" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Okabe-Ito palette (colorblind-safe) — matches build_paper1_figures.py.
OI = {
    "black":     "#000000",
    "blue":      "#0072B2",
    "vermilion": "#D55E00",
    "grey":      "#777777",
}

# Sequential single-hue ramp for the timeline, ordered by "closedness"
# (open = lightest). One hue, light→dark — NOT four unrelated hues.
STATE_COLORS = {
    "regular":    "#EAF2FA",   # regular session   (lightest — open)
    "after":      "#9CC4E4",   # after-hours / pre-market
    "overnight":  "#4E94C4",   # weeknight closed
    "weekend":    "#0B4A73",   # weekend closed    (darkest)
}

# Caption numbers (the contract). The script recomputes each from the
# panels and asserts agreement — a mismatch is a hard error, not a
# silent caption edit.
CAPTION = {
    "wk_median": 51, "wk_p99": 732,
    "on_median": 46, "on_p99": 615,
    "pct_weekends_500": 13.8,
    "n_weekend": 5996, "n_overnight": 22624,
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


def load_gaps() -> tuple[pd.Series, pd.Series, pd.Series, float]:
    """|close→open| gaps in bps for weekend / overnight / earnings-night,
    plus the share of weekends where ≥1 of the 10 symbols gapped >500 bps."""
    wk = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    on = pd.read_parquet(DATA_PROCESSED / "overnight_panel.parquet")

    assert len(wk) == CAPTION["n_weekend"], f"weekend rows {len(wk)}"
    assert len(on) == CAPTION["n_overnight"], f"overnight rows {len(on)}"

    wk_gap = ((wk["mon_open"] / wk["fri_close"] - 1).abs() * 1e4).dropna()
    on_gap = ((on["mon_open"] / on["fri_close"] - 1).abs() * 1e4).dropna()
    earn_mask = on["regime_pub"].astype(str) == "earnings_night"
    earn_gap = ((on.loc[earn_mask, "mon_open"]
                 / on.loc[earn_mask, "fri_close"] - 1).abs() * 1e4).dropna()

    per_weekend_max = (
        wk.assign(gap_bps=(wk["mon_open"] / wk["fri_close"] - 1).abs() * 1e4)
          .groupby("fri_ts")["gap_bps"].max()
    )
    pct_500 = 100.0 * float((per_weekend_max > 500).mean())

    # ---- verify against the caption (round to caption precision).
    checks = [
        ("weekend median", round(float(wk_gap.median())), CAPTION["wk_median"]),
        ("weekend p99", round(float(wk_gap.quantile(0.99))), CAPTION["wk_p99"]),
        ("overnight median", round(float(on_gap.median())), CAPTION["on_median"]),
        ("overnight p99", round(float(on_gap.quantile(0.99))), CAPTION["on_p99"]),
        ("% weekends >500 bps", round(pct_500, 1), CAPTION["pct_weekends_500"]),
    ]
    for name, got, want in checks:
        status = "OK " if got == want else "MISMATCH"
        print(f"  [{status}] {name}: computed {got} vs caption {want}")
        assert got == want, f"{name}: computed {got} != caption {want}"

    return wk_gap, on_gap, earn_gap, pct_500


# ========================================================= top panel


def draw_week_timeline(ax: plt.Axes) -> None:
    """One wall-clock week, Mon 00:00 → Sun 24:00 ET, coloured by state.

    Hours from Mon 00:00. Weekday d ∈ {0..4}:
      04:00–09:30 pre-market, 09:30–16:00 regular, 16:00–20:00 after-hours,
      20:00–04:00(+1) overnight. Fri 20:00 → Mon 04:00 is the weekend
      (fully closed); Mon 00:00–04:00 (left edge) is its tail.
    """
    segs: dict[str, list[tuple[float, float]]] = {
        "regular": [], "after": [], "overnight": [], "weekend": [],
    }
    for d in range(5):                       # Mon..Fri
        h0 = 24.0 * d
        segs["after"].append((h0 + 4.0, 5.5))          # pre-market
        segs["regular"].append((h0 + 9.5, 6.5))        # regular session
        segs["after"].append((h0 + 16.0, 4.0))         # after-hours
    for d in range(4):                       # Mon..Thu nights
        segs["overnight"].append((24.0 * d + 20.0, 8.0))
    segs["weekend"].append((0.0, 4.0))                 # Sun-night tail
    segs["weekend"].append((116.0, 52.0))              # Fri 20:00 → Sun 24:00

    Y0, H = 0.0, 1.0
    for state in ("weekend", "overnight", "after", "regular"):
        ax.broken_barh(segs[state], (Y0, H),
                       facecolors=STATE_COLORS[state], edgecolor="none")
    # Thin frame around the bar so the lightest segments read on white.
    ax.plot([0, 168, 168, 0, 0], [Y0, Y0, Y0 + H, Y0 + H, Y0],
            color=OI["grey"], lw=0.5, zorder=4)
    # Midnight separators (recessive).
    for d in range(1, 7):
        ax.plot([24 * d, 24 * d], [Y0, Y0 + H],
                color="white", lw=0.6, zorder=3)

    # ---- direct label: the 65.5-hour closed span (wraps past Sun 24:00).
    yb = 1.55
    ax.annotate("", xy=(171.5, yb), xytext=(112.0, yb),
                annotation_clip=False,
                arrowprops=dict(arrowstyle="->", lw=0.9, color=OI["black"]))
    ax.plot([112, 112], [yb - 0.18, yb + 0.18],
            color=OI["black"], lw=0.9, clip_on=False)
    ax.text(140.0, yb + 0.35,
            "Fri 16:00 $\\rightarrow$ Mon 09:30 ET\n"
            "65.5 h, no reference print",
            ha="center", va="bottom", fontsize=8.0, color=OI["black"])

    # ---- direct label: 32.5 of 168 hours open.
    ax.annotate(
        "regular session: 6.5 h $\\times$ 5 = 32.5 of 168 h (19%)",
        xy=(36.75, Y0 + H),                  # Tue regular-session block
        xytext=(36.75, yb + 0.55),
        ha="center", va="bottom", fontsize=8.0, color=OI["black"],
        arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"]),
    )

    # ---- axes cosmetics.
    ax.set_xlim(0, 168)
    ax.set_ylim(-0.55, 3.3)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_position(("data", -0.05))
    ax.set_xticks([24 * d + 12 for d in range(7)])
    ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set_xticks([24 * d for d in range(8)], minor=True)
    ax.tick_params(axis="x", which="major", length=0, pad=3)
    ax.tick_params(axis="x", which="minor", length=3, width=0.6)

    handles = [
        Patch(facecolor=STATE_COLORS["regular"], edgecolor=OI["grey"],
              linewidth=0.4, label="regular session"),
        Patch(facecolor=STATE_COLORS["after"], label="after-hours"),
        Patch(facecolor=STATE_COLORS["overnight"], label="overnight (closed)"),
        Patch(facecolor=STATE_COLORS["weekend"], label="weekend (closed)"),
    ]
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.10), ncol=4, frameon=False,
              fontsize=7.8, handlelength=1.2, handleheight=0.9,
              columnspacing=1.2, handletextpad=0.5)


# ====================================================== bottom panel


X_MIN, X_MAX = 1.0, 3000.0   # bps; gaps below 1 bps clipped to 1


def _log_kde(gaps: pd.Series, grid: np.ndarray) -> np.ndarray:
    """KDE of log10(gap bps), gaps clipped to [X_MIN, ∞). Density per
    unit log10 — the natural density on a log-x axis."""
    x = np.log10(np.clip(gaps.to_numpy(), X_MIN, None))
    return gaussian_kde(x)(grid)


def draw_gap_distributions(
    ax: plt.Axes,
    wk_gap: pd.Series,
    on_gap: pd.Series,
    earn_gap: pd.Series,
    pct_500: float,
) -> None:
    grid = np.linspace(np.log10(X_MIN), np.log10(X_MAX), 400)
    xs = 10.0 ** grid

    wk_d = _log_kde(wk_gap, grid)
    on_d = _log_kde(on_gap, grid)
    earn_d = _log_kde(earn_gap, grid)

    ax.fill_between(xs, on_d, color=OI["vermilion"], alpha=0.10, lw=0)
    ax.plot(xs, on_d, color=OI["vermilion"], lw=1.5,
            label=f"overnight (n = {len(on_gap):,})")
    ax.fill_between(xs, wk_d, color=OI["blue"], alpha=0.12, lw=0)
    ax.plot(xs, wk_d, color=OI["blue"], lw=1.5,
            label=f"weekend (n = {len(wk_gap):,})")
    ax.plot(xs, earn_d, color="#555555", lw=1.2, ls="--",
            label=f"earnings night (n = {len(earn_gap):,})")

    # ---- head-room above the curves keeps the label band collision-free.
    y_max = 1.35 * max(wk_d.max(), on_d.max(), earn_d.max())

    # ---- p99 markers, direct-labelled (labels in text ink). The two
    # lines sit close on a log axis — labels stack in the top-right
    # corner with thin leaders.
    wk_p99 = float(wk_gap.quantile(0.99))     # 732 bps
    on_p99 = float(on_gap.quantile(0.99))     # 615 bps
    ax.axvline(on_p99, color=OI["vermilion"], lw=0.9, ls=":", alpha=0.9,
               ymax=0.84)
    ax.axvline(wk_p99, color=OI["blue"], lw=0.9, ls=":", alpha=0.9,
               ymax=0.84)
    # Stacked labels, keyed by a short dotted swatch in the line's
    # colour + linestyle (text stays in ink; no leader lines, which
    # would cross the other label).
    for label, colour, y_row in [
        (f"weekend p99 = {wk_p99:.0f} bps", OI["blue"], 0.945),
        (f"overnight p99 = {on_p99:.0f} bps", OI["vermilion"], 0.865),
    ]:
        ax.plot([0.700, 0.728], [y_row, y_row], transform=ax.transAxes,
                ls=":", lw=1.1, color=colour, clip_on=False)
        ax.text(0.740, y_row, label, transform=ax.transAxes,
                ha="left", va="center", fontsize=8.0, color=OI["black"])

    # ---- earnings-night tail annotation (§6 scale claim): in the free
    # band between the legend and the p99 labels, leader to the rising
    # slope of the dashed curve.
    x_lead = 330.0
    y_lead = float(np.interp(np.log10(x_lead), grid, earn_d))
    ax.annotate(
        "earnings-night tail\n$\\approx$8$\\times$ normal-night scale (§6)",
        xy=(x_lead, y_lead),
        xytext=(0.565, 0.775), textcoords="axes fraction",
        ha="center", va="top", fontsize=8.0, color=OI["black"],
        arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["grey"],
                        shrinkB=3),
    )

    # ---- the one-weekend-in-seven fact.
    ax.text(0.035, 0.615,
            f"on {pct_500:.1f}% of weekends,\n"
            "$\\geq$1 of 10 symbols\ngapped >500 bps",
            transform=ax.transAxes, ha="left", va="top",
            fontsize=8.0, color=OI["black"])

    ax.set_xscale("log")
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylim(0, y_max)
    ax.set_xticks([1, 10, 100, 1000])
    ax.set_xticklabels(["1", "10", "100", "1,000"])
    ax.set_xlabel(r"$|$close $\rightarrow$ open$|$ gap (bps, log scale)")
    ax.set_ylabel("density")
    ax.legend(loc="upper left", frameon=False, fontsize=8.0,
              handlelength=1.6, borderaxespad=0.4)


# ================================================================ main


def main() -> None:
    setup_rc()
    print("computing panel statistics vs caption ...")
    wk_gap, on_gap, earn_gap, pct_500 = load_gaps()

    # ---- H1a: the week timeline, as a compact strip (inline exhibit).
    fig_a, ax_a = plt.subplots(figsize=(6.0, 1.8))
    draw_week_timeline(ax_a)
    pdf_a = FIG_DIR / "fig_h1a_week_timeline.pdf"
    fig_a.savefig(pdf_a)
    fig_a.savefig(pdf_a.with_suffix(".png"), dpi=200)
    plt.close(fig_a)
    print(f"  wrote {pdf_a}")
    print(f"  wrote {pdf_a.with_suffix('.png')}")

    # ---- H1b: the gap distributions, standard figure aspect.
    fig_b, ax_b = plt.subplots(figsize=(6.0, 3.1))
    draw_gap_distributions(ax_b, wk_gap, on_gap, earn_gap, pct_500)
    pdf_b = FIG_DIR / "fig_h1b_gap_distributions.pdf"
    fig_b.savefig(pdf_b)
    fig_b.savefig(pdf_b.with_suffix(".png"), dpi=200)
    plt.close(fig_b)
    print(f"  wrote {pdf_b}")
    print(f"  wrote {pdf_b.with_suffix('.png')}")


if __name__ == "__main__":
    main()
