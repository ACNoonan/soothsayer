"""Unit tests for the M6 path-fitted conformity score (`§10.1`).

Verifies the spec literally:

  s_path = max_{t ∈ [Fri 16:00, Mon 09:30]} |P_t − point| / (fri_close · σ̂_sym)

with the path supremum approximated by the (path_lo, path_hi) extrema and
the endpoint mon_open. Tests the library function in isolation; the
empirical fit pipeline is exercised in `scripts/run_v1b_path_fitted_conformal.py`
and the cross-validation against forward-tape data is gated on accumulation
of ≥ 300 path-coverage weekends (see B6 in
`reports/active/paper1_methodology_revisions.md`).
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    compute_score_lwc,
    compute_score_lwc_path,
)


def _panel(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["fri_close"] = df["fri_close"].astype(float)
    df["mon_open"] = df["mon_open"].astype(float)
    df["factor_ret"] = df["factor_ret"].astype(float)
    df["sigma_hat_sym_pre_fri"] = df["sigma_hat_sym_pre_fri"].astype(float)
    df["path_lo"] = df["path_lo"].astype(float)
    df["path_hi"] = df["path_hi"].astype(float)
    return df


class PathFittedScoreTests(unittest.TestCase):

    def test_degenerate_path_equals_endpoint(self) -> None:
        """If the path collapses to the endpoint (path_lo = path_hi = point),
        the path score equals the endpoint score."""
        panel = _panel([{
            "fri_close": 100.0,
            "factor_ret": 0.005,
            "mon_open": 101.0,
            "path_lo": 100.5,  # point = 100.0 * 1.005 = 100.5
            "path_hi": 100.5,
            "sigma_hat_sym_pre_fri": 0.01,
        }])
        endpoint = compute_score_lwc(panel)
        path = compute_score_lwc_path(panel)
        # |101.0 - 100.5| / (100.0 * 0.01) = 0.5 / 1.0 = 0.5
        self.assertAlmostEqual(float(endpoint.iloc[0]), 0.5, places=8)
        self.assertAlmostEqual(float(path.iloc[0]), 0.5, places=8)

    def test_path_score_dominates_endpoint(self) -> None:
        """For any panel row, path-score ≥ endpoint-score (max-over-path
        construction)."""
        panel = _panel([
            # row 1: deep weekend dip below mon_open
            {"fri_close": 100.0, "factor_ret": 0.0, "mon_open": 100.5,
             "path_lo": 95.0,  "path_hi": 100.6, "sigma_hat_sym_pre_fri": 0.01},
            # row 2: deep weekend spike above mon_open
            {"fri_close": 100.0, "factor_ret": 0.0, "mon_open": 99.5,
             "path_lo": 99.4,  "path_hi": 105.0, "sigma_hat_sym_pre_fri": 0.01},
            # row 3: tight path
            {"fri_close": 100.0, "factor_ret": 0.0, "mon_open": 101.0,
             "path_lo": 100.0, "path_hi": 101.5, "sigma_hat_sym_pre_fri": 0.01},
        ])
        endpoint = compute_score_lwc(panel).to_numpy()
        path = compute_score_lwc_path(panel).to_numpy()
        self.assertTrue(np.all(path >= endpoint - 1e-12),
                        f"path={path}, endpoint={endpoint}")

    def test_path_score_formula(self) -> None:
        """Numerical: s_path = max(point-path_lo, path_hi-point, |mon_open-point|) /
        (fri_close · σ̂)."""
        panel = _panel([{
            "fri_close": 100.0,
            "factor_ret": 0.0,         # point = 100
            "mon_open": 100.5,         # endpoint breach 0.5
            "path_lo": 96.0,           # max breach below = 4.0  ← supremum
            "path_hi": 102.0,          # max breach above = 2.0
            "sigma_hat_sym_pre_fri": 0.01,
        }])
        path = float(compute_score_lwc_path(panel).iloc[0])
        expected = 4.0 / (100.0 * 0.01)
        self.assertAlmostEqual(path, expected, places=8)

    def test_nan_sigma_returns_nan(self) -> None:
        panel = _panel([
            {"fri_close": 100.0, "factor_ret": 0.0, "mon_open": 100.5,
             "path_lo": 99.5, "path_hi": 100.5, "sigma_hat_sym_pre_fri": np.nan},
            {"fri_close": 100.0, "factor_ret": 0.0, "mon_open": 100.5,
             "path_lo": 99.5, "path_hi": 100.5, "sigma_hat_sym_pre_fri": 0.0},
        ])
        out = compute_score_lwc_path(panel)
        self.assertTrue(np.isnan(out.iloc[0]))
        self.assertTrue(np.isnan(out.iloc[1]))

    def test_nan_path_extrema_returns_nan(self) -> None:
        panel = _panel([
            {"fri_close": 100.0, "factor_ret": 0.0, "mon_open": 100.5,
             "path_lo": np.nan, "path_hi": 100.5, "sigma_hat_sym_pre_fri": 0.01},
            {"fri_close": 100.0, "factor_ret": 0.0, "mon_open": 100.5,
             "path_lo": 99.5,   "path_hi": np.nan, "sigma_hat_sym_pre_fri": 0.01},
        ])
        out = compute_score_lwc_path(panel)
        self.assertTrue(np.isnan(out.iloc[0]))
        self.assertTrue(np.isnan(out.iloc[1]))

    def test_breach_below_dominates(self) -> None:
        """When path_lo dips far below point and mon_open is on the high side,
        the breach below the point is the supremum (left-tail dominant)."""
        panel = _panel([{
            "fri_close": 100.0, "factor_ret": 0.0,
            "mon_open": 101.0,             # endpoint breach 1.0
            "path_lo": 92.0, "path_hi": 101.5,  # breach below = 8, above = 1.5
            "sigma_hat_sym_pre_fri": 0.01,
        }])
        path = float(compute_score_lwc_path(panel).iloc[0])
        self.assertAlmostEqual(path, 8.0 / 1.0, places=8)

    def test_negatively_signed_path_no_breach_below(self) -> None:
        """If path_lo > point (no breach below), only path_hi and mon_open matter."""
        panel = _panel([{
            "fri_close": 100.0, "factor_ret": 0.0,
            "mon_open": 102.0,
            "path_lo": 100.5, "path_hi": 105.0,  # both above point=100; only path_hi-point and |mon_open-point|
            "sigma_hat_sym_pre_fri": 0.01,
        }])
        path = float(compute_score_lwc_path(panel).iloc[0])
        # Expected: max(0 [no breach below], 5.0 [breach above], 2.0 [endpoint]) = 5.0
        self.assertAlmostEqual(path, 5.0 / 1.0, places=8)


if __name__ == "__main__":
    unittest.main()
