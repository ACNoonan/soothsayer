"""
Freeze a 5-variant σ̂ schedule bundle for forward-tape held-out re-validation.

This is the §13.6 selection-procedure mitigation: the canonical M6 LWC
deployment runs only one σ̂ rule (EWMA HL=8 since the 2026-05-04 promotion),
but the variant comparison that selected HL=8 was multi-test exposed across
80 split-date Christoffersen cells. To re-validate the selection on data
the comparison never saw, the forward-tape harness needs frozen schedules
for *every* variant that was on the ladder, evaluated against the same
forward weekends.

This script materialises that bundle. It fits each of the 5 variants
({baseline_k26, ewma_hl6, ewma_hl8, ewma_hl12, blend_a50_hl8}) on the
same training cutoff (split=2023-01-01) using identical evaluable rows,
and writes a single bundle JSON with every variant's
(regime_quantile_table, c_bump_schedule, delta_shift_schedule, σ̂ descriptor).

The bundle is content-addressed (SHA-256 over canonical-JSON serialisation)
and date-tagged. Lifecycle is independent of the canonical
`lwc_artefact_v1_frozen_*` files — the canonical deployment artefact is
the source of truth for what the live oracle serves; the variant bundle
is *only* for forward-tape evaluation. Two distinct files, two distinct
glob patterns, no overlap.

Reproduces deterministically from `seed=0` and the v1b panel. Mirrors the
fit logic in `scripts/run_sigma_ewma_variants.py::run_variant` (§5.2 step
B) so the bundle's per-variant schedules are byte-for-byte identical to
what that script computed for Phase 5.

Run
---
  uv run python scripts/freeze_sigma_ewma_variant_bundle.py             # date = today
  uv run python scripts/freeze_sigma_ewma_variant_bundle.py --date 2026-05-04
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    SIGMA_HAT_K,
    SIGMA_HAT_MIN,
    add_sigma_hat_sym,
    add_sigma_hat_sym_blend,
    add_sigma_hat_sym_ewma,
    compute_score_lwc,
    fit_c_bump_schedule,
    train_quantile_table,
)
from soothsayer.config import DATA_PROCESSED


SPLIT_DATE = date(2023, 1, 1)
REGIMES = ("normal", "long_weekend", "high_vol")
TARGETS = (0.68, 0.85, 0.95, 0.99)
BUNDLE_SCHEMA_VERSION = "lwc_variant_bundle.v1"

# Mirror Phase 5's σ̂ ladder. The forward-tape evaluator dispatches on
# `sigma_hat.method` + `sigma_hat.half_life_weekends` + (for blend)
# `sigma_hat.alpha`, so adding/removing a variant here propagates without
# any other change.
VARIANT_SPECS: list[dict] = [
    {
        "name": "baseline_k26",
        "label": "K=26 trailing window (M6 baseline pre-2026-05-04)",
        "sigma_hat": {
            "method": "trailing_window",
            "K_weekends": int(SIGMA_HAT_K),
            "half_life_weekends": None,
            "alpha": None,
            "min_past_obs": int(SIGMA_HAT_MIN),
            "raw_column": "sigma_hat_sym_pre_fri",
        },
    },
    {
        "name": "ewma_hl6",
        "label": "EWMA HL=6",
        "sigma_hat": {
            "method": "ewma",
            "K_weekends": None,
            "half_life_weekends": 6,
            "alpha": None,
            "min_past_obs": int(SIGMA_HAT_MIN),
            "raw_column": "sigma_hat_sym_ewma_pre_fri_hl6",
        },
    },
    {
        "name": "ewma_hl8",
        "label": "EWMA HL=8 (canonical M6 since 2026-05-04)",
        "sigma_hat": {
            "method": "ewma",
            "K_weekends": None,
            "half_life_weekends": 8,
            "alpha": None,
            "min_past_obs": int(SIGMA_HAT_MIN),
            "raw_column": "sigma_hat_sym_ewma_pre_fri_hl8",
        },
    },
    {
        "name": "ewma_hl12",
        "label": "EWMA HL=12",
        "sigma_hat": {
            "method": "ewma",
            "K_weekends": None,
            "half_life_weekends": 12,
            "alpha": None,
            "min_past_obs": int(SIGMA_HAT_MIN),
            "raw_column": "sigma_hat_sym_ewma_pre_fri_hl12",
        },
    },
    {
        "name": "blend_a50_hl8",
        "label": "0.5·K=26 + 0.5·EWMA HL=8 convex blend",
        "sigma_hat": {
            "method": "blend",
            "K_weekends": int(SIGMA_HAT_K),
            "half_life_weekends": 8,
            "alpha": 0.5,
            "min_past_obs": int(SIGMA_HAT_MIN),
            "raw_column": "sigma_hat_sym_blend_pre_fri_a50_hl8",
        },
    },
]


def _add_variant_sigma(panel: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, str]:
    """Compute σ̂ on `panel` per `spec`. Returns (panel, raw_col_name)."""
    sigma = spec["sigma_hat"]
    method = sigma["method"]
    if method == "trailing_window":
        out = add_sigma_hat_sym(panel, K=sigma["K_weekends"],
                                min_obs=sigma["min_past_obs"])
        return out, sigma["raw_column"]
    if method == "ewma":
        out = add_sigma_hat_sym_ewma(panel,
                                     half_life=sigma["half_life_weekends"],
                                     min_obs=sigma["min_past_obs"])
        return out, sigma["raw_column"]
    if method == "blend":
        out = add_sigma_hat_sym_blend(panel,
                                      alpha=sigma["alpha"],
                                      half_life=sigma["half_life_weekends"],
                                      K=sigma["K_weekends"],
                                      min_obs=sigma["min_past_obs"])
        return out, sigma["raw_column"]
    raise ValueError(f"Unknown σ̂ method {method!r} for variant {spec['name']!r}")


def _fit_one_variant(panel: pd.DataFrame, spec: dict) -> dict:
    """Fit (qt, cb, δ) for one σ̂ variant at split=2023-01-01.

    Mirrors `run_sigma_ewma_variants.run_variant`'s §5.2.B logic exactly:
    pre-split train, post-split OOS, regime-grouped CP quantile per τ from
    train, smallest c on grid such that mean(score ≤ b·c) ≥ τ on OOS, δ
    inherited from the deployed M6 schedule (all-zero — every variant lands
    there under the same selection criterion; verified by `select_delta_schedule`
    in the Phase 5 driver).
    """
    work, raw_col = _add_variant_sigma(panel, spec)
    work["score"] = compute_score_lwc(work, scale_col=raw_col)
    mask = work["score"].notna() & work[raw_col].notna()
    work = work[mask].copy().reset_index(drop=True)
    train = work[work["fri_ts"] < SPLIT_DATE]
    oos = work[work["fri_ts"] >= SPLIT_DATE]

    qt = train_quantile_table(train, cell_col="regime_pub",
                              taus=DEFAULT_TAUS, score_col="score")
    cb = fit_c_bump_schedule(oos, qt, cell_col="regime_pub",
                             taus=DEFAULT_TAUS, score_col="score")
    delta = {float(t): 0.0 for t in DEFAULT_TAUS}

    return {
        "_lwc_variant": spec["name"],
        "label": spec["label"],
        "split_date": SPLIT_DATE.isoformat(),
        "targets": list(TARGETS),
        "regimes": list(REGIMES),
        "sigma_hat": spec["sigma_hat"],
        "regime_quantile_table": {
            r: {f"{tau:.2f}": float(qt.get(r, {}).get(float(tau), float("nan")))
                for tau in TARGETS}
            for r in REGIMES
        },
        "c_bump_schedule": {f"{tau:.2f}": float(cb[float(tau)]) for tau in TARGETS},
        "delta_shift_schedule": {f"{tau:.2f}": float(delta[float(tau)])
                                 for tau in TARGETS},
        "n_train": int(len(train)),
        "n_oos": int(len(oos)),
        "n_evaluable_rows": int(len(work)),
    }


def _canonical_json_bytes(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        type=lambda s: date.fromisoformat(s),
        default=date.today(),
        help="Freeze date stamp (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args()

    panel_path = DATA_PROCESSED / "v1b_panel.parquet"
    if not panel_path.exists():
        raise FileNotFoundError(
            f"{panel_path} not found. Run scripts/run_calibration.py first."
        )
    panel = pd.read_parquet(panel_path)
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    print(f"Loaded panel: {len(panel):,} rows × "
          f"{panel['fri_ts'].nunique()} weekends × "
          f"{panel['symbol'].nunique()} symbols", flush=True)

    variants_out = []
    for spec in VARIANT_SPECS:
        print(f"  Fitting {spec['name']:>15s}  ({spec['label']})", flush=True)
        variants_out.append(_fit_one_variant(panel, spec))

    bundle = {
        "_schema_version": BUNDLE_SCHEMA_VERSION,
        "_freeze_date": args.date.isoformat(),
        "_fetched_at": datetime.now(timezone.utc).isoformat(),
        "_source": "scripts/freeze_sigma_ewma_variant_bundle.py",
        "methodology_version": "M6_LWC_Phase5_variant_bundle",
        "split_date": SPLIT_DATE.isoformat(),
        "variants": variants_out,
    }
    self_sha = hashlib.sha256(_canonical_json_bytes(bundle)).hexdigest()
    bundle["_artefact_sha256"] = self_sha

    stamp = args.date.strftime("%Y%m%d")
    out_path = DATA_PROCESSED / f"lwc_variant_bundle_v1_frozen_{stamp}.json"
    out_path.write_text(json.dumps(bundle, indent=2) + "\n")

    print()
    print(f"Wrote {out_path}")
    print(f"  _freeze_date     = {bundle['_freeze_date']}")
    print(f"  _artefact_sha256 = {self_sha}")
    print(f"  variants         = {[v['_lwc_variant'] for v in variants_out]}")
    print(f"  split_date       = {SPLIT_DATE.isoformat()}")
    print()
    print("Per-variant c_bump_schedule:")
    for v in variants_out:
        cb = v["c_bump_schedule"]
        bits = "  ".join(f"τ={t}: c={cb[t]:.4f}" for t in cb)
        print(f"  {v['_lwc_variant']:>15s}  {bits}")


if __name__ == "__main__":
    main()
