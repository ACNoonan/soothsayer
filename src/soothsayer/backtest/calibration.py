"""
Calibration helpers for the M5 (Mondrian split-conformal by regime) build.

Under v2 (paper 1 §7.7), the deployed Oracle reads
`data/processed/mondrian_artefact_v2.parquet` and serves a band via
per-regime conformal quantile + δ-shifted c(τ) bump. The v1 calibration-
surface API (`compute_calibration_surface`, `pooled_surface`, `invert`) was
removed in the M5 refactor.

This module exposes the M5 fit/serve primitives that the deployed pipeline
and the §10 robustness checks both share (`scripts/run_v1b_*` scripts):

  - compute_score        -- relative absolute residual = |y - p̂| / fri_close
  - train_quantile_table -- finite-sample CP quantile per (cell × τ) on TRAIN
  - fit_c_bump_schedule  -- smallest c with mean(score ≤ b·c) ≥ τ on OOS
  - serve_bands          -- vectorised serving formula for a (cell, τ) grid

`cell_col` is the conformal partition: "regime_pub" for the AMM profile and
"vol_tertile_cell" for the §10.2 vol-tertile sub-split robustness check.

The legacy `build_bounds_table` is retained for archived v1 diagnostic
scripts under `scripts/v1_archive/`.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


# Default M5 budget: four served τ anchors. Match
# `scripts/build_mondrian_artefact.py` and `src/soothsayer/oracle.py`.
DEFAULT_TAUS: tuple[float, ...] = (0.68, 0.85, 0.95, 0.99)


def compute_score(panel: pd.DataFrame) -> pd.Series:
    """M5 conformity score: relative absolute residual.

    point = fri_close * (1 + factor_ret)   (the §7.4 factor switchboard)
    score = |mon_open - point| / fri_close

    Caller is responsible for passing the unfiltered panel; rows with NaN
    in any input return NaN scores."""
    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    return (
        (panel["mon_open"].astype(float) - point).abs()
        / panel["fri_close"].astype(float)
    )


def train_quantile_table(
    panel_train: pd.DataFrame,
    cell_col: str,
    taus: tuple[float, ...] = DEFAULT_TAUS,
    score_col: str = "score",
) -> dict[str, dict[float, float]]:
    """Per-cell finite-sample CP quantile q_cell(τ).

    Rank ceil(τ·(n+1)) of the sorted scores within each cell. Mirrors
    `_train_quantile` in `scripts/build_mondrian_artefact.py`."""
    out: dict[str, dict[float, float]] = {}
    for cell, g in panel_train.groupby(cell_col):
        scores = g[score_col].dropna().to_numpy(float)
        n = scores.size
        if n == 0:
            out[str(cell)] = {tau: float("nan") for tau in taus}
            continue
        sorted_scores = np.sort(scores)
        row: dict[float, float] = {}
        for tau in taus:
            k = int(np.ceil(tau * (n + 1)))
            k = min(max(k, 1), n)
            row[tau] = float(sorted_scores[k - 1])
        out[str(cell)] = row
    return out


def fit_c_bump_schedule(
    panel_oos: pd.DataFrame,
    quantile_table: dict[str, dict[float, float]],
    cell_col: str,
    taus: tuple[float, ...] = DEFAULT_TAUS,
    grid: np.ndarray | None = None,
    score_col: str = "score",
) -> dict[float, float]:
    """Smallest c on `grid` with mean(score ≤ b_cell(τ) · c) ≥ τ on OOS rows.

    Mirrors `_fit_c_bump` in `scripts/build_mondrian_artefact.py`. If no c on
    the grid achieves the target, returns the largest grid value (conservative
    fallback)."""
    if grid is None:
        grid = np.arange(1.0, 5.0001, 0.001)
    out: dict[float, float] = {}
    cells = panel_oos[cell_col].astype(str).to_numpy()
    scores = panel_oos[score_col].to_numpy(float)
    for tau in taus:
        b_per_row = np.array(
            [quantile_table.get(c, {}).get(tau, np.nan) for c in cells],
            dtype=float,
        )
        mask = np.isfinite(b_per_row) & np.isfinite(scores)
        s = scores[mask]
        b = b_per_row[mask]
        if s.size == 0:
            out[tau] = float(grid[-1])
            continue
        chosen = float(grid[-1])
        for c in grid:
            if float(np.mean(s <= b * c)) >= tau:
                chosen = float(c)
                break
        out[tau] = chosen
    return out


def serve_bands(
    panel: pd.DataFrame,
    quantile_table: dict[str, dict[float, float]],
    c_bump_schedule: dict[float, float],
    cell_col: str,
    taus: tuple[float, ...] = DEFAULT_TAUS,
    delta_shift_schedule: dict[float, float] | None = None,
) -> dict[float, pd.DataFrame]:
    """Apply the M5 serving formula across `taus`.

    For each τ: τ' = τ + δ(τ), q = c(τ') · b_cell(τ'), and the band is
    centred on point = fri_close * (1 + factor_ret) with symmetric width
    q · point. Returns {τ: DataFrame(lower, upper)} keyed by `panel.index`.

    `delta_shift_schedule` defaults to the deployed
    `oracle.DELTA_SHIFT_SCHEDULE`. Pass an empty dict to suppress δ-shift
    (the in-sample reading)."""
    if delta_shift_schedule is None:
        # Local import to avoid a top-level cycle (oracle imports from
        # universe, which can read the lending sidecar at module import).
        from soothsayer.oracle import DELTA_SHIFT_SCHEDULE
        delta_shift_schedule = DELTA_SHIFT_SCHEDULE

    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    cells = panel[cell_col].astype(str).to_numpy()
    out: dict[float, pd.DataFrame] = {}
    anchors = sorted(c_bump_schedule.keys())

    def _interp(table: dict[float, float], x: float) -> float:
        if x <= anchors[0]:
            return float(table[anchors[0]])
        if x >= anchors[-1]:
            return float(table[anchors[-1]])
        for i in range(len(anchors) - 1):
            lo, hi = anchors[i], anchors[i + 1]
            if lo <= x <= hi:
                frac = (x - lo) / (hi - lo)
                return float(table[lo] + frac * (table[hi] - table[lo]))
        return float(table[anchors[-1]])

    for tau in taus:
        delta = float(delta_shift_schedule.get(tau, 0.0))
        served = min(tau + delta, anchors[-1])
        c = _interp(c_bump_schedule, served)
        b_per_row = np.array(
            [quantile_table.get(c_, {}).get(served, np.nan) for c_ in cells],
            dtype=float,
        )
        # Off-grid τ within the table: linearly interpolate per cell.
        if not np.all(np.isfinite(b_per_row)):
            for cell, row in quantile_table.items():
                if served not in row:
                    table_anchors = sorted(row.keys())
                    if not table_anchors:
                        continue
                    if served <= table_anchors[0]:
                        v = row[table_anchors[0]]
                    elif served >= table_anchors[-1]:
                        v = row[table_anchors[-1]]
                    else:
                        for i in range(len(table_anchors) - 1):
                            lo, hi = table_anchors[i], table_anchors[i + 1]
                            if lo <= served <= hi:
                                frac = (served - lo) / (hi - lo)
                                v = row[lo] + frac * (row[hi] - row[lo])
                                break
                    b_per_row[cells == cell] = v
        q_eff = c * b_per_row
        lower = point.values * (1.0 - q_eff)
        upper = point.values * (1.0 + q_eff)
        out[tau] = pd.DataFrame(
            {"lower": lower, "upper": upper}, index=panel.index
        )
    return out


def fit_split_conformal(
    panel: pd.DataFrame,
    split_date: date,
    cell_col: str = "regime_pub",
    taus: tuple[float, ...] = DEFAULT_TAUS,
) -> tuple[dict[str, dict[float, float]], dict[float, float], dict]:
    """One-shot M5 fit at an arbitrary `split_date`.

    Returns (quantile_table, c_bump_schedule, info) where `info` records the
    train/OOS sizes and split anchor — convenient for split-date sensitivity
    and LOSO CV."""
    work = panel.copy()
    if "score" not in work.columns:
        work["score"] = compute_score(work)
    work[cell_col] = work[cell_col].astype(str)

    train = work[work["fri_ts"] < split_date].dropna(subset=["score"])
    oos = work[work["fri_ts"] >= split_date].dropna(subset=["score"])

    qt = train_quantile_table(train, cell_col=cell_col, taus=taus)
    cb = fit_c_bump_schedule(oos, qt, cell_col=cell_col, taus=taus)
    info = {
        "split_date": split_date.isoformat(),
        "n_train": int(len(train)),
        "n_oos": int(len(oos)),
        "n_train_weekends": int(train["fri_ts"].nunique()),
        "n_oos_weekends": int(oos["fri_ts"].nunique()),
        "cell_col": cell_col,
        "cells": sorted(qt.keys()),
    }
    return qt, cb, info


def build_bounds_table(
    panel: pd.DataFrame,
    bounds_by_coverage: dict[float, pd.DataFrame],
    forecaster: str,
) -> pd.DataFrame:
    """Flatten {coverage: DataFrame(lower, upper)} into a long-form bounds table.

    Output columns: symbol, fri_ts, mon_ts, regime_pub, claimed, lower, upper,
                    mon_open, fri_close, forecaster.
    """
    rows = []
    for cov, band in bounds_by_coverage.items():
        m = band["lower"].notna() & band["upper"].notna()
        sub = panel.loc[m, ["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]].copy()
        sub["claimed"] = float(cov)
        sub["lower"] = band.loc[m, "lower"].values
        sub["upper"] = band.loc[m, "upper"].values
        sub["forecaster"] = forecaster
        rows.append(sub)
    if not rows:
        return pd.DataFrame(
            columns=["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open",
                     "fri_close", "claimed", "lower", "upper", "forecaster"]
        )
    out = pd.concat(rows, ignore_index=True)
    out.attrs.clear()  # avoid non-JSON-serializable .attrs on parquet write
    return out
