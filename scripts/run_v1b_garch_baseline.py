"""
GARCH(1,1) baseline — §6 / §10 paper-1 robustness check.

The textbook econometric default for a time-varying weekend interval is
the per-symbol GARCH(1,1) model on log Friday→Monday returns:

    r_t = μ + ε_t,    ε_t = σ_t · z_t,    z_t ~ N(0, 1)
    σ_t² = ω + α · ε_{t-1}² + β · σ_{t-1}²

Forecasted weekend band:
    p̂ = fri_close · exp(μ + 0)               (centred forecast)
    lower = fri_close · exp(μ - z_α · σ̂_t)
    upper = fri_close · exp(μ + z_α · σ̂_t)

This script fits one GARCH(1,1) per symbol on pre-2023 weekend returns,
forecasts σ̂_t one-step-ahead at each post-2023 weekend (no leak),
constructs τ ∈ {0.68, 0.85, 0.95, 0.99} bands, and compares pooled
realised coverage / mean half-width / Kupiec / Christoffersen against the
deployed M5 numbers from §6.3.

Output: reports/tables/v1b_robustness_garch_baseline.csv
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
    fit_split_conformal,
    serve_bands,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)


def fit_per_symbol_garch(panel: pd.DataFrame) -> pd.DataFrame:
    """Fit GARCH(1,1) per symbol on pre-2023 weekend log-returns and emit
    one-step-ahead σ̂ at every post-2023 weekend (rolling re-fit per
    weekend would be the academically pure variant; we use a single fit on
    the train side, with σ̂_t produced by feeding the full pre-t return
    history into the fitted model — this is the textbook "expanding-window
    fit, recursive forecast" baseline)."""
    rows = []
    for sym, g in panel.groupby("symbol"):
        g = g.sort_values("fri_ts").reset_index(drop=True).copy()
        g["log_ret"] = np.log(g["mon_open"] / g["fri_close"])
        train = g[g["fri_ts"] < SPLIT_DATE].dropna(subset=["log_ret"])
        if len(train) < 50:
            print(f"  {sym}: only {len(train)} train rows — skipping",
                  flush=True)
            continue
        # arch wants returns in pct units; rescale and back out at forecast time.
        scale = 100.0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdl = arch_model(train["log_ret"].values * scale,
                             mean="Constant", vol="GARCH", p=1, q=1,
                             dist="normal")
            res = mdl.fit(disp="off", show_warning=False)
        mu_hat = float(res.params.get("mu", 0.0)) / scale
        omega = float(res.params["omega"]) / (scale ** 2)
        alpha = float(res.params["alpha[1]"])
        beta = float(res.params["beta[1]"])

        # Recursive σ_t² over the full series (train + OOS) using the
        # fitted (omega, alpha, beta) and the *realised* ε_{t-1}². No
        # leak — σ̂_t at row t uses only ε_{t-1} and σ̂_{t-1}, both of
        # which sit at t-1 ≤ fri_ts(t).
        sigma2_seq = np.empty(len(g), dtype=float)
        sigma2_seq[:] = np.nan
        sigma2_seq[0] = omega / max(1.0 - alpha - beta, 1e-6)
        for i in range(1, len(g)):
            r_prev = g["log_ret"].iloc[i - 1]
            if not np.isfinite(r_prev):
                sigma2_seq[i] = sigma2_seq[i - 1]
                continue
            eps_prev = r_prev - mu_hat
            sigma2_seq[i] = omega + alpha * (eps_prev ** 2) + beta * sigma2_seq[i - 1]
        sigma_hat = np.sqrt(sigma2_seq)

        for i, row in g.iterrows():
            rows.append({
                "symbol": sym,
                "fri_ts": row["fri_ts"],
                "regime_pub": row["regime_pub"],
                "fri_close": float(row["fri_close"]),
                "mon_open": float(row["mon_open"]),
                "mu_hat": mu_hat,
                "sigma_hat": float(sigma_hat[i]),
                "omega": omega, "alpha": alpha, "beta": beta,
            })
    return pd.DataFrame(rows)


def serve_garch_bands(forecasts: pd.DataFrame,
                      taus: tuple[float, ...]) -> dict[float, pd.DataFrame]:
    """For each row, p̂ = fri_close · exp(μ); band = fri_close · exp(μ ± z_α σ̂)."""
    out: dict[float, pd.DataFrame] = {}
    fri_close = forecasts["fri_close"].astype(float).values
    mu = forecasts["mu_hat"].values
    sig = forecasts["sigma_hat"].values
    for tau in taus:
        z = norm.ppf(0.5 + tau / 2.0)
        lower = fri_close * np.exp(mu - z * sig)
        upper = fri_close * np.exp(mu + z * sig)
        out[tau] = pd.DataFrame({"lower": lower, "upper": upper},
                                index=forecasts.index)
    return out


def coverage_table(panel: pd.DataFrame, bounds: dict[float, pd.DataFrame],
                   taus: tuple[float, ...], label: str) -> pd.DataFrame:
    """Caller is responsible for `panel` and `bounds[tau]` sharing the same
    index — `bounds` here is keyed by `panel.index`, not by symbol/fri_ts."""
    rows = []
    for tau in taus:
        b = bounds[tau]
        if not b.index.equals(panel.index):
            b = b.reindex(panel.index)
        inside = ((panel["mon_open"] >= b["lower"]) &
                  (panel["mon_open"] <= b["upper"]))
        v = (~inside).astype(int).to_numpy()
        lr_uc, p_uc = met._lr_kupiec(v, tau)
        cc = met.conditional_coverage_from_bounds(
            panel, {tau: b}, group_by="symbol"
        )
        cc0 = cc.iloc[0]
        rows.append({
            "method": label, "tau": tau,
            "n": int(len(panel)),
            "realised": float(inside.mean()),
            "half_width_bps": float(((b["upper"] - b["lower"]) / 2 /
                                     panel["fri_close"] * 1e4).mean()),
            "kupiec_lr": float(lr_uc), "kupiec_p": float(p_uc),
            "christ_lr": float(cc0["lr_ind"]),
            "christ_p": float(cc0["p_ind"]),
        })
    return pd.DataFrame(rows)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel["score"] = compute_score(panel)

    print(f"Panel: {len(panel):,} rows × "
          f"{panel['fri_ts'].nunique()} weekends × "
          f"{panel['symbol'].nunique()} symbols", flush=True)

    print("\n[1/3] Per-symbol GARCH(1,1) fit + recursive σ̂ …", flush=True)
    forecasts = fit_per_symbol_garch(panel)
    forecasts["fri_ts"] = pd.to_datetime(forecasts["fri_ts"]).dt.date
    print(f"      {len(forecasts):,} (symbol, weekend) rows; "
          f"mean σ̂ = {forecasts['sigma_hat'].mean():.4f}", flush=True)
    fc_oos = forecasts[forecasts["fri_ts"] >= SPLIT_DATE].dropna(
        subset=["sigma_hat"]).reset_index(drop=True)

    print("[2/3] Serving GARCH bands and tabulating coverage …", flush=True)
    g_bounds = serve_garch_bands(fc_oos, DEFAULT_TAUS)
    g_cov = coverage_table(fc_oos, g_bounds, DEFAULT_TAUS, "GARCH(1,1)")
    print(g_cov.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n[3/3] Re-serving deployed M5 on the same OOS keys …", flush=True)
    qt, cb, info = fit_split_conformal(panel, SPLIT_DATE, cell_col="regime_pub")
    keys_g = fc_oos[["symbol", "fri_ts"]].assign(_in_garch=True)
    panel_oos = (
        panel[panel["fri_ts"] >= SPLIT_DATE]
        .dropna(subset=["score"])
        .merge(keys_g, on=["symbol", "fri_ts"], how="inner")
        .sort_values(["symbol", "fri_ts"])
        .reset_index(drop=True)
    )
    m5_bounds = serve_bands(panel_oos, qt, cb, cell_col="regime_pub",
                            taus=DEFAULT_TAUS)
    m5_cov = coverage_table(panel_oos, m5_bounds, DEFAULT_TAUS, "M5_deployed")
    print(m5_cov.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    out = pd.concat([g_cov, m5_cov], ignore_index=True)
    out_path = REPORTS / "tables" / "v1b_robustness_garch_baseline.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}", flush=True)

    print("\n" + "=" * 80)
    print("HEAD-TO-HEAD AT τ = 0.95")
    print("=" * 80)
    g95 = g_cov[g_cov["tau"] == 0.95].iloc[0]
    m95 = m5_cov[m5_cov["tau"] == 0.95].iloc[0]
    print(f"GARCH(1,1):  realised = {g95['realised']:.4f}  "
          f"hw = {g95['half_width_bps']:.1f} bps  "
          f"Kupiec p = {g95['kupiec_p']:.3f}  "
          f"Christoffersen p = {g95['christ_p']:.3f}")
    print(f"M5 deployed: realised = {m95['realised']:.4f}  "
          f"hw = {m95['half_width_bps']:.1f} bps  "
          f"Kupiec p = {m95['kupiec_p']:.3f}  "
          f"Christoffersen p = {m95['christ_p']:.3f}")


if __name__ == "__main__":
    main()
