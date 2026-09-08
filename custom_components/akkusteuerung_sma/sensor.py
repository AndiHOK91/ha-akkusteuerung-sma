"""Sensors for SMA Akku Steuerung.

Migrated from the opti canonical sensor layer.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

SENSORS = {
    "target_soc": "Ziel SOC",
    "charge_power": "Optimale Ladeleistung",
    "price_level": "Preisniveau",
    "peak_reserve_soc": "Peak Reserve SOC",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Create opti sensors."""
    async_add_entities(
        OptiSensor(entry, key, name) for key, name in SENSORS.items()
    )


class OptiSensor(SensorEntity):
    """Representation of a migrated opti sensor."""

    def __init__(self, entry: ConfigEntry, key: str, name: str) -> None:
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._entry = entry

    @property
    def native_value(self):
        """Return current calculated value.

        Calculation will be supplied by the migrated strategy coordinator.
        """
        data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        return data.get(self._key)
