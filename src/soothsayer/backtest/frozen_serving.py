"""
Frozen-artefact serving — shared by the forward-tape evaluator and the
band-archive emitter.

Loads a frozen LWC artefact sidecar (constants ONLY — no re-fitting) and
applies the frozen serving formula to a panel. Extracted verbatim from
`scripts/run_forward_tape_evaluation.py` (Phase 4.3) so the weekly
evaluation report and the public band archive are served by the same
code path and cannot drift.

Critical contract: nothing here may touch the frozen artefact's
constants. The frozen `regime_quantile_table`, `c_bump_schedule`, and
`delta_shift_schedule` from the JSON sidecar are the only inputs to the
serving formula. σ̂_sym(t) for forward weekends is recomputed (it's a
trailing window; can't be frozen) but uses the same rule and min_obs as
the artefact build, dispatched off the sidecar's `sigma_hat` block.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    SIGMA_HAT_K,
    SIGMA_HAT_MIN,
    add_sigma_hat_sym,
    add_sigma_hat_sym_blend,
    add_sigma_hat_sym_ewma,
)
from soothsayer.config import DATA_PROCESSED


def load_frozen(suffix: str | None = None) -> tuple[Path, dict]:
    """Locate + parse the frozen artefact JSON sidecar.

    `suffix` is the YYYYMMDD freeze date; None selects the latest by
    filename sort (the auto-discovery glob STATUS.md documents).
    """
    if suffix is not None:
        path = DATA_PROCESSED / f"lwc_artefact_v1_frozen_{suffix}.json"
        if not path.exists():
            raise FileNotFoundError(f"Frozen artefact not found: {path}")
    else:
        candidates = sorted(DATA_PROCESSED.glob("lwc_artefact_v1_frozen_*.json"))
        if not candidates:
            raise FileNotFoundError("No frozen artefact in data/processed/.")
        path = candidates[-1]
    return path, json.loads(path.read_text())


def apply_frozen_sigma_rule(panel: pd.DataFrame, sidecar: dict) -> pd.DataFrame:
    """Compute σ̂ on `panel` per the frozen artefact's σ̂ rule and surface the
    value under the canonical `sigma_hat_sym_pre_fri` column the rest of the
    serving formula reads.

    Dispatches on `sidecar["sigma_hat"]["method"]` so callers stay in sync
    with whichever variant the canonical artefact was built under. Older
    frozen sidecars (pre-Phase-5) lack the `sigma_hat` block; in that case
    fall back to the K=26 trailing-window default, matching pre-promotion
    behaviour. New frozen sidecars (post 2026-05-04) always include it.
    """
    sigma = sidecar.get("sigma_hat", {}) or {}
    method = sigma.get("method", "trailing_window")
    min_obs = int(sigma.get("min_past_obs", SIGMA_HAT_MIN))
    if method == "trailing_window":
        K = int(sigma.get("K_weekends", SIGMA_HAT_K))
        out = add_sigma_hat_sym(panel, K=K, min_obs=min_obs)
        return out
    if method == "ewma":
        hl = int(sigma["half_life_weekends"])
        out = add_sigma_hat_sym_ewma(panel, half_life=hl, min_obs=min_obs)
        out["sigma_hat_sym_pre_fri"] = out[f"sigma_hat_sym_ewma_pre_fri_hl{hl}"]
        return out
    if method == "blend":
        alpha = float(sigma["alpha"])
        hl = int(sigma["half_life_weekends"])
        K = int(sigma.get("K_weekends", SIGMA_HAT_K))
        out = add_sigma_hat_sym_blend(panel, alpha=alpha, half_life=hl,
                                      K=K, min_obs=min_obs)
        a_tag = int(round(alpha * 100))
        out["sigma_hat_sym_pre_fri"] = (
            out[f"sigma_hat_sym_blend_pre_fri_a{a_tag}_hl{hl}"]
        )
        return out
    raise ValueError(f"Unknown σ̂ method {method!r} in frozen sidecar.")


def frozen_schedules(sidecar: dict) -> tuple[dict, dict, dict]:
    """Pull the three frozen schedules out of the JSON sidecar with the
    {regime → {τ → b}} / {τ → c} / {τ → δ} shapes that `serve_frozen`
    expects."""
    quantile_table = {
        regime: {float(tau): float(b) for tau, b in row.items()}
        for regime, row in sidecar["regime_quantile_table"].items()
    }
    c_bump_schedule = {
        float(tau): float(c)
        for tau, c in sidecar["c_bump_schedule"].items()
    }
    delta_shift_schedule = {
        float(tau): float(d)
        for tau, d in sidecar["delta_shift_schedule"].items()
    }
    return quantile_table, c_bump_schedule, delta_shift_schedule


def interp(table: dict[float, float], x: float) -> float:
    """Piecewise-linear interpolation over a {x → y} anchor table, clamped
    at the endpoints."""
    keys = sorted(table.keys())
    if x <= keys[0]:
        return float(table[keys[0]])
    if x >= keys[-1]:
        return float(table[keys[-1]])
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= x <= hi:
            frac = (x - lo) / (hi - lo)
            return float(table[lo] + frac * (table[hi] - table[lo]))
    return float(table[keys[-1]])


def serve_frozen(
    panel: pd.DataFrame,
    qt: dict, cb: dict, delta: dict,
    taus: tuple[float, ...] = DEFAULT_TAUS,
) -> dict[float, pd.DataFrame]:
    """Apply the frozen LWC serving formula. Identical to
    `calibration.serve_bands_lwc` but reads schedules from the JSON
    sidecar (not the module-level LWC_* runtime tables) so callers are
    immune to live-artefact updates between freeze and evaluation."""
    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    fri_close = panel["fri_close"].astype(float).to_numpy()
    sigma = panel["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    cells = panel["regime_pub"].astype(str).to_numpy()
    out: dict[float, pd.DataFrame] = {}
    anchors = sorted(cb.keys())
    for tau in taus:
        d = float(delta.get(tau, 0.0))
        served = min(tau + d, anchors[-1])
        c = interp(cb, served)
        b_per_row = np.array([
            interp(qt[c_], served) if c_ in qt else np.nan
            for c_ in cells
        ], dtype=float)
        # Rows whose regime is unknown to the frozen table (shouldn't
        # happen given the panel's regime classifier matches the
        # frozen one, but defensive): fall back to high_vol if known.
        unk = ~np.isfinite(b_per_row)
        if unk.any() and "high_vol" in qt:
            b_per_row[unk] = interp(qt["high_vol"], served)
        q_eff = c * b_per_row
        half = q_eff * sigma * fri_close
        out[tau] = pd.DataFrame(
            {"lower": point.values - half, "upper": point.values + half},
            index=panel.index,
        )
    return out
