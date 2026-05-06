"""Paper 1 — Tier B item B3.

Kupiec power / minimum detectable effect (MDE) at τ ∈ {0.85, 0.95, 0.99},
pooled (N=1,730) and per-symbol (N=173).

The §6.4 paper headline includes per-symbol Kupiec at τ=0.99. With
N=173 OOS weekends and nominal violation rate 0.01, the expected
violation count per symbol is 1.73 — statistically thin. A reviewer will
ask: against what alternative is the per-symbol pass at τ=0.99
informative?

Method (per τ, per N):
  for each Δ ∈ {0.005, 0.010, 0.015, 0.020, 0.025, 0.030, 0.040, 0.050}:
      simulate K=10,000 datasets of N Bernoulli draws at p* = (1-τ) + Δ
                                                          (or p* = (1-τ) − Δ for under-coverage)
      compute Kupiec LR p-value at each draw
      power(Δ) = fraction of draws with p < 0.05

  MDE = smallest Δ with power ≥ 0.8

Direction: report both **two-sided** (test rejects in either direction)
and **one-sided over-coverage** (under-coverage in our setting since
violations are coverage misses; over-coverage = realised < nominal).

For τ=0.99 the binomial is highly discrete at small N, so we use exact
Monte Carlo with the same Kupiec LR formula as `metrics._lr_kupiec`.

Output:
  reports/tables/paper1_b3_kupiec_power_mde.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.config import REPORTS

NOMINAL_TAUS = (0.85, 0.95, 0.99)
SAMPLE_SIZES = {
    "pooled_N1730":     1730,
    "per_symbol_N173":  173,
}
DELTAS = (0.005, 0.010, 0.015, 0.020, 0.025, 0.030, 0.040, 0.050,
          0.075, 0.100)
N_REP = 10_000
ALPHA = 0.05
RNG = np.random.default_rng(20260506)
TARGET_POWER = 0.8


def kupiec_power(tau: float, n: int, p_alt: float, n_rep: int) -> float:
    """Fraction of simulated samples where Kupiec LR rejects H0:p=(1-tau)
    at α=0.05, when the true violation prob is p_alt."""
    n_violations = RNG.binomial(n=n, p=p_alt, size=n_rep)
    n_reject = 0
    nominal = 1.0 - tau
    # Build Kupiec LR vectorised
    # _lr_kupiec uses violations array; we just need (n_v, n) → LR
    # Reproduce metrics._lr_kupiec inline (vectorised):
    # Actually the metric takes the binary array — for power we just need n_v.
    # _lr_kupiec(violations, claimed): violations is array; n = len; m = sum
    # LR_uc = -2 ( m·ln(α/(m/n)) + (n-m)·ln((1-α)/((n-m)/n)) )
    # if m==0 or m==n, the standard p̂ → boundary handling:
    n_v = n_violations
    m = n_v
    n_arr = np.full(n_rep, n)
    p_hat = m / n_arr
    # Kupiec: -2(LL_null - LL_unrestricted)
    # = -2[m ln(α) + (n-m) ln(1-α) - m ln(p̂) - (n-m) ln(1-p̂)]
    #   when 0 < m < n
    eps = 1e-12
    p_hat_safe = np.clip(p_hat, eps, 1 - eps)
    ll_null = m * np.log(nominal) + (n_arr - m) * np.log(1 - nominal)
    ll_alt  = m * np.log(p_hat_safe) + (n_arr - m) * np.log(1 - p_hat_safe)
    lr = -2.0 * (ll_null - ll_alt)
    lr = np.maximum(lr, 0.0)
    # Boundary: when m=0, LL_alt → 0; when m=n, also handled by clip
    # Compare to χ²(1) critical: 3.841 at α=0.05
    crit = 3.841
    n_reject = int(np.sum(lr > crit))
    return n_reject / n_rep


def find_mde(tau: float, n: int, target_power: float = TARGET_POWER,
             direction: str = "two_sided") -> dict:
    """Find smallest Δ such that power ≥ target_power.

    direction:
      'over_violations' — true p = nominal + Δ (more violations than nominal,
                          i.e. UNDER-coverage)
      'under_violations' — true p = nominal − Δ (fewer violations, i.e.
                            OVER-coverage)
      'two_sided' — uses max of the two
    """
    nominal = 1.0 - tau
    rows = []
    for delta in DELTAS:
        if direction == "over_violations":
            p_alt = nominal + delta
            pwr = kupiec_power(tau, n, p_alt, N_REP)
        elif direction == "under_violations":
            p_alt = max(nominal - delta, 1e-6)
            pwr = kupiec_power(tau, n, p_alt, N_REP)
        else:  # two_sided
            pwr_o = kupiec_power(tau, n, nominal + delta, N_REP)
            pwr_u = kupiec_power(tau, n,
                                  max(nominal - delta, 1e-6), N_REP)
            pwr = max(pwr_o, pwr_u)
        rows.append({"delta": delta, "power": pwr})
    df = pd.DataFrame(rows)
    qualifying = df[df["power"] >= target_power]
    mde = float(qualifying["delta"].min()) if len(qualifying) else float("nan")
    return {"mde": mde, "power_table": df}


def main() -> None:
    rows = []
    print(f"Kupiec power simulation: K={N_REP:,} reps, α={ALPHA}, "
          f"target power {TARGET_POWER:.0%}", flush=True)
    for tau in NOMINAL_TAUS:
        for sample_name, n in SAMPLE_SIZES.items():
            for direction in ("over_violations", "under_violations"):
                res = find_mde(tau, n, direction=direction)
                pt = res["power_table"]
                row = {
                    "tau": tau,
                    "sample": sample_name,
                    "n": n,
                    "expected_violations_under_null": (1 - tau) * n,
                    "direction": direction,
                    "mde": res["mde"],
                }
                # Capture power at each delta
                for d, p in zip(pt["delta"], pt["power"]):
                    row[f"power_at_delta_{d:.4f}"] = float(p)
                rows.append(row)
                print(f"τ={tau} {sample_name:18s} {direction:18s}: "
                      f"MDE = {res['mde']:.4f} (~{res['mde']*100:.2f} pp)",
                      flush=True)

    df = pd.DataFrame(rows)
    out_path = REPORTS / "tables" / "paper1_b3_kupiec_power_mde.csv"
    df.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}", flush=True)

    # Summary table — focus on key questions
    print("\n=== headline MDE (one-sided, under-coverage = excess violations) ===")
    sub = df[df["direction"] == "over_violations"][[
        "tau", "sample", "n", "expected_violations_under_null", "mde"
    ]]
    print(sub.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n=== headline MDE (one-sided, over-coverage = fewer violations) ===")
    sub = df[df["direction"] == "under_violations"][[
        "tau", "sample", "n", "expected_violations_under_null", "mde"
    ]]
    print(sub.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
