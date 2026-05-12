"""
Phase 3 — synthetic-DGP simulation study for the M6 (LWC) promotion.

Validates the M5 vs M6 contrast on synthetic panels with known ground
truth — the standard reviewer hygiene check the paper currently lacks.
Four data-generating processes, 100 Monte Carlo replications each,
deterministic from seed=0.

Synthetic panel schema (mirrors `v1b_panel.parquet` minimally)
--------------------------------------------------------------
  symbol      = S00 ... S09
  fri_ts      = monotonic Friday dates 2010-01-01 + 7·t for t in 0..599
  mon_ts      = fri_ts + 3 days (the calibration code reads it but treats
                it as opaque metadata)
  fri_close   = 100.0  (units don't matter — score is relative)
  mon_open    = 100.0 · (1 + r_t)  where r_t is the simulated return
  factor_ret  = 0.0  (no factor adjustment; point estimator → fri_close)
  regime_pub  = depends on DGP

DGPs
----
A  homoskedastic  : r_{i,t} = σ_i · t_4 / sqrt(2),   σ_i ∈ linspace(0.005, 0.030, 10)
                    No regimes; regime_pub = "normal" everywhere.
                    Expected: M5 bimodal per-symbol Kupiec; M6 passes all 10.

B  regime-switching: same r as A but with a global vol multiplier m_t ∈ {0.5, 1.0, 2.0}
                    governed by a 3-state Markov chain. r_{i,t} = m_t · σ_i · t_4 / sqrt(2).
                    Stationary distribution π = [0.65, 0.25, 0.10] for {medium, low, high}.
                    Expected: M6 still passes per-symbol; M5 still bimodal.

C  non-stationary : σ_t drifts upward, σ_t = σ_i · (1 + 0.1·t/T).
                    Tests whether LWC's trailing-K σ̂ tracks slow drift.
                    Expected: M6 stays calibrated; M5 progressively under-covers.

D  exchangeability: structural break at t=400 (variance triples → std × √3).
                    Train on t<400, evaluate on t≥400.
                    Expected: both degrade (CP exchangeability assumption broken);
                    LWC's adaptive scale recovers faster.

Train/OOS split for all DGPs is t < 400 / t ≥ 400 (matches DGP D).

Outputs
-------
  reports/tables/sim_a_per_symbol_kupiec.csv
  reports/tables/sim_b_per_symbol_kupiec.csv
  reports/tables/sim_c_per_symbol_kupiec.csv
  reports/tables/sim_d_per_symbol_kupiec.csv
  reports/tables/sim_summary.csv                  (one row per DGP × τ × forecaster)
  reports/figures/simulation_summary.{pdf,png}    (4-panel box-plot at τ=0.95)

Run
---
  uv run python -u scripts/run_simulation_study.py

  The full battery (4 DGPs × 100 reps × 2 forecasters) takes ~90 s on
  this machine. The σ̂ inner loop dominates; the rest is fast.
"""

from __future__ import annotations

from datetime import date, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.config import REPORTS

N_SYMBOLS = 10
N_WEEKENDS = 600
SPLIT_T = 400  # train: t < 400; OOS: t >= 400
TAUS = DEFAULT_TAUS
N_REPS = 100
SEED = 0
BASE_DATE = date(2010, 1, 1)
SIGMA_GRID = np.linspace(0.005, 0.030, N_SYMBOLS)
SYMBOLS = [f"S{i:02d}" for i in range(N_SYMBOLS)]

# DGP A / B / C: SPLIT_DATE_SYNTH must be the Friday at index SPLIT_T.
SPLIT_DATE_SYNTH = BASE_DATE + timedelta(days=7 * SPLIT_T)

# Markov chain for DGP B.
# Stationary π = [0.65, 0.25, 0.10] for states {medium, low, high}.
# Constructed to satisfy detailed balance with diagonals
# [0.958, 0.85, 0.85] (state 0 dwell ~24 weeks; state 1/2 dwell ~6.7 weeks).
REGIME_LABELS = ("medium", "low", "high")
VOL_MULTIPLIER = {"medium": 1.0, "low": 0.5, "high": 2.0}
STATIONARY = np.array([0.65, 0.25, 0.10])
MARKOV_P = np.array([
    [0.95830, 0.03850, 0.00385 + 0.00050],   # +small to make rows sum to 1
    [0.10000, 0.85000, 0.05000],
    [0.02500, 0.12500, 0.85000],
])
# Renormalise rows (rounding correction).
MARKOV_P = MARKOV_P / MARKOV_P.sum(axis=1, keepdims=True)


# ============================================================== panel building


def _fri_ts_for(t: int) -> date:
    return BASE_DATE + timedelta(days=7 * t)


def _empty_panel(symbols: list[str], n_weekends: int) -> pd.DataFrame:
    """Skeleton panel: every (symbol, t) row, with fri_ts/mon_ts populated.
    Caller fills in `mon_open`, `regime_pub` per DGP."""
    rows = []
    for t in range(n_weekends):
        fri = _fri_ts_for(t)
        mon = fri + timedelta(days=3)
        for sym in symbols:
            rows.append({
                "symbol": sym,
                "fri_ts": fri,
                "mon_ts": mon,
                "fri_close": 100.0,
                "mon_open": np.nan,
                "factor_ret": 0.0,
                "regime_pub": "normal",
                "_t": t,
            })
    return pd.DataFrame(rows)


def _student_t_returns(rng: np.random.Generator,
                       sigmas: np.ndarray,
                       n_t: int,
                       df: float = 4.0) -> np.ndarray:
    """Returns matrix r[s, t] = sigmas[s, t] · t_4 / sqrt(2) so that
    std(r[s, ·]) = sigmas[s, t] (df=4 has variance 2, so sqrt(2) rescales).

    sigmas may be scalar-per-symbol (broadcast) or full per-(symbol, t)
    matrix shape (N_SYMBOLS, n_t)."""
    raw = rng.standard_t(df, size=(N_SYMBOLS, n_t))
    sigmas_arr = np.broadcast_to(sigmas, (N_SYMBOLS, n_t))
    return sigmas_arr * raw / np.sqrt(df / (df - 2.0))


def make_panel_dgp_a(rng: np.random.Generator) -> pd.DataFrame:
    """DGP A: homoskedastic Student-t df=4 per-symbol; no regimes."""
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    sigmas = SIGMA_GRID.reshape(-1, 1)  # (N_SYMBOLS, 1) → broadcast over t
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    # Map (symbol, t) returns into the long-form panel.
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]],
                                     int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = "normal"
    return panel.drop(columns=["_t"]).reset_index(drop=True)


def _simulate_markov_regime(rng: np.random.Generator,
                            n_t: int) -> np.ndarray:
    """One regime path of length n_t over states {0, 1, 2} with transition
    matrix MARKOV_P. Initial state drawn from stationary distribution."""
    state = int(rng.choice(3, p=STATIONARY))
    out = np.empty(n_t, dtype=int)
    for t in range(n_t):
        out[t] = state
        state = int(rng.choice(3, p=MARKOV_P[state]))
    return out


def make_panel_dgp_b(rng: np.random.Generator) -> pd.DataFrame:
    """DGP B: regime-switching global vol multiplier on top of A's per-symbol σ."""
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    regime_path = _simulate_markov_regime(rng, N_WEEKENDS)
    regime_labels = np.array([REGIME_LABELS[r] for r in regime_path])
    multiplier_path = np.array([VOL_MULTIPLIER[REGIME_LABELS[r]]
                                for r in regime_path])
    sigmas = SIGMA_GRID.reshape(-1, 1) * multiplier_path.reshape(1, -1)
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]],
                                     int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = panel["_t"].map(lambda t: regime_labels[int(t)])
    return panel.drop(columns=["_t"]).reset_index(drop=True)


def make_panel_dgp_c(rng: np.random.Generator) -> pd.DataFrame:
    """DGP C: non-stationary scale; σ_t = σ_i · (1 + 0.1 · t/T)."""
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    drift = 1.0 + 0.1 * np.arange(N_WEEKENDS) / N_WEEKENDS
    sigmas = SIGMA_GRID.reshape(-1, 1) * drift.reshape(1, -1)
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]],
                                     int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = "normal"
    return panel.drop(columns=["_t"]).reset_index(drop=True)


def make_panel_dgp_d(rng: np.random.Generator) -> pd.DataFrame:
    """DGP D: structural break at t=400 (variance triples → std × √3)."""
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    break_t = SPLIT_T
    multiplier = np.ones(N_WEEKENDS)
    multiplier[break_t:] = np.sqrt(3.0)
    sigmas = SIGMA_GRID.reshape(-1, 1) * multiplier.reshape(1, -1)
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]],
                                     int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = "normal"
    return panel.drop(columns=["_t"]).reset_index(drop=True)


DGP_BUILDERS = {
    "A": ("homoskedastic", make_panel_dgp_a),
    "B": ("regime-switching", make_panel_dgp_b),
    "C": ("non-stationary scale", make_panel_dgp_c),
    "D": ("exchangeability stress (break at t=400)", make_panel_dgp_d),
}


# ============================================================ per-rep evaluator


def _per_symbol_kupiec_at(panel_oos: pd.DataFrame,
                           bounds: dict[float, pd.DataFrame],
                           tau: float) -> pd.DataFrame:
    rows = []
    for sym, idx in panel_oos.groupby("symbol").groups.items():
        sub = panel_oos.loc[idx]
        b = bounds[tau].loc[idx]
        inside = (sub["mon_open"] >= b["lower"]) & (sub["mon_open"] <= b["upper"])
        v = (~inside).astype(int).to_numpy()
        lr, p = met._lr_kupiec(v, tau)
        hw_bps = (
            (b["upper"].to_numpy() - b["lower"].to_numpy())
            / 2.0
            / sub["fri_close"].to_numpy()
            * 1.0e4
        )
        rows.append({"symbol": sym, "tau": float(tau),
                     "n": int(len(sub)),
                     "viol_rate": float(v.mean()),
                     "kupiec_lr": float(lr),
                     "kupiec_p": float(p),
                     "mean_hw_bps": float(np.mean(hw_bps))})
    return pd.DataFrame(rows)


def evaluate_one_rep(panel: pd.DataFrame,
                     dgp: str,
                     rep: int) -> pd.DataFrame:
    """Run M5 + LWC fit/serve on a synthetic panel, return per-symbol
    Kupiec at every τ × forecaster."""
    rows = []
    for forecaster in ("m5", "lwc"):
        prepped = prep_panel_for_forecaster(panel, forecaster)
        prepped = prepped.dropna(subset=["score"]).reset_index(drop=True)
        try:
            qt, cb, info = fit_split_conformal_forecaster(
                prepped, SPLIT_DATE_SYNTH, forecaster, cell_col="regime_pub",
            )
        except Exception:
            # Edge: a regime cell can be empty in a rare bootstrap sample.
            # Skip this rep for that forecaster and tag it.
            continue
        oos = (prepped[prepped["fri_ts"] >= SPLIT_DATE_SYNTH]
               .dropna(subset=["score"])
               .reset_index(drop=True))
        if len(oos) == 0:
            continue
        bounds = serve_bands_forecaster(
            oos, qt, cb, forecaster,
            cell_col="regime_pub", taus=TAUS,
        )
        for tau in TAUS:
            kup = _per_symbol_kupiec_at(oos, bounds, tau)
            kup["forecaster"] = forecaster
            kup["dgp"] = dgp
            kup["rep"] = int(rep)
            rows.append(kup)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


# ===================================================================== runner


def run_dgp(dgp_key: str, parent_rng: np.random.Generator,
            n_reps: int = N_REPS) -> pd.DataFrame:
    """Run n_reps replications of one DGP. Returns long-form per-symbol
    Kupiec table tagged with `dgp`."""
    name, builder = DGP_BUILDERS[dgp_key]
    print(f"\n[DGP {dgp_key}] {name}  ({n_reps} reps)", flush=True)
    # Spawn n_reps independent child RNGs for bit-level reproducibility.
    child_rngs = parent_rng.spawn(n_reps)
    out_frames = []
    for rep, rng in enumerate(child_rngs):
        panel = builder(rng)
        df = evaluate_one_rep(panel, dgp_key, rep)
        if not df.empty:
            out_frames.append(df)
        if (rep + 1) % 25 == 0:
            print(f"  {rep + 1}/{n_reps} reps complete", flush=True)
    if not out_frames:
        return pd.DataFrame()
    return pd.concat(out_frames, ignore_index=True)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate a per-symbol-Kupiec table to one row per (dgp, τ, forecaster):
    pass-rate, mean violation rate, mean realised, Kupiec p mean/median."""
    rows = []
    for (dgp, tau, fc), g in df.groupby(["dgp", "tau", "forecaster"]):
        n_total = len(g)
        n_pass = int((g["kupiec_p"] >= 0.05).sum())
        rows.append({
            "dgp": dgp,
            "tau": float(tau),
            "forecaster": fc,
            "n_obs": n_total,  # 100 reps × 10 symbols = 1000
            "pass_rate_05": n_pass / n_total if n_total else float("nan"),
            "n_pass_05": n_pass,
            "n_total": n_total,
            "mean_realised": float(1 - g["viol_rate"].mean()),
            "mean_kupiec_p": float(g["kupiec_p"].mean()),
            "median_kupiec_p": float(g["kupiec_p"].median()),
        })
    return pd.DataFrame(rows).sort_values(["dgp", "tau", "forecaster"])


def render_figure(all_df: pd.DataFrame, out_dir) -> None:
    """Two-panel summary at tau = 0.95 in the CQR-Fig.4 idiom.

    Rows: 4 DGPs x 2 forecasters = 8 (A-M5, A-LWC, B-M5, ..., D-LWC).
    Each box is the distribution of per-(rep, symbol) cells (N = N_REPS x
    N_SYMBOLS = 1000 cells per box). Left panel: avg. half-width (bps).
    Right panel: avg. realised coverage. M5 rows are red; LWC (deployed
    sigma-hat-standardised) rows are blue and bold. A median pill is
    annotated to the left of each box. The right panel's dotted vertical
    line marks the nominal tau = 0.95.

    Visual idiom adapted from Romano-Patterson-Candes (2019), Fig. 4,
    extended to the per-symbol Mondrian setting.
    """
    sub = all_df[all_df["tau"] == 0.95].copy()
    sub["realised"] = 1.0 - sub["viol_rate"]
    if sub.empty or "mean_hw_bps" not in sub.columns:
        print("  WARN: render_figure has no half-width data; "
              "re-run after the schema upgrade.", flush=True)
        return

    # 8 rows: A-M5, A-LWC, B-M5, B-LWC, C-M5, C-LWC, D-M5, D-LWC.
    dgp_keys = ["A", "B", "C", "D"]
    forecasters = ("m5", "lwc")
    rows = [(d, fc) for d in dgp_keys for fc in forecasters]

    hw_data = []
    cov_data = []
    row_labels = []
    row_colors = []
    row_bold = []
    for (d, fc) in rows:
        cell = sub[(sub["dgp"] == d) & (sub["forecaster"] == fc)]
        hw_data.append(cell["mean_hw_bps"].to_numpy())
        cov_data.append(cell["realised"].to_numpy())
        label = f"{d} · {'M5' if fc == 'm5' else 'LWC'}"
        row_labels.append(label)
        row_colors.append("#D55E00" if fc == "m5" else "#0072B2")
        row_bold.append(fc == "lwc")

    fig, (ax_hw, ax_cov) = plt.subplots(
        1, 2, figsize=(11.0, 6.4),
        gridspec_kw={"width_ratios": [1.0, 1.0], "wspace": 0.06},
        sharey=True,
    )

    n_rows = len(rows)
    positions = list(range(n_rows, 0, -1))  # top-to-bottom (A-M5 at top)

    def _draw(ax, data, positions, colors, bold_flags):
        bp = ax.boxplot(
            data, positions=positions, widths=0.62, vert=False,
            patch_artist=True, showfliers=True,
            flierprops={"marker": "o", "markersize": 3,
                        "markerfacecolor": "#777777",
                        "markeredgecolor": "none", "alpha": 0.45},
            medianprops={"color": "#000000", "linewidth": 1.4},
            whiskerprops={"color": "#000000", "linewidth": 0.7},
            capprops={"color": "#000000", "linewidth": 0.7},
            boxprops={"linewidth": 0.6, "edgecolor": "#000000"},
        )
        for patch, c, bold in zip(bp["boxes"], colors, bold_flags):
            patch.set_facecolor(c)
            patch.set_alpha(0.85 if bold else 0.45)

    _draw(ax_hw,  hw_data,  positions, row_colors, row_bold)
    _draw(ax_cov, cov_data, positions, row_colors, row_bold)

    # Median pills on the left edge of each panel.
    def _annotate_medians(ax, data, positions, fmt, x_frac):
        xmin, xmax = ax.get_xlim()
        x = xmin + x_frac * (xmax - xmin)
        for vals, y in zip(data, positions):
            if len(vals) == 0:
                continue
            med = float(np.median(vals))
            ax.annotate(fmt.format(med), xy=(x, y), xycoords="data",
                        ha="left", va="center", fontsize=8.0,
                        bbox=dict(boxstyle="round,pad=0.18,rounding_size=0.4",
                                  facecolor="white", edgecolor="#777777",
                                  linewidth=0.5))

    # Cosmetic axis tweaks before annotating (so xlim is settled).
    # Half-width: pad on the left so pills don't overlap the boxes.
    hw_min = min((x.min() for x in hw_data if len(x)), default=0.0)
    hw_max = max((x.max() for x in hw_data if len(x)), default=1.0)
    pad = 0.15 * (hw_max - hw_min)
    ax_hw.set_xlim(hw_min - 1.4 * pad, hw_max + 0.05 * pad)

    # Coverage: fixed sensible range with nominal line.
    ax_cov.set_xlim(0.78, 1.005)

    _annotate_medians(ax_hw,  hw_data,  positions, "{:.0f}", x_frac=0.005)
    _annotate_medians(ax_cov, cov_data, positions, "{:.3f}", x_frac=0.005)

    # Coverage nominal line.
    ax_cov.axvline(0.95, linestyle=":", color="#000000",
                   linewidth=0.8, alpha=0.7, zorder=0)
    ax_cov.text(0.95, 0.55, r"nominal $\tau = 0.95$",
                ha="center", va="bottom", fontsize=8.0, color="#000000",
                bbox=dict(boxstyle="round,pad=0.2",
                          facecolor="white", edgecolor="none", alpha=0.85))

    # Panel titles in a band above each panel (CQR Fig.4 idiom).
    for ax, title in [(ax_hw, "Avg. Half-width (bps)"),
                      (ax_cov, "Avg. Coverage")]:
        ax.set_title(title, fontsize=10.5,
                     bbox=dict(boxstyle="square,pad=0.4",
                               facecolor="#DDDDDD", edgecolor="none"),
                     pad=8)
        ax.grid(axis="x", color="#CCCCCC", linewidth=0.4, alpha=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", left=False)

    # Y-axis labels: one per row, M6/LWC bolded.
    ax_hw.set_yticks(positions)
    ax_hw.set_yticklabels(row_labels)
    for tick, bold in zip(ax_hw.get_yticklabels(), row_bold):
        tick.set_fontweight("bold" if bold else "normal")
        tick.set_fontsize(9.5)

    ax_hw.set_ylim(0.4, n_rows + 0.6)

    # Faint horizontal separators between DGP groups (every 2 rows).
    for r in range(2, n_rows, 2):
        y = positions[r] + 0.5
        for ax in (ax_hw, ax_cov):
            ax.axhline(y, color="#BBBBBB", linewidth=0.4, alpha=0.5)

    fig.suptitle(
        "Phase 3 simulation study — half-width and coverage at "
        r"$\tau = 0.95$, 100 reps $\times$ 10 symbols per DGP",
        fontsize=11.0, y=0.99,
    )
    fig.text(
        0.5, 0.005,
        "Box = per-(rep, symbol) cell distribution, N = 1,000 per row. "
        "M5 rows = unweighted Mondrian; LWC rows (bold) = deployed "
        r"$\hat\sigma_s$-standardised. Visual idiom: Romano et al. (2019), Fig. 4.",
        ha="center", va="bottom", fontsize=8.0, color="#555555",
    )

    fig.subplots_adjust(left=0.10, right=0.985, top=0.92, bottom=0.085,
                        wspace=0.06)

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "simulation_summary.pdf"
    png_path = out_dir / "simulation_summary.png"
    fig.savefig(pdf_path)
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    print(f"\nWrote {pdf_path}", flush=True)
    print(f"Wrote {png_path}", flush=True)


def main() -> None:
    parent_rng = np.random.default_rng(SEED)
    print(f"Seed: {SEED}  |  N_REPS per DGP: {N_REPS}  |  "
          f"split: t<{SPLIT_T} train, t≥{SPLIT_T} OOS", flush=True)

    # Spawn 4 parent generators, one per DGP — independent streams so adding
    # / removing a DGP doesn't perturb the others' draws.
    dgp_rngs = parent_rng.spawn(4)
    dgp_keys = ["A", "B", "C", "D"]

    all_frames = []
    out_tables = REPORTS / "tables"
    out_tables.mkdir(parents=True, exist_ok=True)
    for key, rng in zip(dgp_keys, dgp_rngs):
        df = run_dgp(key, rng, n_reps=N_REPS)
        if df.empty:
            print(f"  DGP {key}: NO ROWS — skipping", flush=True)
            continue
        out_path = out_tables / f"sim_{key.lower()}_per_symbol_kupiec.csv"
        df.to_csv(out_path, index=False)
        print(f"  Wrote {out_path}  ({len(df):,} rows)", flush=True)
        all_frames.append(df)

    all_df = pd.concat(all_frames, ignore_index=True)
    summary = summarise(all_df)
    summary_path = out_tables / "sim_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"\nWrote {summary_path}", flush=True)

    # Headline table at τ=0.95.
    print("\n" + "=" * 100)
    print("HEADLINE — per-symbol Kupiec pass-rate (p ≥ 0.05) at τ=0.95")
    print("(across 100 reps × 10 symbols = 1000 (symbol, rep) cells)")
    print("=" * 100)
    h = summary[summary["tau"] == 0.95].pivot(
        index="dgp", columns="forecaster",
        values=["pass_rate_05", "mean_realised"]
    )
    print(h.to_string(float_format=lambda x: f"{x:.4f}"))

    print("\n" + "=" * 100)
    print("Per-DGP, per-τ summary")
    print("=" * 100)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    render_figure(all_df, REPORTS / "figures")


if __name__ == "__main__":
    main()
