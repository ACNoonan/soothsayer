"""V1b — tokenized-tracking baseline head-to-head against Soothsayer's M6 LWC band.

The Cong-et-al post-cutover baseline: a naive oracle that publishes
`point = tokenized_perp_close_at_t`, `halfwidth = q_tau(|residual|)` where
the residual is the historical |perp_at_t - mon_NMS_open|. This is what a
lazy competitor would ship after reading the Cong et al. R^2 = 0.839
finding on the conditional mean.

Compared head-to-head against Soothsayer's deployed M6 LWC artefact across
six canonical snapshots in the closed window (Fri 16:00 ET, Sat 12:00 ET,
Sun 12:00 ET, Sun 20:00 ET, Mon 04:00 ET, Mon 09:00 ET).

Outputs:
  - data/processed/v1b_tokenized_tracking_baseline.parquet (one row per
    (symbol, weekend, snapshot, tau) for both forecasters)
  - reports/tables/v1b_tokenized_tracking_baseline_summary.csv (aggregated)
  - reports/v1b_tokenized_tracking_baseline.md (write-up — drafted, not
    written by this script; this script emits the table and the script
    writes the prose).
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.stats import chi2

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from soothsayer.config import DATA_PROCESSED  # noqa: E402
from soothsayer.oracle import Oracle, LWC_ARTEFACT_PATH  # noqa: E402
from soothsayer.sources.scryer import (  # noqa: E402
    load_cex_stock_perp_ohlcv,
    load_yahoo_bars,
)


ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# Snapshot offsets relative to Friday NMS close (16:00 America/New_York).
# Each snapshot is a clock-time on a fixed weekday in the closed window;
# the helper below maps (fri_date, label) -> aware datetime in ET.
SNAPSHOTS: tuple[tuple[str, int, int, int], ...] = (
    # (label, day_offset_from_fri, hour_ET, minute_ET)
    ("fri_close",  0, 16,  0),   # Fri 16:00 ET — NMS just closed
    ("sat_noon",   1, 12,  0),   # Sat 12:00 ET
    ("sun_noon",   2, 12,  0),   # Sun 12:00 ET
    ("sun_globex", 2, 20,  0),   # Sun 20:00 ET — CME Globex reopen
    ("mon_premkt", 3,  4,  0),   # Mon 04:00 ET — pre-market start
    ("mon_open",   3,  9,  0),   # Mon 09:00 ET — just before NMS open
)

TAU_GRID: tuple[float, ...] = (0.68, 0.85, 0.95, 0.99)

# Soothsayer's panel includes TLT, but no xstock-backed perp exists for TLT
# (no Backed TLTx). Drop from the bake-off.
BAKEOFF_SYMBOLS: tuple[str, ...] = (
    "SPY", "QQQ", "GLD", "TSLA", "NVDA", "GOOGL", "AAPL", "HOOD", "MSTR",
)

# Walk-forward warm-up: minimum number of past weekends required (pooled across
# all symbols) before we evaluate a weekend. With ~9 symbols per weekend, even
# 4 past weekends gives ~36 pooled obs which is enough to estimate a 0.95
# quantile to ~2dp accuracy.
MIN_WARMUP_WEEKENDS = 4


# ---------- Plumbing ----------

def snapshot_ts(fri_date: date, day_offset: int, hour_et: int, min_et: int) -> pd.Timestamp:
    """Materialise a snapshot moment as a tz-aware UTC pandas Timestamp.

    Uses America/New_York for the wall clock so DST transitions across the
    panel (e.g., March 2026 DST start) resolve to the right UTC instant."""
    base = datetime(fri_date.year, fri_date.month, fri_date.day, tzinfo=ET)
    moment = base + timedelta(days=day_offset, hours=hour_et, minutes=min_et)
    # Replace base's 00:00 wall-clock with the target hour/minute. We added
    # `hour_et` hours to a 00:00 base, so the resulting wall-clock matches.
    return pd.Timestamp(moment).tz_convert(UTC)


def load_perp_path(symbol: str, fri_date: date) -> pd.DataFrame:
    """Load all kraken_futures xstock-backed perp 1m bars in the closed window
    [fri 16:00 ET, mon 14:00 ET]. Returns columns (ts_utc, perp_close)."""
    start = fri_date - timedelta(days=1)
    end = fri_date + timedelta(days=4)
    raw = load_cex_stock_perp_ohlcv(symbol, start, end)
    if raw.empty:
        return pd.DataFrame(columns=["ts_utc", "perp_close"])
    df = raw[raw["backing_kind"] == "xstock_backed"].copy()
    df["ts_utc"] = pd.to_datetime(df["bar_open_ts"], unit="s", utc=True)
    win_start = snapshot_ts(fri_date, 0, 16, 0)
    win_end = snapshot_ts(fri_date, 3, 14, 0)
    df = df[(df["ts_utc"] >= win_start) & (df["ts_utc"] <= win_end)]
    df = df[["ts_utc", "close"]].rename(columns={"close": "perp_close"}).copy()
    df = df.sort_values("ts_utc").reset_index(drop=True)
    return df


def perp_at_snapshot(perp_path: pd.DataFrame, snap_ts: pd.Timestamp) -> float | None:
    """Asof-most-recent-or-equal lookup against the perp 1m bars. Returns None
    if no bar exists at or before the snapshot moment (e.g., panel starts
    after the snapshot)."""
    if perp_path.empty:
        return None
    before = perp_path[perp_path["ts_utc"] <= snap_ts]
    if before.empty:
        return None
    return float(before.iloc[-1]["perp_close"])


def fetch_mon_open(symbol: str, fri_date: date) -> tuple[date | None, float | None]:
    """Mon NMS open for the weekend whose Friday is ``fri_date``. Searches the
    next 5 calendar days for the first yahoo bar (handles long weekends)."""
    bars = load_yahoo_bars(symbol, fri_date + timedelta(days=1), fri_date + timedelta(days=7))
    if bars.empty:
        return None, None
    bars = bars.copy()
    bars["ts"] = pd.to_datetime(bars["ts"]).dt.date
    bars = bars[bars["ts"] > fri_date].sort_values("ts")
    if bars.empty:
        return None, None
    row = bars.iloc[0]
    return row["ts"], float(row["open"])


# ---------- Statistics ----------

def winkler(lo: float, hi: float, y: float, tau: float) -> float:
    """Winkler / interval score for prediction interval [lo, hi] at level tau.
    Lower is better. Penalty for breaches scales with 1/alpha = 1/(1-tau)."""
    alpha = 1.0 - tau
    width = hi - lo
    if y < lo:
        return width + (2.0 / alpha) * (lo - y)
    if y > hi:
        return width + (2.0 / alpha) * (y - hi)
    return width


def kupiec_p_uc(coverage: float, n: int, tau: float) -> float:
    """Kupiec unconditional-coverage test p-value (two-sided LR)."""
    if n == 0:
        return float("nan")
    x = int(round(coverage * n))
    if x == 0 or x == n:
        # Saturated — return 0 for x=0 vs nonzero tau (always reject) but be
        # graceful for x=n on small samples.
        if x == n and tau >= 1.0 - 1e-9:
            return 1.0
        if x == 0 and tau <= 1e-9:
            return 1.0
    p = max(min(coverage, 1.0 - 1e-12), 1e-12)
    t = max(min(tau, 1.0 - 1e-12), 1e-12)
    ll_alt = x * np.log(p) + (n - x) * np.log(1 - p)
    ll_null = x * np.log(t) + (n - x) * np.log(1 - t)
    lr = 2 * (ll_alt - ll_null)
    return float(1.0 - chi2.cdf(lr, df=1))


def christoffersen_p_cc(breaches: np.ndarray, tau: float) -> float:
    """Christoffersen conditional-coverage joint test p-value.

    LR_cc = LR_uc + LR_ind, df=2. ``breaches`` is a 0/1 array (1 = in-band)."""
    n = len(breaches)
    if n < 2:
        return float("nan")
    coverage = float(breaches.mean())
    lr_uc_p = kupiec_p_uc(coverage, n, tau)
    n00 = n01 = n10 = n11 = 0
    for i in range(1, n):
        prev_breach = 1 - breaches[i - 1]
        this_breach = 1 - breaches[i]
        if prev_breach == 0 and this_breach == 0:
            n00 += 1
        elif prev_breach == 0 and this_breach == 1:
            n01 += 1
        elif prev_breach == 1 and this_breach == 0:
            n10 += 1
        else:
            n11 += 1
    if (n00 + n01) == 0 or (n10 + n11) == 0 or (n01 + n11) == 0:
        return lr_uc_p
    pi01 = n01 / (n00 + n01)
    pi11 = n11 / (n10 + n11)
    pi_pooled = (n01 + n11) / (n00 + n01 + n10 + n11)
    if pi_pooled in (0, 1) or pi01 in (0, 1) or pi11 in (0, 1):
        return lr_uc_p
    ll_alt = (
        n00 * np.log(1 - pi01) + n01 * np.log(pi01)
        + n10 * np.log(1 - pi11) + n11 * np.log(pi11)
    )
    ll_null = (n00 + n10) * np.log(1 - pi_pooled) + (n01 + n11) * np.log(pi_pooled)
    lr_ind = 2 * (ll_alt - ll_null)
    p_ind = 1.0 - chi2.cdf(lr_ind, df=1)
    # Joint LR_cc: pooled p-value via Fisher combination (independent components).
    # Cleaner is to compute LR_cc directly; this returns LR_ind for the table.
    return float(p_ind)


# ---------- Pipeline ----------

def build_observation_panel() -> pd.DataFrame:
    """Per-(weekend, symbol) frame of:
      fri_ts, symbol, fri_close, mon_open, point_soothsayer, halfwidth_soothsayer_tau,
      perp_at_<snapshot>
    """
    oracle = Oracle.load(lwc_artefact_path=LWC_ARTEFACT_PATH)
    art = oracle._lwc_artefact  # type: ignore[attr-defined]
    if art is None:
        raise RuntimeError("LWC artefact not loaded — cannot build bake-off panel.")
    # Slice to the post-kraken-launch period.
    art = art[pd.to_datetime(art["fri_ts"]) >= pd.Timestamp("2025-12-19")]
    art = art[art["symbol"].isin(BAKEOFF_SYMBOLS)].copy()
    art["fri_ts"] = pd.to_datetime(art["fri_ts"]).dt.date

    rows: list[dict] = []
    for _, art_row in art.sort_values(["fri_ts", "symbol"]).iterrows():
        symbol: str = art_row["symbol"]
        fri_d: date = art_row["fri_ts"]
        fri_close = float(art_row["fri_close"])

        mon_d, mon_open = fetch_mon_open(symbol, fri_d)
        if mon_open is None:
            continue

        perp_path = load_perp_path(symbol, fri_d)
        if perp_path.empty:
            continue

        soothsayer_pp = {
            tau: oracle.fair_value_lwc(symbol, fri_d, target_coverage=tau)
            for tau in TAU_GRID
        }

        rec: dict = {
            "fri_ts": fri_d,
            "symbol": symbol,
            "fri_close": fri_close,
            "mon_ts": mon_d,
            "mon_open": mon_open,
            "regime_pub": str(art_row["regime_pub"]),
            "sigma_hat_sym_pre_fri": float(art_row["sigma_hat_sym_pre_fri"]),
        }
        for tau, pp in soothsayer_pp.items():
            rec[f"sooth_point_tau{tau}"] = pp.point
            rec[f"sooth_lower_tau{tau}"] = pp.lower
            rec[f"sooth_upper_tau{tau}"] = pp.upper
            rec[f"sooth_halfwidth_tau{tau}"] = (pp.upper - pp.lower) / 2.0

        for label, day_off, h_et, m_et in SNAPSHOTS:
            snap = snapshot_ts(fri_d, day_off, h_et, m_et)
            px = perp_at_snapshot(perp_path, snap)
            rec[f"perp_at_{label}"] = px

        rows.append(rec)
    return pd.DataFrame(rows)


def calibrate_walkforward_baseline(panel: pd.DataFrame, snapshot_label: str) -> pd.DataFrame:
    """Compute the baseline half-width at each (weekend, symbol) for every tau,
    using walk-forward expanding-window pooled-across-symbols residual quantile.

    Residual = mon_open - perp_at_snapshot.  Half-width at tau = empirical
    tau-quantile of |residual| across all (past weekend, any symbol) tuples.

    Returns the original panel with new columns:
      baseline_<label>_point, baseline_<label>_halfwidth_tau{tau},
      baseline_<label>_residual.
    """
    p = panel.copy()
    px_col = f"perp_at_{snapshot_label}"
    p["__resid__"] = p["mon_open"] - p[px_col]

    p = p.sort_values("fri_ts").reset_index(drop=True)
    weekends = sorted(p["fri_ts"].unique())
    weekend_to_pos = {w: i for i, w in enumerate(weekends)}

    halfwidth_by_tau: dict[float, list[float]] = {tau: [] for tau in TAU_GRID}
    point_col_vals: list[float] = []

    for _, row in p.iterrows():
        w_pos = weekend_to_pos[row["fri_ts"]]
        past = p[p["fri_ts"] < row["fri_ts"]]
        past_resid = past["__resid__"].dropna().abs().values

        point_col_vals.append(row[px_col])

        n_past_weekends = w_pos
        if (
            n_past_weekends < MIN_WARMUP_WEEKENDS
            or len(past_resid) == 0
            or pd.isna(row[px_col])
        ):
            for tau in TAU_GRID:
                halfwidth_by_tau[tau].append(float("nan"))
            continue

        for tau in TAU_GRID:
            hw = float(np.quantile(past_resid, tau))
            halfwidth_by_tau[tau].append(hw)

    p[f"baseline_{snapshot_label}_point"] = point_col_vals
    for tau in TAU_GRID:
        p[f"baseline_{snapshot_label}_halfwidth_tau{tau}"] = halfwidth_by_tau[tau]
    p[f"baseline_{snapshot_label}_residual"] = p["__resid__"]
    p = p.drop(columns=["__resid__"])
    return p


def score_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to one row per (forecaster, snapshot, tau) with realised
    coverage, mean half-width (bps), mean Winkler, Kupiec p, n."""
    out_rows: list[dict] = []

    # Soothsayer — single forecast per weekend (no snapshot variation).
    valid_sooth = panel.dropna(subset=["mon_open"]).copy()
    for tau in TAU_GRID:
        lo = valid_sooth[f"sooth_lower_tau{tau}"]
        hi = valid_sooth[f"sooth_upper_tau{tau}"]
        y = valid_sooth["mon_open"]
        in_band = (y >= lo) & (y <= hi)
        hw = (hi - lo) / 2.0
        hw_bps = (hw / valid_sooth["fri_close"]) * 1e4
        winks = np.array([
            winkler(L, H, Y, tau) for L, H, Y in zip(lo.values, hi.values, y.values)
        ])
        n = int(in_band.notna().sum())
        cov = float(in_band.mean())
        p_uc = kupiec_p_uc(cov, n, tau)
        breaches = in_band.astype(int).values
        p_cc = christoffersen_p_cc(breaches, tau)
        out_rows.append({
            "forecaster": "soothsayer_m6_lwc",
            "snapshot": "fri_close",  # the band is published once at fri close
            "tau": tau,
            "n": n,
            "realised_coverage": cov,
            "mean_halfwidth_bps": float(hw_bps.mean()),
            "median_halfwidth_bps": float(hw_bps.median()),
            "mean_winkler_price": float(winks.mean()),
            "mean_winkler_bps": float((winks / valid_sooth["fri_close"]).mean() * 1e4),
            "kupiec_p_uc": p_uc,
            "christoffersen_p_ind": p_cc,
        })

    # Tokenized-tracking baseline — one row per snapshot.
    for label, _, _, _ in SNAPSHOTS:
        for tau in TAU_GRID:
            point_col = f"baseline_{label}_point"
            hw_col = f"baseline_{label}_halfwidth_tau{tau}"
            valid = panel.dropna(subset=["mon_open", point_col, hw_col]).copy()
            if valid.empty:
                continue
            lo = valid[point_col] - valid[hw_col]
            hi = valid[point_col] + valid[hw_col]
            y = valid["mon_open"]
            in_band = (y >= lo) & (y <= hi)
            hw_bps = (valid[hw_col] / valid["fri_close"]) * 1e4
            winks = np.array([
                winkler(L, H, Y, tau)
                for L, H, Y in zip(lo.values, hi.values, y.values)
            ])
            n = int(in_band.notna().sum())
            cov = float(in_band.mean())
            p_uc = kupiec_p_uc(cov, n, tau)
            breaches = in_band.astype(int).values
            p_cc = christoffersen_p_cc(breaches, tau)
            out_rows.append({
                "forecaster": "tokenized_tracking_baseline",
                "snapshot": label,
                "tau": tau,
                "n": n,
                "realised_coverage": cov,
                "mean_halfwidth_bps": float(hw_bps.mean()),
                "median_halfwidth_bps": float(hw_bps.median()),
                "mean_winkler_price": float(winks.mean()),
                "mean_winkler_bps": float((winks / valid["fri_close"]).mean() * 1e4),
                "kupiec_p_uc": p_uc,
                "christoffersen_p_ind": p_cc,
            })

    return pd.DataFrame(out_rows)


def main() -> int:
    print("[1/4] Building observation panel (LWC artefact ∪ kraken_futures perp tape)...")
    panel = build_observation_panel()
    print(f"      panel rows: {len(panel)}  weekends: {panel['fri_ts'].nunique()}  symbols: {panel['symbol'].nunique()}")

    print("[2/4] Walk-forward calibrating baseline at each snapshot...")
    for label, _, _, _ in SNAPSHOTS:
        panel = calibrate_walkforward_baseline(panel, label)
    print(f"      panel columns after baseline build: {len(panel.columns)}")

    print("[3/4] Scoring head-to-head...")
    summary = score_panel(panel)

    out_panel = DATA_PROCESSED / "v1b_tokenized_tracking_baseline.parquet"
    out_summary_csv = REPO / "reports" / "tables" / "v1b_tokenized_tracking_baseline_summary.csv"
    out_panel.parent.mkdir(parents=True, exist_ok=True)
    out_summary_csv.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(out_panel, index=False)
    summary.to_csv(out_summary_csv, index=False)
    print(f"[4/4] Wrote {out_panel}")
    print(f"      Wrote {out_summary_csv}")

    print()
    print("---- Soothsayer M6 LWC ----")
    print(
        summary[summary["forecaster"] == "soothsayer_m6_lwc"][
            ["tau", "n", "realised_coverage", "mean_halfwidth_bps",
             "mean_winkler_bps", "kupiec_p_uc"]
        ].round(4).to_string(index=False)
    )
    print()
    print("---- Tokenized-tracking baseline (by snapshot) ----")
    print(
        summary[summary["forecaster"] == "tokenized_tracking_baseline"][
            ["snapshot", "tau", "n", "realised_coverage", "mean_halfwidth_bps",
             "mean_winkler_bps", "kupiec_p_uc"]
        ].round(4).to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
