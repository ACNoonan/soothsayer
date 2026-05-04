"""
Calibration helpers for the M5 (Mondrian split-conformal by regime) build
and the M6 (Locally-Weighted Conformal) build.

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

It also exposes the M6 (LWC) primitives that share the same shape:

  - add_sigma_hat_sym         -- pre-Friday trailing relative-residual std
  - compute_score_lwc         -- standardised score |y - p̂| / (fri_close · σ̂)
  - train_lwc_quantile_table  -- finite-sample CP quantile on standardised scores
  - serve_bands_lwc           -- vectorised LWC serve, de-standardising back

`cell_col` is the conformal partition: "regime_pub" for the AMM/M6 profile
and "vol_tertile_cell" for the §10.2 vol-tertile sub-split robustness check.

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

# M6 (LWC) σ̂_sym window. Trailing K=26 weekend observations of relative
# residual std per symbol, requiring at least SIGMA_HAT_MIN past obs.
# Validated in `reports/v3_bakeoff.md` (Candidate 1) — the warm-up filter
# drops ~80 rows at panel start. Both constants must match the bake-off
# values exactly so the M6 quantiles reproduce the bake-off receipts.
SIGMA_HAT_K: int = 26
SIGMA_HAT_MIN: int = 8

# Phase 5 EWMA σ̂ variant — fast-reacting σ̂ aimed at the 2021/2022 split-date
# Christoffersen rejections (M6_REFACTOR.md §5). Half-life HL_WEEKENDS sets the
# weekend-decay rate λ via λ = 0.5 ** (1 / HL). Same warm-up rule as the K=26
# baseline (≥ SIGMA_HAT_MIN past obs) so variants share evaluable rows.
SIGMA_HAT_EWMA_HALF_LIVES: tuple[int, ...] = (6, 8, 12)
# Convex-blend variant: α · σ̂_K26 + (1−α) · σ̂_EWMA_HL8 with α=0.5 (smoothing
# knob exploratory point, matches Phase 5.1 brief).
SIGMA_HAT_BLEND_ALPHA: float = 0.5
SIGMA_HAT_BLEND_HL: int = 8


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


# ----------------------------------------------------------- M6 (LWC) helpers


def add_sigma_hat_sym(
    panel: pd.DataFrame,
    K: int = SIGMA_HAT_K,
    min_obs: int = SIGMA_HAT_MIN,
) -> pd.DataFrame:
    """Add `rel_resid` and `sigma_hat_sym_pre_fri` columns to `panel`.

    `sigma_hat_sym_pre_fri[i]` is the standard deviation of the trailing K
    relative residuals for that symbol, computed strictly from rows with
    `fri_ts' < fri_ts[i]`. Rows with fewer than `min_obs` past observations
    get NaN (the warm-up boundary).

    Returns a new DataFrame with the original ordering preserved (sorted
    intermediately by (symbol, fri_ts) for the rolling window, then
    reindexed back to the input order).

    Mirrors `add_sigma_hat` in `scripts/run_v3_bakeoff.py` — the function
    that produced the C1 LWC numerics in `reports/v3_bakeoff.md`."""
    work = panel.copy()
    work["rel_resid"] = (
        (work["mon_open"].astype(float)
         - work["fri_close"].astype(float) * (1.0 + work["factor_ret"].astype(float)))
        / work["fri_close"].astype(float)
    )
    sigma = np.full(len(work), np.nan)
    # groupby preserves the original row labels in `idx` even after a sort.
    sorted_view = work.sort_values(["symbol", "fri_ts"])
    for _, idx in sorted_view.groupby("symbol", sort=False).groups.items():
        sub = sorted_view.loc[idx]
        rr = sub["rel_resid"].to_numpy(float)
        for i, src_idx in enumerate(idx):
            lo = max(0, i - K)
            past = rr[lo:i]
            past = past[np.isfinite(past)]
            if past.size < min_obs:
                continue
            sigma[src_idx] = float(np.std(past, ddof=1))
    work["sigma_hat_sym_pre_fri"] = sigma
    return work


def add_sigma_hat_sym_ewma(
    panel: pd.DataFrame,
    half_life: int,
    min_obs: int = SIGMA_HAT_MIN,
) -> pd.DataFrame:
    """Add `rel_resid` and `sigma_hat_sym_ewma_pre_fri_hl{N}` columns to `panel`.

    EWMA estimator on per-symbol relative residuals with weekend half-life
    `half_life`. The decay rate is λ = 0.5 ** (1 / half_life) so observations
    `half_life` weekends in the past contribute half the weight of the most
    recent. Strictly pre-Friday: σ̂[i] uses only rows with `fri_ts' < fri_ts[i]`.
    Rows with fewer than `min_obs` past observations get NaN (warm-up boundary;
    same rule as `add_sigma_hat_sym` so variants are comparable on identical
    rows).

    The reported σ̂ is the EWMA *standard deviation* — sqrt of the weighted
    mean of squared residuals (residuals already have ~zero mean by the §7.4
    factor switchboard, so no de-meaning step). Mirrors the conventional
    RiskMetrics-style EWMA volatility estimator used in financial-econometrics
    backtests.

    Validates the Phase 5 σ̂ fast-reacting variant brief (M6_REFACTOR.md §5.1).
    """
    if half_life <= 0:
        raise ValueError(f"half_life must be positive, got {half_life}")
    work = panel.copy()
    if "rel_resid" not in work.columns:
        work["rel_resid"] = (
            (work["mon_open"].astype(float)
             - work["fri_close"].astype(float) * (1.0 + work["factor_ret"].astype(float)))
            / work["fri_close"].astype(float)
        )
    decay = 0.5 ** (1.0 / float(half_life))
    sigma = np.full(len(work), np.nan)
    sorted_view = work.sort_values(["symbol", "fri_ts"])
    for _, idx in sorted_view.groupby("symbol", sort=False).groups.items():
        sub = sorted_view.loc[idx]
        rr = sub["rel_resid"].to_numpy(float)
        for i, src_idx in enumerate(idx):
            past = rr[:i]
            past = past[np.isfinite(past)]
            if past.size < min_obs:
                continue
            # Weights decay backwards from the most recent past observation:
            # weight[t-1] = 1, weight[t-2] = decay, weight[t-3] = decay**2, ...
            ages = np.arange(past.size - 1, -1, -1, dtype=float)
            weights = decay ** ages
            weights /= weights.sum()
            mean_sq = float(np.sum(weights * past * past))
            sigma[src_idx] = float(np.sqrt(mean_sq))
    work[f"sigma_hat_sym_ewma_pre_fri_hl{half_life}"] = sigma
    return work


def add_sigma_hat_sym_blend(
    panel: pd.DataFrame,
    alpha: float = SIGMA_HAT_BLEND_ALPHA,
    half_life: int = SIGMA_HAT_BLEND_HL,
    K: int = SIGMA_HAT_K,
    min_obs: int = SIGMA_HAT_MIN,
) -> pd.DataFrame:
    """Convex blend of K-window σ̂ and EWMA σ̂.

    σ̂_blend = α · σ̂_K + (1 − α) · σ̂_EWMA_HL

    Adds `sigma_hat_sym_blend_pre_fri_a{a}_hl{N}` to `panel`. Both component
    σ̂s are pre-Friday and share the `min_obs` warm-up rule so the blend is
    well-defined whenever both components are. Convex with α ∈ [0, 1]; α=0.5
    matches the Phase 5.1 exploratory point."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha}")
    work = panel.copy()
    if "sigma_hat_sym_pre_fri" not in work.columns:
        work = add_sigma_hat_sym(work, K=K, min_obs=min_obs)
    ewma_col = f"sigma_hat_sym_ewma_pre_fri_hl{half_life}"
    if ewma_col not in work.columns:
        work = add_sigma_hat_sym_ewma(work, half_life=half_life, min_obs=min_obs)
    s_k = work["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    s_e = work[ewma_col].astype(float).to_numpy()
    blend = alpha * s_k + (1.0 - alpha) * s_e
    a_tag = int(round(alpha * 100))
    work[f"sigma_hat_sym_blend_pre_fri_a{a_tag}_hl{half_life}"] = blend
    return work


def compute_score_lwc(
    panel: pd.DataFrame,
    scale_col: str = "sigma_hat_sym_pre_fri",
) -> pd.Series:
    """M6 conformity score: relative absolute residual standardised by σ̂_sym.

    score_lwc = |mon_open - point| / (fri_close · σ̂_sym_pre_fri)

    `panel` must already have the column named by `scale_col` (default
    `sigma_hat_sym_pre_fri` from `add_sigma_hat_sym`; pass an EWMA column
    such as `sigma_hat_sym_ewma_pre_fri_hl8` for the Phase 5 variants).
    Rows with NaN / non-positive σ̂ return NaN."""
    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    abs_resid_rel = (
        (panel["mon_open"].astype(float) - point).abs()
        / panel["fri_close"].astype(float)
    )
    sigma = panel[scale_col].astype(float)
    out = abs_resid_rel / sigma
    out[~(sigma > 0)] = np.nan
    return out


def train_lwc_quantile_table(
    panel: pd.DataFrame,
    train_mask: pd.Series | np.ndarray,
    regime_col: str = "regime_pub",
    scale_col: str = "sigma_hat_sym_pre_fri",
    anchors: tuple[float, ...] = DEFAULT_TAUS,
    score_col: str = "score_lwc",
) -> dict[str, dict[float, float]]:
    """Per-regime finite-sample CP quantile q_r^LWC(τ) on standardised scores.

    Inputs:
      - panel: must have `regime_col` and `score_col`. If `score_col` is not
        present, the function computes it from `mon_open / fri_close /
        factor_ret / scale_col`.
      - train_mask: row mask (boolean Series or ndarray) selecting the training
        slice. Same convention as M5's `panel_train` argument.
      - regime_col: cell axis. M6 uses "regime_pub" (3 cells), matching M5's
        AMM profile.
      - scale_col: column holding σ̂_sym (default "sigma_hat_sym_pre_fri").
        Used only if `score_col` is absent (we'd then need it to compute the
        standardised score). When `score_col` is present, this argument is
        not read.
      - anchors: served τ grid.

    Returns a {regime → {τ → q_r^LWC(τ)}} dict, identical shape to
    `train_quantile_table`. The serve-time half-width is `q · σ̂ · fri_close`."""
    work = panel.copy()
    if score_col not in work.columns:
        if scale_col not in work.columns:
            raise ValueError(
                f"Neither score_col={score_col!r} nor scale_col={scale_col!r} "
                "found in panel. Run add_sigma_hat_sym() first or pass a panel "
                "with the score column already computed."
            )
        work[score_col] = compute_score_lwc(work)
    if isinstance(train_mask, pd.Series):
        train_mask = train_mask.to_numpy(bool)
    train = work[np.asarray(train_mask, dtype=bool)]
    return train_quantile_table(
        train, cell_col=regime_col, taus=anchors, score_col=score_col
    )


def serve_bands_lwc(
    panel: pd.DataFrame,
    quantile_table: dict[str, dict[float, float]],
    c_bump_schedule: dict[float, float],
    cell_col: str = "regime_pub",
    scale_col: str = "sigma_hat_sym_pre_fri",
    taus: tuple[float, ...] = DEFAULT_TAUS,
    delta_shift_schedule: dict[float, float] | None = None,
) -> dict[float, pd.DataFrame]:
    """Apply the M6 (LWC) serving formula across `taus`.

    For each τ:
        τ' = τ + δ(τ)
        q_eff = c(τ') · q_cell^LWC(τ')                       (unitless)
        half_width = q_eff · σ̂_sym(t) · fri_close            (price units)
        lower / upper = point ∓ half_width                   (point = factor-adjusted)

    Symmetric formula relative to fri_close — matches the conformity score
    `|mon_open - point| / (fri_close · σ̂)` used to fit q. Returns
    `{τ: DataFrame(lower, upper)}` keyed by `panel.index`.

    `delta_shift_schedule` defaults to the deployed M6 LWC schedule
    (`oracle.LWC_DELTA_SHIFT_SCHEDULE`); pass an empty dict to suppress
    δ-shift (the in-sample reading)."""
    if delta_shift_schedule is None:
        from soothsayer.oracle import LWC_DELTA_SHIFT_SCHEDULE
        delta_shift_schedule = LWC_DELTA_SHIFT_SCHEDULE

    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    fri_close = panel["fri_close"].astype(float).to_numpy()
    sigma = panel[scale_col].astype(float).to_numpy()
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
        # Off-grid τ within the per-cell row: linearly interpolate.
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
        half = q_eff * sigma * fri_close
        out[tau] = pd.DataFrame(
            {"lower": point.values - half, "upper": point.values + half},
            index=panel.index,
        )
    return out


# --------------------------------------------- forecaster-aware dispatchers


# Public alias for the supported forecasters in the §10 robustness scripts.
# "m5" = Mondrian split-conformal by regime (deployed); "lwc" = M6 Locally-
# Weighted Conformal. See `M6_REFACTOR.md` Phase 2 for the full validation
# battery this dispatcher serves.
FORECASTERS = ("m5", "lwc")


def prep_panel_for_forecaster(
    panel: pd.DataFrame,
    forecaster: str,
) -> pd.DataFrame:
    """Materialise the columns the forecaster's fit/serve path needs.

    M5: adds a `score` column (relative absolute residual) — the existing
        downstream code already expects this.
    LWC: adds `sigma_hat_sym_pre_fri` (trailing K=26 weekend residual std,
        strictly pre-Friday) and writes the standardised LWC score into
        the same `score` column. Rows without a defined σ̂ (warm-up) get
        NaN scores and are dropped by downstream `dropna(subset=["score"])`.

    Returns a new DataFrame with the original index preserved (or reset to
    a fresh range index — caller can rely on the row order being unchanged
    relative to the input).

    By writing both forecasters' active score into the column literally
    named `score`, the §10 runners need only swap `prep_panel_for_forecaster`
    for `compute_score`; their existing `dropna(subset=["score"])` filters
    keep working unchanged."""
    if forecaster not in FORECASTERS:
        raise ValueError(
            f"forecaster must be one of {FORECASTERS}, got {forecaster!r}"
        )
    work = panel.copy()
    if forecaster == "m5":
        work["score"] = compute_score(work)
        return work
    # forecaster == "lwc"
    work = add_sigma_hat_sym(work)
    work["score"] = compute_score_lwc(work)
    return work


def fit_split_conformal_forecaster(
    panel: pd.DataFrame,
    split_date: date,
    forecaster: str,
    cell_col: str = "regime_pub",
    taus: tuple[float, ...] = DEFAULT_TAUS,
) -> tuple[dict[str, dict[float, float]], dict[float, float], dict]:
    """Forecaster-aware `fit_split_conformal`.

    Both forecasters use the same conformal cell partition (`cell_col`) and
    the same finite-sample CP rank formula. They differ only in the score
    they read — which `prep_panel_for_forecaster` has already written into
    `panel["score"]`. So this is a thin wrapper that delegates to the
    existing `fit_split_conformal`."""
    if forecaster not in FORECASTERS:
        raise ValueError(
            f"forecaster must be one of {FORECASTERS}, got {forecaster!r}"
        )
    if "score" not in panel.columns:
        raise ValueError(
            "panel is missing the 'score' column — call "
            "prep_panel_for_forecaster() first."
        )
    qt, cb, info = fit_split_conformal(
        panel, split_date, cell_col=cell_col, taus=taus
    )
    info["forecaster"] = forecaster
    return qt, cb, info


def serve_bands_forecaster(
    panel: pd.DataFrame,
    quantile_table: dict[str, dict[float, float]],
    c_bump_schedule: dict[float, float],
    forecaster: str,
    cell_col: str = "regime_pub",
    taus: tuple[float, ...] = DEFAULT_TAUS,
    delta_shift_schedule: dict[float, float] | None = None,
) -> dict[float, pd.DataFrame]:
    """Forecaster-aware `serve_bands`.

    M5: legacy point-relative band (`point ± q·point`); δ defaults to the
        deployed M5 `DELTA_SHIFT_SCHEDULE`.
    LWC: σ̂-scaled band (`point ± q·σ̂·fri_close`); δ defaults to the
        deployed M6 `LWC_DELTA_SHIFT_SCHEDULE`. Panel must have
        `sigma_hat_sym_pre_fri` (already added by `prep_panel_for_forecaster`)."""
    if forecaster == "m5":
        return serve_bands(
            panel, quantile_table, c_bump_schedule,
            cell_col=cell_col, taus=taus,
            delta_shift_schedule=delta_shift_schedule,
        )
    if forecaster == "lwc":
        return serve_bands_lwc(
            panel, quantile_table, c_bump_schedule,
            cell_col=cell_col, taus=taus,
            delta_shift_schedule=delta_shift_schedule,
        )
    raise ValueError(
        f"forecaster must be one of {FORECASTERS}, got {forecaster!r}"
    )


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
