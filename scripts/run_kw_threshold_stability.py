"""
M6 Phase 8.3 — Cross-subperiod k_w threshold stability.

Phase 7.1 produced consumer reserve guidance ("at τ=0.95, reserve against
≈ 5 simultaneous breaches"). That guidance is a one-shot empirical
observation. A consumer sizing reserves needs to know the threshold is
stable across regimes; if the empirical 95th-percentile of `k_w` jumped
from k=3 in 2023 to k=7 in 2025, the guidance would be unreliable.

This runner piggybacks on Phase 7.2's calendar sub-periods. For each
forecaster × τ ∈ {0.85, 0.95, 0.99}:

  1. Fit `k*` on the *full* OOS slice (the threshold is fitted once,
     globally — never per-subperiod, which would be tautological).
  2. For each subperiod {2023, 2024, 2025, 2026-YTD}: realised hit
     rate of `P(k_w ≥ k*)`, Kupiec test against the *full-OOS rate*
     (NOT against 0.05 — the test is for stability, not for nominal
     calibration), and the per-subperiod empirical 95th-percentile of
     k_w (so cross-period drift in the threshold itself is visible).

Two threshold conventions are reported:
  - `k_close`: smallest k whose full-OOS rate is closest to 0.05
    (primary; better test power)
  - `k_below`: smallest k whose full-OOS rate is ≤ 0.05 (conservative
    deployment-recommended threshold; lower test power)

Output
------
  reports/tables/m6_kw_threshold_stability.csv

Run
---
  uv run python -u scripts/run_kw_threshold_stability.py
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.config import REPORTS

FORECASTERS = ("m5", "lwc")
TAUS = (0.85, 0.95, 0.99)
N_PANEL = 10
TARGET_RATE = 0.05
LOW_POWER_EXPECTED_HITS = 3.0   # subperiod-binomial-test power rule-of-thumb

# Calendar subperiods (matching Phase 7.2).
SUBPERIODS: tuple[tuple[str, date, date], ...] = (
    ("2023",     date(2023, 1, 1), date(2024, 1, 1)),
    ("2024",     date(2024, 1, 1), date(2025, 1, 1)),
    ("2025",     date(2025, 1, 1), date(2026, 1, 1)),
    ("2026-YTD", date(2026, 1, 1), date(2027, 1, 1)),
)


def select_thresholds(rates: dict[int, float]) -> tuple[int, int]:
    """Two threshold-selection conventions on the full-OOS hit-rate curve.

    `rates[k] = P(k_w ≥ k)` over the full OOS slice.
    Returns (k_below, k_close) where:
      - k_below = smallest k whose rate is ≤ 0.05 (deployment-conservative)
      - k_close = k whose rate is closest to 0.05, restricted to k where
        rate ≤ 0.5 (so we don't pick the trivial k=0 with rate=1.0)
    """
    valid = {k: r for k, r in rates.items() if r <= 0.5}
    k_below = min((k for k in valid if valid[k] <= TARGET_RATE), default=N_PANEL)
    k_close = min(valid.keys(), key=lambda k: abs(valid[k] - TARGET_RATE))
    return k_below, k_close


def main() -> None:
    weekly = pd.read_csv(REPORTS / "tables"
                         / "m6_portfolio_clustering_per_weekend.csv")
    weekly["fri_ts"] = pd.to_datetime(weekly["fri_ts"]).dt.date
    weekly = weekly[weekly["n_w"] == N_PANEL].reset_index(drop=True)

    rows: list[dict] = []

    for fc in FORECASTERS:
        for tau in TAUS:
            full = weekly[(weekly["forecaster"] == fc) &
                          (weekly["tau"].round(2) == round(tau, 2))]
            n_full = len(full)
            kw_full = full["k_w"].to_numpy()
            rates = {k: float((kw_full >= k).mean())
                     for k in range(N_PANEL + 1)}
            k_below, k_close = select_thresholds(rates)
            full_p95 = float(np.quantile(kw_full, 0.95))

            for k_label, k_star in (("close", k_close), ("below_5pct", k_below)):
                full_rate = rates[k_star]
                full_hits = int((kw_full >= k_star).sum())

                for label, lo, hi in SUBPERIODS:
                    sub = full[(full["fri_ts"] >= lo) &
                               (full["fri_ts"] < hi)]
                    n_sub = len(sub)
                    if n_sub == 0:
                        continue
                    kw_sub = sub["k_w"].to_numpy()
                    sub_hits = int((kw_sub >= k_star).sum())
                    sub_rate = float(sub_hits / n_sub)
                    sub_p95 = float(np.quantile(kw_sub, 0.95))
                    expected_hits = full_rate * n_sub
                    low_power = int(expected_hits < LOW_POWER_EXPECTED_HITS)

                    # Kupiec LR test: H0 subperiod rate = full_rate.
                    # `met._lr_kupiec(violations, claimed)` interprets
                    # `claimed` as a coverage level (it tests H0:
                    # viol_rate = 1 − claimed). We want H0: viol_rate =
                    # full_rate, so pass `claimed = 1 − full_rate`.
                    # Edge cases: if full_rate is 0 or 1 the test isn't
                    # well-defined; skip with NaN.
                    if 0.0 < full_rate < 1.0:
                        viol = (kw_sub >= k_star).astype(int)
                        lr, p = met._lr_kupiec(viol, 1.0 - full_rate)
                    else:
                        lr, p = float("nan"), float("nan")

                    rows.append({
                        "forecaster": fc,
                        "tau": float(tau),
                        "k_threshold_kind": k_label,   # "close" or "below_5pct"
                        "k_threshold": int(k_star),
                        "full_oos_n": int(n_full),
                        "full_oos_hits": full_hits,
                        "full_oos_rate": float(full_rate),
                        "full_oos_p95_kw": full_p95,
                        "subperiod": label,
                        "subperiod_n": int(n_sub),
                        "subperiod_hits": sub_hits,
                        "subperiod_rate": sub_rate,
                        "subperiod_p95_kw": sub_p95,
                        "kupiec_lr": float(lr),
                        "kupiec_p": float(p),
                        "expected_hits": float(expected_hits),
                        "low_power_flag": low_power,
                    })

    out = pd.DataFrame(rows)
    out_path = REPORTS / "tables" / "m6_kw_threshold_stability.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}", flush=True)
    print(f"  rows: {len(out)}  "
          f"(2 forecasters × 3 τ × 2 thresholds × 4 subperiods = 48)",
          flush=True)

    # ---------------------------- console summary
    print("\n" + "=" * 100)
    print("HEADLINE — primary threshold k* (full-OOS rate closest to 5%)")
    print("=" * 100)
    head = out[out["k_threshold_kind"] == "close"][[
        "forecaster", "tau", "k_threshold", "full_oos_rate",
        "subperiod", "subperiod_rate", "subperiod_p95_kw",
        "kupiec_p", "low_power_flag",
    ]]
    print(head.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # Per (forecaster × τ) stability summary
    print("\n" + "=" * 100)
    print("CROSS-SUBPERIOD STABILITY — Kupiec rejection counts at α=0.05 "
          "(out of 4 subperiods)")
    print("=" * 100)
    for kind in ("close", "below_5pct"):
        print(f"\n  threshold convention: {kind}")
        for fc in FORECASTERS:
            for tau in TAUS:
                cells = out[(out["forecaster"] == fc) &
                            (out["tau"].round(2) == round(tau, 2)) &
                            (out["k_threshold_kind"] == kind)]
                k_star = int(cells["k_threshold"].iloc[0])
                n_rej = int(((cells["kupiec_p"] < 0.05) &
                             (~cells["kupiec_p"].isna())).sum())
                low_power_count = int(cells["low_power_flag"].sum())
                print(f"    {fc:>3s}  τ={tau:.2f}  k*={k_star:>2d}  "
                      f"rejections {n_rej}/4  "
                      f"(low-power cells: {low_power_count}/4)")

    print("\n" + "=" * 100)
    print("PER-SUBPERIOD k_w 95th-PERCENTILE — drift visibility")
    print("=" * 100)
    drift = out[out["k_threshold_kind"] == "close"][[
        "forecaster", "tau", "subperiod", "subperiod_p95_kw",
    ]].drop_duplicates()
    drift_pivot = drift.pivot_table(
        index=["forecaster", "tau"], columns="subperiod",
        values="subperiod_p95_kw",
    )
    print(drift_pivot.to_string(float_format=lambda x: f"{x:.1f}"))


if __name__ == "__main__":
    main()
