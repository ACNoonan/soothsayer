"""
W11 — proxy-reliance exponent ρ sweep (Zhong, arXiv:2603.22569).

Zhong parameterises the exponent on the volatility proxy in the nonconformity
score, interpolating between an additive shift and a fully proxy-scaled
correction:

    u_s^(ρ) = (Y_s − q̂_s) / v_s^ρ ,     ρ ∈ [0, 1]

and reports that *intermediate* ρ is more robust when the proxy underreacts
in stress. Our deployed score sits at ρ = 1 (fully σ̂-scaled); the §7.1
constant-buffer comparator sits at ρ ≈ 0. So §7 ablates both endpoints of
Zhong's axis and none of its interior — and the choice of ρ = 1 was never
considered, let alone justified. A reader of Zhong asks about it immediately.

Construction — only the exponent moves:

    score_ρ = |mon_open − point| / (fri_close · σ̂^ρ)
    half    = q_r(τ) · σ̂^ρ · fri_close

ρ = 1 reproduces the deployed architecture exactly; ρ = 0 is a per-regime
quantile on the unstandardised relative residual (the §7.2 unweighted-Mondrian
comparator). Everything else is held fixed: same panel, point estimator,
Mondrian cells, split, finite-sample rank formula. δ suppressed and no c(τ)
bump on any arm, so no arm can be rescued by a fitted correction.

Run on both off-hours panels. The overnight panel uses the de-contaminated σ̂
(earnings residuals excluded from the scale pool) — omitting that mask
inflates σ̂ ~32% on GOOGL and ~23% on NVDA and would confound the sweep.

Zhong's stress claim is tested directly: per-regime coverage is reported, so
if intermediate ρ helps anywhere it should show in `high_vol`.

Outputs
-------
  reports/tables/w11_rho_sweep.csv
  reports/tables/w11_rho_sweep_by_regime.csv
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
RHOS = (0.0, 0.25, 0.5, 0.75, 1.0)


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
        w = w[(w["sigma_hat_sym_pre_fri"] > 0)
              & w["mon_open"].notna()].reset_index(drop=True)

        abs_rel = ((w["mon_open"] - w["point"]).abs()
                   / w["fri_close"]).to_numpy(float)
        sig = w["sigma_hat_sym_pre_fri"].to_numpy(float)
        fri = w["fri_close"].to_numpy(float)
        point = w["point"].to_numpy(float)
        act = w["mon_open"].to_numpy(float)
        cells = w["regime_pub"].to_numpy()
        is_tr = (w["fri_ts"] < SPLIT_DATE).to_numpy()
        is_oos = ~is_tr

        print(f"\n### {panel_name}: train {is_tr.sum():,} / oos {is_oos.sum():,}",
              flush=True)

        for rho in RHOS:
            scale = sig ** rho                    # σ̂^ρ ; ρ=0 -> 1.0
            score = abs_rel / scale
            qt = {c: {t: _cp_q(score[is_tr & (cells == c)], t)
                      for t in DEFAULT_TAUS}
                  for c in np.unique(cells)}

            for tau in DEFAULT_TAUS:
                q = np.array([qt[c][tau] for c in cells], dtype=float)
                hw = q * scale * fri
                ins = (act >= point - hw) & (act <= point + hw)
                o = is_oos
                _, p_uc = met._lr_kupiec((~ins[o]).astype(int), tau)

                sym = 0
                for s in np.unique(w["symbol"]):
                    m = o & (w["symbol"] == s).to_numpy()
                    _, ps = met._lr_kupiec((~ins[m]).astype(int), tau)
                    sym += int(np.isfinite(ps) and ps >= 0.05)

                rp, rn = 0, 0
                for c in np.unique(cells):
                    m = o & (cells == c)
                    _, pr = met._lr_kupiec((~ins[m]).astype(int), tau)
                    ok = int(np.isfinite(pr) and pr >= 0.05)
                    rp += ok; rn += 1
                    reg_rows.append({
                        "panel": panel_name, "rho": rho, "tau": tau,
                        "regime": c, "n": int(m.sum()),
                        "realised": float(ins[m].mean()),
                        "half_width_bps": float((hw[m] / fri[m] * 1e4).mean()),
                        "kupiec_p": float(pr), "kupiec_pass": ok,
                    })

                rows.append({
                    "panel": panel_name, "rho": rho, "tau": tau,
                    "n": int(o.sum()),
                    "realised": float(ins[o].mean()),
                    "half_width_bps": float((hw[o] / fri[o] * 1e4).mean()),
                    "kupiec_p": float(p_uc),
                    "per_symbol_pass": sym, "per_symbol_n": 10,
                    "per_regime_pass": rp, "per_regime_n": rn,
                })
            print(f"   ρ={rho:.2f} done", flush=True)

    d, dr = pd.DataFrame(rows), pd.DataFrame(reg_rows)
    t = REPORTS / "tables"; t.mkdir(parents=True, exist_ok=True)
    d.to_csv(t / "w11_rho_sweep.csv", index=False)
    dr.to_csv(t / "w11_rho_sweep_by_regime.csv", index=False)

    for pan, _ in PANELS:
        print("\n" + "=" * 100)
        print(f"{pan.upper()} — ρ sweep (ρ=1 is deployed; ρ=0 is unweighted)")
        print("=" * 100)
        v = d[d.panel == pan]
        print(v.pivot_table(index="rho", columns="tau",
                            values=["half_width_bps", "per_symbol_pass",
                                    "per_regime_pass"])
              .to_string(float_format=lambda x: f"{x:.2f}"))
        print(f"\n  high_vol coverage by ρ (Zhong's stress claim):")
        hv = dr[(dr.panel == pan) & (dr.regime == "high_vol")]
        print(hv.pivot_table(index="rho", columns="tau",
                             values=["realised", "half_width_bps"])
              .to_string(float_format=lambda x: f"{x:.3f}"))

    print(f"\nWrote {t / 'w11_rho_sweep.csv'}")


if __name__ == "__main__":
    main()
