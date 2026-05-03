"""
Soothsayer Oracle — serving-time API (M5 + M6b2 Lending dual-profile).

Consumers call `Oracle.fair_value(symbol, as_of, target_coverage)` and receive
a calibrated price band: a point estimate and lower/upper bounds whose
empirical coverage matches the target. Two profiles share the M5 architecture
and wire format and differ only in the conformal cell axis:

  profile="amm"      (M5)   — Mondrian by regime          (3 cells × 4 τ)
  profile="lending"  (M6b2) — Mondrian by symbol_class    (6 cells × 4 τ)

Common pipeline (both profiles):

  point = fri_close * (1 + factor_ret)                  # §7.4 factor switchboard
  tau'  = tau + delta_shift_schedule(tau)               # walk-forward conservatism
  q     = c_bump_schedule(tau') * b_cell(tau')          # cell axis differs by profile

AMM band (legacy formula relative to point — kept for byte-for-byte M5 parity):
  lower = point * (1 - q),  upper = point * (1 + q)

Lending band (relative to fri_close — exact match to the conformity score
   |mon_open - point| / fri_close used to calibrate b):
  lower = point - q * fri_close,  upper = point + q * fri_close

Per-profile constant budgets:
  AMM       — REGIME_QUANTILE_TABLE   (3×4 = 12) + C_BUMP_SCHEDULE (4) +
              DELTA_SHIFT_SCHEDULE (4)                = 20 scalars
  Lending   — LENDING_QUANTILE_TABLE  (6×4 = 24) + LENDING_C_BUMP_SCHEDULE (4) +
              LENDING_DELTA_SHIFT_SCHEDULE (4)        = 32 scalars

AMM constants are hardcoded literals (legacy M5 deployment). Lending constants
are loaded from the artefact JSON sidecar at module import — that file is the
single source of truth produced by `scripts/build_m6b2_lending_artefact.py`.

Per-Friday lookup parquet (shared, both profiles):
  `data/processed/mondrian_artefact_v2.parquet`
Lending audit-trail sidecar (24 + 4 + 4 scalars + symbol_class mapping):
  `data/processed/m6b2_lending_artefact_v1.json`

Reference: paper 1 §7.7, `reports/methodology_history.md` (M5 + 2026-05-03
dual-profile entries), `M6_REFACTOR.md` Phase A2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal, Optional

import pandas as pd

from .config import DATA_PROCESSED
from .universe import symbol_class_for


ARTEFACT_PATH = DATA_PROCESSED / "mondrian_artefact_v2.parquet"
LENDING_SIDECAR_PATH = DATA_PROCESSED / "m6b2_lending_artefact_v1.json"

Profile = Literal["lending", "amm"]
DEFAULT_PROFILE: Profile = "lending"

# Mondrian receipt label exposed in PricePoint.forecaster_used and the on-chain
# PriceUpdate.forecaster_code (FORECASTER_MONDRIAN = 2 in the consumer SDK).
# Both profiles emit the same forecaster receipt; the on-chain `profile_code`
# byte (Phase A4) carries the lending-vs-amm distinction.
MONDRIAN_FORECASTER = "mondrian"


# Per-(regime, τ) trained quantile from the pre-2023 calibration set
# (split date 2023-01-01). See `scripts/build_mondrian_artefact.py` step 1
# for the fit; values match `reports/tables/v1b_mondrian_calibration.csv`
# (method=M2_mondrian_fa, since M5 reuses the M2 fit and adds the OOS bump).
REGIME_QUANTILE_TABLE: dict[str, dict[float, float]] = {
    "normal": {
        0.68: 0.006070,
        0.85: 0.011236,
        0.95: 0.021530,
        0.99: 0.049663,
    },
    "long_weekend": {
        0.68: 0.006648,
        0.85: 0.014248,
        0.95: 0.031032,
        0.99: 0.071228,
    },
    "high_vol": {
        0.68: 0.011628,
        0.85: 0.021460,
        0.95: 0.042911,
        0.99: 0.099418,
    },
}

# OOS-fit multiplicative bump on the trained quantile (the M5 analogue of v1's
# BUFFER_BY_TARGET). One scalar per τ-anchor; off-grid τ linearly interpolated.
# See `reports/tables/v1b_mondrian_calibration.csv` (M5_mondrian_deployable
# rows, bump_c column).
C_BUMP_SCHEDULE: dict[float, float] = {
    0.68: 1.498,
    0.85: 1.455,
    0.95: 1.300,
    0.99: 1.076,
}

# Walk-forward-fit τ-shift schedule. Serves c(τ + δ) · q_r(τ + δ) instead of
# c(τ) · q_r(τ); pushes per-split realised coverage above nominal so the
# deployed schedule is conservative, not centred (see §7.7.4 / sweep table
# `reports/tables/v1b_mondrian_delta_sweep.csv`).
DELTA_SHIFT_SCHEDULE: dict[float, float] = {
    0.68: 0.05,
    0.85: 0.02,
    0.95: 0.00,
    0.99: 0.00,
}

# Default consumer target. Held over from v1 — protocol-policy work consumes
# τ=0.85 as a moderately conservative Schelling point (see paper 3 plan §13).
DEFAULT_TARGET_COVERAGE: float = 0.85
# Top of the τ schedule. Serving requests above this clip to the τ=0.99 row
# of the schedule; finite-sample tail discussion in §9.1.
MAX_SERVED_TARGET: float = 0.99
# Bottom of the τ schedule. Below this we clip to the τ=0.68 row.
MIN_SERVED_TARGET: float = 0.68


def _interp_schedule(tau: float, schedule: dict[float, float]) -> float:
    """Linearly interpolate a τ-keyed schedule. Targets at or below the
    smallest anchor return the smallest anchor's value; targets at or above
    the largest anchor return the largest anchor's value."""
    anchors = sorted(schedule.keys())
    if tau <= anchors[0]:
        return float(schedule[anchors[0]])
    if tau >= anchors[-1]:
        return float(schedule[anchors[-1]])
    for i in range(len(anchors) - 1):
        lo, hi = anchors[i], anchors[i + 1]
        if lo <= tau <= hi:
            frac = (tau - lo) / (hi - lo)
            return float(schedule[lo] + frac * (schedule[hi] - schedule[lo]))
    return float(schedule[anchors[-1]])


def delta_shift_for_target(tau: float) -> float:
    return _interp_schedule(tau, DELTA_SHIFT_SCHEDULE)


def c_bump_for_target(tau: float) -> float:
    return _interp_schedule(tau, C_BUMP_SCHEDULE)


def regime_quantile_for(regime: str, tau: float) -> float:
    """Linearly interpolate the per-regime quantile row at τ. Unknown regimes
    fall back to `high_vol` (the conservative widest-quantile row)."""
    row = REGIME_QUANTILE_TABLE.get(regime, REGIME_QUANTILE_TABLE["high_vol"])
    return _interp_schedule(tau, row)


# --- Lending profile (M6b2) constants ---------------------------------------
# Loaded from `data/processed/m6b2_lending_artefact_v1.json` at module import.
# That file is the single source of truth, written by
# `scripts/build_m6b2_lending_artefact.py`. The 24 + 4 + 4 scalars duplicate
# the audit-trail sidecar; the runtime serve is the same 5-line lookup as M5.

LENDING_QUANTILE_TABLE: dict[str, dict[float, float]] = {}
LENDING_C_BUMP_SCHEDULE: dict[float, float] = {}
LENDING_DELTA_SHIFT_SCHEDULE: dict[float, float] = {}
LENDING_METADATA: dict = {}


def _load_lending_constants(path: Path = LENDING_SIDECAR_PATH) -> None:
    """Populate the LENDING_* tables from the artefact JSON sidecar.

    Called once at module import. Re-callable by tests / the build script if
    they need to reload after regenerating the sidecar."""
    global LENDING_QUANTILE_TABLE, LENDING_C_BUMP_SCHEDULE
    global LENDING_DELTA_SHIFT_SCHEDULE, LENDING_METADATA
    if not path.exists():
        LENDING_QUANTILE_TABLE = {}
        LENDING_C_BUMP_SCHEDULE = {}
        LENDING_DELTA_SHIFT_SCHEDULE = {}
        LENDING_METADATA = {}
        return
    sidecar = json.loads(path.read_text())
    LENDING_QUANTILE_TABLE = {
        cls: {float(tau): float(b) for tau, b in row.items()}
        for cls, row in sidecar["class_quantile_table"].items()
    }
    LENDING_C_BUMP_SCHEDULE = {
        float(tau): float(c) for tau, c in sidecar["c_bump_schedule"].items()
    }
    LENDING_DELTA_SHIFT_SCHEDULE = {
        float(tau): float(d) for tau, d in sidecar["delta_shift_schedule"].items()
    }
    LENDING_METADATA = {
        "_schema_version": sidecar.get("_schema_version"),
        "_fetched_at": sidecar.get("_fetched_at"),
        "_source": sidecar.get("_source"),
        "methodology_version": sidecar.get("methodology_version"),
        "split_date": sidecar.get("split_date"),
        "n_train_per_class": sidecar.get("n_train_per_class", {}),
    }


_load_lending_constants()


def lending_delta_shift_for(tau: float) -> float:
    return _interp_schedule(tau, LENDING_DELTA_SHIFT_SCHEDULE)


def lending_c_bump_for(tau: float) -> float:
    return _interp_schedule(tau, LENDING_C_BUMP_SCHEDULE)


def lending_class_quantile_for(symbol_class: str, tau: float) -> float:
    """Linearly interpolate the per-class quantile row at τ. Raises if
    `symbol_class` is unknown — there is no implicit fallback class
    (unlike the AMM profile's `high_vol` regime fallback) because the
    lending profile only covers symbols listed in the artefact mapping."""
    row = LENDING_QUANTILE_TABLE.get(symbol_class)
    if row is None:
        known = sorted(LENDING_QUANTILE_TABLE.keys())
        raise KeyError(
            f"Unknown symbol_class '{symbol_class}' for lending profile. "
            f"Known classes: {known}"
        )
    return _interp_schedule(tau, row)


@dataclass(frozen=True)
class PricePoint:
    """The Soothsayer oracle read. Stable fields are what protocols integrate
    against; `diagnostics` is human-consumable metadata.

    Field semantics under M5:
      - `target_coverage`: what the consumer asked for (τ).
      - `calibration_buffer_applied`: δ(τ) — the OOS-fit τ-shift, the
        structural successor to v1's `BUFFER_BY_TARGET` schedule.
      - `claimed_coverage_served`: τ + δ(τ), the served band's claim.
      - `forecaster_used`: always "mondrian" under M5 (legacy field; on the
        wire this maps to FORECASTER_MONDRIAN = 2).
    """

    symbol: str
    as_of: date
    target_coverage: float
    calibration_buffer_applied: float  # δ(τ) — OOS-fit shift on serving target
    claimed_coverage_served: float  # τ + δ(τ)
    point: float
    lower: float
    upper: float
    regime: str
    forecaster_used: str
    sharpness_bps: float
    profile: str = DEFAULT_PROFILE
    diagnostics: dict = field(default_factory=dict)

    @property
    def half_width_bps(self) -> float:
        if self.point == 0:
            return 0.0
        return (self.upper - self.lower) / 2 / self.point * 1e4

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of": str(self.as_of),
            "target_coverage": self.target_coverage,
            "calibration_buffer_applied": self.calibration_buffer_applied,
            "claimed_coverage_served": self.claimed_coverage_served,
            "point": self.point,
            "lower": self.lower,
            "upper": self.upper,
            "regime": self.regime,
            "forecaster_used": self.forecaster_used,
            "sharpness_bps": self.sharpness_bps,
            "half_width_bps": self.half_width_bps,
            "profile": self.profile,
            "diagnostics": self.diagnostics,
        }


class Oracle:
    """Serving-time Oracle — dual-profile Mondrian split-conformal.

    `profile="lending"` (default, M6b2) cells along the symbol_class axis.
    `profile="amm"` (M5) cells along the regime axis. Same per-Friday parquet
    backs both; only the conformal lookup differs."""

    def __init__(
        self,
        artefact: pd.DataFrame,
        profile: Profile = DEFAULT_PROFILE,
    ):
        if profile not in ("lending", "amm"):
            raise ValueError(
                f"profile must be 'lending' or 'amm', got {profile!r}"
            )
        if profile == "lending" and not LENDING_QUANTILE_TABLE:
            raise RuntimeError(
                f"Lending profile requested but {LENDING_SIDECAR_PATH} not "
                "loaded. Run `uv run python scripts/build_m6b2_lending_artefact.py` "
                "first to materialise the M6b2 sidecar."
            )
        self._artefact = artefact
        self._profile: Profile = profile

    @property
    def profile(self) -> Profile:
        return self._profile

    @classmethod
    def load(
        cls,
        artefact_path: Path | str = ARTEFACT_PATH,
        profile: Profile = DEFAULT_PROFILE,
    ) -> "Oracle":
        artefact = pd.read_parquet(artefact_path)
        # Normalise fri_ts to datetime.date so equality checks against
        # consumer-supplied dates work regardless of upstream pandas dtype.
        artefact["fri_ts"] = pd.to_datetime(artefact["fri_ts"]).dt.date
        return cls(artefact=artefact, profile=profile)

    def list_available(self, symbol: Optional[str] = None) -> pd.DataFrame:
        cols = ["symbol", "fri_ts", "regime_pub"]
        df = self._artefact[cols].drop_duplicates()
        if symbol is not None:
            df = df[df["symbol"] == symbol]
        return df.sort_values(["symbol", "fri_ts"]).reset_index(drop=True)

    def fair_value(
        self,
        symbol: str,
        as_of: date | str,
        target_coverage: float = DEFAULT_TARGET_COVERAGE,
    ) -> PricePoint:
        """Serve a calibrated price band.

        At consumer τ, looks up the per-Friday point and regime, applies
        the δ-shift schedule + c(τ) bump + per-cell quantile, returns
        symmetric bounds around the factor-adjusted point. The cell axis
        depends on `self.profile` — symbol_class for "lending", regime for
        "amm" — but everything else is shared."""
        if isinstance(as_of, str):
            as_of = pd.to_datetime(as_of).date()

        rows = self._artefact[
            (self._artefact["symbol"] == symbol)
            & (self._artefact["fri_ts"] == as_of)
        ]
        if rows.empty:
            raise ValueError(
                f"No artefact row for symbol={symbol} as_of={as_of}. "
                "Call list_available() to see what's supported."
            )

        row = rows.iloc[0]
        regime = str(row["regime_pub"])
        fri_close = float(row["fri_close"])
        point = float(row["point"])

        tau_clipped = max(min(target_coverage, MAX_SERVED_TARGET), MIN_SERVED_TARGET)

        if self._profile == "lending":
            delta = lending_delta_shift_for(tau_clipped)
            served_target = min(tau_clipped + delta, MAX_SERVED_TARGET)
            c_bump = lending_c_bump_for(served_target)
            cls_label = symbol_class_for(symbol)
            if cls_label is None:
                raise ValueError(
                    f"Lending profile: symbol {symbol!r} has no symbol_class "
                    f"in the artefact mapping. Known mapping: "
                    f"{sorted(LENDING_QUANTILE_TABLE.keys())}"
                )
            b = lending_class_quantile_for(cls_label, served_target)
            q_eff = c_bump * b
            # Band relative to fri_close — exact match to the conformity score
            # |mon_open - point| / fri_close used to fit b.
            lower = point - q_eff * fri_close
            upper = point + q_eff * fri_close
            cell_diag = {"symbol_class": cls_label, "b_class": b}
        else:  # profile == "amm"
            delta = delta_shift_for_target(tau_clipped)
            served_target = min(tau_clipped + delta, MAX_SERVED_TARGET)
            c_bump = c_bump_for_target(served_target)
            q_regime = regime_quantile_for(regime, served_target)
            q_eff = c_bump * q_regime
            # Legacy M5 formula — band relative to point. Kept for byte-for-byte
            # parity with the deployed M5 wire receipts.
            lower = point * (1.0 - q_eff)
            upper = point * (1.0 + q_eff)
            cell_diag = {"q_regime": q_regime}

        sharpness_bps = (upper - lower) / 2 / fri_close * 1e4 if fri_close else 0.0

        diagnostics = {
            "fri_close": fri_close,
            "served_target": served_target,
            "c_bump": c_bump,
            "q_eff": q_eff,
        }
        diagnostics.update(cell_diag)

        return PricePoint(
            symbol=symbol,
            as_of=as_of,
            target_coverage=float(target_coverage),
            calibration_buffer_applied=float(delta),
            claimed_coverage_served=float(served_target),
            point=point,
            lower=lower,
            upper=upper,
            regime=regime,
            forecaster_used=MONDRIAN_FORECASTER,
            sharpness_bps=sharpness_bps,
            profile=self._profile,
            diagnostics=diagnostics,
        )
