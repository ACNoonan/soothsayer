"""
Build the Mondrian (M5) deployment artefact — the v2 successor to v1b_bounds.parquet.

The v2 Oracle serves a band as

    p_hat = fri_close * (1 + factor_ret)                 # §7.4 factor switchboard
    tau'  = tau + delta_shift_schedule(tau)              # post-hoc OOS-fit overshoot
    q     = c_bump_schedule(tau') * q_regime(regime_pub, tau')
    lower = p_hat * (1 - q),  upper = p_hat * (1 + q),  point = p_hat

This script produces two artefacts:

  - data/processed/mondrian_artefact_v2.parquet   per-Friday lookup rows:
      symbol, fri_ts, regime_pub, fri_close, point  (+ scryer-style metadata)

  - data/processed/mondrian_artefact_v2.json      audit-trail sidecar with
      the 12 trained quantiles q_r(tau), 4 OOS-fit c(tau) bumps, and 4
      delta-shift-schedule entries — duplicates the constants hardcoded in
      src/soothsayer/oracle.py and crates/soothsayer-oracle/src/config.rs.

The constants are hardcoded in serving code (Python and Rust) so the live
serving path doesn't depend on a parquet read for the 20 deployment scalars;
the JSON sidecar is the audit trail and the parity-check input.

References:
  - reports/methodology_history.md (2026-05-02 M5 entry)
  - reports/paper1_coverage_inversion/07_ablation.md §7.7
  - reports/tables/v1b_mondrian_calibration.csv (M5_mondrian_deployable rows)
  - reports/tables/v1b_mondrian_delta_sweep.csv (delta selection)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.config import DATA_PROCESSED


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95, 0.99)
REGIMES = ("normal", "long_weekend", "high_vol")
SCHEMA_VERSION = "mondrian.v1"
ARTEFACT_PARQUET = DATA_PROCESSED / "mondrian_artefact_v2.parquet"
ARTEFACT_JSON = DATA_PROCESSED / "mondrian_artefact_v2.json"

# delta-shift schedule selected by `scripts/run_mondrian_delta_sweep.py` on
# the 6-split walk-forward — smallest schedule that aligns walk-forward
# realised coverage with nominal at each anchor.
DELTA_SHIFT_SCHEDULE: dict[float, float] = {
    0.68: 0.05,
    0.85: 0.02,
    0.95: 0.00,
    0.99: 0.00,
}


def _train_quantile(scores: np.ndarray, tau: float) -> float:
    """Split-CP finite-sample quantile: rank ceil(tau*(n+1)) of the sorted
    scores. Mirrors `calibrate_mondrian` in run_mondrian_regime_baseline.py."""
    n = scores.size
    if n == 0:
        return float("nan")
    k = int(np.ceil(tau * (n + 1)))
    k = min(max(k, 1), n)
    return float(np.sort(scores)[k - 1])


def _fit_c_bump(
    scores_oos: np.ndarray,
    b_per_row: np.ndarray,
    tau: float,
    grid: np.ndarray,
) -> float:
    """Smallest c in `grid` with mean(score <= b * c) >= tau on OOS rows.
    Mirrors `calibrate_mondrian_deployable` in the baseline script."""
    valid = np.isfinite(b_per_row) & np.isfinite(scores_oos)
    s = scores_oos[valid]
    b = b_per_row[valid]
    for c in grid:
        if float(np.mean(s <= b * c)) >= tau:
            return float(c)
    return float(grid[-1])


def main() -> None:
    panel_path = DATA_PROCESSED / "v1b_panel.parquet"
    if not panel_path.exists():
        raise FileNotFoundError(
            f"{panel_path} not found. Run `uv run python scripts/run_calibration.py` "
            "first to materialise the v1b panel."
        )
    panel = pd.read_parquet(panel_path)
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)

    # M5 point estimator: factor-adjusted Friday close (§7.4 switchboard).
    panel["point"] = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    # Conformity score: relative absolute residual.
    panel["score"] = (
        (panel["mon_open"].astype(float) - panel["point"]).abs()
        / panel["fri_close"].astype(float)
    )

    train = panel[panel["fri_ts"] < SPLIT_DATE].dropna(subset=["score"])
    oos = panel[panel["fri_ts"] >= SPLIT_DATE].copy()

    print(f"Train: {len(train):,} rows × {train['fri_ts'].nunique()} weekends")
    print(f"OOS:   {len(oos):,} rows × {oos['fri_ts'].nunique()} weekends")
    print()

    # --- Step 1: trained per-regime quantiles q_r(tau)
    quantile_table: dict[str, dict[float, float]] = {r: {} for r in REGIMES}
    for r in REGIMES:
        scores_r = train.loc[train["regime_pub"] == r, "score"].to_numpy(float)
        for tau in TARGETS:
            quantile_table[r][tau] = _train_quantile(scores_r, tau)

    print("Trained per-regime quantiles q_r(tau):")
    for r in REGIMES:
        cells = "  ".join(
            f"τ={tau:.2f}: {quantile_table[r][tau]:.6f}" for tau in TARGETS
        )
        print(f"  {r:>14}  {cells}")
    print()

    # --- Step 2: OOS-fit c(tau) bumps (one scalar per anchor)
    c_grid = np.arange(1.0, 5.0001, 0.001)
    c_bump_schedule: dict[float, float] = {}
    oos_ok = oos.dropna(subset=["score"]).copy()
    for tau in TARGETS:
        b_per_row = np.array(
            [quantile_table[r][tau] for r in oos_ok["regime_pub"]],
            dtype=float,
        )
        c_bump_schedule[tau] = _fit_c_bump(
            oos_ok["score"].to_numpy(float), b_per_row, tau, c_grid
        )

    print("OOS-fit c(tau) bumps:")
    for tau in TARGETS:
        print(f"  τ={tau:.2f}: c={c_bump_schedule[tau]:.4f}")
    print()
    print("delta-shift schedule (from run_mondrian_delta_sweep.py):")
    for tau in TARGETS:
        print(f"  τ={tau:.2f}: δ={DELTA_SHIFT_SCHEDULE[tau]:.3f}")
    print()

    # --- Step 3: per-Friday lookup parquet
    rows = panel[["symbol", "fri_ts", "regime_pub", "fri_close", "point"]].copy()
    rows["_schema_version"] = SCHEMA_VERSION
    rows["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    rows["_source"] = "scripts/build_mondrian_artefact.py"
    rows = rows.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)
    rows.to_parquet(ARTEFACT_PARQUET, index=False)
    print(f"Wrote {ARTEFACT_PARQUET}  ({len(rows):,} rows, "
          f"{rows['symbol'].nunique()} symbols, "
          f"{rows['fri_ts'].nunique()} weekends)")

    # --- Step 4: JSON sidecar with the 12 + 4 + 4 deployment scalars
    sidecar = {
        "_schema_version": SCHEMA_VERSION,
        "_fetched_at": datetime.now(timezone.utc).isoformat(),
        "_source": "scripts/build_mondrian_artefact.py",
        "split_date": SPLIT_DATE.isoformat(),
        "targets": list(TARGETS),
        "regimes": list(REGIMES),
        "regime_quantile_table": {
            r: {f"{tau:.2f}": quantile_table[r][tau] for tau in TARGETS}
            for r in REGIMES
        },
        "c_bump_schedule": {f"{tau:.2f}": c_bump_schedule[tau] for tau in TARGETS},
        "delta_shift_schedule": {f"{tau:.2f}": DELTA_SHIFT_SCHEDULE[tau] for tau in TARGETS},
        "n_train": int(len(train)),
        "n_oos": int(len(oos_ok)),
    }
    ARTEFACT_JSON.write_text(json.dumps(sidecar, indent=2) + "\n")
    print(f"Wrote {ARTEFACT_JSON}")


if __name__ == "__main__":
    main()
