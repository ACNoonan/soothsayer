"""
Path-coverage diagnostic for Paper 1 §6.x.

Endpoint coverage (the headline of §6) measures whether the realised Monday
open lies inside the served band. A protocol consuming Soothsayer over the
weekend cares about a stronger property: whether the *intra-weekend price
path* ever leaves the band. A liquidation triggered on Saturday afternoon
when an on-chain xStock briefly traded outside the band is a real loss
event even if Monday open returns inside.

This script computes two complementary path-coverage measures against the
deployed M5 artefact:

  (A) CME-implied underlier path on the full 12-year panel.
      For each (symbol, weekend), use the per-symbol futures factor (ES=F /
      GC=F / ZN=F) 1m bars in [Fri 16:00 ET, Mon 09:30 ET], scale by
      `fri_close / F_anchor` to project an underlier-equivalent path, and
      check whether the path ever exits the served band. The Globex Friday
      17:00 ET → Sunday 18:00 ET dark window is unobservable from CME and
      reported as a coverage gap (path_observable_share).

      MSTR post-2020-08 (BTC-USD factor) is excluded — no weekend BTC tape
      in scryer cache. ES=F coverage starts 2018, so the panel is
      2018-01-05 through 2026-04-17.

  (B) On-chain xStock path on the post-launch slice.
      For each (symbol, weekend) where dex_xstock/swaps tape is live, use
      `price_per_xstock` directly (no scaling — the consumer-experienced
      object). Sample is small (post mid-2025 launch, scryer cache
      currently 2026-04 onward) but it is the right object for the DeFi
      consumer story.

Outputs:
  reports/tables/path_coverage_cme.csv         per (τ, regime) pooled
  reports/tables/path_coverage_cme_per_row.csv per (symbol, weekend, τ)
  reports/tables/path_coverage_onchain.csv     small post-launch sample
  reports/v1b_path_coverage.md                 paper-ready summary

The output is consumed by §6.x of `reports/paper1_coverage_inversion/`.
"""

from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

from soothsayer.config import DATA_PROCESSED, REPORTS, SCRYER_DATASET_ROOT
from soothsayer.oracle import (
    MAX_SERVED_TARGET,
    c_bump_for_target,
    delta_shift_for_target,
    regime_quantile_for,
)


ANCHORS = (0.68, 0.85, 0.95, 0.99)
NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# Windows. NYSE close is 16:00 ET; NYSE open is 09:30 ET. Long weekends use
# the actual mon_ts from the panel (which may be Tuesday / Wednesday).
WINDOW_START = dtime(16, 0)
WINDOW_END = dtime(9, 30)

# Per-symbol futures factor for the path proxy. Drops any symbol whose
# factor we cannot observe weekend-continuous from scryer.
FACTOR_FOR_PATH: dict[str, str] = {
    "SPY":   "ES=F",
    "QQQ":   "ES=F",
    "AAPL":  "ES=F",
    "GOOGL": "ES=F",
    "NVDA":  "ES=F",
    "TSLA":  "ES=F",
    "HOOD":  "ES=F",
    "MSTR":  "ES=F",   # only pre-2020-08; post-pivot rows are skipped
    "GLD":   "GC=F",
    "TLT":   "ZN=F",
}
MSTR_BTC_PIVOT = date(2020, 8, 1)


# ----------------------------------------------------------------- band serve

def serve_bands(artefact: pd.DataFrame) -> pd.DataFrame:
    """Vectorised serving formula across all anchors using the deployed
    M5 serving helpers (`soothsayer.oracle`). Mirrors `Oracle.fair_value`
    (amm profile) exactly:

        τ' = min(τ + δ(τ), 0.99)
        q_eff = c(τ') × q_r(τ')
        lower = point * (1 - q_eff); upper = point * (1 + q_eff)
    """
    out = artefact[["symbol", "fri_ts", "regime_pub", "fri_close", "point"]].copy()
    regimes = out["regime_pub"].astype(str).to_numpy()
    point = out["point"].astype(float).to_numpy()
    for tau in ANCHORS:
        tau_p = min(tau + delta_shift_for_target(tau), MAX_SERVED_TARGET)
        c = c_bump_for_target(tau_p)
        q_r = np.array([regime_quantile_for(r, tau_p) for r in regimes])
        q_eff = c * q_r
        out[f"lower_{tau}"] = point * (1.0 - q_eff)
        out[f"upper_{tau}"] = point * (1.0 + q_eff)
        out[f"q_eff_{tau}"] = q_eff
    return out


# -------------------------------------------------------------- CME path read

def load_cme_factor(factor: str) -> pd.DataFrame:
    """All 1m bars for one futures factor across all available years."""
    root = SCRYER_DATASET_ROOT / "cme" / "intraday_1m" / "v1" / f"symbol={factor}"
    if not root.exists():
        raise FileNotFoundError(f"CME factor not in scryer cache: {factor}")
    d = ds.dataset(str(root), format="parquet", partitioning="hive")
    tbl = d.to_table(columns=["ts", "high", "low", "close"])
    df = tbl.to_pandas()
    df["ts"] = pd.to_numeric(df["ts"], downcast="integer")
    return df.sort_values("ts").reset_index(drop=True)


def weekend_window_utc(fri_ts: date, mon_ts: date) -> tuple[int, int]:
    start = datetime.combine(fri_ts, WINDOW_START, tzinfo=NY).astimezone(UTC)
    end = datetime.combine(mon_ts, WINDOW_END, tzinfo=NY).astimezone(UTC)
    return int(start.timestamp()), int(end.timestamp())


def cme_path_extrema(
    factor_bars: pd.DataFrame,
    fri_ts: date,
    mon_ts: date,
) -> tuple[float | None, float | None, float | None, int]:
    """Return (factor_anchor_close, path_low, path_high, n_bars).

    Anchor is the last bar at-or-before Friday 16:00 ET (the NYSE close
    timestamp the band is anchored to). path_low/path_high scan the entire
    [Fri 16:00, Mon 09:30] window; n_bars is the count of observed minutes
    (used to compute path_observable_share).
    """
    start_utc, end_utc = weekend_window_utc(fri_ts, mon_ts)
    in_window = factor_bars[(factor_bars["ts"] >= start_utc) & (factor_bars["ts"] <= end_utc)]
    if in_window.empty:
        return None, None, None, 0
    # Anchor = last close at-or-before start_utc + 60s (the bar that contains
    # 16:00 ET). Fall back to the first in-window bar if none precedes.
    pre = factor_bars[factor_bars["ts"] <= start_utc + 60]
    if pre.empty:
        anchor = float(in_window["close"].iloc[0])
    else:
        anchor = float(pre["close"].iloc[-1])
    return anchor, float(in_window["low"].min()), float(in_window["high"].max()), int(len(in_window))


# --------------------------------------------------------------- on-chain path

def load_xstock_swaps(xsymbol: str) -> pd.DataFrame:
    root = SCRYER_DATASET_ROOT / "dex_xstock" / "swaps" / "v1" / f"symbol={xsymbol}"
    if not root.exists():
        return pd.DataFrame(columns=["block_time", "price_per_xstock"])
    # rglob avoids picking up scryer's *.parquet.lock sentinels left by an
    # in-flight concurrent fetch (zero-byte files that crash pyarrow).
    files = [str(p) for p in sorted(root.rglob("*.parquet"))]
    if not files:
        return pd.DataFrame(columns=["block_time", "price_per_xstock"])
    d = ds.dataset(files, format="parquet")
    tbl = d.to_table(columns=["block_time", "price_per_xstock"])
    df = tbl.to_pandas()
    df = df[df["price_per_xstock"] > 0].sort_values("block_time").reset_index(drop=True)
    return df


def onchain_path_extrema(
    swaps: pd.DataFrame,
    fri_ts: date,
    mon_ts: date,
) -> tuple[float | None, float | None, int]:
    start_utc, end_utc = weekend_window_utc(fri_ts, mon_ts)
    w = swaps[(swaps["block_time"] >= start_utc) & (swaps["block_time"] <= end_utc)]
    if w.empty:
        return None, None, 0
    return float(w["price_per_xstock"].min()), float(w["price_per_xstock"].max()), int(len(w))


# ----------------------------------------------------------------- evaluation

def eval_cme_path(panel: pd.DataFrame, served: pd.DataFrame) -> pd.DataFrame:
    """Per-row CME-path coverage. One row per (symbol, weekend, τ)."""
    # Pre-load each factor once.
    factor_cache: dict[str, pd.DataFrame] = {}

    # Restrict to symbols we can proxy and to MSTR pre-pivot.
    base = panel.merge(served, on=["symbol", "fri_ts"], suffixes=("", "_art"))
    base = base[base["symbol"].isin(FACTOR_FOR_PATH)]
    base = base[~((base["symbol"] == "MSTR") & (base["fri_ts"] >= MSTR_BTC_PIVOT))]
    base["factor_used"] = base["symbol"].map(FACTOR_FOR_PATH)

    rows: list[dict] = []
    for _, row in base.iterrows():
        factor = row["factor_used"]
        if factor not in factor_cache:
            factor_cache[factor] = load_cme_factor(factor)
        anchor, lo, hi, n_bars = cme_path_extrema(
            factor_cache[factor], row["fri_ts"], row["mon_ts"]
        )
        if anchor is None or anchor <= 0 or n_bars == 0:
            continue
        scale = float(row["fri_close"]) / anchor
        path_lo = lo * scale
        path_hi = hi * scale
        for tau in ANCHORS:
            band_lo = float(row[f"lower_{tau}"])
            band_hi = float(row[f"upper_{tau}"])
            endpoint_in = band_lo <= float(row["mon_open"]) <= band_hi
            path_in = (path_lo >= band_lo) and (path_hi <= band_hi)
            rows.append({
                "symbol": row["symbol"],
                "fri_ts": row["fri_ts"],
                "mon_ts": row["mon_ts"],
                "regime_pub": row["regime_pub"],
                "tau": tau,
                "factor_used": factor,
                "n_bars": n_bars,
                "fri_close": float(row["fri_close"]),
                "mon_open": float(row["mon_open"]),
                "point": float(row["point"]),
                "band_lo": band_lo,
                "band_hi": band_hi,
                "path_lo": path_lo,
                "path_hi": path_hi,
                "endpoint_in_band": endpoint_in,
                "path_in_band": path_in,
            })
    return pd.DataFrame(rows)


def eval_onchain_path(panel: pd.DataFrame, served: pd.DataFrame) -> pd.DataFrame:
    base = panel.merge(served, on=["symbol", "fri_ts"], suffixes=("", "_art"))
    rows: list[dict] = []
    for sym in ["SPY", "QQQ", "AAPL", "GOOGL", "NVDA", "TSLA", "HOOD", "MSTR"]:
        xsym = sym + "x"
        swaps = load_xstock_swaps(xsym)
        if swaps.empty:
            continue
        sym_rows = base[base["symbol"] == sym]
        for _, row in sym_rows.iterrows():
            lo, hi, n_swaps = onchain_path_extrema(swaps, row["fri_ts"], row["mon_ts"])
            if lo is None or n_swaps == 0:
                continue
            for tau in ANCHORS:
                band_lo = float(row[f"lower_{tau}"])
                band_hi = float(row[f"upper_{tau}"])
                rows.append({
                    "symbol": sym,
                    "xstock": xsym,
                    "fri_ts": row["fri_ts"],
                    "mon_ts": row["mon_ts"],
                    "regime_pub": row["regime_pub"],
                    "tau": tau,
                    "n_swaps": n_swaps,
                    "fri_close": float(row["fri_close"]),
                    "mon_open": float(row["mon_open"]),
                    "band_lo": band_lo,
                    "band_hi": band_hi,
                    "onchain_lo": lo,
                    "onchain_hi": hi,
                    "endpoint_in_band": band_lo <= float(row["mon_open"]) <= band_hi,
                    "path_in_band": (lo >= band_lo) and (hi <= band_hi),
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- aggregation

def aggregate(per_row: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Pooled coverage rates + endpoint vs path gap."""
    g = per_row.groupby(group_cols)
    out = g.agg(
        n=("path_in_band", "size"),
        endpoint_cov=("endpoint_in_band", "mean"),
        path_cov=("path_in_band", "mean"),
    ).reset_index()
    out["gap_pp"] = (out["endpoint_cov"] - out["path_cov"]) * 100.0
    return out


# --------------------------------------------------------------------- output

def write_markdown(
    cme_pooled_by_tau: pd.DataFrame,
    cme_pooled_by_tau_regime: pd.DataFrame,
    onchain_pooled: pd.DataFrame,
    cme_observable_share: float,
    out_path: Path,
) -> None:
    lines: list[str] = []
    lines.append("# §6.x Path coverage — endpoint vs intra-weekend\n")
    lines.append(
        "Endpoint coverage (§6.2) tests whether the realised Monday open lies "
        "inside the served band. A DeFi consumer holding an xStock as collateral "
        "is exposed at every block over the weekend, not only at Monday open. "
        "This section reports two complementary *path-coverage* measures: the "
        "fraction of weekends on which the underlier-equivalent price path stays "
        "inside the served band over the entire prediction window "
        "[Fri 16:00 ET, Mon 09:30 ET].\n"
    )
    lines.append("## CME-implied underlier path (full panel proxy)\n")
    lines.append(
        "For each (symbol, weekend), the path is constructed from the per-symbol "
        "futures factor (ES=F for equities, GC=F for GLD, ZN=F for TLT) by "
        "scaling with `fri_close / F_anchor`. CME 1m bars cover Friday "
        "09:30–17:00 ET and Sunday 18:00 ET through the rest of the week; the "
        "Friday 17:00 ET → Sunday 18:00 ET Globex-dark window is unobservable. "
        f"Mean fraction of the prediction window that is observable: "
        f"`{cme_observable_share:.1%}`. MSTR post-2020-08 is excluded (BTC tape "
        "absent from scryer cache). CME tape coverage starts 2018-01-05.\n"
    )
    lines.append("**Pooled by τ.**\n")
    lines.append(cme_pooled_by_tau.to_markdown(index=False, floatfmt=".4f"))
    lines.append("\n\n**Pooled by τ × regime.**\n")
    lines.append(cme_pooled_by_tau_regime.to_markdown(index=False, floatfmt=".4f"))
    lines.append("\n\n## On-chain xStock path (post-launch slice)\n")
    lines.append(
        "On-chain xStock swaps from `dex_xstock/swaps/v1` give the "
        "consumer-experienced object directly (no scaling). Sample is the "
        "post-launch slice currently cached in scryer; this is the right "
        "object for DeFi consumer impact but small-N until V3.1 / scryer "
        "item 51 backfill matures.\n"
    )
    if onchain_pooled.empty:
        lines.append("\n_No on-chain weekend overlap with the panel — sample is shorter than one prediction window._\n")
    else:
        lines.append(onchain_pooled.to_markdown(index=False, floatfmt=".4f"))
    lines.append(
        "\n\n## Reading\n"
        "- Endpoint coverage matches §6.2. Any positive `gap_pp` is the share "
        "of weekends where the band held at Monday open but was punctured "
        "at some point intra-weekend.\n"
        "- The CME-path proxy is conservative against the band on observable "
        "minutes only — the dark window is genuinely unobservable from CME, "
        "so the true path-violation rate is **at least** the reported figure.\n"
        "- Path-violation concentration in `high_vol` (cross-tab above) is "
        "the load-bearing risk surface for Paper 3 lending policy.\n"
        "- A consumer requiring path coverage at level τ rather than endpoint "
        "coverage at level τ should consult the gap and either widen via the "
        "circuit-breaker mechanism of §9.1 or step up to the next anchor.\n"
    )
    out_path.write_text("\n".join(lines))


def main() -> None:
    artefact = pd.read_parquet(DATA_PROCESSED / "mondrian_artefact_v2.parquet")
    artefact["fri_ts"] = pd.to_datetime(artefact["fri_ts"]).dt.date
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date

    served = serve_bands(artefact)

    print("[1/3] CME path proxy …", flush=True)
    cme_per_row = eval_cme_path(panel, served)
    print(f"      {len(cme_per_row)} rows ({cme_per_row['fri_ts'].nunique()} weekends, "
          f"{cme_per_row['symbol'].nunique()} symbols)", flush=True)

    # Observable share = mean(n_bars / max possible bars in window).
    # Max ≈ Friday 16:00–17:00 (60) + Sunday 18:00–24:00 (360) + Monday 0:00–9:30 (570) = 990 minutes.
    # Long weekends extend the second half. Use the actual window length per row.
    cme_per_row_unique = cme_per_row.drop_duplicates(subset=["symbol", "fri_ts"])
    window_minutes = (
        cme_per_row_unique.apply(
            lambda r: (
                int((datetime.combine(r["mon_ts"], WINDOW_END, tzinfo=NY)
                     - datetime.combine(r["fri_ts"], WINDOW_START, tzinfo=NY)).total_seconds() // 60)
                # Subtract Saturday + Friday-night/Sunday-evening Globex dark
                - (49 * 60)  # ~49h Globex-dark from Fri 17:00 ET to Sun 18:00 ET
            ),
            axis=1,
        )
        .clip(lower=1)
    )
    obs_share = float((cme_per_row_unique["n_bars"].astype(float) / window_minutes).clip(0, 1.0).mean())

    cme_pooled_by_tau = aggregate(cme_per_row, ["tau"])
    cme_pooled_by_tau_regime = aggregate(cme_per_row, ["tau", "regime_pub"])

    print("[2/3] On-chain xStock path …", flush=True)
    onchain_per_row = eval_onchain_path(panel, served)
    print(f"      {len(onchain_per_row)} rows ({onchain_per_row['fri_ts'].nunique() if not onchain_per_row.empty else 0} weekends)", flush=True)
    onchain_pooled = (
        aggregate(onchain_per_row, ["symbol", "tau"])
        if not onchain_per_row.empty else pd.DataFrame()
    )

    print("[3/3] Writing outputs …", flush=True)
    out_dir = REPORTS / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    cme_per_row.to_csv(out_dir / "path_coverage_cme_per_row.csv", index=False)
    cme_pooled_by_tau.to_csv(out_dir / "path_coverage_cme.csv", index=False)
    cme_pooled_by_tau_regime.to_csv(out_dir / "path_coverage_cme_by_regime.csv", index=False)
    if not onchain_per_row.empty:
        onchain_per_row.to_csv(out_dir / "path_coverage_onchain_per_row.csv", index=False)
        onchain_pooled.to_csv(out_dir / "path_coverage_onchain.csv", index=False)

    write_markdown(
        cme_pooled_by_tau, cme_pooled_by_tau_regime, onchain_pooled,
        obs_share, REPORTS / "v1b_path_coverage.md",
    )
    print(f"      observable share of window (CME): {obs_share:.1%}", flush=True)
    print("done.")


if __name__ == "__main__":
    main()
