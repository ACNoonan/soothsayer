"""
Reviewer-tier diagnostics — Berkowitz, DQ, CRPS, exceedance magnitude.

Closes the four reviewer-likely gaps identified in the 2026-04-25 audit:
  1. Berkowitz (2001) joint LR test on inverse-normal-transformed PITs
  2. Engle-Manganelli (2004) Dynamic Quantile (DQ) test
  3. CRPS via piecewise-linear quantile-grid integration (Gneiting-Raftery)
  4. McNeil-Frey-style exceedance-magnitude diagnostic (simplified, no GPD fit)

Distinct from `run_extended_diagnostics.py` (which does D5 inter-anchor τ
sweep + D6 discrete served-band PIT). This script:
  - Re-serves OOS at a 19-point central-quantile τ grid → reconstructs the
    served-band CDF row-by-row → computes *continuous* PITs and CRPS
  - Re-serves OOS at the four headline τ anchors → computes per-row hits +
    band edges for DQ + exceedance magnitude

Outputs:
  reports/tables/v1b_oos_reviewer_diagnostics.csv     per-τ DQ + magnitude
  reports/tables/v1b_oos_berkowitz_crps.csv           pooled Berkowitz + CRPS
  reports/tables/v1b_oos_pit_continuous.csv           per-row continuous PITs + CRPS
  reports/figures/v1b_reliability_diagram.png         reliability + PIT histogram
"""

from __future__ import annotations

import time
from datetime import date

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2 as _chi2

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


SPLIT_DATE = date(2023, 1, 1)
PIT_TAU_GRID = tuple(round(0.05 * k, 2) for k in range(1, 20))   # 0.05..0.95 step 0.05
HEADLINE_TAUS = (0.68, 0.85, 0.95, 0.99)


def serve_central_band(oracle: Oracle, symbol: str, fri_ts, taus):
    out = {}
    for t in taus:
        try:
            pp = oracle.fair_value(symbol, fri_ts, target_coverage=t)
            out[t] = (float(pp.lower), float(pp.upper))
        except (ValueError, KeyError):
            out[t] = (float("nan"), float("nan"))
    return out


def build_cdf_anchors(band_by_tau: dict) -> tuple[np.ndarray, np.ndarray]:
    """Convert {τ: (L, U)} into ordered (q_value, F_level) arrays for interp.

    Central τ band [L, U] maps to F(L) = (1-τ)/2 and F(U) = (1+τ)/2.
    """
    qs, fs = [], []
    for t, (lo, hi) in band_by_tau.items():
        if not (np.isfinite(lo) and np.isfinite(hi)):
            continue
        qs.append(lo); fs.append((1.0 - t) / 2.0)
        qs.append(hi); fs.append((1.0 + t) / 2.0)
    if not qs:
        return np.array([]), np.array([])
    qs = np.array(qs); fs = np.array(fs)
    order = np.argsort(qs)
    return qs[order], fs[order]


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

    print(f"OOS panel: {len(panel_oos):,} rows in {panel_oos['fri_ts'].nunique()} weekends",
          flush=True)
    print(f"PIT τ grid: {len(PIT_TAU_GRID)} points "
          f"({PIT_TAU_GRID[0]}..{PIT_TAU_GRID[-1]}); "
          f"headline τ: {HEADLINE_TAUS}", flush=True)

    pit_rows = []
    anchor_rows = []
    t0 = time.time()
    for i, w in panel_oos.iterrows():
        bands_pit = serve_central_band(oracle, w["symbol"], w["fri_ts"], PIT_TAU_GRID)
        q_arr, f_arr = build_cdf_anchors(bands_pit)
        if len(q_arr) >= 2:
            pit = met.pit_from_quantile_grid(w["mon_open"], f_arr, q_arr)
            crps = met.crps_from_quantiles(w["mon_open"], f_arr, q_arr)
        else:
            pit = float("nan"); crps = float("nan")
        pit_rows.append({
            "symbol": w["symbol"], "fri_ts": w["fri_ts"], "regime_pub": w["regime_pub"],
            "mon_open": w["mon_open"], "fri_close": w["fri_close"],
            "pit": pit, "crps": crps,
        })

        bands_anchor = serve_central_band(oracle, w["symbol"], w["fri_ts"], HEADLINE_TAUS)
        for t in HEADLINE_TAUS:
            lo, hi = bands_anchor[t]
            inside = (np.isfinite(lo) and np.isfinite(hi)
                      and (w["mon_open"] >= lo) and (w["mon_open"] <= hi))
            half_width_bps = ((hi - lo) / 2.0 / w["fri_close"] * 1e4
                              if np.isfinite(lo) and np.isfinite(hi) else float("nan"))
            anchor_rows.append({
                "symbol": w["symbol"], "fri_ts": w["fri_ts"], "regime_pub": w["regime_pub"],
                "target": t, "lower": lo, "upper": hi,
                "mon_open": w["mon_open"], "fri_close": w["fri_close"],
                "inside": int(bool(inside)) if np.isfinite(lo) else 0,
                "half_width_bps": half_width_bps,
            })

        if (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            print(f"  [{i+1}/{len(panel_oos)}] elapsed={elapsed:.0f}s "
                  f"({(i+1)/elapsed:.1f} rows/s)", flush=True)

    served = pd.DataFrame(anchor_rows)
    pits = pd.DataFrame(pit_rows)
    print(f"\nServe complete in {time.time()-t0:.1f}s", flush=True)

    # === Per-τ DQ + magnitude ===
    diag_rows = []
    for t in HEADLINE_TAUS:
        sub = served[served["target"] == t].sort_values(["symbol", "fri_ts"])
        # DQ pooled across symbols (sum of independent χ² statistics).
        dq_total, dq_df_total = 0.0, 0
        for sym, g in sub.groupby("symbol"):
            v_g = (~g["inside"].astype(bool)).astype(int).values
            if len(v_g) < 10:
                continue
            res = met.dynamic_quantile_test(v_g, t, n_lags=4)
            if np.isfinite(res["dq"]):
                dq_total += res["dq"]; dq_df_total += res["df"]
        p_dq = (float(1.0 - _chi2.cdf(max(dq_total, 0.0), df=max(dq_df_total, 1)))
                if dq_df_total > 0 else float("nan"))
        mag = met.exceedance_magnitude(
            sub["mon_open"].values, sub["lower"].values,
            sub["upper"].values, sub["fri_close"].values,
        )
        diag_rows.append({
            "target": t, "n": int(len(sub)),
            "dq_pooled": dq_total, "dq_df": dq_df_total, "p_dq": p_dq,
            **mag,
        })
    diag = pd.DataFrame(diag_rows)

    # === Pooled Berkowitz + CRPS summary ===
    bz = met.berkowitz_test(pits["pit"].dropna().values)
    crps_mean = float(pits["crps"].dropna().mean())
    crps_median = float(pits["crps"].dropna().median())
    pit_summary = pd.DataFrame([{
        "n_pits": bz["n"],
        "berkowitz_lr": bz["lr"], "berkowitz_p": bz["p_value"],
        "rho_hat": bz.get("rho_hat", float("nan")),
        "mean_z": bz.get("mean_z", float("nan")),
        "var_z": bz.get("var_z", float("nan")),
        "mean_crps": crps_mean, "median_crps": crps_median,
    }])

    out_dir = REPORTS / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    diag.to_csv(out_dir / "v1b_oos_reviewer_diagnostics.csv", index=False)
    pit_summary.to_csv(out_dir / "v1b_oos_berkowitz_crps.csv", index=False)
    pits.to_csv(out_dir / "v1b_oos_pit_continuous.csv", index=False)

    # === Reliability diagram (figure) ===
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: reliability (claimed vs realised) at the central-quantile τ grid
    rel_taus = list(PIT_TAU_GRID) + list(HEADLINE_TAUS)
    rel_taus = sorted(set(rel_taus))
    rel_rows = []
    for t in rel_taus:
        sub_anchor = served[served["target"] == t]
        if not sub_anchor.empty:
            rel_rows.append({"tau": t, "realised": float(sub_anchor["inside"].mean()),
                             "is_anchor": t in HEADLINE_TAUS, "source": "anchor"})
            continue
        # PIT-grid τ — not yet evaluated as a band hit; compute from PIT distribution
        # Pr(realised inside central-τ band) = Pr((1-τ)/2 < PIT < (1+τ)/2)
        pit_vals = pits["pit"].dropna().values
        in_band = ((pit_vals > (1 - t) / 2) & (pit_vals < (1 + t) / 2)).mean()
        rel_rows.append({"tau": t, "realised": float(in_band),
                         "is_anchor": False, "source": "pit"})
    rel_df = pd.DataFrame(rel_rows).sort_values("tau")
    axes[0].plot([0, 1], [0, 1], "k--", alpha=0.5, label="perfect calibration")
    rel_pit = rel_df[rel_df["source"] == "pit"]
    rel_anc = rel_df[rel_df["source"] == "anchor"]
    axes[0].plot(rel_pit["tau"], rel_pit["realised"], "o-", color="C0",
                 markersize=5, alpha=0.7, label=f"central-τ grid ({len(PIT_TAU_GRID)} pts)")
    axes[0].plot(rel_anc["tau"], rel_anc["realised"], "s", color="C3",
                 markersize=12, label=f"anchor τ ({len(HEADLINE_TAUS)} pts)", zorder=5)
    axes[0].set_xlabel(r"Consumer target $\tau$")
    axes[0].set_ylabel("Realised coverage on OOS 2023+")
    axes[0].set_title("Reliability diagram — served-band Oracle\n"
                      f"OOS panel: {len(panel_oos):,} rows × {len(panel_oos['fri_ts'].unique())} weekends")
    axes[0].set_xlim(0, 1); axes[0].set_ylim(0, 1)
    axes[0].grid(True, alpha=0.3); axes[0].legend(loc="lower right")

    # Right: continuous-PIT histogram
    pit_vals = pits["pit"].dropna().values
    axes[1].hist(pit_vals, bins=20, edgecolor="black", alpha=0.7, color="C0")
    axes[1].axhline(len(pit_vals) / 20, color="red", linestyle="--",
                    label=f"uniform expectation ({len(pit_vals)/20:.0f})")
    axes[1].set_xlabel("Continuous PIT (interpolated from served-band quantile grid)")
    axes[1].set_ylabel("Count")
    bz_str = (f"Berkowitz LR = {bz['lr']:.2f}, p = {bz['p_value']:.3f}"
              if np.isfinite(bz["lr"]) else "Berkowitz: NaN")
    axes[1].set_title(f"Served-band PIT histogram\n{bz_str} "
                      f"({'pass' if bz['p_value'] > 0.05 else 'reject'} at α=0.05)")
    axes[1].set_xlim(0, 1)
    axes[1].grid(True, alpha=0.3); axes[1].legend()

    fig.tight_layout()
    fig_dir = REPORTS / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig_path = fig_dir / "v1b_reliability_diagram.png"
    fig.savefig(fig_path, dpi=140)
    plt.close(fig)

    print()
    print("=" * 80)
    print("Per-τ DQ + exceedance magnitude")
    print("=" * 80)
    print(diag.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print("=" * 80)
    print("Pooled Berkowitz + CRPS")
    print("=" * 80)
    print(pit_summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()
    print(f"Wrote {out_dir / 'v1b_oos_reviewer_diagnostics.csv'}")
    print(f"Wrote {out_dir / 'v1b_oos_berkowitz_crps.csv'}")
    print(f"Wrote {out_dir / 'v1b_oos_pit_continuous.csv'}")
    print(f"Wrote {fig_path}")


if __name__ == "__main__":
    main()
