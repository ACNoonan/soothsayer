"""
Build Figure S2 — "Does the same method still deliver its promise overnight —
including on earnings nights?"

Replaces fig8_overnight_calibration as the §6.8 exhibit (fig8 is left
untouched). Reviewer verdict on fig8: a four-line calibration plot does not
tell a protocol engineer whether earnings nights are handled appropriately.

Design (one question, one glance):
  Promised-vs-delivered dot rows at the four coverage anchors
  (68 / 85 / 95 / 99%), two groups:

    top    — all overnight gaps pooled (n = 6,450 OOS rows): the delivered
             dot sits ON the promised tick at every anchor;
    bottom — earnings nights only (n = 60 OOS rows): the delivered dot sits
             to the RIGHT of the promise at every anchor, with the direction
             spelled out in words — earnings nights err on the safe side
             (bands too wide, never too narrow).

Numbers are recomputed from data/processed/overnight_panel.parquet plus the
deployed overnight artefact schedules (overnight_artefact_v1.json) and
asserted against the caption contract below — a mismatch is a hard error,
not a silent caption edit. Matches the Phase-2 tables in
reports/active/overnight_calibration_firstread.md.

Style matches scripts/build_paper1_figures.py (Okabe-Ito, serif + cm
mathtext, 6.0 in single-column width, vector PDF + 200 dpi PNG).

Run:
  uv run python -u scripts/build_fig_s2.py
"""

from __future__ import annotations

import json
from datetime import date

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from soothsayer.backtest.calibration import compute_score_lwc
from soothsayer.config import DATA_PROCESSED, REPORTS

FIG_DIR = REPORTS / "paper1_coverage_inversion" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

SPLIT_DATE = date(2023, 1, 1)
TAUS = (0.68, 0.85, 0.95, 0.99)

# Okabe-Ito palette (colorblind-safe) — matches build_paper1_figures.py.
OI = {
    "black": "#000000",
    "blue": "#0072B2",
    "green": "#009E73",
    "grey": "#777777",
}

# Caption contract (Phase-2 tables, overnight_calibration_firstread.md).
# Recomputed below and asserted; 4-dp realised coverage.
CAPTION = {
    "n_pooled": 6450,
    "n_earn": 60,
    "pooled": {0.68: 0.6800, 0.85: 0.8507, 0.95: 0.9510, 0.99: 0.9918},
    "earn": {0.68: 0.7667, 0.85: 0.9667, 0.95: 0.9833, 0.99: 1.0000},
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


def delivered_coverage() -> tuple[dict[float, float], dict[float, float], int, int]:
    """OOS realised coverage per τ — pooled and earnings_night-only — served
    from the deployed overnight artefact schedules (byte-for-byte what a
    consumer would read), then asserted against the caption contract."""
    panel = pd.read_parquet(DATA_PROCESSED / "overnight_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel["point"] = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    panel["score"] = compute_score_lwc(panel, scale_col="sigma_hat_sym_pre_fri")

    work = panel[
        panel["score"].notna() & panel["sigma_hat_sym_pre_fri"].notna()
    ].reset_index(drop=True)
    oos = work[work["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)

    side = json.loads(
        (DATA_PROCESSED / "overnight_artefact_v1.json").read_text())
    qt = {r: {float(t): float(v) for t, v in row.items()}
          for r, row in side["regime_quantile_table"].items()}
    cb = {float(t): float(v) for t, v in side["c_bump_schedule"].items()}

    earn = oos["regime_pub"] == "earnings_night"
    pooled, earn_cov = {}, {}
    for tau in TAUS:
        q = oos["regime_pub"].map({r: qt[r][tau] for r in qt}).astype(float)
        half = cb[tau] * q * oos["sigma_hat_sym_pre_fri"] * oos["fri_close"]
        inside = (oos["mon_open"] >= oos["point"] - half) & (
            oos["mon_open"] <= oos["point"] + half)
        pooled[tau] = float(inside.mean())
        earn_cov[tau] = float(inside[earn].mean())

    # ---- verify against the caption contract.
    checks = [("n pooled", len(oos), CAPTION["n_pooled"]),
              ("n earnings", int(earn.sum()), CAPTION["n_earn"])]
    for tau in TAUS:
        checks.append((f"pooled τ={tau}", round(pooled[tau], 4),
                       CAPTION["pooled"][tau]))
        checks.append((f"earnings τ={tau}", round(earn_cov[tau], 4),
                       CAPTION["earn"][tau]))
    for name, got, want in checks:
        status = "OK " if got == want else "MISMATCH"
        print(f"  [{status}] {name}: computed {got} vs caption {want}")
        assert got == want, f"{name}: computed {got} != caption {want}"

    return pooled, earn_cov, len(oos), int(earn.sum())


# ============================================================ figure


def build() -> None:
    pooled, earn_cov, n_pooled, n_earn = delivered_coverage()

    fig, ax = plt.subplots(figsize=(6.0, 4.3))

    # Row layout: pooled group on top, earnings group below, τ descending
    # left-to-right along x so rows read top-down 68 → 99 within a group.
    GAP = 1.9                       # vertical gap between the two groups
    y_pooled = {tau: 8.0 - i for i, tau in enumerate(TAUS)}
    y_earn = {tau: 8.0 - GAP - len(TAUS) + 1 - i - 1
              for i, tau in enumerate(TAUS)}

    # Recessive vertical guides at the four promised anchors.
    y_lo = min(y_earn.values()) - 0.6
    y_hi = max(y_pooled.values()) + 0.6
    for tau in TAUS:
        ax.plot([tau, tau], [y_lo, y_hi], color=OI["grey"], lw=0.5,
                ls=":", alpha=0.45, zorder=1)

    def draw_group(ys: dict[float, float], cov: dict[float, float],
                   dot_color: str) -> None:
        for tau in TAUS:
            y = ys[tau]
            # delivered: filled dot (no connector bar — deviation direction
            # is carried by one shared annotation, not per-row whiskers)
            ax.plot([cov[tau]], [y], marker="o", ms=8.5, color=dot_color,
                    mec="black", mew=0.5, zorder=4)
            # promised anchor: vertical tick, drawn ON TOP so that a dot
            # sitting exactly on the promise reads as "dot on the tick".
            ax.plot([tau], [y], marker="|", ms=14, mew=1.6,
                    color=OI["black"], zorder=5)

    draw_group(y_pooled, pooled, OI["blue"])
    draw_group(y_earn, earn_cov, OI["green"])

    # Row labels (left) + delivered-value labels (right of the dot pair).
    for tau in TAUS:
        ax.text(0.615, y_pooled[tau], f"{tau:.0%} promised",
                ha="right", va="center", fontsize=8.5, color=OI["black"])
        ax.text(0.615, y_earn[tau], f"{tau:.0%} promised",
                ha="right", va="center", fontsize=8.5, color=OI["black"])
        ax.text(max(tau, pooled[tau]) + 0.012, y_pooled[tau],
                f"delivered {pooled[tau]:.1%}",
                ha="left", va="center", fontsize=8.0, color=OI["blue"])
        d_pp = 100.0 * (earn_cov[tau] - tau)
        ax.text(earn_cov[tau] + 0.012, y_earn[tau],
                f"{earn_cov[tau]:.1%}  (+{d_pp:.1f} pp)",
                ha="left", va="center", fontsize=8.0, color=OI["green"])
        if tau == 0.99:
            # small-n context so a bare "100.0%" cannot read as absurd
            ax.text(earn_cov[tau] + 0.012, y_earn[tau] - 0.38,
                    "(0 misses in 60 nights; exact\n"
                    "calibration would expect 0.6)",
                    ha="left", va="top", fontsize=7.0, color=OI["grey"])

    # Group headers.
    ax.text(0.615, max(y_pooled.values()) + 0.85,
            f"All overnight gaps, pooled  (n = {n_pooled:,} held-out symbol-nights)",
            ha="left", va="center", fontsize=9.0,
            fontweight="bold", color=OI["black"])
    ax.text(0.615, max(y_earn.values()) + 0.85,
            f"Earnings nights only  (n = {n_earn})",
            ha="left", va="center", fontsize=9.0, fontweight="bold",
            color=OI["black"])

    # The direction, in words — one shared annotation for the group
    # (one sentence; wrapped at the dash so it fits the column width).
    ax.text(0.615, min(y_earn.values()) - 1.55,
            "earnings nights land on the safe side of the promise —\n"
            "too-wide costs some efficiency; too-narrow would cost solvency. "
            "None landed under.",
            ha="left", va="top", fontsize=8.0, color=OI["green"],
            style="italic", linespacing=1.35)

    # Legend: what the two marks mean.
    handles = [
        Line2D([0], [0], marker="|", ms=11, mew=1.6, color=OI["black"],
               lw=0, label="promised coverage"),
        Line2D([0], [0], marker="o", ms=7.5, color=OI["grey"], mec="black",
               mew=0.5, lw=0, label="delivered coverage (out-of-sample)"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.115),
              ncol=2, frameon=False, fontsize=8.0, handletextpad=0.4,
              columnspacing=1.6)

    ax.set_title(
        "Overnight, delivered coverage sits on the promise —\n"
        "earnings nights land above it, the safe side",
        fontsize=10.5, loc="left", pad=10)

    ax.set_xlim(0.50, 1.16)
    ax.set_ylim(y_lo - 2.2, y_hi + 1.3)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xticks(list(TAUS))
    ax.set_xticklabels([f"{t:.0%}" for t in TAUS])
    # 95% / 99% anchors are 4 pp apart — nudge alignment so labels clear.
    for lbl, ha in zip(ax.get_xticklabels(), ("center", "center", "right", "left")):
        lbl.set_horizontalalignment(ha)
    ax.set_xlabel("share of next-morning opens that landed inside the served band")

    out = FIG_DIR / "fig_s2_overnight.pdf"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=200)
    plt.close(fig)
    print(f"  wrote {out}")
    print(f"  wrote {out.with_suffix('.png')}")


if __name__ == "__main__":
    setup_rc()
    build()
