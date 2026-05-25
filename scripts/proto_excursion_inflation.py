"""
PROTOTYPE (not paper-wired) — excursion-inflation factor for a path-aware band.

Question being prototyped (from the 2026-05 reviewer thread): the actionable
object for a lending protocol / oracle-conditioned AMM is path-indexed, not the
Monday-open endpoint. Do we need a *different model*, or can the deployed
endpoint band be composed with a regime-dependent excursion inflation λ(τ) to
deliver τ *path* coverage?

Definition. Standardise every deviation by the same scale the band uses,
σ̂_sym(t)·fri_close (call it S). For each (symbol, weekend):

    z_end      = |mon_open - point| / S                 endpoint deviation
    z_path_ext = max(|path_hi - point|, |path_lo - point|) / S
                                                         worst intra-weekend excursion

The half-width (standardised) needed for τ coverage of each object is the
τ-quantile of that object. The excursion inflation is their ratio:

    λ(τ) = Quantile_τ(z_path_ext) / Quantile_τ(z_end)

λ ≈ 1  → an endpoint-sized band already covers the path; the fix is framing +
         a thin inflation layer, same engine.
λ ≫ 1  → the path object is genuinely bigger than the endpoint object; an
         endpoint-trained band cannot be cheaply inflated into a path band, and
         a path-native target is warranted.

Two proxies bound the truth:
  (A) CME factor path, 12-yr / ~3.8k cells. COUPLED to `point` (point is the
      factor projection), so λ_cme isolates the factor's intra-weekend
      *round-trip* excursion that the endpoint misses. Lower bound on inflation.
  (B) Kraken xStock-perp path, trade-supported (volume_base>0), ~19 weekends.
      DECOUPLED from `point` (independent venue), so it also carries basis +
      idiosyncratic excursion. Realistic but small-N and liquidity-fragile.

Reuses run_path_coverage's loaders/serve so the band + path extraction are
byte-identical to the §6.x table. Writes a single prototype markdown; touches
nothing the paper consumes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_path_coverage import (  # noqa: E402  (path insert above)
    ANCHORS,
    FACTOR_FOR_PATH,
    MSTR_BTC_PIVOT,
    cme_path_extrema,
    load_cme_factor,
    load_perp_ohlcv,
    perp_path_extrema,
    serve_bands,
)
from soothsayer.config import DATA_PROCESSED, REPORTS  # noqa: E402
from datetime import timedelta  # noqa: E402


def _std_scale(row: pd.Series) -> float:
    """S = σ̂_sym(t)·fri_close — the price-unit scale the band half-width uses."""
    return float(row["sigma_hat_sym_pre_fri"]) * float(row["fri_close"])


def build_cme_rows(panel: pd.DataFrame, served: pd.DataFrame) -> pd.DataFrame:
    base = panel.merge(served, on=["symbol", "fri_ts"], suffixes=("", "_art"))
    base = base[base["symbol"].isin(FACTOR_FOR_PATH)]
    base = base[~((base["symbol"] == "MSTR") & (base["fri_ts"] >= MSTR_BTC_PIVOT))]
    base["factor_used"] = base["symbol"].map(FACTOR_FOR_PATH)
    if base.empty:
        return pd.DataFrame()
    w_start = pd.to_datetime(base["fri_ts"].min()).date() - timedelta(days=1)
    w_end = pd.to_datetime(base["mon_ts"].max()).date() + timedelta(days=1)
    cache: dict[str, pd.DataFrame] = {}
    rows: list[dict] = []
    for _, row in base.iterrows():
        factor = row["factor_used"]
        if factor not in cache:
            cache[factor] = load_cme_factor(factor, w_start, w_end)
        anchor, lo, hi, n_bars = cme_path_extrema(cache[factor], row["fri_ts"], row["mon_ts"])
        if anchor is None or anchor <= 0 or n_bars == 0:
            continue
        scale = float(row["fri_close"]) / anchor
        path_lo, path_hi = lo * scale, hi * scale
        S = _std_scale(row)
        if S <= 0:
            continue
        point = float(row["point"])
        rows.append({
            "proxy": "cme",
            "symbol": row["symbol"], "fri_ts": row["fri_ts"],
            "regime_pub": row["regime_pub"], "n_bars": n_bars,
            "z_end": abs(float(row["mon_open"]) - point) / S,
            "z_path_ext": max(abs(path_hi - point), abs(path_lo - point)) / S,
        })
    return pd.DataFrame(rows)


def build_perp_rows(panel: pd.DataFrame, served: pd.DataFrame,
                    min_volume: float, min_traded_bars: int) -> pd.DataFrame:
    base = panel.merge(served, on=["symbol", "fri_ts"], suffixes=("", "_art"))
    if base.empty:
        return pd.DataFrame()
    w_start = pd.to_datetime(base["fri_ts"].min()).date() - timedelta(days=1)
    w_end = pd.to_datetime(base["mon_ts"].max()).date() + timedelta(days=1)
    rows: list[dict] = []
    for sym in ["SPY", "QQQ", "GLD", "AAPL", "TSLA", "HOOD", "MSTR", "GOOGL", "NVDA"]:
        bars = load_perp_ohlcv(sym, w_start, w_end)
        if bars.empty:
            continue
        for _, row in base[base["symbol"] == sym].iterrows():
            lo, hi, n_bars = perp_path_extrema(
                bars, row["fri_ts"], row["mon_ts"],
                min_volume=min_volume, min_traded_bars=min_traded_bars,
            )
            if lo is None or n_bars == 0:
                continue
            S = _std_scale(row)
            if S <= 0:
                continue
            point = float(row["point"])
            rows.append({
                "proxy": "perp", "symbol": sym, "fri_ts": row["fri_ts"],
                "regime_pub": row["regime_pub"], "n_bars": n_bars,
                "z_end": abs(float(row["mon_open"]) - point) / S,
                "z_path_ext": max(abs(hi - point), abs(lo - point)) / S,
            })
    return pd.DataFrame(rows)


def inflation_table(df: pd.DataFrame, group: list[str] | None = None) -> pd.DataFrame:
    """λ(τ) = Q_τ(z_path_ext) / Q_τ(z_end), plus the path coverage the
    endpoint-sized band (λ=1) actually delivers."""
    out: list[dict] = []
    groups = [("pooled", df)] if group is None else list(df.groupby(group[0]))
    for gname, g in groups:
        if len(g) < 5:
            continue
        for tau in ANCHORS:
            q_end = float(np.quantile(g["z_end"], tau))
            q_path = float(np.quantile(g["z_path_ext"], tau))
            lam = q_path / q_end if q_end > 0 else np.nan
            # path coverage the deployed endpoint band delivers: share of
            # weekends whose worst excursion is within the endpoint half-width.
            path_cov_at_endpoint = float((g["z_path_ext"] <= q_end).mean())
            out.append({
                "group": gname, "tau": tau, "n": len(g),
                "q_end_std": round(q_end, 3), "q_path_std": round(q_path, 3),
                "lambda": round(lam, 3),
                "path_cov_at_endpoint_band": round(path_cov_at_endpoint, 3),
            })
    return pd.DataFrame(out)


def _fmt(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False) if not df.empty else "_(empty)_"


def main() -> None:
    artefact = pd.read_parquet(DATA_PROCESSED / "lwc_artefact_v1.parquet")
    artefact["fri_ts"] = pd.to_datetime(artefact["fri_ts"]).dt.date
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel["mon_ts"] = pd.to_datetime(panel["mon_ts"]).dt.date
    served = serve_bands(artefact)

    print("[1/2] CME factor path (coupled, large-N) …", flush=True)
    cme = build_cme_rows(panel, served)
    print(f"      {len(cme)} cells, {cme['fri_ts'].nunique()} weekends", flush=True)

    print("[2/2] Kraken perp path (trade-supported, small-N) …", flush=True)
    perp = build_perp_rows(panel, served, min_volume=0.0, min_traded_bars=3)
    print(f"      {len(perp)} cells, {perp['fri_ts'].nunique() if not perp.empty else 0} weekends", flush=True)

    cme_pooled = inflation_table(cme)
    cme_regime = inflation_table(cme, ["regime_pub"])
    perp_pooled = inflation_table(perp) if not perp.empty else pd.DataFrame()

    out = REPORTS / "active" / "proto_excursion_inflation.md"
    lines = [
        "# PROTOTYPE — excursion inflation λ(τ) for a path-aware band\n",
        "**Status:** prototype, not paper-wired. Generated by "
        "`scripts/proto_excursion_inflation.py`.\n",
        "λ(τ) = Q_τ(worst intra-weekend excursion) / Q_τ(endpoint deviation), "
        "both standardised by σ̂·fri_close. λ≈1 ⇒ endpoint-sized band already "
        "covers the path (framing fix + thin inflation, same engine); λ≫1 ⇒ "
        "path object genuinely bigger, path-native target warranted.\n",
        "`path_cov_at_endpoint_band` = path coverage the *deployed* endpoint "
        "band (λ=1) delivers at that τ — the gap from τ is the shortfall a "
        "consumer reading the band over the weekend actually eats.\n",
        "\n## (A) CME factor path — coupled, lower bound on inflation\n",
        "Point is the factor projection, so this isolates the factor's "
        "intra-weekend *round-trip* excursion the endpoint misses.\n",
        "\n### Pooled\n", _fmt(cme_pooled),
        "\n\n### By regime\n", _fmt(cme_regime),
        "\n\n## (B) Kraken xStock-perp path — decoupled, trade-supported "
        "(volume_base>0, ≥3 traded bars)\n",
        "Independent venue ⇒ also carries basis + idiosyncratic excursion. "
        "Small-N and liquidity-fragile; read as a noisy upper-ish bound.\n",
        "\n### Pooled\n", _fmt(perp_pooled),
        "\n\n## Reproduction\n```\nuv run python scripts/proto_excursion_inflation.py\n```\n",
    ]
    out.write_text("".join(s if s.endswith("\n") else s for s in lines))
    print(f"\nwrote {out}", flush=True)

    # Echo the headline to stdout for the conversation.
    print("\n=== CME pooled λ(τ) ===", flush=True)
    print(cme_pooled.to_string(index=False), flush=True)
    if not perp_pooled.empty:
        print("\n=== Perp (trade-supported) pooled λ(τ) ===", flush=True)
        print(perp_pooled.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
