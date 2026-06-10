"""
Build the Paper 1 figures.

Outputs PDFs into `reports/paper1_coverage_inversion/figures/`:

  fig1_pipeline.pdf          Architecture / data-flow block diagram
  fig2_calibration.pdf       Calibration curve: deployed architecture vs
                             GARCH(1,1)-t anchor markers (caption-matching
                             design; only methods that emit a calibrated band)
  fig3_stability.pdf         Walk-forward + split-date sensitivity
  fig4_per_symbol.pdf        Per-symbol violation rate vs nominal at τ=0.95,
                             deployed (blue) vs unweighted-Mondrian comparator
                             (grey) — the §6.4.1 contrast in one panel
  fig5_pareto.pdf            Coverage vs half-width across the two methods
                             that emit a calibrated coverage band (deployed +
                             GARCH-t). Incumbent oracle surfaces are
                             deliberately excluded — §9.6: a coverage-vs-
                             sharpness comparison against them is not
                             well-defined.
  fig6_path_coverage.pdf     Endpoint vs path coverage across τ
                             (single panel; perp reference, n = 118)
  fig9_boj_anatomy.pdf       Anatomy of the served band on the worst observed
                             weekend (2024-08-02 BoJ unwind) — nested bands,
                             factor-adjusted point, realised opens, from the
                             deployed artefact
  simulation_summary.pdf     4-DGP simulation study (copied from
                             reports/figures/ produced by run_simulation_study.py)

Internal codenames (M5 / M6 / LWC / Soothsayer-v0) are deliberately kept OUT
of figure artwork — legends use the paper's descriptive names ("this paper",
"unweighted Mondrian", "constant buffer"). See revision_critique.md A5.

Conventions
-----------
Single-column 6.0 in width (matches arxiv.sty NIPS-derived layout).
Okabe-Ito colorblind-safe palette. Computer Modern math via mathtext (no
external usetex dependency). PDFs (vector) for clean scaling.

Run:
  uv run python scripts/build_paper1_figures.py
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

from soothsayer.backtest.calibration import (
    add_sigma_hat_sym_ewma,
    compute_score_lwc,
    fit_c_bump_schedule,
    serve_bands_lwc,
    train_lwc_quantile_table,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

FIG_DIR = REPORTS / "paper1_coverage_inversion" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLES = REPORTS / "tables"
SIM_FIG = REPORTS / "figures"  # produced by run_simulation_study.py

SPLIT_DATE = date(2023, 1, 1)
TAUS = (0.68, 0.85, 0.95, 0.99)
SIGMA_HL = 8  # EWMA σ̂ half-life (weekends) — matches deployed M6.

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


# ============================================================ shared helpers


def _load_panel() -> pd.DataFrame:
    """Load + clean v1b_panel.parquet for downstream LWC fits."""
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    return panel


def _load_lwc_artefact() -> tuple[
    dict[str, dict[float, float]],
    dict[float, float],
    dict[float, float],
]:
    """Load the deployed M6 schedules from the live LWC artefact sidecar.

    Returns (regime_quantile_table, c_bump_schedule, delta_shift_schedule).
    Pulling from the artefact (not re-fitting) keeps the figure aligned
    byte-for-byte with the Oracle a deployed consumer would read."""
    art = json.loads((DATA_PROCESSED / "lwc_artefact_v1.json").read_text())
    qt = {
        r: {float(t): float(v) for t, v in row.items()}
        for r, row in art["regime_quantile_table"].items()
    }
    cb = {float(t): float(v) for t, v in art["c_bump_schedule"].items()}
    delta = {float(t): float(v) for t, v in art["delta_shift_schedule"].items()}
    return qt, cb, delta


def _serve_m6_bands(
    panel: pd.DataFrame,
    taus: tuple[float, ...] = TAUS,
) -> tuple[pd.DataFrame, dict[float, pd.DataFrame], str]:
    """Add σ̂ EWMA HL=8 to `panel` and serve M6 bands at the deployed schedule.

    Returns (panel_with_sigma, {τ: DataFrame(lower, upper)}, scale_col)."""
    scale_col = f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HL}"
    panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HL)
    qt, cb, delta = _load_lwc_artefact()
    bands = serve_bands_lwc(
        panel,
        qt,
        cb,
        scale_col=scale_col,
        taus=taus,
        delta_shift_schedule=delta,
    )
    return panel, bands, scale_col


# =================================================================== Fig 0


def fig0_weekend_returns() -> None:
    """Per-symbol weekend log-return panel (CAViaR Figure 1 analogue).

    10 sub-panels, one per ticker, weekend log-returns 2014–2026 with
    the 2023-01-01 train/test split as a vertical dashed line and a
    marginal histogram on the right of each panel. The 'we know our
    data' figure for §5."""
    panel = _load_panel()
    panel = panel[panel["symbol"].isin([
        "SPY", "QQQ", "AAPL", "GOOGL", "NVDA", "TSLA", "HOOD",
        "MSTR", "GLD", "TLT",
    ])].copy()
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"])
    panel["weekend_log_ret"] = np.log(panel["mon_open"]
                                      / panel["fri_close"])

    sym_order = ["SPY", "QQQ", "AAPL", "GOOGL", "NVDA",
                 "TSLA", "HOOD", "MSTR", "GLD", "TLT"]
    fig = plt.figure(figsize=(7.0, 8.6))
    gs = fig.add_gridspec(
        nrows=10, ncols=2, width_ratios=[4.5, 1],
        hspace=0.35, wspace=0.05,
    )

    split_dt = pd.Timestamp("2023-01-01")
    # The three named stress weekends the §5.2 caption points at —
    # annotated so a reader can tell which spike is which (critique C/fig0).
    # (date, label, label y-offset pts) — BoJ and tariff are ~8 months
    # apart on a 12-year axis, so their labels are staggered vertically.
    EVENTS = [
        (pd.Timestamp("2020-03-06"), "COVID", 3),
        (pd.Timestamp("2024-08-02"), "BoJ", 3),
        (pd.Timestamp("2025-04-04"), "tariff", 11),
    ]
    for i, sym in enumerate(sym_order):
        sub = panel[panel["symbol"] == sym].sort_values("fri_ts")
        if sub.empty:
            continue
        ax_ts = fig.add_subplot(gs[i, 0])
        ax_hist = fig.add_subplot(gs[i, 1], sharey=ax_ts)
        rets_pct = 100.0 * sub["weekend_log_ret"].to_numpy()
        ax_ts.plot(sub["fri_ts"], rets_pct,
                   color=OI["blue"], linewidth=0.55, alpha=0.85)
        ax_ts.axvline(split_dt, color=OI["vermilion"],
                      linewidth=0.8, linestyle="--", alpha=0.7)
        for ev_dt, ev_label, ev_dy in EVENTS:
            ax_ts.axvline(ev_dt, color=OI["grey"],
                          linewidth=0.5, linestyle="-", alpha=0.35)
            if i == 0:  # label once, on the top (SPY) panel
                ax_ts.annotate(
                    ev_label, xy=(ev_dt, 1.0),
                    xycoords=("data", "axes fraction"),
                    xytext=(0, ev_dy), textcoords="offset points",
                    ha="center", va="bottom", fontsize=6.5,
                    color=OI["grey"], annotation_clip=False,
                )
        ax_ts.axhline(0.0, color=OI["grey"], linewidth=0.4, alpha=0.5)
        ymax = float(np.nanpercentile(np.abs(rets_pct), 99.5))
        ymax = max(ymax * 1.1, 1.0)
        ax_ts.set_ylim(-ymax, ymax)
        ax_ts.set_xlim(pd.Timestamp("2014-01-01"),
                       pd.Timestamp("2026-05-15"))
        ax_ts.text(0.012, 0.86, sym, transform=ax_ts.transAxes,
                   fontsize=9, fontweight="bold", color=OI["black"],
                   ha="left", va="top")
        if i < len(sym_order) - 1:
            ax_ts.set_xticklabels([])
        else:
            ax_ts.set_xlabel("Friday close", fontsize=9)
        ax_ts.set_ylabel("%", fontsize=8, labelpad=1)
        ax_ts.tick_params(axis="both", labelsize=7)

        ax_hist.hist(rets_pct, bins=40, orientation="horizontal",
                     color=OI["blue"], alpha=0.55, edgecolor="none")
        ax_hist.tick_params(axis="x", labelsize=6, pad=1)
        ax_hist.tick_params(axis="y", labelleft=False)
        ax_hist.spines["bottom"].set_visible(False)
        ax_hist.set_xticks([])

    fig.suptitle(
        "Weekend log-returns (Fri close → Mon open), 2014-01-17 → 2026-04-24",
        fontsize=10.5, y=0.995,
    )
    fig.text(
        0.985, 0.011,
        "Vertical dashed line = 2023-01-01 train/OOS split. Right marginal: weekend-return histogram.",
        ha="right", va="bottom", fontsize=7.5, color=OI["grey"],
    )

    out_path = FIG_DIR / "fig0_weekend_returns.pdf"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  wrote {out_path}")


# =================================================================== Fig 1


def fig1_pipeline() -> None:
    """M6 architecture / data-flow diagram. matplotlib patches + arrows."""
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    def box(x, y, w, h, text, fc, ec=OI["black"], fontsize=8.0):
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

    # Top: 5 inputs at Friday 16:00 ET.
    ax.text(50, 57, "Inputs at Friday 16:00 ET", ha="center",
            fontsize=9.5, color=OI["black"], fontweight="bold")
    inputs = [
        (1,    44, 15.5, 9, r"$p_t^{\mathrm{Fri}}$" "\n" r"close",                          "#FDF6E3"),
        (18,   44, 18.5, 9, r"factor return" "\n" r"$\rho(s,t)\!\to\!r_t^F$",               "#FDF6E3"),
        (38,   44, 22.0, 9, r"per-symbol scale" "\n" r"$\hat\sigma_s(t)$ EWMA HL=8",        "#E8F4E8"),
        (61.5, 44, 17.5, 9, r"regime label" "\n" r"$r\!\in\!\{\mathrm{nrm,lw,hv}\}$",        "#FDF6E3"),
        (80.5, 44, 18.5, 9, r"consumer $\tau$" "\n" r"$\in[0.68,0.99]$",                    "#FDF6E3"),
    ]
    for (x, y, w, h, t, fc) in inputs:
        box(x, y, w, h, t, fc)

    # Middle: 5-line lookup, shaded box.
    p = FancyBboxPatch(
        (4, 14), 92, 24, boxstyle="round,pad=0.4,rounding_size=2.0",
        linewidth=1.0, facecolor="#E8F1FA", edgecolor=OI["blue"],
    )
    ax.add_patch(p)
    ax.text(50, 35.5, "Five-line serving lookup", ha="center",
            fontsize=9.5, color=OI["blue"], fontweight="bold")
    eqs = [
        r"$\hat p_t = p_t^{\mathrm{Fri}} \cdot (1 + r_t^F)$",
        r"$q_{\mathrm{eff}} = c(\tau) \cdot q_r(\tau) \quad\quad c\in\{1.000,\,1.000,\,1.079,\,1.003\},\ \delta(\tau)\equiv 0$",
        r"$\mathrm{half}_t = q_{\mathrm{eff}} \cdot \hat\sigma_s(t) \cdot p_t^{\mathrm{Fri}}$",
        r"$L_t = \hat p_t - \mathrm{half}_t,\quad U_t = \hat p_t + \mathrm{half}_t$",
    ]
    for i, eq in enumerate(eqs):
        ax.text(7, 31.5 - 4.0 * i, eq, ha="left", va="center",
                fontsize=9, color=OI["black"])

    # Bottom: receipt with the diagnostic quartet. Field names follow
    # §4.7: target and served coverage are both τ (δ ≡ 0), shown as
    # named fields rather than a bare repeated τ (critique A3).
    box(2, 1, 96, 9,
        r"$\mathrm{PricePoint}\{\,\mathrm{symbol},\, \mathrm{as\_of},\, \tau_{\mathrm{target}}{=}\tau,\, \tau_{\mathrm{served}}{=}\tau,\, \delta(\tau){=}0,\, \hat p_t,\, L_t,\, U_t,\, r,\, \mathrm{sharpness\,bps},\, \mathrm{diagnostics}\{c,\, q_{\mathrm{eff}},\, q_r,\, \hat\sigma_s\}\,\}$",
        "#F5F5F5", ec=OI["grey"], fontsize=7.0)
    ax.text(50, 11.2,
            "Per-read receipt (P1: auditability) — 16 deployment scalars "
            "(12 $q_r$ + 4 $c(\\tau)$) + per-symbol $\\hat\\sigma_s(t)$",
            ha="center", fontsize=8.5, color=OI["grey"], fontweight="bold")

    # Arrows down from inputs into shaded box. The lookup→receipt arrow
    # is offset from centre so it doesn't pierce the receipt label text.
    for (x, _, w, _, _, _) in inputs:
        arrow(x + w / 2, 44, x + w / 2, 38.5)
    arrow(25, 14, 25, 10.2)

    plt.savefig(FIG_DIR / "fig1_pipeline.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig1_pipeline.pdf'}")


# =================================================================== Fig 2


def fig2_calibration() -> None:
    """Calibration curve: deployed architecture vs GARCH(1,1)-t markers.

    Caption-matching design (§6.3.2): the deployed architecture (blue) on
    a fine τ grid over the 1,730-row 2023+ OOS slice tracks the 45°
    diagonal; GARCH(1,1)-t (vermilion squares) at the four served anchors
    visibly under-covers at τ ∈ {0.68, 0.85, 0.95}. Star marks the
    headline τ=0.95 result. Restricted to methods that emit a calibrated
    coverage band (§9.6) — no incumbent surfaces, no internal-codename
    comparators."""
    panel = _load_panel()

    fine_taus = tuple(np.round(np.linspace(0.10, 0.99, 60), 4))

    # ---- Deployed architecture (LWC + EWMA HL=8) fine-grid serve.
    panel_lwc = add_sigma_hat_sym_ewma(panel.copy(), half_life=SIGMA_HL)
    scale_col = f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HL}"
    panel_lwc["score_lwc"] = compute_score_lwc(panel_lwc, scale_col=scale_col)
    train_lwc = panel_lwc[
        (panel_lwc["fri_ts"] < SPLIT_DATE) & panel_lwc["score_lwc"].notna()
    ]
    oos_lwc = (
        panel_lwc[(panel_lwc["fri_ts"] >= SPLIT_DATE)
                  & panel_lwc["score_lwc"].notna()]
        .sort_values(["symbol", "fri_ts"])
        .reset_index(drop=True)
    )
    qt_lwc = train_lwc_quantile_table(
        train_lwc,
        train_mask=np.ones(len(train_lwc), dtype=bool),
        regime_col="regime_pub",
        scale_col=scale_col,
        anchors=fine_taus,
        score_col="score_lwc",
    )
    cb_lwc = fit_c_bump_schedule(
        oos_lwc, qt_lwc, cell_col="regime_pub", taus=fine_taus,
        score_col="score_lwc",
    )
    bounds_lwc = serve_bands_lwc(
        oos_lwc, qt_lwc, cb_lwc,
        cell_col="regime_pub", scale_col=scale_col,
        taus=fine_taus,
        delta_shift_schedule={t: 0.0 for t in fine_taus},
    )
    m6_curve = []
    for tau in fine_taus:
        b = bounds_lwc[tau]
        cov = ((oos_lwc["mon_open"] >= b["lower"]) &
               (oos_lwc["mon_open"] <= b["upper"])).mean()
        m6_curve.append((tau, float(cov)))
    m6 = pd.DataFrame(m6_curve, columns=["claimed", "realised"])

    # ---- GARCH(1,1)-t at the four served anchors (§6.4.3 baseline).
    garch = pd.read_csv(TABLES / "m6_lwc_robustness_garch_t_baseline.csv")
    if "garch_dist" in garch.columns:
        garch = garch[garch["garch_dist"] == "t"]
    garch = garch.sort_values("tau")

    # ---- Plot.
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    ax.plot([0, 1], [0, 1], lw=0.8, ls="--", color=OI["grey"],
            label=r"perfect calibration ($45^\circ$)")
    ax.plot(m6["claimed"], m6["realised"], color=OI["blue"], lw=2.0,
            label=r"this paper (deployed architecture)")
    ax.scatter(garch["tau"], garch["realised"],
               color=OI["vermilion"], marker="s", s=42, zorder=5,
               edgecolor="black", linewidth=0.4,
               label=r"GARCH(1,1)-$t$ baseline (four anchors)")

    # Anchor markers + headline annotation.
    for tau in TAUS:
        ax.axvline(tau, lw=0.4, ls=":", color=OI["grey"], alpha=0.5)
    headline_x, headline_y = 0.95, 0.9503
    ax.plot(headline_x, headline_y, marker="*", markersize=14,
            color=OI["blue"], markeredgecolor="black",
            markeredgewidth=0.5, zorder=5)
    ax.annotate(
        r"$\tau\!=\!0.95$: realised $0.950$" "\n" r"Kupiec $p_{uc}\!=\!0.956$",
        xy=(headline_x, headline_y), xytext=(0.55, 0.78),
        fontsize=8.5, color=OI["blue"],
        arrowprops=dict(arrowstyle="-", lw=0.6, color=OI["blue"]),
    )

    ax.set_xlim(0.1, 1.0)
    ax.set_ylim(0.0, 1.02)
    ax.set_xlabel(r"claimed coverage $\tau$")
    ax.set_ylabel(r"realised coverage on OOS slice (n = 1,730)")
    ax.legend(loc="lower right", framealpha=0.9, fontsize=8.0)
    ax.grid(False)

    plt.savefig(FIG_DIR / "fig2_calibration.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig2_calibration.pdf'}")


# =================================================================== Fig 3


def fig3_stability() -> None:
    """Two-panel M6 stability: walk-forward (left) + split-date sensitivity (right)."""
    # Walk-forward at M6's δ ≡ 0 schedule (the LWC delta-sweep CSV).
    wf = pd.read_csv(TABLES / "v1b_lwc_delta_sweep.csv")
    wf = wf[np.isclose(wf["delta"], 0.0)].copy()

    # Split-date sensitivity from M6 LWC robustness.
    sd = pd.read_csv(TABLES / "m6_lwc_robustness_split_sensitivity.csv")
    sd = sd[sd["forecaster"] == "lwc"].copy()

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(6.5, 3.2))

    # ---- Left: 6-split walk-forward.
    from scipy.stats import binom
    for tau, color, marker in [
        (0.68, OI["orange"], "o"),
        (0.85, OI["green"], "s"),
        (0.95, OI["blue"], "*"),
        (0.99, OI["purple"], "^"),
    ]:
        sub = wf[np.isclose(wf["target"], tau)].sort_values("split_fraction")
        if sub.empty:
            continue
        n = sub["n_test"].astype(int).to_numpy()
        cov = sub["test_realised"].astype(float).to_numpy()
        lo = np.array([
            binom.ppf(0.025, n_i, c_i) / max(n_i, 1) if n_i > 0 else np.nan
            for n_i, c_i in zip(n, cov)
        ])
        hi = np.array([
            binom.ppf(0.975, n_i, c_i) / max(n_i, 1) if n_i > 0 else np.nan
            for n_i, c_i in zip(n, cov)
        ])
        markersize = 9 if tau == 0.95 else 5
        ax_l.errorbar(
            sub["split_fraction"].to_numpy(), cov,
            yerr=[cov - lo, hi - cov],
            color=color, marker=marker, markersize=markersize,
            lw=1.0, capsize=2.5, label=rf"$\tau\!=\!{tau:.2f}$",
        )
        ax_l.axhline(tau, color=color, ls=":", lw=0.6, alpha=0.6)

    ax_l.set_xlabel(r"train fraction (expanding window)")
    ax_l.set_ylabel(r"realised coverage on test fold")
    ax_l.set_xlim(0.15, 0.75)
    ax_l.set_ylim(0.55, 1.02)
    ax_l.set_title("(a) 6-split walk-forward ($\\delta\\equiv 0$)",
                   fontsize=10, fontweight="bold")
    ax_l.legend(loc="lower right", ncol=2, framealpha=0.9, fontsize=7.5)

    # ---- Right: split-date sensitivity at τ=0.95.
    sd95 = sd[np.isclose(sd["tau"], 0.95)].copy()
    sd95["split_date"] = pd.to_datetime(sd95["split_date"])
    sd95 = sd95.sort_values("split_date")

    n = sd95["n_oos"].astype(int).to_numpy()
    cov = sd95["realised"].astype(float).to_numpy()
    lo = binom.ppf(0.025, n, cov) / np.maximum(n, 1)
    hi = binom.ppf(0.975, n, cov) / np.maximum(n, 1)
    x = np.arange(len(sd95))
    ax_r.errorbar(
        x, cov, yerr=[cov - lo, hi - cov],
        color=OI["blue"], marker="*", markersize=11,
        lw=1.0, capsize=3.0, label=r"$\tau\!=\!0.95$ realised",
    )
    ax_r.axhline(0.95, color=OI["blue"], ls=":", lw=0.6, alpha=0.6,
                 label=r"nominal $\tau\!=\!0.95$")

    if 2023 in sd95["split_date"].dt.year.tolist():
        deployed_idx = sd95["split_date"].dt.year.tolist().index(2023)
        ax_r.axvspan(deployed_idx - 0.35, deployed_idx + 0.35,
                     color=OI["yellow"], alpha=0.25, zorder=0)
        ax_r.text(deployed_idx, 0.965, "deployed\nsplit",
                  ha="center", va="top",
                  fontsize=7.5, color=OI["grey"])

    ax_r.set_xticks(x)
    ax_r.set_xticklabels([d.strftime("%Y-%m-%d")
                          for d in sd95["split_date"]],
                         rotation=20, fontsize=8)
    ax_r.set_xlabel(r"OOS split anchor")
    ax_r.set_ylabel(r"realised coverage on OOS slice")
    ax_r.set_xlim(-0.5, len(sd95) - 0.5)
    ax_r.set_ylim(0.93, 0.97)
    ax_r.set_title("(b) split-date sensitivity",
                   fontsize=10, fontweight="bold")
    ax_r.legend(loc="lower right", framealpha=0.9, fontsize=7.5)

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_stability.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig3_stability.pdf'}")


# =================================================================== Fig 4


def fig4_per_symbol() -> None:
    """Single-panel per-symbol violation rate at τ=0.95 — deployed vs
    unweighted-Mondrian comparator.

    x-axis: 10 symbols ordered by realised PIT variance σ̂²_z (low → high).
    y-axis: per-symbol violation rate at τ=0.95, with binomial 95% CI band
    around the nominal 0.05 rate shaded. All 10 deployed-architecture
    symbols sit inside the band (the §6.4.1 headline); the unweighted
    Mondrian comparator's rates (grey ×, from
    m6_per_symbol_kupiec_4methods.csv, method=m5) disperse outside it —
    the 10/10-vs-2/10 contrast in one panel (revision_critique C/fig4)."""
    df = pd.read_csv(TABLES / "m6_lwc_robustness_per_symbol.csv")
    df = df.sort_values("var_z").reset_index(drop=True)

    # Unweighted-Mondrian comparator rates at τ=0.95, aligned to the
    # same symbol order.
    grid = pd.read_csv(TABLES / "m6_per_symbol_kupiec_4methods.csv")
    m5 = (grid[(grid["method"] == "m5") & np.isclose(grid["tau"], 0.95)]
          .set_index("symbol")["viol_rate"]
          .reindex(df["symbol"]))

    from scipy.stats import binom
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle

    n_oos = int(df["n_oos"].iloc[0])
    target = 0.05  # 1 − τ at τ=0.95
    lo_count, hi_count = binom.interval(0.95, n_oos, target)
    lo_rate = lo_count / n_oos
    hi_rate = hi_count / n_oos

    fig, ax = plt.subplots(figsize=(6.4, 3.8))

    # Binomial 95% CI band around nominal 0.05.
    ax.axhspan(lo_rate, hi_rate, color=OI["green"], alpha=0.14, zorder=0)
    ax.axhline(target, color=OI["grey"], ls="--", lw=0.8, zorder=1)

    # Per-symbol violation rates.
    x = np.arange(len(df))
    ax.scatter(
        x, m5.to_numpy(),
        color=OI["grey"], marker="x", linewidth=1.6,
        s=60, zorder=2, alpha=0.9,
    )
    ax.scatter(
        x, df["viol_rate_0.95"],
        color=OI["blue"], edgecolor="black", linewidth=0.5,
        s=85, zorder=3,
    )

    # x-axis: symbol names on the bottom.
    ax.set_xticks(x)
    ax.set_xticklabels(df["symbol"], rotation=0, fontsize=9)
    ax.set_xlabel(
        r"symbol (ordered by per-symbol PIT variance $\hat\sigma^2_z$, low $\to$ high)",
        fontsize=9,
    )
    ax.set_ylabel(r"per-symbol violation rate at $\tau\!=\!0.95$", fontsize=9)
    ax.set_xlim(-0.6, len(df) - 0.4)
    y_max = max(
        float(df["viol_rate_0.95"].max()) * 1.4,
        float(np.nanmax(m5.to_numpy())) * 1.55,  # headroom so the legend
        hi_rate * 1.3,                           # clears the comparator ×s
        0.10,
    )
    ax.set_ylim(0.0, y_max)

    # σ̂²_z values as a secondary x-axis on top.
    ax2 = ax.secondary_xaxis("top")
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{v:.2f}" for v in df["var_z"]],
                        fontsize=7.5, color=OI["grey"])
    ax2.set_xlabel(r"$\hat\sigma^2_z$ (PIT variance per symbol)",
                   fontsize=8, color=OI["grey"])
    ax2.tick_params(colors=OI["grey"])

    # Legend (custom).
    legend_handles = [
        Line2D([0], [0], color=OI["grey"], ls="--", lw=0.8,
               label=r"nominal $1{-}\tau = 0.05$"),
        Rectangle((0, 0), 1, 1, color=OI["green"], alpha=0.14,
                  label=rf"binomial 95% CI ($n={n_oos}$)"),
        Line2D([0], [0], marker="o", color="w",
               markerfacecolor=OI["blue"], markeredgecolor="black",
               markersize=8, label=r"this paper (deployed $\hat\sigma_s$)"),
        Line2D([0], [0], marker="x", color=OI["grey"],
               markersize=7, markeredgewidth=1.6, lw=0,
               label=r"unweighted Mondrian comparator"),
    ]
    ax.legend(handles=legend_handles, loc="upper right",
              framealpha=0.9, fontsize=8.0)

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig4_per_symbol.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig4_per_symbol.pdf'}")


# =================================================================== Fig 5


def fig5_pareto() -> None:
    """Realised coverage vs half-width at the four served τ.

    Restricted to the two methods that emit a calibrated coverage band
    (caption + §9.6 stance): the deployed architecture from
    m6_pooled_oos.csv (forecaster=lwc, pooled) and GARCH(1,1)-t from
    m6_lwc_robustness_garch_t_baseline.csv. Incumbent oracle surfaces
    (Pyth, Chainlink Streams, RedStone, Kamino Scope) do not emit one,
    so a coverage-vs-sharpness comparison against them is not
    well-defined and is deliberately NOT plotted (revision_critique A1)."""
    pooled = pd.read_csv(TABLES / "m6_pooled_oos.csv")

    garch = pd.read_csv(TABLES / "m6_lwc_robustness_garch_t_baseline.csv")
    if "garch_dist" in garch.columns:
        garch = garch[garch["garch_dist"] == "t"]
    garch = garch.sort_values("tau")

    fig, ax = plt.subplots(figsize=(6.0, 4.2))

    # ---- This paper — deployed architecture, pooled OOS at four anchors.
    m6 = pooled[(pooled["forecaster"] == "lwc")
                & (pooled["stratification"] == "pooled")].sort_values("tau")
    ax.plot(m6["realised"], m6["half_width_bps"],
            color=OI["blue"], marker="*", markersize=11,
            lw=1.6, label=r"this paper (deployed architecture)", zorder=5)
    for _, row in m6.iterrows():
        ax.annotate(rf"$\tau\!=\!{row['tau']:.2f}$",
                    (row["realised"], row["half_width_bps"]),
                    xytext=(8, 4), textcoords="offset points",
                    fontsize=7.5, color=OI["blue"])

    # ---- GARCH(1,1)-t baseline.
    ax.plot(garch["realised"], garch["half_width_bps"],
            color=OI["vermilion"], marker="s", markersize=5,
            lw=1.0, label=r"GARCH(1,1)-$t$ baseline", zorder=4)

    # ---- Vertical lines at four claimed τ.
    for tau in TAUS:
        ax.axvline(tau, lw=0.4, ls=":", color=OI["grey"], alpha=0.5)
        ax.text(tau, 105, rf"$\tau\!=\!{tau:.2f}$", rotation=90, va="bottom",
                ha="right", fontsize=7, color=OI["grey"])

    ax.set_yscale("log")
    ax.set_xlim(0.6, 1.02)
    ax.set_ylim(100, 900)
    ax.set_xlabel(r"realised coverage")
    ax.set_ylabel(r"mean half-width (bps, log)")
    ax.legend(loc="lower right", framealpha=0.9, fontsize=8.0)

    plt.savefig(FIG_DIR / "fig5_pareto.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig5_pareto.pdf'}")


# =================================================================== Fig 6


def fig6_path_coverage() -> None:
    """Single-panel M6 endpoint vs path coverage on the perp reference.

    The per-row CSV `path_coverage_perp_per_row.csv` carries the perp
    side (`perp_path_lo` / `perp_path_hi`). We recompute M6 bands on the
    fly using the deployed LWC schedules + EWMA HL=8 σ̂, then merge against
    the same per-row keys to read off M6 path / endpoint coverage at the
    four anchors. Single panel — the gap is annotated per-anchor; the §6.6
    narrative stands on the M6 numbers alone."""
    per_row = pd.read_csv(TABLES / "path_coverage_perp_per_row.csv")
    per_row["fri_ts"] = pd.to_datetime(per_row["fri_ts"]).dt.date

    panel = _load_panel()
    panel, bands_m6, scale_col = _serve_m6_bands(panel, taus=TAUS)
    keys = panel[["symbol", "fri_ts"]].reset_index().rename(columns={"index": "panel_idx"})

    # Build M6 bands for the per-row keyspace.
    m6_rows = []
    for tau, bands_tau in bands_m6.items():
        merged = per_row[np.isclose(per_row["tau"], tau)].merge(
            keys, on=["symbol", "fri_ts"], how="inner",
        )
        idx = merged["panel_idx"].to_numpy()
        m6_rows.append(pd.DataFrame({
            "symbol": merged["symbol"].to_numpy(),
            "fri_ts": merged["fri_ts"].to_numpy(),
            "tau": tau,
            "m6_lo": bands_tau["lower"].to_numpy()[idx],
            "m6_hi": bands_tau["upper"].to_numpy()[idx],
            "perp_path_lo": merged["perp_path_lo"].to_numpy(),
            "perp_path_hi": merged["perp_path_hi"].to_numpy(),
            "mon_open": merged["mon_open"].to_numpy(),
        }))
    m6 = pd.concat(m6_rows, ignore_index=True)
    m6["m6_path_in_band"] = (
        (m6["perp_path_lo"] >= m6["m6_lo"]) & (m6["perp_path_hi"] <= m6["m6_hi"])
    )
    m6["m6_endpoint_in_band"] = (
        (m6["mon_open"] >= m6["m6_lo"]) & (m6["mon_open"] <= m6["m6_hi"])
    )

    # Aggregate by τ.
    agg = (m6.groupby("tau", as_index=False)
              .agg(n=("symbol", "size"),
                   endpoint_cov=("m6_endpoint_in_band", "mean"),
                   path_cov=("m6_path_in_band", "mean")))
    agg["gap_pp"] = (agg["endpoint_cov"] - agg["path_cov"]) * 100

    fig, ax = plt.subplots(figsize=(6.0, 4.0))

    pp = agg.sort_values("tau").copy()
    ax.plot([0.6, 1.0], [0.6, 1.0], lw=0.6, ls="--",
            color=OI["grey"], label=r"$45^\circ$")
    ax.plot(pp["tau"], pp["endpoint_cov"], color=OI["blue"], marker="o",
            markersize=8, lw=1.6, label=r"endpoint coverage")
    ax.plot(pp["tau"], pp["path_cov"], color=OI["vermilion"], marker="s",
            markersize=7, lw=1.4, label=r"path coverage")
    ax.fill_between(pp["tau"], pp["path_cov"], pp["endpoint_cov"],
                    color=OI["vermilion"], alpha=0.12, zorder=0)
    for _, row in pp.iterrows():
        ax.annotate(rf"${row['gap_pp']:.1f}\,\mathrm{{pp}}$",
                    ((row["tau"] + 0.005),
                     (row["endpoint_cov"] + row["path_cov"]) / 2),
                    fontsize=8.5, color=OI["vermilion"], ha="left",
                    va="center")
    ax.set_xlim(0.65, 1.02)
    ax.set_ylim(0.30, 1.05)
    ax.set_xlabel(r"claimed coverage $\tau$")
    ax.set_ylabel(r"realised coverage on perp reference")
    # No in-artwork title — the §6.5 caption carries sample size and dates
    # (revision_critique A5: keep section refs and codenames out of artwork).
    ax.legend(loc="lower right", framealpha=0.9, fontsize=9.0)

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig6_path_coverage.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig6_path_coverage.pdf'}")


# ================================================================== Fig 7b


def fig7b_oos_ablation() -> None:
    """Real-data §7.2 per-symbol ablation in the CQR-Fig.4 idiom.

    For each split anchor in {2021,2022,2023,2024}-01-01 and each method
    in {constant-buffer (oracle-fit), unweighted Mondrian (M5), deployed
    σ̂-standardised (M6)}, fit/serve at τ=0.95 and tabulate per-symbol
    (mean half-width bps, realised coverage). The figure is a two-panel
    horizontal boxplot — one row per method, distribution = per-(symbol,
    split-anchor) cells. Visual idiom: Romano et al. (2019), Fig. 4.

    The single deployed-anchor row of §7.2 becomes a 40-cell distribution
    that reveals the M6 σ̂-standardisation contribution: per-symbol
    coverage tightens onto τ=0.95, while M5 is dispersed and CB-matched
    is uniformly off-target by symbol class."""
    from datetime import date as _date

    from soothsayer.backtest.calibration import (
        compute_score,
        fit_split_conformal_forecaster,
        prep_panel_for_forecaster,
        serve_bands_forecaster,
    )

    panel0 = _load_panel()
    panel0["fri_ts"] = pd.to_datetime(panel0["fri_ts"]).dt.date

    SPLIT_ANCHORS = [
        _date(2021, 1, 1), _date(2022, 1, 1),
        _date(2023, 1, 1), _date(2024, 1, 1),
    ]
    TAU = 0.95

    # Build the LWC-prepped panel once (it adds σ̂ EWMA HL=8 + lwc score).
    # The same row set is used for every method, so M5 and CB-matched are
    # evaluated on identical (symbol × weekend) cells as M6.
    panel_lwc = prep_panel_for_forecaster(panel0, "lwc")
    panel_lwc = panel_lwc.dropna(subset=["score"]).reset_index(drop=True)

    method_rows: list[dict] = []

    for split_dt in SPLIT_ANCHORS:
        # ---- M6 (LWC, deployed σ̂-standardised)
        qt6, cb6, _ = fit_split_conformal_forecaster(
            panel_lwc, split_dt, "lwc", cell_col="regime_pub", taus=(TAU,),
        )
        oos = panel_lwc[panel_lwc["fri_ts"] >= split_dt].copy()
        b6 = serve_bands_forecaster(oos, qt6, cb6, "lwc",
                                    cell_col="regime_pub", taus=(TAU,))
        method_rows.extend(_per_symbol_metrics_at(
            oos, b6[TAU], split_dt, "M6 (deployed " r"$\hat\sigma_s$)",
            method_id="m6",
        ))

        # ---- M5 (unweighted Mondrian) on the same row set.
        panel_m5 = panel_lwc.copy()
        panel_m5["score"] = compute_score(panel_m5)
        qt5, cb5, _ = fit_split_conformal_forecaster(
            panel_m5, split_dt, "m5", cell_col="regime_pub", taus=(TAU,),
        )
        oos5 = panel_m5[panel_m5["fri_ts"] >= split_dt].copy()
        b5 = serve_bands_forecaster(oos5, qt5, cb5, "m5",
                                    cell_col="regime_pub", taus=(TAU,))
        method_rows.extend(_per_symbol_metrics_at(
            oos5, b5[TAU], split_dt, "M5 (unweighted Mondrian)",
            method_id="m5",
        ))

        # ---- CB matched (oracle-fit on the OOS slice).
        oos_cb = panel_lwc[panel_lwc["fri_ts"] >= split_dt].copy()
        rel_resid = (
            (oos_cb["mon_open"].to_numpy()
             - oos_cb["fri_close"].to_numpy())
            / oos_cb["fri_close"].to_numpy()
        )
        b_matched = float(np.quantile(np.abs(rel_resid), TAU))
        lower_cb = oos_cb["fri_close"].to_numpy() * (1.0 - b_matched)
        upper_cb = oos_cb["fri_close"].to_numpy() * (1.0 + b_matched)
        bcb = pd.DataFrame(
            {"lower": lower_cb, "upper": upper_cb}, index=oos_cb.index,
        )
        method_rows.extend(_per_symbol_metrics_at(
            oos_cb, bcb, split_dt, "CB matched (oracle-fit)",
            method_id="cb_matched",
        ))

    cells = pd.DataFrame(method_rows)
    out_csv = TABLES / "paper1_fig7b_per_symbol_ablation.csv"
    cells.to_csv(out_csv, index=False)
    print(f"  wrote {out_csv}  ({len(cells):,} rows)")

    # ---- Render: 3 method rows × 2 panels.
    method_order = [
        ("CB matched (oracle-fit)",          "cb_matched", OI["grey"],     False),
        ("M5 (unweighted Mondrian)",         "m5",         OI["vermilion"], False),
        (r"M6 (deployed $\hat\sigma_s$)",    "m6",         OI["blue"],     True),
    ]

    hw_data, cov_data, labels, colors, bolds = [], [], [], [], []
    for label, mid, color, bold in method_order:
        c = cells[cells["method_id"] == mid]
        hw_data.append(c["hw_bps"].to_numpy())
        cov_data.append(c["coverage"].to_numpy())
        labels.append(label); colors.append(color); bolds.append(bold)

    fig, (ax_hw, ax_cov) = plt.subplots(
        1, 2, figsize=(10.4, 3.6),
        gridspec_kw={"width_ratios": [1.0, 1.0], "wspace": 0.06},
        sharey=True,
    )
    n_rows = len(method_order)
    positions = list(range(n_rows, 0, -1))

    def _draw(ax, data):
        bp = ax.boxplot(
            data, positions=positions, widths=0.55, vert=False,
            patch_artist=True, showfliers=True,
            flierprops={"marker": "o", "markersize": 3,
                        "markerfacecolor": "#777777",
                        "markeredgecolor": "none", "alpha": 0.45},
            medianprops={"color": "#000000", "linewidth": 1.4},
            whiskerprops={"color": "#000000", "linewidth": 0.7},
            capprops={"color": "#000000", "linewidth": 0.7},
            boxprops={"linewidth": 0.6, "edgecolor": "#000000"},
        )
        for patch, c, bold in zip(bp["boxes"], colors, bolds):
            patch.set_facecolor(c)
            patch.set_alpha(0.85 if bold else 0.45)

    _draw(ax_hw,  hw_data)
    _draw(ax_cov, cov_data)

    hw_min = min((x.min() for x in hw_data if len(x)), default=0.0)
    hw_max = max((x.max() for x in hw_data if len(x)), default=1.0)
    pad = 0.18 * (hw_max - hw_min)
    ax_hw.set_xlim(hw_min - 1.4 * pad, hw_max + 0.05 * pad)
    ax_cov.set_xlim(0.78, 1.005)

    def _annotate_medians(ax, data, fmt, x_frac):
        xmin, xmax = ax.get_xlim()
        x = xmin + x_frac * (xmax - xmin)
        for vals, y in zip(data, positions):
            if len(vals) == 0:
                continue
            med = float(np.median(vals))
            ax.annotate(fmt.format(med), xy=(x, y),
                        ha="left", va="center", fontsize=8.5,
                        bbox=dict(boxstyle="round,pad=0.18,rounding_size=0.4",
                                  facecolor="white", edgecolor="#777777",
                                  linewidth=0.5))

    _annotate_medians(ax_hw,  hw_data,  "{:.0f}", x_frac=0.005)
    _annotate_medians(ax_cov, cov_data, "{:.3f}", x_frac=0.005)

    ax_cov.axvline(0.95, linestyle=":", color="#000000",
                   linewidth=0.8, alpha=0.7, zorder=0)
    ax_cov.text(0.95, 0.55, r"nominal $\tau = 0.95$",
                ha="center", va="bottom", fontsize=8.0, color="#000000",
                bbox=dict(boxstyle="round,pad=0.2",
                          facecolor="white", edgecolor="none", alpha=0.85))

    for ax, title in [(ax_hw, "Mean half-width (bps)"),
                      (ax_cov, "Realised coverage")]:
        ax.set_title(title, fontsize=10.0,
                     bbox=dict(boxstyle="square,pad=0.4",
                               facecolor="#DDDDDD", edgecolor="none"),
                     pad=6)
        ax.grid(axis="x", color="#CCCCCC", linewidth=0.4, alpha=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", left=False)

    ax_hw.set_yticks(positions)
    ax_hw.set_yticklabels(labels)
    for tick, bold in zip(ax_hw.get_yticklabels(), bolds):
        tick.set_fontweight("bold" if bold else "normal")
        tick.set_fontsize(9.5)
    ax_hw.set_ylim(0.4, n_rows + 0.6)

    fig.suptitle(
        r"OOS per-symbol ablation at $\tau = 0.95$ — "
        "10 symbols × 4 split anchors {2021, 2022, 2023, 2024}",
        fontsize=10.5, y=0.985,
    )
    fig.text(
        0.5, 0.012,
        "Box = per-(symbol, split-anchor) cell distribution, N = 40 per row. "
        "Visual idiom: Romano et al. (2019), Fig. 4.",
        ha="center", va="bottom", fontsize=8.0, color="#555555",
    )
    fig.subplots_adjust(left=0.20, right=0.985, top=0.88, bottom=0.13,
                        wspace=0.06)

    out_path = FIG_DIR / "fig7b_oos_ablation.pdf"
    fig.savefig(out_path)
    fig.savefig(out_path.with_suffix(".png"), dpi=150)
    plt.close(fig)
    print(f"  wrote {out_path}")


def _per_symbol_metrics_at(
    oos: pd.DataFrame,
    band: pd.DataFrame,
    split_dt,
    method_label: str,
    method_id: str,
) -> list[dict]:
    """Per-symbol (coverage, mean half-width bps) on an OOS slice."""
    rows = []
    for sym, idx in oos.groupby("symbol").groups.items():
        sub = oos.loc[idx]
        b = band.loc[idx]
        inside = (sub["mon_open"] >= b["lower"]) & (sub["mon_open"] <= b["upper"])
        cov = float(inside.mean())
        hw_bps = float(
            ((b["upper"].to_numpy() - b["lower"].to_numpy())
             / 2.0
             / sub["fri_close"].to_numpy()
             ).mean() * 1.0e4
        )
        rows.append({
            "symbol": sym,
            "split_anchor": split_dt.isoformat(),
            "method_label": method_label,
            "method_id": method_id,
            "n": int(len(sub)),
            "coverage": cov,
            "hw_bps": hw_bps,
        })
    return rows


# =================================================================== Fig 9


def fig9_boj_anatomy() -> None:
    """Anatomy of a served band on the worst observed weekend (§6.3.5).

    The 2024-08-02 → 2024-08-05 BoJ yen-carry-unwind weekend: for each of
    the 10 symbols, the deployed nested bands at τ ∈ {0.85, 0.95, 0.99}
    (artefact schedules, byte-aligned with what a consumer read), the
    factor-adjusted point, and the realised Monday open — all in
    weekend-return space relative to Friday close. Shows in one image
    (i) what the product is, (ii) per-symbol σ̂ width differentiation
    (MSTR's τ=0.85 half-width is ~9× SPY's), and (iii) the cross-
    sectional common-mode joint breach no per-symbol band can absorb
    (revision_critique ADD-1).

    Bands are computed FROM THE DEPLOYED ARTEFACT (parquet rows +
    sidecar schedules), not refit — byte-aligned with what a
    consumer read. This is what exposed the stale K=26-era numbers
    in the old §6.3.5 table (TSLA breaches at τ=0.95 under the
    deployed EWMA σ̂; k_w = 9, consistent with §6.3.4's max k_w)."""
    ANATOMY_TAUS = (0.85, 0.95, 0.99)

    art = pd.read_parquet(DATA_PROCESSED / "lwc_artefact_v1.parquet")
    art = art[pd.to_datetime(art["fri_ts"]).dt.date.astype(str)
              == "2024-08-02"]
    if art.empty:
        print("  WARN: 2024-08-02 weekend not in artefact — skipping fig9.")
        return
    side = json.loads((DATA_PROCESSED / "lwc_artefact_v1.json").read_text())
    qt, cbump = side["regime_quantile_table"], side["c_bump_schedule"]

    panel = _load_panel()
    mon = (panel[panel["fri_ts"].astype(str) == "2024-08-02"]
           .set_index("symbol")["mon_open"])

    rows = []
    for _, r in art.iterrows():
        fri = float(r["fri_close"])
        point_pct = (float(r["point"]) / fri - 1.0) * 100.0
        entry = {
            "symbol": r["symbol"],
            "realised_pct": (float(mon[r["symbol"]]) / fri - 1.0) * 100.0,
            "point_pct": point_pct,
        }
        for tau in ANATOMY_TAUS:
            hw_pct = (float(cbump[str(tau)])
                      * float(qt[r["regime_pub"]][str(tau)])
                      * float(r["sigma_hat_sym_pre_fri"]) * 100.0)
            entry[f"lo_{tau}"] = point_pct - hw_pct
            entry[f"hi_{tau}"] = point_pct + hw_pct
        rows.append(entry)
    df = pd.DataFrame(rows).sort_values("realised_pct",
                                        ascending=True).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    y = np.arange(len(df))

    # Nested bands: widest τ lightest, drawn first.
    BAND_STYLE = {
        0.99: dict(color=OI["blue"], alpha=0.18, lw=9),
        0.95: dict(color=OI["blue"], alpha=0.40, lw=6),
        0.85: dict(color=OI["blue"], alpha=0.80, lw=3),
    }
    for tau in (0.99, 0.95, 0.85):  # widest first, 0.85 on top
        st = BAND_STYLE[tau]
        ax.hlines(y, df[f"lo_{tau}"], df[f"hi_{tau}"],
                  color=st["color"], alpha=st["alpha"],
                  linewidth=st["lw"], zorder=2)

    # Factor-adjusted point (band centre).
    ax.scatter(df["point_pct"], y, marker="|", s=120, color="black",
               linewidth=1.2, zorder=4)

    # Realised Monday open — breach state judged against the τ=0.95 band.
    breach95 = ((df["realised_pct"] < df["lo_0.95"])
                | (df["realised_pct"] > df["hi_0.95"]))
    ax.scatter(df.loc[breach95, "realised_pct"], y[breach95.to_numpy()],
               marker="o", s=55, color=OI["vermilion"],
               edgecolor="black", linewidth=0.5, zorder=5)
    ax.scatter(df.loc[~breach95, "realised_pct"], y[(~breach95).to_numpy()],
               marker="o", s=55, color="white",
               edgecolor=OI["blue"], linewidth=1.2, zorder=5)

    # Per-symbol realised-return annotation: breached dots are far left
    # of their bands (label to the left); inside dots sit within the
    # band (label above, so it doesn't hide behind the band fill).
    for yi, (_, r) in zip(y, df.iterrows()):
        if breach95.loc[_]:
            kw = dict(xytext=(-6, -1), ha="right", va="center",
                      color=OI["vermilion"])
        else:
            kw = dict(xytext=(0, 8), ha="center", va="bottom",
                      color=OI["grey"])
        ax.annotate(rf"${r['realised_pct']:+.1f}\%$",
                    (r["realised_pct"], yi),
                    textcoords="offset points", fontsize=7.5, **kw)

    ax.axvline(0.0, color=OI["grey"], lw=0.6, ls="--", alpha=0.6, zorder=1)
    ax.set_xlim(df["realised_pct"].min() - 4.0,
                df[[c for c in df.columns if c.startswith("hi_")]]
                .to_numpy().max() + 1.5)
    ax.set_yticks(y)
    ax.set_yticklabels(df["symbol"], fontsize=9)
    ax.set_xlabel(r"weekend return, Fri 16:00 ET close $\to$ Mon 09:30 ET open (%)")
    ax.set_ylim(-0.6, len(df) - 0.4)

    # Legend.
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=OI["blue"], alpha=0.18, lw=9,
               label=r"served band, $\tau = 0.99$"),
        Line2D([0], [0], color=OI["blue"], alpha=0.40, lw=6,
               label=r"served band, $\tau = 0.95$"),
        Line2D([0], [0], color=OI["blue"], alpha=0.80, lw=3,
               label=r"served band, $\tau = 0.85$"),
        Line2D([0], [0], marker="|", color="black", lw=0, markersize=10,
               markeredgewidth=1.2, label=r"factor-adjusted point $\hat p$"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=OI["vermilion"],
               markeredgecolor="black", markersize=7,
               label=r"realised Mon open (breach at $\tau = 0.95$)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="white",
               markeredgecolor=OI["blue"], markersize=7,
               label=r"realised Mon open (inside)"),
    ]
    # Legend below the axes — the data fills the full plot area, so any
    # in-axes placement occludes a band or a dot.
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.14), ncol=3, frameon=False,
              fontsize=7.5, columnspacing=1.2, handletextpad=0.6)

    plt.tight_layout()
    out_path = FIG_DIR / "fig9_boj_anatomy.pdf"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  wrote {out_path}")


# =================================================================== Fig 7


def fig7_simulation_summary() -> None:
    """Copy `reports/figures/simulation_summary.pdf` (produced by
    `scripts/run_simulation_study.py`) into the paper figures directory.

    The Phase-3 simulation figure is generated by the simulation runner
    in the global figures location; the paper expects it under
    `reports/paper1_coverage_inversion/figures/`. We copy rather than
    symlink so the build is robust to figure-dir reorgs."""
    src = SIM_FIG / "simulation_summary.pdf"
    dst = FIG_DIR / "simulation_summary.pdf"
    if not src.exists():
        print(f"  WARN: {src} not found — run scripts/run_simulation_study.py first.")
        return
    shutil.copyfile(src, dst)
    print(f"  copied {src} → {dst}")


# =================================================================== main


def main() -> None:
    setup_rc()
    print(f"Building paper 1 figures into {FIG_DIR} …", flush=True)
    fig0_weekend_returns()
    fig1_pipeline()
    fig2_calibration()
    fig3_stability()
    fig4_per_symbol()
    fig5_pareto()
    fig6_path_coverage()
    fig7_simulation_summary()
    fig7b_oos_ablation()
    fig9_boj_anatomy()
    print("done.")


if __name__ == "__main__":
    main()
