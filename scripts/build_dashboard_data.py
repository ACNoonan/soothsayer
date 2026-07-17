"""
Generate JSON data files for the Soothsayer dashboard at landing/dashboard.html
(and the inline charts on landing/index.html / dashboard-narrative.html). Reads
from `reports/tables/*.csv` and `data/processed/*.parquet`; writes to
`landing/data/*.json`.

M6 migration (2026-07): deployed forecaster is M6 LWC (sigma-hat EWMA HL=8),
split 2023-01-01, OOS = 1,730 rows x 173 weekends x 10 tickers. Headline /
per-target / per-symbol / leave-one-out / walk-forward panels are driven by the
`m6_*` robustness tables. See NOTE comments for panels that have no clean M6
equivalent and are still v1b/M5-sourced (inter-anchor fine grid, window
sensitivity, comparator weekends) or carry a data gap (per-symbol MAE).

Run after any methodology change that affects published numbers.
No network: local reports/tables + data/processed parquet only.
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

# Deployed forecaster key inside the m6_* tables.
M6 = "lwc"


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


def _pooled_lwc() -> pd.DataFrame:
    """The M6 pooled OOS anchors (4 targets) for the deployed LWC forecaster."""
    df = pd.read_csv(TABLES / "m6_pooled_oos.csv")
    df = df[df["forecaster"] == M6].sort_values("tau").reset_index(drop=True)
    return df


def build_calibration_curve():
    """M6 calibration curve.

    NOTE: the deployed LWC artefact is target-keyed (targets [0.68,0.85,0.95,
    0.99]); there is no M6 fine-grid (50-level) claimed-vs-realised sweep table,
    and one cannot be produced from the artefact without re-running M6
    calibration at each tau. We therefore publish the 4 real anchor points from
    m6_pooled_oos (all is_anchor=true) rather than fabricate an interpolated
    curve. GAP: inter-anchor fine grid not migrated.
    """
    df = _pooled_lwc()
    points = []
    for _, r in df.iterrows():
        n = _safe_int(r["n"])
        realized = _safe_float(r["realised"])
        points.append({
            "tau": _safe_float(r["tau"]),
            "n": n,
            "realized": realized,
            "half_width_bps": _safe_float(r["half_width_bps"]),
            "p_uc": _safe_float(r["kupiec_p"]),
            "p_ind": _safe_float(r["christ_p"]),
            "is_anchor": True,
        })
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
    """M6 walk-forward / split stability from m6_lwc_robustness_split_sensitivity.

    Expanding-window splits at 2021/2022/2023/2024-01-01 (4 splits). M6 LWC has
    no additive `buffer` (the c_bump multiplier replaces it), so buffer_* fields
    are null. GAP vs old v1b panel: v1b reported a 6-split buffer sweep; the
    dashboard copy that references "buffer mean / 6 splits" is HTML-owned and
    now stale relative to this content.
    """
    df = pd.read_csv(TABLES / "m6_lwc_robustness_split_sensitivity.csv")
    df = df[df["forecaster"] == M6].copy()
    split_order = {d: i for i, d in enumerate(sorted(df["split_date"].unique()))}

    splits = []
    for _, r in df.sort_values(["tau", "split_date"]).iterrows():
        p_uc = _safe_float(r["kupiec_p"])
        splits.append({
            "split": int(split_order[r["split_date"]]),
            "cutoff": str(r["split_date"]),
            "horizon_end": None,
            "target": _safe_float(r["tau"]),
            "buffer_chosen": None,
            "realized": _safe_float(r["realised"]),
            "half_width_bps": _safe_float(r["half_width_bps"]),
            "n": _safe_int(r["n_oos"]),
            "n_weekends": _safe_int(r["n_oos_weekends"]),
            "p_uc": p_uc,
            "p_ind": _safe_float(r["christ_p"]),
            "status": "pass" if (p_uc is not None and p_uc > 0.05) else "fail",
        })

    deployed_c = {
        float(r["tau"]): _safe_float(r["c_bump"]) for _, r in _pooled_lwc().iterrows()
    }
    summary_rows = []
    for tau, g in df.groupby("tau"):
        n_pass = int((g["kupiec_p"] > 0.05).sum())
        summary_rows.append({
            "target": float(tau),
            "n_splits": int(len(g)),
            "buffer_mean": None,
            "buffer_std": None,
            "deployed_buffer": None,
            "deployed_c_bump": deployed_c.get(float(tau)),
            "realized_mean": _safe_float(g["realised"].mean()),
            "realized_std": _safe_float(g["realised"].std(ddof=1)),
            "n_pass": n_pass,
        })
    summary_rows.sort(key=lambda x: x["target"])
    write_json(OUT / "walkforward.json", {"splits": splits, "summary": summary_rows})


def build_window_sensitivity():
    """NOTE: UNMIGRATED. M6 LWC uses a sigma-hat EWMA (half-life 8), not a fixed
    rolling lookback window; there is no M6 window-length sweep. This remains the
    v1b (M5-era) 52->312-week sensitivity so the dashboard's window panel keeps
    rendering. Regenerated verbatim from the v1b source table."""
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
    """M6 leave-one-symbol-out (LOSO) from m6_lwc_robustness_loso.

    Each row is (held-out symbol, tau). GAP: the LOSO table carries Kupiec only,
    no Christoffersen, so p_ind is null. A `loso_95` summary block carries the
    headline held-out mean/sd at tau=0.95.
    """
    df = pd.read_csv(TABLES / "m6_lwc_robustness_loso.csv")
    df = df[df["forecaster"] == M6].copy()
    rows = [
        {
            "held_out": str(r["held_out_symbol"]),
            "split": "leave_one_out",
            "target": _safe_float(r["tau"]),
            "n": _safe_int(r["n_held_oos"]),
            "realized": _safe_float(r["realised"]),
            "half_width_bps": _safe_float(r["half_width_bps"]),
            "p_uc": _safe_float(r["kupiec_p"]),
            "p_ind": None,
        }
        for _, r in df.iterrows()
    ]
    at95 = df[np.isclose(df["tau"], 0.95)]
    summary = {
        "loso_95": {
            "n_symbols": int(at95["held_out_symbol"].nunique()),
            "mean_realized": _safe_float(at95["realised"].mean()),
            "std_realized": _safe_float(at95["realised"].std(ddof=1)),
            "n_kupiec_pass": int((at95["kupiec_p"] > 0.05).sum()),
        }
    }
    write_json(OUT / "leave_one_out.json", {"rows": rows, "summary": summary})


def build_per_target_oos():
    """M6 per-target Kupiec/Christoffersen from m6_pooled_oos (deployed LWC).

    NOTE: m6_pooled_oos is pooled-only; there is no M6 high_vol/long_weekend/
    normal regime stratification, so `per_regime` carries the 4 pooled anchors
    only (regime='pooled'). GAP: regime breakdown not migrated. This file is not
    consumed by the dashboard HTML; retained for completeness.
    """
    df = _pooled_lwc()
    per_regime = []
    kupiec = []
    for _, r in df.iterrows():
        n = _safe_int(r["n"])
        realized = _safe_float(r["realised"])
        per_regime.append({
            "target": _safe_float(r["tau"]),
            "regime": "pooled",
            "n": n,
            "realized": realized,
            "half_width_bps": _safe_float(r["half_width_bps"]),
            "buffer": None,
        })
        kupiec.append({
            "target": _safe_float(r["tau"]),
            "n": n,
            "realized": realized,
            "violations": _safe_int(round(n * (1.0 - realized))),
            "p_uc": _safe_float(r["kupiec_p"]),
            "p_ind": _safe_float(r["christ_p"]),
        })
    write_json(OUT / "per_target_oos.json", {"per_regime": per_regime, "kupiec": kupiec})


def build_per_symbol():
    """M6 per-symbol coverage at tau=0.95.

    Coverage/Kupiec from m6_lwc_robustness_per_symbol; sharp half-width from the
    lwc @0.95 rows of m6_per_symbol_master_grid. GAP: no per-symbol MAE in any
    M6 table, so mae_bps is null (renders as em-dash).
    """
    cov = pd.read_csv(TABLES / "m6_lwc_robustness_per_symbol.csv")
    grid = pd.read_csv(TABLES / "m6_per_symbol_master_grid.csv")
    hw = grid[(grid["method"] == M6) & (np.isclose(grid["tau"], 0.95))]
    hw = hw.set_index("symbol")["half_width_bps"].to_dict()

    rows = []
    for _, r in cov.iterrows():
        sym = str(r["symbol"])
        rows.append({
            "symbol": sym,
            "n": _safe_int(r["n_oos"]),
            "cov95_realized": _safe_float(1.0 - r["viol_rate_0.95"]),
            "cov95_sharp_bps": _safe_float(hw.get(sym)),
            "mae_bps": None,
            "kupiec_p_95": _safe_float(r["kupiec_p_0.95"]),
        })
    write_json(OUT / "per_symbol.json", rows)


def build_comparator_weekend_panel():
    """For the visceral 'this weekend, who was right?' panel: each row is one
    (symbol, fri_ts) with all three oracles' bands + the realised mon_open.

    NOTE: UNMIGRATED to M6 served bands. Soothsayer's band here is the v1b_bounds
    (F1_emp_regime, claimed=0.95) surface; there is no per-weekend M6-served
    bounds parquet with this schema. Retained as v1b/M5 evidence so the panel
    keeps rendering. Pyth/Chainlink comparators are venue data, not model-
    dependent."""
    pyth_path = RAW / "pyth_benchmark_oos.parquet"
    if not pyth_path.exists():
        print("  pyth_benchmark_oos.parquet missing; skipping comparator panel")
        return
    pyth = pd.read_parquet(pyth_path)
    pyth = pyth[~pyth["pyth_unavailable"]].copy()
    if pyth.empty:
        print("  no Pyth data available; skipping comparator panel")
        return

    bounds = pd.read_parquet(RAW / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds = bounds[(bounds["forecaster"] == "F1_emp_regime") & (bounds["claimed"] == 0.95)]
    bounds_idx = bounds.set_index(["symbol", "fri_ts"])

    cl_path = RAW / "v1_chainlink_vs_monday_open.parquet"
    cl_idx = None
    if cl_path.exists():
        cl = pd.read_parquet(cl_path)
        cl["fri_ts"] = pd.to_datetime(cl["fri_ts"]).dt.date
        cl["sym_under"] = cl["symbol"].astype(str).str.replace("x", "", regex=False)
        cl_idx = cl.set_index(["sym_under", "fri_ts"])

    Z = 1.959963984540054
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
        cl_mid = None
        if cl_idx is not None:
            try:
                cl_row = cl_idx.loc[(sym, r["fri_ts"])]
                if isinstance(cl_row, pd.DataFrame):
                    cl_row = cl_row.iloc[0]
                cl_mid = float(cl_row["cl_mid"])
            except KeyError:
                pass
        if cl_mid is None:
            cl_mid = fri_close

        move_bps = (mon_open - fri_close) / fri_close * 1e4

        rows.append({
            "symbol": sym,
            "fri_ts": fri_ts,
            "regime": str(r["regime_pub"]),
            "fri_close": fri_close,
            "mon_open": mon_open,
            "move_bps": float(move_bps),
            "soothsayer_lower": sooth_lo,
            "soothsayer_upper": sooth_hi,
            "soothsayer_inside": int(sooth_lo <= mon_open <= sooth_hi),
            "soothsayer_halfwidth_bps": float((sooth_hi - sooth_lo) / 2 / fri_close * 1e4),
            "pyth_price": pyth_price,
            "pyth_conf": pyth_conf,
            "pyth_lower": pyth_lo,
            "pyth_upper": pyth_hi,
            "pyth_inside": int(pyth_lo <= mon_open <= pyth_hi),
            "pyth_halfwidth_bps": float(Z * pyth_conf / fri_close * 1e4),
            "chainlink_mid": cl_mid,
            "chainlink_diff_from_actual_bps": float((mon_open - cl_mid) / fri_close * 1e4),
        })
    write_json(OUT / "comparator_weekends.json", rows)


def build_narrative_headline():
    """Headline chart: claimed-vs-realised for all three oracles.

    Soothsayer curve = the M6 LWC anchors (4 targets; see build_calibration_curve
    NOTE on the fine-grid gap). Pyth from pyth_coverage_by_k; Chainlink stale-hold
    narrative is unchanged (venue behaviour, not model-dependent).
    """
    cal = _pooled_lwc()
    pyth_pooled = pd.read_csv(TABLES / "pyth_coverage_by_k.csv")
    pyth_pooled = pyth_pooled[pyth_pooled["scope"] == "pooled"].sort_values("k")

    soothsayer = [
        {"claimed": _safe_float(r["tau"]),
         "realized": _safe_float(r["realised"]),
         "halfwidth_bps": _safe_float(r["half_width_bps"]),
         "is_anchor": True}
        for _, r in cal.iterrows()
    ]
    pyth_naive_row = pyth_pooled[pyth_pooled["k"] == 1.96]
    pyth_naive_realized = float(pyth_naive_row.iloc[0]["realized"]) if not pyth_naive_row.empty else None
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
    """Headline stats for the hero cards.

    headline + leave_one_out are M6 (deployed LWC). inter_anchor and
    window_sensitivity subsections are UNMIGRATED (still v1b/M5): there is no M6
    fine-grid tau sweep nor an M6 window-length sweep, and the dashboard copy for
    those two panels ("50-level τ sweep", "156 window") is HTML-owned and pinned
    to these v1b values.
    """
    # --- M6 headline (deployed LWC) ---
    pooled = _pooled_lwc()
    summary_at = {}
    for _, r in pooled.iterrows():
        t = float(r["tau"])
        n = _safe_int(r["n"])
        realized = _safe_float(r["realised"])
        summary_at[f"{t:.2f}"] = {
            "n": n,
            "realized": realized,
            "violations": _safe_int(round(n * (1.0 - realized))),
            "p_uc": _safe_float(r["kupiec_p"]),
            "p_ind": _safe_float(r["christ_p"]),
        }

    # --- UNMIGRATED: v1b inter-anchor fine grid ---
    inter = pd.read_csv(TABLES / "v1b_diag_inter_anchor_tau.csv")
    inter["abs_dev"] = (inter["realized"] - inter["tau"]).abs()
    n_pass = int((inter["p_uc"] > 0.05).sum())

    # --- UNMIGRATED: v1b window sensitivity ---
    win = pd.read_csv(TABLES / "v1b_window_sensitivity.csv")
    win_unique = win[["window"]].drop_duplicates()

    # --- M6 leave-one-symbol-out ---
    loso = pd.read_csv(TABLES / "m6_lwc_robustness_loso.csv")
    loso = loso[loso["forecaster"] == M6]
    loso95 = loso[np.isclose(loso["tau"], 0.95)]

    payload = {
        "headline": summary_at,
        "inter_anchor": {
            "n_targets": int(len(inter)),
            "n_kupiec_pass": n_pass,
            "max_abs_dev": _safe_float(inter["abs_dev"].max()),
            "deployment_range": "[0.52, 0.98]",
            "_source": "v1b (unmigrated: no M6 fine-grid tau sweep)",
        },
        "window_sensitivity": {
            "n_windows_tested": int(len(win_unique)),
            "windows": [_safe_int(v) for v in sorted(win_unique["window"].unique().tolist())],
            "deployed": 156,
            "_source": "v1b (unmigrated: M6 LWC uses sigma-hat EWMA HL=8, no lookback sweep)",
        },
        "leave_one_out": {
            "n_symbols": int(loso["held_out_symbol"].nunique()),
            "n_pass": int((loso["kupiec_p"] > 0.05).sum()),
            "n_total": int(len(loso)),
            "loso_95_mean": _safe_float(loso95["realised"].mean()),
            "loso_95_std": _safe_float(loso95["realised"].std(ddof=1)),
        },
    }
    write_json(OUT / "summary.json", payload)


def main() -> None:
    print("Generating dashboard JSON files (M6 LWC)...")
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
