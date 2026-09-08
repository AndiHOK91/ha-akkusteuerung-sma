"""Parity tests for the migrated surplus gates."""

import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "akkusteuerung_sma" / "surplus.py"
SPEC = importlib.util.spec_from_file_location("akkusteuerung_surplus", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
surplus = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = surplus
SPEC.loader.exec_module(surplus)

surplus_70_raw = surplus.surplus_70_raw
surplus_ac_raw = surplus.surplus_ac_raw
surplus_veto_raw = surplus.surplus_veto_raw


class SurplusParityTests(unittest.TestCase):
    def test_70_threshold_zero_disables_gate(self):
        raw, value, threshold_off = surplus_70_raw(
            grid_export_w=5000,
            battery_power_w=1000,
            threshold_on_w=0,
            was_on=False,
        )
        self.assertFalse(raw)
        self.assertEqual(6000, value)
        self.assertEqual(-1000, threshold_off)

    def test_ac_threshold_zero_disables_gate(self):
        raw, value, threshold_off = surplus_ac_raw(
            pv_power_w=5000,
            battery_power_w=1000,
            threshold_on_w=0,
            was_on=False,
        )
        self.assertFalse(raw)
        self.assertEqual(6000, value)
        self.assertEqual(-300, threshold_off)

    def test_70_hysteresis_holds_existing_on_state(self):
        raw, _value, threshold_off = surplus_70_raw(
            grid_export_w=3500,
            battery_power_w=0,
            threshold_on_w=4000,
            was_on=True,
        )
        self.assertTrue(raw)
        self.assertEqual(3000, threshold_off)

    def test_ac_hysteresis_holds_existing_on_state(self):
        raw, _value, threshold_off = surplus_ac_raw(
            pv_power_w=3800,
            battery_power_w=0,
            threshold_on_w=4000,
            was_on=True,
        )
        self.assertTrue(raw)
        self.assertEqual(3700, threshold_off)

    def test_veto_subtracts_grid_import(self):
        raw, value, scarcity_open = surplus_veto_raw(
            grid_export_w=0,
            grid_import_w=3000,
            battery_power_w=3000,
            threshold_on_w=200,
            threshold_off_w=100,
            forecast_surplus_kwh=1,
            needed_full_kwh=5,
            scarcity_factor=1,
            was_on=False,
        )
        self.assertTrue(scarcity_open)
        self.assertEqual(0, value)
        self.assertFalse(raw)

    def test_veto_forecast_uncertainty_fails_open(self):
        raw, value, scarcity_open = surplus_veto_raw(
            grid_export_w=500,
            grid_import_w=0,
            battery_power_w=0,
            threshold_on_w=200,
            threshold_off_w=100,
            forecast_surplus_kwh=None,
            needed_full_kwh=None,
            scarcity_factor=1,
            was_on=False,
        )
        self.assertTrue(scarcity_open)
        self.assertEqual(500, value)
        self.assertTrue(raw)


if __name__ == "__main__":
    unittest.main()
