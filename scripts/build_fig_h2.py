"""
Build Paper 1 hero figure H2 — "Anatomy of a read".

Consumer-facing flow diagram of the coverage-inversion contract, three
stages left to right:

  1. Consumer chooses target coverage τ (four audited anchors).
  2. Oracle serving lookup — the five-step lookup against the frozen
     per-Friday artefact (kept compact; it is the middle, not the star).
  3. The read: band (P̂, L, U) + the PricePoint calibration receipt with
     the EXACT §3 wire names, plus the third-party verification loop.

Message: coverage is the input; the receipt makes the claim checkable.

Style matches scripts/build_paper1_figures.py fig1_pipeline (matplotlib
patches/annotations, Okabe-Ito palette, serif/CM mathtext). One accent
hue (Okabe-Ito vermilion) is reserved for the receipt fields.

Outputs:
  reports/paper1_coverage_inversion/figures/fig_h2_anatomy_of_a_read.pdf
  reports/paper1_coverage_inversion/figures/fig_h2_anatomy_of_a_read.png

Run:
  uv run python -u scripts/build_fig_h2.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

REPO = Path(__file__).resolve().parents[1]
FIG_DIR = REPO / "reports" / "paper1_coverage_inversion" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Okabe-Ito palette (colorblind-safe) — mirrors build_paper1_figures.py.
OI = {
    "black":     "#000000",
    "orange":    "#E69F00",
    "skyblue":   "#56B4E9",
    "green":     "#009E73",
    "yellow":    "#F0E442",
    "blue":      "#0072B2",
    "vermilion": "#D55E00",
    "purple":    "#CC79A7",
    "grey":      "#777777",
}
ACCENT = OI["vermilion"]        # the receipt — the star of the figure
ACCENT_FILL = "#FCEEE5"         # very light warm tint behind receipt fields
INK = OI["black"]
MONO = "DejaVu Sans Mono"


def setup_rc() -> None:
    mpl.rcParams.update({
        "text.usetex": False,
        "mathtext.fontset": "cm",
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times"],
        "font.size": 10,
        "axes.linewidth": 0.7,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,
    })


def build() -> None:
    setup_rc()
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 64)
    ax.axis("off")

    def rbox(x, y, w, h, fc, ec, lw=0.8, rounding=1.2):
        p = FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0.3,rounding_size={rounding}",
            linewidth=lw, facecolor=fc, edgecolor=ec,
        )
        ax.add_patch(p)
        return p

    def arrow(x1, y1, x2, y2, color=OI["grey"], lw=0.7, style="->", ls="-",
              rad=0.0):
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle=style, lw=lw, color=color, linestyle=ls,
                connectionstyle=f"arc3,rad={rad}", shrinkA=1, shrinkB=1,
            ),
        )

    # ---------------------------------------------------------- stage headers
    ax.text(11.5, 57.0, "1 · consumer", ha="center", fontsize=8.0,
            color=INK, fontweight="bold")
    ax.text(39.5, 57.0, "2 · oracle serving lookup", ha="center",
            fontsize=8.0, color=INK, fontweight="bold")
    ax.text(78.0, 57.0, "3 · the read", ha="center", fontsize=8.0,
            color=ACCENT, fontweight="bold")

    # ------------------------------------------------------- 1: consumer box
    rbox(1, 28, 21, 26, "#FDF6E3", INK)
    ax.text(11.5, 50.5, "chooses target", ha="center", fontsize=7.6, color=INK)
    ax.text(11.5, 47.9, "coverage", ha="center", fontsize=7.6, color=INK)
    ax.text(11.5, 42.7, r"$\tau$", ha="center", va="center", fontsize=16,
            color=INK)
    ax.text(11.5, 37.4, "audited anchors", ha="center", fontsize=6.4,
            color=OI["grey"])
    anchors = ["0.68", "0.85", "0.95", "0.99"]
    for i, a in enumerate(anchors):
        cx = 2.7 + 4.9 * i
        rbox(cx, 30.3, 4.1, 4.2, "white", OI["grey"], lw=0.6, rounding=0.8)
        ax.text(cx + 2.05, 32.4, a, ha="center", va="center", fontsize=6.2,
                color=INK)

    # ------------------------------------------------ 2: five-step lookup box
    rbox(27, 28, 25, 26, "#E8F1FA", OI["blue"])
    ax.text(39.5, 51.4, "five-step lookup", ha="center", fontsize=7.6,
            color=OI["blue"], fontweight="bold")
    ax.text(39.5, 48.9, "frozen per-Friday artefact", ha="center",
            fontsize=6.2, color=OI["grey"], style="italic")
    steps = [
        r"1  regime $r$ $\leftarrow$ pre-publish",
        r"    features",
        r"2  quantile $q_r(\tau)$ per regime",
        r"3  scale $\hat\sigma_s(t)$ per symbol",
        r"4  buffer $c(\tau)$",
        r"5  band $\hat P \pm c\, q_r\, \hat\sigma_s \cdot P_{\mathrm{Fri}}$",
    ]
    ys = [46.2, 43.7, 40.7, 37.7, 34.7, 31.7]
    for s, y in zip(steps, ys):
        ax.text(28.6, y, s, ha="left", va="center",
                fontsize=6.4, color=INK)

    # ------------------------------------------------------- 3: the read box
    rbox(57, 7, 42, 47, "white", INK, lw=1.1, rounding=1.6)
    ax.text(78, 51.4, r"PricePoint$(s,\, t,\, \tau)$", ha="center",
            fontsize=8.6, color=INK, fontweight="bold")
    ax.text(59.2, 47.8, "band", ha="left", fontsize=7.2, color=INK,
            fontweight="bold")
    ax.text(96.4, 47.8, r"$\hat P,\ L,\ U$", ha="right", fontsize=7.8,
            color=INK)

    # Receipt sub-box — the star, in the accent hue.
    rbox(58.6, 8.6, 38.8, 36.4, ACCENT_FILL, ACCENT, lw=1.0, rounding=1.2)
    ax.text(78, 42.6, "calibration receipt", ha="center", fontsize=7.6,
            color=ACCENT, fontweight="bold")

    # Six receipt fields — EXACT §3 wire names (mono, accent) + math (ink).
    fields = [
        ("target_coverage",                    r"$\tau$"),
        ("regime",                             r"$r$"),
        ("forecaster_used",                    r"$f$"),
        ("diagnostics.c_bump",                 r"$c(\tau)$"),
        ("diagnostics.q_regime_lwc",           r"$q_r(\tau)$"),
        ("diagnostics.sigma_hat_sym_pre_fri",  r"$\hat\sigma_s(t)$"),
    ]
    y0 = 39.6
    for i, (name, sym) in enumerate(fields):
        y = y0 - 3.3 * i
        ax.text(59.9, y, name, ha="left", va="center", fontsize=5.7,
                family=MONO, color=ACCENT)
        ax.text(96.0, y, sym, ha="right", va="center", fontsize=7.0,
                color=INK)

    # Echo / derived fields (grey, below a thin divider).
    ax.plot([59.9, 96.0], [21.0, 21.0], lw=0.5, color=ACCENT, alpha=0.45)
    echoes = [
        (r"claimed_coverage_served",
         r"$=\tau\ \ (\delta \equiv 0)$"),
        (r"sharpness_bps",
         r"$10^4\, c(\tau)\, q_r(\tau)\, \hat\sigma_s(t)$"),
        (r"diagnostics.q_eff",
         r"$c(\tau)\, q_r(\tau)$"),
    ]
    for i, (name, sym) in enumerate(echoes):
        y = 19.2 - 3.0 * i
        ax.text(59.9, y, name, ha="left", va="center", fontsize=5.4,
                family=MONO, color=OI["grey"])
        ax.text(96.0, y, sym, ha="right", va="center", fontsize=6.2,
                color=OI["grey"])
    ax.text(78, 10.2, "echoed / derived", ha="center", fontsize=5.4,
            color=OI["grey"], style="italic")

    # ------------------------------------------------------------- flow arrows
    arrow(22.6, 41, 26.4, 41)
    ax.text(24.5, 42.8, r"$\tau$", ha="center", fontsize=7.2, color=INK)
    arrow(52.6, 41, 56.4, 41)

    # ------------------------------------------------------ verification loop
    # Dashed accent arrow from the receipt all the way back to the consumer,
    # closing the loop: the third party who chose τ is the one who verifies.
    # One gentle arc through the corridor between the caption text and the
    # bottom edges of the stage boxes.
    arrow(56.6, 16.5, 12.5, 25.6, color=ACCENT, lw=0.9, ls=(0, (4, 2.5)),
          rad=0.14)
    ax.text(2, 21.5, "verification loop", ha="left", fontsize=7.4,
            color=ACCENT, fontweight="bold")
    ver_lines = [
        "third party re-derives the band to floating-point",
        "precision from receipt + public artefact",
        "(< 100 KB per symbol-year), and rebuilds the",
        "calibration surface itself from public data",
    ]
    for i, line in enumerate(ver_lines):
        ax.text(2, 18.7 - 2.65 * i, line, ha="left", fontsize=6.6, color=INK)

    out_pdf = FIG_DIR / "fig_h2_anatomy_of_a_read.pdf"
    out_png = FIG_DIR / "fig_h2_anatomy_of_a_read.png"
    plt.savefig(out_pdf)
    plt.savefig(out_png, dpi=300)
    plt.close(fig)
    print(f"  wrote {out_pdf}")
    print(f"  wrote {out_png}")


if __name__ == "__main__":
    build()
