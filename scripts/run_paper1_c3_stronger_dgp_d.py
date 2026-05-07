"""Paper 1 — Tier C item C3.

Stronger DGP-D variants — the existing simulation §6.6 DGP-D uses a 3×
transient variance bump (std × √3). Real markets routinely do worse:
2024-08-05 BoJ unwind, 2025-04 tariff weekend, 2020-03 COVID.

Three variants tested here, all sharing DGP-D's structural-break frame:

  D_3x_persistent (existing baseline)
                std × √3 from t=400 onward
                (this is the §6.6 result the paper currently reports)

  D_10x_persistent
                std × √10 from t=400 onward
                Permanent regime shift to 10× variance — the most extreme
                stationarity break a real underlying could exhibit.

  D_10x_50wk_transient
                std × √10 for t ∈ [400, 450), std × 1 thereafter
                Transient bump matching real-world events (COVID-month
                vol multiplier was roughly 5× for ~6-8 weeks).

  D_jump_mean
                Mean shifts from 0 to +0.02 (200 bps) at t=400, std unchanged.
                Tests conditional-mean break (vs the variance-only breaks
                above). The σ̂ standardisation does not adapt to mean drift.

For each: run M5 + LWC fit at split t=400, evaluate on t ≥ 400 OOS,
report per-symbol Kupiec pass rate at τ=0.95 across N_REPS=100 reps.

Output:
  reports/tables/paper1_c3_stronger_dgp_d.csv
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.backtest import metrics as met
from soothsayer.config import REPORTS

# Re-use constants from the existing simulation script.
import sys
sys.path.insert(0, str((REPORTS.parent / "scripts").resolve()))
from run_simulation_study import (  # type: ignore
    N_WEEKENDS, N_SYMBOLS, SPLIT_T, SPLIT_DATE_SYNTH, BASE_DATE,
    SIGMA_GRID, SYMBOLS, _empty_panel, _student_t_returns,
    DEFAULT_TAUS,
)

N_REPS = 100
SEED = 0
HEADLINE_TAU = 0.95


def make_dgp_d_3x_persistent(rng: np.random.Generator) -> pd.DataFrame:
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    multiplier = np.ones(N_WEEKENDS)
    multiplier[SPLIT_T:] = np.sqrt(3.0)
    sigmas = SIGMA_GRID.reshape(-1, 1) * multiplier.reshape(1, -1)
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]], int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = "normal"
    return panel.drop(columns=["_t"]).reset_index(drop=True)


def make_dgp_d_10x_persistent(rng: np.random.Generator) -> pd.DataFrame:
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    multiplier = np.ones(N_WEEKENDS)
    multiplier[SPLIT_T:] = np.sqrt(10.0)
    sigmas = SIGMA_GRID.reshape(-1, 1) * multiplier.reshape(1, -1)
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]], int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = "normal"
    return panel.drop(columns=["_t"]).reset_index(drop=True)


def make_dgp_d_10x_50wk_transient(rng: np.random.Generator) -> pd.DataFrame:
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    multiplier = np.ones(N_WEEKENDS)
    multiplier[SPLIT_T:SPLIT_T + 50] = np.sqrt(10.0)
    sigmas = SIGMA_GRID.reshape(-1, 1) * multiplier.reshape(1, -1)
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]], int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = "normal"
    return panel.drop(columns=["_t"]).reset_index(drop=True)


def make_dgp_d_jump_mean(rng: np.random.Generator) -> pd.DataFrame:
    panel = _empty_panel(SYMBOLS, N_WEEKENDS)
    multiplier = np.ones(N_WEEKENDS)  # std unchanged
    sigmas = SIGMA_GRID.reshape(-1, 1) * multiplier.reshape(1, -1)
    r = _student_t_returns(rng, sigmas, N_WEEKENDS)
    # Add a +200 bps mean jump from t=400 onward, on every symbol
    mean_shift = np.zeros(N_WEEKENDS)
    mean_shift[SPLIT_T:] = 0.02
    r = r + mean_shift.reshape(1, -1)
    sym_to_idx = {s: i for i, s in enumerate(SYMBOLS)}
    panel["mon_open"] = panel.apply(
        lambda row: 100.0 * (1.0 + r[sym_to_idx[row["symbol"]], int(row["_t"])]),
        axis=1,
    )
    panel["regime_pub"] = "normal"
    return panel.drop(columns=["_t"]).reset_index(drop=True)


DGPS = [
    ("D_3x_persistent",       "std × √3 from t=400 (existing §6.6 baseline)",     make_dgp_d_3x_persistent),
    ("D_10x_persistent",      "std × √10 from t=400 (extreme persistent)",         make_dgp_d_10x_persistent),
    ("D_10x_50wk_transient",  "std × √10 for t ∈ [400, 450), std × 1 thereafter",  make_dgp_d_10x_50wk_transient),
    ("D_jump_mean",           "+200 bps conditional-mean jump at t=400 (std unchanged)", make_dgp_d_jump_mean),
]


def per_symbol_pass(panel_oos, bounds, tau):
    rows = []
    for sym, idx in panel_oos.groupby("symbol").groups.items():
        sub = panel_oos.loc[idx]
        b = bounds[tau].loc[idx]
        inside = (sub["mon_open"] >= b["lower"]) & (sub["mon_open"] <= b["upper"])
        v = (~inside).astype(int).to_numpy()
        lr, p = met._lr_kupiec(v, tau)
        rows.append({"symbol": sym, "n": int(len(sub)),
                     "viol_rate": float(v.mean()),
                     "kupiec_p": float(p), "passed": bool(p >= 0.05)})
    return rows


def main() -> None:
    parent_rng = np.random.default_rng(SEED)
    out_rows = []
    for dgp_key, description, builder in DGPS:
        print(f"\n=== {dgp_key}: {description} ===", flush=True)
        rep_seeds = parent_rng.spawn(N_REPS)
        m5_pass_rates = []
        lwc_pass_rates = []
        m5_realised = []
        lwc_realised = []
        for rep in range(N_REPS):
            rng = np.random.default_rng(rep_seeds[rep])
            panel = builder(rng)
            for forecaster in ("m5", "lwc"):
                prepped = prep_panel_for_forecaster(panel, forecaster)
                prepped = prepped.dropna(subset=["score"]).reset_index(drop=True)
                try:
                    qt, cb, info = fit_split_conformal_forecaster(
                        prepped, SPLIT_DATE_SYNTH, forecaster, cell_col="regime_pub",
                    )
                except Exception:
                    continue
                oos = (prepped[prepped["fri_ts"] >= SPLIT_DATE_SYNTH]
                       .dropna(subset=["score"]).reset_index(drop=True))
                if len(oos) == 0:
                    continue
                bounds = serve_bands_forecaster(
                    oos, qt, cb, forecaster,
                    cell_col="regime_pub", taus=DEFAULT_TAUS,
                )
                rows = per_symbol_pass(oos, bounds, HEADLINE_TAU)
                n_pass = sum(1 for r in rows if r["passed"])
                # Pooled realised
                b = bounds[HEADLINE_TAU]
                inside = ((oos["mon_open"] >= b["lower"])
                          & (oos["mon_open"] <= b["upper"]))
                if forecaster == "m5":
                    m5_pass_rates.append(n_pass / N_SYMBOLS)
                    m5_realised.append(float(inside.mean()))
                else:
                    lwc_pass_rates.append(n_pass / N_SYMBOLS)
                    lwc_realised.append(float(inside.mean()))
        m5_pr_mean = float(np.mean(m5_pass_rates)) if m5_pass_rates else float("nan")
        lwc_pr_mean = float(np.mean(lwc_pass_rates)) if lwc_pass_rates else float("nan")
        m5_realised_mean = float(np.mean(m5_realised)) if m5_realised else float("nan")
        lwc_realised_mean = float(np.mean(lwc_realised)) if lwc_realised else float("nan")
        out_rows.append({
            "dgp": dgp_key,
            "description": description,
            "n_reps": N_REPS,
            "m5_per_symbol_pass_rate_at_0.95": m5_pr_mean,
            "lwc_per_symbol_pass_rate_at_0.95": lwc_pr_mean,
            "m5_pooled_realised_at_0.95": m5_realised_mean,
            "lwc_pooled_realised_at_0.95": lwc_realised_mean,
        })
        print(f"  M5  per-symbol pass rate at τ=0.95: {m5_pr_mean*100:.1f}%  "
              f"(pooled realised: {m5_realised_mean:.4f})")
        print(f"  LWC per-symbol pass rate at τ=0.95: {lwc_pr_mean*100:.1f}%  "
              f"(pooled realised: {lwc_realised_mean:.4f})")

    df = pd.DataFrame(out_rows)
    out_path = REPORTS / "tables" / "paper1_c3_stronger_dgp_d.csv"
    df.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}", flush=True)
    print("\n=== summary ===")
    print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
