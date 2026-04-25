"""
Walk-forward backtest: distribution-valued calibration claims.

The single-split (pre-2023 train / 2023+ test) used through v1b gives one
realisation of the buffer values, the Kupiec p-values, and the OOS coverage
deltas. A reviewer can reasonably ask: how stable are these across train/
test splits? What is the standard error around the deployed
`BUFFER_BY_TARGET` values?

This script implements rolling-origin expanding-window walk-forward:
  Split k:  train = [start, cutoff_k);  test = [cutoff_k, cutoff_k + horizon)

Cutoffs span 2019-01-01 → 2024-01-01 in 12-month steps (6 splits). Horizon
is 12 months. For each split:
  1. Fit the calibration surface on bounds with fri_ts < cutoff.
  2. For each τ ∈ {0.68, 0.85, 0.95, 0.99}, sweep the buffer over the same
     grid as `tune_buffer.py` and pick the smallest one passing
     Kupiec p_uc > 0.10 + Christoffersen p_ind > 0.05 + realized ≥ τ−0.005.
     Record per-split the chosen buffer and the (realized, half_width, p_uc, p_ind)
     it produces on the test slice.

Outputs:
  reports/tables/v1b_walkforward_buffer.csv  (split, target, buffer, realized, ...)
  reports/v1b_walkforward.md                 writeup with per-target buffer ± SE
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


CUTOFFS = [
    date(2019, 1, 1),
    date(2020, 1, 1),
    date(2021, 1, 1),
    date(2022, 1, 1),
    date(2023, 1, 1),
    date(2024, 1, 1),
]
HORIZON_MONTHS = 12
TARGETS = (0.68, 0.85, 0.95, 0.99)
BUFFER_GRID = tuple(round(b * 0.001, 3) for b in range(0, 61, 5))  # 0..0.060 step 0.005


def _tables_dir() -> Path:
    p = REPORTS / "tables"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month + months - 1) // 12
    m = (d.month + months - 1) % 12 + 1
    return date(y, m, min(d.day, 28))


def _serve(bounds_test: pd.DataFrame, panel_test: pd.DataFrame,
           surface: pd.DataFrame, surface_pooled: pd.DataFrame,
           target: float, buffer: float) -> pd.DataFrame:
    oracle = Oracle(bounds=bounds_test, surface=surface, surface_pooled=surface_pooled)
    rows = []
    for _, row in panel_test.iterrows():
        try:
            pp = oracle.fair_value(row["symbol"], row["fri_ts"],
                                   target_coverage=target, buffer_override=buffer)
        except ValueError:
            continue
        inside = (row["mon_open"] >= pp.lower) and (row["mon_open"] <= pp.upper)
        rows.append({
            "symbol": row["symbol"], "fri_ts": row["fri_ts"],
            "regime_pub": row["regime_pub"],
            "inside": int(inside),
            "half_width_bps": float(pp.half_width_bps),
        })
    return pd.DataFrame(rows)


def _stats(served: pd.DataFrame, target: float) -> dict:
    n = int(len(served))
    if n == 0:
        return {"n": 0, "realized": float("nan"),
                "mean_half_width_bps": float("nan"),
                "p_uc": float("nan"), "p_ind": float("nan")}
    realized = float(served["inside"].mean())
    hw = float(served["half_width_bps"].mean())
    v = (~served["inside"].astype(bool)).astype(int).values
    lr_uc, p_uc = met._lr_kupiec(v, target)
    lr_ind_total, n_groups = 0.0, 0
    for sym, g in served.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
        lr_ind, _ = met._lr_christoffersen_independence(
            (~g["inside"].astype(bool)).astype(int).values)
        if not np.isnan(lr_ind):
            lr_ind_total += lr_ind
            n_groups += 1
    p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
    return {
        "n": n, "realized": realized, "mean_half_width_bps": hw,
        "p_uc": float(p_uc), "p_ind": p_ind,
    }


def _pick_buffer(bounds_test, panel_test, surface, surface_pooled,
                 target: float) -> tuple[float, dict]:
    """Smallest buffer satisfying realized ≥ τ−0.005 and p_uc > 0.10 and p_ind > 0.05.
    Falls back to relaxed criteria if nothing passes."""
    sweep_rows = []
    for buf in BUFFER_GRID:
        served = _serve(bounds_test, panel_test, surface, surface_pooled, target, buf)
        s = _stats(served, target)
        s["buffer"] = buf
        sweep_rows.append(s)
    sweep = pd.DataFrame(sweep_rows)

    ok = sweep[
        (sweep["realized"] >= target - 0.005)
        & (sweep["p_uc"] > 0.10)
        & (sweep["p_ind"] > 0.05)
    ].sort_values("buffer")
    if not ok.empty:
        chosen = ok.iloc[0]
        return float(chosen["buffer"]), {**chosen.to_dict(), "status": "PASS"}
    ok2 = sweep[(sweep["realized"] >= target - 0.005) & (sweep["p_uc"] > 0.05)].sort_values("buffer")
    if not ok2.empty:
        chosen = ok2.iloc[0]
        return float(chosen["buffer"]), {**chosen.to_dict(), "status": "MARGINAL"}
    ok3 = sweep[sweep["realized"] >= target].sort_values("buffer")
    chosen = ok3.iloc[0] if not ok3.empty else sweep.iloc[-1]
    return float(chosen["buffer"]), {**chosen.to_dict(), "status": "CEILING"}


def main() -> None:
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds["mon_ts"] = pd.to_datetime(bounds["mon_ts"]).dt.date
    panel_full = bounds[["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]].drop_duplicates(
        ["symbol", "fri_ts"]
    ).reset_index(drop=True)

    rows = []
    for k, cutoff in enumerate(CUTOFFS):
        horizon_end = _add_months(cutoff, HORIZON_MONTHS)
        train_b = bounds[bounds["fri_ts"] < cutoff]
        test_b = bounds[(bounds["fri_ts"] >= cutoff) & (bounds["fri_ts"] < horizon_end)]
        test_p = panel_full[(panel_full["fri_ts"] >= cutoff) & (panel_full["fri_ts"] < horizon_end)]
        if len(train_b) < 1000 or len(test_p) < 50:
            print(f"[split{k}] cutoff={cutoff} skipped — train_b={len(train_b)}, test_p={len(test_p)}", flush=True)
            continue
        surface = cal.compute_calibration_surface(train_b)
        surface_pooled = cal.pooled_surface(train_b)
        print(f"[split{k}] cutoff={cutoff}, horizon→{horizon_end} | "
              f"train_b={len(train_b):,}  test_p={len(test_p):,} weekends={test_p['fri_ts'].nunique()}",
              flush=True)
        for tau in TARGETS:
            t0 = time.time()
            buf, info = _pick_buffer(test_b, test_p, surface, surface_pooled, tau)
            row = {
                "split": k, "cutoff": cutoff, "horizon_end": horizon_end,
                "n_train_b": int(len(train_b)),
                "n_test_p": int(len(test_p)),
                "target": tau,
                "buffer_chosen": buf,
                "realized": info.get("realized"),
                "mean_half_width_bps": info.get("mean_half_width_bps"),
                "p_uc": info.get("p_uc"),
                "p_ind": info.get("p_ind"),
                "status": info.get("status"),
            }
            rows.append(row)
            print(f"  τ={tau:.2f}: buf={buf:.3f}  realized={row['realized']:.3f}  "
                  f"hw={row['mean_half_width_bps']:.0f}bps  "
                  f"p_uc={row['p_uc']:.3f} p_ind={row['p_ind']:.3f}  "
                  f"[{row['status']}]  ({time.time()-t0:.1f}s)", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(_tables_dir() / "v1b_walkforward_buffer.csv", index=False)

    # Per-target distribution
    print()
    print("=" * 80)
    print("PER-TARGET BUFFER DISTRIBUTION ACROSS SPLITS")
    print("=" * 80)
    summary_rows = []
    for tau in TARGETS:
        sub = df[df["target"] == tau]
        if sub.empty:
            continue
        summary_rows.append({
            "target": tau,
            "n_splits": int(len(sub)),
            "buffer_mean": float(sub["buffer_chosen"].mean()),
            "buffer_std": float(sub["buffer_chosen"].std()),
            "buffer_min": float(sub["buffer_chosen"].min()),
            "buffer_max": float(sub["buffer_chosen"].max()),
            "deployed_buffer": {0.68: 0.045, 0.85: 0.045, 0.95: 0.020, 0.99: 0.005}.get(tau, np.nan),
            "realized_mean": float(sub["realized"].mean()),
            "realized_std": float(sub["realized"].std()),
            "p_uc_min": float(sub["p_uc"].min()),
            "n_pass": int((sub["status"] == "PASS").sum()),
        })
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(_tables_dir() / "v1b_walkforward_summary.csv", index=False)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # ---- Writeup ----
    md_lines = [
        "# V1b — Walk-forward calibration backtest",
        "",
        "**Method.** Rolling-origin expanding-window walk-forward. For each cutoff "
        f"in {[c.isoformat() for c in CUTOFFS]}, train calibration surface on bounds with "
        f"fri_ts < cutoff, evaluate Oracle on bounds in [cutoff, cutoff + {HORIZON_MONTHS} months). "
        "For each τ ∈ {0.68, 0.85, 0.95, 0.99}, sweep buffer over `[0.000, 0.060]` step 0.005 "
        "and pick the smallest passing realized ≥ τ−0.005 + Kupiec $p_{uc}$ > 0.10 + "
        "Christoffersen $p_{ind}$ > 0.05.",
        "",
        "## Per-target buffer summary across splits",
        "",
        summary.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Per-split detail",
        "",
        df.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Reading",
        "",
        "- `buffer_mean ± buffer_std` is the empirical distribution of optimal buffers across walk-forward splits — the single-split values in `BUFFER_BY_TARGET` should fall within ~1σ of `buffer_mean`.",
        "- `n_pass / n_splits` is the fraction of splits in which the chosen buffer satisfies the strict (PASS) criteria. Lower fractions reveal targets where calibration is fundamentally harder (typically the tails).",
        "- `realized_std` quantifies how stable the served calibration is across deployment windows; small values support a fixed `BUFFER_BY_TARGET` schedule with rolling re-fits, large values argue for adaptive per-window re-tuning.",
        "",
        "## Use",
        "",
        "1. For paper §9.4 ('sample-size-one buffer' disclosure): replace with measured `buffer_mean ± buffer_std` per τ.",
        "2. For deployment cadence (`docs/v2.md` §V2.2): the `realized_std` figure caps the rolling rebuild interval — if drift is bounded, quarterly rebuilds suffice; otherwise monthly or event-driven.",
        "3. For grant application (`docs/grant_application_tldr.md`): the walk-forward result is the Tier-1 deliverable that converts a single-split anchor into a distribution-valued claim.",
    ]
    out = REPORTS / "v1b_walkforward.md"
    out.write_text("\n".join(md_lines))
    print()
    print(f"Wrote {out}")
    print(f"Wrote {_tables_dir() / 'v1b_walkforward_buffer.csv'}")
    print(f"Wrote {_tables_dir() / 'v1b_walkforward_summary.csv'}")


if __name__ == "__main__":
    main()
