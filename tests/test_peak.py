"""Parity tests for the migrated peak-reserve calculation."""

from datetime import datetime
import importlib.util
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "akkusteuerung_sma" / "peak.py"
SPEC = importlib.util.spec_from_file_location("akkusteuerung_peak", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
peak = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = peak
SPEC.loader.exec_module(peak)

calculate_peak_reserve = peak.calculate_peak_reserve
pv_rich_day = peak.pv_rich_day
TZ = ZoneInfo("Europe/Berlin")
WINTER_ABEND = datetime(2026, 1, 15, 17, 30, tzinfo=TZ)


def calc(today, tomorrow, *, now=WINTER_ABEND, score_today=1, score_tomorrow=1,
         capacity=12.8, consumption=0.9, min_soc=10, max_soc=95,
         sun_above=False, next_rising=None, markup=0, rich=False):
    if next_rising is None:
        next_rising = datetime(2026, 1, 16, 8, 15, tzinfo=TZ)
    return calculate_peak_reserve(
        now=now,
        next_rising=next_rising,
        sun_above_horizon=sun_above,
        today_score=score_today,
        tomorrow_score=score_tomorrow,
        rich_day=rich,
        prices_today=today,
        prices_tomorrow=tomorrow,
        battery_capacity_kwh=capacity,
        peak_consumption_kw=consumption,
        min_soc=min_soc,
        max_soc=max_soc,
        min_peak_markup_ct=markup,
    )


class PeakReserveParityTests(unittest.TestCase):
    def test_evening_spike_today_counts(self):
        today = [50.0] * 19 + [200.0, 200.0, 200.0, 50.0, 50.0]
        result = calc(today, [50.0] * 24)
        self.assertEqual(3.0, result.peak_hours_ve)
        self.assertEqual(0.0, result.peak_hours_exp)
        self.assertAlmostEqual(33.4, result.reserve_soc, delta=0.2)
        self.assertAlmostEqual(33.4, result.reserve_ve_soc, delta=0.2)
        self.assertEqual(3.0, result.required_kwh)
        self.assertEqual(50.0, result.min_price_before_peak_ct)
        self.assertEqual(200.0, result.peak_price_avg_ct)

    def test_missing_tomorrow_keeps_today_valid(self):
        today = [50.0] * 19 + [200.0, 200.0, 200.0, 50.0, 50.0]
        result = calc(today, [])
        self.assertTrue(result.valid)
        self.assertEqual(3.0, result.peak_hours_ve)

    def test_reserve_is_capped_at_max_soc(self):
        today = [50.0] * 19 + [200.0, 200.0, 200.0, 50.0, 50.0]
        result = calc(today, [50.0] * 24, capacity=2.0)
        self.assertEqual(95.0, result.reserve_soc)

    def test_quarter_hour_raster(self):
        today = [50.0] * 76 + [200.0] * 12 + [50.0] * 8
        result = calc(today, [50.0] * 24)
        self.assertTrue(result.valid)
        self.assertEqual(3.0, result.peak_hours_ve)
        self.assertEqual(3.0, result.required_kwh)

    def test_mixed_raster(self):
        today = [50.0] * 24
        tomorrow = [50.0] * 76 + [200.0] * 12 + [50.0] * 8
        result = calc(today, tomorrow, score_tomorrow=1)
        self.assertTrue(result.valid)
        self.assertEqual(3.0, result.peak_hours_ve)
        self.assertEqual(3.0, result.required_kwh)

    def test_implausible_raster_invalidates_all_prices(self):
        result = calc([50.0] * 40, [50.0] * 24)
        self.assertFalse(result.valid)

    def test_dst_quarter_hour_lengths_are_valid(self):
        self.assertTrue(calc([50.0] * 92, [50.0] * 24).valid)
        self.assertTrue(calc([50.0] * 100, [50.0] * 24).valid)

    def test_current_peak_hour_counts(self):
        now = datetime(2026, 1, 15, 20, 30, tzinfo=TZ)
        today = [50.0] * 19 + [200.0, 200.0, 200.0, 50.0, 50.0]
        result = calc(today, [50.0] * 24, now=now)
        self.assertEqual(2.0, result.peak_hours_ve)
        self.assertGreater(result.required_kwh, 0)

    def test_good_sunny_day_has_empty_horizon(self):
        now = datetime(2026, 6, 20, 12, 30, tzinfo=TZ)
        today = [20.0] * 12 + [200.0] + [20.0] * 11
        result = calc(today, [20.0] * 24, now=now, score_today=9, sun_above=True)
        self.assertEqual(0.0, result.peak_hours_ve)
        self.assertEqual(0.0, result.required_kwh)

    def test_min_price_before_peak_stops_at_first_peak(self):
        today = [50.0] * 18 + [30.0, 200.0, 200.0, 10.0, 50.0, 50.0]
        result = calc(today, [50.0] * 24)
        self.assertEqual(30.0, result.min_price_before_peak_ct)

    def test_economic_filter_flat_day(self):
        filtered = calc([30.0] * 24, [30.5] * 24, markup=10)
        self.assertEqual(0.0, filtered.required_kwh)
        self.assertEqual(0.0, filtered.peak_hours_ve)
        self.assertEqual(0.0, filtered.peak_hours_exp)
        unfiltered = calc([30.0] * 24, [30.5] * 24, markup=0)
        self.assertEqual(24.0, unfiltered.peak_hours_exp)
        self.assertGreater(unfiltered.required_kwh, 0)

    def test_economic_filter_boundary_is_inclusive(self):
        today = [50.0] * 20 + [60.0] * 4
        tomorrow = [50.0] * 24
        exact = calc(today, tomorrow, markup=10)
        self.assertEqual(4.0, exact.peak_hours_ve)
        self.assertEqual(50.0, exact.window_min_ct)
        above = calc(today, tomorrow, markup=10.5)
        self.assertEqual(0.0, above.peak_hours_ve)

    def test_ve_average_only_uses_very_expensive_slots(self):
        today = [20.0 + i for i in range(24)]
        tomorrow = [20.0 + i for i in range(24)]
        result = calc(today, tomorrow)
        self.assertGreater(result.peak_hours_ve, 0)
        self.assertGreater(result.peak_hours_exp, 0)
        self.assertEqual(41.0, result.peak_price_ve_avg_ct)
        self.assertNotEqual(result.peak_price_ve_avg_ct, result.peak_price_avg_ct)

    def test_rich_day_shortens_recharge_buffer(self):
        now = datetime(2026, 7, 27, 3, 40, tzinfo=TZ)
        rising = datetime(2026, 7, 27, 5, 45, tzinfo=TZ)
        prices = [25.0] * 24 + [31.0] * 4 + [32.0] * 4 + [34.0] * 4 + [10.0] * 36 + [40.0] * 16 + [25.0] * 8
        result = calc(
            prices, [], now=now, score_today=10, score_tomorrow=10,
            capacity=12.8, consumption=0.8, min_soc=5,
            next_rising=rising, rich=True,
        )
        self.assertEqual(datetime(2026, 7, 27, 6, 45, tzinfo=TZ), result.horizon_end)
        self.assertEqual(0.75, result.peak_hours_ve + result.peak_hours_exp)
        self.assertEqual(0.67, result.required_kwh)

    def test_pv_rich_day_hysteresis_and_season_gate(self):
        july = datetime(2026, 7, 27, 3, 40, tzinfo=TZ)
        rising = datetime(2026, 7, 27, 5, 45, tzinfo=TZ)
        self.assertTrue(pv_rich_day(next_rising=rising, now=july, today_score=10, tomorrow_score=8, previous_state=False))
        self.assertTrue(pv_rich_day(next_rising=rising, now=july, today_score=9, tomorrow_score=8, previous_state=True))
        self.assertFalse(pv_rich_day(next_rising=rising, now=july, today_score=9, tomorrow_score=8, previous_state=False))
        march = datetime(2026, 3, 20, 3, 40, tzinfo=TZ)
        march_rising = datetime(2026, 3, 20, 6, 15, tzinfo=TZ)
        self.assertFalse(pv_rich_day(next_rising=march_rising, now=march, today_score=10, tomorrow_score=10, previous_state=True))


if __name__ == "__main__":
    unittest.main()
