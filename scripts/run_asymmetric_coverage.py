"""
W4 — Asymmetric / one-sided coverage analysis (Lending-track sub-axis).

W2 found that single-symbol M5 has wildly heterogeneous PIT variance —
SPY/QQQ compressed (var_z ≈ 0.30–0.44), MSTR/TSLA/HOOD inflated
(var_z ≈ 1.7–2.1). M6b2 (Lending-track) addresses the *scale* by
partitioning the conformal cell on `symbol_class`. W4 asks the
orthogonal question: within each symbol_class, is the *signed* residual
asymmetric? If yes, the symmetric band over-allocates width to one tail
and under-allocates to the other — and the asymmetric quantile pair
(q_low, q_high) is the cleaner Lending-track receipt.

The protocol-side stake is direct. MarginFi uses the lower bound for
asset valuation (P_conf below mid) and the upper bound for liability
valuation (P_conf above mid); a borrower lending MSTRx and borrowing
SPYx wants q_low(MSTRx) and q_high(SPYx) — *not* a symmetric ±hw on
each. Band-perp's long-liquidation buffer reads q_low; short-liquidation
buffer reads q_high. Single-underlier options inherit the asymmetry of
the underlying.

For each symbol_class × τ ∈ {0.68, 0.85, 0.95, 0.99}, this script:

  1. Fits the symmetric M6b2 quantile b_sym(class, τ) on the pre-2023
     calibration set as the (1-α)(n+1)/n quantile of |r|.
  2. Fits the equal-tail asymmetric pair (q_low(class, τ), q_high(class, τ))
     such that P(r < -q_low) ≈ P(r > q_high) ≈ (1-τ)/2 on the same train slice.
  3. Evaluates both bands on the OOS 2023+ slice: pooled coverage, left-tail
     violation rate, right-tail violation rate, total width per row.
  4. Tests H0: left_viol_rate == right_viol_rate per (class, τ) under the
     symmetric band, via binomial test on the conditional sign of violations.
  5. Computes the *one-sided* asymmetric width that lending consumers
     actually use — q_low at one-sided τ_one = q_low at two-sided τ_two
     where (1-τ_two)/2 = 1-τ_one. Reports the width vs symmetric b at the
     same τ_one.
  6. Aggregates a Paper 3-style decision: per-class, does the asymmetric
     pair materially differ from the symmetric? Pooled width premium of
     symmetric over asymmetric at matched two-sided τ?

Outputs:
  reports/tables/v1b_w4_asymmetric_per_class_tau.csv   per-(class, τ) numerics
  reports/tables/v1b_w4_asymmetric_one_sided.csv       per-(class, τ_one) lending-consumer view
  reports/tables/v1b_w4_skewness_train.csv             sign-test + skewness diagnostics
  reports/v1b_w4_asymmetric_coverage_lending.md        paper-ready writeup
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import binomtest, skew as scipy_skew

from soothsayer.config import DATA_PROCESSED, REPORTS

SPLIT_DATE = date(2023, 1, 1)
TARGETS = (0.68, 0.85, 0.95, 0.99)

# Locked symbol_class mapping (matches M6_REFACTOR.md Phase A1 + scripts/run_m6b_per_symbol_class_mondrian.py)
SYMBOL_CLASS = {
    "SPY": "equity_index", "QQQ": "equity_index",
    "AAPL": "equity_meta", "GOOGL": "equity_meta",
    "NVDA": "equity_highbeta", "TSLA": "equity_highbeta", "MSTR": "equity_highbeta",
    "HOOD": "equity_recent",
    "GLD": "gold",
    "TLT": "bond",
}

# Width-difference threshold below which we declare "asymmetry not material"
MATERIAL_WIDTH_DELTA_PCT = 0.05  # 5% relative difference between q_low and q_high
# Min cell size for τ=0.99 asymmetric quantile estimation (need >=5 obs in each tail)
MIN_N_FOR_TAU_99 = 500


def conformal_quantile_symmetric(scores: np.ndarray, tau: float) -> float:
    """M6b2 symmetric: (1-α)(n+1)/n quantile of |r|."""
    n = len(scores)
    if n < 5:
        return float("nan")
    k = min(max(int(np.ceil(tau * (n + 1))), 1), n)
    sorted_scores = np.sort(scores)
    return float(sorted_scores[k - 1])


def conformal_quantile_asymmetric(signed_r: np.ndarray, tau: float) -> tuple[float, float]:
    """Equal-tail asymmetric: (q_low, q_high) such that P(r < -q_low) ≈ P(r > q_high) ≈ (1-τ)/2.

    Both q_low and q_high are returned as positive magnitudes (i.e., q_low > 0
    is the distance below point on the left side; q_high > 0 is the distance
    above point on the right side). The band is [point - q_low·fri_close,
    point + q_high·fri_close]."""
    n = len(signed_r)
    if n < 5:
        return float("nan"), float("nan")
    alpha = 1.0 - tau
    sorted_r = np.sort(signed_r)
    # Lower tail: P(r ≤ -q_low) = α/2  ⟹  -q_low = quantile(r, α/2)
    k_low = min(max(int(np.floor(alpha / 2.0 * (n + 1))), 1), n)
    q_low = -float(sorted_r[k_low - 1])
    # Upper tail: P(r ≥ q_high) = α/2  ⟹  q_high = quantile(r, 1 - α/2)
    k_high = min(max(int(np.ceil((1.0 - alpha / 2.0) * (n + 1))), 1), n)
    q_high = float(sorted_r[k_high - 1])
    return q_low, q_high


def conformal_quantile_one_sided(signed_r: np.ndarray, tau: float, side: str) -> float:
    """One-sided conformal quantile for the lending-consumer view.

      side="lower" (asset valuation): q_low_one(τ) such that P(r ≥ -q_low_one) = τ
                                      i.e., q_low_one = quantile(-r, τ) = -quantile(r, 1-τ)
      side="upper" (liability valuation): q_high_one(τ) such that P(r ≤ q_high_one) = τ
                                          i.e., q_high_one = quantile(r, τ)
    """
    n = len(signed_r)
    if n < 5:
        return float("nan")
    sorted_r = np.sort(signed_r)
    if side == "lower":
        k = min(max(int(np.floor((1.0 - tau) * (n + 1))), 1), n)
        return -float(sorted_r[k - 1])
    elif side == "upper":
        k = min(max(int(np.ceil(tau * (n + 1))), 1), n)
        return float(sorted_r[k - 1])
    raise ValueError(f"side must be 'lower' or 'upper', got {side!r}")


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet")
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]).copy()
    panel["point_fa"] = panel["fri_close"].astype(float) * (1.0 + panel["factor_ret"].astype(float))
    panel["r"] = (panel["mon_open"] - panel["point_fa"]) / panel["fri_close"]
    panel["symbol_class"] = panel["symbol"].map(SYMBOL_CLASS)
    assert panel["symbol_class"].notna().all()

    panel_train = panel[panel["fri_ts"] < SPLIT_DATE].reset_index(drop=True)
    panel_oos = panel[panel["fri_ts"] >= SPLIT_DATE].reset_index(drop=True)
    print(f"train: {len(panel_train):,} rows; OOS: {len(panel_oos):,} rows", flush=True)

    classes = sorted(panel["symbol_class"].unique())

    # === Skewness + sign test on TRAIN signed residuals ===
    skew_rows = []
    for cls in classes:
        r = panel_train.loc[panel_train["symbol_class"] == cls, "r"].to_numpy()
        n = len(r)
        n_neg = int((r < 0).sum())
        # H0: P(r < 0) = 0.5; if rejected at α=0.05, the median is asymmetric
        bt = binomtest(n_neg, n, p=0.5, alternative="two-sided")
        skew_rows.append({
            "symbol_class": cls,
            "n_train": n,
            "fraction_negative": n_neg / n,
            "p_sign_test_eq_05": bt.pvalue,
            "skewness": float(scipy_skew(r)),
            "mean_r_train": float(r.mean()),
            "std_r_train": float(r.std(ddof=0)),
        })
    skew_df = pd.DataFrame(skew_rows).sort_values("symbol_class")
    print("\n=== Per-class TRAIN signed-residual sign test + skewness ===")
    print(skew_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"), flush=True)

    # === Symmetric vs asymmetric per (class, τ) ===
    rows: list[dict] = []
    for cls in classes:
        r_train = panel_train.loc[panel_train["symbol_class"] == cls, "r"].to_numpy()
        r_oos = panel_oos.loc[panel_oos["symbol_class"] == cls, "r"].to_numpy()
        abs_r_train = np.abs(r_train)

        for tau in TARGETS:
            # Skip τ=0.99 for thin cells
            if tau == 0.99 and len(r_train) < MIN_N_FOR_TAU_99:
                rows.append({
                    "symbol_class": cls, "tau": tau, "skip_reason": "thin_cell_for_tau99",
                    "n_train": len(r_train), "n_oos": len(r_oos),
                })
                continue

            b_sym = conformal_quantile_symmetric(abs_r_train, tau)
            q_low, q_high = conformal_quantile_asymmetric(r_train, tau)

            # OOS evaluation
            inside_sym = (np.abs(r_oos) <= b_sym).astype(int)
            left_v_sym = (r_oos < -b_sym).astype(int)
            right_v_sym = (r_oos > b_sym).astype(int)
            inside_asym = ((r_oos >= -q_low) & (r_oos <= q_high)).astype(int)
            left_v_asym = (r_oos < -q_low).astype(int)
            right_v_asym = (r_oos > q_high).astype(int)

            # Test of tail-rate equality under symmetric band on TRAIN
            n_left_train = int((r_train < -b_sym).sum())
            n_right_train = int((r_train > b_sym).sum())
            n_viol_train = n_left_train + n_right_train
            if n_viol_train >= 5:
                bt_train = binomtest(n_left_train, n_viol_train, p=0.5, alternative="two-sided")
                p_tail_eq_train = bt_train.pvalue
            else:
                p_tail_eq_train = float("nan")
            # And on OOS
            n_left_oos = int(left_v_sym.sum())
            n_right_oos = int(right_v_sym.sum())
            n_viol_oos = n_left_oos + n_right_oos
            if n_viol_oos >= 5:
                bt_oos = binomtest(n_left_oos, n_viol_oos, p=0.5, alternative="two-sided")
                p_tail_eq_oos = bt_oos.pvalue
            else:
                p_tail_eq_oos = float("nan")

            sym_total_width = 2.0 * b_sym
            asym_total_width = q_low + q_high
            width_delta_pct = (asym_total_width - sym_total_width) / sym_total_width if sym_total_width > 0 else float("nan")
            asym_skew_ratio = (q_high - q_low) / (q_high + q_low) if (q_high + q_low) > 0 else float("nan")

            rows.append({
                "symbol_class": cls, "tau": tau,
                "n_train": len(r_train), "n_oos": len(r_oos),
                "b_sym_bps": b_sym * 1e4,
                "q_low_bps": q_low * 1e4,
                "q_high_bps": q_high * 1e4,
                "sym_total_width_bps": sym_total_width * 1e4,
                "asym_total_width_bps": asym_total_width * 1e4,
                "width_delta_asym_vs_sym_pct": width_delta_pct,
                "asym_skew_ratio": asym_skew_ratio,
                "realised_sym_oos": float(inside_sym.mean()),
                "realised_asym_oos": float(inside_asym.mean()),
                "left_viol_rate_sym_oos": float(left_v_sym.mean()),
                "right_viol_rate_sym_oos": float(right_v_sym.mean()),
                "left_viol_rate_asym_oos": float(left_v_asym.mean()),
                "right_viol_rate_asym_oos": float(right_v_asym.mean()),
                "tail_asymmetry_pp_sym_oos": float(left_v_sym.mean() - right_v_sym.mean()),
                "p_tail_eq_train": p_tail_eq_train,
                "p_tail_eq_oos": p_tail_eq_oos,
                "n_viol_train": n_viol_train,
                "n_viol_oos": n_viol_oos,
            })

    per_cell = pd.DataFrame(rows)
    out_csv = REPORTS / "tables" / "v1b_w4_asymmetric_per_class_tau.csv"
    per_cell.to_csv(out_csv, index=False)
    skew_df.to_csv(REPORTS / "tables" / "v1b_w4_skewness_train.csv", index=False)
    print(f"\nwrote {out_csv}", flush=True)

    # Print per-cell summary
    valid = per_cell[per_cell.get("skip_reason").isna()] if "skip_reason" in per_cell.columns else per_cell
    show_cols = ["symbol_class", "tau", "n_train", "b_sym_bps", "q_low_bps", "q_high_bps",
                 "asym_skew_ratio", "width_delta_asym_vs_sym_pct",
                 "left_viol_rate_sym_oos", "right_viol_rate_sym_oos", "p_tail_eq_oos"]
    print("\n=== Per-(class, τ) symmetric vs asymmetric ===")
    print(valid[show_cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"), flush=True)

    # === One-sided lending-consumer view ===
    one_sided_rows = []
    for cls in classes:
        r_train = panel_train.loc[panel_train["symbol_class"] == cls, "r"].to_numpy()
        r_oos = panel_oos.loc[panel_oos["symbol_class"] == cls, "r"].to_numpy()
        abs_r_train = np.abs(r_train)
        for tau_one in (0.95, 0.99):
            if tau_one == 0.99 and len(r_train) < MIN_N_FOR_TAU_99:
                continue
            q_low_one = conformal_quantile_one_sided(r_train, tau_one, side="lower")
            q_high_one = conformal_quantile_one_sided(r_train, tau_one, side="upper")
            b_sym_two = conformal_quantile_symmetric(abs_r_train, tau_one)

            # Evaluate one-sided OOS coverage
            cov_lower_one = float((r_oos >= -q_low_one).mean())
            cov_upper_one = float((r_oos <= q_high_one).mean())
            cov_sym_one_lower = float((r_oos >= -b_sym_two).mean())
            cov_sym_one_upper = float((r_oos <= b_sym_two).mean())

            one_sided_rows.append({
                "symbol_class": cls, "tau_one_sided": tau_one,
                "n_train": len(r_train), "n_oos": len(r_oos),
                "q_low_one_bps": q_low_one * 1e4,
                "q_high_one_bps": q_high_one * 1e4,
                "b_sym_two_sided_bps": b_sym_two * 1e4,
                "cov_lower_asym_one_oos": cov_lower_one,
                "cov_lower_sym_two_oos": cov_sym_one_lower,
                "cov_upper_asym_one_oos": cov_upper_one,
                "cov_upper_sym_two_oos": cov_sym_one_upper,
                "asset_buffer_delta_pct": (q_low_one - b_sym_two) / b_sym_two if b_sym_two > 0 else float("nan"),
                "liability_buffer_delta_pct": (q_high_one - b_sym_two) / b_sym_two if b_sym_two > 0 else float("nan"),
            })
    one_sided = pd.DataFrame(one_sided_rows)
    one_sided.to_csv(REPORTS / "tables" / "v1b_w4_asymmetric_one_sided.csv", index=False)
    print("\n=== One-sided lending-consumer view (τ_one ∈ {0.95, 0.99}) ===")
    print(one_sided[[
        "symbol_class", "tau_one_sided", "q_low_one_bps", "q_high_one_bps",
        "b_sym_two_sided_bps", "asset_buffer_delta_pct", "liability_buffer_delta_pct",
    ]].to_string(index=False, float_format=lambda x: f"{x:.4f}"), flush=True)

    # === Pooled width premium ===
    # Average over classes (sample-size-weighted by n_oos) of the asymmetric two-sided width vs symmetric
    pooled_rows = []
    for tau in TARGETS:
        sub = valid[valid["tau"] == tau]
        if sub.empty:
            continue
        # Weight by n_oos
        w = sub["n_oos"].astype(float)
        sym_w = float((sub["sym_total_width_bps"] * w).sum() / w.sum())
        asym_w = float((sub["asym_total_width_bps"] * w).sum() / w.sum())
        pooled_rows.append({
            "tau": tau,
            "pooled_sym_width_bps": sym_w,
            "pooled_asym_width_bps": asym_w,
            "width_delta_pct": (asym_w - sym_w) / sym_w if sym_w > 0 else float("nan"),
            "n_classes_evaluated": int(len(sub)),
        })
    pooled = pd.DataFrame(pooled_rows)
    print("\n=== Pooled (n_oos-weighted) symmetric vs asymmetric width ===")
    print(pooled.to_string(index=False, float_format=lambda x: f"{x:.4f}"), flush=True)

    # === Decision aggregation ===
    # Per (class, τ): material asymmetry if |asym_skew_ratio| > MATERIAL_WIDTH_DELTA_PCT AND p_tail_eq_oos < 0.10
    material = valid.assign(
        material=lambda d: (d["asym_skew_ratio"].abs() > MATERIAL_WIDTH_DELTA_PCT)
                          & (d["p_tail_eq_oos"].fillna(1.0) < 0.10)
    )
    material_count = int(material["material"].sum())
    material_share = material_count / max(len(material), 1)

    # Markdown writeup
    md = _build_markdown(skew_df, valid, one_sided, pooled, material_count, material_share)
    out_md = REPORTS / "v1b_w4_asymmetric_coverage_lending.md"
    out_md.write_text(md)
    print(f"\nwrote {out_md}", flush=True)


def _build_markdown(skew_df, per_cell, one_sided, pooled, material_count, material_share):
    lines = [
        "# V1b — W4: Asymmetric / one-sided coverage on Lending-track",
        "",
        "**Question.** M6b2 (Lending-track) publishes a symmetric `±b_class(τ)` band per "
        "symbol_class. Within each class, is the *signed* residual distribution asymmetric "
        "enough that the symmetric band over-allocates width to one tail and under-allocates "
        "to the other? If yes, the equal-tail asymmetric quantile pair `(q_low(class, τ), "
        "q_high(class, τ))` is the cleaner Lending-track receipt — and one that maps directly "
        "to MarginFi's P-conf / P+conf semantics and band-perp's long/short liquidation "
        "buffers.",
        "",
        "## TRAIN signed-residual diagnostics (per symbol_class)",
        "",
        skew_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        "**Reading.** `fraction_negative` near 0.50 = symmetric around zero; "
        "`p_sign_test_eq_05 < 0.05` rejects symmetric median. `skewness` is the Pearson moment "
        "(positive = right tail heavier; negative = left tail heavier).",
        "",
        "## Per-(class, τ) symmetric vs asymmetric quantiles",
        "",
        per_cell[[
            "symbol_class", "tau", "n_train", "n_oos",
            "b_sym_bps", "q_low_bps", "q_high_bps",
            "sym_total_width_bps", "asym_total_width_bps",
            "width_delta_asym_vs_sym_pct", "asym_skew_ratio",
            "left_viol_rate_sym_oos", "right_viol_rate_sym_oos",
            "p_tail_eq_train", "p_tail_eq_oos",
        ]].to_markdown(index=False, floatfmt=".4f"),
        "",
        "**Reading.**",
        "- `b_sym_bps`: symmetric M6b2 half-width in basis points.",
        "- `q_low_bps`, `q_high_bps`: equal-tail asymmetric magnitudes (both reported positive).",
        "- `asym_skew_ratio = (q_high − q_low) / (q_high + q_low)`. ≈0 = symmetric; positive = right tail wider; negative = left tail wider.",
        "- `width_delta_asym_vs_sym_pct`: total band width (`q_low + q_high`) vs `2·b_sym`. Negative = asymmetric is narrower at matched two-sided coverage.",
        "- `left_viol_rate_sym_oos`, `right_viol_rate_sym_oos`: under the *symmetric* band, the realised left- and right-tail violation rates on OOS. Both should be ≈ (1-τ)/2 if the residual is symmetric.",
        "- `p_tail_eq_oos`: binomial test of left vs right violation rate equality on OOS, conditional on a violation. p < 0.05 rejects symmetry of *tail violation rates*.",
        "",
        "## Pooled (n_oos-weighted) width comparison",
        "",
        pooled.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## One-sided lending-consumer view (the buffer MarginFi / band-perp actually reads)",
        "",
        "MarginFi's asset valuation reads the lower bound; liability valuation reads the upper. "
        "Each consumer wants *one-sided* τ-coverage, not two-sided. The asymmetric one-sided "
        "quantile at τ_one = q_low_one(τ_one) for assets, q_high_one(τ_one) for liabilities. "
        "Below, we compare those to the symmetric two-sided `b_sym(τ_one)` consumers would read "
        "today under symmetric M6b2.",
        "",
        one_sided.to_markdown(index=False, floatfmt=".4f"),
        "",
        "**Reading.** `asset_buffer_delta_pct` = `(q_low_one − b_sym_two) / b_sym_two`. Negative "
        "= asymmetric reduces asset buffer (assets are *less* risky than the symmetric band "
        "suggests on the downside). `liability_buffer_delta_pct` is the analogous comparison for "
        "the upper bound.",
        "",
        "## Decision",
        "",
        f"**Materially-asymmetric cells (|skew_ratio| > 5% AND p_tail_eq_oos < 0.10):** "
        f"{material_count} of {len(per_cell)} cells ({material_share*100:.0f}%).",
        "",
        "Adopt criteria for a Lending-track asymmetric receipt:",
        "",
        "- **Adopt** if ≥ 25% of cells are materially asymmetric AND pooled `width_delta_pct` at "
        "τ=0.95 is ≤ −2% (asymmetric meaningfully tighter at matched two-sided coverage). "
        "Implement `M6_REFACTOR.md` Phase A7: extend the M6b2 artefact builder to emit "
        "`LENDING_QUANTILE_LOW` and `LENDING_QUANTILE_HIGH` (24+24 trained scalars), and have "
        "the publisher write `lower = point − q_low·fri_close` and `upper = point + q_high·fri_close`.",
        "- **Disclose-not-deploy** if asymmetry is detectable but small (cells materially asymmetric "
        "but pooled `width_delta_pct` between −2% and 0%). Footnote in Paper 3 §Structural; do not "
        "implement A7. Symmetric M6b2 ships as the canonical Lending-track.",
        "- **Reject** if cells are symmetric (`width_delta_pct` ≥ 0% pooled, low cell-count "
        "rejection rate). Strike A7 from `M6_REFACTOR.md`.",
        "",
        "## Paper 3 narrative cascade (if Adopt)",
        "",
        "If asymmetric ships, Paper 3's MarginFi worked example becomes empirically grounded: "
        "for each xStock symbol_class, publish q_low(class, τ) and q_high(class, τ); MarginFi's "
        "asset Bank reads q_low; liability Bank reads q_high. The Geometric claim sharpens from "
        "'narrow buffer for SPYx, wide for MSTRx' to 'narrow `q_low` for SPYx, wide `q_high` for "
        "MSTRx, with realised one-sided coverage ≥ τ-target on OOS'.",
        "",
        "## Sources & reproducibility",
        "",
        "- Input: `data/processed/v1b_panel.parquet`",
        "- Per-(class, τ) numerics: `reports/tables/v1b_w4_asymmetric_per_class_tau.csv`",
        "- One-sided lending view: `reports/tables/v1b_w4_asymmetric_one_sided.csv`",
        "- Skewness diagnostics: `reports/tables/v1b_w4_skewness_train.csv`",
        "- Reproducible via `scripts/run_asymmetric_coverage.py`",
        "",
        f"Run on {pd.Timestamp.today().date().isoformat()}.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
