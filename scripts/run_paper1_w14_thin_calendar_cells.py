"""
W14 — thin calendar cells: is it noise, shift, or shape? And what fixes it?

The problem
-----------
Two calendar-known regime cells fail calibration, in opposite directions:

  earnings_night (overnight, n_oos = 60)   over-covers in the body
      τ=0.68 -> 0.800 realised (Kupiec p=0.038)
      τ=0.85 -> 0.967 realised (p=0.003)
      τ=0.95 -> 0.983 (passes)
  triple_witching (weekend, n_oos = 130)   under-covers in the tail
      τ=0.95 -> 0.908 realised (p=0.047)

Both are thin, both are knowable from the calendar, and W12/W13 showed both
are *necessary* cells — the failures are in how the cell's quantile is
estimated, not in whether the cell should exist.

Three candidate explanations, and they imply different fixes:
  (a) SMALL-SAMPLE NOISE  — n=60 cannot resolve much; the "failure" may be
      inside the binomial CI. Fix: nothing, but stop claiming the cell is
      calibrated.
  (b) TRAIN -> OOS SHIFT  — the cell's quantile profile moves between fit
      and serve. Fix: more data / re-fit cadence.
  (c) GENUINE SHAPE       — the cell's residual distribution is not a scale
      multiple of the pooled one, so a per-τ quantile from a thin sample is
      badly estimated. Fix: borrow shape from the pool, keep scale local.

Step 1 diagnoses. Step 2 tests the remedy implied by (c).

The remedy
----------
Per-cell quantiles spend one parameter per (cell, τ). For a cell with ~170
training rows that is wasteful, and the tail anchors are estimated from a
handful of order statistics. The alternative spends ONE parameter per cell:

    q_r(τ)  =  w_r · q_cell(τ)  +  (1 − w_r) · m_r · q_pooled(τ)
    w_r     =  n_r / (n_r + k)
    m_r     =  median(score_cell) / median(score_pooled)      (robust scale)

"Shape from the pool, scale from the cell." As a cell grows, w_r -> 1 and it
recovers its own empirical quantile; as it thins, it falls back to the
pooled *shape* rescaled to the cell's own magnitude — which is exactly the
information a thin cell can estimate reliably and the per-τ quantile cannot.

Shrinking toward the *unscaled* pooled quantile (what Rafe & Das evaluate in
arXiv:2605.05562, and find only marginally helpful) would be wrong here: it
would collapse a 10x-fatter earnings cell toward normal-night width. The
m_r rescaling is what makes shrinkage safe for heterogeneous cells.

k = 0 recovers the deployed architecture; k -> inf is pure scale-family.

Outputs
-------
  reports/tables/w14_thin_cells_diagnosis.csv
  reports/tables/w14_thin_cells_remedies.csv
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
K_GRID = (0.0, 50.0, 100.0, 200.0, 500.0, np.inf)
THIN = {"weekend": "triple_witching", "overnight": "earnings_night"}
RNG = np.random.default_rng(0)


def is_triple_witching(d: date) -> bool:
    return d.month in (3, 6, 9, 12) and d.weekday() == 4 and 15 <= d.day <= 21


def _cp_q(s: np.ndarray, tau: float) -> float:
    s = np.sort(s[np.isfinite(s)])
    if s.size == 0:
        return float("nan")
    k = min(max(int(np.ceil(tau * (s.size + 1))), 1), s.size)
    return float(s[k - 1])


def main() -> None:
    diag, rem = [], []

    for panel_name, fname in PANELS:
        raw = pd.read_parquet(DATA_PROCESSED / f"{fname}.parquet")
        raw["fri_ts"] = pd.to_datetime(raw["fri_ts"]).dt.date
        raw = raw.dropna(subset=["mon_open", "fri_close", "regime_pub",
                                 "factor_ret"]).reset_index(drop=True)
        raw["regime_pub"] = raw["regime_pub"].astype(str)

        w = prep_panel_for_forecaster(
            raw, "lwc", sigma_exclude_mask_col=SIGMA_EXCL[panel_name])
        if panel_name == "weekend":   # W13 cell
            tw = w["fri_ts"].map(is_triple_witching)
            w["cell"] = np.where(tw, "triple_witching", w["regime_pub"])
        else:
            w["cell"] = w["regime_pub"]
        w["point"] = w["fri_close"] * (1.0 + w["factor_ret"])
        w = w.dropna(subset=["score"]).reset_index(drop=True)

        tr = w[w["fri_ts"] < SPLIT_DATE]
        oos = w[w["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
        thin = THIN[panel_name]

        # ---------------- Step 1: diagnosis -----------------------------
        pooled_tr = tr["score"].to_numpy(float)
        for cell, g in tr.groupby("cell"):
            sc = g["score"].to_numpy(float)
            o = oos[oos["cell"] == cell]["score"].to_numpy(float)
            for tau in DEFAULT_TAUS:
                qc, qp = _cp_q(sc, tau), _cp_q(pooled_tr, tau)
                # the ratio the OOS slice would have wanted
                diag.append({
                    "panel": panel_name, "cell": cell, "tau": tau,
                    "n_train": int(sc.size), "n_oos": int(o.size),
                    "ratio_train": qc / qp if qp else np.nan,
                    "ratio_oos_wanted": (_cp_q(o, tau) / qp) if (qp and o.size) else np.nan,
                    "is_thin": cell == thin,
                })

        # binomial CI on the thin cell's OOS coverage — is the failure noise?
        n_thin = int((oos["cell"] == thin).sum())
        for tau in DEFAULT_TAUS:
            if n_thin:
                draws = RNG.binomial(n_thin, tau, 4000) / n_thin
                lo, hi = np.quantile(draws, [0.025, 0.975])
                diag.append({"panel": panel_name, "cell": f"{thin}__CI",
                             "tau": tau, "n_train": np.nan, "n_oos": n_thin,
                             "ratio_train": lo, "ratio_oos_wanted": hi,
                             "is_thin": True})

        # ---------------- Step 2: remedies ------------------------------
        m_r = {c: (float(np.median(g["score"])) / float(np.median(pooled_tr)))
               for c, g in tr.groupby("cell")}
        q_cell = {c: {t: _cp_q(g["score"].to_numpy(float), t) for t in DEFAULT_TAUS}
                  for c, g in tr.groupby("cell")}
        q_pool = {t: _cp_q(pooled_tr, t) for t in DEFAULT_TAUS}
        n_cell = {c: int(len(g)) for c, g in tr.groupby("cell")}

        cells = oos["cell"].to_numpy()
        scale = (oos["sigma_hat_sym_pre_fri"].to_numpy(float)
                 * oos["fri_close"].to_numpy(float))
        point = oos["point"].to_numpy(float)
        act = oos["mon_open"].to_numpy(float)
        fri = oos["fri_close"].to_numpy(float)

        for k in K_GRID:
            for tau in DEFAULT_TAUS:
                q = np.array([
                    (q_cell[c][tau] if k == 0 else
                     (m_r[c] * q_pool[tau] if not np.isfinite(k) else
                      (n_cell[c] / (n_cell[c] + k)) * q_cell[c][tau]
                      + (1 - n_cell[c] / (n_cell[c] + k)) * m_r[c] * q_pool[tau]))
                    for c in cells], dtype=float)
                hw = q * scale
                ins = (act >= point - hw) & (act <= point + hw)
                _, p_uc = met._lr_kupiec((~ins).astype(int), tau)

                sym = 0
                for s in np.unique(oos["symbol"]):
                    m = (oos["symbol"] == s).to_numpy()
                    _, ps = met._lr_kupiec((~ins[m]).astype(int), tau)
                    sym += int(np.isfinite(ps) and ps >= 0.05)
                rp, rn, thin_cov, thin_p = 0, 0, np.nan, np.nan
                for c in np.unique(cells):
                    m = cells == c
                    _, pr = met._lr_kupiec((~ins[m]).astype(int), tau)
                    rn += 1; rp += int(np.isfinite(pr) and pr >= 0.05)
                    if c == thin:
                        thin_cov, thin_p = float(ins[m].mean()), float(pr)

                rem.append({
                    "panel": panel_name, "k": k, "tau": tau,
                    "realised": float(ins.mean()),
                    "half_width_bps": float((hw / fri * 1e4).mean()),
                    "kupiec_p": float(p_uc),
                    "per_symbol_pass": sym,
                    "per_regime_pass": rp, "per_regime_n": rn,
                    f"thin_cell_cov": thin_cov, "thin_cell_kupiec_p": thin_p,
                })

    dd, dr = pd.DataFrame(diag), pd.DataFrame(rem)
    t = REPORTS / "tables"; t.mkdir(parents=True, exist_ok=True)
    dd.to_csv(t / "w14_thin_cells_diagnosis.csv", index=False)
    dr.to_csv(t / "w14_thin_cells_remedies.csv", index=False)

    for pan, _ in PANELS:
        thin = THIN[pan]
        print("\n" + "=" * 100)
        print(f"{pan.upper()} — thin cell = {thin}")
        print("=" * 100)
        d = dd[(dd.panel == pan) & (dd.cell == thin)]
        c = dd[(dd.panel == pan) & (dd.cell == f"{thin}__CI")]
        print("  DIAGNOSIS  q_cell/q_pooled, train vs what OOS wanted:")
        print(d[["tau", "n_train", "n_oos", "ratio_train",
                 "ratio_oos_wanted"]].to_string(index=False,
                                                float_format=lambda x: f"{x:.3f}"))
        print("  95% binomial CI on OOS coverage at this n (is a miss just noise?):")
        print("   " + "  ".join(
            f"τ={r.tau}: [{r.ratio_train:.3f},{r.ratio_oos_wanted:.3f}]"
            for r in c.itertuples()))
        print("\n  REMEDY sweep (k=0 is deployed; k=inf is pure scale-family):")
        v = dr[dr.panel == pan]
        print(v.pivot_table(index="k", columns="tau",
                            values=["thin_cell_cov", "per_regime_pass",
                                    "half_width_bps"])
              .to_string(float_format=lambda x: f"{x:.3f}"))

    print(f"\nWrote {t / 'w14_thin_cells_remedies.csv'}")


if __name__ == "__main__":
    main()
