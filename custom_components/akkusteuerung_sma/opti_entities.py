"""Canonical Opti entity definitions.

The original project uses the opti_* canonical layer. This module will
be used while migrating YAML entities into Home Assistant entities.
"""

from __future__ import annotations


CANONICAL_ENTITIES = {
    "target_soc": "sensor.opti_target_soc",
    "charge_power": "sensor.opti_charge_power_w",
    "price_level": "sensor.opti_price_level",
    "peak_reserve_soc": "sensor.opti_peak_reserve_soc",
}
