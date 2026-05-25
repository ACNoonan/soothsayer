"""
Build the OVERNIGHT (single-weeknight close→open) calibration panel.

Phase 1 of the off-hours generalization (reports/active/overnight_panel_scope.md).
This is the overnight analog of the weekend `v1b_panel.parquet`: same factor
switchboard, same σ̂ machinery, same column contract — the *only* difference is
the gap selector (`PanelSpec.gap_mode="overnight"` → gap==1 trading-day steps
instead of Fri→Mon).

Writes `data/processed/overnight_panel.parquet` and prints a sanity read that
tests the two structural hypotheses motivating the build:
  (H1) overnight moves are smaller than weekend moves (shorter closed window),
       so a weekend-calibrated band would over-cover overnight;
  (H2) earnings nights are a distinct fat tail the weekend panel barely contains.

CAVEATS (Phase 1, to be closed in Phase 2):
  * earnings_night uses the pre-timing STUB flag (brackets both nights around an
    earnings date; needs scryer BMO/AMC timing, Phase 0).
  * σ̂ is the weekend EWMA HL=8 variant applied as-is at overnight cadence — not
    yet re-tuned, and contaminated by earnings jumps.
  * ex-dividend mornings not yet corrected (raw close/open).
Treat coverage numbers downstream as a first read, not a validated result.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from soothsayer.backtest import panel as panel_mod
from soothsayer.backtest import regimes
from soothsayer.backtest.calibration import add_sigma_hat_sym_ewma, SIGMA_HAT_MIN
from soothsayer.config import DATA_PROCESSED

START = date(2012, 1, 1)
END = date(2026, 4, 25)
SIGMA_HL = 8  # match the deployed weekend variant for a like-for-like first read
OUT = DATA_PROCESSED / "overnight_panel.parquet"


def _abs_z(p: pd.DataFrame) -> pd.Series:
    """|realized standardized move| = |log(t1_open/t0_close)| / t0 20d vol."""
    r = np.log(p["mon_open"].astype(float) / p["fri_close"].astype(float))
    return (r / p["fri_vol_20d"].replace(0, np.nan)).abs()


def _dispersion(z: pd.Series) -> dict:
    z = z.dropna()
    return {
        "n": int(z.size),
        "mean_|z|": round(float(z.mean()), 3),
        "p95_|z|": round(float(z.quantile(0.95)), 3),
        "p99_|z|": round(float(z.quantile(0.99)), 3),
    }


def main() -> None:
    spec = panel_mod.PanelSpec(start=START, end=END, gap_mode="overnight")
    print(f"Building overnight panel  {START} → {END}  (gap_mode=overnight) …", flush=True)
    p = panel_mod.build(spec)
    p = regimes.tag(p, mode="overnight")

    # σ̂ (overnight cadence). De-contaminate the baseline scale by excluding
    # earnings-night residuals from the EWMA pool (their fat tail is carried by
    # the earnings_night regime quantile, not by σ̂). Alias to the canonical
    # serving column the artefact/battery expect.
    p = add_sigma_hat_sym_ewma(
        p, half_life=SIGMA_HL, min_obs=SIGMA_HAT_MIN,
        exclude_mask_col="earnings_next_week",
    )
    p["sigma_hat_sym_pre_fri"] = p[f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HL}"]

    p.attrs.clear()  # PanelSpec in attrs is not parquet-serializable
    p.to_parquet(OUT, index=False)
    print(f"wrote {OUT}  ({len(p):,} rows)\n", flush=True)

    # ----------------------------------------------------------- sanity read
    n_nights = p["fri_ts"].nunique()
    print(f"rows={len(p):,}  nights={n_nights:,}  symbols={p['symbol'].nunique()}  "
          f"span={p['fri_ts'].min()} → {p['fri_ts'].max()}", flush=True)
    print("\nregime_pub mix:")
    print(regimes.counts(p).to_string(index=False), flush=True)

    p["abs_z"] = _abs_z(p)

    # H1: overnight vs weekend dispersion (load the deployed weekend panel).
    print("\n=== H1: overnight vs weekend realized-move dispersion ===", flush=True)
    wk_path = DATA_PROCESSED / "v1b_panel.parquet"
    rows = [{"panel": "overnight", **_dispersion(p["abs_z"])}]
    if wk_path.exists():
        wk = pd.read_parquet(wk_path)
        wk_z = (np.log(wk["mon_open"].astype(float) / wk["fri_close"].astype(float))
                / wk["fri_vol_20d"].replace(0, np.nan)).abs()
        rows.append({"panel": "weekend", **_dispersion(wk_z)})
    print(pd.DataFrame(rows).to_string(index=False), flush=True)

    # H2: earnings-night vs non-earnings overnight dispersion.
    print("\n=== H2: earnings-night vs other overnight (raw move, not regime-pri) ===", flush=True)
    is_earn = p["earnings_next_week"].fillna(False).astype(bool)
    h2 = pd.DataFrame([
        {"bucket": "earnings_straddle", **_dispersion(p.loc[is_earn, "abs_z"])},
        {"bucket": "other", **_dispersion(p.loc[~is_earn, "abs_z"])},
    ])
    print(h2.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
