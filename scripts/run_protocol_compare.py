"""
Supplemental Kamino-vs-Soothsayer protocol comparison on the held-out slice.

This script is intentionally additive: it does not change the existing
calibration or A/B outputs. Instead it adds three stronger comparator tests:

1. Dense LTV sweep near the lending thresholds.
2. Full 3-state decision confusion (Safe / Caution / Liquidate).
3. Weekend-block bootstrap confidence intervals on deltas vs Kamino.

The Soothsayer side uses the real Oracle serving path on the OOS slice:
surface trained on pre-split data, bands served on post-split weekends.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from soothsayer.backtest import calibration as cal
from soothsayer.backtest.protocol_compare import (
    DEFAULT_TRUTH_MODES,
    DEFAULT_REGIME_MULTIPLIERS,
    DEFAULT_WEIGHT_SCHEMES,
    KAMINO_BPS,
    apply_weight_scheme,
    build_weight_lookup,
    bootstrap_variant_deltas,
    decision_confusion,
    enrich_observation_rows,
    evaluate_price_grid,
    kamino_lower_price,
    make_ltv_grid,
    realized_truth_config,
    summarize_variant_rows,
)
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


SPLIT_DATE = date(2023, 1, 1)
DEFAULT_TARGETS = (0.80, 0.85, 0.90, 0.95)
DEFAULT_BOOTSTRAPS = 1000
DEFAULT_SEED = 0xA11CE55


def _tables_dir() -> Path:
    path = REPORTS / "tables"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _parse_targets(raw: str) -> tuple[float, ...]:
    vals = tuple(float(x.strip()) for x in raw.split(",") if x.strip())
    if not vals:
        raise ValueError("must provide at least one target")
    return vals


def _parse_csv_list(raw: str) -> tuple[str, ...]:
    vals = tuple(x.strip() for x in raw.split(",") if x.strip())
    if not vals:
        raise ValueError("must provide at least one value")
    return vals


def _load_oos_oracle(split_date: date) -> tuple[Oracle, pd.DataFrame]:
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds["mon_ts"] = pd.to_datetime(bounds["mon_ts"]).dt.date

    panel_full = bounds[
        ["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]
    ].drop_duplicates(subset=["symbol", "fri_ts"]).reset_index(drop=True)

    bounds_oos = bounds[bounds["fri_ts"] >= split_date].reset_index(drop=True)
    bounds_train = bounds[bounds["fri_ts"] < split_date].reset_index(drop=True)
    panel_oos = panel_full[panel_full["fri_ts"] >= split_date].reset_index(drop=True)

    train_surface = cal.compute_calibration_surface(bounds_train)
    train_pooled = cal.pooled_surface(bounds_train)
    oracle = Oracle(bounds=bounds_oos, surface=train_surface, surface_pooled=train_pooled)
    return oracle, panel_oos


def _serve_rows(
    oracle: Oracle,
    panel_oos: pd.DataFrame,
    *,
    ltv_grid,
    targets: tuple[float, ...],
    truth_modes: tuple[str, ...],
    kamino_bps: float,
    include_case_b: bool,
) -> pd.DataFrame:
    rows: list[dict] = []

    for _, weekend in panel_oos.iterrows():
        symbol = weekend["symbol"]
        fri_ts = weekend["fri_ts"]
        regime = str(weekend["regime_pub"])
        fri_close = float(weekend["fri_close"])
        mon_open = float(weekend["mon_open"])

        kamino = evaluate_price_grid(
            fri_close=fri_close,
            comparison_price=kamino_lower_price(fri_close, kamino_bps),
            regime=regime,
            ltv_grid=ltv_grid,
            demote_threshold=False,
        )
        kamino["variant"] = f"kamino_flat_{int(kamino_bps)}bps"
        kamino["protocol"] = "kamino"
        kamino["target"] = pd.NA
        kamino["target_label"] = f"flat_{int(kamino_bps)}bps"
        kamino["claim_served"] = pd.NA
        kamino["half_width_bps"] = kamino_bps
        kamino["clipped_forces_caution"] = False
        kamino["demote_threshold_pred"] = False

        frames = [kamino]
        for target in targets:
            pp = oracle.fair_value(symbol, fri_ts, target_coverage=target)
            common = dict(
                protocol="soothsayer",
                target=target,
                target_label=f"{target:.3f}",
                claim_served=pp.claimed_coverage_served,
                half_width_bps=pp.half_width_bps,
                clipped_forces_caution=pp.claimed_coverage_served >= 0.995,
            )
            case_a = evaluate_price_grid(
                fri_close=fri_close,
                comparison_price=float(pp.lower),
                regime=regime,
                ltv_grid=ltv_grid,
                demote_threshold=False,
                clipped_forces_caution=common["clipped_forces_caution"],
            )
            case_a["variant"] = f"ss_case_a_t{int(round(target * 1000)):03d}"
            for key, value in common.items():
                case_a[key] = value
            case_a["demote_threshold_pred"] = False
            frames.append(case_a)

            if include_case_b:
                case_b = evaluate_price_grid(
                    fri_close=fri_close,
                    comparison_price=float(pp.lower),
                    regime=regime,
                    ltv_grid=ltv_grid,
                    demote_threshold=True,
                    clipped_forces_caution=common["clipped_forces_caution"],
                    regime_multipliers=DEFAULT_REGIME_MULTIPLIERS,
                )
                case_b["variant"] = f"ss_case_b_t{int(round(target * 1000)):03d}"
                for key, value in common.items():
                    case_b[key] = value
                case_b["demote_threshold_pred"] = True
                frames.append(case_b)

        combined = pd.concat(frames, ignore_index=True)
        combined = combined.rename(columns={"decision": "decision_pred", "current_ltv": "ltv_pred"})
        combined["symbol"] = symbol
        combined["fri_ts"] = fri_ts
        combined["mon_ts"] = weekend["mon_ts"]
        combined["regime_pub"] = regime
        combined["fri_close"] = fri_close
        combined["mon_open"] = mon_open

        for truth_mode in truth_modes:
            truth_frames = []
            for _, variant_frame in combined.groupby("variant", observed=True, dropna=False):
                truth_cfg = realized_truth_config(
                    truth_mode,
                    demote_threshold=bool(variant_frame["demote_threshold_pred"].iloc[0]),
                    clipped_forces_caution=bool(variant_frame["clipped_forces_caution"].iloc[0]),
                )
                realized = evaluate_price_grid(
                    fri_close=fri_close,
                    comparison_price=mon_open,
                    regime=regime,
                    ltv_grid=ltv_grid,
                    demote_threshold=truth_cfg["demote_threshold"],
                    clipped_forces_caution=truth_cfg["clipped_forces_caution"],
                ).rename(columns={"decision": "decision_realized", "current_ltv": "ltv_realized"})
                truth_variant = variant_frame.merge(realized, on="ltv_target", how="left")
                truth_variant["truth_mode"] = truth_mode
                truth_frames.append(truth_variant)
            rows.extend(pd.concat(truth_frames, ignore_index=True).to_dict(orient="records"))

    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Held-out Kamino vs Soothsayer protocol comparison.")
    parser.add_argument("--targets", default="0.80,0.85,0.90,0.95")
    parser.add_argument(
        "--truths",
        default="economic_flat85,policy_consistent",
        help="Comma-separated truth modes. Options: economic_flat85, policy_consistent",
    )
    parser.add_argument(
        "--weightings",
        default="uniform_ltv,borrower_heavy,threshold_heavy,debt_weighted",
        help="Comma-separated weight schemes. Options: uniform_ltv, borrower_heavy, threshold_heavy, debt_weighted, custom_csv",
    )
    parser.add_argument(
        "--weight-csv",
        type=str,
        default=None,
        help="Optional CSV with columns ltv_target,weight for custom_csv weighting.",
    )
    parser.add_argument("--ltv-start", type=float, default=0.70)
    parser.add_argument("--ltv-end", type=float, default=0.90)
    parser.add_argument("--ltv-step-bps", type=float, default=25.0)
    parser.add_argument("--kamino-bps", type=float, default=KAMINO_BPS)
    parser.add_argument("--n-boot", type=int, default=DEFAULT_BOOTSTRAPS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--no-case-b", action="store_true", help="Skip regime-demoted threshold variant.")
    args = parser.parse_args()

    targets = _parse_targets(args.targets)
    truths = _parse_csv_list(args.truths)
    weightings = _parse_csv_list(args.weightings)
    ltv_grid = make_ltv_grid(args.ltv_start, args.ltv_end, args.ltv_step_bps)

    unknown_truths = sorted(set(truths) - set(DEFAULT_TRUTH_MODES))
    if unknown_truths:
        raise ValueError(f"unknown truth modes: {unknown_truths}")
    unknown_weightings = sorted(set(weightings) - (set(DEFAULT_WEIGHT_SCHEMES) | {"custom_csv"}))
    if unknown_weightings:
        raise ValueError(f"unknown weighting schemes: {unknown_weightings}")
    if "custom_csv" in weightings and not args.weight_csv:
        raise ValueError("--weight-csv is required when using custom_csv weighting")

    print("Loading held-out Oracle comparison setup...")
    oracle, panel_oos = _load_oos_oracle(SPLIT_DATE)
    print(f"  held-out rows: {len(panel_oos):,} symbol-weekends")
    print(f"  LTV grid: {len(ltv_grid)} points from {ltv_grid[0]:.3f} to {ltv_grid[-1]:.3f}")
    print(f"  targets: {targets}")
    print(f"  truth modes: {truths}")
    print(f"  weight schemes: {weightings}")

    raw_rows = _serve_rows(
        oracle,
        panel_oos,
        ltv_grid=ltv_grid,
        targets=targets,
        truth_modes=truths,
        kamino_bps=args.kamino_bps,
        include_case_b=not args.no_case_b,
    )
    rows = enrich_observation_rows(raw_rows)

    weight_lookups = {
        scheme: build_weight_lookup(
            ltv_grid,
            weight_scheme=scheme,
            custom_weights_path=Path(args.weight_csv) if scheme == "custom_csv" and args.weight_csv else None,
        )
        for scheme in weightings
    }

    pooled_frames = []
    regime_frames = []
    ltv_frames = []
    confusion_frames = []
    boot_frames = []
    baseline_variant = f"kamino_flat_{int(args.kamino_bps)}bps"

    for truth_mode in truths:
        truth_rows = rows[rows["truth_mode"] == truth_mode].copy()
        for weight_scheme in weightings:
            weighted_rows = apply_weight_scheme(
                truth_rows,
                weight_scheme=weight_scheme,
                weight_lookup=weight_lookups[weight_scheme],
            )
            pooled = summarize_variant_rows(
                weighted_rows,
                ["truth_mode", "weight_scheme", "variant", "protocol", "target", "target_label"],
            ).sort_values(["truth_mode", "weight_scheme", "variant"])
            by_regime = summarize_variant_rows(
                weighted_rows,
                ["truth_mode", "weight_scheme", "variant", "protocol", "target", "target_label", "regime_pub"],
            ).sort_values(["truth_mode", "weight_scheme", "variant", "regime_pub"])
            by_ltv = summarize_variant_rows(
                weighted_rows,
                ["truth_mode", "weight_scheme", "variant", "protocol", "target", "target_label", "ltv_target"],
            ).sort_values(["truth_mode", "weight_scheme", "variant", "ltv_target"])
            confusion = decision_confusion(
                weighted_rows,
                ["truth_mode", "weight_scheme", "variant", "protocol", "target", "target_label", "regime_pub"],
            )
            compare_variants = sorted(v for v in weighted_rows["variant"].astype(str).unique().tolist() if v != baseline_variant)
            boot = bootstrap_variant_deltas(
                weighted_rows,
                baseline_variant=baseline_variant,
                compare_variants=compare_variants,
                n_boot=args.n_boot,
                seed=args.seed,
                weight_col="row_weight",
            )
            boot["truth_mode"] = truth_mode
            boot["weight_scheme"] = weight_scheme

            pooled_frames.append(pooled)
            regime_frames.append(by_regime)
            ltv_frames.append(by_ltv)
            confusion_frames.append(confusion)
            boot_frames.append(boot)

    pooled = pd.concat(pooled_frames, ignore_index=True)
    by_regime = pd.concat(regime_frames, ignore_index=True)
    by_ltv = pd.concat(ltv_frames, ignore_index=True)
    confusion = pd.concat(confusion_frames, ignore_index=True)
    boot = pd.concat(boot_frames, ignore_index=True)

    tables_dir = _tables_dir()
    raw_path = tables_dir / "protocol_compare_rows.parquet"
    pooled_path = tables_dir / "protocol_compare_summary.csv"
    regime_path = tables_dir / "protocol_compare_by_regime.csv"
    ltv_path = tables_dir / "protocol_compare_by_ltv.csv"
    confusion_path = tables_dir / "protocol_compare_confusion.csv"
    boot_path = tables_dir / "protocol_compare_bootstrap.csv"

    rows.to_parquet(raw_path, index=False)
    pooled.to_csv(pooled_path, index=False)
    by_regime.to_csv(regime_path, index=False)
    by_ltv.to_csv(ltv_path, index=False)
    confusion.to_csv(confusion_path, index=False)
    boot.to_csv(boot_path, index=False)

    print()
    print("Pooled summary")
    print("=" * 88)
    preview = pooled[
        (pooled["truth_mode"] == truths[0]) & (pooled["weight_scheme"] == weightings[0])
    ].copy()
    display_cols = [
        "truth_mode",
        "weight_scheme",
        "variant",
        "mean_half_width_bps",
        "fp_liq_rate",
        "miss_liq_rate",
        "false_caution_rate",
        "missed_caution_rate",
        "expected_loss",
    ]
    print(preview[display_cols].to_string(index=False, float_format=lambda x: f"{x:0.4f}"))
    print()
    print("Wrote:")
    print(f"  {pooled_path}")
    print(f"  {regime_path}")
    print(f"  {ltv_path}")
    print(f"  {confusion_path}")
    print(f"  {boot_path}")
    print(f"  {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
