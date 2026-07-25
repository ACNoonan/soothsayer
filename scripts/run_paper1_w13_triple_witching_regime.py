"""
W13 — does a `triple_witching` regime earn a cell on the weekend panel?

Motivation
----------
W12 established *why* the Mondrian partition is load-bearing: it is the only
channel through which the band can widen for an event that is identifiable
from the calendar *before* it happens. No online learner can do that
(W10: earnings_night 0.317–0.383 vs deployed 0.983). That makes the regime
taxonomy the architecture's moat, and the obvious move is to widen it.

Triple witching — quarterly simultaneous expiry of index futures, index
options and single-stock options, on the **third Friday of Mar/Jun/Sep/Dec**
— is the strongest remaining candidate that needs *no new upstream data*.
It is purely calendrical, so it is computable here without violating
CLAUDE.md rules #1/#2 (FOMC and CPI dates would be new upstream data and
must land in scryer first). The S&P quarterly rebalance is effective at the
open following the same session, so this cell captures both.

It is a *weekend*-panel candidate only: a triple-witching Friday's next
open is Monday, which is a weekend gap, not an overnight one.

Design
------
Priority mirrors `earnings_night` on the overnight panel — a scheduled,
calendar-known event takes top precedence over the volatility-derived cell,
because it is knowable at serve time and its fatness is event-driven rather
than scale-driven.

    baseline : normal / long_weekend / high_vol          (deployed)
    variant  : + triple_witching (top priority)

Same σ̂, same split, same rank formula, δ suppressed on both arms. The test
is whether the new cell (a) behaves differently enough to deserve its own
quantile, and (b) improves or degrades calibration once it is carved out —
the cell is thin, so degradation via cell-thinness is a real risk, and §4.3
already rejected a per-(symbol, regime) rung on exactly those grounds.

Outputs
-------
  reports/tables/w13_triple_witching.csv
  reports/tables/w13_triple_witching_by_regime.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS, fit_split_conformal_forecaster,
    prep_panel_for_forecaster, serve_bands_forecaster,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
NO_DELTA: dict[float, float] = {}


def is_triple_witching(d: date) -> bool:
    """Third Friday of March, June, September or December.

    The third Friday always falls on day-of-month 15–21 inclusive, so this
    needs no calendar library and no upstream data."""
    return d.month in (3, 6, 9, 12) and d.weekday() == 4 and 15 <= d.day <= 21


def _score(oos, band, tau, label):
    m = oos["mon_open"].notna() & band["lower"].notna() & band["upper"].notna()
    p, b = oos.loc[m], band.loc[m]
    ins = (p["mon_open"] >= b["lower"]) & (p["mon_open"] <= b["upper"])
    _, p_uc = met._lr_kupiec((~ins).astype(int).to_numpy(), tau)

    sym = sum(
        int(np.isfinite(pp) and pp >= 0.05)
        for _, s in p.groupby("symbol")
        for pp in [met._lr_kupiec(
            (~((s["mon_open"] >= b.loc[s.index, "lower"]) &
               (s["mon_open"] <= b.loc[s.index, "upper"]))).astype(int).to_numpy(),
            tau)[1]]
    )
    rows, rpass, rn = [], 0, 0
    for reg, s in p.groupby("regime_cell"):
        sb = b.loc[s.index]
        i = (s["mon_open"] >= sb["lower"]) & (s["mon_open"] <= sb["upper"])
        _, pr = met._lr_kupiec((~i).astype(int).to_numpy(), tau)
        ok = int(np.isfinite(pr) and pr >= 0.05)
        rpass += ok; rn += 1
        rows.append({**label, "tau": tau, "regime": reg, "n": int(len(s)),
                     "realised": float(i.mean()),
                     "half_width_bps": float(((sb["upper"] - sb["lower"]) / 2
                                              / s["fri_close"] * 1e4).mean()),
                     "kupiec_p": float(pr), "kupiec_pass": ok})
    return {**label, "tau": tau, "n": int(m.sum()),
            "realised": float(ins.mean()),
            "half_width_bps": float(((b["upper"] - b["lower"]) / 2
                                     / p["fri_close"] * 1e4).mean()),
            "kupiec_p": float(p_uc),
            "per_symbol_pass": sym, "per_regime_pass": rpass,
            "per_regime_n": rn}, rows


def main() -> None:
    raw = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    raw["fri_ts"] = pd.to_datetime(raw["fri_ts"]).dt.date
    raw = raw.dropna(subset=["mon_open", "fri_close", "regime_pub",
                             "factor_ret"]).reset_index(drop=True)
    raw["regime_pub"] = raw["regime_pub"].astype(str)
    raw["tw"] = raw["fri_ts"].map(is_triple_witching)

    w = prep_panel_for_forecaster(raw, "lwc")
    w["baseline_cell"] = w["regime_pub"]
    w["variant_cell"] = np.where(w["tw"], "triple_witching", w["regime_pub"])

    n_tw_all = int(w["tw"].sum())
    n_tw_oos = int((w["tw"] & (w["fri_ts"] >= SPLIT_DATE)).sum())
    n_tw_tr = n_tw_all - n_tw_oos
    print(f"triple-witching rows: {n_tw_all} total "
          f"({w.loc[w['tw'],'fri_ts'].nunique()} distinct Fridays) · "
          f"train {n_tw_tr} · oos {n_tw_oos}")
    ov = w[w["tw"]]["regime_pub"].value_counts().to_dict()
    print(f"  what those rows are classified as today: {ov}")

    rows, reg_rows = [], []
    for arm, cell in (("baseline", "baseline_cell"),
                      ("plus_triple_witching", "variant_cell")):
        work = w.copy()
        qt, cb, _ = fit_split_conformal_forecaster(
            work, SPLIT_DATE, "lwc", cell_col=cell)
        oos = (work[work["fri_ts"] >= SPLIT_DATE].dropna(subset=["score"])
               .sort_values(["fri_ts", "symbol"]).reset_index(drop=True))
        bounds = serve_bands_forecaster(
            oos, qt, cb, "lwc", cell_col=cell, taus=DEFAULT_TAUS,
            delta_shift_schedule=NO_DELTA)
        # Score both arms on the SAME partition (the variant's) so the
        # triple-witching sub-population is visible in both.
        oos = oos.assign(regime_cell=oos["variant_cell"])
        for tau in DEFAULT_TAUS:
            r, rr = _score(oos, bounds[tau], tau, {"arm": arm})
            rows.append(r); reg_rows.extend(rr)
        print(f"  {arm}: fit {len(qt)} cells", flush=True)

    out = pd.DataFrame(rows); outr = pd.DataFrame(reg_rows)
    tdir = REPORTS / "tables"; tdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(tdir / "w13_triple_witching.csv", index=False)
    outr.to_csv(tdir / "w13_triple_witching_by_regime.csv", index=False)

    print("\n" + "=" * 96)
    print("POOLED — weekend panel, δ suppressed")
    print("=" * 96)
    print(out.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n" + "=" * 96)
    print("BY CELL @ τ=0.95  (scored on the same partition for both arms)")
    print("=" * 96)
    v = outr[outr.tau == 0.95]
    print(v.pivot_table(index="regime", columns="arm",
                        values=["n", "realised", "half_width_bps", "kupiec_p"])
          .to_string(float_format=lambda x: f"{x:.4f}"))
    print(f"\nWrote {tdir / 'w13_triple_witching.csv'}")


if __name__ == "__main__":
    main()
