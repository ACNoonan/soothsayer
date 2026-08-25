"""Rebuild the weekend and overnight calibration panels on the extended window.

Why this exists. The panels the paper cites end 2026-04-24 (weekend) and
2026-04-25 (overnight), and their `earnings_night` cells were built on
`earnings.v2` — which went dark for confirmed sessions after 2025-05-28 and
duplicates every Finnhub date revision. Both are repaired: earnings now come
from `earnings.v3` via `load_earnings_v3`, and the daily bars run to
2026-08-24.

**This script never overwrites paper evidence.** `v1b_panel.parquet` and
`overnight_panel.parquet` are the artefacts §6 was computed from and stay
byte-identical; the rebuild lands beside them under an `_ext_{cutoff}` name.

It also runs the regression that matters: over the ORIGINAL window the
rebuilt panel must match the old one everywhere except `earnings_next_week`,
whose only permitted moves are False→True on nights EDGAR newly confirmed. A
row that changes any other column means the rebuild moved something it had no
business moving, and the script says so rather than writing.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

import pandas as pd

from soothsayer.backtest import panel as panel_mod
from soothsayer.backtest import regimes
from soothsayer.backtest.calibration import add_sigma_hat_sym_ewma, SIGMA_HAT_MIN
from soothsayer.config import DATA_PROCESSED

# Import the overnight reference builder's own ex-div step rather than
# reimplementing it: the reference `overnight_panel.parquet` has it applied,
# and a rebuild without it differs on every ex-dividend morning.
from build_overnight_panel import _apply_ex_div_adjustment, SIGMA_HL

WEEKEND_REF = DATA_PROCESSED / "v1b_panel.parquet"
OVERNIGHT_REF = DATA_PROCESSED / "overnight_panel.parquet"

WEEKEND_START = date(2012, 1, 1)
OVERNIGHT_START = date(2012, 1, 1)

# Columns that exist only in the reference artefact's post-processing and are
# not produced by a bare build() + regimes.tag(); excluded from the diff.
_DIFF_EXCLUDE = {"earnings_next_week", "earnings_next_week_f"}


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ("fri_ts", "mon_ts"):
        if c in out.columns:
            out[c] = pd.to_datetime(out[c]).dt.date
    return out


def _regression(new: pd.DataFrame, ref: pd.DataFrame, label: str) -> bool:
    """Compare the rebuilt panel to the reference over the reference window."""
    key = ["symbol", "fri_ts"]
    new_n, ref_n = _norm(new), _norm(ref)
    cutoff = ref_n["fri_ts"].max()
    new_in = new_n[new_n["fri_ts"] <= cutoff]

    merged = ref_n.merge(new_in, on=key, how="outer", suffixes=("_ref", "_new"),
                         indicator=True)
    only_ref = int((merged["_merge"] == "left_only").sum())
    only_new = int((merged["_merge"] == "right_only").sum())
    both = merged[merged["_merge"] == "both"]

    print(f"  [{label}] reference rows      : {len(ref_n):,} (→ {cutoff})")
    print(f"  [{label}] rebuilt rows in win : {len(new_in):,}")
    print(f"  [{label}] rows only in ref    : {only_ref:,}")
    print(f"  [{label}] rows only in rebuild: {only_new:,}")

    shared = [c for c in ref_n.columns
              if c in new_in.columns and c not in key and c not in _DIFF_EXCLUDE]
    moved = []
    for c in shared:
        a, b = both[f"{c}_ref"], both[f"{c}_new"]
        if pd.api.types.is_float_dtype(a) and pd.api.types.is_float_dtype(b):
            diff = ~((a - b).abs() < 1e-9) & ~(a.isna() & b.isna())
        else:
            diff = (a != b) & ~(a.isna() & b.isna())
        n = int(diff.sum())
        if n:
            moved.append((c, n))
    if moved:
        print(f"  [{label}] UNEXPECTED column moves:")
        for c, n in moved:
            print(f"      {c}: {n:,} rows changed")
    else:
        print(f"  [{label}] no non-earnings column moved  ✓")

    if "earnings_next_week" in ref_n.columns and "earnings_next_week" in new_in.columns:
        a = both["earnings_next_week_ref"].fillna(False).astype(bool)
        b = both["earnings_next_week_new"].fillna(False).astype(bool)
        gained, lost = int((~a & b).sum()), int((a & ~b).sum())
        print(f"  [{label}] earnings_next_week False→True: {gained:,}")
        print(f"  [{label}] earnings_next_week True→False: {lost:,}")
    return not moved and only_ref == 0


def _build(gap_mode: str, start: date, end: date, vix_source: str) -> pd.DataFrame:
    """Rebuild one panel through the SAME pipeline its reference used.

    The two differ past `build()`, and getting that wrong is silent: an
    overnight panel tagged in weekend regime mode still has a populated
    `regime_pub` column, just the wrong one — 4,828 rows wrong, when this
    script first ran.
    """
    spec = panel_mod.PanelSpec(
        start=start, end=end, gap_mode=gap_mode, vix_source=vix_source
    )
    p = panel_mod.build(spec)
    if gap_mode == "overnight":
        p = regimes.tag(p, mode="overnight")
        # Reconstruct cum-dividend opens before σ̂, exactly as the reference
        # builder does, so every downstream object sees the adjusted open.
        p = _apply_ex_div_adjustment(p, start, end)
        # σ̂ at overnight cadence, with earnings-night residuals excluded from
        # the EWMA pool. Omitting the mask contaminates σ̂ (+32% GOOGL, +23%
        # NVDA) and over-widens every ordinary night — and fails silently, in
        # the safe-looking direction. See STATUS.md "Load-bearing today".
        p = add_sigma_hat_sym_ewma(
            p, half_life=SIGMA_HL, min_obs=SIGMA_HAT_MIN,
            exclude_mask_col="earnings_next_week",
        )
        p["sigma_hat_sym_pre_fri"] = p[f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HL}"]
    else:
        p = regimes.tag(p)
    p["fri_ts"] = pd.to_datetime(p["fri_ts"]).dt.date
    p["mon_ts"] = pd.to_datetime(p["mon_ts"]).dt.date
    p["_schema_version"] = "soothsayer.panel_ext.v1"
    p["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    p["_source"] = "scripts/rebuild_panels_extended.py"
    p.attrs.clear()  # build() parks a non-serialisable PanelSpec here
    return p.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default="2026-08-24",
                    help="panel end date (YYYY-MM-DD); default is the last session on disk")
    ap.add_argument("--write", action="store_true",
                    help="persist the rebuilt panels; without it this is a dry run")
    ap.add_argument("--vix-source", default=None, choices=("yahoo", "cboe"),
                    help="override the ^VIX feed for BOTH panels. Left unset "
                         "(the default) each panel uses the feed its own "
                         "reference was built with: weekend=yahoo, "
                         "overnight=cboe. Only override for a panel you intend "
                         "to refit on.")
    args = ap.parse_args()
    end = date.fromisoformat(args.end)
    tag = end.strftime("%Y%m%d")

    # The two reference panels were built either side of the CBOE blend
    # (commit 6c479ca, 2026-05-04): v1b_panel.parquet is dated 2026-04-27 and
    # so carries Yahoo VIX, overnight_panel.parquet is dated 2026-06-26 and
    # carries CBOE. Matching each one is what keeps an extension comparable
    # to the artefact fit on it; a single global default cannot do both.
    for label, gap_mode, start, ref_path, vix_default in (
        ("weekend", "weekend", WEEKEND_START, WEEKEND_REF, "yahoo"),
        ("overnight", "overnight", OVERNIGHT_START, OVERNIGHT_REF, "cboe"),
    ):
        vix = args.vix_source or vix_default
        print(f"\n=== {label} panel  {start} → {end}  vix={vix} ===", flush=True)
        p = _build(gap_mode, start, end, vix)
        print(f"  rebuilt: {len(p):,} rows × {p['fri_ts'].nunique():,} gaps "
              f"({p['fri_ts'].min()} → {p['fri_ts'].max()})")
        if "earnings_next_week" in p.columns:
            print(f"  earnings gaps flagged: {int(p['earnings_next_week'].sum()):,}")

        if ref_path.exists():
            ref = pd.read_parquet(ref_path)
            ok = _regression(p, ref, label)
            print(f"  [{label}] regression: {'PASS' if ok else 'REVIEW'}")

        out = DATA_PROCESSED / f"{ref_path.stem}_ext_{tag}.parquet"
        if args.write:
            p.to_parquet(out, index=False)
            print(f"  wrote {out}")
        else:
            print(f"  (dry run — would write {out})")


if __name__ == "__main__":
    main()
