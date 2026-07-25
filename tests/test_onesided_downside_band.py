"""Unit tests for the one-sided (downside) lending profile — Appendix G.

Covers the three things that would silently break the product claim:

  1. Sign convention. `compute_score_lwc_onesided` must be positive when the
     realised price lands *below* the point estimate. A sign flip would fit
     the upside quantile and serve a bound that is wrong in the one direction
     a lending consumer cares about — and it would still look plausible,
     because the magnitudes are similar.

  2. The serving algebra. lower = point − c·q·σ̂·fri_close, exactly.

  3. The reason the profile exists: at the same τ, the one-sided buffer must
     be *strictly smaller* than the two-sided band's lower-edge distance,
     because the two-sided lower edge is a (1+τ)/2 bound. If that inequality
     ever fails, the capital claim in Appendix G.3 is wrong.
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from soothsayer.backtest.calibration import (
    compute_score_lwc,
    compute_score_lwc_onesided,
    serve_downside_bound_lwc,
)


def _panel() -> pd.DataFrame:
    """Four rows with hand-computable residuals; factor_ret = 0 so
    point == fri_close and the arithmetic stays checkable by eye."""
    return pd.DataFrame({
        "symbol": ["A", "A", "B", "B"],
        "fri_close": [100.0, 100.0, 200.0, 200.0],
        "factor_ret": [0.0, 0.0, 0.0, 0.0],
        # A: −2 then +2 (down then up); B: −10 then +6
        "mon_open": [98.0, 102.0, 190.0, 206.0],
        "sigma_hat_sym_pre_fri": [0.01, 0.01, 0.02, 0.02],
        "regime_pub": ["normal", "normal", "normal", "normal"],
    })


class TestOneSidedScore(unittest.TestCase):
    def test_sign_convention_is_downside_positive(self):
        s = compute_score_lwc_onesided(_panel()).to_numpy()
        # row 0: (100 − 98)/(100·0.01) = +2.0   price fell -> positive
        # row 1: (100 − 102)/(100·0.01) = −2.0  price rose -> negative
        # row 2: (200 − 190)/(200·0.02) = +2.5
        # row 3: (200 − 206)/(200·0.02) = −1.5
        np.testing.assert_allclose(s, [2.0, -2.0, 2.5, -1.5])
        self.assertGreater(s[0], 0.0, "a downward move must score positive")
        self.assertLess(s[1], 0.0, "an upward move must score negative")

    def test_two_sided_is_the_absolute_value(self):
        p = _panel()
        one = compute_score_lwc_onesided(p).to_numpy()
        two = compute_score_lwc(p).to_numpy()
        np.testing.assert_allclose(two, np.abs(one))

    def test_nonpositive_sigma_yields_nan(self):
        p = _panel()
        p.loc[0, "sigma_hat_sym_pre_fri"] = 0.0
        p.loc[1, "sigma_hat_sym_pre_fri"] = np.nan
        s = compute_score_lwc_onesided(p)
        self.assertTrue(np.isnan(s.iloc[0]))
        self.assertTrue(np.isnan(s.iloc[1]))
        self.assertFalse(np.isnan(s.iloc[2]))


class TestServing(unittest.TestCase):
    def test_lower_edge_algebra_and_no_upper(self):
        p = _panel()
        qt = {"normal": {0.95: 2.0}}
        cb = {0.95: 1.5}
        out = serve_downside_bound_lwc(p, qt, cb, taus=(0.95,))[0.95]
        # buffer = c·q·σ̂·fri_close = 1.5·2.0·0.01·100 = 3.0 on A
        #                          = 1.5·2.0·0.02·200 = 12.0 on B
        np.testing.assert_allclose(out["lower"].to_numpy(),
                                   [97.0, 97.0, 188.0, 188.0])
        np.testing.assert_allclose(out["point"].to_numpy(),
                                   [100.0, 100.0, 200.0, 200.0])
        self.assertNotIn("upper", out.columns,
                         "a one-sided read must not publish an upper edge")

    def test_c_bump_defaults_to_identity_when_absent(self):
        p = _panel()
        out = serve_downside_bound_lwc(
            p, {"normal": {0.95: 2.0}}, {}, taus=(0.95,))[0.95]
        # c defaults to 1.0 -> buffer 2.0·0.01·100 = 2.0
        np.testing.assert_allclose(out["lower"].to_numpy()[:2], [98.0, 98.0])

    def test_unknown_regime_gives_nan_not_a_silent_zero(self):
        p = _panel()
        p["regime_pub"] = "does_not_exist"
        out = serve_downside_bound_lwc(
            p, {"normal": {0.95: 2.0}}, {0.95: 1.0}, taus=(0.95,))[0.95]
        self.assertTrue(out["lower"].isna().all(),
                        "a missing cell must not serve point-minus-zero")


class TestCapitalClaim(unittest.TestCase):
    """The Appendix G.3 inequality, on the real artefact if it is present."""

    def test_one_sided_buffer_is_smaller_at_equal_tau(self):
        try:
            from soothsayer.oracle import Oracle
            import soothsayer.oracle as o
        except Exception as exc:                      # pragma: no cover
            self.skipTest(f"oracle import failed: {exc}")
        if not o.LWC_ONESIDED_REGIME_QUANTILE_TABLE:
            self.skipTest("one-sided sidecar not built")
        try:
            orc = Oracle.load()
        except Exception as exc:                      # pragma: no cover
            self.skipTest(f"artefacts not on disk: {exc}")
        if not orc.has_lwc:
            self.skipTest("LWC artefact not loaded")

        avail = orc.list_available("SPY")
        if avail.empty:
            self.skipTest("no SPY rows in artefact")
        as_of = avail["fri_ts"].iloc[-1]

        for tau in (0.68, 0.85, 0.95, 0.99):
            one = orc.downside_bound_lwc("SPY", as_of, target_coverage=tau)
            two = orc.fair_value_lwc("SPY", as_of, target_coverage=tau)
            two_sided_buffer_bps = (
                (two.point - two.lower) / one.diagnostics["fri_close"] * 1e4
            )
            with self.subTest(tau=tau):
                self.assertLess(
                    one.buffer_bps, two_sided_buffer_bps,
                    f"at τ={tau} the one-sided buffer ({one.buffer_bps:.1f} bps) "
                    f"must be below the two-sided lower-edge distance "
                    f"({two_sided_buffer_bps:.1f} bps) — the two-sided edge is "
                    f"a {(1 + tau) / 2:.3f} bound, not a {tau} bound",
                )
                # the receipt must state the one-sided claim, not the band's
                self.assertAlmostEqual(one.claimed_coverage, tau, places=6)
                self.assertAlmostEqual(
                    one.diagnostics["two_sided_equivalent_coverage"],
                    (1 + tau) / 2, places=6)
                self.assertEqual(one.forecaster_used, "lwc_onesided")
                self.assertEqual(one.to_dict()["side"], "downside_only")

    def test_profile_is_flagged_undeployed(self):
        import soothsayer.oracle as o
        if not o.LWC_ONESIDED_METADATA:
            self.skipTest("one-sided sidecar not built")
        self.assertIs(o.LWC_ONESIDED_METADATA.get("_deployed"), False,
                      "the one-sided sidecar must declare itself undeployed "
                      "until the Appendix G.5 battery closes")


if __name__ == "__main__":
    unittest.main()
