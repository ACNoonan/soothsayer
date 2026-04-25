"""
Leave-one-symbol-out cross-asset OOS validation.

Question. Every per-symbol coverage number in §6 of the paper is computed on
a calibration surface that included that symbol's data. To validate that the
*mechanism* (factor-switchboard + log-log regime + empirical-quantile
inversion + per-target buffer) transfers to unseen tickers, we hold out
each symbol in turn and serve it through the pooled-fallback path.

Method. For symbol $s_k$:
  1. Build the calibration surface on `bounds_train` filtered to $\{s : s \ne s_k\}$
     and `fri_ts < 2023-01-01`.
  2. Build the pooled surface (regime-only) on the same filtered training set.
  3. Serve symbol $s_k$ on its OOS 2023+ weekends. Because the per-symbol
     surface for $s_k$ is empty, the Oracle's `_invert_to_claimed` falls
     through to the pooled surface — exactly the production code path for
     a symbol with sparse history.
  4. Compute realised coverage at τ ∈ \{0.68, 0.85, 0.95\} on the held-out
     symbol's slice. Report per-symbol leave-one-out vs in-sample diff.

Outputs:
  reports/tables/v1b_leave_one_out.csv
  reports/v1b_leave_one_out.md
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.backtest import calibration as cal
from soothsayer.backtest import metrics as met
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95)


def _tables_dir() -> Path:
    p = REPORTS / "tables"; p.mkdir(parents=True, exist_ok=True); return p


def _serve_panel(bounds_oos, panel_oos, surface, surface_pooled, target):
    oracle = Oracle(bounds=bounds_oos, surface=surface, surface_pooled=surface_pooled)
    rows = []
    for _, w in panel_oos.iterrows():
        try:
            pp = oracle.fair_value(w["symbol"], w["fri_ts"], target_coverage=target)
        except ValueError:
            continue
        inside = (w["mon_open"] >= pp.lower) and (w["mon_open"] <= pp.upper)
        rows.append({
            "symbol": w["symbol"], "fri_ts": w["fri_ts"], "regime_pub": w["regime_pub"],
            "inside": int(inside), "half_width_bps": float(pp.half_width_bps),
            "claim_served": float(pp.claimed_coverage_served),
            "calibration_path": pp.diagnostics.get("calibration", "?"),
        })
    return pd.DataFrame(rows)


def _stats(served: pd.DataFrame, target: float) -> dict:
    if served.empty:
        return {"n": 0, "realized": float("nan"), "mean_half_width_bps": float("nan"),
                "p_uc": float("nan"), "p_ind": float("nan")}
    n = int(len(served))
    realized = float(served["inside"].mean())
    hw = float(served["half_width_bps"].mean())
    v = (~served["inside"].astype(bool)).astype(int).values
    _, p_uc = met._lr_kupiec(v, target)
    lr_ind_total, n_groups = 0.0, 0
    for sym, g in served.sort_values(["symbol", "fri_ts"]).groupby("symbol"):
        lr_ind, _ = met._lr_christoffersen_independence(
            (~g["inside"].astype(bool)).astype(int).values)
        if not np.isnan(lr_ind):
            lr_ind_total += lr_ind
            n_groups += 1
    p_ind = float(1.0 - chi2.cdf(max(lr_ind_total, 0.0), df=n_groups)) if n_groups > 0 else float("nan")
    return {"n": n, "realized": realized, "mean_half_width_bps": hw,
            "p_uc": float(p_uc), "p_ind": p_ind}


def main() -> None:
    bounds_full = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds_full["fri_ts"] = pd.to_datetime(bounds_full["fri_ts"]).dt.date
    bounds_full["mon_ts"] = pd.to_datetime(bounds_full["mon_ts"]).dt.date

    panel_full = bounds_full[
        ["symbol", "fri_ts", "mon_ts", "regime_pub", "mon_open", "fri_close"]
    ].drop_duplicates(["symbol", "fri_ts"]).reset_index(drop=True)
    panel_oos = panel_full[panel_full["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_oos = bounds_full[bounds_full["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    bounds_train_full = bounds_full[bounds_full["fri_ts"] < SPLIT_DATE].reset_index(drop=True)

    symbols = sorted(panel_oos["symbol"].unique())
    print(f"Leave-one-out across {len(symbols)} symbols × {len(TARGETS)} targets", flush=True)

    # In-sample baseline (full surface) for the diff
    full_surface = cal.compute_calibration_surface(bounds_train_full)
    full_pooled = cal.pooled_surface(bounds_train_full)
    in_sample_rows = []
    for sym in symbols:
        panel_sym = panel_oos[panel_oos["symbol"] == sym].reset_index(drop=True)
        bounds_sym_oos = bounds_oos[bounds_oos["symbol"] == sym].reset_index(drop=True)
        for t in TARGETS:
            served = _serve_panel(bounds_sym_oos, panel_sym, full_surface, full_pooled, t)
            s = _stats(served, t)
            in_sample_rows.append({"held_out": sym, "split": "in_sample", "target": t, **s})

    # Leave-one-out
    loo_rows = []
    t0 = time.time()
    for sym in symbols:
        bounds_train_sub = bounds_train_full[bounds_train_full["symbol"] != sym].reset_index(drop=True)
        sub_surface = cal.compute_calibration_surface(bounds_train_sub)
        sub_pooled = cal.pooled_surface(bounds_train_sub)
        panel_sym = panel_oos[panel_oos["symbol"] == sym].reset_index(drop=True)
        bounds_sym_oos = bounds_oos[bounds_oos["symbol"] == sym].reset_index(drop=True)
        for t in TARGETS:
            served = _serve_panel(bounds_sym_oos, panel_sym, sub_surface, sub_pooled, t)
            s = _stats(served, t)
            loo_rows.append({"held_out": sym, "split": "leave_one_out", "target": t, **s,
                             "calibration_path_modal": served["calibration_path"].mode().iloc[0]
                             if not served.empty and "calibration_path" in served.columns else None})
        elapsed = time.time() - t0
        print(f"  [{symbols.index(sym)+1}/{len(symbols)}] {sym} done; elapsed={elapsed:.0f}s", flush=True)

    in_sample = pd.DataFrame(in_sample_rows)
    loo = pd.DataFrame(loo_rows)

    # Wide form for the comparison table
    df = pd.concat([in_sample, loo], ignore_index=True)
    df.to_csv(_tables_dir() / "v1b_leave_one_out.csv", index=False)

    # Pivot: per (held_out, target) show in_sample vs leave_one_out realised
    pivot = df.pivot_table(index=["held_out", "target"], columns="split",
                            values=["realized", "mean_half_width_bps", "p_uc", "p_ind"]).reset_index()
    print()
    print("=" * 80)
    print("LEAVE-ONE-OUT vs IN-SAMPLE realised coverage")
    print("=" * 80)
    # Compact print: per-symbol per-target in_sample → loo realised
    rows_print = []
    for sym in symbols:
        for t in TARGETS:
            isd = in_sample[(in_sample["held_out"] == sym) & (in_sample["target"] == t)]
            lod = loo[(loo["held_out"] == sym) & (loo["target"] == t)]
            if isd.empty or lod.empty:
                continue
            rows_print.append({
                "symbol": sym, "target": t,
                "n": int(isd.iloc[0]["n"]),
                "in_sample_realized": float(isd.iloc[0]["realized"]),
                "loo_realized": float(lod.iloc[0]["realized"]),
                "delta": float(lod.iloc[0]["realized"] - isd.iloc[0]["realized"]),
                "in_sample_hw_bps": float(isd.iloc[0]["mean_half_width_bps"]),
                "loo_hw_bps": float(lod.iloc[0]["mean_half_width_bps"]),
                "loo_p_uc": float(lod.iloc[0]["p_uc"]),
                "loo_p_ind": float(lod.iloc[0]["p_ind"]),
            })
    summary = pd.DataFrame(rows_print)
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # Pooled at τ=0.85 and τ=0.95 across all held-out symbols
    print()
    print("=" * 80)
    print("POOLED across held-out symbols")
    print("=" * 80)
    pooled_rows = []
    for split in ["in_sample", "leave_one_out"]:
        for t in TARGETS:
            sub = df[(df["split"] == split) & (df["target"] == t)]
            if sub.empty:
                continue
            # pooled means weighted by n
            n_total = int(sub["n"].sum())
            cov = float((sub["realized"] * sub["n"]).sum() / n_total)
            hw = float((sub["mean_half_width_bps"] * sub["n"]).sum() / n_total)
            pooled_rows.append({
                "split": split, "target": t, "n_total": n_total,
                "weighted_realized": cov, "weighted_hw_bps": hw,
            })
    pooled = pd.DataFrame(pooled_rows)
    print(pooled.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # Headline: max degradation in realised coverage from in-sample to LOO
    if not summary.empty:
        max_drop = float((summary["in_sample_realized"] - summary["loo_realized"]).max())
        worst_idx = (summary["in_sample_realized"] - summary["loo_realized"]).idxmax()
        worst = summary.iloc[worst_idx]
        print()
        print(f"Largest in-sample → LOO drop: {max_drop:.3f} (at {worst['symbol']}, τ = {worst['target']})")
        n_pass_loo = int((summary["loo_p_uc"] > 0.05).sum())
        print(f"LOO Kupiec pass at α=0.05: {n_pass_loo}/{len(summary)} (symbol, τ) cells")

    # Writeup
    md = [
        "# V1b — Leave-one-symbol-out cross-asset validation",
        "",
        "**Question.** The per-symbol coverage results in §6.5 of the paper are computed on a calibration surface that *included* the symbol being scored. A reviewer who picks up the paper and asks *would this work for an unseen ticker?* has no evidence-based answer from §6.5. This diagnostic provides one.",
        "",
        f"**Method.** For each of the {len(symbols)} symbols, refit the calibration surface on the *other* nine symbols' pre-2023 data only, then serve the held-out symbol on its 2023+ OOS slice. Because the per-symbol surface for the held-out ticker is empty, the Oracle's surface-inversion code falls through to the pooled (regime-only) surface — the production path for any ticker with sparse history. Compare in-sample realised coverage (full surface) to leave-one-out realised coverage at τ ∈ {0.68, 0.85, 0.95}.",
        "",
        "## Per-symbol results",
        "",
        summary.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Pooled across held-out symbols",
        "",
        pooled.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Reading",
        "",
        "**If LOO realised tracks in-sample within ~2pp at τ=0.85 and τ=0.95:** the calibration *mechanism* transfers to unseen tickers — the per-symbol surface contributes refinement, but the regime-pooled fallback delivers the headline calibration claim by itself. This supports a paper claim that the methodology generalises to tickers outside our 10-symbol universe (subject to the same regime-labeler and factor-switchboard).",
        "",
        "**If specific symbols show large LOO drops:** those tickers' per-symbol surfaces were doing real work, and the methodology requires symbol-specific calibration to deliver the headline number. This narrows the generalisation claim from \"the mechanism\" to \"the mechanism + per-symbol fitted surface\". Disclose accordingly.",
        "",
        "Raw artefacts: `reports/tables/v1b_leave_one_out.csv`. Reproducible via `scripts/run_leave_one_out.py`.",
    ]
    out = REPORTS / "v1b_leave_one_out.md"
    out.write_text("\n".join(md))
    print()
    print(f"Wrote {out}")
    print(f"Wrote {_tables_dir() / 'v1b_leave_one_out.csv'}")


if __name__ == "__main__":
    main()
