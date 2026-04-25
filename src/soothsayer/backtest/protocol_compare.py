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
    grp = rows.groupby(group_cols_list, observed=True, dropna=False)
    summary = grp.agg(
        n=("decision_pred", "count"),
        mean_half_width_bps=("half_width_bps", "mean"),
        liquidation_rate=("is_liquidate", "mean"),
        caution_rate=("is_caution", "mean"),
        safe_rate=("is_safe", "mean"),
        realized_liquidation_rate=("realized_is_liquidate", "mean"),
        fp_liq_rate=("fp_liq", "mean"),
        miss_liq_rate=("miss_liq", "mean"),
        false_caution_rate=("false_caution", "mean"),
        missed_caution_rate=("missed_caution", "mean"),
        expected_loss=("decision_cost", "mean"),
    ).reset_index()
    return summary.sort_values(group_cols_list).reset_index(drop=True)


def decision_confusion(rows: pd.DataFrame, group_cols: Iterable[str]) -> pd.DataFrame:
    group_cols_list = list(group_cols)
    conf = (
        rows.groupby(
            group_cols_list + ["decision_realized", "decision_pred"],
            observed=True,
            dropna=False,
        )
        .size()
        .rename("n")
        .reset_index()
    )
    conf["rate_within_group"] = conf["n"] / conf.groupby(
        group_cols_list,
        observed=True,
        dropna=False,
    )["n"].transform("sum")
    return conf.sort_values(group_cols_list + ["decision_realized", "decision_pred"]).reset_index(drop=True)


def bootstrap_variant_deltas(
    rows: pd.DataFrame,
    *,
    baseline_variant: str,
    compare_variants: Iterable[str],
    n_boot: int,
    seed: int,
    group_col: str = "regime_pub",
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
                metric_name: float(scoped[f"{source_col}_cmp"].mean() - scoped[f"{source_col}_base"].mean())
                for metric_name, source_col in metrics
            }
            boot = {metric_name: np.empty(n_boot, dtype=float) for metric_name, _ in metrics}
            for i in range(n_boot):
                draw = weekends[rng.integers(0, n_weekends, size=n_weekends)]
                sample = pd.concat([scoped_by_week[w] for w in draw], ignore_index=True)
                for metric_name, source_col in metrics:
                    boot[metric_name][i] = float(
                        sample[f"{source_col}_cmp"].mean() - sample[f"{source_col}_base"].mean()
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
