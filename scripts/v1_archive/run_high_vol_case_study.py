"""
High-vol case study — Paper 1 §6 honest comparator.

The 2024-08-02 / 2024-08-05 weekend (Yen carry-trade unwind). All 10 panel
symbols are observed; 7 of 10 realised Monday-open moves exceed 500 bps;
panel max is SMCI-class but on tradeable underliers SPY −298 bps, NVDA −734
bps, MSTR −2737 bps, etc. This is the regime where a fixed Pyth+5% buffer
(~500 bps) demonstrably fails and where the regime-aware Oracle widens.

Outputs a Markdown case-study report mirroring the structure of
reports/kamino_xstocks_weekend_20260424.md so the comparison reads as a
direct counterpart to the calm-weekend report.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

from soothsayer.backtest import calibration as cal
from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.oracle import Oracle


CASE_FRI = date(2024, 8, 2)
TARGETS = (0.68, 0.85, 0.95, 0.99)
PYTH_BUFFERS = (0.02, 0.05, 0.10, 0.20)
SPLIT_DATE = date(2023, 1, 1)


def main() -> None:
    panel = pd.read_parquet(DATA_PROCESSED / "v1b_panel.parquet").dropna(
        subset=["fri_close", "mon_open", "regime_pub"])
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date

    week = panel[panel["fri_ts"] == CASE_FRI].sort_values("symbol").reset_index(drop=True)
    if week.empty:
        raise SystemExit(f"No panel rows for {CASE_FRI}")

    # Median VIX from training panel for the VIX-scaled baseline
    panel_train = panel[panel["fri_ts"] < SPLIT_DATE]
    v_median = float(np.median(panel_train["vix_fri_close"].dropna()))

    # Calibrate const-buffer + VIX-scaled at each τ on training (mirrors §A logic)
    rel_dev = (panel_train["mon_open"].astype(float).values
               - panel_train["fri_close"].astype(float).values) / panel_train["fri_close"].astype(float).values
    rel_dev_abs = np.abs(rel_dev)
    train_vix = panel_train["vix_fri_close"].astype(float).values
    rel_dev_scaled = rel_dev_abs / (train_vix / v_median)

    calibrated_b = {tau: float(np.quantile(rel_dev_abs, tau, method="higher")) for tau in TARGETS}
    calibrated_c = {tau: float(np.quantile(rel_dev_scaled, tau, method="higher")) for tau in TARGETS}

    # Oracle on OOS bounds
    bounds = pd.read_parquet(DATA_PROCESSED / "v1b_bounds.parquet")
    bounds["fri_ts"] = pd.to_datetime(bounds["fri_ts"]).dt.date
    bounds_train = bounds[bounds["fri_ts"] < SPLIT_DATE]
    bounds_case = bounds[bounds["fri_ts"] == CASE_FRI]
    surface = cal.compute_calibration_surface(bounds_train)
    surface_pooled = cal.pooled_surface(bounds_train)
    oracle = Oracle(bounds=bounds_case, surface=surface, surface_pooled=surface_pooled)

    rows = []
    vix_at_t = float(week["vix_fri_close"].iloc[0])

    for _, w in week.iterrows():
        sym = w["symbol"]
        fri = float(w["fri_close"])
        mon = float(w["mon_open"])
        realised_bps = (mon - fri) / fri * 1e4
        regime = str(w["regime_pub"])

        per_sym = {
            "symbol": sym,
            "regime": regime,
            "fri_close": fri,
            "mon_open": mon,
            "realised_bps": realised_bps,
        }

        # Fixed Pyth+b
        for b in PYTH_BUFFERS:
            lo, hi = fri * (1 - b), fri * (1 + b)
            per_sym[f"pyth_{int(b*100)}_lo"] = lo
            per_sym[f"pyth_{int(b*100)}_hi"] = hi
            per_sym[f"pyth_{int(b*100)}_in"] = int(lo <= mon <= hi)
            per_sym[f"pyth_{int(b*100)}_hw_bps"] = b * 1e4

        # VIX-scaled at each τ
        for tau in TARGETS:
            c = calibrated_c[tau]
            b = c * (vix_at_t / v_median)
            lo, hi = fri * (1 - b), fri * (1 + b)
            per_sym[f"vix_{int(tau*100)}_lo"] = lo
            per_sym[f"vix_{int(tau*100)}_hi"] = hi
            per_sym[f"vix_{int(tau*100)}_in"] = int(lo <= mon <= hi)
            per_sym[f"vix_{int(tau*100)}_hw_bps"] = b * 1e4

        # Empirical const-buffer at each τ
        for tau in TARGETS:
            b = calibrated_b[tau]
            lo, hi = fri * (1 - b), fri * (1 + b)
            per_sym[f"const_{int(tau*100)}_lo"] = lo
            per_sym[f"const_{int(tau*100)}_hi"] = hi
            per_sym[f"const_{int(tau*100)}_in"] = int(lo <= mon <= hi)
            per_sym[f"const_{int(tau*100)}_hw_bps"] = b * 1e4

        # Deployed Oracle at each τ
        for tau in TARGETS:
            try:
                pp = oracle.fair_value(sym, CASE_FRI, target_coverage=tau)
                per_sym[f"oracle_{int(tau*100)}_lo"] = float(pp.lower)
                per_sym[f"oracle_{int(tau*100)}_hi"] = float(pp.upper)
                per_sym[f"oracle_{int(tau*100)}_in"] = int(pp.lower <= mon <= pp.upper)
                per_sym[f"oracle_{int(tau*100)}_hw_bps"] = float(pp.half_width_bps)
            except Exception as exc:
                per_sym[f"oracle_{int(tau*100)}_lo"] = None
                per_sym[f"oracle_{int(tau*100)}_hi"] = None
                per_sym[f"oracle_{int(tau*100)}_in"] = None
                per_sym[f"oracle_{int(tau*100)}_hw_bps"] = None
                per_sym[f"oracle_{int(tau*100)}_err"] = str(exc)

        rows.append(per_sym)

    df = pd.DataFrame(rows)
    out_csv = REPORTS / "tables" / "case_study_high_vol_2024_08_02.csv"
    df.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv}")

    # ---- Build markdown ----
    methods = (
        [(f"Pyth+{int(b*100)}%", f"pyth_{int(b*100)}") for b in PYTH_BUFFERS]
        + [(f"VIX-scaled τ={tau:.2f}", f"vix_{int(tau*100)}") for tau in TARGETS]
        + [(f"Const-buffer τ={tau:.2f}", f"const_{int(tau*100)}") for tau in TARGETS]
        + [(f"Soothsayer τ={tau:.2f}", f"oracle_{int(tau*100)}") for tau in TARGETS]
    )

    md_lines: list[str] = []
    md_lines.append(f"# High-vol case study — weekend {CASE_FRI} → {df.iloc[0].get('mon_open') and (CASE_FRI.replace(day=CASE_FRI.day))}".rstrip())
    md_lines[-1] = f"# High-vol case study — weekend {CASE_FRI} (Friday close) → {(CASE_FRI.toordinal()+3)} Monday open"
    md_lines[-1] = f"# High-vol case study — Yen carry unwind weekend ({CASE_FRI} → 2024-08-05)"
    md_lines.append(f"*Generated {datetime.utcnow().isoformat(timespec='seconds')}Z; OOS panel slice (post-2023, surface frozen on pre-2023).* ")
    md_lines.append("")
    md_lines.append(
        "Counterpart to `kamino_xstocks_weekend_20260424.md`: that report covered a "
        "calm-regime weekend where every coverage method except Pyth-conf-only carried the band. "
        "This report covers the high-vol regime where fixed Pyth+constant baselines start to fail. "
        f"VIX(Fri close) = {vix_at_t:.2f} vs training median {v_median:.2f} (×{vix_at_t/v_median:.2f}); "
        f"regime classification = `{week['regime_pub'].mode().iat[0]}`. "
        "All bands below: lower/upper in price units; ✓/✗ on whether Monday open landed inside; "
        "half-width (hw) in basis points relative to Friday close."
    )
    md_lines.append("")

    md_lines.append("## Section 1 — Realised moves and panel context")
    md_lines.append("")
    md_lines.append("| Symbol | Regime | Fri close | Mon open | Realised (bps) |")
    md_lines.append("|---|---|---:|---:|---:|")
    for _, r in df.iterrows():
        md_lines.append(
            f"| **{r['symbol']}** | {r['regime']} | "
            f"${r['fri_close']:,.2f} | ${r['mon_open']:,.2f} | "
            f"{r['realised_bps']:+.1f} |"
        )
    md_lines.append("")
    md_lines.append(
        f"Aggregate: max |Mon−Fri|/Fri = {df['realised_bps'].abs().max():.0f} bps; "
        f"mean |move| = {df['realised_bps'].abs().mean():.0f} bps; "
        f"{int((df['realised_bps'].abs() > 500).sum())} of {len(df)} symbols breach the 500-bps threshold "
        "(i.e., a fixed Pyth+5% band would not have covered)."
    )
    md_lines.append("")

    md_lines.append("## Section 2 — Coverage by method")
    md_lines.append("")
    header = "| Symbol | Realised (bps) | " + " | ".join(name for name, _ in methods) + " |"
    sep = "|---|---:|" + "|".join(["---"] * len(methods)) + "|"
    md_lines.append(header)
    md_lines.append(sep)
    for _, r in df.iterrows():
        cells = [f"**{r['symbol']}**", f"{r['realised_bps']:+.0f}"]
        for _, key in methods:
            in_flag = r.get(f"{key}_in")
            hw = r.get(f"{key}_hw_bps")
            if in_flag is None or hw is None:
                cells.append("—")
                continue
            mark = "✓" if int(in_flag) == 1 else "✗"
            cells.append(f"{mark} / {hw:.0f} bps")
        md_lines.append("| " + " | ".join(cells) + " |")
    md_lines.append("")

    # Aggregate row
    md_lines.append("**Aggregate coverage on this weekend** (✓ count / total):")
    md_lines.append("")
    md_lines.append("| Method | Covered | Mean half-width (bps) |")
    md_lines.append("|---|---|---:|")
    for name, key in methods:
        in_col = df[f"{key}_in"].dropna()
        hw_col = df[f"{key}_hw_bps"].dropna()
        if in_col.empty:
            md_lines.append(f"| {name} | — | — |")
            continue
        md_lines.append(f"| {name} | {int(in_col.sum())}/{len(in_col)} | {float(hw_col.mean()):.0f} |")
    md_lines.append("")

    md_lines.append("## Section 3 — Reading the result")
    md_lines.append("")
    md_lines.append(
        "- **Pyth+5% (the comparator a thoughtful Kamino risk committee deploys) fails on this weekend** "
        f"({int(df['pyth_5_in'].sum())}/{len(df)} symbols covered, mean half-width 500 bps). "
        "Pyth+10% covers more (its half-width is ~3× soothsayer's typical normal-regime band) but is uniformly wide. "
        "Pyth+20% (~$200 of every $1000 collateral as 'safety buffer') covers more but is so wide it would liquidate few near-LTV borrowers in normal weeks. "
        "On a *calm* weekend (e.g. 2026-04-24, max realised |move| 183 bps), Pyth+5% would have covered 8/8 — a property of that weekend's realised distribution, not of the methodology. The same Pyth+5% covers 3/10 here."
    )
    md_lines.append(
        "- **The calibrated comparators (const-buffer, VIX-scaled) trained on pre-2023 data systematically under-cover** here: "
        "their training-set quantiles do not anticipate post-2023 tail events. This is the same train→OOS distribution shift "
        "that makes them under-cover on the aggregate OOS slice (see `reports/tables/v1b_width_at_coverage_pooled.csv`)."
    )
    md_lines.append(
        "- **The deployed Soothsayer Oracle widens via the regime classifier** "
        "(`high_vol` → F0_stale forecaster + log-log VIX scaling). The widening is real but the magnitude is not enough "
        "to cover this weekend at τ=0.85 or τ=0.95: realised |moves| of 1,000–2,700 bps exceed every band on the panel "
        "except Pyth+10% / +20% on the smallest-realised-move symbols. **Soothsayer's actual high-vol-tail product is τ=0.99, "
        f"which on this weekend covers {int(df.get('oracle_99_in', pd.Series([0]*len(df))).sum())}/{len(df)} "
        "(half-widths of 600–2,000 bps). This is what the consumer-selectable τ interface is for: a Kamino-style "
        "consumer worried about Yen-carry-class moves picks τ=0.99 and pays the width premium during high_vol regimes only.**"
    )
    md_lines.append(
        "- **The honest read of this case study is that no single methodology covers this weekend at τ ≤ 0.95.** "
        "Soothsayer's edge is not 'wider bands than Pyth+5% on the worst weekend' — it is (i) average-weekend Winkler "
        "(see `v1b_width_at_coverage_pooled.csv`) and (ii) calibration-receipt provenance (the consumer can audit which "
        "τ they chose and what the realised rate has been). The hard tail-cover claim sits at τ=0.99, with the "
        "structural-finite-sample caveat disclosed in §9.1."
    )
    md_lines.append("")
    md_lines.append(
        "*One weekend is one observation. The aggregate evidence for width-at-coverage across all "
        "172 OOS weekends is in `reports/tables/v1b_width_at_coverage_pooled.csv`; this case study is "
        "the qualitative counterpart that shows where the differences come from.*"
    )
    md_lines.append("")

    out_md = REPORTS / "paper1_coverage_inversion" / f"case_study_high_vol_{CASE_FRI.isoformat().replace('-','')}.md"
    out_md.write_text("\n".join(md_lines))
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
