"""
Forward-tape variant comparison evaluator — §13.6 selection-procedure mitigation.

Companion to `run_forward_tape_evaluation.py`. Where that script evaluates
the canonical (EWMA HL=8) deployment artefact against the forward tape,
THIS script evaluates *all five* Phase 5 σ̂ variants — frozen at the same
training cutoff in `lwc_variant_bundle_v1_frozen_*.json` — against the
same forward weekends.

The point is held-out re-validation of the Phase 5 selection. None of the
forward weekends were used to select EWMA HL=8 from the variant ladder;
the bundle was frozen at the same cutoff as the canonical artefact. So
the per-variant comparison on forward data is a genuine independent check
on whether the in-sample selection generalises.

Critical contract: this script must NEVER touch the bundle's frozen
schedules. It re-computes σ̂ for each variant on the combined
context+forward panel (using the σ̂ rule recorded in the variant's
sidecar block), but the regime quantile table, c-bump schedule, and
δ-shift schedule are read directly from the bundle JSON and applied
unchanged.

Behaviour
---------
- 0 forward rows in the tape: graceful exit. No comparison report written.
- ≥ 1 forward weekend: writes per-variant pooled OOS metrics + a comparison
  table. < 4 weekends gets a "preliminary" banner same as the canonical
  evaluator.
- Re-validation framing: the report does NOT re-select among variants on
  forward data. Its role is to validate that the canonical (HL=8) variant
  still looks at least as good as the others on data the comparison never
  saw — if a different variant looked dramatically cleaner, that's a flag
  to revisit, not a flag to re-deploy.

Outputs
-------
  reports/m6_forward_tape_{N}weekends_variants.md
  reports/tables/m6_forward_tape_{N}weekends_variants.csv

Run
---
  uv run python scripts/run_forward_tape_variant_comparison.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    SIGMA_HAT_MIN,
    add_sigma_hat_sym,
    add_sigma_hat_sym_blend,
    add_sigma_hat_sym_ewma,
)
from soothsayer.config import DATA_PROCESSED, REPORTS


FORWARD_TAPE_PATH = DATA_PROCESSED / "forward_tape_v1.parquet"
BUNDLE_GLOB = "lwc_variant_bundle_v1_frozen_*.json"
CANONICAL_VARIANT = "ewma_hl8"


# ============================================================ bundle discovery


def _load_bundle(suffix: str | None) -> tuple[Path, dict]:
    if suffix is not None:
        path = DATA_PROCESSED / f"lwc_variant_bundle_v1_frozen_{suffix}.json"
        if not path.exists():
            raise FileNotFoundError(f"Variant bundle not found: {path}")
    else:
        candidates = sorted(DATA_PROCESSED.glob(BUNDLE_GLOB))
        if not candidates:
            raise FileNotFoundError(
                f"No variant bundle in data/processed/. Run "
                "`uv run python scripts/freeze_sigma_ewma_variant_bundle.py` first."
            )
        path = candidates[-1]
    return path, json.loads(path.read_text())


def _variant_schedules(variant: dict) -> tuple[dict, dict, dict]:
    """Pull the three frozen schedules out of one variant block."""
    qt = {
        regime: {float(tau): float(b) for tau, b in row.items()}
        for regime, row in variant["regime_quantile_table"].items()
    }
    cb = {float(tau): float(c)
          for tau, c in variant["c_bump_schedule"].items()}
    delta = {float(tau): float(d)
             for tau, d in variant["delta_shift_schedule"].items()}
    return qt, cb, delta


# =================================================================== σ̂ per variant


def _compute_variant_sigma(panel: pd.DataFrame, variant: dict) -> tuple[pd.DataFrame, str]:
    """Apply the variant's σ̂ rule to `panel`. Returns (panel_with_col, raw_col).

    Dispatches on `sigma_hat.method` recorded in the bundle:
      trailing_window  -> add_sigma_hat_sym(K=K_weekends, min_obs=min_past_obs)
      ewma             -> add_sigma_hat_sym_ewma(half_life)
      blend            -> add_sigma_hat_sym_blend(alpha, half_life, K)
    """
    sigma = variant["sigma_hat"]
    method = sigma["method"]
    raw_col = sigma["raw_column"]
    min_obs = int(sigma.get("min_past_obs", SIGMA_HAT_MIN))
    if method == "trailing_window":
        return add_sigma_hat_sym(panel, K=int(sigma["K_weekends"]),
                                 min_obs=min_obs), raw_col
    if method == "ewma":
        return add_sigma_hat_sym_ewma(
            panel, half_life=int(sigma["half_life_weekends"]),
            min_obs=min_obs,
        ), raw_col
    if method == "blend":
        return add_sigma_hat_sym_blend(
            panel, alpha=float(sigma["alpha"]),
            half_life=int(sigma["half_life_weekends"]),
            K=int(sigma["K_weekends"]),
            min_obs=min_obs,
        ), raw_col
    raise ValueError(f"Unknown σ̂ method {method!r} in variant {variant['_lwc_variant']!r}")


# ============================================================ serve + metrics


def _interp(table: dict[float, float], x: float) -> float:
    keys = sorted(table.keys())
    if x <= keys[0]:
        return float(table[keys[0]])
    if x >= keys[-1]:
        return float(table[keys[-1]])
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= x <= hi:
            frac = (x - lo) / (hi - lo)
            return float(table[lo] + frac * (table[hi] - table[lo]))
    return float(table[keys[-1]])


def _serve_variant(panel: pd.DataFrame, qt: dict, cb: dict, delta: dict,
                    sigma_col: str,
                    taus: tuple[float, ...] = DEFAULT_TAUS) -> dict[float, pd.DataFrame]:
    """Apply a frozen variant's serving formula. Identical math to
    `serve_bands_lwc` but parameterised on the σ̂ column (different per
    variant) and reads schedules straight from the bundle JSON."""
    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    fri_close = panel["fri_close"].astype(float).to_numpy()
    sigma = panel[sigma_col].astype(float).to_numpy()
    cells = panel["regime_pub"].astype(str).to_numpy()
    out: dict[float, pd.DataFrame] = {}
    anchors = sorted(cb.keys())
    for tau in taus:
        d = float(delta.get(tau, 0.0))
        served = min(tau + d, anchors[-1])
        c = _interp(cb, served)
        b_per_row = np.array(
            [_interp(qt[c_], served) if c_ in qt else np.nan for c_ in cells],
            dtype=float,
        )
        unk = ~np.isfinite(b_per_row)
        if unk.any() and "high_vol" in qt:
            b_per_row[unk] = _interp(qt["high_vol"], served)
        q_eff = c * b_per_row
        half = q_eff * sigma * fri_close
        out[tau] = pd.DataFrame(
            {"lower": point.values - half, "upper": point.values + half},
            index=panel.index,
        )
    return out


def _pooled_metrics(panel: pd.DataFrame, bounds: dict,
                    taus: tuple[float, ...]) -> pd.DataFrame:
    rows = []
    for tau in taus:
        b = bounds[tau]
        inside = ((panel["mon_open"] >= b["lower"]) &
                  (panel["mon_open"] <= b["upper"]))
        v = (~inside).astype(int).to_numpy()
        lr_uc, p_uc = met._lr_kupiec(v, tau)
        cc = met.conditional_coverage_from_bounds(
            panel, {tau: b}, group_by="symbol"
        )
        cc0 = cc.iloc[0]
        rows.append({
            "tau": float(tau),
            "n": int(len(panel)),
            "realised": float(inside.mean()),
            "half_width_bps": float(((b["upper"] - b["lower"]) / 2
                                     / panel["fri_close"] * 1e4).mean()),
            "kupiec_lr": float(lr_uc),
            "kupiec_p": float(p_uc),
            "christ_lr": float(cc0["lr_ind"]),
            "christ_p": float(cc0["p_ind"]),
        })
    return pd.DataFrame(rows)


# ===================================================================== render


def _render_report(
    n_weekends: int,
    fri_ts_range: tuple,
    per_variant_pooled: dict[str, pd.DataFrame],
    bundle_path: Path,
    bundle: dict,
    is_preliminary: bool,
) -> Path:
    out_path = REPORTS / f"m6_forward_tape_{n_weekends}weekends_variants.md"
    sha = bundle.get("_artefact_sha256", "<unknown>")
    freeze = bundle.get("_freeze_date", "<unknown>")

    lines = [
        f"# M6 σ̂ variant comparison — forward tape, {n_weekends} weekends since freeze",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.",
        f"**Variant bundle:** `{bundle_path.name}` (SHA-256 `{sha[:12]}…`, "
        f"freeze date {freeze}).",
        f"**Forward window:** {fri_ts_range[0]} → {fri_ts_range[1]}.",
        "",
        "**Role of this report.** §13.6 of `reports/m6_sigma_ewma.md` describes "
        "the selection-procedure transparency layer — the canonical M6 σ̂ rule "
        "(EWMA HL=8) was selected from a 5-variant ladder under a multi-test-"
        "exposed criterion (80 split-date Christoffersen cells). To re-validate "
        "the selection on data it never saw, this report scores all five "
        "variants on the same forward weekends. The intent is *re-validation*, "
        "not *re-selection*: a different variant looking cleaner here is a flag "
        "to revisit, not to re-deploy.",
        "",
    ]
    if is_preliminary:
        lines += [
            "> **Preliminary** — fewer than 4 forward weekends accumulated; "
            "treat the comparison as anecdotal until ≥ 4 weekends land. "
            "Per-variant Christoffersen and Kupiec are uninformative at this n.",
            "",
        ]

    lines += [
        "## 1. Pooled OOS — all variants at every served τ",
        "",
        "| variant | τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant_name, pooled in per_variant_pooled.items():
        marker = " (canonical)" if variant_name == CANONICAL_VARIANT else ""
        for _, r in pooled.iterrows():
            lines.append(
                f"| {variant_name}{marker} | {r['tau']:.2f} | {int(r['n'])} | "
                f"{r['realised']:.4f} | {r['half_width_bps']:.1f} | "
                f"{r['kupiec_p']:.4f} | {r['christ_p']:.4f} |"
            )

    lines += [
        "",
        "## 2. Headline comparison — variant × τ pooled half-width (bps)",
        "",
    ]
    # Build a width comparison table: rows=variant, cols=τ
    taus = sorted({float(r["tau"]) for r in per_variant_pooled[
        next(iter(per_variant_pooled))].to_dict("records")})
    header = "| variant | " + " | ".join(f"τ={t:.2f}" for t in taus) + " |"
    sep = "|---|" + "|".join(["---:"] * len(taus)) + "|"
    lines += [header, sep]
    for variant_name, pooled in per_variant_pooled.items():
        marker = " (canonical)" if variant_name == CANONICAL_VARIANT else ""
        cells = []
        for tau in taus:
            row = pooled[pooled["tau"] == tau].iloc[0]
            cells.append(f"{row['half_width_bps']:.1f}")
        lines.append(f"| {variant_name}{marker} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## 3. Headline comparison — realised coverage",
        "",
        header,
        sep,
    ]
    for variant_name, pooled in per_variant_pooled.items():
        marker = " (canonical)" if variant_name == CANONICAL_VARIANT else ""
        cells = []
        for tau in taus:
            row = pooled[pooled["tau"] == tau].iloc[0]
            cells.append(f"{row['realised']:.4f}")
        lines.append(f"| {variant_name}{marker} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## 4. Reproducibility",
        "",
        "```bash",
        "uv run python scripts/freeze_sigma_ewma_variant_bundle.py",
        "uv run python scripts/collect_forward_tape.py",
        "uv run python scripts/run_forward_tape_variant_comparison.py",
        "```",
        "",
        "The variant bundle is read-only. To advance the freeze date, re-run "
        "`scripts/freeze_sigma_ewma_variant_bundle.py` with a new `--date` and "
        "re-run this evaluator.",
        "",
    ]

    out_path.write_text("\n".join(lines))
    return out_path


# ===================================================================== runner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-suffix", default=None,
                        help="YYYYMMDD suffix of the variant bundle "
                             "(defaults to latest).")
    args = parser.parse_args()

    if not FORWARD_TAPE_PATH.exists():
        raise SystemExit(
            f"{FORWARD_TAPE_PATH} not found. Run "
            "`uv run python scripts/collect_forward_tape.py` first."
        )

    tape = pd.read_parquet(FORWARD_TAPE_PATH)
    tape["fri_ts"] = pd.to_datetime(tape["fri_ts"]).dt.date
    forward_count = int(tape["is_forward"].sum())
    n_weekends = (tape[tape["is_forward"]]["fri_ts"].nunique()
                  if forward_count else 0)

    print(f"Forward tape: {len(tape):,} total rows / "
          f"{forward_count:,} forward rows / {n_weekends} forward weekends",
          flush=True)

    if forward_count == 0:
        print("Insufficient data — 0 forward weekends. Skipping variant "
              "comparison report (canonical evaluator handles the stub).",
              flush=True)
        return

    bundle_path, bundle = _load_bundle(args.bundle_suffix)
    print(f"Variant bundle: {bundle_path.name}", flush=True)
    print(f"  freeze_date={bundle.get('_freeze_date')}  "
          f"sha256={bundle.get('_artefact_sha256','')[:12]}…", flush=True)
    print(f"  variants    ={[v['_lwc_variant'] for v in bundle['variants']]}",
          flush=True)

    # σ̂ for every variant must come from the same combined context+forward
    # panel — each variant's σ̂ rule is applied separately. We compute σ̂ once
    # per variant on the full tape, then filter to forward rows that have a
    # finite σ̂ for THIS variant (warm-up boundaries vary slightly between
    # rules but in practice all five share the ≥ 8 past-obs warm-up).
    per_variant_pooled: dict[str, pd.DataFrame] = {}
    table_rows: list[dict] = []
    for variant in bundle["variants"]:
        name = variant["_lwc_variant"]
        qt, cb, delta = _variant_schedules(variant)
        full = tape.copy()
        full, raw_col = _compute_variant_sigma(full, variant)
        forward = full[full["is_forward"] & full[raw_col].notna()].copy()
        forward = forward.sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
        n_forward = len(forward)
        print(f"  {name:>15s}: {n_forward} forward rows w/ σ̂", flush=True)
        if n_forward == 0:
            continue
        bounds = _serve_variant(forward, qt, cb, delta, sigma_col=raw_col)
        pooled = _pooled_metrics(forward, bounds, DEFAULT_TAUS)
        pooled.insert(0, "variant", name)
        per_variant_pooled[name] = pooled
        for _, r in pooled.iterrows():
            table_rows.append({**{"variant": name}, **r.to_dict()})

    if not per_variant_pooled:
        print("All variants returned 0 evaluable forward rows — exiting.",
              flush=True)
        return

    out_csv = REPORTS / "tables" / f"m6_forward_tape_{n_weekends}weekends_variants.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(table_rows).to_csv(out_csv, index=False)

    forward_rows_canonical = next(iter(per_variant_pooled.values()))
    fri_ts_range = (
        tape[tape["is_forward"]]["fri_ts"].min(),
        tape[tape["is_forward"]]["fri_ts"].max(),
    )
    is_preliminary = n_weekends < 4
    out_md = _render_report(
        n_weekends, fri_ts_range, per_variant_pooled,
        bundle_path, bundle, is_preliminary,
    )
    print(f"\nWrote {out_md}", flush=True)
    print(f"Wrote {out_csv}", flush=True)


if __name__ == "__main__":
    main()
