"""
Parity-fixture generator for `crates/soothsayer-verify`.

The verifier deliberately re-implements the coverage statistics
(Kupiec POF, Christoffersen independence, integer-df χ² survival)
independently of `soothsayer.backtest.metrics` — reusing the paper's own
code would let a bug self-confirm. This script pins the Python/scipy
implementations as ground truth: it writes synthetic edge cases AND the
real forward-tape violation panel to a JSON fixture that the Rust test
suite (`tests/parity.rs`) must reproduce to ≤1e-9.

Regenerate after any change to `metrics.py`'s test statistics or to the
frozen serving path:

  uv run python scripts/gen_verify_parity_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import DEFAULT_TAUS
from soothsayer.backtest.frozen_serving import (
    apply_frozen_sigma_rule,
    frozen_schedules,
    load_frozen,
    serve_frozen,
)
from soothsayer.config import DATA_PROCESSED

OUT = (Path(__file__).resolve().parents[1]
       / "crates" / "soothsayer-verify" / "tests" / "fixtures" / "parity.json")


def _nan_to_none(x: float):
    return None if (x is None or not np.isfinite(x)) else float(x)


def synthetic_cases() -> tuple[list, list]:
    rng = np.random.default_rng(20260721)
    vectors = [
        [0] * 12,
        [0] * 120,
        [0] * 119 + [1],
        [1] + [0] * 119,
        [0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0] * 3,      # clustered
        [0, 1] * 18,                                    # alternating
        [1] * 20,
        [int(x) for x in rng.integers(0, 2, size=60)],
        [int(x) for x in (rng.random(200) < 0.05)],
        [int(x) for x in (rng.random(200) < 0.32)],
    ]
    kupiec = []
    christ = []
    for v in vectors:
        arr = np.asarray(v, dtype=int)
        for claimed in (0.68, 0.85, 0.95, 0.99):
            lr, p = met._lr_kupiec(arr, claimed)
            kupiec.append({"violations": v, "claimed": claimed,
                           "lr": _nan_to_none(lr), "p": _nan_to_none(p)})
        lr_i, p_i = met._lr_christoffersen_independence(arr)
        christ.append({"violations": v,
                       "lr": _nan_to_none(lr_i), "p": _nan_to_none(p_i)})
    return kupiec, christ


def chi2_sf_cases() -> list:
    cases = []
    for df in (1, 2, 3, 4, 5, 7, 10, 12):
        for x in (0.0, 1e-6, 0.5, 1.1474, 2.4121, 5.8806, 7.5817, 15.3, 40.0):
            cases.append({"x": x, "df": df,
                          "sf": float(1.0 - chi2.cdf(x, df=df))})
    return cases


def forward_tape_cases() -> list:
    """The real 12-weekend forward panel: per-symbol violation vectors at
    each served τ plus the pooled statistics the report prints. This is the
    integration-grade fixture — Rust must reproduce the actual report."""
    tape = pd.read_parquet(DATA_PROCESSED / "forward_tape_v1.parquet")
    _, sidecar = load_frozen(None)
    qt, cb, delta = frozen_schedules(sidecar)
    full = apply_frozen_sigma_rule(tape, sidecar)
    fwd = full[full["is_forward"] & full["sigma_hat_sym_pre_fri"].notna()].copy()
    fwd = fwd.sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    bounds = serve_frozen(fwd, qt, cb, delta)

    out = []
    for tau in DEFAULT_TAUS:
        b = bounds[tau]
        inside = (fwd["mon_open"] >= b["lower"]) & (fwd["mon_open"] <= b["upper"])
        viol = (~inside).astype(int)
        lr_uc, p_uc = met._lr_kupiec(viol.to_numpy(), tau)
        by_symbol: dict[str, list[int]] = {}
        lr_sum, k = 0.0, 0
        for sym in sorted(fwd["symbol"].unique()):
            idx = fwd.index[fwd["symbol"] == sym]
            sub = fwd.loc[idx].sort_values("fri_ts")
            v = viol.loc[sub.index].to_numpy()
            by_symbol[sym] = [int(x) for x in v]
            lr_g, _ = met._lr_christoffersen_independence(v)
            if np.isfinite(lr_g):
                lr_sum += lr_g
                k += 1
        christ_p = (float(1.0 - chi2.cdf(max(lr_sum, 0.0), df=k))
                    if k > 0 else None)
        out.append({
            "claimed": float(tau),
            "violations_by_symbol": by_symbol,
            "kupiec_lr": _nan_to_none(lr_uc),
            "kupiec_p": _nan_to_none(p_uc),
            "christ_lr": _nan_to_none(lr_sum) if k > 0 else None,
            "christ_df": k,
            "christ_p": christ_p,
        })
    return out


def main() -> None:
    kupiec, christ = synthetic_cases()
    fixture = {
        "_generated_by": "scripts/gen_verify_parity_fixture.py",
        "_ground_truth": "scipy.stats.chi2 + soothsayer.backtest.metrics",
        "chi2_sf": chi2_sf_cases(),
        "kupiec": kupiec,
        "christoffersen": christ,
        "forward_tape": forward_tape_cases(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixture, indent=1))
    print(f"Wrote {OUT} "
          f"({len(fixture['chi2_sf'])} chi2 + {len(kupiec)} kupiec + "
          f"{len(christ)} christoffersen + {len(fixture['forward_tape'])} "
          "forward-tape cases)")


if __name__ == "__main__":
    main()
