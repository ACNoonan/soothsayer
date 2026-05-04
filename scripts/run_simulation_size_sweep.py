"""
Phase 6 — sample-size sensitivity for the M6 (LWC) per-symbol calibration.

Sweeps the panel-length axis over the same four DGPs from Phase 3
(`scripts/run_simulation_study.py`). Answers the production-deployment
question: **how soon can a newly-listed symbol be admitted to the M6
panel without breaking per-symbol Kupiec calibration?**

Sweep grid
----------
  N (total weekends per symbol) ∈ {80, 100, 150, 200, 300, 400, 600}
  - N=600 reproduces Phase 3 byte-for-byte (regression guard).
  - N=200 corresponds to HOOD's regime (HOOD has 246 weekends in the
    deployed panel; ~218 evaluable after the σ̂ warm-up filter).
  - N=80 is the low-bound minimum-viable.

Train/OOS split: 2/3 train, 1/3 OOS — matches Phase 3's 400 / 200
convention. SPLIT_T(N) = round(N * 2/3).

DGPs A/B/C truncate cleanly: same standard-t draws as N=600, taking the
first-N-weekend prefix. DGP D adapts: structural break is always at
SPLIT_T(N) (the train/OOS boundary), so at smaller N the break-point
shifts. At N=600 this lands at t=400, matching Phase 3.

LWC σ̂ rule: K=26 (Phase 3 convention; preserves byte-for-byte
reproduction at N=600). Phase 5 promoted EWMA HL=8 as the canonical
deployed σ̂; the headline panel-admission threshold is reported under
the conservative K=26 rule. EWMA HL=8 only helps from there.

Outputs
-------
  reports/tables/sim_size_sweep_per_symbol_kupiec.csv
      One row per (dgp, n_weekends, rep, symbol, tau, forecaster).

  reports/tables/sim_size_sweep_summary.csv
      One row per (dgp, n_weekends, tau, forecaster):
      pass_rate_05, mean_realised, mean_kupiec_p, n_pass_05, n_total.

  reports/figures/sim_size_curves.{pdf,png}
      4-panel (DGP A/B/C/D); N on x-axis (log-spaced), pass-rate at τ=0.95
      on y-axis, M5 vs LWC as separate lines. Horizontal reference at 0.95
      (panel-admission target).

Run
---
  uv run python -u scripts/run_simulation_size_sweep.py
  uv run python -u scripts/run_simulation_size_sweep.py --reproduce-phase3
  uv run python -u scripts/run_simulation_size_sweep.py --n-list 80,200,600

Reproducibility
---------------
RNG hierarchy is identical to Phase 3:
    parent = default_rng(0)
    [dgp_a_rng, dgp_b_rng, dgp_c_rng, dgp_d_rng] = parent.spawn(4)
    [rep_rng_0, ..., rep_rng_99] = dgp_X_rng.spawn(100)
The base panel for each rep is built at N=600 using the rep's RNG (same
RNG calls as Phase 3); smaller-N panels are deterministic truncations of
that base. So the N=600 column of the sweep is bit-identical to Phase 3,
and the rest of the sweep is reproducible from `seed=0` alone.

Wall-clock: full battery (7 N × 4 DGPs × 100 reps × 2 forecasters ≈
22,400 cells) finishes in about 7 minutes. The σ̂ inner loop dominates;
LWC at N=600 is ~10× slower per cell than at N=80.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    add_sigma_hat_sym_ewma,
    compute_score_lwc,
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.config import REPORTS

# Mirror Phase 3 constants exactly so N=600 cells reproduce byte-for-byte.
# `scripts/` isn't a package, so import via the file path.
import importlib.util
import sys
from pathlib import Path

_PHASE3_PATH = Path(__file__).resolve().parent / "run_simulation_study.py"
_spec = importlib.util.spec_from_file_location(
    "_run_simulation_study", _PHASE3_PATH,
)
_phase3 = importlib.util.module_from_spec(_spec)
sys.modules["_run_simulation_study"] = _phase3
_spec.loader.exec_module(_phase3)

BASE_DATE = _phase3.BASE_DATE
MARKOV_P = _phase3.MARKOV_P
N_REPS = _phase3.N_REPS
N_SYMBOLS = _phase3.N_SYMBOLS
PHASE3_N_WEEKENDS = _phase3.N_WEEKENDS
REGIME_LABELS = _phase3.REGIME_LABELS
SEED = _phase3.SEED
SIGMA_GRID = _phase3.SIGMA_GRID
STATIONARY = _phase3.STATIONARY
SYMBOLS = _phase3.SYMBOLS
TAUS = _phase3.TAUS
VOL_MULTIPLIER = _phase3.VOL_MULTIPLIER
_empty_panel = _phase3._empty_panel
_simulate_markov_regime = _phase3._simulate_markov_regime


SWEEP_N: tuple[int, ...] = (80, 100, 150, 200, 300, 400, 600)
TRAIN_FRACTION = 2.0 / 3.0
OUT_TABLES = REPORTS / "tables"
OUT_FIGURES = REPORTS / "figures"

# σ̂ variant for the LWC forecaster path. "k26" = trailing 26-weekend window
# (Phase 3 convention; bit-exact reproduction of sim_summary.csv at N=600).
# "ewma_hl8" = post-Phase-5 canonical σ̂ (`reports/m6_sigma_ewma.md`).
SIGMA_VARIANTS = ("k26", "ewma_hl8")


# ------------------------------------------------------------- panel building
#
# These N-aware builders preserve Phase 3's RNG call sequence at N=600 — each
# rep's base panel is generated at N=PHASE3_N_WEEKENDS first, then the panel
# is truncated to the requested N. DGPs A/B/C truncate cleanly. DGP D's break
# always lands at SPLIT_T(N), which is t=400 at N=600 (matches Phase 3) and
# adapts to keep "exchangeability stress at the train/OOS boundary" semantics
# for shorter panels.


def _split_t_for(n_weekends: int) -> int:
    """Train/OOS boundary: round(N * 2/3). At N=600 → 400, matching Phase 3."""
    return int(round(n_weekends * TRAIN_FRACTION))


def _split_date_for(n_weekends: int) -> date:
    return BASE_DATE + timedelta(days=7 * _split_t_for(n_weekends))


def _student_t_raw(rng: np.random.Generator, n_t: int,
                   df: float = 4.0) -> np.ndarray:
    """Raw standard-t draws (variance-1 pre-rescale). Returns
    `(N_SYMBOLS, n_t)` array; later multiplied by σ-multipliers."""
    raw = rng.standard_t(df, size=(N_SYMBOLS, n_t))
    return raw / np.sqrt(df / (df - 2.0))


def _truncate_panel(panel: pd.DataFrame, n_weekends: int) -> pd.DataFrame:
    """Keep the first `n_weekends` distinct fri_ts values. Returns a copy with
    a fresh index so downstream `serve_bands` row-indexing is preserved."""
    keep_dates = sorted(panel["fri_ts"].unique())[:n_weekends]
    return (panel[panel["fri_ts"].isin(keep_dates)]
            .sort_values(["fri_ts", "symbol"])
            .reset_index(drop=True))


def make_panel_a(rng: np.random.Generator, n_weekends: int) -> pd.DataFrame:
    """DGP A: homoskedastic Student-t df=4 per-symbol; no regimes.

    Identical to Phase 3 at N=600. The standard-t draws are made at full
    PHASE3_N_WEEKENDS so the per-rep RNG call sequence matches Phase 3
    exactly; the result is then truncated to `n_weekends`."""
    raw = _student_t_raw(rng, PHASE3_N_WEEKENDS)
    sigmas = SIGMA_GRID.reshape(-1, 1)  # broadcast over t
    r_full = sigmas * raw
    return _build_panel_from_returns(r_full[:, :n_weekends],
                                     regimes_full=None,
                                     n_weekends=n_weekends)


def make_panel_b(rng: np.random.Generator, n_weekends: int) -> pd.DataFrame:
    """DGP B: regime-switching global vol multiplier on top of A's per-symbol σ.

    The Markov chain is simulated at full PHASE3_N_WEEKENDS first (the
    Phase 3 RNG call), then truncated. Same for the standard-t draws."""
    regime_path_full = _simulate_markov_regime(rng, PHASE3_N_WEEKENDS)
    raw = _student_t_raw(rng, PHASE3_N_WEEKENDS)
    multipliers_full = np.array(
        [VOL_MULTIPLIER[REGIME_LABELS[r]] for r in regime_path_full],
        dtype=float,
    )
    sigmas = SIGMA_GRID.reshape(-1, 1) * multipliers_full.reshape(1, -1)
    r_full = sigmas * raw
    regimes_truncated = np.array(
        [REGIME_LABELS[r] for r in regime_path_full[:n_weekends]]
    )
    return _build_panel_from_returns(r_full[:, :n_weekends],
                                     regimes_full=regimes_truncated,
                                     n_weekends=n_weekends)


def make_panel_c(rng: np.random.Generator, n_weekends: int) -> pd.DataFrame:
    """DGP C: non-stationary scale, σ_t = σ_i · (1 + 0.1 · t / PHASE3_N).

    The drift slope is fixed (0.1 / 600 per weekend) — at smaller N we see
    less drift accumulated, which is the natural interpretation of "shorter
    panel → less of the long-run drift visible". Bit-identical at N=600
    because the drift function and standard-t draws match Phase 3."""
    raw = _student_t_raw(rng, PHASE3_N_WEEKENDS)
    drift = 1.0 + 0.1 * np.arange(PHASE3_N_WEEKENDS) / PHASE3_N_WEEKENDS
    sigmas = SIGMA_GRID.reshape(-1, 1) * drift.reshape(1, -1)
    r_full = sigmas * raw
    return _build_panel_from_returns(r_full[:, :n_weekends],
                                     regimes_full=None,
                                     n_weekends=n_weekends)


def make_panel_d(rng: np.random.Generator, n_weekends: int) -> pd.DataFrame:
    """DGP D: structural break at SPLIT_T(N). At N=600 → break_t=400 (matches
    Phase 3); at smaller N the break shifts to the train/OOS boundary so the
    "exchangeability stress at OOS start" semantics is preserved.

    The standard-t draws are common across N (drawn at PHASE3_N_WEEKENDS), so
    only the σ-multiplier varies with N. At N=600 with break_t=400, the σ
    sequence equals Phase 3's exactly."""
    raw = _student_t_raw(rng, PHASE3_N_WEEKENDS)
    break_t_full = _split_t_for(n_weekends)  # break is N-dependent
    multipliers_full = np.ones(PHASE3_N_WEEKENDS)
    # Apply √3 from break_t onwards, but only up to N (rest is irrelevant).
    multipliers_full[break_t_full:] = np.sqrt(3.0)
    sigmas = SIGMA_GRID.reshape(-1, 1) * multipliers_full.reshape(1, -1)
    r_full = sigmas * raw
    return _build_panel_from_returns(r_full[:, :n_weekends],
                                     regimes_full=None,
                                     n_weekends=n_weekends)


def _build_panel_from_returns(r: np.ndarray,
                               regimes_full: np.ndarray | None,
                               n_weekends: int) -> pd.DataFrame:
    """Materialise a (10 × n_weekends) returns matrix into the long-form panel
    schema the calibration helpers expect. `regimes_full` is an n_weekends-
    length array (DGP B); None means a single "normal" regime."""
    panel = _empty_panel(SYMBOLS, n_weekends)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]],
                                     int(row["_t"])]),
        axis=1,
    )
    if regimes_full is None:
        panel["regime_pub"] = "normal"
    else:
        panel["regime_pub"] = panel["_t"].map(lambda t: regimes_full[int(t)])
    return panel.drop(columns=["_t"]).reset_index(drop=True)


DGP_BUILDERS = {
    "A": ("homoskedastic", make_panel_a),
    "B": ("regime-switching", make_panel_b),
    "C": ("non-stationary scale", make_panel_c),
    "D": ("exchangeability stress (break at SPLIT_T)", make_panel_d),
}


# -------------------------------------------------------------- per-rep eval


def _prep_panel_lwc_ewma_hl8(panel: pd.DataFrame) -> pd.DataFrame:
    """LWC σ̂ swap: EWMA HL=8 instead of K=26. Surface the EWMA value under
    the canonical `sigma_hat_sym_pre_fri` column so `serve_bands_lwc` and the
    score path read it without further plumbing changes.

    Same warm-up rule (≥ 8 past obs) as the K=26 path so the evaluable
    rows are identical."""
    work = add_sigma_hat_sym_ewma(panel, half_life=8)
    work["sigma_hat_sym_pre_fri"] = work["sigma_hat_sym_ewma_pre_fri_hl8"]
    work["score"] = compute_score_lwc(work,
                                      scale_col="sigma_hat_sym_pre_fri")
    return work


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
        rows.append({
            "symbol": sym, "tau": float(tau),
            "n": int(len(sub)),
            "viol_rate": float(v.mean()),
            "kupiec_lr": float(lr),
            "kupiec_p": float(p),
        })
    return pd.DataFrame(rows)


def evaluate_one_rep(panel: pd.DataFrame,
                     dgp: str,
                     n_weekends: int,
                     rep: int,
                     sigma_variant: str = "k26") -> pd.DataFrame:
    split_d = _split_date_for(n_weekends)
    rows = []
    for forecaster in ("m5", "lwc"):
        if forecaster == "lwc" and sigma_variant == "ewma_hl8":
            prepped = _prep_panel_lwc_ewma_hl8(panel)
        else:
            prepped = prep_panel_for_forecaster(panel, forecaster)
        prepped = prepped.dropna(subset=["score"]).reset_index(drop=True)
        try:
            qt, cb, _info = fit_split_conformal_forecaster(
                prepped, split_d, forecaster, cell_col="regime_pub",
            )
        except Exception:
            # Edge: at very small N a regime cell can be empty in this rep.
            continue
        oos = (prepped[prepped["fri_ts"] >= split_d]
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
            kup["n_weekends"] = int(n_weekends)
            rows.append(kup)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


# ----------------------------------------------------------------- main loop


def run_dgp_size_sweep(dgp_key: str, parent_rng: np.random.Generator,
                        n_list: tuple[int, ...],
                        n_reps: int = N_REPS,
                        sigma_variant: str = "k26") -> pd.DataFrame:
    """Run all (N, rep) cells for a single DGP, sharing the RNG hierarchy
    with Phase 3 so the N=600 cells reproduce that run byte-for-byte under
    the K=26 σ̂ rule. `sigma_variant="ewma_hl8"` swaps the LWC σ̂ for the
    post-Phase-5 deployed rule; M5 path is unchanged across variants."""
    name, builder = DGP_BUILDERS[dgp_key]
    print(f"\n[DGP {dgp_key}] {name}  (σ̂={sigma_variant})", flush=True)
    child_rngs = parent_rng.spawn(n_reps)
    out_frames = []
    for rep, rep_rng in enumerate(child_rngs):
        snapshot_state = rep_rng.bit_generator.state
        for n in n_list:
            cell_rng = np.random.default_rng()
            cell_rng.bit_generator.state = snapshot_state
            panel = builder(cell_rng, n)
            df = evaluate_one_rep(panel, dgp_key, n, rep,
                                  sigma_variant=sigma_variant)
            if not df.empty:
                out_frames.append(df)
        if (rep + 1) % 25 == 0:
            print(f"  {rep + 1}/{n_reps} reps complete", flush=True)
    if not out_frames:
        return pd.DataFrame()
    return pd.concat(out_frames, ignore_index=True)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-symbol-Kupiec table to one row per
    (dgp, n_weekends, τ, forecaster)."""
    rows = []
    for (dgp, n, tau, fc), g in df.groupby(["dgp", "n_weekends",
                                            "tau", "forecaster"]):
        n_total = len(g)
        n_pass = int((g["kupiec_p"] >= 0.05).sum())
        rows.append({
            "dgp": dgp,
            "n_weekends": int(n),
            "tau": float(tau),
            "forecaster": fc,
            "n_obs": n_total,
            "pass_rate_05": n_pass / n_total if n_total else float("nan"),
            "n_pass_05": n_pass,
            "n_total": n_total,
            "mean_realised": float(1 - g["viol_rate"].mean()),
            "mean_kupiec_p": float(g["kupiec_p"].mean()),
            "median_kupiec_p": float(g["kupiec_p"].median()),
        })
    return (pd.DataFrame(rows)
            .sort_values(["dgp", "n_weekends", "tau", "forecaster"])
            .reset_index(drop=True))


# -------------------------------------------------------------- thresholds


def panel_admission_thresholds(summary: pd.DataFrame,
                                tau_target: float = 0.95) -> pd.DataFrame:
    """Per-DGP minimum N at which (a) LWC pass-rate ≥ 0.95 and (b) LWC
    pass-rate ≥ M5's asymptotic (N=600) pass-rate."""
    rows = []
    for dgp in sorted(summary["dgp"].unique()):
        sub = summary[(summary["dgp"] == dgp)
                      & (summary["tau"] == tau_target)].sort_values("n_weekends")
        lwc = sub[sub["forecaster"] == "lwc"]
        m5 = sub[sub["forecaster"] == "m5"]
        # LWC ≥ 0.95
        admit_lwc = lwc[lwc["pass_rate_05"] >= 0.95]
        n_admit = int(admit_lwc["n_weekends"].min()) if not admit_lwc.empty else None
        # LWC parity with M5 asymptotic
        m5_asy = float(m5[m5["n_weekends"] == m5["n_weekends"].max()]
                       ["pass_rate_05"].iloc[0])
        parity_lwc = lwc[lwc["pass_rate_05"] >= m5_asy]
        n_parity = (int(parity_lwc["n_weekends"].min())
                    if not parity_lwc.empty else None)
        rows.append({
            "dgp": dgp,
            "tau": tau_target,
            "lwc_pass_rate_at_n600":
                float(lwc[lwc["n_weekends"] == lwc["n_weekends"].max()]
                      ["pass_rate_05"].iloc[0]),
            "m5_pass_rate_at_n600": m5_asy,
            "min_n_lwc_pass_rate_ge_095": n_admit,
            "min_n_lwc_pass_rate_ge_m5_asymptotic": n_parity,
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- figures


def render_curves(summary: pd.DataFrame, out_dir, suffix: str = "") -> None:
    """4-panel curves: N (log scale) × per-symbol Kupiec pass-rate at τ=0.95.
    M5 vs LWC. Reference line at 0.95 (panel-admission target).

    `suffix` (e.g. "_ewma_hl8") tags the output filenames so different σ̂
    variants don't overwrite each other."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sub = summary[summary["tau"] == 0.95].copy()
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5), sharex=True, sharey=True)
    titles = {
        "A": "DGP A — Homoskedastic Student-t",
        "B": "DGP B — Regime-switching vol multiplier",
        "C": "DGP C — Non-stationary scale (drift)",
        "D": "DGP D — Structural break (exchangeability stress)",
    }
    colors = {"m5": "#d62728", "lwc": "#1f77b4"}
    for ax, dgp in zip(axes.flat, ["A", "B", "C", "D"]):
        d = sub[sub["dgp"] == dgp]
        if d.empty:
            ax.set_title(f"{titles[dgp]}  (no data)")
            continue
        for fc in ("m5", "lwc"):
            f = d[d["forecaster"] == fc].sort_values("n_weekends")
            if f.empty:
                continue
            ax.plot(f["n_weekends"], f["pass_rate_05"],
                    marker="o", color=colors[fc],
                    label="M5" if fc == "m5" else "LWC")
        ax.axhline(0.95, color="black", linestyle="--", linewidth=0.7,
                   label="0.95 admit target")
        ax.set_xscale("log")
        ax.set_xticks([80, 100, 150, 200, 300, 400, 600])
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        ax.set_xlim(70, 700)
        ax.set_ylim(-0.02, 1.04)
        ax.set_xlabel("N weekends per symbol (total panel)")
        ax.set_ylabel("Per-symbol Kupiec pass-rate (p ≥ 0.05)")
        ax.set_title(titles[dgp])
        ax.legend(loc="lower right", fontsize=8)
    fig.suptitle("Phase 6 — Per-symbol Kupiec pass-rate vs panel length at τ=0.95\n"
                 "(100 Monte Carlo reps per cell; seed=0; N=600 reproduces Phase 3)",
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    pdf_path = out_dir / f"sim_size_curves{suffix}.pdf"
    png_path = out_dir / f"sim_size_curves{suffix}.png"
    fig.savefig(pdf_path)
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    print(f"\nWrote {pdf_path}", flush=True)
    print(f"Wrote {png_path}", flush=True)


# ---------------------------------------------------------------- regression


def regression_check_n600(sweep_summary: pd.DataFrame) -> None:
    """Verify that the N=600 cells reproduce `reports/tables/sim_summary.csv`
    byte-for-byte (the Phase 3 regression guard)."""
    phase3_path = OUT_TABLES / "sim_summary.csv"
    if not phase3_path.exists():
        print(f"\n[regression] {phase3_path} missing — skipping regression check.",
              flush=True)
        return
    phase3 = pd.read_csv(phase3_path)
    n600 = sweep_summary[sweep_summary["n_weekends"] == 600].copy()
    merged = n600.merge(
        phase3.rename(columns={
            "pass_rate_05": "pass_rate_05_phase3",
            "mean_realised": "mean_realised_phase3",
            "mean_kupiec_p": "mean_kupiec_p_phase3",
            "n_pass_05": "n_pass_05_phase3",
        })[["dgp", "tau", "forecaster",
            "pass_rate_05_phase3", "mean_realised_phase3",
            "mean_kupiec_p_phase3", "n_pass_05_phase3"]],
        on=["dgp", "tau", "forecaster"], how="inner",
    )
    if len(merged) != len(phase3):
        print(f"\n[regression] WARN: row-count mismatch "
              f"(sweep N=600 has {len(merged)}, Phase 3 has {len(phase3)})",
              flush=True)
    diffs = []
    for col_sweep, col_p3 in [
        ("n_pass_05", "n_pass_05_phase3"),
        ("pass_rate_05", "pass_rate_05_phase3"),
        ("mean_realised", "mean_realised_phase3"),
    ]:
        diff = (merged[col_sweep] - merged[col_p3]).abs()
        diffs.append((col_sweep, float(diff.max())))
    print("\n" + "=" * 100, flush=True)
    print("REGRESSION CHECK — N=600 sweep cells vs Phase 3 sim_summary.csv",
          flush=True)
    print("=" * 100, flush=True)
    for col, max_diff in diffs:
        verdict = "OK (bit-exact)" if max_diff == 0 else f"DIFF max={max_diff:.6g}"
        print(f"  {col:>20s}: {verdict}", flush=True)


# ----------------------------------------------------------------- driver


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n-list", default=",".join(str(n) for n in SWEEP_N),
        help="Comma-separated N values (default: %(default)s).",
    )
    parser.add_argument(
        "--dgps", default="A,B,C,D",
        help="Comma-separated DGP keys (default: %(default)s).",
    )
    parser.add_argument(
        "--reproduce-phase3", action="store_true",
        help="Run only N=600 — for the bit-exact regression check.",
    )
    parser.add_argument(
        "--n-reps", type=int, default=N_REPS,
        help="Monte Carlo reps per (DGP, N) cell (default: %(default)s).",
    )
    parser.add_argument(
        "--sigma-variant", choices=SIGMA_VARIANTS, default="k26",
        help="LWC σ̂ rule. 'k26' = Phase 3 baseline (default; bit-exact "
             "reproduction at N=600). 'ewma_hl8' = post-Phase-5 canonical "
             "σ̂ — outputs land in `*_ewma_hl8.csv` so the K=26 sweep is not "
             "overwritten.",
    )
    args = parser.parse_args()

    n_list = ((600,) if args.reproduce_phase3
              else tuple(int(x) for x in args.n_list.split(",")))
    dgp_keys = [s.strip().upper() for s in args.dgps.split(",") if s.strip()]
    for k in dgp_keys:
        if k not in DGP_BUILDERS:
            raise SystemExit(f"Unknown DGP key {k!r}. Choices: A,B,C,D")
    print(f"Seed: {SEED}  |  reps per (DGP, N): {args.n_reps}  |  "
          f"N grid: {n_list}  |  DGPs: {dgp_keys}  |  "
          f"σ̂={args.sigma_variant}", flush=True)

    # Always spawn 4 child RNGs in fixed (A, B, C, D) order so the per-DGP
    # RNG state matches Phase 3 even when --dgps filters to a subset.
    parent_rng = np.random.default_rng(SEED)
    all_dgp_rngs = parent_rng.spawn(4)
    rng_by_key = dict(zip(["A", "B", "C", "D"], all_dgp_rngs))

    # Output suffix scopes the variant so K=26 sweep isn't overwritten.
    suffix = "" if args.sigma_variant == "k26" else f"_{args.sigma_variant}"

    OUT_TABLES.mkdir(parents=True, exist_ok=True)
    all_frames = []
    for key in dgp_keys:
        df = run_dgp_size_sweep(key, rng_by_key[key], n_list=n_list,
                                n_reps=args.n_reps,
                                sigma_variant=args.sigma_variant)
        if df.empty:
            print(f"  DGP {key}: NO ROWS — skipping", flush=True)
            continue
        all_frames.append(df)

    if not all_frames:
        print("No cells produced; exiting.", flush=True)
        return
    all_df = pd.concat(all_frames, ignore_index=True)

    per_symbol_path = OUT_TABLES / f"sim_size_sweep_per_symbol_kupiec{suffix}.csv"
    all_df.to_csv(per_symbol_path, index=False)
    print(f"\nWrote {per_symbol_path}  ({len(all_df):,} rows)", flush=True)

    summary = summarise(all_df)
    summary_path = OUT_TABLES / f"sim_size_sweep_summary{suffix}.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Wrote {summary_path}", flush=True)

    thresholds = panel_admission_thresholds(summary, tau_target=0.95)
    thresh_path = OUT_TABLES / f"sim_size_sweep_admission_thresholds{suffix}.csv"
    thresholds.to_csv(thresh_path, index=False)
    print(f"Wrote {thresh_path}", flush=True)

    # Regression guard runs only when reproducing the Phase 3 K=26 baseline.
    if args.sigma_variant == "k26":
        regression_check_n600(summary)
    else:
        print(f"\n[regression] σ̂={args.sigma_variant} — skipping Phase 3 "
              f"regression check (variant differs from Phase 3 baseline).",
              flush=True)

    print("\n" + "=" * 100, flush=True)
    print("HEADLINE — per-symbol Kupiec pass-rate at τ=0.95 by N", flush=True)
    print("=" * 100, flush=True)
    headline = summary[summary["tau"] == 0.95].pivot_table(
        index=["dgp", "n_weekends"], columns="forecaster",
        values="pass_rate_05",
    )
    print(headline.round(4).to_string(), flush=True)

    print("\n" + "=" * 100, flush=True)
    print("PANEL-ADMISSION THRESHOLDS @ τ=0.95", flush=True)
    print("=" * 100, flush=True)
    print(thresholds.to_string(index=False, float_format=lambda x: f"{x:.4f}"),
          flush=True)

    # Only render the figure when the full DGP grid was swept; otherwise the
    # missing panels look broken.
    if 600 in n_list and len(n_list) > 1 and set(dgp_keys) == {"A", "B", "C", "D"}:
        render_curves(summary, OUT_FIGURES, suffix=suffix)


if __name__ == "__main__":
    main()
