"""
Calibration and accuracy metrics for weekend-gap forecasters.

Every forecaster is summarised as a (point, sigma) pair, from which Gaussian
CIs at any coverage level q are constructed as point ± z_q * sigma. The
central question is whether the realised Monday open falls inside the claimed
CI at the claimed rate — the primary product claim.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm


# Standard coverage levels to evaluate
COVERAGE_LEVELS = (0.68, 0.95, 0.99)


def _z(coverage: float) -> float:
    return norm.ppf(0.5 + coverage / 2.0)


def _valid(fc: pd.DataFrame, panel: pd.DataFrame) -> pd.Series:
    """Mask for rows with usable forecasts (non-NaN point and sigma)."""
    return fc["point"].notna() & fc["sigma"].notna() & (fc["sigma"] > 0) & panel["mon_open"].notna()


def coverage_and_sharpness(
    panel: pd.DataFrame,
    forecast: pd.DataFrame,
    coverage_levels: tuple[float, ...] = COVERAGE_LEVELS,
) -> pd.DataFrame:
    """One row per coverage level with:
        claimed  realized  sharpness_bps  n
    sharpness = mean half-width / fri_close, in bps (100 * 100 = bps)."""
    m = _valid(forecast, panel)
    p = panel.loc[m]
    f = forecast.loc[m]
    rows = []
    for cov in coverage_levels:
        z = _z(cov)
        lo = f["point"] - z * f["sigma"]
        hi = f["point"] + z * f["sigma"]
        inside = (p["mon_open"] >= lo) & (p["mon_open"] <= hi)
        half_width_bps = (z * f["sigma"] / p["fri_close"] * 1e4).mean()
        rows.append(
            {
                "claimed": cov,
                "realized": float(inside.mean()),
                "sharpness_bps": float(half_width_bps),
                "n": int(len(p)),
            }
        )
    return pd.DataFrame(rows)


def point_accuracy(panel: pd.DataFrame, forecast: pd.DataFrame) -> dict:
    """MAE, RMSE, median bias — all in bps of Friday close."""
    m = _valid(forecast, panel)
    p = panel.loc[m]
    f = forecast.loc[m]
    err_bps = (f["point"] - p["mon_open"]) / p["fri_close"] * 1e4
    return {
        "mae_bps": float(err_bps.abs().mean()),
        "rmse_bps": float(np.sqrt((err_bps ** 2).mean())),
        "median_bias_bps": float(err_bps.median()),
        "n": int(len(p)),
    }


def calibration_curve(
    panel: pd.DataFrame,
    forecast: pd.DataFrame,
    quantiles: np.ndarray | None = None,
) -> pd.DataFrame:
    """Realized coverage across a fine quantile grid, for plotting.
    Returns claimed, realized, over nominal 0.10..0.99."""
    if quantiles is None:
        quantiles = np.arange(0.10, 1.00, 0.05)
    m = _valid(forecast, panel)
    p = panel.loc[m]
    f = forecast.loc[m]
    rows = []
    for q in quantiles:
        z = _z(q)
        lo = f["point"] - z * f["sigma"]
        hi = f["point"] + z * f["sigma"]
        realized = ((p["mon_open"] >= lo) & (p["mon_open"] <= hi)).mean()
        rows.append({"claimed": float(q), "realized": float(realized)})
    return pd.DataFrame(rows)


def coverage_and_sharpness_from_bounds(
    panel: pd.DataFrame,
    point: pd.Series,
    bounds: dict[float, pd.DataFrame],
) -> pd.DataFrame:
    """Same schema as coverage_and_sharpness, but takes direct {coverage: (lower, upper)} bounds.

    Sharpness is mean ((upper - lower) / 2) / fri_close in bps, averaging over the
    symmetric half-width even when the band is asymmetric (same metric shape as the
    parametric case)."""
    rows = []
    for cov, band in bounds.items():
        m = panel["mon_open"].notna() & band["lower"].notna() & band["upper"].notna()
        p = panel.loc[m]
        b = band.loc[m]
        inside = (p["mon_open"] >= b["lower"]) & (p["mon_open"] <= b["upper"])
        half_width_bps = ((b["upper"] - b["lower"]) / 2 / p["fri_close"] * 1e4).mean()
        rows.append(
            {
                "claimed": cov,
                "realized": float(inside.mean()),
                "sharpness_bps": float(half_width_bps),
                "n": int(len(p)),
            }
        )
    return pd.DataFrame(rows)


def calibration_curve_from_bounds(
    panel: pd.DataFrame,
    bounds: dict[float, pd.DataFrame],
) -> pd.DataFrame:
    """Claim/realize curve from explicit-bounds forecasters. Quantile grid is
    whatever coverage levels were supplied."""
    rows = []
    for cov in sorted(bounds.keys()):
        band = bounds[cov]
        m = panel["mon_open"].notna() & band["lower"].notna() & band["upper"].notna()
        realized = ((panel.loc[m, "mon_open"] >= band.loc[m, "lower"]) & (panel.loc[m, "mon_open"] <= band.loc[m, "upper"])).mean()
        rows.append({"claimed": float(cov), "realized": float(realized)})
    return pd.DataFrame(rows)


def summarize_bounds(
    name: str,
    panel: pd.DataFrame,
    point: pd.Series,
    bounds: dict[float, pd.DataFrame],
) -> pd.DataFrame:
    cov = coverage_and_sharpness_from_bounds(panel, point, bounds)
    m = panel["mon_open"].notna() & point.notna()
    err_bps = ((point.loc[m] - panel.loc[m, "mon_open"]) / panel.loc[m, "fri_close"] * 1e4)
    row: dict = {"forecaster": name, "n": int(m.sum())}
    for _, r in cov.iterrows():
        pct = int(round(r["claimed"] * 100))
        row[f"cov{pct}_realized"] = r["realized"]
        row[f"cov{pct}_sharp_bps"] = r["sharpness_bps"]
    row["mae_bps"] = float(err_bps.abs().mean())
    row["rmse_bps"] = float(np.sqrt((err_bps ** 2).mean()))
    row["bias_bps"] = float(err_bps.median())
    return pd.DataFrame([row])


def _lr_kupiec(violations: np.ndarray, claimed: float) -> tuple[float, float]:
    """Kupiec POF (proportion-of-failures) likelihood-ratio test.

    H0: violation rate == expected = (1 - claimed).
    Returns (LR_uc, p_value). LR_uc ~ χ²(1) under H0.
    """
    n = len(violations)
    x = int(violations.sum())
    if n == 0:
        return float("nan"), float("nan")
    p_exp = 1.0 - claimed
    p_obs = x / n
    # Guard log(0)
    if p_obs in (0.0, 1.0):
        # Likelihood collapses to a single term; return boundary test value
        if p_exp in (0.0, 1.0):
            return 0.0, 1.0
        # Use a large-but-finite LR so the test flags the extreme
        lr = 2.0 * n * (p_obs * np.log(max(p_obs, 1e-12) / p_exp) +
                       (1 - p_obs) * np.log(max(1 - p_obs, 1e-12) / max(1 - p_exp, 1e-12)))
    else:
        lr = 2.0 * (x * np.log(p_obs / p_exp) + (n - x) * np.log((1 - p_obs) / (1 - p_exp)))
    p_val = 1.0 - chi2.cdf(lr, df=1)
    return float(lr), float(p_val)


def _lr_christoffersen_independence(violations: np.ndarray) -> tuple[float, float]:
    """Christoffersen (1998) independence test: are violations Markov-independent?

    Transitions (n_ij = count of going from state i at t-1 to state j at t, where
    1 = violation, 0 = non-violation):
      - H0: π_01 == π_11 (violations don't cluster)
      - Alternative: π_01 != π_11

    Returns (LR_ind, p_value). LR_ind ~ χ²(1) under H0.
    Requires at least 2 observations AND both types of transitions to compute.
    """
    v = np.asarray(violations, dtype=int)
    n = len(v)
    if n < 2:
        return float("nan"), float("nan")
    # Transitions: pairs (v[t-1], v[t])
    prev = v[:-1]
    curr = v[1:]
    n00 = int(((prev == 0) & (curr == 0)).sum())
    n01 = int(((prev == 0) & (curr == 1)).sum())
    n10 = int(((prev == 1) & (curr == 0)).sum())
    n11 = int(((prev == 1) & (curr == 1)).sum())

    # P(violation) under unrestricted model:
    denom0 = n00 + n01
    denom1 = n10 + n11
    if denom0 == 0 or denom1 == 0:
        # Can't identify one of the transition probabilities — no evidence of clustering
        # but also no test. Return NaN so callers know.
        return float("nan"), float("nan")
    pi01 = n01 / denom0
    pi11 = n11 / denom1
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)

    def _llik(p01: float, p11: float) -> float:
        # Log-likelihood of observing this transition sequence given probabilities
        terms = [
            n00 * np.log(max(1 - p01, 1e-12)),
            n01 * np.log(max(p01, 1e-12)),
            n10 * np.log(max(1 - p11, 1e-12)),
            n11 * np.log(max(p11, 1e-12)),
        ]
        return float(sum(terms))

    ll_restricted = _llik(pi, pi)       # Under H0: π_01 = π_11 = π
    ll_unrestricted = _llik(pi01, pi11)  # Unrestricted
    lr = 2.0 * (ll_unrestricted - ll_restricted)
    p_val = 1.0 - chi2.cdf(max(lr, 0.0), df=1)
    return float(lr), float(p_val)


def _lr_conditional_coverage(violations: np.ndarray, claimed: float) -> tuple[float, float]:
    """Christoffersen conditional-coverage LR: combines Kupiec POF + independence.

    LR_cc = LR_uc + LR_ind  ~  χ²(2)  under H0 (correct rate AND no clustering).
    Returns (LR_cc, p_value).
    """
    lr_uc, _ = _lr_kupiec(violations, claimed)
    lr_ind, _ = _lr_christoffersen_independence(violations)
    if np.isnan(lr_uc) or np.isnan(lr_ind):
        return float("nan"), float("nan")
    lr_cc = lr_uc + lr_ind
    p_val = 1.0 - chi2.cdf(max(lr_cc, 0.0), df=2)
    return float(lr_cc), float(p_val)


def conditional_coverage_from_bounds(
    panel: pd.DataFrame,
    bounds: dict[float, pd.DataFrame],
    group_by: str | None = "symbol",
) -> pd.DataFrame:
    """Per-(claimed) Kupiec + Christoffersen + conditional-coverage tests.

    `group_by` controls the unit over which independence is tested. Default
    "symbol" respects the natural time-series ordering within each ticker
    (the standard approach — cross-symbol transitions are not meaningful).
    Pass None to pool.

    Returns a DataFrame with one row per claimed level:
        claimed, n, violations, violation_rate,
        lr_uc, p_uc,       -- Kupiec unconditional coverage
        lr_ind, p_ind,     -- Christoffersen independence
        lr_cc, p_cc        -- Combined conditional coverage
    """
    rows = []
    for cov, band in bounds.items():
        m = panel["mon_open"].notna() & band["lower"].notna() & band["upper"].notna()
        p = panel.loc[m].copy()
        b = band.loc[m]
        inside = (p["mon_open"] >= b["lower"]) & (p["mon_open"] <= b["upper"])
        violations_all = (~inside).astype(int).values

        if group_by is not None and group_by in p.columns:
            # Run independence test within each group separately then pool via summed LR
            # (equivalent to conditioning on the group — a reasonable approximation)
            lr_uc, p_uc = _lr_kupiec(violations_all, cov)
            lr_ind_sum, lr_ind_groups = 0.0, 0
            # Sort within group by time so transitions make sense
            p_sorted = p.sort_values([group_by, "fri_ts"])
            inside_sorted = inside.loc[p_sorted.index].values
            viol_sorted = (~inside_sorted.astype(bool)).astype(int)
            groups = p_sorted[group_by].values
            for g in pd.unique(groups):
                mask = groups == g
                lr_g, _ = _lr_christoffersen_independence(viol_sorted[mask])
                if not np.isnan(lr_g):
                    lr_ind_sum += lr_g
                    lr_ind_groups += 1
            lr_ind = lr_ind_sum if lr_ind_groups > 0 else float("nan")
            # Pooled across groups: sum of independent χ²(1) LRs is χ²(k)
            # but if we want a single p-value, test against χ²(k) where k = n_groups.
            if lr_ind_groups > 0:
                p_ind = 1.0 - chi2.cdf(max(lr_ind, 0.0), df=lr_ind_groups)
            else:
                p_ind = float("nan")
            # Combined CC: LR_uc (df=1) + summed LR_ind (df=k) → χ²(1 + k)
            if not np.isnan(lr_ind):
                lr_cc = lr_uc + lr_ind
                p_cc = 1.0 - chi2.cdf(max(lr_cc, 0.0), df=1 + lr_ind_groups)
            else:
                lr_cc, p_cc = float("nan"), float("nan")
        else:
            lr_uc, p_uc = _lr_kupiec(violations_all, cov)
            lr_ind, p_ind = _lr_christoffersen_independence(violations_all)
            lr_cc, p_cc = _lr_conditional_coverage(violations_all, cov)

        rows.append(
            {
                "claimed": float(cov),
                "n": int(m.sum()),
                "violations": int(violations_all.sum()),
                "violation_rate": float(violations_all.mean()),
                "expected_rate": float(1.0 - cov),
                "lr_uc": lr_uc,
                "p_uc": p_uc,
                "lr_ind": lr_ind,
                "p_ind": p_ind,
                "lr_cc": lr_cc,
                "p_cc": p_cc,
            }
        )
    return pd.DataFrame(rows)


def summarize(
    name: str,
    panel: pd.DataFrame,
    forecast: pd.DataFrame,
    coverage_levels: tuple[float, ...] = COVERAGE_LEVELS,
) -> pd.DataFrame:
    """Flat single-row summary suitable for stacking across forecasters."""
    cov = coverage_and_sharpness(panel, forecast, coverage_levels)
    acc = point_accuracy(panel, forecast)
    row: dict = {"forecaster": name, "n": acc["n"]}
    for _, r in cov.iterrows():
        pct = int(round(r["claimed"] * 100))
        row[f"cov{pct}_realized"] = r["realized"]
        row[f"cov{pct}_sharp_bps"] = r["sharpness_bps"]
    row["mae_bps"] = acc["mae_bps"]
    row["rmse_bps"] = acc["rmse_bps"]
    row["bias_bps"] = acc["median_bias_bps"]
    return pd.DataFrame([row])
