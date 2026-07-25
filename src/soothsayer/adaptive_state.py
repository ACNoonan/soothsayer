"""
Checkpointed adaptive cell state — the overnight serving profile (W15).

The two-sided weekend band is a pure function of a frozen, SHA-stamped
artefact: a consumer downloads one file and re-derives any read in one step.
That property is the product (§3). The overnight profile adds an adaptive
per-cell level (W15), which changes the signature:

    band     = f(artefact, tau, symbol, as_of, m[tau][cell])
    m[tau][r] = g(m_0, every realised outcome in cell r up to t)

`m` is a single scalar per (tau, cell) — three or four numbers per tau —
under a deterministic update over *public prices*. So the band stays
verifiable. What it loses without further work is (a) one-step verification,
because reconstructing `m` means replaying from inception, and (b) the
pre-commitment property, because the provider recomputes `m` each period
rather than having published it in advance.

Checkpoints restore both. A checkpoint is a hashed snapshot of the state at
a stated period. With one published:

  * verify one read      — O(1) against the `m` in the receipt
  * audit the state      — replay only since the last checkpoint
  * detect a deviating provider — recompute the checkpoint from public
    prices and compare hashes

`replay()` is the single source of truth for the update, used by the builder
and by any third-party verifier, so "what the provider did" and "what an
auditor recomputes" cannot drift apart by construction.

See `reports/active/adaptive_state_wire_design.md` for the decision record
and `reports/active/w15_hybrid_adaptive_cells.md` for the empirical result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

# Deployed W15 constants. Changing any of these changes every downstream
# checkpoint hash, which is intended — the hash pins the rule, not just the
# numbers.
GAMMA: float = 0.05
M_FLOOR: float = 0.25
M_CEIL: float = 4.0
STATE_SCHEMA: str = "soothsayer.adaptive_state.v1"


@dataclass(frozen=True)
class Checkpoint:
    """A hashed snapshot of adaptive state at `through_period`.

    `m[tau][cell]` is the multiplier to apply to the frozen per-cell
    quantile when serving any period *after* `through_period`.
    """

    schema: str
    profile: str
    artefact_sha256: str
    through_period: date
    gamma: float
    m_floor: float
    m_ceil: float
    n_periods_replayed: int
    m: dict[float, dict[str, float]]
    checkpoint_sha256: str = ""

    def canonical(self) -> str:
        """Deterministic serialisation — the pre-image of the hash.

        Sorted keys and fixed float formatting, so the hash depends on the
        state and not on dict ordering or platform repr."""
        body = {
            "schema": self.schema,
            "profile": self.profile,
            "artefact_sha256": self.artefact_sha256,
            "through_period": str(self.through_period),
            "gamma": f"{self.gamma:.10f}",
            "m_floor": f"{self.m_floor:.10f}",
            "m_ceil": f"{self.m_ceil:.10f}",
            "n_periods_replayed": self.n_periods_replayed,
            "m": {
                f"{tau:.4f}": {c: f"{v:.10f}" for c, v in sorted(row.items())}
                for tau, row in sorted(self.m.items())
            },
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"))

    def compute_sha256(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()

    def sealed(self) -> "Checkpoint":
        """Return a copy carrying its own hash."""
        return Checkpoint(**{**self.__dict__,
                             "checkpoint_sha256": self.compute_sha256()})

    def verify_self(self) -> bool:
        """True if the stored hash matches the state it claims to cover."""
        return bool(self.checkpoint_sha256) and (
            self.checkpoint_sha256 == self.compute_sha256()
        )

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["through_period"] = str(self.through_period)
        d["m"] = {f"{t:.4f}": {c: float(v) for c, v in r.items()}
                  for t, r in self.m.items()}
        return d

    @classmethod
    def from_dict(cls, d: Mapping) -> "Checkpoint":
        return cls(
            schema=d["schema"], profile=d["profile"],
            artefact_sha256=d["artefact_sha256"],
            through_period=pd.to_datetime(d["through_period"]).date(),
            gamma=float(d["gamma"]), m_floor=float(d["m_floor"]),
            m_ceil=float(d["m_ceil"]),
            n_periods_replayed=int(d["n_periods_replayed"]),
            m={float(t): {c: float(v) for c, v in r.items()}
               for t, r in d["m"].items()},
            checkpoint_sha256=d.get("checkpoint_sha256", ""),
        )


def _advance_cell(m: float, breach_rate: float, tau: float,
                  gamma: float, floor: float, ceil: float) -> float:
    """One W15 update step: m <- clip(m * exp(gamma*(err - (1-tau)))).

    Too many breaches raises m (wider); too few lowers it. Clipped so a
    single pathological period cannot destroy the band."""
    return float(np.clip(
        m * np.exp(gamma * (breach_rate - (1.0 - tau))), floor, ceil
    ))


def replay(
    panel: pd.DataFrame,
    quantile_table: Mapping[str, Mapping[float, float]],
    taus: Sequence[float],
    *,
    profile: str,
    artefact_sha256: str,
    through_period: date | None = None,
    start_state: Mapping[float, Mapping[str, float]] | None = None,
    gamma: float = GAMMA,
    m_floor: float = M_FLOOR,
    m_ceil: float = M_CEIL,
    period_col: str = "fri_ts",
    cell_col: str = "regime_pub",
) -> Checkpoint:
    """Replay the adaptive state over `panel`, in period order.

    THE single definition of the update, run identically by the publisher
    and by any third-party auditor. `panel` must carry `point`,
    `fri_close`, `sigma_hat_sym_pre_fri`, `mon_open`, the period column and
    the cell column — all reconstructible from public data.

    `start_state` resumes from a prior checkpoint's `m`; omit it to start
    from 1.0 everywhere (inception). Rows on or before a resumed
    checkpoint's period must be excluded by the caller — this function
    replays every row it is given.
    """
    need = {"point", "fri_close", "sigma_hat_sym_pre_fri", "mon_open",
            period_col, cell_col}
    missing = need - set(panel.columns)
    if missing:
        raise ValueError(f"panel missing required columns: {sorted(missing)}")

    df = panel.dropna(subset=["point", "fri_close", "sigma_hat_sym_pre_fri",
                              "mon_open"]).sort_values([period_col])
    if through_period is not None:
        df = df[df[period_col] <= through_period]
    cells = sorted(set(df[cell_col].astype(str)) | set(quantile_table))

    m: dict[float, dict[str, float]] = {
        float(t): {c: float((start_state or {}).get(t, {}).get(c, 1.0))
                   for c in cells}
        for t in taus
    }

    periods = sorted(set(df[period_col]))
    for p in periods:
        rows = df[df[period_col] == p]
        cc = rows[cell_col].astype(str).to_numpy()
        pt = rows["point"].to_numpy(float)
        fc = rows["fri_close"].to_numpy(float)
        sg = rows["sigma_hat_sym_pre_fri"].to_numpy(float)
        ac = rows["mon_open"].to_numpy(float)
        for tau in taus:
            tau = float(tau)
            q = np.array([quantile_table.get(c, {}).get(tau, np.nan)
                          for c in cc], dtype=float)
            mm = np.array([m[tau][c] for c in cc], dtype=float)
            hw = mm * q * sg * fc
            breach = (ac < pt - hw) | (ac > pt + hw)
            for c in np.unique(cc):
                sel = cc == c
                if not np.isfinite(hw[sel]).any():
                    continue
                m[tau][c] = _advance_cell(
                    m[tau][c], float(breach[sel].mean()), tau,
                    gamma, m_floor, m_ceil)

    return Checkpoint(
        schema=STATE_SCHEMA, profile=profile,
        artefact_sha256=artefact_sha256,
        through_period=(through_period if through_period is not None
                        else (periods[-1] if periods else date(1970, 1, 1))),
        gamma=gamma, m_floor=m_floor, m_ceil=m_ceil,
        n_periods_replayed=len(periods), m=m,
    ).sealed()


def verify_checkpoint(
    checkpoint: Checkpoint,
    panel: pd.DataFrame,
    quantile_table: Mapping[str, Mapping[float, float]],
    **kwargs,
) -> tuple[bool, Checkpoint]:
    """Recompute a checkpoint from public data and compare hashes.

    Returns `(matches, recomputed)`. A False here means the published state
    is not what the published rule produces on the published inputs — i.e.
    the provider deviated, or the inputs moved. This is the check that
    restores the pre-commitment property a frozen artefact has natively."""
    if not checkpoint.verify_self():
        return False, checkpoint
    recomputed = replay(
        panel, quantile_table, sorted(checkpoint.m),
        profile=checkpoint.profile,
        artefact_sha256=checkpoint.artefact_sha256,
        through_period=checkpoint.through_period,
        gamma=checkpoint.gamma, m_floor=checkpoint.m_floor,
        m_ceil=checkpoint.m_ceil, **kwargs,
    )
    return (recomputed.checkpoint_sha256 == checkpoint.checkpoint_sha256,
            recomputed)


def multiplier_for(checkpoint: Checkpoint, cell: str, tau: float) -> float:
    """Serving-time lookup. Unknown cell falls back to 1.0 — a cell with no
    accumulated state serves the frozen quantile unmodified, which is the
    conservative reading."""
    row = checkpoint.m.get(float(tau))
    if row is None:                       # exact-tau only; no interpolation
        raise KeyError(
            f"checkpoint carries no state for tau={tau}; served anchors are "
            f"{sorted(checkpoint.m)}"
        )
    return float(row.get(cell, 1.0))
