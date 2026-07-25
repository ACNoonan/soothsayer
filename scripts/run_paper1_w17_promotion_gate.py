"""
W17 — promotion gate: the W16 recommended config in the DEPLOYED setup.

W16 recommended a panel-specific split:

    weekend    W13 (triple_witching cell) + W14 (shrinkage, k=200)
    overnight  W15 (adaptive per-cell level, gamma=0.05)

Every W10-W16 arm suppressed delta and omitted the c(tau) bump, to isolate
one knob at a time. Before any of it can be promoted it has to survive the
configuration actually served.

Two findings simplify this gate:

  * delta is all-zero under M6 (`oracle.LWC_DELTA_SHIFT_SCHEDULE`), so
    "delta suppressed" was ALREADY the deployed configuration. That caveat
    dissolves rather than needing a test.
  * c(tau) is the only real difference. It is fitted OOS as the smallest
    c >= 1 reaching pooled coverage tau, so it can only widen.

That last property is why the gate matters. c(tau) is a single GLOBAL
scalar with no per-cell channel: it can repair pooled under-coverage, and
it cannot repair a conditional failure. If W13/W14/W15 were merely
compensating for something c(tau) also fixes, their per-regime gains
should evaporate here. If the gains are genuinely conditional, they should
survive with c(tau) close to its deployed near-identity values
(1.000, 1.000, 1.079, 1.003).

Arms per panel: deployed baseline vs the W16 recommendation, both with
c(tau) fitted independently, so neither is advantaged.

Outputs
-------
  reports/tables/w17_promotion_gate.csv
  reports/tables/w17_promotion_gate_by_regime.csv
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
K_SHRINK, GAMMA = 200.0, 0.05
M_FLOOR, M_CEIL = 0.25, 4.0

# (label, triple_witching cell, shrinkage, adaptive)
ARMS = {
    "weekend": [("deployed", False, False, False),
                ("W16 rec (W13+W14)", True, True, False)],
    "overnight": [("deployed", False, False, False),
                  ("W16 rec (W15)", False, False, True)],
}


def is_triple_witching(d: date) -> bool:
    return d.month in (3, 6, 9, 12) and d.weekday() == 4 and 15 <= d.day <= 21


def _cp_q(s: np.ndarray, tau: float) -> float:
    s = np.sort(s[np.isfinite(s)])
    if s.size == 0:
        return float("nan")
    k = min(max(int(np.ceil(tau * (s.size + 1))), 1), s.size)
    return float(s[k - 1])


def _fit_c(score: np.ndarray, q_row: np.ndarray, tau: float) -> float:
    m = np.isfinite(score) & np.isfinite(q_row)
    s, b = score[m], q_row[m]
    if s.size == 0:
        return float("nan")
    for c in np.arange(1.0, 5.0001, 0.001):
        if float(np.mean(s <= b * c)) >= tau:
            return float(c)
    return 5.0


def main() -> None:
    rows, reg_rows = [], []

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
        w["tw"] = w["fri_ts"].map(is_triple_witching)

        score = w["score"].to_numpy(float)
        sig = w["sigma_hat_sym_pre_fri"].to_numpy(float)
        fri = w["fri_close"].to_numpy(float)
        point = w["point"].to_numpy(float)
        act = w["mon_open"].to_numpy(float)
        periods = w["fri_ts"].to_numpy()
        is_tr = (w["fri_ts"] < SPLIT_DATE).to_numpy()
        o = ~is_tr
        order = sorted(set(periods))
        idx_by_period = {p: np.where(periods == p)[0] for p in order}

        print(f"\n### {panel_name}: train {is_tr.sum():,} / oos {o.sum():,}",
              flush=True)

        for arm, use_tw, use_shrink, use_adapt in ARMS[panel_name]:
            cells = np.where(w["tw"].to_numpy() & use_tw,
                             "triple_witching", w["regime_pub"].to_numpy())
            uniq = np.unique(cells)
            tr_s = score[is_tr]
            q_pool = {t: _cp_q(tr_s, t) for t in DEFAULT_TAUS}
            med_pool = float(np.median(tr_s[np.isfinite(tr_s)]))
            q_cell, m_r, n_cell = {}, {}, {}
            for c in uniq:
                sc = score[is_tr & (cells == c)]
                q_cell[c] = {t: _cp_q(sc, t) for t in DEFAULT_TAUS}
                n_cell[c] = int(np.isfinite(sc).sum())
                m_r[c] = (float(np.median(sc[np.isfinite(sc)])) / med_pool
                          if n_cell[c] else 1.0)

            def base_q(c: str, t: float) -> float:
                if not use_shrink:
                    return q_cell[c][t]
                wt = n_cell[c] / (n_cell[c] + K_SHRINK)
                return wt * q_cell[c][t] + (1 - wt) * m_r[c] * q_pool[t]

            for tau in DEFAULT_TAUS:
                served = np.full(len(w), np.nan)
                mult = {c: 1.0 for c in uniq}
                for p in order:
                    ix = idx_by_period[p]
                    for i in ix:
                        served[i] = mult[cells[i]] * base_q(cells[i], tau)
                    if not use_adapt:
                        continue
                    hw_p = served[ix] * sig[ix] * fri[ix]
                    br = ((act[ix] < point[ix] - hw_p)
                          | (act[ix] > point[ix] + hw_p))
                    for c in np.unique(cells[ix]):
                        sel = cells[ix] == c
                        mult[c] = float(np.clip(
                            mult[c] * np.exp(
                                GAMMA * (float(br[sel].mean()) - (1 - tau))),
                            M_FLOOR, M_CEIL))

                # c(tau): fitted OOS per arm, exactly as the deployed path does
                c_bump = _fit_c(score[o], served[o], tau)
                hw = served * c_bump * sig * fri
                ins = (act >= point - hw) & (act <= point + hw)
                _, p_uc = met._lr_kupiec((~ins[o]).astype(int), tau)

                sym = 0
                for s in np.unique(w["symbol"]):
                    mm = o & (w["symbol"] == s).to_numpy()
                    _, ps = met._lr_kupiec((~ins[mm]).astype(int), tau)
                    sym += int(np.isfinite(ps) and ps >= 0.05)

                rp, rn = 0, 0
                for c in uniq:
                    mm = o & (cells == c)
                    if mm.sum() == 0:
                        continue
                    _, pr = met._lr_kupiec((~ins[mm]).astype(int), tau)
                    ok = int(np.isfinite(pr) and pr >= 0.05)
                    rp += ok; rn += 1
                    reg_rows.append({
                        "panel": panel_name, "arm": arm, "tau": tau,
                        "regime": c, "n": int(mm.sum()),
                        "realised": float(ins[mm].mean()),
                        "half_width_bps": float((hw[mm] / fri[mm] * 1e4).mean()),
                        "kupiec_p": float(pr), "kupiec_pass": ok,
                    })

                rows.append({
                    "panel": panel_name, "arm": arm, "tau": tau,
                    "c_bump": c_bump, "n": int(o.sum()),
                    "realised": float(ins[o].mean()),
                    "half_width_bps": float((hw[o] / fri[o] * 1e4).mean()),
                    "kupiec_p": float(p_uc),
                    "per_symbol_pass": sym, "per_symbol_n": 10,
                    "per_regime_pass": rp, "per_regime_n": rn,
                })
            print(f"   {arm} done", flush=True)

    d, dr = pd.DataFrame(rows), pd.DataFrame(reg_rows)
    t = REPORTS / "tables"; t.mkdir(parents=True, exist_ok=True)
    d.to_csv(t / "w17_promotion_gate.csv", index=False)
    dr.to_csv(t / "w17_promotion_gate_by_regime.csv", index=False)

    for pan, _ in PANELS:
        print("\n" + "=" * 104)
        print(f"{pan.upper()} — deployed configuration (delta=0 live, c(tau) fitted per arm)")
        print("=" * 104)
        v = d[d.panel == pan]
        print(v[["arm", "tau", "c_bump", "realised", "half_width_bps",
                 "kupiec_p", "per_symbol_pass", "per_regime_pass",
                 "per_regime_n"]]
              .to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        key = "triple_witching" if pan == "weekend" else "earnings_night"
        k = dr[(dr.panel == pan) & (dr.regime == key)]
        if not k.empty:
            print(f"\n  {key}:")
            print(k[["arm", "tau", "n", "realised", "half_width_bps",
                     "kupiec_p"]].to_string(index=False,
                                            float_format=lambda x: f"{x:.3f}"))
    print(f"\nWrote {t / 'w17_promotion_gate.csv'}")


if __name__ == "__main__":
    main()
