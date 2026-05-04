"""
Editorial prework for the Paper 1 final pass — three short re-runs.

Item 3   GARCH at matched 95% coverage. The §6.4.2 head-to-head reports
         GARCH(1,1) at *nominal* τ=0.95 realising 0.9254 with hw 322.2 bps;
         a "9% sharper at τ=0.95" framing is unfair because GARCH delivers
         a different point on the coverage-width curve. Re-fit GARCH at a
         fine τ-nominal grid; find the smallest τ' such that realised ≥ 0.95
         on the OOS slice; report the matched-coverage half-width vs M5.

Item 11  MSTR-removed sensitivity. The §5.4 factor-switchboard pivot
         (MSTR ES=F → BTC-USD on 2020-08-01) is a discretionary modeling
         choice. Re-fit M5 on a 9-symbol panel with MSTR removed entirely
         and report the Δ on pooled τ=0.95 realised coverage and mean
         half-width. If |Δ| ≤ 0.5pp / 2%, the §5.4 pivot is benign and
         a footnote suffices.

Item 12  Realised-move tertile stratification. §9.1 declares an 80%
         empirical ceiling on shock-tertile coverage at nominal τ=0.95;
         the §6.3 headline pooled 0.950 is not stratified. Stratify the
         deployed M5 τ=0.95 realised coverage by `realized_bucket` (calm
         / normal / shock tertiles of |z-score|). Closes the loop between
         the §6.3 headline and the §9.1 ceiling.

Outputs
-------
  reports/tables/v1b_prework_garch_matched.csv
  reports/tables/v1b_prework_mstr_sensitivity.csv
  reports/tables/v1b_prework_tertile.csv
"""

from __future__ import annotations

import warnings
from datetime import date

import numpy as np
import pandas as pd
from arch import arch_model
from scipy.stats import norm

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    compute_score,
    fit_c_bump_schedule,
    serve_bands,
    train_quantile_table,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)


# =================================================================== Item 3


def fit_per_symbol_garch(panel: pd.DataFrame) -> pd.DataFrame:
    """Per-symbol GARCH(1,1) — same construction as run_v1b_garch_baseline.py.
    Recursive σ̂_t over OOS using fitted (μ, ω, α, β) on the train side."""
    rows = []
    for sym, g in panel.groupby("symbol"):
        g = g.sort_values("fri_ts").reset_index(drop=True).copy()
        g["log_ret"] = np.log(g["mon_open"] / g["fri_close"])
        train = g[g["fri_ts"] < SPLIT_DATE].dropna(subset=["log_ret"])
        if len(train) < 50:
            continue
        scale = 100.0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = arch_model(train["log_ret"].values * scale,
                             mean="Constant", vol="GARCH", p=1, q=1,
                             dist="normal").fit(disp="off", show_warning=False)
        mu = float(res.params.get("mu", 0.0)) / scale
        omega = float(res.params["omega"]) / (scale ** 2)
        alpha = float(res.params["alpha[1]"])
        beta = float(res.params["beta[1]"])

        sigma2 = np.empty(len(g)); sigma2[:] = np.nan
        sigma2[0] = omega / max(1.0 - alpha - beta, 1e-6)
        for i in range(1, len(g)):
            r_prev = g["log_ret"].iloc[i - 1]
            if not np.isfinite(r_prev):
                sigma2[i] = sigma2[i - 1]; continue
            sigma2[i] = (omega + alpha * (r_prev - mu) ** 2
                         + beta * sigma2[i - 1])
        sigma_hat = np.sqrt(sigma2)
        for i, row in g.iterrows():
            rows.append({
                "symbol": sym, "fri_ts": row["fri_ts"],
                "fri_close": float(row["fri_close"]),
                "mon_open": float(row["mon_open"]),
                "mu": mu, "sigma_hat": float(sigma_hat[i]),
            })
    return pd.DataFrame(rows)


def garch_realised_at(forecasts: pd.DataFrame, tau: float) -> tuple[float, float]:
    """Realised coverage and mean half-width of a GARCH(1,1) ±z_α σ̂ band
    at nominal `tau`."""
    z = norm.ppf(0.5 + tau / 2.0)
    fri = forecasts["fri_close"].values
    mon = forecasts["mon_open"].values
    mu = forecasts["mu"].values
    sig = forecasts["sigma_hat"].values
    lower = fri * np.exp(mu - z * sig)
    upper = fri * np.exp(mu + z * sig)
    inside = (mon >= lower) & (mon <= upper)
    hw_bps = ((upper - lower) / 2 / fri * 1e4).mean()
    return float(inside.mean()), float(hw_bps)


def run_item3(panel: pd.DataFrame) -> pd.DataFrame:
    """Find the GARCH τ-nominal that delivers realised ≥ 0.95 on the OOS
    slice, then report matched-coverage width vs M5."""
    print("\n[Item 3] GARCH matched-coverage sweep …", flush=True)
    forecasts = fit_per_symbol_garch(panel)
    forecasts["fri_ts"] = pd.to_datetime(forecasts["fri_ts"]).dt.date
    fc_oos = (forecasts[forecasts["fri_ts"] >= SPLIT_DATE]
              .dropna(subset=["sigma_hat"])
              .reset_index(drop=True))
    print(f"  {len(fc_oos):,} OOS forecasts", flush=True)

    # Sweep nominal τ on a fine grid; find smallest τ' delivering ≥ 0.95.
    grid = np.round(np.arange(0.950, 0.9991, 0.001), 4)
    rows = []
    matched_tau = None
    matched_hw = None
    for tau in grid:
        cov, hw = garch_realised_at(fc_oos, float(tau))
        rows.append({"method": "GARCH(1,1)",
                     "tau_nominal": float(tau),
                     "realised": cov, "half_width_bps": hw})
        if matched_tau is None and cov >= 0.95:
            matched_tau = float(tau); matched_hw = hw

    # M5 deployed — already at τ=0.95 the realised is 0.9503, hw 354.6.
    rows.append({"method": "M5_deployed",
                 "tau_nominal": 0.95, "realised": 0.9503,
                 "half_width_bps": 354.6})

    df = pd.DataFrame(rows)
    if matched_tau is not None:
        m5_hw = 354.6
        ratio = matched_hw / m5_hw
        print(f"  GARCH matches 0.95 realised at τ_nominal = {matched_tau:.3f}  "
              f"(hw = {matched_hw:.1f} bps; M5 = {m5_hw:.1f} bps; "
              f"GARCH/M5 = {ratio:.3f}×)", flush=True)
    else:
        max_cov = df[df["method"] == "GARCH(1,1)"]["realised"].max()
        print(f"  GARCH never reaches 0.95 on this grid; max realised = {max_cov:.4f}",
              flush=True)
    out_path = REPORTS / "tables" / "v1b_prework_garch_matched.csv"
    df.to_csv(out_path, index=False)
    print(f"  wrote {out_path}", flush=True)
    return df


# =================================================================== Item 11


def run_item11(panel: pd.DataFrame) -> pd.DataFrame:
    """Re-fit M5 on a 9-symbol panel with MSTR removed and report pooled
    τ=0.95 realised + mean half-width vs the 10-symbol deployed."""
    print("\n[Item 11] MSTR-removed sensitivity …", flush=True)

    panel_full = panel.copy()
    panel_no_mstr = panel[panel["symbol"] != "MSTR"].copy().reset_index(drop=True)
    print(f"  full panel:        {len(panel_full):,} rows ({panel_full['symbol'].nunique()} syms)")
    print(f"  MSTR-removed:      {len(panel_no_mstr):,} rows ({panel_no_mstr['symbol'].nunique()} syms)")

    rows = []
    for label, p in [("M5_full_panel_10sym", panel_full),
                     ("M5_no_MSTR_9sym", panel_no_mstr)]:
        train = p[p["fri_ts"] < SPLIT_DATE].dropna(subset=["score"])
        oos = (p[p["fri_ts"] >= SPLIT_DATE]
               .dropna(subset=["score"])
               .sort_values(["symbol", "fri_ts"])
               .reset_index(drop=True))
        qt = train_quantile_table(train, cell_col="regime_pub", taus=DEFAULT_TAUS)
        cb = fit_c_bump_schedule(oos, qt, cell_col="regime_pub", taus=DEFAULT_TAUS)
        bounds = serve_bands(oos, qt, cb, cell_col="regime_pub", taus=DEFAULT_TAUS)
        for tau in DEFAULT_TAUS:
            b = bounds[tau]
            inside = ((oos["mon_open"] >= b["lower"]) &
                      (oos["mon_open"] <= b["upper"]))
            v = (~inside).astype(int).to_numpy()
            lr, p_val = met._lr_kupiec(v, tau)
            rows.append({
                "panel": label, "n_train": int(len(train)),
                "n_oos": int(len(oos)), "tau": tau,
                "realised": float(inside.mean()),
                "half_width_bps": float(((b["upper"] - b["lower"]) / 2 /
                                         oos["fri_close"] * 1e4).mean()),
                "kupiec_lr": float(lr), "kupiec_p": float(p_val),
                "c_bump": float(cb[tau]),
                "q_normal": qt.get("normal", {}).get(tau, np.nan),
                "q_long_weekend": qt.get("long_weekend", {}).get(tau, np.nan),
                "q_high_vol": qt.get("high_vol", {}).get(tau, np.nan),
            })

    df = pd.DataFrame(rows)
    out_path = REPORTS / "tables" / "v1b_prework_mstr_sensitivity.csv"
    df.to_csv(out_path, index=False)
    print(f"  wrote {out_path}", flush=True)

    # Console summary at τ=0.95.
    full_95 = df[(df["panel"] == "M5_full_panel_10sym") & (df["tau"] == 0.95)].iloc[0]
    no_95   = df[(df["panel"] == "M5_no_MSTR_9sym") & (df["tau"] == 0.95)].iloc[0]
    d_real = (no_95["realised"] - full_95["realised"]) * 100
    d_hw_pct = (no_95["half_width_bps"] / full_95["half_width_bps"] - 1) * 100
    print(f"\n  τ=0.95 sensitivity:")
    print(f"    full (10 sym): realised {full_95['realised']:.4f}  "
          f"hw {full_95['half_width_bps']:.1f} bps")
    print(f"    no MSTR (9):   realised {no_95['realised']:.4f}  "
          f"hw {no_95['half_width_bps']:.1f} bps")
    print(f"    Δ realised: {d_real:+.2f}pp   Δ hw: {d_hw_pct:+.2f}%")
    if abs(d_real) <= 0.5 and abs(d_hw_pct) <= 2.0:
        print(f"  → benign; §5.4 footnote suffices")
    else:
        print(f"  → non-trivial; surface in §6.4 / §9.2 rather than footnote")
    return df


# =================================================================== Item 12


def run_item12(panel: pd.DataFrame) -> pd.DataFrame:
    """Stratify deployed M5 OOS coverage at τ=0.95 by `realized_bucket`."""
    print("\n[Item 12] Realised-move tertile stratification …", flush=True)
    if "realized_bucket" not in panel.columns:
        raise RuntimeError(
            "panel lacks `realized_bucket`; expected from regimes.tag(). "
            "Re-run scripts/run_calibration.py to materialise it."
        )

    train = panel[panel["fri_ts"] < SPLIT_DATE].dropna(subset=["score"])
    oos = (panel[panel["fri_ts"] >= SPLIT_DATE]
           .dropna(subset=["score"])
           .reset_index(drop=True))
    qt = train_quantile_table(train, cell_col="regime_pub", taus=DEFAULT_TAUS)
    cb = fit_c_bump_schedule(oos, qt, cell_col="regime_pub", taus=DEFAULT_TAUS)
    bounds = serve_bands(oos, qt, cb, cell_col="regime_pub", taus=DEFAULT_TAUS)

    rows = []
    bucket_order = ["calm", "normal", "shock"]
    for tau in DEFAULT_TAUS:
        b = bounds[tau]
        inside = ((oos["mon_open"] >= b["lower"]) & (oos["mon_open"] <= b["upper"]))
        # Pooled
        v = (~inside).astype(int).to_numpy()
        lr, p_val = met._lr_kupiec(v, tau)
        rows.append({
            "tau": tau, "tertile": "pooled",
            "n": int(len(oos)),
            "realised": float(inside.mean()),
            "half_width_bps": float(((b["upper"] - b["lower"]) / 2 /
                                     oos["fri_close"] * 1e4).mean()),
            "kupiec_lr": float(lr), "kupiec_p": float(p_val),
        })
        # Per tertile
        for bk in bucket_order:
            mask = oos["realized_bucket"] == bk
            sub = oos[mask]
            sub_b = b[mask.values]
            inside_t = ((sub["mon_open"] >= sub_b["lower"]) &
                        (sub["mon_open"] <= sub_b["upper"]))
            v_t = (~inside_t).astype(int).to_numpy()
            lr_t, p_t = met._lr_kupiec(v_t, tau)
            rows.append({
                "tau": tau, "tertile": bk,
                "n": int(len(sub)),
                "realised": float(inside_t.mean()),
                "half_width_bps": float(((sub_b["upper"] - sub_b["lower"]) / 2 /
                                         sub["fri_close"] * 1e4).mean()),
                "kupiec_lr": float(lr_t), "kupiec_p": float(p_t),
            })

    df = pd.DataFrame(rows)
    out_path = REPORTS / "tables" / "v1b_prework_tertile.csv"
    df.to_csv(out_path, index=False)
    print(f"  wrote {out_path}", flush=True)

    # Console summary at τ=0.95.
    print(f"\n  τ=0.95 by tertile:")
    sub = df[df["tau"] == 0.95]
    print(sub.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    return df


# =================================================================== main


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel["score"] = compute_score(panel)

    print(f"Panel: {len(panel):,} rows × {panel['fri_ts'].nunique()} weekends "
          f"× {panel['symbol'].nunique()} symbols")

    run_item3(panel)
    run_item11(panel)
    run_item12(panel)

    print("\ndone.")


if __name__ == "__main__":
    main()
