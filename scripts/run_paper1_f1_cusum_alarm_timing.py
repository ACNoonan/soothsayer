"""Paper 1 — Tier D item F1.

CUSUM empirical OOS alarm timing — when do the alarms fire, and do they
cluster on known stress windows?

C2 found that the calibrated CUSUM at h ∈ {0.40, 0.40, 0.30} for τ ∈
{0.85, 0.95, 0.99} alarms on the empirical OOS slice at all three τ. The
H0 false-alarm envelope over 173 weekends is ~53 %, so an alarm in
isolation is not statistically remarkable. But if the alarms cluster
around the same dates — and especially around known stress windows
(2024-08-05 BoJ unwind, 2025-04 tariff weekend) — that's a coherent
"monitor caught real transient stress" claim. If they scatter, that's
the H0 envelope.

This script:
  1. Re-runs the calibrated CUSUM on the empirical OOS series (single
     trace per τ; uses calibrated h from C2 directly).
  2. Identifies *all* threshold crossings (not just the first), since
     the first alarm in C2 stops at the first crossing.
  3. Reports alarm dates per τ + max S+ / S- trajectories.
  4. Cross-references with notable weekends:
       2023-03-10 (SVB collapse weekend)
       2024-08-02/05 (BoJ unwind)
       2025-04-04/07 (Trump tariff weekend)
  5. Computes pairwise alarm-date correlation across τ — if all three τ
     alarm in the same week, that's a coherent stress signal.

Output:
  reports/tables/paper1_f1_cusum_alarm_timing.csv
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
# Calibrated thresholds from C2 (paper1_c2_cusum_drift.csv)
CALIBRATED_H = {0.85: 0.400, 0.95: 0.400, 0.99: 0.300}

# Notable stress windows (Friday or Monday boundary; adjacent ±1 weekend
# qualifies as "near"-stress).
NOTABLE_WINDOWS = {
    "2023-03-SVB-collapse":     date(2023, 3, 10),   # Fri close before SVB seizure
    "2023-03-CS-takeover":      date(2023, 3, 17),
    "2023-10-Israel-war":       date(2023, 10,  6),  # 10/7 attack
    "2024-08-BoJ-unwind":       date(2024, 8,  2),   # Fri before 8/5 crash
    "2025-04-tariff-weekend":   date(2025, 4,  4),   # tariff escalation
    "2025-04-tariff-pause":     date(2025, 4, 11),
}


def cusum_full_trajectory(x: np.ndarray, mu0: float, k: float, h: float):
    n = len(x)
    s_pos = np.zeros(n + 1)
    s_neg = np.zeros(n + 1)
    alarms = []
    in_alarm = False
    for t in range(n):
        s_pos[t + 1] = max(0.0, s_pos[t] + (x[t] - mu0 - k))
        s_neg[t + 1] = max(0.0, s_neg[t] - (x[t] - mu0 + k))
        crossed = (s_pos[t + 1] >= h) or (s_neg[t + 1] >= h)
        if crossed and not in_alarm:
            alarms.append({
                "t": t + 1,
                "side": "S+" if s_pos[t + 1] >= h else "S-",
                "S_pos_at_alarm": float(s_pos[t + 1]),
                "S_neg_at_alarm": float(s_neg[t + 1]),
            })
            in_alarm = True
        elif not crossed and in_alarm:
            in_alarm = False  # reset alarm gate after crossing back below h
    return s_pos[1:], s_neg[1:], alarms


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

    # weekend index → fri_ts (sorted)
    weekend_dates = sorted(oos["fri_ts"].unique())
    fri_ts_arr = np.array(weekend_dates)
    print(f"OOS slice: {len(weekend_dates)} weekends "
          f"({weekend_dates[0]} → {weekend_dates[-1]})", flush=True)

    all_rows = []
    trajectories = {}
    for tau in HEADLINE_TAUS:
        mu0 = 1.0 - tau
        k = mu0 / 2.0
        h = CALIBRATED_H[tau]
        c = cb[tau]
        b_per_row = np.array(
            [qt.get(cells[i], {}).get(tau, np.nan) for i in range(len(oos))],
            dtype=float,
        )
        valid = base_valid & np.isfinite(b_per_row)
        sub = oos[valid].copy()
        sub["score"] = score[valid]
        sub["b_eff"] = b_per_row[valid] * c
        sub["viol"] = (sub["score"] > sub["b_eff"]).astype(int)
        # Per-weekend k_w / 10
        kw_per_w = sub.groupby("fri_ts")["viol"].sum().reindex(weekend_dates, fill_value=0) / 10.0
        x_emp = kw_per_w.to_numpy(float)

        s_pos, s_neg, alarms = cusum_full_trajectory(x_emp, mu0, k, h)
        trajectories[tau] = {"s_pos": s_pos, "s_neg": s_neg, "k_w_div_10": x_emp}
        print(f"\n=== τ = {tau} (h = {h:.3f}, k = {k:.4f}) ===")
        print(f"  number of distinct alarm episodes: {len(alarms)}")
        for a in alarms:
            d = fri_ts_arr[a["t"] - 1]
            kw_at_alarm = int(round(x_emp[a["t"] - 1] * 10))
            print(f"    t={a['t']:3d}  fri_ts={d}  side={a['side']:2s}  "
                  f"S+={a['S_pos_at_alarm']:.3f}  S-={a['S_neg_at_alarm']:.3f}  "
                  f"k_w={kw_at_alarm}")
            all_rows.append({"tau": tau, "alarm_t": a["t"],
                             "alarm_fri_ts": d.isoformat(),
                             "side": a["side"],
                             "S_pos_at_alarm": a["S_pos_at_alarm"],
                             "S_neg_at_alarm": a["S_neg_at_alarm"],
                             "kw_at_alarm": kw_at_alarm,
                             "h": h})

    df = pd.DataFrame(all_rows)
    out = REPORTS / "tables" / "paper1_f1_cusum_alarm_timing.csv"
    df.to_csv(out, index=False)
    print(f"\nwrote {out}")

    # Cross-reference with known stress windows: which τ alarms within 2
    # weekends of each stress window?
    print("\n=== alarm proximity to known stress windows ===")
    proximity_rows = []
    for stress_label, stress_date in NOTABLE_WINDOWS.items():
        for tau in HEADLINE_TAUS:
            sub = df[df["tau"] == tau]
            min_dist = float("inf")
            closest_alarm = None
            for _, r in sub.iterrows():
                ad = pd.Timestamp(r["alarm_fri_ts"]).date()
                d = abs((ad - stress_date).days) / 7.0
                if d < min_dist:
                    min_dist = d
                    closest_alarm = ad
            proximity_rows.append({
                "stress_label": stress_label,
                "stress_date": stress_date.isoformat(),
                "tau": tau,
                "closest_alarm_date": closest_alarm.isoformat() if closest_alarm else None,
                "weekends_distance": float(min_dist) if min_dist < float("inf") else None,
            })
            mark = "✓" if min_dist <= 2 else " "
            print(f"  {mark}  τ={tau} {stress_label:30s} (stress {stress_date}): "
                  f"closest alarm at {closest_alarm} "
                  f"(Δ={min_dist:.1f} weekends)")

    out2 = REPORTS / "tables" / "paper1_f1_cusum_alarm_proximity.csv"
    pd.DataFrame(proximity_rows).to_csv(out2, index=False)
    print(f"\nwrote {out2}")

    # Pairwise alarm-date overlap: how many alarms are within 2 weekends
    # of each other across τ?
    print("\n=== pairwise τ alarm coincidence ===")
    coincidence_rows = []
    for i, tau_i in enumerate(HEADLINE_TAUS):
        for tau_j in HEADLINE_TAUS[i + 1:]:
            ai = df[df["tau"] == tau_i]["alarm_fri_ts"].apply(
                lambda x: pd.Timestamp(x).date()).tolist()
            aj = df[df["tau"] == tau_j]["alarm_fri_ts"].apply(
                lambda x: pd.Timestamp(x).date()).tolist()
            n_coincident = 0
            for d1 in ai:
                for d2 in aj:
                    if abs((d1 - d2).days) / 7.0 <= 2.0:
                        n_coincident += 1
                        break
            coincidence_rows.append({
                "tau_i": tau_i, "tau_j": tau_j,
                "n_alarms_i": len(ai), "n_alarms_j": len(aj),
                "n_coincident_within_2_weekends": n_coincident,
            })
            print(f"  τ={tau_i} vs τ={tau_j}: "
                  f"{len(ai)} & {len(aj)} alarms; "
                  f"{n_coincident} coincident within 2 weekends")
    pd.DataFrame(coincidence_rows).to_csv(
        REPORTS / "tables" / "paper1_f1_cusum_alarm_coincidence.csv", index=False
    )


if __name__ == "__main__":
    main()
