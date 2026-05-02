from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from soothsayer.config import SCRYER_DATASET_ROOT


@dataclass
class SurfaceCoverage:
    rows: int
    files: int
    start_utc: str | None
    end_utc: str | None


def _load_surface(base: Path) -> tuple[pd.DataFrame, list[Path]]:
    files = sorted(base.rglob("*.parquet")) if base.exists() else []
    if not files:
        return pd.DataFrame(), []
    df = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    return df, files


def _iso(ts: pd.Timestamp | None) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    return ts.isoformat()


def _q(series: pd.Series, q: float) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float(s.quantile(q))


def _coverage(df: pd.DataFrame, files: list[Path], ts_col: str, unit: str = "s") -> SurfaceCoverage:
    if df.empty or ts_col not in df.columns:
        return SurfaceCoverage(rows=int(len(df)), files=len(files), start_utc=None, end_utc=None)
    ts = pd.to_datetime(df[ts_col], unit=unit, utc=True, errors="coerce")
    return SurfaceCoverage(
        rows=int(len(df)),
        files=len(files),
        start_utc=_iso(ts.min()),
        end_utc=_iso(ts.max()),
    )


def compute() -> dict[str, Any]:
    root = SCRYER_DATASET_ROOT

    v5, v5_files = _load_surface(root / "soothsayer_v5" / "tape" / "v1")
    pyth, pyth_files = _load_surface(root / "pyth" / "oracle_tape" / "v1")
    red, red_files = _load_surface(root / "redstone" / "oracle_tape" / "v1")
    cl, cl_files = _load_surface(root / "chainlink" / "data_streams" / "v1")

    out: dict[str, Any] = {
        "coverage": {
            "soothsayer_v5_tape": asdict(_coverage(v5, v5_files, "poll_ts", "s")),
            "pyth_oracle_tape": asdict(_coverage(pyth, pyth_files, "poll_unix", "s")),
            "redstone_oracle_tape": asdict(_coverage(red, red_files, "redstone_ts", "ms")),
            "chainlink_data_streams": asdict(_coverage(cl, cl_files, "observation_ts", "s")),
        }
    }

    # v5 basis behavior by weekend vs weekday (xStock joined tape)
    if not v5.empty:
        v5 = v5.copy()
        v5["ts"] = pd.to_datetime(v5["poll_ts"], unit="s", utc=True, errors="coerce")
        v5["is_weekend"] = v5["ts"].dt.dayofweek >= 5
        v5["basis_abs_bps"] = pd.to_numeric(v5["basis_bp"], errors="coerce").abs()
        out["v5_basis"] = {
            "weekend": {
                "rows": int(v5["is_weekend"].sum()),
                "median_abs_bps": _q(v5.loc[v5["is_weekend"], "basis_abs_bps"], 0.5),
                "p90_abs_bps": _q(v5.loc[v5["is_weekend"], "basis_abs_bps"], 0.9),
            },
            "weekday": {
                "rows": int((~v5["is_weekend"]).sum()),
                "median_abs_bps": _q(v5.loc[~v5["is_weekend"], "basis_abs_bps"], 0.5),
                "p90_abs_bps": _q(v5.loc[~v5["is_weekend"], "basis_abs_bps"], 0.9),
            },
            "symbols": sorted(v5["symbol"].dropna().unique().tolist()),
        }

    # Pyth session and weekend variance proxies
    if not pyth.empty:
        pyth = pyth.copy()
        pyth["ts"] = pd.to_datetime(pyth["poll_unix"], unit="s", utc=True, errors="coerce")
        pyth["is_weekend"] = pyth["ts"].dt.dayofweek >= 5
        pyth["abs_ret_bps"] = (
            pyth.groupby("symbol")["pyth_price"].pct_change().abs() * 1e4
        )
        by_weekend = pyth.groupby("is_weekend").agg(
            rows=("symbol", "size"),
            conf_median_bps=("pyth_half_width_bps", "median"),
            conf_p90_bps=("pyth_half_width_bps", lambda s: s.quantile(0.9)),
            abs_ret_median_bps=("abs_ret_bps", "median"),
            abs_ret_p90_bps=("abs_ret_bps", lambda s: s.quantile(0.9)),
        )
        out["pyth"] = {
            "session_counts": pyth["session"].value_counts(dropna=False).to_dict(),
            "weekend_vs_weekday": {
                str(k): {kk: float(vv) for kk, vv in row.items()}
                for k, row in by_weekend.to_dict(orient="index").items()
            },
            "symbols": sorted(pyth["symbol"].dropna().unique().tolist()),
        }

    # RedStone cadence and variability
    if not red.empty:
        red = red.copy()
        red["poll_dt"] = pd.to_datetime(red["poll_ts"], utc=True, errors="coerce")
        red["is_weekend"] = red["poll_dt"].dt.dayofweek >= 5
        red = red.sort_values(["symbol", "poll_dt"])
        red["abs_ret_bps"] = red.groupby("symbol")["value"].pct_change().abs() * 1e4
        by_weekend = red.groupby("is_weekend").agg(
            rows=("symbol", "size"),
            abs_ret_median_bps=("abs_ret_bps", "median"),
            abs_ret_p90_bps=("abs_ret_bps", lambda s: s.quantile(0.9)),
            minutes_age_median=("minutes_age", "median"),
        )
        cadence_summary: dict[str, dict[str, float | int | None]] = {}
        for sym, g in red.groupby("symbol"):
            uniq = pd.Series(sorted(g["poll_dt"].dropna().unique()))
            delta = uniq.diff().dt.total_seconds().dropna()
            cadence_summary[str(sym)] = {
                "rows": int(len(g)),
                "unique_polls": int(len(uniq)),
                "cadence_median_s": float(delta.median()) if not delta.empty else None,
                "cadence_p90_s": float(delta.quantile(0.9)) if not delta.empty else None,
            }
        out["redstone"] = {
            "weekend_vs_weekday": {
                str(k): {kk: float(vv) for kk, vv in row.items()}
                for k, row in by_weekend.to_dict(orient="index").items()
            },
            "cadence_by_symbol": cadence_summary,
        }

    # Chainlink v11 diagnostics in chainlink/data_streams
    if not cl.empty and "schema_id" in cl.columns:
        v11 = cl[cl["schema_id"] == 11].copy()
        if not v11.empty:
            v11["obs_dt"] = pd.to_datetime(v11["observation_ts"], unit="s", utc=True, errors="coerce")
            v11["is_weekend"] = v11["obs_dt"].dt.dayofweek >= 5
            v11["spread_bps"] = (
                (pd.to_numeric(v11["ask_price"], errors="coerce")
                 - pd.to_numeric(v11["bid_price"], errors="coerce"))
                / pd.to_numeric(v11["mid_price"], errors="coerce")
                * 1e4
            )

            def _marker(series: pd.Series) -> pd.Series:
                s = pd.to_numeric(series, errors="coerce")
                return (np.round((s * 100) % 100, 0) == 1)

            v11["bid_marker_01"] = _marker(v11["bid_price"])
            v11["ask_marker_01"] = _marker(v11["ask_price"])
            out["chainlink_v11"] = {
                "rows": int(len(v11)),
                "window_start_utc": _iso(v11["obs_dt"].min()),
                "window_end_utc": _iso(v11["obs_dt"].max()),
                "weekend_rate": float(v11["is_weekend"].mean()),
                "market_status_counts": v11["market_status"].value_counts(dropna=False).to_dict(),
                "spread_bps_median": _q(v11["spread_bps"], 0.5),
                "spread_bps_p90": _q(v11["spread_bps"], 0.9),
                "bid_marker_01_rate": float(v11["bid_marker_01"].mean()),
                "ask_marker_01_rate": float(v11["ask_marker_01"].mean()),
                "symbols": sorted(v11["symbol"].fillna("").astype(str).unique().tolist()),
            }

    return out


def main() -> None:
    payload = compute()
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
