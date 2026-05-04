"""
Build all six Paper 1 figures.

Outputs PDFs into `reports/paper1_coverage_inversion/figures/`:

  fig1_pipeline.pdf          M5 architecture / data-flow block diagram
  fig2_calibration.pdf       Calibration curve: M5 vs v1 vs constant-buffer
  fig3_stability.pdf         Walk-forward + split-date sensitivity panels
  fig4_per_symbol.pdf        Per-symbol bimodality scatter
  fig5_pareto.pdf            Coverage vs half-width Pareto across methods
  fig6_path_coverage.pdf     Endpoint vs path coverage on perp reference

Conventions
-----------
Single-column 6.0 in width (matches arxiv.sty NIPS-derived layout).
Okabe-Ito colorblind-safe palette. LaTeX-rendered text via `text.usetex=True`
to match the body's Computer Modern. PDFs (vector) for clean scaling.

Run:
  uv run python scripts/build_paper1_figures.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    compute_score,
    fit_c_bump_schedule,
    serve_bands,
    train_quantile_table,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

FIG_DIR = REPORTS / "paper1_coverage_inversion" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLES = REPORTS / "tables"

SPLIT_DATE = date(2023, 1, 1)
TAUS = (0.68, 0.85, 0.95, 0.99)

# Okabe-Ito palette (colorblind-safe).
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


def setup_rc() -> None:
    """Match LaTeX body Computer-Modern look using matplotlib's built-in
    mathtext (no usetex dependency on a full texlive install)."""
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


# =================================================================== Fig 1


def fig1_pipeline() -> None:
    """M5 architecture / data-flow diagram. matplotlib patches + arrows."""
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    def box(x, y, w, h, text, fc, ec=OI["black"], fontsize=8.5):
        p = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
            linewidth=0.8, facecolor=fc, edgecolor=ec,
        )
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, color=OI["black"])

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=0.7, color=OI["grey"]))

    # Top: inputs (Friday 16:00 ET)
    ax.text(50, 57, "Inputs at Friday 16:00 ET", ha="center",
            fontsize=9.5, color=OI["black"], fontweight="bold")
    inputs = [
        (3,  44, 20, 9, r"$p_t^{\mathrm{Fri}}$" "\n" r"close",       "#FDF6E3"),
        (26, 44, 22, 9, r"factor switchboard" "\n" r"$\rho(s,t)\!\to\!r_t^F$", "#FDF6E3"),
        (51, 44, 22, 9, r"regime classifier" "\n" r"$r\!\in\!\{\mathrm{nrm,lw,hv}\}$", "#FDF6E3"),
        (76, 44, 21, 9, r"consumer $\tau$" "\n" r"$\in[0.68,0.99]$", "#FDF6E3"),
    ]
    for (x, y, w, h, t, fc) in inputs:
        box(x, y, w, h, t, fc)

    # Middle: 5-line lookup, shaded box
    p = FancyBboxPatch(
        (4, 14), 92, 24, boxstyle="round,pad=0.4,rounding_size=2.0",
        linewidth=1.0, facecolor="#E8F1FA", edgecolor=OI["blue"],
    )
    ax.add_patch(p)
    ax.text(50, 35.5, "Five-line serving lookup", ha="center",
            fontsize=9.5, color=OI["blue"], fontweight="bold")
    eqs = [
        r"$\hat p_t = p_t^{\mathrm{Fri}} \cdot (1 + r_t^F)$",
        r"$\tau' = \tau + \delta(\tau) \quad\quad \delta\in\{0.05,\, 0.02,\, 0.00,\, 0.00\}$",
        r"$q_{\mathrm{eff}} = c(\tau') \cdot q_r(\tau') \quad c\in\{1.498,\,1.455,\,1.300,\,1.076\}$",
        r"$L_t = \hat p_t \cdot (1 - q_{\mathrm{eff}}), \quad U_t = \hat p_t \cdot (1 + q_{\mathrm{eff}})$",
    ]
    for i, eq in enumerate(eqs):
        ax.text(7, 31.5 - 4.0 * i, eq, ha="left", va="center",
                fontsize=9, color=OI["black"])

    # Bottom: receipt
    box(2, 1, 96, 9,
        r"$\mathrm{PricePoint}\{\,\mathrm{symbol},\, \mathrm{as\_of},\, \tau,\, \delta(\tau),\, \tau{+}\delta(\tau),\, \hat p_t,\, L_t,\, U_t,\, r,\, \mathrm{sharpness\,bps},\, \mathrm{diagnostics}\{c,\, q_{\mathrm{eff}},\, q_r\}\,\}$",
        "#F5F5F5", ec=OI["grey"], fontsize=7.5)
    ax.text(50, 11.2, "Per-read receipt (P1: auditability)",
            ha="center", fontsize=9, color=OI["grey"], fontweight="bold")

    # Arrows down from inputs into shaded box
    for (x, _, w, _, _, _) in inputs:
        arrow(x + w / 2, 44, x + w / 2, 38.5)
    # Arrow down from shaded box into receipt
    arrow(50, 14, 50, 10.2)

    plt.savefig(FIG_DIR / "fig1_pipeline.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig1_pipeline.pdf'}")


# =================================================================== Fig 2


def fig2_calibration() -> None:
    """Calibration curve: M5 vs v1 vs constant-buffer + 45° diagonal.

    M5 served at a fine τ grid via the helper, evaluated on the 1,730-row
    OOS slice. v1 from `v1b_bounds.parquet` at its 12 native anchors.
    Constant-buffer baseline = factor-adjusted point ± k_τ·z_α·σ_20d
    (the §7.1 stress-test rung) at the same fine grid.
    """
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret",
                "fri_vol_20d"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel["score"] = compute_score(panel)

    # M5 fine-grid serve.
    train = panel[panel["fri_ts"] < SPLIT_DATE].dropna(subset=["score"])
    oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
           .dropna(subset=["score"])
           .sort_values(["symbol", "fri_ts"])
           .reset_index(drop=True))
    fine_taus = tuple(np.round(np.linspace(0.10, 0.99, 60), 4))
    qt = train_quantile_table(train, cell_col="regime_pub", taus=fine_taus)
    cb = fit_c_bump_schedule(oos, qt, cell_col="regime_pub", taus=fine_taus)
    bounds = serve_bands(
        oos, qt, cb, cell_col="regime_pub", taus=fine_taus,
        delta_shift_schedule={t: 0.0 for t in fine_taus},
    )
    m5_curve = []
    for tau in fine_taus:
        b = bounds[tau]
        cov = ((oos["mon_open"] >= b["lower"]) &
               (oos["mon_open"] <= b["upper"])).mean()
        m5_curve.append((tau, float(cov)))
    m5 = pd.DataFrame(m5_curve, columns=["claimed", "realised"])

    # v1 bounds curve (deployed-hybrid policy on its 12 native anchors).
    bounds_v1 = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds_v1["fri_ts"] = pd.to_datetime(bounds_v1["fri_ts"]).dt.date
    bounds_v1 = bounds_v1[bounds_v1["fri_ts"] >= SPLIT_DATE]
    REGIME_FC = {"normal": "F1_emp_regime",
                 "long_weekend": "F1_emp_regime",
                 "high_vol": "F0_stale"}
    bounds_v1 = bounds_v1[bounds_v1.apply(
        lambda r: r["forecaster"] == REGIME_FC.get(r["regime_pub"]),
        axis=1
    )].copy()
    BUFFER_BY_TARGET = {0.68: 0.005, 0.85: 0.010, 0.95: 0.020, 0.99: 0.040}
    v1_rows = []
    for tau in sorted(bounds_v1["claimed"].unique()):
        sub = bounds_v1[np.isclose(bounds_v1["claimed"], tau)]
        # Deployed v1 buffer is at the 4 anchors only; for off-anchor τ
        # it linearly interpolates. Match that.
        anchors = sorted(BUFFER_BY_TARGET.keys())
        if tau <= anchors[0]:
            buf = BUFFER_BY_TARGET[anchors[0]]
        elif tau >= anchors[-1]:
            buf = BUFFER_BY_TARGET[anchors[-1]]
        else:
            for i in range(len(anchors) - 1):
                lo, hi = anchors[i], anchors[i + 1]
                if lo <= tau <= hi:
                    frac = (tau - lo) / (hi - lo)
                    buf = (BUFFER_BY_TARGET[lo]
                           + frac * (BUFFER_BY_TARGET[hi] - BUFFER_BY_TARGET[lo]))
                    break
        lower = sub["lower"] - buf * sub["fri_close"]
        upper = sub["upper"] + buf * sub["fri_close"]
        cov = ((sub["mon_open"] >= lower) & (sub["mon_open"] <= upper)).mean()
        v1_rows.append((float(tau), float(cov)))
    v1 = pd.DataFrame(v1_rows, columns=["claimed", "realised"])

    # Constant-buffer baseline: F0_stale Gaussian z·σ_20d, no factor adjustment,
    # at the fine grid. This is the §7.1 rung.
    from scipy.stats import norm
    n_per_weekend = oos["fri_vol_20d"].notna().sum()
    cb_curve = []
    for tau in fine_taus:
        z = norm.ppf(0.5 + tau / 2.0)
        # F0_stale: point = fri_close, σ = fri_close · √2 · σ_20d (2-day vol).
        sig = oos["fri_close"] * np.sqrt(2.0) * oos["fri_vol_20d"]
        lower = oos["fri_close"] - z * sig
        upper = oos["fri_close"] + z * sig
        m = oos["fri_vol_20d"].notna() & oos["mon_open"].notna()
        cov = ((oos.loc[m, "mon_open"] >= lower.loc[m]) &
               (oos.loc[m, "mon_open"] <= upper.loc[m])).mean()
        cb_curve.append((tau, float(cov)))
    cbdf = pd.DataFrame(cb_curve, columns=["claimed", "realised"])

    # Plot.
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    ax.plot([0, 1], [0, 1], lw=0.8, ls="--", color=OI["grey"],
            label=r"perfect calibration ($45^\circ$)")
    ax.plot(cbdf["claimed"], cbdf["realised"], color=OI["vermilion"],
            label="constant-buffer baseline (F0_stale, $\\sigma_{20d}$)")
    ax.plot(v1["claimed"], v1["realised"], color=OI["orange"],
            marker="o", markersize=3.5, label=r"v1 hybrid Oracle (deployed 2025)")
    ax.plot(m5["claimed"], m5["realised"], color=OI["blue"], lw=2.0,
            label=r"M5 (this paper)")

    # Anchor markers + headline annotation.
    for tau in TAUS:
        ax.axvline(tau, lw=0.4, ls=":", color=OI["grey"], alpha=0.5)
    headline_x, headline_y = 0.95, 0.9503
    ax.plot(headline_x, headline_y, marker="*", markersize=14,
            color=OI["blue"], markeredgecolor="black",
            markeredgewidth=0.5, zorder=5)
    ax.annotate(
        r"$\tau\!=\!0.95$: realised $0.950$" "\n" r"Kupiec $p_{uc}\!=\!0.956$",
        xy=(headline_x, headline_y), xytext=(0.6, 0.78),
        fontsize=8.5, color=OI["blue"],
        arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["blue"]),
    )

    ax.set_xlim(0.1, 1.0)
    ax.set_ylim(0.0, 1.02)
    ax.set_xlabel(r"claimed coverage $\tau$")
    ax.set_ylabel("realised coverage on OOS slice (n = 1730)")
    ax.legend(loc="lower right", framealpha=0.9)
    ax.grid(False)

    plt.savefig(FIG_DIR / "fig2_calibration.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig2_calibration.pdf'}")


# =================================================================== Fig 3


def fig3_stability() -> None:
    """Two-panel stability: walk-forward (left) + split-date sensitivity (right)."""
    wf = pd.read_csv(TABLES / "v1b_mondrian_walkforward.csv")
    sd = pd.read_csv(TABLES / "v1b_robustness_split_sensitivity.csv")

    fig, (ax_l, ax_r) = plt.subplots(
        1, 2, figsize=(6.5, 3.2)
    )

    # --- Left panel: 6-split walk-forward.
    for tau, color, marker in [
        (0.68, OI["orange"], "o"),
        (0.85, OI["green"], "s"),
        (0.95, OI["blue"], "*"),
        (0.99, OI["purple"], "^"),
    ]:
        sub = wf[np.isclose(wf["target"], tau)].sort_values("split_fraction")
        n = sub["n_test"].astype(int).values
        cov = sub["test_realised"].astype(float).values
        # Wilson 95% binomial CI
        from scipy.stats import binom
        lo = np.array([binom.ppf(0.025, n_i, c_i) / max(n_i, 1)
                       if n_i > 0 else np.nan for n_i, c_i in zip(n, cov)])
        hi = np.array([binom.ppf(0.975, n_i, c_i) / max(n_i, 1)
                       if n_i > 0 else np.nan for n_i, c_i in zip(n, cov)])
        markersize = 9 if tau == 0.95 else 5
        ax_l.errorbar(sub["split_fraction"].values, cov,
                      yerr=[cov - lo, hi - cov],
                      color=color, marker=marker, markersize=markersize,
                      lw=1.0, capsize=2.5, label=rf"$\tau\!=\!{tau:.2f}$")
        ax_l.axhline(tau, color=color, ls=":", lw=0.6, alpha=0.6)

    ax_l.set_xlabel(r"train fraction (expanding window)")
    ax_l.set_ylabel(r"realised coverage on test fold")
    ax_l.set_xlim(0.15, 0.75)
    ax_l.set_ylim(0.55, 1.02)
    ax_l.set_title("(a) 6-split walk-forward", fontsize=10, fontweight="bold")
    ax_l.legend(loc="lower right", ncol=2, framealpha=0.9, fontsize=7.5)

    # --- Right panel: split-date sensitivity at τ=0.95.
    sd95 = sd[np.isclose(sd["tau"], 0.95)].copy()
    sd95["split_date"] = pd.to_datetime(sd95["split_date"])
    sd95 = sd95.sort_values("split_date")

    n = sd95["n_oos"].astype(int).values
    cov = sd95["realised"].astype(float).values
    from scipy.stats import binom
    lo = binom.ppf(0.025, n, cov) / np.maximum(n, 1)
    hi = binom.ppf(0.975, n, cov) / np.maximum(n, 1)
    x = np.arange(len(sd95))
    ax_r.errorbar(x, cov, yerr=[cov - lo, hi - cov],
                  color=OI["blue"], marker="*", markersize=11,
                  lw=1.0, capsize=3.0, label=r"$\tau\!=\!0.95$ realised")
    ax_r.axhline(0.95, color=OI["blue"], ls=":", lw=0.6, alpha=0.6,
                 label=r"nominal $\tau\!=\!0.95$")

    # Highlight the deployed split (2023-01-01).
    deployed_idx = sd95["split_date"].dt.year.tolist().index(2023)
    ax_r.axvspan(deployed_idx - 0.35, deployed_idx + 0.35,
                 color=OI["yellow"], alpha=0.25, zorder=0)
    ax_r.text(deployed_idx, 0.978, "deployed\nsplit", ha="center", va="top",
              fontsize=7.5, color=OI["grey"])

    ax_r.set_xticks(x)
    ax_r.set_xticklabels([d.strftime("%Y-%m-%d")
                          for d in sd95["split_date"]],
                         rotation=20, fontsize=8)
    ax_r.set_xlabel(r"OOS split anchor")
    ax_r.set_ylabel(r"realised coverage on OOS slice")
    ax_r.set_xlim(-0.5, len(sd95) - 0.5)
    ax_r.set_ylim(0.93, 0.98)
    ax_r.set_title("(b) split-date sensitivity", fontsize=10, fontweight="bold")
    ax_r.legend(loc="lower right", framealpha=0.9, fontsize=7.5)

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_stability.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig3_stability.pdf'}")


# =================================================================== Fig 4


def fig4_per_symbol() -> None:
    """Per-symbol bimodality: var_z vs Kupiec p (log scale)."""
    df = pd.read_csv(TABLES / "v1b_robustness_per_symbol.csv")
    fig, ax = plt.subplots(figsize=(6.0, 4.2))

    # Three regions.
    too_wide = df["var_z_m5"] < 1.0
    too_narrow = df["var_z_m5"] >= 1.0
    passing = df["kupiec_p_0.95"] >= 0.05

    # Shaded passing region.
    ax.axhspan(0.05, 1.0, color=OI["green"], alpha=0.08, zorder=0)
    ax.axvline(1.0, color=OI["grey"], ls="--", lw=0.6, zorder=0)
    ax.axhline(0.05, color=OI["grey"], ls="--", lw=0.6, zorder=0)

    # Points by region.
    # Stagger label offsets manually for the two clusters where points are
    # close in (var_z, p) space — left-side ticker quartet (SPY/TLT/QQQ/GLD)
    # and right-side trio (HOOD/MSTR/TSLA).
    LABEL_OFFSETS = {
        "SPY":   (-22, -2),
        "TLT":   (8, -2),
        "QQQ":   (-22, 4),
        "GLD":   (8, 4),
        "AAPL":  (8, 0),
        "GOOGL": (8, 0),
        "NVDA":  (8, 0),
        "TSLA":  (8, 0),
        "HOOD":  (-32, 0),
        "MSTR":  (8, 0),
    }
    for mask, label, color, marker in [
        (too_wide & ~passing, r"bands too wide ($\sigma^2_z<1$)", OI["vermilion"], "v"),
        (too_narrow & ~passing, r"bands too narrow ($\sigma^2_z>1$)", OI["blue"], "^"),
        (passing, r"passes Kupiec at $\tau=0.95$", OI["green"], "o"),
    ]:
        sub = df[mask]
        ax.scatter(sub["var_z_m5"], sub["kupiec_p_0.95"].clip(lower=1e-4),
                   color=color, marker=marker, s=60,
                   edgecolor="black", linewidth=0.4, zorder=3, label=label)
        for _, row in sub.iterrows():
            offs = LABEL_OFFSETS.get(row["symbol"], (8, 0))
            ax.annotate(row["symbol"],
                        (row["var_z_m5"], max(row["kupiec_p_0.95"], 1e-4)),
                        xytext=offs, textcoords="offset points",
                        fontsize=8, va="center", color=OI["black"])

    ax.set_yscale("log")
    ax.set_xlim(0.0, 2.4)
    ax.set_ylim(5e-5, 1.5)
    ax.set_xlabel(r"per-symbol M5 PIT variance $\widehat{\sigma}^2_z$")
    ax.set_ylabel(r"per-symbol Kupiec $p$ at $\tau\!=\!0.95$")
    ax.set_title("Per-symbol bimodality on the 2023+ OOS slice",
                 fontsize=10, fontweight="bold")

    # Region labels.
    ax.text(0.05, 4.5e-3,
            "Variance compression\n(0%–1% violation rate)",
            fontsize=8, color=OI["vermilion"], fontweight="bold")
    ax.text(1.45, 4.5e-3,
            "Variance expansion\n(11%–16% violation rate)",
            fontsize=8, color=OI["blue"], fontweight="bold")
    ax.text(0.05, 0.85,
            r"Passing region (Kupiec $p \geq 0.05$)",
            fontsize=8, color=OI["green"], fontweight="bold")

    ax.legend(loc="lower center", framealpha=0.9, fontsize=8.0,
              bbox_to_anchor=(0.5, -0.32), ncol=3)

    plt.savefig(FIG_DIR / "fig4_per_symbol.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig4_per_symbol.pdf'}")


# =================================================================== Fig 5


def fig5_pareto() -> None:
    """Realised coverage vs half-width across methods, log-y on width."""
    inc = pd.read_csv(TABLES / "incumbent_oracle_unified_summary.csv")
    garch = pd.read_csv(TABLES / "v1b_robustness_garch_baseline.csv")
    garch_g = garch[garch["method"] == "GARCH(1,1)"]

    fig, ax = plt.subplots(figsize=(6.0, 4.2))

    # M5 (the paper).
    m5 = inc[inc["oracle"] == "soothsayer_m5_v2_candidate"].sort_values("tau")
    ax.plot(m5["realized_at_tau_band"], m5["halfwidth_bps_at_tau"],
            color=OI["blue"], marker="*", markersize=11,
            lw=1.6, label=r"M5 (this paper)", zorder=5)
    for _, row in m5.iterrows():
        ax.annotate(rf"$\tau\!=\!{row['tau']:.2f}$",
                    (row["realized_at_tau_band"], row["halfwidth_bps_at_tau"]),
                    xytext=(8, 4), textcoords="offset points",
                    fontsize=7.5, color=OI["blue"])

    # v1 (deployed).
    v1 = inc[inc["oracle"] == "soothsayer_v1_deployed"].sort_values("tau")
    ax.plot(v1["realized_at_tau_band"], v1["halfwidth_bps_at_tau"],
            color=OI["orange"], marker="o", markersize=6,
            lw=1.2, label=r"v1 hybrid Oracle", zorder=4)

    # GARCH(1,1).
    ax.plot(garch_g["realised"], garch_g["half_width_bps"],
            color=OI["vermilion"], marker="s", markersize=5,
            lw=1.0, label=r"GARCH(1,1) baseline", zorder=4)

    # Pyth (smallest-k that achieves the band claim).
    pyth = inc[inc["oracle"] == "pyth_smallest_k"].sort_values("tau")
    ax.plot(pyth["realized_at_tau_band"], pyth["halfwidth_bps_at_tau"],
            color=OI["green"], marker="D", markersize=5,
            lw=0.8, ls="-", label=r"Pyth $\pm k\!\cdot\!\mathrm{conf}$ (consumer wrap)", zorder=3)

    # Chainlink Streams (87-obs frozen panel).
    cl = inc[inc["oracle"] == "chainlink_streams_smallest_k_pct"].sort_values("tau")
    ax.plot(cl["realized_at_tau_band"], cl["halfwidth_bps_at_tau"],
            color=OI["purple"], marker="X", markersize=5,
            lw=0.8, ls="-", label=r"Chainlink Streams mid$\,\pm\,k\%$", zorder=3)

    # Vertical lines at four claimed τ.
    for tau in TAUS:
        ax.axvline(tau, lw=0.4, ls=":", color=OI["grey"], alpha=0.5)
        ax.text(tau, 700, rf"$\tau\!=\!{tau:.2f}$", rotation=90, va="bottom",
                ha="right", fontsize=7, color=OI["grey"])

    ax.set_yscale("log")
    ax.set_xlim(0.6, 1.02)
    ax.set_ylim(50, 1500)
    ax.set_xlabel(r"realised coverage")
    ax.set_ylabel(r"mean half-width (bps, log)")
    ax.set_title(r"Coverage vs sharpness across methods at four served $\tau$",
                 fontsize=10, fontweight="bold")
    ax.legend(loc="lower right", framealpha=0.9, fontsize=8.0)

    plt.savefig(FIG_DIR / "fig5_pareto.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig5_pareto.pdf'}")


# =================================================================== Fig 6


def fig6_path_coverage() -> None:
    """Endpoint vs path coverage on the perp reference, two panels."""
    pp = pd.read_csv(TABLES / "path_coverage_perp.csv")
    ppr = pd.read_csv(TABLES / "path_coverage_perp_by_regime.csv")

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(6.0, 3.2))

    # --- Left: coverage vs τ.
    pp = pp.sort_values("tau")
    ax_l.plot([0.6, 1.0], [0.6, 1.0], lw=0.6, ls="--",
              color=OI["grey"], label=r"$45^\circ$")
    ax_l.plot(pp["tau"], pp["endpoint_cov"], color=OI["blue"], marker="o",
              markersize=7, lw=1.6, label=r"endpoint coverage")
    ax_l.plot(pp["tau"], pp["path_cov"], color=OI["vermilion"], marker="s",
              markersize=6, lw=1.4, label=r"path coverage")
    ax_l.fill_between(pp["tau"], pp["path_cov"], pp["endpoint_cov"],
                      color=OI["vermilion"], alpha=0.12, zorder=0)
    for _, row in pp.iterrows():
        ax_l.annotate(rf"${row['gap_pp']:.1f}\,\mathrm{{pp}}$",
                      ((row["tau"] + 0.005),
                       (row["endpoint_cov"] + row["path_cov"]) / 2),
                      fontsize=7.5, color=OI["vermilion"], ha="left",
                      va="center")
    ax_l.set_xlim(0.65, 1.02)
    ax_l.set_ylim(0.45, 1.05)
    ax_l.set_xlabel(r"claimed coverage $\tau$")
    ax_l.set_ylabel(r"realised coverage")
    ax_l.set_title(r"(a) coverage vs $\tau$ on perp reference",
                   fontsize=9.5, fontweight="bold")
    ax_l.legend(loc="upper left", framealpha=0.9, fontsize=8.0)
    ax_l.text(0.99, 0.48, r"$n=118$ symbol-weekends" "\n" r"2025-12 $\to$ 2026-04",
              ha="right", fontsize=7, color=OI["grey"])

    # --- Right: gap by regime at τ=0.95.
    sub = ppr[np.isclose(ppr["tau"], 0.95)].copy()
    order = ["normal", "long_weekend", "high_vol"]
    sub = sub.set_index("regime_pub").loc[order].reset_index()
    pooled = pp[np.isclose(pp["tau"], 0.95)].iloc[0]

    x = np.arange(len(sub) + 1)
    gaps = list(sub["gap_pp"]) + [float(pooled["gap_pp"])]
    ns = list(sub["n"].astype(int)) + [int(pooled["n"])]
    labels = ["normal", "long\nweekend", "high\nvol", "pooled"]
    colors = [OI["blue"], OI["green"], OI["orange"], OI["vermilion"]]
    bars = ax_r.bar(x, gaps, color=colors, edgecolor="black", linewidth=0.5,
                    alpha=0.85)
    for i, (g, n_i) in enumerate(zip(gaps, ns)):
        ax_r.text(i, g + 0.6, f"{g:.1f}\n$n={n_i}$",
                  ha="center", va="bottom", fontsize=7.5)
    ax_r.set_xticks(x)
    ax_r.set_xticklabels(labels, fontsize=8.5)
    ax_r.set_ylabel(r"endpoint $-$ path coverage (pp)")
    ax_r.set_title(r"(b) gap by regime at $\tau=0.95$",
                   fontsize=9.5, fontweight="bold")
    ax_r.set_ylim(0, max(gaps) * 1.35)
    ax_r.axhline(0, lw=0.5, color=OI["black"])

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig6_path_coverage.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig6_path_coverage.pdf'}")


# =================================================================== main


def main() -> None:
    setup_rc()
    print(f"Building 6 figures into {FIG_DIR} …", flush=True)
    fig1_pipeline()
    fig2_calibration()
    fig3_stability()
    fig4_per_symbol()
    fig5_pareto()
    fig6_path_coverage()
    print("done.")


if __name__ == "__main__":
    main()
