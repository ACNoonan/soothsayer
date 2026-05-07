"""Paper 1 — Tier C item C2.

Page CUSUM drift detection on weekly violation rate at τ ∈ {0.85, 0.95, 0.99}.

Two-sided CUSUM:
  S_t^+ = max(0, S_{t-1}^+ + (X_t − μ_0 − k))    (upward shift = under-coverage)
  S_t^− = max(0, S_{t-1}^− − (X_t − μ_0 + k))    (downward shift = over-coverage)
  alarm at t if  max(S_t^+, S_t^−) ≥ h

  X_t = violation rate that weekend = k_w / 10
  μ_0 = nominal violation rate = 1 − τ
  k   = reference value, set to detect a 2× shift in violation rate
        k = (2 μ_0 − μ_0) / 2 = μ_0 / 2
  h   = decision threshold, calibrated by Monte Carlo to in-control
        ARL_0 = 200 weeks (one false alarm per ~4 years on average)

Power test: inject a 2× violation-rate shift starting at week 50 of a
synthetic 200-week trace; report detection latency averaged over 5,000
reps.

The deliverable is operational: the §9.2 disclosure currently describes
forward-tape monitoring as passive observation. CUSUM upgrades that to
an explicit drift detector with calibrated alarm rates — concrete, tied
to a τ-anchor, and quantitative.

Output:
  reports/tables/paper1_c2_cusum_drift.csv
  reports/tables/paper1_c2_cusum_calibration.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    add_sigma_hat_sym_ewma,
    SIGMA_HAT_HL_WEEKENDS,
    train_quantile_table,
    fit_c_bump_schedule,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
HEADLINE_TAUS = (0.85, 0.95, 0.99)
ARL_0_TARGET = 200            # one false alarm per ~4 years
N_SIM_FOR_H = 20_000
SIM_LENGTH = 500              # long enough to estimate ARL_0 ≤ 200
N_SIM_POWER = 5_000
POWER_LENGTH = 200
POWER_INJECTION_AT = 50
RNG = np.random.default_rng(20260506)


def cusum_two_sided(x: np.ndarray, mu0: float, k: float, h: float) -> dict:
    """Run two-sided CUSUM. Returns alarm time (or len(x) if never) and
    final S+ / S- trajectories."""
    n = len(x)
    s_pos = np.zeros(n + 1)
    s_neg = np.zeros(n + 1)
    alarm_t = n  # no alarm
    for t in range(n):
        s_pos[t + 1] = max(0.0, s_pos[t] + (x[t] - mu0 - k))
        s_neg[t + 1] = max(0.0, s_neg[t] - (x[t] - mu0 + k))
        if alarm_t == n and max(s_pos[t + 1], s_neg[t + 1]) >= h:
            alarm_t = t + 1
            break
    return {"alarm_t": alarm_t, "s_pos": s_pos, "s_neg": s_neg}


def calibrate_h(mu0: float, k: float, target_arl0: float, n_sim: int,
                sim_length: int) -> tuple[float, float]:
    """Find smallest h with mean ARL_0 ≥ target_arl0 (vectorised).

    Algorithm:
      1. Vectorised CUSUM across n_sim traces (one pass over t).
      2. Track running max M[i, t] of max(S_pos[i, t], S_neg[i, t]).
      3. Alarm time for threshold h on trace i is searchsorted(M[i], h).
      4. For each h on the grid, mean alarm time = mean ARL_0(h).
    """
    h_grid = np.unique(np.concatenate([
        np.arange(0.5, 50.0001, 0.5) * k,
        np.arange(0.05, 1.5001, 0.05),
    ]))
    h_grid = h_grid[h_grid > 0]
    samples = RNG.binomial(n=10, p=mu0, size=(n_sim, sim_length)) / 10.0

    # Vectorised CUSUM
    S_pos = np.zeros((n_sim, sim_length + 1))
    S_neg = np.zeros((n_sim, sim_length + 1))
    M = np.zeros((n_sim, sim_length + 1))
    for t in range(sim_length):
        S_pos[:, t + 1] = np.maximum(0.0,
                                       S_pos[:, t] + (samples[:, t] - mu0 - k))
        S_neg[:, t + 1] = np.maximum(0.0,
                                       S_neg[:, t] - (samples[:, t] - mu0 + k))
        M[:, t + 1] = np.maximum(M[:, t],
                                   np.maximum(S_pos[:, t + 1], S_neg[:, t + 1]))

    chosen = None
    for h in h_grid:
        # Alarm time per trace: smallest t s.t. M[i, t] >= h
        # M is non-decreasing along axis=1.
        alarm_t = np.argmax(M >= h, axis=1)  # 0 if never (from argmax of all-False)
        never = M[:, -1] < h
        alarm_t = np.where(never, sim_length, alarm_t)
        mean_rl = float(alarm_t.mean())
        if mean_rl >= target_arl0:
            chosen = (float(h), mean_rl)
            break
    if chosen is None:
        h = float(h_grid[-1])
        alarm_t = np.argmax(M >= h, axis=1)
        never = M[:, -1] < h
        alarm_t = np.where(never, sim_length, alarm_t)
        chosen = (h, float(alarm_t.mean()))
    return chosen


def detection_latency(mu0: float, mu1: float, k: float, h: float,
                      n_sim: int, length: int, inject_at: int) -> dict:
    """Vectorised detection latency under a step shift mu0 → mu1 at `inject_at`."""
    pre = RNG.binomial(n=10, p=mu0, size=(n_sim, inject_at)) / 10.0
    post = RNG.binomial(n=10, p=mu1, size=(n_sim, length - inject_at)) / 10.0
    samples = np.concatenate([pre, post], axis=1)
    S_pos = np.zeros((n_sim, length + 1))
    S_neg = np.zeros((n_sim, length + 1))
    M = np.zeros((n_sim, length + 1))
    for t in range(length):
        S_pos[:, t + 1] = np.maximum(0.0, S_pos[:, t] + (samples[:, t] - mu0 - k))
        S_neg[:, t + 1] = np.maximum(0.0, S_neg[:, t] - (samples[:, t] - mu0 + k))
        M[:, t + 1] = np.maximum(M[:, t],
                                   np.maximum(S_pos[:, t + 1], S_neg[:, t + 1]))
    alarm_t = np.argmax(M >= h, axis=1)
    never = M[:, -1] < h
    alarm_t = np.where(never, length, alarm_t).astype(float)
    detected = (alarm_t < length) & (alarm_t >= inject_at)
    n_detected = int(detected.sum())
    if n_detected == 0:
        return {"detection_rate": 0.0,
                "median_latency": float("nan"),
                "mean_latency": float("nan")}
    lats = alarm_t[detected] - inject_at
    return {"detection_rate": float(n_detected / n_sim),
            "median_latency": float(np.median(lats)),
            "mean_latency": float(np.mean(lats))}


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HAT_HL_WEEKENDS)
    sigma_col = f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HAT_HL_WEEKENDS}"
    panel["sigma_hat_sym_pre_fri"] = panel[sigma_col]
    panel["score_lwc"] = compute_score_lwc(panel, scale_col="sigma_hat_sym_pre_fri")
    panel = panel[panel["score_lwc"].notna()].reset_index(drop=True)

    train = panel[panel["fri_ts"] <  SPLIT_DATE].reset_index(drop=True)
    oos   = panel[panel["fri_ts"] >= SPLIT_DATE].sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    qt = train_quantile_table(train, cell_col="regime_pub",
                               taus=HEADLINE_TAUS, score_col="score_lwc")
    cb = fit_c_bump_schedule(oos, qt, cell_col="regime_pub",
                              taus=HEADLINE_TAUS, score_col="score_lwc")

    cells = oos["regime_pub"].astype(str).to_numpy()
    score = oos["score_lwc"].astype(float).to_numpy()
    sigma = oos["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    base_valid = np.isfinite(score) & np.isfinite(sigma) & (sigma > 0)

    rows_calib = []
    rows_emp = []
    rows_power = []
    for tau in HEADLINE_TAUS:
        mu0 = 1.0 - tau
        k = mu0 / 2.0
        c = cb[tau]
        b_per_row = np.array(
            [qt.get(cells[i], {}).get(tau, np.nan)
             for i in range(len(oos))],
            dtype=float,
        )
        valid = base_valid & np.isfinite(b_per_row)
        sub = oos[valid].copy()
        sub["score"] = score[valid]
        sub["b_eff"] = b_per_row[valid] * c
        sub["viol"] = (sub["score"] > sub["b_eff"]).astype(int)
        kw_per_w = sub.groupby("fri_ts")["viol"].sum() / 10.0
        x_emp = kw_per_w.to_numpy(float)
        n_weekends = len(x_emp)

        # Calibrate h
        h, mean_rl = calibrate_h(mu0, k, ARL_0_TARGET,
                                  N_SIM_FOR_H, SIM_LENGTH)
        rows_calib.append({"tau": tau, "mu0": mu0, "k": k, "h": h,
                           "mean_run_length_h0_under_calibration": mean_rl,
                           "n_weekends_oos": n_weekends})
        print(f"\n=== τ={tau}: μ_0={mu0:.4f}  k={k:.4f}  h={h:.4f}  "
              f"(mean H0 RL = {mean_rl:.0f} weekends) ===", flush=True)

        # Empirical OOS — does it alarm?
        res = cusum_two_sided(x_emp, mu0, k, h)
        max_pos = float(np.max(res["s_pos"]))
        max_neg = float(np.max(res["s_neg"]))
        alarmed = res["alarm_t"] < n_weekends
        rows_emp.append({"tau": tau, "n_weekends_oos": n_weekends,
                          "h": h,
                          "max_S_plus": max_pos,
                          "max_S_minus": max_neg,
                          "alarmed": alarmed,
                          "alarm_t": res["alarm_t"] if alarmed else None})
        print(f"  empirical OOS: alarmed = {alarmed}  "
              f"max S+ = {max_pos:.4f}  max S- = {max_neg:.4f}  "
              f"(threshold h = {h:.4f})")

        # Power: detection latency under 2x violation-rate shift
        for mu1_mult, label in [(2.0, "2x_shift"), (3.0, "3x_shift"),
                                 (1.5, "1.5x_shift")]:
            mu1 = mu0 * mu1_mult
            r = detection_latency(mu0, mu1, k, h, N_SIM_POWER,
                                   POWER_LENGTH, POWER_INJECTION_AT)
            rows_power.append({"tau": tau, "mu0": mu0,
                                "mu1_multiplier": mu1_mult,
                                "mu1": mu1, "label": label,
                                **r})
            print(f"  shift {label} (μ_0 → {mu1:.4f}): "
                  f"detection rate = {r['detection_rate']*100:.1f}%; "
                  f"median latency = {r['median_latency']:.1f} weekends")

    df_calib = pd.DataFrame(rows_calib)
    df_emp = pd.DataFrame(rows_emp)
    df_power = pd.DataFrame(rows_power)

    out_d = REPORTS / "tables" / "paper1_c2_cusum_drift.csv"
    out_c = REPORTS / "tables" / "paper1_c2_cusum_calibration.csv"
    df_emp_full = df_emp.merge(df_calib, on="tau", suffixes=("_empirical", "_calibration"))
    df_emp_full.to_csv(out_d, index=False)
    df_power.to_csv(out_c, index=False)
    print(f"\nwrote {out_d}\nwrote {out_c}")

    print("\n=== summary ===")
    print(df_emp[["tau", "n_weekends_oos", "h", "max_S_plus", "max_S_minus", "alarmed"]]
          .to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()
    print(df_power[["tau", "mu1_multiplier", "label", "detection_rate",
                    "median_latency", "mean_latency"]]
          .to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
