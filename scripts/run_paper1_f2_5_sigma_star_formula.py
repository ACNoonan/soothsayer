"""Paper 1 — Tier D follow-up F2.5.

Validate F2's predicted phase-transition formula

  σ*(Δ) ≈ Δ / (q · c − 1)

across multiple jump magnitudes Δ ∈ {50, 100, 200, 400} bps. F2 found
the empirical phase transition at σ_i ≈ 0.013–0.016 for Δ = 200 bps;
that's a single-point match. F2.5 sweeps Δ and confirms whether the
formula tracks the empirical transition across Δ — converting σ* from
"matches once" to "predictive across magnitudes".

For each Δ:
  1. Run 100 reps of D_jump_mean with that Δ.
  2. Per σ_i, aggregate per-symbol Kupiec pass rate at τ=0.95.
  3. Identify empirical phase transition σ*_emp = smallest σ with
     pass_rate ≥ 0.5.
  4. Predicted σ*_pred = Δ / (q·c − 1) where q = q_r(0.95) · c(0.95)
     for LWC on the synthetic panel under no-jump fit.
  5. Compare σ*_emp vs σ*_pred.

Output:
  reports/tables/paper1_f2_5_sigma_star_formula.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.backtest import metrics as met
from soothsayer.config import REPORTS

import sys
sys.path.insert(0, str((REPORTS.parent / "scripts").resolve()))
from run_simulation_study import (  # type: ignore
    N_WEEKENDS, N_SYMBOLS, SPLIT_T, SPLIT_DATE_SYNTH,
    SIGMA_GRID, SYMBOLS, _empty_panel, _student_t_returns,
    DEFAULT_TAUS,
)

N_REPS = 50
SEED = 0
HEADLINE_TAU = 0.95
DELTA_BPS_GRID = (50, 100, 200, 400)   # in bps; 200 = F2 baseline


def make_dgp_jump(rng, jump_bps):
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    sigmas = SIGMA_GRID.reshape(-1, 1) * np.ones(N_WEEKENDS).reshape(1, -1)
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    mean_shift = np.zeros(N_WEEKENDS)
    mean_shift[SPLIT_T:] = jump_bps / 1e4
    r = r + mean_shift.reshape(1, -1)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]], int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = "normal"
    return panel.drop(columns=["_t"]).reset_index(drop=True)


def evaluate_jump(panel, forecaster):
    prepped = prep_panel_for_forecaster(panel, forecaster)
    prepped = prepped.dropna(subset=["score"]).reset_index(drop=True)
    qt, cb, info = fit_split_conformal_forecaster(
        prepped, SPLIT_DATE_SYNTH, forecaster, cell_col="regime_pub",
    )
    oos = (prepped[prepped["fri_ts"] >= SPLIT_DATE_SYNTH]
           .dropna(subset=["score"]).reset_index(drop=True))
    bounds = serve_bands_forecaster(
        oos, qt, cb, forecaster,
        cell_col="regime_pub", taus=DEFAULT_TAUS,
    )
    rows = []
    b = bounds[HEADLINE_TAU]
    for sym, idx in oos.groupby("symbol").groups.items():
        sub = oos.loc[idx]
        bb = b.loc[idx]
        inside = (sub["mon_open"] >= bb["lower"]) & (sub["mon_open"] <= bb["upper"])
        v = (~inside).astype(int).to_numpy()
        if len(v) < 5:
            continue
        lr, p = met._lr_kupiec(v, HEADLINE_TAU)
        rows.append({"symbol": sym,
                     "viol_rate": float(v.mean()),
                     "kupiec_p": float(p),
                     "passed": bool(p >= 0.05)})
    # Also extract the standardised threshold q_r * c at this τ on the
    # `normal` cell (only one cell in this synthetic panel).
    q = qt.get("normal", {}).get(HEADLINE_TAU, np.nan)
    c = cb[HEADLINE_TAU]
    return rows, float(q), float(c)


def main() -> None:
    parent_rng = np.random.default_rng(SEED)
    rep_seeds = parent_rng.spawn(N_REPS)
    sigma_by_sym = {SYMBOLS[i]: float(SIGMA_GRID[i]) for i in range(N_SYMBOLS)}

    summary_rows = []

    for delta_bps in DELTA_BPS_GRID:
        delta = delta_bps / 1e4
        print(f"\n=== Δ = {delta_bps} bps ===", flush=True)
        # Aggregate per-symbol pass rate across reps
        per_sym_pass_count = {s: 0 for s in SYMBOLS}
        per_sym_count = {s: 0 for s in SYMBOLS}
        per_sym_viol_rates = {s: [] for s in SYMBOLS}
        q_log, c_log = [], []
        for rep in range(N_REPS):
            rng = np.random.default_rng(rep_seeds[rep])
            panel = make_dgp_jump(rng, delta_bps)
            rows, q_at_95, c_at_95 = evaluate_jump(panel, "lwc")
            q_log.append(q_at_95)
            c_log.append(c_at_95)
            for r in rows:
                per_sym_count[r["symbol"]] += 1
                per_sym_viol_rates[r["symbol"]].append(r["viol_rate"])
                if r["passed"]:
                    per_sym_pass_count[r["symbol"]] += 1

        q_mean = float(np.mean(q_log))
        c_mean = float(np.mean(c_log))
        qc = q_mean * c_mean
        print(f"  q_mean = {q_mean:.4f}  c_mean = {c_mean:.4f}  q·c = {qc:.4f}")

        sigma_pred = delta / max(qc - 1.0, 1e-9)
        print(f"  predicted σ*(Δ={delta_bps} bps) = Δ/(q·c−1) = "
              f"{delta_bps}/{qc - 1:.3f} = {sigma_pred:.4f} = "
              f"{sigma_pred * 1e4:.0f} bps in σ_i units")

        # Per-symbol pass rate
        sigma_pass = []
        for s in SYMBOLS:
            n = per_sym_count[s]
            pr = per_sym_pass_count[s] / max(n, 1)
            sigma_pass.append((sigma_by_sym[s], s, pr))
        sigma_pass.sort()

        # Empirical σ*_emp = smallest σ with pass_rate ≥ 0.5
        sigma_star_emp = None
        for sg, s, pr in sigma_pass:
            if pr >= 0.5:
                sigma_star_emp = sg
                break
        print(f"  empirical σ*_emp (smallest σ with pass ≥ 0.5):")
        for sg, s, pr in sigma_pass:
            mark = "←" if sg == sigma_star_emp else " "
            print(f"    σ={sg:.4f} ({s}): pass_rate={pr:.2f}  {mark}")
        print(f"  σ*_emp = {sigma_star_emp:.4f} = {sigma_star_emp * 1e4:.0f} bps "
              f"vs σ*_pred = {sigma_pred:.4f} = {sigma_pred * 1e4:.0f} bps  "
              f"(ratio emp/pred = {sigma_star_emp / sigma_pred:.2f})")

        for sg, s, pr in sigma_pass:
            summary_rows.append({
                "delta_bps": delta_bps, "symbol": s,
                "sigma_i": sg, "pass_rate": pr,
                "n_reps": per_sym_count[s],
                "mean_viol_rate": float(np.mean(per_sym_viol_rates[s])),
                "q_mean": q_mean, "c_mean": c_mean,
                "qc": qc,
                "sigma_star_pred": sigma_pred,
                "sigma_star_emp": sigma_star_emp,
            })

    df = pd.DataFrame(summary_rows)
    out = REPORTS / "tables" / "paper1_f2_5_sigma_star_formula.csv"
    df.to_csv(out, index=False)
    print(f"\nwrote {out}")

    print("\n=== σ* formula validation across Δ ===")
    pivot = df.groupby("delta_bps").agg(
        sigma_star_emp_bps=("sigma_star_emp", lambda s: s.iloc[0] * 1e4),
        sigma_star_pred_bps=("sigma_star_pred", lambda s: s.iloc[0] * 1e4),
        qc=("qc", "first"),
    )
    pivot["ratio_emp_over_pred"] = pivot["sigma_star_emp_bps"] / pivot["sigma_star_pred_bps"]
    print(pivot.to_string(float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
