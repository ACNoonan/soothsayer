"""Score one weekend's xStock prediction across four methods, on the same
real reserve parameters.

Phase 1 Week 3 / Step 3 of the real-data Kamino comparator. For each
(symbol, weekend), assembles:

- Kamino reserve config (LTV / liq threshold / heuristic guard rail / oracle
  wiring), from ``data/processed/kamino_xstocks_snapshot_*.json``.
- Friday close + Monday open reference, from yfinance underlier.
- Kamino-actually-served price at Friday close + Monday open. If the Scope
  tape (``data/raw/kamino_scope_tape_*.parquet``) covers the window we use
  it directly; otherwise we fall back to the V5 tape's Chainlink ``cl_tokenized_px``,
  which is what Scope downstream-aggregates anyway, and label the result
  accordingly.
- V5 tape summary across the weekend: min / max / mean of Chainlink
  tokenized + Jupiter mid + Jupiter spread.
- Soothsayer band at τ=0.85 (deployment default) and τ=0.95 (oracle-validation
  comparator). No regime variation in the demo: same τ for every symbol.
- Simple market heuristic: ``[Fri_close ± max(|tokenized_px - Fri_close|)
  over the weekend on V5 tape]``. Free-data baseline. If V5 tape doesn't
  cover the weekend, falls back to ``±2 * stdev(daily_log_returns_30d)``.

Then scores each of the four bands on:

- ``coverage`` — did the realized Monday open land inside [lower, upper]?
- ``half_width_bps`` — half-width as basis points of Friday close.
- ``excess_width_bps`` — half-width minus |realized gap| (positive = over-
  protected; negative = under-protected, missed the move).
- ``decision_at_near_origination`` — under the same reserve params (LTV at
  origination, liquidation threshold), with debt sized to ``LTV =
  liq_threshold − 0.5pp`` (a borrower right above the origination ceiling
  but below liquidation), what does each method's lower bound classify them
  as on Monday?
- ``decision_at_near_liquidation`` — same but with debt sized to ``LTV =
  liq_threshold − 0.05pp`` (a borrower one tick from liquidation under Friday
  pricing).

Output: ``data/processed/weekend_comparison_YYYYMMDD.json`` keyed by Friday
date. Idempotent on re-run.

Run:
    uv run python scripts/score_weekend_comparison.py            # latest completed weekend
    uv run python scripts/score_weekend_comparison.py --friday 2026-04-24
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from glob import glob
from pathlib import Path
from typing import Optional

import pandas as pd

from soothsayer.config import DATA_PROCESSED, DATA_RAW
from soothsayer.oracle import Oracle
from soothsayer.sources.jupiter import XSTOCK_MINTS

# Mapping xStock symbol → underlier ticker for yfinance.
XSTOCK_TO_UNDERLIER = {f"{u}x": u for u in ["SPY", "QQQ", "TSLA", "GOOGL", "AAPL", "NVDA", "MSTR", "HOOD"]}

DEFAULT_TARGET_85 = 0.85
DEFAULT_TARGET_95 = 0.95


@dataclass
class WeekendWindow:
    friday: date
    monday: date

    @property
    def fri_close_ts(self) -> int:
        # Friday 16:00 ET = 20:00 UTC (ignoring DST shifts; close enough for window selection).
        dt = datetime.combine(self.friday, time(20, 0), tzinfo=timezone.utc)
        return int(dt.timestamp())

    @property
    def mon_open_ts(self) -> int:
        # Monday 09:30 ET = 13:30 UTC.
        dt = datetime.combine(self.monday, time(13, 30), tzinfo=timezone.utc)
        return int(dt.timestamp())


def latest_completed_friday(today: Optional[date] = None) -> date:
    """Most recent Friday whose Monday is also in the past (so yfinance has Mon open)."""
    today = today or date.today()
    # Find this week's Friday relative to today.
    # weekday(): Mon=0..Sun=6. Friday=4.
    days_since_friday = (today.weekday() - 4) % 7
    candidate_friday = today - timedelta(days=days_since_friday)
    # The Monday after this Friday must already be in the past for the data to exist.
    candidate_monday = candidate_friday + timedelta(days=3)
    if candidate_monday > today:
        candidate_friday -= timedelta(days=7)
    return candidate_friday


def latest_snapshot() -> dict:
    candidates = sorted(DATA_PROCESSED.glob("kamino_xstocks_snapshot_*.json"))
    if not candidates:
        raise SystemExit("No Kamino snapshot found. Run scripts/snapshot_kamino_xstocks.py.")
    return json.loads(candidates[-1].read_text())


def load_v5_tape(window: WeekendWindow) -> pd.DataFrame:
    """Concat all v5_tape parquets covering the weekend window."""
    frames = []
    for fp in sorted(glob(str(DATA_RAW / "v5_tape_*.parquet"))):
        df = pd.read_parquet(fp)
        # poll_ts is unix int.
        in_window = (df["poll_ts"] >= window.fri_close_ts) & (df["poll_ts"] <= window.mon_open_ts)
        if in_window.any():
            frames.append(df[in_window])
    if not frames:
        return pd.DataFrame(columns=["poll_ts", "symbol", "cl_tokenized_px", "jup_mid"])
    return pd.concat(frames, ignore_index=True)


def load_scope_tape(window: WeekendWindow) -> pd.DataFrame:
    frames = []
    for fp in sorted(glob(str(DATA_RAW / "kamino_scope_tape_*.parquet"))):
        df = pd.read_parquet(fp)
        # poll_ts is iso string here; convert.
        df["poll_unix"] = pd.to_datetime(df["poll_ts"]).astype("int64") // 10**9
        in_window = (df["poll_unix"] >= window.fri_close_ts) & (df["poll_unix"] <= window.mon_open_ts)
        if in_window.any():
            frames.append(df[in_window])
    if not frames:
        return pd.DataFrame(columns=["poll_ts", "poll_unix", "symbol", "scope_price"])
    return pd.concat(frames, ignore_index=True)


def yfinance_close_open(symbols: list[str], friday: date, monday: date) -> dict[str, dict]:
    """Pull Friday close + Monday open per underlier ticker via yfinance.
    Bulk-fetch a 2-week window so the call is single-shot."""
    import yfinance as yf
    tickers = " ".join(symbols)
    # Pull 2 weeks of history to be tolerant of holidays.
    df = yf.download(
        tickers, start=(friday - timedelta(days=10)).isoformat(),
        end=(monday + timedelta(days=2)).isoformat(),
        progress=False, auto_adjust=False, group_by="ticker",
    )
    out: dict[str, dict] = {}
    for sym in symbols:
        try:
            sub = df[sym] if sym in df.columns.get_level_values(0) else df
            # Find the row where the index is the friday and the monday.
            sub.index = pd.to_datetime(sub.index).date
            fri_close = float(sub.loc[friday, "Close"]) if friday in sub.index else None
            mon_open = float(sub.loc[monday, "Open"]) if monday in sub.index else None
            out[sym] = {"fri_close": fri_close, "mon_open": mon_open}
        except Exception as e:  # noqa: BLE001
            out[sym] = {"fri_close": None, "mon_open": None, "yf_err": str(e)}
    return out


def find_nearest_in_tape(tape: pd.DataFrame, ts_unix: int, ts_col: str = "poll_ts",
                         tolerance_secs: int = 1800) -> Optional[pd.Series]:
    """Closest-in-time row to ts_unix within tolerance."""
    if tape.empty:
        return None
    if ts_col not in tape.columns:
        return None
    deltas = (tape[ts_col] - ts_unix).abs()
    idx = deltas.idxmin()
    if deltas.loc[idx] > tolerance_secs:
        return None
    return tape.loc[idx]


def classify(ltv: float, max_ltv_pct: int, liq_threshold_pct: int) -> str:
    max_ltv = max_ltv_pct / 100.0
    liq = liq_threshold_pct / 100.0
    if ltv >= liq:
        return "Liquidate"
    if ltv >= max_ltv:
        return "Caution"
    return "Safe"


def score_band(lower: float, upper: float, fri_close: float, mon_open: float) -> dict:
    point = (lower + upper) / 2
    half_width_abs = (upper - lower) / 2
    half_width_bps = (half_width_abs / fri_close) * 1e4 if fri_close > 0 else None
    realized_gap_bps = ((mon_open - fri_close) / fri_close) * 1e4 if fri_close > 0 else None
    coverage = lower <= mon_open <= upper if mon_open is not None else None
    excess_width_bps = (
        half_width_bps - abs(realized_gap_bps) if (half_width_bps is not None and realized_gap_bps is not None) else None
    )
    return {
        "lower": lower,
        "upper": upper,
        "point": point,
        "half_width_bps": half_width_bps,
        "coverage": coverage,
        "excess_width_bps": excess_width_bps,
    }


def decisions_under_reserve(lower_per_method: dict[str, float], reserve_cfg: dict, fri_close: float,
                            collateral_qty: float = 100.0) -> dict[str, dict[str, str]]:
    """For each method's lower bound, classify a near-origination borrower
    and a near-liquidation borrower."""
    max_ltv_pct = reserve_cfg["loan_to_value_pct"]
    liq_pct = reserve_cfg["liquidation_threshold_pct"]
    # near-origination: target LTV at Friday = (max_ltv - 0.5pp)
    # near-liquidation: target LTV at Friday = (liq - 0.05pp)
    near_origin_ltv = (max_ltv_pct - 0.5) / 100.0
    near_liq_ltv = (liq_pct - 0.05) / 100.0
    debt_origin = near_origin_ltv * fri_close * collateral_qty
    debt_liq = near_liq_ltv * fri_close * collateral_qty
    out: dict[str, dict[str, str]] = {}
    for method, lower in lower_per_method.items():
        if lower is None or lower <= 0:
            out[method] = {"near_origination": "n/a", "near_liquidation": "n/a"}
            continue
        ltv_origin_under_method = debt_origin / (lower * collateral_qty)
        ltv_liq_under_method = debt_liq / (lower * collateral_qty)
        out[method] = {
            "near_origination": classify(ltv_origin_under_method, max_ltv_pct, liq_pct),
            "near_liquidation": classify(ltv_liq_under_method, max_ltv_pct, liq_pct),
            "ltv_origin_under_method": round(ltv_origin_under_method, 4),
            "ltv_liq_under_method": round(ltv_liq_under_method, 4),
        }
    return out


def ltv_gap_breach(reserve_cfg: dict, fri_close: float, mon_open: Optional[float],
                   lower_per_method: dict[str, Optional[float]]) -> dict:
    """The Kamino-shaped question: did the realized Monday move cross the
    liquidation threshold for a borrower originated at max-LTV, and did each
    method's lower bound *predict* that crossing?

    A borrower originated at max-LTV with debt = max_ltv * fri_close * Q gets
    liquidated when collateral price falls to ``breach_price = fri_close *
    max_ltv / liq_threshold``. Below that price the new LTV exceeds the
    liquidation threshold.

    For SPY at LTV=73, liq=75, the breach price is fri_close * 0.9733 — i.e.
    a 2.67% downside move triggers liquidation. That ~2.67% is the "trigger
    drop" we report; it's the actually-deployed Kamino tolerance for a borrower
    at the origination ceiling.

    Per-method classification reduces to whether the method's lower bound is
    at or below the breach price. Combined with whether the realized Monday
    open also breached, we get a 2x2:

      flagged & realized   = matched      (correct warning)
      flagged & ¬realized  = preemptive   (safe-side false positive)
      ¬flagged & realized  = missed       (dangerous false negative)
      ¬flagged & ¬realized = silent_safe  (correct silence)

    Aggregating ``matched`` and ``missed`` rates across many weekends is the
    welfare-relevant comparison for a Kamino-shaped consumer; this function
    produces the per-(symbol, weekend) inputs to that aggregation.
    """
    max_ltv = reserve_cfg["loan_to_value_pct"] / 100.0
    liq = reserve_cfg["liquidation_threshold_pct"] / 100.0
    breach_price = fri_close * max_ltv / liq
    trigger_drop_bps = (breach_price - fri_close) / fri_close * 1e4  # negative
    realized_gap_bps = ((mon_open - fri_close) / fri_close) * 1e4 if mon_open is not None else None
    realized_breach = (mon_open is not None) and (mon_open <= breach_price)

    out: dict = {
        "max_ltv_pct": reserve_cfg["loan_to_value_pct"],
        "liq_threshold_pct": reserve_cfg["liquidation_threshold_pct"],
        "ltv_gap_pp": reserve_cfg["liquidation_threshold_pct"] - reserve_cfg["loan_to_value_pct"],
        "breach_price": breach_price,
        "trigger_drop_bps": trigger_drop_bps,
        "realized_gap_bps": realized_gap_bps,
        "realized_breach": realized_breach,
        "methods": {},
    }
    for method, lower in lower_per_method.items():
        if lower is None or lower <= 0:
            out["methods"][method] = {"classification": "n/a"}
            continue
        flagged = lower <= breach_price
        if flagged and realized_breach:
            cls = "matched"
        elif flagged and not realized_breach:
            cls = "preemptive"
        elif (not flagged) and realized_breach:
            cls = "missed"
        else:
            cls = "silent_safe"
        out["methods"][method] = {
            "lower": lower,
            "lower_distance_bps": (lower - fri_close) / fri_close * 1e4,
            "flagged_breach": flagged,
            "classification": cls,
        }
    return out


def compute_simple_heuristic(fri_close: float, v5: pd.DataFrame) -> dict:
    """±max(|cl_tokenized_px - Fri_close|) observed over the weekend.
    Falls back to ±0.0 if V5 tape didn't cover."""
    if v5.empty or "cl_tokenized_px" not in v5.columns:
        return {"lower": fri_close, "upper": fri_close, "method": "no_tape_fallback"}
    series = v5["cl_tokenized_px"].dropna()
    if series.empty:
        return {"lower": fri_close, "upper": fri_close, "method": "empty_tape"}
    max_dev = (series - fri_close).abs().max()
    return {
        "lower": fri_close - max_dev,
        "upper": fri_close + max_dev,
        "method": "v5_tokenized_px_max_dev",
        "max_dev_abs": float(max_dev),
        "n_obs": int(len(series)),
    }


def kamino_incumbent_band(reserve_cfg: dict, fri_close: float, scope_friday_price: Optional[float],
                          scope_monday_price: Optional[float]) -> dict:
    """Construct the closest-faithful incumbent 'band' from real reserve params.

    Kamino doesn't publish a coverage band per se. They consume a point price
    from Scope and apply LTV-vs-liquidation-threshold thresholds. The most
    honest reconstruction we can offer that the spec asks for:

    Lower bound: the Scope-served price at Monday open (or Friday close if
    Monday isn't in tape). This is what Kamino actually consumes for LTV.
    There is no symmetric 'upper'; we record the price directly and treat
    band = [point - guard_rail_floor, point + guard_rail_ceiling] using the
    PriceHeuristic guard rail as a *validity bound*, NOT a coverage claim.
    """
    heuristic = reserve_cfg["token_info"]["heuristic"]
    point = scope_monday_price or scope_friday_price or fri_close
    return {
        "lower": heuristic["lower_price"],
        "upper": heuristic["upper_price"],
        "point": point,
        "label": "reconstructed_from_PriceHeuristic_guard_rail",
        "scope_friday_price": scope_friday_price,
        "scope_monday_price": scope_monday_price,
        "note": "Kamino's PriceHeuristic is a validity guard rail, not a coverage band. "
                "Scope-served point is the actually-consumed value.",
    }


def score_weekend(friday: date, monday: date, snapshot: dict, oracle: Oracle) -> dict:
    window = WeekendWindow(friday=friday, monday=monday)
    print(f"\nScoring weekend {friday} → {monday}")
    print(f"  V5 tape window: [{window.fri_close_ts}, {window.mon_open_ts}]")

    v5_tape = load_v5_tape(window)
    scope_tape = load_scope_tape(window)
    print(f"  V5 tape rows in window: {len(v5_tape)}; Scope tape rows: {len(scope_tape)}")

    underlier_symbols = list(XSTOCK_TO_UNDERLIER.values())
    yf = yfinance_close_open(underlier_symbols, friday, monday)
    print(f"  yfinance pulls: {sum(1 for v in yf.values() if v.get('fri_close'))}/{len(yf)} fri_close, "
          f"{sum(1 for v in yf.values() if v.get('mon_open'))}/{len(yf)} mon_open")

    rows: list[dict] = []
    for r in snapshot["reserves"]:
        x_sym = r["symbol"]
        underlier = XSTOCK_TO_UNDERLIER.get(x_sym)
        if not underlier or underlier not in yf:
            continue
        yfv = yf[underlier]
        fri_close = yfv.get("fri_close")
        mon_open = yfv.get("mon_open")
        if fri_close is None or mon_open is None:
            print(f"  [{x_sym}] missing yfinance fri/mon — skip")
            continue

        sym_v5 = v5_tape[v5_tape["symbol"] == x_sym] if not v5_tape.empty else v5_tape
        sym_scope = scope_tape[scope_tape["symbol"] == x_sym] if not scope_tape.empty else scope_tape

        scope_fri = find_nearest_in_tape(sym_scope, window.fri_close_ts, "poll_unix")
        scope_mon = find_nearest_in_tape(sym_scope, window.mon_open_ts, "poll_unix")
        scope_fri_px = float(scope_fri["scope_price"]) if scope_fri is not None else None
        scope_mon_px = float(scope_mon["scope_price"]) if scope_mon is not None else None

        try:
            soothsayer_85 = oracle.fair_value(symbol=underlier, as_of=friday, target_coverage=DEFAULT_TARGET_85)
            soothsayer_95 = oracle.fair_value(symbol=underlier, as_of=friday, target_coverage=DEFAULT_TARGET_95)
        except Exception as e:  # noqa: BLE001
            print(f"  [{x_sym}] Oracle.fair_value failed: {e}")
            continue

        incumbent = kamino_incumbent_band(r, fri_close, scope_fri_px, scope_mon_px)
        heuristic = compute_simple_heuristic(fri_close, sym_v5)
        s85 = {"lower": soothsayer_85.lower, "upper": soothsayer_85.upper}
        s95 = {"lower": soothsayer_95.lower, "upper": soothsayer_95.upper}

        bands = {
            "kamino_incumbent": score_band(incumbent["lower"], incumbent["upper"], fri_close, mon_open),
            "soothsayer_t085": score_band(s85["lower"], s85["upper"], fri_close, mon_open),
            "soothsayer_t095": score_band(s95["lower"], s95["upper"], fri_close, mon_open),
            "simple_heuristic": score_band(heuristic["lower"], heuristic["upper"], fri_close, mon_open),
        }
        bands["kamino_incumbent"]["band_label"] = incumbent["label"]
        bands["kamino_incumbent"]["scope_friday_price"] = incumbent["scope_friday_price"]
        bands["kamino_incumbent"]["scope_monday_price"] = incumbent["scope_monday_price"]
        bands["simple_heuristic"]["method"] = heuristic.get("method")

        # Decision classification: use each method's *lower bound* as the conservative collateral price.
        # For incumbent, the conservative-protocol view is the Scope-served price at Monday open (NOT
        # the heuristic guard rail), because that is what the protocol actually consumes for LTV.
        kamino_lower_for_decision = scope_mon_px if scope_mon_px is not None else fri_close
        method_lowers = {
            "kamino_incumbent": kamino_lower_for_decision,
            "soothsayer_t085": s85["lower"],
            "soothsayer_t095": s95["lower"],
            "simple_heuristic": heuristic["lower"],
        }
        decisions = decisions_under_reserve(
            lower_per_method=method_lowers,
            reserve_cfg=r["config"],
            fri_close=fri_close,
        )

        # The Kamino-shaped question: did the realized move cross the
        # liquidation threshold for a max-LTV borrower, and did each method
        # warn? See ltv_gap_breach() for the 2x2 classification.
        breach = ltv_gap_breach(
            reserve_cfg=r["config"],
            fri_close=fri_close,
            mon_open=mon_open,
            lower_per_method=method_lowers,
        )

        rows.append({
            "symbol": x_sym,
            "underlier": underlier,
            "reserve_pda": r["reserve_pda"],
            "lending_market": r["lending_market"],
            "reserve_config": {
                "loan_to_value_pct": r["config"]["loan_to_value_pct"],
                "liquidation_threshold_pct": r["config"]["liquidation_threshold_pct"],
                "borrow_factor_pct": r["config"]["borrow_factor_pct"],
                "max_age_price_seconds": r["token_info"]["max_age_price_seconds"],
            },
            "fri_close": fri_close,
            "mon_open": mon_open,
            "realized_gap_bps": ((mon_open - fri_close) / fri_close) * 1e4,
            "v5_tape_n_obs": int(len(sym_v5)),
            "scope_tape_n_obs": int(len(sym_scope)),
            "scope_friday_price": scope_fri_px,
            "scope_monday_price": scope_mon_px,
            "bands": bands,
            "decisions": decisions,
            "ltv_gap_breach": breach,
        })
        # Compact stdout summary.
        rgap = ((mon_open - fri_close) / fri_close) * 1e4
        cov_summary = " ".join(
            f"{m[:8]}={'✓' if b.get('coverage') else '✗' if b.get('coverage') is False else '?'}"
            for m, b in bands.items()
        )
        breach_marker = "🔴 BREACH" if breach["realized_breach"] else "—"
        print(f"  [{x_sym:7s}] Fri ${fri_close:>7.2f}  Mon ${mon_open:>7.2f}  "
              f"realized {rgap:+7.1f} bps  trigger {breach['trigger_drop_bps']:+7.1f} bps  "
              f"{breach_marker}   {cov_summary}")

    out = {
        "friday": friday.isoformat(),
        "monday": monday.isoformat(),
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_used": snapshot["snapshot_date"],
        "n_symbols": len(rows),
        "rows": rows,
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--friday", type=str, default=None,
                    help="Friday of the weekend to score (YYYY-MM-DD); default: latest completed weekend")
    args = ap.parse_args()

    if args.friday:
        friday = date.fromisoformat(args.friday)
    else:
        friday = latest_completed_friday()
    monday = friday + timedelta(days=3)

    snapshot = latest_snapshot()
    oracle = Oracle.load()

    result = score_weekend(friday, monday, snapshot, oracle)

    out_path = DATA_PROCESSED / f"weekend_comparison_{friday.strftime('%Y%m%d')}.json"
    out_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"\nWrote {result['n_symbols']} symbols → {out_path}")


if __name__ == "__main__":
    main()
