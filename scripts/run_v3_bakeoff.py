"""
v3 methodology bake-off — Candidates 1, 2, 4 head-to-head against M5 baseline.

Question
--------
The §10 robustness pass localised M5's residual rejection to two sources:
(A) per-symbol residual-scale heterogeneity (bimodal Berkowitz / per-symbol
Kupiec) and (B) cross-sectional within-weekend common-mode (ρ_cross =
0.354). The vol-tertile sub-split refuted finer regime granularity as a
fix. Three candidate methodologies attack the disease:

  C1  Locally-weighted conformal (LWC)
        score   = |residual| / (fri_close · σ̂_sym(t))
        cell    = regime_pub          (3 cells, like M5)
        serve   = q(τ) · c(τ) · fri_close · σ̂_sym(t)

  C2  Symbol-class Mondrian (M6b2 ported to the AMM-evaluation frame)
        score   = |residual| / fri_close   (M5's score)
        cell    = symbol_class        (6 cells; mapping from
                                       data/processed/m6b2_lending_artefact_v1.json)
        serve   = q(τ) · c(τ) · fri_close   (M5-style relative band)

  C4  Stacked LWC + M6b2
        score   = |residual| / (fri_close · σ̂_sym(t))
        cell    = symbol_class
        serve   = q(τ) · c(τ) · fri_close · σ̂_sym(t)

  M5  Baseline (deployed, refit here for parity)
        score   = |residual| / fri_close
        cell    = regime_pub
        serve   = q(τ) · c(τ) · fri_close

Method
------
- Same panel (`v1b_panel.parquet`), same train/OOS split (2023-01-01),
  same four served τ ∈ {0.68, 0.85, 0.95, 0.99}.
- Quantile table refit on TRAIN per (cell × τ) via finite-sample CP rank.
- c(τ) refit on OOS as the smallest c with mean(score ≤ b·c) ≥ τ.
- δ-shift schedule held at **zero** for all variants — the deployed δ
  schedule was tuned for M5; using it here would bias the bake-off.
- σ̂_sym(t) = trailing-K weekends standard deviation of relative residual
  for that symbol, K = min(26, n_available_past), require ≥ 8 past
  observations. Strictly pre-Friday (uses only fri_ts' < fri_ts rows).
- Evaluation per variant:
    * pooled realised coverage + Kupiec at each τ
    * mean half-width (bps) at each τ
    * **per-symbol Kupiec p at τ=0.95** (the new headline metric)
    * Berkowitz LR on PITs (cross-sectional-within-weekend ordering)
    * cross-sectional ρ in PITs (the load-bearing residual mechanism)

Outputs
-------
  reports/tables/v3_bakeoff_pooled.csv         pooled headline numbers
  reports/tables/v3_bakeoff_per_symbol.csv     per-symbol Kupiec at τ ∈ {0.95, 0.99}
  reports/tables/v3_bakeoff_mechanism.csv      Berkowitz / ρ_cross per variant
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
TAUS = (0.68, 0.85, 0.95, 0.99)
SCALE_K = 26
SCALE_MIN = 8


# ----------------------------------------------------------- σ̂_sym helpers


def add_sigma_hat(panel: pd.DataFrame) -> pd.DataFrame:
    """Add `sigma_hat_sym` = trailing-K relative-residual std per symbol,
    computed strictly from rows with `fri_ts' < fri_ts`. Rows lacking
    SCALE_MIN past observations get NaN."""
    out = panel.sort_values(["symbol", "fri_ts"]).reset_index(drop=True).copy()
    out["rel_resid"] = (
        (out["mon_open"].astype(float) - out["fri_close"].astype(float) *
         (1.0 + out["factor_ret"].astype(float)))
        / out["fri_close"].astype(float)
    )
    sigma = np.full(len(out), np.nan)
    for sym, idx in out.groupby("symbol").groups.items():
        sub = out.loc[idx]
        rr = sub["rel_resid"].to_numpy(float)
        # Strictly past: at row position i, use rows [max(0, i-K), i)
        for i, src_idx in enumerate(idx):
            lo = max(0, i - SCALE_K)
            past = rr[lo:i]
            past = past[np.isfinite(past)]
            if past.size < SCALE_MIN:
                continue
            sigma[src_idx] = float(np.std(past, ddof=1))
    out["sigma_hat_sym"] = sigma
    return out


# ------------------------------------------------------ symbol_class lookup


def load_symbol_class_map() -> dict[str, str]:
    sidecar = json.loads((DATA_PROCESSED / "m6b2_lending_artefact_v1.json").read_text())
    return dict(sidecar["symbol_class_mapping"])


# --------------------------------------------------------- M5-style fit/serve


def train_quantile_table(panel_train: pd.DataFrame, cell_col: str,
                         score_col: str, taus: tuple[float, ...]) -> dict:
    out: dict[str, dict[float, float]] = {}
    for cell, g in panel_train.groupby(cell_col):
        scores = g[score_col].dropna().to_numpy(float)
        n = scores.size
        if n == 0:
            out[str(cell)] = {tau: float("nan") for tau in taus}
            continue
        sorted_scores = np.sort(scores)
        row = {}
        for tau in taus:
            k = int(np.ceil(tau * (n + 1)))
            k = min(max(k, 1), n)
            row[tau] = float(sorted_scores[k - 1])
        out[str(cell)] = row
    return out


def fit_c_bump(panel_oos: pd.DataFrame, qt: dict, cell_col: str,
               score_col: str, taus: tuple[float, ...]) -> dict[float, float]:
    grid = np.arange(1.0, 5.0001, 0.001)
    cells = panel_oos[cell_col].astype(str).to_numpy()
    scores = panel_oos[score_col].to_numpy(float)
    out = {}
    for tau in taus:
        b_per = np.array([qt.get(c, {}).get(tau, np.nan) for c in cells],
                         dtype=float)
        m = np.isfinite(b_per) & np.isfinite(scores)
        s = scores[m]
        b = b_per[m]
        chosen = float(grid[-1])
        for c in grid:
            if float(np.mean(s <= b * c)) >= tau:
                chosen = float(c)
                break
        out[tau] = chosen
    return out


def serve_variant(panel: pd.DataFrame, qt: dict, cb: dict,
                  cell_col: str, *, lwc: bool,
                  taus: tuple[float, ...]) -> dict[float, pd.DataFrame]:
    """Serve bands for any of the four variants.

    M5 / M6b2 (lwc=False):
        half_width = q(τ) · c(τ) · fri_close
    LWC variants (lwc=True):
        half_width = q(τ) · c(τ) · fri_close · σ̂_sym(t)
    """
    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    fri_close = panel["fri_close"].astype(float).to_numpy()
    cells = panel[cell_col].astype(str).to_numpy()
    sigma = panel["sigma_hat_sym"].to_numpy(float) if lwc else None
    out: dict[float, pd.DataFrame] = {}
    for tau in taus:
        c = float(cb[tau])
        b_per = np.array([qt.get(cl, {}).get(tau, np.nan) for cl in cells],
                         dtype=float)
        if lwc:
            half = c * b_per * fri_close * sigma
        else:
            half = c * b_per * fri_close
        out[tau] = pd.DataFrame({
            "lower": point.values - half,
            "upper": point.values + half,
        }, index=panel.index)
    return out


# ---------------------------------------------------- PIT + mechanism metrics


DENSE_GRID = (
    0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.68, 0.70, 0.80, 0.85,
    0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999,
)


def _interp(table: dict[float, float], x: float) -> float:
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


def build_pits(panel: pd.DataFrame, qt: dict, cb: dict, cell_col: str,
               *, lwc: bool, dense: tuple[float, ...] = DENSE_GRID) -> np.ndarray:
    """Build per-row PITs at the variant's served-band CDF, dense τ grid.

    Caller must order panel by (fri_ts, symbol) so the lag-1 in Berkowitz
    captures cross-sectional within-weekend AR(1) — the §6.3.1 frame."""
    grid_taus = np.array(sorted(dense))
    point = (panel["fri_close"].astype(float) *
             (1.0 + panel["factor_ret"].astype(float))).to_numpy()
    fri_close = panel["fri_close"].astype(float).to_numpy()
    mon_open = panel["mon_open"].astype(float).to_numpy()
    cells = panel[cell_col].astype(str).to_numpy()
    sigma = panel["sigma_hat_sym"].to_numpy(float) if lwc else None
    pits = np.full(len(panel), np.nan)
    for i in range(len(panel)):
        q_row = qt.get(cells[i])
        if q_row is None:
            continue
        b_anchors = np.array([
            _interp(q_row, tau) * _interp(cb, tau) for tau in grid_taus
        ], dtype=float)
        # In LWC, b_anchors are unitless; multiply by fri_close · σ̂.
        # In M5/M6b2 they are already scaled by fri_close / fri_close (relative).
        # In both cases the band half-width in price units at row i is:
        #   half_i = b_anchor · fri_close[i] · (sigma[i] if lwc else 1.0)
        scale = fri_close[i] * (sigma[i] if lwc else 1.0)
        if not np.isfinite(scale) or scale <= 0:
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


def lag1_rho(z: np.ndarray) -> tuple[float, int]:
    z = z[np.isfinite(z)]
    if len(z) < 30:
        return float("nan"), 0
    z_lag = z[:-1]
    z_cur = z[1:]
    rho = float(np.corrcoef(z_cur, z_lag)[0, 1])
    return rho, len(z_cur)


# --------------------------------------------------- variant evaluation


def per_symbol_kupiec_at(panel: pd.DataFrame, bounds: pd.DataFrame,
                         tau: float) -> pd.DataFrame:
    rows = []
    for sym, idx in panel.groupby("symbol").groups.items():
        sub = panel.loc[idx]
        b = bounds.loc[idx]
        inside = (sub["mon_open"] >= b["lower"]) & (sub["mon_open"] <= b["upper"])
        v = (~inside).astype(int).to_numpy()
        lr, p = met._lr_kupiec(v, tau)
        rows.append({
            "symbol": sym, "n": int(len(sub)), "tau": tau,
            "viol_rate": float(v.mean()),
            "kupiec_lr": float(lr), "kupiec_p": float(p),
        })
    return pd.DataFrame(rows)


def evaluate_variant(name: str, panel_train: pd.DataFrame,
                     panel_oos_eval: pd.DataFrame, panel_oos_cfit: pd.DataFrame,
                     cell_col: str, score_col: str, lwc: bool) -> dict:
    qt = train_quantile_table(panel_train, cell_col, score_col, TAUS)
    cb = fit_c_bump(panel_oos_cfit, qt, cell_col, score_col, TAUS)
    bounds = serve_variant(panel_oos_eval, qt, cb, cell_col, lwc=lwc, taus=TAUS)

    pooled_rows = []
    per_sym_all = []
    for tau in TAUS:
        b = bounds[tau]
        inside = ((panel_oos_eval["mon_open"] >= b["lower"]) &
                  (panel_oos_eval["mon_open"] <= b["upper"]))
        v = (~inside).astype(int).to_numpy()
        lr, p = met._lr_kupiec(v, tau)
        pooled_rows.append({
            "variant": name, "tau": tau,
            "n": int(len(panel_oos_eval)),
            "realised": float(inside.mean()),
            "half_width_bps": float(((b["upper"] - b["lower"]) / 2 /
                                     panel_oos_eval["fri_close"] * 1e4).mean()),
            "kupiec_lr": float(lr), "kupiec_p": float(p),
            "c_bump": float(cb[tau]),
        })
        if tau in (0.95, 0.99):
            ps = per_symbol_kupiec_at(panel_oos_eval, b, tau)
            ps["variant"] = name
            per_sym_all.append(ps)

    # Mechanism metrics — cross-sectional ordering for Berkowitz
    panel_xs = panel_oos_eval.sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    qt_x = qt
    cb_x = cb
    pits = build_pits(panel_xs, qt_x, cb_x, cell_col, lwc=lwc)
    pits_clean = pits[(np.isfinite(pits)) & (pits > 0) & (pits < 1)]
    z = norm.ppf(pits_clean) if len(pits_clean) >= 30 else np.array([])
    rho_cross, n_pairs = lag1_rho(z) if len(z) > 0 else (float("nan"), 0)
    bw = met.berkowitz_test(pits_clean) if len(pits_clean) >= 30 else {
        "lr": float("nan"), "p_value": float("nan"), "n": 0,
        "rho_hat": float("nan"), "var_z": float("nan"), "mean_z": float("nan"),
    }

    mechanism = {
        "variant": name,
        "n_pits": int(len(pits_clean)),
        "berkowitz_lr": float(bw.get("lr", np.nan)),
        "berkowitz_p": float(bw.get("p_value", np.nan)),
        "rho_cross_xs": float(rho_cross),
        "n_pairs_xs": int(n_pairs),
        "var_z": float(bw.get("var_z", np.nan)),
        "mean_z": float(bw.get("mean_z", np.nan)),
    }

    return {
        "pooled": pd.DataFrame(pooled_rows),
        "per_symbol": (pd.concat(per_sym_all, ignore_index=True)
                       if per_sym_all else pd.DataFrame()),
        "mechanism": mechanism,
    }


# ---------------------------------------------------------------------- main


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    # Symbol class.
    smap = load_symbol_class_map()
    panel["symbol_class"] = panel["symbol"].map(smap)
    if panel["symbol_class"].isna().any():
        unmapped = panel[panel["symbol_class"].isna()]["symbol"].unique()
        raise ValueError(f"Unmapped symbols in symbol_class lookup: {unmapped}")

    # σ̂_sym(t) — pre-Friday rolling residual std.
    panel = add_sigma_hat(panel)

    # Score columns.
    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    panel["score_M5"] = (panel["mon_open"].astype(float) - point).abs() / panel["fri_close"]
    panel["score_LWC"] = panel["score_M5"] / panel["sigma_hat_sym"]

    # Train / OOS — drop rows lacking σ̂_sym so all variants share the same
    # evaluation panel (otherwise LWC and M5 would have different N).
    mask_full = (panel["score_M5"].notna() & panel["sigma_hat_sym"].notna() &
                 panel["score_LWC"].notna())
    work = panel[mask_full].copy()
    print(f"Panel after σ̂_sym filter: {len(work):,} rows × "
          f"{work['fri_ts'].nunique()} weekends "
          f"(dropped {len(panel) - len(work):,} rows lacking ≥{SCALE_MIN} "
          f"past obs per symbol)", flush=True)

    train = work[work["fri_ts"] < SPLIT_DATE].copy()
    oos = work[work["fri_ts"] >= SPLIT_DATE].copy()
    print(f"  train: {len(train):,}  oos: {len(oos):,}", flush=True)

    variants = [
        ("M5_baseline",    "regime_pub",   "score_M5",  False),
        ("C1_LWC_regime",  "regime_pub",   "score_LWC", True),
        ("C2_M6b2_class",  "symbol_class", "score_M5",  False),
        ("C4_LWC_class",   "symbol_class", "score_LWC", True),
    ]

    pooled_all = []
    per_sym_all = []
    mechanism_rows = []
    for name, cell_col, score_col, lwc in variants:
        print(f"\n[{name}] cell={cell_col}  score={score_col}  lwc={lwc}",
              flush=True)
        out = evaluate_variant(name, train, oos, oos, cell_col, score_col, lwc)
        print(out["pooled"].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        m = out["mechanism"]
        print(f"  Berkowitz LR={m['berkowitz_lr']:.2f} (p={m['berkowitz_p']:.2e})  "
              f"ρ_cross={m['rho_cross_xs']:.3f}  var_z={m['var_z']:.3f}",
              flush=True)
        pooled_all.append(out["pooled"])
        per_sym_all.append(out["per_symbol"])
        mechanism_rows.append(m)

    pooled = pd.concat(pooled_all, ignore_index=True)
    per_sym = pd.concat(per_sym_all, ignore_index=True)
    mech = pd.DataFrame(mechanism_rows)

    out_dir = REPORTS / "tables"
    pooled.to_csv(out_dir / "v3_bakeoff_pooled.csv", index=False)
    per_sym.to_csv(out_dir / "v3_bakeoff_per_symbol.csv", index=False)
    mech.to_csv(out_dir / "v3_bakeoff_mechanism.csv", index=False)

    print("\n" + "=" * 100)
    print("HEADLINE — pooled τ=0.95")
    print("=" * 100)
    h95 = pooled[pooled["tau"] == 0.95][
        ["variant", "n", "realised", "half_width_bps", "kupiec_p", "c_bump"]
    ]
    print(h95.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n" + "=" * 100)
    print("PER-SYMBOL KUPIEC AT τ=0.95 (worst-case across symbols)")
    print("=" * 100)
    ps95 = per_sym[per_sym["tau"] == 0.95]
    summary = ps95.groupby("variant").agg(
        n_symbols=("symbol", "nunique"),
        worst_kupiec_p=("kupiec_p", "min"),
        n_pass_05=("kupiec_p", lambda x: int((x >= 0.05).sum())),
        viol_rate_max=("viol_rate", "max"),
        viol_rate_min=("viol_rate", "min"),
    ).reset_index()
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n" + "=" * 100)
    print("PER-SYMBOL KUPIEC AT τ=0.95 — full table")
    print("=" * 100)
    pivot = ps95.pivot_table(
        index="symbol", columns="variant",
        values="kupiec_p"
    )
    pivot_v = ps95.pivot_table(
        index="symbol", columns="variant",
        values="viol_rate"
    )
    print("Kupiec p:")
    print(pivot.to_string(float_format=lambda x: f"{x:.3f}"))
    print("\nViolation rate:")
    print(pivot_v.to_string(float_format=lambda x: f"{x:.3f}"))

    print("\n" + "=" * 100)
    print("MECHANISM — Berkowitz / cross-sectional ρ")
    print("=" * 100)
    print(mech.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print(f"\nWrote {out_dir / 'v3_bakeoff_pooled.csv'}")
    print(f"Wrote {out_dir / 'v3_bakeoff_per_symbol.csv'}")
    print(f"Wrote {out_dir / 'v3_bakeoff_mechanism.csv'}")


if __name__ == "__main__":
    main()
