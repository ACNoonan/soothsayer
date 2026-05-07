"""Paper 1 — Tier D item F2.

C3 D_jump_mean per-symbol pass-rate decomposition.

C3's writeup asserts the 59.5 % per-symbol Kupiec pass rate at τ=0.95
under D_jump_mean is *bimodal across symbols by σ_i* — low-vol symbols
(half-width < 200 bps) fail Kupiec because the +200 bps mean jump
displaces their realised observations beyond the band; high-vol symbols
(half-width > 200 bps) absorb the jump within their wider band. F2
verifies this empirically: pull per-symbol pass rate as a function of
σ_i across reps and check whether the relationship is monotone-cliff
(clean bimodality) or diffuse.

Cleaner predictions if bimodal:
  - Pass rate at σ_i = 0.005 (S00, lowest-vol) → near 0 %
  - Pass rate at σ_i = 0.030 (S09, highest-vol) → near 100 %
  - Phase transition near σ* such that half-width(σ*) ≈ jump magnitude (200 bps)

For τ=0.95 with t_4 marginals and σ̂ tracking actual std:
  half-width = q_r(0.95) · c(0.95) · σ̂ · fri_close
             ≈ 1.96 · c · σ_i · 100  (in price units)
             = 196 · c · σ_i  bps of fri_close
  so half-width(σ_i = 0.010) ≈ 196 · c · 0.01 ≈ 2 · c bps_of_fri_close × 100

Without c, half_width = 196 · σ_i — for σ=0.01 that's 1.96 → in price units
on fri_close=100 → 1.96 → 196 bps. So σ_i ≈ 0.010 should be the threshold
where half_width crosses 200 bps (c=1).

Output:
  reports/tables/paper1_f2_mean_jump_bimodality.csv
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

N_REPS = 100
SEED = 0
HEADLINE_TAU = 0.95
JUMP_BPS = 0.02   # +200 bps


def make_dgp_d_jump_mean(rng):
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    sigmas = SIGMA_GRID.reshape(-1, 1) * np.ones(N_WEEKENDS).reshape(1, -1)
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    mean_shift = np.zeros(N_WEEKENDS)
    mean_shift[SPLIT_T:] = JUMP_BPS
    r = r + mean_shift.reshape(1, -1)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]], int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = "normal"
    return panel.drop(columns=["_t"]).reset_index(drop=True)


def run_one_rep(panel, forecaster):
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
                     "passed": bool(p >= 0.05),
                     "mean_lower": float(bb["lower"].mean()),
                     "mean_upper": float(bb["upper"].mean()),
                     "mean_realised": float(sub["mon_open"].mean()),
                     "mean_half_width_bps": float(((bb["upper"] - bb["lower"]) / 2 / sub["fri_close"] * 1e4).mean()),
                     })
    return rows, cb[HEADLINE_TAU]


def main() -> None:
    parent_rng = np.random.default_rng(SEED)
    rep_seeds = parent_rng.spawn(N_REPS)

    sigma_by_sym = {SYMBOLS[i]: float(SIGMA_GRID[i]) for i in range(N_SYMBOLS)}
    print(f"Symbol → σ_i:")
    for s, sg in sigma_by_sym.items():
        print(f"  {s}: σ = {sg:.4f}  (typical t_4 |z| · σ · 100 = {0.85 * sg * 100:.1f} pre-jump bps)")
    print(f"Mean jump magnitude: {JUMP_BPS * 1e4:.0f} bps")

    rows_all = []
    cb_log = []
    for rep in range(N_REPS):
        rng = np.random.default_rng(rep_seeds[rep])
        panel = make_dgp_d_jump_mean(rng)
        for forecaster in ("m5", "lwc"):
            rows, c_at_95 = run_one_rep(panel, forecaster)
            for r in rows:
                rows_all.append({"rep": rep, "forecaster": forecaster,
                                  "sigma_i": sigma_by_sym[r["symbol"]],
                                  **r})
            cb_log.append({"rep": rep, "forecaster": forecaster,
                            "c_at_0.95": c_at_95})

    df = pd.DataFrame(rows_all)
    cb_df = pd.DataFrame(cb_log)

    # Per-symbol pass rate across reps × forecaster
    summary = (df.groupby(["forecaster", "symbol", "sigma_i"])
                  .agg(pass_rate=("passed", "mean"),
                       mean_viol_rate=("viol_rate", "mean"),
                       mean_half_width_bps=("mean_half_width_bps", "mean"),
                       mean_realised=("mean_realised", "mean"),
                       mean_lower=("mean_lower", "mean"),
                       mean_upper=("mean_upper", "mean"),
                       n_reps=("passed", "size"))
                  .reset_index())
    summary["jump_inside_band"] = (
        (summary["mean_lower"] <= 100.0 + JUMP_BPS * 100) &
        (summary["mean_upper"] >= 100.0 + JUMP_BPS * 100)
    )

    print("\n=== per-symbol pass rate at τ=0.95, both forecasters ===")
    for forecaster in ("m5", "lwc"):
        sub = summary[summary["forecaster"] == forecaster].sort_values("sigma_i")
        print(f"\n{forecaster.upper()}:")
        print(sub[["symbol", "sigma_i", "pass_rate",
                   "mean_viol_rate", "mean_half_width_bps",
                   "jump_inside_band"]].to_string(
            index=False, float_format=lambda x: f"{x:.4f}"))

    # Mean c(0.95) across reps per forecaster
    print("\n=== c(τ=0.95) across reps ===")
    print(cb_df.groupby("forecaster")["c_at_0.95"]
          .agg(["mean", "median", "min", "max"])
          .to_string(float_format=lambda x: f"{x:.4f}"))

    out = REPORTS / "tables" / "paper1_f2_mean_jump_bimodality.csv"
    summary.to_csv(out, index=False)
    print(f"\nwrote {out}")

    # Bimodality check: is there a clean monotone-cliff in pass_rate vs sigma_i?
    print("\n=== bimodality diagnostic (LWC) ===")
    lwc = summary[summary["forecaster"] == "lwc"].sort_values("sigma_i").reset_index(drop=True)
    print("σ_i ascending:")
    for _, r in lwc.iterrows():
        bar = "█" * int(round(r["pass_rate"] * 20))
        print(f"  σ={r['sigma_i']:.4f}  hw={r['mean_half_width_bps']:7.1f}bps  "
              f"pass={r['pass_rate']:.2f}  {bar}")
    if (lwc["pass_rate"].iloc[0] < 0.20 and lwc["pass_rate"].iloc[-1] > 0.80):
        print("\n  → CLEAN MONOTONE STRUCTURE confirmed: "
              "low-σ (failing) → high-σ (passing) phase transition")
    else:
        print("\n  → bimodality NOT clean (more diffuse than predicted)")


if __name__ == "__main__":
    main()
