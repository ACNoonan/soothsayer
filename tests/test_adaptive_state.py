"""Audit properties of the checkpointed adaptive state (W15, overnight).

These are the properties the calibration-transparency claim rests on once a
served band stops being a pure function of a frozen artefact. Each test
corresponds to something a consumer or auditor must be able to do:

  determinism   two replays of the same public inputs agree, so "what the
                publisher did" and "what I recomputed" cannot differ by
                accident
  resumability  replaying from a checkpoint equals replaying from inception,
                which is what bounds audit cost to one checkpoint interval
  tamper        a published state that is not what the published rule
                produces is detectable — this restores the pre-commitment
                property a frozen artefact has natively
  rule pinning  the hash covers gamma/floor/ceil, not just the numbers, so a
                provider cannot silently change the update rule
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta

import numpy as np
import pandas as pd

from soothsayer.adaptive_state import (
    Checkpoint, multiplier_for, replay, verify_checkpoint,
)

TAUS = (0.68, 0.95)
QT = {"normal": {0.68: 1.0, 0.95: 2.0},
      "stress": {0.68: 2.0, 0.95: 4.0}}


def _panel(n_periods: int = 40, seed: int = 0) -> pd.DataFrame:
    """Synthetic panel with two cells and a deterministic move pattern."""
    rng = np.random.default_rng(seed)
    rows = []
    d0 = date(2024, 1, 1)
    for i in range(n_periods):
        cell = "stress" if i % 5 == 0 else "normal"
        for sym in ("A", "B"):
            fc = 100.0
            rows.append({
                "fri_ts": d0 + timedelta(days=i),
                "symbol": sym,
                "regime_pub": cell,
                "fri_close": fc,
                "point": fc,
                "sigma_hat_sym_pre_fri": 0.01,
                "mon_open": fc * (1.0 + rng.normal(0, 0.02)),
            })
    return pd.DataFrame(rows)


def _replay(panel, **kw):
    return replay(panel, QT, TAUS, profile="overnight",
                  artefact_sha256="deadbeef", **kw)


class TestDeterminism(unittest.TestCase):
    def test_two_replays_agree(self):
        p = _panel()
        a, b = _replay(p), _replay(p)
        self.assertEqual(a.checkpoint_sha256, b.checkpoint_sha256)
        self.assertTrue(a.verify_self())

    def test_row_order_does_not_change_the_hash(self):
        p = _panel()
        shuffled = p.sample(frac=1.0, random_state=7).reset_index(drop=True)
        self.assertEqual(_replay(p).checkpoint_sha256,
                         _replay(shuffled).checkpoint_sha256)

    def test_json_round_trip_preserves_hash(self):
        ck = _replay(_panel())
        again = Checkpoint.from_dict(ck.to_dict())
        self.assertEqual(again.checkpoint_sha256, ck.checkpoint_sha256)
        self.assertTrue(again.verify_self())


class TestResumability(unittest.TestCase):
    def test_resume_from_checkpoint_equals_replay_from_inception(self):
        """The property that bounds audit cost to one checkpoint interval."""
        p = _panel(40)
        cut = sorted(set(p["fri_ts"]))[19]
        first = _replay(p, through_period=cut)
        rest = p[p["fri_ts"] > cut]
        resumed = _replay(rest, start_state=first.m)
        one_shot = _replay(p)
        for tau in TAUS:
            for cell in QT:
                self.assertAlmostEqual(
                    resumed.m[tau][cell], one_shot.m[tau][cell], places=10,
                    msg=f"resume diverged at tau={tau} cell={cell}")


class TestTamperDetection(unittest.TestCase):
    def test_edited_state_fails_self_verify(self):
        ck = _replay(_panel())
        d = ck.to_dict()
        d["m"]["0.9500"]["normal"] = 1.5           # someone widens the band
        tampered = Checkpoint.from_dict(d)
        self.assertFalse(tampered.verify_self())

    def test_recompute_catches_a_deviating_publisher(self):
        p = _panel()
        ck = _replay(p)
        d = ck.to_dict()
        d["m"]["0.9500"]["normal"] *= 1.10
        forged = Checkpoint.from_dict(d).sealed()   # re-seal to hide the edit
        self.assertTrue(forged.verify_self(), "re-sealing hides a bare edit")
        ok, _ = verify_checkpoint(forged, p, QT)
        self.assertFalse(ok, "recomputation must still catch it")

    def test_honest_checkpoint_verifies(self):
        p = _panel()
        ok, recomputed = verify_checkpoint(_replay(p), p, QT)
        self.assertTrue(ok)
        self.assertTrue(recomputed.verify_self())


class TestRulePinning(unittest.TestCase):
    def test_gamma_change_changes_the_hash(self):
        p = _panel()
        self.assertNotEqual(_replay(p, gamma=0.05).checkpoint_sha256,
                            _replay(p, gamma=0.10).checkpoint_sha256)

    def test_clip_bounds_are_covered_by_the_hash(self):
        p = _panel()
        self.assertNotEqual(_replay(p, m_ceil=4.0).checkpoint_sha256,
                            _replay(p, m_ceil=8.0).checkpoint_sha256)

    def test_multiplier_lookup_and_unknown_cell_fallback(self):
        ck = _replay(_panel())
        self.assertGreater(multiplier_for(ck, "normal", 0.95), 0.0)
        # a cell with no accumulated state serves the frozen quantile as-is
        self.assertEqual(multiplier_for(ck, "never_seen", 0.95), 1.0)
        with self.assertRaises(KeyError):
            multiplier_for(ck, "normal", 0.85)   # unserved anchor, no interp


class TestGuards(unittest.TestCase):
    def test_missing_columns_raise(self):
        p = _panel().drop(columns=["sigma_hat_sym_pre_fri"])
        with self.assertRaises(ValueError):
            _replay(p)

    def test_multiplier_stays_within_clip_bounds(self):
        # a panel that breaches constantly must not run m away unbounded
        p = _panel()
        p["mon_open"] = p["fri_close"] * 5.0
        ck = _replay(p, m_ceil=4.0)
        for tau in TAUS:
            for cell in QT:
                self.assertLessEqual(ck.m[tau][cell], 4.0 + 1e-9)
                self.assertGreaterEqual(ck.m[tau][cell], 0.25 - 1e-9)


if __name__ == "__main__":
    unittest.main()
