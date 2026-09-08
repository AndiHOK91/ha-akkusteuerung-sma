"""Tests for migrated rolling statistics."""

from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "akkusteuerung_sma" / "statistics.py"
SPEC = importlib.util.spec_from_file_location("akkusteuerung_statistics", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
statistics = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = statistics
SPEC.loader.exec_module(statistics)

RollingMean = statistics.RollingMean


class RollingMeanTests(unittest.TestCase):
    def test_mean_uses_time_window(self):
        mean = RollingMean(timedelta(minutes=60), 1500)
        start = datetime(2026, 9, 8, 12, 0)
        mean.add(start, 100)
        mean.add(start + timedelta(minutes=30), 300)
        self.assertEqual(200, mean.mean)
        mean.add(start + timedelta(minutes=61), 500)
        self.assertEqual(400, mean.mean)

    def test_sampling_size_caps_samples(self):
        mean = RollingMean(timedelta(hours=1), 2)
        start = datetime(2026, 9, 8, 12, 0)
        mean.add(start, 100)
        mean.add(start + timedelta(minutes=1), 200)
        mean.add(start + timedelta(minutes=2), 500)
        self.assertEqual(350, mean.mean)
        self.assertEqual(2, mean.count)


if __name__ == "__main__":
    unittest.main()
