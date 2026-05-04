"""
Phase 5 — σ̂ fast-reacting variant prototype.

Targets the temporal-clustering issue surfaced in Phase 2 §11 item 2:
LWC has 2021 + 2022 split-date Christoffersen rejections at τ=0.95 because
σ̂_sym(t) is itself slowly-varying — a calm streak under-estimates σ̂ going
into a vol shock. This script prototypes shorter-memory EWMA σ̂ variants
and re-runs the Phase 2 diagnostics against them, all on identical rows.

Variants
--------
  baseline_k26        K=26 trailing-window (currently deployed M6).
  ewma_hl6            EWMA σ̂ with weekend half-life = 6.
  ewma_hl8            EWMA σ̂ with weekend half-life = 8.
  ewma_hl12           EWMA σ̂ with weekend half-life = 12.
  blend_a50_hl8       0.5 · σ̂_K26 + 0.5 · σ̂_EWMA_HL8 — exploratory point.

All variants share the same warm-up rule (≥ 8 past obs) so they are
diagnosed on identical rows; n_eval is identical across variants.

Diagnostics (per variant)
-------------------------
  1. Walk-forward δ-sweep mirroring `run_lwc_delta_sweep.py`. Output:
       reports/tables/sigma_ewma_<variant>_delta_sweep.csv
     The selection criterion (smallest δ with cov_mean ≥ τ at every split)
     is reported so the deployer can see what δ the variant lands on.

  2. Pooled OOS Kupiec + Christoffersen + half-width at τ ∈ DEFAULT_TAUS,
     fit at split=2023-01-01 with the chosen δ schedule. Same shape as
     `reports/m6_pooled_oos.csv`.

  3. Split-date Christoffersen at the 4 split anchors × 4 τ — Phase 2
     diagnostic the σ̂ variant is targeting. Same per-symbol-grouped pooled
     LR test as `run_v1b_split_sensitivity.py`.

  4. Per-symbol Berkowitz LR + Kupiec at 4 τ on the 2023+ OOS slice. Same
     shape as `reports/tables/m6_lwc_robustness_per_symbol.csv`.

Outputs
-------
  reports/tables/sigma_ewma_summary.csv
      One row per (variant × τ): pooled realised, half-width, Kupiec p,
      Christoffersen p, n.

  reports/tables/sigma_ewma_split_sensitivity.csv
      One row per (variant × split × τ).

  reports/tables/sigma_ewma_per_symbol.csv
      One row per (variant × symbol): n_oos, Kupiec p at 4 τ, Berkowitz LR/p.

  reports/tables/sigma_ewma_<variant>_delta_sweep.csv
      Walk-forward δ-sweep per variant.

Run
---
  uv run python -u scripts/run_sigma_ewma_variants.py
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    add_sigma_hat_sym,
    add_sigma_hat_sym_ewma,
    add_sigma_hat_sym_blend,
    compute_score_lwc,
    fit_c_bump_schedule,
    serve_bands_lwc,
    train_quantile_table,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
SPLIT_ANCHORS = (date(2021, 1, 1), date(2022, 1, 1),
                 date(2023, 1, 1), date(2024, 1, 1))
DELTA_GRID = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07)
WALKFORWARD_FRACTIONS = (0.20, 0.30, 0.40, 0.50, 0.60, 0.70)

PIT_DENSE_GRID = (
    0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.68, 0.70, 0.80, 0.85,
    0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999,
)

OUT_TABLES = REPORTS / "tables"


# ----------------------------------------------------------------------------
# Variant registry
# ----------------------------------------------------------------------------


def _add_baseline(panel: pd.DataFrame) -> pd.DataFrame:
    return add_sigma_hat_sym(panel)


def _add_ewma_hl(hl: int):
    def _add(panel: pd.DataFrame) -> pd.DataFrame:
        return add_sigma_hat_sym_ewma(panel, half_life=hl)
    return _add


def _add_blend_50_8(panel: pd.DataFrame) -> pd.DataFrame:
    return add_sigma_hat_sym_blend(panel, alpha=0.5, half_life=8)


VARIANTS: list[dict] = [
    {
        "name": "baseline_k26",
        "label": "K=26 (M6 baseline)",
        "add_fn": _add_baseline,
        "scale_col": "sigma_hat_sym_pre_fri",
    },
    {
        "name": "ewma_hl6",
        "label": "EWMA HL=6",
        "add_fn": _add_ewma_hl(6),
        "scale_col": "sigma_hat_sym_ewma_pre_fri_hl6",
    },
    {
        "name": "ewma_hl8",
        "label": "EWMA HL=8",
        "add_fn": _add_ewma_hl(8),
        "scale_col": "sigma_hat_sym_ewma_pre_fri_hl8",
    },
    {
        "name": "ewma_hl12",
        "label": "EWMA HL=12",
        "add_fn": _add_ewma_hl(12),
        "scale_col": "sigma_hat_sym_ewma_pre_fri_hl12",
    },
    {
        "name": "blend_a50_hl8",
        "label": "Blend 0.5·K26 + 0.5·EWMA_HL8",
        "add_fn": _add_blend_50_8,
        "scale_col": "sigma_hat_sym_blend_pre_fri_a50_hl8",
    },
]


# ----------------------------------------------------------------------------
# Walk-forward δ-sweep — generalised over scale_col
# ----------------------------------------------------------------------------


def _train_quantile_per_regime(
    panel_train: pd.DataFrame,
    score_col: str,
) -> pd.DataFrame:
    rows = []
    for regime, g in panel_train.groupby("regime_pub"):
        scores = g[score_col].dropna().to_numpy(float)
        n = scores.size
        if n == 0:
            continue
        sorted_scores = np.sort(scores)
        for tau in DEFAULT_TAUS:
            k = int(np.ceil(tau * (n + 1)))
            k = min(max(k, 1), n)
            rows.append(
                {"regime_pub": regime, "target": tau,
                 "b": float(sorted_scores[k - 1]), "n_train": n}
            )
    return pd.DataFrame(rows)


def _fit_c_for_target(
    panel_tune: pd.DataFrame,
    base_quantiles: pd.DataFrame,
    score_col: str,
    target: float,
    coverage_target: float,
) -> float:
    sub = base_quantiles[base_quantiles["target"] == target][["regime_pub", "b"]]
    merged = panel_tune.merge(sub, on="regime_pub", how="left").dropna(
        subset=[score_col, "b"]
    )
    scores = merged[score_col].to_numpy(float)
    b_arr = merged["b"].to_numpy(float)
    grid = np.arange(1.0, 5.0001, 0.001)
    for c in grid:
        if float(np.mean(scores <= b_arr * c)) >= coverage_target:
            return float(c)
    return float(grid[-1])


def walk_forward_lwc_variant(
    panel_train: pd.DataFrame,
    panel_oos: pd.DataFrame,
    delta: float,
    score_col: str,
    scale_col: str,
) -> pd.DataFrame:
    base = _train_quantile_per_regime(panel_train, score_col)
    weekends = sorted(panel_oos["fri_ts"].unique())
    rows = []
    for f in WALKFORWARD_FRACTIONS:
        n_tune = max(int(round(len(weekends) * f)), 8)
        tune_ws = set(weekends[:n_tune])
        test_ws = set(weekends[n_tune:])
        panel_tune = panel_oos[panel_oos["fri_ts"].isin(tune_ws)].copy()
        panel_test = panel_oos[panel_oos["fri_ts"].isin(test_ws)].copy()
        for tau in DEFAULT_TAUS:
            cov_target = min(tau + delta, 0.999)
            c = _fit_c_for_target(panel_tune, base, score_col, target=tau,
                                  coverage_target=cov_target)
            sub = base[base["target"] == tau][["regime_pub", "b"]]
            test = panel_test.merge(sub, on="regime_pub", how="left").dropna(
                subset=[score_col, "b"]
            )
            test["b_eff"] = test["b"] * c
            inside = (test[score_col] <= test["b_eff"]).astype(int)
            hw_bps = test["b_eff"] * test[scale_col] * 1e4
            rows.append({
                "split_fraction": f,
                "n_tune_weekends": n_tune,
                "n_test_weekends": len(test_ws),
                "target": tau,
                "delta": delta,
                "bump_c": c,
                "n_test": int(inside.size),
                "test_realised": float(inside.mean()) if len(inside) else float("nan"),
                "test_half_width_bps_mean": float(hw_bps.mean()) if len(test) else float("nan"),
            })
    return pd.DataFrame(rows)


def select_delta_schedule(sweep: pd.DataFrame) -> dict[float, float]:
    """Smallest δ on the grid such that mean walk-forward test_realised ≥ τ.

    Matches the criterion the deployed M6 baseline used (`build_lwc_artefact.py`
    docstring): "smallest δ such that pooled walk-forward realised coverage at
    every τ ≥ nominal." Under LWC every τ already has cov_mean ≥ τ at δ=0, so
    the baseline lands at all-zero. The same criterion is applied per Phase 5
    variant for an apples-to-apples comparison."""
    out: dict[float, float] = {}
    for tau in DEFAULT_TAUS:
        chosen = float(max(DELTA_GRID))
        for delta in sorted(set(sweep["delta"])):
            g = sweep[(sweep["target"] == tau) & (sweep["delta"] == delta)]
            if g.empty:
                continue
            cov_mean = float(g["test_realised"].mean())
            if cov_mean >= tau:
                chosen = float(delta)
                break
        out[float(tau)] = chosen
    return out


# ----------------------------------------------------------------------------
# Split-date Christoffersen + pooled OOS metrics
# ----------------------------------------------------------------------------


def _fit_split_lwc(
    panel: pd.DataFrame,
    split_d: date,
    score_col: str,
) -> tuple[dict[str, dict[float, float]], dict[float, float]]:
    work = panel.dropna(subset=[score_col]).copy()
    train = work[work["fri_ts"] < split_d]
    oos = work[work["fri_ts"] >= split_d]
    qt = train_quantile_table(train, cell_col="regime_pub",
                              taus=DEFAULT_TAUS, score_col=score_col)
    cb = fit_c_bump_schedule(oos, qt, cell_col="regime_pub",
                             taus=DEFAULT_TAUS, score_col=score_col)
    return qt, cb


def _coverage_row(panel_oos: pd.DataFrame,
                  bounds: dict[float, pd.DataFrame],
                  tau: float) -> dict:
    b = bounds[tau]
    inside = ((panel_oos["mon_open"] >= b["lower"]) &
              (panel_oos["mon_open"] <= b["upper"]))
    v = (~inside).astype(int).to_numpy()
    lr_uc, p_uc = met._lr_kupiec(v, tau)
    cc = met.conditional_coverage_from_bounds(
        panel_oos, {tau: b}, group_by="symbol"
    )
    cc0 = cc.iloc[0]
    hw_bps = float(((b["upper"] - b["lower"]) / 2 /
                    panel_oos["fri_close"] * 1e4).mean())
    return {
        "tau": float(tau),
        "n_oos": int(len(panel_oos)),
        "n_oos_weekends": int(panel_oos["fri_ts"].nunique()),
        "realised": float(inside.mean()),
        "half_width_bps": float(hw_bps),
        "kupiec_lr": float(lr_uc),
        "kupiec_p": float(p_uc),
        "christ_lr": float(cc0["lr_ind"]),
        "christ_p": float(cc0["p_ind"]),
    }


# ----------------------------------------------------------------------------
# Per-symbol Berkowitz (PIT-based, dense grid)
# ----------------------------------------------------------------------------


def _interp_table(table: dict[float, float], x: float) -> float:
    keys = sorted(table.keys())
    if x <= keys[0]:
        return float(table[keys[0]])
    if x >= keys[-1]:
        return float(table[keys[-1]])
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= x <= hi:
            frac = (x - lo) / (hi - lo)
            return float(table[lo] + frac * (table[hi] - table[lo]))
    return float(table[keys[-1]])


def build_lwc_pits(
    panel: pd.DataFrame,
    qt: dict[str, dict[float, float]],
    cb: dict[float, float],
    scale_col: str,
    cell_col: str = "regime_pub",
    dense_grid: tuple[float, ...] = PIT_DENSE_GRID,
) -> np.ndarray:
    grid_taus = np.array(sorted(dense_grid))
    point = (panel["fri_close"].astype(float)
             * (1.0 + panel["factor_ret"].astype(float))).to_numpy()
    fri_close = panel["fri_close"].astype(float).to_numpy()
    mon_open = panel["mon_open"].astype(float).to_numpy()
    cells = panel[cell_col].astype(str).to_numpy()
    sigma = panel[scale_col].to_numpy(float)

    pits = np.full(len(panel), np.nan)
    for i in range(len(panel)):
        q_row = qt.get(cells[i])
        if q_row is None:
            continue
        b_anchors = np.array(
            [_interp_table(q_row, tau) * _interp_table(cb, tau)
             for tau in grid_taus],
            dtype=float,
        )
        s = sigma[i]
        if not (np.isfinite(s) and s > 0):
            continue
        scale = fri_close[i] * s
        if not (np.isfinite(scale) and scale > 0):
            continue
        half_i = b_anchors * scale
        if not np.all(np.isfinite(half_i)):
            continue
        r = mon_open[i] - point[i]
        abs_r = abs(r)
        anchor_b = np.concatenate(([0.0], half_i))
        anchor_tau = np.concatenate(([0.0], grid_taus))
        if abs_r >= anchor_b[-1]:
            tau_hat = anchor_tau[-1]
        else:
            tau_hat = float(np.interp(abs_r, anchor_b, anchor_tau))
        pits[i] = 0.5 + 0.5 * tau_hat * (1 if r >= 0 else -1)
    return pits


def per_symbol_diagnostics(
    panel_oos: pd.DataFrame,
    bounds: dict[float, pd.DataFrame],
    qt: dict[str, dict[float, float]],
    cb: dict[float, float],
    scale_col: str,
) -> pd.DataFrame:
    rows = []
    for sym, idx in panel_oos.groupby("symbol").groups.items():
        sub = panel_oos.loc[idx]
        row: dict = {"symbol": sym, "n_oos": int(len(sub))}
        for tau in DEFAULT_TAUS:
            band = bounds[tau].loc[sub.index]
            inside = ((sub["mon_open"] >= band["lower"]) &
                      (sub["mon_open"] <= band["upper"]))
            v = (~inside).astype(int).to_numpy()
            lr_uc, p_uc = met._lr_kupiec(v, tau)
            row[f"viol_rate_{tau}"] = float(v.mean())
            row[f"kupiec_p_{tau}"] = float(p_uc)
        # Berkowitz on PITs; dense grid; sort by fri_ts within the symbol
        sub_sorted = sub.sort_values("fri_ts")
        pits = build_lwc_pits(sub_sorted, qt, cb, scale_col)
        clean = pits[(np.isfinite(pits)) & (pits > 0) & (pits < 1)]
        if len(clean) >= 30:
            bw = met.berkowitz_test(clean)
            row["berkowitz_lr"] = float(bw.get("lr", float("nan")))
            row["berkowitz_p"] = float(bw.get("p_value", float("nan")))
            row["berkowitz_n"] = int(bw.get("n", len(clean)))
        else:
            row["berkowitz_lr"] = float("nan")
            row["berkowitz_p"] = float("nan")
            row["berkowitz_n"] = int(len(clean))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


# ----------------------------------------------------------------------------
# Main driver
# ----------------------------------------------------------------------------


def _load_panel() -> pd.DataFrame:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    return panel


def run_variant(panel: pd.DataFrame, variant: dict) -> dict:
    """Run all Phase 5.2 + 5.3 diagnostics for a single variant.

    Returns a dict with:
      delta_sweep_df       (long-form per-split per-(τ, δ))
      delta_schedule       {τ: δ}
      summary_rows         pooled OOS rows at split=2023-01-01
      split_rows           per-split per-τ rows across SPLIT_ANCHORS
      per_symbol_df        per-symbol Kupiec + Berkowitz rows
      n_eval               number of rows used (post σ̂ warm-up filter)
    """
    name = variant["name"]
    add_fn = variant["add_fn"]
    scale_col = variant["scale_col"]
    print(f"\n=== Variant: {name} ({variant['label']}) ===", flush=True)

    work = add_fn(panel)
    work["score"] = compute_score_lwc(work, scale_col=scale_col)
    mask = work["score"].notna() & work[scale_col].notna()
    work = work[mask].copy().reset_index(drop=True)
    print(f"  panel after σ̂ warm-up: {len(work):,} rows × "
          f"{work['fri_ts'].nunique()} weekends", flush=True)

    # 5.2.A — walk-forward δ-sweep (using the deployed split=2023-01-01)
    panel_train = work[work["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = work[work["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"  train={len(panel_train):,}  oos={len(panel_oos):,}", flush=True)
    sweep_rows = []
    for delta in DELTA_GRID:
        wf = walk_forward_lwc_variant(
            panel_train, panel_oos, delta=float(delta),
            score_col="score", scale_col=scale_col,
        )
        sweep_rows.append(wf)
    sweep = pd.concat(sweep_rows, ignore_index=True)
    sweep_path = OUT_TABLES / f"sigma_ewma_{name}_delta_sweep.csv"
    sweep.to_csv(sweep_path, index=False)
    print(f"  wrote {sweep_path}", flush=True)

    delta_schedule = select_delta_schedule(sweep)
    print(f"  selected δ schedule: {delta_schedule}", flush=True)

    # 5.2.B / 5.3.A — pooled OOS at the deployed schedule, split=2023-01-01
    qt_2023, cb_2023 = _fit_split_lwc(work, SPLIT_DATE, score_col="score")
    bounds_2023 = serve_bands_lwc(
        panel_oos, qt_2023, cb_2023,
        cell_col="regime_pub", scale_col=scale_col,
        taus=DEFAULT_TAUS,
        delta_shift_schedule=delta_schedule,
    )
    summary_rows = []
    for tau in DEFAULT_TAUS:
        row = _coverage_row(panel_oos, bounds_2023, tau)
        row["variant"] = name
        row["delta"] = float(delta_schedule[float(tau)])
        row["c_bump"] = float(cb_2023[float(tau)])
        summary_rows.append(row)

    # 5.3.B — split-date Christoffersen across 4 anchors
    split_rows = []
    for d_split in SPLIT_ANCHORS:
        qt, cb = _fit_split_lwc(work, d_split, score_col="score")
        oos_d = (work[work["fri_ts"] >= d_split]
                 .dropna(subset=["score"])
                 .sort_values(["symbol", "fri_ts"])
                 .reset_index(drop=True))
        bounds_d = serve_bands_lwc(
            oos_d, qt, cb,
            cell_col="regime_pub", scale_col=scale_col,
            taus=DEFAULT_TAUS,
            delta_shift_schedule=delta_schedule,
        )
        for tau in DEFAULT_TAUS:
            row = _coverage_row(oos_d, bounds_d, tau)
            row["split_date"] = d_split.isoformat()
            row["variant"] = name
            split_rows.append(row)

    # 5.3.C — per-symbol Berkowitz + Kupiec at split=2023-01-01
    per_symbol = per_symbol_diagnostics(
        panel_oos, bounds_2023, qt_2023, cb_2023, scale_col=scale_col
    )
    per_symbol.insert(0, "variant", name)

    return {
        "name": name,
        "delta_sweep": sweep,
        "delta_schedule": delta_schedule,
        "summary_rows": summary_rows,
        "split_rows": split_rows,
        "per_symbol": per_symbol,
        "n_eval": int(len(work)),
    }


def serve_variant_oos_pairs(panel: pd.DataFrame, variant: dict) -> pd.DataFrame:
    """Per-row (symbol, fri_ts, τ, inside, half_width_bps) for split=2023-01-01.

    Used to build paired bootstrap deltas vs the baseline. Mirrors the
    `_serve_oos` step in `scripts/aggregate_m5_m6_bootstrap.py` but
    parametrised by σ̂ variant."""
    add_fn = variant["add_fn"]
    scale_col = variant["scale_col"]
    work = add_fn(panel)
    work["score"] = compute_score_lwc(work, scale_col=scale_col)
    work = work[work["score"].notna() & work[scale_col].notna()].reset_index(drop=True)

    qt, cb = _fit_split_lwc(work, SPLIT_DATE, score_col="score")
    oos = (work[work["fri_ts"] >= SPLIT_DATE]
           .dropna(subset=["score"])
           .sort_values(["symbol", "fri_ts"])
           .reset_index(drop=True))
    bounds = serve_bands_lwc(
        oos, qt, cb,
        cell_col="regime_pub", scale_col=scale_col,
        taus=DEFAULT_TAUS, delta_shift_schedule={t: 0.0 for t in DEFAULT_TAUS},
    )
    rows = []
    for tau in DEFAULT_TAUS:
        b = bounds[tau]
        inside = ((oos["mon_open"] >= b["lower"]) &
                  (oos["mon_open"] <= b["upper"])).astype(int).to_numpy()
        hw_bps = ((b["upper"] - b["lower"]) / 2 / oos["fri_close"] * 1e4).to_numpy()
        for j, (_, r) in enumerate(oos.iterrows()):
            rows.append({
                "symbol": r["symbol"], "fri_ts": r["fri_ts"], "tau": float(tau),
                "inside": int(inside[j]), "half_width_bps": float(hw_bps[j]),
            })
    return pd.DataFrame(rows)


def bootstrap_delta_vs_baseline(
    panel: pd.DataFrame,
    promote: dict,
    n_replicates: int = 1000,
    seed: int = 0,
) -> pd.DataFrame:
    """Weekend-block bootstrap of (cov_promote − cov_baseline,
    hw_promote − hw_baseline) on `(symbol, fri_ts, τ)`-paired rows.

    Mirrors `aggregate_m5_m6_bootstrap.py` exactly; just swaps M5/LWC for
    baseline_k26 / promote_variant. 95% percentile CI is the deployment
    gate per Phase 5.4."""
    baseline_v = next(v for v in VARIANTS if v["name"] == "baseline_k26")
    df_base = serve_variant_oos_pairs(panel, baseline_v).rename(
        columns={"inside": "inside_base", "half_width_bps": "hw_base"}
    )
    df_prom = serve_variant_oos_pairs(panel, promote).rename(
        columns={"inside": "inside_prom", "half_width_bps": "hw_prom"}
    )
    paired = df_base.merge(df_prom, on=["symbol", "fri_ts", "tau"], how="inner")

    rng = np.random.default_rng(seed)
    weekends = sorted(paired["fri_ts"].unique())
    weekend_to_idx = {w: i for i, w in enumerate(weekends)}
    n_weekends = len(weekends)
    sampled = rng.integers(low=0, high=n_weekends,
                           size=(n_replicates, n_weekends))

    out_rows = []
    for tau in DEFAULT_TAUS:
        sub = paired[paired["tau"] == tau].sort_values(
            ["fri_ts", "symbol"]).reset_index(drop=True)
        weekend_idx = sub["fri_ts"].map(weekend_to_idx).to_numpy()
        i_base = sub["inside_base"].to_numpy(int)
        i_prom = sub["inside_prom"].to_numpy(int)
        hw_base = sub["hw_base"].to_numpy(float)
        hw_prom = sub["hw_prom"].to_numpy(float)

        d_cov = np.empty(n_replicates)
        d_hw = np.empty(n_replicates)
        cov_base_reps = np.empty(n_replicates)
        cov_prom_reps = np.empty(n_replicates)
        hw_base_reps = np.empty(n_replicates)
        hw_prom_reps = np.empty(n_replicates)
        for r in range(n_replicates):
            counts = pd.Series(sampled[r]).value_counts()
            weights = np.zeros(n_weekends + 1, dtype=int)
            weights[counts.index.values] = counts.values
            row_w = weights[weekend_idx]
            tot = row_w.sum()
            if tot == 0:
                d_cov[r] = d_hw[r] = float("nan")
                continue
            cov_b = (i_base * row_w).sum() / tot
            cov_p = (i_prom * row_w).sum() / tot
            hw_b = (hw_base * row_w).sum() / tot
            hw_p = (hw_prom * row_w).sum() / tot
            cov_base_reps[r] = cov_b
            cov_prom_reps[r] = cov_p
            hw_base_reps[r] = hw_b
            hw_prom_reps[r] = hw_p
            d_cov[r] = cov_p - cov_b
            d_hw[r] = hw_p - hw_b

        out_rows.append({
            "tau": float(tau),
            "point_realised_baseline": float(i_base.mean()),
            "point_realised_promote": float(i_prom.mean()),
            "point_delta_realised": float(i_prom.mean() - i_base.mean()),
            "ci_lo_delta_realised": float(np.quantile(d_cov, 0.025)),
            "ci_hi_delta_realised": float(np.quantile(d_cov, 0.975)),
            "point_hw_bps_baseline": float(hw_base.mean()),
            "point_hw_bps_promote": float(hw_prom.mean()),
            "point_delta_hw_bps": float(hw_prom.mean() - hw_base.mean()),
            "ci_lo_delta_hw_bps": float(np.quantile(d_hw, 0.025)),
            "ci_hi_delta_hw_bps": float(np.quantile(d_hw, 0.975)),
            "point_delta_hw_pct_baseline": float(
                (hw_prom.mean() - hw_base.mean()) / hw_base.mean() * 100.0
            ),
            "ci_hi_delta_hw_pct_baseline": float(
                np.quantile(d_hw, 0.975) / hw_base.mean() * 100.0
            ),
            "n_weekends": int(n_weekends),
            "n_rows": int(len(sub)),
            "n_replicates": int(n_replicates),
            "seed": int(seed),
        })
    return pd.DataFrame(out_rows)


def benjamini_hochberg(p_values: np.ndarray, fdr: float) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values controlling FDR at `fdr`.

    Returns an array `q` of the same shape as `p_values` such that
    `q[i] ≤ fdr` iff hypothesis i is rejected under BH at level `fdr`.

    Standard step-up procedure: sort ascending, threshold rank k at
    `k · fdr / m`, find the largest k with `p_(k) ≤ threshold`, reject
    H_(1), …, H_(k). Adjusted p-values are the cumulative-min from the
    right of `m · p_(k) / k`.
    """
    p = np.asarray(p_values, dtype=float)
    n = p.size
    if n == 0:
        return p.copy()
    order = np.argsort(p)
    ranked = p[order]
    ranks = np.arange(1, n + 1, dtype=float)
    raw_q = ranked * n / ranks
    # Cumulative min from the right (BH adjusted p-value monotonisation).
    q_sorted = np.minimum.accumulate(raw_q[::-1])[::-1]
    q_sorted = np.minimum(q_sorted, 1.0)
    q = np.empty_like(p)
    q[order] = q_sorted
    return q


def emit_multiple_testing_correction(all_split: pd.DataFrame, fdr: float = 0.05) -> dict:
    """Apply Benjamini-Hochberg correction at FDR=`fdr` across the full
    (variant × split × τ) split-date Christoffersen grid.

    Phase 5's promotion procedure ran 80 split-date Christoffersen tests
    (5 variants × 4 split anchors × 4 τ values) and selected the variant
    with zero per-cell rejections at uncorrected α=0.05. That selection
    is multiple-testing exposed (the "garden of forking paths" — under
    the joint null, ~4 of 80 tests are expected to reject by chance, and
    the procedure favours variants that happened to land lucky).

    BH correction across the full 80-cell grid is the standard mitigation:
    we sort the 80 p-values, threshold rank k at k · fdr / 80, and accept
    only the variants with no BH-rejected cell. Adjusted p-values are
    written under `christ_p_bh` next to the raw `christ_p`.

    Output: `reports/tables/sigma_ewma_split_sensitivity_bh_corrected.csv`
    (full 80-row grid with raw + adjusted p-values + per-cell BH verdict).

    Returns a dict with the BH-qualified variant set so callers can
    cross-check the corrected verdict against the uncorrected one.
    """
    p = all_split["christ_p"].to_numpy(float)
    q = benjamini_hochberg(p, fdr=fdr)
    out = all_split.copy()
    out["christ_p_bh"] = q
    out["bh_reject"] = (q < fdr).astype(int)
    n_total = len(out)
    n_uncorrected = int((out["christ_p"] < fdr).sum())
    n_bh = int(out["bh_reject"].sum())

    qualified_uncorr: list[str] = []
    qualified_bh: list[str] = []
    for v in [V["name"] for V in VARIANTS]:
        sub = out[out["variant"] == v]
        if (sub["christ_p"] < fdr).sum() == 0:
            qualified_uncorr.append(v)
        if (sub["bh_reject"] == 0).all():
            qualified_bh.append(v)

    bh_path = OUT_TABLES / "sigma_ewma_split_sensitivity_bh_corrected.csv"
    out[["variant", "split_date", "tau", "christ_p", "christ_p_bh",
         "bh_reject"]].to_csv(bh_path, index=False)

    print("\n" + "=" * 100)
    print(f"BENJAMINI-HOCHBERG CORRECTION — split-date Christoffersen grid")
    print(f"  m = {n_total} tests (5 variants × 4 splits × 4 τ); FDR = {fdr}")
    print("=" * 100)
    print(f"  Uncorrected α=0.05 rejections : {n_uncorrected} / {n_total}")
    print(f"  BH-corrected   FDR=0.05      : {n_bh} / {n_total}")
    print()
    print(f"  Variants qualifying (zero rejected cells)")
    print(f"    Uncorrected : {qualified_uncorr if qualified_uncorr else 'NONE'}")
    print(f"    BH-corrected: {qualified_bh if qualified_bh else 'NONE'}")
    print(f"  Wrote {bh_path}")
    return {
        "fdr": fdr,
        "n_tests": n_total,
        "n_uncorrected_rejections": n_uncorrected,
        "n_bh_rejections": n_bh,
        "qualified_uncorrected": qualified_uncorr,
        "qualified_bh": qualified_bh,
    }


def main() -> None:
    OUT_TABLES.mkdir(parents=True, exist_ok=True)
    panel = _load_panel()
    print(f"Loaded panel: {len(panel):,} rows × "
          f"{panel['fri_ts'].nunique()} weekends × "
          f"{panel['symbol'].nunique()} symbols", flush=True)

    results = [run_variant(panel, v) for v in VARIANTS]

    # Consolidated summary CSV
    all_summary = pd.DataFrame(
        [r for res in results for r in res["summary_rows"]]
    )
    all_summary = all_summary[[
        "variant", "tau", "delta", "c_bump", "realised", "half_width_bps",
        "kupiec_lr", "kupiec_p", "christ_lr", "christ_p",
        "n_oos", "n_oos_weekends",
    ]]
    summary_path = OUT_TABLES / "sigma_ewma_summary.csv"
    all_summary.to_csv(summary_path, index=False)
    print(f"\nWrote {summary_path}", flush=True)

    # Split-date Christoffersen consolidated
    all_split = pd.DataFrame(
        [r for res in results for r in res["split_rows"]]
    )
    all_split = all_split[[
        "variant", "split_date", "tau", "n_oos", "n_oos_weekends",
        "realised", "half_width_bps",
        "kupiec_lr", "kupiec_p", "christ_lr", "christ_p",
    ]]
    split_path = OUT_TABLES / "sigma_ewma_split_sensitivity.csv"
    all_split.to_csv(split_path, index=False)
    print(f"Wrote {split_path}", flush=True)

    # Multiple-testing correction across the full (variant × split × τ) grid.
    # Disclosure layer for §13 of reports/m6_sigma_ewma.md — does NOT change
    # the deployment decision; documents the selection-induced bias and
    # records which variants survive Benjamini-Hochberg at FDR=0.05.
    bh_summary = emit_multiple_testing_correction(all_split, fdr=0.05)

    # Per-symbol diagnostics consolidated
    all_psym = pd.concat([res["per_symbol"] for res in results],
                         ignore_index=True)
    psym_path = OUT_TABLES / "sigma_ewma_per_symbol.csv"
    all_psym.to_csv(psym_path, index=False)
    print(f"Wrote {psym_path}", flush=True)

    # Print the headline tables
    print("\n" + "=" * 100)
    print("PHASE 5 — POOLED OOS @ split=2023-01-01 (deployed δ per variant)")
    print("=" * 100)
    pivot_summary = all_summary.pivot_table(
        index="variant", columns="tau",
        values=["realised", "half_width_bps", "kupiec_p", "christ_p"]
    )
    print(pivot_summary.round(4).to_string())

    print("\n" + "=" * 100)
    print("SPLIT-DATE CHRISTOFFERSEN p-VALUE  (target column: τ=0.95)")
    print("=" * 100)
    for variant in [r["name"] for r in results]:
        sub = all_split[(all_split["variant"] == variant)
                        & (all_split["tau"] == 0.95)]
        print(f"  {variant:>15s}: " + "  ".join(
            f"{r['split_date']}: christ_p={r['christ_p']:.4f}"
            for _, r in sub.iterrows()
        ))

    print("\n" + "=" * 100)
    print("PER-SYMBOL Kupiec @ τ=0.95 PASS RATES (target ≥ 8/10)")
    print("=" * 100)
    for variant in [r["name"] for r in results]:
        sub = all_psym[all_psym["variant"] == variant]
        n_pass = int((sub["kupiec_p_0.95"] >= 0.05).sum())
        n_total = len(sub)
        print(f"  {variant:>15s}: {n_pass}/{n_total}")

    print("\n" + "=" * 100)
    print("PER-SYMBOL Berkowitz LR — symbols with p < 0.01 (Phase 2 outliers)")
    print("=" * 100)
    flagged = ("TSLA", "GOOGL", "TLT")
    for variant in [r["name"] for r in results]:
        sub = all_psym[all_psym["variant"] == variant]
        flagged_rows = sub[sub["symbol"].isin(flagged)]
        bits = []
        for _, r in flagged_rows.iterrows():
            verdict = "REJ" if r["berkowitz_p"] < 0.01 else "PASS"
            bits.append(f"{r['symbol']}: LR={r['berkowitz_lr']:.2f} "
                        f"(p={r['berkowitz_p']:.4f}, {verdict})")
        print(f"  {variant:>15s}: " + "  |  ".join(bits))

    # Promotion-criterion qualification check: clears split-date Christoffersen
    # at every (split × τ) at α=0.05 AND per-symbol Kupiec ≥ 8/10.
    qualified: list[str] = []
    for v in VARIANTS:
        if v["name"] == "baseline_k26":
            continue
        sub_split = all_split[all_split["variant"] == v["name"]]
        if (sub_split["christ_p"] < 0.05).any():
            continue
        sub_psym = all_psym[all_psym["variant"] == v["name"]]
        n_pass = int((sub_psym["kupiec_p_0.95"] >= 0.05).sum())
        if n_pass < 8:
            continue
        qualified.append(v["name"])
    print("\n" + "=" * 100)
    print("PROMOTION-CRITERION QUALIFICATION")
    print("=" * 100)
    print(f"  Variants clearing split-date Christoffersen × per-symbol Kupiec ≥ 8/10:")
    print(f"  {qualified if qualified else 'NONE'}")

    promote_name: str | None = None
    if qualified:
        # Tiebreaker: prefer longest half-life (most data-efficient).
        def _hl_key(name: str) -> int:
            if name.startswith("ewma_hl"):
                return int(name.split("hl")[-1])
            if name.startswith("blend_a50_hl"):
                return int(name.split("hl")[-1])
            return -1
        qualified.sort(key=_hl_key, reverse=True)
        # Tiebreaker preference: pure EWMA over blend at same HL.
        if "ewma_hl12" in qualified:
            promote_name = "ewma_hl12"
        else:
            promote_name = qualified[0]
        print(f"  Tie-broken winner (longest HL, EWMA over blend): {promote_name}")

        promote_v = next(v for v in VARIANTS if v["name"] == promote_name)
        print(f"\n[bootstrap] paired weekend-block CI on Δ(width) and Δ(realised) "
              f"vs baseline_k26 (1000 reps, seed=0) …", flush=True)
        bs = bootstrap_delta_vs_baseline(panel, promote_v,
                                          n_replicates=1000, seed=0)
        bs.insert(0, "promote_variant", promote_name)
        bs_path = OUT_TABLES / "sigma_ewma_bootstrap.csv"
        bs.to_csv(bs_path, index=False)
        print(f"  wrote {bs_path}", flush=True)
        print()
        print(f"{'τ':>5} {'realised_base':>14} {'realised_prom':>14} "
              f"{'Δrealised':>10} {'95%CI(Δrealised)':>22} "
              f"{'hw_base':>9} {'hw_prom':>9} {'Δhw_bps':>9} "
              f"{'Δhw_%':>7} {'95%CI hi (%)':>13}")
        for _, r in bs.iterrows():
            print(f"{r['tau']:>5.2f} "
                  f"{r['point_realised_baseline']:>14.4f} "
                  f"{r['point_realised_promote']:>14.4f} "
                  f"{r['point_delta_realised']:>+10.4f} "
                  f"  [{r['ci_lo_delta_realised']:+.4f}, {r['ci_hi_delta_realised']:+.4f}] "
                  f"{r['point_hw_bps_baseline']:>9.1f} "
                  f"{r['point_hw_bps_promote']:>9.1f} "
                  f"{r['point_delta_hw_bps']:>+9.2f} "
                  f"{r['point_delta_hw_pct_baseline']:>+7.2f} "
                  f"{r['ci_hi_delta_hw_pct_baseline']:>+13.2f}")

        # Final gate: 95-CI upper on Δhw% ≤ +5 at every τ.
        worst_hi = float(bs["ci_hi_delta_hw_pct_baseline"].max())
        gate_pass = bool(worst_hi <= 5.0)
        print(f"\n  Δhw 95-CI upper bound (max across τ): {worst_hi:+.2f}%")
        print(f"  Phase 5 gate (≤ +5%): {'PASS' if gate_pass else 'FAIL'}")
        print(f"\n  PROMOTION VERDICT: "
              f"{'PROMOTE → ' + promote_name if gate_pass else 'REJECT (width gate failed)'}")
    else:
        print("  PROMOTION VERDICT: REJECT (no variant cleared the criterion)")


if __name__ == "__main__":
    main()
