"""Render the weekly Kamino-xStocks comparator report from
``data/processed/weekend_comparison_YYYYMMDD.json``.

Phase 1 Week 3 / Step 4. Produces two outputs from one scored weekend:

- ``reports/kamino_xstocks_weekend_YYYYMMDD.md`` — public markdown report
- ``landing/kamino_xstocks_weekend_fragment.html`` — drop-in HTML section
  for the landing page (overwritten each week)

Structure follows the spec's three sections:

  Section 1 — What was observed
    Per (symbol, weekend): Kamino reserve config snapshot, oracle path,
    Friday close, observed weekend tape range, Monday open.

  Section 2 — Who covered the realized move
    Compact coverage + half-width table across the four methods.
    Kamino's PriceHeuristic is reported as a validity guard rail, NOT a
    coverage band — it is included in Section 1 as a recorded incumbent
    parameter rather than scored alongside Soothsayer.

  Section 3 — Lending consequence under real reserve params
    Decision classification at near-origination and near-liquidation
    borrower states for each method's lower bound, evaluated against the
    actually-deployed (loan_to_value_pct, liquidation_threshold_pct).

Run:
    uv run python scripts/render_weekend_report.py                          # latest
    uv run python scripts/render_weekend_report.py --friday 2026-04-17
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from soothsayer.config import DATA_PROCESSED, REPO_ROOT


REPORTS_DIR = REPO_ROOT / "reports"
LANDING_DIR = REPO_ROOT / "landing"


def latest_weekend_json() -> Path:
    candidates = sorted(DATA_PROCESSED.glob("weekend_comparison_*.json"))
    if not candidates:
        raise SystemExit(
            "No weekend_comparison JSON found under data/processed/. "
            "Run scripts/score_weekend_comparison.py first."
        )
    return candidates[-1]


def fmt_cov(b: dict) -> str:
    """Coverage cell — None means 'not applicable'."""
    if b.get("coverage") is True:
        return "✓ in"
    if b.get("coverage") is False:
        return "✗ out"
    return "n/a"


def fmt_band(b: dict) -> str:
    return f"[\\${b['lower']:.2f}, \\${b['upper']:.2f}]"


def fmt_hw(b: dict) -> str:
    hw = b.get("half_width_bps")
    return f"{hw:.1f}" if hw is not None else "n/a"


def fmt_excess(b: dict) -> str:
    ex = b.get("excess_width_bps")
    if ex is None:
        return "n/a"
    sign = "+" if ex >= 0 else ""
    return f"{sign}{ex:.1f}"


def render_markdown(data: dict) -> str:
    rows = data["rows"]
    n = len(rows)

    md: list[str] = []
    md.append(f"# Kamino xStocks — weekend comparator: {data['friday']} → {data['monday']}\n")
    md.append(
        f"*Generated {data['scored_at']}; reserve config snapshot from {data['snapshot_used']}.*\n"
    )
    md.append(
        "Forward-running comparator that scores Soothsayer bands and free-data baselines "
        "against the realized Monday open under Kamino's actually-deployed xStock reserve "
        "parameters. All 8 xStocks live in lending market "
        f"`{rows[0]['lending_market']}` and consume Scope as the primary oracle. The numbers "
        "below are reproducible from the on-chain klend program (`KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD`) "
        "via `scripts/snapshot_kamino_xstocks.py` + `scripts/score_weekend_comparison.py`.\n"
    )

    # --- Section 1: What was observed ---------------------------------
    md.append("## Section 1 — What was observed\n")
    md.append(
        "Per-symbol Friday close (yfinance underlier), Monday open (yfinance underlier), "
        "Kamino reserve config (LTV at origination / liquidation threshold / heuristic guard "
        "rail), and weekend tape coverage. Kamino's `PriceHeuristic` is a *validity guard rail* "
        "— Scope reads outside the range are rejected — not a coverage band, so it is reported "
        "here as a recorded incumbent parameter rather than scored against the realized move.\n"
    )
    md.append(
        "| Symbol | Reserve PDA | LTV / liq | Gap (pp) | Heuristic guard rail | "
        "Fri close | Mon open | Realized (bps) | V5 tape obs | Scope tape obs |\n"
    )
    md.append(
        "|---|---|---|---:|---|---:|---:|---:|---:|---:|\n"
    )
    for r in rows:
        rc = r["reserve_config"]
        kb = r["bands"]["kamino_incumbent"]
        guard = f"\\[\\${kb['lower']:.0f}, \\${kb['upper']:.0f}\\]"
        md.append(
            f"| **{r['symbol']}** | `{r['reserve_pda'][:8]}…` | "
            f"{rc['loan_to_value_pct']} / {rc['liquidation_threshold_pct']} | "
            f"{rc['liquidation_threshold_pct'] - rc['loan_to_value_pct']} | "
            f"{guard} | "
            f"\\${r['fri_close']:.2f} | \\${r['mon_open']:.2f} | "
            f"{r['realized_gap_bps']:+.1f} | "
            f"{r['v5_tape_n_obs']} | {r['scope_tape_n_obs']} |\n"
        )
    md.append("\n")

    # --- Section 2: Coverage of realized move -------------------------
    md.append("## Section 2 — Who covered the realized move\n")
    md.append(
        "Coverage and half-width comparison across the three methods that publish a "
        "coverage band: Soothsayer at τ=0.85 (deployment default), Soothsayer at τ=0.95 "
        "(stricter oracle-validation comparator), and a simple free-data heuristic "
        "(`Friday close ± max(|Chainlink tokenizedPrice − Friday close|)` over the V5 tape). "
        "Excess width is half-width minus the realized absolute move; positive values "
        "indicate over-protection, negative values indicate the band missed the move.\n"
    )
    md.append(
        "| Symbol | Realized (bps) | "
        "Soothsayer τ=0.85 cov / hw / excess | "
        "Soothsayer τ=0.95 cov / hw / excess | "
        "Simple heuristic cov / hw / excess |\n"
    )
    md.append("|---|---:|---|---|---|\n")
    for r in rows:
        b85 = r["bands"]["soothsayer_t085"]
        b95 = r["bands"]["soothsayer_t095"]
        bh = r["bands"]["simple_heuristic"]
        md.append(
            f"| **{r['symbol']}** | {r['realized_gap_bps']:+.1f} | "
            f"{fmt_cov(b85)} / {fmt_hw(b85)} / {fmt_excess(b85)} | "
            f"{fmt_cov(b95)} / {fmt_hw(b95)} / {fmt_excess(b95)} | "
            f"{fmt_cov(bh)} / {fmt_hw(bh)} / {fmt_excess(bh)} |\n"
        )

    # Aggregate coverage rates.
    cov_85 = [b["bands"]["soothsayer_t085"]["coverage"] for b in rows]
    cov_95 = [b["bands"]["soothsayer_t095"]["coverage"] for b in rows]
    cov_h = [b["bands"]["simple_heuristic"]["coverage"] for b in rows]

    def rate(arr: list) -> str:
        valid = [v for v in arr if v is not None]
        if not valid:
            return "n/a"
        return f"{sum(valid)}/{len(valid)}"
    md.append(
        f"\n**Aggregate coverage on this weekend** "
        f"(method ✓ / total scorable rows): "
        f"Soothsayer τ=0.85 = {rate(cov_85)}; "
        f"Soothsayer τ=0.95 = {rate(cov_95)}; "
        f"simple heuristic = {rate(cov_h)}.\n"
    )
    md.append(
        "*One weekend is a tiny sample by design — this report is a forward-running tape; "
        "the cross-week aggregate becomes the meaningful comparison after several weekends.*\n"
    )

    # --- Section 3: Lending consequence under real reserve params -----
    md.append("\n## Section 3 — Lending consequence under real reserve params\n")
    md.append(
        "For each method's lower bound, what does the same reserve config classify a "
        "near-origination borrower (debt sized to LTV = max-LTV − 0.5pp) and a "
        "near-liquidation borrower (debt sized to LTV = liquidation threshold − 0.05pp) as on "
        "Monday? `Kamino-incumbent` uses the Scope-served Monday-open price (or Friday close as "
        "fallback when Scope tape is absent for past weekends) — this is the *actually-deployed* "
        "incumbent decision rule, not a reconstruction. Soothsayer rows use the band's lower bound "
        "as the conservative collateral price.\n"
    )
    md.append(
        "| Symbol | LTV / liq / gap | Method | Near-origination | Near-liquidation | Effective LTV (orig / liq) |\n"
    )
    md.append("|---|---|---|---|---|---|\n")
    for r in rows:
        rc = r["reserve_config"]
        gap_label = (f"{rc['loan_to_value_pct']} / {rc['liquidation_threshold_pct']} "
                     f"/ {rc['liquidation_threshold_pct']-rc['loan_to_value_pct']}pp")
        for method, dec in r["decisions"].items():
            ltv_o = dec.get("ltv_origin_under_method")
            ltv_l = dec.get("ltv_liq_under_method")
            ltv_label = f"{ltv_o:.3f} / {ltv_l:.3f}" if ltv_o is not None else "n/a"
            md.append(
                f"| **{r['symbol']}** | {gap_label} | `{method}` | "
                f"{dec.get('near_origination','n/a')} | {dec.get('near_liquidation','n/a')} | "
                f"{ltv_label} |\n"
            )

    # --- Decision divergence summary ---------------------------------
    md.append("\n### Decision divergence summary\n")
    md.append(
        "Cases where Soothsayer (τ=0.85) and Kamino-incumbent reach a *different* classification "
        "for the near-liquidation borrower. These are the cells the pitch deck is interested in:\n\n"
    )
    md.append("| Symbol | Realized (bps) | Kamino near-liq | Soothsayer τ=0.85 near-liq | Direction |\n")
    md.append("|---|---:|---|---|---|\n")
    n_diverge = 0
    for r in rows:
        ki = r["decisions"]["kamino_incumbent"]["near_liquidation"]
        sb = r["decisions"]["soothsayer_t085"]["near_liquidation"]
        if ki == sb:
            continue
        n_diverge += 1
        # Direction: was Soothsayer more or less conservative?
        order = {"Safe": 0, "Caution": 1, "Liquidate": 2}
        if order.get(sb, 0) > order.get(ki, 0):
            direction = "Soothsayer more conservative"
        else:
            direction = "Soothsayer less conservative"
        md.append(f"| **{r['symbol']}** | {r['realized_gap_bps']:+.1f} | {ki} | {sb} | {direction} |\n")
    if n_diverge == 0:
        md.append("| *(no divergences this weekend)* | | | | |\n")
    md.append(
        f"\n**Decision divergence count this weekend: {n_diverge} of {n} symbols** "
        f"on the near-liquidation borrower.\n"
    )

    # --- Honest framing ----------------------------------------------
    md.append("\n## Honest framing\n")
    md.append(
        "- The Kamino-incumbent row uses the actually-deployed Scope oracle path; it is not a "
        "reconstruction or proxy.\n"
        "- The Soothsayer rows are the deployed methodology serving at consumer τ; they are not "
        "tuned to this weekend.\n"
        "- The simple heuristic exists to prevent the comparison from looking like 'Soothsayer "
        "vs one arbitrary number'. It is intentionally weak and is expected to be the worst of "
        "the three coverage methods most weeks.\n"
        "- Coverage on a single weekend is too small a sample to support a welfare claim. "
        "The quantity that matters across weeks is the *false-liquidation rate* and "
        "*missed-risk rate* under the same reserve parameters — that aggregation is in scope "
        "for Paper 3 (`reports/paper3_liquidation_policy/plan.md`) once enough forward weekends "
        "have accumulated.\n"
    )

    return "".join(md)


def render_html(data: dict) -> str:
    rows = data["rows"]
    n = len(rows)
    n_diverge = sum(
        1 for r in rows
        if r["decisions"]["kamino_incumbent"]["near_liquidation"]
        != r["decisions"]["soothsayer_t085"]["near_liquidation"]
    )
    cov_85 = [b["bands"]["soothsayer_t085"]["coverage"] for b in rows]
    cov_95 = [b["bands"]["soothsayer_t095"]["coverage"] for b in rows]
    rate = lambda arr: f"{sum(v for v in arr if v is not None)}/{sum(1 for v in arr if v is not None)}"

    html: list[str] = []
    html.append('<!-- Generated by scripts/render_weekend_report.py. Drop this fragment into landing/index.html. -->\n')
    html.append('<section class="kamino-weekend">\n')
    html.append(f'  <h2>Kamino xStocks — weekend comparator: {data["friday"]} → {data["monday"]}</h2>\n')
    html.append(
        f'  <p class="kamino-weekend__caption">'
        f'Forward-running comparator that scores Soothsayer bands against the realized Monday open '
        f'under Kamino\'s actually-deployed xStock reserve parameters. All 8 xStocks live in one '
        f'lending market and consume Scope as primary oracle. Reserve config snapshot from '
        f'{data["snapshot_used"]}. Reproducible from the on-chain klend program.'
        f'</p>\n'
    )
    html.append('  <table class="kamino-weekend__table"><thead><tr>')
    for h in ["Symbol", "LTV/liq", "Fri close", "Mon open", "Realized (bps)",
              "Soothsayer τ=0.85 cov / hw bps", "Soothsayer τ=0.95 cov / hw bps",
              "Kamino near-liq", "Soothsayer τ=0.85 near-liq"]:
        html.append(f'<th>{h}</th>')
    html.append('</tr></thead>\n    <tbody>\n')
    for r in rows:
        rc = r["reserve_config"]
        b85 = r["bands"]["soothsayer_t085"]
        b95 = r["bands"]["soothsayer_t095"]
        ki = r["decisions"]["kamino_incumbent"]["near_liquidation"]
        sb = r["decisions"]["soothsayer_t085"]["near_liquidation"]
        diverge_class = " class=\"kamino-weekend__diverge\"" if ki != sb else ""
        html.append(
            f'      <tr{diverge_class}>'
            f'<td><strong>{r["symbol"]}</strong></td>'
            f'<td>{rc["loan_to_value_pct"]}/{rc["liquidation_threshold_pct"]}</td>'
            f'<td>${r["fri_close"]:.2f}</td>'
            f'<td>${r["mon_open"]:.2f}</td>'
            f'<td>{r["realized_gap_bps"]:+.1f}</td>'
            f'<td>{fmt_cov(b85)} / {fmt_hw(b85)}</td>'
            f'<td>{fmt_cov(b95)} / {fmt_hw(b95)}</td>'
            f'<td>{ki}</td>'
            f'<td>{sb}</td>'
            f'</tr>\n'
        )
    html.append('    </tbody></table>\n')
    html.append(
        f'  <p class="kamino-weekend__summary">'
        f'<strong>{n_diverge} of {n} xStocks</strong> reach a different near-liquidation '
        f'classification under Soothsayer τ=0.85 vs Kamino-incumbent on this weekend. '
        f'Coverage rates: Soothsayer τ=0.85 = {rate(cov_85)}, '
        f'Soothsayer τ=0.95 = {rate(cov_95)}. One weekend is a small sample; '
        f'the meaningful aggregate emerges across multiple weekends.'
        f'</p>\n'
    )
    html.append('</section>\n')
    return "".join(html)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--friday", type=str, default=None,
                    help="Friday date of the weekend to render (YYYY-MM-DD)")
    args = ap.parse_args()

    if args.friday:
        target = DATA_PROCESSED / f"weekend_comparison_{args.friday.replace('-','')}.json"
        if not target.exists():
            raise SystemExit(f"No JSON for friday {args.friday} at {target}")
    else:
        target = latest_weekend_json()

    data = json.loads(target.read_text())
    print(f"Rendering {target.name} ({data['n_symbols']} symbols, {data['friday']} → {data['monday']})")

    md = render_markdown(data)
    html = render_html(data)

    friday_ymd = data["friday"].replace("-", "")
    md_path = REPORTS_DIR / f"kamino_xstocks_weekend_{friday_ymd}.md"
    html_path = LANDING_DIR / "kamino_xstocks_weekend_fragment.html"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)
    html_path.write_text(html)
    print(f"Wrote {md_path}")
    print(f"Wrote {html_path}")


if __name__ == "__main__":
    main()
