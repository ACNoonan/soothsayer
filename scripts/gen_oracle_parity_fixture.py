"""
Generate the Python ground truth for the M5/M6 Rust serving-parity suite.

The 180/180 M5↔M6 Python/Rust parity was a one-off validation with no
committed harness, so nothing currently catches drift on the serving path.
This fixture makes it a regression suite.

Two distinct failure modes are covered, and the second is the one that will
actually bite:

1. **Formula drift.** The band arithmetic diverges between `oracle.py` and
   `oracle.rs` — caught by the per-case band comparison.

2. **Constant staleness.** Python loads the per-regime quantiles, c(tau) and
   delta schedules from the artefact JSON sidecar at import. Rust *hardcodes*
   them in `config.rs`. Rebuild the artefact and the Rust constants are
   silently stale — the Rust oracle keeps serving, just with last quarter's
   calibration. Nothing in the type system notices. So the fixture pins the
   Python sidecar values and the Rust suite asserts its own constants equal
   them.

Serving cases embed the artefact row fields directly (regime, point,
fri_close, sigma_hat), so the Rust suite needs no parquet — `data/processed/`
is gitignored and a test that silently skips is not a regression test.

Run
---
  ./.venv/bin/python scripts/gen_oracle_parity_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

import soothsayer.oracle as O
from soothsayer.oracle import Oracle

OUT = Path("crates/soothsayer-oracle/tests/fixtures/oracle_parity.json")
ANCHORS = [0.68, 0.85, 0.95, 0.99]
# on-anchor plus deliberately off-anchor, where interpolation is exercised
TAUS = [0.68, 0.72, 0.85, 0.90, 0.95, 0.97, 0.99]
REGIMES = ["normal", "long_weekend", "high_vol"]


def main() -> None:
    # Oracle.load() defaults to profile="lending", where fair_value() serves
    # the M6b2 SYMBOL-CLASS path. Rust's Forecaster::Mondrian is the regime
    # path, which Python reaches only under profile="amm". Comparing the
    # default against Rust silently compares two different architectures —
    # the first run of this harness caught exactly that.
    orc = Oracle.load(profile="amm")
    if not orc.has_lwc:
        raise SystemExit("LWC artefact not loaded; cannot pin M6 cases.")

    cases = []
    avail = orc.list_available()
    # spread across symbols and dates rather than taking a contiguous block
    picks = avail.iloc[:: max(1, len(avail) // 24)].head(24)
    for _, row in picks.iterrows():
        sym, as_of = row["symbol"], row["fri_ts"]
        for tau in TAUS:
            for fc in ("mondrian", "lwc"):
                try:
                    pp = (orc.fair_value(sym, as_of, target_coverage=tau)
                          if fc == "mondrian"
                          else orc.fair_value_lwc(sym, as_of, target_coverage=tau))
                except Exception:
                    continue
                d = pp.diagnostics
                cases.append({
                    "symbol": sym, "as_of": str(as_of), "tau": tau,
                    "forecaster": fc,
                    "regime": pp.regime,
                    "point": pp.point,
                    "fri_close": d["fri_close"],
                    "sigma_hat": d.get("sigma_hat_sym_pre_fri"),
                    "served_target": pp.claimed_coverage_served,
                    "delta": pp.calibration_buffer_applied,
                    "c_bump": d["c_bump"],
                    "q_eff": d["q_eff"],
                    "lower": pp.lower, "upper": pp.upper,
                    "sharpness_bps": pp.sharpness_bps,
                })

    fixture = {
        "_generated_by": "scripts/gen_oracle_parity_fixture.py",
        "_ground_truth": "soothsayer.oracle profile=amm (sidecar-loaded constants)",
        "_profile": "amm",
        "anchors": ANCHORS,
        # --- constant staleness guards: Rust hardcodes these, Python loads them
        "mondrian_constants": {
            "regime_quantile_table": {
                r: [O.regime_quantile_for(r, t) for t in ANCHORS] for r in REGIMES
            },
            "c_bump_schedule": [O.c_bump_for_target(t) for t in ANCHORS],
            "delta_shift_schedule": [O.delta_shift_for_target(t) for t in ANCHORS],
        },
        "lwc_constants": {
            "regime_quantile_table": {
                r: [O.lwc_regime_quantile_for(r, t) for t in ANCHORS] for r in REGIMES
            },
            "c_bump_schedule": [O.lwc_c_bump_for(t) for t in ANCHORS],
            "delta_shift_schedule": [O.lwc_delta_shift_for(t) for t in ANCHORS],
        },
        # --- interpolation at off-anchor tau
        "interp": [
            {"tau": t, "regime": r,
             "mondrian_q": O.regime_quantile_for(r, t),
             "lwc_q": O.lwc_regime_quantile_for(r, t),
             "mondrian_c": O.c_bump_for_target(t),
             "lwc_c": O.lwc_c_bump_for(t)}
            for t in TAUS for r in REGIMES
        ],
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixture, indent=1) + "\n")
    print(f"Wrote {OUT}")
    print(f"  serving cases: {len(cases)} "
          f"({sum(1 for c in cases if c['forecaster']=='mondrian')} M5 / "
          f"{sum(1 for c in cases if c['forecaster']=='lwc')} M6)")
    print(f"  interp cases:  {len(fixture['interp'])}")


if __name__ == "__main__":
    main()
