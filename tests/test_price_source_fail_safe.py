"""Fail-safe tests for temporary electricity-price source outages."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[1] / "custom_components" / "akkusteuerung_sma"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


derived = _load("akkusteuerung_derived_price_fail", "derived.py")
strategy = _load("akkusteuerung_strategy_price_fail", "strategy.py")


class PriceSourceFailSafeTests(unittest.TestCase):
    def test_missing_current_price_never_invents_a_level(self):
        level, percentile, count = derived.price_level(None, [20, 30, 40, 50])
        self.assertIsNone(level)
        self.assertIsNone(percentile)
        self.assertEqual(count, 4)

    def test_too_short_price_series_never_invents_a_level(self):
        level, percentile, count = derived.price_level(30, [20, 30, 40])
        self.assertIsNone(level)
        self.assertIsNone(percentile)
        self.assertEqual(count, 3)

    def _base(self, **overrides):
        values = dict(
            master_enabled=True,
            core_valid=True,
            soc=60.0,
            min_soc=10.0,
            max_soc=95.0,
            target_soc=95.0,
            current_mode=strategy.MODE_DYNAMIC,
            is_day=False,
            forecast_score=5.0,
            forecast_score_tomorrow=5.0,
            price_level=None,
            current_price_ct=None,
            forecast_grid_charge_enabled=True,
            pv_surplus_charge_enabled=True,
            winter_charging_allowed=True,
            feed_in_tariff_ct=8.0,
            grid_charge_spread_ct=10.0,
            hold_spread_ct=0.0,
            peak_reserve_active=False,
            peak_reserve_soc=None,
            peak_reserve_ve_soc=None,
            min_price_before_peak_ct=None,
            peak_price_avg_ct=None,
            peak_price_ve_avg_ct=None,
            charge_ceiling_active=False,
            charge_ceiling_max_soc=95.0,
            balancing_mode="aus",
            surplus_70_active=False,
            surplus_ac_active=False,
            surplus_veto_active=False,
        )
        values.update(overrides)
        return strategy.StrategyInput(**values)

    def test_price_outage_holds_passive_mode(self):
        decision = strategy.decide_strategy(
            self._base(current_mode=strategy.MODE_DISCHARGE_ONLY)
        )
        self.assertEqual(decision.mode, strategy.MODE_DISCHARGE_ONLY)
        self.assertIn("passiver Modus gehalten", decision.reason)

    def test_price_outage_releases_grid_charge(self):
        decision = strategy.decide_strategy(
            self._base(current_mode=strategy.MODE_GRID_CHARGE)
        )
        self.assertEqual(decision.mode, strategy.MODE_DYNAMIC)

    def test_minsoc_still_wins_during_price_outage(self):
        decision = strategy.decide_strategy(self._base(soc=5.0))
        self.assertEqual(decision.mode, strategy.MODE_CHARGE_ONLY)
        self.assertIn("MinSOC", decision.reason)


if __name__ == "__main__":
    unittest.main()
