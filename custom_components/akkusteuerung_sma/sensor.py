"""Sensors for SMA Akku Steuerung."""

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
    "pv_surplus": "PV Überschuss",
    "mode": "Strategie Modus",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Create opti sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        OptiSensor(coordinator, key, name) for key, name in SENSORS.items()
    )


class OptiSensor(SensorEntity):
    """Representation of a calculated opti value."""

    def __init__(self, coordinator, key: str, name: str):
        self.coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"akkusteuerung_sma_{key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
