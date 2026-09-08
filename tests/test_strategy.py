"""Parity-oriented tests for the migrated Opti core strategy ladder."""

from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "akkusteuerung_sma" / "strategy.py"
SPEC = importlib.util.spec_from_file_location("akkusteuerung_strategy", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
strategy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = strategy
SPEC.loader.exec_module(strategy)

MODE_CHARGE_ONLY = strategy.MODE_CHARGE_ONLY
MODE_DISCHARGE_ONLY = strategy.MODE_DISCHARGE_ONLY
MODE_DYNAMIC = strategy.MODE_DYNAMIC
MODE_GRID_CHARGE = strategy.MODE_GRID_CHARGE
MODE_PAUSE = strategy.MODE_PAUSE
StrategyInput = strategy.StrategyInput
decide_strategy = strategy.decide_strategy

BASE = StrategyInput(
    master_enabled=True,
    core_valid=True,
    soc=50,
    min_soc=10,
    max_soc=95,
    target_soc=70,
    current_mode=MODE_DYNAMIC,
    is_day=True,
    forecast_score=5,
    forecast_score_tomorrow=5,
    price_level="NORMAL",
    current_price_ct=30,
    forecast_grid_charge_enabled=True,
    pv_surplus_charge_enabled=True,
    winter_charging_allowed=True,
    feed_in_tariff_ct=8,
    grid_charge_spread_ct=10,
    hold_spread_ct=5,
    peak_reserve_active=False,
    peak_reserve_soc=None,
    peak_reserve_ve_soc=None,
    min_price_before_peak_ct=None,
    peak_price_avg_ct=None,
    peak_price_ve_avg_ct=None,
    charge_ceiling_active=False,
    charge_ceiling_max_soc=95,
)


class StrategyTests(unittest.TestCase):
    def test_master_off_is_pause(self):
        decision = decide_strategy(replace(BASE, master_enabled=False))
        self.assertEqual(MODE_PAUSE, decision.mode)

    def test_invalid_core_is_pause(self):
        decision = decide_strategy(replace(BASE, core_valid=False))
        self.assertEqual(MODE_PAUSE, decision.mode)

    def test_minsoc_has_top_strategy_priority(self):
        decision = decide_strategy(
            replace(
                BASE,
                soc=5,
                forecast_score=0,
                current_price_ct=-10,
                feed_in_tariff_ct=8,
                peak_reserve_active=True,
                peak_reserve_soc=80,
                peak_reserve_ve_soc=60,
                peak_price_avg_ct=60,
                price_level="VERY_EXPENSIVE",
            )
        )
        self.assertEqual(MODE_CHARGE_ONLY, decision.mode)
        self.assertIn("MinSOC", decision.reason)

    def test_negative_price_grid_charge(self):
        decision = decide_strategy(
            replace(BASE, soc=40, forecast_score=1, current_price_ct=2, feed_in_tariff_ct=8)
        )
        self.assertEqual(MODE_GRID_CHARGE, decision.mode)

    def test_peak_l1_beats_forecast_charge(self):
        decision = decide_strategy(
            replace(
                BASE,
                soc=50,
                forecast_score=1,
                forecast_score_tomorrow=1,
                price_level="VERY_EXPENSIVE",
                current_price_ct=50,
                peak_reserve_active=True,
                peak_reserve_soc=70,
                peak_reserve_ve_soc=50,
                peak_price_avg_ct=55,
            )
        )
        self.assertEqual(MODE_DISCHARGE_ONLY, decision.mode)
        self.assertIn("L1", decision.reason)

    def test_target_soc_hysteresis(self):
        entering = decide_strategy(replace(BASE, soc=72, target_soc=70, current_mode=MODE_DYNAMIC))
        self.assertEqual(MODE_DYNAMIC, entering.mode)
        leaving = decide_strategy(replace(BASE, soc=74, target_soc=70, current_mode=MODE_DYNAMIC))
        self.assertEqual(MODE_DISCHARGE_ONLY, leaving.mode)

    def test_missing_price_holds_only_passive_mode(self):
        passive = decide_strategy(
            replace(BASE, soc=70, target_soc=70, price_level=None, current_mode=MODE_DISCHARGE_ONLY)
        )
        self.assertEqual(MODE_DISCHARGE_ONLY, passive.mode)
        forced = decide_strategy(
            replace(BASE, soc=70, target_soc=70, price_level=None, current_mode=MODE_GRID_CHARGE)
        )
        self.assertEqual(MODE_DYNAMIC, forced.mode)


if __name__ == "__main__":
    unittest.main()
