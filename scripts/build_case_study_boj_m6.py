"""Recompute the 2024-08-02 -> 2024-08-05 BoJ case-study coverage grid
with the deployed M6 LWC bands (deployment artefact, byte-aligned),
keeping the original v1 case study's hypothetical comparator configs.

Reads only local processed data (data/processed/*). No external APIs.
Band formula mirrors scripts/build_paper1_figures.py::fig9_boj_anatomy:
    hw = c_bump[tau] * regime_quantile_table[regime_pub][tau] * sigma_hat_sym_pre_fri
centred on the factor-adjusted point from the artefact parquet row
(delta_shift_schedule is identically zero in the deployed sidecar).

Writes reports/paper1_coverage_inversion/case_study_boj_m6.md.
Sanity-checks the resulting breach counts against paper section 6.3.5
(k_w = 10 / 9 / 5 at tau = 0.85 / 0.95 / 0.99) and fails if they differ.

Run with: .venv/bin/python -u scripts/build_case_study_boj_m6.py
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/adamnoonan/Documents/soothsayer")
DP = ROOT / "data" / "processed"
TAUS = ("0.68", "0.85", "0.95", "0.99")

# Hypothetical comparator configs carried verbatim from the original
# v1 case study (case_study_high_vol_20240802.md), centred on Friday
# close, symmetric, half-widths in bps.
COMPARATORS = [
    ("Pyth+2%", 200.0), ("Pyth+5%", 500.0),
    ("Pyth+10%", 1000.0), ("Pyth+20%", 2000.0),
    ("VIX-scaled t=0.68", 103.0), ("VIX-scaled t=0.85", 173.0),
    ("VIX-scaled t=0.95", 329.0), ("VIX-scaled t=0.99", 700.0),
    ("Const-buffer t=0.68", 75.0), ("Const-buffer t=0.85", 139.0),
    ("Const-buffer t=0.95", 272.0), ("Const-buffer t=0.99", 694.0),
]

def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

art_pq = DP / "lwc_artefact_v1.parquet"
art_js = DP / "lwc_artefact_v1.json"
panel_pq = DP / "v1b_panel.parquet"

art = pd.read_parquet(art_pq)
art = art[pd.to_datetime(art["fri_ts"]).dt.date.astype(str) == "2024-08-02"]
assert len(art) == 10, f"expected 10 artefact rows, got {len(art)}"

side = json.loads(art_js.read_text())
qt, cb, delta = (side["regime_quantile_table"], side["c_bump_schedule"],
                 side["delta_shift_schedule"])
assert all(float(v) == 0.0 for v in delta.values()), "delta shift not zero"

panel = pd.read_parquet(panel_pq)
panel["fri_ts_d"] = pd.to_datetime(panel["fri_ts"]).dt.date.astype(str)
mon = (panel[panel["fri_ts_d"] == "2024-08-02"]
       .set_index("symbol")["mon_open"])

rows = []
for _, r in art.iterrows():
    sym = r["symbol"]
    fri = float(r["fri_close"])
    mo = float(mon[sym])
    realised_bps = (mo / fri - 1.0) * 1e4
    point_bps = (float(r["point"]) / fri - 1.0) * 1e4
    entry = {"symbol": sym, "regime": r["regime_pub"], "fri_close": fri,
             "mon_open": mo, "realised_bps": realised_bps}
    # comparators: centred on Friday close
    for name, hw in COMPARATORS:
        entry[name] = (abs(realised_bps) <= hw, hw)
    # M6: centred on factor-adjusted point
    for tau in TAUS:
        hw_bps = (float(cb[tau]) * float(qt[r["regime_pub"]][tau])
                  * float(r["sigma_hat_sym_pre_fri"]) * 1e4)
        cov = (point_bps - hw_bps) <= realised_bps <= (point_bps + hw_bps)
        entry[f"M6 t={tau}"] = (cov, hw_bps)
    rows.append(entry)

df = pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)

def mark(t):
    cov, hw = t
    return f"{'Y' if cov else 'N'} / {hw:.0f} bps"

method_cols = [n for n, _ in COMPARATORS] + [f"M6 t={t}" for t in TAUS]

# ---- emit markdown ----
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
lines = []
lines.append("# High-vol case study, M6 recompute — Yen carry unwind weekend (2024-08-02 → 2024-08-05)")
lines.append("")
lines.append(f"*Generated {now} by `scripts/build_case_study_boj_m6.py` (band logic mirrors "
             "`scripts/build_paper1_figures.py::fig9_boj_anatomy` / paper §6.3.5). "
             "M6-current counterpart to `case_study_high_vol_20240802.md`, whose "
             "\"Soothsayer\" columns describe the retired v1 surface; that file is "
             "preserved unmodified as a historical record.*")
lines.append("")
lines.append("## Provenance")
lines.append("")
lines.append("| Input | Path | SHA-256 |")
lines.append("|---|---|---|")
for p in (art_pq, art_js, panel_pq):
    lines.append(f"| {p.name} | `{p.relative_to(ROOT)}` | `{sha256(p)}` |")
lines.append("")
lines.append(f"- Deployment artefact: methodology `{side['methodology_version']}`, "
             f"variant `{side['_lwc_variant']}`, `_fetched_at` = `{side['_fetched_at']}`, "
             f"source `{side['_source']}`, split date {side['split_date']}.")
lines.append("- M6 served band per (symbol, τ): half-width = "
             "`c_bump[τ] × regime_quantile_table[regime_pub][τ] × σ̂_sym_pre_fri`, "
             "centred on the factor-adjusted point `point` from the per-Friday artefact row "
             "(`delta_shift_schedule` is identically 0 at all τ in the deployed sidecar). "
             "σ̂ is EWMA HL=8. Bands are read from the deployment artefact, not refit — "
             "byte-aligned with what a consumer read on 2024-08-02.")
lines.append("- The 2024-08-02 row sits in the OOS slice (post-2023; schedules fitted on pre-2023 train only).")
lines.append("- Comparator configs are **hypothetical consumer configurations**, carried verbatim "
             "from `case_study_high_vol_20240802.md` for comparability. They are not incumbent "
             "products: Pyth+k% wraps a Pyth-style point price in a fixed symmetric k% buffer; "
             "\"VIX-scaled\" and \"Const-buffer\" are the paper's v1-era calibrated baselines "
             "(pre-2023 train), centred on Friday close. Coverage = Monday 09:30 ET open inside the band.")
lines.append("- The original case study's \"Soothsayer\" columns describe the retired v1 surface "
             "(F0_stale forecaster + log-log VIX scaling) and are superseded by the M6 columns here. "
             "The original file is preserved unmodified.")
lines.append("")
lines.append("## Section 1 — Realised moves and panel context")
lines.append("")
lines.append("Market facts, unchanged from the original case study. Regime classification "
             "for 2024-08-02 = `high_vol` for all 10 symbols (artefact `regime_pub`).")
lines.append("")
lines.append("| Symbol | Regime | Fri close | Mon open | Realised (bps) |")
lines.append("|---|---|---:|---:|---:|")
for _, r in df.iterrows():
    lines.append(f"| **{r['symbol']}** | {r['regime']} | ${r['fri_close']:.2f} "
                 f"| ${r['mon_open']:.2f} | {r['realised_bps']:+.1f} |")
agg_abs = df["realised_bps"].abs()
n500 = int((agg_abs > 500).sum())
lines.append("")
lines.append(f"Aggregate: max |Mon−Fri|/Fri = {agg_abs.max():.0f} bps; mean |move| = "
             f"{agg_abs.mean():.0f} bps; {n500} of 10 symbols exceed 500 bps.")
lines.append("")
lines.append("## Section 2 — Coverage by method (M6 deployed bands)")
lines.append("")
hdr = "| Symbol | Realised (bps) | " + " | ".join(
    c.replace("t=", "τ=") for c in method_cols) + " |"
lines.append(hdr)
lines.append("|---|---:|" + "---|" * len(method_cols))
for _, r in df.iterrows():
    cells = " | ".join(mark(r[c]).replace("Y /", "✓ /").replace("N /", "✗ /")
                       for c in method_cols)
    lines.append(f"| **{r['symbol']}** | {r['realised_bps']:+.0f} | {cells} |")
lines.append("")
lines.append("**Aggregate coverage on this weekend** (✓ count / total):")
lines.append("")
lines.append("| Method | Covered | Mean half-width (bps) |")
lines.append("|---|---|---:|")
for c in method_cols:
    covs = df[c].apply(lambda t: t[0])
    hws = df[c].apply(lambda t: t[1])
    lines.append(f"| {c.replace('t=', 'τ=')} | {int(covs.sum())}/10 | {hws.mean():.0f} |")
lines.append("")

# ---- Section 3: reading (lab-report register; numbers above are the record) ----
lines.append("## Section 3 — Reading the result")
lines.append("")
lines.append("- **M6 at τ = 0.68 and τ = 0.85 covers 0/10.** All ten symbols breach the "
             "τ = 0.85 band simultaneously; this weekend is the single k_w = 10 event at "
             "τ = 0.85 in the OOS record (paper §6.3.4–§6.3.5).")
lines.append("- **M6 at τ = 0.95 covers 1/10** (TLT only; k_w = 9, the OOS maximum at that "
             "anchor). The σ̂ standardisation works at the per-symbol level — MSTR's "
             "τ = 0.85 half-width (663 bps) is ≈ 8× SPY's (85 bps) — but nine symbols "
             "moving the same direction by 4–27 σ̂-scale weekend returns is a "
             "cross-sectional common-mode event that no per-symbol band absorbs. "
             "The §6.3.4 joint-breach distribution (k* = 3 reserve-guidance threshold at "
             "τ = 0.95) is the operational handle for this event class.")
lines.append("- **M6 at τ = 0.99 covers 5/10** (GLD, GOOGL, MSTR, TLT, TSLA; mean "
             "half-width 896 bps). Coverage at this anchor comes from per-symbol width "
             "differentiation plus the factor-adjusted centre: MSTR's served band is "
             "2,208 bps wide and centred −538 bps below Friday close, so its −2,737 bps "
             "realised move lands inside; SPY's 283 bps band does not reach its "
             "−399 bps move.")
lines.append("- **Fixed-buffer comparators:** Pyth+5% covers 3/10; Pyth+10% covers 6/10 "
             "and Pyth+20% covers 9/10, at uniform 1,000 / 2,000 bps half-widths on every "
             "symbol in every week regardless of regime. The v1-era calibrated comparators "
             "(VIX-scaled, const-buffer; pre-2023 train) cover at most 2/10 at τ ≤ 0.95 "
             "and 5/10 at τ = 0.99.")
lines.append("- **No method on this grid attains its nominal coverage at τ ≤ 0.95 on this "
             "weekend.** The best τ ≤ 0.95 cell is 2/10. The tail-coverage story on this "
             "event sits at τ = 0.99, where M6 matches the best comparator count (5/10) "
             "with regime- and symbol-conditional widths rather than a flat buffer.")
lines.append("")
lines.append("**Change vs the retired v1 columns** (`case_study_high_vol_20240802.md`, "
             "generated 2026-05-03 against F0_stale + log-log VIX scaling):")
lines.append("")
lines.append("| Anchor | v1 covered | v1 mean hw (bps) | M6 covered | M6 mean hw (bps) |")
lines.append("|---|---|---:|---|---:|")
V1_ROWS = {"0.68": (0, 189), "0.85": (0, 298), "0.95": (2, 584), "0.99": (3, 761)}
for tau in TAUS:
    col = f"M6 t={tau}"
    m6_cov = int(df[col].apply(lambda t: t[0]).sum())
    m6_hw = df[col].apply(lambda t: t[1]).mean()
    v1_cov, v1_hw = V1_ROWS[tau]
    lines.append(f"| τ={tau} | {v1_cov}/10 | {v1_hw} | {m6_cov}/10 | {m6_hw:.0f} |")
lines.append("")
lines.append("M6 serves narrower bands at τ ≤ 0.95 (and loses GLD at τ = 0.95 relative to "
             "v1) and wider, better-targeted bands at τ = 0.99 (adding GOOGL and MSTR). "
             "The v1 rows are superseded; they are retained in the original file as a "
             "historical record only.")
lines.append("")
lines.append("*One weekend is one observation. The aggregate OOS calibration evidence for "
             "the deployed M6 architecture is in paper §6.3–§6.4 (pooled and per-symbol "
             "Kupiec, joint-tail k_w distribution: "
             "`reports/tables/paper1_a3_joint_baseline_kw_distribution.csv`, "
             "`reports/tables/m6_kw_threshold_stability.csv`); this case study is the "
             "qualitative counterpart on the worst observed weekend.*")
lines.append("")

out = "\n".join(lines)
out_path = ROOT / "reports" / "paper1_coverage_inversion" / "case_study_boj_m6.md"

# sanity vs §6.3.5: expected k_w breaches 10/9/5 at 0.85/0.95/0.99
mismatch = False
for tau, exp_k in (("0.85", 10), ("0.95", 9), ("0.99", 5)):
    k = int((~df[f"M6 t={tau}"].apply(lambda t: t[0])).sum())
    status = "OK" if k == exp_k else "MISMATCH"
    mismatch |= k != exp_k
    print(f"sanity k_w @ τ={tau}: {k} (expected {exp_k}) {status}")
if mismatch:
    raise SystemExit("k_w sanity check vs §6.3.5 failed — not writing report")

out_path.write_text(out)
print(f"wrote {out_path}")
