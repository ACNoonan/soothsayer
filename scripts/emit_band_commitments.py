"""
Pre-open commitment publisher — the two emission moments that give
archive rows a pre-outcome timestamp (scope doc §11.2).

M6 factorisation: the band half-width  q_eff · σ̂ · fri_close  is fully
determined at Friday close; only the band *center* moves with weekend
futures. So:

  friday mode   (run Friday evening / Saturday, before Globex reopens
                Sunday 18:00 ET): per symbol, compute σ̂ (frozen EWMA
                rule over the completed-weekend panel), publication
                regime, and per-τ half-widths from the frozen scalars.
                Append to data/band_archive/commitments_v1.csv.

  monday mode   (run Monday BEFORE 09:30 ET): read the committed rows,
                compute the point = fri_close · (1 + factor_ret) with
                the factor instrument's Monday daily-bar open (the same
                `{prefix}_mon_open` semantics `panel.build()` uses, via
                the same loaders — so the published band matches later
                evaluation by construction), and append full band rows
                to bands_v1.csv with provenance=published_pre_open.
                Committed widths are used VERBATIM — a commitment is
                binding; if recomputation would disagree, that is drift
                to disclose, not a value to update.

Honesty guards:
  - monday mode refuses to write after 09:25 ET on the open date
    (--allow-post-open exists for testing and FORCES --dry-run).
  - symbols whose factor instrument has no Monday bar in scryer yet are
    skipped with a note (the Tuesday harness's retro_frozen row fills
    them; the dedup key makes the two paths race-free). Known standing
    case: MSTR's BTC-USD factor — scryer's equities-daily runner fires
    18:00 ET, so Monday's BTC bar (opens 00:00 UTC) is absent Monday
    morning.

σ̂ context is anchored to the frozen artefact's training cutoff minus
`--context-days`, exactly like scripts/collect_forward_tape.py, so the
committed σ̂ matches what the forward-tape evaluator later recomputes.

Per CLAUDE.md hard rule #1 this script fetches nothing: every input is
scryer parquet via the panel loaders.

Run
---
  uv run python scripts/emit_band_commitments.py friday
  uv run python scripts/emit_band_commitments.py monday
  uv run python scripts/emit_band_commitments.py friday --as-of-friday 2026-07-17 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from datetime import time as dtime

import numpy as np
import pandas as pd

from soothsayer.band_archive import (
    BANDS_COLUMNS,
    BANDS_PATH,
    COMMITMENTS_COLUMNS,
    COMMITMENTS_PATH,
    FORECASTER_CODE_LWC,
    PROFILE_CODE_LENDING,
    PROVENANCE_PRE_OPEN,
    append_dedup,
)
from soothsayer.backtest import regimes
from soothsayer.backtest.calibration import DEFAULT_TAUS
from soothsayer.backtest.frozen_serving import (
    apply_frozen_sigma_rule,
    frozen_schedules,
    interp,
    load_frozen,
)
from soothsayer.backtest.panel import (
    BTC,
    FACTOR_BY_SYMBOL,
    MSTR_BTC_PIVOT,
    PanelSpec,
    _load_one_symbol,
    _universe,
    build as build_panel,
)
from soothsayer.config import DATA_PROCESSED

ET = ZoneInfo("America/New_York")
DEFAULT_CONTEXT_DAYS = 400  # matches collect_forward_tape.py

# US equity market holidays (NYSE full closures). Static table with a
# horizon guard — the emitter refuses to reason about dates past the
# table. Extend the table (one line) before HORIZON passes; the guard
# makes silent staleness impossible.
US_MARKET_HOLIDAYS: frozenset[date] = frozenset({
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16),
    date(2026, 4, 3), date(2026, 5, 25), date(2026, 6, 19),
    date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26),
    date(2026, 12, 25),
    # 2027 (observed dates)
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15),
    date(2027, 3, 26), date(2027, 5, 31), date(2027, 6, 18),
    date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25),
    date(2027, 12, 24),
})
HOLIDAY_TABLE_HORIZON = date(2027, 12, 31)


def next_trading_day(d: date) -> date:
    nxt = d + timedelta(days=1)
    while True:
        if nxt > HOLIDAY_TABLE_HORIZON:
            raise SystemExit(
                f"next_trading_day({d}) walked past the holiday-table "
                f"horizon {HOLIDAY_TABLE_HORIZON}. Extend "
                "US_MARKET_HOLIDAYS before scheduling more commitments."
            )
        if nxt.weekday() < 5 and nxt not in US_MARKET_HOLIDAYS:
            return nxt
        nxt += timedelta(days=1)


def _factor_instrument(symbol: str, weekend: date) -> str:
    if symbol == "MSTR" and weekend >= MSTR_BTC_PIVOT:
        return BTC
    return FACTOR_BY_SYMBOL.get(symbol, "ES=F")


def _training_cutoff(frozen_parquet: Path) -> date:
    frozen = pd.read_parquet(frozen_parquet, columns=["fri_ts"])
    return pd.to_datetime(frozen["fri_ts"]).max().date()


def _load_frozen_pair(suffix: str | None) -> tuple[Path, dict, str, date]:
    json_path, sidecar = load_frozen(suffix)
    sha = sidecar.get("_artefact_sha256")
    if not sha:
        raise SystemExit(f"{json_path.name} lacks _artefact_sha256; refusing to emit.")
    parquet_path = json_path.with_suffix(".parquet")
    if not parquet_path.exists():
        raise SystemExit(f"Frozen parquet missing next to sidecar: {parquet_path}")
    return json_path, sidecar, sha, _training_cutoff(parquet_path)


def _bar_at(sym: str, day: date) -> pd.Series | None:
    """The daily bar for `sym` dated exactly `day`, via the panel's
    source-dispatch loader (yahoo / CBOE-blend / CME-blend)."""
    df = _load_one_symbol(sym, day - timedelta(days=6), day)
    if df.empty:
        return None
    df = df[pd.to_datetime(df["ts"]).dt.date == day]
    return None if df.empty else df.iloc[-1]


# ==================================================================== friday


def run_friday(args) -> int:
    json_path, sidecar, sha, cutoff = _load_frozen_pair(args.frozen_suffix)
    qt, cb, delta = frozen_schedules(sidecar)
    anchors = sorted(cb.keys())

    today = date.today()
    if args.as_of_friday:
        fri = date.fromisoformat(args.as_of_friday)
    else:
        # Auto-detect: the most recent equity trading day with a bar on
        # disk, looked up via SPY (any universe symbol would do).
        probe = _load_one_symbol("SPY", today - timedelta(days=6), today)
        if probe.empty:
            raise SystemExit("No recent SPY bars in scryer — cannot locate Friday.")
        fri = pd.to_datetime(probe["ts"]).dt.date.max()

    mon = next_trading_day(fri)
    gap_days = (mon - fri).days
    if gap_days < 3 and not args.as_of_friday:
        raise SystemExit(
            f"Latest trading day {fri} is not a weekend-eve (next session "
            f"{mon}, gap {gap_days}d). Nothing to commit."
        )
    print(f"Committing weekend {fri} → {mon} (gap {gap_days}d) under freeze {sha}")

    # Honesty guard: a weekend commitment must precede the first Globex
    # session after that Friday (Sunday 18:00 ET; 17:45 cushion). After
    # that, weekend information exists and a write to the real
    # commitments file would be retro-dressed as a commitment. Test
    # writes to an explicit --commitments-path override are exempt.
    globex_reopen = datetime.combine(fri + timedelta(days=2), dtime(17, 45), tzinfo=ET)
    if datetime.now(ET) >= globex_reopen and not args.commitments_path:
        if not args.dry_run:
            print("NOTE: past Globex reopen for this weekend — forcing dry-run; "
                  "commitments can no longer be honestly emitted.")
        args.dry_run = True

    vix_bar = _bar_at("^VIX", fri)
    if vix_bar is None:
        raise SystemExit(f"No ^VIX bar for {fri} in scryer (cboe/yahoo) — "
                         "regime rule needs it; aborting.")
    vix_close = float(vix_bar["close"])

    # Completed-weekend context panel, window anchored to the freeze
    # cutoff exactly like the forward-tape collector so σ̂ matches the
    # evaluator's recomputation.
    start = cutoff - timedelta(days=args.context_days)
    panel = build_panel(PanelSpec(start=start, end=fri))
    if panel.empty:
        raise SystemExit("Context panel is empty — check scryer surfaces.")

    synth_rows = []
    skipped = []
    for sym in _universe():
        bar = _bar_at(sym, fri)
        if bar is None:
            skipped.append(sym)
            continue
        synth_rows.append({
            "symbol": sym,
            "fri_ts": fri,
            "mon_ts": mon,
            "gap_days": float(gap_days),
            "fri_close": float(bar["close"]),
            "mon_open": np.nan,
            "factor_ret": np.nan,
            "fri_vol_20d": np.nan,
            "vix_fri_close": vix_close,
        })
    if skipped:
        print(f"WARN: no {fri} bar for {skipped} — committing the rest.")
    if not synth_rows:
        raise SystemExit(f"No symbol has a {fri} bar in scryer; aborting.")

    cols = ["symbol", "fri_ts", "mon_ts", "gap_days", "fri_close",
            "mon_open", "factor_ret", "fri_vol_20d", "vix_fri_close"]
    combined = pd.concat(
        [panel[cols], pd.DataFrame(synth_rows)[cols]], ignore_index=True
    )
    combined = regimes.tag(combined)
    combined = apply_frozen_sigma_rule(combined, sidecar)

    cur = combined[combined["fri_ts"] == fri]
    computed_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_rows = []
    for _, row in cur.iterrows():
        sigma = float(row["sigma_hat_sym_pre_fri"])
        if not (np.isfinite(sigma) and sigma > 0):
            print(f"WARN: σ̂ unavailable for {row['symbol']} (warm-up?) — skipping.")
            continue
        regime = str(row["regime_pub"])
        q_row = qt.get(regime) or qt.get("high_vol")
        for tau in DEFAULT_TAUS:
            served = min(tau + float(delta.get(tau, 0.0)), anchors[-1])
            q_eff = interp(cb, served) * interp(q_row, served)
            out_rows.append({
                "weekend_date": fri.isoformat(),
                "mon_date": mon.isoformat(),
                "symbol": row["symbol"],
                "tau": float(tau),
                "fri_close": float(row["fri_close"]),
                "sigma_hat": sigma,
                "regime_code": regime,
                "half_width_bps": q_eff * sigma * 1e4,
                "half_width_abs": q_eff * sigma * float(row["fri_close"]),
                "forecaster_code": FORECASTER_CODE_LWC,
                "profile_code": PROFILE_CODE_LENDING,
                "artefact_sha256": sha,
                "computed_ts": computed_ts,
            })

    out = pd.DataFrame(out_rows)[COMMITMENTS_COLUMNS]
    if args.dry_run:
        print(out.to_string(index=False))
        print(f"(dry-run: {len(out)} rows NOT written)")
        return 0
    path = Path(args.commitments_path) if args.commitments_path else COMMITMENTS_PATH
    n_app, n_tot = append_dedup(path, out, COMMITMENTS_COLUMNS)
    print(f"Appended {n_app} commitment rows ({len(out) - n_app} already "
          f"present); {path} now {n_tot} rows.")
    return 0


# ==================================================================== monday


def run_monday(args) -> int:
    path = Path(args.commitments_path) if args.commitments_path else COMMITMENTS_PATH
    if not path.exists():
        raise SystemExit(f"No commitments file at {path} — run friday mode first.")
    com = pd.read_csv(path, dtype={"weekend_date": str, "mon_date": str})

    if args.as_of_friday:
        com = com[com["weekend_date"] == args.as_of_friday]
        if com.empty:
            raise SystemExit(f"No commitment rows for weekend {args.as_of_friday}.")
        mon = date.fromisoformat(com["mon_date"].iloc[0])
    else:
        today = date.today()
        com = com[com["mon_date"] == today.isoformat()]
        if com.empty:
            print(f"No commitments with mon_date={today} — nothing due.")
            return 0
        mon = today

    dry_run = args.dry_run
    now_et = datetime.now(ET)
    past_open = now_et.date() > mon or (
        now_et.date() == mon and (now_et.hour, now_et.minute) >= (9, 25)
    )
    if past_open:
        if not args.allow_post_open:
            raise SystemExit(
                f"Refusing to emit published_pre_open rows at {now_et:%F %H:%M} ET "
                f"for open date {mon} — the pre-open window has passed. "
                "(--allow-post-open forces a dry run for testing.)"
            )
        dry_run = True
        print("NOTE: post-open — forcing dry-run; nothing will be written.")

    weekend = date.fromisoformat(com["weekend_date"].iloc[0])
    computed_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # One factor lookup per instrument.
    instruments = {
        _factor_instrument(sym, weekend) for sym in com["symbol"].unique()
    }
    factor_ret: dict[str, float | None] = {}
    for inst in instruments:
        fri_bar = _bar_at(inst, weekend)
        mon_bar = _bar_at(inst, mon)
        if fri_bar is None or mon_bar is None:
            factor_ret[inst] = None
            missing = "Friday close" if fri_bar is None else "Monday open"
            print(f"WARN: {inst}: no {missing} bar in scryer yet.")
            continue
        factor_ret[inst] = float(mon_bar["open"]) / float(fri_bar["close"]) - 1.0

    out_rows, skipped = [], []
    for _, row in com.iterrows():
        inst = _factor_instrument(str(row["symbol"]), weekend)
        fr = factor_ret.get(inst)
        if fr is None:
            skipped.append(str(row["symbol"]))
            continue
        point = float(row["fri_close"]) * (1.0 + fr)
        half = float(row["half_width_abs"])
        out_rows.append({
            "weekend_date": row["weekend_date"],
            "mon_date": row["mon_date"],
            "symbol": row["symbol"],
            "tau": float(row["tau"]),
            "lower": point - half,
            "upper": point + half,
            "point": point,
            "half_width_bps": float(row["half_width_bps"]),
            "regime_code": row["regime_code"],
            "forecaster_code": int(row["forecaster_code"]),
            "profile_code": int(row["profile_code"]),
            "artefact_sha256": row["artefact_sha256"],
            "provenance": PROVENANCE_PRE_OPEN,
            "computed_ts": computed_ts,
        })
    if skipped:
        uniq = sorted(set(skipped))
        print(f"Skipped (factor pending, retro path will fill): {uniq}")
    if not out_rows:
        raise SystemExit("No factor data available for any symbol — nothing emitted.")

    out = pd.DataFrame(out_rows)[BANDS_COLUMNS]
    if dry_run:
        print(out.to_string(index=False))
        print(f"(dry-run: {len(out)} rows NOT written)")
        return 0
    bands_path = Path(args.bands_path) if args.bands_path else BANDS_PATH
    n_app, n_tot = append_dedup(bands_path, out, BANDS_COLUMNS)
    print(f"Appended {n_app} published_pre_open rows ({len(out) - n_app} "
          f"already present); {bands_path} now {n_tot} rows.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["friday", "monday"])
    parser.add_argument("--as-of-friday", default=None,
                        help="Weekend Friday (YYYY-MM-DD). Default: auto-detect "
                             "(friday mode) / commitments due today (monday mode).")
    parser.add_argument("--frozen-suffix", default=None)
    parser.add_argument("--context-days", type=int, default=DEFAULT_CONTEXT_DAYS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-post-open", action="store_true",
                        help="Testing only: run monday mode after the open — "
                             "forces --dry-run, never writes.")
    parser.add_argument("--commitments-path", default=None, help="Override (testing).")
    parser.add_argument("--bands-path", default=None, help="Override (testing).")
    args = parser.parse_args()

    if args.mode == "friday":
        sys.exit(run_friday(args))
    sys.exit(run_monday(args))


if __name__ == "__main__":
    main()
