"""
Forward-tape evaluator for the M6 LWC harness — Phase 4.3.

Loads the frozen LWC artefact (constants ONLY — no re-fitting), reads
`data/processed/forward_tape_v1.parquet`, computes σ̂_sym(t) over the
combined context+forward panel, applies the frozen serving formula to
every forward row, and reports per-symbol / pooled coverage in
`reports/m6_forward_tape_{N}weekends.md`.

Critical contract: this script must NEVER touch the frozen artefact's
constants. The frozen `regime_quantile_table`, `c_bump_schedule`, and
`delta_shift_schedule` from the JSON sidecar are the only inputs to the
serving formula. σ̂_sym(t) for forward weekends is recomputed (it's a
trailing-K window; can't be frozen) but uses the same K and min_obs as
the artefact build.

Behaviour
---------
- 0 forward rows in the tape: graceful exit with "insufficient data —
  T weekends" message. The launchd cadence will retry next week.
- < 4 forward weekends: report is written but flagged as preliminary.
- ≥ 4 forward weekends: full §6.3 (pooled OOS) + §6.4 (per-symbol
  Kupiec + Berkowitz LR) reported. §6.6 path-fitted is deferred to a
  future phase (needs CME 1m fresh + meaningful sample size).

Outputs
-------
  reports/m6_forward_tape_{N}weekends.md
  reports/tables/m6_forward_tape_{N}weekends_per_symbol.csv

Run
---
  uv run python scripts/run_forward_tape_evaluation.py
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from soothsayer.backtest import metrics as met
from soothsayer.backtest.calibration import (
    DEFAULT_TAUS,
    SIGMA_HAT_K,
    SIGMA_HAT_MIN,
    add_sigma_hat_sym,
    compute_score_lwc,
)
from soothsayer.config import DATA_PROCESSED, REPORTS


FORWARD_TAPE_PATH = DATA_PROCESSED / "forward_tape_v1.parquet"

# Dense PIT grid for per-symbol Berkowitz; matches the in-sample
# `run_v1b_per_symbol_diagnostics.py` runner.
PIT_DENSE_GRID = (
    0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.68, 0.70, 0.80, 0.85,
    0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.998, 0.999,
)


# ============================================================ frozen constants


def _load_frozen(suffix: str | None) -> tuple[Path, dict]:
    if suffix is not None:
        path = DATA_PROCESSED / f"lwc_artefact_v1_frozen_{suffix}.json"
        if not path.exists():
            raise FileNotFoundError(f"Frozen artefact not found: {path}")
    else:
        candidates = sorted(DATA_PROCESSED.glob("lwc_artefact_v1_frozen_*.json"))
        if not candidates:
            raise FileNotFoundError("No frozen artefact in data/processed/.")
        path = candidates[-1]
    return path, json.loads(path.read_text())


def _frozen_schedules(sidecar: dict) -> tuple[dict, dict, dict]:
    """Pull the three frozen schedules out of the JSON sidecar with the
    {regime → {τ → b}} / {τ → c} / {τ → δ} shapes that
    `serve_bands_lwc` expects."""
    quantile_table = {
        regime: {float(tau): float(b) for tau, b in row.items()}
        for regime, row in sidecar["regime_quantile_table"].items()
    }
    c_bump_schedule = {
        float(tau): float(c)
        for tau, c in sidecar["c_bump_schedule"].items()
    }
    delta_shift_schedule = {
        float(tau): float(d)
        for tau, d in sidecar["delta_shift_schedule"].items()
    }
    return quantile_table, c_bump_schedule, delta_shift_schedule


# ====================================================== σ̂ + serve from frozen


def _interp(table: dict[float, float], x: float) -> float:
    keys = sorted(table.keys())
    if x <= keys[0]:
        return float(table[keys[0]])
    if x >= keys[-1]:
        return float(table[keys[-1]])
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= x <= hi:
            frac = (x - lo) / (hi - lo)
            return float(table[lo] + frac * (table[hi] - table[lo]))
    return float(table[keys[-1]])


def _serve_frozen(
    panel: pd.DataFrame,
    qt: dict, cb: dict, delta: dict,
    taus: tuple[float, ...] = DEFAULT_TAUS,
) -> dict[float, pd.DataFrame]:
    """Apply the frozen LWC serving formula. Identical to
    `calibration.serve_bands_lwc` but reads schedules from the JSON
    sidecar (not the module-level LWC_* runtime tables) so we are
    immune to live-artefact updates between freeze and evaluation."""
    point = panel["fri_close"].astype(float) * (
        1.0 + panel["factor_ret"].astype(float)
    )
    fri_close = panel["fri_close"].astype(float).to_numpy()
    sigma = panel["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    cells = panel["regime_pub"].astype(str).to_numpy()
    out: dict[float, pd.DataFrame] = {}
    anchors = sorted(cb.keys())
    for tau in taus:
        d = float(delta.get(tau, 0.0))
        served = min(tau + d, anchors[-1])
        c = _interp(cb, served)
        b_per_row = np.array([
            _interp(qt[c_], served) if c_ in qt else np.nan
            for c_ in cells
        ], dtype=float)
        # Rows whose regime is unknown to the frozen table (shouldn't
        # happen given the panel's regime classifier matches the
        # frozen one, but defensive): fall back to high_vol if known.
        unk = ~np.isfinite(b_per_row)
        if unk.any() and "high_vol" in qt:
            b_per_row[unk] = _interp(qt["high_vol"], served)
        q_eff = c * b_per_row
        half = q_eff * sigma * fri_close
        out[tau] = pd.DataFrame(
            {"lower": point.values - half, "upper": point.values + half},
            index=panel.index,
        )
    return out


# ============================================================== PIT + metrics


def _build_pits(
    panel: pd.DataFrame,
    qt: dict, cb: dict,
    dense_grid: tuple[float, ...] = PIT_DENSE_GRID,
) -> np.ndarray:
    """Per-row PITs at the frozen LWC band CDF, dense τ grid. Caller
    must order panel by (fri_ts, symbol) for cross-sectional Berkowitz."""
    grid_taus = np.array(sorted(dense_grid))
    point = (panel["fri_close"].astype(float)
             * (1.0 + panel["factor_ret"].astype(float))).to_numpy()
    fri_close = panel["fri_close"].astype(float).to_numpy()
    mon_open = panel["mon_open"].astype(float).to_numpy()
    cells = panel["regime_pub"].astype(str).to_numpy()
    sigma = panel["sigma_hat_sym_pre_fri"].astype(float).to_numpy()
    pits = np.full(len(panel), np.nan)
    for i in range(len(panel)):
        q_row = qt.get(cells[i])
        if q_row is None:
            continue
        b_anchors = np.array(
            [_interp(q_row, tau) * _interp(cb, tau) for tau in grid_taus],
            dtype=float,
        )
        s = sigma[i]
        if not (np.isfinite(s) and s > 0):
            continue
        scale = fri_close[i] * s
        if not (np.isfinite(scale) and scale > 0):
            continue
        half_i = b_anchors * scale
        if not np.all(np.isfinite(half_i)):
            continue
        r = mon_open[i] - point[i]
        abs_r = abs(r)
        anchor_b = np.concatenate(([0.0], half_i))
        anchor_tau = np.concatenate(([0.0], grid_taus))
        if abs_r >= anchor_b[-1]:
            tau_hat = anchor_tau[-1]
        else:
            tau_hat = float(np.interp(abs_r, anchor_b, anchor_tau))
        pits[i] = 0.5 + 0.5 * tau_hat * (1 if r >= 0 else -1)
    return pits


def _pooled_metrics(
    panel: pd.DataFrame, bounds: dict, taus: tuple[float, ...]
) -> pd.DataFrame:
    rows = []
    for tau in taus:
        b = bounds[tau]
        inside = ((panel["mon_open"] >= b["lower"]) &
                  (panel["mon_open"] <= b["upper"]))
        v = (~inside).astype(int).to_numpy()
        lr_uc, p_uc = met._lr_kupiec(v, tau)
        cc = met.conditional_coverage_from_bounds(
            panel, {tau: b}, group_by="symbol"
        )
        cc0 = cc.iloc[0]
        rows.append({
            "tau": float(tau),
            "n": int(len(panel)),
            "realised": float(inside.mean()),
            "half_width_bps": float(((b["upper"] - b["lower"]) / 2
                                     / panel["fri_close"] * 1e4).mean()),
            "kupiec_lr": float(lr_uc),
            "kupiec_p": float(p_uc),
            "christ_lr": float(cc0["lr_ind"]),
            "christ_p": float(cc0["p_ind"]),
        })
    return pd.DataFrame(rows)


def _per_symbol_kupiec(
    panel: pd.DataFrame, bounds: dict, taus: tuple[float, ...]
) -> pd.DataFrame:
    rows = []
    for sym, idx in panel.groupby("symbol").groups.items():
        sub = panel.loc[idx]
        row: dict = {"symbol": sym, "n_oos": int(len(sub))}
        for tau in taus:
            band = bounds[tau].loc[sub.index]
            inside = ((sub["mon_open"] >= band["lower"]) &
                      (sub["mon_open"] <= band["upper"]))
            v = (~inside).astype(int).to_numpy()
            lr, p = met._lr_kupiec(v, tau)
            row[f"viol_rate_{tau}"] = float(v.mean())
            row[f"kupiec_p_{tau}"] = float(p)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("symbol").reset_index(drop=True)


def _per_symbol_berkowitz(
    panel: pd.DataFrame, qt: dict, cb: dict
) -> pd.DataFrame:
    rows = []
    for sym, idx in panel.groupby("symbol").groups.items():
        sub = panel.loc[idx].sort_values("fri_ts").reset_index(drop=True)
        pits = _build_pits(sub, qt, cb)
        clean = pits[(np.isfinite(pits)) & (pits > 0) & (pits < 1)]
        if len(clean) < 10:  # forward-tape will be small; relax from in-sample's 30
            rows.append({"symbol": sym,
                         "berkowitz_lr": float("nan"),
                         "berkowitz_p": float("nan"),
                         "var_z": float("nan"),
                         "berkowitz_n": int(len(clean))})
            continue
        bw = met.berkowitz_test(clean)
        rows.append({"symbol": sym,
                     "berkowitz_lr": float(bw.get("lr", float("nan"))),
                     "berkowitz_p": float(bw.get("p_value", float("nan"))),
                     "var_z": float(bw.get("var_z", float("nan"))),
                     "berkowitz_n": int(bw.get("n", len(clean)))})
    return pd.DataFrame(rows)


# ===================================================================== render


def _render_report(
    n_weekends: int,
    n_rows: int,
    fri_ts_range: tuple[date, date],
    pooled: pd.DataFrame,
    per_symbol: pd.DataFrame,
    frozen_path: Path,
    sidecar: dict,
    is_preliminary: bool,
) -> Path:
    out_path = REPORTS / f"m6_forward_tape_{n_weekends}weekends.md"
    sha = sidecar.get("_artefact_sha256", "<unknown>")
    freeze = sidecar.get("_freeze_date", "<unknown>")

    lines = [
        f"# M6 LWC forward-tape OOS — {n_weekends} weekends since freeze",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.",
        "**Frozen artefact:** "
        f"`{frozen_path.name}` (SHA-256 `{sha[:12]}…`, freeze date "
        f"{freeze}).",
        f"**Forward window:** {fri_ts_range[0]} → {fri_ts_range[1]}  "
        f"(n_rows = {n_rows}, n_weekends = {n_weekends}).",
        "",
    ]
    if is_preliminary:
        lines += [
            "> **Preliminary** — fewer than 4 forward weekends accumulated; "
            "treat the headline as anecdotal until ≥ 4 weekends land. "
            "Per-symbol Kupiec is uninformative at this n.",
            "",
        ]

    lines += [
        "## 1. Pooled OOS at every served τ",
        "",
        "| τ | n | realised | half-width (bps) | Kupiec p | Christoffersen p |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in pooled.iterrows():
        lines.append(
            f"| {r['tau']:.2f} | {int(r['n'])} | {r['realised']:.4f} | "
            f"{r['half_width_bps']:.1f} | {r['kupiec_p']:.4f} | "
            f"{r['christ_p']:.4f} |"
        )

    lines += [
        "",
        "## 2. Per-symbol diagnostics at τ = 0.95",
        "",
        "| symbol | n | violation rate | Kupiec p | Berkowitz LR | Berkowitz p |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in per_symbol.iterrows():
        viol = r.get("viol_rate_0.95", float("nan"))
        kupiec = r.get("kupiec_p_0.95", float("nan"))
        bw_lr = r.get("berkowitz_lr", float("nan"))
        bw_p = r.get("berkowitz_p", float("nan"))
        lines.append(
            f"| {r['symbol']} | {int(r['n_oos'])} | "
            f"{viol:.4f} | {kupiec:.4f} | "
            f"{'nan' if not np.isfinite(bw_lr) else f'{bw_lr:.2f}'} | "
            f"{'nan' if not np.isfinite(bw_p) else f'{bw_p:.4f}'} |"
        )

    if not is_preliminary:
        n_pass = int((per_symbol.get("kupiec_p_0.95", pd.Series(dtype=float))
                      >= 0.05).sum())
        n_total = len(per_symbol)
        lines += [
            "",
            f"**Headline:** {n_pass} / {n_total} symbols pass per-symbol "
            f"Kupiec at τ=0.95 on the forward tape (in-sample baseline: 10/10 "
            "under M6, 2/10 under M5; see `reports/m6_validation.md`).",
        ]

    lines += [
        "",
        "## 3. Reproducibility",
        "",
        "```bash",
        "uv run python scripts/collect_forward_tape.py",
        "uv run python scripts/run_forward_tape_evaluation.py",
        "```",
        "",
        "The frozen artefact is read-only. To advance the freeze date "
        "(after a planned methodology refresh), re-run "
        "`scripts/freeze_lwc_artefact.py` with a new `--date` and re-run "
        "the harness.",
        "",
    ]

    out_path.write_text("\n".join(lines))
    return out_path


# ===================================================================== runner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-suffix", default=None,
                        help="YYYYMMDD suffix of the frozen artefact "
                             "(defaults to latest).")
    args = parser.parse_args()

    if not FORWARD_TAPE_PATH.exists():
        raise SystemExit(
            f"{FORWARD_TAPE_PATH} not found. Run "
            "`uv run python scripts/collect_forward_tape.py` first."
        )

    tape = pd.read_parquet(FORWARD_TAPE_PATH)
    tape["fri_ts"] = pd.to_datetime(tape["fri_ts"]).dt.date
    forward = tape[tape["is_forward"]].copy()
    n_forward = len(forward)
    n_weekends = forward["fri_ts"].nunique() if n_forward else 0

    print(f"Forward tape: {len(tape):,} total rows  /  "
          f"{n_forward:,} forward rows  /  {n_weekends} forward weekends",
          flush=True)

    if n_forward == 0:
        print("Insufficient data — 0 forward weekends. Exiting.", flush=True)
        # Write a minimal stub report so the CI / launchd cadence has
        # an artifact to commit.
        stub = REPORTS / "m6_forward_tape_0weekends.md"
        stub.write_text(
            f"# M6 LWC forward-tape — 0 weekends since freeze\n\n"
            f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.\n\n"
            "No forward weekends with complete coverage have landed in the "
            "scryer parquet since the M6 LWC artefact was frozen. The "
            "harness fires on its launchd cadence (Tuesday 09:30 local "
            "time) and will populate this report once at least one "
            "complete forward weekend is available.\n\n"
            "Most likely cause of an empty tape: at least one of the four "
            "scryer runners (`equities-daily`, `earnings`, `cme-intraday-"
            "1m`, `cboe-indices`) had a recent failure or gap that left a "
            "Friday or Monday bar missing for the panel's exogenous "
            "factors. The wrapper script's SLA pre-check "
            "(`scripts/check_scryer_freshness.py`) flags any runner that's "
            "missed its 26h SLA; check `~/Library/Logs/"
            "soothsayer-forward-tape.log` for the most recent fire's "
            "summary.\n"
        )
        print(f"Wrote {stub}", flush=True)
        return

    frozen_path, sidecar = _load_frozen(args.frozen_suffix)
    qt, cb, delta = _frozen_schedules(sidecar)
    print(f"Frozen artefact: {frozen_path.name}", flush=True)
    print(f"  freeze_date={sidecar.get('_freeze_date')}  "
          f"sha256={sidecar.get('_artefact_sha256','')[:12]}…", flush=True)

    # σ̂_sym(t) over the combined context+forward panel — must use the
    # same K=26 / min_obs=8 as the frozen build for consistency.
    full = tape.copy()
    full = add_sigma_hat_sym(full, K=SIGMA_HAT_K, min_obs=SIGMA_HAT_MIN)
    forward = full[full["is_forward"] & full["sigma_hat_sym_pre_fri"].notna()].copy()
    forward = forward.sort_values(["fri_ts", "symbol"]).reset_index(drop=True)
    n_forward_post_sigma = len(forward)
    print(f"Forward rows with σ̂ available: {n_forward_post_sigma}", flush=True)
    if n_forward_post_sigma == 0:
        print("All forward rows lack σ̂ — too few context weekends. Exiting.",
              flush=True)
        return

    bounds = _serve_frozen(forward, qt, cb, delta)
    pooled = _pooled_metrics(forward, bounds, DEFAULT_TAUS)
    per_sym_k = _per_symbol_kupiec(forward, bounds, DEFAULT_TAUS)
    per_sym_b = _per_symbol_berkowitz(forward, qt, cb)
    per_sym = per_sym_k.merge(per_sym_b, on="symbol", how="left")

    out_csv = REPORTS / "tables" / f"m6_forward_tape_{n_weekends}weekends_per_symbol.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    per_sym.to_csv(out_csv, index=False)

    fri_ts_range = (forward["fri_ts"].min(), forward["fri_ts"].max())
    is_preliminary = n_weekends < 4
    out_md = _render_report(
        n_weekends, n_forward_post_sigma, fri_ts_range,
        pooled, per_sym, frozen_path, sidecar, is_preliminary,
    )
    print(f"\nWrote {out_md}", flush=True)
    print(f"Wrote {out_csv}", flush=True)
    print("\nPooled OOS:")
    print(pooled.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
