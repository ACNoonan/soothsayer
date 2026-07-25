"""
Band-archive I/O — shared by the archive emitters and the commitment
publisher.

The public band archive (`data/band_archive/`) is the append-only,
claims-only record `soothsayer-verify` audits (see the README there).
Two files:

  bands_v1.csv        one row per (weekend, symbol, τ): full band
                      (lower/point/upper) + receipt fields.
                      provenance ∈ {retro_frozen, published_pre_open}.
  commitments_v1.csv  one row per (weekend, symbol, τ): the Friday-close
                      commitment — σ̂, regime, and half-width — emitted
                      BEFORE the weekend's outcome information exists.
                      The Monday pre-open publisher must use these
                      committed widths verbatim (a commitment is
                      binding; recomputation drift is an alarm, not an
                      update).

Both are append-only with dedup key (weekend_date, symbol, tau,
artefact_sha256): re-runs are idempotent, and a pre-open row emitted on
Monday makes the Tuesday harness's retro row for the same key a no-op —
pre-open provenance wins by arriving first.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = REPO_ROOT / "data" / "band_archive"
BANDS_PATH = ARCHIVE_DIR / "bands_v1.csv"
COMMITMENTS_PATH = ARCHIVE_DIR / "commitments_v1.csv"
# Adaptive (overnight, W15) profile gets its OWN append-only archive rather
# than a new column on bands_v1. Three reasons: bands_v1 is parsed by the
# `soothsayer-verify` crate against a fixed schema; STATUS pins its rows as
# never-edited; and the two profiles have genuinely different verification
# procedures — a frozen row is checked against one artefact hash, an
# adaptive row against an artefact hash *and* a checkpoint hash. Mixing them
# in one file would force every consumer to branch on profile.
ADAPTIVE_BANDS_PATH = ARCHIVE_DIR / "bands_adaptive_v1.csv"

PROVENANCE_RETRO = "retro_frozen"
PROVENANCE_PRE_OPEN = "published_pre_open"

# Receipt codes mirroring crates/soothsayer-consumer (FORECASTER_LWC,
# PROFILE_LENDING).
FORECASTER_CODE_LWC = 3
# Reserved on the wire alongside the receipt label in oracle.py. A row under
# this code is NOT reproducible from the frozen artefact alone — it needs the
# m_regime and checkpoint_sha256 columns too.
FORECASTER_CODE_LWC_ADAPTIVE = 5
PROFILE_CODE_LENDING = 1
PROFILE_CODE_OVERNIGHT = 3

BANDS_COLUMNS = [
    "weekend_date", "mon_date", "symbol", "tau",
    "lower", "upper", "point", "half_width_bps", "regime_code",
    "forecaster_code", "profile_code", "artefact_sha256",
    "provenance", "computed_ts",
]

# Adaptive-profile rows carry the two extra fields needed to reproduce the
# band: the per-cell multiplier in force (`m_regime`) and the checkpoint it
# came from. Without both, an archive row cannot be re-derived from its own
# columns, which is the property that makes it an audit record at all.
ADAPTIVE_BANDS_COLUMNS = [
    "period_date", "next_open_date", "symbol", "tau",
    "lower", "upper", "point", "half_width_bps", "regime_code",
    "m_regime", "checkpoint_sha256", "checkpoint_through",
    "forecaster_code", "profile_code", "artefact_sha256",
    "provenance", "computed_ts",
]

COMMITMENTS_COLUMNS = [
    "weekend_date", "mon_date", "symbol", "tau",
    "fri_close", "sigma_hat", "regime_code",
    "half_width_bps", "half_width_abs",
    "forecaster_code", "profile_code", "artefact_sha256",
    "computed_ts",
]

DEDUP_KEY = ["weekend_date", "symbol", "tau", "artefact_sha256"]
SORT_KEY = ["weekend_date", "symbol", "tau"]

# Adaptive rows dedup on the CHECKPOINT hash, not the artefact hash: the
# frozen quantiles are stable across a whole chain, so artefact_sha256 alone
# would collapse every checkpoint's rows onto the first one emitted.
ADAPTIVE_DEDUP_KEY = ["period_date", "symbol", "tau", "checkpoint_sha256"]
ADAPTIVE_SORT_KEY = ["period_date", "symbol", "tau"]


def append_dedup(path: Path, new: pd.DataFrame, columns: list[str],
                 dedup_key: list[str] | None = None,
                 sort_key: list[str] | None = None) -> tuple[int, int]:
    """Append `new` rows to the CSV at `path`, skipping rows whose
    `dedup_key` already exists. Atomic write, stable sort, %.10g floats.
    Returns (n_appended, n_total).

    `dedup_key` / `sort_key` default to the frozen weekend schema; the
    adaptive profile passes ADAPTIVE_DEDUP_KEY / ADAPTIVE_SORT_KEY."""
    dedup_key = dedup_key or DEDUP_KEY
    sort_key = sort_key or SORT_KEY
    new = new[columns]
    if path.exists():
        date_cols = {c: str for c in
                     ("weekend_date", "mon_date", "period_date",
                      "next_open_date") if c in columns}
        existing = pd.read_csv(path, dtype=date_cols)
        seen = set(map(tuple, existing[dedup_key].astype(str).to_numpy()))
        mask = [tuple(map(str, k)) not in seen
                for k in new[dedup_key].astype(str).to_numpy()]
        appended = new[mask]
        combined = pd.concat([existing[columns], appended], ignore_index=True)
    else:
        appended, combined = new, new

    combined = combined.sort_values(sort_key).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    combined.to_csv(tmp, index=False, float_format="%.10g")
    tmp.replace(path)
    return len(appended), len(combined)
