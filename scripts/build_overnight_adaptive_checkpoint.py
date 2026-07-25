"""
Build the overnight adaptive checkpoint (W15 profile).

Emits two artefacts:

  overnight_adaptive_artefact_v1.json   frozen per-regime quantiles + c(tau),
                                        SHA-stamped — the pre-committed part
  overnight_adaptive_checkpoint_v1.json a hashed snapshot of m[tau][cell] at
                                        a stated period — the live part

The split is the whole design. The quantiles are frozen and hashed exactly
as the two-sided artefact is; only the per-cell *level* adapts, and its
state is three scalars per tau under a deterministic update over public
prices. A consumer verifies a read in one step against the checkpoint, and
audits the checkpoint itself by replaying from the previous one.

Run
---
  ./.venv/bin/python scripts/build_overnight_adaptive_checkpoint.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from soothsayer.adaptive_state import GAMMA, M_CEIL, M_FLOOR, replay, verify_checkpoint
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS, prep_panel_for_forecaster,
)
from soothsayer.config import DATA_PROCESSED

PANEL = DATA_PROCESSED / "overnight_panel.parquet"
ARTEFACT_JSON = DATA_PROCESSED / "overnight_adaptive_artefact_v1.json"
CHECKPOINT_JSON = DATA_PROCESSED / "overnight_adaptive_checkpoint_v1.json"
SPLIT_DATE = date(2023, 1, 1)
SIGMA_EXCL = "earnings_next_week"      # de-contaminated σ̂ — see W12 correction


def _cp_q(s: np.ndarray, tau: float) -> float:
    s = np.sort(s[np.isfinite(s)])
    if s.size == 0:
        return float("nan")
    k = min(max(int(np.ceil(tau * (s.size + 1))), 1), s.size)
    return float(s[k - 1])


def main() -> None:
    raw = pd.read_parquet(PANEL)
    raw["fri_ts"] = pd.to_datetime(raw["fri_ts"]).dt.date
    raw = raw.dropna(subset=["mon_open", "fri_close", "regime_pub",
                             "factor_ret"]).reset_index(drop=True)
    raw["regime_pub"] = raw["regime_pub"].astype(str)

    w = prep_panel_for_forecaster(raw, "lwc",
                                  sigma_exclude_mask_col=SIGMA_EXCL)
    w["point"] = w["fri_close"] * (1.0 + w["factor_ret"])
    w = (w[(w["sigma_hat_sym_pre_fri"] > 0) & w["score"].notna()]
         .sort_values(["fri_ts", "symbol"]).reset_index(drop=True))

    train = w[w["fri_ts"] < SPLIT_DATE]
    regimes = sorted(w["regime_pub"].unique())
    qt = {r: {t: _cp_q(train[train["regime_pub"] == r]["score"].to_numpy(float), t)
              for t in DEFAULT_TAUS} for r in regimes}

    print(f"rows {len(w):,} · train {len(train):,} · regimes {regimes}")
    for r in regimes:
        print(f"  {r:<16} " + "  ".join(f"q({t})={qt[r][t]:.3f}"
                                        for t in DEFAULT_TAUS))

    # --- frozen part: quantiles, hashed
    artefact = {
        "_artefact": "overnight_adaptive_v1",
        "_profile": "overnight",
        "_built_at": datetime.now(timezone.utc).isoformat(),
        "_panel": PANEL.name,
        "_split_date": str(SPLIT_DATE),
        "_sigma_rule": "ewma_hl8, earnings-excluded scale pool",
        "_deployed": False,
        "_status": (
            "CHARACTERISED, NOT DEPLOYED. W15 cleared the W17 promotion "
            "gate but promotion is blocked on the wire/archive work in "
            "reports/active/adaptive_state_wire_design.md."
        ),
        "regime_quantile_table": {
            r: {f"{t:.2f}": qt[r][t] for t in DEFAULT_TAUS} for r in regimes
        },
    }
    canon = json.dumps(artefact["regime_quantile_table"], sort_keys=True,
                       separators=(",", ":"))
    sha = hashlib.sha256(canon.encode()).hexdigest()
    artefact["_artefact_sha256"] = sha
    ARTEFACT_JSON.write_text(json.dumps(artefact, indent=2) + "\n")
    print(f"\nFrozen quantiles sha256 {sha[:16]}…  -> {ARTEFACT_JSON.name}")

    # --- live part: replay m over the whole panel
    through = max(w["fri_ts"])
    ck = replay(w, qt, DEFAULT_TAUS, profile="overnight",
                artefact_sha256=sha, through_period=through)
    CHECKPOINT_JSON.write_text(json.dumps(ck.to_dict(), indent=2) + "\n")
    print(f"Checkpoint through {ck.through_period} "
          f"({ck.n_periods_replayed} periods) sha256 "
          f"{ck.checkpoint_sha256[:16]}…  -> {CHECKPOINT_JSON.name}")

    print("\n  learned multipliers m[tau][cell]:")
    hdr = "    cell".ljust(20) + "".join(f"τ={t:<8}" for t in DEFAULT_TAUS)
    print(hdr)
    for r in regimes:
        print("    " + r.ljust(16)
              + "".join(f"{ck.m[t][r]:<10.3f}" for t in DEFAULT_TAUS))

    # --- prove the audit property on the spot
    ok, _ = verify_checkpoint(ck, w, qt)
    print(f"\n  self-verify (recompute from public data): "
          f"{'PASS' if ok else 'FAIL'}")
    tampered = pd.DataFrame(ck.to_dict()["m"]).copy()
    print(f"  checkpoint pins the rule as well as the numbers: "
          f"gamma={ck.gamma}, floor={ck.m_floor}, ceil={ck.m_ceil}")


if __name__ == "__main__":
    main()
