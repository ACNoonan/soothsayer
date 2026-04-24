"""
Regime tagging for the weekend panel.

Each weekend is tagged with a single primary regime, rank-ordered by what most
affects the difficulty of forecasting Monday open. All tags here use only
pre-publish (Friday 16:00 ET) information — no look-ahead into Monday's realized
move. This is the only honest way to test whether a regime-aware forecaster
would widen CI before the event, not after.

  high_vol      — VIX at Friday close in top quartile of trailing 252-day window
  long_weekend  — gap_days >= 4 (holiday-extended)
  normal        — everything else

A separate `realized_bucket` tag (tertiles of |z-score| of the realized weekend
move) is added for post-hoc diagnostics — it quantifies forecaster behavior
given what actually happened, distinct from what could have been predicted.

Earnings and macro-event tags (FOMC, CPI) come in a later pass — they need
external calendars.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _realized_zscore(panel: pd.DataFrame) -> pd.Series:
    """|z-score| of the realized weekend log-return, scaled by Friday's 20d vol.

    This is POST-HOC — uses mon_open, so it's only for diagnostic bucketing of
    already-observed weekends, never for a pre-publish regime."""
    r = np.log(panel["mon_open"] / panel["fri_close"])
    z = r / panel["fri_vol_20d"].replace(0, np.nan)
    return z.abs()


def _high_vol_flag(panel: pd.DataFrame) -> pd.Series:
    """Flag weekends where VIX at Friday close is in the top quartile of its
    trailing 252-trading-day window, computed per fri_ts."""
    vix = panel[["fri_ts", "vix_fri_close"]].drop_duplicates().sort_values("fri_ts")
    rolling = vix["vix_fri_close"].rolling(52, min_periods=20).quantile(0.75)
    lookup = pd.Series(rolling.values, index=vix["fri_ts"].values)
    return panel["fri_ts"].map(lookup).lt(panel["vix_fri_close"]).fillna(False)


def tag(panel: pd.DataFrame) -> pd.DataFrame:
    """Add `regime_pub` and `realized_bucket` columns. Non-destructive."""
    out = panel.copy()
    high_vol = _high_vol_flag(out)

    regime_pub = pd.Series("normal", index=out.index, dtype=object)
    regime_pub.loc[out["gap_days"] >= 4] = "long_weekend"
    regime_pub.loc[high_vol] = "high_vol"  # overrides long_weekend if both — top priority
    out["regime_pub"] = regime_pub.values

    # Post-hoc realized-move tertile (calm / normal / shock) for diagnostic splits only
    z = _realized_zscore(out)
    try:
        q33, q67 = z.quantile([0.33, 0.67]).values
    except Exception:
        q33, q67 = 0.5, 1.0
    bucket = pd.Series("normal", index=out.index, dtype=object)
    bucket.loc[z < q33] = "calm"
    bucket.loc[z >= q67] = "shock"
    out["realized_bucket"] = bucket.values
    return out


def counts(panel: pd.DataFrame, column: str = "regime_pub") -> pd.DataFrame:
    return (
        panel.groupby(column)
        .size()
        .rename("n")
        .reset_index()
        .sort_values("n", ascending=False)
    )
