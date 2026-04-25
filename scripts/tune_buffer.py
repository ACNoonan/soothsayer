"""
Tune the empirical calibration buffer per-target on OOS 2023+ data.

Background. The original 2.5pp scalar buffer was calibrated against τ=0.95.
Conformal-comparison work (`reports/v1b_conformal_comparison.md`) confirmed
the heuristic dominates every conformal alternative on this data, but also
exposed that 2.5pp is target-specific: at τ=0.85 (the new shipping default
per oracle.py 2026-04-25) the buffer under-corrects and Kupiec rejects.

Method. For each target τ ∈ {0.68, 0.85, 0.95, 0.99}, sweep the buffer over
a fine grid {0.000, 0.005, …, 0.060} on the OOS 2023+ panel using a
calibration surface fit on pre-2023. For each (τ, buffer) record realized
coverage, mean half-width, Kupiec p_uc, Christoffersen p_ind. Recommend the
smallest buffer satisfying:

  (i)   realized ≥ target − 0.005     (under-cover by ≤ 0.5pp)
  (ii)  Kupiec p_uc > 0.10            (cannot reject correct rate)
  (iii) Christoffersen p_ind > 0.05   (violations not clustered)

If no buffer in the grid satisfies these, report the closest-passing config
and flag the structural ceiling explicitly.

Outputs:
  reports/tables/v1b_buffer_sweep.csv         full (target × buffer) sweep
  reports/tables/v1b_buffer_recommended.csv   per-target chosen buffer
  reports/v1b_buffer_tune.md                  writeup
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


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95, 0.99)
BUFFER_GRID = tuple(round(b * 0.001, 3) for b in range(0, 61, 5))  # 0.000 .. 0.060 step 0.005


def _tables_dir() -> Path:
    p = REPORTS / "tables"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _serve(bounds_oos: pd.DataFrame, panel_oos: pd.DataFrame,
           surface: pd.DataFrame, surface_pooled: pd.DataFrame,
           target: float, buffer: float) -> pd.DataFrame:
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)
    rows = []
    for _, row in panel_oos.iterrows():
        try:
            pp = oracle.fair_value(row["symbol"], row["fri_ts"],
                                   target_coverage=target, buffer_override=buffer)
        except ValueError:
            continue
        inside = (row["mon_open"] >= pp.lower) and (row["mon_open"] <= pp.upper)
        rows.append({
            "symbol": row["symbol"],
            "fri_ts": row["fri_ts"],
            "regime_pub": row["regime_pub"],
            "inside": int(inside),
            "half_width_bps": float(pp.half_width_bps),
            "claim_served": float(pp.claimed_coverage_served),
        })
    return pd.DataFrame(rows)


def _stats(served: pd.DataFrame, target: float) -> dict:
    n = int(len(served))
    realized = float(served["inside"].mean())
    mean_hw = float(served["half_width_bps"].mean())
    v = (~served["inside"].astype(bool)).astype(int).values
    lr_uc, p_uc = met._lr_kupiec(v, target)
    # Pooled Christoffersen across symbols
    lr_ind_total = 0.0
    n_groups = 0
    for sym, grp in served.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
        v_sym = (~grp["inside"].astype(bool)).astype(int).values
        lr_ind, _ = met._lr_christoffersen_independence(v_sym)
        if not np.isnan(lr_ind):
            lr_ind_total += lr_ind
            n_groups += 1
    p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
    return {
        "n": n, "realized": realized, "mean_half_width_bps": mean_hw,
        "violations": int(v.sum()), "violation_rate": float(v.mean()),
        "lr_uc": float(lr_uc), "p_uc": float(p_uc),
        "lr_ind": float(lr_ind_total), "p_ind": p_ind,
    }


def main() -> None:
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds["mon_ts"] = pd.to_datetime(bounds["mon_ts"]).dt.date

    panel_full = bounds[
        ["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]
    ].drop_duplicates(["symbol", "fri_ts"]).reset_index(drop=True)
    panel_oos = panel_full[panel_full["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)

    surface = cal.compute_calibration_surface(bounds_train)
    surface_pooled = cal.pooled_surface(bounds_train)

    print(f"OOS panel: {len(panel_oos):,} rows in {panel_oos['fri_ts'].nunique()} weekends; "
          f"{len(BUFFER_GRID)} buffer levels × {len(TARGETS)} targets", flush=True)

    sweep_rows = []
    for target in TARGETS:
        print()
        print(f"--- target τ = {target:.2f} ---", flush=True)
        for buf in BUFFER_GRID:
            t0 = time.time()
            served = _serve(bounds_oos, panel_oos, surface, surface_pooled, target, buf)
            stats = _stats(served, target)
            sweep_rows.append({"target": target, "buffer": buf, **stats})
            print(f"  buf={buf:.3f}: realized={stats['realized']:.3f}  "
                  f"hw={stats['mean_half_width_bps']:.0f}bps  "
                  f"p_uc={stats['p_uc']:.3f}  p_ind={stats['p_ind']:.3f}  "
                  f"({time.time()-t0:.1f}s)", flush=True)

    sweep = pd.DataFrame(sweep_rows)
    sweep.to_csv(_tables_dir() / "v1b_buffer_sweep.csv", index=False)

    # ---- Recommendation logic ----
    rec_rows = []
    for target in TARGETS:
        sub = sweep[sweep["target"] == target].sort_values("buffer").reset_index(drop=True)
        # Hard requirements
        ok = sub[
            (sub["realized"] >= target - 0.005) &
            (sub["p_uc"] > 0.10) &
            (sub["p_ind"] > 0.05)
        ]
        if not ok.empty:
            chosen = ok.iloc[0]
            status = "PASS"
        else:
            # Fallback: relax to p_uc > 0.05
            ok2 = sub[(sub["realized"] >= target - 0.005) & (sub["p_uc"] > 0.05)]
            if not ok2.empty:
                chosen = ok2.iloc[0]
                status = "MARGINAL_pass_uc_only"
            else:
                # No buffer passes. Pick the one closest to target with realized >= target.
                ok3 = sub[sub["realized"] >= target]
                if not ok3.empty:
                    chosen = ok3.iloc[0]
                    status = "STRUCTURAL_CEILING"
                else:
                    # Even max buffer under-covers — hard ceiling
                    chosen = sub.iloc[-1]
                    status = "STRUCTURAL_CEILING"
        rec_rows.append({
            "target": target,
            "recommended_buffer": float(chosen["buffer"]),
            "realized": float(chosen["realized"]),
            "mean_half_width_bps": float(chosen["mean_half_width_bps"]),
            "p_uc": float(chosen["p_uc"]),
            "p_ind": float(chosen["p_ind"]),
            "status": status,
        })

    rec = pd.DataFrame(rec_rows)
    rec.to_csv(_tables_dir() / "v1b_buffer_recommended.csv", index=False)

    print()
    print("=" * 80)
    print("RECOMMENDED BUFFER PER TARGET")
    print("=" * 80)
    print(rec.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # ---- Writeup ----
    lines = [
        "# V1b — per-target buffer tuning",
        "",
        f"**Method.** OOS 2023+ panel ({len(panel_oos):,} rows, "
        f"{panel_oos['fri_ts'].nunique()} weekends); calibration surface fit on "
        f"pre-{SPLIT_DATE} bounds. For each target τ ∈ {list(TARGETS)}, sweep "
        f"buffer over {list(BUFFER_GRID)} (61 / 11 levels, step 0.005).",
        "",
        "**Decision criterion.** Smallest buffer satisfying: realized ≥ τ − 0.5pp, "
        "Kupiec $p_{uc}$ > 0.10, Christoffersen $p_{ind}$ > 0.05. If no level "
        "satisfies, report the marginal-pass or structural-ceiling fallback.",
        "",
        "## Recommendation",
        "",
        rec.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Full sweep",
        "",
        sweep.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Reading",
        "",
        "- Status `PASS` means all three calibration tests are not rejected at the recommended buffer.",
        "- `STRUCTURAL_CEILING` at τ=0.99 reflects the documented finite-sample tail issue (§9.1 of paper); buffer cannot push past `MAX_SERVED_TARGET = 0.995`.",
        "- The recommended buffers should be persisted as `BUFFER_BY_TARGET` in `src/soothsayer/oracle.py`, replacing the scalar `CALIBRATION_BUFFER_PCT`. Off-grid targets interpolate linearly between adjacent points.",
    ]
    out_path = REPORTS / "v1b_buffer_tune.md"
    out_path.write_text("\n".join(lines))
    print()
    print(f"Wrote {out_path}")
    print(f"Wrote {_tables_dir() / 'v1b_buffer_sweep.csv'}")
    print(f"Wrote {_tables_dir() / 'v1b_buffer_recommended.csv'}")


if __name__ == "__main__":
    main()
