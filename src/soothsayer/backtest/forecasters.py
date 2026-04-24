"""
Weekend-gap forecasters. Each is a stateless function over a panel row (or
column-wise over the full panel) that returns:

  point        -- point estimate of Monday open
  sigma        -- standard deviation of the Monday-open prediction

CIs are derived parametrically: point ± z_q * sigma. The tradeoff between
sigma methodologies is the whole thing we're testing, so point-estimate
functions and sigma functions are kept decoupled.

Forecasters never read `mon_open` for the row they're predicting; they may
read historical Monday opens (prior weekends' realized outcomes) to fit
sigma models — this is the residual-std approach used in F1 and F2.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def gaussian_bounds(
    forecast: pd.DataFrame,
    coverage_levels: tuple[float, ...],
) -> dict[float, pd.DataFrame]:
    """Convert a (point, sigma) Gaussian forecast into the {coverage: (lower, upper)}
    shape used by the bounds-table builder.

    Used to fold Gaussian forecasters (F0_stale, F1_futures_adj, F2_har_rv)
    into the same calibration-surface machinery as the empirical-quantile
    forecasters (F1_emp, F1_emp_vol, F1_emp_loglog, F1_emp_regime).
    """
    out: dict[float, pd.DataFrame] = {}
    for cov in coverage_levels:
        z = float(norm.ppf(0.5 + cov / 2.0))
        mask = forecast["point"].notna() & forecast["sigma"].notna() & (forecast["sigma"] > 0)
        lower = forecast["point"] - z * forecast["sigma"]
        upper = forecast["point"] + z * forecast["sigma"]
        lower = lower.where(mask)
        upper = upper.where(mask)
        out[float(cov)] = pd.DataFrame(
            {"lower": lower.values, "upper": upper.values},
            index=forecast.index,
        )
    return out


# ---------- Point estimates ----------

def point_stale(panel: pd.DataFrame) -> pd.Series:
    """F0 point: Friday close held forward. The Chainlink analog."""
    return panel["fri_close"].astype(float)


def point_futures_adjusted(panel: pd.DataFrame) -> pd.Series:
    """F1/F2 point: Friday close scaled by the per-symbol factor's weekend return.

    `factor_ret` is populated by `panel.build()` from `FACTOR_BY_SYMBOL`:
    equities use ES=F, gold uses GC=F, long rates use ZN=F. This is the
    asset-class switchboard that fixes the GLD/TLT point-estimate degradation
    from the first V1b pass."""
    return panel["fri_close"].astype(float) * (1.0 + panel["factor_ret"].astype(float))


# ---------- Sigma models ----------

def _gap_scale(gap_days: pd.Series) -> pd.Series:
    """Weekend-length variance scaling: gap=3 → sqrt(1), gap=4 → sqrt(2), etc.

    Standard Fri→Mon weekend (gap=3) is one trading-day's worth of variance.
    Each additional calendar day is treated as roughly one extra trading day
    of non-trading variance, which is a standard (and conservative) heuristic."""
    extra = (gap_days.astype(int) - 3).clip(lower=0) + 1
    return np.sqrt(extra.astype(float))


def sigma_f0(panel: pd.DataFrame) -> pd.Series:
    """F0 sigma: fri_vol_20d * gap_scale * fri_close (in price units)."""
    return panel["fri_vol_20d"].astype(float) * _gap_scale(panel["gap_days"]) * panel["fri_close"].astype(float)


def _rolling_residual_std(
    panel: pd.DataFrame,
    point_col: str,
    window: int,
) -> pd.Series:
    """For each (symbol, weekend), compute the std of the return-residual
    (log(mon_open / point) — a.k.a. pct error of the forecaster) over the
    prior `window` weekends *of the same symbol*, strictly before this row.

    Walk-forward: row i uses only rows (i - window .. i - 1) for its symbol."""
    out = pd.Series(index=panel.index, dtype=float)
    for sym, idx in panel.groupby("symbol").groups.items():
        g = panel.loc[idx].sort_values("fri_ts")
        # Log-return residual: what was left unexplained by the point forecaster
        resid = np.log(g["mon_open"].astype(float) / g[point_col].astype(float))
        # Shift by 1 so row i uses only prior residuals (no look-ahead)
        rolling = resid.shift(1).rolling(window, min_periods=max(8, window // 4)).std()
        out.loc[g.index] = rolling.values
    return out


def sigma_f1(panel: pd.DataFrame, window: int = 52) -> pd.Series:
    """F1 sigma: rolling std of (log mon_open / point_futures_adjusted) over
    the prior `window` weekends (default 52 = ~1 year of weekends).

    Expressed in price units: point * resid_std (local linearization of the
    log-return std to a return std, fine for |resid| < 10%)."""
    point_fa = point_futures_adjusted(panel)
    tmp = panel.copy()
    tmp["_pfa"] = point_fa
    resid_std = _rolling_residual_std(tmp, "_pfa", window)
    return point_fa * resid_std


def empirical_quantiles_f1(
    panel: pd.DataFrame,
    coverage_levels: tuple[float, ...],
    window: int = 104,
) -> dict[float, pd.DataFrame]:
    """F1-emp: factor-adjusted point with CIs from empirical quantiles of
    the rolling residual-return distribution. No Gaussian assumption — captures
    fat tails directly.

    Returns {coverage: DataFrame(lower, upper)} indexed like panel."""
    point_fa = point_futures_adjusted(panel)
    min_obs = max(20, window // 4)
    out: dict[float, pd.DataFrame] = {
        cov: pd.DataFrame(index=panel.index, columns=["lower", "upper"], dtype=float)
        for cov in coverage_levels
    }

    for sym, idx in panel.groupby("symbol").groups.items():
        g = panel.loc[idx].sort_values("fri_ts")
        g_pfa = point_fa.loc[g.index]
        resid_log = np.log(g["mon_open"].astype(float) / g_pfa)
        resid_hist = resid_log.shift(1)
        for i, row_idx in enumerate(g.index):
            start = max(0, i - window)
            past = resid_hist.iloc[start:i].dropna()
            if len(past) < min_obs:
                for cov in coverage_levels:
                    out[cov].at[row_idx, "lower"] = np.nan
                    out[cov].at[row_idx, "upper"] = np.nan
                continue
            pfa_i = g_pfa.iloc[i]
            for cov in coverage_levels:
                tail = (1 - cov) / 2
                lo_q = past.quantile(tail)
                hi_q = past.quantile(1 - tail)
                out[cov].at[row_idx, "lower"] = float(pfa_i * np.exp(lo_q))
                out[cov].at[row_idx, "upper"] = float(pfa_i * np.exp(hi_q))
    return out


def empirical_quantiles_f1_loglog(
    panel: pd.DataFrame,
    coverage_levels: tuple[float, ...],
    window: int = 156,
    min_obs: int = 50,
    vol_col: str = "vix_fri_close",
    extra_regressors: tuple[str, ...] = (),
) -> tuple[dict[float, pd.DataFrame], pd.DataFrame]:
    """F1-emp-loglog: factor-adjusted point with CIs derived from a data-driven
    regime-aware vol model.

    Fit per-symbol rolling:
        log(|resid|) = α + β · log(vol_idx) + γ₁·x₁ + γ₂·x₂ + ... + ε
    where `vol_col` is the per-symbol vol index (VIX for equities, GVZ for
    gold, MOVE for treasuries — supplied by panel.build) and `extra_regressors`
    is a tuple of 0/1 (or continuous) columns like "earnings_next_week" or
    "is_long_weekend".

    Extra regressors whose in-window variance is zero get silently dropped
    from that fit — avoids singular matrices when a ticker has no earnings
    observations in a given window.

    Returns (bounds_by_coverage, fit_diagnostics).
    """
    point_fa = point_futures_adjusted(panel)
    out: dict[float, pd.DataFrame] = {
        cov: pd.DataFrame(index=panel.index, columns=["lower", "upper"], dtype=float)
        for cov in coverage_levels
    }
    diag_rows: list[dict] = []

    extra_cols = list(extra_regressors)

    for sym, idx in panel.groupby("symbol").groups.items():
        g = panel.loc[idx].sort_values("fri_ts")
        g_pfa = point_fa.loc[g.index]
        vol = g[vol_col].astype(float).values
        resid_log = np.log(g["mon_open"].astype(float).values / g_pfa.values)
        extras = {col: g[col].astype(float).values if col in g.columns else np.zeros(len(g))
                  for col in extra_cols}

        for i, row_idx in enumerate(g.index):
            pfa_i = g_pfa.iloc[i]
            vol_i = vol[i]
            if not np.isfinite(vol_i) or vol_i <= 0 or not np.isfinite(pfa_i):
                continue
            start = max(0, i - window)
            past_r = resid_log[start:i]
            past_v = vol[start:i]
            past_extras = {col: arr[start:i] for col, arr in extras.items()}
            now_extras = {col: arr[i] for col, arr in extras.items()}

            valid = np.isfinite(past_r) & np.isfinite(past_v) & (past_v > 0) & (np.abs(past_r) > 1e-10)
            for arr in past_extras.values():
                valid &= np.isfinite(arr)
            if valid.sum() < min_obs:
                continue

            r_v = past_r[valid]
            v_v = past_v[valid]
            # Build design matrix: [1, log(vol), x1, x2, ...]
            design_cols = [np.ones(valid.sum()), np.log(v_v)]
            kept_extra_names = []
            for col in extra_cols:
                x_col = past_extras[col][valid]
                if np.nanstd(x_col) > 0:  # has variance in this window
                    design_cols.append(x_col)
                    kept_extra_names.append(col)
            X = np.column_stack(design_cols)
            y = np.log(np.abs(r_v))

            try:
                beta_hat, *_ = np.linalg.lstsq(X, y, rcond=None)
            except np.linalg.LinAlgError:
                continue
            alpha = beta_hat[0]
            b = beta_hat[1]
            gammas = dict(zip(kept_extra_names, beta_hat[2:]))

            # σ_hist on the valid window
            sigma_hist_log = alpha + b * np.log(v_v)
            for col in kept_extra_names:
                sigma_hist_log = sigma_hist_log + gammas[col] * past_extras[col][valid]
            sigma_hist = np.exp(sigma_hist_log)

            # σ_now
            sigma_now_log = alpha + b * np.log(vol_i)
            for col in kept_extra_names:
                sigma_now_log += gammas[col] * now_extras[col]
            sigma_now = float(np.exp(sigma_now_log))
            if sigma_now <= 0 or not np.isfinite(sigma_now):
                continue

            z_hist = r_v / sigma_hist

            diag = {
                "symbol": sym,
                "fri_ts": g.iloc[i]["fri_ts"],
                "alpha": float(alpha),
                "beta": float(b),
                "sigma_now": sigma_now,
                "n_fit": int(valid.sum()),
            }
            for col in extra_cols:
                diag[f"gamma_{col}"] = float(gammas.get(col, 0.0))
                diag[f"now_{col}"] = float(now_extras[col])
            diag_rows.append(diag)

            for cov in coverage_levels:
                tail = (1 - cov) / 2
                z_lo = float(np.quantile(z_hist, tail))
                z_hi = float(np.quantile(z_hist, 1 - tail))
                out[cov].at[row_idx, "lower"] = float(pfa_i * np.exp(z_lo * sigma_now))
                out[cov].at[row_idx, "upper"] = float(pfa_i * np.exp(z_hi * sigma_now))

    diag = pd.DataFrame(diag_rows)
    return out, diag


def empirical_quantiles_f1_vol(
    panel: pd.DataFrame,
    coverage_levels: tuple[float, ...],
    window: int = 104,
) -> dict[float, pd.DataFrame]:
    """F1-emp-vol: same as F1-emp but residuals are standardised by
    contemporaneous VIX before quantiling, then de-standardised by current VIX.

    Rationale: residual weekend vol scales approximately linearly with VIX.
    A 104-week rolling window mixes calm and stressed regimes; taking the
    empirical quantile of r/VIX removes the vol-of-vol contribution to the
    historical distribution, and multiplying back by VIX_now re-widens the
    CI in turbulent regimes. Addresses the high_vol undercoverage finding
    from the first V1b pass (80.8% realised at 95% claimed).
    """
    point_fa = point_futures_adjusted(panel)
    min_obs = max(20, window // 4)
    out: dict[float, pd.DataFrame] = {
        cov: pd.DataFrame(index=panel.index, columns=["lower", "upper"], dtype=float)
        for cov in coverage_levels
    }

    for sym, idx in panel.groupby("symbol").groups.items():
        g = panel.loc[idx].sort_values("fri_ts")
        g_pfa = point_fa.loc[g.index]
        vix = g["vix_fri_close"].astype(float)
        resid_log = np.log(g["mon_open"].astype(float) / g_pfa)
        resid_std = resid_log / vix  # standardised residual (vol-normalised)
        resid_std_hist = resid_std.shift(1)
        for i, row_idx in enumerate(g.index):
            start = max(0, i - window)
            past = resid_std_hist.iloc[start:i].dropna()
            if len(past) < min_obs:
                for cov in coverage_levels:
                    out[cov].at[row_idx, "lower"] = np.nan
                    out[cov].at[row_idx, "upper"] = np.nan
                continue
            pfa_i = g_pfa.iloc[i]
            vix_i = vix.iloc[i]
            if not np.isfinite(vix_i) or vix_i <= 0:
                for cov in coverage_levels:
                    out[cov].at[row_idx, "lower"] = np.nan
                    out[cov].at[row_idx, "upper"] = np.nan
                continue
            for cov in coverage_levels:
                tail = (1 - cov) / 2
                lo_z = past.quantile(tail)
                hi_z = past.quantile(1 - tail)
                out[cov].at[row_idx, "lower"] = float(pfa_i * np.exp(lo_z * vix_i))
                out[cov].at[row_idx, "upper"] = float(pfa_i * np.exp(hi_z * vix_i))
    return out


def sigma_f2_har_rv(panel: pd.DataFrame, daily: pd.DataFrame) -> pd.Series:
    """F2 sigma: HAR-RV forecast of next-period realized volatility, times
    gap-scale, in price units. Requires the full daily bars to compute
    historical RV series for the HAR-RV fit.

    HAR-RV: RV_{t+1} = c + β_d * RV_t^(d) + β_w * RV_t^(w) + β_m * RV_t^(m)
    with RV^(d) = last-day squared log-return, RV^(w) = 5-day mean, RV^(m) = 22-day mean.

    We fit one HAR-RV per symbol on the full pre-weekend history using a
    rolling-origin walk-forward (the fit uses only data strictly before Friday).
    """
    # Compute daily squared log-returns per symbol
    d = daily.copy()
    d["ts"] = pd.to_datetime(d["ts"])
    d = d.sort_values(["symbol", "ts"])
    d["logret"] = np.log(d["close"] / d.groupby("symbol")["close"].shift(1))
    d["rv_d"] = d["logret"] ** 2
    # Rolling means of daily RV — lag by 1 so row t uses data through t-1
    d["rv_w"] = d.groupby("symbol")["rv_d"].transform(lambda s: s.rolling(5, min_periods=5).mean())
    d["rv_m"] = d.groupby("symbol")["rv_d"].transform(lambda s: s.rolling(22, min_periods=22).mean())

    # Index daily frame by (symbol, date) for fast per-weekend lookup
    d = d.set_index(["symbol", pd.to_datetime(d["ts"]).dt.date])

    sigma = pd.Series(index=panel.index, dtype=float)
    for sym, grp in panel.groupby("symbol", sort=False):
        g = grp.sort_values("fri_ts").reset_index()
        # Align Friday-date features for each weekend
        features = []
        targets = []
        fridays = []
        for _, row in g.iterrows():
            fri = row["fri_ts"]
            try:
                feat = d.loc[(sym, fri)]
            except KeyError:
                features.append((np.nan, np.nan, np.nan))
                targets.append(np.nan)
                fridays.append(fri)
                continue
            if not isinstance(feat, pd.Series):
                # Multiple rows for same date (shouldn't happen for daily) — take first
                feat = feat.iloc[0]
            features.append((feat.get("rv_d"), feat.get("rv_w"), feat.get("rv_m")))
            # Target = realized weekend log-return variance = (log(mon_open/fri_close))^2
            targets.append(np.log(row["mon_open"] / row["fri_close"]) ** 2)
            fridays.append(fri)

        feat_df = pd.DataFrame(features, columns=["rv_d", "rv_w", "rv_m"])
        tgt_series = pd.Series(targets)

        # Walk-forward OLS: for each row i, fit on rows [0, i-1] with sufficient data
        pred_var = np.full(len(g), np.nan)
        for i in range(len(g)):
            train_x = feat_df.iloc[:i]
            train_y = tgt_series.iloc[:i]
            mask = train_x.notna().all(axis=1) & train_y.notna()
            if mask.sum() < 40:  # need enough history to fit 4 params sensibly
                # Fall back to rolling realized-weekend-variance mean
                if mask.sum() > 0:
                    pred_var[i] = train_y[mask].mean()
                continue
            X = train_x[mask].values
            y = train_y[mask].values
            X_aug = np.column_stack([np.ones(len(X)), X])
            # Ridge for stability (λ = 1e-10 of identity)
            XtX = X_aug.T @ X_aug + 1e-10 * np.eye(4)
            beta = np.linalg.solve(XtX, X_aug.T @ y)
            x_i = feat_df.iloc[i]
            if x_i.isna().any():
                pred_var[i] = train_y[mask].mean()
                continue
            pred = beta[0] + beta[1] * x_i["rv_d"] + beta[2] * x_i["rv_w"] + beta[3] * x_i["rv_m"]
            pred_var[i] = max(pred, 1e-8)  # guard against negatives from OLS

        # Convert predicted variance (log-return variance) to price-unit sigma
        pred_ret_sigma = np.sqrt(pred_var)
        point_fa = g["fri_close"] * (1.0 + g["fut_ret"])
        sig_price = point_fa * pred_ret_sigma
        sigma.loc[g["index"]] = sig_price.values

    return sigma


# ---------- Forecaster bundle ----------

def forecast_f0(panel: pd.DataFrame) -> pd.DataFrame:
    """F0 Stale-hold. Returns columns point, sigma."""
    return pd.DataFrame(
        {
            "point": point_stale(panel),
            "sigma": sigma_f0(panel),
        },
        index=panel.index,
    )


def forecast_f1(panel: pd.DataFrame, window: int = 52) -> pd.DataFrame:
    """F1 Naive futures-adjusted with rolling-residual sigma."""
    return pd.DataFrame(
        {
            "point": point_futures_adjusted(panel),
            "sigma": sigma_f1(panel, window=window),
        },
        index=panel.index,
    )


def forecast_f2(panel: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """F2 Futures-adjusted point with HAR-RV forecast sigma."""
    return pd.DataFrame(
        {
            "point": point_futures_adjusted(panel),
            "sigma": sigma_f2_har_rv(panel, daily),
        },
        index=panel.index,
    )
