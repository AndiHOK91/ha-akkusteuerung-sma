"""Configurable Opti helper numbers."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity

from .const import DOMAIN


NUMBERS = [
    ("Maximaler SOC", "max_soc", 100, 0, 100, 1),
    ("Minimaler SOC", "min_soc", 10, 0, 100, 1),
    ("Maximale Ladeleistung", "max_charge_power", 5000, 0, 10000, 100),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Create Opti helper number entities."""
    async_add_entities([OptiNumber(name, key, value, minimum, maximum, step) for name, key, value, minimum, maximum, step in NUMBERS])


class OptiNumber(NumberEntity):
    """Opti helper number entity."""

    _attr_native_unit_of_measurement = ""

    def __init__(self, name, key, value, minimum, maximum, step):
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_native_value = value
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step

    async def async_set_native_value(self, value):
        self._attr_native_value = value
        self.async_write_ha_state()
