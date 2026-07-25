"""
Adaptive-profile band-archive emitter (overnight, W15).

Sibling of `emit_band_archive.py`, with one structural difference that is
the whole point of the file.

The frozen weekend profile can serve any historical weekend in any order,
because the artefact does not move. The adaptive profile cannot: the band
served on night t uses the multiplier state accumulated from outcomes
through night t-1. Emitting a row for night t from a checkpoint that
already contains night t's outcome would be lookahead, and it would be
invisible in the output — the row would simply look slightly too well
calibrated.

So this emitter walks the panel forward in period order and, for each
night, **records the band BEFORE advancing the state with that night's
outcome** — the identical serve-then-update ordering that
`adaptive_state.replay()` uses internally. The `m_regime` written to each
row is therefore the multiplier a consumer could actually have read at
serve time.

As with the frozen archive, rows are **claims only**: band edges, point,
and receipt fields. The realised open is never written; a verifier fetches
truth independently, and that separation is what makes the archive
evidence rather than self-report.

Dedup key: (period_date, symbol, tau, checkpoint_sha256) — re-runs are
idempotent, and a new checkpoint appends rather than rewriting history.

Run
---
  ./.venv/bin/python scripts/emit_adaptive_band_archive.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from soothsayer.adaptive_state import GAMMA, M_CEIL, M_FLOOR, _advance_cell
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS, prep_panel_for_forecaster,
)
from soothsayer.band_archive import (
    ADAPTIVE_BANDS_COLUMNS as COLUMNS,
    ADAPTIVE_BANDS_PATH as ARCHIVE_PATH,
    ADAPTIVE_DEDUP_KEY,
    ADAPTIVE_SORT_KEY,
    FORECASTER_CODE_LWC_ADAPTIVE,
    PROFILE_CODE_OVERNIGHT,
    PROVENANCE_RETRO,
    append_dedup,
)
from soothsayer.config import DATA_PROCESSED

PANEL = DATA_PROCESSED / "overnight_panel.parquet"
SIDECAR = DATA_PROCESSED / "overnight_adaptive_artefact_v1.json"
CHECKPOINT = DATA_PROCESSED / "overnight_adaptive_checkpoint_v1.json"
SIGMA_EXCL = "earnings_next_week"


def build_rows(since: str | None) -> pd.DataFrame:
    if not (SIDECAR.exists() and CHECKPOINT.exists()):
        raise SystemExit(
            "Missing overnight adaptive artefact/checkpoint — run "
            "`python scripts/build_overnight_adaptive_checkpoint.py` first."
        )
    side = json.loads(SIDECAR.read_text())
    sha = side.get("_artefact_sha256")
    if not sha:
        raise SystemExit("sidecar lacks _artefact_sha256; refusing to emit.")
    qt = {c: {float(t): float(v) for t, v in row.items()}
          for c, row in side["regime_quantile_table"].items()}
    ck = json.loads(CHECKPOINT.read_text())

    raw = pd.read_parquet(PANEL)
    raw["fri_ts"] = pd.to_datetime(raw["fri_ts"]).dt.date
    raw["mon_ts"] = pd.to_datetime(raw["mon_ts"]).dt.date
    raw = raw.dropna(subset=["mon_open", "fri_close", "regime_pub",
                             "factor_ret"]).reset_index(drop=True)
    raw["regime_pub"] = raw["regime_pub"].astype(str)
    w = prep_panel_for_forecaster(raw, "lwc",
                                  sigma_exclude_mask_col=SIGMA_EXCL)
    w["point"] = w["fri_close"] * (1.0 + w["factor_ret"])
    w = (w[(w["sigma_hat_sym_pre_fri"] > 0) & w["score"].notna()]
         .sort_values(["fri_ts", "symbol"]).reset_index(drop=True))

    cells = sorted(w["regime_pub"].unique())
    m = {float(t): {c: 1.0 for c in cells} for t in DEFAULT_TAUS}
    cutoff = pd.to_datetime(since).date() if since else None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out = []
    for period in sorted(set(w["fri_ts"])):
        rows = w[w["fri_ts"] == period]
        emit = cutoff is None or period >= cutoff
        for tau in DEFAULT_TAUS:
            tau = float(tau)
            for _, r in rows.iterrows():
                cell = r["regime_pub"]
                q = qt.get(cell, {}).get(tau, float("nan"))
                mm = m[tau][cell]
                if not np.isfinite(q):
                    continue
                half = mm * q * float(r["sigma_hat_sym_pre_fri"]) * float(r["fri_close"])
                if emit:
                    out.append({
                        "period_date": str(period),
                        "next_open_date": str(r["mon_ts"]),
                        "symbol": r["symbol"], "tau": tau,
                        "lower": float(r["point"]) - half,
                        "upper": float(r["point"]) + half,
                        "point": float(r["point"]),
                        "half_width_bps": half / float(r["fri_close"]) * 1e4,
                        "regime_code": cell,
                        "m_regime": mm,
                        "checkpoint_sha256": ck["checkpoint_sha256"],
                        "checkpoint_through": ck["through_period"],
                        "forecaster_code": FORECASTER_CODE_LWC_ADAPTIVE,
                        "profile_code": PROFILE_CODE_OVERNIGHT,
                        "artefact_sha256": sha,
                        "provenance": PROVENANCE_RETRO,
                        "computed_ts": now,
                    })
            # advance AFTER recording — the serve-then-update ordering that
            # keeps each row's m_regime free of that night's own outcome
            pt = rows["point"].to_numpy(float)
            fc = rows["fri_close"].to_numpy(float)
            sg = rows["sigma_hat_sym_pre_fri"].to_numpy(float)
            ac = rows["mon_open"].to_numpy(float)
            cc = rows["regime_pub"].to_numpy()
            qq = np.array([qt.get(c, {}).get(tau, np.nan) for c in cc], float)
            mmv = np.array([m[tau][c] for c in cc], float)
            hw = mmv * qq * sg * fc
            breach = (ac < pt - hw) | (ac > pt + hw)
            for c in np.unique(cc):
                sel = cc == c
                if not np.isfinite(hw[sel]).any():
                    continue
                m[tau][c] = _advance_cell(m[tau][c], float(breach[sel].mean()),
                                          tau, GAMMA, M_FLOOR, M_CEIL)

    return pd.DataFrame(out, columns=COLUMNS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None,
                    help="only emit rows on/after this date (state is still "
                         "replayed from inception, so m_regime is correct)")
    args = ap.parse_args()

    new = build_rows(args.since)
    if new.empty:
        print("No adaptive rows to emit.")
        return
    n_app, n_tot = append_dedup(ARCHIVE_PATH, new, COLUMNS,
                                dedup_key=ADAPTIVE_DEDUP_KEY,
                                sort_key=ADAPTIVE_SORT_KEY)
    print(f"Adaptive archive: appended {n_app:,} of {len(new):,} rows "
          f"({n_tot:,} total) -> {ARCHIVE_PATH}")


if __name__ == "__main__":
    main()
