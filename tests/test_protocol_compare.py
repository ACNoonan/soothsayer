from __future__ import annotations

import unittest

import pandas as pd

from soothsayer.backtest.protocol_compare import (
    CAUTION,
    LIQUIDATE,
    SAFE,
    apply_decision_cost,
    bootstrap_variant_deltas,
    enrich_observation_rows,
    evaluate_price_grid,
    make_ltv_grid,
)


class ProtocolCompareTests(unittest.TestCase):
    def test_make_ltv_grid_is_inclusive(self) -> None:
        grid = make_ltv_grid(0.70, 0.71, 50)
        self.assertEqual(grid.tolist(), [0.70, 0.705, 0.71])

    def test_threshold_demote_flips_high_vol_decision(self) -> None:
        ltv_grid = [0.75]
        case_a = evaluate_price_grid(
            fri_close=700.0,
            comparison_price=693.0,
            regime="high_vol",
            ltv_grid=ltv_grid,
            demote_threshold=False,
        )
        case_b = evaluate_price_grid(
            fri_close=700.0,
            comparison_price=693.0,
            regime="high_vol",
            ltv_grid=ltv_grid,
            demote_threshold=True,
        )
        self.assertEqual(case_a.loc[0, "decision"], CAUTION)
        self.assertEqual(case_b.loc[0, "decision"], LIQUIDATE)

    def test_expected_cost_distinguishes_liquidation_severity(self) -> None:
        predicted = pd.Series([SAFE, CAUTION, LIQUIDATE])
        realized = pd.Series([LIQUIDATE, LIQUIDATE, SAFE])
        cost = apply_decision_cost(predicted, realized)
        self.assertEqual(cost.tolist(), [4.0, 2.5, 1.0])

    def test_bootstrap_delta_is_zero_for_identical_variants(self) -> None:
        rows = pd.DataFrame(
            {
                "variant": ["kamino", "kamino", "ss", "ss"],
                "symbol": ["SPY", "QQQ", "SPY", "QQQ"],
                "fri_ts": ["2024-01-05", "2024-01-05", "2024-01-05", "2024-01-05"],
                "ltv_target": [0.75, 0.75, 0.75, 0.75],
                "regime_pub": ["normal", "normal", "normal", "normal"],
                "decision_pred": [SAFE, SAFE, SAFE, SAFE],
                "decision_realized": [SAFE, SAFE, SAFE, SAFE],
                "half_width_bps": [300.0, 300.0, 300.0, 300.0],
            }
        )
        rows = enrich_observation_rows(rows)
        boot = bootstrap_variant_deltas(
            rows,
            baseline_variant="kamino",
            compare_variants=["ss"],
            n_boot=25,
            seed=7,
        )
        self.assertEqual(len(boot), 2)  # pooled + normal
        for col in [
            "delta_mean_half_width_bps",
            "delta_fp_liq_rate",
            "delta_miss_liq_rate",
            "delta_false_caution_rate",
            "delta_missed_caution_rate",
            "delta_expected_loss",
        ]:
            self.assertTrue((boot[col] == 0.0).all(), msg=col)


if __name__ == "__main__":
    unittest.main()
