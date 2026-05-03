"""
Serving-layer ablation under the deployed BUFFER_BY_TARGET schedule.

Re-runs the §7.4 (forecaster policy × buffer) C-matrix from v1b_ablation.md
under the deployed Oracle configuration, replacing the legacy scalar 0.025
buffer with the per-target schedule. The five cells:

  C0  F1 everywhere,                   buffer = 0
  C1  F0 everywhere,                   buffer = 0
  C2  hybrid (deployed REGIME_FORECASTER), buffer = 0
  C3  F1 everywhere,                   buffer = BUFFER_BY_TARGET[τ]
  C4  hybrid,                          buffer = BUFFER_BY_TARGET[τ]   (deployed Oracle)

Reports per-cell coverage + half-width + Kupiec + Christoffersen at the §6
headline target τ = 0.95, plus pairwise bootstrap 95% CIs on the four
comparisons (C0→C2, C0→C3, C2→C4, C0→C4).

Outputs:
  reports/tables/v1b_serving_ablation.csv         per-cell metrics
  reports/tables/v1b_serving_ablation_bootstrap.csv  pairwise deltas with CIs
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle, buffer_for_target


SPLIT_DATE = date(2023, 1, 1)
HEADLINE_TAU = 0.95
N_BOOTSTRAP = 1000
RNG_SEED = 20260426

CELLS = [
    # (name, forecaster_override, buffer_strategy)
    ("C0", "F1_emp_regime", "zero"),
    ("C1", "F0_stale", "zero"),
    ("C2", None, "zero"),                  # None → use REGIME_FORECASTER
    ("C3", "F1_emp_regime", "deployed"),
    ("C4", None, "deployed"),              # = the deployed Oracle
    # F0_VIX challenger rungs (paper 1 §7.4): forward-curve-implied Gaussian
    # baseline through the same surface inversion + buffer as the deployed
    # forecasters. B1 mirrors C0 (zero buffer), B2 mirrors C3 (deployed buffer).
    # Equity-only — bounds carry only the 8 equities, so the cell sample is
    # smaller than C0–C4 by the GLD/TLT row count.
    ("B1", "F0_VIX", "zero"),
    ("B2", "F0_VIX", "deployed"),
]


F0_VIX_EQUITY_UNIVERSE = frozenset({"SPY", "QQQ", "AAPL", "GOOGL", "NVDA", "TSLA", "MSTR", "HOOD"})


def serve_cell(oracle: Oracle, panel_oos: pd.DataFrame, cell_name: str,
               forecaster: str | None, buffer_strategy: str, target: float) -> pd.DataFrame:
    """Serve every (symbol, fri_ts) in OOS at `target` under this cell's config."""
    rows = []
    for _, w in panel_oos.iterrows():
        # F0_VIX is equity-only — GLD/TLT bounds were not built for this
        # forecaster (their proper vol indices are GVZ/MOVE; see §7.5).
        if forecaster == "F0_VIX" and w["symbol"] not in F0_VIX_EQUITY_UNIVERSE:
            continue
        if buffer_strategy == "zero":
            buffer_arg: float | None = 0.0
        else:
            buffer_arg = None  # use deployed schedule
        try:
            pp = oracle.fair_value(
                w["symbol"], w["fri_ts"],
                target_coverage=target,
                forecaster_override=forecaster,
                buffer_override=buffer_arg,
            )
        except (ValueError, KeyError):
            continue
        inside = (w["mon_open"] >= pp.lower) and (w["mon_open"] <= pp.upper)
        rows.append({
            "cell": cell_name,
            "symbol": w["symbol"],
            "fri_ts": w["fri_ts"],
            "regime_pub": w["regime_pub"],
            "fri_close": float(w["fri_close"]),
            "mon_open": float(w["mon_open"]),
            "lower": float(pp.lower),
            "upper": float(pp.upper),
            "half_width_bps": float(pp.half_width_bps),
            "buffer_applied": float(pp.calibration_buffer_applied),
            "inside": int(bool(inside)),
        })
    return pd.DataFrame(rows)


def cell_summary(served: pd.DataFrame, target: float) -> dict:
    """Pooled coverage + half-width + Kupiec + Christoffersen for one cell."""
    n = len(served)
    realised = float(served["inside"].mean())
    half = float(served["half_width_bps"].mean())
    v = (~served["inside"].astype(bool)).astype(int).values
    lr_uc, p_uc = met._lr_kupiec(v, target)
    # Christoffersen pooled across symbols (sum of independent χ²s)
    lr_ind_total = 0.0
    n_groups = 0
    for sym, g in served.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
        v_g = (~g["inside"].astype(bool)).astype(int).values
        lr_ind, _ = met._lr_christoffersen_independence(v_g)
        if not np.isnan(lr_ind):
            lr_ind_total += lr_ind
            n_groups += 1
    p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
    return {
        "n": n,
        "realised": realised,
        "half_width_bps": half,
        "buffer_applied": float(served["buffer_applied"].iloc[0]) if n > 0 else float("nan"),
        "lr_uc": float(lr_uc),
        "p_uc": float(p_uc),
        "lr_ind": float(lr_ind_total),
        "p_ind": p_ind,
    }


def block_bootstrap_delta(serv_a: pd.DataFrame, serv_b: pd.DataFrame,
                           rng: np.random.Generator, n_resamples: int = N_BOOTSTRAP):
    """Per-weekend block bootstrap on Δcoverage and Δsharpness% (b−a).

    Restricts the comparison to the (fri_ts, symbol) intersection so cells with
    different sample compositions (e.g., F0_VIX equity-only vs full hybrid
    panel) are compared on the same rows. Within each bootstrap iteration we
    resample weekends, then take all symbols common to both cells at each
    sampled weekend.
    """
    keys_a = set(zip(serv_a["fri_ts"], serv_a["symbol"]))
    keys_b = set(zip(serv_b["fri_ts"], serv_b["symbol"]))
    common_keys = keys_a & keys_b
    if not common_keys:
        return np.array([]), np.array([])
    a_filt = serv_a[serv_a.set_index(["fri_ts", "symbol"]).index.isin(common_keys)]
    b_filt = serv_b[serv_b.set_index(["fri_ts", "symbol"]).index.isin(common_keys)]
    weekends = sorted({w for w, _ in common_keys})
    a_by_w = a_filt.set_index(["fri_ts", "symbol"])
    b_by_w = b_filt.set_index(["fri_ts", "symbol"])
    deltas_cov = []
    deltas_sharp = []
    for _ in range(n_resamples):
        idx = rng.choice(len(weekends), size=len(weekends), replace=True)
        sample_weekends = [weekends[i] for i in idx]
        a_inside = []
        b_inside = []
        a_w = []
        b_w = []
        for w in sample_weekends:
            a_rows = a_by_w.loc[[w]] if w in a_by_w.index.get_level_values(0) else None
            b_rows = b_by_w.loc[[w]] if w in b_by_w.index.get_level_values(0) else None
            if a_rows is None or b_rows is None:
                continue
            a_inside.extend(a_rows["inside"].tolist())
            b_inside.extend(b_rows["inside"].tolist())
            a_w.extend(a_rows["half_width_bps"].tolist())
            b_w.extend(b_rows["half_width_bps"].tolist())
        if not a_inside:
            continue
        a_cov = np.mean(a_inside); b_cov = np.mean(b_inside)
        a_hw = np.mean(a_w); b_hw = np.mean(b_w)
        deltas_cov.append((b_cov - a_cov) * 100.0)  # pp
        deltas_sharp.append((b_hw - a_hw) / a_hw * 100.0)  # %
    return np.array(deltas_cov), np.array(deltas_sharp)


def main() -> None:
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds["mon_ts"] = pd.to_datetime(bounds["mon_ts"]).dt.date

    panel = bounds[["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]].drop_duplicates(
        ["symbol", "fri_ts"]
    ).reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_oos = bounds[bounds["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE].reset_index(drop=True)

    surface = cal.compute_calibration_surface(bounds_train)
    surface_pooled = cal.pooled_surface(bounds_train)
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)

    deployed_buffer_at_tau = buffer_for_target(HEADLINE_TAU)
    print(f"OOS panel: {len(panel_oos):,} rows × {panel_oos['fri_ts'].nunique()} weekends")
    print(f"Headline τ = {HEADLINE_TAU}; deployed buffer at this τ = {deployed_buffer_at_tau:.4f}")
    print()

    cells_data: dict[str, pd.DataFrame] = {}
    summary_rows = []
    for name, fc, strat in CELLS:
        served = serve_cell(oracle, panel_oos, name, fc, strat, HEADLINE_TAU)
        cells_data[name] = served
        s = cell_summary(served, HEADLINE_TAU)
        summary_rows.append({
            "cell": name,
            "policy": "F1 everywhere" if fc == "F1_emp_regime" else
                      "F0 everywhere" if fc == "F0_stale" else
                      "F0_VIX everywhere" if fc == "F0_VIX" else "hybrid",
            "buffer_strategy": strat,
            "buffer_applied": s["buffer_applied"],
            **{k: v for k, v in s.items() if k != "buffer_applied"},
        })
        print(f"{name}: realised={s['realised']:.4f} half={s['half_width_bps']:.1f}bps "
              f"buffer={s['buffer_applied']:.4f} p_uc={s['p_uc']:.3f} p_ind={s['p_ind']:.3f}")

    summary = pd.DataFrame(summary_rows)
    print()
    print("Cell summary table:")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # Pairwise bootstrap on the four reported comparisons
    pair_specs = [
        ("C0", "C2", "hybrid effect, no buffer"),
        ("C0", "C3", "buffer effect, no hybrid"),
        ("C2", "C4", "buffer effect, with hybrid"),
        ("C0", "C4", "total serving layer"),
        # F0_VIX challenger comparisons (paper 1 §7.4)
        ("B1", "B2", "F0_VIX buffer effect"),
        ("B2", "C4", "F0_VIX buffered vs deployed Oracle"),
        ("B2", "C3", "F0_VIX buffered vs F1-everywhere buffered"),
    ]
    rng = np.random.default_rng(RNG_SEED)
    bootstrap_rows = []
    for a, b, label in pair_specs:
        d_cov, d_sharp = block_bootstrap_delta(cells_data[a], cells_data[b], rng)
        bootstrap_rows.append({
            "comparison": f"{a} → {b}",
            "label": label,
            "delta_cov_pp_mean": float(d_cov.mean()),
            "delta_cov_pp_lo": float(np.percentile(d_cov, 2.5)),
            "delta_cov_pp_hi": float(np.percentile(d_cov, 97.5)),
            "delta_sharp_pct_mean": float(d_sharp.mean()),
            "delta_sharp_pct_lo": float(np.percentile(d_sharp, 2.5)),
            "delta_sharp_pct_hi": float(np.percentile(d_sharp, 97.5)),
        })
    bootstrap = pd.DataFrame(bootstrap_rows)
    print()
    print("Pairwise bootstrap (b − a, 1000 resamples by weekend):")
    print(bootstrap.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    out_dir = REPORTS / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_dir / "v1b_serving_ablation.csv", index=False)
    bootstrap.to_csv(out_dir / "v1b_serving_ablation_bootstrap.csv", index=False)
    print()
    print(f"Wrote {out_dir / 'v1b_serving_ablation.csv'}")
    print(f"Wrote {out_dir / 'v1b_serving_ablation_bootstrap.csv'}")


if __name__ == "__main__":
    main()
