"""
GARCH(1,1) baseline — §6 / §10 paper-1 robustness check.

The textbook econometric default for a time-varying weekend interval is
the per-symbol GARCH(1,1) model on log Friday→Monday returns:

    r_t = μ + ε_t,    ε_t = σ_t · z_t,    z_t ~ N(0, 1) or t(ν)
    σ_t² = ω + α · ε_{t-1}² + β · σ_{t-1}²

Forecasted weekend band:
    p̂ = fri_close · exp(μ + 0)               (centred forecast)
    lower = fri_close · exp(μ - q_α · σ̂_t)
    upper = fri_close · exp(μ + q_α · σ̂_t)

where q_α = norm.ppf(0.5 + τ/2) under Gaussian innovations, or the
*standardised*-t quantile (var=1) under Student-t innovations:
    q_α^t(ν) = t.ppf(0.5 + τ/2, df=ν) · sqrt((ν-2)/ν)

This script fits one GARCH(1,1) per symbol on pre-2023 weekend returns,
forecasts σ̂_t one-step-ahead at each post-2023 weekend (no leak),
constructs τ ∈ {0.68, 0.85, 0.95, 0.99} bands, and compares against the
active forecaster's deployed bands on the same OOS keys.

Forecasters
-----------
  --forecaster m5   (default; deployed Mondrian-by-regime)
  --forecaster lwc  (M6 Locally-Weighted Conformal)

The GARCH fit itself is forecaster-agnostic — only the reference band
swaps between M5 and LWC.

Innovation distributions
------------------------
  --dist gaussian   (default; backward-compat with the existing receipt)
  --dist t          (Phase 7.3 — Student-t innovations; standard
                     practitioner baseline. Per-symbol fallback to
                     gaussian if the t-fit doesn't converge or returns
                     ν ≤ 2.5; flagged in the `dist_used` output column.)

Outputs:
  reports/tables/v1b_robustness_garch_baseline.csv         (--forecaster m5 --dist gaussian)
  reports/tables/m6_lwc_robustness_garch_baseline.csv      (--forecaster lwc --dist gaussian)
  reports/tables/v1b_robustness_garch_t_baseline.csv       (--forecaster m5 --dist t)
  reports/tables/m6_lwc_robustness_garch_t_baseline.csv    (--forecaster lwc --dist t)
"""

from __future__ import annotations

import argparse
import warnings
from datetime import date

import numpy as np
import pandas as pd
from arch import arch_model
from scipy.stats import norm, t as student_t

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    fit_split_conformal_forecaster,
    prep_panel_for_forecaster,
    serve_bands_forecaster,
)
from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
NU_FLOOR = 2.5  # below this, t-variance scaling is numerically unstable


def fit_per_symbol_garch(panel: pd.DataFrame, dist: str) -> pd.DataFrame:
    """Fit GARCH(1,1) per symbol on pre-2023 weekend log-returns and emit
    one-step-ahead σ̂ at every post-2023 weekend (rolling re-fit per
    weekend would be the academically pure variant; we use a single fit on
    the train side, with σ̂_t produced by feeding the full pre-t return
    history into the fitted model — this is the textbook "expanding-window
    fit, recursive forecast" baseline).

    `dist` selects the innovation distribution. Under `t`, fits with
    `dist="t"` and records the fitted ν per symbol; on convergence
    failure or ν ≤ NU_FLOOR the symbol falls back to gaussian and the
    `dist_used` column records the fallback."""
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
        dist_used = dist
        nu_hat = float("nan")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                mdl = arch_model(train["log_ret"].values * scale,
                                 mean="Constant", vol="GARCH", p=1, q=1,
                                 dist=("normal" if dist == "gaussian" else "t"))
                res = mdl.fit(disp="off", show_warning=False)
                if dist == "t":
                    nu_hat = float(res.params.get("nu", float("nan")))
                    if not np.isfinite(nu_hat) or nu_hat <= NU_FLOOR:
                        # Fall back: refit under gaussian.
                        print(f"  {sym}: t-fit returned ν={nu_hat:.2f}; "
                              "falling back to gaussian.", flush=True)
                        mdl = arch_model(train["log_ret"].values * scale,
                                         mean="Constant", vol="GARCH",
                                         p=1, q=1, dist="normal")
                        res = mdl.fit(disp="off", show_warning=False)
                        dist_used = "gaussian"
                        nu_hat = float("nan")
            except Exception as exc:  # noqa: BLE001
                print(f"  {sym}: GARCH fit raised {exc!r}; "
                      "falling back to gaussian.", flush=True)
                mdl = arch_model(train["log_ret"].values * scale,
                                 mean="Constant", vol="GARCH", p=1, q=1,
                                 dist="normal")
                res = mdl.fit(disp="off", show_warning=False)
                dist_used = "gaussian"
                nu_hat = float("nan")

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
                "dist_used": dist_used,
                "nu_hat": nu_hat,
            })
    return pd.DataFrame(rows)


def _quantile(tau: float, dist_used: str, nu: float) -> float:
    """Symmetric two-sided coverage τ → one-sided quantile q.

    Gaussian: q = Φ⁻¹(0.5 + τ/2).
    Standardised-t (var=1): q = T_ν⁻¹(0.5 + τ/2) · √((ν-2)/ν)."""
    p = 0.5 + tau / 2.0
    if dist_used == "gaussian" or not np.isfinite(nu):
        return float(norm.ppf(p))
    return float(student_t.ppf(p, df=nu) * np.sqrt((nu - 2.0) / nu))


def serve_garch_bands(forecasts: pd.DataFrame,
                      taus: tuple[float, ...]) -> dict[float, pd.DataFrame]:
    """For each row, p̂ = fri_close · exp(μ); band = fri_close · exp(μ ± q_α σ̂).
    The quantile q_α follows the per-symbol fitted distribution; under the
    Phase 7.3 t variant ν is per-symbol so we vectorise per row."""
    out: dict[float, pd.DataFrame] = {}
    fri_close = forecasts["fri_close"].astype(float).values
    mu = forecasts["mu_hat"].values
    sig = forecasts["sigma_hat"].values
    dist_used = forecasts["dist_used"].values
    nu = forecasts["nu_hat"].values
    for tau in taus:
        # Memoise q per (dist_used, nu) so we don't recompute per row.
        q_per_row = np.empty(len(forecasts), dtype=float)
        cache: dict[tuple[str, float], float] = {}
        for i in range(len(forecasts)):
            key = (str(dist_used[i]), float(nu[i])
                   if np.isfinite(nu[i]) else float("nan"))
            if key not in cache:
                cache[key] = _quantile(tau, key[0], key[1])
            q_per_row[i] = cache[key]
        lower = fri_close * np.exp(mu - q_per_row * sig)
        upper = fri_close * np.exp(mu + q_per_row * sig)
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


def _output_path(forecaster: str, dist: str) -> str:
    suffix = "" if dist == "gaussian" else "_t"
    if forecaster == "m5":
        return str(REPORTS / "tables"
                   / f"v1b_robustness_garch{suffix}_baseline.csv")
    return str(REPORTS / "tables"
               / f"m6_lwc_robustness_garch{suffix}_baseline.csv")


def _garch_label(dist: str) -> str:
    """Row label for the `method` column. Gaussian keeps the historical
    `GARCH(1,1)` literal so `build_paper1_figures.py` (which filters on
    that string) and the existing receipt remain byte-equivalent. The
    Phase 7.3 t variant uses `GARCH(1,1)-t`."""
    return "GARCH(1,1)" if dist == "gaussian" else "GARCH(1,1)-t"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecaster", choices=("m5", "lwc"), default="m5")
    parser.add_argument(
        "--dist", choices=("gaussian", "t"), default="gaussian",
        help="Innovation distribution. Default `gaussian` preserves the "
             "existing receipt; `t` enables the Phase 7.3 Student-t baseline.",
    )
    args = parser.parse_args()

    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)
    panel = prep_panel_for_forecaster(panel, args.forecaster)

    print(f"Forecaster: {args.forecaster}   GARCH innovation dist: "
          f"{args.dist}", flush=True)
    print(f"Panel: {len(panel):,} rows × "
          f"{panel['fri_ts'].nunique()} weekends × "
          f"{panel['symbol'].nunique()} symbols", flush=True)

    print("\n[1/3] Per-symbol GARCH(1,1) fit + recursive σ̂ …", flush=True)
    forecasts = fit_per_symbol_garch(panel, args.dist)
    forecasts["fri_ts"] = pd.to_datetime(forecasts["fri_ts"]).dt.date
    print(f"      {len(forecasts):,} (symbol, weekend) rows; "
          f"mean σ̂ = {forecasts['sigma_hat'].mean():.4f}", flush=True)
    if args.dist == "t":
        per_sym_nu = (forecasts.groupby("symbol")
                      .agg(dist_used=("dist_used", "first"),
                           nu_hat=("nu_hat", "first"))
                      .reset_index())
        n_t = int((per_sym_nu["dist_used"] == "t").sum())
        print(f"      per-symbol t fit: {n_t}/{len(per_sym_nu)} converged"
              " (others fell back to gaussian); ν̂ summary:", flush=True)
        print(per_sym_nu.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    fc_oos = forecasts[forecasts["fri_ts"] >= SPLIT_DATE].dropna(
        subset=["sigma_hat"]).reset_index(drop=True)

    print("[2/3] Serving GARCH bands and tabulating coverage …", flush=True)
    g_bounds = serve_garch_bands(fc_oos, DEFAULT_TAUS)
    g_cov = coverage_table(fc_oos, g_bounds, DEFAULT_TAUS, _garch_label(args.dist))
    print(g_cov.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    label = "M5_deployed" if args.forecaster == "m5" else "LWC_deployed"
    print(f"\n[3/3] Re-serving deployed {args.forecaster.upper()} "
          "on the same OOS keys …", flush=True)
    qt, cb, info = fit_split_conformal_forecaster(
        panel, SPLIT_DATE, args.forecaster, cell_col="regime_pub",
    )
    keys_g = fc_oos[["symbol", "fri_ts"]].assign(_in_garch=True)
    panel_oos = (
        panel[panel["fri_ts"] >= SPLIT_DATE]
        .dropna(subset=["score"])
        .merge(keys_g, on=["symbol", "fri_ts"], how="inner")
        .sort_values(["symbol", "fri_ts"])
        .reset_index(drop=True)
    )
    ref_bounds = serve_bands_forecaster(
        panel_oos, qt, cb, args.forecaster,
        cell_col="regime_pub", taus=DEFAULT_TAUS,
    )
    ref_cov = coverage_table(panel_oos, ref_bounds, DEFAULT_TAUS, label)
    print(ref_cov.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    out = pd.concat([g_cov, ref_cov], ignore_index=True)
    out["forecaster"] = args.forecaster
    out["garch_dist"] = args.dist
    out_path = _output_path(args.forecaster, args.dist)
    out.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}", flush=True)

    g_lbl = _garch_label(args.dist)
    print("\n" + "=" * 80)
    print(f"HEAD-TO-HEAD AT τ = 0.95  ({label} vs {g_lbl})")
    print("=" * 80)
    g95 = g_cov[g_cov["tau"] == 0.95].iloc[0]
    r95 = ref_cov[ref_cov["tau"] == 0.95].iloc[0]
    print(f"{g_lbl}:    realised = {g95['realised']:.4f}  "
          f"hw = {g95['half_width_bps']:.1f} bps  "
          f"Kupiec p = {g95['kupiec_p']:.3f}  "
          f"Christoffersen p = {g95['christ_p']:.3f}")
    print(f"{label}:  realised = {r95['realised']:.4f}  "
          f"hw = {r95['half_width_bps']:.1f} bps  "
          f"Kupiec p = {r95['kupiec_p']:.3f}  "
          f"Christoffersen p = {r95['christ_p']:.3f}")


if __name__ == "__main__":
    main()
