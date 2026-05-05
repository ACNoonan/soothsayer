"""
Build the M6b2 Lending-track deployment artefact — the Phase A1 successor to
the M5 Mondrian artefact along the symbol_class cell axis.

The Lending-track Oracle serves a band as

    point  = fri_close * (1 + factor_ret)                # §7.4 factor switchboard
    tau'   = tau + delta_shift_schedule(tau)             # walk-forward overshoot
    q      = c_bump_schedule(tau') * b(symbol_class, tau')
    lower  = point - q * fri_close,
    upper  = point + q * fri_close

The only thing M6b2 changes from M5 is the conformal cell axis: per-regime
quantile (3 cells × 4 anchors = 12 trained b's) becomes per-symbol_class
(6 cells × 4 anchors = 24 trained b's). Score, point estimator, OOS-fit
c(tau) bump, and walk-forward delta-shift schedule are all inherited
unchanged from M5.

This script produces two artefacts:

  - data/processed/m6b2_lending_artefact_v1.parquet   per-(symbol, fri_ts, target)
      lookup rows: symbol, fri_ts, mon_ts, regime_pub, symbol_class, point_fa,
      lower_tau, upper_tau, target  (+ scryer-style metadata).

  - data/processed/m6b2_lending_artefact_v1.json      audit-trail sidecar with
      the 24 trained quantiles b(symbol_class, tau), 4 OOS-fit c(tau) bumps,
      4 delta-shift-schedule entries, the symbol_class mapping, and per-cell
      train sample sizes.

The serving constants (24 b's + 4 c's + 4 deltas) get hardcoded into
src/soothsayer/oracle.py and crates/soothsayer-oracle/src/config.rs in
Phase A2 / A3. The JSON sidecar is the audit trail and parity-check input.

References:
  - reports/active/m6_refactor.md (Phase A1)
  - reports/v1b_m6b_per_symbol_class_mondrian.md   (reproduction target)
  - reports/methodology_history.md (2026-05-03 dual-profile entry)
  - scripts/build_mondrian_artefact.py             (M5 structural template)
  - scripts/run_m6b_per_symbol_class_mondrian.py   (M6b2 validation runner)
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.config import DATA_PROCESSED


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95, 0.99)
SCHEMA_VERSION = "m6b2.lending.v1"
ARTEFACT_PARQUET = DATA_PROCESSED / "m6b2_lending_artefact_v1.parquet"
ARTEFACT_JSON = DATA_PROCESSED / "m6b2_lending_artefact_v1.json"
SOURCE_TAG = "scripts/build_m6b2_lending_artefact.py"

# Locked symbol_class mapping (reports/active/m6_refactor.md A1).
# Matches scripts/run_m6b_per_symbol_class_mondrian.py SYMBOL_CLASS exactly.
SYMBOL_CLASS: dict[str, str] = {
    "SPY": "equity_index",
    "QQQ": "equity_index",
    "AAPL": "equity_meta",
    "GOOGL": "equity_meta",
    "NVDA": "equity_highbeta",
    "TSLA": "equity_highbeta",
    "MSTR": "equity_highbeta",
    "HOOD": "equity_recent",
    "GLD": "gold",
    "TLT": "bond",
}
CLASSES: tuple[str, ...] = (
    "equity_index",
    "equity_meta",
    "equity_highbeta",
    "equity_recent",
    "gold",
    "bond",
)
MIN_CELL_N = 30

# delta-shift schedule inherited unchanged from M5
# (scripts/build_mondrian_artefact.py / scripts/run_mondrian_delta_sweep.py).
DELTA_SHIFT_SCHEDULE: dict[float, float] = {
    0.68: 0.05,
    0.85: 0.02,
    0.95: 0.00,
    0.99: 0.00,
}


def _train_quantile(scores: np.ndarray, tau: float) -> float:
    """Split-CP finite-sample quantile: rank ceil(tau*(n+1)) of the sorted
    scores. Matches `_train_quantile` in scripts/build_mondrian_artefact.py
    and `_conformal_quantile` in scripts/run_m6b_per_symbol_class_mondrian.py."""
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
    Matches `_fit_c_bump` in scripts/build_mondrian_artefact.py."""
    valid = np.isfinite(b_per_row) & np.isfinite(scores_oos)
    s = scores_oos[valid]
    b = b_per_row[valid]
    for c in grid:
        if float(np.mean(s <= b * c)) >= tau:
            return float(c)
    return float(grid[-1])


def _panel_fetched_at(panel_path: Path) -> str:
    """Deterministic timestamp derived from the input panel's mtime, so
    re-runs against the same panel produce byte-identical artefacts."""
    mtime = int(panel_path.stat().st_mtime)
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    panel_path = DATA_PROCESSED / "v1b_panel.parquet"
    if not panel_path.exists():
        raise FileNotFoundError(
            f"{panel_path} not found. Run `uv run python scripts/run_calibration.py` "
            "first to materialise the v1b panel."
        )
    panel_fetched_at = _panel_fetched_at(panel_path)

    panel = pd.read_parquet(panel_path)
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    panel = panel.dropna(
        subset=["fri_close", "mon_open", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)

    # M5 / M6b2 point estimator: factor-adjusted Friday close.
    panel["point_fa"] = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    # Conformity score: relative absolute residual against fri_close.
    panel["score"] = (
        (panel["mon_open"].astype(float) - panel["point_fa"]).abs()
        / panel["fri_close"].astype(float)
    )
    panel["symbol_class"] = panel["symbol"].map(SYMBOL_CLASS)
    missing = panel.loc[panel["symbol_class"].isna(), "symbol"].unique().tolist()
    if missing:
        raise ValueError(
            f"Symbols not in SYMBOL_CLASS mapping: {missing}. "
            "reports/active/m6_refactor.md A1 requires the mapping to cover the full panel."
        )

    train = panel[panel["fri_ts"] < SPLIT_DATE].dropna(subset=["score"])
    oos = panel[panel["fri_ts"] >= SPLIT_DATE].copy()
    oos_ok = oos.dropna(subset=["score"]).copy()

    print(f"Train: {len(train):,} rows × {train['fri_ts'].nunique()} weekends")
    print(f"OOS:   {len(oos):,} rows × {oos['fri_ts'].nunique()} weekends")
    print()

    # --- Step 1: trained per-(symbol_class, tau) quantiles b
    quantile_table: dict[str, dict[float, float]] = {c: {} for c in CLASSES}
    n_train_per_class: dict[str, int] = {}
    for cls in CLASSES:
        scores_c = train.loc[train["symbol_class"] == cls, "score"].to_numpy(float)
        n_train_per_class[cls] = int(scores_c.size)
        if scores_c.size < MIN_CELL_N:
            print(
                f"WARNING: cell '{cls}' has n_train={scores_c.size} < "
                f"MIN_CELL_N={MIN_CELL_N}; quantile may be unstable."
            )
        for tau in TARGETS:
            quantile_table[cls][tau] = _train_quantile(scores_c, tau)

    print("Trained per-(symbol_class, tau) quantiles b:")
    header = f"  {'symbol_class':>16}  " + "  ".join(
        f"τ={tau:.2f}".rjust(11) for tau in TARGETS
    ) + "    n_train"
    print(header)
    for cls in CLASSES:
        cells = "  ".join(
            f"{quantile_table[cls][tau]:.6f}".rjust(11) for tau in TARGETS
        )
        print(f"  {cls:>16}  {cells}    {n_train_per_class[cls]:>4d}")
    print()

    # --- Step 2: OOS-fit c(tau) bumps (one scalar per anchor, pooled across cells)
    c_grid = np.arange(1.0, 5.0001, 0.001)
    c_bump_schedule: dict[float, float] = {}
    for tau in TARGETS:
        b_per_row = np.array(
            [quantile_table[c][tau] for c in oos_ok["symbol_class"]],
            dtype=float,
        )
        c_bump_schedule[tau] = _fit_c_bump(
            oos_ok["score"].to_numpy(float), b_per_row, tau, c_grid
        )

    print("OOS-fit c(tau) bumps:")
    for tau in TARGETS:
        print(f"  τ={tau:.2f}: c={c_bump_schedule[tau]:.4f}")
    print()
    print("delta-shift schedule (inherited from M5):")
    for tau in TARGETS:
        print(f"  τ={tau:.2f}: δ={DELTA_SHIFT_SCHEDULE[tau]:.3f}")
    print()

    # --- Step 3: per-(symbol, fri_ts, target) lookup parquet
    base_cols = ["symbol", "fri_ts", "mon_ts", "regime_pub", "symbol_class",
                 "fri_close", "point_fa"]
    pieces: list[pd.DataFrame] = []
    for tau in TARGETS:
        df_tau = panel[base_cols].copy()
        df_tau["b"] = df_tau["symbol_class"].map(
            lambda c, _tau=tau: quantile_table[c][_tau]
        ).astype(float)
        b_eff = df_tau["b"].to_numpy() * float(c_bump_schedule[tau])
        df_tau["lower_tau"] = (
            df_tau["point_fa"].to_numpy() - b_eff * df_tau["fri_close"].to_numpy()
        )
        df_tau["upper_tau"] = (
            df_tau["point_fa"].to_numpy() + b_eff * df_tau["fri_close"].to_numpy()
        )
        df_tau["target"] = float(tau)
        pieces.append(df_tau)
    rows = pd.concat(pieces, ignore_index=True)

    # Project to the prompt's canonical column set + deterministic metadata.
    out_cols = ["symbol", "fri_ts", "mon_ts", "regime_pub", "symbol_class",
                "point_fa", "lower_tau", "upper_tau", "target"]
    rows = rows[out_cols].copy()
    rows["_schema_version"] = SCHEMA_VERSION
    rows["_fetched_at"] = panel_fetched_at
    rows["_source"] = SOURCE_TAG
    rows = rows.sort_values(["symbol", "fri_ts", "target"]).reset_index(drop=True)

    # Schema-invariant gate (gate #4): lower < point < upper, no NaN classes.
    bad_band = rows[
        ~((rows["lower_tau"] < rows["point_fa"]) &
          (rows["point_fa"] < rows["upper_tau"]))
    ]
    if len(bad_band):
        raise ValueError(
            f"{len(bad_band)} rows violate lower < point < upper invariant"
        )
    if rows["symbol_class"].isna().any():
        raise ValueError("symbol_class column has NaN; mapping incomplete")

    rows.to_parquet(ARTEFACT_PARQUET, index=False)
    print(
        f"Wrote {ARTEFACT_PARQUET}  ({len(rows):,} rows, "
        f"{rows['symbol'].nunique()} symbols × {rows['fri_ts'].nunique()} weekends "
        f"× {len(TARGETS)} anchors)"
    )

    # --- Step 4: JSON sidecar with the 24 + 4 + 4 deployment scalars
    sidecar = {
        "_schema_version": SCHEMA_VERSION,
        "_fetched_at": panel_fetched_at,
        "_source": SOURCE_TAG,
        "methodology_version": "m6b2.lending.v1",
        "split_date": SPLIT_DATE.isoformat(),
        "targets": list(TARGETS),
        "classes": list(CLASSES),
        "symbol_class_mapping": dict(SYMBOL_CLASS),
        "class_quantile_table": {
            cls: {f"{tau:.2f}": quantile_table[cls][tau] for tau in TARGETS}
            for cls in CLASSES
        },
        "c_bump_schedule": {f"{tau:.2f}": c_bump_schedule[tau] for tau in TARGETS},
        "delta_shift_schedule": {
            f"{tau:.2f}": DELTA_SHIFT_SCHEDULE[tau] for tau in TARGETS
        },
        "n_train_per_class": dict(n_train_per_class),
        "n_train_total": int(len(train)),
        "n_oos_total": int(len(oos_ok)),
        "min_cell_n": MIN_CELL_N,
    }
    ARTEFACT_JSON.write_text(json.dumps(sidecar, indent=2, sort_keys=False) + "\n")
    print(f"Wrote {ARTEFACT_JSON}")
    print()

    # --- Step 5: numerical reproduction gate (gate #1)
    repro_targets = {
        0.68: (116.067, 0.680),
        0.85: (185.315, 0.850),
        0.95: (303.719, 0.950),
        0.99: (663.933, 0.990),
    }
    print("Pooled OOS reproduction vs reports/v1b_m6b_per_symbol_class_mondrian.md:")
    print(f"  {'tau':>6}  {'half_width_bps':>14}  {'target':>8}  "
          f"{'realised':>10}  {'tgt_real':>8}  {'flag':>6}")
    any_diverge = False
    for tau in TARGETS:
        b_per_row = np.array(
            [quantile_table[c][tau] for c in oos_ok["symbol_class"]], dtype=float,
        )
        b_eff = b_per_row * float(c_bump_schedule[tau])
        scores = oos_ok["score"].to_numpy(float)
        half_width_bps = float((b_eff * 1e4).mean())
        realised = float(np.mean(scores <= b_eff))
        tgt_hw, tgt_real = repro_targets[tau]
        diverge = (abs(half_width_bps - tgt_hw) > 1.0) or (abs(realised - tgt_real) > 0.001)
        flag = "DIVERGE" if diverge else "ok"
        any_diverge = any_diverge or diverge
        print(
            f"  τ={tau:.2f}  {half_width_bps:>14.3f}  {tgt_hw:>8.3f}  "
            f"{realised:>10.3f}  {tgt_real:>8.3f}  {flag:>6}"
        )
    if any_diverge:
        print("\nGATE #1 FAIL: numerical reproduction divergence > 1 bp / 0.001.")
    else:
        print("\nGATE #1 PASS: pooled OOS reproduction within tolerance.")
    print()

    # --- Step 6: artefact file metadata (gate #3 hash recording)
    parquet_size = ARTEFACT_PARQUET.stat().st_size
    json_size = ARTEFACT_JSON.stat().st_size
    parquet_sha = _sha256(ARTEFACT_PARQUET)
    json_sha = _sha256(ARTEFACT_JSON)
    print("Artefact file metadata:")
    print(f"  {ARTEFACT_PARQUET}")
    print(f"    bytes={parquet_size}  sha256={parquet_sha}")
    print(f"  {ARTEFACT_JSON}")
    print(f"    bytes={json_size}  sha256={json_sha}")


if __name__ == "__main__":
    main()
