"""
Path-coverage robustness — three confound checks on the §6.6 result.

The headline run reports a 14.4pp gap at τ=0.95 between endpoint coverage
(0.983) and perp-path coverage (0.839) on 118 (symbol, weekend) rows from
Kraken Futures `PF_<sym>XUSD` 1m bars. Three confounds are addressed
before treating the gap as the product-level truth:

  (A) Perp-vs-spot basis at Friday 16:00 ET. The perp may not anchor
      cleanly to the NYSE close that the band is built around. Rescale
      every perp bar by `fri_close / perp_anchor` so basis(Fri 16:00) = 0
      and recompute path coverage on the rescaled path. Also report the
      basis distribution (mean / median / p5 / p95).

  (B) Volume floor. Drop perp bars below a `volume_base` threshold and
      recompute path coverage on the survivors. Tests whether the gap is
      driven by thin-liquidity prints. Sweep over thresholds
      {0.0, 0.1, 1.0, 10.0}.

  (C) Sustained crossing. Replace the "any 1m bar's high/low" definition
      of a path violation with a rolling-window median of the close. A
      lending consumer's TWAP-based liquidation triggers on sustained
      drift, not single prints. Sweep over windows {1, 5, 15} minutes.

Outputs:
  reports/tables/path_coverage_robustness_basis.csv
  reports/tables/path_coverage_robustness_volfloor.csv
  reports/tables/path_coverage_robustness_sustained.csv
  reports/v1b_path_coverage_robustness.md
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.config import DATA_PROCESSED, REPORTS

# Reuse everything from the headline script — single source of truth.
from run_path_coverage import (
    ANCHORS,
    aggregate,
    load_perp_ohlcv,
    serve_bands,
    weekend_window_utc,
)


PERP_SYMBOLS = ["SPY", "QQQ", "GLD", "AAPL", "TSLA", "HOOD", "MSTR", "GOOGL", "NVDA"]
VOLUME_FLOORS = [0.0, 0.1, 1.0, 10.0]
SUSTAIN_WINDOWS = [1, 5, 15]


# ----------------------------------------------------------------- per-row eval

def _band_check(row: pd.Series, lo: float, hi: float) -> dict:
    return {
        "endpoint_in_band": float(row["band_lo"]) <= float(row["mon_open"]) <= float(row["band_hi"]),
        "path_in_band": (lo >= float(row["band_lo"])) and (hi <= float(row["band_hi"])),
    }


def eval_basis_normalized(panel: pd.DataFrame, served: pd.DataFrame) -> pd.DataFrame:
    """Variant A — recenter perp path so basis(Fri 16:00 ET) = 0."""
    base = panel.merge(served, on=["symbol", "fri_ts"], suffixes=("", "_art"))
    rows: list[dict] = []
    for sym in PERP_SYMBOLS:
        bars = load_perp_ohlcv(sym)
        if bars.empty:
            continue
        sym_rows = base[base["symbol"] == sym]
        for _, r in sym_rows.iterrows():
            start_utc, end_utc = weekend_window_utc(r["fri_ts"], r["mon_ts"])
            w = bars[(bars["bar_open_ts"] >= start_utc) & (bars["bar_open_ts"] <= end_utc)]
            if w.empty:
                continue
            pre = bars[bars["bar_open_ts"] <= start_utc + 60]
            anchor = float(pre["close"].iloc[-1]) if not pre.empty else float(w["close"].iloc[0])
            if anchor <= 0:
                continue
            scale = float(r["fri_close"]) / anchor
            lo_raw = float(w["low"].min())
            hi_raw = float(w["high"].max())
            lo_norm = lo_raw * scale
            hi_norm = hi_raw * scale
            basis_bps = (anchor - float(r["fri_close"])) / float(r["fri_close"]) * 1e4
            for tau in ANCHORS:
                row = {
                    "symbol": sym,
                    "fri_ts": r["fri_ts"],
                    "mon_ts": r["mon_ts"],
                    "regime_pub": r["regime_pub"],
                    "tau": tau,
                    "fri_close": float(r["fri_close"]),
                    "perp_anchor": anchor,
                    "basis_bps": basis_bps,
                    "band_lo": float(r[f"lower_{tau}"]),
                    "band_hi": float(r[f"upper_{tau}"]),
                    "raw_path_lo": lo_raw,
                    "raw_path_hi": hi_raw,
                    "norm_path_lo": lo_norm,
                    "norm_path_hi": hi_norm,
                    "mon_open": float(r["mon_open"]),
                }
                row["endpoint_in_band"] = row["band_lo"] <= row["mon_open"] <= row["band_hi"]
                row["path_in_band_raw"] = (lo_raw >= row["band_lo"]) and (hi_raw <= row["band_hi"])
                row["path_in_band_norm"] = (lo_norm >= row["band_lo"]) and (hi_norm <= row["band_hi"])
                rows.append(row)
    return pd.DataFrame(rows)


def eval_volume_floor(panel: pd.DataFrame, served: pd.DataFrame) -> pd.DataFrame:
    """Variant B — drop bars below volume floor before computing extrema."""
    base = panel.merge(served, on=["symbol", "fri_ts"], suffixes=("", "_art"))
    rows: list[dict] = []
    for sym in PERP_SYMBOLS:
        bars = load_perp_ohlcv(sym)
        if bars.empty:
            continue
        sym_rows = base[base["symbol"] == sym]
        for _, r in sym_rows.iterrows():
            start_utc, end_utc = weekend_window_utc(r["fri_ts"], r["mon_ts"])
            w = bars[(bars["bar_open_ts"] >= start_utc) & (bars["bar_open_ts"] <= end_utc)]
            if w.empty:
                continue
            for vol_min in VOLUME_FLOORS:
                f = w[w["volume_base"] > vol_min] if vol_min > 0 else w
                if f.empty:
                    continue
                lo = float(f["low"].min())
                hi = float(f["high"].max())
                for tau in ANCHORS:
                    band_lo = float(r[f"lower_{tau}"])
                    band_hi = float(r[f"upper_{tau}"])
                    rows.append({
                        "symbol": sym,
                        "fri_ts": r["fri_ts"],
                        "regime_pub": r["regime_pub"],
                        "tau": tau,
                        "vol_floor": vol_min,
                        "n_bars_post_filter": int(len(f)),
                        "n_bars_total": int(len(w)),
                        "band_lo": band_lo,
                        "band_hi": band_hi,
                        "path_lo": lo,
                        "path_hi": hi,
                        "mon_open": float(r["mon_open"]),
                        "endpoint_in_band": band_lo <= float(r["mon_open"]) <= band_hi,
                        "path_in_band": (lo >= band_lo) and (hi <= band_hi),
                    })
    return pd.DataFrame(rows)


def eval_sustained(panel: pd.DataFrame, served: pd.DataFrame) -> pd.DataFrame:
    """Variant C — path violation requires rolling-median outside band."""
    base = panel.merge(served, on=["symbol", "fri_ts"], suffixes=("", "_art"))
    rows: list[dict] = []
    for sym in PERP_SYMBOLS:
        bars = load_perp_ohlcv(sym)
        if bars.empty:
            continue
        sym_rows = base[base["symbol"] == sym]
        for _, r in sym_rows.iterrows():
            start_utc, end_utc = weekend_window_utc(r["fri_ts"], r["mon_ts"])
            w = bars[(bars["bar_open_ts"] >= start_utc) & (bars["bar_open_ts"] <= end_utc)]
            if w.empty:
                continue
            close = w["close"].astype(float).reset_index(drop=True)
            for win in SUSTAIN_WINDOWS:
                if win == 1:
                    series = close
                else:
                    series = close.rolling(window=win, min_periods=win).median().dropna()
                if series.empty:
                    continue
                lo = float(series.min())
                hi = float(series.max())
                for tau in ANCHORS:
                    band_lo = float(r[f"lower_{tau}"])
                    band_hi = float(r[f"upper_{tau}"])
                    rows.append({
                        "symbol": sym,
                        "fri_ts": r["fri_ts"],
                        "regime_pub": r["regime_pub"],
                        "tau": tau,
                        "sustain_window_min": win,
                        "n_obs_post_roll": int(len(series)),
                        "band_lo": band_lo,
                        "band_hi": band_hi,
                        "path_lo": lo,
                        "path_hi": hi,
                        "mon_open": float(r["mon_open"]),
                        "endpoint_in_band": band_lo <= float(r["mon_open"]) <= band_hi,
                        "path_in_band": (lo >= band_lo) and (hi <= band_hi),
                    })
    return pd.DataFrame(rows)


# --------------------------------------------------------------- aggregation

def basis_summary_table(per_row_basis: pd.DataFrame) -> pd.DataFrame:
    """Pooled-by-τ comparison: endpoint vs raw-path vs normalized-path."""
    g = per_row_basis.groupby("tau")
    out = g.agg(
        n=("path_in_band_raw", "size"),
        endpoint_cov=("endpoint_in_band", "mean"),
        path_cov_raw=("path_in_band_raw", "mean"),
        path_cov_norm=("path_in_band_norm", "mean"),
    ).reset_index()
    out["gap_pp_raw"] = (out["endpoint_cov"] - out["path_cov_raw"]) * 100.0
    out["gap_pp_norm"] = (out["endpoint_cov"] - out["path_cov_norm"]) * 100.0
    out["delta_norm_vs_raw_pp"] = (out["path_cov_norm"] - out["path_cov_raw"]) * 100.0
    return out


def basis_distribution(per_row_basis: pd.DataFrame) -> pd.DataFrame:
    uniq = per_row_basis.drop_duplicates(subset=["symbol", "fri_ts"])
    s = uniq["basis_bps"]
    return pd.DataFrame([{
        "n_pairs": len(uniq),
        "basis_mean_bps": s.mean(),
        "basis_median_bps": s.median(),
        "basis_p5_bps": s.quantile(0.05),
        "basis_p95_bps": s.quantile(0.95),
        "basis_abs_mean_bps": s.abs().mean(),
        "basis_abs_p95_bps": s.abs().quantile(0.95),
    }])


def volfloor_table(per_row_vol: pd.DataFrame) -> pd.DataFrame:
    g = per_row_vol.groupby(["vol_floor", "tau"])
    out = g.agg(
        n=("path_in_band", "size"),
        endpoint_cov=("endpoint_in_band", "mean"),
        path_cov=("path_in_band", "mean"),
        n_bars_mean=("n_bars_post_filter", "mean"),
        survival_share=("n_bars_post_filter", lambda s: float((s / per_row_vol["n_bars_total"].iloc[0]).mean())),
    ).reset_index()
    out["gap_pp"] = (out["endpoint_cov"] - out["path_cov"]) * 100.0
    return out


def sustained_table(per_row_sus: pd.DataFrame) -> pd.DataFrame:
    g = per_row_sus.groupby(["sustain_window_min", "tau"])
    out = g.agg(
        n=("path_in_band", "size"),
        endpoint_cov=("endpoint_in_band", "mean"),
        path_cov=("path_in_band", "mean"),
    ).reset_index()
    out["gap_pp"] = (out["endpoint_cov"] - out["path_cov"]) * 100.0
    return out


# --------------------------------------------------------------------- output

def write_markdown(
    basis_dist: pd.DataFrame,
    basis_tab: pd.DataFrame,
    volfloor_tab: pd.DataFrame,
    sustained_tab: pd.DataFrame,
    out_path: Path,
) -> None:
    lines: list[str] = []
    lines.append("# §6.6 Path coverage — robustness checks\n")
    lines.append(
        "The headline §6.6 result is a 14.4pp gap at τ=0.95 between endpoint "
        "coverage (0.983) and perp-path coverage (0.839) on 118 (symbol, "
        "weekend) rows. This file reports three robustness checks before "
        "treating the gap as the product-level truth: (A) perp-vs-spot "
        "basis at the Friday-close anchor, (B) volume floor on perp bars, "
        "(C) sustained-crossing definition via rolling-median.\n"
    )

    lines.append("## (A) Perp-vs-spot basis at Friday 16:00 ET\n")
    lines.append(
        "If the perp anchors significantly off the NYSE close, the raw perp "
        "path is in different units than the band. Recenter every perp bar "
        "by `fri_close / perp_anchor` and recompute path coverage. The "
        "basis distribution across 118 (symbol, weekend) pairs:\n"
    )
    lines.append(basis_dist.to_markdown(index=False, floatfmt=".2f"))
    lines.append("\n\n**Pooled by τ — raw vs basis-normalized path coverage:**\n")
    lines.append(basis_tab.to_markdown(index=False, floatfmt=".4f"))
    lines.append(
        "\n\n*Reading.* If `basis_abs_mean_bps` is < 50bps the perp anchors "
        "cleanly and `delta_norm_vs_raw_pp` should be small. A large delta "
        "(say > 5pp) means the headline number was driven by perp-spot "
        "basis at the start-of-window, not by intra-weekend price moves.\n"
    )

    lines.append("\n## (B) Volume floor on perp bars\n")
    lines.append(
        "Drop bars below `volume_base` thresholds and recompute path "
        "coverage on the survivors. Tests whether thin-liquidity prints "
        "drive the violations. `survival_share` = mean fraction of the "
        "weekend-window bars that survive the filter.\n"
    )
    lines.append(volfloor_tab.to_markdown(index=False, floatfmt=".4f"))
    lines.append(
        "\n\n*Reading.* If `path_cov` rises substantially as `vol_floor` "
        "increases — say from 0.84 to 0.92 at vol_floor = 1.0 — then the "
        "headline gap is partly perp microstructure noise on thin bars. "
        "If `path_cov` is flat across thresholds, the gap is real and not "
        "a thin-liquidity artifact.\n"
    )

    lines.append("\n## (C) Sustained crossing (rolling median)\n")
    lines.append(
        "Replace the `any 1m bar` violation definition with a rolling "
        "median of the close. Most lending protocols TWAP the on-chain "
        "price before liquidating, so a 5–15 minute median is closer to "
        "the consumer-relevant trigger than a single tick.\n"
    )
    lines.append(sustained_tab.to_markdown(index=False, floatfmt=".4f"))
    lines.append(
        "\n\n*Reading.* The `sustain_window_min = 1` row reproduces the "
        "headline (single-bar definition). Higher windows test whether "
        "the gap is sustained drift or single-print noise. A drop from "
        "14pp at win=1 to ~5pp at win=15 says most violations are "
        "transient prints; a flat profile says the gap is sustained.\n"
    )

    out_path.write_text("\n".join(lines))


def main() -> None:
    artefact = pd.read_parquet(DATA_PROCESSED / "mondrian_artefact_v2.parquet")
    artefact["fri_ts"] = pd.to_datetime(artefact["fri_ts"]).dt.date
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    served = serve_bands(artefact)

    print("[A/3] Basis normalization …", flush=True)
    basis_rows = eval_basis_normalized(panel, served)
    basis_dist = basis_distribution(basis_rows)
    basis_tab = basis_summary_table(basis_rows)
    print(f"      {len(basis_rows)} rows, abs basis mean {basis_dist['basis_abs_mean_bps'].iloc[0]:.1f}bps", flush=True)

    print("[B/3] Volume floor …", flush=True)
    vol_rows = eval_volume_floor(panel, served)
    vol_tab = volfloor_table(vol_rows)
    print(f"      {len(vol_rows)} rows across {len(VOLUME_FLOORS)} thresholds", flush=True)

    print("[C/3] Sustained crossing …", flush=True)
    sus_rows = eval_sustained(panel, served)
    sus_tab = sustained_table(sus_rows)
    print(f"      {len(sus_rows)} rows across {len(SUSTAIN_WINDOWS)} windows", flush=True)

    out_dir = REPORTS / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    basis_rows.to_csv(out_dir / "path_coverage_robustness_basis.csv", index=False)
    vol_rows.to_csv(out_dir / "path_coverage_robustness_volfloor.csv", index=False)
    sus_rows.to_csv(out_dir / "path_coverage_robustness_sustained.csv", index=False)

    write_markdown(
        basis_dist, basis_tab, vol_tab, sus_tab,
        REPORTS / "v1b_path_coverage_robustness.md",
    )
    print("done.")


if __name__ == "__main__":
    main()
