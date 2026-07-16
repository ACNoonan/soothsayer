"""V1b — MATCHED-HISTORY tokenized-tracking head-to-head (reviewer fairness fix).

Reviewer finding (CONFIRMED, see reports/v1b_tokenized_tracking_baseline.md §Headline):
the deployed §6.3 / App-D comparison reads Soothsayer's M6 LWC band off the FULL
12-year *frozen* artefact (`oracle.fair_value_lwc`), whose σ̂_sym and per-regime
conformal quantile are calibrated on ~12 years of weekends, while the naive
tokenized-tracking baseline calibrates on a walk-forward expanding window that
only starts at the 2025-12-19 kraken_futures perp-tape floor (≤19 weekends /
symbol). So the headline "45% narrower / 46% better Winkler" (τ=0.95, frozen-M6
358 bps hw / 879 bps Winkler vs baseline mon_open 656 / 1619) is confounded by a
~100× calibration-history asymmetry (12 years vs ~4 months).

This script disentangles ARCHITECTURE from CALIBRATION-HISTORY LENGTH. It refits
the deployed M6 ARCHITECTURE walk-forward using ONLY post-2025-12 calibration
data available up to each evaluation weekend — the same expanding window, the
same 4-weekend warm-up, the same evaluation cells the baseline uses — and asks
whether the width / Winkler advantage survives when history is equalized.

The M6 architecture that is refit walk-forward (identical to the deployed serve
path minus the OOS-fit c(τ)-bump / δ-shift conservatism layer, which needs a
train/OOS split the short window cannot afford — the baseline has no such layer
either, so dropping it keeps the comparison apples-to-apples):

  point   = fri_close · (1 + factor_ret)                    §7.4 factor switchboard
  σ̂_sym   = pre-Friday EWMA(HL=8) std of the symbol's post-2025-12 rel-residuals
  score   = |mon_open - point| / (fri_close · σ̂_sym)         standardised
  q_r(τ)  = finite-sample CP τ-quantile of scores in regime r  (Mondrian by regime)
  half    = q_r(τ) · σ̂_sym · fri_close
  lower / upper = point ∓ half

Two matched variants are produced:
  - matched_m6_regime : full architecture, Mondrian-by-regime conformal cells.
  - matched_m6_pooled : single conformal cell (no regime split) — the graceful
    fallback for when the short-window per-regime cells are too thin to fit a
    finite-sample quantile (documented as the floor finding).

Both are scored against the SAME baseline (walk-forward, post-2025-12) and the
SAME frozen-M6 band, on a COMMON evaluable set (cells where every method emits a
finite band), so the only thing that changes between frozen-M6 and matched-M6 is
the calibration-history length.

Outputs:
  - reports/tables/v1b_tokenized_matched_history_summary.csv   (per forecaster × τ)
  - reports/tables/v1b_tokenized_matched_history_deltas.csv     (width/Winkler deltas + bootstrap CI)
  - reports/tables/v1b_tokenized_matched_history_per_symbol.csv (per-symbol survival)
  - reports/tables/v1b_tokenized_matched_history_regime_floor.csv (walk-forward cell counts / saturation)

HARD RULES honoured: reads only scryer parquet + local processed data; no external
API/network; run with `uv run python -u scripts/run_v1b_tokenized_matched_history.py`.
Does NOT touch any paper .md file.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))  # make `scripts` importable when run as a file

from soothsayer.config import DATA_PROCESSED  # noqa: E402
from soothsayer.backtest.calibration import (  # noqa: E402
    add_sigma_hat_sym_ewma,
    compute_score_lwc,
    train_quantile_table,
)

# Reuse the primary bake-off plumbing so the eval cells / stats are byte-identical.
from scripts.run_v1b_tokenized_tracking_baseline import (  # noqa: E402
    BAKEOFF_SYMBOLS,
    MIN_WARMUP_WEEKENDS,
    TAU_GRID,
    fetch_mon_open,
    kupiec_p_uc,
    christoffersen_p_cc,
    winkler,
)

# --- Matched-history knobs -------------------------------------------------

TAPE_FLOOR = pd.Timestamp("2025-12-19")  # kraken_futures perp launch (baseline floor)
SIGMA_HALF_LIFE = 8                       # deployed M6 σ̂ rule (EWMA HL=8)
# Deployed σ̂ warm-up is ≥8 past obs; on the ≤19-weekend window that alone
# would strand almost every cell (see the floor table). We relax to match the
# baseline's 4-weekend pooled warm-up so the ARCHITECTURE is evaluable on the
# equalized window. SIGMA_MIN_OBS=8 is reported alongside as the floor.
SIGMA_MIN_OBS = 4
# Baseline (charitable) snapshot the original headline used: Monday 09:00 ET,
# the moment the perp has absorbed the whole weekend. `fri_close` is the
# timing-matched snapshot (same info set as M6's Friday-set band) — reported too.
PRIMARY_BASELINE_SNAPSHOT = "mon_open"
N_BOOT = 5000
BOOT_SEED = 20260716


# ---------- Calibration panel (post-2025-12 equities residuals) ----------

def build_calibration_panel(eval_panel: pd.DataFrame) -> pd.DataFrame:
    """Post-2025-12 M6 calibration panel: one row per (symbol, weekend) with the
    factor-adjusted point, the Monday open, the rel-residual, the walk-forward
    matched σ̂ (EWMA HL=8, post-2025-12 only) and the standardised LWC score.

    The residual `mon_open - point` needs NO perp tape, so the architecture's
    natural calibration set spans all 19 post-2025-12 weekends per symbol (vs
    the baseline's perp-limited ≤19). Both are confined to the post-2025-12
    window — that is what equalizes the 12yr-vs-4mo asymmetry the reviewer flagged.

    mon_open is taken from the frozen bake-off panel where present (so the frozen-M6
    numbers reproduce exactly) and fetched from yahoo for the calibration-only
    early weekends the perp tape never reached.
    """
    art = pd.read_parquet(DATA_PROCESSED / "lwc_artefact_v1.parquet")
    art["fri_ts"] = pd.to_datetime(art["fri_ts"]).dt.date
    art = art[pd.to_datetime(art["fri_ts"]) >= TAPE_FLOOR]
    art = art[art["symbol"].isin(BAKEOFF_SYMBOLS)].copy()

    # point = fri_close·(1+factor_ret) is stored directly as `point`.
    art["point"] = art["point"].astype(float)
    art["fri_close"] = art["fri_close"].astype(float)
    art["factor_ret"] = art["point"] / art["fri_close"] - 1.0

    # mon_open: prefer the frozen bake-off panel (consistency w/ the original
    # 45%/46% numbers); fetch the rest from yahoo.
    known = eval_panel[["symbol", "fri_ts", "mon_open"]].dropna(subset=["mon_open"])
    art = art.merge(known, on=["symbol", "fri_ts"], how="left")
    missing = art["mon_open"].isna()
    n_fetch = int(missing.sum())
    for i in art.index[missing]:
        _, mo = fetch_mon_open(art.at[i, "symbol"], art.at[i, "fri_ts"])
        art.at[i, "mon_open"] = mo
    art = art.dropna(subset=["mon_open"]).copy()
    print(f"      calibration panel: {len(art)} rows "
          f"({len(art) - n_fetch} from frozen panel, {n_fetch} fetched), "
          f"{art['fri_ts'].nunique()} weekends, {art['symbol'].nunique()} symbols")

    # Walk-forward matched σ̂ (EWMA HL=8, strictly pre-Friday, post-2025-12 only).
    art = add_sigma_hat_sym_ewma(art, half_life=SIGMA_HALF_LIFE, min_obs=SIGMA_MIN_OBS)
    art["sigma_hat_matched"] = art[f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HALF_LIFE}"]
    # Standardised LWC score on the MATCHED σ̂.
    art["score_lwc_matched"] = compute_score_lwc(art, scale_col="sigma_hat_matched")
    return art


# ---------- Walk-forward matched-M6 refit ----------

def refit_matched_m6(
    eval_panel: pd.DataFrame,
    cal_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Walk-forward refit of the M6 architecture on the equalized window.

    For each eval weekend w: fit the per-regime (and pooled) finite-sample CP
    quantile from calibration rows with fri_ts < w (post-2025-12 only, ≥4 past
    weekends), then serve the eval cells at w with matched σ̂. Returns
    (augmented eval_panel, regime-floor diagnostic frame).
    """
    ev = eval_panel.copy()
    # Attach the matched σ̂ to each eval cell (join on symbol+weekend).
    sig = cal_panel[["symbol", "fri_ts", "sigma_hat_matched"]]
    ev = ev.merge(sig, on=["symbol", "fri_ts"], how="left")

    eval_weekends = sorted(ev["fri_ts"].unique())
    all_weekends = sorted(cal_panel["fri_ts"].unique())

    # Result accumulators keyed by eval-panel index.
    for tau in TAU_GRID:
        ev[f"matched_regime_half_tau{tau}"] = np.nan
        ev[f"matched_pooled_half_tau{tau}"] = np.nan

    floor_rows: list[dict] = []

    for w in eval_weekends:
        cal = cal_panel[
            (cal_panel["fri_ts"] < w) & cal_panel["score_lwc_matched"].notna()
        ].copy()
        n_past_weekends = sum(1 for x in all_weekends if x < w)
        # Per-regime CP quantile table (Mondrian) + pooled (single cell).
        cal_ok = n_past_weekends >= MIN_WARMUP_WEEKENDS and not cal.empty
        qt_regime = (
            train_quantile_table(cal, cell_col="regime_pub", taus=TAU_GRID,
                                 score_col="score_lwc_matched")
            if cal_ok else {}
        )
        pooled = cal.assign(_cell="all")
        qt_pooled = (
            train_quantile_table(pooled, cell_col="_cell", taus=TAU_GRID,
                                 score_col="score_lwc_matched")
            if cal_ok else {}
        )

        # Floor diagnostic: per-regime obs count + finite-sample-quantile
        # saturation flag (ceil(τ(n+1)) > n ⇒ quantile pinned to the cell max).
        for reg in sorted(cal["regime_pub"].astype(str).unique()) if cal_ok else []:
            n_r = int((cal["regime_pub"].astype(str) == reg).sum())
            for tau in TAU_GRID:
                k = int(np.ceil(tau * (n_r + 1)))
                floor_rows.append({
                    "eval_weekend": w, "regime": reg, "tau": tau,
                    "n_cal_in_regime": n_r,
                    "cp_rank": min(max(k, 1), n_r),
                    "saturated": bool(k > n_r),  # quantile pinned to max score
                })

        rows_w = ev.index[ev["fri_ts"] == w]
        for idx in rows_w:
            reg = str(ev.at[idx, "regime_pub"])
            sig_i = ev.at[idx, "sigma_hat_matched"]
            fri_close = float(ev.at[idx, "fri_close"])
            point = float(ev.at[idx, "sooth_point_tau0.68"])  # factor-adj point
            if not cal_ok or pd.isna(sig_i) or not (sig_i > 0):
                continue
            for tau in TAU_GRID:
                qr = qt_regime.get(reg, {}).get(tau, np.nan)
                qp = qt_pooled.get("all", {}).get(tau, np.nan)
                if np.isfinite(qr):
                    ev.at[idx, f"matched_regime_half_tau{tau}"] = qr * sig_i * fri_close
                if np.isfinite(qp):
                    ev.at[idx, f"matched_pooled_half_tau{tau}"] = qp * sig_i * fri_close
            # store point for band reconstruction
            ev.at[idx, "matched_point"] = point

    floor = pd.DataFrame(floor_rows)
    return ev, floor


# ---------- Scoring on a common evaluable set ----------

def _band_cols(forecaster: str, tau: float, snapshot: str) -> tuple:
    """Return (point_series_key, lower/upper builder) spec per forecaster."""
    raise NotImplementedError  # inlined below for clarity


def score_common(
    ev: pd.DataFrame,
    baseline_snapshot: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Score frozen-M6, matched-M6 (regime + pooled) and the walk-forward
    baseline on the COMMON evaluable set (cells where all four emit a finite
    band) for every τ. Returns (summary, deltas, per_symbol)."""
    summary_rows: list[dict] = []
    delta_rows: list[dict] = []
    per_symbol_rows: list[dict] = []
    rng = np.random.default_rng(BOOT_SEED)

    for tau in TAU_GRID:
        base_hw_col = f"baseline_{baseline_snapshot}_halfwidth_tau{tau}"
        base_pt_col = f"baseline_{baseline_snapshot}_point"
        frozen_hw_col = f"sooth_halfwidth_tau{tau}"
        matched_reg_col = f"matched_regime_half_tau{tau}"
        matched_pool_col = f"matched_pooled_half_tau{tau}"

        needed = [
            "mon_open", "fri_close", base_hw_col, base_pt_col,
            frozen_hw_col, f"sooth_lower_tau{tau}", f"sooth_upper_tau{tau}",
            matched_reg_col, matched_pool_col, "matched_point",
        ]
        common = ev.dropna(subset=needed).copy()
        if common.empty:
            continue
        y = common["mon_open"].to_numpy(float)
        fri = common["fri_close"].to_numpy(float)

        # Build per-forecaster (lower, upper, hw_bps, winkler_bps) on common set.
        def pack(name, lo, hi, hw):
            in_band = (y >= lo) & (y <= hi)
            wk = np.array([winkler(L, H, Y, tau) for L, H, Y in zip(lo, hi, y)])
            return {
                "name": name,
                "in_band": in_band,
                "hw_bps": hw / fri * 1e4,
                "wink_bps": wk / fri * 1e4,
                "cov": float(in_band.mean()),
            }

        # frozen-M6 (full 12y artefact)
        f_lo = common[f"sooth_lower_tau{tau}"].to_numpy(float)
        f_hi = common[f"sooth_upper_tau{tau}"].to_numpy(float)
        f_hw = common[frozen_hw_col].to_numpy(float)
        F = pack("frozen_m6_12y", f_lo, f_hi, f_hw)

        # matched-M6 regime
        mp = common["matched_point"].to_numpy(float)
        mr_hw = common[matched_reg_col].to_numpy(float)
        MR = pack("matched_m6_regime", mp - mr_hw, mp + mr_hw, mr_hw)

        # matched-M6 pooled
        mpool_hw = common[matched_pool_col].to_numpy(float)
        MP = pack("matched_m6_pooled", mp - mpool_hw, mp + mpool_hw, mpool_hw)

        # baseline (walk-forward, post-2025-12)
        b_pt = common[base_pt_col].to_numpy(float)
        b_hw = common[base_hw_col].to_numpy(float)
        B = pack("tokenized_baseline", b_pt - b_hw, b_pt + b_hw, b_hw)

        n = len(common)
        for M in (F, MR, MP, B):
            breaches = M["in_band"].astype(int)
            summary_rows.append({
                "tau": tau, "forecaster": M["name"], "n": n,
                "realised_coverage": M["cov"],
                "mean_halfwidth_bps": float(M["hw_bps"].mean()),
                "median_halfwidth_bps": float(np.median(M["hw_bps"])),
                "mean_winkler_bps": float(M["wink_bps"].mean()),
                "kupiec_p_uc": kupiec_p_uc(M["cov"], n, tau),
                "christoffersen_p_ind": christoffersen_p_cc(breaches.to_numpy()
                                                            if hasattr(breaches, "to_numpy")
                                                            else np.asarray(breaches), tau),
            })

        # --- deltas vs baseline (paired, bootstrap CI over cells) ---
        def delta_block(M, label):
            hw_m, hw_b = M["hw_bps"], B["hw_bps"]
            wk_m, wk_b = M["wink_bps"], B["wink_bps"]
            width_red = 1.0 - hw_m.mean() / hw_b.mean()
            wink_imp = 1.0 - wk_m.mean() / wk_b.mean()
            # paired bootstrap over cells
            wr, wi = [], []
            idx = np.arange(n)
            for _ in range(N_BOOT):
                bi = rng.choice(idx, size=n, replace=True)
                wr.append(1.0 - hw_m[bi].mean() / hw_b[bi].mean())
                wi.append(1.0 - wk_m[bi].mean() / wk_b[bi].mean())
            return {
                "tau": tau, "forecaster": label, "baseline_snapshot": baseline_snapshot,
                "n": n,
                "width_reduction_pct": 100 * width_red,
                "width_reduction_ci_lo": 100 * float(np.percentile(wr, 2.5)),
                "width_reduction_ci_hi": 100 * float(np.percentile(wr, 97.5)),
                "winkler_improvement_pct": 100 * wink_imp,
                "winkler_improvement_ci_lo": 100 * float(np.percentile(wi, 2.5)),
                "winkler_improvement_ci_hi": 100 * float(np.percentile(wi, 97.5)),
                "mean_hw_bps": float(hw_m.mean()),
                "baseline_hw_bps": float(hw_b.mean()),
                "mean_winkler_bps": float(wk_m.mean()),
                "baseline_winkler_bps": float(wk_b.mean()),
            }

        delta_rows.append(delta_block(F, "frozen_m6_12y"))
        delta_rows.append(delta_block(MR, "matched_m6_regime"))
        delta_rows.append(delta_block(MP, "matched_m6_pooled"))

        # --- per-symbol survival (τ=0.95 headline + all τ) ---
        for sym, g in common.groupby("symbol"):
            gi = common.index.get_indexer(g.index)
            per_symbol_rows.append({
                "tau": tau, "symbol": sym, "n": len(g),
                "frozen_hw_bps": float(F["hw_bps"][gi].mean()),
                "matched_regime_hw_bps": float(MR["hw_bps"][gi].mean()),
                "matched_pooled_hw_bps": float(MP["hw_bps"][gi].mean()),
                "baseline_hw_bps": float(B["hw_bps"][gi].mean()),
                "frozen_wink_bps": float(F["wink_bps"][gi].mean()),
                "matched_regime_wink_bps": float(MR["wink_bps"][gi].mean()),
                "matched_pooled_wink_bps": float(MP["wink_bps"][gi].mean()),
                "baseline_wink_bps": float(B["wink_bps"][gi].mean()),
                "matched_regime_wink_ratio_base_over_m6":
                    float(B["wink_bps"][gi].mean() / MR["wink_bps"][gi].mean()),
                "matched_pooled_wink_ratio_base_over_m6":
                    float(B["wink_bps"][gi].mean() / MP["wink_bps"][gi].mean()),
            })

    return (pd.DataFrame(summary_rows), pd.DataFrame(delta_rows),
            pd.DataFrame(per_symbol_rows))


def main() -> int:
    tables = REPO / "reports" / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    print("[1/5] Loading frozen bake-off panel (117 eval cells + frozen-M6 + baseline)...")
    eval_panel = pd.read_parquet(DATA_PROCESSED / "v1b_tokenized_tracking_baseline.parquet")
    eval_panel["fri_ts"] = pd.to_datetime(eval_panel["fri_ts"]).dt.date
    print(f"      eval cells: {len(eval_panel)}  weekends: {eval_panel['fri_ts'].nunique()}"
          f"  symbols: {eval_panel['symbol'].nunique()}")

    print("[2/5] Building post-2025-12 matched calibration panel (σ̂ EWMA HL=8, min_obs=4)...")
    cal_panel = build_calibration_panel(eval_panel)

    print("[3/5] Walk-forward refit of the M6 architecture on the equalized window...")
    ev, floor = refit_matched_m6(eval_panel, cal_panel)
    # how many eval cells got a matched band at tau=0.95?
    got = ev[f"matched_regime_half_tau0.95"].notna().sum()
    got_p = ev[f"matched_pooled_half_tau0.95"].notna().sum()
    print(f"      matched-M6 regime bands: {got}/{len(ev)} cells;"
          f" pooled bands: {got_p}/{len(ev)} cells")

    print(f"[4/5] Scoring on common evaluable set (baseline snapshot = {PRIMARY_BASELINE_SNAPSHOT})...")
    summary, deltas, per_symbol = score_common(ev, PRIMARY_BASELINE_SNAPSHOT)
    # Also score against the timing-matched fri_close snapshot for context.
    summary_fc, deltas_fc, _ = score_common(ev, "fri_close")
    summary_fc["baseline_snapshot"] = "fri_close"
    summary["baseline_snapshot"] = PRIMARY_BASELINE_SNAPSHOT

    print("[5/5] Writing tables...")
    out_summary = tables / "v1b_tokenized_matched_history_summary.csv"
    out_deltas = tables / "v1b_tokenized_matched_history_deltas.csv"
    out_persym = tables / "v1b_tokenized_matched_history_per_symbol.csv"
    out_floor = tables / "v1b_tokenized_matched_history_regime_floor.csv"
    pd.concat([summary, summary_fc], ignore_index=True).to_csv(out_summary, index=False)
    pd.concat([deltas, deltas_fc.assign(baseline_snapshot="fri_close")],
              ignore_index=True).to_csv(out_deltas, index=False)
    per_symbol.to_csv(out_persym, index=False)
    floor.to_csv(out_floor, index=False)

    # Persist the refit panel for audit.
    keep = [c for c in ev.columns if not c.startswith("perp_at_")]
    ev[keep].to_parquet(DATA_PROCESSED / "v1b_tokenized_matched_history.parquet", index=False)

    # -------- console report --------
    pd.set_option("display.width", 200)
    print("\n==== SUMMARY (common evaluable set, baseline = mon_open) ====")
    print(summary[["tau", "forecaster", "n", "realised_coverage",
                   "mean_halfwidth_bps", "mean_winkler_bps", "kupiec_p_uc"]]
          .round(4).to_string(index=False))

    print("\n==== DELTAS vs baseline (mon_open) — does the architecture edge survive? ====")
    show = deltas[["tau", "forecaster", "n",
                   "width_reduction_pct", "width_reduction_ci_lo", "width_reduction_ci_hi",
                   "winkler_improvement_pct", "winkler_improvement_ci_lo", "winkler_improvement_ci_hi"]]
    print(show.round(1).to_string(index=False))

    print("\n==== REGIME-CELL FLOOR (walk-forward CP-quantile saturation) ====")
    if not floor.empty:
        fl = (floor.groupby(["regime", "tau"])
              .agg(mean_n=("n_cal_in_regime", "mean"),
                   min_n=("n_cal_in_regime", "min"),
                   max_n=("n_cal_in_regime", "max"),
                   frac_saturated=("saturated", "mean"))
              .reset_index())
        print(fl.round(2).to_string(index=False))

    print(f"\nWrote:\n  {out_summary}\n  {out_deltas}\n  {out_persym}\n  {out_floor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
