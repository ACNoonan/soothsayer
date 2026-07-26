"""
Generate the Python ground truth for the Rust adaptive-path parity suite.

The one thing this suite exists to pin is the **canonical serialisation**.
The checkpoint hash covers gamma, the clip bounds and the period as well as
the numbers, so a Rust verifier that serialises even slightly differently
would reject an *honest* checkpoint — a failure that presents as fraud
detection and is actually a port bug. Byte-level divergence here is the
worst kind: silent, and it points the accusatory direction.

Emits:
  canonical      the exact pre-image string, so Rust is compared byte-for-byte
                 rather than only on the digest (a digest match tells you
                 nothing about WHERE two impls diverge)
  sha256         the digest of that pre-image
  multiplier     lookup cases, including unknown-cell fallback
  bands          serving cases: m * q * sigma * prev_close
  edge_floats    fixed-precision formatting cases, the most likely source of
                 a cross-language mismatch

Run
---
  ./.venv/bin/python scripts/gen_adaptive_parity_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

from soothsayer.adaptive_state import Checkpoint
from soothsayer.config import DATA_PROCESSED

OUT = Path("crates/soothsayer-oracle/tests/fixtures/adaptive_parity.json")
CHECKPOINT = DATA_PROCESSED / "overnight_adaptive_checkpoint_v1.json"


def main() -> None:
    if not CHECKPOINT.exists():
        raise SystemExit(
            f"{CHECKPOINT.name} missing — run "
            "`python scripts/build_overnight_adaptive_checkpoint.py` first."
        )
    ck = Checkpoint.from_dict(json.loads(CHECKPOINT.read_text()))
    if not ck.verify_self():
        raise SystemExit("checkpoint fails its own hash; refusing to pin it.")

    cells = sorted(next(iter(ck.m.values())))
    taus = sorted(ck.m)

    multipliers = [
        {"cell": c, "tau": t, "m": ck.m[t][c]} for t in taus for c in cells
    ]
    # unknown cell must fall back to 1.0, not raise and not serve zero
    multipliers.append({"cell": "never_seen_cell", "tau": taus[0], "m": 1.0})

    bands = []
    for t in taus:
        for c in cells:
            for sigma, prev_close, q in (
                (0.0100, 100.0, 2.0),
                (0.0271, 417.31, 15.834),
                (0.0043, 1893.55, 0.843),
            ):
                m = ck.m[t][c]
                bands.append({
                    "cell": c, "tau": t, "m": m, "q": q,
                    "sigma_hat": sigma, "prev_close": prev_close,
                    "half_width": m * q * sigma * prev_close,
                })

    fixture = {
        "_generated_by": "scripts/gen_adaptive_parity_fixture.py",
        "_ground_truth": "soothsayer.adaptive_state.Checkpoint",
        "checkpoint": ck.to_dict(),
        "canonical": ck.canonical(),
        "sha256": ck.checkpoint_sha256,
        "multipliers": multipliers,
        "bands": bands,
        "edge_floats": [
            {"value": v, "formatted": f"{v:.10f}"}
            for v in (0.0, 1.0, 0.05, 0.25, 4.0, 0.7047382915,
                      0.9999999999, 1.00000000005, 0.1234567890123,
                      2.675, 1.005, 0.5)
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixture, indent=1) + "\n")
    print(f"Wrote {OUT}")
    print(f"  canonical: {len(fixture['canonical'])} bytes")
    print(f"  sha256:    {fixture['sha256'][:16]}…")
    print(f"  cases:     {len(multipliers)} multiplier, {len(bands)} band, "
          f"{len(fixture['edge_floats'])} float")


if __name__ == "__main__":
    main()
