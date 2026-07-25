"""
W12 — does the regime partition earn its place *given* σ̂ standardisation?

The gap this closes
-------------------
§7's comparators form a 2×2 on {σ̂ standardisation, regime partition} and
one cell has never been run:

                     no partition          Mondrian partition
    no σ̂             constant buffer §7.1  unweighted Mondrian §7.2
    σ̂                --- NEVER RUN ---     deployed

§7.1 tests stratification against a comparator that also lacks σ̂; §7.2
tests σ̂ against a comparator that has the partition. So "what does the
partition buy *given* σ̂?" is unanswered. W10's online-conformal run
(2026-07-24) made the question urgent: pooled ACI on the σ̂-standardised
score reached per-symbol 10/10 with no partition at all, 6.2% narrower
than deployed.

All four arms are frozen split-conformal through the sanctioned code path,
differing only in (forecaster, cell_col):

    m5  + _all        no σ̂, one pooled quantile
    m5  + regime_pub  no σ̂, per-regime quantiles
    lwc + _all        σ̂, one pooled quantile   <- the missing cell
    lwc + regime_pub  σ̂, per-regime quantiles  = deployed

δ(τ) is suppressed (`{}`) on **every** arm. The deployed M5 path would
otherwise carry a non-zero walk-forward δ that the LWC path does not,
which would contaminate a comparison whose entire point is to isolate two
other knobs.

Run across BOTH off-hours panels — weekend (Fri→Mon) and overnight
(close→next open) — because the architecture claim in §6.8 is that it
holds across closed-market hours generally, not weekends specifically.

The decisive metric is *not* pooled coverage. Every arm is expected to
pool to nominal. The questions are:
  (a) per-symbol Kupiec — does it hold for each ticker individually?
  (b) per-REGIME Kupiec — does it hold *inside* high_vol / long_weekend /
      earnings_night? This is where a pooled quantile should break if the
      partition is doing real work, and it is the number that decides
      whether the buckets stay.

Outputs
-------
  reports/tables/w12_partition_given_sigma.csv          pooled + per-symbol
  reports/tables/w12_partition_given_sigma_by_regime.csv per-regime

Run
---
  ./.venv/bin/python scripts/run_paper1_w12_partition_given_sigma.py
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
# The overnight panel's σ̂ MUST exclude earnings residuals from the scale pool
# (build_overnight_panel.py builds it that way). prep_panel_for_forecaster
# recomputes σ̂, so omitting this silently substitutes a contaminated scale:
# +32% σ̂ on GOOGL, +23% on NVDA, over-widening every ordinary night.
SIGMA_EXCL = {"weekend": None, "overnight": "earnings_next_week"}
NO_DELTA: dict[float, float] = {}

ARMS = [
    ("m5",  "_all",       "no_sigma_pooled",     "no σ̂ · pooled"),
    ("m5",  "regime_pub", "no_sigma_mondrian",   "no σ̂ · Mondrian"),
    ("lwc", "_all",       "sigma_pooled",        "σ̂ · pooled  <-- missing cell"),
    ("lwc", "regime_pub", "sigma_mondrian",      "σ̂ · Mondrian (deployed)"),
]

PANELS = [("weekend", "v1b_panel"), ("overnight", "overnight_panel")]


def _kupiec_pass(sub: pd.DataFrame, band: pd.DataFrame, tau: float) -> tuple[int, int]:
    """(passes, total) Kupiec at 5% over the groups already split by caller."""
    ins = (sub["mon_open"] >= band["lower"]) & (sub["mon_open"] <= band["upper"])
    _, p = met._lr_kupiec((~ins).astype(int).to_numpy(), tau)
    return (int(np.isfinite(p) and p >= 0.05), 1)


def _score_arm(oos: pd.DataFrame, band: pd.DataFrame, tau: float,
               label: dict) -> tuple[dict, list[dict]]:
    m = oos["mon_open"].notna() & band["lower"].notna() & band["upper"].notna()
    p, b = oos.loc[m], band.loc[m]
    inside = (p["mon_open"] >= b["lower"]) & (p["mon_open"] <= b["upper"])
    lr, p_uc = met._lr_kupiec((~inside).astype(int).to_numpy(), tau)
    cc = met.conditional_coverage_from_bounds(p, {tau: b}, group_by="symbol").iloc[0]

    sym_pass = sym_n = 0
    for _, sub in p.groupby("symbol"):
        a, n = _kupiec_pass(sub, b.loc[sub.index], tau)
        sym_pass += a; sym_n += n

    reg_rows, reg_pass, reg_n = [], 0, 0
    for reg, sub in p.groupby("regime_pub"):
        sb = b.loc[sub.index]
        ins = (sub["mon_open"] >= sb["lower"]) & (sub["mon_open"] <= sb["upper"])
        _, pr = met._lr_kupiec((~ins).astype(int).to_numpy(), tau)
        ok = int(np.isfinite(pr) and pr >= 0.05)
        reg_pass += ok; reg_n += 1
        reg_rows.append({
            **label, "tau": tau, "regime": reg, "n": int(len(sub)),
            "realised": float(ins.mean()),
            "half_width_bps": float(((sb["upper"] - sb["lower"]) / 2
                                     / sub["fri_close"] * 1e4).mean()),
            "kupiec_p": float(pr), "kupiec_pass": ok,
        })

    row = {
        **label, "tau": tau, "n": int(m.sum()),
        "realised": float(inside.mean()),
        "half_width_bps": float(((b["upper"] - b["lower"]) / 2
                                 / p["fri_close"] * 1e4).mean()),
        "kupiec_p": float(p_uc), "christ_p": float(cc["p_ind"]),
        "per_symbol_kupiec_pass": sym_pass, "per_symbol_n": sym_n,
        "per_regime_kupiec_pass": reg_pass, "per_regime_n": reg_n,
    }
    return row, reg_rows


def main() -> None:
    rows, reg_rows = [], []

    for panel_name, fname in PANELS:
        raw = pd.read_parquet(DATA_PROCESSED / f"{fname}.parquet")
        raw["fri_ts"] = pd.to_datetime(raw["fri_ts"]).dt.date
        raw = raw.dropna(
            subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
        ).reset_index(drop=True)
        raw["regime_pub"] = raw["regime_pub"].astype(str)
        raw["_all"] = "all"

        print(f"\n### {panel_name}: {len(raw):,} rows · "
              f"{raw['fri_ts'].nunique()} periods · "
              f"{raw['symbol'].nunique()} symbols · "
              f"regimes {sorted(raw['regime_pub'].unique())}", flush=True)

        for forecaster, cell_col, arm_key, arm_desc in ARMS:
            work = prep_panel_for_forecaster(
                raw, forecaster, sigma_exclude_mask_col=SIGMA_EXCL[panel_name])
            qt, cb, _ = fit_split_conformal_forecaster(
                work, SPLIT_DATE, forecaster, cell_col=cell_col)
            oos = (work[work["fri_ts"] >= SPLIT_DATE]
                   .dropna(subset=["score"])
                   .sort_values(["fri_ts", "symbol"]).reset_index(drop=True))
            bounds = serve_bands_forecaster(
                oos, qt, cb, forecaster, cell_col=cell_col,
                taus=DEFAULT_TAUS, delta_shift_schedule=NO_DELTA)

            label = {"panel": panel_name, "arm": arm_key, "arm_desc": arm_desc,
                     "forecaster": forecaster, "cells": cell_col}
            for tau in DEFAULT_TAUS:
                r, rr = _score_arm(oos, bounds[tau], tau, label)
                rows.append(r); reg_rows.extend(rr)
            print(f"   {arm_desc:<32} n_oos={len(oos):,}", flush=True)

    out = pd.DataFrame(rows)
    outr = pd.DataFrame(reg_rows)
    tdir = REPORTS / "tables"; tdir.mkdir(parents=True, exist_ok=True)
    out.to_csv(tdir / "w12_partition_given_sigma.csv", index=False)
    outr.to_csv(tdir / "w12_partition_given_sigma_by_regime.csv", index=False)

    for panel_name, _ in PANELS:
        print("\n" + "=" * 108)
        print(f"{panel_name.upper()} — τ = 0.95  (δ suppressed on every arm)")
        print("=" * 108)
        v = out[(out.panel == panel_name) & (out.tau == 0.95)]
        print(v[["arm_desc", "n", "realised", "half_width_bps", "kupiec_p",
                 "per_symbol_kupiec_pass", "per_symbol_n",
                 "per_regime_kupiec_pass", "per_regime_n"]]
              .to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        print(f"\n  per-regime detail @ τ=0.95 ({panel_name}):")
        w = outr[(outr.panel == panel_name) & (outr.tau == 0.95)]
        print(w.pivot_table(index="regime", columns="arm",
                            values=["realised", "half_width_bps"])
              .to_string(float_format=lambda x: f"{x:.4f}"))

    print(f"\nWrote {tdir / 'w12_partition_given_sigma.csv'}")


if __name__ == "__main__":
    main()
