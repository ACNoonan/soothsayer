"""
Unified head-to-head: Soothsayer (v1 deployed, M5 candidate) vs incumbent oracles.

W1 deliverable for `VALIDATION_BACKLOG.md`. Reads the per-oracle coverage
artefacts and builds one head-to-head table at matched coverage τ ∈
{0.68, 0.85, 0.95}: smallest published-band half-width that delivers
each τ on each oracle's available sample. Sample size and panel scope
are reported per row — *the comparison is not on a single shared panel*
(impossible while incumbent tapes have <40 days of forward capture);
the value is the empirical width-cost-to-target across oracles.

Inputs (all written by their per-oracle benchmark scripts):
  reports/tables/pyth_coverage_by_k.csv             (k * conf; mean_halfwidth_bps)
  reports/tables/chainlink_implicit_band.csv        (k_pct; halfwidth_bps)
  reports/tables/redstone_coverage_by_k_pct.csv     (k_pct; halfwidth_bps)
  reports/tables/kamino_scope_coverage_by_k_pct.csv (k_pct; halfwidth_bps)

  data/processed/v1b_bounds.parquet                  (Soothsayer v1 deployed bounds)
  reports/tables/v1b_mondrian_oos.csv                (M5 candidate OOS realised + halfwidth, optional)

Outputs:
  reports/tables/incumbent_oracle_unified_summary.csv
  reports/v1b_incumbent_oracle_comparison.md
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.config import DATA_PROCESSED, REPORTS

TAU_GRID = (0.68, 0.85, 0.95)


def _smallest_k_at_tau(pooled: pd.DataFrame, tau: float, k_col: str, hw_col: str) -> dict | None:
    """Return the row in `pooled` with smallest `k_col` such that
    `realized >= tau`. None if no row in the sweep crosses τ."""
    p = pooled[pooled["realized"] >= tau].sort_values(k_col)
    if p.empty:
        return None
    r = p.iloc[0]
    return {"k": float(r[k_col]), "halfwidth_bps": float(r[hw_col]),
            "realized": float(r["realized"]), "n": int(r["n"])}


def _load_pyth() -> pd.DataFrame | None:
    p = REPORTS / "tables" / "pyth_coverage_by_k.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    return df[df["scope"] == "pooled"].copy()


def _load_csv_pooled(rel: str, k_col: str = "k_pct") -> pd.DataFrame | None:
    p = REPORTS / "tables" / rel
    if not p.exists():
        return None
    df = pd.read_csv(p)
    if "scope" not in df.columns:
        return df
    return df[df["scope"] == "pooled"].copy()


def _soothsayer_summary() -> dict[str, dict[float, dict]]:
    """Read existing canonical OOS tables for v1 deployed Oracle and M5
    candidate. Source: `reports/tables/v1b_mondrian_oos.csv` (both methods
    on the same OOS 2023+ panel of 1,730 rows × 173 weekends)."""
    p = REPORTS / "tables" / "v1b_mondrian_oos.csv"
    if not p.exists():
        return {}
    df = pd.read_csv(p)
    out: dict[str, dict[float, dict]] = {"v1": {}, "M5": {}}
    method_map = {"oracle": "v1", "M5_mondrian_deployable": "M5"}
    for _, r in df.iterrows():
        key = method_map.get(str(r["method"]))
        if key is None:
            continue
        tau = float(r["target"])
        if tau not in TAU_GRID:
            continue
        out[key][tau] = {
            "n": int(r["n"]),
            "realized": float(r["realised"]),
            "halfwidth_bps": float(r["half_width_bps"]),
            "p_uc": float(r["p_uc"]),
        }
    return out


def main() -> None:
    pyth = _load_pyth()
    chainlink = _load_csv_pooled("chainlink_implicit_band.csv", k_col="k_pct")
    redstone = _load_csv_pooled("redstone_coverage_by_k_pct.csv", k_col="k_pct")
    scope = _load_csv_pooled("kamino_scope_coverage_by_k_pct.csv", k_col="k_pct")
    sooth = _soothsayer_summary()
    v1 = sooth.get("v1", {})
    m5 = sooth.get("M5", {})

    rows: list[dict] = []
    for tau in TAU_GRID:
        # Soothsayer v1 (deployed)
        if tau in v1:
            r = v1[tau]
            rows.append({
                "tau": tau, "oracle": "soothsayer_v1_deployed",
                "n": r["n"], "panel": "OOS 2023+ (yahoo daily, 173 weekends)",
                "halfwidth_bps_at_tau": r["halfwidth_bps"],
                "realized_at_tau_band": r["realized"],
                "k_or_kpct_supplier": "published",
                "notes": f"Kupiec p_uc={r['p_uc']:.3f}. Soothsayer publishes the calibrated band; no consumer back-fit.",
            })
        # Soothsayer M5 (v2 candidate; same OOS panel)
        if tau in m5:
            r = m5[tau]
            rows.append({
                "tau": tau, "oracle": "soothsayer_m5_v2_candidate",
                "n": r["n"], "panel": "OOS 2023+ (yahoo daily, 173 weekends)",
                "halfwidth_bps_at_tau": r["halfwidth_bps"],
                "realized_at_tau_band": r["realized"],
                "k_or_kpct_supplier": "published",
                "notes": f"Kupiec p_uc={r['p_uc']:.3f}. v2 candidate; deployment deferred until post-2026-05-10.",
            })
        # Pyth — smallest k * conf hitting τ; n is the available subset
        if pyth is not None and not pyth.empty:
            hit = _smallest_k_at_tau(pyth.rename(columns={"mean_halfwidth_bps": "halfwidth_bps"}),
                                     tau, k_col="k", hw_col="halfwidth_bps")
            if hit is not None:
                rows.append({
                    "tau": tau, "oracle": "pyth_smallest_k",
                    "n": hit["n"], "panel": "OOS 2024+ available subset (n=265, SPY/QQQ/TLT/TSLA-heavy)",
                    "halfwidth_bps_at_tau": hit["halfwidth_bps"],
                    "realized_at_tau_band": hit["realized"],
                    "k_or_kpct_supplier": f"consumer-supplied k = {hit['k']:.1f} on `pyth_conf`",
                    "notes": "Pyth `conf` is publisher-dispersion diagnostic, not coverage claim.",
                })
            else:
                rows.append({
                    "tau": tau, "oracle": "pyth_smallest_k",
                    "n": int(pyth.iloc[0]["n"]) if len(pyth) else 0,
                    "panel": "OOS 2024+ available subset",
                    "halfwidth_bps_at_tau": float("inf"),
                    "realized_at_tau_band": float("nan"),
                    "k_or_kpct_supplier": "no k in sweep crosses τ",
                    "notes": "Pyth `conf` × any sweep multiplier under-covered τ on this panel.",
                })
        # Chainlink — frozen 87-obs panel, k_pct on stale mid
        if chainlink is not None and not chainlink.empty:
            hit = _smallest_k_at_tau(chainlink, tau, k_col="k_pct", hw_col="halfwidth_bps")
            if hit is not None:
                rows.append({
                    "tau": tau, "oracle": "chainlink_streams_smallest_k_pct",
                    "n": hit["n"], "panel": "frozen 87-obs panel 2026-02-06 → 2026-04-17",
                    "halfwidth_bps_at_tau": hit["halfwidth_bps"],
                    "realized_at_tau_band": hit["realized"],
                    "k_or_kpct_supplier": f"consumer-supplied k_pct = {hit['k']*100:.2f}% on stale mid",
                    "notes": "Chainlink bid/ask zeroed under marketStatus=5 (weekend); we wrap the stale mid.",
                })
        # RedStone — forward-tape, point-only
        if redstone is not None and not redstone.empty:
            hit = _smallest_k_at_tau(redstone, tau, k_col="k_pct", hw_col="halfwidth_bps")
            if hit is not None:
                rows.append({
                    "tau": tau, "oracle": "redstone_smallest_k_pct",
                    "n": hit["n"], "panel": f"forward-tape, n={hit['n']} (4 weekends × 3 symbols)",
                    "halfwidth_bps_at_tau": hit["halfwidth_bps"],
                    "realized_at_tau_band": hit["realized"],
                    "k_or_kpct_supplier": f"consumer-supplied k_pct = {hit['k']*100:.2f}% on RedStone point",
                    "notes": "Forward-tape; sample grows weekly. Tape carries SPY/QQQ/MSTR underliers only.",
                })
        # Kamino Scope — forward-tape, point-only
        if scope is not None and not scope.empty:
            hit = _smallest_k_at_tau(scope, tau, k_col="k_pct", hw_col="halfwidth_bps")
            if hit is not None:
                rows.append({
                    "tau": tau, "oracle": "kamino_scope_smallest_k_pct",
                    "n": hit["n"], "panel": f"forward-tape, n={hit['n']}",
                    "halfwidth_bps_at_tau": hit["halfwidth_bps"],
                    "realized_at_tau_band": hit["realized"],
                    "k_or_kpct_supplier": f"consumer-supplied k_pct = {hit['k']*100:.2f}% on Scope point",
                    "notes": "xStock-native; forward-tape; sample grows weekly.",
                })

    summary = pd.DataFrame(rows)
    out_csv = REPORTS / "tables" / "incumbent_oracle_unified_summary.csv"
    summary.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv}", flush=True)

    md_lines: list[str] = [
        "# V1b — Incumbent oracle unified comparison",
        "",
        "**Question.** Across the four incumbent oracles serving xStock-relevant symbols on Solana "
        "(Pyth, Chainlink Data Streams, RedStone, Kamino Scope), what published-band half-width "
        "(in bps of price) does each require to deliver τ-coverage of the realised "
        "Friday-close → Monday-open weekend gap? How does that compare to Soothsayer's deployed v1 "
        "served band?",
        "",
        "**Construction.** This table is *not* a single-panel head-to-head — incumbent tape recency "
        "varies (Pyth 2024+, Chainlink frozen 2026-02→04 panel, RedStone + Scope forward-tape "
        "2026-04→ ongoing) and the symbol coverage differs (Pyth covers 8 underliers; RedStone "
        "covers SPY/QQQ/MSTR only; Scope covers 8 xStocks). Per-row n is the available-subset n on "
        "each oracle's own panel. The row-level comparison is *width-cost-to-target on each "
        "oracle's own data*. The Soothsayer v1 row uses the same OOS 2023+ panel that backs §6 / "
        "§7 of Paper 1.",
        "",
        "## Headline table",
        "",
        summary.to_markdown(index=False, floatfmt=(".2f", "", "", "", ".0f", ".3f", "", "")),
        "",
        "## Reading",
        "",
        "Three things this table makes precise:",
        "",
        "1. **Only Soothsayer publishes `halfwidth_bps_at_tau` directly.** Every other row's "
        "`halfwidth_bps_at_tau` is the smallest in the consumer-supplied k-sweep (k or k_pct) that "
        "crosses τ realised. The consumer pays the calibration cost themselves — Soothsayer "
        "publishes it as a first-class field with an audit-able receipt.",
        "2. **Per-row sample sizes differ by an order of magnitude.** Soothsayer's row is on "
        "1,720 OOS observations; Pyth's row is on its 265-obs available subset; Chainlink's row is "
        "on a 87-obs frozen panel; RedStone and Scope are forward-tape baselines whose sample "
        "grows weekly. Cell-to-cell differences must be read with this caveat.",
        "3. **Forward-tape rows over-cover trivially under sample-window-specific gentle weekends.** "
        "RedStone's smallest k_pct hitting τ=0.95 looks small on a 12-obs sample where weekends "
        "have been mild; this is a sample-window feature and should be expected to widen as more "
        "weekends accrue (especially long weekends and earnings-adjacent windows).",
        "",
        "## Per-oracle source reports",
        "",
        "- Pyth: `reports/v1b_pyth_comparison.md`",
        "- Chainlink Data Streams: `reports/v1b_chainlink_comparison.md`",
        "- RedStone: `reports/v1b_redstone_comparison.md`",
        "- Kamino Scope: `reports/v1b_kamino_scope_comparison.md`",
        "",
        "## How to keep this current",
        "",
        "Re-run the four per-oracle scripts then this unified runner whenever a new weekend's "
        "Yahoo Monday-open lands in scryer (typically Tuesday by 14:00 UTC):",
        "",
        "```bash",
        "PYTHONPATH=src .venv/bin/python scripts/redstone_benchmark_comparison.py",
        "PYTHONPATH=src .venv/bin/python scripts/kamino_scope_benchmark_comparison.py",
        "PYTHONPATH=src .venv/bin/python scripts/run_incumbent_oracle_unified_report.py",
        "```",
        "",
        "Pyth and Chainlink are not re-run by default (Pyth's panel is 2024+; Chainlink's is a "
        "frozen pre-cutover artifact); refresh those when extending their respective historical "
        "backfills.",
        "",
        "Reproducible via `scripts/run_incumbent_oracle_unified_report.py`. "
        "Per-row data: `reports/tables/incumbent_oracle_unified_summary.csv`.",
    ]

    out_md = REPORTS / "v1b_incumbent_oracle_comparison.md"
    out_md.write_text("\n".join(md_lines))
    print(f"Wrote {out_md}", flush=True)
    print("\nUnified summary:")
    print(summary.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
