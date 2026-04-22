"""
V3 — Kraken xStock Perp Funding Rate Signal (H9).

Tests whether Kraken perp funding rate adds incremental predictive power
for the Monday-open gap, beyond a macro baseline of weekend BTC / ES /
sector-ETF returns.

Regressions (rows = (weekend, ticker)):

  baseline:    g_T ~ const + r_BTC_weekend + r_ES_weekend + r_XLK_Fri [ + ticker FE ]
  augmented:   g_T ~ ... + f_T_SunEvening

  g_T          = ln(P_mon_open / P_fri_close)  for the underlying
  r_BTC        = ln(BTC_mon_open / BTC_fri_close)
  r_ES         = ln(ES_mon_open / ES_fri_close)
  r_XLK_Fri    = XLK Friday daily return (close/prev_close)
  f_T          = Kraken perp funding at Sun 20:00 UTC for PF_{TICKER}XUSD

Gate: delta is significant at 5%, delta R² > 2% vs baseline.

Outputs:
  reports/figures/v3_funding_signal.png
  reports/tables/v3_coefficients.csv
  reports/v3_funding_signal.md
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, time as dt_time

import numpy as np
import pandas as pd
import statsmodels.api as sm

from soothsayer.config import REPORTS
from soothsayer.sources.kraken_perp import fetch_funding, to_perp_symbol
from soothsayer.sources.yahoo import fetch_daily, weekend_pairs
from soothsayer.universe import CORE_XSTOCKS

FIG_DIR = REPORTS / "figures"
TABLE_DIR = REPORTS / "tables"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

# Sunday 20:00 UTC as the "Sun-evening" funding snapshot (late weekend, pre-Asia open).
FUNDING_OFFSET_FROM_MON = timedelta(hours=-14, minutes=-30)  # mon_open_ts - 14h30m -> Sun 20:00 UTC (EDT)


def daily_lookup(df: pd.DataFrame) -> tuple[dict, dict]:
    """Build (symbol, date) -> close and (symbol, date) -> open lookups."""
    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"]).dt.date
    fri_close = df.set_index(["symbol", "ts"])["close"].to_dict()
    mon_open = df.set_index(["symbol", "ts"])["open"].to_dict()
    return fri_close, mon_open


def mon_open_utc_ts(mon_date: date) -> int:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    dt_et = datetime.combine(mon_date, dt_time(9, 30), tzinfo=ET)
    return int(dt_et.astimezone(UTC).timestamp())


def funding_at_sun_evening(funding_df: pd.DataFrame, mon_date: date) -> float | None:
    """Pick the Kraken funding rate at Sunday 20:00 UTC (close to the hour) for a given weekend."""
    target = datetime.combine(mon_date, dt_time(9, 30), tzinfo=UTC) + FUNDING_OFFSET_FROM_MON
    target = target.replace(minute=0, second=0, microsecond=0)
    target_pd = pd.Timestamp(target)
    # Find the observation closest to target (same hour)
    exact = funding_df[funding_df["ts"] == target_pd]
    if not exact.empty:
        return float(exact["funding_rate"].iloc[0])
    return None


def main() -> None:
    tickers = [x.underlying for x in CORE_XSTOCKS]
    exog = ["BTC-USD", "ES=F", "XLK"]
    print(f"pulling daily bars for {len(tickers)} underlyings + {len(exog)} exogenous...", flush=True)
    daily = fetch_daily(tickers + exog, start=date(2025, 12, 1), end=date.today())
    print(f"  got {len(daily)} rows across {daily['symbol'].nunique()} tickers", flush=True)

    fri_close, mon_open = daily_lookup(daily)

    # Friday return of XLK
    xlk = daily[daily["symbol"] == "XLK"].sort_values("ts").reset_index(drop=True).copy()
    xlk["ts"] = pd.to_datetime(xlk["ts"]).dt.date
    xlk["prev_close"] = xlk["close"].shift(1)
    xlk["r_fri"] = np.log(xlk["close"] / xlk["prev_close"])
    xlk_fri_return = dict(zip(xlk["ts"], xlk["r_fri"]))

    # Build weekend pairs using SPY (same calendar for all underlyings)
    spy = daily[daily["symbol"] == "SPY"].sort_values("ts").reset_index(drop=True)
    pairs = weekend_pairs(spy)
    # Require weekend ends AFTER the earliest Kraken listing so every row has a funding value
    pairs = pairs[pairs["mon_ts"] >= date(2025, 12, 22)].reset_index(drop=True)
    print(f"  weekend pairs: {len(pairs)}", flush=True)

    # Pull Kraken funding history for our 8 tickers
    print("pulling Kraken funding history...", flush=True)
    funding: dict[str, pd.DataFrame] = {}
    for t in tickers:
        perp = to_perp_symbol(f"{t}x")
        try:
            funding[t] = fetch_funding(perp)
            print(f"  {t} ({perp}): {len(funding[t])} rows, from {funding[t]['ts'].min()}", flush=True)
        except Exception as e:
            print(f"  {t} ({perp}): {e}", flush=True)
            funding[t] = pd.DataFrame()

    rows: list[dict] = []
    for _, row in pairs.iterrows():
        fri_date = row["fri_ts"]
        mon_date = row["mon_ts"]
        # Weekend exogenous returns (daily-bar approximations)
        btc_fri = fri_close.get(("BTC-USD", fri_date))
        btc_mon = mon_open.get(("BTC-USD", mon_date))
        es_fri = fri_close.get(("ES=F", fri_date))
        es_mon = mon_open.get(("ES=F", mon_date))
        if None in (btc_fri, btc_mon, es_fri, es_mon) or any(pd.isna(v) for v in (btc_fri, btc_mon, es_fri, es_mon)):
            continue
        r_btc = float(np.log(btc_mon / btc_fri))
        r_es = float(np.log(es_mon / es_fri))
        r_xlk = xlk_fri_return.get(fri_date)
        if r_xlk is None or pd.isna(r_xlk):
            continue

        for t in tickers:
            underlying_fri = fri_close.get((t, fri_date))
            underlying_mon = mon_open.get((t, mon_date))
            if underlying_fri is None or underlying_mon is None or pd.isna(underlying_fri) or pd.isna(underlying_mon):
                continue
            g_T = float(np.log(underlying_mon / underlying_fri))

            f_ts = funding.get(t)
            f_sun = funding_at_sun_evening(f_ts, mon_date) if f_ts is not None and not f_ts.empty else None
            rows.append(
                {
                    "weekend_mon": mon_date,
                    "ticker": t,
                    "g_T": g_T,
                    "r_btc": r_btc,
                    "r_es": r_es,
                    "r_xlk_fri": float(r_xlk),
                    "funding_sun": f_sun,
                }
            )

    df = pd.DataFrame(rows)
    print(f"\nassembled {len(df)} (weekend, ticker) rows", flush=True)
    print(f"coverage (rows per ticker): {df.groupby('ticker').size().to_dict()}")
    print(f"funding availability: {df['funding_sun'].notna().sum()}/{len(df)} rows")

    # Baseline regression (drop rows with missing exogenous only)
    base_df = df.dropna(subset=["g_T", "r_btc", "r_es", "r_xlk_fri"]).copy()
    # Add ticker fixed effects
    base_df = pd.get_dummies(base_df, columns=["ticker"], drop_first=True, prefix="tk")
    exog_base = ["r_btc", "r_es", "r_xlk_fri"] + [c for c in base_df.columns if c.startswith("tk_")]
    X_base = sm.add_constant(base_df[exog_base].astype(float))
    y_base = base_df["g_T"].astype(float)
    res_base = sm.OLS(y_base, X_base).fit()

    # Augmented regression — only rows with funding
    aug_df = base_df.dropna(subset=["funding_sun"]).copy()
    exog_aug = exog_base + ["funding_sun"]
    X_aug = sm.add_constant(aug_df[exog_aug].astype(float))
    y_aug = aug_df["g_T"].astype(float)
    res_aug = sm.OLS(y_aug, X_aug).fit()

    # Re-fit baseline on the AUGMENTED sample for an apples-to-apples ΔR²
    X_base_same = sm.add_constant(aug_df[exog_base].astype(float))
    res_base_same = sm.OLS(y_aug, X_base_same).fit()

    delta = float(res_aug.params["funding_sun"])
    delta_se = float(res_aug.bse["funding_sun"])
    delta_t = float(res_aug.tvalues["funding_sun"])
    delta_p = float(res_aug.pvalues["funding_sun"])
    r2_base = float(res_base_same.rsquared)
    r2_aug = float(res_aug.rsquared)
    dr2 = r2_aug - r2_base

    print("\n=== baseline (on augmented sample) ===")
    print(f"  n={int(res_base_same.nobs)}  R²={r2_base:.4f}  adj-R²={res_base_same.rsquared_adj:.4f}")
    print("\n=== augmented ===")
    print(f"  n={int(res_aug.nobs)}  R²={r2_aug:.4f}  adj-R²={res_aug.rsquared_adj:.4f}")
    print(f"  delta = {delta:+.5f}  SE={delta_se:.5f}  t={delta_t:+.3f}  p={delta_p:.4f}")
    print(f"  ΔR² = {dr2*100:+.2f} percentage points")

    # Per-ticker regressions on the augmented spec (no FE — one ticker at a time)
    per_ticker_rows = []
    for t in tickers:
        sub = df[(df["ticker"] == t) & df[["r_btc", "r_es", "r_xlk_fri", "funding_sun"]].notna().all(axis=1)]
        if len(sub) < 6:
            per_ticker_rows.append({"ticker": t, "n": len(sub), "delta": np.nan, "se": np.nan, "p": np.nan, "dR2": np.nan})
            continue
        X_b = sm.add_constant(sub[["r_btc", "r_es", "r_xlk_fri"]].astype(float))
        X_a = sm.add_constant(sub[["r_btc", "r_es", "r_xlk_fri", "funding_sun"]].astype(float))
        r_b = sm.OLS(sub["g_T"].astype(float), X_b).fit()
        r_a = sm.OLS(sub["g_T"].astype(float), X_a).fit()
        per_ticker_rows.append(
            {
                "ticker": t,
                "n": int(r_a.nobs),
                "delta": float(r_a.params["funding_sun"]),
                "se": float(r_a.bse["funding_sun"]),
                "p": float(r_a.pvalues["funding_sun"]),
                "dR2": float(r_a.rsquared - r_b.rsquared),
            }
        )
    per = pd.DataFrame(per_ticker_rows)
    print("\n=== per-ticker ===")
    print(per.round({"delta": 5, "p": 4, "dR2": 4}).to_string(index=False))

    # Outputs
    per.to_csv(TABLE_DIR / "v3_coefficients.csv", index=False)
    print(f"wrote {TABLE_DIR/'v3_coefficients.csv'}")

    # Plot
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.5))
    pd_ = per.dropna(subset=["delta"]).sort_values("delta").copy()
    ax.errorbar(pd_["ticker"], pd_["delta"], yerr=1.96 * pd_["se"],
                fmt="o", capsize=4, color="#1f77b4", ecolor="#888")
    ax.axhline(0, color="gray", ls="--", alpha=0.5)
    ax.set_ylabel("δ (Monday log-gap per unit funding rate)")
    ax.set_title(f"V3 — per-ticker funding coefficient (pooled δ={delta:+.5f}, "
                 f"p={delta_p:.3f}, ΔR²={dr2*100:+.2f} pp)")
    fig.tight_layout()
    fig_path = FIG_DIR / "v3_funding_signal.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)
    print(f"wrote {fig_path}")

    # Writeup
    passed = delta_p < 0.05 and dr2 > 0.02
    decision = (
        "**PASS** — funding is an additive weekend-gap signal. Add to MVP ingest."
        if passed
        else f"**FAIL** — funding is not adding meaningful signal (δ p={delta_p:.3f}, "
        f"ΔR²={dr2*100:+.2f} pp). Keep as backup input only."
    )
    lines = [
        "# V3 — Kraken Perp Funding Rate as a Weekend-Gap Signal",
        "",
        "**Hypothesis (H9):** Kraken xStock perp funding rate at Sunday evening predicts the "
        "Monday-open gap for the underlying, beyond what weekend BTC / ES / sector-ETF returns alone predict.",
        "",
        "**Gate:** δ significant at 5% **and** ΔR² > 2 pp vs baseline.",
        "",
        "**Specification:**",
        "- baseline:   `g_T = α + β_BTC * r_BTC_weekend + β_ES * r_ES_weekend + β_XLK * r_XLK_Fri + ticker FE`",
        "- augmented:  baseline + `δ * f_Sun20UTC`",
        "",
        f"**Sample:** {int(res_aug.nobs)} (weekend, ticker) rows across 8 xStock underlyings; "
        f"earliest Kraken listing Dec 17 2025 (SPY/QQQ/GLD) and Feb 6 2026 (others).",
        "",
        "## Pooled result (ticker-FE OLS)",
        "",
        "| sample | n | R² | adj-R² |",
        "|---|---|---|---|",
        f"| baseline (same-sample) | {int(res_base_same.nobs)} | {r2_base:.4f} | {res_base_same.rsquared_adj:.4f} |",
        f"| augmented | {int(res_aug.nobs)} | {r2_aug:.4f} | {res_aug.rsquared_adj:.4f} |",
        "",
        f"**δ (funding coefficient)** = {delta:+.5f}  (SE {delta_se:.5f}, t {delta_t:+.3f}, p {delta_p:.4f})",
        f"  \n**ΔR²** = {dr2*100:+.2f} percentage points",
        "",
        "## Per-ticker",
        "",
        per.round({"delta": 5, "p": 4, "dR2": 4}).to_markdown(index=False),
        "",
        "## Decision",
        "",
        decision,
        "",
        "![V3 per-ticker funding coefficient](figures/v3_funding_signal.png)",
    ]
    report_path = REPORTS / "v3_funding_signal.md"
    report_path.write_text("\n".join(lines))
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
