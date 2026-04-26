"""
Generate JSON data files for the Soothsayer dashboard at landing/dashboard.html
(and the inline charts on landing/index.html). Reads from `reports/tables/*.csv`
and `data/processed/*.parquet`; writes to `landing/data/*.json`.

Run after any methodology change that affects published numbers.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "reports" / "tables"
RAW = ROOT / "data" / "processed"
OUT = ROOT / "landing" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def _safe_float(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


def _safe_int(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return int(v)


def write_json(path: Path, payload):
    with path.open("w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"  wrote {path.relative_to(ROOT)}  ({len(json.dumps(payload))} bytes)")


def build_calibration_curve():
    df = pd.read_csv(TABLES / "v1b_diag_inter_anchor_tau.csv")
    points = [
        {
            "tau": _safe_float(r["tau"]),
            "n": _safe_int(r["n"]),
            "realized": _safe_float(r["realized"]),
            "half_width_bps": _safe_float(r["mean_half_width_bps"]),
            "p_uc": _safe_float(r["p_uc"]),
            "p_ind": _safe_float(r["p_ind"]),
            "is_anchor": bool(r["is_anchor"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(OUT / "calibration_curve.json", points)


def build_pyth_comparator():
    df = pd.read_csv(TABLES / "pyth_coverage_by_k.csv")
    pooled = df[df["scope"] == "pooled"].sort_values("k").reset_index(drop=True)
    points = [
        {
            "k": _safe_float(r["k"]),
            "n": _safe_int(r["n"]),
            "realized": _safe_float(r["realized"]),
            "half_width_bps": _safe_float(r["mean_halfwidth_bps"]),
        }
        for _, r in pooled.iterrows()
    ]
    write_json(OUT / "pyth_comparator.json", points)


def build_chainlink_comparator():
    df = pd.read_csv(TABLES / "chainlink_implicit_band.csv")
    points = [
        {
            "k_pct": _safe_float(r["k_pct"]),
            "n": _safe_int(r["n"]),
            "realized": _safe_float(r["realized"]),
            "half_width_bps": _safe_float(r["halfwidth_bps"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(OUT / "chainlink_comparator.json", points)


def build_walkforward():
    df = pd.read_csv(TABLES / "v1b_walkforward_buffer.csv")
    summary = pd.read_csv(TABLES / "v1b_walkforward_summary.csv")
    splits = []
    for _, r in df.iterrows():
        splits.append({
            "split": _safe_int(r["split"]),
            "cutoff": str(r["cutoff"]),
            "horizon_end": str(r["horizon_end"]),
            "target": _safe_float(r["target"]),
            "buffer_chosen": _safe_float(r["buffer_chosen"]),
            "realized": _safe_float(r["realized"]),
            "half_width_bps": _safe_float(r["mean_half_width_bps"]),
            "p_uc": _safe_float(r["p_uc"]),
            "p_ind": _safe_float(r["p_ind"]),
            "status": str(r["status"]),
        })
    summary_rows = []
    for _, r in summary.iterrows():
        summary_rows.append({
            "target": _safe_float(r["target"]),
            "n_splits": _safe_int(r["n_splits"]),
            "buffer_mean": _safe_float(r["buffer_mean"]),
            "buffer_std": _safe_float(r["buffer_std"]),
            "deployed_buffer": _safe_float(r["deployed_buffer"]),
            "realized_mean": _safe_float(r["realized_mean"]),
            "realized_std": _safe_float(r["realized_std"]),
            "n_pass": _safe_int(r["n_pass"]),
        })
    write_json(OUT / "walkforward.json", {"splits": splits, "summary": summary_rows})


def build_window_sensitivity():
    df = pd.read_csv(TABLES / "v1b_window_sensitivity.csv")
    points = [
        {
            "window": _safe_int(r["window"]),
            "target": _safe_float(r["target"]),
            "n": _safe_int(r["n"]),
            "realized": _safe_float(r["realized"]),
            "half_width_bps": _safe_float(r["mean_half_width_bps"]),
            "p_uc": _safe_float(r["p_uc"]),
            "p_ind": _safe_float(r["p_ind"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(OUT / "window_sensitivity.json", points)


def build_leave_one_out():
    df = pd.read_csv(TABLES / "v1b_leave_one_out.csv")
    rows = [
        {
            "held_out": str(r["held_out"]),
            "split": str(r["split"]),
            "target": _safe_float(r["target"]),
            "n": _safe_int(r["n"]),
            "realized": _safe_float(r["realized"]),
            "half_width_bps": _safe_float(r["mean_half_width_bps"]),
            "p_uc": _safe_float(r["p_uc"]),
            "p_ind": _safe_float(r["p_ind"]),
        }
        for _, r in df.iterrows()
    ]
    write_json(OUT / "leave_one_out.json", rows)


def build_per_target_oos():
    df = pd.read_csv(TABLES / "v1b_oos_validation_pertarget.csv")
    rows = [
        {
            "target": _safe_float(r["target"]),
            "regime": str(r["regime_pub"]),
            "n": _safe_int(r["n"]),
            "realized": _safe_float(r["realized"]),
            "half_width_bps": _safe_float(r["mean_half_width_bps"]),
            "buffer": _safe_float(r["buffer"]),
        }
        for _, r in df.iterrows()
    ]
    kup = pd.read_csv(TABLES / "v1b_oos_kupiec_pertarget.csv")
    kupiec = [
        {
            "target": _safe_float(r["target"]),
            "n": _safe_int(r["n"]),
            "realized": _safe_float(r["realized"]),
            "violations": _safe_int(r["violations"]),
            "p_uc": _safe_float(r["p_uc"]),
            "p_ind": _safe_float(r["p_ind"]),
        }
        for _, r in kup.iterrows()
    ]
    write_json(OUT / "per_target_oos.json", {"per_regime": rows, "kupiec": kupiec})


def build_per_symbol():
    df = pd.read_csv(TABLES / "v1b_per_symbol.csv")
    f1 = df[df["forecaster"] == "F1_emp_regime"]
    rows = []
    for _, r in f1.iterrows():
        rows.append({
            "symbol": str(r["symbol"]),
            "n": _safe_int(r["n"]),
            "cov95_realized": _safe_float(r["cov95_realized"]),
            "cov95_sharp_bps": _safe_float(r["cov95_sharp_bps"]),
            "mae_bps": _safe_float(r["mae_bps"]),
        })
    write_json(OUT / "per_symbol.json", rows)


def build_comparator_weekend_panel():
    """For the visceral 'this weekend, who was right?' panel: join Pyth historical
    data with our OOS panel so each row is (symbol, fri_ts, mon_open, fri_close,
    soothsayer_lower, soothsayer_upper, pyth_price, pyth_conf). Limited to the
    Pyth-eligible 2024+ slice."""
    pyth_path = RAW / "pyth_benchmark_oos.parquet"
    if not pyth_path.exists():
        print("  pyth_benchmark_oos.parquet missing; skipping comparator panel")
        return
    pyth = pd.read_parquet(pyth_path)
    pyth = pyth[~pyth["pyth_unavailable"]].copy()
    if pyth.empty:
        print("  no Pyth data available; skipping comparator panel")
        return

    # We need the served band — load the bounds parquet and extract the deployed
    # served band per (symbol, fri_ts). The Oracle's deployed BUFFER_BY_TARGET
    # at τ=0.95 is 0.020 → effective_target = 0.97; surface inversion finds
    # claimed_q ≈ 0.97. To avoid re-instantiating the Oracle, we approximate by
    # picking the bounds row at claimed=0.95 (close enough for a visualisation).
    bounds = pd.read_parquet(RAW / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds = bounds[(bounds["forecaster"] == "F1_emp_regime") & (bounds["claimed"] == 0.95)]
    bounds_idx = bounds.set_index(["symbol", "fri_ts"])

    rows = []
    pyth["fri_ts"] = pd.to_datetime(pyth["fri_ts"]).dt.date
    for _, r in pyth.sort_values("fri_ts").tail(60).iterrows():
        try:
            b = bounds_idx.loc[(r["symbol"], r["fri_ts"])]
        except KeyError:
            continue
        if isinstance(b, pd.DataFrame):
            b = b.iloc[0]
        rows.append({
            "symbol": str(r["symbol"]),
            "fri_ts": str(r["fri_ts"]),
            "fri_close": _safe_float(r["fri_close"]),
            "mon_open": _safe_float(r["mon_open"]),
            "soothsayer_lower": _safe_float(b["lower"]),
            "soothsayer_upper": _safe_float(b["upper"]),
            "pyth_price": _safe_float(r["pyth_price"]),
            "pyth_conf": _safe_float(r["pyth_conf"]),
            "regime": str(r["regime_pub"]),
        })
    write_json(OUT / "comparator_weekends.json", rows)


def build_summary_stats():
    """One JSON file with the headline stats for hero cards."""
    kup = pd.read_csv(TABLES / "v1b_oos_kupiec_pertarget.csv")
    summary_at = {}
    for _, r in kup.iterrows():
        t = float(r["target"])
        summary_at[f"{t:.2f}"] = {
            "n": _safe_int(r["n"]),
            "realized": _safe_float(r["realized"]),
            "violations": _safe_int(r["violations"]),
            "p_uc": _safe_float(r["p_uc"]),
            "p_ind": _safe_float(r["p_ind"]),
        }

    inter = pd.read_csv(TABLES / "v1b_diag_inter_anchor_tau.csv")
    inter["abs_dev"] = (inter["realized"] - inter["tau"]).abs()
    n_pass = int((inter["p_uc"] > 0.05).sum())

    win = pd.read_csv(TABLES / "v1b_window_sensitivity.csv")
    win_unique = win[["window"]].drop_duplicates()

    loo = pd.read_csv(TABLES / "v1b_leave_one_out.csv")
    loo_loo = loo[loo["split"] == "leave_one_out"]

    payload = {
        "headline": summary_at,
        "inter_anchor": {
            "n_targets": int(len(inter)),
            "n_kupiec_pass": n_pass,
            "max_abs_dev": _safe_float(inter["abs_dev"].max()),
            "deployment_range": "[0.52, 0.98]",
        },
        "window_sensitivity": {
            "n_windows_tested": int(len(win_unique)),
            "windows": [_safe_int(v) for v in sorted(win_unique["window"].unique().tolist())],
            "deployed": 156,
        },
        "leave_one_out": {
            "n_symbols": int(loo_loo["held_out"].nunique()),
            "n_pass": int(((loo_loo["p_uc"] > 0.05)).sum()),
            "n_total": int(len(loo_loo)),
        },
    }
    write_json(OUT / "summary.json", payload)


def main() -> None:
    print("Generating dashboard JSON files...")
    build_summary_stats()
    build_calibration_curve()
    build_pyth_comparator()
    build_chainlink_comparator()
    build_walkforward()
    build_window_sensitivity()
    build_leave_one_out()
    build_per_target_oos()
    build_per_symbol()
    build_comparator_weekend_panel()
    print(f"\nAll JSON files written to {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
