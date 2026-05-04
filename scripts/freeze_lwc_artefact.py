"""
Freeze the M6 LWC artefact for the forward-tape harness — Phase 4.1.

Copies the live `data/processed/lwc_artefact_v1.json` to a date-tagged
frozen sidecar `lwc_artefact_v1_frozen_{YYYYMMDD}.json`, embeds a
SHA-256 of the canonical-JSON serialisation at `_artefact_sha256`, and
records the freeze date at `_freeze_date`. The frozen file is the
single artefact every forward-tape evaluation runs against — no
re-fitting, no schedule re-tuning.

Run
---
  uv run python scripts/freeze_lwc_artefact.py             # date = today
  uv run python scripts/freeze_lwc_artefact.py --date 2026-04-24

The companion parquet (`lwc_artefact_v1.parquet`) is also copied,
tagged with the same date suffix; the SHA-256 in the JSON sidecar
covers both. Idempotent: re-running with the same date overwrites the
frozen pair.

Why we ship a separate `freeze_lwc_artefact.py` instead of inlining the
freeze in `build_lwc_artefact.py`: the live artefact keeps updating as
new training rows accumulate; the frozen artefact must NOT change
between forward-tape evaluations. Two distinct lifecycles, two distinct
files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import date

from soothsayer.config import DATA_PROCESSED


LIVE_JSON = DATA_PROCESSED / "lwc_artefact_v1.json"
LIVE_PARQUET = DATA_PROCESSED / "lwc_artefact_v1.parquet"


def _canonical_json_bytes(obj: dict) -> bytes:
    """Stable canonical serialisation: sorted keys, no extra whitespace, UTF-8.
    SHA-256 of this byte stream is the artefact's content fingerprint."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        type=lambda s: date.fromisoformat(s),
        default=date.today(),
        help="Freeze date stamp (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args()

    if not LIVE_JSON.exists():
        raise FileNotFoundError(
            f"Live artefact JSON missing: {LIVE_JSON}. "
            "Run scripts/build_lwc_artefact.py first."
        )
    if not LIVE_PARQUET.exists():
        raise FileNotFoundError(
            f"Live artefact parquet missing: {LIVE_PARQUET}. "
            "Run scripts/build_lwc_artefact.py first."
        )

    stamp = args.date.strftime("%Y%m%d")
    frozen_json = DATA_PROCESSED / f"lwc_artefact_v1_frozen_{stamp}.json"
    frozen_parquet = DATA_PROCESSED / f"lwc_artefact_v1_frozen_{stamp}.parquet"

    # 1. Copy the parquet first so we can hash it for the JSON sidecar.
    shutil.copyfile(LIVE_PARQUET, frozen_parquet)
    parquet_sha = _sha256_file(frozen_parquet)

    # 2. Load the live JSON, augment with freeze metadata + parquet hash,
    #    compute the canonical-JSON sha of the augmented object (excluding
    #    the self-sha field — that goes in last and points at the
    #    pre-self-sha canonical bytes), and write.
    sidecar = json.loads(LIVE_JSON.read_text())
    augmented = {
        **sidecar,
        "_freeze_date": args.date.isoformat(),
        "_frozen_parquet_sha256": parquet_sha,
        "_frozen_parquet_path": frozen_parquet.name,
    }
    self_sha = hashlib.sha256(_canonical_json_bytes(augmented)).hexdigest()
    augmented["_artefact_sha256"] = self_sha
    frozen_json.write_text(json.dumps(augmented, indent=2) + "\n")

    print(f"Wrote {frozen_json}")
    print(f"  _freeze_date         = {augmented['_freeze_date']}")
    print(f"  _artefact_sha256     = {self_sha}")
    print(f"  _frozen_parquet_sha = {parquet_sha}")
    print(f"  source split_date    = {augmented.get('split_date')}")
    print(f"  n_train / n_oos      = {augmented.get('n_train')} / {augmented.get('n_oos')}")
    print(f"Wrote {frozen_parquet}  ({frozen_parquet.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
