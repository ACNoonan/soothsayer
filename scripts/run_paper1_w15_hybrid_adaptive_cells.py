"""
W15 — hybrid: frozen Mondrian cells with an adaptive level inside each cell.

The idea comes straight out of W10 + W12:

  W10 — online conformal (ACI/DtACI/PI) is *sharper* than the deployed band,
        but fails conditional coverage catastrophically: overnight
        `earnings_night` 0.317–0.383 against a claimed 0.95, because an
        adaptive learner converges a *global* level and has no channel to
        widen for a scheduled event it has not yet observed.
  W12 — the Mondrian partition IS that channel, and it is load-bearing:
        deployed realises 0.983 on the same cell.

So take the partition from one and the adaptation from the other. Keep the
per-regime quantile q_r(τ) — the conditional channel — and let only the
*level within each cell* drift:

    half_{r,t} = m_{r,t} · q_r(τ) · σ̂_s(t) · fri_close
    m_{r,t+1}  = m_{r,t} · exp( γ · (err_{r,t} − (1−τ)) )

where err_{r,t} is the realised breach fraction in cell r at period t. Too
many breaches raises m (wider); too few lowers it. m is warmed up on the
training period and starts at 1.0, so γ = 0 reproduces the deployed band
exactly.

Why this is verifiable, which is the whole point of the primitive: the state
is **one scalar per regime cell** — three or four numbers — with a
deterministic update over public prices. Published in the receipt and
checkpointed periodically, a consumer verifies any single read in one step
against the published m, and replays only since the last checkpoint to audit
the state itself. That is the "aggregate the equation so it is more easily
verified" shape, and it is why the O(t)-replay objection to full online
conformal does not apply here.

Arms: deployed (γ=0) plus γ ∈ {0.02, 0.05, 0.10}. Both off-hours panels,
de-contaminated σ̂ overnight, δ suppressed, no c(τ) bump on any arm.

Outputs
-------
  reports/tables/w15_hybrid_adaptive_cells.csv
  reports/tables/w15_hybrid_adaptive_cells_by_regime.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS, prep_panel_for_forecaster,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
SIGMA_EXCL = {"weekend": None, "overnight": "earnings_next_week"}
PANELS = [("weekend", "v1b_panel"), ("overnight", "overnight_panel")]
GAMMAS = (0.0, 0.02, 0.05, 0.10)
M_FLOOR, M_CEIL = 0.25, 4.0     # keep one bad period from destroying the band


def _cp_q(s: np.ndarray, tau: float) -> float:
    s = np.sort(s[np.isfinite(s)])
    if s.size == 0:
        return float("nan")
    k = min(max(int(np.ceil(tau * (s.size + 1))), 1), s.size)
    return float(s[k - 1])


def main() -> None:
    rows, reg_rows, traj = [], [], []

    for panel_name, fname in PANELS:
        raw = pd.read_parquet(DATA_PROCESSED / f"{fname}.parquet")
        raw["fri_ts"] = pd.to_datetime(raw["fri_ts"]).dt.date
        raw = raw.dropna(subset=["mon_open", "fri_close", "regime_pub",
                                 "factor_ret"]).reset_index(drop=True)
        raw["regime_pub"] = raw["regime_pub"].astype(str)

        w = prep_panel_for_forecaster(
            raw, "lwc", sigma_exclude_mask_col=SIGMA_EXCL[panel_name])
        w["point"] = w["fri_close"] * (1.0 + w["factor_ret"])
        w = (w[(w["sigma_hat_sym_pre_fri"] > 0) & w["score"].notna()]
             .sort_values(["fri_ts", "symbol"]).reset_index(drop=True))

        score = w["score"].to_numpy(float)
        sig = w["sigma_hat_sym_pre_fri"].to_numpy(float)
        fri = w["fri_close"].to_numpy(float)
        point = w["point"].to_numpy(float)
        act = w["mon_open"].to_numpy(float)
        cells = w["regime_pub"].to_numpy()
        periods = w["fri_ts"].to_numpy()
        is_tr = (w["fri_ts"] < SPLIT_DATE).to_numpy()

        qt = {c: {t: _cp_q(score[is_tr & (cells == c)], t) for t in DEFAULT_TAUS}
              for c in np.unique(cells)}
        order = sorted(set(periods))
        idx_by_period = {p: np.where(periods == p)[0] for p in order}

        print(f"\n### {panel_name}: {len(w):,} rows · {len(order)} periods",
              flush=True)

        for gamma in GAMMAS:
            for tau in DEFAULT_TAUS:
                target_breach = 1.0 - tau
                m = {c: 1.0 for c in np.unique(cells)}
                served_q = np.full(len(w), np.nan)

                for p in order:
                    ix = idx_by_period[p]
                    for i in ix:                      # serve with current m
                        served_q[i] = m[cells[i]] * qt[cells[i]][tau]
                    if gamma == 0.0:
                        continue
                    hw_p = served_q[ix] * sig[ix] * fri[ix]
                    br = (act[ix] < point[ix] - hw_p) | (act[ix] > point[ix] + hw_p)
                    for c in np.unique(cells[ix]):    # update per cell present
                        sel = cells[ix] == c
                        err = float(br[sel].mean())
                        m[c] = float(np.clip(
                            m[c] * np.exp(gamma * (err - target_breach)),
                            M_FLOOR, M_CEIL))

                hw = served_q * sig * fri
                ins = (act >= point - hw) & (act <= point + hw)
                o = ~is_tr
                _, p_uc = met._lr_kupiec((~ins[o]).astype(int), tau)

                sym = 0
                for s in np.unique(w["symbol"]):
                    mm = o & (w["symbol"] == s).to_numpy()
                    _, ps = met._lr_kupiec((~ins[mm]).astype(int), tau)
                    sym += int(np.isfinite(ps) and ps >= 0.05)

                rp, rn = 0, 0
                for c in np.unique(cells):
                    mm = o & (cells == c)
                    _, pr = met._lr_kupiec((~ins[mm]).astype(int), tau)
                    ok = int(np.isfinite(pr) and pr >= 0.05)
                    rp += ok; rn += 1
                    reg_rows.append({
                        "panel": panel_name, "gamma": gamma, "tau": tau,
                        "regime": c, "n": int(mm.sum()),
                        "realised": float(ins[mm].mean()),
                        "half_width_bps": float((hw[mm] / fri[mm] * 1e4).mean()),
                        "kupiec_p": float(pr), "kupiec_pass": ok,
                        "final_m": m[c],
                    })

                rows.append({
                    "panel": panel_name, "gamma": gamma, "tau": tau,
                    "n": int(o.sum()),
                    "realised": float(ins[o].mean()),
                    "half_width_bps": float((hw[o] / fri[o] * 1e4).mean()),
                    "kupiec_p": float(p_uc),
                    "per_symbol_pass": sym, "per_symbol_n": 10,
                    "per_regime_pass": rp, "per_regime_n": rn,
                })
                if tau == 0.95:
                    traj.append({"panel": panel_name, "gamma": gamma,
                                 **{f"m_{c}": m[c] for c in sorted(m)}})
            print(f"   γ={gamma:.2f} done", flush=True)

    d, dr = pd.DataFrame(rows), pd.DataFrame(reg_rows)
    t = REPORTS / "tables"; t.mkdir(parents=True, exist_ok=True)
    d.to_csv(t / "w15_hybrid_adaptive_cells.csv", index=False)
    dr.to_csv(t / "w15_hybrid_adaptive_cells_by_regime.csv", index=False)

    for pan, _ in PANELS:
        print("\n" + "=" * 100)
        print(f"{pan.upper()} — hybrid (γ=0 is deployed/frozen)")
        print("=" * 100)
        v = d[d.panel == pan]
        print(v.pivot_table(index="gamma", columns="tau",
                            values=["half_width_bps", "per_symbol_pass",
                                    "per_regime_pass"])
              .to_string(float_format=lambda x: f"{x:.2f}"))
        key = "earnings_night" if pan == "overnight" else "high_vol"
        print(f"\n  {key} coverage @ τ=0.95 (the conditional channel):")
        k = dr[(dr.panel == pan) & (dr.regime == key) & (dr.tau == 0.95)]
        print(k[["gamma", "n", "realised", "half_width_bps", "kupiec_p",
                 "final_m"]].to_string(index=False,
                                       float_format=lambda x: f"{x:.3f}"))
    print(f"\n  final per-cell multipliers @ τ=0.95:")
    print(pd.DataFrame(traj).to_string(index=False,
                                       float_format=lambda x: f"{x:.3f}"))
    print(f"\nWrote {t / 'w15_hybrid_adaptive_cells.csv'}")


if __name__ == "__main__":
    main()
