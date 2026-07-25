"""
Band-archive emitter — the public served-band record `soothsayer-verify`
audits against.

Serves the frozen LWC artefact over every forward weekend in
`data/processed/forward_tape_v1.parquet` and appends one row per
(weekend, symbol, τ) to `data/band_archive/bands_v1.csv` (committed —
`data/band_archive/` is deliberately NOT gitignored, unlike the rest of
`data/`). The archive records **claims only**: band edges, point, and
receipt fields. It never contains the realised Monday open — a verifier
fetches truth independently; that separation is the point.

Uses `soothsayer.backtest.frozen_serving` — the same code path as the
weekly forward-tape evaluation report — so the archive and the report
cannot drift.

Provenance semantics (see data/band_archive/README.md):
  retro_frozen        row computed after the weekend outcome existed,
                      from an artefact frozen BEFORE the weekend
                      (deterministic function of a SHA-stamped freeze).
  published_pre_open  row emitted before the target open existed
                      (future publisher wiring; not yet produced).

Dedup key: (weekend_date, symbol, tau, artefact_sha256) — re-runs are
idempotent; a new freeze appends new rows rather than rewriting history.

Run
---
  uv run python scripts/emit_band_archive.py [--frozen-suffix YYYYMMDD]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from soothsayer.backtest.calibration import DEFAULT_TAUS
from soothsayer.backtest.frozen_serving import (
    apply_frozen_sigma_rule,
    frozen_schedules,
    load_frozen,
    serve_frozen,
)
from soothsayer.config import DATA_PROCESSED

FORWARD_TAPE_PATH = DATA_PROCESSED / "forward_tape_v1.parquet"
ARCHIVE_PATH = Path(__file__).resolve().parents[1] / "data" / "band_archive" / "bands_v1.csv"

# Receipt codes mirroring crates/soothsayer-consumer (FORECASTER_LWC,
# PROFILE_LENDING). The frozen artefact is the M6 LWC lending-track
# serving path; if a future freeze changes either, thread it from the
# sidecar instead of widening these constants.
FORECASTER_CODE_LWC = 3
PROFILE_CODE_LENDING = 1

COLUMNS = [
    "weekend_date", "mon_date", "symbol", "tau",
    "lower", "upper", "point", "half_width_bps", "regime_code",
    "forecaster_code", "profile_code", "artefact_sha256",
    "provenance", "computed_ts",
]
DEDUP_KEY = ["weekend_date", "symbol", "tau", "artefact_sha256"]


def build_rows(frozen_suffix: str | None) -> pd.DataFrame:
    tape = pd.read_parquet(FORWARD_TAPE_PATH)
    frozen_path, sidecar = load_frozen(frozen_suffix)
    sha = sidecar.get("_artefact_sha256")
    if not sha:
        raise SystemExit(f"{frozen_path.name} lacks _artefact_sha256; refusing "
                         "to emit archive rows without a verifiable freeze hash.")
    qt, cb, delta = frozen_schedules(sidecar)

    full = apply_frozen_sigma_rule(tape, sidecar)
    forward = full[full["is_forward"] & full["sigma_hat_sym_pre_fri"].notna()].copy()
    if forward.empty:
        return pd.DataFrame(columns=COLUMNS)
    forward["fri_date"] = pd.to_datetime(forward["fri_ts"]).dt.date
    forward["mon_date"] = pd.to_datetime(forward["mon_ts"]).dt.date
    forward = forward.sort_values(["fri_date", "symbol"]).reset_index(drop=True)

    bounds = serve_frozen(forward, qt, cb, delta)
    computed_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    point = forward["fri_close"].astype(float) * (
        1.0 + forward["factor_ret"].astype(float)
    )

    frames = []
    for tau in DEFAULT_TAUS:
        b = bounds[tau]
        frames.append(pd.DataFrame({
            "weekend_date": forward["fri_date"],
            "mon_date": forward["mon_date"],
            "symbol": forward["symbol"],
            "tau": float(tau),
            "lower": b["lower"].astype(float),
            "upper": b["upper"].astype(float),
            "point": point,
            "half_width_bps": ((b["upper"] - b["lower"]) / 2
                               / forward["fri_close"].astype(float) * 1e4),
            "regime_code": forward["regime_pub"].astype(str),
            "forecaster_code": FORECASTER_CODE_LWC,
            "profile_code": PROFILE_CODE_LENDING,
            "artefact_sha256": sha,
            "provenance": "retro_frozen",
            "computed_ts": computed_ts,
        }))
    out = pd.concat(frames, ignore_index=True)[COLUMNS]
    print(f"Frozen artefact: {frozen_path.name} (sha256 {sha})")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-suffix", default=None,
                        help="YYYYMMDD suffix of the frozen artefact "
                             "(defaults to latest).")
    args = parser.parse_args()

    new = build_rows(args.frozen_suffix)
    if new.empty:
        print("No forward rows with σ̂ available — nothing to emit.")
        return

    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ARCHIVE_PATH.exists():
        existing = pd.read_csv(ARCHIVE_PATH, dtype={"weekend_date": str,
                                                    "mon_date": str})
        seen = set(map(tuple, existing[DEDUP_KEY].astype(str).to_numpy()))
        mask = [tuple(map(str, k)) not in seen
                for k in new[DEDUP_KEY].astype(str).to_numpy()]
        appended = new[mask]
        combined = pd.concat([existing, appended], ignore_index=True)
    else:
        appended, combined = new, new

    combined = combined.sort_values(["weekend_date", "symbol", "tau"]).reset_index(drop=True)
    tmp = ARCHIVE_PATH.with_suffix(".csv.tmp")
    combined.to_csv(tmp, index=False, float_format="%.10g")
    tmp.replace(ARCHIVE_PATH)
    print(f"Appended {len(appended)} rows ({len(new) - len(appended)} already "
          f"present); archive now {len(combined)} rows "
          f"({combined['weekend_date'].nunique()} weekends) at {ARCHIVE_PATH}")


if __name__ == "__main__":
    main()
