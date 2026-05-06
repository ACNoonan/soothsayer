"""Paper 1 — Tier B item B4.

Regime classifier internal-consistency check: swap VIX → GVZ for GLD and
VIX → MOVE for TLT in the regime-classifier `high_vol` flag, then re-fit
M6 LWC and compare to the deployed VIX-only classifier.

The deployed regime classifier flags `high_vol` if VIX_fri_close is in
the top quartile of its trailing 52-weekend window — for *all* symbols.
But GLD (gold) and TLT (long-dated treasury) have their own vol indices
(GVZ and MOVE) that more naturally signal asset-specific high-vol
regimes. The §7 σ̂-regression story already uses asset-specific σ̂; the
regime classifier currently does not. This is an internal-consistency
gap: either the swap matters (and we should disclose) or it doesn't (and
we should disclose that).

Approach:
  1. Build deployed regime tag (`regime_pub_VIX`).
  2. Build hybrid tag (`regime_pub_HYBRID`):
       - GLD high_vol if GVZ_fri_close > q75(rolling-52-week GVZ)
       - TLT high_vol if MOVE_fri_close > q75(rolling-52-week MOVE)
       - all other symbols: as VIX (deployed rule)
       - long_weekend / normal: unchanged
  3. Re-fit M6 LWC under each tagging and compare:
       - GLD-only and TLT-only per-symbol Kupiec / Christoffersen at all τ
       - Pooled coverage / half-width at all τ
       - Regime tag agreement rate per (symbol, weekend)

Output:
  reports/tables/paper1_b4_regime_index_sensitivity.csv
  reports/tables/paper1_b4_regime_index_sensitivity_per_symbol.csv
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    add_sigma_hat_sym_ewma,
    SIGMA_HAT_HL_WEEKENDS,
    train_quantile_table,
    fit_c_bump_schedule,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)
ROLLING_WEEKS = 52
ROLLING_QUANTILE = 0.75
ASSET_INDEX_OVERRIDE = {"GLD": "gvz_fri_close", "TLT": "move_fri_close"}


def _high_vol_flag_per_index(panel: pd.DataFrame, index_col: str) -> pd.Series:
    idx = panel[["fri_ts", index_col]].drop_duplicates().sort_values("fri_ts")
    rolling = idx[index_col].rolling(ROLLING_WEEKS, min_periods=20).quantile(ROLLING_QUANTILE)
    lookup = pd.Series(rolling.values, index=idx["fri_ts"].values)
    return panel["fri_ts"].map(lookup).lt(panel[index_col]).fillna(False)


def build_hybrid_regime(panel: pd.DataFrame) -> pd.Series:
    """Per-symbol high-vol via VIX/GVZ/MOVE, then `regime_pub`-style merge."""
    high_vol_default = _high_vol_flag_per_index(panel, "vix_fri_close")
    high_vol = high_vol_default.copy()
    for sym, idx_col in ASSET_INDEX_OVERRIDE.items():
        sym_mask = panel["symbol"] == sym
        if not sym_mask.any():
            continue
        sub = panel[sym_mask].copy()
        sub_flag = _high_vol_flag_per_index(sub, idx_col).reindex(panel.index, fill_value=False)
        # Replace high_vol values for this symbol with sub_flag values
        high_vol = high_vol.where(~sym_mask, sub_flag)
    regime = pd.Series("normal", index=panel.index, dtype=object)
    regime.loc[panel["gap_days"] >= 4] = "long_weekend"
    regime.loc[high_vol.values] = "high_vol"
    return regime


def fit_eval(panel: pd.DataFrame, regime_col: str) -> tuple[dict, dict]:
    """Fit M6 LWC under given regime column. Returns (qt, cb)."""
    p = panel.copy()
    p["regime_active"] = p[regime_col].astype(str)
    train = p[p["fri_ts"] <  SPLIT_DATE].reset_index(drop=True)
    oos   = p[p["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    qt = train_quantile_table(train, cell_col="regime_active",
                               taus=HEADLINE_TAUS, score_col="score_lwc")
    cb = fit_c_bump_schedule(oos, qt, cell_col="regime_active",
                              taus=HEADLINE_TAUS, score_col="score_lwc")
    return qt, cb


def evaluate(panel_oos: pd.DataFrame, qt: dict, cb: dict,
             regime_col: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cells = panel_oos[regime_col].astype(str).to_numpy()
    sigma = panel_oos["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    score = panel_oos["score_lwc"].astype(float).to_numpy()
    base_valid = np.isfinite(score) & np.isfinite(sigma) & (sigma > 0)
    pooled = []
    persym = []
    for tau in HEADLINE_TAUS:
        c = cb[tau]
        b_per_row = np.array(
            [qt.get(cells[i], {}).get(tau, np.nan)
             for i in range(len(panel_oos))],
            dtype=float,
        )
        valid = base_valid & np.isfinite(b_per_row)
        s = score[valid]
        b_eff = b_per_row[valid] * c
        inside = (s <= b_eff).astype(int)
        viol = (1 - inside).astype(int)
        lr_uc, p_uc = met._lr_kupiec(viol, tau)
        lr_ind, p_ind = met._lr_christoffersen_independence(viol)
        sigma_v = sigma[valid]
        hw_bps = b_eff * sigma_v * 1e4
        pooled.append({
            "target": tau, "bump_c": float(c),
            "n_oos": int(valid.sum()),
            "realised": float(inside.mean()),
            "kupiec_p": float(p_uc),
            "christoffersen_p": float(p_ind),
            "half_width_bps_mean": float(hw_bps.mean()),
        })
        # Per-symbol at τ=0.95 only
        if tau == 0.95:
            sub = panel_oos[valid].copy()
            sub["score"] = score[valid]
            sub["b_eff"] = b_per_row[valid] * c
            sub["viol"] = (sub["score"] > sub["b_eff"]).astype(int)
            for sym, g in sub.groupby("symbol"):
                v = g["viol"].to_numpy()
                if len(v) < 5:
                    continue
                _, p = met._lr_kupiec(v, tau)
                persym.append({"symbol": str(sym), "n": int(len(v)),
                                "viol_rate": float(v.mean()),
                                "kupiec_p": float(p), "tau": tau})
    return pd.DataFrame(pooled), pd.DataFrame(persym)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "factor_ret",
                "vix_fri_close", "gap_days"]
    ).reset_index(drop=True)

    n_pre = len(panel)
    panel = panel.dropna(subset=["gvz_fri_close", "move_fri_close"]).reset_index(drop=True)
    print(f"GVZ/MOVE coverage: {len(panel):,} / {n_pre:,} rows have both indices",
          flush=True)

    panel["regime_pub_VIX"] = (
        pd.Series("normal", index=panel.index, dtype=object)
    )
    panel.loc[panel["gap_days"] >= 4, "regime_pub_VIX"] = "long_weekend"
    panel.loc[_high_vol_flag_per_index(panel, "vix_fri_close").values,
              "regime_pub_VIX"] = "high_vol"

    panel["regime_pub_HYBRID"] = build_hybrid_regime(panel)

    # Tag agreement
    same = (panel["regime_pub_VIX"] == panel["regime_pub_HYBRID"])
    print(f"\nregime tag agreement: {same.mean()*100:.2f}% identical",
          flush=True)
    for sym in ASSET_INDEX_OVERRIDE:
        sub = panel[panel["symbol"] == sym]
        if len(sub) == 0:
            continue
        same_sub = (sub["regime_pub_VIX"] == sub["regime_pub_HYBRID"])
        flip_count = (~same_sub).sum()
        print(f"  {sym}: {flip_count}/{len(sub)} weekends ({100*flip_count/len(sub):.1f}%) "
              f"flip regime under {ASSET_INDEX_OVERRIDE[sym]}", flush=True)

    # Score under deployed σ̂ (σ̂ doesn't depend on regime — same column for both)
    panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HAT_HL_WEEKENDS)
    sigma_col = f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HAT_HL_WEEKENDS}"
    panel["sigma_hat_sym_pre_fri"] = panel[sigma_col]
    panel["score_lwc"] = compute_score_lwc(panel, scale_col="sigma_hat_sym_pre_fri")
    panel = panel[panel["score_lwc"].notna()].reset_index(drop=True)

    pooled_rows = []
    persym_rows = []
    for tag, regime_col in [("VIX_only_deployed", "regime_pub_VIX"),
                             ("hybrid_GVZ_MOVE", "regime_pub_HYBRID")]:
        print(f"\n=== {tag} ({regime_col}) ===", flush=True)
        qt, cb = fit_eval(panel, regime_col)
        oos = panel[panel["fri_ts"] >= SPLIT_DATE].copy()
        oos["regime_active"] = oos[regime_col].astype(str)
        df_pool, df_per = evaluate(oos, qt, cb, "regime_active")
        for r in df_pool.to_dict("records"):
            pooled_rows.append({"variant": tag, **r})
        for r in df_per.to_dict("records"):
            persym_rows.append({"variant": tag, **r})
        print(df_pool.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        n_pass = int((df_per["kupiec_p"] >= 0.05).sum())
        print(f"  per-symbol Kupiec at τ=0.95: {n_pass}/{len(df_per)} pass")
        # Highlight GLD and TLT specifically
        for s in ("GLD", "TLT"):
            r = df_per[df_per["symbol"] == s]
            if len(r):
                print(f"    {s}: viol_rate={r['viol_rate'].iloc[0]:.4f}  "
                      f"Kupiec p={r['kupiec_p'].iloc[0]:.4f}")

    pooled_df = pd.DataFrame(pooled_rows)
    persym_df = pd.DataFrame(persym_rows)
    out_pool = REPORTS / "tables" / "paper1_b4_regime_index_sensitivity.csv"
    out_per = REPORTS / "tables" / "paper1_b4_regime_index_sensitivity_per_symbol.csv"
    pooled_df.to_csv(out_pool, index=False)
    persym_df.to_csv(out_per, index=False)
    print(f"\nwrote {out_pool}\nwrote {out_per}")

    print("\n=== headline τ=0.95 cross-variant ===")
    pivot = pooled_df[pooled_df["target"] == 0.95].set_index("variant")[
        ["realised", "bump_c", "kupiec_p", "christoffersen_p",
         "half_width_bps_mean"]
    ]
    print(pivot.to_string(float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
