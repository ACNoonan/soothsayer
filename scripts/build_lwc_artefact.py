"""
Build the M6 (Locally-Weighted Conformal) deployment artefact.

The M6 Oracle serves a band as

    σ̂_sym(t)   = pre-Friday relative-residual scale per symbol (variant-
                  dependent: EWMA HL=8 weekends as of 2026-05-04 σ̂ promotion;
                  K=26 trailing window prior to that). Both rules require
                  ≥ 8 past obs.
    score      = |mon_open - point| / (fri_close · σ̂_sym(t))     standardised
    point      = fri_close · (1 + factor_ret)                     §7.4 switchboard
    τ'         = τ + δ_LWC(τ)
    q          = c_LWC(τ') · q_regime^LWC(regime, τ')              unitless
    half       = q · σ̂_sym(t) · fri_close
    lower / upper = point ∓ half,  point = point

Mirrors `scripts/build_mondrian_artefact.py` (M5) but on the standardised
score. Outputs:

  - data/processed/lwc_artefact_v1.parquet
        per-Friday lookup rows: symbol, fri_ts, regime_pub, fri_close,
        point, sigma_hat_sym_pre_fri  (+ scryer-style metadata).
        The `sigma_hat_sym_pre_fri` column always holds the active variant's
        σ̂ value — readers (Oracle, smoke, freeze) need not change when the
        variant rule changes. The sidecar's `_lwc_variant` field records
        which σ̂ rule produced the column.

  - data/processed/lwc_artefact_v1.json
        audit-trail sidecar with the 12 trained quantiles q_r^LWC(τ),
        4 OOS-fit c_LWC(τ) bumps, 4 δ_LWC(τ) shifts, the σ̂ rule
        descriptor, and n_train / n_oos / dropped-warm-up counts. Constants
        here are the single source of truth loaded by `src/soothsayer/oracle.py`
        at module import for the LWC serving path.

References:
  - reports/m6_sigma_ewma.md — Phase 5 σ̂ EWMA promotion (2026-05-04).
    Headline: EWMA HL=8 narrows pooled half-width by 3.83% at τ=0.95 vs
    the K=26 baseline AND clears split-date Christoffersen at every
    (split × τ) at α=0.05 (baseline rejected at 2021/2022 × τ=0.95).
  - reports/v3_bakeoff.md (Candidate 1) — original LWC validation against
    M5; reproduced byte-for-byte on the K=26 σ̂ rule.
  - reports/tables/v1b_lwc_delta_sweep.csv (baseline δ source).
  - reports/tables/sigma_ewma_*_delta_sweep.csv (EWMA δ source).
  - M6_REFACTOR.md Phase 1 + Phase 5.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    SIGMA_HAT_K,
    SIGMA_HAT_MIN,
    add_sigma_hat_sym,
    add_sigma_hat_sym_ewma,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95, 0.99)
REGIMES = ("normal", "long_weekend", "high_vol")
SCHEMA_VERSION = "lwc.v1"
ARTEFACT_PARQUET = DATA_PROCESSED / "lwc_artefact_v1.parquet"
ARTEFACT_JSON = DATA_PROCESSED / "lwc_artefact_v1.json"

# σ̂ variant catalogue. Phase 5 added EWMA HL=8 as the canonical variant
# (M6_REFACTOR.md §5; reports/m6_sigma_ewma.md). The K=26 baseline remains
# buildable for archival reproduction of the v3 bake-off receipts.
SIGMA_VARIANT_CANONICAL = "ewma_hl8"
SIGMA_VARIANTS: dict[str, dict] = {
    "baseline_k26": {
        "method": "trailing_window",
        "K_weekends": int(SIGMA_HAT_K),
        "half_life_weekends": None,
        "description": (
            "trailing-K weekend std of relative residual per symbol; "
            "strictly pre-Friday (uses only fri_ts' < fri_ts)"
        ),
    },
    "ewma_hl8": {
        "method": "ewma",
        "K_weekends": None,
        "half_life_weekends": 8,
        "description": (
            "EWMA std of relative residual per symbol with weekend "
            "half-life HL=8 (decay λ = 0.5 ** (1/8)); strictly pre-Friday "
            "(uses only fri_ts' < fri_ts); requires ≥ 8 past obs"
        ),
    },
}

# δ-shift schedule selected from `reports/tables/v1b_lwc_delta_sweep.csv`.
# Selection criterion (mirrors M5): smallest δ such that pooled walk-forward
# realised coverage at every τ ≥ nominal. Under LWC every τ already has
# cov_mean ≥ τ at δ = 0 (margins +3.26 / +2.95 / +1.45 / +0.37 pp), so the
# all-zero schedule clears the criterion. This is a finding worth flagging:
# LWC's per-symbol-scale standardisation tightens cross-split calibration
# variance, so the M5-style overshoot margin is no longer load-bearing.
# Worst-split deficits (−1.74 pp at τ=0.95, −0.23 pp at τ=0.99) are within
# the splitting noise; raising δ to clear them costs +30% / +53% on width
# (a c-grid discontinuity at τ=0.99) for negligible coverage gain.
DELTA_SHIFT_SCHEDULE: dict[float, float] = {
    0.68: 0.00,
    0.85: 0.00,
    0.95: 0.00,
    0.99: 0.00,
}


def _train_quantile(scores: np.ndarray, tau: float) -> float:
    """Split-CP finite-sample quantile: rank ceil(τ·(n+1)) of sorted scores."""
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
    """Smallest c on `grid` with mean(score ≤ b·c) ≥ τ on OOS rows.
    Mirrors `_fit_c_bump` in build_mondrian_artefact.py."""
    valid = np.isfinite(b_per_row) & np.isfinite(scores_oos)
    s = scores_oos[valid]
    b = b_per_row[valid]
    for c in grid:
        if float(np.mean(s <= b * c)) >= tau:
            return float(c)
    return float(grid[-1])


def _add_sigma_variant(panel: pd.DataFrame, variant: str) -> tuple[pd.DataFrame, str]:
    """Compute σ̂ per `variant` and write it under `sigma_hat_sym_pre_fri`.

    Returns (panel_with_column, raw_column_name). The Oracle reads from
    `sigma_hat_sym_pre_fri` regardless of variant; the `_lwc_variant` field
    in the JSON sidecar tells consumers which rule produced it."""
    if variant == "baseline_k26":
        out = add_sigma_hat_sym(panel, K=SIGMA_HAT_K, min_obs=SIGMA_HAT_MIN)
        raw_col = "sigma_hat_sym_pre_fri"
        return out, raw_col
    if variant == "ewma_hl8":
        out = add_sigma_hat_sym_ewma(panel, half_life=8, min_obs=SIGMA_HAT_MIN)
        raw_col = "sigma_hat_sym_ewma_pre_fri_hl8"
        # Surface the EWMA value under the canonical column the Oracle reads.
        out["sigma_hat_sym_pre_fri"] = out[raw_col]
        return out, raw_col
    raise ValueError(
        f"Unknown σ̂ variant {variant!r}. Choices: {list(SIGMA_VARIANTS)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant", choices=list(SIGMA_VARIANTS),
        default=SIGMA_VARIANT_CANONICAL,
        help="σ̂ rule. Default %(default)r is the canonical M6 variant since "
             "the 2026-05-04 Phase 5 promotion. Pass `baseline_k26` to "
             "reproduce the original v3-bakeoff receipts.",
    )
    args = parser.parse_args()
    variant = args.variant
    variant_info = SIGMA_VARIANTS[variant]
    print(f"σ̂ variant: {variant}  ({variant_info['description']})", flush=True)

    panel_path = DATA_PROCESSED / "v1b_panel.parquet"
    if not panel_path.exists():
        raise FileNotFoundError(
            f"{panel_path} not found. Run `uv run python scripts/run_calibration.py` "
            "first to materialise the v1b panel."
        )
    panel = pd.read_parquet(panel_path)
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    panel["point"] = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )

    # σ̂_sym(t): variant-dependent pre-Friday symbol-scale (see SIGMA_VARIANTS).
    # Rows below the warm-up boundary (< SIGMA_HAT_MIN past obs) get NaN and
    # are excluded from train + OOS.
    panel, sigma_raw_col = _add_sigma_variant(panel, variant)
    panel["score"] = compute_score_lwc(panel, scale_col="sigma_hat_sym_pre_fri")

    n_pre_filter = len(panel)
    mask = panel["score"].notna() & panel["sigma_hat_sym_pre_fri"].notna()
    work = panel[mask].copy().reset_index(drop=True)
    n_dropped_warmup = n_pre_filter - len(work)

    train = work[work["fri_ts"] < SPLIT_DATE].copy()
    oos = work[work["fri_ts"] >= SPLIT_DATE].copy()

    print(f"Panel after σ̂_sym filter: {len(work):,} rows × "
          f"{work['fri_ts'].nunique()} weekends "
          f"(dropped {n_dropped_warmup:,} warm-up rows)")
    print(f"Train: {len(train):,} rows × {train['fri_ts'].nunique()} weekends")
    print(f"OOS:   {len(oos):,} rows × {oos['fri_ts'].nunique()} weekends")
    print()

    # --- Step 1: trained per-regime quantiles q_r^LWC(τ)
    quantile_table: dict[str, dict[float, float]] = {r: {} for r in REGIMES}
    for r in REGIMES:
        scores_r = train.loc[train["regime_pub"] == r, "score"].to_numpy(float)
        for tau in TARGETS:
            quantile_table[r][tau] = _train_quantile(scores_r, tau)

    print("Trained per-regime LWC quantiles q_r^LWC(τ) [unitless]:")
    for r in REGIMES:
        cells = "  ".join(
            f"τ={tau:.2f}: {quantile_table[r][tau]:.4f}" for tau in TARGETS
        )
        print(f"  {r:>14}  {cells}")
    print()

    # --- Step 2: OOS-fit c_LWC(τ) on standardised residuals
    c_grid = np.arange(1.0, 5.0001, 0.001)
    c_bump_schedule: dict[float, float] = {}
    for tau in TARGETS:
        b_per_row = np.array(
            [quantile_table[r][tau] for r in oos["regime_pub"]],
            dtype=float,
        )
        c_bump_schedule[tau] = _fit_c_bump(
            oos["score"].to_numpy(float), b_per_row, tau, c_grid
        )

    print("OOS-fit c_LWC(τ) bumps:")
    for tau in TARGETS:
        print(f"  τ={tau:.2f}: c={c_bump_schedule[tau]:.4f}")
    print()
    print("δ_LWC(τ) schedule (from run_lwc_delta_sweep.py):")
    for tau in TARGETS:
        print(f"  τ={tau:.2f}: δ={DELTA_SHIFT_SCHEDULE[tau]:.3f}")
    print()

    # --- Step 3: per-Friday lookup parquet (over the full filtered panel,
    # train + OOS — every served row needs σ̂ available)
    rows = work[
        ["symbol", "fri_ts", "regime_pub", "fri_close", "point",
         "sigma_hat_sym_pre_fri"]
    ].copy()
    rows["_schema_version"] = SCHEMA_VERSION
    rows["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    rows["_source"] = "scripts/build_lwc_artefact.py"
    rows = rows.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)
    rows.to_parquet(ARTEFACT_PARQUET, index=False)
    print(f"Wrote {ARTEFACT_PARQUET}  ({len(rows):,} rows, "
          f"{rows['symbol'].nunique()} symbols, "
          f"{rows['fri_ts'].nunique()} weekends)")

    # --- Step 4: JSON sidecar with the 12 + 4 + 4 deployment scalars
    sidecar = {
        "_schema_version": SCHEMA_VERSION,
        "_fetched_at": datetime.now(timezone.utc).isoformat(),
        "_source": "scripts/build_lwc_artefact.py",
        "methodology_version": "M6_LWC",
        "_lwc_variant": variant,
        "split_date": SPLIT_DATE.isoformat(),
        "targets": list(TARGETS),
        "regimes": list(REGIMES),
        "sigma_hat": {
            "method": variant_info["method"],
            "K_weekends": variant_info["K_weekends"],
            "half_life_weekends": variant_info["half_life_weekends"],
            "min_past_obs": int(SIGMA_HAT_MIN),
            "rule": variant_info["description"],
            "raw_column": sigma_raw_col,
        },
        "regime_quantile_table": {
            r: {f"{tau:.2f}": quantile_table[r][tau] for tau in TARGETS}
            for r in REGIMES
        },
        "c_bump_schedule": {
            f"{tau:.2f}": c_bump_schedule[tau] for tau in TARGETS
        },
        "delta_shift_schedule": {
            f"{tau:.2f}": DELTA_SHIFT_SCHEDULE[tau] for tau in TARGETS
        },
        "n_train": int(len(train)),
        "n_oos": int(len(oos)),
        "n_dropped_warmup": int(n_dropped_warmup),
    }
    ARTEFACT_JSON.write_text(json.dumps(sidecar, indent=2) + "\n")
    print(f"Wrote {ARTEFACT_JSON}")


if __name__ == "__main__":
    main()
