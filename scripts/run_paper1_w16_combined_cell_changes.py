"""
W16 — W13 + W14 + W15 evaluated together.

Three separate experiments each modify the per-cell conformal quantile, and
each was tested in isolation. They cannot be promoted independently:

  W13  add a `triple_witching` cell (weekend). Found a live 0.869-vs-0.95
       coverage hole and closed most of it; also tightened `normal` 6%.
  W14  m_r-rescaled shrinkage toward the pooled shape,
       q = w·q_cell + (1−w)·m_r·q_pooled, w = n/(n+k). Fixed the residual
       triple-witching miss at k≈200 (+1.3% width). Did nothing overnight.
  W15  adaptive per-cell level, m_{r,t+1} = m_{r,t}·exp(γ(err−(1−τ))).
       Fixed the earnings_night drift overnight (−15% width, Kupiec
       0.171→0.529). Inert on the weekend panel.

W14 already carried the W13 cell, so W13+W14 is co-tested. What is untested
is W15 layered on top of either — and there is a real reason to suspect
interference: shrinkage *stabilises* a thin cell's estimate toward a pooled
shape, while adaptation *moves* the level period by period. Applied to the
same thin cell they could fight, with the adaptive term chasing noise that
shrinkage was introduced to suppress.

Arms are the combinations that could actually ship, not a full factorial:

  weekend    base · +W13 · +W13+W14 · +W13+W15 · +W13+W14+W15
  overnight  base · +W14 · +W15 · +W14+W15          (no triple witching —
                                                     it is a weekend event)

Same panel, point estimator, split, rank formula throughout. δ suppressed
and no c(τ) on any arm. De-contaminated σ̂ overnight.

Outputs
-------
  reports/tables/w16_combined_cell_changes.csv
  reports/tables/w16_combined_cell_changes_by_regime.csv
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
K_SHRINK = 200.0        # W14 plateau
GAMMA = 0.05            # W15 plateau
M_FLOOR, M_CEIL = 0.25, 4.0

ARMS = {
    "weekend": [
        ("base",              False, False, False),
        ("W13",               True,  False, False),
        ("W13+W14",           True,  True,  False),
        ("W13+W15",           True,  False, True),
        ("W13+W14+W15",       True,  True,  True),
    ],
    "overnight": [
        ("base",              False, False, False),
        ("W14",               False, True,  False),
        ("W15",               False, False, True),
        ("W14+W15",           False, True,  True),
    ],
}


def is_triple_witching(d: date) -> bool:
    return d.month in (3, 6, 9, 12) and d.weekday() == 4 and 15 <= d.day <= 21


def _cp_q(s: np.ndarray, tau: float) -> float:
    s = np.sort(s[np.isfinite(s)])
    if s.size == 0:
        return float("nan")
    k = min(max(int(np.ceil(tau * (s.size + 1))), 1), s.size)
    return float(s[k - 1])


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
        order = sorted(set(periods))
        idx_by_period = {p: np.where(periods == p)[0] for p in order}

        print(f"\n### {panel_name}: {len(w):,} rows · {len(order)} periods",
              flush=True)

        for arm, use_tw, use_shrink, use_adapt in ARMS[panel_name]:
            cells = np.where(w["tw"].to_numpy() & use_tw,
                             "triple_witching",
                             w["regime_pub"].to_numpy())
            uniq = np.unique(cells)
            tr_scores = score[is_tr]
            q_pool = {t: _cp_q(tr_scores, t) for t in DEFAULT_TAUS}
            med_pool = float(np.median(tr_scores[np.isfinite(tr_scores)]))
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
                        err = float(br[sel].mean())
                        mult[c] = float(np.clip(
                            mult[c] * np.exp(GAMMA * (err - (1 - tau))),
                            M_FLOOR, M_CEIL))

                hw = served * sig * fri
                ins = (act >= point - hw) & (act <= point + hw)
                o = ~is_tr
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
                        "final_m": mult[c],
                    })

                rows.append({
                    "panel": panel_name, "arm": arm, "tau": tau,
                    "n": int(o.sum()),
                    "realised": float(ins[o].mean()),
                    "half_width_bps": float((hw[o] / fri[o] * 1e4).mean()),
                    "kupiec_p": float(p_uc),
                    "per_symbol_pass": sym, "per_symbol_n": 10,
                    "per_regime_pass": rp, "per_regime_n": rn,
                })
            print(f"   {arm} done", flush=True)

    d, dr = pd.DataFrame(rows), pd.DataFrame(reg_rows)
    t = REPORTS / "tables"; t.mkdir(parents=True, exist_ok=True)
    d.to_csv(t / "w16_combined_cell_changes.csv", index=False)
    dr.to_csv(t / "w16_combined_cell_changes_by_regime.csv", index=False)

    for pan, _ in PANELS:
        print("\n" + "=" * 104)
        print(f"{pan.upper()} — combined")
        print("=" * 104)
        v = d[d.panel == pan]
        print(v.pivot_table(index="arm", columns="tau", sort=False,
                            values=["half_width_bps", "per_symbol_pass",
                                    "per_regime_pass"])
              .to_string(float_format=lambda x: f"{x:.2f}"))
        key = "triple_witching" if pan == "weekend" else "earnings_night"
        k = dr[(dr.panel == pan) & (dr.regime == key)]
        if not k.empty:
            print(f"\n  {key} by arm and τ (realised / width):")
            print(k.pivot_table(index="arm", columns="tau", sort=False,
                                values=["realised", "half_width_bps"])
                  .to_string(float_format=lambda x: f"{x:.3f}"))
    print(f"\nWrote {t / 'w16_combined_cell_changes.csv'}")


if __name__ == "__main__":
    main()
