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
CHAIN_JSON = DATA_PROCESSED / "overnight_adaptive_checkpoint_chain_v1.json"
# Cadence policy: quarterly. Chosen because it bounds an auditor's replay to
# ~63 overnight periods (one quarter of weeknights) while keeping the number
# of published hashes small enough to eyeball. Each checkpoint is verifiable
# by replaying from its predecessor, so the chain is tamper-evident end to
# end and an auditor picks their own depth: one interval for a spot check,
# the whole chain for a full audit.
CHECKPOINT_CADENCE = "quarterly"
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

    # --- live part: a quarterly chain, plus the latest for serving
    periods = sorted(set(w["fri_ts"]))
    q_ends: list[date] = []
    for p_ in periods:
        qtr = (p_.month - 1) // 3
        nxt_i = periods.index(p_) + 1
        if nxt_i >= len(periods):
            continue
        n = periods[nxt_i]
        if (n.year, (n.month - 1) // 3) != (p_.year, qtr):
            q_ends.append(p_)
    chain, prev_state, prev_sha, prev_end = [], None, None, None
    for q_end in q_ends:
        # Each link replays only its own quarter, seeded from the previous
        # checkpoint's state — the same resume path an auditor uses, so the
        # chain is built by exactly the procedure that verifies it.
        seg = (w[w["fri_ts"] <= q_end] if prev_end is None
               else w[(w["fri_ts"] > prev_end) & (w["fri_ts"] <= q_end)])
        c = replay(seg, qt, DEFAULT_TAUS, profile="overnight",
                   artefact_sha256=sha, through_period=q_end,
                   start_state=prev_state)
        d = c.to_dict(); d["prev_checkpoint_sha256"] = prev_sha
        chain.append(d)
        prev_state, prev_sha, prev_end = c.m, c.checkpoint_sha256, q_end
    CHAIN_JSON.write_text(json.dumps(
        {"_cadence": CHECKPOINT_CADENCE, "_artefact_sha256": sha,
         "_n_checkpoints": len(chain), "checkpoints": chain}, indent=2) + "\n")
    print(f"Chain: {len(chain)} quarterly checkpoints -> {CHAIN_JSON.name}")

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
