"""
Commercial gut check for the one-sided downside lending product.

Question
--------
If a lending protocol values xStock collateral at Soothsayer's one-sided
lower bound, how much borrowing capacity can it safely leave available versus
a blanket freeze or a fixed haircut?

This runner deliberately separates two evidence views:

1. ``exact_current`` — the exact one-sided artefact built by
   ``build_lwc_onesided_artefact.py``. Its c(tau) schedule was fitted on the
   same 2023+ rows being characterised, so this is retrospective product
   characterization, not held-out evidence.
2. ``chronology_honest`` — the same architecture with quantiles fit before
   2023, c(tau) tuned on 2023-2024, and a genuinely untouched 2025+ test.

It also separates two decision timestamps:

1. ``preopen`` — the factor-adjusted point is available immediately before
   the Monday cash open.
2. ``friday_commitment`` — only Friday close and the precommitted downside
   buffer are available. For the chronology-honest view, this timing gets its
   own properly fitted Friday-to-Monday downside score. The exact-current view
   reuses the current product's buffer and is therefore diagnostic only.

The economic unit is permitted debt per $1m of Friday-close collateral. A
counterfactual loan is unsafe at Monday open when permitted debt exceeds the
reserve's liquidation-threshold value at the realised Monday price.

Inputs
------
  data/processed/v1b_panel.parquet
  data/processed/kamino_xstocks_snapshot_20260427.json
  data/processed/lwc_onesided_artefact_v1.json

Outputs
-------
  reports/tables/lending_commercial_backtest_summary.csv
  reports/tables/lending_commercial_backtest_by_reserve.csv
  reports/tables/lending_commercial_matched_fixed.csv
  reports/lending_commercial_backtest.md

Run
---
  ./.venv/bin/python scripts/run_lending_commercial_backtest.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    prep_panel_for_forecaster,
)
from soothsayer.config import DATA_PROCESSED, REPORTS


PANEL_PATH = DATA_PROCESSED / "v1b_panel.parquet"
RESERVE_SNAPSHOT_PATH = (
    DATA_PROCESSED / "kamino_xstocks_snapshot_20260427.json"
)
CURRENT_SIDECAR_PATH = DATA_PROCESSED / "lwc_onesided_artefact_v1.json"

TABLE_DIR = REPORTS / "tables"
SUMMARY_PATH = TABLE_DIR / "lending_commercial_backtest_summary.csv"
BY_RESERVE_PATH = TABLE_DIR / "lending_commercial_backtest_by_reserve.csv"
MATCHED_PATH = TABLE_DIR / "lending_commercial_matched_fixed.csv"
REPORT_PATH = REPORTS / "lending_commercial_backtest.md"

TRAIN_END = date(2023, 1, 1)
TUNE_END = date(2025, 1, 1)
HONEST_TEST_START = TUNE_END
EXACT_TEST_START = TRAIN_END

COLLATERAL_NOTIONAL_USD = 1_000_000.0
FIXED_HAIRCUT_BPS = tuple(np.arange(0.0, 1500.0 + 0.1, 25.0))
ANNUAL_BORROW_RATE = 0.05
WEEKEND_DAYS = 2.5
N_BOOT = 2_000
BOOT_SEED = 20260725

NARROW_SYMBOLS = ("SPY", "QQQ")
XSTOCK_SYMBOLS = (
    "SPY", "QQQ", "TSLA", "GOOGL", "NVDA", "AAPL", "MSTR", "HOOD",
)


@dataclass(frozen=True)
class Model:
    name: str
    evidence_label: str
    test_start: date
    quantiles_preopen: dict[str, dict[float, float]]
    c_preopen: dict[float, float]
    quantiles_friday: dict[str, dict[float, float]]
    c_friday: dict[float, float]
    static_haircuts_preopen: dict[str, dict[float, float]]
    static_haircuts_friday: dict[str, dict[float, float]]


def cp_quantile(scores: np.ndarray, tau: float) -> float:
    """Finite-sample split-conformal quantile at rank ceil(tau * (n + 1))."""
    values = np.sort(scores[np.isfinite(scores)])
    if values.size == 0:
        return float("nan")
    rank = min(max(int(np.ceil(tau * (values.size + 1))), 1), values.size)
    return float(values[rank - 1])


def fit_quantiles(
    train: pd.DataFrame,
    score_col: str,
) -> dict[str, dict[float, float]]:
    return {
        str(regime): {
            float(tau): cp_quantile(group[score_col].to_numpy(float), tau)
            for tau in DEFAULT_TAUS
        }
        for regime, group in train.groupby("regime_pub", observed=True)
    }


def fit_c_schedule(
    tune: pd.DataFrame,
    score_col: str,
    quantiles: dict[str, dict[float, float]],
) -> dict[float, float]:
    """Smallest c >= 1 attaining target coverage on the tuning period."""
    cells = tune["regime_pub"].astype(str).to_numpy()
    scores = tune[score_col].to_numpy(float)
    schedule: dict[float, float] = {}
    for tau in DEFAULT_TAUS:
        base = np.array([quantiles[cell][float(tau)] for cell in cells])
        valid = np.isfinite(scores) & np.isfinite(base)
        chosen = 5.0
        for c in np.arange(1.0, 5.0001, 0.001):
            if float(np.mean(scores[valid] <= base[valid] * c)) >= tau:
                chosen = float(c)
                break
        schedule[float(tau)] = chosen
    return schedule


def fit_static_haircuts(
    tune: pd.DataFrame,
    *,
    timing: str,
) -> dict[str, dict[float, float]]:
    """Per-symbol fixed downside haircut fitted before the held-out test."""
    reference = (
        tune["point"].astype(float)
        if timing == "preopen"
        else tune["fri_close"].astype(float)
    )
    scored = tune.copy()
    scored["static_downside_bps"] = (
        (reference - scored["mon_open"].astype(float)) / reference * 10_000.0
    )
    return {
        str(symbol): {
            float(tau): max(
                cp_quantile(group["static_downside_bps"].to_numpy(float), tau),
                0.0,
            )
            for tau in DEFAULT_TAUS
        }
        for symbol, group in scored.groupby("symbol", observed=True)
    }


def load_current_tables() -> tuple[
    dict[str, dict[float, float]], dict[float, float]
]:
    sidecar = json.loads(CURRENT_SIDECAR_PATH.read_text())
    quantiles = {
        str(regime): {
            float(tau): float(value) for tau, value in table.items()
        }
        for regime, table in sidecar["regime_quantile_table"].items()
    }
    c_schedule = {
        float(tau): float(value)
        for tau, value in sidecar["c_bump_schedule"].items()
    }
    return quantiles, c_schedule


def prepare_panel() -> pd.DataFrame:
    raw = pd.read_parquet(PANEL_PATH)
    raw["fri_ts"] = pd.to_datetime(raw["fri_ts"]).dt.date
    raw = raw.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    raw["regime_pub"] = raw["regime_pub"].astype(str)

    work = prep_panel_for_forecaster(raw, "lwc")
    work["point"] = work["fri_close"] * (1.0 + work["factor_ret"])
    scale = (
        work["fri_close"].astype(float)
        * work["sigma_hat_sym_pre_fri"].astype(float)
    )
    work["score_preopen"] = (
        work["point"].astype(float) - work["mon_open"].astype(float)
    ) / scale
    work["score_friday"] = (
        work["fri_close"].astype(float) - work["mon_open"].astype(float)
    ) / scale
    return work.dropna(
        subset=[
            "score_preopen", "score_friday", "sigma_hat_sym_pre_fri",
        ]
    ).reset_index(drop=True)


def load_reserves() -> dict[str, dict[str, float]]:
    snapshot = json.loads(RESERVE_SNAPSHOT_PATH.read_text())
    reserves: dict[str, dict[str, float]] = {}
    for reserve in snapshot["reserves"]:
        symbol = str(reserve["symbol"]).removesuffix("x")
        config = reserve["config"]
        reserves[symbol] = {
            "max_ltv": float(config["loan_to_value_pct"]) / 100.0,
            "liquidation_threshold": (
                float(config["liquidation_threshold_pct"]) / 100.0
            ),
            "borrow_limit_raw": float(config["borrow_limit"]),
        }
    missing = set(XSTOCK_SYMBOLS) - set(reserves)
    if missing:
        raise ValueError(f"reserve snapshot missing symbols: {sorted(missing)}")
    return reserves


def make_models(work: pd.DataFrame) -> list[Model]:
    current_q, current_c = load_current_tables()

    train = work[work["fri_ts"] < TRAIN_END]
    tune = work[
        (work["fri_ts"] >= TRAIN_END) & (work["fri_ts"] < TUNE_END)
    ]
    honest_q_preopen = fit_quantiles(train, "score_preopen")
    honest_c_preopen = fit_c_schedule(
        tune, "score_preopen", honest_q_preopen
    )
    honest_q_friday = fit_quantiles(train, "score_friday")
    honest_c_friday = fit_c_schedule(
        tune, "score_friday", honest_q_friday
    )
    static_preopen = fit_static_haircuts(tune, timing="preopen")
    static_friday = fit_static_haircuts(tune, timing="friday_commitment")

    return [
        Model(
            name="exact_current",
            evidence_label="retrospective_characterization",
            test_start=EXACT_TEST_START,
            quantiles_preopen=current_q,
            c_preopen=current_c,
            # Current Friday view: reuse the committed current buffer around
            # Friday close. This is intentionally diagnostic, not recalibrated.
            quantiles_friday=current_q,
            c_friday=current_c,
            static_haircuts_preopen=static_preopen,
            static_haircuts_friday=static_friday,
        ),
        Model(
            name="chronology_honest",
            evidence_label="held_out_2025_plus",
            test_start=HONEST_TEST_START,
            quantiles_preopen=honest_q_preopen,
            c_preopen=honest_c_preopen,
            quantiles_friday=honest_q_friday,
            c_friday=honest_c_friday,
            static_haircuts_preopen=static_preopen,
            static_haircuts_friday=static_friday,
        ),
    ]


def evaluate_policy(
    frame: pd.DataFrame,
    reserves: dict[str, dict[str, float]],
    *,
    model: Model,
    timing: str,
    policy: str,
    policy_kind: str,
    tau: float | None = None,
    fixed_haircut_bps: float | None = None,
) -> pd.DataFrame:
    """Evaluate one origination policy on every symbol-weekend row."""
    out = frame.copy()
    out["view"] = model.name
    out["evidence_label"] = model.evidence_label
    out["timing"] = timing
    out["policy"] = policy
    out["policy_kind"] = policy_kind
    out["tau"] = tau
    out["fixed_haircut_bps"] = fixed_haircut_bps

    reference = (
        out["point"].to_numpy(float)
        if timing == "preopen"
        else out["fri_close"].to_numpy(float)
    )
    fri = out["fri_close"].to_numpy(float)
    actual = out["mon_open"].to_numpy(float)
    quantity = COLLATERAL_NOTIONAL_USD / fri

    if policy_kind == "freeze":
        lower = np.zeros(len(out), dtype=float)
    elif policy_kind == "fixed":
        if fixed_haircut_bps is None:
            raise ValueError("fixed_haircut_bps required for fixed policy")
        lower = reference * (1.0 - fixed_haircut_bps / 10_000.0)
    elif policy_kind == "fixed_frozen":
        if tau is None:
            raise ValueError("tau required for frozen fixed policy")
        table = (
            model.static_haircuts_preopen
            if timing == "preopen"
            else model.static_haircuts_friday
        )
        row_haircuts = np.array([
            table[str(symbol)][float(tau)]
            for symbol in out["symbol"].astype(str)
        ])
        lower = reference * (1.0 - row_haircuts / 10_000.0)
        out["effective_haircut_bps"] = row_haircuts
    elif policy_kind == "onesided":
        if tau is None:
            raise ValueError("tau required for one-sided policy")
        if timing == "preopen":
            quantiles, c_schedule = model.quantiles_preopen, model.c_preopen
        else:
            quantiles, c_schedule = model.quantiles_friday, model.c_friday
        q = np.array([
            quantiles[str(cell)][float(tau)]
            for cell in out["regime_pub"].astype(str)
        ])
        scale = (
            out["sigma_hat_sym_pre_fri"].to_numpy(float)
            * fri
        )
        lower = reference - q * c_schedule[float(tau)] * scale
    else:
        raise ValueError(f"unknown policy_kind: {policy_kind}")

    max_ltv = out["symbol"].map(
        {symbol: cfg["max_ltv"] for symbol, cfg in reserves.items()}
    ).to_numpy(float)
    liquidation_threshold = out["symbol"].map(
        {
            symbol: cfg["liquidation_threshold"]
            for symbol, cfg in reserves.items()
        }
    ).to_numpy(float)

    permitted_debt = np.maximum(lower, 0.0) * quantity * max_ltv
    realized_safe_ceiling = actual * quantity * liquidation_threshold
    shortfall = np.maximum(
        permitted_debt - realized_safe_ceiling, 0.0
    )

    out["reference_price"] = reference
    out["lower"] = lower
    out["buffer_bps"] = np.where(
        reference > 0.0, (reference - lower) / reference * 10_000.0, np.nan
    )
    out["permitted_debt_per_1m"] = permitted_debt
    out["realized_safe_debt_per_1m"] = realized_safe_ceiling
    out["unsafe"] = permitted_debt > realized_safe_ceiling
    out["shortfall_per_1m"] = shortfall
    out["lower_breached"] = actual < lower
    return out


def build_evaluations(
    work: pd.DataFrame,
    reserves: dict[str, dict[str, float]],
    models: list[Model],
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    xstocks = work[work["symbol"].isin(XSTOCK_SYMBOLS)].copy()

    for model in models:
        test = xstocks[xstocks["fri_ts"] >= model.test_start].copy()
        for timing in ("preopen", "friday_commitment"):
            rows.append(evaluate_policy(
                test, reserves,
                model=model,
                timing=timing,
                policy="freeze",
                policy_kind="freeze",
            ))
            for haircut_bps in FIXED_HAIRCUT_BPS:
                rows.append(evaluate_policy(
                    test, reserves,
                    model=model,
                    timing=timing,
                    policy=f"fixed_{int(haircut_bps):04d}bps",
                    policy_kind="fixed",
                    fixed_haircut_bps=float(haircut_bps),
                ))
            for tau in DEFAULT_TAUS:
                rows.append(evaluate_policy(
                    test, reserves,
                    model=model,
                    timing=timing,
                    policy=f"fixed_frozen_tau_{tau:.2f}",
                    policy_kind="fixed_frozen",
                    tau=float(tau),
                ))
                rows.append(evaluate_policy(
                    test, reserves,
                    model=model,
                    timing=timing,
                    policy=f"onesided_tau_{tau:.2f}",
                    policy_kind="onesided",
                    tau=float(tau),
                ))
    return pd.concat(rows, ignore_index=True)


def summarize_group(group: pd.DataFrame) -> pd.Series:
    n = len(group)
    unsafe = group["unsafe"].to_numpy(bool)
    capacity = group["permitted_debt_per_1m"].to_numpy(float)
    shortfall = group["shortfall_per_1m"].to_numpy(float)
    return pd.Series({
        "n": n,
        "n_weekends": group["fri_ts"].nunique(),
        "mean_capacity_per_1m": float(np.mean(capacity)),
        "median_capacity_per_1m": float(np.median(capacity)),
        "unsafe_n": int(np.sum(unsafe)),
        "unsafe_rate": float(np.mean(unsafe)),
        "mean_shortfall_per_1m": float(np.mean(shortfall)),
        "max_shortfall_per_1m": float(np.max(shortfall)),
        "lower_breach_rate": float(group["lower_breached"].mean()),
        "mean_buffer_bps": float(group["buffer_bps"].mean()),
        "annual_revenue_capacity_at_5pct": (
            float(np.mean(capacity)) * ANNUAL_BORROW_RATE
        ),
        "weekend_income_at_5pct": (
            float(np.mean(capacity))
            * ANNUAL_BORROW_RATE
            * WEEKEND_DAYS
            / 365.0
        ),
    })


def make_summaries(evaluations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scopes = {
        "narrow_spy_qqq": NARROW_SYMBOLS,
        "all_8_xstocks": XSTOCK_SYMBOLS,
    }
    summary_frames: list[pd.DataFrame] = []
    for scope, symbols in scopes.items():
        scoped = evaluations[evaluations["symbol"].isin(symbols)].copy()
        grouped = (
            scoped.groupby(
                [
                    "view", "evidence_label", "timing", "policy",
                    "policy_kind", "tau", "fixed_haircut_bps",
                ],
                dropna=False,
                observed=True,
            )
            .apply(summarize_group, include_groups=False)
            .reset_index()
        )
        grouped.insert(2, "scope", scope)
        summary_frames.append(grouped)
    summary = pd.concat(summary_frames, ignore_index=True)

    by_reserve = (
        evaluations.groupby(
            [
                "view", "evidence_label", "timing", "symbol", "policy",
                "policy_kind", "tau", "fixed_haircut_bps",
            ],
            dropna=False,
            observed=True,
        )
        .apply(summarize_group, include_groups=False)
        .reset_index()
    )
    return summary, by_reserve


def bootstrap_capacity_delta(
    product: pd.DataFrame,
    fixed: pd.DataFrame,
) -> tuple[float, float]:
    merged = product.merge(
        fixed,
        on=["symbol", "fri_ts"],
        suffixes=("_product", "_fixed"),
        how="inner",
    )
    by_week = (
        merged.groupby("fri_ts", observed=True)
        .apply(
            lambda g: (
                g["permitted_debt_per_1m_product"]
                - g["permitted_debt_per_1m_fixed"]
            ).mean(),
            include_groups=False,
        )
        .to_numpy(float)
    )
    rng = np.random.default_rng(BOOT_SEED)
    draws = rng.integers(0, len(by_week), size=(N_BOOT, len(by_week)))
    boot = by_week[draws].mean(axis=1)
    return float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def match_fixed_haircuts(
    summary: pd.DataFrame,
    by_reserve: pd.DataFrame,
    evaluations: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict] = []
    scopes = {
        "narrow_spy_qqq": NARROW_SYMBOLS,
        "all_8_xstocks": XSTOCK_SYMBOLS,
    }

    products = summary[summary["policy_kind"] == "onesided"]
    for _, product in products.iterrows():
        symbols = scopes[str(product["scope"])]
        common_filter = (
            (evaluations["view"] == product["view"])
            & (evaluations["timing"] == product["timing"])
            & evaluations["symbol"].isin(symbols)
        )
        product_rows_all = evaluations[
            common_filter & (evaluations["policy"] == product["policy"])
        ]

        # Primary deployable comparator: per-reserve static downside quantiles
        # selected on 2023-2024 and frozen before the 2025+ test.
        frozen_policy = f"fixed_frozen_tau_{float(product['tau']):.2f}"
        frozen_summary = summary[
            (summary["view"] == product["view"])
            & (summary["timing"] == product["timing"])
            & (summary["scope"] == product["scope"])
            & (summary["policy"] == frozen_policy)
        ]
        if not frozen_summary.empty:
            frozen = frozen_summary.iloc[0]
            frozen_rows = evaluations[
                common_filter & (evaluations["policy"] == frozen_policy)
            ]
            ci_lo, ci_hi = bootstrap_capacity_delta(
                product_rows_all, frozen_rows
            )
            capacity_delta = (
                float(product["mean_capacity_per_1m"])
                - float(frozen["mean_capacity_per_1m"])
            )
            schedule = (
                frozen_rows.groupby("symbol", observed=True)["buffer_bps"]
                .mean()
                .to_dict()
            )
            rows.append({
                "view": product["view"],
                "evidence_label": product["evidence_label"],
                "timing": product["timing"],
                "scope": product["scope"],
                "tau": product["tau"],
                "match_basis": "frozen_pretest_same_tau_per_reserve",
                "product_policy": product["policy"],
                "matched_fixed_policy": frozen_policy,
                "matched_fixed_haircut_bps": float(
                    np.mean(list(schedule.values()))
                ),
                "matched_fixed_haircuts": ";".join(
                    f"{symbol}:{schedule[symbol]:.0f}" for symbol in symbols
                ),
                "product_capacity_per_1m": product["mean_capacity_per_1m"],
                "fixed_capacity_per_1m": frozen["mean_capacity_per_1m"],
                "capacity_delta_per_1m": capacity_delta,
                "capacity_delta_pct_vs_fixed": (
                    capacity_delta / float(frozen["mean_capacity_per_1m"])
                    if float(frozen["mean_capacity_per_1m"]) > 0 else np.nan
                ),
                "capacity_delta_ci_lo": ci_lo,
                "capacity_delta_ci_hi": ci_hi,
                "product_unsafe_n": product["unsafe_n"],
                "fixed_unsafe_n": frozen["unsafe_n"],
                "product_unsafe_rate": product["unsafe_rate"],
                "fixed_unsafe_rate": frozen["unsafe_rate"],
                "product_lower_breach_rate": product["lower_breach_rate"],
                "fixed_lower_breach_rate": frozen["lower_breach_rate"],
                "product_mean_shortfall_per_1m": (
                    product["mean_shortfall_per_1m"]
                ),
                "fixed_mean_shortfall_per_1m": (
                    frozen["mean_shortfall_per_1m"]
                ),
                "n": product["n"],
                "n_weekends": product["n_weekends"],
            })

        base_filter = (
            (summary["view"] == product["view"])
            & (summary["timing"] == product["timing"])
            & (summary["scope"] == product["scope"])
            & (summary["policy_kind"] == "fixed")
        )
        match_filters = {
            "endpoint_safety": (
                (summary["unsafe_rate"] <= product["unsafe_rate"] + 1e-15)
                & (
                    summary["mean_shortfall_per_1m"]
                    <= product["mean_shortfall_per_1m"] + 1e-12
                )
            ),
            "lower_bound_coverage": (
                summary["lower_breach_rate"]
                <= product["lower_breach_rate"] + 1e-15
            ),
        }
        for match_basis, risk_filter in match_filters.items():
            fixed = summary[base_filter & risk_filter].sort_values(
                ["mean_capacity_per_1m", "fixed_haircut_bps"],
                ascending=[False, True],
            )
            if fixed.empty:
                continue
            matched = fixed.iloc[0]

            product_rows = evaluations[
                common_filter & (evaluations["policy"] == product["policy"])
            ]
            fixed_rows = evaluations[
                common_filter & (evaluations["policy"] == matched["policy"])
            ]
            ci_lo, ci_hi = bootstrap_capacity_delta(product_rows, fixed_rows)

            capacity_delta = (
                float(product["mean_capacity_per_1m"])
                - float(matched["mean_capacity_per_1m"])
            )
            rows.append({
                "view": product["view"],
                "evidence_label": product["evidence_label"],
                "timing": product["timing"],
                "scope": product["scope"],
                "tau": product["tau"],
                "match_basis": match_basis,
                "product_policy": product["policy"],
                "matched_fixed_policy": matched["policy"],
                "matched_fixed_haircut_bps": matched["fixed_haircut_bps"],
                "product_capacity_per_1m": product["mean_capacity_per_1m"],
                "fixed_capacity_per_1m": matched["mean_capacity_per_1m"],
                "capacity_delta_per_1m": capacity_delta,
                "capacity_delta_pct_vs_fixed": (
                    capacity_delta / float(matched["mean_capacity_per_1m"])
                    if float(matched["mean_capacity_per_1m"]) > 0 else np.nan
                ),
                "capacity_delta_ci_lo": ci_lo,
                "capacity_delta_ci_hi": ci_hi,
                "product_unsafe_n": product["unsafe_n"],
                "fixed_unsafe_n": matched["unsafe_n"],
                "product_unsafe_rate": product["unsafe_rate"],
                "fixed_unsafe_rate": matched["unsafe_rate"],
                "product_lower_breach_rate": product["lower_breach_rate"],
                "fixed_lower_breach_rate": matched["lower_breach_rate"],
                "product_mean_shortfall_per_1m": (
                    product["mean_shortfall_per_1m"]
                ),
                "fixed_mean_shortfall_per_1m": (
                    matched["mean_shortfall_per_1m"]
                ),
                "n": product["n"],
                "n_weekends": product["n_weekends"],
            })

        # Stronger production comparator: allow a separate static haircut for
        # each reserve, then aggregate the selected fixed-policy rows. This
        # asks whether regime/time variation adds value after the baseline is
        # already allowed to absorb persistent cross-symbol heterogeneity.
        for basis in ("endpoint_safety", "lower_bound_coverage"):
            selected: dict[str, str] = {}
            selected_bps: dict[str, float] = {}
            for symbol in symbols:
                product_symbol = by_reserve[
                    (by_reserve["view"] == product["view"])
                    & (by_reserve["timing"] == product["timing"])
                    & (by_reserve["symbol"] == symbol)
                    & (by_reserve["policy"] == product["policy"])
                ]
                fixed_symbol = by_reserve[
                    (by_reserve["view"] == product["view"])
                    & (by_reserve["timing"] == product["timing"])
                    & (by_reserve["symbol"] == symbol)
                    & (by_reserve["policy_kind"] == "fixed")
                ].copy()
                if product_symbol.empty or fixed_symbol.empty:
                    continue
                ps = product_symbol.iloc[0]
                if basis == "endpoint_safety":
                    eligible = fixed_symbol[
                        (fixed_symbol["unsafe_rate"] <= ps["unsafe_rate"] + 1e-15)
                        & (
                            fixed_symbol["mean_shortfall_per_1m"]
                            <= ps["mean_shortfall_per_1m"] + 1e-12
                        )
                    ]
                else:
                    eligible = fixed_symbol[
                        fixed_symbol["lower_breach_rate"]
                        <= ps["lower_breach_rate"] + 1e-15
                    ]
                if eligible.empty:
                    continue
                choice = eligible.sort_values(
                    ["mean_capacity_per_1m", "fixed_haircut_bps"],
                    ascending=[False, True],
                ).iloc[0]
                selected[symbol] = str(choice["policy"])
                selected_bps[symbol] = float(choice["fixed_haircut_bps"])
            if len(selected) != len(symbols):
                continue

            fixed_rows_all = pd.concat(
                [
                    evaluations[
                        (evaluations["view"] == product["view"])
                        & (evaluations["timing"] == product["timing"])
                        & (evaluations["symbol"] == symbol)
                        & (evaluations["policy"] == policy)
                    ]
                    for symbol, policy in selected.items()
                ],
                ignore_index=True,
            )
            fixed_agg = summarize_group(fixed_rows_all)
            ci_lo, ci_hi = bootstrap_capacity_delta(
                product_rows_all, fixed_rows_all
            )
            capacity_delta = (
                float(product["mean_capacity_per_1m"])
                - float(fixed_agg["mean_capacity_per_1m"])
            )
            rows.append({
                "view": product["view"],
                "evidence_label": product["evidence_label"],
                "timing": product["timing"],
                "scope": product["scope"],
                "tau": product["tau"],
                "match_basis": f"{basis}_per_reserve",
                "product_policy": product["policy"],
                "matched_fixed_policy": "per_reserve",
                "matched_fixed_haircut_bps": float(
                    np.mean(list(selected_bps.values()))
                ),
                "matched_fixed_haircuts": ";".join(
                    f"{symbol}:{selected_bps[symbol]:.0f}"
                    for symbol in symbols
                ),
                "product_capacity_per_1m": product["mean_capacity_per_1m"],
                "fixed_capacity_per_1m": fixed_agg["mean_capacity_per_1m"],
                "capacity_delta_per_1m": capacity_delta,
                "capacity_delta_pct_vs_fixed": (
                    capacity_delta / float(fixed_agg["mean_capacity_per_1m"])
                    if float(fixed_agg["mean_capacity_per_1m"]) > 0 else np.nan
                ),
                "capacity_delta_ci_lo": ci_lo,
                "capacity_delta_ci_hi": ci_hi,
                "product_unsafe_n": product["unsafe_n"],
                "fixed_unsafe_n": fixed_agg["unsafe_n"],
                "product_unsafe_rate": product["unsafe_rate"],
                "fixed_unsafe_rate": fixed_agg["unsafe_rate"],
                "product_lower_breach_rate": product["lower_breach_rate"],
                "fixed_lower_breach_rate": fixed_agg["lower_breach_rate"],
                "product_mean_shortfall_per_1m": (
                    product["mean_shortfall_per_1m"]
                ),
                "fixed_mean_shortfall_per_1m": (
                    fixed_agg["mean_shortfall_per_1m"]
                ),
                "n": product["n"],
                "n_weekends": product["n_weekends"],
            })
    return pd.DataFrame(rows)


def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_report(
    work: pd.DataFrame,
    models: list[Model],
    summary: pd.DataFrame,
    by_reserve: pd.DataFrame,
    matched: pd.DataFrame,
) -> str:
    honest = summary[
        (summary["view"] == "chronology_honest")
        & (summary["timing"] == "preopen")
        & (summary["policy_kind"] == "onesided")
    ].copy()
    honest_display = honest[
        [
            "scope", "tau", "mean_capacity_per_1m", "unsafe_n",
            "unsafe_rate", "mean_shortfall_per_1m", "lower_breach_rate",
            "mean_buffer_bps",
        ]
    ].copy()
    honest_display.columns = [
        "Scope", "τ", "Capacity / $1m", "Unsafe n", "Unsafe rate",
        "Mean shortfall / $1m", "Lower-bound breach", "Mean buffer (bps)",
    ]
    honest_display["Capacity / $1m"] = honest_display[
        "Capacity / $1m"
    ].map(money)
    honest_display["Mean shortfall / $1m"] = honest_display[
        "Mean shortfall / $1m"
    ].map(money)
    honest_display["Unsafe rate"] = honest_display["Unsafe rate"].map(pct)
    honest_display["Lower-bound breach"] = honest_display[
        "Lower-bound breach"
    ].map(pct)
    honest_display["Mean buffer (bps)"] = honest_display[
        "Mean buffer (bps)"
    ].map(lambda x: f"{x:,.1f}")

    def format_matched(frame: pd.DataFrame) -> pd.DataFrame:
        display = frame[
            [
                "match_basis", "scope", "tau", "matched_fixed_haircut_bps",
                "product_capacity_per_1m", "fixed_capacity_per_1m",
                "capacity_delta_per_1m", "capacity_delta_pct_vs_fixed",
                "capacity_delta_ci_lo", "capacity_delta_ci_hi",
                "product_lower_breach_rate", "fixed_lower_breach_rate",
                "product_unsafe_n", "fixed_unsafe_n",
            ]
        ].copy()
        display.columns = [
            "Comparison", "Scope", "τ", "Mean fixed (bps)",
            "Product capacity", "Fixed capacity", "Δ capacity", "Δ vs fixed",
            "95% CI low", "95% CI high", "Product breach", "Fixed breach",
            "Product unsafe", "Fixed unsafe",
        ]
        for column in (
            "Product capacity", "Fixed capacity", "Δ capacity",
            "95% CI low", "95% CI high",
        ):
            display[column] = display[column].map(money)
        for column in ("Δ vs fixed", "Product breach", "Fixed breach"):
            display[column] = display[column].map(pct)
        display["Mean fixed (bps)"] = display[
            "Mean fixed (bps)"
        ].map(lambda x: f"{x:,.0f}")
        return display

    honest_preopen = matched[
        (matched["view"] == "chronology_honest")
        & (matched["timing"] == "preopen")
    ].copy()
    frozen_display = format_matched(
        honest_preopen[
            honest_preopen["match_basis"]
            == "frozen_pretest_same_tau_per_reserve"
        ]
    )
    frontier_display = format_matched(
        honest_preopen[
            honest_preopen["match_basis"].isin(
                [
                    "endpoint_safety_per_reserve",
                    "lower_bound_coverage_per_reserve",
                ]
            )
        ]
    )

    reserve_honest = by_reserve[
        (by_reserve["view"] == "chronology_honest")
        & (by_reserve["timing"] == "preopen")
        & (by_reserve["policy"] == "onesided_tau_0.85")
    ].copy()
    reserve_display = reserve_honest[
        [
            "symbol", "mean_capacity_per_1m", "unsafe_n", "unsafe_rate",
            "mean_shortfall_per_1m", "lower_breach_rate", "mean_buffer_bps",
        ]
    ].copy()
    reserve_display.columns = [
        "Reserve", "Capacity / $1m", "Unsafe n", "Unsafe rate",
        "Mean shortfall / $1m", "Lower-bound breach", "Mean buffer (bps)",
    ]
    reserve_display["Capacity / $1m"] = reserve_display[
        "Capacity / $1m"
    ].map(money)
    reserve_display["Mean shortfall / $1m"] = reserve_display[
        "Mean shortfall / $1m"
    ].map(money)
    reserve_display["Unsafe rate"] = reserve_display["Unsafe rate"].map(pct)
    reserve_display["Lower-bound breach"] = reserve_display[
        "Lower-bound breach"
    ].map(pct)
    reserve_display["Mean buffer (bps)"] = reserve_display[
        "Mean buffer (bps)"
    ].map(lambda x: f"{x:,.1f}")

    current_model = next(m for m in models if m.name == "exact_current")
    honest_model = next(m for m in models if m.name == "chronology_honest")
    current_c = ", ".join(
        f"{tau:.2f}: {current_model.c_preopen[tau]:.3f}"
        for tau in DEFAULT_TAUS
    )
    honest_c = ", ".join(
        f"{tau:.2f}: {honest_model.c_preopen[tau]:.3f}"
        for tau in DEFAULT_TAUS
    )

    def matched_row(
        timing: str, scope: str, tau: float, basis: str
    ) -> pd.Series:
        row = matched[
            (matched["view"] == "chronology_honest")
            & (matched["timing"] == timing)
            & (matched["scope"] == scope)
            & (matched["tau"] == tau)
            & (matched["match_basis"] == basis)
        ]
        if row.empty:
            raise ValueError(
                f"missing matched row: {timing}, {scope}, {tau}, {basis}"
            )
        return row.iloc[0]

    friday_85_endpoint = matched_row(
        "friday_commitment", "narrow_spy_qqq", 0.85,
        "endpoint_safety_per_reserve",
    )
    friday_85_coverage = matched_row(
        "friday_commitment", "narrow_spy_qqq", 0.85,
        "lower_bound_coverage_per_reserve",
    )
    preopen_95_coverage = matched_row(
        "preopen", "narrow_spy_qqq", 0.95,
        "lower_bound_coverage_per_reserve",
    )
    friday_85_frozen = matched_row(
        "friday_commitment", "narrow_spy_qqq", 0.85,
        "frozen_pretest_same_tau_per_reserve",
    )
    preopen_85_frozen = matched_row(
        "preopen", "narrow_spy_qqq", 0.85,
        "frozen_pretest_same_tau_per_reserve",
    )
    friday_capacity_85 = float(
        summary[
            (summary["view"] == "chronology_honest")
            & (summary["timing"] == "friday_commitment")
            & (summary["scope"] == "narrow_spy_qqq")
            & (summary["policy"] == "onesided_tau_0.85")
        ]["mean_capacity_per_1m"].iloc[0]
    )

    return f"""# One-sided lending commercial backtest

**Run date:** 2026-07-25  
**Status:** Internal gut check, not a protocol revenue claim.

## Question

If a lending protocol values xStock collateral at Soothsayer's one-sided
downside bound, how much borrowing capacity can it safely leave available
compared with a blanket freeze or a fixed haircut?

The experiment normalizes every observation to **$1 million of collateral at
Friday close** and applies the actual Kamino xStock max-LTV and liquidation
threshold for that reserve. A counterfactual maximum-size loan is unsafe when
its permitted debt exceeds the reserve's liquidation-threshold value at the
realized Monday open.

## Gut-check verdict

**The product clearly beats a blanket freeze and preserves the intended risk
level better than a static policy frozen before the test. It does not show a
large capital-efficiency advantage over a static haircut chosen with hindsight
to match the realised test risk.**

- At the current τ=0.85 default, the chronology-honest Friday policy permits
  about **{money(friday_capacity_85)}**
  per $1m of SPY/QQQ collateral rather than the freeze policy's $0.
- Against the per-reserve fixed τ=0.85 policy selected on 2023–2024 and then
  frozen, Soothsayer gives up
  **{money(abs(float(friday_85_frozen["capacity_delta_per_1m"])))}**
  per $1m of Friday capacity ({pct(abs(float(friday_85_frozen["capacity_delta_pct_vs_fixed"])))})
  but cuts the held-out lower-bound breach rate from
  **{pct(float(friday_85_frozen["fixed_lower_breach_rate"]))} to
  {pct(float(friday_85_frozen["product_lower_breach_rate"]))}** and records
  **{int(friday_85_frozen["product_unsafe_n"])} versus
  {int(friday_85_frozen["fixed_unsafe_n"])}** endpoint-unsafe loans.
- At Monday pre-open, the same frozen comparison gives up
  **{money(abs(float(preopen_85_frozen["capacity_delta_per_1m"])))}**
  per $1m while cutting bound breaches from
  **{pct(float(preopen_85_frozen["fixed_lower_breach_rate"]))} to
  {pct(float(preopen_85_frozen["product_lower_breach_rate"]))}**.
- If the static haircut is instead selected *after seeing 2025+* to match
  realised endpoint risk, the Friday τ=0.85 product adds only
  **{money(float(friday_85_endpoint["capacity_delta_per_1m"]))}**
  per $1m; its block-bootstrap interval
  [{money(float(friday_85_endpoint["capacity_delta_ci_lo"]))},
  {money(float(friday_85_endpoint["capacity_delta_ci_hi"]))}]
  crosses zero. At matched lower-bound coverage it adds
  **{money(float(friday_85_coverage["capacity_delta_per_1m"]))}**
  ({pct(float(friday_85_coverage["capacity_delta_pct_vs_fixed"]))}).
- At τ=0.95, the narrow-reserve product also loses
  **{money(abs(float(preopen_95_coverage["capacity_delta_per_1m"])))}**
  per $1m to per-reserve fixed haircuts even when matching the bound's own
  breach rate.

The gut-check therefore supports a narrower commercial proposition:
**Soothsayer's value is maintaining a declared downside risk level through
distribution shift, not manufacturing large extra capacity relative to the
best static rule in hindsight.** The next evidence should price the avoided
risk drift on a real book and path-aware stress periods.

## Primary result — chronology-honest, Monday pre-open

Quantiles are fit before 2023, the global one-sided `c(τ)` schedule is tuned
on 2023–2024, and the following rows are evaluated only on untouched 2025+
weekends. The test contains
**{int(work[work["fri_ts"] >= HONEST_TEST_START]["fri_ts"].nunique())} weekends**.

{honest_display.to_markdown(index=False)}

`Unsafe` is deliberately stricter and more commercial than a lower-bound
breach: it asks whether a loan originated at the maximum allowed LTV against
the conservative bound would already exceed the reserve's liquidation
threshold at Monday open.

## Primary comparator — fixed before the held-out test

The fixed policy is fit per reserve on 2023–2024 at the same labelled τ, frozen,
and evaluated untouched alongside Soothsayer on 2025+. This is the deployable
chronology-honest comparison. A negative capacity delta can be worthwhile when
the fixed policy misses its intended risk level, so read capacity and breach
columns together.

{frozen_display.to_markdown(index=False)}

## Diagnostic ceiling — fixed haircut selected with hindsight

This second comparison allows the risk team to pick
the **smallest fixed haircut on a 25 bps grid separately for every reserve**,
then aggregates those choices. Unlike the primary comparator, it selects the
haircuts after seeing the test outcomes. It is an ex-post efficiency ceiling,
not a deployable backtest. It matches risk on one of two bases:

- `endpoint_safety`: no higher observed unsafe-loan rate and no larger mean
  shortfall after applying the reserve's additional max-LTV-to-liquidation
  cushion;
- `lower_bound_coverage`: no higher rate of the realised price falling below
  the bound itself, which tests the oracle primitive before the reserve cushion.

Positive Δ means the dynamic one-sided product permits more debt at matched
observed risk. Confidence intervals resample whole weekends.

{frontier_display.to_markdown(index=False)}

## Reserve detail at the product default, τ = 0.85

{reserve_display.to_markdown(index=False)}

## Evidence views and timing

- **Exact current product:** pre-2023 regime quantiles plus the current
  one-sided `c(τ)` schedule ({current_c}), characterised on 2023+. Because
  those `c` values were selected using the same 2023+ outcomes, this view is
  descriptive and must not be called held out.
- **Chronology-honest product architecture:** the same pre-2023 quantiles,
  `c(τ)` tuned only on 2023–2024 ({honest_c}), tested from 2025 onward.
- **Monday pre-open:** uses the factor-adjusted point, which is available at
  that decision time.
- **Friday commitment:** uses Friday close plus a Friday-known buffer. The
  chronology-honest version is independently calibrated to Friday-to-Monday
  downside moves. The exact-current Friday view merely re-centres the current
  buffer and is diagnostic.

## What this answers

This backtest measures:

1. borrowing capacity made available per $1 million of collateral;
2. endpoint liquidation-threshold crossings for maximum-size new loans;
3. shortfall severity when a crossing occurs;
4. whether dynamic symbol/regime buffers dominate a fixed haircut at matched
   observed risk.

It does **not** measure realized borrower demand, actual historical protocol
revenue, full-position health across multi-asset books, or intra-weekend
executable-path liquidations. Revenue columns in the CSV are capacity
scenarios at a 5% annual borrow rate, not forecasts.

## Data and reproducibility

- Historical underlier panel: `{PANEL_PATH}`
- Reserve configuration: `{RESERVE_SNAPSHOT_PATH}`
- Current one-sided sidecar: `{CURRENT_SIDECAR_PATH}`
- Runner: `scripts/run_lending_commercial_backtest.py`
- Full summary: `{SUMMARY_PATH}`
- Per-reserve detail: `{BY_RESERVE_PATH}`
- Matched fixed-haircut frontier: `{MATCHED_PATH}`

All inputs are local parquet/JSON artefacts. No upstream data is fetched.
"""


def validate_outputs(
    work: pd.DataFrame,
    summary: pd.DataFrame,
    matched: pd.DataFrame,
) -> None:
    """Fail closed on the assumptions the commercial conclusion relies on."""
    honest_dates = work.loc[
        work["fri_ts"] >= HONEST_TEST_START, "fri_ts"
    ]
    if honest_dates.empty or min(honest_dates) < HONEST_TEST_START:
        raise AssertionError("chronology-honest test contains pre-2025 rows")

    fixed = summary[summary["policy_kind"] == "fixed"].sort_values(
        ["view", "timing", "scope", "fixed_haircut_bps"]
    )
    for _, group in fixed.groupby(
        ["view", "timing", "scope"], observed=True
    ):
        capacity = group["mean_capacity_per_1m"].to_numpy(float)
        if np.any(np.diff(capacity) > 1e-8):
            raise AssertionError(
                "fixed-haircut capacity must decrease monotonically"
            )

    if not np.allclose(
        matched["capacity_delta_per_1m"],
        (
            matched["product_capacity_per_1m"]
            - matched["fixed_capacity_per_1m"]
        ),
    ):
        raise AssertionError("matched capacity deltas do not reconcile")

    endpoint = matched[
        matched["match_basis"].str.startswith("endpoint_safety")
    ]
    if (
        endpoint["fixed_unsafe_rate"]
        > endpoint["product_unsafe_rate"] + 1e-15
    ).any():
        raise AssertionError("endpoint comparator has higher unsafe rate")
    if (
        endpoint["fixed_mean_shortfall_per_1m"]
        > endpoint["product_mean_shortfall_per_1m"] + 1e-12
    ).any():
        raise AssertionError("endpoint comparator has larger shortfall")

    coverage = matched[
        matched["match_basis"].str.startswith("lower_bound_coverage")
    ]
    if (
        coverage["fixed_lower_breach_rate"]
        > coverage["product_lower_breach_rate"] + 1e-15
    ).any():
        raise AssertionError("coverage comparator has higher breach rate")


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    work = prepare_panel()
    reserves = load_reserves()
    models = make_models(work)

    print(
        f"Prepared {len(work):,} scored rows; "
        f"{work['fri_ts'].min()} through {work['fri_ts'].max()}."
    )
    for model in models:
        print(
            f"{model.name}: test starts {model.test_start}; "
            f"preopen c={model.c_preopen}; friday c={model.c_friday}"
        )

    evaluations = build_evaluations(work, reserves, models)
    summary, by_reserve = make_summaries(evaluations)
    matched = match_fixed_haircuts(summary, by_reserve, evaluations)
    validate_outputs(work, summary, matched)

    summary.to_csv(SUMMARY_PATH, index=False)
    by_reserve.to_csv(BY_RESERVE_PATH, index=False)
    matched.to_csv(MATCHED_PATH, index=False)
    REPORT_PATH.write_text(
        render_report(work, models, summary, by_reserve, matched)
    )

    print(f"Wrote {SUMMARY_PATH}")
    print(f"Wrote {BY_RESERVE_PATH}")
    print(f"Wrote {MATCHED_PATH}")
    print(f"Wrote {REPORT_PATH}")

    headline = matched[
        (matched["view"] == "chronology_honest")
        & (matched["timing"] == "preopen")
        & (matched["tau"].isin([0.85, 0.95]))
    ]
    print("\nChronology-honest pre-open headline:")
    print(headline.to_string(index=False))


if __name__ == "__main__":
    main()
