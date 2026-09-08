"""Tests for the migrated balancing state machine."""

from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "akkusteuerung_sma" / "balancing.py"
SPEC = importlib.util.spec_from_file_location("akkusteuerung_balancing", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
balancing = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = balancing
SPEC.loader.exec_module(balancing)


class BalancingTests(unittest.TestCase):
    def test_thirtieth_confirmed_minute_completes_cycle(self):
        state = balancing.BalancingPersistentState(days_since_full=12, done_minutes=29)
        now = datetime(2026, 9, 8, 12, 30)
        changed = balancing.update_balancing_counters(
            state,
            now=now,
            soc=99.0,
            done_soc=98.5,
        )
        self.assertTrue(changed)
        self.assertEqual(0, state.days_since_full)
        self.assertEqual(0, state.done_minutes)
        self.assertTrue(state.completion_valid)
        self.assertEqual(now, state.last_completion)

    def test_fallback_below_done_soc_resets_confirmation(self):
        state = balancing.BalancingPersistentState(done_minutes=17)
        balancing.update_balancing_counters(
            state,
            now=datetime(2026, 9, 8, 12, 31),
            soc=98.0,
            done_soc=98.5,
        )
        self.assertEqual(0, state.done_minutes)

    def test_daylight_due_watchdog_prefers_pv(self):
        result = balancing.balancing_watchdog(
            soc=60,
            days_since_full=14,
            interval_days=14,
            grace_days=3,
            max_paid_ct=25,
            current_price_ct=20,
            feed_in_tariff_ct=8,
            price_level="CHEAP",
            is_day=True,
            grid_balancing_enabled=True,
            resting_cell_spread_mv=None,
            spread_threshold_mv=35,
            spread_cooldown_days=5,
        )
        self.assertEqual("pv", result.mode)

    def test_night_paid_grid_requires_grid_permission(self):
        common = dict(
            soc=60,
            days_since_full=18,
            interval_days=14,
            grace_days=3,
            max_paid_ct=25,
            current_price_ct=20,
            feed_in_tariff_ct=8,
            price_level="CHEAP",
            is_day=False,
            resting_cell_spread_mv=None,
            spread_threshold_mv=35,
            spread_cooldown_days=5,
        )
        blocked = balancing.balancing_watchdog(grid_balancing_enabled=False, **common)
        allowed = balancing.balancing_watchdog(grid_balancing_enabled=True, **common)
        self.assertEqual("aus", blocked.mode)
        self.assertEqual("netz", allowed.mode)


if __name__ == "__main__":
    unittest.main()
