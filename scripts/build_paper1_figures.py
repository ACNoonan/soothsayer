"""
Build all seven Paper 1 figures.

Outputs PDFs into `reports/paper1_coverage_inversion/figures/`:

  fig1_pipeline.pdf          M6 architecture / data-flow block diagram
  fig2_calibration.pdf       Calibration curve: M6 vs M5 vs Soothsayer-v0
                             vs constant-buffer baseline
  fig3_stability.pdf         M6 walk-forward + split-date sensitivity
  fig4_per_symbol.pdf        M6 per-symbol violation rate vs nominal at τ=0.95
                             (single panel; binomial 95% CI shaded)
  fig5_pareto.pdf            Coverage vs half-width Pareto across methods
                             (M6 / Soothsayer-v0 / GARCH / Pyth / Chainlink)
  fig6_path_coverage.pdf     M6 endpoint vs path coverage across τ
                             (single panel; perp reference, n = 118)
  simulation_summary.pdf     Phase-3 4-DGP simulation study (copied from
                             reports/figures/ produced by run_simulation_study.py)

The paper's M-series naming maps to internal codenames as:
  Soothsayer-v0 = the 2025 deployed hybrid Oracle (finite-sample cap at 0.972;
                  appears as the legacy comparator in fig 2 / fig 5)
  M5            = Mondrian split-conformal by regime; no per-symbol σ̂
                  standardisation (the un-LWC predecessor to the deployed M6)
  M6            = Locally-Weighted Conformal under EWMA HL=8 σ̂ (deployed)

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
    compute_score,
    compute_score_lwc,
    fit_c_bump_schedule,
    serve_bands,
    serve_bands_lwc,
    train_lwc_quantile_table,
    train_quantile_table,
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
        (1,  44, 17.5, 9, r"$p_t^{\mathrm{Fri}}$" "\n" r"close",                          "#FDF6E3"),
        (20, 44, 18.5, 9, r"factor return" "\n" r"$\rho(s,t)\!\to\!r_t^F$",               "#FDF6E3"),
        (40, 44, 18.5, 9, r"per-symbol scale" "\n" r"$\hat\sigma_s(t)$ EWMA HL=8",        "#E8F4E8"),
        (60, 44, 17.5, 9, r"regime label" "\n" r"$r\!\in\!\{\mathrm{nrm,lw,hv}\}$",        "#FDF6E3"),
        (79, 44, 18.5, 9, r"consumer $\tau$" "\n" r"$\in[0.68,0.99]$",                    "#FDF6E3"),
    ]
    for (x, y, w, h, t, fc) in inputs:
        box(x, y, w, h, t, fc)

    # Middle: 5-line lookup, shaded box.
    p = FancyBboxPatch(
        (4, 14), 92, 24, boxstyle="round,pad=0.4,rounding_size=2.0",
        linewidth=1.0, facecolor="#E8F1FA", edgecolor=OI["blue"],
    )
    ax.add_patch(p)
    ax.text(50, 35.5, "Five-line serving lookup (M6 / LWC)", ha="center",
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

    # Bottom: receipt with M6 diagnostic quartet.
    box(2, 1, 96, 9,
        r"$\mathrm{PricePoint}\{\,\mathrm{symbol},\, \mathrm{as\_of},\, \tau,\, \delta(\tau){=}0,\, \tau,\, \hat p_t,\, L_t,\, U_t,\, r,\, \mathrm{sharpness\,bps},\, \mathrm{diagnostics}\{c,\, q_{\mathrm{eff}},\, q_r,\, \hat\sigma_s\}\,\}$",
        "#F5F5F5", ec=OI["grey"], fontsize=7.2)
    ax.text(50, 11.2, "Per-read receipt (P1: auditability) — 16 deployment scalars + per-symbol $\\hat\\sigma_s(t)$",
            ha="center", fontsize=8.5, color=OI["grey"], fontweight="bold")

    # Arrows down from inputs into shaded box.
    for (x, _, w, _, _, _) in inputs:
        arrow(x + w / 2, 44, x + w / 2, 38.5)
    arrow(50, 14, 50, 10.2)

    plt.savefig(FIG_DIR / "fig1_pipeline.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig1_pipeline.pdf'}")


# =================================================================== Fig 2


def fig2_calibration() -> None:
    """Calibration curve: M6 vs M5 vs Soothsayer-v0 vs constant-buffer baseline.

    All four lines plotted on the same 1,730-row 2023+ OOS slice. M6 from
    LWC under EWMA HL=8 σ̂ at a fine τ grid; M5 from Mondrian-by-regime
    at the same fine grid; Soothsayer-v0 from the v1b_bounds.parquet
    surface (its 12 native anchors); constant-buffer from F0_stale +
    Gaussian z·σ_20d at the fine grid."""
    panel = _load_panel()
    train_full = panel[panel["fri_ts"] < SPLIT_DATE]
    oos_full = (
        panel[panel["fri_ts"] >= SPLIT_DATE]
        .sort_values(["symbol", "fri_ts"])
        .reset_index(drop=True)
    )

    fine_taus = tuple(np.round(np.linspace(0.10, 0.99, 60), 4))

    # ---- M5 fine-grid serve.
    panel_m5 = panel.copy()
    panel_m5["score"] = compute_score(panel_m5)
    train_m5 = panel_m5[panel_m5["fri_ts"] < SPLIT_DATE].dropna(subset=["score"])
    oos_m5 = (panel_m5[panel_m5["fri_ts"] >= SPLIT_DATE]
              .dropna(subset=["score"])
              .sort_values(["symbol", "fri_ts"])
              .reset_index(drop=True))
    qt_m5 = train_quantile_table(train_m5, cell_col="regime_pub", taus=fine_taus)
    cb_m5 = fit_c_bump_schedule(oos_m5, qt_m5, cell_col="regime_pub", taus=fine_taus)
    bounds_m5 = serve_bands(
        oos_m5, qt_m5, cb_m5, cell_col="regime_pub", taus=fine_taus,
        delta_shift_schedule={t: 0.0 for t in fine_taus},
    )
    m5_curve = []
    for tau in fine_taus:
        b = bounds_m5[tau]
        cov = ((oos_m5["mon_open"] >= b["lower"]) &
               (oos_m5["mon_open"] <= b["upper"])).mean()
        m5_curve.append((tau, float(cov)))
    m5 = pd.DataFrame(m5_curve, columns=["claimed", "realised"])

    # ---- M6 (LWC + EWMA HL=8) fine-grid serve.
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

    # ---- Soothsayer-v0 (legacy hybrid Oracle from v1b_bounds.parquet).
    bounds_v0 = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds_v0["fri_ts"] = pd.to_datetime(bounds_v0["fri_ts"]).dt.date
    bounds_v0 = bounds_v0[bounds_v0["fri_ts"] >= SPLIT_DATE]
    REGIME_FC = {"normal": "F1_emp_regime",
                 "long_weekend": "F1_emp_regime",
                 "high_vol": "F0_stale"}
    bounds_v0 = bounds_v0[bounds_v0.apply(
        lambda r: r["forecaster"] == REGIME_FC.get(r["regime_pub"]),
        axis=1
    )].copy()
    BUFFER_BY_TARGET = {0.68: 0.005, 0.85: 0.010, 0.95: 0.020, 0.99: 0.040}
    v0_rows = []
    for tau in sorted(bounds_v0["claimed"].unique()):
        sub = bounds_v0[np.isclose(bounds_v0["claimed"], tau)]
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
        v0_rows.append((float(tau), float(cov)))
    v0 = pd.DataFrame(v0_rows, columns=["claimed", "realised"])

    # ---- Constant-buffer baseline (F0_stale + Gaussian z·σ_20d).
    from scipy.stats import norm
    cb_oos = oos_full.dropna(subset=["fri_vol_20d"]).copy()
    cb_curve = []
    for tau in fine_taus:
        z = norm.ppf(0.5 + tau / 2.0)
        sig = cb_oos["fri_close"] * np.sqrt(2.0) * cb_oos["fri_vol_20d"]
        lower = cb_oos["fri_close"] - z * sig
        upper = cb_oos["fri_close"] + z * sig
        cov = ((cb_oos["mon_open"] >= lower) & (cb_oos["mon_open"] <= upper)).mean()
        cb_curve.append((tau, float(cov)))
    cbdf = pd.DataFrame(cb_curve, columns=["claimed", "realised"])

    # ---- Plot.
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    ax.plot([0, 1], [0, 1], lw=0.8, ls="--", color=OI["grey"],
            label=r"perfect calibration ($45^\circ$)")
    ax.plot(cbdf["claimed"], cbdf["realised"], color=OI["vermilion"], lw=1.2,
            label=r"constant-buffer baseline (F0\_stale, $\sigma_{20d}$)")
    ax.plot(v0["claimed"], v0["realised"], color=OI["orange"],
            marker="o", markersize=3.5, label=r"Soothsayer-v0 (legacy hybrid)")
    ax.plot(m5["claimed"], m5["realised"], color=OI["green"], lw=1.4,
            label=r"M5 (Mondrian, no $\hat\sigma$ standardisation)")
    ax.plot(m6["claimed"], m6["realised"], color=OI["blue"], lw=2.0,
            label=r"M6 (this paper)")

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
    ax_l.set_title("(a) 6-split walk-forward (M6, $\\delta\\equiv 0$)",
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
        lw=1.0, capsize=3.0, label=r"$\tau\!=\!0.95$ realised (M6)",
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
    ax_r.set_title("(b) split-date sensitivity (M6)",
                   fontsize=10, fontweight="bold")
    ax_r.legend(loc="lower right", framealpha=0.9, fontsize=7.5)

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_stability.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig3_stability.pdf'}")


# =================================================================== Fig 4


def fig4_per_symbol() -> None:
    """Single-panel M6 per-symbol violation rate at τ=0.95.

    x-axis: 10 symbols ordered by realised PIT variance σ̂²_z (low → high).
    y-axis: per-symbol violation rate at τ=0.95, with binomial 95% CI band
    around the nominal 0.05 rate shaded. All 10 symbols sit inside the band —
    the §6.4.1 headline. The single (symbol × τ) grid outlier (TSLA at
    τ=0.85, p=0.044) is annotated separately, below the main panel."""
    df = pd.read_csv(TABLES / "m6_lwc_robustness_per_symbol.csv")
    df = df.sort_values("var_z").reset_index(drop=True)

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
    y_max = max(float(df["viol_rate_0.95"].max()) * 1.4, hi_rate * 1.3, 0.10)
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
               markersize=8, label=r"M6 violation rate"),
    ]
    ax.legend(handles=legend_handles, loc="upper right",
              framealpha=0.9, fontsize=8.0)

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig4_per_symbol.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig4_per_symbol.pdf'}")


# =================================================================== Fig 5


def fig5_pareto() -> None:
    """Realised coverage vs half-width across methods at four served τ.

    M6 from m6_pooled_oos.csv (forecaster=lwc, stratification=pooled).
    Soothsayer-v0 from incumbent_oracle_unified_summary.csv (the legacy
    deployed hybrid). GARCH-t from m6_lwc_robustness_garch_t_baseline.csv
    (the practitioner-standard parametric baseline; Phase 7.3).
    Pyth + Chainlink from incumbent_oracle_unified_summary.csv at the
    consumer-supplied wrap multiplier."""
    inc = pd.read_csv(TABLES / "incumbent_oracle_unified_summary.csv")
    pooled = pd.read_csv(TABLES / "m6_pooled_oos.csv")

    # Prefer GARCH-t (Phase 7.3, practitioner standard) if available;
    # fall back to GARCH-Gaussian for backward compatibility.
    garch_t_path = TABLES / "m6_lwc_robustness_garch_t_baseline.csv"
    if garch_t_path.exists():
        garch = pd.read_csv(garch_t_path)
        # The Phase 7.3 runner emits a `method` column literal "GARCH(1,1)";
        # the t-vs-N split is on `garch_dist` if present.
        if "garch_dist" in garch.columns:
            garch = garch[garch["garch_dist"] == "t"]
        else:
            garch = garch[garch["method"] == "GARCH(1,1)"]
        garch_label = r"GARCH(1,1)-$t$ baseline"
    else:
        garch = pd.read_csv(TABLES / "m6_lwc_robustness_garch_baseline.csv")
        garch = garch[garch["method"] == "GARCH(1,1)"]
        garch_label = r"GARCH(1,1)-Gaussian baseline"

    fig, ax = plt.subplots(figsize=(6.0, 4.2))

    # ---- M6 (this paper) — LWC pooled OOS at four anchors.
    m6 = pooled[(pooled["forecaster"] == "lwc")
                & (pooled["stratification"] == "pooled")].sort_values("tau")
    ax.plot(m6["realised"], m6["half_width_bps"],
            color=OI["blue"], marker="*", markersize=11,
            lw=1.6, label=r"M6 (this paper)", zorder=5)
    for _, row in m6.iterrows():
        ax.annotate(rf"$\tau\!=\!{row['tau']:.2f}$",
                    (row["realised"], row["half_width_bps"]),
                    xytext=(8, 4), textcoords="offset points",
                    fontsize=7.5, color=OI["blue"])

    # ---- Soothsayer-v0 (legacy hybrid Oracle).
    v0 = inc[inc["oracle"] == "soothsayer_v1_deployed"].sort_values("tau")
    ax.plot(v0["realized_at_tau_band"], v0["halfwidth_bps_at_tau"],
            color=OI["orange"], marker="o", markersize=6,
            lw=1.2, label=r"Soothsayer-v0 (legacy hybrid)", zorder=4)

    # ---- GARCH baseline.
    ax.plot(garch["realised"], garch["half_width_bps"],
            color=OI["vermilion"], marker="s", markersize=5,
            lw=1.0, label=garch_label, zorder=4)

    # ---- Pyth (consumer wrap at smallest k achieving claimed coverage).
    pyth = inc[inc["oracle"] == "pyth_smallest_k"].sort_values("tau")
    ax.plot(pyth["realized_at_tau_band"], pyth["halfwidth_bps_at_tau"],
            color=OI["green"], marker="D", markersize=5,
            lw=0.8, label=r"Pyth $\pm k\!\cdot\!\mathrm{conf}$ ($n=265$)", zorder=3)

    # ---- Chainlink Streams (manual mid ± k% wrap).
    cl = inc[inc["oracle"] == "chainlink_streams_smallest_k_pct"].sort_values("tau")
    ax.plot(cl["realized_at_tau_band"], cl["halfwidth_bps_at_tau"],
            color=OI["purple"], marker="X", markersize=5,
            lw=0.8, label=r"Chainlink Streams mid$\,\pm\,k\%$ ($n=87$)", zorder=3)

    # ---- Vertical lines at four claimed τ.
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
            markersize=8, lw=1.6, label=r"M6 endpoint coverage")
    ax.plot(pp["tau"], pp["path_cov"], color=OI["vermilion"], marker="s",
            markersize=7, lw=1.4, label=r"M6 path coverage")
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
    n_pooled = int(pp["n"].iloc[0])
    ax.set_title(
        rf"M6 endpoint vs path coverage across $\tau$ ($n={n_pooled}$ symbol-weekends, 2025-12 $\to$ 2026-04)",
        fontsize=9.5, fontweight="bold",
    )
    ax.legend(loc="lower right", framealpha=0.9, fontsize=9.0)

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig6_path_coverage.pdf")
    plt.close(fig)
    print(f"  wrote {FIG_DIR / 'fig6_path_coverage.pdf'}")


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
    fig1_pipeline()
    fig2_calibration()
    fig3_stability()
    fig4_per_symbol()
    fig5_pareto()
    fig6_path_coverage()
    fig7_simulation_summary()
    print("done.")


if __name__ == "__main__":
    main()
