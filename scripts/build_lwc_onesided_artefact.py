"""
Build the one-sided (downside) LWC deployment artefact — lending profile.

Sibling of `build_lwc_artefact.py`. Same panel, same point estimator, same
per-symbol σ̂ rule, same Mondrian cells, same finite-sample rank formula.
The only change is the conformity score:

    two-sided (deployed) : |mon_open − point| / (fri_close · σ̂)
    one-sided (this)     : (point − mon_open) / (fri_close · σ̂)

Why (Appendix G): a two-sided band at τ places (1−τ)/2 in each tail, so its
lower edge is a (1+τ)/2 downside bound. A lending protocol is exposed in one
direction only, so the two-sided band over-provisions it — ~34% of the
collateral buffer at the τ = 0.85 default, ~41% overnight. Fitting the
downside quantile directly removes that and is better calibrated: on the
overnight panel, imposing symmetry fails Kupiec at three of four anchors.

**This artefact is NOT the deployed serving path.** It carries none of the
held-out battery behind the two-sided artefact — no leave-one-symbol-out, no
nested temporal holdout, no forward tape, no simulation study, no Rust
parity. It exists so the one-sided profile can be served, measured and
accumulate its own forward record alongside the frozen two-sided artefact,
which keeps its ~12 weekends of forward evidence intact. See Appendix G.5.

Outputs
-------
  data/processed/lwc_onesided_artefact_v1.parquet   per-(symbol, fri_ts) rows
  data/processed/lwc_onesided_artefact_v1.json      audit-trail sidecar

Run
---
  ./.venv/bin/python scripts/build_lwc_onesided_artefact.py
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    SIGMA_HAT_HL_WEEKENDS,
    add_sigma_hat_sym_ewma,
    compute_score_lwc_onesided,
)
from soothsayer.config import DATA_PROCESSED

PANEL = DATA_PROCESSED / "v1b_panel.parquet"
ARTEFACT_PARQUET = DATA_PROCESSED / "lwc_onesided_artefact_v1.parquet"
ARTEFACT_JSON = DATA_PROCESSED / "lwc_onesided_artefact_v1.json"
SPLIT_DATE = date(2023, 1, 1)
TARGETS = DEFAULT_TAUS


def _train_quantile(scores: np.ndarray, tau: float) -> float:
    """Finite-sample split-CP quantile: rank ceil(τ(n+1)). Same formula as
    `build_lwc_artefact._train_quantile`, so the two artefacts differ only in
    the score they consume."""
    s = np.sort(scores[np.isfinite(scores)])
    if s.size == 0:
        return float("nan")
    k = min(max(int(np.ceil(tau * (s.size + 1))), 1), s.size)
    return float(s[k - 1])


def _fit_c_bump(scores: np.ndarray, q_per_row: np.ndarray, tau: float) -> float:
    """Smallest c on a 1.000–5.000 grid with OOS coverage ≥ τ.

    Grid starts at 1.0, so c can only widen — it repairs under-coverage and
    cannot manufacture a tighter buffer."""
    m = np.isfinite(scores) & np.isfinite(q_per_row)
    s, b = scores[m], q_per_row[m]
    if s.size == 0:
        return float("nan")
    for c in np.arange(1.0, 5.0001, 0.001):
        if float(np.mean(s <= b * c)) >= tau:
            return float(c)
    return 5.0


def main() -> None:
    panel = pd.read_parquet(PANEL)
    panel["fri_ts"] = pd.to_datetime(panel["fri_ts"]).dt.date
    panel = panel.dropna(
        subset=["mon_open", "fri_close", "regime_pub", "factor_ret"]
    ).reset_index(drop=True)
    panel["regime_pub"] = panel["regime_pub"].astype(str)

    panel = add_sigma_hat_sym_ewma(panel, half_life=SIGMA_HAT_HL_WEEKENDS)
    panel["sigma_hat_sym_pre_fri"] = panel[
        f"sigma_hat_sym_ewma_pre_fri_hl{SIGMA_HAT_HL_WEEKENDS}"
    ]
    panel["point"] = panel["fri_close"] * (1.0 + panel["factor_ret"])
    panel["score"] = compute_score_lwc_onesided(panel)
    work = panel[panel["score"].notna()
                 & (panel["sigma_hat_sym_pre_fri"] > 0)].reset_index(drop=True)

    train = work[work["fri_ts"] < SPLIT_DATE]
    oos = work[work["fri_ts"] >= SPLIT_DATE]
    regimes = sorted(work["regime_pub"].unique())
    print(f"rows {len(work):,}  train {len(train):,}  oos {len(oos):,}  "
          f"regimes {regimes}")

    # --- trained per-regime downside quantiles
    qt: dict[str, dict[float, float]] = {}
    for r in regimes:
        sc = train[train["regime_pub"] == r]["score"].to_numpy(float)
        qt[r] = {t: _train_quantile(sc, t) for t in TARGETS}
        print(f"  {r:<16} n_train={sc.size:>5}  "
              + "  ".join(f"q({t})={qt[r][t]:.3f}" for t in TARGETS))

    # --- OOS-fit c(τ)
    oos_cells = oos["regime_pub"].to_numpy()
    oos_scores = oos["score"].to_numpy(float)
    cb: dict[float, float] = {}
    for t in TARGETS:
        q_row = np.array([qt[c][t] for c in oos_cells], dtype=float)
        cb[t] = _fit_c_bump(oos_scores, q_row, t)
        cov = float(np.mean(oos_scores <= q_row * cb[t]))
        print(f"  τ={t:.2f}: c={cb[t]:.4f}  -> OOS downside coverage {cov:.4f}")

    # --- artefact rows
    rows = work[["symbol", "fri_ts", "regime_pub", "fri_close", "point",
                 "sigma_hat_sym_pre_fri"]].copy()
    rows.to_parquet(ARTEFACT_PARQUET, index=False)
    print(f"Wrote {ARTEFACT_PARQUET}  ({len(rows):,} rows)")

    sidecar = {
        "_artefact": "lwc_onesided_v1",
        "_side": "downside_only",
        "_built_at": datetime.now(timezone.utc).isoformat(),
        "_panel": str(PANEL.name),
        "_split_date": str(SPLIT_DATE),
        "_sigma_rule": f"ewma_hl{SIGMA_HAT_HL_WEEKENDS}",
        "_score": "(point - mon_open) / (fri_close * sigma_hat_sym_pre_fri)",
        "_deployed": False,
        "_status": (
            "CHARACTERISED, NOT DEPLOYED. Carries none of the held-out "
            "battery behind lwc_artefact_v1 (no LOSO, no nested temporal "
            "holdout, no forward tape, no simulation study, no Rust parity). "
            "See research/coverage-inversion/rewrite/16_appendix_G.md §G.5."
        ),
        "_delta_shift": (
            "none — the one-sided path has no walk-forward delta schedule "
            "fitted; reusing the two-sided delta would mis-state the claim."
        ),
        "regime_quantile_table": {
            r: {f"{t:.2f}": qt[r][t] for t in TARGETS} for r in regimes
        },
        "c_bump_schedule": {f"{t:.2f}": cb[t] for t in TARGETS},
        "n_train": int(len(train)),
        "n_oos": int(len(oos)),
    }
    ARTEFACT_JSON.write_text(json.dumps(sidecar, indent=2) + "\n")
    print(f"Wrote {ARTEFACT_JSON}")


if __name__ == "__main__":
    main()
