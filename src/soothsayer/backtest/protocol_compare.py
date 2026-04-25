"""
Supplemental protocol-comparison utilities for Kamino-style lending tests.

These helpers intentionally sit beside the existing calibration/validation
scripts rather than replacing them. The goal is to evaluate lending decisions
under a calibrated band using:

1. A dense LTV grid near the governance thresholds.
2. A full 3-state decision confusion matrix (Safe / Caution / Liquidate).
3. Weekend-block bootstrap confidence intervals on deltas vs Kamino.
4. A simple decision-cost score so we can compare protocol behavior, not just
   interval coverage.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


SAFE = "Safe"
CAUTION = "Caution"
LIQUIDATE = "Liquidate"
DECISION_STATES = (SAFE, CAUTION, LIQUIDATE)

MAX_LTV_AT_ORIGINATION = 0.75
LIQUIDATION_THRESHOLD = 0.85
KAMINO_BPS = 300.0
DEFAULT_REGIME_MULTIPLIERS: dict[str, float] = {
    "normal": 1.00,
    "long_weekend": 0.95,
    "high_vol": 0.85,
}

# A simple, explicit cost matrix for ranking decision policies. The values are
# dimensionless "pain units" so analysts can rescale them later; only the
# relative ordering matters.
DEFAULT_COST_MATRIX: dict[tuple[str, str], float] = {
    (SAFE, SAFE): 0.00,
    (CAUTION, SAFE): 0.10,
    (LIQUIDATE, SAFE): 1.00,
    (SAFE, CAUTION): 0.15,
    (CAUTION, CAUTION): 0.00,
    (LIQUIDATE, CAUTION): 0.35,
    (SAFE, LIQUIDATE): 4.00,
    (CAUTION, LIQUIDATE): 2.50,
    (LIQUIDATE, LIQUIDATE): 0.00,
}

DEFAULT_WEIGHT_SCHEMES = (
    "uniform_ltv",
    "borrower_heavy",
    "threshold_heavy",
    "debt_weighted",
)
DEFAULT_TRUTH_MODES = ("economic_flat85", "policy_consistent")


@dataclass(frozen=True)
class ComparisonConfig:
    variant: str
    protocol: str
    target: float | None
    target_label: str
    demote_threshold: bool
    half_width_bps: float
    claim_served: float | None = None
    clipped_forces_caution: bool = False


def realized_truth_config(
    truth_mode: str,
    *,
    demote_threshold: bool,
    clipped_forces_caution: bool,
) -> dict[str, bool]:
    """Return the realized-policy semantics for a variant under a truth mode."""
    if truth_mode == "economic_flat85":
        return {"demote_threshold": False, "clipped_forces_caution": False}
    if truth_mode == "policy_consistent":
        return {
            "demote_threshold": demote_threshold,
            "clipped_forces_caution": clipped_forces_caution,
        }
    raise ValueError(f"unknown truth_mode: {truth_mode}")


def make_ltv_grid(
    start: float = 0.70,
    end: float = 0.90,
    step_bps: float = 25.0,
) -> np.ndarray:
    """Dense LTV grid in level units, inclusive of the end-point."""
    if step_bps <= 0:
        raise ValueError("step_bps must be positive")
    step = step_bps / 10_000.0
    count = int(round((end - start) / step))
    grid = start + np.arange(count + 1) * step
    if grid[-1] < end - 1e-12:
        grid = np.append(grid, end)
    return np.round(grid, 6)


def build_weight_lookup(
    ltv_grid: Iterable[float],
    *,
    weight_scheme: str,
    custom_weights_path: Path | None = None,
) -> dict[float, float]:
    """Normalized per-LTV weights for sensitivity analysis."""
    ltv = np.asarray(list(ltv_grid), dtype=float)
    if len(ltv) == 0:
        raise ValueError("ltv_grid cannot be empty")

    if weight_scheme == "uniform_ltv":
        raw = np.ones(len(ltv), dtype=float)
    elif weight_scheme == "borrower_heavy":
        raw = np.exp(-0.5 * ((ltv - 0.75) / 0.03) ** 2)
    elif weight_scheme == "threshold_heavy":
        raw = np.exp(-0.5 * ((ltv - 0.85) / 0.02) ** 2)
    elif weight_scheme == "debt_weighted":
        raw = ltv.copy()
    elif weight_scheme == "custom_csv":
        if custom_weights_path is None:
            raise ValueError("custom_weights_path is required for custom_csv weighting")
        custom = pd.read_csv(custom_weights_path)
        required = {"ltv_target", "weight"}
        if not required.issubset(custom.columns):
            raise ValueError("custom weight csv must contain ltv_target and weight columns")
        custom = custom.copy()
        custom["ltv_target"] = custom["ltv_target"].round(6)
        custom = custom.drop_duplicates(subset=["ltv_target"], keep="last")
        merged = pd.DataFrame({"ltv_target": np.round(ltv, 6)}).merge(
            custom[["ltv_target", "weight"]],
            on="ltv_target",
            how="left",
        )
        if merged["weight"].isna().any():
            missing = merged.loc[merged["weight"].isna(), "ltv_target"].tolist()
            raise ValueError(f"custom weight csv missing LTV rows: {missing[:5]}")
        raw = merged["weight"].to_numpy(dtype=float)
    else:
        raise ValueError(f"unknown weight_scheme: {weight_scheme}")

    if np.any(raw < 0):
        raise ValueError("weights must be non-negative")
    total = float(raw.sum())
    if total <= 0:
        raise ValueError("weights must sum to a positive value")
    normalized = raw / total
    return dict(zip(np.round(ltv, 6).tolist(), normalized.tolist(), strict=True))


def apply_weight_scheme(
    rows: pd.DataFrame,
    *,
    weight_scheme: str,
    weight_lookup: Mapping[float, float],
) -> pd.DataFrame:
    out = rows.copy()
    out["weight_scheme"] = weight_scheme
    out["row_weight"] = out["ltv_target"].round(6).map(dict(weight_lookup)).astype(float)
    if out["row_weight"].isna().any():
        raise ValueError("weight lookup missing one or more ltv_target values")
    return out


def kamino_lower_price(fri_close: float, deviation_bps: float = KAMINO_BPS) -> float:
    return fri_close * (1.0 - deviation_bps / 10_000.0)


def effective_threshold(
    regime: str,
    *,
    liquidation_threshold: float = LIQUIDATION_THRESHOLD,
    demote_threshold: bool = False,
    regime_multipliers: Mapping[str, float] | None = None,
) -> float:
    if not demote_threshold:
        return liquidation_threshold
    mults = dict(regime_multipliers or DEFAULT_REGIME_MULTIPLIERS)
    fallback = mults.get("high_vol", 1.0)
    return liquidation_threshold * mults.get(regime, fallback)


def current_ltv_for_price(ltv_target: np.ndarray | float, fri_close: float, price: float) -> np.ndarray:
    if price <= 0:
        raise ValueError("price must be positive")
    return np.asarray(ltv_target, dtype=float) * float(fri_close) / float(price)


def classify_ltv(
    current_ltv: np.ndarray | float,
    *,
    threshold_effective: float,
    max_ltv_at_origination: float = MAX_LTV_AT_ORIGINATION,
    clipped_forces_caution: bool = False,
) -> np.ndarray:
    ltv = np.asarray(current_ltv, dtype=float)
    decision = np.full(ltv.shape, SAFE, dtype=object)
    decision[ltv >= max_ltv_at_origination] = CAUTION
    decision[ltv >= threshold_effective] = LIQUIDATE
    if clipped_forces_caution:
        decision[decision == SAFE] = CAUTION
    return decision


def evaluate_price_grid(
    *,
    fri_close: float,
    comparison_price: float,
    regime: str,
    ltv_grid: Iterable[float],
    demote_threshold: bool,
    clipped_forces_caution: bool = False,
    liquidation_threshold: float = LIQUIDATION_THRESHOLD,
    max_ltv_at_origination: float = MAX_LTV_AT_ORIGINATION,
    regime_multipliers: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    ltv_grid_arr = np.asarray(list(ltv_grid), dtype=float)
    threshold = effective_threshold(
        regime,
        liquidation_threshold=liquidation_threshold,
        demote_threshold=demote_threshold,
        regime_multipliers=regime_multipliers,
    )
    current_ltv = current_ltv_for_price(ltv_grid_arr, fri_close, comparison_price)
    decision = classify_ltv(
        current_ltv,
        threshold_effective=threshold,
        max_ltv_at_origination=max_ltv_at_origination,
        clipped_forces_caution=clipped_forces_caution,
    )
    return pd.DataFrame(
        {
            "ltv_target": ltv_grid_arr,
            "current_ltv": current_ltv,
            "threshold_effective": threshold,
            "decision": decision,
        }
    )


def apply_decision_cost(
    predicted: pd.Series,
    realized: pd.Series,
    *,
    cost_matrix: Mapping[tuple[str, str], float] | None = None,
) -> pd.Series:
    cost = dict(cost_matrix or DEFAULT_COST_MATRIX)
    pairs = list(zip(predicted.astype(str), realized.astype(str), strict=False))
    return pd.Series([float(cost[(p, r)]) for p, r in pairs], index=predicted.index, dtype=float)


def _weighted_mean(series: pd.Series, weights: pd.Series | np.ndarray | None = None) -> float:
    values = series.to_numpy(dtype=float)
    if weights is None:
        return float(values.mean()) if len(values) else float("nan")
    w = np.asarray(weights, dtype=float)
    total = float(w.sum())
    if total <= 0:
        return float("nan")
    return float(np.average(values, weights=w))


def enrich_observation_rows(
    rows: pd.DataFrame,
    *,
    predicted_col: str = "decision_pred",
    realized_col: str = "decision_realized",
    cost_matrix: Mapping[tuple[str, str], float] | None = None,
) -> pd.DataFrame:
    out = rows.copy()
    pred = out[predicted_col].astype(str)
    realized = out[realized_col].astype(str)
    out["decision_cost"] = apply_decision_cost(pred, realized, cost_matrix=cost_matrix)
    out["is_safe"] = (pred == SAFE).astype(int)
    out["is_caution"] = (pred == CAUTION).astype(int)
    out["is_liquidate"] = (pred == LIQUIDATE).astype(int)
    out["realized_is_safe"] = (realized == SAFE).astype(int)
    out["realized_is_caution"] = (realized == CAUTION).astype(int)
    out["realized_is_liquidate"] = (realized == LIQUIDATE).astype(int)
    out["fp_liq"] = ((pred == LIQUIDATE) & (realized != LIQUIDATE)).astype(int)
    out["miss_liq"] = ((pred != LIQUIDATE) & (realized == LIQUIDATE)).astype(int)
    out["false_caution"] = ((pred == CAUTION) & (realized == SAFE)).astype(int)
    out["missed_caution"] = ((pred == SAFE) & (realized != SAFE)).astype(int)
    return out


def summarize_variant_rows(rows: pd.DataFrame, group_cols: Iterable[str]) -> pd.DataFrame:
    """Aggregate decision metrics at the requested grouping level."""
    group_cols_list = list(group_cols)
    out_rows: list[dict] = []
    for keys, grp in rows.groupby(group_cols_list, observed=True, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        rec = dict(zip(group_cols_list, keys, strict=True))
        weights = grp["row_weight"] if "row_weight" in grp.columns else None
        rec.update(
            {
                "n": int(len(grp)),
                "weight_sum": float(weights.sum()) if weights is not None else float(len(grp)),
                "mean_half_width_bps": _weighted_mean(grp["half_width_bps"], weights),
                "liquidation_rate": _weighted_mean(grp["is_liquidate"], weights),
                "caution_rate": _weighted_mean(grp["is_caution"], weights),
                "safe_rate": _weighted_mean(grp["is_safe"], weights),
                "realized_liquidation_rate": _weighted_mean(grp["realized_is_liquidate"], weights),
                "fp_liq_rate": _weighted_mean(grp["fp_liq"], weights),
                "miss_liq_rate": _weighted_mean(grp["miss_liq"], weights),
                "false_caution_rate": _weighted_mean(grp["false_caution"], weights),
                "missed_caution_rate": _weighted_mean(grp["missed_caution"], weights),
                "expected_loss": _weighted_mean(grp["decision_cost"], weights),
            }
        )
        out_rows.append(rec)
    summary = pd.DataFrame(out_rows)
    return summary.sort_values(group_cols_list).reset_index(drop=True)


def decision_confusion(rows: pd.DataFrame, group_cols: Iterable[str]) -> pd.DataFrame:
    group_cols_list = list(group_cols)
    weight_col = "row_weight" if "row_weight" in rows.columns else None
    agg_rows: list[dict] = []
    for keys, grp in rows.groupby(
        group_cols_list + ["decision_realized", "decision_pred"],
        observed=True,
        dropna=False,
    ):
        if not isinstance(keys, tuple):
            keys = (keys,)
        rec = dict(zip(group_cols_list + ["decision_realized", "decision_pred"], keys, strict=True))
        rec["n"] = int(len(grp))
        rec["weighted_n"] = float(grp[weight_col].sum()) if weight_col else float(len(grp))
        agg_rows.append(rec)
    conf = pd.DataFrame(agg_rows)
    conf["rate_within_group"] = conf["n"] / conf.groupby(
        group_cols_list,
        observed=True,
        dropna=False,
    )["n"].transform("sum")
    conf["weighted_rate_within_group"] = conf["weighted_n"] / conf.groupby(
        group_cols_list,
        observed=True,
        dropna=False,
    )["weighted_n"].transform("sum")
    return conf.sort_values(group_cols_list + ["decision_realized", "decision_pred"]).reset_index(drop=True)


def bootstrap_variant_deltas(
    rows: pd.DataFrame,
    *,
    baseline_variant: str,
    compare_variants: Iterable[str],
    n_boot: int,
    seed: int,
    group_col: str = "regime_pub",
    weight_col: str | None = "row_weight",
) -> pd.DataFrame:
    """Weekend-block bootstrap of Soothsayer minus baseline deltas."""
    metrics = [
        ("mean_half_width_bps", "half_width_bps"),
        ("fp_liq_rate", "fp_liq"),
        ("miss_liq_rate", "miss_liq"),
        ("false_caution_rate", "false_caution"),
        ("missed_caution_rate", "missed_caution"),
        ("expected_loss", "decision_cost"),
    ]
    rng = np.random.default_rng(seed)
    results: list[dict] = []
    variants = rows["variant"].astype(str)
    baseline = rows.loc[variants == baseline_variant].copy()
    compare_set = {str(v) for v in compare_variants}
    keys = ["symbol", "fri_ts", "ltv_target"]
    scopes = ["pooled"] + sorted(rows[group_col].dropna().astype(str).unique().tolist())

    for variant in sorted(compare_set):
        compare = rows.loc[variants == variant].copy()
        merged = baseline.merge(
            compare,
            on=keys,
            how="inner",
            suffixes=("_base", "_cmp"),
        )
        if merged.empty:
            continue

        for scope in scopes:
            scoped = merged if scope == "pooled" else merged[merged[f"{group_col}_base"] == scope]
            if scoped.empty:
                continue
            weekends = pd.unique(scoped["fri_ts"].values)
            n_weekends = len(weekends)
            scoped_by_week = {w: grp for w, grp in scoped.groupby("fri_ts")}
            point = {
                metric_name: float(
                    _weighted_mean(scoped[f"{source_col}_cmp"], scoped[f"{weight_col}_cmp"] if weight_col else None)
                    - _weighted_mean(scoped[f"{source_col}_base"], scoped[f"{weight_col}_base"] if weight_col else None)
                )
                for metric_name, source_col in metrics
            }
            boot = {metric_name: np.empty(n_boot, dtype=float) for metric_name, _ in metrics}
            for i in range(n_boot):
                draw = weekends[rng.integers(0, n_weekends, size=n_weekends)]
                sample = pd.concat([scoped_by_week[w] for w in draw], ignore_index=True)
                for metric_name, source_col in metrics:
                    boot[metric_name][i] = float(
                        _weighted_mean(sample[f"{source_col}_cmp"], sample[f"{weight_col}_cmp"] if weight_col else None)
                        - _weighted_mean(sample[f"{source_col}_base"], sample[f"{weight_col}_base"] if weight_col else None)
                    )

            rec: dict[str, float | int | str] = {
                "baseline_variant": baseline_variant,
                "compare_variant": variant,
                "scope": scope,
                "n_rows": int(len(scoped)),
                "n_weekends": int(n_weekends),
            }
            for metric_name, _ in metrics:
                rec[f"delta_{metric_name}"] = point[metric_name]
                rec[f"delta_{metric_name}_ci_lo"] = float(np.quantile(boot[metric_name], 0.025))
                rec[f"delta_{metric_name}_ci_hi"] = float(np.quantile(boot[metric_name], 0.975))
            results.append(rec)

    return pd.DataFrame(results)
