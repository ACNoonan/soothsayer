"""V1b — Jupiter-mid (v5/tape) cross-check of the tokenized-tracking bake-off.

Replays the §7.6 comparison against the Soothsayer M6 LWC band on the
Solana-DEX-mid surface (`soothsayer_v5/tape` jup_mid) rather than the
kraken_futures perp. Sample is tiny — 3 weekends overlap the v5 forward
tape (2026-04-24, 2026-05-01, 2026-05-08), one of which (2026-04-24) is
in the deployed LWC artefact directly and two of which (2026-05-01,
2026-05-08) require manual computation of the served band from the
existing sidecar constants + an EWMA HL=8 σ̂_sym(t) computed against the
forward-tape-extended panel.

This is a *confirmatory* cross-check, not a powered head-to-head. The
baseline halfwidth at each τ is borrowed verbatim from the primary
kraken_futures bake-off's `mon_open` snapshot (no re-fit on the 3
weekends — that would be in-sample on the panel we're evaluating). The
question this answers: does the directional result reproduce on the
direct on-chain (Jupiter quote) surface that a Solana-DEX consumer would
actually read?

Outputs:
  - reports/tables/paper1_c2_tokenized_tracking_v5_xcheck.csv
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from soothsayer.config import DATA_PROCESSED  # noqa: E402
from soothsayer.oracle import (  # noqa: E402
    Oracle, LWC_ARTEFACT_PATH,
    lwc_c_bump_for, lwc_delta_shift_for, lwc_regime_quantile_for,
    MAX_SERVED_TARGET, MIN_SERVED_TARGET,
)
from soothsayer.sources.scryer import load_v5_window, load_yahoo_bars  # noqa: E402
from soothsayer.universe import BY_SYMBOL  # noqa: E402


ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# v5 uses x-suffixed symbols; we work in underlying-ticker space for everything else.
V5_SYM_MAP: dict[str, str] = {
    "SPYx": "SPY", "QQQx": "QQQ",
    "AAPLx": "AAPL", "GOOGLx": "GOOGL", "NVDAx": "NVDA",
    "TSLAx": "TSLA", "MSTRx": "MSTR", "HOODx": "HOOD",
}

# Weekends to evaluate. fri_ts in the LWC artefact + the post-frozen extensions.
TARGET_FRI_TS: tuple[date, ...] = (
    date(2026, 4, 24),
    date(2026, 5, 1),
    date(2026, 5, 8),
)

TAU_GRID: tuple[float, ...] = (0.68, 0.85, 0.95, 0.99)

# Borrowed `k` (= empirical-quantile halfwidth) from the primary bake-off's
# mon_open snapshot, pooled across symbols. Loaded from the primary summary
# CSV at run time so this stays in sync with the primary runner.


def fri_close_moment(fri_date: date) -> pd.Timestamp:
    base = datetime(fri_date.year, fri_date.month, fri_date.day, 16, 0, tzinfo=ET)
    return pd.Timestamp(base).tz_convert(UTC)


def mon_open_moment(fri_date: date) -> pd.Timestamp:
    # Mon 09:30 ET — handles long weekends by stepping +3 calendar days from
    # the Friday. For long weekends the underlying's actual reopen-day differs;
    # we use yahoo's first post-Friday bar's date for that. This is only used
    # to bound the v5 snapshot search window.
    base = datetime(fri_date.year, fri_date.month, fri_date.day, 9, 30, tzinfo=ET)
    return pd.Timestamp(base + timedelta(days=3)).tz_convert(UTC)


def fetch_mon_open(symbol: str, fri_date: date) -> tuple[date | None, float | None]:
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


def served_lwc_band(symbol: str, fri_date: date, tau: float, oracle: Oracle,
                    extended_lookup: pd.DataFrame) -> dict | None:
    """Serve the M6 LWC band for any fri_ts. For fri_ts present in the
    deployed artefact, delegates to Oracle.fair_value_lwc. For forward fri_ts,
    looks up the row in `extended_lookup` and computes the band manually using
    the existing sidecar constants (no re-fit; preserves deployed serving)."""
    try:
        pp = oracle.fair_value_lwc(symbol, fri_date, target_coverage=tau)
        return {
            "point": pp.point, "lower": pp.lower, "upper": pp.upper,
            "regime": pp.regime, "fri_close": pp.diagnostics["fri_close"],
        }
    except ValueError:
        row = extended_lookup[
            (extended_lookup["symbol"] == symbol)
            & (extended_lookup["fri_ts"] == fri_date)
        ]
        if row.empty:
            return None
        r = row.iloc[0]
        regime = str(r["regime_pub"])
        fri_close = float(r["fri_close"])
        point = float(r["point"])
        sigma_hat = float(r["sigma_hat_sym_pre_fri"])
        tau_clipped = max(min(tau, MAX_SERVED_TARGET), MIN_SERVED_TARGET)
        delta = lwc_delta_shift_for(tau_clipped)
        served_target = min(tau_clipped + delta, MAX_SERVED_TARGET)
        c_bump = lwc_c_bump_for(served_target)
        q_regime = lwc_regime_quantile_for(regime, served_target)
        q_eff = c_bump * q_regime
        half = q_eff * sigma_hat * fri_close
        return {
            "point": point, "lower": point - half, "upper": point + half,
            "regime": regime, "fri_close": fri_close,
        }


def build_extended_lookup() -> pd.DataFrame:
    """For the forward fri_ts (2026-05-01, 2026-05-08), build a per-Friday
    lookup row with (symbol, fri_ts, regime_pub, fri_close, point, sigma_hat).
    σ̂ is EWMA HL=8 of |residual|/fri_close over past weekends of the same
    symbol, computed against (frozen panel ∪ forward-tape rows up to but not
    including the target fri_ts).
    """
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    ft = pd.read_parquet(DATA_PROCESSED / "forward_tape_v1.parquet")
    # Project both to the columns we need.
    keep = ["symbol", "fri_ts", "fri_close", "mon_open", "regime_pub", "factor_ret"]
    panel = panel[keep].copy()
    ft = ft[keep].copy()
    # forward_tape covers some rows already in the panel (2025-04→2026-04). Keep panel
    # for those and add forward rows from the tape for fri_ts > panel max.
    panel_max = pd.to_datetime(panel["fri_ts"]).max().date()
    ft["fri_ts"] = pd.to_datetime(ft["fri_ts"]).dt.date
    extra = ft[ft["fri_ts"] > panel_max].copy()
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    combined = pd.concat([panel, extra], ignore_index=True).sort_values(["symbol", "fri_ts"])
    combined = combined.dropna(subset=["fri_close", "mon_open", "regime_pub", "factor_ret"])
    combined["resid_rel"] = (combined["mon_open"] - combined["fri_close"]) / combined["fri_close"]
    combined["abs_resid_rel"] = combined["resid_rel"].abs()

    # EWMA HL=8 per symbol, strictly pre-Friday (shift by 1 then ewm).
    out_chunks = []
    for sym, g in combined.groupby("symbol"):
        g = g.sort_values("fri_ts").copy()
        sigma_hat = (
            g["abs_resid_rel"].shift(1).ewm(halflife=8, adjust=False).mean()
        )
        g["sigma_hat_sym_pre_fri"] = sigma_hat
        out_chunks.append(g)
    combined = pd.concat(out_chunks).sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    combined["point"] = combined["fri_close"] * (1.0 + combined["factor_ret"])
    return combined


def main() -> int:
    print("[1/4] Building extended LWC lookup (frozen panel + forward-tape forward weekends)...", flush=True)
    lookup = build_extended_lookup()
    print(f"      lookup rows: {len(lookup):,}  syms: {lookup['symbol'].nunique()}", flush=True)
    print(f"      fri_ts max: {pd.to_datetime(lookup['fri_ts']).max().date()}", flush=True)

    oracle = Oracle.load(lwc_artefact_path=LWC_ARTEFACT_PATH)

    # Borrow baseline halfwidth from the primary bake-off summary (mon_open snapshot)
    primary = pd.read_csv(REPO / "reports" / "tables" / "paper1_c2_tokenized_tracking_baseline_summary.csv")
    base_mon = primary[(primary["forecaster"] == "tokenized_tracking_baseline")
                       & (primary["snapshot"] == "mon_open")].set_index("tau")
    print(f"[2/4] Borrowed baseline halfwidth (bps) from primary mon_open snapshot:")
    print(f"      {base_mon[['mean_hw_bps']].round(1).to_dict()}", flush=True)

    print("[3/4] Loading v5 tape, finding mon_open jup_mid for each (symbol, fri_ts)...", flush=True)
    v5 = load_v5_window("2026-04-23", "2026-05-12")
    v5 = v5[v5["jup_err"] == ""].copy()
    v5["ts_utc"] = pd.to_datetime(v5["poll_ts"], unit="s", utc=True)

    rows: list[dict] = []
    for fri_d in TARGET_FRI_TS:
        mon_snap = mon_open_moment(fri_d)
        # Use the v5 row most-recently-before Mon 09:00 ET.
        for v5sym, undsym in V5_SYM_MAP.items():
            mon_ts, mon_px = fetch_mon_open(undsym, fri_d)
            if mon_ts is None:
                continue
            v5sub = v5[(v5["symbol"] == v5sym) & (v5["ts_utc"] <= mon_snap)]
            v5sub = v5sub[v5sub["ts_utc"] >= fri_close_moment(fri_d)]
            if v5sub.empty:
                continue
            v5_mon_jup = float(v5sub.sort_values("ts_utc").iloc[-1]["jup_mid"])

            for tau in TAU_GRID:
                soothsayer = served_lwc_band(undsym, fri_d, tau, oracle, lookup)
                if soothsayer is None:
                    continue
                # Baseline: point = v5_mon_jup, halfwidth = borrowed primary baseline hw_bps × fri_close
                fri_close = soothsayer["fri_close"]
                hw_bps = float(base_mon.loc[tau, "mean_hw_bps"])
                hw_price = hw_bps / 1e4 * fri_close
                base_lower, base_upper = v5_mon_jup - hw_price, v5_mon_jup + hw_price

                # Compute coverage and Winkler vs Mon NMS open.
                alpha = 1.0 - tau

                def wink(lo, hi, y, alpha):
                    width = hi - lo
                    if y < lo: return width + (2 / alpha) * (lo - y)
                    if y > hi: return width + (2 / alpha) * (y - hi)
                    return width

                s_lo, s_hi = soothsayer["lower"], soothsayer["upper"]
                s_in = (mon_px >= s_lo) and (mon_px <= s_hi)
                s_hw = (s_hi - s_lo) / 2.0
                s_wk = wink(s_lo, s_hi, mon_px, alpha)
                b_in = (mon_px >= base_lower) and (mon_px <= base_upper)
                b_hw = hw_price
                b_wk = wink(base_lower, base_upper, mon_px, alpha)
                rows.append({
                    "fri_ts": fri_d, "symbol": undsym, "tau": tau,
                    "fri_close": fri_close, "mon_open": mon_px, "v5_jup_mon": v5_mon_jup,
                    "sooth_lower": s_lo, "sooth_upper": s_hi, "sooth_in_band": s_in,
                    "sooth_hw_bps": s_hw / fri_close * 1e4,
                    "sooth_winkler_bps": s_wk / fri_close * 1e4,
                    "base_point_jup": v5_mon_jup, "base_lower": base_lower, "base_upper": base_upper,
                    "base_in_band": b_in, "base_hw_bps": b_hw / fri_close * 1e4,
                    "base_winkler_bps": b_wk / fri_close * 1e4,
                })
    panel = pd.DataFrame(rows)

    print("[4/4] Aggregating...", flush=True)
    if panel.empty:
        print("WARN: empty v5 cross-check panel — no overlap found.")
        return 1

    summary = panel.groupby("tau").agg(
        n=("symbol", "size"),
        sooth_cov=("sooth_in_band", "mean"),
        sooth_hw_bps=("sooth_hw_bps", "mean"),
        sooth_wk_bps=("sooth_winkler_bps", "mean"),
        base_cov=("base_in_band", "mean"),
        base_hw_bps=("base_hw_bps", "mean"),
        base_wk_bps=("base_winkler_bps", "mean"),
    ).reset_index()
    summary["wk_ratio"] = summary["base_wk_bps"] / summary["sooth_wk_bps"]

    out_csv = REPO / "reports" / "tables" / "paper1_c2_tokenized_tracking_v5_xcheck.csv"
    out_panel = DATA_PROCESSED / "v1b_tokenized_tracking_v5_xcheck.parquet"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_panel.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_csv, index=False)
    panel.to_parquet(out_panel, index=False)
    print(f"      Wrote {out_csv}")
    print(f"      Wrote {out_panel}")
    print()
    print(f"---- v5 jup_mid cross-check (n={int(summary['n'].iloc[0])}, weekends={panel['fri_ts'].nunique()}) ----")
    print(summary.round(3).to_string(index=False))
    print()
    print(f"Per-weekend symbol counts:")
    print(panel.groupby('fri_ts')['symbol'].nunique().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
