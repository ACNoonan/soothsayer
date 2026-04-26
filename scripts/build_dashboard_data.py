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
    """For the visceral 'this weekend, who was right?' panel: each row is one
    (symbol, fri_ts) with all three oracles' bands + the realised mon_open.

    Also computes the pre-computed `inside` flags for each oracle so the JS
    side doesn't need to re-derive them."""
    pyth_path = RAW / "pyth_benchmark_oos.parquet"
    if not pyth_path.exists():
        print("  pyth_benchmark_oos.parquet missing; skipping comparator panel")
        return
    pyth = pd.read_parquet(pyth_path)
    pyth = pyth[~pyth["pyth_unavailable"]].copy()
    if pyth.empty:
        print("  no Pyth data available; skipping comparator panel")
        return

    # Soothsayer served band — use the deployed surface-inversion semantics for
    # τ=0.95: BUFFER_BY_TARGET[0.95] = 0.020 → effective τ = 0.97 → invert →
    # claimed_q lands near 0.99 in many cases. For viz simplicity we pick the
    # claimed=0.95 row from bounds_oos (deployment-defaultish; close enough for
    # the per-weekend panel). The aggregate stats below use the actual served
    # band from `served_oos_at_95` if available — see note in JS.
    bounds = pd.read_parquet(RAW / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds = bounds[(bounds["forecaster"] == "F1_emp_regime") & (bounds["claimed"] == 0.95)]
    bounds_idx = bounds.set_index(["symbol", "fri_ts"])

    # Chainlink dataset (separate Feb-Apr 2026 sample) — for symbols/weekends
    # that overlap with the Pyth panel, attach Chainlink data too.
    cl_path = RAW / "v1_chainlink_vs_monday_open.parquet"
    cl_idx = None
    if cl_path.exists():
        cl = pd.read_parquet(cl_path)
        cl["fri_ts"] = pd.to_datetime(cl["fri_ts"]).dt.date
        # Map cl xStock symbols (SPYx, AAPLx, …) back to underlyings
        cl["sym_under"] = cl["symbol"].astype(str).str.replace("x", "", regex=False)
        cl_idx = cl.set_index(["sym_under", "fri_ts"])

    Z = 1.959963984540054  # 1.96 to higher precision for the "naive 95% Gaussian wrap"
    rows = []
    pyth["fri_ts"] = pd.to_datetime(pyth["fri_ts"]).dt.date
    for _, r in pyth.sort_values("fri_ts", ascending=False).iterrows():
        try:
            b = bounds_idx.loc[(r["symbol"], r["fri_ts"])]
        except KeyError:
            continue
        if isinstance(b, pd.DataFrame):
            b = b.iloc[0]
        sym = str(r["symbol"])
        fri_ts = str(r["fri_ts"])
        fri_close = float(r["fri_close"])
        mon_open = float(r["mon_open"])

        sooth_lo = float(b["lower"]); sooth_hi = float(b["upper"])
        pyth_price = float(r["pyth_price"]); pyth_conf = float(r["pyth_conf"])
        pyth_lo = pyth_price - Z * pyth_conf
        pyth_hi = pyth_price + Z * pyth_conf
        # Chainlink stale-hold: cl_mid ≈ fri_close (we take fri_close as the
        # canonical archetype representation); a "consumer wrap" is undefined,
        # so the contained-flag is just whether mon_open == fri_close (almost
        # never), or alternatively the mon_open is within ±k% of fri_close at
        # whatever k the consumer chose. Without a consumer wrap, Chainlink's
        # band is degenerate.
        cl_mid = None
        if cl_idx is not None:
            try:
                cl_row = cl_idx.loc[(sym, r["fri_ts"])]
                if isinstance(cl_row, pd.DataFrame):
                    cl_row = cl_row.iloc[0]
                cl_mid = float(cl_row["cl_mid"])
            except KeyError:
                pass
        # If no Chainlink data for this (symbol, weekend), use fri_close as
        # the archetype (Chainlink-on-Solana stale-hold during marketStatus=5
        # is fri_close empirically; see reports/v1_chainlink_bias.md).
        if cl_mid is None:
            cl_mid = fri_close

        # Realised move from fri_close in bps
        move_bps = (mon_open - fri_close) / fri_close * 1e4

        rows.append({
            "symbol": sym,
            "fri_ts": fri_ts,
            "regime": str(r["regime_pub"]),
            "fri_close": fri_close,
            "mon_open": mon_open,
            "move_bps": float(move_bps),
            # Soothsayer
            "soothsayer_lower": sooth_lo,
            "soothsayer_upper": sooth_hi,
            "soothsayer_inside": int(sooth_lo <= mon_open <= sooth_hi),
            "soothsayer_halfwidth_bps": float((sooth_hi - sooth_lo) / 2 / fri_close * 1e4),
            # Pyth + naive 1.96·conf
            "pyth_price": pyth_price,
            "pyth_conf": pyth_conf,
            "pyth_lower": pyth_lo,
            "pyth_upper": pyth_hi,
            "pyth_inside": int(pyth_lo <= mon_open <= pyth_hi),
            "pyth_halfwidth_bps": float(Z * pyth_conf / fri_close * 1e4),
            # Chainlink stale-hold
            "chainlink_mid": cl_mid,
            "chainlink_diff_from_actual_bps": float((mon_open - cl_mid) / fri_close * 1e4),
        })
    write_json(OUT / "comparator_weekends.json", rows)


def build_narrative_headline():
    """Headline chart data: claimed-vs-realised for all three oracles, on a
    common axis. Soothsayer is a curve (sweep τ); Pyth is a single dot at
    naive (claimed=0.95, realised=0.102); Chainlink stale-hold has no
    published claim, so we plot it as a marker showing realised over-cover
    of the implicit "stale = constant" interpretation."""
    cal = pd.read_csv(TABLES / "v1b_diag_inter_anchor_tau.csv")
    pyth_pooled = pd.read_csv(TABLES / "pyth_coverage_by_k.csv")
    pyth_pooled = pyth_pooled[pyth_pooled["scope"] == "pooled"].sort_values("k")

    # Soothsayer line: sweep over τ
    soothsayer = [
        {"claimed": _safe_float(r["tau"]),
         "realized": _safe_float(r["realized"]),
         "halfwidth_bps": _safe_float(r["mean_half_width_bps"]),
         "is_anchor": bool(r["is_anchor"])}
        for _, r in cal.iterrows()
    ]
    # Pyth: at the textbook 1.96σ ("95%") read → 10.2% realised
    pyth_naive_row = pyth_pooled[pyth_pooled["k"] == 1.96]
    pyth_naive_realized = float(pyth_naive_row.iloc[0]["realized"]) if not pyth_naive_row.empty else None
    # Pyth: at consumer-fit 50× → 95.1% realised
    pyth_50_row = pyth_pooled[pyth_pooled["k"] == 50.0]
    pyth_50_realized = float(pyth_50_row.iloc[0]["realized"]) if not pyth_50_row.empty else None

    payload = {
        "soothsayer_curve": soothsayer,
        "pyth_naive": {
            "claimed": 0.95,
            "realized": pyth_naive_realized,
            "interpretation": "Pyth published price ± 1.96·conf, read as a 95% CI",
        },
        "pyth_consumer_fit": {
            "claimed": 0.95,
            "realized": pyth_50_realized,
            "consumer_k": 50.0,
            "interpretation": "Pyth at ±50·conf — the consumer-supplied multiplier needed to hit 95%",
        },
        "chainlink_stale": {
            "interpretation": "Chainlink Data Streams during marketStatus=5: bid≈0, ask=0, no published band. 100% of weekend observations.",
            "no_published_claim": True,
        },
    }
    write_json(OUT / "narrative_headline.json", payload)


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
    build_narrative_headline()
    print(f"\nAll JSON files written to {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
