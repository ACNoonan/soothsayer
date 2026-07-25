"""
W4 — one-sided (downside) bands for the lending track.

Why
---
The deployed band is symmetric: the conformity score is |mon_open − point|
and the band is point ± q. But a lending protocol holding tokenised equity
as collateral is exposed to the **downside only**. A symmetric band at τ
puts (1−τ)/2 in each tail, so its lower edge is really a (1+τ)/2 one-sided
bound — a consumer wiring the τ = 0.95 band into loan-to-value is actually
provisioning to 97.5% and is over-collateralised relative to the number
they think they bought.

Both papers this work now positions against — Zhong (arXiv:2603.22569) and
Schmitt (arXiv:2602.03903) — calibrate **one-sided** VaR. The symmetric
choice is ours, not the literature's.

Two comparisons, because they answer different questions:

  (A) SAME LABEL.  one-sided@τ vs symmetric@τ. Quantifies the hidden
      conservatism a consumer is paying for today. Expected: symmetric
      realises ≈(1+τ)/2 downside coverage, not τ.

  (B) MATCHED DOWNSIDE COVERAGE.  one-sided@τ vs symmetric@(2τ−1) — both
      *claim* the same downside coverage. This is the honest capital
      comparison and asks whether a directly-fitted downside quantile
      beats an absolute-value quantile at the same protection level. If
      the gap distribution is skewed, it should; if it is symmetric, the
      two coincide and (A) is the whole story.

Scores (both σ̂-standardised, same Mondrian cells, same finite-sample rank
formula ceil(τ(n+1)) as the deployed path):

    score_sym  = |mon_open − point| / (fri_close · σ̂)
    score_down = (point − mon_open) / (fri_close · σ̂)      signed

`score_down` is positive when the realised price lands *below* the point
estimate, so its upper τ-quantile is exactly the downside buffer.

No c(τ) bump on either arm — it is an OOS-fit correction that would have
to be re-fit per arm and would confound the comparison. Both arms are the
raw split-conformal fit, so neither is advantaged.

Outputs
-------
  reports/tables/w4_one_sided_bands.csv         pooled, both panels
  reports/tables/w4_one_sided_by_symbol.csv     per-symbol
  reports/tables/w4_one_sided_by_regime.csv     per-regime

Run
---
  ./.venv/bin/python scripts/run_paper1_w4_one_sided_bands.py
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
# The overnight panel's σ̂ MUST exclude earnings residuals from the scale pool
# (build_overnight_panel.py builds it that way). prep_panel_for_forecaster
# recomputes σ̂, so omitting this silently substitutes a contaminated scale:
# +32% σ̂ on GOOGL, +23% on NVDA, over-widening every ordinary night.
SIGMA_EXCL = {"weekend": None, "overnight": "earnings_next_week"}
PANELS = [("weekend", "v1b_panel"), ("overnight", "overnight_panel")]


def _cp_quantile(scores: np.ndarray, tau: float) -> float:
    """Finite-sample split-CP quantile: rank ceil(τ(n+1)). Identical to
    `calibration.train_quantile_table`, restated so this runner does not
    depend on the absolute-value score assumption baked into that helper."""
    s = np.sort(scores[np.isfinite(scores)])
    n = s.size
    if n == 0:
        return float("nan")
    k = min(max(int(np.ceil(tau * (n + 1))), 1), n)
    return float(s[k - 1])


def _fit_cells(train: pd.DataFrame, score_col: str,
               taus: tuple[float, ...]) -> dict[str, dict[float, float]]:
    return {
        str(cell): {t: _cp_quantile(g[score_col].to_numpy(float), t) for t in taus}
        for cell, g in train.groupby("regime_pub")
    }


def _fit_c(scores: np.ndarray, q_per_row: np.ndarray, target: float) -> float:
    """Deployed c(τ) bump: smallest c on a 1.000–5.000 grid making OOS
    coverage reach `target`. Mirrors `calibration.fit_c_bump_schedule`.

    The grid starts at 1.0, so c can only *widen* — it repairs under-coverage
    and cannot manufacture a saving by narrowing. Applied to every arm so no
    arm is advantaged; without it the raw one-sided fit under-covers at low τ
    and its apparent capital saving is partly miscalibration rather than
    efficiency."""
    m = np.isfinite(scores) & np.isfinite(q_per_row)
    s, b = scores[m], q_per_row[m]
    if s.size == 0:
        return 5.0
    for c in np.arange(1.0, 5.0001, 0.001):
        if float(np.mean(s <= b * c)) >= target:
            return float(c)
    return 5.0


def _kupiec(breach: np.ndarray, target_cov: float) -> float:
    _, p = met._lr_kupiec(breach.astype(int), target_cov)
    return float(p)


def main() -> None:
    pooled, by_sym, by_reg = [], [], []

    for panel_name, fname in PANELS:
        raw = pd.read_parquet(DATA_PROCESSED / f"{fname}.parquet")
        raw["fri_ts"] = pd.to_datetime(raw["fri_ts"]).dt.date
        raw = raw.dropna(
            subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
        ).reset_index(drop=True)
        raw["regime_pub"] = raw["regime_pub"].astype(str)

        w = prep_panel_for_forecaster(
            raw, "lwc", sigma_exclude_mask_col=SIGMA_EXCL[panel_name])
        w["point"] = w["fri_close"] * (1.0 + w["factor_ret"])
        sig = w["sigma_hat_sym_pre_fri"].astype(float)
        denom = w["fri_close"].astype(float) * sig
        w["score_sym"] = (w["mon_open"] - w["point"]).abs() / denom
        w["score_down"] = (w["point"] - w["mon_open"]) / denom
        w = w.dropna(subset=["score_sym", "score_down"]).reset_index(drop=True)

        train = w[w["fri_ts"] < SPLIT_DATE]
        oos = w[w["fri_ts"] >= SPLIT_DATE].sort_values(
            ["fri_ts", "symbol"]).reset_index(drop=True)

        # Symmetric needs quantiles at both τ (same-label) and 2τ−1 (matched).
        sym_taus = tuple(sorted({*DEFAULT_TAUS,
                                 *[round(2 * t - 1, 4) for t in DEFAULT_TAUS
                                   if 2 * t - 1 > 0]}))
        q_sym = _fit_cells(train, "score_sym", sym_taus)
        q_down = _fit_cells(train, "score_down", DEFAULT_TAUS)

        cells = oos["regime_pub"].to_numpy()
        scale = (oos["sigma_hat_sym_pre_fri"].to_numpy(float)
                 * oos["fri_close"].to_numpy(float))
        point = oos["point"].to_numpy(float)
        actual = oos["mon_open"].to_numpy(float)
        fri = oos["fri_close"].to_numpy(float)

        print(f"\n### {panel_name}: train {len(train):,} / oos {len(oos):,}",
              flush=True)

        for tau in DEFAULT_TAUS:
            tau_m = round(2 * tau - 1, 4)
            arms = {
                "one_sided":      np.array([q_down[c][tau] for c in cells]),
                "symmetric_same": np.array([q_sym[c][tau] for c in cells]),
            }
            if tau_m > 0:
                arms["symmetric_matched"] = np.array(
                    [q_sym[c][tau_m] for c in cells])

            # c(τ)-corrected arms — the deployed pipeline, not a raw score swap.
            sd = oos["score_down"].to_numpy(float)
            ss = oos["score_sym"].to_numpy(float)
            arms["one_sided_c"] = arms["one_sided"] * _fit_c(
                sd, arms["one_sided"], tau)
            if tau_m > 0:
                arms["symmetric_matched_c"] = arms["symmetric_matched"] * _fit_c(
                    ss, arms["symmetric_matched"], tau_m)

            for arm, q in arms.items():
                lower = point - q * scale
                breach = actual < lower
                buffer_bps = (point - lower) / fri * 1e4
                # What downside coverage does this arm actually deliver?
                cov = float(1.0 - breach.mean())
                # The coverage it *claims*: one-sided and matched arms claim
                # τ; symmetric_same claims τ two-sided = (1+τ)/2 downside.
                claimed = (1.0 + tau) / 2.0 if arm == "symmetric_same" else tau

                sym_pass = 0
                for s in np.unique(oos["symbol"]):
                    m = (oos["symbol"] == s).to_numpy()
                    p = _kupiec(breach[m], claimed)
                    sym_pass += int(np.isfinite(p) and p >= 0.05)
                    by_sym.append({
                        "panel": panel_name, "tau": tau, "arm": arm,
                        "symbol": s, "n": int(m.sum()),
                        "downside_cov": float(1 - breach[m].mean()),
                        "claimed": claimed, "kupiec_p": p,
                        "buffer_bps": float(buffer_bps[m].mean()),
                    })

                reg_pass = 0
                regs = np.unique(cells)
                for r in regs:
                    m = cells == r
                    p = _kupiec(breach[m], claimed)
                    reg_pass += int(np.isfinite(p) and p >= 0.05)
                    by_reg.append({
                        "panel": panel_name, "tau": tau, "arm": arm,
                        "regime": r, "n": int(m.sum()),
                        "downside_cov": float(1 - breach[m].mean()),
                        "claimed": claimed, "kupiec_p": p,
                        "buffer_bps": float(buffer_bps[m].mean()),
                    })

                pooled.append({
                    "panel": panel_name, "tau": tau, "arm": arm,
                    "claimed_downside_cov": claimed,
                    "realised_downside_cov": cov,
                    "buffer_bps": float(buffer_bps.mean()),
                    "kupiec_p": _kupiec(breach, claimed),
                    "per_symbol_pass": sym_pass, "per_symbol_n": 10,
                    "per_regime_pass": reg_pass, "per_regime_n": len(regs),
                    "n": int(len(oos)),
                })

    dp = pd.DataFrame(pooled)
    tdir = REPORTS / "tables"; tdir.mkdir(parents=True, exist_ok=True)
    dp.to_csv(tdir / "w4_one_sided_bands.csv", index=False)
    pd.DataFrame(by_sym).to_csv(tdir / "w4_one_sided_by_symbol.csv", index=False)
    pd.DataFrame(by_reg).to_csv(tdir / "w4_one_sided_by_regime.csv", index=False)

    for panel_name, _ in PANELS:
        print("\n" + "=" * 100)
        print(f"{panel_name.upper()} — downside coverage and collateral buffer")
        print("=" * 100)
        v = dp[dp.panel == panel_name]
        print(v[["tau", "arm", "claimed_downside_cov", "realised_downside_cov",
                 "buffer_bps", "kupiec_p", "per_symbol_pass",
                 "per_regime_pass", "per_regime_n"]]
              .to_string(index=False, float_format=lambda x: f"{x:.4f}"))

        print(f"\n  capital saving, {panel_name} (one-sided vs each symmetric arm):")
        for tau in DEFAULT_TAUS:
            s = v[v.tau == tau].set_index("arm")
            if "one_sided" not in s.index:
                continue
            o = s.loc["one_sided", "buffer_bps"]
            bits = []
            for a in ("symmetric_same", "symmetric_matched"):
                if a in s.index:
                    b = s.loc[a, "buffer_bps"]
                    bits.append(f"{a}: {b:7.1f} -> {o:7.1f} bps ({(o/b-1)*100:+5.1f}%)")
            print(f"    τ={tau}:  " + "   |   ".join(bits))

    print(f"\nWrote {tdir / 'w4_one_sided_bands.csv'}")


if __name__ == "__main__":
    main()
