"""Opti strategy selection entities."""

from homeassistant.components.select import SelectEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Create strategy selector."""
    async_add_entities([OptiModeSelect()])


class OptiModeSelect(SelectEntity):
    """Operating strategy selector."""

    _attr_options = ["Automatik", "Eigenverbrauch", "PV Überschuss", "Nachtladung"]

    def __init__(self):
        self._attr_name = "Akku Strategie Modus"
        self._attr_unique_id = f"{DOMAIN}_strategy_mode"
        self._attr_current_option = "Automatik"

    async def async_select_option(self, option):
        self._attr_current_option = option
        self.async_write_ha_state()
