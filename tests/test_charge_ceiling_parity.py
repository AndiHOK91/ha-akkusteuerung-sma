"""Parity tests for the native charge-ceiling latch."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

MODULE = Path(__file__).parents[1] / "custom_components" / "akkusteuerung_sma" / "peak.py"
spec = importlib.util.spec_from_file_location("akkusteuerung_peak_charge_ceiling", MODULE)
peak = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = peak
spec.loader.exec_module(peak)


class ChargeCeilingParityTests(unittest.TestCase):
    def test_real_entry_holds_until_below_lower_bound(self):
        active = False
        previous_max = None
        for soc, expected in (
            (93.0, False),
            (95.0, True),
            (94.0, True),
            (92.0, True),
            (91.9, False),
            (93.0, False),
        ):
            active = peak.charge_ceiling_active(
                soc=soc,
                max_soc=95.0,
                previous_state=active,
                previous_max_soc=previous_max,
            )
            previous_max = 95.0
            self.assertEqual(active, expected)

    def test_restored_latch_is_kept_inside_hysteresis_band(self):
        self.assertTrue(
            peak.charge_ceiling_active(
                soc=93.0,
                max_soc=95.0,
                previous_state=True,
                previous_max_soc=95.0,
            )
        )
        self.assertFalse(
            peak.charge_ceiling_active(
                soc=91.0,
                max_soc=95.0,
                previous_state=True,
                previous_max_soc=95.0,
            )
        )

    def test_changed_max_soc_does_not_inherit_old_latch(self):
        self.assertFalse(
            peak.charge_ceiling_active(
                soc=98.0,
                max_soc=100.0,
                previous_state=True,
                previous_max_soc=95.0,
            )
        )
        self.assertTrue(
            peak.charge_ceiling_active(
                soc=94.0,
                max_soc=93.0,
                previous_state=False,
                previous_max_soc=95.0,
            )
        )

    def test_direct_limit_always_applies_without_prior_latch(self):
        self.assertTrue(
            peak.charge_ceiling_active(
                soc=95.0,
                max_soc=95.0,
                previous_state=False,
                previous_max_soc=None,
            )
        )


if __name__ == "__main__":
    unittest.main()
